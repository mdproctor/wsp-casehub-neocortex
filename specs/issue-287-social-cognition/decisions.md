# Decisions — issue-287-social-cognition

## D1: Architecture approach for social cognition in cognitive-index

**Choice:** Perceiver-primary re-architecture — CognitiveProfile internalizes PerspectivalResolver, gains batched compare(), perspective applied before trajectory computation. Two new focused types (SocialComparison static utility, DomainActivation CDI bean).
**Alternatives:**
- Unified Query Engine — single CognitiveQueryEngine replacing all types. Rejected: trades three small tested types for one ~500-line orchestrator in a codebase where the largest class is 162 lines.
- Perspective as cross-cutting concern — Perspective sealed interface on every cognitive query type. Rejected: no evidence TemporalIndex needs perspective; speculative blast radius.
- Signal-Producer SPI — CDI-discovered producers with topological ordering. Rejected: speculative extensibility for zero production callers; type-erased signal map worse than typed fields.
- Focused Compositions (original Position C) — just add perspective field + two new beans. Superseded: missed the perceiver-primary insight, didn't batch compare(), kept PerspectivalResolver as public API.
**Rationale:** Perspective is constitutive of entity resolution, not a post-processing step. The trajectory bug (computing trajectory on raw shared node before overlay) is a structural defect, not a wiring oversight. Internalizing PerspectivalResolver fixes this by construction. Batched compare() avoids N redundant overlay scans. asSeenBy() is optional because admin views, exports, and tests genuinely need the shared view. Static utility for comparison follows AffectTrajectoryAnalyzer precedent — pure computation over already-resolved data.
**Trade-offs:** PerspectivalResolver becomes package-private — callers who want raw overlay control lose direct access (mitigated: PerspectivalMerge stays public for edge cases). No extensibility framework for future social cognition features (mitigated: extract SPI when concrete implementations justify it, same as fusion-api extraction from rag-api).
**Sources:** PerspectivalResolver.java, CognitiveProfile.java (trajectory bug at line 160), AffectTrajectoryAnalyzer.java, Epley/Keysar perspective-taking research (cognitive science architect), existing codebase SPI extraction precedent (fusion-api from rag-api)
**Exploration:** multi-agent-debate (2 rounds — round 1: 3 assigned positions + mediator; round 2: 3 independent architects with different lenses + mediator)
**Status:** captured

## D2: SocialComparison result model

**Choice:** Three focused metrics — PAD distance matrix (pairwise Euclidean in PAD space), per-dimension consensus (variance across agents per PAD dimension), trajectory alignment (TrendDirection agreement/divergence). No outlier detection or aggregate scores — callers derive those from raw per-agent data.
**Alternatives:**
- Full divergence record with outlier detection, aggregate divergence score, distance matrices beyond pairwise — over-specified for zero callers, callers can derive from raw data
- Single aggregate "divergence score" — loses the per-dimension signal that makes the result actionable
**Rationale:** Maps to real social cognition questions: "how far apart?" (distance), "do they agree?" (consensus), "are they trending together?" (alignment). Reuses existing TrendDirection from AffectTrajectory. Lean result — no redundant aggregations.
**Trade-offs:** Callers who want outlier detection or aggregate scores compute them from the raw Map<PrincipalId, EntityKnowledge>. Acceptable because the raw data is always available alongside the comparison.
**Sources:** AffectTrajectory.java (TrendDirection reuse), AffectTrajectoryAnalyzer.java (static utility pattern)
**Exploration:** quick
**Depends on:** D1 (SocialComparison as static utility)
**Status:** captured

## D3: Domain signal model for cross-domain reasoning

**Choice:** Domain signal = aggregate affect trajectories for all entities within a subgraph. Flow: query MindMapStore for subgraph member entities → query CaseMemoryStore for affect memories in time window → aggregate into per-domain time series.
**Alternatives:**
- Domain-scoped mood memories — requires changes to the mood capture pipeline to tag mood with context. More accurate but out of scope for #287.
- Experience event correlation — correlate outcomes across domains instead of affect. Complementary signal but less directly emotional.
**Rationale:** Works with existing data, no pipeline changes. Entity-level affect trajectories scoped by subgraph membership IS the agent's "work emotional trajectory." Mood memories are agent-global and can't be domain-scoped without capture pipeline changes.
**Trade-offs:** Subgraphs with few entities or sparse affect data produce noisy signals. Mitigated by minimum sample count enforcement in the result.
**Sources:** SubgraphTypes.java, MindMapQuery.withSubgraphId(), AffectEvents.DOMAIN, CaseMemoryStore.query()
**Exploration:** quick
**Depends on:** D1 (DomainActivation as CDI bean)
**Status:** captured

## D4: Correlation algorithm for cross-domain reasoning

**Choice:** Pearson correlation for strength measurement + sliding-window cross-correlation for temporal lag detection. Result: per-domain trajectories + pairwise correlation coefficients + temporal lag estimates + sample counts.
**Alternatives:**
- DTW (Dynamic Time Warping) — already in codebase (DtwSimilarity in memory-api). Overkill for aggregated domain trajectories; designed for aligning arbitrary sequences.
- Granger causality — statistical test for predictive relationship ("does A help predict B?"). Most informative but computationally expensive and data-hungry. Future enhancement.
- Pearson only (no lag) — misses the directionally interesting insight ("work stress PRECEDES family tension by 48h").
**Rationale:** Pearson is simple, interpretable, well-understood. Cross-correlation detects temporal lag — the "spreading activation" insight from cognitive science. Both are O(n) on the aggregated time series. Sufficient for a first implementation with zero callers.
**Trade-offs:** Pearson assumes linear relationship — non-linear correlations will be missed. Cross-correlation assumes stationarity. Both acceptable for a first implementation; Granger causality can be added later as a refinement.
**Sources:** DtwSimilarity.java (existing DTW precedent — not used here), AffectTrajectoryAnalyzer.java (regression precedent)
**Exploration:** quick
**Depends on:** D3 (domain signal model)
**Status:** captured
