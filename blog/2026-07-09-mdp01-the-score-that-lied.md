---
title: "The Score That Lied"
date: 2026-07-09
entry_type: note
subtype: diary
projects: [casehub-neocortex]
tags: [rag, cross-encoder, reranking, scoring]
---

## The Score That Lied

After cross-encoder reranking, every chunk carries two scores: the original vector similarity (how close the embedding was) and the cross-encoder score (how relevant the content actually is to the query). The cross-encoder reorders the results — a chunk ranked 8th by vector similarity might be 1st by cross-encoder. The reranker got this right. What it got wrong was which score it left in `relevanceScore`.

`relevanceScore` is the field downstream consumers use for gap detection, threshold filtering, and confidence signals. After reranking, it still held the vector similarity — the score from the leg that was just overruled. A chunk promoted to the top by the cross-encoder still reported its mediocre vector similarity as its relevance. Downstream logic that filtered on `relevanceScore > 0.7` would discard the cross-encoder's best picks while keeping chunks the reranker had pushed down.

The fix is small: promote the cross-encoder score to `relevanceScore` and stash the original vector similarity in metadata under `_vectorSimilarity`. After reranking, `relevanceScore` reflects the signal that determined the ordering. Consumers that specifically need the vector similarity can still find it.

The subtlety is in the metadata key design. `RerankingLogic` already uses `_crossEncoderScore` to carry scores between CRAG and reranking — when both decorators are active, CRAG's quality filter produces scores that the reranker can reuse, avoiding a second BERT forward pass. That key is a data propagation channel. The `_reranked` stamp is an execution guard — it prevents double-application through the blocking-to-reactive bridge.

Three keys, three purposes: `_crossEncoderScore` for score propagation between decorators, `_vectorSimilarity` for preserving the original signal, `_reranked` for execution guarding. Conflating any two would break the system — CRAG's score propagation would trigger the reranker's guard, or the preserved vector similarity would be mistaken for a pre-computed reranking score. Each key exists because the three concerns are genuinely independent.
