# Cognitive Observability — Design Spec

**Issue:** casehubio/neocortex#333
**Date:** 2026-09-14
**Status:** Draft

## Overview

Expose the cognitive subsystem's internal state via MCP tools so LLMs and
human consumers can inspect, diff, and diagnose the MindMap + Memory graph.
Five MCP tools across three implementation layers, backed by a mutation-tracking
decorator and snapshot persistence infrastructure.

The system builds on existing foundations:
- **MindMapAnalyzer** — 9 static analysis methods (orphans, centrality, k-cores, contradictions, stale nodes)
- **CognitiveProfile.resolve()** — cross-store entity resolution (node + edges + memories across 6 domains + affect trajectory)
- **ConsolidationScheduler + ConsolidationPhase** — existing consolidation pipeline (4 phases, runs every 5 min)

## Module Structure

### New modules

| Module | Purpose | Dependencies |
|--------|---------|-------------|
| `cognitive-observability` | Domain logic, GraphQL resolvers (@McpDomain), mutation types, serialization | cognitive-index, cognitive-api, mindmap-api, mindmap-core, memory-api, platform-api |
| `cognitive-observability-sqlite` | SQLite SnapshotStore implementation | cognitive-observability, HikariCP, Flyway |
| `cognitive-observability-testing` | SnapshotStoreContractTest abstract base, InMemorySnapshotStore | cognitive-observability |

### Existing module changes

| Module | Change |
|--------|--------|
| `mindmap-api` | New `MutationContext` ThreadLocal holder (source tagging for mutations) |
| `mindmap-intelligence` | ConsolidationScheduler sets `MutationContext` before each phase, fires `ConsolidationCompleted` CDI event |

`ConsolidationPhase.run()` remains `void` — no SPI change. The decorator
(in cognitive-observability, classpath-activated) captures all mutations
automatically (D1). `MutationContext` lives in mindmap-api so both the
decorator and callers can reference it without circular dependencies.

**Module dependency rationale:**
- `cognitive-api` — `Confidence` record used in GraphMutation.NodeAdded
- `mindmap-core` — `MindMapAnalyzer` (9 static analysis methods) used by `cognition_health`

## Layer 1: Live View

Three MCP tools wrapping existing infrastructure. No snapshot/delta
dependency — independently useful.

### cognition_inspect

Aggregate stats for the cognitive graph. Answers: "What do I know right now?"

```java
@McpDomain("cognition")
@GraphQLApi
public class CognitionInspectResolver {

    @Query
    @PlatformQuery("Aggregate stats: node/edge counts per subgraph, confidence distribution, trait summary")
    public CognitionInspectResult inspect(
        @Name("tenantId") String tenantId,
        @Name("subgraphId") @Nullable String subgraphId  // null = all subgraphs
    ) { ... }
}
```

**CognitionInspectResult:**
- Per-subgraph: node count, edge count, avg confidence, trait distribution
- Confidence histogram (buckets: 0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0)
- Subgraph list with types

Note: "recent activity" is intentionally omitted — that's the domain of
`cognition_diff` (Layer 3). `cognition_inspect` reports current state only,
keeping it a pure Layer 1 tool with no persistence dependency.

Implementation: direct MindMapStore queries. No persistence dependency.

### cognition_entity

Deep dive on a single entity. Answers: "What do I know about X?"

```java
@Query
@PlatformQuery("Entity deep dive: node, edges, traits, PAD, confidence, affect trajectory, related memories")
public EntityKnowledge entity(
    @Name("tenantId") String tenantId,
    @Name("entityName") @Nullable String entityName,
    @Name("nodeId") @Nullable String nodeId,
    @Name("subgraphId") @Nullable String subgraphId,
    @Name("includeMemories") @DefaultValue("true") boolean includeMemories,
    @Name("memoryLimit") @DefaultValue("10") int memoryLimit
) { ... }
```

Implementation: delegates to `CognitiveProfile.resolve()` with
`CognitiveProfileQuery`. When `entityName` is provided with a `subgraphId`,
uses `CognitiveProfileQuery.byName(entityName, subgraphId, tenantId)` for
precise resolution; without `subgraphId`, uses
`CognitiveProfileQuery.byName(entityName, tenantId)` which resolves across
all subgraphs (both InMemoryMindMapStore and SqliteMindMapStore support
cross-subgraph resolution via null subgraphId).

Returns `EntityKnowledge` directly — it already contains node, edges,
memories, affect trajectory, unresolved refs. When the entity is not found
(`CognitiveProfile.resolve()` returns `Optional.empty()`), returns a
structured "not found" result with entityName/nodeId echoed back and null
fields, rather than throwing an error.

### cognition_health

Graph health diagnostics. Answers: "Is my graph healthy?"

```java
@Query
@PlatformQuery("Graph health: orphans, contradictions, low-confidence clusters, unvalidated edges, stale nodes")
public GraphHealthReport health(
    @Name("tenantId") String tenantId,
    @Name("subgraphId") @Nullable String subgraphId,
    @Name("staleThresholdDays") @DefaultValue("30") int staleThresholdDays,
    @Name("lowConfidenceThreshold") @DefaultValue("0.3") double lowConfidenceThreshold
) { ... }
```

**GraphHealthReport:**
- orphanNodes: count + list (from MindMapAnalyzer.orphanNodes)
- contradictions: count + list (from MindMapAnalyzer.contradictions)
- lowConfidenceRatio: double (from MindMapAnalyzer.lowConfidenceCluster)
- unvalidatedEdgeRatio: double (from MindMapAnalyzer.unvalidatedEdgeRatio)
- staleNodes: count + list (from MindMapAnalyzer.staleNodes)
- density: per-subgraph (from MindMapAnalyzer.subgraphDensity)
- kCores: community structure (from MindMapAnalyzer.kCores) — filters synthetic Summary-trait nodes per GE-20260910-2a660e

Implementation: wraps MindMapAnalyzer static methods. No persistence dependency.

**Null subgraphId behavior:** When `subgraphId` is null, iterates over
`store.listSubgraphs(tenantId)` and runs each analyzer method per subgraph.
Results are aggregated into a single `GraphHealthReport`:
- orphanNodes, contradictions, staleNodes: concatenated across subgraphs
- density: list of `SparseSubgraph` results (one per subgraph — already per-subgraph)
- kCores: concatenated, each tagged with subgraphId
- lowConfidenceRatio: per-subgraph `LowConfidenceCluster` results collected (not averaged)
- unvalidatedEdgeRatio: per-subgraph `UnvalidatedEdgeRatio` results collected

Per-subgraph results are returned as lists — no lossy aggregation (averaging, summing)
that would obscure subgraph-level detail.

### Graph serialization

Static utility `GraphSerializer` in cognitive-observability:
- `toJson(List<MindMapNode> nodes, List<MindMapEdge> edges)` → JSON string (Jackson)
- `toMermaid(List<MindMapNode> nodes, List<MindMapEdge> edges)` → Mermaid graph string
- `fromJson(String json)` → deserialized node/edge lists

Used by MCP tool results for export. Pure functions, no CDI dependencies.

## Layer 2: Snapshot + Delta Infrastructure

### GraphMutation — sealed interface hierarchy (D3)

The atomic unit of graph change. Lives in `cognitive-observability`.

```java
public sealed interface GraphMutation {
    Instant timestamp();
    String source();  // e.g. "consolidation:MergeDetectionPhase", "conversation-bridge", "extraction", "manual"

    // --- Node mutations ---

    record NodeAdded(String nodeId, String name, String subgraphId,
                     Confidence confidence, Instant timestamp, String source) implements GraphMutation {}

    record NodeUpdated(String nodeId, String subgraphId, Map<String, FieldChange> changes,
                       Instant timestamp, String source) implements GraphMutation {}

    record NodeErased(String nodeId, String subgraphId, int cascadedCount,
                      Instant timestamp, String source) implements GraphMutation {}

    // --- Edge mutations ---

    record EdgeAdded(String edgeId, String sourceNodeId, String targetNodeId,
                     String edgeType, Confidence confidence,
                     Instant timestamp, String source) implements GraphMutation {}

    record EdgeRemoved(String edgeId, String sourceNodeId, String targetNodeId,
                       String edgeType, Instant timestamp, String source) implements GraphMutation {}

    // --- Merge / supersession ---

    record NodesMerged(String survivorId, String absorbedId,
                       List<MergeConflict> conflictsResolved,
                       Instant timestamp, String source) implements GraphMutation {}

    record NodeSuperseded(String supersededId, String supersedingId,
                          String reason, Instant timestamp, String source) implements GraphMutation {}

    record NodeReinstated(String nodeId, Instant timestamp, String source) implements GraphMutation {}

    // --- Alias mutations ---

    record AliasAdded(String nodeId, String alias,
                      Instant timestamp, String source) implements GraphMutation {}

    record AliasRemoved(String nodeId, String alias,
                        Instant timestamp, String source) implements GraphMutation {}

    // --- Subgraph mutations ---

    record SubgraphCreated(String subgraphId, String name, String type,
                           Instant timestamp, String source) implements GraphMutation {}

    record SubgraphErased(String subgraphId, int nodesErased,
                          Instant timestamp, String source) implements GraphMutation {}

    // --- Bulk erasure ---

    record EntityErased(String entityName, int nodesAffected,
                        Instant timestamp, String source) implements GraphMutation {}
}
```

**FieldChange** record: `(String field, Object oldValue, Object newValue)` — captures
before/after for updated fields. Since the decorator pre-reads the node before
delegating `updateNode`, full before/after snapshots are available at zero extra cost.

`FieldChange.diff(MindMapNode before, NodeUpdate update)` behavior per field type:

| NodeUpdate field | FieldChange produced |
|-----------------|---------------------|
| `name` | `("name", before.name(), update.name())` |
| `confidence` | `("confidence", before.confidence(), update.confidence())` |
| `pleasure/arousal/dominance` | `("pleasure", before.pleasure(), update.pleasure())` etc. |
| `validFrom/validUntil` | `("validFrom", before.validFrom(), update.validFrom())` etc. |
| `traitsToAdd/traitsToRemove` | `("traits", before.traits(), computedNewTraits)` where `computedNewTraits = (before.traits() ∪ traitsToAdd) \ traitsToRemove` |
| `refsToAdd/refsToRemove` | `("refs", before.refs(), computedNewRefs)` where `computedNewRefs = (before.refs() ∪ refsToAdd) \ refsToRemove` |
| `propertiesToSet/propertiesToRemove` | `("properties", before.properties(), computedNewProps)` where `computedNewProps = (before.properties() ∪ propertiesToSet) \ propertiesToRemove` |

A FieldChange entry is only produced when the NodeUpdate field is non-null (for scalars)
or non-empty (for collection deltas). Trait/ref/property changes are captured as full
before/after snapshots rather than delta operations — this is consistent with the scalar
pattern and provides complete context for mutation replay without requiring the consumer
to understand delta semantics.

**NodesMerged** uses singular `absorbedId` matching the `MindMapStore.mergeNodes(keepNodeId, removeNodeId, tenantId)` API which merges exactly one pair. `conflictsResolved` comes from `MergeResult.propertyConflicts()`.

**`eraseEntityAcrossTenants` handling:** The decorator overrides this method to iterate tenants itself, calling `this.eraseEntity()` per tenant. This is necessary because concrete store implementations call `this.eraseEntity()` internally, which bypasses the decorator chain entirely — no `EntityErased` mutations would be captured. The same `this`-bypass pattern exists in `eraseSubgraph` (calls `this.eraseNode()`) and `eraseEntity` (calls `this.eraseNode()`), but those are acceptable because the decorator captures the aggregate mutation (`SubgraphErased`, `EntityErased`) at the top level.

**Intentionally excluded from the sealed hierarchy:** `updateSubgraph` changes only the root node pointer, which is not a graph topology change — it's metadata on the subgraph container.

### MutationContext (mindmap-api)

ThreadLocal holder for mutation source tagging. Lives in mindmap-api so both
the decorator (cognitive-observability) and callers (mindmap-intelligence) can
reference it without circular dependencies.

```java
public final class MutationContext {
    private static final ThreadLocal<String> SOURCE = ThreadLocal.withInitial(() -> "manual");

    public static void set(String source) { SOURCE.set(source); }
    public static String get() { return SOURCE.get(); }
    public static void clear() { SOURCE.remove(); }
}
```

### MutationTrackingDecorator (D8)

Two-class split following the established codebase convention (same pattern
as AffectTrajectoryDecorator + AffectTrajectoryCdiDecorator,
TraitApplicationDecorator + TraitApplicationCdiDecorator):

**Runtime class** — `MutationTrackingDecorator extends AbstractForwardingMindMapStore`
in `cognitive-observability`. Framework-neutral, unit-testable without CDI.

**CDI wiring class** — `MutationTrackingCdiDecorator extends MutationTrackingDecorator`
with `@Decorator @Priority(20)` in `cognitive-observability`. Classpath-activated —
when cognitive-observability is on the classpath, the decorator is active; when
absent, no tracking.

`@Priority(20)` — runs closest to the bean, after all domain decorators.
Active CDI decorators in the chain: TraitApplication `@Priority(70)`,
AffectTrajectory `@Priority(65)`. (ConfidenceDecay and VocabularyNormalization
are runtime-only decorators with no CDI variants. DerivedEdgeCdiDecorator
lacks `@Decorator` annotation and is not currently active in the CDI chain.)

```java
// Runtime class — cognitive-observability module
public class MutationTrackingDecorator extends AbstractForwardingMindMapStore {

    private final SnapshotStore snapshotStore;  // nullable
    private final Consumer<GraphMutationRecorded> eventSink;

    public MutationTrackingDecorator(MindMapStore delegate,
                                      SnapshotStore snapshotStore,
                                      Consumer<GraphMutationRecorded> eventSink) {
        super(delegate);
        this.snapshotStore = snapshotStore;
        this.eventSink = eventSink;
    }

    @Override
    public String addNode(NodeInput input, String tenantId) {
        String nodeId = delegate().addNode(input, tenantId);
        persistMutation(new GraphMutation.NodeAdded(
            nodeId, input.name(), input.subgraphId(),
            input.confidence(), Instant.now(), MutationContext.get()), tenantId);
        return nodeId;
    }

    @Override
    public void updateNode(String nodeId, NodeUpdate update, String tenantId) {
        // Pre-read to capture old values for FieldChange (same pattern as AffectTrajectoryDecorator)
        MindMapNode before = delegate().getNode(nodeId, tenantId);
        delegate().updateNode(nodeId, update, tenantId);
        Map<String, FieldChange> changes = FieldChange.diff(before, update);
        if (!changes.isEmpty()) {
            String subgraphId = before != null ? before.subgraphId() : null;
            persistMutation(new GraphMutation.NodeUpdated(
                nodeId, subgraphId, changes, Instant.now(), MutationContext.get()), tenantId);
        }
    }

    @Override
    public String addEdge(EdgeInput input, String tenantId) {
        String edgeId = delegate().addEdge(input, tenantId);
        persistMutation(new GraphMutation.EdgeAdded(
            edgeId, input.sourceNodeId(), input.targetNodeId(),
            input.edgeType(), input.confidence(),
            Instant.now(), MutationContext.get()), tenantId);
        return edgeId;
    }

    @Override
    public void removeEdge(String edgeId, String tenantId) {
        MindMapEdge edge = delegate().getEdge(edgeId, tenantId);
        delegate().removeEdge(edgeId, tenantId);
        if (edge != null) {
            persistMutation(new GraphMutation.EdgeRemoved(
                edgeId, edge.sourceNodeId(), edge.targetNodeId(),
                edge.edgeType(), Instant.now(), MutationContext.get()), tenantId);
        }
    }

    @Override
    public int eraseNode(String nodeId, String tenantId) {
        MindMapNode node = delegate().getNode(nodeId, tenantId);
        int affected = delegate().eraseNode(nodeId, tenantId);
        String subgraphId = node != null ? node.subgraphId() : null;
        persistMutation(new GraphMutation.NodeErased(
            nodeId, subgraphId, affected - 1,  // cascadedCount = edges + aliases deleted
            Instant.now(), MutationContext.get()), tenantId);
        return affected;
    }

    @Override
    public int eraseEntityAcrossTenants(String entityName, Set<String> tenantIds) {
        // Override required: concrete stores call this.eraseEntity() internally,
        // which bypasses the decorator chain. Iterating here routes each call
        // through this decorator's eraseEntity() override, capturing mutations.
        int count = 0;
        for (String tid : tenantIds) {
            count += this.eraseEntity(entityName, tid);
        }
        return count;
    }

    @Override
    public MergeResult mergeNodes(String keepNodeId, String removeNodeId, String tenantId) {
        MergeResult result = delegate().mergeNodes(keepNodeId, removeNodeId, tenantId);
        persistMutation(new GraphMutation.NodesMerged(
            result.survivingNodeId(), removeNodeId,
            result.propertyConflicts(),
            Instant.now(), MutationContext.get()), tenantId);
        return result;
    }

    @Override
    public void supersede(String targetId, String supersedingId, String reason, String tenantId) {
        delegate().supersede(targetId, supersedingId, reason, tenantId);
        persistMutation(new GraphMutation.NodeSuperseded(
            targetId, supersedingId, reason,
            Instant.now(), MutationContext.get()), tenantId);
    }

    @Override
    public void reinstate(String targetId, String tenantId) {
        delegate().reinstate(targetId, tenantId);
        persistMutation(new GraphMutation.NodeReinstated(
            targetId, Instant.now(), MutationContext.get()), tenantId);
    }

    @Override
    public void addAlias(String nodeId, String alias, String tenantId) {
        delegate().addAlias(nodeId, alias, tenantId);
        persistMutation(new GraphMutation.AliasAdded(
            nodeId, alias, Instant.now(), MutationContext.get()), tenantId);
    }

    @Override
    public void removeAlias(String nodeId, String alias, String tenantId) {
        delegate().removeAlias(nodeId, alias, tenantId);
        persistMutation(new GraphMutation.AliasRemoved(
            nodeId, alias, Instant.now(), MutationContext.get()), tenantId);
    }

    @Override
    public String createSubgraph(SubgraphInput input, String tenantId) {
        String subgraphId = delegate().createSubgraph(input, tenantId);
        persistMutation(new GraphMutation.SubgraphCreated(
            subgraphId, input.name(), input.type(),
            Instant.now(), MutationContext.get()), tenantId);
        return subgraphId;
    }

    @Override
    public int eraseSubgraph(String subgraphId, String tenantId) {
        int affected = delegate().eraseSubgraph(subgraphId, tenantId);
        persistMutation(new GraphMutation.SubgraphErased(
            subgraphId, affected, Instant.now(), MutationContext.get()), tenantId);
        return affected;
    }

    @Override
    public int eraseEntity(String entityName, String tenantId) {
        int affected = delegate().eraseEntity(entityName, tenantId);
        persistMutation(new GraphMutation.EntityErased(
            entityName, affected, Instant.now(), MutationContext.get()), tenantId);
        return affected;
    }

    private void persistMutation(GraphMutation mutation, String tenantId) {
        if (snapshotStore != null) {
            snapshotStore.storeMutation(tenantId, mutation);
        }
        eventSink.accept(new GraphMutationRecorded(tenantId, mutation));
    }
}
```

```java
// CDI wiring class — cognitive-observability module
@Decorator
@Priority(20)
public class MutationTrackingCdiDecorator extends MutationTrackingDecorator {

    @Inject
    public MutationTrackingCdiDecorator(@Delegate @Any MindMapStore delegate,
                                         Instance<SnapshotStore> snapshotStore,
                                         Event<GraphMutationRecorded> event) {
        super(delegate,
              snapshotStore.isResolvable() ? snapshotStore.get() : null,
              event::fire);
    }
}
```

No explicit flush needed. Each mutation is persisted immediately. No buffer,
no caller coupling. The decorator is self-contained.

**Subgraph attribution strategy:** `addNode` and `createSubgraph` get subgraphId
from the input. `updateNode` and `eraseNode` get subgraphId from the pre-read
(no extra cost — the pre-read is already needed for FieldChange or cascade count).
Operations without a natural pre-read (`removeEdge`, `addEdge`) get subgraphId
from the edge's source/target nodes only when a pre-read is already happening;
otherwise subgraph_id is null in the mutations table and queries handle it
accordingly.

**CDI event:** `GraphMutationRecorded(String tenantId, GraphMutation mutation, Instant timestamp)`

### MutationContext integration

Callers set `MutationContext` via the shared ThreadLocal in mindmap-api.
No import of the decorator needed. Each entry point that calls MindMapStore
is responsible for setting its own context — no thread propagation needed.

**Thread safety constraint:** `MutationContext` uses `ThreadLocal`, which is
correct for the current architecture where all MindMapStore operations execute
synchronously on the calling thread. ConsolidationScheduler uses a
single-threaded `ScheduledExecutorService`, and ConversationBridge processes
synchronously on the request thread. If future work dispatches MindMapStore
calls to virtual threads or async executors, each async entry point must set
its own MutationContext (as ExtractionRequestedObserver already does — see below).

ConsolidationScheduler changes (in mindmap-intelligence):

```java
// In tick() — event fires per tenant, inside the tenant loop:
for (String tenantId : memoryStore.discoverTenants(null, null)) {
    List<String> priority = subgraphPriority(tenantId);
    List<PhaseResult> phaseResults = new ArrayList<>();
    for (ConsolidationPhase phase : phases) {
        Instant phaseStart = Instant.now();
        MutationContext.set("consolidation:" + phase.name());
        try {
            phase.run(tenantId, priority);
            phaseResults.add(new PhaseResult(
                phase.name(), phaseStart, Instant.now(), true, null));
        } catch (Exception e) {
            phaseResults.add(new PhaseResult(
                phase.name(), phaseStart, Instant.now(), false, e.getMessage()));
            LOG.log(Level.WARNING, "Phase " + phase.name()
                + " failed for tenant " + tenantId, e);
        } finally {
            MutationContext.clear();
        }
    }
    consolidationCompletedEvent.fire(new ConsolidationCompleted(tenantId, phaseResults));
}
// Note: AccessFrequencyPhase.beginTick() runs BEFORE the tenant loop — no MutationContext needed there

// In consolidateNow(tenantId) — same pattern:
List<PhaseResult> phaseResults = new ArrayList<>();
for (ConsolidationPhase phase : phases) {
    Instant phaseStart = Instant.now();
    MutationContext.set("consolidation:" + phase.name());
    try {
        phase.run(tenantId, priority);
        phaseResults.add(new PhaseResult(phase.name(), phaseStart, Instant.now(), true, null));
    } catch (Exception e) {
        phaseResults.add(new PhaseResult(phase.name(), phaseStart, Instant.now(), false, e.getMessage()));
    } finally { MutationContext.clear(); }
}
consolidationCompletedEvent.fire(new ConsolidationCompleted(tenantId, phaseResults));
```

**PhaseResult semantics:** Every phase produces a `PhaseResult` regardless of
success or failure — both are recorded. `SnapshotCaptureService` maps each
`PhaseResult` to a `PhaseAuditEntry`, enriching with `mutationCount` by querying
`SnapshotStore.findMutations(tenantId, null, pr.startedAt(), pr.completedAt())`
filtered by source tag `"consolidation:" + phaseName`.

ConversationBridge changes (in mindmap-intelligence):

```java
public SegmentationResult process(String cleanedText, String tenantId,
                                   List<String> recentEntityNames,
                                   Object principalId) {
    MutationContext.set("conversation-bridge");
    try {
        // ... existing processing ...
        return new SegmentationResult(createdNodeIds, segments.size());
    } finally {
        MutationContext.clear();
    }
}
```

ExtractionRequestedObserver changes (in mindmap-intelligence):

```java
// @ObservesAsync runs on a different thread — sets its own MutationContext
public void onExtractionRequested(@ObservesAsync ExtractionRequested event) {
    MutationContext.set("extraction");
    try {
        // ... existing extraction + supersede logic ...
    } finally {
        MutationContext.clear();
    }
}
```

### Keyframe capture

`SnapshotCaptureService` (`@ApplicationScoped` in cognitive-observability)
observes `ConsolidationCompleted` CDI event. After each consolidation run:
1. Count mutations since last keyframe for each affected subgraph
2. If count >= keyframe interval, capture a keyframe by reading current
   subgraph state from MindMapStore
3. Handle retention purge on the same schedule

`ConsolidationCompleted` CDI event added to mindmap-intelligence:
```java
public record ConsolidationCompleted(String tenantId,
                                      List<PhaseResult> phaseResults) {}

public record PhaseResult(String phaseName, Instant startedAt, Instant completedAt,
                           boolean success, String errorMessage) {}
```

`PhaseResult` carries per-phase timing and success/failure status so that
`SnapshotCaptureService` can construct `ConsolidationAuditEntry` without
access to the `ConsolidationPhase` registry (which is in `mindmap-intelligence`,
not `cognitive-observability`). Total duration is derivable from
`phaseResults.first().startedAt()` to `phaseResults.last().completedAt()`.

### GraphSnapshot model (D4)

Per-subgraph, per-tenant snapshots with keyframe/delta distinction.

```java
public record GraphSnapshot(
    String snapshotId,
    String tenantId,
    String subgraphId,
    Instant capturedAt,
    SnapshotType type,
    // Keyframe fields (null for DELTA):
    List<NodeSnapshot> nodes,
    List<EdgeSnapshot> edges,
    // Delta fields (null for KEYFRAME):
    List<GraphMutation> mutations,
    String parentKeyframeId
) {
    public enum SnapshotType { KEYFRAME, DELTA }
}

public record NodeSnapshot(String id, String name, String subgraphType,
    Confidence confidence, Double pleasure, Double arousal, Double dominance,
    Set<String> traits, List<NodeRef> refs, Map<String, Object> properties,
    Instant createdAt, Instant updatedAt) {}

public record EdgeSnapshot(String id, String sourceNodeId, String targetNodeId,
    String edgeType, ValidationTier tier, Confidence confidence,
    Instant createdAt, Instant updatedAt) {}
```

**Cross-subgraph mutations (R1-08):** Bridge edges and cross-subgraph merges
are captured by the decorator with source node IDs. The mutation record
includes all node IDs involved. When querying deltas for a specific subgraph,
mutations that reference nodes outside that subgraph are included if any
referenced node belongs to the queried subgraph.

### SnapshotStore SPI (D5)

```java
public interface SnapshotStore {
    // --- Mutation storage ---
    void storeMutation(String tenantId, GraphMutation mutation);
    List<GraphMutation> findMutations(String tenantId, String subgraphId, Instant from, Instant to);
    List<GraphMutation> findMutationsForEntity(String tenantId, String nodeId, Instant from, Instant to);

    // --- Keyframe storage ---
    void storeKeyframe(GraphSnapshot keyframe);
    GraphSnapshot reconstruct(String tenantId, String subgraphId, Instant pointInTime);
    Optional<GraphSnapshot> latestKeyframe(String tenantId, String subgraphId);
    long mutationCountSinceKeyframe(String tenantId, String subgraphId);

    // --- Consolidation audit log ---
    void storeAuditEntry(ConsolidationAuditEntry entry);
    List<ConsolidationAuditEntry> findAuditEntries(String tenantId, Instant from, Instant to);
    Optional<Instant> lastConsolidationTime(String tenantId);

    // --- Lifecycle ---
    void purge(SnapshotRetentionPolicy policy);
    long count(String tenantId);
}
```

**SnapshotRetentionPolicy:** `record SnapshotRetentionPolicy(Duration maxAge, String tenantId)`
Default: 90 days, configurable via `casehub.mindmap.snapshots.retention.days`.

**Purge scheduling:** Purge runs as an observer on `ConsolidationCompleted` inside
`SnapshotCaptureService`. On each consolidation completion, the service checks if
24 hours have elapsed since the last purge (tracked via a volatile `lastPurgeTime`
field). This avoids a separate `ScheduledExecutorService` and reuses the
consolidation scheduler's existing lifecycle. The purge itself is synchronous and
lightweight (single SQL DELETE with timestamp predicate).

**Keyframe promotion (D7):** After storing a delta, check delta count since
last keyframe. If >= `casehub.mindmap.snapshots.keyframe-interval` (default 10),
capture a new keyframe by reading current subgraph state from MindMapStore.

**Reconstruction:** Find nearest keyframe <= pointInTime. Find all deltas
between keyframe and pointInTime. Apply mutations sequentially to keyframe state.

### SQLite implementation

`cognitive-observability-sqlite` module. Tables:

```sql
-- V1__create_snapshot_tables.sql
CREATE TABLE mutations (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    subgraph_id TEXT,           -- nullable for cross-subgraph mutations
    source TEXT NOT NULL,       -- e.g. "consolidation:MergeDetectionPhase"
    mutation_type TEXT NOT NULL, -- e.g. "NodeAdded", "NodesMerged"
    timestamp TEXT NOT NULL,
    data TEXT NOT NULL           -- JSON blob of the full GraphMutation record
);

CREATE INDEX idx_mutations_tenant_subgraph_time
    ON mutations(tenant_id, subgraph_id, timestamp);

-- Junction table: maps each mutation to ALL affected node IDs.
-- Multi-node mutations (merges, supersessions, edges) produce multiple rows.
CREATE TABLE mutation_nodes (
    mutation_id TEXT NOT NULL REFERENCES mutations(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    PRIMARY KEY (mutation_id, node_id)
);

CREATE INDEX idx_mutation_nodes_lookup
    ON mutation_nodes(tenant_id, node_id);

CREATE TABLE keyframes (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    subgraph_id TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    data TEXT NOT NULL           -- JSON blob of NodeSnapshot[] + EdgeSnapshot[]
);

CREATE INDEX idx_keyframes_tenant_subgraph_time
    ON keyframes(tenant_id, subgraph_id, captured_at);

CREATE TABLE audit_entries (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT NOT NULL,
    data TEXT NOT NULL           -- JSON blob of ConsolidationAuditEntry
);

CREATE INDEX idx_audit_tenant_time
    ON audit_entries(tenant_id, completed_at);
```

WAL mode, HikariCP connection pool, Flyway migrations. Same patterns as
SqliteMindMapStore and SqliteCbrRetrievalTracker.

**Entity indexing via junction table:** `storeMutation` extracts all affected
node IDs from each mutation type and inserts rows into `mutation_nodes`:

| Mutation type | Node IDs indexed |
|--------------|-----------------|
| `NodeAdded`, `NodeUpdated`, `NodeErased`, `NodeReinstated` | `nodeId` |
| `AliasAdded`, `AliasRemoved` | `nodeId` |
| `EdgeAdded`, `EdgeRemoved` | `sourceNodeId`, `targetNodeId` |
| `NodesMerged` | `survivorId`, `absorbedId` |
| `NodeSuperseded` | `supersededId`, `supersedingId` |
| `SubgraphCreated`, `SubgraphErased`, `EntityErased` | none (no specific node) |

`findMutationsForEntity(tenantId, nodeId, from, to)` queries via JOIN:
```sql
SELECT m.* FROM mutations m
JOIN mutation_nodes mn ON m.id = mn.mutation_id
WHERE mn.tenant_id = ? AND mn.node_id = ? AND m.timestamp BETWEEN ? AND ?
ORDER BY m.timestamp
```

This ensures `cognition_trace` returns complete audit trails — e.g., querying
the absorbed node in a merge returns the `NodesMerged` mutation with TraceEvent
type `MERGED_INTO`, and querying the survivor returns it with type `MERGED_FROM`.

**GraphMutation JSON serialization:** The `mutation_type` column serves as the
discriminator for Jackson deserialization. On write, `mutation_type` is set to
the simple class name of the GraphMutation variant (e.g., `"NodeAdded"`,
`"NodesMerged"`). On read, the `mutation_type` value determines which record
class to deserialize the `data` JSON blob into. This is implemented via a
Jackson `@JsonTypeInfo(use = Id.NAME, property = "type")` +
`@JsonSubTypes(...)` on the `GraphMutation` sealed interface, with the `type`
field written into the JSON blob. The `mutation_type` column is a denormalized
copy for SQL filtering without JSON parsing.
`SnapshotStoreContractTest` includes a round-trip test for each of the 14
mutation types to enforce serialization consistency across implementations.

### In-memory implementation (testing)

`cognitive-observability-testing` module. `InMemorySnapshotStore @Alternative @Priority(2)`.
`SnapshotStoreContractTest` abstract base with tests for store/find/reconstruct/purge.

## Layer 3: Temporal Observation

Two MCP tools building on Layer 2 infrastructure.

### cognition_diff

Structured delta between two points. Answers: "What changed?"

```java
@Query
@PlatformQuery("Structured delta: what changed between two points in time")
public GraphDiffResult diff(
    @Name("tenantId") String tenantId,
    @Name("subgraphId") @Nullable String subgraphId,
    @Name("from") @Nullable String from,       // ISO-8601 timestamp
    @Name("to") @Nullable String to,           // ISO-8601 timestamp, default now
    @Name("source") @Nullable String source    // filter by source tag
) { ... }
```

**GraphDiffResult:**
- mutations: filtered `List<GraphMutation>` from `SnapshotStore.findMutations()`
- summary: aggregate counts (nodesAdded, nodesErased, nodesUpdated, edgesAdded, edgesRemoved, merges, supersessions, reinstated)
- timeRange: actual from/to after resolution

If `from` is null, defaults to the last consolidation completion timestamp
(retrieved via `SnapshotStore.lastConsolidationTime(tenantId)`). If no
consolidation has run, defaults to 24 hours ago. If `subgraphId` is null,
returns mutations across all subgraphs. `source` filter matches mutation source
tags (e.g., "consolidation:*", "conversation-bridge").

### cognition_trace

Entity audit trail. Answers: "What happened to entity X over time?"

```java
@Query
@PlatformQuery("Entity audit trail: creation, updates, merges, supersessions, confidence changes over time")
public EntityTrace trace(
    @Name("tenantId") String tenantId,
    @Name("entityName") @Nullable String entityName,
    @Name("nodeId") @Nullable String nodeId,
    @Name("subgraphId") @Nullable String subgraphId,
    @Name("from") @Nullable String from,
    @Name("to") @Nullable String to
) { ... }
```

**EntityTrace:**
- entityId: resolved node ID
- entityName: current name
- events: List<TraceEvent> — chronological list of all mutations affecting this entity
- currentState: EntityKnowledge (from CognitiveProfile.resolve())

**TraceEvent:** wraps a GraphMutation with additional context:
- mutation: the GraphMutation record
- type: enum (CREATED, UPDATED, MERGED_INTO, MERGED_FROM, SUPERSEDED, SUPERSEDED_BY, REINSTATED, ERASED, ALIAS_ADDED, ALIAS_REMOVED)
- relatedEntities: node IDs of other entities involved (merge partner, superseding node, etc.)

Implementation: queries `SnapshotStore.findMutationsForEntity(tenantId, nodeId, from, to)`
directly — the SPI already provides entity-scoped queries, so no post-filtering needed.
Resolves entity by name via MindMapStore if nodeId not provided (using `subgraphId`
if supplied for precise resolution).

### Consolidation audit log

`SnapshotCaptureService` constructs audit entries from `ConsolidationCompleted`
events (the scheduler itself is in `mindmap-intelligence` and cannot reference
`ConsolidationAuditEntry` from `cognitive-observability`):

```java
public record ConsolidationAuditEntry(
    String tenantId,
    Instant startedAt,
    Instant completedAt,
    List<PhaseAuditEntry> phases
) {}

public record PhaseAuditEntry(
    String phaseName,
    Duration duration,
    int mutationCount,
    boolean success,
    String errorMessage  // null on success
) {}
```

Stored via `SnapshotStore.storeAuditEntry()`, queryable via
`SnapshotStore.findAuditEntries(tenantId, from, to)`. Used by `cognition_diff`
to correlate mutations with consolidation phases, and by
`SnapshotStore.lastConsolidationTime()` for cognition_diff's default `from`.

## Configuration

| Property | Default | Description |
|----------|---------|-------------|
| `casehub.mindmap.snapshots.enabled` | `false` | Enable/disable snapshot capture |
| `casehub.mindmap.snapshots.keyframe-interval` | `10` | Deltas between keyframes |
| `casehub.mindmap.snapshots.retention.days` | `90` | Snapshot retention period |
| `casehub.mindmap.snapshots.sqlite.path` | (required when enabled) | SQLite database path |

Layer 1 tools work without snapshots enabled. Layer 3 tools require
`casehub.mindmap.snapshots.enabled=true`.

## Epic Decomposition (D9)

Three child issues:

### Child 1: Layer 1 — Live View (M / Low)
- cognition_inspect, cognition_entity, cognition_health resolvers
- GraphSerializer utility (toJson, toMermaid)
- GraphHealthReport, CognitionInspectResult types
- No snapshot dependency

### Child 2: Layer 2 — Snapshot + Delta Infrastructure (L / Med)
- MutationContext ThreadLocal holder in mindmap-api
- GraphMutation sealed hierarchy (14 mutation types) + FieldChange in cognitive-observability
- MutationTrackingDecorator + MutationTrackingCdiDecorator on MindMapStore in cognitive-observability (classpath-activated)
- MutationContext integration (ConsolidationScheduler tick() + consolidateNow(), ConversationBridge, ExtractionRequestedObserver)
- ConsolidationCompleted CDI event in mindmap-intelligence
- GraphSnapshot, NodeSnapshot, EdgeSnapshot types
- SnapshotStore SPI + SnapshotRetentionPolicy
- SnapshotCaptureService (keyframe triggering via ConsolidationCompleted observation)
- SQLite SnapshotStore implementation + Flyway migrations
- InMemorySnapshotStore + SnapshotStoreContractTest
- GraphMutationRecorded CDI event
- ConsolidationAuditEntry types

### Child 3: Layer 3 — Temporal Observation (M / Med)
- cognition_diff resolver + GraphDiffResult
- cognition_trace resolver + EntityTrace + TraceEvent
- Consolidation audit log persistence + query
- Depends on Layer 2

## Gotchas

- k-core community detection includes synthetic Summary-trait nodes — filter them in cognition_health (GE-20260910-2a660e)
- Synthetic container nodes cause false integrity mismatches — exclude from orphan detection (GE-20260805-aa8a88)
- Never write to graph during tick loop — all observability tools are read-only (GE-20260912-be7c74)
- MutationTrackingCdiDecorator @Priority(20) — lowest priority = runs closest to the bean, after TraitApplication(@70) and AffectTrajectory(@65), so it captures the final mutation
- MutationContext uses ThreadLocal — correct for current synchronous architecture; async entry points (ExtractionRequestedObserver) must set their own context

## References

- MindMapAnalyzer — `mindmap-core/src/main/java/.../runtime/MindMapAnalyzer.java`
- CognitiveProfile — `cognitive-index/src/main/java/.../CognitiveProfile.java`
- ConsolidationScheduler — `mindmap-intelligence/src/main/java/.../consolidation/ConsolidationScheduler.java`
- ConsolidationPhase SPI — `mindmap-intelligence/src/main/java/.../consolidation/ConsolidationPhase.java`
- Platform MCP pattern — `platform-api/src/main/java/.../mcp/@McpDomain.java`, `platform/mcp/GraphQLModelScanner.java`
- ExperienceEvent sealed hierarchy — `memory-api/src/main/java/.../experience/ExperienceEvent.java`
- AffectTrajectoryDecorator — `mindmap/src/main/java/.../AffectTrajectoryDecorator.java`
- GE-20260912-ff141b — Neocortex cognitive stack overview
- GE-20260912-be7c74 — Three-tier memory architecture (read-only observation constraint)
- GE-20260910-2a660e — k-core includes synthetic nodes
- GE-20260805-aa8a88 — Synthetic container nodes cause false integrity mismatches
- GE-20260818-c2f072 — Testing MCP domain dispatch without CDI
- GE-20260814-0fcc1a — CaseLifecycleEvent CDI observer pattern
- casehubio/neocortex#333 — epic issue
