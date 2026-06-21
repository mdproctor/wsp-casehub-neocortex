# HyDE — Hypothetical Document Embeddings for Query Expansion

**Issue:** casehubio/neural-text#32
**Date:** 2026-06-21
**Status:** Approved

## Problem

`CaseRetriever.retrieve(String query, ...)` uses a single `String query` for three distinct purposes: dense embedding, sparse embedding, and cross-encoder reranking. This overloading means any pre-retrieval query transformation (like HyDE) corrupts downstream scoring — if a decorator swaps the query string, reranking evaluates "does this chunk match the hypothetical document?" instead of "does this chunk answer the user's question?"

HyDE generates a hypothetical document passage from the query, then embeds *that* for vector search. The hypothetical document is closer in embedding space to actual relevant documents than the raw query, bridging the query-document vocabulary gap. But the original query must still be used for reranking and CRAG evaluation.

## Solution

Fix the overloaded `String query` at the SPI level. Replace it with `RetrievalQuery` — a value type carrying both the original query and optional expansion text. Each pipeline stage uses the right text for its purpose.

## Design

### RetrievalQuery (rag-api)

```java
public record RetrievalQuery(String text, String expandedText) {

    public RetrievalQuery {
        if (text == null || text.isBlank())
            throw new IllegalArgumentException("text must not be null or blank");
    }

    public static RetrievalQuery of(String text) {
        return new RetrievalQuery(text, null);
    }

    public String searchText() {
        return expandedText != null ? expandedText : text;
    }

    public RetrievalQuery withExpansion(String expandedText) {
        return new RetrievalQuery(text, expandedText);
    }
}
```

- `text()` — original query. Used for reranking, CRAG evaluation, logging.
- `expandedText()` — HyDE hypothetical document or template expansion. Null when no expansion applied.
- `searchText()` — resolves which text to embed: `expandedText` if present, else `text`.
- `withExpansion()` — produces a new query with expansion attached, preserving the original.

### CaseRetriever / ReactiveCaseRetriever SPI changes (rag-api)

Breaking change — `String query` → `RetrievalQuery query`:

```java
public interface CaseRetriever {
    List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus,
                                   int maxResults, PayloadFilter filter);

    default List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus,
                                           int maxResults) {
        return retrieve(query, corpus, maxResults, null);
    }
}
```

```java
public interface ReactiveCaseRetriever {
    Uni<List<RetrievedChunk>> retrieve(RetrievalQuery query, CorpusRef corpus,
                                        int maxResults, PayloadFilter filter);

    default Uni<List<RetrievedChunk>> retrieve(RetrievalQuery query, CorpusRef corpus,
                                                int maxResults) {
        return retrieve(query, corpus, maxResults, null);
    }
}
```

No String-based convenience methods on the SPI. Callers construct `RetrievalQuery` explicitly.

### QueryExpander SPI (rag-api)

```java
public interface QueryExpander {
    RetrievalQuery expand(RetrievalQuery query);
}
```

Takes `RetrievalQuery` (not `String`) for composability — each expander sees the original query and any prior expansion. No reactive variant; the HyDE decorator owns threading. No `@DefaultBean` — absence of a bean is the "off" state.

### rag-hyde module (new)

**Activation:** classpath + config. Both required.

```properties
casehub.rag.hyde.enabled=true    # gates @IfBuildProperty
casehub.rag.hyde.mode=llm        # "llm" (default) or "template"
```

**Decorators:**

`HydeCaseRetriever` — `@Decorator @Priority(200)` on `CaseRetriever`, gated by `@IfBuildProperty(name = "casehub.rag.hyde.enabled", stringValue = "true")`. Calls `QueryExpander.expand()`, delegates with the expanded query.

`ReactiveHydeCaseRetriever` — same for `ReactiveCaseRetriever`. Wraps `expander.expand()` with `runSubscriptionOn(Infrastructure.getDefaultWorkerPool())`.

**Priority 200** puts HyDE outermost — it executes before CRAG (Priority 100). The full pipeline:

```
raw query
  → HyDE @Priority(200): expand query, attach expandedText
    → CRAG @Priority(100): evaluate with text(), filter, expand search
      → HybridCaseRetriever: embed with searchText(), rerank with text()
```

**QueryExpander implementations:**

`LlmQueryExpander` — `@ApplicationScoped`, `@IfBuildProperty(name = "casehub.rag.hyde.mode", stringValue = "llm", enableIfMissing = true)`. Requires `ChatModel` bean. Configurable prompt template via `casehub.rag.hyde.prompt-template`.

`TemplateQueryExpander` — `@ApplicationScoped`, `@IfBuildProperty(name = "casehub.rag.hyde.mode", stringValue = "template")`. Uses configurable template string via `casehub.rag.hyde.template`.

**Dependencies:** `rag-api`, `langchain4j-core` (for ChatModel), Quarkus Arc, Mutiny.

**Package:** `io.casehub.rag.hyde`
**Artifact:** `casehub-rag-hyde`

### CRAG retrofit (rag-crag)

Classpath + config activation to match HyDE:

```properties
casehub.rag.crag.enabled=true    # required — classpath alone no longer activates
```

Both `CorrectiveCaseRetriever` and `ReactiveCorrectiveCaseRetriever` gain `@IfBuildProperty(name = "casehub.rag.crag.enabled", stringValue = "true")` alongside existing `@Decorator @Priority(100)`.

### HybridCaseRetriever changes (rag)

Uses `query.searchText()` for dense and sparse embedding, `query.text()` for reranking:

```java
// Embedding: use searchText (hypothetical doc if expanded)
Embedding denseEmbedding = embeddingModel.embed(TextSegment.from(query.searchText())).content();
Map<Integer, Float> sparseMap = sparseEmbedder.embed(query.searchText());

// Reranking: use original query
List<RankedResult> ranked = reranker.rerank(query.text(), texts);
```

`ReactiveHybridCaseRetriever` — same split in `embedQuery()` and `maybeRerank()`.

### Testing (rag-testing)

`InMemoryQueryExpander` — `@Alternative @Priority(1) @ApplicationScoped`. Deterministic stub: returns `query.withExpansion("hypothetical: " + query.text())`. Records expanded queries for test assertions.

`InMemoryCaseRetriever` / `InMemoryReactiveCaseRetriever` — signature change, uses `query.searchText()` for matching.

All existing tests — mechanical `"query"` → `RetrievalQuery.of("query")` migration.

### Module structure

```
rag-api/                          (new types added)
  + RetrievalQuery
  + QueryExpander
  ~ CaseRetriever                  — String → RetrievalQuery
  ~ ReactiveCaseRetriever          — String → RetrievalQuery

rag-hyde/                          (new module)
  ├── HydeCaseRetriever
  ├── ReactiveHydeCaseRetriever
  ├── LlmQueryExpander
  ├── TemplateQueryExpander
  └── HydeConfig

rag/                               (modified)
  ~ HybridCaseRetriever
  ~ ReactiveHybridCaseRetriever
  ~ BlockingToReactiveCaseRetriever
  ~ RagBeanProducer
  ~ ReactiveRagBeanProducer

rag-crag/                          (modified)
  ~ CorrectiveCaseRetriever        — + @IfBuildProperty
  ~ ReactiveCorrectiveCaseRetriever — + @IfBuildProperty
  ~ CragConfig                     — + enabled property

rag-testing/                       (modified)
  ~ InMemoryCaseRetriever
  ~ InMemoryReactiveCaseRetriever
  + InMemoryQueryExpander
```

### Dependency graph

```
rag-api  ←── rag-hyde  (+ langchain4j-core for ChatModel)
   ↑
   ├──── rag
   ├──── rag-crag
   └──── rag-testing
```

`rag-hyde` depends on `rag-api` and `langchain4j-core`. It does NOT depend on `rag` or `rag-crag`.

## Out of scope

- Multi-query expansion (generating N hypothetical documents and merging results) — future enhancement if single-document HyDE proves insufficient.
- Step-back prompting — different query transformation strategy, would be a separate `QueryExpander` implementation.
- Benchmarking HyDE vs raw retrieval — tracked separately as part of RAG quality measurement.
