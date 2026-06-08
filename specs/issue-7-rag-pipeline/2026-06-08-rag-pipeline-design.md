# RAG Pipeline Design — casehub-neural-text #7

**Date:** 2026-06-08
**Status:** Approved — pending implementation
**Issue:** casehubio/neural-text#7
**Platform tracking:** casehubio/parent#164

---

## What This Delivers

`rag-api`, `rag`, `rag-tika`, and `rag-testing` published. CaseHub application repos can define named corpora in configuration, ingest documents via `CorpusStore`, and retrieve grounded context via `CaseRetriever`. Hybrid dense+sparse search operates across tenancy-isolated Qdrant collections. Optional cross-encoder reranking for precision mode.

---

## Module Structure

```
rag-api/       Pure Java, zero deps.
               CorpusStore SPI, CaseRetriever SPI, CorpusRef, ChunkInput, RetrievedChunk.
               Package: io.casehub.rag

rag/           Quarkus library JAR (Jandex-indexed, not a Quarkus extension).
               QdrantCorpusStore, HybridCaseRetriever, TenancyStrategy, QdrantConfig.
               Package: io.casehub.rag.runtime

rag-tika/      Optional. LangChain4j Tika parser → List<ChunkInput>.
               Callers add as compile dep to activate.
               Package: io.casehub.rag.tika

rag-testing/   In-memory CorpusStore + CaseRetriever stubs.
               @Alternative @Priority(1). No Qdrant, no embeddings.
               Package: io.casehub.rag.testing
```

### Dependencies

| Module | Depends on |
|--------|-----------|
| `rag-api` | nothing |
| `rag` | `rag-api`, `inference-splade`, `inference-tasks`, `casehub-platform-api`, `quarkus-arc`, `langchain4j-core`, `langchain4j-embeddings`, `io.qdrant:client` |
| `rag-tika` | `rag-api`, `langchain4j-document-parser-apache-tika`, `langchain4j` (for DocumentSplitter) |
| `rag-testing` | `rag-api` |

### What was dropped

`langchain4j-qdrant` removed from the dependency tree. LangChain4j does not support Qdrant hybrid search with named vector spaces (open feature request [langchain4j#4087](https://github.com/langchain4j/langchain4j/issues/4087), no timeline). Since we need the direct Qdrant Java client for sparse vectors + RRF fusion anyway, using it for both legs gives a unified architecture with one client, one code path, and no split-brain between dense and sparse operations.

LangChain4j is still used for: `EmbeddingModel` (dense embedding generation), `DocumentSplitter` (chunking), `ApacheTikaDocumentParser` (in `rag-tika`), and core data types (`TextSegment`, `Embedding`).

---

## rag-api Types

All types are records or interfaces. Zero external dependencies.

### CorpusRef

Identifies a tenant-scoped corpus. Mandatory on all SPI calls — no ambient tenancy.

```java
public record CorpusRef(String tenantId, String corpusName) {
    public CorpusRef {
        if (tenantId == null || tenantId.isBlank())
            throw new IllegalArgumentException("tenantId must not be null or blank");
        if (corpusName == null || corpusName.isBlank())
            throw new IllegalArgumentException("corpusName must not be null or blank");
    }
}
```

### ChunkInput

Pre-chunked text with metadata. What callers pass to ingest.

```java
public record ChunkInput(String content, String sourceDocumentId, Map<String, String> metadata) {
    public ChunkInput {
        if (content == null || content.isBlank())
            throw new IllegalArgumentException("content must not be null or blank");
        if (sourceDocumentId == null || sourceDocumentId.isBlank())
            throw new IllegalArgumentException("sourceDocumentId must not be null or blank");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }
}
```

### RetrievedChunk

What retrieval returns. Simple relevance score — no per-leg provenance.

```java
public record RetrievedChunk(String content, String sourceDocumentId,
                             double relevanceScore, Map<String, String> metadata) {}
```

### CorpusStore

Write-oriented SPI. Ingest pre-chunked content, delete documents, manage corpora.

```java
public interface CorpusStore {
    void ingest(CorpusRef corpus, List<ChunkInput> chunks);
    void deleteDocument(CorpusRef corpus, String sourceDocumentId);
    void deleteCorpus(CorpusRef corpus);
    List<String> listDocuments(CorpusRef corpus);
}
```

### CaseRetriever

Read-oriented SPI. Retrieval entry point for engine case steps and the fact space prompt compiler.

```java
public interface CaseRetriever {
    List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults);
}
```

### Design decisions

- `CorpusStore.ingest()` accepts pre-chunked `ChunkInput`, not raw documents. Callers chunk themselves or use `rag-tika`. Keeps Tika dependency optional.
- `CaseRetriever.retrieve()` takes `maxResults` as a parameter — different case steps may want different result counts.
- Separate SPIs for write (CorpusStore) and read (CaseRetriever). Different implementations, different CDI beans, different lifecycle concerns.
- `CorpusRef` is the tenancy enforcement point. Every SPI method requires it explicitly.

---

## rag Runtime

### QdrantConfig

`@ConfigMapping(prefix = "casehub.rag")` for Qdrant connection and pipeline tuning.

```
casehub.rag.qdrant.host = localhost
casehub.rag.qdrant.port = 6334
casehub.rag.qdrant.api-key =            # optional
casehub.rag.qdrant.use-tls = false

casehub.rag.tenancy-strategy = SEPARATE_COLLECTIONS   # or SHARED_COLLECTION
casehub.rag.dense-vector-name = dense
casehub.rag.sparse-vector-name = sparse

casehub.rag.retrieval.dense-top-k = 40
casehub.rag.retrieval.sparse-top-k = 40
casehub.rag.retrieval.rrf-k = 60
casehub.rag.retrieval.rerank-enabled = true
casehub.rag.retrieval.rerank-top-n = 10
```

### TenancyStrategy

Maps `CorpusRef` to Qdrant collection name + optional filter. Configurable — operational decision, not architectural.

**SEPARATE_COLLECTIONS (default):**
- Collection name: `{tenantId}_{corpusName}`
- Filter: none (isolation by collection boundary)
- `deleteCorpus` → delete entire collection

**SHARED_COLLECTION:**
- Collection name: `{corpusName}`
- Filter: `must[match("tenantId", ref.tenantId())]` on every query and delete
- `deleteCorpus` → delete all points matching tenantId filter

### QdrantCorpusStore

`@ApplicationScoped`. Implements `CorpusStore`.

**Ingest pipeline:**
1. Resolve collection name via `TenancyStrategy`
2. Ensure collection exists — create with two named vector spaces (`dense`: float vector at `EmbeddingModel.dimension()`, `sparse`: sparse vector) if absent
3. For each `ChunkInput`: embed dense via `EmbeddingModel.embed()`, embed sparse via `SparseEmbedder.embed()`
4. Build Qdrant `PointStruct` per chunk — UUID id, both named vectors, payload containing `content`, `sourceDocumentId`, `tenantId`, and all `metadata` entries
5. Batch upsert to Qdrant

**Delete operations:**
- `deleteDocument`: scroll + delete by `sourceDocumentId` payload filter (+ tenantId filter in shared mode)
- `deleteCorpus`: delete collection (separate mode) or delete all points by tenantId filter (shared mode)
- `listDocuments`: scroll with payload filter, extract distinct `sourceDocumentId` values

### HybridCaseRetriever

`@ApplicationScoped`. Implements `CaseRetriever`.

**Retrieval pipeline:**
1. Resolve collection name + filter via `TenancyStrategy`
2. Embed query dense via `EmbeddingModel`, sparse via `SparseEmbedder`
3. Issue Qdrant Query API request:
   - Prefetch 1: dense nearest-neighbor search, top-K results
   - Prefetch 2: sparse nearest-neighbor search, top-K results
   - Fusion: RRF with configurable k constant
   - Limit: `maxResults` (or `rerank-top-n` candidates if reranking enabled)
4. Map Qdrant scored points → `RetrievedChunk` list
5. If reranking enabled and `CrossEncoderReranker` available: rerank candidates, re-sort by cross-encoder score, truncate to final `maxResults`
6. Return `List<RetrievedChunk>` sorted by descending relevance

### CDI injection

Both beans inject:
- `QdrantClient` — produced internally from `QdrantConfig`
- `EmbeddingModel` — provided by the consuming app
- `SparseEmbedder` — provided by the consuming app
- `Instance<CrossEncoderReranker>` — optional, provided by the consuming app if reranking is desired
- `TenancyStrategy` — produced internally from config

---

## rag-tika

Optional module. `@ApplicationScoped` CDI bean.

```java
public class TikaDocumentParser {
    List<ChunkInput> parse(InputStream content, String sourceDocumentId,
                           String contentType, Map<String, String> metadata);
}
```

Pipeline:
1. `ApacheTikaDocumentParser` (LangChain4j) parses InputStream → `Document`
2. `DocumentSplitter` (recursive character, configurable chunk size + overlap) splits → `List<TextSegment>`
3. Maps each segment → `ChunkInput` with `sourceDocumentId` and merged metadata (Tika-extracted + caller-provided)

Configuration:
```
casehub.rag.tika.chunk-size = 512
casehub.rag.tika.chunk-overlap = 64
```

Callers add `casehub-rag-tika` as compile dep to activate. Without it, `CorpusStore.ingest()` still works — callers provide their own `List<ChunkInput>`.

---

## rag-testing

Deterministic in-memory stubs. Both `@Alternative @Priority(1)`.

**`InMemoryCorpusStore`** — `Map<CorpusRef, Map<String, List<ChunkInput>>>`. All operations in-memory. Displaces `QdrantCorpusStore` on test classpath.

**`InMemoryCaseRetriever`** — two modes:
- Default: backed by an `InMemoryCorpusStore` instance (injected). Returns stored chunks for the corpus as `RetrievedChunk` (content + sourceDocumentId from the `ChunkInput`, relevanceScore = 1.0), insertion order, truncated to `maxResults`. No embedding, no scoring. Tests that use both stubs together get consistent ingest → retrieve behavior.
- Programmatic: `InMemoryCaseRetriever.returning(List<RetrievedChunk>)` — factory method producing a standalone instance with fixed responses regardless of query. For tests that need controlled retrieval without ingesting.

Consumer test classpath:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-rag-testing</artifactId>
    <scope>test</scope>
</dependency>
```

---

## Consumer Integration

`rag` is a library JAR, not a Quarkus extension. The consuming Quarkus app provides:

| Bean | How | Source |
|------|-----|--------|
| `EmbeddingModel` | App-level CDI producer (quarkus-langchain4j ONNX, remote API, etc.) | App |
| `SparseEmbedder` | App produces from `@Inference("splade")` model via `inference-quarkus` | App |
| `CrossEncoderReranker` | App produces from `@Inference("cross-encoder")` model | App (optional) |
| `QdrantClient` | Produced by `rag` module from `QdrantConfig` | `rag` |
| `TenancyStrategy` | Produced by `rag` module from config | `rag` |

This follows the platform's established pattern: `rag` provides the runtime, the app provides the configuration and infrastructure beans.

---

## Hortora Boundary

`rag-api` is the shared contract — pure Java, zero deps. Hortora can implement `CorpusStore` and `CaseRetriever` against their own stack (different tenancy model, different Qdrant wiring, potentially different vector store).

`rag` is casehub-specific — depends on `casehub-platform-api`. Hortora does not take this module. They reuse `inference-splade` and `inference-tasks` (already shared, zero casehub deps) and write their own Qdrant integration.

The design brief confirms this split: "No code is shared between the two LangChain4j wiring layers."

---

## ArchUnit Constraints

- `rag-api`: zero deps on Quarkus, LangChain4j, Qdrant, casehub domain types. Same enforcement pattern as `inference-api`.
- `rag-testing`: no Qdrant client, no LangChain4j embeddings. Pure Java + `rag-api` only.
- `rag`: no casehub domain types beyond `casehub-platform-api` (CurrentPrincipal, TenancyConstants).

---

## What This Does NOT Cover

- Qdrant server deployment / DevServices (future: `inference-quarkus` Dev Services could manage Qdrant lifecycle)
- Fact space prompt compiler integration (casehub-engine concern — consumes `CaseRetriever` SPI)
- Dense embedding model selection (app-level concern)
- SPLADE / cross-encoder model selection (app-level concern)
- Native image support for Qdrant client (not a gate — Qdrant client is pure Java gRPC/REST)
