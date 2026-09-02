# Trajectory-Aware Curiosity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #242 — Trajectory-aware curiosity
**Issue group:** #253, #242

**Goal:** Update CuriositySignalGenerator affect dampening to use trajectory slope instead of PAD snapshot.

**Architecture:** Add memory-api + cognitive-index dependencies, inject Instance<CaseMemoryStore>, replace snapshot dampening with trajectory-based logic via AffectTrajectoryAnalyzer. CuriosityConfig record absorbs existing constants and adds trajectory thresholds.

**Tech Stack:** Java 21, Quarkus CDI, JUnit 5, AssertJ

## Global Constraints

- Java 21 source level, Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- `Instance<T>` for graceful degradation (no hard dependency on CaseMemoryStore)

---

## Batch 1: Trajectory-Aware Affect Dampening

### Task 1: CuriosityConfig record + pom dependency updates

**Files:**
- Create: `../../mindmap-api/src/main/java/io/casehub/neocortex/mindmap/CuriosityConfig.java`
- Modify: `mindmap-intelligence/pom.xml` — add memory-api + cognitive-index dependencies
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGenerator.java` — replace hardcoded constants with CuriosityConfig
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGeneratorTest.java` — update constructor calls

**Interfaces:**
- Produces: `CuriosityConfig` record with `defaults()` factory
- Produces: Updated `CuriositySignalGenerator` constructor accepting `Instance<CuriosityConfig>`

- [ ] **Step 1: Create CuriosityConfig record**

```java
package io.casehub.neocortex.mindmap.intelligence;

public record CuriosityConfig(
    double proximityScale,
    long staleDaysThreshold,
    int maxBfsDepth,
    int topCentrality,
    double volatilityThreshold,
    double maxBoostFactor,
    double minDampenFactor,
    double improvingDampenCap,
    double volatilityBoostCap,
    int trajectoryLimit
) {
    public static CuriosityConfig defaults() {
        return new CuriosityConfig(7.0, 90, 4, 3, 0.3, 1.0, 0.1, 0.7, 0.5, 20);
    }
}
```

- [ ] **Step 2: Add dependencies to pom.xml**

Add to `mindmap-intelligence/pom.xml` `<dependencies>`:

```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-memory-api</artifactId>
</dependency>
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-cognitive-index</artifactId>
</dependency>
```

- [ ] **Step 3: Update CuriositySignalGenerator constructor**

Add `Instance<CaseMemoryStore>` and `Instance<CuriosityConfig>` to constructor. Replace hardcoded constants with config fields. Keep existing behavior — just wire through config values.

```java
private final MindMapStore store;
private final CaseMemoryStore memoryStore;
private final CuriosityConfig config;

@Inject
public CuriositySignalGenerator(MindMapStore store,
                                 Instance<CaseMemoryStore> memoryStore,
                                 Instance<CuriosityConfig> config) {
    this.store = store;
    this.memoryStore = memoryStore.isResolvable() ? memoryStore.get() : null;
    this.config = config.isResolvable() ? config.get() : CuriosityConfig.defaults();
}
```

Replace all constant references:
- `PROXIMITY_SCALE` → `config.proximityScale()`
- `STALE_THRESHOLD` → `Duration.ofDays(config.staleDaysThreshold())`
- `MAX_BFS_DEPTH` → `config.maxBfsDepth()`
- `TOP_CENTRALITY` → `config.topCentrality()`

- [ ] **Step 4: Update existing tests to use new constructor**

In `CuriositySignalGeneratorTest.java`, update the constructor call to pass null/defaults:

```java
var generator = new CuriositySignalGenerator(store, null, CuriosityConfig.defaults());
```

Add a test-friendly constructor:

```java
CuriositySignalGenerator(MindMapStore store, CaseMemoryStore memoryStore, CuriosityConfig config) {
    this.store = store;
    this.memoryStore = memoryStore;
    this.config = config != null ? config : CuriosityConfig.defaults();
}
```

- [ ] **Step 5: Run existing tests — verify they still pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CuriositySignalGeneratorTest`
Expected: all existing tests pass (behavior unchanged)

- [ ] **Step 6: Commit**

```
refactor(mindmap-intelligence): CuriosityConfig record, add memory-api + cognitive-index deps

Extract hardcoded constants into CuriosityConfig record. Add
Instance<CaseMemoryStore> for trajectory access (graceful degradation).

Refs #242
```

### Task 2: Trajectory-based applyAffectDampening

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGenerator.java` — replace `applyAffectDampening`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGeneratorTest.java` — add trajectory tests

**Interfaces:**
- Consumes: `CaseMemoryStore.query()`, `AffectTrajectoryAnalyzer.analyze()`, `AffectEvents.DOMAIN`, `MemoryQuery.forEntity()`
- Consumes: `CuriosityConfig` thresholds

- [ ] **Step 1: Write failing tests for trajectory dampening**

Add to `CuriositySignalGeneratorTest.java`:

```java
@Test
void worseningTrajectory_boostsCuriosity() {
    // Create a node with worsening affect trajectory (decreasing pleasure over time)
    // Verify signal score is multiplied by factor > 1.0
}

@Test
void stableNegative_dampensAsSnapshot() {
    // Create a node with stable negative pleasure (flat trajectory)
    // Verify signal score is dampened (factor < 1.0)
}

@Test
void improvingTrajectory_dampensCuriosity() {
    // Create a node with improving affect trajectory (increasing pleasure)
    // Verify signal score is dampened
}

@Test
void highVolatility_boostsCuriosity() {
    // Create a node with volatile arousal (high stddev)
    // Verify volatility boost is applied
}

@Test
void proximitySignals_participateInTrajectory() {
    // Create a future-dated node with worsening trajectory
    // Verify PROXIMITY signal score is boosted
}

@Test
void noMemoryStore_fallsBackToSnapshot() {
    // CuriositySignalGenerator with null CaseMemoryStore
    // Verify current snapshot dampening behavior
}

@Test
void customConfig_changesThresholds() {
    // Pass custom CuriosityConfig with different thresholds
    // Verify the thresholds are respected
}
```

Tests use `InMemoryMindMapStore` + a mock/stub `CaseMemoryStore` that returns pre-constructed `Memory` objects with specific PAD values and timestamps to produce known trajectories.

- [ ] **Step 2: Implement trajectory-based applyAffectDampening**

Replace the method body:

```java
private void applyAffectDampening(List<CuriositySignal> signals, String tenantId) {
    Map<String, AffectTrajectory> trajectoryCache = new HashMap<>();

    for (int i = 0; i < signals.size(); i++) {
        CuriositySignal signal = signals.get(i);
        if (signal.targetNodeId() == null) continue;

        MindMapNode node = store.getNode(signal.targetNodeId(), tenantId);
        if (node == null) continue;

        double factor = computeTrajectoryFactor(signal.targetNodeId(), node, tenantId, trajectoryCache);
        if (factor != 1.0) {
            signals.set(i, new CuriositySignal(
                signal.category(), signal.score() * factor,
                signal.targetNodeId(), signal.targetSubgraphId(),
                signal.question(), signal.description()));
        }
    }
}

private double computeTrajectoryFactor(String nodeId, MindMapNode node,
                                        String tenantId,
                                        Map<String, AffectTrajectory> cache) {
    if (memoryStore == null) return snapshotFactor(node);

    AffectTrajectory trajectory = cache.computeIfAbsent(nodeId,
        id -> computeTrajectory(id, tenantId));

    if (trajectory.sampleCount() < 2) return snapshotFactor(node);

    double factor = switch (trajectory.trend()) {
        case WORSENING -> 1.0 + Math.min(config.maxBoostFactor(), Math.abs(trajectory.pleasureSlope()));
        case IMPROVING -> Math.max(config.minDampenFactor(),
            1.0 - Math.min(config.improvingDampenCap(), Math.abs(trajectory.pleasureSlope())));
        case STABLE -> {
            double p = node.pleasure() != null ? node.pleasure() : 0.0;
            yield p < 0 ? Math.max(config.minDampenFactor(), 1.0 + p) : 1.0;
        }
    };

    if (trajectory.arousalVolatility() > config.volatilityThreshold()) {
        factor *= 1.0 + Math.min(config.volatilityBoostCap(), trajectory.arousalVolatility());
    }

    return factor;
}

private double snapshotFactor(MindMapNode node) {
    if (node.pleasure() != null && node.pleasure() < 0) {
        return Math.max(config.minDampenFactor(), 1.0 + node.pleasure());
    }
    return 1.0;
}

private AffectTrajectory computeTrajectory(String nodeId, String tenantId) {
    var query = MemoryQuery.forEntity(nodeId, AffectEvents.DOMAIN, tenantId)
        .withLimit(config.trajectoryLimit());
    List<Memory> memories = memoryStore.query(query);
    return AffectTrajectoryAnalyzer.analyze(memories);
}
```

- [ ] **Step 3: Add required imports**

```java
import io.casehub.neocortex.cognitive.index.AffectTrajectory;
import io.casehub.neocortex.cognitive.index.AffectTrajectoryAnalyzer;
import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryQuery;
import io.casehub.neocortex.memory.mood.AffectEvents;
import jakarta.enterprise.inject.Instance;
```

- [ ] **Step 4: Run tests — verify all pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CuriositySignalGeneratorTest`
Expected: all tests pass (existing + 7 new)

- [ ] **Step 5: Full build verification**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl cognitive-api,cognitive-index,memory-api,mindmap-api,mindmap-inmem,mindmap,mindmap-intelligence`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```
feat(mindmap-intelligence): trajectory-aware affect dampening

CuriositySignalGenerator uses AffectTrajectoryAnalyzer slope instead
of PAD snapshot. Worsening boosts, improving dampens, volatility
boosts. PROXIMITY signals participate. Configurable via CuriosityConfig.

Refs #242
```

### Task 3: Documentation

**Files:**
- Modify: `docs/guides/cognitive-architecture-roadmap.md` — mark §3e DONE
- Modify: `CLAUDE.md` — update mindmap-intelligence description

- [ ] **Step 1: Mark roadmap §3e DONE**
- [ ] **Step 2: Update CLAUDE.md mindmap-intelligence description**
- [ ] **Step 3: Commit**

```
docs: mark roadmap §3e DONE, update CLAUDE.md for trajectory curiosity

Refs #242
```

## References

- `specs/issue-253-cognitive-rearchitecture/2026-08-31-trajectory-aware-curiosity-design.md` — design spec
- `CuriositySignalGenerator.java:182-197` — current applyAffectDampening
- `AffectTrajectoryAnalyzer.java` — trajectory computation
- `AffectTrajectoryDecorator.java` — Instance<CaseMemoryStore> pattern
- `cognitive-architecture-roadmap.md` §3e
- Decisions D27-D29
- GitHub #242
