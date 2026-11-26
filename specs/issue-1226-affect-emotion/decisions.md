# Decisions — SE6: Affect & Emotion (#1226)

## D1: Mood rate-limiting strategy (C2)

**Choice:** Asymptotic approach — `delta * (1 - |mood| / maxDisplacement)`
**Alternatives:**
- Weighted average — needs blending factor config, more complex
- Per-tick cap — crude, doesn't model diminishing returns
**Rationale:** Self-limiting in one line. As mood approaches ±1.0, additional deltas have diminishing effect. No new config parameters. Predictable behavior: a single strong emotion can shift mood significantly from neutral, but can't pin it at ±1.0 — that requires sustained emotional pressure.
**Trade-offs:** A single extreme event can still shift mood by ~0.5 from neutral. If finer control is needed later, the asymptotic formula can be parameterized without changing the approach.
**Sources:** `cognition/src/main/java/.../mood/MoodOrchestrator.java:83-96`, MoodConfig:32
**Exploration:** quick
**Status:** captured

## D2: Goal emotions as set-point bias (C4)

**Choice:** Set-point bias — goal emotions contribute a standing bias that mood decays toward, not a delta added every tick
**Alternatives:**
- Delta on change only — simpler but doesn't model standing emotional tone of active goals
**Rationale:** Goals create a persistent emotional tone (HOPE lifts mood while goals are active). A set-point bias models this correctly: mood drifts toward the goal-influenced baseline rather than being pushed there every tick. Avoids the runaway accumulation bug where N active goals each add +0.3 pleasure per tick.
**Trade-offs:** Requires a new `setGoalBias()` method on MoodOrchestrator. The bias must be recomputed when goals change, not every tick.
**Sources:** `cognition/src/main/java/.../mood/GoalEmotionMoodBridge.java:27-52`
**Exploration:** quick
**Status:** captured

## D3: Pole sign semantics in eidos (C7)

**Choice:** Add `signedPosition(String term)` to `DispositionAxis` enum in eidos
**Alternatives:**
- Hardcode sign map in DriveComposer — duplicates eidos knowledge, no cross-repo API
**Rationale:** `DispositionAxis` already has `lowPoleLabel()` and `highPoleLabel()`. Adding `signedPosition()` (+1.0 for high, -1.0 for low, 0.0 for mid-range) keeps pole semantics where they belong. One method, no breaking changes. DriveComposer consumes it naturally.
**Trade-offs:** Cross-repo change (eidos + neocortex). Eidos must be built first in the dependency chain.
**Depends on:** None
**Sources:** `eidos/api/src/.../DispositionAxis.java:54-72`, `cognition/src/.../drive/DriveComposer.java:119-123`
**Exploration:** deep-analysis (eidos repo exploration)
**Status:** captured

## D4: Valence-aware regulation filter (C13)

**Choice:** Two-tier regulation: (1) safety gate executes FIRST — fires for any emotion above 0.75 intensity regardless of valence, (2) normal regulation path filters maxDiscrepancy to negative-valence emotions only (pleasure < 0). The safety gate must run before the effort computation's early return to remain reachable when all emotions are positive.
**Alternatives:**
- Bosse model as-is — regulate ALL deviations regardless of valence (the current behavior)
- Functional maladaptiveness — regulate based on whether the emotion is maladaptive rather than its valence (more nuanced but requires a maladaptiveness classifier)
**Rationale:** Bosse et al. 2010 models homeostatic regulation of biological emotion systems, where any deviation from baseline triggers corrective action. For a cognitive agent, moderate positive emotions (JOY, HOPE, INTEREST) are functionally beneficial — they facilitate engagement and goal pursuit. Downregulating them wastes cognitive resources and produces flatter, less responsive agents. The valence filter is a pragmatic departure that preserves the Bosse framework's proportional effort computation while restricting its scope to emotions that actually warrant intervention. Extreme positive states (obsessive INTEREST, manic HOPE above 0.75 intensity) are still caught by the safety gate, which fires independently of the maxDiscrepancy computation.
**Trade-offs:** Some edge cases exist: moderate FEAR can be functional (alerting), moderate ANGER can be motivating. These are still regulated under this approach. A more granular filter could use emotion-specific regulation thresholds, but the complexity isn't justified given the existing strategy selection layers (CAPS, predictor) which handle strategy choice — the valence filter only controls whether regulation is *attempted*.
**Sources:** `EmotionRegulationTickParticipant.java:184-187` (maxDiscrepancy computation), Bosse et al. 2010 equation `α_n × d / d_max`
**Exploration:** quick
**Status:** captured
