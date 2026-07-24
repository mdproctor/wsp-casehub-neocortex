# CBR Revise SPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #140 — feat: CBR Revise SPI — recordOutcome for CbrCaseMemoryStore
**Issue group:** #140

**Goal:** Add `recordOutcome()` to the CBR SPI so that case outcome observations
update the stored case's `outcome` and `confidence` fields, closing the CBR
Revise feedback loop.

**Architecture:** New `CbrOutcome` record in memory-api carries outcome data.
`CbrCaseMemoryStore.recordOutcome(caseId, tenantId, outcome)` is the SPI method —
no `caseType` in the signature (consumer doesn't have it; backends iterate
registered schemas). Confidence adjustment uses EMA. Idempotency via `observedAt`
timestamp guard. CloudEvent consumer in memory/ module bridges desiredstate events
to the SPI.

**Tech Stack:** Java 21, Quarkus CDI, Qdrant gRPC client, JPA/Hibernate,
casehub-desiredstate-api (CloudEvent types)

## Global Constraints

- Java 21 language level, Java 26 JVM
- Pre-release: breaking changes are free
- `CbrCase.withOutcome()` is abstract, not default — compile-time safety
- Learning rate constant: `CbrOutcome.DEFAULT_LEARNING_RATE = 0.2`
- Null confidence treated as 1.0 in EMA calculation
- Case not found on `recordOutcome` → silent ignore, no exception
- Idempotency: skip if `outcome.observedAt()` ≤ stored `lastOutcomeAt`
- `Outcome` enum (not `Result`) — consistent with desiredstate spec

---

### Task 1: CbrOutcome record + CbrCase.withOutcome

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrOutcome.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureVectorCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TextualCbrCase.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrOutcomeTest.java`

**Interfaces:**
- Produces: `CbrOutcome(Outcome result, double successRate, String detail, Instant observedAt)`,
  `CbrOutcome.of(double, String, Instant)`, `CbrOutcome.adjustConfidence(Double, double, double)`,
  `CbrOutcome.DEFAULT_LEARNING_RATE`, `CbrCase.withOutcome(String, Double)`

- [ ] **Step 1: Write CbrOutcome unit tests**

Create `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrOutcomeTest.java`:

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.time.Instant;
import static org.assertj.core.api.Assertions.*;

class CbrOutcomeTest {

    private static final Instant NOW = Instant.parse("2026-07-13T10:00:00Z");

    @Test
    void of_successRate1_isSuccess() {
        CbrOutcome outcome = CbrOutcome.of(1.0, "all passed", NOW);
        assertThat(outcome.result()).isEqualTo(CbrOutcome.Outcome.SUCCESS);
        assertThat(outcome.successRate()).isEqualTo(1.0);
        assertThat(outcome.detail()).isEqualTo("all passed");
        assertThat(outcome.observedAt()).isEqualTo(NOW);
    }

    @Test
    void of_successRate0_isFailure() {
        CbrOutcome outcome = CbrOutcome.of(0.0, null, NOW);
        assertThat(outcome.result()).isEqualTo(CbrOutcome.Outcome.FAILURE);
    }

    @Test
    void of_successRateBetween_isPartial() {
        CbrOutcome outcome = CbrOutcome.of(0.75, "3 of 4", NOW);
        assertThat(outcome.result()).isEqualTo(CbrOutcome.Outcome.PARTIAL);
    }

    @Test
    void constructor_rejectsNegativeRate() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new CbrOutcome(CbrOutcome.Outcome.FAILURE, -0.1, null, NOW));
    }

    @Test
    void constructor_rejectsRateAboveOne() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new CbrOutcome(CbrOutcome.Outcome.SUCCESS, 1.1, null, NOW));
    }

    @Test
    void constructor_rejectsNullResult() {
        assertThatNullPointerException()
            .isThrownBy(() -> new CbrOutcome(null, 0.5, null, NOW));
    }

    @Test
    void constructor_rejectsNullObservedAt() {
        assertThatNullPointerException()
            .isThrownBy(() -> new CbrOutcome(CbrOutcome.Outcome.SUCCESS, 1.0, null, null));
    }

    @Test
    void adjustConfidence_emaFormula() {
        double result = CbrOutcome.adjustConfidence(0.8, 1.0, 0.2);
        assertThat(result).isCloseTo(0.84, within(0.001));
    }

    @Test
    void adjustConfidence_failure_decreases() {
        double result = CbrOutcome.adjustConfidence(0.8, 0.0, 0.2);
        assertThat(result).isCloseTo(0.64, within(0.001));
    }

    @Test
    void adjustConfidence_partial() {
        double result = CbrOutcome.adjustConfidence(0.8, 0.5, 0.2);
        assertThat(result).isCloseTo(0.74, within(0.001));
    }

    @Test
    void adjustConfidence_nullOldConfidence_treatsAsOne() {
        double result = CbrOutcome.adjustConfidence(null, 0.0, 0.2);
        assertThat(result).isCloseTo(0.8, within(0.001));
    }

    @Test
    void adjustConfidence_convergesToObservedRate() {
        double confidence = 0.5;
        for (int i = 0; i < 50; i++) {
            confidence = CbrOutcome.adjustConfidence(confidence, 1.0, 0.2);
        }
        assertThat(confidence).isCloseTo(1.0, within(0.01));
    }

    @Test
    void defaultLearningRate() {
        assertThat(CbrOutcome.DEFAULT_LEARNING_RATE).isEqualTo(0.2);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrOutcomeTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: FAIL — `CbrOutcome` class not found

- [ ] **Step 3: Create CbrOutcome record**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrOutcome.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.time.Instant;
import java.util.Objects;

public record CbrOutcome(
    Outcome result,
    double successRate,
    String detail,
    Instant observedAt
) {
    public enum Outcome { SUCCESS, PARTIAL, FAILURE }

    public static final double DEFAULT_LEARNING_RATE = 0.2;

    public CbrOutcome {
        Objects.requireNonNull(result, "result must not be null");
        if (successRate < 0.0 || successRate > 1.0)
            throw new IllegalArgumentException("successRate must be in [0,1], got: " + successRate);
        Objects.requireNonNull(observedAt, "observedAt must not be null");
    }

    public static CbrOutcome of(double successRate, String detail, Instant observedAt) {
        Outcome result = successRate == 1.0 ? Outcome.SUCCESS
                       : successRate == 0.0 ? Outcome.FAILURE
                       : Outcome.PARTIAL;
        return new CbrOutcome(result, successRate, detail, observedAt);
    }

    public static double adjustConfidence(Double oldConfidence, double successRate,
                                          double learningRate) {
        double old = oldConfidence != null ? oldConfidence : 1.0;
        return (1.0 - learningRate) * old + learningRate * successRate;
    }
}
```

- [ ] **Step 4: Run CbrOutcome tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrOutcomeTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: ALL PASS

- [ ] **Step 5: Write withOutcome tests**

Add to existing `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrCaseTest.java`:

```java
@Test
void featureVectorCase_withOutcome_preservesFields() {
    var original = new FeatureVectorCbrCase("prob", "sol", null, 0.8,
        Map.of("race", FeatureValue.string("Zerg")));
    CbrCase updated = original.withOutcome("SUCCESS", 0.84);
    assertThat(updated.outcome()).isEqualTo("SUCCESS");
    assertThat(updated.confidence()).isEqualTo(0.84);
    assertThat(updated.problem()).isEqualTo("prob");
    assertThat(updated.solution()).isEqualTo("sol");
    assertThat(updated.features()).isEqualTo(original.features());
}

@Test
void planCase_withOutcome_preservesPlanTrace() {
    var trace = new PlanTrace("bind", "cap", "worker", "SUCCESS", 1, Map.of());
    var original = new PlanCbrCase("prob", "sol", null, null,
        Map.of(), List.of(trace));
    CbrCase updated = original.withOutcome("FAILURE", 0.64);
    assertThat(updated.outcome()).isEqualTo("FAILURE");
    assertThat(updated.confidence()).isEqualTo(0.64);
    assertThat(updated).isInstanceOf(PlanCbrCase.class);
    assertThat(((PlanCbrCase) updated).planTrace()).containsExactly(trace);
}

@Test
void textualCase_withOutcome() {
    var original = new TextualCbrCase("prob", "sol", null, null);
    CbrCase updated = original.withOutcome("PARTIAL", 0.74);
    assertThat(updated.outcome()).isEqualTo("PARTIAL");
    assertThat(updated.confidence()).isEqualTo(0.74);
    assertThat(updated.problem()).isEqualTo("prob");
}
```

- [ ] **Step 6: Add withOutcome abstract method to CbrCase + implementations**

Use `ide_insert_member` on `CbrCase` interface to add:
```java
CbrCase withOutcome(String outcome, Double confidence);
```

Use `ide_insert_member` on each record to add the implementation:

`FeatureVectorCbrCase`:
```java
@Override
public CbrCase withOutcome(String outcome, Double confidence) {
    return new FeatureVectorCbrCase(problem(), solution(), outcome, confidence, features());
}
```

`PlanCbrCase`:
```java
@Override
public CbrCase withOutcome(String outcome, Double confidence) {
    return new PlanCbrCase(problem(), solution(), outcome, confidence, features(), planTrace());
}
```

`TextualCbrCase`:
```java
@Override
public CbrCase withOutcome(String outcome, Double confidence) {
    return new TextualCbrCase(problem(), solution(), outcome, confidence);
}
```

- [ ] **Step 7: Run withOutcome tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrCaseTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: ALL PASS

- [ ] **Step 8: Verify with ide_diagnostics**

Run `ide_diagnostics` on all modified files to check for compilation errors.

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#140): CbrOutcome record + CbrCase.withOutcome abstract method"
```

---

### Task 2: SPI method + NoOp + Bridge + Decorators

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ReactiveCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/BlockingToReactiveCbrBridge.java`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/RerankingCbrCaseMemoryStore.java`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/ReactiveRerankingCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CbrOutcome` from Task 1
- Produces: `CbrCaseMemoryStore.recordOutcome(String caseId, String tenantId, CbrOutcome outcome)`,
  `ReactiveCbrCaseMemoryStore.recordOutcome(String caseId, String tenantId, CbrOutcome outcome) → Uni<Void>`

- [ ] **Step 1: Add recordOutcome to CbrCaseMemoryStore**

Use `ide_insert_member` on `CbrCaseMemoryStore` after `eraseEntity`:
```java
void recordOutcome(String caseId, String tenantId, CbrOutcome outcome);
```

- [ ] **Step 2: Add recordOutcome to ReactiveCbrCaseMemoryStore**

Use `ide_insert_member` on `ReactiveCbrCaseMemoryStore` after `eraseEntity`:
```java
Uni<Void> recordOutcome(String caseId, String tenantId, CbrOutcome outcome);
```

- [ ] **Step 3: Implement NoOp**

Use `ide_insert_member` on `NoOpCbrCaseMemoryStore`:
```java
@Override
public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {}
```

- [ ] **Step 4: Implement BlockingToReactiveCbrBridge**

Use `ide_insert_member` on `BlockingToReactiveCbrBridge`:
```java
@Override
public Uni<Void> recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
    return Uni.createFrom().voidItem()
        .invoke(() -> delegate.recordOutcome(caseId, tenantId, outcome))
        .runSubscriptionOn(Infrastructure.getDefaultWorkerPool());
}
```

- [ ] **Step 5: Implement RerankingCbrCaseMemoryStore (pass-through)**

Use `ide_insert_member` on `RerankingCbrCaseMemoryStore`:
```java
@Override
public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
    delegate.recordOutcome(caseId, tenantId, outcome);
}
```

- [ ] **Step 6: Implement ReactiveRerankingCbrCaseMemoryStore (pass-through)**

Use `ide_insert_member` on `ReactiveRerankingCbrCaseMemoryStore`:
```java
@Override
public Uni<Void> recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
    return delegate.recordOutcome(caseId, tenantId, outcome);
}
```

- [ ] **Step 7: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl memory-api,memory,memory-cbr-crossencoder -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: BUILD SUCCESS (InMemory, Qdrant, JPA will fail — they don't implement yet, but
they're not in this compile scope)

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/ memory/ memory-cbr-crossencoder/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#140): recordOutcome SPI method + NoOp, bridge, decorator implementations"
```

---

### Task 3: Contract tests + InMemory implementation

**Files:**
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CbrCaseMemoryStore.recordOutcome()` from Task 2, `CbrOutcome` from Task 1,
  `CbrCase.withOutcome()` from Task 1
- Produces: 9 contract tests that all backends must pass, working InMemory implementation

- [ ] **Step 1: Add StoredCase.lastOutcomeAt field**

The `StoredCase` record in `InMemoryCbrCaseMemoryStore` needs a `lastOutcomeAt` field
for idempotency. Use `ide_edit_member` on the `StoredCase` record:

```java
private record StoredCase(
        String id, CbrCase cbrCase, String caseType, String entityId, MemoryDomain domain,
        String tenantId, String caseId, Instant storedAt, Instant lastOutcomeAt
) {}
```

Update the `store()` method's `StoredCase` construction to pass `null` for `lastOutcomeAt`:
Find the line creating `new StoredCase(...)` and add `null` as the last argument.

- [ ] **Step 2: Write contract tests**

Add to `CbrCaseMemoryStoreContractTest.java` using `ide_insert_member`:

```java
@Test
void recordOutcome_updatesOutcomeAndConfidence() {
    registerDefaultSchema();
    store().store(new FeatureVectorCbrCase("prob", "sol", null, 0.8,
        Map.of("opponent_race", FeatureValue.string("Zerg"))),
        "game", ENTITY, CBR, TENANT, "case-1");

    store().recordOutcome("case-1", TENANT,
        CbrOutcome.of(1.0, "all nodes succeeded", Instant.now()));

    var results = store().retrieveSimilar(
        new CbrQuery(TENANT, CBR, "game",
            Map.of("opponent_race", FeatureValue.string("Zerg")),
            Map.of(), Map.of(), 10, 0.0, null, null, 0.0,
            RetrievalMode.FEATURE_ONLY, null),
        FeatureVectorCbrCase.class);

    assertThat(results).hasSize(1);
    assertThat(results.getFirst().cbrCase().outcome()).isEqualTo("SUCCESS");
    assertThat(results.getFirst().cbrCase().confidence())
        .isCloseTo(0.84, within(0.001));
}

@Test
void recordOutcome_partialResult() {
    registerDefaultSchema();
    store().store(new FeatureVectorCbrCase("prob", "sol", null, 0.8,
        Map.of("opponent_race", FeatureValue.string("Zerg"))),
        "game", ENTITY, CBR, TENANT, "case-2");

    store().recordOutcome("case-2", TENANT,
        CbrOutcome.of(0.5, "2 of 4", Instant.now()));

    var results = store().retrieveSimilar(
        new CbrQuery(TENANT, CBR, "game",
            Map.of("opponent_race", FeatureValue.string("Zerg")),
            Map.of(), Map.of(), 10, 0.0, null, null, 0.0,
            RetrievalMode.FEATURE_ONLY, null),
        FeatureVectorCbrCase.class);

    assertThat(results.getFirst().cbrCase().outcome()).isEqualTo("PARTIAL");
    assertThat(results.getFirst().cbrCase().confidence())
        .isCloseTo(0.74, within(0.001));
}

@Test
void recordOutcome_failure_decreasesConfidence() {
    registerDefaultSchema();
    store().store(new FeatureVectorCbrCase("prob", "sol", null, 0.8,
        Map.of("opponent_race", FeatureValue.string("Zerg"))),
        "game", ENTITY, CBR, TENANT, "case-3");

    store().recordOutcome("case-3", TENANT,
        CbrOutcome.of(0.0, "all failed", Instant.now()));

    var results = store().retrieveSimilar(
        new CbrQuery(TENANT, CBR, "game",
            Map.of("opponent_race", FeatureValue.string("Zerg")),
            Map.of(), Map.of(), 10, 0.0, null, null, 0.0,
            RetrievalMode.FEATURE_ONLY, null),
        FeatureVectorCbrCase.class);

    assertThat(results.getFirst().cbrCase().confidence())
        .isCloseTo(0.64, within(0.001));
}

@Test
void recordOutcome_multipleOutcomes_emaConverges() {
    registerDefaultSchema();
    store().store(new FeatureVectorCbrCase("prob", "sol", null, 0.5,
        Map.of("opponent_race", FeatureValue.string("Zerg"))),
        "game", ENTITY, CBR, TENANT, "case-4");

    Instant base = Instant.parse("2026-07-13T10:00:00Z");
    for (int i = 0; i < 5; i++) {
        store().recordOutcome("case-4", TENANT,
            CbrOutcome.of(1.0, null, base.plusSeconds(i + 1)));
    }

    var results = store().retrieveSimilar(
        new CbrQuery(TENANT, CBR, "game",
            Map.of("opponent_race", FeatureValue.string("Zerg")),
            Map.of(), Map.of(), 10, 0.0, null, null, 0.0,
            RetrievalMode.FEATURE_ONLY, null),
        FeatureVectorCbrCase.class);

    assertThat(results.getFirst().cbrCase().confidence()).isGreaterThan(0.8);
}

@Test
void recordOutcome_nullInitialConfidence_treatsAsOne() {
    registerDefaultSchema();
    store().store(new FeatureVectorCbrCase("prob", "sol", null, null,
        Map.of("opponent_race", FeatureValue.string("Zerg"))),
        "game", ENTITY, CBR, TENANT, "case-5");

    store().recordOutcome("case-5", TENANT,
        CbrOutcome.of(0.0, null, Instant.now()));

    var results = store().retrieveSimilar(
        new CbrQuery(TENANT, CBR, "game",
            Map.of("opponent_race", FeatureValue.string("Zerg")),
            Map.of(), Map.of(), 10, 0.0, null, null, 0.0,
            RetrievalMode.FEATURE_ONLY, null),
        FeatureVectorCbrCase.class);

    assertThat(results.getFirst().cbrCase().confidence())
        .isCloseTo(0.8, within(0.001));
}

@Test
void recordOutcome_unknownCaseId_silentlyIgnored() {
    registerDefaultSchema();
    assertThatCode(() -> store().recordOutcome("nonexistent", TENANT,
        CbrOutcome.of(1.0, null, Instant.now())))
        .doesNotThrowAnyException();
}

@Test
void recordOutcome_preservesOtherFields() {
    registerDefaultSchema();
    var features = Map.of("opponent_race", FeatureValue.string("Zerg"),
                          "army_size_ratio", FeatureValue.number(0.7));
    store().store(new FeatureVectorCbrCase("my problem", "my solution", null, 0.8,
        features), "game", ENTITY, CBR, TENANT, "case-7");

    store().recordOutcome("case-7", TENANT,
        CbrOutcome.of(1.0, "ok", Instant.now()));

    var results = store().retrieveSimilar(
        new CbrQuery(TENANT, CBR, "game",
            Map.of("opponent_race", FeatureValue.string("Zerg")),
            Map.of(), Map.of(), 10, 0.0, null, null, 0.0,
            RetrievalMode.FEATURE_ONLY, null),
        FeatureVectorCbrCase.class);

    var c = results.getFirst().cbrCase();
    assertThat(c.problem()).isEqualTo("my problem");
    assertThat(c.solution()).isEqualTo("my solution");
    assertThat(c.features()).containsEntry("opponent_race", FeatureValue.string("Zerg"));
    assertThat(c.features()).containsEntry("army_size_ratio", FeatureValue.number(0.7));
}

@Test
void recordOutcome_withDetail_doesNotCorruptCase() {
    registerDefaultSchema();
    store().store(new FeatureVectorCbrCase("prob", "sol", null, 0.8,
        Map.of("opponent_race", FeatureValue.string("Zerg"))),
        "game", ENTITY, CBR, TENANT, "case-8");

    store().recordOutcome("case-8", TENANT,
        CbrOutcome.of(0.75, "3/4 nodes succeeded, 1 FAILED: node-xyz", Instant.now()));

    var results = store().retrieveSimilar(
        new CbrQuery(TENANT, CBR, "game",
            Map.of("opponent_race", FeatureValue.string("Zerg")),
            Map.of(), Map.of(), 10, 0.0, null, null, 0.0,
            RetrievalMode.FEATURE_ONLY, null),
        FeatureVectorCbrCase.class);

    assertThat(results.getFirst().cbrCase().outcome()).isEqualTo("PARTIAL");
    assertThat(results.getFirst().cbrCase().confidence())
        .isCloseTo(0.79, within(0.001));
}

@Test
void recordOutcome_duplicateObservedAt_idempotent() {
    registerDefaultSchema();
    store().store(new FeatureVectorCbrCase("prob", "sol", null, 0.8,
        Map.of("opponent_race", FeatureValue.string("Zerg"))),
        "game", ENTITY, CBR, TENANT, "case-9");

    Instant observed = Instant.parse("2026-07-13T10:00:00Z");
    store().recordOutcome("case-9", TENANT,
        CbrOutcome.of(1.0, null, observed));
    store().recordOutcome("case-9", TENANT,
        CbrOutcome.of(1.0, null, observed));

    var results = store().retrieveSimilar(
        new CbrQuery(TENANT, CBR, "game",
            Map.of("opponent_race", FeatureValue.string("Zerg")),
            Map.of(), Map.of(), 10, 0.0, null, null, 0.0,
            RetrievalMode.FEATURE_ONLY, null),
        FeatureVectorCbrCase.class);

    assertThat(results.getFirst().cbrCase().confidence())
        .isCloseTo(0.84, within(0.001));
}
```

- [ ] **Step 3: Run contract tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -Dtest=InMemoryCbrCaseMemoryStoreTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: FAIL — `recordOutcome` not implemented in InMemoryCbrCaseMemoryStore

- [ ] **Step 4: Implement InMemoryCbrCaseMemoryStore.recordOutcome**

Use `ide_insert_member` on `InMemoryCbrCaseMemoryStore` after `eraseEntity`:

```java
@Override
public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
    for (int i = 0; i < cases.size(); i++) {
        StoredCase stored = cases.get(i);
        if (caseId.equals(stored.caseId()) && tenantId.equals(stored.tenantId())) {
            if (stored.lastOutcomeAt() != null
                    && !outcome.observedAt().isAfter(stored.lastOutcomeAt())) {
                return;
            }
            double newConfidence = CbrOutcome.adjustConfidence(
                stored.cbrCase().confidence(), outcome.successRate(),
                CbrOutcome.DEFAULT_LEARNING_RATE);
            CbrCase updated = stored.cbrCase().withOutcome(
                outcome.result().name(), newConfidence);
            cases.set(i, new StoredCase(stored.id(), updated, stored.caseType(),
                stored.entityId(), stored.domain(), stored.tenantId(),
                stored.caseId(), stored.storedAt(), outcome.observedAt()));
            return;
        }
    }
}
```

- [ ] **Step 5: Run contract tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -Dtest=InMemoryCbrCaseMemoryStoreTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-testing/ memory-cbr-inmem/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#140): contract tests + InMemory recordOutcome implementation"
```

---

### Task 4: Qdrant implementation

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CbrOutcome` from Task 1, `CbrPointBuilder.pointId()` (existing),
  `CbrCollectionManager.collectionName()` (existing)
- Produces: Working Qdrant `recordOutcome` — iterates registered schemas, O(1) lookup
  via deterministic UUID, payload update with idempotency guard

- [ ] **Step 1: Implement QdrantCbrCaseMemoryStore.recordOutcome**

Use `ide_insert_member` on `QdrantCbrCaseMemoryStore` after `eraseEntity`:

```java
@Override
public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
    for (String caseType : schemas.keySet()) {
        String collection = collectionManager.collectionName(caseType);
        try {
            if (!collectionManager.client().collectionExistsAsync(collection).get()) {
                continue;
            }
            UUID pointUuid = CbrPointBuilder.pointId(tenantId, caseType, caseId);
            var pointId = PointIdFactory.id(pointUuid);

            var points = collectionManager.client()
                .getAsync(collection, List.of(pointId), true, false, null).get();
            if (points.isEmpty()) continue;

            var payload = points.getFirst().getPayloadMap();

            String existingLastOutcome = extractString(payload, "last_outcome_at");
            if (existingLastOutcome != null) {
                Instant existingInstant = Instant.parse(existingLastOutcome);
                if (!outcome.observedAt().isAfter(existingInstant)) return;
            }

            Double oldConfidence = extractDouble(payload, "confidence");
            double newConfidence = CbrOutcome.adjustConfidence(
                oldConfidence, outcome.successRate(), CbrOutcome.DEFAULT_LEARNING_RATE);

            Map<String, Value> updates = new HashMap<>();
            updates.put("outcome", ValueFactory.value(outcome.result().name()));
            updates.put("confidence", ValueFactory.value(newConfidence));
            updates.put("last_outcome_at", ValueFactory.value(outcome.observedAt().toString()));
            if (outcome.detail() != null) {
                updates.put("outcome_detail", ValueFactory.value(outcome.detail()));
            }

            var selector = PointsSelector.newBuilder()
                .setPoints(PointsIdsList.newBuilder().addIds(pointId).build())
                .build();
            collectionManager.client()
                .setPayloadAsync(collection, updates, selector, null, null).get();
            return;
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new RuntimeException("Interrupted during recordOutcome", e);
        } catch (ExecutionException e) {
            throw new RuntimeException("recordOutcome failed", e.getCause());
        }
    }
}
```

Note: Exact Qdrant client API may need adjustment — verify `getAsync` and
`setPayloadAsync` signatures against the actual client version. Check imports:
`io.qdrant.client.grpc.Points.PointsSelector`, `io.qdrant.client.grpc.Points.PointsIdsList`,
`io.qdrant.client.PointIdFactory`, `io.qdrant.client.ValueFactory`.

- [ ] **Step 2: Run Qdrant contract tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -Dtest=QdrantCbrCaseMemoryStoreTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: ALL PASS (requires Testcontainers Qdrant — Docker must be running)

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-qdrant/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#140): Qdrant recordOutcome — deterministic UUID lookup + payload update"
```

---

### Task 5: JPA implementation + Flyway migration

**Files:**
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/CbrCaseEntity.java`
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java`
- Create: `memory-cbr-jpa/src/main/resources/db/cbr/migration/V2__add_outcome_detail_columns.sql`

**Interfaces:**
- Consumes: `CbrOutcome` from Task 1
- Produces: Working JPA `recordOutcome` with new columns

- [ ] **Step 1: Create Flyway migration**

Create `memory-cbr-jpa/src/main/resources/db/cbr/migration/V2__add_outcome_detail_columns.sql`:

```sql
ALTER TABLE cbr_case ADD COLUMN outcome_detail TEXT;
ALTER TABLE cbr_case ADD COLUMN last_outcome_at TIMESTAMP WITH TIME ZONE;
```

- [ ] **Step 2: Add columns to CbrCaseEntity**

Use `ide_insert_member` on `CbrCaseEntity` after `storedAt`:

```java
@Column(name = "outcome_detail", columnDefinition = "TEXT")
public String outcomeDetail;

@Column(name = "last_outcome_at")
public Instant lastOutcomeAt;
```

- [ ] **Step 3: Implement JpaCbrCaseMemoryStore.recordOutcome**

Use `ide_insert_member` on `JpaCbrCaseMemoryStore` after `eraseEntity`:

```java
@Override
public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
    var results = em.createQuery(
            "SELECT c FROM CbrCaseEntity c WHERE c.caseId = :caseId AND c.tenantId = :tenantId",
            CbrCaseEntity.class)
        .setParameter("caseId", caseId)
        .setParameter("tenantId", tenantId)
        .getResultList();

    if (results.isEmpty()) return;

    CbrCaseEntity entity = results.getFirst();

    if (entity.lastOutcomeAt != null
            && !outcome.observedAt().isAfter(entity.lastOutcomeAt)) {
        return;
    }

    double newConfidence = CbrOutcome.adjustConfidence(
        entity.confidence, outcome.successRate(), CbrOutcome.DEFAULT_LEARNING_RATE);

    entity.outcome = outcome.result().name();
    entity.confidence = newConfidence;
    entity.outcomeDetail = outcome.detail();
    entity.lastOutcomeAt = outcome.observedAt();

    em.merge(entity);
}
```

- [ ] **Step 4: Run JPA contract tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-jpa -Dtest=JpaCbrCaseMemoryStoreTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-cbr-jpa/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#140): JPA recordOutcome + V2 migration (outcome_detail, last_outcome_at)"
```

---

### Task 6: CloudEvent consumer + full build

**Files:**
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/CbrOutcomeConsumer.java`
- Modify: `memory/pom.xml` (add casehub-desiredstate-api dependency)
- Test: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/CbrOutcomeConsumerTest.java`

**Interfaces:**
- Consumes: `CbrCaseMemoryStore.recordOutcome()` from Task 2,
  `CbrOutcome.of()` from Task 1,
  `CbrOutcomeData` and `CbrEventTypes` from casehub-desiredstate-api
- Produces: CDI bean that consumes `io.casehub.cbr.outcome` CloudEvents

- [ ] **Step 1: Write consumer test**

Create `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/CbrOutcomeConsumerTest.java`:

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.desiredstate.api.CbrOutcomeData;
import io.casehub.desiredstate.api.CbrPath;
import io.casehub.neocortex.memory.cbr.CbrOutcome;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class CbrOutcomeConsumerTest {

    @Test
    void onCbrOutcome_delegatesToStore() {
        var recorded = new ArrayList<RecordedOutcome>();
        var consumer = new CbrOutcomeConsumer(new CapturingStore(recorded));

        var data = new CbrOutcomeData(
            "tenant-1", "case-42", CbrPath.FAULT,
            Map.of("node-a", "SUCCEEDED", "node-b", "FAILED"),
            1, 1, 2, 0.5,
            Instant.parse("2026-07-13T09:00:00Z"),
            Instant.parse("2026-07-13T10:00:00Z"));

        consumer.onCbrOutcome(data);

        assertThat(recorded).hasSize(1);
        var r = recorded.getFirst();
        assertThat(r.caseId).isEqualTo("case-42");
        assertThat(r.tenantId).isEqualTo("tenant-1");
        assertThat(r.outcome.result()).isEqualTo(CbrOutcome.Outcome.PARTIAL);
        assertThat(r.outcome.successRate()).isEqualTo(0.5);
        assertThat(r.outcome.observedAt()).isEqualTo(Instant.parse("2026-07-13T10:00:00Z"));
        assertThat(r.outcome.detail()).contains("node-a");
    }

    record RecordedOutcome(String caseId, String tenantId, CbrOutcome outcome) {}

    static class CapturingStore extends NoOpCbrCaseMemoryStore {
        final List<RecordedOutcome> recorded;

        CapturingStore(List<RecordedOutcome> recorded) { this.recorded = recorded; }

        @Override
        public void recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
            recorded.add(new RecordedOutcome(caseId, tenantId, outcome));
        }
    }
}
```

- [ ] **Step 2: Add casehub-desiredstate-api dependency to memory/pom.xml**

Add to `memory/pom.xml` dependencies:

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-desiredstate-api</artifactId>
</dependency>
```

Also add version management in the parent `pom.xml` `<dependencyManagement>` if not
already present.

- [ ] **Step 3: Implement CbrOutcomeConsumer**

Create `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/CbrOutcomeConsumer.java`:

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.desiredstate.api.CbrOutcomeData;
import io.casehub.neocortex.memory.cbr.CbrCaseMemoryStore;
import io.casehub.neocortex.memory.cbr.CbrOutcome;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

import java.util.Map;
import java.util.stream.Collectors;

@ApplicationScoped
public class CbrOutcomeConsumer {

    private final CbrCaseMemoryStore store;

    @Inject
    public CbrOutcomeConsumer(CbrCaseMemoryStore store) {
        this.store = store;
    }

    public void onCbrOutcome(CbrOutcomeData data) {
        CbrOutcome outcome = CbrOutcome.of(
            data.successRate(),
            summarize(data.nodeOutcomes()),
            data.observedAt());
        store.recordOutcome(data.sourceId(), data.tenancyId(), outcome);
    }

    private static String summarize(Map<String, String> nodeOutcomes) {
        if (nodeOutcomes == null || nodeOutcomes.isEmpty()) return null;
        return nodeOutcomes.entrySet().stream()
            .map(e -> e.getKey() + "=" + e.getValue())
            .collect(Collectors.joining(", "));
    }
}
```

Note: The consumer's CDI event observation mechanism (`@Observes` with CloudEvent
routing) depends on how the platform dispatches CloudEvents to CDI beans. The
`onCbrOutcome` method is public so it can be called directly or wired via whatever
event bridge the platform uses. The exact `@Observes` qualifier is deferred until
the platform's CloudEvent→CDI adapter is available. The unit test validates the
mapping logic directly.

- [ ] **Step 4: Run consumer tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=CbrOutcomeConsumerTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: ALL PASS

- [ ] **Step 5: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: BUILD SUCCESS — all modules compile and all tests pass

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory/ pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#140): CloudEvent consumer for io.casehub.cbr.outcome + desiredstate-api dependency"
```

---

### Task 7: CLAUDE.md update + follow-on issue

**Files:**
- Modify: `CLAUDE.md` (update memory-api and memory module descriptions)

**Interfaces:**
- Consumes: All previous tasks complete
- Produces: Updated documentation, follow-on issue filed

- [ ] **Step 1: Update CLAUDE.md module descriptions**

Update the `memory-api` description to mention CbrOutcome and recordOutcome SPI.
Update the `memory` description to mention CbrOutcomeConsumer.

- [ ] **Step 2: File follow-on issue for CloudEvent routing wiring**

The consumer exists but needs wiring to the platform's CloudEvent→CDI adapter
(`Ganglion` / `@Observes` qualifier). File:

```
Title: feat: wire CbrOutcomeConsumer to platform CloudEvent routing
Body: CbrOutcomeConsumer.onCbrOutcome(CbrOutcomeData) is implemented but needs
wiring to the platform's CloudEvent dispatch infrastructure (Ganglion/RAS).
The consumer bean exists in memory/ — it needs a @Observes qualifier or
Ganglion registration to receive io.casehub.cbr.outcome events.

Depends on: the platform CloudEvent→CDI adapter being available in neocortex's
classpath (casehub-ras-api or casehub-qhorus-api).
```

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "docs(#140): update CLAUDE.md — CbrOutcome, recordOutcome SPI, CbrOutcomeConsumer"
```
