# mindmap-sqlite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #214 — feat: mindmap-sqlite — production SQLite backend
**Issue group:** #214

**Goal:** SQLite-backed `MindMapStore` implementation passing all 72 contract tests, following the `memory-sqlite` pattern (HikariCP WAL, Flyway, FTS5).

**Architecture:** New `mindmap-sqlite/` module with `SqliteMindMapStore` as `@Alternative @Priority(1)` — displaces `NoOpMindMapStore` and `InMemoryMindMapStore` when on classpath. Six tables (nodes, edges, aliases, subgraphs, node_refs, supersessions) with FTS5 content table on node names and properties. JSON blobs for traits, refs, and properties. Programmatic HikariCP + Flyway at `@PostConstruct`.

**Tech Stack:** Java 21, SQLite (xerial jdbc), HikariCP, Flyway, FTS5, Jackson (JSON), Quarkus CDI

## Global Constraints

- Java 21 source (Java 26 JVM)
- No platform-api dependency (no `CurrentPrincipal` — tenantId is a method parameter)
- `@Alternative @Priority(1)` — displaces `InMemoryMindMapStore` (@Priority(2)) and `NoOpMindMapStore` (@DefaultBean)
- Config namespace: `casehub.mindmap.sqlite.*`
- Flyway location: `classpath:db/mindmap-sqlite/migration`
- Timestamps stored as truncated-to-millis ISO-8601 (24 chars: `...T10:15:30.000Z`) — same pattern as `memory-sqlite`
- Must pass all 72 `MindMapStoreContractTest` tests

---

## Batch 1: Module + Schema + Node/Subgraph CRUD

### Task 1: Maven module + Flyway migration + basic wiring

**Files:**
- Create: `mindmap-sqlite/pom.xml`
- Create: `mindmap-sqlite/src/main/java/io/casehub/neocortex/mindmap/sqlite/SqliteMindMapStore.java`
- Create: `mindmap-sqlite/src/main/resources/db/mindmap-sqlite/migration/V1__mindmap_sqlite_schema.sql`
- Modify: `pom.xml` (parent — add `<module>` + `<dependencyManagement>` entry)
- Test: `mindmap-sqlite/src/test/java/io/casehub/neocortex/mindmap/sqlite/SqliteMindMapStoreTest.java`

**Interfaces:**
- Consumes: `MindMapStore` SPI (mindmap-api), `MindMapStoreContractTest` (mindmap-testing)
- Produces: `SqliteMindMapStore` — `@Alternative @Priority(1) @ApplicationScoped`, all 72 contract tests passing

- [ ] **Step 1: Create `pom.xml`**

Dependencies: `mindmap-api`, `sqlite-jdbc`, `HikariCP`, `flyway-core`, `quarkus-jackson`, `quarkus-arc`, `micrometer-core`. Test scope: `mindmap-testing`, `junit-jupiter`, `assertj-core`.

```xml
<!-- Follow memory-sqlite/pom.xml pattern exactly -->
```

- [ ] **Step 2: Add module to parent POM**

Add `<module>mindmap-sqlite</module>` after `mindmap-inmem` in the `<modules>` section. Add `<dependency>` entry in `<dependencyManagement>` with `${project.version}`.

- [ ] **Step 3: Create Flyway migration V1**

Six tables + FTS5 + indexes + triggers:

```sql
-- nodes: core columns + JSON blobs for traits, refs, properties
CREATE TABLE IF NOT EXISTS mindmap_node (
    node_id        TEXT NOT NULL,
    tenant_id      TEXT NOT NULL,
    name           TEXT NOT NULL,
    subgraph_id    TEXT NOT NULL,
    confidence_origin TEXT NOT NULL,
    confidence     REAL NOT NULL,
    provenance     TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    confirmed_at   TEXT NOT NULL,
    valid_from     TEXT,
    valid_until    TEXT,
    traits         TEXT NOT NULL DEFAULT '[]',
    refs           TEXT NOT NULL DEFAULT '[]',
    pleasure       REAL,
    arousal        REAL,
    dominance      REAL,
    properties     TEXT NOT NULL DEFAULT '{}',
    superseded_at  TEXT,
    superseding_id TEXT,
    supersession_reason TEXT,
    reinstated_at  TEXT,
    PRIMARY KEY (node_id)
);

CREATE INDEX IF NOT EXISTS mindmap_node_tenant_idx
    ON mindmap_node (tenant_id);
CREATE INDEX IF NOT EXISTS mindmap_node_subgraph_idx
    ON mindmap_node (tenant_id, subgraph_id);
CREATE INDEX IF NOT EXISTS mindmap_node_name_idx
    ON mindmap_node (tenant_id, LOWER(name));

-- edges
CREATE TABLE IF NOT EXISTS mindmap_edge (
    edge_id        TEXT NOT NULL,
    tenant_id      TEXT NOT NULL,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_type      TEXT NOT NULL,
    tier           TEXT NOT NULL,
    confidence_origin TEXT NOT NULL,
    confidence     REAL NOT NULL,
    provenance     TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL,
    valid_from     TEXT,
    valid_until    TEXT,
    pleasure       REAL,
    arousal        REAL,
    dominance      REAL,
    properties     TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (edge_id)
);

CREATE INDEX IF NOT EXISTS mindmap_edge_tenant_idx
    ON mindmap_edge (tenant_id);
CREATE INDEX IF NOT EXISTS mindmap_edge_source_idx
    ON mindmap_edge (tenant_id, source_node_id);
CREATE INDEX IF NOT EXISTS mindmap_edge_target_idx
    ON mindmap_edge (tenant_id, target_node_id);
CREATE INDEX IF NOT EXISTS mindmap_edge_type_idx
    ON mindmap_edge (tenant_id, edge_type);

-- aliases
CREATE TABLE IF NOT EXISTS mindmap_alias (
    tenant_id TEXT NOT NULL,
    alias     TEXT NOT NULL,
    node_id   TEXT NOT NULL,
    PRIMARY KEY (tenant_id, alias)
);

-- subgraphs
CREATE TABLE IF NOT EXISTS mindmap_subgraph (
    subgraph_id  TEXT NOT NULL,
    tenant_id    TEXT NOT NULL,
    name         TEXT NOT NULL,
    type         TEXT NOT NULL,
    root_node_id TEXT,
    created_at   TEXT NOT NULL,
    PRIMARY KEY (subgraph_id)
);

-- FTS5 content table on node names + properties
CREATE VIRTUAL TABLE IF NOT EXISTS mindmap_fts
    USING fts5(name, properties, content='mindmap_node', content_rowid='rowid');

CREATE TRIGGER IF NOT EXISTS mindmap_fts_ai AFTER INSERT ON mindmap_node BEGIN
    INSERT INTO mindmap_fts(rowid, name, properties) VALUES (new.rowid, new.name, new.properties);
END;

CREATE TRIGGER IF NOT EXISTS mindmap_fts_ad AFTER DELETE ON mindmap_node BEGIN
    INSERT INTO mindmap_fts(mindmap_fts, rowid, name, properties) VALUES('delete', old.rowid, old.name, old.properties);
END;

CREATE TRIGGER IF NOT EXISTS mindmap_fts_au AFTER UPDATE ON mindmap_node BEGIN
    INSERT INTO mindmap_fts(mindmap_fts, rowid, name, properties) VALUES('delete', old.rowid, old.name, old.properties);
    INSERT INTO mindmap_fts(rowid, name, properties) VALUES (new.rowid, new.name, new.properties);
END;
```

- [ ] **Step 4: Implement `SqliteMindMapStore` — init/shutdown + subgraph + node CRUD**

Follow `SqliteMemoryStore` pattern: `@PostConstruct init()` creates `HikariDataSource` + runs Flyway. `@PreDestroy shutdown()` closes pool.

Config properties:
- `casehub.mindmap.sqlite.path` — database file path (`:memory:` for tests)
- `casehub.mindmap.sqlite.pool.max-size` — default 5
- `casehub.mindmap.sqlite.busy-timeout-ms` — default 5000

Implement these methods first:
- `registerVocabulary()` — in-memory canonical/alias maps (same as InMemoryMindMapStore)
- `createSubgraph()`, `getSubgraph()`, `updateSubgraph()`
- `addNode()`, `getNode()`, `updateNode()`
- `capabilities()` — return `EnumSet.allOf(MindMapCapability.class)`

JSON serialization for traits (`Set<String>` → JSON array), refs (`Set<NodeRef>` → JSON array of objects), and properties (`Map<String,String>` → JSON object). Use Jackson `ObjectMapper`.

- [ ] **Step 5: Implement edge + alias + traversal + search methods**

- `addEdge()`, `getEdge()`, `removeEdge()` — vocabulary resolution same as in-memory
- `addAlias()`, `removeAlias()`, `resolveNode()` — aliases stored lowercase in `mindmap_alias`
- `neighbors()` (both overloads) — query edges by source or target
- `bridgeEdges()` — subquery for nodes in subgraph, then edges crossing boundary
- `search()` — build dynamic WHERE clause from `MindMapQuery` fields; FTS5 for text search
- `nodesIn()` — filter by subgraph_id, exclude superseded

- [ ] **Step 6: Implement merge + supersession + erasure methods**

- `mergeNodes()` — transaction: repoint edges, deduplicate, union aliases/traits/refs/properties, remove source node. Property conflict resolution by `updated_at`.
- `supersede()`, `reinstate()`, `getSupersessionStatus()`
- `eraseNode()` — delete node + cascading edges + aliases. Return count.
- `eraseSubgraph()` — delete all nodes in subgraph + subgraph itself
- `eraseEntity()` — find by name (case-insensitive) OR alias, then erase each
- `eraseEntityAcrossTenants()` — iterate tenantIds, call eraseEntity per tenant

- [ ] **Step 7: Create test class + run all 72 contract tests**

```java
package io.casehub.neocortex.mindmap.sqlite;

import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.testing.MindMapStoreContractTest;

class SqliteMindMapStoreTest extends MindMapStoreContractTest {

    @Override
    protected MindMapStore createStore() {
        SqliteMindMapStore store = new SqliteMindMapStore();
        store.path = ":memory:";
        store.maxPoolSize = 1;
        store.busyTimeoutMs = 5000;
        store.init();
        return store;
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-sqlite`
Expected: all 72 tests pass.

- [ ] **Step 8: Add SQLite-specific FTS test**

Add a test for FTS5 text search via `search()` with a text query — verify it matches node names and property values, not just substring contains.

- [ ] **Step 9: Update CLAUDE.md**

Add `mindmap-sqlite/` to Module Structure section. Add Maven coordinate row. Add root Java package entry.

- [ ] **Step 10: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-sqlite/ pom.xml CLAUDE.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#214): mindmap-sqlite — SQLite backend for MindMapStore SPI

Refs #214"
```

## References

- `specs/mindmap-spi/2026-08-26-mindmap-spi-design.md` §6.2 — SQLite backend schema
- `memory-sqlite/src/main/java/.../SqliteMemoryStore.java` — reference SQLite pattern
- `memory-sqlite/src/main/resources/db/memory-sqlite/migration/V1__memory_sqlite_entry.sql` — reference migration
- `mindmap-inmem/src/main/java/.../InMemoryMindMapStore.java` — reference implementation
- `mindmap-testing/src/main/java/.../MindMapStoreContractTest.java` — 72 contract tests
- GitHub #214 — tracking issue
