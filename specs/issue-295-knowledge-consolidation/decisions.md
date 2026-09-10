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
