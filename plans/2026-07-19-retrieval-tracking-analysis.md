# Retrieval Tracking Analysis Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #109 — feat: retrieval tracking analysis service — aggregation, curation recommendations
**Issue group:** #109

**Goal:** Add a pure-computation analysis layer to rag-api that interprets raw retrieval tracking data into per-document statistics and quality signals.

**Architecture:** Static utility class `RetrievalAnalyzer` with three methods (`documentStats`, `unretrievedDocuments`, `qualitySignals`) operating over existing `RetrievalTracker` and `EmbeddingIngestor` SPIs. Four new value types (`DocumentStats`, `DocumentQualitySignal`, `QualitySignal`, `QualityThresholds`) in the same package. All code in `rag-api` — no new module, no new dependencies.

**Tech Stack:** Java 21, no additional dependencies beyond what rag-api already has (Mutiny provided scope, JUnit 5 + AssertJ for tests).

## Global Constraints

- All code in `rag-api` module, package `io.casehub.neocortex.rag`
- No dependency on `rag-testing` (would be circular) — tests use inline stubs
- No CDI, no Quarkus annotations — pure Java
- `RetrievalAnalyzer` methods are `public static` — stateless, no instance state
- Field naming: `averageRetrievalScore` (not `averageRelevanceScore` — R1-07)
- Feedback follows via `retrievalId` join, not by its own timestamp — R1-02
- `findFeedback` called with `Instant.MAX` upper bound to capture late feedback — R1-02
- `QualityThresholds` has 4 fields including `minFeedbackForQualityCheck` — R3-02
- Severity ordering: NEVER_RETRIEVED > HIGH_RETRIEVAL_LOW_QUALITY > STALE — R1-08

---

### Task 1: Value Types and QualityThresholds Validation

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/QualitySignal.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/QualityThresholds.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/DocumentStats.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/DocumentQualitySignal.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/QualityThresholdsTest.java`

**Interfaces:**
- Consumes: `RetrievalOutcome` (existing enum in rag-api)
- Produces: `QualitySignal` enum, `QualityThresholds` record with `defaults()` and validation, `DocumentStats` record, `DocumentQualitySignal` record — used by Tasks 2–4

- [ ] **Step 1: Write QualityThresholds validation tests**

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import java.time.Duration;
import static org.assertj.core.api.Assertions.*;

class QualityThresholdsTest {

    @Test
    void defaults_returnsExpectedValues() {
        var t = QualityThresholds.defaults();
        assertThat(t.minRetrievalsForQualityCheck()).isEqualTo(3);
        assertThat(t.minFeedbackForQualityCheck()).isEqualTo(3);
        assertThat(t.lowQualityRatio()).isEqualTo(0.7);
        assertThat(t.staleWindow()).isEqualTo(Duration.ofDays(90));
    }

    @Test
    void rejectsNegativeMinRetrievals() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new QualityThresholds(0, 3, 0.7, Duration.ofDays(90)));
    }

    @Test
    void rejectsNegativeMinFeedback() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new QualityThresholds(3, 0, 0.7, Duration.ofDays(90)));
    }

    @Test
    void rejectsRatioAboveOne() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new QualityThresholds(3, 3, 1.1, Duration.ofDays(90)));
    }

    @Test
    void rejectsNegativeRatio() {
        assertThatIllegalArgumentException()
                .isThrownBy(() -> new QualityThresholds(3, 3, -0.1, Duration.ofDays(90)));
    }

    @Test
    void rejectsNullStaleWindow() {
        assertThatNullPointerException()
                .isThrownBy(() -> new QualityThresholds(3, 3, 0.7, null));
    }

    @Test
    void acceptsBoundaryValues() {
        assertThatNoException()
                .isThrownBy(() -> new QualityThresholds(1, 1, 0.0, Duration.ofDays(1)));
        assertThatNoException()
                .isThrownBy(() -> new QualityThresholds(1, 1, 1.0, Duration.ofDays(1)));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=QualityThresholdsTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure — `QualityThresholds` does not exist yet.

- [ ] **Step 3: Create QualitySignal enum**

Use `ide_create_file`:

```java
package io.casehub.neocortex.rag;

public enum QualitySignal {
    NEVER_RETRIEVED,
    HIGH_RETRIEVAL_LOW_QUALITY,
    STALE
}
```

- [ ] **Step 4: Create QualityThresholds record**

Use `ide_create_file`:

```java
package io.casehub.neocortex.rag;

import java.time.Duration;
import java.util.Objects;

public record QualityThresholds(
        int minRetrievalsForQualityCheck,
        int minFeedbackForQualityCheck,
        double lowQualityRatio,
        Duration staleWindow) {

    public QualityThresholds {
        if (minRetrievalsForQualityCheck < 1) {
            throw new IllegalArgumentException(
                    "minRetrievalsForQualityCheck must be >= 1, got " + minRetrievalsForQualityCheck);
        }
        if (minFeedbackForQualityCheck < 1) {
            throw new IllegalArgumentException(
                    "minFeedbackForQualityCheck must be >= 1, got " + minFeedbackForQualityCheck);
        }
        if (lowQualityRatio < 0.0 || lowQualityRatio > 1.0) {
            throw new IllegalArgumentException(
                    "lowQualityRatio must be in [0, 1], got " + lowQualityRatio);
        }
        Objects.requireNonNull(staleWindow, "staleWindow must not be null");
    }

    public static QualityThresholds defaults() {
        return new QualityThresholds(3, 3, 0.7, Duration.ofDays(90));
    }
}
```

- [ ] **Step 5: Create DocumentStats record**

Use `ide_create_file`:

```java
package io.casehub.neocortex.rag;

import java.time.Instant;
import java.util.Map;

public record DocumentStats(
        String sourceDocumentId,
        int retrievalCount,
        Instant firstRetrieved,
        Instant lastRetrieved,
        double averageRetrievalScore,
        Map<RetrievalOutcome, Integer> feedbackDistribution) {

    public DocumentStats {
        feedbackDistribution = Map.copyOf(feedbackDistribution);
    }
}
```

- [ ] **Step 6: Create DocumentQualitySignal record**

Use `ide_create_file`:

```java
package io.casehub.neocortex.rag;

public record DocumentQualitySignal(
        String sourceDocumentId,
        DocumentStats stats,
        QualitySignal signal) {
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=QualityThresholdsTest`
Expected: All 7 tests PASS.

- [ ] **Step 8: Commit**

```bash
git add rag-api/src/main/java/io/casehub/neocortex/rag/QualitySignal.java \
       rag-api/src/main/java/io/casehub/neocortex/rag/QualityThresholds.java \
       rag-api/src/main/java/io/casehub/neocortex/rag/DocumentStats.java \
       rag-api/src/main/java/io/casehub/neocortex/rag/DocumentQualitySignal.java \
       rag-api/src/test/java/io/casehub/neocortex/rag/QualityThresholdsTest.java
git commit -m "feat(#109): add retrieval analysis value types — QualitySignal, QualityThresholds, DocumentStats, DocumentQualitySignal"
```

---

### Task 2: RetrievalAnalyzer.documentStats()

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerDocumentStatsTest.java`

**Interfaces:**
- Consumes: `RetrievalTracker.findRecords(CorpusRef, Instant, Instant)` → `List<RetrievalRecord>`, `RetrievalTracker.findFeedback(CorpusRef, Instant, Instant)` → `List<RetrievalFeedback>`, `DocumentStats` (from Task 1)
- Produces: `RetrievalAnalyzer.documentStats(RetrievalTracker tracker, CorpusRef corpus, Instant since, Instant until)` → `Map<String, DocumentStats>`

**Test stub pattern:** Tests create inline `RetrievalTracker` implementations. Only `findRecords` and `findFeedback` need real implementations; other methods throw `UnsupportedOperationException`. Extract a helper to reduce boilerplate:

```java
private static RetrievalTracker stubTracker(
        List<RetrievalRecord> records,
        List<RetrievalFeedback> feedback) {
    return new RetrievalTracker() {
        @Override
        public String record(RetrievalQuery q, CorpusRef c, List<RetrievedChunk> r, int m) {
            throw new UnsupportedOperationException();
        }
        @Override
        public void feedback(String rid, String did, RetrievalOutcome o) {
            throw new UnsupportedOperationException();
        }
        @Override
        public List<RetrievalRecord> findRecords(CorpusRef c, Instant s, Instant u) {
            return records;
        }
        @Override
        public List<RetrievalFeedback> findFeedback(CorpusRef c, Instant s, Instant u) {
            return feedback;
        }
        @Override
        public Set<String> findRetrievedDocumentIds(CorpusRef c, Instant s, Instant u) {
            throw new UnsupportedOperationException();
        }
        @Override
        public int purgeOlderThan(Instant cutoff) {
            throw new UnsupportedOperationException();
        }
    };
}
```

Note: `RetrievalTracker.record()` accepts `List<RetrievedChunk>` (not `List<RetrievedDocumentRef>`). `RetrievedChunk` is from LangChain4j — check the actual import. If `RetrievedChunk` is not available in `rag-api` test scope, use `dev.langchain4j.rag.content.retriever.RetrievedChunk` or check how other rag-api tests handle this. If the type is not on the test classpath, the stub can use a raw type cast or the method signature can reference the correct type — verify at implementation time.

- [ ] **Step 1: Write failing tests for documentStats**

Create `RetrievalAnalyzerDocumentStatsTest.java`:

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class RetrievalAnalyzerDocumentStatsTest {

    private static final CorpusRef CORPUS = new CorpusRef("t1", "corpus1");
    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");
    private static final Instant T1 = Instant.parse("2026-01-02T00:00:00Z");
    private static final Instant T2 = Instant.parse("2026-01-03T00:00:00Z");
    private static final Instant T3 = Instant.parse("2026-01-04T00:00:00Z");
    private static final Instant SINCE = Instant.parse("2025-12-01T00:00:00Z");
    private static final Instant UNTIL = Instant.parse("2026-02-01T00:00:00Z");

    // Helper to build a RetrievalRecord with given docs
    private static RetrievalRecord record(String retrievalId, Instant timestamp,
                                           RetrievedDocumentRef... docs) {
        return new RetrievalRecord(retrievalId, RetrievalQuery.of("query"),
                CORPUS, List.of(docs), 10, timestamp);
    }

    private static RetrievedDocumentRef doc(String id, double score) {
        return new RetrievedDocumentRef(id, score);
    }

    // --- stubTracker helper as shown above ---

    @Test
    void singleDocSingleRetrieval() {
        var records = List.of(record("r1", T1, doc("doc-A", 0.9)));
        var tracker = stubTracker(records, List.of());

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        assertThat(result).hasSize(1);
        var stats = result.get("doc-A");
        assertThat(stats.retrievalCount()).isEqualTo(1);
        assertThat(stats.firstRetrieved()).isEqualTo(T1);
        assertThat(stats.lastRetrieved()).isEqualTo(T1);
        assertThat(stats.averageRetrievalScore()).isEqualTo(0.9);
        assertThat(stats.feedbackDistribution()).isEmpty();
    }

    @Test
    void multipleRetrievalsSameDoc() {
        var records = List.of(
                record("r1", T1, doc("doc-A", 0.8)),
                record("r2", T2, doc("doc-A", 0.6)),
                record("r3", T3, doc("doc-A", 1.0)));
        var tracker = stubTracker(records, List.of());

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        var stats = result.get("doc-A");
        assertThat(stats.retrievalCount()).isEqualTo(3);
        assertThat(stats.firstRetrieved()).isEqualTo(T1);
        assertThat(stats.lastRetrieved()).isEqualTo(T3);
        assertThat(stats.averageRetrievalScore()).isCloseTo(0.8, within(0.001));
    }

    @Test
    void multipleDocumentsIndependentStats() {
        var records = List.of(
                record("r1", T1, doc("doc-A", 0.9), doc("doc-B", 0.5)),
                record("r2", T2, doc("doc-A", 0.7)));
        var tracker = stubTracker(records, List.of());

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        assertThat(result).hasSize(2);
        assertThat(result.get("doc-A").retrievalCount()).isEqualTo(2);
        assertThat(result.get("doc-B").retrievalCount()).isEqualTo(1);
    }

    @Test
    void withFeedback_distributionPopulated() {
        var records = List.of(record("r1", T1, doc("doc-A", 0.9)));
        var feedback = List.of(
                new RetrievalFeedback("r1", "doc-A", RetrievalOutcome.RELEVANT, T2));
        var tracker = stubTracker(records, feedback);

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        assertThat(result.get("doc-A").feedbackDistribution())
                .containsEntry(RetrievalOutcome.RELEVANT, 1);
    }

    @Test
    void mixedFeedbackOutcomes_eachCounted() {
        var records = List.of(
                record("r1", T1, doc("doc-A", 0.9)),
                record("r2", T2, doc("doc-A", 0.8)));
        var feedback = List.of(
                new RetrievalFeedback("r1", "doc-A", RetrievalOutcome.NOT_RELEVANT, T1),
                new RetrievalFeedback("r2", "doc-A", RetrievalOutcome.HIGHLY_RELEVANT, T2));
        var tracker = stubTracker(records, feedback);

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        var dist = result.get("doc-A").feedbackDistribution();
        assertThat(dist).containsEntry(RetrievalOutcome.NOT_RELEVANT, 1)
                        .containsEntry(RetrievalOutcome.HIGHLY_RELEVANT, 1);
    }

    @Test
    void noRetrievalsInWindow_emptyMap() {
        var tracker = stubTracker(List.of(), List.of());

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        assertThat(result).isEmpty();
    }

    @Test
    void multipleChunksCollapsedToSameDoc_countedAsOnePerRetrieval() {
        // A single retrieval returning 2 chunks for same doc (already collapsed
        // by the tracker into one RetrievedDocumentRef with max score)
        var records = List.of(record("r1", T1, doc("doc-A", 0.9)));
        var tracker = stubTracker(records, List.of());

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        assertThat(result.get("doc-A").retrievalCount()).isEqualTo(1);
    }

    @Test
    void lateFeedbackIncluded_retrievalInWindowFeedbackAfterUntil() {
        // Retrieval at T1 (in window), feedback at T3 (after UNTIL for a tighter window)
        var records = List.of(record("r1", T1, doc("doc-A", 0.9)));
        // Feedback timestamp is after UNTIL but retrievalId matches a record in-window
        var feedback = List.of(
                new RetrievalFeedback("r1", "doc-A", RetrievalOutcome.RELEVANT,
                        Instant.parse("2026-03-01T00:00:00Z")));
        var tracker = stubTracker(records, feedback);

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        assertThat(result.get("doc-A").feedbackDistribution())
                .containsEntry(RetrievalOutcome.RELEVANT, 1);
    }

    @Test
    void outOfWindowFeedbackExcluded_retrievalOutsideWindow() {
        // Retrieval "r-outside" is NOT in findRecords (outside window)
        // but its feedback IS returned by findFeedback (widened upper bound)
        // Post-filter should discard it because retrievalId doesn't match
        var records = List.of(record("r1", T1, doc("doc-A", 0.9)));
        var feedback = List.of(
                new RetrievalFeedback("r-outside", "doc-A", RetrievalOutcome.NOT_RELEVANT, T2));
        var tracker = stubTracker(records, feedback);

        var result = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL);

        assertThat(result.get("doc-A").feedbackDistribution()).isEmpty();
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalAnalyzerDocumentStatsTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure — `RetrievalAnalyzer` does not exist.

- [ ] **Step 3: Create RetrievalAnalyzer with documentStats implementation**

Use `ide_create_file`:

```java
package io.casehub.neocortex.rag;

import java.time.Instant;
import java.util.*;

public final class RetrievalAnalyzer {

    private RetrievalAnalyzer() {}

    public static Map<String, DocumentStats> documentStats(
            RetrievalTracker tracker,
            CorpusRef corpus,
            Instant since, Instant until) {

        List<RetrievalRecord> records = tracker.findRecords(corpus, since, until);
        if (records.isEmpty()) {
            return Map.of();
        }

        // Widen feedback upper bound to capture late-submitted feedback
        List<RetrievalFeedback> allFeedback = tracker.findFeedback(corpus, since, Instant.MAX);

        // Collect retrievalIds from in-window records for post-filtering feedback
        Set<String> inWindowRetrievalIds = new HashSet<>();
        for (RetrievalRecord r : records) {
            inWindowRetrievalIds.add(r.retrievalId());
        }

        // Group feedback by sourceDocumentId, post-filtered to in-window retrievals
        Map<String, Map<RetrievalOutcome, Integer>> feedbackByDoc = new HashMap<>();
        for (RetrievalFeedback fb : allFeedback) {
            if (inWindowRetrievalIds.contains(fb.retrievalId())) {
                feedbackByDoc
                        .computeIfAbsent(fb.sourceDocumentId(), k -> new EnumMap<>(RetrievalOutcome.class))
                        .merge(fb.outcome(), 1, Integer::sum);
            }
        }

        // Aggregate per document
        Map<String, List<DocAppearance>> appearances = new HashMap<>();
        for (RetrievalRecord r : records) {
            for (RetrievedDocumentRef doc : r.documents()) {
                appearances.computeIfAbsent(doc.sourceDocumentId(), k -> new ArrayList<>())
                        .add(new DocAppearance(r.timestamp(), doc.relevanceScore()));
            }
        }

        Map<String, DocumentStats> result = new LinkedHashMap<>();
        for (var entry : appearances.entrySet()) {
            String docId = entry.getKey();
            List<DocAppearance> apps = entry.getValue();

            int count = apps.size();
            Instant first = apps.stream().map(DocAppearance::timestamp).min(Comparator.naturalOrder()).orElseThrow();
            Instant last = apps.stream().map(DocAppearance::timestamp).max(Comparator.naturalOrder()).orElseThrow();
            double avgScore = apps.stream().mapToDouble(DocAppearance::score).average().orElse(0.0);
            Map<RetrievalOutcome, Integer> dist = feedbackByDoc.getOrDefault(docId, Map.of());

            result.put(docId, new DocumentStats(docId, count, first, last, avgScore, dist));
        }

        return result;
    }

    private record DocAppearance(Instant timestamp, double score) {}
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalAnalyzerDocumentStatsTest`
Expected: All 9 tests PASS.

- [ ] **Step 5: Run ide_diagnostics to verify no compilation issues**

Run: `ide_diagnostics` on `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java`

- [ ] **Step 6: Commit**

```bash
git add rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java \
       rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerDocumentStatsTest.java
git commit -m "feat(#109): add RetrievalAnalyzer.documentStats() — per-document retrieval statistics"
```

---

### Task 3: RetrievalAnalyzer.unretrievedDocuments()

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerUnretrievedTest.java`

**Interfaces:**
- Consumes: `RetrievalTracker.findRetrievedDocumentIds(CorpusRef, Instant, Instant)` → `Set<String>`, `EmbeddingIngestor.listDocuments(CorpusRef)` → `List<String>`
- Produces: `RetrievalAnalyzer.unretrievedDocuments(RetrievalTracker tracker, EmbeddingIngestor ingestor, CorpusRef corpus, Instant since, Instant until)` → `Set<String>`

**Stub pattern for EmbeddingIngestor:** Only `listDocuments` needs implementation; other methods throw `UnsupportedOperationException`.

```java
private static EmbeddingIngestor stubIngestor(List<String> documents) {
    return new EmbeddingIngestor() {
        @Override public void ingest(CorpusRef c, List<ChunkInput> chunks) {
            throw new UnsupportedOperationException();
        }
        @Override public void deleteDocument(CorpusRef c, String docId) {
            throw new UnsupportedOperationException();
        }
        @Override public void deleteCorpus(CorpusRef c) {
            throw new UnsupportedOperationException();
        }
        @Override public List<String> listDocuments(CorpusRef c) {
            return documents;
        }
    };
}
```

**Stub pattern for RetrievalTracker in this task:** Only `findRetrievedDocumentIds` needs implementation.

```java
private static RetrievalTracker stubTrackerWithRetrievedIds(Set<String> ids) {
    return new RetrievalTracker() {
        // ... other methods throw UnsupportedOperationException ...
        @Override
        public Set<String> findRetrievedDocumentIds(CorpusRef c, Instant s, Instant u) {
            return ids;
        }
    };
}
```

- [ ] **Step 1: Write failing tests for unretrievedDocuments**

Create `RetrievalAnalyzerUnretrievedTest.java`:

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class RetrievalAnalyzerUnretrievedTest {

    private static final CorpusRef CORPUS = new CorpusRef("t1", "corpus1");
    private static final Instant SINCE = Instant.parse("2025-12-01T00:00:00Z");
    private static final Instant UNTIL = Instant.parse("2026-02-01T00:00:00Z");

    // --- stub helpers as shown above ---

    @Test
    void allDocumentsRetrieved_emptySet() {
        var tracker = stubTrackerWithRetrievedIds(Set.of("doc-A", "doc-B"));
        var ingestor = stubIngestor(List.of("doc-A", "doc-B"));

        var result = RetrievalAnalyzer.unretrievedDocuments(
                tracker, ingestor, CORPUS, SINCE, UNTIL);

        assertThat(result).isEmpty();
    }

    @Test
    void someNeverRetrieved_correctSetDifference() {
        var tracker = stubTrackerWithRetrievedIds(Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A", "doc-B", "doc-C"));

        var result = RetrievalAnalyzer.unretrievedDocuments(
                tracker, ingestor, CORPUS, SINCE, UNTIL);

        assertThat(result).containsExactlyInAnyOrder("doc-B", "doc-C");
    }

    @Test
    void emptyCorpus_emptySet() {
        var tracker = stubTrackerWithRetrievedIds(Set.of());
        var ingestor = stubIngestor(List.of());

        var result = RetrievalAnalyzer.unretrievedDocuments(
                tracker, ingestor, CORPUS, SINCE, UNTIL);

        assertThat(result).isEmpty();
    }

    @Test
    void emptyRetrievalHistory_allDocumentsReturned() {
        var tracker = stubTrackerWithRetrievedIds(Set.of());
        var ingestor = stubIngestor(List.of("doc-A", "doc-B"));

        var result = RetrievalAnalyzer.unretrievedDocuments(
                tracker, ingestor, CORPUS, SINCE, UNTIL);

        assertThat(result).containsExactlyInAnyOrder("doc-A", "doc-B");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalAnalyzerUnretrievedTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure — `unretrievedDocuments` method does not exist.

- [ ] **Step 3: Add unretrievedDocuments to RetrievalAnalyzer**

Use `ide_insert_member` on `RetrievalAnalyzer`, after `documentStats`:

```java
public static Set<String> unretrievedDocuments(
        RetrievalTracker tracker,
        EmbeddingIngestor ingestor,
        CorpusRef corpus,
        Instant since, Instant until) {

    Set<String> retrieved = tracker.findRetrievedDocumentIds(corpus, since, until);
    List<String> allDocuments = ingestor.listDocuments(corpus);

    Set<String> unretrieved = new LinkedHashSet<>();
    for (String docId : allDocuments) {
        if (!retrieved.contains(docId)) {
            unretrieved.add(docId);
        }
    }
    return unretrieved;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalAnalyzerUnretrievedTest`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java \
       rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerUnretrievedTest.java
git commit -m "feat(#109): add RetrievalAnalyzer.unretrievedDocuments() — zero-retrieval document identification"
```

---

### Task 4: RetrievalAnalyzer.qualitySignals()

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java`
- Test: `rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerQualitySignalsTest.java`

**Interfaces:**
- Consumes: `RetrievalAnalyzer.documentStats()` (from Task 2), `RetrievalAnalyzer.unretrievedDocuments()` (from Task 3), `QualityThresholds` (from Task 1), `DocumentQualitySignal` (from Task 1), `QualitySignal` (from Task 1)
- Produces: `RetrievalAnalyzer.qualitySignals(RetrievalTracker tracker, EmbeddingIngestor ingestor, CorpusRef corpus, Instant since, Instant until, QualityThresholds thresholds)` → `List<DocumentQualitySignal>`

**Stub pattern:** This task needs both `findRecords`/`findFeedback` (for documentStats internally) and `findRetrievedDocumentIds` (for unretrievedDocuments internally) and `listDocuments`. Build a combined stub that provides all four.

- [ ] **Step 1: Write failing tests for qualitySignals**

Create `RetrievalAnalyzerQualitySignalsTest.java`:

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class RetrievalAnalyzerQualitySignalsTest {

    private static final CorpusRef CORPUS = new CorpusRef("t1", "corpus1");
    private static final Instant SINCE = Instant.parse("2025-01-01T00:00:00Z");
    private static final Instant UNTIL = Instant.parse("2026-07-01T00:00:00Z");
    private static final QualityThresholds DEFAULTS = QualityThresholds.defaults();

    // Helper: build a full tracker stub that supports all four query methods
    // (findRecords, findFeedback, findRetrievedDocumentIds, and the others throw)

    private static RetrievedDocumentRef doc(String id, double score) {
        return new RetrievedDocumentRef(id, score);
    }

    private static RetrievalRecord record(String rid, Instant ts, RetrievedDocumentRef... docs) {
        return new RetrievalRecord(rid, RetrievalQuery.of("q"), CORPUS, List.of(docs), 10, ts);
    }

    // --- combined stubTracker and stubIngestor helpers ---

    @Test
    void neverRetrievedDocsFlagged() {
        // doc-B in corpus but never retrieved
        var tracker = combinedStub(
                List.of(record("r1", UNTIL.minusSeconds(3600), doc("doc-A", 0.9))),
                List.of(),
                Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A", "doc-B"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).signal()).isEqualTo(QualitySignal.NEVER_RETRIEVED);
        assertThat(result.get(0).sourceDocumentId()).isEqualTo("doc-B");
        assertThat(result.get(0).stats()).isNull();
    }

    @Test
    void highRetrievalLowQuality_whenRatioExceedsThreshold() {
        // doc-A retrieved 5 times, all feedback is NOT_RELEVANT
        Instant recent = UNTIL.minusSeconds(3600);
        var records = new ArrayList<RetrievalRecord>();
        var feedback = new ArrayList<RetrievalFeedback>();
        for (int i = 0; i < 5; i++) {
            String rid = "r" + i;
            records.add(record(rid, recent, doc("doc-A", 0.5)));
            feedback.add(new RetrievalFeedback(rid, "doc-A",
                    RetrievalOutcome.NOT_RELEVANT, recent));
        }
        var tracker = combinedStub(records, feedback, Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).signal()).isEqualTo(QualitySignal.HIGH_RETRIEVAL_LOW_QUALITY);
        assertThat(result.get(0).stats()).isNotNull();
        assertThat(result.get(0).stats().retrievalCount()).isEqualTo(5);
    }

    @Test
    void highRetrievalLowQuality_notFlaggedWhenBelowThreshold() {
        // 5 retrievals, 2 NOT_RELEVANT + 3 RELEVANT = 0.4 ratio, below 0.7 default
        Instant recent = UNTIL.minusSeconds(3600);
        var records = new ArrayList<RetrievalRecord>();
        var feedback = new ArrayList<RetrievalFeedback>();
        for (int i = 0; i < 5; i++) {
            String rid = "r" + i;
            records.add(record(rid, recent, doc("doc-A", 0.5)));
            feedback.add(new RetrievalFeedback(rid, "doc-A",
                    i < 2 ? RetrievalOutcome.NOT_RELEVANT : RetrievalOutcome.RELEVANT,
                    recent));
        }
        var tracker = combinedStub(records, feedback, Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).isEmpty();
    }

    @Test
    void belowMinRetrievals_notFlaggedEvenWithBadFeedback() {
        // Only 2 retrievals (below default min of 3), all NOT_RELEVANT
        Instant recent = UNTIL.minusSeconds(3600);
        var records = List.of(
                record("r1", recent, doc("doc-A", 0.5)),
                record("r2", recent, doc("doc-A", 0.5)));
        var feedback = List.of(
                new RetrievalFeedback("r1", "doc-A", RetrievalOutcome.NOT_RELEVANT, recent),
                new RetrievalFeedback("r2", "doc-A", RetrievalOutcome.NOT_RELEVANT, recent));
        var tracker = combinedStub(records, feedback, Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).isEmpty();
    }

    @Test
    void aboveMinRetrievalsZeroFeedback_notFlagged() {
        // 5 retrievals, zero feedback — quality check skipped (denominator zero)
        Instant recent = UNTIL.minusSeconds(3600);
        var records = new ArrayList<RetrievalRecord>();
        for (int i = 0; i < 5; i++) {
            records.add(record("r" + i, recent, doc("doc-A", 0.5)));
        }
        var tracker = combinedStub(records, List.of(), Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).isEmpty();
    }

    @Test
    void aboveMinRetrievals_feedbackBelowMinFeedback_notFlagged() {
        // 5 retrievals, only 2 feedback entries (below minFeedback=3) — sparse guard
        Instant recent = UNTIL.minusSeconds(3600);
        var records = new ArrayList<RetrievalRecord>();
        for (int i = 0; i < 5; i++) {
            records.add(record("r" + i, recent, doc("doc-A", 0.5)));
        }
        var feedback = List.of(
                new RetrievalFeedback("r0", "doc-A", RetrievalOutcome.NOT_RELEVANT, recent),
                new RetrievalFeedback("r1", "doc-A", RetrievalOutcome.NOT_RELEVANT, recent));
        var tracker = combinedStub(records, feedback, Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).isEmpty();
    }

    @Test
    void stale_whenLastRetrievalOutsideStaleWindow() {
        // Last retrieval 120 days ago, stale window is 90 days
        Instant old = UNTIL.minus(Duration.ofDays(120));
        var records = List.of(
                record("r1", old, doc("doc-A", 0.9)),
                record("r2", old, doc("doc-A", 0.8)),
                record("r3", old, doc("doc-A", 0.7)));
        var tracker = combinedStub(records, List.of(), Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).signal()).isEqualTo(QualitySignal.STALE);
    }

    @Test
    void multipleSignals_highestSeverityOnly() {
        // doc-A: stale AND low quality → only HIGH_RETRIEVAL_LOW_QUALITY emitted
        Instant old = UNTIL.minus(Duration.ofDays(120));
        var records = new ArrayList<RetrievalRecord>();
        var feedback = new ArrayList<RetrievalFeedback>();
        for (int i = 0; i < 5; i++) {
            String rid = "r" + i;
            records.add(record(rid, old, doc("doc-A", 0.5)));
            feedback.add(new RetrievalFeedback(rid, "doc-A",
                    RetrievalOutcome.NOT_RELEVANT, old));
        }
        var tracker = combinedStub(records, feedback, Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).signal()).isEqualTo(QualitySignal.HIGH_RETRIEVAL_LOW_QUALITY);
    }

    @Test
    void customThresholds_overrideDefaults() {
        // 3 retrievals, 2 NOT_RELEVANT feedback. Default ratio 0.7 → not flagged (0.67).
        // Custom ratio 0.5 → flagged.
        Instant recent = UNTIL.minusSeconds(3600);
        var records = new ArrayList<RetrievalRecord>();
        var feedback = new ArrayList<RetrievalFeedback>();
        for (int i = 0; i < 3; i++) {
            String rid = "r" + i;
            records.add(record(rid, recent, doc("doc-A", 0.5)));
            feedback.add(new RetrievalFeedback(rid, "doc-A",
                    i < 2 ? RetrievalOutcome.NOT_RELEVANT : RetrievalOutcome.RELEVANT,
                    recent));
        }
        var tracker = combinedStub(records, feedback, Set.of("doc-A"));
        var ingestor = stubIngestor(List.of("doc-A"));
        var thresholds = new QualityThresholds(3, 3, 0.5, Duration.ofDays(90));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, thresholds);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).signal()).isEqualTo(QualitySignal.HIGH_RETRIEVAL_LOW_QUALITY);
    }

    @Test
    void resultOrdering_neverRetrievedFirst_thenLowQuality_thenStale() {
        Instant recent = UNTIL.minusSeconds(3600);
        Instant old = UNTIL.minus(Duration.ofDays(120));

        // doc-A: NEVER_RETRIEVED (in corpus, never retrieved)
        // doc-B: HIGH_RETRIEVAL_LOW_QUALITY (5 retrievals, all bad feedback, recent)
        // doc-C: STALE (3 retrievals, all old)
        var records = new ArrayList<RetrievalRecord>();
        var feedback = new ArrayList<RetrievalFeedback>();
        for (int i = 0; i < 5; i++) {
            records.add(record("rb" + i, recent, doc("doc-B", 0.5)));
            feedback.add(new RetrievalFeedback("rb" + i, "doc-B",
                    RetrievalOutcome.NOT_RELEVANT, recent));
        }
        for (int i = 0; i < 3; i++) {
            records.add(record("rc" + i, old, doc("doc-C", 0.9)));
        }
        var tracker = combinedStub(records, feedback, Set.of("doc-B", "doc-C"));
        var ingestor = stubIngestor(List.of("doc-A", "doc-B", "doc-C"));

        var result = RetrievalAnalyzer.qualitySignals(
                tracker, ingestor, CORPUS, SINCE, UNTIL, DEFAULTS);

        assertThat(result).hasSize(3);
        assertThat(result.get(0).signal()).isEqualTo(QualitySignal.NEVER_RETRIEVED);
        assertThat(result.get(0).sourceDocumentId()).isEqualTo("doc-A");
        assertThat(result.get(1).signal()).isEqualTo(QualitySignal.HIGH_RETRIEVAL_LOW_QUALITY);
        assertThat(result.get(1).sourceDocumentId()).isEqualTo("doc-B");
        assertThat(result.get(2).signal()).isEqualTo(QualitySignal.STALE);
        assertThat(result.get(2).sourceDocumentId()).isEqualTo("doc-C");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalAnalyzerQualitySignalsTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation failure — `qualitySignals` method does not exist.

- [ ] **Step 3: Add qualitySignals to RetrievalAnalyzer**

Use `ide_insert_member` on `RetrievalAnalyzer`, after `unretrievedDocuments`:

```java
public static List<DocumentQualitySignal> qualitySignals(
        RetrievalTracker tracker,
        EmbeddingIngestor ingestor,
        CorpusRef corpus,
        Instant since, Instant until,
        QualityThresholds thresholds) {

    Map<String, DocumentStats> stats = documentStats(tracker, corpus, since, until);
    Set<String> unretrieved = unretrievedDocuments(tracker, ingestor, corpus, since, until);

    List<DocumentQualitySignal> neverRetrievedSignals = new ArrayList<>();
    List<DocumentQualitySignal> lowQualitySignals = new ArrayList<>();
    List<DocumentQualitySignal> staleSignals = new ArrayList<>();

    // NEVER_RETRIEVED
    for (String docId : unretrieved) {
        neverRetrievedSignals.add(
                new DocumentQualitySignal(docId, null, QualitySignal.NEVER_RETRIEVED));
    }

    Instant staleCutoff = until.minus(thresholds.staleWindow());

    for (var entry : stats.entrySet()) {
        String docId = entry.getKey();
        DocumentStats ds = entry.getValue();

        // HIGH_RETRIEVAL_LOW_QUALITY check
        if (ds.retrievalCount() >= thresholds.minRetrievalsForQualityCheck()) {
            int totalFeedback = ds.feedbackDistribution().values().stream()
                    .mapToInt(Integer::intValue).sum();
            if (totalFeedback >= thresholds.minFeedbackForQualityCheck()) {
                int lowCount = ds.feedbackDistribution()
                        .getOrDefault(RetrievalOutcome.NOT_RELEVANT, 0)
                        + ds.feedbackDistribution()
                        .getOrDefault(RetrievalOutcome.PARTIALLY_RELEVANT, 0);
                double ratio = (double) lowCount / totalFeedback;
                if (ratio >= thresholds.lowQualityRatio()) {
                    lowQualitySignals.add(
                            new DocumentQualitySignal(docId, ds,
                                    QualitySignal.HIGH_RETRIEVAL_LOW_QUALITY));
                    continue; // highest severity wins — skip STALE check
                }
            }
        }

        // STALE check (only if not already flagged as low quality)
        if (ds.lastRetrieved().isBefore(staleCutoff)) {
            staleSignals.add(
                    new DocumentQualitySignal(docId, ds, QualitySignal.STALE));
        }
    }

    // Combine in severity order
    List<DocumentQualitySignal> result = new ArrayList<>(
            neverRetrievedSignals.size() + lowQualitySignals.size() + staleSignals.size());
    result.addAll(neverRetrievedSignals);
    result.addAll(lowQualitySignals);
    result.addAll(staleSignals);
    return result;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalAnalyzerQualitySignalsTest`
Expected: All 11 tests PASS.

- [ ] **Step 5: Run full rag-api test suite to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api`
Expected: All existing tests + all new tests PASS.

- [ ] **Step 6: Commit**

```bash
git add rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java \
       rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerQualitySignalsTest.java
git commit -m "feat(#109): add RetrievalAnalyzer.qualitySignals() — quality signal classification with caller-controlled thresholds"
```

- [ ] **Step 7: Run full project build to verify no cross-module breakage**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Then: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api`
Expected: Build succeeds. All rag-api tests pass.
