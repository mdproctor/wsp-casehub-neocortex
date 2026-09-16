# Cognitive S-Batch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #340 — corroboration-gated graduation
**Issue group:** #340, #342, #344

**Goal:** Three independent cognitive subsystem enhancements: prevent premature episodic-to-semantic promotion (#340), trigger consolidation on accumulated significance (#342), and reduce redundancy in CBR retrieval via MMR diversity (#344).

**Architecture:** Each issue is self-contained with no cross-dependencies. #340 widens the GraduationScorer SPI with a GraduationContext record and adds Subject-based corroboration queries to ExperienceConsolidationPhase. #342 adds a SignificanceAccumulator CDI bean that observes ExperienceRecorded events and triggers consolidation when a configurable threshold is crossed. #344 adds a DiversityCbrCaseMemoryStore @Decorator at Priority(55) that applies MMR greedy selection to reduce result redundancy.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI, JUnit 5, InMemoryMemoryStore, InMemoryMindMapStore, InMemoryCbrCaseMemoryStore

## Global Constraints

- Java 21 source level on Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All commits reference an issue: `Refs #N` or `Closes #N`
- No new modules — all changes fit existing modules
- Pre-release: SPI changes are acceptable without backward compatibility shims

---

## Batch 1: Corroboration-Gated Graduation (#340)

### Task 1: GraduationContext record and GraduationScorer SPI change

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationContext.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationScorer.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorer.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationConfig.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhaseTest.java` (fix compilation after SPI change)
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorerTest.java`

**Interfaces:**
- Produces: `GraduationContext(int corroboratingCount, String tenantId)` record used by Task 2
- Produces: `GraduationScorer.score(Memory, GraduationContext)` signature used by Task 2
- Produces: `ExperienceConsolidationConfig.minCorroboration()` (default 3) used by Task 2

- [ ] **Step 1: Write DefaultGraduationScorerTest**

Create the test file. Tests verify the scorer gates on corroboration count and delegates to confidence when threshold met.

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.Subject;
import io.casehub.neocortex.memory.experience.GraduationContext;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class DefaultGraduationScorerTest {

    private final DefaultGraduationScorer scorer = new DefaultGraduationScorer(3);

    private Memory memory(double confidence) {
        return new Memory("m1", Subject.of("person", "alice"),
            new MemoryDomain("experience"), "t1", null,
            "observation text", Map.of(), Instant.now(),
            Confidence.unknown(confidence), null, null, null, null, Set.of());
    }

    @Test
    void belowCorroborationThreshold_returnsZero() {
        assertEquals(0.0, scorer.score(memory(0.9),
            new GraduationContext(2, "t1")));
    }

    @Test
    void atCorroborationThreshold_returnsConfidence() {
        assertEquals(0.9, scorer.score(memory(0.9),
            new GraduationContext(3, "t1")));
    }

    @Test
    void aboveCorroborationThreshold_returnsConfidence() {
        assertEquals(0.8, scorer.score(memory(0.8),
            new GraduationContext(5, "t1")));
    }

    @Test
    void nullConfidence_returnsDefaultWhenCorroborated() {
        var mem = new Memory("m1", Subject.of("person", "alice"),
            new MemoryDomain("experience"), "t1", null,
            "text", Map.of(), Instant.now(),
            null, null, null, null, null, Set.of());
        assertEquals(0.5, scorer.score(mem, new GraduationContext(3, "t1")));
    }

    @Test
    void zeroCorroboration_returnsZero() {
        assertEquals(0.0, scorer.score(memory(0.9),
            new GraduationContext(0, "t1")));
    }
}
```

- [ ] **Step 2: Run test — verify compilation fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DefaultGraduationScorerTest -am`
Expected: Compilation error — `GraduationContext` does not exist, `score(Memory, GraduationContext)` does not match SPI.

- [ ] **Step 3: Create GraduationContext record**

```java
package io.casehub.neocortex.memory.experience;

public record GraduationContext(int corroboratingCount, String tenantId) {}
```

- [ ] **Step 4: Change GraduationScorer signature**

Use `ide_replace_member` on `GraduationScorer` to change the method signature:

```java
@FunctionalInterface
public interface GraduationScorer {
    double score(Memory memory, GraduationContext context);
}
```

- [ ] **Step 5: Add minCorroboration to ExperienceConsolidationConfig**

Use `ide_edit_member` to add:

```java
@WithDefault("3") int minCorroboration();
```

- [ ] **Step 6: Update DefaultGraduationScorer**

Replace the entire class body. Add a `minCorroboration` field, package-private constructor for tests, CDI constructor using `Instance<ExperienceConsolidationConfig>`:

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.experience.GraduationContext;
import io.casehub.neocortex.memory.experience.GraduationScorer;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

@DefaultBean
@ApplicationScoped
public class DefaultGraduationScorer implements GraduationScorer {

    private final int minCorroboration;

    @Inject
    DefaultGraduationScorer(Instance<ExperienceConsolidationConfig> config) {
        var c = config.isResolvable() ? config.get() : null;
        this.minCorroboration = c != null ? c.minCorroboration() : 3;
    }

    DefaultGraduationScorer(int minCorroboration) {
        this.minCorroboration = minCorroboration;
    }

    DefaultGraduationScorer() { this(3); }

    @Override
    public double score(Memory memory, GraduationContext context) {
        if (context.corroboratingCount() < minCorroboration) return 0.0;
        if (memory.confidence() != null) {
            return memory.confidence().value();
        }
        return 0.5;
    }
}
```

- [ ] **Step 7: Fix ExperienceConsolidationPhaseTest compilation**

The existing test has a lambda `GraduationScorer failOnFirst = m -> {...}` on line 147. Change it to accept two parameters:

```java
GraduationScorer failOnFirst = (m, ctx) -> {
    if (m.text().equals("good event")) throw new RuntimeException("scorer failed");
    return 0.8;
};
```

Also update `setUp()` to pass a `GraduationContext` where the scorer is called. Since `ExperienceConsolidationPhase` calls the scorer internally, the phase needs updating first (Task 2). For now, make the phase pass a stub context. Temporarily update `ExperienceConsolidationPhase.run()` to pass `new GraduationContext(Integer.MAX_VALUE, tenantId)` so existing tests pass — Task 2 replaces this with the real batch-query logic.

- [ ] **Step 8: Run tests — verify scorer tests pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DefaultGraduationScorerTest -am`
Expected: All 5 tests PASS.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExperienceConsolidationPhaseTest -am`
Expected: All existing tests PASS (stub context means no behavior change yet).

- [ ] **Step 9: Commit**

```bash
git add memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationContext.java \
  memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationScorer.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorer.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationConfig.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhase.java \
  mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorerTest.java \
  mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhaseTest.java
git commit -m "feat: widen GraduationScorer SPI with GraduationContext, add corroboration gate to DefaultGraduationScorer Refs #340"
```

### Task 2: Batch-query corroboration in ExperienceConsolidationPhase

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhaseTest.java`

**Interfaces:**
- Consumes: `GraduationContext(int corroboratingCount, String tenantId)` from Task 1
- Consumes: `GraduationScorer.score(Memory, GraduationContext)` from Task 1
- Consumes: `ExperienceConsolidationConfig.minCorroboration()` from Task 1
- Consumes: `MemoryQuery.forSubject(Subject, MemoryDomain, String)` from memory-api
- Produces: Corroboration-gated graduation behavior (no downstream consumers)

- [ ] **Step 1: Write corroboration tests in ExperienceConsolidationPhaseTest**

Add four new tests:

```java
@Test
void singleObservation_notGraduated_whenCorroborationRequired() {
    storeExperience("a1", "observation", "Bob looks worried",
        Map.of("subject", "Bob"), 0.8);

    var corroboratingPhase = new ExperienceConsolidationPhase(
        memoryStore, mindMapStore, new DefaultGraduationScorer(3),
        classifier, 0.5, 20);
    corroboratingPhase.run(TENANT, List.of());

    assertEquals(0, cognitiveNodes().size());
}

@Test
void threeConvergingObservations_graduates() {
    storeExperience("a1", "observation", "Bob looks worried",
        Map.of("subject", "Bob"), 0.8);
    storeExperience("a1", "observation", "Bob seems stressed",
        Map.of("subject", "Bob"), 0.7);
    storeExperience("a1", "observation", "Bob is anxious",
        Map.of("subject", "Bob"), 0.9);

    var corroboratingPhase = new ExperienceConsolidationPhase(
        memoryStore, mindMapStore, new DefaultGraduationScorer(3),
        classifier, 0.5, 20);
    corroboratingPhase.run(TENANT, List.of());

    assertEquals(3, cognitiveNodes().size());
}

@Test
void differentSubjects_doNotCorroborate() {
    storeExperience("a1", "observation", "Bob looks worried",
        Map.of("subject", "Bob"), 0.8);
    storeExperience("a1", "observation", "Alice is happy",
        Map.of("subject", "Alice"), 0.8);
    storeExperience("a1", "observation", "Charlie is tired",
        Map.of("subject", "Charlie"), 0.8);

    var corroboratingPhase = new ExperienceConsolidationPhase(
        memoryStore, mindMapStore, new DefaultGraduationScorer(3),
        classifier, 0.5, 20);
    corroboratingPhase.run(TENANT, List.of());

    assertEquals(0, cognitiveNodes().size());
}

@Test
void retroactiveCorroboration_graduatesOnSubsequentPass() {
    storeExperience("a1", "observation", "Bob event 1",
        Map.of("subject", "Bob"), 0.8);
    storeExperience("a1", "observation", "Bob event 2",
        Map.of("subject", "Bob"), 0.8);

    var corroboratingPhase = new ExperienceConsolidationPhase(
        memoryStore, mindMapStore, new DefaultGraduationScorer(3),
        classifier, 0.5, 20);
    corroboratingPhase.run(TENANT, List.of());
    assertEquals(0, cognitiveNodes().size());

    storeExperience("a1", "observation", "Bob event 3",
        Map.of("subject", "Bob"), 0.8);

    var freshPhase = new ExperienceConsolidationPhase(
        memoryStore, mindMapStore, new DefaultGraduationScorer(3),
        classifier, 0.5, 20);
    freshPhase.run(TENANT, List.of());
    assertEquals(3, cognitiveNodes().size());
}
```

- [ ] **Step 2: Run tests — verify new tests fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExperienceConsolidationPhaseTest -am`
Expected: New corroboration tests FAIL (phase passes stub context with `Integer.MAX_VALUE`).

- [ ] **Step 3: Implement batch-query corroboration in ExperienceConsolidationPhase**

Replace the stub `GraduationContext` logic in `run()`. After scanning memories, extract unique Subjects, query corroboration counts, then build and cache a `Map<Subject, GraduationContext>`:

In `ExperienceConsolidationPhase`:
1. Add `minCorroboration` field (from config, default 3)
2. Add private method `buildCorroborationMap(List<Memory> experiences, String tenantId)`:

```java
private Map<Subject, GraduationContext> buildCorroborationMap(
        List<Memory> experiences, String tenantId) {
    Map<Subject, GraduationContext> map = new HashMap<>();
    for (Memory m : experiences) {
        Subject subject = m.subject();
        if (map.containsKey(subject)) continue;
        var query = MemoryQuery.forSubject(subject,
                ExperienceEvents.DOMAIN, tenantId)
            .withLimit(minCorroboration);
        int count = memoryStore.query(query).size();
        map.put(subject, new GraduationContext(count, tenantId));
    }
    return map;
}
```

3. In `run()`, after scanning and before the scoring loop, call `buildCorroborationMap()`.
4. In the scoring loop, replace the stub context with `corroborationMap.get(memory.subject())`.
5. Update both constructors to accept/read `minCorroboration`.

- [ ] **Step 4: Run all tests — verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExperienceConsolidationPhaseTest -am`
Expected: All tests PASS (existing + new corroboration tests).

Note: Existing `graduatedEvent_producesCognitiveNode` uses the old `DefaultGraduationScorer()` constructor (minCorroboration=3). With only 1 memory stored, `corroboratingCount` will be 1 < 3, so this test will FAIL. Fix by changing the `setUp()` scorer to `new DefaultGraduationScorer(1)` (threshold 1 = no corroboration gate), or store 3 experiences in that test.

The cleanest fix: change `setUp()` to use `new DefaultGraduationScorer(1)` so the existing tests verify pre-corroboration behavior. The new tests explicitly use `new DefaultGraduationScorer(3)`.

- [ ] **Step 5: Build the full module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -am`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhase.java \
  mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhaseTest.java
git commit -m "feat: batch-query Subject corroboration in ExperienceConsolidationPhase Closes #340"
```

---

## Batch 2: Significance-Threshold Trigger (#342)

### Task 3: SignificanceExtractor SPI and SignificanceAccumulator

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceExtractor.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultSignificanceExtractor.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceSnapshot.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceAccumulator.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceAccumulatorTest.java`

**Interfaces:**
- Consumes: `ExperienceRecorded(ExperienceEvent event, String memoryId)` from memory-api
- Consumes: `ConsolidationScheduler.consolidateNow(String tenantId)` from same module
- Produces: `SignificanceExtractor.extract(ExperienceRecorded)` — @FunctionalInterface SPI
- Produces: `SignificanceAccumulator.swapAndReset()` → `SignificanceSnapshot` — used by Task 4
- Produces: `SignificanceSnapshot(Map<String, Double> perTenant)` — result record

- [ ] **Step 1: Write SignificanceAccumulatorTest**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.memory.experience.ExperienceRecorded;
import io.casehub.neocortex.memory.experience.Observation;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class SignificanceAccumulatorTest {

    private List<String> consolidatedTenants;
    private SignificanceAccumulator accumulator;

    @BeforeEach
    void setUp() {
        consolidatedTenants = new ArrayList<>();
        accumulator = new SignificanceAccumulator(
            e -> 1.0, 3.0, consolidatedTenants::add);
    }

    private ExperienceRecorded event(String tenantId) {
        return new ExperienceRecorded(
            new Observation("agent-1", tenantId, null, "turn-1",
                Instant.now(), "something happened", null, Map.of()),
            "mem-1");
    }

    @Test
    void belowThreshold_doesNotTrigger() {
        accumulator.onExperienceRecorded(event("t1"));
        accumulator.onExperienceRecorded(event("t1"));
        assertThat(consolidatedTenants).isEmpty();
    }

    @Test
    void atThreshold_triggers() {
        accumulator.onExperienceRecorded(event("t1"));
        accumulator.onExperienceRecorded(event("t1"));
        accumulator.onExperienceRecorded(event("t1"));
        assertThat(consolidatedTenants).containsExactly("t1");
    }

    @Test
    void perTenantAccumulation_independent() {
        accumulator.onExperienceRecorded(event("t1"));
        accumulator.onExperienceRecorded(event("t1"));
        accumulator.onExperienceRecorded(event("t2"));
        assertThat(consolidatedTenants).isEmpty();

        accumulator.onExperienceRecorded(event("t1"));
        assertThat(consolidatedTenants).containsExactly("t1");
    }

    @Test
    void swapAndReset_clearsCounters() {
        accumulator.onExperienceRecorded(event("t1"));
        accumulator.onExperienceRecorded(event("t1"));

        SignificanceSnapshot snapshot = accumulator.swapAndReset();
        assertThat(snapshot.perTenant()).containsEntry("t1", 2.0);

        accumulator.onExperienceRecorded(event("t1"));
        assertThat(consolidatedTenants).isEmpty();
    }

    @Test
    void customExtractor_affectsAccumulation() {
        var weighted = new SignificanceAccumulator(
            e -> 5.0, 10.0, consolidatedTenants::add);
        weighted.onExperienceRecorded(event("t1"));
        assertThat(consolidatedTenants).isEmpty();
        weighted.onExperienceRecorded(event("t1"));
        assertThat(consolidatedTenants).containsExactly("t1");
    }

    @Test
    void eventsDuringReset_countTowardNextCycle() {
        accumulator.onExperienceRecorded(event("t1"));
        accumulator.onExperienceRecorded(event("t1"));
        accumulator.swapAndReset();

        accumulator.onExperienceRecorded(event("t1"));
        accumulator.onExperienceRecorded(event("t1"));
        assertThat(consolidatedTenants).isEmpty();

        accumulator.onExperienceRecorded(event("t1"));
        assertThat(consolidatedTenants).containsExactly("t1");
    }
}
```

- [ ] **Step 2: Run test — verify compilation fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SignificanceAccumulatorTest -am`
Expected: Compilation error — classes do not exist.

- [ ] **Step 3: Create SignificanceExtractor, DefaultSignificanceExtractor, SignificanceSnapshot**

`SignificanceExtractor.java`:
```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.memory.experience.ExperienceRecorded;

@FunctionalInterface
public interface SignificanceExtractor {
    double extract(ExperienceRecorded event);
}
```

`DefaultSignificanceExtractor.java`:
```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.memory.experience.ExperienceRecorded;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;

@DefaultBean
@ApplicationScoped
public class DefaultSignificanceExtractor implements SignificanceExtractor {
    @Override
    public double extract(ExperienceRecorded event) { return 1.0; }
}
```

`SignificanceSnapshot.java`:
```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import java.util.Map;

public record SignificanceSnapshot(Map<String, Double> perTenant) {
    public SignificanceSnapshot { perTenant = Map.copyOf(perTenant); }
    public static final SignificanceSnapshot EMPTY = new SignificanceSnapshot(Map.of());
}
```

- [ ] **Step 4: Create SignificanceAccumulator**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.memory.experience.ExperienceRecorded;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.util.HashMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.DoubleAdder;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.function.Consumer;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class SignificanceAccumulator {

    private static final Logger LOG = Logger.getLogger(
        SignificanceAccumulator.class.getName());

    private volatile ConcurrentHashMap<String, DoubleAdder> perTenant =
        new ConcurrentHashMap<>();
    private final SignificanceExtractor extractor;
    private final double threshold;
    private final Consumer<String> triggerAction;
    private final ExecutorService triggerExecutor;

    @Inject
    SignificanceAccumulator(Instance<SignificanceExtractor> extractor,
                            Instance<ConsolidationScheduler> scheduler,
                            @ConfigProperty(
                                name = "casehub.consolidation.significance-threshold",
                                defaultValue = "10.0") double threshold) {
        this(extractor.isResolvable() ? extractor.get() : e -> 1.0,
             threshold,
             scheduler.isResolvable()
                 ? tenantId -> scheduler.get().consolidateNow(tenantId)
                 : tenantId -> {});
    }

    SignificanceAccumulator(SignificanceExtractor extractor,
                            double threshold,
                            Consumer<String> triggerAction) {
        this.extractor = extractor;
        this.threshold = threshold;
        this.triggerAction = triggerAction;
        this.triggerExecutor = Executors.newSingleThreadExecutor(r -> {
            Thread t = new Thread(r, "significance-trigger");
            t.setDaemon(true);
            return t;
        });
    }

    void onExperienceRecorded(@Observes ExperienceRecorded event) {
        double significance = extractor.extract(event);
        String tenantId = event.event().tenantId();
        DoubleAdder adder = perTenant.computeIfAbsent(
            tenantId, k -> new DoubleAdder());
        adder.add(significance);
        if (adder.sum() >= threshold) {
            triggerExecutor.submit(() -> {
                try {
                    triggerAction.accept(tenantId);
                } catch (Exception e) {
                    LOG.log(Level.WARNING,
                        "Significance-triggered consolidation failed for "
                        + tenantId, e);
                }
            });
        }
    }

    public SignificanceSnapshot swapAndReset() {
        var old = perTenant;
        perTenant = new ConcurrentHashMap<>();
        var snapshot = new HashMap<String, Double>();
        old.forEach((k, v) -> snapshot.put(k, v.sum()));
        return new SignificanceSnapshot(snapshot);
    }
}
```

- [ ] **Step 5: Run tests — verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SignificanceAccumulatorTest -am`
Expected: All 6 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceExtractor.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultSignificanceExtractor.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceSnapshot.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceAccumulator.java \
  mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceAccumulatorTest.java
git commit -m "feat: SignificanceAccumulator with pluggable extractor — event-driven consolidation trigger Refs #342"
```

### Task 4: Integrate SignificanceAccumulator into ConsolidationScheduler

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationScheduler.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationSchedulerTest.java`

**Interfaces:**
- Consumes: `SignificanceAccumulator.swapAndReset()` → `SignificanceSnapshot` from Task 3

- [ ] **Step 1: Write integration test**

Add to `ConsolidationSchedulerTest`:

```java
@Test
void tick_resetsSignificanceAccumulator() {
    var accumulator = new SignificanceAccumulator(
        e -> 1.0, 100.0, t -> {});

    var schedulerWithAccumulator = new ConsolidationScheduler(
        List.of(), idleTracker, memoryStore, null, e -> {},
        5, accumulator);

    var event = new ExperienceRecorded(
        new Observation("a1", "tenant-1", null, "t1",
            java.time.Instant.now(), "test", null, Map.of()),
        "m1");
    accumulator.onExperienceRecorded(event);

    schedulerWithAccumulator.tick();

    SignificanceSnapshot snapshot = accumulator.swapAndReset();
    assertThat(snapshot.perTenant()).isEmpty();
}
```

- [ ] **Step 2: Run test — verify fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ConsolidationSchedulerTest#tick_resetsSignificanceAccumulator -am`
Expected: Compilation error — constructor doesn't accept accumulator.

- [ ] **Step 3: Add SignificanceAccumulator to ConsolidationScheduler**

Add `SignificanceAccumulator` as an optional dependency:
1. Add `private final SignificanceAccumulator accumulator;` field
2. Update CDI constructor to accept `Instance<SignificanceAccumulator> accumulator`
3. Update package-private constructors to accept `SignificanceAccumulator accumulator` (nullable)
4. At the start of `tick()`, after the lock is acquired and idle check passes, call `accumulator.swapAndReset()` if non-null
5. At the start of `consolidateNow()`, call `accumulator.swapAndReset()` if non-null

- [ ] **Step 4: Fix existing ConsolidationSchedulerTest constructors**

Update existing `setUp()` and other tests to pass `null` as the accumulator parameter to the package-private constructor.

- [ ] **Step 5: Run all ConsolidationScheduler tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ConsolidationSchedulerTest -am`
Expected: All tests PASS (existing + new integration test).

- [ ] **Step 6: Build the full module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -am`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationScheduler.java \
  mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationSchedulerTest.java
git commit -m "feat: integrate SignificanceAccumulator into ConsolidationScheduler — swap-and-reset on tick Closes #342"
```

---

## Batch 3: CBR Retrieval Diversity (#344)

### Task 5: MmrSelector — pure-Java MMR algorithm

**Files:**
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/diversity/MmrSelector.java`
- Test: `memory/src/test/java/io/casehub/neocortex/memory/cbr/diversity/MmrSelectorTest.java`

**Interfaces:**
- Produces: `MmrSelector.select(List<ScoredCbrCase<C>>, int topK, double lambda, PairwiseSimilarity<C> similarity)` — used by Task 6
- Produces: `MmrSelector.PairwiseSimilarity<C>` — @FunctionalInterface for case-to-case similarity

- [ ] **Step 1: Write MmrSelectorTest**

```java
package io.casehub.neocortex.memory.cbr.diversity;

import io.casehub.neocortex.memory.cbr.CbrCase;
import io.casehub.neocortex.memory.cbr.FeatureValue;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class MmrSelectorTest {

    private ScoredCbrCase<TestCase> scored(String id, double score,
                                            Map<String, FeatureValue> features) {
        return new ScoredCbrCase<>(
            new TestCase(features), id, "test-type", score,
            false, Map.of(), Instant.now(), null, null);
    }

    @Test
    void lambdaOne_preservesScoreOrder() {
        var c1 = scored("c1", 0.9, Map.of("a", FeatureValue.string("x")));
        var c2 = scored("c2", 0.8, Map.of("a", FeatureValue.string("y")));
        var c3 = scored("c3", 0.7, Map.of("a", FeatureValue.string("z")));

        var result = MmrSelector.select(
            List.of(c1, c2, c3), 3, 1.0, (a, b) -> 0.0);

        assertThat(result).extracting(ScoredCbrCase::caseId)
            .containsExactly("c1", "c2", "c3");
    }

    @Test
    void lambdaZero_maximizesDiversity() {
        var c1 = scored("c1", 0.9, Map.of("a", FeatureValue.string("x")));
        var c2 = scored("c2", 0.8, Map.of("a", FeatureValue.string("x")));
        var c3 = scored("c3", 0.7, Map.of("a", FeatureValue.string("z")));

        var result = MmrSelector.select(
            List.of(c1, c2, c3), 2, 0.0,
            (a, b) -> a.cbrCase().features().get("a").equals(
                       b.cbrCase().features().get("a")) ? 1.0 : 0.0);

        assertThat(result).extracting(ScoredCbrCase::caseId)
            .containsExactly("c1", "c3");
    }

    @Test
    void topKGreaterThanCandidates_returnsAll() {
        var c1 = scored("c1", 0.9, Map.of());
        var result = MmrSelector.select(List.of(c1), 5, 0.7, (a, b) -> 0.0);
        assertThat(result).hasSize(1);
    }

    @Test
    void resultResortedByScore() {
        var c1 = scored("c1", 0.9, Map.of("a", FeatureValue.string("x")));
        var c2 = scored("c2", 0.5, Map.of("a", FeatureValue.string("y")));
        var c3 = scored("c3", 0.7, Map.of("a", FeatureValue.string("z")));

        var result = MmrSelector.select(
            List.of(c1, c2, c3), 3, 0.7, (a, b) -> 0.0);

        assertThat(result).extracting(ScoredCbrCase::score)
            .isSortedAccordingTo((a, b) -> Double.compare(b, a));
    }

    @Test
    void emptyInput_returnsEmpty() {
        var result = MmrSelector.<TestCase>select(List.of(), 5, 0.7, (a, b) -> 0.0);
        assertThat(result).isEmpty();
    }

    record TestCase(Map<String, FeatureValue> features) implements CbrCase {
        @Override public String problem() { return "test"; }
        @Override public Map<String, FeatureValue> features() { return features; }
    }
}
```

- [ ] **Step 2: Run test — verify compilation fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=io.casehub.neocortex.memory.cbr.diversity.MmrSelectorTest -am`
Expected: Compilation error — `MmrSelector` does not exist.

- [ ] **Step 3: Implement MmrSelector**

```java
package io.casehub.neocortex.memory.cbr.diversity;

import io.casehub.neocortex.memory.cbr.CbrCase;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class MmrSelector {

    private MmrSelector() {}

    @FunctionalInterface
    public interface PairwiseSimilarity<C extends CbrCase> {
        double similarity(ScoredCbrCase<C> a, ScoredCbrCase<C> b);
    }

    public static <C extends CbrCase> List<ScoredCbrCase<C>> select(
            List<ScoredCbrCase<C>> candidates,
            int topK,
            double lambda,
            PairwiseSimilarity<C> similarity) {
        if (candidates.size() <= topK) return List.copyOf(candidates);

        var remaining = new ArrayList<>(candidates);
        var selected = new ArrayList<ScoredCbrCase<C>>(topK);

        remaining.sort((a, b) -> Double.compare(b.score(), a.score()));
        selected.add(remaining.remove(0));

        while (selected.size() < topK && !remaining.isEmpty()) {
            double bestMmr = Double.NEGATIVE_INFINITY;
            int bestIdx = 0;

            for (int i = 0; i < remaining.size(); i++) {
                ScoredCbrCase<C> candidate = remaining.get(i);
                double relevance = candidate.score();
                double maxSim = 0.0;
                for (ScoredCbrCase<C> sel : selected) {
                    maxSim = Math.max(maxSim,
                        similarity.similarity(candidate, sel));
                }
                double mmr = lambda * relevance - (1.0 - lambda) * maxSim;
                if (mmr > bestMmr) {
                    bestMmr = mmr;
                    bestIdx = i;
                }
            }
            selected.add(remaining.remove(bestIdx));
        }

        selected.sort((a, b) -> Double.compare(b.score(), a.score()));
        return List.copyOf(selected);
    }
}
```

- [ ] **Step 4: Run tests — verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=io.casehub.neocortex.memory.cbr.diversity.MmrSelectorTest -am`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add memory/src/main/java/io/casehub/neocortex/memory/cbr/diversity/MmrSelector.java \
  memory/src/test/java/io/casehub/neocortex/memory/cbr/diversity/MmrSelectorTest.java
git commit -m "feat: MmrSelector — pure-Java Maximal Marginal Relevance algorithm Refs #344"
```

### Task 6: DiversityCbrCaseMemoryStore decorator

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java` (add `withTopK()` convenience method)
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/diversity/DiversityCbrCaseMemoryStore.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/diversity/DiversityConfig.java`
- Test: `memory/src/test/java/io/casehub/neocortex/memory/cbr/diversity/DiversityCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `MmrSelector.select(candidates, topK, lambda, similarity)` from Task 5
- Consumes: `CbrSimilarityScorer.score(features1, features2, weights, schema)` from memory-api
- Consumes: `DelegatingCbrCaseMemoryStore` base class from memory-api
- Consumes: `CbrFeatureSchema` cached via `registerSchema()` interception

- [ ] **Step 1: Write DiversityCbrCaseMemoryStoreTest**

```java
package io.casehub.neocortex.memory.cbr.diversity;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrCaseMemoryStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class DiversityCbrCaseMemoryStoreTest {

    private InMemoryCbrCaseMemoryStore inner;
    private DiversityCbrCaseMemoryStore decorator;
    private static final String TENANT = "t1";
    private static final MemoryDomain DOMAIN = new MemoryDomain("test");

    @BeforeEach
    void setUp() {
        inner = new InMemoryCbrCaseMemoryStore();
        decorator = new DiversityCbrCaseMemoryStore(
            inner, 0.7, 1.5, true);
    }

    @Test
    void disabled_passesThrough() {
        var disabled = new DiversityCbrCaseMemoryStore(
            inner, 0.7, 1.5, false);

        var schema = CbrFeatureSchema.of("test-type",
            List.of(FeatureField.categorical("color")));
        disabled.registerSchema(schema);

        storeCases(schema, 5);
        var query = CbrQuery.of(TENANT, DOMAIN, "test-type",
            Map.of("color", FeatureValue.string("red")), 3);
        var results = disabled.retrieveSimilar(query, CbrCase.class);

        assertThat(results).hasSizeLessThanOrEqualTo(3);
    }

    @Test
    void enabled_returnsRequestedTopK() {
        var schema = CbrFeatureSchema.of("test-type",
            List.of(FeatureField.categorical("color")));
        decorator.registerSchema(schema);

        storeCases(schema, 10);
        var query = CbrQuery.of(TENANT, DOMAIN, "test-type",
            Map.of("color", FeatureValue.string("red")), 3);
        var results = decorator.retrieveSimilar(query, CbrCase.class);

        assertThat(results).hasSize(3);
    }

    @Test
    void noSchema_passesThrough() {
        storeCasesNoSchema(3);
        var query = CbrQuery.of(TENANT, DOMAIN, "unregistered",
            Map.of(), 3);
        var results = decorator.retrieveSimilar(query, CbrCase.class);
        assertThat(results).hasSizeLessThanOrEqualTo(3);
    }

    @Test
    void preservesCaseIds() {
        var schema = CbrFeatureSchema.of("test-type",
            List.of(FeatureField.categorical("color")));
        decorator.registerSchema(schema);

        storeCases(schema, 5);
        var query = CbrQuery.of(TENANT, DOMAIN, "test-type",
            Map.of("color", FeatureValue.string("red")), 5);
        var results = decorator.retrieveSimilar(query, CbrCase.class);

        for (var r : results) {
            assertThat(r.caseId()).isNotNull();
            assertThat(r.caseType()).isEqualTo("test-type");
        }
    }

    private void storeCases(CbrFeatureSchema schema, int count) {
        inner.registerSchema(schema);
        for (int i = 0; i < count; i++) {
            var c = new SimpleCbrCase(
                "case " + i,
                Map.of("color", FeatureValue.string(
                    i % 3 == 0 ? "red" : i % 3 == 1 ? "blue" : "green")));
            inner.store(c, "test-type", "e" + i, DOMAIN, TENANT, null, null);
        }
    }

    private void storeCasesNoSchema(int count) {
        for (int i = 0; i < count; i++) {
            var c = new SimpleCbrCase("case " + i, Map.of());
            inner.store(c, "unregistered", "e" + i, DOMAIN, TENANT, null, null);
        }
    }

    record SimpleCbrCase(String problem, Map<String, FeatureValue> features)
            implements CbrCase {
        @Override public String problem() { return problem; }
        @Override public Map<String, FeatureValue> features() { return features; }
    }
}
```

- [ ] **Step 2: Run test — verify compilation fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=io.casehub.neocortex.memory.cbr.diversity.DiversityCbrCaseMemoryStoreTest -am`
Expected: Compilation error — `DiversityCbrCaseMemoryStore` does not exist.

- [ ] **Step 3: Add withTopK() to CbrQuery**

`CbrQuery` is a record with 17 `with*()` methods but no `withTopK()`. Add:

```java
public CbrQuery withTopK(int topK) {
    return new CbrQuery(tenantId, domain, caseTypeScope, features, filters,
        weights, topK, minSimilarity, notBefore, problem, vectorWeight,
        retrievalMode, fusionStrategy, temporalDecay, scope, scopeDecay,
        callerPrincipalId);
}
```

- [ ] **Step 4a: Create DiversityConfig**

```java
package io.casehub.neocortex.memory.cbr.diversity;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.cbr.diversity")
public interface DiversityConfig {
    @WithDefault("false") boolean enabled();
    @WithDefault("0.7") double lambda();
    @WithDefault("1.5") double overFetchFactor();
}
```

- [ ] **Step 4: Implement DiversityCbrCaseMemoryStore**

```java
package io.casehub.neocortex.memory.cbr.diversity;

import io.casehub.neocortex.memory.cbr.*;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;

import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

@Decorator
@Priority(55)
public class DiversityCbrCaseMemoryStore extends DelegatingCbrCaseMemoryStore {

    private static final Logger LOG = Logger.getLogger(
        DiversityCbrCaseMemoryStore.class.getName());

    private final double lambda;
    private final double overFetchFactor;
    private final boolean enabled;
    private final ConcurrentHashMap<String, CbrFeatureSchema> schemaCache =
        new ConcurrentHashMap<>();

    @Inject
    DiversityCbrCaseMemoryStore(@Delegate @Any CbrCaseMemoryStore delegate,
                                 DiversityConfig config) {
        this(delegate, config.lambda(), config.overFetchFactor(), config.enabled());
    }

    DiversityCbrCaseMemoryStore(CbrCaseMemoryStore delegate,
                                 double lambda,
                                 double overFetchFactor,
                                 boolean enabled) {
        super(delegate);
        this.lambda = lambda;
        this.overFetchFactor = overFetchFactor;
        this.enabled = enabled;
    }

    @Override
    public void registerSchema(CbrFeatureSchema schema) {
        schemaCache.put(schema.caseType(), schema);
        super.registerSchema(schema);
    }

    @Override
    public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(
            CbrQuery query, Class<C> caseType) {
        if (!enabled) return super.retrieveSimilar(query, caseType);

        String ct = switch (query.caseTypeScope()) {
            case CbrQuery.CaseTypeScope.Specific s -> s.caseType();
            case CbrQuery.CaseTypeScope.AllInDomain a -> null;
        };

        CbrFeatureSchema schema = ct != null ? schemaCache.get(ct) : null;
        if (schema == null) {
            if (ct != null) {
                LOG.fine("No cached schema for caseType '" + ct
                    + "' — diversity skipped");
            }
            return super.retrieveSimilar(query, caseType);
        }

        int originalTopK = query.topK();
        int inflatedTopK = (int) Math.ceil(originalTopK * overFetchFactor);
        CbrQuery inflated = query.withTopK(inflatedTopK);

        List<ScoredCbrCase<C>> candidates = super.retrieveSimilar(
            inflated, caseType);
        if (candidates.size() <= originalTopK) return candidates;

        Map<String, Double> uniformWeights = buildUniformWeights(schema);

        return MmrSelector.select(candidates, originalTopK, lambda,
            (a, b) -> CbrSimilarityScorer.score(
                a.cbrCase().features(),
                b.cbrCase().features(),
                uniformWeights, schema));
    }

    private Map<String, Double> buildUniformWeights(CbrFeatureSchema schema) {
        var weights = new java.util.HashMap<String, Double>();
        for (FeatureField field : schema.fields()) {
            weights.put(field.name(), 1.0);
        }
        return Map.copyOf(weights);
    }
}
```

- [ ] **Step 6: Run tests — verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -Dtest=io.casehub.neocortex.memory.cbr.diversity.DiversityCbrCaseMemoryStoreTest -am`
Expected: All 4 tests PASS.

- [ ] **Step 7: Build the full module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory -am`
Expected: All tests PASS.

- [ ] **Step 8: Commit**

```bash
git add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java \
  memory/src/main/java/io/casehub/neocortex/memory/cbr/diversity/DiversityCbrCaseMemoryStore.java \
  memory/src/main/java/io/casehub/neocortex/memory/cbr/diversity/DiversityConfig.java \
  memory/src/test/java/io/casehub/neocortex/memory/cbr/diversity/DiversityCbrCaseMemoryStoreTest.java
git commit -m "feat: DiversityCbrCaseMemoryStore @Decorator — MMR diversity injection at Priority(55) Closes #344"
```

---

## References

- [2026-09-16-cognitive-s-batch-design.md] — design spec this plan implements
- [decisions.md] — 7 captured design decisions (D1-D7)
- [memory-api/.../GraduationScorer.java] — current SPI to widen
- [memory-api/.../GraduationContext.java] — new record (this plan creates it)
- [mindmap-intelligence/.../DefaultGraduationScorer.java] — scorer to modify
- [mindmap-intelligence/.../ExperienceConsolidationPhase.java] — phase to add batch-query
- [mindmap-intelligence/.../ExperienceConsolidationConfig.java] — config to extend
- [mindmap-intelligence/.../ConsolidationScheduler.java] — scheduler to integrate accumulator
- [mindmap-intelligence/.../RetrievalAccessTracker.java] — swap-and-reset pattern reference
- [memory-api/.../DelegatingCbrCaseMemoryStore.java] — decorator base class
- [memory-api/.../CbrSimilarityScorer.java] — pairwise similarity for MMR
- [GitHub #340] — corroboration-gated graduation
- [GitHub #342] — importance-threshold reflection trigger
- [GitHub #344] — CBR retrieval diversity injection
