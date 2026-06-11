# Corpus Storage Module Design

**Date:** 2026-06-11
**Status:** Draft
**Tracks:** casehubio/neural-text (new modules: `corpus-api/`, `corpus/`, plus ingestion bridge in `rag/`)

## Problem

casehub-neural-text provides a RAG pipeline (embedding, Qdrant, hybrid search) but has no document storage layer. Consumers must manage their own document lifecycle — storage, versioning, change tracking, distribution — before feeding documents into the RAG pipeline.

The Hortora knowledge garden (~4,000 entries today, potentially millions at scale) is the first consumer. Other casehub domains (legal, clinical, compliance) have the same pattern: a corpus of text documents that need ingestion, versioning, change tracking, and semantic retrieval.

## Design Principles

1. **Corpus module has zero dependency on RAG/LangChain4j/Qdrant** — pure document storage
2. **ZIP is the primary store** — flat files are a mirror, not the source of truth
3. **Append-only** — no in-place modification, no deletes in the hot path
4. **Chain integrity** — verifiable linked sequence of ZIP archives
5. **Developer UX** — configure a corpus in properties, inject a ready-to-use service

## Module Structure

```
corpus-api/     — SPI + value types. Zero dependencies.
corpus/         — Zip4j implementation. Depends on corpus-api + zip4j.
rag/            — Ingestion bridge additions. Depends on corpus-api + existing RAG infrastructure.
```

```
Document producers (forage, harvest, etc.)
        |
   corpus-api SPI
        |
   corpus/ (Zip4j rolling ZIPs, chain manifest, integrity)
        |
   ChangeSource SPI
        |
   rag/ CorpusIngestionService (chunk -> embed -> Qdrant)
        |
   Qdrant (vectors + metadata payloads)
```

## corpus-api — SPI

### CorpusStore (write)

```java
public interface CorpusStore {
    void append(String path, byte[] content);
    void append(String path, byte[] content, Map<String, String> metadata);
}
```

### CorpusReader (read)

```java
public interface CorpusReader {
    Optional<byte[]> read(String path);
    Optional<byte[]> readVersion(String path, int version);
    List<VersionInfo> versions(String path);
    List<String> list();
    List<String> list(String domainPrefix);
    boolean exists(String path);
}
```

### ChangeSource (change tracking)

```java
public interface ChangeSource {
    ChangeSet changesSince(String cursor);
    ChangeSet fullScan();
}

public record ChangeSet(List<ChangedEntry> entries, String newCursor) {}
public record ChangedEntry(String path, ChangeType type) {}
public enum ChangeType { ADDED, MODIFIED }
```

### CorpusIntegrity (health check)

```java
public interface CorpusIntegrity {
    IntegrityReport check();
    IntegrityReport checkAndRecover();
    IntegrityReport fullHashVerification();
}
```

### Value types

```java
public record VersionInfo(int version, Instant timestamp, String zipFile) {}

public record IntegrityReport(
    String corpusName,
    int chainLength,
    long totalEntries,
    String status,
    List<IntegrityIssue> issues,
    List<String> recovered
) {}

public record IntegrityIssue(Severity severity, String zipFile, String message) {}

public enum Severity { INFO, WARNING, ERROR }
```

### Configuration

```java
public record CorpusConfig(
    String name,
    Path source,
    StorageMode mode,
    long maxZipSize,
    IngestionMode ingestion,
    Optional<IdStrategy> idStrategy
) {}

public enum StorageMode { ZIP, FLAT, COMPOSITE }
public enum IngestionMode { AUTO, MANUAL, NONE }
```

Configured via application.properties:

```properties
casehub.corpus.garden.source=/path/to/garden
casehub.corpus.garden.mode=composite
casehub.corpus.garden.max-zip-size=104857600
casehub.corpus.garden.ingestion=auto

casehub.corpus.garden.id-strategy=frontmatter
casehub.corpus.garden.id-field=id

casehub.corpus.legal.source=/path/to/legal-docs
casehub.corpus.legal.mode=zip
casehub.corpus.legal.ingestion=manual
```

### Design constraints

- No Zip4j, LangChain4j, or Qdrant dependencies in this module
- Pure Java interfaces and records
- ID-based lookup is optional (configured per corpus via `id-strategy`)
- Path-based lookup always available

## corpus — Implementation

### Dependencies

- `corpus-api`
- `net.lingala.zip4j:zip4j:2.11.6` (Apache-2.0, zero transitive deps)

### Rolling ZIP Manager

`ZipCorpusStore` implements `CorpusStore`, `CorpusReader`, `ChangeSource`, `CorpusIntegrity`.

**ZIP lifecycle:**

1. **Startup** — read `chain.json`, scan ZIP central directories, build in-memory master index
2. **Append** — write entry to active ZIP via Zip4j. Check size threshold after write.
3. **Rollover** — close active ZIP (append `_chain/meta.json` with all metadata), write new `chain.json` atomically (temp file + rename), create new active ZIP, append `_chain/successor.json` to previous ZIP
4. **Shutdown** — flush, update `chain.json`

### Chain Manifest (`chain.json`)

External file alongside the ZIPs. Atomic source of truth for chain state. Written via temp file + rename.

```json
{
  "corpus": "garden",
  "schemaVersion": 1,
  "chain": [
    {
      "uuid": "550e8400-e29b-41d4-a716-446655440000",
      "file": "garden-001.zip",
      "sequence": 0,
      "status": "closed",
      "predecessor": null,
      "successor": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "entryCount": 5200,
      "cumulativeEntryCount": 5200,
      "contentHash": "sha256:abc123...",
      "domains": {"tools": 2100, "jvm": 1800, "quarkus": 1300},
      "dateRange": {"earliest": "2026-01-15", "latest": "2026-03-22"}
    }
  ]
}
```

### Internal ZIP Metadata

Inside each closed ZIP, `_chain/meta.json` is a **copy** of the chain entry for self-describing distribution. Written once at close time when all metadata is known. Not written to active ZIPs — the active ZIP has no internal metadata.

`_chain/successor.json` is appended to a closed ZIP when the next ZIP in the chain is created.

### ZIP States

| State | Has `_chain/meta.json` | Meaning |
|-------|------------------------|---------|
| Active | No | Current append target |
| Closed | Yes, `status: "closed"` | No more entries, chain continues |
| Sealed | Yes, `status: "sealed"` | Final ZIP in a frozen chain |

### Rollover Atomicity

Closing ZIP N and linking it to ZIP N+1 is atomic via `chain.json`:

1. Write new `chain.json` atomically (temp + rename) — ZIP N closed, ZIP N+1 active
2. Append `_chain/meta.json` to ZIP N (can fail — `chain.json` is the truth)
3. Create ZIP N+1 on disk
4. Append `_chain/successor.json` to ZIP N (can fail — `chain.json` has the link)

If the process crashes at any point, startup integrity check detects and recovers from `chain.json` or from the ZIPs themselves.

### Master Index (in-memory)

```java
Map<String, EntryLocation> pathIndex;     // path -> (zipFile, latest)
Map<String, List<EntryLocation>> history; // path -> all versions
```

Built on startup from ZIP central directories. Rebuilt from ZIPs if lost. Central directories are small — scanning 10 ZIPs takes milliseconds.

### Composite Mode

`CompositeCorpusStore` wraps `ZipCorpusStore` + `FlatCorpusStore`:

- **Writes** fan out to both ZIP and flat filesystem
- **Reads** come from ZIP (authoritative)
- **Flat files** are a live mirror for human browsing, grep, IDE access

Modes:

| Mode | Read from | Write to |
|------|-----------|----------|
| `ZIP` | ZIP | ZIP only |
| `FLAT` | filesystem | filesystem only |
| `COMPOSITE` | ZIP | ZIP + filesystem |

### Integrity System

Runs on startup (fast — manifest + central directories only). Full hash verification is opt-in.

**Detection matrix:**

| Check | Detects | Severity | Recovery |
|-------|---------|----------|----------|
| ZIP in directory, not in `chain.json` | Orphaned ZIP | WARNING | Link to chain via predecessor |
| Entry in `chain.json`, ZIP missing | Gap in chain | ERROR | Report: sequence N missing, M entries lost |
| Internal `_chain/meta.json` missing | Crash before copy written | INFO | Reconstruct from `chain.json`, append to ZIP |
| Internal meta disagrees with `chain.json` | Corruption/partial write | WARNING | `chain.json` wins, rewrite internal copy |
| Predecessor UUID mismatch | Broken chain link | ERROR | Report broken link |
| Content hash mismatch (opt-in) | Tampered ZIP | ERROR | Report tampered ZIP |
| Entry count mismatch | Partial write/corruption | WARNING | Report expected vs actual |
| `chain.json` missing entirely | Lost manifest | WARNING | Reconstruct from internal `_chain/meta.json` across all ZIPs |

**Integrity report:**

```
Corpus: garden
Chain length: 5 ZIPs (sequences 0-4)
Total entries: 12,847
Status: active (head: garden-005.zip)

Issues:
  [WARNING] garden-003.zip: internal meta.json missing — reconstructed from chain.json
  [ERROR]   garden-002.zip: content hash mismatch — ZIP may have been modified after close
  [ERROR]   gap: sequence 7 missing — garden-007.zip not found, ~2,400 entries lost

Recovered:
  [INFO] garden-003.zip: internal meta.json rewritten
  [INFO] orphan garden-009.zip linked to chain (predecessor matched sequence 8)
```

### Versioning

Append-only. New versions of a document at the same path are appended to the current ZIP. The central directory points to the latest. Previous versions are orphaned bytes — still in the ZIP, accessible via version history API.

- `read(path)` — returns latest version (default, fast)
- `readVersion(path, version)` — returns specific version
- `versions(path)` — returns all versions with timestamps

### ID-Based Lookup (optional)

When configured with an `id-strategy`, the master index also builds `ID -> (zip, path)` mappings:

- `filename-pattern` — extract ID from filename via regex
- `frontmatter` — parse YAML frontmatter and extract a named field

Path-based lookup always works regardless of ID strategy configuration.

## rag/ — Ingestion Bridge

### CorpusIngestionService

New class in `rag/` module. Wires `ChangeSource` to the existing embedding + Qdrant infrastructure.

**Flow:**

1. Poll `ChangeSource.changesSince(cursor)` on configurable schedule
2. For each changed entry: read from `CorpusReader`, extract metadata, chunk, embed, push to Qdrant
3. Persist cursor (survives restarts)
4. Reconciliation: `ChangeSource.fullScan()` -> compare against Qdrant -> report/fix gaps

**Ingestion modes:**

- `AUTO` — `@Scheduled` poll, configurable interval
- `MANUAL` — application calls explicitly
- `NONE` — no ingestion service created

### Metadata Extraction

Pluggable per corpus:

```java
public interface MetadataExtractor {
    Map<String, String> extract(String path, byte[] content);
}
```

Default implementation: YAML frontmatter parser (covers garden entries). Consumers provide their own for other document types.

Extracted metadata becomes filterable payload fields in Qdrant.

### Chunking

Delegates to LangChain4j `DocumentSplitter`. Configurable per corpus:

```properties
casehub.corpus.garden.chunking=none
casehub.corpus.legal.chunking=recursive
casehub.corpus.legal.chunking.max-tokens=300
casehub.corpus.legal.chunking.overlap-tokens=30
```

`none` = whole document body (minus extracted metadata) is one chunk.

### Cursor Persistence

Simple file alongside the corpus (`.<corpus-name>-cursor`). Contains the cursor string from the last successful `changesSince()` call.

## Maven Coordinates

| Module | artifactId |
|--------|-----------|
| Corpus API | `casehub-corpus-api` |
| Corpus | `casehub-corpus` |

Ingestion bridge lives in existing `casehub-rag`.

## Implementation Sequence

**Issue 1 (Session 1):** `corpus-api` + `corpus`
- SPI interfaces and value types
- `ZipCorpusStore` with Zip4j append
- Rolling ZIPs with size threshold
- Chain manifest (`chain.json`) with atomic writes
- Internal `_chain/meta.json` and `_chain/successor.json`
- Master index from central directories
- Composite mode (ZIP + flat files)
- Integrity check, detection, recovery, reporting
- Versioning (latest by default, history on demand)
- Optional ID-based lookup
- `FlatCorpusStore` implementation
- `ChangeSource` implementation
- Unit tests, integration tests

**Issue 2 (Session 2):** Ingestion bridge in `rag/`
- `CorpusIngestionService` wiring `ChangeSource` to RAG pipeline
- `MetadataExtractor` SPI + YAML frontmatter default implementation
- Chunking configuration per corpus
- Cursor persistence
- Reconciliation mode (full scan vs Qdrant)
- Integration tests with Qdrant

## Upstream Dependencies

Track quarkus-langchain4j composition annotations (casehubio/neural-text#16). When `@DocumentIngestion` ships, the ingestion bridge can adopt it. When `@Corpus` qualifier ships, multi-corpus CDI injection simplifies.

## Distribution Model

ZIP files are the distribution format:
- Ship the set of ZIPs for a corpus
- Each ZIP is independently browsable (standard ZIP, any tool can open it)
- Closed ZIPs contain `_chain/meta.json` for self-describing chains
- `chain.json` ships alongside for integrity verification
- Incremental sync: "you have ZIPs 1-5, here's ZIP 6"
