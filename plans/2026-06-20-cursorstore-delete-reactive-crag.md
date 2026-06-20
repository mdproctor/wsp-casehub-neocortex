# CursorStore.delete() + ReactiveCorrectiveCaseRetriever Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `CursorStore.delete()` to the RAG SPI (#38) and implement the reactive CRAG decorator for `ReactiveCaseRetriever` (#41).

**Architecture:** Two independent changes on one branch. #38 adds a method to an existing SPI and its two implementations. #41 extracts shared CRAG logic from the blocking decorator into `CragEvaluationLogic`, then builds a reactive `@Decorator` on `ReactiveCaseRetriever` that reuses that shared logic with Mutiny `Uni` chains. An already-graded guard prevents double CRAG application when the blocking bridge is active.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI `@Decorator`, SmallRye Mutiny, JUnit 5, AssertJ

**Build command:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

**Build single module:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`

---

### Task 1: CursorStore.delete() — SPI + Implementations + Tests

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/rag/CursorStore.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/FileCursorStore.java`
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCursorStore.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/FileCursorStoreTest.java`
- Modify: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCursorStoreTest.java`

- [ ] **Step 1: Add `delete()` to the CursorStore SPI**

Add the method to `rag-api/src/main/java/io/casehub/rag/CursorStore.java`. No default body — every implementation must provide a semantically correct delete.

```java
package io.casehub.rag;

import java.util.Optional;

public interface CursorStore {
    Optional<String> load(String corpusName);
    void save(String corpusName, String cursor);
    void delete(String corpusName);
}
```

- [ ] **Step 2: Write failing tests for FileCursorStore.delete()**

Add to `rag/src/test/java/io/casehub/rag/runtime/FileCursorStoreTest.java`:

```java
@Test
void deleteRemovesCursor() {
    store.save("garden", "cursor-1");
    store.delete("garden");
    assertThat(store.load("garden")).isEmpty();
}

@Test
void deleteNonExistentIsNoOp() {
    store.delete("nonexistent"); // no exception
    assertThat(store.load("nonexistent")).isEmpty();
}

@Test
void deleteRemovesFile() {
    store.save("garden", "cursor-1");
    assertThat(Files.exists(tempDir.resolve("garden.cursor"))).isTrue();
    store.delete("garden");
    assertThat(Files.exists(tempDir.resolve("garden.cursor"))).isFalse();
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag`
Expected: Compilation failure — `FileCursorStore` does not implement `delete()`.

- [ ] **Step 4: Implement FileCursorStore.delete()**

Add to `rag/src/main/java/io/casehub/rag/runtime/FileCursorStore.java`:

```java
@Override
public void delete(String corpusName) {
    Path file = baseDir.resolve(corpusName + ".cursor");
    try {
        Files.deleteIfExists(file);
    } catch (IOException e) {
        throw new UncheckedIOException("Failed to delete cursor for " + corpusName, e);
    }
}
```

- [ ] **Step 5: Run FileCursorStore tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag`
Expected: All FileCursorStoreTest tests pass (existing + 3 new).

- [ ] **Step 6: Write failing tests for InMemoryCursorStore.delete()**

Add to `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCursorStoreTest.java`:

```java
@Test
void deleteRemovesCursor() {
    store.save("garden", "cursor-1");
    store.delete("garden");
    assertThat(store.load("garden")).isEmpty();
}

@Test
void deleteNonExistentIsNoOp() {
    store.delete("nonexistent"); // no exception
    assertThat(store.load("nonexistent")).isEmpty();
}
```

- [ ] **Step 7: Implement InMemoryCursorStore.delete()**

Add to `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCursorStore.java`:

```java
@Override
public void delete(String corpusName) {
    cursors.remove(corpusName);
}
```

- [ ] **Step 8: Run InMemoryCursorStore tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-testing`
Expected: All InMemoryCursorStoreTest tests pass (existing + 2 new).

- [ ] **Step 9: Build all affected modules to verify nothing breaks**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-api,rag,rag-testing`
Expected: BUILD SUCCESS. All tests pass.

- [ ] **Step 10: Commit**

```
feat(#38): add CursorStore.delete() — clean cursor reset without implementation coupling

Closes #38
```

Stage: `rag-api/src/main/java/io/casehub/rag/CursorStore.java`, `rag/src/main/java/io/casehub/rag/runtime/FileCursorStore.java`, `rag/src/test/java/io/casehub/rag/runtime/FileCursorStoreTest.java`, `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCursorStore.java`, `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCursorStoreTest.java`

---

### Task 2: Extract CragEvaluationLogic — Shared CRAG Logic

**Files:**
- Create: `rag-crag/src/main/java/io/casehub/rag/crag/CragEvaluationLogic.java`
- Create: `rag-crag/src/test/java/io/casehub/rag/crag/CragEvaluationLogicTest.java`

- [ ] **Step 1: Write CragEvaluationLogicTest — all pure function tests**

Create `rag-crag/src/test/java/io/casehub/rag/crag/CragEvaluationLogicTest.java`:

```java
package io.casehub.rag.crag;

import io.casehub.rag.RelevanceGrade;
import io.casehub.rag.RetrievedChunk;
import org.junit.jupiter.api.Test;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class CragEvaluationLogicTest {

    @Test
    void isAlreadyGraded_emptyList() {
        assertThat(CragEvaluationLogic.isAlreadyGraded(List.of())).isFalse();
    }

    @Test
    void isAlreadyGraded_allGraded() {
        var chunks = List.of(
            chunk("a", "d1", RelevanceGrade.CORRECT),
            chunk("b", "d2", RelevanceGrade.AMBIGUOUS),
            chunk("c", "d3", RelevanceGrade.INCORRECT));
        assertThat(CragEvaluationLogic.isAlreadyGraded(chunks)).isTrue();
    }

    @Test
    void isAlreadyGraded_allUngraded() {
        var chunks = List.of(
            chunk("a", "d1", RelevanceGrade.UNGRADED),
            chunk("b", "d2", RelevanceGrade.UNGRADED));
        assertThat(CragEvaluationLogic.isAlreadyGraded(chunks)).isFalse();
    }

    @Test
    void isAlreadyGraded_mixed() {
        var chunks = List.of(
            chunk("a", "d1", RelevanceGrade.CORRECT),
            chunk("b", "d2", RelevanceGrade.UNGRADED));
        assertThat(CragEvaluationLogic.isAlreadyGraded(chunks)).isFalse();
    }

    @Test
    void gradeChunks_countsAccumulate() {
        var chunks = List.of(
            chunk("a", "d1"), chunk("b", "d2"), chunk("c", "d3"));
        var grades = List.of(
            RelevanceGrade.CORRECT, RelevanceGrade.INCORRECT, RelevanceGrade.AMBIGUOUS);

        var result = CragEvaluationLogic.gradeChunks(chunks, grades);

        assertThat(result.correct()).isEqualTo(1);
        assertThat(result.incorrect()).isEqualTo(1);
        assertThat(result.ambiguous()).isEqualTo(1);
        assertThat(result.graded()).hasSize(3);
        assertThat(result.graded().get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
        assertThat(result.graded().get(1).grade()).isEqualTo(RelevanceGrade.INCORRECT);
        assertThat(result.graded().get(2).grade()).isEqualTo(RelevanceGrade.AMBIGUOUS);
    }

    @Test
    void gradeChunks_dedupKeysUseFullContent() {
        var chunks = List.of(chunk("content-a", "doc1"), chunk("content-b", "doc1"));
        var grades = List.of(RelevanceGrade.CORRECT, RelevanceGrade.CORRECT);

        var result = CragEvaluationLogic.gradeChunks(chunks, grades);

        assertThat(result.seen()).containsExactlyInAnyOrder(
            "doc1\0content-a", "doc1\0content-b");
    }

    @Test
    void filterIncorrect_removesIncorrect() {
        var graded = List.of(
            chunk("a", "d1", RelevanceGrade.CORRECT),
            chunk("b", "d2", RelevanceGrade.INCORRECT),
            chunk("c", "d3", RelevanceGrade.AMBIGUOUS));

        var survivors = CragEvaluationLogic.filterIncorrect(graded);

        assertThat(survivors).hasSize(2);
        assertThat(survivors).extracting(RetrievedChunk::content)
            .containsExactly("a", "c");
    }

    @Test
    void deduplicateExpanded_filtersSeen() {
        Set<String> seen = new HashSet<>(Set.of("doc1\0already-seen"));
        var expanded = List.of(
            chunk("already-seen", "doc1"),
            chunk("new-chunk", "doc2"));

        var deduped = CragEvaluationLogic.deduplicateExpanded(expanded, seen);

        assertThat(deduped).hasSize(1);
        assertThat(deduped.get(0).content()).isEqualTo("new-chunk");
    }

    @Test
    void sortAndTruncate_correctBeforeAmbiguous() {
        var chunks = List.of(
            chunk("ambig", "d1", RelevanceGrade.AMBIGUOUS),
            chunk("correct", "d2", RelevanceGrade.CORRECT));

        var sorted = CragEvaluationLogic.sortAndTruncate(chunks, 10);

        assertThat(sorted.get(0).content()).isEqualTo("correct");
        assertThat(sorted.get(1).content()).isEqualTo("ambig");
    }

    @Test
    void sortAndTruncate_truncatesAtMax() {
        var chunks = List.of(
            chunk("a", "d1", RelevanceGrade.CORRECT),
            chunk("b", "d2", RelevanceGrade.CORRECT),
            chunk("c", "d3", RelevanceGrade.CORRECT));

        var truncated = CragEvaluationLogic.sortAndTruncate(chunks, 2);

        assertThat(truncated).hasSize(2);
    }

    @Test
    void needsExpansion_thresholdBoundaries() {
        assertThat(CragEvaluationLogic.needsExpansion(5, 5, 1)).isFalse();
        assertThat(CragEvaluationLogic.needsExpansion(3, 5, 0)).isFalse();
        assertThat(CragEvaluationLogic.needsExpansion(3, 5, 1)).isTrue();
    }

    @Test
    void buildQualityEvent_fields() {
        var event = CragEvaluationLogic.buildQualityEvent(10, 5, 3, 2, true);

        assertThat(event.totalRetrieved()).isEqualTo(10);
        assertThat(event.totalCorrect()).isEqualTo(5);
        assertThat(event.totalAmbiguous()).isEqualTo(3);
        assertThat(event.totalIncorrect()).isEqualTo(2);
        assertThat(event.evaluated()).isTrue();
        assertThat(event.expandedSearch()).isTrue();
    }

    // -- helpers --

    private static RetrievedChunk chunk(String content, String docId) {
        return new RetrievedChunk(content, docId, 0.9, Map.of());
    }

    private static RetrievedChunk chunk(String content, String docId, RelevanceGrade grade) {
        return new RetrievedChunk(content, docId, 0.9, Map.of(), grade);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crag`
Expected: Compilation failure — `CragEvaluationLogic` does not exist.

- [ ] **Step 3: Implement CragEvaluationLogic**

Create `rag-crag/src/main/java/io/casehub/rag/crag/CragEvaluationLogic.java`:

```java
package io.casehub.rag.crag;

import io.casehub.rag.RelevanceGrade;
import io.casehub.rag.RetrievalQuality;
import io.casehub.rag.RetrievedChunk;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

final class CragEvaluationLogic {

    private CragEvaluationLogic() {}

    record GradeResult(List<RetrievedChunk> graded, Set<String> seen,
                       int correct, int ambiguous, int incorrect) {}

    static boolean isAlreadyGraded(List<RetrievedChunk> chunks) {
        return !chunks.isEmpty()
            && chunks.stream().noneMatch(c -> c.grade() == RelevanceGrade.UNGRADED);
    }

    static GradeResult gradeChunks(List<RetrievedChunk> chunks,
                                   List<RelevanceGrade> grades) {
        Set<String> seen = new HashSet<>();
        int correct = 0, ambiguous = 0, incorrect = 0;
        List<RetrievedChunk> graded = new ArrayList<>(chunks.size());
        for (int i = 0; i < chunks.size(); i++) {
            RelevanceGrade grade = grades.get(i);
            switch (grade) {
                case CORRECT   -> correct++;
                case AMBIGUOUS -> ambiguous++;
                case INCORRECT -> incorrect++;
                default -> throw new IllegalStateException(
                    "Evaluator returned " + grade
                        + " — implementations must return CORRECT, AMBIGUOUS, or INCORRECT");
            }
            RetrievedChunk c = chunks.get(i);
            seen.add(dedupKey(c));
            graded.add(c.withGrade(grade));
        }
        return new GradeResult(graded, seen, correct, ambiguous, incorrect);
    }

    static List<RetrievedChunk> filterIncorrect(List<RetrievedChunk> graded) {
        return graded.stream()
            .filter(c -> c.grade() != RelevanceGrade.INCORRECT)
            .toList();
    }

    static boolean needsExpansion(int survivorCount, int maxResults,
                                  int incorrectCount) {
        return survivorCount < maxResults && incorrectCount > 0;
    }

    static List<RetrievedChunk> deduplicateExpanded(
            List<RetrievedChunk> expanded, Set<String> seen) {
        return expanded.stream()
            .filter(c -> !seen.contains(dedupKey(c)))
            .toList();
    }

    static List<RetrievedChunk> sortAndTruncate(
            List<RetrievedChunk> merged, int maxResults) {
        return merged.stream()
            .sorted(Comparator.comparingInt(
                (RetrievedChunk c) -> c.grade() == RelevanceGrade.CORRECT ? 0 : 1))
            .limit(maxResults)
            .toList();
    }

    static RetrievalQuality buildQualityEvent(
            int totalRetrieved, int correct, int ambiguous,
            int incorrect, boolean expanded) {
        return new RetrievalQuality(
            totalRetrieved, correct, ambiguous, incorrect, true, expanded);
    }

    static String dedupKey(RetrievedChunk c) {
        return c.sourceDocumentId() + "\0" + c.content();
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crag`
Expected: All CragEvaluationLogicTest tests pass. Existing CorrectiveCaseRetrieverTest tests also pass (CragEvaluationLogic is additive — no changes to existing code yet).

- [ ] **Step 5: Commit**

```
feat(#41): extract CragEvaluationLogic — shared pure functions for CRAG decorators
```

Stage: `rag-crag/src/main/java/io/casehub/rag/crag/CragEvaluationLogic.java`, `rag-crag/src/test/java/io/casehub/rag/crag/CragEvaluationLogicTest.java`

---

### Task 3: Refactor Blocking CorrectiveCaseRetriever to Use Shared Logic

**Files:**
- Modify: `rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java`
- Modify: `rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java`

- [ ] **Step 1: Add `alreadyGradedChunksPassThrough` test to CorrectiveCaseRetrieverTest**

Add to `rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java`:

```java
@Test
void alreadyGradedChunksPassThrough() {
    var preGraded = List.of(
        chunk("good", "doc1", 0.9).withGrade(RelevanceGrade.CORRECT),
        chunk("maybe", "doc2", 0.8).withGrade(RelevanceGrade.AMBIGUOUS));
    var delegate = InMemoryCaseRetriever.returning(preGraded);

    var evaluatorCalled = new java.util.concurrent.atomic.AtomicBoolean(false);
    RelevanceEvaluator evaluator = (query, content) -> {
        evaluatorCalled.set(true);
        return RelevanceGrade.CORRECT;
    };

    var quality = new AtomicReference<RetrievalQuality>();
    var retriever = new CorrectiveCaseRetriever(
        delegate, evaluator, stubConfig(3), capturingEvent(quality));

    var results = retriever.retrieve("query", CORPUS, 10, null);

    assertThat(results).hasSize(2);
    assertThat(results).isEqualTo(preGraded);
    assertThat(evaluatorCalled.get()).isFalse();
    assertThat(quality.get()).isNull();
}
```

Note: The `chunk()` helper in the existing test creates ungraded chunks with `new RetrievedChunk(content, docId, score, Map.of())`. Here we use the existing `chunk()` helper then `.withGrade()`. The `capturingEvent` mock initialises the `AtomicReference` as `null`, so `quality.get()` being `null` confirms no event was fired.

- [ ] **Step 2: Run tests to verify the new test fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crag -Dtest=CorrectiveCaseRetrieverTest#alreadyGradedChunksPassThrough`
Expected: FAIL — current implementation unconditionally evaluates all chunks.

- [ ] **Step 3: Refactor CorrectiveCaseRetriever to use CragEvaluationLogic**

Replace the `retrieve()` method body and remove the private `dedupKey()` method. The full file becomes:

```java
package io.casehub.rag.crag;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.PayloadFilter;
import io.casehub.rag.RelevanceEvaluator;
import io.casehub.rag.RetrievalQuality;
import io.casehub.rag.RetrievedChunk;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.event.Event;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.List;

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

        if (CragEvaluationLogic.isAlreadyGraded(chunks)) {
            return chunks;
        }

        List<String> contents = chunks.stream().map(RetrievedChunk::content).toList();
        var initial = CragEvaluationLogic.gradeChunks(chunks,
            evaluator.evaluateBatch(query, contents));
        int totalRetrieved = chunks.size();

        List<RetrievedChunk> surviving = new ArrayList<>(
            CragEvaluationLogic.filterIncorrect(initial.graded()));

        boolean expanded = false;
        int correct = initial.correct(), ambiguous = initial.ambiguous(),
            incorrect = initial.incorrect();

        if (CragEvaluationLogic.needsExpansion(
                surviving.size(), maxResults, initial.incorrect())) {
            expanded = true;
            int expandedLimit = maxResults * config.expansionMultiplier();
            List<RetrievedChunk> expandedChunks = delegate.retrieve(
                query, corpus, expandedLimit, filter);

            List<RetrievedChunk> newChunks =
                CragEvaluationLogic.deduplicateExpanded(expandedChunks, initial.seen());

            if (!newChunks.isEmpty()) {
                List<String> newContents = newChunks.stream()
                    .map(RetrievedChunk::content).toList();
                var expansionResult = CragEvaluationLogic.gradeChunks(newChunks,
                    evaluator.evaluateBatch(query, newContents));

                totalRetrieved += newChunks.size();
                correct += expansionResult.correct();
                ambiguous += expansionResult.ambiguous();
                incorrect += expansionResult.incorrect();

                surviving.addAll(
                    CragEvaluationLogic.filterIncorrect(expansionResult.graded()));
            }
        }

        List<RetrievedChunk> result =
            CragEvaluationLogic.sortAndTruncate(surviving, maxResults);

        qualityEvent.fire(CragEvaluationLogic.buildQualityEvent(
            totalRetrieved, correct, ambiguous, incorrect, expanded));

        return result;
    }
}
```

- [ ] **Step 4: Run all CorrectiveCaseRetrieverTest tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crag`
Expected: All 9 tests pass (8 existing + 1 new `alreadyGradedChunksPassThrough`). CragEvaluationLogicTest also passes.

- [ ] **Step 5: Commit**

```
refactor(#41): CorrectiveCaseRetriever uses CragEvaluationLogic + already-graded guard
```

Stage: `rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java`, `rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java`

---

### Task 4: Add Mutiny Dependency to rag-crag

**Files:**
- Modify: `rag-crag/pom.xml`

- [ ] **Step 1: Add Mutiny provided-scope dependency**

Add to the `<dependencies>` section of `rag-crag/pom.xml`, after the existing `smallrye-config-core` dependency:

```xml
<dependency>
    <groupId>io.smallrye.reactive</groupId>
    <artifactId>mutiny</artifactId>
    <scope>provided</scope>
</dependency>
```

- [ ] **Step 2: Verify build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-crag`
Expected: BUILD SUCCESS.

- [ ] **Step 3: Commit**

```
chore(#41): add Mutiny provided dependency to rag-crag for reactive decorator
```

Stage: `rag-crag/pom.xml`

---

### Task 5: ReactiveCorrectiveCaseRetriever — Tests + Implementation

**Files:**
- Create: `rag-crag/src/main/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetriever.java`
- Create: `rag-crag/src/test/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetrieverTest.java`

- [ ] **Step 1: Write ReactiveCorrectiveCaseRetrieverTest**

Create `rag-crag/src/test/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetrieverTest.java`:

```java
package io.casehub.rag.crag;

import io.casehub.rag.CorpusRef;
import io.casehub.rag.PayloadFilter;
import io.casehub.rag.ReactiveCaseRetriever;
import io.casehub.rag.RelevanceEvaluator;
import io.casehub.rag.RelevanceGrade;
import io.casehub.rag.RetrievalQuality;
import io.casehub.rag.RetrievedChunk;
import io.casehub.rag.testing.InMemoryRelevanceEvaluator;
import io.smallrye.mutiny.Uni;
import jakarta.enterprise.event.Event;
import jakarta.enterprise.event.NotificationOptions;
import jakarta.enterprise.util.TypeLiteral;
import org.junit.jupiter.api.Test;

import java.lang.annotation.Annotation;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

class ReactiveCorrectiveCaseRetrieverTest {

    private static final CorpusRef CORPUS = new CorpusRef("tenant-1", "test-corpus");

    @Test
    void alreadyGradedChunksPassThrough() {
        var preGraded = List.of(
            chunk("good", "doc1", 0.9).withGrade(RelevanceGrade.CORRECT),
            chunk("maybe", "doc2", 0.8).withGrade(RelevanceGrade.AMBIGUOUS));
        var delegate = fixedReactiveRetriever(preGraded);

        var evaluatorCalled = new AtomicBoolean(false);
        RelevanceEvaluator evaluator = (query, content) -> {
            evaluatorCalled.set(true);
            return RelevanceGrade.CORRECT;
        };

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new ReactiveCorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingAsyncEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 10, null)
            .await().indefinitely();

        assertThat(results).hasSize(2);
        assertThat(results).isEqualTo(preGraded);
        assertThat(evaluatorCalled.get()).isFalse();
        assertThat(quality.get()).isNull();
    }

    @Test
    void allCorrectChunksPassThrough() {
        var delegate = fixedReactiveRetriever(
            chunk("good1", "doc1", 0.9), chunk("good2", "doc2", 0.8));
        var quality = new AtomicReference<RetrievalQuality>();

        var retriever = reactiveCorrective(
            delegate, RelevanceGrade.CORRECT, quality);
        var results = retriever.retrieve("query", CORPUS, 10, null)
            .await().indefinitely();

        assertThat(results).hasSize(2);
        assertThat(results).allSatisfy(
            c -> assertThat(c.grade()).isEqualTo(RelevanceGrade.CORRECT));
        assertThat(quality.get().evaluated()).isTrue();
        assertThat(quality.get().expandedSearch()).isFalse();
        assertThat(quality.get().totalCorrect()).isEqualTo(2);
    }

    @Test
    void allIncorrectTriggersExpansion() {
        var delegate = fixedReactiveRetriever(
            chunk("bad1", "doc1", 0.9), chunk("bad2", "doc2", 0.8));
        var quality = new AtomicReference<RetrievalQuality>();

        var retriever = reactiveCorrective(
            delegate, RelevanceGrade.INCORRECT, quality);
        var results = retriever.retrieve("query", CORPUS, 5, null)
            .await().indefinitely();

        assertThat(results).isEmpty();
        assertThat(quality.get().expandedSearch()).isTrue();
        assertThat(quality.get().totalIncorrect()).isGreaterThan(0);
    }

    @Test
    void mixedGradesFilterIncorrect() {
        List<RetrievedChunk> chunks = List.of(
            chunk("good", "doc1", 0.9),
            chunk("bad", "doc2", 0.8),
            chunk("maybe", "doc3", 0.7));
        var delegate = fixedReactiveRetriever(chunks);

        var evaluator = gradeByContent(Map.of(
            "good", RelevanceGrade.CORRECT,
            "bad", RelevanceGrade.INCORRECT,
            "maybe", RelevanceGrade.AMBIGUOUS));

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new ReactiveCorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingAsyncEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 10, null)
            .await().indefinitely();

        assertThat(results).hasSize(2);
        assertThat(results).extracting(RetrievedChunk::content)
            .containsExactly("good", "maybe");
        assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
        assertThat(results.get(1).grade()).isEqualTo(RelevanceGrade.AMBIGUOUS);
    }

    @Test
    void truncationPrefersCORRECT() {
        List<RetrievedChunk> chunks = List.of(
            chunk("ambig1", "doc1", 0.9),
            chunk("ambig2", "doc2", 0.8),
            chunk("correct1", "doc3", 0.7));
        var delegate = fixedReactiveRetriever(chunks);

        var evaluator = gradeByContent(Map.of(
            "ambig1", RelevanceGrade.AMBIGUOUS,
            "ambig2", RelevanceGrade.AMBIGUOUS,
            "correct1", RelevanceGrade.CORRECT));

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new ReactiveCorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingAsyncEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 2, null)
            .await().indefinitely();

        assertThat(results).hasSize(2);
        assertThat(results.get(0).content()).isEqualTo("correct1");
    }

    @Test
    void emptyCorpusReturnsEmpty() {
        var delegate = fixedReactiveRetriever(List.of());
        var quality = new AtomicReference<RetrievalQuality>();

        var retriever = reactiveCorrective(
            delegate, RelevanceGrade.CORRECT, quality);
        var results = retriever.retrieve("query", CORPUS, 5, null)
            .await().indefinitely();

        assertThat(results).isEmpty();
        assertThat(quality.get().expandedSearch()).isFalse();
        assertThat(quality.get().totalRetrieved()).isEqualTo(0);
    }

    @Test
    void smallCorpusNoExpansion() {
        var delegate = fixedReactiveRetriever(chunk("only", "doc1", 0.9));
        var quality = new AtomicReference<RetrievalQuality>();

        var retriever = reactiveCorrective(
            delegate, RelevanceGrade.CORRECT, quality);
        var results = retriever.retrieve("query", CORPUS, 5, null)
            .await().indefinitely();

        assertThat(results).hasSize(1);
        assertThat(quality.get().expandedSearch()).isFalse();
    }

    @Test
    void qualityEventFired() {
        var callCount = new int[]{0};
        ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            callCount[0]++;
            if (callCount[0] == 1) {
                return Uni.createFrom().item(List.of(chunk("bad", "doc1", 0.9)));
            }
            return Uni.createFrom().item(List.of(
                chunk("bad", "doc1", 0.9), chunk("good", "doc2", 0.8)));
        };

        var evaluator = gradeByContent(Map.of(
            "bad", RelevanceGrade.INCORRECT,
            "good", RelevanceGrade.CORRECT));

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new ReactiveCorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingAsyncEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 5, null)
            .await().indefinitely();

        assertThat(results).hasSize(1);
        assertThat(results.get(0).content()).isEqualTo("good");
        assertThat(quality.get().totalRetrieved()).isEqualTo(2);
        assertThat(quality.get().expandedSearch()).isTrue();
    }

    @Test
    void expansionDeduplicates() {
        var callCount = new int[]{0};
        ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            callCount[0]++;
            if (callCount[0] == 1) {
                return Uni.createFrom().item(List.of(chunk("seen", "doc1", 0.9)));
            }
            return Uni.createFrom().item(List.of(
                chunk("seen", "doc1", 0.9), chunk("new", "doc2", 0.8)));
        };

        var evaluator = gradeByContent(Map.of(
            "seen", RelevanceGrade.INCORRECT,
            "new", RelevanceGrade.CORRECT));

        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new ReactiveCorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingAsyncEvent(quality));

        var results = retriever.retrieve("query", CORPUS, 5, null)
            .await().indefinitely();

        assertThat(results).hasSize(1);
        assertThat(results.get(0).content()).isEqualTo("new");
    }

    @Test
    void evaluatorRunsOnWorkerThread() {
        var evaluatorThreadId = new AtomicLong(Thread.currentThread().getId());
        RelevanceEvaluator evaluator = new RelevanceEvaluator() {
            @Override
            public RelevanceGrade evaluate(String query, String chunkContent) {
                evaluatorThreadId.set(Thread.currentThread().getId());
                return RelevanceGrade.CORRECT;
            }
        };

        var delegate = fixedReactiveRetriever(chunk("a", "doc1", 0.9));
        var quality = new AtomicReference<RetrievalQuality>();
        var retriever = new ReactiveCorrectiveCaseRetriever(
            delegate, evaluator, stubConfig(3), capturingAsyncEvent(quality));

        retriever.retrieve("query", CORPUS, 5, null).await().indefinitely();

        assertNotEquals(Thread.currentThread().getId(), evaluatorThreadId.get(),
            "evaluator must execute on a worker thread, not the subscribing thread");
    }

    // -- helpers --

    private static RetrievedChunk chunk(String content, String docId, double score) {
        return new RetrievedChunk(content, docId, score, Map.of());
    }

    private static ReactiveCaseRetriever fixedReactiveRetriever(RetrievedChunk... chunks) {
        return fixedReactiveRetriever(List.of(chunks));
    }

    private static ReactiveCaseRetriever fixedReactiveRetriever(List<RetrievedChunk> chunks) {
        return (query, corpus, maxResults, filter) ->
            Uni.createFrom().item(chunks);
    }

    private static ReactiveCorrectiveCaseRetriever reactiveCorrective(
            ReactiveCaseRetriever delegate, RelevanceGrade fixedGrade,
            AtomicReference<RetrievalQuality> qualityCapture) {
        return new ReactiveCorrectiveCaseRetriever(
            delegate,
            InMemoryRelevanceEvaluator.returning(fixedGrade),
            stubConfig(3),
            capturingAsyncEvent(qualityCapture));
    }

    private static CragConfig stubConfig(int expansionMultiplier) {
        return new CragConfig() {
            @Override public double correctThreshold() { return 0.7; }
            @Override public double incorrectThreshold() { return 0.3; }
            @Override public int expansionMultiplier() { return expansionMultiplier; }
        };
    }

    private static Event<RetrievalQuality> capturingAsyncEvent(
            AtomicReference<RetrievalQuality> ref) {
        return new Event<>() {
            @Override public void fire(RetrievalQuality event) { ref.set(event); }
            @Override public Event<RetrievalQuality> select(Annotation... a) { return this; }
            @Override public <U extends RetrievalQuality> Event<U> select(
                Class<U> c, Annotation... a) { return null; }
            @Override public <U extends RetrievalQuality> Event<U> select(
                TypeLiteral<U> t, Annotation... a) { return null; }
            @Override public CompletionStage<RetrievalQuality> fireAsync(
                RetrievalQuality event) {
                ref.set(event);
                return CompletableFuture.completedFuture(event);
            }
            @Override public CompletionStage<RetrievalQuality> fireAsync(
                RetrievalQuality event, NotificationOptions options) {
                return fireAsync(event);
            }
        };
    }

    private static RelevanceEvaluator gradeByContent(
            Map<String, RelevanceGrade> contentToGrade) {
        return (query, chunkContent) ->
            contentToGrade.getOrDefault(chunkContent, RelevanceGrade.UNGRADED);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crag`
Expected: Compilation failure — `ReactiveCorrectiveCaseRetriever` does not exist.

- [ ] **Step 3: Implement ReactiveCorrectiveCaseRetriever**

Create `rag-crag/src/main/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetriever.java`:

```java
package io.casehub.rag.crag;

import io.casehub.rag.CorpusRef;
import io.casehub.rag.PayloadFilter;
import io.casehub.rag.ReactiveCaseRetriever;
import io.casehub.rag.RelevanceEvaluator;
import io.casehub.rag.RetrievalQuality;
import io.casehub.rag.RetrievedChunk;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.event.Event;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.List;

@Decorator
@Priority(100)
public class ReactiveCorrectiveCaseRetriever implements ReactiveCaseRetriever {

    private final ReactiveCaseRetriever delegate;
    private final RelevanceEvaluator evaluator;
    private final CragConfig config;
    private final Event<RetrievalQuality> qualityEvent;

    @Inject
    ReactiveCorrectiveCaseRetriever(@Delegate @Any ReactiveCaseRetriever delegate,
                                    RelevanceEvaluator evaluator,
                                    CragConfig config,
                                    Event<RetrievalQuality> qualityEvent) {
        this.delegate = delegate;
        this.evaluator = evaluator;
        this.config = config;
        this.qualityEvent = qualityEvent;
    }

    @Override
    public Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus,
                                               int maxResults, PayloadFilter filter) {
        return delegate.retrieve(query, corpus, maxResults, filter)
            .onItem().transformToUni(chunks -> {
                if (CragEvaluationLogic.isAlreadyGraded(chunks)) {
                    return Uni.createFrom().item(chunks);
                }
                return evaluateAndCorrect(query, corpus, maxResults, filter, chunks);
            });
    }

    private Uni<List<RetrievedChunk>> evaluateAndCorrect(
            String query, CorpusRef corpus, int maxResults,
            PayloadFilter filter, List<RetrievedChunk> chunks) {

        return Uni.createFrom().item(() -> {
                List<String> contents = chunks.stream()
                    .map(RetrievedChunk::content).toList();
                return CragEvaluationLogic.gradeChunks(chunks,
                    evaluator.evaluateBatch(query, contents));
            })
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
            .onItem().transformToUni(initial -> {
                List<RetrievedChunk> surviving = new ArrayList<>(
                    CragEvaluationLogic.filterIncorrect(initial.graded()));

                if (!CragEvaluationLogic.needsExpansion(
                        surviving.size(), maxResults, initial.incorrect())) {
                    List<RetrievedChunk> result =
                        CragEvaluationLogic.sortAndTruncate(surviving, maxResults);
                    qualityEvent.fireAsync(CragEvaluationLogic.buildQualityEvent(
                        chunks.size(), initial.correct(), initial.ambiguous(),
                        initial.incorrect(), false));
                    return Uni.createFrom().item(result);
                }

                int expandedLimit = maxResults * config.expansionMultiplier();
                return delegate.retrieve(query, corpus, expandedLimit, filter)
                    .onItem().transformToUni(expandedChunks -> {
                        List<RetrievedChunk> newChunks =
                            CragEvaluationLogic.deduplicateExpanded(
                                expandedChunks, initial.seen());

                        if (newChunks.isEmpty()) {
                            List<RetrievedChunk> result =
                                CragEvaluationLogic.sortAndTruncate(
                                    surviving, maxResults);
                            qualityEvent.fireAsync(
                                CragEvaluationLogic.buildQualityEvent(
                                    chunks.size(), initial.correct(),
                                    initial.ambiguous(), initial.incorrect(),
                                    true));
                            return Uni.createFrom().item(result);
                        }

                        return Uni.createFrom().item(() -> {
                                List<String> newContents = newChunks.stream()
                                    .map(RetrievedChunk::content).toList();
                                return CragEvaluationLogic.gradeChunks(newChunks,
                                    evaluator.evaluateBatch(query, newContents));
                            })
                            .runSubscriptionOn(
                                Infrastructure.getDefaultWorkerPool())
                            .onItem().transform(expansionResult -> {
                                surviving.addAll(
                                    CragEvaluationLogic.filterIncorrect(
                                        expansionResult.graded()));

                                int totalRetrieved =
                                    chunks.size() + newChunks.size();
                                qualityEvent.fireAsync(
                                    CragEvaluationLogic.buildQualityEvent(
                                        totalRetrieved,
                                        initial.correct()
                                            + expansionResult.correct(),
                                        initial.ambiguous()
                                            + expansionResult.ambiguous(),
                                        initial.incorrect()
                                            + expansionResult.incorrect(),
                                        true));

                                return CragEvaluationLogic.sortAndTruncate(
                                    surviving, maxResults);
                            });
                    });
            });
    }
}
```

- [ ] **Step 4: Run all rag-crag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crag`
Expected: All tests pass — CragEvaluationLogicTest (11), CorrectiveCaseRetrieverTest (9), ReactiveCorrectiveCaseRetrieverTest (10), CrossEncoderRelevanceEvaluatorTest (existing).

- [ ] **Step 5: Commit**

```
feat(#41): ReactiveCorrectiveCaseRetriever — reactive path CRAG decorator
```

Stage: `rag-crag/src/main/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetriever.java`, `rag-crag/src/test/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetrieverTest.java`

---

### Task 6: Add UNGRADED Assertions to Existing Tests

**Files:**
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`

- [ ] **Step 1: Add grade == UNGRADED assertion to HybridCaseRetrieverTest**

In `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`, add the import:

```java
import io.casehub.rag.RelevanceGrade;
```

Then add this assertion to the `retrieveFromIngestedCorpus` test, after the existing assertions:

```java
assertThat(results).allSatisfy(chunk ->
    assertThat(chunk.grade()).isEqualTo(RelevanceGrade.UNGRADED));
```

- [ ] **Step 2: Add grade == UNGRADED assertion to BlockingToReactiveCaseRetrieverTest**

In `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`, add the import:

```java
import io.casehub.rag.RelevanceGrade;
```

Then add this assertion to the `retrieveDelegatesToBlocking` test, after the existing assertions:

```java
assertThat(result).allSatisfy(chunk ->
    assertThat(chunk.grade()).isEqualTo(RelevanceGrade.UNGRADED));
```

- [ ] **Step 3: Run the modified tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag`
Expected: All tests pass. The existing retrievers produce chunks with default UNGRADED grade.

- [ ] **Step 4: Commit**

```
test(#41): assert grade == UNGRADED in non-CRAG retriever tests
```

Stage: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`, `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`

---

### Task 7: Full Build Verification

**Files:** None (verification only)

- [ ] **Step 1: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS across all modules.

- [ ] **Step 2: Run smoke tests for examples**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -Pexamples-smoke`
Expected: All smoke tests pass.

- [ ] **Step 3: Verify no IntelliJ diagnostics in modified files**

Use `mcp__intellij-index__ide_diagnostics` on each modified/created file to check for errors:
- `rag-api/src/main/java/io/casehub/rag/CursorStore.java`
- `rag/src/main/java/io/casehub/rag/runtime/FileCursorStore.java`
- `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCursorStore.java`
- `rag-crag/src/main/java/io/casehub/rag/crag/CragEvaluationLogic.java`
- `rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java`
- `rag-crag/src/main/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetriever.java`
