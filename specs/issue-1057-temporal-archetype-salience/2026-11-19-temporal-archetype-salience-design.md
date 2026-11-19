# Temporal Archetype Salience Across Life Phases — Design Spec

**Issue:** casehubio/neocortex#1057
**Date:** 2026-11-19
**Status:** Draft

## Problem

The archetype model currently assigns static ranked archetypes to an agent (1st=Creator, 2nd=Sage) that remain constant for the agent's lifetime. In reality, archetype salience shifts across developmental phases — a person may strongly identify as an Explorer in adolescence but shift toward Sage in adulthood. The biographical evidence for this already exists: `FormativeExperience` events carry `developmental-period` values (childhood, adolescence, early-adulthood, adulthood), and the archetype extraction pipeline identifies ranked archetypes with evidence text.

What's missing: (a) extracting per-phase archetype salience weights from biographical evidence, (b) determining the agent's current life phase at runtime, and (c) using phase-indexed salience to modulate how strongly each archetype's situational profiles affect the agent's personality.

## Approach

Three layers, each small and independently testable:

1. **Extraction** — extend `PersonalityProfileEntry.ArchetypeSelection` with per-phase salience weights, extracted alongside existing archetype data
2. **Phase resolution** — compute current developmental phase from `lifecycle.born` on the PERSON MindMap node
3. **Runtime modulation** — scale situational profile composite deltas by the current-phase archetype salience weight

## 1. Extraction — Phase-Indexed Archetype Salience

### Data model

Add a `PhaseSalience` record to `PersonalityProfileEntry`:

```java
public record PhaseSalience(
    String phase,       // "childhood", "adolescence", "early-adulthood", "adulthood"
    Double salience,    // [0, 1] — how dominant this archetype was in this phase
    String evidence     // biographical text supporting this assessment
) {}
```

Add `List<PhaseSalience> phaseSalience` to `ArchetypeSelection`. The extraction prompt asks: "For each identified archetype, estimate its salience (0-1) in each developmental period present in the biography, with evidence."

### Storage

`PersonalityProfileHandler.writeArchetypes()` writes additional properties on the PERSON node:

```
archetype-1-salience-childhood=0.80
archetype-1-salience-adolescence=0.75
archetype-1-salience-early-adulthood=0.60
archetype-1-salience-adulthood=0.40
archetype-2-salience-childhood=0.15
archetype-2-salience-adolescence=0.20
archetype-2-salience-early-adulthood=0.35
archetype-2-salience-adulthood=0.55
```

Up to 12 properties for 3 ranked archetypes × 4 phases. Same pattern as existing archetype properties (`archetype-1-family`, `archetype-1-adjectives`). Written once at import, read-only at runtime.

### Defaults

When no phase salience data is extracted (agent has no biographical evidence for a phase), no property is written. The runtime defaults to 1.0 — no modulation. This preserves backward compatibility: agents without phase salience data behave identically to today.

## 2. Phase Resolution — DevelopmentalPhaseResolver

### Location

A pure static utility in `mindmap-api` (zero deps beyond `LifecycleDate`):

```java
public final class DevelopmentalPhaseResolver {
    public static String resolvePhase(LifecycleDate born, Instant now)
    public static String resolvePhase(MindMapNode personNode, Instant now)
}
```

### Phase boundaries

Matching `FormativeTimestampGenerator` conventions:

| Phase | Age range |
|-------|-----------|
| `childhood` | 0–12 |
| `adolescence` | 13–17 |
| `early-adulthood` | 18–25 |
| `adulthood` | 26+ |

When `born` is null or absent, returns `"adulthood"` (the default for agents without biographical birth data).

### Implementation

Reads `lifecycle.born` from the PERSON node's properties via `LifecycleEvents.extract()`. Computes age in years from `born.toStartInstant()` to `now`. Maps to phase via threshold comparison.

## 3. Runtime Modulation — Phase-Weighted Profile Intensity

### Modulation point

In `SituationalPersonalityParticipant.computeCompositeDelta()`, the existing formula:

```
composite[facet] += delta[facet] * intensity
```

Becomes:

```
composite[facet] += delta[facet] * intensity * phaseSalience
```

Where `phaseSalience` is the archetype salience weight for the current phase, looked up from the PERSON node. If no phase salience data exists for this archetype/phase combination, `phaseSalience = 1.0`.

### Reading phase salience at tick time

`SituationalPersonalityParticipant` needs:
1. The agent's current phase (from `DevelopmentalPhaseResolver`)
2. The phase salience weights for each archetype family (from PERSON node properties)

Both are stable values that change rarely (phase changes once per life stage; salience weights change only on re-import). Cache them per-agent alongside the existing `lastResults` cache, refreshed when the agent's PERSON node changes.

### Integration with SituationalDeltaConverter

Currently, `SituationalDeltaConverter.toSituationalDeltas()` converts `List<SituationalProfile>` from eidos into `Map<SituationalMode, Map<String, Double>>`. Each profile comes from a specific archetype family (via `SituationalProfileDeriver`).

The modulation applies at the point where these deltas are consumed by `computeCompositeDelta()`. Each `SituationalProfile` has a provenance string (e.g., `"family-default:CREATOR"` or `"biographical"`). The phase salience lookup uses the family name from the provenance to find the right weight.

For per-character biographical profiles (provenance `"biographical"`), which are already specific to the agent, the salience weight comes from the primary archetype (rank 1). These profiles represent the agent's personally-extracted situational responses, which are still modulated by how salient that identity is in the current phase.

### Data flow

```
Biography import:
  PersonalityProfileHandler
    → reads ArchetypeSelection.phaseSalience
    → writes archetype-{rank}-salience-{phase} to PERSON node

Tick pipeline:
  SituationalPersonalityParticipant.tick()
    → DevelopmentalPhaseResolver.resolvePhase(personNode, now)
    → reads archetype-{rank}-salience-{currentPhase} from PERSON node
    → computeCompositeDelta() scales delta by phaseSalience
    → modulated facet displacements flow to downstream consumers
```

## Testing

1. **DevelopmentalPhaseResolver** — unit tests for each phase boundary, null/missing born date, partial dates (year-only), qualifier handling.
2. **PersonalityProfileHandler** — test that phase salience properties are written from `ArchetypeSelection.phaseSalience`.
3. **SituationalPersonalityParticipant** — test that `computeCompositeDelta` scales by phase salience when available. Test default 1.0 when no data. Test that different phases produce different scaling.
4. **Integration** — end-to-end test: import biography with phase salience → tick with known phase → verify reduced modulation.

## Scope exclusions

- **Phase-specific sub-archetype selection** — which sub-archetype (e.g., Warrior vs. Rescuer within Hero) is active per phase. Future work.
- **Dynamic phase transitions** — detecting when an agent crosses a phase boundary during a session. The phase is computed from the born date; boundary crossing happens on a years timescale.
- **Narrative time** — agents whose narrative clock differs from wall clock. Future work (requires a narrative-time subsystem).
- **Cross-archetype facet blending** — weighted average of multiple families' profiles. D2 decision: reweight, not blend.

## References

- [PersonalityProfileEntry.java:105-114] — existing ArchetypeSelection record
- [PersonalityProfileHandler.java:111-123] — existing archetype property writing
- [SituationalPersonalityParticipant.java:187-203] — computeCompositeDelta formula
- [SituationalDeltaConverter.java] — profile-to-delta conversion
- [SituationalProfileDeriver.java] — archetype-to-profile derivation with provenance
- [FormativeTimestampGenerator.java:29-49] — phase boundary conventions
- [LifecycleDate.java] — EDTF partial date value type
- [LifecycleEvents.java] — lifecycle property conventions
- [DevelopmentalPhaseResolver] — new, proposed in this spec
- [GitHub #1057] — focal issue
- [GitHub #712] — temporal drift concept origin
- [GitHub #1058] — shadow narrative frame (sibling)
