# Cross-Type CBR Query Design

**Issue:** casehubio/neocortex#288
**Blocked by this:** casehubio/engine#1055 (cross-case-type CBR retrieval), casehubio/engine#1054 (case definition selection)

## Problem

`CbrQuery.caseType` is `Objects.requireNonNull` — every query must specify a single case type. This prevents cross-type retrieval: "across all playbook types, which one produced the best outcome for alerts with these features?" The engine needs this for CBR-driven case definition selection.

## Design

### 1. Sealed CaseTypeScope (memory-api)

Replace `String caseType` on `CbrQuery` with a sealed `CaseTypeScope`:

```java
public sealed interface CaseTypeScope {
    record Specific(String caseType) implements CaseTypeScope {
        public Specific {
            Objects.requireNonNull(caseType, "caseType required");
        }
    }
    record AllInDomain() implements CaseTypeScope {}
}
```

`CbrQuery` changes:
- Record field: `CaseTypeScope caseTypeScope` replaces `String caseType`
- Compact constructor: `Objects.requireNonNull(caseTypeScope, "caseTypeScope required")`
- New factory: `CbrQuery.crossType(tenantId, domain, scope, features, topK)` — creates with `AllInDomain`
- Existing factory `CbrQuery.of(...)` retains `String caseType` parameter, wraps in `Specific`
- Convenience accessor: `String caseType()` returns the string for `Specific`, throws for `AllInDomain` (callers that need the string must pattern-match first — the exception catches missed migrations)
- All `with*` methods carry `caseTypeScope` through unchanged

The sealed interface forces exhaustive switch expressions at every consumption site. A missing case is a compile error, not a runtime NPE. This eliminates three `ConcurrentHashMap.get(null)` NPE sites and one `.equals(null)` silent-filtering bug that nullable `String` would have introduced.

### 2. ScoredCbrCase caseType field (memory-api)

Add `String caseType` after `caseId`:

```java
public record ScoredCbrCase<C extends CbrCase>(
    C cbrCase, String caseId, String caseType, double score, boolean reranked,
    Map<String, Double> featureSimilarities, Instant storedAt,
    Path scope, Double trustTrajectory)
```

- `Objects.requireNonNull(caseType, "caseType required")` in the compact constructor — caseType is always known at store time
- All convenience constructors: accept caseType or use a default (existing 2-arg `(cbrCase, score)` and `(cbrCase, score, reranked)` add a caseType parameter)
- Add `withCaseType(String)` wither
- All existing `with*` methods carry caseType through
- Always populated by stores — results are self-describing regardless of query type

### 3. InMemory store changes

In `retrieveSimilar()`, switch on `query.caseTypeScope()`:

**Specific path (existing behavior, refactored):**
- `schemas.get(caseTypeScope.caseType())` for schema lookup — same as today
- `stored.caseType().equals(caseTypeScope.caseType())` filter — same as today
- Populate `caseType` on `ScoredCbrCase` from `StoredCase.caseType()`

**AllInDomain path:**
- Remove caseType filter — iterate all cases matching tenant + domain
- Schema lookup per candidate: `schemas.get(stored.caseType())`
- Feature validation per candidate against its own schema
- DTW band field extraction per candidate schema
- Filter validation per candidate:
  - If filters contain `HasMatch` and candidate schema is null → skip candidate, log warning
  - Otherwise `matchesFilters()` with per-candidate schema
- Populate `caseType` on each `ScoredCbrCase` from `StoredCase.caseType()`

### 4. Qdrant store changes

Switch on `query.caseTypeScope()`:

**Specific path (existing behavior, refactored):**
- Single collection: `collectionManager.collectionName(caseType)` — same as today
- Populate `caseType` on results from the known type

**AllInDomain path:**
1. `client.listCollectionsAsync()` → filter by `config.collectionPrefix() + "_"` prefix → extract caseType suffix
2. Parallel fan-out: submit a query to each collection via `Futures.allAsList()` (Guava, already a transitive dependency)
3. Per-collection: build identity filter omitting caseType, schema lookup from `schemas.get(derivedCaseType)`, apply structural filters per-collection schema
4. Merge all candidates by score, take overall topK
5. Partial failure: if a collection query fails, log warning, return results from successful collections
6. Populate `caseType` on results from collection name suffix

Identity filter change in `CbrQueryTranslator.toIdentityFilter()`: accept `CaseTypeScope` — add `matchKeyword("caseType", ...)` only for `Specific`, omit for `AllInDomain`.

### 5. Score merging strategy

Raw score merge — no cross-type normalization. `CbrSimilarityScorer` produces weighted averages in [0,1] with consistent semantics regardless of schema. The fan-out caps per-type results to topK, preventing data-volume dominance. Different schemas produce different score distributions by design — fewer features means each contributes more, which is correct when those features are the important discriminators.

### 6. Decorator chain impact

All decorators on `retrieveSimilar` handle `AllInDomain` transparently:

| Decorator | Priority | Behavior with AllInDomain |
|---|---|---|
| TrendEnrichment | 90 | `expandedSchemas.get(...)` — pattern match CaseTypeScope: skip enrichment for AllInDomain (trend fields are type-specific) |
| ScopeDecay | 85 | Independent of caseType — operates on results |
| CrossEncoder | 75 | Independent of caseType — reranks by score |
| OutcomeWeighting | 65 | Independent of caseType — modulates by confidence |
| TrustWeighted | 60 | Independent of caseType — modulates by trust |
| Tracking | 50 | Independent of caseType — records events |

Only TrendEnrichment needs a code change (pattern match on CaseTypeScope instead of `schemas.get(query.caseType())`). All other decorators pass through unchanged.

### 7. Contract test additions (memory-testing)

New tests in `CbrCaseMemoryStoreContractTest`:
- Cross-type retrieval: store cases of types A and B, query with `AllInDomain`, verify both returned with correct `caseType` on `ScoredCbrCase`
- Single-type with caseType populated: existing tests updated to verify `caseType` on results
- Cross-type with shared-field filter: filter by field present in both types, verify matching cases from both types returned
- Cross-type with type-specific filter: filter by field present only in type A, verify type B cases excluded (not errored)
- Cross-type result ordering: verify results sorted by score across types, topK respected
- Cross-type with `AllInDomain` and no registered schemas: verify empty results (no candidates match when schemas required for scoring)

New tests in `CbrQueryTest`:
- `crossType()` factory creates `AllInDomain` scope
- `of()` factory creates `Specific` scope
- `caseType()` accessor throws for `AllInDomain`
- `caseTypeScope()` is non-null for both variants
- `withCaseType()` wither produces `Specific`

New tests in `ScoredCbrCaseTest`:
- `caseType` is required (NPE on null)
- `withCaseType()` produces new instance with updated caseType

## Non-goals

- Parallel fan-out optimization beyond `Futures.allAsList()` (thread pool tuning, connection pooling per collection)
- Cross-type score normalization (percentile rank, z-score) — defer until empirical evidence of score distribution issues
- Cross-type queries on other SPI methods (`findCaseIds`, `supersedeMatching`, `scan`) — these are targeted operations on specific types

## References

- CbrQuery.java:10-169 — current CbrQuery record
- ScoredCbrCase.java:7-48 — current ScoredCbrCase record
- InMemoryCbrCaseMemoryStore.java:80-163 — retrieveSimilar with caseType filter
- QdrantCbrCaseMemoryStore.java:208-238 — retrieveSimilar with collection routing
- CbrCollectionManager.java:49-51 — collectionName prefix scheme
- CbrQueryTranslator.java:35-60 — toIdentityFilter with caseType match
- TrendEnrichmentCbrCaseMemoryStore.java:54-64 — retrieveSimilar schema lookup
- CbrSimilarityScorer — weighted average scoring in [0,1]
- casehubio/engine#1055 — cross-case-type CBR retrieval (blocked)
- casehubio/engine#1054 — case definition selection (blocked)
- decisions.md — D1-D5 decision records with alternatives and rationale
