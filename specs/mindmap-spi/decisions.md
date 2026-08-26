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

## D5: Intelligence layer placement

**Choice:** Above the SPI in a separate module (`mindmap-intelligence/`)
**Alternatives:**
- Enrichment pipeline in the SPI (like CaseEnrichmentStep) — couples SPI to enrichment concerns
- Split — rules in SPI, LLM above — adds complexity to the SPI boundary
**Rationale:** The SPI is a pure storage/query contract. Intelligence (LLM extraction, gap detection, active learning, rule engine, contradiction detection) consumes the SPI. Clean separation — you can use the store without the intelligence layer. Testable in isolation.
**Trade-offs:** Forward-chaining rules could fire on every edge insert if they were in the store — putting them above means the caller must invoke the rule engine explicitly.
**Sources:** CaseEnrichmentStep pattern (considered and rejected), CbrCaseMemoryStore (pure storage, intelligence above)
**Exploration:** quick
**Status:** captured

## D6: Controlled vocabulary governance

**Choice:** Schema registration (like CbrFeatureSchema) with alias normalization
**Alternatives:**
- Open with normalization above — flexible but allows synonym accumulation
- Seeded vocabulary, extensible at runtime — hybrid but introduces "unregistered" state
**Rationale:** The store rejects unregistered edge types, enforcing vocabulary governance at the SPI level. Aliases normalise on ingest ("employed-by" → "works-at"). Consistent with CbrFeatureSchema.registerSchema() pattern. Prevents the "5 ways to say the same thing" problem structurally.
**Trade-offs:** Requires vocabulary registration before any edges can be stored. Cold-start requires a seed vocabulary. New edge types require explicit registration.
**Sources:** CbrFeatureSchema.registerSchema() pattern, conversation on vocabulary governance
**Exploration:** quick
**Status:** captured

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

## D9: Node content model — hybrid core + traits (Drools Traits pattern)

**Choice:** Single core MindMapNode with fixed fields + dynamic properties, with dynamically-applied trait interfaces maintained by forward-chaining rules and truth maintenance. Proxy generation abstracts over core vs dynamic property storage. Compaction promotes frequently-used dynamic properties into the core schema over time.
**Alternatives:**
- Sealed hierarchy (PersonNode, ProjectNode, etc.) — rigid, new types require SPI changes
- Open hierarchy with typed views — similar to traits but without rule-maintained lifecycle
- Single interface + properties only — works but loses typed access and rule-driven classification
**Rationale:** A node is a "Thing" with core fields. Traits (Java interfaces like Personable, Projectlike) are applied dynamically at runtime via proxy. A node can implement multiple traits simultaneously. Rules apply/retract traits based on node properties and edges — truth maintenance ensures consistency. Compaction migrates stable dynamic properties into the core, hidden behind the same proxy interface.
**Trade-offs:** Proxy generation adds complexity. Truth maintenance requires a rule engine in the intelligence layer. Compaction is a schema migration concern. The SPI must store applied traits as metadata without knowing the trait interfaces themselves.
**Sources:** Drools Traits system (user's prior work), hybrid core+triple systems
**Exploration:** quick
**Status:** captured

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
