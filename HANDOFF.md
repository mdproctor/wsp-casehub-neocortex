# HANDOFF — casehub-neocortex

## Session completed: #1240 and #1241

Two XS/Low issues from the #1237 additional-capabilities stream, both done and ready to land.

### #1240 — cognitionActive marker detection
- Branch: `issue-1240-cognition-active-marker` (1 commit, stacked base)
- `CognitiveAvatarProducer` now injects `Instance<CognitiveLifecycle>` to detect whether the full cognition module is on the classpath
- When resolvable, 4 lightweight capabilities (Needs, Appraisal, InnerThoughts, Consolidation) yield via `isActive() = false`
- Design decision: D5 in `docs/specs/issue-1237-additional-capabilities/decisions.md`

### #1241 — consolidation trait constants
- Branch: `issue-1241-consolidation-trait-const` (1 commit, stacked on #1240)
- `ConsolidationTraits` utility class in `mindmap-api` with 3 constants
- All string literals replaced across 7 production + 5 test files in `cognitive-runtime`, `mindmap-intelligence`, and `cognition`

### Queue state
Both items marked done, waiting for `work end` to land. No active item in queue.

## Active Work: Cognitive Pipeline Coherence (#1220)

A comprehensive review (107 findings across 9 sections) identified systemic issues in the cognitive pipeline. These are organized into 7 sub-epics. SE1 is done. 6 remain — all can run in parallel.

### How to pick up any sub-epic

1. Read the **issue** on GitHub (`casehubio/neocortex#NNNN`) — it has the goal, modules, file list, and child issues with finding references
2. Read the **epic plan** in the project: `docs/specs/cognitive-review-analysis/2026-11-24-epic-plan.md` — it has the dependency graph, module ownership, and child issue details for all 7 sub-epics
3. Read the **triage** for context on each finding: `docs/specs/cognitive-review-analysis/2026-11-24-cognitive-review-triage.md` — categorised findings with fix status
4. Run `work start #NNNN` to create a branch and plan the work. The epic plan has enough detail for each child issue to write an implementation plan directly — brainstorm only if the approach is unclear

### Status

| Sub-epic | Issue | Status | Module | Findings remaining |
|----------|-------|--------|--------|--------------------|
| SE1: Pipeline Spine | #1221 | **Done** (closed) | cognition core | 0 (+2 deferred: #1231, #1232) |
| SE2: CAPS Rework | #1222 | **Open** | caps-engine, caps-testing, caps-llm-classifier, caps-situation-cbr | 8 |
| SE3: Storage & Data Integrity | #1223 | **Open** | memory-sqlite, mindmap-sqlite, mindmap | 4 |
| SE4: Consolidation Phases | #1224 | **Open** | mindmap-intelligence | 9 |
| SE5: cognitive-index | #1225 | **Open** | cognitive-index | 6 |
| SE6: Affect & Emotion | #1226 | **Open** | cognition (mood/drive/appraisal/regulation) | 14 |
| SE7: Orchestrators | #1227 | **Open** | cognition (goal/narrative/personality/hygiene) | 10 |

**Cross-repo:** #1228 (vocabulary alignment with eidos) — coordinate with eidos repo.

## References

- **Parent epic:** casehubio/neocortex#1220
- **Epic plan:** `docs/specs/cognitive-review-analysis/2026-11-24-epic-plan.md`
- **Triage:** `docs/specs/cognitive-review-analysis/2026-11-24-cognitive-review-triage.md`
