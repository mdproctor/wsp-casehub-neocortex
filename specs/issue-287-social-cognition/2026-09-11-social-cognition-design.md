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

**Cleanup:** Remove dead `CbrCaseMemoryStore` injection from CognitiveProfile. The `cbrStore` field (line 42) is unused — zero production references within cognitive-index. The import and constructor parameter are removed. TemporalIndex retains its own `CbrCaseMemoryStore` injection (separate concern, out of scope).

### Change 4: CognitiveProfile gains compare()

```java
public Map<PrincipalId, EntityKnowledge> compare(
    CognitiveProfileQuery query, Set<PrincipalId> agents);
```

Batch comparison of N agents' perspectives on the same entity. The query's own `asSeenBy` is ignored — each agent's perspective is resolved independently. Internally:

1. Resolve the shared node once
2. Load all overlay nodes for the tenant once via PerspectivalResolver's package-private `loadAllOverlays(tenantId)` method (single `MindMapStore.search()` with trait="overlay")
3. Partition overlays by `agentId` property — O(N) filter, not N separate scans
4. For each agent: merge overlay via `PerspectivalMerge.merge()` → collect entity IDs from merged node → query principal-scoped memories → compute trajectory
5. Return `Map<PrincipalId, EntityKnowledge>` with each entry's `perceiver` set

The key optimization: overlay loading happens once via `loadAllOverlays()`. The per-agent work (merge + memory query + trajectory) is lightweight. CognitiveProfile.compare() never reimplements overlay loading — all overlay logic stays in PerspectivalResolver.

### Change 5: PerspectivalResolver becomes package-private

PerspectivalResolver's overlay-loading logic is correct and stays as-is. Its visibility changes from `public @ApplicationScoped` to package-private. CognitiveProfile calls it internally. This reverses #253 D55 — confirmed zero external production callers (only tests and documentation reference it).

**New package-private method:** `loadAllOverlays(String tenantId)` returns `List<MindMapNode>` — all overlay nodes for the tenant, unfiltered by principal. This is the same `MindMapStore.search(MindMapQuery.of(tenantId, 1000).withTraits(Set.of("overlay")))` query the existing `loadOverlays(tenantId, principal)` already performs. The existing method now delegates to `loadAllOverlays()` and filters by principal in Java, eliminating logic duplication. CognitiveProfile.compare() calls `loadAllOverlays()` directly and partitions by agentId.

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
    Set<PrincipalId> unassessedAgents,   // agents with null PAD — excluded from distances and differences
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

PAD values are sourced from the merged perspectival node (`EntityKnowledge.node().pleasure()`, `.arousal()`, `.dominance()`). These are the agent's stored affect assessment of the entity — the canonical perspectival view after overlay merge. Not a temporal observation, not the trajectory endpoint, not the latest memory's PAD. When an agent has no overlay and the shared node has no PAD, all three values are null.

**PadDistanceMatrix** — pairwise Euclidean distances in PAD space:

```java
public record PadDistanceMatrix(
    Map<AgentPair, Double> distances
) {
    public OptionalDouble distance(PrincipalId a, PrincipalId b);
    public double maxDistance();
    public double meanDistance();
}

public record AgentPair(PrincipalId a, PrincipalId b) {
    // Canonical ordering: a.value() < b.value() lexicographically
}
```

**Null PAD handling:** PAD assessment is atomic — an agent is "assessed" if all three PAD dimensions (pleasure, arousal, dominance) are non-null after overlay merge, "unassessed" if any dimension is null. Unassessed agents are listed in `PerspectivalComparison.unassessedAgents` and excluded from both distance AND difference computations. `SocialComparison.compare()` pre-filters to assessed agents before computing any pairwise metrics. This avoids conflating "no opinion" with "neutral" (0.0). Callers who want null-as-neutral can compute it from AffectSnapshot directly.

**PairwiseDifferences** — per-dimension signed differences:

```java
public record PairwiseDifferences(
    Map<AgentPair, Double> differences   // signed: a - b
) {
    public OptionalDouble difference(PrincipalId a, PrincipalId b);
}

public enum PadDimension { PLEASURE, AROUSAL, DOMINANCE }
```

`PairwiseDifferences.difference()` returns `OptionalDouble` — consistent with `PadDistanceMatrix.distance()`. Pairs involving unassessed agents are excluded.

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

Slope vector similarity uses `[pleasureSlope, arousalSlope, dominanceSlope]` from AffectTrajectory — a 3D cosine similarity capturing direction and rate agreement across all PAD dimensions. This requires adding `arousalSlope` to AffectTrajectory (see Change 9). Arousal trend (both agents becoming more activated, or both calming) is a meaningful alignment signal that the previous 2D formulation missed.

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

**D3 composition note:** D3's trade-offs section directed DomainActivation to compose `CognitiveProfile.resolve()` for entity resolution. This directive is retracted. DomainActivation's aggregate pattern is fundamentally different from per-entity resolve(): it needs all entities in a subgraph (which CognitiveProfile doesn't expose), only affect memories in a time window (not all domains), and aggregate time-bucketed signals (not per-entity EntityKnowledge). Composing resolve() per-entity would waste I/O (fetching edges, all domains, per-entity trajectory) for data DomainActivation discards. The shared code between the two paths is `collectEntityIds(MindMapNode)` — extracted to a package-private utility in CognitiveProfile for reuse. DomainActivation does NOT need perspectival overlay merging: its signals come from principal-scoped affect memories (via `withCallerPrincipalId()`), not from entity-level PAD values. Refs come from the shared node (PerspectivalMerge preserves shared node refs), so overlay merge doesn't affect entity ID collection.

**DomainActivationQuery**:

```java
public record DomainActivationQuery(
    PrincipalId principal,       // required — privacy by construction
    Set<String> subgraphIds,     // ≥ 2 subgraph instances to correlate
    String tenantId,
    Instant from,                // time window start
    Instant to,                  // time window end
    Duration bucketDuration,     // aggregation bucket size; default 24h
    int entityLimit              // max entities per subgraph; default 1000
) {
    public DomainActivationQuery {
        Objects.requireNonNull(principal, "principal required");
        Objects.requireNonNull(tenantId, "tenantId required");
        if (subgraphIds == null || subgraphIds.size() < 2)
            throw new IllegalArgumentException("at least 2 subgraphIds required");
        if (bucketDuration == null) bucketDuration = Duration.ofHours(24);
        if (entityLimit < 1) entityLimit = 1000;
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
    int entityCount,                // entities included in signal (≤ entityLimit)
    boolean truncated,              // true if subgraph has more entities than entityLimit
    int memoryCount,
    int bucketCount                 // number of time buckets with data
) {}

public record DomainPair(String subgraphIdA, String subgraphIdB) {
    // Canonical ordering: a < b lexicographically
}

public record DomainCorrelation(
    double dtwSimilarity,           // DTW similarity score [0, 1]
    List<DtwAlignment> alignment,   // temporal correspondence path
    int samplePairs,
    CorrelationStrength strength
) {}

public record DtwAlignment(int indexA, int indexB) {}
// Defined alongside Dtw utility in cognitive-index. Domain-neutral
// naming — no CBR "query"/"case" semantics. AlignmentPair in
// memory-api remains unchanged for CBR use.

public enum CorrelationStrength {
    STRONG,     // dtwSimilarity >= 0.7  (provisional — see calibration note)
    MODERATE,   // >= 0.4
    WEAK,       // >= 0.2
    NONE        // < 0.2
}
// Thresholds are provisional. DTW similarity score distributions depend
// on input characteristics (autocorrelation, dimensionality, value range).
// PAD time series have high autocorrelation (emotional states persist),
// which may shift the baseline upward. Calibrate during implementation
// against representative PAD time series data — e.g., random-pair
// baseline to establish the score distribution floor.
```

**Resolution flow:**

1. For each subgraphId: query `MindMapStore.search(MindMapQuery.of(tenantId, query.entityLimit() + 1).withSubgraphId(subgraphId))` for member entities. If `returned.size() > entityLimit`, set `truncated = true` and use only the first `entityLimit` entities. `MindMapStore.search()` returns `List<MindMapNode>` with no count metadata, so the +1 probe is the only way to detect truncation without a separate count API.
2. For each entity: collect memory-linkable IDs via shared `collectEntityIds()` utility. Query `CaseMemoryStore.query(MemoryQuery.forSubjects(..., AffectEvents.DOMAIN, tenantId).withCallerPrincipalId(principal).withSince(from).withUntil(to))` for affect memories in the time window. The `withUntil()` method is a prerequisite addition to MemoryQuery (see Change 9).
3. Aggregate per-domain: time-bucketed mean PAD values (configurable `bucketDuration`). **Empty buckets (time periods with no affect memories) are skipped** — the time series contains only buckets with data. DTW handles unequal-length series natively (that's its purpose). Zero-fill would inject false "neutral" signals; forward-fill would assume stationarity without basis. `DomainSignal.bucketCount` reports how many buckets actually have data, letting callers assess sparsity relative to the time window. Sparse domains (few buckets relative to the window) produce low-confidence correlations — callers can threshold on `bucketCount` or use CorrelationStrength.
4. Compute per-domain `AffectTrajectory` via `AffectTrajectoryAnalyzer.analyze()`
5. Compute pairwise DTW similarity using the full 3D PAD time series (Euclidean distance across pleasure, arousal, dominance at each time point). This captures cross-dimension correlations that pleasure-only DTW would miss — e.g., work arousal (stress) correlating with family dominance (feeling controlled).
6. Return `Optional.empty()` if any domain has zero entities or zero memories

**DTW implementation:** Implement a lightweight `Dtw` utility class in cognitive-index operating on `double[][]` time series (each row is a time point, columns are PAD dimensions). The core DTW algorithm (distance matrix computation + backtrace, ~40 lines) is independent of CBR types. `DtwSimilarity` in memory-api remains unchanged — the algorithms are identical but the type interfaces are incompatible (`FeatureValue`/`FeatureField` vs raw doubles), and coupling them would require either a dependency from memory-api to cognitive-api (wrong direction) or a new shared module (overkill for 40 lines of algorithm). The `Dtw` utility reuses the same DTW structure: configurable warping constraints, early abandonment, alignment path extraction, and `1.0 / (1.0 + normalized)` scoring.

### Change 8: Principal-scoped memory queries (D6)

When `CognitiveProfileQuery.asSeenBy()` is set, CognitiveProfile passes the principal to all memory queries:

```java
MemoryQuery.forSubjects(entityIds, domain, tenantId)
    .withCallerPrincipalId(asSeenBy)   // NEW — scopes to this agent's memories
    .withLimit(memoryLimit)
    .withOrder(MemoryOrder.CHRONOLOGICAL)
```

The memory infrastructure already supports this — `MemoryInput.principalId` and `MemoryQuery.withCallerPrincipalId()` exist but are currently unwired. `AffectEvents.toMemoryInput()` passes null for principalId. Callers storing agent-specific affect assessments must set `MemoryInput.withPrincipalId()` — existing memories with null principalId remain queryable by all agents (backward compatible).

### Change 9: Prerequisite changes in memory-api and cognitive-index

**MemoryQuery gains `Instant until`** — time-range upper bound for DomainActivation's time-window queries. Symmetric with existing `since` field. All store implementations (InMemory, SQLite, JPA) already implement `since` filtering with the same pattern (`AND created_at >= ?`); adding `until` (`AND created_at <= ?`) is mechanical across all stores.

```java
// In MemoryQuery record:
Instant until    // NEW — upper time bound (nullable, null = unbounded)

public MemoryQuery withUntil(Instant until) {
    return new MemoryQuery(subjects, domain, tenantId, caseId, question, limit, since, until, order, callerPrincipalId);
}
```

**AffectTrajectory gains `arousalSlope`** — least-squares slope of arousal over time, computed alongside `pleasureSlope` and `dominanceSlope` in `AffectTrajectoryAnalyzer.analyze()`. The existing `arousalVolatility` (standard deviation) is retained — both are useful metrics (slope captures direction, volatility captures variability). **This is a breaking change:** inserting `arousalSlope` between `arousalVolatility` and `dominanceSlope` shifts positional constructor arguments. All existing `new AffectTrajectory(...)` call sites must be updated:
- `AffectTrajectoryAnalyzer.java` lines 26, 29, 61 (3 production sites)
- `EntityKnowledgeTest.java` line 63, `TemporalFocusTest.java` lines 68, 87, 104 (4 test sites)

The migration is mechanical — add the new `arousalSlope` argument at position 3.

```java
public record AffectTrajectory(
    double pleasureSlope,
    double arousalVolatility,
    double arousalSlope,       // NEW — least-squares slope of arousal over time
    double dominanceSlope,
    TrendDirection trend,
    double rateOfChange,
    int sampleCount
) {}
```

## Scope Notes

DomainActivation addresses the core cross-domain affect correlation scope of #283. The following aspects of #283 remain out of scope for this spec:

- **MoodEvents correlation:** MoodEvents are agent-global mood snapshots — they are not domain-scoped and cannot be attributed to a specific subgraph without capture pipeline changes (tagging mood with domain context).
- **ExperienceEvents correlation:** ExperienceEvents are discrete outcomes (achievements, setbacks), not continuous affect signals. DTW operates on continuous time series; correlating discrete events requires different techniques (event co-occurrence analysis, Granger causality on event-triggered windows).

These are tracked as separate issues for future #283 work.

## Module Impact

Primary changes in `cognitive-index`. Prerequisite change in `memory-api`.

**memory-api:**

| File | Change |
|------|--------|
| MemoryQuery.java | + `Instant until` field, + `withUntil()` wither |

**cognitive-index:**

| File | Change |
|------|--------|
| CognitiveProfileQuery.java | + `asSeenBy` field, + `withAsSeenBy()` |
| EntityKnowledge.java | + `perceiver` field |
| CognitiveProfile.java | + perspective in resolve(), + compare() method, + PerspectivalResolver composition, - `CbrCaseMemoryStore` injection |
| PerspectivalResolver.java | Visibility: public → package-private, + `loadAllOverlays()` package-private method |
| AffectTrajectory.java | + `arousalSlope` field |
| AffectTrajectoryAnalyzer.java | + arousal slope computation in analyze() |
| SocialComparison.java | NEW — static utility |
| PerspectivalComparison.java | NEW — result record |
| AffectSnapshot.java | NEW — per-agent perspective record |
| PadDistanceMatrix.java | NEW — distance matrix with AgentPair, unassessedAgents |
| PairwiseDifferences.java | NEW — signed per-dimension differences |
| TrajectoryAlignment.java | NEW — slope vector cosine similarity (3D) |
| PadDimension.java | NEW — enum (PLEASURE, AROUSAL, DOMINANCE) |
| TrendAgreement.java | NEW — enum (ALIGNED, DIVERGENT, MIXED, INSUFFICIENT) |
| AgentPair.java | NEW — canonical pair record |
| Dtw.java | NEW — lightweight DTW utility for double[] time series |
| DomainActivation.java | NEW — CDI bean |
| DomainActivationQuery.java | NEW — query record (with entityLimit) |
| DomainActivationResult.java | NEW — result record |
| DomainSignal.java | NEW — per-subgraph signal (with truncation tracking) |
| DomainPair.java | NEW — canonical pair record |
| DomainCorrelation.java | NEW — DTW correlation result |
| CorrelationStrength.java | NEW — enum (thresholds provisional) |

**memory store implementations** (InMemory, SQLite, JPA): add `until` filtering — symmetric with existing `since` filtering.

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
13. Trajectory alignment — both IMPROVING → ALIGNED, cosine ≈ 1.0 (3D slope vector)
14. Trajectory alignment — one IMPROVING, one WORSENING → DIVERGENT, cosine ≈ -1.0 (3D slope vector)
15. Trajectory alignment — one STABLE, one WORSENING → MIXED
16. Trajectory alignment — insufficient data (< 2 samples) → INSUFFICIENT
17. Single agent comparison → trivial result (distance 0, no pairwise differences)
18. Null PAD agents excluded from distance computation, listed in unassessedAgents

### DomainActivation (12 tests)

19. Two subgraphs with correlated 3D PAD trajectories → STRONG DTW similarity
20. Two subgraphs with uncorrelated signals → WEAK/NONE
21. Principal scoping — only this agent's affect memories used
22. Time window filtering — memories outside window excluded (via MemoryQuery.withUntil)
23. Time bucketing — 24h buckets aggregate correctly
24. Custom bucket duration (e.g., 1h) produces finer-grained signal
25. Empty subgraph (no entities) → Optional.empty()
26. Subgraph with entities but no affect memories → Optional.empty()
27. Graceful degradation — MindMapStore unavailable → Optional.empty()
28. Graceful degradation — CaseMemoryStore unavailable → Optional.empty()
29. Three subgraphs — all pairwise correlations computed
30. Minimum sample count enforcement — too few buckets → NONE strength
31. Subgraph exceeding entityLimit — DomainSignal.truncated is true, totalEntityCount > entityCount
32. Custom entityLimit on DomainActivationQuery is respected

### AffectTrajectory arousalSlope (2 tests)

33. analyze() computes arousalSlope alongside pleasureSlope and dominanceSlope
34. arousalSlope positive for increasing arousal series, negative for decreasing

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
