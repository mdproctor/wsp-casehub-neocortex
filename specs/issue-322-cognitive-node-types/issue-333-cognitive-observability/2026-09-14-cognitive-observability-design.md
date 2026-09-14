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
| `cognitive-observability` | Domain logic, GraphQL resolvers (@McpDomain), mutation types, serialization | cognitive-index, mindmap-api, memory-api, platform-api |
| `cognitive-observability-sqlite` | SQLite SnapshotStore implementation | cognitive-observability, HikariCP, Flyway |
| `cognitive-observability-testing` | SnapshotStoreContractTest abstract base, InMemorySnapshotStore | cognitive-observability |

### Existing module changes

| Module | Change |
|--------|--------|
| `mindmap` | New `MutationTrackingDecorator` (@Decorator on MindMapStore) |
| `mindmap-intelligence` | ConsolidationScheduler sets `MutationContext` before each phase |

`ConsolidationPhase.run()` remains `void` — no SPI change. The decorator captures
all mutations automatically (D1).

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
    @PlatformQuery("Aggregate stats: node/edge counts per subgraph, confidence distribution, trait summary, recent activity")
    public CognitionInspectResult inspect(
        @Name("tenantId") String tenantId,
        @Name("subgraphId") @Nullable String subgraphId  // null = all subgraphs
    ) { ... }
}
```

**CognitionInspectResult:**
- Per-subgraph: node count, edge count, avg confidence, trait distribution
- Confidence histogram (buckets: 0-0.2, 0.2-0.4, 0.4-0.6, 0.6-0.8, 0.8-1.0)
- Recent activity: last N mutations (from decorator buffer, if available)
- Subgraph list with types

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
    @Name("includeMemories") @DefaultValue("true") boolean includeMemories,
    @Name("memoryLimit") @DefaultValue("10") int memoryLimit
) { ... }
```

Implementation: delegates to `CognitiveProfile.resolve()` with
`CognitiveProfileQuery`. Returns `EntityKnowledge` directly — it already
contains node, edges, memories, affect trajectory, unresolved refs.

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

    record NodeAdded(String nodeId, String name, String subgraphId,
                     Confidence confidence, Instant timestamp, String source) implements GraphMutation {}

    record NodeRemoved(String nodeId, Instant timestamp, String source) implements GraphMutation {}

    record NodeUpdated(String nodeId, Map<String, FieldChange> changes,
                       Instant timestamp, String source) implements GraphMutation {}

    record EdgeAdded(String edgeId, String sourceNodeId, String targetNodeId,
                     String edgeType, Confidence confidence,
                     Instant timestamp, String source) implements GraphMutation {}

    record EdgeRemoved(String edgeId, String sourceNodeId, String targetNodeId,
                       String edgeType, Instant timestamp, String source) implements GraphMutation {}

    record NodesMerged(String survivorId, Set<String> absorbedIds,
                       List<MergeConflict> conflictsResolved,
                       Instant timestamp, String source) implements GraphMutation {}

    record NodeSuperseded(String supersededId, String supersedingId,
                          String reason, Instant timestamp, String source) implements GraphMutation {}
}
```

**FieldChange** record: `(String field, Object oldValue, Object newValue)` — captures
before/after for updated fields (confidence, PAD dimensions, properties, traits).

### MutationTrackingDecorator (D8)

`@Decorator @Priority(20)` on `MindMapStore` in the `mindmap` module.
Low priority — runs after all domain decorators (DerivedEdge @80,
AffectTrajectory @65, ConfidenceDecay, Vocabulary).

```java
@Decorator
@Priority(20)
public class MutationTrackingDecorator implements MindMapStore {

    @Inject @Delegate MindMapStore delegate;
    @Inject Event<GraphMutationRecorded> mutationEvent;
    @Inject Instance<SnapshotStore> snapshotStore;

    // ThreadLocal set by callers (ConsolidationScheduler, ConversationBridge, etc.)
    private static final ThreadLocal<String> MUTATION_SOURCE = ThreadLocal.withInitial(() -> "manual");

    public static void setSource(String source) { MUTATION_SOURCE.set(source); }
    public static void clearSource() { MUTATION_SOURCE.remove(); }

    // Per-thread mutation buffer — flushed at batch boundary
    private static final ThreadLocal<List<GraphMutation>> BUFFER = ThreadLocal.withInitial(ArrayList::new);

    @Override
    public MindMapNode addNode(NodeInput input, String tenantId) {
        MindMapNode result = delegate.addNode(input, tenantId);
        BUFFER.get().add(new GraphMutation.NodeAdded(
            result.id(), result.name(), input.subgraphId(),
            result.confidence(), Instant.now(), MUTATION_SOURCE.get()));
        return result;
    }

    // Similar interception for updateNode, removeNode, addEdge, removeEdge, mergeNodes, supersede

    public static void flush(String tenantId, String subgraphId) {
        List<GraphMutation> mutations = new ArrayList<>(BUFFER.get());
        BUFFER.get().clear();
        if (!mutations.isEmpty()) {
            // Persist delta via SnapshotStore (if available)
            // Fire CDI event
        }
    }
}
```

**Flush callers:**
- `ConsolidationScheduler` — after all phases complete for a tenant
- `ConversationBridge` — at end of `process()`
- `ExtractionRequestedObserver` — at end of extraction

**CDI event:** `GraphMutationRecorded(String tenantId, String subgraphId, List<GraphMutation> mutations, Instant timestamp)`

### MutationContext integration

ConsolidationScheduler changes (in mindmap-intelligence):

```java
// In tick(), before each phase:
for (ConsolidationPhase phase : phases) {
    MutationTrackingDecorator.setSource("consolidation:" + phase.name());
    try {
        phase.run(tenantId, priority);
    } finally {
        MutationTrackingDecorator.clearSource();
    }
}
MutationTrackingDecorator.flush(tenantId, null);  // null = all subgraphs
```

ConversationBridge changes (in mindmap-intelligence):

```java
public List<MindMapNode> process(String text, String tenantId, ...) {
    MutationTrackingDecorator.setSource("conversation-bridge");
    try {
        // ... existing processing ...
        return nodes;
    } finally {
        MutationTrackingDecorator.flush(tenantId, "general");
        MutationTrackingDecorator.clearSource();
    }
}
```

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
    void storeKeyframe(GraphSnapshot keyframe);
    void storeDelta(GraphSnapshot delta);
    GraphSnapshot reconstruct(String tenantId, String subgraphId, Instant pointInTime);
    List<GraphSnapshot> findDeltas(String tenantId, String subgraphId, Instant from, Instant to);
    Optional<GraphSnapshot> latestKeyframe(String tenantId, String subgraphId);
    void purge(SnapshotRetentionPolicy policy);
    long count(String tenantId);
}
```

**SnapshotRetentionPolicy:** `record SnapshotRetentionPolicy(Duration maxAge, String tenantId)`
Default: 90 days, configurable via `casehub.mindmap.snapshots.retention.days`.
Purge scheduled every 24h (ScheduledExecutorService daemon thread).

**Keyframe promotion (D7):** After storing a delta, check delta count since
last keyframe. If >= `casehub.mindmap.snapshots.keyframe-interval` (default 10),
capture a new keyframe by reading current subgraph state from MindMapStore.

**Reconstruction:** Find nearest keyframe <= pointInTime. Find all deltas
between keyframe and pointInTime. Apply mutations sequentially to keyframe state.

### SQLite implementation

`cognitive-observability-sqlite` module. Tables:

```sql
-- V1__create_snapshot_tables.sql
CREATE TABLE snapshots (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    subgraph_id TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    type TEXT NOT NULL,  -- KEYFRAME or DELTA
    parent_keyframe_id TEXT,
    data TEXT NOT NULL,  -- JSON blob (nodes+edges for keyframe, mutations for delta)
    FOREIGN KEY (parent_keyframe_id) REFERENCES snapshots(id)
);

CREATE INDEX idx_snapshots_tenant_subgraph_time
    ON snapshots(tenant_id, subgraph_id, captured_at);

CREATE INDEX idx_snapshots_type
    ON snapshots(type);
```

WAL mode, HikariCP connection pool, Flyway migrations. Same patterns as
SqliteMindMapStore and SqliteCbrRetrievalTracker.

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
- mutations: filtered List<GraphMutation> from SnapshotStore.findDeltas()
- summary: aggregate counts (nodesAdded, nodesRemoved, nodesUpdated, edgesAdded, edgesRemoved, merges, supersessions)
- timeRange: actual from/to after resolution

If `from` is null, defaults to last consolidation run. If `subgraphId` is null,
returns deltas across all subgraphs. `source` filter matches mutation source tags
(e.g., "consolidation:*", "conversation-bridge").

### cognition_trace

Entity audit trail. Answers: "What happened to entity X over time?"

```java
@Query
@PlatformQuery("Entity audit trail: creation, updates, merges, supersessions, confidence changes over time")
public EntityTrace trace(
    @Name("tenantId") String tenantId,
    @Name("entityName") @Nullable String entityName,
    @Name("nodeId") @Nullable String nodeId,
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
- type: enum (CREATED, UPDATED, MERGED_INTO, MERGED_FROM, SUPERSEDED, SUPERSEDED_BY, DELETED)
- relatedEntities: node IDs of other entities involved (merge partner, superseding node, etc.)

Implementation: queries SnapshotStore.findDeltas() for the time range, filters
mutations that reference the target entity's node ID (including as absorbedId
in merges, or supersededId in supersessions). Resolves entity by name via
MindMapStore if nodeId not provided.

### Consolidation audit log

ConsolidationScheduler emits structured audit entries after each run:

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

Stored via SnapshotStore alongside graph snapshots. Queryable by `cognition_diff`
to correlate mutations with consolidation phases.

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
- GraphMutation sealed hierarchy + FieldChange
- MutationTrackingDecorator on MindMapStore
- MutationContext integration (ConsolidationScheduler, ConversationBridge, ExtractionRequestedObserver)
- GraphSnapshot, NodeSnapshot, EdgeSnapshot types
- SnapshotStore SPI + SnapshotRetentionPolicy
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
- MutationTrackingDecorator @Priority(20) — must run AFTER all domain decorators so it captures the final mutation, not intermediate states

## References

- MindMapAnalyzer — `mindmap-runtime/src/main/java/.../MindMapAnalyzer.java`
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
