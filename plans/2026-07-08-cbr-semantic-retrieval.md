# CBR Semantic Retrieval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #83 — feat: CBR Phase 3 — semantic case retrieval (bridge CBR + RAG)
**Issue group:** #83

**Goal:** Bridge CBR and RAG retrieval by adding hybrid two-pass retrieval
(feature filtering + semantic ranking), RRF/CC score fusion, optional
cross-encoder reranking, and explicit retrieval mode configuration on
`CbrQuery`.

**Architecture:** Mode-dispatched retrieval in `QdrantCbrCaseMemoryStore`
with `RetrievalMode` enum gating behavior. `ScoreFusion` utility in
`memory-api` provides generic RRF and CC fusion shared across all
backends. New `memory-cbr-crossencoder` module adds optional reranking
via `@Decorator` on `CbrCaseMemoryStore`, classpath-activated.

**Tech Stack:** Java 21, Quarkus 3.32.2, Qdrant Java client,
LangChain4j 1.14.1, ONNX Runtime (inference-tasks)

## Global Constraints

- All new types in `memory-api` must have zero external dependencies
- `ScoreFusion` is generic — no CBR or RAG type coupling
- RRF scores normalized to [0, 1] by dividing by `N/(k+1)`
- `minSimilarity` skipped for RRF fusion (rank-based, not similarity-based)
- CC: constant-score legs normalize to 1.0 (no division by zero)
- CC: absent candidates contribute 0.0 for that leg
- Cross-encoder scores sigmoid-normalized: `1/(1+exp(-raw))`
- Use IntelliJ MCP (`mcp__intellij-index__*`) for all code navigation
  and structural editing. Never use bash grep for source files.

---

### Task 1: API types — `RetrievalMode`, `CbrFusionStrategy`, `CbrQuery` additions

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/RetrievalMode.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFusionStrategy.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrQueryTest.java`

**Interfaces:**
- Produces: `RetrievalMode.FEATURE_ONLY`, `.SEMANTIC_ONLY`, `.HYBRID`
- Produces: `CbrFusionStrategy.RRF`, `.CC`
- Produces: `CbrQuery.retrievalMode()`, `CbrQuery.fusionStrategy()`
- Produces: `CbrQuery.withRetrievalMode(RetrievalMode)`, `CbrQuery.withFusionStrategy(CbrFusionStrategy)`

- [ ] **Step 1: Write failing tests for new CbrQuery fields**

Add to `CbrQueryTest.java`:

```java
@Test
void of_defaultsToHybridRetrievalMode() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5);
    assertThat(q.retrievalMode()).isEqualTo(RetrievalMode.HYBRID);
}

@Test
void of_defaultsToRrfFusionStrategy() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5);
    assertThat(q.fusionStrategy()).isEqualTo(CbrFusionStrategy.RRF);
}

@Test
void withRetrievalMode_setsMode() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    assertThat(q.retrievalMode()).isEqualTo(RetrievalMode.FEATURE_ONLY);
}

@Test
void withFusionStrategy_setsStrategy() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5)
        .withFusionStrategy(CbrFusionStrategy.CC);
    assertThat(q.fusionStrategy()).isEqualTo(CbrFusionStrategy.CC);
}

@Test
void withRetrievalMode_preservesOtherFields() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5)
        .withWeights(Map.of("a", 2.0)).withVectorWeight(0.3)
        .withProblem("test").withFusionStrategy(CbrFusionStrategy.CC)
        .withRetrievalMode(RetrievalMode.SEMANTIC_ONLY);
    assertThat(q.weights()).containsEntry("a", 2.0);
    assertThat(q.vectorWeight()).isEqualTo(0.3);
    assertThat(q.problem()).isEqualTo("test");
    assertThat(q.fusionStrategy()).isEqualTo(CbrFusionStrategy.CC);
}

@Test
void withFusionStrategy_preservesOtherFields() {
    var q = CbrQuery.of("t", CBR, "type", Map.of(), 5)
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY)
        .withFusionStrategy(CbrFusionStrategy.CC);
    assertThat(q.retrievalMode()).isEqualTo(RetrievalMode.FEATURE_ONLY);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrQueryTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `RetrievalMode`, `CbrFusionStrategy` do not exist

- [ ] **Step 3: Create the enums**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/RetrievalMode.java`:

```java
package io.casehub.neocortex.memory.cbr;

public enum RetrievalMode {
    FEATURE_ONLY,
    SEMANTIC_ONLY,
    HYBRID
}
```

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFusionStrategy.java`:

```java
package io.casehub.neocortex.memory.cbr;

public enum CbrFusionStrategy {
    RRF,
    CC
}
```

- [ ] **Step 4: Update CbrQuery record to include new fields**

Add `RetrievalMode retrievalMode` and `CbrFusionStrategy fusionStrategy`
fields to the record. Update the compact constructor to add:
```java
Objects.requireNonNull(retrievalMode, "retrievalMode required");
Objects.requireNonNull(fusionStrategy, "fusionStrategy required");
```

Update `CbrQuery.of()` to supply defaults:
```java
return new CbrQuery(tenantId, domain, caseType, features, Map.of(), topK,
    0.0, null, null, 0.5, RetrievalMode.HYBRID, CbrFusionStrategy.RRF);
```

Update ALL existing `with*()` methods to pass through the two new fields.

Add new builder methods:
```java
public CbrQuery withRetrievalMode(RetrievalMode retrievalMode) {
    return new CbrQuery(tenantId, domain, caseType, features, weights, topK,
        minSimilarity, notBefore, problem, vectorWeight, retrievalMode, fusionStrategy);
}

public CbrQuery withFusionStrategy(CbrFusionStrategy fusionStrategy) {
    return new CbrQuery(tenantId, domain, caseType, features, weights, topK,
        minSimilarity, notBefore, problem, vectorWeight, retrievalMode, fusionStrategy);
}
```

Fix existing test constructors that use the 10-arg canonical constructor
(e.g., `CbrQueryTest.minSimilarityOutOfRangeRejected`) to pass the two
new args. Search for `new CbrQuery(` across the codebase with
`ide_find_references` on the CbrQuery constructor.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrQueryTest`
Expected: all tests PASS

- [ ] **Step 6: Fix downstream compilation**

The record constructor change breaks downstream callers. Run:
`JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl memory-api,memory-testing,memory-cbr-inmem,memory-qdrant,memory-cbr-embedding`

Fix any `new CbrQuery(...)` calls in other modules to include the two new
args. Use `ide_find_references` on the `CbrQuery` constructor to find them all.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#83): add RetrievalMode, CbrFusionStrategy enums and CbrQuery fields"
```

---

### Task 2: `ScoredCbrCase` — add `reranked` field

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ScoredCbrCase.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/ScoredCbrCaseTest.java`

**Interfaces:**
- Produces: `ScoredCbrCase.reranked()` — returns `boolean`
- Produces: `ScoredCbrCase.withReranked()` — returns copy with `reranked=true`
- Produces: two-arg constructor backward-compat: `ScoredCbrCase(cbrCase, score)` delegates to 3-arg

- [ ] **Step 1: Write failing tests**

Add to `ScoredCbrCaseTest.java`:

```java
@Test
void constructor_twoArg_defaultsRerankedFalse() {
    var cbrCase = new TextualCbrCase("problem", "solution", null, null);
    assertThat(new ScoredCbrCase<>(cbrCase, 0.5).reranked()).isFalse();
}

@Test
void constructor_threeArg_setsReranked() {
    var cbrCase = new TextualCbrCase("problem", "solution", null, null);
    assertThat(new ScoredCbrCase<>(cbrCase, 0.5, true).reranked()).isTrue();
}

@Test
void withReranked_returnsNewInstanceWithRerankedTrue() {
    var cbrCase = new TextualCbrCase("problem", "solution", null, null);
    var original = new ScoredCbrCase<>(cbrCase, 0.8);
    var reranked = original.withReranked();
    assertThat(reranked.reranked()).isTrue();
    assertThat(reranked.score()).isEqualTo(0.8);
    assertThat(reranked.cbrCase()).isSameAs(cbrCase);
    assertThat(original.reranked()).isFalse();
}
```

- [ ] **Step 2: Run tests — expect compile failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=ScoredCbrCaseTest`

- [ ] **Step 3: Implement**

Update `ScoredCbrCase.java`:

```java
public record ScoredCbrCase<C extends CbrCase>(C cbrCase, double score, boolean reranked) {
    public ScoredCbrCase {
        Objects.requireNonNull(cbrCase, "cbrCase required");
        if (!(score >= -1.0 && score <= 1.0))
            throw new IllegalArgumentException("score must be in [-1,1], got: " + score);
    }

    public ScoredCbrCase(C cbrCase, double score) {
        this(cbrCase, score, false);
    }

    public ScoredCbrCase<C> withReranked() {
        return new ScoredCbrCase<>(cbrCase, score, true);
    }
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=ScoredCbrCaseTest`

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#83): add reranked field to ScoredCbrCase for double-reranking guard"
```

---

### Task 3: `ScoreFusion` utility — RRF and CC algorithms

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/ScoreFusion.java`
- Create: `memory-api/src/test/java/io/casehub/neocortex/memory/ScoreFusionTest.java`

**Interfaces:**
- Produces: `ScoreFusion.ScoredLeg<T>(List<T> items, ToDoubleFunction<T> scoreExtractor, double weight)`
- Produces: `ScoreFusion.FusedResult<T>(T item, double score)`
- Produces: `ScoreFusion.rrf(List<ScoredLeg<T>>, Function<T,String>, int, double)` → `List<FusedResult<T>>`
- Produces: `ScoreFusion.convexCombination(List<ScoredLeg<T>>, Function<T,String>, int)` → `List<FusedResult<T>>`

- [ ] **Step 1: Write comprehensive failing tests**

Create `memory-api/src/test/java/io/casehub/neocortex/memory/ScoreFusionTest.java`:

```java
package io.casehub.neocortex.memory;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.*;

class ScoreFusionTest {

    record Item(String id, double score) {}

    private static ScoreFusion.ScoredLeg<Item> leg(double weight, Item... items) {
        return new ScoreFusion.ScoredLeg<>(List.of(items), Item::score, weight);
    }

    private static Item item(String id, double score) {
        return new Item(id, score);
    }

    // --- RRF tests ---

    @Test
    void rrf_twoLegs_disjointCandidates_rankBasedScoring() {
        var legA = leg(1.0, item("a", 0.9), item("b", 0.8));
        var legB = leg(1.0, item("c", 0.7), item("d", 0.6));
        var results = ScoreFusion.rrf(List.of(legA, legB), Item::id, 4, 60);
        assertThat(results).hasSize(4);
        // a: 1/(60+1) from legA only = 0.01639
        // c: 1/(60+1) from legB only = 0.01639
        // b: 1/(60+2) from legA only = 0.01613
        // d: 1/(60+2) from legB only = 0.01613
        // After normalization by 2/(60+1): max possible = 2/61 = 0.03279
        // a normalized = 0.01639/0.03279 = 0.5
        assertThat(results.get(0).item().id()).isIn("a", "c");
        assertThat(results.get(0).score()).isCloseTo(0.5, within(0.01));
    }

    @Test
    void rrf_twoLegs_overlappingCandidates_scoresAccumulate() {
        var legA = leg(1.0, item("a", 0.9), item("b", 0.8));
        var legB = leg(1.0, item("a", 0.7), item("c", 0.6));
        var results = ScoreFusion.rrf(List.of(legA, legB), Item::id, 3, 60);
        // a appears in both legs: 1/(60+1) + 1/(60+1) = 2/61
        // normalized by 2/61 = 1.0
        assertThat(results.get(0).item().id()).isEqualTo("a");
        assertThat(results.get(0).score()).isCloseTo(1.0, within(0.01));
    }

    @Test
    void rrf_scoreNormalization_outputInZeroToOne() {
        var legA = leg(1.0, item("a", 0.9));
        var legB = leg(1.0, item("b", 0.8));
        var results = ScoreFusion.rrf(List.of(legA, legB), Item::id, 10, 60);
        for (var r : results) {
            assertThat(r.score()).isBetween(0.0, 1.0);
        }
    }

    @Test
    void rrf_sortsInternallyByScore_ranksDerivedCorrectly() {
        // Pass items NOT sorted by score — RRF should sort internally
        var leg = leg(1.0, item("a", 0.3), item("b", 0.9), item("c", 0.6));
        var results = ScoreFusion.rrf(List.of(leg), Item::id, 3, 60);
        // After internal sort: b(0.9)=rank1, c(0.6)=rank2, a(0.3)=rank3
        assertThat(results.get(0).item().id()).isEqualTo("b");
    }

    @Test
    void rrf_singleLeg_degeneratesToPassthrough() {
        var leg = leg(1.0, item("a", 0.9), item("b", 0.5));
        var results = ScoreFusion.rrf(List.of(leg), Item::id, 10, 60);
        assertThat(results).hasSize(2);
        assertThat(results.get(0).item().id()).isEqualTo("a");
    }

    @Test
    void rrf_emptyLegs_returnsEmpty() {
        var results = ScoreFusion.rrf(List.of(), Item::id, 10, 60);
        assertThat(results).isEmpty();
    }

    @Test
    void rrf_emptyLeg_handledGracefully() {
        var legA = leg(1.0, item("a", 0.9));
        var legB = new ScoreFusion.ScoredLeg<>(List.<Item>of(), Item::score, 1.0);
        var results = ScoreFusion.rrf(List.of(legA, legB), Item::id, 10, 60);
        assertThat(results).hasSize(1);
    }

    @Test
    void rrf_topK_trims() {
        var leg = leg(1.0, item("a", 0.9), item("b", 0.8), item("c", 0.7));
        var results = ScoreFusion.rrf(List.of(leg), Item::id, 2, 60);
        assertThat(results).hasSize(2);
    }

    // --- CC tests ---

    @Test
    void cc_twoLegs_minMaxNormalizationAndWeightedSum() {
        var legA = leg(0.6, item("a", 0.2), item("b", 0.8));
        var legB = leg(0.4, item("a", 0.9), item("b", 0.1));
        var results = ScoreFusion.convexCombination(
            List.of(legA, legB), Item::id, 10);
        // legA normalized: b=1.0, a=0.0. legB normalized: a=1.0, b=0.0
        // a: 0.6*0.0 + 0.4*1.0 = 0.4
        // b: 0.6*1.0 + 0.4*0.0 = 0.6
        assertThat(results.get(0).item().id()).isEqualTo("b");
        assertThat(results.get(0).score()).isCloseTo(0.6, within(0.01));
        assertThat(results.get(1).item().id()).isEqualTo("a");
        assertThat(results.get(1).score()).isCloseTo(0.4, within(0.01));
    }

    @Test
    void cc_disjointCandidates_absentContributesZero() {
        var legA = leg(0.5, item("a", 0.9));
        var legB = leg(0.5, item("b", 0.8));
        var results = ScoreFusion.convexCombination(
            List.of(legA, legB), Item::id, 10);
        // a: in legA only → 0.5*1.0 + 0.5*0.0 = 0.5
        // b: in legB only → 0.5*0.0 + 0.5*1.0 = 0.5
        assertThat(results).hasSize(2);
        assertThat(results.get(0).score()).isCloseTo(0.5, within(0.01));
    }

    @Test
    void cc_constantScoreLeg_normalizesToOne() {
        var leg = leg(1.0, item("a", 0.5), item("b", 0.5));
        var results = ScoreFusion.convexCombination(
            List.of(leg), Item::id, 10);
        // min=max=0.5, all normalize to 1.0
        assertThat(results.get(0).score()).isCloseTo(1.0, within(0.01));
        assertThat(results.get(1).score()).isCloseTo(1.0, within(0.01));
    }

    @Test
    void cc_weightRenormalization() {
        // Weights 3.0 and 1.0 → renormalized to 0.75 and 0.25
        var legA = leg(3.0, item("x", 1.0));
        var legB = leg(1.0, item("x", 1.0));
        var results = ScoreFusion.convexCombination(
            List.of(legA, legB), Item::id, 10);
        // x in both, both normalize to 1.0 → 0.75*1.0 + 0.25*1.0 = 1.0
        assertThat(results.get(0).score()).isCloseTo(1.0, within(0.01));
    }

    @Test
    void cc_singleLeg_degeneratesToPassthrough() {
        var leg = leg(1.0, item("a", 0.9), item("b", 0.5));
        var results = ScoreFusion.convexCombination(
            List.of(leg), Item::id, 10);
        assertThat(results).hasSize(2);
        assertThat(results.get(0).item().id()).isEqualTo("a");
    }

    @Test
    void cc_emptyLegs_returnsEmpty() {
        var results = ScoreFusion.convexCombination(
            List.of(), Item::id, 10);
        assertThat(results).isEmpty();
    }

    @Test
    void cc_topK_trims() {
        var leg = leg(1.0, item("a", 0.9), item("b", 0.8), item("c", 0.7));
        var results = ScoreFusion.convexCombination(
            List.of(leg), Item::id, 2);
        assertThat(results).hasSize(2);
    }
}
```

- [ ] **Step 2: Run tests — expect compile failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=ScoreFusionTest`

- [ ] **Step 3: Implement `ScoreFusion`**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/ScoreFusion.java`:

```java
package io.casehub.neocortex.memory;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;
import java.util.function.ToDoubleFunction;

public final class ScoreFusion {

    public record ScoredLeg<T>(List<T> items, ToDoubleFunction<T> scoreExtractor, double weight) {}

    public record FusedResult<T>(T item, double score) {}

    private ScoreFusion() {}

    public static <T> List<FusedResult<T>> rrf(
            List<ScoredLeg<T>> legs,
            Function<T, String> idExtractor,
            int topK,
            double k) {
        if (legs.isEmpty()) return List.of();

        Map<String, Double> scores = new LinkedHashMap<>();
        Map<String, T> items = new LinkedHashMap<>();

        for (ScoredLeg<T> leg : legs) {
            List<T> sorted = new ArrayList<>(leg.items());
            sorted.sort(Comparator.comparingDouble(leg.scoreExtractor()).reversed());
            for (int rank = 0; rank < sorted.size(); rank++) {
                T item = sorted.get(rank);
                String id = idExtractor.apply(item);
                scores.merge(id, 1.0 / (k + rank + 1), Double::sum);
                items.putIfAbsent(id, item);
            }
        }

        double maxScore = (double) legs.size() / (k + 1);

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

    public static <T> List<FusedResult<T>> convexCombination(
            List<ScoredLeg<T>> legs,
            Function<T, String> idExtractor,
            int topK) {
        if (legs.isEmpty()) return List.of();

        double totalWeight = legs.stream().mapToDouble(ScoredLeg::weight).sum();
        if (totalWeight <= 0) return List.of();

        Map<String, Double> composites = new LinkedHashMap<>();
        Map<String, T> items = new LinkedHashMap<>();

        for (ScoredLeg<T> leg : legs) {
            double normalizedWeight = leg.weight() / totalWeight;
            double min = leg.items().stream()
                .mapToDouble(leg.scoreExtractor()).min().orElse(0);
            double max = leg.items().stream()
                .mapToDouble(leg.scoreExtractor()).max().orElse(0);
            double range = max - min;

            for (T item : leg.items()) {
                String id = idExtractor.apply(item);
                double raw = leg.scoreExtractor().applyAsDouble(item);
                double norm = range > 0 ? (raw - min) / range : 1.0;
                composites.merge(id, normalizedWeight * norm, Double::sum);
                items.putIfAbsent(id, item);
            }
        }

        List<Map.Entry<String, Double>> sorted = new ArrayList<>(composites.entrySet());
        sorted.sort(Map.Entry.<String, Double>comparingByValue().reversed());

        List<FusedResult<T>> result = new ArrayList<>(Math.min(sorted.size(), topK));
        for (int i = 0; i < Math.min(sorted.size(), topK); i++) {
            Map.Entry<String, Double> entry = sorted.get(i);
            result.add(new FusedResult<>(items.get(entry.getKey()), entry.getValue()));
        }
        return List.copyOf(result);
    }
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=ScoreFusionTest`

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#83): add ScoreFusion utility — generic RRF and CC algorithms"
```

---

### Task 4: Remove `CbrSimilarityScorer.compositeScore()`

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `ScoreFusion` from Task 3 (replaces `compositeScore`)

- [ ] **Step 1: Find all call sites**

Use `ide_find_references` on `CbrSimilarityScorer.compositeScore` to find
all callers. Expected: only `QdrantCbrCaseMemoryStore.retrieveSimilar()`.

- [ ] **Step 2: Remove `compositeScore()` from `CbrSimilarityScorer`**

Delete the method (lines 94-97). Use `ide_refactor_safe_delete` or manual
removal — this is a single static method with one caller that we'll fix
in the same task.

- [ ] **Step 3: Update `QdrantCbrCaseMemoryStore.retrieveSimilar()`**

Replace the `compositeScore()` call at line 213-214 with direct
computation for now (the full mode dispatch comes in Task 6):

```java
// Temporary — replaced by mode dispatch in Task 6
double finalScore;
if (denseSearch) {
    finalScore = query.vectorWeight() * rc.vectorScore()
        + (1.0 - query.vectorWeight()) * featureScore;
} else {
    finalScore = featureScore;
}
```

- [ ] **Step 4: Run existing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory-qdrant`
Expected: all existing tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/ memory-qdrant/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor(#83): remove CbrSimilarityScorer.compositeScore() — superseded by ScoreFusion"
```

---

### Task 5: `InMemoryCbrCaseMemoryStore` — mode dispatch + contract tests

**Files:**
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`

**Interfaces:**
- Consumes: `RetrievalMode` from Task 1
- Produces: contract tests that all `CbrCaseMemoryStore` impls must pass

- [ ] **Step 1: Add contract tests**

Add to `CbrCaseMemoryStoreContractTest.java`:

```java
@Test
void retrieveSimilar_featureOnly_ignoresProblem() {
    registerDefaultSchema();
    store().store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
        "problem text", null, null, null),
        "starcraft-game", ENTITY, CBR, TENANT, null);
    var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
            Map.of("race", "Zerg"), 5)
        .withProblem("some problem")
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).isNotEmpty();
}

@Test
void retrieveSimilar_defaultRetrievalMode_isHybrid() {
    var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
        Map.of("race", "Zerg"), 5);
    assertThat(query.retrievalMode()).isEqualTo(RetrievalMode.HYBRID);
}

@Test
void retrieveSimilar_defaultFusionStrategy_isRrf() {
    var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
        Map.of("race", "Zerg"), 5);
    assertThat(query.fusionStrategy()).isEqualTo(CbrFusionStrategy.RRF);
}

@Test
void retrieveSimilar_hybrid_withoutEmbeddingModel_degradesToFeatureOnly() {
    registerDefaultSchema();
    store().store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
        "problem text", null, null, null),
        "starcraft-game", ENTITY, CBR, TENANT, null);
    var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
            Map.of("race", "Zerg"), 5)
        .withProblem("problem")
        .withRetrievalMode(RetrievalMode.HYBRID);
    // In-memory store has no embedding model, should degrade
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).isNotEmpty();
}

@Test
void retrieveSimilar_semanticOnly_withoutEmbeddingModel_returnsEmpty() {
    registerDefaultSchema();
    store().store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
        "problem text", null, null, null),
        "starcraft-game", ENTITY, CBR, TENANT, null);
    var query = CbrQuery.of(TENANT, CBR, "starcraft-game",
            Map.of("race", "Zerg"), 5)
        .withProblem("problem")
        .withRetrievalMode(RetrievalMode.SEMANTIC_ONLY);
    var results = store().retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).isEmpty();
}
```

- [ ] **Step 2: Run tests — expect failures**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem`
Expected: `semanticOnly_withoutEmbeddingModel_returnsEmpty` fails (InMemory
currently returns feature-scored results regardless of mode)

- [ ] **Step 3: Implement mode dispatch in InMemoryCbrCaseMemoryStore**

Update `retrieveSimilar()` to add mode dispatch at the top:

```java
@Override
@SuppressWarnings("unchecked")
public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery query, Class<C> caseClass) {
    RetrievalMode mode = query.retrievalMode();
    if (mode == RetrievalMode.SEMANTIC_ONLY) {
        return List.of();
    }
    if (mode == RetrievalMode.HYBRID && query.problem() != null) {
        java.util.logging.Logger.getLogger(getClass().getName())
            .warning("HYBRID mode degraded to FEATURE_ONLY — no EmbeddingModel available");
    }
    // ... existing feature scoring logic unchanged ...
}
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem`

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-cbr-inmem/ memory-testing/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#83): InMemoryCbrCaseMemoryStore mode dispatch + contract tests"
```

---

### Task 6: `QdrantCbrCaseMemoryStore` — mode-dispatched hybrid retrieval

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/test/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `RetrievalMode`, `CbrFusionStrategy` from Task 1
- Consumes: `ScoreFusion.rrf()`, `ScoreFusion.convexCombination()` from Task 3
- Consumes: contract tests from Task 5

This is the largest task. The current `retrieveSimilar()` does single-path
retrieval. Refactor to three modes.

- [ ] **Step 1: Write integration tests for mode dispatch**

Add to `QdrantCbrCaseMemoryStoreTest.java`:

```java
@Test
void retrieveSimilar_featureOnly_ignoresProblem() {
    // Store cases with known features
    registerSchemaAndStoreCases();
    var query = CbrQuery.of(TENANT, CBR, CASE_TYPE, Map.of("race", "Zerg"), 5)
        .withProblem("some problem text")
        .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
    var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).isNotEmpty();
    // Results are feature-scored only — no vector blending
}

@Test
void retrieveSimilar_semanticOnly_ignoresFeatures() {
    registerSchemaAndStoreCases();
    var query = CbrQuery.of(TENANT, CBR, CASE_TYPE, Map.of("race", "Zerg"), 5)
        .withProblem("matching problem text")
        .withRetrievalMode(RetrievalMode.SEMANTIC_ONLY);
    var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
    // Results ranked by vector score only
    assertThat(results).isNotEmpty();
}

@Test
void retrieveSimilar_hybrid_fusesFeatureAndSemanticLegs() {
    registerSchemaAndStoreCases();
    var query = CbrQuery.of(TENANT, CBR, CASE_TYPE, Map.of("race", "Zerg"), 5)
        .withProblem("matching problem text")
        .withRetrievalMode(RetrievalMode.HYBRID);
    var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).isNotEmpty();
}

@Test
void retrieveSimilar_hybrid_rrf_scoresInZeroToOne() {
    registerSchemaAndStoreCases();
    var query = CbrQuery.of(TENANT, CBR, CASE_TYPE, Map.of("race", "Zerg"), 5)
        .withProblem("matching problem text")
        .withRetrievalMode(RetrievalMode.HYBRID)
        .withFusionStrategy(CbrFusionStrategy.RRF);
    var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
    for (var r : results) {
        assertThat(r.score()).isBetween(0.0, 1.0);
    }
}

@Test
void retrieveSimilar_hybrid_rrf_skipsMinSimilarity() {
    registerSchemaAndStoreCases();
    var query = CbrQuery.of(TENANT, CBR, CASE_TYPE, Map.of("race", "Zerg"), 5)
        .withProblem("matching problem text")
        .withMinSimilarity(0.99)
        .withRetrievalMode(RetrievalMode.HYBRID)
        .withFusionStrategy(CbrFusionStrategy.RRF);
    // With RRF, minSimilarity is skipped — results should appear
    var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).isNotEmpty();
}

@Test
void retrieveSimilar_hybrid_withoutProblem_degradesToFeatureOnly() {
    registerSchemaAndStoreCases();
    var query = CbrQuery.of(TENANT, CBR, CASE_TYPE, Map.of("race", "Zerg"), 5)
        .withRetrievalMode(RetrievalMode.HYBRID);
    // problem is null → degrade to FEATURE_ONLY
    var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
    assertThat(results).isNotEmpty();
}

@Test
void retrieveSimilar_cc_respectsMinSimilarity() {
    registerSchemaAndStoreCases();
    var query = CbrQuery.of(TENANT, CBR, CASE_TYPE, Map.of("race", "Zerg"), 5)
        .withProblem("matching problem text")
        .withMinSimilarity(0.99)
        .withRetrievalMode(RetrievalMode.HYBRID)
        .withFusionStrategy(CbrFusionStrategy.CC);
    var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
    for (var r : results) {
        assertThat(r.score()).isGreaterThanOrEqualTo(0.99);
    }
}
```

The exact test helper methods (`registerSchemaAndStoreCases`) depend on what's
already in `QdrantCbrCaseMemoryStoreTest`. Adapt to use existing helpers.

- [ ] **Step 2: Run tests — expect failures**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -Dtest=QdrantCbrCaseMemoryStoreTest`

- [ ] **Step 3: Refactor `retrieveSimilar()` with mode dispatch**

Replace the current `retrieveSimilar()` body with mode-dispatched logic.
The key structural change:

```java
public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery query, Class<C> caseClass) {
    // ... existing schema validation and collection check ...

    Filter filter = CbrQueryTranslator.toIdentityFilter(query);
    RetrievalMode effectiveMode = resolveEffectiveMode(query);

    return switch (effectiveMode) {
        case FEATURE_ONLY -> retrieveFeatureOnly(query, caseClass, filter);
        case SEMANTIC_ONLY -> retrieveSemanticOnly(query, caseClass, filter);
        case HYBRID -> retrieveHybrid(query, caseClass, filter);
    };
}

private RetrievalMode resolveEffectiveMode(CbrQuery query) {
    if (query.retrievalMode() == RetrievalMode.SEMANTIC_ONLY) {
        if (embeddingModel == null || query.problem() == null) {
            return null; // signals return empty
        }
        return RetrievalMode.SEMANTIC_ONLY;
    }
    if (query.retrievalMode() == RetrievalMode.HYBRID) {
        if (embeddingModel == null || query.problem() == null) {
            LOG.warning("HYBRID degraded to FEATURE_ONLY — "
                + (embeddingModel == null ? "no EmbeddingModel" : "problem is null"));
            return RetrievalMode.FEATURE_ONLY;
        }
        return RetrievalMode.HYBRID;
    }
    return RetrievalMode.FEATURE_ONLY;
}
```

Extract existing filter-only path into `retrieveFeatureOnly()`.
Extract existing dense path into `retrieveSemanticOnly()`.
Build new `retrieveHybrid()`:

```java
private <C extends CbrCase> List<ScoredCbrCase<C>> retrieveHybrid(
        CbrQuery query, Class<C> caseClass, Filter filter) {
    String collection = collectionManager.collectionName(query.caseType());
    CbrFeatureSchema schema = schemas.get(query.caseType());

    // Leg 1: dense vector search
    List<ScoredPoint> densePoints = executeDenseSearch(collection, filter, query);

    // Leg 2: filter-only scroll
    List<ScoredPoint> filterPoints = executeFilterQuery(collection, filter,
        Math.max(query.topK(), config.overFetchLimit()));

    // Merge candidate pools by point ID — reconstruct once
    Map<String, ReconstructedCandidate<C>> candidateMap = new LinkedHashMap<>();
    mergePoints(densePoints, candidateMap, caseClass, true);
    mergePoints(filterPoints, candidateMap, caseClass, false);

    List<ReconstructedCandidate<C>> allCandidates = new ArrayList<>(candidateMap.values());

    // Batch precompute embeddings for semantic text fields
    EmbeddingTextSimilarity textSim = (schema != null && embeddingModel != null)
        ? new EmbeddingTextSimilarity(embeddingModel) : null;
    Map<String, LocalSimilarityFunction> overrides = schema != null
        ? buildTextOverrides(schema, textSim) : Map.of();
    if (textSim != null && !overrides.isEmpty()) {
        List<String> texts = collectSemanticTextValues(query, allCandidates, overrides.keySet());
        textSim.precompute(texts);
    }

    // Score feature leg — all candidates
    List<ScoredCbrCase<C>> featureLeg = new ArrayList<>();
    for (var rc : allCandidates) {
        double score = CbrSimilarityScorer.score(
            query.features(), rc.cbrCase().features(), query.weights(), schema, overrides);
        featureLeg.add(new ScoredCbrCase<>(rc.cbrCase(), score));
    }

    // Semantic leg — only candidates from dense search, use vector score
    List<ScoredCbrCase<C>> semanticLeg = new ArrayList<>();
    for (var rc : allCandidates) {
        if (rc.vectorScore() > 0) {
            semanticLeg.add(new ScoredCbrCase<>(rc.cbrCase(), rc.vectorScore()));
        }
    }

    // Fuse
    var featureScoredLeg = new ScoreFusion.ScoredLeg<>(
        featureLeg, ScoredCbrCase::score, 1.0 - query.vectorWeight());
    var semanticScoredLeg = new ScoreFusion.ScoredLeg<>(
        semanticLeg, ScoredCbrCase::score, query.vectorWeight());

    List<ScoreFusion.FusedResult<ScoredCbrCase<C>>> fused;
    if (query.fusionStrategy() == CbrFusionStrategy.RRF) {
        fused = ScoreFusion.rrf(List.of(featureScoredLeg, semanticScoredLeg),
            r -> r.cbrCase().caseId() != null ? r.cbrCase().caseId() : String.valueOf(System.identityHashCode(r.cbrCase())),
            query.topK(), 60);
    } else {
        fused = ScoreFusion.convexCombination(List.of(featureScoredLeg, semanticScoredLeg),
            r -> r.cbrCase().caseId() != null ? r.cbrCase().caseId() : String.valueOf(System.identityHashCode(r.cbrCase())),
            query.topK());
    }

    // Apply minSimilarity only for CC
    List<ScoredCbrCase<C>> results = new ArrayList<>(fused.size());
    for (var f : fused) {
        if (query.fusionStrategy() == CbrFusionStrategy.RRF || f.score() >= query.minSimilarity()) {
            results.add(new ScoredCbrCase<>(f.item().cbrCase(), f.score()));
        }
    }
    return Collections.unmodifiableList(results);
}
```

The exact ID extraction function depends on what field uniquely identifies
a case. Use `ide_find_references` on `CbrCase` to check if there's a
unique `id()` or similar method. Adapt accordingly.

- [ ] **Step 4: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant`
Expected: all tests PASS (existing + new)

- [ ] **Step 5: Run contract tests from in-memory module too**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem`

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-qdrant/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#83): mode-dispatched hybrid retrieval with RRF/CC fusion in QdrantCbrCaseMemoryStore"
```

---

### Task 7: New module — `memory-cbr-crossencoder`

**Files:**
- Create: `memory-cbr-crossencoder/pom.xml`
- Create: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/CbrRerankingConfig.java`
- Create: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/RerankingCbrCaseMemoryStore.java`
- Create: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/ReactiveRerankingCbrCaseMemoryStore.java`
- Create: `memory-cbr-crossencoder/src/test/java/io/casehub/neocortex/memory/cbr/crossencoder/RerankingCbrCaseMemoryStoreTest.java`
- Modify: `pom.xml` (parent) — add `<module>`, `<dependency>` in dependencyManagement

**Interfaces:**
- Consumes: `CbrCaseMemoryStore.retrieveSimilar()` (decorated)
- Consumes: `CrossEncoderReranker` from `inference-tasks`
- Consumes: `ScoredCbrCase.reranked()`, `.withReranked()` from Task 2
- Consumes: `RetrievalMode` from Task 1

- [ ] **Step 1: Create module pom.xml**

Create `memory-cbr-crossencoder/pom.xml` modeled on `rag-crossencoder/pom.xml`:

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-neocortex-memory-cbr-crossencoder</artifactId>
  <name>CaseHub Neocortex - Memory CBR Cross-Encoder</name>
  <description>Cross-encoder reranking for CBR retrieval. Classpath-activated.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-inference-tasks</artifactId>
    </dependency>
    <dependency>
      <groupId>jakarta.enterprise</groupId>
      <artifactId>jakarta.enterprise.cdi-api</artifactId>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>io.smallrye.config</groupId>
      <artifactId>smallrye-config-core</artifactId>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
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
      <artifactId>casehub-neocortex-inference-inmem</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-cbr-inmem</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-testing</artifactId>
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

- [ ] **Step 2: Add module to parent pom.xml**

Add `<module>memory-cbr-crossencoder</module>` after `memory-cbr-embedding`
in the `<modules>` section.

Add dependency management entry:
```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-memory-cbr-crossencoder</artifactId>
  <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Create config interface**

Create `CbrRerankingConfig.java`:

```java
package io.casehub.neocortex.memory.cbr.crossencoder;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.cbr.reranking")
public interface CbrRerankingConfig {
    @WithDefault("false")
    boolean enabled();

    @WithDefault("30")
    int rerankPoolSize();
}
```

- [ ] **Step 4: Write failing tests**

Create `RerankingCbrCaseMemoryStoreTest.java`:

```java
package io.casehub.neocortex.memory.cbr.crossencoder;

import io.casehub.neocortex.memory.cbr.*;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrCaseMemoryStore;
import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.inference.tasks.RankedResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class RerankingCbrCaseMemoryStoreTest {

    private static final MemoryDomain CBR = new MemoryDomain("cbr");
    private InMemoryCbrCaseMemoryStore inner;
    private RerankingCbrCaseMemoryStore reranker;
    private StubCrossEncoderReranker crossEncoder;

    @BeforeEach
    void setUp() {
        inner = new InMemoryCbrCaseMemoryStore();
        crossEncoder = new StubCrossEncoderReranker();
        var config = new CbrRerankingConfig() {
            public boolean enabled() { return true; }
            public int rerankPoolSize() { return 30; }
        };
        reranker = new RerankingCbrCaseMemoryStore(inner, crossEncoder, config);
        inner.registerSchema(CbrFeatureSchema.of("game",
            FeatureField.categorical("race")));
    }

    @Test
    void reranking_reordersResultsByCrossEncoderScore() {
        inner.store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
            "low relevance problem", null, null, null),
            "game", "e1", CBR, "t1", null);
        inner.store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
            "high relevance problem", null, null, null),
            "game", "e2", CBR, "t1", null);

        // Stub returns second case as higher ranked
        crossEncoder.setScores(new float[]{-1.0f, 2.0f});

        var query = CbrQuery.of("t1", CBR, "game", Map.of("race", "Zerg"), 5)
            .withProblem("query text")
            .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
        // FEATURE_ONLY → reranking skipped
        var results = reranker.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(results).allMatch(r -> !r.reranked());
    }

    @Test
    void featureOnly_skipsReranking() {
        inner.store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
            "problem", null, null, null),
            "game", "e1", CBR, "t1", null);
        var query = CbrQuery.of("t1", CBR, "game", Map.of("race", "Zerg"), 5)
            .withRetrievalMode(RetrievalMode.FEATURE_ONLY);
        var results = reranker.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(crossEncoder.callCount()).isZero();
        assertThat(results).isNotEmpty();
    }

    @Test
    void nullProblem_skipsReranking() {
        inner.store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
            null, null, null, null),
            "game", "e1", CBR, "t1", null);
        var query = CbrQuery.of("t1", CBR, "game", Map.of("race", "Zerg"), 5);
        var results = reranker.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(crossEncoder.callCount()).isZero();
    }

    @Test
    void alreadyReranked_skipsReranking() {
        inner.store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
            "problem", null, null, null),
            "game", "e1", CBR, "t1", null);
        // First pass — should rerank
        crossEncoder.setScores(new float[]{0.5f});
        var query = CbrQuery.of("t1", CBR, "game", Map.of("race", "Zerg"), 5)
            .withProblem("query");
        var firstPass = reranker.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(firstPass).allMatch(ScoredCbrCase::reranked);
    }

    @Test
    void sigmoidNormalization_scoresInZeroToOne() {
        inner.store(FeatureVectorCbrCase.of(Map.of("race", "Zerg"),
            "problem", null, null, null),
            "game", "e1", CBR, "t1", null);
        // Raw logit of 5.0 → sigmoid ≈ 0.993
        crossEncoder.setScores(new float[]{5.0f});
        var query = CbrQuery.of("t1", CBR, "game", Map.of("race", "Zerg"), 5)
            .withProblem("query");
        var results = reranker.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(results).isNotEmpty();
        for (var r : results) {
            assertThat(r.score()).isBetween(0.0, 1.0);
        }
    }

    static class StubCrossEncoderReranker extends CrossEncoderReranker {
        private float[] scores = new float[0];
        private int calls = 0;

        StubCrossEncoderReranker() {
            super(null); // null model — we override methods
        }

        void setScores(float[] scores) { this.scores = scores; }
        int callCount() { return calls; }

        @Override
        public List<RankedResult> rerank(String query, List<String> candidates) {
            calls++;
            List<RankedResult> results = new java.util.ArrayList<>();
            for (int i = 0; i < candidates.size(); i++) {
                float s = i < scores.length ? scores[i] : 0f;
                results.add(new RankedResult(candidates.get(i), s, i));
            }
            results.sort((a, b) -> Float.compare(b.score(), a.score()));
            return results;
        }
    }
}
```

Note: The exact stub approach depends on `CrossEncoderReranker`'s
constructor requirements. If it doesn't allow null model, use a mock
framework or create a minimal stub `InferenceModel`. Check with
`ide_file_structure` on `CrossEncoderReranker.java`.

- [ ] **Step 5: Create `RerankingCbrCaseMemoryStore`**

```java
package io.casehub.neocortex.memory.cbr.crossencoder;

import io.casehub.neocortex.inference.tasks.CrossEncoderReranker;
import io.casehub.neocortex.inference.tasks.RankedResult;
import io.casehub.neocortex.memory.cbr.*;
import io.quarkus.arc.Unremovable;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@Decorator
@Priority(75)
@Unremovable
@IfBuildProperty(name = "casehub.cbr.reranking.enabled", stringValue = "true")
public class RerankingCbrCaseMemoryStore implements CbrCaseMemoryStore {

    private final CbrCaseMemoryStore delegate;
    private final CrossEncoderReranker reranker;
    private final CbrRerankingConfig config;

    @Inject
    RerankingCbrCaseMemoryStore(@Delegate @Any CbrCaseMemoryStore delegate,
                                 Instance<CrossEncoderReranker> rerankerInstance,
                                 CbrRerankingConfig config) {
        this.delegate = delegate;
        this.reranker = rerankerInstance.isResolvable() ? rerankerInstance.get() : null;
        this.config = config;
    }

    // Test constructor
    RerankingCbrCaseMemoryStore(CbrCaseMemoryStore delegate,
                                 CrossEncoderReranker reranker,
                                 CbrRerankingConfig config) {
        this.delegate = delegate;
        this.reranker = reranker;
        this.config = config;
    }

    @Override
    public void registerSchema(CbrFeatureSchema schema) {
        delegate.registerSchema(schema);
    }

    @Override
    public String store(CbrCase cbrCase, String caseType, String entityId,
                        io.casehub.neocortex.memory.MemoryDomain domain,
                        String tenantId, String caseId) {
        return delegate.store(cbrCase, caseType, entityId, domain, tenantId, caseId);
    }

    @Override
    public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(
            CbrQuery query, Class<C> caseClass) {
        if (shouldSkip(query)) {
            return delegate.retrieveSimilar(query, caseClass);
        }

        int fetchSize = Math.max(query.topK(), config.rerankPoolSize());
        CbrQuery overfetchQuery = new CbrQuery(
            query.tenantId(), query.domain(), query.caseType(),
            query.features(), query.weights(), fetchSize,
            query.minSimilarity(), query.notBefore(), query.problem(),
            query.vectorWeight(), query.retrievalMode(), query.fusionStrategy());

        List<ScoredCbrCase<C>> candidates = delegate.retrieveSimilar(overfetchQuery, caseClass);
        if (candidates.isEmpty()) return candidates;

        if (candidates.stream().allMatch(ScoredCbrCase::reranked)) {
            return candidates.subList(0, Math.min(candidates.size(), query.topK()));
        }

        List<String> problemTexts = candidates.stream()
            .map(c -> c.cbrCase().problem() != null ? c.cbrCase().problem() : "")
            .toList();

        List<RankedResult> ranked = reranker.rerank(query.problem(), problemTexts);

        List<ScoredCbrCase<C>> results = new ArrayList<>(
            Math.min(ranked.size(), query.topK()));
        for (int i = 0; i < Math.min(ranked.size(), query.topK()); i++) {
            RankedResult r = ranked.get(i);
            ScoredCbrCase<C> original = candidates.get(r.originalIndex());
            double sigmoidScore = 1.0 / (1.0 + Math.exp(-r.score()));
            results.add(new ScoredCbrCase<C>(original.cbrCase(), sigmoidScore).withReranked());
        }

        return Collections.unmodifiableList(results);
    }

    @Override
    public Integer erase(io.casehub.neocortex.memory.EraseRequest request) {
        return delegate.erase(request);
    }

    @Override
    public Integer eraseEntity(String entityId, String tenantId) {
        return delegate.eraseEntity(entityId, tenantId);
    }

    private boolean shouldSkip(CbrQuery query) {
        if (reranker == null) return true;
        if (query.retrievalMode() == RetrievalMode.FEATURE_ONLY) return true;
        if (query.problem() == null) return true;
        return false;
    }
}
```

- [ ] **Step 6: Create reactive variant**

Create `ReactiveRerankingCbrCaseMemoryStore.java` following the
`ReactiveRerankingCaseRetriever` pattern exactly — `@Decorator @Priority(75)`
on `ReactiveCbrCaseMemoryStore`, same guards, `runSubscriptionOn(workerPool)`
for the blocking rerank call.

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-crossencoder`

- [ ] **Step 8: Build full project**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Then: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test`

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-cbr-crossencoder/ pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#83): add memory-cbr-crossencoder — optional cross-encoder reranking for CBR"
```

---

### Task 8: CLAUDE.md and spec updates

**Files:**
- Modify: `CLAUDE.md` — add `memory-cbr-crossencoder` to module list, package map, Maven coords
- Modify: `docs/specs/2026-07-08-cbr-semantic-retrieval-design.md` — mark as implemented

- [ ] **Step 1: Update CLAUDE.md**

Add the new module to:
1. Module Structure section (after `memory-cbr-embedding/`)
2. Maven Coordinates table
3. Root Java package table

- [ ] **Step 2: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md docs/specs/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "docs(#83): update CLAUDE.md with memory-cbr-crossencoder module"
```
