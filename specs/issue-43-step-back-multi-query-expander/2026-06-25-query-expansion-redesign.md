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

**SPI contract:** `expand()` must return a non-empty list. An expander that returns nothing is a contract violation, not "no expansion." Implementations that have nothing to expand should return `List.of(query)` (the original unchanged).

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

- Identity key for deduplication: `sourceDocumentId + "\0" + content` (exact string equality, matching `CragEvaluationLogic.dedupKey()`)
- K=60 default (Cormack et al., 2009; same as Qdrant's native RRF)
- Fused chunks carry the RRF score as `relevanceScore`, preserving `metadata` from first occurrence
- **Grade resolution for duplicates:** when the same chunk appears in multiple result sets with different grades (e.g., CORRECT from one sub-retrieval, AMBIGUOUS from another), the best grade wins: CORRECT > AMBIGUOUS > UNGRADED > INCORRECT. This is necessary because each sub-retrieval is independently CRAG-evaluated against its own query text — the same chunk can legitimately receive different grades. Taking the best grade preserves the signal that the chunk proved relevant to at least one formulation of the user's intent.

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

        if (expanded.isEmpty()) {
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
- Each sub-retrieval goes through full decorator chain (including CRAG if active). CRAG's own internal re-retrieval (`delegate.retrieve()` at line 67 of `CorrectiveCaseRetriever`) calls the concrete bean directly, not back up the decorator chain — no infinite loop risk.
- **Known behavior change:** when CRAG is active, N sub-retrievals produce N `RetrievalQuality` CDI events per user request (previously 1). The expansion decorator cannot intercept or aggregate CRAG's events without coupling the decorators. Event consumers must account for multi-event-per-request when expansion is enabled.
- Decorator keeps `@Priority(200)` — CRAG at `@Priority(100)` is unaffected

**Reactive counterpart** — `ReactiveQueryExpandingCaseRetriever` fans out concurrent sub-retrievals:

```java
@Decorator
@Priority(200)
@IfBuildProperty(name = "casehub.rag.expansion.enabled", stringValue = "true")
public class ReactiveQueryExpandingCaseRetriever implements ReactiveCaseRetriever {

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
            .chain(expanded -> {
                if (expanded.size() == 1) {
                    return delegate.retrieve(expanded.get(0), corpus, maxResults, filter);
                }

                List<Uni<List<RetrievedChunk>>> unis = expanded.stream()
                    .map(eq -> delegate.retrieve(eq, corpus, maxResults, filter))
                    .toList();

                return Uni.combine().all().unis(unis)
                    .with(results -> {
                        @SuppressWarnings("unchecked")
                        List<List<RetrievedChunk>> resultSets =
                            (List<List<RetrievedChunk>>) (List<?>) results;
                        return RrfFusion.fuse(resultSets, maxResults);
                    });
            });
    }
}
```

- Expansion runs on worker pool (blocking `ChatModel` call, same as current pattern)
- Sub-retrievals fan out concurrently via `Uni.combine().all().unis()` — each is independent
- If any sub-retrieval fails, the combined Uni fails (retrieval errors should propagate)

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

**CRAG interaction:** each sub-retrieval is independently CRAG-evaluated against its own query text. The original retrieval is evaluated against the original intent (precision). The step-back retrieval is evaluated against the broader intent (breadth). This is intentional — CRAG asks "are these chunks good for what THIS query was trying to find?" not "are these chunks good for the original user question." Evaluating the step-back retrieval against the original narrow query would incorrectly penalize chunks that are relevant to the broader context.

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
}
```

- Default `hypothetical-count=1` — backward-compatible single-query HyDE behavior
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
    int hypotheticalCount();  // N hypothetical documents for LLM mode (property: hypothetical-count)

    Optional<String> promptTemplate();           // custom LLM/HyDE prompt
    Optional<String> template();                 // template mode string
    Optional<String> stepBackPromptTemplate();   // custom step-back prompt
}
```

Configuration examples:

```properties
# HyDE (single) — equivalent to current default behavior
casehub.rag.expansion.enabled=true
casehub.rag.expansion.mode=llm

# Multi-query HyDE — 3 hypothetical documents
casehub.rag.expansion.enabled=true
casehub.rag.expansion.mode=llm
casehub.rag.expansion.hypothetical-count=3

# Step-back prompting
casehub.rag.expansion.enabled=true
casehub.rag.expansion.mode=step-back

# Template expansion (unchanged behavior)
casehub.rag.expansion.enabled=true
casehub.rag.expansion.mode=template
```

`hypothetical-count` only applies to LLM mode. Step-back always returns exactly 2 (original + abstract). Template always returns 1.

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
- `ExpansionConfig.java` — renamed from HydeConfig, new properties (`hypotheticalCount`, `stepBackPromptTemplate`)
- `QueryExpandingCaseRetriever.java` — renamed, multi-query fan-out + RRF merge
- `ReactiveQueryExpandingCaseRetriever.java` — renamed, concurrent fan-out via `Uni.combine()`
- `LlmQueryExpander.java` — returns List, hypotheticalCount support
- `TemplateQueryExpander.java` — returns List
- `StepBackQueryExpander.java` — new implementation
- `QueryExpandingCaseRetrieverTest.java` — renamed from HydeCaseRetrieverTest, new multi-query + RRF tests
- `ReactiveQueryExpandingCaseRetrieverTest.java` — renamed, new concurrent fan-out tests
- `LlmQueryExpanderTest.java` — new tests for hypotheticalCount>1, config stubs updated for new properties
- `TemplateQueryExpanderTest.java` — updated for List return
- `StepBackQueryExpanderTest.java` — new: default prompt, custom prompt, returns [original, abstract], LLM error handling

**rag-testing:**
- `InMemoryQueryExpander.java` — returns List
- `InMemoryQueryExpanderTest.java` — updated assertions

**Root project:**
- `pom.xml` — module rename in modules list and dependencyManagement
- `CLAUDE.md` — module listing, package, config references
- `ARC42STORIES.MD` — rag-hyde → rag-expansion references

## Deferred Concerns

1. **Parallel LLM calls (#45)** — N sequential `chatModel.chat()` calls for multi-query HyDE. Each call is ~500ms–2s depending on model and prompt length. At `hypothetical-count=3`, expansion latency is 1.5–6s; at `hypothetical-count=5`, 2.5–10s — all before any retrieval begins. This is the dominant latency in the pipeline. Parallelization requires an async ChatModel API (not yet available in LangChain4j). Filed as #45.
2. **Parent doc update** — `docs/repos/casehub-neural-text.md` in casehubio/parent needs QueryExpander, CRAG, expansion module added. Scope extends casehubio/parent#306.
