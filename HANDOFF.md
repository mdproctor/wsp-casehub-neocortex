# Handoff — 2026-07-12

## What Changed

Branch `issue-137-approx-dtw-typed-cbr` covers #131 (typed CBR feature values) + #137 (approximate DTW). Execution order: #131 first. Sealed `FeatureValue` hierarchy (7 variants) replaces `Map<String, Object>` across all CBR APIs. Design spec at `docs/specs/2026-07-12-typed-features-and-approx-dtw-design.md`. Plan at workspace `plans/2026-07-12-typed-features-and-approx-dtw.md`.

**Completed this session:** Tasks 1–2 of the plan (FeatureValue type + core API migration). All `memory-api` production code migrated, 470 tests green. InMemoryCbrCaseMemoryStore filter matching migrated (zero errors). 4 orphaned branches closed (issue-30, issue-56, issue-672, fix-ce). 37 diary entries published. featureSimilarities (engine#672) and CE score fix (fix-ce) merged to main.

**In progress:** Task 3 — `CbrCaseMemoryStoreContractTest` (1707 lines) has ~100 remaining type errors. All mechanical wrapping: `Map.of("key", rawValue)` → `Map.of("key", FeatureValue.xxx(rawValue))` plus structured value wrapping (stringList, numberList, struct, structList). Store itself is clean.

## Immediate Next Step

Continue Task 3: fix remaining ~100 type errors in `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`. Run `mvn test -pl memory-cbr-inmem` to verify. Then Tasks 4–9 per the plan.

## What's Left

- Contract test migration (~100 errors) · M · Low — mechanical wrapping
- Qdrant backend migration (Task 4) · M · Low — CbrPointBuilder, CbrMemorySerializer, CbrQueryTranslator, QdrantCbrCaseMemoryStore
- EmbeddingTextSimilarity migration (Task 5) · XS · Low
- Full build verification + cross-repo engine issue (Task 6) · S · Low
- DtwSimilarity early abandonment (Task 7) · S · Med — new 5-arg overload with row-minimum tracking
- LbKeogh utility (Task 8) · S · Med — envelope computation + lower bound
- DTW optimization integration (Task 9) · M · Med — scorer threshold pass-through + store loop

## What's Next

*Unchanged — retrieve with: `git show HEAD~1:HANDOFF.md`*

## Key References

- Spec: `docs/specs/2026-07-12-typed-features-and-approx-dtw-design.md`
- Plan: workspace `plans/2026-07-12-typed-features-and-approx-dtw.md`
- Blog: `blog/2026-07-12-mdp03-the-type-that-replaced-object.md`
- Journal: `design/JOURNAL.md`
