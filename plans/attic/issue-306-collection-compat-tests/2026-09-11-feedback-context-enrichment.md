# Feedback Context Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #305 — Feedback context — enrich RetrievalTracker.feedback() with issue/project correlation
**Issue group:** #305

**Goal:** Add `FeedbackContext` to the retrieval feedback pipeline so callers can attach issue/project/agent context to feedback submissions.

**Architecture:** New `FeedbackContext` record and `FeedbackAttributeKeys` constants in `rag-api`. Default method bridge on `RetrievalTracker` for backward compat. `RetrievalFeedback` gains a nullable context field. SQLite V2 migration adds context columns. InMemory impl gets context for free via the record change.

**Tech Stack:** Java 21, Quarkus 3.32.2, SQLite, Jackson (quarkus-jackson), Flyway

## Global Constraints

- Java 21 source level, Java 26 JVM
- All new types in `io.casehub.neocortex.rag` package (rag-api module)
- Follow existing naming conventions: kebab-case attribute keys, `@Nullable` annotation from `jakarta.annotation`
- `quarkus-jackson` dependency added to `rag-tracking` for JSON serialization of attributes map
- Contract tests in `rag-testing` (src/main, not src/test — shared test base)

---

## Batch 1: API types + SPI evolution + contract tests

### Task 1: FeedbackContext, FeedbackAttributeKeys, and RetrievalFeedback evolution

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackContext.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackAttributeKeys.java`
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalFeedback.java`
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java`
- Modify: `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/InMemoryRetrievalTracker.java`
- Modify: `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/RetrievalTrackerContractTest.java`

**Interfaces:**
- Produces: `FeedbackContext` record — `ofIssue(String issueRepo, int issueNumber)` factory, `EMPTY` constant, `issueRepo()`, `issueNumber()`, `attributes()` accessors
- Produces: `FeedbackAttributeKeys` — `AGENT_ID`, `SESSION_ID`, `WORK_PHASE` constants
- Produces: `RetrievalTracker.feedback(String, String, RetrievalOutcome, FeedbackContext)` — new primary method
- Produces: `RetrievalFeedback.context()` — nullable `FeedbackContext` accessor

- [ ] **Step 1: Write failing contract tests**

Add 4 new tests to `RetrievalTrackerContractTest`:

```java
// --- feedback context ---

@Test
void feedback_storesContext() {
    String id = tracker().record(RetrievalQuery.of("q"), CORPUS, chunks("d1"), 10);
    var ctx = FeedbackContext.ofIssue("casehubio/neocortex", 305);
    tracker().feedback(id, "d1", RetrievalOutcome.RELEVANT, ctx);
    var fb = tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX);
    assertThat(fb).hasSize(1);
    assertThat(fb.getFirst().context()).isNotNull();
    assertThat(fb.getFirst().context().issueRepo()).isEqualTo("casehubio/neocortex");
    assertThat(fb.getFirst().context().issueNumber()).isEqualTo(305);
}

@Test
void feedback_nullContext() {
    String id = tracker().record(RetrievalQuery.of("q"), CORPUS, chunks("d1"), 10);
    tracker().feedback(id, "d1", RetrievalOutcome.RELEVANT);
    var fb = tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX);
    assertThat(fb).hasSize(1);
    assertThat(fb.getFirst().context()).isNull();
}

@Test
void feedback_upsertPreservesLatestContext() {
    String id = tracker().record(RetrievalQuery.of("q"), CORPUS, chunks("d1"), 10);
    var ctx1 = FeedbackContext.ofIssue("repo-a", 1);
    var ctx2 = FeedbackContext.ofIssue("repo-b", 2);
    tracker().feedback(id, "d1", RetrievalOutcome.NOT_RELEVANT, ctx1);
    tracker().feedback(id, "d1", RetrievalOutcome.RELEVANT, ctx2);
    var fb = tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX);
    assertThat(fb).hasSize(1);
    assertThat(fb.getFirst().outcome()).isEqualTo(RetrievalOutcome.RELEVANT);
    assertThat(fb.getFirst().context().issueRepo()).isEqualTo("repo-b");
    assertThat(fb.getFirst().context().issueNumber()).isEqualTo(2);
}

@Test
void feedback_attributesRoundTrip() {
    String id = tracker().record(RetrievalQuery.of("q"), CORPUS, chunks("d1"), 10);
    var ctx = new FeedbackContext(null, null,
        Map.of(FeedbackAttributeKeys.AGENT_ID, "agent-1",
               FeedbackAttributeKeys.SESSION_ID, "sess-42"));
    tracker().feedback(id, "d1", RetrievalOutcome.RELEVANT, ctx);
    var fb = tracker().findFeedback(CORPUS, Instant.EPOCH, Instant.MAX);
    assertThat(fb.getFirst().context()).isNotNull();
    assertThat(fb.getFirst().context().issueRepo()).isNull();
    assertThat(fb.getFirst().context().attributes())
        .containsEntry(FeedbackAttributeKeys.AGENT_ID, "agent-1")
        .containsEntry(FeedbackAttributeKeys.SESSION_ID, "sess-42");
}
```

- [ ] **Step 2: Create FeedbackContext record**

Create `rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackContext.java`:

```java
package io.casehub.neocortex.rag;

import jakarta.annotation.Nullable;
import java.util.Map;

public record FeedbackContext(
    @Nullable String issueRepo,
    @Nullable Integer issueNumber,
    Map<String, String> attributes
) {
    public static final FeedbackContext EMPTY = new FeedbackContext(null, null, Map.of());

    public FeedbackContext {
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }

    public static FeedbackContext ofIssue(String issueRepo, int issueNumber) {
        return new FeedbackContext(issueRepo, issueNumber, Map.of());
    }
}
```

- [ ] **Step 3: Create FeedbackAttributeKeys**

Create `rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackAttributeKeys.java`:

```java
package io.casehub.neocortex.rag;

public final class FeedbackAttributeKeys {

    public static final String AGENT_ID = "agent-id";
    public static final String SESSION_ID = "session-id";
    public static final String WORK_PHASE = "work-phase";

    private FeedbackAttributeKeys() {}
}
```

- [ ] **Step 4: Evolve RetrievalFeedback**

Change `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalFeedback.java` — add nullable `FeedbackContext context` as the 5th field:

```java
package io.casehub.neocortex.rag;

import jakarta.annotation.Nullable;
import java.time.Instant;

public record RetrievalFeedback(
    String retrievalId,
    String sourceDocumentId,
    RetrievalOutcome outcome,
    Instant timestamp,
    @Nullable FeedbackContext context
) {
    public RetrievalFeedback {
        if (retrievalId == null || retrievalId.isBlank())
            throw new IllegalArgumentException("retrievalId must not be null or blank");
        if (sourceDocumentId == null || sourceDocumentId.isBlank())
            throw new IllegalArgumentException("sourceDocumentId must not be null or blank");
        if (outcome == null)
            throw new IllegalArgumentException("outcome must not be null");
        if (timestamp == null)
            throw new IllegalArgumentException("timestamp must not be null");
    }
}
```

- [ ] **Step 5: Evolve RetrievalTracker SPI**

Change `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java` — add 4-param feedback as new primary, make old 3-param a default bridge:

```java
package io.casehub.neocortex.rag;

import jakarta.annotation.Nullable;
import java.time.Instant;
import java.util.List;
import java.util.Set;

public interface RetrievalTracker {

    String record(RetrievalQuery query, CorpusRef corpus,
                  List<RetrievedChunk> results, int maxResults);

    void feedback(String retrievalId, String sourceDocumentId,
                  RetrievalOutcome outcome, @Nullable FeedbackContext context);

    default void feedback(String retrievalId, String sourceDocumentId,
                          RetrievalOutcome outcome) {
        feedback(retrievalId, sourceDocumentId, outcome, null);
    }

    List<RetrievalRecord> findRecords(CorpusRef corpus, Instant since, Instant until);

    List<RetrievalFeedback> findFeedback(CorpusRef corpus, Instant since, Instant until);

    Set<String> findRetrievedDocumentIds(CorpusRef corpus, Instant since, Instant until);

    int purgeOlderThan(Instant cutoff);
}
```

- [ ] **Step 6: Fix InMemoryRetrievalTracker compilation**

Update `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/InMemoryRetrievalTracker.java`:

Change the `feedback` method signature (lines 48-54) to accept `FeedbackContext`:

```java
@Override
public void feedback(String retrievalId, String sourceDocumentId,
                     RetrievalOutcome outcome, @Nullable FeedbackContext context) {
    final String key = retrievalId + "\0" + sourceDocumentId;
    feedbackIndex.put(key, new RetrievalFeedback(
        retrievalId, sourceDocumentId, outcome, Instant.now(), context));
}
```

Add import for `FeedbackContext` and `jakarta.annotation.Nullable`.

Also fix the existing `RetrievalFeedback` 4-arg constructor call: since the record now has 5 fields, any other place constructing `RetrievalFeedback` in `InMemoryRetrievalTracker` must pass `null` as the 5th argument. There are no other construction sites — only this one in `feedback()`.

- [ ] **Step 7: Fix existing contract tests — RetrievalFeedback construction sites**

The existing contract tests call `tracker().feedback(id, docId, outcome)` which routes through the default bridge → `feedback(id, docId, outcome, null)`. No test code changes needed for existing tests — they use the SPI method, not the constructor directly.

Verify: run the contract test suite.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api,rag-testing`

Expected: compilation succeeds, `InMemoryRetrievalTrackerTest` passes (all existing + 4 new contract tests).

- [ ] **Step 8: Commit**

```
git add rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackContext.java \
       rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackAttributeKeys.java \
       rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalFeedback.java \
       rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java \
       rag-testing/src/main/java/io/casehub/neocortex/rag/testing/InMemoryRetrievalTracker.java \
       rag-testing/src/main/java/io/casehub/neocortex/rag/testing/RetrievalTrackerContractTest.java
```

Message: `feat(rag-api): add FeedbackContext to RetrievalTracker.feedback() SPI  Refs #305`

## Batch 2: SQLite implementation

### Task 2: SqliteRetrievalTracker context persistence

**Files:**
- Modify: `rag-tracking/pom.xml`
- Create: `rag-tracking/src/main/resources/db/rag-tracking/migration/V2__feedback_context.sql`
- Modify: `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java`

**Interfaces:**
- Consumes: `FeedbackContext` record — `issueRepo()`, `issueNumber()`, `attributes()` accessors
- Consumes: `RetrievalFeedback(String, String, RetrievalOutcome, Instant, FeedbackContext)` — 5-arg constructor
- Consumes: `RetrievalTracker.feedback(String, String, RetrievalOutcome, FeedbackContext)` — 4-param method to override

- [ ] **Step 1: Add quarkus-jackson dependency to rag-tracking**

Add to `rag-tracking/pom.xml` in the `<dependencies>` section, after the `quarkus-arc` dependency:

```xml
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-jackson</artifactId>
</dependency>
```

- [ ] **Step 2: Create V2 Flyway migration**

Create `rag-tracking/src/main/resources/db/rag-tracking/migration/V2__feedback_context.sql`:

```sql
ALTER TABLE retrieval_feedback ADD COLUMN issue_repo TEXT;
ALTER TABLE retrieval_feedback ADD COLUMN issue_number INTEGER;
ALTER TABLE retrieval_feedback ADD COLUMN attributes TEXT;

CREATE INDEX idx_feedback_issue ON retrieval_feedback(issue_repo, issue_number);
```

- [ ] **Step 3: Update SqliteRetrievalTracker — add ObjectMapper and JSON helpers**

Add field and imports to `SqliteRetrievalTracker`:

```java
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.casehub.neocortex.rag.FeedbackContext;
import jakarta.annotation.Nullable;
import jakarta.inject.Inject;
```

Add field:

```java
@Inject
ObjectMapper objectMapper;
```

Add private helpers at the bottom (before the existing `hasSinceFilter` helper):

```java
private String toJson(Map<String, String> attrs) {
    if (attrs == null || attrs.isEmpty()) return null;
    try {
        return objectMapper.writeValueAsString(attrs);
    } catch (JsonProcessingException e) {
        throw new IllegalStateException("Failed to serialize attributes", e);
    }
}

private Map<String, String> fromJson(String json) {
    if (json == null || json.isBlank()) return Map.of();
    try {
        return objectMapper.readValue(json, new TypeReference<Map<String, String>>() {});
    } catch (JsonProcessingException e) {
        throw new IllegalStateException("Failed to deserialize attributes: " + json, e);
    }
}

private @Nullable FeedbackContext readContext(ResultSet rs) throws SQLException {
    String issueRepo = rs.getString("issue_repo");
    String issueNumberStr = rs.getString("issue_number");
    String attributesJson = rs.getString("attributes");
    if (issueRepo == null && issueNumberStr == null && attributesJson == null) {
        return null;
    }
    Integer issueNumber = issueNumberStr != null ? Integer.parseInt(issueNumberStr) : null;
    return new FeedbackContext(issueRepo, issueNumber, fromJson(attributesJson));
}
```

- [ ] **Step 4: Update SqliteRetrievalTracker.feedback() method**

Replace the `feedback` method (lines 137-152):

```java
@Override
public void feedback(String retrievalId, String sourceDocumentId,
                     RetrievalOutcome outcome, @Nullable FeedbackContext context) {
    String timestamp = toIso(Instant.now());
    try (Connection conn = dataSource.getConnection();
         PreparedStatement ps = conn.prepareStatement(
             "INSERT OR REPLACE INTO retrieval_feedback (retrieval_id, source_document_id, outcome, timestamp, issue_repo, issue_number, attributes) VALUES (?,?,?,?,?,?,?)")) {
        ps.setString(1, retrievalId);
        ps.setString(2, sourceDocumentId);
        ps.setString(3, outcome.name());
        ps.setString(4, timestamp);
        if (context != null) {
            ps.setString(5, context.issueRepo());
            if (context.issueNumber() != null) {
                ps.setInt(6, context.issueNumber());
            } else {
                ps.setNull(6, java.sql.Types.INTEGER);
            }
            ps.setString(7, toJson(context.attributes()));
        } else {
            ps.setNull(5, java.sql.Types.VARCHAR);
            ps.setNull(6, java.sql.Types.INTEGER);
            ps.setNull(7, java.sql.Types.VARCHAR);
        }
        ps.executeUpdate();
    } catch (SQLException e) {
        throw new IllegalStateException("feedback() failed", e);
    }
}
```

- [ ] **Step 5: Update SqliteRetrievalTracker.findFeedback() to read context**

Replace the `findFeedback` method (lines 199-231). The SELECT now includes the three new columns, and reconstructs `FeedbackContext`:

```java
@Override
public List<RetrievalFeedback> findFeedback(CorpusRef corpus,
                                             Instant since, Instant until) {
    var sql = new StringBuilder("SELECT f.retrieval_id, f.source_document_id, f.outcome, f.timestamp, f.issue_repo, f.issue_number, f.attributes FROM retrieval_feedback f JOIN retrieval_records r ON f.retrieval_id = r.retrieval_id WHERE r.tenant_id = ? AND r.corpus_name = ?");
    boolean hasSince = hasSinceFilter(since);
    boolean hasUntil = hasUntilFilter(until);
    if (hasSince) sql.append(" AND f.timestamp >= ?");
    if (hasUntil) sql.append(" AND f.timestamp < ?");

    try (Connection conn = dataSource.getConnection();
         PreparedStatement ps = conn.prepareStatement(sql.toString())) {
        int idx = 1;
        ps.setString(idx++, corpus.tenantId());
        ps.setString(idx++, corpus.corpusName());
        if (hasSince) ps.setString(idx++, toIso(since));
        if (hasUntil) ps.setString(idx++, toIso(until));

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
        throw new IllegalStateException("findFeedback() failed", e);
    }
}
```

- [ ] **Step 6: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api,rag-testing,rag-tracking`

Expected: all existing tests pass + 4 new contract tests pass (inherited by SqliteRetrievalTrackerTest).

- [ ] **Step 7: Commit**

```
git add rag-tracking/pom.xml \
       rag-tracking/src/main/resources/db/rag-tracking/migration/V2__feedback_context.sql \
       rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java
```

Message: `feat(rag-tracking): persist FeedbackContext in SQLite — V2 migration + JSON attributes  Refs #305`

## References

- specs/issue-306-collection-compat-tests/2026-09-11-feedback-context-enrichment-design.md — design spec
- rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java — current SPI
- rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalFeedback.java — current record
- rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java — SQLite impl
- rag-tracking/src/main/resources/db/rag-tracking/migration/V1__retrieval_tracking.sql — current schema
- rag-testing/src/main/java/io/casehub/neocortex/rag/testing/InMemoryRetrievalTracker.java — in-memory impl
- rag-testing/src/main/java/io/casehub/neocortex/rag/testing/RetrievalTrackerContractTest.java — contract tests
- memory-api/src/main/java/io/casehub/neocortex/memory/experience/ExperienceAttributeKeys.java — pattern reference
- memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java — JSON serialization pattern
- GE-20260719-59b809 — findFeedback() timestamp semantics
- GitHub #305
