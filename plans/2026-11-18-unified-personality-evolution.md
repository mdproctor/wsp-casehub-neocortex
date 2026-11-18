# Unified Personality Evolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1060 — PersonalityEvolutionOrchestrator is never ticked
**Issue group:** #1060, #1080 (absorbed)

**Goal:** Wire personality evolution into the cognitive tick lifecycle with a unified
outcome infrastructure for both JPAF disposition profiles and PID-5 facets,
using option (A) — neocortex stores lived results, Eidos keeps authored identity only.

**Architecture:** Two personality families (JPAF and PID-5) share outcome infrastructure
(store of record in `PersonalityState`, pull-based propagation via `compositionVersion`,
consolidation cadence, audit) but keep their native accumulation and evaluation dynamics.
`PersonalityStateService` (renamed from `SituationalStateService`) is the single serialised
owner of all per-agent evolution state. `EffectiveCognitiveDefaults` pulls lived state
lazily via `compositionVersion`-keyed freshness, replacing the deleted `updateState`.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI, Eidos API (evaluation SPIs), MindMap (state persistence)

**Store-of-record decision:** Option (A) — neocortex stores lived results.

## Global Constraints

- Java 21 source (Java 26 JVM)
- `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn` for all builds
- Every commit references an issue (`Refs #1060`)
- TDD: failing test first, then implementation
- IntelliJ MCP for all code navigation and structural editing
- Spec reference: `wsp-casehub-neocortex/specs/issue-1060-personality-evolution-orchestrator-never-ticked/2026-11-17-unified-personality-evolution-design.md`
- All new types use option (A) text from the spec; (B) text is ignored

---

## Batch 1: Foundation — PersonalityStateService + Core Types

After this batch: `PersonalityStateService` exists with striped locking and `transition()` API.
`ReflectionLedger`, updated `PersonalityStateSnapshot`, and new config types compile. Existing
tests still pass (rename is mechanical).

### Task 1: Rename SituationalStateService → PersonalityStateService

**Files:**
- Rename: `SituationalStateService` → `PersonalityStateService` (use `ide_refactor_rename`)
- Modify: all references across the codebase (rename handles this)
- Test: existing `SituationalStateServiceTest` (renamed)

**Interfaces:**
- Produces: `PersonalityStateService` class name used by all subsequent tasks

- [ ] **Step 1: Verify existing tests pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SituationalStateServiceTest`

- [ ] **Step 2: Rename via IntelliJ**

Use `ide_refactor_rename` on `SituationalStateService` → `PersonalityStateService`.
This updates all references across the project.

- [ ] **Step 3: Run affected tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: all pass (rename is mechanical)

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "refactor: rename SituationalStateService → PersonalityStateService

Refs #1060"
```

### Task 2: Add striped locking and transition() API to PersonalityStateService

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/PersonalityStateService.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/TenantAgentKey.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/situational/PersonalityStateServiceTest.java`

**Interfaces:**
- Produces: `transition(tenantId, agentId, now, UnaryOperator<PersonalityState>)` → `PersonalityState`
- Produces: `read(tenantId, agentId, now)` → `PersonalityState`
- Produces: `compositionVersion(tenantId, agentId)` → `long`
- Produces: `agentIds(tenantId)` → `Set<String>`
- Produces: `TenantAgentKey(tenantId, agentId)` record

- [ ] **Step 1: Write failing test for transition()**

Test that `transition` applies the operator atomically and increments `version`.

- [ ] **Step 2: Implement TenantAgentKey and striped locking**

`TenantAgentKey` record with `hashCode()` spread for stripe indexing.
Fixed `ReentrantLock[256]` array in `PersonalityStateService`, never evicted (D26).

- [ ] **Step 3: Implement transition()**

Under the stripe lock: load-or-create, apply `fn`, increment `version`, compute
`compositionVersion` bump, persist, replace cache. `persist`/`loadOrCreate`/`currentState`
become private (D10).

- [ ] **Step 4: Write failing test for compositionVersion()**

Test that `compositionVersion` bumps only when the composed view changes (D29).
Verify it does NOT bump when `promoted` changes with `homeOffset` compensating.

- [ ] **Step 5: Implement compositionVersion()**

Quantised key: `round((promoted + homeOffset)/EPSILON_PUBLISH)` per facet, plus
`livedProfile` (exact comparison). Bump only when key differs (D29).
Load-through on cache miss, never creates.

- [ ] **Step 6: Write interleaving test (spec §[S2])**

Inject a latch inside the mutation between the deformation phase's load and commit.
Assert both writers' effects survive and none is applied twice.

- [ ] **Step 7: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat(#1060): add striped locking and transition() API to PersonalityStateService

D10, D26, D29. Striped ReentrantLock[256], transition() as sole mutation path,
compositionVersion for pull model.

Refs #1060"
```

### Task 3: ReflectionLedger + PersonalityState additions + Config types

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/ReflectionLedger.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/PersonalityState.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/FacetState.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/personality/DispositionEvolutionConfig.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/ReflectionOutcome.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PersonalityStateSnapshot.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/DynamicsConfig.java`
- Test: unit tests for ReflectionLedger serialisation round-trip

**Interfaces:**
- Produces: `ReflectionLedger` with 11 fields persisted as `jpaf.*` properties
- Produces: `DispositionEvolutionConfig(reflectionPeriod, retentionPerReflection, minTransitionInterval)`
- Produces: `ReflectionOutcome` sealed hierarchy
- Produces: `FacetState` with `saturatedSince`, `promoted`, `cappedSince`
- Produces: `PersonalityStateSnapshot` with `livedProfile`, `compositionVersion`, `promoted` on `FacetDisplacement`

- [ ] **Step 1: Write ReflectionLedger with property serialisation tests**

11 fields: `lastReflectionAt`, `lastTransitionAt`, `pendingEvolution`, `disabled`,
`decayedThrough`, `reauthor`, `epochFingerprint`, `lastTransitionFromLabel`,
`reversalStreak`, `auditOutbox`, `inert`. All persisted as `jpaf.*` properties on
the PERSONALITY_STATE MindMap node.

- [ ] **Step 2: Add reflection() to PersonalityState**

`PersonalityState.reflection()` returns the `ReflectionLedger` component.
`withReflection(ReflectionLedger)` for immutable updates.
Add `version` and `compositionVersion` fields.

- [ ] **Step 3: Add FacetState promotion fields**

`saturatedSince` (Instant, nullable), `promoted` (double), `cappedSince` (Instant, nullable).

- [ ] **Step 4: Update PersonalityStateSnapshot**

Add `LivedProfile livedProfile` (nullable), `compositionVersion` (long).
`FacetDisplacement` gains `promoted` (double). Defensive copies.

- [ ] **Step 5: Create DispositionEvolutionConfig**

Record with `reflectionPeriod` (24h), `retentionPerReflection` (0.8), `minTransitionInterval` (30d).
MicroProfile config keys: `casehub.cognition.personality.*`.

- [ ] **Step 6: Create ReflectionOutcome sealed type**

`Stable`, `Drifting(magnitude)`, `Evolved(previousLabel, newLabel, newProfile, triggerType)`,
`Dampened(decayFactor)`, `Deferred(previousLabel, newLabel, triggerType, eligibleAt)`,
`Disabled(rc)`, `Failed(step, message)`.

- [ ] **Step 7: Add DynamicsConfig promotion fields + validation**

`promoteFraction` (0.8), `promoteDwell` (30d), `promotionBudget` (0.20).
7 validation rules in compact constructor (spec §DynamicsConfig).

- [ ] **Step 8: Run all affected module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition,cognition-api,cognitive-index`

- [ ] **Step 9: Commit**

```bash
git add -A && git commit -m "feat(#1060): ReflectionLedger, config types, state snapshot additions

D12 (ledger as component), D29 (compositionVersion). Foundation types for
both JPAF and PID-5 evolution pipelines.

Refs #1060"
```

---

## Batch 2: Composition Layer — LivedComposition + Pull Model

After this batch: `EffectiveCognitiveDefaults` uses the pull model. `updateState` is deleted.
`LivedComposition` composes authored + lived profiles. The composition is tested end-to-end.

### Task 4: LivedComposition + LivedProfile (cognitive-index)

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/LivedComposition.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/LivedProfile.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/LivedCompositionTest.java`

**Interfaces:**
- Produces: `LivedComposition.fingerprint(List<WeightedTerm>)` → `String`
- Produces: `LivedComposition.profile(List<WeightedTerm> authored, LivedProfile lived)` → `List<WeightedTerm>`
- Produces: `LivedComposition.compose(DescriptorView authored, PersonalityStateSnapshot lived, boolean includeDisplacement)` → `DescriptorView`
- Produces: `LivedProfile(List<WeightedTerm> profile, String authoredFingerprint)` record

- [ ] **Step 1: Write failing tests**

Test fingerprint determinism (sorted terms, 4dp weights, SHA-256).
Test profile composition: matching fingerprint → lived; mismatched → authored.
Test compose: facet resting = `clamp01(baseline + promoted + homeOffset)`.

- [ ] **Step 2: Implement LivedComposition**

Pure static utility. `fingerprint()` sorts terms by name, formats weights to 4dp,
SHA-256 hashes. `profile()` compares fingerprints. `compose()` replaces
`composeFacets` logic with the full (A) composition rule.

- [ ] **Step 3: Write authored-edit tests (D16, spec §Authored edits)**

Authored profile edit: fingerprint mismatch → authored wins immediately.
Revert: fingerprint matches again → lived active.
Facet re-authoring: `promoted` composes over new baseline.

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

### Task 5: Pull model in EffectiveCognitiveDefaults

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/EffectiveCognitiveDefaults.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PersonalityStateSource.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/EffectiveCognitiveDefaultsTest.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/SituationalPersonalityParticipant.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/SituationalDeformationPhase.java`

**Interfaces:**
- Consumes: `LivedComposition.compose()`, `PersonalityStateSource.compositionVersion()`
- Produces: Pull-based freshness: `forAgent()` checks both `baseVersion` and `compositionVersion`

- [ ] **Step 1: Write failing test for compositionVersion-based freshness**

A state change that bumps `compositionVersion` causes the next `forAgent()` to re-derive.
A state change within the same grid cell does NOT cause re-derivation.

- [ ] **Step 2: Add compositionVersion() to PersonalityStateSource**

```java
long compositionVersion(String tenantId, String agentId);
```

- [ ] **Step 3: Modify Slot freshness check**

`isStale` checks both `baseVersion < currentBaseVersion` and
`compositionVersion < stateSource.compositionVersion(t, a)`.

- [ ] **Step 4: Replace composeFacets with LivedComposition.compose**

Delete the private `composeFacets` method. `deriveSlot` calls
`LivedComposition.compose(baseView, stateSnap, false)` for resting,
`LivedComposition.compose(baseView, stateSnap, true)` for effective.

- [ ] **Step 5: Delete updateState()**

Remove the method. Remove calls from `SituationalPersonalityParticipant`
and `SituationalDeformationPhase` (they stop publishing; D25).

- [ ] **Step 6: Write pull contract test**

After a `transition` that changes homeOffset beyond EPSILON_PUBLISH,
the next `forAgent()` reflects the new value without any publish call.

- [ ] **Step 7: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index,cognition`

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat(#1060): pull model — compositionVersion freshness, delete updateState

D25 (pull), D29 (quantised compositionVersion). EffectiveCognitiveDefaults
lazily re-derives when compositionVersion changes. No writer publishes.

Refs #1060"
```

---

## Batch 3: Signal Recording — Writer + Recorder

After this batch: CDI events fire pressure signals into the JPAF signal pipeline.
`DispositionSignalWriter` coalesces activations. `DispositionSignalRecorder` observes
`RelationshipRecorded` and `InteractionAppraised` events. Existing signal recording
(which was inert) is replaced.

### Task 6: IsolatedTransactions SPI + DispositionSignalWriter

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/personality/IsolatedTransactions.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/DirectIsolatedTransactions.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/JtaIsolatedTransactions.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/DispositionSignalWriter.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/DispositionSignalWriterTest.java`

**Interfaces:**
- Produces: `IsolatedTransactions.requiresNew(Runnable)` SPI
- Produces: `DispositionSignalWriter.enqueue(tenantId, agentId, List<String> terms)` — non-blocking
- Produces: `DispositionSignalWriter.drain(tenantId, agentId)` — blocking, batch write
- Produces: `DispositionSignalWriter.decay(tenantId, agentId, double factor)` — drain then decay
- Produces: `DispositionSignalWriter.clear(tenantId, agentId)` — discard pending, clear store

- [ ] **Step 1: Write failing test for coalescing behaviour**

8 threads × 100 enqueues on the same agent. After drain, the store holds exactly 800
total activations across the terms (spec §Robustness R3, test 13).

- [ ] **Step 2: Implement IsolatedTransactions + DirectIsolatedTransactions**

`@FunctionalInterface`: `void requiresNew(Runnable work)`.
`DirectIsolatedTransactions` runs inline. `JtaIsolatedTransactions` wraps `TransactionManager`.

- [ ] **Step 3: Implement DispositionSignalWriter**

Striped `ReentrantLock[256]` (own array, not shared with PersonalityStateService).
Pending buffer: `ConcurrentHashMap<TenantAgentKey, ConcurrentHashMap<String, AtomicLong>>`.
`enqueue` uses `tryLock` — on fail, adds to pending without blocking (D28).
`drain` acquires lock, swaps pending map, batch-writes to `DispositionSignalStore`.
`clear` discards pending under lock, then clears store.

- [ ] **Step 4: Write signal-store outage test (spec §R3)**

`drain` throws → activations retained in buffer. Next drain delivers them.
Compensation: `decay` that throws after drain → restore `decayedThrough` marker.

- [ ] **Step 5: Run tests**

- [ ] **Step 6: Commit**

### Task 7: TraitActivation changes + DispositionSignalRecorder + InteractionAppraised

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/personality/TraitActivation.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/personality/TraitPressureSource.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/DispositionSignalRecorder.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/InteractionAppraised.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/InteractionPressureSource.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/RelationshipPressureSource.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/DispositionSignalRecorderTest.java`

**Interfaces:**
- Consumes: `DispositionSignalWriter.enqueue()`, `PersonalityStateService.read()`
- Produces: `DispositionSignalRecorder` CDI bean, `InteractionAppraised` event

- [ ] **Step 1: Modify TraitActivation — remove SignalValence**

`TraitActivation(String functionTerm)` only. D13: polarity encoded by target selection.
Add `default boolean relevant(E event)` to `TraitPressureSource`.

- [ ] **Step 2: Update RelationshipPressureSource for authored targeting (D23)**

POSITIVE → authored dominant term. NEGATIVE → authored auxiliary term.
Takes `DescriptorView` (authored descriptor). No valence in activation.

- [ ] **Step 3: Write failing test for recorder — NEUTRAL short-circuit**

`RelationshipRecorded` with `QualitySignal.NEUTRAL` → no descriptor lookup, no activations.

- [ ] **Step 4: Write failing test — authored targeting**

After a TI-NE → NE-TI swap, NEGATIVE interaction still increments `ne` (the authored auxiliary).

- [ ] **Step 5: Implement DispositionSignalRecorder**

`@ApplicationScoped`. `@Observes RelationshipRecorded` and `onInteractionAppraised()`.
Builds `Map<Class<?>, TraitPressureSource<?>>` at startup, fail-fast on duplicates.
Checks `stateService.read(...).reflection().disabled()` before recording.
Enqueues terms via `DispositionSignalWriter.enqueue()`.

- [ ] **Step 6: Create InteractionAppraised + InteractionPressureSource**

`InteractionAppraised(tenantId, agentId, subjectId, quality, at)`.
`InteractionPressureSource implements TraitPressureSource<InteractionAppraised>`.
Same JPAF mapping as RelationshipPressureSource.

- [ ] **Step 7: Modify CognitionCore.recordInteraction**

Move quality computation out of `if (subjectId != null)` block.
Emit `InteractionAppraised` to the recorder (D11).

- [ ] **Step 8: Run all tests**

- [ ] **Step 9: Commit**

---

## Batch 4: PID-5 Promotion

After this batch: PID-5 facets graduate from `homeOffset` to `promoted` when sustained
saturation exceeds thresholds. `SituationalDeformationPhase` runs at `@Priority(46)`.

### Task 8: PersonalityStateIntegrator.promotionCandidates()

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/PersonalityStateIntegrator.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/situational/PersonalityStateIntegratorPromotionTest.java`

**Interfaces:**
- Produces: `promotionCandidates(PersonalityState, Map<String, Double> baselines, Instant now)` → `Map<String, PromotionCandidate>`

- [ ] **Step 1: Write failing test — dwell clock**

Facet with `|homeOffset| ≥ promoteFraction × dMax` for exactly `promoteDwell`: candidate returned.
One day short: no candidate.

- [ ] **Step 2: Write failing test — budget cap**

Facet with `|promoted + homeOffset| > promotionBudget`: not a candidate.

- [ ] **Step 3: Write failing test — delta computation (A)**

`delta = clamp01(baseline + promoted + homeOffset) − (baseline + promoted)`.
Verify exact value for authored baseline 0.85, promoted 0.10, homeOffset 0.09.

- [ ] **Step 4: Write failing test — continuity**

Resting score `(baseline + promoted + homeOffset)` is identical before and after promotion.

- [ ] **Step 5: Implement promotionCandidates()**

Pure method. Iterates facets, checks saturation tracking, computes candidates.
`baselineFor` takes real per-facet baselines from `DescriptorView`.

- [ ] **Step 6: Run tests**

- [ ] **Step 7: Commit**

### Task 9: SituationalDeformationPhase promotion step

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/SituationalDeformationPhase.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/situational/SituationalDeformationPhasePromotionTest.java`

**Interfaces:**
- Consumes: `PersonalityStateIntegrator.promotionCandidates()`, `PersonalityStateService.transition()`

- [ ] **Step 1: Set @Priority(46)**

Was unset (MAX_VALUE). Now explicitly `@Priority(46)` — after all personality-reading
phases, before `DispositionEvolutionPhase` at 50.

- [ ] **Step 2: Write failing test — promotion via transition**

One `transition` call: `homeOffset -= delta`, `promoted += delta`, `saturatedSince := null`.

- [ ] **Step 3: Write failing test — crash recovery (D8)**

If `transition` succeeds but the process crashes before the next operation,
the state is consistent: no double-counted promotion.

- [ ] **Step 4: Implement promotion step**

After existing `closeHour` logic, call `integrator.promotionCandidates()`.
For each candidate, apply via `stateService.transition()`.
Under-count ordering (D8): if the write fails, the homeOffset stays — no double count.

- [ ] **Step 5: Run all cognition tests**

- [ ] **Step 6: Commit**

---

## Batch 5: JPAF Evaluation — DispositionEvolutionPhase

After this batch: the JPAF evaluation pipeline runs during consolidation. Accumulated signals
are evaluated per-agent, transitions commit to lived state, CBR cases are recorded, and
attention signals fire.

### Task 10: EidosCognitiveProfileBridge.livedDescriptor + LivedDescriptors

**Files:**
- Modify: `cognitive-eidos/src/main/java/io/casehub/neocortex/cognitive/eidos/EidosCognitiveProfileBridge.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/LivedDescriptors.java`
- Test: `cognitive-eidos/src/test/java/io/casehub/neocortex/cognitive/eidos/EidosCognitiveProfileBridgeLivedTest.java`

**Interfaces:**
- Produces: `EidosCognitiveProfileBridge.livedDescriptor(AgentDescriptor authored, LivedProfile lived)` → `AgentDescriptor`
- Produces: `LivedDescriptors.compose(AgentDescriptor authored, PersonalityState state)` → `AgentDescriptor`

- [ ] **Step 1: Write failing test — livedDescriptor composition**

Authored TI-NE descriptor + lived NE-TI profile with matching fingerprint → descriptor with NE-TI weights.
Mismatched fingerprint → authored descriptor unchanged.

- [ ] **Step 2: Implement livedDescriptor**

Maps `DispositionValue` ↔ `WeightedTerm`, delegates to `LivedComposition.profile`, maps back,
rebuilds descriptor through `toBuilder()`.

- [ ] **Step 3: Implement LivedDescriptors**

Thin wrapper: extracts `LivedProfile` from `PersonalityState`, delegates to bridge.

- [ ] **Step 4: Run tests**

- [ ] **Step 5: Commit**

### Task 11: DispositionEvolutionPhase — the main consolidation phase

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/DispositionEvolutionPhase.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/DispositionEvolutionPhaseTest.java`

**Interfaces:**
- Consumes: `DispositionHealth`, `DispositionEvolution`, `AgentRegistry`, `CbrRecordStore`,
  `EffectiveCognitiveDefaults`, `PersonalityStateService`, `DispositionSignalWriter`,
  `DispositionEvolutionConfig`, `CognitiveJournal`, `Clock`
- Produces: `ConsolidationPhase` at `@Priority(50)`. `name()` = `"disposition-evolution"`.

This is the largest task — the full JPAF evaluation algorithm from spec §DispositionEvolutionPhase.
The algorithm has steps R (recovery), G (wall-clock gate), 0a (epoch/reauthor), D (decay),
0 (enablement), 2 (evaluate), 3 (commit), 4 (record).

- [ ] **Step 1: Write failing test — stable reflection**

Agent with no signals → `Stable`. Ledger `lastReflectionAt` advances by one period.

- [ ] **Step 2: Write failing test — wall-clock gate**

Agent whose `lastReflectionAt` is less than one period ago → skipped entirely.

- [ ] **Step 3: Write failing test — Evolved path with rate bound**

Signals that trigger `EvolutionPending` → `Evolved`. Transition committed to lived state.
Second evolution attempt within `minTransitionInterval / rc` → `Deferred`.

- [ ] **Step 4: Write failing test — recovery**

`pendingEvolution` in ledger → on next run, clear signals, close epoch. No duplicate commit.

- [ ] **Step 5: Write failing test — authored edit detection (D23, D27)**

Authored fingerprint change → epoch clears, signals reset. Lived profile goes dormant.

- [ ] **Step 6: Write failing test — reversal detection (D30)**

A→B→A transitions with streak counting. Oscillation counter increments at streak ≥ 2.

- [ ] **Step 7: Implement DispositionEvolutionPhase.run()**

Full algorithm per the spec pseudocode (steps R, G, 0a, D, 0, 2, 3, 4).
Per-agent `try/catch` for isolation. Uses `LivedDescriptors.compose()` for probe descriptor.
CBR transition case recording. Journal entries. Attention signals.

- [ ] **Step 8: Write failing test — Dampened**

`DispositionEvolution.evaluate()` returns `Dampened` → decay by factor, no transition.

- [ ] **Step 9: Write failing test — Disabled (rc = 0)**

Agent with `relationalComplexity = 0` → `Disabled`. No evaluation.

- [ ] **Step 10: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`

- [ ] **Step 11: Commit**

```bash
git add -A && git commit -m "feat(#1060): DispositionEvolutionPhase — JPAF evaluation consolidation phase

D6, D9, D12, D17-D18, D22-D24, D27, D30. Full JPAF pipeline: recovery,
wall-clock gate, epoch tracking, decay, evaluation, commit, rate bound,
reversal detection, authored edit handling.

Refs #1060"
```

---

## Batch 6: Production Wiring + Cleanup + Integration Tests

After this batch: the full personality evolution pipeline is production-wired. Old PEO is
deleted. Integration and end-to-end tests verify the complete flow.

### Task 12: Production wiring in CognitionDefaultBeans

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCoreFactory.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitivePipelineBuilder.java`
- Create or modify: `cognitive-eidos/.../IdentityChangePropagator.java` (non-evolution updates only under A)
- Modify: `mindmap-api/.../SignalCategory.java` — add `PERSONALITY_EVOLVED`

**Interfaces:**
- Produces: CDI beans for `EffectiveCognitiveDefaults`, `PersonalityStateService`,
  `DispositionSignalWriter`, `IsolatedTransactions`

- [ ] **Step 1: Add CDI producers to CognitionDefaultBeans**

`@Produces @DefaultBean @Singleton EffectiveCognitiveDefaults` — from registry, EidosDescriptorViewSource, PersonalityStateService.
`@Produces @DefaultBean @Singleton DispositionSignalWriter` — from store + IsolatedTransactions.
`@Produces @DefaultBean @Singleton IsolatedTransactions` — JTA when available, Direct fallback.
Delete `DefaultPersonalityStateSource` — `PersonalityStateService` now implements `PersonalityStateSource`.

- [ ] **Step 2: Wire recorder into CognitionCore**

`CognitivePipelineBuilder.dispositionSignalRecorder(DispositionSignalRecorder)`.
`CognitionCoreFactory` resolves `DispositionSignalRecorder` via `Instance<>`.

- [ ] **Step 3: Add SignalCategory.PERSONALITY_EVOLVED**

New enum value in mindmap-api.

- [ ] **Step 4: Run compilation check across all modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -DskipTests`

- [ ] **Step 5: Commit**

### Task 13: Delete PersonalityEvolutionOrchestrator + obsolete types

**Files:**
- Delete: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/PersonalityEvolutionOrchestrator.java`
- Delete: `cognition-api/src/main/java/io/casehub/neocortex/cognition/personality/EvolutionTick.java`
- Delete: `cognition-api/src/main/java/io/casehub/neocortex/cognition/personality/PersonalityEvolutionConfig.java` (replaced by `DispositionEvolutionConfig`)
- Delete: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DefaultPersonalityStateSource.java`
- Modify: test files referencing deleted types
- Delete: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/PersonalityEvolutionOrchestratorTest.java`

- [ ] **Step 1: Delete PEO and EvolutionTick via ide_refactor_safe_delete**

Verify no remaining references. Update any tests that import deleted types.

- [ ] **Step 2: Delete PersonalityEvolutionConfig**

Replaced by `DispositionEvolutionConfig`.

- [ ] **Step 3: Delete DefaultPersonalityStateSource**

`PersonalityStateService` now implements `PersonalityStateSource`.

- [ ] **Step 4: Compile check**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -DskipTests`

- [ ] **Step 5: Commit**

### Task 14: Integration + End-to-End Tests

**Files:**
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/PersonalityEvolutionIntegrationTest.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/PersonalityEvolutionE2ETest.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/JpafTrajectoryTest.java`

**Interfaces:**
- Consumes: all types from Batches 1-5

- [ ] **Step 1: CDI wiring test (spec test group 7)**

`@QuarkusTest` or equivalent: `EffectiveCognitiveDefaults` resolves, scheduler lists both
personality phases, core has recorder, no stubs for required beans.

- [ ] **Step 2: Integration test (spec test group 6)**

Events → activations → reflection → Evolved → `forAgent()` reflects the change.
Uses real Eidos SPIs (`DefaultDispositionHealth`, `DefaultDispositionEvolution`).
PID-5 sustained displacement → promotion.

- [ ] **Step 3: End-to-end test (spec test group 8)**

`recordInteraction` with negative mood → consolidation tick → `forAgent()` returns
swapped profile → tick → evict slot → restart → lived profile still visible.
Pull contract: no publish, just compositionVersion bump.

- [ ] **Step 4: 240-day trajectory tests (spec test group 14)**

6 scenarios × 3 rc values against real Eidos SPIs:
- Pure NEGATIVE 5/period: one transition, no return
- Pure POSITIVE 3/period: 0 transitions
- Mixed 3+5: swap within 2 periods, then stable
- Positive after adaptation: return once
- Dead zone 5+5: transitions spaced ≥ `minTransitionInterval / rc`
- Threshold sweep: T=0.55 and T=0.60 alternation

- [ ] **Step 5: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "test(#1060): integration, E2E, and 240-day trajectory tests

Covers spec test groups 6-8, 14. Full pipeline verification with real
Eidos SPIs, pull contract, slot eviction/restart, and multi-period dynamics.

Refs #1060"
```

---

## References

- [2026-11-17-unified-personality-evolution-design.md] — design spec (rev 2 + 12 review rounds)
- [PersonalityEvolutionOrchestrator.java] — existing code being replaced
- [PersonalityEvolutionOrchestratorTest.java] — behavioural parity reference
- [EffectiveCognitiveDefaults.java] — pull model target
- [SituationalPersonalityParticipant.java] — PID-5 displacement pipeline
- [SituationalDeformationPhase.java] — PID-5 consolidation + promotion host
- [PersonalityStateIntegrator.java] — PID-5 integration + promotion candidates
- [CognitionCore.java] — InteractionAppraised source
- casehubio/neocortex#1060 — focal issue
- casehubio/neocortex#1080 — absorbed (IdentityChangePropagator, non-evolution only under A)
- casehubio/neocortex#1082 — prerequisite (situational participant wiring)
- casehubio/neocortex#1063 — prerequisite (scheduler starvation)
