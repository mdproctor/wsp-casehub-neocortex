# HANDOFF — casehub-neocortex (slot 230)

## Active Work: SE7 Orchestrators & Higher Cognition (#1227)

**Branch:** `issue-1226-affect-emotion` (reused from SE6 — pipeline stacked work on existing branch)
**Queue:** `casehubio/neocortex#1227` active, 10 tasks injected across 6 batches

### What was completed this session

**Design and planning — no implementation yet:**

1. **Brainstorming** — 6 design decisions captured:
   - D1: Fix E5 relational-schema trust with cursor (not remove dead code)
   - D2: E8 retention formula first-principles redesign (base = recency + frequency, confidence × trust as multipliers)
   - D3: E10d goal surfacing writes nothing (not an experience event — first-principles analysis)
   - D4: E9 embedding-based pairwise cosine for hygiene grouping
   - D5: E16 fix all three belief revision bugs (while disabled, cheapest to fix now)
   - D6: 6-batch ordering strategy

2. **Design spec** written and reviewed:
   - `specs/issue-1227-orchestrators-higher-cognition/2026-11-26-orchestrators-higher-cognition-design.md`
   - Light design review ran (16 issues, 5 HIGH) — all corrections applied
   - Key corrections: missing E10e (goal tick results discarded by safeRun), E4 idempotent recomputation, E12 INTENTION-only filter, E1 Strategy root cause distinct

3. **Implementation plan** written:
   - `plans/2026-11-26-se7-orchestrators-higher-cognition.md`
   - 10 tasks in 6 batches, all with TDD steps and exact file paths

### What's next

1. **Execute the plan** — start with `executing-plans` skill, beginning at Batch 1 (Task 1: E4 confidence decay)
2. IntelliJ MCP needs heap recovery before execution can begin — wait for lifecycle manager to close idle projects
3. The branch is `issue-1226-affect-emotion` with 1 commit ahead of main (closure stamp) and 1 behind (docs promote) — needs rebase or new branch before implementation

### Notes for next session

- `MemoryScanRequest.callerPrincipalId` wired in `InMemoryMemoryStore` only — SQLite/JPA stores need updating when touched next
- MoodConfig default decay constant changed from 4h to 20min — review cognitive profile config overrides
- eidos repo has `signedPosition()` commit on `issue-1226-affect-emotion` — needs separate landing if not already done
- AttributedState record (cognition-api) needs `originalConfidence` field added — Task 1 covers this
- RetentionScore/RetentionConfig (cognition-api) need formula redesign — Task 3 covers this
- E2 was deferred from SE1 (#1221) — now in SE7 Batch 6

## Epic Status (#1220)

| Sub-epic | Issue | Status |
|----------|-------|--------|
| SE1: Pipeline Spine | #1221 | Done (landed) |
| SE2: CAPS Rework | #1222 | Done (landed) |
| SE3: Storage & Data Integrity | #1223 | Done (landed) |
| SE4: Consolidation Phases | #1224 | Done (landed) |
| SE5: cognitive-index | #1225 | Done (landed) |
| SE6: Affect & Emotion | #1226 | **Done (landed)** |
| SE7: Orchestrators | #1227 | **Active** — design complete, implementation not started |

**6 of 7 sub-epics done. SE7 is the final sub-epic.**
