# Corpus Ingestion Bridge Design

**Date:** 2026-06-13
**Status:** Draft
**Tracks:** casehubio/neural-text#19
**Parent spec:** `specs/2026-06-11-corpus-storage-module-design.md` (rev 5, §rag/ — Ingestion Bridge)

## Problem

The corpus modules (`corpus-api/`, `corpus/`) provide document storage with change tracking. The RAG modules (`rag-api/`, `rag/`) provide embedding and vector search via Qdrant. Nothing connects them. Documents written to a corpus are not automatically embedded and made searchable. Consumers must manually read documents, chunk them, and call `EmbeddingIngestor` — duplicating pipeline logic across every integration.

## Solution

A config-driven ingestion bridge in `rag/` that polls `ChangeSource`, reads from `CorpusReader`, extracts metadata, chunks, and pushes to Qdrant via the existing `EmbeddingIngestor`. Three new SPIs in `rag-api` provide the extension points: `MetadataExtractor`, `CursorStore`, and `CorpusIngestionBinding`.

## Design Principles

1. **Bridge depends on corpus-api SPIs only** — `ChangeSource` and `CorpusReader`, never `CorpusStore`. The bridge is a read-only consumer. A producer class in `rag/` handles corpus instance creation from config.
2. **Per-binding MetadataExtractor** — different corpora have different document formats (YAML frontmatter, Tika, CSV). The extractor belongs per-corpus in the binding, not as a global CDI bean.
3. **Blocking pipeline** — every operation (ZIP I/O, embedding inference, Qdrant gRPC) is blocking. No reactive variant needed for a background poller.
4. **Delete-then-reingest for MODIFIED** — `EmbeddingIngestor` generates random UUIDs per point. Re-ingesting without deleting first creates duplicates. The bridge always deletes old vectors before ingesting new ones for MODIFIED entries.
5. **All-or-nothing cursor advancement** — cursor advances only when the entire ChangeSet succeeds. On partial failure, the entire set is retried next poll. Safe because delete-then-reingest is idempotent.

## rag-api Additions (Tier 1)

### MetadataExtractor SPI

```java
package io.casehub.rag;

import java.util.Map;

public interface MetadataExtractor {
    ExtractionResult extract(String path, byte[] content);
}
```

Returns both the cleaned body (frontmatter stripped) and the extracted metadata. The body goes to the chunker. The metadata becomes `ChunkInput.metadata()` and Qdrant payload fields.

### ExtractionResult

```java
package io.casehub.rag;

import java.util.Map;

public record ExtractionResult(String body, Map<String, String> metadata) {
    public ExtractionResult {
        if (body == null)
            throw new IllegalArgumentException("body must not be null");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }
}
```

### CursorStore SPI

```java
package io.casehub.rag;

import java.util.Optional;

public interface CursorStore {
    Optional<String> load(String corpusName);
    void save(String corpusName, String cursor);
}
```

Persists the ChangeSource cursor per corpus. Pluggable backend — file-based default, in-memory for tests, DB-backed for multi-instance deployments.

### CorpusIngestionBinding

```java
package io.casehub.rag;

import io.casehub.corpus.ChangeSource;
import io.casehub.corpus.CorpusReader;
import java.util.Objects;

public record CorpusIngestionBinding(
    String name,
    CorpusRef corpusRef,
    ChangeSource changeSource,
    CorpusReader corpusReader,
    MetadataExtractor metadataExtractor
) {
    public CorpusIngestionBinding {
        if (name == null || name.isBlank())
            throw new IllegalArgumentException("name must not be null or blank");
        Objects.requireNonNull(corpusRef, "corpusRef");
        Objects.requireNonNull(changeSource, "changeSource");
        Objects.requireNonNull(corpusReader, "corpusReader");
        Objects.requireNonNull(metadataExtractor, "metadataExtractor");
    }
}
```

The bridge's input contract. Each bean is a complete descriptor of one corpus to ingest. CDI-discovered via `Instance<CorpusIngestionBinding>`. Applications can produce bindings manually for custom backends; the auto-wiring producer creates them from config for the common case.

### New dependency

rag-api → corpus-api (Tier 1 → Tier 1, both pure Java, same repo).

## rag/ Additions (Tier 3)

### CorpusIngestionService

`@ApplicationScoped`. Discovers `CorpusIngestionBinding` beans via `Instance<CorpusIngestionBinding>`.

**Poll loop:**

Single `@Scheduled` method with configurable global interval (`casehub.rag.ingestion.interval`, default `30s`). Iterates all discovered bindings, processes each independently. Per-corpus `ReentrantLock` prevents concurrent processing (poll vs reconciliation overlap). Only runs for corpora with `mode=AUTO` in config. `MANUAL` corpora are processed on explicit trigger. `NONE` are skipped.

**Processing a ChangeSet:**

```
1. CursorStore.load(binding.name()) → cursor
2. ChangeSource.changesSince(cursor) → ChangeSet
3. If empty → return

4. Phase 1 — Deletions:
   For DELETED: EmbeddingIngestor.deleteDocument(corpusRef, path)
   For MODIFIED: EmbeddingIngestor.deleteDocument(corpusRef, path)

5. Phase 2 — Ingestion:
   For each ADDED/MODIFIED:
     a. CorpusReader.read(path) → byte[] (skip if empty)
     b. MetadataExtractor.extract(path, content) → ExtractionResult
     c. Chunk body via DocumentSplitter (resolved from config per corpus name)
     d. Create ChunkInput(chunkText, sourceDocumentId=path, metadata) per chunk
   Batch all ChunkInputs → EmbeddingIngestor.ingest(corpusRef, allChunks)

6. ALL succeeded → CursorStore.save(name, changeSet.newCursor())
   ANY failed → log failures, do NOT advance cursor
```

**sourceDocumentId:** the corpus path (e.g. `tools/git-rebase.md`). Stable across updates, unique within a corpus.

**Reconciliation:**

Separate from the poll loop. Triggerable via `reconcile(String corpusName)` or `reconcileAll()`.

```
1. ChangeSource.fullScan() → all paths in corpus
2. EmbeddingIngestor.listDocuments(corpusRef) → all sourceDocumentIds in Qdrant
3. In corpus but not in Qdrant → reingest
4. In Qdrant but not in corpus → deleteDocument()
5. CursorStore.save(name, fullScan.newCursor())
```

**Error handling:**

| Failure | Action |
|---------|--------|
| ChangeSource throws | Log error, skip this corpus, continue to next binding |
| CorpusReader.read() returns empty | Log warning, skip entry (doc deleted between detect and read) |
| MetadataExtractor throws | Log error, skip entry, mark ChangeSet as partially failed |
| EmbeddingIngestor throws | Log error, mark ChangeSet as failed, don't advance cursor |

### YamlFrontmatterExtractor

`@DefaultBean @ApplicationScoped`. Parses YAML frontmatter delimited by `---` lines. Returns body (everything after closing `---`) and metadata (flat `key: value` pairs). Pure string parsing — no SnakeYAML dependency. If no frontmatter found, returns entire content as body with empty metadata.

Not injected globally — used by `CorpusBindingProducer` as the default extractor for bindings that don't specify one.

### FileCursorStore

`@DefaultBean @ApplicationScoped`. Stores cursor values as text files: `<cursor-dir>/<corpusName>.cursor`. Atomic write via temp file + rename. Config: `casehub.rag.ingestion.cursor-dir` (defaults to `${java.io.tmpdir}/casehub-ingestion-cursors`).

### IngestionConfig

```java
@ConfigMapping(prefix = "casehub.rag.ingestion")
public interface IngestionConfig {

    @WithDefault("30s")
    Duration interval();

    @WithDefault("${java.io.tmpdir}/casehub-ingestion-cursors")
    String cursorDir();

    Map<String, CorpusIngestionConfig> corpora();

    interface CorpusIngestionConfig {
        @WithDefault("AUTO")
        IngestionMode mode();

        String tenantId();
        String corpusName();

        @WithDefault("none")
        String chunking();

        Optional<Integer> chunkingMaxTokens();
        Optional<Integer> chunkingOverlapTokens();
    }
}
```

Config example:
```properties
casehub.rag.ingestion.interval=30s
casehub.rag.ingestion.corpora.garden.tenant-id=default
casehub.rag.ingestion.corpora.garden.corpus-name=garden
casehub.rag.ingestion.corpora.garden.mode=auto
casehub.rag.ingestion.corpora.garden.chunking=none
casehub.rag.ingestion.corpora.legal.tenant-id=acme-corp
casehub.rag.ingestion.corpora.legal.corpus-name=legal
casehub.rag.ingestion.corpora.legal.chunking=recursive
casehub.rag.ingestion.corpora.legal.chunking-max-tokens=300
casehub.rag.ingestion.corpora.legal.chunking-overlap-tokens=30
```

### IngestionMode

```java
package io.casehub.rag.runtime;

public enum IngestionMode { AUTO, MANUAL, NONE }
```

### CorpusBindingProducer

`@ApplicationScoped`. Reads `IngestionConfig.corpora()` map. For each named corpus entry, constructs the corpus implementation objects (`ZipCorpusStore`, `FlatCorpusStore`, or `CompositeCorpusStore` depending on corpus-level config at `casehub.corpus.<name>.*`) and produces a `CorpusIngestionBinding` CDI bean. The corpus-level config (`casehub.corpus.<name>.source`, `casehub.corpus.<name>.mode`, etc.) is read via a separate `@ConfigMapping` within this producer. Uses `YamlFrontmatterExtractor` as the default extractor for each binding.

This is the only class in `rag/` that depends on `casehub-corpus` implementation types. The rest of the ingestion service depends only on corpus-api types via the binding.

### Chunking

Resolved internally by `CorpusIngestionService` from `IngestionConfig` per corpus name. Maps config values to LangChain4j `DocumentSplitter` implementations:

| Config value | DocumentSplitter |
|---|---|
| `none` | null — whole body is one chunk |
| `recursive` | `RecursiveCharacterTextSplitter(maxTokens, overlapTokens)` |

LangChain4j types stay internal to `rag/` — never leak into rag-api or the binding.

## rag-testing/ Additions

### InMemoryCursorStore

`@Alternative @Priority(1) @ApplicationScoped`. `ConcurrentHashMap<String, String>` backing store. Provides `reset()` and `getAll()` for test assertions. Follows the existing rag-testing pattern.

No reactive CursorStore variant — the bridge is blocking-only.

No MetadataExtractor test stub — tests construct bindings with inline implementations or use `YamlFrontmatterExtractor` directly.

## Dependency Changes

**rag-api pom.xml — new:**
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-corpus-api</artifactId>
</dependency>
```

**rag/ pom.xml — new:**
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-corpus</artifactId>
</dependency>
```

**No new modules.** All changes are additions to existing modules.

## File Inventory

| Module | New files | Purpose |
|--------|-----------|---------|
| rag-api | `MetadataExtractor.java` | SPI |
| rag-api | `ExtractionResult.java` | Value type |
| rag-api | `CursorStore.java` | SPI |
| rag-api | `CorpusIngestionBinding.java` | Bridge input contract |
| rag | `CorpusIngestionService.java` | Poll loop + reconciliation orchestrator |
| rag | `YamlFrontmatterExtractor.java` | `@DefaultBean` MetadataExtractor |
| rag | `FileCursorStore.java` | `@DefaultBean` CursorStore |
| rag | `IngestionConfig.java` | `@ConfigMapping` |
| rag | `IngestionMode.java` | Enum |
| rag | `CorpusBindingProducer.java` | Auto-wires bindings from config |
| rag-testing | `InMemoryCursorStore.java` | Test stub |

## Coherence Review

| Check | Result |
|-------|--------|
| Module-tier-structure (PP-20260512) | rag-api stays Tier 1 (pure Java + Mutiny provided). corpus-api dep is Tier 1. rag/ stays Tier 3. rag-testing @Alternative @Priority(1). |
| Reactive SPI bridge (PP-20260529-5745c1) | No reactive variants — background poller, all ops blocking. |
| Persistence-backend-cdi-priority | FileCursorStore @DefaultBean → InMemoryCursorStore @Alternative @Priority(1). Standard ladder. |
| CursorStore as store SPI | File-based default is the production backend (analogous to casehub-platform-config). Cursor data is ephemeral — no persistence-memory/ module needed. |
| Plane separation (parent spec) | Bridge depends on CorpusReader + ChangeSource only. CorpusBindingProducer is the sole corpus/ dependent. |
| Platform capability ownership | Extends existing "Knowledge corpus retrieval (RAG)" capability. No new ownership entry. Deep-dive update tracked as parent#214. |
| Cross-repo deps | None new. corpus-api and corpus are in the same repo. |
