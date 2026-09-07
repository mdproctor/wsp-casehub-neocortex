## D1: Thing ↔ MindMapNode — separate types, consumer vs internal

**Choice:** Thing is a separate type from MindMapNode. Thing is the consumer-facing semantic API; MindMapNode is the internal storage SPI. They do not share a type hierarchy. Thing wraps/references MindMapNode internally but consumers never see MindMapNode when working at the cognitive level.
**Alternatives:**
- MindMapNode implements Thing — conflates storage SPI with semantic model. Changes to storage interface leak into the consumer API. Couples two fundamentally different concerns.
- ThingView CDI service (no new type) — no object identity for Thing. Loses the "hold a Thing, interact with it" Drools feel. Just utility functions, not a type system.
**Rationale:** Storage and semantics are separate concerns with different lifecycles. MindMapNode evolves with storage requirements (new indexes, new backends). Thing evolves with consumer needs (new trait APIs, type system extensions). Keeping them separate means neither constrains the other. The consumer gets a clean, stable API; the platform gets freedom to change storage internals.
**Trade-offs:** Requires a bridging layer (ThingResolver or similar) to hydrate Things from MindMapNode + edges + type metadata. Extra step compared to using MindMapNode directly.
**Sources:** MindMapNode.java, TraitProxy.java, issue #278 (Thing model prior art)
**Exploration:** quick
**Status:** captured
