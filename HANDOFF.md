# HANDOFF — casehub-neocortex (slot 230)

## Active Work: SE6 Affect & Emotion (#1226)

Branch `issue-1226-affect-emotion` is ready for implementation. Design, review, and planning are complete.

### What's ready

| Artifact | Location |
|----------|----------|
| **Spec** (3 review rounds) | `specs/issue-1226-affect-emotion/2026-11-26-affect-emotion-design.md` |
| **Decisions** (4) | `specs/issue-1226-affect-emotion/decisions.md` |
| **Plan** (16 tasks, 4 batches) | `plans/2026-11-26-affect-emotion.md` |

### How to start implementation

1. Run `work continue` — the pipeline will detect #1226 as active on `issue-1226-affect-emotion`
2. Invoke `executing-plans` with the plan at `plans/2026-11-26-affect-emotion.md`
3. Follow the 4-batch structure — each batch is a safe wrap point

### Plan summary (16 tasks, 4 batches)

**Batch 1: Mood Mechanics** (Tasks 1-4)
- Task 1: C20 — Thread safety on pendingSignals (ConcurrentLinkedDeque)
- Task 2: C3 — Decay before signal (swap order in doTick)
- Task 3: C4 — Goal emotions as set-point bias (new setGoalBias API)
- Task 4: C2 — Rate-limit mood deltas (direction-aware asymptotic + 20min decay)

**Batch 2: Appraisal & Mapping** (Tasks 5-8)
- Task 5: C16 — Concern salience normalisation (min instead of max)
- Task 6: C21 — Gut-feeling agent filter (PrincipalId on MemoryScanRequest)
- Task 7: C11 — Appraisal weights consumed + habituation token hash
- Task 8: C14 — EmotionMapper 6 missing emotions + INTERRUPTION cap

**Batch 3: Drive Computation** (Tasks 9-12)
- Task 9: C7 — Pole sign semantics (eidos signedPosition + DriveComposer) **CROSS-REPO**
- Task 10: C6 — Coping drive modulation merge (put→merge with description ordering)
- Task 11: C9 — DriveSource state agent-keyed (ConcurrentHashMap per agent)
- Task 12: C10 — DriveAdaptationPhase cursor + zero recovery

**Batch 4: Regulation** (Tasks 13-16)
- Task 13: C5 — CognitiveResourcePool wiring (CDI Instance injection)
- Task 14: C17 — CognitiveLoadEstimator LOW reachable
- Task 15: C13 — Valence-aware regulation filter (D4 two-tier)
- Task 16: C12 — RegulatedShift reaches mood (new MoodSignal subtype)

### Key design decisions

- **D1**: Asymptotic mood rate-limiting with direction-aware dampening (recovery undampened)
- **D2**: Goal emotions as set-point bias, not per-tick delta
- **D3**: `DispositionAxis.signedPosition()` in eidos — cross-repo API change
- **D4**: Two-tier regulation — safety gate (valence-blind, >0.75) + normal path (negative-valence only)

### Cross-repo note

Eidos cloned into slot at `/Users/mdproctor/claude/casehub/slots/230/eidos` on branch `issue-1226-affect-emotion`. Task 9 (C7) requires building eidos first:
```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl api -DskipTests
```

## Epic Status (#1220)

| Sub-epic | Issue | Status |
|----------|-------|--------|
| SE1: Pipeline Spine | #1221 | Done |
| SE2: CAPS Rework | #1222 | **Done** (landed) |
| SE3: Storage & Data Integrity | #1223 | Done |
| SE4: Consolidation Phases | #1224 | Done |
| SE5: cognitive-index | #1225 | Done |
| SE6: Affect & Emotion | #1226 | **In progress** — design complete, implementation next |
| SE7: Orchestrators | #1227 | Queued |

**5 of 7 sub-epics done. SE6 in progress. SE7 queued.**
