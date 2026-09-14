# Decisions — #333 Cognitive Observability

## D1: ConsolidationPhase SPI return type

**Choice:** Change `ConsolidationPhase.run()` return type from `void` to `List<GraphMutation>`
**Alternatives:**
- Side-channel MutationCollector — avoids SPI break but adds indirection and implicit state
- CDI events only — decoupled but harder to correlate with consolidation boundaries
**Rationale:** Clean, explicit contract. Each phase declares exactly what it changed. Callers (ConsolidationScheduler) get structured delta data without ambient state. All 4 existing phases updated — the SPI is internal to neocortex, so the break is contained.
**Trade-offs:** All 4 existing ConsolidationPhase implementations must be updated. Phases that don't mutate the graph return empty list.
**Sources:** ConsolidationPhase.java (mindmap-intelligence), ConsolidationScheduler.java, ExperienceEvent sealed hierarchy (memory-api) as pattern precedent
**Exploration:** quick
**Status:** captured

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

## D5: Snapshot storage — SPI with SQLite implementation

**Choice:** SnapshotStore SPI in the observability module API, SQLite implementation in a separate `cognitive-observability-sqlite` module
**Alternatives:**
- In-memory ring buffer — no persistence across restarts, session-scoped only
- Append to existing mindmap SQLite DB — couples observability lifecycle to graph storage
**Rationale:** Follows the established pattern: MindMapStore/mindmap-sqlite, CaseMemoryStore/memory-sqlite, CbrRetrievalTracker/memory-cbr-tracking. SPI enables in-memory alternative for tests. SQLite with WAL + HikariCP + Flyway.
**Trade-offs:** Another SQLite database file. SPI abstraction adds indirection for a single known implementation.
**Sources:** SqliteMindMapStore, SqliteMemoryStore, SqliteCbrRetrievalTracker patterns
**Exploration:** quick
**Status:** captured

## D6: Graph serialization — static utility

**Choice:** GraphSerializer static utility class with toJson() and toMermaid() methods in cognitive-observability
**Alternatives:**
- SPI with pluggable format implementations — over-engineered for two known formats
**Rationale:** Serialization format is an observability concern, not a domain extension point. Jackson for JSON, string builder for Mermaid. No known consumers need other formats. Can be promoted to SPI later if needed (YAGNI).
**Trade-offs:** Adding a new format requires modifying the utility class rather than adding a new implementation.
**Sources:** Epic requirement for toJson() and toMermaid() export helpers
**Exploration:** quick
**Status:** captured

## D7: Snapshot capture trigger — consolidation boundary

**Choice:** Capture delta snapshot after each consolidation run completes. Promote to keyframe every N deltas (configurable, default 10).
**Alternatives:**
- Time-based interval — may snapshot unchanged state or miss rapid changes
- Mutation-count threshold — adaptive but decoupled from consolidation boundaries
**Rationale:** ConsolidationScheduler already orchestrates phases sequentially. After all phases finish, their returned List<GraphMutation> are aggregated into a delta snapshot. Natural alignment with the primary source of graph change. Keyframe promotion is count-based with configurable interval.
**Trade-offs:** Non-consolidation mutations (conversation, extraction) are captured by the decorator but don't trigger snapshots. Snapshot granularity is tied to consolidation frequency.
**Sources:** ConsolidationScheduler.tick(), epic keyframe-interval config (casehub.mindmap.snapshots.keyframe-interval)
**Exploration:** quick
**Status:** captured

## D8: Mutation tracking — capture all, tag by source

**Choice:** MindMapStore decorator captures every mutation and tags it with source context (consolidation phase name, conversation-bridge, extraction, manual). Thread-local or context object set by callers.
**Alternatives:**
- Consolidation only — misses conversation/extraction mutations, partial observability
- Two decorators — clean separation but two interception points for the same concern
**Rationale:** Maximum observability. cognition_diff can filter by source. ConsolidationScheduler sets context before running phases; ConversationBridge and ExtractionRequestedObserver set their own context. Unknown sources get a "manual" tag.
**Trade-offs:** Thread-local context coupling. All mutation paths must set context or accept default "manual" tag. Slight overhead on every MindMapStore write.
**Sources:** AffectTrajectoryDecorator pattern, DerivedEdgeDecorator thread-local precedent
**Depends on:** D1 (ConsolidationPhase return type), D3 (GraphMutation model)
**Exploration:** quick
**Status:** captured

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
