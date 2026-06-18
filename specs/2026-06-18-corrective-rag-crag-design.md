# Corrective RAG (CRAG) — Self-Healing Retrieval with Relevance Evaluation

**Issue:** casehubio/neural-text#33
**Date:** 2026-06-18
**Status:** Approved (rev 2 — post code review)

## Problem

Standard RAG blindly trusts retrieval results. When Qdrant returns irrelevant chunks — vocabulary mismatch, stale corpus content, ambiguous queries — those chunks reach the LLM as context and degrade its output. In regulated domains (AML, clinical), irrelevant context injected into prompts can cause entity confusion, misleading safety assessments, or incorrect compliance determinations. The current pipeline has no mechanism to detect or correct poor retrieval quality.

The platform's `@DefaultBean` → no-op pattern already masks absent backends. CRAG addresses a different failure: a *present* backend returning *bad results* that silently propagate.

## Solution

A post-retrieval quality gate that evaluates each chunk's relevance, filters irrelevant results, optionally expands the search when too few good results survive, and surfaces quality metadata to consumers.

Three components:

1. **`RelevanceEvaluator` SPI** (rag-api) — judges individual (query, chunk) pairs as Correct/Ambiguous/Incorrect
2. **`CorrectiveCaseRetriever` CDI decorator** (rag-crag) — intercepts any `CaseRetriever`, applies evaluation, filters, and expands
3. **`CrossEncoderRelevanceEvaluator` default** (rag-crag) — threshold-based grading using the cross-encoder model already deployed for reranking

## Architecture

### Module layout

| Module | Contains | Tier | Hortora? |
|--------|----------|------|----------|
| `rag-api` | `RelevanceEvaluator` SPI, `RelevanceGrade`, enriched `RetrievedChunk` | 1 (pure Java) | ✅ yes |
| `rag-crag` | `CorrectiveCaseRetriever` (`@Decorator`), `ReactiveCorrectiveCaseRetriever` (`@Decorator`), `CrossEncoderRelevanceEvaluator`, `CragBeanProducer`, `CragConfig` | CDI library | ✅ yes |
| `rag-testing` | `InMemoryRelevanceEvaluator` stub | 1 | ✅ yes |
| `rag` | Updated return types on `HybridCaseRetriever`, `ReactiveHybridCaseRetriever`, `BlockingToReactiveCaseRetriever` — no structural change | 3 | ✅ yes |

### Activation

Classpath presence — add `casehub-rag-crag` as a compile dependency. `CorrectiveCaseRetriever` is a CDI `@Decorator` — it intercepts the active `CaseRetriever` bean (whatever it is). Remove the dependency → zero cost, no CRAG code loaded.

### CDI wiring — @Decorator, not @Alternative

CRAG uses the CDI `@Decorator` pattern, not `@Alternative`. This solves three problems:

1. **No circular dependency** — `@Delegate @Any @Inject CaseRetriever delegate` is CDI-managed; resolves to the underlying bean without self-injection
2. **No priority collision** — decorators don't compete with alternatives in bean resolution. `InMemoryCaseRetriever` (`@Alternative @Priority(1)` in rag-testing) and the CRAG decorator coexist: in `@QuarkusTest`, the decorator wraps the in-memory stub; in production, it wraps `HybridCaseRetriever`
3. **Classpath activation** — the decorator only exists when `rag-crag` is on the classpath

### Framework dependency split

The blocking `@Decorator` uses only CDI annotations (`jakarta.decorator.Decorator`, `jakarta.decorator.Delegate`) — no Quarkus-specific dependency. The reactive `@Decorator` uses `@IfBuildProperty(name = "casehub.rag.reactive.enabled", stringValue = "true")` which is Quarkus-specific. This matches the existing codebase pattern — blocking path is framework-independent, reactive path requires Quarkus Arc.

### Dependencies

```
rag-crag → rag-api (compile)
rag-crag → inference-tasks (compile, for CrossEncoderReranker)
rag-crag → jakarta.enterprise.cdi-api (provided)
rag-crag → jakarta.decorator-api (provided)
rag-crag → inference-inmem (test)
rag-crag → rag-testing (test)
```

No `quarkus:build` goal. Jandex indexed for CDI discovery.

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

The canonical constructor is 5-arg. Existing 4-arg call sites compile via the convenience constructor and default to `UNGRADED`. The compact constructor validation (null checks, `Map.copyOf()`) moves to the 5-arg canonical constructor.

### CaseRetriever (unchanged return type)

```java
public interface CaseRetriever {
    List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults, PayloadFilter filter);

    default List<RetrievedChunk> retrieve(String query, CorpusRef corpus, int maxResults) {
        return retrieve(query, corpus, maxResults, null);
    }
}
```

**Return type stays `List<RetrievedChunk>`.** Per-chunk grades travel on `RetrievedChunk` itself. Aggregate quality metadata (`RetrievalQuality`) is delivered as a CDI event, not on the return value. This avoids coupling the prompt compiler to retrieval telemetry and eliminates the cross-repo migration that a `RetrievalResult` wrapper would require.

Mirrored on `ReactiveCaseRetriever` — `Uni<List<RetrievedChunk>>`, unchanged.

### RetrievalQuality (CDI event, not return type)

```java
public record RetrievalQuality(
    int totalRetrieved,
    int totalCorrect,
    int totalAmbiguous,
    int totalIncorrect,
    boolean evaluated,
    boolean expandedSearch
) {
    public static final RetrievalQuality NONE =
        new RetrievalQuality(0, 0, 0, 0, false, false);
}
```

`evaluated=true` means CRAG was active and grading happened. `evaluated=false` means no evaluation (non-CRAG path). Lives in `rag-api` (pure Java record — CDI event infrastructure is provided by the container, not the event type). The decorator fires `Event<RetrievalQuality>.fire(quality)` after each retrieval.

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

Pure Java, Tier 1. No inference dependency — implementations bring their own. The `evaluateBatch` default is sequential; `CrossEncoderRelevanceEvaluator` overrides with `CrossEncoderReranker.rerank()` for genuinely batched ONNX inference.

## rag-crag Module

### Maven coordinates

| Element | Value |
|---------|-------|
| Folder | `rag-crag/` |
| artifactId | `casehub-rag-crag` |
| Package | `io.casehub.rag.crag` |

### CrossEncoderRelevanceEvaluator

Default `RelevanceEvaluator` implementation. Reuses the cross-encoder model already deployed for reranking — no new model required. Scores each (query, chunk) pair and maps to `RelevanceGrade` via two configurable thresholds:

- Score ≥ `correctThreshold` → CORRECT
- Score ≤ `incorrectThreshold` → INCORRECT
- Between → AMBIGUOUS

Batch evaluation uses `CrossEncoderReranker.rerank()` for efficient batched inference, then thresholds each score.

**Calibration note:** Cross-encoder scores are model-dependent. A model trained for MS MARCO passage ranking produces scores in a different range than one trained for NLI. Default thresholds (0.7/0.3) are starting points — threshold tuning is mandatory per deployed model. Validate against a held-out relevance judgment set. Wrong thresholds silently degrade quality: too lenient passes irrelevant chunks, too strict filters good ones.

### CorrectiveCaseRetriever — CDI @Decorator

```java
@Decorator
@Priority(100)
public class CorrectiveCaseRetriever implements CaseRetriever {

    @Delegate @Any @Inject CaseRetriever delegate;
    @Inject RelevanceEvaluator evaluator;
    @Inject CragConfig config;
    @Inject Event<RetrievalQuality> qualityEvent;

    @Override
    public List<RetrievedChunk> retrieve(String query, CorpusRef corpus,
                                          int maxResults, PayloadFilter filter) {
        // 1. Initial retrieval
        List<RetrievedChunk> chunks = delegate.retrieve(query, corpus, maxResults, filter);

        // 2. Evaluate each chunk
        List<String> contents = chunks.stream().map(RetrievedChunk::content).toList();
        List<RelevanceGrade> grades = evaluator.evaluateBatch(query, contents);

        // 3. Grade each chunk
        List<RetrievedChunk> graded = new ArrayList<>();
        int correct = 0, ambiguous = 0, incorrect = 0;
        for (int i = 0; i < chunks.size(); i++) {
            RelevanceGrade grade = grades.get(i);
            switch (grade) {
                case CORRECT   -> correct++;
                case AMBIGUOUS -> ambiguous++;
                case INCORRECT -> incorrect++;
                default -> {}
            }
            graded.add(chunks.get(i).withGrade(grade));
        }

        // 4. Filter: keep CORRECT + AMBIGUOUS, discard INCORRECT
        List<RetrievedChunk> surviving = graded.stream()
            .filter(c -> c.grade() != RelevanceGrade.INCORRECT)
            .toList();

        // 5. Top-K expansion if too few survive
        boolean expanded = false;
        if (surviving.size() < maxResults) {
            int expandedLimit = maxResults * config.expansionMultiplier();
            List<RetrievedChunk> expandedChunks = delegate.retrieve(
                query, corpus, expandedLimit, filter);
            // Re-evaluate only new chunks (exact content hash match for dedup)
            // Merge into surviving set
            expanded = true;
        }

        // 6. Truncate to maxResults
        List<RetrievedChunk> result = surviving.stream()
            .limit(maxResults)
            .toList();

        // 7. Fire quality event
        qualityEvent.fire(new RetrievalQuality(
            chunks.size(), correct, ambiguous, incorrect, true, expanded));

        return result;
    }
}
```

`ReactiveCorrectiveCaseRetriever` mirrors the same logic with `Uni<>` chains, running evaluation on the worker pool. Gated by `@IfBuildProperty(name = "casehub.rag.reactive.enabled", stringValue = "true")`.

### CragBeanProducer

Produces `RelevanceEvaluator` only — the decorator is CDI-managed via `@Decorator`, not produced by a factory.

```java
@ApplicationScoped
public class CragBeanProducer {

    @Inject CragConfig config;
    @Inject Instance<CrossEncoderReranker> rerankerInstance;

    @Produces @ApplicationScoped
    RelevanceEvaluator evaluator() {
        if (!rerankerInstance.isResolvable()) {
            throw new IllegalStateException(
                "rag-crag requires a CrossEncoderReranker bean. " +
                "Configure casehub.inference.models.<name> and produce a CrossEncoderReranker.");
        }
        return new CrossEncoderRelevanceEvaluator(
            rerankerInstance.get(),
            config.correctThreshold(),
            config.incorrectThreshold());
    }
}
```

### Configuration

```properties
casehub.rag.crag.correct-threshold=0.7    # score above = CORRECT (tune per model)
casehub.rag.crag.incorrect-threshold=0.3  # score below = INCORRECT (tune per model)
casehub.rag.crag.expansion-multiplier=3   # fetch 3x on retry
```

### Expansion strategy — scope and limitations

Top-K expansion helps when relevant content exists at lower ranks in the same corpus. It does **not** help when the corpus lacks relevant content entirely (vocabulary mismatch, stale corpus). These are the dominant failure modes in regulated domains.

Cross-corpus search and query expansion are separate architectural concerns:
- Query expansion → HyDE (#32), a pre-retrieval stage
- Cross-corpus search → requires a corpus registry/discovery mechanism that doesn't exist

Neither belongs inside the CRAG decorator. The decorator's fallback strategies are: filter (always) and expand (when surviving < maxResults). Both are configuration-driven, not pluggable via SPI — the correction logic is simple orchestration; the pluggable parts are the evaluator (how to judge) and the retriever (how to search).

## Changes to Existing Modules

### rag module

No return type change. `HybridCaseRetriever`, `ReactiveHybridCaseRetriever`, `BlockingToReactiveCaseRetriever` unchanged — they already return `List<RetrievedChunk>`. The only change: `RetrievedChunk` gains a 5th field (`grade`), but existing 4-arg construction compiles via the convenience constructor (defaults to `UNGRADED`).

### rag-testing module

`InMemoryCaseRetriever` — existing 4-arg `RetrievedChunk` construction unchanged (convenience constructor defaults to `UNGRADED`).

New: `InMemoryRelevanceEvaluator` — `@Alternative @Priority(1) @ApplicationScoped`, configurable fixed grade:

```java
public class InMemoryRelevanceEvaluator implements RelevanceEvaluator {
    private final RelevanceGrade fixedGrade;

    public InMemoryRelevanceEvaluator() { this.fixedGrade = RelevanceGrade.CORRECT; }
    private InMemoryRelevanceEvaluator(RelevanceGrade grade) { this.fixedGrade = grade; }

    public static InMemoryRelevanceEvaluator returning(RelevanceGrade grade) {
        return new InMemoryRelevanceEvaluator(grade);
    }

    @Override
    public RelevanceGrade evaluate(String query, String chunkContent) {
        return fixedGrade;
    }
}
```

### Consumer migration

**No cross-repo migration required.** `CaseRetriever.retrieve()` still returns `List<RetrievedChunk>`. casehub-engine and Hortora call sites are unchanged. Per-chunk grades are available via `chunk.grade()` if consumers choose to inspect them. `RetrievalQuality` is observable via CDI `@Observes RetrievalQuality` for consumers that want it.

Issue #40 (consumer migration) can be closed or repurposed as "consumer adoption of CRAG quality metadata" rather than a mechanical migration.

## Testing Strategy

### Unit tests in rag-crag (pure Java, no CDI)

`CrossEncoderRelevanceEvaluatorTest`:
- Score above correctThreshold → CORRECT
- Score below incorrectThreshold → INCORRECT
- Score between → AMBIGUOUS
- Batch matches individual evaluation
- Backed by `InMemoryInferenceModel`

`CorrectiveCaseRetrieverTest`:
- All CORRECT → all chunks returned with grades, quality event has `evaluated=true`, `expandedSearch=false`
- All INCORRECT → all filtered, expansion triggered
- Mixed grades → INCORRECT filtered, CORRECT + AMBIGUOUS kept
- Expansion triggered when surviving < maxResults
- Deduplication on expansion (exact content hash match)
- Grades populated on returned chunks
- `RetrievalQuality` event counts match
- Backed by `InMemoryCaseRetriever` + `InMemoryRelevanceEvaluator`

### Unit tests in rag (RetrievedChunk enrichment)

`RetrievedChunkTest` — verify 4-arg convenience constructor defaults to `UNGRADED`, `withGrade()` produces correct copy.

Existing `HybridCaseRetrieverTest`, `BlockingToReactiveCaseRetrieverTest` — verify returned chunks have `grade == UNGRADED`.

### Integration test in example-rag-pipeline

`RagPipelineIT` — existing test, verify returned chunks carry `UNGRADED` (no CRAG on classpath in default profile). New `CragPipelineIT` under `examples` profile — add `casehub-rag-crag` dependency, ingests documents, retrieves with CRAG active, verifies filtering and per-chunk grades. Smoke profile uses `InMemoryRelevanceEvaluator`.

## ARC42STORIES Update Plan

CRAG starts **Journey J4: Retrieval Quality** — the first post-completion extension of the architecture.

### New journey

| Journey | Description | Chapters | Status |
|---------|-------------|----------|--------|
| J4 Retrieval Quality | Self-healing retrieval — evaluate, filter, and correct poor retrieval results | C10 | 🔲 pending |

### New chapter

| # | Chapter | Journey | Layers touched | Delta summary | Status |
|---|---------|---------|----------------|---------------|--------|
| 10 | Corrective RAG (CRAG) | J4 | L6, L7, **new L10** | L6: Low (RelevanceEvaluator SPI, RelevanceGrade, enriched RetrievedChunk), L7: Low (no structural change), L10: High (new module) | 🔲 pending (#33) |

### New layer

| Layer | Module | Tier | Hortora? |
|-------|--------|------|----------|
| L10 CRAG | `rag-crag` | CDI library, classpath-activated | ✅ yes |

### Updated chapter flow

```
C9 → C10["C10: CRAG\n+ L10, L6 (enriched)"]
```

C10 depends on C7 (RAG pipeline must exist) and C4 (CrossEncoderReranker from inference-tasks).

### Accountability gaps closed by C10

| Gap | What breaks without it | Closed by |
|-----|------------------------|-----------|
| Silent bad retrieval | Irrelevant chunks reach LLM prompt, degrade output quality | RelevanceEvaluator grades each chunk; INCORRECT filtered |
| No retrieval quality signal | Consumers (AML, clinical) can't assess confidence in retrieved context | Per-chunk `RelevanceGrade` + `RetrievalQuality` CDI event |
| No corrective action | Poor initial retrieval is final | Top-K expansion re-retrieves when too few good results survive |

## Not in Scope

- Specific ONNX evaluator model — infrastructure only; model is deployment config. Tracked as #39.
- Query expansion / HyDE — tracked as #32, separate pre-retrieval concern
- Corpus broadening / cross-corpus search — requires corpus registry that doesn't exist
- PLATFORM.md capability ownership update — done at work-end
- Dedicated three-way classification model — upgrade path via the SPI (#39)
- FallbackStrategy SPI — correction logic (filter + expand) is simple orchestration; pluggable parts are already pluggable (evaluator, retriever)
