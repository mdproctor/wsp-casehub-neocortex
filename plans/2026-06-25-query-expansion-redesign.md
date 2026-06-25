# Query Expansion Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename `rag-hyde` → `rag-expansion`, change `QueryExpander` SPI to return `List<RetrievalQuery>`, add `StepBackQueryExpander` (#43), extend `LlmQueryExpander` with multi-query support (#42), and add application-level RRF fusion.

**Architecture:** The `QueryExpander` SPI in `rag-api` changes its return type from single `RetrievalQuery` to `List<RetrievalQuery>`. A new `RrfFusion` utility in `rag-api` merges multiple ranked result sets. The `rag-hyde` module is renamed to `rag-expansion` with all classes renamed to reflect generic query expansion. The decorator handles single-query fast path and multi-query fan-out + RRF merge. Two new behaviors: `StepBackQueryExpander` (returns original + abstract) and multi-query `LlmQueryExpander` (returns N hypothetical documents).

**Tech Stack:** Java 21, Quarkus 3.32.2 (CDI decorators, SmallRye Config), LangChain4j 1.14.1 (`ChatModel`), Mutiny (`Uni`), JUnit 5 + AssertJ

## Global Constraints

- Java 21 source, Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build: `mvn` not `./mvnw`; always scope with `-pl <module>`
- groupId: `io.casehub`, version: `0.2-SNAPSHOT`
- All commits reference issues: `#43` and/or `#42`
- IntelliJ MCP for all renames/moves — never bash `mv` for source files
- Module tests: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl <module> --batch-mode`
- Jandex plugin required in rag-expansion for CDI bean discovery as JAR
- Reactive parity: every blocking decorator/SPI change must have a reactive counterpart

---

### Task 1: RRF Fusion Utility in rag-api

Add `RrfFusion` — pure Java utility for merging N ranked result sets via Reciprocal Rank Fusion. This has no dependencies on other changes and is consumed by later tasks.

**Files:**
- Create: `rag-api/src/main/java/io/casehub/rag/RrfFusion.java`
- Create: `rag-api/src/test/java/io/casehub/rag/RrfFusionTest.java`

**Interfaces:**
- Consumes: `RetrievedChunk` record (existing in rag-api), `RelevanceGrade` enum (existing)
- Produces: `RrfFusion.fuse(List<List<RetrievedChunk>>, int): List<RetrievedChunk>` and `RrfFusion.fuse(List<List<RetrievedChunk>>, int, int): List<RetrievedChunk>`

- [ ] **Step 1: Write failing tests**

```java
// rag-api/src/test/java/io/casehub/rag/RrfFusionTest.java
package io.casehub.rag;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class RrfFusionTest {

    @Test
    void fuseSingleListReturnsSameOrder() {
        var chunks = List.of(chunk("a", "doc1", 0.9), chunk("b", "doc2", 0.8));
        var result = RrfFusion.fuse(List.of(chunks), 10);
        assertThat(result).hasSize(2);
        assertThat(result.get(0).content()).isEqualTo("a");
        assertThat(result.get(1).content()).isEqualTo("b");
    }

    @Test
    void fuseTwoListsMergesAndDeduplicates() {
        var list1 = List.of(chunk("a", "doc1", 0.9), chunk("b", "doc2", 0.8));
        var list2 = List.of(chunk("b", "doc2", 0.7), chunk("c", "doc3", 0.6));
        var result = RrfFusion.fuse(List.of(list1, list2), 10);
        assertThat(result).hasSize(3);
        // "b" appears in both lists → highest RRF score (rank 1 in list1 + rank 0 in list2)
        assertThat(result.get(0).content()).isEqualTo("b");
    }

    @Test
    void fuseRespectsMaxResults() {
        var list1 = List.of(chunk("a", "doc1", 0.9), chunk("b", "doc2", 0.8));
        var list2 = List.of(chunk("c", "doc3", 0.7), chunk("d", "doc4", 0.6));
        var result = RrfFusion.fuse(List.of(list1, list2), 2);
        assertThat(result).hasSize(2);
    }

    @Test
    void fuseEmptyListsReturnsEmpty() {
        var result = RrfFusion.fuse(List.of(), 10);
        assertThat(result).isEmpty();
    }

    @Test
    void fuseTakesBestGradeForDuplicates() {
        var list1 = List.of(new RetrievedChunk("a", "doc1", 0.9, Map.of(), RelevanceGrade.AMBIGUOUS));
        var list2 = List.of(new RetrievedChunk("a", "doc1", 0.8, Map.of(), RelevanceGrade.CORRECT));
        var result = RrfFusion.fuse(List.of(list1, list2), 10);
        assertThat(result).hasSize(1);
        assertThat(result.get(0).grade()).isEqualTo(RelevanceGrade.CORRECT);
    }

    @Test
    void fusePreservesMetadataFromFirstOccurrence() {
        var list1 = List.of(new RetrievedChunk("a", "doc1", 0.9, Map.of("key", "val1")));
        var list2 = List.of(new RetrievedChunk("a", "doc1", 0.8, Map.of("key", "val2")));
        var result = RrfFusion.fuse(List.of(list1, list2), 10);
        assertThat(result.get(0).metadata().get("key")).isEqualTo("val1");
    }

    @Test
    void fuseWithCustomK() {
        var list1 = List.of(chunk("a", "doc1", 0.9));
        var list2 = List.of(chunk("a", "doc1", 0.8));
        var resultK60 = RrfFusion.fuse(List.of(list1, list2), 10, 60);
        var resultK1 = RrfFusion.fuse(List.of(list1, list2), 10, 1);
        // Lower K amplifies rank differences
        assertThat(resultK1.get(0).relevanceScore()).isGreaterThan(resultK60.get(0).relevanceScore());
    }

    @Test
    void gradeOrderingCorrectBeatsAmbiguous() {
        var list1 = List.of(new RetrievedChunk("a", "doc1", 0.9, Map.of(), RelevanceGrade.INCORRECT));
        var list2 = List.of(new RetrievedChunk("a", "doc1", 0.8, Map.of(), RelevanceGrade.AMBIGUOUS));
        var result = RrfFusion.fuse(List.of(list1, list2), 10);
        assertThat(result.get(0).grade()).isEqualTo(RelevanceGrade.AMBIGUOUS);
    }

    private static RetrievedChunk chunk(String content, String docId, double score) {
        return new RetrievedChunk(content, docId, score, Map.of());
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api --batch-mode -Dtest=RrfFusionTest`
Expected: Compilation failure — `RrfFusion` does not exist

- [ ] **Step 3: Implement RrfFusion**

```java
// rag-api/src/main/java/io/casehub/rag/RrfFusion.java
package io.casehub.rag;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class RrfFusion {

    private static final int DEFAULT_K = 60;

    private RrfFusion() {}

    public static List<RetrievedChunk> fuse(
            List<List<RetrievedChunk>> rankedLists, int maxResults) {
        return fuse(rankedLists, maxResults, DEFAULT_K);
    }

    public static List<RetrievedChunk> fuse(
            List<List<RetrievedChunk>> rankedLists, int maxResults, int k) {
        if (rankedLists.isEmpty()) {
            return List.of();
        }

        Map<String, Double> scores = new LinkedHashMap<>();
        Map<String, RetrievedChunk> chunks = new LinkedHashMap<>();

        for (List<RetrievedChunk> results : rankedLists) {
            for (int rank = 0; rank < results.size(); rank++) {
                RetrievedChunk chunk = results.get(rank);
                String key = dedupKey(chunk);
                scores.merge(key, 1.0 / (k + rank + 1), Double::sum);

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

    private static String dedupKey(RetrievedChunk c) {
        return c.sourceDocumentId() + "\0" + c.content();
    }

    private static RelevanceGrade betterGrade(RelevanceGrade a, RelevanceGrade b) {
        return gradeRank(a) <= gradeRank(b) ? a : b;
    }

    private static int gradeRank(RelevanceGrade g) {
        return switch (g) {
            case CORRECT -> 0;
            case AMBIGUOUS -> 1;
            case UNGRADED -> 2;
            case INCORRECT -> 3;
        };
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api --batch-mode -Dtest=RrfFusionTest`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```
feat(#43,#42): add RrfFusion utility to rag-api — application-level reciprocal rank fusion
```

---

### Task 2: Change QueryExpander SPI + Update InMemoryQueryExpander

Change the SPI return type and update the rag-testing stub. These are the foundation changes — everything downstream depends on this.

**Files:**
- Modify: `rag-api/src/main/java/io/casehub/rag/QueryExpander.java`
- Modify: `rag-testing/src/main/java/io/casehub/rag/testing/InMemoryQueryExpander.java`
- Modify: `rag-testing/src/test/java/io/casehub/rag/testing/InMemoryQueryExpanderTest.java`

**Interfaces:**
- Produces: `QueryExpander.expand(RetrievalQuery): List<RetrievalQuery>` — consumed by all decorator and expander tasks

- [ ] **Step 1: Update QueryExpander SPI**

```java
// rag-api/src/main/java/io/casehub/rag/QueryExpander.java
package io.casehub.rag;

import java.util.List;

public interface QueryExpander {
    List<RetrievalQuery> expand(RetrievalQuery query);
}
```

- [ ] **Step 2: Run rag-api tests — verify existing tests still pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-api --batch-mode`
Expected: PASS (QueryExpander has no tests of its own in rag-api; DependencyConstraintTest and others are unaffected)

- [ ] **Step 3: Update InMemoryQueryExpander to return List**

```java
// rag-testing/src/main/java/io/casehub/rag/testing/InMemoryQueryExpander.java
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
    public List<RetrievalQuery> expand(RetrievalQuery query) {
        RetrievalQuery expanded = query.withExpansion("hypothetical: " + query.text());
        expandedQueries.add(expanded);
        return List.of(expanded);
    }

    public List<RetrievalQuery> expandedQueries() {
        return List.copyOf(expandedQueries);
    }

    public void clear() {
        expandedQueries.clear();
    }
}
```

- [ ] **Step 4: Update InMemoryQueryExpanderTest for List return**

```java
// rag-testing/src/test/java/io/casehub/rag/testing/InMemoryQueryExpanderTest.java
package io.casehub.rag.testing;

import io.casehub.rag.RetrievalQuery;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class InMemoryQueryExpanderTest {

    @Test
    void expandReturnsSingleElementList() {
        var expander = new InMemoryQueryExpander();
        var result = expander.expand(RetrievalQuery.of("what is diabetes?"));
        assertThat(result).hasSize(1);
        assertThat(result.get(0).text()).isEqualTo("what is diabetes?");
        assertThat(result.get(0).expandedText()).isEqualTo("hypothetical: what is diabetes?");
        assertThat(result.get(0).searchText()).isEqualTo("hypothetical: what is diabetes?");
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
        assertThat(result).hasSize(1);
        assertThat(result.get(0).text()).isEqualTo("original");
        assertThat(result.get(0).expandedText()).isEqualTo("hypothetical: original");
    }
}
```

- [ ] **Step 5: Run rag-testing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-testing --batch-mode`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```
feat(#43,#42): change QueryExpander SPI to return List<RetrievalQuery>

Breaking change: expand() now returns List<RetrievalQuery> instead of single
RetrievalQuery. SPI contract: must return non-empty list. InMemoryQueryExpander
updated to return single-element list.
```

---

### Task 3: Module Rename — rag-hyde → rag-expansion

Rename the module directory, artifactId, package, and all class names. Use IntelliJ MCP for semantic renames. This task produces a compiling but not yet functionally updated module — the SPI return type change in the expanders happens here to fix compilation, but multi-query logic comes in Task 4.

**Files:**
- Rename directory: `rag-hyde/` → `rag-expansion/`
- Modify: `pom.xml` (root) — module list + dependencyManagement
- Modify: `rag-expansion/pom.xml` — artifactId, name, description
- Rename classes via IntelliJ: `HydeCaseRetriever` → `QueryExpandingCaseRetriever`, `ReactiveHydeCaseRetriever` → `ReactiveQueryExpandingCaseRetriever`, `HydeConfig` → `ExpansionConfig`
- Move package via IntelliJ: `io.casehub.rag.hyde` → `io.casehub.rag.expansion`
- Update all `@IfBuildProperty` string literals: `casehub.rag.hyde.*` → `casehub.rag.expansion.*`
- Update all `@ConfigMapping` prefix: `casehub.rag.hyde` → `casehub.rag.expansion`
- Update all expanders and decorators to return/consume `List<RetrievalQuery>` (single-element for now)

**Interfaces:**
- Consumes: `QueryExpander.expand(): List<RetrievalQuery>` from Task 2
- Produces: Renamed module with all tests passing, ready for multi-query logic in Task 4

- [ ] **Step 1: Rename directory**

```bash
git -C /Users/mdproctor/claude/casehub/neural-text mv rag-hyde rag-expansion
```

- [ ] **Step 2: Update root pom.xml — module list**

Change `<module>rag-hyde</module>` to `<module>rag-expansion</module>` in root `pom.xml` line 28.

- [ ] **Step 3: Update root pom.xml — dependencyManagement**

Change `<artifactId>casehub-rag-hyde</artifactId>` to `<artifactId>casehub-rag-expansion</artifactId>` in root `pom.xml` line 159.

- [ ] **Step 4: Update module pom.xml**

In `rag-expansion/pom.xml`:
- Line 13: `<artifactId>casehub-rag-expansion</artifactId>`
- Update `<name>` to `CaseHub Neural Text - RAG Expansion`
- Update `<description>` to `Query expansion — CDI @Decorator on CaseRetriever that expands queries via QueryExpander SPI before retrieval. Supports HyDE, step-back prompting, and multi-query. Classpath + config activated.`

- [ ] **Step 5: Rename classes via IntelliJ MCP**

Use `ide_refactor_rename` for each:

- `HydeCaseRetriever` → `QueryExpandingCaseRetriever`
- `ReactiveHydeCaseRetriever` → `ReactiveQueryExpandingCaseRetriever`
- `HydeConfig` → `ExpansionConfig`
- `HydeCaseRetrieverTest` → `QueryExpandingCaseRetrieverTest`
- `ReactiveHydeCaseRetrieverTest` → `ReactiveQueryExpandingCaseRetrieverTest`

- [ ] **Step 6: Move package via IntelliJ MCP**

Use `ide_move_file` to move all source files from `io/casehub/rag/hyde/` to `io/casehub/rag/expansion/` — both `src/main/java` and `src/test/java`.

- [ ] **Step 7: Update config annotations**

In `QueryExpandingCaseRetriever.java` and `ReactiveQueryExpandingCaseRetriever.java`:
- `@IfBuildProperty(name = "casehub.rag.expansion.enabled", stringValue = "true")`

In `LlmQueryExpander.java`:
- `@IfBuildProperty(name = "casehub.rag.expansion.mode", stringValue = "llm", enableIfMissing = true)`

In `TemplateQueryExpander.java`:
- `@IfBuildProperty(name = "casehub.rag.expansion.mode", stringValue = "template")`

In `ExpansionConfig.java`:
- `@ConfigMapping(prefix = "casehub.rag.expansion")`

- [ ] **Step 8: Update LlmQueryExpander to return List (single-element for now)**

```java
@Override
public List<RetrievalQuery> expand(RetrievalQuery query) {
    String prompt = config.promptTemplate().orElse(DEFAULT_PROMPT)
        .formatted(query.text());
    String hypothetical = chatModel.chat(prompt);
    return List.of(query.withExpansion(hypothetical));
}
```

- [ ] **Step 9: Update TemplateQueryExpander to return List**

```java
@Override
public List<RetrievalQuery> expand(RetrievalQuery query) {
    String expanded = config.template().orElse(DEFAULT_TEMPLATE)
        .formatted(query.text());
    return List.of(query.withExpansion(expanded));
}
```

- [ ] **Step 10: Update QueryExpandingCaseRetriever for List (single-element only — multi-query in Task 4)**

```java
@Override
public List<RetrievedChunk> retrieve(RetrievalQuery query, CorpusRef corpus,
                                      int maxResults, PayloadFilter filter) {
    List<RetrievalQuery> expanded;
    try {
        expanded = expander.expand(query);
    } catch (Exception e) {
        LOG.log(Level.WARNING, "Query expansion failed, using original query", e);
        expanded = List.of(query);
    }

    if (expanded.isEmpty()) {
        expanded = List.of(query);
    }

    return delegate.retrieve(expanded.get(0), corpus, maxResults, filter);
}
```

- [ ] **Step 11: Update ReactiveQueryExpandingCaseRetriever similarly**

```java
@Override
public Uni<List<RetrievedChunk>> retrieve(RetrievalQuery query, CorpusRef corpus,
                                           int maxResults, PayloadFilter filter) {
    return Uni.createFrom().item(() -> expander.expand(query))
        .runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
        .onFailure().recoverWithItem(t -> {
            LOG.log(Level.WARNING, "Query expansion failed, using original query", t);
            return List.of(query);
        })
        .map(expanded -> expanded.isEmpty() ? List.of(query) : expanded)
        .chain(expanded -> delegate.retrieve(expanded.get(0), corpus, maxResults, filter));
}
```

- [ ] **Step 12: Update all test files for new return types**

Update `QueryExpandingCaseRetrieverTest`, `ReactiveQueryExpandingCaseRetrieverTest`, `LlmQueryExpanderTest`, `TemplateQueryExpanderTest` — change all `expander.expand(query)` assertions from single-value to `result.get(0)` or list-based assertions. Update config stubs to implement `ExpansionConfig` (renamed from `HydeConfig`).

- [ ] **Step 13: Sync IntelliJ and run tests**

Sync files with IntelliJ: `ide_sync_files` on `rag-expansion/`.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion --batch-mode`
Expected: All existing tests PASS with renamed classes and packages

- [ ] **Step 14: Commit**

```
refactor(#43,#42): rename rag-hyde → rag-expansion — module, package, classes, config namespace

HydeCaseRetriever → QueryExpandingCaseRetriever
ReactiveHydeCaseRetriever → ReactiveQueryExpandingCaseRetriever
HydeConfig → ExpansionConfig
io.casehub.rag.hyde → io.casehub.rag.expansion
casehub.rag.hyde.* → casehub.rag.expansion.*
```

---

### Task 4: Multi-Query Fan-Out + RRF Merge in Decorators

Add the multi-query logic to both decorators. When `QueryExpander` returns more than one query, the decorator fans out, retrieves for each, and merges via RRF.

**Files:**
- Modify: `rag-expansion/src/main/java/io/casehub/rag/expansion/QueryExpandingCaseRetriever.java`
- Modify: `rag-expansion/src/main/java/io/casehub/rag/expansion/ReactiveQueryExpandingCaseRetriever.java`
- Modify: `rag-expansion/src/test/java/io/casehub/rag/expansion/QueryExpandingCaseRetrieverTest.java`
- Modify: `rag-expansion/src/test/java/io/casehub/rag/expansion/ReactiveQueryExpandingCaseRetrieverTest.java`

**Interfaces:**
- Consumes: `RrfFusion.fuse()` from Task 1, `QueryExpander.expand(): List<RetrievalQuery>` from Task 2
- Produces: Multi-query-aware decorators consumed by end users

- [ ] **Step 1: Write multi-query tests for blocking decorator**

Add to `QueryExpandingCaseRetrieverTest.java`:

```java
@Test
void multiQueryFansOutAndMergesViaRrf() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9));
    };
    QueryExpander multiExpander = query -> List.of(
        query,
        RetrievalQuery.of("abstract version")
    );

    var decorator = new QueryExpandingCaseRetriever(delegate, multiExpander);
    var results = decorator.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    assertThat(capturedQueries).hasSize(2);
    assertThat(capturedQueries.get(0).text()).isEqualTo("original");
    assertThat(capturedQueries.get(1).text()).isEqualTo("abstract version");
    assertThat(results).hasSize(2);
}

@Test
void singleQuerySkipsRrf() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk("result", "doc1", 0.9));
    };
    QueryExpander singleExpander = query -> List.of(query.withExpansion("expanded"));

    var decorator = new QueryExpandingCaseRetriever(delegate, singleExpander);
    var results = decorator.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    assertThat(capturedQueries).hasSize(1);
    assertThat(results).hasSize(1);
}

@Test
void emptyExpansionFallsBackToOriginal() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    CaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return List.of(chunk("result", "doc1", 0.9));
    };
    QueryExpander emptyExpander = query -> List.of();

    var decorator = new QueryExpandingCaseRetriever(delegate, emptyExpander);
    var results = decorator.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null);

    assertThat(capturedQueries).hasSize(1);
    assertThat(capturedQueries.get(0).text()).isEqualTo("original");
    assertThat(capturedQueries.get(0).expandedText()).isNull();
    assertThat(results).hasSize(1);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion --batch-mode -Dtest=QueryExpandingCaseRetrieverTest`
Expected: `multiQueryFansOutAndMergesViaRrf` FAILS (decorator currently only uses `expanded.get(0)`)

- [ ] **Step 3: Implement multi-query in blocking decorator**

Replace the retrieve method in `QueryExpandingCaseRetriever.java` with the full version from the spec (section 4) — including the empty guard, single-query fast path, and multi-query fan-out with `RrfFusion.fuse()`. Add `import io.casehub.rag.RrfFusion;` and `import java.util.ArrayList;`.

- [ ] **Step 4: Run blocking tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion --batch-mode -Dtest=QueryExpandingCaseRetrieverTest`
Expected: All tests PASS

- [ ] **Step 5: Write multi-query tests for reactive decorator**

Add to `ReactiveQueryExpandingCaseRetrieverTest.java`:

```java
@Test
void multiQueryFansOutConcurrently() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return Uni.createFrom().item(List.of(chunk(query.searchText(), "doc-" + capturedQueries.size(), 0.9)));
    };
    QueryExpander multiExpander = query -> List.of(
        query,
        RetrievalQuery.of("abstract version")
    );

    var decorator = new ReactiveQueryExpandingCaseRetriever(delegate, multiExpander);
    var results = decorator.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null)
        .await().indefinitely();

    assertThat(capturedQueries).hasSize(2);
    assertThat(results).hasSize(2);
}

@Test
void emptyExpansionFallsBackToOriginal() {
    var capturedQueries = new ArrayList<RetrievalQuery>();
    ReactiveCaseRetriever delegate = (query, corpus, maxResults, filter) -> {
        capturedQueries.add(query);
        return Uni.createFrom().item(List.of(chunk("result", "doc1", 0.9)));
    };
    QueryExpander emptyExpander = query -> List.of();

    var decorator = new ReactiveQueryExpandingCaseRetriever(delegate, emptyExpander);
    var results = decorator.retrieve(RetrievalQuery.of("original"), CORPUS, 10, null)
        .await().indefinitely();

    assertThat(capturedQueries).hasSize(1);
    assertThat(capturedQueries.get(0).expandedText()).isNull();
}
```

- [ ] **Step 6: Implement multi-query in reactive decorator**

Replace the retrieve method in `ReactiveQueryExpandingCaseRetriever.java` with the full version from the spec (section 4, reactive counterpart) — including `Uni.combine().all().unis()` fan-out with `RrfFusion.fuse()`.

- [ ] **Step 7: Run all rag-expansion tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion --batch-mode`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```
feat(#43,#42): multi-query fan-out + RRF merge in expansion decorators

When QueryExpander returns >1 query, the decorator fans out sub-retrievals
and merges via RrfFusion. Single-query fast path skips fusion. Empty
expansion falls back to original query. Reactive path fans out concurrently
via Uni.combine().all().unis().
```

---

### Task 5: ExpansionConfig — New Properties + StepBackQueryExpander (#43)

Add `hypotheticalCount` and `stepBackPromptTemplate` to config. Add `StepBackQueryExpander`.

**Files:**
- Modify: `rag-expansion/src/main/java/io/casehub/rag/expansion/ExpansionConfig.java`
- Create: `rag-expansion/src/main/java/io/casehub/rag/expansion/StepBackQueryExpander.java`
- Create: `rag-expansion/src/test/java/io/casehub/rag/expansion/StepBackQueryExpanderTest.java`

**Interfaces:**
- Consumes: `ChatModel` (LangChain4j), `ExpansionConfig`, `QueryExpander` SPI
- Produces: `StepBackQueryExpander` — selected via `casehub.rag.expansion.mode=step-back`

- [ ] **Step 1: Add new properties to ExpansionConfig**

```java
// rag-expansion/src/main/java/io/casehub/rag/expansion/ExpansionConfig.java
package io.casehub.rag.expansion;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

import java.util.Optional;

@ConfigMapping(prefix = "casehub.rag.expansion")
public interface ExpansionConfig {

    @WithDefault("false")
    boolean enabled();

    @WithDefault("llm")
    String mode();

    @WithDefault("1")
    int hypotheticalCount();

    Optional<String> promptTemplate();

    Optional<String> template();

    Optional<String> stepBackPromptTemplate();
}
```

- [ ] **Step 2: Write StepBackQueryExpander tests**

```java
// rag-expansion/src/test/java/io/casehub/rag/expansion/StepBackQueryExpanderTest.java
package io.casehub.rag.expansion;

import dev.langchain4j.data.message.AiMessage;
import dev.langchain4j.data.message.UserMessage;
import dev.langchain4j.model.chat.ChatModel;
import dev.langchain4j.model.chat.request.ChatRequest;
import dev.langchain4j.model.chat.response.ChatResponse;
import io.casehub.rag.RetrievalQuery;
import org.junit.jupiter.api.Test;

import java.util.Optional;
import java.util.function.Function;

import static org.assertj.core.api.Assertions.assertThat;

class StepBackQueryExpanderTest {

    @Test
    void expandReturnsOriginalAndAbstract() {
        ChatModel model = stubChatModel(prompt -> "What are NSAIDs?");
        var expander = new StepBackQueryExpander(model, stubConfig(Optional.empty()));
        var result = expander.expand(RetrievalQuery.of("side effects of ibuprofen for liver patients"));

        assertThat(result).hasSize(2);
        assertThat(result.get(0).text()).isEqualTo("side effects of ibuprofen for liver patients");
        assertThat(result.get(0).expandedText()).isNull();
        assertThat(result.get(1).text()).isEqualTo("What are NSAIDs?");
    }

    @Test
    void expandUsesDefaultPromptTemplate() {
        var capturedPrompt = new String[1];
        ChatModel model = stubChatModel(prompt -> {
            capturedPrompt[0] = prompt;
            return "abstract question";
        });
        var expander = new StepBackQueryExpander(model, stubConfig(Optional.empty()));
        expander.expand(RetrievalQuery.of("test query"));

        assertThat(capturedPrompt[0]).contains("test query");
        assertThat(capturedPrompt[0]).contains("more general, abstract version");
    }

    @Test
    void expandUsesCustomPromptTemplate() {
        ChatModel model = stubChatModel(prompt -> "custom abstract");
        var expander = new StepBackQueryExpander(model,
            stubConfig(Optional.of("Step back from: %s")));
        var result = expander.expand(RetrievalQuery.of("specific question"));

        assertThat(result).hasSize(2);
        assertThat(result.get(1).text()).isEqualTo("custom abstract");
    }

    @Test
    void expandPreservesOriginalExpansion() {
        ChatModel model = stubChatModel(prompt -> "abstract");
        var expander = new StepBackQueryExpander(model, stubConfig(Optional.empty()));
        var query = new RetrievalQuery("original", "prior expansion");
        var result = expander.expand(query);

        assertThat(result.get(0).text()).isEqualTo("original");
        assertThat(result.get(0).expandedText()).isEqualTo("prior expansion");
        assertThat(result.get(1).text()).isEqualTo("abstract");
    }

    private static ChatModel stubChatModel(Function<String, String> handler) {
        return new ChatModel() {
            @Override
            public ChatResponse doChat(ChatRequest request) {
                String userText = ((UserMessage) request.messages().get(0)).singleText();
                String response = handler.apply(userText);
                return ChatResponse.builder()
                    .aiMessage(AiMessage.from(response))
                    .build();
            }
        };
    }

    private static ExpansionConfig stubConfig(Optional<String> stepBackPromptTemplate) {
        return new ExpansionConfig() {
            @Override public boolean enabled() { return true; }
            @Override public String mode() { return "step-back"; }
            @Override public int hypotheticalCount() { return 1; }
            @Override public Optional<String> promptTemplate() { return Optional.empty(); }
            @Override public Optional<String> template() { return Optional.empty(); }
            @Override public Optional<String> stepBackPromptTemplate() { return stepBackPromptTemplate; }
        };
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion --batch-mode -Dtest=StepBackQueryExpanderTest`
Expected: Compilation failure — `StepBackQueryExpander` does not exist

- [ ] **Step 4: Implement StepBackQueryExpander**

```java
// rag-expansion/src/main/java/io/casehub/rag/expansion/StepBackQueryExpander.java
package io.casehub.rag.expansion;

import dev.langchain4j.model.chat.ChatModel;
import io.casehub.rag.QueryExpander;
import io.casehub.rag.RetrievalQuery;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.util.List;

@ApplicationScoped
@IfBuildProperty(name = "casehub.rag.expansion.mode", stringValue = "step-back")
public class StepBackQueryExpander implements QueryExpander {

    static final String DEFAULT_PROMPT =
        "Given the question below, generate a more general, abstract version "
        + "that captures the underlying concept. The step-back question should "
        + "be broader and help retrieve foundational knowledge. "
        + "Return only the step-back question, nothing else.\n\n"
        + "Original question: %s\n\nStep-back question:";

    private final ChatModel chatModel;
    private final ExpansionConfig config;

    @Inject
    public StepBackQueryExpander(ChatModel chatModel, ExpansionConfig config) {
        this.chatModel = chatModel;
        this.config = config;
    }

    @Override
    public List<RetrievalQuery> expand(RetrievalQuery query) {
        String prompt = config.stepBackPromptTemplate().orElse(DEFAULT_PROMPT)
            .formatted(query.text());
        String stepBack = chatModel.chat(prompt);
        return List.of(
            query,
            RetrievalQuery.of(stepBack)
        );
    }
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion --batch-mode -Dtest=StepBackQueryExpanderTest`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```
feat(#43): add StepBackQueryExpander — abstract query reformulation

Returns [original, abstract] for augmented retrieval. Activated via
casehub.rag.expansion.mode=step-back. Custom prompt template
configurable via casehub.rag.expansion.step-back-prompt-template.
```

---

### Task 6: Multi-Query LlmQueryExpander (#42) + Config Stubs Update

Extend `LlmQueryExpander` with `hypotheticalCount` support. Update all config stubs across test files.

**Files:**
- Modify: `rag-expansion/src/main/java/io/casehub/rag/expansion/LlmQueryExpander.java`
- Modify: `rag-expansion/src/test/java/io/casehub/rag/expansion/LlmQueryExpanderTest.java`

**Interfaces:**
- Consumes: `ExpansionConfig.hypotheticalCount()` from Task 5
- Produces: Multi-query LLM expansion — N hypothetical documents per query

- [ ] **Step 1: Write multi-query LLM tests**

Add to `LlmQueryExpanderTest.java`:

```java
@Test
void expandReturnsMultipleHypotheticals() {
    int[] callCount = {0};
    ChatModel model = stubChatModel(prompt -> {
        callCount[0]++;
        return "hypothetical " + callCount[0];
    });
    var expander = new LlmQueryExpander(model, stubConfig(Optional.empty(), 3));
    var result = expander.expand(RetrievalQuery.of("test query"));

    assertThat(result).hasSize(3);
    assertThat(result.get(0).expandedText()).isEqualTo("hypothetical 1");
    assertThat(result.get(1).expandedText()).isEqualTo("hypothetical 2");
    assertThat(result.get(2).expandedText()).isEqualTo("hypothetical 3");
    assertThat(result.get(0).text()).isEqualTo("test query");
}

@Test
void expandDefaultCountIsOne() {
    ChatModel model = stubChatModel(prompt -> "single hypothetical");
    var expander = new LlmQueryExpander(model, stubConfig(Optional.empty(), 1));
    var result = expander.expand(RetrievalQuery.of("test"));

    assertThat(result).hasSize(1);
    assertThat(result.get(0).expandedText()).isEqualTo("single hypothetical");
}
```

Update the `stubConfig` helper to accept `hypotheticalCount`:

```java
private static ExpansionConfig stubConfig(Optional<String> promptTemplate, int hypotheticalCount) {
    return new ExpansionConfig() {
        @Override public boolean enabled() { return true; }
        @Override public String mode() { return "llm"; }
        @Override public int hypotheticalCount() { return hypotheticalCount; }
        @Override public Optional<String> promptTemplate() { return promptTemplate; }
        @Override public Optional<String> template() { return Optional.empty(); }
        @Override public Optional<String> stepBackPromptTemplate() { return Optional.empty(); }
    };
}

private static ExpansionConfig stubConfig(Optional<String> promptTemplate) {
    return stubConfig(promptTemplate, 1);
}
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion --batch-mode -Dtest=LlmQueryExpanderTest`
Expected: `expandReturnsMultipleHypotheticals` FAILS (current implementation ignores count, returns single element)

- [ ] **Step 3: Implement multi-query LlmQueryExpander**

```java
@Override
public List<RetrievalQuery> expand(RetrievalQuery query) {
    int n = config.hypotheticalCount();
    String promptTemplate = config.promptTemplate().orElse(DEFAULT_PROMPT);

    List<RetrievalQuery> expansions = new ArrayList<>(n);
    for (int i = 0; i < n; i++) {
        String prompt = promptTemplate.formatted(query.text());
        String hypothetical = chatModel.chat(prompt);
        expansions.add(query.withExpansion(hypothetical));
    }
    return expansions;
}
```

Add `import java.util.ArrayList;`.

- [ ] **Step 4: Run all rag-expansion tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion --batch-mode`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```
feat(#42): multi-query LlmQueryExpander — configurable hypothetical-count

LlmQueryExpander now generates N hypothetical documents per query
(casehub.rag.expansion.hypothetical-count, default 1). Each LLM call
produces a different hypothetical via temperature diversity. Multi-query
results are merged via RRF in the decorator (Task 4).
```

---

### Task 7: Full Build + Documentation Updates

Run the full build, update CLAUDE.md and ARC42STORIES.MD.

**Files:**
- Modify: `CLAUDE.md`
- Modify: `ARC42STORIES.MD`

**Interfaces:**
- Consumes: All previous tasks
- Produces: Passing full build, updated documentation

- [ ] **Step 1: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile and all tests pass

- [ ] **Step 2: Update CLAUDE.md**

Replace all references:
- Module listing: `rag-hyde` → `rag-expansion` with updated description
- Maven coordinates table: `casehub-rag-hyde` → `casehub-rag-expansion`
- Root Java package table: `io.casehub.rag.hyde` → `io.casehub.rag.expansion`
- Module description: update to reflect generic query expansion, step-back, multi-query

- [ ] **Step 3: Update ARC42STORIES.MD**

Update Layer L11 and Chapter C11 references:
- `rag-hyde` → `rag-expansion`
- `HydeCaseRetriever` → `QueryExpandingCaseRetriever`
- `ReactiveHydeCaseRetriever` → `ReactiveQueryExpandingCaseRetriever`
- `HydeConfig` → `ExpansionConfig`
- `casehub.rag.hyde.*` → `casehub.rag.expansion.*`
- Add `StepBackQueryExpander` to key files table
- Note multi-query support and RRF fusion

- [ ] **Step 4: Run full build again to verify docs didn't break anything**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```
docs(#43,#42): update CLAUDE.md + ARC42STORIES.MD for rag-expansion rename + new capabilities
```
