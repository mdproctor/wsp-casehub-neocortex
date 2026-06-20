# CursorStore.delete() + ReactiveCorrectiveCaseRetriever Design

**Date:** 2026-06-20
**Issues:** casehubio/neural-text#38, casehubio/neural-text#41
**Branch:** issue-38-cursorstore-delete-reactive-crag

---

## #38 — CursorStore.delete()

### Problem

Hortora engine needs to reset the ingestion cursor when migrating from dense-only to hybrid search. The current workaround is `CursorStore.save(bindingName, "")` — this works with `FileCursorStore` (empty content returns `Optional.empty()` on load) but couples to an implementation detail. The SPI contract makes no guarantee about empty-string semantics.

### Design

**SPI change** (`rag-api`): Add `default void delete(String corpusName)` to `CursorStore`. Default body calls `save(corpusName, "")` for backward compatibility with custom implementations.

**FileCursorStore override** (`rag`): Delete the `{baseDir}/{corpusName}.cursor` file. No-op if the file doesn't exist. Throws `UncheckedIOException` on I/O failure, matching existing `save`/`load` error handling.

**InMemoryCursorStore override** (`rag-testing`): `cursors.remove(corpusName)`.

### Tests

| Test | Implementation | Assertion |
|------|---------------|-----------|
| `deleteRemovesCursor` | Both | save → delete → load returns empty |
| `deleteNonExistentIsNoOp` | Both | delete unknown corpus, no exception |
| `deleteRemovesFile` | FileCursorStore | verify `.cursor` file physically removed |

---

## #41 — ReactiveCorrectiveCaseRetriever

### Problem

CRAG (#33) ships with a blocking `CorrectiveCaseRetriever` `@Decorator`. The reactive path (`ReactiveCaseRetriever`) is not yet decorated — reactive consumers bypass CRAG entirely.

### Design

**Class:** `ReactiveCorrectiveCaseRetriever` in `rag-crag` module, package `io.casehub.rag.crag`.

**CDI wiring:** `@Decorator @Priority(100)` on `ReactiveCaseRetriever`. Classpath-activated — no `@IfBuildProperty` gate. Matches the blocking decorator's activation model: rag-crag on classpath = CRAG active for both paths.

**Constructor injection:**
- `@Delegate @Any ReactiveCaseRetriever delegate`
- `RelevanceEvaluator evaluator`
- `CragConfig config`
- `Event<RetrievalQuality> qualityEvent`

### Retrieve Flow

Mirrors the blocking decorator as a Uni chain:

1. `delegate.retrieve(query, corpus, maxResults, filter)` — returns `Uni<List<RetrievedChunk>>`
2. `.onItem().transformToUni()` → offload `evaluator.evaluateBatch()` to worker thread via `Uni.createFrom().item(() -> ...).runSubscriptionOn(Infrastructure.getDefaultWorkerPool())`
3. Grade chunks with evaluation results
4. Filter out INCORRECT grades
5. If surviving count < maxResults AND there were incorrect chunks → expand:
   - Delegate again with `maxResults * config.expansionFactor()`
   - Offload second evaluation to worker thread
   - Deduplicate using `sourceDocumentId + "\0" + content.hashCode()` key
   - Merge expanded results
6. Sort: CORRECT before AMBIGUOUS, then by relevance score
7. Truncate to `maxResults`
8. `qualityEvent.fireAsync(...)` — fire-and-forget, do not chain `CompletionStage` into result
9. Return `Uni<List<RetrievedChunk>>` with graded results

### Shared Logic Extraction

The evaluate → filter → expand → deduplicate → sort logic is identical between blocking and reactive decorators. Extract a package-private `CragEvaluationLogic` helper class:

- Pure functions operating on `List<RetrievedChunk>` and `List<RelevanceGrade>`
- No CDI, no Uni dependencies
- Both decorators call into this shared logic
- Refactor blocking `CorrectiveCaseRetriever` to use it too

Methods:
- `gradeChunks(List<RetrievedChunk>, List<RelevanceGrade>)` → `List<RetrievedChunk>` with grades applied
- `filterAndPartition(List<RetrievedChunk>)` → survivors + whether expansion needed
- `deduplicateAndMerge(List<RetrievedChunk> original, List<RetrievedChunk> expanded)` → merged list
- `sortAndTruncate(List<RetrievedChunk>, int maxResults)` → final result
- `buildQualityEvent(...)` → `RetrievalQuality` record

### Testing

**Unit tests** (`CorrectiveCaseRetrieverTest` pattern — pure JUnit, constructor injection, no `@QuarkusTest`):

| Test | Assertion |
|------|-----------|
| `allCorrectChunksPassThrough` | No filtering, no expansion |
| `allIncorrectTriggersExpansion` | Delegate called again with expanded maxResults |
| `mixedGradesFilterIncorrect` | INCORRECT removed, CORRECT + AMBIGUOUS kept |
| `truncationPrefersCORRECT` | CORRECT sorted before AMBIGUOUS |
| `emptyCorpusReturnsEmpty` | Empty delegate result → empty output |
| `smallCorpusNoExpansion` | Below threshold, no expansion triggered |
| `qualityEventFired` | `fireAsync()` called with correct counters |
| `expansionDeduplicates` | Same chunk from original + expansion appears once |

Event mock implements `fireAsync()` returning `CompletableFuture.completedFuture()`.

**Integration test** (`example-rag-pipeline`): `CragReactivePipelineIT` — exercises reactive decorator end-to-end with `InMemoryRelevanceEvaluator`.

### Additional Assertions (from issue body)

Add `grade == UNGRADED` assertions to existing tests:
- `HybridCaseRetrieverTest` — confirms without CRAG, chunks are ungraded
- `BlockingToReactiveCaseRetrieverTest` — same confirmation on reactive bridge path

---

## Module Impact

| Module | Changes |
|--------|---------|
| `rag-api` | `CursorStore.delete()` default method |
| `rag` | `FileCursorStore.delete()` override + tests |
| `rag-testing` | `InMemoryCursorStore.delete()` override + tests |
| `rag-crag` | `ReactiveCorrectiveCaseRetriever`, `CragEvaluationLogic`, refactor blocking decorator, tests |
| `example-rag-pipeline` | `CragReactivePipelineIT` |

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Activation model | Classpath-activated | Matches blocking decorator; avoids untested `@IfBuildProperty` on `@Decorator` |
| CDI event | `fireAsync()` fire-and-forget | Reactive path should not block on observer completion |
| Blocking evaluation | Worker thread offload | `RelevanceEvaluator` is blocking (cross-encoder); same pattern as `BlockingToReactiveCaseRetriever` |
| Shared logic | Extract `CragEvaluationLogic` | Avoids duplicating grading/filtering/sorting between decorators |
| Reactive evaluator SPI | Deferred | YAGNI — can be added later without changing the decorator |
