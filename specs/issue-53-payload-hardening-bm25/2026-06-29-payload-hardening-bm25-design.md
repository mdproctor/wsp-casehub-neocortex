# Payload Hardening and BM25 Retrieval — Design Spec

**Issues:** #53, #54, #48
**Branch:** `issue-53-payload-hardening-bm25`
**Date:** 2026-06-29

## Summary

Three related changes to the RAG pipeline:

1. **#54 — Metadata key collision:** Two-layer fail-fast validation prevents metadata from silently overwriting reserved payload fields.
2. **#53 — CamelCase tokenization:** Pre-split camelCase identifiers in BM25 input text so partial identifier search works (e.g., searching "HashMap" finds "ConcurrentHashMap").
3. **#48 — BM25 retrieval leg:** Add server-side BM25 sparse vectors as a third RRF fusion leg alongside dense and SPLADE.

## 1. Metadata Key Validation (#54)

### Problem

`QdrantPointBuilder.buildPoint()` writes `content`, `sourceDocumentId`, and `tenantId` as payload fields, then iterates `ChunkInput.metadata()` into the same map. A metadata entry with key `"content"` silently overwrites the stored content. With payload indexes (#47, #50), corruption is amplified: wrong BM25 results, missed deletes, cross-tenant data leakage.

### Design

**Layer 1 — `ChunkInput` constructor (rag-api):**

Reject metadata keys that shadow the record's own fields: `"content"`, `"sourceDocumentId"`. These are structural contradictions — `ChunkInput` has typed fields for them, and metadata is "everything else." This invariant holds regardless of the storage backend.

```java
private static final Set<String> RESERVED_KEYS = Set.of("content", "sourceDocumentId");

public ChunkInput {
    // existing null/blank checks ...
    metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    for (String key : metadata.keySet()) {
        if (RESERVED_KEYS.contains(key)) {
            throw new IllegalArgumentException(
                "metadata key '" + key + "' conflicts with ChunkInput field name");
        }
    }
}
```

**Layer 2 — `QdrantPointBuilder.buildPoint()` (rag impl):**

Reject metadata keys that collide with implementation-specific payload fields. Currently only `"tenantId"` — it enters the payload from `CorpusRef`, not `ChunkInput`, so `ChunkInput` can't validate against it.

```java
private static final Set<String> QDRANT_RESERVED_KEYS = Set.of("tenantId");

// in buildPoint(), before metadata loop:
for (String key : chunk.metadata().keySet()) {
    if (QDRANT_RESERVED_KEYS.contains(key)) {
        throw new IllegalArgumentException(
            "metadata key '" + key + "' conflicts with reserved Qdrant payload field");
    }
}
```

**Shared constant for retrieval filtering:**

Extract the `RESERVED_PAYLOAD_KEYS` set from both `HybridCaseRetriever` and `ReactiveHybridCaseRetriever` to a shared location in `QdrantPointBuilder` (package-private). The set is `Set.of("content", "sourceDocumentId", "tenantId")` — the union of both layers, used when reconstructing metadata from retrieved points.

### Impact

- **rag-api:** `ChunkInput` gains validation. Breaking change for callers passing reserved keys as metadata — they get `IllegalArgumentException`. This is the point: forcing callers to be explicit.
- **rag-testing:** No stub changes. Stubs inherit `ChunkInput` validation automatically. Test data using reserved metadata keys will surface as test failures.
- **Existing data:** Already-stored points with colliding metadata are unaffected (read path doesn't validate, it filters).

## 2. CamelCase Token Expansion (#53)

### Problem

Qdrant's Word tokenizer treats `ConcurrentHashMap` as a single token `concurrenthashmap`. Searching for `HashMap` produces no match. This affects both the text payload index (#47) and BM25 server-side tokenization.

### Design

Expand camelCase identifiers **only in the text passed to BM25 `Document`**, not in the `content` payload field.

- **Text payload index (#47):** Retains current behavior — exact full-identifier search. The issue description explicitly says this is acceptable for the target scenarios.
- **BM25 vector (#48):** Gets expanded text — partial identifier search works.

**`CamelCaseExpander` — package-private utility in `rag` module:**

A stateless pure function. Input: raw text. Output: text with camelCase identifiers expanded.

Expansion strategy: **for each token that contains camelCase boundaries, append the sub-tokens after it.** Non-camelCase tokens pass through unchanged.

Examples:
- `"ConcurrentHashMap is useful"` → `"ConcurrentHashMap Concurrent Hash Map is useful"`
- `"maxResults for HTMLParser"` → `"maxResults max Results for HTMLParser HTML Parser"`
- `"Base64Encoder works"` → `"Base64Encoder Base64 Encoder works"`
- `"simple words only"` → `"simple words only"` (no change)

Splitting rules:
- Lowercase→uppercase: `maxResults` → `max` + `Results`
- Uppercase run followed by lowercase (keep last uppercase with lowercase): `HTMLParser` → `HTML` + `Parser`
- Number boundaries: `Base64Encoder` → `Base64` + `Encoder`
- Underscores/hyphens: already split by the Word tokenizer, no action needed
- Tokens without camelCase boundaries: passed through unchanged

Used at two points:
1. **Ingest** — `QdrantPointBuilder`: text passed to `Document.newBuilder().setText(expanded)` for the BM25 named vector.
2. **Query** — both retrievers: text passed to `Document.newBuilder().setText(expanded)` for the BM25 prefetch.

### Known limitation

The text payload index on `content` still uses the Word tokenizer without camelCase splitting. Text filters (`matchText("content", "HashMap")`) will not match documents containing only `ConcurrentHashMap`. This is a documented known behavior — text filtering is boolean narrowing, not scored retrieval. BM25 handles the scored keyword retrieval case.

## 3. BM25 as Third RRF Retrieval Leg (#48)

### Problem

Dense embeddings miss exact keyword matches (VOCABULARY_GAP). SPLADE covers some gaps via learned term expansion, but Java class names and CDI annotations still underperform. BM25 adds classical keyword matching — the third leg that completes the retrieval triad.

### Design

BM25 is implemented as a **server-side sparse vector** using Qdrant's built-in inference (`"qdrant/bm25"` model). No client-side BM25 model needed. Qdrant computes IDF internally as the corpus grows.

### Collection creation

Add a third named sparse vector `"bm25"` with `Modifier.Idf` to `ensureCollection()` in both `QdrantEmbeddingIngestor` and `ReactiveQdrantEmbeddingIngestor`:

```java
SparseVectorConfig.Builder sparseConfig = SparseVectorConfig.newBuilder();
if (sparseEmbedder != null) {
    sparseConfig.putMap(sparseVectorName, SparseVectorParams.getDefaultInstance());
}
if (bm25Enabled) {
    sparseConfig.putMap(bm25VectorName,
        SparseVectorParams.newBuilder().setModifier(Modifier.Idf).build());
}
```

SPLADE and BM25 are independently optional. The sparse config includes whichever are enabled.

No migration path for existing collections — drop and re-create. This platform has no end users; breaking changes cost nothing.

### Ingestion

`QdrantPointBuilder.buildPoint()` adds a BM25 named vector using `Document` for server-side inference:

```java
String expandedContent = CamelCaseExpander.expand(chunk.content());
Vector bm25Vector = VectorFactory.vector(
    Document.newBuilder()
        .setText(expandedContent)
        .setModel("qdrant/bm25")
        .build());
```

The named vectors map grows from 1-2 to 1-3 entries depending on which sparse embedders are enabled. `buildPoint()` gains a `bm25Enabled` parameter and `bm25VectorName`.

### Retrieval

Both `HybridCaseRetriever` and `ReactiveHybridCaseRetriever` add a BM25 prefetch leg:

```java
String expandedQuery = CamelCaseExpander.expand(query.text());
PrefetchQuery.Builder bm25Prefetch = PrefetchQuery.newBuilder()
    .setQuery(QueryFactory.nearest(
        Document.newBuilder()
            .setText(expandedQuery)
            .setModel("qdrant/bm25")
            .build()))
    .setUsing(bm25VectorName)
    .setLimit(bm25TopK);
mergedFilter.ifPresent(bm25Prefetch::setFilter);
```

Three-way RRF fusion: dense + sparse + bm25 → `QueryFactory.rrf(Rrf.newBuilder().setK(rrfK).build())`. RRF handles N legs transparently.

**Query text selection:** BM25 uses `query.text()` (original user query), not `query.searchText()` (which may include HyDE expansion). BM25 is keyword matching — hypothetical documents from HyDE would add noise.

**Retrieval mode matrix:**

| SPLADE | BM25 | Mode |
|--------|------|------|
| off | off | Dense-only (no fusion) |
| on | off | Dense + sparse RRF (current behavior) |
| off | on | Dense + BM25 RRF |
| on | on | Dense + sparse + BM25 RRF |

### Configuration

```java
@ConfigMapping(prefix = "casehub.rag")
public interface RagConfig {
    // existing: denseVectorName, sparseVectorName, ...

    @WithDefault("bm25")
    String bm25VectorName();

    interface RetrievalConfig {
        // existing: denseTopK, sparseTopK, rrfK, rerankEnabled, rerankTopN

        @WithDefault("true")
        boolean bm25Enabled();

        @WithDefault("40")
        int bm25TopK();
    }
}
```

BM25 is enabled by default. The `"qdrant/bm25"` model string is a constant — it's a Qdrant built-in, not configurable.

### CDI producers

Both `RagBeanProducer` and `ReactiveRagBeanProducer` pass `bm25Enabled`, `bm25TopK`, and `bm25VectorName` to the ingestors and retrievers.

### In-memory stubs

No changes. The `EmbeddingIngestor` and `CaseRetriever` SPI signatures are unchanged. BM25 is entirely within the Qdrant implementation.

## Files Changed

### rag-api (Tier 1)
- `ChunkInput.java` — add metadata key validation against record field names

### rag (Tier 3)
- `QdrantPointBuilder.java` — add `tenantId` metadata validation, add BM25 vector, add `RESERVED_PAYLOAD_KEYS` shared constant
- `CamelCaseExpander.java` — **new**, package-private utility
- `HybridCaseRetriever.java` — add BM25 prefetch leg, use shared `RESERVED_PAYLOAD_KEYS`
- `ReactiveHybridCaseRetriever.java` — add BM25 prefetch leg, use shared `RESERVED_PAYLOAD_KEYS`
- `QdrantEmbeddingIngestor.java` — add BM25 sparse config to `ensureCollection()`, pass BM25 params to `buildPoint()`
- `ReactiveQdrantEmbeddingIngestor.java` — add BM25 sparse config to `buildCreateRequest()` and `ensureCollection()`, pass BM25 params to `buildPoint()`
- `RagConfig.java` — add `bm25VectorName`, `bm25Enabled`, `bm25TopK`
- `RagBeanProducer.java` — pass BM25 config to ingestor and retriever
- `ReactiveRagBeanProducer.java` — pass BM25 config to ingestor and retriever

### Tests
- `ChunkInputTest.java` — test reserved metadata key rejection
- `CamelCaseExpanderTest.java` — **new**, test splitting rules
- `QdrantPointBuilderTest.java` — test `tenantId` metadata rejection, test BM25 vector inclusion
- `HybridCaseRetrieverTest.java` — test BM25 prefetch leg, test three-way RRF
- `ReactiveHybridCaseRetrieverTest.java` — test BM25 prefetch leg
- `QdrantEmbeddingIngestorTest.java` — test BM25 sparse config in collection creation
- `ReactiveQdrantEmbeddingIngestorTest.java` — test BM25 sparse config in collection creation

## Protocols Checked

- `qdrant-client-library.md` — using `io.qdrant:client` directly (not langchain4j-qdrant). Confirmed.
- `spi-signature-change-all-impls-same-commit.md` — SPI signatures unchanged. N/A.
- `module-tier-structure.md` — `ChunkInput` validation is in Tier 1 (pure Java). Implementation validation is in Tier 3 (Qdrant). Correct tier placement.

## Garden Entries Referenced

- GE-20260629-0a321f — Qdrant createCollectionAsync idempotency asymmetry (informs ensureCollection design)
- GE-20260609-c1998e — `QueryFactory.rrf(Rrf)` vs `fusion(Fusion.RRF)` — using `rrf()` for configurable k
- GE-20260627-8b0fb8 — PrefetchQuery per-leg SearchParams (oversampling targets dense only, not BM25)
