# Feedback Context Enrichment

**Issue:** casehubio/neocortex#305
**Date:** 2026-09-11
**Status:** Draft

## Problem

`RetrievalTracker.feedback()` accepts only `(retrievalId, sourceDocumentId, outcome)` — no context about what triggered the retrieval or why the feedback was submitted. The same document can be HIGHLY_RELEVANT for one work context and NOT_RELEVANT for another, but this distinction is lost at the SPI boundary.

Production callers (`GardenMcpTools.gardenFeedback()`) already have issue context (`issueRepo`, `issueNumber`) available but cannot propagate it through the SPI. Future callers will have additional context dimensions (agentId, session, work phase) that should be capturable without SPI breaks.

## Design

### New types in rag-api

**FeedbackContext** — value type carrying typed fields for known high-value dimensions plus an extensible attributes map for the long tail. Follows the established neocortex pattern (MemoryInput, ExperienceEvent, CbrQuery).

```java
public record FeedbackContext(
    @Nullable String issueRepo,
    @Nullable Integer issueNumber,
    Map<String, String> attributes
) {
    public static final FeedbackContext EMPTY =
        new FeedbackContext(null, null, Map.of());

    public FeedbackContext {
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }

    public static FeedbackContext ofIssue(String issueRepo, int issueNumber) {
        return new FeedbackContext(issueRepo, issueNumber, Map.of());
    }
}
```

**FeedbackAttributeKeys** — standard attribute key constants. Same pattern as `ExperienceAttributeKeys`.

```java
public final class FeedbackAttributeKeys {
    public static final String AGENT_ID = "agent-id";
    public static final String SESSION_ID = "session-id";
    public static final String WORK_PHASE = "work-phase";

    private FeedbackAttributeKeys() {}
}
```

### SPI evolution

**RetrievalTracker** gains a 4-param `feedback()` as the new primary method. The existing 3-param signature becomes a default method bridge delegating with null context. Zero breakage for existing implementors and callers.

```java
public interface RetrievalTracker {

    // ... record(), find*(), purge() unchanged ...

    void feedback(String retrievalId, String sourceDocumentId,
                  RetrievalOutcome outcome, @Nullable FeedbackContext context);

    default void feedback(String retrievalId, String sourceDocumentId,
                          RetrievalOutcome outcome) {
        feedback(retrievalId, sourceDocumentId, outcome, null);
    }
}
```

### RetrievalFeedback evolution

Gains a 5th field for the round-trip context. Nullable — feedback submitted without context (via the default bridge or legacy callers) carries null.

```java
public record RetrievalFeedback(
    String retrievalId,
    String sourceDocumentId,
    RetrievalOutcome outcome,
    Instant timestamp,
    @Nullable FeedbackContext context
) {
    public RetrievalFeedback {
        // existing validations unchanged
        // context is nullable — no validation
    }
}
```

### findFeedback() — no signature change

`findFeedback(CorpusRef, Instant, Instant)` returns all feedback in the time window. Callers post-filter by context fields in Java. This matches the existing `RetrievalAnalyzer` pattern where `documentStats()` loads all feedback and post-filters by `retrievalId` (per GE-20260719-59b809). SQL-level filtering is a future enhancement if data volume warrants it.

### RetrievalAnalyzer — no change

`RetrievalAnalyzer` continues to aggregate feedback by document within a corpus+time window. Context-aware slicing (grouping by issue or project) is deferred — YAGNI until a consumer needs it.

## Storage

### SQLite (rag-tracking)

V2 Flyway migration adds three columns to `retrieval_feedback`:

```sql
-- V2__feedback_context.sql
ALTER TABLE retrieval_feedback ADD COLUMN issue_repo TEXT;
ALTER TABLE retrieval_feedback ADD COLUMN issue_number INTEGER;
ALTER TABLE retrieval_feedback ADD COLUMN attributes TEXT;

CREATE INDEX idx_feedback_issue ON retrieval_feedback(issue_repo, issue_number);
```

- `issue_repo` and `issue_number` are dedicated indexed columns for efficient SQL filtering.
- `attributes` is a JSON TEXT column for the long-tail map. SQLite `json_extract()` available for ad-hoc queries.
- Existing rows get NULL for all three columns — backward compatible.

**SqliteRetrievalTracker changes:**

- `feedback()`: INSERT/REPLACE now includes `issue_repo`, `issue_number`, `attributes` (JSON serialized via Jackson `ObjectMapper` — add `quarkus-jackson` dependency to `rag-tracking`, matching the pattern in `memory-sqlite`).
- `findFeedback()`: reads back the three new columns, reconstructs `FeedbackContext` (null if all three columns are null, otherwise builds the record).

### In-memory (rag-testing)

`InMemoryRetrievalTracker.feedback()` already stores `RetrievalFeedback` in a `ConcurrentHashMap`. The `RetrievalFeedback` record now carries context, so storage works automatically — no structural change needed beyond passing context through.

## Testing

Extend `RetrievalTrackerContractTest` with 4 new tests:

| Test | Verifies |
|------|----------|
| `feedback_storesContext` | Round-trip: submit feedback with `FeedbackContext.ofIssue(repo, number)`, retrieve via `findFeedback()`, verify context fields match |
| `feedback_nullContext` | Backward compat: submit via 3-param default method, verify `context()` is null on retrieved feedback |
| `feedback_upsertPreservesLatestContext` | UPSERT: submit feedback with context A, then with context B for same (retrievalId, docId) — verify only context B persists |
| `feedback_attributesRoundTrip` | Map serialization: submit feedback with attributes map containing 2+ entries, verify all entries survive round-trip |

## Scope exclusions

- **No `findFeedback()` overload** with context-based filtering — deferred until a caller needs SQL-level filtering.
- **No `RetrievalAnalyzer` changes** — context-aware slicing deferred until a consumer needs grouped analytics.
- **No upstream caller changes** — `GardenMcpTools` wiring to pass context is tracked separately (Hortora/engine concern, not neocortex).

## References

- `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java` — current SPI
- `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalFeedback.java` — current record
- `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java` — SQLite implementation
- `rag-tracking/src/main/resources/db/rag-tracking/migration/V1__retrieval_tracking.sql` — current schema
- `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/InMemoryRetrievalTracker.java` — in-memory impl
- `rag-testing/src/main/java/io/casehub/neocortex/rag/testing/RetrievalTrackerContractTest.java` — contract tests
- `memory-api/.../ExperienceAttributeKeys.java` — attribute keys pattern
- `memory-api/.../ExperienceEvent.java` — typed + attributes pattern
- GE-20260719-59b809 — findFeedback() timestamp semantics gotcha
- docs/specs/2026-07-05-retrieval-tracking-spi-design.md — original SPI design
