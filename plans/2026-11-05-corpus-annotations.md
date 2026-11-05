# Corpus Annotations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #788 — Corpus mindmap: sticky-note annotations on corpus entries
**Issue group:** #789 (parent epic), #785, #800, #786, #801, #787, #802 (completed)

**Goal:** Add agent-authored, per-entry annotations to corpus-management with dedicated SQLite storage and MCP operations.

**Architecture:** New `AnnotationStore` SPI in `corpus-management-api` with `SqliteAnnotationStore` in `corpus-management`. Own SQLite database (separate from CorpusEntryStore). FTS5 for annotation text search. Entry audit fields (`createdBy`, `createdAt`, `updatedBy`, `updatedAt`) added to `CorpusEntry`. MCP operations on `CorpusApi` for annotation CRUD and search.

**Tech Stack:** Java 21, SQLite (via SqliteDataSourceFactory), Flyway, JUnit 5 + AssertJ

## Global Constraints

- Java 21 source, Java 26 JVM (`JAVA_HOME=$(/usr/libexec/java_home -v 26)`)
- Build: `mvn clean install` (not `./mvnw`)
- Module build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl corpus-management-api,corpus-management`
- Use `ide-tooling` for all code navigation and structural editing
- Every commit references #788: `Refs #788` or `Closes #788`
- Annotation Flyway location: `classpath:db/corpus-annotations`
- Entry audit migration location: `classpath:db/corpus-catalogue` (next version: V3)

---

## Batch 1: SPI + Record Types

### Task 1: CorpusAnnotation record and AnnotationTypes constants

**Files:**
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusAnnotation.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/AnnotationTypes.java`

**Interfaces:**
- Consumes: nothing
- Produces: `CorpusAnnotation(String id, String corpusId, String entryId, String agentId, String type, String text, Map<String, String> metadata, Instant createdAt)`, `AnnotationTypes.QUALITY_FLAG`, `AnnotationTypes.CONTRADICTION`, `AnnotationTypes.STALENESS`, `AnnotationTypes.NOTE`

- [ ] **Step 1: Create CorpusAnnotation record**

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

- [ ] **Step 2: Create AnnotationTypes constants**

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

- [ ] **Step 3: Create AnnotationStore SPI**

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

- [ ] **Step 4: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl corpus-management-api`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
git add corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusAnnotation.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/AnnotationTypes.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/AnnotationStore.java
git commit -m "feat(#788): add CorpusAnnotation record, AnnotationTypes, and AnnotationStore SPI

Refs #788"
```

### Task 2: SqliteAnnotationStore implementation with tests

**Files:**
- Create: `corpus-management/src/main/resources/db/corpus-annotations/V1__annotations.sql`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteAnnotationStore.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/SqliteAnnotationStoreTest.java`

**Interfaces:**
- Consumes: `AnnotationStore` SPI, `CorpusAnnotation` record, `AnnotationTypes` constants, `SqliteDataSourceFactory` (from `sqlite-support`)
- Produces: `SqliteAnnotationStore(DataSource)` constructor

- [ ] **Step 1: Create Flyway migration**

File: `corpus-management/src/main/resources/db/corpus-annotations/V1__annotations.sql`

```sql
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

CREATE VIRTUAL TABLE annotations_fts USING fts5(
    text,
    content='annotations',
    content_rowid='rowid'
);

CREATE TRIGGER annotations_ai AFTER INSERT ON annotations BEGIN
    INSERT INTO annotations_fts(rowid, text) VALUES (new.rowid, new.text);
END;

CREATE TRIGGER annotations_ad AFTER DELETE ON annotations BEGIN
    INSERT INTO annotations_fts(annotations_fts, rowid, text)
        VALUES('delete', old.rowid, old.text);
END;
```

- [ ] **Step 2: Write failing tests**

File: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/SqliteAnnotationStoreTest.java`

```java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.corpus.management.AnnotationTypes;
import io.casehub.neocortex.corpus.management.CorpusAnnotation;
import io.casehub.neocortex.sqlite.SqliteDataSourceFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class SqliteAnnotationStoreTest {

    private SqliteAnnotationStore store;

    @BeforeEach
    void setUp() {
        var ds = SqliteDataSourceFactory.create(":memory:", 1, 3000);
        store = new SqliteAnnotationStore(ds);
    }

    @Test
    void addAndRetrieveByEntry() {
        var annotation = new CorpusAnnotation(
            null, "corpus-1", "entry-1", "agent-a",
            AnnotationTypes.QUALITY_FLAG, "Needs revision after Quarkus 3.36",
            Map.of("version", "3.36"), Instant.now());

        String id = store.add(annotation);
        assertThat(id).isNotNull();

        var results = store.forEntry("corpus-1", "entry-1");
        assertThat(results).hasSize(1);
        assertThat(results.get(0).id()).isEqualTo(id);
        assertThat(results.get(0).type()).isEqualTo(AnnotationTypes.QUALITY_FLAG);
        assertThat(results.get(0).text()).isEqualTo("Needs revision after Quarkus 3.36");
        assertThat(results.get(0).metadata()).containsEntry("version", "3.36");
    }

    @Test
    void forEntryFiltersByType() {
        store.add(new CorpusAnnotation(null, "c1", "e1", "agent-a",
            AnnotationTypes.QUALITY_FLAG, "Flag note", Map.of(), Instant.now()));
        store.add(new CorpusAnnotation(null, "c1", "e1", "agent-a",
            AnnotationTypes.NOTE, "General note", Map.of(), Instant.now()));

        var flags = store.forEntry("c1", "e1", AnnotationTypes.QUALITY_FLAG);
        assertThat(flags).hasSize(1);
        assertThat(flags.get(0).type()).isEqualTo(AnnotationTypes.QUALITY_FLAG);
    }

    @Test
    void forEntryReturnsEmptyForUnknownEntry() {
        assertThat(store.forEntry("c1", "unknown")).isEmpty();
    }

    @Test
    void removeDeletesAnnotation() {
        String id = store.add(new CorpusAnnotation(null, "c1", "e1", "agent-a",
            AnnotationTypes.NOTE, "To be removed", Map.of(), Instant.now()));

        store.remove(id);

        assertThat(store.forEntry("c1", "e1")).isEmpty();
    }

    @Test
    void removeForEntryDeletesAllAnnotationsOnEntry() {
        store.add(new CorpusAnnotation(null, "c1", "e1", "agent-a",
            AnnotationTypes.NOTE, "Note 1", Map.of(), Instant.now()));
        store.add(new CorpusAnnotation(null, "c1", "e1", "agent-b",
            AnnotationTypes.QUALITY_FLAG, "Flag 1", Map.of(), Instant.now()));
        store.add(new CorpusAnnotation(null, "c1", "e2", "agent-a",
            AnnotationTypes.NOTE, "Other entry", Map.of(), Instant.now()));

        int removed = store.removeForEntry("c1", "e1");
        assertThat(removed).isEqualTo(2);
        assertThat(store.forEntry("c1", "e1")).isEmpty();
        assertThat(store.forEntry("c1", "e2")).hasSize(1);
    }

    @Test
    void searchFindsAnnotationsByText() {
        store.add(new CorpusAnnotation(null, "c1", "e1", "agent-a",
            AnnotationTypes.STALENESS, "Outdated after Quarkus 3.36 upgrade",
            Map.of(), Instant.now()));
        store.add(new CorpusAnnotation(null, "c1", "e2", "agent-a",
            AnnotationTypes.NOTE, "Unrelated note about testing",
            Map.of(), Instant.now()));

        var results = store.search("Quarkus", null, 10);
        assertThat(results).hasSize(1);
        assertThat(results.get(0).entryId()).isEqualTo("e1");
    }

    @Test
    void searchFiltersByType() {
        store.add(new CorpusAnnotation(null, "c1", "e1", "agent-a",
            AnnotationTypes.STALENESS, "Quarkus related staleness",
            Map.of(), Instant.now()));
        store.add(new CorpusAnnotation(null, "c1", "e2", "agent-a",
            AnnotationTypes.NOTE, "Quarkus related note",
            Map.of(), Instant.now()));

        var results = store.search("Quarkus", AnnotationTypes.STALENESS, 10);
        assertThat(results).hasSize(1);
        assertThat(results.get(0).type()).isEqualTo(AnnotationTypes.STALENESS);
    }

    @Test
    void searchRespectsLimit() {
        for (int i = 0; i < 5; i++) {
            store.add(new CorpusAnnotation(null, "c1", "e" + i, "agent-a",
                AnnotationTypes.NOTE, "Searchable content item " + i,
                Map.of(), Instant.now()));
        }

        var results = store.search("Searchable", null, 3);
        assertThat(results).hasSize(3);
    }

    @Test
    void metadataRoundTrips() {
        var meta = Map.of("key1", "value1", "key2", "value2");
        String id = store.add(new CorpusAnnotation(null, "c1", "e1", "agent-a",
            AnnotationTypes.NOTE, "Note with metadata", meta, Instant.now()));

        var results = store.forEntry("c1", "e1");
        assertThat(results.get(0).metadata()).isEqualTo(meta);
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=SqliteAnnotationStoreTest`
Expected: FAIL — `SqliteAnnotationStore` class not found

- [ ] **Step 4: Implement SqliteAnnotationStore**

File: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteAnnotationStore.java`

```java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.corpus.management.AnnotationStore;
import io.casehub.neocortex.corpus.management.CorpusAnnotation;
import io.casehub.neocortex.sqlite.SqliteDataSourceFactory;

import javax.sql.DataSource;
import java.sql.*;
import java.time.Instant;
import java.util.*;
import java.util.logging.Level;
import java.util.logging.Logger;

public class SqliteAnnotationStore implements AnnotationStore {

    private static final Logger LOG = Logger.getLogger(SqliteAnnotationStore.class.getName());
    private static final String FLYWAY_LOCATION = "classpath:db/corpus-annotations";

    private final DataSource dataSource;

    public SqliteAnnotationStore(DataSource dataSource) {
        this.dataSource = dataSource;
        if (dataSource instanceof com.zaxxer.hikari.HikariDataSource hds) {
            SqliteDataSourceFactory.migrate(hds, FLYWAY_LOCATION);
        }
    }

    @Override
    public String add(CorpusAnnotation annotation) {
        String id = annotation.id() != null ? annotation.id() : UUID.randomUUID().toString();
        String sql = "INSERT INTO annotations (id, corpus_id, entry_id, agent_id, type, text, metadata, created_at) VALUES (?,?,?,?,?,?,?,?)";
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, id);
            ps.setString(2, annotation.corpusId());
            ps.setString(3, annotation.entryId());
            ps.setString(4, annotation.agentId());
            ps.setString(5, annotation.type());
            ps.setString(6, annotation.text());
            ps.setString(7, toJson(annotation.metadata()));
            ps.setString(8, annotation.createdAt() != null
                ? annotation.createdAt().toString() : Instant.now().toString());
            ps.executeUpdate();
        } catch (SQLException e) {
            throw new RuntimeException("Failed to add annotation", e);
        }
        return id;
    }

    @Override
    public void remove(String annotationId) {
        String sql = "DELETE FROM annotations WHERE id = ?";
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, annotationId);
            ps.executeUpdate();
        } catch (SQLException e) {
            throw new RuntimeException("Failed to remove annotation " + annotationId, e);
        }
    }

    @Override
    public List<CorpusAnnotation> forEntry(String corpusId, String entryId) {
        return queryAnnotations(
            "SELECT * FROM annotations WHERE corpus_id = ? AND entry_id = ? ORDER BY created_at",
            corpusId, entryId);
    }

    @Override
    public List<CorpusAnnotation> forEntry(String corpusId, String entryId, String type) {
        String sql = "SELECT * FROM annotations WHERE corpus_id = ? AND entry_id = ? AND type = ? ORDER BY created_at";
        List<CorpusAnnotation> results = new ArrayList<>();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, corpusId);
            ps.setString(2, entryId);
            ps.setString(3, type);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) results.add(fromRow(rs));
            }
        } catch (SQLException e) {
            throw new RuntimeException("Failed to query annotations", e);
        }
        return results;
    }

    @Override
    public List<CorpusAnnotation> search(String text, String type, int limit) {
        String sql;
        if (type != null) {
            sql = "SELECT a.* FROM annotations a JOIN annotations_fts f ON a.rowid = f.rowid WHERE annotations_fts MATCH ? AND a.type = ? ORDER BY rank LIMIT ?";
        } else {
            sql = "SELECT a.* FROM annotations a JOIN annotations_fts f ON a.rowid = f.rowid WHERE annotations_fts MATCH ? ORDER BY rank LIMIT ?";
        }
        List<CorpusAnnotation> results = new ArrayList<>();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, text);
            if (type != null) {
                ps.setString(2, type);
                ps.setInt(3, limit);
            } else {
                ps.setInt(2, limit);
            }
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) results.add(fromRow(rs));
            }
        } catch (SQLException e) {
            LOG.log(Level.WARNING, "Annotation search failed", e);
        }
        return results;
    }

    @Override
    public int removeForEntry(String corpusId, String entryId) {
        String sql = "DELETE FROM annotations WHERE corpus_id = ? AND entry_id = ?";
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, corpusId);
            ps.setString(2, entryId);
            return ps.executeUpdate();
        } catch (SQLException e) {
            throw new RuntimeException("Failed to remove annotations for entry " + entryId, e);
        }
    }

    private List<CorpusAnnotation> queryAnnotations(String sql, String corpusId, String entryId) {
        List<CorpusAnnotation> results = new ArrayList<>();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, corpusId);
            ps.setString(2, entryId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) results.add(fromRow(rs));
            }
        } catch (SQLException e) {
            throw new RuntimeException("Failed to query annotations", e);
        }
        return results;
    }

    private static CorpusAnnotation fromRow(ResultSet rs) throws SQLException {
        String metaJson = rs.getString("metadata");
        Map<String, String> metadata = metaJson != null ? fromJson(metaJson) : Map.of();
        Instant createdAt;
        try { createdAt = Instant.parse(rs.getString("created_at")); }
        catch (Exception e) { createdAt = Instant.now(); }
        return new CorpusAnnotation(
            rs.getString("id"),
            rs.getString("corpus_id"),
            rs.getString("entry_id"),
            rs.getString("agent_id"),
            rs.getString("type"),
            rs.getString("text"),
            metadata,
            createdAt);
    }

    @SuppressWarnings("unchecked")
    private static Map<String, String> fromJson(String json) {
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper()
                .readValue(json, Map.class);
        } catch (Exception e) {
            return Map.of();
        }
    }

    private static String toJson(Map<String, String> map) {
        if (map == null || map.isEmpty()) return null;
        try {
            return new com.fasterxml.jackson.databind.ObjectMapper()
                .writeValueAsString(map);
        } catch (Exception e) {
            return null;
        }
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=SqliteAnnotationStoreTest`
Expected: 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add corpus-management/src/main/resources/db/corpus-annotations/V1__annotations.sql corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteAnnotationStore.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/SqliteAnnotationStoreTest.java
git commit -m "feat(#788): implement SqliteAnnotationStore with FTS5 search

Own SQLite database via SqliteDataSourceFactory. 9 tests covering add,
remove, forEntry, type filtering, search, removeForEntry, metadata
round-trip.

Refs #788"
```

## Batch 2: Entry Audit + MCP

### Task 3: Add audit fields to CorpusEntry and SqliteCorpusEntryStore

**Files:**
- Modify: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusEntry.java`
- Create: `corpus-management/src/main/resources/db/corpus-catalogue/V3__entry_audit_fields.sql`
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStore.java`
- Modify: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStoreTest.java`

**Interfaces:**
- Consumes: `CorpusEntry` (existing), `SqliteCorpusEntryStore` (existing)
- Produces: `CorpusEntry` with 4 new nullable fields: `createdBy` (String), `createdAt` (Instant), `updatedBy` (String), `updatedAt` (Instant)

- [ ] **Step 1: Write failing test for audit fields**

Add to `SqliteCorpusEntryStoreTest.java`:

```java
@Test
void addPersistsAuditFields() {
    var entry = new CorpusEntry("e-audit", Map.of("title", "Audit test"), "Body",
        null, "agent-x", Instant.parse("2026-11-05T10:00:00Z"), null, null);
    store.add(CORPUS, entry);

    var retrieved = store.get(CORPUS, "e-audit");
    assertThat(retrieved).isPresent();
    assertThat(retrieved.get().createdBy()).isEqualTo("agent-x");
    assertThat(retrieved.get().createdAt()).isEqualTo(Instant.parse("2026-11-05T10:00:00Z"));
}

@Test
void updatePersistsAuditFields() {
    var entry = new CorpusEntry("e-audit2", Map.of("title", "Original"), "Body",
        null, "agent-x", Instant.parse("2026-11-05T10:00:00Z"), null, null);
    store.add(CORPUS, entry);

    var updated = new CorpusEntry("e-audit2", Map.of("title", "Updated"), "New body",
        null, "agent-x", Instant.parse("2026-11-05T10:00:00Z"),
        "agent-y", Instant.parse("2026-11-05T11:00:00Z"));
    store.update(CORPUS, "e-audit2", updated);

    var retrieved = store.get(CORPUS, "e-audit2");
    assertThat(retrieved).isPresent();
    assertThat(retrieved.get().updatedBy()).isEqualTo("agent-y");
    assertThat(retrieved.get().updatedAt()).isEqualTo(Instant.parse("2026-11-05T11:00:00Z"));
}

@Test
void existingEntriesReturnNullAuditFields() {
    var entry = new CorpusEntry("e-legacy", Map.of("title", "Legacy"), "Body", null);
    store.add(CORPUS, entry);

    var retrieved = store.get(CORPUS, "e-legacy");
    assertThat(retrieved).isPresent();
    assertThat(retrieved.get().createdBy()).isNull();
    assertThat(retrieved.get().updatedBy()).isNull();
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=SqliteCorpusEntryStoreTest`
Expected: FAIL — `CorpusEntry` constructor doesn't accept audit fields

- [ ] **Step 3: Add audit fields to CorpusEntry record**

Modify `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusEntry.java`:

```java
package io.casehub.neocortex.corpus.management;

import java.time.Instant;
import java.util.List;
import java.util.Map;

public record CorpusEntry(
    String id,
    Map<String, Object> metadata,
    String body,
    String artifactRef,
    String createdBy,
    Instant createdAt,
    String updatedBy,
    Instant updatedAt
) {
    public CorpusEntry(String id, Map<String, Object> metadata, String body, String artifactRef) {
        this(id, metadata, body, artifactRef, null, null, null, null);
    }

    public String stringField(String key) {
        return (String) metadata.get(key);
    }

    @SuppressWarnings("unchecked")
    public List<String> stringListField(String key) {
        return (List<String>) metadata.get(key);
    }

    public Instant instantField(String key) {
        return (Instant) metadata.get(key);
    }

    public Integer intField(String key) {
        return (Integer) metadata.get(key);
    }

    public Double doubleField(String key) {
        return (Double) metadata.get(key);
    }
}
```

The 4-arg constructor preserves backward compatibility — all existing callers continue to work with null audit fields.

- [ ] **Step 4: Create Flyway migration**

File: `corpus-management/src/main/resources/db/corpus-catalogue/V3__entry_audit_fields.sql`

```sql
ALTER TABLE corpus_entries ADD COLUMN created_by TEXT;
ALTER TABLE corpus_entries ADD COLUMN updated_by TEXT;
ALTER TABLE corpus_entries ADD COLUMN updated_at TEXT;
```

Note: `created_at` and `last_modified_at` already exist in the schema (V2). The new `created_by` column tracks WHO created; the existing `created_at` column already tracks WHEN. `updated_by` + `updated_at` are new. The existing `last_modified_at` was store-generated; `updated_at` is caller-provided.

- [ ] **Step 5: Update SqliteCorpusEntryStore to persist and read audit fields**

In `SqliteCorpusEntryStore.add()` — add `created_by` to the INSERT:

```java
String sql = "INSERT INTO corpus_entries (id, corpus_tenant_id, corpus_name, frontmatter_json, body, artifact_ref, created_at, last_modified_at, created_by) VALUES (?,?,?,?,?,?,?,?,?)";
// ... existing bindings ...
ps.setString(9, entry.createdBy()); // nullable
```

In `SqliteCorpusEntryStore.update()` — add `updated_by`, `updated_at` to the UPDATE:

```java
String sql = "UPDATE corpus_entries SET frontmatter_json = ?, body = ?, artifact_ref = ?, last_modified_at = ?, updated_by = ?, updated_at = ? WHERE id = ? AND corpus_tenant_id = ? AND corpus_name = ?";
// ... existing bindings ...
ps.setString(5, entry.updatedBy()); // nullable
ps.setString(6, entry.updatedAt() != null ? entry.updatedAt().toString() : null);
ps.setString(7, entryId);
ps.setString(8, corpus.tenantId());
ps.setString(9, corpus.corpusName());
```

In `fromRow()` — read the new columns:

```java
private static CorpusEntry fromRow(ResultSet rs) throws SQLException {
    String createdBy = rs.getString("created_by");
    String updatedBy = rs.getString("updated_by");
    String updatedAtStr = rs.getString("updated_at");
    Instant createdAt = null;
    try { createdAt = Instant.parse(rs.getString("created_at")); } catch (Exception ignored) {}
    Instant updatedAt = null;
    if (updatedAtStr != null) {
        try { updatedAt = Instant.parse(updatedAtStr); } catch (Exception ignored) {}
    }
    return new CorpusEntry(
        rs.getString("id"),
        fromJson(rs.getString("frontmatter_json")),
        rs.getString("body"),
        rs.getString("artifact_ref"),
        createdBy,
        createdAt,
        updatedBy,
        updatedAt);
}
```

Also update the SELECT in `get()` to include the new columns:

```java
String sql = "SELECT id, frontmatter_json, body, artifact_ref, created_at, created_by, updated_by, updated_at FROM corpus_entries WHERE id = ? AND corpus_tenant_id = ? AND corpus_name = ?";
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-api,corpus-management`
Expected: ALL tests PASS (existing + 3 new audit tests)

- [ ] **Step 7: Commit**

```bash
git add corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusEntry.java corpus-management/src/main/resources/db/corpus-catalogue/V3__entry_audit_fields.sql corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStore.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStoreTest.java
git commit -m "feat(#788): add audit fields to CorpusEntry (createdBy, createdAt, updatedBy, updatedAt)

Backward-compatible 4-arg constructor preserved. Flyway V3 adds columns.
SqliteCorpusEntryStore persists and reads audit fields. 3 new tests.

Refs #788"
```

### Task 4: Add annotation MCP operations to CorpusApi

**Files:**
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApi.java`
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBean.java`
- Modify: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBeanTest.java`

**Interfaces:**
- Consumes: `AnnotationStore` SPI, `CorpusAnnotation` record, `CorpusApiBean` (existing)
- Produces: 4 new MCP operations on `CorpusApi`: `annotate`, `annotations`, `searchAnnotations`, `removeAnnotation`

- [ ] **Step 1: Write failing test for MCP annotation operations**

Add to `CorpusApiBeanTest.java` (or create it if it doesn't exist):

```java
@Test
void annotateCreatesAnnotation() {
    String id = apiBean.annotate("corpus-1", "entry-1", AnnotationTypes.NOTE,
        "This entry needs review", "agent-a");
    assertThat(id).isNotNull();

    var annotations = apiBean.annotations("corpus-1", "entry-1", null);
    assertThat(annotations).hasSize(1);
    assertThat(annotations.get(0).text()).isEqualTo("This entry needs review");
}

@Test
void searchAnnotationsFindsByText() {
    apiBean.annotate("corpus-1", "entry-1", AnnotationTypes.STALENESS,
        "Outdated after Quarkus upgrade", "agent-a");

    var results = apiBean.searchAnnotations("Quarkus", null, 10);
    assertThat(results).hasSize(1);
}

@Test
void removeAnnotationDeletes() {
    String id = apiBean.annotate("corpus-1", "entry-1", AnnotationTypes.NOTE,
        "Temporary note", "agent-a");

    apiBean.removeAnnotation(id);

    assertThat(apiBean.annotations("corpus-1", "entry-1", null)).isEmpty();
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=CorpusApiBeanTest`
Expected: FAIL — methods not found on `CorpusApi`

- [ ] **Step 3: Add annotation methods to CorpusApi interface**

Append to `CorpusApi.java`:

```java
@PlatformMutation("Add a typed annotation to a corpus entry")
String annotate(String corpusId, String entryId,
                String type, String text, String agentId);

@PlatformQuery("List annotations on a corpus entry, optionally filtered by type")
List<CorpusAnnotation> annotations(String corpusId, String entryId, String type);

@PlatformQuery("Search annotation text across all entries, optionally filtered by type")
List<CorpusAnnotation> searchAnnotations(String text, String type, Integer limit);

@PlatformMutation("Remove an annotation by ID")
void removeAnnotation(String annotationId);
```

Add import for `CorpusAnnotation` at the top.

- [ ] **Step 4: Implement in CorpusApiBean**

Add `AnnotationStore` to `CorpusApiBean` constructor (5th param):

```java
private final AnnotationStore annotationStore;

public CorpusApiBean(SearchResource searchResource,
                      SearchProfileStore profileStore,
                      ProvenanceStore provenanceStore,
                      CorpusRef corpusRef,
                      AnnotationStore annotationStore) {
    this.searchResource  = searchResource;
    this.profileStore    = profileStore;
    this.provenanceStore = provenanceStore;
    this.corpusRef       = corpusRef;
    this.annotationStore = annotationStore;
}
```

Implement the 4 methods:

```java
@Override
public String annotate(String corpusId, String entryId,
                        String type, String text, String agentId) {
    var annotation = new CorpusAnnotation(
        null, corpusId != null ? corpusId : corpusRef.corpusName(),
        entryId, agentId, type, text, Map.of(), Instant.now());
    return annotationStore.add(annotation);
}

@Override
public List<CorpusAnnotation> annotations(String corpusId, String entryId, String type) {
    String cid = corpusId != null ? corpusId : corpusRef.corpusName();
    if (type != null && !type.isBlank()) {
        return annotationStore.forEntry(cid, entryId, type);
    }
    return annotationStore.forEntry(cid, entryId);
}

@Override
public List<CorpusAnnotation> searchAnnotations(String text, String type, Integer limit) {
    return annotationStore.search(text, type, limit != null ? limit : 20);
}

@Override
public void removeAnnotation(String annotationId) {
    annotationStore.remove(annotationId);
}
```

- [ ] **Step 5: Update CorpusApiBeanTest setUp to provide AnnotationStore**

In the test's `setUp()`, create a `SqliteAnnotationStore` backed by `:memory:` and pass it as the 5th constructor argument to `CorpusApiBean`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management`
Expected: ALL tests PASS

- [ ] **Step 7: Run full module build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl corpus-management-api,corpus-management`
Expected: BUILD SUCCESS

- [ ] **Step 8: Commit**

```bash
git add corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApi.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBean.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBeanTest.java
git commit -m "feat(#788): add annotation MCP operations to CorpusApi

annotate, annotations, searchAnnotations, removeAnnotation operations.
CorpusApiBean wires AnnotationStore. 3 new MCP tests.

Closes #788"
```

## References

- `specs/issue-787-rich-document-ingestion/2026-11-05-corpus-annotations-design.md` — design spec
- `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusEntry.java` — existing record to modify
- `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/CorpusEntryStore.java` — SPI pattern reference
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStore.java` — SQLite impl pattern reference
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/ProvenanceStore.java` — separate SQLite DB pattern
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApi.java` — MCP interface to extend
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBean.java` — MCP implementation
- `corpus-management/src/main/resources/db/corpus-catalogue/V2__create_entries.sql` — existing entry schema
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java` — string constants pattern
- GitHub #788 — focal issue
- GitHub #789 — parent epic
