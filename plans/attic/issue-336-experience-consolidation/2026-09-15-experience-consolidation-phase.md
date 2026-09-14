# ExperienceConsolidationPhase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #336 — ExperienceConsolidationPhase — graduate episodic buffer events to mindmap during consolidation
**Issue group:** #336

**Goal:** Add a new ConsolidationPhase that bridges Tier 2 experience memories to Tier 3 cognitive mindmap nodes during consolidation, with pluggable scoring and classification SPIs.

**Architecture:** A thin pipeline orchestrator phase at @Priority(15) delegates scoring to GraduationScorer and classification to GraduationClassifier — both SPIs in memory-api with @DefaultBean implementations in mindmap-intelligence. Uses CaseMemoryStore.scan() with cursor-based pagination. Cursor persisted on a sentinel node in TYPE_SYSTEM subgraph.

**Tech Stack:** Java 21, Quarkus 3.32.2 CDI, CaseMemoryStore SPI, MindMapStore SPI

## Global Constraints

- Java 21 source (on Java 26 JVM)
- SPIs in memory-api (`io.casehub.neocortex.memory.experience` package)
- Implementations in mindmap-intelligence (`io.casehub.neocortex.mindmap.intelligence.consolidation` package)
- All tests use InMemoryMindMapStore + InMemoryMemoryStore — no SQLite, Docker, ONNX
- Memory record accessors: `memoryId()` (not `id()`), `text()` (not `content()`)
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Module test: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`

---

## Batch 1: Foundation — SPIs, defaults, and SCAN prerequisite

### Task 1: Add SCAN capability to InMemoryMemoryStore

**Files:**
- Modify: `memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java`
- Test: `memory-inmem/src/test/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStoreTest.java`

**Interfaces:**
- Consumes: `MemoryScanRequest(tenantId, domain, attributeKey, attributeValue, limit, afterMemoryId)`, `MemoryCapability.SCAN`
- Produces: `InMemoryMemoryStore.scan(MemoryScanRequest)` returning `List<Memory>`, `InMemoryMemoryStore.capabilities()` including `SCAN`

- [ ] **Step 1: Write failing test for scan by domain**

```java
@Test
void scanByDomain_returnsMatchingMemories() {
    store.store(new MemoryInput(Subject.of("agent", "a1"), new MemoryDomain("experience"),
        "t1", null, "event one", Map.of(), null, null, null, null, null, null));
    store.store(new MemoryInput(Subject.of("agent", "a1"), new MemoryDomain("reflection"),
        "t1", null, "reflect one", Map.of(), null, null, null, null, null, null));
    store.store(new MemoryInput(Subject.of("agent", "a2"), new MemoryDomain("experience"),
        "t1", null, "event two", Map.of(), null, null, null, null, null, null));

    List<Memory> result = store.scan(new MemoryScanRequest("t1", "experience", null, null, 100, null));

    assertEquals(2, result.size());
    assertTrue(result.stream().allMatch(m -> m.domain().name().equals("experience")));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-inmem -Dtest=InMemoryMemoryStoreTest#scanByDomain_returnsMatchingMemories`
Expected: FAIL — `MemoryCapabilityException: SCAN`

- [ ] **Step 3: Write failing test for cursor pagination**

```java
@Test
void scanWithCursor_resumesFromAfterMemoryId() {
    String id1 = store.store(new MemoryInput(Subject.of("agent", "a1"), new MemoryDomain("experience"),
        "t1", null, "event one", Map.of(), null, null, null, null, null, null));
    String id2 = store.store(new MemoryInput(Subject.of("agent", "a1"), new MemoryDomain("experience"),
        "t1", null, "event two", Map.of(), null, null, null, null, null, null));
    String id3 = store.store(new MemoryInput(Subject.of("agent", "a1"), new MemoryDomain("experience"),
        "t1", null, "event three", Map.of(), null, null, null, null, null, null));

    List<Memory> page1 = store.scan(new MemoryScanRequest("t1", "experience", null, null, 2, null));
    assertEquals(2, page1.size());

    List<Memory> page2 = store.scan(new MemoryScanRequest("t1", "experience", null, null, 2, page1.get(1).memoryId()));
    assertEquals(1, page2.size());
    assertEquals("event three", page2.get(0).text());
}
```

- [ ] **Step 4: Write failing test for attribute filter**

```java
@Test
void scanWithAttributeFilter_filtersCorrectly() {
    store.store(new MemoryInput(Subject.of("agent", "a1"), new MemoryDomain("experience"),
        "t1", null, "obs", Map.of("event-type", "observation"), null, null, null, null, null, null));
    store.store(new MemoryInput(Subject.of("agent", "a1"), new MemoryDomain("experience"),
        "t1", null, "act", Map.of("event-type", "action"), null, null, null, null, null, null));

    List<Memory> result = store.scan(new MemoryScanRequest("t1", "experience", "event-type", "observation", 100, null));
    assertEquals(1, result.size());
    assertEquals("obs", result.get(0).text());
}
```

- [ ] **Step 5: Implement scan() and add SCAN to capabilities**

Add `MemoryCapability.SCAN` to the capabilities set. Implement `scan()`:

```java
@Override
public List<Memory> scan(MemoryScanRequest request) {
    requireCapability(MemoryCapability.SCAN);
    List<Memory> all = new ArrayList<>();
    for (var entry : store.entrySet()) {
        if (!entry.getKey().tenantId().equals(request.tenantId())) continue;
        for (Memory m : entry.getValue()) {
            if (request.domain() != null && !m.domain().name().equals(request.domain())) continue;
            if (request.attributeKey() != null
                && !request.attributeValue().equals(m.attributes().get(request.attributeKey()))) continue;
            all.add(m);
        }
    }
    all.sort(Comparator.comparing(Memory::createdAt));

    if (request.afterMemoryId() != null) {
        int idx = -1;
        for (int i = 0; i < all.size(); i++) {
            if (all.get(i).memoryId().equals(request.afterMemoryId())) { idx = i; break; }
        }
        if (idx >= 0) all = all.subList(idx + 1, all.size());
    }
    if (all.size() > request.limit()) all = all.subList(0, request.limit());
    return List.copyOf(all);
}
```

- [ ] **Step 6: Run all scan tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-inmem -Dtest=InMemoryMemoryStoreTest`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java memory-inmem/src/test/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStoreTest.java
git commit -m "feat(memory-inmem): add SCAN capability to InMemoryMemoryStore

Refs #336"
```

---

### Task 2: GraduationScorer SPI + GraduationResult + GraduationClassifier SPI

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationScorer.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationClassifier.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationResult.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/experience/GraduationResultTest.java`

**Interfaces:**
- Consumes: `Memory` record from `io.casehub.neocortex.memory.Memory`, `ConfidenceOrigin` from `io.casehub.neocortex.cognitive.ConfidenceOrigin`
- Produces: `GraduationScorer.score(Memory) → double`, `GraduationClassifier.classify(Memory) → GraduationResult`, `GraduationResult(cognitiveKind, confidenceOrigin, properties)`

- [ ] **Step 1: Write failing test for GraduationResult validation**

```java
@Test
void graduationResult_requiresCognitiveKind() {
    assertThrows(NullPointerException.class,
        () -> new GraduationResult(null, ConfidenceOrigin.STATED, Map.of()));
}

@Test
void graduationResult_requiresConfidenceOrigin() {
    assertThrows(NullPointerException.class,
        () -> new GraduationResult("belief", null, Map.of()));
}

@Test
void graduationResult_nullPropertiesDefaultsToEmpty() {
    var result = new GraduationResult("belief", ConfidenceOrigin.STATED, null);
    assertEquals(Map.of(), result.properties());
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=GraduationResultTest`
Expected: FAIL — class not found

- [ ] **Step 3: Create GraduationScorer.java**

```java
package io.casehub.neocortex.memory.experience;

import io.casehub.neocortex.memory.Memory;

@FunctionalInterface
public interface GraduationScorer {
    double score(Memory memory);
}
```

- [ ] **Step 4: Create GraduationResult.java**

```java
package io.casehub.neocortex.memory.experience;

import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import java.util.Map;
import java.util.Objects;

public record GraduationResult(
    String cognitiveKind,
    ConfidenceOrigin confidenceOrigin,
    Map<String, String> properties
) {
    public GraduationResult {
        Objects.requireNonNull(cognitiveKind, "cognitiveKind required");
        Objects.requireNonNull(confidenceOrigin, "confidenceOrigin required");
        if (properties == null) properties = Map.of();
    }
}
```

- [ ] **Step 5: Create GraduationClassifier.java**

```java
package io.casehub.neocortex.memory.experience;

import io.casehub.neocortex.memory.Memory;

public interface GraduationClassifier {
    GraduationResult classify(Memory memory);
}
```

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=GraduationResultTest`
Expected: ALL PASS

- [ ] **Step 7: Compile check across memory-api**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl memory-api`
Expected: BUILD SUCCESS

- [ ] **Step 8: Commit**

```bash
git add memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationScorer.java memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationClassifier.java memory-api/src/main/java/io/casehub/neocortex/memory/experience/GraduationResult.java memory-api/src/test/java/io/casehub/neocortex/memory/experience/GraduationResultTest.java
git commit -m "feat(memory-api): GraduationScorer + GraduationClassifier SPIs + GraduationResult record

Refs #336"
```

---

### Task 3: DefaultGraduationScorer + DefaultGraduationClassifier

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorer.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationClassifier.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorerTest.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationClassifierTest.java`

**Interfaces:**
- Consumes: `GraduationScorer`, `GraduationClassifier`, `GraduationResult` from memory-api; `Memory`, `Confidence`, `ConfidenceOrigin`, `ExperienceAttributeKeys`
- Produces: `DefaultGraduationScorer` (@DefaultBean), `DefaultGraduationClassifier` (@DefaultBean)

- [ ] **Step 1: Write failing scorer tests**

```java
@Test
void score_returnsConfidenceValue() {
    Memory memory = new Memory("m1", Subject.of("agent", "a1"),
        new MemoryDomain("experience"), "t1", null, "event",
        Map.of(), Instant.now(), Confidence.unknown(0.8), null, null, null, null, null);
    assertEquals(0.8, new DefaultGraduationScorer().score(memory), 0.001);
}

@Test
void score_returnsDefaultWhenConfidenceNull() {
    Memory memory = new Memory("m1", Subject.of("agent", "a1"),
        new MemoryDomain("experience"), "t1", null, "event",
        Map.of(), Instant.now(), null, null, null, null, null, null);
    assertEquals(0.5, new DefaultGraduationScorer().score(memory), 0.001);
}
```

- [ ] **Step 2: Run to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DefaultGraduationScorerTest`
Expected: FAIL — class not found

- [ ] **Step 3: Write failing classifier tests**

```java
@Test
void classify_observation_producesBelief() {
    Memory memory = new Memory("m1", Subject.of("agent", "a1"),
        new MemoryDomain("experience"), "t1", null, "saw something",
        Map.of("event-type", "observation", "subject", "Bob"),
        Instant.now(), null, null, null, null, null, null);
    GraduationResult result = new DefaultGraduationClassifier().classify(memory);
    assertEquals("belief", result.cognitiveKind());
    assertEquals(ConfidenceOrigin.STATED, result.confidenceOrigin());
    assertEquals("Bob", result.properties().get("subject"));
    assertEquals("active", result.properties().get("status"));
}

@Test
void classify_action_producesIntention() {
    Memory memory = new Memory("m1", Subject.of("agent", "a1"),
        new MemoryDomain("experience"), "t1", null, "did something",
        Map.of("event-type", "action", "capability", "persuade"),
        Instant.now(), null, null, null, null, null, null);
    GraduationResult result = new DefaultGraduationClassifier().classify(memory);
    assertEquals("intention", result.cognitiveKind());
    assertEquals(ConfidenceOrigin.INFERRED, result.confidenceOrigin());
    assertEquals("persuade", result.properties().get("goal"));
}

@Test
void classify_outcome_producesJudgment() {
    Memory memory = new Memory("m1", Subject.of("agent", "a1"),
        new MemoryDomain("experience"), "t1", null, "it worked",
        Map.of("event-type", "outcome", "result", "success"),
        Instant.now(), null, null, null, null, null, null);
    GraduationResult result = new DefaultGraduationClassifier().classify(memory);
    assertEquals("judgment", result.cognitiveKind());
    assertEquals(ConfidenceOrigin.INFERRED, result.confidenceOrigin());
    assertEquals("success", result.properties().get("target"));
}

@Test
void classify_unknownType_defaultsToBelief() {
    Memory memory = new Memory("m1", Subject.of("agent", "a1"),
        new MemoryDomain("experience"), "t1", null, "something",
        Map.of("event-type", "unknown"),
        Instant.now(), null, null, null, null, null, null);
    GraduationResult result = new DefaultGraduationClassifier().classify(memory);
    assertEquals("belief", result.cognitiveKind());
    assertEquals(ConfidenceOrigin.INFERRED, result.confidenceOrigin());
}
```

- [ ] **Step 4: Implement DefaultGraduationScorer**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.experience.GraduationScorer;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;

@DefaultBean
@ApplicationScoped
public class DefaultGraduationScorer implements GraduationScorer {
    @Override
    public double score(Memory memory) {
        if (memory.confidence() != null) {
            return memory.confidence().value();
        }
        return 0.5;
    }
}
```

- [ ] **Step 5: Implement DefaultGraduationClassifier**

Full implementation from spec §3.2 — observation → belief, action → intention, outcome → judgment.

- [ ] **Step 6: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="DefaultGraduationScorerTest,DefaultGraduationClassifierTest"`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorer.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationClassifier.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationScorerTest.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DefaultGraduationClassifierTest.java
git commit -m "feat(mindmap-intelligence): DefaultGraduationScorer + DefaultGraduationClassifier @DefaultBean implementations

Refs #336"
```

---

## Batch 2: Phase — ExperienceConsolidationPhase with full test coverage

### Task 4: ExperienceConsolidationPhase + ExperienceConsolidationConfig

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhase.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationConfig.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhaseTest.java`

**Interfaces:**
- Consumes: `ConsolidationPhase` SPI, `CaseMemoryStore.scan(MemoryScanRequest)`, `MindMapStore.addNode(NodeInput, tenantId)`, `MindMapStore.search(MindMapQuery)`, `MindMapStore.listSubgraphs(tenantId)`, `MindMapStore.createSubgraph(SubgraphInput, tenantId)`, `MindMapStore.getNode(nodeId, tenantId)`, `MindMapStore.updateNode(nodeId, NodeUpdate, tenantId)`, `GraduationScorer.score(Memory)`, `GraduationClassifier.classify(Memory)`, `SubgraphTypes.COGNITIVE`, `SubgraphTypes.TYPE_SYSTEM`, `NodeInput.of(name, subgraphId)`, `MindMapConfidenceDefaults.forOrigin(origin, instant)`, `ExperienceEvents.DOMAIN`, `ExperienceAttributeKeys.EVENT_TYPE`
- Produces: `ExperienceConsolidationPhase` (@Priority 15), `ExperienceConsolidationConfig` (@ConfigMapping)

- [ ] **Step 1: Write failing test — graduated event produces cognitive node**

```java
@Test
void graduatedEvent_producesCognitiveNode() {
    storeExperienceMemory("m1", "a1", "t1", "observation", "Bob looks worried",
        Map.of("subject", "Bob"), 0.8);

    phase.run("t1", List.of());

    List<MindMapNode> nodes = mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE));
    assertEquals(1, nodes.size());
    MindMapNode node = nodes.get(0);
    assertEquals("belief", node.property("cognitiveKind").orElse(""));
    assertEquals("m1", node.property("source-memory-id").orElse(""));
    assertEquals("experience-consolidation", node.provenance());
}
```

Use a private `storeExperienceMemory` helper that creates a `MemoryInput` via `ExperienceEvents.toMemoryInput()` from an `Observation`/`Action`/`Outcome` and stores via `memoryStore.store()`.

- [ ] **Step 2: Run to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExperienceConsolidationPhaseTest#graduatedEvent_producesCognitiveNode`
Expected: FAIL — class not found

- [ ] **Step 3: Write failing test — score below threshold not graduated**

```java
@Test
void scoreBelowThreshold_notGraduated() {
    storeExperienceMemory("m1", "a1", "t1", "observation", "trivial event",
        Map.of("subject", "X"), 0.1);

    phase.run("t1", List.of());

    List<MindMapNode> nodes = mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE));
    assertEquals(0, nodes.size());
}
```

- [ ] **Step 4: Write failing test — max-per-pass cap**

```java
@Test
void maxPerPass_capsProcessing() {
    for (int i = 0; i < 5; i++) {
        storeExperienceMemory("m" + i, "a1", "t1", "observation",
            "event " + i, Map.of("subject", "S"), 0.8);
    }

    // Phase with maxPerPass=3
    var cappedPhase = new ExperienceConsolidationPhase(
        memoryStore, mindMapStore, scorer, classifier, 0.5, 3);
    cappedPhase.run("t1", List.of());

    List<MindMapNode> nodes = mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE));
    assertEquals(3, nodes.size());

    // Second run processes remaining
    cappedPhase.run("t1", List.of());
    nodes = mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE));
    assertEquals(5, nodes.size());
}
```

- [ ] **Step 5: Write failing test — cursor persistence**

```java
@Test
void cursorPersistence_secondRunSkipsProcessed() {
    storeExperienceMemory("m1", "a1", "t1", "observation", "first",
        Map.of("subject", "A"), 0.8);
    phase.run("t1", List.of());

    storeExperienceMemory("m2", "a1", "t1", "observation", "second",
        Map.of("subject", "B"), 0.8);
    phase.run("t1", List.of());

    List<MindMapNode> nodes = mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE));
    assertEquals(2, nodes.size());
}
```

- [ ] **Step 6: Write failing test — dedup guard**

```java
@Test
void dedupGuard_reprocessedMemoryNotDuplicated() {
    storeExperienceMemory("m1", "a1", "t1", "observation", "same event",
        Map.of("subject", "A"), 0.8);
    phase.run("t1", List.of());

    // Simulate cursor reset (crash recovery) — run again from beginning
    var freshPhase = new ExperienceConsolidationPhase(
        memoryStore, mindMapStore, scorer, classifier, 0.5, 20);
    freshPhase.run("t1", List.of());

    List<MindMapNode> nodes = mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE));
    assertEquals(1, nodes.size());
}
```

- [ ] **Step 7: Write failing test — error isolation**

```java
@Test
void errorIsolation_failedMemoryDoesNotBlockOthers() {
    storeExperienceMemory("m1", "a1", "t1", "observation", "good event",
        Map.of("subject", "A"), 0.8);
    storeExperienceMemory("m2", "a1", "t1", "observation", "another good",
        Map.of("subject", "B"), 0.8);

    GraduationScorer failOnFirst = m -> {
        if (m.memoryId().equals("m1")) throw new RuntimeException("scorer failed");
        return 0.8;
    };
    var phaseWithFailingScorer = new ExperienceConsolidationPhase(
        memoryStore, mindMapStore, failOnFirst, classifier, 0.5, 20);
    phaseWithFailingScorer.run("t1", List.of());

    List<MindMapNode> nodes = mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE));
    assertEquals(1, nodes.size());
}
```

- [ ] **Step 8: Write failing test — node properties**

```java
@Test
void nodeProperties_allFieldsSet() {
    storeExperienceMemory("m1", "a1", "t1", "observation", "Bob is worried",
        Map.of("subject", "Bob"), 0.8);
    phase.run("t1", List.of());

    MindMapNode node = mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE)).get(0);

    assertEquals("m1", node.property("source-memory-id").orElse(""));
    assertEquals("observation", node.property("event-type").orElse(""));
    assertEquals("a1", node.property("agent-id").orElse(""));
    assertEquals("belief", node.property("cognitiveKind").orElse(""));
    assertTrue(node.property("graduation-score").isPresent());
    assertEquals("experience-consolidation", node.provenance());
}
```

- [ ] **Step 9: Write failing test — multi-tenant isolation**

```java
@Test
void multiTenant_independentProcessing() {
    storeExperienceMemory("m1", "a1", "t1", "observation", "tenant1 event",
        Map.of("subject", "A"), 0.8);
    storeExperienceMemory("m2", "a1", "t2", "observation", "tenant2 event",
        Map.of("subject", "B"), 0.8);

    phase.run("t1", List.of());

    assertEquals(1, mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE)).size());
    assertEquals(0, mindMapStore.search(
        MindMapQuery.of("t2", 100).withType(SubgraphTypes.COGNITIVE)).size());

    phase.run("t2", List.of());
    assertEquals(1, mindMapStore.search(
        MindMapQuery.of("t2", 100).withType(SubgraphTypes.COGNITIVE)).size());
}
```

- [ ] **Step 10: Write failing test — empty experience set**

```java
@Test
void emptyExperienceSet_noNodesCreated() {
    phase.run("t1", List.of());
    assertEquals(0, mindMapStore.search(
        MindMapQuery.of("t1", 100).withType(SubgraphTypes.COGNITIVE)).size());
}
```

- [ ] **Step 11: Implement ExperienceConsolidationConfig**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.consolidation.graduation")
public interface ExperienceConsolidationConfig {
    @WithDefault("0.5") double threshold();
    @WithDefault("20") int maxPerPass();
}
```

- [ ] **Step 12: Implement ExperienceConsolidationPhase**

Full implementation per spec §7 — scan, score, classify, create nodes, cursor management, error isolation, dedup guard.

Constructor accepts both CDI-injected (with `Instance<>` wrappers) and test-friendly (direct values) forms. Private methods: `loadCursor(tenantId)`, `saveCursor(tenantId, memoryId)`, `findOrCreateCognitiveSubgraph(tenantId)`, `loadExistingSourceMemoryIds(tenantId)`.

- [ ] **Step 13: Run all phase tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExperienceConsolidationPhaseTest`
Expected: ALL PASS

- [ ] **Step 14: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: ALL PASS — no regressions in existing tests

- [ ] **Step 15: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhase.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationConfig.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhaseTest.java
git commit -m "feat(mindmap-intelligence): ExperienceConsolidationPhase — graduate episodic events to cognitive nodes

@Priority(15) ConsolidationPhase that scans experience memories,
scores via GraduationScorer SPI, classifies via GraduationClassifier SPI,
and creates typed nodes in the COGNITIVE subgraph.

Closes #336"
```

---

## Batch 3: Integration — full build verification and CLAUDE.md update

### Task 5: Full build verification + CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md` (update module descriptions with ExperienceConsolidationPhase)

**Interfaces:**
- Consumes: all files from Tasks 1-4
- Produces: green full build, updated CLAUDE.md

- [ ] **Step 1: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 2: Update CLAUDE.md**

Update `mindmap-intelligence/` module description to include `ExperienceConsolidationPhase (@Priority(15) — scans experience memories, scores via GraduationScorer SPI, classifies via GraduationClassifier SPI, creates cognitive nodes in COGNITIVE subgraph; cursor-based pagination via MemoryScanRequest, sentinel node in TYPE_SYSTEM for persistent cursor)`.

Update `memory-api/` module description to include `GraduationScorer (@FunctionalInterface — graduation worthiness scoring SPI for experience consolidation), GraduationClassifier (classification SPI mapping memories to cognitive types), GraduationResult (classification result record: cognitiveKind + confidenceOrigin + properties)`.

Update `memory-inmem/` description to note SCAN capability support.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with ExperienceConsolidationPhase, graduation SPIs, SCAN capability

Refs #336"
```

---

## References

- specs/issue-336-experience-consolidation/2026-09-15-experience-consolidation-phase-design.md — design spec
- specs/issue-336-experience-consolidation/decisions.md — D1-D8 design decisions
- ConsolidationScheduler.java:107-144 — phase orchestration
- ConsolidationPhase.java:5-8 — SPI contract
- SchemaDiscoveryPhase.java — latest phase pattern
- Memory.java:10-39 — Memory record (memoryId, text, confidence, subject, attributes, PAD)
- InMemoryMemoryStore.java:36-247 — in-memory store (needs SCAN)
- MemoryScanRequest.java:5-22 — scan request record
- ExperienceEvents.java:19-66 — toMemoryInput conversion
- ExperienceAttributeKeys.java — attribute key constants
- NodeInput.java:10-116 — node creation record with withPleasure/withArousal/withDominance
- SubgraphTypes.java — COGNITIVE constant
- MindMapConfidenceDefaults.java — forOrigin factory
- GitHub #336 — focal issue
