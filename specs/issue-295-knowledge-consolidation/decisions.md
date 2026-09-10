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
