---
layout: post
title: "Profiling the Right Bottleneck — Consolidation Phase Scaling"
date: 2026-09-19
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [performance, mindmap, consolidation, algorithms]
series: issue-357-consolidation-phase-scaling
---

# Profiling the Right Bottleneck — Consolidation Phase Scaling

The GA audit flagged two scaling cliffs in the consolidation pipeline: `MergeDetectionPhase` does O(n²) pairwise name comparison, and `CuriositySignalGenerator` calls Brandes' betweenness centrality — O(V(V+E)) — on every tick. Both had safety-cap guards (skip at 500 and 2000 nodes respectively). A third issue, `orphanNodes`, was doing V individual SQL queries where one would do.

The interesting part was the merge detection fix. I expected the O(n²) name comparison to be the bottleneck — that's what the issue described. But working through the numbers from first principles told a different story.

At n=5000, the Jaro-Winkler loop generates ~12.5 million comparisons. Each takes about a microsecond. That's ~12 seconds — not great but not terrible. The real cost is what happens next: for each pair that passes the name threshold, two SQL queries fetch neighbor sets for the Jaccard overlap check. If even 1% of pairs pass, that's 125K pairs × 2 queries = 250K SQL round-trips at ~1ms each. **250 seconds of IO**, not 12 seconds of CPU.

The O(n²) comparison is the visible problem. The per-pair SQL amplification is the expensive one.

The fix addresses both dimensions independently. Prefix bucketing groups nodes by the first three characters of their lowercase name — for Jaro-Winkler ≥ 0.85, similar names almost always share a prefix. This reduces candidate pairs from O(n²) to O(Σbᵢ²) where each bucket is much smaller than n. Bulk neighbor pre-loading fetches all neighbor sets once upfront in O(n) queries, cached in a map. Every subsequent Jaccard computation is a microsecond in-memory lookup instead of a SQL round-trip.

I evaluated MinHash (which already exists in `rag-api` for query clustering) and rejected it. Once you've pre-loaded the neighbor sets, exact Jaccard is just as fast as approximate — the sets are small, typically under 50 elements. MinHash would add value for a *different* capability — structure-only merge detection, finding duplicates with different names but shared neighbors. That's a semantic change, not a performance fix.

The other two fixes were straightforward. Sampled Brandes picks k random source nodes (k=100 by default, deterministic seed) instead of running BFS from all V nodes. Error bounded by 1/√k ≈ 10%, which is more than enough for a curiosity signal that only needs the top-N ranking. The orphan detection pushed down to the SPI as a `nodesWithoutEdges` default method — SqliteMindMapStore overrides with a single `NOT IN` query, InMemoryMindMapStore with a set difference.

All three guards are gone. Merge detection, centrality, and orphan detection now work on subgraphs of any size.
