# Semantic Text Field Similarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #106 — feat: semantic text field similarity in CbrSimilarityScorer
**Issue group:** #106

**Goal:** Make text field similarity pluggable in the CBR scorer, with an embedding-based implementation for semantic matching.

**Architecture:** Add `LocalSimilarityFunction` functional interface to `memory-api`. Extend `CbrSimilarityScorer.score()` with a per-field override map. Add `semantic` flag to `FeatureField.Text` for opt-in. Create `memory-cbr-embedding` module with `EmbeddingTextSimilarity` (batch `precompute()` + cosine similarity). Wire into both store implementations.

**Tech Stack:** Java 21, LangChain4j 1.14.1 (`EmbeddingModel`, `CosineSimilarity`), Quarkus CDI

## Global Constraints

- Java 21 source level, Java 26 JVM
- `memory-api` is Tier 1: pure Java, zero external dependencies
- `memory-cbr-embedding` new module: depends on `memory-api` + `langchain4j-core` only
- `LocalSimilarityFunction.compute()` returns `double` in [0, 1]
- Fail-fast on embedding failures — no silent fallback
- All SPI implementations updated in same commit when signatures change
- Use `mvn` not `./mvnw`
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`

---

### Task 1: `LocalSimilarityFunction` interface + `FeatureField.Text` semantic flag + scorer override

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/LocalSimilarityFunction.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureField.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/FeatureFieldTest.java`

**Interfaces:**
- Consumes: nothing (foundational task)
- Produces:
  - `LocalSimilarityFunction` — `@FunctionalInterface`, method `double compute(Object queryValue, Object caseValue)`, constant `EXACT_MATCH`
  - `FeatureField.Text(String name, boolean semantic)` — second component `semantic`, default `false`
  - `FeatureField.semanticText(String name)` — factory returning `new Text(name, true)`
  - `CbrSimilarityScorer.score(Map, Map, Map, CbrFeatureSchema, Map<String, LocalSimilarityFunction>)` — 5-arg overload

- [ ] **Step 1: Write failing tests for `LocalSimilarityFunction`**

Add to `CbrSimilarityScorerTest.java`:

```java
@Test
void overrideReplacesDefaultTextBehavior() {
    LocalSimilarityFunction prefixMatch = (q, c) ->
        ((String) c).startsWith((String) q) ? 1.0 : 0.0;

    double sim = CbrSimilarityScorer.score(
        Map.of("label", "hel"),
        Map.of("label", "hello world"),
        Map.of(),
        SCHEMA,
        Map.of("label", prefixMatch));
    assertThat(sim).isEqualTo(1.0);
}

@Test
void overrideForOneFieldDefaultForOthers() {
    LocalSimilarityFunction always1 = (q, c) -> 1.0;

    double sim = CbrSimilarityScorer.score(
        Map.of("color", "red", "label", "a"),
        Map.of("color", "blue", "label", "b"),
        Map.of(),
        SCHEMA,
        Map.of("label", always1));
    // color: exact match miss = 0.0, label: override = 1.0
    // (0.0 + 1.0) / 2 = 0.5
    assertThat(sim).isCloseTo(0.5, org.assertj.core.data.Offset.offset(1e-9));
}

@Test
void emptyOverridesPreservesExistingBehavior() {
    double sim = CbrSimilarityScorer.score(
        Map.of("label", "hello"),
        Map.of("label", "hello"),
        Map.of(),
        SCHEMA,
        Map.of());
    assertThat(sim).isEqualTo(1.0);
}
```

- [ ] **Step 2: Write failing tests for `FeatureField.Text` semantic flag**

Add to `FeatureFieldTest.java`:

```java
@Test
void textDefaultIsNotSemantic() {
    var f = FeatureField.text("desc");
    assertThat(f).isInstanceOf(FeatureField.Text.class);
    assertThat(((FeatureField.Text) f).semantic()).isFalse();
}

@Test
void semanticTextIsSemantic() {
    var f = FeatureField.semanticText("desc");
    assertThat(f).isInstanceOf(FeatureField.Text.class);
    assertThat(((FeatureField.Text) f).semantic()).isTrue();
}

@Test
void textAndSemanticTextWithSameNameAreNotEqual() {
    var exact = FeatureField.text("desc");
    var semantic = FeatureField.semanticText("desc");
    assertThat(exact).isNotEqualTo(semantic);
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="CbrSimilarityScorerTest,FeatureFieldTest" -DfailIfNoTests=false`
Expected: FAIL — `LocalSimilarityFunction` not found, `semanticText` method not found, 5-arg `score()` not found

- [ ] **Step 4: Create `LocalSimilarityFunction.java`**

```java
package io.casehub.neocortex.memory.cbr;

@FunctionalInterface
public interface LocalSimilarityFunction {
    double compute(Object queryValue, Object caseValue);

    LocalSimilarityFunction EXACT_MATCH = (q, c) -> q.equals(c) ? 1.0 : 0.0;
}
```

- [ ] **Step 5: Modify `FeatureField.Text` to add `semantic` flag**

Change the `Text` record from:
```java
record Text(String name) implements FeatureField {
    public Text { Objects.requireNonNull(name, "name"); }
}
```
To:
```java
record Text(String name, boolean semantic) implements FeatureField {
    public Text { Objects.requireNonNull(name, "name"); }
    public Text(String name) { this(name, false); }
}
```

Add the `semanticText` factory method to the `FeatureField` interface:
```java
static FeatureField semanticText(String name) { return new Text(name, true); }
```

- [ ] **Step 6: Add 5-arg `score()` overload to `CbrSimilarityScorer`**

Add the new overload and make the existing 4-arg delegate to it:

```java
public static double score(Map<String, Object> queryFeatures,
                           Map<String, Object> caseFeatures,
                           Map<String, Double> weights,
                           CbrFeatureSchema schema) {
    return score(queryFeatures, caseFeatures, weights, schema, Map.of());
}

public static double score(Map<String, Object> queryFeatures,
                           Map<String, Object> caseFeatures,
                           Map<String, Double> weights,
                           CbrFeatureSchema schema,
                           Map<String, LocalSimilarityFunction> overrides) {
    if (queryFeatures.isEmpty()) return 1.0;
    if (schema == null) return 1.0;

    double weightedSum = 0.0;
    double totalWeight = 0.0;

    for (Map.Entry<String, Object> entry : queryFeatures.entrySet()) {
        FeatureField field = findField(schema, entry.getKey());
        if (field == null) continue;

        double weight = weights.getOrDefault(entry.getKey(), 1.0);
        Object caseValue = caseFeatures.get(entry.getKey());
        double localSim = caseValue == null ? 0.0
            : localSimilarity(field, entry.getValue(), caseValue, overrides);

        weightedSum += weight * localSim;
        totalWeight += weight;
    }

    return totalWeight > 0 ? weightedSum / totalWeight : 1.0;
}
```

Update `localSimilarity` to accept and check overrides:

```java
private static double localSimilarity(FeatureField field, Object queryVal, Object caseVal,
                                       Map<String, LocalSimilarityFunction> overrides) {
    LocalSimilarityFunction override = overrides.get(field.name());
    if (override != null) return override.compute(queryVal, caseVal);

    if (field instanceof FeatureField.Numeric n) {
        return numericSimilarity(n, queryVal, caseVal);
    }
    return queryVal.equals(caseVal) ? 1.0 : 0.0;
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="CbrSimilarityScorerTest,FeatureFieldTest" -DfailIfNoTests=false`
Expected: ALL PASS

- [ ] **Step 8: Run full memory-api test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api`
Expected: ALL PASS (existing tests use 4-arg `score()` which delegates to 5-arg)

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/LocalSimilarityFunction.java memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureField.java memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/FeatureFieldTest.java
```

Message: `feat(#106): LocalSimilarityFunction SPI, FeatureField.Text semantic flag, scorer override map`

---

### Task 2: `memory-cbr-embedding` module with `EmbeddingTextSimilarity`

**Files:**
- Create: `memory-cbr-embedding/pom.xml`
- Create: `memory-cbr-embedding/src/main/java/io/casehub/neocortex/memory/cbr/embedding/EmbeddingTextSimilarity.java`
- Create: `memory-cbr-embedding/src/test/java/io/casehub/neocortex/memory/cbr/embedding/EmbeddingTextSimilarityTest.java`
- Modify: `pom.xml` (parent — add module + dependency management)

**Interfaces:**
- Consumes: `LocalSimilarityFunction` from Task 1
- Produces:
  - `EmbeddingTextSimilarity` — implements `LocalSimilarityFunction`, constructor `(EmbeddingModel model)`, method `void precompute(List<String> texts)`

- [ ] **Step 1: Create `memory-cbr-embedding/pom.xml`**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-neocortex-memory-cbr-embedding</artifactId>
  <name>CaseHub Neocortex - Memory CBR Embedding</name>
  <description>EmbeddingModel-based LocalSimilarityFunction for semantic text field similarity in CBR.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-api</artifactId>
    </dependency>
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j-core</artifactId>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 2: Add module to parent POM**

In `pom.xml` (root), add `<module>memory-cbr-embedding</module>` after `<module>memory-cbr-inmem</module>` in the `<modules>` section.

Add dependency management entry in the `<dependencyManagement><dependencies>` section:
```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-memory-cbr-embedding</artifactId>
  <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Write failing tests for `EmbeddingTextSimilarity`**

Create `memory-cbr-embedding/src/test/java/io/casehub/neocortex/memory/cbr/embedding/EmbeddingTextSimilarityTest.java`:

```java
package io.casehub.neocortex.memory.cbr.embedding;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import org.junit.jupiter.api.Test;
import java.util.List;

import static org.assertj.core.api.Assertions.*;

class EmbeddingTextSimilarityTest {

    static EmbeddingModel stubModel() {
        return new EmbeddingModel() {
            @Override
            public Response<Embedding> embed(TextSegment segment) {
                return Response.from(vectorFor(segment.text()));
            }

            @Override
            public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
                return Response.from(segments.stream()
                    .map(s -> vectorFor(s.text())).toList());
            }

            @Override
            public int dimension() { return 3; }

            private Embedding vectorFor(String text) {
                return switch (text) {
                    case "hello" -> Embedding.from(new float[]{1.0f, 0.0f, 0.0f});
                    case "hi" -> Embedding.from(new float[]{0.9f, 0.1f, 0.0f});
                    case "goodbye" -> Embedding.from(new float[]{0.0f, 1.0f, 0.0f});
                    default -> Embedding.from(new float[]{0.0f, 0.0f, 1.0f});
                };
            }
        };
    }

    @Test
    void identicalTextsScoreOne() {
        var sim = new EmbeddingTextSimilarity(stubModel());
        assertThat(sim.compute("hello", "hello")).isEqualTo(1.0);
    }

    @Test
    void similarTextsScoreHighButNotOne() {
        var sim = new EmbeddingTextSimilarity(stubModel());
        double score = sim.compute("hello", "hi");
        // cos(hello, hi) = (0.9)/sqrt(1*0.82) ≈ 0.9938
        assertThat(score).isGreaterThan(0.9);
        assertThat(score).isLessThan(1.0);
    }

    @Test
    void dissimilarTextsScoreLow() {
        var sim = new EmbeddingTextSimilarity(stubModel());
        double score = sim.compute("hello", "goodbye");
        // cos([1,0,0], [0,1,0]) = 0.0
        assertThat(score).isCloseTo(0.0, offset(1e-6));
    }

    @Test
    void negativeCosineClampedToZero() {
        EmbeddingModel negModel = new EmbeddingModel() {
            @Override
            public Response<Embedding> embed(TextSegment segment) {
                if (segment.text().equals("a")) return Response.from(Embedding.from(new float[]{1.0f, 0.0f}));
                return Response.from(Embedding.from(new float[]{-1.0f, 0.0f}));
            }

            @Override
            public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
                return Response.from(segments.stream()
                    .map(s -> embed(s).content()).toList());
            }

            @Override
            public int dimension() { return 2; }
        };
        var sim = new EmbeddingTextSimilarity(negModel);
        assertThat(sim.compute("a", "b")).isEqualTo(0.0);
    }

    @Test
    void queryEmbeddingCachedAcrossCalls() {
        int[] callCount = {0};
        EmbeddingModel countingModel = new EmbeddingModel() {
            @Override
            public Response<Embedding> embed(TextSegment segment) {
                callCount[0]++;
                return Response.from(Embedding.from(new float[]{1.0f, 0.0f, 0.0f}));
            }

            @Override
            public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
                return Response.from(segments.stream()
                    .map(s -> embed(s).content()).toList());
            }

            @Override
            public int dimension() { return 3; }
        };
        var sim = new EmbeddingTextSimilarity(countingModel);
        sim.compute("query", "case1");
        sim.compute("query", "case2");
        // "query" embedded once (cached), "case1" once, "case2" once = 3 total
        assertThat(callCount[0]).isEqualTo(3);
    }

    @Test
    void precomputeBatchEmbedsAndWarmsCache() {
        int[] embedAllCalls = {0};
        EmbeddingModel batchModel = new EmbeddingModel() {
            @Override
            public Response<Embedding> embed(TextSegment segment) {
                return Response.from(Embedding.from(new float[]{1.0f, 0.0f, 0.0f}));
            }

            @Override
            public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
                embedAllCalls[0]++;
                return Response.from(segments.stream()
                    .map(s -> Embedding.from(new float[]{1.0f, 0.0f, 0.0f})).toList());
            }

            @Override
            public int dimension() { return 3; }
        };
        var sim = new EmbeddingTextSimilarity(batchModel);
        sim.precompute(List.of("a", "b", "c"));
        assertThat(embedAllCalls[0]).isEqualTo(1);

        // compute() should hit warm cache — no additional embed calls
        int[] singleCalls = {0};
        sim.compute("a", "b");
        assertThat(embedAllCalls[0]).isEqualTo(1);
    }

    @Test
    void precomputeSkipsAlreadyCached() {
        int[] embedAllCalls = {0};
        EmbeddingModel batchModel = new EmbeddingModel() {
            @Override
            public Response<Embedding> embed(TextSegment segment) {
                return Response.from(Embedding.from(new float[]{1.0f, 0.0f, 0.0f}));
            }

            @Override
            public Response<List<Embedding>> embedAll(List<TextSegment> segments) {
                embedAllCalls[0]++;
                return Response.from(segments.stream()
                    .map(s -> Embedding.from(new float[]{1.0f, 0.0f, 0.0f})).toList());
            }

            @Override
            public int dimension() { return 3; }
        };
        var sim = new EmbeddingTextSimilarity(batchModel);
        sim.precompute(List.of("a", "b"));
        sim.precompute(List.of("a", "c"));
        // Second call should only embed "c"
        assertThat(embedAllCalls[0]).isEqualTo(2);
    }

    private static org.assertj.core.data.Offset<Double> offset(double v) {
        return org.assertj.core.data.Offset.offset(v);
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-embedding`
Expected: FAIL — `EmbeddingTextSimilarity` not found

- [ ] **Step 5: Implement `EmbeddingTextSimilarity`**

Create `memory-cbr-embedding/src/main/java/io/casehub/neocortex/memory/cbr/embedding/EmbeddingTextSimilarity.java`:

```java
package io.casehub.neocortex.memory.cbr.embedding;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.store.embedding.CosineSimilarity;
import io.casehub.neocortex.memory.cbr.LocalSimilarityFunction;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public class EmbeddingTextSimilarity implements LocalSimilarityFunction {

    private final EmbeddingModel model;
    private final Map<String, Embedding> cache = new HashMap<>();

    public EmbeddingTextSimilarity(EmbeddingModel model) {
        this.model = Objects.requireNonNull(model);
    }

    public void precompute(List<String> texts) {
        List<TextSegment> uncached = texts.stream()
            .filter(t -> !cache.containsKey(t))
            .distinct()
            .map(TextSegment::from).toList();
        if (!uncached.isEmpty()) {
            List<Embedding> embeddings = model.embedAll(uncached).content();
            for (int i = 0; i < uncached.size(); i++) {
                cache.put(uncached.get(i).text(), embeddings.get(i));
            }
        }
    }

    @Override
    public double compute(Object queryValue, Object caseValue) {
        Embedding queryEmb = embed((String) queryValue);
        Embedding caseEmb = embed((String) caseValue);
        return Math.max(0.0, CosineSimilarity.between(queryEmb, caseEmb));
    }

    private Embedding embed(String text) {
        return cache.computeIfAbsent(text, t -> model.embed(TextSegment.from(t)).content());
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-embedding`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-cbr-embedding/ pom.xml
```

Message: `feat(#106): memory-cbr-embedding module — EmbeddingTextSimilarity with batch precompute`

---

### Task 3: Contract test Text field coverage + store wiring

**Files:**
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/pom.xml`
- Modify: `memory-testing/pom.xml` (if needed for new dep)

**Interfaces:**
- Consumes:
  - `LocalSimilarityFunction` from Task 1
  - `FeatureField.Text.semantic()`, `FeatureField.semanticText()` from Task 1
  - `CbrSimilarityScorer.score(Map, Map, Map, CbrFeatureSchema, Map<String, LocalSimilarityFunction>)` from Task 1
  - `EmbeddingTextSimilarity` from Task 2
- Produces: updated store implementations, extended contract tests

- [ ] **Step 1: Add Text field to contract test schema and write new tests**

In `CbrCaseMemoryStoreContractTest.java`, update `registerDefaultSchema()`:

```java
@BeforeEach
void registerDefaultSchema() {
    store().registerSchema(CbrFeatureSchema.of("starcraft-game",
        FeatureField.categorical("opponent_race"),
        FeatureField.categorical("detected_build"),
        FeatureField.numeric("army_size_ratio", 0.0, 3.0),
        FeatureField.text("notes")));
}
```

Add test methods:

```java
@Test
void textExactMatch_identicalStrings() {
    store().store(new FeatureVectorCbrCase("game", "strat", "WIN", null,
        Map.of("opponent_race", "Zerg", "notes", "early pool")),
        "starcraft-game", ENTITY, CBR, TENANT, "case-1");

    var q = CbrQuery.of(TENANT, CBR, "starcraft-game",
        Map.of("notes", "early pool"), 5);
    var results = store().retrieveSimilar(q, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.getFirst().score()).isEqualTo(1.0);
}

@Test
void textExactMatch_differentStrings() {
    store().store(new FeatureVectorCbrCase("match", "strat", "WIN", null,
        Map.of("opponent_race", "Zerg", "notes", "early pool")),
        "starcraft-game", ENTITY, CBR, TENANT, "case-1");
    store().store(new FeatureVectorCbrCase("no match", "strat", "WIN", null,
        Map.of("opponent_race", "Zerg", "notes", "late game macro")),
        "starcraft-game", ENTITY, CBR, TENANT, "case-2");

    var q = CbrQuery.of(TENANT, CBR, "starcraft-game",
        Map.of("notes", "early pool"), 5);
    var results = store().retrieveSimilar(q, FeatureVectorCbrCase.class);
    assertThat(results).hasSizeGreaterThanOrEqualTo(2);
    assertThat(results.get(0).cbrCase().problem()).isEqualTo("match");
    assertThat(results.get(0).score()).isGreaterThan(results.get(1).score());
}
```

- [ ] **Step 2: Update `InMemoryCbrCaseMemoryStore` to use 5-arg `score()`**

Change the `retrieveSimilar` method's scoring call from:

```java
double featureScore = CbrSimilarityScorer.score(
    query.features(), stored.cbrCase().features(), query.weights(), schema);
```

To:

```java
double featureScore = CbrSimilarityScorer.score(
    query.features(), stored.cbrCase().features(), query.weights(), schema, Map.of());
```

Add `import java.util.Map;` if not already present (it is).

- [ ] **Step 3: Run contract test via InMemory to verify Text field tests pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem`
Expected: ALL PASS (Text fields use exact match — no EmbeddingModel in InMemory)

- [ ] **Step 4: Add `memory-cbr-embedding` dependency to `memory-qdrant/pom.xml`**

Add after the `casehub-neocortex-rag-api` dependency:

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-memory-cbr-embedding</artifactId>
</dependency>
```

- [ ] **Step 5: Add `buildTextOverrides()` and `collectSemanticTextValues()` to `QdrantCbrCaseMemoryStore`**

Add these private methods:

```java
private Map<String, LocalSimilarityFunction> buildTextOverrides(
        CbrFeatureSchema schema, EmbeddingTextSimilarity textSim) {
    if (textSim == null) return Map.of();
    Map<String, LocalSimilarityFunction> overrides = new HashMap<>();
    for (FeatureField field : schema.fields()) {
        if (field instanceof FeatureField.Text t && t.semantic()) {
            overrides.put(field.name(), textSim);
        }
    }
    return overrides.isEmpty() ? Map.of() : Collections.unmodifiableMap(overrides);
}

private <C extends CbrCase> List<String> collectSemanticTextValues(
        CbrQuery query, List<ReconstructedCandidate<C>> candidates, Set<String> fieldNames) {
    List<String> texts = new ArrayList<>();
    for (String fieldName : fieldNames) {
        if (query.features().get(fieldName) instanceof String s) texts.add(s);
        for (var rc : candidates) {
            if (rc.cbrCase().features().get(fieldName) instanceof String s) texts.add(s);
        }
    }
    return texts;
}
```

Add the inner record at class level:

```java
private record ReconstructedCandidate<C extends CbrCase>(C cbrCase, float vectorScore) {}
```

Add imports:

```java
import io.casehub.neocortex.memory.cbr.LocalSimilarityFunction;
import io.casehub.neocortex.memory.cbr.embedding.EmbeddingTextSimilarity;
import java.util.Set;
```

- [ ] **Step 6: Restructure `retrieveSimilar()` to two-pass flow**

Replace the scoring loop in `retrieveSimilar()` (after the `scoredPoints` are obtained) with the two-pass approach:

```java
// 1. Build overrides
EmbeddingTextSimilarity textSim = (schema != null && embeddingModel != null)
    ? new EmbeddingTextSimilarity(embeddingModel) : null;
Map<String, LocalSimilarityFunction> overrides = schema != null
    ? buildTextOverrides(schema, textSim)
    : Map.of();

// 2. Reconstruct all candidates (pass 1)
List<ReconstructedCandidate<C>> reconstructed = new ArrayList<>(scoredPoints.size());
for (ScoredPoint point : scoredPoints) {
    try {
        C cbrCase = (C) reconstructCase(point.getPayloadMap(), caseClass);
        if (cbrCase != null) {
            reconstructed.add(new ReconstructedCandidate<>(cbrCase, point.getScore()));
        }
    } catch (Exception e) {
        LOG.log(Level.WARNING, "Failed to reconstruct case from point", e);
    }
}

// 3. Batch precompute embeddings for semantic text values
if (textSim != null && !overrides.isEmpty()) {
    List<String> texts = collectSemanticTextValues(query, reconstructed, overrides.keySet());
    textSim.precompute(texts);
}

// 4. Score and filter (pass 2 — compute() hits warm cache)
List<ScoredCbrCase<C>> candidates = new ArrayList<>(reconstructed.size());
for (var rc : reconstructed) {
    double featureScore = CbrSimilarityScorer.score(
        query.features(), rc.cbrCase().features(), query.weights(), schema, overrides);
    double finalScore;
    if (denseSearch) {
        finalScore = CbrSimilarityScorer.compositeScore(
            featureScore, rc.vectorScore(), query.vectorWeight());
    } else {
        finalScore = featureScore;
    }

    if (finalScore >= query.minSimilarity()) {
        candidates.add(new ScoredCbrCase<>(rc.cbrCase(), finalScore));
    }
}

// Sort by score descending, take topK
candidates.sort((a, b) -> Double.compare(b.score(), a.score()));
List<ScoredCbrCase<C>> results = candidates.size() <= query.topK()
    ? candidates
    : candidates.subList(0, query.topK());
return Collections.unmodifiableList(new ArrayList<>(results));
```

- [ ] **Step 7: Run the full test suite for affected modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory-cbr-embedding,memory-cbr-inmem,memory-qdrant`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-testing/ memory-cbr-inmem/ memory-qdrant/ memory-qdrant/pom.xml
```

Message: `feat(#106): wire semantic text overrides into stores, extend contract test with Text field`

---

### Task 4: Full build verification + CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md` (module listing update)

**Interfaces:**
- Consumes: all prior tasks
- Produces: verified green build, updated documentation

- [ ] **Step 1: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 2: Update CLAUDE.md module listing**

Add `memory-cbr-embedding` entry to the Module Structure section after `memory-cbr-inmem`:

```
memory-cbr-embedding/ — EmbeddingTextSimilarity: EmbeddingModel-based LocalSimilarityFunction for semantic text field cosine similarity, batch precompute() via embedAll(), cache-backed compute(). Depends on memory-api + langchain4j-core only — zero Qdrant deps
```

Add to Maven Coordinates table:

```
| Memory CBR Embedding | `casehub-neocortex-memory-cbr-embedding` |
```

Add root Java package entry:

```
| Root Java package (memory-cbr-embedding) | `io.casehub.neocortex.memory.cbr.embedding` |
```

Update `memory-api` description to mention `LocalSimilarityFunction`:

In the `memory-api` line, add `LocalSimilarityFunction` to the list of types.

Update `memory-qdrant` description to mention `EmbeddingTextSimilarity` integration.

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md
```

Message: `docs(#106): CLAUDE.md — memory-cbr-embedding module, LocalSimilarityFunction`

- [ ] **Step 4: Final full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS
