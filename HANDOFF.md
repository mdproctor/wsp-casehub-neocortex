# Handoff — 2026-07-09

## What Changed

Branch `issue-124-cbr-fusion-consolidation` covers #124, #123, #122 (CBR Track A). Consolidation phase (#124) is complete — 4 commits on the project branch:
1. `34078bd` — new `fusion-api` Tier 1 module with `ScoreFusion`, `FusionStrategy` enum
2. `e5dc4e2` — `CbrFusionStrategy` → `FusionStrategy` (atomic SPI change, DBSF guard)
3. `2d446c8` — RAG callers migrated, `RrfFusion` + `ConvexCombinationFusion` + rag-api `FusionStrategy` deleted, unused `rag-api` dep removed from `memory-qdrant`
4. `7fef4db` — `CamelCaseExpander` moved to `fusion-api` (public visibility)

Design spec reviewed (4 rounds, 17 issues, $16.57): `docs/specs/2026-07-08-cbr-fusion-consolidation-design.md`. Implementation plan: `plans/2026-07-09-cbr-fusion-consolidation.md` — 10 tasks, 4 complete, 6 remaining.

## Immediate Next Step

Run `/work` to resume branch `issue-124-cbr-fusion-consolidation`. Continue with Task 5 in the plan (`plans/2026-07-09-cbr-fusion-consolidation.md`): add `QdrantCbrConfig` properties for SPLADE, BM25, CC weights. Tasks 5-10 implement SPLADE (#122) and BM25 (#123) legs for CBR.

## Remaining Tasks (from plan)

| Task | Description | Status |
|------|-------------|--------|
| 5 | QdrantCbrConfig for SPLADE + BM25 + CC weights | pending |
| 6 | Collection schema evolution — add SPLADE/BM25 named vectors to existing collections | pending |
| 7 | SPLADE + BM25 ingestion (CbrPointBuilder + store) — `inference-splade` dep, optional `SparseEmbedder` injection | pending |
| 8 | SPLADE + BM25 retrieval legs in `retrieveHybrid()` — dynamic 2-4 leg fusion, CC weight renormalization | pending |
| 9 | Reconciliation vector enrichment phase — three-phase model, backfill SPLADE/BM25 vectors | pending |
| 10 | Update CLAUDE.md + ARC42STORIES.MD — add fusion-api module | pending |

## Key Design Decisions (read spec for full detail)

- **CC weight renormalization:** semantic sub-weights renormalize among *active* semantic legs before applying `vectorWeight` split — preserves the feature/semantic contract
- **DBSF guard:** `switch` in `retrieveHybrid()` throws `UnsupportedOperationException` for DBSF
- **Collection schema evolution:** `ensureCollection()` adds missing named vectors to existing collections via Qdrant `updateCollection` API
- **Three-phase reconciliation:** orphan cleanup → reindex → vector enrichment (new phase for SPLADE/BM25 backfill)
- **`SparseEmbedder` injection:** optional CDI via `Instance<SparseEmbedder>` in `QdrantCbrCaseMemoryStore`

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency
- casehubio/parent#358 — update `docs/repos/casehub-neocortex.md` for rag-crossencoder rename · XS · Low

## What's Next — CBR App Enablement Critical Path

*Unchanged — retrieve with: `git show HEAD~1:HANDOFF.md`*

## What's Next — Other

*Unchanged — retrieve with: `git show HEAD~1:HANDOFF.md`*

## Key References

- Spec: `docs/specs/2026-07-08-cbr-fusion-consolidation-design.md`
- Plan: `plans/2026-07-09-cbr-fusion-consolidation.md` (workspace)
- Review workspace: `~/adr/casehub-neocortex/fusion-consolidation-20260709-095355/`
- Garden: GE-20260709-137b8e (peer Tier 1 utility module convention)
- Blog: `blog/2026-07-09-mdp01-three-implementations-of-the-same-algorithm.md`
