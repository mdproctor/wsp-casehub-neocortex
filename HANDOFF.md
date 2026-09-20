# HANDOFF — casehub-neocortex

## Last Session

Two issues closed (#359, #372) in a single branch, plus a cross-repo CDI fix (#373 from casehub-aml).

### What Happened

**#359 — Event recorder dedup + DelegatingCaseMemoryStore (S/Low)**
- Extracted `EventRecorderCore<E, R, F, S>` abstract base in `memory-core` — shared `record()`/`recordAll()` batch logic with type-safe hooks (toInput, toRecorded, toFailure, toResult, emptyResult)
- `ExperienceRecorderCore` and `EngagementRecorderCore` reduced from ~60 lines each to ~10 lines
- Created `DelegatingCaseMemoryStore` in `memory-api` — forwarding base paralleling `DelegatingCbrCaseMemoryStore`
- `ErasureNotificationCaseMemoryStore` simplified to extend it — 10 manual forwarding methods removed
- `memory-core` module documented in CLAUDE.md (was missing)

**#372 — CaseContextRetriever (S/Low)**
- New `CaseContextRetriever` in `rag-api` — multi-corpus retrieval with per-corpus error isolation, sourceDocumentId dedup (keeps highest score), score-sorted truncation
- Improved over issue proposal: returns `List<RetrievedChunk>` (typed) not `List<Map<String, Object>>` (loose); static `toMap()` for serialization; placed in rag-api (not rag-core) to avoid heavy transitive deps
- 11 unit tests
- Code review fix: `toMap()` metadata ordering to prevent key collision

**#373 — CDI proxy no-arg constructors (cross-repo from casehub-aml)**
- Protected no-arg constructors added to `EventRecorderCore` and `EngagementRecorderCore` for Quarkus CDI proxy compatibility

### Documentation Updated
- CLAUDE.md: memory-core module, DelegatingCaseMemoryStore, CaseContextRetriever
- ARC42STORIES §5: memory-core container, CaseContextRetriever in rag-api, DelegatingCaseMemoryStore in memory-api
- Consumer guide: CaseContextRetriever in rag-api row, DelegatingCaseMemoryStore in memory-api row
- Contributor guide: memory-core module row, CaseContextRetriever, DelegatingCaseMemoryStore, ErasureNotificationCaseMemoryStore

### Issues Closed
- #359 (event recorder dedup + DelegatingCaseMemoryStore)
- #372 (CaseContextRetriever)

## Next

Continue #355 GA audit. Remaining in priority order:
- #360 — extract cbr-algorithms from memory-api (M/Med)
- #361 — resolve mindmap→cognitive-index upward dependency (S/High)
- #362 — audit orphaned SPIs (S/Low)
- #363 — API consistency (M/Med)
- #364 — consumer-facing SPI Javadoc (M/Low)
- #365 — config consistency (M/Med)
- #366 — config reference documentation (S/Low)
- #367 — SPI completeness (L/Med)

## Cross-Module

- Engine AML tests should pass after rebuilding against latest neocortex
- casehubio/soc#57 can now refactor to use `CaseContextRetriever` (#372 landed)
