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
**Sources:** CbrReconciliationService (existing @Scheduled pattern in neocortex), RetentionScheduler (rag-tracking, same pattern), issue #297
**Exploration:** quick
**Status:** captured
