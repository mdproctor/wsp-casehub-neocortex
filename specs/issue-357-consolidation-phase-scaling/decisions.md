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
