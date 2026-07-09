# Handoff — 2026-07-09

## What Changed

Closed #124 (ScoreFusion consolidation), #123 (BM25 leg for CBR), #122 (SPLADE leg for CBR). New `fusion-api` Tier 1 module extracts `ScoreFusion`, unified `FusionStrategy` enum, and `CamelCaseExpander` — shared by RAG and CBR. RAG callers migrated; `RrfFusion`, `ConvexCombinationFusion`, rag-api `FusionStrategy`, and `CbrFusionStrategy` deleted. CBR gains optional SPLADE sparse embedding and BM25 server-side inference as retrieval legs. Dynamic 2-4 leg hybrid fusion with CC weight renormalization. Collection schema evolution (delete-and-recreate, guarded by `allowSparseVectorMigration`). Three-phase reconciliation adds vector enrichment for backfilling SPLADE/BM25 vectors. Final review: 2 rounds, 15 issues, 6 verified, $8.62. Landed as `075d2ec` on both `origin/main` and `upstream/main`.

## Garden Entries

- GE-20260709-063f66 — Qdrant updateCollection cannot add new sparse vectors to existing collections
- GE-20260709-94d8d3 — Qdrant scroll returns VectorOutput not Vector — use updateVectorsAsync
- GE-20260709-137b8e — peer Tier 1 utility module convention (from previous session)

## Immediate Next Step

Pick next work item from What's Next. Track A is complete (#124→#123→#122). Track B (#89 structured case fields) and Track C (#84 outcome learning) are both unblocked.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency
- casehubio/parent#358 — update `docs/repos/casehub-neocortex.md` for rag-crossencoder rename · XS · Low

## What's Next — CBR App Enablement Critical Path

Track A complete. Remaining tracks:

| # | Description | Scale | Complexity | Track | Notes |
|---|-------------|-------|------------|-------|-------|
| #89 | Structured case fields (nested objects, list containment) | M | Med | B | Unblocked — track B head |
| #91 | Temporal case representation (time-series segments) | M | High | B | Blocked by #89 |
| #92 | Sequence similarity (DTW, edit distance) | M | High | B | Blocked by #91 |
| #84 | Outcome learning + retrieval traceability | L | High | C | Unblocked — track C head |
| #85 | Plan adaptation SPI | M | High | C | Blocked by #84 |

## What's Next — Other

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
| #120 | Expansion drift metrics with auto-fallback | M | Med | |

## Key References

- Spec: `docs/specs/2026-07-08-cbr-fusion-consolidation-design.md`
- Review: `~/adr/casehub-neocortex/fusion-consolidation-final-20260709-162633/`
- Blog: `blog/2026-07-09-mdp01-three-implementations-of-the-same-algorithm.md`, `blog/2026-07-09-mdp02-the-api-that-wouldnt-evolve.md`
