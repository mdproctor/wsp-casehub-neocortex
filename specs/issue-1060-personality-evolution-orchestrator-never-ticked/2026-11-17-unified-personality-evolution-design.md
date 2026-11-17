# Unified Personality Evolution

**Issue:** casehubio/neocortex#1060
**Refs:** #712 (situational modulation, Era 7b), #1055 (EffectiveCognitiveDefaults), #126 (JPAF orchestrator), #1080 (absorbed)
**Prerequisites:** casehubio/eidos#235, #1082, #1063 (see §Prerequisites)
**Follow-ups:** #1102, casehubio/agency#487, casehubio/eidos#237
**Date:** 2026-11-17 (rev 2, after the round-1 structure review)

## Problem

All of the following were verified in code.

1. **The JPAF pipeline is never run.** `PersonalityEvolutionOrchestrator.tick()` / `record()` have no production callers. Agency only produces the bean (`AgencyBeans:308`, `AgencyAutoConfiguration:287`).
2. **Identity writes are discarded.** On evolution, the orchestrator calls `DispositionProfileStore.update()`. The only implementation is `NoOpDispositionProfileStore`, and the SPI has no facet write.
3. **The base layer has exactly one owner, the Eidos descriptor.** `CognitionCore.tick()` calls `effectiveDefaults.updateBase(tenantId, toDescriptorView(descriptor), …)` on every tick (`CognitionCore.java:288-291`). `EidosDescriptorViewSource` reads the same `AgentRegistry`. A lasting change written anywhere other than the registry is reverted on the next tick.
4. **PID-5 lasting drift already exists and has an owner.** `PersonalityStateIntegrator.closeHour()` moves `homeOffset` from the signed exposure integral (TESSERA slow drift). It is bounded by `dMax` (0.10) and decays back toward 0 over `tauSetpoint` (180 d). `SituationalDeformationPhase` runs this at consolidation cadence and persists it through `SituationalStateService`. Era 7b key decision 1 is "one model, not overlay". The one missing PID-5 step is graduation of persistent `homeOffset` into the identity baseline.
5. **Upstream infrastructure is unwired or starved.** The situational pipeline has no production wiring (#1082). `ConsolidationScheduler` starves busy deployments and forgets tenants on restart (#1063). Every production `RelationshipRecorded` is `QualitySignal.NEUTRAL` (`RelationshipProcessor:39-42`), so the JPAF path receives no signals (#1102).

The first revision of this spec rested on three false premises:

- that nothing writes `homeOffset`
- that `updateBase()` is a durable propagation path
- that JPAF evaluation is simple enough to re-implement

This revision removes all three.

## Design

### Core principle

**Unify where the process really is the same. Keep each family's native dynamics where it is not.**

Both personality families do share one *outcome*: lasting change to who the agent is. They also share where that change lives, how it reaches derived cognition, its time basis, and how it is audited. They do **not** share an accumulation and evaluation process:

| | Disposition-profile family (JPAF) | PID-5 facet family |
|---|---|---|
| Dimensions | `dispositionProfile` terms. Vocabulary-generic: Jungian functions, Big Five, DISC, … (issue-126 D2) | AMPD/PID-5 facets (`ampdFacets`) |
| Nature of change | Discrete: type transitions (swap, replacement, reorganisation) | Continuous: elastic-band drift |
| Accumulator | `DispositionSignalStore` (Eidos; `JpaDispositionSignalStore` is persistent) | Integrator exposure integral → `homeOffset` (neocortex, persisted in MindMap) |
| Evaluator | `DispositionHealth.probe` + `DispositionEvolution.evaluate` (Eidos; four JPAF rules, vocabulary shadows, tenant preferences, canonical normalisation) | `PersonalityStateIntegrator` (closeHour, and the new promotion step) |
| Owner of evaluation | Eidos, the vocabulary owner. Neocortex decides *when* and *where the result goes* | Situational state owner (`cognition.situational`) |

**Unified elements, one each:**

- **Identity of record:** `AgentDescriptor.disposition` in Eidos `AgentRegistry`, written through a real `DispositionProfileStore` (eidos#235).
- **Propagation path:** registry `register` → `AgentDescriptorUpdated` → `EffectiveCognitiveDefaults.updateBase` with the owner's descriptor. `CognitionCore`'s per-tick re-base reads the same owner, so the two can never diverge.
- **Time basis:** wall-clock grids, independent of tick rate and scheduler cadence (Era 7b key decision 4). PID-5 uses the integrator's hourly grid. JPAF uses a reflection-period grid.
- **Cadence owner:** consolidation phases in `cognition`, ordered explicitly.
- **Audit:** `CognitiveJournal` entries, plus attention signals for significant events.

### Personality change model, per family

```
PID-5 facets (owner: situational state, cognition.situational)
  Displacement   per tick           integrator.pull                 existing (#712)
  Home offset    hourly grid        integrator.closeHour            existing (#712)
  Baseline       hourly grid,       SituationalDeformationPhase     NEW (this issue)
  promotion      dwell-gated        → DispositionProfileStore.updateFacets

Disposition profile (owner of evaluation: Eidos JPAF; cadence: cognition.personality)
  Activation     event time         DispositionSignalRecorder       NEW (replaces PEO.record)
                                    → DispositionSignalStore
  Reflection     reflection grid    DispositionEvolutionPhase       NEW (replaces PEO.tick)
                                    → DispositionHealth.probe
  Transition     on EvolutionPending→Evolved                        NEW
                                    → DispositionProfileStore.update
```

### Identity of record and propagation

**Eidos owns identity.** eidos#235 delivers a registry-backed `DispositionProfileStore` with:

- `update(agentId, tenancyId, List<DispositionValue>)`, which already exists in the SPI and now gets a real implementation;
- `updateFacets(agentId, tenancyId, Map<String, Integer> absoluteScores)`, which is new. Writes are absolute, so a retried write is idempotent.

Both run as a transactional read-modify-`register`, guarded against lost updates. `AgentRegistry.updateGoalLifecycleState` already follows this pattern. `register` fires `AgentDescriptorUpdated` in both the JPA and in-memory registries.

**Propagation (absorbs #1080).** `IdentityChangePropagator` lives in `cognitive-eidos`, alongside `EidosDescriptorViewSource`:

```java
@ApplicationScoped
class IdentityChangePropagator {
    void onUpdated(@Observes(during = TransactionPhase.AFTER_SUCCESS) AgentDescriptorUpdated e) {
        var d = e.current();
        effectiveDefaults.updateBase(d.tenancyId(),
                EidosCognitiveProfileBridge.toDescriptorView(d), "identity-update");
    }
}
```

- `AFTER_SUCCESS` means a rolled-back identity write never reaches derived cognition. Outside JTA, the observer is notified immediately.
- The view comes from the descriptor the owner just committed, so this call refreshes from the owner. It is not a second writer.
- This also covers every other registry update path (for example goal lifecycle and admin edits), which #1080 was filed for.

**Per-tick re-base consistency.** `CognitionCore.tick()` keeps re-basing from the caller's descriptor. That stays correct as long as the caller resolves the descriptor from `AgentRegistry` on each tick. Agency's `CognitionAvatarAdapter` resolves it through `agentRegistry.findById`. agency#487 verifies there is no caching.

**No neocortex component writes the base layer directly any more.** The direct `updateBase` / `updateState` calls from evolution logic in rev 1 are removed.

| Change | Writer | Propagation |
|---|---|---|
| JPAF type transition | `DispositionEvolutionPhase` → `DispositionProfileStore.update` | registry → `AgentDescriptorUpdated` → `IdentityChangePropagator` → `updateBase` |
| PID-5 baseline promotion | `SituationalDeformationPhase` → `DispositionProfileStore.updateFacets` | same path. `homeOffset` reduction is published through the existing `updateState` snapshot |
| PID-5 `homeOffset` drift | integrator (existing) | `updateState` (existing, unchanged) |

### Disposition-profile evolution (JPAF family)

#### `DispositionEvolutionPhase` (cognition, `cognition.personality`)

`@ApplicationScoped @Priority(50)`. Implements the `mindmap-intelligence` `ConsolidationPhase` SPI, following the precedent of `SituationalDeformationPhase`, `RelationalSchemaEvolutionPhase` (@20), `RelationshipStagePhase` (@18), `DriveAdaptationPhase` (@17) and `BeliefRevisionPhase` (@14). It lives in `cognition` because `cognition` depends on `mindmap-intelligence` (`cognition/pom.xml:66`) and not the other way round.

It injects the Eidos SPIs `DispositionSignalStore`, `DispositionHealth`, `DispositionEvolution`, `DispositionProfileStore` and `AgentRegistry`. It also injects `CbrRecordStore`, `EffectiveCognitiveDefaults` (read-only, for `relationalComplexity`), `DispositionEvolutionLedgerStore` and `Clock`.

**`run(tenantId, subgraphPriority)`:**

```
for agentId in effectiveDefaults.agentIds(tenantId):
    ledger = ledgerStore.load(tenantId, agentId)          // persisted; see below
    n = floor((now - ledger.lastReflectionAt) / config.reflectionPeriod)
    if n == 0: continue                                    // wall-clock gate
    descriptor = agentRegistry.findById(agentId, tenantId) // the owner's view
    if descriptor has no dispositionProfile: advance ledger; continue

    // 1. Decay: wall-clock, catch-up exact for missed periods
    signalStore.decay(agentId, tenantId, config.retentionPerReflection ^ n)

    // 2. Evaluate: pure, no side effects
    status = health.probe(descriptor, probeContext)
    decision = switch status:
        Aligned            -> Stable                                    (halt := false)
        Drifted d          -> d.magnitude >= l2Ceiling * relationalComplexity
                              ? Halted(d.magnitude)                    (halt := true)
                              : Drifting(d.magnitude)                  (halt := false)
        EvolutionPending p -> switch evolution.evaluate(descriptor, p):
                                Evolved e  -> Evolved(e, p.type)       (halt := false)
                                Dampened x -> Dampened(x.decayFactor)  (halt := true)

    // 3. Commit: only after the decision is final
    Evolved:  profileStore.update(agentId, tenantId, e.newProfile)     // identity write
              cbrStore.store(transition case, trigger_type = p.type)   // PersonalityTransitionSchema
              signalStore.clear(agentId, tenantId)
    Dampened: signalStore.decay(agentId, tenantId, x.decayFactor)

    // 4. Record
    ledger := ledger.advancedBy(n * reflectionPeriod).withHalted(halt)
    ledgerStore.persist(ledger)
    journal.record(DispositionReflected(...outcome...))
    signals: Evolved -> PERSONALITY_EVOLVED (1.0); Halted -> PERSONALITY_HALT (0.9)
```

This keeps the orchestrator's semantics exactly, which the existing `PersonalityEvolutionOrchestratorTest` scenarios specify (stable, drifting, halted, evolved, dampened). It changes the parts that were wrong:

- **Gate before commit.** `probe` and `evaluate` are pure. The identity write, CBR case and signal clear happen only after the decision is final. The drift ceiling is checked inside the decision, never after a write.
- **Per-family safety in native units.** The L2 ceiling applies to the JPAF effective-weight simplex only, scaled by `relationalComplexity` (Cattell 1971; Halford 1998). It is never combined with facet units. PID-5 safety is in §Safety.
- **Wall-clock reflection grid.** This is the JPAF "reflection at episode boundaries" model with batched periodic probing and a time-based decay anchor (issue-126 D3), and it matches the integrator's hourly-grid pattern. Decay per reflection is `retentionPerReflection`. Missed periods catch up exactly as `retention^n`. Signal half-life is therefore independent of scheduler cadence, idle gating, `consolidateNow` bursts or starvation. A coarse grid, rather than continuous `factor^(Δt/τ)` on every run, is required by the store: `DispositionSignalStore` counts are integers and `JpaDispositionSignalStore.decay` truncates (`(int)(count·f)`), so frequent small decays would wipe signals. eidos#237 tracks moving to fractional weights. Once that lands, the grid could become continuous without any structural change here.
- **Persisted reflection ledger.** `lastReflectionAt` and `halted` are persisted per agent, so a restart neither resets the reflection clock nor clears a halt.

#### `DispositionEvolutionLedgerStore` (cognition, `cognition.personality`)

One MindMap node per agent (`evo-ledger:<hash(agentId)>`) in the `PERSONALITY_STATE` subgraph, using the same subgraph resolution and node-naming scheme as `SituationalStateService`. Properties are `lastReflectionAt` and `halted`. It keeps a write-through in-memory cache, which the recorder reads on its hot path.

- **Writer:** `DispositionEvolutionPhase` only.
- **Readers:** the phase, and `DispositionSignalRecorder` (halt check).
- An agent with no ledger starts with `lastReflectionAt = now`, so its first reflection happens one period after first sight.

#### `DispositionSignalRecorder` (cognition, `cognition.personality`)

An `@ApplicationScoped` CDI observer. It replaces `PersonalityEvolutionOrchestrator.record()`.

```
@Observes RelationshipRecorded e:
    ev = e.event()
    source = sources.forEventType(RelationshipEvent.class)   // at most one, see dedup rule
    if source == null || !source.relevant(ev): return          // NEUTRAL short-circuits here,
                                                                // before any registry lookup
    if ledgerStore.isHalted(ev.tenantId(), ev.agentId()): return
    descriptor = agentRegistry.findById(ev.agentId(), ev.tenantId())   // lazy, only when needed
    for a in source.translate(ev, descriptor):
        if a.functionTerm() in descriptor profile terms:
            signalStore.recordActivation(agentId, tenantId, a.functionTerm(), a.valence())
        else:
            debug-log the dropped term (vocabulary mismatch is visible, not silent)
```

- **One event type only.** It observes only `RelationshipRecorded`, the only event with a concrete pressure source. `ExperienceRecorded` is **not** observed. `RelationshipRecorded` is derived from it (`RelationshipProcessor.onExperienceRecorded`), so observing both would double-count one experience.
- **Dedup rule.** Each event type in a derivation chain binds to at most one `TraitPressureSource`. The recorder builds a `Map<Class<?>, TraitPressureSource<?>>` at startup and **fails fast** if two sources declare the same `eventType()`. That replaces the orchestrator's order-dependent "first match wins". A future source for a primary event (`ExperienceRecorded`) must exclude experiences that produce a derived `RelationshipRecorded`. #1102 tracks the valenced sources.
- **Concurrency.** An activation recorded between a reflection's `probe` and its `clear` is consumed by that evolution. This is the intended semantics: the transition closes the signal epoch. No lock is needed. The scheduler serialises phase runs under its own lock on one executor thread, and the signal stores are safe to call concurrently (JPA row-transactional; in-memory concurrent maps).

#### `TraitPressureSource<E>` / `TraitActivation`: kept

Their shape (an Eidos `AgentDescriptor` in, a `(profileTerm, SignalValence)` activation out) is exactly what `DispositionSignalStore.recordActivation` consumes. One addition:

```java
default boolean relevant(E event) { return true; }   // cheap pre-filter, no descriptor needed
```

`RelationshipPressureSource` overrides it as `qualitySignal() != NEUTRAL` and is otherwise unchanged.

#### `DispositionEvolutionConfig` (cognition-api): replaces `PersonalityEvolutionConfig`

```java
public record DispositionEvolutionConfig(
    Duration reflectionPeriod,        // JPAF reflection grid (default 24h; issue-126 D3)
    double retentionPerReflection,    // signal retention per reflection period (default 0.8,
                                      //   unchanged from PersonalityEvolutionConfig.DEFAULT_DECAY_FACTOR)
    double l2Ceiling                  // drift ceiling on the JPAF weight simplex (default 0.15),
                                      //   scaled by relationalComplexity
) {}
```

`dampeningFactor` is removed. The orchestrator never read it: the dampened path uses `EvolutionResult.Dampened.decayFactor()`, which comes from the Eidos tenant preference `DispositionPreferenceKeys.DECAY_FACTOR`. Dampening strength stays an Eidos-owned preference.

The config is renamed because it is family-specific. A neutral "personality" name would be dishonest about scope.

#### `ReflectionOutcome` (cognition, `cognition.personality`): replaces `EvolutionTick`

A sealed type with the variants `Stable`, `Drifting(magnitude)`, `Halted(magnitude)`, `Evolved(previousLabel, newLabel, newProfile, triggerType)` and `Dampened(decayFactor)`. It is the per-agent result of one reflection and is used in the journal entry and in tests. The name is chosen so it does not collide with `io.casehub.eidos.api.DispositionEvolution.EvolutionResult`. `EvolutionTick` (cognition-api) is deleted.

### PID-5 baseline promotion (facet family)

The integrator already owns displacement and `homeOffset`. This issue adds only the final step: graduating **persistent** home offset into the identity baseline. The state owner performs it as part of the same state transition.

#### Promotion rule (hourly grid, inside `PersonalityStateIntegrator`)

`FacetState` gains two fields:

- `saturatedSince` (`Instant`, nullable)
- `promoted` (`double`): cumulative baseline change promoted so far, signed

Both are persisted by `SituationalStateService.toProperties` / `fromProperties` like the existing fields.

At each `closeHour` boundary:

- If `|homeOffset| ≥ promoteFraction · dMax` (default 0.8 · 0.10 = 0.08) and `saturatedSince == null`, set `saturatedSince` to the boundary.
- If `|homeOffset|` falls below the threshold, set `saturatedSince := null`.

`fastForwardIdleHours` applies the same rule. It is evaluated once at the end of the fast-forward, after the closed-form `homeOffset` decay. That is exact, because `|homeOffset|` decays monotonically during idle hours.

`integrator.promotionCandidates(state, baselines, now)` is pure. It returns a `FacetPromotion(facet, delta, targetScore)` for each facet where all of these hold:

- `saturatedSince != null`
- `now − saturatedSince ≥ promoteDwell` (default 30 d)
- `|promoted + homeOffset| ≤ promotionBudget` (default 0.20 on the 0–1 facet scale)

The values are computed as follows:

- `targetScore = round(100 · clamp01(baseline + homeOffset))` (Eidos AMPD scores are integer 0–100)
- `delta = targetScore/100 − baseline`, which is the exact amount the identity write will apply

**Why these defaults:** `dMax` is 0.10, so any promotion threshold above `dMax` is unreachable. Rev 1's 0.3 could never fire. Sustained near-saturation for a month is the TESSERA criterion: repeated states over a long period, not a transient. The 180-day `tauSetpoint` already treats `homeOffset` as lasting. Promotion makes it *identity*, which is not subject to setpoint decay. The cumulative budget caps lifetime identity drift per facet. Without it, re-saturation after each promotion would allow unbounded drift over years.

#### Promotion transaction (in `SituationalDeformationPhase.run`, per agent)

Ordering is chosen so that every failure under-counts and never double-counts.

```
state = integrator.advance(state, now)                       // existing
if state.pendingPromotions non-empty:                         // recover an interrupted run
    profileStore.updateFacets(agent, tenant, pending absolute scores)   // idempotent
    state = state.withPendingPromotions(empty); persist

candidates = integrator.promotionCandidates(state, baselines(descriptorView), now)
if candidates non-empty:
    state = state.applyPromotions(candidates)   // homeOffset -= delta, promoted += delta,
                                                // saturatedSince := null,
                                                // pendingPromotions := candidates
    stateService.persist(tenant, agent, state)                // (1) durable intent
    profileStore.updateFacets(agent, tenant, absolute scores) // (2) identity write → propagation
    state = state.withPendingPromotions(empty)
    stateService.persist(tenant, agent, state)                // (3) intent cleared
    journal.record(PersonalityFacetPromoted(...)); signal PERSONALITY_EVOLVED (0.8)
for facets blocked only by the budget: journal.record(PersonalityPromotionCapped(...))

effectiveDefaults.updateState(snapshot)   // existing; published after (2)
```

- **Continuity.** Before promotion, the resting score is `baseline + homeOffset`. After it, the score is `(baseline + delta) + (homeOffset − delta)`. Derived cognition sees no jump.
- **Failure between (1) and (2).** The resting score is low by `delta` until the next run replays the pending absolute write. That is conservative: identity never overshoots.
- **No double count.** The identity write is absolute, and the state reduction happens before it.

**Integrator baseline.** `PersonalityStateIntegrator.baselineFor` currently returns a hard-coded 0.5 when it clamps displacement. Promotion needs real baselines, and so does correct clamping. The integrator therefore takes per-facet baselines from the `DescriptorView`:

- `pull` gets them from the participant's descriptor.
- `promotionCandidates` gets them from `DescriptorViewSource` in the phase.

This is absorbed here because both changes touch the same code.

**Phase ordering.** `SituationalDeformationPhase` gets `@Priority(45)`. Today it has none and sorts to `Integer.MAX_VALUE`, and its CDI registration is #1082. `DispositionEvolutionPhase` gets `@Priority(50)`. The two families are independent and run sequentially on the scheduler thread, so no ordering dependency exists between them. The priorities only make the order deterministic and keep both after the data-producing phases (14–20).

### Safety (per family, native units)

| Family | Mechanism | Units | Owner |
|---|---|---|---|
| JPAF | L2 drift ceiling on effective weights × `relationalComplexity`. Over-reinforcement `Drifted` halts. `Dampened` halts | weight simplex | `DispositionEvolutionPhase`; halt persisted in the ledger |
| JPAF | Halt gates signal recording | – | Read by `DispositionSignalRecorder` |
| PID-5 | `dMax` bounds `homeOffset`; `tauSetpoint` returns it toward 0 | facet scale 0–1 | integrator (existing) |
| PID-5 | Dwell-gated promotion and a cumulative `promotionBudget` per facet | facet scale 0–1 | integrator |

There is no cross-family drift norm. Weight-simplex deltas and facet-scale offsets cannot be compared, so combining them in one L2 would let one family halt the other.

### Observability

**Journal entries** (`CognitiveEntry`, alongside `SituationalDeformationConsolidated`), so evolution is auditable even when attention is disabled:

- `DispositionReflected(tenantId, agentId, ref, at, outcome, magnitude, previousLabel, newLabel, triggerType)`: one per reflection that runs
- `PersonalityFacetPromoted(tenantId, agentId, ref, at, facet, delta, newScore, cumulativePromoted)`
- `PersonalityPromotionCapped(tenantId, agentId, ref, at, facet, homeOffset, cumulativePromoted)`

**Attention signals.** Two values are added to `io.casehub.neocortex.mindmap.SignalCategory` (mindmap-api). This is the enum used by `ConsolidationPhase.signals()` / `AttentionSignal` and consumed by `ConsolidationScheduler`. The `mindmap.intelligence.SignalCategory` enum is not touched.

| Event | Category | Significance |
|---|---|---|
| JPAF type transition | `PERSONALITY_EVOLVED` | 1.0 |
| PID-5 baseline promotion | `PERSONALITY_EVOLVED` | 0.8 |
| JPAF drift halt | `PERSONALITY_HALT` | 0.9 |

### Module placement

| Type | Module | Notes |
|---|---|---|
| `DispositionEvolutionPhase` | cognition (`cognition.personality`) | `ConsolidationPhase` impl; `cognition` → `mindmap-intelligence` |
| `DispositionSignalRecorder` | cognition (`cognition.personality`) | CDI observer |
| `DispositionEvolutionLedgerStore` | cognition (`cognition.personality`) | MindMap-backed |
| `ReflectionOutcome` | cognition (`cognition.personality`) | replaces `EvolutionTick` |
| `DispositionEvolutionConfig` | cognition-api | replaces `PersonalityEvolutionConfig` |
| `TraitPressureSource.relevant` (default method) | cognition-api | SPI addition |
| Promotion (`FacetState` fields, `promotionCandidates`, baselines) | cognition (`cognition.situational`) | state owner |
| Promotion step, `@Priority(45)` | cognition (`SituationalDeformationPhase`) | |
| `IdentityChangePropagator` | cognitive-eidos | absorbs #1080 |
| Journal entry types | alongside `CognitiveEntry` | |
| `PERSONALITY_EVOLVED`, `PERSONALITY_HALT` | mindmap-api `SignalCategory` | |

### Deletions (no deprecation; there are no external users)

| Removed | Replaced by |
|---|---|
| `PersonalityEvolutionOrchestrator` | `DispositionEvolutionPhase` + `DispositionSignalRecorder` |
| `EvolutionTick` (cognition-api) | `ReflectionOutcome` (cognition) |
| `PersonalityEvolutionConfig` (cognition-api) | `DispositionEvolutionConfig` |

The Agency producers of the orchestrator are removed in agency#487, in the same change window.

**Not deprecated:** `DispositionSignalStore`, `DispositionHealth`, `DispositionEvolution`, `SignalValence`. They remain the JPAF accumulator and evaluator (issue-126 D1, reaffirmed). `DispositionProfileStore` becomes real (eidos#235).

### Prerequisites and sequencing

| Dependency | Kind | Effect if absent |
|---|---|---|
| casehubio/eidos#235: registry-backed `DispositionProfileStore` + `updateFacets` | **Hard.** Lands first | Every identity change is discarded (NoOp). Nothing in this design changes identity |
| #1063: scheduler starvation and restart tenant loss | **Hard for production effect** | Both phases are cadence-invariant (wall-clock grids with exact catch-up), so they are *correct* under any schedule. But they *never run* for busy deployments or unregistered tenants |
| #1082: situational pipeline wiring | **Hard for PID-5 promotion** | `stateService.cachedAgentIds` is empty, so no PID-5 state exists to promote. The JPAF path does not depend on it |
| #1102: valenced relationship and goal-outcome signals | **Hard for production non-inertness of JPAF** | The JPAF pipeline is wired and verified with synthetic valenced events, but production `RelationshipRecorded` is always NEUTRAL, so no activations occur |
| casehubio/agency#487: remove orchestrator producers, wire the new beans | Same change window | Agency fails to compile |
| casehubio/eidos#237: fractional activation weights | Not blocking | Integer truncation biases low counts; the reflection grid limits the damage |

**What #1060 closes:** the structural defect. Evolution is evaluated on a durable wall-clock cadence. Its result is written to the identity of record. It reaches `EffectiveCognitiveDefaults` through one path, for both families.

**What it does not close:** signal starvation (#1102) and scheduler starvation (#1063). Those are tracked separately because their causes are upstream of evolution.

### Testing strategy

1. **`DispositionEvolutionPhase` unit tests** (Eidos SPIs as test doubles):
   - Behavioural parity with every `PersonalityEvolutionOrchestratorTest` scenario: stable, drifting, halted (with `relationalComplexity` scaling), evolved (profile write, CBR `trigger_type` = JPAF type, signal clear), dampened.
   - The gate-before-commit property: no `profileStore` or `cbrStore` interaction on a Halted or Drifting outcome.
   - The reflection grid: no reflection before the period; `retention^n` on catch-up after n missed periods; the result is independent of how many `run` calls happen within one period.
   - The ledger: halt survives a store reload; `lastReflectionAt` advances by whole periods.
2. **`DispositionSignalRecorder` unit tests:**
   - NEUTRAL produces no registry lookup.
   - Halted produces no activation.
   - A term not in the profile is dropped and logged.
   - Startup fails on duplicate `eventType()` sources.
   - `ExperienceRecorded` is not observed.
3. **Integrator promotion tests:**
   - The dwell clock starts and resets across hour boundaries and idle fast-forward.
   - No candidate before the dwell; a candidate after it.
   - The budget cap blocks promotion and journals it.
   - `delta` matches integer rounding exactly.
   - Continuity: the resting facet is identical before and after promotion.
   - Baselines replace the hard-coded 0.5 in clamping.
4. **`SituationalDeformationPhase` promotion tests:**
   - The ordering persist(intent) → `updateFacets` → persist(clear).
   - Crash recovery: a pending intent is replayed idempotently on the next run.
   - No double count when the identity write is replayed.
5. **`IdentityChangePropagator` tests:**
   - `AgentDescriptorUpdated` → `updateBase` with the current descriptor's view.
   - Not invoked on rollback (`AFTER_SUCCESS`).
6. **Integration** (in-memory Eidos registry and stores, synthetic valenced `RelationshipRecorded`):
   - Events → activations → reflection → `Evolved` → registry descriptor changed → `EffectiveCognitiveDefaults.forAgent` reflects the new dominant function.
   - A following simulated `CognitionCore` tick with a registry-sourced descriptor does **not** revert it.
   - PID-5: sustained displacement over simulated weeks → saturation → promotion → registry `ampdFacets` updated → effective facet continuous across the promotion.

## Decisions

See `decisions.md`. Rev 2 revises D3–D6 and adds D7–D8.

## References

- `PersonalityEvolutionOrchestrator.java`, `PersonalityEvolutionOrchestratorTest.java`: the behaviour being replaced and its specification
- `PersonalityStateIntegrator.java`, `SituationalDeformationPhase.java`, `SituationalStateService.java`, `FacetState.java`, `DynamicsConfig.java`: PID-5 state owner
- `EffectiveCognitiveDefaults.java`, `CognitionCore.java:288-291`, `EidosDescriptorViewSource.java`: base layer and its owner
- Eidos `DefaultDispositionHealth.java`, `DefaultDispositionEvolution.java`, `JpaDispositionSignalStore.java`, `JpaAgentRegistry.java` (`register` → `AgentDescriptorUpdated`), `AgentRegistry.updateGoalLifecycleState` (read-modify-register precedent)
- `RelationshipProcessor.java`, `RelationshipPressureSource.java`: the signal source and why it is NEUTRAL
- `ConsolidationScheduler.java`: `@Priority` ordering, single-thread lock
- `docs/specs/issue-126-autonomous-agent-patterns/decisions.md`: D1 (keep the Eidos JPAF pipeline), D2 (vocabulary-generic profile terms), D3 (batched periodic reflection)
- `docs/research/era7-personality-trait-integration-research.md`: Era 7b key decisions (one model; wall-clock grid)
- casehubio/neocortex#712, #1055, #1063, #1080, #1082, #1102; casehubio/eidos#235, #237; casehubio/agency#487
