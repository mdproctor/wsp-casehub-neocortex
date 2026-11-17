# Unified Personality Evolution

**Issue:** casehubio/neocortex#1060
**Refs:** #712 (situational modulation), #1055 (EffectiveCognitiveDefaults)
**Date:** 2026-11-17

## Problem

`PersonalityEvolutionOrchestrator` has zero production callers. `tick()` and
`record()` exist but are never invoked — the class is inert. When `tick()`
does run (in tests), it writes to `DispositionProfileStore` (Eidos) but nothing
propagates the change to `EffectiveCognitiveDefaults` or `CognitiveDerivationEngine`.
Additionally, it operates only on Jungian function terms (JPAF stack) and never
reads PID-5 facets, while `SituationalPersonalityParticipant` (#712) handles
per-tick PID-5 displacement via a separate pipeline.

The root cause is architectural: Jungian function evolution and PID-5 facet
evolution are the same fundamental process — accumulated experiential pressure
on a personality dimension causes lasting change — but they were built at
different times with different infrastructure. The evolution process SPIs
(`DispositionSignalStore`, `DispositionHealth`, `DispositionEvolution`) live
in Eidos, while the signals that feed them and the consumer that needs the
result (`EffectiveCognitiveDefaults`) live in neocortex.

## Design

### Core principle

One signal model, one accumulator, one evaluation pipeline, one consolidation
phase. The personality dimension type (Jungian term vs PID-5 facet) determines
what changes and where the result propagates — not how signals accumulate or
how evolution is evaluated.

### Three-tier personality change model

```
Tier 1: Displacement (per-tick, transient)
  SituationalPersonalityParticipant → updateState(displacement)
  Existing, unchanged.

Tier 2: HomeOffset graduation (consolidation-cadence, lasting)
  PersonalityEvolutionPhase → updateState(homeOffset)
  Accumulated pressure → lasting facet shift. Reversible over time.

Tier 3: Baseline promotion (identity-level, rare)
  PersonalityEvolutionPhase → DispositionProfileStore + updateBase()
  When homeOffset drifts far enough, promote to Eidos baseline.
  For Jungian: JPAF stack weight reordering.
  For PID-5: baseline facet score update.
```

Tier 1 is `SituationalPersonalityParticipant` (#712), unchanged by this design.
This issue implements Tier 2 and Tier 3.

### New types

#### `PersonalityPressure` (cognition-api)

```java
public record PersonalityPressure(
    String dimension,       // "Ni", "Te", "ANXIOUSNESS", etc.
    double magnitude,       // signed: positive = reinforcing, negative = weakening
    String sourceType       // "relationship", "situational", "experience"
) {}
```

Dimension is a plain string — no enum. Jungian terms and PID-5 facet names
coexist in the same namespace. `sourceType` is for observability, not routing.

#### `PersonalityPressureSource<E>` (cognition-api)

Generalises the existing `TraitPressureSource<E>`:

```java
public interface PersonalityPressureSource<E> {
    Class<E> eventType();
    List<PersonalityPressure> translate(E event, DescriptorView descriptor);
}
```

Takes `DescriptorView` instead of `AgentDescriptor` — the neocortex-native
descriptor representation. This decouples pressure sources from Eidos types.

The existing `RelationshipPressureSource` is refactored to implement this SPI,
translating `RelationshipRecorded` CDI events into Jungian function pressures.
Its logic is preserved: positive relationship → reinforce dominant function,
negative → pressure auxiliary.

#### `PersonalitySignalAccumulator` (cognition-api SPI + impl in cognition)

```java
public interface PersonalitySignalAccumulator {
    void record(String tenantId, String agentId, PersonalityPressure pressure);
    void decay(String tenantId, String agentId, double factor);
    void clear(String tenantId, String agentId);
    Map<String, Double> accumulated(String tenantId, String agentId);
    Set<String> agentIds(String tenantId);
}
```

In-memory implementation: `ConcurrentHashMap<TenantAgentKey, ConcurrentHashMap<String, AtomicDouble>>`.
Signals decay on every consolidation tick. Lost on restart — acceptable because
personality evolution operates on weeks/months timescale and signals re-accumulate
quickly.

#### `PersonalityEvolutionConfig` (cognition-api)

Replaces the existing `PersonalityEvolutionConfig` with unified parameters:

```java
public record PersonalityEvolutionConfig(
    double decayFactor,              // per-consolidation signal decay (default 0.95)
    double jungianThreshold,         // signal magnitude for Jungian weight shift (default 0.3)
    double jungianShiftRate,         // weight adjustment per evolution event (default 0.05)
    double jungianReorderThreshold,  // weight difference for type transition (default 0.15)
    double facetThreshold,           // signal magnitude for PID-5 homeOffset shift (default 0.2)
    double facetShiftRate,           // homeOffset adjustment per evolution event (default 0.02)
    double baselinePromotionThreshold, // homeOffset magnitude to promote to Eidos (default 0.3)
    double l2Ceiling,                // max total drift before halt (default 0.15)
    double dampeningFactor           // signal dampening on halt (default 0.5)
) {}
```

### PersonalityEvolutionPhase (consolidation phase)

`@ApplicationScoped @Priority(50)` in `mindmap-intelligence` consolidation
package. Runs after behavioral synthesis (19), experience consolidation (15),
and sub-thought consolidation (16) — all of which produce data that feeds
personality evolution.

#### `run(tenantId, subgraphPriority)`

```
for each agentId in effectiveDefaults.agentIds(tenantId):
    1. Load DescriptorView from DescriptorViewSource
    2. Decay accumulated signals for this agent
    3. Read accumulated pressures per dimension

    // Jungian evaluation
    4. For each Jungian dimension (from DescriptorView.dispositionProfile):
       - If |accumulated| > jungianThreshold:
         - Compute weight shift = sign(accumulated) * jungianShiftRate
         - Apply to function weight
         - If weight reordering occurs:
           - Record type transition in CBR
           - Build new DescriptorView → effectiveDefaults.updateBase()
           - Write to DispositionProfileStore (Eidos identity)
         - Else:
           - Build new DescriptorView → effectiveDefaults.updateBase()
       - Clear signals for evolved dimensions

    // PID-5 evaluation
    5. For each PID-5 dimension (from DescriptorView.personalityFacets):
       - If |accumulated| > facetThreshold:
         - Compute homeOffset shift = sign(accumulated) * facetShiftRate
         - If new total homeOffset > baselinePromotionThreshold:
           - Promote to Eidos baseline (facet score update)
           - Reset homeOffset to 0
           - Build new DescriptorView → effectiveDefaults.updateBase()
         - Else:
           - effectiveDefaults.updateState() with new homeOffset
       - Clear signals for evolved dimensions

    // Safety: drift ceiling
    6. Compute total drift magnitude across all dimensions
       - If > l2Ceiling * relationalComplexity:
         - Halt: dampen all signals, skip further evolution
         - Emit attention signal (PERSONALITY_HALT)
```

#### Safety mechanisms (preserved from PEO)

- **Halt flag**: per-agent flag, set when total drift exceeds L2 ceiling.
  Clears on next consolidation tick if drift is below ceiling.
- **L2 ceiling**: maximum total personality drift, scaled by agent's
  `relationalComplexity` from `EffectiveCognitiveDefaults.restingFor()`.
  Higher relational complexity tolerates more drift (Cattell 1971, Halford 1998).
- **Dampening**: when halted, signals are decayed by `dampeningFactor`
  instead of evaluated. Prevents runaway evolution.
- **Reentrant lock**: per-agent lock prevents concurrent evaluation.

### Signal recording (CDI observers)

#### `PersonalityPressureRecorder` (cognition module)

`@ApplicationScoped` bean that observes CDI events and records pressure
signals into `PersonalitySignalAccumulator`:

```java
@Observes RelationshipRecorded event →
    Load DescriptorView for agent
    For each PersonalityPressureSource matching RelationshipEvent:
        Record PersonalityPressure into accumulator

@Observes ExperienceRecorded event →
    Load DescriptorView for agent
    For each PersonalityPressureSource matching ExperienceEvent:
        Record PersonalityPressure into accumulator
```

Pressure sources are CDI-discovered via `Instance<PersonalityPressureSource<?>>`.

#### PID-5 pressure from displacement

PID-5 signals are computed during the consolidation phase itself, not from
CDI events. The phase reads the current `PersonalityState` from
`SituationalStateService` and computes pressure from the displacement pattern:

```
For each facet with active displacement:
    pressure = displacement * consistency_factor
    consistency_factor = 1.0 if same direction as last N windows, else decayed

    Record PersonalityPressure(facet, pressure, "situational")
```

This means PID-5 pressure is derived from the existing situational modulation
data — no new signal infrastructure needed. The consistency factor ensures
oscillating displacement cancels out, while persistent directional displacement
accumulates.

### Propagation paths

| Evolution type | Propagation | Method |
|---|---|---|
| Jungian weight shift (no reorder) | Update derived defaults | `updateBase(tenantId, newView, eventRef)` |
| Jungian type transition (reorder) | Update derived defaults + Eidos identity | `updateBase()` + `DispositionProfileStore.update()` + CBR case |
| PID-5 homeOffset shift | Update personality state | `updateState(tenantId, agentId, snapshot, eventRef)` |
| PID-5 baseline promotion | Update Eidos identity + reset homeOffset | `DispositionProfileStore.updateFacets()` + `updateBase()` |

`DispositionProfileStore.updateFacets()` may need to be added to the Eidos
API for PID-5 baseline promotion. If Eidos doesn't support per-facet updates,
the full descriptor update path (`updateBase()`) suffices for the initial
implementation.

### Module placement

| Type | Module | Rationale |
|---|---|---|
| `PersonalityPressure` | cognition-api | Public type, used by pressure sources |
| `PersonalityPressureSource<E>` | cognition-api | Public SPI, CDI-discovered |
| `PersonalitySignalAccumulator` | cognition-api (SPI) | Public interface |
| `InMemoryPersonalitySignalAccumulator` | cognition | Default implementation |
| `PersonalityEvolutionConfig` | cognition-api | Replaces existing config |
| `PersonalityEvolutionPhase` | mindmap-intelligence | Consolidation phase |
| `PersonalityPressureRecorder` | cognition | CDI observer |
| `RelationshipPersonalityPressureSource` | cognition | Refactored from `RelationshipPressureSource` |

### Deprecations

The following Eidos SPIs are no longer called by any neocortex code after
this change. They should be deprecated in a follow-up Eidos issue:

- `DispositionSignalStore` → replaced by `PersonalitySignalAccumulator`
- `DispositionHealth` → evaluation logic inlined in `PersonalityEvolutionPhase`
- `DispositionEvolution` → evaluation logic inlined in `PersonalityEvolutionPhase`
- `SignalValence` → replaced by signed `magnitude` in `PersonalityPressure`

`DispositionProfileStore` remains — it is the Eidos identity store for
baseline writes.

The existing `PersonalityEvolutionOrchestrator` class is removed. Its logic
is split between:
- `PersonalityEvolutionPhase` (tick/evaluation logic)
- `RelationshipPersonalityPressureSource` (signal translation)
- `PersonalityPressureRecorder` (CDI event observation)

The existing `TraitPressureSource<E>` SPI in cognition-api is deprecated
in favour of `PersonalityPressureSource<E>`.

### Existing types renamed/refactored

| Old | New | Change |
|---|---|---|
| `TraitPressureSource<E>` | `PersonalityPressureSource<E>` | Generalised: takes DescriptorView, returns PersonalityPressure |
| `TraitActivation` | removed | Replaced by `PersonalityPressure` |
| `RelationshipPressureSource` | `RelationshipPersonalityPressureSource` | Implements new SPI |
| `PersonalityEvolutionConfig` | `PersonalityEvolutionConfig` | Extended with PID-5 and unified fields |
| `EvolutionTick` | `EvolutionResult` | Return type of phase evaluation, not tied to tick concept |

### Testing strategy

1. **Unit tests for PersonalitySignalAccumulator**: record, decay, clear,
   concurrent access, multi-dimension isolation
2. **Unit tests for PersonalityEvolutionPhase**: Jungian threshold crossing,
   PID-5 threshold crossing, type transition detection, halt/dampening,
   L2 ceiling scaling, displacement consistency factor
3. **Unit tests for PersonalityPressureRecorder**: CDI event translation,
   pressure source dispatch
4. **Integration test**: full pipeline — record events → accumulate →
   consolidation tick → verify EffectiveCognitiveDefaults reflects evolution
5. **Existing PEO test behavioural parity**: ensure the new phase matches
   the existing `PersonalityEvolutionOrchestratorTest` scenarios (stable,
   drifting, evolved, dampened, halted)

### Attention signals

The phase emits `AttentionSignal` for significant events:

| Event | Category | Significance |
|---|---|---|
| Jungian type transition | `PERSONALITY_EVOLVED` (new) | 1.0 |
| PID-5 baseline promotion | `PERSONALITY_EVOLVED` | 0.8 |
| PID-5 homeOffset shift | `PERSONALITY_EVOLVED` | 0.3 |
| Drift halt triggered | `PERSONALITY_HALT` (new) | 0.9 |

Two new `SignalCategory` values: `PERSONALITY_EVOLVED` and `PERSONALITY_HALT`.

## References

- `PersonalityEvolutionOrchestrator.java` — existing evolution logic
- `PersonalityEvolutionOrchestratorTest.java` — behavioral specification
- `SituationalPersonalityParticipant.java` — existing displacement pipeline
- `EffectiveCognitiveDefaults.java` — propagation target
- `PersonalityStateSnapshot.java` — homeOffset/displacement data model
- `ConsolidationScheduler.java` — consolidation phase lifecycle
- `BehavioralSynthesisPhase.java` — precedent for personality-aware consolidation
- `RelationshipPressureSource.java` — existing Jungian signal translation
- casehubio/neocortex#712 — situational personality modulation
- casehubio/neocortex#1055 — EffectiveCognitiveDefaults (landed)
