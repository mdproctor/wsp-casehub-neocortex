# HANDOFF — casehub-neocortex

## Last Session

Completed quality pass queue (.plan): #388, #362, #367. All three landed on main, pushed, issues closed.

- **#388** — DomainActivation.correlate() now skips empty subgraphs instead of aborting the batch. 3 new tests.
- **#362** — Orphaned SPI audit: added NoOpAgentTrustProvider @DefaultBean, removed empty VocabularyNormalizationDecorator, kept CaseEnrichmentStep as consumer extension point.
- **#367** — SPI completeness: @DefaultBean audit found zero new needed (2 already exist, 3 not CDI, 2 intentionally required, 1 gracefully degrades). Added 57 contract tests across 5 SPIs (CursorStore, CorpusStore/Reader, ChangeSource, QueryExpander, RelevanceEvaluator).

## Immediate Next Step

New quality pass queue in .plan (4 issues, #361 is active):

1. **#361** — resolve mindmap → cognitive-index upward dependency (S/High — architectural, moves code between modules)
2. **#346** — optional text-similarity corroboration for graduation scoring (S/Med — feature)
3. **#365** — configuration consistency — naming, feature flags, fail-fast, timeouts (M/Med — refactor pass)
4. **#366** — config reference documentation — all properties (S-M/Low — docs sweep, do after #365)

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
