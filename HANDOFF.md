# HANDOFF — casehub-neocortex

## Last Session

**From casehub-aml #10 session (2026-09-20):**
- Committed `9390a1a2` on branch `issue-359-event-recorder-dedup`: added protected no-args constructors to `EventRecorderCore` and `EngagementRecorderCore` for Quarkus 3.39 CDI proxy compatibility. Filed as neocortex#373.
- Needs: cherry-pick to main or merge the branch.

**Previous session:**
Two GA audit issues (#357, #358) — design, implementation, and close for both in a single session.

### What Happened

**#357 — Consolidation phase scaling (S/Med)**
- First-principles analysis revealed merge detection bottleneck was per-pair SQL amplification, not the O(n²) name comparison
- Prefix bucketing + bulk neighbor pre-loading for merge detection — O(n² + k×SQL) → O(n×SQL + Σbᵢ²)
- Sampled Brandes for approximate betweenness centrality — new `approximateBetweennessCentrality(store, subgraphId, tenantId, k)` method with deterministic seed (k=100)
- `nodesWithoutEdges` default SPI method on MindMapStore — SqliteMindMapStore overrides with single NOT IN query, InMemoryMindMapStore with set difference
- All three node-count safety guards removed (500-node merge, 2000-node centrality)
- Contributor guide updated with new algorithm descriptions

**#358 — SQLite DataSource factory (S/Low)**
- New `sqlite-support` module with `SqliteDataSourceFactory` — static `create()` overloads + `migrate()`
- 5 SQLite stores migrated: SqliteMindMapStore, SqliteMemoryStore, SqliteRetrievalTracker, SqliteCbrRetrievalTracker, SqliteSnapshotStore
- 37 additions, 202 deletions — 165 lines of duplication eliminated
- CLAUDE.md updated with new module

### Issues Closed
- #357 (consolidation phase scaling)
- #358 (SQLite DataSource factory)

## Next

Continue #355 GA audit — #359 (event recorder dedup + DelegatingCaseMemoryStore) is next in priority order.

Remaining in priority order:
- #359 — event recorder dedup + DelegatingCaseMemoryStore (S/Low)
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
