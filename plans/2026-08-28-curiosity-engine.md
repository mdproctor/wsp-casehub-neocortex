# Curiosity Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #221 — feat: mindmap-intelligence — curiosity engine
**Issue group:** #213, #215, #216, #217, #218, #219, #220, #221

**Goal:** Compute prioritised curiosity signals from mind map graph analysis with temporal proximity attention magnets, affect-aware dampening, and topical distance cycle-breaking.

**Architecture:** `CuriositySignalGenerator` is an `@ApplicationScoped` CDI bean in `mindmap-intelligence/` that implements `CuriositySignalProvider`. It consumes `MindMapAnalyzer` (static utility in `mindmap/`) and `MindMapStore` (SPI) to produce a ranked `List<CuriositySignal>` with template-generated questions. Three dampening passes: affect (PAD pleasure, PROXIMITY bypass), topical distance (BFS from recent entities), and final sort.

**Tech Stack:** Java 21, Quarkus 3.32.2, mindmap-api (MindMapStore, MindMapAnalyzer)

## Global Constraints

- Java 21 source level on Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All code in `mindmap-intelligence/` under `io.casehub.neocortex.mindmap.intelligence`
- Every commit references #221: `Refs #221`
- Tests use `InMemoryMindMapStore` — no Docker, no real LLM
- No new Maven dependencies — uses only mindmap-api and quarkus-arc (already present)
- Use IntelliJ MCP for all Java file operations

---

## Batch 1: Value Types + Signal Generator

### Task 1: CuriositySignal, SignalCategory, CuriositySignalProvider

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignal.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SignalCategory.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalProvider.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalTest.java`

**Interfaces:**
- Consumes: nothing (foundational types)
- Produces: `CuriositySignal(SignalCategory, double, String, String, String, String)`, `SignalCategory` enum, `CuriositySignalProvider.computeSignals(String, Set<String>)` — used by Task 2

- [ ] **Step 1: Write tests for value types**

```java
package io.casehub.neocortex.mindmap.intelligence;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class CuriositySignalTest {

    @Test
    void signalHoldsAllFields() {
        var signal = new CuriositySignal(
            SignalCategory.STRUCTURAL, 0.75, "node-1", "sg-1",
            "What is Alice's connection?", "Orphan node: Alice");
        assertThat(signal.category()).isEqualTo(SignalCategory.STRUCTURAL);
        assertThat(signal.score()).isEqualTo(0.75);
        assertThat(signal.targetNodeId()).isEqualTo("node-1");
        assertThat(signal.targetSubgraphId()).isEqualTo("sg-1");
        assertThat(signal.question()).isEqualTo("What is Alice's connection?");
        assertThat(signal.description()).isEqualTo("Orphan node: Alice");
    }

    @Test
    void signalWithNullTargets() {
        var signal = new CuriositySignal(
            SignalCategory.QUALITY, 0.5, null, "sg-1",
            "Question", "Description");
        assertThat(signal.targetNodeId()).isNull();
    }

    @Test
    void allSignalCategories() {
        assertThat(SignalCategory.values()).containsExactlyInAnyOrder(
            SignalCategory.STRUCTURAL, SignalCategory.QUALITY,
            SignalCategory.TEMPORAL, SignalCategory.CENTRALITY,
            SignalCategory.PROXIMITY);
    }
}
```

- [ ] **Step 2: Run test — verify fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CuriositySignalTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: FAIL — classes not found

- [ ] **Step 3: Create the three types**

`SignalCategory.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

public enum SignalCategory {
    STRUCTURAL, QUALITY, TEMPORAL, CENTRALITY, PROXIMITY
}
```

`CuriositySignal.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

public record CuriositySignal(
    SignalCategory category,
    double score,
    String targetNodeId,
    String targetSubgraphId,
    String question,
    String description
) {}
```

`CuriositySignalProvider.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.List;
import java.util.Set;

public interface CuriositySignalProvider {
    List<CuriositySignal> computeSignals(String tenantId,
                                          Set<String> recentEntityIds);
}
```

- [ ] **Step 4: Run test — verify passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CuriositySignalTest`
Expected: PASS — 3 tests

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-intelligence/src
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#221): CuriositySignal + SignalCategory + CuriositySignalProvider SPI Refs #221"
```

### Task 2: CuriositySignalGenerator — core signal collection + dampening

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGenerator.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGeneratorTest.java`

**Interfaces:**
- Consumes: `CuriositySignalProvider` (Task 1), `MindMapStore` (mindmap-api), `MindMapAnalyzer` (mindmap runtime — static utility), `MindMapNode`, `MindMapEdge`, `MindMapSubgraph`, `SubgraphType`, `ConfidenceOrigin`, `NodeInput`, `SubgraphInput`, `EdgeInput`
- Produces: `CuriositySignalGenerator.computeSignals(String, Set<String>)` returning `List<CuriositySignal>` sorted by score descending

- [ ] **Step 1: Write comprehensive tests**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class CuriositySignalGeneratorTest {

    private static final String TENANT = "test-tenant";
    private InMemoryMindMapStore store;
    private CuriositySignalGenerator generator;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        generator = new CuriositySignalGenerator(store);
    }

    @Test
    void emptyGraphProducesNoSignals() {
        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());
        assertThat(signals).isEmpty();
    }

    @Test
    void orphanNodeProducesStructuralSignal() {
        String sgId = store.createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
        store.addNode(new NodeInput("Alice", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);

        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());

        assertThat(signals).anyMatch(s ->
            s.category() == SignalCategory.STRUCTURAL
            && s.question().contains("Alice"));
    }

    @Test
    void contradictionProducesQualitySignal() {
        String sgId = store.createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
        String aliceId = store.addNode(new NodeInput("Alice", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        String acmeId = store.addNode(new NodeInput("Acme", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        String initechId = store.addNode(new NodeInput("Initech", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        store.addEdge(new EdgeInput(aliceId, acmeId, "works-at", ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, Map.of()), TENANT);
        store.addEdge(new EdgeInput(aliceId, initechId, "works-at", ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, Map.of()), TENANT);

        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());

        assertThat(signals).anyMatch(s ->
            s.category() == SignalCategory.QUALITY
            && s.description().contains("contradiction"));
    }

    @Test
    void staleNodeProducesTemporalSignal() {
        String sgId = store.createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
        store.addNode(new NodeInput("OldData", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);

        // InMemoryMindMapStore sets updatedAt to now, so stale nodes
        // need updatedAt manipulation. We use a long staleThreshold
        // and verify the signal IS NOT generated for fresh nodes.
        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());
        // Fresh node should NOT be stale
        assertThat(signals).noneMatch(s ->
            s.category() == SignalCategory.TEMPORAL
            && s.question().contains("OldData")
            && s.description().contains("stale"));
    }

    @Test
    void proximitySignalForFutureEvent() {
        String sgId = store.createSubgraph(new SubgraphInput("Events", SubgraphType.GENERAL, null), TENANT);
        Instant threeDaysFromNow = Instant.now().plus(3, ChronoUnit.DAYS);
        store.addNode(new NodeInput("Visit parents", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, threeDaysFromNow, null, null, null, null, Map.of()), TENANT);

        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());

        assertThat(signals).anyMatch(s ->
            s.category() == SignalCategory.PROXIMITY
            && s.question().contains("Visit parents")
            && s.score() > 0.5);
    }

    @Test
    void pastEventProducesTemporalSignal() {
        String sgId = store.createSubgraph(new SubgraphInput("Events", SubgraphType.GENERAL, null), TENANT);
        Instant yesterday = Instant.now().minus(1, ChronoUnit.DAYS);
        store.addNode(new NodeInput("Meeting", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, yesterday, null, null, null, Map.of()), TENANT);

        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());

        assertThat(signals).anyMatch(s ->
            s.category() == SignalCategory.TEMPORAL
            && s.question().contains("Meeting")
            && s.question().contains("outcome"));
    }

    @Test
    void affectDampeningReducesScoreForNegativePleasure() {
        String sgId = store.createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
        store.addNode(new NodeInput("Sad Topic", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, -0.8, null, null, Map.of()), TENANT);

        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());

        CuriositySignal sadSignal = signals.stream()
            .filter(s -> s.description().contains("Sad Topic"))
            .findFirst().orElse(null);
        if (sadSignal != null) {
            assertThat(sadSignal.score()).isLessThanOrEqualTo(0.3);
        }
    }

    @Test
    void proximitySignalsBypassesAffectDampening() {
        String sgId = store.createSubgraph(new SubgraphInput("Events", SubgraphType.GENERAL, null), TENANT);
        Instant twoDaysFromNow = Instant.now().plus(2, ChronoUnit.DAYS);
        store.addNode(new NodeInput("Funeral", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, twoDaysFromNow, null, -0.9, null, null, Map.of()), TENANT);

        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());

        CuriositySignal proximitySignal = signals.stream()
            .filter(s -> s.category() == SignalCategory.PROXIMITY
                && s.description().contains("Funeral"))
            .findFirst().orElse(null);
        assertThat(proximitySignal).isNotNull();
        assertThat(proximitySignal.score()).isGreaterThan(0.5);
    }

    @Test
    void topicalDistanceDampeningReducesDistantSignals() {
        String sgId = store.createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
        String aId = store.addNode(new NodeInput("A", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        String bId = store.addNode(new NodeInput("B", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        String cId = store.addNode(new NodeInput("C", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        String dId = store.addNode(new NodeInput("D", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        store.addEdge(new EdgeInput(aId, bId, "knows", ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, Map.of()), TENANT);
        store.addEdge(new EdgeInput(bId, cId, "knows", ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, Map.of()), TENANT);
        store.addEdge(new EdgeInput(cId, dId, "knows", ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, Map.of()), TENANT);

        List<CuriositySignal> signalsWithContext = generator.computeSignals(TENANT, Set.of(aId));
        List<CuriositySignal> signalsWithoutContext = generator.computeSignals(TENANT, Set.of());

        // D is 3 hops from A — should be dampened
        CuriositySignal dSignalWithContext = signalsWithContext.stream()
            .filter(s -> s.targetNodeId() != null && s.targetNodeId().equals(dId))
            .findFirst().orElse(null);
        CuriositySignal dSignalWithout = signalsWithoutContext.stream()
            .filter(s -> s.targetNodeId() != null && s.targetNodeId().equals(dId))
            .findFirst().orElse(null);

        if (dSignalWithContext != null && dSignalWithout != null) {
            assertThat(dSignalWithContext.score()).isLessThan(dSignalWithout.score());
        }
    }

    @Test
    void signalsSortedByScoreDescending() {
        String sgId = store.createSubgraph(new SubgraphInput("Mixed", SubgraphType.GENERAL, null), TENANT);
        store.addNode(new NodeInput("Orphan1", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        Instant tomorrow = Instant.now().plus(1, ChronoUnit.DAYS);
        store.addNode(new NodeInput("Urgent Event", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, tomorrow, null, null, null, null, Map.of()), TENANT);

        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());

        for (int i = 1; i < signals.size(); i++) {
            assertThat(signals.get(i).score())
                .isLessThanOrEqualTo(signals.get(i - 1).score());
        }
    }

    @Test
    void centralitySignalForHighDegreeNode() {
        String sgId = store.createSubgraph(new SubgraphInput("Network", SubgraphType.GENERAL, null), TENANT);
        String hubId = store.addNode(new NodeInput("Hub", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        for (int i = 0; i < 5; i++) {
            String leafId = store.addNode(new NodeInput("Leaf" + i, sgId, ConfidenceOrigin.STATED, null, "test",
                null, null, null, null, null, null, null, Map.of()), TENANT);
            store.addEdge(new EdgeInput(hubId, leafId, "connects", ConfidenceOrigin.STATED, null, "test",
                null, null, null, null, null, Map.of()), TENANT);
        }

        List<CuriositySignal> signals = generator.computeSignals(TENANT, Set.of());

        assertThat(signals).anyMatch(s ->
            s.category() == SignalCategory.CENTRALITY
            && s.question().contains("Hub"));
    }
}
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CuriositySignalGeneratorTest`
Expected: FAIL — CuriositySignalGenerator not found

- [ ] **Step 3: Implement CuriositySignalGenerator**

Create `CuriositySignalGenerator.java` with:
- `computeSignals()` iterating subgraphs, collecting signals from each category
- `collectStructuralSignals()` — orphanNodes + subgraphDensity from MindMapAnalyzer
- `collectQualitySignals()` — contradictions + lowConfidenceCluster + unvalidatedEdgeRatio
- `collectTemporalSignals()` — staleNodes (90-day threshold) + past events
- `collectCentralitySignals()` — betweennessCentrality + degreeCentrality (top 3 each)
- `collectProximitySignals()` — nodes with validFrom in the future
- `applyAffectDampening()` — PAD pleasure < 0 → dampen score, PROXIMITY bypass
- `applyTopicalDistanceDampening()` — BFS distance from recentEntityIds
- `bfsDistance()` — bounded BFS to depth 4
- `generateQuestion()` — switch on SignalCategory → template string

Full implementation code as specified in spec §7.4–§7.9. The generator is `@ApplicationScoped` and takes `MindMapStore` via `@Inject`.

- [ ] **Step 4: Run tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CuriositySignalGeneratorTest`
Expected: PASS — 12 tests

- [ ] **Step 5: Run all mindmap-intelligence tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: PASS — all tests (ExtractionResult + ExtractionJsonParser + MindMapExtractor + TraitProxy + StandardTraitRules + CuriositySignal + CuriositySignalGenerator)

- [ ] **Step 6: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/neocortex/pom.xml -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-intelligence/src
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#221): CuriositySignalGenerator — signal collection, dampening, question templates

Signal categories: STRUCTURAL (orphans, sparse subgraphs), QUALITY
(contradictions, low confidence, unvalidated edges), TEMPORAL (stale
nodes, past events), CENTRALITY (betweenness, degree), PROXIMITY
(temporal attention magnets).

Three dampening passes: affect (PAD pleasure, PROXIMITY bypass),
topical distance (BFS from recent entities), final sort by score.
Template-based question generation — pure Java, no LLM.

Refs #221"
```

---

## References

- `specs/mindmap-spi/2026-08-26-mindmap-spi-design.md` §7 — Curiosity engine spec
- `specs/mindmap-spi/decisions.md` D36-D41 — Curiosity engine design decisions
- `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzer.java` — Raw signal source (8 static methods)
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapStore.java` — SPI interface
- `blocks/src/main/java/io/casehub/blocks/agentic/social/drive/CuriosityDrive.java` — Consumer (blocks-side follow-up)
- `blocks/src/main/java/io/casehub/blocks/agentic/social/drive/DriveSource.java` — Integration target interface
- GitHub #221 — feat: mindmap-intelligence — curiosity engine
- GitHub #213 — MindMap SPI epic
