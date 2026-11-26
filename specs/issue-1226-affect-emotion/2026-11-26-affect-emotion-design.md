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

**Fix:** Replace raw sum with asymptotic approach. In `MoodOrchestrator.doTick()`, change the accumulation loop:

```java
// Before: p += signal.pleasureDelta();
// After:
double remaining = config.maxDisplacement() - Math.abs(p);
double scale = Math.max(0.0, remaining / config.maxDisplacement());
p += signal.pleasureDelta() * scale;
```

Apply same pattern to arousal and dominance. Also shorten default decay constant from 4 hours to 20 minutes (`MoodConfig` default).

### C3: Decay before signal (MoodOrchestrator)

**Problem:** Decay uses elapsed time since last tick. After a 2-hour idle gap, a fresh emotion signal is immediately decayed by 2 hours. `MoodDecay.decayAxis` erases ~40% of the shift.

**Fix:** Swap the order in `doTick()`: decay the pre-signal mood first using elapsed time, then apply new signals to the decayed state. Lines 102-112 (decay) must execute before lines 83-96 (signal accumulation).

### C4: Goal emotions as set-point bias (GoalEmotionMoodBridge)

**Problem:** Every tick, all active goal emotions (HOPE on each goal) are summed into a `DirectShift` delta and added to mood. 5 goals with HOPE → +0.3 pleasure delta per tick, pinning mood positive.

**Fix (D2):** Replace `record(DirectShift)` with a `setGoalBias(MoodState)` method on `MoodOrchestrator`. Goal emotions compute a standing PAD bias. `MoodDecay` decays toward `baseline + goalBias` instead of bare `baseline`. `GoalEmotionMoodBridge` calls `setGoalBias()` only when goal set changes, not every tick.

Add to `MoodOrchestrator`:
```java
void setGoalBias(String agentId, String tenantId, MoodState bias);
```

Modify `MoodDecay.decay()` to accept an effective baseline (baseline + goalBias).

### C20: Thread safety on pendingSignals (MoodOrchestrator)

**Problem:** `record()` mutates `ArrayDeque<MoodSignal>` without acquiring `tickLock`. `doTick()` drains the same deque under the lock. Race condition.

**Fix:** Replace `ArrayDeque<MoodSignal>` with `ConcurrentLinkedDeque<MoodSignal>`. No lock needed for `addLast()`. Drain in `doTick()` via `pollFirst()` loop (already does this).

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
1. Add mapping rules for 6 missing emotions using SEC dimension patterns from OCC theory:
   - PRIDE: high internal-standards + high conduciveness
   - RELIEF: high conduciveness + prior high urgency (delta)
   - GRATITUDE: high conduciveness + external attribution (high external-standards)
   - ADMIRATION: high external-standards + high novelty
   - SATISFACTION: high conduciveness + high controllability
   - DISAPPOINTMENT: low conduciveness + high relevance
2. Cap INTERRUPTION: `clampIntensity((1.0 - novelty) * 0.3)` — maximum 0.3 instead of 1.0.

### C16: Concern salience normalised by max(a,b) (ConcernBasedSalienceStrategy)

**Problem:** `keywordOverlap()` normalises by `Math.max(a.size(), b.size())`. A 3-word concern against a 30-word observation: `max(3,30)=30`, score = 3/30 = 0.1 even with all concern words matching.

**Fix:** Normalise by `Math.min(a.size(), b.size())`. All concern words appearing = 1.0 regardless of observation length.

### C21: Gut-feeling Layer 2 scans tenant-wide (GutFeelingParticipant)

**Problem:** Layer 2 affect fallback calls `memoryStore.scan()` with no agent filter. Multi-agent tenants share affect history.

**Fix:** Add agent filter to the `MemoryScanRequest`. Use the principal/subject mechanism to scope to the current agent.

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

**Problem:** `recordAppraisalModulation()` uses `put()` — second call overwrites first.

**Fix:** Use `merge()` with accumulator:
```java
pendingAppraisalModulations.merge(key, modulation,
    (old, neu) -> { var m = new EnumMap<>(old); neu.forEach((k,v) -> m.merge(k, v, Double::sum)); return m; });
```

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

### C12: Regulated intensity doesn't reach mood (EmotionRegulationTickParticipant)

**Problem:** Regulation computes `regulatedIntensity` but only uses it for CAPS weight updates. `GoalEmotionMoodBridge` reads raw `CognitiveEmotion::intensity`, bypassing regulation.

**Fix:** After regulation produces a result, record a `MoodSignal.RegulatedShift` that applies the difference `(regulatedIntensity - originalIntensity)` as a correction to mood. This feeds back through the rate-limited mood pipeline (C2 fix).

### C13: Regulation triggers on positive emotions (EmotionRegulationTickParticipant)

**Problem:** Regulation threshold uses `Math.abs(intensity - 0.3)` — valence-blind. High JOY (0.8) triggers regulation.

**Fix:** Filter to negative-valence emotions before computing maxDiscrepancy. Check `emotion.pad().pleasure() < 0` before including in the regulation candidate set.

### C17: CognitiveLoadEstimator LOW unreachable

**Problem:** `drives().size()` returns 4 (always — the axis count). With `MODERATE_THRESHOLD=4`, LOW is unreachable.

**Fix:** Count drives with intensity above a meaningful threshold: `drives.stream().filter(d -> d.intensity() > 0.3).count()`.

## Verification Criteria

1. **Mood stability:** With no input, mood should decay to baseline within ~20 minutes (not 4 hours). A single strong emotion should shift mood by ~0.3-0.5 from neutral, not pin at ±1.0.
2. **Personality differentiation:** Bold and cautious agents under the same emotional input should produce different drive intensities with opposite signs on the risk-sensitive axes.
3. **Emotion coverage:** EmotionMapper should produce all 15 emotion types given appropriate SEC inputs.
4. **Regulation selectivity:** Regulation should fire on FEAR/ANGER/DISTRESS but not on JOY/PRIDE/HOPE.

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
- `cognition/src/main/java/.../drive/DriveAdaptationPhase.java` — C10 (actually in mindmap-intelligence)
- `cognition/src/main/java/.../regulation/EmotionRegulationTickParticipant.java` — C5, C12, C13
- `cognition/src/main/java/.../regulation/CognitiveLoadEstimator.java` — C17
- `eidos/api/src/.../DispositionAxis.java` — C7 cross-repo
- `memory-api/src/.../MoodDecay.java` — C3
- decisions.md D1, D2, D3
