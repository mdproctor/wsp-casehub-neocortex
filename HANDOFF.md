# HANDOFF — casehub-neocortex (slot 230)

## Mission: Work Through the Cognitive Pipeline Coherence Epic (#1220)

This slot's job is to work through the sub-epics of #1220 until all are closed.
The queue has the remaining items. Run `work start` to pick up the next one.

## Epic Status

| Sub-epic | Issue | Status | Module | Findings |
|----------|-------|--------|--------|----------|
| SE1: Pipeline Spine | #1221 | **Done** | cognition core | 0 remaining (+2 deferred: #1231, #1232) |
| SE2: CAPS Rework | #1222 | **Queued** | caps-engine, caps-testing, caps-llm-classifier, caps-situation-cbr | 8 findings (B1-B12 excl. landed B11/B13/B14) |
| SE3: Storage & Data Integrity | #1223 | **Done** | memory-sqlite, mindmap-sqlite, mindmap | 0 remaining |
| SE4: Consolidation Phases | #1224 | **Done** (this session) | mindmap-intelligence | 0 remaining |
| SE5: cognitive-index | #1225 | **Done** | cognitive-index | 0 remaining |
| SE6: Affect & Emotion | #1226 | **Queued** | cognition (mood/drive/appraisal/regulation) | 14 findings (C2-C7, C9-C14, C16-C17, C20-C21) |
| SE7: Orchestrators | #1227 | **Queued** | cognition (goal/narrative/personality/hygiene) | 10 findings (E1, E4-E10, E12-E17) |

**4 of 7 sub-epics done. 3 remaining in the queue.**

## Queue

The `.queue` has SE2, SE6, SE7 in that order. All three are unblocked:
- SE2 (CAPS) is independent — different Maven modules, no dependencies
- SE6 and SE7 were blocked on SE1 (pipeline spine) which is done

Run `work start` — it picks up SE2 (#1222) first. Each sub-epic follows the
same pattern: read the issue body for findings, brainstorm or go straight to
plan (the findings are concrete enough to plan directly), implement with TDD,
review, land.

## How to Pick Up a Sub-Epic

1. `work start` picks the next queued item
2. Read the **issue** on GitHub — it lists the findings, modules, and file ownership
3. Read the **epic plan**: `docs/specs/cognitive-review-analysis/2026-11-24-epic-plan.md`
4. Read the **triage**: `docs/specs/cognitive-review-analysis/2026-11-24-cognitive-review-triage.md`
5. The findings are concrete code bugs — brainstorm only if the approach is unclear

## Cross-Repo Coordination

- #1228 (vocabulary alignment with eidos) — coordinate with eidos repo
- SE6/SE7 touch `cognition` module files that SE1 already modified — rebase on
  latest main before starting

## Deferred Items

Two items deferred from earlier sub-epics:
- Wire configureSearchBudget/configureCuriosity into builder (S/Med) — follow-up to SE1
- Fix deriveQualitySignal timing in recordInteraction (XS/Med) — deferred to SE6

## SE4 Session Notes (2026-11-25)

Three cross-cutting principles emerged that may inform SE6/SE7 work:
1. **Entity resolution reuse** — SurfaceFormTrie is already a dependency of
   mindmap-intelligence; consider for other modules that do ad-hoc entity matching
2. **Tenant-scoped state** — any `ConcurrentHashMap` keyed by principal alone
   should be checked for tenant isolation
3. **Threshold safety** — irreversible operations (merge, erasure) need higher
   evidence bars than reversible ones

Spec gaps not implemented (not regressions, documented as Notes):
- MindMapExtractor trie-first + subgraph-scoped fuzzy tiers
- SubThoughtExtractor SUBJECT fallback (needs CaseMemoryStore API change)
