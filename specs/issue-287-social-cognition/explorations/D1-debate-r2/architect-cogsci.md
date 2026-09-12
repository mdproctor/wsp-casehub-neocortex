# Proposal 1: Perceiver-Primary Cognitive Index (Cognitive Science Lens)

## Core Change

CognitiveProfile becomes perceiver-primary. PrincipalId perceiver is conceptually required — the "view from nowhere" (null perceiver) is the degenerate case, not the default. Cognition is always situated; perception without a perceiver is the architectural disease that produced the trajectory bug.

**PerspectivalResolver** internalized as package-private helper. Callers never manually manage overlay resolution.

## New Types

**SocialComparison** — static utility (not CDI bean). Takes N already-resolved EntityKnowledge records (one per agent), computes relational properties: PAD distance matrix, consensus metrics, divergence signals, trajectory alignment. Caller does N CognitiveProfile.resolve() calls with different perceivers, passes results. Same design philosophy as AffectTrajectoryAnalyzer — pure computation over already-resolved data.

**DomainActivation** — CDI bean. Takes principal + subgraph IDs + time window. Queries domain-scoped affect memories, computes lead-lag relationships (spreading activation model). Privacy enforced by method signature (single PrincipalId required).

**EntityKnowledge** gains `PrincipalId perceiver` field.

## What Stays, What Moves

- **Unchanged:** AffectTrajectoryAnalyzer, PerspectivalMerge, TemporalIndex, TemporalFocus, CognitiveDefaults
- **Internalized:** PerspectivalResolver → package-private helper
- **New:** SocialComparison (static), PerspectivalComparison (record), DomainActivation (CDI), DomainActivationPattern (record)

## Key Argument

The software should mirror cognitive structure. Perceivers are primary because cognition is always situated. Comparison is derived computation because social comparison operates over already-formed perspectives. Domain activation is a query because cross-domain reasoning requires store access.
