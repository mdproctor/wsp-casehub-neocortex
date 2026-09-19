# SQLite DataSource Factory — Extract Shared Infrastructure

**Issue:** casehubio/neocortex#358
**Parent:** casehubio/neocortex#355 (GA audit)
**Date:** 2026-09-19

## Problem

SQLite init is duplicated across 5 stores (~20 lines each): SqliteMindMapStore,
SqliteMemoryStore, SqliteRetrievalTracker, SqliteCbrRetrievalTracker,
SqliteSnapshotStore. Each repeats: `:memory:` detection, SQLiteConfig WAL/sync/
timeout setup, HikariConfig pool sizing, HikariDataSource construction, Flyway
migration, @PreDestroy close.

Minor variations: pool name (1 store), cache size (3 set 64000, 2 omit).

## Design

### New Module: `sqlite-support`

**Artifact:** `casehub-neocortex-sqlite-support`
**Package:** `io.casehub.neocortex.sqlite`
**Dependencies:** `sqlite-jdbc`, `HikariCP`, `flyway-core`
**Tier:** Tier 1 (pure Java utility, no CDI, no Quarkus)

### API

```java
public final class SqliteDataSourceFactory {

    private SqliteDataSourceFactory() {}

    public static HikariDataSource create(String path, int maxPoolSize,
                                           int busyTimeoutMs) {
        return create(path, maxPoolSize, busyTimeoutMs, -1);
    }

    public static HikariDataSource create(String path, int maxPoolSize,
                                           int busyTimeoutMs, int cacheSize) {
        // :memory: detection: ":memory:".equals(path) || path == null || path.isBlank()
        // SQLiteDataSource config: WAL mode (non-memory), NORMAL sync, busyTimeout
        // Optional: setCacheSize if cacheSize > 0
        // HikariConfig: setDataSource, setMaximumPoolSize
        // Return new HikariDataSource(config)
    }

    public static void migrate(HikariDataSource ds, String flywayLocation) {
        // Flyway.configure().dataSource(ds).locations(flywayLocation).load().migrate()
    }
}
```

### Store Migration

Each store's init reduces to 2-3 lines:

```java
// Before: ~20 lines of SQLiteConfig + HikariConfig + Flyway
// After:
this.dataSource = SqliteDataSourceFactory.create(path, 5, 5000, 64000);
SqliteDataSourceFactory.migrate(dataSource, "db/mindmap-sqlite/migration");
```

| Store | Call |
|-------|------|
| SqliteMindMapStore | `create(path, 5, 5000, 64000)` + `migrate(ds, "db/mindmap-sqlite/migration")` |
| SqliteMemoryStore | `create(path, 5, 5000, 64000)` + `migrate(ds, "db/memory-sqlite/migration")` |
| SqliteRetrievalTracker | `create(path, 5, 5000, 64000)` + `migrate(ds, "db/rag-tracking/migration")` |
| SqliteCbrRetrievalTracker | `create(path, poolSize, timeout)` + `migrate(ds, "db/cbr-tracking/migration")` |
| SqliteSnapshotStore | `create(path, 3, 5000)` + `migrate(ds, "db/observability")` |

### Module Dependencies

Each existing SQLite module replaces its direct `sqlite-jdbc` + `HikariCP`
dependencies with a single dependency on `sqlite-support`. Flyway stays as
a direct dependency (each module owns its own migration scripts).

Actually — Flyway is also duplicated. `sqlite-support` should declare
`flyway-core` as a compile dependency. Stores that use `migrate()` get
Flyway transitively.

### Testing

Unit test in `sqlite-support`: create an in-memory DataSource, run a
trivial migration, verify table exists, close. Verifies the factory works
without depending on any store.

### Files Changed

- **Create:** `sqlite-support/` module with `pom.xml` and `SqliteDataSourceFactory.java`
- **Create:** `sqlite-support/src/test/` with factory unit test + trivial Flyway migration
- **Modify:** `pom.xml` (root) — add `sqlite-support` to `<modules>`
- **Modify:** 5 store classes — replace init blocks with factory calls
- **Modify:** 5 store `pom.xml` files — replace `sqlite-jdbc` + `HikariCP` with `sqlite-support`

## References

- `SqliteMindMapStore.java:63-110` — init pattern (representative of the 3 identical stores)
- `SqliteCbrRetrievalTracker.java:42-90` — config-interface variant
- `SqliteSnapshotStore.java:28-70` — plain-class variant
- `GitHub #358` — issue description with proposed API
