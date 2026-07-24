# Batch: Inference Flexibility, Fusion Strategy, Embedding Adapter, CBR Similarity

> **For agentic workers:** REQUIRED SUB-SKILL: Use hortora:subagent-driven-development (recommended) or hortora:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement six issues (#51, #52, #61, #104, #82, #87) on one branch — input name aliases, rank-3 SPLADE max-pool, SeparateModelEmbedder adapter, configurable fusion strategy, and CBR weighted similarity scoring.

**Architecture:** Five independent implementation units ordered by dependency: inference fixes (#51, #52) → RAG embedding adapter (#61) → fusion strategy (#104) → CBR similarity (#82+#87). Each unit is self-contained with its own test cycle.

**Tech Stack:** Java 21, Quarkus 3.32, LangChain4j 1.14.1, ONNX Runtime JVM, Qdrant 1.18 Java client

## Global Constraints

- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Module build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`
- Test: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`
- Use `mvn` not `./mvnw`
- Every commit references an issue
- TDD: write failing test first, then implement
- All SPI signature changes update all implementations in the same commit
- `inference-api` is Tier 1 (zero external deps beyond CDI annotations and Mutiny provided)
- `memory-api` is Tier 1 (zero external deps beyond CDI annotations and Mutiny provided)
- Spec: `specs/2026-07-05-batch-inference-fusion-cbr-design.md` (workspace)

---

### Task 1: Input Name Aliases (#51)

**Files:**
- Modify: `inference-runtime/src/main/java/io/casehub/neocortex/inference/runtime/ModelConfig.java`
- Modify: `inference-runtime/src/main/java/io/casehub/neocortex/inference/runtime/OnnxInferenceModel.java`
- Modify: `inference-runtime/src/test/java/io/casehub/neocortex/inference/runtime/OnnxInferenceModelTest.java`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `ModelConfig` with `inputNameOverrides` field; `OnnxInferenceModel` resolves aliases at construction

- [ ] **Step 1: Update ModelConfig to add inputNameOverrides**

Add the new field to the record, update the compact constructor and convenience constructors:

```java
public record ModelConfig(
    Path modelPath,
    Path tokenizerPath,
    int maxSequenceLength,
    int intraOpThreads,
    int interOpThreads,
    Map<String, String> inputNameOverrides
) {
    public ModelConfig {
        Objects.requireNonNull(modelPath, "modelPath must not be null");
        Objects.requireNonNull(tokenizerPath, "tokenizerPath must not be null");
        if (maxSequenceLength <= 0)
            throw new IllegalArgumentException("maxSequenceLength must be positive");
        if (intraOpThreads < 0)
            throw new IllegalArgumentException("intraOpThreads must be non-negative");
        if (interOpThreads < 0)
            throw new IllegalArgumentException("interOpThreads must be non-negative");
        inputNameOverrides = inputNameOverrides == null ? null : Map.copyOf(inputNameOverrides);
    }

    public ModelConfig(Path modelPath, Path tokenizerPath) {
        this(modelPath, tokenizerPath, 512, 0, 0, null);
    }

    public ModelConfig(Path modelPath, Path tokenizerPath, int maxSequenceLength) {
        this(modelPath, tokenizerPath, maxSequenceLength, 0, 0, null);
    }
}
```

- [ ] **Step 2: Write failing test — alias resolution accepts `wrong-inputs-model.onnx`**

The test model `wrong-inputs-model.onnx` has inputs named `tokens` and `mask`. The existing test `rejectsModelMissingInputIds` asserts this fails. Change it to assert success, and add a new test for the alias resolution:

```java
@Test
void acceptsModelWithBertInputAliases() {
    ModelConfig config = new ModelConfig(wrongInputsModel, tokenizerPath);
    try (OnnxInferenceModel model = new OnnxInferenceModel(config)) {
        InferenceOutput output = model.run(InferenceInput.of("test"));
        assertNotNull(output);
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-runtime -Dtest="OnnxInferenceModelTest#acceptsModelWithBertInputAliases"`
Expected: FAIL — constructor still rejects non-standard names.

- [ ] **Step 3: Implement alias resolution in OnnxInferenceModel constructor**

Add a static alias table and resolution method. Store resolved names as instance fields. Update `run()` and `runBatch()` to use the resolved names instead of hardcoded strings.

Alias table:
```java
private static final Map<String, List<String>> INPUT_ALIASES = Map.of(
    "input_ids", List.of("tokens", "input.1"),
    "attention_mask", List.of("input_mask", "mask", "input.2"),
    "token_type_ids", List.of("segment_ids", "input.3")
);
```

Resolution: check overrides first (from `ModelConfig.inputNameOverrides()`), then canonical name, then aliases. Store resolved names in `inputIdsName`, `attentionMaskName`, `tokenTypeIdsName` fields.

Replace all hardcoded `"input_ids"`, `"attention_mask"`, `"token_type_ids"` in `run()` and `runBatch()` inputMap construction with the resolved field names.

- [ ] **Step 4: Run tests to verify alias resolution works**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-runtime`
Expected: All tests pass. The `wrong-inputs-model.onnx` test now succeeds via alias resolution.

- [ ] **Step 5: Write test for explicit overrides via ModelConfig**

```java
@Test
void acceptsExplicitInputNameOverrides() {
    ModelConfig config = new ModelConfig(wrongInputsModel, tokenizerPath, 512, 0, 0,
        Map.of("input_ids", "tokens", "attention_mask", "mask"));
    try (OnnxInferenceModel model = new OnnxInferenceModel(config)) {
        InferenceOutput output = model.run(InferenceInput.of("test"));
        assertNotNull(output);
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-runtime -Dtest="OnnxInferenceModelTest#acceptsExplicitInputNameOverrides"`
Expected: PASS (overrides take precedence).

- [ ] **Step 6: Write test for unresolvable input names**

```java
@Test
void rejectsModelWithUnknownInputNames() {
    // Create a model config pointing to a model with completely custom names
    // that don't match any alias. Use the wrong-inputs model but with
    // names that aren't in the alias table by overriding to wrong values.
    ModelConfig config = new ModelConfig(wrongInputsModel, tokenizerPath, 512, 0, 0,
        Map.of("input_ids", "nonexistent_name"));
    assertThrows(ModelLoadException.class, () -> new OnnxInferenceModel(config));
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-runtime`
Expected: All pass.

- [ ] **Step 7: Build full module to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl inference-runtime`
Expected: BUILD SUCCESS

- [ ] **Step 8: Commit**

```
feat(#51): input name alias resolution in OnnxInferenceModel

Static alias table resolves BERT naming conventions (input_mask,
segment_ids) and ONNX export defaults (input.1, input.2). ModelConfig
gains inputNameOverrides for fully custom names.
```

---

### Task 2: Rank-3 SPLADE Max-Pool Reduction (#52)

**Files:**
- Modify: `inference-splade/src/main/java/io/casehub/neocortex/inference/splade/SparseEmbedder.java`
- Modify: `inference-splade/src/test/java/io/casehub/neocortex/inference/splade/SparseEmbedderTest.java`

**Interfaces:**
- Consumes: `InferenceModel` (unchanged), `InferenceOutput.output(name)` returning `float[][]`
- Produces: `SparseEmbedder` that accepts rank-3 SPLADE models and applies max-pool reduction

- [ ] **Step 1: Write failing test — rank-3 output produces correct sparse map**

Create a stub `InferenceModel` that returns rank-3 output (`float[seq_len][vocab_size]`). Verify that `SparseEmbedder.embed()` max-pools across the sequence dimension and produces the expected sparse map.

```java
@Nested
class Rank3Output {
    @Test
    void maxPoolsAcrossSequenceDimension() {
        // 2 tokens, vocab size 4. Max-pool should take max across tokens.
        float[][] rank3Output = {
            {0.0f, 1.5f, 0.0f, 2.0f},  // token 0
            {3.0f, 0.0f, 0.5f, 0.0f}   // token 1
        };
        // After max-pool: {3.0, 1.5, 0.5, 2.0}
        // After logSaturate (log1p of max(0,x)): log1p(3.0)≈1.386, log1p(1.5)≈0.916,
        //   log1p(0.5)≈0.405, log1p(2.0)≈1.099
        // All above default threshold 0.01
        InferenceModel stubModel = rank3StubModel(rank3Output);
        SparseEmbedder embedder = new SparseEmbedder(stubModel);
        Map<Integer, Float> result = embedder.embed("test");

        assertEquals(4, result.size());
        assertEquals((float) Math.log1p(3.0f), result.get(0), 1e-5f);
        assertEquals((float) Math.log1p(1.5f), result.get(1), 1e-5f);
        assertEquals((float) Math.log1p(0.5f), result.get(2), 1e-5f);
        assertEquals((float) Math.log1p(2.0f), result.get(3), 1e-5f);
    }
}
```

The `rank3StubModel` helper returns an `InferenceModel` whose `run()` produces `InferenceOutput` with a single output named `"output"` containing the given `float[][]`, and `outputSize()` returns `OptionalInt.empty()`.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-splade -Dtest="SparseEmbedderTest$Rank3Output#maxPoolsAcrossSequenceDimension"`
Expected: FAIL — constructor rejects model because `outputSize()` is empty.

- [ ] **Step 2: Implement max-pool in SparseEmbedder**

Replace the constructor validation and embed/embedBatch methods:

1. Remove `model.outputSize().orElseThrow(...)` — replace with single-output validation:
```java
if (model.run(InferenceInput.of("probe")).outputNames().size() != 1) {
    throw new IllegalArgumentException("SparseEmbedder requires a single-output model");
}
```

Actually, probing at construction time is expensive. Instead, validate lazily on first `embed()` call, or validate without running by checking `outputSize()` presence OR falling through to runtime shape detection. The simplest correct approach: remove the outputSize check entirely and let the single-output assumption be validated at runtime via `outputNames().size()`.

2. Replace `output.values()` calls with shape-aware extraction:

```java
private float[] extractSparseVector(InferenceOutput output) {
    String name = output.outputNames().iterator().next();
    float[][] matrix = output.output(name);
    if (matrix.length == 1) {
        return matrix[0];  // rank-2: [1][vocab] → [vocab]
    }
    return maxPool(matrix);  // rank-3: [seq][vocab] → [vocab]
}

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

3. Update `embed()`: `return logSaturate(extractSparseVector(output));`
4. Update `embedBatch()`: same pattern per output in the batch.

- [ ] **Step 3: Run tests to verify rank-3 and existing rank-2 both work**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-splade`
Expected: All tests pass — existing rank-2 tests unchanged, new rank-3 test passes.

- [ ] **Step 4: Write batch rank-3 test**

```java
@Test
void batchMaxPoolsEachSampleIndependently() {
    InferenceModel stubModel = rank3BatchStubModel(/* two samples with different seq lengths */);
    SparseEmbedder embedder = new SparseEmbedder(stubModel);
    List<Map<Integer, Float>> results = embedder.embedBatch(List.of("a", "b"));
    assertEquals(2, results.size());
    // verify each sample's sparse map independently
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl inference-splade`
Expected: PASS

- [ ] **Step 5: Build full module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl inference-splade`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```
feat(#52): rank-3 SPLADE max-pool reduction in SparseEmbedder

SparseEmbedder now handles both rank-2 [1, vocab] and rank-3
[seq, vocab] model outputs. Rank-3 outputs are max-pooled across
the sequence dimension before log-saturation. The outputSize()
construction gate is removed.
```

---

### Task 3: SeparateModelEmbedder + CDI Wiring (#61)

**Files:**
- Create: `rag/src/main/java/io/casehub/neocortex/rag/runtime/SeparateModelEmbedder.java`
- Create: `rag/src/main/java/io/casehub/neocortex/rag/runtime/MultiModalEmbedderProducer.java`
- Create: `rag/src/test/java/io/casehub/neocortex/rag/runtime/SeparateModelEmbedderTest.java`
- Modify: `inference-api/src/main/java/io/casehub/neocortex/inference/MatryoshkaMultiModalEmbedder.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/RagBeanProducer.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/ReactiveRagBeanProducer.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/RagConfig.java`

**Interfaces:**
- Consumes: `MultiModalEmbedder` (interface), `EmbeddingModel` (LangChain4j), `SparseEmbedder` (task 2)
- Produces: `SeparateModelEmbedder implements MultiModalEmbedder`, `MultiModalEmbedderProducer` CDI bean, `MatryoshkaMultiModalEmbedder.wrapIfNeeded()` static method

- [ ] **Step 1: Write failing test for SeparateModelEmbedder dense-only**

```java
class SeparateModelEmbedderTest {
    @Test
    void denseOnlyEmbed() {
        EmbeddingModel denseModel = text -> Response.from(Embedding.from(new float[]{1f, 2f, 3f}));
        SeparateModelEmbedder embedder = new SeparateModelEmbedder(denseModel, 512);

        MultiModalEmbedding result = embedder.embed("test");

        assertArrayEquals(new float[]{1f, 2f, 3f}, result.dense(), 1e-5f);
        assertNull(result.sparse());
        assertNull(result.colbert());
        assertEquals(Set.of(EmbeddingMode.DENSE), embedder.supportedModes());
        assertEquals(3, embedder.denseDimension());
        assertTrue(embedder.colbertDimension().isEmpty());
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest="SeparateModelEmbedderTest#denseOnlyEmbed"`
Expected: FAIL — class does not exist.

- [ ] **Step 2: Implement SeparateModelEmbedder**

```java
package io.casehub.neocortex.rag.runtime;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import io.casehub.neocortex.inference.EmbeddingMode;
import io.casehub.neocortex.inference.MultiModalEmbedder;
import io.casehub.neocortex.inference.MultiModalEmbedding;
import io.casehub.neocortex.inference.splade.SparseEmbedder;

import java.util.*;

public final class SeparateModelEmbedder implements MultiModalEmbedder {

    private final EmbeddingModel denseModel;
    private final SparseEmbedder sparseEmbedder;
    private final int maxSequenceLength;
    private final Set<EmbeddingMode> modes;

    public SeparateModelEmbedder(EmbeddingModel denseModel, int maxSequenceLength) {
        this(denseModel, null, maxSequenceLength);
    }

    public SeparateModelEmbedder(EmbeddingModel denseModel, SparseEmbedder sparseEmbedder,
                                  int maxSequenceLength) {
        this.denseModel = Objects.requireNonNull(denseModel, "denseModel");
        this.sparseEmbedder = sparseEmbedder;
        if (maxSequenceLength <= 0)
            throw new IllegalArgumentException("maxSequenceLength must be positive");
        this.maxSequenceLength = maxSequenceLength;
        this.modes = sparseEmbedder != null
            ? Set.of(EmbeddingMode.DENSE, EmbeddingMode.SPARSE)
            : Set.of(EmbeddingMode.DENSE);
    }

    @Override
    public MultiModalEmbedding embed(String text) {
        float[] dense = denseModel.embed(text).content().vector();
        Map<Integer, Float> sparse = sparseEmbedder != null ? sparseEmbedder.embed(text) : null;
        return new MultiModalEmbedding(dense, sparse, null);
    }

    @Override
    public List<MultiModalEmbedding> embedBatch(List<String> texts) {
        List<TextSegment> segments = texts.stream().map(TextSegment::from).toList();
        Response<List<Embedding>> denseResponse = denseModel.embedAll(segments);
        List<Map<Integer, Float>> sparseResults = sparseEmbedder != null
            ? sparseEmbedder.embedBatch(texts) : null;

        List<MultiModalEmbedding> results = new ArrayList<>(texts.size());
        for (int i = 0; i < texts.size(); i++) {
            float[] dense = denseResponse.content().get(i).vector();
            Map<Integer, Float> sparse = sparseResults != null ? sparseResults.get(i) : null;
            results.add(new MultiModalEmbedding(dense, sparse, null));
        }
        return List.copyOf(results);
    }

    @Override public Set<EmbeddingMode> supportedModes() { return modes; }
    @Override public int denseDimension() { return denseModel.dimension(); }
    @Override public OptionalInt colbertDimension() { return OptionalInt.empty(); }
    @Override public int maxSequenceLength() { return maxSequenceLength; }
}
```

- [ ] **Step 3: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest="SeparateModelEmbedderTest"`
Expected: PASS

- [ ] **Step 4: Write test for dense+sparse mode**

```java
@Test
void denseAndSparseEmbed() {
    EmbeddingModel denseModel = text -> Response.from(Embedding.from(new float[]{1f, 2f}));
    InferenceModel sparseModel = rank2StubModel(new float[]{0f, 0.5f, 0f, 2.0f});
    SparseEmbedder sparse = new SparseEmbedder(sparseModel);

    SeparateModelEmbedder embedder = new SeparateModelEmbedder(denseModel, sparse, 512);

    MultiModalEmbedding result = embedder.embed("test");
    assertArrayEquals(new float[]{1f, 2f}, result.dense(), 1e-5f);
    assertNotNull(result.sparse());
    assertEquals(Set.of(EmbeddingMode.DENSE, EmbeddingMode.SPARSE), embedder.supportedModes());
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest="SeparateModelEmbedderTest"`
Expected: PASS

- [ ] **Step 5: Add `wrapIfNeeded()` to MatryoshkaMultiModalEmbedder**

```java
public static MultiModalEmbedder wrapIfNeeded(MultiModalEmbedder embedder, OptionalInt dimension) {
    if (dimension.isPresent() && !(embedder instanceof MatryoshkaMultiModalEmbedder)) {
        return new MatryoshkaMultiModalEmbedder(embedder, dimension.getAsInt());
    }
    return embedder;
}
```

- [ ] **Step 6: Update RagBeanProducer and ReactiveRagBeanProducer to use `wrapIfNeeded()`**

Replace both `effectiveEmbedder()` implementations:

```java
private MultiModalEmbedder effectiveEmbedder() {
    return MatryoshkaMultiModalEmbedder.wrapIfNeeded(embedder,
        config.matryoshka().dimension());
}
```

- [ ] **Step 7: Create MultiModalEmbedderProducer CDI bean**

```java
package io.casehub.neocortex.rag.runtime;

@ApplicationScoped
public class MultiModalEmbedderProducer {

    @Produces @DefaultBean @ApplicationScoped
    @IfBuildProperty(name = "casehub.rag.embedder.enabled", stringValue = "true",
                     enableIfMissing = true)
    MultiModalEmbedder separateModelEmbedder(
            Instance<EmbeddingModel> denseModel,
            Instance<SparseEmbedder> sparseEmbedder,
            RagConfig config) {
        if (denseModel.isUnsatisfied()) {
            throw new IllegalStateException(
                "No EmbeddingModel available — provide a LangChain4j EmbeddingModel bean "
                + "or configure BGE-M3. Set casehub.rag.embedder.enabled=false to disable RAG.");
        }
        int maxSeqLen = config.maxSequenceLength().orElse(512);
        if (sparseEmbedder.isResolvable()) {
            return new SeparateModelEmbedder(denseModel.get(), sparseEmbedder.get(), maxSeqLen);
        }
        return new SeparateModelEmbedder(denseModel.get(), maxSeqLen);
    }
}
```

- [ ] **Step 8: Add `maxSequenceLength()` to RagConfig**

In `RagConfig.java`, add:
```java
Optional<Integer> maxSequenceLength();
```

Update `RagTestFixtures` stub config to include this method.

- [ ] **Step 9: Build rag module and verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl inference-api,rag`
Expected: BUILD SUCCESS

- [ ] **Step 10: Commit**

```
feat(#61): SeparateModelEmbedder — MultiModalEmbedder adapter for
EmbeddingModel + optional SparseEmbedder

Bridges LangChain4j EmbeddingModel (dense) and optional SparseEmbedder
(sparse) into the MultiModalEmbedder contract. @DefaultBean CDI producer
in MultiModalEmbedderProducer, displaced by BgeM3 when configured.
Matryoshka wrapping consolidated to wrapIfNeeded() static method.
```

---

### Task 4: Configurable Fusion Strategy (#104)

**Files:**
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/FusionStrategy.java`
- Create: `rag-api/src/main/java/io/casehub/neocortex/rag/ConvexCombinationFusion.java`
- Create: `rag-api/src/test/java/io/casehub/neocortex/rag/ConvexCombinationFusionTest.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/RagConfig.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/test/java/io/casehub/neocortex/rag/runtime/RagTestFixtures.java`
- Modify: `rag/src/test/java/io/casehub/neocortex/rag/runtime/HybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/neocortex/rag/runtime/ReactiveHybridCaseRetrieverTest.java`

**Interfaces:**
- Consumes: `RetrievedChunk`, `RelevanceGrade`, `RrfFusion` (existing pattern reference)
- Produces: `FusionStrategy` enum, `ConvexCombinationFusion.fuse()`, config properties `fusionStrategy`, `ccWeights`

- [ ] **Step 1: Create FusionStrategy enum in rag-api**

```java
package io.casehub.neocortex.rag;

public enum FusionStrategy { RRF, DBSF, CC }
```

- [ ] **Step 2: Write failing tests for ConvexCombinationFusion**

```java
class ConvexCombinationFusionTest {
    @Test
    void fusesTwoLegsWithWeights() {
        var dense = List.of(chunk("a", 0.9), chunk("b", 0.7), chunk("c", 0.5));
        var sparse = List.of(chunk("b", 0.8), chunk("d", 0.6), chunk("a", 0.4));
        var legs = List.of(
            new ConvexCombinationFusion.ScoredLeg(dense, 0.6),
            new ConvexCombinationFusion.ScoredLeg(sparse, 0.4));

        List<RetrievedChunk> result = ConvexCombinationFusion.fuse(legs, 10);

        // "b" is in both legs — should rank highest
        assertEquals("b", result.get(0).sourceDocumentId());
        assertTrue(result.get(0).relevanceScore() > result.get(1).relevanceScore());
    }

    @Test
    void renormalizesWeightsForAbsentLegs() {
        // Only one leg present out of configured weights — weight should be 1.0
        var dense = List.of(chunk("a", 0.9));
        var legs = List.of(new ConvexCombinationFusion.ScoredLeg(dense, 0.5));

        List<RetrievedChunk> result = ConvexCombinationFusion.fuse(legs, 10);
        assertEquals(1.0, result.get(0).relevanceScore(), 1e-5);
    }

    @Test
    void handlesEqualScoresWithoutNaN() {
        var leg = List.of(chunk("a", 0.5), chunk("b", 0.5));
        var legs = List.of(new ConvexCombinationFusion.ScoredLeg(leg, 1.0));

        List<RetrievedChunk> result = ConvexCombinationFusion.fuse(legs, 10);
        assertFalse(Double.isNaN(result.get(0).relevanceScore()));
        assertEquals(1.0, result.get(0).relevanceScore(), 1e-5);
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest="ConvexCombinationFusionTest"`
Expected: FAIL — class does not exist.

- [ ] **Step 3: Implement ConvexCombinationFusion**

```java
package io.casehub.neocortex.rag;

import java.util.*;

public final class ConvexCombinationFusion {

    public record ScoredLeg(List<RetrievedChunk> chunks, double weight) {
        public ScoredLeg {
            Objects.requireNonNull(chunks, "chunks");
            if (weight < 0) throw new IllegalArgumentException("weight must be non-negative");
        }
    }

    private ConvexCombinationFusion() {}

    public static List<RetrievedChunk> fuse(List<ScoredLeg> legs, int maxResults) {
        if (legs.isEmpty()) return List.of();

        // Renormalize weights for active legs
        double totalWeight = legs.stream().mapToDouble(ScoredLeg::weight).sum();
        if (totalWeight <= 0) return List.of();

        Map<String, Double> scores = new LinkedHashMap<>();
        Map<String, RetrievedChunk> chunks = new LinkedHashMap<>();

        for (ScoredLeg leg : legs) {
            double normalizedWeight = leg.weight() / totalWeight;
            double[] minMax = minMax(leg.chunks());
            double min = minMax[0], max = minMax[1];
            double range = max - min;

            for (RetrievedChunk chunk : leg.chunks()) {
                String key = dedupKey(chunk);
                double normalized = range > 0
                    ? (chunk.relevanceScore() - min) / range
                    : 1.0;  // all equal → all get 1.0
                scores.merge(key, normalizedWeight * normalized, Double::sum);

                chunks.merge(key, chunk, (existing, incoming) ->
                    betterGrade(existing.grade(), incoming.grade()) == incoming.grade()
                        ? existing.withGrade(incoming.grade()) : existing);
            }
        }

        List<Map.Entry<String, Double>> sorted = new ArrayList<>(scores.entrySet());
        sorted.sort(Map.Entry.<String, Double>comparingByValue().reversed());

        List<RetrievedChunk> result = new ArrayList<>(Math.min(sorted.size(), maxResults));
        for (int i = 0; i < Math.min(sorted.size(), maxResults); i++) {
            Map.Entry<String, Double> entry = sorted.get(i);
            RetrievedChunk original = chunks.get(entry.getKey());
            result.add(new RetrievedChunk(original.content(), original.sourceDocumentId(),
                entry.getValue(), original.metadata(), original.grade()));
        }
        return List.copyOf(result);
    }

    // ... private helpers: dedupKey, betterGrade, gradeRank (same as RrfFusion), minMax
}
```

- [ ] **Step 4: Run CC fusion tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest="ConvexCombinationFusionTest"`
Expected: PASS

- [ ] **Step 5: Add config properties to RagConfig**

Add `fusionStrategy()`, `CcWeightsConfig` interface to `RagConfig.RetrievalConfig`. Update `RagTestFixtures` stub config to return defaults.

- [ ] **Step 6: Implement strategy switch in HybridCaseRetriever**

In `retrieve()`, replace the hardcoded `QueryFactory.rrf(...)` calls with a switch on `config.retrieval().fusionStrategy()`:

- `RRF` → current behavior (unchanged)
- `DBSF` → replace `QueryFactory.rrf(...)` with `QueryFactory.fusion(Fusion.DBSF)`
- `CC` → execute each leg as a separate `QueryPoints`, collect results, call `ConvexCombinationFusion.fuse()`. Skip ColBERT reranking when CC is active.

- [ ] **Step 7: Implement same switch in ReactiveHybridCaseRetriever**

Mirror the blocking retriever changes with reactive Uni composition.

- [ ] **Step 8: Run all retriever tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag`
Expected: All existing tests pass (default strategy is RRF — no behavior change).

- [ ] **Step 9: Build rag-api and rag modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-api,rag`
Expected: BUILD SUCCESS

- [ ] **Step 10: Commit**

```
feat(#104): configurable fusion strategy — RRF, DBSF, Convex
Combination in HybridCaseRetriever

FusionStrategy enum (RRF/DBSF/CC) in rag-api. CC uses client-side
ConvexCombinationFusion with per-leg weights and min-max normalization.
RRF/DBSF remain server-side via Qdrant prefetch. ColBERT reranking
excluded from CC path. DBSF added as one-line swap (scope note in spec).
```

---

### Task 5: CBR Weighted Similarity (#82 + #87)

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- Create: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrQueryTest.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslator.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/CbrQueryTranslatorTest.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Consumes: `CbrFeatureSchema`, `FeatureField`, `ScoredCbrCase`, `CbrCaseMemoryStore`
- Produces: `CbrQuery` with `weights` + `vectorWeight`, `CbrSimilarityScorer.score()` + `compositeScore()`

- [ ] **Step 1: Update CbrQuery record with new fields**

```java
public record CbrQuery(
    String tenantId,
    MemoryDomain domain,
    String caseType,
    Map<String, Object> features,
    Map<String, Double> weights,
    int topK,
    double minSimilarity,
    Instant notBefore,
    String problem,
    double vectorWeight
) {
    public CbrQuery {
        Objects.requireNonNull(tenantId, "tenantId required");
        Objects.requireNonNull(domain, "domain required");
        Objects.requireNonNull(caseType, "caseType required");
        Objects.requireNonNull(features, "features required");
        features = Map.copyOf(features);
        Objects.requireNonNull(weights, "weights required");
        weights = Map.copyOf(weights);
        if (topK < 1) throw new IllegalArgumentException("topK must be >= 1, got: " + topK);
        if (minSimilarity < 0.0 || minSimilarity > 1.0)
            throw new IllegalArgumentException("minSimilarity must be in [0,1], got: " + minSimilarity);
        if (vectorWeight < 0.0 || vectorWeight > 1.0)
            throw new IllegalArgumentException("vectorWeight must be in [0,1], got: " + vectorWeight);
        for (Map.Entry<String, Double> w : weights.entrySet()) {
            if (w.getValue() < 0)
                throw new IllegalArgumentException("weight for '" + w.getKey() + "' must be non-negative");
        }
        if (problem != null && problem.isBlank())
            throw new IllegalArgumentException("problem must not be blank when provided");
    }

    public static CbrQuery of(String tenantId, MemoryDomain domain,
                               String caseType, Map<String, Object> features, int topK) {
        return new CbrQuery(tenantId, domain, caseType, features, Map.of(), topK,
                            0.0, null, null, 0.5);
    }

    public CbrQuery withProblem(String problem) {
        return new CbrQuery(tenantId, domain, caseType, features, weights, topK,
                            minSimilarity, notBefore, problem, vectorWeight);
    }

    public CbrQuery withMinSimilarity(double minSimilarity) {
        return new CbrQuery(tenantId, domain, caseType, features, weights, topK,
                            minSimilarity, notBefore, problem, vectorWeight);
    }

    public CbrQuery withNotBefore(Instant notBefore) {
        return new CbrQuery(tenantId, domain, caseType, features, weights, topK,
                            minSimilarity, notBefore, problem, vectorWeight);
    }

    public CbrQuery withWeights(Map<String, Double> weights) {
        return new CbrQuery(tenantId, domain, caseType, features, weights, topK,
                            minSimilarity, notBefore, problem, vectorWeight);
    }

    public CbrQuery withWeight(String field, double weight) {
        Map<String, Double> newWeights = new java.util.HashMap<>(weights);
        newWeights.put(field, weight);
        return withWeights(newWeights);
    }

    public CbrQuery withVectorWeight(double vectorWeight) {
        return new CbrQuery(tenantId, domain, caseType, features, weights, topK,
                            minSimilarity, notBefore, problem, vectorWeight);
    }
}
```

- [ ] **Step 2: Fix all compilation errors from CbrQuery signature change**

Update all callers of the 8-arg `CbrQuery` constructor — the contract test, CbrQueryTest, CbrQueryTranslatorTest, and any other direct constructors — to pass the two new fields (`weights=Map.of()`, `vectorWeight=0.5`). The `CbrQuery.of()` factory handles this automatically.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl memory-api,memory-qdrant,memory-cbr-inmem,memory-testing`
Expected: COMPILE SUCCESS

- [ ] **Step 3: Write failing tests for CbrSimilarityScorer**

```java
class CbrSimilarityScorerTest {
    static final CbrFeatureSchema SCHEMA = CbrFeatureSchema.of("test",
        FeatureField.categorical("color"),
        FeatureField.numeric("score", 0.0, 100.0),
        FeatureField.text("label"));

    @Test
    void categoricalExactMatch() {
        double sim = CbrSimilarityScorer.score(
            Map.of("color", "red"), Map.of("color", "red"), Map.of(), SCHEMA);
        assertEquals(1.0, sim, 1e-9);
    }

    @Test
    void categoricalMismatch() {
        double sim = CbrSimilarityScorer.score(
            Map.of("color", "red"), Map.of("color", "blue"), Map.of(), SCHEMA);
        assertEquals(0.0, sim, 1e-9);
    }

    @Test
    void numericLinearDecay() {
        double sim = CbrSimilarityScorer.score(
            Map.of("score", 80.0), Map.of("score", 60.0), Map.of(), SCHEMA);
        // |80-60| / (100-0) = 0.2, so sim = 1.0 - 0.2 = 0.8
        assertEquals(0.8, sim, 1e-9);
    }

    @Test
    void weightedScoring() {
        // color matches (sim=1.0), score differs (sim=0.8)
        // weight color=2.0, score=1.0
        // weighted = (2*1.0 + 1*0.8) / (2+1) = 2.8/3 ≈ 0.933
        double sim = CbrSimilarityScorer.score(
            Map.of("color", "red", "score", 80.0),
            Map.of("color", "red", "score", 60.0),
            Map.of("color", 2.0, "score", 1.0),
            SCHEMA);
        assertEquals(2.8 / 3.0, sim, 1e-9);
    }

    @Test
    void emptyQueryFeaturesReturnsOne() {
        double sim = CbrSimilarityScorer.score(Map.of(), Map.of("color", "red"), Map.of(), SCHEMA);
        assertEquals(1.0, sim, 1e-9);
    }

    @Test
    void nullSchemaReturnsOne() {
        double sim = CbrSimilarityScorer.score(
            Map.of("color", "red"), Map.of("color", "red"), Map.of(), null);
        assertEquals(1.0, sim, 1e-9);
    }

    @Test
    void missingFeatureInCaseScoresZero() {
        double sim = CbrSimilarityScorer.score(
            Map.of("color", "red"), Map.of(), Map.of(), SCHEMA);
        assertEquals(0.0, sim, 1e-9);
    }

    @Test
    void compositeScoreFormula() {
        double composite = CbrSimilarityScorer.compositeScore(0.8, 0.6, 0.3);
        // 0.3 * 0.6 + 0.7 * 0.8 = 0.18 + 0.56 = 0.74
        assertEquals(0.74, composite, 1e-9);
    }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="CbrSimilarityScorerTest"`
Expected: FAIL — class does not exist.

- [ ] **Step 4: Implement CbrSimilarityScorer**

```java
package io.casehub.neocortex.memory.cbr;

import java.util.Map;

public final class CbrSimilarityScorer {

    private CbrSimilarityScorer() {}

    public static double score(Map<String, Object> queryFeatures,
                                Map<String, Object> caseFeatures,
                                Map<String, Double> weights,
                                CbrFeatureSchema schema) {
        if (queryFeatures.isEmpty()) return 1.0;
        if (schema == null) return 1.0;

        double weightedSum = 0.0;
        double totalWeight = 0.0;

        for (Map.Entry<String, Object> entry : queryFeatures.entrySet()) {
            FeatureField field = findField(schema, entry.getKey());
            if (field == null) continue;

            double weight = weights.getOrDefault(entry.getKey(), 1.0);
            Object caseValue = caseFeatures.get(entry.getKey());
            double localSim = caseValue == null ? 0.0
                : localSimilarity(field, entry.getValue(), caseValue);

            weightedSum += weight * localSim;
            totalWeight += weight;
        }

        return totalWeight > 0 ? weightedSum / totalWeight : 1.0;
    }

    public static double compositeScore(double featureScore, double vectorScore,
                                         double vectorWeight) {
        return vectorWeight * vectorScore + (1.0 - vectorWeight) * featureScore;
    }

    private static double localSimilarity(FeatureField field, Object queryVal, Object caseVal) {
        if (field instanceof FeatureField.Numeric n) {
            return numericSimilarity(n, queryVal, caseVal);
        }
        // Categorical and Text: exact match
        return queryVal.equals(caseVal) ? 1.0 : 0.0;
    }

    private static double numericSimilarity(FeatureField.Numeric field,
                                             Object queryVal, Object caseVal) {
        double range = field.max() - field.min();
        if (range <= 0) return queryVal.equals(caseVal) ? 1.0 : 0.0;

        double caseNum = ((Number) caseVal).doubleValue();

        if (queryVal instanceof NumericRange nr) {
            if (caseNum >= nr.min() && caseNum <= nr.max()) return 1.0;
            double dist = caseNum < nr.min() ? nr.min() - caseNum : caseNum - nr.max();
            return Math.max(0.0, 1.0 - dist / range);
        }

        double queryNum = ((Number) queryVal).doubleValue();
        return Math.max(0.0, 1.0 - Math.abs(queryNum - caseNum) / range);
    }

    private static FeatureField findField(CbrFeatureSchema schema, String name) {
        for (FeatureField f : schema.fields()) {
            if (f.name().equals(name)) return f;
        }
        return null;
    }
}
```

- [ ] **Step 5: Run scorer tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest="CbrSimilarityScorerTest"`
Expected: PASS

- [ ] **Step 6: Update CbrQueryTranslator — identity-only filter**

Add a new method `toIdentityFilter(CbrQuery query)` that builds `must` conditions for tenant, domain, caseType, and notBefore only — no feature conditions. The existing `toFilter()` remains for backward compatibility during the transition but is no longer called by the stores.

- [ ] **Step 7: Update QdrantCbrCaseMemoryStore.retrieveSimilar()**

Replace the current flow with the new scoring flow per spec §4.3:
1. Build identity-only filter via `CbrQueryTranslator.toIdentityFilter(query)`
2. Dense search path: `SearchPoints` with oversample factor (`topK * 3`)
3. Filter-only path: `ScrollPoints` with `Math.max(topK, 200)` limit
4. Reconstruct cases from payload
5. Compute `CbrSimilarityScorer.score()` per case
6. Compute composite score with vector similarity if dense search was active
7. Filter by `minSimilarity`, sort descending, take `topK`

- [ ] **Step 8: Update InMemoryCbrCaseMemoryStore.retrieveSimilar()**

Replace `matchesFeatures()` boolean with `CbrSimilarityScorer.score()`. Sort by score, apply `minSimilarity` threshold, take `topK`. Remove the old `matchesFeatures()` method.

- [ ] **Step 9: Update contract tests for graded scoring**

Update existing tests that relied on boolean filtering to verify graded scoring:
- `categoricalExactMatch` → verify matching cases score higher than non-matching
- `numericRange` tests → verify within-range scores higher than outside

Add new tests per spec §4.6:
- `weightedScoringProducesExpectedRanking`
- `defaultWeightsAreUniform`
- `numericSimilarityDecay`
- `minSimilarityThresholdOnCompositeScore`
- `missingFeatureScoresZero`
- `emptyFeaturesScoresOne`

- [ ] **Step 10: Build all memory modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api,memory,memory-testing,memory-cbr-inmem,memory-qdrant`
Expected: BUILD SUCCESS

- [ ] **Step 11: Commit**

```
feat(#82,#87): CBR weighted similarity — per-field local similarity
functions with configurable weights

CbrQuery gains weights and vectorWeight fields. CbrSimilarityScorer
computes weighted composite similarity using field-type-derived local
functions (categorical exact match, numeric linear decay, text exact
match). Features move from hard Qdrant payload filters to client-side
graded scoring. Identity fields (tenant, domain, caseType, notBefore)
remain as hard filters.
```

---

### Task 6: Full Integration Build + Cross-Module Verification

**Files:**
- All modules

**Interfaces:**
- Consumes: all previous tasks
- Produces: green full build

- [ ] **Step 1: Full build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile and all tests pass.

- [ ] **Step 2: Verify example modules compile (smoke profile)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -Pexamples-smoke`
Expected: BUILD SUCCESS — examples compile against updated APIs.

- [ ] **Step 3: Run IntelliJ diagnostics on changed files**

Use `ide_diagnostics` to check for warnings/errors on the key new files:
- `SeparateModelEmbedder.java`
- `ConvexCombinationFusion.java`
- `CbrSimilarityScorer.java`
- `MultiModalEmbedderProducer.java`

- [ ] **Step 4: Protocol compliance review**

Verify against protocols:
- `module-tier-structure` — CbrSimilarityScorer in Tier 1, SeparateModelEmbedder in Tier 3
- `persistence-backend-cdi-priority` — CDI ladder unchanged
- `spi-signature-change-all-impls-same-commit` — CbrQuery change + all impl updates in one commit
- `library-jar-annotation-only-deps` — no Quarkus extension deps in library JARs

- [ ] **Step 5: No commit — this is verification only**
