# Unified Personality Evolution

**Issue:** casehubio/neocortex#1060
**Refs:** #712 (situational modulation, Era 7b), #1055 (EffectiveCognitiveDefaults), #126 (JPAF orchestrator), #1080 (absorbed)
**Prerequisites:** #1082, #1063; under option (B) only: casehubio/eidos#235, casehubio/eidos#239 (see §Prerequisites; R1-01)
**Follow-ups:** #1102, #1104 (single-instance deployment contract), casehubio/agency#487, casehubio/eidos#237
**Date:** 2026-11-17 (rev 2, after the round-1 structure review; robustness amendments marked **[R]**, after the round-1 robustness review; structure round-2 amendments marked **[S2]**)

## Problem

All of the following were verified in code.

1. **The JPAF pipeline is never run.** `PersonalityEvolutionOrchestrator.tick()` / `record()` have no production callers. Agency only produces the bean (`AgencyBeans:308`, `AgencyAutoConfiguration:287`).
2. **Identity writes are discarded.** On evolution, the orchestrator calls `DispositionProfileStore.update()`. The only implementation is `NoOpDispositionProfileStore`, and the SPI has no facet write.
3. **The base layer has exactly one owner, the Eidos descriptor.** `CognitionCore.tick()` calls `effectiveDefaults.updateBase(tenantId, toDescriptorView(descriptor), …)` on every tick (`CognitionCore.java:288-291`). `EidosDescriptorViewSource` reads the same `AgentRegistry`. A lasting change written anywhere other than the registry is reverted on the next tick.
4. **PID-5 lasting drift already exists and has an owner.** `PersonalityStateIntegrator.closeHour()` moves `homeOffset` from the signed exposure integral (TESSERA slow drift). It is bounded by `dMax` (0.10) and decays back toward 0 over `tauSetpoint` (180 d). `SituationalDeformationPhase` runs this at consolidation cadence and persists it through `SituationalStateService`. Era 7b key decision 1 is "one model, not overlay". The one missing PID-5 step is graduation of persistent `homeOffset` into the identity baseline.
5. **[R] The propagation target itself has no production bean.** No producer for `EffectiveCognitiveDefaults` exists in neocortex or agency. The only construction is `EffectiveCognitiveDefaults.forTesting`, and agency consumes it only as `Optional`. `PersonalityStateSource`'s only production implementation, `DefaultPersonalityStateSource`, returns `Optional.empty()`. So even a correct `updateBase`/`updateState` call reaches nothing in production, and an evicted or restarted slot never sees `homeOffset`.
6. **Upstream infrastructure is unwired or starved.** The situational pipeline has no production wiring (#1082). `ConsolidationScheduler` starves busy deployments and forgets tenants on restart (#1063). Every production `RelationshipRecorded` is `QualitySignal.NEUTRAL` (`RelationshipProcessor:39-42`), so the JPAF path receives no signals (#1102).

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

- **Store of record for lived results** *[depends on R1-01]*. Under (B): `AgentDescriptor.disposition` in Eidos `AgentRegistry`, written through a real `DispositionProfileStore` (eidos#235). Under (A): the per-agent `PersonalityState` node; Eidos holds authored identity only.
- **Propagation path** *[depends on R1-01]*. Under (B): registry `register` → `AgentDescriptorUpdated` → `EffectiveCognitiveDefaults.updateBase` with the owner's descriptor; `CognitionCore`'s per-tick re-base reads the same owner. Under (A): `PersonalityStateService.transition` → `updateState(snapshot)`; the per-tick authored `updateBase` is correct by construction, because `recompute` carries the state snapshot across base updates.
- **Time basis:** wall-clock grids, independent of tick rate and scheduler cadence (Era 7b key decision 4). PID-5 uses the integrator's hourly grid. JPAF uses a reflection-period grid.
- **Cadence owner:** consolidation phases in `cognition`, ordered explicitly.
- **Audit:** `CognitiveJournal` entries, plus attention signals for significant events.

### Personality change model, per family *[promotion and transition targets depend on R1-01; the diagram shows (B)]*

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

### Identity of record and propagation *[depends on R1-01: this section describes option (B)]*

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

### Open decision: store of record for lived personality (coherence review R1-01 / R1-11)

**Defect in the registry-as-store-of-record path, verified in code.** Authored descriptors are re-registered on every boot:

1. `AgentDescriptorYamlRegistrar.register` (eidos runtime) maps the classpath YAML and calls `registry::register`.
2. `JpaAgentRegistry.register` is `DELETE` + `persist`, a wholesale replace, and fires `AgentDescriptorUpdated(previous, authored)`.

So after every restart:
- A JPAF transition written through `DispositionProfileStore.update` is reverted to the authored `dispositionProfile`, and `IdentityChangePropagator` propagates the reversion.
- A PID-5 promotion written through `updateFacets` is reverted, but neocortex `FacetState` still holds `homeOffset − delta` and `promoted + delta`. The lived facet score therefore **drops by `delta`** below its pre-promotion value, and the promotion budget accounting no longer matches identity.

Neither eidos#235 nor this spec handles it. The defect is noted on eidos#235.

**Options:**

- **(A) Neocortex stores lived results; Eidos keeps evaluating them (recommended).**
  - JPAF *evaluation* stays in Eidos, per issue-126 D1/D2. `DispositionHealth.probe` and `DispositionEvolution.evaluate` are pure functions of `(descriptor, signal counts)`.
  - The *result* is stored in neocortex lived state, next to `homeOffset`. The phase writes the evolved profile into the per-agent `PersonalityState` node (property `profile.<term>.weight`) through `PersonalityStateService.transition`. *[C2]* Neocortex calls **no** `DispositionProfileStore` under (A). Implementing the Eidos SPI only to call it from the same module would be indirection with no architectural benefit, and it would compete with eidos#235's bean.
  - The phase probes with the **lived descriptor**: the authored descriptor with the lived profile substituted.
  - PID-5 promotion moves `homeOffset` into the non-decaying `FacetState.promoted` component. It is not written to Eidos. *[C2]* The **meaning of `promoted` differs by option**. Under (A) it is a lived component of the resting score. Under (B) it is a bookkeeping counter of what was already written into the registry baseline (see the option table below).
  - `EffectiveCognitiveDefaults` composes `authored ⊕ lived` (lived profile replaces authored weights; resting facet = `baseline + promoted + homeOffset`). The per-tick authored `updateBase` from `CognitionCore` becomes correct by construction, because `recompute` carries the state snapshot across base updates.
  - What this removes: the two-store intent/replay protocol, the registry lost-update locking (eidos#235 item 3), `IdentityChangePropagator`'s role in evolution, and the boot defect.
  - What it costs: Eidos consumers that read `AgentRegistry` directly, such as the agency prompt section, must read lived personality from `EffectiveCognitiveDefaults`. That goes into agency#487.
  - It matches the #712 layering, where the personality state vector modulates between the identity store and the CDE (Era 7b decision 1, "one model": a single continuously evolving state vector).
- **(B) Registry stays store of record; Eidos separates authored from evolved.** eidos#235 is extended so that re-registration preserves evolved `dispositionProfile`/`ampdFacets`, or so that an evolved layer is stored separately and composed in `findById`. This keeps every `AgentRegistry` reader seeing lived identity. The costs:
  - an authored/evolved split is still built, just inside the registry;
  - cross-store promotion stays crash-sensitive, because neocortex `promoted` and Eidos `ampdFacets` must agree;
  - registry write contention remains.

Until this is decided, the propagation table above is correct only for an uninterrupted process lifetime.

**[C2] Option-dependent text and rewrite scope.** Sections whose text depends on R1-01 are tagged *[depends on R1-01]*, or carry inline *(A)*/*(B)* variants. Untagged prose that names the registry, `IdentityChangePropagator`, `profileStore` or `updateFacets` describes option (B). This table is the complete (A) delta:

| Section | As written (B) | Under (A) |
|---|---|---|
| §Core principle, §Identity of record and propagation | Registry of record; `AgentDescriptorUpdated` → `IdentityChangePropagator` → `updateBase` | `PersonalityState` of record; `transition` → `updateState`. The propagator stays only for non-evolution registry updates (goal lifecycle, admin edits; the #1080 scope) |
| `DispositionProfileStore` bean | eidos#235 registry-backed bean, called by both phases | Not called by neocortex; no second bean to arbitrate; eidos#235 is not a #1060 prerequisite |
| §DispositionEvolutionPhase: descriptor probed | `agentRegistry.findById` (registry = lived) | **Lived descriptor**: the registry descriptor with `dispositionProfile` replaced by `PersonalityState.livedProfile` when present |
| §DispositionSignalRecorder: dominant/auxiliary ranking | Registry descriptor | Lived descriptor (same substitution). Membership is unaffected: `DefaultDispositionEvolution` swap, replacement and reorganisation only re-weight terms already in the profile |
| §JPAF commit ordering | Steps (1)–(5) across state, registry, signal store and CBR | (1)+(2) are one `transition` (intent + lived profile). (3) clear and (4) CBR follow, then (5) is a **separate** `transition` that clears the intent. See the correction in §JPAF commit ordering |
| §Promotion rule: `promoted` | Bookkeeping: the registry baseline already includes it, so resting = `baseline_registry + homeOffset` | Lived component: resting = `baseline_authored + promoted + homeOffset`, and the authored baseline is never mutated. The budget test `|promoted + homeOffset| ≤ promotionBudget` is identical in both |
| §Promotion rule: `delta` | `round` to an integer AMPD `targetScore`; `delta = targetScore/100 − baseline` | No rounding: `delta = clamp01(baseline + promoted + homeOffset) − (baseline + promoted)` |
| §Promotion transaction | Two `transition`s around `updateFacets`, with `pendingPromotions` | One `transition` (already written as the *(A)* block) |
| §Prerequisites | eidos#235, eidos#239 hard | Neither required |
| §Testing items 4–6 | Assert registry `dispositionProfile`/`ampdFacets`, propagator | Assert `PersonalityState` and `forAgent()`. Item 8 (tick → evict → restart) is unchanged and must pass under either option |

**[S2] Structure-review evidence for the decision.** Round 2 of the structure review raised five findings. Four of them come from evolution results crossing a store boundary: R2-01 (cross-store double count), R2-02 (publication order across two layers), R2-03 (facet-key contract on writes) and R2-05 (three-store JPAF commit).

- **Under (A):** every evolution result commits in **one** `PersonalityStateService.transition` (§Lived personality state). The only remaining cross-store step is clearing the Eidos signal store, and it is ordered so that a failure under-counts.
- **Under (B):** each of those findings needs its own protocol (intent/replay, ordered publication, canonical-key writes, registry locking). Those protocols are specified below for (B), but they are cost that (A) does not pay.

Structure therefore also recommends **(A)**. It is the option with one owner per kind of data:
- **Eidos** owns *authored* identity. Boot re-registration from YAML is then correct by construction.
- **Neocortex** owns the *lived* personality state vector (Era 7b decision 1).

Wherever a protocol below differs between the options, it is tagged *(A)* / *(B)*.

### [S3] *(A)* Lived composition and authored edits

This applies under option (A) only. It is written to drop into the collapsed spec verbatim (structure R3-02, R3-03). Under (B) the registry *is* the lived descriptor, and neither rule is needed.

#### One owner of "authored ⊕ lived" (R3-03)

**Rule.** The lived descriptor is the authored descriptor with two substitutions:
- **Profile:** the lived profile replaces the authored one **only if** its stored authored fingerprint equals the fingerprint of the current authored profile (next subsection). Otherwise the authored profile stands.
- **Facets:** each facet's resting score is `clamp01(baseline_authored + promoted + homeOffset)`. The effective score adds `displacement`.

**One implementation.** Pure functions in `cognitive-index`, over neocortex-native types:

```java
public final class LivedComposition {
    static String fingerprint(List<WeightedTerm> authoredProfile);   // terms sorted, weights to 4 dp, SHA-256
    static List<WeightedTerm> profile(List<WeightedTerm> authoredProfile, LivedProfile lived);  // match ? lived : authored
    static DescriptorView compose(DescriptorView authored, PersonalityStateSnapshot lived, boolean includeDisplacement);
}
public record LivedProfile(List<WeightedTerm> profile, String authoredFingerprint) {}
```

All three consumers delegate to it, across both type systems:

| Consumer | Needs | Delegation |
|---|---|---|
| `EffectiveCognitiveDefaults.deriveSlot` | resting/effective `DescriptorView` | `LivedComposition.compose(base, snapshot, false/true)`. This **replaces** the private `composeFacets` |
| `DispositionEvolutionPhase` (probe/evaluate) | Eidos `AgentDescriptor` | `LivedDescriptors.compose(authored, state)` |
| `DispositionSignalRecorder` (dominant/auxiliary ranking for `translate`) | Eidos `AgentDescriptor` | `LivedDescriptors.compose(authored, state)` |

`LivedDescriptors` (cognition, `cognition.personality`) is the single Eidos-facing composer. It delegates to `EidosCognitiveProfileBridge.livedDescriptor(AgentDescriptor authored, LivedProfile lived)` (cognitive-eidos). That method maps the authored `DispositionValue`s to `WeightedTerm`s (as `toDescriptorView` already does), calls `LivedComposition.profile`, maps back, and rebuilds through `toBuilder()`. The rule, including the fingerprint check, therefore exists exactly once. The phase and the recorder share one Eidos-side entry point, and `EffectiveCognitiveDefaults` uses the same function directly.

**[R2] Every other consumer of "who the agent is" (R2-02).** The table above covers composition. The robustness review found three more consumers that would silently read the authored descriptor under (A). Each one must go through the same rule:

| Consumer | Defect if authored | Requirement |
|---|---|---|
| CBR transition case (`old_dominant`/`old_auxiliary`) | The second and every later transition record the wrong "from" state | Built from the probed descriptor (`LivedDescriptors.compose`) for "from", and from `e.newProfile` for "to" |
| `PersonalityStateIntegrator.pull` (displacement clamp) and `promotionCandidates` (promotion clamp) | The clamp runs against `authored`, not `authored + promoted`. Example: authored 0.85, promoted 0.10, `homeOffset` 0.09 → promotion delta 0.09 → resting 1.04, clipped to 1.00, so 0.04 is silently discarded | Callers pass **authored** facet scores only. The integrator itself forms the lived baseline `authored + fs.promoted()` from the state it is given, so no caller can pass the wrong baseline. The (A) delta is `clamp01(b + p + h) − (b + p)` ([C2] table); in the example it is 0.05, and 0.04 stays in `homeOffset` |
| The recorder's ranking on a state-cache miss | It ranks against authored | §DispositionSignalRecorder uses `stateService.read` (load-through), never a cache-only peek |

**Tests:**
- After a lived `TI-NE → NE-TI` swap, a NEGATIVE interaction increments `ti`, the lived auxiliary.
- A second transition's CBR case records `old_dominant = ne`.
- Promotion at authored 0.85 with promoted 0.10 leaves the 0.04 excess in `homeOffset`.

**The snapshot carries raw lived state, not a composed profile.** `PersonalityStateSnapshot` gains `LivedProfile livedProfile` (nullable), and `FacetDisplacement` gains `promoted`. Composition happens in `EffectiveCognitiveDefaults` against the base it currently holds. That base is re-based every tick by `CognitionCore`. A profile composed when the snapshot is built would bake in whatever authored base the state service saw last, and the fingerprint check would then test the wrong base.

**Test.** For one agent, the phase's probed descriptor, the recorder's ranking descriptor and `forAgent()`'s `DescriptorView` expose the same profile in each case: no lived profile, a matching lived profile, and a stale (re-authored) lived profile. `EffectiveCognitiveDefaults` has no composition code of its own.

#### Authored edits: authored identity wins (R3-02)

The two families store lived results with different semantics, and the difference follows the nature of each change (§Core principle):

- **PID-5 `promoted` is a delta.** Like `homeOffset` and displacement, which #712 already composes over whatever authored baseline exists, it composes over a re-authored baseline. The operator's new baseline takes effect, and lived experience stays relative to it. No reconciliation is needed.
- **The JPAF lived profile is absolute.** Transitions are canonical re-weightings (dominant 0.35, auxiliary 0.20, normalised), not increments. Re-applying them as deltas to a changed authored profile would produce a profile Eidos never evaluated. So the lived profile carries `authoredFingerprint`, which is `LivedComposition.fingerprint` of the authored profile it was evolved from. The phase writes it in the same `transition` as the lived profile and the intent.

**Rule.** If the current authored fingerprint differs from the stored one, **the authored edit wins**:

- **Readers, immediately.** `LivedComposition.profile` returns the authored profile, and it is pure, so every reader agrees at once. A term added by an author immediately joins the membership used for recording and probing.
- **[R3] The lived profile goes dormant; it is never deleted (R3-02).** The readers already make a mismatch harmless immediately and purely. A durable deletion would add no correctness, only irreversibility. Rollbacks, YAML reverts and a fixed admin typo would each permanently destroy a month-scale, rate-bounded evolution within one consolidation interval. So:
  - `livedProfile` keeps its stored fingerprint. While the fingerprints differ it is ignored, and it becomes active again by itself if the authored profile returns to the fingerprint it was evolved from. It is overwritten only by the next committed transition.
  - `ReflectionLedger.reauthor = Reauthor(fingerprint, since, confirmed)` tracks the mismatch. It is reconciled by `DispositionEvolutionPhase` at step 0a, **at a due reflection only**: after the wall-clock gate and after the `findById` the reflection already does. Rev 2's per-run `findById` is therefore gone, and §[R] Enumeration cost holds again.

    | Observation at a due reflection | Action |
    |---|---|
    | authored fp ≠ lived fp, and `reauthor` absent or for a different fp | `reauthor := (fp, now, false)`; journal `DispositionReauthored(old, new)` |
    | same mismatch held for ≥ one `reflectionPeriod`, unconfirmed | **confirm**: `signalWriter.clear` (the old epoch's activations were earned under the lived ranking), then `transition(lastTransitionAt := now, confirmed := true)`. Confirmation counts as a transition for the [R] rate bound |
    | authored fp = lived fp again | `reauthor := null`; journal `DispositionReauthorReverted`. If unconfirmed, the signals are intact. If confirmed, the lived profile is active again and the cleared epoch stays cleared, which is an accepted under-count |
    | unconfirmed mismatch, and the reflection yields `Evolved` | `Deferred`, with `eligibleAt = since + P`. Nothing is committed against an authored profile that may still be reverted |

  - **Pending intent.** Under (A) recovery only closes the epoch of a decision that was already committed. Its lived profile, with the old fingerprint, simply turns dormant like any other, so the intent is no longer discarded. That rule was only needed by the deleting design.
  - **Crash safety.** Confirmation runs `clear` before the `transition`, so a crash in between re-runs `clear` at the next due reflection. That is an under-count of at most the activations recorded in that window, and `confirmed` is still false.
- **Boot re-registration** of unchanged YAML yields the same fingerprint, so it is a no-op. That is the property that makes (A) correct under `AgentDescriptorYamlRegistrar`.
- **Scope.** The fingerprint covers the profile's terms and weights only. A vocabulary change with an unchanged profile leaves the lived weighting valid. Only shadow resolution changes, and Eidos applies that at the next probe.

The reviewer's alternative, per-term deltas mirroring PID-5, is rejected for the reason given above: JPAF results are not increments.

**Tests.**
- An authored profile edit after a transition: readers use the authored profile immediately, the next due reflection journals `DispositionReauthored`, and the lived profile is kept dormant. **[R3]** These tests replace rev 2's delete-on-mismatch test:
  - Re-author, then revert within one period: the lived profile is active again, the signals are intact, and `DispositionReauthorReverted` is journaled.
  - Re-author held for one full period: confirmation runs once (`clear`, `lastTransitionAt` reset), and repeated due reflections do not repeat it.
  - Unconfirmed mismatch with an `Evolved` probe: the outcome is `Deferred` and nothing is committed.
  - No `findById` happens on a run where no reflection is due.
- An added authored term is immediately recordable.
- Unchanged YAML re-registration keeps the lived profile.
- A facet re-authoring keeps `promoted` composed over the new baseline.

**Collapse plan when (A) is chosen.** The edit is mechanical:
- Delete §Identity of record and propagation, the (B) promotion block, `pendingPromotions`, the (1b) publication rule, every *(B)* bullet, the [C2] option table, and the eidos#235/#239 prerequisite rows.
- Replace the JPAF pseudocode's `agentRegistry.findById` with `LivedDescriptors.compose`, and step (2) with the lived-profile write in the same `transition` as (1).
- Add step 0a above.
- Un-absorb #1080 (no longer the evolution propagation path; non-ticking agents only).
- Add `LivedComposition`, `LivedProfile`, the snapshot fields and `LivedDescriptors` to §Module placement, and remove `IdentityChangePropagator`.

### [S2] Lived personality state: one owner for all per-agent evolution state

**Defect, verified in code.** `PersonalityState` has two read-modify-write writers on different threads, with no serialisation:
- `SituationalPersonalityParticipant.tick()` runs on the tick thread: `loadOrCreate` → `advance` → `pull` → `persist`.
- `SituationalDeformationPhase.run()` runs on the consolidation thread: `currentState` → `advance` → `persist`.

`persist` is a blind MindMap write followed by `stateCache.put`. `loadOrCreate`'s create path is unguarded, so two concurrent first loads both `addNode`. Before this issue a lost write cost a few self-healing hours of `advance`. Once promotion and the reflection ledger live in this state, a lost write is a permanent identity error: a double-counted promotion or a bypassed budget.

**Fix.** `SituationalStateService` is renamed **`PersonalityStateService`**. It now holds more than situational state: the reflection ledger under both options, and the lived profile under (A). It becomes the sole owner of serialisation, not only of storage:

```java
/** Sole mutation path: per-agent lock; load-or-create, apply fn, version++, persist, replace cache — all under the lock. */
PersonalityState transition(String tenantId, String agentId, Instant now, UnaryOperator<PersonalityState> fn);
/** Read path: cache hit, else load-or-create under the same per-agent lock (first sight is persisted). */
PersonalityState read(String tenantId, String agentId, Instant now);
```

- **No other path.** `persist`, `loadOrCreate` and `currentState` become private. Every writer goes through `transition`:
  - the participant;
  - `SituationalDeformationPhase`;
  - `DispositionEvolutionPhase` (reflection ledger; lived profile under A).

  `DispositionSignalRecorder` only calls `read`.
- **`fn` is pure.** Callers gather evidence (appraisal, mood, descriptor) before calling `transition`.
- **[R3] `fn` derives from `st`, never from a pre-call snapshot (R3-03).** Every field a `transition` does not intend to change is taken from its `st` argument. Values read before the call (`r`, `s`) may serve only as *inputs to a decision*: a condition, or the new value of a field the call means to set. They must never serve as the base object written back. The round-2 disabled branch broke this rule: `st -> st.withReflection(r.advancedBy(…))` wrote back a stale `r` and reverted step D's `decayedThrough`. The only other kind of conditional write, the compensation in step D, compares against `st` (`st.reflection().decayedThrough().equals(marker)`).
  - **Enforcement:** a property test interleaves step D, `closeEpoch`, step 0a, the disabled branch, step 4 and a participant tick in random order. After every run it asserts `decayedThrough ≥ lastReflectionAt`, no field regresses, and `version` strictly increases. A code-review rule flags any `withReflection(` whose argument does not begin with `st.reflection()`.
- **Version-ordered publication.** A persisted monotonic `version` becomes `PersonalityStateSnapshot.stateVersion`, replacing `System.nanoTime()`. `EffectiveCognitiveDefaults` already keeps the higher `stateVersion`, so a snapshot of an older state can never replace a newer one, even when it is published after the lock is released.
- **Robustness additions** (failure atomicity, `TenantAgentKey`, persisted enumeration, eviction, `PersonalityStateSource`) are under §Promotion transaction → [R]. Multi-instance deployments are covered by #1104.
- **One store for all per-agent evolution state.** The reflection ledger is a component of `PersonalityState` (§Reflection ledger), not a separate store. There is then one owner of the `PERSONALITY_STATE` subgraph, one node per agent, one lock and one version. Under (A), the JPAF intent, the lived profile and the ledger are literally one node write, which the [R] JPAF commit ordering relies on.

**Interleaving test.** A participant tick is injected (via a latch inside the mutation) between the deformation phase's load and its commit. After both commit, `promoted + homeOffset` equals the pre-promotion `homeOffset` plus the tick's own drift. Both writers' effects survive, and none is applied twice.

**[R] Robustness evidence for (A).** The round-1 robustness review counted every path by which a lasting change is lost or reverted. Under (B), five independent conditions must all hold for an evolution to survive:

1. eidos#235 lands, with lost-update protection.
2. Boot re-registration preserves evolved fields.
3. Every `CognitionCore.tick` caller re-reads the registry each tick (agency#487 item 4; nothing enforces this).
4. The two-store intent protocols (D8 for PID-5; §JPAF commit ordering for JPAF) never lose an intent.
5. `IdentityChangePropagator` observes every write, including in-memory registries outside JTA.

Under (A), lived state has one durable home: the per-agent `PersonalityState` node, written by one serialized owner (§[S2] `PersonalityStateService.transition`). It is composed over whatever base the tick passes in, so 1–5 are not required. JPAF result and ledger become a single atomic node write, and the two-store crash windows disappear.

(A) still needs the shared prerequisite above: a production `EffectiveCognitiveDefaults` and a real `PersonalityStateSource` (§Production wiring). Under (A), lived personality survives `CognitionCore` re-base, idle eviction and restart by construction. The end-to-end test in §Testing (tick → evict → restart) is written so it fails under any path that loses lived state.

### Disposition-profile evolution (JPAF family)

#### `DispositionEvolutionPhase` (cognition, `cognition.personality`)

`@ApplicationScoped @Priority(50)`. Implements the `mindmap-intelligence` `ConsolidationPhase` SPI, following the precedent of `SituationalDeformationPhase`, `RelationalSchemaEvolutionPhase` (@20), `RelationshipStagePhase` (@18), `DriveAdaptationPhase` (@17) and `BeliefRevisionPhase` (@14). It lives in `cognition` because `cognition` depends on `mindmap-intelligence` (`cognition/pom.xml:66`) and not the other way round.

It injects the Eidos SPIs `DispositionHealth`, `DispositionEvolution`, *(B) only:* `DispositionProfileStore`, and `AgentRegistry`. **[R3]** It never injects `DispositionSignalStore` directly: every signal-store call (decay, clear) goes through `DispositionSignalWriter` (§DispositionSignalRecorder, [R3] Signal writer). It also injects `CbrRecordStore`, `EffectiveCognitiveDefaults` (read-only, for `relationalComplexity`), `PersonalityStateService` (owner of the reflection ledger; see [S2]) and `Clock`.

**`run(tenantId, subgraphPriority)`:**

```
for agentId in effectiveDefaults.agentIds(tenantId):
  try:                                                                   // [R] per-agent isolation
    s = stateService.read(tenantId, agentId, now)                        // persisted on first sight
    r = s.reflection()

    // R. [R2] Recovery: every run, BEFORE the wall-clock gate (R2-04)
    if r.pendingEvolution != null:                                       // committed decision, epoch not yet closed
        (B) profileStore.update(agentId, tenantId, r.pendingEvolution.newProfile)   // absolute, idempotent
            //  (A): nothing to do; the lived profile was written with the intent at (1)
        signalWriter.clear(tenantId, agentId)                            // (3) close the epoch  [R3] via writer
        s = stateService.transition(..., st -> st.withReflection(st.reflection().closeEpoch()))
            // (5) one write: pendingEvolution := null, lastTransitionAt := intent.at,
            //     auditOutbox += intent.case; PERSONALITY_EVOLVED is emitted on this commit
    s = flushAuditOutbox(s)                                              // (4) bounded retries, §Transition audit outbox
    r = s.reflection()

    // G. Wall-clock gate (R2-06)
    if now < r.lastReflectionAt:                                         // clock regressed
        stateService.transition(..., st -> st.withReflection(st.reflection().clampedTo(now)))
        journal.record(ReflectionClockRegressed(...)) once per regression; continue
    n = floor((now - r.lastReflectionAt) / P)
    if n <= 0: continue
    if r.pendingEvolution != null: continue                             // recovery failed above: never probe

    authored = agentRegistry.findById(agentId, tenantId)                 // empty → debug skip, ledger untouched
    descriptor = LivedDescriptors.compose(authored, s)                    // [R2] (A): lived profile; (B): identity
    if descriptor has no dispositionProfile: advance ledger via transition; continue

    // 0a. (A) [R3] Re-authoring: the lived profile goes DORMANT, never deleted (R3-02, §[S3] Authored edits)
    //     Evaluated only at a due reflection, so it costs no per-run findById.
    (s, reauthorPending) = reconcileReauthoring(s, fingerprint(authored), now)   // every write derives from st
        //  mismatch first seen           -> reauthor := (fp, since = now, confirmed = false); journal DispositionReauthored
        //  mismatch held >= P, unconfirmed -> signalWriter.clear; transition(lastTransitionAt := now, confirmed := true)
        //  fingerprint back to lived fp  -> reauthor := null; journal DispositionReauthorReverted
        //  returns true while an unconfirmed re-authoring is pending (step 3 then defers any Evolved)

    // D. [R2] Decay exactly once per period: marker first, then decay (R2-03)
    k = n - floor((r.decayedThrough - r.lastReflectionAt) / P)           // periods not yet decayed, 0..n
    if k > 0:
        prev   = r.decayedThrough
        marker = r.lastReflectionAt + n·P
        s = stateService.transition(..., st -> st.withReflection(st.reflection().withDecayedThrough(marker)))
        try:
            signalWriter.decay(tenantId, agentId, retention ^ k)         // residual counts drain, enabled or not
        catch RuntimeException:                                          // [R3] thrown, not crashed (R3-01)
            stateService.transition(..., st -> st.withReflection(
                st.reflection().decayedThrough().equals(marker)
                    ? st.reflection().withDecayedThrough(prev) : st.reflection()))   // periods stay owed
            rethrow                                                     // per-agent catch; caught up on recovery

    // 0. [C3] Enablement: recomputed every due reflection, never sticky
    rc = effectiveDefaults.restingFor(tenantId, agentId).capacityConfig()?.relationalComplexityOrDefault() ?: 1.0
    if config.l2Ceiling * rc == 0:                                      // evolution-disabled (rc = 0)
        stateService.transition(..., st -> st.withReflection(            // [R3] derive from st, never from r (R3-03)
            st.reflection().advancedBy(n * P).withHalted(false).withDisabled(true)))
        if !r.disabled: journal.record(DispositionEvolutionEnablementChanged(enabled = false, rc))
        outcome Disabled(rc); continue                                  // no probe, no DispositionReflected
    reenabled := r.disabled                                             // cleared by step 4's transition

    // 2. Evaluate: pure, no side effects. [R2] An evaluation exception yields Failed, not a retry loop.
    try:
        status = health.probe(descriptor, REFLECTION_CONTEXT)           // [C2] constant, see "Probe context"
        decision = switch status:
            Aligned            -> Stable                                    (halt := false)
            Drifted d          -> d.magnitude >= l2Ceiling * rc
                                  ? Halted(d.magnitude)                    (halt := true)
                                  : Drifting(d.magnitude)                  (halt := false)
            EvolutionPending p -> switch evolution.evaluate(descriptor, p):
                                    Evolved e  -> Evolved(e, p.type)       (halt := false)
                                    Dampened x -> Dampened(x.decayFactor)  (halt := true)
    catch RuntimeException ex:
        decision = Failed(step, ex.message)                                 (halt := r.halted)

    // 3. Commit: only after the decision is final  [R] intent-first, see "JPAF commit ordering"
    Evolved & reauthorPending:                                            // [R3] (A) unconfirmed re-authoring
              -> Deferred(previousLabel, newLabel, triggerType, eligibleAt = reauthor.since + P)
                 (no commit against an authored profile that may still be reverted)
    Evolved & now - s.reflection().lastTransitionAt < minTransitionInterval:
              -> Deferred(previousLabel, newLabel, triggerType,
                          eligibleAt = s.reflection().lastTransitionAt + minTransitionInterval)
                 (no commit; signals keep decaying; halt := false; no attention signal)   [R] rate bound
    Evolved:  s = stateService.transition(..., st -> st.withReflection(
                      st.reflection().withPendingEvolution(intentId, e.newProfile, case, at = now))
                      (A): .withLivedProfile(e.newProfile, fingerprint(authored)).withReauthor(null))
                                                                          // (1) intent (+ (2) under A)
              (B) profileStore.update(agentId, tenantId, e.newProfile)            // (2) absolute identity write
              signalWriter.clear(tenantId, agentId)                               // (3) close the signal epoch
              s = stateService.transition(..., st -> st.withReflection(st.reflection().closeEpoch()))   // (5)
              s = flushAuditOutbox(s)                                             // (4) best effort, off the critical path
    Dampened: signalWriter.decay(tenantId, agentId, x.decayFactor)

    // 4. Record: Failed advances the ledger too, so a persistent evaluation failure costs one journal entry per period
    stateService.transition(..., st -> st.withReflection(
        st.reflection().advancedBy(n * P).withHalted(halt).withDisabled(false)))   // [R] per [S2]
    if reenabled: journal.record(DispositionEvolutionEnablementChanged(enabled = true, rc))   // [C3]
    journal.record(DispositionReflected(...outcome...))                 // Failed → DispositionEvolutionFailed
    signals: Halted -> PERSONALITY_HALT (0.9) only when r.halted was false   [R] edge-triggered
  catch RuntimeException:                                                // infrastructure failure (state, signal store)
    WARN + personality.evolution.failures; retried next run, which is idempotent (see crash table)
```

**[C2] Probe context.** A consolidation phase has no caller-supplied context. The phase passes the constant `REFLECTION_CONTEXT = CapabilityHealth.ProbeContext.of("personality-reflection")`, which has empty metadata. `DefaultDispositionHealth.probe` never reads its `context` argument: the outcome depends only on the descriptor, the signal counts and tenant preferences. So the constant changes no decision, and parity tests pass the same constant. The domain string only identifies the caller to a future context-sensitive `DispositionHealth`.

**[R] Per-agent isolation.** The body of the per-agent loop runs inside `try/catch (RuntimeException)`. A failure:
- logs WARN with tenant and agent;
- journals `DispositionEvolutionFailed(tenantId, agentId, phase step, message)`;
- increments `personality.evolution.failures`;
- continues with the next agent.

Without this, one agent's exception (for example an Eidos `DispositionValue` validation failure or a registry error) aborts evolution for every later agent of the tenant on every run, because `ConsolidationScheduler.runPhases` catches only per phase. `findById` returning empty (agent deleted, or known only to the explicit layer) is a debug-logged skip that leaves the ledger untouched. It is not an exception.

**[R2] Recovery runs before the wall-clock gate, and resumes at the first incomplete step (R2-04).** `pendingEvolution` exists only between commit step (1) and the epoch close. While it exists, the decision is committed but the signal epoch is still open.
- Recovery runs on **every** run, before the `n` gate: (B)'s absolute identity write, then `clear`, then `closeEpoch`.
- `closeEpoch` is one `transition` that clears the intent, sets `lastTransitionAt` and moves the transition case into `auditOutbox`. `clear` can therefore be re-run only while the intent still exists, that is, until the epoch has closed once.
- Recovery never re-runs after a successful close, so a failing CBR store can no longer cause repeated `clear`s (the R2-04 data-loss path).
- The only re-clear window is a crash between `clear` and `closeEpoch`. It erases only the activations recorded between that crash and the next run, at most one consolidation interval. Those activations sit at the epoch boundary the transition is closing, so this is accepted.
- Probing is blocked only until the epoch is closed, so a failed CBR write no longer freezes the agent.
- A persistent failure of `clear` itself (signal store down) keeps the intent pending. Recording to that same store is failing too, so no additional data is at risk. `DispositionTransitionStalled` is journaled once, when the intent becomes older than one `reflectionPeriod`, and the metric `personality.evolution.intent.age` exposes it.

**[R2] Transition audit outbox (R2-04).** The CBR case is a derived audit record, so it is off the critical path. `ReflectionLedger.auditOutbox` is a list of `AuditEntry(intentId, case, attempts, nextAttemptAt)`. `flushAuditOutbox` runs before the gate on every run, and only for entries whose `nextAttemptAt ≤ now`:
- **Success:** `cbrStore.store(case + feature intent_id)`, then `transition(remove intentId)`.
- **Failure:** `transition(attempts + 1, nextAttemptAt = now + reflectionPeriod)`.
- **Give-up:** at `attempts = maxAuditAttempts` (5), the entry is removed and `DispositionTransitionAuditFailed(intentId, labels)` is journaled. A CBR outage of about 5 periods is therefore tolerated, and the journal keeps the transition auditable.
- **Duplicates:** possible only from a crash between `store` and `remove`, and identifiable by `intent_id`. The guarantee is at-least-once.

**[R] JPAF commit ordering** (revised in [R2]):
1. intent, plus under (A) the lived profile and its fingerprint, in one `transition`;
2. (B) only: absolute identity write;
3. `clear`, which closes the signal epoch;
4. `closeEpoch`: intent cleared, case moved to the outbox;
5. outbox flush.

Rev 2's original order was identity write → CBR → clear. A crash after the identity write and before `clear` makes the next reflection probe the *new* identity with the *old* counts, which can commit a spurious second transition. The intent guards against this, because the phase never probes while an intent exists. *[C2 correction, preserved]* The intent is never cleared in the same write as (1), only after `clear` has succeeded.

**[R2] Decay is exactly once per period, marker first (R2-03).** `ReflectionLedger.decayedThrough` records the end of the last decayed period. Step D computes `k`, the number of periods not yet decayed, and persists `decayedThrough` **before** calling `signalStore.decay(retention^k)`. Retries are therefore harmless:
- An evaluation failure, a failed ledger write or a crash after step D re-enters with `k = 0`, so nothing is decayed twice.
- A probe that throws on every call becomes `ReflectionOutcome.Failed`, which still advances the ledger. A persistent evaluation fault therefore costs one `DispositionEvolutionFailed` entry per period, never a decay per consolidation run.

This is better than the reviewer's decay-then-mark order. With decay-then-mark, a persistent failure of the *marker* write (a MindMap outage) re-decays on every run, which is the same wipe-out scenario moved to a different store. With marker-then-decay, every persistent failure is harmless:
- MindMap down: the marker fails first, and nothing decays.
- **Signal store down for d periods** *[R3 correction, R3-01]*: a *thrown* `decay` is compensated. A `transition` restores the previous `decayedThrough`, but only if the marker is still the one this run wrote, so a concurrent advance is never undone. Those periods therefore stay owed. When the store returns, `k` covers them all, and the counts are decayed by exactly `retention^(d+1)`.
  - Round 2's wording ("the next period's marker covers only that period") was wrong: without compensation, every period of the outage would be skipped permanently. Pressure from before the outage would then be over-retained ×1/retention^d, which is ×3.05 at d = 5, and could commit a transition the wall-clock model says had faded.
  - A caught exception reliably means nothing was decayed. `REQUIRES_NEW` (via `DispositionSignalWriter`) rolls the store's transaction back on the throw, and an exception during commit is the ambiguous case, which degrades to the crash case below.

The remaining cost is the **crash** window between marker and decay: a process death, or a failing compensation `transition` (MindMap failing in the instant between two writes). That run's `k` periods, normally one, are skipped, so pending pressure is retained ×1/retention^k once. It can never compound across runs, and the [R] rate bound still applies.

**[R2] Clock regression (R2-06).** The gate is `n ≤ 0`, not `n == 0`, so a regressed clock can never produce `retention^(negative)` (> 1, which inflates counts) or move the ledger backwards. If `now < lastReflectionAt`, the phase:
- clamps `lastReflectionAt` and `decayedThrough` to `now` in one `transition`;
- journals `ReflectionClockRegressed(previous, now)` once;
- skips the agent for that run.

The same clamp applies on load to `PersonalityState.cursorTime`/`hourCursor`. The integrator is already safe (`advance` loops only while `cursor.isBefore(to)`), but the clamp stops it stalling until wall time catches up.

**[S2] Crash-point table** (revised in [R2]). One failure principle for both families: a cross-store failure may under-count, or retain pending pressure for at most one extra period. It never double-commits a transition, never overshoots committed identity, and never compounds on retry.

| Crash or persistent failure | Effect | Class |
|---|---|---|
| process crash (or failed compensation) after the `decayedThrough` marker, before `decay` | that run's `k` periods (normally 1) are skipped once | one-off over-retention ×1/retention^k; never compounds |
| **[R3]** signal store down for d periods (`decay` throws, MindMap up) | compensation restores `decayedThrough` each time; the periods stay owed | caught up exactly as `retention^(d+1)` on recovery |
| persistent probe/evaluate failure | `Failed` advances the ledger; no repeated decay | one journal entry per period |
| after (1), before `clear` | recovery on the next run; (2) is absolute | retried, idempotent |
| after `clear`, before `closeEpoch` | recovery re-clears, which erases only activations recorded since the crash | boundary under-count, at most one consolidation interval |
| CBR down for days | outbox retries once per period; give-up journals `DispositionTransitionAuditFailed`; reflection continues | audit only; evolution unaffected |
| after `cbrStore.store`, before outbox `remove` | duplicate CBR case, identifiable by `intent_id` | at-least-once audit |

This is the same principle as D8 for PID-5. Structure R2-05 proposed `clear → update` as a simpler order, but the intent ordering is strictly better: it never loses a transition, whereas `clear → update` loses one on a crash between the two steps.

**[R] Transition rate bound.** `minTransitionInterval` (default 30 d) caps committed JPAF transitions at one per agent per interval, independent of event rate. It gates only *when* an `Evolved` result is committed (neocortex's role under D6), and leaves *what* is valid to Eidos. Without the bound, the transition rate depends on traffic. Under default Eidos preferences (δ = 0.06; dominant 0.35, auxiliary 0.20), a swap needs effective(aux) ≥ 0.35, which is about **4 retained auxiliary activations**. A busy agent with ≥ 4 negative interactions in one reflection period (24 h) would therefore swap type daily. See §Calibration.

**[R] Ceiling edge case.** `relationalComplexity` is validated to [0,1] (`CognitiveCapacityConfig`), so `l2Ceiling·rc` can be 0. In that case the agent is **evolution-disabled**: the recorder skips it, the phase skips reflection, and the ledger records `disabled` once and journals it once. Without this, rc = 0 flaps every period: halt, then decay to Aligned, then unhalt, then the next activation halts again, with a signal each time.

**[C3] Enablement is recomputed, not latched.** Step 0 of `run()` re-derives `l2Ceiling·rc` at every due reflection from the agent's current resting `relationalComplexity`.
- **Disable edge.** When the product is 0, the reflection:
  - decays the residual counts;
  - advances the ledger with `disabled = true` and `halted = false`, so a disabled agent is never also halted;
  - skips the probe;
  - yields `ReflectionOutcome.Disabled(rc)`.

  `DispositionEvolutionEnablementChanged(enabled = false, rc)` is journaled only on the false → true edge of `ledger.disabled`. Repeated disabled reflections journal nothing.
- **Re-enable rule.** The phase owns re-enabling. At the first due reflection where rc > 0, it evaluates normally, step 4 clears `disabled`, and the matching `enabled = true` entry is journaled.
- **Recorder.** It reads `disabled` from the ledger, so after rc rises it keeps dropping activations for at most one `reflectionPeriod`, until that reflection runs. This is accepted. Re-reading `restingFor` on the recorder's hot path to close that window would put a CDE derivation into every interaction, and the dropped activations would only have counted from the re-enable onward anyway.

**Halt is not sticky in this model.** Rev 2's drift is Eidos's L2 between the base and the *count-adjusted* effective weights. It measures pending pressure, not applied change. While halted, the recorder drops activations and the counts decay by `retention^n`, so drift falls and the halt clears at a later reflection. The robustness review's sticky-halt and restart-ratchet failure modes applied to rev 1, where drift was measured over applied changes and halt was held in memory.

**[R] Enumeration cost.** `effectiveDefaults.agentIds(tenant)` performs one registry `find(all)` per run. Per-agent work is the cached ledger read, and `findById` happens only for agents whose reflection is due. That is O(registered agents) cheap reads per consolidation plus O(due agents) lookups, which is accepted at current scale (tens of agents per tenant).

This keeps the orchestrator's semantics exactly, which the existing `PersonalityEvolutionOrchestratorTest` scenarios specify (stable, drifting, halted, evolved, dampened). It changes the parts that were wrong:

- **Gate before commit.** `probe` and `evaluate` are pure. The identity write, CBR case and signal clear happen only after the decision is final. The drift ceiling is checked inside the decision, never after a write.
- **Per-family safety in native units.** The L2 ceiling applies to the JPAF effective-weight simplex only, scaled by `relationalComplexity` (Cattell 1971; Halford 1998). It is never combined with facet units. PID-5 safety is in §Safety.
- **Wall-clock reflection grid.** This is the JPAF "reflection at episode boundaries" model with batched periodic probing and a time-based decay anchor (issue-126 D3), and it matches the integrator's hourly-grid pattern. Decay per reflection is `retentionPerReflection`. Missed periods catch up exactly as `retention^n`. Signal half-life is therefore independent of scheduler cadence, idle gating, `consolidateNow` bursts or starvation. A coarse grid, rather than continuous `factor^(Δt/τ)` on every run, is required by the store: `DispositionSignalStore` counts are integers and `JpaDispositionSignalStore.decay` truncates (`(int)(count·f)`), so frequent small decays would wipe signals. eidos#237 tracks moving to fractional weights. Once that lands, the grid could become continuous without any structural change here.
- **Persisted reflection ledger.** `lastReflectionAt` and `halted` are persisted per agent, so a restart neither resets the reflection clock nor clears a halt.

#### Reflection ledger: a component of `PersonalityState` [S2]

There is no separate ledger store. `DispositionEvolutionLedgerStore` and its `evo-ledger:` node from rev 2 are removed. `PersonalityState` gains a `ReflectionLedger reflection` record with these fields:
- `lastReflectionAt` and `halted`;
- **[R]** `lastTransitionAt` (rate bound);
- **[R]** `pendingEvolution` (the intent: absolute new profile, transition-case features, intent id);
- **[R]** `disabled` (rc = 0).
- **[R2]** `decayedThrough` (`Instant`): the end of the last decayed period, so decay happens exactly once per period (R2-03). It is initialised to `lastReflectionAt`. **[R3]** A thrown `decay` restores its previous value (R3-01).
- **[R3]** *(A)* `reauthor` (`Reauthor(fingerprint, since, confirmed)`, nullable): tracks an authored-profile mismatch that has not been confirmed or reverted yet (R3-02). It is encoded as `jpaf.reauthor.*` properties.
- **[R2]** `auditOutbox` (list of `AuditEntry(intentId, case, attempts, nextAttemptAt)`): pending CBR transition cases (R2-04). Encoded as `jpaf.audit.<intentId>.*` properties.
- **[R2]** `inert` (boolean): the edge-trigger memory for `DispositionInputInert` (R2-09). The phase writes it in step 4's `transition`.
  - The per-period counts it is derived from are **not** state. The recorder keeps them in its own in-memory `ConcurrentHashMap<TenantAgentKey, InputCounts>` (two `LongAdder`s: seen and relevant). The phase drains them at each due reflection, so the recorder hot path never touches `PersonalityState`, and §[S2]'s transition-only rule holds.
  - A restart resets the counts, which can only delay the journal entry, never suppress it.
- **[R2]** `pendingEvolution` also carries `at`, the commit time. `closeEpoch` copies it into `lastTransitionAt`, so a delayed recovery does not shift the rate-bound window.

The ledger is persisted as `jpaf.*` properties on the agent's existing `PERSONALITY_STATE` node (`sit-state:`), and is written only through `PersonalityStateService.transition`. The failure-atomicity and `TenantAgentKey` requirements under §Promotion transaction therefore apply to it unchanged.

- **Writer:** `DispositionEvolutionPhase` only.
- **Readers:** the phase, and `DispositionSignalRecorder`. The recorder checks halt through `stateService.read`, which is cache-first.
- **First sight is persisted (structure R2-06).** An agent with no node is created by `read`/`transition` under the per-agent lock, with `reflection.lastReflectionAt = now`, and the node is written immediately. A restart inside the first `reflectionPeriod` keeps the original clock, so a deployment that restarts more often than the period still reflects.
- **One subgraph owner (structure R2-07).** Only `PersonalityStateService` resolves the `PERSONALITY_STATE` subgraph. No second list-then-create resolver exists, so two stores can no longer race to create two subgraphs of the same type. In-process first resolution per tenant is serialised by the existing `computeIfAbsent`. Cross-instance creation is covered by #1104.
- **Why co-located.** The ledger is per-agent lived personality-evolution state, so it belongs with the rest of that state vector (Era 7b decision 1), under the same lock and version. The participant's facet transitions never touch `reflection`, and the JPAF phase never touches facets, so co-location adds no contention beyond the per-agent lock's short critical section.

#### `DispositionSignalRecorder` (cognition, `cognition.personality`)

An `@ApplicationScoped` bean. It replaces `PersonalityEvolutionOrchestrator.record()`. **[C3]** It has two entry points, one per event type, and both feed one shared pipeline:

```
// Entry 1: CDI observer (RelationshipProcessor fires RelationshipRecorded)
@Observes RelationshipRecorded e:
    record(e.event(), e.event().tenantId(), e.event().agentId())

// Entry 2: direct call. CognitionCore.recordInteraction → the recorder injected by
// CognitionCoreFactory via CognitivePipelineBuilder.dispositionSignalRecorder(...)
public void onInteractionAppraised(InteractionAppraised e):
    record(e, e.tenantId(), e.agentId())

// Shared pipeline: identical for both event types
private <E> void record(E ev, String tenantId, String agentId):
  try:
    source = sources.forEventType(ev.getClass())              // at most one per type, see dedup rule
    if source == null || !source.relevant(ev): return          // NEUTRAL short-circuits here,
                                                                // before any state or registry lookup
    s = stateService.read(tenantId, agentId, now); r = s.reflection()
    if r.halted() || r.disabled(): return                      // [C3] disabled (rc = 0) as well as halted
    authored = agentRegistry.findById(agentId, tenantId)       // lazy; empty → debug skip
    descriptor = LivedDescriptors.compose(authored, s)         // [R3] explicit: (A) lived ranking; (B) identity
    terms = []
    for a in source.translate(ev, descriptor):
        if a.functionTerm() in descriptor profile terms: terms += a.functionTerm()
        else: debug-log + personality.signal.dropped{reason=unknown-term}
    signalWriter.recordActivations(tenantId, agentId, terms)   // [R3] per-agent serialised, REQUIRES_NEW;
                                                               // [S2] 3-arg recordActivation: no valence
  catch RuntimeException: WARN + personality.signal.record.failures      // [R] totality, both entries
```

**Why entry 2 is a direct call, not a CDI event.** `CognitionCore` is not a CDI bean, and it fires no CDI events. `CognitionCoreFactory` (`@ApplicationScoped`) builds it and hands it every collaborator, and the recorder is one more collaborator. Introducing CDI events for this one path would create a second wiring style inside `CognitionCore`. The shared private pipeline means both entries get the same `relevant` → halt/disabled → `findById` → membership → totality treatment.

- **Signal units (activation, not valence).** One translated activation adds one count to the term. In `DefaultDispositionHealth.probe`, the effective weight is `normalise(base + count × REINFORCEMENT_DELTA)`, where `REINFORCEMENT_DELTA` is an Eidos tenant preference with default 0.06. No `DispositionSignalStore` honours `SignalValence`: `InMemoryDispositionSignalStore` and `JpaDispositionSignalStore` implement only the 3-arg `recordActivation`, and the 4-arg default drops valence. So every activation *reinforces* its term. `RelationshipPressureSource` maps NEGATIVE to the auxiliary, meaning the auxiliary is engaged under relational strain, as JPAF describes. That is what makes `DOMINANT_AUXILIARY_SWAP` reachable. This is the existing, intended semantics and is kept unchanged. Thresholds are therefore calibrated by the Eidos preferences (`REINFORCEMENT_DELTA`, `OVER_REINFORCEMENT_THRESHOLD`), not by a neocortex magnitude scale.
- **[C3] Two event types, one source each.**
  - `RelationshipRecorded` (CDI) → `RelationshipPressureSource`.
  - `InteractionAppraised` (direct call) → `InteractionPressureSource`.

  `ExperienceRecorded` is **not** observed: `RelationshipRecorded` is derived from it (`RelationshipProcessor.onExperienceRecorded`), so observing both would double-count one experience.
- **Dedup rule.** Each event type in a derivation chain binds to at most one `TraitPressureSource`. The recorder builds a `Map<Class<?>, TraitPressureSource<?>>` at startup and **fails fast** if two sources declare the same `eventType()`. That replaces the orchestrator's order-dependent "first match wins". A future source for a primary event (`ExperienceRecorded`) must exclude experiences that produce a derived `RelationshipRecorded`. #1102 tracks the valenced sources.
- **[R] Totality.** `RelationshipRecorded` is fired synchronously inside `RelationshipProcessor`'s try block, *after* the memory is stored. A synchronous observer exception would skip the remaining observers and be logged there as a misleading "Relationship memory store failed". The recorder is therefore total:
  - The body is wrapped in `try/catch (RuntimeException)`, which logs WARN with tenant and agent and increments `personality.signal.record.failures`.
  - `findById` returning empty is a debug-logged skip.
  - The same applies to the `InteractionAppraised` path below.
- **[R] Live valenced source: `InteractionAppraised`.** Production `RelationshipRecorded` is always NEUTRAL (#1102), but production interactions already carry valence. `CognitionCore.recordInteraction` (`:411-428`) computes a `QualitySignal` for every interaction: the impact-supplied value, else `deriveQualitySignal`, which is mood-based (`:566-581`). Agency calls it in production with `impact = null` (`CognitionAvatarAdapter.recordInteraction` ← `SpeechSession`).
  - `CognitionCore.recordInteraction` emits `InteractionAppraised(tenantId, agentId, subjectId, quality, at)` to the recorder via `CognitivePipelineBuilder.dispositionSignalRecorder(...)`, inside `safeRun`. It does so regardless of `userModelEnabled`.
  - `InteractionPressureSource implements TraitPressureSource<InteractionAppraised>` uses the same JPAF mapping as `RelationshipPressureSource`: POSITIVE activates the dominant, NEGATIVE activates the auxiliary, NEUTRAL is filtered out by `relevant()`.
  - This makes the JPAF path non-inert in production without waiting for #1102.
  - **[R2] Quality is computed independently of `subjectId` (R2-09).** Today quality is derived only inside `if (subjectId != null)` (`CognitionCore:423-429`). The emission moves the computation out of that block, so an interaction with no identified subject still carries valence. The rule is:
    - if `impact.userModelSignal()` is present, use its `quality()`;
    - otherwise use `deriveQualitySignal`.

    `InteractionSignal` is sealed, and every variant exposes `quality()`. The user-model call is unchanged and still requires a subject.
  - **[R2] Stated dependency.** Without an impact-supplied quality, valence comes only from mood. `deriveQualitySignal` returns NEUTRAL when `mood.currentMood` is empty, which is always the case when `CognitionConfig.moodEnabled()` is false. For a tenant with mood disabled and no impact-supplied quality, this source is therefore NEUTRAL by design, and until #1102 JPAF is inert for that tenant. That is acceptable, but it must never be silent:
    - **Counters:** `personality.signal.relevant{source}` and `personality.signal.irrelevant{source}` are incremented at the `relevant()` filter, so an all-NEUTRAL tenant is visible.
    - **Startup WARN:** logged once by `CognitionCoreFactory` when the recorder is wired but `moodEnabled` is false: *"disposition evolution enabled but mood disabled: interaction valence will be NEUTRAL unless impact supplies quality (#1102)"*.
    - **Journal:** at each due reflection the phase drains the recorder's per-agent counts.
      - If the period saw ≥ `inertThreshold` interactions (default 50) and none was relevant, `ReflectionLedger.inert` is set, and `DispositionInputInert(tenantId, agentId, interactions)` is journaled on the false → true edge only.
      - A period with any relevant interaction clears `inert`.
  - Dedup: `InteractionAppraised` and `RelationshipRecorded` are distinct event types, and the latter is NEUTRAL today. When #1102 valences `RelationshipRecorded`, the one-source-per-derivation-chain rule decides which event carries the activation (noted on #1102).
- **[R] Dimension namespace.** Both sources emit terms taken from the descriptor's own `dispositionProfile` (dominant or auxiliary by weight), so their spelling is canonical by construction. The profile-membership check, together with debug log and the counter `personality.signal.dropped{reason=unknown-term}`, guards future sources.
- **Concurrency.** An activation recorded between a reflection's `probe` and its `clear` is consumed by that evolution. This is the intended semantics: the transition closes the signal epoch. Neocortex needs no lock of its own, because the scheduler serialises phase runs under its own lock on one executor thread.
- **[R2] The Eidos signal stores are *not* concurrency-safe today (R1-08; eidos#241).** The rev 2 claim that they were is withdrawn.
  - `JpaDispositionSignalStore.recordActivation` is `em.find` then `count++` or `persist`, and `DispositionSignalEntity` has no `@Version`. Concurrent activations for one term lose increments, and concurrent *first* activations raise a primary-key violation.
  - `decay` is SELECT → mutate → flush, so it overwrites activations committed in between.
  - `InMemoryDispositionSignalStore` races in `decay`, `removeIf` and `clear`, and uses an aliasing `agentId:tenancyId` key.

  Concurrent writers are real: per-turn `InteractionAppraised` from several speech sessions, plus `RelationshipRecorded`, plus the phase's `decay`/`clear`.

  **[R3] Withdrawn: "lost increments only under-count" (round-2 A5/D19 were false; R1-08).** `DefaultDispositionHealth.probe` normalises: `effective(t) = (w_t + c_t·δ) / Σ(w + c·δ)` (`:59-74`). Losing increments on one term therefore *raises* every other term's share.
  - **Counter-example** (verified): profile `ti 0.35, ne 0.20`, rest 0.45, δ = 0.06.
    - True counts `ti 4, ne 4` give effective(ne) = 0.44/1.48 = 0.297, so no swap.
    - Losing the four `ti` increments gives 0.44/1.24 = 0.355 ≥ 0.35, so a spurious `DOMINANT_AUXILIARY_SWAP`.
  - **The losses are biased.** Lost updates concentrate on the hottest row, which is the dominant under positive traffic. So they systematically favour a spurious swap.

  The consequence is that the design must not have lost updates from its own writers. It must not wait for Eidos, and it must not ship the evolution disabled either.
- **[R3] Signal writer: per-agent serialisation plus runtime-neutral isolation (R1-08, R2-05).** Every neocortex access that mutates the signal store goes through one component in `cognition.personality`:

  ```java
  public final class DispositionSignalWriter {          // plain class; produced as a bean per runtime
      DispositionSignalWriter(DispositionSignalStore store, IsolatedTransactions tx);
      void recordActivations(String tenantId, String agentId, List<String> terms);
      void decay(String tenantId, String agentId, double factor);
      void clear(String tenantId, String agentId);
  }
  public interface IsolatedTransactions {               // cognition-api: runtime-neutral port
      void requiresNew(Runnable work);                  // run in a new transaction; never join the caller's
  }
  ```

  - **Per-agent serialisation (R1-08).** Each method takes a per-`TenantAgentKey` `ReentrantLock` and *then* calls `tx.requiresNew(...)`, so the commit happens inside the lock. The next writer for that agent starts only after the previous one has committed, and at READ_COMMITTED its `em.find` sees the committed count. Within one JVM this removes, for every neocortex writer:
    - `JpaDispositionSignalStore`'s lost increments;
    - the concurrent-first-insert primary-key violation;
    - `decay`'s overwrite of in-flight increments;
    - the in-memory store's decay/clear races.

    The recorder, the phase's `decay`/`clear` and the recovery path all go through the writer. Neither the recorder nor the phase injects `DispositionSignalStore`. The single-instance contract (#1104) is the existing deployment assumption. eidos#241 remains the store-level fix for multi-instance deployments and non-neocortex writers. It is not blocking, because neocortex no longer depends on it for correctness.
  - **Cost.** The lock is held for one short transaction (one `find` plus one update or insert). It contends only between concurrent sessions of the **same** agent, and other agents are unaffected. Locks are evicted with idle state (§[R] eviction).
  - **Transaction isolation without proxy self-invocation (R2-05).** Isolation is programmatic, behind the port, so it does not depend on `@Transactional` interception at all. That rules out both failure modes the review found: Spring's proxy bypass on a `this.` call, and ArC's non-interception of private methods.

    | Runtime | `IsolatedTransactions` implementation | Selected by |
    |---|---|---|
    | Quarkus with JTA (narayana) | `JtaIsolatedTransactions(jakarta.transaction.TransactionManager)`: `suspend()` → `begin()` → run → `commit()` (`rollback()` on throw) → `resume()` | `@Produces @DefaultBean` in `CognitionDefaultBeans` when `Instance<TransactionManager>` resolves |
    | Quarkus without JTA | `DirectIsolatedTransactions`: runs inline. No JTA means no outer transaction exists to join or poison | same producer, otherwise |
    | Spring (agency-spring) | `TransactionTemplate` with `PROPAGATION_REQUIRES_NEW` over the application's `PlatformTransactionManager` | `@Bean` in `AgencyAutoConfiguration` (agency#487) |

    `JtaIsolatedTransactions` uses only `jakarta.transaction-api`, a compile-scope dependency of cognition, so cognition gains no Narayana or Spring dependency.
  - **Tests** (§Testing 13):
    - 8 threads × 100 activations on the dominant term give exactly 800.
    - Concurrent first activations do not throw.
    - Concurrent `decay` loses no increment.
    - The counter-example above (dominant increments under concurrency) commits **no** swap.
    - Outer-transaction isolation runs under **both** wirings: a CDI `@QuarkusTest`, and agency's `spring-integration-test`, the latter delivered with agency#487.
- **[R2] Hot-path cost (R2-05).** Each non-NEUTRAL interaction turn costs:
  1. `stateService.read`, which on a cache hit is lock-free and does no I/O;
  2. one `agentRegistry.findById`, an indexed read;
  3. one short isolated JPA write through `DispositionSignalWriter`, serialised per agent ([R3]: it contends only with concurrent sessions of the same agent).

  NEUTRAL turns return at `relevant()` with no I/O. A cache miss loads the node under the per-agent lock (§[S2] `read`). That happens once per agent after 24 h of idleness, or after a restart. The worst case on a miss is one MindMap node read, plus waiting for at most one in-flight `transition` of the *same agent*, whose critical section is one MindMap property write. No lock is taken on the hit path. The halt check deliberately goes through `read` rather than a cache-only peek, because under (A) the same `read` supplies the lived profile that ranks dominant and auxiliary (§(A) lived descriptor). A cache-only peek would rank against the authored profile on every miss, which is exactly the wrong-function defect R2-02 describes.

#### `TraitPressureSource<E>` kept; `TraitActivation` loses its valence [S2]

**Polarity is encoded by target selection, never by a valence flag.** Eidos JPAF is a reinforcement-by-use model. `effective = normalise(base + count × REINFORCEMENT_DELTA)`, and no store honours `SignalValence` (§Signal units). `TraitActivation(functionTerm, SignalValence)` therefore promised a semantics the accumulator does not have. A source that emits `(dominant, NEGATIVE)` meaning "weaken the dominant" would *reinforce* it instead.

`TraitActivation` becomes `TraitActivation(String functionTerm)`. The recorder calls the 3-arg `recordActivation`. A source expresses polarity by choosing **which** profile term to activate. For example, `RelationshipPressureSource` and `InteractionPressureSource` map NEGATIVE to the auxiliary, the engaged function under strain. This rule is recorded on #1102 for future sources.

Signed accumulator weights (the reviewer's alternative) are rejected. They would change Eidos's JPAF theory (functions are reinforced by use, never weakened by signals) inside a storage-format issue. If weakening is ever wanted, it is a JPAF model change with its own design. Whether the Eidos SPI's no-op valence overload and `valenceCounts` are removed is noted on eidos#237 for Eidos to decide.

`TraitPressureSource<E>` keeps its shape: an Eidos `AgentDescriptor` in, `List<TraitActivation>` out. One addition:

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
    double l2Ceiling,                 // drift ceiling on the JPAF weight simplex (default 0.15),
                                      //   scaled by relationalComplexity
    Duration minTransitionInterval    // [R] committed-transition rate bound per agent (default 30d)
) {}
```

Validation (compact constructor):
- `reflectionPeriod` is positive.
- `retentionPerReflection ∈ [0, 1)`. **[R]** 1 is excluded: with no decay, a halted agent's counts never fall, so the halt could never clear.
- `l2Ceiling > 0`.
- **[R]** `minTransitionInterval ≥ reflectionPeriod`.

`defaults()` returns `(24h, 0.8, 0.15, 30d)`.

**Source** *[C3: moved here; covers all four components]*: MicroProfile config, with each key falling back to its `defaults()` value. This follows the `@ConfigProperty` style of the sibling cognition phases, for example `RelationalSchemaEvolutionPhase`.

| Component | Key | Format |
|---|---|---|
| `reflectionPeriod` | `casehub.cognition.personality.reflection-period` | ISO-8601 duration |
| `retentionPerReflection` | `casehub.cognition.personality.retention-per-reflection` | double |
| `l2Ceiling` | `casehub.cognition.personality.l2-ceiling` | double |
| `minTransitionInterval` | `casehub.cognition.personality.min-transition-interval` | ISO-8601 duration |

**[R] Promotion parameters** (`promoteFraction` 0.8, `promoteDwell` 30 d, `promotionBudget` 0.20) are added to `DynamicsConfig`, the integrator's config record. It currently has no validation, so a compact constructor is added. It rejects:
- `promoteFraction ∉ (0, 1]`
- `promoteDwell ≤ 0`
- `promotionBudget ∉ (0, 1]`
- `dMax ∉ (0, 0.5]`
- `sMax ≤ 0`
- `epsilonPublish ≥ promoteFraction·dMax` (a promotable `homeOffset` must also be publishable)
- **[R2]** `promotionBudget < promoteFraction·dMax` (R1-17). A candidate needs `|homeOffset| ≥ promoteFraction·dMax` and `|promoted + homeOffset| ≤ promotionBudget`. With `promoted = 0`, a budget below `promoteFraction·dMax` (for example 0.05 < 0.08) makes every candidate fail the budget test, so promotion is unreachable. That is the rev-1 defect class again. Defaults: 0.20 ≥ 0.08.

Each of these breaks a stated invariant. For example, `promoteFraction > 1` makes promotion unreachable, which is exactly the rev 1 defect.

**[C3] Source of the promotion parameters.** They use the source `DynamicsConfig` already has: the `dynamics:` section of `cognition/src/main/resources/situational-personality.yaml`, parsed by `SituationalPersonalityConfigLoader.parseDynamics`. That method already reads per-key with defaults, for example `tau_setpoint` → `Duration.ofDays(180)`. Three snake_case keys are added in that file's convention:
- `promote_fraction` (double, default 0.8);
- `promote_dwell` (ISO-8601 duration, default `P30D`, parsed like `tau_setpoint`);
- `promotion_budget` (double, default 0.20).

A missing `dynamics:` section still yields `DynamicsConfig.defaults()`, which gains the three defaults. Validation runs in the new compact constructor, so YAML values and defaults are checked by the same rules. The `DynamicsConfig` bean in §Production wiring is `SituationalPersonalityConfig.dynamics()` from this loader.

The two records keep different sources on purpose. `DynamicsConfig` is one section of the situational-personality YAML, alongside the mode, gain and classifier tables it is tuned with. `DispositionEvolutionConfig` is a new four-value record with no YAML home. Neither needs a second configuration mechanism.

`dampeningFactor` is removed. The orchestrator never read it: the dampened path uses `EvolutionResult.Dampened.decayFactor()`, which comes from the Eidos tenant preference `DispositionPreferenceKeys.DECAY_FACTOR`. Dampening strength stays an Eidos-owned preference.

The config is renamed because it is family-specific. A neutral "personality" name would be dishonest about scope.

#### `ReflectionOutcome` (cognition, `cognition.personality`): replaces `EvolutionTick`

A sealed type with the variants `Stable`, `Drifting(magnitude)`, `Halted(magnitude)`, `Evolved(previousLabel, newLabel, newProfile, triggerType)`, `Dampened(decayFactor)`, **[C3]** `Deferred(previousLabel, newLabel, triggerType, eligibleAt)` (an `Evolved` result withheld by the [R] rate bound; nothing committed) and **[C3]** `Disabled(relationalComplexity)` (rc = 0; no probe ran), and **[R2]** `Failed(step, message)` (probe or evaluate threw; the ledger still advances, so a persistent evaluation fault is journaled once per period rather than retried and re-decayed every run). It is the per-agent result of one reflection and is used in the journal entry and in tests. The name is chosen so it does not collide with `io.casehub.eidos.api.DispositionEvolution.EvolutionResult`. `EvolutionTick` (cognition-api) is deleted.

### PID-5 baseline promotion (facet family)

The integrator already owns displacement and `homeOffset`. This issue adds only the final step: graduating **persistent** home offset into the identity baseline. The state owner performs it as part of the same state transition.

#### Promotion rule (hourly grid, inside `PersonalityStateIntegrator`)

`FacetState` gains two fields:

- `saturatedSince` (`Instant`, nullable)
- `promoted` (`double`): cumulative baseline change promoted so far, signed
- **[R2]** `cappedSince` (`Instant`, nullable): set when the facet is a candidate in every respect except `promotionBudget`, and cleared when it no longer is (R2-08)

Both are persisted by `PersonalityStateService.toProperties` / `fromProperties` like the existing fields.

**[C2] `pendingPromotions` (option (B) only; absent under (A)).** This is the durable intent D8's replay depends on. It lives on `PersonalityState`, not `FacetState`, because one intent covers every facet in one `updateFacets` call:
- **Type.** `PendingPromotions(String intentId, Map<String, Integer> absoluteScores)`, or `null`. Keys are canonical AMPD facet names (eidos#239). Values are the absolute 0–100 target scores. Replay therefore needs neither baselines nor name derivation.
- **Encoding.** Properties `pendingPromotion.id = <uuid>` and `pendingPromotion.score.<facet> = <int>`. `fromProperties` reads every key with the `pendingPromotion.score.` prefix. A missing `pendingPromotion.id` means no intent.
- **Writes.** Set at step (1) and cleared at step (3), each inside `transition`. It therefore shares the state's lock, version and failure atomicity. The enumeration-survives-restart requirement guarantees replay after a restart.

At each `closeHour` boundary:

- If `|homeOffset| ≥ promoteFraction · dMax` (default 0.8 · 0.10 = 0.08) and `saturatedSince == null`, set `saturatedSince` to the boundary.
- If `|homeOffset|` falls below the threshold, set `saturatedSince := null`.

`fastForwardIdleHours` applies the same rule. It is evaluated once at the end of the fast-forward, after the closed-form `homeOffset` decay. That is exact, because `|homeOffset|` decays monotonically during idle hours.

`integrator.promotionCandidates(state, baselines, now)` is pure. It returns a `FacetPromotion(facet, delta, targetScore)` for each facet where all of these hold:

- `saturatedSince != null`
- `now − saturatedSince ≥ promoteDwell` (default 30 d)
- `|promoted + homeOffset| ≤ promotionBudget` (default 0.20 on the 0–1 facet scale)

The values are computed as follows:

- *(B)*: `targetScore = round(100 · clamp01(baseline + homeOffset))` (Eidos AMPD scores are integer 0–100), and `delta = targetScore/100 − baseline`, the exact amount the identity write will apply. `baseline` here is the registry baseline, which already includes past promotions, so `promoted` is not added.
- *(A)* *[C3]*: no `targetScore` and no rounding. `delta = clamp01(baseline + promoted + homeOffset) − (baseline + promoted)`, where `baseline` is the authored baseline and `promoted` is a lived component.
- **[S2] Facet-key contract: the identity owner owns it (structure R2-03).** The canonical AMPD facet names are the 13 title-case names already enforced by `AmpdFacetShift.VALID_FACETS`. Neocortex's `PersonalityFacet` constants and `SituationalStateService` keys are the same names. eidos#239 makes Eidos the single owner of the contract: `AmpdFacet` canonicalises its name on construction and on deserialisation, rejects unknown names, and rejects duplicate facets in a descriptor. After that, `EidosCognitiveProfileBridge.titleCase` is a no-op guard, not a load-bearing step.
  - *(A):* no facet write crosses the boundary (promotion moves `homeOffset` into `FacetState.promoted`), so the contract is read-only. #239 is hygiene, not a prerequisite.
  - *(B):* `updateFacets` is keyed by **canonical AMPD names only**, and eidos#239 is a **hard prerequisite** of B. The rev-2 workaround (map each state key to whatever authored spelling `titleCase`s to it) is superseded: it put an identity-boundary contract in the consumer, and it fails silently when two authored spellings collide.
  - Either way, a state facet with no authored counterpart has no baseline to promote into. It is skipped and logged at `FINE`.

**Why these defaults:** `dMax` is 0.10, so any promotion threshold above `dMax` is unreachable. Rev 1's 0.3 could never fire. Sustained near-saturation for a month is the TESSERA criterion: repeated states over a long period, not a transient. The 180-day `tauSetpoint` already treats `homeOffset` as lasting. Promotion makes it *identity*, which is not subject to setpoint decay. The cumulative budget caps lifetime identity drift per facet. Without it, re-saturation after each promotion would allow unbounded drift over years.

#### Promotion transaction (in `SituationalDeformationPhase.run`, per agent)

Ordering is chosen so that every failure under-counts and never double-counts.

**[S2] Under (A)**, one transition, with no identity write and no intent:

```
s = stateService.transition(t, a, now, st -> {
        st = integrator.advance(st, now)
        c  = integrator.promotionCandidates(st, baselines(descriptorView), now)
        return st.applyPromotions(c)          // homeOffset -= delta, promoted += delta, saturatedSince := null
    })
effectiveDefaults.updateState(snapshot(s))    // resting = baseline + promoted + homeOffset: unchanged by promotion
journal / signal as below
```

**Under (B)** (rev 2 with the [R] and [S2] amendments):

```
s = stateService.transition(..., st -> integrator.advance(st, now))
if s.pendingPromotions non-empty:                             // recover an interrupted run
    effectiveDefaults.updateState(snapshot(s))                // [S2] reduced offset visible first
    profileStore.updateFacets(agent, tenant, pending absolute scores)   // idempotent, canonical keys (#239)
    s = stateService.transition(..., st -> st.withPendingPromotions(empty))

baselines = baselines(descriptorView)                         // gathered before the transition (fn is pure)
s = stateService.transition(..., st -> {                      // [S3] candidates computed on the CURRENT state, inside fn
        c = integrator.promotionCandidates(st, baselines, now)
        return st.applyPromotions(c)            // (1) homeOffset -= delta, promoted += delta,
    })                                          //     saturatedSince := null, pendingPromotions := c
candidates = s.pendingPromotions                              // the committed candidates drive (2)
if candidates non-empty:
    effectiveDefaults.updateState(snapshot(s))                // (1b) [S2] publish the REDUCED offset before (2)
    profileStore.updateFacets(agent, tenant, absolute scores) // (2) identity write → propagator → updateBase
    s = stateService.transition(..., st -> st.withPendingPromotions(empty))   // (3) intent cleared
    journal.record(PersonalityFacetPromoted(...)); signal PERSONALITY_EVOLVED (0.8)
for facets blocked only by the budget: [R2] edge-triggered via FacetState.cappedSince, under both options:
    null → set:  journal.record(PersonalityPromotionCapped(...))
    set → null:  journal.record(PersonalityPromotionUncapped(...))
    unchanged:   nothing (a facet that stays capped journals once, not ~288×/day)

effectiveDefaults.updateState(snapshot(s))    // final publication (higher version)
```

**[S2] Publication order (structure R2-02).** Under (B), step (2) fires `AgentDescriptorUpdated`, and outside JTA (the in-memory registry) the propagator runs `updateBase(baseline + δ)` synchronously inside (2). `EffectiveCognitiveDefaults.recompute` carries the existing state snapshot across a base update. If the reduced snapshot had not already been published, derived cognition would compose `(baseline + δ) + h`, an **overshoot** of δ, until the final `updateState`. A failure in (3) or in the journal write would make that overshoot last until the next tick. Publishing the reduced snapshot at (1b) means the only possible transient is `baseline + (h − δ)`, an undershoot, which is consistent with D8. Under (A) the question does not arise: the base never changes and resting is continuous by construction.

- **Continuity.** *[C2] Narrowed.* **Persisted state** is continuous: `(baseline + delta) + (homeOffset − delta) = baseline + homeOffset`. **Derived cognition** under (B) has one bounded transient. Between (1b) and the propagator's `updateBase`, it composes `baseline + homeOffset − delta`, an undershoot of `delta` and never an overshoot. The undershoot lasts until the propagator runs: inside (2) outside JTA, at commit under `AFTER_SUCCESS`, or at the next replay if (2) throws. When (2) throws, the per-agent catch still leaves the reduced state published, because (1b) already ran. Under (A) there is one `transition` and one publication, so derived cognition sees no jump.
- **Failure between (1) and (2).** The resting score is low by `delta` until the next run replays the pending absolute write. That is conservative: identity never overshoots.
- **No double count.** The identity write is absolute, and the state reduction happens before it.
- **[R] Per-agent isolation.** The same try/catch / journal / continue contract as `DispositionEvolutionPhase` applies here. A promotion that fails for one agent cannot stop deformation or promotion for the rest of the tenant.
- **[R] Bounded arithmetic.**
  - *(B)*: `targetScore` is `round(100·clamp01(...))`, so the identity write is always a valid AMPD score.
  - *(A)* and *(B)*: `delta` is computed from the clamped value, so any excess that the clamp cuts off stays in `homeOffset` and is never discarded.
  - Resting composition (`EffectiveCognitiveDefaults.composeFacets`) already clamps to [0,1], so `PersonalityFacet` validation cannot throw.

**[R] Robustness requirements on `PersonalityStateService`.** These are additions to §[S2]'s `transition` primitive, and every writer, including each step of this transaction, goes through `transition`. Steps (1) and (3) above are two `transition` calls, and the identity write (2) runs between them, outside the lock.

- **Failure atomicity.** If `fn` or the persist throws, the cache is untouched, the version is not consumed, and the exception propagates to the caller's per-agent catch.
- **Keys (R1-18).** The lock map, the cache, and the node's stored identity all use a `TenantAgentKey` record. Today's `slotKey = agentId + ":" + tenantId` with `endsWith(":" + tenant)` matching (`SituationalStateService:85-94`, `:192-194`) aliases agent `"x:a"` in tenant `"b"` with agent `"x"` in tenant `"a:b"`.
- **Enumeration survives restart.** `cachedAgentIds(tenant)` is replaced by `agentIds(tenant)`, which reads the persisted `PERSONALITY_STATE` nodes. Each node stores `agentId` as a property. Without this, the cache is empty after a restart and the deformation/promotion phase skips every agent until it next ticks, including any agent with a pending promotion intent, so D8's replay would never run.
- **Cache eviction.** Idle entries (24 h, aligned with `EffectiveCognitiveDefaults.evictIdle`) are evicted together with their unheld lock. This is safe because reads are load-through, and it closes the state-service half of #1089.
- **State source.** `PersonalityStateService` implements `PersonalityStateSource`, and `DefaultPersonalityStateSource` (always empty) is deleted. An evicted or restarted `EffectiveCognitiveDefaults` slot then composes persisted `homeOffset`/`promoted` (and, under (A), the lived profile) instead of silently dropping them (§Production wiring).

**Integrator baseline.** `PersonalityStateIntegrator.baselineFor` currently returns a hard-coded 0.5 when it clamps displacement. Promotion needs real baselines, and so does correct clamping. The integrator therefore takes per-facet baselines from the `DescriptorView`:

- `pull` gets them from the participant's descriptor.
- `promotionCandidates` gets them from `DescriptorViewSource` in the phase.

This is absorbed here because both changes touch the same code.

**Phase ordering.** *[C2]* `SituationalDeformationPhase` gets `@Priority(46)` and `DispositionEvolutionPhase` gets `@Priority(50)`. Both values are unused: `GoalRecognitionPhase` holds 45, and no phase uses 46–69. Today `SituationalDeformationPhase` has no priority and sorts to `Integer.MAX_VALUE`. `ConsolidationScheduler` sorts with a stable comparator over CDI iteration order, so only unique values give a deterministic order.

The requirement is that both phases run **after every phase that reads personality**. Verified readers of `restingFor` are `BehavioralSynthesisPhase` (19), `RelationalSchemaEvolutionPhase` (20), `DriveProfileDerivationPhase` (21), `RecurringThoughtPhase` (25), `SearchBudgetDescriptionGenerationPhase` (28) and `CuriosityDescriptionGenerationPhase` (29). Placing both personality phases after the highest existing phase (45), not just after 29, means future readers in 30–45 need no renumbering. Every phase in a pass then reads one consistent personality, and evolution lands at the end of the pass. The two personality phases touch disjoint state (facets vs. the profile and reflection ledger), so 46 before 50 is a convention, not a dependency.

### Safety (per family, native units)

| Family | Mechanism | Units | Owner |
|---|---|---|---|
| JPAF | `Drifted` halts when its L2 magnitude ≥ `l2Ceiling × relationalComplexity`. Eidos reports over-reinforcement as an ordinary `Drifted`, which goes through the same rule (see below). `Dampened` halts | weight simplex | `DispositionEvolutionPhase`; halt persisted in the ledger |
| JPAF | Halt gates signal recording | – | Read by `DispositionSignalRecorder` |
| PID-5 | `dMax` bounds `homeOffset`; `tauSetpoint` returns it toward 0 | facet scale 0–1 | integrator (existing) |
| PID-5 | Dwell-gated promotion and a cumulative `promotionBudget` per facet | facet scale 0–1 | integrator |

**[C2] Over-reinforcement has no separate branch.** `DefaultDispositionHealth.probe` reports over-reinforcement (dominant effective weight ≥ `OVER_REINFORCEMENT_THRESHOLD`, default 0.50) as `Drifted(effective, mostActivated, computeL2(base, effective))`. That is the same type, with no reason field, so the phase applies the single magnitude rule. Under default preferences this always halts. The dominant term alone contributes ≥ 0.50 − 0.35 = 0.15 to the L2, and the ceiling is `0.15 × rc ≤ 0.15` because rc ∈ [0, 1]. For an authored profile whose dominant base is already near 0.50, over-reinforcement may stay under the ceiling. That is benign, because the profile has barely moved. Neocortex deliberately does not re-derive the threshold: it is an Eidos-owned preference (issue-126 D1), and re-deriving it would duplicate Eidos evaluation.

There is no cross-family drift norm. Weight-simplex deltas and facet-scale offsets cannot be compared, so combining them in one L2 would let one family halt the other.

### Observability

**Journal entries** (`CognitiveEntry`, alongside `SituationalDeformationConsolidated`), so evolution is auditable even when attention is disabled:

- `DispositionReflected(tenantId, agentId, ref, at, outcome, magnitude, previousLabel, newLabel, triggerType)`: one per reflection that runs a probe. `outcome` is the `ReflectionOutcome` variant name: `STABLE`, `DRIFTING`, `HALTED`, `EVOLVED`, `DAMPENED` or **[C3]** `DEFERRED`. For `DEFERRED`, the labels and `triggerType` are those of the withheld transition. A `Disabled` reflection runs no probe, so it writes no `DispositionReflected`.
- **[C3]** `DispositionEvolutionEnablementChanged(tenantId, agentId, ref, at, enabled, relationalComplexity)`: one per edge of `ledger.disabled`, in both directions.
- `PersonalityFacetPromoted(tenantId, agentId, ref, at, facet, delta, newScore, cumulativePromoted)`
- `PersonalityPromotionCapped(tenantId, agentId, ref, at, facet, homeOffset, cumulativePromoted)`: **[R2]** on entry to the capped state only, with `PersonalityPromotionUncapped(tenantId, agentId, ref, at, facet)` on exit (`FacetState.cappedSince` edge)
- **[R2]** `ReflectionClockRegressed`, `DispositionTransitionStalled`, `DispositionTransitionAuditFailed`: each once per event (§JPAF commit ordering, §Clock regression)

**Attention signals.** Two values are added to `io.casehub.neocortex.mindmap.SignalCategory` (mindmap-api). This is the enum used by `ConsolidationPhase.signals()` / `AttentionSignal` and consumed by `ConsolidationScheduler`. The `mindmap.intelligence.SignalCategory` enum is not touched.

| Event | Category | Significance |
|---|---|---|
| JPAF type transition | `PERSONALITY_EVOLVED` | 1.0 |
| PID-5 baseline promotion | `PERSONALITY_EVOLVED` | 0.8 |
| JPAF drift halt | `PERSONALITY_HALT` | 0.9 |

Signal fields. The emitting phase collects the run's signals and returns them from `ConsolidationPhase.signals()`, which already exists as a default method returning `List.of()`.

**[R] Drain on read.** `signals()` swaps out the pending list and returns it, as `ExperienceConsolidationPhase` does (`:137-141`). `ConsolidationScheduler.tick` calls `beginTick()` once and then runs every tenant, calling `signals()` after each tenant's `run`. A phase that clears only in `beginTick()` would therefore leak tenant A's signals into tenant B's batch. `PERSONALITY_HALT` is edge-triggered on the ledger's `halted` false → true transition, so a halted agent emits one signal per halt episode, not one per reflection.

| Field | Value |
|---|---|
| `principalId` | `agentId` |
| `tenantId` | `tenantId` |
| `sourceNodeId` | id of the agent's `PERSONALITY_STATE` node: the `sit-state:` node, for both promotion and JPAF events (the ledger lives on it; [S2]) |
| `sourceName` | `"personality"` |
| `reason` | JPAF transition: `"<previousLabel> -> <newLabel> (<triggerType>)"`; halt: `"drift <magnitude> >= ceiling <l2Ceiling·rc>"`; promotion: `"<facet> baseline <old> -> <new>"` |

Event refs: journal entries use `EventRef.consolidation(EventRef.event("disposition-evolution"))` (JPAF) and `EventRef.consolidation(EventRef.event("situational-deformation"))` (promotion, the existing ref). The propagator's `updateBase` uses `"identity-update"`.

No signal is emitted for ordinary hourly `homeOffset` drift. It changes every hour and belongs in the journal (`SituationalDeformationConsolidated`), not in attention.

### Module placement

| Type | Module | Notes |
|---|---|---|
| `DispositionEvolutionPhase` | cognition (`cognition.personality`) | `ConsolidationPhase` impl; `cognition` → `mindmap-intelligence` |
| `DispositionSignalRecorder` | cognition (`cognition.personality`) | CDI observer |
| `ReflectionLedger` (component of `PersonalityState`) | cognition (`cognition.situational`, with `PersonalityState`) | [S2] replaces `DispositionEvolutionLedgerStore`; persisted on the `sit-state:` node |
| `ReflectionOutcome` | cognition (`cognition.personality`) | replaces `EvolutionTick` |
| `DispositionEvolutionConfig` | cognition-api | replaces `PersonalityEvolutionConfig` |
| `TraitPressureSource.relevant` (default method) | cognition-api | SPI addition |
| Promotion (`FacetState` fields, `promotionCandidates`, baselines) | cognition (`cognition.situational`) | state owner |
| Promotion step, `@Priority(46)` | cognition (`SituationalDeformationPhase`) | |
| `IdentityChangePropagator` | cognitive-eidos | absorbs #1080 *(B only)* |
| **[S3]** *(A)* `LivedComposition`, `LivedProfile` | cognitive-index | the one "authored ⊕ lived" rule; replaces `EffectiveCognitiveDefaults.composeFacets` |
| **[S3]** *(A)* `PersonalityStateSnapshot` + `LivedProfile livedProfile`, `FacetDisplacement.promoted` | cognitive-index | raw lived state; composed in `EffectiveCognitiveDefaults` |
| **[S3]** *(A)* `EidosCognitiveProfileBridge.livedDescriptor(AgentDescriptor, LivedProfile)` | cognitive-eidos | `DispositionValue` ↔ `WeightedTerm`, delegates to `LivedComposition.profile` |
| **[S3]** *(A)* `LivedDescriptors` | cognition (`cognition.personality`) | single Eidos-facing composer for the phase and the recorder |
| **[R]** `InteractionAppraised`, `InteractionPressureSource` | cognition (`cognition.personality`) | live valenced source; emitted by `CognitionCore.recordInteraction` |
| **[R3]** `DispositionSignalWriter` | cognition (`cognition.personality`) | sole neocortex mutator of `DispositionSignalStore`; per-agent serialised |
| **[R3]** `IsolatedTransactions` (port) | cognition-api | runtime-neutral REQUIRES_NEW |
| **[R3]** `JtaIsolatedTransactions`, `DirectIsolatedTransactions` | cognition | CDI implementations; `jakarta.transaction-api` only. The Spring `TransactionTemplate` implementation lives in agency-spring (agency#487) |
| **[R]** `PersonalityStateService`: `TenantAgentKey` keys, persisted `agentIds`, eviction, and the `PersonalityStateSource` impl (on top of §[S2] `transition`) | cognition | single serialised state owner |
| **[R]** `EffectiveCognitiveDefaults`, `PersonalityStateService`, `PersonalityStateIntegrator`, `DynamicsConfig` producers | cognition (`CognitionDefaultBeans`) | first production wiring; `DefaultPersonalityStateSource` deleted |
| Journal entry types | alongside `CognitiveEntry` | |
| `PERSONALITY_EVOLVED`, `PERSONALITY_HALT` | mindmap-api `SignalCategory` | |

### Deletions (no deprecation; there are no external users)

| Removed | Replaced by |
|---|---|
| `PersonalityEvolutionOrchestrator` | `DispositionEvolutionPhase` + `DispositionSignalRecorder` |
| `EvolutionTick` (cognition-api) | `ReflectionOutcome` (cognition) |
| `PersonalityEvolutionConfig` (cognition-api) | `DispositionEvolutionConfig` |
| **[S2]** `TraitActivation.valence` (`SignalValence` component) | nothing: polarity is encoded by target-term selection (D13) |
| **[S2]** `SituationalStateService` (name) | `PersonalityStateService`. Public `persist` / `loadOrCreate` / `currentState` become private behind `transition` / `read` |

The Agency producers of the orchestrator are removed in agency#487, in the same change window.

**Not deprecated:** `DispositionSignalStore`, `DispositionHealth`, `DispositionEvolution`. They remain the JPAF accumulator and evaluator (issue-126 D1, reaffirmed). **[S2]** Neocortex stops using `SignalValence`: `TraitActivation.valence` is removed. The Eidos type itself is Eidos's to keep or remove (eidos#237 comment). `DispositionProfileStore` becomes real (eidos#235).

### [R] Production wiring (in scope; #1060 does not close without it)

#1060 was filed because a fully implemented component had no production caller. Unit tests with hand-wired collaborators cannot be its acceptance gate. These beans are delivered by this issue:

| Bean | Producer | Notes |
|---|---|---|
| `EffectiveCognitiveDefaults` | `@Produces @DefaultBean @Singleton` in `CognitionDefaultBeans` | First production producer. It is built from the explicit `CognitiveDefaultsRegistry`, `EidosDescriptorViewSource`, and `PersonalityStateService` as `PersonalityStateSource`. It is already a required injection point (`CognitionDefaultBeans.cognitiveResourcePool`) and an `Instance<>` point in ≥ 6 phases and in `CognitionCoreFactory`. |
| `PersonalityStateService` (§[S2]), `PersonalityStateIntegrator`, `DynamicsConfig` | `@Produces @DefaultBean @Singleton` (cognition) | The facet-name set comes from the `PersonalityFacet` constants. **[C3]** `DynamicsConfig` is produced as `SituationalPersonalityConfigLoader`'s `dynamics()` (see §DispositionEvolutionConfig, "Source of the promotion parameters"). |
| `SituationalDeformationPhase` | `@ApplicationScoped @Priority(46)` | This is pulled forward from #1082, because promotion and integrator advance must run in production even before the participant is registered. `agentIds` reads persisted nodes, so an empty cache is fine. |
| `DispositionEvolutionPhase`, `DispositionSignalRecorder`, `InteractionPressureSource` | `@ApplicationScoped` (cognition, Jandex-indexed) | The phase is discovered by `ConsolidationScheduler`'s `Instance<ConsolidationPhase>`. |
| Recorder → `CognitionCore` | `CognitionCoreFactory` → `CognitivePipelineBuilder.dispositionSignalRecorder(...)` | Feeds `InteractionAppraised`. |
| **[R3]** `DispositionSignalWriter`, `IsolatedTransactions` | `@Produces @DefaultBean @Singleton` in `CognitionDefaultBeans`: `JtaIsolatedTransactions` when `Instance<TransactionManager>` resolves, otherwise `DirectIsolatedTransactions` | Injected into the recorder and both phases. On Spring, `AgencyAutoConfiguration` supplies a `TransactionTemplate(PROPAGATION_REQUIRES_NEW)` implementation (agency#487) |

#1082 keeps the participant's registration in `CognitionCore`, which is blocked on eidos#234. Spring wiring is agency#487.

### [R] Deployment assumptions

ASSUMPTION: One active neocortex instance per tenant. `ConsolidationScheduler.knownTenants`, `SignificanceAccumulator`, the `EffectiveCognitiveDefaults` slots, and the per-agent locks in `PersonalityStateService` (the ledger has no lock of its own since [S2]) all assume this. Two instances would split events across nodes and fork evolution. neocortex#1104 documents the contract and the options if that ever changes.

### [R] Calibration (wall-clock, default parameters)

**JPAF.** Each reflection is one 24 h period. A swap needs about 4 retained auxiliary activations. Decay is ×0.8 per period, truncated to an integer.

| Sustained negative-interaction rate | Earliest swap | Next transition |
|---|---|---|
| ≥ 4 per period | next reflection (≤ 24 h) | ≥ 30 d later (`minTransitionInterval`) |
| ~1–3 per period | a few periods: retained counts climb, since for c ≤ 5 `(int)(c·0.8)` loses exactly 1 per period | ≥ 30 d later |
| sporadic (≤ 1 per several periods) | never (truncation returns 1 → 0) | — |

The type-change rate is therefore bounded at ≤ 1 per 30 d by construction. Time to the *first* change is governed by Eidos preferences (`REINFORCEMENT_DELTA`) and the source's event granularity. Interaction-turn granularity is fine-grained; tenants that want slower first transitions tune δ (eidos preference). eidos#237 (fractional counts) removes the truncation cliff.

**PID-5.**
- Saturation requires `|homeOffset| ≥ 0.08` with `dMax = 0.10`. Reaching it takes hours to days at `sMax` displacement (#712 dynamics).
- Promotion requires 30 d of continuous saturation.
- Each promotion applies at most the current `homeOffset`, which is ≤ 0.10.
- The cumulative budget is 0.20.

So identity change per facet is ≥ 30 d per step, and ≤ 0.20 per lifetime.

All gates are wall-clock: reflection grid, interval, dwell, and integrator hours. Consolidation cadence (idle gating, `consolidateNow` bursts, #1063 starvation) affects latency only, never rate.

### Prerequisites and sequencing

| Dependency | Kind | Effect if absent |
|---|---|---|
| casehubio/eidos#235: registry-backed `DispositionProfileStore` + `updateFacets` *[depends on R1-01]* | (B): **Hard.** Lands first, and must also preserve evolved fields across boot re-registration. (A): not required | (B): every identity change is discarded (NoOp) |
| **[C2]** Production `EffectiveCognitiveDefaults` producer and real `PersonalityStateSource` (Problem 5) | **In scope** (§Production wiring), not external | Correct evolution reaches nothing in production; evicted or restarted slots lose lived state |
| #1063: scheduler starvation and restart tenant loss | **Hard for production effect** | Both phases are cadence-invariant (wall-clock grids with exact catch-up), so they are *correct* under any schedule. But they *never run* for busy deployments or unregistered tenants |
| #1082: situational participant registration | **Hard for PID-5 promotion in production** | Without the participant there is no displacement, so `homeOffset` never saturates. **[R]** The state service, integrator, deformation phase and promotion are production-wired by this issue, and only the displacement source remains in #1082 |
| #1102: valenced relationship and goal-outcome signals | **[R] Not blocking** (was: hard for JPAF non-inertness) | `InteractionAppraised` from `CognitionCore.recordInteraction` carries live production valence. #1102 adds further valenced sources |
| casehubio/agency#487: remove orchestrator producers, wire the new beans | Same change window | Agency fails to compile |
| casehubio/eidos#237: fractional activation weights | Not blocking | Integer truncation biases low counts; the reflection grid limits the damage |
| **[R2]** casehubio/eidos#241: signal-store concurrency (atomic upsert, bulk decay, `REQUIRES_NEW`, in-memory races and keys) | Not blocking **[R3]** | Neocortex's own writers are serialised per agent by `DispositionSignalWriter`, so a single-instance deployment has no lost updates. #241 covers multi-instance (#1104) and non-neocortex writers. The round-2 "only under-counts" rationale is withdrawn: under normalisation, a lost increment can *cause* a swap |
| **[S2]** casehubio/eidos#239: canonical `AmpdFacet` names | **Hard under (B)**; hygiene under (A) | (B): `updateFacets` keyed by an uncanonicalised name appends a duplicate facet or misses the stored spelling |

**What #1060 closes:** the structural defect. Evolution is evaluated on a durable wall-clock cadence. Its result is committed to one store of record, which R1-01 chooses. It reaches `EffectiveCognitiveDefaults` through one path for both families. *[C2]* That path exists in production only because this issue also delivers the `EffectiveCognitiveDefaults` producer and a real `PersonalityStateSource` (Problem 5, §Production wiring).

**What it does not close:** additional valenced sources (#1102), scheduler starvation (#1063), and the situational participant's registration (#1082). Those are tracked separately because their causes are upstream of evolution.

**[R] Close criterion.** #1060 closes when the production-wiring test and the end-to-end test (§Testing, items 7–8) pass against real CDI beans:
- a real `CognitionCore.recordInteraction` produces a changed `EffectiveCognitiveDefaults.forAgent()`;
- that change survives a following tick, idle eviction, and a restart.

### Testing strategy

1. **`DispositionEvolutionPhase` unit tests** (Eidos SPIs as test doubles):
   - Behavioural parity with every `PersonalityEvolutionOrchestratorTest` scenario: stable, drifting, halted (with `relationalComplexity` scaling), evolved (profile write, CBR `trigger_type` = JPAF type, signal clear), dampened.
   - The gate-before-commit property: no `profileStore` or `cbrStore` interaction on a Halted or Drifting outcome.
   - The reflection grid: no reflection before the period; `retention^n` on catch-up after n missed periods; the result is independent of how many `run` calls happen within one period.
   - The ledger: halt survives a store reload; `lastReflectionAt` advances by whole periods.
   - **[C3]** `Deferred`: an `Evolved` result inside `minTransitionInterval` commits nothing, writes `DispositionReflected(DEFERRED, …)` with the withheld labels, emits no signal, and leaves `halted = false`.
   - **[C3]** `Disabled`: at rc = 0 there is no probe; counts decay; `disabled` is set with exactly one `enabled = false` entry, even over several reflections. When rc later rises above 0, the next due reflection probes normally, clears `disabled` and journals one `enabled = true`.
2. **`DispositionSignalRecorder` unit tests:**
   - NEUTRAL produces no registry lookup.
   - Halted produces no activation.
   - A term not in the profile is dropped and logged.
   - Startup fails on duplicate `eventType()` sources.
   - `ExperienceRecorded` is not observed.
   - **[C3]** Each case above is also run through the `onInteractionAppraised` entry: NEUTRAL `InteractionAppraised` does no state or registry lookup, a halted agent records nothing, and an unknown term is dropped.
   - **[C3]** A disabled agent (`reflection().disabled()`) records nothing on either entry.
   - **[C3]** A throwing source or registry, on either entry, does not propagate. `recordInteraction`'s `safeRun` and `RelationshipProcessor`'s other observers are unaffected.
3. **Integrator promotion tests:**
   - The dwell clock starts and resets across hour boundaries and idle fast-forward.
   - No candidate before the dwell; a candidate after it.
   - The budget cap blocks promotion and journals it.
   - *(B)*: `delta` matches integer rounding exactly. *(A)* *[C3]*: `delta` equals the clamped transfer exactly, with no rounding.
   - Continuity: the resting facet is identical before and after promotion.
   - Baselines replace the hard-coded 0.5 in clamping.
4. **`SituationalDeformationPhase` promotion tests** *[(B) as written; (A) per the [C2] option table]*:
   - The ordering persist(intent) → `updateFacets` → persist(clear).
   - Crash recovery: a pending intent is replayed idempotently on the next run.
   - No double count when the identity write is replayed.
5. **`IdentityChangePropagator` tests** *[(B) evolution path; under (A), non-evolution registry updates only]*:
   - `AgentDescriptorUpdated` → `updateBase` with the current descriptor's view.
   - Not invoked on rollback (`AFTER_SUCCESS`).
6. **Integration** (in-memory Eidos registry and stores, synthetic valenced `RelationshipRecorded`):
   - Events → activations → reflection → `Evolved` → registry descriptor changed → `EffectiveCognitiveDefaults.forAgent` reflects the new dominant function.
   - A following simulated `CognitionCore` tick with a registry-sourced descriptor does **not** revert it.
   - PID-5: sustained displacement over simulated weeks → saturation → promotion → registry `ampdFacets` updated → effective facet continuous across the promotion.
   - **[R]** Uses the real `DefaultDispositionHealth`/`DefaultDispositionEvolution`, not mocks. `PersonalityEvolutionOrchestratorTest` mocks both, so "parity" with it specifies orchestration only.
7. **[R] CDI production-wiring test (`@QuarkusTest`).** It must show all of the following:
   - `EffectiveCognitiveDefaults` resolves, and its `PersonalityStateSource` is `PersonalityStateService`.
   - `ConsolidationScheduler.manifest()` lists `disposition-evolution` and `situational-deformation`.
   - A `CognitionCoreFactory`-built core has the recorder wired.
   - No `DescriptorViewSource` or `PersonalityStateSource` is a stub.
8. **[R] End-to-end, production beans, controllable clock.**
   1. Drive `CognitionCore.recordInteraction` with forced-negative mood across reflection periods.
   2. Consolidation runs and `forAgent()` shows the swapped type label.
   3. A subsequent `CognitionCore.tick`, `evictIdle`, and a fresh service/EDC instance over the same stores each still show the change. This is the store-of-record regression test, and it must pass under whichever option is chosen.
   4. Exactly one CBR transition case and one `PERSONALITY_EVOLVED` signal are produced.
   5. A second transition is deferred until `minTransitionInterval` has passed.
9. **[R] Robustness unit tests.** These cover:
   - **Commit failures:** a crash injected after each JPAF commit step (1)–(5) and after each promotion step leaves no spurious second transition, no double count, and no lost intent. CBR failure leaves the intent to be retried.
   - **Per-agent isolation:** a throwing agent does not stop later agents.
   - **Recorder totality:** a throwing source or registry call does not propagate out of `RelationshipProcessor`, `recordInteraction`, or the remaining observers.
   - **State concurrency:** concurrent participant and phase `update`s on one agent lose nothing, and versions strictly increase.
   - **Key isolation:** `TenantAgentKey` isolation for the `"x:a"`/`"b"` vs `"x"`/`"a:b"` case.
   - **rc boundary:** rc = 0 disables evolution without flapping.
   - **Halt signal:** fires once per halt episode.
   - **Signal drain:** `signals()` across two tenants in one tick has no cross-tenant carry-over.
   - **Config:** every validation rule in both config records.
   - **Promotion boundary:** a facet at 0.95, so the clamp limits the target and the excess stays in `homeOffset`.
10. **[S2] Structure round-2 tests:**
    - **Interleaving (R2-01):** a participant tick is latched between the deformation phase's load and its commit. Afterwards, `promoted + homeOffset` equals the pre-promotion offset plus the tick's own drift, with no double count and no lost `promoted`.
    - **First-sight race:** two concurrent first `read`s of a new agent create exactly one node.
    - **Publication order (R2-02, option B):** sample `restingFor` after every step of the promotion transaction, including with (3) forced to throw. It never exceeds the pre-promotion resting score.
    - **Ledger across restart (R2-06):** first sight, then a restart at 0.5 × `reflectionPeriod`, then another restart. The reflection fires one period after the *original* first sight.
    - **Single subgraph (R2-07):** concurrent first use by the participant and `DispositionEvolutionPhase` for a new tenant yields exactly one `PERSONALITY_STATE` subgraph.
    - **No valence (R2-04):** `TraitActivation` has no valence component. A NEGATIVE relationship increments the auxiliary's count, never decrements the dominant's.
    - **Facet keys (R2-03, option B):** `updateFacets` is called only with names in the canonical AMPD set.
11. **[S3] Structure round-3 tests:**
    - *(A)* **One composer (R3-03):** the phase's probed descriptor, the recorder's ranking descriptor and `forAgent()` expose the same profile for: no lived profile, a matching lived profile, and a stale lived profile.
    - *(A)* **Authored edits (R3-02):** an edit after a transition makes readers use the authored profile at once. **[R3]** The lived profile turns dormant, not deleted. It reactivates on revert, and a mismatch held for one period confirms once (§[S3] Authored edits tests). An added authored term is recordable. Unchanged YAML re-registration keeps the lived profile. A facet re-authoring keeps `promoted` over the new baseline.
    - *(B)* **Candidates on current state (R3-04):** a participant tick that lowers `|homeOffset|` below the threshold between the advance `transition` and the promotion `transition` yields no promotion.
12. **[R2] Robustness round-2 tests:**
    - **Exactly-once decay (R2-03):** `probe` throws on 10 consecutive runs within one period. Counts are decayed exactly once, the ledger advances with `Failed`, and one `DispositionEvolutionFailed` is journaled. A failing `decayedThrough` transition (MindMap down) applies no decay at all.
    - **Recovery and outbox (R2-04):**
      - CBR fails for 3 consecutive periods. Activations recorded after the transition survive, reflection resumes once the epoch is closed, and exactly one CBR case lands after recovery.
      - After `maxAuditAttempts` failures the entry is dropped and `DispositionTransitionAuditFailed` is journaled.
      - A crash between `clear` and `closeEpoch` re-clears only once.
      - Recovery runs on a run where `n = 0`.
    - **Clock regression (R2-06):** set the clock back by 2 periods. There is no decay with factor > 1, `lastReflectionAt` never moves backwards, and exactly one `ReflectionClockRegressed` is journaled.
    - **Signal-store concurrency (R1-08):** superseded by §Testing 13. With the [R3] writer, counts are exact, not a lower bound.
    - **Transaction isolation (R2-05):** superseded by §Testing 13, which runs under both the CDI and the Spring wiring.
    - **Hot path (R2-05):** a cache-hit interaction acquires no per-agent lock.
    - *(A)* **Lived-descriptor consumers (R2-02):**
      - After a lived `TI-NE → NE-TI` swap, a NEGATIVE interaction increments the lived auxiliary `ti`.
      - The second transition's CBR case has `old_dominant = ne`.
      - Promotion with authored 0.85, promoted 0.10 and `homeOffset` 0.09 promotes 0.05 and leaves 0.04 in `homeOffset`.
    - *(A)* **Continuity (R2-01):** `restingFor` is sampled immediately before and after the promotion `transition`. The values are equal to 1e-9 for every facet. The JPAF analogue: `forAgent()` changes type label exactly at the commit of step (1), and at no other step.
    - **Per-option replacements for items 4 and 6.**
      - *(A)* Item 4: the promotion is one `transition`, with no `DispositionProfileStore` interaction (the phase has no such injection point under (A)) and no `pendingPromotions`.
      - *(A)* Item 6: assert `PersonalityState.livedProfile`, `FacetState.promoted` and `forAgent()`, never registry `dispositionProfile`/`ampdFacets`.
      - *(B)* Items 4 and 6 as written.
      - Item 8 is unchanged and must pass under both options.
    - **Budget invariant (R1-17):** `DynamicsConfig` with `promotionBudget = 0.05`, `promoteFraction = 0.8`, `dMax = 0.10` is rejected.
    - **Capped edge (R2-08):** a facet that stays capped for 48 simulated hours journals `PersonalityPromotionCapped` exactly once, and `PersonalityPromotionUncapped` once on exit.
    - **Inert input (R2-09):** with mood disabled, there is one startup WARN, the `personality.signal.irrelevant{interaction}` counter increments, and one `DispositionInputInert` is journaled per inert episode.
13. **[R3] Robustness round-3 tests:**
    - **Writer serialisation (R1-08):**
      - 8 threads × 100 activations on one term, against the real `JpaDispositionSignalStore`, give **exactly** 800.
      - Concurrent first activations do not throw.
      - `decay` concurrent with activations loses no increment.
      - **Normalisation counter-example:** profile `ti 0.35, ne 0.20`, rest 0.45. 4 `ti` and 4 `ne` activations from concurrent threads, then a reflection: no `DOMINANT_AUXILIARY_SWAP`, because effective(ne) = 0.297.
    - **Transaction isolation (R2-05), under both runtimes:**
      - A CDI `@QuarkusTest` and agency's `spring-integration-test` (agency#487) each open an outer transaction, call `recordInteraction`/fire `RelationshipRecorded` with a forced signal-store failure, and assert the outer transaction commits.
      - A unit test asserts that `DispositionSignalWriter` calls `IsolatedTransactions.requiresNew` for every store call, with no reliance on interception.
    - **Signal-store outage (R3-01):** `decay` throws for 5 consecutive due reflections, then succeeds. `decayedThrough` is unchanged across the outage, and the counts equal `(int)(c·0.8^6)`. A compensation `transition` forced to fail loses exactly that run's `k` periods.
    - *(A)* **Dormant re-authoring (R3-02):** the four cases under §[S3] Authored edits tests.
    - **No stale write-back (R3-03):** the [S2] interleaving property test. A disabled agent decays exactly once per period across 10 disabled reflections and on re-enable.

## Decisions

See `decisions.md`. *[C3: complete index]*

| Decision | Subject | Origin |
|---|---|---|
| D1–D2 | Signal recording and evaluation cadence | rev 1 |
| D3–D6 | Propagation, PID-5 scope, signal model, architecture | rev 1, revised in rev 2 |
| D7 | Safety policy | rev 2 |
| D8 | Failure ordering for PID-5 promotion | rev 2; generalised by [S2] to both families and the derived view |
| D9 | JPAF commit ordering and transition rate bound | [R] |
| D10 | Single serialised owner of situational/lived state | [R] |
| D11 | Production wiring in scope; live valenced source | [R] |
| D12 | Reflection ledger is a component of `PersonalityState` | [S2] |
| D13 | Polarity encoded by target selection; `TraitActivation` loses valence | [S2] |
| D14 | The identity owner owns the facet-key contract | [S2] |
| D15 | *(A)* One owner of "authored ⊕ lived": `LivedComposition` | [S3] |
| D16 | *(A)* Authored edits win over the lived JPAF profile (fingerprint) | [S3] |

The store-of-record choice (R1-01) is deliberately not a numbered decision until the human makes it.

## References

- `PersonalityEvolutionOrchestrator.java`, `PersonalityEvolutionOrchestratorTest.java`: the behaviour being replaced and its specification
- `PersonalityStateIntegrator.java`, `SituationalDeformationPhase.java`, `SituationalStateService.java`, `FacetState.java`, `DynamicsConfig.java`: PID-5 state owner
- `EffectiveCognitiveDefaults.java`, `CognitionCore.java:288-291`, `EidosDescriptorViewSource.java`: base layer and its owner
- Eidos `DefaultDispositionHealth.java`, `DefaultDispositionEvolution.java`, `JpaDispositionSignalStore.java`, `JpaAgentRegistry.java` (`register` → `AgentDescriptorUpdated`), `AgentRegistry.updateGoalLifecycleState` (read-modify-register precedent)
- `RelationshipProcessor.java`, `RelationshipPressureSource.java`: the signal source and why it is NEUTRAL
- `ConsolidationScheduler.java`: `@Priority` ordering, single-thread lock
- `docs/specs/issue-126-autonomous-agent-patterns/decisions.md`: D1 (keep the Eidos JPAF pipeline), D2 (vocabulary-generic profile terms), D3 (batched periodic reflection)
- `docs/research/era7-personality-trait-integration-research.md`: Era 7b key decisions (one model; wall-clock grid)
- casehubio/neocortex#712, #1055, #1063, #1080, #1082, #1089, #1102, #1104; casehubio/eidos#234, #235, #237, #239; casehubio/agency#487
