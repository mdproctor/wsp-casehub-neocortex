# SC2 Strategy Classifier — Design Spec

**Issue**: casehubio/neocortex#76 (training), casehubio/neocortex#75 (dataset)
**Branch**: `issue-76-1d-cnn-strategy-classifier`
**Date**: 2026-07-30
**Cross-repo**: feeds casehubio/quarkmind#208 (ONNX strategy classifier epic)

## Problem

QuarkMind's three-tier enemy strategy classifier (Drools CEP → ONNX → LLM) needs a trained neural network for the middle tier. The model classifies opponent strategic intent from partial scouting observations in <10ms on CPU. The gap: Drools is fast but only recognises hand-authored patterns; the LLM handles anything but costs 500ms+. A trained model covers the space between — variations of known archetypes, hybrid strategies, and meta shifts.

## Design Decisions

- **Architecture**: CNN-Attention hybrid — 1D-CNN for local temporal pattern extraction, single self-attention layer for cross-window relationships, classification head. Captures both "Barracks then Factory within 60s" (local) and "early Refinery relates to late Starport" (global).
- **Per-matchup models**: three separate models (vs-Terran, vs-Zerg, vs-Protoss). Opponent race is known at game start; the feature distributions are fundamentally different across races.
- **Map characteristics as features**: rush distance, expansion count, map size, choke type — encoded as input features, not as model boundaries. Maps influence viable strategies but there are too many named maps to train per-map models.
- **Fog-of-war from the start**: inputs are masked to simulate realistic scouting. Labels come from the opponent's complete build order. The model learns: "given what I've scouted → what are they actually doing behind the fog."
- **Hybrid labelling**: rule-based for unambiguous archetypes (rush, cannon rush, macro economy), LLM for ambiguous/hybrid builds.
- **Pre-extracted MSC features**: download the .npz sparse matrices (Wu et al. 2017), skip replay parsing entirely.

## Data Pipeline

### MSC Download

Download pre-extracted global features from the MSC Google Drive. Each replay yields a `(T, M)` sparse matrix with per-timestep features: resources, buildings, units, upgrades, scores. Both players' data plus metadata (map name, matchup, result).

### Map Characteristic Extraction

Lookup table mapping MSC map names to derived characteristics:

| Characteristic | Type | Values |
|---|---|---|
| Rush distance | categorical | short / medium / long |
| Expansion count | numeric | number of natural expansion locations |
| Map size | categorical | small / medium / large |
| Choke type | categorical | wall-off possible / open natural |

Derived from known map data or clustered from early-game timing distributions in the dataset. Maps not in the table get "unknown" defaults. Provided as a separate static input tensor (see §Feature Engineering).

### Fog-of-War Simulation

For each replay with Player A and Player B:
- **Input**: Player A's own state (full visibility) + masked view of Player B's state
- **Label**: Player B's actual strategic archetype (from their complete build order)

Masking model simulates realistic scouting:
- Pre-scout (minute 0–1.5): no opponent info visible except race
- First scout arrival (~minute 1.5–2.5): main base buildings visible
- Mid-game scouting (minute 3+): gradually reveal more based on typical scout patterns
- Random variation per epoch in scout timing — acts as data augmentation

### Hybrid Labelling

**Pass 1 — Rule-based**: pattern-match against the archetype taxonomy from quarkmind#183. High-confidence threshold — only label when the signal is unambiguous.

Example rules:
- Pool before Hatchery before minute 2 → ZERG_RUSH
- Forge + Cannon near opponent before minute 4 → CANNON_RUSH
- 3+ Command Centres before significant army → MACRO_ECONOMY
- Barracks + Marines + no expansion before minute 3 → TERRAN_RUSH

**Pass 2 — LLM**: replays not labelled by rules get their complete build order fed to an LLM with the archetype taxonomy as a classification prompt. Returns archetype + confidence. Low-confidence labels flagged for exclusion.

**Archetype taxonomy** (from quarkmind#183, extended):

| Archetype | Races | Key signals |
|---|---|---|
| RUSH | T, Z, P | Early aggression, low economy |
| PROXY | T, P | Production structures near opponent |
| CANNON_RUSH | P | Forge + Cannons near enemy |
| BANSHEE_HARASS | T | Starport + Tech Lab, cloaked air |
| AIR_SUPERIORITY | T, P | Air-dominant composition |
| MECH_PUSH | T | Factory + Siege Tanks + Thors |
| BIO_TIMING | T | Barracks ×3+ + Medivac |
| ROACH_RUSH | Z | Early Roach Warren |
| LING_BANE | Z | Baneling Nest + speed, aggressive zergling/baneling |
| MUTA_HARASS | Z | Spire + Mutalisks |
| HYDRA_PUSH | Z | Hydralisk Den, ground-heavy composition |
| DT_RUSH | P | Dark Shrine, fast tech to Dark Templars |
| BLINK_STALKER | P | Twilight Council + Blink research |
| COLOSSUS_PUSH | P | Robotics Bay + Colossi |
| MACRO_ECONOMY | T, Z, P | Early expansion, delayed army |
| TECH_RUSH | T, Z, P | Fast tech path, skip early units |

**Per-matchup class counts**: vs-Terran 8, vs-Zerg 7, vs-Protoss 9. All archetypes are detectable from MSC's per-timestep building, unit, and upgrade features.

### Dataset Age

MSC replays are from StarCraft II circa 2017 (patches 3.x). The archetype taxonomy targets current meta (patches 5.x). Fundamental archetypes (rush, macro, tech) are stable across patches, but specific feature distributions (building timings, unit composition frequencies) may have shifted. Training on MSC establishes a baseline; the held-out QuarkMind replays (casehubio/quarkmind#213) validate whether that baseline transfers to current meta. If transfer validation shows significant degradation, more recent replay data will be needed.

### Feature Engineering

Raw MSC features → two tensor groups:

**Temporal features** — windowed `[W, F_temporal]` tensor:
- Fixed-width time windows (30 seconds each)
- For classification at minute T, windows 0 through T/0.5
- Pad to max window count (10 for minute 5)
- Features per window (F_temporal):
  - Our state: resource rates, supply, building counts, unit counts, upgrade flags
  - Scouted opponent state: same categories but fog-masked (zeros where unscouted)
  - Scouting flag: binary — distinguishes "no buildings" from "haven't looked"

**Static map features** — `[F_map]` vector (not repeated per window):
- Rush distance, expansion count, map size, choke type
- Concatenated after temporal pooling, before the dense classification layers
- Static features contribute nothing to temporal convolution or cross-window attention; placing them after pooling lets the dense layers combine learned temporal patterns with map context

### Split

Train/val/test 7:1:2 per MSC convention, stratified by matchup and archetype. **Split unit is per-replay** — all time-window samples from the same replay go into the same partition. This prevents information leakage: a minute-2 sample in training would leak features to a minute-5 sample from the same replay in test, since the later sample is a superset of the earlier one.

## Model Architecture

```
Temporal Input [batch, W, F_temporal]    Map Input [batch, F_map]
  |                                        |
  +- Conv1D(F_temporal -> 64, k=3, pad=1)  |
  |  + BatchNorm + ReLU                    |
  +- Conv1D(64 -> 128, k=3, pad=1)        |
  |  + BatchNorm + ReLU                    |
  |                                        |
  +- Sinusoidal positional encoding        |
  +- Self-attention (padding mask)         |
  |                                        |
  +- Masked average pooling -> [batch,128] |
  |                                        |
  +------------ Concat ------------------->+
               [batch, 128 + F_map]
               |
               +- Dense(128 + F_map -> 64) + ReLU + Dropout(0.3)
               +- Dense(64 -> num_archetypes) -> logits
```

Output is temperature-scaled logits — softmax applied at inference time by `TensorClassifier`. Temperature is calibrated post-training on the validation set and baked into the model (final layer weights and biases scaled by 1/T) before ONNX export. Both must be scaled: `logits/T = (W*x + b)/T = (W/T)*x + (b/T)`.

**Positional encoding**: sinusoidal (fixed, no learnable parameters) added to the 128-dim conv output before self-attention. Required because attention is position-invariant — without it, the model cannot distinguish "Refinery at minute 1, Starport at minute 3" from the reverse ordering.

**Padding mask**: derived from the temporal input — any time window where all features are zero is treated as padding. Player state features (resource rates, supply) are always non-zero for real game windows, making this heuristic reliable. The mask is used for both self-attention (padded positions receive zero attention weight) and average pooling (mean computed only over non-padded windows). This prevents zero-padding from diluting the signal at early time points — at minute 2 with only 4/10 real windows, unmasked pooling would dilute by 60%.

**Input handling**: two ONNX inputs. `InferenceInput.Tensor` uses `Map<String, float[][]>` (rank-2). The Java caller provides `InferenceInput.tensor(Map.of("temporal", float[1][W*F_temporal], "map", float[1][F_map]))`. The model reshapes "temporal" from `[batch, W*F_temporal]` to `[batch, W, F_temporal]` via an ONNX Reshape op. "map" passes directly to the concatenation layer after temporal pooling.

**Parameter budget**: ~200K per model, <10MB total for all three.

## Training

- **Optimizer**: AdamW, lr=1e-3 with cosine annealing
- **Loss**: focal loss (gamma=2) — handles class imbalance for rare archetypes
- **Batch size**: 128
- **Epochs**: 50 with early stopping on validation loss (patience 10)
- **Fog-of-war augmentation**: stochastic masking re-applied each epoch
- **Multi-window training**: each replay produces samples at minute 2, 3, 4, 5 (same label, increasingly complete input)
- **Reproducibility**: fixed random seeds, all hyperparameters in config, training logs

## ONNX Export

```python
torch.onnx.export(
    model,
    (dummy_temporal, dummy_map),          # [1, W*F_temporal], [1, F_map]
    "strategy_vs_terran.onnx",
    input_names=["temporal", "map"],
    output_names=["logits"],
    dynamic_axes={
        "temporal": {0: "batch"},
        "map": {0: "batch"},
        "logits": {0: "batch"}
    },
    opset_version=17
)
```

Two inputs with dynamic batch dimension. Static window and feature dimensions — the Java caller pads temporal features to the expected shape. `opset_version=17` pinned for reproducibility and ONNX Runtime compatibility.

**Temperature baking**: after calibrating optimal temperature T on the validation set, scale the final linear layer's weights and biases by 1/T before export. The full logit `W*x + b` must be divided by T, requiring both terms: `(W/T)*x + (b/T)`. Scaling weights alone leaves the bias unscaled, which shifts the calibrated distribution — classes with large bias values would retain their full advantage rather than having it attenuated. The exported model produces temperature-scaled logits directly — no runtime calibration parameter needed.

Output artifacts: `strategy_vs_terran.onnx`, `strategy_vs_zerg.onnx`, `strategy_vs_protoss.onnx`.

## Evaluation

**Metrics** (per-matchup model on test split):
- Top-1 accuracy: overall and per-archetype
- Top-3 accuracy: overall
- Early detection accuracy: top-1 at minute 2, 3, 4, 5
- Confidence calibration: reliability diagram, before and after temperature scaling
- Temperature scaling: find optimal T on validation set, verify calibration improvement
- Inference latency: p50/p95/p99 over 1000 single-sample runs (Python ONNX Runtime)

**Acceptance criteria**:
- >= 65% top-1 at minute 4
- >= 85% top-3 at minute 4
- >= 50% top-1 at minute 2 for critical archetypes (rush, cannon rush, proxy)
- Inference < 10ms on CPU
- Model file < 10MB

**Output**: summary report (printed + JSON), confusion matrix per matchup.

## Java Integration

### TensorClassifier adapter

New `TensorClassifier` in `inference-tasks` — same pattern as `TextClassifier` but accepts `InferenceInput.Tensor` (named float tensors) instead of text. Encapsulates softmax, argmax, and label mapping. Returns `ClassificationResult`. This is required to satisfy neocortex's architectural contract (ARC42STORIES §4: "typed task adapters interpret tensor names and post-process outputs into domain types"; §8 anti-pattern: "Exposing tensors to callers").

Without this adapter, QuarkMind's `CascadingPatternClassifier` would need to construct `InferenceInput.tensor(...)`, extract the `"logits"` tensor by name, apply softmax manually, and map indices to labels — exactly the steps the task adapter layer exists to encapsulate. Issue #77 deferred this adapter; this spec includes it.

### Validation test

In `inference-runtime/src/test/java/`:
1. Load each `.onnx` via `OnnxInferenceModel` with `ModelConfig` (no tokenizer)
2. Construct `InferenceInput.Tensor` with `{temporal: float[1][W*F_temporal], map: float[1][F_map]}`
3. Verify via `TensorClassifier`: output is `ClassificationResult` with correct archetype labels, probabilities sum to ~1.0
4. Latency: 1000 single-sample runs, assert p99 < 10ms

The `.onnx` files are checked into `inference-runtime/src/test/resources/models/strategy/` as test resources. QuarkMind pulls them from a model registry for production use.

**Batching note**: `OnnxInferenceModel.runBatch()` for `Tensor` inputs executes sequentially (one ONNX session call per sample). The game-loop use case is single-sample inference (one classification per tick), so this is not a performance concern. True tensor batching (stacking samples into a single `float[N][W*F]` call) is a potential neocortex follow-up if batch throughput becomes important.

## Project Structure

```
evaluation/
  strategy_classifier/
    __init__.py
    requirements.txt
    config.py

    # Data pipeline (#75)
    download_msc.py
    map_features.py
    fog_of_war.py
    labelling/
      __init__.py
      rules.py
      llm_labeller.py
      label_pipeline.py
    feature_engineering.py
    dataset.py

    # Model (#76)
    model.py
    train.py
    export_onnx.py
    evaluate.py

    # Output (gitignored)
    data/
    models/
    output/

inference-runtime/
  src/test/
    java/.../runtime/
      StrategyClassifierOnnxTest.java
    resources/models/strategy/
      strategy_vs_terran.onnx
      strategy_vs_zerg.onnx
      strategy_vs_protoss.onnx
      model_manifest.json        # training run metadata: date, dataset, accuracy, hyperparams
```

Self-contained venv, same pattern as `evaluation/code_domain_embeddings/`. Run with `python3 -m evaluation.strategy_classifier.<script>`.

## Research References

- [TacticCraft (2025)](https://arxiv.org/abs/2507.15618) — tactic tensor taxonomy, LLM-classified replay labels
- [SC-Phi2 (2024)](https://www.mdpi.com/2673-2688/5/4/115) — SLM for build order prediction, LoRA on single GPU
- [Transformers for SC2 Macromanagement (2021)](https://arxiv.org/pdf/2110.05343) — Transformer beats GRU/LSTM on MSC
- [Bayesian Build Tree Prediction (2019)](https://alexander-parker.github.io/2019-09-20-Predicting-Opponent-Strategy-in-StarCraft/) — lightweight baseline
- [AlphaStar (2019)](https://deepmind.google/blog/alphastar-mastering-the-real-time-strategy-game-starcraft-ii/) — deep LSTM under partial observability
- [MSC Dataset (Wu et al. 2017)](https://github.com/wuhuikai/MSC) — 36k+ SC2 replays with pre-extracted features
