# Corpus Annotations Design — #788

## Overview

Sticky-note annotations on corpus entries. Agents attach typed notes to entries — quality flags, contradiction notices, staleness markers, general observations. Annotations are first-class queryable objects with their own search, independent of corpus search.

## Scope

**In scope:**
- `AnnotationStore` SPI in `corpus-management-api`
- `CorpusAnnotation` record in `corpus-management-api`
- `AnnotationTypes` constants in `corpus-management-api`
- `SqliteAnnotationStore` in `corpus-management`
- Entry audit fields (`createdBy`, `createdAt`, `updatedBy`, `updatedAt`) on `CorpusEntry`
- MCP operations on `CorpusApi` for annotation CRUD and search

**Out of scope:**
- Human-authored annotations (agents only for now)
- Block/section-level granularity (per-entry only)
- Annotation text boosting corpus search results (separate search only)
- Confidence decay or supersession lifecycle
- MindMap graph integration (can be bridged later)
- Git-native AnnotationStore impl (SPI boundary enables this later)

## Architecture

### Module Placement

| Artifact | Module |
|----------|--------|
| `CorpusAnnotation` record | `corpus-management-api` |
| `AnnotationStore` SPI | `corpus-management-api` |
| `AnnotationTypes` constants | `corpus-management-api` |
| `SqliteAnnotationStore` impl | `corpus-management` |
| `CorpusEntry` audit fields | `corpus-management-api` (record change) |
| `SqliteCorpusEntryStore` migration | `corpus-management` (Flyway) |
| MCP annotation operations | `corpus-management` (`CorpusApi`) |

Follows the established pattern: SPI in API module, SQLite impl in runtime module — same as `CorpusEntryStore`, `ProvenanceStore`, `CorpusSearch`.

### Storage

Own SQLite database via `SqliteDataSourceFactory` (separate HikariCP pool, WAL mode). Zero contention with MindMap or CaseMemoryStore. Path configurable via `casehub.corpus.annotations.sqlite.path`.

Rationale: MindMap's SQLite WAL is already busy with consolidation phases, trait rules, derived edges, and confidence decay. A dedicated database keeps annotation throughput predictable under high-frequency agent annotation.

## Data Model

### CorpusAnnotation

```java
package io.casehub.neocortex.corpus.management;

import java.time.Instant;
import java.util.Map;

public record CorpusAnnotation(
    String id,
    String corpusId,
    String entryId,
    String agentId,
    String type,
    String text,
    Map<String, String> metadata,
    Instant createdAt
) {
    public CorpusAnnotation {
        if (entryId == null || entryId.isBlank())
            throw new IllegalArgumentException("entryId must not be blank");
        if (type == null || type.isBlank())
            throw new IllegalArgumentException("type must not be blank");
        if (text == null || text.isBlank())
            throw new IllegalArgumentException("text must not be blank");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }
}
```

### AnnotationTypes

```java
package io.casehub.neocortex.corpus.management;

public final class AnnotationTypes {
    public static final String QUALITY_FLAG = "quality-flag";
    public static final String CONTRADICTION = "contradiction";
    public static final String STALENESS = "staleness";
    public static final String NOTE = "note";

    private AnnotationTypes() {}
}
```

String type field — not an enum. Consumers define domain-specific types beyond the built-in constants. Follows the `SubgraphTypes` pattern from MindMap.

### AnnotationStore SPI

```java
package io.casehub.neocortex.corpus.management;

import java.util.List;

public interface AnnotationStore {

    String add(CorpusAnnotation annotation);

    void remove(String annotationId);

    List<CorpusAnnotation> forEntry(String corpusId, String entryId);

    List<CorpusAnnotation> forEntry(String corpusId, String entryId, String type);

    List<CorpusAnnotation> search(String text, String type, int limit);

    int removeForEntry(String corpusId, String entryId);
}
```

- `add` — stores an annotation, returns generated ID
- `remove` — deletes a single annotation by ID
- `forEntry` — all annotations on an entry, optionally filtered by type
- `search` — FTS5 text search across annotation content, optionally filtered by type
- `removeForEntry` — bulk delete all annotations on an entry (for entry deletion cascade)

No `update` — annotations are immutable notes. Delete and recreate if wrong.

### SQLite Schema

```sql
-- Flyway: V1__annotations.sql
CREATE TABLE annotations (
    id          TEXT PRIMARY KEY,
    corpus_id   TEXT NOT NULL,
    entry_id    TEXT NOT NULL,
    agent_id    TEXT NOT NULL,
    type        TEXT NOT NULL,
    text        TEXT NOT NULL,
    metadata    TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX idx_annotations_entry ON annotations(corpus_id, entry_id);
CREATE INDEX idx_annotations_type ON annotations(corpus_id, type);

-- FTS5 for annotation text search
CREATE VIRTUAL TABLE annotations_fts USING fts5(
    text,
    content='annotations',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER annotations_ai AFTER INSERT ON annotations BEGIN
    INSERT INTO annotations_fts(rowid, text) VALUES (new.rowid, new.text);
END;

CREATE TRIGGER annotations_ad AFTER DELETE ON annotations BEGIN
    INSERT INTO annotations_fts(annotations_fts, rowid, text)
        VALUES('delete', old.rowid, old.text);
END;
```

### CorpusEntry Audit Fields

```java
public record CorpusEntry(
    String id,
    Map<String, Object> metadata,
    String body,
    String artifactRef,
    String createdBy,      // nullable — null for pre-existing entries
    Instant createdAt,     // nullable
    String updatedBy,      // nullable
    Instant updatedAt      // nullable
)
```

SqliteCorpusEntryStore migration:

```sql
-- Flyway: V<next>__entry_audit_fields.sql
ALTER TABLE corpus_entries ADD COLUMN created_by TEXT;
ALTER TABLE corpus_entries ADD COLUMN created_at TEXT;
ALTER TABLE corpus_entries ADD COLUMN updated_by TEXT;
ALTER TABLE corpus_entries ADD COLUMN updated_at TEXT;
```

Callers populate the audit fields on the `CorpusEntry` record before calling `add()`/`update()`. The store persists what it receives — it does not resolve identity or generate timestamps. This keeps the SPI signature unchanged (`add(CorpusRef, CorpusEntry)`) and avoids a breaking change to existing callers (pre-existing entries pass nulls).

## MCP Operations

Added to `CorpusApi`:

```java
@PlatformMutation("Add an annotation to a corpus entry")
String annotate(String corpusId, String entryId,
                String type, String text, String agentId);

@PlatformQuery("List annotations on a corpus entry, optionally filtered by type")
List<CorpusAnnotation> annotations(String corpusId, String entryId, String type);

@PlatformQuery("Search annotation text across all entries, optionally filtered by type")
List<CorpusAnnotation> searchAnnotations(String text, String type, Integer limit);

@PlatformMutation("Remove an annotation by ID")
void removeAnnotation(String annotationId);
```

Metadata is not exposed via MCP — it's for programmatic use. MCP callers use the fixed fields.

## Testing

- `AnnotationStoreContractTest` abstract base in `corpus-management` test sources — covers add, remove, forEntry, forEntry with type filter, search, removeForEntry, immutability (no update), edge cases (blank text rejection, null type rejection)
- `SqliteAnnotationStore` concrete test extending the contract
- `CorpusEntry` audit field tests in existing `SqliteCorpusEntryStore` tests

## References

- `CorpusEntryStore.java` — established SPI pattern for corpus-management-api
- `SqliteCorpusEntryStore.java` — established SQLite impl pattern
- `ProvenanceStore.java` — separate SQLite database pattern with SqliteDataSourceFactory
- `SubgraphTypes.java` — string constants pattern for extensible types
- `CorpusApi.java` — MCP domain for annotation operations
- `BlockAnnotation.java` — existing structural annotation (different concept: inline text markers vs. sticky notes)
- Issue #788 — acceptance criteria and design questions
- Decision D8, D9 in decisions.md
