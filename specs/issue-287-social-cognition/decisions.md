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
