# HANDOFF — casehub-neocortex

## Last Session

Landed #270 (hot-reload cognitive profiles) on main — CognitiveProfileWatcher with directory-watcher, atomic volatile swaps, CDI event notification. Then created 8 cognitive improvement issues (#338–#345) from research. Started brainstorming for S-batch (#340, #342, #344) — context gathered, first design question answered.

## Branch State

**Branch:** `issue-340-cognitive-s-batch` — covers #340, #342, #344
**State:** mid-brainstorm — context gathered, one decision agreed (Subject-based corroboration for #340), no spec written yet

## Key Context for Resume

- **#340:** `DefaultGraduationScorer` is a 1-line passthrough. Corroboration should match on `Subject` (same entity) — 3+ converging episodes. Follow-up #346 filed for text similarity.
- **#342:** `ReflectionService` does NOT exist despite CLAUDE.md describing it. Retarget to `ConsolidationScheduler` — significance accumulator using event count or cumulative confidence (not importance scoring, which is #339).
- **#344:** Diversity injection at retrieval level after scoring, before top-K return. When results cluster too tightly, inject structurally different lower-ranked case.

## Next Action

Resume brainstorming: propose approaches for each issue, capture decisions, write spec.
