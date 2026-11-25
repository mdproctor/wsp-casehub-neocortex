# HANDOFF — casehub-neocortex

## Active Work: Cognitive Pipeline Coherence (#1220)

A comprehensive review (107 findings across 9 sections) identified systemic issues in the cognitive pipeline. These are organized into 7 sub-epics. SE1 and SE4 are done. 5 remain — all can run in parallel.

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
| SE4: Consolidation Phases | #1224 | **Done** (this session) | mindmap-intelligence | 0 |
| SE5: cognitive-index | #1225 | **Open** | cognitive-index | 6 |
| SE6: Affect & Emotion | #1226 | **Open** | cognition (mood/drive/appraisal/regulation) | 14 |
| SE7: Orchestrators | #1227 | **Open** | cognition (goal/narrative/personality/hygiene) | 10 |

**Cross-repo:** #1228 (vocabulary alignment with eidos) — coordinate with eidos repo.

### Parallelism rules

All 5 open sub-epics touch different Maven modules or different files within the same module. They can run in separate slots with zero merge-conflict risk. The only constraint:
- SE6 and SE7 depend on SE1 (pipeline spine) which is done
- SE2, SE3, SE5 have no dependencies — start any time

### SE4 session summary (2026-11-25)

**Branch:** `issue-1224-consolidation-phase-fixes` (11 commits, squash-reviewed)
**What was done:** All 8 findings fixed (F3, F5, F6, F7, F11, F16, F17, F19)

Three cross-cutting principles emerged:
1. **Entity resolution reuse** — wired SurfaceFormTrie (already a dependency) into SubThoughtExtractor, raised MindMapExtractor fuzzy threshold from 0.85 to 0.95
2. **Tenant-scoped state** — composite key in CognitiveAttentionAccumulator, per-tenant swapAndReset in SignificanceAccumulator, dynamic tenant discovery via ExperienceRecorded observer
3. **Threshold safety** — min-neighbor guard for merge (JW < 0.95 needs ≥ 2 shared neighbors), word-token Jaccard for goal merge, INFERRED default confidence for ConversationBridge

Additional fixes: watermark cursor with TTL escape hatch (10 ticks), type-based graduated node naming, CommunitySummaryPhase disabled by default via runtime config.

**Spec gaps documented but not implemented:**
- MindMapExtractor trie-first + subgraph-scoped fuzzy tiers (threshold raise covers the acute problem)
- SubThoughtExtractor SUBJECT fallback (needs CaseMemoryStore retrieve-by-id API)

**Tests:** 758 mindmap-intelligence + 1383 cognition = 2141 tests green.
**Blog:** "Three Principles, Eight Bugs"

### What the next session should do

Pick up any remaining open sub-epic. SE2 (CAPS), SE3 (Storage), or SE5 (cognitive-index) are all independent and can start immediately. SE6 and SE7 are unblocked now that SE1 is done.
