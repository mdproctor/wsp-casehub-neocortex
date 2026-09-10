# HANDOFF — casehub-neocortex

## Last Session

Completed neocortex side of #304 (knowledge garden platform extraction) — 10 of 13 tasks across 5 batches. Brainstorming through implementation in one session.

**What was built:**
- 4 new SPIs in rag-api: `PostRetrievalScorer`, `ProvenanceTracker`, `FederationStrategy`, `DocumentQueryAugmenter` + supporting records (`ScoringContext`, `AdaptiveSearchConfig`, `AdaptiveFilter`, `FederationQuery`, `FederatedResult`, `FederationTarget`, `ProvenanceRecord`, `ProvenanceStats`)
- 2 new modules: `rag-scoring` (TemporalDecayScorer, VersionScorer, AdaptiveSearchWrapper), `rag-query-augmentation` (AgentQueryAugmenter, QueryAugmentingMetadataExtractor)
- `CollectionCompatibility` utility in rag module (generic migration checks)
- CBR rename: PlanCbrCase → ResolvedCase, TextualCbrCase → ResolutionGuide, PlanTrace → ResolutionStep (47 files, 305 refs)
- `CbrOutcome.retrievalId` for retrieval-to-outcome correlation

**Key design decisions:** SPI-first extraction — SPIs in rag-api, impls stay in engine until second consumer validates. Federation is routing not decoration (single `federate()` method). Two feedback axes stay separate (RetrievalTracker for relevance, CbrCaseMemoryStore for outcome). CBR_TYPE constants unchanged to avoid data migration. Scored post-merge via `AdaptiveFilter` (not decorator — needs full result set).

**Bugs found and fixed:** Slot creation inherits stale lifecycle files from workspace clone — fixed in `soredium/work-slot/slot_lifecycle.py`. IntelliJ rename fails when wksp symlink present + Maven unlinked — workaround documented in work-slot SKILL.md, garden entry GE-20260911-42a250.

## Deferred

3 engine integration tasks (need neocortex pushed first):
- Engine uses rag-scoring (M/Med) — delete TemporalDecayScorer/VersionScorer
- Engine implements ProvenanceTracker + FederationStrategy SPIs (M/Med)
- Engine CBR rename + MCP verification (S/Low)

## References

- Spec: `wksp/specs/issue-304-neocortex-garden-platform/2026-09-10-neocortex-garden-platform-design.md`
- Decisions: `wksp/specs/issue-304-neocortex-garden-platform/decisions.md` (12 decisions, reviewed)
- Plan: `wksp/plans/2026-09-10-neocortex-garden-platform.md`
- Cross-ref: Hortora/engine#90
- Garden: GE-20260911-42a250 (IntelliJ rename gotcha)
- Filed: casehubio/neocortex#305 (feedback context enrichment, deferred)
