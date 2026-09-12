# Position B: Perspective as Cross-Cutting Concern

Define a Perspective sealed interface (None, Agent, Comparative). Make every cognitive query type perspective-aware.

## The Core Claim

Perspective is not a feature to be bolted onto entity resolution. It is a dimension of every cognitive query, and the re-architecture must treat it that way.

The codebase proves this. Today, PerspectivalResolver accepts a PrincipalId for perspectival overlay resolution. TemporalQuery accepts a PrincipalId for access control filtering. CognitiveProfileQuery accepts neither. Three types in the same module use agent identity in incompatible ways — or ignore it entirely. The result: there is no path from "resolve an entity" to "resolve an entity as Alice sees it" without manual orchestration outside the module. EntityKnowledge always returns the shared node, never a perspectivally-merged view.

This is not a missing feature. It is a missing dimension.

## What the Re-Architecture Should Do

Define a Perspective sealed interface with three variants: None, Agent(PrincipalId), and Comparative(Set<PrincipalId>). Make every cognitive query type accept an optional Perspective. Push PerspectivalResolver and PerspectivalMerge down to internal implementation details.

Concretely:

- CognitiveProfileQuery.withPerspective(Agent(alice)) → EntityKnowledge from Alice's view
- TemporalQuery.withPerspective(Agent(alice)) → timeline with Alice's emotional coloring
- CognitiveProfileQuery.withPerspective(Comparative(alice, bob)) → EntityKnowledge with divergence metrics

Each query type interprets Perspective according to its own semantics. The sealed interface guarantees exhaustive handling.

## Why This Beats the Alternatives

**Against Position A (Unified Engine):** The existing types are well-factored. Their responsibility boundaries are correct. What is wrong is that they lack a shared vocabulary for perspective. Adding Perspective to their query types is a surgical fix. Replacing them with a unified engine throws away good factoring to solve a vocabulary problem.

**Against Position C (Focused Compositions):** Position C adds perspective only to CognitiveProfile, creating asymmetry. CognitiveProfile becomes perspective-aware while TemporalIndex stays blind. When #283 needs subgraph-scoped correlations from a specific agent's viewpoint, we face the same problem again — but now with a precedent that perspective lives only in entity resolution.

## Honest Weaknesses

**Wider blast radius.** Every query type needs modification. This is worth it because the alternative is repeated local fixes that each re-invent how perspective applies.

**Premature abstraction risk.** The Comparative variant exists to serve #271, but the variants map directly to real query patterns that already exist — None (today), Agent (PerspectivalResolver), Comparative (#271). Not speculative categories.

## The Principle

When a dimension cuts across every operation in a module, model it as a first-class concept in every operation. Perspective is not entity resolution's problem. It is the cognitive query tier's problem.
