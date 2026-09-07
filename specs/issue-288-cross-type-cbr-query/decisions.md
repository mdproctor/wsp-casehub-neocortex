## D1: Nullable caseType on CbrQuery

**Choice:** Remove `Objects.requireNonNull(caseType)` — null means "all types in domain"
**Alternatives:**
- Separate `retrieveAcrossTypes()` SPI method — avoids null semantics but forces N decorator updates and creates maintenance burden
- Wildcard string sentinel (e.g. `"*"`) — stringly-typed, can collide with actual caseType names
**Rationale:** The decorator chain already degrades gracefully with null caseType (TrendEnrichment skips enrichment, all others are caseType-independent). No SPI signature change needed.
**Trade-offs:** Null caseType is a semantic overload — callers must know null means "cross-type", not "unset". Mitigated by explicit factory method naming.
**Sources:** CbrQuery.java:32 (requireNonNull), TrendEnrichmentCbrCaseMemoryStore.java:56 (schema lookup)
**Exploration:** quick
**Status:** captured

## D2: Add caseType field to ScoredCbrCase

**Choice:** Add `String caseType` after `caseId` in the record. Always populated by stores.
**Alternatives:**
- Add `caseType()` to CbrCase interface — mixes storage metadata with case data; CbrCase is problem/solution/outcome, caseType is storage categorization
- Wrapper `TypedScoredCbrCase` — changes return type for cross-type queries only, awkward API split
**Rationale:** ScoredCbrCase is already the "result with metadata" record (caseId, score, storedAt, scope, trustTrajectory). caseType fits this pattern. Self-describing results eliminate query-result correlation.
**Trade-offs:** Adding a record field changes the canonical constructor — all call sites need updating. Mechanical but widespread.
**Sources:** ScoredCbrCase.java:7-8 (current record fields), CbrCase.java:8 (cbrType is paradigm discriminator, not business type)
**Exploration:** quick
**Status:** captured

## D3: Allow filters with null caseType — per-candidate schema lookup

**Choice:** Allow filters on cross-type queries. Validate/match per-candidate using stored caseType's schema.
**Alternatives:**
- Reject filters when caseType is null — simpler but artificially restricts queries on shared fields (e.g., severity=HIGH across types)
- Skip validation entirely, best-effort matching — loses HasMatch struct vs struct-list disambiguation
**Rationale:** Cross-type query = N single-type queries merged. Each candidate has a known caseType → schema. matchesFilters already excludes candidates missing the filtered field (storedValue == null → return false). Only HasMatch needs schema for ObjectList vs NestedObject disambiguation — skip candidates whose schema is null when HasMatch is present.
**Trade-offs:** Lose upfront "did you misspell the field name" validation for cross-type queries. Development-time guard only, not a correctness concern.
**Sources:** InMemoryCbrCaseMemoryStore.java:482 (null storedValue → false), :512-519 (HasMatch needs field type)
**Exploration:** deep-analysis
**Status:** captured

## D4: Qdrant multi-collection fan-out via listCollections

**Choice:** `client.listCollectionsAsync()` → filter by prefix → query each collection serially → merge by score → take topK
**Alternatives:**
- Use `schemas` map to find known caseTypes — misses types stored without schema registration
- Use `knownCollections` set — only populated in current JVM session, misses previous sessions
- Parallel fan-out via CompletableFuture — premature optimization for <10 collections
**Rationale:** listCollections is authoritative (metadata query, no data scan) and finds all types regardless of JVM session state. Serial execution is simple and sufficient for the expected cardinality (3-10 types per domain).
**Trade-offs:** N+1 RPCs (1 list + N queries). Acceptable at expected cardinality. Parallel execution is a documented future optimization.
**Sources:** CbrCollectionManager.java:49-51 (collectionName prefix scheme), :31 (knownCollections only session-scoped)
**Exploration:** deep-analysis
**Status:** captured
