# Retrieval Fusion Weights, Payload Boosting, and Query Analytics — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #178 — feat: configurable per-leg RRF/fusion weights in HybridCaseRetriever
**Issue group:** #178, #179, #180

**Goal:** Unified per-leg fusion weights across RRF/CC, payload-based quality boosting with strategy-derived integration, and query-level retrieval analytics.

**Architecture:** Three changes in existing modules. `ScoreFusion.rrf()` gains weighted scoring. `HybridCaseRetriever` gets client-side weighted RRF fallback and CC quality leg. `PayloadBoostCaseRetriever` decorator handles RRF/DBSF quality rescore. `RetrievalAnalyzer` gains three query-level static methods. CBR guard in `QdrantCbrCaseMemoryStore` prevents weighted RRF regression.

**Tech Stack:** Java 21, Quarkus 3.32.2, SmallRye Config, CDI decorators, Qdrant gRPC, JUnit 5 + AssertJ

## Global Constraints

- Java 21 source on Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Build with `mvn` not `./mvnw`
- All weight values >= 0 (validated at startup)
- Pre-release: breaking config changes acceptable
- IntelliJ MCP mandatory for all .java edits — use `ide_edit_member`, `ide_replace_member`, `ide_insert_member`, `ide_create_file`
- `project_path=/Users/mdproctor/claude/casehub/neocortex` for all IntelliJ calls

---

### Task 1: Weighted RRF in ScoreFusion

**Files:**
- Modify: `fusion-api/src/main/java/io/casehub/neocortex/fusion/ScoreFusion.java` — `rrf()` method
- Modify: `fusion-api/src/test/java/io/casehub/neocortex/fusion/ScoreFusionTest.java` — add weighted tests

**Interfaces:**
- Consumes: `ScoreFusion.ScoredLeg<T>(items, scoreExtractor, weight)` — existing record
- Produces: `ScoreFusion.rrf()` now multiplies each leg's contribution by `leg.weight()`. Normalization: `maxScore = totalWeight / (k + 1)`. Output remains [0, 1]. With all weights 1.0, behavior is identical to current.

- [ ] **Step 1: Write failing tests for weighted RRF**

Add these tests to `ScoreFusionTest.java` using `ide_insert_member`:

```java
@Test
void rrf_weightedLegs_higherWeightIncreasesContribution() {
    var legA = leg(2.0, item("a", 0.9));
    var legB = leg(1.0, item("b", 0.8));
    var results = ScoreFusion.rrf(List.of(legA, legB), Item::id, 10, 60);
    assertThat(results.get(0).item().id()).isEqualTo("a");
    assertThat(results.get(0).score()).isGreaterThan(results.get(1).score());
}

@Test
void rrf_equalWeights_matchesUnweightedBehavior() {
    var legA = leg(1.0, item("a", 0.9), item("b", 0.8));
    var legB = leg(1.0, item("a", 0.7), item("c", 0.6));
    var equalResult = ScoreFusion.rrf(List.of(legA, legB), Item::id, 3, 60);

    var legA5 = leg(5.0, item("a", 0.9), item("b", 0.8));
    var legB5 = leg(5.0, item("a", 0.7), item("c", 0.6));
    var scaledResult = ScoreFusion.rrf(List.of(legA5, legB5), Item::id, 3, 60);

    assertThat(equalResult.get(0).item().id()).isEqualTo(scaledResult.get(0).item().id());
    assertThat(equalResult.get(0).score()).isCloseTo(scaledResult.get(0).score(), within(0.001));
}

@Test
void rrf_zeroWeightLeg_contributesNothing() {
    var legA = leg(1.0, item("a", 0.9));
    var legB = leg(0.0, item("b", 0.8));
    var results = ScoreFusion.rrf(List.of(legA, legB), Item::id, 10, 60);
    assertThat(results).hasSize(2);
    assertThat(results.get(0).item().id()).isEqualTo("a");
    assertThat(results.get(0).score()).isGreaterThan(0);
    assertThat(results.get(1).score()).isCloseTo(0.0, within(0.001));
}

@Test
void rrf_weightedNormalization_outputInZeroToOne() {
    var legA = leg(3.0, item("a", 0.9));
    var legB = leg(1.0, item("a", 0.8));
    var results = ScoreFusion.rrf(List.of(legA, legB), Item::id, 10, 60);
    for (var r : results) {
        assertThat(r.score()).isBetween(0.0, 1.0);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl fusion-api -Dtest=ScoreFusionTest -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: tests fail because `rrf()` ignores weights — `rrf_weightedLegs_higherWeightIncreasesContribution` fails (equal scores), `rrf_zeroWeightLeg_contributesNothing` fails (non-zero score for zero-weight leg).

- [ ] **Step 3: Implement weighted RRF**

Use `ide_replace_member` on `ScoreFusion.rrf()`:

```java
public static <T> List<FusedResult<T>> rrf(
        List<ScoredLeg<T>> legs,
        Function<T, String> idExtractor,
        int topK,
        double k) {
    if (legs.isEmpty()) return List.of();

    Map<String, Double> scores = new LinkedHashMap<>();
    Map<String, T> items = new LinkedHashMap<>();

    double totalWeight = 0;
    for (ScoredLeg<T> leg : legs) {
        totalWeight += leg.weight();
        if (leg.weight() <= 0) continue;
        List<T> sorted = new ArrayList<>(leg.items());
        sorted.sort(Comparator.comparingDouble(leg.scoreExtractor()).reversed());
        for (int rank = 0; rank < sorted.size(); rank++) {
            T item = sorted.get(rank);
            String id = idExtractor.apply(item);
            scores.merge(id, leg.weight() / (k + rank + 1), Double::sum);
            items.putIfAbsent(id, item);
        }
    }

    double maxScore = totalWeight > 0 ? totalWeight / (k + 1) : 0;

    List<Map.Entry<String, Double>> sorted = new ArrayList<>(scores.entrySet());
    sorted.sort(Map.Entry.<String, Double>comparingByValue().reversed());

    List<FusedResult<T>> result = new ArrayList<>(Math.min(sorted.size(), topK));
    for (int i = 0; i < Math.min(sorted.size(), topK); i++) {
        Map.Entry<String, Double> entry = sorted.get(i);
        double normalized = maxScore > 0 ? entry.getValue() / maxScore : 0.0;
        result.add(new FusedResult<>(items.get(entry.getKey()), normalized));
    }
    return List.copyOf(result);
}
```

- [ ] **Step 4: Run all ScoreFusion tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl fusion-api -Dtest=ScoreFusionTest
```

Expected: ALL tests pass (new weighted tests + existing unweighted tests unchanged since all existing tests use weight=1.0).

- [ ] **Step 5: Verify with ide_diagnostics**

Run `ide_diagnostics` on `ScoreFusion.java` — expect zero errors.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add fusion-api/src/main/java/io/casehub/neocortex/fusion/ScoreFusion.java fusion-api/src/test/java/io/casehub/neocortex/fusion/ScoreFusionTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#178): weighted RRF in ScoreFusion — leg.weight() scales rank contribution"
```

---

### Task 2: FusionWeightsConfig replacing CcWeightsConfig

**Files:**
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/RagConfig.java` — replace `CcWeightsConfig` with `FusionWeightsConfig`, add `qualityPayloadField`, `qualityMax`, startup validation
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java` — update `ccWeights()` → `weights()` references in `executeConvexCombinationFusion()`

**Interfaces:**
- Consumes: nothing new
- Produces: `RagConfig.RetrievalConfig.weights()` returning `FusionWeightsConfig` with `dense()`, `sparse()`, `bm25()`, `quality()`. `RetrievalConfig.qualityPayloadField()` returning `Optional<String>`. `RetrievalConfig.qualityMax()` returning `double` (default 10.0).

- [ ] **Step 1: Replace CcWeightsConfig with FusionWeightsConfig in RagConfig**

Use `ide_edit_member` on `RagConfig.CcWeightsConfig` (member=`CcWeightsConfig`):

```java
interface FusionWeightsConfig {
    @WithDefault("1.0") double dense();
    @WithDefault("1.0") double sparse();
    @WithDefault("1.0") double bm25();
    @WithDefault("0.0") double quality();
}
```

Use `ide_edit_member` on `RetrievalConfig.ccWeights` to rename and update return type:

```java
FusionWeightsConfig weights();
```

Add to `RetrievalConfig` using `ide_insert_member`:

```java
Optional<String> qualityPayloadField();

@WithDefault("10.0")
double qualityMax();
```

- [ ] **Step 2: Update HybridCaseRetriever references**

In `executeConvexCombinationFusion()`, use `ide_replace_text_in_file` to replace all `config.retrieval().ccWeights()` with `config.retrieval().weights()`:

- `config.retrieval().ccWeights().dense()` → `config.retrieval().weights().dense()`
- `config.retrieval().ccWeights().sparse()` → `config.retrieval().weights().sparse()`
- `config.retrieval().ccWeights().bm25()` → `config.retrieval().weights().bm25()`

- [ ] **Step 3: Verify with ide_diagnostics**

Run `ide_diagnostics` on both `RagConfig.java` and `HybridCaseRetriever.java`. Expect zero errors.

- [ ] **Step 4: Run HybridCaseRetriever tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest
```

Expected: all existing tests pass (default weights are 1.0 — equal weighting, same behavior).

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag/src/main/java/io/casehub/neocortex/rag/runtime/RagConfig.java rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#178): replace CcWeightsConfig with FusionWeightsConfig — unified per-leg weights"
```

---

### Task 3: Client-side weighted RRF in HybridCaseRetriever

**Files:**
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java` — add `executeRrfFusion()`, equal-weight detection, DBSF warning
- Modify: `rag/src/test/java/io/casehub/neocortex/rag/runtime/HybridCaseRetrieverTest.java` — add client-side RRF test

**Interfaces:**
- Consumes: `ScoreFusion.rrf()` (Task 1), `FusionWeightsConfig` (Task 2)
- Produces: `HybridCaseRetriever.retrieve()` with strategy-aware fusion: server-side RRF for equal weights, client-side `ScoreFusion.rrf()` for non-equal weights.

- [ ] **Step 1: Add equal-weight detection helper**

Use `ide_insert_member` in `HybridCaseRetriever`, after `buildFusionQuery`:

```java
private boolean hasEqualActiveWeights() {
    double dense = config.retrieval().weights().dense();
    double sparse = embedder.supportedModes().contains(io.casehub.neocortex.inference.EmbeddingMode.SPARSE)
        ? config.retrieval().weights().sparse() : dense;
    double bm25 = config.bm25Enabled() ? config.retrieval().weights().bm25() : dense;
    return Double.compare(dense, sparse) == 0 && Double.compare(dense, bm25) == 0;
}
```

- [ ] **Step 2: Add executeRrfFusion method**

Use `ide_insert_member` after `executeConvexCombinationFusion`:

```java
private List<RetrievedChunk> executeRrfFusion(
        String collection, RetrievalQuery query, MultiModalEmbedding searchTextEmbedding,
        MultiModalEmbedding originalTextEmbedding, Optional<Filter> mergedFilter, int maxResults) {

    List<Float> denseVector = QdrantPointBuilder.floatListFrom(searchTextEmbedding.dense());
    List<ScoreFusion.ScoredLeg<RetrievedChunk>> legs = new ArrayList<>();

    QueryPoints.Builder denseQuery = QueryPoints.newBuilder()
        .setCollectionName(collection)
        .setQuery(QueryFactory.nearest(denseVector))
        .setUsing(config.denseVectorName())
        .setLimit(config.retrieval().denseTopK())
        .setWithPayload(WithPayloadSelectorFactory.enable(true));
    if (config.quantization().type() != DenseQuantization.NONE && config.quantization().oversampling().isPresent()) {
        denseQuery.setParams(quantizationSearchParams());
    }
    mergedFilter.ifPresent(denseQuery::setFilter);

    List<ScoredPoint> densePoints = executeQuery(denseQuery.build());
    if (!densePoints.isEmpty()) {
        legs.add(new ScoreFusion.ScoredLeg<>(
            mapToChunks(densePoints), RetrievedChunk::relevanceScore, config.retrieval().weights().dense()));
    }

    if (originalTextEmbedding.sparse() != null) {
        Map<Integer, Float> sparseMap = originalTextEmbedding.sparse();
        List<Float> sparseValues = new ArrayList<>(sparseMap.size());
        List<Integer> sparseIndices = new ArrayList<>(sparseMap.size());
        for (Map.Entry<Integer, Float> entry : sparseMap.entrySet()) {
            sparseIndices.add(entry.getKey());
            sparseValues.add(entry.getValue());
        }

        QueryPoints.Builder sparseQuery = QueryPoints.newBuilder()
            .setCollectionName(collection)
            .setQuery(QueryFactory.nearest(sparseValues, sparseIndices))
            .setUsing(config.sparseVectorName())
            .setLimit(config.retrieval().sparseTopK())
            .setWithPayload(WithPayloadSelectorFactory.enable(true));
        mergedFilter.ifPresent(sparseQuery::setFilter);

        List<ScoredPoint> sparsePoints = executeQuery(sparseQuery.build());
        if (!sparsePoints.isEmpty()) {
            legs.add(new ScoreFusion.ScoredLeg<>(
                mapToChunks(sparsePoints), RetrievedChunk::relevanceScore, config.retrieval().weights().sparse()));
        }
    }

    if (config.bm25Enabled()) {
        String expandedQuery = CamelCaseExpander.expand(query.text());
        QueryPoints.Builder bm25Query = QueryPoints.newBuilder()
            .setCollectionName(collection)
            .setQuery(QueryFactory.nearest(
                Document.newBuilder()
                    .setText(expandedQuery)
                    .setModel(QdrantPointBuilder.BM25_MODEL)
                    .build()))
            .setUsing(config.bm25VectorName())
            .setLimit(config.retrieval().bm25TopK())
            .setWithPayload(WithPayloadSelectorFactory.enable(true));
        mergedFilter.ifPresent(bm25Query::setFilter);

        List<ScoredPoint> bm25Points = executeQuery(bm25Query.build());
        if (!bm25Points.isEmpty()) {
            legs.add(new ScoreFusion.ScoredLeg<>(
                mapToChunks(bm25Points), RetrievedChunk::relevanceScore, config.retrieval().weights().bm25()));
        }
    }

    return ScoreFusion.rrf(legs, RetrievedChunk::fusionKey, maxResults, config.retrieval().rrfK())
        .stream().map(f -> f.item().withRelevanceScore(f.score())).toList();
}
```

- [ ] **Step 3: Wire client-side RRF into retrieve()**

In `retrieve()`, modify the fusion path. Find the block starting with `if (useFusion && fusionStrategy == FusionStrategy.CC)` and add the weighted RRF check before it. Use `ide_replace_member` on `retrieve`:

The logic in `retrieve()` should become (after the embedding block, around line 110):

```java
if (useFusion && fusionStrategy == FusionStrategy.CC) {
    return executeConvexCombinationFusion(collection, query, searchTextEmbedding,
        originalTextEmbedding, mergedFilter, maxResults);
}

if (useFusion && fusionStrategy == FusionStrategy.RRF && !hasEqualActiveWeights()) {
    return executeRrfFusion(collection, query, searchTextEmbedding,
        originalTextEmbedding, mergedFilter, maxResults);
}
```

The existing server-side RRF path continues below for equal-weight RRF.

- [ ] **Step 4: Add DBSF startup warning**

Add a `@PostConstruct` or constructor log warning. Use `ide_insert_member`:

```java
private static final org.jboss.logging.Logger LOG = org.jboss.logging.Logger.getLogger(HybridCaseRetriever.class);
```

In the 4-arg constructor, add after assignments:

```java
if (config.retrieval().fusionStrategy() == FusionStrategy.DBSF && !hasEqualActiveWeightsFromConfig(config)) {
    LOG.warn("Non-equal fusion weights have no effect with DBSF strategy — " +
             "DBSF uses server-side equal-weight fusion. Consider RRF or CC for per-leg weight control.");
}
```

Add a static helper (since `hasEqualActiveWeights()` uses instance state that may not be available at construction):

```java
private static boolean hasEqualActiveWeightsFromConfig(RagConfig config) {
    double d = config.retrieval().weights().dense();
    double s = config.retrieval().weights().sparse();
    double b = config.retrieval().weights().bm25();
    return Double.compare(d, s) == 0 && Double.compare(d, b) == 0;
}
```

- [ ] **Step 5: Verify with ide_diagnostics and run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest
```

Expected: all tests pass. The existing `threeWayRrfIngestAndRetrieve` test uses default weights (all 1.0 = equal), so it continues using server-side RRF.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#178): client-side weighted RRF fallback when fusion weights are non-equal"
```

---

### Task 4: CBR guard for weighted RRF

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java` — guard in `fuseAndScore()` for RRF strategy
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStoreTest.java` — test CBR guard
- Test: `memory-testing/src/test/java/io/casehub/neocortex/memory/cbr/testing/InMemoryCbrCaseMemoryStoreTest.java` — verify contract tests still pass

**Interfaces:**
- Consumes: `ScoreFusion.rrf()` (Task 1 — now uses weights)
- Produces: CBR's RRF path uses `weight=1.0` for ALL legs, preserving current equal-weight behavior.

- [ ] **Step 1: Write failing test**

The test should verify that CBR's RRF path uses equal weights regardless of CC config. Since this is an integration test against Qdrant, add a simpler unit-level assertion. In `QdrantCbrCaseMemoryStoreTest`, or if that's Testcontainers-only, verify behavior via the contract test.

Actually, the guard can be verified by existing contract tests since the behavior should not change. The real risk is that WITHOUT the guard, the weighted RRF would change scores. So the test is: run the existing CBR contract tests after Task 1's ScoreFusion change — they should still pass because the guard neutralizes the weight change.

- [ ] **Step 2: Add the guard in fuseAndScore()**

In `QdrantCbrCaseMemoryStore.fuseAndScore()`, use `ide_replace_member` on `fuseAndScore`. The change is in the leg construction block (around lines 430-460). Replace the weight computation to be strategy-aware:

Currently the weight computation is unconditional:
```java
double featureWeight = 1.0 - query.vectorWeight();
// ...
double rawDense = (!denseLeg.isEmpty()) ? config.ccWeights().dense() : 0.0;
// etc.
```

Replace with:

```java
boolean useEqualWeights = query.fusionStrategy() == FusionStrategy.RRF;

double featureWeight = useEqualWeights ? 1.0 : (1.0 - query.vectorWeight());
var featureScoredLeg = new ScoreFusion.ScoredLeg<>(featureLeg, FusionEntry::score, featureWeight);

double rawDense, rawSparse, rawBm25;
if (useEqualWeights) {
    rawDense = (!denseLeg.isEmpty()) ? 1.0 : 0.0;
    rawSparse = (!spladeLeg.isEmpty()) ? 1.0 : 0.0;
    rawBm25 = (!bm25Leg.isEmpty()) ? 1.0 : 0.0;
} else {
    rawDense = (!denseLeg.isEmpty()) ? config.ccWeights().dense() : 0.0;
    rawSparse = (!spladeLeg.isEmpty()) ? config.ccWeights().sparse() : 0.0;
    rawBm25 = (!bm25Leg.isEmpty()) ? config.ccWeights().bm25() : 0.0;
}
double semanticTotal = rawDense + rawSparse + rawBm25;

List<ScoreFusion.ScoredLeg<FusionEntry<C>>> legs = new ArrayList<>();
legs.add(featureScoredLeg);
if (!denseLeg.isEmpty() && semanticTotal > 0) {
    double denseWeight = useEqualWeights ? 1.0 : query.vectorWeight() * rawDense / semanticTotal;
    legs.add(new ScoreFusion.ScoredLeg<>(denseLeg, FusionEntry::score, denseWeight));
}
if (!spladeLeg.isEmpty() && semanticTotal > 0) {
    double sparseWeight = useEqualWeights ? 1.0 : query.vectorWeight() * rawSparse / semanticTotal;
    legs.add(new ScoreFusion.ScoredLeg<>(spladeLeg, FusionEntry::score, sparseWeight));
}
if (!bm25Leg.isEmpty() && semanticTotal > 0) {
    double bm25Weight = useEqualWeights ? 1.0 : query.vectorWeight() * rawBm25 / semanticTotal;
    legs.add(new ScoreFusion.ScoredLeg<>(bm25Leg, FusionEntry::score, bm25Weight));
}
```

- [ ] **Step 3: Run CBR contract tests and Qdrant integration tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-testing
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant
```

Expected: all tests pass — RRF behavior unchanged (equal weights), CC behavior unchanged (CC-derived weights still used).

- [ ] **Step 4: Verify with ide_diagnostics**

Run `ide_diagnostics` on `QdrantCbrCaseMemoryStore.java` — expect zero errors.

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "fix(#178): CBR guard — RRF uses equal-weight legs to preserve current behavior"
```

---

### Task 5: Payload quality boost — decorator + CC quality leg

**Files:**
- Create: `rag/src/main/java/io/casehub/neocortex/rag/runtime/PayloadBoostCaseRetriever.java` — `@Decorator @Priority(60)`
- Create: `rag/src/test/java/io/casehub/neocortex/rag/runtime/PayloadBoostCaseRetrieverTest.java` — unit tests
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java` — numeric payload extraction in `mapToChunks()`, CC quality leg in `executeConvexCombinationFusion()`

**Interfaces:**
- Consumes: `FusionWeightsConfig.quality()` (Task 2), `RetrievalConfig.qualityPayloadField()` (Task 2), `RetrievalConfig.qualityMax()` (Task 2)
- Produces: `PayloadBoostCaseRetriever` decorator on `CaseRetriever` at `@Priority(60)`. CC path integrates quality as a fusion leg. RRF/DBSF path applies post-fusion multiplicative rescore.

- [ ] **Step 1: Write PayloadBoostCaseRetriever tests**

Use `ide_create_file`:

```java
package io.casehub.neocortex.rag.runtime;

import io.casehub.neocortex.fusion.FusionStrategy;
import io.casehub.neocortex.rag.CaseRetriever;
import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.PayloadFilter;
import io.casehub.neocortex.rag.RetrievalQuery;
import io.casehub.neocortex.rag.RetrievedChunk;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;

class PayloadBoostCaseRetrieverTest {

    private static RetrievedChunk chunk(String id, double score, String qualityValue) {
        Map<String, String> metadata = qualityValue != null
            ? Map.of("score", qualityValue) : Map.of();
        return new RetrievedChunk("content-" + id, id, score, metadata);
    }

    private static CaseRetriever stubRetriever(List<RetrievedChunk> results) {
        return (query, corpus, maxResults, filter) -> results;
    }

    private static RagConfig stubConfig(FusionStrategy strategy, double qualityWeight, String qualityField, double qualityMax) {
        return TestRagConfigBuilder.create()
            .fusionStrategy(strategy)
            .qualityWeight(qualityWeight)
            .qualityPayloadField(qualityField)
            .qualityMax(qualityMax)
            .build();
    }

    @Test
    void rrfStrategy_boostsHighQualityDocuments() {
        var chunks = List.of(
            chunk("low-q", 0.8, "3"),
            chunk("high-q", 0.7, "9"));
        var config = stubConfig(FusionStrategy.RRF, 0.5, "score", 10.0);
        var decorator = new PayloadBoostCaseRetriever(stubRetriever(chunks), config);

        var result = decorator.retrieve(RetrievalQuery.of("test"), new CorpusRef("t", "c"), 10, null);

        assertThat(result.get(0).sourceDocumentId()).isEqualTo("high-q");
    }

    @Test
    void ccStrategy_isNoOp() {
        var chunks = List.of(chunk("a", 0.8, "3"), chunk("b", 0.7, "9"));
        var config = stubConfig(FusionStrategy.CC, 0.5, "score", 10.0);
        var decorator = new PayloadBoostCaseRetriever(stubRetriever(chunks), config);

        var result = decorator.retrieve(RetrievalQuery.of("test"), new CorpusRef("t", "c"), 10, null);

        assertThat(result.get(0).sourceDocumentId()).isEqualTo("a");
        assertThat(result.get(0).relevanceScore()).isEqualTo(0.8);
    }

    @Test
    void qualityWeightZero_isNoOp() {
        var chunks = List.of(chunk("a", 0.7, "9"), chunk("b", 0.8, "3"));
        var config = stubConfig(FusionStrategy.RRF, 0.0, null, 10.0);
        var decorator = new PayloadBoostCaseRetriever(stubRetriever(chunks), config);

        var result = decorator.retrieve(RetrievalQuery.of("test"), new CorpusRef("t", "c"), 10, null);

        assertThat(result.get(0).sourceDocumentId()).isEqualTo("b");
    }

    @Test
    void missingQualityField_retainsOriginalScore() {
        var chunks = List.of(chunk("no-field", 0.8, null), chunk("has-field", 0.7, "9"));
        var config = stubConfig(FusionStrategy.RRF, 0.5, "score", 10.0);
        var decorator = new PayloadBoostCaseRetriever(stubRetriever(chunks), config);

        var result = decorator.retrieve(RetrievalQuery.of("test"), new CorpusRef("t", "c"), 10, null);

        assertThat(result).anySatisfy(c ->
            assertThat(c.sourceDocumentId()).isEqualTo("no-field"));
    }

    @Test
    void nonNumericField_retainsOriginalScore() {
        var chunks = List.of(chunk("bad", 0.8, "not-a-number"));
        var config = stubConfig(FusionStrategy.RRF, 0.5, "score", 10.0);
        var decorator = new PayloadBoostCaseRetriever(stubRetriever(chunks), config);

        var result = decorator.retrieve(RetrievalQuery.of("test"), new CorpusRef("t", "c"), 10, null);

        assertThat(result.get(0).relevanceScore()).isEqualTo(0.8);
    }

    @Test
    void qualityMaxClampsNormalization() {
        var chunks = List.of(chunk("over-max", 0.5, "20"));
        var config = stubConfig(FusionStrategy.RRF, 1.0, "score", 10.0);
        var decorator = new PayloadBoostCaseRetriever(stubRetriever(chunks), config);

        var result = decorator.retrieve(RetrievalQuery.of("test"), new CorpusRef("t", "c"), 10, null);

        double expected = 0.5 * (1 + Math.min(20.0 / 10.0, 1.0) * 1.0);
        assertThat(result.get(0).relevanceScore()).isCloseTo(expected, within(0.001));
    }
}
```

Note: `TestRagConfigBuilder` may need to be created or the test may use a different config stub pattern — adapt to the existing test infrastructure in `HybridCaseRetrieverTest`. The test implementation will need to match whatever config stub pattern is already in use.

- [ ] **Step 2: Write PayloadBoostCaseRetriever**

Use `ide_create_file`:

```java
package io.casehub.neocortex.rag.runtime;

import io.casehub.neocortex.fusion.FusionStrategy;
import io.casehub.neocortex.rag.CaseRetriever;
import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.PayloadFilter;
import io.casehub.neocortex.rag.RetrievalQuery;
import io.casehub.neocortex.rag.RetrievedChunk;
import io.quarkus.arc.Unremovable;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

@Decorator
@Priority(60)
@Unremovable
public class PayloadBoostCaseRetriever implements CaseRetriever {

    private final CaseRetriever delegate;
    private final RagConfig config;

    @Inject
    PayloadBoostCaseRetriever(@Delegate @Any CaseRetriever delegate, RagConfig config) {
        this.delegate = delegate;
        this.config = config;
    }

    PayloadBoostCaseRetriever(CaseRetriever delegate, RagConfig config) {
        this.delegate = delegate;
        this.config = config;
    }

    @Override
    public List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus,
                                          int maxResults, PayloadFilter filter) {
        List<RetrievedChunk> results = delegate.retrieve(query, corpus, maxResults, filter);

        double qualityWeight = config.retrieval().weights().quality();
        if (qualityWeight <= 0) return results;
        if (config.retrieval().fusionStrategy() == FusionStrategy.CC) return results;

        Optional<String> fieldOpt = config.retrieval().qualityPayloadField();
        if (fieldOpt.isEmpty()) return results;
        String qualityField = fieldOpt.get();
        double qualityMax = config.retrieval().qualityMax();

        boolean anyBoosted = false;
        List<RetrievedChunk> boosted = new ArrayList<>(results.size());
        for (RetrievedChunk chunk : results) {
            String rawValue = chunk.metadata().get(qualityField);
            if (rawValue == null) {
                boosted.add(chunk);
                continue;
            }
            try {
                double payloadValue = Double.parseDouble(rawValue);
                double normalized = Math.min(payloadValue / qualityMax, 1.0);
                double boostedScore = chunk.relevanceScore() * (1 + normalized * qualityWeight);
                boosted.add(chunk.withRelevanceScore(boostedScore));
                anyBoosted = true;
            } catch (NumberFormatException e) {
                boosted.add(chunk);
            }
        }

        if (!anyBoosted) return results;

        boosted.sort(Comparator.comparingDouble(RetrievedChunk::relevanceScore).reversed());
        return List.copyOf(boosted);
    }
}
```

- [ ] **Step 3: Extend mapToChunks() for numeric payload**

In `HybridCaseRetriever.mapToChunks()`, use `ide_replace_member` to also extract numeric and integer payload values as string representations:

Replace the metadata extraction block inside the for loop:

```java
Map<String, String> metadata = new HashMap<>();
for (Map.Entry<String, Value> entry : payload.entrySet()) {
    if (!QdrantPointBuilder.RESERVED_PAYLOAD_KEYS.contains(entry.getKey())) {
        Value v = entry.getValue();
        if (v.hasStringValue()) {
            metadata.put(entry.getKey(), v.getStringValue());
        } else if (v.hasDoubleValue()) {
            metadata.put(entry.getKey(), String.valueOf(v.getDoubleValue()));
        } else if (v.hasIntegerValue()) {
            metadata.put(entry.getKey(), String.valueOf(v.getIntegerValue()));
        }
    }
}
```

- [ ] **Step 4: Add CC quality leg in executeConvexCombinationFusion()**

In `executeConvexCombinationFusion()`, after the BM25 leg block and before the `ScoreFusion.convexCombination()` call, add the quality leg. Use `ide_replace_member` on `executeConvexCombinationFusion`:

After the BM25 leg construction and before the return statement, insert:

```java
double qualityWeight = config.retrieval().weights().quality();
Optional<String> qualityFieldOpt = config.retrieval().qualityPayloadField();
if (qualityWeight > 0 && qualityFieldOpt.isPresent()) {
    String qualityField = qualityFieldOpt.get();
    double qualityMax = config.retrieval().qualityMax();

    java.util.Set<String> seen = new java.util.HashSet<>();
    List<RetrievedChunk> qualityItems = new ArrayList<>();
    for (var leg : legs) {
        for (var item : leg.items()) {
            if (seen.add(item.fusionKey())) {
                String rawValue = item.metadata().get(qualityField);
                if (rawValue != null) {
                    try {
                        double val = Double.parseDouble(rawValue);
                        qualityItems.add(item.withRelevanceScore(Math.min(val / qualityMax, 1.0)));
                    } catch (NumberFormatException ignored) {}
                }
            }
        }
    }
    if (!qualityItems.isEmpty()) {
        legs.add(new ScoreFusion.ScoredLeg<>(qualityItems, RetrievedChunk::relevanceScore, qualityWeight));
    }
}
```

- [ ] **Step 5: Run tests and verify**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag
```

Expected: all tests pass including new PayloadBoostCaseRetriever tests.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag/src/main/java/io/casehub/neocortex/rag/runtime/PayloadBoostCaseRetriever.java rag/src/test/java/io/casehub/neocortex/rag/runtime/PayloadBoostCaseRetrieverTest.java rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#180): payload quality boost — CC fusion leg + RRF/DBSF decorator rescore"
```

---

### Task 6: RetrievalAnalyzer query-level analytics

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/QueryQualitySignal.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/QueryFrequencyStats.java`
- Create: `rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerQueryTest.java`
- Modify: `rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java` — add three methods

**Interfaces:**
- Consumes: `RetrievalTracker.findRecords()` — existing SPI
- Produces: `RetrievalAnalyzer.lowRelevanceQueries()`, `zeroHitQueries()`, `queryFrequency()` — static methods

- [ ] **Step 1: Create value types**

Use `ide_create_file` for `QueryQualitySignal.java`:

```java
package io.casehub.neocortex.rag;

import java.time.Instant;

public record QueryQualitySignal(
        String queryText,
        double averageRelevanceScore,
        int retrievalCount,
        Instant lastSeen) {

    public QueryQualitySignal {
        if (queryText == null || queryText.isBlank())
            throw new IllegalArgumentException("queryText must not be null or blank");
        if (retrievalCount < 1)
            throw new IllegalArgumentException("retrievalCount must be positive");
        if (lastSeen == null)
            throw new IllegalArgumentException("lastSeen must not be null");
    }
}
```

Use `ide_create_file` for `QueryFrequencyStats.java`:

```java
package io.casehub.neocortex.rag;

import java.time.Instant;

public record QueryFrequencyStats(
        int count,
        double averageScore,
        Instant firstSeen,
        Instant lastSeen) {

    public QueryFrequencyStats {
        if (count < 1) throw new IllegalArgumentException("count must be positive");
        if (firstSeen == null) throw new IllegalArgumentException("firstSeen must not be null");
        if (lastSeen == null) throw new IllegalArgumentException("lastSeen must not be null");
    }
}
```

- [ ] **Step 2: Write tests**

Use `ide_create_file` for `RetrievalAnalyzerQueryTest.java`:

```java
package io.casehub.neocortex.rag;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.*;

class RetrievalAnalyzerQueryTest {

    private static final CorpusRef CORPUS = new CorpusRef("tenant", "corpus");
    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");
    private static final Instant T1 = Instant.parse("2026-01-01T01:00:00Z");
    private static final Instant T2 = Instant.parse("2026-01-01T02:00:00Z");
    private static final Instant SINCE = Instant.parse("2025-12-31T00:00:00Z");
    private static final Instant UNTIL = Instant.parse("2026-12-31T00:00:00Z");

    private static RetrievalRecord record(String queryText, Instant ts, RetrievedDocumentRef... docs) {
        return new RetrievalRecord(
            "r-" + queryText + "-" + ts.getEpochSecond(),
            RetrievalQuery.of(queryText), CORPUS,
            List.of(docs), Math.max(docs.length, 1), ts);
    }

    private static RetrievedDocumentRef doc(String id, double score) {
        return new RetrievedDocumentRef(id, score);
    }

    private static StubTracker tracker(RetrievalRecord... records) {
        return new StubTracker(List.of(records));
    }

    @Test
    void lowRelevanceQueries_filtersbelowThreshold() {
        var t = tracker(
            record("bad query", T0, doc("d1", 0.1), doc("d2", 0.2)),
            record("good query", T0, doc("d1", 0.9), doc("d2", 0.8)));

        var result = RetrievalAnalyzer.lowRelevanceQueries(t, CORPUS, SINCE, UNTIL, 0.5);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).queryText()).isEqualTo("bad query");
        assertThat(result.get(0).averageRelevanceScore()).isCloseTo(0.15, within(0.01));
    }

    @Test
    void lowRelevanceQueries_aggregatesAcrossMultipleRetrievals() {
        var t = tracker(
            record("q", T0, doc("d1", 0.2)),
            record("q", T1, doc("d1", 0.4)));

        var result = RetrievalAnalyzer.lowRelevanceQueries(t, CORPUS, SINCE, UNTIL, 0.5);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).averageRelevanceScore()).isCloseTo(0.3, within(0.01));
        assertThat(result.get(0).retrievalCount()).isEqualTo(2);
    }

    @Test
    void lowRelevanceQueries_emptyTracker_returnsEmpty() {
        var result = RetrievalAnalyzer.lowRelevanceQueries(tracker(), CORPUS, SINCE, UNTIL, 0.5);
        assertThat(result).isEmpty();
    }

    @Test
    void zeroHitQueries_findsEmptyResults() {
        var t = tracker(
            record("miss", T0),
            record("hit", T0, doc("d1", 0.9)));

        var result = RetrievalAnalyzer.zeroHitQueries(t, CORPUS, SINCE, UNTIL);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).queryText()).isEqualTo("miss");
        assertThat(result.get(0).averageRelevanceScore()).isEqualTo(0.0);
    }

    @Test
    void zeroHitQueries_multipleZeroHitsForSameQuery() {
        var t = tracker(
            record("miss", T0),
            record("miss", T1));

        var result = RetrievalAnalyzer.zeroHitQueries(t, CORPUS, SINCE, UNTIL);

        assertThat(result).hasSize(1);
        assertThat(result.get(0).retrievalCount()).isEqualTo(2);
        assertThat(result.get(0).lastSeen()).isEqualTo(T1);
    }

    @Test
    void zeroHitQueries_emptyTracker_returnsEmpty() {
        var result = RetrievalAnalyzer.zeroHitQueries(tracker(), CORPUS, SINCE, UNTIL);
        assertThat(result).isEmpty();
    }

    @Test
    void queryFrequency_countsAndScores() {
        var t = tracker(
            record("popular", T0, doc("d1", 0.9)),
            record("popular", T1, doc("d2", 0.7)),
            record("rare", T2, doc("d3", 0.5)));

        var result = RetrievalAnalyzer.queryFrequency(t, CORPUS, SINCE, UNTIL);

        assertThat(result).hasSize(2);
        assertThat(result.get("popular").count()).isEqualTo(2);
        assertThat(result.get("popular").averageScore()).isCloseTo(0.8, within(0.01));
        assertThat(result.get("popular").firstSeen()).isEqualTo(T0);
        assertThat(result.get("popular").lastSeen()).isEqualTo(T1);
        assertThat(result.get("rare").count()).isEqualTo(1);
    }

    @Test
    void queryFrequency_emptyTracker_returnsEmpty() {
        var result = RetrievalAnalyzer.queryFrequency(tracker(), CORPUS, SINCE, UNTIL);
        assertThat(result).isEmpty();
    }

    private static class StubTracker implements RetrievalTracker {
        private final List<RetrievalRecord> records;

        StubTracker(List<RetrievalRecord> records) {
            this.records = records;
        }

        @Override
        public String record(RetrievalQuery query, CorpusRef corpus, List<RetrievedChunk> results, int maxResults) {
            throw new UnsupportedOperationException();
        }

        @Override
        public void feedback(String retrievalId, String sourceDocumentId, RetrievalOutcome outcome) {
            throw new UnsupportedOperationException();
        }

        @Override
        public List<RetrievalRecord> findRecords(CorpusRef corpus, Instant since, Instant until) {
            return records.stream()
                .filter(r -> r.corpus().equals(corpus))
                .filter(r -> !r.timestamp().isBefore(since) && r.timestamp().isBefore(until))
                .toList();
        }

        @Override
        public List<RetrievalFeedback> findFeedback(CorpusRef corpus, Instant since, Instant until) {
            return List.of();
        }

        @Override
        public Set<String> findRetrievedDocumentIds(CorpusRef corpus, Instant since, Instant until) {
            return Set.of();
        }

        @Override
        public int purgeOlderThan(Instant cutoff) {
            return 0;
        }
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalAnalyzerQueryTest -Dsurefire.failIfNoSpecifiedTests=false
```

Expected: compilation failure — methods don't exist yet.

- [ ] **Step 4: Implement the three methods**

Use `ide_insert_member` on `RetrievalAnalyzer`, after `qualitySignals`:

```java
public static List<QueryQualitySignal> lowRelevanceQueries(
        RetrievalTracker tracker, CorpusRef corpus,
        Instant since, Instant until, double scoreThreshold) {

    List<RetrievalRecord> records = tracker.findRecords(corpus, since, until);
    if (records.isEmpty()) return List.of();

    Map<String, List<Double>> scoresByQuery = new HashMap<>();
    Map<String, Instant> lastSeenByQuery = new HashMap<>();

    for (RetrievalRecord r : records) {
        String qt = r.query().text();
        if (r.documents().isEmpty()) continue;
        double avg = r.documents().stream()
            .mapToDouble(RetrievedDocumentRef::relevanceScore).average().orElse(0.0);
        scoresByQuery.computeIfAbsent(qt, k -> new ArrayList<>()).add(avg);
        lastSeenByQuery.merge(qt, r.timestamp(),
            (a, b) -> a.isAfter(b) ? a : b);
    }

    List<QueryQualitySignal> result = new ArrayList<>();
    for (var entry : scoresByQuery.entrySet()) {
        List<Double> scores = entry.getValue();
        double overallAvg = scores.stream().mapToDouble(Double::doubleValue).average().orElse(0.0);
        if (overallAvg < scoreThreshold) {
            result.add(new QueryQualitySignal(
                entry.getKey(), overallAvg, scores.size(), lastSeenByQuery.get(entry.getKey())));
        }
    }
    result.sort(Comparator.comparingDouble(QueryQualitySignal::averageRelevanceScore));
    return result;
}

public static List<QueryQualitySignal> zeroHitQueries(
        RetrievalTracker tracker, CorpusRef corpus,
        Instant since, Instant until) {

    List<RetrievalRecord> records = tracker.findRecords(corpus, since, until);
    if (records.isEmpty()) return List.of();

    Map<String, Integer> countByQuery = new LinkedHashMap<>();
    Map<String, Instant> lastSeenByQuery = new HashMap<>();

    for (RetrievalRecord r : records) {
        if (r.documents().isEmpty()) {
            String qt = r.query().text();
            countByQuery.merge(qt, 1, Integer::sum);
            lastSeenByQuery.merge(qt, r.timestamp(),
                (a, b) -> a.isAfter(b) ? a : b);
        }
    }

    List<QueryQualitySignal> result = new ArrayList<>();
    for (var entry : countByQuery.entrySet()) {
        result.add(new QueryQualitySignal(
            entry.getKey(), 0.0, entry.getValue(), lastSeenByQuery.get(entry.getKey())));
    }
    return result;
}

public static Map<String, QueryFrequencyStats> queryFrequency(
        RetrievalTracker tracker, CorpusRef corpus,
        Instant since, Instant until) {

    List<RetrievalRecord> records = tracker.findRecords(corpus, since, until);
    if (records.isEmpty()) return Map.of();

    Map<String, Integer> countByQuery = new LinkedHashMap<>();
    Map<String, List<Double>> scoresByQuery = new HashMap<>();
    Map<String, Instant> firstSeenByQuery = new HashMap<>();
    Map<String, Instant> lastSeenByQuery = new HashMap<>();

    for (RetrievalRecord r : records) {
        String qt = r.query().text();
        countByQuery.merge(qt, 1, Integer::sum);
        double avg = r.documents().isEmpty() ? 0.0
            : r.documents().stream()
                .mapToDouble(RetrievedDocumentRef::relevanceScore).average().orElse(0.0);
        scoresByQuery.computeIfAbsent(qt, k -> new ArrayList<>()).add(avg);
        firstSeenByQuery.merge(qt, r.timestamp(),
            (a, b) -> a.isBefore(b) ? a : b);
        lastSeenByQuery.merge(qt, r.timestamp(),
            (a, b) -> a.isAfter(b) ? a : b);
    }

    Map<String, QueryFrequencyStats> result = new LinkedHashMap<>();
    countByQuery.entrySet().stream()
        .sorted(Map.Entry.<String, Integer>comparingByValue().reversed())
        .forEachOrdered(entry -> {
            String qt = entry.getKey();
            double avgScore = scoresByQuery.get(qt).stream()
                .mapToDouble(Double::doubleValue).average().orElse(0.0);
            result.put(qt, new QueryFrequencyStats(
                entry.getValue(), avgScore,
                firstSeenByQuery.get(qt), lastSeenByQuery.get(qt)));
        });
    return result;
}
```

- [ ] **Step 5: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalAnalyzerQueryTest
```

Expected: all tests pass.

- [ ] **Step 6: Run all rag-api tests for regression**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api
```

Expected: all tests pass (existing documentStats, unretrievedDocuments, qualitySignals tests unaffected).

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-api/src/main/java/io/casehub/neocortex/rag/QueryQualitySignal.java rag-api/src/main/java/io/casehub/neocortex/rag/QueryFrequencyStats.java rag-api/src/main/java/io/casehub/neocortex/rag/RetrievalAnalyzer.java rag-api/src/test/java/io/casehub/neocortex/rag/RetrievalAnalyzerQueryTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#179): RetrievalAnalyzer query-level analytics — low-relevance, zero-hit, frequency"
```

---

### Task 7: Full build verification

**Files:** None — verification only.

- [ ] **Step 1: Full build**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

Expected: all modules build and all tests pass.

- [ ] **Step 2: Verify no diagnostic errors across changed files**

Run `ide_diagnostics` on each changed file:
- `fusion-api/ScoreFusion.java`
- `rag/RagConfig.java`
- `rag/HybridCaseRetriever.java`
- `rag/PayloadBoostCaseRetriever.java`
- `rag-api/RetrievalAnalyzer.java`
- `memory-qdrant/QdrantCbrCaseMemoryStore.java`

- [ ] **Step 3: Update CLAUDE.md module descriptions**

Update the module descriptions in `CLAUDE.md` to reflect new capabilities:
- `fusion-api` — note weighted RRF
- `rag` — note PayloadBoostCaseRetriever, FusionWeightsConfig, client-side weighted RRF
- `rag-api` — note new query-level analytics methods and value types
