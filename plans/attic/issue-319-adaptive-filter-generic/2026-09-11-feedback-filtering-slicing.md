# Feedback Filtering and Analyzer Slicing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #317 — findFeedback() context-based filtering overload
**Issue group:** #317, #318

**Goal:** Add `FeedbackFilter` for SQL-level feedback querying, and context-aware overloads on `RetrievalAnalyzer.documentStats()` and `qualitySignals()`.

**Architecture:** New `FeedbackFilter` record in rag-api mirroring `FeedbackContext`. Default method on `RetrievalTracker` with post-filter fallback. `SqliteRetrievalTracker` overrides with SQL WHERE clauses + `json_extract`. `RetrievalAnalyzer` gains filtered overloads that delegate to the new `findFeedback`.

**Tech Stack:** Java 21, Quarkus 3.32.2, SQLite, Jackson

## Global Constraints

- Java 21 source level, Java 26 JVM
- `FeedbackFilter` in `io.casehub.neocortex.rag` package (rag-api, zero deps)
- No `@Nullable` annotations in rag-api (zero-dep constraint)
- Contract tests in `rag-testing/src/main` (shared test base)
- `json_extract` for attribute filtering in SQLite (unindexed — acceptable at current scale)

---

## Batch 1: FeedbackFilter + SPI overload + contract tests

### Task 1: FeedbackFilter and RetrievalTracker filtered findFeedback

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackFilter.java`
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java`
- Modify: `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/RetrievalTrackerContractTest.java`

**Interfaces:**
- Produces: `FeedbackFilter` record — `NONE` constant, `byIssue(String, int)` factory, `matches(RetrievalFeedback, FeedbackFilter)` static method
- Produces: `RetrievalTracker.findFeedback(CorpusRef, Instant, Instant, FeedbackFilter)` — default method with post-filter fallback

- [ ] **Step 1: Write failing contract tests**

Add 4 new tests to `RetrievalTrackerContractTest` in the `// --- feedback context ---` section:

```java
@Test
void findFeedback_filterByIssue() {
    String id1 = tracker().record(RetrievalQuery.of("q1"), CORPUS, chunks("d1"), 10);
    String id2 = tracker().record(RetrievalQuery.of("q2"), CORPUS, chunks("d2"), 10);
    tracker().feedback(id1, "d1", RetrievalOutcome.RELEVANT,
        FeedbackContext.ofIssue("repo-a", 1));
    tracker().feedback(id2, "d2", RetrievalOutcome.RELEVANT,
        FeedbackContext.ofIssue("repo-b", 2));
    var filtered = tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX,
        FeedbackFilter.byIssue("repo-a", 1));
    assertThat(filtered).hasSize(1);
    assertThat(filtered.getFirst().sourceDocumentId()).isEqualTo("d1");
}

@Test
void findFeedback_filterByAttributes() {
    String id1 = tracker().record(RetrievalQuery.of("q1"), CORPUS, chunks("d1"), 10);
    String id2 = tracker().record(RetrievalQuery.of("q2"), CORPUS, chunks("d2"), 10);
    tracker().feedback(id1, "d1", RetrievalOutcome.RELEVANT,
        new FeedbackContext(null, null, Map.of(FeedbackAttributeKeys.AGENT_ID, "agent-1")));
    tracker().feedback(id2, "d2", RetrievalOutcome.RELEVANT,
        new FeedbackContext(null, null, Map.of(FeedbackAttributeKeys.AGENT_ID, "agent-2")));
    var filtered = tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX,
        new FeedbackFilter(null, null, Map.of(FeedbackAttributeKeys.AGENT_ID, "agent-1")));
    assertThat(filtered).hasSize(1);
    assertThat(filtered.getFirst().sourceDocumentId()).isEqualTo("d1");
}

@Test
void findFeedback_filterNoneReturnsAll() {
    String id = tracker().record(RetrievalQuery.of("q"), CORPUS, chunks("d1", "d2"), 10);
    tracker().feedback(id, "d1", RetrievalOutcome.RELEVANT,
        FeedbackContext.ofIssue("repo-a", 1));
    tracker().feedback(id, "d2", RetrievalOutcome.RELEVANT);
    var filtered = tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX,
        FeedbackFilter.NONE);
    assertThat(filtered).hasSize(2);
}

@Test
void findFeedback_nullContextExcludedByFilter() {
    String id = tracker().record(RetrievalQuery.of("q"), CORPUS, chunks("d1", "d2"), 10);
    tracker().feedback(id, "d1", RetrievalOutcome.RELEVANT,
        FeedbackContext.ofIssue("repo-a", 1));
    tracker().feedback(id, "d2", RetrievalOutcome.RELEVANT);
    var filtered = tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX,
        FeedbackFilter.byIssue("repo-a", 1));
    assertThat(filtered).hasSize(1);
    assertThat(filtered.getFirst().sourceDocumentId()).isEqualTo("d1");
}
```

Add import for `FeedbackFilter` to the test file.

- [ ] **Step 2: Create FeedbackFilter record**

Create `rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackFilter.java`:

```java
package io.casehub.neocortex.rag;

import java.util.Map;
import java.util.Objects;

public record FeedbackFilter(
    String issueRepo,
    Integer issueNumber,
    Map<String, String> attributes
) {
    public static final FeedbackFilter NONE = new FeedbackFilter(null, null, Map.of());

    public FeedbackFilter {
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }

    public static FeedbackFilter byIssue(String issueRepo, int issueNumber) {
        return new FeedbackFilter(issueRepo, issueNumber, Map.of());
    }

    public static boolean matches(RetrievalFeedback feedback, FeedbackFilter filter) {
        if (filter == null || NONE.equals(filter)) return true;
        FeedbackContext ctx = feedback.context();
        if (ctx == null) return false;
        if (filter.issueRepo() != null && !filter.issueRepo().equals(ctx.issueRepo())) return false;
        if (filter.issueNumber() != null && !filter.issueNumber().equals(ctx.issueNumber())) return false;
        for (var entry : filter.attributes().entrySet()) {
            if (!Objects.equals(entry.getValue(), ctx.attributes().get(entry.getKey()))) return false;
        }
        return true;
    }
}
```

- [ ] **Step 3: Add default findFeedback overload to RetrievalTracker**

Add to `RetrievalTracker.java` after the existing `findFeedback` method:

```java
default List<RetrievalFeedback> findFeedback(CorpusRef corpus, Instant since,
                                              Instant until, FeedbackFilter filter) {
    if (filter == null || FeedbackFilter.NONE.equals(filter)) {
        return findFeedback(corpus, since, until);
    }
    return findFeedback(corpus, since, until).stream()
        .filter(f -> FeedbackFilter.matches(f, filter))
        .toList();
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl rag-api,rag-testing`

Expected: all tests pass including 4 new filter contract tests via `InMemoryRetrievalTrackerTest`.

- [ ] **Step 5: Commit**

```
git add rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackFilter.java \
       rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java \
       rag-testing/src/main/java/io/casehub/neocortex/rag/testing/RetrievalTrackerContractTest.java
```

Message: `feat(rag-api): add FeedbackFilter and filtered findFeedback default method  Refs #317`

## Batch 2: SqliteRetrievalTracker SQL-level filtering

### Task 2: SqliteRetrievalTracker findFeedback override with SQL filtering

**Files:**
- Modify: `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java`

**Interfaces:**
- Consumes: `FeedbackFilter` — `issueRepo()`, `issueNumber()`, `attributes()` accessors
- Consumes: `FeedbackFilter.NONE` — for short-circuit check

- [ ] **Step 1: Add filtered findFeedback override to SqliteRetrievalTracker**

Add a new method overriding the default, after the existing `findFeedback` method. It builds on the same SQL pattern but appends WHERE clauses dynamically:

```java
@Override
public List<RetrievalFeedback> findFeedback(CorpusRef corpus,
                                             Instant since, Instant until,
                                             FeedbackFilter filter) {
    if (filter == null || FeedbackFilter.NONE.equals(filter)) {
        return findFeedback(corpus, since, until);
    }

    var sql = new StringBuilder("SELECT f.retrieval_id, f.source_document_id, f.outcome, f.timestamp, f.issue_repo, f.issue_number, f.attributes FROM retrieval_feedback f JOIN retrieval_records r ON f.retrieval_id = r.retrieval_id WHERE r.tenant_id = ? AND r.corpus_name = ?");
    boolean hasSince = hasSinceFilter(since);
    boolean hasUntil = hasUntilFilter(until);
    if (hasSince) sql.append(" AND f.timestamp >= ?");
    if (hasUntil) sql.append(" AND f.timestamp < ?");

    if (filter.issueRepo() != null) sql.append(" AND f.issue_repo = ?");
    if (filter.issueNumber() != null) sql.append(" AND f.issue_number = ?");
    for (var entry : filter.attributes().entrySet()) {
        sql.append(" AND json_extract(f.attributes, ?) = ?");
    }

    try (Connection conn = dataSource.getConnection();
         PreparedStatement ps = conn.prepareStatement(sql.toString())) {
        int idx = 1;
        ps.setString(idx++, corpus.tenantId());
        ps.setString(idx++, corpus.corpusName());
        if (hasSince) ps.setString(idx++, toIso(since));
        if (hasUntil) ps.setString(idx++, toIso(until));

        if (filter.issueRepo() != null) ps.setString(idx++, filter.issueRepo());
        if (filter.issueNumber() != null) ps.setInt(idx++, filter.issueNumber());
        for (var entry : filter.attributes().entrySet()) {
            ps.setString(idx++, "$." + entry.getKey());
            ps.setString(idx++, entry.getValue());
        }

        List<RetrievalFeedback> feedbacks = new ArrayList<>();
        try (ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                feedbacks.add(new RetrievalFeedback(
                    rs.getString("retrieval_id"),
                    rs.getString("source_document_id"),
                    RetrievalOutcome.valueOf(rs.getString("outcome")),
                    fromIso(rs.getString("timestamp")),
                    readContext(rs)
                ));
            }
        }
        return List.copyOf(feedbacks);
    } catch (SQLException e) {
        throw new IllegalStateException("findFeedback(filter) failed", e);
    }
}
```

Add import for `FeedbackFilter`.

- [ ] **Step 2: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl rag-api,rag-testing,rag-tracking`

Expected: all tests pass — `SqliteRetrievalTrackerTest` inherits the 4 new contract tests and exercises the SQL override.

- [ ] **Step 3: Commit**

```
git add rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java
```

Message: `feat(rag-tracking): SQL-level FeedbackFilter in findFeedback — indexed + json_extract  Refs #317`

## Batch 3: RetrievalAnalyzer context-aware overloads

### Task 3: RetrievalAnalyzer filtered documentStats and qualitySignals

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java`
- Modify: `rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerDocumentStatsTest.java`
- Modify: `rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerQualitySignalsTest.java`

**Interfaces:**
- Consumes: `FeedbackFilter` — passed to `tracker.findFeedback(corpus, since, Instant.MAX, filter)`
- Consumes: `RetrievalTracker.findFeedback(CorpusRef, Instant, Instant, FeedbackFilter)` — filtered query

- [ ] **Step 1: Write failing test for filtered documentStats**

Add to `RetrievalAnalyzerDocumentStatsTest.java`:

```java
@Test
void documentStats_filteredByIssue() {
    var records = List.of(
        new RetrievalRecord("r1", RetrievalQuery.of("q"), CORPUS,
            List.of(new RetrievedDocumentRef("doc-A", 0.9)), 10, T1));
    var feedback = List.of(
        new RetrievalFeedback("r1", "doc-A", RetrievalOutcome.RELEVANT, T2,
            FeedbackContext.ofIssue("repo-a", 1)),
        new RetrievalFeedback("r1", "doc-A", RetrievalOutcome.NOT_RELEVANT, T2,
            FeedbackContext.ofIssue("repo-b", 2)));

    var tracker = stubTracker(records, feedback);
    var stats = RetrievalAnalyzer.documentStats(tracker, CORPUS, SINCE, UNTIL,
        FeedbackFilter.byIssue("repo-a", 1));

    assertThat(stats).containsKey("doc-A");
    assertThat(stats.get("doc-A").feedbackDistribution())
        .containsEntry(RetrievalOutcome.RELEVANT, 1)
        .doesNotContainKey(RetrievalOutcome.NOT_RELEVANT);
}
```

Add imports for `FeedbackContext`, `FeedbackFilter`.

- [ ] **Step 2: Write failing test for filtered qualitySignals**

Add to `RetrievalAnalyzerQualitySignalsTest.java`:

```java
@Test
void qualitySignals_filteredByIssue() {
    var records = new ArrayList<RetrievalRecord>();
    var feedback = new ArrayList<RetrievalFeedback>();
    Instant recent = Instant.now().minusSeconds(60);

    for (int i = 0; i < 5; i++) {
        String rid = "r" + i;
        records.add(new RetrievalRecord(rid, RetrievalQuery.of("q"), CORPUS,
            List.of(new RetrievedDocumentRef("doc-A", 0.9)), 10, recent));
        feedback.add(new RetrievalFeedback(rid, "doc-A",
            RetrievalOutcome.NOT_RELEVANT, recent,
            FeedbackContext.ofIssue("repo-bad", 1)));
    }
    // Add good feedback from a different issue
    feedback.add(new RetrievalFeedback("r0", "doc-A",
        RetrievalOutcome.HIGHLY_RELEVANT, recent,
        FeedbackContext.ofIssue("repo-good", 2)));

    var tracker = stubTracker(records, feedback);

    // Unfiltered: doc-A has mixed feedback — may or may not trigger LOW_QUALITY
    // Filtered to repo-bad: all NOT_RELEVANT — should trigger LOW_QUALITY
    var signals = RetrievalAnalyzer.qualitySignals(tracker, ingestor, CORPUS,
        SINCE, UNTIL, THRESHOLDS, FeedbackFilter.byIssue("repo-bad", 1));

    assertThat(signals).anyMatch(s ->
        s.documentId().equals("doc-A") && s.signal() == QualitySignal.HIGH_RETRIEVAL_LOW_QUALITY);
}
```

Add imports for `FeedbackContext`, `FeedbackFilter`.

- [ ] **Step 3: Implement filtered documentStats overload**

Add to `RetrievalAnalyzer.java` after the existing `documentStats` method. Refactor the existing method to delegate:

```java
public static Map<String, DocumentStats> documentStats(
        RetrievalTracker tracker,
        CorpusRef corpus,
        Instant since, Instant until,
        FeedbackFilter filter) {

    List<RetrievalRecord> records = tracker.findRecords(corpus, since, until);
    if (records.isEmpty()) {
        return Map.of();
    }

    List<RetrievalFeedback> allFeedback = tracker.findFeedback(corpus, since, Instant.MAX, filter);

    Set<String> inWindowRetrievalIds = new HashSet<>();
    for (RetrievalRecord r : records) {
        inWindowRetrievalIds.add(r.retrievalId());
    }

    Map<String, Map<RetrievalOutcome, Integer>> feedbackByDoc = new HashMap<>();
    for (RetrievalFeedback fb : allFeedback) {
        if (inWindowRetrievalIds.contains(fb.retrievalId())) {
            feedbackByDoc
                    .computeIfAbsent(fb.sourceDocumentId(), k -> new EnumMap<>(RetrievalOutcome.class))
                    .merge(fb.outcome(), 1, Integer::sum);
        }
    }

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
```

Then change the existing 4-arg `documentStats` to delegate:

```java
public static Map<String, DocumentStats> documentStats(
        RetrievalTracker tracker,
        CorpusRef corpus,
        Instant since, Instant until) {
    return documentStats(tracker, corpus, since, until, FeedbackFilter.NONE);
}
```

- [ ] **Step 4: Implement filtered qualitySignals overload**

Add to `RetrievalAnalyzer.java` after the existing `qualitySignals` method:

```java
public static List<DocumentQualitySignal> qualitySignals(
        RetrievalTracker tracker,
        EmbeddingIngestor ingestor,
        CorpusRef corpus,
        Instant since, Instant until,
        QualityThresholds thresholds,
        FeedbackFilter filter) {

    Map<String, DocumentStats> stats       = documentStats(tracker, corpus, since, until, filter);
    Set<String>                unretrieved = unretrievedDocuments(tracker, ingestor, corpus, since, until);

    List<DocumentQualitySignal> neverRetrievedSignals = new ArrayList<>();
    List<DocumentQualitySignal> lowQualitySignals     = new ArrayList<>();
    List<DocumentQualitySignal> staleSignals          = new ArrayList<>();

    for (String docId : unretrieved) {
        neverRetrievedSignals.add(
                new DocumentQualitySignal(docId, null, QualitySignal.NEVER_RETRIEVED));
    }

    Instant staleCutoff = until.minus(thresholds.staleWindow());

    for (var entry : stats.entrySet()) {
        String        docId = entry.getKey();
        DocumentStats ds    = entry.getValue();

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
                    continue;
                }
            }
        }

        if (ds.lastRetrieved().isBefore(staleCutoff)) {
            staleSignals.add(
                    new DocumentQualitySignal(docId, ds, QualitySignal.STALE));
        }
    }

    List<DocumentQualitySignal> result = new ArrayList<>(
            neverRetrievedSignals.size() + lowQualitySignals.size() + staleSignals.size());
    result.addAll(neverRetrievedSignals);
    result.addAll(lowQualitySignals);
    result.addAll(staleSignals);
    return result;
}
```

Then change the existing 6-arg `qualitySignals` to delegate:

```java
public static List<DocumentQualitySignal> qualitySignals(
        RetrievalTracker tracker,
        EmbeddingIngestor ingestor,
        CorpusRef corpus,
        Instant since, Instant until,
        QualityThresholds thresholds) {
    return qualitySignals(tracker, ingestor, corpus, since, until, thresholds, FeedbackFilter.NONE);
}
```

- [ ] **Step 5: Fix stub trackers in test files**

The stub trackers in `RetrievalAnalyzerDocumentStatsTest` and `RetrievalAnalyzerQualitySignalsTest` implement `RetrievalTracker`. The default `findFeedback(filter)` method on the interface handles filtering — no stub changes needed unless the stub overrides `findFeedback`. Verify compilation.

- [ ] **Step 6: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl rag-api,rag-testing,rag-tracking`

Expected: all tests pass — existing behavior unchanged (delegation to NONE), new filtered tests pass.

- [ ] **Step 7: Commit**

```
git add rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java \
       rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerDocumentStatsTest.java \
       rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerQualitySignalsTest.java
```

Message: `feat(rag-api): context-aware documentStats and qualitySignals overloads  Closes #318, Refs #317`

## References

- specs/issue-317-feedback-filtering-slicing/2026-09-11-feedback-filtering-slicing-design.md — design spec
- rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java — SPI gaining overload
- rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java:23-72 — documentStats
- rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java:92-147 — qualitySignals
- rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackContext.java — context type
- rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java — SQL override
- memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java:326 — json_extract pattern
- GitHub #317, #318
