# embedAll Batching — QdrantEmbeddingIngestor

**Issue:** hortora/engine#26
**Date:** 2026-06-25
**Status:** Approved (rev 2 — post review)

## Problem

`QdrantEmbeddingIngestor.ingest()` passes all chunks to three unbounded operations:

1. `embeddingModel.embedAll(segments)` — single HTTP request to Ollama
2. `sparseEmbedder.embedBatch(texts)` — single ONNX inference allocating batchSize x maxTokens arrays
3. `client.upsertAsync(collection, points)` — single gRPC message to Qdrant

With ~6,500 garden entries, Ollama returns 400 Bad Request. LangChain4j's `EmbeddingModel.embedAll()` has no built-in batching — the interface is a raw method that providers implement directly.

## Design Decision

Batching belongs inside the Qdrant implementations, not in the SPI or the caller.

**Why not the SPI?** `EmbeddingIngestor.ingest(CorpusRef, List<ChunkInput>)` is a semantic contract: "ingest these chunks." Batch size is a tier-3 infrastructure concern (HTTP body limits, gRPC message size, ONNX memory). Tier-1 SPIs must not leak provider-specific constraints.

**Why not the caller?** `CorpusIngestionService` doesn't know and shouldn't know about Ollama HTTP limits. Every future caller would need to re-implement batching. The deterministic chunk index counter would need to be managed externally, violating the SPI's opacity. `doProcessBinding()` and `doProcessWatchEvent()` would both need identical batching logic — duplicated with no SPI to standardize it. `doReconcile()` ingests per-document and wouldn't need batching at all — so the caller has no consistent policy.

**Why the implementation?** The ingestor orchestrates all three subsystems that have size limits. It's the only layer that can batch all three in lockstep while preserving deterministic IDs. Idempotent upsert (deterministic UUIDs from `sourceDocumentId + chunkIndex`) makes partial-batch failure safe — the caller doesn't advance the cursor on exception, so the next poll retries everything.

## Shared Logic Extraction — QdrantPointBuilder

`buildPoint()` is duplicated verbatim between `QdrantEmbeddingIngestor` and `ReactiveQdrantEmbeddingIngestor`. Batching adds `computeChunkIndices()` — also pure, also identical in both. Extract both to a package-private utility:

```java
final class QdrantPointBuilder {
    static int[] computeChunkIndices(List<ChunkInput> chunks) { ... }
    static PointStruct buildPoint(ChunkInput chunk, CorpusRef corpus,
            Embedding denseEmbedding, Map<Integer, Float> sparseMap,
            int chunkIndex, String denseVectorName, String sparseVectorName) { ... }
}
```

This is shared pure computation — no I/O, no threading model, no Mutiny. The reactive-blocking-tier-separation protocol forbids reactive deps in the blocking tier and vice versa; pure computation via a utility violates neither. Extracting before adding batching reduces duplication and makes the batch loop in each implementation purely orchestration.

## Batch Loop Structure

### Step 0 — Validate and ensure collection

`ensureCollection(collection)` runs once before the batch loop. Not per-batch — the collection exists after the first call.

### Step 1 — Pre-compute chunk indices

Before batching begins, iterate all chunks once to build per-document counters. Store the computed index for each chunk position. This ensures deterministic UUIDs are identical regardless of batch size.

```
chunks:        [A#0, A#1, B#0, A#2, B#1, ...]
chunkIndices:  [0,   1,   0,   2,   1,   ...]
```

Pre-computing makes the invariant trivially verifiable — indices are assigned once, before any I/O, so batch boundaries cannot affect them. A counter carried across batch iterations would produce identical results but ties correctness to loop structure.

### Step 2 — Iterate in windows

```
ensureCollection(collection)           — once, before loop
int[] indices = computeChunkIndices(chunks)  — once, before loop

for each window of batchSize chunks (with their pre-computed indices):
    1. embedAll(segments)      — dense embedding via LangChain4j
    2. embedBatch(texts)       — sparse embedding via ONNX (if available)
    3. buildPoints(...)        — construct Qdrant PointStructs
    4. upsertAsync(points)     — push to Qdrant
```

**Failure semantics:** Throw immediately on any step. No partial-success tracking. `CorpusIngestionService` doesn't advance the cursor on exception. Already-upserted chunks from earlier batches get re-upserted on retry (idempotent — same UUID = update, not duplicate).

**Progress logging:** Log at batch completion: `"Ingested batch {n}/{total} ({chunksProcessed}/{totalChunks} chunks)"`. For a 6,500-chunk fullScan with batch size 100, that's 65 log lines — sufficient for operational visibility without being noisy.

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

One batch size for all three operations — they're lockstep, and the tightest constraint (Ollama HTTP) determines the effective limit.

**Default 100 justification:** At 100 items x ~500 chars average, the Ollama HTTP body is ~50 KB (well within limits). ONNX Runtime allocates ~100 x 512 x 3 x 8 bytes ≈ 1.2 MB for token arrays (trivial). Qdrant upsert with 100 points at ~3 KB each (768-dim dense + sparse + payload) is ~300 KB (well under the 256 MB gRPC default max message size).

## Constructor Changes

Both `QdrantEmbeddingIngestor` and `ReactiveQdrantEmbeddingIngestor` gain a `int batchSize` parameter. Both producers (`RagBeanProducer`, `ReactiveRagBeanProducer`) read `config.embeddingBatchSize()` and pass it through.

**Constructor validation:** `batchSize <= 0` throws `IllegalArgumentException`. Consistent with `SparseEmbedder`'s constructor which validates `threshold`. Without this, a misconfigured `casehub.rag.embedding-batch-size=0` would produce an infinite loop at runtime.

## Affected Files

### Production (6 files)

| File | Change |
|------|--------|
| `RagConfig.java` | Add `embeddingBatchSize()` with default 100 |
| `QdrantPointBuilder.java` | **New** — package-private utility: `computeChunkIndices()` + `buildPoint()` extracted from both implementations |
| `QdrantEmbeddingIngestor.java` | `batchSize` field + constructor param + validation, batch loop with pre-computed indices, delegate `buildPoint` to `QdrantPointBuilder` |
| `ReactiveQdrantEmbeddingIngestor.java` | Same — `batchSize` field + validation, `Multi`-based batch loop, delegate `buildPoint` to `QdrantPointBuilder` |
| `RagBeanProducer.java` | Pass `config.embeddingBatchSize()` to constructor |
| `ReactiveRagBeanProducer.java` | Pass `config.embeddingBatchSize()` to constructor |

### Tests (5 files — constructor signature change)

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
4. **batchSize = 1**: Every chunk gets its own batch — exercises maximum iterations and single-element subList
