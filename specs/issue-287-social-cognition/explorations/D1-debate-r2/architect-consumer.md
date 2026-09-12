# Proposal 2: CognitiveQuery — Consumer-First (Consumer API Lens)

## Core Change

Single entry-point CDI bean `CognitiveQuery` REPLACES CognitiveProfile + PerspectivalResolver. Both existing classes deleted.

Three methods:
- `resolve(CognitiveProfileQuery)` → EntityKnowledge (with optional asSeenBy perspective)
- `compare(CognitiveProfileQuery, PrincipalId... agents)` → PerspectivalComparison
- `correlate(CrossDomainQuery)` → CrossDomainInsight

## Query Types

**CognitiveProfileQuery.asSeenBy(PrincipalId)** — perspective as optional query parameter. Trajectory computed after perspective applied. Bug fixed by construction.

**CrossDomainQuery** (new) — subgraphTypes, tenantId, principal (required), time window, limit.

## Result Types

**EntityKnowledge** stays unchanged. When resolved with asSeenBy, the node field contains the merged perspectival node.

**PerspectivalComparison** (new) — sharedNode + Map<PrincipalId, EntityKnowledge> + PadDivergence. forAgent(PrincipalId) accessor.

**PadDivergence** (new) — per-dimension deltas, trendDisagreement flag, per-agent trajectories.

**CrossDomainInsight** (new) — Pearson coefficient, supporting signals, sample count.

## What Moves, What Stays

- **Deleted:** CognitiveProfile, PerspectivalResolver
- **Package-private:** PerspectivalMerge, AffectTrajectoryAnalyzer
- **Unchanged:** TemporalIndex, TemporalFocus, CognitiveDefaults, all configuration types

## Key Argument

Work backwards from ideal call sites. One import, one inject, one call for any cognitive query. If callers need 5 lines of boilerplate, the API failed.
