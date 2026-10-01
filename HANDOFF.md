# HANDOFF — casehub-neocortex

## Last Session

- **#361** — Extracted `RuleResolver` SPI into mindmap-api to break mindmap → cognitive-index upward dependency. DeclarativeRuleRegistry implements it. 9 files changed, full build green. Landed on main, pushed, issue closed.

## Immediate Next Step

Quality pass queue in .plan (3 issues remaining, #346 is active):

1. **#346** — optional text-similarity corroboration for graduation scoring (S/Med — feature)
2. **#365** — configuration consistency — naming, feature flags, fail-fast, timeouts (M/Med — refactor pass)
3. **#366** — config reference documentation — all properties (S-M/Low — docs sweep, do after #365)

## Parked (Large Architecture)

- **#391** — Adaptive cognitive brief (L/High)
- **#392** — Multi-agent Inside Out architecture (XL/High)
- **#393** — Context-budget-aware prompt rendering (L/High)

## Cross-Module

Blocks branches landed on main (this session):
- `issue-325-remove-social-jpa` — removed 3 orphaned social-jpa modules (2109 lines deleted)
- `issue-324-restore-goal-producers` — restored CDI/Spring producers for #323 + #324 (rebased on top of #325)
- Pushed to canonical local main

## References

- `plans/2026-09-29-cognition-migration.md` — migration plan (complete)
- `specs/issue-303-migrate-cognitive-state/decisions.md` — design decisions
