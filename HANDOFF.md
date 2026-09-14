# HANDOFF — casehub-neocortex

## Last Session

Designed and implemented cognitive observability (#333) — brainstorming, spec (3-round standard review, $20.61), plan (17 tasks / 3 batches), and execution of Batches 1-2 (14 of 17 tasks complete). Batch 3 (Layer 3 temporal observation) remains.

### What was built

**Layer 1 — Live View (Batch 1, complete):**
- `cognitive-observability` module — new Maven module with platform-api (@McpDomain) + MicroProfile GraphQL deps
- `CognitionInspectService` — per-subgraph node/edge counts, avg confidence, trait distribution, 5-bucket confidence histogram
- `CognitionHealthService` — wraps MindMapAnalyzer (orphans, contradictions, low-confidence, unvalidated edges, stale nodes, density, k-cores with Summary-trait filtering)
- `GraphSerializer` — toJson (Jackson) + toMermaid (StringBuilder) graph export
- `CognitionResolver` — @McpDomain("cognition") @GraphQLApi with inspect(), entity(), health() queries
- 14 tests green

**Layer 2 — Snapshot + Delta Infrastructure (Batch 2, complete):**
- `MutationContext` — ThreadLocal in mindmap-api for mutation source tagging
- `GraphMutation` — sealed interface (13 record variants: NodeAdded, NodeUpdated, NodeErased, EdgeAdded, EdgeRemoved, NodesMerged, NodeSuperseded, NodeReinstated, AliasAdded, AliasRemoved, SubgraphCreated, SubgraphErased, EntityErased) with Jackson @JsonTypeInfo
- `FieldChange` — diff() and diffSnapshot() for before/after field tracking (handles mutable InMemoryMindMapStore via pre-snapshot)
- `SnapshotStore` SPI — storeMutation, findMutations, findMutationsForEntity, storeKeyframe, reconstruct, audit entries, purge
- `MutationTrackingDecorator` — extends AbstractForwardingMindMapStore, intercepts all 14 mutation methods, pre-snapshots for updateNode
- `MutationTrackingCdiDecorator` — @Decorator @Priority(20), classpath-activated
- `ConsolidationCompleted` + `PhaseResult` CDI events in mindmap-intelligence
- ConsolidationScheduler modified: MutationContext set/clear per phase, fires ConsolidationCompleted per tenant
- ConversationBridge + ExtractionRequestedObserver: MutationContext wrapping
- `InMemorySnapshotStore` + `SnapshotStoreContractTest` (12 tests) in cognitive-observability-testing
- `SqliteSnapshotStore` (WAL, HikariCP, Flyway V1, junction table mutation_nodes) in cognitive-observability-sqlite — passes all 12 contract tests
- `SnapshotCaptureService` — observes ConsolidationCompleted, builds audit entries, keyframe threshold capture, retention purge

### Key findings during implementation

- InMemoryMindMapStore.getNode() returns a mutable StoredNode reference — updateNode mutates it in place. The decorator must snapshot node state into an immutable NodeSnapshot record before calling delegate().updateNode() to avoid aliasing
- mindmap-core was missing from root pom dependencyManagement — added
- MicroProfile GraphQL API 2.0 (`org.eclipse.microprofile.graphql`) provides @GraphQLApi/@Query/@Name/@DefaultValue — not managed by Quarkus BOM, version added to root dependencyManagement

## Immediate Next Step

**Batch 3: Layer 3 — Temporal Observation (3 tasks remaining)**
1. Task 15: `CognitionDiffService` + `GraphDiffResult` — structured diff with source filtering, wildcard support, default from=lastConsolidationTime
2. Task 16: `CognitionTraceService` + `EntityTrace` + `TraceEvent` — entity audit trail with bidirectional merge/supersession tracing
3. Task 17: Add diff() + trace() @Query methods to CognitionResolver, full build verification, CLAUDE.md update

All infrastructure is in place — Layer 3 tasks are pure query logic over the SnapshotStore SPI. Should be straightforward.

## References

- Spec: `wksp/specs/issue-322-cognitive-node-types/issue-333-cognitive-observability/2026-09-14-cognitive-observability-design.md`
- Decisions: `wksp/specs/issue-322-cognitive-node-types/issue-333-cognitive-observability/decisions.md` (D1-D10, 4 revised from review)
- Plan: `wksp/plans/2026-09-14-cognitive-observability.md`
- Open issues: #333 (cognitive observability epic — in progress)
