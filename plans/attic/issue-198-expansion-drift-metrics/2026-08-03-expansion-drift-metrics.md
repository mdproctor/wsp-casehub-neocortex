# Expansion Drift Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #198 — expansion drift metrics auto-fallback
**Issue group:** #198

**Goal:** Add drift detection to `QueryExpandingCaseRetriever` that measures
cosine similarity between original and expanded queries, logs and meters
drift values, and optionally drops drifted expansions.

**Architecture:** All changes are in `rag-expansion/`. The `QueryExpandingCaseRetriever`
gains optional `EmbeddingModel` and `MeterRegistry` CDI injections. A new
`DriftAction` enum and `ExpansionConfig.DriftConfig` sub-interface configure
behavior. `ExpansionConfigValidator` gains threshold and model-availability
checks. `CosineSimilarity.between()` from langchain4j-core computes drift.

**Tech Stack:** Java 21, Quarkus CDI, LangChain4j 1.14.1 (`EmbeddingModel`,
`CosineSimilarity`, `Embedding`, `TextSegment`), Micrometer

## Global Constraints

- Pre-release: breaking changes are free
- `langchain4j-core` is already an explicit dependency of `rag-expansion`
- `micrometer-core` must be `provided` scope (Quarkus supplies at runtime)
- All existing `QueryExpandingCaseRetrieverTest` tests must continue passing
- Drift detection must be zero-overhead when disabled (no embedding computation)

---

### Task 1: Config, Enum, and Validation

**Files:**
- Create: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/DriftAction.java`
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ExpansionConfig.java`
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ExpansionConfigValidator.java`
- Modify: `rag-expansion/pom.xml`
- Test: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/ExpansionConfigValidatorTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `DriftAction` enum (`OBSERVE`, `DROP`), `ExpansionConfig.DriftConfig`
  interface (`boolean enabled()`, `double threshold()`, `DriftAction action()`),
  `ExpansionConfig.drift()` accessor

- [ ] **Step 1: Write failing tests for threshold validation**

Add to `ExpansionConfigValidatorTest`:

```java
@Test
void warnsWhenDriftEnabledButNoEmbeddingModel() {
    var config = configWith(true, "llm", driftConfig(true, 0.7, DriftAction.OBSERVE));
    var validator = new ExpansionConfigValidator();
    validator.config = config;
    validator.embeddingModel = Instance.empty(); // CDI empty instance

    validator.onStartup(null);

    assertThat(logCapture.warnings())
        .anyMatch(w -> w.contains("no EmbeddingModel available"));
}

@Test
void rejectsThresholdAboveOne() {
    var config = configWith(true, "llm", driftConfig(true, 1.5, DriftAction.OBSERVE));
    var validator = new ExpansionConfigValidator();
    validator.config = config;

    assertThatThrownBy(() -> validator.onStartup(null))
        .isInstanceOf(IllegalStateException.class)
        .hasMessageContaining("threshold");
}

@Test
void rejectsThresholdBelowZero() {
    var config = configWith(true, "llm", driftConfig(true, -0.1, DriftAction.DROP));
    var validator = new ExpansionConfigValidator();
    validator.config = config;

    assertThatThrownBy(() -> validator.onStartup(null))
        .isInstanceOf(IllegalStateException.class)
        .hasMessageContaining("threshold");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=ExpansionConfigValidatorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure (DriftAction, DriftConfig not defined)

- [ ] **Step 3: Create DriftAction enum**

Use `ide_create_file`:

```java
package io.casehub.neocortex.rag.expansion;

public enum DriftAction {
    OBSERVE,
    DROP
}
```

- [ ] **Step 4: Add DriftConfig to ExpansionConfig**

Use `ide_insert_member` on `ExpansionConfig` to add:

```java
interface DriftConfig {
    @WithDefault("false")
    boolean enabled();

    @WithDefault("0.7")
    double threshold();

    @WithDefault("observe")
    DriftAction action();
}

DriftConfig drift();
```

- [ ] **Step 5: Add micrometer-core dependency to pom.xml**

Add to `rag-expansion/pom.xml` dependencies:

```xml
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-core</artifactId>
    <scope>provided</scope>
</dependency>
```

- [ ] **Step 6: Update ExpansionConfigValidator**

Use `ide_edit_member` to replace the class body. Add `Instance<EmbeddingModel>`
field injection and extend `onStartup()`:

```java
@Inject
ExpansionConfig config;

@Inject
@Any
Instance<EmbeddingModel> embeddingModel;

void onStartup(@Observes StartupEvent event) {
    if (config.mode().isEmpty()) {
        LOG.warning("Query expansion is enabled but no mode is set"
            + " — queries will pass through unchanged."
            + " Set casehub.rag.expansion.mode to llm, template, or step-back.");
    }

    ExpansionConfig.DriftConfig drift = config.drift();
    if (drift.enabled()) {
        if (drift.threshold() < 0.0 || drift.threshold() > 1.0) {
            throw new IllegalStateException(
                "casehub.rag.expansion.drift.threshold must be in [0.0, 1.0], got " + drift.threshold());
        }
        if (!embeddingModel.isResolvable()) {
            LOG.warning("Drift detection enabled but no EmbeddingModel available"
                + " — drift detection will be inactive.");
        }
    }
}
```

Add imports: `dev.langchain4j.model.embedding.EmbeddingModel`, `jakarta.enterprise.inject.Any`,
`jakarta.enterprise.inject.Instance`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=ExpansionConfigValidatorTest`
Expected: all tests PASS

- [ ] **Step 8: Run full module tests for regression**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion`
Expected: all existing tests still PASS

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-expansion/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#198): DriftAction enum, DriftConfig, threshold validation"
```

---

### Task 2: Drift Detection and Metrics in QueryExpandingCaseRetriever

**Files:**
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/QueryExpandingCaseRetriever.java`
- Test: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/QueryExpandingCaseRetrieverTest.java`

**Interfaces:**
- Consumes: `DriftAction` enum, `ExpansionConfig.DriftConfig` from Task 1.
  `EmbeddingModel.embedAll(List<TextSegment>)` → `Response<List<Embedding>>`.
  `CosineSimilarity.between(Embedding, Embedding)` → `double` in [-1, 1].
- Produces: drift-filtered expansion list, Micrometer counters/distribution summary

- [ ] **Step 1: Write failing test — observe mode logs but keeps all expansions**

Add to `QueryExpandingCaseRetrieverTest`:

```java
@Test
void driftObserveModeKeepsAllExpansions() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    // Expander returns query with high-drift expansion
    QueryExpander driftingExpander = query -> List.of(query.withExpansion("completely unrelated text"));

    var embeddingModel = new StubEmbeddingModel(Map.of(
        "original", new float[]{1.0f, 0.0f, 0.0f},
        "completely unrelated text", new float[]{0.0f, 1.0f, 0.0f}
    ));
    var driftConfig = stubDriftConfig(true, 0.7, DriftAction.OBSERVE);
    var config = stubExpansionConfig(driftConfig);

    var retriever = new QueryExpandingCaseRetriever(delegate, driftingExpander,
        Instance.of(embeddingModel), Instance.empty(), config);
    var results = retriever.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    // Observe mode: all expansions kept despite drift
    assertThat(capturedQueries).hasSize(2); // original + expanded
    assertThat(results).hasSize(2);
}
```

- [ ] **Step 2: Write failing test — drop mode removes drifted expansions**

```java
@Test
void driftDropModeRemovesDriftedExpansions() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    QueryExpander driftingExpander = query -> List.of(query.withExpansion("completely unrelated text"));

    var embeddingModel = new StubEmbeddingModel(Map.of(
        "original", new float[]{1.0f, 0.0f, 0.0f},
        "completely unrelated text", new float[]{0.0f, 1.0f, 0.0f}
    ));
    var driftConfig = stubDriftConfig(true, 0.7, DriftAction.DROP);
    var config = stubExpansionConfig(driftConfig);

    var retriever = new QueryExpandingCaseRetriever(delegate, driftingExpander,
        Instance.of(embeddingModel), Instance.empty(), config);
    var results = retriever.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    // Drop mode: drifted expansion removed, only original survives
    assertThat(capturedQueries).hasSize(1);
    assertThat(capturedQueries.get(0).expandedText()).isNull();
}
```

- [ ] **Step 3: Write failing test — original query never drift-compared or dropped**

```java
@Test
void originalQueryExcludedFromDriftComparison() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    // Expander returns only expanded query (original will be prepended)
    QueryExpander expander = query -> List.of(query.withExpansion("similar enough text"));

    var embeddingModel = new StubEmbeddingModel(Map.of(
        "original", new float[]{1.0f, 0.0f, 0.0f},
        "similar enough text", new float[]{0.9f, 0.4f, 0.0f}
    ));
    var driftConfig = stubDriftConfig(true, 0.7, DriftAction.DROP);
    var config = stubExpansionConfig(driftConfig);

    var retriever = new QueryExpandingCaseRetriever(delegate, expander,
        Instance.of(embeddingModel), Instance.empty(), config);
    var results = retriever.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    // Original always survives, expansion above threshold also survives
    assertThat(capturedQueries).hasSize(2);
    assertThat(capturedQueries.get(0).expandedText()).isNull(); // original
    assertThat(capturedQueries.get(1).expandedText()).isEqualTo("similar enough text");
}
```

- [ ] **Step 4: Write failing test — embedding failure falls back gracefully**

```java
@Test
void embeddingFailureFallsBackToUnfilteredList() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    QueryExpander expander = query -> List.of(query.withExpansion("expanded text"));

    EmbeddingModel failingModel = segments -> { throw new RuntimeException("ONNX model error"); };
    var driftConfig = stubDriftConfig(true, 0.7, DriftAction.DROP);
    var config = stubExpansionConfig(driftConfig);

    var retriever = new QueryExpandingCaseRetriever(delegate, expander,
        Instance.of(failingModel), Instance.empty(), config);
    var results = retriever.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    // Fail-safe: all expansions kept
    assertThat(capturedQueries).hasSize(2);
}
```

- [ ] **Step 5: Write failing test — no EmbeddingModel skips drift detection**

```java
@Test
void noEmbeddingModelSkipsDriftDetection() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    QueryExpander expander = query -> List.of(query.withExpansion("expanded text"));

    var driftConfig = stubDriftConfig(true, 0.7, DriftAction.DROP);
    var config = stubExpansionConfig(driftConfig);

    // No EmbeddingModel available
    var retriever = new QueryExpandingCaseRetriever(delegate, expander,
        Instance.empty(), Instance.empty(), config);
    var results = retriever.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    // All expansions kept — drift detection skipped
    assertThat(capturedQueries).hasSize(2);
}
```

- [ ] **Step 6: Write failing test — drift disabled skips detection**

```java
@Test
void driftDisabledSkipsDriftDetection() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    QueryExpander driftingExpander = query -> List.of(query.withExpansion("completely unrelated"));

    var embeddingModel = new StubEmbeddingModel(Map.of(
        "original", new float[]{1.0f, 0.0f, 0.0f},
        "completely unrelated", new float[]{0.0f, 1.0f, 0.0f}
    ));
    var driftConfig = stubDriftConfig(false, 0.7, DriftAction.DROP); // disabled
    var config = stubExpansionConfig(driftConfig);

    var retriever = new QueryExpandingCaseRetriever(delegate, driftingExpander,
        Instance.of(embeddingModel), Instance.empty(), config);
    var results = retriever.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    // Drift disabled: all expansions kept
    assertThat(capturedQueries).hasSize(2);
}
```

- [ ] **Step 7: Write failing test — batch embedding call**

```java
@Test
void driftDetectionUsesSingleBatchEmbedCall() {
    var embedCallCount = new int[]{0};
    EmbeddingModel countingModel = segments -> {
        embedCallCount[0]++;
        List<Embedding> embeddings = segments.stream()
            .map(s -> Embedding.from(new float[]{1.0f, 0.0f, 0.0f}))
            .toList();
        return Response.from(embeddings);
    };
    CaseRetriever delegate = (query, corpus, maxResults, filter) ->
        List.of(chunk(query.searchText(), "doc", 0.9));
    QueryExpander expander = query -> List.of(
        query.withExpansion("exp1"), query.withExpansion("exp2"));

    var driftConfig = stubDriftConfig(true, 0.7, DriftAction.OBSERVE);
    var config = stubExpansionConfig(driftConfig);

    var retriever = new QueryExpandingCaseRetriever(delegate, expander,
        Instance.of(countingModel), Instance.empty(), config);
    retriever.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    assertThat(embedCallCount[0]).isEqualTo(1); // single embedAll call
}
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=QueryExpandingCaseRetrieverTest`
Expected: compilation failure (new constructor signature)

- [ ] **Step 9: Add test helpers**

Add to `QueryExpandingCaseRetrieverTest`:

```java
private static ExpansionConfig.DriftConfig stubDriftConfig(boolean enabled, double threshold, DriftAction action) {
    return new ExpansionConfig.DriftConfig() {
        @Override public boolean enabled() { return enabled; }
        @Override public double threshold() { return threshold; }
        @Override public DriftAction action() { return action; }
    };
}

private static ExpansionConfig stubExpansionConfig(ExpansionConfig.DriftConfig driftConfig) {
    return new ExpansionConfig() {
        @Override public boolean enabled() { return true; }
        @Override public Optional<String> mode() { return Optional.of("llm"); }
        @Override public int hypotheticalCount() { return 1; }
        @Override public Optional<String> promptTemplate() { return Optional.empty(); }
        @Override public Optional<String> template() { return Optional.empty(); }
        @Override public Optional<String> stepBackPromptTemplate() { return Optional.empty(); }
        @Override public DriftConfig drift() { return driftConfig; }
    };
}

private static class StubEmbeddingModel implements EmbeddingModel {
    private final Map<String, float[]> vectors;

    StubEmbeddingModel(Map<String, float[]> vectors) {
        this.vectors = vectors;
    }

    @Override
    public Response<List<Embedding>> embedAll(List<TextSegment> textSegments) {
        List<Embedding> embeddings = textSegments.stream()
            .map(s -> {
                float[] vec = vectors.getOrDefault(s.text(), new float[]{0.5f, 0.5f, 0.5f});
                return Embedding.from(vec);
            })
            .toList();
        return Response.from(embeddings);
    }
}

@SuppressWarnings("unchecked")
private static <T> Instance<T> Instance.of(T value) {
    // Simple CDI Instance stub — return provided value
    // Implementation: anonymous Instance that returns value from get()
    // and true from isResolvable()
}

@SuppressWarnings("unchecked")
private static <T> Instance<T> Instance.empty() {
    // CDI Instance stub — isResolvable() returns false
}
```

Note: The `Instance.of()` and `Instance.empty()` stubs need concrete
implementations wrapping the CDI `Instance` interface. Use anonymous
classes that implement `isResolvable()`, `get()`, and delegate
`iterator()` / `stream()` appropriately.

- [ ] **Step 10: Implement drift detection in QueryExpandingCaseRetriever**

Use `ide_edit_member` to update the constructor — add new params:

```java
@Inject
public QueryExpandingCaseRetriever(@Delegate @Any CaseRetriever delegate,
                                   QueryExpander expander,
                                   @Any Instance<EmbeddingModel> embeddingModel,
                                   Instance<MeterRegistry> meterRegistry,
                                   ExpansionConfig config) {
    this.delegate = delegate;
    this.expander = expander;
    this.embeddingModel = embeddingModel;
    this.meterRegistry = meterRegistry;
    this.config = config;
    LOG.fine(() -> "Query expansion decorator active, expander: " + expander.getClass().getSimpleName());
}
```

Add fields:

```java
private final Instance<EmbeddingModel> embeddingModel;
private final Instance<MeterRegistry> meterRegistry;
private final ExpansionConfig config;
```

Add `filterByDrift` method:

```java
private List<RetrievalQuery> filterByDrift(RetrievalQuery original, List<RetrievalQuery> expanded) {
    ExpansionConfig.DriftConfig drift = config.drift();
    if (!drift.enabled() || !embeddingModel.isResolvable()) {
        return expanded;
    }

    try {
        // Collect texts: original first, then expanded queries with expandedText
        List<RetrievalQuery> expandedOnly = expanded.stream()
            .filter(q -> q.expandedText() != null)
            .toList();

        if (expandedOnly.isEmpty()) {
            return expanded;
        }

        List<TextSegment> segments = new ArrayList<>(expandedOnly.size() + 1);
        segments.add(TextSegment.from(original.text()));
        for (var q : expandedOnly) {
            segments.add(TextSegment.from(q.searchText()));
        }

        List<Embedding> embeddings = embeddingModel.get().embedAll(segments).content();
        Embedding originalEmbedding = embeddings.get(0);

        String mode = config.mode().orElse("unknown");

        // Record total expansion event
        if (meterRegistry.isResolvable()) {
            meterRegistry.get().counter("casehub.rag.expansion.total", "mode", mode).increment();
        }

        Set<RetrievalQuery> toDrop = new HashSet<>();
        for (int i = 0; i < expandedOnly.size(); i++) {
            double similarity = CosineSimilarity.between(originalEmbedding, embeddings.get(i + 1));

            LOG.fine(() -> String.format("Drift: similarity=%.4f threshold=%.4f query='%s'",
                similarity, drift.threshold(), expandedOnly.get(i).searchText()));

            if (meterRegistry.isResolvable()) {
                meterRegistry.get().summary("casehub.rag.expansion.drift", "mode", mode)
                    .record(similarity);
            }

            if (similarity < drift.threshold()) {
                LOG.warning(() -> String.format(
                    "Expansion drift detected: similarity=%.4f below threshold=%.4f for query='%s'",
                    similarity, drift.threshold(), expandedOnly.get(i).searchText()));

                if (drift.action() == DriftAction.DROP) {
                    toDrop.add(expandedOnly.get(i));
                    if (meterRegistry.isResolvable()) {
                        meterRegistry.get().counter("casehub.rag.expansion.drift.fallback", "mode", mode)
                            .increment();
                    }
                }
            }
        }

        if (toDrop.isEmpty()) {
            return expanded;
        }

        return expanded.stream().filter(q -> !toDrop.contains(q)).toList();

    } catch (Exception e) {
        LOG.log(Level.WARNING, "Drift detection failed, using unfiltered expansion list", e);
        return expanded;
    }
}
```

Add imports: `dev.langchain4j.model.embedding.EmbeddingModel`,
`dev.langchain4j.data.embedding.Embedding`, `dev.langchain4j.data.segment.TextSegment`,
`dev.langchain4j.store.embedding.CosineSimilarity`,
`io.micrometer.core.instrument.MeterRegistry`,
`jakarta.enterprise.inject.Instance`, `jakarta.enterprise.inject.Any`,
`java.util.HashSet`, `java.util.Set`.

Wire into `retrieve()` — use `ide_replace_member` on `retrieve`. Add
the `filterByDrift` call after the "ensure original present" block:

```java
// Filter by drift (after original ensured, before fan-out)
expanded = filterByDrift(query, expanded);
```

- [ ] **Step 11: Update existing tests to use new constructor**

The existing tests use the 2-param constructor `(CaseRetriever, QueryExpander)`.
Add a convenience constructor or update each test to pass `Instance.empty()`
for the new params and a no-drift config. A package-private constructor is
cleanest:

```java
QueryExpandingCaseRetriever(CaseRetriever delegate, QueryExpander expander) {
    this(delegate, expander, Instance.empty(), Instance.empty(), NO_DRIFT_CONFIG);
}
```

Where `NO_DRIFT_CONFIG` is a static `ExpansionConfig` with `drift().enabled() = false`.

- [ ] **Step 12: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion`
Expected: all tests PASS (old + new)

- [ ] **Step 13: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add rag-expansion/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#198): drift detection and Micrometer metrics in QueryExpandingCaseRetriever"
```

---
