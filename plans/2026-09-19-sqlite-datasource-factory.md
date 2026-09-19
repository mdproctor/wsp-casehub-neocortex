# SqliteDataSourceFactory Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #358 — refactor: extract shared SQLite infrastructure — SqliteDataSourceFactory
**Issue group:** #358

**Goal:** Extract duplicated SQLite init code (WAL, HikariCP, Flyway) from 5 stores into a shared `sqlite-support` utility module.

**Architecture:** New `sqlite-support` module with a `SqliteDataSourceFactory` static utility class. Each store replaces ~20 lines of init with 2 lines. Factory handles `:memory:` detection, SQLiteConfig, HikariConfig, and DataSource creation. Flyway migration is a separate `migrate()` call since each store has its own migration location.

**Tech Stack:** Java 21, SQLite JDBC, HikariCP, Flyway, JUnit 5

## Global Constraints

- Java 21 source level, Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`
- Use `mvn` not `./mvnw`
- Commits reference issue: `Refs #358`
- Parent pom: `casehub-neocortex-parent` version `0.2-SNAPSHOT`

---

## Batch 1: Create sqlite-support module + migrate all 5 stores

### Task 1: Create `sqlite-support` module with `SqliteDataSourceFactory` + unit test

**Files:**
- Create: `sqlite-support/pom.xml`
- Create: `sqlite-support/src/main/java/io/casehub/neocortex/sqlite/SqliteDataSourceFactory.java`
- Create: `sqlite-support/src/test/java/io/casehub/neocortex/sqlite/SqliteDataSourceFactoryTest.java`
- Create: `sqlite-support/src/test/resources/db/test/migration/V1__create_test_table.sql`
- Modify: `pom.xml` (root) — add `sqlite-support` to `<modules>`

**Interfaces:**
- Produces: `SqliteDataSourceFactory.create(String path, int maxPoolSize, int busyTimeoutMs)` returning `HikariDataSource`
- Produces: `SqliteDataSourceFactory.create(String path, int maxPoolSize, int busyTimeoutMs, int cacheSize)` returning `HikariDataSource`
- Produces: `SqliteDataSourceFactory.migrate(HikariDataSource ds, String flywayLocation)` returning void

- [ ] **Step 1: Create module pom.xml**

Create `sqlite-support/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>0.2-SNAPSHOT</version>
    </parent>

    <artifactId>casehub-neocortex-sqlite-support</artifactId>
    <packaging>jar</packaging>
    <name>CaseHub Neocortex - SQLite Support</name>
    <description>Shared SQLite infrastructure: HikariCP DataSource factory with WAL mode,
        Flyway migration, and :memory: detection. Used by all SQLite-backed stores.</description>

    <dependencies>
        <dependency>
            <groupId>org.xerial</groupId>
            <artifactId>sqlite-jdbc</artifactId>
        </dependency>
        <dependency>
            <groupId>com.zaxxer</groupId>
            <artifactId>HikariCP</artifactId>
        </dependency>
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-core</artifactId>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.assertj</groupId>
            <artifactId>assertj-core</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 2: Add module to root pom.xml**

In the root `pom.xml`, add `<module>sqlite-support</module>` after the `corpus` module (around line 46) in the default modules section.

- [ ] **Step 3: Write the failing test**

Create `sqlite-support/src/test/resources/db/test/migration/V1__create_test_table.sql`:

```sql
CREATE TABLE test_table (
    id TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

Create `sqlite-support/src/test/java/io/casehub/neocortex/sqlite/SqliteDataSourceFactoryTest.java`:

```java
package io.casehub.neocortex.sqlite;

import com.zaxxer.hikari.HikariDataSource;
import org.junit.jupiter.api.Test;

import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;

import static org.assertj.core.api.Assertions.assertThat;

class SqliteDataSourceFactoryTest {

    @Test
    void create_inMemory_returnsWorkingDataSource() throws Exception {
        try (HikariDataSource ds = SqliteDataSourceFactory.create(":memory:", 1, 5000)) {
            try (Connection conn = ds.getConnection();
                 Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery("SELECT 1")) {
                assertThat(rs.next()).isTrue();
                assertThat(rs.getInt(1)).isEqualTo(1);
            }
        }
    }

    @Test
    void create_blankPath_treatedAsMemory() throws Exception {
        try (HikariDataSource ds = SqliteDataSourceFactory.create("", 5, 5000)) {
            assertThat(ds.getMaximumPoolSize()).isEqualTo(1);
        }
    }

    @Test
    void create_nullPath_treatedAsMemory() throws Exception {
        try (HikariDataSource ds = SqliteDataSourceFactory.create(null, 5, 5000)) {
            assertThat(ds.getMaximumPoolSize()).isEqualTo(1);
        }
    }

    @Test
    void create_withCacheSize_setsCache() throws Exception {
        try (HikariDataSource ds = SqliteDataSourceFactory.create(":memory:", 1, 5000, 64000)) {
            try (Connection conn = ds.getConnection();
                 Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery("PRAGMA cache_size")) {
                assertThat(rs.next()).isTrue();
                assertThat(rs.getInt(1)).isEqualTo(64000);
            }
        }
    }

    @Test
    void migrate_runsFlywayMigration() throws Exception {
        try (HikariDataSource ds = SqliteDataSourceFactory.create(":memory:", 1, 5000)) {
            SqliteDataSourceFactory.migrate(ds, "classpath:db/test/migration");

            try (Connection conn = ds.getConnection();
                 Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery(
                     "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'")) {
                assertThat(rs.next()).isTrue();
            }
        }
    }
}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl sqlite-support`

Expected: compilation error — `SqliteDataSourceFactory` does not exist.

- [ ] **Step 5: Write the implementation**

Create `sqlite-support/src/main/java/io/casehub/neocortex/sqlite/SqliteDataSourceFactory.java`:

```java
package io.casehub.neocortex.sqlite;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.flywaydb.core.Flyway;
import org.sqlite.SQLiteConfig;
import org.sqlite.SQLiteDataSource;

public final class SqliteDataSourceFactory {

    private SqliteDataSourceFactory() {}

    public static HikariDataSource create(String path, int maxPoolSize, int busyTimeoutMs) {
        return create(path, maxPoolSize, busyTimeoutMs, -1);
    }

    public static HikariDataSource create(String path, int maxPoolSize,
                                           int busyTimeoutMs, int cacheSize) {
        boolean isMemory = ":memory:".equals(path) || path == null || path.isBlank();
        int effectivePoolSize = isMemory ? 1 : maxPoolSize;

        SQLiteConfig sqLiteConfig = new SQLiteConfig();
        if (!isMemory) {
            sqLiteConfig.setJournalMode(SQLiteConfig.JournalMode.WAL);
        }
        sqLiteConfig.setSynchronous(SQLiteConfig.SynchronousMode.NORMAL);
        sqLiteConfig.setBusyTimeout(busyTimeoutMs);
        if (cacheSize > 0) {
            sqLiteConfig.setCacheSize(cacheSize);
        }

        SQLiteDataSource sqLiteDataSource = new SQLiteDataSource(sqLiteConfig);
        sqLiteDataSource.setUrl("jdbc:sqlite:" + (isMemory ? ":memory:" : path));

        HikariConfig hikari = new HikariConfig();
        hikari.setDataSource(sqLiteDataSource);
        hikari.setMaximumPoolSize(effectivePoolSize);
        hikari.setMinimumIdle(1);

        return new HikariDataSource(hikari);
    }

    public static void migrate(HikariDataSource ds, String flywayLocation) {
        Flyway.configure()
            .dataSource(ds)
            .locations(flywayLocation)
            .load()
            .migrate();
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl sqlite-support`

Expected: 5 tests pass.

- [ ] **Step 7: Install sqlite-support to local repo**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl sqlite-support -DskipTests`

- [ ] **Step 8: Commit**

```bash
git -C "$PROJECT" add sqlite-support/ pom.xml
git -C "$PROJECT" commit -m "feat(sqlite-support): SqliteDataSourceFactory — shared HikariCP + Flyway init

Static factory with create(path, poolSize, timeout) and create(path, poolSize,
timeout, cacheSize) overloads. migrate(ds, location) for Flyway. Handles
:memory: detection, WAL mode, NORMAL sync.

Refs #358"
```

### Task 2: Migrate all 5 stores to use SqliteDataSourceFactory

**Files:**
- Modify: `mindmap-sqlite/pom.xml` — add `sqlite-support` dependency
- Modify: `mindmap-sqlite/src/main/java/io/casehub/neocortex/mindmap/sqlite/SqliteMindMapStore.java` — replace init block
- Modify: `memory-sqlite/pom.xml` — add `sqlite-support` dependency
- Modify: `memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java` — replace init block
- Modify: `rag-tracking/pom.xml` — add `sqlite-support` dependency
- Modify: `rag-tracking/src/main/java/io/casehub/neocortex/rag/tracking/SqliteRetrievalTracker.java` — replace init block
- Modify: `memory-cbr-tracking/pom.xml` — add `sqlite-support` dependency
- Modify: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/SqliteCbrRetrievalTracker.java` — replace init block
- Modify: `cognitive-observability-sqlite/pom.xml` — add `sqlite-support` dependency
- Modify: `cognitive-observability-sqlite/src/main/java/io/casehub/neocortex/cognitive/observability/sqlite/SqliteSnapshotStore.java` — replace init block

**Interfaces:**
- Consumes: `SqliteDataSourceFactory.create(...)`, `SqliteDataSourceFactory.migrate(...)`

- [ ] **Step 1: Add sqlite-support dependency to all 5 store pom.xml files**

For each of `mindmap-sqlite/pom.xml`, `memory-sqlite/pom.xml`, `rag-tracking/pom.xml`, `memory-cbr-tracking/pom.xml`, `cognitive-observability-sqlite/pom.xml`, add:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-sqlite-support</artifactId>
    <version>${project.version}</version>
</dependency>
```

Remove the direct `sqlite-jdbc`, `HikariCP`, and `flyway-core` dependencies from each — they come transitively from `sqlite-support` now. Keep any other dependencies (jackson, quarkus, etc.) as-is.

- [ ] **Step 2: Migrate SqliteMindMapStore**

Replace the `init()` body (lines 80-107 in SqliteMindMapStore.java) with:

```java
dataSource = SqliteDataSourceFactory.create(path, maxPoolSize, busyTimeoutMs, 64000);
SqliteDataSourceFactory.migrate(dataSource, "classpath:db/mindmap-sqlite/migration");
```

Add import: `import io.casehub.neocortex.sqlite.SqliteDataSourceFactory;`

Remove now-unused imports: `org.sqlite.SQLiteConfig`, `org.sqlite.SQLiteDataSource`, `com.zaxxer.hikari.HikariConfig`, `org.flywaydb.core.Flyway`. Keep `com.zaxxer.hikari.HikariDataSource` (used for the field type and @PreDestroy).

- [ ] **Step 3: Migrate SqliteMemoryStore**

Same pattern as SqliteMindMapStore — replace `init()` body with:

```java
dataSource = SqliteDataSourceFactory.create(path, maxPoolSize, busyTimeoutMs, 64000);
SqliteDataSourceFactory.migrate(dataSource, "classpath:db/memory-sqlite/migration");
```

Add import, remove unused imports.

- [ ] **Step 4: Migrate SqliteRetrievalTracker**

Same pattern — replace `init()` body with:

```java
dataSource = SqliteDataSourceFactory.create(path, maxPoolSize, busyTimeoutMs, 64000);
SqliteDataSourceFactory.migrate(dataSource, "classpath:db/rag-tracking/migration");
```

Add import, remove unused imports.

- [ ] **Step 5: Migrate SqliteCbrRetrievalTracker**

Replace `initDataSource(String path, int poolSize, int busyTimeoutMs)` body (lines 65-84) with:

```java
dataSource = SqliteDataSourceFactory.create(path, poolSize, busyTimeoutMs);
```

Replace `init()` Flyway section with:

```java
if (dataSource == null) return;
SqliteDataSourceFactory.migrate(dataSource, "classpath:db/cbr-tracking/migration");
```

Add import, remove unused imports.

- [ ] **Step 6: Migrate SqliteSnapshotStore**

Replace the constructor's DataSource setup (lines 33-50) with:

```java
this.dataSource = SqliteDataSourceFactory.create(path, 3, 5000);
SqliteDataSourceFactory.migrate(dataSource, "classpath:db/observability");
```

The `poolName` was previously set — this is the only store that used it. It's cosmetic and not worth preserving.

Add import, remove unused imports (`org.sqlite.SQLiteConfig`, `org.sqlite.SQLiteDataSource`, `com.zaxxer.hikari.HikariConfig`, `org.flywaydb.core.Flyway`). Keep `com.zaxxer.hikari.HikariDataSource`.

- [ ] **Step 7: Run all affected store tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl sqlite-support,mindmap-sqlite,memory-sqlite,rag-tracking,memory-cbr-tracking,cognitive-observability-sqlite`

Expected: all tests pass — the factory produces identical DataSources, so all existing store tests verify the migration is correct.

- [ ] **Step 8: Commit**

```bash
git -C "$PROJECT" add mindmap-sqlite/ memory-sqlite/ rag-tracking/ memory-cbr-tracking/ cognitive-observability-sqlite/
git -C "$PROJECT" commit -m "refactor: migrate 5 SQLite stores to SqliteDataSourceFactory

Each store's ~20-line init block replaced with 2 lines: create() + migrate().
Direct sqlite-jdbc, HikariCP, flyway-core dependencies replaced with
sqlite-support transitive dependency.

Closes #358"
```

## References

- [specs/issue-358-sqlite-datasource-factory/2026-09-19-sqlite-datasource-factory-design.md] — design spec
- [SqliteMindMapStore.java:79-107] — representative init pattern (3 identical stores)
- [SqliteCbrRetrievalTracker.java:60-85] — config-interface variant
- [SqliteSnapshotStore.java:33-61] — plain-class variant
- [mindmap-sqlite/pom.xml] — dependency pattern reference
- [GitHub #358] — focal issue
- [GitHub #355] — parent GA audit epic
