*Updated: engine#780, engine#781 closed — removed from backlog.*

# Handoff — 2026-07-28

## What Changed

Two branches landed on main. Both pushed to origin and upstream.

### Branch 1: `issue-181-embedding-retrieval-improvements` (landed as `65ffff1`)

Closes #181, #182, #183. Also closed #117 (embedSeparate migration completed it), #93/#81/#55 (CBR roadmap cascade — all phases delivered).

- `embed(Map)` removed from `MultiModalEmbedder` — batch-composition hazard
- `HybridCaseRetriever` migrated to `embedSeparate()` for per-leg separation
- `ColBertRelevanceEvaluator.calibrate()` — percentile-based threshold derivation from score distributions
- `MinHashIndex` + LSH banding for `RetrievalAnalyzer.queryClusters()` — O(n*k) for large query sets
- Root cause of #181 -2.2pp regression: tokenizer `modelMaxLength` fix + CE score promotion (both correct changes)

### Branch 2: `issue-77-tensor-inference-spi` (landed as `3836855`)

Closes #77, #144.

- `InferenceInput` refactored to sealed interface: `Text` (existing tokenization) + `Tensor` (raw float[][] bypassing tokenizer)
- `OnnxInferenceModel` dispatches on input type. `ModelConfig.tokenizerPath` nullable for tensor-only models
- ARC42STORIES §5 gains memory modules (L12-L15). §9 gains Chapter C12: CBR decorator chain + outcome learning

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Trigger: second consumer materialises |
| #129 | Add CBR memory modules to ARC42STORIES §5 | M | Low | Partially done — L12-L15 added, full detail remains |
| #76 | Train 1D-CNN strategy classifier + ONNX export | M | High | Unblocked by #77 (tensor input SPI) |
