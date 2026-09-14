# Decisions — #333 Cognitive Observability

## D1: ConsolidationPhase SPI — no return type change

**Choice:** Keep `ConsolidationPhase.run()` returning `void`. The MindMapStore mutation-tracking decorator (D8) captures all mutations automatically — phases don't need to manually report what they changed.
**Alternatives:**
- Change return type to `List<GraphMutation>` — redundant with decorator capture, error-prone (phases must manually mirror what the store already recorded), creates circular dependency (D5/R1-05)
- Side-channel MutationCollector — same redundancy problem
**Rationale:** All 4 consolidation phases operate through `MindMapStore` (addNode, updateNode, mergeNodes, eraseNode). The decorator intercepts every call. ConsolidationScheduler sets the mutation context (phase name) before each `phase.run()` so the decorator tags mutations by source. No SPI break needed.
**Trade-offs:** Phases cannot report "semantic intent" beyond what the store operations imply. If a phase needs to annotate why it made a change (not just what changed), that information is lost. Acceptable — the phase name in the mutation tag provides sufficient context.
**Sources:** ConsolidationPhase.java, ConsolidationScheduler.java, decision review R1-03
**Exploration:** quick
**Status:** revised (was: change return type; reviewer R1-03 identified redundancy with decorator)

## D2: Module placement

**Choice:** New `cognitive-observability` module for all observability domain logic and GraphQL resolvers
**Alternatives:**
- Add to cognitive-index — mixes query infrastructure with presentation/tooling concerns
- Split types in cognitive-api, resolvers in new module — more wiring for marginal reuse
**Rationale:** Observability is read-only tooling, not core domain logic. Dedicated module keeps concerns separated. Depends on cognitive-index, mindmap-api, memory-api. Houses GraphQL resolvers (@McpDomain), snapshot/delta types, graph serialization.
**Trade-offs:** One more module in the build. GraphMutation types live here rather than in cognitive-api, so other modules can't depend on them without depending on observability.
**Sources:** Platform MCP pattern (@McpDomain + GraphQLModelScanner), existing module structure
**Exploration:** quick
**Status:** captured

## D3: GraphMutation type model

**Choice:** Sealed interface hierarchy with pattern matching
**Alternatives:**
- Flat enum-discriminated record — simpler but loses type safety, many nullable fields
**Rationale:** Each mutation type (NodeAdded, NodeRemoved, NodeUpdated, EdgeAdded, EdgeRemoved, NodesMerged, NodeSuperseded) is a record with exactly the fields it needs. Pattern matching in switch expressions. Consistent with ExperienceEvent sealed hierarchy in memory-api.
**Trade-offs:** More types to maintain than a single flat record. Serialization requires polymorphic handling (Jackson @JsonTypeInfo or manual).
**Sources:** ExperienceEvent sealed hierarchy (memory-api), FeatureValue sealed hierarchy (memory-api)
**Exploration:** quick
**Status:** captured

## D4: Snapshot model — per-subgraph with keyframe/delta

**Choice:** Each snapshot captures one subgraph: all nodes + edges for keyframes, List<GraphMutation> for deltas. Scoped per-tenant, per-subgraph.
**Alternatives:**
- Whole-tenant state — larger serialization, harder incremental capture, cross-subgraph ops naturally included
**Rationale:** Subgraphs are the natural partition unit. Consolidation phases already operate per-subgraph. Keeps snapshots manageable. Bridge edges captured by snapshotting both endpoint subgraphs.
**Trade-offs:** Cross-subgraph queries (bridge edges) require joining snapshots from multiple subgraphs. Reconstruction is per-subgraph, not per-tenant.
**Sources:** SubgraphTypes constants (mindmap-api), ConsolidationScheduler per-tenant iteration
**Exploration:** quick
**Status:** captured

## D5: Snapshot storage — SPI with SQLite implementation + retention policy

**Choice:** SnapshotStore SPI in the observability module API, SQLite implementation in a separate `cognitive-observability-sqlite` module. Time-based retention policy: configurable via `casehub.mindmap.snapshots.retention.days` (default 90), scheduled purge every 24h (consistent with CbrRetrievalTracker pattern).
**Alternatives:**
- In-memory ring buffer — no persistence across restarts, session-scoped only
- Append to existing mindmap SQLite DB — couples observability lifecycle to graph storage
**Rationale:** Follows the established pattern: MindMapStore/mindmap-sqlite, CaseMemoryStore/memory-sqlite, CbrRetrievalTracker/memory-cbr-tracking. SPI enables in-memory alternative for tests. SQLite with WAL + HikariCP + Flyway. Retention prevents unbounded growth.
**Trade-offs:** Another SQLite database file. SPI abstraction adds indirection for a single known implementation. Retention purge deletes old keyframe chains — reconstruction is only possible within the retention window.
**Sources:** SqliteMindMapStore, SqliteMemoryStore, SqliteCbrRetrievalTracker retention pattern, decision review R1-10
**Exploration:** quick
**Status:** revised (added retention policy per reviewer R1-10)

## D6: Graph serialization — static utility

**Choice:** GraphSerializer static utility class with toJson() and toMermaid() methods in cognitive-observability
**Alternatives:**
- SPI with pluggable format implementations — over-engineered for two known formats
**Rationale:** Serialization format is an observability concern, not a domain extension point. Jackson for JSON, string builder for Mermaid. No known consumers need other formats. Can be promoted to SPI later if needed (YAGNI).
**Trade-offs:** Adding a new format requires modifying the utility class rather than adding a new implementation.
**Sources:** Epic requirement for toJson() and toMermaid() export helpers
**Exploration:** quick
**Status:** captured

## D7: Snapshot capture trigger — natural boundaries

**Choice:** Flush delta snapshots at all natural mutation boundaries: end of consolidation run, end of conversation turn (ConversationBridge.process()), end of extraction (ExtractionRequestedObserver). Promote to keyframe every N deltas (configurable via `casehub.mindmap.snapshots.keyframe-interval`, default 10).
**Alternatives:**
- Consolidation boundary only — misses intermediate conversation/extraction mutations between consolidation runs
- Time-based interval — may snapshot unchanged state or miss rapid changes
- Mutation-count threshold — adaptive but decoupled from semantic boundaries
**Rationale:** The decorator (D8) buffers mutations. Each mutation source sets context and signals "batch complete" when its work unit finishes. The decorator flushes accumulated mutations as a delta to the SnapshotStore. `cognition_diff` queries deltas by time range, giving full mutation timeline. Keyframes are periodic full-state captures for reconstruction efficiency.
**Trade-offs:** More deltas stored than consolidation-only approach. Manual MindMapStore calls (not through a known source) produce individual deltas unless explicitly batched.
**Sources:** ConsolidationScheduler.tick(), ConversationBridge.process(), ExtractionRequestedObserver, decision review R1-06
**Exploration:** quick
**Status:** revised (was: consolidation boundary only; reviewer R1-06 identified observation gaps)

## D8: Mutation tracking — capture all, tag by source, fire CDI events

**Choice:** MindMapStore decorator captures every mutation and tags it with source context (consolidation phase name, conversation-bridge, extraction, manual). Thread-local context set by callers. Fires `GraphMutationRecorded` CDI event after flushing each delta batch — enables cross-module reactivity consistent with existing event patterns (AffectRecorded, CbrCasesErased, etc.).
**Alternatives:**
- Consolidation only — misses conversation/extraction mutations, partial observability
- Two decorators — clean separation but two interception points for the same concern
**Rationale:** Maximum observability. cognition_diff can filter by source. ConsolidationScheduler sets context before running phases; ConversationBridge and ExtractionRequestedObserver set their own context. Unknown sources get a "manual" tag. CDI events enable other modules to react to graph changes without coupling to the decorator. ThreadLocal is appropriate because MindMapStore is a synchronous SPI — all current callers (ConsolidationScheduler, ConversationBridge, ExtractionRequestedObserver) operate on worker threads, not reactive chains.
**Trade-offs:** Thread-local context coupling. All mutation paths must set context or accept default "manual" tag. Slight overhead on every MindMapStore write. If reactive callers are added to MindMapStore in future, ThreadLocal must be upgraded to Mutiny Context propagation.
**Sources:** AffectTrajectoryDecorator pattern, DerivedEdgeDecorator thread-local precedent, decision review R1-07 (ThreadLocal assessment), R1-09 (CDI events)
**Depends on:** D3 (GraphMutation model)
**Exploration:** quick
**Status:** revised (removed D1 dependency per R1-04; added CDI events per R1-09)

## D9: Epic decomposition — by layer

**Choice:** 3 child issues decomposed by layer: Layer 1 (live view), Layer 2 (snapshot/delta infrastructure), Layer 3 (temporal observation)
**Alternatives:**
- By tool (5 issues) — tools share infrastructure, risk of cross-cutting work
- Infrastructure + tools (2 issues) — infrastructure issue is large with no user-visible output
**Rationale:** Natural dependency chain. Layer 1 is independently useful (wraps existing MindMapAnalyzer + CognitiveProfile). Layer 2 is infrastructure (SPI, types, decorator, ConsolidationPhase change, SQLite). Layer 3 builds on Layer 2 (diff + trace tools).
**Trade-offs:** Layer 2 has no user-visible MCP tools — it's pure infrastructure. Layer 1 can ship without Layer 2/3.
**Sources:** Epic structure (3 layers defined), issue #333 body
**Exploration:** quick
**Status:** captured

## D10: MCP tool pattern — @McpDomain GraphQL resolvers

**Choice:** GraphQL resolvers annotated with @McpDomain("cognition"), auto-discovered by platform's GraphQLModelScanner + DynamicToolRegistrar
**Alternatives:** None considered — this is the established platform pattern
**Rationale:** Consistent with platform architecture. Domain defines GraphQL resolvers; platform auto-generates MCP tool exposure. No manual tool registration needed.
**Trade-offs:** Dependency on platform-api for annotations. GraphQL resolver boilerplate.
**Sources:** platform-api @McpDomain, GraphQLModelScanner, DynamicToolRegistrar, CaseHubMcpTools
**Exploration:** quick
**Status:** captured
