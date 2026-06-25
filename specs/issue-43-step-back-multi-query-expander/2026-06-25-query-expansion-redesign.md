# Query Expansion Redesign — Step-Back Prompting (#43) + Multi-Query HyDE (#42)

## Summary

Redesign the query expansion architecture: rename `rag-hyde` → `rag-expansion`, change `QueryExpander` SPI to return `List<RetrievalQuery>`, add `StepBackQueryExpander`, and extend `LlmQueryExpander` with configurable multi-query support. Add application-level RRF fusion utility to `rag-api`.

## Motivation

Two issues drive this work:

- **#43 Step-back prompting**: A new `QueryExpander` strategy that abstracts a specific query into a broader one. Returns both the original (precision) and abstract (breadth) queries — "augment the query" rather than replace it.
- **#42 Multi-query HyDE**: Generate N hypothetical documents per query instead of 1, retrieve for each, and merge results via RRF fusion.

Both require `QueryExpander` to return multiple queries. The current SPI returns a single `RetrievalQuery` — insufficient for either use case.

The existing module name (`rag-hyde`) and decorator name (`HydeCaseRetriever`) are also incorrect — the decorator does generic query expansion, not HyDE-specific work. With step-back being added, the names actively mislead. No external consumers exist, so fixing the names now costs nothing.

## Design

### 1. SPI Change — `QueryExpander` returns `List<RetrievalQuery>`

```java
// rag-api: io.casehub.rag.QueryExpander
package io.casehub.rag;

import java.util.List;

public interface QueryExpander {
    List<RetrievalQuery> expand(RetrievalQuery query);
}
```

Single-query expansion returns `List.of(expanded)`. Multi-query returns N items. Step-back returns `[original, abstract]`. The cardinality decision belongs to the implementation, not the framework.

`RetrievalQuery` is unchanged — each element in the returned list is a complete `RetrievalQuery` with its own `text()` and optional `expandedText()`.

### 2. RRF Fusion Utility in `rag-api`

Application-level Reciprocal Rank Fusion for merging N result sets from N expanded queries. Pure Java, zero dependencies, operates on `List<RetrievedChunk>`.

```java
// rag-api: io.casehub.rag.RrfFusion
package io.casehub.rag;

import java.util.List;

public final class RrfFusion {
    private static final int DEFAULT_K = 60;

    public static List<RetrievedChunk> fuse(
            List<List<RetrievedChunk>> rankedLists, int maxResults) { ... }

    public static List<RetrievedChunk> fuse(
            List<List<RetrievedChunk>> rankedLists, int maxResults, int k) { ... }
}
```

- Identity key for deduplication: `sourceDocumentId` + content hash
- K=60 default (Cormack et al., 2009; same as Qdrant's native RRF)
- Fused chunks carry the RRF score as `relevanceScore`, preserving original `metadata` and `grade` from first occurrence

### 3. Module Rename — `rag-hyde` → `rag-expansion`

| Before | After |
|--------|-------|
| Folder: `rag-hyde/` | Folder: `rag-expansion/` |
| artifactId: `casehub-rag-hyde` | artifactId: `casehub-rag-expansion` |
| Package: `io.casehub.rag.hyde` | Package: `io.casehub.rag.expansion` |

Per maven-coordinate-standard (PP-20260512): `casehub-rag-expansion` follows `casehub-{repo}-{function}`. Folder `rag-expansion/` uses the short form.

### 4. Decorator Rename + Multi-Query Logic

| Before | After |
|--------|-------|
| `HydeCaseRetriever` | `QueryExpandingCaseRetriever` |
| `ReactiveHydeCaseRetriever` | `ReactiveQueryExpandingCaseRetriever` |
| `HydeConfig` | `ExpansionConfig` |

The decorator gains fan-out + merge when `QueryExpander` returns more than one query:

```java
@Decorator
@Priority(200)
@IfBuildProperty(name = "casehub.rag.expansion.enabled", stringValue = "true")
public class QueryExpandingCaseRetriever implements CaseRetriever {

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

        if (expanded.size() == 1) {
            return delegate.retrieve(expanded.get(0), corpus, maxResults, filter);
        }

        List<List<RetrievedChunk>> resultSets = new ArrayList<>(expanded.size());
        for (RetrievalQuery eq : expanded) {
            resultSets.add(delegate.retrieve(eq, corpus, maxResults, filter));
        }
        return RrfFusion.fuse(resultSets, maxResults);
    }
}
```

- Single-query fast path: skip RRF when only one expansion
- Fail-safe: expansion error falls back to original query
- Each sub-retrieval goes through full decorator chain (including CRAG if active)
- Reactive counterpart fans out with `Uni.combine().all()` for concurrent sub-retrievals
- Decorator keeps `@Priority(200)` — CRAG at `@Priority(100)` is unaffected

### 5. `StepBackQueryExpander` (#43)

```java
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
            query,                        // original — precision anchor
            RetrievalQuery.of(stepBack)   // abstract — breadth
        );
    }
}
```

Always returns 2 queries. Original first (preserves any prior expansion), step-back second as a fresh `RetrievalQuery`. Two retrievals, RRF-merged by the decorator.

### 6. Multi-Query `LlmQueryExpander` (#42)

```java
@ApplicationScoped
@IfBuildProperty(name = "casehub.rag.expansion.mode", stringValue = "llm", enableIfMissing = true)
public class LlmQueryExpander implements QueryExpander {

    static final String DEFAULT_PROMPT =
        "Given the question below, write a short passage (3-5 sentences) "
        + "that would directly answer it. Write as if the passage comes from "
        + "an authoritative document. Do not include the question itself.\n\n"
        + "Question: %s\n\nPassage:";

    private final ChatModel chatModel;
    private final ExpansionConfig config;

    @Inject
    public LlmQueryExpander(ChatModel chatModel, ExpansionConfig config) {
        this.chatModel = chatModel;
        this.config = config;
    }

    @Override
    public List<RetrievalQuery> expand(RetrievalQuery query) {
        int n = config.count();
        String promptTemplate = config.promptTemplate().orElse(DEFAULT_PROMPT);

        List<RetrievalQuery> expansions = new ArrayList<>(n);
        for (int i = 0; i < n; i++) {
            String prompt = promptTemplate.formatted(query.text());
            String hypothetical = chatModel.chat(prompt);
            expansions.add(query.withExpansion(hypothetical));
        }
        return expansions;
    }
}
```

- Default `count=1` — backward-compatible single-query HyDE behavior
- N>1: LLM temperature provides diversity across hypothetical documents
- No original query in the list — HyDE replaces, step-back augments
- `TemplateQueryExpander` returns `List.of(expanded)` — deterministic, no count support:

```java
@Override
public List<RetrievalQuery> expand(RetrievalQuery query) {
    String expanded = config.template().orElse(DEFAULT_TEMPLATE)
        .formatted(query.text());
    return List.of(query.withExpansion(expanded));
}
```

### 7. `ExpansionConfig`

```java
@ConfigMapping(prefix = "casehub.rag.expansion")
public interface ExpansionConfig {

    @WithDefault("false")
    boolean enabled();

    @WithDefault("llm")
    String mode();      // "llm", "template", "step-back"

    @WithDefault("1")
    int count();        // N hypothetical documents for LLM mode

    Optional<String> promptTemplate();           // custom LLM/HyDE prompt
    Optional<String> template();                 // template mode string
    Optional<String> stepBackPromptTemplate();   // custom step-back prompt
}
```

### 8. `InMemoryQueryExpander` (rag-testing)

```java
@Override
public List<RetrievalQuery> expand(RetrievalQuery query) {
    RetrievalQuery expanded = query.withExpansion("hypothetical: " + query.text());
    expandedQueries.add(expanded);
    return List.of(expanded);
}
```

Single-element list. Tests needing multi-query construct a custom lambda.

## Protocol Compliance

| Protocol | Status |
|----------|--------|
| Module tier structure (PP-20260512) | ✓ SPI in rag-api (Tier 1), impls in rag-expansion |
| Optional module pattern (PP-20260508) | ✓ Jandex + @IfBuildProperty activation |
| Maven coordinate standard (PP-20260512) | ✓ `casehub-rag-expansion`, folder `rag-expansion/` |
| Reactive parity (PP-20260521) | ✓ Both blocking and reactive decorators |
| SPI adapter placement (PP-20260529) | ✓ All impls in host module |
| Library JAR annotation deps (PP-20260604) | ✓ CDI/Arc as provided scope |

## Files Touched

**rag-api (SPI + utility):**
- `QueryExpander.java` — return type change
- `RrfFusion.java` — new utility class
- `RrfFusionTest.java` — new tests

**rag-expansion (renamed from rag-hyde):**
- `pom.xml` — artifactId, name, description
- `ExpansionConfig.java` — renamed from HydeConfig, new properties
- `QueryExpandingCaseRetriever.java` — renamed, multi-query fan-out + merge
- `ReactiveQueryExpandingCaseRetriever.java` — renamed, concurrent fan-out
- `LlmQueryExpander.java` — returns List, count support
- `TemplateQueryExpander.java` — returns List
- `StepBackQueryExpander.java` — new
- All test files — renamed, updated assertions

**rag-testing:**
- `InMemoryQueryExpander.java` — returns List
- `InMemoryQueryExpanderTest.java` — updated assertions

**Root project:**
- `pom.xml` — module rename in modules list and dependencyManagement
- `CLAUDE.md` — module listing, package, config references
- `ARC42STORIES.MD` — rag-hyde → rag-expansion references

## Deferred Concerns

1. **Parallel LLM calls** — N sequential `chatModel.chat()` calls for multi-query HyDE. Parallelization requires async ChatModel API, not available now. File as GitHub issue.
2. **Parent doc update** — `docs/repos/casehub-neural-text.md` in casehubio/parent needs QueryExpander, CRAG, expansion module added. Scope extends casehubio/parent#306.
