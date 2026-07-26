# Handoff — 2026-07-27

## What Changed

Branch `issue-181-embedding-retrieval-improvements` closed. Landed as `65ffff1` on main (fork). Pushed to origin. Closes #181, #182, #183.

**Delivered:** Embedding pipeline cleanup, ColBERT auto-calibration, MinHash query clustering.

- `embed(Map)` removed from `MultiModalEmbedder` — batch-composition hazard that produced different embeddings via individual `embed(String)` calls (batch=1) vs `embedBatch` due to padding/attention mask differences.
- `HybridCaseRetriever` migrated to `embedSeparate()` — the canonical per-leg separation API. Replaces the conditional `embed()`/`embedBatch()` pattern. Single-embedding API simplifies CC and RRF fusion paths.
- `ColBertRelevanceEvaluator.calibrate(List<Double> sampleScores)` — factory that derives CORRECT/INCORRECT thresholds from score distributions at P75/P25 (default) or custom percentiles. Decouples thresholds from hardcoded values.
- `MinHashIndex` + LSH banding for `RetrievalAnalyzer.queryClusters()` — replaces O(n²) brute-force pairwise Jaccard with LSH candidate generation + exact verification for query sets > 50. Overflow-safe hashing, record-based deduplication.
- Root-cause analysis for #181 regression: tokenizer `modelMaxLength` fix (e3fb82f) + CE score promotion (c6f2d77) shifted embedding/scoring distributions. Both are correct changes; the -2.2pp regression is an expected consequence of improved behavior, not a bug.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| engine#780 | Wire trust data from routing context into CbrCase | S | Med | Engine work |
| engine#781 | AgentTrustProvider impl: bridge TrustScoreSource | S | Low | Engine work |
| #117 | Per-leg embedding separation — remaining open work | S | Med | embedSeparate migration complete; #117 tracks the full feature |

## Garden Entries

(none this session)
