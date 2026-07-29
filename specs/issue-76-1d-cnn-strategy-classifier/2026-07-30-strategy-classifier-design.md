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

Derived from known map data or clustered from early-game timing distributions in the dataset. Maps not in the table get "unknown" defaults. Static features appended to every time window.

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
| MACRO_ECONOMY | T, Z, P | Early expansion, delayed army |
| TECH_RUSH | T, Z, P | Fast tech path, skip early units |

### Feature Engineering

Raw MSC features → windowed `[W, F]` tensors:

- Fixed-width time windows (30 seconds each)
- For classification at minute T, windows 0 through T/0.5
- Pad to max window count (10 for minute 5)
- Features per window (F):
  - Our state: resource rates, supply, building counts, unit counts, upgrade flags
  - Scouted opponent state: same categories but fog-masked (zeros where unscouted)
  - Scouting flag: binary — distinguishes "no buildings" from "haven't looked"
  - Map characteristics: static, repeated each window

### Split

Train/val/test 7:1:2 per MSC convention, stratified by matchup and archetype.

## Model Architecture

```
Input [batch, W, F]
  |
  +- Conv1D(F -> 64, kernel=3, padding=1) + BatchNorm + ReLU
  +- Conv1D(64 -> 128, kernel=3, padding=1) + BatchNorm + ReLU
  |
  +- Single-head self-attention over the time axis
  |   (queries/keys/values from the 128-dim conv output)
  |
  +- Global average pooling over time -> [batch, 128]
  +- Dense(128 -> 64) + ReLU + Dropout(0.3)
  +- Dense(64 -> num_archetypes) -> logits
```

Output is raw logits — softmax applied at inference time by the Java consumer (following the `TextClassifier` pattern).

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
    dummy_input,                          # [1, W, F]
    "strategy_vs_terran.onnx",
    input_names=["features"],
    output_names=["logits"],
    dynamic_axes={"features": {0: "batch"}, "logits": {0: "batch"}}
)
```

Dynamic batch dimension for `OnnxInferenceModel.runBatch()`. Static window and feature dimensions — the Java caller pads to the expected shape.

Output artifacts: `strategy_vs_terran.onnx`, `strategy_vs_zerg.onnx`, `strategy_vs_protoss.onnx`.

## Evaluation

**Metrics** (per-matchup model on test split):
- Top-1 accuracy: overall and per-archetype
- Top-3 accuracy: overall
- Early detection accuracy: top-1 at minute 2, 3, 4, 5
- Confidence calibration: reliability diagram
- Inference latency: p50/p95/p99 over 1000 runs (Python ONNX Runtime)

**Acceptance criteria**:
- >= 65% top-1 at minute 4
- >= 85% top-3 at minute 4
- >= 50% top-1 at minute 2 for critical archetypes (rush, cannon rush, proxy)
- Inference < 10ms on CPU
- Model file < 10MB

**Output**: summary report (printed + JSON), confusion matrix per matchup.

## Java Integration

Validation test in `inference-runtime/src/test/java/`:
1. Load each `.onnx` via `OnnxInferenceModel` with `ModelConfig` (no tokenizer)
2. Construct `InferenceInput.Tensor` with shape `{features: float[1][W][F]}`
3. Verify: output name "logits", shape matches archetype count, values finite, softmax sums to ~1.0
4. Test `runBatch()` with multiple samples
5. Latency: 1000 runs, assert p99 < 10ms

The `.onnx` files are checked into `inference-runtime/src/test/resources/models/strategy/` as test resources. QuarkMind pulls them from a model registry for production use.

No new production Java code — `OnnxInferenceModel` + `InferenceInput.Tensor` already supports everything needed.

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
```

Self-contained venv, same pattern as `evaluation/code_domain_embeddings/`. Run with `python3 -m evaluation.strategy_classifier.<script>`.

## Research References

- [TacticCraft (2025)](https://arxiv.org/abs/2507.15618) — tactic tensor taxonomy, LLM-classified replay labels
- [SC-Phi2 (2024)](https://www.mdpi.com/2673-2688/5/4/115) — SLM for build order prediction, LoRA on single GPU
- [Transformers for SC2 Macromanagement (2021)](https://arxiv.org/pdf/2110.05343) — Transformer beats GRU/LSTM on MSC
- [Bayesian Build Tree Prediction (2019)](https://alexander-parker.github.io/2019-09-20-Predicting-Opponent-Strategy-in-StarCraft/) — lightweight baseline
- [AlphaStar (2019)](https://deepmind.google/blog/alphastar-mastering-the-real-time-strategy-game-starcraft-ii/) — deep LSTM under partial observability
- [MSC Dataset (Wu et al. 2017)](https://github.com/wuhuikai/MSC) — 36k+ SC2 replays with pre-extracted features
