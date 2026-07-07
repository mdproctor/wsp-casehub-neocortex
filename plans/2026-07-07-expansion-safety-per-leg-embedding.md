# Expansion Safety Net and Per-Leg Embedding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #119 — always include original query in expansion result set
**Issue group:** #119, #113

**Goal:** Make query expansion a purely additive operation — original query
always present as safety net (#119), and each retrieval leg gets optimal
input text (#113).

**Architecture:** Two independent changes in two modules. The expansion
decorator (`rag-expansion`) prepends the original query using record
equality. The hybrid retriever (`rag`) uses `embedBatch()` to produce
separate embeddings for dense vs lexical legs when expansion is active.

**Tech Stack:** Java 21, Quarkus 3.32, JUnit 5, AssertJ, Mutiny,
Testcontainers (Qdrant)

## Global Constraints

- Java 21 language level on Java 26 JVM
- `RetrievalQuery` is a record — equality is structural (both `text` and
  `expandedText` fields)
- Per-leg embedding is unconditional when expansion is active — no config flag
- `embedBatch()` for the two-text case; single `embed()` when no expansion
- BM25 already uses `query.text()` — no change needed
- Both blocking and reactive variants must be updated in parallel

---

### Task 1: Original Query Prepend in Blocking Decorator

**Files:**
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/QueryExpandingCaseRetriever.java`
- Test: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/QueryExpandingCaseRetrieverTest.java`

**Interfaces:**
- Consumes: `QueryExpander.expand(RetrievalQuery)`, `RetrievalQuery` record equality
- Produces: unchanged `CaseRetriever` contract — callers see no difference

- [ ] **Step 1: Write failing tests for original query prepend**

Add three tests to `QueryExpandingCaseRetrieverTest`:

```java
@Test
void prependsOriginalWhenExpanderOmitsIt() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    // Expander returns only the expanded query (like LlmQueryExpander)
    QueryExpander hydeExpander = query -> List.of(query.withExpansion("hypothetical"));

    var decorator = new QueryExpandingCaseRetriever(delegate, hydeExpander);
    var results = decorator.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    // Original + expanded = 2 queries fanned out
    assertThat(capturedQueries).hasSize(2);
    // First query is the original (no expansion)
    assertThat(capturedQueries.get(0).expandedText()).isNull();
    assertThat(capturedQueries.get(0).text()).isEqualTo("original");
    // Second is the expanded
    assertThat(capturedQueries.get(1).expandedText()).isEqualTo("hypothetical");
    assertThat(results).hasSize(2);
}

@Test
void doesNotDuplicateOriginalWhenExpanderIncludesIt() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    // StepBack-style: expander already includes original
    var original = RetrievalQuery.of("original");
    QueryExpander stepBackExpander = query -> List.of(query, RetrievalQuery.of("abstract"));

    var decorator = new QueryExpandingCaseRetriever(delegate, stepBackExpander);
    decorator.retrieve(original, CORPUS, 10, null);

    assertThat(capturedQueries).hasSize(2);
    assertThat(capturedQueries.get(0)).isEqualTo(original);
}

@Test
void prependsOriginalForReformulatedQueryWithoutExpansion() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    // Custom expander returns a reformulated query (no withExpansion)
    QueryExpander reformulator = query -> List.of(RetrievalQuery.of("reformulated"));

    var original = RetrievalQuery.of("original");
    var decorator = new QueryExpandingCaseRetriever(delegate, reformulator);
    decorator.retrieve(original, CORPUS, 10, null);

    // Original prepended because contains() uses record equality
    assertThat(capturedQueries).hasSize(2);
    assertThat(capturedQueries.get(0)).isEqualTo(original);
    assertThat(capturedQueries.get(1).text()).isEqualTo("reformulated");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=QueryExpandingCaseRetrieverTest#prependsOriginalWhenExpanderOmitsIt+doesNotDuplicateOriginalWhenExpanderIncludesIt+prependsOriginalForReformulatedQueryWithoutExpansion -DfailIfNoTests=false`

Expected: FAIL — no prepend logic exists yet.

- [ ] **Step 3: Implement original query prepend**

In `QueryExpandingCaseRetriever.retrieve()`, after the existing empty-list
guard (`if (expanded.isEmpty())`), add the original-query prepend:

```java
if (!expanded.contains(query)) {
    var withOriginal = new ArrayList<RetrievalQuery>(expanded.size() + 1);
    withOriginal.add(query);
    withOriginal.addAll(expanded);
    expanded = withOriginal;
}
```

The `expanded` variable must be reassignable — change from `List<RetrievalQuery>`
to `var` or ensure the declaration allows reassignment (it's currently final
from the try-catch; assign to a new local after the guard).

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=QueryExpandingCaseRetrieverTest`

Expected: ALL PASS

- [ ] **Step 5: Update existing tests that assume no prepend**

The existing `delegatesWithExpandedQuery` test expects a single delegate call
when the expander returns one expanded query. After the prepend, it becomes
two calls (original + expanded). Update:

- `delegatesWithExpandedQuery`: now expects 2 delegate calls; assert first is
  original, second has expansion. Results fused via RRF.
- `singleQuerySkipsRrf`: this test returns `query.withExpansion("expanded")`
  which means contains(query) is false (different record). After prepend,
  two queries. Update to expect 2 calls.

- [ ] **Step 6: Run full test suite for rag-expansion**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion`

Expected: ALL PASS

- [ ] **Step 7: Commit**

```
feat(#119): always include original query in blocking expansion decorator

QueryExpandingCaseRetriever now prepends the original query when the
expander omits it, using record equality to avoid duplicates.
```

---

### Task 2: Original Query Prepend in Reactive Decorator

**Files:**
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ReactiveQueryExpandingCaseRetriever.java`
- Test: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/ReactiveQueryExpandingCaseRetrieverTest.java`

**Interfaces:**
- Consumes: same `QueryExpander`, `RetrievalQuery` record equality
- Produces: unchanged `ReactiveCaseRetriever` contract

- [ ] **Step 1: Write failing tests for reactive original query prepend**

Mirror the three tests from Task 1 in `ReactiveQueryExpandingCaseRetrieverTest`:

```java
@Test
void prependsOriginalWhenExpanderOmitsIt() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return Uni.createFrom().item(List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9)));
    };
    QueryExpander hydeExpander = query -> List.of(query.withExpansion("hypothetical"));

    var decorator = new ReactiveQueryExpandingCaseRetriever(delegate, hydeExpander);
    var results = decorator.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null)
        .await().indefinitely();

    assertThat(capturedQueries).hasSize(2);
    assertThat(capturedQueries.get(0).expandedText()).isNull();
    assertThat(capturedQueries.get(0).text()).isEqualTo("original");
    assertThat(capturedQueries.get(1).expandedText()).isEqualTo("hypothetical");
    assertThat(results).hasSize(2);
}

@Test
void doesNotDuplicateOriginalWhenExpanderIncludesIt() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return Uni.createFrom().item(List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9)));
    };
    var original = RetrievalQuery.of("original");
    QueryExpander stepBackExpander = query -> List.of(query, RetrievalQuery.of("abstract"));

    var decorator = new ReactiveQueryExpandingCaseRetriever(delegate, stepBackExpander);
    decorator.retrieve(original, CORPUS, 10, null).await().indefinitely();

    assertThat(capturedQueries).hasSize(2);
    assertThat(capturedQueries.get(0)).isEqualTo(original);
}

@Test
void prependsOriginalForReformulatedQueryWithoutExpansion() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return Uni.createFrom().item(List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9)));
    };
    QueryExpander reformulator = query -> List.of(RetrievalQuery.of("reformulated"));

    var original = RetrievalQuery.of("original");
    var decorator = new ReactiveQueryExpandingCaseRetriever(delegate, reformulator);
    decorator.retrieve(original, CORPUS, 10, null).await().indefinitely();

    assertThat(capturedQueries).hasSize(2);
    assertThat(capturedQueries.get(0)).isEqualTo(original);
    assertThat(capturedQueries.get(1).text()).isEqualTo("reformulated");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=ReactiveQueryExpandingCaseRetrieverTest#prependsOriginalWhenExpanderOmitsIt+doesNotDuplicateOriginalWhenExpanderIncludesIt+prependsOriginalForReformulatedQueryWithoutExpansion -DfailIfNoTests=false`

Expected: FAIL

- [ ] **Step 3: Implement reactive original query prepend**

In `ReactiveQueryExpandingCaseRetriever.retrieve()`, in the `.map()` stage
that handles empty expansion, add the prepend logic:

```java
.map(expanded -> expanded.isEmpty() ? List.of(query) : expanded)
.map(expanded -> {
    if (!expanded.contains(query)) {
        var withOriginal = new ArrayList<RetrievalQuery>(expanded.size() + 1);
        withOriginal.add(query);
        withOriginal.addAll(expanded);
        return withOriginal;
    }
    return expanded;
})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=ReactiveQueryExpandingCaseRetrieverTest`

Expected: ALL PASS (update existing tests same as Task 1 Step 5)

- [ ] **Step 5: Run full rag-expansion module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```
feat(#119): always include original query in reactive expansion decorator

ReactiveQueryExpandingCaseRetriever now prepends the original query when
the expander omits it, matching the blocking decorator behaviour.
```

---

### Task 3: Per-Leg Embedding Separation in HybridCaseRetriever

**Files:**
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/test/java/io/casehub/neocortex/rag/runtime/RagTestFixtures.java` (enhance `StubMultiModalEmbedder` to capture embed calls)
- Test: `rag/src/test/java/io/casehub/neocortex/rag/runtime/HybridCaseRetrieverTest.java`

**Interfaces:**
- Consumes: `MultiModalEmbedder.embed(String)`, `MultiModalEmbedder.embedBatch(List<String>)`, `RetrievalQuery.text()`, `RetrievalQuery.searchText()`, `RetrievalQuery.expandedText()`
- Produces: unchanged `CaseRetriever` contract

- [ ] **Step 1: Enhance StubMultiModalEmbedder to capture embed calls**

Add call tracking to `RagTestFixtures.StubMultiModalEmbedder`:

```java
private final List<String> embedCalls = new ArrayList<>();
private final List<List<String>> batchCalls = new ArrayList<>();

@Override
public MultiModalEmbedding embed(String text) {
    embedCalls.add(text);
    return makeEmbedding();
}

@Override
public List<MultiModalEmbedding> embedBatch(List<String> texts) {
    batchCalls.add(List.copyOf(texts));
    List<MultiModalEmbedding> result = new ArrayList<>(texts.size());
    for (int i = 0; i < texts.size(); i++) {
        result.add(makeEmbedding());
    }
    return result;
}

List<String> embedCalls() { return List.copyOf(embedCalls); }
List<List<String>> batchCalls() { return List.copyOf(batchCalls); }
void clearCalls() { embedCalls.clear(); batchCalls.clear(); }
```

- [ ] **Step 2: Write failing tests for per-leg embedding**

Add to `HybridCaseRetrieverTest`:

```java
@Test
void usesEmbedBatchWhenExpansionActive() {
    MultiModalEmbedder embedder = RagTestFixtures.stubEmbedder(DENSE_DIM, true);
    // Cast to access call tracking
    var stub = (RagTestFixtures.StubMultiModalEmbedder) embedder;

    CorpusRef corpus = uniqueCorpus();
    // Ingest first so collection exists
    var ingestor = new QdrantEmbeddingIngestor(client, embedder,
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        RagTestFixtures.stubConfig());
    ingestor.ingest(corpus, List.of(
        new ChunkInput("test content", "doc-1", Map.of())));

    var retriever = new HybridCaseRetriever(client, embedder,
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        RagTestFixtures.stubConfig());

    stub.clearCalls();

    // Query WITH expansion active
    var expandedQuery = RetrievalQuery.of("original").withExpansion("hypothetical");
    retriever.retrieve(expandedQuery, corpus, 10, null);

    // Should use embedBatch with [searchText, text]
    assertThat(stub.batchCalls()).hasSize(1);
    assertThat(stub.batchCalls().get(0)).containsExactly("hypothetical", "original");
    assertThat(stub.embedCalls()).isEmpty();
}

@Test
void usesSingleEmbedWhenNoExpansion() {
    var stub = RagTestFixtures.stubEmbedder(DENSE_DIM, true);

    CorpusRef corpus = uniqueCorpus();
    var ingestor = new QdrantEmbeddingIngestor(client, stub,
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        RagTestFixtures.stubConfig());
    ingestor.ingest(corpus, List.of(
        new ChunkInput("test content", "doc-1", Map.of())));

    var retriever = new HybridCaseRetriever(client, stub,
        TenantGuard.of(RagTestFixtures.stubPrincipal(TENANT)),
        RagTestFixtures.stubConfig());

    stub.clearCalls();

    // Query WITHOUT expansion
    retriever.retrieve(RetrievalQuery.of("original"), corpus, 10, null);

    // Should use single embed call
    assertThat(stub.embedCalls()).hasSize(1);
    assertThat(stub.embedCalls().get(0)).isEqualTo("original");
    assertThat(stub.batchCalls()).isEmpty();
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest#usesEmbedBatchWhenExpansionActive+usesSingleEmbedWhenNoExpansion -DfailIfNoTests=false`

Expected: FAIL — current code always uses single `embed()`.

- [ ] **Step 4: Implement per-leg embedding separation**

In `HybridCaseRetriever.retrieve()`, replace the single embed call (line 89):

```java
// OLD: MultiModalEmbedding embedding = embedder.embed(query.searchText());
// NEW:
MultiModalEmbedding searchTextEmbedding;
MultiModalEmbedding originalTextEmbedding;
if (query.expandedText() != null) {
    List<MultiModalEmbedding> embeddings = embedder.embedBatch(
        List.of(query.searchText(), query.text()));
    searchTextEmbedding = embeddings.get(0);
    originalTextEmbedding = embeddings.get(1);
} else {
    searchTextEmbedding = embedder.embed(query.searchText());
    originalTextEmbedding = searchTextEmbedding;
}
```

Then update all references in the method:
- Dense leg: `searchTextEmbedding.dense()` (was `embedding.dense()`)
- Sparse leg: `originalTextEmbedding.sparse()` (was `embedding.sparse()`)
- ColBERT: `originalTextEmbedding.colbert()` (was `embedding.colbert()`)
- `hasSparse`: `originalTextEmbedding.sparse() != null`

Apply the same changes in `executeConvexCombinationFusion()` — it receives
the embedding as a parameter, so the method signature changes to accept both:

```java
private List<RetrievedChunk> executeConvexCombinationFusion(
        String collection, RetrievalQuery query,
        MultiModalEmbedding searchTextEmbedding,
        MultiModalEmbedding originalTextEmbedding,
        Optional<Filter> mergedFilter, int maxResults)
```

Dense leg uses `searchTextEmbedding.dense()`, sparse leg uses
`originalTextEmbedding.sparse()`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=HybridCaseRetrieverTest`

Expected: ALL PASS

- [ ] **Step 6: Commit**

```
feat(#113): per-leg embedding separation in HybridCaseRetriever

Dense leg uses searchText() (expanded); sparse and ColBERT use text()
(original). Uses embedBatch() when expansion is active, single embed()
otherwise. Closes the gap between ARC42STORIES C11 documented intent
and actual implementation.
```

---

### Task 4: Per-Leg Embedding Separation in ReactiveHybridCaseRetriever

**Files:**
- Modify: `rag/src/main/java/io/casehub/neocortex/rag/runtime/ReactiveHybridCaseRetriever.java`
- Test: `rag/src/test/java/io/casehub/neocortex/rag/runtime/ReactiveHybridCaseRetrieverTest.java`

**Interfaces:**
- Consumes: same as Task 3
- Produces: unchanged `ReactiveCaseRetriever` contract

- [ ] **Step 1: Write failing tests for reactive per-leg embedding**

Mirror the two tests from Task 3 in `ReactiveHybridCaseRetrieverTest`.
Same patterns: assert `embedBatch` called with `[searchText, text]` when
expansion active, single `embed` when not.

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveHybridCaseRetrieverTest#usesEmbedBatchWhenExpansionActive+usesSingleEmbedWhenNoExpansion -DfailIfNoTests=false`

Expected: FAIL

- [ ] **Step 3: Implement reactive per-leg embedding**

In `ReactiveHybridCaseRetriever.retrieve()`, replace the embed call in the
`Uni.createFrom().item(() -> embedder.embed(query.searchText()))` chain.
The reactive version needs to batch-embed on the worker pool:

```java
.chain(exists -> {
    if (!exists) {
        return Uni.createFrom().item(List.<RetrievedChunk>of());
    }
    if (query.expandedText() != null) {
        return Uni.createFrom().item(() -> embedder.embedBatch(
                List.of(query.searchText(), query.text())))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
            .chain(embeddings -> executeRetrieve(query, collection, mergedFilter,
                embeddings.get(0), embeddings.get(1), maxResults));
    } else {
        return Uni.createFrom().item(() -> embedder.embed(query.searchText()))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
            .chain(embedding -> executeRetrieve(query, collection, mergedFilter,
                embedding, embedding, maxResults));
    }
});
```

Update `executeRetrieve` signature to accept both embeddings:

```java
private Uni<List<RetrievedChunk>> executeRetrieve(
        RetrievalQuery query, String collection,
        Optional<Filter> mergedFilter,
        MultiModalEmbedding searchTextEmbedding,
        MultiModalEmbedding originalTextEmbedding,
        int maxResults)
```

Same routing as Task 3: dense uses `searchTextEmbedding`, sparse/ColBERT
use `originalTextEmbedding`.

Update `executeConvexCombinationFusion` signature the same way.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag -Dtest=ReactiveHybridCaseRetrieverTest`

Expected: ALL PASS

- [ ] **Step 5: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Expected: ALL PASS (964+ tests)

- [ ] **Step 6: Commit**

```
feat(#113): per-leg embedding separation in ReactiveHybridCaseRetriever

Reactive variant matches blocking behaviour — dense leg uses searchText(),
sparse and ColBERT use text(). Uses embedBatch() on the worker pool when
expansion is active.
```

---

### Task 5: ARC42STORIES Update

**Files:**
- Modify: `ARC42STORIES.MD` — C11 section

**Interfaces:**
- Consumes: none
- Produces: none

- [ ] **Step 1: Update C11 to reflect implementation**

ARC42STORIES C11 already documents the dense/sparse split as shipped. The
code now matches. Verify the existing text is accurate — if any line claims
the split is "planned" or "will be implemented", update to present tense.
No change needed if the text already reads as shipped (which is now true).

- [ ] **Step 2: Commit if changed**

```
docs(#113): verify ARC42STORIES C11 dense/sparse split matches implementation
```
