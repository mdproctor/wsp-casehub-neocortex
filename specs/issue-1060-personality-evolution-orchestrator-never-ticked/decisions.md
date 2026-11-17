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
**Status:** captured (rev 2)

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

**Status:** captured (robustness round 2)
