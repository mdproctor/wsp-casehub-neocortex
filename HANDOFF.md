# HANDOFF — casehub-neocortex

## Last Session

Designed and implemented composable cognitive avatars (#1219). Full session: brainstorming (10 design decisions, standard decision review, standard spec review), then implementation of Batches 1-3 (4 of 4 batches, 7 of 8 tasks). Research cross-references updated in era1, era3, and CHARACTER-EMERGENCE-FINDINGS.

**Built:**
- `CognitivePromptSource` interface extracted from `CognitiveLifecycle` (cognition-api)
- `BriefingConfig` added as 9th component of `CognitiveDefaults` (cognitive-index)
- New `cognitive-runtime` module with `CognitiveCapability` SPI, `CognitiveAvatar` composition root, 6 capabilities (Briefing, Goal, Temporal, Memory, EntityKnowledge, Disposition)
- 2 persona YAML profiles (stoic-mentor, bold-strategist) with three-layer evocative briefing
- 42 tests, full project build green

**Filed:** #1233 (XS — missing unit tests for MemoryCapability + EntityKnowledgeCapability), #1234 (XS — add disposition axes to persona YAMLs)

**Infrastructure note (carried forward):** 32 commits in `~/claude/public/casehub/neocortex` are unpushed. `canonical_sync.py publish neocortex` fails with a doubled-path bug. Not blocking.

## Queue State

Branch `issue-1219-briefed-cognitive-avatars` active. Project and workspace both on the branch.

- **#1219** (Composable cognitive avatars — M/Med) — **active**, Batches 1-3 done, Batch 4 (Docs) remaining

## Remaining Work on #1219

**Batch 4 — Documentation (1 task):**
- Task 8: Update consumer-guide.md (add cognitive-runtime module), CLAUDE.md (module structure + maven coordinates), ARC42STORIES.MD (building block + journey)

**Follow-up issues (not blocking #1219 close):**
- #1233 — Add unit tests for MemoryCapability and EntityKnowledgeCapability (XS/Low)
- #1234 — Add disposition axes to persona YAML profiles (XS/Low)

**CognitiveAvatarProducer and ProfileDescriptorViewSource** — defined in the spec but not yet committed. The CDI wiring for creating avatars from profiles. The module works for programmatic consumers without CDI; the producer is needed for Quarkus integration.

## Key Design Decisions

Briefing and emergence are orthogonal reasoning-shaping strategies, not layers of one stack. Both share the same CDI infrastructure (MindMapStore, CaseMemoryStore, etc.). The capability list is not a ceiling — consolidation, practical appraisal, ticks, inner thoughts, hierarchy of needs can all be composed as future capabilities without architectural change.

Echo mechanism is research-validated (era1 P16/P25/P26/P30, era3 template suppression finding). Prescriptive echo suppresses character — must be evocative.

## Immediate Next Step

Run `work continue`. Complete Task 8 (documentation updates), then `work end` to land.

## References

- casehubio/neocortex#1219 — focal issue
- Design spec: `specs/issue-1219-briefed-cognitive-avatars/2026-11-24-composable-cognitive-avatars-design.md`
- Decisions: `specs/issue-1219-briefed-cognitive-avatars/decisions.md` (10 decisions)
- Plan: `plans/2026-11-24-composable-cognitive-avatars.md`
- Research: `docs/research/era1-character-taxonomy-research.md` (echo validation), `docs/research/era3-cognitive-layering-research.md` (template suppression)
