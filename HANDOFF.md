# Handoff — 2026-07-19

## What Changed

Branch `issue-130-batch-sx-cbr-fixes` closed. Landed as `3cc09f5` on main. Pushed to both origin (mdproctor/neocortex) and upstream (casehubio/neocortex). Closes #130, #143, #128, #162, #141, #155.

**Delivered:** Six S/XS CBR fixes feeding back into CaseHub foundation and apps:

- **#130** — `examples/pom.xml` aggregator for casehub-examples integration. Follow-up filed: casehubio/examples#1.
- **#143** — `CbrFeatureSchema.learningRate()` — optional per-caseType learning rate for `recordOutcome` EMA. Nullable, validated [0,1], defaults to `DEFAULT_LEARNING_RATE` (0.2). All store implementations updated (InMemory, JPA, Qdrant).
- **#128** — `CbrSimilarityScorer` now respects `LocalSimilarityFunction` overrides for structured fields (CategoricalList, NumericList, NestedObject, ObjectList). Without override, fields are still skipped. Dead throws changed to `return 0.0`. Deferred: built-in defaults (Jaccard, recursive weighted) → #169.
- **#162** — `InMemoryCbrCaseMemoryStore.clearCases()` for test isolation. Clears cases only, preserves schemas. Contract test gains `clearStore()` hook.
- **#141** — JPA `deserializeMap` → `deserializeFeatures` returning `Map<String, FeatureValue>` directly. Cleanup, not a fix — compilation errors were already resolved.
- **#155** — `SupersessionStatus` record + `getSupersessionStatus()` / `findSupersededCases()` on `CbrCaseMemoryStore` + reactive parity. Abstract methods (not defaults) for compile-time decorator safety. `reinstatedAt` distinguishes "never superseded" from "was superseded then reinstated". `supersede()` nulls `reinstatedAt`. 38 files touched — 14 decorators, 3 core stores, ~20 test stubs. V5 Flyway migration for JPA.

Design review: 2 rounds, 14 issues, all resolved. Key findings: clearAll→clearCases (schemas survive tests), SupersessionStatus gains caseId+reinstatedAt, abstract methods not defaults for decorator safety, structured field throws→return 0.0.

## Immediate Next Step

Pick next from backlog. No blockers.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #168 | Engine gardenUnretrieved → use RetrievalAnalyzer | S | Low | Cross-repo (engine) |
| #167 | Query→document→outcome correlation graph | M | High | Follow-up from #109 |
| #166 | Reactive JPA backend for CbrCaseMemoryStore | M | Med | Eliminate blocking bridge |
| #157 | FeatureStatistics + CbrSuggestions → memory-api | M | Med | Currently stuck in casehub-life |
| #169 | Built-in defaults for structured field similarity | M | Med | Follow-up from #128 |
| #148 | Cross-plan structural analysis / ensemble adaptation | M | High | |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready |

## References

- Spec: `specs/2026-07-19-batch-sx-cbr-fixes-design.md` (workspace)
- Plan: `plans/attic/issue-130-batch-sx-cbr-fixes/2026-07-19-batch-sx-cbr-fixes.md` (workspace)
- Design review: `~/adr/casehub-neocortex/batch-sx-cbr-fixes-20260719-213716/` (2 rounds, 14 issues)
- Follow-up: casehubio/examples#1 (collapse neocortex entries), #169 (built-in structured field defaults)
