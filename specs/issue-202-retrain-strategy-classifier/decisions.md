## D1: Labelling strategy across data sources

**Choice:** Unified labelling — thin adapter per source normalizing to common build-order format (building name + minute), then same rule-based labeller on all sources
**Alternatives:**
- Per-source labelling — use Spawning Tool's own labels where available, rule-based for SC2EGSet/MSC — risk of label disagreement between sources
**Rationale:** Consistent labels across datasets are essential for training a single model. Pre-existing labels from different sources use different taxonomies and thresholds. A single labelling pipeline ensures every sample is classified by the same criteria.
**Trade-offs:** Discards Spawning Tool's pre-existing build labels, which may be more nuanced for their data. Requires writing adapters per source format.
**Sources:** labelling/rules.py (existing rule-based labeller), spawningtool PyPI v3.0.0, prepare_real_data.py (SC2EGSet adapter)
**Exploration:** quick
**Status:** captured

## D2: Minimum samples per archetype

**Choice:** 50 training samples minimum per archetype. Below 50, consolidate into nearest parent archetype.
**Alternatives:**
- No minimum — keep all archetypes regardless of sample count, accept low accuracy on tail classes
- Higher threshold (100+) — more conservative, loses granularity earlier
**Rationale:** Below 50 samples with focal loss and class weighting, the CNN memorizes rather than generalizes. 50 is the practical floor for learning discriminative features with the existing architecture.
**Trade-offs:** May lose some archetype granularity (e.g., TECH_RUSH → RUSH) depending on data yield. Consolidation decisions are data-driven — made after ingesting all sources, not predetermined.
**Sources:** SC2EGSet vs_zerg class distribution (TECH_RUSH: 4 samples, HYDRA_PUSH: 28, MUTA_HARASS: 33), training pipeline config (focal_gamma=2.0, compute_class_weights)
**Exploration:** quick
**Status:** captured

## D3: Data ingestion strategy

**Choice:** Sequential ingest, then train once — download MSC, harvest Spawning Tool replay packs, process all three sources through the unified labeller, merge into a single combined dataset per matchup, then train once.
**Alternatives:**
- Incremental training — train on SC2EGSet first, evaluate, add MSC/Spawning Tool and retrain — gives per-source contribution data but costs extra iteration cycles
**Rationale:** Get the best model as fast as possible. Per-source contribution analysis is nice-to-have but not worth the extra training cycles. Can always retrain on a subset later.
**Trade-offs:** No baseline comparison between SC2EGSet-only vs combined. Acceptable — the goal is accuracy on real data, not source attribution.
**Depends on:** D1 (unified labelling)
**Sources:** run_pipeline.py, prepare_real_data.py, download_msc.py
**Exploration:** quick
**Status:** captured
