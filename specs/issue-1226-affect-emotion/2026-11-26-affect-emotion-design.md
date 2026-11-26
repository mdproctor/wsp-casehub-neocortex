# SE6: Affect & Emotion — Design Spec

**Issue:** casehubio/neocortex#1226
**Parent:** #1220 (Cognitive Review Epic)
**Branch:** `issue-1226-affect-emotion`
**Modules:** cognition (mood/, drive/, appraisal/, regulation/, gut/, salience/), cognition-api, eidos/api
**After:** SE2 (#1222) — CAPS rework landed

## Goal

Fix 14 bugs in the affect and emotion pipeline that cause mood to pin at extremes, drives to ignore personality, regulation to suppress positive emotions, and appraisal to miss half the emotion vocabulary.

## Batch 1: Mood Mechanics (C2, C3, C4, C20)

Mood is the foundation — drives, regulation, and appraisal all consume it. Fix first.

### C2: Rate-limit mood deltas (MoodOrchestrator)

**Problem:** Emotion PAD deltas are summed raw then clamped. Two strong emotions (+0.8 each) sum to +1.6, clamped to 1.0. With a 4-hour decay constant, mood pins at ±1.0 and never recovers at conversational pace.

**Fix:** Replace raw sum with **direction-aware** asymptotic approach. In `MoodOrchestrator.doTick()`, change the accumulation loop:

```java
// Before: p += signal.pleasureDelta();
// After: direction-aware dampening — only signals pushing further from
// the effective baseline are dampened; recovery signals apply at full strength.
double effectiveBaseline = config.baseline().pleasure() + goalBiasPleasure;
double displacement = p - effectiveBaseline;
double remaining = config.maxDisplacement() - Math.abs(displacement);
double headroom = Math.max(0.0, remaining / config.maxDisplacement());

double delta = signal.pleasureDelta();
boolean pushingAway = (delta > 0 && displacement >= 0) || (delta < 0 && displacement <= 0);

p += pushingAway ? delta * headroom : delta;
```

Apply same pattern to arousal and dominance (using their respective effective baselines). The `goalBiasPleasure` (and `goalBiasArousal`, `goalBiasDominance`) come from the goal bias set by `GoalEmotionMoodBridge` (C4 fix). Existing `clampAxis()` after the loop prevents overshooting ±maxDisplacement.

The direction-aware approach means:
- **Reinforcement** (pushing further from effective baseline): dampened as mood approaches limits — prevents pinning at extremes
- **Recovery** (pulling toward effective baseline): undampened — a positive signal can fully counteract negative mood without suppression

Also shorten default decay constant from 4 hours to 20 minutes (`MoodConfig` default). **Rationale for 20 minutes:** At conversational pace (messages every 1–5 minutes), a 4-hour time constant means mood barely decays between messages — 2 minutes of elapsed time decays <1% (factor `e^(-2/240) ≈ 0.992`). Mood from one interaction lingers all day (3×τ = 12 hours for 95% decay). At 20 minutes, mood responds to recent conversational context: 95% decay within 1 hour of silence, while still persisting meaningfully during a 30-minute conversation (60% retained after 10 minutes). `MoodConfig` is per-agent configurable, so agents with different interaction cadences can override.

### C3: Decay before signal (MoodOrchestrator)

**Problem:** Decay uses elapsed time since last tick. After a 2-hour idle gap, a fresh emotion signal is immediately decayed by 2 hours. `MoodDecay.decayAxis` erases ~40% of the shift.

**Fix:** Swap the order in `doTick()`: decay the pre-signal mood first using elapsed time, then apply new signals to the decayed state. Lines 102-112 (decay) must execute before lines 83-96 (signal accumulation).

### C4: Goal emotions as set-point bias (GoalEmotionMoodBridge)

**Problem:** Every tick, all active goal emotions are intensity-weighted-averaged into a `DirectShift` delta and added to mood. The magnitude depends on specific emotion intensities and PAD projections (not a fixed +0.3), but standing emotions are re-recorded as fresh deltas every tick regardless, pushing mood persistently in one direction.

**Fix (D2):** Replace `record(DirectShift)` with a `setGoalBias(MoodState)` method on `MoodOrchestrator`. Goal emotions compute a standing PAD bias. `MoodDecay` decays toward `baseline + goalBias` instead of bare `baseline`. `GoalEmotionMoodBridge` calls `setGoalBias()` only when goal set changes, not every tick.

Add to `MoodOrchestrator`:
```java
void setGoalBias(String agentId, String tenantId, MoodState bias);
```

Modify `MoodDecay.decay()` to accept an effective baseline (baseline + goalBias).

### C20: Thread safety on pendingSignals (MoodOrchestrator)

**Problem:** `record()` mutates `ArrayDeque<MoodSignal>` without acquiring `tickLock`. `doTick()` drains the same deque under the lock. Race condition.

**Fix:** Replace `ArrayDeque<MoodSignal>` with `ConcurrentLinkedDeque<MoodSignal>`. No lock needed for `addLast()`. Replace the existing `while (!isEmpty()) { removeFirst() }` drain with the idiomatic concurrent pattern:

```java
MoodSignal signal;
while ((signal = state.pendingSignals.pollFirst()) != null) {
    drained.add(signal);
}
```

The current code uses `removeFirst()` inside a `while (!isEmpty())` guard — safe under a lock with ArrayDeque, but with ConcurrentLinkedDeque the `isEmpty()` check and `removeFirst()` are not atomic. `pollFirst()` is a single atomic operation returning `null` when empty.

## Batch 2: Appraisal & Mapping (C11, C14, C16, C21)

These produce the emotion signals consumed by mood and drives. Fix before drives so the signals are correct.

### C11: Appraisal weights and habituation not consumed (LlmAppraisalStrategy)

**Problem:** `CognitiveDerivationEngine` derives appraisal weights per agent, but `buildUserMessage()` never reads `context.appraisalWeights()`. Habituation uses `String.hashCode()` — only exact-text repeats are detected.

**Fix:**
1. In `buildUserMessage()`, append appraisal weight instructions: for each SEC dimension where the weight differs from 1.0 by >0.15, add a bias instruction like "Pay special attention to [dimension] — this agent is particularly sensitive to it."
2. Replace `Integer.toHexString(narrative.hashCode())` with a normalized token hash: lowercase, sort tokens, remove stopwords, then hash. This catches minor rephrasing.

### C14: EmotionMapper missing 6 emotions + INTERRUPTION intensity (EmotionMapper)

**Problem:** `mapEmotions()` only produces 9 of 15 emotion types. Missing: PRIDE, RELIEF, GRATITUDE, ADMIRATION, SATISFACTION, DISAPPOINTMENT. INTERRUPTION fires at intensity 1.0 on low novelty (should be low-moderate).

**Fix:**
1. Add mapping rules for 6 missing emotions using SEC dimension patterns aligned with OCC theory:
   - **PRIDE:** high internal-standards + high conduciveness (self-caused good outcome — correct per OCC)
   - **RELIEF:** high conduciveness + urgency delta > 0.3 (prior threat resolved — OCC's disconfirmation of a feared prospect; urgency delta captures the transition from danger to safety)
   - **GRATITUDE:** high conduciveness + low controllability (good outcome, not self-caused — OCC compound of JOY + other-agency; low controllability approximates external attribution since the agent didn't control the outcome)
   - **ADMIRATION:** high external-standards (> 0.7) + relevance > 0.3 (someone's action notably exceeds social norms AND the agent notices it — OCC's approval of praiseworthy action; the relevance gate prevents firing on routine norm-conformance that the agent doesn't attend to; novelty is NOT a component of OCC admiration and is removed from this mapping)
   - **SATISFACTION:** high conduciveness + low novelty (expected good outcome confirmed — OCC's confirmation of a prospect; low novelty captures the expectedness that distinguishes satisfaction from surprise-joy)
   - **DISAPPOINTMENT:** low conduciveness + high relevance (cared about outcome, got negative — OCC's disconfirmation of a prospect of a desirable event)
2. Cap INTERRUPTION: `clampIntensity((1.0 - novelty) * 0.3)` — maximum 0.3 instead of 1.0.

**SEC limitations documented:** The SEC dimensions available do not directly encode other-agency attribution or temporal prospect tracking. The GRATITUDE mapping uses low controllability as a proxy for external agency — this will produce false positives when negative outcomes are also uncontrollable. The ADMIRATION mapping captures norm-conformance but cannot distinguish between situational norm-alignment and attributing a praiseworthy act to a specific agent. These limitations are inherent to SEC-only mapping without ToM/social-context inputs.

**Unmapped EmotionType values (8 of 23):**
- **FEARS_CONFIRMED:** mirror of RELIEF — requires temporal prospect tracking (prior fear → confirmed negative). SEC doesn't track prior emotional state.
- **HAPPY_FOR, PITY:** fortune-of-others — require ToM/social-context inputs (knowing another agent's situation and valence).
- **RESENTMENT, GLOATING:** fortune-of-others for disliked agents — require both ToM and relationship valence.
- **GRATIFICATION:** OCC compound of PRIDE + JOY — could be derived as a post-hoc compound when both trigger simultaneously. Deferred to a follow-up issue.
- **LOVE, HATE:** object-based emotions requiring sustained relationship context, not single-event appraisal.

These 8 require either social-context SEC extensions or compound/temporal derivation. Tracked as a separate follow-up for social emotion mapping once the ToM subsystem matures.

### C16: Concern salience normalised by max(a,b) (ConcernBasedSalienceStrategy)

**Problem:** `keywordOverlap()` normalises by `Math.max(a.size(), b.size())`. A 3-word concern against a 30-word observation: `max(3,30)=30`, score = 3/30 = 0.1 even with all concern words matching.

**Fix:** Normalise by `Math.min(a.size(), b.size())`. All concern words appearing = 1.0 regardless of observation length.

### C21: Gut-feeling Layer 2 scans tenant-wide (GutFeelingParticipant)

**Problem:** Layer 2 affect fallback calls `memoryStore.scan()` with no agent filter. Multi-agent tenants share affect history.

**Fix:** Add `@Nullable PrincipalId callerPrincipalId` field to `MemoryScanRequest` (cross-module API change to memory-api). This aligns with the existing `CbrQuery.callerPrincipalId` pattern for principal-scoped filtering.

In `GutFeelingParticipant`, change the scan to:
```java
var affectMemories = memoryStore.scan(
    new MemoryScanRequest(tenantId, "affect", null, null, 50, null,
                          PrincipalId.agent(agentId)));
```

Affect memories already store `PrincipalId` via `AffectTrajectoryDecorator` (which extracts agentId from the MindMap node's properties and calls `input.withPrincipalId(PrincipalId.agent(agentId))`). The CaseMemoryStore scan implementation uses `MemoryVisibility` for principal-scoped filtering — the plumbing exists, only the MemoryScanRequest field is missing.

The `MemoryScanRequest` compact constructor gains a backward-compatible overload: the existing 6-arg constructor defaults `callerPrincipalId` to `null` (unfiltered).

## Batch 3: Drive Computation (C6, C7, C9, C10)

Drives consume mood and appraisal output. The eidos change (C7) is a prerequisite.

### C7: Pole sign semantics (eidos + DriveComposer) — CROSS-REPO

**Problem:** `DriveComposer.personalityModulation()` takes `getFirst().weight()` from the disposition profile without checking which pole the term represents. "cautious" and "bold" both produce positive modulation.

**Fix (D3):** Add to `DispositionAxis` in eidos:
```java
public double signedPosition(String term) {
    if (term.equalsIgnoreCase(highPoleLabel())) return +1.0;
    if (term.equalsIgnoreCase(lowPoleLabel())) return -1.0;
    return 0.0;
}
```

In `DriveComposer`, change line 123:
```java
// Before: return weight * config.personalityModulationStrength();
double sign = matchedAxis.signedPosition(values.getFirst().term());
return sign * weight * config.personalityModulationStrength();
```

**Build order:** eidos must be built and installed before neocortex.

### C6: Coping drive modulations overwritten (DriveOrchestrator)

**Problem:** `recordAppraisalModulation()` uses `put()` for both `pendingAppraisalModulations` and `pendingAppraisalDescriptions` — second call overwrites first in both maps.

**Fix:** Use `merge()` with accumulator for both maps. **Description merge must execute before modulation merge** so the comparison uses the previous caller's individual contribution, not the already-merged total.

```java
public void recordAppraisalModulation(String agentId, String tenantId,
                                       Map<DriveAxis, Double> modulation,
                                       @Nullable Map<DriveAxis, String> descriptions) {
    var key = agentId + ":" + tenantId;

    // 1. Merge descriptions FIRST — using pre-merge modulation state for comparison
    if (descriptions != null) {
        pendingAppraisalDescriptions.merge(key, descriptions,
            (old, neu) -> {
                var merged = new EnumMap<>(old);
                var priorMod = pendingAppraisalModulations.get(key);
                neu.forEach((axis, desc) -> {
                    var priorAxisMod = priorMod != null ? priorMod.getOrDefault(axis, 0.0) : 0.0;
                    var newAxisMod = modulation.getOrDefault(axis, 0.0);
                    if (Math.abs(newAxisMod) >= Math.abs(priorAxisMod)) merged.put(axis, desc);
                });
                return merged;
            });
    }

    // 2. Merge modulations SECOND
    pendingAppraisalModulations.merge(key, modulation,
        (old, neu) -> {
            var m = new EnumMap<>(old);
            neu.forEach((k, v) -> m.merge(k, v, Double::sum));
            return m;
        });
}
```

This ensures the description comparison is between the new caller's individual contribution and the previous caller's individual contribution (not the merged total). Example: Call 1 = CURIOSITY +0.1 "mild gap", Call 2 = CURIOSITY +0.3 "strong emotional response" → description merge compares |0.3| ≥ |0.1| → true → "strong emotional response" wins.

### C9: DriveSource state not agent-keyed (CuriosityDrive et al.)

**Problem:** `lastGaps`, `lastChannel` are single volatile fields shared across agents. Multi-agent = cross-contamination.

**Fix:** Replace with `ConcurrentHashMap<String, T>` keyed by agentId. Apply to CuriosityDrive, CompetenceDrive, AffiliationDrive, AutonomyDrive — all four have the same pattern.

### C10: DriveAdaptationPhase cursor + zero recovery

**Problem 1:** UUID lexical comparison as a cursor — arbitrary ordering unrelated to creation time.
**Problem 2:** `currentIntensity * (1 + delta)` — intensity at 0.0 can never recover.

**Fix 1:** Use timestamp-based cursor stored as a property on a sentinel node.
**Fix 2:** Additive update: `Math.min(1.0, currentIntensity + delta * config.recoveryRate())`. Clamp to [0.0, 1.0].

## Batch 4: Regulation (C5, C12, C13, C17)

Top of the stack — consumes mood, drives, appraisal. Fix last.

### C5: CognitiveResourcePool null (EmotionRegulationTickParticipant)

**Problem:** `this.cognitiveResourcePool = null;` hardcoded in constructor. Depletion is always 0, fatigue gate never fires.

**Fix:** Accept `@Nullable CognitiveResourcePool` as a constructor parameter (CDI `Instance<CognitiveResourcePool>`). Wire via `CognitionDefaultBeans` (which already produces `DefaultCognitiveResourcePool`).

**Behavioral impact:** This activates a previously inert subsystem. With `cognitiveResourcePool = null`, the fatigue gate (`currentFatigue > SAFETY_FATIGUE_THRESHOLD`) never fires and alpha is always `DEFAULT_ALPHA * 1.0 = 0.5`. After the fix, depletion accumulates via `recordEffort()`, alpha decreases over time, and the safety gate starts triggering `ATTENTIONAL_DEPLOYMENT` under sustained emotional load.

**Threshold calibration:** `DefaultCognitiveResourcePool` uses logarithmic depletion: `Math.min(1.0, Math.log(1 + accumulator) / Math.log(1 + maxEffort))`. With `REGULATION_CONTRIBUTION_RATE = 0.15` and typical `regulationEffort` of ~0.3-0.5, each regulation event adds ~0.045-0.075 to the accumulator. The logarithmic curve means early events contribute more than later ones, and reaching `SAFETY_FATIGUE_THRESHOLD = 0.7` requires sustained regulation across many ticks — not a single intense interaction. Recovery between ticks via `recordRecovery()` further moderates accumulation. The thresholds are appropriate for a gradual depletion model where the safety gate represents genuine cognitive exhaustion, not momentary spikes.

### C12: Regulated intensity doesn't reach mood (EmotionRegulationTickParticipant)

**Problem:** Regulation computes `regulatedIntensity` but only uses it for CAPS weight updates. `GoalEmotionMoodBridge` reads raw `CognitiveEmotion::intensity`, bypassing regulation.

**Fix:** After regulation produces a result, record a `MoodSignal.RegulatedShift` that applies the difference `(regulatedIntensity - originalIntensity)` as a correction to mood. This feeds back through the rate-limited mood pipeline (C2 fix).

Add `RegulatedShift` to the `MoodSignal` sealed interface in cognition-api:

```java
record RegulatedShift(
    double pleasureDelta,
    double arousalDelta,
    double dominanceDelta,
    String regulationStrategy,
    @Nullable EmotionType targetEmotion
) implements MoodSignal {
    public RegulatedShift {
        Objects.requireNonNull(regulationStrategy, "regulationStrategy required");
        validateDelta("pleasureDelta", pleasureDelta);
        validateDelta("arousalDelta", arousalDelta);
        validateDelta("dominanceDelta", dominanceDelta);
    }
}
```

**Fields:**
- `pleasureDelta/arousalDelta/dominanceDelta`: the correction `(regulatedIntensity - originalIntensity)` projected onto PAD via `AlmaPadTable`. Validated to [-2, 2] like other MoodSignal subtypes.
- `regulationStrategy`: which strategy produced this correction (e.g. "COGNITIVE_REAPPRAISAL", "ATTENTIONAL_DEPLOYMENT").
- `targetEmotion`: which emotion was regulated (nullable — regulation may target the overall emotional state).

**Cause tracking:** `RegulatedShift` does NOT participate in `MoodOrchestrator.doTick()` cause tracking. The existing pattern match handles `DirectShift` and `InteractionAppraisal` for cause — regulation adjustments are second-order effects, not primary causes. No new pattern-match branch needed in `doTick()`.

**MoodOrchestrator dependency:** `EmotionRegulationTickParticipant` has no current reference to `MoodOrchestrator`. Add `@Nullable MoodOrchestrator moodOrchestrator` as a constructor parameter on the final constructor (extending the existing telescoping chain). Wire via `CognitionDefaultBeans` CDI producer. The dependency creates a feedback loop (mood → appraisal → regulation → mood) which is architecturally correct — the cycle is broken by the tick boundary.

**Call sites — both paths:** Recording must happen in `handleRegulationResult()` (not inline in `tick()`), because `tick()` has two mutually exclusive code paths:
1. **Coping path** (line 249-252): when `config.copingEnabled() && copingMicroLoop != null`, routes to `tickCopingPath()` → `handleRegulationResult()`.
2. **Normal path**: inline regulation result handling (structurally identical to `handleRegulationResult()`).

Add RegulatedShift recording inside `handleRegulationResult()` (which serves both paths), after the existing result-storage block:

```java
if (moodOrchestrator != null && dominantType != null) {
    double intensityDelta = result.regulatedIntensity() - result.peakOriginalIntensity();
    var pad = AlmaPadTable.project(dominantType, intensityDelta);
    moodOrchestrator.record(new MoodSignal.RegulatedShift(
        pad.pleasure(), pad.arousal(), pad.dominance(),
        result.strategy().name(), dominantType), context.agentId(), context.tenantId());
}
```

The normal path's inline result handling should delegate to `handleRegulationResult()` as well, eliminating the code duplication between the two paths.

### C13: Regulation triggers on positive emotions (EmotionRegulationTickParticipant)

**Problem:** Regulation threshold uses `Math.abs(intensity - 0.3)` — valence-blind. High JOY (0.8) triggers regulation.

**Fix (D4):** Restructure `tick()` to enforce the two-tier approach correctly. The current code computes maxDiscrepancy → regulationEffort → early return before the safety gate is reached. Filtering maxDiscrepancy to negative-valence while leaving the safety gate after the early return would make the safety gate unreachable when all emotions are positive.

**Required flow restructure** in `tick()`:

```java
// Step 1: Compute peakEmotion from ALL emotions (unfiltered — safety gate is valence-blind)
var peakEmotion = appraisal.get().emotions().stream()
    .max(Comparator.comparingDouble(CognitiveEmotion::intensity))
    .orElse(null);

// Step 2: Safety gate FIRST — fires unconditionally on extreme intensity or fatigue
double depletion = cognitiveResourcePool != null
    ? cognitiveResourcePool.currentDepletion(context.agentId(), context.tenantId()) : 0.0;
double currentFatigue = depletion;

if (peakEmotion != null && (currentFatigue > SAFETY_FATIGUE_THRESHOLD
                            || peakEmotion.intensity() > SAFETY_INTENSITY_THRESHOLD)) {
    // Safety gate fires — skip maxDiscrepancy, skip effort, go directly to ATTENTIONAL_DEPLOYMENT
    pinnedStrategy = EmotionRegulationStrategy.ATTENTIONAL_DEPLOYMENT;
    strategySource = "SAFETY_GATE";
    // ... proceed to regulation generation with pinnedStrategy
}

// Step 3: Normal regulation — only negative-valence emotions trigger effort
double maxDiscrepancy = appraisal.get().emotions().stream()
    .filter(e -> e.pad().pleasure() < 0)
    .mapToDouble(e -> Math.abs(e.intensity() - BASELINE_INTENSITY))
    .max().orElse(0.0);

double alpha = DEFAULT_ALPHA * (1.0 - depletion);
double regulationEffort = alpha * maxDiscrepancy / D_MAX;

if (pinnedStrategy == null && regulationEffort < EFFORT_NOISE_FLOOR) {
    // No safety gate fired AND no negative-valence emotions above threshold → no regulation needed
    recordRecovery(...);
    return;
}
// ... continue to Layer 2 (CAPS), Layer 3 (predictor), Layer 4 (LLM)
// When pinnedStrategy != null (safety gate fired), this early return is bypassed
// and regulation generation proceeds with the pinned ATTENTIONAL_DEPLOYMENT strategy.
```

**Theoretical departure from Bosse et al. 2010:** The Bosse model regulates ALL deviations from baseline intensity regardless of valence (equation `α_n × d / d_max` applies uniformly). This spec intentionally departs from that model. For a cognitive agent, downregulating moderate JOY or HOPE is counterproductive — these positive states facilitate engagement and goal pursuit. The departure uses a two-tier approach:

1. **Safety gate (moved before effort computation):** Fires for ANY emotion exceeding `SAFETY_INTENSITY_THRESHOLD = 0.75` regardless of valence, OR when `currentFatigue > SAFETY_FATIGUE_THRESHOLD`. This catches extreme positive states (obsessive INTEREST, manic HOPE). By running before the effort early return, it is always reachable.
2. **Normal regulation path:** Only negative-valence emotions (pleasure < 0) contribute to `maxDiscrepancy` and trigger the regulation effort computation. Moderate JOY, HOPE, INTEREST are not candidates for normal regulation.

Together these tiers provide: normal positive emotions unregulated, moderate negative emotions regulated proportionally, extreme emotions of either valence caught by the safety gate.

### C17: CognitiveLoadEstimator LOW unreachable

**Problem:** `drives().size()` returns 4 (always — the axis count). With `MODERATE_THRESHOLD=4`, LOW is unreachable.

**Fix:** Count drives with intensity above a meaningful threshold: `drives.stream().filter(d -> d.intensity() > 0.3).count()`.

## Verification Criteria

1. **Mood stability (C2, C3):** With no input, mood should decay to baseline within ~60 minutes (3×τ at 20 minutes). A single strong emotion should shift mood by ~0.3-0.5 from neutral, not pin at ±1.0.
2. **Mood recovery (C2):** An agent at mood -0.8 receiving a strong positive signal (+0.8) should recover toward baseline with no dampening on the recovery direction. The same signal pushing further negative (at -0.8, receiving -0.8) should be dampened.
3. **Goal bias interaction (C4, C2):** With goalBias of +0.3 pleasure, mood at +0.3 is at the effective baseline. Signals should not be dampened at this point. Mood should decay toward +0.3, not 0.0.
4. **Personality differentiation (C7):** Bold and cautious agents under the same emotional input should produce different drive intensities with opposite signs on the risk-sensitive axes.
5. **Emotion coverage (C14):** EmotionMapper should produce all 15 mapped emotion types given appropriate SEC inputs. Unmapped types (8) should be documented as excluded.
6. **Regulation selectivity (C13):** The safety gate must fire for ANY emotion above 0.75 intensity regardless of valence — even when all emotions are positive. Normal regulation effort should compute from negative-valence emotions only. An agent with only positive emotions at intensity 0.9 must hit the safety gate, not early-return.
7. **Modulation accumulation (C6):** Two consecutive `recordAppraisalModulation` calls within one tick should produce a combined modulation per axis (additive), with the description from the larger contributor preserved.
8. **Agent-scoped drives (C9):** Two agents ticked concurrently on the same DriveSource instances should produce independent drive intensities and independent diagnostic state (lastChannel, lastTrend, etc.).
9. **Thread safety (C20):** Concurrent `record()` and `tick()` on the same agent should not corrupt state. The `pollFirst()` drain should not throw `NoSuchElementException`.
10. **Agent-scoped gut feeling (C21):** Layer 2 affect fallback should return affect memories scoped to the requesting agent, not the entire tenant.
11. **Resource pool activation (C5):** Regulation should fire the fatigue gate when depletion > 0.7, which requires the resource pool to actually track effort. Alpha should decrease with accumulated depletion.
12. **Regulation reaches mood (C12):** After regulation produces a result, a `RegulatedShift` mood signal should be recorded with the intensity delta projected onto PAD.
13. **Drive cursor ordering (C10):** Drive adaptation should use timestamp-based cursor, not UUID lexical ordering. Intensity at 0.0 should recover via additive update.
14. **Appraisal weights consumed (C11):** SEC dimensions where appraisal weight differs from 1.0 by >0.15 should produce bias instructions in the LLM prompt.
15. **Salience normalisation (C16):** A 3-word concern fully matching within a 30-word observation should score 1.0 (min-based normalisation), not 0.1.
16. **Cognitive load estimator (C17):** LOW level should be reachable — count drives with intensity > 0.3, not all 4 axes.

## References

- `cognition/src/main/java/.../mood/MoodOrchestrator.java` — C2, C3, C20
- `cognition/src/main/java/.../mood/GoalEmotionMoodBridge.java` — C4
- `cognition/src/main/java/.../appraisal/LlmAppraisalStrategy.java` — C11
- `cognition/src/main/java/.../appraisal/EmotionMapper.java` — C14
- `cognition/src/main/java/.../salience/ConcernBasedSalienceStrategy.java` — C16
- `cognition/src/main/java/.../gut/GutFeelingParticipant.java` — C21
- `cognition/src/main/java/.../drive/DriveOrchestrator.java` — C6
- `cognition/src/main/java/.../drive/DriveComposer.java` — C7
- `cognition/src/main/java/.../drive/CuriosityDrive.java` — C9
- `cognition/src/main/java/.../drive/DriveAdaptationPhase.java` — C10
- `cognition/src/main/java/.../regulation/EmotionRegulationTickParticipant.java` — C5, C12, C13
- `cognition/src/main/java/.../regulation/CognitiveLoadEstimator.java` — C17
- `eidos/api/src/.../DispositionAxis.java` — C7 cross-repo
- `memory-api/src/.../MoodDecay.java` — C3
- decisions.md D1, D2, D3, D4
