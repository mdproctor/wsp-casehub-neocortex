# Native Reactive Qdrant Implementations + Bridge Thread-Offloading Tests

**Date:** 2026-06-09
**Issues:** casehubio/neural-text#13, casehubio/neural-text#14
**Branch:** `issue-13-native-reactive-qdrant`
**Module:** `rag/` (implementations), `rag-api/` (Javadoc only)

---

## Problem

The `@DefaultBean` bridges (`BlockingToReactiveCorpusStore`, `BlockingToReactiveCaseRetriever`)
wrap blocking Qdrant calls on the Mutiny worker pool via `runSubscriptionOn()`. This works but
adds a thread hop per call — the blocking impl calls `ListenableFuture.get()` on a worker thread
when the Qdrant client already provides natively async `ListenableFuture` methods.

Separately, the bridge tests verify delegation correctness but not that the delegate actually
runs on a worker thread. Removing `runSubscriptionOn()` would silently block the Vert.x event
loop with no test failure.

## Solution

### #13 — Native reactive Qdrant implementations

Two new classes in `rag/`, package `io.casehub.rag.runtime`:

**`ReactiveQdrantCorpusStore implements ReactiveCorpusStore`**
- `@IfBuildProperty(name = "casehub.rag.reactive.enabled", stringValue = "true")`
- `@ApplicationScoped`
- Displaces the `@DefaultBean` bridge when the property is set

**`ReactiveHybridCaseRetriever implements ReactiveCaseRetriever`**
- Same CDI gating
- Same displacement behaviour

#### CDI gating rationale

`@IfBuildProperty` without a `@ConfigRoot(phase = BUILD_TIME)` declaration — neural-text has
no `deployment/` module. The property is evaluated during the consuming app's augmentation.
Matches the casehub-eidos precedent (`casehub.eidos.reactive.enabled`).

Consuming apps opt in by setting `casehub.rag.reactive.enabled=true` in `application.properties`.
Default is `false` — only the `@DefaultBean` bridges are active.

#### ListenableFuture → Uni bridge

Package-private utility class `QdrantFutures` in `io.casehub.rag.runtime`:

```java
static <T> Uni<T> toUni(ListenableFuture<T> future) {
    return Uni.createFrom().emitter(em ->
        Futures.addCallback(future, new FutureCallback<>() {
            public void onSuccess(T result) { em.complete(result); }
            public void onFailure(Throwable t) { em.fail(t); }
        }, MoreExecutors.directExecutor()));
}
```

Single static method. `directExecutor()` — callback runs on the gRPC executor (Qdrant's
internal Netty event loop), no extra thread hop. Both reactive impls use this.

#### Blocking embedding offload

`EmbeddingModel.embed()` and `SparseEmbedder.embed()` are blocking (synchronous ONNX inference).
Native reactive impls offload embedding to the worker pool, then chain natively async Qdrant calls:

```
assertTenant (inline, no I/O)
  → embed on worker pool via runSubscriptionOn(workerPool) → Uni<EmbeddingResult>
    → chain natively async Qdrant call via toUni() → Uni<result>
```

Methods with no embedding (`deleteDocument`, `deleteCorpus`, `listDocuments`) are purely
native async — no worker pool involved.

#### Method-by-method design

**`ReactiveQdrantCorpusStore`:**

| Method | Embedding | Qdrant call | Notes |
|---|---|---|---|
| `ingest` | Dense + sparse batch on worker pool | `upsertAsync` via `toUni()` | Build points between embed and upsert |
| `deleteDocument` | None | `deleteAsync` via `toUni()` | Pure async |
| `deleteCorpus` | None | `deleteCollectionAsync` or `deleteAsync` via `toUni()` | Depends on `TenancyStrategy` |
| `listDocuments` | None | `scrollAsync` via `toUni()` in a pagination loop | Recursive `Uni` chaining — each page checks `hasNextPageOffset()` and chains the next scroll or completes |

**`ReactiveHybridCaseRetriever`:**

| Method | Embedding | Qdrant call | Notes |
|---|---|---|---|
| `retrieve` | Dense + sparse on worker pool | `collectionExistsAsync` → `queryAsync` via `toUni()` | Optional reranking offloaded to worker pool (blocking ONNX) |

`retrieve` flow:
1. `assertTenant` — inline
2. `toUni(client.collectionExistsAsync(...))` — native async
3. If exists → offload dense + sparse embedding to worker pool
4. Chain `toUni(client.queryAsync(queryPoints))` — build prefetch queries with RRF fusion
5. Map `ScoredPoint` → `RetrievedChunk` — inline (CPU-only)
6. If reranking enabled → offload `reranker.rerank()` to worker pool (blocking ONNX)

#### `ensureCollection`

Lazy collection creation. Same `ConcurrentHashMap.newKeySet()` fast-path guard. Returns
`Uni<Void>` — chains `collectionExistsAsync` → `createCollectionAsync` via `toUni()`.

#### CDI producer additions

`RagBeanProducer` gets two new `@Produces` methods, each annotated with the same
`@IfBuildProperty` gate. They construct the reactive impls with the same dependencies
as the blocking impls (same `QdrantClient`, `EmbeddingModel`, `SparseEmbedder`,
`TenancyStrategy`, config values, `CurrentPrincipal`).

#### Dependencies

No new Maven dependencies. Guava (`Futures`, `FutureCallback`, `MoreExecutors`) is
already transitive from the Qdrant client. Mutiny is already a dependency of `rag/`
(transitive from `quarkus-arc`).

---

### #14 — Bridge thread-offloading regression tests

#### Thread assertion on bridge tests

Both `BlockingToReactiveCorpusStoreTest` and `BlockingToReactiveCaseRetrieverTest` get
a new test that verifies the delegate executes on a worker thread.

Pattern:
1. Create a recording delegate that captures `Thread.currentThread().getName()` during execution
2. Subscribe from the test thread
3. Assert the captured thread name differs from the test thread name
4. Assert the captured thread name contains `"executor-thread"` (Mutiny worker pool convention)

One test method per bridge class — all methods in each bridge use the same
`runSubscriptionOn` pattern, so verifying one method proves the wiring.

#### Parity test — no change

The manual `PAIRS` map in `BlockingReactiveParityTest` is adequate for two SPI pairs.
The issue notes "consider switching to naming-convention auto-discovery if more pairs
are added" — no third pair is being added in this branch, so no change.

#### Javadoc on reactive SPIs

Single-line class-level Javadoc on each reactive SPI in `rag-api/`:

```java
/** Reactive counterpart of {@link CorpusStore}. All methods return on the Vert.x event loop. */
public interface ReactiveCorpusStore { ... }

/** Reactive counterpart of {@link CaseRetriever}. All methods return on the Vert.x event loop. */
public interface ReactiveCaseRetriever { ... }
```

No method-level Javadoc — method signatures mirror the blocking SPI exactly and
the parity test enforces that.

---

## Testing

| Test class | Module | Type | What it verifies |
|---|---|---|---|
| `QdrantFuturesTest` | `rag` | Unit | `toUni()` propagates success, failure, and cancellation from `ListenableFuture` to `Uni`. Uses Guava `SettableFuture`. |
| `ReactiveQdrantCorpusStoreTest` | `rag` | Integration (Testcontainers) | Ingest → listDocuments round-trip, deleteDocument, deleteCorpus, tenant isolation, collection auto-creation. Mirrors `QdrantCorpusStoreTest`. |
| `ReactiveHybridCaseRetrieverTest` | `rag` | Integration (Testcontainers) | Ingest → retrieve round-trip, hybrid RRF fusion, cross-encoder reranking, tenant isolation. Mirrors `HybridCaseRetrieverTest`. |
| `BlockingToReactiveCorpusStoreTest` | `rag` | Unit (addition) | New: delegate executes on worker thread, not subscribing thread. |
| `BlockingToReactiveCaseRetrieverTest` | `rag` | Unit (addition) | New: delegate executes on worker thread, not subscribing thread. |

Existing tests (`QdrantCorpusStoreTest`, `HybridCaseRetrieverTest`, bridge delegation tests,
parity test) are unchanged.

---

## Files changed

| File | Action |
|---|---|
| `rag/src/main/java/io/casehub/rag/runtime/QdrantFutures.java` | New — `ListenableFuture` → `Uni` bridge utility |
| `rag/src/main/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStore.java` | New |
| `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java` | New |
| `rag/src/main/java/io/casehub/rag/runtime/RagBeanProducer.java` | Modified — two new `@Produces` methods |
| `rag/src/test/java/io/casehub/rag/runtime/QdrantFuturesTest.java` | New |
| `rag/src/test/java/io/casehub/rag/runtime/ReactiveQdrantCorpusStoreTest.java` | New |
| `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java` | New |
| `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCorpusStoreTest.java` | Modified — thread assertion |
| `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java` | Modified — thread assertion |
| `rag-api/src/main/java/io/casehub/rag/ReactiveCorpusStore.java` | Modified — class Javadoc |
| `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java` | Modified — class Javadoc |

---

## Platform coherence

- **Module tier:** all changes in `rag/` (Tier 3) except Javadoc additions to `rag-api/` (Tier 1) — no tier violation.
- **CDI gating:** follows `reactive-service-build-gating` protocol (PP-20260519-39a9a5). Matches casehub-eidos precedent for library modules without `deployment/`.
- **Parity:** existing `BlockingReactiveParityTest` covers structural parity. No new SPI methods.
- **No new dependencies.** Guava is transitive from Qdrant client.
- **Doc update needed:** `docs/repos/casehub-neural-text.md` in casehub-parent should note the reactive gating property after implementation ships.

## Out of scope

- Engine-side `casehub-engine-rag` adapter module — created when engine integrates (parent#164)
- Switching parity test to auto-discovery — not warranted for two pairs
- Reactive variants of `SparseEmbedder` or `EmbeddingModel` — upstream concern, not this repo
