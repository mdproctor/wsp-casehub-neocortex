# Handoff — 2026-08-14 (main)

## What Changed

Closed #206 — default retention config domain/caseTypes. Added `@WithDefault("")` to `domain()` and `caseTypes()` in `CbrRetentionConfig`, `TrustRetentionConfig`, `MemoryRetentionConfig`. Apps that don't use retention need zero config. Runtime validation when `enabled=true`. 5 new tests. Garden entry GE-20260814-5920f5 captured (@ConfigMapping startup validation gotcha).

## Completed Epics

- #196 — agent memory patterns: CLOSED (all 3 batches)
- #197 — retrieval model quality: CLOSED (batches 1-3 done, #39 deferred)

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ | M | Low | Deferred — trigger: second consumer materialises |
| #65 | epic: memory-memori adapter | XL | Med | Blocked — Memori REST API not shipped |
| #16 | quarkus-langchain4j composition annotations | M | Low | Blocked upstream (quarkiverse #2572) |
| #12 | Migrate Qdrant hybrid search | M | Med | Blocked upstream (LangChain4j #4994) |
| #39 | Dedicated RelevanceEvaluator model | M | High | Deferred — trigger: consumer shows insufficient accuracy |
| #202 | Retrain strategy classifier on real replay data | M | Med | Status unknown |

All remaining issues are blocked or deferred. Repo is in a holding pattern.

## Cross-Repo Updates (2026-08-10, from hortora/engine session)

- **Issue filed:** #205 — `CorpusIngestionService.chunkDocument()` drops `listMetadata` from `ExtractionResult`. Uses 3-arg `ChunkInput` constructor; needs 4-arg to pass list metadata (tags, see_also) through to Qdrant payload.
- **Slot created:** casehub slot 108, branch `issue-205-listmetadata-passthrough`
- **Blocks:** Hortora/engine#87 (tags payload enrichment)
