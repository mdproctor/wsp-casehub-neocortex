# Handoff — 2026-07-08

## What Changed

Closed #110 (retrieval tracking data retention) and #121 (cross-encoder reranking). `purgeOlderThan(Instant)` added to `RetrievalTracker` and `ReactiveRetrievalTracker` SPIs with cascade DELETE in SQLite, `RetentionScheduler` (90-day default, `ScheduledExecutorService` daemon thread). `RerankingCaseRetriever` `@Decorator @Priority(75)` with blocking + reactive variants, overfetch via `max(limit, rerankPoolSize)`. `rag-crag/` renamed to `rag-crossencoder/` — module boundary aligned with dependency boundary (`inference-tasks`). Score propagation from CRAG to reranker via chunk metadata eliminates double cross-encoder inference. Landed as `233cc86` on both `origin/main` and `upstream/main`. Design review (2 rounds, 14 issues, all resolved). Garden entry GE-20260708-d53278 (score propagation technique). casehubio/parent#358 filed for PLATFORM.md deep-dive update.

## Immediate Next Step

Pick next work item from What's Next — #109 and #120 are unblocked.

## Cross-Module

**We're blocking:**
- `Hortora/engine` — can now adopt both reranking (`casehub.rag.reranking.enabled=true`) and HyDE with confidence. Their `0.2-SNAPSHOT` dependency picks up all changes.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency
- casehubio/parent#358 — update `docs/repos/casehub-neocortex.md` for rag-crossencoder rename · XS · Low

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked (#105 closed) |
| #120 | Expansion drift metrics with auto-fallback | M | Med | Builds on per-leg embedding + score propagation |

## Key References

- Spec: `docs/specs/2026-07-07-retention-and-reranking-design.md`
- Garden: `GE-20260708-d53278` (score propagation via chunk metadata)
