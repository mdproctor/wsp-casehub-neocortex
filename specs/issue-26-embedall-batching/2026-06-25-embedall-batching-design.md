# embedAll Batching — QdrantEmbeddingIngestor

**Issue:** hortora/engine#26
**Date:** 2026-06-25
**Status:** Approved

## Problem

`QdrantEmbeddingIngestor.ingest()` passes all chunks to three unbounded operations:

1. `embeddingModel.embedAll(segments)` — single HTTP request to Ollama
2. `sparseEmbedder.embedBatch(texts)` — single ONNX inference allocating batchSize x maxTokens arrays
3. `client.upsertAsync(collection, points)` — single gRPC message to Qdrant

With ~6,500 garden entries, Ollama returns 400 Bad Request. LangChain4j's `EmbeddingModel.embedAll()` has no built-in batching — it forwards the full list to the provider.

## Design Decision

Batching belongs inside the Qdrant implementations, not in the SPI or the caller.

**Why not the SPI?** `EmbeddingIngestor.ingest(CorpusRef, List<ChunkInput>)` is a semantic contract: "ingest these chunks." Batch size is a tier-3 infrastructure concern (HTTP body limits, gRPC message size, ONNX memory). Tier-1 SPIs must not leak provider-specific constraints.

**Why not the caller?** `CorpusIngestionService` doesn't know and shouldn't know about Ollama HTTP limits. Every future caller would need to re-implement batching. The deterministic chunk index counter would need to be managed externally, violating the SPI's opacity. `doReconcile()` already ingests per-document — inconsistent with batch-in-caller.

**Why the implementation?** The ingestor orchestrates all three subsystems that have size limits. It's the only layer that can batch all three in lockstep while preserving deterministic IDs. Idempotent upsert (deterministic UUIDs from `sourceDocumentId + chunkIndex`) makes partial-batch failure safe — the caller doesn't advance the cursor on exception, so the next poll retries everything.

## Batch Loop Structure

### Step 1 — Pre-compute chunk indices

Before batching begins, iterate all chunks once to build per-document counters. Store the computed index for each chunk position. This ensures deterministic UUIDs are identical regardless of batch size.

```
chunks:        [A#0, A#1, B#0, A#2, B#1, ...]
chunkIndices:  [0,   1,   0,   2,   1,   ...]
```

### Step 2 — Iterate in windows

```
for each window of batchSize chunks (with their pre-computed indices):
    1. embedAll(segments)      — dense embedding via LangChain4j
    2. embedBatch(texts)       — sparse embedding via ONNX (if available)
    3. buildPoints(...)        — construct Qdrant PointStructs
    4. upsertAsync(points)     — push to Qdrant
```

**Failure semantics:** Throw immediately on any step. No partial-success tracking. `CorpusIngestionService` doesn't advance the cursor on exception. Already-upserted chunks from earlier batches get re-upserted on retry (idempotent — same UUID = update, not duplicate).

### Blocking path

Plain `for` loop over `chunks.subList(start, end)`.

### Reactive path

`Multi.createFrom().iterable(batches).onItem().transformToUniAndConcatenate(batch -> processBatch(...))` — sequential processing. No concurrent batches (memory-safe, won't overwhelm the embedding service).

## Configuration

Single property on `RagConfig`:

```java
@WithDefault("100")
int embeddingBatchSize();
```

Config key: `casehub.rag.embedding-batch-size`

One batch size for all three operations — they're lockstep, and the tightest constraint (Ollama HTTP) determines the effective limit. Default 100: conservative enough for all providers.

## Constructor Changes

Both `QdrantEmbeddingIngestor` and `ReactiveQdrantEmbeddingIngestor` gain a `int batchSize` parameter. Both producers (`RagBeanProducer`, `ReactiveRagBeanProducer`) read `config.embeddingBatchSize()` and pass it through.

## Affected Files

### Production (5 files)

| File | Change |
|------|--------|
| `RagConfig.java` | Add `embeddingBatchSize()` with default 100 |
| `QdrantEmbeddingIngestor.java` | `batchSize` field + constructor param, batch loop with pre-computed indices |
| `ReactiveQdrantEmbeddingIngestor.java` | Same — `batchSize` field, `Multi`-based batch loop |
| `RagBeanProducer.java` | Pass `config.embeddingBatchSize()` to constructor |
| `ReactiveRagBeanProducer.java` | Pass `config.embeddingBatchSize()` to constructor |

### Tests (5 files)

| File | Change |
|------|--------|
| `QdrantEmbeddingIngestorTest.java` | Add `batchSize` to constructors, add batching tests |
| `ReactiveQdrantEmbeddingIngestorTest.java` | Same |
| `HybridCaseRetrieverTest.java` | Add `batchSize` to ingestor constructors |
| `ReactiveHybridCaseRetrieverTest.java` | Same |
| `AssertTenantReactiveTest.java` | Same |

### Not changed

- `EmbeddingIngestor` / `ReactiveEmbeddingIngestor` SPI — batching is an implementation concern
- `CorpusIngestionService` — caller doesn't know about batching
- `InMemoryEmbeddingIngestor` / `InMemoryReactiveEmbeddingIngestor` — no batching needed
- `BlockingToReactiveEmbeddingIngestor` — delegates to blocking impl which handles its own batching

### New tests

1. **Batching splits correctly**: Ingest N chunks with batchSize M < N, verify all chunks land in Qdrant with correct deterministic IDs
2. **Cross-batch document continuity**: A single document's chunks span two batches, verify chunk indices are continuous (pre-computed, not reset per batch)
3. **batchSize >= chunks**: Degenerates to single batch — same as current behaviour
