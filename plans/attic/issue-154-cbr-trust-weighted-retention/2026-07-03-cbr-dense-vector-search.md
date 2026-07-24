# CBR Dense Vector Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dense vector search and minSimilarity wiring to CBR retrieval, returning scored results.

**Architecture:** CbrQuery gains a `problem` field for query-side embedding. QdrantCbrCaseMemoryStore branches between `searchAsync` (dense + filter) and `scrollAsync` (filter-only) based on embedding model and problem text availability. All `retrieveSimilar()` calls return `ScoredCbrCase<C>` wrapping the case with its similarity score.

**Tech Stack:** Java 21, Qdrant Java client 1.18.1, LangChain4j EmbeddingModel SPI, Mutiny (reactive)

## Global Constraints

- Java 21 language level on Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All records validate in compact constructors
- Nullable fields use `null`, not Optional
- `Map.copyOf()` on all map fields in compact constructors
- Breaking changes are acceptable — no backward-compatibility shims

---

### Task 1: API Evolution — ScoredCbrCase, CbrQuery.problem, SPI + All Implementations

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ScoredCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ReactiveCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/BlockingToReactiveCbrBridge.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Test: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Produces: `ScoredCbrCase<C extends CbrCase>(C cbrCase, double score)` — used by all tasks
- Produces: `CbrQuery.problem()` — used by Task 2 for dense search branching
- Produces: `CbrQuery.withProblem(String)`, `CbrQuery.withMinSimilarity(double)`, `CbrQuery.withNotBefore(Instant)` — builders
- Produces: `CbrCaseMemoryStore.retrieveSimilar()` returns `List<ScoredCbrCase<C>>`
- Produces: `ReactiveCbrCaseMemoryStore.retrieveSimilar()` returns `Uni<List<ScoredCbrCase<C>>>`

- [ ] **Step 1: Create ScoredCbrCase record**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ScoredCbrCase.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.Objects;

public record ScoredCbrCase<C extends CbrCase>(C cbrCase, double score) {
    public ScoredCbrCase {
        Objects.requireNonNull(cbrCase, "cbrCase required");
    }
}
```

- [ ] **Step 2: Add `problem` field and builders to CbrQuery**

Modify `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java`.

Replace the entire record with:

```java
package io.casehub.neocortex.memory.cbr;

import io.casehub.neocortex.memory.MemoryDomain;
import java.time.Instant;
import java.util.Map;
import java.util.Objects;

public record CbrQuery(
    String tenantId,
    MemoryDomain domain,
    String caseType,
    Map<String, Object> features,
    int topK,
    double minSimilarity,
    Instant notBefore,
    String problem
) {
    public CbrQuery {
        Objects.requireNonNull(tenantId, "tenantId required");
        Objects.requireNonNull(domain, "domain required");
        Objects.requireNonNull(caseType, "caseType required");
        Objects.requireNonNull(features, "features required");
        features = Map.copyOf(features);
        if (topK < 1) throw new IllegalArgumentException("topK must be >= 1, got: " + topK);
        if (minSimilarity < 0.0 || minSimilarity > 1.0)
            throw new IllegalArgumentException("minSimilarity must be in [0,1], got: " + minSimilarity);
        if (problem != null && problem.isBlank())
            throw new IllegalArgumentException("problem must not be blank when provided");
    }

    public static CbrQuery of(String tenantId, MemoryDomain domain,
                               String caseType, Map<String, Object> features, int topK) {
        return new CbrQuery(tenantId, domain, caseType, features, topK, 0.0, null, null);
    }

    public CbrQuery withProblem(String problem) {
        return new CbrQuery(tenantId, domain, caseType, features, topK,
                            minSimilarity, notBefore, problem);
    }

    public CbrQuery withMinSimilarity(double minSimilarity) {
        return new CbrQuery(tenantId, domain, caseType, features, topK,
                            minSimilarity, notBefore, problem);
    }

    public CbrQuery withNotBefore(Instant notBefore) {
        return new CbrQuery(tenantId, domain, caseType, features, topK,
                            minSimilarity, notBefore, problem);
    }
}
```

- [ ] **Step 3: Update CbrCaseMemoryStore SPI return type**

In `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCaseMemoryStore.java`, change `retrieveSimilar` signature:

```java
<C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery query, Class<C> caseType);
```

- [ ] **Step 4: Update ReactiveCbrCaseMemoryStore SPI return type**

In `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ReactiveCbrCaseMemoryStore.java`, change `retrieveSimilar` signature:

```java
<C extends CbrCase> Uni<List<ScoredCbrCase<C>>> retrieveSimilar(CbrQuery query, Class<C> caseType);
```

- [ ] **Step 5: Update NoOpCbrCaseMemoryStore**

In `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpCbrCaseMemoryStore.java`, change `retrieveSimilar`:

```java
@Override
public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery query, Class<C> caseClass) {
    return List.of();
}
```

- [ ] **Step 6: Update BlockingToReactiveCbrBridge**

In `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/BlockingToReactiveCbrBridge.java`, change `retrieveSimilar`:

```java
@Override
public <C extends CbrCase> Uni<List<ScoredCbrCase<C>>> retrieveSimilar(CbrQuery query, Class<C> caseClass) {
    return Uni.createFrom().item(() -> delegate.retrieveSimilar(query, caseClass))
        .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
}
```

- [ ] **Step 7: Update InMemoryCbrCaseMemoryStore**

In `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`, change `retrieveSimilar` to wrap results in `ScoredCbrCase` with score 1.0:

```java
@Override
@SuppressWarnings("unchecked")
public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery query, Class<C> caseClass) {
    CbrFeatureSchema schema = schemas.get(query.caseType());
    if (schema != null) {
        validateQueryFeatures(query.features(), schema);
    }

    List<ScoredCbrCase<C>> results = new ArrayList<>();
    for (StoredCase stored : cases) {
        if (!stored.tenantId().equals(query.tenantId())) continue;
        if (!stored.domain().equals(query.domain())) continue;
        if (!stored.caseType().equals(query.caseType())) continue;
        if (query.notBefore() != null && stored.storedAt().isBefore(query.notBefore())) continue;
        if (!caseClass.isInstance(stored.cbrCase())) continue;
        if (schema != null && !matchesFeatures(stored.cbrCase(), query.features(), schema)) continue;

        results.add(new ScoredCbrCase<>((C) stored.cbrCase(), 1.0));
        if (results.size() >= query.topK()) break;
    }
    return Collections.unmodifiableList(results);
}
```

- [ ] **Step 8: Update QdrantCbrCaseMemoryStore (return type only — dense search is Task 2)**

In `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`, change `retrieveSimilar` to wrap results in `ScoredCbrCase`:

```java
@Override
@SuppressWarnings("unchecked")
public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery query, Class<C> caseClass) {
    CbrFeatureSchema schema = schemas.get(query.caseType());
    if (schema != null) {
        CbrQueryTranslator.validateQueryFeatures(query.features(), schema);
    }

    String collection = collectionManager.collectionName(query.caseType());

    try {
        if (!collectionManager.client().collectionExistsAsync(collection).get()) {
            return List.of();
        }
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new RuntimeException("Interrupted checking collection existence", e);
    } catch (ExecutionException e) {
        throw new RuntimeException("Failed to check collection existence", e.getCause());
    }

    Filter filter = CbrQueryTranslator.toFilter(query, schema);

    // Dense search is wired in Task 2 — for now, filter-only
    List<ScoredPoint> scoredPoints = executeFilterQuery(collection, filter, query.topK());

    List<ScoredCbrCase<C>> results = new ArrayList<>(scoredPoints.size());
    for (ScoredPoint point : scoredPoints) {
        try {
            C cbrCase = (C) reconstructCase(point.getPayloadMap(), caseClass);
            if (cbrCase != null) {
                results.add(new ScoredCbrCase<>(cbrCase, point.getScore()));
            }
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Failed to reconstruct case from point", e);
        }
    }

    return Collections.unmodifiableList(results);
}
```

- [ ] **Step 9: Migrate contract tests — update all `retrieveSimilar` assertions for ScoredCbrCase**

In `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`:

Every test that calls `retrieveSimilar()` and accesses results must change from `result.problem()` to `result.cbrCase().problem()`, from `result.solution()` to `result.cbrCase().solution()`, etc.

Also fix the `notBefore` tests that use the 7-arg CbrQuery constructor — add the 8th `problem` argument (`null`).

Key pattern for each assertion change:
```java
// Before:
assertThat(results.get(0).problem()).isEqualTo("expected");
// After:
assertThat(results.get(0).cbrCase().problem()).isEqualTo("expected");
```

For notBefore tests using the direct constructor:
```java
// Before:
var query = new CbrQuery("test-tenant", CBR, "starcraft-game", Map.of(), 10, 0.0, notBefore);
// After:
var query = new CbrQuery("test-tenant", CBR, "starcraft-game", Map.of(), 10, 0.0, notBefore, null);
```

- [ ] **Step 10: Add new contract tests**

Add three new tests to `CbrCaseMemoryStoreContractTest`:

```java
@Test
void retrieveSimilar_withProblem_null_returnsFilteredResults() {
    var fv = new FeatureVectorCbrCase("Zerg rush detected", "wall-off", null, null,
        Map.of("opponent_race", "Zerg"));
    store().store(fv, "starcraft-game", ENTITY, CBR, TENANT, "case-null-problem");

    var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
        Map.of("opponent_race", "Zerg"), 5);
    // problem is null by default via of()
    assertThat(query.problem()).isNull();

    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).cbrCase().problem()).isEqualTo("Zerg rush detected");
    assertThat(results.get(0).score()).isEqualTo(1.0);
}

@Test
void retrieveSimilar_withProblem_nonNull_returnsFilteredResults() {
    var fv = new FeatureVectorCbrCase("Zerg rush detected", "wall-off", null, null,
        Map.of("opponent_race", "Zerg"));
    store().store(fv, "starcraft-game", ENTITY, CBR, TENANT, "case-with-problem");

    var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
        Map.of("opponent_race", "Zerg"), 5)
        .withProblem("Zerg attack incoming");

    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.get(0).cbrCase().problem()).isEqualTo("Zerg rush detected");
}

@Test
void retrieveSimilar_minSimilarity_zero_returnsAllMatches() {
    var fv1 = new FeatureVectorCbrCase("case one", "solution one", null, null,
        Map.of("opponent_race", "Zerg"));
    var fv2 = new FeatureVectorCbrCase("case two", "solution two", null, null,
        Map.of("opponent_race", "Zerg"));
    store().store(fv1, "starcraft-game", ENTITY, CBR, TENANT, "case-ms-1");
    store().store(fv2, "starcraft-game", ENTITY, CBR, TENANT, "case-ms-2");

    var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
        Map.of("opponent_race", "Zerg"), 10);
    // minSimilarity is 0.0 by default
    assertThat(query.minSimilarity()).isEqualTo(0.0);

    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).hasSizeGreaterThanOrEqualTo(2);
}
```

- [ ] **Step 11: Build and verify all tests pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api,memory,memory-cbr-inmem,memory-testing`

Expected: BUILD SUCCESS — all existing + new contract tests pass.

Then run Qdrant tests (requires Docker):
Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-qdrant`

Expected: BUILD SUCCESS — all 23+ contract tests pass via Testcontainers.

- [ ] **Step 12: Commit**

```
feat(#70): ScoredCbrCase return type + CbrQuery.problem field

Breaking API change: retrieveSimilar() returns List<ScoredCbrCase<C>>
instead of List<C>. CbrQuery gains nullable `problem` field for
query-side embedding, plus withProblem/withMinSimilarity/withNotBefore
builders. All implementations updated. Dense search wired in next commit.

Closes #71 (minSimilarity wiring is structural — score=1.0 in filter-only
mode means threshold is a no-op until dense search is active).
```

---

### Task 2: Qdrant Dense Vector Search + Dimension Validation

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrCollectionManager.java`
- Create: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrDenseSearchTest.java`

**Interfaces:**
- Consumes: `CbrQuery.problem()` (from Task 1)
- Consumes: `ScoredCbrCase<C>` (from Task 1)
- Consumes: `CbrQueryTranslator.toFilter()` (unchanged)
- Consumes: `QdrantClient.searchAsync(SearchPoints)` returns `ListenableFuture<List<ScoredPoint>>`

- [ ] **Step 1: Write the dense search integration test class**

Create `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrDenseSearchTest.java`:

```java
package io.casehub.neocortex.memory.cbr.qdrant;

import dev.langchain4j.data.embedding.Embedding;
import dev.langchain4j.data.segment.TextSegment;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.QdrantGrpcClient;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;

import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.assertThat;

@Testcontainers
class QdrantCbrDenseSearchTest {

    @SuppressWarnings("resource")
    @Container
    static final GenericContainer<?> qdrant = new GenericContainer<>("qdrant/qdrant:v1.18.0")
        .withExposedPorts(6334);

    private static final MemoryDomain CBR = new MemoryDomain("cbr");
    private static final String TENANT = "test-tenant";
    private static final String ENTITY = "test-entity";
    private static final AtomicInteger TEST_COUNTER = new AtomicInteger();
    private static final int DIM = 4;

    private QdrantCbrCaseMemoryStore store;
    private final DeterministicEmbeddingModel embeddingModel = new DeterministicEmbeddingModel();

    @BeforeEach
    void setUp() {
        QdrantClient client = new QdrantClient(
            QdrantGrpcClient.newBuilder(qdrant.getHost(), qdrant.getMappedPort(6334), false).build());

        int testId = TEST_COUNTER.incrementAndGet();
        QdrantCbrConfig config = new QdrantCbrConfig() {
            @Override public String host() { return qdrant.getHost(); }
            @Override public int port() { return qdrant.getMappedPort(6334); }
            @Override public Optional<String> apiKey() { return Optional.empty(); }
            @Override public boolean useTls() { return false; }
            @Override public String collectionPrefix() { return "dense_test_" + testId; }
            @Override public String denseVectorName() { return "dense"; }
            @Override public int maxRetries() { return 3; }
        };

        CbrCollectionManager collectionManager = new CbrCollectionManager(client, config);
        store = new QdrantCbrCaseMemoryStore(collectionManager, embeddingModel, config, null);

        store.registerSchema(CbrFeatureSchema.of("starcraft-game",
            FeatureField.categorical("opponent_race"),
            FeatureField.numeric("army_size_ratio", 0.0, 3.0)));
    }

    @Test
    void denseSearch_ranksResultsBySimilarity() {
        // "alpha" embeds to [1,0,0,0], "alpha-ish" to [0.9,0.1,0,0], "beta" to [0,1,0,0]
        store.store(new TextualCbrCase("alpha", "solution-a", null, null),
            "starcraft-game", ENTITY, CBR, TENANT, "case-alpha");
        store.store(new TextualCbrCase("beta", "solution-b", null, null),
            "starcraft-game", ENTITY, CBR, TENANT, "case-beta");
        store.store(new TextualCbrCase("alpha-ish", "solution-c", null, null),
            "starcraft-game", ENTITY, CBR, TENANT, "case-alpha-ish");

        var query = CbrQuery.of(TENANT, CBR, "starcraft-game", Map.of(), 10)
            .withProblem("alpha");

        var results = store.retrieveSimilar(query, CbrCase.class);

        assertThat(results).hasSizeGreaterThanOrEqualTo(2);
        // "alpha" should rank first (exact match), then "alpha-ish" (high similarity)
        assertThat(results.get(0).cbrCase().problem()).isEqualTo("alpha");
        assertThat(results.get(0).score()).isGreaterThan(results.get(1).score());
    }

    @Test
    void denseSearch_minSimilarity_filtersLowScoreResults() {
        store.store(new TextualCbrCase("alpha", "solution-a", null, null),
            "starcraft-game", ENTITY, CBR, TENANT, "case-filter-alpha");
        store.store(new TextualCbrCase("beta", "solution-b", null, null),
            "starcraft-game", ENTITY, CBR, TENANT, "case-filter-beta");

        // Query with high threshold — "beta" should be excluded (orthogonal to "alpha")
        var query = CbrQuery.of(TENANT, CBR, "starcraft-game", Map.of(), 10)
            .withProblem("alpha")
            .withMinSimilarity(0.5);

        var results = store.retrieveSimilar(query, CbrCase.class);

        // "alpha" should pass (cos=1.0), "beta" should be filtered (cos≈0.0)
        assertThat(results).allSatisfy(r -> assertThat(r.score()).isGreaterThanOrEqualTo(0.5));
        assertThat(results.stream().map(r -> r.cbrCase().problem()))
            .contains("alpha")
            .doesNotContain("beta");
    }

    @Test
    void denseSearch_fallsBackToFilterOnly_whenProblemNull() {
        store.store(new TextualCbrCase("alpha", "solution-a", null, null),
            "starcraft-game", ENTITY, CBR, TENANT, "case-fallback-alpha");
        store.store(new TextualCbrCase("beta", "solution-b", null, null),
            "starcraft-game", ENTITY, CBR, TENANT, "case-fallback-beta");

        // problem=null → filter-only mode, all results score 1.0
        var query = CbrQuery.of(TENANT, CBR, "starcraft-game", Map.of(), 10);

        var results = store.retrieveSimilar(query, CbrCase.class);

        assertThat(results).hasSize(2);
        assertThat(results).allSatisfy(r -> assertThat(r.score()).isEqualTo(1.0f));
    }

    @Test
    void denseSearch_withPayloadFilters_combinesVectorAndFilter() {
        store.store(new FeatureVectorCbrCase("alpha", "sol-a", null, null,
                Map.of("opponent_race", "Zerg")),
            "starcraft-game", ENTITY, CBR, TENANT, "case-combo-zerg");
        store.store(new FeatureVectorCbrCase("alpha", "sol-b", null, null,
                Map.of("opponent_race", "Protoss")),
            "starcraft-game", ENTITY, CBR, TENANT, "case-combo-protoss");

        // Dense search for "alpha" + filter for Zerg only
        var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
                Map.of("opponent_race", "Zerg"), 10)
            .withProblem("alpha");

        var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);

        assertThat(results).hasSize(1);
        assertThat(results.get(0).cbrCase().features().get("opponent_race")).isEqualTo("Zerg");
    }

    /**
     * Deterministic embedding model for testing. Maps known text strings to
     * fixed unit vectors so cosine similarity is predictable.
     */
    static class DeterministicEmbeddingModel implements EmbeddingModel {
        private static final Map<String, float[]> KNOWN_VECTORS = Map.of(
            "alpha", new float[]{1.0f, 0.0f, 0.0f, 0.0f},
            "alpha-ish", new float[]{0.9f, 0.436f, 0.0f, 0.0f},  // cos(alpha, alpha-ish) ≈ 0.9
            "beta", new float[]{0.0f, 1.0f, 0.0f, 0.0f},
            "gamma", new float[]{0.0f, 0.0f, 1.0f, 0.0f}
        );

        @Override
        public Response<Embedding> embed(String text) {
            return Response.from(Embedding.from(vectorFor(text)));
        }

        @Override
        public Response<Embedding> embed(TextSegment segment) {
            return embed(segment.text());
        }

        @Override
        public int dimension() { return DIM; }

        private float[] vectorFor(String text) {
            float[] known = KNOWN_VECTORS.get(text);
            if (known != null) return known;
            // Fallback: hash-based deterministic vector, normalized
            int hash = text.hashCode();
            float[] v = new float[DIM];
            for (int i = 0; i < DIM; i++) {
                v[i] = ((hash >> (i * 8)) & 0xFF) / 255.0f;
            }
            float norm = 0;
            for (float f : v) norm += f * f;
            norm = (float) Math.sqrt(norm);
            if (norm > 0) for (int i = 0; i < DIM; i++) v[i] /= norm;
            return v;
        }
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-qdrant -Dtest=QdrantCbrDenseSearchTest`

Expected: FAIL — `denseSearch_ranksResultsBySimilarity` fails because the store still uses `scrollAsync` (all scores = 1.0, no vector-based ranking).

- [ ] **Step 3: Implement `executeDenseSearch` in QdrantCbrCaseMemoryStore**

Add a new private method and update `retrieveSimilar()` to branch:

```java
import io.qdrant.client.grpc.Points.SearchPoints;

// In retrieveSimilar(), replace the single executeFilterQuery call with:
List<ScoredPoint> scoredPoints;
if (embeddingModel != null && query.problem() != null) {
    scoredPoints = executeDenseSearch(collection, filter, query);
} else {
    if (query.problem() != null) {
        LOG.info("Dense search unavailable — problem text ignored, returning filter-only results for caseType=" + query.caseType());
    }
    scoredPoints = executeFilterQuery(collection, filter, query.topK());
}

// New method:
private List<ScoredPoint> executeDenseSearch(String collection, Filter filter, CbrQuery query) {
    Embedding queryEmbedding = embeddingModel.embed(TextSegment.from(query.problem())).content();

    SearchPoints.Builder searchBuilder = SearchPoints.newBuilder()
        .setCollectionName(collection)
        .addAllVector(queryEmbedding.vectorAsList())
        .setVectorName(config.denseVectorName())
        .setFilter(filter)
        .setLimit(query.topK())
        .setScoreThreshold((float) query.minSimilarity())
        .setWithPayload(WithPayloadSelectorFactory.enable(true));

    try {
        return collectionManager.client().searchAsync(searchBuilder.build()).get();
    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new RuntimeException("Interrupted during dense search", e);
    } catch (ExecutionException e) {
        throw new RuntimeException("Dense search failed", e.getCause());
    }
}
```

- [ ] **Step 4: Run the dense search tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-qdrant -Dtest=QdrantCbrDenseSearchTest`

Expected: PASS — all 4 dense search tests pass.

- [ ] **Step 5: Implement dimension validation in CbrCollectionManager**

Modify `CbrCollectionManager.ensureCollection()` — after finding an existing collection, validate vector dimension:

```java
void ensureCollection(String caseType, int vectorDimension) {
    String collection = collectionName(caseType);
    if (knownCollections.contains(collection)) {
        return;
    }

    try {
        if (client.collectionExistsAsync(collection).get()) {
            // Validate vector dimension matches
            int effectiveDim = vectorDimension > 0 ? vectorDimension : 1;
            var info = client.getCollectionInfoAsync(collection).get();
            var vectorsConfig = info.getConfig().getParams().getVectorsConfig();
            if (vectorsConfig.hasParamsMap()) {
                var params = vectorsConfig.getParamsMap().getMapMap().get(config.denseVectorName());
                if (params != null && params.getSize() != effectiveDim) {
                    LOG.warning("Collection " + collection + " has vector dimension "
                        + params.getSize() + " but expected " + effectiveDim
                        + " — recreating collection (existing points will be lost)");
                    client.deleteCollectionAsync(collection).get();
                    // Fall through to create with correct dimension
                } else {
                    knownCollections.add(collection);
                    return;
                }
            } else {
                knownCollections.add(collection);
                return;
            }
        }

        int effectiveDim = vectorDimension > 0 ? vectorDimension : 1;

        VectorParams denseParams = VectorParams.newBuilder()
            .setSize(effectiveDim)
            .setDistance(Distance.Cosine)
            .build();

        CreateCollection.Builder createBuilder = CreateCollection.newBuilder()
            .setCollectionName(collection)
            .setVectorsConfig(VectorsConfig.newBuilder()
                .setParamsMap(VectorParamsMap.newBuilder()
                    .putMap(config.denseVectorName(), denseParams)
                    .build())
                .build());

        client.createCollectionAsync(createBuilder.build()).get();
        createBasePayloadIndexes(collection);
        knownCollections.add(collection);

    } catch (InterruptedException e) {
        Thread.currentThread().interrupt();
        throw new RuntimeException("Interrupted during ensureCollection", e);
    } catch (ExecutionException e) {
        throw new RuntimeException("ensureCollection failed for " + collection, e.getCause());
    }
}
```

Add import: `import io.qdrant.client.grpc.Collections.CollectionInfo;` (already available via existing imports).

- [ ] **Step 6: Run full Qdrant test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-qdrant`

Expected: PASS — all contract tests (23+) and dense search tests (4) pass.

- [ ] **Step 7: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Expected: BUILD SUCCESS across all modules.

- [ ] **Step 8: Commit**

```
feat(#70): dense vector search — searchAsync + minSimilarity + dimension validation

QdrantCbrCaseMemoryStore branches between searchAsync (when EmbeddingModel
and query.problem() are present) and scrollAsync (filter-only fallback).
score_threshold wires minSimilarity for server-side filtering.

CbrCollectionManager validates existing collection vector dimension on
startup — recreates if mismatched (e.g., upgrading from no-model to model).

Closes #70
```

---

### Task 3: Parent Spec Sync (#58)

**Files:**
- Modify: `specs/issue-20-cbr-retrieval-architecture/2026-06-30-cbr-retrieval-architecture.md` (workspace)

**Interfaces:**
- Consumes: Implementation from Tasks 1-2 as source of truth

- [ ] **Step 1: Update §3 CbrCase interface**

Add `cbrType()` and `features()` methods that are in the code but not the spec:

```java
public interface CbrCase {
    String cbrType();
    String problem();
    String solution();
    String outcome();
    Double confidence();
    default Map<String, Object> features() { return Map.of(); }
}
```

- [ ] **Step 2: Update §3.3 PlanCbrCase location**

Change `engine-api` to `memory-api`. PlanTrace uses only String and Map, no engine dependency.

- [ ] **Step 3: Update §4 Feature Schema**

Add `NumericRange` record and update the query operation table:

| Field Type | Index Type | Query Operation |
|-----------|-----------|-----------------|
| `Categorical` | Qdrant keyword payload index | Exact match filter |
| `Numeric` | Qdrant float payload index | Range filter (`Number` for exact, `NumericRange` for range) |
| `Text` | Qdrant keyword payload index | Keyword filter |

- [ ] **Step 4: Update §5 CbrQuery**

Add `problem` field (nullable), `notBefore` field (nullable), `minSimilarity` semantics. Add `withProblem()`, `withMinSimilarity()`, `withNotBefore()` builders.

- [ ] **Step 5: Update §6 CbrCaseMemoryStore SPI**

- `store()`: add `caseType` parameter
- `erase()`/`eraseEntity()`: return `Integer` (boxed)
- `retrieveSimilar()`: returns `List<ScoredCbrCase<C>>`
- Add `ScoredCbrCase<C extends CbrCase>(C cbrCase, double score)` record
- Update §6.3: NoOp does not delegate to CaseMemoryStore

- [ ] **Step 6: Update §7 Qdrant-Backed Memory**

Document dual-path retrieval (dense + filter-only), `score_threshold` wiring, collection dimension validation.

- [ ] **Step 7: Commit to workspace**

```
docs(#58): sync CBR spec — ScoredCbrCase, problem field, dense search, NumericRange

Aligns parent spec with code: store() caseType param, Integer return
types, CbrCase.cbrType()/features() methods, ScoredCbrCase return type,
CbrQuery.problem field, dual-path retrieval, dimension validation,
NoOp standalone (no delegation).

Closes #58
```
