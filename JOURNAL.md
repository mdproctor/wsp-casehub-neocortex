# Design Journal — issue-287-social-cognition

## 2026-09-11 — Design + Batch 1 implementation

### Design phase

Multi-agent debate (2 rounds) to decide the architecture for social cognition in cognitive-index.

Round 1 tested three pre-assigned positions (Unified Engine, Perspective Cross-Cutting, Focused Compositions) — converged on Focused Compositions but confirmed the trajectory-before-perspective bug. Round 2 used three independent architects with different optimization lenses (cognitive science fidelity, consumer API elegance, evolution resilience). The cognitive science architect surfaced the "perceiver-primary" insight — perspective is constitutive of entity resolution, not a post-processing step. The consumer API architect contributed batched compare() and optional asSeenBy(). The evolution architect's Signal-Producer SPI was rejected as speculative for zero callers.

Decisions captured: D1 (perceiver-primary architecture), D2 (PAD distance + slope vector similarity), D3 (subgraphId-scoped domain signals), D4 (DTW over Pearson — reviewer caught linearity/stationarity assumptions), D5 (privacy by method signature), D6 (principal-scoped memory queries — reviewer surfaced this).

Standard decision review (3 rounds, 34 issues, $13.60) revised D1-D4 substantively and added D6. Standard spec review (1 round before memory kill) cleaned up CbrStore injection, added loadAllOverlays() delegation pattern, added unassessedAgents field.

### Implementation — Batch 1 (Perspective Integration)

Three tasks completed:
1. CognitiveProfileQuery.withAsSeenBy() + EntityKnowledge.perceiver — backward compatible field additions
2. PerspectivalResolver internalized as package-private + loadAllOverlays() extracted
3. CognitiveProfile.resolve() perspective-aware — overlay before trajectory, principal-scoped memories, CbrStore cleanup

192 tests pass (189 existing + 3 new perspective tests).

### Remaining

Batch 2: CognitiveProfile.compare() + SocialComparison static utility (#271)
Batch 3: DomainActivation CDI bean with DTW correlation (#283)
