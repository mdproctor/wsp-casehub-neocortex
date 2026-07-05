# Batch Design: Inference Flexibility, Fusion Strategy, Embedding Adapter, CBR Similarity

**Issues:** #104, #51, #52, #61, #82, #87
**Date:** 2026-07-05
**Branch:** `issue-104-batch-fusion-inference-cbr`

---

## 1. Inference Flexibility (#51 + #52)

### 1.1 Input Name Aliases (#51)

**Problem:** `OnnxInferenceModel` hardcodes HuggingFace naming convention (`input_ids`, `attention_mask`, `token_type_ids`). ONNX models using original BERT names or ONNX export defaults fail at load time with `ModelLoadException`.

**Design:** Static alias resolution at construction time. `OnnxInferenceModel` inspects the model's actual input names and resolves them against a known alias table:

| Semantic role | Canonical name | Known aliases |
|---|---|---|
| Token IDs | `input_ids` | `tokens`, `input.1` |
| Attention mask | `attention_mask` | `input_mask`, `mask`, `input.2` |
| Token type IDs | `token_type_ids` | `segment_ids`, `input.3` |

Resolution algorithm:
1. For each semantic role, check if the canonical name is in the model's input names
2. If not, check each alias in order
3. If an alias matches, record the mapping: semantic role → actual model name
4. If no match found for a required role (token IDs, attention mask), throw `ModelLoadException` listing the model's actual names and all known aliases

The resolved names are stored as instance fields and used in `run()` and `runBatch()` (replacing the hardcoded string literals).

**Fallback — explicit overrides via ModelConfig:** Add optional `Map<String, String> inputNameOverrides` to `ModelConfig`. When provided, overrides take precedence over alias resolution. Handles fully custom input names that don't match any known alias.

```java
// ModelConfig addition
public record ModelConfig(
    Path modelPath,
    Path tokenizerPath,
    int maxSequenceLength,
    int intraOpThreads,
    int interOpThreads,
    Map<String, String> inputNameOverrides   // nullable, keyed by canonical name
) { ... }
```

**Files changed:**
- `inference-runtime/.../OnnxInferenceModel.java` — alias resolution in constructor, resolved names in run/runBatch
- `inference-runtime/.../ModelConfig.java` — add `inputNameOverrides` field
- `inference-runtime/.../ OnnxInferenceModelTest.java` — test with `wrong-inputs-model.onnx` (currently asserts rejection; flip to assert successful alias resolution), add test for explicit overrides

### 1.2 Rank-3 SPLADE Max-Pool Reduction (#52)

**Problem:** SPLADE models may output rank-3 tensors `[batch, seq_len, vocab_size]`. `SparseEmbedder` requires `outputSize()` (empty for rank-3) and calls `values()` (returns first token only for rank-3). Standard processing is max-pool across the sequence dimension.

**Design:** Fix in `SparseEmbedder` — it owns SPLADE semantics and knows the reduction operation.

Changes to `SparseEmbedder`:
1. Remove the `outputSize()` validation gate — it gates construction but the value is never used
2. Replace `output.values()` with explicit output access: get the single output name via `output.outputNames().iterator().next()`, then call `output.output(name)` to get `float[][]`
3. Detect output shape:
   - `float[][].length == 1` → rank-2 (`[1][vocab_size]`), take `[0]` — current behavior
   - `float[][].length > 1` → rank-3 (`[seq_len][vocab_size]`), max-pool across dim 0
4. Apply `logSaturate()` to the resulting `float[vocab_size]`

Max-pool reduction:
```java
private float[] maxPool(float[][] tokenVectors) {
    int vocabSize = tokenVectors[0].length;
    float[] pooled = new float[vocabSize];
    for (float[] tokenVector : tokenVectors) {
        for (int i = 0; i < vocabSize; i++) {
            pooled[i] = Math.max(pooled[i], tokenVector[i]);
        }
    }
    return pooled;
}
```

Batch handling: `embedBatch()` calls `model.runBatch()`. Each per-sample `InferenceOutput` may be rank-2 or rank-3 (OnnxInferenceModel already strips padding for rank-3 via attention mask). Same detection logic per sample.

Validation: `SparseEmbedder` still validates that the model has exactly one output (multi-output models are not SPLADE models). The check changes from `outputSize().isPresent()` to `outputNames().size() == 1`.

**Files changed:**
- `inference-splade/.../SparseEmbedder.java` — remove outputSize gate, add max-pool, use output(name)
- `inference-splade/.../SparseEmbedderTest.java` — add rank-3 tests (create a mock InferenceModel returning rank-3 output, verify max-pool produces correct sparse map)

---

## 2. RAG Embedding Adapter (#61)

**Problem:** `MultiModalEmbedder` is the sole embedding contract for RAG. Only `BgeM3Embedder` implements it. Deployments using LangChain4j `EmbeddingModel` (dense) + optional `SparseEmbedder` (sparse) have no path into the RAG pipeline.

**Design:** `SeparateModelEmbedder` in `rag/` module composes existing models into `MultiModalEmbedder`.

```java
public final class SeparateModelEmbedder implements MultiModalEmbedder {
    private final EmbeddingModel denseModel;
    private final SparseEmbedder sparseEmbedder;  // nullable
    private final int maxSequenceLength;

    public SeparateModelEmbedder(EmbeddingModel denseModel, int maxSequenceLength) { ... }
    public SeparateModelEmbedder(EmbeddingModel denseModel, SparseEmbedder sparseEmbedder,
                                  int maxSequenceLength) { ... }
}
```

Method implementations:
- `embed(text)` → dense from `denseModel.embed(text).content().vector()`, sparse from `sparseEmbedder.embed(text)` if present, ColBERT always null
- `embedBatch(texts)` → dense from `denseModel.embedAll(...)`, sparse from `sparseEmbedder.embedBatch(...)`, zip results
- `supportedModes()` → `{DENSE}` or `{DENSE, SPARSE}`
- `denseDimension()` → `denseModel.dimension()`
- `colbertDimension()` → `OptionalInt.empty()`
- `maxSequenceLength()` → constructor param

**Module placement:** `rag/` — already depends on both `langchain4j-core` and `inference-api`. The adapter is consumed by the RAG pipeline's CDI producers.

**CDI wiring:** `@DefaultBean` producer in `RagBeanProducer`:

```java
@Produces @DefaultBean @ApplicationScoped
@IfBuildProperty(name = "casehub.rag.embedder.enabled", stringValue = "true", enableIfMissing = true)
MultiModalEmbedder separateModelEmbedder(
        Instance<EmbeddingModel> denseModel,
        Instance<SparseEmbedder> sparseEmbedder,
        RagConfig config) {
    if (denseModel.isUnsatisfied()) {
        throw new IllegalStateException(
            "No EmbeddingModel available — provide a LangChain4j EmbeddingModel bean "
            + "or configure BGE-M3. Set casehub.rag.embedder.enabled=false to disable RAG.");
    }
    MultiModalEmbedder embedder;
    if (sparseEmbedder.isResolvable()) {
        embedder = new SeparateModelEmbedder(denseModel.get(), sparseEmbedder.get(),
            config.maxSequenceLength().orElse(512));
    } else {
        embedder = new SeparateModelEmbedder(denseModel.get(),
            config.maxSequenceLength().orElse(512));
    }
    return maybeWrapMatryoshka(embedder, config);
}
```

Deployments without any embedding model disable RAG via `casehub.rag.embedder.enabled=false`. The `@IfBuildProperty` guard prevents CDI from attempting to produce the bean at all.

BgeM3Embedder (when configured by Hortora's `HybridSearchProducer` as `@ApplicationScoped`) displaces this `@DefaultBean` automatically.

**Matryoshka double-wrap fix:** `RagBeanProducer.effectiveEmbedder()` currently wraps unconditionally when `matryoshka.dimension` is set. Fix: check `instanceof MatryoshkaMultiModalEmbedder` before wrapping. This prevents double-wrapping when the producer already applied Matryoshka.

**Files changed:**
- `rag/.../SeparateModelEmbedder.java` — new class
- `rag/.../RagBeanProducer.java` — add @DefaultBean producer, fix Matryoshka double-wrap
- `rag/.../ReactiveRagBeanProducer.java` — same @DefaultBean and Matryoshka fix
- `rag/.../SeparateModelEmbedderTest.java` — new test
- `rag/.../RagConfig.java` — add `maxSequenceLength()` optional config

---

## 3. Configurable Fusion Strategy (#104)

**Problem:** `HybridCaseRetriever` hardcodes `QueryFactory.rrf()` for multi-leg fusion. Need RRF, DBSF, and Convex Combination as selectable strategies.

**Design:** Config-driven strategy selection with two code paths — server-side (RRF/DBSF via Qdrant prefetch) and client-side (CC via separate queries).

### 3.1 New types in `rag-api`

```java
public enum FusionStrategy { RRF, DBSF, CC }
```

```java
public final class ConvexCombinationFusion {
    public record ScoredLeg(List<RetrievedChunk> chunks, double weight) {}

    public static List<RetrievedChunk> fuse(List<ScoredLeg> legs, int maxResults) { ... }
}
```

CC fusion algorithm:
1. Min-max normalize scores within each leg to [0, 1]
2. For each unique document (keyed by sourceDocumentId + content):
   - `score = Σ(leg_weight × normalized_score)` across all legs containing it
   - Documents absent from a leg contribute 0 for that leg
3. Preserve best `RelevanceGrade` across duplicates (same as `RrfFusion`)
4. Sort by descending score, return topK

### 3.2 Config additions in `RagConfig`

```java
interface RetrievalConfig {
    @WithDefault("RRF")
    FusionStrategy fusionStrategy();

    @WithDefault("60")
    int rrfK();  // existing, only used when strategy=RRF

    CcWeightsConfig ccWeights();  // only used when strategy=CC
}

interface CcWeightsConfig {
    @WithDefault("0.5")
    double dense();

    @WithDefault("0.3")
    double sparse();

    @WithDefault("0.2")
    double bm25();
}
```

### 3.3 Retriever changes

**RRF path (current, unchanged):** Prefetch legs → `QueryFactory.rrf(Rrf.newBuilder().setK(rrfK).build())` as outer query.

**DBSF path (new, server-side):** Prefetch legs → `QueryFactory.fusion(Fusion.DBSF)` as outer query. Swap only.

**CC path (new, client-side):**
1. Build separate `QueryPoints` for each active leg (dense, sparse, BM25) with individual limits (`denseTopK`, `sparseTopK`, `bm25TopK`)
2. Execute each as a standalone Qdrant `QueryPoints` request
3. Convert results to `List<RetrievedChunk>` per leg
4. Call `ConvexCombinationFusion.fuse()` with configured weights
5. If ColBERT reranking enabled: take top `rerankTopN` from fused results, run ColBERT MAX_SIM query against Qdrant, re-sort

The CC path runs 3 queries (dense + sparse + BM25) plus optionally 1 for ColBERT = 4 round trips. RRF/DBSF remain 1 round trip. This tradeoff is explicit and documented.

Both `HybridCaseRetriever` and `ReactiveHybridCaseRetriever` switch on `config.retrieval().fusionStrategy()`.

**Files changed:**
- `rag-api/.../FusionStrategy.java` — new enum
- `rag-api/.../ConvexCombinationFusion.java` — new utility
- `rag-api/.../ConvexCombinationFusionTest.java` — new test
- `rag/.../RagConfig.java` — add fusionStrategy, ccWeights
- `rag/.../HybridCaseRetriever.java` — strategy switch
- `rag/.../ReactiveHybridCaseRetriever.java` — strategy switch (parity)
- `rag/.../HybridCaseRetrieverTest.java` — add DBSF and CC test cases
- `rag/.../ReactiveHybridCaseRetrieverTest.java` — parity tests
- `rag/.../RagTestFixtures.java` — update stub config

---

## 4. CBR Weighted Similarity (#82 + #87)

**Problem:** `retrieveSimilar()` returns `score=1.0` for all filter matches. No per-field similarity computation. No per-field weights. Features are hard Qdrant-side payload filters (pass/fail).

**Design:** Proper CBR similarity model with per-field local similarity functions, per-field weights, and composite scoring.

### 4.1 CbrQuery changes (`memory-api`)

```java
public record CbrQuery(
    String tenantId,
    MemoryDomain domain,
    String caseType,
    Map<String, Object> features,
    Map<String, Double> weights,       // NEW — per-field weights, default empty (uniform)
    int topK,
    double minSimilarity,
    Instant notBefore,
    String problem,
    double vectorWeight                // NEW — β: balance vector vs feature sim, default 0.5
) { ... }
```

New convenience methods:
- `withWeights(Map<String, Double>)` — wither
- `withWeight(String field, double weight)` — single-field wither
- `withVectorWeight(double)` — wither

Updated factory: `CbrQuery.of(...)` sets `weights=Map.of()` and `vectorWeight=0.5`.

### 4.2 CbrSimilarityScorer (`memory-api`)

New pure-Java utility — Tier 1, zero deps:

```java
public final class CbrSimilarityScorer {

    public static double score(
            Map<String, Object> queryFeatures,
            Map<String, Object> caseFeatures,
            Map<String, Double> weights,
            CbrFeatureSchema schema) { ... }

    public static double compositeScore(
            double featureScore,
            double vectorScore,
            double vectorWeight) { ... }
}
```

**`score()` algorithm:**
1. For each query feature with a matching schema field:
   - Compute local similarity based on field type
   - Look up weight (default 1.0 if not in weights map)
   - Accumulate `weightedSum += weight * localSim` and `totalWeight += weight`
2. If the case lacks a query feature entirely: local similarity = 0.0
3. Return `weightedSum / totalWeight` (or 0.0 if no features matched)

**Local similarity by field type:**
- `Categorical`: `query.equals(caseValue) ? 1.0 : 0.0`
- `Numeric`: `1.0 - Math.abs(queryNum - caseNum) / (field.max() - field.min())`, clamped to [0, 1]. If `max == min`, exact match semantics (1.0 or 0.0).
- `Text`: `query.equals(caseValue) ? 1.0 : 0.0` (semantic similarity deferred — see §4.5)

Query feature value types for numeric:
- Plain `Number`: treated as exact query value. `localSim = 1.0 - |query - case| / range`
- `NumericRange`: treated as target range. `localSim = 1.0` if case value is within range, decays linearly outside range: `1.0 - distance_to_nearest_bound / range`

**`compositeScore()`:** `vectorWeight * vectorScore + (1 - vectorWeight) * featureScore`

### 4.3 Retrieval flow changes

**QdrantCbrCaseMemoryStore:**

Old flow:
1. Build filter (tenant + domain + caseType + features as hard `must` + notBefore)
2. Dense search or scroll → return with Qdrant score

New flow:
1. Build identity filter only (tenant + domain + caseType + notBefore)
2. Retrieve candidates:
   - If `problem` set: `SearchPoints` with dense vector + identity filter, limit = `topK * oversampleFactor` (default 3). Get cosine scores.
   - If `problem` null: `ScrollPoints` with identity filter, limit = `overFetchLimit` (default 200)
3. Reconstruct `CbrCase` from each candidate's payload
4. Compute `featureScore = CbrSimilarityScorer.score(query.features(), case.features(), query.weights(), schema)`
5. Compute `finalScore`:
   - If dense search was active: `CbrSimilarityScorer.compositeScore(featureScore, qdrantCosine, query.vectorWeight())`
   - If filter-only: `featureScore`
6. Filter by `minSimilarity`
7. Sort by `finalScore` descending, take `topK`

**CbrQueryTranslator changes:**
- Rename or split: identity-only filter method vs full filter method
- The identity filter builds `must` conditions for tenant, domain, caseType, notBefore only — features are no longer part of the Qdrant filter

**InMemoryCbrCaseMemoryStore:**
- Replace boolean `matchesFeatures()` with `CbrSimilarityScorer.score()`
- Sort by score, apply `minSimilarity` threshold, take `topK`
- Same scoring logic as Qdrant path — backend-independent

**CbrCollectionManager:** No changes. Payload indexes on feature fields remain — they're still useful for future optimization (Qdrant `should` clause scoring).

### 4.4 Config

```java
interface CbrConfig {
    @WithDefault("3")
    int oversampleFactor();    // multiplier for dense search candidates

    @WithDefault("200")
    int overFetchLimit();      // max candidates when no dense search
}
```

Config prefix: `casehub.cbr.similarity`.

### 4.5 Deferred concerns — file as GitHub issues

1. **Semantic text field similarity** — `FeatureField.Text` currently uses exact match. Future: embed text values via `EmbeddingModel` and compute cosine similarity. Requires `EmbeddingModel` dependency in the scorer, which conflicts with Tier 1 placement.

2. **Categorical similarity tables** — Non-binary categorical similarity (domain-specific equivalence classes). Requires schema-level configuration of a similarity matrix.

3. **Per-field similarity function configuration** — Custom `SimilarityFunction` enum on `FeatureField` (Gaussian, step, exponential decay). Derive-from-type is sufficient for now.

### 4.6 Contract test additions (`memory-testing`)

New tests for `CbrCaseMemoryStoreContractTest`:
- `weightedScoringProducesExpectedRanking` — two cases differing in a weighted field, verify order
- `defaultWeightsAreUniform` — no weights → all features equal
- `numericSimilarityDecay` — closer numeric value scores higher
- `categoricalExactMatchScoring` — match=1.0, mismatch=0.0
- `minSimilarityThresholdOnCompositeScore` — below threshold excluded
- `vectorWeightBalancesDenseAndFeature` — verify composite formula
- `missingFeatureScoresZero` — case lacking a queried feature gets 0.0 for that field
- `emptyFeaturesScoresOne` — no features queried → score = 1.0 (vacuous truth, or if problem is set, pure vector score)

---

## 5. Cross-Issue Dependencies

| Issue | Depends on | Reason |
|---|---|---|
| #52 | — | Standalone fix in SparseEmbedder |
| #51 | — | Standalone fix in OnnxInferenceModel |
| #61 | #52 | SeparateModelEmbedder's sparse leg depends on SparseEmbedder handling rank-3 |
| #104 | #61 | CC fusion needs to work with both BgeM3 and SeparateModel embedders |
| #82+#87 | — | Independent of inference/RAG changes |

Implementation order: #51 → #52 → #61 → #104 → #82+#87

---

## 6. Protocol Compliance

| Protocol | How this design complies |
|---|---|
| `module-tier-structure` | `CbrSimilarityScorer` is pure Java in `memory-api` (Tier 1). `SeparateModelEmbedder` in `rag/` (Tier 3). No tier violations. |
| `persistence-backend-cdi-priority` | CDI ladder unchanged. `SeparateModelEmbedder` is `@DefaultBean`, displaced by `BgeM3Embedder` (`@ApplicationScoped`). |
| `spi-signature-change-all-impls-same-commit` | `CbrQuery` record change updates all implementations in same commit: QdrantCbrCaseMemoryStore, InMemoryCbrCaseMemoryStore, NoOpCbrCaseMemoryStore, contract test. |
| `reactive-blocking-tier-separation` | Retriever changes maintain blocking/reactive parity. |
