## D1: Thing ↔ MindMapNode — separate types, consumer vs internal

**Choice:** Thing is a separate type from MindMapNode. Thing is the consumer-facing semantic API; MindMapNode is the internal storage SPI. They do not share a type hierarchy. Thing wraps/references MindMapNode internally but consumers never see MindMapNode when working at the cognitive level.
**Alternatives:**
- MindMapNode implements Thing — conflates storage SPI with semantic model. Changes to storage interface leak into the consumer API. Couples two fundamentally different concerns.
- ThingView CDI service (no new type) — no object identity for Thing. Loses the "hold a Thing, interact with it" Drools feel. Just utility functions, not a type system.
**Rationale:** Storage and semantics are separate concerns with different lifecycles. MindMapNode evolves with storage requirements (new indexes, new backends). Thing evolves with consumer needs (new trait APIs, type system extensions). Keeping them separate means neither constrains the other. The consumer gets a clean, stable API; the platform gets freedom to change storage internals.
**Trade-offs:** Requires a bridging layer (ThingResolver or similar) to hydrate Things from MindMapNode + edges + type metadata. Extra step compared to using MindMapNode directly.
**Sources:** MindMapNode.java, TraitProxy.java, issue #278 (Thing model prior art)
**Exploration:** quick
**Status:** revised — reframed Thing as a lightweight read-only projection, not a live Drools fact (R1-12). The separation motivation is consumer/internal API boundary, not live interaction.

## D2: Module placement — new thing-api

**Choice:** New `thing-api` module at tier-0 (zero deps, pure Java). Contains Thing interface and the convention-based proxy for as(). Consumer-facing module — app developers depend on thing-api, not mindmap-api.
**Alternatives:**
- cognitive-api — already the zero-deps cross-cutting home, but Thing is a knowledge representation base type, not a cognitive classification. Overloads cognitive-api's purpose (D26 from #253 defines it as cognitive classifications).
- mindmap-api — co-locates Thing with MindMapNode, but blurs the consumer/internal boundary. Consumers importing mindmap-api would see both Thing and MindMapNode, defeating the separation.
**Rationale:** Thing is foundational — the knowledge representation base type that Subject, MindMap, and the type system all reference. It warrants its own module with a clean dependency surface. Follows the same pattern as cognitive-api (zero-deps shared type module) but for a different architectural concern.
**Trade-offs:** Adds a module to the reactor. Justified — the concern is genuinely distinct from cognitive classification.
**Depends on:** D1 (Thing ↔ MindMapNode separation)
**Sources:** cognitive-api/pom.xml (zero-dep pattern), D26 from #253 (cognitive-api acceptance criteria)
**Exploration:** quick
**Status:** revised — removed Triple from module contents (R1-02). D3 decided against triples on Thing; no Triple type needed.

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

## D5: SubgraphType enum → dynamic string + constants

**Choice:** Replace SubgraphType enum with String in MindMapSubgraph and SubgraphInput. Current enum values become lowercase string constants in a SubgraphTypes utility class in mindmap-api. Lowercase-normalized (same convention as Subject.type()). RuleCondition.InSubgraphType changes its field from SubgraphType to String and gets a real implementation (currently returns false).
**Alternatives:**
- SubgraphType record wrapper — SubgraphType(String name) for type safety. Adds a type for what is just a string label. The enum-to-record migration creates more churn than enum-to-String for callers.
**Rationale:** LLM discovers new entity types at runtime — a fixed enum prevents this. String with constants follows Subject(type, id) convention. Constants preserve compile-time references for well-known types without restricting new ones. InSubgraphType finally gets a working implementation.
**Trade-offs:** Callers using SubgraphType.PERSON switch to SubgraphTypes.PERSON — mechanical migration. Loss of exhaustive switch — acceptable since the point is that new types can appear at runtime.
**Depends on:** D1 (Thing/MindMapNode separation — subgraph types are graph partitioning in mindmap-api, not Thing identity in thing-api)
**Sources:** SubgraphType.java (6-value enum), SubgraphInput.java, MindMapSubgraph.java, RuleCondition.InSubgraphType (returns false), Subject.java (lowercase normalization convention), issue #281
**Exploration:** quick
**Status:** captured

## D6: Type registry — types as MindMap nodes in a type subgraph

**Choice:** Types are first-class data in MindMap. A designated subgraph (type=SubgraphTypes.TYPE_SYSTEM) contains type-definition nodes. `subtype-of` edges form the type hierarchy. Core types carry a `java-class` property linking to their Java interface. Dynamic types are nodes without a `java-class` property. No new SPI — type management is MindMapStore operations on a special subgraph. A TypeResolver utility in a higher module reads the type subgraph and builds the mapping.
**Alternatives:**
- Standalone TypeRegistry SPI — separate storage from MindMap. Cleaner separation but duplicates graph structure (nodes, edges, hierarchy) that MindMap already provides. Two storage systems for the same concept.
- In-code registry only — core types registered programmatically. No runtime type discovery. Blocks the LLM from discovering new types, which is the core requirement.
**Rationale:** The type system IS knowledge about knowledge — it belongs in the knowledge graph. MindMap already provides nodes, edges, properties, and traversal. Using a special subgraph means type hierarchy queries are just graph traversal — no new query infrastructure. The LLM discovers new types by adding nodes to the type subgraph, which is exactly how it adds any other knowledge.
**Trade-offs:** Type operations couple to MindMapStore availability. TypeResolver (the consumer utility) needs MindMapStore access. thing-api stays zero-deps — it carries the Thing interface but not the type resolution logic.
**Depends on:** D5 (dynamic subgraph types — TYPE_SYSTEM is a new constant)
**Sources:** issue #278 (type subgraph proposal), MindMapStore.nodesIn() (subgraph queries), MindMapStore.neighbors() (hierarchy traversal), CognitiveLoader.java (vocabulary registration pattern)
**Exploration:** quick
**Status:** captured

## D7: Subject ↔ Thing bridge — convention, not dependency

**Choice:** Subject references Thing by naming convention. Subject.type() == Thing.type() (core or dynamic type name). Subject.id() == Thing.id() (MindMapNode UUID). No code dependency between memory-api and thing-api. Resolution from Subject to Thing happens at the call site via ThingResolver. Subject stays exactly as-is — a lightweight pointer.
**Alternatives:**
- Subject depends on thing-api — Subject gains toThing(ThingResolver) or Thing gains toSubject(). Forces a dependency between two tier-0 modules. Couples memory-api to the Thing concept.
- Shared supertype (ThingRef) — both Subject and Thing implement a reference interface. Over-engineered for an (id, type) pointer convention.
**Rationale:** Follows the NodeRef pattern — NodeRef(scheme="memory", id=memoryId) is a convention, not a type dependency. Both modules stay independent and zero-deps. The convention is simple and documented: same id, same type. Resolution is the caller's concern, not a type system concern.
**Trade-offs:** No compile-time enforcement that Subject.type() matches Thing.type(). Convention-based — if either side changes its type naming, the bridge breaks silently. Acceptable for a pre-release platform where both conventions are documented.
**Depends on:** D2 (thing-api zero-deps), D3 (Thing carries type())
**Sources:** Subject.java (type + id), NodeRef.java (convention-based cross-store reference), issue #278 (Subject becomes a Thing reference)
**Exploration:** quick
**Status:** captured

## D8: Dynamic property schema — schema as properties on type nodes

**Choice:** Property schema for dynamic types is stored as properties on type nodes in the type subgraph. Convention: `schema.{fieldName}.type={string|number|boolean|date}`, `schema.{fieldName}.required={true|false}`. No new types in thing-api. A PropertySchema utility in mindmap-intelligence reads these properties and validates Thing properties against the schema. Validation is advisory (warn, not reject) — LLMs may produce novel properties that extend the schema.
**Alternatives:**
- PropertySchema record in thing-api — structured type for field definitions. Needs serialization conventions since MindMapNode properties are Map<String, String>. Cleaner API but adds complexity for a property-convention problem.
- JSON Schema as single property — full JSON Schema power in a `property-schema` property. Heavyweight JSON parsing in a zero-deps context. MindMap properties are strings, not JSON values.
**Rationale:** Properties on type nodes follow the existing model — no new types, no serialization, no parsing. Schema is metadata about a type stored as more properties using a naming convention. The advisory validation matches the design principle: LLM-discovered types may have novel properties the schema doesn't cover yet. The schema documents expectations and enables reasoning, not enforcement.
**Trade-offs:** Schema expressiveness is limited to simple types (string/number/boolean/date). No nested objects, no array types. Sufficient for the property model (Map<String, String>). If richer schema is needed later, the convention extends naturally (schema.{field}.items.type, etc.).
**Depends on:** D6 (types as MindMap nodes — schema lives on type nodes)
**Sources:** MindMapNode.properties() (string-valued property model), issue #282 (dynamic property schema), CognitiveLoader.java (convention-based metadata registration)
**Exploration:** quick
**Status:** captured

## D9: ThingResolver in mindmap-intelligence

**Choice:** ThingResolver is an @ApplicationScoped CDI bean in mindmap-intelligence. Depends on thing-api + mindmap-api. resolve(String nodeId, String tenantId) → Optional<Thing>. Fetches node from MindMapStore, reads traits, reads type subgraph to determine type(), constructs a Thing implementation.
**Alternatives:**
- New `thing` CDI module — dedicated to Thing resolution. Adds a module for one CDI bean. Unnecessary when mindmap-intelligence already has the right dependencies and purpose.
- cognitive-index — hosts cross-store resolvers (CognitiveProfile, PerspectivalResolver). But ThingResolver doesn't cross stores — it bridges thing-api and mindmap-api only.
**Rationale:** mindmap-intelligence is the "smart MindMap layer" — TraitProxy, TraitRules, CuriositySignalGenerator, MindMapExtractor all live here. ThingResolver is the natural companion: it uses TraitRule results and type subgraph data to construct Things from MindMapNodes. No new module needed.
**Trade-offs:** mindmap-intelligence gains a thing-api dependency. Acceptable — it's a consumer of Thing, not a provider of storage.
**Depends on:** D1 (separation), D2 (thing-api module), D6 (type subgraph for type() resolution)
**Sources:** TraitProxy.java (mindmap-intelligence), CognitiveLoader.java (mindmap-intelligence CDI bean), MindMapStore.java (node/subgraph queries)
**Exploration:** quick
**Status:** captured

## D10: Thing type() — explicit type property on MindMapNode

**Choice:** Each MindMapNode carries a `type` property (e.g., type=person, type=research-topic) set at creation time by the caller or LLM extractor. Thing.type() reads property("type"). The type value must match a type node name in the type subgraph (D6) — ThingResolver validates at hydration time. The type property is the core type the Thing was "instantiated against" (from #278 prior art).
**Alternatives:**
- Inferred from subgraph type — Thing.type() derives from the node's subgraph. But subgraphs are partitioning (D5), not typing. A subgraph could contain multiple entity types. Conflates grouping with identity.
- Inferred from traits — Thing.type() is the "most specific" satisfied trait. Requires type hierarchy ordering to determine specificity. Traits can be multiple (Personable + Organisational) — ambiguous which is the primary type.
**Rationale:** Explicit is better than inferred. The type is set once at creation — it identifies what the Thing IS, not what interfaces it satisfies. Traits are additional capabilities discovered over time (a Person gains Appointable when events are added). The type/trait distinction mirrors Java's class vs interface: a class has one identity type, but implements many interfaces.
**Trade-offs:** Requires callers to set the type property at node creation. ThingResolver refuses nodes without an explicit type property — returns Optional.empty(). No fallback to subgraph type (that would contradict D5's separation of partitioning from typing). ThingResolver normalizes type to lowercase when reading the property, ensuring Subject.type() convention alignment (R1-08).
**Depends on:** D3 (Thing carries type()), D6 (type subgraph for validation), D7 (Subject.type() == Thing.type() convention)
**Sources:** Subject.java (type convention, lowercase normalization), NodeInput.withProperty() (property setting), issue #278 (ThingInstance instantiated against one core type)
**Exploration:** quick
**Status:** revised — removed subgraph type fallback (R1-10, contradicts D5); added lowercase normalization (R1-08); ThingResolver refuses nodes without type (R1-10)

## D11: Trait interfaces — consumer-defined, platform-provided optional

**Choice:** as(Class<T>) works with ANY interface by convention — method names map to property keys. Consumers can define their own domain-specific trait interfaces without depending on platform definitions. The existing trait interfaces (Personable, Projectlike, Organisational, Eventlike) stay in mindmap-intelligence as platform-provided conveniences, not required dependencies. thing-api ships with ZERO pre-defined trait interfaces — it is purely structural.
**Alternatives:**
- Move trait interfaces to thing-api — thing-api carries domain knowledge (birthday, role, email). Violates zero-deps purpose.
- New thing-traits module — more module proliferation for optional convenience types.
- Consumers must import mindmap-intelligence — defeats the consumer/internal separation.
**Rationale:** The proxy is generic — it maps method names to property keys regardless of which interface defines them. A consumer who defines `interface Customer { Optional<String> accountId(); }` gets typed access to `property("accountId")` without importing any platform module. Platform traits are optional conveniences for common entity types. This is the most architecturally coherent option (R1-03).
**Trade-offs:** No shared trait vocabulary across consumers. Each consumer may define overlapping interfaces. Acceptable — the property keys are the shared vocabulary, not the Java interfaces.
**Depends on:** D4 (convention-based proxy)
**Sources:** TraitProxy.java (generic method-name convention), Personable.java (platform trait example), R1-03
**Exploration:** surfaced by review (R1-03)
**Status:** captured

## D12: Shared PropertyAccessor — single proxy implementation

**Choice:** Define a `PropertyAccessor` functional interface in thing-api: `Optional<String> property(String key)`. Thing extends PropertyAccessor. The JDK Proxy invocation handler in thing-api works on any PropertyAccessor. mindmap-intelligence's TraitInvocationHandler is replaced by having MindMapNode adapt to PropertyAccessor (trivially — it already has `property(String key)`). One proxy implementation, two use sites.
**Alternatives:**
- Duplicate proxy — thing-api and mindmap-intelligence each have their own invocation handler doing the same method-name-to-property dispatch with the same type coercion (String, Integer, Long, Double, Optional). Two implementations that must stay in sync.
**Rationale:** TraitInvocationHandler is 51 lines of non-trivial type coercion logic. Duplicating it creates a maintenance burden — new return types (Boolean, Instant) must be added in both places. A shared PropertyAccessor in thing-api (zero deps) allows one proxy that works everywhere (R1-04).
**Trade-offs:** mindmap-intelligence gains a dependency on thing-api for the proxy. Its existing TraitProxy.as() calls migrate to the shared implementation. Mechanical change.
**Depends on:** D2 (thing-api module), D4 (convention-based proxy)
**Sources:** TraitInvocationHandler.java (51 lines of type coercion), R1-04
**Exploration:** surfaced by review (R1-04)
**Status:** captured

## D13: Type subgraph bootstrapping — CognitiveLoader at startup

**Choice:** CognitiveLoader (@PostConstruct in mindmap-intelligence) bootstraps the TYPE_SYSTEM subgraph and core type nodes at startup. Same pattern as existing vocabulary registration. Creates the subgraph if absent, creates core type nodes (person, project, organisation, concept, research-area, general) if absent. Idempotent — safe to run on every startup. Per-tenant: each tenant gets its own type subgraph populated.
**Alternatives:**
- Lazy creation on first ThingResolver call — race conditions in concurrent environments. First resolve fails if type subgraph doesn't exist yet.
- Migration script — one-time setup but doesn't handle new tenants created after deployment.
**Rationale:** CognitiveLoader already does startup registration (vocabulary). Adding type subgraph bootstrap is natural. @PostConstruct runs once, idempotent, handles all tenants. discoverTenants() (from CaseMemoryStore) provides the tenant list. Instance<MindMapStore> graceful degradation — if no MindMap backend, no bootstrap needed.
**Trade-offs:** Core types are hardcoded in CognitiveLoader. Adding a new core type requires a code change. Acceptable — core type promotion is a conscious developer act (issue #278).
**Depends on:** D6 (type subgraph), D5 (TYPE_SYSTEM constant)
**Sources:** CognitiveLoader.java (existing @PostConstruct registration), MindMapStore.createSubgraph(), R1-06
**Exploration:** surfaced by review (R1-06)
**Status:** captured

## D14: Thing is an interface with an implementation record in thing-api

**Choice:** Thing is an interface. A package-private implementation record `ThingRecord(String id, String name, String type, Map<String, String> properties, Set<String> traits)` lives in thing-api. ThingResolver constructs ThingRecord instances via a static factory: `Thing.of(id, name, type, properties, traits)`. Consumers interact with the Thing interface; the implementation is hidden.
**Alternatives:**
- Thing as a public record — simple but exposes the constructor, allowing arbitrary construction that bypasses ThingResolver validation (type exists in type subgraph, traits computed by rules).
- Thing as a class — unnecessary complexity for an immutable value. Records are the right fit.
**Rationale:** Interface + hidden record follows the established codebase pattern (MindMapNode is an interface with backend-specific implementations). The factory method on Thing provides a clean construction API for ThingResolver without exposing the record (R1-16).
**Trade-offs:** Factory method in an interface requires a static method referencing the package-private record. Standard Java pattern — `Thing.of()` returns the hidden implementation.
**Depends on:** D2 (thing-api module), D3 (Thing shape)
**Sources:** MindMapNode.java (interface pattern), R1-16
**Exploration:** surfaced by review (R1-16)
**Status:** captured
