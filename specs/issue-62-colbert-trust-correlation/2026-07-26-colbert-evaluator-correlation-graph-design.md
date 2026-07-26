# ColBERT Relevance Evaluator + Correlation Graph Design

**Issues:** #62, #167
**Date:** 2026-07-26
**Status:** Draft

---

## 1. ColBERT Relevance Evaluator (#62)

### Problem

`CorrectiveCaseRetriever` (CRAG decorator) uses `RelevanceEvaluator` to grade
retrieved chunks. The only production implementation is
`CrossEncoderRelevanceEvaluator`, which runs ONNX inference on (query, content)
pairs. Post-BGE-M3 migration, cross-encoder models are removed — CRAG has no
evaluator and fails at startup.

ColBERT MAX_SIM scores are already computed during retrieval (Qdrant outer
query in `HybridCaseRetriever`) and live on `RetrievedChunk.relevanceScore`.
These scores are a strong relevance signal — but the `RelevanceEvaluator`
interface strips them, passing only text to the evaluator.

The `instanceof CrossEncoderRelevanceEvaluator` check in
`CorrectiveCaseRetriever` is a polymorphism violation that would compound if
a second `instanceof` were added for ColBERT.

### Design

#### 1.1 Widen `RelevanceEvaluator` interface

Add a chunk-aware method that gives evaluators access to scores, metadata,
and existing grades — not just text content.

```java
// rag-api: RelevanceEvaluator.java
public interface RelevanceEvaluator {

    RelevanceGrade evaluate(String query, String chunkContent);

    default List<RelevanceGrade> evaluateBatch(String query,
                                                List<String> chunkContents) {
        // unchanged — delegates to evaluate()
    }

    default List<ScoredGrade> evaluateChunks(String query,
                                              List<RetrievedChunk> chunks) {
        List<RelevanceGrade> grades = evaluateBatch(query,
            chunks.stream().map(RetrievedChunk::content).toList());
        return IntStream.range(0, grades.size())
            .mapToObj(i -> new ScoredGrade(grades.get(i), Float.NaN))
            .toList();
    }
}
```

Default implementation delegates to text-based evaluation and returns NaN
scores (no reranking signal). Existing evaluators work unchanged.

#### 1.2 Move `ScoredGrade` to `rag-api`

`ScoredGrade(RelevanceGrade grade, float score)` is currently in
`rag-crossencoder` (`io.casehub.neocortex.rag.crossencoder`). It is a
general value type — grade plus numeric score — not cross-encoder-specific.

Move to `io.casehub.neocortex.rag` in `rag-api`. Update imports in
`rag-crossencoder`.

#### 1.3 `ColBertRelevanceEvaluator`

New class in `rag-crossencoder` module,
`io.casehub.neocortex.rag.crossencoder.corrective` package (alongside
`CrossEncoderRelevanceEvaluator` and `CorrectiveCaseRetriever`).

```java
public final class ColBertRelevanceEvaluator implements RelevanceEvaluator {

    private final double correctThreshold;
    private final double incorrectThreshold;

    // Thresholds validated: incorrectThreshold <= correctThreshold

    @Override
    public List<ScoredGrade> evaluateChunks(String query,
                                             List<RetrievedChunk> chunks) {
        return chunks.stream()
            .map(c -> new ScoredGrade(
                gradeFromScore(c.relevanceScore()),
                (float) c.relevanceScore()))
            .toList();
    }

    @Override
    public RelevanceGrade evaluate(String query, String chunkContent) {
        throw new UnsupportedOperationException(
            "ColBERT evaluation requires chunk scores — "
            + "use evaluateChunks()");
    }

    private RelevanceGrade gradeFromScore(double score) {
        if (score >= correctThreshold)   return RelevanceGrade.CORRECT;
        if (score <= incorrectThreshold) return RelevanceGrade.INCORRECT;
        return RelevanceGrade.AMBIGUOUS;
    }
}
```

Zero inference calls. Reads `relevanceScore` directly from chunks —
which IS the ColBERT MAX_SIM score when ColBERT reranking is active
in `HybridCaseRetriever`.

#### 1.4 Refactor `CrossEncoderRelevanceEvaluator`

Override `evaluateChunks()` with the current `evaluateBatchWithScores()`
logic. The old `evaluateBatchWithScores()` method becomes an internal
detail or is removed — `evaluateChunks()` is the polymorphic entry point.

```java
@Override
public List<ScoredGrade> evaluateChunks(String query,
                                         List<RetrievedChunk> chunks) {
    if (chunks.isEmpty()) return List.of();
    List<String> contents = chunks.stream()
        .map(RetrievedChunk::content).toList();
    List<RankedResult> ranked = reranker.rerank(query, contents);
    ScoredGrade[] results = new ScoredGrade[contents.size()];
    for (RankedResult r : ranked) {
        results[r.originalIndex()] = new ScoredGrade(
            gradeFromScore(r.score()), r.score());
    }
    return List.of(results);
}
```

#### 1.5 Refactor `CorrectiveCaseRetriever`

Eliminate the `instanceof CrossEncoderRelevanceEvaluator` check. Always
call `evaluateChunks()`:

```java
var scored = evaluator.evaluateChunks(query.text(), chunks);
grades = scored.stream().map(ScoredGrade::grade).toList();

List<RetrievedChunk> gradedInput = chunks;
if (hasUsableScores(scored)) {
    float[] scores = extractScores(scored);
    gradedInput = RerankingLogic.attachScores(chunks, scores);
}
```

`hasUsableScores()` checks for non-NaN scores (text-based evaluators
return NaN via the default implementation).

Same refactor applies to the expansion path (second evaluation pass).

#### 1.6 CDI wiring

`CrossEncoderBeanProducer` currently throws when no `CrossEncoderReranker`
is available — a hard startup failure in post-BGE-M3 deployments. A
separate `@DefaultBean` producer would never activate because the
existing producer fails first.

Fix: single producer with fallback logic inside:

```java
@ApplicationScoped
public class CrossEncoderBeanProducer {

    @Inject CragConfig config;
    @Inject Instance<CrossEncoderReranker> rerankerInstance;

    @Produces
    @ApplicationScoped
    RelevanceEvaluator evaluator() {
        if (rerankerInstance.isResolvable()) {
            return new CrossEncoderRelevanceEvaluator(
                rerankerInstance.get(),
                config.correctThreshold(),
                config.incorrectThreshold());
        }
        return new ColBertRelevanceEvaluator(
            config.correctThreshold(),
            config.incorrectThreshold());
    }
}
```

No new producer class. No CDI priority complexity. One producer, two
code paths based on what's available at runtime.

**Activation matrix:**

| Cross-encoder available | Evaluator used |
|------------------------|----------------|
| Yes | `CrossEncoderRelevanceEvaluator` |
| No | `ColBertRelevanceEvaluator` |

Same threshold config keys for both evaluators. ColBERT MAX_SIM scores
typically range 0.3–0.8 vs cross-encoder 0.0–1.0 — deployments
switching evaluators must recalibrate thresholds.

#### 1.7 Threshold configuration

Reuse `CragConfig.correctThreshold()` and `CragConfig.incorrectThreshold()`.
Same config keys, same semantics — the interpretation (MAX_SIM range vs
cross-encoder range) depends on which evaluator is active. Default values
may need adjusting for MAX_SIM (typically 0.3–0.8 range vs cross-encoder
0.0–1.0).

Document the range difference in config comments.

---

## 2. Query-Document-Outcome Correlation Graph (#167)

### Problem

`RetrievalAnalyzer` provides document-level stats (`documentStats`) and
query-level quality signals (`lowRelevanceQueries`, `zeroHitQueries`,
`queryFrequency`). These are independent views. There is no structure that
joins queries ↔ documents ↔ outcomes to answer:

- Which specific documents make a query perform poorly?
- Which queries retrieve the same document set (and should be deduplicated)?
- Which documents are central to many queries (high impact if removed/degraded)?

### Design

#### 2.1 Value types (all in `rag-api`)

```java
// The bipartite graph: queries on one side, documents on the other
public record CorrelationGraph(
    Map<String, QueryNode> queries,
    Map<String, DocumentNode> documents
) { /* defensive copies, non-null validation */ }

// Query-side node
public record QueryNode(
    String queryText,
    int retrievalCount,
    Map<String, EdgeStats> documentEdges   // documentId → stats
) { /* validation */ }

// Document-side node
public record DocumentNode(
    String documentId,
    int retrievalCount,
    Map<String, EdgeStats> queryEdges      // queryText → stats
) { /* validation */ }

// Edge between a query and a document
public record EdgeStats(
    int coOccurrenceCount,
    double averageScore,
    Map<RetrievalOutcome, Integer> outcomeDistribution
) { /* validation, defensive copy on outcomeDistribution */ }
```

#### 2.2 Analysis result types

```java
// Queries that retrieve overlapping document sets
public record QueryCluster(
    Set<String> queryTexts,
    double jaccardSimilarity,
    Set<String> sharedDocumentIds
) { /* validation: queryTexts.size() >= 2, similarity in [0,1] */ }

// Document centrality and outcome quality
public record DocumentImpact(
    String documentId,
    int distinctQueryCount,
    int totalRetrievals,
    double averageScore,
    Map<RetrievalOutcome, Integer> aggregateOutcomes
) { /* validation */ }
```

#### 2.3 Builder and analysis methods on `RetrievalAnalyzer`

```java
// Build the graph by joining records with feedback
public static CorrelationGraph correlationGraph(
    RetrievalTracker tracker, CorpusRef corpus,
    Instant since, Instant until);

// Group queries by shared document sets (Jaccard similarity)
public static List<QueryCluster> queryClusters(
    CorrelationGraph graph, double minJaccardSimilarity);

// Rank documents by centrality and outcome quality
public static List<DocumentImpact> documentImpact(
    CorrelationGraph graph);
```

#### 2.4 `correlationGraph()` algorithm

1. Fetch all `RetrievalRecord` for the corpus and time window
2. Fetch all `RetrievalFeedback` for the same window
3. Index feedback by `(retrievalId, sourceDocumentId)` → outcome
4. For each record: for each document in the record's results:
   - Increment the query→document edge count
   - Accumulate the document's relevance score
   - Look up feedback (if any) and accumulate outcome distribution
5. Build dual-indexed `QueryNode` and `DocumentNode` maps

Pure computation. O(R*D + F) where R = records, D = avg documents per
record, F = feedback entries.

#### 2.5 `queryClusters()` algorithm

For each pair of queries in the graph:
1. Compute Jaccard similarity: |docsA ∩ docsB| / |docsA ∪ docsB|
2. If similarity >= threshold, merge into a cluster

O(Q²) where Q = distinct queries. For large Q, could optimise with
MinHash — but for the expected corpus sizes (hundreds to low thousands
of distinct queries), brute-force Jaccard is fine.

Return clusters sorted by similarity (highest first).

#### 2.6 `documentImpact()` algorithm

For each document node in the graph:
1. Count distinct queries that retrieve it (`queryEdges.size()`)
2. Sum total retrievals across all queries
3. Compute average score across all edges
4. Aggregate outcome distributions across all edges

Return sorted by `distinctQueryCount` descending (most central first).

---

## 3. Module Impact

| Module | Changes |
|--------|---------|
| `rag-api` | `ScoredGrade` moved here; `evaluateChunks()` added to `RelevanceEvaluator`; new value types: `CorrelationGraph`, `QueryNode`, `DocumentNode`, `EdgeStats`, `QueryCluster`, `DocumentImpact`; new methods on `RetrievalAnalyzer` |
| `rag-crossencoder` | `ColBertRelevanceEvaluator` + `ColBertEvaluatorProducer` (new); `CrossEncoderRelevanceEvaluator` refactored to override `evaluateChunks()`; `CorrectiveCaseRetriever` refactored to eliminate `instanceof`; `ScoredGrade` import updated |
| `rag-testing` | `InMemoryRelevanceEvaluator` unchanged (default `evaluateChunks()` delegates to `evaluateBatch()`) |

No new modules. No new dependencies.

---

## 4. Testing Strategy

### #62 tests

- `ColBertRelevanceEvaluatorTest`: threshold mapping (CORRECT/AMBIGUOUS/INCORRECT boundaries), edge cases (exact threshold, zero, negative scores)
- `CrossEncoderRelevanceEvaluatorTest`: verify `evaluateChunks()` produces same results as old `evaluateBatchWithScores()`
- `CorrectiveCaseRetrieverTest`: existing tests pass with refactored code; new test verifying ColBERT evaluator integration (score-based grading flows through CRAG expansion correctly)
- `RelevanceEvaluatorTest`: default `evaluateChunks()` delegates to `evaluateBatch()` correctly, returns NaN scores

### #167 tests

- `CorrelationGraphTest`: builder produces correct graph from known records + feedback; empty inputs; single query; single document
- `QueryClusterTest`: known overlapping queries cluster; disjoint queries don't cluster; threshold boundary
- `DocumentImpactTest`: centrality ranking; outcome aggregation; single-query documents
- `RetrievalAnalyzerCorrelationTest`: integration — end-to-end from `InMemoryRetrievalTracker` data through graph building to analysis results

---

## 5. Out of Scope

- ColBERT MAX_SIM threshold auto-calibration (manual config for now)
- Graph persistence (computed on demand from tracker data)
- Reactive variants of correlation analysis (blocking-only, consistent with `RetrievalAnalyzer`)
- MinHash optimisation for query clustering (brute-force Jaccard sufficient at expected scale)
- Visualization / rendering of the correlation graph
