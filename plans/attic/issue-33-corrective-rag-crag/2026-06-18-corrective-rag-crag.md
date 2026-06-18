# Corrective RAG (CRAG) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a post-retrieval quality gate that evaluates, filters, and corrects poor retrieval results via a CDI decorator on CaseRetriever.

**Architecture:** `RelevanceEvaluator` SPI in rag-api (Tier 1). `CorrectiveCaseRetriever` CDI `@Decorator` in a new `rag-crag` module, classpath-activated. Default `CrossEncoderRelevanceEvaluator` reuses the existing cross-encoder model with configurable thresholds. Per-chunk `RelevanceGrade` on enriched `RetrievedChunk`; aggregate `RetrievalQuality` as a CDI event.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI `@Decorator`, SmallRye Config `@ConfigMapping`, inference-tasks `CrossEncoderReranker`

**Spec:** `specs/2026-06-18-corrective-rag-crag-design.md` (rev 4)

---

## File Map

### New files

| File | Module | Responsibility |
|------|--------|----------------|
| `rag-api/src/main/java/io/casehub/rag/RelevanceGrade.java` | rag-api | Enum: CORRECT, AMBIGUOUS, INCORRECT, UNGRADED |
| `rag-api/src/main/java/io/casehub/rag/RelevanceEvaluator.java` | rag-api | SPI: evaluate(query, chunk) → RelevanceGrade |
| `rag-api/src/main/java/io/casehub/rag/RetrievalQuality.java` | rag-api | CDI event record: counts + evaluated + expandedSearch |
| `rag-api/src/test/java/io/casehub/rag/RetrievedChunkTest.java` | rag-api | Tests for enriched RetrievedChunk (grade field, withGrade, convenience ctor) |
| `rag-api/src/test/java/io/casehub/rag/RelevanceEvaluatorTest.java` | rag-api | Tests for evaluateBatch default method |
| `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryRelevanceEvaluator.java` | rag-testing | @Alternative @Priority(1) stub evaluator |
| `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryRelevanceEvaluatorTest.java` | rag-testing | Tests for the stub evaluator |
| `rag-crag/pom.xml` | rag-crag | Maven module definition |
| `rag-crag/src/main/java/io/casehub/rag/crag/CragConfig.java` | rag-crag | @ConfigMapping: thresholds + expansion multiplier |
| `rag-crag/src/main/java/io/casehub/rag/crag/CrossEncoderRelevanceEvaluator.java` | rag-crag | RelevanceEvaluator impl: score → threshold → grade |
| `rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java` | rag-crag | @Decorator: evaluate → filter → expand → grade-sort → event |
| `rag-crag/src/main/java/io/casehub/rag/crag/CragBeanProducer.java` | rag-crag | Produces RelevanceEvaluator from CrossEncoderReranker |
| `rag-crag/src/test/java/io/casehub/rag/crag/CrossEncoderRelevanceEvaluatorTest.java` | rag-crag | Threshold grading tests |
| `rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java` | rag-crag | Full decorator pipeline tests |

### Modified files

| File | Module | Change |
|------|--------|--------|
| `rag-api/src/main/java/io/casehub/rag/RetrievedChunk.java` | rag-api | Add grade field, convenience ctor, withGrade() |
| `pom.xml` (root) | parent | Add rag-crag module + dependencyManagement entry |

---

## Task 1: Enrich RetrievedChunk with RelevanceGrade (rag-api)

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/RelevanceGrade.java`
- Modify: `rag-api/src/main/java/io/casehub/rag/RetrievedChunk.java`
- Create: `rag-api/src/test/java/io/casehub/rag/RetrievedChunkTest.java`

- [ ] **Step 1: Create RelevanceGrade enum**

Create `rag-api/src/main/java/io/casehub/rag/RelevanceGrade.java`:

```java
package io.casehub.rag;

public enum RelevanceGrade {
    CORRECT,
    AMBIGUOUS,
    INCORRECT,
    UNGRADED
}
```

- [ ] **Step 2: Write failing tests for enriched RetrievedChunk**

Create `rag-api/src/test/java/io/casehub/rag/RetrievedChunkTest.java`:

```java
package io.casehub.rag;

import org.junit.jupiter.api.Test;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RetrievedChunkTest {

    @Test
    void fourArgConstructorDefaultsToUngraded() {
        var chunk = new RetrievedChunk("content", "doc-1", 0.9, Map.of("k", "v"));
        assertThat(chunk.grade()).isEqualTo(RelevanceGrade.UNGRADED);
    }

    @Test
    void fiveArgConstructorSetsGrade() {
        var chunk = new RetrievedChunk("content", "doc-1", 0.9, Map.of(), RelevanceGrade.CORRECT);
        assertThat(chunk.grade()).isEqualTo(RelevanceGrade.CORRECT);
    }

    @Test
    void withGradeProducesNewChunkPreservingAllFields() {
        var original = new RetrievedChunk("content", "doc-1", 0.9, Map.of("k", "v"));
        var graded = original.withGrade(RelevanceGrade.INCORRECT);
        assertThat(graded.content()).isEqualTo("content");
        assertThat(graded.sourceDocumentId()).isEqualTo("doc-1");
        assertThat(graded.relevanceScore()).isEqualTo(0.9);
        assertThat(graded.metadata()).containsEntry("k", "v");
        assertThat(graded.grade()).isEqualTo(RelevanceGrade.INCORRECT);
        assertThat(original.grade()).isEqualTo(RelevanceGrade.UNGRADED);
    }

    @Test
    void canonicalConstructorValidatesNulls() {
        assertThatThrownBy(() -> new RetrievedChunk(null, "doc", 0.5, Map.of(), RelevanceGrade.UNGRADED))
            .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RetrievedChunk("c", null, 0.5, Map.of(), RelevanceGrade.UNGRADED))
            .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new RetrievedChunk("c", "doc", 0.5, Map.of(), null))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void metadataNullDefaultsToEmptyMap() {
        var chunk = new RetrievedChunk("content", "doc-1", 0.9, null);
        assertThat(chunk.metadata()).isEmpty();
        assertThat(chunk.grade()).isEqualTo(RelevanceGrade.UNGRADED);
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievedChunkTest -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: FAIL — `RetrievedChunk` has no `grade` field or 5-arg constructor yet.

- [ ] **Step 4: Modify RetrievedChunk to add grade field**

Replace the entire record in `rag-api/src/main/java/io/casehub/rag/RetrievedChunk.java`:

```java
package io.casehub.rag;

import java.util.Map;

public record RetrievedChunk(String content, String sourceDocumentId,
                             double relevanceScore, Map<String, String> metadata,
                             RelevanceGrade grade) {
    public RetrievedChunk {
        if (content == null)
            throw new IllegalArgumentException("content must not be null");
        if (sourceDocumentId == null)
            throw new IllegalArgumentException("sourceDocumentId must not be null");
        if (grade == null)
            throw new IllegalArgumentException("grade must not be null");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }

    public RetrievedChunk(String content, String sourceDocumentId,
                          double relevanceScore, Map<String, String> metadata) {
        this(content, sourceDocumentId, relevanceScore, metadata, RelevanceGrade.UNGRADED);
    }

    public RetrievedChunk withGrade(RelevanceGrade grade) {
        return new RetrievedChunk(content, sourceDocumentId, relevanceScore, metadata, grade);
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievedChunkTest -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: PASS

- [ ] **Step 6: Run all rag-api tests to verify nothing broke**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: PASS — existing tests (BlockingReactiveParityTest, DependencyConstraintTest) should still pass. The 4-arg `RetrievedChunk` constructor used across the codebase compiles and defaults to `UNGRADED`.

- [ ] **Step 7: Commit**

```
git add rag-api/src/main/java/io/casehub/rag/RelevanceGrade.java \
       rag-api/src/main/java/io/casehub/rag/RetrievedChunk.java \
       rag-api/src/test/java/io/casehub/rag/RetrievedChunkTest.java
git commit -m "feat(#33): enrich RetrievedChunk with RelevanceGrade — 5-arg canonical, 4-arg convenience defaulting to UNGRADED"
```

---

## Task 2: Add RelevanceEvaluator SPI and RetrievalQuality event (rag-api)

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/RelevanceEvaluator.java`
- Create: `rag-api/src/main/java/io/casehub/rag/RetrievalQuality.java`
- Create: `rag-api/src/test/java/io/casehub/rag/RelevanceEvaluatorTest.java`

- [ ] **Step 1: Write failing test for evaluateBatch default method**

Create `rag-api/src/test/java/io/casehub/rag/RelevanceEvaluatorTest.java`:

```java
package io.casehub.rag;

import org.junit.jupiter.api.Test;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class RelevanceEvaluatorTest {

    @Test
    void evaluateBatchDefaultDelegatesToEvaluate() {
        RelevanceEvaluator evaluator = (query, chunkContent) -> {
            if (chunkContent.contains("relevant")) return RelevanceGrade.CORRECT;
            if (chunkContent.contains("maybe")) return RelevanceGrade.AMBIGUOUS;
            return RelevanceGrade.INCORRECT;
        };

        List<RelevanceGrade> grades = evaluator.evaluateBatch("query",
            List.of("relevant text", "maybe useful", "garbage"));

        assertThat(grades).containsExactly(
            RelevanceGrade.CORRECT, RelevanceGrade.AMBIGUOUS, RelevanceGrade.INCORRECT);
    }

    @Test
    void evaluateBatchEmptyListReturnsEmpty() {
        RelevanceEvaluator evaluator = (query, chunkContent) -> RelevanceGrade.CORRECT;
        List<RelevanceGrade> grades = evaluator.evaluateBatch("query", List.of());
        assertThat(grades).isEmpty();
    }

    @Test
    void evaluateBatchReturnsImmutableList() {
        RelevanceEvaluator evaluator = (query, chunkContent) -> RelevanceGrade.CORRECT;
        List<RelevanceGrade> grades = evaluator.evaluateBatch("query", List.of("text"));
        assertThat(grades).isUnmodifiable();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RelevanceEvaluatorTest -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: FAIL — `RelevanceEvaluator` does not exist.

- [ ] **Step 3: Create RelevanceEvaluator SPI and RetrievalQuality**

Create `rag-api/src/main/java/io/casehub/rag/RelevanceEvaluator.java`:

```java
package io.casehub.rag;

import java.util.ArrayList;
import java.util.List;

public interface RelevanceEvaluator {

    RelevanceGrade evaluate(String query, String chunkContent);

    default List<RelevanceGrade> evaluateBatch(String query, List<String> chunkContents) {
        List<RelevanceGrade> grades = new ArrayList<>(chunkContents.size());
        for (String content : chunkContents) {
            grades.add(evaluate(query, content));
        }
        return List.copyOf(grades);
    }
}
```

Create `rag-api/src/main/java/io/casehub/rag/RetrievalQuality.java`:

```java
package io.casehub.rag;

public record RetrievalQuality(
    int totalRetrieved,
    int totalCorrect,
    int totalAmbiguous,
    int totalIncorrect,
    boolean evaluated,
    boolean expandedSearch
) {
    public static final RetrievalQuality NONE =
        new RetrievalQuality(0, 0, 0, 0, false, false);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git add rag-api/src/main/java/io/casehub/rag/RelevanceEvaluator.java \
       rag-api/src/main/java/io/casehub/rag/RelevanceEvaluator.java \
       rag-api/src/main/java/io/casehub/rag/RetrievalQuality.java \
       rag-api/src/test/java/io/casehub/rag/RelevanceEvaluatorTest.java
git commit -m "feat(#33): add RelevanceEvaluator SPI and RetrievalQuality event type to rag-api"
```

---

## Task 3: Add InMemoryRelevanceEvaluator stub (rag-testing)

**Files:**
- Create: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryRelevanceEvaluator.java`
- Create: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryRelevanceEvaluatorTest.java`

- [ ] **Step 1: Write failing tests**

Create `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryRelevanceEvaluatorTest.java`:

```java
package io.casehub.rag.testing;

import io.casehub.rag.RelevanceGrade;
import org.junit.jupiter.api.Test;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryRelevanceEvaluatorTest {

    @Test
    void defaultConstructorReturnsCorrect() {
        var evaluator = new InMemoryRelevanceEvaluator();
        assertThat(evaluator.evaluate("query", "content")).isEqualTo(RelevanceGrade.CORRECT);
    }

    @Test
    void returningFactoryReturnsConfiguredGrade() {
        var evaluator = InMemoryRelevanceEvaluator.returning(RelevanceGrade.INCORRECT);
        assertThat(evaluator.evaluate("query", "content")).isEqualTo(RelevanceGrade.INCORRECT);
    }

    @Test
    void evaluateBatchReturnsConfiguredGradeForAll() {
        var evaluator = InMemoryRelevanceEvaluator.returning(RelevanceGrade.AMBIGUOUS);
        List<RelevanceGrade> grades = evaluator.evaluateBatch("query",
            List.of("chunk1", "chunk2", "chunk3"));
        assertThat(grades).containsExactly(
            RelevanceGrade.AMBIGUOUS, RelevanceGrade.AMBIGUOUS, RelevanceGrade.AMBIGUOUS);
    }

    @Test
    void evaluateIgnoresQueryAndContent() {
        var evaluator = InMemoryRelevanceEvaluator.returning(RelevanceGrade.CORRECT);
        assertThat(evaluator.evaluate("any query", "any content")).isEqualTo(RelevanceGrade.CORRECT);
        assertThat(evaluator.evaluate("different", "different")).isEqualTo(RelevanceGrade.CORRECT);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryRelevanceEvaluatorTest -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: FAIL — class does not exist.

- [ ] **Step 3: Create InMemoryRelevanceEvaluator**

Create `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryRelevanceEvaluator.java`:

```java
package io.casehub.rag.testing;

import io.casehub.rag.RelevanceEvaluator;
import io.casehub.rag.RelevanceGrade;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;

@Alternative
@Priority(1)
@ApplicationScoped
public class InMemoryRelevanceEvaluator implements RelevanceEvaluator {

    private final RelevanceGrade fixedGrade;

    public InMemoryRelevanceEvaluator() {
        this.fixedGrade = RelevanceGrade.CORRECT;
    }

    private InMemoryRelevanceEvaluator(RelevanceGrade grade) {
        this.fixedGrade = grade;
    }

    public static InMemoryRelevanceEvaluator returning(RelevanceGrade grade) {
        return new InMemoryRelevanceEvaluator(grade);
    }

    @Override
    public RelevanceGrade evaluate(String query, String chunkContent) {
        return fixedGrade;
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git add rag-testing/src/main/java/io/casehub/rag/testing/InMemoryRelevanceEvaluator.java \
       rag-testing/src/test/java/io/casehub/rag/testing/InMemoryRelevanceEvaluatorTest.java
git commit -m "feat(#33): add InMemoryRelevanceEvaluator stub to rag-testing"
```

---

## Task 4: Verify existing tests pass with enriched RetrievedChunk

**Files:**
- None created. Verification only.

- [ ] **Step 1: Run all rag-testing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: ALL PASS — existing `InMemoryCaseRetrieverTest` uses 4-arg `RetrievedChunk` construction which compiles via the convenience constructor.

- [ ] **Step 2: Run rag module tests (non-Testcontainers)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -f /Users/mdproctor/claude/casehub/neural-text/pom.xml -Dtest='!*IT,!HybridCaseRetrieverTest,!ReactiveHybridCaseRetrieverTest'`

Expected: PASS — blocking-to-reactive bridge tests and others use 4-arg RetrievedChunk.

- [ ] **Step 3: Run inference-tasks tests (unaffected module — smoke check)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-tasks -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: ALL PASS — inference-tasks has no dependency on rag-api.

---

## Task 5: Create rag-crag module scaffold

**Files:**
- Create: `rag-crag/pom.xml`
- Modify: `pom.xml` (root — add module + dependencyManagement entry)

- [ ] **Step 1: Create rag-crag/pom.xml**

Create `rag-crag/pom.xml`:

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

  <artifactId>casehub-rag-crag</artifactId>
  <name>CaseHub Neural Text - RAG CRAG</name>
  <description>Corrective RAG — CDI @Decorator on CaseRetriever that evaluates retrieval quality, filters irrelevant chunks, and expands search. Classpath-activated.</description>

  <dependencies>

    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-rag-api</artifactId>
    </dependency>

    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-tasks</artifactId>
    </dependency>

    <dependency>
      <groupId>jakarta.enterprise</groupId>
      <artifactId>jakarta.enterprise.cdi-api</artifactId>
      <version>4.1.0</version>
      <scope>provided</scope>
    </dependency>

    <dependency>
      <groupId>io.smallrye</groupId>
      <artifactId>smallrye-config-core</artifactId>
      <version>3.14.1</version>
      <scope>provided</scope>
    </dependency>

    <!-- Testing -->
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
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-inmem</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-rag-testing</artifactId>
      <scope>test</scope>
    </dependency>

  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>io.smallrye</groupId>
        <artifactId>jandex-maven-plugin</artifactId>
        <executions>
          <execution>
            <id>make-index</id>
            <goals><goal>jandex</goal></goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>

</project>
```

- [ ] **Step 2: Add rag-crag to root pom.xml modules list**

In `pom.xml` (root), add `<module>rag-crag</module>` after `<module>rag-testing</module>` in the `<modules>` section.

- [ ] **Step 3: Add rag-crag to root pom.xml dependencyManagement**

In `pom.xml` (root), add in the `<dependencyManagement>` section after the `casehub-rag-testing` entry:

```xml
      <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-rag-crag</artifactId>
        <version>${project.version}</version>
      </dependency>
```

- [ ] **Step 4: Create source directories**

```bash
mkdir -p rag-crag/src/main/java/io/casehub/rag/crag
mkdir -p rag-crag/src/test/java/io/casehub/rag/crag
```

- [ ] **Step 5: Verify module compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl rag-crag -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: BUILD SUCCESS (empty module compiles)

- [ ] **Step 6: Commit**

```
git add rag-crag/pom.xml pom.xml
git commit -m "feat(#33): scaffold rag-crag module — CDI library, Jandex indexed, classpath-activated"
```

---

## Task 6: CrossEncoderRelevanceEvaluator (rag-crag)

**Files:**
- Create: `rag-crag/src/main/java/io/casehub/rag/crag/CrossEncoderRelevanceEvaluator.java`
- Create: `rag-crag/src/test/java/io/casehub/rag/crag/CrossEncoderRelevanceEvaluatorTest.java`

- [ ] **Step 1: Write failing tests**

Create `rag-crag/src/test/java/io/casehub/rag/crag/CrossEncoderRelevanceEvaluatorTest.java`:

```java
package io.casehub.rag.crag;

import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.rag.RelevanceGrade;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CrossEncoderRelevanceEvaluatorTest {

    @Test
    void scoreAboveCorrectThresholdReturnsCorrect() {
        var evaluator = evaluatorReturningScore(0.85f, 0.7, 0.3);
        assertThat(evaluator.evaluate("query", "chunk")).isEqualTo(RelevanceGrade.CORRECT);
    }

    @Test
    void scoreAtCorrectThresholdReturnsCorrect() {
        var evaluator = evaluatorReturningScore(0.7f, 0.7, 0.3);
        assertThat(evaluator.evaluate("query", "chunk")).isEqualTo(RelevanceGrade.CORRECT);
    }

    @Test
    void scoreBelowIncorrectThresholdReturnsIncorrect() {
        var evaluator = evaluatorReturningScore(0.1f, 0.7, 0.3);
        assertThat(evaluator.evaluate("query", "chunk")).isEqualTo(RelevanceGrade.INCORRECT);
    }

    @Test
    void scoreAtIncorrectThresholdReturnsIncorrect() {
        var evaluator = evaluatorReturningScore(0.3f, 0.7, 0.3);
        assertThat(evaluator.evaluate("query", "chunk")).isEqualTo(RelevanceGrade.INCORRECT);
    }

    @Test
    void scoreBetweenThresholdsReturnsAmbiguous() {
        var evaluator = evaluatorReturningScore(0.5f, 0.7, 0.3);
        assertThat(evaluator.evaluate("query", "chunk")).isEqualTo(RelevanceGrade.AMBIGUOUS);
    }

    @Test
    void evaluateBatchUsesRerankerBatchPath() {
        var model = InMemoryInferenceModel.withFunction(1, input -> {
            String candidate = input.texts().get(1);
            return switch (candidate) {
                case "good" -> new float[]{0.9f};
                case "meh"  -> new float[]{0.5f};
                case "bad"  -> new float[]{0.1f};
                default     -> new float[]{0.0f};
            };
        });
        var reranker = new CrossEncoderReranker(model);
        var evaluator = new CrossEncoderRelevanceEvaluator(reranker, 0.7, 0.3);

        List<RelevanceGrade> grades = evaluator.evaluateBatch("query",
            List.of("good", "meh", "bad"));

        assertThat(grades).containsExactly(
            RelevanceGrade.CORRECT, RelevanceGrade.AMBIGUOUS, RelevanceGrade.INCORRECT);
    }

    @Test
    void constructorRejectsNullReranker() {
        assertThatThrownBy(() -> new CrossEncoderRelevanceEvaluator(null, 0.7, 0.3))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void constructorRejectsInvertedThresholds() {
        var model = InMemoryInferenceModel.returning(0.5f);
        var reranker = new CrossEncoderReranker(model);
        assertThatThrownBy(() -> new CrossEncoderRelevanceEvaluator(reranker, 0.3, 0.7))
            .isInstanceOf(IllegalArgumentException.class);
    }

    private static CrossEncoderRelevanceEvaluator evaluatorReturningScore(
            float score, double correctThreshold, double incorrectThreshold) {
        var model = InMemoryInferenceModel.returning(score);
        var reranker = new CrossEncoderReranker(model);
        return new CrossEncoderRelevanceEvaluator(reranker, correctThreshold, incorrectThreshold);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-crag -Dtest=CrossEncoderRelevanceEvaluatorTest -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: FAIL — class does not exist.

- [ ] **Step 3: Implement CrossEncoderRelevanceEvaluator**

Create `rag-crag/src/main/java/io/casehub/rag/crag/CrossEncoderRelevanceEvaluator.java`:

```java
package io.casehub.rag.crag;

import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.inference.tasks.RankedResult;
import io.casehub.rag.RelevanceEvaluator;
import io.casehub.rag.RelevanceGrade;

import java.util.ArrayList;
import java.util.List;

public final class CrossEncoderRelevanceEvaluator implements RelevanceEvaluator {

    private final CrossEncoderReranker reranker;
    private final double correctThreshold;
    private final double incorrectThreshold;

    public CrossEncoderRelevanceEvaluator(CrossEncoderReranker reranker,
                                          double correctThreshold,
                                          double incorrectThreshold) {
        if (reranker == null) throw new IllegalArgumentException("reranker must not be null");
        if (incorrectThreshold > correctThreshold)
            throw new IllegalArgumentException(
                "incorrectThreshold (" + incorrectThreshold
                    + ") must not exceed correctThreshold (" + correctThreshold + ")");
        this.reranker = reranker;
        this.correctThreshold = correctThreshold;
        this.incorrectThreshold = incorrectThreshold;
    }

    @Override
    public RelevanceGrade evaluate(String query, String chunkContent) {
        float score = reranker.score(query, chunkContent);
        return gradeFromScore(score);
    }

    @Override
    public List<RelevanceGrade> evaluateBatch(String query, List<String> chunkContents) {
        if (chunkContents.isEmpty()) return List.of();
        List<RankedResult> ranked = reranker.rerank(query, chunkContents);
        List<RelevanceGrade> grades = new ArrayList<>(chunkContents.size());
        for (int i = 0; i < chunkContents.size(); i++) grades.add(null);
        for (RankedResult r : ranked) {
            grades.set(r.originalIndex(), gradeFromScore(r.score()));
        }
        return List.copyOf(grades);
    }

    private RelevanceGrade gradeFromScore(float score) {
        if (score >= correctThreshold) return RelevanceGrade.CORRECT;
        if (score <= incorrectThreshold) return RelevanceGrade.INCORRECT;
        return RelevanceGrade.AMBIGUOUS;
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-crag -Dtest=CrossEncoderRelevanceEvaluatorTest -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: ALL PASS

- [ ] **Step 5: Commit**

```
git add rag-crag/src/main/java/io/casehub/rag/crag/CrossEncoderRelevanceEvaluator.java \
       rag-crag/src/test/java/io/casehub/rag/crag/CrossEncoderRelevanceEvaluatorTest.java
git commit -m "feat(#33): add CrossEncoderRelevanceEvaluator — threshold-based grading via cross-encoder scores"
```

---

## Task 7: CorrectiveCaseRetriever decorator (rag-crag)

**Files:**
- Create: `rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java`
- Create: `rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java`

- [ ] **Step 1: Write failing tests**

Create `rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java`:

```java
package io.casehub.rag.crag;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.PayloadFilter;
import io.casehub.rag.RelevanceGrade;
import io.casehub.rag.RetrievalQuality;
import io.casehub.rag.RetrievedChunk;
import io.casehub.rag.testing.InMemoryCaseRetriever;
import io.casehub.rag.testing.InMemoryRelevanceEvaluator;
import jakarta.enterprise.event.Event;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class CorrectiveCaseRetrieverTest {

    private static final CorpusRef CORPUS = new CorpusRef("tenant-1", "test-corpus");

    @Test
    void allCorrect_returnsAllChunksWithGrades() {
        var delegate = fixedRetriever(
            chunk("good1", "doc1", 0.9), chunk("good2", "doc2", 0.8));
        var quality = new AtomicReference<RetrievalQuality>();

        var retriever = corrective(delegate, RelevanceGrade.CORRECT, quality);
        var results = retriever.retrieve("query", CORPUS, 10, null);

        assertThat(results).hasSize(2);
        assertThat(results).allSatisfy(c -> assertThat(c.grade()).isEqualTo(RelevanceGrade.CORRECT));
        assertThat(quality.get().evaluated()).isTrue();
        assertThat(quality.get().expandedSearch()).isFalse();
        assertThat(quality.get().totalCorrect()).isEqualTo(2);
        assertThat(quality.get().totalIncorrect()).isEqualTo(0);
    }

    @Test
    void allIncorrect_filtersAll_triggersExpansion() {
        var delegate = fixedRetriever(
            chunk("bad1", "doc1", 0.9), chunk("bad2", "doc2", 0.8));
        var quality = new AtomicReference<RetrievalQuality>();

        var retriever = corrective(delegate, RelevanceGrade.INCORRECT, quality);
        var results = retriever.retrieve("query", CORPUS, 5, null);

        assertThat(results).isEmpty();
        assertThat(quality.get().expandedSearch()).isTrue();
        assertThat(quality.get().totalIncorrect()).isGreaterThan(0);
    }

    @Test
    void mixedGrades_filtersIncorrect_keepsCorrectAndAmbiguous() {
        List<RetrievedChunk> chunks = List.of(
            chunk("good", "doc1", 0.9),
            chunk("bad", "doc2", 0.8),
            chunk("maybe", "doc3", 0.7));
        var delegate = InMemoryCaseRetriever.returning(chunks);

        var evaluator = new GradeByContentEvaluator(Map.of(
            "good", RelevanceGrade.CORRECT,
            "bad", RelevanceGrade.INCORRECT,
            "maybe", RelevanceGrade.AMBIGUOUS));

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new CorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 10, null);

        assertThat(results).hasSize(2);
        assertThat(results).extracting(RetrievedChunk::content)
            .containsExactly("good", "maybe");
        assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
        assertThat(results.get(1).grade()).isEqualTo(RelevanceGrade.AMBIGUOUS);
        assertThat(quality.get().totalCorrect()).isEqualTo(1);
        assertThat(quality.get().totalAmbiguous()).isEqualTo(1);
        assertThat(quality.get().totalIncorrect()).isEqualTo(1);
    }

    @Test
    void truncation_prefersCorrectOverAmbiguous() {
        List<RetrievedChunk> chunks = List.of(
            chunk("ambig1", "doc1", 0.9),
            chunk("ambig2", "doc2", 0.8),
            chunk("correct1", "doc3", 0.7));
        var delegate = InMemoryCaseRetriever.returning(chunks);

        var evaluator = new GradeByContentEvaluator(Map.of(
            "ambig1", RelevanceGrade.AMBIGUOUS,
            "ambig2", RelevanceGrade.AMBIGUOUS,
            "correct1", RelevanceGrade.CORRECT));

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new CorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 2, null);

        assertThat(results).hasSize(2);
        assertThat(results.get(0).content()).isEqualTo("correct1");
        assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
    }

    @Test
    void emptyInitialRetrieval_triggersExpansion() {
        var delegate = InMemoryCaseRetriever.returning(List.of());
        var quality = new AtomicReference<RetrievalQuality>();

        var retriever = corrective(delegate, RelevanceGrade.CORRECT, quality);
        var results = retriever.retrieve("query", CORPUS, 5, null);

        assertThat(results).isEmpty();
        assertThat(quality.get().expandedSearch()).isTrue();
        assertThat(quality.get().totalRetrieved()).isEqualTo(0);
    }

    @Test
    void qualityEvent_countsReflectInitialAndExpansion() {
        var callCount = new int[]{0};
        CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            callCount[0]++;
            if (callCount[0] == 1) {
                return List.of(chunk("bad", "doc1", 0.9));
            }
            return List.of(
                chunk("bad", "doc1", 0.9),
                chunk("good", "doc2", 0.8));
        };

        var evaluator = new GradeByContentEvaluator(Map.of(
            "bad", RelevanceGrade.INCORRECT,
            "good", RelevanceGrade.CORRECT));

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new CorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 5, null);

        assertThat(results).hasSize(1);
        assertThat(results.get(0).content()).isEqualTo("good");
        assertThat(quality.get().totalRetrieved()).isEqualTo(2);
        assertThat(quality.get().totalCorrect()).isEqualTo(1);
        assertThat(quality.get().totalIncorrect()).isEqualTo(2);
        assertThat(quality.get().expandedSearch()).isTrue();
    }

    @Test
    void expansion_deduplicates_alreadySeenChunks() {
        var callCount = new int[]{0};
        CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            callCount[0]++;
            if (callCount[0] == 1) {
                return List.of(chunk("seen", "doc1", 0.9));
            }
            return List.of(
                chunk("seen", "doc1", 0.9),
                chunk("new", "doc2", 0.8));
        };

        var evaluator = new GradeByContentEvaluator(Map.of(
            "seen", RelevanceGrade.INCORRECT,
            "new", RelevanceGrade.CORRECT));

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new CorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 5, null);

        assertThat(results).hasSize(1);
        assertThat(results.get(0).content()).isEqualTo("new");
        assertThat(quality.get().totalRetrieved()).isEqualTo(2);
    }

    // ── helpers ──────────────────────────────────────────────────────

    private static RetrievedChunk chunk(String content, String docId, double score) {
        return new RetrievedChunk(content, docId, score, Map.of());
    }

    private static CaseRetriever fixedRetriever(RetrievedChunk... chunks) {
        return InMemoryCaseRetriever.returning(List.of(chunks));
    }

    private static CorrectiveCaseRetriever corrective(
            CaseRetriever delegate, RelevanceGrade fixedGrade,
            AtomicReference<RetrievalQuality> qualityCapture) {
        return new CorrectiveCaseRetriever(
            delegate,
            InMemoryRelevanceEvaluator.returning(fixedGrade),
            stubConfig(3),
            capturingEvent(qualityCapture));
    }

    private static CragConfig stubConfig(int expansionMultiplier) {
        return new CragConfig() {
            @Override public double correctThreshold() { return 0.7; }
            @Override public double incorrectThreshold() { return 0.3; }
            @Override public int expansionMultiplier() { return expansionMultiplier; }
        };
    }

    private static Event<RetrievalQuality> capturingEvent(AtomicReference<RetrievalQuality> ref) {
        return new Event<>() {
            @Override public void fire(RetrievalQuality event) { ref.set(event); }
            @Override public <U extends RetrievalQuality> Event<U> select(Class<U> c, java.lang.annotation.Annotation... a) { return null; }
            @Override public <U extends RetrievalQuality> Event<U> select(jakarta.enterprise.util.TypeLiteral<U> t, java.lang.annotation.Annotation... a) { return null; }
            @Override public java.util.concurrent.CompletionStage<RetrievalQuality> fireAsync(RetrievalQuality event) { ref.set(event); return java.util.concurrent.CompletableFuture.completedFuture(event); }
            @Override public java.util.concurrent.CompletionStage<RetrievalQuality> fireAsync(RetrievalQuality event, jakarta.enterprise.event.NotificationOptions options) { return fireAsync(event); }
        };
    }

    private record GradeByContentEvaluator(Map<String, RelevanceGrade> contentToGrade)
            implements io.casehub.rag.RelevanceEvaluator {
        @Override
        public RelevanceGrade evaluate(String query, String chunkContent) {
            return contentToGrade.getOrDefault(chunkContent, RelevanceGrade.UNGRADED);
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-crag -Dtest=CorrectiveCaseRetrieverTest -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: FAIL — `CorrectiveCaseRetriever` does not exist.

- [ ] **Step 3: Create CragConfig interface**

Create `rag-crag/src/main/java/io/casehub/rag/crag/CragConfig.java`:

```java
package io.casehub.rag.crag;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.rag.crag")
public interface CragConfig {

    @WithDefault("0.7")
    double correctThreshold();

    @WithDefault("0.3")
    double incorrectThreshold();

    @WithDefault("3")
    int expansionMultiplier();
}
```

- [ ] **Step 4: Implement CorrectiveCaseRetriever**

Create `rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java`:

```java
package io.casehub.rag.crag;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.PayloadFilter;
import io.casehub.rag.RelevanceEvaluator;
import io.casehub.rag.RelevanceGrade;
import io.casehub.rag.RetrievalQuality;
import io.casehub.rag.RetrievedChunk;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.event.Event;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Decorator
@Priority(100)
public class CorrectiveCaseRetriever implements CaseRetriever {

    private final CaseRetriever delegate;
    private final RelevanceEvaluator evaluator;
    private final CragConfig config;
    private final Event<RetrievalQuality> qualityEvent;

    @Inject
    CorrectiveCaseRetriever(@Delegate @Any CaseRetriever delegate,
                            RelevanceEvaluator evaluator,
                            CragConfig config,
                            Event<RetrievalQuality> qualityEvent) {
        this.delegate = delegate;
        this.evaluator = evaluator;
        this.config = config;
        this.qualityEvent = qualityEvent;
    }

    @Override
    public List<RetrievedChunk> retrieve(String query, CorpusRef corpus,
                                          int maxResults, PayloadFilter filter) {
        List<RetrievedChunk> chunks = delegate.retrieve(query, corpus, maxResults, filter);
        int totalRetrieved = chunks.size();

        List<String> contents = chunks.stream().map(RetrievedChunk::content).toList();
        List<RelevanceGrade> grades = evaluator.evaluateBatch(query, contents);

        Set<String> seen = new HashSet<>();
        int correct = 0, ambiguous = 0, incorrect = 0;
        List<RetrievedChunk> graded = new ArrayList<>(chunks.size());
        for (int i = 0; i < chunks.size(); i++) {
            RelevanceGrade grade = grades.get(i);
            switch (grade) {
                case CORRECT   -> correct++;
                case AMBIGUOUS -> ambiguous++;
                case INCORRECT -> incorrect++;
                default -> {}
            }
            RetrievedChunk c = chunks.get(i);
            seen.add(dedupKey(c));
            graded.add(c.withGrade(grade));
        }

        List<RetrievedChunk> surviving = new ArrayList<>(graded.stream()
            .filter(c -> c.grade() != RelevanceGrade.INCORRECT)
            .toList());

        boolean expanded = false;
        if (surviving.size() < maxResults) {
            expanded = true;
            int expandedLimit = maxResults * config.expansionMultiplier();
            List<RetrievedChunk> expandedChunks = delegate.retrieve(
                query, corpus, expandedLimit, filter);

            List<RetrievedChunk> newChunks = expandedChunks.stream()
                .filter(c -> !seen.contains(dedupKey(c)))
                .toList();

            if (!newChunks.isEmpty()) {
                List<String> newContents = newChunks.stream()
                    .map(RetrievedChunk::content).toList();
                List<RelevanceGrade> newGrades = evaluator.evaluateBatch(query, newContents);

                totalRetrieved += newChunks.size();
                for (int i = 0; i < newChunks.size(); i++) {
                    RelevanceGrade grade = newGrades.get(i);
                    switch (grade) {
                        case CORRECT   -> correct++;
                        case AMBIGUOUS -> ambiguous++;
                        case INCORRECT -> incorrect++;
                        default -> {}
                    }
                    if (grade != RelevanceGrade.INCORRECT) {
                        surviving.add(newChunks.get(i).withGrade(grade));
                    }
                }
            }
        }

        surviving.sort(Comparator.comparingInt(
            (RetrievedChunk c) -> c.grade() == RelevanceGrade.CORRECT ? 0 : 1));
        List<RetrievedChunk> result = surviving.stream()
            .limit(maxResults)
            .toList();

        qualityEvent.fire(new RetrievalQuality(
            totalRetrieved, correct, ambiguous, incorrect, true, expanded));

        return result;
    }

    private static String dedupKey(RetrievedChunk c) {
        return c.sourceDocumentId() + "\0" + c.content().hashCode();
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-crag -Dtest=CorrectiveCaseRetrieverTest -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```
git add rag-crag/src/main/java/io/casehub/rag/crag/CragConfig.java \
       rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java \
       rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java
git commit -m "feat(#33): add CorrectiveCaseRetriever @Decorator — evaluate, filter, expand, grade-sort, quality event"
```

---

## Task 8: CragBeanProducer (rag-crag)

**Files:**
- Create: `rag-crag/src/main/java/io/casehub/rag/crag/CragBeanProducer.java`

- [ ] **Step 1: Create CragBeanProducer**

Create `rag-crag/src/main/java/io/casehub/rag/crag/CragBeanProducer.java`:

```java
package io.casehub.rag.crag;

import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.rag.RelevanceEvaluator;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.enterprise.inject.Produces;
import jakarta.inject.Inject;

@ApplicationScoped
public class CragBeanProducer {

    @Inject CragConfig config;
    @Inject Instance<CrossEncoderReranker> rerankerInstance;

    @Produces
    @ApplicationScoped
    RelevanceEvaluator evaluator() {
        if (!rerankerInstance.isResolvable()) {
            throw new IllegalStateException(
                "rag-crag requires a CrossEncoderReranker bean. "
                    + "Configure casehub.inference.models.<name> and produce a CrossEncoderReranker.");
        }
        return new CrossEncoderRelevanceEvaluator(
            rerankerInstance.get(),
            config.correctThreshold(),
            config.incorrectThreshold());
    }
}
```

- [ ] **Step 2: Commit**

```
git add rag-crag/src/main/java/io/casehub/rag/crag/CragBeanProducer.java
git commit -m "feat(#33): add CragBeanProducer — produces RelevanceEvaluator from CrossEncoderReranker + config thresholds"
```

---

## Task 9: Full build verification

**Files:**
- None created. Verification only.

- [ ] **Step 1: Build all modules without tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: BUILD SUCCESS — all modules compile including the new rag-crag.

- [ ] **Step 2: Run all tests (excluding Testcontainers-dependent tests)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -f /Users/mdproctor/claude/casehub/neural-text/pom.xml -Dtest='!*IT,!HybridCaseRetrieverTest,!ReactiveHybridCaseRetrieverTest'`

Expected: ALL PASS — rag-api, rag-testing, rag-crag, and rag non-Testcontainers tests all green.

- [ ] **Step 3: Run full rag module tests with Testcontainers (if Docker available)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -f /Users/mdproctor/claude/casehub/neural-text/pom.xml`

Expected: ALL PASS — HybridCaseRetrieverTest still passes with enriched RetrievedChunk (4-arg convenience constructor).

---

## Task 10: ARC42STORIES update

**Files:**
- Modify: `ARC42STORIES.MD`

- [ ] **Step 1: Add J4 journey, C10 chapter, L10 layer**

Add Journey J4 to the §9.1 journey overview table. Add C10 to the §9.2 chapter index table and flow diagram. Add L10 to the §5 layer table. Add C10 chapter entry to §9.3 and L10 layer entry to §9.4.

The content follows the spec's ARC42STORIES Update Plan section exactly.

- [ ] **Step 2: Commit**

```
git add ARC42STORIES.MD
git commit -m "docs(#33): add J4 Retrieval Quality journey, C10 CRAG chapter, L10 CRAG layer to ARC42STORIES"
```

---

## Deferred: ReactiveCorrectiveCaseRetriever

The reactive decorator mirrors the blocking logic with `Uni<>` chains and uses `qualityEvent.fireAsync()`. However, the spec notes that `@IfBuildProperty` on a `@Decorator` class is a **first-use pattern in this codebase** that needs verification during implementation. Rather than building both paths before verifying the CDI annotation composition works, implement the blocking decorator first (Tasks 1–9), verify the full pipeline, then add the reactive decorator as a follow-up. If `@IfBuildProperty` + `@Decorator` doesn't compose in Quarkus Arc, the fallback is a producer-based approach (same pattern as `ReactiveRagBeanProducer`).
