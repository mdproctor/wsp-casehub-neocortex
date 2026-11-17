# Unified Personality Evolution

**Issue:** casehubio/neocortex#1060
**Refs:** #712 (situational modulation, Era 7b), #1055 (EffectiveCognitiveDefaults), #126 (JPAF orchestrator), #1080 (absorbed)
**Prerequisites:** casehubio/eidos#235, #1082, #1063 (see §Prerequisites)
**Follow-ups:** #1102, #1104 (single-instance deployment contract), casehubio/agency#487, casehubio/eidos#237
**Date:** 2026-11-17 (rev 2, after the round-1 structure review; robustness amendments marked **[R]**, after the round-1 robustness review)

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
  - The *result* is stored in neocortex lived state, next to `homeOffset`. Neocortex supplies the `DispositionProfileStore` implementation. It writes the evolved profile into the per-agent `PersonalityState` node (property `profile.<term>.weight`), through `SituationalStateService` under the same per-agent state transition as the integrator.
  - The phase probes with the **lived descriptor**: the authored descriptor with the lived profile substituted.
  - PID-5 promotion moves `homeOffset` into the non-decaying `FacetState.promoted` component, which is already introduced above. It is not written to Eidos.
  - `EffectiveCognitiveDefaults` composes `authored ⊕ lived` (lived profile replaces authored weights; resting facet = `baseline + promoted + homeOffset`). The per-tick authored `updateBase` from `CognitionCore` becomes correct by construction, because `recompute` carries the state snapshot across base updates.
  - What this removes: the two-store intent/replay protocol, the registry lost-update locking (eidos#235 item 3), `IdentityChangePropagator`'s role in evolution, and the boot defect.
  - What it costs: Eidos consumers that read `AgentRegistry` directly, such as the agency prompt section, must read lived personality from `EffectiveCognitiveDefaults`. That goes into agency#487.
  - It matches the #712 layering, where the personality state vector modulates between the identity store and the CDE (Era 7b decision 1, "one model": a single continuously evolving state vector).
- **(B) Registry stays store of record; Eidos separates authored from evolved.** eidos#235 is extended so that re-registration preserves evolved `dispositionProfile`/`ampdFacets`, or so that an evolved layer is stored separately and composed in `findById`. This keeps every `AgentRegistry` reader seeing lived identity. The costs:
  - an authored/evolved split is still built, just inside the registry;
  - cross-store promotion stays crash-sensitive, because neocortex `promoted` and Eidos `ampdFacets` must agree;
  - registry write contention remains.

Until this is decided, the propagation table above is correct only for an uninterrupted process lifetime.

**[S2] Structure-review evidence for the decision.** Round 2 of the structure review raised five findings. Four of them come from evolution results crossing a store boundary: R2-01 (cross-store double count), R2-02 (publication order across two layers), R2-03 (facet-key contract on writes) and R2-05 (three-store JPAF commit).

- **Under (A):** every evolution result commits in **one** `PersonalityStateService.transition` (§Lived personality state). The only remaining cross-store step is clearing the Eidos signal store, and it is ordered so that a failure under-counts.
- **Under (B):** each of those findings needs its own protocol (intent/replay, ordered publication, canonical-key writes, registry locking). Those protocols are specified below for (B), but they are cost that (A) does not pay.

Structure therefore also recommends **(A)**. It is the option with one owner per kind of data:
- **Eidos** owns *authored* identity. Boot re-registration from YAML is then correct by construction.
- **Neocortex** owns the *lived* personality state vector (Era 7b decision 1).

Wherever a protocol below differs between the options, it is tagged *(A)* / *(B)*.

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
- **Version-ordered publication.** A persisted monotonic `version` becomes `PersonalityStateSnapshot.stateVersion`, replacing `System.nanoTime()`. `EffectiveCognitiveDefaults` already keeps the higher `stateVersion`, so a snapshot of an older state can never replace a newer one, even when it is published after the lock is released.
- **Robustness additions** (failure atomicity, `TenantAgentKey`, persisted enumeration, eviction, `PersonalityStateSource`) are under §Promotion transaction → [R]. Multi-instance deployments are covered by #1104.
- **One store for all per-agent evolution state.** The reflection ledger is a component of `PersonalityState` (§Reflection ledger), not a separate store. There is then one owner of the `PERSONALITY_STATE` subgraph, one node per agent, one lock and one version. Under (A), the JPAF intent, the lived profile and the ledger are literally one node write, which the [R] JPAF commit ordering relies on.

**Interleaving test.** A participant tick is injected (via a latch inside the mutation) between the deformation phase's load and its commit. After both commit, `promoted + homeOffset` equals the pre-promotion `homeOffset` plus the tick's own drift. Both writers' effects survive, and none is applied twice.

**[R] Robustness evidence for (A).** The round-1 robustness review counted every path by which a lasting change is lost or reverted. Under (B), five independent conditions must all hold for an evolution to survive:

1. eidos#235 lands, with lost-update protection.
2. Boot re-registration preserves evolved fields.
3. Every `CognitionCore.tick` caller re-reads the registry each tick (agency#487 item 4; nothing enforces this).
4. The two-store intent protocol (D8, plus the JPAF equivalent below) never loses an intent.
5. `IdentityChangePropagator` observes every write, including in-memory registries outside JTA.

Under (A), lived state has one durable home: the per-agent `PersonalityState` node, written by one serialized owner (§[S2] `PersonalityStateService.transition`). It is composed over whatever base the tick passes in, so 1–5 are not required. JPAF result and ledger become a single atomic node write, and the two-store crash windows disappear.

(A) still needs the shared prerequisite above: a production `EffectiveCognitiveDefaults` and a real `PersonalityStateSource` (§Production wiring). Under (A), lived personality survives `CognitionCore` re-base, idle eviction and restart by construction. The end-to-end test in §Testing (tick → evict → restart) is written so it fails under any path that loses lived state.

### Disposition-profile evolution (JPAF family)

#### `DispositionEvolutionPhase` (cognition, `cognition.personality`)

`@ApplicationScoped @Priority(50)`. Implements the `mindmap-intelligence` `ConsolidationPhase` SPI, following the precedent of `SituationalDeformationPhase`, `RelationalSchemaEvolutionPhase` (@20), `RelationshipStagePhase` (@18), `DriveAdaptationPhase` (@17) and `BeliefRevisionPhase` (@14). It lives in `cognition` because `cognition` depends on `mindmap-intelligence` (`cognition/pom.xml:66`) and not the other way round.

It injects the Eidos SPIs `DispositionSignalStore`, `DispositionHealth`, `DispositionEvolution`, `DispositionProfileStore` and `AgentRegistry`. It also injects `CbrRecordStore`, `EffectiveCognitiveDefaults` (read-only, for `relationalComplexity`), `PersonalityStateService` (owner of the reflection ledger; see [S2]) and `Clock`.

**`run(tenantId, subgraphPriority)`:**

```
for agentId in effectiveDefaults.agentIds(tenantId):
    ledger = stateService.read(tenantId, agentId, now).reflection()   // persisted on first sight
    n = floor((now - ledger.lastReflectionAt) / config.reflectionPeriod)
    if n == 0: continue                                    // wall-clock gate
    descriptor = agentRegistry.findById(agentId, tenantId) // the owner's view (A: + lived profile)
    if descriptor has no dispositionProfile: advance ledger via transition; continue

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

    // 3. Commit: only after the decision is final  [R] intent-first, see "JPAF commit ordering"
    Evolved & now - ledger.lastTransitionAt < minTransitionInterval:
              -> Deferred (no commit; signals keep decaying; halt := false)    [R] rate bound
    Evolved:  stateService.transition(..., s -> s.withReflection(ledger.withPendingEvolution(e.newProfile, case)))  // (1) intent
              profileStore.update(agentId, tenantId, e.newProfile)     // (2) identity write (absolute); (A): lived profile, same update as (1)
              signalStore.clear(agentId, tenantId)                     // (3) close the signal epoch
              cbrStore.store(transition case, trigger_type = p.type)   // (4) derived record
              ledger := ledger.withoutPendingEvolution().withLastTransitionAt(now)   // (5) intent cleared
    Dampened: signalStore.decay(agentId, tenantId, x.decayFactor)

    // 4. Record
    ledger := ledger.advancedBy(n * reflectionPeriod).withHalted(halt)
    stateService.transition(tenantId, agentId, now, s -> s.withReflection(ledger))   // [R] per [S2]
    journal.record(DispositionReflected(...outcome...))
    signals: Evolved -> PERSONALITY_EVOLVED (1.0)
             Halted  -> PERSONALITY_HALT (0.9) only when ledger.halted was false   [R] edge-triggered
```

**[R] Per-agent isolation.** The body of the per-agent loop runs inside `try/catch (RuntimeException)`. A failure:
- logs WARN with tenant and agent;
- journals `DispositionEvolutionFailed(tenantId, agentId, phase step, message)`;
- increments `personality.evolution.failures`;
- continues with the next agent.

Without this, one agent's exception (for example an Eidos `DispositionValue` validation failure or a registry error) aborts evolution for every later agent of the tenant on every run, because `ConsolidationScheduler.runPhases` catches only per phase. `findById` returning empty (agent deleted, or known only to the explicit layer) is a debug-logged skip that leaves the ledger untouched. It is not an exception.

**[R] Pending intent first.** If `ledger.pendingEvolution` is present at the start of an agent's run, the phase replays steps (2)–(5) before anything else. Step (2) is absolute, so the replay is idempotent. The phase never probes while an intent is pending.

**[R] JPAF commit ordering.** Rev 2's original order was identity write → CBR → clear. A crash after the identity write and before `clear` makes the next reflection probe the *new* identity with the *old* counts, which can commit a spurious second transition. Persisting the intent first and closing the signal epoch before the derived CBR write removes that path:
- A CBR failure leaves the intent in place, and the next run retries it.
- A duplicate CBR case is possible only from a crash between (4) and (5). The case carries the ledger's intent id, so it is identifiable, and the guarantee is at-least-once.

Under store-of-record option (A), the intent, the lived profile and the ledger all live in the same `PersonalityState` node, so (1), (2) and (5) collapse into one atomic node write.

**[S2] Crash-point table (one failure principle for both families: a cross-store failure may under-count or be retried, never double-count or overshoot).**

| Crash point | Effect | Class |
|---|---|---|
| after decay, before the ledger `transition` | next run decays the same periods again | under-count (signals weaker); accepted |
| after (1), before (2) | intent replayed next run; (2) is absolute | retried, idempotent |
| after (2), before (3) | replay re-applies (2) and then clears. The phase never probes while an intent is pending, so new-profile/old-epoch evaluation is impossible | no double count |
| after (3), before (5) | replay re-runs (4); the duplicate CBR case is identifiable by the intent id | at-least-once audit only |

This is the same principle as D8 for PID-5. Structure R2-05 proposed `clear → update` as a simpler order, but the [R] intent ordering is strictly better: it never loses a transition, whereas `clear → update` loses one on a crash between the two steps.

**[R] Transition rate bound.** `minTransitionInterval` (default 30 d) caps committed JPAF transitions at one per agent per interval, independent of event rate. It gates only *when* an `Evolved` result is committed (neocortex's role under D6), and leaves *what* is valid to Eidos. Without the bound, the transition rate depends on traffic. Under default Eidos preferences (δ = 0.06; dominant 0.35, auxiliary 0.20), a swap needs effective(aux) ≥ 0.35, which is about **4 retained auxiliary activations**. A busy agent with ≥ 4 negative interactions in one reflection period (24 h) would therefore swap type daily. See §Calibration.

**[R] Ceiling edge case.** `relationalComplexity` is validated to [0,1] (`CognitiveCapacityConfig`), so `l2Ceiling·rc` can be 0. In that case the agent is **evolution-disabled**: the recorder skips it, the phase skips reflection, and the ledger records `disabled` once and journals it once. Without this, rc = 0 flaps every period: halt, then decay to Aligned, then unhalt, then the next activation halts again, with a signal each time.

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

The ledger is persisted as `jpaf.*` properties on the agent's existing `PERSONALITY_STATE` node (`sit-state:`), and is written only through `PersonalityStateService.transition`. The failure-atomicity and `TenantAgentKey` requirements under §Promotion transaction therefore apply to it unchanged.

- **Writer:** `DispositionEvolutionPhase` only.
- **Readers:** the phase, and `DispositionSignalRecorder`. The recorder checks halt through `stateService.read`, which is cache-first.
- **First sight is persisted (structure R2-06).** An agent with no node is created by `read`/`transition` under the per-agent lock, with `reflection.lastReflectionAt = now`, and the node is written immediately. A restart inside the first `reflectionPeriod` keeps the original clock, so a deployment that restarts more often than the period still reflects.
- **One subgraph owner (structure R2-07).** Only `PersonalityStateService` resolves the `PERSONALITY_STATE` subgraph. No second list-then-create resolver exists, so two stores can no longer race to create two subgraphs of the same type. In-process first resolution per tenant is serialised by the existing `computeIfAbsent`. Cross-instance creation is covered by #1104.
- **Why co-located.** The ledger is per-agent lived personality-evolution state, so it belongs with the rest of that state vector (Era 7b decision 1), under the same lock and version. The participant's facet transitions never touch `reflection`, and the JPAF phase never touches facets, so co-location adds no contention beyond the per-agent lock's short critical section.

#### `DispositionSignalRecorder` (cognition, `cognition.personality`)

An `@ApplicationScoped` CDI observer. It replaces `PersonalityEvolutionOrchestrator.record()`.

```
@Observes RelationshipRecorded e:
    ev = e.event()
    source = sources.forEventType(RelationshipEvent.class)   // at most one, see dedup rule
    if source == null || !source.relevant(ev): return          // NEUTRAL short-circuits here,
                                                                // before any registry lookup
    if stateService.read(ev.tenantId(), ev.agentId(), now).reflection().halted(): return
    descriptor = agentRegistry.findById(ev.agentId(), ev.tenantId())   // lazy, only when needed
    for a in source.translate(ev, descriptor):
        if a.functionTerm() in descriptor profile terms:
            signalStore.recordActivation(agentId, tenantId, a.functionTerm())   // [S2] 3-arg: no valence
        else:
            debug-log the dropped term (vocabulary mismatch is visible, not silent)
```

- **Signal units (activation, not valence).** One translated activation adds one count to the term. In `DefaultDispositionHealth.probe`, the effective weight is `normalise(base + count × REINFORCEMENT_DELTA)`, where `REINFORCEMENT_DELTA` is an Eidos tenant preference with default 0.06. No `DispositionSignalStore` honours `SignalValence`: `InMemoryDispositionSignalStore` and `JpaDispositionSignalStore` implement only the 3-arg `recordActivation`, and the 4-arg default drops valence. So every activation *reinforces* its term. `RelationshipPressureSource` maps NEGATIVE to the auxiliary, meaning the auxiliary is engaged under relational strain, as JPAF describes. That is what makes `DOMINANT_AUXILIARY_SWAP` reachable. This is the existing, intended semantics and is kept unchanged. Thresholds are therefore calibrated by the Eidos preferences (`REINFORCEMENT_DELTA`, `OVER_REINFORCEMENT_THRESHOLD`), not by a neocortex magnitude scale.
- **One event type only.** It observes only `RelationshipRecorded`, the only event with a concrete pressure source. `ExperienceRecorded` is **not** observed. `RelationshipRecorded` is derived from it (`RelationshipProcessor.onExperienceRecorded`), so observing both would double-count one experience.
- **Dedup rule.** Each event type in a derivation chain binds to at most one `TraitPressureSource`. The recorder builds a `Map<Class<?>, TraitPressureSource<?>>` at startup and **fails fast** if two sources declare the same `eventType()`. That replaces the orchestrator's order-dependent "first match wins". A future source for a primary event (`ExperienceRecorded`) must exclude experiences that produce a derived `RelationshipRecorded`. #1102 tracks the valenced sources.
- **[R] Totality.** `RelationshipRecorded` is fired synchronously inside `RelationshipProcessor`'s try block, *after* the memory is stored. A synchronous observer exception would skip the remaining observers and be logged there as a misleading "Relationship memory store failed". The recorder is therefore total:
  - The body is wrapped in `try/catch (RuntimeException)`, which logs WARN with tenant and agent and increments `personality.signal.record.failures`.
  - `findById` returning empty is a debug-logged skip.
  - The same applies to the `InteractionAppraised` path below.
- **[R] Live valenced source: `InteractionAppraised`.** Production `RelationshipRecorded` is always NEUTRAL (#1102), but production interactions already carry valence. `CognitionCore.recordInteraction` (`:411-428`) computes a `QualitySignal` for every interaction: the impact-supplied value, else `deriveQualitySignal`, which is mood-based (`:566-581`). Agency calls it in production with `impact = null` (`CognitionAvatarAdapter.recordInteraction` ← `SpeechSession`).
  - `CognitionCore.recordInteraction` emits `InteractionAppraised(tenantId, agentId, subjectId, quality, at)` to the recorder via `CognitivePipelineBuilder.dispositionSignalRecorder(...)`, inside `safeRun`. It does so regardless of `userModelEnabled`.
  - `InteractionPressureSource implements TraitPressureSource<InteractionAppraised>` uses the same JPAF mapping as `RelationshipPressureSource`: POSITIVE activates the dominant, NEGATIVE activates the auxiliary, NEUTRAL is filtered out by `relevant()`.
  - This makes the JPAF path non-inert in production without waiting for #1102.
  - Dedup: `InteractionAppraised` and `RelationshipRecorded` are distinct event types, and the latter is NEUTRAL today. When #1102 valences `RelationshipRecorded`, the one-source-per-derivation-chain rule decides which event carries the activation (noted on #1102).
- **[R] Dimension namespace.** Both sources emit terms taken from the descriptor's own `dispositionProfile` (dominant or auxiliary by weight), so their spelling is canonical by construction. The profile-membership check, together with debug log and the counter `personality.signal.dropped{reason=unknown-term}`, guards future sources.
- **Concurrency.** An activation recorded between a reflection's `probe` and its `clear` is consumed by that evolution. This is the intended semantics: the transition closes the signal epoch. No lock is needed. The scheduler serialises phase runs under its own lock on one executor thread, and the signal stores are safe to call concurrently (JPA row-transactional; in-memory concurrent maps).

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

**[R] Promotion parameters** (`promoteFraction` 0.8, `promoteDwell` 30 d, `promotionBudget` 0.20) are added to `DynamicsConfig`, the integrator's config record. It currently has no validation, so a compact constructor is added. It rejects:
- `promoteFraction ∉ (0, 1]`
- `promoteDwell ≤ 0`
- `promotionBudget ∉ (0, 1]`
- `dMax ∉ (0, 0.5]`
- `sMax ≤ 0`
- `epsilonPublish ≥ promoteFraction·dMax` (a promotable `homeOffset` must also be publishable)

Each of these breaks a stated invariant. For example, `promoteFraction > 1` makes promotion unreachable, which is exactly the rev 1 defect. Source: MicroProfile config keys `casehub.cognition.personality.reflection-period`, `.retention-per-reflection` and `.l2-ceiling`, falling back to `defaults()`. This follows the `@ConfigProperty` style of the sibling cognition phases, for example `RelationalSchemaEvolutionPhase`.

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
- **Facet naming across the boundary.** `SituationalStateService` keys facets by the `PersonalityFacet` constants (title case, for example `"Risk Taking"`), which is the form `EidosCognitiveProfileBridge.titleCase` produces. Eidos `AmpdFacet.facet` is a free-form authored string. The phase maps each state key to the authored `AmpdFacet.facet` whose `titleCase` form equals it, and `updateFacets` is keyed by that **authored spelling**, so the identity write never introduces a second spelling of the same facet. A state facet with no authored counterpart is not promoted, because there is no baseline to promote into. It is skipped and logged at `FINE`.

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
- **[R] Per-agent isolation.** The same try/catch / journal / continue contract as `DispositionEvolutionPhase` applies here. A promotion that fails for one agent cannot stop deformation or promotion for the rest of the tenant.
- **[R] Bounded arithmetic.**
  - `targetScore` is `round(100·clamp01(...))`, so the identity write is always a valid AMPD score.
  - `delta` is computed from the clamped target, so any excess that the clamp cuts off stays in `homeOffset` and is never discarded.
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

Signal fields. The emitting phase collects the run's signals and returns them from `ConsolidationPhase.signals()`, which already exists as a default method returning `List.of()`.

**[R] Drain on read.** `signals()` swaps out the pending list and returns it, as `ExperienceConsolidationPhase` does (`:137-141`). `ConsolidationScheduler.tick` calls `beginTick()` once and then runs every tenant, calling `signals()` after each tenant's `run`. A phase that clears only in `beginTick()` would therefore leak tenant A's signals into tenant B's batch. `PERSONALITY_HALT` is edge-triggered on the ledger's `halted` false → true transition, so a halted agent emits one signal per halt episode, not one per reflection.

| Field | Value |
|---|---|
| `principalId` | `agentId` |
| `tenantId` | `tenantId` |
| `sourceNodeId` | id of the agent's `PERSONALITY_STATE` node: the `sit-state:` node for promotion, the `evo-ledger:` node for JPAF events |
| `sourceName` | `"personality"` |
| `reason` | JPAF transition: `"<previousLabel> -> <newLabel> (<triggerType>)"`; halt: `"drift <magnitude> >= ceiling <l2Ceiling·rc>"`; promotion: `"<facet> baseline <old> -> <new>"` |

Event refs: journal entries use `EventRef.consolidation(EventRef.event("disposition-evolution"))` (JPAF) and `EventRef.consolidation(EventRef.event("situational-deformation"))` (promotion, the existing ref). The propagator's `updateBase` uses `"identity-update"`.

No signal is emitted for ordinary hourly `homeOffset` drift. It changes every hour and belongs in the journal (`SituationalDeformationConsolidated`), not in attention.

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
| **[R]** `InteractionAppraised`, `InteractionPressureSource` | cognition (`cognition.personality`) | live valenced source; emitted by `CognitionCore.recordInteraction` |
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

The Agency producers of the orchestrator are removed in agency#487, in the same change window.

**Not deprecated:** `DispositionSignalStore`, `DispositionHealth`, `DispositionEvolution`. They remain the JPAF accumulator and evaluator (issue-126 D1, reaffirmed). **[S2]** Neocortex stops using `SignalValence`: `TraitActivation.valence` is removed. The Eidos type itself is Eidos's to keep or remove (eidos#237 comment). `DispositionProfileStore` becomes real (eidos#235).

### [R] Production wiring (in scope; #1060 does not close without it)

#1060 was filed because a fully implemented component had no production caller. Unit tests with hand-wired collaborators cannot be its acceptance gate. These beans are delivered by this issue:

| Bean | Producer | Notes |
|---|---|---|
| `EffectiveCognitiveDefaults` | `@Produces @DefaultBean @Singleton` in `CognitionDefaultBeans` | First production producer. It is built from the explicit `CognitiveDefaultsRegistry`, `EidosDescriptorViewSource`, and `PersonalityStateService` as `PersonalityStateSource`. It is already a required injection point (`CognitionDefaultBeans.cognitiveResourcePool`) and an `Instance<>` point in ≥ 6 phases and in `CognitionCoreFactory`. |
| `PersonalityStateService` (§[S2]), `PersonalityStateIntegrator`, `DynamicsConfig` | `@Produces @DefaultBean @Singleton` (cognition) | The facet-name set comes from the `PersonalityFacet` constants. |
| `SituationalDeformationPhase` | `@ApplicationScoped @Priority(45)` | This is pulled forward from #1082, because promotion and integrator advance must run in production even before the participant is registered. `agentIds` reads persisted nodes, so an empty cache is fine. |
| `DispositionEvolutionPhase`, `DispositionSignalRecorder`, `DispositionEvolutionLedgerStore`, `InteractionPressureSource` | `@ApplicationScoped` (cognition, Jandex-indexed) | The phase is discovered by `ConsolidationScheduler`'s `Instance<ConsolidationPhase>`. |
| Recorder → `CognitionCore` | `CognitionCoreFactory` → `CognitivePipelineBuilder.dispositionSignalRecorder(...)` | Feeds `InteractionAppraised`. |

#1082 keeps the participant's registration in `CognitionCore`, which is blocked on eidos#234. Spring wiring is agency#487.

### [R] Deployment assumptions

ASSUMPTION: One active neocortex instance per tenant. `ConsolidationScheduler.knownTenants`, `SignificanceAccumulator`, the `EffectiveCognitiveDefaults` slots, and the per-agent locks in the state service and ledger all assume this. Two instances would split events across nodes and fork evolution. neocortex#1104 documents the contract and the options if that ever changes.

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
| casehubio/eidos#235: registry-backed `DispositionProfileStore` + `updateFacets` | **Hard.** Lands first | Every identity change is discarded (NoOp). Nothing in this design changes identity |
| #1063: scheduler starvation and restart tenant loss | **Hard for production effect** | Both phases are cadence-invariant (wall-clock grids with exact catch-up), so they are *correct* under any schedule. But they *never run* for busy deployments or unregistered tenants |
| #1082: situational participant registration | **Hard for PID-5 promotion in production** | Without the participant there is no displacement, so `homeOffset` never saturates. **[R]** The state service, integrator, deformation phase and promotion are production-wired by this issue, and only the displacement source remains in #1082 |
| #1102: valenced relationship and goal-outcome signals | **[R] Not blocking** (was: hard for JPAF non-inertness) | `InteractionAppraised` from `CognitionCore.recordInteraction` carries live production valence. #1102 adds further valenced sources |
| casehubio/agency#487: remove orchestrator producers, wire the new beans | Same change window | Agency fails to compile |
| casehubio/eidos#237: fractional activation weights | Not blocking | Integer truncation biases low counts; the reflection grid limits the damage |

**What #1060 closes:** the structural defect. Evolution is evaluated on a durable wall-clock cadence. Its result is written to the identity of record. It reaches `EffectiveCognitiveDefaults` through one path, for both families.

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
