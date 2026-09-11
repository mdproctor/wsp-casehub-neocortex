# Mediator Synthesis — Architecture Debate Round 2

## Verdict: Proposal 1 (Perceiver-Primary) Wins — Hybrid with Proposal 2

Proposal 1's architectural diagnosis is correct: perspective is part of entity resolution, not a post-processing step. The trajectory bug is a structural defect caused by separating these concerns into two disconnected CDI beans. Internalizing PerspectivalResolver fixes this structurally.

Proposal 2 contributes two essential corrections. Proposal 3 is rejected.

## Why Proposal 1 Wins

The trajectory bug is not a wiring oversight — it's an architectural disease. CognitiveProfile resolves entity knowledge. PerspectivalResolver merges overlays. They are two CDI beans that do not call each other. The result: trajectory is always computed on the raw shared node. Proposal 1 correctly identifies this: perspective is constitutive of entity resolution, not something you apply after. Internalizing PerspectivalResolver as package-private means the overlay merge happens before trajectory computation because the code physically cannot skip it.

## Why Proposal 3 Loses

SignalProducer SPI proposes CDI-discovered producers with topological ordering, sealed interface hierarchies, and open-ended signal maps — for a module with zero production callers and two concrete features. This codebase's every surviving SPI follows the same pattern: start concrete, extract the interface when a second real implementation forces it. SignalProducer has zero concrete implementations that justify it. The proposed future features (emotional contagion, coalition detection) have no issues, no specs, no callers. CognitiveView replacing EntityKnowledge with Map<Class<Signal>, List<Signal>> is strictly worse — EntityKnowledge's typed fields are IDE-discoverable; a type-erased map requires callers to know signal class names.

**Saved from Proposal 3:** ResolvedContext as a package-private intermediate — separating "perspective-applied data" from "computation over that data." Good internal abstraction, but package-private, not public.

## What Proposal 2 Corrects in Proposal 1

**1. asSeenBy() must be optional, not conceptually required.** Batch operations, admin views, data exports, and test fixtures all genuinely need the unperspectived entity. The shared view is a real use case, not a degenerate case.

**2. compare() must be a single batched call.** PerspectivalResolver.loadOverlays() queries all overlay nodes for a tenant and filters in memory. Doing N separate resolve() calls for N agents means N redundant full scans. A single compare() method loads overlays once and resolves N perspectives against them — batch the expensive I/O, fan out only the cheap computation.

## Why Proposal 2 Partially Loses

Deleting CognitiveProfile to create CognitiveQuery is a rename with collateral damage. CognitiveProfile is 162 lines and structurally sound — it just needs perspective integration. "Fewer imports" is not "better architecture."

## Final Architecture

- **CognitiveProfileQuery** gains `withAsSeenBy(PrincipalId)` — optional, nullable, existing withX() pattern
- **EntityKnowledge** gains `PrincipalId perceiver` — nullable (null = shared/unperspectived view)
- **CognitiveProfile** internalizes PerspectivalResolver (package-private), gains `compare(query, Set<PrincipalId> agents)` → `Map<PrincipalId, EntityKnowledge>`. One node resolution, one overlay scan, N lightweight merge-and-analyze passes.
- **PerspectivalResolver** becomes package-private helper class (not deleted — overlay-loading logic is correct)
- **SocialComparison** — new static utility. Takes Map<PrincipalId, EntityKnowledge>, computes PAD distance matrix, consensus, divergence, trajectory alignment. Pure computation. Same pattern as AffectTrajectoryAnalyzer.
- **DomainActivation** — new CDI bean. Principal + subgraph IDs + time window → lead-lag correlations. Privacy by method signature.
- **PerspectivalMerge** stays public static utility (used by tests and internal code)
- **AffectTrajectoryAnalyzer** unchanged
- **TemporalIndex, TemporalFocus, CognitiveDefaults** unchanged

## What Gets Rejected

SignalProducer SPI, CognitiveView, @DependsOn topological ordering, sealed CognitiveSignal hierarchy, CognitiveQuery as replacement class name. All solve problems that do not yet exist. When emotional contagion actually arrives with an issue number and a caller, extract the SPI from concrete code at that point.
