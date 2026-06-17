# RAG Hortora Shared-Code Gaps — Design Spec

**Date:** 2026-06-17
**Status:** Approved — pending implementation
**Issue:** casehubio/neural-text#35
**Cross-refs:** casehubio/engine#521 (CaseRetriever call-site update), casehubio/parent#270 (PLATFORM.md dependency map)

---

## Problem

Hortora's garden retrieval engine (`Hortora/engine`) duplicates significant code from neural-text's `rag` module: Qdrant integration, ingestion orchestration, cursor management, change detection, metadata extraction. The duplication exists because `rag` has three hard blockers preventing Hortora from consuming it directly:

1. Sparse embedding is mandatory — no dense-only mode
2. Point IDs are random — no idempotent upserts
3. No query-time payload filtering on `CaseRetriever`

This spec addresses all three. After implementation, Hortora drops 6 classes and depends on `casehub-rag-api` + `casehub-rag` directly.

---

## Change 1: PayloadFilter — sealed filter algebra in rag-api

New type in `rag-api/src/main/java/io/casehub/rag/PayloadFilter.java`:

```java
public sealed interface PayloadFilter {

    record Eq(String field, String value) implements PayloadFilter {}
    record In(String field, List<String> values) implements PayloadFilter {}
    record Not(PayloadFilter inner) implements PayloadFilter {}
    record And(List<PayloadFilter> filters) implements PayloadFilter {}

    static PayloadFilter eq(String field, String value) { return new Eq(field, value); }
    static PayloadFilter in(String field, List<String> values) { return new In(field, List.copyOf(values)); }
    static PayloadFilter not(PayloadFilter inner) { return new Not(inner); }
    static PayloadFilter and(PayloadFilter... filters) { return new And(List.of(filters)); }
}
```

Tier 1 pure — zero dependencies beyond `java.util`. Sealed for exhaustive pattern matching in implementations. Four operations: keyword equality, multi-value membership, negation, conjunction.

---

## Change 2: CaseRetriever SPI signature — add filter parameter

**`CaseRetriever`:**

```java
public interface CaseRetriever {
    List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter);
}
```

**`ReactiveCaseRetriever`:**

```java
public interface ReactiveCaseRetriever {
    Uni<List<RetrievedChunk>> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter);
}
```

`filter` is nullable — `null` means no payload filtering. No backward-compatible overload — all callers update explicitly.

### Call sites to update (all within this repo)

| Class | Module | Change |
|---|---|---|
| `HybridCaseRetriever` | rag | Implementation — apply filter |
| `ReactiveHybridCaseRetriever` | rag | Implementation — apply filter |
| `BlockingToReactiveCaseRetriever` | rag | Pass through |
| `InMemoryCaseRetriever` | rag-testing | Apply filter to in-memory chunks |
| `InMemoryReactiveCaseRetriever` | rag-testing | Apply filter |
| `HybridSearchDemo` | examples | Pass `null` |
| `RagPipelineIT` | examples | Pass `null` |
| `HybridSearchSmokeTest` | examples | Pass `null` |
| `BlockingToReactiveCaseRetrieverTest` | rag tests | Pass `null` |
| `BlockingReactiveParityTest` | rag-api tests | Update method reference |

### External callers

`casehub-engine` consumes `CaseRetriever` — tracked in casehubio/engine#521. Mechanical migration: pass `null` at every call site.

---

## Change 3: Optional sparse embeddings

### Bean producers

Both `RagBeanProducer` and `ReactiveRagBeanProducer`:

```java
// Before:
@Inject SparseEmbedder sparseEmbedder;

// After:
@Inject Instance<SparseEmbedder> sparseEmbedderInstance;

// In producer method:
SparseEmbedder sparseEmbedder = sparseEmbedderInstance.isResolvable()
    ? sparseEmbedderInstance.get() : null;
```

Follows the pattern already used for `CrossEncoderReranker`.

### QdrantEmbeddingIngestor

`sparseEmbedder` field becomes nullable:

- **`ingest()`**: skip `sparseEmbedder.embedBatch()` when null. Build points with dense vector only.
- **`ensureCollection()`**: skip `SparseVectorConfig` when null. Collection gets dense `VectorParamsMap` only.
- **`buildPoint()`**: when sparse map is null, named vectors contains only `denseVectorName`.

### HybridCaseRetriever

`sparseEmbedder` field becomes nullable:

- **When null**: skip sparse query embedding, skip sparse prefetch, use direct dense nearest-neighbor query instead of RRF fusion. Retriever degrades to dense-only search.
- **When present**: unchanged — full hybrid RRF.
- Reranking remains independently controlled.

### Reactive variants

`ReactiveQdrantEmbeddingIngestor` and `ReactiveHybridCaseRetriever` — same changes mirrored.

### Config

`RagConfig.sparseVectorName()` stays but is only read when `sparseEmbedder` is non-null. No config changes.

---

## Change 4: Deterministic point IDs

### QdrantEmbeddingIngestor.buildPoint()

Replace `UUID.randomUUID()` with `UUID.nameUUIDFromBytes()` (v3, JDK built-in):

```java
// In ingest(), where i is the chunk's position in the list:
String idInput = chunk.sourceDocumentId() + "#" + i;
UUID pointId = UUID.nameUUIDFromBytes(idInput.getBytes(StandardCharsets.UTF_8));
```

Every chunk gets a deterministic ID from `sourceDocumentId + "#" + listIndex`. Single-chunk documents get `sourceDocumentId + "#0"`. Stable as long as the same splitter produces the same chunk count and order — which `DocumentSplitters.recursive()` guarantees for the same input.

Same change in `ReactiveQdrantEmbeddingIngestor`.

### Migration

Existing Qdrant collections have random UUIDs. After this change, re-ingesting creates new deterministic points alongside old random ones. A one-time `reconcileAll()` cleans up — deletes stale points, reingests with new IDs. No special migration code needed.

---

## Change 5: PayloadFilter translation in rag implementations

New package-private class in `rag/src/main/java/io/casehub/rag/runtime/PayloadFilterTranslator.java`:

```java
final class PayloadFilterTranslator {
    static Optional<Filter> toQdrantFilter(PayloadFilter filter) {
        if (filter == null) return Optional.empty();
        return Optional.of(Filter.newBuilder()
            .addMust(toCondition(filter))
            .build());
    }

    private static Condition toCondition(PayloadFilter filter) {
        return switch (filter) {
            case PayloadFilter.Eq eq -> ConditionFactory.matchKeyword(eq.field(), eq.value());
            case PayloadFilter.In in -> ConditionFactory.matchKeywords(in.field(), in.values());
            case PayloadFilter.Not not -> ConditionFactory.not(toCondition(not.inner()));
            case PayloadFilter.And and -> {
                var nested = Filter.newBuilder();
                for (var f : and.filters()) nested.addMust(toCondition(f));
                yield ConditionFactory.filter(nested.build());
            }
        };
    }
}
```

Exhaustive pattern match on the sealed interface — adding a new variant forces a compile error.

### Filter composition in retrievers

`HybridCaseRetriever.retrieve()` and `ReactiveHybridCaseRetriever.retrieve()` compose payload filter with tenancy filter:

```java
Optional<Filter> tenantFilter = tenancyStrategy.tenantFilter(corpus);
Optional<Filter> payloadFilter = PayloadFilterTranslator.toQdrantFilter(filter);

Filter.Builder combined = Filter.newBuilder();
tenantFilter.ifPresent(tf -> combined.addAllMust(tf.getMustList()));
payloadFilter.ifPresent(pf -> combined.addAllMust(pf.getMustList()));
Optional<Filter> mergedFilter = combined.getMustCount() > 0
    ? Optional.of(combined.build()) : Optional.empty();
```

Applied to both dense and sparse prefetch queries (hybrid mode) or the single dense query (dense-only mode).

### InMemoryCaseRetriever

Filter applied to in-memory chunk list via metadata matching. `Eq` checks `metadata.get(field).equals(value)`, `In` checks `values.contains(metadata.get(field))`, etc. Keeps test behavior consistent without Qdrant.

---

## What Hortora drops after this ships

| Hortora class | Replaced by |
|---|---|
| `GardenIngestionService` | `CorpusIngestionService` via `CorpusIngestionBinding` |
| `GardenIndexer` | `CorpusIngestionService` startup lifecycle |
| `FileCursorStore` | `rag:FileCursorStore` |
| `ExtractionResult` | `rag-api:ExtractionResult` |
| `QdrantClientProducer` | `rag:QdrantClientProducer` |
| `GardenMetadataExtractor` | Own impl of `MetadataExtractor` SPI (stays in engine) |

## What stays in Hortora

- Federation: `ChainWalker`, `FederationConfig`, `FederationConfigParser`, `RemoteGardenClient`
- MCP server: `GardenMcpTools`
- REST: `SearchResource` — slimmed to delegate to `CaseRetriever` + federate via `ChainWalker`
- CDI: `CorpusIngestionBinding` producer, no-op `CurrentPrincipal` `@Alternative`

---

## Tenancy

Not in scope. `CorpusRef.tenantId` remains required. Hortora provides a constant tenant ID and a matching no-op `CurrentPrincipal` `@Alternative`. `MemoryPermissions.assertTenant()` is already a no-op for background operations (watcher/startup) where `RequestContextCheck.isActive()` returns false.

---

## Platform coherence

- **Tier 1 purity**: `PayloadFilter` is pure Java, sealed, zero dependencies. No Qdrant types leak into `rag-api`.
- **Reactive parity**: all SPI changes mirror between blocking and reactive variants.
- **Cross-repo propagation**: casehubio/engine#521 tracks `CaseRetriever` call-site updates.
- **PLATFORM.md**: casehubio/parent#270 tracks dependency map update.
