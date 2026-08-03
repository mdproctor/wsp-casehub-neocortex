# Batch Reconcile Ingestion — Design Spec

**Issue:** casehubio/neocortex#201
**Date:** 2026-08-03
**Module:** rag (CorpusIngestionService)

## Problem

`CorpusIngestionService.doReconcile()` calls `ingestor.ingest()` per document
during full-scan reconciliation. Each call embeds 1-3 chunks in a separate ONNX
forward pass. With ~4900 documents (Hortora garden corpus), this produces ~4900
ONNX forward passes instead of ~49 at batch size 100 — a 56-minute reindex.

The rest of the pipeline already supports batching:
- `OnnxInferenceModel.runBatch()` pads inputs to max length, runs a single forward pass
- `BgeM3Embedder.embedBatch()` delegates to `runBatch()`
- `QdrantEmbeddingIngestor.ingest(List<ChunkInput>)` splits chunks into batches
  of `embeddingBatchSize` and calls `embedder.embedBatch()` per batch

`doProcessBinding()` and `doProcessWatchEvent()` already collect all chunks before
calling `ingest()` once. Only `doReconcile()` is unbatched.

## Fix

Refactor `doReconcile()` to collect chunks from all missing documents before
calling `ingest()` — adopt the same chunk-collection pattern `doProcessBinding()`
already uses.

### Current flow (per document)

```
for each missing document:
    read content → extract metadata → chunk → ingest(corpusRef, chunks)
for each stale document (in Qdrant but not in corpus):
    deleteDocument(corpusRef, path)
save cursor
```

### New flow (batched)

```
allChunks = []
for each missing document:
    try:
        read content → extract metadata → chunk → allChunks.addAll(chunks)
    catch:
        log warning, continue
if allChunks not empty:
    try:
        ingest(corpusRef, allChunks)
    catch:
        log warning
for each stale document (in Qdrant but not in corpus):
    try:
        deleteDocument(corpusRef, path)
    catch:
        log warning
save cursor
```

## What Changes

**`CorpusIngestionService.doReconcile()`** — the only production code change.
Collect chunks from all missing documents into a single list, then call
`ingestor.ingest(corpusRef, allChunks)` once. Per-document extraction errors
are caught and logged with `continue`. The `ingest()` call is also try-caught —
a Qdrant failure during ingestion does not prevent stale-document deletion or
cursor advancement. The stale-document deletion loop is unchanged.

## Fault Isolation

**Trade-off acknowledged:** the current per-document `ingest()` provides
per-document fault isolation — if document 2500 fails, documents 2501-4900
still succeed. The batched approach degrades this to per-batch granularity
inside `QdrantEmbeddingIngestor` — a Qdrant failure at batch 30/49 abandons
batches 31-49.

This is the same trade-off `doProcessBinding()` already makes. Reconcile is
idempotent — re-running catches any documents missed due to a transient Qdrant
failure. The throughput gain (56 min → 2-5 min) justifies the coarser fault
isolation.

## Cursor Semantics

Reconcile always saves cursor at the end, regardless of partial failure. This
differs from `doProcessBinding()` (which withholds cursor on failure) because
the two methods serve different purposes:

- `doProcessBinding()` is cursor-driven: withholding cursor ensures failed
  entries are retried on next poll.
- `doReconcile()` is full-scan: it compares corpus vs Qdrant state directly
  and does not rely on cursor position for correctness. The cursor marks
  "full scan completed" — re-running reconcile catches anything missed.

This change adopts `doProcessBinding()`'s chunk-collection pattern, not its
cursor policy.

## Crash Recovery

Issue #201 raised cursor-per-batch as a design consideration. This spec does
not implement intermediate checkpointing because:

- The fix reduces 56-minute reconciles to 2-5 minutes — the crash window
  shrinks by an order of magnitude.
- Reconcile is idempotent — a crash + re-run catches everything.
- Intermediate checkpointing would require splitting `allChunks` into groups
  and introducing ingest-checkpoint-ingest loops, adding complexity for a
  scenario largely eliminated by this fix.

If the 50K-doc projection (1.5-4 hours) becomes real, intermediate
checkpointing can be added as a follow-up.

## DedupEmbeddingIngestor

`DedupEmbeddingIngestor` (@Decorator @Priority(50)) wraps `EmbeddingIngestor`.
Two interactions with this change:

**Performance:** when dedup is enabled, `isDuplicate()` calls
`embedder.embed(chunk.content())` — a single-chunk ONNX forward pass — for
every chunk before the batch reaches `QdrantEmbeddingIngestor`. The
performance numbers below assume dedup is disabled (the default).

**Behavioral:** in the current per-document flow, document A's chunks are
ingested before document B is processed, so dedup catches cross-document
duplicates. In the batched flow, neither A nor B is in Qdrant when dedup runs,
so cross-document near-duplicates within the same reconcile pass may slip
through. This is acceptable because dedup is disabled by default and reconcile
is a reindex operation — dedup is primarily useful for incremental ingestion.

## What Does Not Change

- **`EmbeddingIngestor` SPI** — no new methods. `ingest(CorpusRef, List<ChunkInput>)`
  already accepts a list.
- **`QdrantEmbeddingIngestor`** — already batches internally at `embeddingBatchSize`.
- **`OnnxInferenceModel.runBatch()`** — already pads and runs single forward pass.
- **`BgeM3Embedder.embedBatch()`** — already delegates to `runBatch()`.
- **`doProcessBinding()` and `doProcessWatchEvent()`** — already batch correctly.
- **`embeddingBatchSize` config** (default 100) — unchanged.

## Garden Context

- **GE-20260701-f7e1d5** (ColBERT CLS token off-by-one in `runBatch()`): no impact —
  `runBatch()` already handles ColBERT stripping correctly.
- **GE-20260726-f2a554** (batch size changes embeddings due to padding/attention masks):
  acknowledged — reconcile results may differ slightly from incremental ingestion due
  to different batch composition. This is inherent to transformer batching and already
  applies to `doProcessBinding()`.
- **GE-20260703-eca34b** (stale cursor on empty fullScan): no impact — `doReconcile()`
  always saves cursor at end regardless of whether chunks were found.
- **GE-20260630-db5dce** (BGE-M3 sparse ReLU vs SPLADE log-saturation): no impact —
  post-processing is per-output and batch-agnostic.
- **GE-20260729-b7e9a2** (batch tokenization padding changes attention masks): same as
  GE-20260726-f2a554 — inherent to transformer batching, already applies to
  `doProcessBinding()`.

## Memory

**Chunk list:** for 4900 documents × 3 chunks/doc × ~500 chars/chunk = ~7.5 MB
of text. Negligible relative to the ONNX model's memory footprint (~2-6 GB).

**ONNX batch memory:** bounded by `embeddingBatchSize` in `QdrantEmbeddingIngestor`,
not by the total chunk count. At batch size 8, BGE-M3 (768 tokens × 1024-dim)
needs ~6 GB RAM. At batch size 100, proportionally more. This is unchanged by
this fix — it was always the case.

**Tail risk:** corpora with large documents (Tika-processed PDFs) can produce
hundreds of chunks per document. The `allChunks` list grows with total chunk
count, not document count. For realistic corpora this is manageable; extreme
cases (50K docs, 2% large PDFs with 1000+ chunks each) could reach hundreds of
MB. If this becomes a concern, a configurable collection window can be added.

## Testing

- Existing `CorpusIngestionServiceTest` — verify reconcile still works.
- New test: reconcile with multiple missing documents verifies all chunks are collected
  and ingested in a single `ingest()` call rather than per-document calls.
- Edge cases: empty corpus, all documents already indexed, single missing document,
  extraction failure on one document does not block others, ingest failure does not
  prevent stale-document deletion.

## Performance

Performance numbers assume dedup is disabled (the default).

| Scenario | Before | After (batch 8) | After (batch 100) |
|----------|--------|------------------|--------------------|
| 4900 docs, ~3 chunks/doc | ~4900 ONNX passes | ~1838 passes | ~147 passes |
| Wall clock (Hortora) | ~56 min | ~20 min | ~2-5 min |
| 50K docs (projected) | ~52 hours | ~19 hours | ~1.5-4 hours |

Actual improvement depends on `casehub.rag.embedding-batch-size` configuration.
Users running BGE-M3 should set this to 8-16 based on available RAM.
