---
title: "One Model, Three Signals"
date: 2026-06-30
entry_type: note
subtype: diary
projects: [casehub-neocortex]
tags: [inference, bge-m3, multi-modal, rag, embedding]
---

## One Model, Three Signals

The RAG pipeline had three retrieval legs — dense embeddings, SPLADE sparse vectors, and BM25 — each requiring its own model or inference path. Dense embeddings went through LangChain4j's `EmbeddingModel`. SPLADE went through our custom `SparseEmbedder`. BM25 used Qdrant's server-side inference. Three separate codepaths for what BGE-M3 can produce in a single forward pass.

BGE-M3 outputs dense, sparse, and ColBERT multi-vectors from one ONNX model. The existing abstractions couldn't represent that — `EmbeddingModel` returns a single dense vector, `SparseEmbedder` returns a sparse map, and neither knows about ColBERT. We needed a unified SPI that captures all three in one call.

`MultiModalEmbedder` is the result. One interface, one forward pass, three output modalities. The implementation (`BgeM3Embedder`) wraps `OnnxInferenceModel` and extracts all three representations from the model's multi-output tensor. That required extending `OnnxInferenceModel` itself — it previously assumed single-output models. The evolution to multi-output support, including rank-3 tensor handling for ColBERT's per-token embeddings, was the bulk of the work.

The interesting part was `InferenceOutput`. It had been a simple record wrapping `float[][]`. Multi-output models produce named tensors — `dense_vecs`, `lexical_weights`, `colbert_vecs` — each with different shapes. The record became a final class wrapping `Map<String, float[][]>` with deep defensive copies on every access. Named outputs, arbitrary dimensionality, immutable. The old single-output API survived as a convenience method that returns the first (or only) output.

The RAG pipeline migration followed naturally. `HybridCaseRetriever` and all reactive variants switched from accepting `EmbeddingModel` + `SparseEmbedder` separately to accepting `MultiModalEmbedder`. The three-leg assembly still fans out to dense, sparse, and BM25 prefetches — but the embedding computation is a single call instead of two. `MatryoshkaEmbeddingModel` became `MatryoshkaMultiModalEmbedder`, dimension truncation applied to the dense output while sparse and ColBERT pass through unchanged.

ColBERT multi-vectors needed their own Qdrant storage — a separate named vector space with per-token vectors. The retriever assembles a MAX_SIM two-stage query: ColBERT prefetch for candidate generation, then RRF fusion with the other legs. Four-way fusion when all modalities are active.
