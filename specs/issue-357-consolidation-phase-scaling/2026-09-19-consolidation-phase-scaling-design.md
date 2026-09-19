# Consolidation Phase Scaling — Approximate Algorithms for Large Subgraphs

**Issue:** casehubio/neocortex#357
**Parent:** casehubio/neocortex#355 (GA audit)
**Date:** 2026-09-19

## Problem

Three scaling cliffs in the consolidation pipeline prevent merge detection,
centrality analysis, and orphan detection from running on large subgraphs:

1. **MergeDetectionPhase.detectCandidates()** — O(n²) pairwise Jaro-Winkler
   comparison plus O(k) per-pair SQL neighbor queries. Hard skip at >500 nodes.
2. **MindMapAnalyzer.betweennessCentrality()** — Full Brandes' O(V(V+E))
   BFS from every node. CuriositySignalGenerator skips at >2000 nodes.
3. **MindMapAnalyzer.orphanNodes()** — V individual `store.neighbors()` SQL
   queries. No guard, but cost grows linearly with subgraph size.

These guards were added as safety caps (#355 P1+P2), not solutions. Large
subgraphs get no merge detection or centrality signals at all.

## Fix 1: Merge Detection — Prefix Bucketing + Bulk Neighbor Pre-Loading

### Analysis

First-principles analysis revealed two independent bottlenecks:

| Bottleneck | Type | Cost at n=5000 |
|---|---|---|
| O(n²) name comparisons | CPU | ~12s (12.5M × 1μs) |
| O(k) neighbor SQL queries | IO | ~250s (if 1% of pairs pass → 250K queries × 1ms) |

Prefix bucketing addresses the CPU bottleneck. Bulk neighbor pre-loading
addresses the IO bottleneck. Together they reduce total cost from
O(n² + k×SQL) to O(n×SQL + Σbᵢ²).

MinHash was evaluated and rejected: bulk pre-loading makes exact in-memory
Jaccard free (~microseconds on small neighbor sets), so approximation adds
no value. MinHash on neighbor sets would enable structure-only merge
detection (different names, same neighbors) — a semantic change out of
scope for this issue.

### Design

Replace `detectCandidates(String subgraphId, String tenantId)`:

**Phase 1 — Bulk pre-load neighbor sets:**
Load all nodes in the subgraph. For each node, call `neighbors()` once
and cache the result in a `Map<String, Set<String>>`. This is O(n) SQL
queries, amortized across all pairs. Memory: O(n × avg_degree × 40B) —
~2MB at n=5000 with avg degree 10.

**Phase 2 — Prefix bucketing:**
Group nodes by their normalized name prefix (lowercase, trimmed, first 3
characters; names shorter than 3 chars use the full name as the key).
Only compare within buckets. For Jaro-Winkler ≥ 0.85, names must be very
similar — prefix sharing is nearly guaranteed. O(n) bucketing + O(Σbᵢ²)
within-bucket comparisons.

**Phase 3 — Evaluate candidates:**
For pairs passing the Jaro-Winkler threshold, compute exact Jaccard from
the pre-loaded neighbor sets. No additional SQL queries. Compute combined
score and proceed with merge/flag as before.

### Guard Update

The 500-node guard can be raised to 10,000 or removed. At n=5000: ~5000
SQL queries (pre-load) + sub-second bucketed name comparison + sub-second
in-memory Jaccard. Total: seconds, not minutes.

### Files Changed

- `MergeDetectionPhase.java` — rewrite `detectCandidates()` with three-phase
  pipeline; add private `prefixBucket()` and `bulkLoadNeighbors()` methods;
  raise or remove the 500-node guard
- `MergeDetectionPhaseTest.java` — tests for prefix bucketing correctness,
  bulk pre-loading, and large-subgraph behavior

## Fix 2: Approximate Betweenness Centrality — Sampled Brandes

### Design

Add a new method to `MindMapAnalyzer`:

```java
public static List<BetweennessCentrality> approximateBetweennessCentrality(
        MindMapStore store, String subgraphId, String tenantId, int k)
```

Implementation: select `k` random source nodes (deterministic via seeded
`Random` for reproducibility), run standard Brandes BFS from each, scale
by `V/k`. Return the same `BetweennessCentrality` records as the exact
method.

Default `k`: `Math.min(nodeCount, 100)`. At k=100, error bounded by
1/√k ≈ 10% — sufficient for a curiosity signal that only needs relative
ranking of top-N nodes.

The existing `betweennessCentrality()` method is preserved unchanged for
callers that need exact results (observability, health reports).

### Caller Update

`CuriositySignalGenerator.collectCentralitySignals()`:
- Remove the 2000-node guard
- Switch to `approximateBetweennessCentrality(store, sg.id(), tenantId, 100)`

### Files Changed

- `MindMapAnalyzer.java` — add `approximateBetweennessCentrality()` method
- `MindMapAnalyzerTest.java` — test approximate vs exact consistency on
  small graphs, verify deterministic seed produces repeatable results
- `CuriositySignalGenerator.java` — remove 2000-node guard, switch to
  approximate method

## Fix 3: Orphan Nodes — SPI Push-Down

### Design

Add a default method to `MindMapStore`:

```java
default List<MindMapNode> nodesWithoutEdges(String subgraphId, String tenantId) {
    return nodesIn(subgraphId, tenantId).stream()
        .filter(n -> neighbors(n.id(), tenantId).isEmpty())
        .toList();
}
```

The default preserves current V-query behavior. Implementations override
with efficient queries:

**SqliteMindMapStore:**
```sql
SELECT n.node_id, n.name, n.subgraph_id, ...
FROM mindmap_node n
WHERE n.subgraph_id = ? AND n.tenant_id = ?
  AND n.node_id NOT IN (
    SELECT source_node_id FROM mindmap_edge WHERE tenant_id = ?
    UNION
    SELECT target_node_id FROM mindmap_edge WHERE tenant_id = ?
  )
```

**InMemoryMindMapStore:** Collect all node IDs that appear as source or
target in any edge, then return nodes not in that set.

`MindMapAnalyzer.orphanNodes()` delegates to `store.nodesWithoutEdges()`
and wraps results in `OrphanNode` records.

### Files Changed

- `MindMapStore.java` — add `nodesWithoutEdges()` default method
- `SqliteMindMapStore.java` — override with single SQL query
- `InMemoryMindMapStore.java` — override with set difference
- `MindMapAnalyzer.java` — simplify `orphanNodes()` to delegate
- `MindMapStoreContractTest.java` — add contract test for `nodesWithoutEdges()`
- `MindMapAnalyzerTest.java` — verify delegation works

## Testing Strategy

- **MergeDetectionPhaseTest:** prefix bucketing correctness (same-prefix
  candidates found, cross-prefix pairs excluded), bulk pre-loading
  coverage, behavior at previous guard boundary (500+ nodes)
- **MindMapAnalyzerTest:** approximate centrality produces same top-N
  ranking as exact on small graphs, deterministic seed, k > V case
- **MindMapStoreContractTest:** `nodesWithoutEdges()` returns nodes with
  no edges, excludes nodes with edges, empty subgraph case
- All existing tests continue passing — no behavioral change for subgraphs
  below the old guard thresholds

## References

- `MergeDetectionPhase.java:88-122` — current O(n²) detectCandidates
- `MindMapAnalyzer.java:42-51` — current orphanNodes V-query loop
- `MindMapAnalyzer.java:156-240` — current Brandes implementation
- `CuriositySignalGenerator.java:157-175` — betweenness caller with 2000-node guard
- `MinHashIndex.java` (rag-api) — evaluated for merge detection, rejected
- `docs/blog/2026-09-18-mdp01-ten-dimension-audit.md:27` — original audit finding
