# Position C: Focused Compositions

One field addition to CognitiveProfileQuery. Two new CDI beans. Zero migration.

## The Thesis

cognitive-index does not need re-architecture. It needs two new types and one field addition. The existing pattern of small, focused, independently testable types has produced a module where the largest class is 162 lines and 187 tests cover 20 test classes. That pattern should be extended, not replaced.

## The Precedent Is Already in the Code

CognitiveProfile.java line 160: `return AffectTrajectoryAnalyzer.analyze(affectMemories)`. CognitiveProfile already composes AffectTrajectoryAnalyzer internally. The caller asks for an entity's knowledge; trajectory computation happens as a private implementation detail.

The "disconnection" between CognitiveProfile and PerspectivalResolver is not a design flaw — it is an incomplete composition. CognitiveProfile composes AffectTrajectoryAnalyzer for trajectory but does not compose PerspectivalResolver for perspective. The fix is one optional field on CognitiveProfileQuery:

```java
PrincipalId perspective  // nullable, new
```

When perspective is non-null, CognitiveProfile applies PerspectivalResolver to the resolved node before building EntityKnowledge. Roughly 8 lines of code, zero new abstractions, zero changes to the external API contract.

## Two New Types for Two New Capabilities

**AffectComparator** for #271: Takes entity + N principals + tenant. Batch-loads overlays for all N agents, applies PerspectivalMerge per agent, computes per-agent trajectories, returns comparison with divergence metrics. Estimated 80-120 lines. Internally composes PerspectivalResolver + AffectTrajectoryAnalyzer.

**CrossDomainAnalyzer** for #283: Takes principal + subgraph IDs + time window. Queries affect memories scoped by subgraph membership, computes per-subgraph AffectTrajectory, runs temporal correlation. Estimated 100-150 lines. Privacy enforcement is intrinsic: query parameterized by principal, scoping enforced at store layers.

Both follow the established convention: @ApplicationScoped, Instance<T> graceful degradation, query-record + result-record.

## Why Not the Unified Engine (Position A)

Position A replaces three working, tested types totaling 310 lines with a monolith estimated at 500+ lines. It trades three small things for one big thing. In a codebase with 30+ modules and a proven track record of small focused types, that is a regression in design quality.

## Why Not Perspective Cross-Cutting (Position B)

Where is the evidence that anyone needs a perspectival timeline? TemporalIndex aggregates chronological entries from three stores. Making it perspective-aware is speculative engineering with real costs: API surface expansion on a stable type, new test matrix, wider blast radius. If perspectival timelines become a real requirement, adding PrincipalId to TemporalQuery later is a backward-compatible change. The cost of deferral is near zero.

## Addressing Weaknesses

**Fragmentation risk** is real but not yet present. The trigger to re-evaluate: when AffectComparator and CrossDomainAnalyzer start duplicating store-resolution boilerplate. If that happens, extract a shared helper. The codebase demonstrates this reflex: fusion-api was extracted from rag-api when fusion became cross-cutting.

## The Bottom Line

Three changes. One optional field. Two new beans. Zero migration. Zero rework of tested code. 187 existing tests pass unmodified. The module stays under 400 total lines of new code. That is the right amount of change for the requirements we actually have.
