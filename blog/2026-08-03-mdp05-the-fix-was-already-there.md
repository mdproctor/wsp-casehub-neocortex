---
layout: post
title: "The Fix Was Already There"
date: 2026-08-03
type: phase-update
entry_type: note
subtype: diary
projects: [casehub-neocortex]
tags: [onnx, inference, performance, rag, corpus-ingestion]
---

## The Fix Was Already There

Hortora's full reindex of ~4900 garden entries takes 56 minutes. Each entry runs through BGE-M3 for dense, sparse, and ColBERT vectors — one ONNX forward pass per entry. The issue proposed adding batch inference: pad multiple texts to max sequence length, run a single forward pass, get a 4-8x throughput improvement.

I started by tracing the actual pipeline, and the first thing I found was that batch inference already existed. The entire chain supports it: `OnnxInferenceModel.runBatch()` pads inputs and runs one forward pass. `BgeM3Embedder.embedBatch()` delegates to it. `QdrantEmbeddingIngestor.ingest()` splits incoming chunks into batches of `embeddingBatchSize` and calls `embedBatch()` for each. The infrastructure was built and proven.

The bottleneck was one method not using it.

`CorpusIngestionService` has two paths for processing corpus entries. `doProcessBinding()` — the incremental path — collects all chunks from all documents into a single list, then calls `ingest()` once. The ONNX batch fills properly. `doReconcile()` — the full-scan path used during reindex — calls `ingest()` per document. Each document has 1-3 chunks, so each ONNX forward pass processes 1-3 texts instead of filling the batch. At `embeddingBatchSize=100`, that's ~4900 nearly-empty forward passes instead of ~49 full ones.

The fix was to make `doReconcile()` collect chunks the same way `doProcessBinding()` already did. One method, ~20 lines changed.

### What the review caught

The design review surfaced something I'd glossed over. `DedupEmbeddingIngestor` is a CDI decorator that checks each chunk against Qdrant for near-duplicates before ingesting. In the per-document flow, document A's chunks are in Qdrant before document B is processed — so dedup catches cross-document duplicates. In the batched flow, neither A nor B is in Qdrant when the other is checked. Near-duplicates within the same reconcile pass can slip through.

This matters less than it sounds — dedup is disabled by default and reconcile is a reindex operation, not incremental ingestion. But the reviewers were right to flag it: a performance optimisation that silently changes dedup semantics is the kind of thing that bites someone six months later.

The review also caught a contradiction in the spec. I'd written "same pattern as `doProcessBinding()`" for the cursor semantics, but `doProcessBinding()` withholds the cursor on failure while `doReconcile()` always saves it. Different methods, different contracts. The spec needed to say which one it meant and why. For reconcile, always saving is correct — it compares corpus vs Qdrant state directly and doesn't rely on cursor position for correctness.

The five garden entries surfaced during work-start were all directly relevant — particularly the one about batch size changing embedding output through attention mask padding. That's inherent to transformer batching and already present in the incremental path, but worth acknowledging explicitly when the reconcile path starts batching too.

The pattern here is one I keep seeing: the optimisation infrastructure is already built, but one code path doesn't use it. The fix isn't new capability — it's consistency.
