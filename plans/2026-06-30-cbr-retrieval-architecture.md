# CBR Retrieval Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the CBR retrieval SPI and implementations in neural-text — `CbrCaseMemoryStore` with Feature-Vector CBR support, backed by in-memory and Qdrant implementations.

**Architecture:** Standalone `CbrCaseMemoryStore` SPI (does NOT extend `CaseMemoryStore`) that delegates regular memory storage to an injected platform `CaseMemoryStore` and adds structured similarity retrieval. Open `CbrCase` type hierarchy with `TextualCbrCase` and `FeatureVectorCbrCase`. Qdrant implementation uses Approach 3: payload filters for categorical/numeric features + dense vector for `problem()` text.

**Tech Stack:** Java 21, Quarkus 3.32.2, Qdrant Java Client, LangChain4j 1.14.1, Mutiny, JUnit 5, AssertJ, ArchUnit

**Spec:** `specs/issue-20-cbr-retrieval-architecture/2026-06-30-cbr-retrieval-architecture.md`
**Analysis:** `specs/issue-20-cbr-retrieval-architecture/2026-06-30-cbr-paradigms-and-analysis.md`

## Global Constraints

- Java 21 source on Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build: `mvn` not `./mvnw`
- `memory-api` is Tier 1 pure Java — no Quarkus, no JPA, no LangChain4j, no Qdrant. Only deps: `platform-api` (compile), `mutiny` (provided scope)
- `CbrCaseMemoryStore` does NOT extend `CaseMemoryStore` — standalone SPI, composition via delegation
- `CbrCase` interface is open (not sealed)
- Package for all new CBR types: `io.casehub.memory.cbr`
- Every commit references issue #20
- ArchUnit enforced on `memory-api`: no casehub domain deps except `io.casehub.platform.api.memory` and `io.casehub.memory.cbr`
- Blocking/reactive parity enforced via reflection test (mirrors `rag-api` `BlockingReactiveParityTest`)
- Serialization to `MemoryInput` is implementation-internal (NOT on `CbrCase` interface) — implementations use Jackson
- `CbrQuery` carries `tenantId` and `domain` (mandatory tenant isolation)
- `CbrQuery` does NOT carry `entityIds` — CBR is cross-entity by design
- Erasure order: delegate first (JPA), then Qdrant index
- Existing PayloadFilter in `rag-api` needs numeric range extension before `memory-qdrant` can use it

---

## Task 1: PayloadFilter Numeric Range Extension

Extend the `PayloadFilter` sealed hierarchy in `rag-api` with `Gte`, `Lte`, and `Range` records for numeric filtering. Update `PayloadFilterTranslator` in `rag` to translate these to Qdrant gRPC conditions. This is a prerequisite for `memory-qdrant` but also independently useful for RAG payload filtering.

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/rag/PayloadFilter.java`
- Modify: `rag-api/src/test/java/io/casehub/rag/PayloadFilterTest.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/PayloadFilterTranslator.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/PayloadFilterTranslatorTest.java`

**Interfaces:**
- Consumes: existing `PayloadFilter` sealed interface with `Eq`, `In`, `Not`, `And`, `Or`
- Produces: `PayloadFilter.Gte(String field, double value)`, `PayloadFilter.Lte(String field, double value)`, `PayloadFilter.Range(String field, double min, double max)` — used by `memory-qdrant` Task 4

- [ ] **Step 1: Write failing tests for new PayloadFilter records**

Add to `PayloadFilterTest.java`:

```java
@Test
void gte_rejectsNullField() {
    assertThatThrownBy(() -> PayloadFilter.gte(null, 1.0))
        .isInstanceOf(NullPointerException.class);
}

@Test
void gte_createsValidFilter() {
    var filter = PayloadFilter.gte("score", 0.5);
    assertThat(filter).isInstanceOf(PayloadFilter.Gte.class);
    assertThat(((PayloadFilter.Gte) filter).field()).isEqualTo("score");
    assertThat(((PayloadFilter.Gte) filter).value()).isEqualTo(0.5);
}

@Test
void lte_createsValidFilter() {
    var filter = PayloadFilter.lte("score", 0.9);
    assertThat(filter).isInstanceOf(PayloadFilter.Lte.class);
}

@Test
void range_rejectsMinGreaterThanMax() {
    assertThatThrownBy(() -> PayloadFilter.range("score", 0.9, 0.1))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void range_createsValidFilter() {
    var filter = PayloadFilter.range("score", 0.1, 0.9);
    assertThat(filter).isInstanceOf(PayloadFilter.Range.class);
    var range = (PayloadFilter.Range) filter;
    assertThat(range.field()).isEqualTo("score");
    assertThat(range.min()).isEqualTo(0.1);
    assertThat(range.max()).isEqualTo(0.9);
}

@Test
void range_composesWithAnd() {
    var filter = PayloadFilter.and(
        PayloadFilter.eq("type", "game"),
        PayloadFilter.range("score", 0.5, 1.0)
    );
    assertThat(filter).isInstanceOf(PayloadFilter.And.class);
}
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=PayloadFilterTest -DfailIfNoTests=false`

Expected: compilation failures — `Gte`, `Lte`, `Range`, `gte()`, `lte()`, `range()` not defined

- [ ] **Step 3: Add Gte, Lte, Range to PayloadFilter sealed hierarchy**

Add to `PayloadFilter.java` — three new records and three factory methods:

```java
record Gte(String field, double value) implements PayloadFilter {
    public Gte {
        Objects.requireNonNull(field, "field");
    }
}

record Lte(String field, double value) implements PayloadFilter {
    public Lte {
        Objects.requireNonNull(field, "field");
    }
}

record Range(String field, double min, double max) implements PayloadFilter {
    public Range {
        Objects.requireNonNull(field, "field");
        if (min > max) throw new IllegalArgumentException(
            "min must be <= max, got min=" + min + " max=" + max);
    }
}

static PayloadFilter gte(String field, double value) { return new Gte(field, value); }
static PayloadFilter lte(String field, double value) { return new Lte(field, value); }
static PayloadFilter range(String field, double min, double max) { return new Range(field, min, max); }
```

- [ ] **Step 4: Update PayloadFilterTranslator exhaustive switch**

Add cases to the `toCondition` switch in `PayloadFilterTranslator.java`:

```java
case PayloadFilter.Gte gte ->
    ConditionFactory.range(gte.field(),
        io.qdrant.client.grpc.Common.Range.newBuilder()
            .setGte(gte.value()).build());
case PayloadFilter.Lte lte ->
    ConditionFactory.range(lte.field(),
        io.qdrant.client.grpc.Common.Range.newBuilder()
            .setLte(lte.value()).build());
case PayloadFilter.Range range ->
    ConditionFactory.range(range.field(),
        io.qdrant.client.grpc.Common.Range.newBuilder()
            .setGte(range.min()).setLte(range.max()).build());
```

Note: the Qdrant `ConditionFactory.range()` API and `Range` protobuf message need verification — check IntelliJ for the exact method signature. The Qdrant gRPC `Range` message has `lt`, `gt`, `gte`, `lte` double fields.

- [ ] **Step 5: Add translator tests**

Add to `PayloadFilterTranslatorTest.java`:

```java
@Test
void gte_translates() {
    var filter = PayloadFilter.gte("score", 0.5);
    var result = PayloadFilterTranslator.toQdrantFilter(filter);
    assertThat(result).isPresent();
}

@Test
void lte_translates() {
    var filter = PayloadFilter.lte("score", 0.9);
    var result = PayloadFilterTranslator.toQdrantFilter(filter);
    assertThat(result).isPresent();
}

@Test
void range_translates() {
    var filter = PayloadFilter.range("score", 0.1, 0.9);
    var result = PayloadFilterTranslator.toQdrantFilter(filter);
    assertThat(result).isPresent();
}

@Test
void range_composedWithEq_translates() {
    var filter = PayloadFilter.and(
        PayloadFilter.eq("type", "game"),
        PayloadFilter.range("score", 0.5, 1.0)
    );
    var result = PayloadFilterTranslator.toQdrantFilter(filter);
    assertThat(result).isPresent();
}
```

- [ ] **Step 6: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api,rag`

Expected: all PayloadFilter and translator tests pass, existing tests still green

- [ ] **Step 7: Commit**

```
feat(#20): PayloadFilter numeric range extension — Gte, Lte, Range

Adds numeric comparison records to the PayloadFilter sealed hierarchy
for CBR feature-vector matching. Prerequisite for memory-qdrant.
```

---

## Task 2: memory-api Module — CBR SPI Types

Create the `memory-api` module with all CBR SPI types. Tier 1 pure Java. This is the foundation — every other memory module depends on it.

**Files:**
- Create: `memory-api/pom.xml`
- Create: `memory-api/src/main/java/io/casehub/memory/cbr/CbrCase.java`
- Create: `memory-api/src/main/java/io/casehub/memory/cbr/TextualCbrCase.java`
- Create: `memory-api/src/main/java/io/casehub/memory/cbr/FeatureVectorCbrCase.java`
- Create: `memory-api/src/main/java/io/casehub/memory/cbr/CbrQuery.java`
- Create: `memory-api/src/main/java/io/casehub/memory/cbr/CbrFeatureSchema.java`
- Create: `memory-api/src/main/java/io/casehub/memory/cbr/FeatureField.java`
- Create: `memory-api/src/main/java/io/casehub/memory/cbr/CbrCaseMemoryStore.java`
- Create: `memory-api/src/main/java/io/casehub/memory/cbr/ReactiveCbrCaseMemoryStore.java`
- Create: `memory-api/src/test/java/io/casehub/memory/cbr/CbrCaseTest.java`
- Create: `memory-api/src/test/java/io/casehub/memory/cbr/CbrQueryTest.java`
- Create: `memory-api/src/test/java/io/casehub/memory/cbr/CbrFeatureSchemaTest.java`
- Create: `memory-api/src/test/java/io/casehub/memory/cbr/FeatureFieldTest.java`
- Create: `memory-api/src/test/java/io/casehub/memory/cbr/BlockingReactiveParityTest.java`
- Create: `memory-api/src/test/java/io/casehub/memory/cbr/DependencyConstraintTest.java`
- Modify: `pom.xml` (parent — add `memory-api` to `<modules>`)

**Interfaces:**
- Consumes: `io.casehub.platform.api.memory.MemoryInput`, `MemoryDomain`, `EraseRequest`, `MemoryPermissions` from `casehub-platform-api`
- Produces: `CbrCase`, `TextualCbrCase`, `FeatureVectorCbrCase`, `CbrQuery`, `CbrFeatureSchema`, `FeatureField`, `CbrCaseMemoryStore`, `ReactiveCbrCaseMemoryStore` — used by Tasks 3, 4, 5

- [ ] **Step 1: Create memory-api/pom.xml**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>

  <artifactId>casehub-memory-api</artifactId>
  <name>CaseHub Neural Text - Memory API</name>
  <description>CBR case memory SPI — CbrCaseMemoryStore, CbrCase hierarchy, CbrQuery, CbrFeatureSchema. Tier 1 pure Java.</description>

  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-platform-api</artifactId>
    </dependency>

    <dependency>
      <groupId>io.smallrye.reactive</groupId>
      <artifactId>mutiny</artifactId>
      <scope>provided</scope>
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
    <dependency>
      <groupId>com.tngtech.archunit</groupId>
      <artifactId>archunit-junit5</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

Add `<module>memory-api</module>` to the parent `pom.xml` `<modules>` section, after `corpus`.

- [ ] **Step 2: Create CbrCase interface**

```java
package io.casehub.memory.cbr;

public interface CbrCase {
    String problem();
    String solution();
    String outcome();
    Double confidence();
}
```

- [ ] **Step 3: Create TextualCbrCase and FeatureVectorCbrCase records**

```java
// TextualCbrCase.java
package io.casehub.memory.cbr;

import java.util.Objects;

public record TextualCbrCase(String problem, String solution,
                              String outcome, Double confidence) implements CbrCase {
    public TextualCbrCase {
        Objects.requireNonNull(problem, "problem required");
        if (problem.isBlank()) throw new IllegalArgumentException("problem must not be blank");
        Objects.requireNonNull(solution, "solution required");
        if (solution.isBlank()) throw new IllegalArgumentException("solution must not be blank");
        if (confidence != null && (confidence < 0.0 || confidence > 1.0))
            throw new IllegalArgumentException("confidence must be in [0,1], got: " + confidence);
    }
}
```

```java
// FeatureVectorCbrCase.java
package io.casehub.memory.cbr;

import java.util.Map;
import java.util.Objects;

public record FeatureVectorCbrCase(String problem, String solution,
                                    String outcome, Double confidence,
                                    Map<String, Object> features) implements CbrCase {
    public FeatureVectorCbrCase {
        Objects.requireNonNull(problem, "problem required");
        if (problem.isBlank()) throw new IllegalArgumentException("problem must not be blank");
        Objects.requireNonNull(solution, "solution required");
        if (solution.isBlank()) throw new IllegalArgumentException("solution must not be blank");
        if (confidence != null && (confidence < 0.0 || confidence > 1.0))
            throw new IllegalArgumentException("confidence must be in [0,1], got: " + confidence);
        Objects.requireNonNull(features, "features required");
        features = Map.copyOf(features);
    }
}
```

- [ ] **Step 4: Create FeatureField and CbrFeatureSchema**

```java
// FeatureField.java
package io.casehub.memory.cbr;

import java.util.Objects;

public interface FeatureField {
    String name();

    record Categorical(String name) implements FeatureField {
        public Categorical { Objects.requireNonNull(name, "name"); }
    }

    record Numeric(String name, double min, double max) implements FeatureField {
        public Numeric {
            Objects.requireNonNull(name, "name");
            if (min > max) throw new IllegalArgumentException(
                "min must be <= max, got min=" + min + " max=" + max);
        }
    }

    record Text(String name) implements FeatureField {
        public Text { Objects.requireNonNull(name, "name"); }
    }

    static FeatureField categorical(String name) { return new Categorical(name); }
    static FeatureField numeric(String name, double min, double max) { return new Numeric(name, min, max); }
    static FeatureField text(String name) { return new Text(name); }
}
```

```java
// CbrFeatureSchema.java
package io.casehub.memory.cbr;

import java.util.List;
import java.util.Objects;

public record CbrFeatureSchema(String caseType, List<FeatureField> fields) {
    public CbrFeatureSchema {
        Objects.requireNonNull(caseType, "caseType required");
        if (caseType.isBlank()) throw new IllegalArgumentException("caseType must not be blank");
        Objects.requireNonNull(fields, "fields required");
        fields = List.copyOf(fields);
    }

    public static CbrFeatureSchema of(String caseType, FeatureField... fields) {
        return new CbrFeatureSchema(caseType, List.of(fields));
    }
}
```

- [ ] **Step 5: Create CbrQuery**

```java
package io.casehub.memory.cbr;

import io.casehub.platform.api.memory.MemoryDomain;
import java.time.Instant;
import java.util.Map;
import java.util.Objects;

public record CbrQuery(
    String tenantId,
    MemoryDomain domain,
    String caseType,
    Map<String, Object> features,
    int topK,
    double minSimilarity,
    Instant notBefore
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
    }

    public static CbrQuery of(String tenantId, MemoryDomain domain,
                               String caseType, Map<String, Object> features, int topK) {
        return new CbrQuery(tenantId, domain, caseType, features, topK, 0.0, null);
    }
}
```

- [ ] **Step 6: Create CbrCaseMemoryStore and ReactiveCbrCaseMemoryStore**

```java
// CbrCaseMemoryStore.java
package io.casehub.memory.cbr;

import io.casehub.platform.api.memory.EraseRequest;
import io.casehub.platform.api.memory.MemoryDomain;
import java.util.List;

public interface CbrCaseMemoryStore {

    void registerSchema(CbrFeatureSchema schema);

    String store(CbrCase cbrCase, String entityId, MemoryDomain domain,
                 String tenantId, String caseId);

    <C extends CbrCase> List<C> retrieveSimilar(CbrQuery query, Class<C> caseType);

    int erase(EraseRequest request);

    int eraseEntity(String entityId, String tenantId);
}
```

```java
// ReactiveCbrCaseMemoryStore.java
package io.casehub.memory.cbr;

import io.casehub.platform.api.memory.EraseRequest;
import io.casehub.platform.api.memory.MemoryDomain;
import io.smallrye.mutiny.Uni;
import java.util.List;

public interface ReactiveCbrCaseMemoryStore {

    Uni<Void> registerSchema(CbrFeatureSchema schema);

    Uni<String> store(CbrCase cbrCase, String entityId, MemoryDomain domain,
                      String tenantId, String caseId);

    <C extends CbrCase> Uni<List<C>> retrieveSimilar(CbrQuery query, Class<C> caseType);

    Uni<Integer> erase(EraseRequest request);

    Uni<Integer> eraseEntity(String entityId, String tenantId);
}
```

- [ ] **Step 7: Write CbrCase/record validation tests**

`CbrCaseTest.java`:

```java
package io.casehub.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class CbrCaseTest {

    @Test
    void textualCbrCase_valid() {
        var c = new TextualCbrCase("problem", "solution", "WIN", 0.9);
        assertThat(c.problem()).isEqualTo("problem");
        assertThat(c.solution()).isEqualTo("solution");
        assertThat(c.outcome()).isEqualTo("WIN");
        assertThat(c.confidence()).isEqualTo(0.9);
    }

    @Test
    void textualCbrCase_nullOutcomeAllowed() {
        var c = new TextualCbrCase("problem", "solution", null, null);
        assertThat(c.outcome()).isNull();
        assertThat(c.confidence()).isNull();
    }

    @Test
    void textualCbrCase_nullProblemRejected() {
        assertThatThrownBy(() -> new TextualCbrCase(null, "solution", null, null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void textualCbrCase_blankProblemRejected() {
        assertThatThrownBy(() -> new TextualCbrCase("  ", "solution", null, null))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void textualCbrCase_confidenceOutOfRange() {
        assertThatThrownBy(() -> new TextualCbrCase("p", "s", null, 1.1))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void textualCbrCase_implementsCbrCase() {
        CbrCase c = new TextualCbrCase("p", "s", null, null);
        assertThat(c.problem()).isEqualTo("p");
    }

    @Test
    void featureVectorCbrCase_valid() {
        var features = Map.<String, Object>of("race", "Zerg", "ratio", 0.7);
        var c = new FeatureVectorCbrCase("problem", "solution", "WIN", 0.8, features);
        assertThat(c.features()).containsEntry("race", "Zerg");
    }

    @Test
    void featureVectorCbrCase_featuresDefensivelyCopied() {
        var features = new java.util.HashMap<String, Object>();
        features.put("race", "Zerg");
        var c = new FeatureVectorCbrCase("p", "s", null, null, features);
        features.put("extra", "value");
        assertThat(c.features()).doesNotContainKey("extra");
    }

    @Test
    void featureVectorCbrCase_nullFeaturesRejected() {
        assertThatThrownBy(() -> new FeatureVectorCbrCase("p", "s", null, null, null))
            .isInstanceOf(NullPointerException.class);
    }
}
```

- [ ] **Step 8: Write CbrQuery, CbrFeatureSchema, FeatureField tests**

`CbrQueryTest.java`:

```java
package io.casehub.memory.cbr;

import io.casehub.platform.api.memory.MemoryDomain;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class CbrQueryTest {

    private static final MemoryDomain CBR = new MemoryDomain("cbr");

    @Test
    void of_createsValidQuery() {
        var q = CbrQuery.of("tenant1", CBR, "starcraft-game",
            Map.of("race", "Zerg"), 5);
        assertThat(q.tenantId()).isEqualTo("tenant1");
        assertThat(q.domain()).isEqualTo(CBR);
        assertThat(q.caseType()).isEqualTo("starcraft-game");
        assertThat(q.topK()).isEqualTo(5);
        assertThat(q.minSimilarity()).isEqualTo(0.0);
        assertThat(q.notBefore()).isNull();
    }

    @Test
    void nullTenantIdRejected() {
        assertThatThrownBy(() -> CbrQuery.of(null, CBR, "type", Map.of(), 5))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void nullDomainRejected() {
        assertThatThrownBy(() -> CbrQuery.of("t", null, "type", Map.of(), 5))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void topKLessThanOneRejected() {
        assertThatThrownBy(() -> CbrQuery.of("t", CBR, "type", Map.of(), 0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void minSimilarityOutOfRangeRejected() {
        assertThatThrownBy(() -> new CbrQuery("t", CBR, "type", Map.of(), 5, 1.5, null))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void featuresDefensivelyCopied() {
        var features = new java.util.HashMap<String, Object>();
        features.put("race", "Zerg");
        var q = CbrQuery.of("t", CBR, "type", features, 5);
        features.put("extra", "value");
        assertThat(q.features()).doesNotContainKey("extra");
    }
}
```

`FeatureFieldTest.java`:

```java
package io.casehub.memory.cbr;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class FeatureFieldTest {

    @Test
    void categorical() {
        var f = FeatureField.categorical("race");
        assertThat(f).isInstanceOf(FeatureField.Categorical.class);
        assertThat(f.name()).isEqualTo("race");
    }

    @Test
    void numeric() {
        var f = FeatureField.numeric("ratio", 0.0, 3.0);
        assertThat(f).isInstanceOf(FeatureField.Numeric.class);
        var n = (FeatureField.Numeric) f;
        assertThat(n.min()).isEqualTo(0.0);
        assertThat(n.max()).isEqualTo(3.0);
    }

    @Test
    void numeric_minGreaterThanMax() {
        assertThatThrownBy(() -> FeatureField.numeric("x", 5.0, 1.0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void text() {
        var f = FeatureField.text("description");
        assertThat(f).isInstanceOf(FeatureField.Text.class);
    }

    @Test
    void nullNameRejected() {
        assertThatThrownBy(() -> FeatureField.categorical(null))
            .isInstanceOf(NullPointerException.class);
    }
}
```

`CbrFeatureSchemaTest.java`:

```java
package io.casehub.memory.cbr;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class CbrFeatureSchemaTest {

    @Test
    void of_createsSchema() {
        var schema = CbrFeatureSchema.of("starcraft-game",
            FeatureField.categorical("race"),
            FeatureField.numeric("ratio", 0.0, 3.0));
        assertThat(schema.caseType()).isEqualTo("starcraft-game");
        assertThat(schema.fields()).hasSize(2);
    }

    @Test
    void nullCaseTypeRejected() {
        assertThatThrownBy(() -> CbrFeatureSchema.of(null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void blankCaseTypeRejected() {
        assertThatThrownBy(() -> CbrFeatureSchema.of("  "))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void fieldsDefensivelyCopied() {
        var fields = new java.util.ArrayList<FeatureField>();
        fields.add(FeatureField.categorical("race"));
        var schema = new CbrFeatureSchema("type", fields);
        fields.add(FeatureField.text("extra"));
        assertThat(schema.fields()).hasSize(1);
    }
}
```

- [ ] **Step 9: Write BlockingReactiveParityTest and DependencyConstraintTest**

`BlockingReactiveParityTest.java` — mirrors `rag-api` pattern exactly:

```java
package io.casehub.memory.cbr;

import io.smallrye.mutiny.Uni;
import org.junit.jupiter.api.Test;
import java.lang.reflect.Method;
import java.lang.reflect.ParameterizedType;
import java.lang.reflect.Type;
import java.util.Arrays;
import java.util.Map;
import java.util.stream.Collectors;
import static org.assertj.core.api.Assertions.assertThat;

class BlockingReactiveParityTest {

    private static final Map<Class<?>, Class<?>> PAIRS = Map.of(
        CbrCaseMemoryStore.class, ReactiveCbrCaseMemoryStore.class
    );

    @Test
    void vacuousPassGuard() {
        assertThat(PAIRS).isNotEmpty();
    }

    @Test
    void everyBlockingMethodHasReactiveEquivalent() {
        for (var entry : PAIRS.entrySet()) {
            Class<?> blocking = entry.getKey();
            Class<?> reactive = entry.getValue();
            Map<String, Method> reactiveMethods = Arrays.stream(reactive.getDeclaredMethods())
                .filter(m -> !m.isDefault())
                .collect(Collectors.toMap(Method::getName, m -> m));
            for (Method bm : blocking.getDeclaredMethods()) {
                if (bm.isDefault()) continue;
                Method rm = reactiveMethods.get(bm.getName());
                assertThat(rm)
                    .as("Reactive mirror of %s.%s", blocking.getSimpleName(), bm.getName())
                    .isNotNull();
                assertThat(rm.getReturnType())
                    .as("Return type of %s.%s must be Uni", reactive.getSimpleName(), rm.getName())
                    .isEqualTo(Uni.class);
                assertThat(rm.getParameterTypes())
                    .as("Parameters of %s.%s must match %s.%s",
                        reactive.getSimpleName(), rm.getName(),
                        blocking.getSimpleName(), bm.getName())
                    .isEqualTo(bm.getParameterTypes());
            }
        }
    }

    @Test
    void everyReactiveMethodHasBlockingEquivalent() {
        for (var entry : PAIRS.entrySet()) {
            Class<?> blocking = entry.getKey();
            Class<?> reactive = entry.getValue();
            Map<String, Method> blockingMethods = Arrays.stream(blocking.getDeclaredMethods())
                .filter(m -> !m.isDefault())
                .collect(Collectors.toMap(Method::getName, m -> m));
            for (Method rm : reactive.getDeclaredMethods()) {
                if (rm.isDefault()) continue;
                assertThat(blockingMethods.get(rm.getName()))
                    .as("Blocking counterpart of %s.%s", reactive.getSimpleName(), rm.getName())
                    .isNotNull();
            }
        }
    }
}
```

`DependencyConstraintTest.java`:

```java
package io.casehub.memory.cbr;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "io.casehub.memory.cbr")
class DependencyConstraintTest {

    @ArchTest
    static final ArchRule noQuarkus = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.quarkus..", "jakarta..");

    @ArchTest
    static final ArchRule noLangChain4j = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("dev.langchain4j..");

    @ArchTest
    static final ArchRule noQdrant = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.qdrant..");

    @ArchTest
    static final ArchRule onlyAllowedCasehubDeps = noClasses()
        .that().resideInAPackage("io.casehub.memory.cbr..")
        .should().dependOnClassesThat(
            DescribedPredicate.describe("casehub classes outside platform-api and memory-cbr",
                (JavaClass cls) -> cls.getPackageName().startsWith("io.casehub.")
                    && !cls.getPackageName().startsWith("io.casehub.memory.cbr")
                    && !cls.getPackageName().startsWith("io.casehub.platform.api.memory")));
}
```

- [ ] **Step 10: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api`

Expected: all tests pass — validation, parity, ArchUnit constraints

- [ ] **Step 11: Commit**

```
feat(#20): memory-api module — CbrCaseMemoryStore SPI, CbrCase hierarchy, CbrQuery, CbrFeatureSchema

Tier 1 pure Java CBR retrieval SPI. CbrCaseMemoryStore is standalone
(does not extend CaseMemoryStore) — delegates regular storage internally.
Open CbrCase interface with TextualCbrCase and FeatureVectorCbrCase.
```

---

## Task 3: memory + memory-testing + memory-cbr-inmem Modules

Create the CDI wiring module (NoOp + bridge), the contract test base, and the in-memory implementation. These are developed together because the contract test needs an implementation to validate against, and the NoOp needs the SPI types to compile.

**Files:**
- Create: `memory/pom.xml`
- Create: `memory/src/main/java/io/casehub/memory/cbr/runtime/NoOpCbrCaseMemoryStore.java`
- Create: `memory/src/main/java/io/casehub/memory/cbr/runtime/BlockingToReactiveCbrBridge.java`
- Create: `memory-testing/pom.xml`
- Create: `memory-testing/src/main/java/io/casehub/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Create: `memory-cbr-inmem/pom.xml`
- Create: `memory-cbr-inmem/src/main/java/io/casehub/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Create: `memory-cbr-inmem/src/test/java/io/casehub/memory/cbr/inmem/InMemoryCbrCaseMemoryStoreTest.java`
- Modify: `pom.xml` (parent — add modules)

**Interfaces:**
- Consumes: `CbrCaseMemoryStore`, `CbrCase`, `CbrQuery`, `CbrFeatureSchema` from memory-api (Task 2); `CaseMemoryStore` from platform-api
- Produces: `NoOpCbrCaseMemoryStore @DefaultBean`, `BlockingToReactiveCbrBridge @DefaultBean`, `InMemoryCbrCaseMemoryStore @Alternative @Priority(2)`, `CbrCaseMemoryStoreContractTest` base class — used by Task 4

- [ ] **Step 1: Create pom.xml files for memory, memory-testing, memory-cbr-inmem**

`memory/pom.xml` — Quarkus CDI module:

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-memory</artifactId>
  <name>CaseHub Neural Text - Memory CBR CDI</name>
  <description>NoOpCbrCaseMemoryStore @DefaultBean and BlockingToReactiveCbrBridge.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-memory-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-platform-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
    </dependency>
    <dependency>
      <groupId>io.smallrye.reactive</groupId>
      <artifactId>mutiny</artifactId>
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

`memory-testing/pom.xml` — test support (contract test base, no test scope — consumed as compile dep by impl test suites):

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-memory-testing</artifactId>
  <name>CaseHub Neural Text - Memory CBR Testing</name>
  <description>CbrCaseMemoryStoreContractTest base class.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-memory-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-platform-api</artifactId>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
    </dependency>
  </dependencies>
</project>
```

`memory-cbr-inmem/pom.xml`:

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-memory-cbr-inmem</artifactId>
  <name>CaseHub Neural Text - Memory CBR In-Memory</name>
  <description>In-memory CbrCaseMemoryStore for testing and dev. @Alternative @Priority(2).</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-memory-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-platform-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-memory-testing</artifactId>
      <scope>test</scope>
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

Add `<module>memory</module>`, `<module>memory-testing</module>`, `<module>memory-cbr-inmem</module>` to parent pom.

- [ ] **Step 2: Write NoOpCbrCaseMemoryStore**

```java
package io.casehub.memory.cbr.runtime;

import io.casehub.memory.cbr.*;
import io.casehub.platform.api.memory.CaseMemoryStore;
import io.casehub.platform.api.memory.EraseRequest;
import io.casehub.platform.api.memory.MemoryDomain;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.List;

@DefaultBean
@ApplicationScoped
public class NoOpCbrCaseMemoryStore implements CbrCaseMemoryStore {

    @Inject CaseMemoryStore delegate;

    @Override
    public void registerSchema(CbrFeatureSchema schema) {}

    @Override
    public String store(CbrCase cbrCase, String entityId, MemoryDomain domain,
                        String tenantId, String caseId) {
        return "";
    }

    @Override
    public <C extends CbrCase> List<C> retrieveSimilar(CbrQuery query, Class<C> caseType) {
        return List.of();
    }

    @Override
    public int erase(EraseRequest request) {
        return 0;
    }

    @Override
    public int eraseEntity(String entityId, String tenantId) {
        return 0;
    }
}
```

- [ ] **Step 3: Write BlockingToReactiveCbrBridge**

```java
package io.casehub.memory.cbr.runtime;

import io.casehub.memory.cbr.*;
import io.casehub.platform.api.memory.EraseRequest;
import io.casehub.platform.api.memory.MemoryDomain;
import io.quarkus.arc.DefaultBean;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.List;

@DefaultBean
@ApplicationScoped
public class BlockingToReactiveCbrBridge implements ReactiveCbrCaseMemoryStore {

    @Inject CbrCaseMemoryStore delegate;

    @Override
    public Uni<Void> registerSchema(CbrFeatureSchema schema) {
        return Uni.createFrom().voidItem()
            .invoke(() -> delegate.registerSchema(schema))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public Uni<String> store(CbrCase cbrCase, String entityId, MemoryDomain domain,
                             String tenantId, String caseId) {
        return Uni.createFrom().item(() -> delegate.store(cbrCase, entityId, domain, tenantId, caseId))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public <C extends CbrCase> Uni<List<C>> retrieveSimilar(CbrQuery query, Class<C> caseType) {
        return Uni.createFrom().item(() -> delegate.retrieveSimilar(query, caseType))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public Uni<Integer> erase(EraseRequest request) {
        return Uni.createFrom().item(() -> delegate.erase(request))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public Uni<Integer> eraseEntity(String entityId, String tenantId) {
        return Uni.createFrom().item(() -> delegate.eraseEntity(entityId, tenantId))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }
}
```

- [ ] **Step 4: Write CbrCaseMemoryStoreContractTest**

The contract test is an abstract base class. Subclasses provide the store instance. Tests verify behavioral contract for all implementations.

```java
package io.casehub.memory.cbr.testing;

import io.casehub.memory.cbr.*;
import io.casehub.platform.api.memory.EraseRequest;
import io.casehub.platform.api.memory.MemoryDomain;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

public abstract class CbrCaseMemoryStoreContractTest {

    protected static final MemoryDomain CBR = new MemoryDomain("cbr");
    protected static final String TENANT = "test-tenant";
    protected static final String ENTITY = "test-entity";

    protected abstract CbrCaseMemoryStore store();

    @BeforeEach
    void registerDefaultSchema() {
        store().registerSchema(CbrFeatureSchema.of("starcraft-game",
            FeatureField.categorical("opponent_race"),
            FeatureField.categorical("detected_build"),
            FeatureField.numeric("army_size_ratio", 0.0, 3.0)));
    }

    @Test
    void store_returnsNonBlankId() {
        var c = new TextualCbrCase("Zerg roach rush", "early pressure", "WIN", 0.9);
        String id = store().store(c, ENTITY, CBR, TENANT, "case-1");
        assertThat(id).isNotBlank();
    }

    @Test
    void retrieveSimilar_emptyWhenNoCases() {
        var q = CbrQuery.of(TENANT, CBR, "starcraft-game", Map.of("opponent_race", "Zerg"), 5);
        var results = store().retrieveSimilar(q, CbrCase.class);
        assertThat(results).isEmpty();
    }

    @Test
    void retrieveSimilar_findsStoredCase() {
        var c = new FeatureVectorCbrCase("Zerg roach rush", "early pressure", "WIN", 0.9,
            Map.of("opponent_race", "Zerg", "detected_build", "ROACH_RUSH", "army_size_ratio", 0.7));
        store().store(c, ENTITY, CBR, TENANT, "case-1");

        var q = CbrQuery.of(TENANT, CBR, "starcraft-game",
            Map.of("opponent_race", "Zerg"), 5);
        var results = store().retrieveSimilar(q, FeatureVectorCbrCase.class);
        assertThat(results).hasSize(1);
        assertThat(results.getFirst().problem()).isEqualTo("Zerg roach rush");
        assertThat(results.getFirst().features()).containsEntry("opponent_race", "Zerg");
    }

    @Test
    void retrieveSimilar_filtersByCaseType() {
        var c = new FeatureVectorCbrCase("Zerg game", "rush", "WIN", null,
            Map.of("opponent_race", "Zerg"));
        store().store(c, ENTITY, CBR, TENANT, "case-1");

        var q = CbrQuery.of(TENANT, CBR, "aml-investigation", Map.of(), 5);
        var results = store().retrieveSimilar(q, FeatureVectorCbrCase.class);
        assertThat(results).isEmpty();
    }

    @Test
    void retrieveSimilar_filtersByTenant() {
        var c = new FeatureVectorCbrCase("problem", "solution", "WIN", null,
            Map.of("opponent_race", "Zerg"));
        store().store(c, ENTITY, CBR, "other-tenant", "case-1");

        var q = CbrQuery.of(TENANT, CBR, "starcraft-game",
            Map.of("opponent_race", "Zerg"), 5);
        var results = store().retrieveSimilar(q, FeatureVectorCbrCase.class);
        assertThat(results).isEmpty();
    }

    @Test
    void retrieveSimilar_categoricalExactMatch() {
        store().store(new FeatureVectorCbrCase("Zerg game", "rush", "WIN", null,
            Map.of("opponent_race", "Zerg", "detected_build", "ROACH_RUSH")), ENTITY, CBR, TENANT, "case-1");
        store().store(new FeatureVectorCbrCase("Protoss game", "expand", "LOSS", null,
            Map.of("opponent_race", "Protoss", "detected_build", "ZEALOT_RUSH")), ENTITY, CBR, TENANT, "case-2");

        var q = CbrQuery.of(TENANT, CBR, "starcraft-game",
            Map.of("opponent_race", "Zerg"), 5);
        var results = store().retrieveSimilar(q, FeatureVectorCbrCase.class);
        assertThat(results).hasSize(1);
        assertThat(results.getFirst().features()).containsEntry("opponent_race", "Zerg");
    }

    @Test
    void retrieveSimilar_respectsTopK() {
        for (int i = 0; i < 10; i++) {
            store().store(new FeatureVectorCbrCase("game " + i, "strat", "WIN", null,
                Map.of("opponent_race", "Zerg")), ENTITY, CBR, TENANT, "case-" + i);
        }

        var q = CbrQuery.of(TENANT, CBR, "starcraft-game",
            Map.of("opponent_race", "Zerg"), 3);
        var results = store().retrieveSimilar(q, FeatureVectorCbrCase.class);
        assertThat(results).hasSizeLessThanOrEqualTo(3);
    }

    @Test
    void erase_removesMatchingCases() {
        store().store(new TextualCbrCase("problem", "solution", "WIN", null),
            ENTITY, CBR, TENANT, "case-1");
        int erased = store().erase(new EraseRequest(ENTITY, CBR, TENANT, "case-1"));
        assertThat(erased).isGreaterThanOrEqualTo(0);
    }

    @Test
    void eraseEntity_removesAllEntityCases() {
        store().store(new TextualCbrCase("p1", "s1", "WIN", null), ENTITY, CBR, TENANT, "case-1");
        store().store(new TextualCbrCase("p2", "s2", "LOSS", null), ENTITY, CBR, TENANT, "case-2");
        int erased = store().eraseEntity(ENTITY, TENANT);
        assertThat(erased).isGreaterThanOrEqualTo(0);
    }

    @Test
    void schemaValidation_categoricalFieldRequiresString() {
        store().store(new FeatureVectorCbrCase("p", "s", null, null,
            Map.of("opponent_race", "Zerg")), ENTITY, CBR, TENANT, "case-1");

        assertThatThrownBy(() -> store().retrieveSimilar(
            CbrQuery.of(TENANT, CBR, "starcraft-game", Map.of("opponent_race", 42), 5),
            FeatureVectorCbrCase.class))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void schemaValidation_numericFieldRequiresNumber() {
        store().store(new FeatureVectorCbrCase("p", "s", null, null,
            Map.of("army_size_ratio", 0.7)), ENTITY, CBR, TENANT, "case-1");

        assertThatThrownBy(() -> store().retrieveSimilar(
            CbrQuery.of(TENANT, CBR, "starcraft-game", Map.of("army_size_ratio", "high"), 5),
            FeatureVectorCbrCase.class))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void schemaValidation_unknownFieldsIgnored() {
        store().store(new FeatureVectorCbrCase("p", "s", null, null,
            Map.of("opponent_race", "Zerg")), ENTITY, CBR, TENANT, "case-1");

        var q = CbrQuery.of(TENANT, CBR, "starcraft-game",
            Map.of("opponent_race", "Zerg", "unknown_field", "value"), 5);
        assertThatCode(() -> store().retrieveSimilar(q, FeatureVectorCbrCase.class))
            .doesNotThrowAnyException();
    }
}
```

- [ ] **Step 5: Write InMemoryCbrCaseMemoryStore**

```java
package io.casehub.memory.cbr.inmem;

import io.casehub.memory.cbr.*;
import io.casehub.platform.api.memory.EraseRequest;
import io.casehub.platform.api.memory.MemoryDomain;
import jakarta.alternative.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

@Alternative
@Priority(2)
@ApplicationScoped
public class InMemoryCbrCaseMemoryStore implements CbrCaseMemoryStore {

    private final Map<String, CbrFeatureSchema> schemas = new ConcurrentHashMap<>();

    private record StoredCase(
        String id, CbrCase cbrCase, String entityId, MemoryDomain domain,
        String tenantId, String caseId, String caseType
    ) {}

    private final List<StoredCase> cases = new CopyOnWriteArrayList<>();

    @Override
    public void registerSchema(CbrFeatureSchema schema) {
        schemas.put(schema.caseType(), schema);
    }

    @Override
    public String store(CbrCase cbrCase, String entityId, MemoryDomain domain,
                        String tenantId, String caseId) {
        String caseType = inferCaseType(cbrCase);
        String id = UUID.randomUUID().toString();
        cases.add(new StoredCase(id, cbrCase, entityId, domain, tenantId, caseId, caseType));
        return id;
    }

    @Override
    @SuppressWarnings("unchecked")
    public <C extends CbrCase> List<C> retrieveSimilar(CbrQuery query, Class<C> caseType) {
        CbrFeatureSchema schema = schemas.get(query.caseType());
        if (schema != null) {
            validateQueryFeatures(query.features(), schema);
        }

        return cases.stream()
            .filter(sc -> sc.tenantId().equals(query.tenantId()))
            .filter(sc -> sc.domain().equals(query.domain()))
            .filter(sc -> sc.caseType().equals(query.caseType()))
            .filter(sc -> query.notBefore() == null || true)
            .filter(sc -> caseType.isInstance(sc.cbrCase()))
            .filter(sc -> matchesFeatures(sc.cbrCase(), query.features(), schema))
            .limit(query.topK())
            .map(sc -> (C) sc.cbrCase())
            .toList();
    }

    @Override
    public int erase(EraseRequest request) {
        int before = cases.size();
        cases.removeIf(sc ->
            sc.entityId().equals(request.entityId())
            && sc.domain().equals(request.domain())
            && sc.tenantId().equals(request.tenantId())
            && (request.caseId() == null || sc.caseId().equals(request.caseId())));
        return before - cases.size();
    }

    @Override
    public int eraseEntity(String entityId, String tenantId) {
        int before = cases.size();
        cases.removeIf(sc ->
            sc.entityId().equals(entityId) && sc.tenantId().equals(tenantId));
        return before - cases.size();
    }

    private String inferCaseType(CbrCase cbrCase) {
        if (cbrCase instanceof FeatureVectorCbrCase fv) {
            return schemas.entrySet().stream()
                .filter(e -> fv.features().keySet().containsAll(
                    e.getValue().fields().stream().map(FeatureField::name).toList()))
                .map(Map.Entry::getKey)
                .findFirst()
                .orElse("unknown");
        }
        return "textual";
    }

    private boolean matchesFeatures(CbrCase stored, Map<String, Object> queryFeatures,
                                     CbrFeatureSchema schema) {
        if (queryFeatures.isEmpty()) return true;
        if (!(stored instanceof FeatureVectorCbrCase fv)) return true;

        for (var entry : queryFeatures.entrySet()) {
            String name = entry.getKey();
            Object queryValue = entry.getValue();
            Object storedValue = fv.features().get(name);
            if (storedValue == null) continue;

            FeatureField field = schema != null
                ? schema.fields().stream().filter(f -> f.name().equals(name)).findFirst().orElse(null)
                : null;

            if (field instanceof FeatureField.Categorical) {
                if (!queryValue.equals(storedValue)) return false;
            }
        }
        return true;
    }

    private void validateQueryFeatures(Map<String, Object> features, CbrFeatureSchema schema) {
        for (var entry : features.entrySet()) {
            FeatureField field = schema.fields().stream()
                .filter(f -> f.name().equals(entry.getKey()))
                .findFirst()
                .orElse(null);
            if (field == null) continue;

            if (field instanceof FeatureField.Categorical && !(entry.getValue() instanceof String)) {
                throw new IllegalArgumentException(
                    "Categorical field '" + entry.getKey() + "' requires String, got: "
                    + entry.getValue().getClass().getSimpleName());
            }
            if (field instanceof FeatureField.Numeric && !(entry.getValue() instanceof Number)) {
                throw new IllegalArgumentException(
                    "Numeric field '" + entry.getKey() + "' requires Number, got: "
                    + entry.getValue().getClass().getSimpleName());
            }
            if (field instanceof FeatureField.Text && !(entry.getValue() instanceof String)) {
                throw new IllegalArgumentException(
                    "Text field '" + entry.getKey() + "' requires String, got: "
                    + entry.getValue().getClass().getSimpleName());
            }
        }
    }
}
```

Note: the `inferCaseType` approach is preliminary — the contract test will drive refinement. The `store()` call needs a way to associate the case with a caseType. This may need a `caseType` parameter added to the `store()` method, or the schema registration may need to be consulted. The subagent implementing this task should verify against the contract test and adjust as needed.

- [ ] **Step 6: Write InMemoryCbrCaseMemoryStoreTest extending contract test**

```java
package io.casehub.memory.cbr.inmem;

import io.casehub.memory.cbr.CbrCaseMemoryStore;
import io.casehub.memory.cbr.testing.CbrCaseMemoryStoreContractTest;

class InMemoryCbrCaseMemoryStoreTest extends CbrCaseMemoryStoreContractTest {

    private final InMemoryCbrCaseMemoryStore store = new InMemoryCbrCaseMemoryStore();

    @Override
    protected CbrCaseMemoryStore store() {
        return store;
    }
}
```

- [ ] **Step 7: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory,memory-testing,memory-cbr-inmem`

Expected: all contract tests pass against inmem, NoOp compiles, bridge compiles

- [ ] **Step 8: Commit**

```
feat(#20): memory + memory-testing + memory-cbr-inmem — NoOp, contract test, in-memory CBR

NoOpCbrCaseMemoryStore @DefaultBean delegates to CaseMemoryStore.
CbrCaseMemoryStoreContractTest validates behavioral contract.
InMemoryCbrCaseMemoryStore @Alternative @Priority(2) passes all contract tests.
```

---

## Task 4: memory-qdrant Module — Qdrant-Backed CbrCaseMemoryStore

Create the Qdrant-backed `CbrCaseMemoryStore` implementing Approach 3: payload filters for categorical/numeric features + dense vector for `problem()` text. Delegates regular memory storage to injected `CaseMemoryStore`. Uses Testcontainers Qdrant for integration tests.

**Files:**
- Create: `memory-qdrant/pom.xml`
- Create: `memory-qdrant/src/main/java/io/casehub/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Create: `memory-qdrant/src/main/java/io/casehub/memory/cbr/qdrant/CbrPointBuilder.java`
- Create: `memory-qdrant/src/main/java/io/casehub/memory/cbr/qdrant/CbrQueryTranslator.java`
- Create: `memory-qdrant/src/main/java/io/casehub/memory/cbr/qdrant/CbrCollectionManager.java`
- Create: `memory-qdrant/src/main/java/io/casehub/memory/cbr/qdrant/QdrantCbrConfig.java`
- Create: `memory-qdrant/src/test/java/io/casehub/memory/cbr/qdrant/QdrantCbrCaseMemoryStoreTest.java`
- Create: `memory-qdrant/src/test/java/io/casehub/memory/cbr/qdrant/CbrPointBuilderTest.java`
- Create: `memory-qdrant/src/test/java/io/casehub/memory/cbr/qdrant/CbrQueryTranslatorTest.java`
- Modify: `pom.xml` (parent — add module)

**Interfaces:**
- Consumes: `CbrCaseMemoryStore`, `CbrCase`, `CbrQuery`, `CbrFeatureSchema`, `FeatureField` from memory-api (Task 2); `PayloadFilter.Gte/Lte/Range` from rag-api (Task 1); `CaseMemoryStore` from platform-api; `CbrCaseMemoryStoreContractTest` from memory-testing (Task 3); Qdrant Java client, LangChain4j `EmbeddingModel`
- Produces: `QdrantCbrCaseMemoryStore @ApplicationScoped` — the production CBR retrieval implementation

This task is the most complex. The subagent implementing it should:
1. Study `HybridCaseRetriever` and `QdrantEmbeddingIngestor` in the `rag/` module for Qdrant client patterns, collection creation, and point building
2. Study `PayloadFilterTranslator` for translating `PayloadFilter` to Qdrant gRPC conditions
3. Use Testcontainers Qdrant (pattern from `rag/` tests) for integration tests
4. Follow the `QdrantPointBuilder` pattern from `rag/` for point construction
5. The contract test from Task 3 must pass against the Qdrant implementation

Key implementation details from the spec:
- **§7:** Delegates `store()` to injected `CaseMemoryStore` for durable storage, then indexes in Qdrant
- **§7.1:** JPA/SQLite is source of truth, Qdrant is derived index. Retry Qdrant indexing 3 times on failure.
- **§6.5:** Erasure order: delegate first, then Qdrant
- **§4.1:** Schema registration creates Qdrant payload indexes asynchronously
- **§4.2:** `problem()` → single dense vector. `FeatureField.Text` → payload text (keyword filter). `Categorical` → keyword index. `Numeric` → float index.

- [ ] **Step 1: Create memory-qdrant/pom.xml**

Dependencies: `casehub-memory-api`, `casehub-rag-api` (for PayloadFilter), `casehub-platform-api`, `quarkus-arc`, LangChain4j `langchain4j-core` (for EmbeddingModel), Qdrant Java client, Jackson (for JSON serialization), Mutiny. Test deps: `casehub-memory-testing`, `quarkus-junit5`, Testcontainers Qdrant.

- [ ] **Step 2: Write CbrPointBuilder — builds Qdrant PointStruct from CbrCase**

Follows the `QdrantPointBuilder` pattern in `rag/`. Serializes features to payload fields, `problem()` to dense vector, full case record to payload JSON.

- [ ] **Step 3: Write CbrQueryTranslator — translates CbrQuery + CbrFeatureSchema to Qdrant query**

Uses `PayloadFilter` algebra (including new `Gte`/`Lte`/`Range` from Task 1) to build payload filters from query features. Constructs Qdrant query with prefetch (payload filters) + dense vector search on `problem()`.

- [ ] **Step 4: Write CbrCollectionManager — creates/ensures Qdrant collection with CBR schema**

Creates collection with dense vector config (from embedding model dimension) + payload indexes per registered schema. Follows the collection management pattern in `QdrantEmbeddingIngestor`.

- [ ] **Step 5: Write QdrantCbrConfig — Quarkus @ConfigMapping**

```java
@ConfigMapping(prefix = "casehub.memory.cbr.qdrant")
public interface QdrantCbrConfig {
    @WithDefault("localhost") String host();
    @WithDefault("6334") int port();
    Optional<String> apiKey();
    @WithDefault("false") boolean useTls();
    @WithDefault("cbr") String collectionPrefix();
}
```

- [ ] **Step 6: Write QdrantCbrCaseMemoryStore**

`@ApplicationScoped`. Injects `CaseMemoryStore` (delegate), `EmbeddingModel` (optional — for `problem()` embedding), `QdrantCbrConfig`. Implements `CbrCaseMemoryStore`. The `store()` method: serializes to MemoryInput → delegates to CaseMemoryStore → builds Qdrant point → upserts. The `retrieveSimilar()` method: validates features against schema → translates to Qdrant query → searches → deserializes results from payload JSON.

- [ ] **Step 7: Write unit tests for CbrPointBuilder and CbrQueryTranslator**

- [ ] **Step 8: Write QdrantCbrCaseMemoryStoreTest extending contract test**

Uses Testcontainers Qdrant. Extends `CbrCaseMemoryStoreContractTest`. All contract tests must pass.

- [ ] **Step 9: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory,memory-testing,memory-cbr-inmem,memory-qdrant`

Expected: all contract tests pass against both inmem and Qdrant implementations

- [ ] **Step 10: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Expected: all modules build, all tests pass including existing rag/inference tests

- [ ] **Step 11: Commit**

```
feat(#20): memory-qdrant — Qdrant-backed CbrCaseMemoryStore with payload filters + dense vector

Approach 3: categorical features → keyword payload indexes, numeric → float indexes,
problem() text → dense vector. Delegates durable storage to CaseMemoryStore.
Passes CbrCaseMemoryStoreContractTest via Testcontainers Qdrant.
```

---

## Implementation Notes

### caseType in store()

The `store()` signature does not include a `caseType` parameter. The implementation must infer the case type from the registered schemas or add `caseType` as a parameter. The subagent implementing Task 3 should evaluate whether `store()` needs a `caseType` parameter and update `CbrCaseMemoryStore`, `ReactiveCbrCaseMemoryStore`, the contract test, and the parity test accordingly. The spec does not mandate how caseType is determined at store time — this is an implementation decision that the TDD cycle will resolve.

### Jakarta Annotations

Use `jakarta.enterprise.inject.Alternative` and `jakarta.annotation.Priority` for CDI priority. Check whether the parent pom manages `jakarta.annotation-api` — if not, add the dependency explicitly.

### Parent POM Version Management

The new modules use dependencies that may or may not be managed in the parent pom (platform-api, Qdrant client, etc.). Check `<dependencyManagement>` in the parent pom and add missing entries before creating module pom.xml files.
