# Retention & Cross-Encoder Reranking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #110 — retrieval tracking data retention policy
**Issue group:** #110, #121

**Goal:** Add TTL-based data retention to the retrieval tracking SPI, and
add a cross-encoder reranking decorator to the RAG pipeline — consolidating
all cross-encoder features into a renamed `rag-crossencoder` module.

**Architecture:** The `rag-crag/` module is renamed to `rag-crossencoder/`
to reflect its broader scope (both CRAG and reranking share the
`inference-tasks` dependency). `purgeOlderThan()` is added to the
`RetrievalTracker` SPI with a `RetentionScheduler` background job.
`RerankingCaseRetriever` is a `@Decorator @Priority(75)` that overfetches
via `max(limit, rerankPoolSize)` and reorders by cross-encoder score.
Score propagation from CRAG to the reranker eliminates double inference.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI decorators, ONNX cross-encoder,
SQLite (HikariCP + Flyway), ScheduledExecutorService

## Global Constraints

- Java 21 source on Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build: `mvn clean install` (not `./mvnw`)
- `spi-signature-change-all-impls-same-commit` — all implementations of a
  changed SPI must ship in the same commit
- `library-jar-annotation-only-deps` — library JARs must not depend on
  Quarkus extensions (use annotation-only libraries)
- Decorator activation: `@IfBuildProperty` + classpath presence
- Use `ide_move_file` / `ide_refactor_rename` for structural code moves

---

### Task 1: Rename module `rag-crag/` → `rag-crossencoder/`

Structural rename — directory, artifactId, packages. Creates `corrective/`
sub-package for existing CRAG classes. No logic changes.

**Files:**
- Rename dir: `rag-crag/` → `rag-crossencoder/`
- Modify: `pom.xml` (parent) — lines 28, 180
- Modify: `rag-crossencoder/pom.xml` — line 13
- Move (package): all `.java` in `io.casehub.neocortex.rag.crag` → `io.casehub.neocortex.rag.crossencoder.corrective`
- Rename class: `CragBeanProducer` → `CrossEncoderBeanProducer` (stays in root `crossencoder` package, not `corrective`)

**Interfaces:**
- Consumes: nothing
- Produces: renamed module with new package structure — all subsequent tasks reference `rag-crossencoder`

- [ ] **Step 1: Rename the module directory**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex mv rag-crag rag-crossencoder
```

- [ ] **Step 2: Update parent pom.xml**

In `/Users/mdproctor/claude/casehub/neocortex/pom.xml`:
- Line 28: `<module>rag-crag</module>` → `<module>rag-crossencoder</module>`
- Line 180: `<artifactId>casehub-neocortex-rag-crag</artifactId>` → `<artifactId>casehub-neocortex-rag-crossencoder</artifactId>`

- [ ] **Step 3: Update module pom.xml**

In `rag-crossencoder/pom.xml`:
- Line 13: `<artifactId>casehub-neocortex-rag-crag</artifactId>` → `<artifactId>casehub-neocortex-rag-crossencoder</artifactId>`
- Update `<name>` and `<description>` to reflect broader scope.

- [ ] **Step 4: Create corrective sub-package and move classes**

Use `ide_move_file` or manual moves to restructure:

Source classes to move to `corrective/` sub-package:
- `CorrectiveCaseRetriever.java`
- `ReactiveCorrectiveCaseRetriever.java`
- `CrossEncoderRelevanceEvaluator.java`
- `CragEvaluationLogic.java`
- `CragConfig.java`

Target directory: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/corrective/`

Test classes to move similarly:
- `CorrectiveCaseRetrieverTest.java`
- `ReactiveCorrectiveCaseRetrieverTest.java`
- `CrossEncoderRelevanceEvaluatorTest.java`
- `CragEvaluationLogicTest.java`

Target: `rag-crossencoder/src/test/java/io/casehub/neocortex/rag/crossencoder/corrective/`

`CragBeanProducer` stays in the root package as `CrossEncoderBeanProducer`.
Move to: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/CrossEncoderBeanProducer.java`

Use `ide_refactor_rename` on `CragBeanProducer` → `CrossEncoderBeanProducer`.

- [ ] **Step 5: Update all package declarations and imports**

Every moved `.java` file needs its `package` declaration updated:
- `package io.casehub.neocortex.rag.crag;` → `package io.casehub.neocortex.rag.crossencoder.corrective;`
- `CragBeanProducer` → `package io.casehub.neocortex.rag.crossencoder;`

Cross-references within the module (e.g. `CragEvaluationLogic` used by `CorrectiveCaseRetriever`) update to the new package.

If `ide_move_file` was used, imports are updated automatically. Otherwise fix manually.

- [ ] **Step 6: Build to verify**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-crossencoder -am
```

Expected: BUILD SUCCESS. All existing CRAG tests pass with new package paths.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-crossencoder pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor(#121): rename rag-crag → rag-crossencoder

Module boundary aligns with dependency boundary — both CRAG and
reranking share inference-tasks. Classes moved to corrective/ sub-package.
CragBeanProducer → CrossEncoderBeanProducer."
```

---

### Task 2: `purgeOlderThan` — SPI + all implementations + contract tests

Adds `purgeOlderThan(Instant cutoff)` to `RetrievalTracker` and
`ReactiveRetrievalTracker` SPIs. Implements in all three: `InMemoryRetrievalTracker`,
`SqliteRetrievalTracker`, `BlockingToReactiveRetrievalTracker`. Adds 4 contract tests.
All in one commit per `spi-signature-change-all-impls-same-commit` protocol.

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java`
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/ReactiveRetrievalTracker.java`
- Modify: `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/InMemoryRetrievalTracker.java`
- Modify: `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/RetrievalTrackerContractTest.java`
- Modify: `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java`
- Modify: `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/BlockingToReactiveRetrievalTracker.java`

**Interfaces:**
- Consumes: existing `RetrievalTracker` SPI
- Produces: `int purgeOlderThan(Instant cutoff)` on `RetrievalTracker`; `Uni<Integer> purgeOlderThan(Instant cutoff)` on `ReactiveRetrievalTracker`

- [ ] **Step 1: Write the 4 contract tests**

Add to `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/RetrievalTrackerContractTest.java`:

```java
@Test
void purge_deletesOldRecordsAndChildren() {
    // Record that will be purged (timestamp = now - 100 days)
    // Must use Thread.sleep or clock manipulation to age the record
    // Record a retrieval, add feedback, then purge with cutoff = now - 50 days
    // Assert: record gone, its documents gone, its feedback gone
    String id = tracker().record(RetrievalQuery.of("old query"), CORPUS, chunks("doc-a"), 10);
    tracker().feedback(id, "doc-a", RetrievalOutcome.RELEVANT);

    // Purge everything older than 1 millisecond from now (i.e. everything)
    Instant cutoff = Instant.now().plusMillis(1);
    int deleted = tracker().purgeOlderThan(cutoff);

    assertThat(deleted).isEqualTo(1);
    assertThat(tracker().findRecords(CORPUS, Instant.EPOCH, Instant.MAX)).isEmpty();
    assertThat(tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX)).isEmpty();
    assertThat(tracker().findRetrievedDocumentIds(CORPUS, Instant.EPOCH, Instant.MAX)).isEmpty();
}

@Test
void purge_preservesRecentRecordsAndChildren() {
    String id = tracker().record(RetrievalQuery.of("recent"), CORPUS, chunks("doc-b"), 10);
    tracker().feedback(id, "doc-b", RetrievalOutcome.RELEVANT);

    // Purge everything older than 1 hour ago (nothing qualifies)
    Instant cutoff = Instant.now().minusSeconds(3600);
    int deleted = tracker().purgeOlderThan(cutoff);

    assertThat(deleted).isEqualTo(0);
    assertThat(tracker().findRecords(CORPUS, Instant.EPOCH, Instant.MAX)).hasSize(1);
    assertThat(tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX)).hasSize(1);
    assertThat(tracker().findRetrievedDocumentIds(CORPUS, Instant.EPOCH, Instant.MAX))
        .containsExactly("doc-b");
}

@Test
void purge_returnsDeletedCount() {
    tracker().record(RetrievalQuery.of("q1"), CORPUS, chunks("d1"), 10);
    tracker().record(RetrievalQuery.of("q2"), CORPUS, chunks("d2"), 10);
    tracker().record(RetrievalQuery.of("q3"), OTHER_CORPUS, chunks("d3"), 10);

    Instant cutoff = Instant.now().plusMillis(1);
    int deleted = tracker().purgeOlderThan(cutoff);

    assertThat(deleted).isEqualTo(3); // all three, regardless of corpus
}

@Test
void purge_emptyWhenNothingOld() {
    int deleted = tracker().purgeOlderThan(Instant.now());
    assertThat(deleted).isEqualTo(0);
}
```

- [ ] **Step 2: Add `purgeOlderThan` to the SPIs**

In `RetrievalTracker.java`, add after the `findRetrievedDocumentIds` method:
```java
int purgeOlderThan(Instant cutoff);
```

In `ReactiveRetrievalTracker.java`, add after `findRetrievedDocumentIds`:
```java
Uni<Integer> purgeOlderThan(Instant cutoff);
```

- [ ] **Step 3: Implement in `InMemoryRetrievalTracker`**

Add after the `clear()` method:
```java
@Override
public int purgeOlderThan(Instant cutoff) {
    List<RetrievalRecord> old = records.stream()
        .filter(r -> r.timestamp().isBefore(cutoff))
        .toList();
    Set<String> oldIds = old.stream()
        .map(RetrievalRecord::retrievalId)
        .collect(Collectors.toSet());
    records.removeAll(old);
    feedbackIndex.entrySet().removeIf(e -> oldIds.contains(e.getValue().retrievalId()));
    return old.size();
}
```

- [ ] **Step 4: Implement in `SqliteRetrievalTracker`**

Add after the `clearAll()` method:
```java
@Override
public int purgeOlderThan(Instant cutoff) {
    String cutoffIso = toIso(cutoff);
    try (Connection conn = dataSource.getConnection()) {
        conn.setAutoCommit(false);
        try {
            try (PreparedStatement ps = conn.prepareStatement(
                "DELETE FROM retrieval_feedback WHERE retrieval_id IN "
                    + "(SELECT retrieval_id FROM retrieval_records WHERE timestamp < ?)")) {
                ps.setString(1, cutoffIso);
                ps.executeUpdate();
            }
            try (PreparedStatement ps = conn.prepareStatement(
                "DELETE FROM retrieved_documents WHERE retrieval_id IN "
                    + "(SELECT retrieval_id FROM retrieval_records WHERE timestamp < ?)")) {
                ps.setString(1, cutoffIso);
                ps.executeUpdate();
            }
            int deleted;
            try (PreparedStatement ps = conn.prepareStatement(
                "DELETE FROM retrieval_records WHERE timestamp < ?")) {
                ps.setString(1, cutoffIso);
                deleted = ps.executeUpdate();
            }
            conn.commit();
            return deleted;
        } catch (Exception e) {
            conn.rollback();
            throw e instanceof RuntimeException re ? re : new IllegalStateException(e);
        } finally {
            conn.setAutoCommit(true);
        }
    } catch (SQLException e) {
        throw new IllegalStateException("purgeOlderThan() failed", e);
    }
}
```

- [ ] **Step 5: Implement in `BlockingToReactiveRetrievalTracker`**

Add after the `findRetrievedDocumentIds` method:
```java
@Override
public Uni<Integer> purgeOlderThan(Instant cutoff) {
    return Uni.createFrom().item(() -> delegate.purgeOlderThan(cutoff))
        .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
}
```

- [ ] **Step 6: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-api,rag-testing,rag-tracking -am
```

Expected: All 20+ existing tests pass + 4 new purge tests × 2 implementations (InMemory, SQLite) = 8 new test passes.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-api rag-testing rag-tracking
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#110): purgeOlderThan — SPI + all implementations + contract tests

Adds int purgeOlderThan(Instant) to RetrievalTracker and
Uni<Integer> purgeOlderThan(Instant) to ReactiveRetrievalTracker.
Implements in SqliteRetrievalTracker (cascade DELETE in transaction),
InMemoryRetrievalTracker (filter collections), and bridge.
4 new contract tests verify purge + children + count + empty."
```

---

### Task 3: RetentionScheduler

Background purge job using `ScheduledExecutorService`. Daemon thread, named,
exception-safe, graceful shutdown. Gated by same `@IfBuildProperty` as tracking.

**Files:**
- Create: `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/RetentionScheduler.java`
- Create: `rag-tracking/src/test/java/io/casehub/neocortex/rag/tracking/RetentionSchedulerTest.java`

**Interfaces:**
- Consumes: `RetrievalTracker.purgeOlderThan(Instant)` from Task 2
- Produces: `@ApplicationScoped` bean activated when tracking is enabled

- [ ] **Step 1: Write the test**

Create `rag-tracking/src/test/java/io/casehub/neocortex/rag/tracking/RetentionSchedulerTest.java`:

```java
package io.casehub.neocortex.rag.tracking;

import io.casehub.neocortex.rag.RetrievalTracker;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class RetentionSchedulerTest {

    @Test
    void purge_callsTrackerWithCorrectCutoff() {
        AtomicReference<Instant> capturedCutoff = new AtomicReference<>();
        AtomicInteger capturedCount = new AtomicInteger();

        RetrievalTracker tracker = new StubTracker() {
            @Override
            public int purgeOlderThan(Instant cutoff) {
                capturedCutoff.set(cutoff);
                capturedCount.incrementAndGet();
                return 5;
            }
        };

        var scheduler = new RetentionScheduler();
        scheduler.tracker = tracker;
        scheduler.retentionDays = 90;

        scheduler.purge();

        assertThat(capturedCount.get()).isEqualTo(1);
        Instant expected = Instant.now().minus(90, ChronoUnit.DAYS);
        assertThat(capturedCutoff.get())
            .isBetween(expected.minusSeconds(2), expected.plusSeconds(2));
    }

    @Test
    void purge_swallowsExceptionWithoutRethrowing() {
        RetrievalTracker tracker = new StubTracker() {
            @Override
            public int purgeOlderThan(Instant cutoff) {
                throw new RuntimeException("simulated failure");
            }
        };

        var scheduler = new RetentionScheduler();
        scheduler.tracker = tracker;
        scheduler.retentionDays = 30;

        // Must not throw — exception is caught and logged
        scheduler.purge();
    }

    @Test
    void start_doesNotCreateExecutorWhenDisabled() {
        var scheduler = new RetentionScheduler();
        scheduler.retentionDays = 0;
        scheduler.start();

        // executor remains null — stop() is a no-op
        scheduler.stop();
    }
}
```

Where `StubTracker` is a minimal no-op implementation. Add it as a private
static inner class or a package-private helper that returns defaults for all
`RetrievalTracker` methods except `purgeOlderThan`.

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-tracking -am -Dtest=RetentionSchedulerTest
```

Expected: FAIL — `RetentionScheduler` class does not exist.

- [ ] **Step 3: Implement RetentionScheduler**

Create `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/RetentionScheduler.java`:

```java
package io.casehub.neocortex.rag.tracking;

import io.casehub.neocortex.rag.RetrievalTracker;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.jboss.logging.Logger;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

@ApplicationScoped
@IfBuildProperty(name = "casehub.rag.tracking.enabled", stringValue = "true")
public class RetentionScheduler {

    private static final Logger LOG = Logger.getLogger(RetentionScheduler.class);

    @Inject RetrievalTracker tracker;

    @ConfigProperty(name = "casehub.rag.tracking.retention.days", defaultValue = "90")
    int retentionDays;

    private ScheduledExecutorService executor;

    @PostConstruct
    void start() {
        if (retentionDays <= 0) return;
        executor = Executors.newSingleThreadScheduledExecutor(r -> {
            Thread t = new Thread(r, "rag-retention-purge");
            t.setDaemon(true);
            return t;
        });
        executor.scheduleAtFixedRate(this::purge, 1, 24, TimeUnit.HOURS);
        LOG.infof("Retention scheduler started: %d-day retention, purge every 24h", retentionDays);
    }

    @PreDestroy
    void stop() {
        if (executor != null) executor.shutdown();
    }

    void purge() {
        try {
            Instant cutoff = Instant.now().minus(retentionDays, ChronoUnit.DAYS);
            int deleted = tracker.purgeOlderThan(cutoff);
            LOG.infof("Retention purge: deleted %d records older than %s", deleted, cutoff);
        } catch (Exception e) {
            LOG.error("Retention purge failed — will retry next cycle", e);
        }
    }
}
```

- [ ] **Step 4: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-tracking -am -Dtest=RetentionSchedulerTest
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-tracking
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#110): RetentionScheduler — background purge with configurable TTL

ScheduledExecutorService with daemon thread, exception-safe purge(),
graceful shutdown(). Default 90-day retention. Gated by
casehub.rag.tracking.enabled. Disabled when retention.days ≤ 0."
```

---

### Task 4: ScoredGrade + RerankingLogic

The static utility that both the reranking decorator and CRAG score propagation
depend on. Pure logic, no CDI.

**Files:**
- Create: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/ScoredGrade.java`
- Create: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/reranking/RerankingLogic.java`
- Create: `rag-crossencoder/src/test/java/io/casehub/neocortex/rag/crossencoder/reranking/RerankingLogicTest.java`

**Interfaces:**
- Consumes: `CrossEncoderReranker.rerank(String, List<String>)` → `List<RankedResult>`, `RetrievedChunk`
- Produces:
  - `record ScoredGrade(RelevanceGrade grade, float score)`
  - `RerankingLogic.rerank(CrossEncoderReranker, String, List<RetrievedChunk>, int)` → `List<RetrievedChunk>`
  - `RerankingLogic.attachScores(List<RetrievedChunk>, float[])` → `List<RetrievedChunk>`
  - `RerankingLogic.hasPrecomputedScores(List<RetrievedChunk>)` → `boolean`
  - `RerankingLogic.isAlreadyReranked(List<RetrievedChunk>)` → `boolean`
  - `RerankingLogic.stamp(List<RetrievedChunk>)` → `List<RetrievedChunk>`
  - Constants: `SCORE_KEY = "_crossEncoderScore"`, `RERANKED_KEY = "_reranked"`

- [ ] **Step 1: Write the tests**

Create `rag-crossencoder/src/test/java/io/casehub/neocortex/rag/crossencoder/reranking/RerankingLogicTest.java`:

```java
package io.casehub.neocortex.rag.crossencoder.reranking;

import io.casehub.neocortex.inference.InferenceInput;
import io.casehub.neocortex.inference.InferenceModel;
import io.casehub.neocortex.inference.InferenceOutput;
import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.rag.RelevanceGrade;
import io.casehub.neocortex.rag.RetrievedChunk;
import org.junit.jupiter.api.Test;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class RerankingLogicTest {

    @Test
    void rerank_sortsAndTruncatesByScore() {
        var reranker = new CrossEncoderReranker(stubModel(0.9f, 0.1f, 0.5f));
        var chunks = List.of(
            chunk("high", "d1", 0.8),
            chunk("low", "d2", 0.9),
            chunk("mid", "d3", 0.7));

        List<RetrievedChunk> result = RerankingLogic.rerank(reranker, "query", chunks, 2);

        assertThat(result).hasSize(2);
        assertThat(result.get(0).content()).isEqualTo("high");  // score 0.9
        assertThat(result.get(1).content()).isEqualTo("mid");   // score 0.5
    }

    @Test
    void rerank_usesPrecomputedScoresWhenAvailable() {
        var chunks = List.of(
            chunkWithScore("a", "d1", 0.3, 0.1f),
            chunkWithScore("b", "d2", 0.8, 0.9f));

        // reranker should NOT be called — pass null to prove it
        List<RetrievedChunk> result = RerankingLogic.rerank(null, "query", chunks, 2);

        assertThat(result.get(0).content()).isEqualTo("b");  // precomputed 0.9
        assertThat(result.get(1).content()).isEqualTo("a");  // precomputed 0.1
    }

    @Test
    void attachScores_writesScoresToMetadata() {
        var chunks = List.of(chunk("a", "d1", 0.5), chunk("b", "d2", 0.6));
        float[] scores = {0.8f, 0.2f};

        List<RetrievedChunk> scored = RerankingLogic.attachScores(chunks, scores);

        assertThat(scored.get(0).metadata()).containsEntry(RerankingLogic.SCORE_KEY, "0.8");
        assertThat(scored.get(1).metadata()).containsEntry(RerankingLogic.SCORE_KEY, "0.2");
    }

    @Test
    void hasPrecomputedScores_trueWhenAllHaveKey() {
        var chunks = List.of(
            chunkWithScore("a", "d1", 0.5, 0.8f),
            chunkWithScore("b", "d2", 0.6, 0.2f));
        assertThat(RerankingLogic.hasPrecomputedScores(chunks)).isTrue();
    }

    @Test
    void hasPrecomputedScores_falseWhenNoneHaveKey() {
        var chunks = List.of(chunk("a", "d1", 0.5));
        assertThat(RerankingLogic.hasPrecomputedScores(chunks)).isFalse();
    }

    @Test
    void hasPrecomputedScores_falseOnPartialScores() {
        var chunks = List.of(
            chunkWithScore("a", "d1", 0.5, 0.8f),
            chunk("b", "d2", 0.6));
        assertThat(RerankingLogic.hasPrecomputedScores(chunks)).isFalse();
    }

    @Test
    void stamp_preventsDoubleApplication() {
        var chunks = List.of(chunk("a", "d1", 0.5));
        assertThat(RerankingLogic.isAlreadyReranked(chunks)).isFalse();

        List<RetrievedChunk> stamped = RerankingLogic.stamp(chunks);
        assertThat(RerankingLogic.isAlreadyReranked(stamped)).isTrue();
    }

    @Test
    void stamp_isDistinctFromScoreKey() {
        var scored = List.of(chunkWithScore("a", "d1", 0.5, 0.8f));
        assertThat(RerankingLogic.isAlreadyReranked(scored)).isFalse();
    }

    @Test
    void rerank_emptyInputReturnsEmpty() {
        List<RetrievedChunk> result = RerankingLogic.rerank(null, "q", List.of(), 10);
        assertThat(result).isEmpty();
    }

    // --- helpers ---

    static RetrievedChunk chunk(String content, String docId, double score) {
        return new RetrievedChunk(content, docId, score, Map.of());
    }

    static RetrievedChunk chunkWithScore(String content, String docId,
                                          double relevance, float ceScore) {
        return new RetrievedChunk(content, docId, relevance,
            Map.of(RerankingLogic.SCORE_KEY, String.valueOf(ceScore)));
    }

    static InferenceModel stubModel(float... scores) {
        return new InferenceModel() {
            int idx = 0;
            @Override public InferenceOutput run(InferenceInput input) {
                return new InferenceOutput(new float[]{scores[idx++]});
            }
            @Override public List<InferenceOutput> runBatch(List<InferenceInput> inputs) {
                return inputs.stream()
                    .map(i -> new InferenceOutput(new float[]{scores[idx++]}))
                    .toList();
            }
            @Override public Optional<Integer> outputSize() { return Optional.of(1); }
        };
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crossencoder -am -Dtest=RerankingLogicTest
```

Expected: FAIL — classes do not exist.

- [ ] **Step 3: Create `ScoredGrade` record**

Create `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/ScoredGrade.java`:

```java
package io.casehub.neocortex.rag.crossencoder;

import io.casehub.neocortex.rag.RelevanceGrade;

public record ScoredGrade(RelevanceGrade grade, float score) {}
```

- [ ] **Step 4: Create `RerankingLogic`**

Create `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/reranking/RerankingLogic.java`:

```java
package io.casehub.neocortex.rag.crossencoder.reranking;

import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.inference.tasks.RankedResult;
import io.casehub.neocortex.rag.RetrievedChunk;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class RerankingLogic {

    static final String SCORE_KEY = "_crossEncoderScore";
    static final String RERANKED_KEY = "_reranked";

    private RerankingLogic() {}

    public static List<RetrievedChunk> rerank(CrossEncoderReranker reranker,
                                               String queryText,
                                               List<RetrievedChunk> chunks,
                                               int maxResults) {
        if (chunks.isEmpty()) return List.of();

        if (hasPrecomputedScores(chunks)) {
            return sortByPrecomputedScores(chunks, maxResults);
        }

        List<String> contents = chunks.stream()
            .map(RetrievedChunk::content).toList();
        List<RankedResult> ranked = reranker.rerank(queryText, contents);

        List<RetrievedChunk> result = new ArrayList<>(
            Math.min(ranked.size(), maxResults));
        for (int i = 0; i < Math.min(ranked.size(), maxResults); i++) {
            RankedResult r = ranked.get(i);
            RetrievedChunk original = chunks.get(r.originalIndex());
            var augmented = new HashMap<>(original.metadata());
            augmented.put(SCORE_KEY, String.valueOf(r.score()));
            result.add(original.withMetadata(augmented));
        }
        return List.copyOf(result);
    }

    public static List<RetrievedChunk> attachScores(List<RetrievedChunk> chunks,
                                                     float[] scores) {
        List<RetrievedChunk> result = new ArrayList<>(chunks.size());
        for (int i = 0; i < chunks.size(); i++) {
            var augmented = new HashMap<>(chunks.get(i).metadata());
            augmented.put(SCORE_KEY, String.valueOf(scores[i]));
            result.add(chunks.get(i).withMetadata(augmented));
        }
        return List.copyOf(result);
    }

    public static boolean hasPrecomputedScores(List<RetrievedChunk> chunks) {
        return !chunks.isEmpty()
            && chunks.stream().allMatch(c -> c.metadata().containsKey(SCORE_KEY));
    }

    public static boolean isAlreadyReranked(List<RetrievedChunk> chunks) {
        return !chunks.isEmpty()
            && chunks.stream().anyMatch(c -> c.metadata().containsKey(RERANKED_KEY));
    }

    public static List<RetrievedChunk> stamp(List<RetrievedChunk> chunks) {
        return chunks.stream()
            .map(c -> {
                var augmented = new HashMap<>(c.metadata());
                augmented.put(RERANKED_KEY, "true");
                return c.withMetadata(augmented);
            })
            .toList();
    }

    private static List<RetrievedChunk> sortByPrecomputedScores(
            List<RetrievedChunk> chunks, int maxResults) {
        return chunks.stream()
            .sorted(Comparator.comparingDouble(
                (RetrievedChunk c) -> Float.parseFloat(c.metadata().get(SCORE_KEY)))
                .reversed())
            .limit(maxResults)
            .toList();
    }
}
```

- [ ] **Step 5: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crossencoder -am -Dtest=RerankingLogicTest
```

Expected: 9 tests PASS.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-crossencoder
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#121): ScoredGrade + RerankingLogic — cross-encoder scoring utilities

Static utility for reranking: sorts by cross-encoder score, supports
precomputed score propagation from CRAG, stamp/guard for bridge
double-application. Distinct _reranked key from _crossEncoderScore."
```

---

### Task 5: Score propagation in CrossEncoderRelevanceEvaluator + CRAG decorators

Adds `evaluateBatchWithScores()` to `CrossEncoderRelevanceEvaluator`. Modifies
both `CorrectiveCaseRetriever` and `ReactiveCorrectiveCaseRetriever` to attach
cross-encoder scores to surviving chunks at ALL evaluation call sites (initial
and expansion).

**Files:**
- Modify: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/corrective/CrossEncoderRelevanceEvaluator.java`
- Modify: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/corrective/CorrectiveCaseRetriever.java`
- Modify: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/corrective/ReactiveCorrectiveCaseRetriever.java`
- Modify: `rag-crossencoder/src/test/java/io/casehub/neocortex/rag/crossencoder/corrective/CrossEncoderRelevanceEvaluatorTest.java`
- Create: `rag-crossencoder/src/test/java/io/casehub/neocortex/rag/crossencoder/corrective/ScorePropagationTest.java`

**Interfaces:**
- Consumes: `RerankingLogic.attachScores(chunks, scores)` from Task 4, `ScoredGrade` from Task 4
- Produces: `CrossEncoderRelevanceEvaluator.evaluateBatchWithScores(String, List<String>)` → `List<ScoredGrade>`

- [ ] **Step 1: Write test for `evaluateBatchWithScores`**

Add to `CrossEncoderRelevanceEvaluatorTest.java`:

```java
@Test
void evaluateBatchWithScores_returnsGradesAndRawScores() {
    // Use a model that returns known scores
    var model = stubModel(0.9f, 0.1f, 0.5f);
    var reranker = new CrossEncoderReranker(model);
    var evaluator = new CrossEncoderRelevanceEvaluator(reranker, 0.7, 0.3);

    List<ScoredGrade> results = evaluator.evaluateBatchWithScores(
        "query", List.of("correct", "incorrect", "ambiguous"));

    assertThat(results).hasSize(3);
    // Results are in original order (not ranked order)
    assertThat(results.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
    assertThat(results.get(0).score()).isEqualTo(0.9f);
    assertThat(results.get(1).grade()).isEqualTo(RelevanceGrade.INCORRECT);
    assertThat(results.get(1).score()).isEqualTo(0.1f);
    assertThat(results.get(2).grade()).isEqualTo(RelevanceGrade.AMBIGUOUS);
    assertThat(results.get(2).score()).isEqualTo(0.5f);
}
```

- [ ] **Step 2: Write score propagation integration test**

Create `ScorePropagationTest.java` — tests that `CorrectiveCaseRetriever`
attaches cross-encoder scores to output chunks when using
`CrossEncoderRelevanceEvaluator`:

```java
package io.casehub.neocortex.rag.crossencoder.corrective;

import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.rag.*;
import io.casehub.neocortex.rag.crossencoder.reranking.RerankingLogic;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class ScorePropagationTest {

    @Test
    void correctiveCaseRetriever_attachesScoresToSurvivingChunks() {
        // Model returns: 0.9 (CORRECT), 0.8 (CORRECT), 0.1 (INCORRECT)
        var reranker = new CrossEncoderReranker(
            RerankingLogicTest.stubModel(0.9f, 0.8f, 0.1f));
        var evaluator = new CrossEncoderRelevanceEvaluator(reranker, 0.7, 0.3);
        var config = stubConfig();

        var delegate = stubRetriever(List.of(
            chunk("good1", "d1", 0.9),
            chunk("good2", "d2", 0.8),
            chunk("bad", "d3", 0.7)));

        var retriever = new CorrectiveCaseRetriever(
            delegate, evaluator, config, e -> {});

        List<RetrievedChunk> results = retriever.retrieve(
            RetrievalQuery.of("test"), new CorpusRef("t1", "c1"), 10, null);

        // INCORRECT chunk filtered, 2 survivors carry scores
        assertThat(results).hasSize(2);
        assertThat(RerankingLogic.hasPrecomputedScores(results)).isTrue();
        assertThat(results.get(0).metadata().get(RerankingLogic.SCORE_KEY))
            .isEqualTo("0.9");
    }

    // stub helpers (delegate, config, chunk)
}
```

(Adapt helper stubs from existing `CorrectiveCaseRetrieverTest` patterns.)

- [ ] **Step 3: Add `evaluateBatchWithScores` to `CrossEncoderRelevanceEvaluator`**

```java
public List<ScoredGrade> evaluateBatchWithScores(String query,
                                                  List<String> chunkContents) {
    if (chunkContents.isEmpty()) return List.of();
    List<RankedResult> ranked = reranker.rerank(query, chunkContents);
    ScoredGrade[] results = new ScoredGrade[chunkContents.size()];
    for (RankedResult r : ranked) {
        results[r.originalIndex()] = new ScoredGrade(
            gradeFromScore(r.score()), r.score());
    }
    return List.of(results);
}
```

Refactor existing `evaluateBatch()` to delegate:
```java
@Override
public List<RelevanceGrade> evaluateBatch(String query, List<String> chunkContents) {
    return evaluateBatchWithScores(query, chunkContents).stream()
        .map(ScoredGrade::grade).toList();
}
```

- [ ] **Step 4: Modify `CorrectiveCaseRetriever` for score propagation**

At both evaluation call sites (initial and expansion), when evaluator is
`CrossEncoderRelevanceEvaluator`, use `evaluateBatchWithScores()` and
attach scores to survivors via `RerankingLogic.attachScores()`.

Replace the evaluation logic in `retrieve()`:

```java
// Where evaluator.evaluateBatch() is called:
List<RelevanceGrade> grades;
float[] scores = null;
if (evaluator instanceof CrossEncoderRelevanceEvaluator ceEval) {
    var scored = ceEval.evaluateBatchWithScores(query.text(), contents);
    grades = scored.stream().map(ScoredGrade::grade).toList();
    scores = new float[scored.size()];
    for (int i = 0; i < scored.size(); i++) scores[i] = scored.get(i).score();
} else {
    grades = evaluator.evaluateBatch(query.text(), contents);
}
var initial = CragEvaluationLogic.gradeChunks(chunks, grades);

// After filterIncorrect:
List<RetrievedChunk> surviving = new ArrayList<>(
    CragEvaluationLogic.filterIncorrect(initial.graded()));
if (scores != null) {
    surviving = new ArrayList<>(attachSurvivingScores(surviving, chunks, scores));
}
```

Apply the SAME pattern to the expansion path.

- [ ] **Step 5: Modify `ReactiveCorrectiveCaseRetriever` identically**

Same `instanceof` check and `attachScores` logic at both evaluation call sites.

- [ ] **Step 6: Run all crossencoder tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crossencoder -am
```

Expected: All existing CRAG tests + new score propagation tests pass.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-crossencoder
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#121): score propagation — CRAG attaches cross-encoder scores to chunks

evaluateBatchWithScores() on CrossEncoderRelevanceEvaluator returns
ScoredGrade(grade, score). Both CorrectiveCaseRetriever and
ReactiveCorrectiveCaseRetriever attach scores at initial AND expansion
call sites. Eliminates double inference when reranking is co-enabled."
```

---

### Task 6: RerankingCaseRetriever + ReactiveRerankingCaseRetriever + RerankingConfig

The decorator pair. Priority 75. `@IfBuildProperty` gated. Overfetch via
`max(limit, rerankPoolSize)`. Stamp after reranking.

**Files:**
- Create: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/reranking/RerankingConfig.java`
- Create: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/reranking/RerankingCaseRetriever.java`
- Create: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/reranking/ReactiveRerankingCaseRetriever.java`
- Create: `rag-crossencoder/src/test/java/io/casehub/neocortex/rag/crossencoder/reranking/RerankingCaseRetrieverTest.java`
- Create: `rag-crossencoder/src/test/java/io/casehub/neocortex/rag/crossencoder/reranking/ReactiveRerankingCaseRetrieverTest.java`

**Interfaces:**
- Consumes: `RerankingLogic` from Task 4, `CrossEncoderReranker` CDI bean, `CaseRetriever` delegate
- Produces: `RerankingCaseRetriever implements CaseRetriever` (`@Decorator @Priority(75)`), reactive mirror

- [ ] **Step 1: Write tests for blocking variant**

Create `RerankingCaseRetrieverTest.java`:

```java
package io.casehub.neocortex.rag.crossencoder.reranking;

import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.rag.*;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

class RerankingCaseRetrieverTest {

    static final CorpusRef CORPUS = new CorpusRef("t1", "c1");

    @Test
    void overfetch_usesMaxOfLimitAndPoolSize() {
        AtomicInteger capturedLimit = new AtomicInteger();
        CaseRetriever delegate = (q, c, max, f) -> {
            capturedLimit.set(max);
            return List.of(chunk("a", "d1", 0.5), chunk("b", "d2", 0.6));
        };

        var reranker = new CrossEncoderReranker(RerankingLogicTest.stubModel(0.3f, 0.8f));
        var retriever = new RerankingCaseRetriever(delegate, reranker, config(30));

        retriever.retrieve(RetrievalQuery.of("q"), CORPUS, 10, null);

        assertThat(capturedLimit.get()).isEqualTo(30); // max(10, 30)
    }

    @Test
    void rerank_sortsOutputByCrossEncoderScore() {
        CaseRetriever delegate = (q, c, max, f) -> List.of(
            chunk("low-ce", "d1", 0.9),   // high original, low CE
            chunk("high-ce", "d2", 0.1)); // low original, high CE

        var reranker = new CrossEncoderReranker(RerankingLogicTest.stubModel(0.1f, 0.9f));
        var retriever = new RerankingCaseRetriever(delegate, reranker, config(30));

        var results = retriever.retrieve(RetrievalQuery.of("q"), CORPUS, 2, null);

        assertThat(results.get(0).content()).isEqualTo("high-ce");
        assertThat(results.get(1).content()).isEqualTo("low-ce");
    }

    @Test
    void rerank_truncatesToMaxResults() {
        CaseRetriever delegate = (q, c, max, f) -> List.of(
            chunk("a", "d1", 0.5),
            chunk("b", "d2", 0.6),
            chunk("c", "d3", 0.7));

        var reranker = new CrossEncoderReranker(
            RerankingLogicTest.stubModel(0.3f, 0.8f, 0.5f));
        var retriever = new RerankingCaseRetriever(delegate, reranker, config(30));

        var results = retriever.retrieve(RetrievalQuery.of("q"), CORPUS, 2, null);

        assertThat(results).hasSize(2);
    }

    @Test
    void alreadyReranked_passesThrough() {
        var stamped = RerankingLogic.stamp(List.of(chunk("a", "d1", 0.5)));
        CaseRetriever delegate = (q, c, max, f) -> stamped;

        var retriever = new RerankingCaseRetriever(delegate, null, config(30));

        var results = retriever.retrieve(RetrievalQuery.of("q"), CORPUS, 10, null);

        assertThat(results).hasSize(1);
        assertThat(results.get(0).content()).isEqualTo("a");
    }

    @Test
    void stampsOutputToPreventBridgeReentry() {
        CaseRetriever delegate = (q, c, max, f) ->
            List.of(chunk("a", "d1", 0.5));

        var reranker = new CrossEncoderReranker(RerankingLogicTest.stubModel(0.7f));
        var retriever = new RerankingCaseRetriever(delegate, reranker, config(30));

        var results = retriever.retrieve(RetrievalQuery.of("q"), CORPUS, 10, null);

        assertThat(RerankingLogic.isAlreadyReranked(results)).isTrue();
    }

    static RetrievedChunk chunk(String content, String docId, double score) {
        return new RetrievedChunk(content, docId, score, Map.of());
    }

    static RerankingConfig config(int poolSize) {
        return new RerankingConfig() {
            @Override public boolean enabled() { return true; }
            @Override public int rerankPoolSize() { return poolSize; }
        };
    }
}
```

- [ ] **Step 2: Create `RerankingConfig`**

```java
package io.casehub.neocortex.rag.crossencoder.reranking;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.rag.reranking")
public interface RerankingConfig {
    @WithDefault("false")
    boolean enabled();

    @WithDefault("30")
    int rerankPoolSize();
}
```

- [ ] **Step 3: Create `RerankingCaseRetriever`**

```java
package io.casehub.neocortex.rag.crossencoder.reranking;

import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.rag.CaseRetriever;
import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.PayloadFilter;
import io.casehub.neocortex.rag.RetrievalQuery;
import io.casehub.neocortex.rag.RetrievedChunk;
import io.quarkus.arc.Unremovable;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.List;

@Decorator
@Priority(75)
@Unremovable
@IfBuildProperty(name = "casehub.rag.reranking.enabled", stringValue = "true")
public class RerankingCaseRetriever implements CaseRetriever {

    private final CaseRetriever delegate;
    private final CrossEncoderReranker reranker;
    private final RerankingConfig config;

    @Inject
    RerankingCaseRetriever(@Delegate @Any CaseRetriever delegate,
                           CrossEncoderReranker reranker,
                           RerankingConfig config) {
        this.delegate = delegate;
        this.reranker = reranker;
        this.config = config;
    }

    // Package-private constructor for unit tests
    RerankingCaseRetriever(CaseRetriever delegate,
                           CrossEncoderReranker reranker,
                           RerankingConfig config) {
        this.delegate = delegate;
        this.reranker = reranker;
        this.config = config;
    }

    @Override
    public List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus,
                                          int maxResults, PayloadFilter filter) {
        int fetchSize = Math.max(maxResults, config.rerankPoolSize());
        List<RetrievedChunk> candidates = delegate.retrieve(
            query, corpus, fetchSize, filter);
        if (RerankingLogic.isAlreadyReranked(candidates)) {
            return candidates.subList(0, Math.min(candidates.size(), maxResults));
        }
        return RerankingLogic.stamp(
            RerankingLogic.rerank(reranker, query.text(), candidates, maxResults));
    }
}
```

- [ ] **Step 4: Create `ReactiveRerankingCaseRetriever`**

```java
package io.casehub.neocortex.rag.crossencoder.reranking;

import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.PayloadFilter;
import io.casehub.neocortex.rag.ReactiveCaseRetriever;
import io.casehub.neocortex.rag.RetrievalQuery;
import io.casehub.neocortex.rag.RetrievedChunk;
import io.quarkus.arc.Unremovable;
import io.quarkus.arc.properties.IfBuildProperty;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.List;

@Decorator
@Priority(75)
@Unremovable
@IfBuildProperty(name = "casehub.rag.reranking.enabled", stringValue = "true")
public class ReactiveRerankingCaseRetriever implements ReactiveCaseRetriever {

    private final ReactiveCaseRetriever delegate;
    private final CrossEncoderReranker reranker;
    private final RerankingConfig config;

    @Inject
    ReactiveRerankingCaseRetriever(@Delegate @Any ReactiveCaseRetriever delegate,
                                    CrossEncoderReranker reranker,
                                    RerankingConfig config) {
        this.delegate = delegate;
        this.reranker = reranker;
        this.config = config;
    }

    @Override
    public Uni<List<RetrievedChunk>> retrieve(RetrievalQuery query, CorpusRef corpus,
                                               int maxResults, PayloadFilter filter) {
        int fetchSize = Math.max(maxResults, config.rerankPoolSize());
        return delegate.retrieve(query, corpus, fetchSize, filter)
            .onItem().transformToUni(candidates -> {
                if (RerankingLogic.isAlreadyReranked(candidates)) {
                    return Uni.createFrom().item(
                        candidates.subList(0, Math.min(candidates.size(), maxResults)));
                }
                return Uni.createFrom().item(() ->
                    RerankingLogic.stamp(
                        RerankingLogic.rerank(reranker, query.text(),
                            candidates, maxResults)))
                    .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
            });
    }
}
```

- [ ] **Step 5: Write reactive variant test**

Create `ReactiveRerankingCaseRetrieverTest.java` — mirror of blocking test
using `Uni` assertions. Key tests: overfetch, sort order, stamp, already-reranked
passthrough.

- [ ] **Step 6: Run all tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-crossencoder -am
```

Expected: All CRAG tests + RerankingLogic tests + decorator tests pass.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-crossencoder
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#121): RerankingCaseRetriever — cross-encoder reranking decorator

@Decorator @Priority(75) with blocking and reactive variants.
Overfetch via max(limit, rerankPoolSize). Stamps output to prevent
bridge re-entry. Uses precomputed CRAG scores when available."
```

---

### Task 7: CrossEncoderBeanProducer update + CLAUDE.md

Update the renamed bean producer. Update CLAUDE.md module table,
maven coordinates, and module descriptions.

**Files:**
- Modify: `rag-crossencoder/src/main/java/io/casehub/neocortex/rag/crossencoder/CrossEncoderBeanProducer.java`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: all previous tasks
- Produces: updated documentation and CDI wiring

- [ ] **Step 1: Update `CrossEncoderBeanProducer`**

The producer was renamed in Task 1. Now update its `@IfBuildProperty` gate —
remove it (the producer should be ungated per the spec). The decorators
themselves are gated. The producer's `Instance<CrossEncoderReranker>` is lazy
and only fires when a decorator requests `RelevanceEvaluator`.

Ensure the producer class has NO `@IfBuildProperty` annotation. Verify it
still produces `RelevanceEvaluator` for CRAG via `Instance<CrossEncoderReranker>`.

- [ ] **Step 2: Update CLAUDE.md**

In the module table:
- Replace `rag-crag/` entry with `rag-crossencoder/` — update description to
  mention both corrective RAG and cross-encoder reranking
- Update `rag-tracking/` description to mention `RetentionScheduler`
- Update `rag-api/` description to mention `purgeOlderThan`

In maven coordinates table:
- Replace `casehub-neocortex-rag-crag` → `casehub-neocortex-rag-crossencoder`
- Add root Java package for reranking: `io.casehub.neocortex.rag.crossencoder.reranking`

- [ ] **Step 3: Full build**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

Expected: BUILD SUCCESS across all modules.

- [ ] **Step 4: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-crossencoder CLAUDE.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "chore(#110,#121): CrossEncoderBeanProducer ungated + CLAUDE.md sync

Bean producer active when module on classpath — decorators handle their
own IfBuildProperty gates. CLAUDE.md updated: rag-crossencoder module,
purgeOlderThan on RetrievalTracker, RetentionScheduler, maven coords."
```
