# Batch S/XS CBR Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #130 — Add aggregator POM to examples/
**Issue group:** #130, #143, #128, #162, #141, #155

**Goal:** Six S/XS fixes to CBR infrastructure that unblock CaseHub app adoption — configurable learning rate, structured field scoring overrides, test isolation, JPA cleanup, supersession queries, and examples aggregation.

**Architecture:** All changes are in `memory-api` (SPI types), concrete store implementations (`memory-cbr-inmem`, `memory-cbr-jpa`, `memory-qdrant`), decorators (`memory/`), `memory-testing` (contract tests), and `examples/` (build). Changes propagate to all `CbrCaseMemoryStore` implementations via compile-time enforcement.

**Tech Stack:** Java 21, Quarkus 3.32.2, JUnit 5, AssertJ, Jackson, JPQL

## Global Constraints

- Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build: `mvn` not `./mvnw`
- Pre-release: breaking changes are acceptable
- IntelliJ MCP mandatory for all .java edits
- Every commit references an issue
- TDD: failing test → implement → verify

---

### Task 1: Examples aggregator POM (#130)

**Files:**
- Create: `examples/pom.xml`

**Interfaces:**
- Consumes: nothing
- Produces: aggregator POM enabling `<module>neocortex-examples</module>` in casehub-examples

- [ ] **Step 1: Create the aggregator POM**

Use `ide_create_file` (or Write since it's XML, not Java):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>0.2-SNAPSHOT</version>
        <relativePath>../pom.xml</relativePath>
    </parent>

    <artifactId>casehub-neocortex-examples</artifactId>
    <packaging>pom</packaging>
    <name>casehub-neocortex-examples</name>

    <modules>
        <module>example-text-analysis</module>
        <module>example-rag-pipeline</module>
        <module>example-cbr</module>
    </modules>
</project>
```

- [ ] **Step 2: Verify the aggregator builds**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -pl examples -DskipTests validate`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add examples/pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#130): examples aggregator POM for casehub-examples integration"
```

- [ ] **Step 4: File follow-up issue on casehub-examples**

```bash
gh issue create --repo casehubio/examples --title "refactor: collapse neocortex individual example entries into single aggregator module" --body "neocortex now has \`examples/pom.xml\` (casehubio/neocortex#130). Replace the three individual \`<module>\` entries with a single \`<module>neocortex-examples</module>\` entry."
```

---

### Task 2: Configurable learning rate per case type (#143)

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureSchema.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureSchemaTest.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/ReactiveQdrantCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Consumes: `CbrFeatureSchema(String caseType, List<FeatureField> fields)` (current)
- Produces: `CbrFeatureSchema(String caseType, List<FeatureField> fields, Double learningRate)` with `of(String caseType, FeatureField... fields)` preserving null learningRate default

- [ ] **Step 1: Write the failing test for CbrFeatureSchema.learningRate**

Add to `CbrFeatureSchemaTest.java`:

```java
@Test
void learningRate_defaultsToNull() {
    var schema = CbrFeatureSchema.of("test", FeatureField.categorical("cat"));
    assertThat(schema.learningRate()).isNull();
}

@Test
void learningRate_customValue() {
    var schema = new CbrFeatureSchema("test",
            List.of(FeatureField.categorical("cat")), 0.5);
    assertThat(schema.learningRate()).isEqualTo(0.5);
}

@Test
void learningRate_rejectsOutOfRange() {
    assertThatThrownBy(() -> new CbrFeatureSchema("test",
            List.of(FeatureField.categorical("cat")), 1.5))
            .isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new CbrFeatureSchema("test",
            List.of(FeatureField.categorical("cat")), -0.1))
            .isInstanceOf(IllegalArgumentException.class);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrFeatureSchemaTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — `learningRate()` method does not exist

- [ ] **Step 3: Add learningRate field to CbrFeatureSchema**

Use `ide_edit_member` to replace the record declaration:

```java
public record CbrFeatureSchema(String caseType, List<FeatureField> fields, Double learningRate) {
    public CbrFeatureSchema {
        Objects.requireNonNull(caseType, "caseType required");
        if (caseType.isBlank()) throw new IllegalArgumentException("caseType must not be blank");
        Objects.requireNonNull(fields, "fields required");
        if (learningRate != null && (learningRate < 0.0 || learningRate > 1.0))
            throw new IllegalArgumentException("learningRate must be in [0,1], got: " + learningRate);
        fields = List.copyOf(fields);
        Set<String> names = new HashSet<>();
        for (FeatureField f : fields) {
            if (!names.add(f.name()))
                throw new IllegalArgumentException("Duplicate field name: '" + f.name() + "'");
        }
    }

    public static CbrFeatureSchema of(String caseType, FeatureField... fields) {
        return new CbrFeatureSchema(caseType, List.of(fields), null);
    }
}
```

- [ ] **Step 4: Run CbrFeatureSchemaTest to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrFeatureSchemaTest`
Expected: PASS

- [ ] **Step 5: Fix compilation in all call sites using the 2-arg constructor**

Search for `new CbrFeatureSchema(` across the codebase — any call using the old 2-arg constructor needs the third `null` parameter. The `of()` factory already handles this.

Use `ide_search_text` to find: `new CbrFeatureSchema(`
For each hit, use `ide_replace_text_in_file` to add `, null` before the closing `)`.

The `TrendAnalyzer.expandSchema()` method creates `new CbrFeatureSchema(schema.caseType(), expanded)` — update to `new CbrFeatureSchema(schema.caseType(), expanded, schema.learningRate())` to preserve the learning rate through schema expansion.

- [ ] **Step 6: Write the contract test for configurable learning rate**

Add to `CbrCaseMemoryStoreContractTest.java`:

```java
@Test
void recordOutcome_customLearningRate() {
    var schema = new CbrFeatureSchema("fast-learn",
            List.of(FeatureField.categorical("cat"), FeatureField.numeric("val", 0, 100)),
            0.8);
    store().registerSchema(schema);

    var cbrCase = new FeatureVectorCbrCase("p", "s", "o", 1.0,
            Map.of("cat", string("a"), "val", number(50)));
    String caseId = store().store(cbrCase, "fast-learn", ENTITY, CBR, TENANT, "c1", Path.root());

    store().recordOutcome(caseId, TENANT, CbrOutcome.of(0.0, "fail", Instant.now()));

    var results = store().retrieveSimilar(
            CbrQuery.of(TENANT, CBR, Path.root(), "fast-learn",
                    Map.of("cat", string("a"), "val", number(50)), 10),
            FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    // With learning rate 0.8: confidence = (1-0.8)*1.0 + 0.8*0.0 = 0.2
    // With default 0.2: confidence = (1-0.2)*1.0 + 0.2*0.0 = 0.8
    // The fast learner should have much lower confidence
    assertThat(results.getFirst().cbrCase().confidence()).isCloseTo(0.2, within(0.01));
}
```

- [ ] **Step 7: Implement learning rate lookup in InMemoryCbrCaseMemoryStore.recordOutcome()**

In `InMemoryCbrCaseMemoryStore.recordOutcome()`, look up the schema for the case's caseType and use its learning rate:

Find the line that calls `CbrOutcome.adjustConfidence` and change the learning rate from `CbrOutcome.DEFAULT_LEARNING_RATE` to:

```java
CbrFeatureSchema schema = schemas.get(stored.caseType());
double lr = (schema != null && schema.learningRate() != null)
            ? schema.learningRate() : CbrOutcome.DEFAULT_LEARNING_RATE;
double newConf = CbrOutcome.adjustConfidence(current.cbrCase().confidence(),
                                              outcome.successRate(), lr);
```

- [ ] **Step 8: Implement learning rate lookup in JpaCbrCaseMemoryStore.recordOutcome()**

Same pattern — look up `schemas.get(entity.caseType)` and use `schema.learningRate()` if non-null.

- [ ] **Step 9: Implement learning rate lookup in ReactiveQdrantCbrCaseMemoryStore**

Same pattern in the reactive store's `recordOutcome()`.

- [ ] **Step 10: Run full contract test + build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Then: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory-cbr-inmem,memory-testing`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 11: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#143): configurable learning rate per case type on CbrFeatureSchema"
```

---

### Task 3: Graded similarity scoring for structured fields (#128)

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java`

**Interfaces:**
- Consumes: `CbrSimilarityScorer.scoreDetailed()`, `LocalSimilarityFunction`
- Produces: `scoreDetailed()` now respects caller overrides for structured fields

- [ ] **Step 1: Write the failing test**

Add to `CbrSimilarityScorerTest.java`:

```java
@Test
void structuredField_overrideRespected() {
    var schema = CbrFeatureSchema.of("test",
            FeatureField.categorical("cat"),
            FeatureField.categoricalList("tags",
                    List.of(FeatureField.categorical("inner"))));

    var query = Map.of("cat", string("a"),
                       "tags", stringList("x", "y", "z"));
    var caseF = Map.of("cat", string("a"),
                       "tags", stringList("x", "y"));

    // Without override: structured field is skipped, score based on "cat" only
    double scoreWithout = CbrSimilarityScorer.score(query, caseF,
            Map.of("cat", 1.0, "tags", 1.0), schema);
    assertThat(scoreWithout).isEqualTo(1.0); // only "cat" contributes

    // With override: structured field participates via custom function
    LocalSimilarityFunction jaccardLike = (q, c) -> {
        if (q instanceof FeatureValue.StringListVal ql
            && c instanceof FeatureValue.StringListVal cl) {
            long intersection = ql.values().stream().filter(cl.values()::contains).count();
            long union = (long) new java.util.HashSet<>(ql.values()) {{
                addAll(cl.values());
            }}.size();
            return union == 0 ? 1.0 : (double) intersection / union;
        }
        return 0.0;
    };

    double scoreWith = CbrSimilarityScorer.score(query, caseF,
            Map.of("cat", 1.0, "tags", 1.0), schema,
            Map.of("tags", jaccardLike));
    // Jaccard of {x,y,z} vs {x,y} = 2/3 ≈ 0.667
    // Weighted: (1.0*1.0 + 1.0*0.667) / 2.0 ≈ 0.833
    assertThat(scoreWith).isCloseTo(0.833, within(0.01));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest#structuredField_overrideRespected`
Expected: FAIL — structured field is skipped, score is 1.0 for both

- [ ] **Step 3: Move structured-field skip after override check in scoreDetailed() (first overload)**

In `CbrSimilarityScorer.scoreDetailed()` (the 5-arg overload, ~line 56), change the loop body. Current code skips structured fields unconditionally at lines 68-71. Move the skip to after checking for an override:

```java
for (Map.Entry<String, FeatureValue> entry : queryFeatures.entrySet()) {
    FeatureField field = findField(schema, entry.getKey());
    if (field == null) {continue;}

    // Check for caller override BEFORE structured-field skip
    LocalSimilarityFunction override = overrides.get(entry.getKey());
    if (override == null
        && (field instanceof FeatureField.CategoricalList
            || field instanceof FeatureField.NumericList
            || field instanceof FeatureField.NestedObject
            || field instanceof FeatureField.ObjectList)) {continue;}

    double       weight    = weights.getOrDefault(entry.getKey(), 1.0);
    FeatureValue caseValue = caseFeatures.get(entry.getKey());
    double localSim = caseValue == null ? 0.0
                                        : localSimilarity(field, entry.getValue(), caseValue, overrides);

    double contribution = weight * localSim;
    weightedSum += contribution;
    totalWeight += weight;
    rawContributions.put(entry.getKey(), contribution);
}
```

- [ ] **Step 4: Same change in the 6-arg overload (with dtwAbandonCostThreshold)**

Apply the identical refactor to the second `scoreDetailed()` overload (~line 94).

- [ ] **Step 5: Change structured-field throws to return 0.0 in localSimilarity()**

In `localSimilarity()` (~line 143), change the four structured field cases from `throw new IllegalStateException(...)` to `return 0.0`:

```java
case FeatureField.CategoricalList cl -> 0.0;
case FeatureField.NumericList nl -> 0.0;
case FeatureField.NestedObject no -> 0.0;
case FeatureField.ObjectList ol -> 0.0;
```

- [ ] **Step 6: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrSimilarityScorerTest`
Expected: PASS (all existing tests + new test)

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#128): allow LocalSimilarityFunction overrides for structured CBR fields"
```

---

### Task 4: InMemoryCbrCaseMemoryStore.clearCases() (#162)

**Files:**
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/ReactiveInMemoryCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Test: `memory-cbr-inmem/src/test/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStoreTest.java` (may need creation)

**Interfaces:**
- Consumes: `InMemoryCbrCaseMemoryStore` (concrete class)
- Produces: `clearCases()` method on concrete stores, `clearStore()` hook in contract test

- [ ] **Step 1: Write the failing test**

Create or add to `InMemoryCbrCaseMemoryStoreTest.java`:

```java
@Test
void clearCases_removesAllCases_preservesSchemas() {
    var store = new InMemoryCbrCaseMemoryStore();
    var schema = CbrFeatureSchema.of("test", FeatureField.categorical("cat"));
    store.registerSchema(schema);

    store.store(new FeatureVectorCbrCase("p", "s", "o", 1.0,
            Map.of("cat", FeatureValue.string("a"))),
            "test", "e1", new MemoryDomain("cbr"), "t1", "c1", Path.root());

    assertThat(store.retrieveSimilar(
            CbrQuery.of("t1", new MemoryDomain("cbr"), Path.root(), "test",
                    Map.of("cat", FeatureValue.string("a")), 10),
            FeatureVectorCbrCase.class)).hasSize(1);

    store.clearCases();

    // Cases cleared
    assertThat(store.retrieveSimilar(
            CbrQuery.of("t1", new MemoryDomain("cbr"), Path.root(), "test",
                    Map.of("cat", FeatureValue.string("a")), 10),
            FeatureVectorCbrCase.class)).isEmpty();

    // Schema preserved — can still store and retrieve
    store.store(new FeatureVectorCbrCase("p2", "s2", "o2", 1.0,
            Map.of("cat", FeatureValue.string("b"))),
            "test", "e2", new MemoryDomain("cbr"), "t1", "c2", Path.root());
    assertThat(store.retrieveSimilar(
            CbrQuery.of("t1", new MemoryDomain("cbr"), Path.root(), "test",
                    Map.of("cat", FeatureValue.string("b")), 10),
            FeatureVectorCbrCase.class)).hasSize(1);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -Dtest=InMemoryCbrCaseMemoryStoreTest#clearCases_removesAllCases_preservesSchemas`
Expected: FAIL — `clearCases()` does not exist

- [ ] **Step 3: Add clearCases() to InMemoryCbrCaseMemoryStore**

Use `ide_insert_member` to add after the `registerSchema` method:

```java
public void clearCases() {
    cases.clear();
}
```

- [ ] **Step 4: Add clearCases() to ReactiveInMemoryCbrCaseMemoryStore**

Same — add `clearCases()` that clears its internal cases list.

- [ ] **Step 5: Add clearStore() hook to CbrCaseMemoryStoreContractTest**

Use `ide_insert_member` to add a protected method:

```java
protected void clearStore() {}
```

Then find the `@BeforeEach` method and add `clearStore();` as the first line. If no `@BeforeEach` exists, add one:

```java
@BeforeEach
void clearBeforeEach() {
    clearStore();
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem,memory-testing`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#162): add clearCases() to InMemoryCbrCaseMemoryStore for test isolation"
```

---

### Task 5: JPA Map→FeatureValue cleanup (#141)

**Files:**
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `FeatureValue.toFeatureMap(Map<String, Object>)`
- Produces: cleaner internal API — `deserializeFeatures()` returns `Map<String, FeatureValue>` directly

- [ ] **Step 1: Verify existing tests pass before refactoring**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-jpa`
Expected: PASS (or skip if no standalone tests — contract test covers via Testcontainers)

- [ ] **Step 2: Rename deserializeMap → deserializeFeatures and change return type**

Use `ide_edit_member` to replace `deserializeMap`:

```java
private Map<String, FeatureValue> deserializeFeatures(String json) {
    if (json == null || json.isBlank()) {return Map.of();}
    try {
        Map<String, Object> raw = objectMapper.readValue(json, MAP_TYPE);
        return FeatureValue.toFeatureMap(raw);
    } catch (JsonProcessingException e) {
        throw new IllegalStateException("Failed to deserialize features JSON", e);
    }
}
```

- [ ] **Step 3: Update reconstruct() to use deserializeFeatures()**

Change the first line of `reconstruct()` from:
```java
Map<String, FeatureValue> features = FeatureValue.toFeatureMap(deserializeMap(entity.features));
```
to:
```java
Map<String, FeatureValue> features = deserializeFeatures(entity.features);
```

- [ ] **Step 4: Remove the MAP_TYPE field if no other method uses it**

Check if `MAP_TYPE` is used elsewhere. If `deserializeFeatures` is the only consumer, remove:
```java
private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {};
```
and inline the TypeReference inside `deserializeFeatures`.

- [ ] **Step 5: Verify with ide_diagnostics**

Run `ide_diagnostics` on the file to confirm no compilation errors.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor(#141): internalize FeatureValue conversion in JPA deserialize path"
```

---

### Task 6: Supersession status + audit metadata SPI (#155)

This is the largest task — touches every `CbrCaseMemoryStore` implementation. Split into sub-steps.

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/SupersessionStatus.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ReactiveCbrCaseMemoryStore.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/ReactiveInMemoryCbrCaseMemoryStore.java`
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java`
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/CbrCaseEntity.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/ReactiveQdrantCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpCbrCaseMemoryStore.java`
- Modify: all 7 blocking decorators in `memory/` — delegation override
- Modify: all 7 reactive decorators in `memory/`, `memory-cbr-crossencoder/`, `memory-cbr-tracking/` — delegation override
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/BlockingToReactiveCbrBridge.java` — Uni wrapping
- Modify: all ~20 test stubs implementing `CbrCaseMemoryStore` — one-liner no-op returns
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Modify: `memory-cbr-inmem/.../InMemoryCbrCaseMemoryStore.java` `StoredCase` record — add `reinstatedAt`

**Interfaces:**
- Consumes: `CbrCaseMemoryStore.supersede()`, `CbrCaseMemoryStore.reinstate()`
- Produces: `SupersessionStatus` record, `getSupersessionStatus(String caseId, String tenantId)`, `findSupersededCases(String tenantId, MemoryDomain domain)`

- [ ] **Step 1: Create SupersessionStatus value type**

Use `ide_create_file`:

```java
package io.casehub.neocortex.memory.cbr;

import java.time.Instant;

public record SupersessionStatus(
    String caseId,
    boolean superseded,
    Instant supersededAt,
    String supersedingCaseId,
    String reason,
    Instant reinstatedAt
) {
    public static final SupersessionStatus NOT_SUPERSEDED =
        new SupersessionStatus(null, false, null, null, null, null);

    public boolean wasReinstated() { return reinstatedAt != null; }
}
```

- [ ] **Step 2: Add abstract methods to CbrCaseMemoryStore interface**

Use `ide_insert_member` to add after `reinstate()`:

```java
SupersessionStatus getSupersessionStatus(String caseId, String tenantId);

List<SupersessionStatus> findSupersededCases(String tenantId, MemoryDomain domain);
```

Add `import java.util.List;` if not already present.

- [ ] **Step 3: Add abstract methods to ReactiveCbrCaseMemoryStore interface**

Use `ide_insert_member` to add after `reinstate()`:

```java
Uni<SupersessionStatus> getSupersessionStatus(String caseId, String tenantId);

Uni<List<SupersessionStatus>> findSupersededCases(String tenantId, MemoryDomain domain);
```

- [ ] **Step 4: Build to identify all compilation failures**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests 2>&1 | grep "error:" | head -50`

This gives the exact list of files that need the two new methods. Work through them systematically.

- [ ] **Step 5: Add reinstatedAt to InMemoryCbrCaseMemoryStore.StoredCase**

The `StoredCase` record needs a `reinstatedAt` field. Update the record declaration and the constructor call in `store()` (pass `null`). Update `supersede()` to null `reinstatedAt`. Update `reinstate()` to set `reinstatedAt = Instant.now()`.

- [ ] **Step 6: Implement getSupersessionStatus in InMemoryCbrCaseMemoryStore**

```java
@Override
public SupersessionStatus getSupersessionStatus(String caseId, String tenantId) {
    java.util.Objects.requireNonNull(caseId, "caseId required");
    java.util.Objects.requireNonNull(tenantId, "tenantId required");
    for (StoredCase stored : cases) {
        if (stored.caseId().equals(caseId) && stored.tenantId().equals(tenantId)) {
            if (stored.supersededAt() != null) {
                return new SupersessionStatus(caseId, true, stored.supersededAt(),
                        stored.supersedingCaseId(), stored.supersessionReason(), stored.reinstatedAt());
            }
            return new SupersessionStatus(caseId, false, null, null, null, stored.reinstatedAt());
        }
    }
    return SupersessionStatus.NOT_SUPERSEDED;
}
```

- [ ] **Step 7: Implement findSupersededCases in InMemoryCbrCaseMemoryStore**

```java
@Override
public List<SupersessionStatus> findSupersededCases(String tenantId, MemoryDomain domain) {
    java.util.Objects.requireNonNull(tenantId, "tenantId required");
    java.util.Objects.requireNonNull(domain, "domain required");
    List<SupersessionStatus> result = new ArrayList<>();
    for (StoredCase stored : cases) {
        if (stored.tenantId().equals(tenantId) && stored.domain().equals(domain)
                && stored.supersededAt() != null) {
            result.add(new SupersessionStatus(stored.caseId(), true, stored.supersededAt(),
                    stored.supersedingCaseId(), stored.supersessionReason(), stored.reinstatedAt()));
        }
    }
    return Collections.unmodifiableList(result);
}
```

- [ ] **Step 8: Implement in ReactiveInMemoryCbrCaseMemoryStore**

Wrap the blocking implementations in `Uni.createFrom().item(...)`.

- [ ] **Step 9: Implement in JpaCbrCaseMemoryStore**

Add `reinstated_at` column to `CbrCaseEntity`. Implement `getSupersessionStatus` with JPQL query. Implement `findSupersededCases` with JPQL `WHERE e.supersededAt IS NOT NULL AND e.tenantId = :t AND e.domain = :d`. Update `supersede()` to null `reinstatedAt`. Update `reinstate()` to set `reinstatedAt`.

- [ ] **Step 10: Implement in QdrantCbrCaseMemoryStore and ReactiveQdrantCbrCaseMemoryStore**

Implement using payload queries. Add `reinstatedAt` to payload upserts. Update `supersede()` and `reinstate()`.

- [ ] **Step 11: Implement in NoOpCbrCaseMemoryStore**

```java
@Override
public SupersessionStatus getSupersessionStatus(String caseId, String tenantId) {
    return SupersessionStatus.NOT_SUPERSEDED;
}

@Override
public List<SupersessionStatus> findSupersededCases(String tenantId, MemoryDomain domain) {
    return List.of();
}
```

- [ ] **Step 12: Add delegation to all 7 blocking decorators**

For each decorator, add:

```java
@Override
public SupersessionStatus getSupersessionStatus(String caseId, String tenantId) {
    return delegate.getSupersessionStatus(caseId, tenantId);
}

@Override
public List<SupersessionStatus> findSupersededCases(String tenantId, MemoryDomain domain) {
    return delegate.findSupersededCases(tenantId, domain);
}
```

Decorators: `TemporalDecayCbrCaseMemoryStore`, `ScopeDecayCbrCaseMemoryStore`, `OutcomeWeightingCbrCaseMemoryStore`, `TrendEnrichmentCbrCaseMemoryStore`, `TrackingCbrCaseMemoryStore`, `ErasureNotificationCbrCaseMemoryStore`, `RerankingCbrCaseMemoryStore`.

- [ ] **Step 13: Add delegation to all 7 reactive decorators + bridge**

Same pattern with `Uni<>` return types. Plus `BlockingToReactiveCbrBridge` wraps the blocking call.

- [ ] **Step 14: Fix all test stubs**

For each test stub implementing `CbrCaseMemoryStore`, add the two methods returning `SupersessionStatus.NOT_SUPERSEDED` and `List.of()`.

Use `ide_build_project` to find remaining compilation errors, fix iteratively.

- [ ] **Step 15: Write contract tests**

Add to `CbrCaseMemoryStoreContractTest.java`:

```java
@Test
void getSupersessionStatus_notSuperseded() {
    registerDefaultSchema();
    String caseId = storeDefaultCase();
    var status = store().getSupersessionStatus(caseId, TENANT);
    assertThat(status.superseded()).isFalse();
    assertThat(status.caseId()).isEqualTo(caseId);
    assertThat(status.wasReinstated()).isFalse();
}

@Test
void getSupersessionStatus_afterSupersede() {
    registerDefaultSchema();
    String caseId = storeDefaultCase();
    store().supersede(caseId, TENANT, "new-case", "better data");
    var status = store().getSupersessionStatus(caseId, TENANT);
    assertThat(status.superseded()).isTrue();
    assertThat(status.supersedingCaseId()).isEqualTo("new-case");
    assertThat(status.reason()).isEqualTo("better data");
    assertThat(status.supersededAt()).isNotNull();
    assertThat(status.wasReinstated()).isFalse();
}

@Test
void getSupersessionStatus_afterReinstate() {
    registerDefaultSchema();
    String caseId = storeDefaultCase();
    store().supersede(caseId, TENANT, "new-case", "better data");
    store().reinstate(caseId, TENANT);
    var status = store().getSupersessionStatus(caseId, TENANT);
    assertThat(status.superseded()).isFalse();
    assertThat(status.reinstatedAt()).isNotNull();
    assertThat(status.wasReinstated()).isTrue();
}

@Test
void getSupersessionStatus_reSupersede_clearsReinstatedAt() {
    registerDefaultSchema();
    String caseId = storeDefaultCase();
    store().supersede(caseId, TENANT, "case-a", "first");
    store().reinstate(caseId, TENANT);
    store().supersede(caseId, TENANT, "case-b", "second");
    var status = store().getSupersessionStatus(caseId, TENANT);
    assertThat(status.superseded()).isTrue();
    assertThat(status.supersedingCaseId()).isEqualTo("case-b");
    assertThat(status.wasReinstated()).isFalse();
}

@Test
void findSupersededCases_filtersCorrectly() {
    registerDefaultSchema();
    String c1 = storeDefaultCase();
    String c2 = storeDefaultCase();
    store().supersede(c1, TENANT, "new", "reason");
    var superseded = store().findSupersededCases(TENANT, CBR);
    assertThat(superseded).hasSize(1);
    assertThat(superseded.getFirst().caseId()).isEqualTo(c1);
    assertThat(superseded.getFirst().superseded()).isTrue();
}
```

- [ ] **Step 16: Run full build and all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 17: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#155): supersession status and audit metadata SPI methods on CbrCaseMemoryStore"
```

---

## Post-implementation

- [ ] Update `docs/repos/casehub-neocortex.md` in parent repo (file issue if cross-repo commit not allowed)
- [ ] Run `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install` for full green build
- [ ] Invoke work-end
