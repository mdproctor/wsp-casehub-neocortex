# Retrain Strategy Classifier on Real Replay Data

## Problem

Three per-matchup ONNX strategy classifiers (vs_terran, vs_zerg, vs_protoss) exist but were trained on synthetic data. The synthetic training exposed severe class imbalance that real data inherits: ROACH_RUSH dominates at 58% of vs_zerg samples, while tail archetypes are broken (MUTA_HARASS: 33 samples, HYDRA_PUSH: 28, TECH_RUSH: 4). The acceptance criteria from #76 were validated against synthetic data only.

## Data Sources

Three public SC2 replay sources, ingested sequentially into one combined dataset:

| Source | Scale | Format | Adapter |
|--------|-------|--------|---------|
| SC2EGSet | ~17,930 esports replays | Pre-extracted JSON game states | `prepare_real_data.py` (existing) |
| MSC (Wu et al.) | ~36,000 replays | Per-timestep sparse matrices | `ingest_msc.py` (new) |
| Spawning Tool | Variable — targeted replay packs | Raw `.SC2Replay` files | `ingest_spawningtool.py` (new) |

Spawning Tool harvesting is targeted: search for replay packs rich in underrepresented archetypes (muta harass, hydra push, DT rush, cannon rush) to address class imbalance at the data level rather than relying solely on algorithmic compensation.

## Unified Labelling Pipeline

Each source has a thin adapter that normalizes replays to a common build-order format: `List[{type: "building"|"unit", name: str, minute: float}]`. The existing rule-based labeller (`labelling/rules.py`) classifies all samples regardless of source. This ensures consistent labels across datasets — no label disagreement between sources using different taxonomies.

The adapter per source:
- **SC2EGSet:** `prepare_real_data.py` already extracts build orders from JSON tracker events. No changes needed.
- **MSC:** `ingest_msc.py` extracts build orders from MSC's per-timestep sparse feature matrices. Maps unit/building presence changes to timestamped build events.
- **Spawning Tool:** `ingest_spawningtool.py` uses the `spawningtool` Python library (v3.0.0) to parse raw `.SC2Replay` files and extract build orders. The library already produces timestamped build events — the adapter normalizes field names.

## Dataset Merge and Consolidation

`merge_datasets.py` combines all three sources' labelled data:

1. Load labelled samples from each source (SC2EGSet, MSC, Spawning Tool)
2. Merge into unified per-matchup pools
3. Report per-class sample counts across all sources
4. Apply consolidation: any archetype with <50 training samples after merging is consolidated into its nearest parent archetype
5. Produce combined train/val/test splits using per-replay splitting (no replay leaks across splits)

### Consolidation Map (applied only when <50 samples)

| Archetype | Consolidates into | Rationale |
|-----------|-------------------|-----------|
| TECH_RUSH | RUSH | Both are early aggressive tech commitments |
| HYDRA_PUSH | MACRO_ECONOMY | Late-game composition, macro-oriented opener |
| MUTA_HARASS | (keep if ≥50) | Distinct enough to warrant its own class if data supports it |

Consolidation is data-driven — these mappings are defaults, applied only after all sources are ingested and per-class counts are known. If targeted Spawning Tool harvesting brings MUTA_HARASS above 50, it stays as its own class.

## Training

No architecture changes. The existing CNN-Attention model with focal loss and class weighting handles the training:

- Same `StrategyClassifier` model (`model.py`)
- Same `focal_gamma=2.0`, `compute_class_weights` for remaining imbalance after consolidation
- Same temperature calibration on validation set
- New data source flag: `python3 -m evaluation.strategy_classifier.run_pipeline --data combined`
- Same ONNX export with baked temperature

## Validation Criteria

From issue #76, validated on real test data (not synthetic):

- [ ] Top-1 accuracy ≥65% at minute 4
- [ ] Top-3 accuracy ≥85% at minute 4
- [ ] Top-1 ≥50% at minute 2 for critical archetypes (rush, cannon rush, proxy)
- [ ] Model file <10MB
- [ ] Inference <10ms on CPU

## Artifact Deployment

Retrained ONNX models replace synthetic-trained artifacts:
- `evaluation/strategy_classifier/output/` — ONNX files + manifests
- `inference-runtime/src/test/resources/models/strategy/` — test resource copies

Training data and models are published to GitHub Releases (#209) for persistence.

## Archetype Definitions (unchanged)

| Matchup | Archetypes |
|---------|-----------|
| vs_terran | RUSH, PROXY, BANSHEE_HARASS, AIR_SUPERIORITY, MECH_PUSH, BIO_TIMING, MACRO_ECONOMY, TECH_RUSH |
| vs_zerg | RUSH, ROACH_RUSH, LING_BANE, MUTA_HARASS, HYDRA_PUSH, MACRO_ECONOMY, TECH_RUSH |
| vs_protoss | RUSH, PROXY, CANNON_RUSH, DT_RUSH, BLINK_STALKER, COLOSSUS_PUSH, AIR_SUPERIORITY, MACRO_ECONOMY, TECH_RUSH |

Post-consolidation, some classes may be merged. The final class list per matchup is determined after ingestion and reported in the model manifest.

## Decision Record

- D1: Unified labelling — one rule-based labeller for all sources via per-source adapters
- D2: 50-sample minimum per archetype — below 50, consolidate into nearest parent
- D3: Sequential ingest, train once — all sources merged before training, no incremental runs

## References

- `evaluation/strategy_classifier/run_pipeline.py` — existing training pipeline entrypoint
- `evaluation/strategy_classifier/prepare_real_data.py` — existing SC2EGSet adapter
- `evaluation/strategy_classifier/download_msc.py` — existing MSC download script
- `evaluation/strategy_classifier/labelling/rules.py` — rule-based labeller (building timing heuristics)
- `evaluation/strategy_classifier/config.py` — archetype definitions, hyperparams
- `evaluation/strategy_classifier/output/model_manifest.json` — current synthetic-trained manifest
- [SC2EGSet on Zenodo](https://zenodo.org/records/14963484) — esports replay dataset
- [SC2EGSet paper (Nature Scientific Data)](https://www.nature.com/articles/s41597-023-02510-7)
- [spawningtool PyPI v3.0.0](https://pypi.org/project/spawningtool/) — SC2 replay parser
- [Spawning Tool replay packs](https://lotv.spawningtool.com/replaypacks/) — targeted strategy harvesting
- casehubio/neocortex#209 — training data persistence on GitHub Releases
- casehubio/quarkmind#208 — parent epic (ONNX strategy classifier)
- casehubio/quarkmind#212 — blocked (three-tier cascade integration)
- casehubio/quarkmind#213 — blocked (IEM10 validation benchmarking)
