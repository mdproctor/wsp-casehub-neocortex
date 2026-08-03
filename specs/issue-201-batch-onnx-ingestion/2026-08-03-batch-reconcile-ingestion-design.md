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
calling `ingest()` — adopt the same pattern `doProcessBinding()` already uses.

### Current flow (per document)

```
for each missing document:
    read content → extract metadata → chunk → ingest(corpusRef, chunks)
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
    ingest(corpusRef, allChunks)
save cursor
```

## What Changes

**`CorpusIngestionService.doReconcile()`** — the only production code change.
Collect chunks from all missing documents into a single list, then call
`ingestor.ingest(corpusRef, allChunks)` once. Per-document extraction errors
are caught and logged with `continue` — same error-handling pattern as
`doProcessBinding()`.

## What Does Not Change

- **`EmbeddingIngestor` SPI** — no new methods. `ingest(CorpusRef, List<ChunkInput>)`
  already accepts a list.
- **`QdrantEmbeddingIngestor`** — already batches internally at `embeddingBatchSize`.
- **`OnnxInferenceModel.runBatch()`** — already pads and runs single forward pass.
- **`BgeM3Embedder.embedBatch()`** — already delegates to `runBatch()`.
- **`doProcessBinding()` and `doProcessWatchEvent()`** — already batch correctly.
- **`embeddingBatchSize` config** (default 100) — unchanged.
- **Cursor semantics** — `doReconcile()` saves cursor once at the end regardless
  of partial failure. Reconcile is idempotent — re-running catches missed documents.

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

For 4900 documents × 3 chunks/doc × ~500 chars/chunk = ~7.5 MB of text in the
`allChunks` list. Negligible relative to the ONNX model's memory footprint (~2-6 GB).

## Testing

- Existing `CorpusIngestionServiceTest` — verify reconcile still works.
- New test: reconcile with multiple missing documents verifies all chunks are collected
  and ingested in a single `ingest()` call rather than per-document calls.
- Edge cases: empty corpus, all documents already indexed, single missing document,
  extraction failure on one document does not block others.

## Performance

| Scenario | Before | After (batch 8) | After (batch 100) |
|----------|--------|------------------|--------------------|
| 4900 docs, ~3 chunks/doc | ~4900 ONNX passes | ~1838 passes | ~147 passes |
| Wall clock (Hortora) | ~56 min | ~20 min | ~2-5 min |
| 50K docs (projected) | ~52 hours | ~19 hours | ~1.5-4 hours |

Actual improvement depends on `casehub.rag.embedding-batch-size` configuration.
Users running BGE-M3 should set this to 8-16 based on available RAM.
