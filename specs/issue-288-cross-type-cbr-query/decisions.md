## D1: Sealed CaseTypeScope on CbrQuery

**Choice:** Replace `String caseType` with a sealed `CaseTypeScope` interface — `Specific(String caseType)` for single-type queries, `AllInDomain()` for cross-type queries. Remove `Objects.requireNonNull(caseType)` from the compact constructor; add `Objects.requireNonNull(caseTypeScope)`.
**Alternatives:**
- Nullable `String caseType` (null means "all types") — null semantics are fragile; `ConcurrentHashMap.get(null)` throws NPE in TrendEnrichment (expandedSchemas), QdrantStore (schemas), and InMemoryStore (schemas). Callers must remember null means "cross-type" not "unset". The decorator chain does NOT degrade gracefully — it crashes.
- Separate `retrieveAcrossTypes()` SPI method — creates parallel code paths that must stay in sync across N decorators. The sealed type gives explicit handling in a single method without dual-path maintenance.
- Wildcard string sentinel (e.g. `"*"`) — stringly-typed, can collide with actual caseType names, no compiler enforcement
**Rationale:** CaseTypeScope forces every code path to explicitly handle both cases via pattern matching. A missing switch case is a compile error (exhaustive switch expressions), not a runtime NPE. The original nullable approach was verified against the codebase and found to have NPE sites in three ConcurrentHashMap.get() calls and a functional failure in InMemoryCbrCaseMemoryStore where `.equals(null)` silently filters all candidates — proving that null semantics are unsafe even for authors who understand the intended semantics.
**Trade-offs:** One new sealed interface with two variants. All code paths that currently use `query.caseType()` must change to pattern matching on CaseTypeScope. This is a larger migration than nullable, but the breakage is the point — it forces every caller to be explicit. Factory method naming (`CbrQuery.crossType(...)` vs `CbrQuery.of(...)`) makes intent clear at construction.
**Sources:** CbrQuery.java:32 (requireNonNull), TrendEnrichmentCbrCaseMemoryStore.java:56 (ConcurrentHashMap.get NPE), QdrantCbrCaseMemoryStore.java:210 (ConcurrentHashMap.get NPE), InMemoryCbrCaseMemoryStore.java:92 (ConcurrentHashMap.get NPE), InMemoryCbrCaseMemoryStore.java:115 (.equals(null) → false → all candidates filtered)
**Exploration:** quick → revised via adversarial review R1-02, R1-03
**Status:** revised — was nullable caseType; now sealed CaseTypeScope after reviewer demonstrated NPE sites and proposed the sealed alternative

## D2: Add caseType field to ScoredCbrCase

**Choice:** Add `String caseType` after `caseId` in the record. Always populated by stores. Enforce with `Objects.requireNonNull(caseType, "caseType required")` in the compact constructor.
**Alternatives:**
- Add `caseType()` to CbrCase interface — mixes storage metadata with case data; CbrCase is problem/solution/outcome, caseType is storage categorization
- Wrapper `TypedScoredCbrCase` — changes return type for cross-type queries only, awkward API split
**Rationale:** ScoredCbrCase is already the "result with metadata" record (caseId, score, storedAt, scope, trustTrajectory). caseType fits this pattern. Self-describing results eliminate query-result correlation. The `requireNonNull` enforcement prevents silent null propagation — unlike `caseId` which predates this discipline and is nullable in convenience constructors, `caseType` is always known at store time. Convenience constructors that don't accept `caseType` should not be used for cross-type results.
**Trade-offs:** Adding a record field changes the canonical constructor — all call sites need updating. Adjacent `String caseId, String caseType` fields create positional swap risk that the compiler cannot catch. Mitigated by: (1) omitting `caseType` IS caught (double → String type mismatch), (2) with* methods are mechanical and IDE-assisted, (3) contract test coverage of all with* methods.
**Sources:** ScoredCbrCase.java:7-8 (current record fields), CbrCase.java:8 (cbrType is paradigm discriminator, not business type)
**Exploration:** quick
**Status:** captured — refined with requireNonNull enforcement per R1-07

## D3: Allow filters with null caseType — per-candidate schema lookup

**Choice:** Allow filters on cross-type queries. Validate/match per-candidate using stored caseType's schema. Log a warning when candidates are skipped due to missing schema for HasMatch filters.
**Alternatives:**
- Reject filters when caseType is null — simpler but artificially restricts queries on shared fields (e.g., severity=HIGH across types)
- Skip validation entirely, best-effort matching — loses HasMatch struct vs struct-list disambiguation
**Rationale:** Cross-type query = N single-type queries merged. Each candidate has a known caseType → schema. matchesFilters already excludes candidates missing the filtered field (storedValue == null → return false). Only HasMatch needs schema for ObjectList vs NestedObject disambiguation — skip candidates whose schema is null when HasMatch is present, with a warning log to make the data loss visible. This design applies primarily to InMemoryCbrCaseMemoryStore where all cases share a single list; with D4's fan-out architecture, each Qdrant sub-query targets a single caseType with its schema already available, making per-candidate schema lookup unnecessary at the Qdrant layer.
**Trade-offs:** Lose upfront "did you misspell the field name" validation for cross-type queries. Development-time guard only, not a correctness concern. HasMatch with missing schema produces a warning log per skipped candidate — operators can identify under-registered schemas.
**Sources:** InMemoryCbrCaseMemoryStore.java:482 (null storedValue → false), :512-519 (HasMatch needs field type)
**Exploration:** deep-analysis
**Status:** captured — clarified D4 dependency and added warning log per R1-09, R1-10

## D4: Qdrant multi-collection parallel fan-out via listCollections

**Choice:** `client.listCollectionsAsync()` → filter by prefix → query all matching collections in parallel via `Futures.allAsList()` → merge by score → take topK
**Alternatives:**
- Use `schemas` map to find known caseTypes — misses types stored without schema registration in the current JVM session
- Use `knownCollections` set — only populated in current JVM session, misses previous sessions
- Serial fan-out — adds O(N) network latency; at N=10 collections with ~5-10ms per RPC, that's 50-100ms of avoidable overhead on the interactive path (case definition selection, engine#1055)
- Single-collection architecture (caseType as payload field) — eliminates fan-out but mixes types in one HNSW graph, degrading nearest-neighbor quality; loses per-type isolation for schema evolution and index tuning
**Rationale:** listCollections is authoritative (metadata query, no data scan) and finds all types regardless of JVM session state. Parallel execution via Guava's `Futures.allAsList()` reduces fan-out latency from O(N) to O(1) — the slowest single query. The Qdrant client already brings Guava as a transitive dependency; the implementation pattern mirrors the existing `awaitFuture()` utility. Multi-collection architecture preserves per-type isolation: independent HNSW graphs, per-type schema evolution, per-type index tuning, per-type retention policies.
**Trade-offs:** N+1 RPCs (1 list + N queries), but parallel execution caps wall-clock to the slowest single query. Partial failure handling needed: if one collection query fails, the cross-type query should return results from successful collections with a warning, not fail entirely.
**Sources:** CbrCollectionManager.java:49-51 (collectionName prefix scheme), :31 (knownCollections only session-scoped), QdrantCbrCaseMemoryStore.java:582,599,647,693,730,960,1035,1058,1090 (schemas.keySet() used in 9 methods — same session-scoped limitation as retrieval)
**Exploration:** deep-analysis → revised via adversarial review R1-12
**Status:** revised — was serial fan-out; now parallel via Futures.allAsList() after reviewer demonstrated latency impact on interactive path

## D5: Cross-type score merging strategy

**Choice:** Raw score merge — query each collection for topK, merge all candidates by score, take the overall topK. No cross-type score normalization.
**Alternatives:**
- Per-type-top-K (retrieve topK from each type, return all without cross-type ranking) — ensures type diversity but inflates result count proportional to number of types; changes the semantic from "best match" to "representative sample"
- Percentile rank normalization (rank within each type, then merge by rank) — eliminates schema-dependent score dynamics but destroys valid signals from well-designed schemas
- Score normalization (min-max or z-score per type before merge) — requires sufficient results per type for meaningful statistics; adds complexity for marginal benefit at expected cardinalities
**Rationale:** CbrSimilarityScorer produces weighted averages in [0,1] — the same semantic on the same scale regardless of schema size. The score represents "how well does this case match the query on the features this type considers important." Schema design encodes domain knowledge about which features matter; raw score comparison preserves that signal. The fan-out architecture (D4) inherently caps per-type results to topK, preventing data-volume dominance — a type with 10,000 stored cases and a type with 100 both contribute at most topK candidates. For case definition selection (engine#1055), raw score merge answers the right question: "which type's historical cases are most similar to this situation?"
**Trade-offs:** Different schemas with different feature counts produce different score distributions — a 3-feature schema has coarser granularity than a 15-feature schema. This is a feature of the weighted-average design: fewer features means each feature contributes more, which is correct when those features ARE the important discriminators. If cross-type score dynamics prove problematic in practice, per-type-top-K can be introduced as a configurable retrieval parameter on CbrQuery (e.g., `ResultMergeStrategy.PER_TYPE_TOP_K`) without architectural change.
**Sources:** CbrSimilarityScorer.java:59-87 (scoreDetailed weighted average), engine#1055 (case definition selection use case)
**Exploration:** implicit → surfaced by adversarial review R1-16, R1-17
**Status:** captured
