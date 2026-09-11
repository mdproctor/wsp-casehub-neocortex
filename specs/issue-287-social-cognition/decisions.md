# Decisions — issue-287-social-cognition

## D1: Architecture approach for social cognition in cognitive-index

**Choice:** Perceiver-primary re-architecture — CognitiveProfile internalizes PerspectivalResolver, gains batched compare(), perspective applied before trajectory computation. Two new focused types (SocialComparison static utility, DomainActivation CDI bean).
**Alternatives:**
- Unified Query Engine — single CognitiveQueryEngine replacing all types. Rejected: trades three small tested types for one ~500-line orchestrator in a codebase where the largest class is 162 lines.
- Perspective as cross-cutting concern — Perspective sealed interface on every cognitive query type. Rejected: no evidence TemporalIndex needs perspective; speculative blast radius.
- Signal-Producer SPI — CDI-discovered producers with topological ordering. Rejected: speculative extensibility for zero production callers; type-erased signal map worse than typed fields.
- Focused Compositions (original Position C) — just add perspective field + two new beans. Superseded: missed the perceiver-primary insight, didn't batch compare(), kept PerspectivalResolver as public API.
**Rationale:** Perspective is constitutive of entity resolution, not a post-processing step. The structural defect is twofold: (1) EntityKnowledge.node() returns unmerged PAD values when perspective is not applied, and (2) CognitiveProfile.queryMemories() and computeTrajectory() never call MemoryQuery.withCallerPrincipalId() — affect memories from all agents are returned undifferentiated. Internalizing PerspectivalResolver gives CognitiveProfile the PrincipalId needed to scope both node resolution AND memory queries. Batched compare() avoids N redundant overlay scans. asSeenBy() is optional because admin views, exports, and tests genuinely need the shared view. Static utility for comparison follows AffectTrajectoryAnalyzer precedent — pure computation over already-resolved data. Explicitly reverses #253 D55 (which made PerspectivalResolver @ApplicationScoped public) — zero external production callers confirmed, only tests and documentation reference it.
**Trade-offs:** PerspectivalResolver becomes package-private — callers who want raw overlay control lose direct access (mitigated: PerspectivalMerge stays public for edge cases). No extensibility framework for future social cognition features (mitigated: extract SPI when concrete implementations justify it, same as fusion-api extraction from rag-api).
**Sources:** PerspectivalResolver.java, CognitiveProfile.java (trajectory bug: both node PAD and memory queries lack principal scoping), AffectTrajectoryAnalyzer.java, Epley/Keysar perspective-taking research (cognitive science architect), existing codebase SPI extraction precedent (fusion-api from rag-api), #253 D55/D63/D64 (PerspectivalResolver lineage)
**Exploration:** multi-agent-debate (2 rounds — round 1: 3 assigned positions + mediator; round 2: 3 independent architects with different lenses + mediator)
**Status:** revised (R1-03: D55 reversal acknowledged; R1-04: trajectory bug rationale corrected to include memory query scoping)

## D2: SocialComparison result model

**Choice:** Three focused metrics — PAD distance matrix (pairwise Euclidean in PAD space), per-dimension pairwise signed differences (each cell is the signed difference between two agents on one PAD dimension), trajectory alignment (slope vector similarity via cosine of [pleasureSlope, dominanceSlope] vectors + TrendDirection categorical agreement). No outlier detection or aggregate scores — callers derive those from pairwise metrics and raw per-agent data. Comparison space is PAD-only — property, edge, and memory-set comparison are separate social cognition features deferred beyond #287.
**Alternatives:**
- Full divergence record with outlier detection, aggregate divergence score, distance matrices beyond pairwise — over-specified for zero callers, callers can derive from raw data
- Single aggregate "divergence score" — loses the per-dimension signal that makes the result actionable
- Per-dimension variance as consensus metric — degenerates for N=2 (most common comparison), not directly interpretable without group size context
- Mahalanobis or weighted Euclidean distance — theoretically better for correlated PAD dimensions (P-D correlation ~0.3-0.5 per Mehrabian), but requires covariance matrix from population data not yet available; Euclidean distortion is modest (~8% for P+D aligned differences) and preserves ordinal rankings
**Rationale:** Maps to real social cognition questions: "how far apart?" (distance), "do they agree per dimension?" (pairwise differences), "are they trending together?" (slope alignment). Slope vector similarity uses pleasureSlope and dominanceSlope already computed by AffectTrajectoryAnalyzer — captures both direction and rate in a single metric. Pairwise signed differences are directly interpretable ("Alice sees this as pleasant, Bob doesn't") regardless of group size. PAD-only scope is deliberate for #287's social cognition through affect; EntityKnowledge carries edges, properties, and memories that support richer comparison as future features.
**Trade-offs:** Callers who want outlier detection or aggregate scores compute them from pairwise metrics and raw Map<PrincipalId, EntityKnowledge>. Acceptable because pairwise differences make outlier identification trivial. Euclidean distance is an approximation for correlated PAD dimensions — refinable to Mahalanobis when population data supports covariance estimation, a single function change with no architectural impact.
**Sources:** AffectTrajectory.java (slope fields for alignment), AffectTrajectoryAnalyzer.java (static utility pattern)
**Exploration:** quick
**Depends on:** D1 (SocialComparison as static utility)
**Status:** revised (R1-07: trajectory alignment now uses slope vector similarity; R1-08: consensus metric changed from variance to pairwise signed differences; R1-22: PAD-only scope made explicit)

## D3: Domain signal model for cross-domain reasoning

**Choice:** Domain signal = aggregate affect trajectories for all entities within a subgraph instance (identified by subgraphId, not SubgraphType). "Domain" in DomainActivation means subgraphId — each subgraph instance is one correlation unit. Flow: query MindMapStore for subgraph member entities via MindMapQuery.withSubgraphId() → query CaseMemoryStore for affect memories in time window → aggregate into per-domain time series via time-bucketed mean PAD values (configurable bucket duration). Callers provide subgraphIds to correlate; the mapping from life-domain concepts ("work", "family") to subgraph instances is a caller concern.
**Alternatives:**
- Domain-scoped mood memories — requires changes to the mood capture pipeline to tag mood with context. More accurate but out of scope for #287.
- Experience event correlation — correlate outcomes across domains instead of affect. Complementary signal but less directly emotional.
- Explicit life-domain tagging on MindMapNodes — adds a "life-domain" property independent of subgraphType. Requires schema changes and migration for zero callers.
- SubgraphType-based domain grouping — too coarse; SubgraphTypes (PERSON, PROJECT, ORGANISATION, etc.) are entity classification categories, not life domains. "Work" entities may span PROJECT + ORGANISATION subgraphs.
**Rationale:** Works with existing data, no pipeline changes. Entity-level affect trajectories scoped by subgraphId IS the agent's "work emotional trajectory." SubgraphId-based querying is concrete and flexible — callers define what constitutes a domain by choosing subgraphs. Time-bucketed mean PAD aggregation is simple and interpretable; bucket duration is configurable to balance resolution vs noise. Mood memories are agent-global and can't be domain-scoped without capture pipeline changes.
**Trade-offs:** Subgraphs with few entities or sparse affect data produce noisy signals. Mitigated by minimum sample count enforcement in the result. Time-bucketed mean smooths individual entity signals and may understate peak correlations — acceptable for a first implementation. DomainActivation shares entity-to-memory resolution logic with CognitiveProfile (collectEntityIds, Subject creation); DomainActivation should compose CognitiveProfile.resolve() for entity resolution rather than duplicating, per the D1 round 1 synthesis's extraction trigger.
**Sources:** MindMapQuery.withSubgraphId() (subgraph instance query), SubgraphTypes.java (entity classification types — NOT the domain boundary), AffectEvents.DOMAIN, CaseMemoryStore.query()
**Exploration:** quick
**Depends on:** D1 (DomainActivation as CDI bean)
**Status:** revised (R1-11: domain = subgraphId clarified, SubgraphType confusion resolved; R1-12: time-bucketed mean PAD aggregation strategy specified)

## D4: Correlation algorithm for cross-domain reasoning

**Choice:** DTW (Dynamic Time Warping) for temporal similarity and alignment between domain signals. Result: per-domain trajectories + pairwise DTW similarity scores + alignment paths (temporal correspondence between domains) + sample counts. Result semantics are constrained to similarity and temporal alignment — NOT prediction or causation.
**Alternatives:**
- Pearson correlation + sliding-window cross-correlation — simple, interpretable, but assumes linear relationships (Pearson) and stationarity (cross-correlation). Emotional time series are non-stationary and autoregressive, producing spurious correlations from shared trends and misidentifying autoregressive momentum as temporal lag. Detrending mitigates but doesn't eliminate these problems.
- Granger causality — statistical test for predictive relationship ("does A help predict B?"). Required for any claim that domain A PRECEDES or PREDICTS domain B. Computationally expensive and data-hungry. Future enhancement when the temporal alignment from DTW motivates hypothesis testing.
- Pearson only (no lag) — simplest but least informative; misses temporal structure entirely.
**Rationale:** DTW exists in the codebase (DtwSimilarity, 157 lines, well-tested with Sakoe-Chiba and Itakura constraints, early abandonment, alignment path extraction). Using it for cross-domain affect similarity is platform-coherent — the same algorithm class used for CBR time series similarity. DTW makes no linearity or stationarity assumptions, handles variable-rate processes, and compares time series shapes directly. The alignment path gives richer temporal correspondence than cross-correlation's single lag value. DTW is O(n²) vs Pearson's O(n), but the bottleneck is I/O (multi-store queries), not computation on the resulting time series. The existing DtwSimilarity operates on FeatureValue/FeatureField types (CBR-specific); the DTW algorithm may need adaptation for raw PAD time series, or a general-purpose DTW extracted from the existing implementation.
**Trade-offs:** DTW gives temporal similarity and alignment but not correlation direction (positive/negative co-movement). Correlation direction can be derived from aligned segments via Spearman rank correlation if needed — a lightweight addition. DTW similarity scores are less immediately interpretable than Pearson correlation coefficients for domain experts unfamiliar with DTW. The existing DtwSimilarity is CBR-specific; using it requires either input format adaptation or algorithm extraction.
**Sources:** DtwSimilarity.java (existing 157-line tested implementation with warping constraints), AffectTrajectoryAnalyzer.java (regression precedent for simpler cases)
**Exploration:** quick
**Depends on:** D3 (domain signal model)
**Status:** revised (R1-15: DTW adopted for platform coherence; R1-16: Pearson + cross-correlation problems acknowledged, result semantics constrained to similarity/alignment)

## D5: Privacy enforcement model for cross-domain reasoning

**Choice:** Method signature enforcement — DomainActivation.correlate() takes exactly one PrincipalId. Cross-principal analysis is not expressible through the API.
**Alternatives:**
- Runtime validation — accept broader query, validate at runtime that all data belongs to same principal. More flexible but adds a failure mode the compiler can't catch.
**Rationale:** Cross-domain reasoning is self-reflection across your own life domains — never comparing your data with someone else's. Making cross-principal analysis unrepresentable in the API is stronger than checking at runtime. Matches PerspectivalResolver's existing pattern (single PrincipalId parameter).
**Trade-offs:** If a future use case needs cross-principal domain correlation (e.g., "compare Alice's work stress with Bob's work stress"), it would need a separate API. Acceptable: that's a different operation (social comparison, not cross-domain self-reflection).
**Sources:** PerspectivalResolver.java (single-principal pattern), issue #283 scope ("only crosses domains for the SAME principal")
**Exploration:** quick
**Depends on:** D1 (DomainActivation as CDI bean)
**Status:** captured

## D6: Principal-scoped memory queries for perspective-aware trajectories

**Choice:** When CognitiveProfileQuery specifies a perspective via asSeenBy(PrincipalId), all memory queries in CognitiveProfile use MemoryQuery.withCallerPrincipalId(principalId) to filter affect memories by the requesting agent. AffectEvents.toMemoryInput() callers must set the principalId (via MemoryInput.withPrincipalId()) when storing agent-specific affect assessments.
**Alternatives:**
- Keep memories agent-global — trajectory is shared ground truth across agents. Simpler but means the "trajectory bug" (all agents see the same trajectory regardless of perspective) is by design, not a bug. Inconsistent with the perspectival overlay model where PAD is always agent-specific.
- Store affect memories with per-agent Subject (e.g., Subject.of("agent-node", agentId + nodeId)) — distinguishes agent memories at the Subject level rather than the principalId field. More explicit but breaks existing Subject.of("node", nodeId) convention and query patterns.
**Rationale:** The memory infrastructure already supports principal-scoped storage (MemoryInput.principalId, MemoryInput.ownedBy()) and principal-scoped queries (MemoryQuery.withCallerPrincipalId()). AffectEvents.toMemoryInput() currently passes null for principalId — the mechanism exists but is unwired. The perspectival overlay model (from #253 D55/D63 design spec) established that "affect is always perspectival" — shared nodes carry no inherent PAD, each agent stores overlay PAD. Extending this principle to affect memories is architecturally consistent: if the node's PAD is agent-specific (via overlay), the trajectory computed from that node's affect memories should also be agent-specific. Without principal scoping, CognitiveProfile.computeTrajectory() returns the same trajectory for all agents regardless of asSeenBy() — contradicting the perspectival model.
**Trade-offs:** Requires affect memory producers to set principalId. Existing affect memories stored without principalId remain queryable by all agents (backward compatible — null principalId means "shared"). Memory store implementations must support withCallerPrincipalId filtering (verified: MemoryQuery already carries this field).
**Sources:** MemoryInput.java (principalId field, withPrincipalId(), ownedBy()), MemoryQuery.java (withCallerPrincipalId()), AffectEvents.java (toMemoryInput() passes null principalId), CognitiveProfile.java (queryMemories() and computeTrajectory() never use withCallerPrincipalId), 2026-09-01-perspectival-overlays-design.md ("Affect is Always Perspectival")
**Exploration:** surfaced by review (R1-04, R1-21)
**Depends on:** D1 (CognitiveProfile internalization provides the PrincipalId context)
**Status:** captured
