## D1: ConversationBridge — DraftHouse KnowledgeFacet, not a new neocortex module

**Choice:** The conversation-to-knowledge bridge is a new DraftHouse Facet (`KnowledgeFacet`) that reuses DraftHouse's existing NotesPipeline for cleanup and depends on neocortex's MindMapExtractor for knowledge extraction. DraftHouse is the orchestration host; neocortex stays a library. A separate UI will integrate the document view with graph visualization of the resulting organized data.
**Alternatives:**
- New module in neocortex (e.g. mindmap-drafthouse) — keeps MindMap logic in neocortex but creates an awkward dependency direction where neocortex depends on DraftHouse's api
- Shared extraction SPI in a new module — more modular but more moving parts for what is fundamentally a pipeline stage
**Rationale:** DraftHouse already owns the session lifecycle, facet composition, NotesPipeline cleanup, and the UI surface. The bridge is naturally a facet that chains cleanup → extraction → storage. MindMapExtractor and MindMapStore are CDI beans that the facet simply injects. Graph visualization is a UI concern that a separate UI integrates — it's not the pipeline's responsibility to render.
**Trade-offs:** DraftHouse gains a neocortex dependency (mindmap-intelligence). This is acceptable — DraftHouse is an application-tier project that already depends on platform libraries. The facet is optional (classpath-activated) so DraftHouse without neocortex still works.
**Sources:** DraftHouse Facet.java, NotesPipeline.java, NotesPipelineObserver.java, VaultWriter.java, MindMapExtractor.java, issue #296
**Exploration:** quick
**Status:** captured

## D2: ConsolidationScheduler trigger — @Scheduled periodic, non-persistent

**Choice:** `@Scheduled` Quarkus timer runs consolidation at a configurable interval (e.g. every 5 minutes). No persistent job state — the scheduler is stateless. On restart, it simply scans the current graph state. Matches the cognitive science "sleep consolidation" metaphor: periodic background reorganization of accumulated knowledge.
**Alternatives:**
- CDI event-driven after extraction — more responsive but harder to reason about timing, back-pressure, and overlapping runs
- Manual/API trigger only — full control but no automatic background processing, undermines the three-speed model
**Rationale:** The knowledge graph itself is persisted (MindMapStore → SQLite/Qdrant). The scheduler just decides what to do on each pass. If the JVM restarts, it re-derives its work from graph state — no lost job queue. Simple, predictable, debuggable.
**Trade-offs:** Not immediately responsive to new data — consolidation waits for the next scheduled tick. Acceptable for background-tier work where latency is minutes, not milliseconds.
**Idle guard:** The scheduler must not run during active work. On each tick, check whether the system has been idle for at least 1 minute (no MindMapStore write operations). If not idle, skip the pass — consolidation is background-only processing that should not interfere with real-time or near-time work.
**Sources:** CbrReconciliationService (existing @Scheduled pattern in neocortex), RetentionScheduler (rag-tracking, same pattern), issue #297
**Exploration:** quick
**Status:** captured

## D6: Consolidation phases — ordered five-phase pipeline

**Choice:** Each idle-pass runs five phases in order: (1) confidence decay — full sweep via ConfidenceDecayDecorator (already exists), (2) access-frequency decay — reduce counters on unaccessed nodes, (3) merge detection — find and merge duplicates (D5), (4) community detection + summary generation (D4), (5) curiosity signal refresh via CuriositySignalGenerator (already exists). Phases run sequentially within a pass. Each phase is a `ConsolidationPhase` interface for testability.
**Alternatives:**
- Parallel phases — some phases could run concurrently, but the ordering has dependencies (merge before community detection avoids summarizing duplicates)
- Selective phases per pass — only run phases that have work (skip community detection if no clusters changed). Optimization for later.
**Rationale:** Order matters: decay first (reduces noise), merge second (removes duplicates before summarization), community detection third (operates on clean graph), curiosity last (scores reflect consolidated state). Sequential is simple and correct. Phase interface enables individual testing and selective disabling.
**Trade-offs:** Full sequential pass may be slow on large graphs. Acceptable for v1 — each phase can be bounded (process at most N nodes per pass) and optimized later.
**Depends on:** D2 (scheduler trigger), D3 (access-frequency), D4 (community), D5 (merge)
**Sources:** ConfidenceDecayDecorator.java, CuriositySignalGenerator.java, issue #297
**Exploration:** quick
**Status:** captured

## D3: Access-frequency tracking — node properties, decorator-intercepted

**Choice:** Store `accessCount` (integer) and `lastAccessed` (ISO instant) as properties on MindMapNode via `NodeUpdate`. A `@Decorator` on MindMapStore intercepts `getNode()`, `search()`, and `neighbors()` to increment counters on accessed nodes. The consolidation scheduler reads these properties to strengthen high-access nodes and let low-access ones decay.
**Alternatives:**
- Separate counter store (AccessTracker SPI) — cleaner separation but a new module and persistence layer for what is a counter
- Memory domain (domain="access" via CaseMemoryStore) — leverages existing infrastructure but creates one memory per access event, heavyweight
**Rationale:** Node properties are already queryable via MindMapQuery, already persisted by every MindMapStore backend, and don't require new infrastructure. The decorator pattern is proven (ConfidenceDecayDecorator, DerivedEdgeDecorator). The counter is a property of the node, not a separate concept.
**Trade-offs:** Properties are string-valued (Map<String, String>), so accessCount requires Integer.parseInt on read. Minor inconvenience. The decorator adds a write on every read operation — batching or sampling may be needed if access volume is high.
**Depends on:** D2 (consolidation scheduler reads these properties)
**Sources:** ConfidenceDecayDecorator.java (decorator pattern), MindMapNode.properties() (string-valued properties), issue #298
**Exploration:** quick
**Status:** captured

## D4: Community summaries — connected-component + edge density clustering

**Choice:** Identify clusters via simple graph partitioning: find densely-connected subsets within a subgraph using edge density thresholds. MindMapAnalyzer already computes degree centrality, betweenness centrality, and subgraph density — extend it with cluster detection. Creates a summary node for each cluster with edges to cluster members. The summary node's name and properties are LLM-generated from the member nodes' content.
**Alternatives:**
- Label propagation — iterative algorithm, more sophisticated but more complex to implement and tune for a first version
- Embedding-based clustering (k-means/DBSCAN) — catches semantic similarity but adds EmbeddingModel dependency and misses structural relationships
**Rationale:** Graph structure is the natural clustering signal for a knowledge graph. Densely-connected nodes share relationships — that's what makes them a community. MindMapAnalyzer already has the building blocks. LLM generates the summary content, graph structure identifies WHAT to summarize.
**Trade-offs:** Misses semantically related nodes that lack direct edges. Acceptable for v1 — embedding-based clustering can be layered on later.
**Depends on:** D2 (consolidation scheduler runs this as a background phase)
**Sources:** MindMapAnalyzer.java (betweennessCentrality, subgraphDensity, degreeCentrality), MindMapStore.neighbors(), issue #299
**Exploration:** quick
**Status:** captured

## D5: Merge detection — two-layer: string heuristic + embedding confirmation

**Choice:** Two-layer merge candidate detection. Layer 1 (cheap): fuzzy string matching on node names (Levenshtein/Jaro-Winkler, pure Java) combined with shared neighbor overlap. Layer 2 (semantic): embed node name + properties via EmbeddingModel, find cosine-similar pairs. Layer 1 catches obvious duplicates ("Mark Proctor" vs "M. Proctor" with same project edges). Layer 2 catches semantic duplicates ("CEO" vs "Chief Executive Officer"). Both layers produce scored candidates for human review or auto-merge above a confidence threshold.
**Alternatives:**
- String similarity only — misses semantic duplicates
- Embedding only — expensive to run on every node pair, unnecessary for obvious name matches
- Graph structure only — misses duplicates with different neighborhoods
**Rationale:** The two-layer approach uses the cheap heuristic as a fast filter, then embedding similarity for harder cases. The string layer is pure Java (no deps), the embedding layer reuses the existing optional `Instance<EmbeddingModel>` pattern from memory-qdrant. Both layers are independently useful — the system degrades gracefully when no EmbeddingModel is available (layer 1 only).
**Trade-offs:** Embedding layer is optional (Instance<EmbeddingModel> graceful degradation). Without it, only string-based detection works. Two-layer adds implementation complexity but covers significantly more ground.
**Depends on:** D2 (consolidation scheduler runs this as a background phase)
**Sources:** EditDistanceSimilarity (memory-api, existing Levenshtein), EmbeddingTextSimilarity (memory-cbr-embedding, existing pattern), MindMapStore.mergeNodes() (merge operation), issue #300
**Exploration:** quick
**Status:** captured
