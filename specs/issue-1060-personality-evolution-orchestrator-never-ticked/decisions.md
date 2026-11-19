# Decisions — #1060 Personality Evolution

## D1: Signal recording cadence

**Choice:** CDI event observer (event-driven). The observer listens to `RelationshipRecorded` only.
**Alternatives:**
- TERMINAL tick participant: simpler wiring, but it runs even when nothing happened, which is wasteful.
- Consolidation-only: delays signal recording by minutes and loses per-event granularity.
**Rationale:** Signals should fire when events occur. This matches the existing event-driven patterns (`RelationshipObserver`, `SubThoughtExtractionObserver`) and costs nothing when no events arrive.
**Rev 2 refinement (R1-10):**
- `ExperienceRecorded` is not observed. `RelationshipRecorded` is derived from it, so observing both would double-count.
- Each event type binds to at most one pressure source. Duplicates fail fast at startup.
- Descriptor lookup is lazy, after the cheap `relevant()` pre-filter.
**Trade-offs:** More CDI wiring than a tick participant.
**Sources:** `RelationshipObserver.java`, `SubThoughtExtractionObserver.java`, `RelationshipProcessor.java:33-47`
**Status:** revised (rev 2)

## D2: Evolution evaluation cadence

**Choice:** Consolidation phases in `cognition`, gated by **wall-clock grids**:
- JPAF uses a reflection period (default 24h).
- PID-5 uses the integrator's hourly grid.

**Alternatives:**
- TERMINAL tick participant: evaluating on every tick is wasteful for a slow process.
- Throttled tick participant: adds an internal timer.
- Rev 1: evaluate and decay on every consolidation run. This makes signal half-life depend on scheduler cadence (R1-08).

**Rationale:**
- Personality change is slow. Consolidation is the right *cadence owner*, but its rate varies: idle gating, `consolidateNow` bursts and starvation (#1063).
- A wall-clock grid with exact catch-up (`retention^n`) makes the dynamics cadence-invariant. Era 7b key decision 4 applies the same principle, and issue-126 D3 chose batched periodic reflection with a time-based decay anchor.
- A coarse grid rather than continuous `f^(Δt/τ)` is required because `DispositionSignalStore` counts are integers that truncate on decay (eidos#237).

**Trade-offs:**
- Evolution needs a persisted per-agent reflection ledger.
- The phase still never runs while the scheduler is starved. #1063 is a prerequisite.

**Sources:** `ConsolidationScheduler.java`, `PersonalityStateIntegrator.java`, `JpaDispositionSignalStore.java:56-78`, issue-126 D3, Era 7b key decision 4
**Status:** revised (rev 2)

## D3: Propagation mechanism

**Choice:**
- The Eidos registry is the single identity of record. Changes are written through a registry-backed `DispositionProfileStore` (eidos#235).
- Propagation is `AgentDescriptorUpdated` → `IdentityChangePropagator` (`AFTER_SUCCESS`) → `EffectiveCognitiveDefaults.updateBase(view of the committed descriptor)`. This absorbs #1080.

**Alternatives:**
- Rev 1: the phase calls `updateBase()` / `updateState()` directly. **Rejected.** `CognitionCore.tick` re-bases from the Eidos descriptor on every tick (`CognitionCore.java:288-291`), so any neocortex-local base write is reverted within one tick. The base layer has exactly one owner.
- Neocortex-owned "evolved baseline" overlay: a persisted fourth composition layer between the Eidos base and situational state. Rejected because it contradicts Eidos as the identity owner and adds a layer with no benefit over writing to the owner.

**Rationale:**
- #1060 itself names the needed path: "DispositionProfileStore → descriptor → `updateBase`".
- `AgentRegistry.register` already fires `AgentDescriptorUpdated`, and `updateGoalLifecycleState` is the read-modify-register precedent.
- Every reader (per-tick re-base, `EidosDescriptorViewSource`, the propagator) reads the same owner, so they cannot diverge.

**Trade-offs:** Hard dependency on eidos#235.
**Sources:** `CognitionCore.java:288-291`, `EidosDescriptorViewSource.java`, eidos `JpaAgentRegistry.register`, `AgentRegistry.updateGoalLifecycleState`, `CdiAgentRegistryEvents`
**Status:** revised (rev 2, R1-03)

## D4: PID-5 scope

**Choice:** Include PID-5 in this issue, limited to **baseline promotion** (Tier 3). The situational state owner performs it inside `SituationalDeformationPhase`.
**Correction of premise:** Rev 1 cited "`homeOffset` field exists but nothing writes it". **That is false.** `PersonalityStateIntegrator.closeHour()` writes `homeOffset` from the signed exposure integral, bounded by `dMax` and decaying over `tauSetpoint` (Era 7b, TESSERA). Rev 1's "Tier 2 homeOffset graduation" therefore duplicated an existing owner's dynamics. It is removed (R1-01, R1-02).
**Alternatives:**
- Defer PID-5 to a separate issue. That leaves the identity write path built for one family only.
- Rev 1 Tier 2 plus displacement-EMA pressure. Rejected: a second writer and a second estimator of the same quantity.

**Rationale:** The only missing PID-5 step is graduating persistent home offset into identity. The owner of `PersonalityState` must do it atomically with the `homeOffset` reduction. The criteria are:
- dwell-gated: |homeOffset| ≥ 0.8·dMax for 30 days
- budget-capped: cumulative |promoted| ≤ 0.20

Rev 1's threshold of 0.3 exceeded `dMax` = 0.10 and could never fire.

**Trade-offs:** Requires #1082 for any production effect. Adds `saturatedSince`, `promoted` and `pendingPromotions` to persisted state.
**Sources:** `PersonalityStateIntegrator.java:97-119`, `DynamicsConfig.defaults()`, `SituationalDeformationPhase.java`, Era 7b research
**Status:** revised (rev 2)

## D5: Signal model

**Choice:** Each family keeps its native accumulator:
- JPAF: the Eidos `DispositionSignalStore`, persistent via `JpaDispositionSignalStore`.
- PID-5: the integrator's exposure integral.

There is no neocortex `PersonalityPressure` / `PersonalitySignalAccumulator`.

**Superseded choice (rev 1):** a single `PersonalityPressure` type and one neocortex accumulator for both families.

**Why superseded:**
- The PID-5 "signals" were a second estimator of the integrator's exposure (R1-02).
- The shared string namespace routed by membership lookup and dropped mismatches silently (R1-09).
- The accumulator re-created an SPI that already exists in Eidos, with a persistent implementation, while being in-memory itself and so lost on restart.

The two families differ in their accumulation process (discrete activation counts vs. continuous displacement integral), not merely in history. **The unification moves to where the families really are the same:**
- the identity of record
- the propagation path
- the wall-clock time basis
- the consolidation cadence owner
- the journal

**Sources:** `PersonalityStateIntegrator.java`, eidos `DispositionSignalStore`, `JpaDispositionSignalStore`, `InMemoryDispositionSignalStore`
**Status:** revised (rev 2)

## D6: Architecture approach

**Choice:** Neocortex owns *when* evolution is evaluated and *where the result propagates*. Eidos owns *what a valid type transition is*: `DispositionHealth` / `DispositionEvolution`, the vocabulary owner. This reaffirms issue-126 D1.

**Superseded choice (rev 1):** full neocortex re-implementation of JPAF evaluation.

**Why superseded:** Rev 1's premise that "the existing threshold/drift/dampening logic is not complex" described the orchestrator wrapper, not the evaluation it delegates to. `DefaultDispositionHealth` / `DefaultDispositionEvolution` implement:
- four JPAF rules
- `VocabularyRegistry` shadow and opposite resolution
- tenant `PreferenceProvider` thresholds
- canonical dominant/auxiliary normalisation and type labels

Re-implementing them would lose shadow replacement and structural reorganisation, strip the CBR `trigger_type` taxonomy, and duplicate vocabulary semantics outside their owner. Issue-126 D1 explicitly rejected exactly that ("bypasses eidos JPAF pipeline… risks duplicating DefaultDispositionEvolution"). Rev 1 reversed that decision without citing it. Rev 2 restores it.

**Trade-offs:** Neocortex depends on Eidos SPI stability, as already accepted in issue-126 D1.
**Sources:** eidos `DefaultDispositionHealth.java`, `DefaultDispositionEvolution.java`, issue-126 `decisions.md` D1
**Status:** revised (rev 2, R1-05)

## D7: Safety policy

**Choice:** Each family has its own safety mechanism in its native units. Halt state is persisted in the reflection ledger.
- JPAF: L2 on the weight simplex × `relationalComplexity`, decided before any commit.
- PID-5: `dMax` and the cumulative promotion budget.

**Alternatives:** Rev 1's single L2 across Jungian weights and facet offsets. Rejected: the units are not commensurable, the check ran after the writes, and halt ownership was unclear (R1-07).
**Status:** captured (rev 2). **JPAF half superseded by D24** (cross-cutting round 1): the L2 halt is deleted. The PID-5 half stands.

## D8: Failure ordering for PID-5 promotion

**Choice:**
1. Persist the reduced `homeOffset` together with a pending-promotion intent.
2. Make an absolute (idempotent) identity write.
3. Clear the intent.

If an intent is still pending on the next run, the write is replayed.

**Rationale:** Two stores (MindMap and the Eidos registry) cannot commit atomically. With this ordering, every failure under-counts transiently and identity never overshoots. Absolute writes make replay safe, and there is no double-count path.

**Structure round 2 amendments:**
- **The principle is generalised to both families:** a cross-store failure may under-count or be retried, and never double-counts or overshoots. D9's JPAF intent ordering satisfies it (see the crash-point table in the spec).
- **The derived view is included, not only the stores.** Under (B), the reduced-`homeOffset` snapshot is published to `EffectiveCognitiveDefaults` *before* the identity write (2). Otherwise the synchronous propagator composes `(baseline+δ) + h` and overshoots (R2-02).
- Under store-of-record option (A), this protocol is unnecessary: promotion is one `transition`.

**Status:** captured (rev 2); amended (structure round 2)

## D9: JPAF commit ordering and transition rate bound (robustness review R1-12, R1-10)

**Choice:**
1. Persist a `pendingEvolution` intent in the ledger.
2. Make an absolute identity write.
3. Clear the signal store.
4. Write the CBR case.
5. Clear the intent.

A pending intent is replayed before any new probe. Separately, `minTransitionInterval` (default 30 d) bounds committed transitions per agent.

**Alternatives:**
- Rev 2's original order (write → CBR → clear). Rejected: a crash after the write re-probes the new identity with the old counts and can commit a spurious second transition.
- A per-source activation cap. Rejected: it interacts badly with integer truncation (eidos#237).

**Rationale:**
- With default Eidos preferences, a swap needs about 4 retained auxiliary activations. Interaction-turn-granularity sources can produce that in one day.
- The interval makes the type-change rate a structural bound and leaves Eidos's rules untouched (D6: neocortex owns *when*).

**Status:** captured (robustness round 1)

## D10: Single serialised owner of situational/lived state (robustness review R1-09, R1-18)

**Choice:** This builds on the structure review's `PersonalityStateService.transition(tenant, agent, now, UnaryOperator)`, which holds a per-agent lock and versions monotonically. Robustness adds:
- failure atomicity: the cache is untouched on a throw;
- `TenantAgentKey` keys everywhere;
- `agentIds(tenant)` read from persisted nodes, so enumeration survives restart and pending promotion intents are replayed;
- load-through idle eviction;
- the service implements `PersonalityStateSource`, replacing the always-empty `DefaultPersonalityStateSource`.

**Rationale:**
- The participant (tick thread) and the deformation/promotion phase (consolidation thread) would otherwise interleave unsynchronised read-modify-writes. That loses displacement, `homeOffset`, or a promotion intent, and the lost intent breaks D8.
- `System.nanoTime()` versions are not comparable across restarts.
- String keys alias across tenants.

**Status:** captured (robustness round 1)

## D11: Production wiring is in scope; live valenced source (robustness review R1-05)

**Choice:**
- #1060 delivers the first production producers for `EffectiveCognitiveDefaults`, the state service, the integrator and the deformation phase.
- It adds `InteractionAppraised` (emitted by `CognitionCore.recordInteraction`, valence via `deriveQualitySignal`) as a JPAF activation source.
- Its close criterion is a CDI wiring test plus an end-to-end test that survives tick, eviction and restart.

**Rationale:**
- #1060 exists because a built component had no production caller. The propagation target itself had no producer.
- `RelationshipRecorded` is always NEUTRAL (#1102). Interaction valence already reaches `CognitionCore` in production (agency `SpeechSession` → `CognitionAvatarAdapter.recordInteraction`).

**Status:** captured (robustness round 1)

## D12: Reflection ledger is a component of PersonalityState (structure review R2-06, R2-07)

**Choice:** No separate `DispositionEvolutionLedgerStore` or `evo-ledger:` node. `PersonalityState.reflection` holds the ledger fields:
- `lastReflectionAt`, `halted`
- `lastTransitionAt`, `pendingEvolution`, `disabled` (from D9)

It is persisted as `jpaf.*` properties on the agent's `PERSONALITY_STATE` node, and mutated only through `PersonalityStateService.transition`. `read` and `transition` create and persist the node on first sight, under the per-agent lock.

**Alternatives:**
- A separate ledger store with a shared `PersonalityStateSubgraph` resolver. That fixes the duplicate-subgraph race, but keeps two stores, two caches, two locks and two versions for one agent's lived state. Under (A) it also splits the JPAF intent from the lived profile, defeating the single-node commit that D9 relies on.
- A cache-only first-sight ledger. Rejected: a restart inside the first reflection period resets the clock, so frequently restarted deployments never reflect.

**Rationale:**
- The ledger is per-agent lived personality-evolution state. Era 7b decision 1 calls for one state vector with one owner.
- Co-location removes the second subgraph resolver (R2-07) and inherits persisted first sight (R2-06).

**Status:** captured (structure round 2)

## D13: Polarity is encoded by target selection; TraitActivation has no valence (structure review R2-04)

**Choice:**
- `TraitActivation(functionTerm)`; the recorder uses the 3-arg `recordActivation`.
- Pressure sources express polarity by choosing which profile term to activate. A negative outcome activates the auxiliary.

**Alternatives:** Signed accumulator weights in eidos#237. Rejected: that would change JPAF's theory (reinforcement by use) inside a storage-format change. Weakening a function by signal is a model change that needs its own design.

**Rationale:** No Eidos store honours `SignalValence`, and `probe` reads counts only. Keeping the field promised semantics the accumulator does not have, and invited sources to emit `(dominant, NEGATIVE)` and get reinforcement. The rule is recorded on #1102, and the Eidos SPI cleanup on eidos#237.

**Status:** captured (structure round 2)

## D14: The identity owner owns the facet-key contract (structure review R2-03)

**Choice:**
- Canonical AMPD facet names (the `AmpdFacetShift.VALID_FACETS` set) are enforced by Eidos: `AmpdFacet` canonicalises on construction and deserialisation, rejects unknown names, and rejects duplicates (eidos#239).
- Under (B), `updateFacets` is keyed by canonical names, and #239 is a hard prerequisite.
- Under (A), no facet write crosses the boundary.

**Alternatives:** The rev-2 consumer-side mapping (map each state key to whichever authored spelling `titleCase`s to it). Superseded: it placed an identity-boundary contract in the consumer, and it fails silently on colliding spellings.

**Status:** captured (structure round 2)

## D15: Under (A), "authored ⊕ lived" has one owner (structure review R3-03)

**Applies if** R1-01 chooses option (A).
**Choice:**
- Pure `LivedComposition` (cognitive-index) is the only implementation of the composition rule: fingerprint-gated profile substitution, plus resting facet = `baseline_authored + promoted + homeOffset`.
- `EffectiveCognitiveDefaults` delegates to it, replacing its private `composeFacets`.
- The phase and the recorder obtain lived Eidos descriptors only through `LivedDescriptors`, which delegates through `EidosCognitiveProfileBridge.livedDescriptor` to the same function.
- `PersonalityStateSnapshot` carries raw lived state (`LivedProfile`, `promoted`), not a composed profile.

**Alternatives:** The snapshot carries an already-composed profile. Rejected: composition must use the base that `EffectiveCognitiveDefaults` currently holds, which `CognitionCore` re-bases every tick. Composing at snapshot time bakes in a stale authored base and makes the fingerprint check test the wrong base.
**Status:** captured (structure round 3), conditional on R1-01 = A

## D16: Under (A), authored edits win over the lived JPAF profile (structure review R3-02)

**Applies if** R1-01 chooses option (A).
**Choice:**
- The lived JPAF profile is stored with the fingerprint of the authored profile it evolved from. On mismatch, readers use the authored profile immediately (a pure check in `LivedComposition`).
- `DispositionEvolutionPhase`, the sole writer, then: clears signals; drops the lived profile and any pending intent; sets `lastTransitionAt := now`; journals `DispositionReauthored`.
- PID-5 `promoted` stays a delta over the authored baseline, consistent with `homeOffset`, so no reconciliation is needed.

**Alternatives:** Per-term JPAF deltas. Rejected: JPAF transitions are canonical re-weightings, not increments. Re-normalising them against a changed base yields a profile Eidos never evaluated.
**Rationale:** Under (A), "Eidos owns authored identity" must mean authored edits take effect. Unchanged boot re-registration keeps the same fingerprint, so it is a no-op.
**Status:** captured (structure round 3), conditional on R1-01 = A

## D17: Exactly-once JPAF decay, marker written first (robustness review R2-03)

**Choice:** `ReflectionLedger.decayedThrough` is persisted **before** `signalStore.decay(retention^k)`, where `k` counts the periods not yet decayed. An evaluation failure becomes `ReflectionOutcome.Failed` and still advances the ledger.

**Alternatives:**
- **Rev 2:** decay, then advance the ledger after evaluation. *Rejected:* a persistent downstream failure re-decays on every consolidation run and wipes counts in about 30 minutes.
- **The reviewer's decay-then-mark.** *Rejected:* a persistent failure of the marker write (MindMap) has the same wipe-out effect.

**Rationale:**
- Marker-first makes every *persistent* failure harmless: MindMap down means nothing decays; signal store down means recording also fails.
- It confines the single-crash cost to one skipped period of decay, a ×1.25 retention that can never compound.

**Status:** captured (robustness round 2)

## D18: The JPAF intent closes at the signal epoch; the CBR case moves to a bounded outbox (robustness review R2-04)

**Choice:**
- Recovery runs before the wall-clock gate on every run: (B) absolute write, then `clear`, then `closeEpoch`.
- `closeEpoch` is a single `transition` that clears the intent, sets `lastTransitionAt` from the intent's commit time, and moves the case into `auditOutbox`.
- The outbox retries once per reflection period, up to 5 attempts, then journals `DispositionTransitionAuditFailed` and drops the entry.

**Alternatives:**
- **Round-1 replay of (2)–(5):** re-clears on every retry, so a CBR outage erases fresh activations and freezes the agent.
- **Explicit per-step flags** (`identityWritten`, `epochClosed`, `audited`), as the reviewer suggested. *Rejected as unnecessary:* the intent's existence already is the "epoch not closed" flag. (2) is idempotent, and (4) leaves the critical path entirely. One fewer state field, same guarantee.

**Rationale:** A derived audit record must never hold evolution hostage or destroy evidence.

**Status:** captured (robustness round 2)

## D19: Recorder writes are transaction-isolated; signal-store concurrency is Eidos's fix (robustness review R1-08, R2-05)

**Choice:**
- The recorder writes activations in its own `@Transactional(REQUIRES_NEW)` method.
- Neocortex treats current signal counts as a lower bound.
- Eidos fixes atomic upsert, bulk decay, `REQUIRES_NEW` and in-memory races in eidos#241 (not blocking).

**Rationale:**
- A personality-signal failure must never roll back the caller's memory or interaction work.
- Lost increments only under-count. That delays evolution and never causes a spurious transition, so neocortex needs no workaround around an Eidos storage bug.

**Status:** **superseded by D20 (robustness round 3).** Both premises were wrong:
- Self-invoked `@Transactional` is not reliable. Spring does not proxy `this.` calls, and ArC does not intercept private methods.
- Lost increments do not only under-count. `DefaultDispositionHealth.probe` normalises across terms, so losing the dominant's increments can commit a spurious swap.

## D20: One per-agent-serialised signal writer behind a runtime-neutral isolation port (robustness review R1-08, R2-05)

**Choice:**
- `DispositionSignalWriter` (cognition) is the only neocortex code that mutates `DispositionSignalStore`. That covers the recorder, the phase's decay and clear, and recovery.
- Each call takes a per-`TenantAgentKey` lock and then runs inside `IsolatedTransactions.requiresNew` (cognition-api port), so the commit happens inside the lock.
- Port implementations: `JtaIsolatedTransactions` (JTA suspend/begin/commit/resume), `DirectIsolatedTransactions` (no JTA), and a Spring `TransactionTemplate(REQUIRES_NEW)` in agency-spring.

**Alternatives:**
- Gate the phase off until eidos#241 lands (the reviewer's recommendation). *Rejected:* it ships #1060 inert in production again, and the close criterion forbids that. It also leaves correctness hostage to another repo's timeline, when neocortex can remove its own lost updates locally.
- A separate `@Transactional(REQUIRES_NEW)` bean. *Rejected in favour of the port:* it still depends on interceptor or proxy configuration that differs per runtime.
- `@Version` retries in neocortex. *Not available:* the entity is Eidos's.

**Rationale:**
- Under the single-instance contract (#1104), in-JVM serialisation makes neocortex's writers race-free against the current Eidos stores.
- Programmatic isolation behaves identically under CDI and Spring, and is testable in both.
- eidos#241 stays the store-level fix for multi-instance deployments and foreign writers. It is not blocking.

**Status:** captured (robustness round 3)

## D21: A thrown decay is compensated; only a crash loses periods (robustness review R3-01)

**Choice:** Write the marker first (D17). If `decay` throws, a `transition` restores the previous `decayedThrough`, but only if the marker is still this run's. The periods stay owed and are caught up as `retention^k` on recovery.

**Rationale:**
- Marker-first protects against persistent MindMap failure.
- Compensation protects against persistent signal-store failure.
- A crash, or a failed compensation, remains the only loss. It is bounded by one run's `k`.

**Status:** captured (robustness round 3)

## D22: Under (A), a re-authored profile makes the lived profile dormant; cleanup is confirmed after one period (robustness review R3-02; refines D16)

**Choice:**
- The lived profile is never deleted on a fingerprint mismatch. Readers ignore it while the fingerprints differ, it reactivates on revert, and it is overwritten only by the next committed transition.
- `ReflectionLedger.reauthor` tracks the mismatch. It is reconciled only at due reflections. Once the mismatch has held for one `reflectionPeriod`, confirmation clears the signal epoch and resets `lastTransitionAt`.
- An unconfirmed mismatch defers any `Evolved`.

**Alternatives:** D16's immediate durable deletion. *Rejected:* it adds no correctness (the readers are already pure), adds irreversibility under rollback, revert or typo, and costs a `findById` on every run.

**Rationale:** D16's principle stands, that authored identity wins. It is enforced by the pure read rule; deleting the lived profile was never needed to enforce it.

**Cross-cutting round 1 amendment (R1-06, with D23):** the signal epoch is keyed to the authored fingerprint.
- `clear` runs when a mismatch is first detected and again when a revert is detected.
- Confirmation no longer clears; it only resets `lastTransitionAt`.
- **Why.** The recorder ranks against the authored profile (D23). Any authored change in either direction leaves counts credited to the wrong role. Round 3's "signals intact on revert" kept counts ranked against the edited profile.
- **Cost.** An under-count of at most one detection lag per change.

**Status:** captured (robustness round 3), conditional on R1-01 = A; amended (cross-cutting round 1)

## D23: Activation targets are anchored to the authored profile (cross-cutting R1-01)

**Choice:** Pressure sources rank dominant and auxiliary against the **authored** descriptor: POSITIVE activates the authored dominant, NEGATIVE the authored auxiliary. The probe still evaluates the lived descriptor.

**Alternatives:**
- **Rank against the lived profile (ROB-R2-02, rev 2).** Rejected. It has no fixed point under negative-leaning input: after a swap, NEGATIVE reinforces the new auxiliary, which is the old dominant. The type alternates at the rate bound forever (verified against `DefaultDispositionHealth`/`DefaultDispositionEvolution`).
- **A neocortex reversal refractory** (reviewer option ii). Rejected. It only lengthens the cycle, and it second-guesses validity (D6).
- **"Strain activates the demoted term"** (reviewer option i). Rejected. The demoted term *is* the lived auxiliary, so this is the rev-2 rule.
- **Accept the oscillation** (reviewer option iii). Rejected. It contradicts "lasting change".

**Rationale:**
- Production valence is mood-derived, not feedback on the function in use. Unattributed valence is meaningful only against a fixed reference, and authored identity is the agent's only fixed reference.
- One-sided and leaning input then reaches a fixed point. Over-reinforcement of the adapted dominant, which Eidos checks first, holds it there.
- D13 (polarity by target selection) is kept.

**Residual:** a dead zone in the Eidos swap criteria, where both arrangements qualify. Filed as eidos#242. Until it lands, transitions there are bounded by D24's rate bound.
**Status:** captured (cross-cutting round 1)

## D24: JPAF safety bounds committed change; no halt (cross-cutting R1-02; supersedes D7's JPAF half)

**Choice:**
- Delete the L2 drift halt (`halted`, `Halted`, `l2Ceiling`, `PERSONALITY_HALT`). Every `Drifted` is `Drifting`, and recording is never gated by pressure.
- `relationalComplexity` scales the committed-transition rate bound: `minTransitionInterval / rc`. rc = 0 is its limit (disabled).

**Rationale** (each point verified):
1. `probe` returns `EvolutionPending` before the generic `Drifted`, so the halt never prevented a transition.
2. Count-adjusted weights are read only by the evaluator. Derived cognition composes committed state only.
3. Pending pressure is bounded by decay.

So the halt's only effects were a valence filter and attention flooding:
- contented agents halted every few days;
- at rc = 0.8 with 2 NEG per period, the halt blocked the swap permanently.

The PEO rationale for rc ("tolerating larger personality adjustments") concerns committed change, which is now what rc governs.

**Alternatives:**
- **Halt only on non-dominant drift** (reviewer option i). Rejected: balanced input still halts before the swap point.
- **Scope the gate to `mostActivated`** (option ii). Rejected: it still filters by valence.
- **Halt hysteresis** (option iii). Rejected: the reviewer notes it keeps the valence filter.

**Status:** captured (cross-cutting round 1)

## D25: The derived view pulls lived state; nobody publishes (cross-cutting R1-03)

**Choice:**
- An `EffectiveCognitiveDefaults` slot is fresh only while both its base version and its state version (`PersonalityStateSource.stateVersion`, load-through, never creating) are current. Otherwise it is re-derived on read.
- `updateState` and every publish call are deleted.

**Alternatives:**
- **Every writer publishes its own result** (the reviewer's fix). Rejected: correctness depends on each writer remembering, which is how R1-03 happened. It also keeps two verified defects:
  - the drift gate leaves an idle agent's decayed displacement unpublished;
  - base-first installation loses a newer state snapshot to a concurrent `updateBase`.
- **`transition` pushes.** Rejected: it creates a construction cycle between the two `@Singleton` producers.

**Rationale:** It is the same staleness mechanism the base layer already uses, and every committed change is visible at the next read by construction.
**Status:** captured (cross-cutting round 1)

## D26: Striped, never-evicted locks; no eviction in #1060; enumeration is registry ∪ persisted (cross-cutting R1-04)

**Choice:**
- `PersonalityStateService` and `DispositionSignalWriter` each use a fixed `ReentrantLock[]` (256 stripes), indexed by `TenantAgentKey`.
- #1060 evicts nothing and closes no part of #1089. The requirements for #1089 are recorded on the issue.
- `DispositionEvolutionPhase` enumerates registry ∪ persisted agents.

**Rationale:**
- Rev 2's eviction had no driver, was defeated by per-run `transition`s, and could hand out two locks for one key, reopening STR-R2-01 and R1-08.
- Striping bounds lock memory and removes the race by construction.
- The union lets recovery and the audit outbox drain for agents that left the registry.

**Status:** captured (cross-cutting round 1)

## D27: The signal epoch has its own key, `epochFingerprint`, for every agent (cross-cutting R2-02; amends D22)

**Choice:**
- `ReflectionLedger.epochFingerprint` records the authored fingerprint the current signal epoch is being recorded under. It is set at the first due reflection without clearing.
- Step 0a(b) clears the epoch whenever `fingerprint(authored) ≠ epochFingerprint`, for every agent, edits and reverts alike.
- The lived-profile reconciliation (`reauthor`, D22) runs only when `livedProfile ≠ null`, and no longer clears anything.

**Why:**
- D23 makes every agent rank against the authored profile, so the signal epoch must be keyed on the authored fingerprint for every agent.
- Round 1 detected changes with `authored fp ≠ lived fp`, which is undefined when `livedProfile` is null:
  - read one way, an unevolved agent's edit never clears, so a swap is driven by mis-credited counts;
  - read the other way, every unevolved agent is spuriously "re-authored" and its first transition is locked out for about 31 days.
- The two questions (which lived profile is valid; which ranking the counts were earned under) have different keys.

**Status:** captured (cross-cutting round 2)

## D28: Recorder activations are coalesced in memory; the hot path never waits and nothing is dropped (cross-cutting R2-03; amends D20)

**Choice:**
- `DispositionSignalWriter.enqueue` increments a per-agent, per-term `AtomicLong` and makes one non-waiting `tryLock()`.
  - If the stripe is free, it drains the agent's pending counts in one isolated batch.
  - Otherwise it returns, leaving the counts for the next flush.
- `drain` and `decay` drain under a blocking lock. `clear` discards the pending counts at the epoch boundary.
- A failed batch adds its counts back. `@PreDestroy` flushes on graceful shutdown.

**Alternatives:** Round 1's `tryLock(recordLockWait)` with a drop on timeout. *Rejected:* valence is per-agent mood, so concurrent sessions drop the *same* term during contention bursts, which reproduces the R1-08 hottest-row bias.

**Rationale:**
- Nothing is lost except on a process crash, which is the same class as the accepted epoch-boundary under-count.
- A signal-store outage buffers activations instead of losing them.

**Status:** captured (cross-cutting round 2)

## D29: Derived-view freshness keys on a quantised composition version (cross-cutting R2-04; amends D25)

**Choice:**
- `PersonalityState.compositionVersion` increments only when the commit changes the composition key: per-facet resting and effective offsets on the `EPSILON_PUBLISH` grid, plus the exact lived profile.
- Slot freshness compares it, not the per-commit `version`.

**Alternatives:**
- A raw per-commit version. *Rejected:* every participant tick and deformation run commits, so every ticking agent would be re-derived on every read after a tick.
- "Changed by ≥ ε since the last bump". *Rejected:* it needs a stored reference snapshot per agent, and a grid does not.

**Rationale:**
- It restores and tightens the `isDirty` cost profile.
- The slot lag is bounded by ε per facet.
- Slow drift is always eventually published.

**Status:** captured (cross-cutting round 2)

## D30: D23's fixed points are conditional on Eidos parameters; neocortex observes reversals, not parameters (cross-cutting R2-01; amends D23)

**Choice:**
- **The precondition is stated.** The §[X1] stability claims hold for `OVER_REINFORCEMENT_THRESHOLD` T ≤ 0.50 at δ = 0.06. For T > 0.50 there is a volume-independent alternation band of width 2T − 1.
- **Neocortex observes reversals.** `ReflectionLedger.lastTransitionFromLabel` is set at `closeEpoch`. A transition back to the pre-previous label journals `DispositionReversal` and increments `personality.disposition.reversals`. This is observability only.
- **The fix belongs to Eidos.** eidos#242 is extended with the T analysis and a property test over (T, δ).

**Alternatives:** The reviewer's per-tenant precondition journal and gauge, raised when T > 0.50. *Rejected:*
- it is a false alarm for tenants whose input never enters the band;
- it misses the T = 0.50 moderate-volume dead zone;
- it couples neocortex to one Eidos preference and to the shape of Eidos's criteria.

The reversal signal is exactly the defect, whatever causes it.

**Status:** captured (cross-cutting round 2)

**Cross-cutting round 3 amendment to D30 (R3-01).** A single reversal is the adapt-and-return lifecycle that D23 designs, so it is not a defect.
- `DispositionReversal` stays as an informational journal entry and counter.
- `ReflectionLedger.reversalStreak` counts consecutive reversals, each committed within two rc-scaled bounds of the previous transition. A reversal after a longer stay restarts the streak at 1, and a non-reversal resets it to 0.
- Re-author confirmation resets the streak and `lastTransitionFromLabel`.
- Only `streak ≥ 2` increments the alerting counter `personality.disposition.oscillations`.

**Alternatives:**
- **The reviewer's streak without spacing.** *Rejected:* it alerts on legitimate seasonal cycles, such as an A→B→A→B sequence months apart.
- **Renaming to `DispositionReturned` with no alerting.** *Rejected:* it loses the symptom signal that made Rule 3 preferable to a parameter check.

**Status:** amended (cross-cutting round 3)
