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

## D2: Module placement — new thing-api

**Choice:** New `thing-api` module at tier-0 (zero deps, pure Java). Contains Thing interface, Triple, and type-related value types. Consumer-facing module — app developers depend on thing-api, not mindmap-api.
**Alternatives:**
- cognitive-api — already the zero-deps cross-cutting home, but Thing is a knowledge representation base type, not a cognitive classification. Overloads cognitive-api's purpose (D26 from #253 defines it as cognitive classifications).
- mindmap-api — co-locates Thing with MindMapNode, but blurs the consumer/internal boundary. Consumers importing mindmap-api would see both Thing and MindMapNode, defeating the separation.
**Rationale:** Thing is foundational — the knowledge representation base type that Subject, MindMap, and the type system all reference. It warrants its own module with a clean dependency surface. Follows the same pattern as cognitive-api (zero-deps shared type module) but for a different architectural concern.
**Trade-offs:** Adds a module to the reactor. Justified — the concern is genuinely distinct from cognitive classification.
**Depends on:** D1 (Thing ↔ MindMapNode separation)
**Sources:** cognitive-api/pom.xml (zero-dep pattern), D26 from #253 (cognitive-api acceptance criteria)
**Exploration:** quick
**Status:** captured

## D3: Thing interface shape — minimal: identity + properties + traits + is/as

**Choice:** Thing carries identity (id, name, type), properties (Map<String, String>), traits (Set<String>), and is()/as() methods. No edges, no triples view, no graph traversal. Relationships are a graph concern queried via the store, not carried on the entity.
**Alternatives:**
- With triples — unified property+edge view (List<Triple>). Conceptually elegant but forces hydration of edges at construction time. Either Thing carries stale relationship data or needs a live store reference, both violating the lightweight zero-deps contract.
- Rich — includes edges and type metadata. Thing becomes a heavy aggregate. Pulls graph traversal into a zero-deps type, defeating its purpose.
**Rationale:** Thing is an entity with identity, properties, and trait-based type identity. Properties ARE the datatype triples (this, key, value). Edge queries give the object triples (this, edgeType, target). No need to unify them on the type. Keeps thing-api zero-deps and Thing lightweight — constructable from a property map without store access.
**Trade-offs:** Consumers who need relationships must query the store separately. This is correct — relationships are live graph state, not entity state.
**Depends on:** D1 (separation), D2 (zero-deps module)
**Sources:** MindMapNode.java (property/trait surface), TraitProxy.java (as() pattern), MindMapStore.neighbors() (edge queries)
**Exploration:** quick
**Status:** captured

## D4: is()/as() implementation — pre-computed traits, convention-based proxy

**Choice:** `is(String traitName)` checks `traits().contains(traitName)` — traits are pre-computed at store time by TraitRule evaluation in the decorator stack. Thing reads the result. `as(Class<T>)` uses a JDK Proxy in thing-api that maps interface method names to `property(methodName)` calls. Zero external deps — only java.lang.reflect.Proxy and the Thing interface. Thing is a snapshot value, not a live evaluator.
**Alternatives:**
- Live rule evaluation — Thing carries a rule evaluator and edges, evaluating is() on demand. Violates zero-deps, makes Thing a live object rather than a value. Rules need edge access which is a graph concern (D3).
**Rationale:** Follows the Drools pattern: the rule engine computes traits, the fact carries the result. Trait computation happens at the store/decorator layer where edges and rules are available. Thing is a value — lightweight, snapshot-based, no store reference. The method-name-to-property-key convention (birthday() reads property("birthday")) is already proven by TraitProxy and needs no external knowledge.
**Trade-offs:** Traits reflect state at construction time. If properties change after Thing is constructed, is() may be stale. Correct behavior — consumers should re-resolve from the store for fresh state.
**Depends on:** D1 (separation), D3 (Thing shape)
**Sources:** TraitProxy.java (JDK Proxy + method-name convention), TraitInvocationHandler.java, PersonableTraitRule.java (store-time evaluation)
**Exploration:** quick
**Status:** captured
