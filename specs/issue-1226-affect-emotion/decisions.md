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
