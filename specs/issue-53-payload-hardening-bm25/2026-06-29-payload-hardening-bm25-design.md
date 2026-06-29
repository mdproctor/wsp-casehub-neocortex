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

**Why only BM25, not SPLADE?** SPLADE uses WordPiece subword tokenization (BERT-based), which already decomposes camelCase at the subword level — `ConcurrentHashMap` becomes tokens like `con`, `##current`, `##hash`, `##map`. Expanding before SPLADE would produce redundant tokens with no retrieval benefit. BM25's word tokenizer treats identifiers as opaque single tokens, so explicit expansion is necessary.

Used at two points:
1. **Ingest** — `QdrantPointBuilder`: text passed to `Document.newBuilder().setText(expanded)` for the BM25 named vector.
2. **Query** — both retrievers: text passed to `Document.newBuilder().setText(expanded)` for the BM25 prefetch.

### Known limitations

**Text payload index:** The text payload index on `content` still uses the Word tokenizer without camelCase splitting. Text filters (`matchText("content", "HashMap")`) will not match documents containing only `ConcurrentHashMap`. This is a documented known behavior — text filtering is boolean narrowing, not scored retrieval. BM25 handles the scored keyword retrieval case.

**Consecutive uppercase abbreviations:** The single-pass algorithm splits at uppercase-run-to-lowercase transitions. For standard Java camelCase (`XMLHttpRequest`), this correctly produces `XML` + `Http` + `Request`. For non-standard consecutive abbreviations like `XMLHTTPRequest`, the algorithm produces `XMLHTTP` + `Request` instead of `XML` + `HTTP` + `Request` — the inner `XMLHTTP` boundary has no lowercase transition to split on. This is accepted: `XMLHTTPRequest` violates Java naming conventions (the correct form is `XMLHttpRequest`), and a multi-pass or recursive algorithm adds complexity for negligible real-world benefit.

Test case: `XMLHTTPRequest` → `XMLHTTPRequest XMLHTTP Request` (documenting actual behavior, not ideal).

## 3. BM25 as Third RRF Retrieval Leg (#48)

### Approach divergence from #48

Issue #48 describes BM25 via Qdrant's full-text payload index — a filter-based prefetch on the `content` field using `match: { text: "query" }`. That approach produces boolean matches (every matching document gets equal rank), which defeats the purpose of an RRF fusion leg — RRF needs meaningfully different scores per document to produce useful rank-based merging.

This design uses server-side BM25 sparse vectors via the `Document` inference API with `"qdrant/bm25"`. This produces real BM25 scores (term frequency × inverse document frequency) as a named sparse vector, giving RRF the scored input it needs. The text payload index from #47 continues to serve `matchText()` filtering; the BM25 retrieval leg is independent.

Consequence: #48's blocker on #47 is obsolete — the BM25 vector is independent of the text payload index. Issue #48 should be updated to remove the #47 dependency and describe the server-side sparse vector approach.

**Minimum Qdrant version:** v1.12+ (server-side inference with built-in models including `"qdrant/bm25"`). The Qdrant Java client 1.18.1 includes the `Document` proto, `VectorFactory.vector(Document)`, and `QueryFactory.nearest(Document)` — verified in the client source.

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

### Existing collection validation

`ensureCollection()` already validates that the dense vector dimension matches. Add validation for sparse vectors: when BM25 is enabled, check that the collection's `sparseVectorsConfig` includes `bm25VectorName`. When SPLADE is enabled (`sparseEmbedder != null`), check for `sparseVectorName`. If missing, throw `IllegalStateException` with a clear message:

```java
Map<String, SparseVectorParams> sparseVectors = info.getConfig().getParams()
    .getSparseVectorsConfig().getMapMap();

if (config.bm25Enabled() && !sparseVectors.containsKey(config.bm25VectorName())) {
    throw new IllegalStateException(
        "BM25 is enabled but collection '" + collection
            + "' was created without sparse vector '"
            + config.bm25VectorName()
            + "'. Drop and re-create the collection.");
}
if (sparseEmbedder != null && !sparseVectors.containsKey(config.sparseVectorName())) {
    throw new IllegalStateException(
        "SPLADE is enabled but collection '" + collection
            + "' was created without sparse vector '"
            + config.sparseVectorName()
            + "'. Drop and re-create the collection.");
}
```

This fixes a pre-existing gap (SPLADE validation was also missing) and prevents confusing Qdrant-level errors on upsert.

### Ingestion

`QdrantPointBuilder` defines a shared constant for the Qdrant built-in BM25 model name, used at both ingest and query time:

```java
static final String BM25_MODEL = "qdrant/bm25";
```

`buildPoint()` adds a BM25 named vector using `Document` for server-side inference:

```java
String expandedContent = CamelCaseExpander.expand(chunk.content());
Vector bm25Vector = VectorFactory.vector(
    Document.newBuilder()
        .setText(expandedContent)
        .setModel(BM25_MODEL)
        .build());
```

The named vectors map grows from 1-2 to 1-3 entries depending on which sparse embedders are enabled. `buildPoint()` gains a `bm25Enabled` parameter and `bm25VectorName`.

### Retrieval

The mode selection conditional in both `HybridCaseRetriever` and `ReactiveHybridCaseRetriever` must support all four modes — including BM25-only (no SPLADE). The current code branches on `sparseEmbedder != null`, which drops BM25 when SPLADE is absent. The restructured logic:

```java
boolean useRrf = sparseEmbedder != null || config.bm25Enabled();
if (useRrf) {
    QueryPoints.Builder qb = QueryPoints.newBuilder()
        .setCollectionName(collection);

    // Dense prefetch (always present in RRF mode)
    PrefetchQuery.Builder densePrefetch = PrefetchQuery.newBuilder()
        .setQuery(QueryFactory.nearest(denseEmbedding.vectorAsList()))
        .setUsing(config.denseVectorName())
        .setLimit(config.retrieval().denseTopK());
    if (quantizationType != DenseQuantization.NONE && oversampling.isPresent()) {
        densePrefetch.setParams(quantizationSearchParams());
    }
    mergedFilter.ifPresent(densePrefetch::setFilter);
    qb.addPrefetch(densePrefetch);

    // SPLADE prefetch (when SPLADE embedder is available)
    if (sparseEmbedder != null) {
        PrefetchQuery.Builder sparsePrefetch = /* ... sparse vector construction ... */;
        mergedFilter.ifPresent(sparsePrefetch::setFilter);
        qb.addPrefetch(sparsePrefetch);
    }

    // BM25 prefetch (when BM25 is enabled)
    if (config.bm25Enabled()) {
        String expandedQuery = CamelCaseExpander.expand(query.text());
        PrefetchQuery.Builder bm25Prefetch = PrefetchQuery.newBuilder()
            .setQuery(QueryFactory.nearest(
                Document.newBuilder()
                    .setText(expandedQuery)
                    .setModel(QdrantPointBuilder.BM25_MODEL)
                    .build()))
            .setUsing(config.bm25VectorName())
            .setLimit(config.retrieval().bm25TopK());
        mergedFilter.ifPresent(bm25Prefetch::setFilter);
        qb.addPrefetch(bm25Prefetch);
    }

    qb.setQuery(QueryFactory.rrf(Rrf.newBuilder().setK(config.retrieval().rrfK()).build()))
       .setLimit(queryLimit)
       .setWithPayload(WithPayloadSelectorFactory.enable(true));
    queryPoints = qb.build();
} else {
    // Dense-only: direct nearest-neighbor query (no fusion)
    /* ... existing dense-only code ... */
}
```

RRF handles N legs transparently — 2 (dense+SPLADE or dense+BM25) or 3 (dense+SPLADE+BM25).

**Query text selection:** BM25 uses `query.text()` (original user query), not `query.searchText()` (which may include HyDE expansion). BM25 is keyword matching — hypothetical documents from HyDE would add noise.

**BM25 tokenizer behavior:** The `"qdrant/bm25"` model uses word-level tokenization: splits on whitespace and punctuation, lowercases all tokens. This matches the Word tokenizer used for the text payload index (#47). CamelCaseExpander output is designed for this tokenizer:

Token-level example (document ingestion):
- Source text: `"ConcurrentHashMap is thread-safe"`
- After CamelCaseExpander: `"ConcurrentHashMap Concurrent Hash Map is thread-safe"`
- BM25 tokens: `[concurrenthashmap, concurrent, hash, map, is, thread, safe]`

Token-level example (query):
- Query: `"HashMap"`
- After CamelCaseExpander: `"HashMap Hash Map"`
- BM25 tokens: `[hashmap, hash, map]`
- Term overlap with document: `hash`, `map` → BM25 match with scored relevance

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

    @WithDefault("true")
    boolean bm25Enabled();

    @WithDefault("bm25")
    String bm25VectorName();

    interface RetrievalConfig {
        // existing: denseTopK, sparseTopK, rrfK, rerankEnabled, rerankTopN

        @WithDefault("40")
        int bm25TopK();
    }
}
```

`bm25Enabled` is at the `RagConfig` top level because it governs both ingestion (collection creation, point building) and retrieval (prefetch leg). This parallels how SPLADE enablement works — `SparseEmbedder` bean presence controls both paths. BM25 doesn't have a separate bean (it's server-side), so an explicit top-level flag is the equivalent mechanism. `bm25TopK` stays in `RetrievalConfig` — it is retrieval-specific.

BM25 is enabled by default. The `"qdrant/bm25"` model string is defined as `QdrantPointBuilder.BM25_MODEL` — a named constant shared by both ingest and query paths. It's a Qdrant built-in, not configurable.

### Constructor redesign — pass `RagConfig` directly

Adding BM25 would push `HybridCaseRetriever` from 15 to 18 constructor parameters. The root problem: CDI producers unpack `RagConfig` into individual arguments, creating a wall of positional `int`/`String`/`boolean` parameters that are trivially swappable with no compile-time error.

**Fix:** Retrievers and ingestors take `RagConfig` directly instead of individual config values. These classes are package-private in the same package as `RagConfig` — no tier crossing, no abstraction leak. The constructor signatures become:

```java
// HybridCaseRetriever / ReactiveHybridCaseRetriever
HybridCaseRetriever(QdrantClient client, EmbeddingModel embeddingModel,
    SparseEmbedder sparseEmbedder, TenantGuard tenantGuard,
    CrossEncoderReranker reranker, RagConfig config)

// QdrantEmbeddingIngestor / ReactiveQdrantEmbeddingIngestor
QdrantEmbeddingIngestor(QdrantClient client, EmbeddingModel embeddingModel,
    SparseEmbedder sparseEmbedder, TenantGuard tenantGuard, RagConfig config)
```

6 parameters for retrievers, 5 for ingestors. Adding future config properties is zero-cost — no constructor changes needed. The classes read what they need: `config.retrieval().denseTopK()`, `config.bm25Enabled()`, `config.tenancyStrategy()`, etc.

`QdrantPointBuilder.buildPoint()` remains a pure static method. It gains a `bm25Enabled` and `bm25VectorName` parameter alongside the existing `denseVectorName` and `sparseVectorName` — the method signature grows from 7 to 9 parameters, but these are all semantically distinct types (`ChunkInput`, `CorpusRef`, `Embedding`, `Map<Integer,Float>`, `int`, `String`, `String`, `boolean`, `String`), not a soup of interchangeable `int` values.

### CDI producers

With `RagConfig` passed directly, the producer methods simplify:

```java
@Produces @ApplicationScoped
HybridCaseRetriever caseRetriever() {
    return new HybridCaseRetriever(client, effectiveEmbeddingModel(),
        resolveSparseEmbedder(), resolveTenantGuard(),
        resolveReranker(), config);
}

@Produces @ApplicationScoped
QdrantEmbeddingIngestor corpusStore() {
    return new QdrantEmbeddingIngestor(client, effectiveEmbeddingModel(),
        resolveSparseEmbedder(), resolveTenantGuard(), config);
}
```

Same pattern for both `RagBeanProducer` and `ReactiveRagBeanProducer`.

### In-memory stubs

No changes. The `EmbeddingIngestor` and `CaseRetriever` SPI signatures are unchanged. BM25 is entirely within the Qdrant implementation.

## Files Changed

### rag-api (Tier 1)
- `ChunkInput.java` — add metadata key validation against record field names

### rag (Tier 3)
- `QdrantPointBuilder.java` — add `tenantId` metadata validation, add BM25 vector, add `RESERVED_PAYLOAD_KEYS` shared constant, add `BM25_MODEL` shared constant
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
- `CamelCaseExpanderTest.java` — **new**, test splitting rules (including `XMLHTTPRequest` edge case documenting actual behavior)
- `QdrantPointBuilderTest.java` — test `tenantId` metadata rejection, test BM25 vector inclusion
- `HybridCaseRetrieverTest.java` — test BM25 prefetch leg, test three-way RRF, test BM25-only mode (no SPLADE, verify RRF with dense+BM25)
- `ReactiveHybridCaseRetrieverTest.java` — test BM25 prefetch leg, test BM25-only mode (no SPLADE)
- `QdrantEmbeddingIngestorTest.java` — test BM25 sparse config in collection creation, test fail-fast for missing BM25/SPLADE sparse vectors
- `ReactiveQdrantEmbeddingIngestorTest.java` — test BM25 sparse config in collection creation, test fail-fast for missing BM25/SPLADE sparse vectors

## Protocols Checked

- `qdrant-client-library.md` — using `io.qdrant:client` directly (not langchain4j-qdrant). Confirmed.
- `spi-signature-change-all-impls-same-commit.md` — SPI signatures unchanged. N/A.
- `module-tier-structure.md` — `ChunkInput` validation is in Tier 1 (pure Java). Implementation validation is in Tier 3 (Qdrant). Correct tier placement.
- Issue #48 approach divergence — original #48 describes filter-based BM25 via text payload index; this spec supersedes with server-side BM25 sparse vectors for scored retrieval. See §3 "Approach divergence from #48".

## Garden Entries Referenced

- GE-20260629-0a321f — Qdrant createCollectionAsync idempotency asymmetry (informs ensureCollection design)
- GE-20260609-c1998e — `QueryFactory.rrf(Rrf)` vs `fusion(Fusion.RRF)` — using `rrf()` for configurable k
- GE-20260627-8b0fb8 — PrefetchQuery per-leg SearchParams (oversampling targets dense only, not BM25)
