# HyDE Query Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement HyDE (Hypothetical Document Embeddings) query expansion for the RAG pipeline, fixing the overloaded `String query` parameter with a structured `RetrievalQuery` type, and retrofitting CRAG's activation model to classpath + config.

**Architecture:** New `RetrievalQuery` value type replaces `String query` in `CaseRetriever`/`ReactiveCaseRetriever` SPIs, separating embedding text from scoring text. `QueryExpander` SPI in `rag-api` with LLM and template implementations in new `rag-hyde` module. HyDE and CRAG are `@Decorator`s with `@IfBuildProperty` gates — classpath + config activation. Dense embedding uses `searchText()` (hypothetical doc), sparse SPLADE uses `text()` (original query), reranking uses `text()`.

**Tech Stack:** Java 21, Quarkus 3.32.2, LangChain4j 1.14.1 (ChatModel), CDI `@Decorator`, SmallRye Mutiny, SmallRye Config `@ConfigMapping`, JUnit 5, AssertJ

**Build command:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

**Build single module:** `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl <module>`

**Spec:** `specs/2026-06-21-hyde-query-expansion-design.md`

---

### Task 1: RetrievalQuery value type

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/RetrievalQuery.java`
- Create: `rag-api/src/test/java/io/casehub/rag/RetrievalQueryTest.java`

- [ ] **Step 1: Write failing tests for RetrievalQuery**

Create `rag-api/src/test/java/io/casehub/rag/RetrievalQueryTest.java`:

```java
package io.casehub.rag;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RetrievalQueryTest {

    @Test
    void ofCreatesQueryWithNullExpandedText() {
        var query = RetrievalQuery.of("find me something");
        assertThat(query.text()).isEqualTo("find me something");
        assertThat(query.expandedText()).isNull();
    }

    @Test
    void searchTextReturnsTextWhenNoExpansion() {
        var query = RetrievalQuery.of("original");
        assertThat(query.searchText()).isEqualTo("original");
    }

    @Test
    void searchTextReturnsExpandedTextWhenPresent() {
        var query = new RetrievalQuery("original", "hypothetical document about original");
        assertThat(query.searchText()).isEqualTo("hypothetical document about original");
    }

    @Test
    void withExpansionPreservesOriginalText() {
        var original = RetrievalQuery.of("my question");
        var expanded = original.withExpansion("a document answering my question");
        assertThat(expanded.text()).isEqualTo("my question");
        assertThat(expanded.expandedText()).isEqualTo("a document answering my question");
        assertThat(expanded.searchText()).isEqualTo("a document answering my question");
    }

    @Test
    void withExpansionDoesNotMutateOriginal() {
        var original = RetrievalQuery.of("my question");
        original.withExpansion("something");
        assertThat(original.expandedText()).isNull();
    }

    @Test
    void nullTextThrows() {
        assertThatThrownBy(() -> RetrievalQuery.of(null))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void blankTextThrows() {
        assertThatThrownBy(() -> RetrievalQuery.of("  "))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void nullExpandedTextIsAllowed() {
        var query = new RetrievalQuery("question", null);
        assertThat(query.expandedText()).isNull();
        assertThat(query.searchText()).isEqualTo("question");
    }

    @Test
    void recordEquality() {
        var a = new RetrievalQuery("q", "e");
        var b = new RetrievalQuery("q", "e");
        assertThat(a).isEqualTo(b);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalQueryTest`

Expected: Compilation error — `RetrievalQuery` does not exist.

- [ ] **Step 3: Implement RetrievalQuery**

Create `rag-api/src/main/java/io/casehub/rag/RetrievalQuery.java`:

```java
package io.casehub.rag;

/**
 * Carries both the original query and optional pre-retrieval expansion text.
 * {@code expandedText} covers any pre-retrieval query transformation —
 * HyDE hypothetical documents, step-back prompts, template expansions.
 * Not related to CRAG's result-set expansion (higher top-K).
 */
public record RetrievalQuery(String text, String expandedText) {

    public RetrievalQuery {
        if (text == null || text.isBlank())
            throw new IllegalArgumentException("text must not be null or blank");
    }

    public static RetrievalQuery of(String text) {
        return new RetrievalQuery(text, null);
    }

    public String searchText() {
        return expandedText != null ? expandedText : text;
    }

    public RetrievalQuery withExpansion(String expandedText) {
        return new RetrievalQuery(text, expandedText);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api -Dtest=RetrievalQueryTest`

Expected: All 9 tests PASS.

- [ ] **Step 5: Commit**

```
git add rag-api/src/main/java/io/casehub/rag/RetrievalQuery.java rag-api/src/test/java/io/casehub/rag/RetrievalQueryTest.java
git commit -m "feat(#32): RetrievalQuery value type — separates embedding text from scoring text"
```

---

### Task 2: QueryExpander SPI + CaseRetriever / ReactiveCaseRetriever SPI change

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/QueryExpander.java`
- Modify: `rag-api/src/main/java/io/casehub/rag/CaseRetriever.java`
- Modify: `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java`

> **Note:** This commit intentionally breaks downstream modules (`rag`, `rag-crag`, `rag-testing`, examples). They are fixed in Tasks 3–6. Build only `rag-api` until downstream is migrated.

- [ ] **Step 1: Create QueryExpander SPI**

Create `rag-api/src/main/java/io/casehub/rag/QueryExpander.java`:

```java
package io.casehub.rag;

public interface QueryExpander {
    RetrievalQuery expand(RetrievalQuery query);
}
```

- [ ] **Step 2: Change CaseRetriever to accept RetrievalQuery**

Replace `rag-api/src/main/java/io/casehub/rag/CaseRetriever.java` with:

```java
package io.casehub.rag;

import java.util.List;

public interface CaseRetriever {
    List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus, int maxResults, PayloadFilter filter);

    default List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus, int maxResults) {
        return retrieve(query, corpus, maxResults, null);
    }
}
```

- [ ] **Step 3: Change ReactiveCaseRetriever to accept RetrievalQuery**

Replace `rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java` with:

```java
package io.casehub.rag;

import io.smallrye.mutiny.Uni;
import java.util.List;

public interface ReactiveCaseRetriever {
    Uni<List<RetrievedChunk>> retrieve(RetrievalQuery query, CorpusRef corpus, int maxResults, PayloadFilter filter);

    default Uni<List<RetrievedChunk>> retrieve(RetrievalQuery query, CorpusRef corpus, int maxResults) {
        return retrieve(query, corpus, maxResults, null);
    }
}
```

- [ ] **Step 4: Build rag-api to verify interfaces compile**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-api -DskipTests`

Expected: BUILD SUCCESS. Downstream modules are intentionally broken.

- [ ] **Step 5: Commit**

```
git add rag-api/src/main/java/io/casehub/rag/QueryExpander.java rag-api/src/main/java/io/casehub/rag/CaseRetriever.java rag-api/src/main/java/io/casehub/rag/ReactiveCaseRetriever.java
git commit -m "feat(#32): QueryExpander SPI + CaseRetriever String→RetrievalQuery breaking change"
```

---

### Task 3: rag-testing stubs migration + InMemoryQueryExpander

**Files:**
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java`
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCaseRetriever.java`
- Modify: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCaseRetrieverTest.java`
- Modify: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCaseRetrieverTest.java`
- Create: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryQueryExpander.java`
- Create: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryQueryExpanderTest.java`

- [ ] **Step 1: Write InMemoryQueryExpander test**

Create `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryQueryExpanderTest.java`:

```java
package io.casehub.rag.testing;

import io.casehub.rag.RetrievalQuery;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryQueryExpanderTest {

    @Test
    void expandProducesHypotheticalPrefix() {
        var expander = new InMemoryQueryExpander();
        var result = expander.expand(RetrievalQuery.of("what is diabetes?"));
        assertThat(result.text()).isEqualTo("what is diabetes?");
        assertThat(result.expandedText()).isEqualTo("hypothetical: what is diabetes?");
        assertThat(result.searchText()).isEqualTo("hypothetical: what is diabetes?");
    }

    @Test
    void expandRecordsQueriesForAssertions() {
        var expander = new InMemoryQueryExpander();
        expander.expand(RetrievalQuery.of("query1"));
        expander.expand(RetrievalQuery.of("query2"));
        assertThat(expander.expandedQueries()).hasSize(2);
        assertThat(expander.expandedQueries().get(0).text()).isEqualTo("query1");
        assertThat(expander.expandedQueries().get(1).text()).isEqualTo("query2");
    }

    @Test
    void clearResetsRecordedQueries() {
        var expander = new InMemoryQueryExpander();
        expander.expand(RetrievalQuery.of("query1"));
        expander.clear();
        assertThat(expander.expandedQueries()).isEmpty();
    }

    @Test
    void expandPreservesExistingExpansion() {
        var expander = new InMemoryQueryExpander();
        var alreadyExpanded = new RetrievalQuery("original", "prior expansion");
        var result = expander.expand(alreadyExpanded);
        assertThat(result.text()).isEqualTo("original");
        assertThat(result.expandedText()).isEqualTo("hypothetical: original");
    }
}
```

- [ ] **Step 2: Implement InMemoryQueryExpander**

Create `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryQueryExpander.java`:

```java
package io.casehub.rag.testing;

import io.casehub.rag.QueryExpander;
import io.casehub.rag.RetrievalQuery;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;

import java.util.ArrayList;
import java.util.List;

@Alternative
@Priority(1)
@ApplicationScoped
public class InMemoryQueryExpander implements QueryExpander {

    private final List<RetrievalQuery> expandedQueries = new ArrayList<>();

    @Override
    public RetrievalQuery expand(RetrievalQuery query) {
        RetrievalQuery expanded = query.withExpansion("hypothetical: " + query.text());
        expandedQueries.add(expanded);
        return expanded;
    }

    public List<RetrievalQuery> expandedQueries() {
        return List.copyOf(expandedQueries);
    }

    public void clear() {
        expandedQueries.clear();
    }
}
```

- [ ] **Step 3: Update InMemoryCaseRetriever signature**

In `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryCaseRetriever.java`, change the `retrieve` method signature from `String query` to `RetrievalQuery query`. Add the import. The query parameter remains unused — the method body is unchanged.

```java
import io.casehub.rag.RetrievalQuery;

// Change method signature only:
@Override
public List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus, int maxResults, PayloadFilter filter) {
    // ... body unchanged — query is not used ...
}
```

- [ ] **Step 4: Update InMemoryReactiveCaseRetriever signature**

In `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryReactiveCaseRetriever.java`, change:

```java
import io.casehub.rag.RetrievalQuery;

@Override
public Uni<List<RetrievedChunk>> retrieve(RetrievalQuery query, CorpusRef corpus, int maxResults, PayloadFilter filter) {
    return Uni.createFrom().item(() -> delegate.retrieve(query, corpus, maxResults, filter));
}
```

- [ ] **Step 5: Update InMemoryCaseRetrieverTest**

In `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryCaseRetrieverTest.java`, add import and change all `"query"` args in `retrieve()` calls to `RetrievalQuery.of("query")`.

- [ ] **Step 6: Update InMemoryReactiveCaseRetrieverTest**

In `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryReactiveCaseRetrieverTest.java`, add import and change all `"query"` args in `retrieve()` calls to `RetrievalQuery.of("query")`.

- [ ] **Step 7: Build and run rag-testing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-api,rag-testing`

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```
git add rag-testing/
git commit -m "feat(#32): rag-testing stubs — RetrievalQuery migration + InMemoryQueryExpander"
```

---

### Task 4: HybridCaseRetriever + ReactiveHybridCaseRetriever — dense/sparse split

**Files:**
- Modify: `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`
- Modify: `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetriever.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`
- Modify: `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`

- [ ] **Step 1: Update HybridCaseRetriever**

In `rag/src/main/java/io/casehub/rag/runtime/HybridCaseRetriever.java`:

1. Add import: `import io.casehub.rag.RetrievalQuery;`
2. Change method signature: `String query` → `RetrievalQuery query`
3. Dense embedding line: change `embeddingModel.embed(TextSegment.from(query))` → `embeddingModel.embed(TextSegment.from(query.searchText()))`
4. Sparse embedding line: change `sparseEmbedder.embed(query)` → `sparseEmbedder.embed(query.text())`
5. Reranking line: change `reranker.rerank(query, texts)` → `reranker.rerank(query.text(), texts)`

- [ ] **Step 2: Update ReactiveHybridCaseRetriever**

In `rag/src/main/java/io/casehub/rag/runtime/ReactiveHybridCaseRetriever.java`:

1. Add import: `import io.casehub.rag.RetrievalQuery;`
2. Change `retrieve` method signature: `String query` → `RetrievalQuery query`
3. Change `embedQuery` to take `RetrievalQuery query` parameter
4. In `embedQuery`: `embeddingModel.embed(TextSegment.from(query.searchText()))` for dense, `sparseEmbedder.embed(query.text())` for sparse
5. Change `maybeRerank` to take `RetrievalQuery query` parameter
6. In `maybeRerank`: `reranker.rerank(query.text(), texts)`
7. Update the `Uni` chain in `retrieve` to pass the full `query` to `embedQuery` and `maybeRerank`

- [ ] **Step 3: Update BlockingToReactiveCaseRetriever**

In `rag/src/main/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetriever.java`:

1. Add import: `import io.casehub.rag.RetrievalQuery;`
2. Change method signature: `String query` → `RetrievalQuery query`

Body passes `query` through unchanged.

- [ ] **Step 4: Update HybridCaseRetrieverTest**

In `rag/src/test/java/io/casehub/rag/runtime/HybridCaseRetrieverTest.java`:

1. Add import: `import io.casehub.rag.RetrievalQuery;`
2. Change all `"query"` string args in `.retrieve(...)` calls to `RetrievalQuery.of("query")` (or whatever the test query string is — match exactly)
3. Any lambda-based `CaseRetriever` stubs: change `(query, corpus, maxResults, filter)` parameter type from implicit `String` to match the new SPI

- [ ] **Step 5: Update ReactiveHybridCaseRetrieverTest**

Same migration as Step 4 but in `rag/src/test/java/io/casehub/rag/runtime/ReactiveHybridCaseRetrieverTest.java`.

- [ ] **Step 6: Update BlockingToReactiveCaseRetrieverTest**

Same migration in `rag/src/test/java/io/casehub/rag/runtime/BlockingToReactiveCaseRetrieverTest.java`.

- [ ] **Step 7: Build and run rag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-api,rag-testing,rag`

Expected: All tests PASS.

- [ ] **Step 8: Commit**

```
git add rag/
git commit -m "feat(#32): HybridCaseRetriever — searchText() for dense, text() for sparse + reranking"
```

---

### Task 5: CRAG retrofit — @IfBuildProperty + RetrievalQuery

**Files:**
- Modify: `rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java`
- Modify: `rag-crag/src/main/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetriever.java`
- Modify: `rag-crag/src/main/java/io/casehub/rag/crag/CragBeanProducer.java`
- Modify: `rag-crag/src/main/java/io/casehub/rag/crag/CragConfig.java`
- Modify: `rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java`
- Modify: `rag-crag/src/test/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetrieverTest.java`
- Modify: `rag-crag/pom.xml` (add quarkus-arc dependency for @IfBuildProperty)

- [ ] **Step 1: Add enabled property to CragConfig**

In `rag-crag/src/main/java/io/casehub/rag/crag/CragConfig.java`, add:

```java
@WithDefault("false")
boolean enabled();
```

- [ ] **Step 2: Add @IfBuildProperty to CorrectiveCaseRetriever**

In `rag-crag/src/main/java/io/casehub/rag/crag/CorrectiveCaseRetriever.java`:

1. Add import: `import io.casehub.rag.RetrievalQuery;` and `import io.quarkus.arc.properties.IfBuildProperty;`
2. Add `@IfBuildProperty(name = "casehub.rag.crag.enabled", stringValue = "true")` to the class
3. Change method signature: `String query` → `RetrievalQuery query`
4. Change `evaluator.evaluateBatch(query, contents)` → `evaluator.evaluateBatch(query.text(), contents)` (two occurrences — initial and expansion)
5. The `delegate.retrieve(query, corpus, ...)` calls pass through `query` unchanged — the full `RetrievalQuery` preserves any HyDE expansion for the retriever

- [ ] **Step 3: Add @IfBuildProperty to ReactiveCorrectiveCaseRetriever**

Same changes as Step 2 but in `rag-crag/src/main/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetriever.java`.

- [ ] **Step 4: Add @IfBuildProperty to CragBeanProducer**

In `rag-crag/src/main/java/io/casehub/rag/crag/CragBeanProducer.java`:

1. Add import: `import io.quarkus.arc.properties.IfBuildProperty;`
2. Add `@IfBuildProperty(name = "casehub.rag.crag.enabled", stringValue = "true")` to the class

- [ ] **Step 5: Add quarkus-arc dependency to rag-crag pom.xml**

In `rag-crag/pom.xml`, add the `quarkus-arc` dependency (provides `@IfBuildProperty`):

```xml
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-arc</artifactId>
    <scope>provided</scope>
</dependency>
```

- [ ] **Step 6: Update CorrectiveCaseRetrieverTest**

In `rag-crag/src/test/java/io/casehub/rag/crag/CorrectiveCaseRetrieverTest.java`:

1. Add import: `import io.casehub.rag.RetrievalQuery;`
2. Change all `"query"` string args in `.retrieve(...)` calls to `RetrievalQuery.of("query")`
3. Lambda-based `CaseRetriever` stubs: first parameter changes from implicit `String` to `RetrievalQuery` — e.g., `(query, corpus, maxResults, filter) -> { ... }` stays the same shape but the type of `query` is now `RetrievalQuery`
4. Update `stubConfig` — add `@Override public boolean enabled() { return true; }` to the anonymous implementation
5. Add test verifying CRAG evaluates with `text()` not `searchText()` when expansion is present:

```java
@Test
void evaluatesAgainstOriginalQueryNotExpansion() {
    var delegate = fixedRetriever(chunk("content", "doc1", 0.9));
    var capturedQuery = new AtomicReference<String>();
    RelevanceEvaluator capturingEvaluator = (query, content) -> {
        capturedQuery.set(query);
        return RelevanceGrade.CORRECT;
    };
    var quality = new AtomicReference<RetrievalQuality>();
    var retriever = new CorrectiveCaseRetriever(
        delegate, capturingEvaluator, stubConfig(3), capturingEvent(quality));

    var expandedQuery = new RetrievalQuery("original question", "hypothetical document about original question");
    retriever.retrieve(expandedQuery, CORPUS, 10, null);

    assertThat(capturedQuery.get()).isEqualTo("original question");
}
```

- [ ] **Step 7: Update ReactiveCorrectiveCaseRetrieverTest**

Same migration as Step 6 but in `rag-crag/src/test/java/io/casehub/rag/crag/ReactiveCorrectiveCaseRetrieverTest.java`. Include the equivalent async test verifying evaluation uses `text()`.

- [ ] **Step 8: Build and run rag-crag tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-api,rag-testing,rag-crag`

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```
git add rag-crag/
git commit -m "feat(#32): CRAG retrofit — @IfBuildProperty gate + RetrievalQuery migration"
```

---

### Task 6: rag-hyde module — pom.xml + HydeConfig

**Files:**
- Create: `rag-hyde/pom.xml`
- Create: `rag-hyde/src/main/java/io/casehub/rag/hyde/HydeConfig.java`
- Modify: `pom.xml` (parent — add module + managed dependency)

- [ ] **Step 1: Create rag-hyde/pom.xml**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>

  <artifactId>casehub-rag-hyde</artifactId>
  <name>CaseHub Neural Text - RAG HyDE</name>
  <description>HyDE (Hypothetical Document Embeddings) — CDI @Decorator on CaseRetriever that expands queries via QueryExpander SPI before retrieval. Classpath + config activated.</description>

  <dependencies>

    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-rag-api</artifactId>
    </dependency>

    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j-core</artifactId>
    </dependency>

    <dependency>
      <groupId>jakarta.enterprise</groupId>
      <artifactId>jakarta.enterprise.cdi-api</artifactId>
      <scope>provided</scope>
    </dependency>

    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
      <scope>provided</scope>
    </dependency>

    <dependency>
      <groupId>io.smallrye.config</groupId>
      <artifactId>smallrye-config-core</artifactId>
      <scope>provided</scope>
    </dependency>

    <dependency>
      <groupId>io.smallrye.reactive</groupId>
      <artifactId>mutiny</artifactId>
      <scope>provided</scope>
    </dependency>

    <!-- Testing -->
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-rag-testing</artifactId>
      <scope>test</scope>
    </dependency>

  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>io.smallrye</groupId>
        <artifactId>jandex-maven-plugin</artifactId>
        <executions>
          <execution>
            <id>make-index</id>
            <goals><goal>jandex</goal></goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>

</project>
```

- [ ] **Step 2: Add rag-hyde to parent pom.xml**

In `pom.xml` (root), add `<module>rag-hyde</module>` after `<module>rag-crag</module>` in the `<modules>` section.

Add managed dependency in `<dependencyManagement>`:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-rag-hyde</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Create HydeConfig**

Create `rag-hyde/src/main/java/io/casehub/rag/hyde/HydeConfig.java`:

```java
package io.casehub.rag.hyde;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

import java.util.Optional;

@ConfigMapping(prefix = "casehub.rag.hyde")
public interface HydeConfig {

    @WithDefault("false")
    boolean enabled();

    @WithDefault("llm")
    String mode();

    Optional<String> promptTemplate();

    Optional<String> template();
}
```

- [ ] **Step 4: Build to verify module wiring**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-hyde -DskipTests`

Expected: BUILD SUCCESS.

- [ ] **Step 5: Commit**

```
git add rag-hyde/ pom.xml
git commit -m "feat(#32): rag-hyde module scaffold — pom.xml + HydeConfig"
```

---

### Task 7: rag-hyde QueryExpander implementations

**Files:**
- Create: `rag-hyde/src/main/java/io/casehub/rag/hyde/LlmQueryExpander.java`
- Create: `rag-hyde/src/main/java/io/casehub/rag/hyde/TemplateQueryExpander.java`
- Create: `rag-hyde/src/test/java/io/casehub/rag/hyde/LlmQueryExpanderTest.java`
- Create: `rag-hyde/src/test/java/io/casehub/rag/hyde/TemplateQueryExpanderTest.java`

- [ ] **Step 1: Write LlmQueryExpander test**

Create `rag-hyde/src/test/java/io/casehub/rag/hyde/LlmQueryExpanderTest.java`:

```java
package io.casehub.rag.hyde;

import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.request.ChatRequest;
import dev.langchain4j.model.chat.response.ChatResponse;
import io.casehub.rag.RetrievalQuery;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class LlmQueryExpanderTest {

    @Test
    void expandCallsChatModelWithDefaultPrompt() {
        var capturedPrompt = new String[1];
        ChatModel mockModel = prompt -> {
            capturedPrompt[0] = prompt;
            return "Diabetes is a chronic condition characterized by elevated blood sugar.";
        };

        var expander = new LlmQueryExpander(mockModel, stubConfig(Optional.empty()));
        var result = expander.expand(RetrievalQuery.of("what is diabetes?"));

        assertThat(result.text()).isEqualTo("what is diabetes?");
        assertThat(result.expandedText()).isEqualTo(
            "Diabetes is a chronic condition characterized by elevated blood sugar.");
        assertThat(capturedPrompt[0]).contains("what is diabetes?");
        assertThat(capturedPrompt[0]).contains("write a short passage");
    }

    @Test
    void expandUsesCustomPromptTemplate() {
        ChatModel mockModel = prompt -> "custom response";
        var expander = new LlmQueryExpander(mockModel,
            stubConfig(Optional.of("Custom: %s")));
        var result = expander.expand(RetrievalQuery.of("test query"));

        assertThat(result.expandedText()).isEqualTo("custom response");
    }

    @Test
    void expandPreservesOriginalText() {
        ChatModel mockModel = prompt -> "hypothetical passage";
        var expander = new LlmQueryExpander(mockModel, stubConfig(Optional.empty()));

        var query = RetrievalQuery.of("my question");
        var result = expander.expand(query);

        assertThat(result.text()).isEqualTo("my question");
        assertThat(result.searchText()).isEqualTo("hypothetical passage");
    }

    private static HydeConfig stubConfig(Optional<String> promptTemplate) {
        return new HydeConfig() {
            @Override public boolean enabled() { return true; }
            @Override public String mode() { return "llm"; }
            @Override public Optional<String> promptTemplate() { return promptTemplate; }
            @Override public Optional<String> template() { return Optional.empty(); }
        };
    }
}
```

- [ ] **Step 2: Implement LlmQueryExpander**

Create `rag-hyde/src/main/java/io/casehub/rag/hyde/LlmQueryExpander.java`:

```java
package io.casehub.rag.hyde;

import dev.langchain4j.model.chat.ChatModel;
import io.casehub.rag.QueryExpander;
import io.casehub.rag.RetrievalQuery;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
@IfBuildProperty(name = "casehub.rag.hyde.mode", stringValue = "llm", enableIfMissing = true)
public class LlmQueryExpander implements QueryExpander {

    static final String DEFAULT_PROMPT =
        "Given the question below, write a short passage (3-5 sentences) "
            + "that would directly answer it. Write as if the passage comes from "
            + "an authoritative document. Do not include the question itself.\n\n"
            + "Question: %s\n\nPassage:";

    private final ChatModel chatModel;
    private final HydeConfig config;

    @Inject
    public LlmQueryExpander(ChatModel chatModel, HydeConfig config) {
        this.chatModel = chatModel;
        this.config = config;
    }

    @Override
    public RetrievalQuery expand(RetrievalQuery query) {
        String prompt = config.promptTemplate().orElse(DEFAULT_PROMPT)
            .formatted(query.text());
        String hypothetical = chatModel.chat(prompt);
        return query.withExpansion(hypothetical);
    }
}
```

- [ ] **Step 3: Run LlmQueryExpander tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-hyde -Dtest=LlmQueryExpanderTest`

Expected: All 3 tests PASS.

- [ ] **Step 4: Write TemplateQueryExpander test**

Create `rag-hyde/src/test/java/io/casehub/rag/hyde/TemplateQueryExpanderTest.java`:

```java
package io.casehub.rag.hyde;

import io.casehub.rag.RetrievalQuery;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class TemplateQueryExpanderTest {

    @Test
    void expandUsesDefaultTemplate() {
        var expander = new TemplateQueryExpander(stubConfig(Optional.empty()));
        var result = expander.expand(RetrievalQuery.of("what is diabetes?"));

        assertThat(result.text()).isEqualTo("what is diabetes?");
        assertThat(result.expandedText()).contains("what is diabetes?");
        assertThat(result.expandedText()).contains("A document that answers");
    }

    @Test
    void expandUsesCustomTemplate() {
        var expander = new TemplateQueryExpander(
            stubConfig(Optional.of("Product matching query: %s")));
        var result = expander.expand(RetrievalQuery.of("SKU-123"));

        assertThat(result.expandedText()).isEqualTo("Product matching query: SKU-123");
    }

    @Test
    void expandPreservesOriginalText() {
        var expander = new TemplateQueryExpander(stubConfig(Optional.empty()));
        var result = expander.expand(RetrievalQuery.of("test"));

        assertThat(result.text()).isEqualTo("test");
    }

    private static HydeConfig stubConfig(Optional<String> template) {
        return new HydeConfig() {
            @Override public boolean enabled() { return true; }
            @Override public String mode() { return "template"; }
            @Override public Optional<String> promptTemplate() { return Optional.empty(); }
            @Override public Optional<String> template() { return template; }
        };
    }
}
```

- [ ] **Step 5: Implement TemplateQueryExpander**

Create `rag-hyde/src/main/java/io/casehub/rag/hyde/TemplateQueryExpander.java`:

```java
package io.casehub.rag.hyde;

import io.casehub.rag.QueryExpander;
import io.casehub.rag.RetrievalQuery;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@ApplicationScoped
@IfBuildProperty(name = "casehub.rag.hyde.mode", stringValue = "template")
public class TemplateQueryExpander implements QueryExpander {

    static final String DEFAULT_TEMPLATE =
        "A document that answers the question \"%s\" would contain the following information:";

    private final HydeConfig config;

    @Inject
    public TemplateQueryExpander(HydeConfig config) {
        this.config = config;
    }

    @Override
    public RetrievalQuery expand(RetrievalQuery query) {
        String expanded = config.template().orElse(DEFAULT_TEMPLATE)
            .formatted(query.text());
        return query.withExpansion(expanded);
    }
}
```

- [ ] **Step 6: Run TemplateQueryExpander tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-hyde -Dtest=TemplateQueryExpanderTest`

Expected: All 3 tests PASS.

- [ ] **Step 7: Commit**

```
git add rag-hyde/src/
git commit -m "feat(#32): LlmQueryExpander + TemplateQueryExpander — QueryExpander implementations"
```

---

### Task 8: rag-hyde decorators — HydeCaseRetriever + ReactiveHydeCaseRetriever

**Files:**
- Create: `rag-hyde/src/main/java/io/casehub/rag/hyde/HydeCaseRetriever.java`
- Create: `rag-hyde/src/main/java/io/casehub/rag/hyde/ReactiveHydeCaseRetriever.java`
- Create: `rag-hyde/src/test/java/io/casehub/rag/hyde/HydeCaseRetrieverTest.java`
- Create: `rag-hyde/src/test/java/io/casehub/rag/hyde/ReactiveHydeCaseRetrieverTest.java`

- [ ] **Step 1: Write HydeCaseRetriever test**

Create `rag-hyde/src/test/java/io/casehub/rag/hyde/HydeCaseRetrieverTest.java`:

```java
package io.casehub.rag.hyde;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.QueryExpander;
import io.casehub.rag.RetrievalQuery;
import io.casehub.rag.RetrievedChunk;
import io.casehub.rag.testing.InMemoryCaseRetriever;
import io.casehub.rag.testing.InMemoryQueryExpander;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class HydeCaseRetrieverTest {

    private static final CorpusRef CORPUS = new CorpusRef("tenant-1", "test-corpus");

    @Test
    void delegatesWithExpandedQuery() {
        var capturedQuery = new AtomicReference<RetrievalQuery>();
        CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            capturedQuery.set(query);
            return List.of(chunk("result", "doc1", 0.9));
        };
        var expander = new InMemoryQueryExpander();

        var hyde = new HydeCaseRetriever(delegate, expander);
        var results = hyde.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

        assertThat(results).hasSize(1);
        assertThat(capturedQuery.get().text()).isEqualTo("original");
        assertThat(capturedQuery.get().expandedText()).isEqualTo("hypothetical: original");
        assertThat(capturedQuery.get().searchText()).isEqualTo("hypothetical: original");
    }

    @Test
    void failSafeOnExpanderError() {
        var capturedQuery = new AtomicReference<RetrievalQuery>();
        CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            capturedQuery.set(query);
            return List.of(chunk("result", "doc1", 0.9));
        };
        QueryExpander failingExpander = query -> {
            throw new RuntimeException("LLM timeout");
        };

        var hyde = new HydeCaseRetriever(delegate, failingExpander);
        var results = hyde.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

        assertThat(results).hasSize(1);
        assertThat(capturedQuery.get().text()).isEqualTo("original");
        assertThat(capturedQuery.get().expandedText()).isNull();
    }

    @Test
    void passesCorpusAndFilterThrough() {
        var capturedCorpus = new AtomicReference<CorpusRef>();
        var capturedMax = new int[1];
        CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            capturedCorpus.set(corpus);
            capturedMax[0] = maxResults;
            return List.of();
        };

        var hyde = new HydeCaseRetriever(delegate, new InMemoryQueryExpander());
        hyde.retrieve(RetrievalQuery.of("q"), CORPUS, 7, null);

        assertThat(capturedCorpus.get()).isEqualTo(CORPUS);
        assertThat(capturedMax[0]).isEqualTo(7);
    }

    private static RetrievedChunk chunk(String content, String docId, double score) {
        return new RetrievedChunk(content, docId, score, Map.of());
    }
}
```

- [ ] **Step 2: Implement HydeCaseRetriever**

Create `rag-hyde/src/main/java/io/casehub/rag/hyde/HydeCaseRetriever.java`:

```java
package io.casehub.rag.hyde;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.PayloadFilter;
import io.casehub.rag.QueryExpander;
import io.casehub.rag.RetrievalQuery;
import io.casehub.rag.RetrievedChunk;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

@Decorator
@Priority(200)
@IfBuildProperty(name = "casehub.rag.hyde.enabled", stringValue = "true")
public class HydeCaseRetriever implements CaseRetriever {

    private static final Logger LOG = Logger.getLogger(HydeCaseRetriever.class.getName());

    private final CaseRetriever delegate;
    private final QueryExpander expander;

    @Inject
    public HydeCaseRetriever(@Delegate @Any CaseRetriever delegate,
                             QueryExpander expander) {
        this.delegate = delegate;
        this.expander = expander;
    }

    @Override
    public List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus,
                                          int maxResults, PayloadFilter filter) {
        RetrievalQuery expanded;
        try {
            expanded = expander.expand(query);
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Query expansion failed, using original query", e);
            expanded = query;
        }
        return delegate.retrieve(expanded, corpus, maxResults, filter);
    }
}
```

- [ ] **Step 3: Run HydeCaseRetriever tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-hyde -Dtest=HydeCaseRetrieverTest`

Expected: All 3 tests PASS.

- [ ] **Step 4: Write ReactiveHydeCaseRetriever test**

Create `rag-hyde/src/test/java/io/casehub/rag/hyde/ReactiveHydeCaseRetrieverTest.java`:

```java
package io.casehub.rag.hyde;

import io.casehub.rag.CorpusRef;
import io.casehub.rag.QueryExpander;
import io.casehub.rag.ReactiveCaseRetriever;
import io.casehub.rag.RetrievalQuery;
import io.casehub.rag.RetrievedChunk;
import io.casehub.rag.testing.InMemoryQueryExpander;
import io.smallrye.mutiny.Uni;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;

class ReactiveHydeCaseRetrieverTest {

    private static final CorpusRef CORPUS = new CorpusRef("tenant-1", "test-corpus");

    @Test
    void delegatesWithExpandedQuery() {
        var capturedQuery = new AtomicReference<RetrievalQuery>();
        ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            capturedQuery.set(query);
            return Uni.createFrom().item(List.of(chunk("result", "doc1", 0.9)));
        };

        var hyde = new ReactiveHydeCaseRetriever(delegate, new InMemoryQueryExpander());
        var results = hyde.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null)
            .await().indefinitely();

        assertThat(results).hasSize(1);
        assertThat(capturedQuery.get().text()).isEqualTo("original");
        assertThat(capturedQuery.get().expandedText()).isEqualTo("hypothetical: original");
    }

    @Test
    void failSafeOnExpanderError() {
        var capturedQuery = new AtomicReference<RetrievalQuery>();
        ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
            capturedQuery.set(query);
            return Uni.createFrom().item(List.of(chunk("result", "doc1", 0.9)));
        };
        QueryExpander failingExpander = query -> {
            throw new RuntimeException("LLM timeout");
        };

        var hyde = new ReactiveHydeCaseRetriever(delegate, failingExpander);
        var results = hyde.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null)
            .await().indefinitely();

        assertThat(results).hasSize(1);
        assertThat(capturedQuery.get().expandedText()).isNull();
    }

    private static RetrievedChunk chunk(String content, String docId, double score) {
        return new RetrievedChunk(content, docId, score, Map.of());
    }
}
```

- [ ] **Step 5: Implement ReactiveHydeCaseRetriever**

Create `rag-hyde/src/main/java/io/casehub/rag/hyde/ReactiveHydeCaseRetriever.java`:

```java
package io.casehub.rag.hyde;

import io.casehub.rag.CorpusRef;
import io.casehub.rag.PayloadFilter;
import io.casehub.rag.QueryExpander;
import io.casehub.rag.ReactiveCaseRetriever;
import io.casehub.rag.RetrievalQuery;
import io.casehub.rag.RetrievedChunk;
import io.quarkus.arc.properties.IfBuildProperty;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

@Decorator
@Priority(200)
@IfBuildProperty(name = "casehub.rag.hyde.enabled", stringValue = "true")
public class ReactiveHydeCaseRetriever implements ReactiveCaseRetriever {

    private static final Logger LOG = Logger.getLogger(ReactiveHydeCaseRetriever.class.getName());

    private final ReactiveCaseRetriever delegate;
    private final QueryExpander expander;

    @Inject
    public ReactiveHydeCaseRetriever(@Delegate @Any ReactiveCaseRetriever delegate,
                                     QueryExpander expander) {
        this.delegate = delegate;
        this.expander = expander;
    }

    @Override
    public Uni<List<RetrievedChunk>> retrieve(RetrievalQuery query, CorpusRef corpus,
                                               int maxResults, PayloadFilter filter) {
        return Uni.createFrom().item(() -> expander.expand(query))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
            .onFailure().recoverWithItem(t -> {
                LOG.log(Level.WARNING, "Query expansion failed, using original query", t);
                return query;
            })
            .chain(expanded -> delegate.retrieve(expanded, corpus, maxResults, filter));
    }
}
```

- [ ] **Step 6: Run ReactiveHydeCaseRetriever tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-hyde -Dtest=ReactiveHydeCaseRetrieverTest`

Expected: All 2 tests PASS.

- [ ] **Step 7: Run all rag-hyde tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl rag-hyde`

Expected: All 11 tests PASS (3 LlmQueryExpander + 3 TemplateQueryExpander + 3 HydeCaseRetriever + 2 ReactiveHydeCaseRetriever).

- [ ] **Step 8: Commit**

```
git add rag-hyde/src/
git commit -m "feat(#32): HydeCaseRetriever + ReactiveHydeCaseRetriever — @Decorator @Priority(200) with fail-safe"
```

---

### Task 9: Example migration + full build verification

**Files:**
- Modify: `examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag/HybridSearchDemo.java`
- Modify: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/RagPipelineIT.java`
- Modify: any other files in examples that call `CaseRetriever.retrieve()` with a `String`

- [ ] **Step 1: Update HybridSearchDemo**

In `examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag/HybridSearchDemo.java`:

1. Add import: `import io.casehub.rag.RetrievalQuery;`
2. Change all `.retrieve("...", ...)` calls to `.retrieve(RetrievalQuery.of("..."), ...)`

- [ ] **Step 2: Update RagPipelineIT**

In `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/RagPipelineIT.java`:

1. Add import: `import io.casehub.rag.RetrievalQuery;`
2. Change all `.retrieve("...", ...)` calls to `.retrieve(RetrievalQuery.of("..."), ...)`

- [ ] **Step 3: Full build — all modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Expected: BUILD SUCCESS — all modules compile, all tests pass.

- [ ] **Step 4: Commit**

```
git add examples/
git commit -m "chore(#32): example migration — String→RetrievalQuery"
```

---

### Task 10: CLAUDE.md + ARC42STORIES updates

**Files:**
- Modify: `CLAUDE.md`
- Modify: `ARC42STORIES.MD`

- [ ] **Step 1: Update CLAUDE.md**

Add `rag-hyde` to the module structure section:

```
rag-hyde/           — HyDE (Hypothetical Document Embeddings) query expansion; LLM + template expanders; @Decorator on CaseRetriever, classpath + config activated
```

Add Maven coordinates:

```
| RAG HyDE | `casehub-rag-hyde` |
```

Add root Java package:

```
| Root Java package (rag-hyde) | `io.casehub.rag.hyde` |
```

Update rag-crag description to mention "classpath + config activated" instead of "classpath-activated".

Update rag-api description to mention `RetrievalQuery`, `QueryExpander`.

- [ ] **Step 2: Update ARC42STORIES.MD**

Apply the update plan from the spec:

1. Add L11 HyDE row to the Layers table
2. Add C11 to the chapter index table and flow diagram
3. Update L10 description: "classpath-activated" → "classpath + config activated"
4. Add C11 column to the Layer × Chapter matrix
5. Update §9.1 Journey Overview for J4
6. Add C11 chapter entry in §9.3
7. Update §5 Building Block View to include rag-hyde container and relations
8. Add chapter sequencing rationale for C11

- [ ] **Step 3: Commit**

```
git add CLAUDE.md ARC42STORIES.MD
git commit -m "docs: sync CLAUDE.md + ARC42STORIES.MD — HyDE module, L11, C11, CRAG activation change (#32)"
```

---
