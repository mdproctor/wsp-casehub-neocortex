# CBR Dense Vector Search + minSimilarity + Spec Sync

**Issues:** #70, #71, #58, #59 (closed)
**Date:** 2026-07-03
**Status:** Approved
**Parent spec:** [CBR Retrieval Architecture](../issue-20-cbr-retrieval-architecture/2026-06-30-cbr-retrieval-architecture.md)

---

## 1. Problem

`QdrantCbrCaseMemoryStore` embeds `CbrCase.problem()` at store time but never uses it for retrieval. `executeFilterQuery()` uses `scrollAsync` (payload-filter-only), returning synthetic score 1.0 for every match. CBR retrieval is reduced to exact-match feature filtering — no semantic similarity on the problem dimension.

`CbrQuery.minSimilarity` is declared but never applied by either backend.

The root gap: `CbrQuery` has no text field for query-side embedding. The spec §4.2 says "embed query.problem()" but `CbrQuery` doesn't have a `problem` field.

Additionally, the CBR spec has accumulated divergences from implementation across #20 and #68.

## 2. Scope

| Issue | Change | Type |
|-------|--------|------|
| #70 | Dense vector search — add `problem` to CbrQuery, dual-path retrieval | API + impl |
| #71 | Wire `minSimilarity` via Qdrant `score_threshold` | impl |
| #59 | Closed — discriminator-based switch already in place | none |
| #58 | Spec update to match code | docs |

## 3. CbrQuery API Change

CbrQuery gains a nullable `String problem` field:

```java
public record CbrQuery(
    String tenantId,
    MemoryDomain domain,
    String caseType,
    Map<String, Object> features,
    int topK,
    double minSimilarity,
    Instant notBefore,
    String problem              // NEW: nullable — text for dense search
) {
    public CbrQuery {
        Objects.requireNonNull(tenantId, "tenantId required");
        Objects.requireNonNull(domain, "domain required");
        Objects.requireNonNull(caseType, "caseType required");
        Objects.requireNonNull(features, "features required");
        features = Map.copyOf(features);
        if (topK < 1) throw new IllegalArgumentException("topK must be >= 1, got: " + topK);
        if (minSimilarity < 0.0 || minSimilarity > 1.0)
            throw new IllegalArgumentException("minSimilarity must be in [0,1], got: " + minSimilarity);
        if (problem != null && problem.isBlank())
            throw new IllegalArgumentException("problem must not be blank when provided");
    }

    public static CbrQuery of(String tenantId, MemoryDomain domain,
                               String caseType, Map<String, Object> features, int topK) {
        return new CbrQuery(tenantId, domain, caseType, features, topK, 0.0, null, null);
    }

    public CbrQuery withProblem(String problem) {
        return new CbrQuery(tenantId, domain, caseType, features, topK,
                            minSimilarity, notBefore, problem);
    }
}
```

**Naming:** `problem` mirrors `CbrCase.problem()` — the same concept from the query perspective. Follows existing conventions (`MemoryQuery.question()`).

**Breaking change:** Direct `new CbrQuery(...)` calls gain an 8th argument. `CbrQuery.of()` factory returns `problem=null`, so factory users compile unchanged. The compile error on direct construction is intentional — forces each caller to decide whether to provide a problem.

## 4. Dual-Path Retrieval

`QdrantCbrCaseMemoryStore.retrieveSimilar()` selects between two paths:

```
retrieveSimilar(query, caseClass)
  ├─ validate features against schema
  ├─ check collection exists
  ├─ build filter via CbrQueryTranslator.toFilter(query, schema)
  │
  ├─ embeddingModel != null && query.problem() != null?
  │   ├─ YES → executeDenseSearch(collection, filter, query)
  │   └─ NO  → executeFilterQuery(collection, filter, query.topK())
  │
  └─ reconstruct cases from ScoredPoints
```

### Dense search path

1. Embed `query.problem()` via `embeddingModel.embed()` → query vector
2. Build Qdrant `SearchPoints`:
   - Named vector (`config.denseVectorName()`) + query vector
   - Payload filter from `CbrQueryTranslator.toFilter()` (unchanged)
   - `limit` = `query.topK()`
   - `score_threshold` = `query.minSimilarity()` (when > 0.0)
   - `with_payload` = true
3. `searchAsync()` returns `List<ScoredPoint>` ordered by cosine similarity descending

### Filter-only path

Current `scrollAsync` behavior unchanged. Synthetic `score = 1.0` for all matches.

### Unchanged components

- `CbrPointBuilder` — store-time embedding already works
- `CbrQueryTranslator` — filter construction unchanged
- `CbrCollectionManager` — collection management unchanged
- `reconstructCase` — payload reconstruction unchanged

## 5. minSimilarity Wiring

**Qdrant dense path:** `score_threshold` on `SearchPoints`. Server-side filtering — results below threshold never returned. `minSimilarity == 0.0` (default) → omit `score_threshold`.

**Qdrant filter-only path:** No-op. All results score 1.0. Any `minSimilarity ≤ 1.0` passes.

**InMemory:** No change. No scoring capability. `minSimilarity` is structurally a no-op (implicit score 1.0).

**Score semantics:** Collection uses `Distance.Cosine`. Qdrant returns similarity in [0, 1]. Maps directly to `minSimilarity`'s [0, 1] range — no normalization.

## 6. Contract Tests

### CbrCaseMemoryStoreContractTest (new tests)

- `retrieveSimilar_withProblem_null_returnsFilteredResults` — `problem=null` still works (all backends)
- `retrieveSimilar_minSimilarity_zero_returnsAllMatches` — default threshold never filters (all backends)

### QdrantCbrDenseSearchTest (new test class)

Testcontainers Qdrant + deterministic EmbeddingModel stub:

- `denseSearch_ranksResultsBySimilarity` — different `problem()` texts, verify ordering
- `denseSearch_minSimilarity_filtersLowScoreResults` — threshold excludes distant cases
- `denseSearch_fallsBackToFilterOnly_whenProblemNull` — EmbeddingModel present but `problem=null` → all matches, no ranking
- `denseSearch_withPayloadFilters_combinesVectorAndFilter` — filter + dense search combined

### Existing tests

All 23 contract tests pass unchanged. `CbrQuery.of()` returns `problem=null`.

## 7. Spec Update (#58)

Divergences to fix in `specs/issue-20-cbr-retrieval-architecture/2026-06-30-cbr-retrieval-architecture.md`:

| Section | Divergence | Fix |
|---------|-----------|-----|
| §3.3 | PlanCbrCase location: spec says `engine-api`, code has `memory-api` | Update to `memory-api` |
| §4 | No `NumericRange` value type | Add NumericRange, document range query semantics |
| §4.2 | Dense search described aspirationally | Update to describe implemented dual-path |
| §5 | No `problem` field, no `notBefore` field | Add both fields, document semantics |
| §5 | No `minSimilarity` semantics | Document wiring to `score_threshold` |
| §6 | `store()` missing `caseType` parameter | Add parameter |
| §6 | `erase()`/`eraseEntity()` return `int` | Update to `Integer` (boxed for reactive parity) |
| §6.3 | NoOp "delegates to CaseMemoryStore" | Update: no delegation, standalone no-op |
| §7 | Retrieval: single path | Document dual-path (dense + filter-only) |

## 8. Files Changed

| Module | File | Change |
|--------|------|--------|
| memory-api | `CbrQuery.java` | Add `problem` field, `withProblem()` builder, validation |
| memory-qdrant | `QdrantCbrCaseMemoryStore.java` | Add `executeDenseSearch()`, branch in `retrieveSimilar()` |
| memory-testing | `CbrCaseMemoryStoreContractTest.java` | 2 new contract tests |
| memory-qdrant | `QdrantCbrDenseSearchTest.java` (NEW) | Dense search integration tests |
| workspace/specs | CBR spec | Divergence fixes per §7 |
