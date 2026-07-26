# ColBERT Evaluator + Correlation Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #62 — ColBertRelevanceEvaluator — CRAG compatibility via MAX_SIM scoring
**Issue group:** #62, #167

**Goal:** Fix the RelevanceEvaluator interface to support score-based evaluation (ColBERT),
eliminate the instanceof polymorphism violation in CRAG, and build the query-document-outcome
correlation graph for retrieval quality analysis.

**Architecture:** Collapse `RelevanceEvaluator` to a single chunk-aware method, move
`ScoredGrade` to `rag-api`, create `ColBertRelevanceEvaluator` as a score-threshold
mapper, and add correlation graph types + analysis methods to `RetrievalAnalyzer`.

**Tech Stack:** Java 21, Quarkus CDI, MicroProfile Config

## Global Constraints

- Java 21 language features (records, sealed, pattern matching)
- All new records use compact constructors with null/constraint validation
- Defensive copies on mutable collections (`Map.copyOf`, `List.copyOf`, `Set.copyOf`)
- `rag-api` is tier 1: zero framework dependencies, pure Java only
- Tests use JUnit 5 + AssertJ
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- IntelliJ MCP mandatory for all source file operations

---

### Task 1: Interface Foundation — ScoredGrade move + RelevanceEvaluator refactor

**Files:**
- Move: `rag-crossencoder/.../rag/crossencoder/ScoredGrade.java` → `rag-api/.../rag/ScoredGrade.java` (use `ide_move_file`)
- Modify: `rag-api/.../rag/RelevanceEvaluator.java`
- Modify: `rag-testing/.../rag/testing/InMemoryRelevanceEvaluator.java`
- Modify: `rag-api/src/test/.../rag/RelevanceEvaluatorTest.java`
- Modify: `rag-testing/src/test/.../rag/testing/InMemoryRelevanceEvaluatorTest.java`
- Test: existing tests refactored

**Interfaces:**
- Produces: `RelevanceEvaluator.evaluateChunks(String query, List<RetrievedChunk> chunks) → List<ScoredGrade>` — the sole interface method
- Produces: `ScoredGrade(RelevanceGrade grade, float score)` in `io.casehub.neocortex.rag` package
- Produces: `InMemoryRelevanceEvaluator.evaluateChunks()` — returns fixed grade with `Float.NaN` score

- [ ] **Step 1: Move ScoredGrade from rag-crossencoder to rag-api**

Use `ide_move_file` to move `ScoredGrade.java` from
`rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/`
to `rag-api/src/main/java/io/casehub/neocortex/rag/`.

This updates all import references across the project automatically.
Verify with `ide_diagnostics` on `rag-crossencoder` module after the move.

- [ ] **Step 2: Write failing test for new RelevanceEvaluator contract**

Replace `RelevanceEvaluatorTest` with tests for the new single-method interface:

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class RelevanceEvaluatorTest {

    @Test
    void evaluateChunksReturnsGradePerChunk() {
        RelevanceEvaluator evaluator = (query, chunks) -> chunks.stream()
            .map(c -> new ScoredGrade(RelevanceGrade.CORRECT, (float) c.relevanceScore()))
            .toList();

        var chunks = List.of(
            new RetrievedChunk("text1", "doc1", 0.9, Map.of()),
            new RetrievedChunk("text2", "doc2", 0.5, Map.of()));

        List<ScoredGrade> results = evaluator.evaluateChunks("query", chunks);

        assertThat(results).hasSize(2);
        assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
        assertThat(results.get(0).score()).isEqualTo(0.9f, within(0.001f));
    }

    @Test
    void evaluateChunksEmptyListReturnsEmpty() {
        RelevanceEvaluator evaluator = (query, chunks) -> List.of();
        assertThat(evaluator.evaluateChunks("query", List.of())).isEmpty();
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RelevanceEvaluatorTest`
Expected: FAIL — `evaluate()` and `evaluateBatch()` still exist, `evaluateChunks` doesn't.

- [ ] **Step 3: Refactor RelevanceEvaluator to single method**

Replace the interface body with:

```java
package io.casehub.neocortex.rag;

import java.util.List;

public interface RelevanceEvaluator {
    List<ScoredGrade> evaluateChunks(String query, List<RetrievedChunk> chunks);
}
```

This removes `evaluate(String, String)` and `evaluateBatch(String, List<String>)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RelevanceEvaluatorTest`
Expected: PASS

- [ ] **Step 5: Write failing test for InMemoryRelevanceEvaluator**

Replace `InMemoryRelevanceEvaluatorTest`:

```java
package io.casehub.neocortex.rag.testing;

import io.casehub.neocortex.rag.*;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class InMemoryRelevanceEvaluatorTest {

    @Test
    void defaultConstructorReturnsCorrect() {
        var evaluator = new InMemoryRelevanceEvaluator();
        var chunks = List.of(new RetrievedChunk("text", "doc1", 0.9, Map.of()));
        var results = evaluator.evaluateChunks("query", chunks);
        assertThat(results).hasSize(1);
        assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
        assertThat(results.get(0).score()).isNaN();
    }

    @Test
    void returningFactoryReturnsConfiguredGrade() {
        var evaluator = InMemoryRelevanceEvaluator.returning(RelevanceGrade.INCORRECT);
        var chunks = List.of(new RetrievedChunk("text", "doc1", 0.5, Map.of()));
        var results = evaluator.evaluateChunks("query", chunks);
        assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.INCORRECT);
    }

    @Test
    void evaluateChunksReturnsConfiguredGradeForAll() {
        var evaluator = InMemoryRelevanceEvaluator.returning(RelevanceGrade.AMBIGUOUS);
        var chunks = List.of(
            new RetrievedChunk("a", "d1", 0.9, Map.of()),
            new RetrievedChunk("b", "d2", 0.5, Map.of()));
        var results = evaluator.evaluateChunks("query", chunks);
        assertThat(results).hasSize(2);
        assertThat(results).allMatch(sg -> sg.grade() == RelevanceGrade.AMBIGUOUS);
        assertThat(results).allMatch(sg -> Float.isNaN(sg.score()));
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing -Dtest=InMemoryRelevanceEvaluatorTest`
Expected: FAIL — `InMemoryRelevanceEvaluator` still has old `evaluate()` method.

- [ ] **Step 6: Refactor InMemoryRelevanceEvaluator**

Replace the class body:

```java
package io.casehub.neocortex.rag.testing;

import io.casehub.neocortex.rag.*;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;
import java.util.List;

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
    public List<ScoredGrade> evaluateChunks(String query, List<RetrievedChunk> chunks) {
        return chunks.stream()
            .map(c -> new ScoredGrade(fixedGrade, Float.NaN))
            .toList();
    }
}
```

- [ ] **Step 7: Run tests to verify both pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api,rag-testing -Dtest="RelevanceEvaluatorTest,InMemoryRelevanceEvaluatorTest"`
Expected: PASS

- [ ] **Step 8: Verify no compilation errors across project**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -DskipTests`
Expected: FAIL in `rag-crossencoder` — `CrossEncoderRelevanceEvaluator` and
`CorrectiveCaseRetriever` still reference old interface. This is expected —
Tasks 3 and 4 fix them.

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add \
  rag-api/src/main/java/io/casehub/neocortex/rag/ScoredGrade.java \
  rag-api/src/main/java/io/casehub/neocortex/rag/RelevanceEvaluator.java \
  rag-api/src/test/java/io/casehub/neocortex/rag/RelevanceEvaluatorTest.java \
  rag-testing/src/main/java/io/casehub/neocortex/rag/testing/InMemoryRelevanceEvaluator.java \
  rag-testing/src/test/java/io/casehub/neocortex/rag/testing/InMemoryRelevanceEvaluatorTest.java
```

Message: `refactor(#62): collapse RelevanceEvaluator to single evaluateChunks() method, move ScoredGrade to rag-api`

---

### Task 2: ColBertRelevanceEvaluator

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/ColBertRelevanceEvaluator.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/ColBertRelevanceEvaluatorTest.java`

**Interfaces:**
- Consumes: `RelevanceEvaluator.evaluateChunks()`, `ScoredGrade`, `RetrievedChunk`, `RelevanceGrade` (all from Task 1)
- Produces: `ColBertRelevanceEvaluator(double correctThreshold, double incorrectThreshold)` — score-threshold mapper

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class ColBertRelevanceEvaluatorTest {

    private static final double CORRECT = 0.55;
    private static final double INCORRECT = 0.35;

    private final ColBertRelevanceEvaluator evaluator =
        new ColBertRelevanceEvaluator(CORRECT, INCORRECT);

    @ParameterizedTest
    @CsvSource({
        "0.9,  CORRECT",
        "0.55, CORRECT",
        "0.5,  AMBIGUOUS",
        "0.4,  AMBIGUOUS",
        "0.35, INCORRECT",
        "0.1,  INCORRECT",
        "0.0,  INCORRECT",
    })
    void gradeFromScore(double score, RelevanceGrade expected) {
        var chunks = List.of(new RetrievedChunk("text", "doc1", score, Map.of()));
        var results = evaluator.evaluateChunks("query", chunks);
        assertThat(results.get(0).grade()).isEqualTo(expected);
    }

    @Test
    void scoreIsPassedThrough() {
        var chunks = List.of(new RetrievedChunk("text", "doc1", 0.75, Map.of()));
        var results = evaluator.evaluateChunks("query", chunks);
        assertThat(results.get(0).score()).isEqualTo(0.75f, within(0.001f));
    }

    @Test
    void emptyChunksReturnsEmpty() {
        assertThat(evaluator.evaluateChunks("query", List.of())).isEmpty();
    }

    @Test
    void multipleChunksGradedIndependently() {
        var chunks = List.of(
            new RetrievedChunk("high", "d1", 0.8, Map.of()),
            new RetrievedChunk("mid", "d2", 0.45, Map.of()),
            new RetrievedChunk("low", "d3", 0.2, Map.of()));
        var results = evaluator.evaluateChunks("query", chunks);
        assertThat(results).extracting(ScoredGrade::grade)
            .containsExactly(RelevanceGrade.CORRECT, RelevanceGrade.AMBIGUOUS, RelevanceGrade.INCORRECT);
    }

    @Test
    void negativeScore() {
        var chunks = List.of(new RetrievedChunk("text", "d1", -0.5, Map.of()));
        var results = evaluator.evaluateChunks("query", chunks);
        assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.INCORRECT);
    }

    @Test
    void constructorRejectsInvertedThresholds() {
        assertThatThrownBy(() -> new ColBertRelevanceEvaluator(0.3, 0.7))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void equalThresholdsAllowed() {
        var eval = new ColBertRelevanceEvaluator(0.5, 0.5);
        var chunks = List.of(
            new RetrievedChunk("a", "d1", 0.5, Map.of()),
            new RetrievedChunk("b", "d2", 0.4, Map.of()));
        var results = eval.evaluateChunks("query", chunks);
        assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
        assertThat(results.get(1).grade()).isEqualTo(RelevanceGrade.INCORRECT);
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=ColBertRelevanceEvaluatorTest`
Expected: FAIL — class doesn't exist.

- [ ] **Step 2: Implement ColBertRelevanceEvaluator**

Create `rag-api/src/main/java/io/casehub/neocortex/rag/ColBertRelevanceEvaluator.java`:

```java
package io.casehub.neocortex.rag;

import java.util.List;

public final class ColBertRelevanceEvaluator implements RelevanceEvaluator {

    private final double correctThreshold;
    private final double incorrectThreshold;

    public ColBertRelevanceEvaluator(double correctThreshold, double incorrectThreshold) {
        if (incorrectThreshold > correctThreshold)
            throw new IllegalArgumentException(
                "incorrectThreshold (" + incorrectThreshold
                    + ") must not exceed correctThreshold (" + correctThreshold + ")");
        this.correctThreshold = correctThreshold;
        this.incorrectThreshold = incorrectThreshold;
    }

    @Override
    public List<ScoredGrade> evaluateChunks(String query, List<RetrievedChunk> chunks) {
        return chunks.stream()
            .map(c -> new ScoredGrade(
                gradeFromScore(c.relevanceScore()),
                (float) c.relevanceScore()))
            .toList();
    }

    private RelevanceGrade gradeFromScore(double score) {
        if (score >= correctThreshold)   return RelevanceGrade.CORRECT;
        if (score <= incorrectThreshold) return RelevanceGrade.INCORRECT;
        return RelevanceGrade.AMBIGUOUS;
    }
}
```

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=ColBertRelevanceEvaluatorTest`
Expected: PASS

- [ ] **Step 4: Commit**

Message: `feat(#62): add ColBertRelevanceEvaluator — score-threshold mapper for CRAG`

---

### Task 3: CrossEncoderRelevanceEvaluator refactor

**Files:**
- Modify: `rag-crossencoder/.../crossencoder/corrective/CrossEncoderRelevanceEvaluator.java`
- Modify: `rag-crossencoder/src/test/.../crossencoder/corrective/CrossEncoderRelevanceEvaluatorTest.java`

**Interfaces:**
- Consumes: `RelevanceEvaluator.evaluateChunks()`, `ScoredGrade`, `RetrievedChunk` (from Task 1)
- Produces: `CrossEncoderRelevanceEvaluator.evaluateChunks()` — runs ONNX reranker inference on chunk content

- [ ] **Step 1: Write failing test for evaluateChunks**

Add to `CrossEncoderRelevanceEvaluatorTest`:

```java
@Test
void evaluateChunksExtractsContentAndGrades() {
    var model = contentScoringModel(Map.of("good", 0.9f, "bad", 0.1f));
    var reranker = new CrossEncoderReranker(model);
    var evaluator = new CrossEncoderRelevanceEvaluator(reranker, 0.7, 0.3);

    var chunks = List.of(
        new RetrievedChunk("good", "d1", 0.5, Map.of()),
        new RetrievedChunk("bad", "d2", 0.5, Map.of()));
    var results = evaluator.evaluateChunks("query", chunks);

    assertThat(results).hasSize(2);
    assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
    assertThat(results.get(0).score()).isEqualTo(0.9f, within(0.01f));
    assertThat(results.get(1).grade()).isEqualTo(RelevanceGrade.INCORRECT);
}

@Test
void evaluateChunksEmptyReturnsEmpty() {
    var model = contentScoringModel(Map.of());
    var reranker = new CrossEncoderReranker(model);
    var evaluator = new CrossEncoderRelevanceEvaluator(reranker, 0.7, 0.3);
    assertThat(evaluator.evaluateChunks("query", List.of())).isEmpty();
}
```

Update imports: `ScoredGrade` now from `io.casehub.neocortex.rag.ScoredGrade`,
add `RetrievedChunk` import.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-crossencoder -Dtest=CrossEncoderRelevanceEvaluatorTest -Dtest.include="evaluateChunks*"`
Expected: FAIL — method doesn't exist.

- [ ] **Step 2: Refactor CrossEncoderRelevanceEvaluator**

Replace the class to implement `evaluateChunks()` as the sole interface method.
Remove `evaluate()`, `evaluateBatch()`, and `evaluateBatchWithScores()`:

```java
package io.casehub.neocortex.rag.crossencoder.corrective;

import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.inference.tasks.RankedResult;
import io.casehub.neocortex.rag.*;
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
    public List<ScoredGrade> evaluateChunks(String query, List<RetrievedChunk> chunks) {
        if (chunks.isEmpty()) return List.of();
        List<String> contents = chunks.stream()
            .map(RetrievedChunk::content).toList();
        List<RankedResult> ranked = reranker.rerank(query, contents);
        ScoredGrade[] results = new ScoredGrade[contents.size()];
        for (RankedResult r : ranked) {
            results[r.originalIndex()] = new ScoredGrade(
                gradeFromScore(r.score()), r.score());
        }
        return List.of(results);
    }

    private RelevanceGrade gradeFromScore(float score) {
        if (score >= (float) correctThreshold) return RelevanceGrade.CORRECT;
        if (score <= (float) incorrectThreshold) return RelevanceGrade.INCORRECT;
        return RelevanceGrade.AMBIGUOUS;
    }
}
```

- [ ] **Step 3: Update existing tests**

Refactor tests that used `evaluate()`, `evaluateBatch()`, `evaluateBatchWithScores()`
to use `evaluateChunks()`. The threshold tests (`scoreAboveCorrectThresholdReturnsCorrect`
etc.) should create single-element chunk lists and assert grades. Replace
`evaluatorReturningScore` helper to build a chunk with a dummy content that maps to
the desired cross-encoder score.

Remove tests for `evaluateBatch` and `evaluateBatchWithScores` — those methods no longer exist.

- [ ] **Step 4: Run all CrossEncoder tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-crossencoder -Dtest=CrossEncoderRelevanceEvaluatorTest`
Expected: PASS

- [ ] **Step 5: Commit**

Message: `refactor(#62): CrossEncoderRelevanceEvaluator implements evaluateChunks()`

---

### Task 4: CRAG refactor + CDI wiring

**Files:**
- Modify: `rag-crossencoder/.../corrective/CorrectiveCaseRetriever.java`
- Modify: `rag-crossencoder/.../corrective/CragConfig.java`
- Modify: `rag-crossencoder/.../CrossEncoderBeanProducer.java`
- Modify: `rag-crossencoder/src/test/.../corrective/CorrectiveCaseRetrieverTest.java`
- Create: `rag-crossencoder/src/test/.../CrossEncoderBeanProducerTest.java`
- Test: all CRAG tests

**Interfaces:**
- Consumes: `RelevanceEvaluator.evaluateChunks()` (Task 1), `ColBertRelevanceEvaluator` (Task 2), `CrossEncoderRelevanceEvaluator.evaluateChunks()` (Task 3)
- Produces: `CragConfig.ColBertConfig` sub-group, `CrossEncoderBeanProducer` with fallback

- [ ] **Step 1: Add ColBertConfig to CragConfig**

```java
@ConfigMapping(prefix = "casehub.rag.crag")
public interface CragConfig {

    @WithDefault("0.7")
    double correctThreshold();

    @WithDefault("0.3")
    double incorrectThreshold();

    @WithDefault("3")
    int expansionMultiplier();

    @WithDefault("false")
    boolean enabled();

    ColBertConfig colbert();

    interface ColBertConfig {
        @WithDefault("0.55")
        double correctThreshold();

        @WithDefault("0.35")
        double incorrectThreshold();
    }
}
```

- [ ] **Step 2: Refactor CorrectiveCaseRetriever — eliminate instanceof**

Replace the `retrieve()` method body. Key changes:
1. Replace `evaluator.evaluateBatch(query.text(), contents)` → `evaluator.evaluateChunks(query.text(), chunks)`
2. Remove `instanceof CrossEncoderRelevanceEvaluator` check
3. Extract scores from `ScoredGrade` list — use NaN check for reranking
4. Same for the expansion path

The `hasUsableScores` and `extractScores` helpers:

```java
private static boolean hasUsableScores(List<ScoredGrade> scored) {
    return !scored.isEmpty() && !Float.isNaN(scored.get(0).score());
}

private static float[] extractScores(List<ScoredGrade> scored) {
    float[] scores = new float[scored.size()];
    for (int i = 0; i < scored.size(); i++) {
        scores[i] = scored.get(i).score();
    }
    return scores;
}
```

Remove `import io.casehub.neocortex.rag.crossencoder.corrective.CrossEncoderRelevanceEvaluator`
from the class (no longer needed — no instanceof check).

- [ ] **Step 3: Update CorrectiveCaseRetrieverTest**

Refactor helper methods for the new interface:

```java
private static RelevanceEvaluator gradeByContent(Map<String, RelevanceGrade> contentToGrade) {
    return (query, chunks) -> chunks.stream()
        .map(c -> new ScoredGrade(
            contentToGrade.getOrDefault(c.content(), RelevanceGrade.UNGRADED),
            Float.NaN))
        .toList();
}
```

Update `alreadyGradedChunksPassThrough` — the evaluator lambda:
```java
RelevanceEvaluator evaluator = (query, chunks) -> {
    evaluatorCalled.set(true);
    return chunks.stream()
        .map(c -> new ScoredGrade(RelevanceGrade.CORRECT, Float.NaN))
        .toList();
};
```

Update `evaluatesAgainstOriginalQueryNotExpansion` — the capturing evaluator:
```java
RelevanceEvaluator capturingEvaluator = (query, chunks) -> {
    capturedQuery.set(query);
    return chunks.stream()
        .map(c -> new ScoredGrade(RelevanceGrade.CORRECT, Float.NaN))
        .toList();
};
```

Update `stubConfig` to include `ColBertConfig`:
```java
private static CragConfig stubConfig(int expansionMultiplier) {
    return new CragConfig() {
        @Override public double correctThreshold() { return 0.7; }
        @Override public double incorrectThreshold() { return 0.3; }
        @Override public int expansionMultiplier() { return expansionMultiplier; }
        @Override public boolean enabled() { return true; }
        @Override public ColBertConfig colbert() {
            return new ColBertConfig() {
                @Override public double correctThreshold() { return 0.55; }
                @Override public double incorrectThreshold() { return 0.35; }
            };
        }
    };
}
```

- [ ] **Step 4: Run all CRAG tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-crossencoder -Dtest=CorrectiveCaseRetrieverTest`
Expected: PASS

- [ ] **Step 5: Refactor CrossEncoderBeanProducer with ColBERT fallback**

```java
@ApplicationScoped
public class CrossEncoderBeanProducer {

    private static final org.jboss.logging.Logger LOG =
        org.jboss.logging.Logger.getLogger(CrossEncoderBeanProducer.class);

    @Inject CragConfig config;
    @Inject Instance<CrossEncoderReranker> rerankerInstance;

    @ConfigProperty(name = "casehub.rag.retrieval.rerank-enabled",
                    defaultValue = "false")
    boolean rerankEnabled;

    @Produces
    @ApplicationScoped
    RelevanceEvaluator evaluator() {
        if (rerankerInstance.isResolvable()) {
            return new CrossEncoderRelevanceEvaluator(
                rerankerInstance.get(),
                config.correctThreshold(),
                config.incorrectThreshold());
        }
        if (!rerankEnabled) {
            throw new IllegalStateException(
                "No CrossEncoderReranker available and ColBERT reranking "
                + "is not enabled (casehub.rag.retrieval.rerank-enabled"
                + "=false). Configure a cross-encoder model or enable "
                + "ColBERT reranking.");
        }
        LOG.infof("No CrossEncoderReranker — using ColBertRelevanceEvaluator "
            + "(correct >= %.2f, incorrect <= %.2f)",
            config.colbert().correctThreshold(),
            config.colbert().incorrectThreshold());
        return new ColBertRelevanceEvaluator(
            config.colbert().correctThreshold(),
            config.colbert().incorrectThreshold());
    }
}
```

Add import: `import org.eclipse.microprofile.config.inject.ConfigProperty;`

- [ ] **Step 6: Full module build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-api,rag-testing,rag-crossencoder -DskipTests`
Expected: PASS — compilation clean across all three modules.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api,rag-testing,rag-crossencoder`
Expected: PASS — all tests green.

- [ ] **Step 7: Commit**

Message: `feat(#62): CRAG uses evaluateChunks() polymorphically, ColBERT fallback in CDI producer`

---

### Task 5: Correlation graph value types + builder

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/EdgeStats.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/QueryNode.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/DocumentNode.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/CorrelationGraph.java`
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/CorrelationGraphTest.java`

**Interfaces:**
- Consumes: `RetrievalTracker`, `RetrievalRecord`, `RetrievalFeedback`, `RetrievalOutcome`, `CorpusRef` (existing rag-api types)
- Produces: `CorrelationGraph`, `QueryNode`, `DocumentNode`, `EdgeStats` records; `RetrievalAnalyzer.correlationGraph()` static method

- [ ] **Step 1: Write failing tests for value types and builder**

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class CorrelationGraphTest {

    private static final CorpusRef CORPUS = new CorpusRef("t1", "c1");
    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");
    private static final Instant T1 = T0.plusSeconds(60);
    private static final Instant SINCE = T0.minusSeconds(1);
    private static final Instant UNTIL = T1.plusSeconds(1);

    @Test
    void emptyTrackerProducesEmptyGraph() {
        var tracker = stubTracker(List.of(), List.of());
        var graph = RetrievalAnalyzer.correlationGraph(tracker, CORPUS, SINCE, UNTIL);
        assertThat(graph.queries()).isEmpty();
        assertThat(graph.documents()).isEmpty();
    }

    @Test
    void singleQuerySingleDocument() {
        var records = List.of(record("what is X", T0, doc("doc1", 0.9)));
        var tracker = stubTracker(records, List.of());
        var graph = RetrievalAnalyzer.correlationGraph(tracker, CORPUS, SINCE, UNTIL);

        assertThat(graph.queries()).hasSize(1);
        assertThat(graph.documents()).hasSize(1);

        var qNode = graph.queries().get("what is x");
        assertThat(qNode.retrievalCount()).isEqualTo(1);
        assertThat(qNode.documentEdges()).containsKey("doc1");

        var edge = qNode.documentEdges().get("doc1");
        assertThat(edge.coOccurrenceCount()).isEqualTo(1);
        assertThat(edge.averageScore()).isEqualTo(0.9, within(0.001));
    }

    @Test
    void queryTextNormalized() {
        var records = List.of(
            record("What is X", T0, doc("doc1", 0.9)),
            record("  what is x  ", T1, doc("doc1", 0.8)));
        var tracker = stubTracker(records, List.of());
        var graph = RetrievalAnalyzer.correlationGraph(tracker, CORPUS, SINCE, UNTIL);

        assertThat(graph.queries()).hasSize(1);
        var qNode = graph.queries().get("what is x");
        assertThat(qNode.retrievalCount()).isEqualTo(2);
        assertThat(qNode.documentEdges().get("doc1").coOccurrenceCount()).isEqualTo(2);
        assertThat(qNode.documentEdges().get("doc1").averageScore())
            .isEqualTo(0.85, within(0.001));
    }

    @Test
    void feedbackAccumulatesInEdge() {
        var records = List.of(record("query", T0, doc("doc1", 0.9)));
        var feedback = List.of(
            new RetrievalFeedback("r1", "doc1", RetrievalOutcome.RELEVANT, T0),
            new RetrievalFeedback("r1", "doc1", RetrievalOutcome.HIGHLY_RELEVANT, T0));
        var tracker = stubTracker(records, feedback);
        var graph = RetrievalAnalyzer.correlationGraph(tracker, CORPUS, SINCE, UNTIL);

        var edge = graph.queries().get("query").documentEdges().get("doc1");
        assertThat(edge.outcomeDistribution())
            .containsEntry(RetrievalOutcome.RELEVANT, 1)
            .containsEntry(RetrievalOutcome.HIGHLY_RELEVANT, 1);
    }

    @Test
    void dualIndexConsistency() {
        var records = List.of(
            record("q1", T0, doc("doc1", 0.9), doc("doc2", 0.7)),
            record("q2", T1, doc("doc1", 0.8)));
        var tracker = stubTracker(records, List.of());
        var graph = RetrievalAnalyzer.correlationGraph(tracker, CORPUS, SINCE, UNTIL);

        assertThat(graph.queries()).hasSize(2);
        assertThat(graph.documents()).hasSize(2);

        var doc1 = graph.documents().get("doc1");
        assertThat(doc1.retrievalCount()).isEqualTo(2);
        assertThat(doc1.queryEdges()).containsKeys("q1", "q2");
    }

    @Test
    void edgeStatsDefensiveCopy() {
        var mutable = new HashMap<RetrievalOutcome, Integer>();
        mutable.put(RetrievalOutcome.RELEVANT, 1);
        var edge = new EdgeStats(1, 0.9, mutable);
        mutable.put(RetrievalOutcome.NOT_RELEVANT, 5);
        assertThat(edge.outcomeDistribution()).doesNotContainKey(RetrievalOutcome.NOT_RELEVANT);
    }

    @Test
    void edgeStatsValidation() {
        assertThatThrownBy(() -> new EdgeStats(0, 0.9, Map.of()))
            .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new EdgeStats(1, 0.9, null))
            .isInstanceOf(IllegalArgumentException.class);
    }

    // -- helpers --

    private static RetrievalRecord record(String queryText, Instant ts,
                                           RetrievedDocumentRef... docs) {
        return new RetrievalRecord(
            "r" + ts.toEpochMilli(), RetrievalQuery.of(queryText),
            CORPUS, List.of(docs), 10, ts);
    }

    private static RetrievedDocumentRef doc(String id, double score) {
        return new RetrievedDocumentRef(id, score);
    }

    private static RetrievalTracker stubTracker(List<RetrievalRecord> records,
                                                 List<RetrievalFeedback> feedback) {
        return new RetrievalTracker() {
            @Override public String record(RetrievalQuery q, CorpusRef c,
                    List<RetrievedChunk> r, int m) { return "stub"; }
            @Override public void feedback(String rid, String docId,
                    RetrievalOutcome o) {}
            @Override public List<RetrievalRecord> findRecords(CorpusRef c,
                    Instant s, Instant u) { return records; }
            @Override public List<RetrievalFeedback> findFeedback(CorpusRef c,
                    Instant s, Instant u) { return feedback; }
            @Override public Set<String> findRetrievedDocumentIds(CorpusRef c,
                    Instant s, Instant u) { return Set.of(); }
            @Override public int purgeOlderThan(Instant cutoff) { return 0; }
        };
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=CorrelationGraphTest`
Expected: FAIL — types don't exist.

- [ ] **Step 2: Create value type records**

Create `EdgeStats.java`:
```java
package io.casehub.neocortex.rag;

import java.util.Map;

public record EdgeStats(
    int coOccurrenceCount,
    double averageScore,
    Map<RetrievalOutcome, Integer> outcomeDistribution
) {
    public EdgeStats {
        if (coOccurrenceCount < 1)
            throw new IllegalArgumentException("coOccurrenceCount must be positive");
        if (outcomeDistribution == null)
            throw new IllegalArgumentException("outcomeDistribution must not be null");
        outcomeDistribution = Map.copyOf(outcomeDistribution);
    }
}
```

Create `QueryNode.java`:
```java
package io.casehub.neocortex.rag;

import java.util.Map;

public record QueryNode(
    String queryText,
    int retrievalCount,
    Map<String, EdgeStats> documentEdges
) {
    public QueryNode {
        if (queryText == null || queryText.isBlank())
            throw new IllegalArgumentException("queryText must not be null or blank");
        if (retrievalCount < 1)
            throw new IllegalArgumentException("retrievalCount must be positive");
        if (documentEdges == null)
            throw new IllegalArgumentException("documentEdges must not be null");
        documentEdges = Map.copyOf(documentEdges);
    }
}
```

Create `DocumentNode.java`:
```java
package io.casehub.neocortex.rag;

import java.util.Map;

public record DocumentNode(
    String documentId,
    int retrievalCount,
    Map<String, EdgeStats> queryEdges
) {
    public DocumentNode {
        if (documentId == null || documentId.isBlank())
            throw new IllegalArgumentException("documentId must not be null or blank");
        if (retrievalCount < 1)
            throw new IllegalArgumentException("retrievalCount must be positive");
        if (queryEdges == null)
            throw new IllegalArgumentException("queryEdges must not be null");
        queryEdges = Map.copyOf(queryEdges);
    }
}
```

Create `CorrelationGraph.java`:
```java
package io.casehub.neocortex.rag;

import java.util.Map;

public record CorrelationGraph(
    Map<String, QueryNode> queries,
    Map<String, DocumentNode> documents
) {
    public CorrelationGraph {
        if (queries == null)
            throw new IllegalArgumentException("queries must not be null");
        if (documents == null)
            throw new IllegalArgumentException("documents must not be null");
        queries = Map.copyOf(queries);
        documents = Map.copyOf(documents);
    }
}
```

- [ ] **Step 3: Implement correlationGraph() on RetrievalAnalyzer**

Add to `RetrievalAnalyzer`:

```java
public static CorrelationGraph correlationGraph(
        RetrievalTracker tracker, CorpusRef corpus,
        Instant since, Instant until) {

    List<RetrievalRecord> records = tracker.findRecords(corpus, since, until);
    List<RetrievalFeedback> allFeedback = tracker.findFeedback(corpus, since, until);

    if (records.isEmpty()) {
        return new CorrelationGraph(Map.of(), Map.of());
    }

    Set<String> inWindowRetrievalIds = new HashSet<>();
    for (RetrievalRecord r : records) {
        inWindowRetrievalIds.add(r.retrievalId());
    }

    Map<String, List<RetrievalOutcome>> feedbackIndex = new HashMap<>();
    for (RetrievalFeedback fb : allFeedback) {
        if (inWindowRetrievalIds.contains(fb.retrievalId())) {
            feedbackIndex.computeIfAbsent(
                fb.retrievalId() + "\0" + fb.sourceDocumentId(),
                k -> new ArrayList<>()).add(fb.outcome());
        }
    }

    Map<String, Integer> queryRetrievalCount = new HashMap<>();
    Map<String, Map<String, List<Double>>> queryDocScores = new HashMap<>();
    Map<String, Map<String, Map<RetrievalOutcome, Integer>>> queryDocOutcomes = new HashMap<>();

    for (RetrievalRecord r : records) {
        String qKey = r.query().text().strip().toLowerCase();
        queryRetrievalCount.merge(qKey, 1, Integer::sum);

        for (RetrievedDocumentRef doc : r.documents()) {
            queryDocScores
                .computeIfAbsent(qKey, k -> new HashMap<>())
                .computeIfAbsent(doc.sourceDocumentId(), k -> new ArrayList<>())
                .add(doc.relevanceScore());

            String fbKey = r.retrievalId() + "\0" + doc.sourceDocumentId();
            List<RetrievalOutcome> outcomes = feedbackIndex.getOrDefault(fbKey, List.of());
            for (RetrievalOutcome outcome : outcomes) {
                queryDocOutcomes
                    .computeIfAbsent(qKey, k -> new HashMap<>())
                    .computeIfAbsent(doc.sourceDocumentId(), k -> new EnumMap<>(RetrievalOutcome.class))
                    .merge(outcome, 1, Integer::sum);
            }
        }
    }

    Map<String, Map<String, EdgeStats>> queryEdgeMap = new LinkedHashMap<>();
    for (var qEntry : queryDocScores.entrySet()) {
        String qKey = qEntry.getKey();
        Map<String, EdgeStats> edges = new LinkedHashMap<>();
        for (var dEntry : qEntry.getValue().entrySet()) {
            String docId = dEntry.getKey();
            List<Double> scores = dEntry.getValue();
            int count = scores.size();
            double avg = scores.stream().mapToDouble(Double::doubleValue).average().orElse(0.0);
            Map<RetrievalOutcome, Integer> dist = queryDocOutcomes
                .getOrDefault(qKey, Map.of())
                .getOrDefault(docId, Map.of());
            edges.put(docId, new EdgeStats(count, avg, dist));
        }
        queryEdgeMap.put(qKey, edges);
    }

    Map<String, QueryNode> queryNodes = new LinkedHashMap<>();
    for (var entry : queryEdgeMap.entrySet()) {
        String qKey = entry.getKey();
        queryNodes.put(qKey, new QueryNode(
            qKey, queryRetrievalCount.get(qKey), entry.getValue()));
    }

    Map<String, Map<String, EdgeStats>> docEdgeMap = new LinkedHashMap<>();
    Map<String, Integer> docRetrievalCount = new HashMap<>();
    for (var qEntry : queryEdgeMap.entrySet()) {
        String qKey = qEntry.getKey();
        for (var dEntry : qEntry.getValue().entrySet()) {
            String docId = dEntry.getKey();
            docEdgeMap.computeIfAbsent(docId, k -> new LinkedHashMap<>())
                .put(qKey, dEntry.getValue());
            docRetrievalCount.merge(docId,
                dEntry.getValue().coOccurrenceCount(), Integer::sum);
        }
    }

    Map<String, DocumentNode> documentNodes = new LinkedHashMap<>();
    for (var entry : docEdgeMap.entrySet()) {
        documentNodes.put(entry.getKey(), new DocumentNode(
            entry.getKey(), docRetrievalCount.get(entry.getKey()),
            entry.getValue()));
    }

    return new CorrelationGraph(queryNodes, documentNodes);
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=CorrelationGraphTest`
Expected: PASS

- [ ] **Step 5: Commit**

Message: `feat(#167): correlation graph value types + builder on RetrievalAnalyzer`

---

### Task 6: Correlation analysis — queryClusters + documentImpact

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/QueryCluster.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/DocumentImpact.java`
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/QueryClusterTest.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/DocumentImpactTest.java`

**Interfaces:**
- Consumes: `CorrelationGraph`, `QueryNode`, `DocumentNode`, `EdgeStats` (Task 5)
- Produces: `QueryCluster`, `DocumentImpact` records; `RetrievalAnalyzer.queryClusters()`, `RetrievalAnalyzer.documentImpact()` static methods

- [ ] **Step 1: Write failing tests for queryClusters**

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class QueryClusterTest {

    @Test
    void overlappingQueriesCluster() {
        var graph = graphWith(
            qNode("q1", "doc1", "doc2", "doc3"),
            qNode("q2", "doc1", "doc2", "doc4"));
        // Jaccard(q1,q2) = |{doc1,doc2}| / |{doc1,doc2,doc3,doc4}| = 2/4 = 0.5
        var clusters = RetrievalAnalyzer.queryClusters(graph, 0.4);
        assertThat(clusters).hasSize(1);
        assertThat(clusters.get(0).queryTexts()).containsExactlyInAnyOrder("q1", "q2");
        assertThat(clusters.get(0).sharedDocumentIds()).containsExactlyInAnyOrder("doc1", "doc2");
        assertThat(clusters.get(0).jaccardSimilarity()).isEqualTo(0.5, within(0.001));
    }

    @Test
    void disjointQueriesDoNotCluster() {
        var graph = graphWith(
            qNode("q1", "doc1"),
            qNode("q2", "doc2"));
        var clusters = RetrievalAnalyzer.queryClusters(graph, 0.1);
        assertThat(clusters).isEmpty();
    }

    @Test
    void thresholdBoundary() {
        var graph = graphWith(
            qNode("q1", "doc1", "doc2"),
            qNode("q2", "doc1", "doc3"));
        // Jaccard = 1/3 ≈ 0.333
        assertThat(RetrievalAnalyzer.queryClusters(graph, 0.34)).isEmpty();
        assertThat(RetrievalAnalyzer.queryClusters(graph, 0.33)).hasSize(1);
    }

    @Test
    void transitiveClusteringMinPairwiseJaccard() {
        var graph = graphWith(
            qNode("q1", "doc1", "doc2"),
            qNode("q2", "doc1", "doc2", "doc3"),
            qNode("q3", "doc2", "doc3"));
        // J(q1,q2) = 2/3, J(q2,q3) = 2/3, J(q1,q3) = 1/3
        var clusters = RetrievalAnalyzer.queryClusters(graph, 0.5);
        assertThat(clusters).hasSize(1);
        assertThat(clusters.get(0).queryTexts()).containsExactlyInAnyOrder("q1", "q2", "q3");
        // Min pairwise = J(q1,q3) = 1/3
        assertThat(clusters.get(0).jaccardSimilarity()).isLessThan(0.5);
    }

    @Test
    void singleQueryNoCluster() {
        var graph = graphWith(qNode("q1", "doc1"));
        assertThat(RetrievalAnalyzer.queryClusters(graph, 0.0)).isEmpty();
    }

    @Test
    void emptyGraphNoCluster() {
        var graph = new CorrelationGraph(Map.of(), Map.of());
        assertThat(RetrievalAnalyzer.queryClusters(graph, 0.0)).isEmpty();
    }

    @Test
    void queryClusterValidation() {
        assertThatThrownBy(() -> new QueryCluster(Set.of("q1"), 0.5, Set.of("d1")))
            .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new QueryCluster(Set.of("q1", "q2"), -0.1, Set.of()))
            .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new QueryCluster(Set.of("q1", "q2"), 1.1, Set.of()))
            .isInstanceOf(IllegalArgumentException.class);
    }

    // -- helpers --

    private static QueryNode qNode(String query, String... docIds) {
        Map<String, EdgeStats> edges = new LinkedHashMap<>();
        for (String docId : docIds) {
            edges.put(docId, new EdgeStats(1, 0.8, Map.of()));
        }
        return new QueryNode(query, 1, edges);
    }

    private static CorrelationGraph graphWith(QueryNode... nodes) {
        Map<String, QueryNode> queries = new LinkedHashMap<>();
        Map<String, DocumentNode> documents = new LinkedHashMap<>();
        for (QueryNode qn : nodes) {
            queries.put(qn.queryText(), qn);
            for (var edge : qn.documentEdges().entrySet()) {
                documents.computeIfAbsent(edge.getKey(),
                    k -> new DocumentNode(k, 1, Map.of(qn.queryText(), edge.getValue())));
            }
        }
        return new CorrelationGraph(queries, documents);
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=QueryClusterTest`
Expected: FAIL — `QueryCluster` doesn't exist.

- [ ] **Step 2: Create QueryCluster record**

```java
package io.casehub.neocortex.rag;

import java.util.Set;

public record QueryCluster(
    Set<String> queryTexts,
    double jaccardSimilarity,
    Set<String> sharedDocumentIds
) {
    public QueryCluster {
        if (queryTexts == null || queryTexts.size() < 2)
            throw new IllegalArgumentException("queryTexts must contain at least 2 queries");
        if (jaccardSimilarity < 0.0 || jaccardSimilarity > 1.0)
            throw new IllegalArgumentException("jaccardSimilarity must be in [0, 1]");
        if (sharedDocumentIds == null)
            throw new IllegalArgumentException("sharedDocumentIds must not be null");
        queryTexts = Set.copyOf(queryTexts);
        sharedDocumentIds = Set.copyOf(sharedDocumentIds);
    }
}
```

- [ ] **Step 3: Implement queryClusters() on RetrievalAnalyzer**

```java
public static List<QueryCluster> queryClusters(
        CorrelationGraph graph, double jaccardThreshold) {

    List<String> queryKeys = new ArrayList<>(graph.queries().keySet());
    int n = queryKeys.size();
    if (n < 2) return List.of();

    Map<String, Set<String>> docSets = new HashMap<>();
    for (var entry : graph.queries().entrySet()) {
        docSets.put(entry.getKey(), entry.getValue().documentEdges().keySet());
    }

    // Build adjacency for connected components
    Map<String, Set<String>> adj = new HashMap<>();
    for (int i = 0; i < n; i++) {
        for (int j = i + 1; j < n; j++) {
            String qi = queryKeys.get(i), qj = queryKeys.get(j);
            double sim = jaccard(docSets.get(qi), docSets.get(qj));
            if (sim >= jaccardThreshold) {
                adj.computeIfAbsent(qi, k -> new HashSet<>()).add(qj);
                adj.computeIfAbsent(qj, k -> new HashSet<>()).add(qi);
            }
        }
    }

    // Find connected components via BFS
    Set<String> visited = new HashSet<>();
    List<QueryCluster> clusters = new ArrayList<>();
    for (String q : queryKeys) {
        if (visited.contains(q) || !adj.containsKey(q)) continue;
        Set<String> component = new LinkedHashSet<>();
        Deque<String> queue = new ArrayDeque<>();
        queue.add(q);
        while (!queue.isEmpty()) {
            String cur = queue.poll();
            if (!visited.add(cur)) continue;
            component.add(cur);
            Set<String> neighbors = adj.getOrDefault(cur, Set.of());
            for (String nb : neighbors) {
                if (!visited.contains(nb)) queue.add(nb);
            }
        }
        if (component.size() >= 2) {
            // Min pairwise Jaccard
            double minSim = 1.0;
            List<String> members = new ArrayList<>(component);
            for (int i = 0; i < members.size(); i++) {
                for (int j = i + 1; j < members.size(); j++) {
                    double sim = jaccard(docSets.get(members.get(i)),
                                         docSets.get(members.get(j)));
                    minSim = Math.min(minSim, sim);
                }
            }
            // Shared docs = intersection of all members
            Set<String> shared = new HashSet<>(docSets.get(members.get(0)));
            for (int i = 1; i < members.size(); i++) {
                shared.retainAll(docSets.get(members.get(i)));
            }
            clusters.add(new QueryCluster(component, minSim, shared));
        }
    }
    clusters.sort(Comparator.comparingDouble(QueryCluster::jaccardSimilarity).reversed());
    return clusters;
}

private static double jaccard(Set<String> a, Set<String> b) {
    if (a.isEmpty() && b.isEmpty()) return 0.0;
    Set<String> intersection = new HashSet<>(a);
    intersection.retainAll(b);
    Set<String> union = new HashSet<>(a);
    union.addAll(b);
    return (double) intersection.size() / union.size();
}
```

- [ ] **Step 4: Run queryClusters tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=QueryClusterTest`
Expected: PASS

- [ ] **Step 5: Write failing tests for documentImpact**

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class DocumentImpactTest {

    @Test
    void rankedByCentrality() {
        var graph = graphWith(
            qNode("q1", Map.of("doc1", 0.9, "doc2", 0.7)),
            qNode("q2", Map.of("doc1", 0.8)),
            qNode("q3", Map.of("doc1", 0.85, "doc2", 0.6, "doc3", 0.5)));

        var impact = RetrievalAnalyzer.documentImpact(graph);

        assertThat(impact).hasSize(3);
        assertThat(impact.get(0).documentId()).isEqualTo("doc1");
        assertThat(impact.get(0).distinctQueryCount()).isEqualTo(3);
        assertThat(impact.get(0).totalRetrievals()).isEqualTo(3);
        assertThat(impact.get(1).documentId()).isEqualTo("doc2");
        assertThat(impact.get(1).distinctQueryCount()).isEqualTo(2);
    }

    @Test
    void outcomeAggregation() {
        var outcomes1 = Map.of(RetrievalOutcome.RELEVANT, 2);
        var outcomes2 = Map.of(RetrievalOutcome.RELEVANT, 1,
                               RetrievalOutcome.NOT_RELEVANT, 1);
        var graph = graphWith(
            qNodeWithOutcomes("q1", "doc1", 0.9, outcomes1),
            qNodeWithOutcomes("q2", "doc1", 0.8, outcomes2));

        var impact = RetrievalAnalyzer.documentImpact(graph);

        assertThat(impact.get(0).aggregateOutcomes())
            .containsEntry(RetrievalOutcome.RELEVANT, 3)
            .containsEntry(RetrievalOutcome.NOT_RELEVANT, 1);
    }

    @Test
    void emptyGraph() {
        var graph = new CorrelationGraph(Map.of(), Map.of());
        assertThat(RetrievalAnalyzer.documentImpact(graph)).isEmpty();
    }

    @Test
    void documentImpactValidation() {
        assertThatThrownBy(() -> new DocumentImpact(null, 1, 1, 0.5, Map.of()))
            .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new DocumentImpact("d1", 0, 1, 0.5, Map.of()))
            .isInstanceOf(IllegalArgumentException.class);
    }

    // -- helpers --

    private static QueryNode qNode(String query, Map<String, Double> docs) {
        Map<String, EdgeStats> edges = new LinkedHashMap<>();
        for (var e : docs.entrySet()) {
            edges.put(e.getKey(), new EdgeStats(1, e.getValue(), Map.of()));
        }
        return new QueryNode(query, 1, edges);
    }

    private static QueryNode qNodeWithOutcomes(String query, String docId,
            double score, Map<RetrievalOutcome, Integer> outcomes) {
        return new QueryNode(query, 1,
            Map.of(docId, new EdgeStats(1, score, outcomes)));
    }

    private static CorrelationGraph graphWith(QueryNode... nodes) {
        Map<String, QueryNode> queries = new LinkedHashMap<>();
        Map<String, DocumentNode> documents = new LinkedHashMap<>();
        for (QueryNode qn : nodes) {
            queries.put(qn.queryText(), qn);
            for (var edge : qn.documentEdges().entrySet()) {
                String docId = edge.getKey();
                Map<String, EdgeStats> qEdges = new LinkedHashMap<>(
                    documents.containsKey(docId) ?
                        documents.get(docId).queryEdges() : Map.of());
                qEdges.put(qn.queryText(), edge.getValue());
                int count = qEdges.values().stream()
                    .mapToInt(EdgeStats::coOccurrenceCount).sum();
                documents.put(docId, new DocumentNode(docId, count, qEdges));
            }
        }
        return new CorrelationGraph(queries, documents);
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=DocumentImpactTest`
Expected: FAIL — `DocumentImpact` doesn't exist.

- [ ] **Step 6: Create DocumentImpact record and implement documentImpact()**

Create `DocumentImpact.java`:
```java
package io.casehub.neocortex.rag;

import java.util.Map;

public record DocumentImpact(
    String documentId,
    int distinctQueryCount,
    int totalRetrievals,
    double averageScore,
    Map<RetrievalOutcome, Integer> aggregateOutcomes
) {
    public DocumentImpact {
        if (documentId == null || documentId.isBlank())
            throw new IllegalArgumentException("documentId must not be null or blank");
        if (distinctQueryCount < 1)
            throw new IllegalArgumentException("distinctQueryCount must be positive");
        if (totalRetrievals < 1)
            throw new IllegalArgumentException("totalRetrievals must be positive");
        if (aggregateOutcomes == null)
            throw new IllegalArgumentException("aggregateOutcomes must not be null");
        aggregateOutcomes = Map.copyOf(aggregateOutcomes);
    }
}
```

Add `documentImpact()` to `RetrievalAnalyzer`:

```java
public static List<DocumentImpact> documentImpact(CorrelationGraph graph) {
    List<DocumentImpact> result = new ArrayList<>();
    for (var entry : graph.documents().entrySet()) {
        DocumentNode node = entry.getValue();
        int distinctQueries = node.queryEdges().size();
        int totalRetrievals = node.queryEdges().values().stream()
            .mapToInt(EdgeStats::coOccurrenceCount).sum();
        double avgScore = node.queryEdges().values().stream()
            .mapToDouble(e -> e.averageScore() * e.coOccurrenceCount())
            .sum() / totalRetrievals;

        Map<RetrievalOutcome, Integer> aggregated = new EnumMap<>(RetrievalOutcome.class);
        for (EdgeStats edge : node.queryEdges().values()) {
            for (var oe : edge.outcomeDistribution().entrySet()) {
                aggregated.merge(oe.getKey(), oe.getValue(), Integer::sum);
            }
        }

        result.add(new DocumentImpact(
            entry.getKey(), distinctQueries, totalRetrievals,
            avgScore, aggregated));
    }
    result.sort(Comparator.comparingInt(DocumentImpact::distinctQueryCount).reversed());
    return result;
}
```

- [ ] **Step 7: Run all correlation tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest="CorrelationGraphTest,QueryClusterTest,DocumentImpactTest"`
Expected: PASS

- [ ] **Step 8: Full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: PASS — all modules, all tests green.

- [ ] **Step 9: Commit**

Message: `feat(#167): query-document-outcome correlation graph with clustering and impact analysis`

---

## Task Dependency Graph

```
Task 1 (Interface Foundation)
  ├── Task 2 (ColBertRelevanceEvaluator)
  ├── Task 3 (CrossEncoder refactor)
  └── Task 4 (CRAG + CDI) ← depends on Tasks 2 & 3
Task 5 (Correlation value types + builder) ← independent
  └── Task 6 (Correlation analysis) ← depends on Task 5
```

Tasks 1-4 and Tasks 5-6 are two independent chains. Within each chain, execution is sequential.
