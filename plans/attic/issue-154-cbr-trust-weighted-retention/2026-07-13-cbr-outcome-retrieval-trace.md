# CBR Outcome-Weighted Retrieval & Retrieval Traceability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #84 — feat: CBR Phase 4 — outcome learning + retrieval traceability
**Issue group:** #84

**Goal:** Activate outcome-weighted retrieval (confidence modulates similarity scores), add retrieval traceability (tracker SPI + SQLite + CDI event), and ship an ExplanationRenderer SPI with generic default.

**Architecture:** Three independent capabilities — outcome weighting as a `@Decorator @Priority(65)` on `CbrCaseMemoryStore`, retrieval tracking as a `@Decorator @Priority(50)` in a new `memory-cbr-tracking` module with SQLite persistence, and `ExplanationRenderer` SPI with generic `@DefaultBean`. Prerequisite: add `caseId` to `ScoredCbrCase` so traces can reference specific cases.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI decorators, SQLite (HikariCP + Flyway), Mutiny

## Global Constraints

- Java 21 source on Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build: `mvn clean install` (not `./mvnw`)
- IntelliJ MCP mandatory for all source file operations
- Pre-release: breaking API changes are fine
- All SPIs require blocking + reactive parity
- CDI decorator ordering: lower `@Priority` = outermost (called first)
- `@IfBuildProperty` for feature activation
- Jandex index plugin required in all new modules

---

### Task 1: Add `caseId` to `ScoredCbrCase`

Prerequisite API change. `ScoredCbrCase` currently has no case identifier — callers can't reference which stored case was matched. All store implementations already have the caseId internally; they just don't surface it.

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ScoredCbrCase.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/ScoredCbrCaseTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrCaseTest.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/RerankingCbrCaseMemoryStore.java`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/ReactiveRerankingCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Test: all existing tests must still pass after the change

**Interfaces:**
- Produces: `ScoredCbrCase<C>(C cbrCase, String caseId, double score, boolean reranked, Map<String, Double> featureSimilarities)` — all subsequent tasks depend on `caseId` being available.

- [ ] **Step 1: Update ScoredCbrCase record declaration**

Use `ide_edit_member` on `ScoredCbrCase` to add `String caseId` as the second record component. Update the compact constructor to accept null caseId (stores may not always have one during reconstruction). Update convenience constructors and `withReranked()`:

```java
public record ScoredCbrCase<C extends CbrCase>(C cbrCase, String caseId, double score, boolean reranked,
                                                Map<String, Double> featureSimilarities) {
    public ScoredCbrCase {
        Objects.requireNonNull(cbrCase, "cbrCase required");
        if (!(score >= -1.0 && score <= 1.0))
            throw new IllegalArgumentException("score must be in [-1,1], got: " + score);
        featureSimilarities = featureSimilarities != null ? Map.copyOf(featureSimilarities) : Map.of();
    }

    public ScoredCbrCase(C cbrCase, String caseId, double score) {
        this(cbrCase, caseId, score, false, Map.of());
    }

    public ScoredCbrCase(C cbrCase, double score) {
        this(cbrCase, null, score, false, Map.of());
    }

    public ScoredCbrCase(C cbrCase, double score, boolean reranked) {
        this(cbrCase, null, score, reranked, Map.of());
    }

    public ScoredCbrCase<C> withReranked() {
        return new ScoredCbrCase<>(cbrCase, caseId, score, true, featureSimilarities);
    }
}
```

The 2-arg `(cbrCase, score)` and 3-arg `(cbrCase, score, reranked)` constructors pass null caseId for backward compatibility with tests and callers that don't have a caseId context.

- [ ] **Step 2: Fix ScoredCbrCaseTest**

Update tests to use the new constructor signatures. Add a test for the new `caseId` field:

```java
@Test void caseId_present() {
    var scored = new ScoredCbrCase<>(cbrCase, "case-1", 0.9);
    assertThat(scored.caseId()).isEqualTo("case-1");
}

@Test void caseId_null_allowed() {
    var scored = new ScoredCbrCase<>(cbrCase, 0.9);
    assertThat(scored.caseId()).isNull();
}

@Test void withReranked_preservesCaseId() {
    var original = new ScoredCbrCase<>(cbrCase, "case-1", 0.8);
    var reranked = original.withReranked();
    assertThat(reranked.caseId()).isEqualTo("case-1");
}
```

- [ ] **Step 3: Fix CbrCaseTest ScoredCbrCase references**

Update the `ScoredCbrCase` constructor calls in `CbrCaseTest` that test validation (score bounds, NaN, infinity). These use the 2-arg constructor — they should continue to work with the backward-compatible overload.

- [ ] **Step 4: Update InMemoryCbrCaseMemoryStore**

In `retrieveSimilar`, pass `stored.caseId()` to the `ScoredCbrCase` constructor:

```java
candidates.add(new ScoredCbrCase<>((C) stored.cbrCase(), stored.caseId(),
        breakdown.score(), false, breakdown.featureSimilarities()));
```

- [ ] **Step 5: Update QdrantCbrCaseMemoryStore**

Three retrieval methods need updating. The `caseId` is stored in the Qdrant payload at key `"case_id"` (verify via the `store()` method's point builder). In `ReconstructedCandidate`, add `caseId`:

```java
private record ReconstructedCandidate<C>(String pointId, C cbrCase, float vectorScore, String caseId) {}
```

Update `reconstructAll` to extract `caseId` from payload: `extractString(payload, "case_id")`.

Update all `new ScoredCbrCase<>` calls in `retrieveFeatureOnly`, `retrieveSemanticOnly`, `retrieveHybrid` to pass `caseId`.

If `"case_id"` is not in the payload (verify in `store()`), add it to the upsert in the `store()` method.

- [ ] **Step 6: Update JpaCbrCaseMemoryStore**

Pass the stored entity's caseId when constructing `ScoredCbrCase`:

```java
candidates.add(new ScoredCbrCase<>((C) reconstructed, entity.getCaseId(),
        breakdown.score(), false, breakdown.featureSimilarities()));
```

- [ ] **Step 7: Update RerankingCbrCaseMemoryStore and ReactiveRerankingCbrCaseMemoryStore**

Preserve `caseId` from the original when constructing reranked results:

```java
// Blocking
results.add(new ScoredCbrCase<C>(original.cbrCase(), original.caseId(),
        sigmoidScore, false, original.featureSimilarities()).withReranked());

// Reactive
results.add(new ScoredCbrCase<C>(original.cbrCase(), original.caseId(),
        sigmoidScore, false, original.featureSimilarities()).withReranked());
```

- [ ] **Step 8: Add contract test for caseId round-trip**

In `CbrCaseMemoryStoreContractTest`, add:

```java
@Test void retrieveSimilar_returnsCaseId() {
    registerDefaultSchema();
    String storedCaseId = store().store(
            featureCase("match problem", Map.of("grade", FeatureValue.string("A"))),
            "default", ENTITY, CBR, TENANT, "my-case-id");
    var results = store().retrieveSimilar(
            CbrQuery.of(TENANT, CBR, "default",
                    Map.of("grade", FeatureValue.string("A")), 5), FeatureVectorCbrCase.class);
    assertThat(results).hasSize(1);
    assertThat(results.getFirst().caseId()).isEqualTo("my-case-id");
}
```

- [ ] **Step 9: Build and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api,memory,memory-testing,memory-cbr-inmem,memory-cbr-crossencoder,memory-cbr-jpa,memory-qdrant -am`

All tests must pass. Use `ide_diagnostics` on each modified file to check for compilation errors before running Maven.

- [ ] **Step 10: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api memory-testing memory-cbr-inmem memory-cbr-crossencoder memory-cbr-jpa memory-qdrant memory
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#84): add caseId to ScoredCbrCase — prerequisite for retrieval traceability"
```

---

### Task 2: New SPIs and Value Types in memory-api

Pure API — interfaces, records, marker interface. No behavior, no external deps.

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/BridgedCbrStore.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/OutcomeWeightingFunction.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ExplanationRenderer.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRetrievalTrace.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRetrievalRecorded.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRetrievalTracker.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ReactiveCbrRetrievalTracker.java`

**Interfaces:**
- Produces: `BridgedCbrStore` (marker), `OutcomeWeightingFunction`, `ExplanationRenderer`, `CbrRetrievalTrace`, `CbrRetrievalRecorded`, `CbrRetrievalTracker`, `ReactiveCbrRetrievalTracker` — all consumed by Tasks 3–6.

- [ ] **Step 1: Create BridgedCbrStore marker interface**

```java
package io.casehub.neocortex.memory.cbr;

public interface BridgedCbrStore {}
```

- [ ] **Step 2: Create OutcomeWeightingFunction SPI**

```java
package io.casehub.neocortex.memory.cbr;

@FunctionalInterface
public interface OutcomeWeightingFunction {
    double apply(double similarity, double confidence);
}
```

- [ ] **Step 3: Create ExplanationRenderer SPI**

```java
package io.casehub.neocortex.memory.cbr;

public interface ExplanationRenderer {
    String render(CbrRetrievalTrace trace);
}
```

- [ ] **Step 4: Create CbrRetrievalTrace record**

```java
package io.casehub.neocortex.memory.cbr;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public record CbrRetrievalTrace(
    String traceId,
    CbrQuery query,
    List<TracedCase> results,
    Instant timestamp
) {
    public CbrRetrievalTrace {
        Objects.requireNonNull(traceId, "traceId");
        Objects.requireNonNull(query, "query");
        Objects.requireNonNull(results, "results");
        results = List.copyOf(results);
        Objects.requireNonNull(timestamp, "timestamp");
    }

    public record TracedCase(
        String caseId,
        double score,
        boolean reranked,
        Map<String, Double> featureSimilarities,
        Double confidence
    ) {
        public TracedCase {
            featureSimilarities = featureSimilarities != null
                ? Map.copyOf(featureSimilarities) : Map.of();
        }
    }
}
```

- [ ] **Step 5: Create CbrRetrievalRecorded CDI event**

```java
package io.casehub.neocortex.memory.cbr;

import java.util.List;
import java.util.Objects;

public record CbrRetrievalRecorded(
    String traceId,
    CbrQuery query,
    List<CbrRetrievalTrace.TracedCase> results
) {
    public CbrRetrievalRecorded {
        Objects.requireNonNull(traceId, "traceId");
        Objects.requireNonNull(query, "query");
        Objects.requireNonNull(results, "results");
        results = List.copyOf(results);
    }
}
```

- [ ] **Step 6: Create CbrRetrievalTracker SPI**

```java
package io.casehub.neocortex.memory.cbr;

import io.casehub.neocortex.memory.MemoryDomain;
import java.time.Instant;
import java.util.List;

public interface CbrRetrievalTracker {
    String record(CbrQuery query, List<ScoredCbrCase<?>> results);
    List<CbrRetrievalTrace> findTraces(String caseType, String tenantId,
                                        MemoryDomain domain,
                                        Instant since, Instant until);
    int purgeOlderThan(Instant cutoff);
}
```

- [ ] **Step 7: Create ReactiveCbrRetrievalTracker SPI**

```java
package io.casehub.neocortex.memory.cbr;

import io.casehub.neocortex.memory.MemoryDomain;
import io.smallrye.mutiny.Uni;
import java.time.Instant;
import java.util.List;

public interface ReactiveCbrRetrievalTracker {
    Uni<String> record(CbrQuery query, List<ScoredCbrCase<?>> results);
    Uni<List<CbrRetrievalTrace>> findTraces(String caseType, String tenantId,
                                             MemoryDomain domain,
                                             Instant since, Instant until);
    Uni<Integer> purgeOlderThan(Instant cutoff);
}
```

- [ ] **Step 8: Build and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api`

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#84): CBR retrieval traceability SPIs and value types"
```

---

### Task 3: Outcome Weighting Decorator

`@Decorator @Priority(65)` in the memory module. Config-activated. Includes default `OutcomeWeightingFunction` and tests.

**Files:**
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/OutcomeWeightingConfig.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/DefaultOutcomeWeightingFunction.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/OutcomeWeightingCbrCaseMemoryStore.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ReactiveOutcomeWeightingCbrCaseMemoryStore.java`
- Create: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/DefaultOutcomeWeightingFunctionTest.java`
- Create: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/OutcomeWeightingCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `OutcomeWeightingFunction` (from Task 2), `CbrCaseMemoryStore`, `ScoredCbrCase` with `caseId` (from Task 1)
- Produces: Outcome-weighted retrieval via `@Decorator` — transparent to callers

- [ ] **Step 1: Write DefaultOutcomeWeightingFunctionTest**

```java
package io.casehub.neocortex.memory.cbr.runtime;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class DefaultOutcomeWeightingFunctionTest {

    @Test void confidenceOne_noChange() {
        var fn = new DefaultOutcomeWeightingFunction(0.3);
        assertThat(fn.apply(0.85, 1.0)).isCloseTo(0.85, within(1e-9));
    }

    @Test void confidenceZero_reducedByAlpha() {
        var fn = new DefaultOutcomeWeightingFunction(0.3);
        // score * (1 - 0.3 + 0.3 * 0) = score * 0.7
        assertThat(fn.apply(0.85, 0.0)).isCloseTo(0.595, within(1e-9));
    }

    @Test void alphaZero_noEffect() {
        var fn = new DefaultOutcomeWeightingFunction(0.0);
        assertThat(fn.apply(0.85, 0.0)).isCloseTo(0.85, within(1e-9));
        assertThat(fn.apply(0.85, 0.5)).isCloseTo(0.85, within(1e-9));
    }

    @Test void alphaOne_fullMultiplication() {
        var fn = new DefaultOutcomeWeightingFunction(1.0);
        assertThat(fn.apply(0.85, 0.5)).isCloseTo(0.425, within(1e-9));
    }

    @Test void halfConfidence_defaultAlpha() {
        var fn = new DefaultOutcomeWeightingFunction(0.3);
        // score * (1 - 0.3 + 0.3 * 0.5) = score * 0.85
        assertThat(fn.apply(1.0, 0.5)).isCloseTo(0.85, within(1e-9));
    }

    @Test void negativeScore_handledCorrectly() {
        var fn = new DefaultOutcomeWeightingFunction(0.3);
        assertThat(fn.apply(-0.5, 1.0)).isCloseTo(-0.5, within(1e-9));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=DefaultOutcomeWeightingFunctionTest`
Expected: compilation failure — class does not exist

- [ ] **Step 3: Implement DefaultOutcomeWeightingFunction**

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.cbr.OutcomeWeightingFunction;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

@DefaultBean
@ApplicationScoped
public class DefaultOutcomeWeightingFunction implements OutcomeWeightingFunction {

    private final double alpha;

    @Inject
    DefaultOutcomeWeightingFunction(OutcomeWeightingConfig config) {
        this.alpha = config.influence();
    }

    DefaultOutcomeWeightingFunction(double alpha) {
        this.alpha = alpha;
    }

    @Override
    public double apply(double similarity, double confidence) {
        return similarity * (1.0 - alpha + alpha * confidence);
    }
}
```

- [ ] **Step 4: Create OutcomeWeightingConfig**

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.cbr.outcome-weighting")
public interface OutcomeWeightingConfig {
    @WithDefault("0.3")
    double influence();
}
```

- [ ] **Step 5: Run DefaultOutcomeWeightingFunctionTest — verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=DefaultOutcomeWeightingFunctionTest`

- [ ] **Step 6: Write OutcomeWeightingCbrCaseMemoryStoreTest**

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.EraseRequest;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import org.junit.jupiter.api.Test;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class OutcomeWeightingCbrCaseMemoryStoreTest {

    private final OutcomeWeightingFunction fn = new DefaultOutcomeWeightingFunction(0.3);

    @Test void successfulCaseRanksHigher() {
        var highConf = testCase("high", 0.9);
        var lowConf = testCase("low", 0.5);
        var delegate = stubDelegate(List.of(
                new ScoredCbrCase<>(lowConf, "c1", 0.8, false, Map.of()),
                new ScoredCbrCase<>(highConf, "c2", 0.8, false, Map.of())));
        var decorator = new OutcomeWeightingCbrCaseMemoryStore(delegate, fn);
        var results = decorator.retrieveSimilar(testQuery(), FeatureVectorCbrCase.class);
        assertThat(results.getFirst().cbrCase().confidence()).isEqualTo(0.9);
    }

    @Test void nullConfidence_treatedAsOne() {
        var noOutcome = testCase("none", null);
        var delegate = stubDelegate(List.of(
                new ScoredCbrCase<>(noOutcome, "c1", 0.8, false, Map.of())));
        var decorator = new OutcomeWeightingCbrCaseMemoryStore(delegate, fn);
        var results = decorator.retrieveSimilar(testQuery(), FeatureVectorCbrCase.class);
        assertThat(results.getFirst().score()).isCloseTo(0.8, within(1e-9));
    }

    @Test void allConfidenceOne_orderUnchanged() {
        var a = testCase("a", 1.0);
        var b = testCase("b", 1.0);
        var delegate = stubDelegate(List.of(
                new ScoredCbrCase<>(a, "c1", 0.9, false, Map.of()),
                new ScoredCbrCase<>(b, "c2", 0.7, false, Map.of())));
        var decorator = new OutcomeWeightingCbrCaseMemoryStore(delegate, fn);
        var results = decorator.retrieveSimilar(testQuery(), FeatureVectorCbrCase.class);
        assertThat(results.get(0).cbrCase().problem()).isEqualTo("a");
        assertThat(results.get(1).cbrCase().problem()).isEqualTo("b");
    }

    @Test void influenceZero_noEffect() {
        var lowConf = testCase("low", 0.1);
        var noEffect = new DefaultOutcomeWeightingFunction(0.0);
        var delegate = stubDelegate(List.of(
                new ScoredCbrCase<>(lowConf, "c1", 0.8, false, Map.of())));
        var decorator = new OutcomeWeightingCbrCaseMemoryStore(delegate, noEffect);
        var results = decorator.retrieveSimilar(testQuery(), FeatureVectorCbrCase.class);
        assertThat(results.getFirst().score()).isCloseTo(0.8, within(1e-9));
    }

    @Test void preservesCaseIdAndRerankedFlag() {
        var c = testCase("p", 0.8);
        var delegate = stubDelegate(List.of(
                new ScoredCbrCase<>(c, "case-42", 0.9, true, Map.of("f", 0.95))));
        var decorator = new OutcomeWeightingCbrCaseMemoryStore(delegate, fn);
        var result = decorator.retrieveSimilar(testQuery(), FeatureVectorCbrCase.class).getFirst();
        assertThat(result.caseId()).isEqualTo("case-42");
        assertThat(result.reranked()).isTrue();
        assertThat(result.featureSimilarities()).containsEntry("f", 0.95);
    }

    @Test void passThrough_store() {
        var delegate = stubDelegate(List.of());
        var decorator = new OutcomeWeightingCbrCaseMemoryStore(delegate, fn);
        var schema = new CbrFeatureSchema("test", List.of());
        decorator.registerSchema(schema);
        // no exception = pass-through works
    }

    // --- helpers ---
    private FeatureVectorCbrCase testCase(String problem, Double confidence) {
        return new FeatureVectorCbrCase(problem, "sol", null, confidence, Map.of());
    }
    private CbrQuery testQuery() {
        return CbrQuery.of("t1", MemoryDomain.of("cbr"), "default", Map.of(), 10);
    }
    private CbrCaseMemoryStore stubDelegate(List<ScoredCbrCase<FeatureVectorCbrCase>> results) {
        return new CbrCaseMemoryStore() {
            @Override public void registerSchema(CbrFeatureSchema schema) {}
            @Override public String store(CbrCase c, String t, String e, MemoryDomain d, String tid, String cid) { return "id"; }
            @Override @SuppressWarnings("unchecked")
            public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery q, Class<C> cl) {
                return (List<ScoredCbrCase<C>>) (List<?>) results;
            }
            @Override public Integer erase(EraseRequest r) { return 0; }
            @Override public Integer eraseEntity(String e, String t) { return 0; }
            @Override public void recordOutcome(String c, String t, CbrOutcome o) {}
        };
    }
}
```

- [ ] **Step 7: Run test to verify it fails**

- [ ] **Step 8: Implement OutcomeWeightingCbrCaseMemoryStore**

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.EraseRequest;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

@Decorator
@Priority(65)
@IfBuildProperty(name = "casehub.cbr.outcome-weighting.enabled", stringValue = "true")
public class OutcomeWeightingCbrCaseMemoryStore implements CbrCaseMemoryStore {

    private final CbrCaseMemoryStore delegate;
    private final OutcomeWeightingFunction weightingFunction;

    @Inject
    OutcomeWeightingCbrCaseMemoryStore(@Delegate @Any CbrCaseMemoryStore delegate,
                                       OutcomeWeightingFunction weightingFunction) {
        this.delegate = delegate;
        this.weightingFunction = weightingFunction;
    }

    @Override
    public void registerSchema(CbrFeatureSchema schema) { delegate.registerSchema(schema); }

    @Override
    public String store(CbrCase cbrCase, String caseType, String entityId,
                        MemoryDomain domain, String tenantId, String caseId) {
        return delegate.store(cbrCase, caseType, entityId, domain, tenantId, caseId);
    }

    @Override
    public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(
            CbrQuery query, Class<C> caseClass) {
        List<ScoredCbrCase<C>> results = delegate.retrieveSimilar(query, caseClass);
        if (results.isEmpty()) return results;
        List<ScoredCbrCase<C>> weighted = new ArrayList<>(results.size());
        for (ScoredCbrCase<C> scored : results) {
            double confidence = scored.cbrCase().confidence() != null
                    ? scored.cbrCase().confidence() : 1.0;
            double newScore = weightingFunction.apply(scored.score(), confidence);
            weighted.add(new ScoredCbrCase<>(scored.cbrCase(), scored.caseId(),
                    newScore, scored.reranked(), scored.featureSimilarities()));
        }
        weighted.sort((a, b) -> Double.compare(b.score(), a.score()));
        return Collections.unmodifiableList(weighted);
    }

    @Override
    public Integer erase(EraseRequest request) { return delegate.erase(request); }

    @Override
    public Integer eraseEntity(String entityId, String tenantId) {
        return delegate.eraseEntity(entityId, tenantId);
    }

    @Override
    public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
        delegate.recordOutcome(caseId, tenantId, outcome);
    }
}
```

- [ ] **Step 9: Implement ReactiveOutcomeWeightingCbrCaseMemoryStore**

Same logic on `ReactiveCbrCaseMemoryStore`. `@Decorator @Priority(65)` with `@IfBuildProperty`. Reactive variant maps the `Uni<List<ScoredCbrCase<C>>>` result.

- [ ] **Step 10: Run tests — verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest="DefaultOutcomeWeightingFunctionTest,OutcomeWeightingCbrCaseMemoryStoreTest"`

- [ ] **Step 11: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#84): outcome weighting decorator — confidence modulates retrieval scores"
```

---

### Task 4: DefaultExplanationRenderer + BridgedCbrStore

Small additions to the memory module — the generic explanation renderer and the bridge marker interface implementation.

**Files:**
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/DefaultExplanationRenderer.java`
- Create: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/DefaultExplanationRendererTest.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/BlockingToReactiveCbrBridge.java` — add `implements BridgedCbrStore`

**Interfaces:**
- Consumes: `ExplanationRenderer`, `CbrRetrievalTrace`, `BridgedCbrStore` (from Task 2)
- Produces: `DefaultExplanationRenderer` @DefaultBean, `BlockingToReactiveCbrBridge implements BridgedCbrStore`

- [ ] **Step 1: Write DefaultExplanationRendererTest**

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class DefaultExplanationRendererTest {

    private final DefaultExplanationRenderer renderer = new DefaultExplanationRenderer();

    @Test void rendersTopMatchWithBreakdown() {
        var trace = new CbrRetrievalTrace("t1",
                CbrQuery.of("tenant", MemoryDomain.of("cbr"), "adverse-event", Map.of(), 5)
                        .withRetrievalMode(RetrievalMode.HYBRID),
                List.of(new CbrRetrievalTrace.TracedCase("ae-001", 0.92, false,
                        Map.of("grade", 1.0, "eventType", 0.95), 0.85)),
                Instant.now());
        String result = renderer.render(trace);
        assertThat(result).contains("Retrieved 1 case");
        assertThat(result).contains("caseId=ae-001");
        assertThat(result).contains("score=0.92");
        assertThat(result).contains("confidence=0.85");
        assertThat(result).contains("grade=1.00");
    }

    @Test void emptyResults() {
        var trace = new CbrRetrievalTrace("t1",
                CbrQuery.of("tenant", MemoryDomain.of("cbr"), "default", Map.of(), 5),
                List.of(), Instant.now());
        String result = renderer.render(trace);
        assertThat(result).contains("Retrieved 0 cases");
    }

    @Test void nullConfidence() {
        var trace = new CbrRetrievalTrace("t1",
                CbrQuery.of("tenant", MemoryDomain.of("cbr"), "default", Map.of(), 5),
                List.of(new CbrRetrievalTrace.TracedCase("c1", 0.75, false, Map.of(), null)),
                Instant.now());
        String result = renderer.render(trace);
        assertThat(result).doesNotContain("null");
    }

    @Test void nullCaseId() {
        var trace = new CbrRetrievalTrace("t1",
                CbrQuery.of("tenant", MemoryDomain.of("cbr"), "default", Map.of(), 5),
                List.of(new CbrRetrievalTrace.TracedCase(null, 0.75, false, Map.of(), 0.9)),
                Instant.now());
        String result = renderer.render(trace);
        assertThat(result).doesNotContain("null");
    }
}
```

- [ ] **Step 2: Implement DefaultExplanationRenderer**

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.cbr.CbrRetrievalTrace;
import io.casehub.neocortex.memory.cbr.ExplanationRenderer;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;
import java.util.stream.Collectors;

@DefaultBean
@ApplicationScoped
public class DefaultExplanationRenderer implements ExplanationRenderer {

    @Override
    public String render(CbrRetrievalTrace trace) {
        int count = trace.results().size();
        var sb = new StringBuilder();
        sb.append("Retrieved ").append(count).append(count == 1 ? " case" : " cases");
        sb.append(" (mode: ").append(trace.query().retrievalMode());
        sb.append(", caseType: ").append(trace.query().caseType()).append(").");

        if (!trace.results().isEmpty()) {
            var top = trace.results().getFirst();
            sb.append("\nTop match:");
            if (top.caseId() != null) sb.append(" caseId=").append(top.caseId()).append(",");
            sb.append(" score=").append(String.format("%.2f", top.score()));
            if (top.confidence() != null) {
                sb.append(", confidence=").append(String.format("%.2f", top.confidence()));
            }
            sb.append(".");
            if (!top.featureSimilarities().isEmpty()) {
                String breakdown = top.featureSimilarities().entrySet().stream()
                        .sorted(java.util.Map.Entry.<String, Double>comparingByValue().reversed())
                        .map(e -> e.getKey() + "=" + String.format("%.2f", e.getValue()))
                        .collect(Collectors.joining(", "));
                sb.append("\nFeature breakdown: ").append(breakdown).append(".");
            }
        }
        return sb.toString();
    }
}
```

- [ ] **Step 3: Add BridgedCbrStore to BlockingToReactiveCbrBridge**

Use `ide_edit_member` with member=`BlockingToReactiveCbrBridge` to change the class declaration:

```java
@DefaultBean
@ApplicationScoped
public class BlockingToReactiveCbrBridge implements ReactiveCbrCaseMemoryStore, BridgedCbrStore {
```

- [ ] **Step 4: Run tests and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory`

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#84): DefaultExplanationRenderer + BridgedCbrStore marker on bridge"
```

---

### Task 5: InMemoryCbrRetrievalTracker + Contract Test

Test infrastructure that Task 6 depends on.

**Files:**
- Create: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/InMemoryCbrRetrievalTracker.java`
- Create: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrRetrievalTrackerContractTest.java`
- Create: `memory-testing/src/test/java/io/casehub/neocortex/memory/cbr/testing/InMemoryCbrRetrievalTrackerTest.java`

**Interfaces:**
- Consumes: `CbrRetrievalTracker`, `CbrRetrievalTrace`, `CbrQuery`, `ScoredCbrCase` (from Tasks 1–2)
- Produces: `CbrRetrievalTrackerContractTest` abstract base — extended by `SqliteCbrRetrievalTrackerTest` in Task 6

- [ ] **Step 1: Write CbrRetrievalTrackerContractTest**

Abstract base with 10 contract tests:

```java
package io.casehub.neocortex.memory.cbr.testing;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

public abstract class CbrRetrievalTrackerContractTest {

    protected static final MemoryDomain CBR = MemoryDomain.of("cbr");
    protected static final MemoryDomain CLINICAL = MemoryDomain.of("clinical");

    protected abstract CbrRetrievalTracker tracker();

    private CbrQuery query(String tenantId) {
        return CbrQuery.of(tenantId, CBR, "default", Map.of(), 5);
    }

    private List<ScoredCbrCase<?>> results() {
        var c = new FeatureVectorCbrCase("problem", "solution", null, 0.9, Map.of());
        return List.of(new ScoredCbrCase<>(c, "case-1", 0.85));
    }

    @Test void record_returnsNonBlankTraceId() {
        String id = tracker().record(query("t1"), results());
        assertThat(id).isNotBlank();
    }

    @Test void record_persistsQueryAndResults() {
        tracker().record(query("t1"), results());
        var traces = tracker().findTraces("default", "t1", CBR,
                Instant.now().minus(1, ChronoUnit.HOURS), Instant.now().plus(1, ChronoUnit.HOURS));
        assertThat(traces).hasSize(1);
        assertThat(traces.getFirst().results()).hasSize(1);
        assertThat(traces.getFirst().results().getFirst().caseId()).isEqualTo("case-1");
    }

    @Test void findTraces_byCaseTypeAndTenant() {
        tracker().record(query("t1"), results());
        tracker().record(CbrQuery.of("t2", CBR, "default", Map.of(), 5), results());
        var traces = tracker().findTraces("default", "t1", CBR,
                Instant.EPOCH, Instant.now().plus(1, ChronoUnit.HOURS));
        assertThat(traces).hasSize(1);
    }

    @Test void findTraces_domainIsolation() {
        tracker().record(CbrQuery.of("t1", CBR, "default", Map.of(), 5), results());
        tracker().record(CbrQuery.of("t1", CLINICAL, "default", Map.of(), 5), results());
        var cbrTraces = tracker().findTraces("default", "t1", CBR,
                Instant.EPOCH, Instant.now().plus(1, ChronoUnit.HOURS));
        var clinicalTraces = tracker().findTraces("default", "t1", CLINICAL,
                Instant.EPOCH, Instant.now().plus(1, ChronoUnit.HOURS));
        assertThat(cbrTraces).hasSize(1);
        assertThat(clinicalTraces).hasSize(1);
    }

    @Test void findTraces_timeRangeFiltering() {
        tracker().record(query("t1"), results());
        var traces = tracker().findTraces("default", "t1", CBR,
                Instant.now().plus(1, ChronoUnit.HOURS),
                Instant.now().plus(2, ChronoUnit.HOURS));
        assertThat(traces).isEmpty();
    }

    @Test void findTraces_emptyWhenNoMatches() {
        var traces = tracker().findTraces("nonexistent", "t1", CBR,
                Instant.EPOCH, Instant.now().plus(1, ChronoUnit.HOURS));
        assertThat(traces).isEmpty();
    }

    @Test void findTraces_multipleTraces_orderedByTimestamp() {
        tracker().record(query("t1"), results());
        tracker().record(query("t1"), results());
        var traces = tracker().findTraces("default", "t1", CBR,
                Instant.EPOCH, Instant.now().plus(1, ChronoUnit.HOURS));
        assertThat(traces).hasSize(2);
        assertThat(traces.get(0).timestamp()).isBeforeOrEqualTo(traces.get(1).timestamp());
    }

    @Test void purgeOlderThan_removesOldTraces() {
        tracker().record(query("t1"), results());
        int purged = tracker().purgeOlderThan(Instant.now().plus(1, ChronoUnit.HOURS));
        assertThat(purged).isEqualTo(1);
        assertThat(tracker().findTraces("default", "t1", CBR,
                Instant.EPOCH, Instant.now().plus(1, ChronoUnit.HOURS))).isEmpty();
    }

    @Test void purgeOlderThan_preservesRecentTraces() {
        tracker().record(query("t1"), results());
        int purged = tracker().purgeOlderThan(Instant.now().minus(1, ChronoUnit.HOURS));
        assertThat(purged).isEqualTo(0);
    }

    @Test void purgeOlderThan_returnsDeletedCount() {
        tracker().record(query("t1"), results());
        tracker().record(query("t1"), results());
        int purged = tracker().purgeOlderThan(Instant.now().plus(1, ChronoUnit.HOURS));
        assertThat(purged).isEqualTo(2);
    }
}
```

- [ ] **Step 2: Implement InMemoryCbrRetrievalTracker**

```java
package io.casehub.neocortex.memory.cbr.testing;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.CopyOnWriteArrayList;

@Alternative
@Priority(1)
@ApplicationScoped
public class InMemoryCbrRetrievalTracker implements CbrRetrievalTracker {

    private final List<CbrRetrievalTrace> traces = new CopyOnWriteArrayList<>();

    @Override
    public String record(CbrQuery query, List<ScoredCbrCase<?>> results) {
        String traceId = UUID.randomUUID().toString();
        List<CbrRetrievalTrace.TracedCase> traced = results.stream()
                .map(s -> new CbrRetrievalTrace.TracedCase(
                        s.caseId(), s.score(), s.reranked(),
                        s.featureSimilarities(),
                        s.cbrCase().confidence()))
                .toList();
        traces.add(new CbrRetrievalTrace(traceId, query, traced, Instant.now()));
        return traceId;
    }

    @Override
    public List<CbrRetrievalTrace> findTraces(String caseType, String tenantId,
                                               MemoryDomain domain,
                                               Instant since, Instant until) {
        return traces.stream()
                .filter(t -> t.query().caseType().equals(caseType))
                .filter(t -> t.query().tenantId().equals(tenantId))
                .filter(t -> t.query().domain().equals(domain))
                .filter(t -> !t.timestamp().isBefore(since) && t.timestamp().isBefore(until))
                .sorted(Comparator.comparing(CbrRetrievalTrace::timestamp))
                .toList();
    }

    @Override
    public int purgeOlderThan(Instant cutoff) {
        int before = traces.size();
        traces.removeIf(t -> t.timestamp().isBefore(cutoff));
        return before - traces.size();
    }
}
```

- [ ] **Step 3: Create InMemoryCbrRetrievalTrackerTest**

```java
package io.casehub.neocortex.memory.cbr.testing;

class InMemoryCbrRetrievalTrackerTest extends CbrRetrievalTrackerContractTest {
    private final InMemoryCbrRetrievalTracker tracker = new InMemoryCbrRetrievalTracker();

    @Override
    protected CbrRetrievalTracker tracker() { return tracker; }
}
```

- [ ] **Step 4: Run tests and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-testing`

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-testing
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#84): CbrRetrievalTrackerContractTest + InMemoryCbrRetrievalTracker"
```

---

### Task 6: memory-cbr-tracking Module

New Maven module: SQLite tracker, Flyway migration, tracking decorators with double-recording guard, blocking-to-reactive bridge.

**Files:**
- Create: `memory-cbr-tracking/pom.xml`
- Create: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/CbrTrackingConfig.java`
- Create: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/SqliteCbrRetrievalTracker.java`
- Create: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/BlockingToReactiveCbrRetrievalTracker.java`
- Create: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/TrackingCbrCaseMemoryStore.java`
- Create: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/ReactiveTrackingCbrCaseMemoryStore.java`
- Create: `memory-cbr-tracking/src/main/resources/db/cbr-tracking/migration/V1__cbr_retrieval_tracking.sql`
- Create: `memory-cbr-tracking/src/test/java/io/casehub/neocortex/memory/cbr/tracking/SqliteCbrRetrievalTrackerTest.java`
- Create: `memory-cbr-tracking/src/test/java/io/casehub/neocortex/memory/cbr/tracking/TrackingCbrCaseMemoryStoreTest.java`
- Modify: `pom.xml` (parent) — add `<module>memory-cbr-tracking</module>`

**Interfaces:**
- Consumes: `CbrRetrievalTracker`, `ReactiveCbrRetrievalTracker`, `CbrRetrievalTrace`, `CbrRetrievalRecorded`, `BridgedCbrStore`, `CbrCaseMemoryStore`, `ReactiveCbrCaseMemoryStore` (from Tasks 1–2)
- Produces: SQLite-backed CBR retrieval tracking, activated by `casehub.cbr.tracking.enabled=true`

- [ ] **Step 1: Add module to parent pom.xml**

Add `<module>memory-cbr-tracking</module>` after `memory-cbr-crossencoder` in the parent pom.xml modules list.

- [ ] **Step 2: Create memory-cbr-tracking/pom.xml**

Modelled on rag-tracking pom.xml:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>0.2-SNAPSHOT</version>
    </parent>
    <artifactId>casehub-neocortex-memory-cbr-tracking</artifactId>
    <packaging>jar</packaging>
    <name>CaseHub Neocortex - Memory CBR Tracking</name>
    <description>SQLite-backed CbrRetrievalTracker + tracking decorators for CbrCaseMemoryStore.
        Classpath + config activated (casehub.cbr.tracking.enabled=true).</description>
    <dependencies>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-api</artifactId>
        </dependency>
        <dependency>
            <groupId>org.xerial</groupId>
            <artifactId>sqlite-jdbc</artifactId>
        </dependency>
        <dependency>
            <groupId>com.zaxxer</groupId>
            <artifactId>HikariCP</artifactId>
        </dependency>
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-core</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-arc</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-scheduler</artifactId>
        </dependency>
        <dependency>
            <groupId>org.eclipse.microprofile.config</groupId>
            <artifactId>microprofile-config-api</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>io.smallrye.reactive</groupId>
            <artifactId>mutiny</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
            <scope>provided</scope>
        </dependency>
        <!-- Test -->
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-testing</artifactId>
            <version>${project.version}</version>
            <scope>test</scope>
        </dependency>
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

- [ ] **Step 3: Create Flyway V1 migration**

```sql
-- V1__cbr_retrieval_tracking.sql
CREATE TABLE cbr_retrieval_traces (
    trace_id    TEXT PRIMARY KEY,
    case_type   TEXT NOT NULL,
    tenant_id   TEXT NOT NULL,
    domain      TEXT NOT NULL,
    query_json  TEXT NOT NULL,
    results_json TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);

CREATE INDEX idx_cbr_traces_lookup
    ON cbr_retrieval_traces(case_type, tenant_id, domain, timestamp);
```

- [ ] **Step 4: Create CbrTrackingConfig**

```java
package io.casehub.neocortex.memory.cbr.tracking;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.cbr.tracking")
public interface CbrTrackingConfig {
    @WithDefault("90")
    int retentionDays();

    Sqlite sqlite();

    interface Sqlite {
        String path();
        @WithDefault("5")
        int poolMaxSize();
        @WithDefault("5000")
        int busyTimeoutMs();
    }
}
```

- [ ] **Step 5: Write SqliteCbrRetrievalTrackerTest**

```java
package io.casehub.neocortex.memory.cbr.tracking;

import io.casehub.neocortex.memory.cbr.CbrRetrievalTracker;
import io.casehub.neocortex.memory.cbr.testing.CbrRetrievalTrackerContractTest;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;

class SqliteCbrRetrievalTrackerTest extends CbrRetrievalTrackerContractTest {

    private SqliteCbrRetrievalTracker tracker;

    @BeforeEach
    void setUp() {
        tracker = new SqliteCbrRetrievalTracker(":memory:", 1, 5000);
        tracker.init();
    }

    @AfterEach
    void tearDown() {
        if (tracker != null) tracker.shutdown();
    }

    @Override
    protected CbrRetrievalTracker tracker() { return tracker; }
}
```

- [ ] **Step 6: Implement SqliteCbrRetrievalTracker**

Follow the `SqliteRetrievalTracker` pattern from rag-tracking:
- `@ApplicationScoped`
- `@PostConstruct init()` — HikariCP + Flyway (location `classpath:db/cbr-tracking/migration`)
- `@PreDestroy shutdown()` — close DataSource
- `@Scheduled(every = "24h") void purgeExpired()` — calls `purgeOlderThan` with retention days
- `record()` — serialize `TracedCase` list as JSON, insert row, return UUID
- `findTraces()` — query with caseType, tenantId, domain, timestamp range, deserialize JSON
- `purgeOlderThan()` — DELETE WHERE timestamp < cutoff
- Test-friendly constructor `SqliteCbrRetrievalTracker(String path, int poolSize, int busyTimeout)` for unit tests

Serialization: use Jackson `ObjectMapper` for `resultsJson` (List<TracedCase> — all primitives). For `queryJson`, serialize the query features via `FeatureValue.toRawMap()` + Jackson.

- [ ] **Step 7: Run SqliteCbrRetrievalTrackerTest — verify all 10 contract tests pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-tracking -Dtest=SqliteCbrRetrievalTrackerTest`

- [ ] **Step 8: Create BlockingToReactiveCbrRetrievalTracker bridge**

```java
package io.casehub.neocortex.memory.cbr.tracking;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import io.quarkus.arc.DefaultBean;
import io.smallrye.mutiny.Uni;
import io.smallrye.mutiny.infrastructure.Infrastructure;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.time.Instant;
import java.util.List;

@DefaultBean
@ApplicationScoped
public class BlockingToReactiveCbrRetrievalTracker implements ReactiveCbrRetrievalTracker {

    @Inject CbrRetrievalTracker delegate;

    @Override
    public Uni<String> record(CbrQuery query, List<ScoredCbrCase<?>> results) {
        return Uni.createFrom().item(() -> delegate.record(query, results))
                .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public Uni<List<CbrRetrievalTrace>> findTraces(String caseType, String tenantId,
                                                    MemoryDomain domain,
                                                    Instant since, Instant until) {
        return Uni.createFrom().item(() -> delegate.findTraces(caseType, tenantId, domain, since, until))
                .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }

    @Override
    public Uni<Integer> purgeOlderThan(Instant cutoff) {
        return Uni.createFrom().item(() -> delegate.purgeOlderThan(cutoff))
                .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
    }
}
```

- [ ] **Step 9: Write TrackingCbrCaseMemoryStoreTest**

```java
package io.casehub.neocortex.memory.cbr.tracking;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import io.casehub.neocortex.memory.cbr.testing.InMemoryCbrRetrievalTracker;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;
import static org.assertj.core.api.Assertions.*;

class TrackingCbrCaseMemoryStoreTest {

    @Test void recordsTraceAndFiresEvent() {
        var tracker = new InMemoryCbrRetrievalTracker();
        var eventRef = new AtomicReference<CbrRetrievalRecorded>();
        var c = new FeatureVectorCbrCase("p", "s", null, 0.9, Map.of());
        var results = List.<ScoredCbrCase<FeatureVectorCbrCase>>of(
                new ScoredCbrCase<>(c, "c1", 0.85));
        var delegate = stubDelegate(results);
        var decorator = new TrackingCbrCaseMemoryStore(delegate, tracker, eventRef::set);

        var query = CbrQuery.of("t1", MemoryDomain.of("cbr"), "default", Map.of(), 5);
        var returned = decorator.retrieveSimilar(query, FeatureVectorCbrCase.class);

        assertThat(returned).isEqualTo(results);
        assertThat(eventRef.get()).isNotNull();
        assertThat(eventRef.get().traceId()).isNotBlank();
        assertThat(eventRef.get().results()).hasSize(1);
    }

    @Test void trackerFailure_nonFatal() {
        CbrRetrievalTracker failingTracker = new CbrRetrievalTracker() {
            @Override public String record(CbrQuery q, List<ScoredCbrCase<?>> r) {
                throw new RuntimeException("boom");
            }
            @Override public List<CbrRetrievalTrace> findTraces(String ct, String t, MemoryDomain d, java.time.Instant s, java.time.Instant u) { return List.of(); }
            @Override public int purgeOlderThan(java.time.Instant cutoff) { return 0; }
        };
        var c = new FeatureVectorCbrCase("p", "s", null, 0.9, Map.of());
        var results = List.<ScoredCbrCase<FeatureVectorCbrCase>>of(
                new ScoredCbrCase<>(c, "c1", 0.85));
        var delegate = stubDelegate(results);
        var decorator = new TrackingCbrCaseMemoryStore(delegate, failingTracker, e -> {});

        var query = CbrQuery.of("t1", MemoryDomain.of("cbr"), "default", Map.of(), 5);
        var returned = decorator.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(returned).isEqualTo(results);
    }

    @Test void resultsUnchanged() {
        var tracker = new InMemoryCbrRetrievalTracker();
        var c = new FeatureVectorCbrCase("p", "s", null, 0.9, Map.of());
        var results = List.<ScoredCbrCase<FeatureVectorCbrCase>>of(
                new ScoredCbrCase<>(c, "c1", 0.85, true, Map.of("f", 0.9)));
        var delegate = stubDelegate(results);
        var decorator = new TrackingCbrCaseMemoryStore(delegate, tracker, e -> {});

        var query = CbrQuery.of("t1", MemoryDomain.of("cbr"), "default", Map.of(), 5);
        var returned = decorator.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(returned.getFirst().score()).isEqualTo(0.85);
        assertThat(returned.getFirst().reranked()).isTrue();
        assertThat(returned.getFirst().caseId()).isEqualTo("c1");
    }

    @SuppressWarnings("unchecked")
    private CbrCaseMemoryStore stubDelegate(List<? extends ScoredCbrCase<?>> results) {
        return new CbrCaseMemoryStore() {
            @Override public void registerSchema(CbrFeatureSchema s) {}
            @Override public String store(CbrCase c, String t, String e, MemoryDomain d, String tid, String cid) { return "id"; }
            @Override public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery q, Class<C> cl) {
                return (List<ScoredCbrCase<C>>) (List<?>) results;
            }
            @Override public Integer erase(io.casehub.neocortex.memory.EraseRequest r) { return 0; }
            @Override public Integer eraseEntity(String e, String t) { return 0; }
            @Override public void recordOutcome(String c, String t, CbrOutcome o) {}
        };
    }
}
```

- [ ] **Step 10: Implement TrackingCbrCaseMemoryStore**

```java
package io.casehub.neocortex.memory.cbr.tracking;

import io.casehub.neocortex.memory.EraseRequest;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.event.Event;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;
import org.jboss.logging.Logger;
import java.util.List;
import java.util.function.Consumer;

@Decorator
@Priority(50)
@IfBuildProperty(name = "casehub.cbr.tracking.enabled", stringValue = "true")
public class TrackingCbrCaseMemoryStore implements CbrCaseMemoryStore {

    private static final Logger LOG = Logger.getLogger(TrackingCbrCaseMemoryStore.class);

    private final CbrCaseMemoryStore delegate;
    private final CbrRetrievalTracker tracker;
    private final Consumer<CbrRetrievalRecorded> eventSink;

    @Inject
    TrackingCbrCaseMemoryStore(@Delegate @Any CbrCaseMemoryStore delegate,
                                CbrRetrievalTracker tracker,
                                Event<CbrRetrievalRecorded> recordedEvent) {
        this(delegate, tracker, recordedEvent::fire);
    }

    TrackingCbrCaseMemoryStore(CbrCaseMemoryStore delegate,
                                CbrRetrievalTracker tracker,
                                Consumer<CbrRetrievalRecorded> eventSink) {
        this.delegate = delegate;
        this.tracker = tracker;
        this.eventSink = eventSink;
    }

    @Override public void registerSchema(CbrFeatureSchema schema) { delegate.registerSchema(schema); }
    @Override public String store(CbrCase c, String ct, String eid, MemoryDomain d, String tid, String cid) {
        return delegate.store(c, ct, eid, d, tid, cid);
    }

    @Override
    public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(CbrQuery query, Class<C> caseClass) {
        List<ScoredCbrCase<C>> results = delegate.retrieveSimilar(query, caseClass);
        try {
            String traceId = tracker.record(query, (List<ScoredCbrCase<?>>) (List<?>) results);
            var traced = results.stream()
                    .map(s -> new CbrRetrievalTrace.TracedCase(
                            s.caseId(), s.score(), s.reranked(),
                            s.featureSimilarities(), s.cbrCase().confidence()))
                    .toList();
            eventSink.accept(new CbrRetrievalRecorded(traceId, query, traced));
        } catch (Exception e) {
            LOG.warn("CBR retrieval tracking failed — returning results unchanged", e);
        }
        return results;
    }

    @Override public Integer erase(EraseRequest r) { return delegate.erase(r); }
    @Override public Integer eraseEntity(String eid, String tid) { return delegate.eraseEntity(eid, tid); }
    @Override public void recordOutcome(String cid, String tid, CbrOutcome o) { delegate.recordOutcome(cid, tid, o); }
}
```

- [ ] **Step 11: Implement ReactiveTrackingCbrCaseMemoryStore with bridge guard**

```java
@Decorator
@Priority(50)
@IfBuildProperty(name = "casehub.cbr.tracking.enabled", stringValue = "true")
public class ReactiveTrackingCbrCaseMemoryStore implements ReactiveCbrCaseMemoryStore {
    // Inject Instance<? extends BridgedCbrStore> to detect bridge
    // If bridge present → pass-through (blocking decorator handles tracking)
    // If bridge absent → track via ReactiveCbrRetrievalTracker, fireAsync()
}
```

The bridge detection uses `delegate instanceof BridgedCbrStore` check. If the delegate is a bridge, all methods pass through without tracking.

- [ ] **Step 12: Run all tracking tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-tracking`

- [ ] **Step 13: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

All modules must pass.

- [ ] **Step 14: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-cbr-tracking pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#84): memory-cbr-tracking module — SQLite tracker + tracking decorators"
```

---

### Task 7: Update CLAUDE.md

Update the module structure and Maven coordinates tables in CLAUDE.md to include the new `memory-cbr-tracking` module and the new SPIs.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add memory-cbr-tracking to module structure**

Add after `memory-cbr-crossencoder/` in the module tree:
```
memory-cbr-tracking/  — @Decorator @Priority(50) retrieval tracking on CbrCaseMemoryStore + ReactiveCbrCaseMemoryStore,
                        SqliteCbrRetrievalTracker (SQLite + HikariCP WAL + Flyway), BlockingToReactiveCbrRetrievalTracker
                        @DefaultBean bridge, CbrRetentionScheduler (@Scheduled, casehub.cbr.tracking.retention.days
                        default 90). Classpath + config activated (casehub.cbr.tracking.enabled=true)
```

- [ ] **Step 2: Add Maven coordinates**

Add to the table: `Memory CBR Tracking | casehub-neocortex-memory-cbr-tracking`

Add root package: `Root Java package (memory-cbr-tracking) | io.casehub.neocortex.memory.cbr.tracking`

- [ ] **Step 3: Update memory-api module description**

Add the new SPIs to the memory-api description: `OutcomeWeightingFunction`, `ExplanationRenderer`, `CbrRetrievalTrace`, `CbrRetrievalRecorded`, `CbrRetrievalTracker`, `ReactiveCbrRetrievalTracker`, `BridgedCbrStore`.

Update `ScoredCbrCase` description to note the `caseId` field.

- [ ] **Step 4: Update memory module description**

Add: `OutcomeWeightingCbrCaseMemoryStore (@Decorator @Priority(65), @IfBuildProperty casehub.cbr.outcome-weighting.enabled)`, `DefaultOutcomeWeightingFunction (@DefaultBean, linear interpolation)`, `DefaultExplanationRenderer (@DefaultBean)`.

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "docs(#84): update CLAUDE.md with memory-cbr-tracking module and new SPIs"
```
