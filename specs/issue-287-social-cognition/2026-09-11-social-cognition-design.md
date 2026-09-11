# Multi-Agent Social Cognition — Comparative Affect and Cross-Domain Reasoning

**Epic:** casehubio/neocortex#287
**Children:** #271 (multi-agent perspectival queries), #283 (cross-domain reasoning)
**Module:** `cognitive-index`
**Package:** `io.casehub.neocortex.cognitive.index`

## Problem

cognitive-index has three disconnected query types that should compose:

- **CognitiveProfile** resolves entities without applying perspectival overlays
- **PerspectivalResolver** applies overlays without resolving memories or trajectory
- **AffectTrajectoryAnalyzer** computes trajectories without knowing about entities or perspectives

A caller who wants "everything about Grandma from Alice's perspective" needs three separate calls plus manual assembly. Worse, the trajectory is computed on the raw shared node's PAD values — not the perspectival view — producing incoherent results. Memory queries also lack principal scoping, so all agents' affect memories are returned undifferentiated.

Two new capabilities are needed:

1. **#271 — Multi-agent perspectival queries:** Compare how N agents feel about the same entity. Per-agent PAD differences, consensus vs divergence, trajectory comparison.
2. **#283 — Cross-domain reasoning:** Correlate temporal affect signals across life domains (subgraphs). "Work stress correlates with family tension." Same-principal privacy.

## Design

### Core Principle: Perspective is Constitutive

Perspective is not a post-processing step applied after entity resolution — it is part of entity resolution. The current separation (CognitiveProfile resolves, PerspectivalResolver overlays) is the architectural disease that produced two bugs: (1) trajectory computed on unmerged PAD, and (2) memory queries returning all agents' data undifferentiated. The fix is structural: internalize PerspectivalResolver inside CognitiveProfile so perspective is applied before any derived computation.

### Change 1: CognitiveProfileQuery gains perspective

```java
public record CognitiveProfileQuery(
    String nodeId,
    String entityName,
    String subgraphId,
    String tenantId,
    Set<MemoryDomain> domains,
    boolean includeEdges,
    int memoryLimit,
    PrincipalId asSeenBy    // NEW — nullable; null = shared/unperspectived view
) {
    // Existing factories unchanged — asSeenBy defaults to null
    public static CognitiveProfileQuery byId(String nodeId, String tenantId);
    public static CognitiveProfileQuery byName(String entityName, String tenantId);

    // New wither
    public CognitiveProfileQuery withAsSeenBy(PrincipalId principal);
}
```

Backward compatible. Callers who never set `asSeenBy` get identical behavior to today.

### Change 2: EntityKnowledge gains perceiver

```java
public record EntityKnowledge(
    MindMapNode node,
    List<MindMapEdge> edges,
    Map<MemoryDomain, List<Memory>> memories,
    AffectTrajectory trajectory,
    Set<NodeRef> unresolvedRefs,
    String tenantId,
    PrincipalId perceiver   // NEW — nullable; null = shared view
) {
    // Compact constructor: perceiver defaults to null for backward compat
}
```

The result identifies whose perspective it represents. When `perceiver` is non-null, `node` carries the merged perspectival PAD, and `trajectory` was computed from principal-scoped affect memories.

### Change 3: CognitiveProfile resolve() pipeline

When `query.asSeenBy()` is non-null, the resolution pipeline changes order:

1. Resolve the shared MindMap node (by ID or name) — unchanged
2. **Apply perspectival overlay** — call PerspectivalResolver (now package-private) to merge the agent's overlay onto the shared node
3. Collect entity IDs from the **merged** node
4. Query memories with `MemoryQuery.withCallerPrincipalId(asSeenBy)` — scopes affect memories to the requesting agent
5. Compute trajectory from the **principal-scoped** memories
6. Return EntityKnowledge with `perceiver = asSeenBy`

When `asSeenBy` is null, the pipeline is unchanged from today (steps 2 and 4's principal scoping are skipped).

### Change 4: CognitiveProfile gains compare()

```java
public Map<PrincipalId, EntityKnowledge> compare(
    CognitiveProfileQuery query, Set<PrincipalId> agents);
```

Batch comparison of N agents' perspectives on the same entity. The query's own `asSeenBy` is ignored — each agent's perspective is resolved independently. Internally:

1. Resolve the shared node once
2. Load all overlay nodes for the tenant once (single `MindMapStore.search()` with trait="overlay")
3. Partition overlays by `agentId` property — O(N) filter, not N separate scans
4. For each agent: merge overlay → collect entity IDs from merged node → query principal-scoped memories → compute trajectory
5. Return `Map<PrincipalId, EntityKnowledge>` with each entry's `perceiver` set

The key optimization: overlay loading happens once. The per-agent work (merge + memory query + trajectory) is lightweight.

### Change 5: PerspectivalResolver becomes package-private

PerspectivalResolver's overlay-loading logic is correct and stays as-is. Its visibility changes from `public @ApplicationScoped` to package-private. CognitiveProfile calls it internally. This reverses #253 D55 — confirmed zero external production callers (only tests and documentation reference it).

PerspectivalMerge remains public — it's a pure static utility used by tests and edge-case callers who need raw merge control.

### Change 6: SocialComparison — static utility for #271

```java
public final class SocialComparison {
    private SocialComparison() {}

    public static PerspectivalComparison compare(
        Map<PrincipalId, EntityKnowledge> perspectives);
}
```

Pure computation over already-resolved data. Same pattern as AffectTrajectoryAnalyzer and MindMapAnalyzer. The caller gets the map from `CognitiveProfile.compare()`, then passes it to `SocialComparison.compare()` for metrics.

**PerspectivalComparison** — result record:

```java
public record PerspectivalComparison(
    String entityId,
    String entityName,
    Map<PrincipalId, AffectSnapshot> perspectives,
    PadDistanceMatrix distances,
    Map<PadDimension, PairwiseDifferences> dimensionDifferences,
    TrajectoryAlignment trajectoryAlignment,
    int agentCount
) {}
```

**AffectSnapshot** — per-agent perspective:

```java
public record AffectSnapshot(
    PrincipalId agent,
    Double pleasure, Double arousal, Double dominance,
    AffectTrajectory trajectory   // nullable — included when temporal data available
) {}
```

**PadDistanceMatrix** — pairwise Euclidean distances in PAD space:

```java
public record PadDistanceMatrix(
    Map<AgentPair, Double> distances
) {
    public double distance(PrincipalId a, PrincipalId b);
    public double maxDistance();
    public double meanDistance();
}

public record AgentPair(PrincipalId a, PrincipalId b) {
    // Canonical ordering: a.value() < b.value() lexicographically
}
```

**PairwiseDifferences** — per-dimension signed differences:

```java
public record PairwiseDifferences(
    Map<AgentPair, Double> differences   // signed: a - b
) {
    public double difference(PrincipalId a, PrincipalId b);
}

public enum PadDimension { PLEASURE, AROUSAL, DOMINANCE }
```

**TrajectoryAlignment** — slope vector similarity:

```java
public record TrajectoryAlignment(
    Map<AgentPair, Double> cosineSimilarities,  // [-1, 1]
    Map<AgentPair, TrendAgreement> agreements
) {}

public enum TrendAgreement {
    ALIGNED,      // both trending same direction
    DIVERGENT,    // trending opposite directions
    MIXED,        // one stable, other trending
    INSUFFICIENT  // < 2 data points for one or both agents
}
```

Slope vector similarity uses `[pleasureSlope, dominanceSlope]` from AffectTrajectory. Cosine similarity captures both direction and rate agreement in a single metric.

### Change 7: DomainActivation — CDI bean for #283

```java
@ApplicationScoped
public class DomainActivation {

    @Inject
    public DomainActivation(Instance<MindMapStore> mindMapStore,
                            Instance<CaseMemoryStore> memoryStore);

    DomainActivation(MindMapStore mindMapStore, CaseMemoryStore memoryStore);

    public Optional<DomainActivationResult> correlate(
        DomainActivationQuery query);
}
```

**DomainActivationQuery**:

```java
public record DomainActivationQuery(
    PrincipalId principal,       // required — privacy by construction
    Set<String> subgraphIds,     // ≥ 2 subgraph instances to correlate
    String tenantId,
    Instant from,                // time window start
    Instant to,                  // time window end
    Duration bucketDuration      // aggregation bucket size; default 24h
) {
    public DomainActivationQuery {
        Objects.requireNonNull(principal, "principal required");
        Objects.requireNonNull(tenantId, "tenantId required");
        if (subgraphIds == null || subgraphIds.size() < 2)
            throw new IllegalArgumentException("at least 2 subgraphIds required");
        if (bucketDuration == null) bucketDuration = Duration.ofHours(24);
    }

    public static DomainActivationQuery between(
        PrincipalId principal, String tenantId,
        String subgraphA, String subgraphB);
}
```

Privacy enforcement is structural: `PrincipalId principal` is required, non-nullable. Cross-principal analysis is not expressible through this API.

**DomainActivationResult**:

```java
public record DomainActivationResult(
    Map<String, DomainSignal> domains,
    Map<DomainPair, DomainCorrelation> correlations,
    PrincipalId principal,
    String tenantId,
    Instant from, Instant to
) {}

public record DomainSignal(
    String subgraphId,
    AffectTrajectory trajectory,    // aggregate trajectory for entities in this subgraph
    int entityCount,
    int memoryCount,
    int bucketCount                 // number of time buckets with data
) {}

public record DomainPair(String subgraphIdA, String subgraphIdB) {
    // Canonical ordering: a < b lexicographically
}

public record DomainCorrelation(
    double dtwSimilarity,           // DTW similarity score [0, 1]
    List<AlignmentPair> alignment,  // temporal correspondence path
    int samplePairs,
    CorrelationStrength strength
) {}

public enum CorrelationStrength {
    STRONG,     // dtwSimilarity >= 0.7
    MODERATE,   // >= 0.4
    WEAK,       // >= 0.2
    NONE        // < 0.2
}
```

**Resolution flow:**

1. For each subgraphId: query `MindMapStore.search(MindMapQuery.of(tenantId, 1000).withSubgraphId(subgraphId))` for member entities
2. For each entity: query `CaseMemoryStore.query(MemoryQuery.forSubjects(..., AffectEvents.DOMAIN, tenantId).withCallerPrincipalId(principal))` for affect memories in the time window
3. Aggregate per-domain: time-bucketed mean PAD values (configurable `bucketDuration`)
4. Compute per-domain `AffectTrajectory` via `AffectTrajectoryAnalyzer.analyze()`
5. Compute pairwise DTW similarity using the pleasure dimension time series. Reuse or extract DTW algorithm from existing `DtwSimilarity` in memory-api
6. Return `Optional.empty()` if any domain has zero entities or zero memories

**DTW usage:** The existing `DtwSimilarity` operates on CBR-specific `FeatureValue`/`FeatureField` types. For cross-domain correlation, either:
- Extract the core DTW algorithm into a general-purpose utility in `cognitive-api` or `fusion-api`
- Adapt the input format to match DtwSimilarity's expectations

Decision deferred to implementation — both approaches work, and the algorithm is identical. The DTW constraints (Sakoe-Chiba band, Itakura parallelogram) and alignment path extraction from the existing implementation are reused either way.

### Change 8: Principal-scoped memory queries (D6)

When `CognitiveProfileQuery.asSeenBy()` is set, CognitiveProfile passes the principal to all memory queries:

```java
MemoryQuery.forSubjects(entityIds, domain, tenantId)
    .withCallerPrincipalId(asSeenBy)   // NEW — scopes to this agent's memories
    .withLimit(memoryLimit)
    .withOrder(MemoryOrder.CHRONOLOGICAL)
```

The memory infrastructure already supports this — `MemoryInput.principalId` and `MemoryQuery.withCallerPrincipalId()` exist but are currently unwired. `AffectEvents.toMemoryInput()` passes null for principalId. Callers storing agent-specific affect assessments must set `MemoryInput.withPrincipalId()` — existing memories with null principalId remain queryable by all agents (backward compatible).

## Module Impact

All changes in `cognitive-index`. No new modules.

| File | Change |
|------|--------|
| CognitiveProfileQuery.java | + `asSeenBy` field, + `withAsSeenBy()` |
| EntityKnowledge.java | + `perceiver` field |
| CognitiveProfile.java | + perspective in resolve(), + compare() method, + PerspectivalResolver composition |
| PerspectivalResolver.java | Visibility: public → package-private |
| SocialComparison.java | NEW — static utility |
| PerspectivalComparison.java | NEW — result record |
| AffectSnapshot.java | NEW — per-agent perspective record |
| PadDistanceMatrix.java | NEW — distance matrix with AgentPair |
| PairwiseDifferences.java | NEW — signed per-dimension differences |
| TrajectoryAlignment.java | NEW — slope vector cosine similarity |
| PadDimension.java | NEW — enum (PLEASURE, AROUSAL, DOMINANCE) |
| TrendAgreement.java | NEW — enum (ALIGNED, DIVERGENT, MIXED, INSUFFICIENT) |
| AgentPair.java | NEW — canonical pair record |
| DomainActivation.java | NEW — CDI bean |
| DomainActivationQuery.java | NEW — query record |
| DomainActivationResult.java | NEW — result record |
| DomainSignal.java | NEW — per-subgraph signal |
| DomainPair.java | NEW — canonical pair record |
| DomainCorrelation.java | NEW — DTW correlation result |
| CorrelationStrength.java | NEW — enum |

## Test Plan

### CognitiveProfile perspective integration (8 tests)

1. resolve() with asSeenBy applies overlay before trajectory computation
2. resolve() with asSeenBy scopes memory queries by principal
3. resolve() without asSeenBy returns shared view (backward compat)
4. resolve() with asSeenBy — MindMapStore unavailable returns empty (graceful degradation)
5. resolve() with asSeenBy — no overlay for agent returns shared node with perceiver set
6. EntityKnowledge.perceiver() is null for shared view, non-null for perspectival
7. compare() returns one EntityKnowledge per agent with correct perceiver
8. compare() loads overlays once (single MindMapStore.search call for all agents)

### SocialComparison (10 tests)

9. PAD distance matrix — two agents, known PAD values → expected Euclidean distance
10. PAD distance matrix — three agents, all pairwise distances computed
11. Pairwise signed differences — pleasure dimension, two agents
12. Pairwise signed differences — all three PAD dimensions
13. Trajectory alignment — both IMPROVING → ALIGNED, cosine ≈ 1.0
14. Trajectory alignment — one IMPROVING, one WORSENING → DIVERGENT, cosine ≈ -1.0
15. Trajectory alignment — one STABLE, one WORSENING → MIXED
16. Trajectory alignment — insufficient data (< 2 samples) → INSUFFICIENT
17. Single agent comparison → trivial result (distance 0, no pairwise differences)
18. Null PAD values treated as 0.0 in distance computation

### DomainActivation (12 tests)

19. Two subgraphs with correlated pleasure trajectories → STRONG DTW similarity
20. Two subgraphs with uncorrelated signals → WEAK/NONE
21. Principal scoping — only this agent's affect memories used
22. Time window filtering — memories outside window excluded
23. Time bucketing — 24h buckets aggregate correctly
24. Custom bucket duration (e.g., 1h) produces finer-grained signal
25. Empty subgraph (no entities) → Optional.empty()
26. Subgraph with entities but no affect memories → Optional.empty()
27. Graceful degradation — MindMapStore unavailable → Optional.empty()
28. Graceful degradation — CaseMemoryStore unavailable → Optional.empty()
29. Three subgraphs — all pairwise correlations computed
30. Minimum sample count enforcement — too few buckets → NONE strength

## Decisions

D1-D6 in `decisions.md`. Key choices:
- Perceiver-primary architecture with PerspectivalResolver internalized (D1)
- PAD distance, pairwise signed differences, slope vector similarity (D2)
- Domain signal = subgraphId-scoped affect trajectory with time-bucketed aggregation (D3)
- DTW for temporal similarity — platform-coherent with existing DtwSimilarity (D4)
- Privacy by method signature — single PrincipalId, non-nullable (D5)
- Principal-scoped memory queries via withCallerPrincipalId (D6)

## References

- PerspectivalResolver.java — overlay loading logic (becomes package-private)
- CognitiveProfile.java — resolve() pipeline, trajectory bug at computeTrajectory()
- AffectTrajectoryAnalyzer.java — static utility pattern, regression computation
- PerspectivalMerge.java — node merge logic (stays public)
- DtwSimilarity.java — existing DTW implementation in memory-api (157 lines)
- AlignmentPair.java — existing DTW alignment type in memory-api
- MemoryQuery.java — withCallerPrincipalId() for principal scoping
- MemoryInput.java — principalId field for storage scoping
- AffectEvents.java — toMemoryInput() currently passes null principalId
- MindMapQuery.java — withSubgraphId() for subgraph-scoped entity queries
- SubgraphTypes.java — PERSON/PROJECT/ORGANISATION constants
- 2026-09-01-perspectival-overlays-design.md — "Affect is Always Perspectival" principle
- Epley, Keysar et al. — perspective-taking anchoring research (cognitive science lens)
- Collins, Loftus — spreading activation model (cross-domain terminology)
- GitHub #271 — multi-agent perspectival queries
- GitHub #283 — cross-domain reasoning
- GitHub #253 — cognitive rearchitecture (parent program, D55 reversed)
