# Shadow Narrative Frame — Design Spec

**Issue:** casehubio/neocortex#1058
**Date:** 2026-11-19
**Status:** Draft

## Problem

BehavioralSynthesisPhase creates attractor nodes in the BEHAVIORAL subgraph — behavioral tendencies like "withdraw", "fight", "fawn", "trust". These nodes carry what the tendency is and how strong it is, but not the situational context in which they formed or what they mean in identity terms.

ShadowArchetypePromptSection renders "N personality traits have shifted from baseline" — a count with no detail. The full displaced personality state (`facetDisplacements`) is available on the snapshot but discarded.

The LLM currently receives the displaced facet values only via `LlmAppraisalStrategy` (in the appraisal prompt). The main cognitive prompt has no view of the modified personality state through the agent's archetype lens.

## Approach

Build the data plumbing. No static shadow taxonomy — the "shadow narrative frame" emerges when the LLM receives displaced personality state + archetype context + attractor pattern together.

Two deliverables:
1. **Attractor formation context** — BEHAVIORAL nodes capture the situational mode and facet displacement snapshot at formation time
2. **Enhanced prompt rendering** — `ShadowArchetypePromptSection` renders configurable, relevance-ranked displaced facets with archetype context

## 1. Attractor Formation Context

### Properties added to BEHAVIORAL attractor nodes

When `BehavioralSynthesisPhase.createOrStrengthenAttractor()` creates or updates a node, write additional properties:

| Property | Value | Source |
|----------|-------|--------|
| `situational-mode` | Active mode name (e.g., "STRESS") or null | `SituationalPersonalitySnapshot.affectiveWinner()` |
| `situational-social-mode` | Active social mode (e.g., "SOCIAL_COLLABORATIVE") or null | `SituationalPersonalitySnapshot.socialWinner()` |
| `situational-intensity` | Mode intensity [0, 1] | `SituationalPersonalitySnapshot.modeIntensities()` |
| `displaced-facets` | Comma-separated `facet:delta` pairs for top displaced facets | `SituationalPersonalitySnapshot.facetDisplacements()` |
| `archetype-family` | Primary archetype family (e.g., "creator") | MindMap PERSON node `archetype-1-family` property |

### Accessing the snapshot

`BehavioralSynthesisPhase` injects `Instance<SituationalPersonalityParticipant>` (graceful degradation when not on classpath). At synthesis time, calls `participant.currentSnapshot(agentId, tenantId)` to get the cached snapshot from the last tick.

If no snapshot is available (participant absent or no tick yet), the properties are simply not written. No failure — attractor creation proceeds without situational annotation.

### Accessing archetype family

Read `archetype-1-family` from the agent's PERSON node in the MindMap. The node is already resolved by `AssociationProcessor.resolveAcrossSubgraphs()` or found via the `agent-id` property. Cache per agent within a single consolidation run.

## 2. Enhanced Prompt Rendering

### ShadowArchetypePromptSection changes

Replace the current generic output:
```
3 personality traits have shifted from baseline.
```

With a relevance-ranked rendering:
```
Your personality has shifted under stress (intensity 72%):
  Anxiousness: elevated (+15%) — characteristic of this state
  Emotional Lability: elevated (+12%) — characteristic of this state
  Hostility: slightly elevated (+8%)
  Withdrawal: reduced (-10%) — against your usual pattern

You are a Creator. These shifts are your current felt reality.
```

### Relevance scoring

Each displaced facet is scored:

```
relevance = |displacement| × modeBoost × attractorBoost
```

- `modeBoost` = `modeRelevanceBoost` (config, default 1.5) if the facet appears in the active mode's `SituationalProfile` delta set, 1.0 otherwise
- `attractorBoost` = `attractorRelevanceBoost` (config, default 1.3) if the facet appears in the active attractor's correlation set, 1.0 otherwise

Facets are sorted by relevance descending. Only facets with `|displacement| >= minDisplacement` are included, capped at `maxFacets`.

### Attractor-facet correlation map

A static map from CAPS output node IDs to correlated AMPD facets, defined on the config:

```
withdraw → [withdrawal, anxiousness, intimacy-avoidance]
fight → [hostility, impulsivity, risk-taking]
flight → [anxiousness, withdrawal]
fawn → [attention-seeking]
freeze → [anxiousness, emotional-lability]
trust → [suspiciousness(-)]
distrust → [suspiciousness, intimacy-avoidance]
approach → [risk-taking, grandiosity]
assert → [hostility, grandiosity]
submit → [withdrawal, anxiousness]
```

The map is on the config record — tunable without code changes. Unmapped attractors get no boost (attractorBoost = 1.0).

### Rendering logic

1. Get snapshot from `SituationalPersonalityParticipant.currentSnapshot()`
2. If no snapshot or no active mode, fall back to current behavior (generic count)
3. Get archetype family from MindMap PERSON node (cached)
4. Score each displaced facet by relevance
5. Take top `maxFacets` above `minDisplacement`
6. Render with direction language ("elevated", "reduced", "slightly elevated")
7. Annotate mode-characteristic facets
8. Include archetype family name

### Config record

```java
public record ShadowFrameConfig(
    int maxFacets,                    // default: 5
    double minDisplacement,           // default: 0.05
    double modeRelevanceBoost,        // default: 1.5
    double attractorRelevanceBoost,   // default: 1.3
    Map<String, List<String>> attractorFacetCorrelations  // tunable map
) {}
```

Produced by `CognitionDefaultBeans` with `@DefaultBean`. Overridable via `application.properties` using `@ConfigMapping`.

## Data Flow

```
Tick pipeline:
  SituationalDetector → mode detection
  SituationalPersonalityParticipant → facet pull, caches snapshot
      ↓
Consolidation:
  BehavioralSynthesisPhase
    → reads snapshot (mode, displacements)
    → reads archetype-family from PERSON node
    → writes attractor node with situational properties
      ↓
Next tick prompt rendering:
  ShadowArchetypePromptSection
    → reads snapshot (mode, displacements)
    → reads archetype-family from PERSON node
    → relevance-ranks facets
    → renders to cognitive prompt
```

## Testing

1. **BehavioralSynthesisPhase** — test that attractor nodes carry `situational-mode`, `displaced-facets`, `archetype-family` when snapshot is available. Test graceful degradation when no snapshot.
2. **Relevance scoring** — unit test the scoring formula with known inputs. Verify mode-characteristic facets rank higher. Verify attractor-correlated facets rank higher.
3. **ShadowArchetypePromptSection** — test rendered output includes facet names, directions, magnitudes, archetype family. Test fallback to generic count when no snapshot.
4. **Config** — test that config parameters affect rendering (maxFacets, minDisplacement, boosts).

## Scope exclusions

- **Shadow label taxonomy** — explicitly excluded. No static mapping of (archetype, mode) → shadow name.
- **Narrative identity synthesis (#599)** — this is groundwork. The narrative interpretation emerges from LLM usage, not from this spec.
- **DispositionEvolutionPhase integration** — adjacent but separate. Disposition evolution operates on the weighted term vector, not attractors.

## References

- [mindmap-intelligence/.../consolidation/BehavioralSynthesisPhase.java] — attractor creation
- [cognition/.../situational/ShadowArchetypePromptSection.java] — current prompt renderer
- [cognition/.../situational/SituationalPersonalityParticipant.java] — snapshot provider
- [cognition/.../situational/SituationalDetector.java] — mode detection
- [cognition/.../situational/PersonalityStateIntegrator.java] — facet accumulation
- [caps-api/SettlingResult.java, CapsAttractor] — attractor types
- [memory-seeding/.../PersonalityProfileHandler.java] — writes archetype-N-family properties
- [GitHub #1058] — focal issue
- [GitHub #712] — shadow narrative concept origin
- [GitHub #599] — narrative identity (McAdams 2001, future work)
- [GitHub #941] — personality-aware situation classification
