# Design Journal — issue-124-cbr-fusion-consolidation

## 2026-07-09 — Fusion consolidation: module extraction + RAG migration

### §5 Building Block View — fusion-api module

The root design question was where to place `ScoreFusion` so both `memory-api` and `rag-api` could reach it without creating a cross-domain dependency. Three peer Tier 1 modules (`memory-api`, `rag-api`, `inference-api`) had zero cross-dependencies — a deliberate invariant. ScoreFusion was in `memory-api` by accident of history (created during CBR Phase 3), not by design.

Resolution: new `fusion-api` Tier 1 module, zero first-party deps. Contains `ScoreFusion` (RRF + CC algorithms), unified `FusionStrategy` enum (replaces both `CbrFusionStrategy` and rag-api's `FusionStrategy`), and `CamelCaseExpander` (BM25 token pre-processing, shared by RAG and CBR).

Key finding during migration: the grade-merging behaviour in `RrfFusion` and `ConvexCombinationFusion` was dead code — all chunks entering fusion are `UNGRADED` (grading happens downstream in the CRAG decorator). This confirmed `ScoreFusion`'s `putIfAbsent` approach is functionally equivalent.

Design review (4 rounds, 17 issues, $16.57) surfaced critical additions: DBSF guard in CBR (`UnsupportedOperationException`), CC weight renormalization that preserves `vectorWeight` feature/semantic split, three-phase reconciliation model with vector enrichment, and collection schema evolution for adding SPLADE/BM25 named vectors to existing collections.

### §10 Architectural Decisions — unused rag-api dependency

Discovered `memory-qdrant` had an unused dependency on `rag-api` — zero imports from `io.casehub.neocortex.rag` anywhere in memory-qdrant source. Removed during consolidation. Origin unclear — possibly added when RrfFusion was considered for use in CBR before ScoreFusion was created.
