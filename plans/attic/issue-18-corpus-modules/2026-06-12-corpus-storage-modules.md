# Corpus Storage Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `corpus-api` (Tier 1 pure-Java SPI) and `corpus` (Zip4j implementation) modules for ZIP-backed document storage with chain integrity, versioning, composite mode, and compaction.

**Architecture:** corpus-api defines four SPIs across three planes: data (CorpusStore write + CorpusReader read), delta (ChangeSource), and ops (CorpusIntegrity). corpus implements them with Zip4j — ZipCorpusStore manages rolling ZIP archives with a chain manifest, master index, tombstone deletion, and compaction. FlatCorpusStore handles filesystem-only mode. CompositeCorpusStore wraps both with sync-then-report semantics. All SPIs have reactive (Mutiny Uni) mirrors with blocking-to-reactive bridges.

**Tech Stack:** Java 21, Zip4j 2.11.6, Mutiny (provided scope), JUnit 5, AssertJ, ArchUnit

**Spec:** `specs/2026-06-11-corpus-storage-module-design.md` (rev 5, approved)

---

## File Structure

### corpus-api (`io.casehub.corpus`)

```
corpus-api/pom.xml
corpus-api/src/main/java/io/casehub/corpus/
├── CorpusStore.java              — write SPI (append, delete)
├── CorpusReader.java             — read SPI (read, readVersion, versions, list, exists)
├── ChangeSource.java             — delta SPI (changesSince, fullScan)
├── CorpusIntegrity.java          — ops SPI (check, checkAndRecover, fullHashVerification)
├── ReactiveCorpusStore.java      — Uni<Void> mirrors
├── ReactiveCorpusReader.java     — Uni mirrors
├── ReactiveChangeSource.java     — Uni mirrors
├── ChangeSet.java                — record(List<ChangedEntry>, String newCursor)
├── ChangedEntry.java             — record(String path, ChangeType type)
├── ChangeType.java               — enum ADDED, MODIFIED, DELETED
├── VersionInfo.java              — record(int version, Instant timestamp, String zipFile)
├── IntegrityReport.java          — record(corpusName, chainLength, totalEntries, status, issues, recovered)
├── IntegrityIssue.java           — record(Severity severity, String zipFile, String message)
└── Severity.java                 — enum INFO, WARNING, ERROR
corpus-api/src/test/java/io/casehub/corpus/
├── DependencyConstraintTest.java — ArchUnit: zero Quarkus/LangChain4j/casehub-domain/Zip4j deps
├── BlockingReactiveParityTest.java — reflection: every blocking method has Uni mirror
├── ChangeSetTest.java
├── ChangedEntryTest.java
├── VersionInfoTest.java
├── IntegrityReportTest.java
└── IntegrityIssueTest.java
```

### corpus (`io.casehub.corpus.zip`)

```
corpus/pom.xml
corpus/src/main/java/io/casehub/corpus/zip/
├── CorpusConfig.java             — record(Path source, StorageMode mode, long maxZipSize)
├── StorageMode.java              — enum ZIP, FLAT, COMPOSITE
├── EntryLocation.java            — record(String zipFile, int version, long timestamp)
├── MasterIndex.java              — pathIndex, history, tombstones — built from central dirs
├── ChainEntry.java               — record matching chain.json entry schema
├── ChainManifest.java            — read/write chain.json, atomic updates
├── ZipCorpusStore.java           — implements CorpusStore + CorpusReader, owns MasterIndex + ChainManifest
├── ZipChangeSource.java          — implements ChangeSource, cursor = "seq:offset"
├── ZipIntegrityChecker.java      — implements CorpusIntegrity
├── Compactor.java                — TOMBSTONES_ONLY + FULL compaction
├── FlatCorpusStore.java          — implements CorpusStore + CorpusReader
├── FlatChangeSource.java         — implements ChangeSource for flat files
├── CompositeCorpusStore.java     — wraps ZipCorpusStore + FlatCorpusStore
├── CompositeChangeSource.java    — sync-then-report
├── CorpusMigrator.java           — migrate(Path sourceDir, CorpusStore target)
├── BlockingToReactiveCorpusStoreBridge.java
├── BlockingToReactiveCorpusReaderBridge.java
└── BlockingToReactiveChangeSourceBridge.java
corpus/src/test/java/io/casehub/corpus/zip/
├── ZipCorpusStoreTest.java       — append, read, delete, list, versions, path validation
├── ZipCorpusStoreRolloverTest.java — rolling ZIP, size threshold, chain manifest
├── ZipChangeSourceTest.java
├── ZipIntegrityCheckerTest.java
├── CompactorTest.java
├── FlatCorpusStoreTest.java
├── FlatChangeSourceTest.java
├── CompositeCorpusStoreTest.java
├── CompositeChangeSourceTest.java
├── CorpusMigratorTest.java
├── ChainManifestTest.java
├── MasterIndexTest.java
└── BlockingToReactiveBridgeTest.java
```

### Parent pom.xml changes

- Add `<module>corpus-api</module>` and `<module>corpus</module>` to `<modules>`
- Add `casehub-corpus-api` and `casehub-corpus` to `<dependencyManagement>`
- Add `zip4j.version` property

---

## Task 1: Module scaffolding

**Files:**
- Create: `corpus-api/pom.xml`
- Create: `corpus/pom.xml`
- Modify: `pom.xml` (parent — modules + dependencyManagement)

- [ ] **Step 1: Create corpus-api/pom.xml**

Follow inference-api pattern: parent ref, zero deps except Mutiny (provided), JUnit/AssertJ/ArchUnit (test).

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>

  <artifactId>casehub-corpus-api</artifactId>
  <name>CaseHub Neural Text - Corpus API</name>
  <description>CorpusStore, CorpusReader, and ChangeSource SPIs — pure Java, zero deps. Hortora-eligible.</description>

  <dependencies>
    <dependency>
      <groupId>io.smallrye.reactive</groupId>
      <artifactId>mutiny</artifactId>
      <scope>provided</scope>
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
    <dependency>
      <groupId>com.tngtech.archunit</groupId>
      <artifactId>archunit-junit5</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 2: Create corpus/pom.xml**

Depends on corpus-api + zip4j.

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>

  <artifactId>casehub-corpus</artifactId>
  <name>CaseHub Neural Text - Corpus</name>
  <description>ZIP-backed document storage with chain integrity, versioning, composite mode, and compaction. Hortora-eligible.</description>

  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-corpus-api</artifactId>
    </dependency>

    <dependency>
      <groupId>net.lingala.zip4j</groupId>
      <artifactId>zip4j</artifactId>
    </dependency>

    <dependency>
      <groupId>io.smallrye.reactive</groupId>
      <artifactId>mutiny</artifactId>
      <scope>provided</scope>
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

- [ ] **Step 3: Update parent pom.xml**

Add `zip4j.version` property, add both modules, add both artifacts + zip4j to dependencyManagement.

- [ ] **Step 4: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl corpus-api,corpus -am -q`

- [ ] **Step 5: Commit**

```
feat(#18): scaffold corpus-api and corpus modules
```

---

## Task 2: corpus-api value types and enums

**Files:**
- Create: `corpus-api/src/main/java/io/casehub/corpus/ChangeType.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/Severity.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/ChangedEntry.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/ChangeSet.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/VersionInfo.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/IntegrityIssue.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/IntegrityReport.java`
- Create: tests for each

Pattern: follow `CorpusRef` and `ChunkInput` from rag-api — compact records with validation in the compact constructor.

- [ ] **Step 1: Write tests for value types**

Test each record's constructor validation (null/blank rejection), immutability (defensive copy of lists/maps), and enum coverage.

- [ ] **Step 2: Run tests — verify RED**

- [ ] **Step 3: Implement value types**

Key design points:
- `ChangeSet`: defensive copy `List.copyOf(entries)` in compact constructor
- `ChangedEntry`: validate path non-null/non-blank
- `VersionInfo`: validate version >= 1, timestamp non-null
- `IntegrityReport`: defensive copy of issues and recovered lists
- `IntegrityIssue`: validate severity non-null, message non-null

- [ ] **Step 4: Run tests — verify GREEN**

- [ ] **Step 5: Commit**

```
feat(#18): corpus-api value types and enums
```

---

## Task 3: corpus-api blocking SPI interfaces

**Files:**
- Create: `corpus-api/src/main/java/io/casehub/corpus/CorpusStore.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/CorpusReader.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/ChangeSource.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/CorpusIntegrity.java`

These are pure interfaces — no tests needed beyond the ArchUnit and parity tests in Task 4.

- [ ] **Step 1: Write CorpusStore interface**

```java
package io.casehub.corpus;

import java.io.InputStream;
import java.nio.file.Path;

public interface CorpusStore {
    void append(String path, byte[] content);
    void append(String path, InputStream content);
    void append(String path, Path file);
    void delete(String path);
}
```

- [ ] **Step 2: Write CorpusReader interface**

```java
package io.casehub.corpus;

import java.io.InputStream;
import java.util.List;
import java.util.Optional;

public interface CorpusReader {
    Optional<byte[]> read(String path);
    Optional<InputStream> readStream(String path);
    Optional<byte[]> readVersion(String path, int version);
    List<VersionInfo> versions(String path);
    List<String> list();
    List<String> list(String prefix);
    boolean exists(String path);
}
```

- [ ] **Step 3: Write ChangeSource and CorpusIntegrity interfaces**

Per spec. ChangeSource returns ChangeSet; CorpusIntegrity returns IntegrityReport.

- [ ] **Step 4: Verify compilation**

- [ ] **Step 5: Commit**

```
feat(#18): corpus-api blocking SPI interfaces
```

---

## Task 4: corpus-api reactive SPIs + architectural tests

**Files:**
- Create: `corpus-api/src/main/java/io/casehub/corpus/ReactiveCorpusStore.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/ReactiveCorpusReader.java`
- Create: `corpus-api/src/main/java/io/casehub/corpus/ReactiveChangeSource.java`
- Create: `corpus-api/src/test/java/io/casehub/corpus/DependencyConstraintTest.java`
- Create: `corpus-api/src/test/java/io/casehub/corpus/BlockingReactiveParityTest.java`

- [ ] **Step 1: Write DependencyConstraintTest**

Follow inference-api/rag-api pattern. Assert zero deps on: Quarkus, Jakarta, LangChain4j, Qdrant, Zip4j, casehub-domain (anything io.casehub.* outside io.casehub.corpus).

- [ ] **Step 2: Write BlockingReactiveParityTest**

Follow rag-api pattern exactly. Pairs: `CorpusStore/ReactiveCorpusStore`, `CorpusReader/ReactiveCorpusReader`, `ChangeSource/ReactiveChangeSource`. No parity test for `CorpusIntegrity` — ops plane has no reactive variant (explicit admin action only, never on event loop).

- [ ] **Step 3: Run tests — verify RED** (reactive interfaces don't exist yet)

- [ ] **Step 4: Implement reactive interfaces**

Each method returns `Uni<T>` wrapping the blocking return type (`void` → `Uni<Void>`). Same parameters.

- [ ] **Step 5: Run all corpus-api tests — verify GREEN**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-api -am`

- [ ] **Step 6: Commit**

```
feat(#18): corpus-api reactive SPIs and architectural tests
```

---

## Task 5: ChainManifest + MasterIndex internals

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/ChainEntry.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/ChainManifest.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/EntryLocation.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/MasterIndex.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/ChainManifestTest.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/MasterIndexTest.java`

These are the internal data structures that ZipCorpusStore depends on. Test them independently first.

- [ ] **Step 1: Write ChainManifestTest**

Tests: write and read chain.json round-trip, atomic update (temp+rename), add entry, close entry, compaction replacement (old UUID → new UUID with replacedBy), schema version.

- [ ] **Step 2: Write MasterIndexTest**

Tests: add entry, add version (same path → version increments), tombstone, list (excludes tombstoned), exists, versions (ordered), rebuild from entries.

- [ ] **Step 3: Run — verify RED**

- [ ] **Step 4: Implement ChainEntry record**

```java
package io.casehub.corpus.zip;

import java.time.LocalDate;
import java.util.Map;

public record ChainEntry(
    String uuid,
    String file,
    int sequence,
    String status,       // "active", "closed", "sealed", "compacted"
    String predecessor,
    int entryCount,
    int cumulativeEntryCount,
    String contentHash,
    Map<String, Integer> domains,
    LocalDate earliest,
    LocalDate latest,
    String replacedBy     // null unless compacted
) {}
```

- [ ] **Step 5: Implement ChainManifest**

JSON serialization using `java.io` and manual JSON writing (no Jackson dep — keep Hortora-eligible). Atomic file write via temp + `Files.move(ATOMIC_MOVE)`. Methods: `load(Path)`, `save(Path)`, `addEntry(ChainEntry)`, `closeEntry(String uuid, String contentHash)`, `retireEntry(String oldUuid, String newUuid)`, `activeEntry()`, `entries()`.

**Design decision:** Use a simple JSON writer (StringBuilder-based) rather than adding a JSON library. The chain.json schema is fixed and small. This keeps the module at zero deps beyond Zip4j. If the schema grows complex enough to warrant a library, add it then.

- [ ] **Step 6: Implement EntryLocation and MasterIndex**

`EntryLocation(String zipFile, int version, long timestamp)`. MasterIndex holds `Map<String, EntryLocation> current`, `Map<String, List<EntryLocation>> history`, `Set<String> tombstones`. Methods: `put(path, location)`, `tombstone(path)`, `get(path)`, `versions(path)`, `list()`, `list(prefix)`, `exists(path)`, `clear()`.

- [ ] **Step 7: Run — verify GREEN**

- [ ] **Step 8: Commit**

```
feat(#18): ChainManifest and MasterIndex internals
```

---

## Task 6: ZipCorpusStore — append, read, delete, list, versions

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/CorpusConfig.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/StorageMode.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/ZipCorpusStore.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/ZipCorpusStoreTest.java`

This is the core task. ZipCorpusStore implements both `CorpusStore` and `CorpusReader`.

- [ ] **Step 1: Write ZipCorpusStoreTest — basic append and read**

Test: append a document, read it back, verify content matches. Use `@TempDir` for the corpus directory.

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement StorageMode enum and CorpusConfig record**

`CorpusConfig(String corpusName, Path source, StorageMode mode, long maxZipSize)` with sensible defaults (maxZipSize = 100MB).

- [ ] **Step 4: Implement ZipCorpusStore skeleton**

Constructor takes `CorpusConfig`. Creates the source directory if absent. Initializes ChainManifest and MasterIndex. Creates the first active ZIP if none exists. `append()` writes to active ZIP via Zip4j, updates MasterIndex. `read()` reads from ZIP central directory using master index location.

Key Zip4j operations:
- `new ZipFile(path)` — open/create
- `zipFile.addStream(inputStream, zipParameters)` — append entry
- `zipFile.getInputStream(fileHeader)` — read entry

- [ ] **Step 5: Run — verify GREEN for basic append/read**

- [ ] **Step 6: Write tests for path validation, delete (tombstone), list, versions, exists**

- Path validation: `_chain/foo` → IllegalArgumentException
- Delete: append then delete, verify `exists()` returns false, `list()` excludes it
- List: append multiple, verify list returns all non-tombstoned
- List with prefix: `list("tools/")` returns only paths starting with `tools/`
- Versions: append same path twice, verify `versions()` returns [1, 2], `readVersion(path, 1)` returns first content

- [ ] **Step 7: Run — verify RED**

- [ ] **Step 8: Implement delete, list, versions, path validation**

`delete(path)` creates a marker entry at `_tombstones/<path>.deleted` in the active ZIP and adds to MasterIndex tombstone set. `list()` returns all paths from MasterIndex excluding tombstones. `versions(path)` returns from MasterIndex history. `readVersion()` reads from the specific ZIP/offset indicated by the version's EntryLocation.

Path validation: check `path.startsWith("_")` in append and throw IAE.

- [ ] **Step 9: Run — verify GREEN**

- [ ] **Step 10: Write tests for readStream() and append(Path file) overloads**

- [ ] **Step 11: Implement stream/file overloads**

- [ ] **Step 12: Run — verify GREEN**

- [ ] **Step 13: Commit**

```
feat(#18): ZipCorpusStore — append, read, delete, list, versions
```

---

## Task 7: Rolling ZIPs and chain manifest integration

**Files:**
- Modify: `corpus/src/main/java/io/casehub/corpus/zip/ZipCorpusStore.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/ZipCorpusStoreRolloverTest.java`

- [ ] **Step 1: Write rollover tests**

- Append entries until exceeding maxZipSize threshold → verify a new ZIP is created
- Verify chain.json lists both ZIPs with correct sequence numbers
- Verify closed ZIP has `_chain/meta.json` inside
- Verify reads work across multiple ZIPs
- Verify versions spanning multiple ZIPs are correctly numbered
- Verify startup rebuilds index from existing ZIPs + chain.json

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement rollover in ZipCorpusStore**

After each `append()`, check active ZIP size against `maxZipSize`. If exceeded:
1. Close active ZIP (write `_chain/meta.json`, compute content hash)
2. Update chain.json atomically (via ChainManifest)
3. Create new active ZIP
4. MasterIndex remains valid — entries point to specific ZIP files

Startup:
1. Load chain.json if exists
2. Scan each ZIP's central directory, build MasterIndex
3. Identify active ZIP (last in chain without `_chain/meta.json`, or create new if all closed)

- [ ] **Step 4: Run — verify GREEN**

- [ ] **Step 5: Commit**

```
feat(#18): rolling ZIP archives with chain manifest
```

---

## Task 8: ZipChangeSource

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/ZipChangeSource.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/ZipChangeSourceTest.java`

- [ ] **Step 1: Write ZipChangeSourceTest**

Tests:
- `fullScan()` returns all non-tombstoned entries as ADDED
- `changesSince(null)` equivalent to fullScan
- Append entries, get cursor from changesSince, append more, verify only new entries returned
- Delete entry, verify DELETED in changesSince
- Modify entry (append same path again), verify MODIFIED in changesSince

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement ZipChangeSource**

Cursor format: `"<sequence>:<entryCount>"` — the ZIP sequence number and cumulative entry count at the time of the last scan. `changesSince(cursor)` scans ZIP entries appended after the cursor position. `fullScan()` returns all current paths (from MasterIndex) as ADDED.

ZipChangeSource takes ZipCorpusStore (or its MasterIndex + chain) as a constructor dependency — it reads index state, doesn't duplicate it.

- [ ] **Step 4: Run — verify GREEN**

- [ ] **Step 5: Commit**

```
feat(#18): ZipChangeSource — delta tracking with cursor
```

---

## Task 9: ZipIntegrityChecker

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/ZipIntegrityChecker.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/ZipIntegrityCheckerTest.java`

- [ ] **Step 1: Write ZipIntegrityCheckerTest**

Tests for each detection case from the spec:
- ZIP in directory not in chain.json → WARNING
- Entry in chain.json, ZIP missing → ERROR
- Missing `_chain/meta.json` in closed ZIP → INFO (recoverable)
- chain.json missing → WARNING (reconstructable from internal meta)
- Content hash mismatch → ERROR
- Entry count mismatch → WARNING
- `checkAndRecover()` fixes missing `_chain/meta.json`
- `check()` is read-only (no modifications)

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement ZipIntegrityChecker**

Implements `CorpusIntegrity`. Constructor takes corpus source path + ChainManifest. Each `check*()` method builds an `IntegrityReport`. `checkAndRecover()` calls `check()` first, then attempts repairs (write missing `_chain/meta.json`, reconstruct chain.json from internal meta).

- [ ] **Step 4: Run — verify GREEN**

- [ ] **Step 5: Commit**

```
feat(#18): ZipIntegrityChecker — detection and recovery
```

---

## Task 10: FlatCorpusStore + FlatChangeSource

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/FlatCorpusStore.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/FlatChangeSource.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/FlatCorpusStoreTest.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/FlatChangeSourceTest.java`

- [ ] **Step 1: Write FlatCorpusStoreTest**

Tests: append writes file to filesystem, read returns file content, delete removes file, list scans directory recursively, exists checks file presence, no versioning (single version only), path validation.

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement FlatCorpusStore**

Implements `CorpusStore` + `CorpusReader`. Straightforward filesystem operations. `append()` creates parent directories and writes file. `delete()` removes file. No ZIP, no chain, no versioning. `versions()` returns a single entry with the file's last modified time. Path maps directly to filesystem path under the source directory.

- [ ] **Step 4: Run — verify GREEN**

- [ ] **Step 5: Write FlatChangeSourceTest and implement FlatChangeSource**

Cursor is last-scan timestamp. `changesSince()` walks the filesystem and compares file modification times against cursor. Reports ADDED for new files, MODIFIED for changed files. DELETED detection requires keeping a previous file list (stored alongside cursor).

- [ ] **Step 6: Run — verify GREEN**

- [ ] **Step 7: Commit**

```
feat(#18): FlatCorpusStore and FlatChangeSource
```

---

## Task 11: CompositeCorpusStore + CompositeChangeSource

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/CompositeCorpusStore.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/CompositeChangeSource.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/CompositeCorpusStoreTest.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/CompositeChangeSourceTest.java`

- [ ] **Step 1: Write CompositeCorpusStoreTest**

Tests:
- SPI append fans out to both ZIP and flat
- Reads come from ZIP (authoritative)
- External flat file write (simulating forage) is visible after next changesSince

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement CompositeCorpusStore**

Wraps `ZipCorpusStore` + `FlatCorpusStore`. `append()` writes to both. `read()` delegates to ZipCorpusStore (authoritative). `delete()` deletes from both. `list()` from ZipCorpusStore.

- [ ] **Step 4: Run — verify GREEN**

- [ ] **Step 5: Write CompositeChangeSourceTest**

Tests:
- Externally written flat file detected and synced to ZIP before reporting
- After sync, CorpusReader finds the synced content in ZIP
- Modified flat file detected and re-synced
- Deleted flat file (if applicable)

- [ ] **Step 6: Implement CompositeChangeSource**

`changesSince()`: 1) Scan flat dir for new/modified files not yet in ZIP, 2) Sync them into ZipCorpusStore internals (direct write, not via public SPI), 3) Scan ZIP state post-sync, report changes. The sync is the key complexity — `CompositeChangeSource` has package-private access to ZipCorpusStore's append internals.

- [ ] **Step 7: Run — verify GREEN**

- [ ] **Step 8: Commit**

```
feat(#18): CompositeCorpusStore with sync-then-report
```

---

## Task 12: Compaction

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/Compactor.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/CompactorTest.java`

- [ ] **Step 1: Write CompactorTest**

Tests:
- TOMBSTONES_ONLY: tombstoned entries removed, old versions preserved, new UUID in chain.json
- FULL: tombstoned entries removed AND old versions removed (only latest kept), new UUID
- Verify `readVersion()` returns empty for compacted-away versions after FULL
- Verify chain.json `replacedBy` reference from old to new UUID
- Cannot compact active ZIP (only closed)

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement Compactor**

`compact(Path zipPath, CompactionMode mode, ChainManifest manifest)`:
1. Read all entries from source ZIP
2. Filter based on mode (skip tombstones always; skip old versions in FULL mode)
3. Write to new temp ZIP
4. Compute content hash of new ZIP
5. Generate new UUID
6. Update ChainManifest: retire old UUID with replacedBy → new UUID, add new entry
7. Replace old ZIP with new (atomic rename)

`CompactionMode` enum: `TOMBSTONES_ONLY`, `FULL`.

- [ ] **Step 4: Run — verify GREEN**

- [ ] **Step 5: Commit**

```
feat(#18): compaction — TOMBSTONES_ONLY and FULL modes
```

---

## Task 13: CorpusMigrator

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/CorpusMigrator.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/CorpusMigratorTest.java`

- [ ] **Step 1: Write CorpusMigratorTest**

Tests:
- Migrate a directory of .md files into a CorpusStore
- Preserves directory structure as path prefixes (`tools/GE-123.md`)
- Skips non-.md files (or make extension configurable)
- Verify all migrated files readable via CorpusReader

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement CorpusMigrator**

`migrate(Path sourceDir, CorpusStore target)`: walks `sourceDir` recursively, computes relative path for each file, calls `target.append(relativePath, file)`.

- [ ] **Step 4: Run — verify GREEN**

- [ ] **Step 5: Commit**

```
feat(#18): CorpusMigrator for garden onboarding
```

---

## Task 14: Blocking-to-reactive bridges

**Files:**
- Create: `corpus/src/main/java/io/casehub/corpus/zip/BlockingToReactiveCorpusStoreBridge.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/BlockingToReactiveCorpusReaderBridge.java`
- Create: `corpus/src/main/java/io/casehub/corpus/zip/BlockingToReactiveChangeSourceBridge.java`
- Create: `corpus/src/test/java/io/casehub/corpus/zip/BlockingToReactiveBridgeTest.java`

Follow `BlockingToReactiveRagBridge` pattern from rag module.

- [ ] **Step 1: Write BlockingToReactiveBridgeTest**

Test: call reactive method, verify it delegates to blocking impl on worker pool, verify result propagates through Uni.

- [ ] **Step 2: Run — verify RED**

- [ ] **Step 3: Implement bridges**

Each bridge wraps a blocking SPI and implements the reactive SPI. Each method: `Uni.createFrom().item(() -> blocking.method(...)).runSubscriptionOn(Infrastructure.getDefaultWorkerPool())`. Void methods use `.replaceWithVoid()`.

- [ ] **Step 4: Run — verify GREEN**

- [ ] **Step 5: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl corpus-api,corpus -am`

- [ ] **Step 6: Commit**

```
feat(#18): blocking-to-reactive bridges for corpus SPIs
```

---

## Deferred

- **ID-based lookup** — spec marks this as optional ("When configured with an id-strategy"). Path-based lookup always works. Defer to a follow-on issue if a consumer needs it.

---

## Verification

After all tasks complete:

1. **Full build:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -DskipTests` — verify all modules compile
2. **All tests:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-api,corpus -am` — all green
3. **ArchUnit:** corpus-api DependencyConstraintTest confirms zero forbidden deps
4. **Parity:** corpus-api BlockingReactiveParityTest confirms all blocking methods have reactive mirrors
5. **Existing modules:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test` — no regressions in inference-* or rag-* modules
