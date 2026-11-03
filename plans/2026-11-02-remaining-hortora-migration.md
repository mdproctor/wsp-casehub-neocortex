# Remaining Hortora Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #775 — Move remaining Hortora services to corpus-management
**Issue group:** #775, #763

**Goal:** Move all remaining domain logic from Hortora engine to neocortex, leaving Hortora as a config-only deployment.

**Architecture:** Cross-repo migration. Files are created in neocortex (generified, pure Java, no CDI/Quarkus deps) and deleted from Hortora. The `corpus-management` module stays pure Java with constructor injection. `CorpusCollectionMigration` goes to the `rag` module (which already has Qdrant deps). Hortora's duplicate scorers (TemporalDecayScorer, VersionScorer) are deleted — identical implementations already exist in neocortex `rag-scoring`.

**Tech Stack:** Java 21, JUnit 5, AssertJ, Mockito (for rag module tests only), SnakeYAML

## Global Constraints

- corpus-management module has zero CDI/Quarkus dependencies — all injection via constructor params
- rag module already depends on `io.qdrant:client`, `io.casehub:casehub-neocortex-inference-api`, `io.casehub:casehub-neocortex-rag-api`
- All generified classes use `java.util.logging.Logger` (not `io.quarkus.logging.Log`)
- Cross-repo IntelliJ workspace is open with both `/Users/mdproctor/claude/casehub/slots/221/neocortex` and `/Users/mdproctor/claude/hortora/engine`
- neocortex project_path: `/Users/mdproctor/claude/casehub/slots/221/neocortex`
- Hortora project_path: `/Users/mdproctor/claude/hortora/engine`

---

## Batch 1: HTTP Federation — RemoteCorpusClient + HttpFederationWalker + FederationConfigParser

### Task 1: Create RemoteCorpusClient interface and HttpFederationWalker

**Files:**
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/RemoteCorpusClient.java`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/HttpFederationWalker.java`
- Test: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/HttpFederationWalkerTest.java`

**Interfaces:**
- Consumes: `SearchResource.FederationWalker` (existing), `FederationConfig` (existing), `SearchResult` (existing)
- Produces: `RemoteCorpusClient` (functional interface), `HttpFederationWalker` (implements `SearchResource.FederationWalker`)

- [ ] **Step 1: Write the failing test**

Create `HttpFederationWalkerTest.java` with the full test suite ported from Hortora's `ChainWalkerTest`. The test uses `RemoteCorpusClient` (not yet created) as the mock client interface.

```java
package io.casehub.neocortex.corpus.management.impl;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.concurrent.AbstractExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;

import static org.assertj.core.api.Assertions.assertThat;

class HttpFederationWalkerTest {

    private static final double HIGH = 0.9;
    private static final double LOW = 0.3;
    private static final double THRESHOLD = 0.7;
    private static final int LIMIT = 3;

    private RecordingClient upstreamClient;
    private RecordingClient peerClient;

    @BeforeEach
    void setUp() {
        upstreamClient = new RecordingClient();
        peerClient = new RecordingClient();
    }

    @Test
    void noFederationReturnsOwnResults() {
        var walker = canonicalWalker();
        var own = List.of(result("e1", HIGH, "my-garden", "MG"));

        var results = walker.walk("query", null, null, null, LIMIT, own, visited());
        assertThat(results).isEqualTo(own);
    }

    @Test
    void sufficientOwnResultsSkipsUpstream() {
        var walker = childWalker();
        var own = List.of(
                result("e1", HIGH, "my-garden", "MG"),
                result("e2", HIGH, "my-garden", "MG"),
                result("e3", HIGH, "my-garden", "MG"));

        walker.walk("query", null, null, null, LIMIT, own, visited());
        assertThat(upstreamClient.callCount).isZero();
    }

    @Test
    void insufficientOwnResultsTriggersUpstream() {
        var walker = childWalker();
        var own = List.of(result("e1", LOW, "my-garden", "MG"));
        upstreamClient.response = List.of(
                result("u1", HIGH, "parent-garden", "PG"),
                result("u2", HIGH, "parent-garden", "PG"));

        var results = walker.walk("query", null, null, null, LIMIT, own, visited());
        assertThat(results).hasSize(3);
        assertThat(upstreamClient.callCount).isEqualTo(1);
        assertThat(results.get(0).source()).isEqualTo("my-garden");
        assertThat(results.get(1).source()).isEqualTo("parent-garden");
    }

    @Test
    void upstreamShortCircuitsOnSufficientResults() {
        var upstream1 = new RecordingClient();
        var upstream2 = new RecordingClient();
        upstream1.response = List.of(
                result("u1", HIGH, "parent", "PG"),
                result("u2", HIGH, "parent", "PG"),
                result("u3", HIGH, "parent", "PG"));

        var config = new FederationConfig("my-garden", "MG", "child", THRESHOLD, 5, 5,
                List.of(
                        new FederationConfig.UpstreamRef("http://parent", "PG", "fallback"),
                        new FederationConfig.UpstreamRef("http://grandparent", "GP", "fallback")),
                List.of());
        Function<String, RemoteCorpusClient> factory = url ->
                url.equals("http://parent") ? upstream1 : upstream2;
        var walker = new HttpFederationWalker(config, new DirectExecutor(), factory);

        var own = List.of(result("e1", LOW, "my-garden", "MG"));
        walker.walk("query", null, null, null, LIMIT, own, visited());

        assertThat(upstream1.callCount).isEqualTo(1);
        assertThat(upstream2.callCount).isZero();
    }

    @Test
    void peerFanOutOnlyWhenInsufficient() {
        var walker = childWithPeerWalker();
        var own = List.of(
                result("e1", HIGH, "my-garden", "MG"),
                result("e2", HIGH, "my-garden", "MG"),
                result("e3", HIGH, "my-garden", "MG"));

        walker.walk("query", null, null, null, LIMIT, own, visited());
        assertThat(peerClient.callCount).isZero();
    }

    @Test
    void peerFanOutTriggersWhenInsufficient() {
        var config = new FederationConfig("my-garden", "MG", "child", THRESHOLD, 5, 5,
                List.of(), List.of(new FederationConfig.PeerRef("http://peer", "PR")));
        Function<String, RemoteCorpusClient> factory = url -> peerClient;
        var walker = new HttpFederationWalker(config, new DirectExecutor(), factory);

        peerClient.response = List.of(result("p1", HIGH, "peer-garden", "PR"));
        var own = List.of(result("e1", LOW, "my-garden", "MG"));

        var results = walker.walk("query", null, null, null, LIMIT, own, visited());
        assertThat(peerClient.callCount).isEqualTo(1);
        assertThat(results).anyMatch(r -> r.source().equals("peer-garden"));
    }

    @Test
    void tierGroupedRelevanceSortedOrdering() {
        var walker = childWalker();
        upstreamClient.response = List.of(
                result("u1", 0.95, "parent", "PG"),
                result("u2", 0.80, "parent", "PG"));

        var own = List.of(
                result("e1", 0.40, "my-garden", "MG"),
                result("e2", 0.60, "my-garden", "MG"));

        var results = walker.walk("query", null, null, null, 10, own, visited());

        assertThat(results.get(0).id()).isEqualTo("e2");
        assertThat(results.get(1).id()).isEqualTo("e1");
        assertThat(results.get(2).id()).isEqualTo("u1");
        assertThat(results.get(3).id()).isEqualTo("u2");
    }

    @Test
    void dedupByIdAndSource() {
        var walker = childWalker();
        upstreamClient.response = List.of(
                result("e1", HIGH, "parent", "PG"),
                result("e1", 0.85, "parent", "PG"));

        var own = List.of(result("e1", LOW, "my-garden", "MG"));

        var results = walker.walk("query", null, null, null, 10, own, visited());
        assertThat(results).hasSize(2);
    }

    @Test
    void upstreamTimeoutContinuesGracefully() {
        var walker = childWalker();
        upstreamClient.shouldThrow = true;

        var own = List.of(result("e1", LOW, "my-garden", "MG"));
        var results = walker.walk("query", null, null, null, LIMIT, own, visited());

        assertThat(results).hasSize(1);
        assertThat(results.get(0).source()).isEqualTo("my-garden");
    }

    @Test
    void truncatesToLimit() {
        var walker = childWalker();
        upstreamClient.response = List.of(
                result("u1", HIGH, "parent", "PG"),
                result("u2", HIGH, "parent", "PG"),
                result("u3", HIGH, "parent", "PG"));

        var own = List.of(
                result("e1", HIGH, "my-garden", "MG"),
                result("e2", HIGH, "my-garden", "MG"));

        var results = walker.walk("query", null, null, null, 3, own, visited());
        assertThat(results).hasSize(3);
    }

    @Test
    void alwaysModeQueriesUpstreamEvenWhenSufficient() {
        var alwaysClient = new RecordingClient();
        alwaysClient.response = List.of(result("a1", HIGH, "always-garden", "AG"));

        var config = new FederationConfig("my-garden", "MG", "child", THRESHOLD, 5, 5,
                List.of(new FederationConfig.UpstreamRef("http://always-upstream", "AG", "always")),
                List.of());
        Function<String, RemoteCorpusClient> factory = url -> alwaysClient;
        var walker = new HttpFederationWalker(config, new DirectExecutor(), factory);

        var own = List.of(
                result("e1", HIGH, "my-garden", "MG"),
                result("e2", HIGH, "my-garden", "MG"),
                result("e3", HIGH, "my-garden", "MG"));

        var results = walker.walk("query", null, null, null, 10, own, visited());
        assertThat(alwaysClient.callCount).isEqualTo(1);
        assertThat(results).anyMatch(r -> r.source().equals("always-garden"));
    }

    @Test
    void visitedHeaderPassedToUpstream() {
        var walker = childWalker();
        upstreamClient.response = List.of();

        var v = new LinkedHashSet<>(Set.of("my-garden"));
        walker.walk("query", null, null, null, LIMIT, List.of(result("e1", LOW, "my-garden", "MG")), v);

        assertThat(upstreamClient.lastVisited).contains("my-garden");
    }

    @Test
    void typeAndTagsPassedToUpstream() {
        var walker = childWalker();
        upstreamClient.response = List.of();

        var v = new LinkedHashSet<>(Set.of("my-garden"));
        walker.walk("query", null, "gotcha", "qdrant,cdi", LIMIT,
                List.of(result("e1", LOW, "my-garden", "MG")), v);

        assertThat(upstreamClient.lastType).isEqualTo("gotcha");
        assertThat(upstreamClient.lastTags).isEqualTo("qdrant,cdi");
    }

    // --- Helpers ---

    private HttpFederationWalker canonicalWalker() {
        var config = new FederationConfig("my-garden", "MG", "canonical", THRESHOLD, 5, 5,
                List.of(), List.of());
        return new HttpFederationWalker(config, new DirectExecutor(), url -> upstreamClient);
    }

    private HttpFederationWalker childWalker() {
        var config = new FederationConfig("my-garden", "MG", "child", THRESHOLD, 5, 5,
                List.of(new FederationConfig.UpstreamRef("http://parent", "PG", "fallback")),
                List.of());
        return new HttpFederationWalker(config, new DirectExecutor(), url -> upstreamClient);
    }

    private HttpFederationWalker childWithPeerWalker() {
        var config = new FederationConfig("my-garden", "MG", "child", THRESHOLD, 5, 5,
                List.of(new FederationConfig.UpstreamRef("http://parent", "PG", "fallback")),
                List.of(new FederationConfig.PeerRef("http://peer", "PR")));
        Function<String, RemoteCorpusClient> factory = url ->
                url.contains("peer") ? peerClient : upstreamClient;
        return new HttpFederationWalker(config, new DirectExecutor(), factory);
    }

    private static SearchResult result(String id, double relevance, String source, String prefix) {
        return new SearchResult(id, "Title " + id, "jvm", "gotcha", 8, "Body", relevance, null, source, prefix);
    }

    private static Set<String> visited() {
        return new LinkedHashSet<>(Set.of("my-garden"));
    }

    static class RecordingClient implements RemoteCorpusClient {
        List<SearchResult> response = List.of();
        boolean shouldThrow = false;
        int callCount = 0;
        String lastVisited;
        String lastType;
        String lastTags;

        @Override
        public List<SearchResult> search(String query, List<String> domains, String type, String tags,
                                         int limit, String visited) {
            callCount++;
            lastVisited = visited;
            lastType = type;
            lastTags = tags;
            if (shouldThrow) {
                throw new RuntimeException("Connection timeout");
            }
            return response;
        }
    }

    static class DirectExecutor extends AbstractExecutorService {
        private volatile boolean shutdown = false;

        @Override public void shutdown() { shutdown = true; }
        @Override public List<Runnable> shutdownNow() { shutdown = true; return List.of(); }
        @Override public boolean isShutdown() { return shutdown; }
        @Override public boolean isTerminated() { return shutdown; }
        @Override public boolean awaitTermination(long timeout, TimeUnit unit) { return true; }
        @Override public void execute(Runnable command) { command.run(); }
    }
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl corpus-management -Dtest=HttpFederationWalkerTest -q`
Expected: FAIL — `RemoteCorpusClient` and `HttpFederationWalker` don't exist.

- [ ] **Step 3: Create RemoteCorpusClient interface**

```java
package io.casehub.neocortex.corpus.management.impl;

import java.util.List;

@FunctionalInterface
public interface RemoteCorpusClient {

    List<SearchResult> search(String query, List<String> domains, String type, String tags,
                              int limit, String visited);
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

- [ ] **Step 4: Create HttpFederationWalker implementation**

```java
package io.casehub.neocortex.corpus.management.impl;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.function.Function;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;

public class HttpFederationWalker implements SearchResource.FederationWalker {

    private static final Logger LOG = Logger.getLogger(HttpFederationWalker.class.getName());

    static final int TIER_OWN = 0;
    static final int TIER_PEER = Integer.MAX_VALUE;

    private final FederationConfig config;
    private final ExecutorService executor;
    private final Map<String, RemoteCorpusClient> upstreamClients = new LinkedHashMap<>();
    private final Map<String, RemoteCorpusClient> peerClients = new LinkedHashMap<>();

    public HttpFederationWalker(FederationConfig config, ExecutorService executor,
                                 Function<String, RemoteCorpusClient> clientFactory) {
        this.config = config;
        this.executor = executor;
        for (var ref : config.upstream()) {
            upstreamClients.put(ref.url(), clientFactory.apply(ref.url()));
        }
        for (var ref : config.peers()) {
            peerClients.put(ref.url(), clientFactory.apply(ref.url()));
        }
    }

    @Override
    public List<SearchResult> walk(String query, List<String> domains, String type, String tags,
                                    int maxResults, List<SearchResult> ownResults, Set<String> visited) {
        if (!config.hasFederation()) {
            return ownResults;
        }

        List<TieredResult> all = new ArrayList<>();
        ownResults.forEach(r -> all.add(new TieredResult(r, TIER_OWN)));

        boolean sufficient = isSufficient(ownResults, maxResults);

        if (!sufficient || hasAlwaysUpstream()) {
            String visitedHeader = String.join(",", visited);
            int upstreamIndex = 0;
            for (var ref : config.upstream()) {
                boolean shouldQuery = "always".equals(ref.searchOrder()) || !sufficient;
                if (!shouldQuery) {
                    upstreamIndex++;
                    continue;
                }

                int tier = upstreamIndex + 1;
                try {
                    RemoteCorpusClient client = upstreamClients.get(ref.url());
                    List<SearchResult> results = client.search(query, domains, type, tags, maxResults, visitedHeader);
                    results.forEach(r -> all.add(new TieredResult(r, tier)));

                    if (!sufficient && isSufficientCombined(all, maxResults)) {
                        sufficient = true;
                        break;
                    }
                } catch (Exception e) {
                    LOG.log(Level.WARNING, "Federation upstream {0} failed: {1}",
                            new Object[]{ref.url(), e.getMessage()});
                }
                upstreamIndex++;
            }
        }

        if (!isSufficientCombined(all, maxResults) && config.hasPeers()) {
            String visitedHeader = String.join(",", visited);
            List<Callable<List<SearchResult>>> peerCalls = config.peers().stream()
                    .map(ref -> (Callable<List<SearchResult>>) () -> {
                        RemoteCorpusClient client = peerClients.get(ref.url());
                        return client.search(query, domains, type, tags, maxResults, visitedHeader);
                    })
                    .toList();

            try {
                List<Future<List<SearchResult>>> futures = executor.invokeAll(
                        peerCalls, config.federationTimeoutSeconds(), TimeUnit.SECONDS);
                for (var future : futures) {
                    try {
                        if (future.isDone() && !future.isCancelled()) {
                            future.get().forEach(r -> all.add(new TieredResult(r, TIER_PEER)));
                        }
                    } catch (ExecutionException e) {
                        LOG.log(Level.WARNING, "Federation peer failed: {0}",
                                e.getCause().getMessage());
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                LOG.warning("Federation peer fan-out interrupted");
            }
        }

        return merge(all, maxResults);
    }

    private boolean isSufficient(List<SearchResult> results, int limit) {
        long aboveThreshold = results.stream()
                .filter(r -> r.relevance() >= config.relevanceThreshold())
                .count();
        return aboveThreshold >= limit;
    }

    private boolean isSufficientCombined(List<TieredResult> results, int limit) {
        long aboveThreshold = results.stream()
                .filter(r -> r.result.relevance() >= config.relevanceThreshold())
                .count();
        return aboveThreshold >= limit;
    }

    private boolean hasAlwaysUpstream() {
        return config.upstream().stream().anyMatch(ref -> "always".equals(ref.searchOrder()));
    }

    static List<SearchResult> merge(List<TieredResult> all, int limit) {
        Set<DedupKey> seen = new LinkedHashSet<>();
        List<TieredResult> deduped = new ArrayList<>();
        for (var tr : all) {
            if (seen.add(new DedupKey(tr.result.id(), tr.result.source()))) {
                deduped.add(tr);
            }
        }

        return deduped.stream()
                .collect(Collectors.groupingBy(tr -> tr.tier))
                .entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .flatMap(entry -> entry.getValue().stream()
                        .sorted(Comparator.comparingDouble((TieredResult tr) -> tr.result.relevance()).reversed())
                        .map(tr -> tr.result))
                .limit(limit)
                .toList();
    }

    record TieredResult(SearchResult result, int tier) {}
    record DedupKey(String id, String source) {}
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl corpus-management -Dtest=HttpFederationWalkerTest -q`
Expected: PASS — all 13 tests green.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex add corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/RemoteCorpusClient.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/HttpFederationWalker.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/HttpFederationWalkerTest.java
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex commit -m "feat(#775): add RemoteCorpusClient and HttpFederationWalker

Generified HTTP federation from Hortora ChainWalker. Pure Java,
constructor injection, no CDI/Quarkus deps.

Refs #775"
```

### Task 2: Move FederationConfigParser to corpus-management

**Files:**
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/FederationConfigParser.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/FederationConfigParserTest.java`
- Copy: test fixtures from `Hortora engine/src/test/resources/fixtures/schema/*.yaml` → `corpus-management/src/test/resources/fixtures/schema/`

**Interfaces:**
- Consumes: `FederationConfig` (existing record in corpus-management)
- Produces: `FederationConfigParser` (static utility + convenience constructor)

- [ ] **Step 1: Copy test fixtures from Hortora**

Copy all 9 YAML fixture files from `/Users/mdproctor/claude/hortora/engine/src/test/resources/fixtures/schema/` to `/Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/test/resources/fixtures/schema/` using bash (non-code files).

```bash
mkdir -p /Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/test/resources/fixtures/schema
cp /Users/mdproctor/claude/hortora/engine/src/test/resources/fixtures/schema/*.yaml /Users/mdproctor/claude/casehub/slots/221/neocortex/corpus-management/src/test/resources/fixtures/schema/
```

- [ ] **Step 2: Write the failing test**

```java
package io.casehub.neocortex.corpus.management.impl;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class FederationConfigParserTest {

    @Test
    void parsesValidChildConfig() throws IOException {
        var config = parse("valid-child.yaml");

        assertThat(config.gardenId()).isEqualTo("my-garden");
        assertThat(config.idPrefix()).isEqualTo("PE");
        assertThat(config.role()).isEqualTo("child");
        assertThat(config.relevanceThreshold()).isEqualTo(0.7);
        assertThat(config.maxDepth()).isEqualTo(5);

        assertThat(config.upstream()).hasSize(2);
        assertThat(config.upstream().get(0).url()).isEqualTo("https://api.hortora.io/jvm");
        assertThat(config.upstream().get(0).idPrefix()).isEqualTo("GE");
        assertThat(config.upstream().get(0).searchOrder()).isEqualTo("fallback");
        assertThat(config.upstream().get(1).url()).isEqualTo("https://enterprise.internal/garden");
        assertThat(config.upstream().get(1).idPrefix()).isEqualTo("EP");
        assertThat(config.upstream().get(1).searchOrder()).isEqualTo("always");

        assertThat(config.peers()).hasSize(1);
        assertThat(config.peers().get(0).url()).isEqualTo("http://localhost:8091");
        assertThat(config.peers().get(0).idPrefix()).isEqualTo("RE");
    }

    @Test
    void parsesCanonicalWithNoUpstreamOrPeers() throws IOException {
        var config = parse("valid-canonical.yaml");

        assertThat(config.gardenId()).isEqualTo("jvm-garden");
        assertThat(config.idPrefix()).isEqualTo("GE");
        assertThat(config.role()).isEqualTo("canonical");
        assertThat(config.upstream()).isEmpty();
        assertThat(config.peers()).isEmpty();
        assertThat(config.hasFederation()).isFalse();
    }

    @Test
    void noFederationBlockReturnsDefaults() throws IOException {
        var config = parse("no-federation.yaml");

        assertThat(config.gardenId()).isEqualTo("solo-garden");
        assertThat(config.idPrefix()).isEqualTo("SG");
        assertThat(config.role()).isEqualTo("canonical");
        assertThat(config.relevanceThreshold()).isEqualTo(0.7);
        assertThat(config.maxDepth()).isEqualTo(5);
        assertThat(config.upstream()).isEmpty();
        assertThat(config.peers()).isEmpty();
    }

    @Test
    void missingFileReturnsDefaults(@TempDir Path tempDir) throws IOException {
        var config = FederationConfigParser.parse(
                tempDir.resolve("nonexistent.yaml"), "default-garden", "DG");

        assertThat(config.gardenId()).isEqualTo("default-garden");
        assertThat(config.idPrefix()).isEqualTo("DG");
        assertThat(config.role()).isEqualTo("canonical");
        assertThat(config.hasFederation()).isFalse();
    }

    @Test
    void malformedYamlThrows() {
        assertThatThrownBy(() -> parse("malformed.yaml"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Failed to parse");
    }

    @Test
    void invalidRoleThrows() {
        assertThatThrownBy(() -> parse("invalid-role.yaml"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("role");
    }

    @Test
    void invalidUrlThrows() {
        assertThatThrownBy(() -> parse("invalid-url.yaml"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("URL");
    }

    @Test
    void missingIdThrows() {
        assertThatThrownBy(() -> parse("missing-id.yaml"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("id");
    }

    @Test
    void defaultRelevanceThreshold() throws IOException {
        var config = parse("valid-canonical.yaml");
        assertThat(config.relevanceThreshold()).isEqualTo(0.7);
    }

    @Test
    void defaultMaxDepth() throws IOException {
        var config = parse("valid-canonical.yaml");
        assertThat(config.maxDepth()).isEqualTo(5);
    }

    @Test
    void invalidSearchOrderThrows() {
        assertThatThrownBy(() -> parse("invalid-search-order.yaml"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("search-order");
    }

    @Test
    void crlfLineEndingsParseCorrectly(@TempDir Path tempDir) throws IOException {
        String content = "---\r\nschema-version: 2.0.0\r\nid: crlf-garden\r\nid-prefix: CR\r\n\r\n" +
                "federation:\r\n  role: canonical\r\n---\r\n";
        Path crlfFile = tempDir.resolve("crlf-schema.yaml");
        Files.writeString(crlfFile, content);

        var config = FederationConfigParser.parse(crlfFile, "fallback-id", "FB");

        assertThat(config.gardenId()).isEqualTo("crlf-garden");
        assertThat(config.idPrefix()).isEqualTo("CR");
        assertThat(config.role()).isEqualTo("canonical");
    }

    @Test
    void parsesTimeoutSeconds() throws IOException {
        var config = parse("with-timeout.yaml");
        assertThat(config.federationTimeoutSeconds()).isEqualTo(10);
    }

    @Test
    void defaultTimeoutIsFiveSeconds() throws IOException {
        var config = parse("valid-child.yaml");
        assertThat(config.federationTimeoutSeconds()).isEqualTo(5);
    }

    private FederationConfig parse(String fixtureFilename) throws IOException {
        Path fixture = Path.of("src/test/resources/fixtures/schema/" + fixtureFilename);
        return FederationConfigParser.parse(fixture, "fallback-id", "FB");
    }
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl corpus-management -Dtest=FederationConfigParserTest -q`
Expected: FAIL — `FederationConfigParser` class does not exist.

- [ ] **Step 4: Create FederationConfigParser (generified from Hortora)**

```java
package io.casehub.neocortex.corpus.management.impl;

import org.yaml.snakeyaml.Yaml;

import java.io.IOException;
import java.net.URI;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class FederationConfigParser {

    private static final Set<String> VALID_ROLES = Set.of("canonical", "child", "peer");
    private static final Set<String> VALID_SEARCH_ORDERS = Set.of("fallback", "always");
    private static final double DEFAULT_RELEVANCE_THRESHOLD = 0.7;
    private static final int DEFAULT_MAX_DEPTH = 5;
    private static final int DEFAULT_FEDERATION_TIMEOUT_SECONDS = 5;

    private final FederationConfig config;

    public FederationConfigParser(Path schemaPath, String id, String idPrefix) throws IOException {
        this.config = parse(schemaPath, id, idPrefix);
    }

    public FederationConfig config() {
        return config;
    }

    @SuppressWarnings("unchecked")
    public static FederationConfig parse(Path schemaPath, String fallbackId, String fallbackPrefix)
            throws IOException {

        if (!Files.exists(schemaPath)) {
            return defaultConfig(fallbackId, fallbackPrefix);
        }

        String content = Files.readString(schemaPath);
        content = content.replace("\r\n", "\n");
        String[] parts = content.split("---\n", 3);
        if (parts.length < 2 || parts[1].isBlank()) {
            return defaultConfig(fallbackId, fallbackPrefix);
        }

        Map<String, Object> yaml;
        try {
            yaml = new Yaml().load(parts[1]);
        } catch (Exception e) {
            throw new IllegalArgumentException("Failed to parse SCHEMA.md YAML: " + e.getMessage(), e);
        }

        if (yaml == null) {
            return defaultConfig(fallbackId, fallbackPrefix);
        }

        String gardenId = requireString(yaml, "id", "SCHEMA.md must have an 'id' field");
        String idPrefix = requireString(yaml, "id-prefix", "SCHEMA.md must have an 'id-prefix' field");

        Map<String, Object> federation = (Map<String, Object>) yaml.get("federation");
        if (federation == null) {
            return new FederationConfig(gardenId, idPrefix, "canonical",
                    DEFAULT_RELEVANCE_THRESHOLD, DEFAULT_MAX_DEPTH, DEFAULT_FEDERATION_TIMEOUT_SECONDS,
                    List.of(), List.of());
        }

        String role = (String) federation.getOrDefault("role", "canonical");
        if (!VALID_ROLES.contains(role)) {
            throw new IllegalArgumentException(
                    "Invalid federation role: '" + role + "'. Must be one of: " + VALID_ROLES);
        }

        double threshold = federation.containsKey("relevance-threshold")
                ? ((Number) federation.get("relevance-threshold")).doubleValue()
                : DEFAULT_RELEVANCE_THRESHOLD;

        int maxDepth = federation.containsKey("max-depth")
                ? ((Number) federation.get("max-depth")).intValue()
                : DEFAULT_MAX_DEPTH;

        int timeoutSeconds = federation.containsKey("timeout-seconds")
                ? ((Number) federation.get("timeout-seconds")).intValue()
                : DEFAULT_FEDERATION_TIMEOUT_SECONDS;

        List<FederationConfig.UpstreamRef> upstream = parseUpstream(
                (List<Map<String, Object>>) federation.get("upstream"));
        List<FederationConfig.PeerRef> peers = parsePeers(
                (List<Map<String, Object>>) federation.get("peers"));

        return new FederationConfig(gardenId, idPrefix, role, threshold, maxDepth, timeoutSeconds,
                upstream, peers);
    }

    private static List<FederationConfig.UpstreamRef> parseUpstream(List<Map<String, Object>> raw) {
        if (raw == null) return List.of();
        return raw.stream().map(entry -> {
            String url = requireString(entry, "url", "Upstream entry must have a 'url' field");
            validateUrl(url);
            String prefix = requireString(entry, "id-prefix",
                    "Upstream entry must have an 'id-prefix' field");
            String order = (String) entry.getOrDefault("search-order", "fallback");
            if (!VALID_SEARCH_ORDERS.contains(order)) {
                throw new IllegalArgumentException(
                        "Invalid search-order: '" + order + "'. Must be one of: " + VALID_SEARCH_ORDERS);
            }
            return new FederationConfig.UpstreamRef(url, prefix, order);
        }).toList();
    }

    private static List<FederationConfig.PeerRef> parsePeers(List<Map<String, Object>> raw) {
        if (raw == null) return List.of();
        return raw.stream().map(entry -> {
            String url = requireString(entry, "url", "Peer entry must have a 'url' field");
            validateUrl(url);
            String prefix = requireString(entry, "id-prefix",
                    "Peer entry must have an 'id-prefix' field");
            return new FederationConfig.PeerRef(url, prefix);
        }).toList();
    }

    private static String requireString(Map<String, Object> map, String key, String message) {
        Object value = map.get(key);
        if (value == null || value.toString().isBlank()) {
            throw new IllegalArgumentException(message);
        }
        return value.toString();
    }

    private static void validateUrl(String url) {
        try {
            URI uri = URI.create(url);
            if (uri.getScheme() == null) {
                throw new IllegalArgumentException("URL has no scheme: " + url);
            }
        } catch (IllegalArgumentException e) {
            throw new IllegalArgumentException("Invalid URL in federation config: " + url, e);
        }
    }

    private static FederationConfig defaultConfig(String gardenId, String idPrefix) {
        return new FederationConfig(gardenId, idPrefix, "canonical",
                DEFAULT_RELEVANCE_THRESHOLD, DEFAULT_MAX_DEPTH, DEFAULT_FEDERATION_TIMEOUT_SECONDS,
                List.of(), List.of());
    }
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl corpus-management -Dtest=FederationConfigParserTest -q`
Expected: PASS — all 14 tests green.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex add corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/FederationConfigParser.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/FederationConfigParserTest.java corpus-management/src/test/resources/fixtures/schema/
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex commit -m "feat(#775): add FederationConfigParser to corpus-management

Generified from Hortora — pure Java, no CDI. Static parse() method
for YAML frontmatter schema docs. Includes all test fixtures.

Refs #775"
```

---

## Batch 2: Outcome Service + Collection Migration

### Task 3: Create CorpusOutcomeService in corpus-management

**Files:**
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusOutcomeService.java`
- Test: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusOutcomeServiceTest.java`

**Interfaces:**
- Consumes: `CbrRecordStore`, `CbrGuidanceRecord`, `CbrOutcome`, `CbrScanRequest`, `CbrScanResult`, `CbrRecordSummary` (from memory-api, already optional dep), `Path` (from casehub-platform-api)
- Produces: `CorpusOutcomeService` (pure Java, constructor injection)

- [ ] **Step 1: Write the failing test**

```java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.memory.cbr.CbrRecordStore;
import io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrRecordStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class CorpusOutcomeServiceTest {

    private CbrRecordStore cbrStore;
    private CorpusOutcomeService service;

    @BeforeEach
    void setUp() {
        cbrStore = new InMemoryCbrRecordStore();
        service = new CorpusOutcomeService(cbrStore, "test-corpus", "corpus", "corpus-outcome");
    }

    @Test
    void recordOutcomeCreatesCase() {
        String result = service.recordOutcome(
                "CE-20261102-a1b2c3", "casehubio/neocortex", 775,
                "Refactoring corpus management", 0.8, "Relevant and current");

        assertThat(result).contains("CE-20261102-a1b2c3");
        assertThat(result).contains("recorded");
    }

    @Test
    void secondOutcomeAdjustsConfidence() {
        service.recordOutcome("CE-20261102-a1b2c3", "casehubio/neocortex", 775,
                "First task", 1.0, "Very helpful");
        service.recordOutcome("CE-20261102-a1b2c3", "casehubio/neocortex", 776,
                "Second task", 0.0, "Not relevant");

        String report = service.outcomeReport();
        assertThat(report).contains("CE-20261102-a1b2c3");
        assertThat(report).contains("trust");
    }

    @Test
    void outcomeReportEmptyWhenNoOutcomes() {
        String report = service.outcomeReport();
        assertThat(report).contains("No outcome data");
    }

    @Test
    void recordOutcomeDoesNotCreateDuplicates() {
        service.recordOutcome("CE-20261102-a1b2c3", "casehubio/neocortex", 775,
                "First", 1.0, null);
        service.recordOutcome("CE-20261102-a1b2c3", "casehubio/neocortex", 776,
                "Second", 0.5, null);
        service.recordOutcome("CE-20261102-a1b2c3", "casehubio/neocortex", 777,
                "Third", 0.0, null);

        String report = service.outcomeReport();
        long count = report.lines()
                .filter(l -> l.contains("CE-20261102-a1b2c3"))
                .count();
        assertThat(count).isEqualTo(1);
    }
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

**Note:** This test depends on `InMemoryCbrRecordStore` from `memory-cbr-inmem`. Add a test-scoped dependency in `corpus-management/pom.xml`:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-cbr-inmem</artifactId>
    <scope>test</scope>
</dependency>
```

Also add `casehub-platform-api` as an optional dependency (for `Path`):

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-platform-api</artifactId>
    <optional>true</optional>
</dependency>
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl corpus-management -Dtest=CorpusOutcomeServiceTest -q`
Expected: FAIL — `CorpusOutcomeService` does not exist.

- [ ] **Step 3: Create CorpusOutcomeService**

```java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.CbrGuidanceRecord;
import io.casehub.neocortex.memory.cbr.CbrOutcome;
import io.casehub.neocortex.memory.cbr.CbrRecordStore;
import io.casehub.neocortex.memory.cbr.CbrRecordSummary;
import io.casehub.neocortex.memory.cbr.CbrScanRequest;
import io.casehub.neocortex.memory.cbr.CbrScanResult;
import io.casehub.platform.api.path.Path;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public class CorpusOutcomeService {

    private final CbrRecordStore cbrStore;
    private final String tenantId;
    private final String scopePrefix;
    private final String caseType;

    public CorpusOutcomeService(CbrRecordStore cbrStore, String tenantId,
                                 String scopePrefix, String caseType) {
        this.cbrStore = cbrStore;
        this.tenantId = tenantId;
        this.scopePrefix = scopePrefix;
        this.caseType = caseType;
    }

    public String recordOutcome(String entryId, String issueRepo, int issueNumber,
                                 String workContext, double successRate, String detail) {
        boolean exists = scanAllCases().stream()
                .anyMatch(c -> entryId.equals(c.caseId()));

        if (!exists) {
            String problem = workContext + " (" + issueRepo + "#" + issueNumber + ")";
            var cbrCase = new CbrGuidanceRecord(problem, entryId, null,
                    Confidence.unknown(1.0), null, null);
            cbrStore.store(cbrCase, caseType, entryId,
                    new MemoryDomain("knowledge"), tenantId, entryId,
                    Path.of(scopePrefix, tenantId));
        }

        CbrOutcome outcome = CbrOutcome.of(successRate,
                detail != null ? detail : "", Instant.now());
        cbrStore.recordOutcome(entryId, outcome, tenantId);

        return "Outcome recorded for " + entryId + " (success=" + successRate + ")";
    }

    public String outcomeReport() {
        List<CbrRecordSummary> cases = scanAllCases();

        if (cases.isEmpty()) {
            return "No outcome data recorded yet.";
        }

        List<CbrRecordSummary> sorted = cases.stream()
                .sorted(Comparator.comparingDouble(c -> c.trustScore() != null ? c.trustScore() : 1.0))
                .toList();

        StringBuilder sb = new StringBuilder();
        sb.append("## Corpus Entry Outcome Report\n\n");
        sb.append("Entries with recorded outcomes, sorted by trust score (lowest first):\n\n");

        for (CbrRecordSummary c : sorted) {
            sb.append("- **").append(c.caseId()).append("**");
            if (c.trustScore() != null) {
                sb.append(" — trust: ").append(String.format("%.2f", c.trustScore()));
            }
            sb.append("\n");
        }

        return sb.toString();
    }

    public void clearAll() {
        cbrStore.eraseByScope(Path.of(scopePrefix, tenantId), tenantId);
    }

    private List<CbrRecordSummary> scanAllCases() {
        List<CbrRecordSummary> all = new ArrayList<>();
        String cursor = null;
        do {
            CbrScanResult page = cbrStore.scan(new CbrScanRequest(
                    tenantId, new MemoryDomain("knowledge"), caseType, 100, cursor));
            all.addAll(page.items());
            cursor = page.hasMore() ? page.nextCursor() : null;
        } while (cursor != null);
        return all;
    }
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl corpus-management -Dtest=CorpusOutcomeServiceTest -q`
Expected: PASS — all 4 tests green.

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex add corpus-management/pom.xml corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusOutcomeService.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusOutcomeServiceTest.java
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex commit -m "feat(#775): add CorpusOutcomeService — generified outcome tracking

Constructor-injected CBR outcome service. Replaces Hortora's
GardenOutcomeService with configurable tenant/scope/caseType.

Refs #775"
```

### Task 4: Create CorpusCollectionMigration in rag module

**Files:**
- Create: `rag/src/main/java/io/casehub/neocortex/rag/runtime/CorpusCollectionMigration.java`
- Test: `rag/src/test/java/io/casehub/neocortex/rag/runtime/CorpusCollectionMigrationTest.java`

**Interfaces:**
- Consumes: `MultiModalEmbedder`, `QdrantClient`, `EmbeddingIngestor`, `CursorStore`, `RagConfig`, `CollectionCompatibility`, `CollectionExpectedConfig`, `MigrationAction`, `CorpusRef` — all already in the rag module's classpath
- Produces: `CorpusCollectionMigration` (pure Java, constructor injection, no `@Observes`)

- [ ] **Step 1: Write the failing test**

Port from Hortora's `CollectionMigrationTest`, replacing `GardenConfig gardenConfig` with `String corpusId` and `String corpusPrefix`, and `onStartup()` with `checkAndMigrate()`.

```java
package io.casehub.neocortex.rag.runtime;

import com.google.common.util.concurrent.Futures;
import io.casehub.neocortex.inference.EmbeddingMode;
import io.casehub.neocortex.inference.MultiModalEmbedder;
import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.CursorStore;
import io.casehub.neocortex.rag.EmbeddingIngestor;
import io.qdrant.client.QdrantClient;
import io.qdrant.client.grpc.Collections.CollectionConfig;
import io.qdrant.client.grpc.Collections.CollectionInfo;
import io.qdrant.client.grpc.Collections.CollectionParams;
import io.qdrant.client.grpc.Collections.SparseVectorConfig;
import io.qdrant.client.grpc.Collections.SparseVectorParams;
import io.qdrant.client.grpc.Collections.VectorParams;
import io.qdrant.client.grpc.Collections.VectorParamsMap;
import io.qdrant.client.grpc.Collections.VectorsConfig;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.OptionalInt;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class CorpusCollectionMigrationTest {

    private MultiModalEmbedder multiModalEmbedder;
    private QdrantClient qdrantClient;
    private EmbeddingIngestor embeddingIngestor;
    private CursorStore cursorStore;
    private RagConfig ragConfig;
    private CorpusCollectionMigration migration;

    @BeforeEach
    void setUp() {
        multiModalEmbedder = mock(MultiModalEmbedder.class);
        qdrantClient = mock(QdrantClient.class);
        embeddingIngestor = mock(EmbeddingIngestor.class);
        cursorStore = mock(CursorStore.class);
        ragConfig = mock(RagConfig.class);

        when(ragConfig.tenancyStrategy()).thenReturn(TenancyStrategy.SEPARATE_COLLECTIONS);
        when(multiModalEmbedder.denseDimension()).thenReturn(1024);
        when(multiModalEmbedder.colbertDimension()).thenReturn(OptionalInt.of(1024));
        when(multiModalEmbedder.supportedModes()).thenReturn(
                Set.of(EmbeddingMode.DENSE, EmbeddingMode.SPARSE, EmbeddingMode.COLBERT));
        when(multiModalEmbedder.maxSequenceLength()).thenReturn(768);
        when(ragConfig.maxMultivectorFloats()).thenReturn(1_000_000);
        when(qdrantClient.listCollectionsAsync())
                .thenReturn(Futures.immediateFuture(java.util.List.of()));

        migration = new CorpusCollectionMigration(
                multiModalEmbedder, qdrantClient,
                embeddingIngestor, cursorStore,
                "garden", "hortora", ragConfig);
    }

    @Test
    void migratesWhenCollectionExistsWithoutSparseVectors() throws Exception {
        when(qdrantClient.collectionExistsAsync("hortora_garden"))
                .thenReturn(Futures.immediateFuture(true));

        CollectionParams params = CollectionParams.newBuilder()
                .setVectorsConfig(VectorsConfig.newBuilder()
                        .setParamsMap(VectorParamsMap.newBuilder()
                                .putMap("dense", VectorParams.newBuilder().setSize(1024).build())
                                .build())
                        .build())
                .build();
        CollectionConfig config = CollectionConfig.newBuilder().setParams(params).build();
        CollectionInfo info = CollectionInfo.newBuilder().setConfig(config).build();
        when(qdrantClient.getCollectionInfoAsync("hortora_garden"))
                .thenReturn(Futures.immediateFuture(info));

        migration.checkAndMigrate(5, 0);

        verify(embeddingIngestor).deleteCorpus(eq(new CorpusRef("hortora", "garden")));
        verify(cursorStore).save("garden", "");
    }

    @Test
    void noOpWhenCollectionFullyMigrated() throws Exception {
        when(qdrantClient.collectionExistsAsync("hortora_garden"))
                .thenReturn(Futures.immediateFuture(true));

        CollectionParams params = CollectionParams.newBuilder()
                .setVectorsConfig(VectorsConfig.newBuilder()
                        .setParamsMap(VectorParamsMap.newBuilder()
                                .putMap("dense", VectorParams.newBuilder().setSize(1024).build())
                                .putMap("colbert", VectorParams.newBuilder().setSize(1024).build())
                                .build())
                        .build())
                .setSparseVectorsConfig(SparseVectorConfig.newBuilder()
                        .putMap("sparse", SparseVectorParams.getDefaultInstance())
                        .build())
                .build();
        CollectionConfig config = CollectionConfig.newBuilder().setParams(params).build();
        CollectionInfo info = CollectionInfo.newBuilder().setConfig(config).build();
        when(qdrantClient.getCollectionInfoAsync("hortora_garden"))
                .thenReturn(Futures.immediateFuture(info));

        migration.checkAndMigrate(5, 0);

        verify(embeddingIngestor, never()).deleteCorpus(any());
        verify(cursorStore, never()).save(any(), any());
    }

    @Test
    void noOpWhenCollectionDoesNotExistAndNoCursor() throws Exception {
        when(qdrantClient.collectionExistsAsync("hortora_garden"))
                .thenReturn(Futures.immediateFuture(false));
        when(cursorStore.load("garden")).thenReturn(java.util.Optional.empty());

        migration.checkAndMigrate(5, 0);

        verify(qdrantClient, never()).getCollectionInfoAsync(any());
        verify(embeddingIngestor, never()).deleteCorpus(any());
    }

    @Test
    void clearsStaleCursorWhenCollectionDoesNotExist() throws Exception {
        when(qdrantClient.collectionExistsAsync("hortora_garden"))
                .thenReturn(Futures.immediateFuture(false));
        when(cursorStore.load("garden")).thenReturn(java.util.Optional.of("{\"file.md\":123}"));

        migration.checkAndMigrate(5, 0);

        verify(cursorStore).save("garden", "");
    }

    @Test
    void colbertValidationFailsExceedingLimit() {
        when(multiModalEmbedder.maxSequenceLength()).thenReturn(1024);
        when(multiModalEmbedder.colbertDimension()).thenReturn(OptionalInt.of(1024));
        when(ragConfig.maxMultivectorFloats()).thenReturn(1_000_000);

        var m = new CorpusCollectionMigration(
                multiModalEmbedder, qdrantClient, embeddingIngestor, cursorStore,
                "garden", "hortora", ragConfig);
        assertThrows(IllegalStateException.class, () -> m.checkAndMigrate(5, 0));
    }

    @Test
    void resetCorpusDeletesAndResetsCursor() {
        CorpusRef corpusRef = new CorpusRef("hortora", "garden");
        migration.resetCorpus(corpusRef);

        verify(embeddingIngestor).deleteCorpus(eq(corpusRef));
        verify(cursorStore).save("garden", "");
    }

    @Test
    void retriesWhenQdrantUnavailableOnStartup() throws Exception {
        when(qdrantClient.listCollectionsAsync())
                .thenReturn(Futures.immediateFailedFuture(
                        new io.grpc.StatusRuntimeException(io.grpc.Status.UNAVAILABLE)))
                .thenReturn(Futures.immediateFailedFuture(
                        new io.grpc.StatusRuntimeException(io.grpc.Status.UNAVAILABLE)))
                .thenReturn(Futures.immediateFuture(java.util.List.of()));

        when(qdrantClient.collectionExistsAsync("hortora_garden"))
                .thenReturn(Futures.immediateFuture(false));
        when(cursorStore.load("garden")).thenReturn(java.util.Optional.empty());

        migration.checkAndMigrate(5, 0);

        verify(qdrantClient, times(3)).listCollectionsAsync();
    }
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

**Note:** Add mockito test-scoped dependency to `rag/pom.xml` if not already present:

```xml
<dependency>
    <groupId>org.mockito</groupId>
    <artifactId>mockito-core</artifactId>
    <scope>test</scope>
</dependency>
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl rag -Dtest=CorpusCollectionMigrationTest -q`
Expected: FAIL — `CorpusCollectionMigration` does not exist.

- [ ] **Step 3: Create CorpusCollectionMigration**

```java
package io.casehub.neocortex.rag.runtime;

import io.casehub.neocortex.inference.MultiModalEmbedder;
import io.casehub.neocortex.rag.CorpusRef;
import io.casehub.neocortex.rag.CursorStore;
import io.casehub.neocortex.rag.EmbeddingIngestor;
import io.qdrant.client.QdrantClient;

import java.util.concurrent.ExecutionException;
import java.util.logging.Level;
import java.util.logging.Logger;

public class CorpusCollectionMigration {

    private static final Logger LOG = Logger.getLogger(CorpusCollectionMigration.class.getName());

    private final MultiModalEmbedder embedder;
    private final QdrantClient qdrantClient;
    private final EmbeddingIngestor embeddingIngestor;
    private final CursorStore cursorStore;
    private final String corpusId;
    private final String corpusPrefix;
    private final RagConfig ragConfig;

    public CorpusCollectionMigration(MultiModalEmbedder embedder, QdrantClient qdrantClient,
                                     EmbeddingIngestor embeddingIngestor, CursorStore cursorStore,
                                     String corpusId, String corpusPrefix, RagConfig ragConfig) {
        this.embedder = embedder;
        this.qdrantClient = qdrantClient;
        this.embeddingIngestor = embeddingIngestor;
        this.cursorStore = cursorStore;
        this.corpusId = corpusId;
        this.corpusPrefix = corpusPrefix;
        this.ragConfig = ragConfig;
    }

    public void resetCorpus(CorpusRef corpusRef) {
        embeddingIngestor.deleteCorpus(corpusRef);
        cursorStore.save(corpusId, "");
    }

    public void checkAndMigrate(int maxRetries, long retryDelayMs) {
        validateColbertLimit();

        if (!waitForQdrant(maxRetries, retryDelayMs)) {
            return;
        }

        CorpusRef corpusRef = new CorpusRef(corpusPrefix, corpusId);
        String collectionName = ragConfig.tenancyStrategy().collectionName(corpusRef);

        try {
            if (!qdrantClient.collectionExistsAsync(collectionName).get()) {
                if (cursorStore.load(corpusId).isPresent()) {
                    LOG.log(Level.INFO,
                            "Collection ''{0}'' does not exist but cursor found — clearing cursor to force re-indexing",
                            collectionName);
                    cursorStore.save(corpusId, "");
                }
                return;
            }

            var expected = new CollectionExpectedConfig(
                    embedder.denseDimension(),
                    true,
                    embedder.colbertDimension().isPresent());
            MigrationAction action = CollectionCompatibility.check(qdrantClient, collectionName, expected);

            switch (action) {
                case MigrationAction.Compatible _ ->
                    LOG.log(Level.INFO, "Collection ''{0}'' is up-to-date — no migration needed",
                            collectionName);
                case MigrationAction.DimensionMismatch m -> {
                    LOG.log(Level.INFO,
                            "Collection ''{0}'' dense dimension {1} != expected {2} — re-indexing",
                            new Object[]{collectionName, m.actual(), m.expected()});
                    resetCorpus(corpusRef);
                }
                case MigrationAction.MissingSparseVectors _ -> {
                    LOG.log(Level.INFO, "Collection ''{0}'' lacks sparse vectors — re-indexing",
                            collectionName);
                    resetCorpus(corpusRef);
                }
                case MigrationAction.MissingColBert _ -> {
                    LOG.log(Level.INFO,
                            "Collection ''{0}'' lacks ColBERT multi-vector config — re-indexing",
                            collectionName);
                    resetCorpus(corpusRef);
                }
            }

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            LOG.log(Level.WARNING, "Interrupted during collection migration check", e);
        } catch (ExecutionException e) {
            LOG.log(Level.WARNING, "Failed to check collection for migration", e.getCause());
        }
    }

    private boolean waitForQdrant(int maxRetries, long delayMs) {
        for (int attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                qdrantClient.listCollectionsAsync().get();
                LOG.log(Level.INFO, "Qdrant ready (attempt {0}/{1})",
                        new Object[]{attempt, maxRetries});
                return true;
            } catch (ExecutionException e) {
                LOG.log(Level.WARNING, "Qdrant not ready (attempt {0}/{1}): {2}",
                        new Object[]{attempt, maxRetries, e.getCause().getMessage()});
                if (attempt < maxRetries && delayMs > 0) {
                    try { Thread.sleep(delayMs); } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        return false;
                    }
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        LOG.warning("Qdrant readiness check exhausted — proceeding without migration");
        return false;
    }

    private void validateColbertLimit() {
        if (embedder.colbertDimension().isEmpty()) {
            return;
        }
        int colbertDim = embedder.colbertDimension().getAsInt();
        long totalFloats = (long) embedder.maxSequenceLength() * colbertDim;
        int limit = ragConfig.maxMultivectorFloats();
        if (totalFloats > limit) {
            throw new IllegalStateException(
                    "ColBERT multi-vector size exceeds limit: maxSequenceLength=%d × colbertDimension=%d = %d floats > maxMultivectorFloats=%d. Reduce max-sequence-length or raise casehub.rag.max-multivector-floats."
                            .formatted(embedder.maxSequenceLength(), colbertDim, totalFloats, limit));
        }
    }
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/casehub/slots/221/neocortex`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl rag -Dtest=CorpusCollectionMigrationTest -q`
Expected: PASS — all 7 tests green.

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex add rag/pom.xml rag/src/main/java/io/casehub/neocortex/rag/runtime/CorpusCollectionMigration.java rag/src/test/java/io/casehub/neocortex/rag/runtime/CorpusCollectionMigrationTest.java
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex commit -m "feat(#775): add CorpusCollectionMigration — generified Qdrant migration

Constructor-injected, configurable corpusId/prefix. Replaces
Hortora CollectionMigration with no CDI/Quarkus deps.

Refs #775"
```

---

## Batch 3: Hortora Cleanup — Delete Migrated Code and Rewire

### Task 5: Delete migrated files from Hortora and rewire producers

**Files:**
- Delete: `src/main/java/io/hortora/garden/federation/ChainWalker.java` (use `ide_refactor_safe_delete`)
- Delete: `src/main/java/io/hortora/garden/federation/RemoteGardenClient.java` (use `ide_refactor_safe_delete`)
- Delete: `src/main/java/io/hortora/garden/federation/FederationConfigParser.java` (use `ide_refactor_safe_delete`)
- Delete: `src/main/java/io/hortora/garden/outcome/GardenOutcomeService.java` (use `ide_refactor_safe_delete`)
- Delete: `src/main/java/io/hortora/garden/inference/CollectionMigration.java` (use `ide_refactor_safe_delete`)
- Delete: `src/main/java/io/hortora/garden/search/TemporalDecayScorer.java` (use `ide_refactor_safe_delete`)
- Delete: `src/main/java/io/hortora/garden/search/VersionScorer.java` (use `ide_refactor_safe_delete`)
- Delete: corresponding test files (`ChainWalkerTest.java`, `FederationConfigParserTest.java`, `GardenOutcomeServiceTest.java`, `CollectionMigrationTest.java`)
- Delete: test fixtures `src/test/resources/fixtures/schema/` (now in neocortex)
- Modify: `src/main/java/io/hortora/garden/config/CorpusManagementProducer.java`
- Modify: `src/main/java/io/hortora/garden/mcp/GardenMcpTools.java`

All `ide_refactor_safe_delete` and edits use project_path `/Users/mdproctor/claude/hortora/engine`.

- [ ] **Step 1: Safe-delete ChainWalker and RemoteGardenClient**

Use `ide_refactor_safe_delete` on each file. Check for usages first — `CorpusManagementProducer` and `ChainWalkerTest` reference `ChainWalker`. Delete tests first, then source.

Delete test: `ide_refactor_safe_delete` file=`src/test/java/io/hortora/garden/federation/ChainWalkerTest.java`, target_type=file
Delete test: `ide_refactor_safe_delete` file=`src/test/java/io/hortora/garden/federation/FederationConfigParserTest.java`, target_type=file
Delete fixture dir: `rm -rf src/test/resources/fixtures/schema/` (non-code files, use bash)

- [ ] **Step 2: Update CorpusManagementProducer**

Replace `ChainWalker` import with `HttpFederationWalker` from neocortex. Replace `CollectionMigration` import with `CorpusCollectionMigration`. Update the `searchResource()` producer to create `HttpFederationWalker` using Quarkus REST client builder as the client factory. Update `reindexService()` to use `CorpusCollectionMigration`.

Use `ide_edit_member` to replace the class declaration and body:

```java
@ApplicationScoped
public class CorpusManagementProducer {

    @Inject GardenConfig gardenConfig;
    @Inject CaseRetriever caseRetriever;
    @Inject FederationConfig federationConfig;
    @Inject SearchConfig searchConfig;
    @Inject io.hortora.garden.provenance.ProvenanceConfig provenanceConfig;
    @Inject EmbeddingIngestor embeddingIngestor;
    @Inject org.eclipse.microprofile.context.ManagedExecutor managedExecutor;
    @Inject Instance<io.casehub.neocortex.inference.MultiModalEmbedder> multiModalEmbedderInstance;
    @Inject io.qdrant.client.QdrantClient qdrantClient;
    @Inject io.casehub.neocortex.rag.CursorStore cursorStore;
    @Inject io.casehub.neocortex.rag.runtime.RagConfig ragConfig;

    @Produces @Singleton
    SearchResource searchResource() {
        CorpusRef corpusRef = new CorpusRef("hortora", gardenConfig.id());
        SearchResource.SearchConfig config = new SearchResource.SearchConfig(
            searchConfig.scoreFloor(), searchConfig.gapThreshold(),
            searchConfig.minResults(), searchConfig.scoreBoostWeight()
        );
        SearchScoringConfig scoring = new SearchScoringConfig() {
            @Override public boolean temporalDecayEnabled() { return true; }
            @Override public boolean versionScoringEnabled() { return true; }
            @Override public double versionDecayFactor() { return 0.03; }
            @Override public double versionDecayFloor() { return 0.5; }
            @Override public double versionTopicWeightDefault() { return 0.3; }
        };
        var walker = new HttpFederationWalker(federationConfig, managedExecutor,
            url -> io.quarkus.rest.client.reactive.QuarkusRestClientBuilder.newBuilder()
                .baseUri(java.net.URI.create(url))
                .readTimeout(federationConfig.federationTimeoutSeconds(), java.util.concurrent.TimeUnit.SECONDS)
                .build(HortorRemoteClient.class));
        return new SearchResource(caseRetriever, corpusRef, federationConfig,
            walker::walk, config, scoring, searchProfileStore());
    }

    @Produces @Singleton
    ProvenanceStore provenanceStore() {
        return new ProvenanceStore(
            SqliteDataSourceFactory.create(provenanceConfig.sqlitePath(),
                provenanceConfig.sqlitePoolMaxSize(), provenanceConfig.sqliteBusyTimeoutMs())
        );
    }

    @Produces @Singleton
    GardenReindexService reindexService() {
        CorpusRef corpusRef = new CorpusRef("hortora", gardenConfig.id());
        var migration = new io.casehub.neocortex.rag.runtime.CorpusCollectionMigration(
            multiModalEmbedderInstance.get(), qdrantClient,
            embeddingIngestor, cursorStore,
            gardenConfig.id(), "hortora", ragConfig);
        return new GardenReindexService(embeddingIngestor, corpusRef,
            migration::resetCorpus);
    }

    @Produces @Singleton
    GardenMetadataExtractor metadataExtractor() {
        return new GardenMetadataExtractor();
    }

    @Produces @Singleton
    SearchProfileStore searchProfileStore() {
        String dbPath = System.getProperty("user.home") + "/.hortora/stats/search-profiles.db";
        return new SearchProfileStore(
            SqliteDataSourceFactory.create(dbPath, 3, 5000)
        );
    }

    @Produces @Singleton
    io.casehub.neocortex.corpus.management.impl.CorpusOutcomeService corpusOutcomeService(
            io.casehub.neocortex.memory.cbr.CbrRecordStore cbrStore) {
        return new io.casehub.neocortex.corpus.management.impl.CorpusOutcomeService(
            cbrStore, gardenConfig.id(), "garden", "garden-outcome");
    }
}
```

Note: A `HortorRemoteClient` JAX-RS interface stays in Hortora (thin Quarkus REST client proxy wrapping `RemoteCorpusClient`).

- [ ] **Step 3: Create HortorRemoteClient JAX-RS interface (Hortora-specific)**

This is the JAX-RS client interface that Quarkus REST client builder needs to create proxies. It implements `RemoteCorpusClient` and adds JAX-RS annotations:

```java
package io.hortora.garden.federation;

import io.casehub.neocortex.corpus.management.impl.RemoteCorpusClient;
import io.casehub.neocortex.corpus.management.impl.SearchResult;
import jakarta.ws.rs.GET;
import jakarta.ws.rs.HeaderParam;
import jakarta.ws.rs.Path;
import jakarta.ws.rs.Produces;
import jakarta.ws.rs.QueryParam;
import jakarta.ws.rs.core.MediaType;

import java.util.List;

@Produces(MediaType.APPLICATION_JSON)
interface HortorRemoteClient extends RemoteCorpusClient {

    @GET
    @Path("/search")
    @Override
    List<SearchResult> search(
            @QueryParam("q") String query,
            @QueryParam("domain") List<String> domains,
            @QueryParam("type") String type,
            @QueryParam("tags") String tags,
            @QueryParam("limit") int limit,
            @HeaderParam("X-Federation-Visited") String visited
    );
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/hortora/engine`.

- [ ] **Step 4: Update FederationConfigParser to use neocortex import**

The existing Hortora `FederationConfigParser.java` is deleted. The `CorpusManagementProducer` or a new CDI producer must produce `FederationConfig` using the neocortex `FederationConfigParser`:

Create a small CDI producer to replace the old FederationConfigParser's `@Produces`:

```java
package io.hortora.garden.federation;

import io.casehub.neocortex.corpus.management.impl.FederationConfig;
import io.casehub.neocortex.corpus.management.impl.FederationConfigParser;
import io.hortora.garden.config.GardenConfig;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;
import jakarta.inject.Inject;
import jakarta.inject.Singleton;

import java.io.IOException;

@ApplicationScoped
public class FederationConfigProducer {

    @Inject GardenConfig gardenConfig;

    @Produces @Singleton
    FederationConfig produce() {
        try {
            return FederationConfigParser.parse(
                    gardenConfig.schemaPath(), gardenConfig.id(), gardenConfig.idPrefix());
        } catch (IOException e) {
            throw new RuntimeException("Failed to read SCHEMA.md at " + gardenConfig.schemaPath(), e);
        }
    }
}
```

Use `ide_create_file` with project_path `/Users/mdproctor/claude/hortora/engine`.

- [ ] **Step 5: Safe-delete remaining files**

Delete source files with `ide_refactor_safe_delete`:
- `src/main/java/io/hortora/garden/federation/FederationConfigParser.java` (target_type=file)
- `src/main/java/io/hortora/garden/federation/ChainWalker.java` (target_type=file, force=true if usages remain — CorpusManagementProducer has been updated)
- `src/main/java/io/hortora/garden/federation/RemoteGardenClient.java` (target_type=file, force=true)
- `src/main/java/io/hortora/garden/outcome/GardenOutcomeService.java` (target_type=file, force=true)
- `src/main/java/io/hortora/garden/inference/CollectionMigration.java` (target_type=file, force=true)
- `src/main/java/io/hortora/garden/search/TemporalDecayScorer.java` (target_type=file)
- `src/main/java/io/hortora/garden/search/VersionScorer.java` (target_type=file)
- `src/test/java/io/hortora/garden/outcome/GardenOutcomeServiceTest.java` (target_type=file)
- `src/test/java/io/hortora/garden/inference/CollectionMigrationTest.java` (target_type=file)

- [ ] **Step 6: Update GardenMcpTools imports**

Replace any imports of deleted types in `GardenMcpTools.java`:
- `import io.hortora.garden.outcome.GardenOutcomeService` → `import io.casehub.neocortex.corpus.management.impl.CorpusOutcomeService`
- `import io.hortora.garden.inference.CollectionMigration` → `import io.casehub.neocortex.rag.runtime.CorpusCollectionMigration`

Update the field declarations and method bodies accordingly using `ide_edit_member`.

- [ ] **Step 7: Install neocortex to .m2 and verify both projects compile**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml clean install -DskipTests -q
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/hortora/engine/pom.xml clean compile -q
```

Expected: both compile clean with no errors.

- [ ] **Step 8: Run all tests in both projects**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/slots/221/neocortex/pom.xml test -pl corpus-management -q
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/hortora/engine/pom.xml test -q
```

Expected: all tests pass in both projects.

- [ ] **Step 9: Commit in both repos**

Neocortex (if any changes from Batch 3 adjustments):
```bash
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex add -A
git -C /Users/mdproctor/claude/casehub/slots/221/neocortex commit -m "fix(#775): adjust imports for Hortora cleanup

Refs #775"
```

Hortora:
```bash
git -C /Users/mdproctor/claude/hortora/engine add -A
git -C /Users/mdproctor/claude/hortora/engine commit -m "refactor: delete migrated services — now in neocortex corpus-management

ChainWalker, RemoteGardenClient, FederationConfigParser,
GardenOutcomeService, CollectionMigration, TemporalDecayScorer,
VersionScorer deleted. Replaced with neocortex imports.
HortorRemoteClient + FederationConfigProducer as thin CDI adapters.

Refs casehubio/neocortex#775"
```

---

## References

- `specs/issue-763-cognitive-knowledge-management/2026-11-02-cognitive-knowledge-management-design.md` — parent design spec
- `plans/2026-11-02-hortora-migration-remediation.md` — previous migration plan
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SearchResource.java:38-42` — FederationWalker interface
- `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/FederationConfig.java` — existing record
- `Hortora engine/src/main/java/io/hortora/garden/federation/ChainWalker.java` — source for HttpFederationWalker
- `Hortora engine/src/main/java/io/hortora/garden/federation/FederationConfigParser.java` — source for parser
- `Hortora engine/src/main/java/io/hortora/garden/outcome/GardenOutcomeService.java` — source for CorpusOutcomeService
- `Hortora engine/src/main/java/io/hortora/garden/inference/CollectionMigration.java` — source for CorpusCollectionMigration
- GitHub #763 — parent epic
- GitHub #775 — this issue
