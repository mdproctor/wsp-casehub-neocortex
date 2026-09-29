# HANDOFF — casehub-neocortex

## Last Session

Designed and began implementing blocks#303 — migrating the entire social cognition layer from blocks to neocortex. First-principles analysis ("would this be used without neocortex?") expanded scope from 8 orchestrators to the full social cognition package (~213 files, ~13K LOC). Completed batches 1-3 of 7: module scaffolding (cognition-api + cognition), 95 value type migrations to cognition-api, and store consolidation (NarrativeMemory, StrategyMemory, UserProfileMemory, MentalModelMemory replacing ad-hoc Store SPIs).

## Immediate Next Step

Resume executing-plans at Batch 4: move pure-computation orchestrators (Mood, Drive, Narrative, PersonalityEvolution) to the cognition module. Open IntelliJ workspace with both repos first.

## Cross-Module

- blocks#303 modifies both neocortex and blocks repos. blocks is on main at 52e40944.
- New types from #317/#318 (CognitiveProfileParticipant, DomainActivationParticipant, DomainActivationSnapshot, 3 new prompt sections) need inclusion in later migration batches.

## References

- `wsp/specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `wsp/specs/issue-303-migrate-cognitive-state/decisions.md` — 6 design decisions
- `wsp/plans/2026-09-29-cognition-migration.md` — implementation plan (7 batches)
- `wsp/scripts/migrate_types.py` — cross-repo file migration script
- `wsp/scripts/fix_imports.py` — cross-subpackage import fixer
- `wsp/blog/2026-09-29-mdp01-the-brain-that-lived-in-the-wrong-body.md` — diary
