# Feedback Filtering and Analyzer Slicing

**Issues:** casehubio/neocortex#317, casehubio/neocortex#318
**Date:** 2026-09-11
**Status:** Draft
**Depends on:** #305 (FeedbackContext enrichment — landed)

## Problem

`findFeedback(CorpusRef, Instant, Instant)` returns all feedback in a time window with no ability to filter by context dimensions. `RetrievalAnalyzer` aggregates feedback by document within a corpus+time window with no ability to scope analysis to a specific issue, project, or agent.

With `FeedbackContext` now stored on every feedback submission (#305), the query and analysis layers need corresponding filtering capabilities.

## Design

### New type in rag-api: FeedbackFilter

Mirrors `FeedbackContext`'s shape. Each field is nullable — null means "don't filter on this dimension."

```java
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
}
```

### SPI change: RetrievalTracker

New `findFeedback` overload as a default method. The default implementation loads all feedback and post-filters in Java — any tracker implementation works without changes. `SqliteRetrievalTracker` overrides with SQL-level filtering for efficiency.

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

A static `FeedbackFilter.matches(RetrievalFeedback, FeedbackFilter)` method handles the matching logic — reusable by the default method and by any test that needs to verify filter semantics.

### Matching semantics

- `issueRepo` non-null: feedback context must have matching `issueRepo()`
- `issueNumber` non-null: feedback context must have matching `issueNumber()`
- `attributes` non-empty: each entry must match the corresponding key in `context.attributes()`
- All non-null filter fields must match (AND semantics)
- Feedback with null context never matches a non-trivial filter

### SqliteRetrievalTracker override

Overrides the default method with SQL-level filtering. Appends WHERE clauses dynamically:

- `issueRepo` non-null → `AND f.issue_repo = ?`
- `issueNumber` non-null → `AND f.issue_number = ?`
- Each attribute entry → `AND json_extract(f.attributes, ?) = ?` (key as `$.keyName`)

Uses the existing composite index `idx_feedback_issue` on `(issue_repo, issue_number)` for typed field filtering. `json_extract` queries are unindexed — acceptable at current feedback volume.

### InMemoryRetrievalTracker

Inherits the default method — no override needed. Post-filters in Java.

### RetrievalAnalyzer overloads

Two new static method overloads that accept `FeedbackFilter`:

**`documentStats(tracker, corpus, since, until, filter)`** — delegates to `tracker.findFeedback(corpus, since, until, filter)` instead of the unfiltered method. All downstream logic (feedbackDistribution, appearances) is unchanged. The existing no-filter method delegates to the new one with `FeedbackFilter.NONE`.

**`qualitySignals(tracker, corpus, since, until, thresholds, filter)`** — calls the filtered `documentStats` overload. Same derivation logic (lowQualityRatio, minFeedbackForQualityCheck). The existing no-filter method delegates with `FeedbackFilter.NONE`.

### Testing

**Contract tests (RetrievalTrackerContractTest):**

| Test | Verifies |
|------|----------|
| `findFeedback_filterByIssue` | Submit feedback with two different issue contexts. Filter by one — only matching feedback returned. |
| `findFeedback_filterByAttributes` | Submit feedback with different agent IDs. Filter by agent-id attribute — only matching returned. |
| `findFeedback_filterNoneReturnsAll` | `FeedbackFilter.NONE` returns all feedback (same as unfiltered). |
| `findFeedback_nullContextExcludedByFilter` | Feedback submitted without context is excluded when any filter field is set. |

**Analyzer tests (in rag-api/src/test):**

| Test | Verifies |
|------|----------|
| `documentStats_filteredByIssue` | DocumentStats distributions only reflect feedback matching the filter. |
| `qualitySignals_filteredByIssue` | Quality signals computed from filtered feedback only. |

### Scope exclusions

- No `correlationGraph` or `documentImpact` filter overloads — deferred until a consumer needs them.
- No index on `attributes` JSON column — `json_extract` filtering is sufficient at current scale.

## References

- `rag-api/src/main/java/io/casehub/neocortex/rag/FeedbackContext.java` — context type this filter matches against
- `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalTracker.java` — SPI gaining overload
- `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java` — static utility gaining overloads
- `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java` — SQL override
- `rag-tracking/src/main/resources/db/rag-tracking/migration/V2__feedback_context.sql` — schema with indexed columns
- `memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java` — json_extract pattern reference
- specs/issue-306-collection-compat-tests/2026-09-11-feedback-context-enrichment-design.md — parent design
- GitHub #317, #318
