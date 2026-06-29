# Qdrant Payload Indexes — Full-Text and Keyword

**Date:** 2026-06-29
**Issues:** casehubio/neural-text#47, casehubio/neural-text#50
**Module:** `rag` (implementation tier)
**Status:** Design approved

## Problem

Hortora/engine#27 benchmarked gardenSearch (dense-only, nomic-embed-text) against grep across 14 real-world scenarios. Grep won every keyword scenario — queries using Java class names (`@DefaultBean`, `ConcurrentHashMap`, `ChatModel`, `ExceptionMapper`) failed catastrophically with vector search because the embedding model treats domain identifiers as generic English tokens.

Separately, `sourceDocumentId` and `tenantId` are used as keyword filters on every `deleteDocument()`, `deleteCorpus()` (shared tenancy), and `listDocuments()` call via `ConditionFactory.matchKeyword()`, but no explicit payload indexes exist — Qdrant does a linear payload scan for each filter.

## Solution

Add three payload indexes to every Qdrant collection, created during `ensureCollection()`:

| Field | Index Type | Parameters |
|-------|-----------|------------|
| `content` | Text (full-text) | `Word` tokenizer, `lowercase=true`, `min_token_len=2`, `max_token_len=40` |
| `sourceDocumentId` | Keyword | defaults |
| `tenantId` | Keyword | defaults |

For existing collections, missing indexes are detected via `CollectionInfo.payload_schema` and added lazily — no re-ingestion required.

## Tokenizer Choice: Word

Evaluated against actual garden content (40% code, 35% prose, 25% identifiers/config):

- **CamelCase preserved:** `ConcurrentHashMap` → single token `concurrenthashmap`. Exact matching works.
- **Dots split:** `io.casehub.rag.EmbeddingIngestor` → `io`, `casehub`, `rag`, `embeddingingestor`. Enables both component and full-path search.
- **Annotations:** `@DefaultBean` → `defaultbean`. Users search for `DefaultBean`, not `@DefaultBean`.
- **Code punctuation:** `close()` → `close`. Code is searchable by identifier.

`Whitespace` was rejected: `close()` stays as one token (search for `close` won't match), and `@DefaultBean` requires the `@` in the query.

**No stemming.** BM25's purpose is exact matching — what embeddings can't do. Stemming moves back toward fuzzy matching.

**No stopwords.** BM25's IDF weighting naturally down-weights common words.

**Fixed parameters, non-configurable.** The index set is infrastructure, not a user-tunable knob. Different tokenizer settings per corpus would require a much larger design change with no current demand.

## Architecture

### Constraint

Full-text indexes cannot be defined in `CreateCollection` — they require a separate `createPayloadIndexAsync` call afterward. Keyword indexes have the same constraint.

### ensureCollection flow

```
1. knownCollections cache hit → return
2. collectionExistsAsync →
   exists:
     validate dimension (unchanged)
     check payload_schema for missing indexes
     createPayloadIndexAsync for each missing index
     add to cache
   not exists:
     createCollectionAsync (dense + sparse + quantization — unchanged)
     createPayloadIndexAsync for all three indexes
     add to cache
```

### Blocking ingestor (QdrantEmbeddingIngestor)

Private `ensurePayloadIndexes(String collection, Map<String, PayloadSchemaInfo> existingSchema)` method. Checks `existingSchema.containsKey()` for each field. Creates missing indexes sequentially via `.get()`. Called from both the existing-collection and new-collection paths.

### Reactive ingestor (ReactiveQdrantEmbeddingIngestor)

Equivalent `ensurePayloadIndexes` returning `Uni<Void>`. Independent index creation calls run concurrently via `Uni.join().all().andFailFast()`. Chained after dimension validation (existing path) or after `createCollectionAsync` (new path).

### Migration

Lazy — triggered when `ensureCollection` encounters an existing collection without the expected indexes. `getCollectionInfoAsync` is already called for dimension validation; `payload_schema` is checked from the same response. No extra Qdrant round-trip.

`createPayloadIndexAsync` builds the index from existing payload data — no re-ingestion needed. The `wait=true` parameter ensures the index is built before returning.

## Tests

Three new test cases per ingestor class (6 total), using Testcontainers with Qdrant v1.18.0:

1. **New collection gets all payload indexes.** Ingest a chunk, verify `payload_schema` contains `content` (Text), `sourceDocumentId` (Keyword), `tenantId` (Keyword).

2. **Migration — existing collection without indexes.** Create a collection manually (vectors only, no payload indexes). Ingest via the ingestor, triggering `ensureCollection`. Verify all three indexes are added.

3. **Idempotent — already-indexed collection.** Use a fresh ingestor instance against an already-indexed collection. Verify `ensureCollection` re-checks, finds indexes present, completes without error.

## Scope boundaries

- **No retrieval changes.** Full-text index is unused until #48 adds a BM25 prefetch leg.
- **No SPI changes.** `EmbeddingIngestor`, `CaseRetriever` interfaces unchanged.
- **No RagConfig changes.** No new configuration properties.
- **No rag-api changes.** Everything stays in `rag` module (Tier 3).
- **No CDI wiring changes.** No new constructor parameters.

## Related

- casehubio/neural-text#48 — BM25 as third RRF leg (depends on this index existing)
- Hortora/engine#27 — dense-only benchmark proving the keyword gap
- Hortora/engine#28 — SPLADE hybrid benchmark (in progress)
- GE-20260627-4712de — garden entry documenting the nomic-embed-text keyword gap
