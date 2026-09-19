## D1: Merge detection scaling strategy

**Choice:** Hybrid — prefix bucketing (name pruning) + bulk neighbor pre-loading (IO amortization)
**Alternatives:**
- Prefix bucketing alone — reduces CPU O(n²) but leaves per-pair SQL bottleneck untouched
- Character n-gram MinHash — unnecessary given bulk pre-loading makes exact Jaccard free; adds complexity and cross-module dependency for no throughput gain
- MinHash on neighbor sets for structure-only merge detection — genuine value but changes merge semantics (new class of duplicates), out of scope for #357
**Rationale:** First-principles analysis shows two independent bottlenecks: O(n²) CPU name comparisons (fixed by prefix bucketing) and O(k) per-pair SQL neighbor queries (fixed by bulk pre-loading all neighbor sets once per subgraph). Together they reduce total cost from O(n² + k*SQL) to O(n*SQL + Σbᵢ²). Exact in-memory Jaccard is microseconds on pre-loaded sets — approximation adds no value.
**Trade-offs:** Bulk pre-loading uses O(n * avg_degree * 40B) memory (~2MB at n=5000). Prefix bucketing degenerates when many names share a prefix, but this is unlikely for knowledge graph entity names.
**Sources:** MergeDetectionPhase.java:88-122 (current O(n²) loop), MinHashIndex.java (rag-api — evaluated and rejected for this use case), CuriositySignalGenerator.java:160 (2000-node guard reference)
**Exploration:** deep-analysis
**Status:** captured

## D2: Betweenness centrality approximation

**Choice:** Sampled Brandes with fixed k, exposed as a separate `approximateBetweennessCentrality(store, subgraphId, tenantId, k)` method on MindMapAnalyzer
**Alternatives:**
- Pivoted Brandes (Geisberger et al.) — degree-weighted pivot selection for better accuracy at same k; marginal benefit when only the top-N ranking matters
- Auto-detect inside existing method — hides the approximation from callers, prevents exact computation when needed (observability, health reports)
**Rationale:** Curiosity signal generator only needs relative ranking of top-N central nodes, not exact scores. Sampled Brandes at k=100 gives ~10% relative error (1/√k), which is more than sufficient. Separate method lets callers choose: CuriositySignalGenerator always calls approximate, observability uses exact for small graphs. The 2000-node guard in CuriositySignalGenerator can be removed.
**Trade-offs:** Two methods on the API surface. Callers must choose which to use.
**Sources:** MindMapAnalyzer.java:156-240 (current Brandes), CuriositySignalGenerator.java:160 (2000-node guard)
**Exploration:** quick
**Status:** captured

## D3: Orphan nodes query optimization

**Choice:** Add `nodesWithoutEdges(subgraphId, tenantId)` default method to MindMapStore SPI, returning `List<MindMapNode>`. SqliteMindMapStore overrides with single SQL `NOT IN` query. InMemoryMindMapStore overrides with set difference. MindMapAnalyzer.orphanNodes() delegates to the store method.
**Alternatives:**
- Bulk pre-load edges in MindMapAnalyzer — still O(n) SQL queries for neighbor loading; no SPI change but doesn't fix the root cause
- Add batch `hasEdges(Set<String>)` to SPI — more generic but no caller besides orphanNodes needs it; over-engineering
**Rationale:** Orphan detection is a store-level query concern — the store knows its schema and can express "nodes without edges" in a single indexed query. The default method on the SPI interface preserves backward compatibility for all implementations (falls back to current V-query approach). Benefits any future caller, not just MindMapAnalyzer.
**Trade-offs:** One new default method on the SPI surface. Trivial — the default preserves current behavior.
**Sources:** MindMapAnalyzer.java:42-51 (current V-query loop), MindMapStore.java (SPI — no edgesIn method exists), SqliteMindMapStore.java:641 (neighbors SQL)
**Exploration:** quick
**Status:** captured
