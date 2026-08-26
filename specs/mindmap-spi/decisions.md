# MindMap SPI — Design Decisions

## D1: Module architecture

**Choice:** New top-level module family (`mindmap-api/`, `mindmap/`, `mindmap-inmem/`, `mindmap-sqlite/`, `mindmap-testing/`)
**Alternatives:**
- Inside memory-api — shares value types but creates coupling to memory-api's dependency tree and risks CDI displacement (GE-20260630-815259)
**Rationale:** Cleaner separation, own dependency tree, no coupling to existing memory SPIs. Follows the established pattern where each concern (inference, rag, corpus, memory) has its own module family.
**Trade-offs:** Cannot reuse MemoryDomain, MemoryCapability, etc. directly — may need own equivalents or shared types in a common module.
**Sources:** GE-20260630-815259 (cross-repo SPI extends CDI displacement), existing module structure pattern
**Exploration:** quick
**Status:** captured

## D2: Cross-store bridging

**Choice:** URI-style typed references (`NodeRef` with scheme/id/qualifier)
**Alternatives:**
- Shared identity namespace — tighter coupling, assumes all entities have a natural shared key
- Both (identity where natural, refs for cross-cutting) — more complex, two resolution mechanisms
**Rationale:** Loose coupling — the graph stores a reference without depending on the other SPI's classpath. Resolution is lazy. A node can reference a CaseMemoryStore entity, a CBR case, or an external URL with the same mechanism.
**Trade-offs:** No compile-time guarantee that the referenced entity exists. Resolution requires the consuming module to have the target SPI available.
**Sources:** CbrCaseMemoryStore standalone SPI pattern, existing bridging via CDI observers in memory/
**Exploration:** quick
**Status:** captured

## D3: Subgraph boundaries

**Choice:** Declared subgraphs with typed root nodes
**Alternatives:**
- Emergent from edge density — more flexible but requires graph analysis to answer "which subgraph?"
- Declared but optional — hybrid that allows orphan nodes, more complex query model
**Rationale:** Gives typed schema expectations per subgraph type (PROJECT has different expectations than PERSON). Simple to query ("give me the project subgraph for neocortex"). Cross-subgraph edges are explicit bridges, making the merge points visible.
**Trade-offs:** Every node must belong to a subgraph — no free-floating concepts. May need a "general" or "uncategorised" subgraph as a catch-all.
**Sources:** Mind map mental model from conversation
**Exploration:** quick
**Status:** captured

## D4: Naming

**Choice:** `mindmap` — MindMapStore, `mindmap-api/`, `io.casehub.neocortex.mindmap`
**Alternatives:**
- `knowledgegraph` — technically precise but longer, academic connotation
- `graph` — short but clashes conceptually with GraphCaseMemoryStore
**Rationale:** Matches the mental model ("mind maps that merge"), intuitive, no academic baggage. Short enough for module/package names.
**Trade-offs:** "Mind map" has connotations of tree-structured diagrams in some contexts — this is more graph than tree. Acceptable given the conversational context.
**Sources:** Conversation framing
**Exploration:** quick
**Status:** captured

## D5: Intelligence layer placement — decorator/consumer split

**Choice:** Two-tier split following the CbrCaseMemoryStore decorator pattern. Transparent concerns (vocabulary normalization, derived edge insertion via rules) operate as CDI `@Decorator` on the SPI — consumers get enriched results without knowing decorators exist. Explicit concerns (LLM extraction, gap detection, active learning, deep contradiction analysis) live above the SPI in a separate module (`mindmap-intelligence/`).
**Alternatives:**
- All intelligence above SPI — forces every consumer to explicitly invoke the rule engine; discards the proven decorator pattern from CBR
- All intelligence in the SPI — couples storage to LLM dependencies
- Enrichment pipeline in the SPI (like CaseEnrichmentStep) — less flexible than decorators
**Rationale:** The CBR system proves this pattern: `TrendEnrichmentCbrCaseMemoryStore` at `@Priority(90)` enriches transparently; LLM-based operations are explicit. The same split applies here: vocabulary normalization and forward-chaining rules for derived edges are cheap, deterministic, and should fire transparently on every addEdge(). LLM extraction, gap detection, and active learning are expensive, non-deterministic, and should be explicitly invoked.
**Trade-offs:** Decorator chain adds implementation complexity. Decorator ordering must be documented. Transparent rules must be fast — slow rules should be moved to the explicit intelligence layer.
**Sources:** CbrCaseMemoryStore decorator chain (TrendEnrichment, OutcomeWeighting, TrustWeighted), CaseEnrichmentStep, R1-04 decision review finding
**Exploration:** quick
**Status:** revised (was: all intelligence above SPI)

## D6: Controlled vocabulary governance — soft registration with validation tiers

**Choice:** Schema registration with alias normalization AND acceptance of unregistered types tagged as `UNVALIDATED`. Registered types normalise on ingest ("employed-by" → "works-at"). Unregistered types are accepted but flagged — the intelligence layer can promote validated types into the controlled vocabulary over time.
**Alternatives:**
- Hard rejection of unregistered types — blocks LLM discovery of novel relationships (R1-05 finding: chicken-and-egg with LLM extraction)
- Open with normalization above — flexible but allows synonym accumulation without any governance
**Rationale:** The LLM extraction layer (D5) may discover novel relationship types that aren't pre-registered. Hard rejection forces pre-registration of all possible types (defeating LLM discovery) or on-the-fly registration (making the boundary meaningless). Soft governance preserves the controlled vocabulary as the goal while allowing discovery. Edges carry a validation tier: `REGISTERED` (normalised, governed) or `UNVALIDATED` (accepted, flagged for review). A promotion path moves validated types from UNVALIDATED to REGISTERED.
**Trade-offs:** UNVALIDATED types can accumulate if the intelligence layer doesn't actively review them. Needs a periodic cleanup/promotion mechanism. Queries should distinguish between validated and unvalidated edges when governance matters.
**Sources:** CbrFeatureSchema.registerSchema() pattern, conversation on vocabulary governance, R1-05 decision review finding
**Exploration:** quick
**Status:** revised (was: hard rejection of unregistered types)

## D7: Entity aliasing

**Choice:** First-class in the SPI (addAlias, resolveNode, mergeNodes)
**Alternatives:**
- Intelligence layer — simpler SPI but consumers must handle name→ID mapping, inconsistent resolution
**Rationale:** Aliasing must be storage-level to be consistent. If two consumers query by alias, they must resolve to the same node — this requires the store to own the alias index. Merge operations (union edges when two nodes are discovered to be the same entity) are destructive and must be atomic.
**Trade-offs:** Adds methods to the SPI. Merge is complex (edge deduplication, alias union, subgraph reassignment). Contract tests must cover merge edge cases.
**Sources:** Conversation on entity resolution
**Exploration:** quick
**Status:** captured

## D8: SPI shape

**Choice:** Approach A — granular graph primitives (single MindMapStore interface with CRUD methods for nodes, edges, aliases, subgraphs, vocabulary, traversal)
**Alternatives:**
- Batch-oriented operations — fewer methods but complex input types, harder to test individually
- Resource-oriented (one interface per concept) — over-decomposition, complex CDI wiring
**Rationale:** Same pattern as CbrCaseMemoryStore — a single interface with granular methods. Simple to implement, test, and decorate. The intelligence layer composes the primitives. Batch operations can be added later as default methods.
**Trade-offs:** More methods on the interface (~15-20). Each must be independently tested in contract suite.
**Sources:** CbrCaseMemoryStore pattern, CaseMemoryStore pattern
**Exploration:** quick
**Status:** captured

## D9: Node content model — hybrid core + dynamic properties + opaque trait metadata

**Choice:** The SPI stores: (1) fixed core fields on `MindMapNode` (id, name, createdAt, confidence, provenance, etc.), (2) dynamic key-value properties, (3) a `Set<String>` of applied trait names as opaque metadata. The SPI does not know what trait names mean — it stores them as strings. Proxy generation, truth maintenance, forward-chaining rules, and compaction are intelligence-layer concerns (D5), not SPI concerns. The SPI's `property(key)` method provides unified access regardless of whether a value is stored as a core field or a dynamic property.
**Alternatives:**
- Sealed hierarchy (PersonNode, ProjectNode, etc.) — rigid, new types require SPI changes
- Full Drools Traits in the SPI — conflates storage with rule engine; violates D5's separation
- Single interface + properties only — works but doesn't store trait classification
**Rationale:** Clear boundary: the SPI is a property store that also tracks which trait names are applied. The intelligence layer owns trait semantics — which interfaces exist, how proxies are generated, when traits are applied/retracted via rules, and when compaction promotes dynamic properties to core. This follows D5's revised decorator/consumer split: trait management is explicit intelligence, not transparent decoration.
**Trade-offs:** Consumers of the raw SPI get untyped property bags. Typed access requires the intelligence/proxy layer. This is acceptable — the SPI's job is storage, not presentation.
**Sources:** Drools Traits system (user's prior work), R1-03 decision review finding (separation of concerns), D5 revised placement
**Exploration:** quick
**Depends on:** D5
**Status:** revised (was: traits in SPI)

## D10: Third-party vs own implementation

**Choice:** Own the SPI and model. Storage is an implementation detail that can change over time (SQLite day-one, TinkerPop/ArcadeDB if traversal complexity grows).
**Alternatives:**
- Build on TinkerPop/Gremlin directly — standard API but heavyweight dependency for simple traversal needs
- Build on ArcadeDB — multi-model but adds an embedded database dependency
- Use Apache Jena — formal ontology framework, explicitly rejected as too heavy
**Rationale:** The intelligence layer (controlled vocabulary, confidence, aliasing, rules, active learning, LLM extraction) is the novel part — no library covers it. The storage layer is simple (nodes + edges + properties in SQLite). TinkerPop is the escape hatch if traversal needs outgrow recursive CTEs. Neo4j rejected on licensing grounds (GPL/proprietary).
**Trade-offs:** Owning storage means maintaining traversal algorithms. Day-one traversal is simple (neighbors, bridges) but shortest-path, community detection, etc. would need implementation or a backend swap.
**Sources:** ArcadeDB (Apache 2.0), TinkerPop (Apache 2.0), Jena (Apache 2.0), Neo4j (GPL — rejected), conversation on NIH risk
**Exploration:** deep-analysis
**Status:** captured

## D11: Tenant isolation

**Choice:** Tenant-isolated, consistent with all platform memory SPIs. Every mutating and querying method requires `tenantId`. The SPI enforces tenant boundaries — a node in tenant A is invisible to queries in tenant B. No cross-tenant operations on the SPI surface (unlike CaseMemoryStore's `eraseEntityAcrossTenants`); cross-tenant admin operations can be added later as capabilities if needed.
**Alternatives:**
- Tenant-unaware SPI with tenant filtering above — violates platform security conventions
- Cross-tenant operations from day one — premature for the initial scope
**Rationale:** Every memory SPI in the platform (`CaseMemoryStore`, `CbrCaseMemoryStore`) requires tenantId on every operation and enforces access via `MemoryPermissions.assertTenant()`. The mindmap SPI must follow the same convention for platform coherence and security.
**Trade-offs:** Every method signature includes tenantId — slightly more verbose API. Cross-tenant admin (e.g., "find all nodes about this entity across tenants") requires a separate capability added later.
**Sources:** CaseMemoryStore.store(MemoryInput) — tenantId required, CbrCaseMemoryStore — tenantId on every call, MemoryPermissions.assertTenant(), R1-11 decision review finding
**Exploration:** quick
**Status:** captured

## D12: GDPR erasure

**Choice:** The SPI provides cascading graph-aware erasure: `eraseNode(nodeId, tenantId)` removes the node, all its edges, all its aliases, its subgraph membership, and any NodeRefs pointing to it from other nodes. `eraseBySubgraph(subgraphId, tenantId)` removes an entire subgraph and all its contents. Both return counts for audit logging. `eraseEntity(entityId, tenantId)` is a future capability if entity-level (vs node-level) erasure is needed.
**Alternatives:**
- Node-only erasure with orphan cleanup — simpler SPI but leaves dangling edges and refs
- Soft-delete with tombstones — preserves history but doesn't satisfy GDPR hard-delete requirements
**Rationale:** Graph erasure is structurally harder than flat record deletion. A node participates in edges, aliases, subgraphs, and cross-references. Deleting only the node leaves the graph in an inconsistent state. The SPI must guarantee cascading cleanup as an atomic operation.
**Trade-offs:** Cascading delete is complex to implement correctly, especially for NodeRefs (which may point to the deleted node from other nodes). Contract tests must verify no dangling references survive erasure.
**Sources:** CaseMemoryStore.eraseEntity(), CbrCaseMemoryStore.erase/eraseEntity/eraseByScope, GDPR Art.17, R1-11 decision review finding
**Exploration:** quick
**Status:** captured

## D13: Capability self-description

**Choice:** The SPI includes a `capabilities()` method returning `Set<MindMapCapability>` and a `requireCapability(MindMapCapability)` guard, following the `MemoryCapability` pattern. Initial capabilities include `TRAVERSAL`, `MERGE`, `VOCABULARY`, `ALIAS`, `SUBGRAPH`, `SEARCH`, `ERASE_NODE`, `ERASE_SUBGRAPH`. Backends declare which operations they support; consumers can check before calling optional operations.
**Alternatives:**
- No capabilities — all methods are mandatory on all backends. Simpler but forces every backend to implement everything, even if some operations are expensive or unsupported.
- Exceptions on unsupported operations — same result but less discoverable than a capability check.
**Rationale:** The in-memory backend will support everything. A future TinkerPop backend may not support atomic merge. A minimal backend may skip traversal. Capability self-description lets consumers adapt without catching exceptions.
**Trade-offs:** Adds an enum and two methods to the SPI. Backends must maintain an accurate capability set.
**Sources:** MemoryCapability enum, CaseMemoryStore.capabilities()/requireCapability(), R1-11 decision review finding
**Exploration:** quick
**Status:** captured
