# Corrective RAG (CRAG) — Self-Healing Retrieval with Relevance Evaluation

**Issue:** casehubio/neural-text#33
**Date:** 2026-06-18
**Status:** Approved

## Problem

Standard RAG blindly trusts retrieval results. When Qdrant returns irrelevant chunks — vocabulary mismatch, stale corpus content, ambiguous queries — those chunks reach the LLM as context and degrade its output. In regulated domains (AML, clinical), irrelevant context injected into prompts can cause entity confusion, misleading safety assessments, or incorrect compliance determinations. The current pipeline has no mechanism to detect or correct poor retrieval quality.

The platform's `@DefaultBean` → no-op pattern already masks absent backends. CRAG addresses a different failure: a *present* backend returning *bad results* that silently propagate.

## Solution

A post-retrieval quality gate that evaluates each chunk's relevance, filters irrelevant results, optionally expands the search when too few good results survive, and surfaces quality metadata to consumers.

Three components:

1. **`RelevanceEvaluator` SPI** (rag-api) — judges individual (query, chunk) pairs as Correct/Ambiguous/Incorrect
2. **`CorrectiveCaseRetriever` decorator** (rag-crag) — wraps any `CaseRetriever`, applies evaluation, filters, and expands
3. **`CrossEncoderRelevanceEvaluator` default** (rag-crag) — threshold-based grading using the cross-encoder model already deployed for reranking

## Architecture

### Module layout

| Module | Contains | Tier |
|--------|----------|------|
| `rag-api` | `RelevanceEvaluator` SPI, `RelevanceGrade`, `RetrievalResult`, `RetrievalQuality`, enriched `RetrievedChunk` | 1 (pure Java) |
| `rag-crag` | `CorrectiveCaseRetriever`, `ReactiveCorrectiveCaseRetriever`, `CrossEncoderRelevanceEvaluator`, `CragBeanProducer`, `CragConfig` | 3 (CDI, library) |
| `rag-testing` | `InMemoryRelevanceEvaluator` stub | 1 |
| `rag` | Updated return types on `HybridCaseRetriever`, `ReactiveHybridCaseRetriever`, `BlockingToReactiveCaseRetriever` | 3 |

### Activation

Classpath presence — add `casehub-rag-crag` as a compile dependency. `CorrectiveCaseRetriever` is `@Alternative @Priority(1)`, displacing `HybridCaseRetriever` as the `CaseRetriever` bean. Remove the dependency → zero cost, no CRAG code loaded.

### Dependencies

```
rag-crag → rag-api (compile)
rag-crag → inference-tasks (compile, for CrossEncoderReranker)
rag-crag → jakarta.enterprise.cdi-api (provided)
rag-crag → inference-inmem (test)
rag-crag → rag-testing (test)
```

No Quarkus runtime dependency. No JPA. No `quarkus:build` goal. Jandex indexed for CDI discovery.

## API Types (rag-api)

### RelevanceGrade

```java
public enum RelevanceGrade {
    CORRECT,    // chunk is relevant to the query
    AMBIGUOUS,  // uncertain — may or may not be relevant
    INCORRECT,  // chunk is not relevant to the query
    UNGRADED    // no evaluation was performed
}
```

### RetrievedChunk (enriched)

```java
public record RetrievedChunk(String content, String sourceDocumentId,
                             double relevanceScore, Map<String, String> metadata,
                             RelevanceGrade grade) {

    public RetrievedChunk(String content, String sourceDocumentId,
                          double relevanceScore, Map<String, String> metadata) {
        this(content, sourceDocumentId, relevanceScore, metadata, RelevanceGrade.UNGRADED);
    }

    public RetrievedChunk withGrade(RelevanceGrade grade) {
        return new RetrievedChunk(content, sourceDocumentId, relevanceScore, metadata, grade);
    }
}
```

### RetrievalResult + RetrievalQuality

```java
public record RetrievalResult(List<RetrievedChunk> chunks, RetrievalQuality quality) {
    public static RetrievalResult ungraded(List<RetrievedChunk> chunks) {
        return new RetrievalResult(chunks, RetrievalQuality.UNGRADED);
    }
}

public record RetrievalQuality(
    int totalRetrieved,
    int totalCorrect,
    int totalAmbiguous,
    int totalIncorrect,
    boolean correctionApplied,
    boolean expandedSearch
) {
    public static final RetrievalQuality UNGRADED =
        new RetrievalQuality(0, 0, 0, 0, false, false);
}
```

### CaseRetriever (changed return type)

```java
public interface CaseRetriever {
    RetrievalResult retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter);

    default RetrievalResult retrieve(String query, CorpusRef corpus, int maxResults) {
        return retrieve(query, corpus, maxResults, null);
    }
}
```

Mirrored on `ReactiveCaseRetriever` with `Uni<RetrievalResult>`.

### RelevanceEvaluator SPI

```java
public interface RelevanceEvaluator {
    RelevanceGrade evaluate(String query, String chunkContent);

    default List<RelevanceGrade> evaluateBatch(String query, List<String> chunkContents) {
        List<RelevanceGrade> grades = new ArrayList<>(chunkContents.size());
        for (String content : chunkContents) {
            grades.add(evaluate(query, content));
        }
        return List.copyOf(grades);
    }
}
```

Pure Java, Tier 1. No inference dependency — implementations bring their own.

## rag-crag Module

### CrossEncoderRelevanceEvaluator

Default `RelevanceEvaluator` implementation. Reuses the cross-encoder model already deployed for reranking — no new model required. Scores each (query, chunk) pair and maps to `RelevanceGrade` via two configurable thresholds:

- Score ≥ `correctThreshold` → CORRECT
- Score ≤ `incorrectThreshold` → INCORRECT
- Between → AMBIGUOUS

Batch evaluation uses `CrossEncoderReranker.rerank()` for efficient batched inference, then thresholds each score.

### CorrectiveCaseRetriever

Decorator wrapping any `CaseRetriever`. Pipeline:

1. **Initial retrieval** — `delegate.retrieve(query, corpus, maxResults, filter)`
2. **Evaluate** — `evaluator.evaluateBatch(query, chunkContents)` grades each chunk
3. **Grade** — stamp each `RetrievedChunk` with its grade via `withGrade()`
4. **Filter** — keep CORRECT + AMBIGUOUS, discard INCORRECT
5. **Expand** — if surviving chunks < maxResults, re-retrieve with `maxResults * expansionMultiplier`. Re-evaluate only new chunks not already seen (exact match on `sourceDocumentId` + chunk content hash). Merge into the surviving set.
6. **Return** — `RetrievalResult` with graded chunks + `RetrievalQuality` metadata

`ReactiveCorrectiveCaseRetriever` mirrors the same logic with `Uni<>` chains, running evaluation on the worker pool.

### CDI Wiring

`CragBeanProducer` (`@ApplicationScoped`):

- Produces `CrossEncoderRelevanceEvaluator` from injected `CrossEncoderReranker` + `CragConfig` thresholds
- Produces `CorrectiveCaseRetriever` (`@Alternative @Priority(1)`) wrapping the injected `CaseRetriever` delegate
- Reactive counterpart produced conditionally via `@IfBuildProperty(name = "casehub.rag.reactive.enabled", stringValue = "true")`

### Configuration

```properties
casehub.rag.crag.correct-threshold=0.7
casehub.rag.crag.incorrect-threshold=0.3
casehub.rag.crag.expansion-multiplier=3
```

## Changes to Existing Modules

### rag module

- `HybridCaseRetriever.retrieve()` → returns `RetrievalResult.ungraded(chunks)`
- `ReactiveHybridCaseRetriever.retrieve()` → returns `Uni.createFrom().item(RetrievalResult.ungraded(chunks))`
- `BlockingToReactiveCaseRetriever` → signature update, still delegates

### rag-testing module

- `InMemoryCaseRetriever.retrieve()` → returns `RetrievalResult.ungraded(results)`
- `InMemoryReactiveCaseRetriever` → same
- New `InMemoryRelevanceEvaluator` — `@Alternative @Priority(1) @ApplicationScoped`, configurable fixed grade. `InMemoryRelevanceEvaluator.returning(RelevanceGrade.INCORRECT)` for testing CRAG filtering behavior.

### Consumer migration (cross-repo)

`retriever.retrieve(q, c, n, f)` → `retriever.retrieve(q, c, n, f).chunks()` at every call site. Mechanical. Filed as GitHub issues on casehub-engine and Hortora — not committed from this session.

## Testing Strategy

### Unit tests in rag-crag

`CrossEncoderRelevanceEvaluatorTest`:
- Score above correctThreshold → CORRECT
- Score below incorrectThreshold → INCORRECT
- Score between → AMBIGUOUS
- Batch matches individual evaluation
- Backed by `InMemoryInferenceModel`

`CorrectiveCaseRetrieverTest`:
- All CORRECT → all chunks returned, `correctionApplied=true`, `expandedSearch=false`
- All INCORRECT → all filtered, expansion triggered
- Mixed grades → INCORRECT filtered, CORRECT + AMBIGUOUS kept
- Expansion triggered when surviving < maxResults
- Deduplication on expansion
- Grades populated on returned chunks
- `RetrievalQuality` counts match
- Backed by `InMemoryCaseRetriever` + `InMemoryRelevanceEvaluator`

### Unit tests in rag (return type migration)

`HybridCaseRetrieverTest`, `BlockingToReactiveCaseRetrieverTest`, `InMemoryCaseRetrieverTest` updated to assert `RetrievalResult` with `RetrievalQuality.UNGRADED`.

### Integration test in example-rag-pipeline

`RagPipelineIT` updated for `RetrievalResult` return type. New `CragPipelineIT` under the `examples` profile — ingests documents, retrieves with CRAG active, verifies filtering and quality metadata. Smoke profile uses `InMemoryRelevanceEvaluator`.

## Fallback Strategies

Two strategies, both configuration-driven:

1. **Filter** (always active) — remove INCORRECT chunks, keep CORRECT + AMBIGUOUS
2. **Top-K expansion** (triggered when surviving < maxResults) — re-retrieve with `maxResults × expansionMultiplier`, evaluate new chunks, merge and deduplicate

Not in scope: query expansion (HyDE, #32), corpus broadening, dense-only/sparse-only retry.

## Not in Scope

- Specific ONNX evaluator model — infrastructure only; model is deployment config
- Query expansion / HyDE — tracked as #32, separate concern
- Corpus broadening / cross-corpus search — requires corpus registry that doesn't exist
- PLATFORM.md capability ownership update — done at work-end
- Dedicated three-way classification model — upgrade path via the SPI
