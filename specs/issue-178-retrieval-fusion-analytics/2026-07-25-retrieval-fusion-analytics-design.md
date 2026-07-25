# Retrieval Fusion Weights, Payload Boosting, and Query Analytics

**Issues:** #178, #179, #180
**Date:** 2026-07-25
**Status:** Design

## Context

Cross-module feedback from Hortora/engine#50 (HyDE investigation) across 14 scenarios
shows keyword queries and NL queries have different failure patterns. Three gaps
identified:

1. All fusion legs have equal weight — no way to tune signal balance per corpus
2. Human-assigned quality scores in Qdrant payload are ignored during ranking
3. Retrieval tracking data exists but has no query-level analytical layer

## #178 — Unified Fusion Weights

### Problem

CC fusion uses per-leg weights via `CcWeightsConfig` (dense 0.5, sparse 0.3, bm25 0.2).
RRF fusion ignores `ScoredLeg.weight()` entirely — all legs get uniform `1/(k + rank + 1)`.
Server-side RRF/DBSF (Qdrant native) has no per-leg weight support. Two separate weight
regimes with no config unification.

### Design

Replace `CcWeightsConfig` with unified `FusionWeightsConfig` under
`casehub.rag.retrieval.weights.*`. All fusion strategies consume the same weights.

**Config:**

```properties
casehub.rag.retrieval.weights.dense=1.0    # default
casehub.rag.retrieval.weights.sparse=1.0   # default
casehub.rag.retrieval.weights.bm25=1.0     # default
```

All default to 1.0 (equal weighting). This replaces CC's former 0.5/0.3/0.2 defaults —
pre-release breaking change, acceptable.

**RRF weighted fusion (`ScoreFusion.rrf()`):**

Currently: `scores.merge(id, 1.0 / (k + rank + 1), Double::sum)`

Becomes: `scores.merge(id, leg.weight() * 1.0 / (k + rank + 1), Double::sum)`

Normalization: `maxScore = totalWeight / (k + 1)` where `totalWeight = sum of all leg weights`.
Output remains in [0, 1].

**CC fusion (`ScoreFusion.convexCombination()`):**

Already uses `ScoredLeg.weight()` with auto-normalization. No algorithm change needed.

**Server-side RRF/DBSF:**

Qdrant's native fusion does not support per-leg weights. Server-side fusion continues
to use equal weights. When a user configures non-equal weights and uses RRF/DBSF,
client-side fusion provides the weighted behavior — this is already the case since CC
is explicitly client-side, and RRF can be run client-side too.

No automatic strategy switching. The user selects their fusion strategy explicitly;
weight config is advisory for server-side strategies.

**Config mapping:**

```java
interface FusionWeightsConfig {
    @WithDefault("1.0") double dense();
    @WithDefault("1.0") double sparse();
    @WithDefault("1.0") double bm25();
}
```

Replaces `CcWeightsConfig`. `RetrievalConfig.ccWeights()` becomes
`RetrievalConfig.weights()`.

**HybridCaseRetriever changes:**

`executeConvexCombinationFusion()` — replace `config.retrieval().ccWeights().dense()`
with `config.retrieval().weights().dense()` etc. Direct substitution.

### Files Changed

| File | Change |
|------|--------|
| `rag/RagConfig.java` | Replace `CcWeightsConfig` with `FusionWeightsConfig`, rename accessor |
| `fusion-api/ScoreFusion.java` | `rrf()` uses `ScoredLeg.weight()`, update normalization |
| `fusion-api/ScoreFusionTest.java` | Add weighted RRF tests |
| `rag/HybridCaseRetriever.java` | Update config references from `ccWeights()` to `weights()` |
| `rag/HybridCaseRetrieverTest.java` | Update config stubs |

## #180 — Payload Quality Boost

### Problem

Documents have human-assigned quality scores (1-10) stored as Qdrant payload metadata.
These scores are ignored during ranking. When a score=9 and score=3 document are close
in retrieval score, the higher-quality one should win.

### Analysis: Quality Is an Authority Signal

The quality score is **query-independent** — the document has the same quality regardless
of query. This is fundamentally different from dense/sparse/BM25, which are
**query-dependent** relevance signals. In IR theory: relevance vs authority.

The correct integration mode depends on the fusion strategy's mathematical properties:

| Fusion | Score model | Quality integration | Why |
|--------|------------|-------------------|-----|
| CC | Score-aware (min-max normalized) | Fusion leg | Magnitude preserved in convex combination |
| RRF | Rank-based (1/k+rank) | Post-fusion rescore | Rank conversion loses magnitude — quality 9→10 same delta as 1→2 |
| DBSF | Score-aware, server-side | Post-fusion rescore | Can't inject non-vector legs server-side |

The integration mode is **derived from the fusion strategy**, not independently configured.
No separate `BoostMode` enum needed.

### Design

**Config:**

```properties
casehub.rag.retrieval.weights.dense=1.0          # default
casehub.rag.retrieval.weights.sparse=1.0         # default
casehub.rag.retrieval.weights.bm25=1.0           # default
casehub.rag.retrieval.weights.quality=0.0        # default: disabled
casehub.rag.retrieval.weights.quality-field=      # payload field name (required when quality > 0)
```

`quality > 0` activates boosting. No separate `enabled` flag — the weight IS the toggle.
`quality-field` names the Qdrant payload field containing the numeric score (e.g. "score").
Startup validation: if `quality > 0` and `quality-field` is empty, fail fast.

```java
interface FusionWeightsConfig {
    @WithDefault("1.0") double dense();
    @WithDefault("1.0") double sparse();
    @WithDefault("1.0") double bm25();
    @WithDefault("0.0") double quality();
    Optional<String> qualityField();
}
```

**CC path (fusion leg):**

When `quality > 0` and strategy is CC, `executeConvexCombinationFusion()` constructs
a quality leg from payload values of documents retrieved by the retrieval legs:

1. Collect all unique documents from dense/sparse/BM25 legs
2. Extract numeric payload value from `qualityField` for each document
3. Build `ScoredLeg<RetrievedChunk>` with quality scores and `weights.quality()` weight
4. Include in `ScoreFusion.convexCombination()` alongside retrieval legs

Quality participates in CC's min-max normalization and weighted summation — magnitude
preserved, naturally competes with retrieval signals.

**RRF/DBSF path (decorator rescore):**

`PayloadBoostCaseRetriever` — `@Decorator @Priority(85)` on `CaseRetriever`.
Positioned between fusion and cross-encoder reranking in the decorator chain:

```
CaseRetriever (HybridCaseRetriever, priority 0)
  → PayloadBoostCaseRetriever (@Priority 85)    ← NEW
  → CrossEncoderRerankingRetriever (@Priority 75)
  → TrackingCaseRetriever (@Priority 50)
```

Decorator logic:
1. Delegate to inner `CaseRetriever.retrieve()`
2. If strategy is CC → no-op (quality already integrated via fusion leg)
3. Read `metadata.get(boostField)` from each `RetrievedChunk`, parse to double
4. Apply: `boostedScore = score * (1 + normalizedQuality * qualityWeight)`
   where `normalizedQuality = payloadValue / maxPayloadValue` across the result set
5. Re-sort by boosted score, return

Classpath + config activated: `casehub.rag.retrieval.weights.quality > 0`.

**Numeric payload extraction:**

`HybridCaseRetriever.mapToChunks()` currently only extracts string payload values.
Extend to also extract numeric values (double) into metadata as string representations.
This enables the decorator to read quality scores from `RetrievedChunk.metadata()`.

### Files Changed

| File | Change |
|------|--------|
| `rag/RagConfig.java` | Add `quality` + `qualityField` to `FusionWeightsConfig` |
| `rag/HybridCaseRetriever.java` | CC path: construct quality leg. `mapToChunks()`: extract numeric payload. |
| `rag/PayloadBoostCaseRetriever.java` | **New.** Decorator for RRF/DBSF rescore path. |
| `rag/HybridCaseRetrieverTest.java` | Quality leg tests for CC path |
| `rag/PayloadBoostCaseRetrieverTest.java` | **New.** Decorator unit tests |

## #179 — RetrievalAnalyzer Query-Level Analytics

### Problem

`RetrievalAnalyzer` in `rag-api` provides document-centric analytics (documentStats,
unretrievedDocuments, qualitySignals). No query-level analysis exists — engine's
`gardenUnretrieved` MCP tool does crude inline frequency counting (~60 lines).

### Design

Extend the existing static utility with three query-level methods. Keep static — pure
computation over passed-in data, no CDI, stays in `rag-api` (tier 1).

**New methods:**

```java
public static List<QueryQualitySignal> lowRelevanceQueries(
    RetrievalTracker tracker, CorpusRef corpus,
    Instant since, Instant until, double scoreThreshold)
```

Queries where average result relevance score < `scoreThreshold`. Identifies retrieval
gaps — queries the system handles poorly.

```java
public static List<QueryQualitySignal> zeroHitQueries(
    RetrievalTracker tracker, CorpusRef corpus,
    Instant since, Instant until)
```

Queries that returned zero results. Identifies corpus coverage gaps.

```java
public static Map<String, QueryFrequencyStats> queryFrequency(
    RetrievalTracker tracker, CorpusRef corpus,
    Instant since, Instant until)
```

Query text → frequency + quality metrics. Sorted by descending count. Identifies hot
topics and their retrieval quality.

**New value types in `rag-api`:**

```java
public record QueryQualitySignal(
    String queryText,
    double averageRelevanceScore,
    int retrievalCount,
    Instant lastSeen) {}
```

```java
public record QueryFrequencyStats(
    int count,
    double averageScore,
    Instant firstSeen,
    Instant lastSeen) {}
```

**Implementation approach:**

All three methods iterate `tracker.findRecords(corpus, since, until)`. Each
`RetrievalRecord` contains the `RetrievalQuery` (with `.text()`) and the list of
`RetrievedDocumentRef` (with `.relevanceScore()`).

- `lowRelevanceQueries`: group by query text, compute average score across all
  retrievals of that query, filter by threshold
- `zeroHitQueries`: filter records where `documents` list is empty
- `queryFrequency`: group by query text, count occurrences, compute avg score,
  track first/last timestamp

### Files Changed

| File | Change |
|------|--------|
| `rag-api/RetrievalAnalyzer.java` | Add three query-level methods |
| `rag-api/QueryQualitySignal.java` | **New.** Value type |
| `rag-api/QueryFrequencyStats.java` | **New.** Value type |
| `rag-api/RetrievalAnalyzerQueryTest.java` | **New.** Tests for query-level methods |

## Module Impact

All changes are within existing modules:

- `fusion-api` — weighted RRF algorithm change
- `rag-api` — new value types, extended RetrievalAnalyzer
- `rag` — config changes, HybridCaseRetriever updates, new decorator

No new modules. No new dependencies. No Flyway migrations.

## Test Strategy

| Area | Tests |
|------|-------|
| Weighted RRF | Weight=1.0 matches current behavior, non-equal weights shift rankings, weight=0 excludes leg, normalization stays [0,1] |
| CC quality leg | Quality weight=0 no change, quality>0 shifts rankings, missing payload values handled gracefully |
| Payload boost decorator | RRF strategy applies boost, CC strategy is no-op, missing field no-op, non-numeric field no-op, disabled config no-op |
| Query analytics | Low-relevance filtering, zero-hit detection, frequency counting, empty tracker returns empty, edge cases (single record, all zero-hit) |
