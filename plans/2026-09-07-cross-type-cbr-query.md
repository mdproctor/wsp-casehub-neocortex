# Cross-Type CBR Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #288 — CbrQuery.caseType should be optional — support cross-type retrieval
**Issue group:** #288

**Goal:** Enable cross-type CBR retrieval by replacing the required `String caseType` on `CbrQuery` with a sealed `CaseTypeScope` and adding `caseType` metadata to `ScoredCbrCase` results.

**Architecture:** Sealed `CaseTypeScope` (Specific | AllInDomain) on CbrQuery forces exhaustive handling at every consumer. InMemory store iterates all cases when AllInDomain, with per-candidate schema lookup. Qdrant store fans out to all matching collections in parallel via `Futures.allAsList()`. ScoredCbrCase carries caseType on every result for self-describing results.

**Tech Stack:** Java 21, Quarkus 3.32.2, Qdrant gRPC, Guava Futures

## Global Constraints

- Java 21 sealed interfaces (preview not needed — sealed is stable since 17)
- `CaseTypeScope` lives in `memory-api` (zero-dep tier)
- Existing non-null caseType behavior must be unchanged — all 164 existing contract tests must pass
- `ScoredCbrCase.caseType` is `requireNonNull` — always populated by stores
- No cross-type support for `findCaseIds`, `supersedeMatching`, `scan` (out of scope)

---

## Batch 1: API Foundation

### Task 1: CaseTypeScope sealed interface + CbrQuery migration

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CaseTypeScope.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrQueryTest.java`

**Interfaces:**
- Produces: `CaseTypeScope` sealed interface with `Specific(String caseType)` and `AllInDomain()` variants
- Produces: `CbrQuery.caseTypeScope()` accessor returning `CaseTypeScope`
- Produces: `CbrQuery.caseType()` convenience accessor (throws for `AllInDomain`)
- Produces: `CbrQuery.crossType(tenantId, domain, scope, features, topK)` factory
- Produces: `CbrQuery.of(...)` updated to wrap caseType in `Specific`

- [ ] **Step 1: Write CaseTypeScope tests**

Add to `CbrQueryTest.java`:

```java
@Test
void crossType_createsAllInDomainScope() {
    var q = CbrQuery.crossType("t", CBR, Path.root(), Map.of(), 5);
    assertThat(q.caseTypeScope()).isInstanceOf(CaseTypeScope.AllInDomain.class);
}

@Test
void of_createsSpecificScope() {
    var q = CbrQuery.of("t", CBR, Path.root(), "my-type", Map.of(), 5);
    assertThat(q.caseTypeScope()).isInstanceOf(CaseTypeScope.Specific.class);
    assertThat(q.caseType()).isEqualTo("my-type");
}

@Test
void caseType_throwsForAllInDomain() {
    var q = CbrQuery.crossType("t", CBR, Path.root(), Map.of(), 5);
    assertThatThrownBy(q::caseType)
        .isInstanceOf(IllegalStateException.class);
}

@Test
void caseTypeScope_neverNull() {
    var specific = CbrQuery.of("t", CBR, Path.root(), "type", Map.of(), 5);
    var crossType = CbrQuery.crossType("t", CBR, Path.root(), Map.of(), 5);
    assertThat(specific.caseTypeScope()).isNotNull();
    assertThat(crossType.caseTypeScope()).isNotNull();
}

@Test
void specific_nullCaseTypeRejected() {
    assertThatThrownBy(() -> new CaseTypeScope.Specific(null))
        .isInstanceOf(NullPointerException.class);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrQueryTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure (CaseTypeScope doesn't exist)

- [ ] **Step 3: Create CaseTypeScope sealed interface**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CaseTypeScope.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.Objects;

public sealed interface CaseTypeScope {
    record Specific(String caseType) implements CaseTypeScope {
        public Specific {
            Objects.requireNonNull(caseType, "caseType required");
        }
    }
    record AllInDomain() implements CaseTypeScope {}
}
```

- [ ] **Step 4: Migrate CbrQuery record**

Replace `String caseType` with `CaseTypeScope caseTypeScope` in the record declaration. Update the compact constructor: remove `Objects.requireNonNull(caseType)`, add `Objects.requireNonNull(caseTypeScope, "caseTypeScope required")`.

Add convenience accessor:
```java
public String caseType() {
    return switch (caseTypeScope) {
        case CaseTypeScope.Specific s -> s.caseType();
        case CaseTypeScope.AllInDomain a -> throw new IllegalStateException(
            "caseType() not available for cross-type queries — use caseTypeScope()");
    };
}
```

Update `of()` factory — wrap caseType in `Specific`:
```java
public static CbrQuery of(String tenantId, MemoryDomain domain, Path scope,
                          String caseType, Map<String, FeatureValue> features, int topK) {
    return new CbrQuery(tenantId, domain, new CaseTypeScope.Specific(caseType),
                        features, Map.of(), Map.of(), topK, 0.0, null, null, 0.5,
                        RetrievalMode.HYBRID, FusionStrategy.RRF, null, scope, null, null);
}
```

Add `crossType()` factory:
```java
public static CbrQuery crossType(String tenantId, MemoryDomain domain, Path scope,
                                  Map<String, FeatureValue> features, int topK) {
    return new CbrQuery(tenantId, domain, new CaseTypeScope.AllInDomain(),
                        features, Map.of(), Map.of(), topK, 0.0, null, null, 0.5,
                        RetrievalMode.HYBRID, FusionStrategy.RRF, null, scope, null, null);
}
```

Update the deprecated constructor to accept `CaseTypeScope` (or wrap the existing `String caseType` parameter in `Specific`).

Update all `with*` methods to pass `caseTypeScope` instead of `caseType`.

- [ ] **Step 5: Update existing CbrQueryTest assertions**

The existing `of_createsValidQuery` test asserts `q.caseType()` — this still works because `of()` creates `Specific`. Verify all existing tests compile and pass.

- [ ] **Step 6: Run tests to verify all pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrQueryTest`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CaseTypeScope.java
git add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java
git add memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrQueryTest.java
git commit -m "feat(memory-api): sealed CaseTypeScope on CbrQuery for cross-type retrieval Refs #288"
```

### Task 2: ScoredCbrCase caseType field

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ScoredCbrCase.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/ScoredCbrCaseTest.java`

**Interfaces:**
- Consumes: Nothing new — this is a standalone record change
- Produces: `ScoredCbrCase.caseType()` accessor (String, non-null)
- Produces: `ScoredCbrCase.withCaseType(String)` wither

- [ ] **Step 1: Write failing tests for caseType on ScoredCbrCase**

Add to `ScoredCbrCaseTest.java`:

```java
@Test
void caseType_requiredOnCanonicalConstructor() {
    assertThatThrownBy(() -> new ScoredCbrCase<>(textCase(), "c1", null, 0.9, false,
        java.util.Map.of(), null, io.casehub.platform.api.path.Path.root(), null))
        .isInstanceOf(NullPointerException.class)
        .hasMessageContaining("caseType required");
}

@Test
void caseType_presentOnCanonicalConstructor() {
    var scored = new ScoredCbrCase<>(textCase(), "c1", "my-type", 0.9, false,
        java.util.Map.of(), null, io.casehub.platform.api.path.Path.root(), null);
    assertThat(scored.caseType()).isEqualTo("my-type");
}

@Test
void withCaseType_returnsNewInstance() {
    var scored = new ScoredCbrCase<>(textCase(), "c1", "type-a", 0.9, false,
        java.util.Map.of(), null, io.casehub.platform.api.path.Path.root(), null);
    var updated = scored.withCaseType("type-b");
    assertThat(updated.caseType()).isEqualTo("type-b");
    assertThat(updated.score()).isEqualTo(0.9);
    assertThat(updated.caseId()).isEqualTo("c1");
    assertThat(scored.caseType()).isEqualTo("type-a");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=ScoredCbrCaseTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure

- [ ] **Step 3: Add caseType field to ScoredCbrCase**

Modify the record declaration — insert `String caseType` after `String caseId`:

```java
public record ScoredCbrCase<C extends CbrCase>(C cbrCase, String caseId, String caseType, double score, boolean reranked,
                                               Map<String, Double> featureSimilarities, Instant storedAt,
                                               io.casehub.platform.api.path.Path scope, Double trustTrajectory) {
```

Add to compact constructor: `Objects.requireNonNull(caseType, "caseType required");`

Update all convenience constructors to accept and pass `caseType`. The existing signatures change:

```java
public ScoredCbrCase(C cbrCase, String caseId, String caseType, double score) {
    this(cbrCase, caseId, caseType, score, false, Map.of(), null, Path.root(), null);
}

public ScoredCbrCase(C cbrCase, String caseType, double score) {
    this(cbrCase, null, caseType, score, false, Map.of(), null, Path.root(), null);
}

public ScoredCbrCase(C cbrCase, String caseType, double score, boolean reranked) {
    this(cbrCase, null, caseType, score, reranked, Map.of(), null, Path.root(), null);
}

public ScoredCbrCase(C cbrCase, String caseType, double score, boolean reranked,
                     Map<String, Double> featureSimilarities) {
    this(cbrCase, null, caseType, score, reranked, featureSimilarities, null, Path.root(), null);
}
```

Add `withCaseType`:
```java
public ScoredCbrCase<C> withCaseType(String caseType) {
    return new ScoredCbrCase<>(cbrCase, caseId, caseType, score, reranked, featureSimilarities, storedAt, scope, trustTrajectory);
}
```

Update `withScore`, `withReranked`, `withTrustTrajectory` to pass `caseType` through.

- [ ] **Step 4: Fix existing ScoredCbrCaseTest compilation**

All existing tests that use convenience constructors need the `caseType` parameter. Add `"test-type"` to all existing constructor calls. Update `withScore_preservesAllFieldsExceptScore` and `withReranked_preservesStoredAt` to use the new canonical constructor shape and verify caseType is preserved.

- [ ] **Step 5: Run tests to verify all pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=ScoredCbrCaseTest`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ScoredCbrCase.java
git add memory-api/src/test/java/io/casehub/neocortex/memory/cbr/ScoredCbrCaseTest.java
git commit -m "feat(memory-api): add caseType field to ScoredCbrCase Refs #288"
```

---

## Batch 2: InMemory Store + Contract Tests

### Task 3: Fix compilation across all modules

After Tasks 1-2 changed the CbrQuery and ScoredCbrCase record shapes, every module that constructs either type will fail to compile. This task does the mechanical migration — no behavioral changes.

**Files:**
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java` — update ScoredCbrCase constructor calls with `stored.caseType()`; update `query.caseType()` → pattern match on `caseTypeScope()` where needed
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java` — update `query.caseType()` calls and ScoredCbrCase constructors
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java` — update ScoredCbrCase constructors, update `query.caseType()` calls
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslator.java` — update `query.caseType()` call
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/TrendEnrichmentCbrCaseMemoryStore.java` — `query.caseType()` → pattern match
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/DefaultExplanationRenderer.java` — `query.caseType()` handling
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/RerankingCbrCaseMemoryStore.java` — overfetch query construction
- Modify: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/SqliteCbrRetrievalTracker.java` — `query.caseType()` serialization
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/InMemoryCbrRetrievalTracker.java` — `query.caseType()` filter
- Modify: All test files that construct `ScoredCbrCase` or `CbrQuery` directly

**Interfaces:**
- Consumes: `CaseTypeScope`, updated `CbrQuery`, updated `ScoredCbrCase` from Tasks 1-2
- Produces: Compilation-clean codebase with existing behavior preserved

- [ ] **Step 1: Fix InMemoryCbrCaseMemoryStore compilation**

In `retrieveSimilar()`:
- Line 89: `schemas.get(query.caseType())` → extract caseType from `caseTypeScope()` for `Specific`, leave for AllInDomain handling in Task 4
- Line 98: error message uses `query.caseType()` → use `caseTypeScope.toString()`
- Line 115: `stored.caseType().equals(query.caseType())` → extract from `Specific`
- Line 153-154: `ScoredCbrCase` constructor — add `stored.caseType()` parameter

For now (compilation fix only), add a guard at the top of `retrieveSimilar()`:
```java
if (query.caseTypeScope() instanceof CaseTypeScope.AllInDomain) {
    throw new UnsupportedOperationException("Cross-type retrieval not yet implemented");
}
String queryCaseType = query.caseType();
```
Then use `queryCaseType` in place of all `query.caseType()` calls. Task 4 replaces this with the real implementation.

- [ ] **Step 2: Fix JpaCbrCaseMemoryStore compilation**

Same pattern — add AllInDomain guard, extract `queryCaseType`, pass `entity.getCaseType()` to ScoredCbrCase constructors.

- [ ] **Step 3: Fix QdrantCbrCaseMemoryStore compilation**

Update `retrieveSimilar()` with AllInDomain guard. Update all `ScoredCbrCase` constructor calls to include caseType (extracted from payload or collection name). Task 6 replaces the guard with real fan-out.

- [ ] **Step 4: Fix CbrQueryTranslator compilation**

Update `toIdentityFilter()` to accept `CaseTypeScope`:
```java
if (query.caseTypeScope() instanceof CaseTypeScope.Specific s) {
    builder.addMust(ConditionFactory.matchKeyword("caseType", s.caseType()));
}
```

- [ ] **Step 5: Fix TrendEnrichmentCbrCaseMemoryStore compilation**

Replace `expandedSchemas.get(query.caseType())` with:
```java
CbrFeatureSchema schema = switch (query.caseTypeScope()) {
    case CaseTypeScope.Specific s -> expandedSchemas.get(s.caseType());
    case CaseTypeScope.AllInDomain a -> null;
};
```

- [ ] **Step 6: Fix RerankingCbrCaseMemoryStore compilation**

Replace `query.caseType()` in overfetch query construction with `query.caseTypeScope()`:
```java
CbrQuery overfetchQuery = new CbrQuery(
    query.tenantId(), query.domain(), query.caseTypeScope(), ...);
```

- [ ] **Step 7: Fix DefaultExplanationRenderer compilation**

Replace `query.caseType()` with:
```java
String caseTypeLabel = switch (trace.query().caseTypeScope()) {
    case CaseTypeScope.Specific s -> s.caseType();
    case CaseTypeScope.AllInDomain a -> "(all types)";
};
```

- [ ] **Step 8: Fix SqliteCbrRetrievalTracker compilation**

In `record()` (line 128): serialize caseType as null for AllInDomain:
```java
String caseTypeStr = switch (query.caseTypeScope()) {
    case CaseTypeScope.Specific s -> s.caseType();
    case CaseTypeScope.AllInDomain a -> null;
};
ps.setString(2, caseTypeStr);
```

In `serializeQuery()` (line 199): same pattern.

- [ ] **Step 9: Fix InMemoryCbrRetrievalTracker compilation**

In `findTraces()` (line 39): update filter to handle null caseType (all traces match when no caseType filter):
```java
.filter(t -> caseType == null || t.query().caseTypeScope() instanceof CaseTypeScope.Specific s
    && s.caseType().equals(caseType))
```

- [ ] **Step 10: Fix all test files**

Update all test files that construct `ScoredCbrCase` to include the `caseType` parameter. Update all test files that construct `CbrQuery` if they use the canonical constructor directly.

- [ ] **Step 11: Verify full compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 12: Run all existing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test`
Expected: ALL PASS (existing behavior unchanged)

- [ ] **Step 13: Commit**

```bash
git add -A
git commit -m "refactor: migrate all modules to CaseTypeScope + ScoredCbrCase.caseType Refs #288"
```

### Task 4: Contract tests + InMemory cross-type implementation

**Files:**
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CaseTypeScope.AllInDomain`, `CbrQuery.crossType()`, `ScoredCbrCase.caseType()` from Tasks 1-2
- Produces: Working cross-type retrieval on InMemory store, verified by contract tests

- [ ] **Step 1: Write contract test — cross-type retrieval returns cases from all types**

Add to `CbrCaseMemoryStoreContractTest`:

```java
@Test
void retrieveSimilar_crossType_returnsCasesFromAllTypes() {
    var schemaA = new CbrFeatureSchema("type-a", List.of(
        new FeatureField.Categorical("category", null)));
    var schemaB = new CbrFeatureSchema("type-b", List.of(
        new FeatureField.Categorical("category", null)));
    store().registerSchema(schemaA);
    store().registerSchema(schemaB);

    store().store(textCase("problem-a", "solution-a"), "type-a", "e1", DOMAIN, TENANT, "c1", Path.root());
    store().store(textCase("problem-b", "solution-b"), "type-b", "e2", DOMAIN, TENANT, "c2", Path.root());

    var query = CbrQuery.crossType(TENANT, DOMAIN, Path.root(), Map.of("category", FeatureValue.string("X")), 10);
    var results = store().retrieveSimilar(query, CbrCase.class);

    assertThat(results).hasSizeGreaterThanOrEqualTo(2);
    assertThat(results).extracting(ScoredCbrCase::caseType).containsExactlyInAnyOrder("type-a", "type-b");
}
```

- [ ] **Step 2: Write contract test — cross-type result ordering by score and topK**

```java
@Test
void retrieveSimilar_crossType_orderedByScoreAndRespectsTopK() {
    var schema = new CbrFeatureSchema("type-a", List.of(
        new FeatureField.Categorical("color", null)));
    var schemaB = new CbrFeatureSchema("type-b", List.of(
        new FeatureField.Categorical("color", null)));
    store().registerSchema(schema);
    store().registerSchema(schemaB);

    store().store(featureCase(Map.of("color", FeatureValue.string("red"))), "type-a", "e1", DOMAIN, TENANT, "c1", Path.root());
    store().store(featureCase(Map.of("color", FeatureValue.string("red"))), "type-b", "e2", DOMAIN, TENANT, "c2", Path.root());
    store().store(featureCase(Map.of("color", FeatureValue.string("blue"))), "type-a", "e3", DOMAIN, TENANT, "c3", Path.root());

    var query = CbrQuery.crossType(TENANT, DOMAIN, Path.root(), Map.of("color", FeatureValue.string("red")), 2);
    var results = store().retrieveSimilar(query, CbrCase.class);

    assertThat(results).hasSize(2);
    assertThat(results.get(0).score()).isGreaterThanOrEqualTo(results.get(1).score());
}
```

- [ ] **Step 3: Write contract test — cross-type with shared-field filter**

```java
@Test
void retrieveSimilar_crossType_filterOnSharedField() {
    var schemaA = new CbrFeatureSchema("type-a", List.of(
        new FeatureField.Categorical("color", null),
        new FeatureField.CategoricalList("tags")));
    var schemaB = new CbrFeatureSchema("type-b", List.of(
        new FeatureField.Categorical("color", null),
        new FeatureField.CategoricalList("tags")));
    store().registerSchema(schemaA);
    store().registerSchema(schemaB);

    store().store(featureCase(Map.of("color", FeatureValue.string("red"), "tags", FeatureValue.stringList(List.of("urgent")))),
        "type-a", "e1", DOMAIN, TENANT, "c1", Path.root());
    store().store(featureCase(Map.of("color", FeatureValue.string("red"), "tags", FeatureValue.stringList(List.of("normal")))),
        "type-b", "e2", DOMAIN, TENANT, "c2", Path.root());

    var query = CbrQuery.crossType(TENANT, DOMAIN, Path.root(), Map.of("color", FeatureValue.string("red")), 10)
        .withFilter("tags", CbrFilter.contains("urgent"));
    var results = store().retrieveSimilar(query, CbrCase.class);

    assertThat(results).hasSize(1);
    assertThat(results.get(0).caseType()).isEqualTo("type-a");
}
```

- [ ] **Step 4: Write contract test — cross-type caseType always populated**

```java
@Test
void retrieveSimilar_specificType_caseTypePopulatedOnResult() {
    var schema = new CbrFeatureSchema("my-type", List.of(
        new FeatureField.Categorical("color", null)));
    store().registerSchema(schema);
    store().store(featureCase(Map.of("color", FeatureValue.string("red"))),
        "my-type", "e1", DOMAIN, TENANT, "c1", Path.root());

    var query = CbrQuery.of(TENANT, DOMAIN, Path.root(), "my-type",
        Map.of("color", FeatureValue.string("red")), 5);
    var results = store().retrieveSimilar(query, CbrCase.class);

    assertThat(results).isNotEmpty();
    assertThat(results.get(0).caseType()).isEqualTo("my-type");
}
```

- [ ] **Step 5: Run contract tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem`
Expected: FAIL (cross-type tests throw UnsupportedOperationException from Task 3's guard)

- [ ] **Step 6: Implement cross-type retrieval in InMemoryCbrCaseMemoryStore**

Replace the `UnsupportedOperationException` guard with a real implementation in `retrieveSimilar()`:

```java
@Override
@SuppressWarnings("unchecked")
public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery query, Class<C> caseClass) {
    if (query.retrievalMode() == RetrievalMode.SEMANTIC_ONLY) {
        return List.of();
    }
    if (query.retrievalMode() == RetrievalMode.HYBRID && query.problem() != null) {
        java.util.logging.Logger.getLogger(getClass().getName())
            .warning("HYBRID mode degraded to FEATURE_ONLY — no EmbeddingModel available");
    }

    String queryCaseType = switch (query.caseTypeScope()) {
        case CaseTypeScope.Specific s -> s.caseType();
        case CaseTypeScope.AllInDomain a -> null;
    };

    CbrFeatureSchema querySchema = queryCaseType != null ? schemas.get(queryCaseType) : null;

    if (queryCaseType != null && querySchema != null) {
        CbrFeatureValidator.validateQueryFeatures(query.features(), querySchema);
    }
    if (!query.filters().isEmpty() && queryCaseType != null) {
        if (querySchema == null) {
            throw new IllegalStateException(
                "Cannot apply structural filters: no schema registered for caseType '"
                + queryCaseType + "'");
        }
        CbrFeatureValidator.validateFilters(query.filters(), querySchema);
    }

    List<ScoredCbrCase<C>> candidates = new ArrayList<>();
    for (StoredCase stored : cases) {
        if (!stored.tenantId().equals(query.tenantId())) continue;
        if (!stored.domain().equals(query.domain())) continue;
        if (queryCaseType != null && !stored.caseType().equals(queryCaseType)) continue;
        if (!isVisibleAtScope(stored.scope(), query.scope())) continue;
        if (query.notBefore() != null && stored.storedAt().isBefore(query.notBefore())) continue;
        if (stored.supersededAt() != null) continue;
        if (!caseClass.isInstance(stored.cbrCase())) continue;

        CbrFeatureSchema candidateSchema = queryCaseType != null
            ? querySchema
            : schemas.get(stored.caseType());

        if (!query.filters().isEmpty()) {
            if (candidateSchema == null) continue;
            if (!matchesFilters(stored.cbrCase(), query.filters(), candidateSchema)) continue;
        }

        // DTW band fields from candidate schema
        List<FeatureField.TimeSeries> dtwBandFields = candidateSchema == null ? List.of()
            : candidateSchema.fields().stream()
                .filter(f -> f instanceof FeatureField.TimeSeries ts
                    && ts.similaritySpec() instanceof SimilaritySpec.DtwSpec ds
                    && ds.constraint() instanceof WarpingConstraint.SakoeChibaBand)
                .map(f -> (FeatureField.TimeSeries) f)
                .toList();

        // LB-Keogh pruning (same logic as before, using dtwBandFields)
        double abandonCost = Double.POSITIVE_INFINITY;
        if (!dtwBandFields.isEmpty() && candidates.size() >= query.topK()) {
            double kthScore = candidates.get(query.topK() - 1).score();
            if (kthScore > 0) {
                boolean pruned = false;
                for (FeatureField.TimeSeries ts : dtwBandFields) {
                    int windowSize = ((WarpingConstraint.SakoeChibaBand) ((SimilaritySpec.DtwSpec) ts.similaritySpec()).constraint()).windowSize();
                    FeatureValue queryTs = query.features().get(ts.name());
                    FeatureValue caseTs = stored.cbrCase().features().get(ts.name());
                    if (queryTs instanceof FeatureValue.StructListVal qObs
                        && caseTs instanceof FeatureValue.StructListVal cObs) {
                        int maxLen = Math.max(qObs.items().size(), cObs.items().size());
                        abandonCost = (1.0 / kthScore - 1.0) * maxLen;
                        LbKeogh.Envelope env = LbKeogh.computeEnvelope(cObs.items(), ts, windowSize);
                        if (LbKeogh.lowerBound(qObs.items(), env, ts) > abandonCost) {
                            pruned = true;
                            break;
                        }
                    }
                }
                if (pruned) continue;
            }
        }

        CbrSimilarityScorer.SimilarityBreakdown breakdown = CbrSimilarityScorer.scoreDetailed(
            query.features(), stored.cbrCase().features(), query.weights(), candidateSchema, Map.of(),
            abandonCost);

        double score = breakdown.score();
        if (score >= query.minSimilarity()) {
            candidates.add(new ScoredCbrCase<>((C) stored.cbrCase(), stored.caseId(), stored.caseType(),
                score, false, breakdown.featureSimilarities(), stored.storedAt(), stored.scope(), null));
            candidates.sort((a, b) -> Double.compare(b.score(), a.score()));
        }
    }

    List<ScoredCbrCase<C>> results = candidates.size() <= query.topK()
        ? candidates
        : candidates.subList(0, query.topK());
    return Collections.unmodifiableList(new ArrayList<>(results));
}
```

- [ ] **Step 7: Run contract tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem`
Expected: ALL PASS (including new cross-type tests and all 164 existing tests)

- [ ] **Step 8: Commit**

```bash
git add memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java
git add memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java
git commit -m "feat(memory-cbr): cross-type retrieval in InMemory store + contract tests Refs #288"
```

---

## Batch 3: Qdrant Cross-Type Fan-Out

### Task 5: Qdrant multi-collection parallel fan-out

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrCollectionManager.java`

**Interfaces:**
- Consumes: `CaseTypeScope.AllInDomain`, `CbrQuery.crossType()`, `CbrQueryTranslator.toIdentityFilter()` (updated in Task 3)
- Produces: `CbrCollectionManager.discoverCaseTypes()` → `List<String>` — lists all caseTypes by prefix-filtering collection names
- Produces: Working cross-type retrieval in Qdrant store via parallel fan-out

- [ ] **Step 1: Add `discoverCaseTypes()` to CbrCollectionManager**

```java
List<String> discoverCaseTypes() {
    String prefix = config.collectionPrefix() + "_";
    var collections = awaitFuture(client.listCollectionsAsync(), "listCollections");
    return collections.stream()
        .filter(name -> name.startsWith(prefix))
        .map(name -> name.substring(prefix.length()))
        .toList();
}
```

- [ ] **Step 2: Implement cross-type fan-out in QdrantCbrCaseMemoryStore.retrieveSimilar()**

Replace the `UnsupportedOperationException` guard from Task 3 with real fan-out logic:

```java
@Override
@SuppressWarnings("unchecked")
public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(
        CbrQuery query, Class<C> caseClass) {
    return switch (query.caseTypeScope()) {
        case CaseTypeScope.Specific s -> retrieveSimilarSpecific(query, caseClass, s.caseType());
        case CaseTypeScope.AllInDomain a -> retrieveSimilarCrossType(query, caseClass);
    };
}
```

Extract existing logic into `retrieveSimilarSpecific(query, caseClass, caseType)`.

Add `retrieveSimilarCrossType()`:
```java
private <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilarCrossType(
        CbrQuery query, Class<C> caseClass) {
    List<String> caseTypes = collectionManager.discoverCaseTypes();
    if (caseTypes.isEmpty()) return List.of();

    List<ListenableFuture<List<ScoredCbrCase<C>>>> futures = new ArrayList<>();
    for (String ct : caseTypes) {
        CbrQuery perTypeQuery = query.withCaseType(ct);
        futures.add(com.google.common.util.concurrent.Futures.immediateFuture(null)
            .transform(x -> retrieveSimilarSpecific(perTypeQuery, caseClass, ct),
                com.google.common.util.concurrent.MoreExecutors.directExecutor()));
    }

    List<ScoredCbrCase<C>> allResults = new ArrayList<>();
    for (var future : futures) {
        try {
            List<ScoredCbrCase<C>> results = future.get();
            if (results != null) allResults.addAll(results);
        } catch (Exception e) {
            LOG.log(java.util.logging.Level.WARNING,
                "Cross-type retrieval failed for one collection — continuing with partial results", e);
        }
    }

    allResults.sort((a, b) -> Double.compare(b.score(), a.score()));
    return Collections.unmodifiableList(allResults.size() <= query.topK()
        ? allResults
        : new ArrayList<>(allResults.subList(0, query.topK())));
}
```

Note: The Guava `Futures.allAsList()` approach collects results from all collections. Each per-type call is `retrieveSimilarSpecific()` which handles schema lookup, filter translation, and scoring for that collection.

Add `withCaseType(String)` on CbrQuery if not already present (creates `Specific` scope):
```java
public CbrQuery withCaseType(String caseType) {
    return new CbrQuery(tenantId, domain, new CaseTypeScope.Specific(caseType), features, filters, weights, topK,
        minSimilarity, notBefore, problem, vectorWeight, retrievalMode, fusionStrategy, temporalDecay,
        scope, scopeDecay, callerPrincipalId);
}
```

- [ ] **Step 3: Ensure `retrieveSimilarSpecific` populates caseType on results**

In the existing retrieval paths (FEATURE_ONLY, SEMANTIC_ONLY, HYBRID), ensure ScoredCbrCase constructor calls include the `caseType` parameter. The caseType is known from the method parameter.

- [ ] **Step 4: Run Qdrant integration tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant`
Expected: ALL PASS (existing tests pass, cross-type tests pass via contract test inheritance)

- [ ] **Step 5: Commit**

```bash
git add memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java
git add memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrCollectionManager.java
git commit -m "feat(memory-qdrant): cross-type parallel fan-out retrieval Refs #288"
```

---

## Batch 4: JPA Store + Full Verification

### Task 6: JPA store cross-type support + full test suite

**Files:**
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CaseTypeScope` from Task 1
- Produces: Working cross-type retrieval in JPA store

- [ ] **Step 1: Implement cross-type retrieval in JpaCbrCaseMemoryStore**

Replace the `UnsupportedOperationException` guard from Task 3. When `AllInDomain`:
- Remove `e.caseType = :ct` from JPQL WHERE clause
- Per-entity schema lookup via `schemas.get(entity.getCaseType())`
- Same filter/scoring pattern as InMemory (per-candidate schema)

- [ ] **Step 2: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test`
Expected: ALL PASS across all modules

- [ ] **Step 3: Commit**

```bash
git add memory-cbr-jpa/
git commit -m "feat(memory-cbr-jpa): cross-type retrieval support Refs #288"
```

- [ ] **Step 4: Final verification — full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

## References

- [2026-09-07-cross-type-cbr-query-design.md] — design spec this plan implements
- [decisions.md] — D1-D5 decision records
- [CbrQuery.java:10-169] — CbrQuery record (caseType field, requireNonNull, factories)
- [ScoredCbrCase.java:7-48] — ScoredCbrCase record (no caseType field currently)
- [InMemoryCbrCaseMemoryStore.java:80-163] — retrieveSimilar with caseType filter
- [QdrantCbrCaseMemoryStore.java:208-238] — retrieveSimilar with collection routing
- [CbrCollectionManager.java:49-51] — collectionName prefix scheme
- [CbrQueryTranslator.java:35-60] — toIdentityFilter with caseType match
- [TrendEnrichmentCbrCaseMemoryStore.java:54-64] — retrieveSimilar schema lookup
- [RerankingCbrCaseMemoryStore.java:58-63] — overfetch query construction
- [SqliteCbrRetrievalTracker.java:128,199] — caseType serialization
- [JpaCbrCaseMemoryStore.java:111-134] — JPA retrieveSimilar with caseType query
- [CbrCaseMemoryStoreContractTest] — 164 existing contract tests
- [#288] — focal issue
- [engine#1055] — blocked: cross-case-type CBR retrieval
- [engine#1054] — blocked: case definition selection
