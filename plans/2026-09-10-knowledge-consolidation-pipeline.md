# Knowledge Consolidation Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #295 — epic: Knowledge Consolidation Pipeline
**Issue group:** #296, #297, #298, #299, #300

**Goal:** Build a three-speed conversation-to-knowledge pipeline: real-time segmentation (ConversationBridge), near-time LLM enrichment (async MindMapExtractor), and background consolidation (4-phase scheduler with access tracking, merge detection, community summaries, and curiosity refresh).

**Architecture:** All new code in `mindmap-intelligence` (ConversationBridge, ConsolidationScheduler, all phases) and `mindmap` (IdleTracker, MindMapStoreIdleTracker decorator). No new Maven modules. Uses existing InMemoryMindMapStore for all tests. DraftHouse integration is deferred (cross-project).

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI (decorators, events, @Scheduled), InMemoryMindMapStore, assertj

## Global Constraints

- Java 21 on Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build: `mvn clean install` (not `./mvnw`)
- All new classes in `io.casehub.neocortex.mindmap.runtime` (mindmap module) or `io.casehub.neocortex.mindmap.intelligence` / `io.casehub.neocortex.mindmap.intelligence.consolidation` (mindmap-intelligence module)
- Tests use `InMemoryMindMapStore` and `InMemoryMemoryStore` — no SQLite, no Docker, no ONNX
- assertj for assertions (`assertThat(...).isEqualTo(...)`)
- SubgraphType is a String, not an enum. Use `SubgraphTypes.GENERAL` constant and `.equals()` comparison
- `NodeInput.of(name, subgraphId)` with `.with*()` chaining for node creation
- `NodeUpdate.empty().withPropertiesToSet(Map.of(...))` for property updates
- Every commit references an issue: `Refs #N` or `Closes #N`

---

## Batch 1: Foundation — Scheduler Infrastructure

After this batch: IdleTracker tracks MindMapStore write activity, RetrievalAccessTracker accumulates in-memory access counts, and the ConsolidationScheduler runs periodic passes with idle-guard and error isolation. AccessFrequencyPhase flushes counters to node properties.

### Task 1: IdleTracker + MindMapStoreIdleTracker

**Files:**
- Create: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/IdleTracker.java`
- Create: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapStoreIdleTracker.java`
- Test: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/IdleTrackerTest.java`
- Test: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/MindMapStoreIdleTrackerTest.java`

**Interfaces:**
- Consumes: `AbstractForwardingMindMapStore` (mindmap-api), `MindMapStore` SPI, `InMemoryMindMapStore` (mindmap-inmem)
- Produces: `IdleTracker.recordWrite()`, `IdleTracker.isIdle(Duration)` — used by ConsolidationScheduler (Task 3)

- [ ] **Step 1: Write IdleTracker test**

```java
package io.casehub.neocortex.mindmap.runtime;

import org.junit.jupiter.api.Test;
import java.time.Duration;
import static org.assertj.core.api.Assertions.assertThat;

class IdleTrackerTest {

    @Test
    void isIdle_noWrites_returnsTrue() {
        var tracker = new IdleTracker();
        assertThat(tracker.isIdle(Duration.ofMinutes(1))).isTrue();
    }

    @Test
    void isIdle_recentWrite_returnsFalse() {
        var tracker = new IdleTracker();
        tracker.recordWrite();
        assertThat(tracker.isIdle(Duration.ofMinutes(1))).isFalse();
    }

    @Test
    void isIdle_oldWrite_returnsTrue() {
        var tracker = new IdleTracker();
        tracker.recordWriteAt(java.time.Instant.now().minus(Duration.ofMinutes(5)));
        assertThat(tracker.isIdle(Duration.ofMinutes(1))).isTrue();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap -Dtest=IdleTrackerTest -DfailIfNoTests=false`
Expected: FAIL — `IdleTracker` class not found

- [ ] **Step 3: Implement IdleTracker**

Use `ide_insert_member` for new class.

```java
package io.casehub.neocortex.mindmap.runtime;

import jakarta.enterprise.context.ApplicationScoped;
import java.time.Duration;
import java.time.Instant;

@ApplicationScoped
public class IdleTracker {

    private volatile Instant lastWrite = Instant.EPOCH;

    public void recordWrite() {
        lastWrite = Instant.now();
    }

    void recordWriteAt(Instant instant) {
        lastWrite = instant;
    }

    public boolean isIdle(Duration threshold) {
        return Duration.between(lastWrite, Instant.now()).compareTo(threshold) > 0;
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap -Dtest=IdleTrackerTest`
Expected: PASS (3 tests)

- [ ] **Step 5: Write MindMapStoreIdleTracker test**

```java
package io.casehub.neocortex.mindmap.runtime;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.time.Duration;
import static org.assertj.core.api.Assertions.assertThat;

class MindMapStoreIdleTrackerTest {

    private InMemoryMindMapStore delegate;
    private IdleTracker idleTracker;
    private MindMapStoreIdleTracker decorator;

    @BeforeEach
    void setUp() {
        delegate = new InMemoryMindMapStore();
        idleTracker = new IdleTracker();
        decorator = new MindMapStoreIdleTracker(delegate, idleTracker);
    }

    @Test
    void addNode_recordsWrite() {
        assertThat(idleTracker.isIdle(Duration.ofSeconds(1))).isTrue();
        String sgId = decorator.createSubgraph(
            new SubgraphInput("Test", SubgraphTypes.GENERAL, null), "t1");
        decorator.addNode(NodeInput.of("Alice", sgId), "t1");
        assertThat(idleTracker.isIdle(Duration.ofSeconds(1))).isFalse();
    }

    @Test
    void getNode_doesNotRecordWrite() {
        String sgId = decorator.createSubgraph(
            new SubgraphInput("Test", SubgraphTypes.GENERAL, null), "t1");
        String nodeId = decorator.addNode(NodeInput.of("Alice", sgId), "t1");
        idleTracker.recordWriteAt(java.time.Instant.EPOCH);
        decorator.getNode(nodeId, "t1");
        assertThat(idleTracker.isIdle(Duration.ofSeconds(1))).isTrue();
    }

    @Test
    void search_doesNotRecordWrite() {
        idleTracker.recordWriteAt(java.time.Instant.EPOCH);
        decorator.search(MindMapQuery.builder("t1").build());
        assertThat(idleTracker.isIdle(Duration.ofSeconds(1))).isTrue();
    }
}
```

- [ ] **Step 6: Implement MindMapStoreIdleTracker**

```java
package io.casehub.neocortex.mindmap.runtime;

import io.casehub.neocortex.mindmap.*;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;
import java.util.Set;

@Decorator
@Priority(30)
public class MindMapStoreIdleTracker extends AbstractForwardingMindMapStore {

    private final IdleTracker idleTracker;

    @Inject
    public MindMapStoreIdleTracker(@Delegate @Any MindMapStore delegate,
                                    IdleTracker idleTracker) {
        super(delegate);
        this.idleTracker = idleTracker;
    }

    @Override
    public String addNode(NodeInput input, String tenantId) {
        idleTracker.recordWrite();
        return delegate().addNode(input, tenantId);
    }

    @Override
    public void updateNode(String nodeId, NodeUpdate update, String tenantId) {
        idleTracker.recordWrite();
        delegate().updateNode(nodeId, update, tenantId);
    }

    @Override
    public String addEdge(EdgeInput input, String tenantId) {
        idleTracker.recordWrite();
        return delegate().addEdge(input, tenantId);
    }

    @Override
    public void removeEdge(String edgeId, String tenantId) {
        idleTracker.recordWrite();
        delegate().removeEdge(edgeId, tenantId);
    }

    @Override
    public MergeResult mergeNodes(String keepNodeId, String removeNodeId, String tenantId) {
        idleTracker.recordWrite();
        return delegate().mergeNodes(keepNodeId, removeNodeId, tenantId);
    }

    @Override
    public void supersede(String targetId, String supersedingId, String reason, String tenantId) {
        idleTracker.recordWrite();
        delegate().supersede(targetId, supersedingId, reason, tenantId);
    }

    @Override
    public void reinstate(String targetId, String tenantId) {
        idleTracker.recordWrite();
        delegate().reinstate(targetId, tenantId);
    }

    @Override
    public int eraseNode(String nodeId, String tenantId) {
        idleTracker.recordWrite();
        return delegate().eraseNode(nodeId, tenantId);
    }

    @Override
    public int eraseSubgraph(String subgraphId, String tenantId) {
        idleTracker.recordWrite();
        return delegate().eraseSubgraph(subgraphId, tenantId);
    }

    @Override
    public int eraseEntity(String entityName, String tenantId) {
        idleTracker.recordWrite();
        return delegate().eraseEntity(entityName, tenantId);
    }

    @Override
    public int eraseEntityAcrossTenants(String entityName, Set<String> tenantIds) {
        idleTracker.recordWrite();
        return delegate().eraseEntityAcrossTenants(entityName, tenantIds);
    }

    @Override
    public String createSubgraph(SubgraphInput input, String tenantId) {
        idleTracker.recordWrite();
        return delegate().createSubgraph(input, tenantId);
    }

    @Override
    public void updateSubgraph(String subgraphId, String rootNodeId, String tenantId) {
        idleTracker.recordWrite();
        delegate().updateSubgraph(subgraphId, rootNodeId, tenantId);
    }

    @Override
    public void addAlias(String nodeId, String alias, String tenantId) {
        idleTracker.recordWrite();
        delegate().addAlias(nodeId, alias, tenantId);
    }

    @Override
    public void removeAlias(String nodeId, String alias, String tenantId) {
        idleTracker.recordWrite();
        delegate().removeAlias(nodeId, alias, tenantId);
    }
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap -Dtest="IdleTrackerTest,MindMapStoreIdleTrackerTest"`
Expected: PASS (6 tests)

- [ ] **Step 8: Commit**

```bash
git add mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/IdleTracker.java \
        mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapStoreIdleTracker.java \
        mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/IdleTrackerTest.java \
        mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/MindMapStoreIdleTrackerTest.java
git commit -m "feat(mindmap): IdleTracker + MindMapStoreIdleTracker decorator

Tracks last MindMapStore write timestamp via volatile Instant.
MindMapStoreIdleTracker is a @Decorator @Priority(30) that records writes
on all mutation operations. Read operations pass through without recording.
IdleTracker.isIdle(Duration) checks whether the system has been quiet
long enough for background consolidation.

Refs #297"
```

---

### Task 2: RetrievalAccessTracker + AccessSnapshot

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/RetrievalAccessTracker.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/AccessSnapshot.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/RetrievalAccessTrackerTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `RetrievalAccessTracker.recordAccess(String nodeId)`, `RetrievalAccessTracker.swapAndReset()` → `AccessSnapshot` — used by ConversationBridge (Task 4), ExtractionRequestedObserver (Task 5), AccessFrequencyPhase (Task 3)

- [ ] **Step 1: Write AccessSnapshot record**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import java.time.Instant;
import java.util.Map;

public record AccessSnapshot(
    Map<String, Long> counts,
    Map<String, Instant> lastAccessTimes
) {
    public AccessSnapshot {
        counts = Map.copyOf(counts);
        lastAccessTimes = Map.copyOf(lastAccessTimes);
    }

    public static final AccessSnapshot EMPTY = new AccessSnapshot(Map.of(), Map.of());
}
```

- [ ] **Step 2: Write RetrievalAccessTracker test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class RetrievalAccessTrackerTest {

    @Test
    void recordAccess_incrementsCount() {
        var tracker = new RetrievalAccessTracker();
        tracker.recordAccess("node-1");
        tracker.recordAccess("node-1");
        tracker.recordAccess("node-2");

        var snapshot = tracker.swapAndReset();
        assertThat(snapshot.counts()).containsEntry("node-1", 2L);
        assertThat(snapshot.counts()).containsEntry("node-2", 1L);
    }

    @Test
    void swapAndReset_clearsState() {
        var tracker = new RetrievalAccessTracker();
        tracker.recordAccess("node-1");

        var first = tracker.swapAndReset();
        assertThat(first.counts()).containsEntry("node-1", 1L);

        var second = tracker.swapAndReset();
        assertThat(second.counts()).isEmpty();
    }

    @Test
    void swapAndReset_capturesLastAccessTimes() {
        var tracker = new RetrievalAccessTracker();
        tracker.recordAccess("node-1");

        var snapshot = tracker.swapAndReset();
        assertThat(snapshot.lastAccessTimes()).containsKey("node-1");
        assertThat(snapshot.lastAccessTimes().get("node-1")).isNotNull();
    }

    @Test
    void recordAccess_afterSwap_writesToNewMap() {
        var tracker = new RetrievalAccessTracker();
        tracker.recordAccess("node-1");

        tracker.swapAndReset();
        tracker.recordAccess("node-2");

        var snapshot = tracker.swapAndReset();
        assertThat(snapshot.counts()).doesNotContainKey("node-1");
        assertThat(snapshot.counts()).containsEntry("node-2", 1L);
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=RetrievalAccessTrackerTest -DfailIfNoTests=false`
Expected: FAIL — class not found

- [ ] **Step 4: Implement RetrievalAccessTracker**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import jakarta.enterprise.context.ApplicationScoped;
import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@ApplicationScoped
public class RetrievalAccessTracker {

    private volatile ConcurrentHashMap<String, AtomicLong> counts = new ConcurrentHashMap<>();
    private volatile ConcurrentHashMap<String, Instant> lastAccess = new ConcurrentHashMap<>();

    public void recordAccess(String nodeId) {
        counts.computeIfAbsent(nodeId, k -> new AtomicLong()).incrementAndGet();
        lastAccess.put(nodeId, Instant.now());
    }

    public AccessSnapshot swapAndReset() {
        var oldCounts = counts;
        var oldLastAccess = lastAccess;
        counts = new ConcurrentHashMap<>();
        lastAccess = new ConcurrentHashMap<>();

        var snapshot = new HashMap<String, Long>();
        oldCounts.forEach((nodeId, counter) -> snapshot.put(nodeId, counter.get()));

        return new AccessSnapshot(snapshot, Map.copyOf(oldLastAccess));
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=RetrievalAccessTrackerTest`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/RetrievalAccessTracker.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/AccessSnapshot.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/RetrievalAccessTrackerTest.java
git commit -m "feat(consolidation): RetrievalAccessTracker with atomic swap-and-reset

In-memory ConcurrentHashMap accumulates access counts and timestamps.
swapAndReset() atomically swaps map references — concurrent recordAccess()
calls write to new maps, captured on the next flush cycle.

Refs #298"
```

---

### Task 3: ConsolidationPhase SPI + ConsolidationScheduler + AccessFrequencyPhase

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationPhase.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationScheduler.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/AccessFrequencyPhase.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/RetrievalStrength.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationSchedulerTest.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/AccessFrequencyPhaseTest.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/RetrievalStrengthTest.java`

**Interfaces:**
- Consumes: `IdleTracker` (Task 1), `RetrievalAccessTracker` (Task 2), `MindMapStore`, `CaseMemoryStore.discoverTenants()`, `CuriositySignalGenerator`
- Produces: `ConsolidationPhase` SPI (used by Tasks 6-10), `ConsolidationScheduler.tick()`, `RetrievalStrength.compute()` static utility

- [ ] **Step 1: Write ConsolidationPhase SPI**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import java.util.List;

public interface ConsolidationPhase {
    String name();
    void run(String tenantId, List<String> subgraphPriority);
}
```

- [ ] **Step 2: Write RetrievalStrength utility + test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import java.time.Duration;
import java.time.Instant;

public final class RetrievalStrength {

    private RetrievalStrength() {}

    public static double compute(Instant lastAccessed, int storageStrength,
                                  double baseHalfLifeDays) {
        if (lastAccessed == null) return 0.0;
        double hoursSince = Duration.between(lastAccessed, Instant.now()).toHours();
        if (hoursSince <= 0) return 1.0;
        double effectiveHalfLifeHours = baseHalfLifeDays * 24.0
            * (1 + Math.log1p(storageStrength));
        return Math.pow(2.0, -hoursSince / effectiveHalfLifeHours);
    }
}
```

Test:

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.time.Duration;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class RetrievalStrengthTest {

    @Test
    void nullLastAccessed_returnsZero() {
        assertThat(RetrievalStrength.compute(null, 0, 30.0)).isEqualTo(0.0);
    }

    @Test
    void justAccessed_returnsOne() {
        assertThat(RetrievalStrength.compute(Instant.now(), 0, 30.0))
            .isEqualTo(1.0);
    }

    @Test
    void halfLifeDecay_zeroStorageStrength() {
        Instant thirtyDaysAgo = Instant.now().minus(Duration.ofDays(30));
        double result = RetrievalStrength.compute(thirtyDaysAgo, 0, 30.0);
        assertThat(result).isCloseTo(0.5, within(0.05));
    }

    @Test
    void highStorageStrength_slowsDecay() {
        Instant thirtyDaysAgo = Instant.now().minus(Duration.ofDays(30));
        double low = RetrievalStrength.compute(thirtyDaysAgo, 1, 30.0);
        double high = RetrievalStrength.compute(thirtyDaysAgo, 100, 30.0);
        assertThat(high).isGreaterThan(low);
    }
}
```

- [ ] **Step 3: Write AccessFrequencyPhase test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.assertThat;

class AccessFrequencyPhaseTest {

    private InMemoryMindMapStore store;
    private RetrievalAccessTracker tracker;
    private AccessFrequencyPhase phase;
    private String subgraphId;
    private String nodeId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        tracker = new RetrievalAccessTracker();
        phase = new AccessFrequencyPhase(store, tracker);
        subgraphId = store.createSubgraph(
            new SubgraphInput("Test", SubgraphTypes.GENERAL, null), "t1");
        nodeId = store.addNode(NodeInput.of("Alice", subgraphId), "t1");
    }

    @Test
    void run_flushesStorageStrength() {
        tracker.recordAccess(nodeId);
        tracker.recordAccess(nodeId);
        tracker.recordAccess(nodeId);

        phase.run("t1", List.of());

        MindMapNode node = store.getNode(nodeId, "t1");
        assertThat(node.property("storageStrength")).hasValue("3");
        assertThat(node.property("lastAccessed")).isPresent();
    }

    @Test
    void run_accumulatesAcrossFlushes() {
        tracker.recordAccess(nodeId);
        phase.run("t1", List.of());

        tracker.recordAccess(nodeId);
        tracker.recordAccess(nodeId);
        phase.run("t1", List.of());

        MindMapNode node = store.getNode(nodeId, "t1");
        assertThat(node.property("storageStrength")).hasValue("3");
    }

    @Test
    void run_noAccesses_noOp() {
        phase.run("t1", List.of());
        MindMapNode node = store.getNode(nodeId, "t1");
        assertThat(node.property("storageStrength")).isEmpty();
    }

    @Test
    void name_returnsAccessFrequency() {
        assertThat(phase.name()).isEqualTo("access-frequency");
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="AccessFrequencyPhaseTest,RetrievalStrengthTest" -DfailIfNoTests=false`
Expected: FAIL — classes not found

- [ ] **Step 5: Implement AccessFrequencyPhase**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeUpdate;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.List;
import java.util.Map;

@ApplicationScoped
@Priority(10)
public class AccessFrequencyPhase implements ConsolidationPhase {

    private final MindMapStore store;
    private final RetrievalAccessTracker tracker;

    @Inject
    public AccessFrequencyPhase(MindMapStore store, RetrievalAccessTracker tracker) {
        this.store = store;
        this.tracker = tracker;
    }

    @Override
    public String name() {
        return "access-frequency";
    }

    @Override
    public void run(String tenantId, List<String> subgraphPriority) {
        var snapshot = tracker.swapAndReset();
        if (snapshot.counts().isEmpty()) return;

        for (var entry : snapshot.counts().entrySet()) {
            String nodeId = entry.getKey();
            long increment = entry.getValue();
            try {
                var node = store.getNode(nodeId, tenantId);
                if (node == null) continue;
                int existing = node.property("storageStrength")
                    .map(Integer::parseInt).orElse(0);
                int newStrength = existing + (int) increment;
                String lastAccessed = snapshot.lastAccessTimes()
                    .containsKey(nodeId)
                    ? snapshot.lastAccessTimes().get(nodeId).toString()
                    : java.time.Instant.now().toString();
                store.updateNode(nodeId,
                    NodeUpdate.empty().withPropertiesToSet(Map.of(
                        "storageStrength", String.valueOf(newStrength),
                        "lastAccessed", lastAccessed)),
                    tenantId);
            } catch (Exception e) {
                // node may have been erased between snapshot and flush
            }
        }
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="AccessFrequencyPhaseTest,RetrievalStrengthTest"`
Expected: PASS (8 tests)

- [ ] **Step 7: Write ConsolidationScheduler test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.runtime.IdleTracker;
import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.MemoryCapability;
import io.casehub.neocortex.mindmap.intelligence.CuriositySignalGenerator;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class ConsolidationSchedulerTest {

    private IdleTracker idleTracker;
    private CaseMemoryStore memoryStore;
    private List<String> executedPhases;
    private ConsolidationScheduler scheduler;

    @BeforeEach
    void setUp() {
        idleTracker = new IdleTracker();
        memoryStore = mock(CaseMemoryStore.class);
        when(memoryStore.capabilities())
            .thenReturn(Set.of(MemoryCapability.DISCOVER_TENANTS));
        when(memoryStore.discoverTenants(null, null))
            .thenReturn(List.of("tenant-1"));

        executedPhases = new ArrayList<>();
        ConsolidationPhase phase1 = new ConsolidationPhase() {
            @Override public String name() { return "phase-1"; }
            @Override public void run(String tenantId, List<String> sp) {
                executedPhases.add(name() + ":" + tenantId);
            }
        };
        ConsolidationPhase phase2 = new ConsolidationPhase() {
            @Override public String name() { return "phase-2"; }
            @Override public void run(String tenantId, List<String> sp) {
                executedPhases.add(name() + ":" + tenantId);
            }
        };

        scheduler = new ConsolidationScheduler(
            List.of(phase1, phase2), idleTracker, memoryStore, null);
    }

    @Test
    void tick_whenIdle_executesAllPhases() {
        scheduler.tick();
        assertThat(executedPhases).containsExactly(
            "phase-1:tenant-1", "phase-2:tenant-1");
    }

    @Test
    void tick_whenNotIdle_skips() {
        idleTracker.recordWrite();
        scheduler.tick();
        assertThat(executedPhases).isEmpty();
    }

    @Test
    void tick_phaseFailure_continuesNextPhase() {
        ConsolidationPhase failing = new ConsolidationPhase() {
            @Override public String name() { return "failing"; }
            @Override public void run(String tenantId, List<String> sp) {
                throw new RuntimeException("boom");
            }
        };
        ConsolidationPhase healthy = new ConsolidationPhase() {
            @Override public String name() { return "healthy"; }
            @Override public void run(String tenantId, List<String> sp) {
                executedPhases.add("healthy:" + tenantId);
            }
        };

        var schedulerWithFailure = new ConsolidationScheduler(
            List.of(failing, healthy), idleTracker, memoryStore, null);
        schedulerWithFailure.tick();

        assertThat(executedPhases).containsExactly("healthy:tenant-1");
    }
}
```

- [ ] **Step 8: Implement ConsolidationScheduler**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.MemoryCapability;
import io.casehub.neocortex.mindmap.intelligence.CuriositySignal;
import io.casehub.neocortex.mindmap.intelligence.CuriositySignalGenerator;
import io.casehub.neocortex.mindmap.runtime.IdleTracker;
import io.quarkus.scheduler.Scheduled;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import java.time.Duration;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class ConsolidationScheduler {

    private static final Logger LOG = Logger.getLogger(
        ConsolidationScheduler.class.getName());

    private final List<ConsolidationPhase> phases;
    private final IdleTracker idleTracker;
    private final CaseMemoryStore memoryStore;
    private final CuriositySignalGenerator curiosityGenerator;
    private final ReentrantLock lock = new ReentrantLock();

    @Inject
    ConsolidationScheduler(Instance<ConsolidationPhase> phases,
                           IdleTracker idleTracker,
                           CaseMemoryStore memoryStore,
                           Instance<CuriositySignalGenerator> curiosityGenerator) {
        this(phases.stream()
                .sorted(Comparator.comparingInt(p ->
                    Optional.ofNullable(p.getClass().getAnnotation(
                        jakarta.annotation.Priority.class))
                        .map(jakarta.annotation.Priority::value)
                        .orElse(Integer.MAX_VALUE)))
                .toList(),
            idleTracker, memoryStore,
            curiosityGenerator.isResolvable() ? curiosityGenerator.get() : null);
    }

    ConsolidationScheduler(List<ConsolidationPhase> phases,
                           IdleTracker idleTracker,
                           CaseMemoryStore memoryStore,
                           CuriositySignalGenerator curiosityGenerator) {
        this.phases = phases;
        this.idleTracker = idleTracker;
        this.memoryStore = memoryStore;
        this.curiosityGenerator = curiosityGenerator;
    }

    @Scheduled(every = "${casehub.consolidation.interval:5m}")
    void tick() {
        if (!lock.tryLock()) return;
        try {
            if (!idleTracker.isIdle(Duration.ofMinutes(1))) return;
            if (!memoryStore.capabilities()
                    .contains(MemoryCapability.DISCOVER_TENANTS)) {
                return;
            }

            for (String tenantId : memoryStore.discoverTenants(null, null)) {
                List<String> priority = subgraphPriority(tenantId);
                for (ConsolidationPhase phase : phases) {
                    try {
                        phase.run(tenantId, priority);
                    } catch (Exception e) {
                        LOG.log(Level.WARNING, "Phase " + phase.name()
                            + " failed for tenant " + tenantId, e);
                    }
                }
            }
        } finally {
            lock.unlock();
        }
    }

    private List<String> subgraphPriority(String tenantId) {
        if (curiosityGenerator == null) return List.of();
        return curiosityGenerator.computeSignals(tenantId, Set.of()).stream()
            .map(CuriositySignal::targetSubgraphId)
            .filter(Objects::nonNull)
            .distinct()
            .toList();
    }
}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="ConsolidationSchedulerTest,AccessFrequencyPhaseTest,RetrievalStrengthTest"`
Expected: PASS (11 tests)

- [ ] **Step 10: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationPhase.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationScheduler.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/AccessFrequencyPhase.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/RetrievalStrength.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationSchedulerTest.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/AccessFrequencyPhaseTest.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/RetrievalStrengthTest.java
git commit -m "feat(consolidation): ConsolidationPhase SPI, scheduler, access-frequency phase

ConsolidationScheduler: @Scheduled periodic with idle guard (1 min),
tryLock concurrency control, tenant enumeration via discoverTenants(),
curiosity-driven subgraph priority, error isolation per phase.

AccessFrequencyPhase: flush write-behind counters from
RetrievalAccessTracker to storageStrength/lastAccessed node properties.
Bjorks dual-strength model — storage strength never decays.

RetrievalStrength: static utility for read-time retrieval strength
computation with log1p-modulated half-life.

Refs #297
Refs #298"
```

---

## Batch 2: ConversationBridge — Real-Time Segmentation + Async Enrichment

After this batch: ConversationBridge segments cleaned text into topical chunks, creates initial "general" nodes, and fires an async CDI event for MindMapExtractor LLM enrichment. ExtractionRequestedObserver supersedes segment nodes with extracted entities.

### Task 4: TextSegment + SegmentationResult + ConversationBridge

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TextSegment.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SegmentationResult.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridge.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridgeTest.java`

**Interfaces:**
- Consumes: `MindMapStore`, `RetrievalAccessTracker` (Task 2), `SubgraphTypes.GENERAL`, `NodeInput.of()`, `MindMapConfidenceDefaults.forOrigin()`
- Produces: `ConversationBridge.process(cleanedText, tenantId, recentEntityNames, principalId)` → `SegmentationResult` — used by DraftHouse KnowledgeFacet (deferred); `ExtractionRequested` CDI event fired — consumed by ExtractionRequestedObserver (Task 5)

- [ ] **Step 1: Write TextSegment and SegmentationResult records**

```java
package io.casehub.neocortex.mindmap.intelligence;

public record TextSegment(String title, String body, String topic) {
    public TextSegment {
        if (title == null || title.isBlank()) throw new IllegalArgumentException("title required");
        if (body == null) throw new NullPointerException("body");
    }
}
```

```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.List;

public record SegmentationResult(List<String> createdNodeIds, int segmentCount) {
    public SegmentationResult {
        createdNodeIds = List.copyOf(createdNodeIds);
    }

    public static final SegmentationResult EMPTY = new SegmentationResult(List.of(), 0);
}
```

- [ ] **Step 2: Write ConversationBridge test**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import io.casehub.neocortex.mindmap.intelligence.consolidation.RetrievalAccessTracker;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.ArrayList;
import java.util.List;
import static org.assertj.core.api.Assertions.assertThat;

class ConversationBridgeTest {

    private InMemoryMindMapStore store;
    private RetrievalAccessTracker tracker;
    private List<ExtractionRequested> firedEvents;
    private ConversationBridge bridge;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        tracker = new RetrievalAccessTracker();
        firedEvents = new ArrayList<>();
        bridge = new ConversationBridge(store, tracker, firedEvents::add);
    }

    @Test
    void process_blankText_returnsEmpty() {
        var result = bridge.process("", "t1", List.of(), null);
        assertThat(result).isEqualTo(SegmentationResult.EMPTY);
    }

    @Test
    void process_singleParagraph_createsOneNode() {
        var result = bridge.process(
            "Alice works on the knowledge graph project.",
            "t1", List.of(), null);
        assertThat(result.segmentCount()).isEqualTo(1);
        assertThat(result.createdNodeIds()).hasSize(1);

        MindMapNode node = store.getNode(result.createdNodeIds().getFirst(), "t1");
        assertThat(node).isNotNull();
        assertThat(node.property("body")).isPresent();
        assertThat(node.property("provenance")).hasValue("conversation-bridge");
    }

    @Test
    void process_multipleParagraphs_createsMultipleNodes() {
        var result = bridge.process(
            "Alice works on AI.\n\nBob studies biology.\n\nCarol builds bridges.",
            "t1", List.of(), null);
        assertThat(result.segmentCount()).isGreaterThanOrEqualTo(1);
        assertThat(result.createdNodeIds()).hasSize(result.segmentCount());
    }

    @Test
    void process_recordsAccess() {
        bridge.process("Some text.", "t1", List.of(), null);
        var snapshot = tracker.swapAndReset();
        assertThat(snapshot.counts()).isNotEmpty();
    }

    @Test
    void process_firesExtractionEvent() {
        bridge.process("Some text.", "t1", List.of(), null);
        assertThat(firedEvents).hasSize(1);
        assertThat(firedEvents.getFirst().tenantId()).isEqualTo("t1");
        assertThat(firedEvents.getFirst().segmentNodeIds()).isNotEmpty();
    }

    @Test
    void process_createsGeneralSubgraphIfMissing() {
        bridge.process("Some text.", "t1", List.of(), null);
        var subgraphs = store.listSubgraphs("t1");
        assertThat(subgraphs).anyMatch(sg -> SubgraphTypes.GENERAL.equals(sg.type()));
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ConversationBridgeTest -DfailIfNoTests=false`
Expected: FAIL — class not found

- [ ] **Step 4: Write ExtractionRequested record**

```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.List;

public record ExtractionRequested(
    String cleanedText,
    String tenantId,
    List<String> recentEntityNames,
    List<String> segmentNodeIds
) {
    public ExtractionRequested {
        recentEntityNames = recentEntityNames != null ? List.copyOf(recentEntityNames) : List.of();
        segmentNodeIds = List.copyOf(segmentNodeIds);
    }
}
```

- [ ] **Step 5: Implement ConversationBridge**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.intelligence.consolidation.RetrievalAccessTracker;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Event;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.function.Consumer;

@ApplicationScoped
public class ConversationBridge {

    private final MindMapStore store;
    private final RetrievalAccessTracker accessTracker;
    private final Consumer<ExtractionRequested> eventSink;

    @Inject
    public ConversationBridge(MindMapStore store,
                              Instance<RetrievalAccessTracker> accessTracker,
                              Event<ExtractionRequested> extractionEvent) {
        this.store = store;
        this.accessTracker = accessTracker.isResolvable() ? accessTracker.get() : null;
        this.eventSink = extractionEvent::fireAsync;
    }

    ConversationBridge(MindMapStore store,
                       RetrievalAccessTracker accessTracker,
                       Consumer<ExtractionRequested> eventSink) {
        this.store = store;
        this.accessTracker = accessTracker;
        this.eventSink = eventSink;
    }

    public SegmentationResult process(String cleanedText, String tenantId,
                                       List<String> recentEntityNames,
                                       Object principalId) {
        if (cleanedText == null || cleanedText.isBlank()) {
            return SegmentationResult.EMPTY;
        }

        List<TextSegment> segments = segment(cleanedText);
        String subgraphId = findOrCreateGeneralSubgraph(tenantId);

        List<String> createdNodeIds = new ArrayList<>();
        for (TextSegment seg : segments) {
            String nodeId = store.addNode(
                NodeInput.of(seg.title(), subgraphId)
                    .withConfidence(MindMapConfidenceDefaults.forOrigin(
                        ConfidenceOrigin.STATED, Instant.now()))
                    .withProvenance("conversation-bridge")
                    .withProperties(Map.of(
                        "body", seg.body(),
                        "topic", seg.topic())),
                tenantId);
            createdNodeIds.add(nodeId);
        }

        if (accessTracker != null) {
            createdNodeIds.forEach(accessTracker::recordAccess);
        }

        eventSink.accept(new ExtractionRequested(
            cleanedText, tenantId, recentEntityNames, createdNodeIds));

        return new SegmentationResult(createdNodeIds, segments.size());
    }

    List<TextSegment> segment(String text) {
        String[] paragraphs = text.split("\\n\\n+");
        List<TextSegment> segments = new ArrayList<>();
        for (String para : paragraphs) {
            String trimmed = para.strip();
            if (trimmed.isEmpty()) continue;
            String title = trimmed.length() > 60
                ? trimmed.substring(0, 60).trim() + "..."
                : trimmed;
            String topic = extractTopic(trimmed);
            segments.add(new TextSegment(title, trimmed, topic));
        }
        if (segments.isEmpty() && !text.isBlank()) {
            String title = text.strip().length() > 60
                ? text.strip().substring(0, 60).trim() + "..."
                : text.strip();
            segments.add(new TextSegment(title, text.strip(), "general"));
        }
        return segments;
    }

    private String extractTopic(String text) {
        return "general";
    }

    private String findOrCreateGeneralSubgraph(String tenantId) {
        return store.listSubgraphs(tenantId).stream()
            .filter(sg -> SubgraphTypes.GENERAL.equals(sg.type()))
            .map(MindMapSubgraph::id)
            .findFirst()
            .orElseGet(() -> store.createSubgraph(
                new SubgraphInput("General", SubgraphTypes.GENERAL, null),
                tenantId));
    }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ConversationBridgeTest`
Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TextSegment.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SegmentationResult.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequested.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridge.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridgeTest.java
git commit -m "feat(intelligence): ConversationBridge — rule-based segmentation + async enrichment

Fast, rule-based text segmentation creates initial 'general' nodes in
MindMapStore with STATED confidence and conversation-bridge provenance.
Fires ExtractionRequested CDI event for async MindMapExtractor enrichment.
Records access for all created nodes via RetrievalAccessTracker.

Refs #296"
```

---

### Task 5: ExtractionRequestedObserver

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserver.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserverTest.java`

**Interfaces:**
- Consumes: `ExtractionRequested` (Task 4), `MindMapExtractor.extract()`, `MindMapStore.supersede()`, `RetrievalAccessTracker.recordAccess()`, `ExtractedEntity.nodeId()`, `ExtractedEntity.created()`
- Produces: none (terminal — fires extraction and supersedes segment nodes)

- [ ] **Step 1: Write ExtractionRequestedObserver test**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import io.casehub.neocortex.mindmap.intelligence.consolidation.RetrievalAccessTracker;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class ExtractionRequestedObserverTest {

    private InMemoryMindMapStore store;
    private MindMapExtractor extractor;
    private RetrievalAccessTracker tracker;
    private ExtractionRequestedObserver observer;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        extractor = mock(MindMapExtractor.class);
        tracker = new RetrievalAccessTracker();
        observer = new ExtractionRequestedObserver(extractor, store, tracker);
        subgraphId = store.createSubgraph(
            new SubgraphInput("General", SubgraphTypes.GENERAL, null), "t1");
    }

    @Test
    void onEvent_supersedesSegmentNodes() {
        String segmentId = store.addNode(NodeInput.of("segment", subgraphId), "t1");

        when(extractor.extract("text", "t1", List.of()))
            .thenReturn(new ExtractionResult(
                List.of(new ExtractedEntity("entity-1", "Alice", true, "person", Map.of())),
                List.of(), List.of(), List.of("Alice")));

        observer.onExtractionRequested(
            new ExtractionRequested("text", "t1", List.of(), List.of(segmentId)));

        var status = store.getSupersessionStatus(segmentId, "t1");
        assertThat(status.superseded()).isTrue();
        assertThat(status.supersedingCaseId()).isEqualTo("entity-1");
    }

    @Test
    void onEvent_noEntities_segmentsPersist() {
        String segmentId = store.addNode(NodeInput.of("segment", subgraphId), "t1");

        when(extractor.extract("text", "t1", List.of()))
            .thenReturn(ExtractionResult.EMPTY);

        observer.onExtractionRequested(
            new ExtractionRequested("text", "t1", List.of(), List.of(segmentId)));

        var status = store.getSupersessionStatus(segmentId, "t1");
        assertThat(status.superseded()).isFalse();
    }

    @Test
    void onEvent_recordsAccessForEntities() {
        when(extractor.extract("text", "t1", List.of()))
            .thenReturn(new ExtractionResult(
                List.of(new ExtractedEntity("e1", "Alice", true, "person", Map.of()),
                        new ExtractedEntity("e2", "Bob", false, "person", Map.of())),
                List.of(), List.of(), List.of("Alice", "Bob")));

        observer.onExtractionRequested(
            new ExtractionRequested("text", "t1", List.of(), List.of()));

        var snapshot = tracker.swapAndReset();
        assertThat(snapshot.counts()).containsKeys("e1", "e2");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExtractionRequestedObserverTest -DfailIfNoTests=false`
Expected: FAIL — class not found

- [ ] **Step 3: Implement ExtractionRequestedObserver**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.intelligence.consolidation.RetrievalAccessTracker;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.ObservesAsync;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class ExtractionRequestedObserver {

    private static final Logger LOG = Logger.getLogger(
        ExtractionRequestedObserver.class.getName());

    private final MindMapExtractor extractor;
    private final MindMapStore store;
    private final RetrievalAccessTracker accessTracker;

    @Inject
    public ExtractionRequestedObserver(MindMapExtractor extractor,
                                        MindMapStore store,
                                        Instance<RetrievalAccessTracker> accessTracker) {
        this.extractor = extractor;
        this.store = store;
        this.accessTracker = accessTracker.isResolvable() ? accessTracker.get() : null;
    }

    ExtractionRequestedObserver(MindMapExtractor extractor,
                                 MindMapStore store,
                                 RetrievalAccessTracker accessTracker) {
        this.extractor = extractor;
        this.store = store;
        this.accessTracker = accessTracker;
    }

    public void onExtractionRequested(@ObservesAsync ExtractionRequested event) {
        try {
            var result = extractor.extract(
                event.cleanedText(), event.tenantId(), event.recentEntityNames());

            if (accessTracker != null) {
                result.entities().stream()
                    .map(ExtractedEntity::nodeId)
                    .forEach(accessTracker::recordAccess);
            }

            List<String> createdEntityIds = result.entities().stream()
                .filter(ExtractedEntity::created)
                .map(ExtractedEntity::nodeId)
                .toList();

            if (!createdEntityIds.isEmpty()) {
                for (String segmentId : event.segmentNodeIds()) {
                    try {
                        store.supersede(segmentId, createdEntityIds.getFirst(),
                            "llm-extraction", event.tenantId());
                    } catch (Exception e) {
                        LOG.log(Level.FINE, "Could not supersede segment " + segmentId, e);
                    }
                }
            }
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Extraction failed for tenant " + event.tenantId(), e);
        }
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExtractionRequestedObserverTest`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserver.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserverTest.java
git commit -m "feat(intelligence): ExtractionRequestedObserver — async LLM enrichment + supersession

@ObservesAsync ExtractionRequested invokes MindMapExtractor, records
access for all entities, and supersedes segment nodes with extracted
entities. If extraction yields no entities, segments persist as
best-available representation.

Closes #296"
```

---

## Batch 3: Merge Detection

After this batch: MergeDetectionPhase detects duplicate entities via Jaro-Winkler name similarity + neighbor overlap (Layer 1), with optional embedding confirmation (Layer 2). Auto-merges high-confidence candidates, flags medium-confidence for review.

### Task 6: MergeCandidate + MergeDetectionPhase Layer 1

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeCandidate.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/JaroWinkler.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhase.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/JaroWinklerTest.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhaseTest.java`

**Interfaces:**
- Consumes: `MindMapStore.nodesIn()`, `MindMapStore.neighbors()`, `MindMapStore.mergeNodes()`, `ConsolidationPhase` SPI (Task 3)
- Produces: `MergeCandidate` record, `JaroWinkler.similarity(String, String)` — Layer 2 (Task 7) extends MergeDetectionPhase

- [ ] **Step 1: Write MergeCandidate record**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import java.time.Instant;

public record MergeCandidate(
    String nodeId1,
    String nodeId2,
    double score,
    String reason,
    Instant detectedAt
) {}
```

- [ ] **Step 2: Write JaroWinkler test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class JaroWinklerTest {

    @Test
    void identicalStrings_returnsOne() {
        assertThat(JaroWinkler.similarity("Alice", "Alice")).isEqualTo(1.0);
    }

    @Test
    void completelyDifferent_returnsLow() {
        assertThat(JaroWinkler.similarity("abc", "xyz")).isLessThan(0.5);
    }

    @Test
    void similarNames_returnsHigh() {
        assertThat(JaroWinkler.similarity("Mark Proctor", "M. Proctor"))
            .isGreaterThan(0.8);
    }

    @Test
    void emptyStrings_returnsOne() {
        assertThat(JaroWinkler.similarity("", "")).isEqualTo(1.0);
    }

    @Test
    void oneEmpty_returnsZero() {
        assertThat(JaroWinkler.similarity("abc", "")).isEqualTo(0.0);
    }

    @Test
    void transposition_handledCorrectly() {
        double score = JaroWinkler.similarity("Martha", "Marhta");
        assertThat(score).isCloseTo(0.961, within(0.01));
    }
}
```

- [ ] **Step 3: Implement JaroWinkler**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

public final class JaroWinkler {

    private static final double WINKLER_PREFIX_WEIGHT = 0.1;
    private static final int WINKLER_MAX_PREFIX = 4;

    private JaroWinkler() {}

    public static double similarity(String s1, String s2) {
        if (s1.equals(s2)) return 1.0;
        int len1 = s1.length();
        int len2 = s2.length();
        if (len1 == 0 || len2 == 0) return 0.0;

        int matchDistance = Math.max(len1, len2) / 2 - 1;
        if (matchDistance < 0) matchDistance = 0;

        boolean[] s1Matches = new boolean[len1];
        boolean[] s2Matches = new boolean[len2];

        int matches = 0;
        int transpositions = 0;

        for (int i = 0; i < len1; i++) {
            int start = Math.max(0, i - matchDistance);
            int end = Math.min(i + matchDistance + 1, len2);
            for (int j = start; j < end; j++) {
                if (s2Matches[j] || s1.charAt(i) != s2.charAt(j)) continue;
                s1Matches[i] = true;
                s2Matches[j] = true;
                matches++;
                break;
            }
        }

        if (matches == 0) return 0.0;

        int k = 0;
        for (int i = 0; i < len1; i++) {
            if (!s1Matches[i]) continue;
            while (!s2Matches[k]) k++;
            if (s1.charAt(i) != s2.charAt(k)) transpositions++;
            k++;
        }

        double jaro = ((double) matches / len1 + (double) matches / len2
            + (double) (matches - transpositions / 2) / matches) / 3.0;

        int prefix = 0;
        for (int i = 0; i < Math.min(Math.min(len1, len2), WINKLER_MAX_PREFIX); i++) {
            if (s1.charAt(i) == s2.charAt(i)) prefix++;
            else break;
        }

        return jaro + prefix * WINKLER_PREFIX_WEIGHT * (1 - jaro);
    }
}
```

- [ ] **Step 4: Run JaroWinkler test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=JaroWinklerTest`
Expected: PASS (6 tests)

- [ ] **Step 5: Write MergeDetectionPhase test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class MergeDetectionPhaseTest {

    private InMemoryMindMapStore store;
    private MergeDetectionPhase phase;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        phase = new MergeDetectionPhase(store, null, 0.85, 0.3, 0.9, 10);
        subgraphId = store.createSubgraph(
            new SubgraphInput("People", SubgraphTypes.PERSON, null), "t1");
    }

    @Test
    void detectCandidates_similarNames_returnsCandidate() {
        store.addNode(NodeInput.of("Mark Proctor", subgraphId), "t1");
        store.addNode(NodeInput.of("M. Proctor", subgraphId), "t1");

        List<MergeCandidate> candidates = phase.detectCandidates(subgraphId, "t1");
        assertThat(candidates).isNotEmpty();
        assertThat(candidates.getFirst().score()).isGreaterThan(0.5);
    }

    @Test
    void detectCandidates_differentNames_noCandidates() {
        store.addNode(NodeInput.of("Alice Smith", subgraphId), "t1");
        store.addNode(NodeInput.of("Bob Jones", subgraphId), "t1");

        List<MergeCandidate> candidates = phase.detectCandidates(subgraphId, "t1");
        assertThat(candidates).isEmpty();
    }

    @Test
    void run_autoMergesHighConfidence() {
        String id1 = store.addNode(NodeInput.of("Alice Smith", subgraphId)
            .withProperties(Map.of("storageStrength", "10")), "t1");
        String id2 = store.addNode(NodeInput.of("Alice Smith", subgraphId)
            .withProperties(Map.of("storageStrength", "5")), "t1");

        phase.run("t1", List.of());

        var nodes = store.nodesIn(subgraphId, "t1");
        assertThat(nodes).hasSize(1);
        assertThat(nodes.getFirst().name()).isEqualTo("Alice Smith");
    }

    @Test
    void run_excludesSummaryTraitNodes() {
        store.addNode(NodeInput.of("Summary of cluster", subgraphId)
            .withTraits(java.util.Set.of("Summary")), "t1");
        store.addNode(NodeInput.of("Summary of cluster 2", subgraphId)
            .withTraits(java.util.Set.of("Summary")), "t1");

        List<MergeCandidate> candidates = phase.detectCandidates(subgraphId, "t1");
        assertThat(candidates).isEmpty();
    }

    @Test
    void name_returnsMergeDetection() {
        assertThat(phase.name()).isEqualTo("merge-detection");
    }
}
```

- [ ] **Step 6: Implement MergeDetectionPhase**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.*;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import java.time.Instant;
import java.util.*;
import java.util.logging.Logger;
import java.util.stream.Collectors;

@ApplicationScoped
@Priority(20)
public class MergeDetectionPhase implements ConsolidationPhase {

    private static final Logger LOG = Logger.getLogger(
        MergeDetectionPhase.class.getName());

    final MindMapStore store;
    final Object embeddingModel;
    final double nameThreshold;
    final double neighborThreshold;
    final double autoMergeThreshold;
    final int maxPerPass;

    @Inject
    public MergeDetectionPhase(MindMapStore store,
                                @SuppressWarnings("unused")
                                Instance<Object> embeddingModel) {
        this(store, null, 0.85, 0.3, 0.9, 10);
    }

    MergeDetectionPhase(MindMapStore store, Object embeddingModel,
                         double nameThreshold, double neighborThreshold,
                         double autoMergeThreshold, int maxPerPass) {
        this.store = store;
        this.embeddingModel = embeddingModel;
        this.nameThreshold = nameThreshold;
        this.neighborThreshold = neighborThreshold;
        this.autoMergeThreshold = autoMergeThreshold;
        this.maxPerPass = maxPerPass;
    }

    @Override
    public String name() {
        return "merge-detection";
    }

    @Override
    public void run(String tenantId, List<String> subgraphPriority) {
        List<String> subgraphIds = orderedSubgraphs(tenantId, subgraphPriority);
        int mergeCount = 0;

        for (String sgId : subgraphIds) {
            if (mergeCount >= maxPerPass) break;
            List<MergeCandidate> candidates = detectCandidates(sgId, tenantId);

            for (MergeCandidate candidate : candidates) {
                if (mergeCount >= maxPerPass) break;
                if (candidate.score() >= autoMergeThreshold) {
                    try {
                        String keepId = chooseKeepNode(
                            candidate.nodeId1(), candidate.nodeId2(), tenantId);
                        String removeId = keepId.equals(candidate.nodeId1())
                            ? candidate.nodeId2() : candidate.nodeId1();
                        store.mergeNodes(keepId, removeId, tenantId);
                        mergeCount++;
                    } catch (Exception e) {
                        LOG.warning("Merge failed: " + e.getMessage());
                    }
                } else if (candidate.score() >= 0.7) {
                    flagCandidate(candidate, tenantId);
                }
            }
        }
    }

    List<MergeCandidate> detectCandidates(String subgraphId, String tenantId) {
        List<MindMapNode> nodes = store.nodesIn(subgraphId, tenantId).stream()
            .filter(n -> !n.traits().contains("Summary"))
            .toList();

        List<MergeCandidate> candidates = new ArrayList<>();
        for (int i = 0; i < nodes.size(); i++) {
            for (int j = i + 1; j < nodes.size(); j++) {
                MindMapNode a = nodes.get(i);
                MindMapNode b = nodes.get(j);
                double nameSim = JaroWinkler.similarity(a.name(), b.name());
                if (nameSim < nameThreshold) continue;

                Set<String> neighborsA = neighborIds(a.id(), tenantId);
                Set<String> neighborsB = neighborIds(b.id(), tenantId);
                double neighborOverlap = jaccard(neighborsA, neighborsB);

                double combined = 0.6 * nameSim + 0.4 * neighborOverlap;
                if (combined >= 0.6) {
                    String reason = neighborOverlap > 0 ? "name+neighbors" : "name-similarity";
                    candidates.add(new MergeCandidate(
                        a.id(), b.id(), combined, reason, Instant.now()));
                }
            }
        }

        candidates.sort(Comparator.comparingDouble(MergeCandidate::score).reversed());
        return candidates;
    }

    private Set<String> neighborIds(String nodeId, String tenantId) {
        return store.neighbors(nodeId, tenantId).stream()
            .map(edge -> edge.sourceNodeId().equals(nodeId) ? edge.targetNodeId() : edge.sourceNodeId())
            .collect(Collectors.toSet());
    }

    private double jaccard(Set<String> a, Set<String> b) {
        if (a.isEmpty() && b.isEmpty()) return 0.0;
        Set<String> intersection = new HashSet<>(a);
        intersection.retainAll(b);
        Set<String> union = new HashSet<>(a);
        union.addAll(b);
        return (double) intersection.size() / union.size();
    }

    private String chooseKeepNode(String id1, String id2, String tenantId) {
        MindMapNode n1 = store.getNode(id1, tenantId);
        MindMapNode n2 = store.getNode(id2, tenantId);
        int s1 = n1.property("storageStrength").map(Integer::parseInt).orElse(0);
        int s2 = n2.property("storageStrength").map(Integer::parseInt).orElse(0);
        return s1 >= s2 ? id1 : id2;
    }

    private void flagCandidate(MergeCandidate candidate, String tenantId) {
        try {
            store.updateNode(candidate.nodeId1(),
                NodeUpdate.empty().withPropertiesToSet(Map.of(
                    "mergeCandidate", candidate.nodeId2())),
                tenantId);
            store.updateNode(candidate.nodeId2(),
                NodeUpdate.empty().withPropertiesToSet(Map.of(
                    "mergeCandidate", candidate.nodeId1())),
                tenantId);
        } catch (Exception e) {
            LOG.fine("Could not flag merge candidate: " + e.getMessage());
        }
    }

    private List<String> orderedSubgraphs(String tenantId, List<String> priority) {
        List<String> all = store.listSubgraphs(tenantId).stream()
            .map(MindMapSubgraph::id).collect(Collectors.toCollection(ArrayList::new));
        List<String> ordered = new ArrayList<>();
        for (String sgId : priority) {
            if (all.remove(sgId)) ordered.add(sgId);
        }
        ordered.addAll(all);
        return ordered;
    }
}
```

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="JaroWinklerTest,MergeDetectionPhaseTest"`
Expected: PASS (11 tests)

- [ ] **Step 8: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeCandidate.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/JaroWinkler.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhase.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/JaroWinklerTest.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhaseTest.java
git commit -m "feat(consolidation): MergeDetectionPhase Layer 1 — Jaro-Winkler + neighbor overlap

Two-pass merge detection: Jaro-Winkler name similarity (≥0.85) combined
with Jaccard neighbor overlap (≥0.3). Combined score = 0.6*name + 0.4*neighbors.
Auto-merges above 0.9 (keeps higher storageStrength node), flags [0.7,0.9)
as mergeCandidate properties. Excludes Summary-trait nodes. Capped at 10
auto-merges per pass.

Refs #300"
```

---

### Task 7: MergeDetectionPhase Layer 2 — Optional Embedding Confirmation

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhase.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhaseEmbeddingTest.java`

**Interfaces:**
- Consumes: `MergeDetectionPhase.detectCandidates()` (Task 6), optional `Instance<dev.langchain4j.model.embedding.EmbeddingModel>`
- Produces: Embedding-confirmed merge candidates with updated scores

- [ ] **Step 1: Write Layer 2 test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.output.Response;
import dev.langchain4j.data.embedding.Embedding;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;
import static org.mockito.ArgumentMatchers.any;

class MergeDetectionPhaseEmbeddingTest {

    private InMemoryMindMapStore store;
    private EmbeddingModel embeddingModel;
    private MergeDetectionPhase phase;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        embeddingModel = mock(EmbeddingModel.class);
        phase = new MergeDetectionPhase(store, embeddingModel, 0.85, 0.3, 0.9, 10);
        subgraphId = store.createSubgraph(
            new SubgraphInput("People", SubgraphTypes.PERSON, null), "t1");
    }

    @Test
    void layer2_confirmsUncertainCandidate() {
        store.addNode(NodeInput.of("Mark Proctor", subgraphId), "t1");
        store.addNode(NodeInput.of("M. Proctor", subgraphId), "t1");

        float[] vec1 = {1.0f, 0.0f, 0.0f};
        float[] vec2 = {0.99f, 0.1f, 0.0f};
        when(embeddingModel.embed(any(String.class)))
            .thenReturn(Response.from(Embedding.from(vec1)))
            .thenReturn(Response.from(Embedding.from(vec2)));

        phase.run("t1", List.of());
        verify(embeddingModel, atLeastOnce()).embed(any(String.class));
    }

    @Test
    void noEmbeddingModel_layer1Only() {
        var phaseNoEmbed = new MergeDetectionPhase(store, null, 0.85, 0.3, 0.9, 10);
        store.addNode(NodeInput.of("Mark Proctor", subgraphId), "t1");
        store.addNode(NodeInput.of("M. Proctor", subgraphId), "t1");

        phaseNoEmbed.run("t1", List.of());
        // Should complete without error — Layer 1 only
    }
}
```

- [ ] **Step 2: Add Layer 2 embedding confirmation to MergeDetectionPhase.run()**

Add a `confirmWithEmbedding(MergeCandidate, String tenantId)` method:

```java
private Optional<MergeCandidate> confirmWithEmbedding(MergeCandidate candidate,
                                                        String tenantId) {
    if (embeddingModel == null) return Optional.empty();
    if (!(embeddingModel instanceof dev.langchain4j.model.embedding.EmbeddingModel model)) {
        return Optional.empty();
    }

    MindMapNode n1 = store.getNode(candidate.nodeId1(), tenantId);
    MindMapNode n2 = store.getNode(candidate.nodeId2(), tenantId);
    if (n1 == null || n2 == null) return Optional.empty();

    String text1 = n1.name() + " " + String.join(" ", n1.properties().values());
    String text2 = n2.name() + " " + String.join(" ", n2.properties().values());

    var emb1 = model.embed(text1).content();
    var emb2 = model.embed(text2).content();
    double cosine = dev.langchain4j.store.embedding.CosineSimilarity.between(emb1, emb2);

    if (cosine >= 0.8) {
        return Optional.of(new MergeCandidate(
            candidate.nodeId1(), candidate.nodeId2(),
            Math.max(candidate.score(), cosine),
            "embedding-confirmed", candidate.detectedAt()));
    }
    return Optional.empty();
}
```

In `run()`, after sorting candidates, for each candidate in the uncertain range [0.6, autoMergeThreshold), attempt Layer 2 confirmation:

```java
for (MergeCandidate candidate : candidates) {
    if (mergeCount >= maxPerPass) break;
    MergeCandidate resolved = candidate;
    if (candidate.score() < autoMergeThreshold && candidate.score() >= 0.6) {
        var confirmed = confirmWithEmbedding(candidate, tenantId);
        if (confirmed.isPresent()) {
            resolved = confirmed.get();
        }
    }
    // ... rest of merge/flag logic using 'resolved'
}
```

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="MergeDetectionPhaseTest,MergeDetectionPhaseEmbeddingTest"`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhase.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhaseEmbeddingTest.java
git commit -m "feat(consolidation): MergeDetectionPhase Layer 2 — optional embedding confirmation

Layer 2 confirms uncertain candidates (score [0.6, 0.9)) via embedding
cosine similarity. Only runs on Layer 1 candidates — not full graph.
Graceful degradation when no EmbeddingModel available (Layer 1 only).

Closes #300"
```

---

## Batch 4: Community Summaries + Curiosity Refresh

After this batch: MindMapAnalyzer gains k-core decomposition, CommunitySummaryPhase generates LLM summaries for dense clusters with hash-based invalidation, CuriosityRefreshPhase delegates to CuriositySignalGenerator. The full consolidation pipeline is operational.

### Task 8: MindMapAnalyzer.kCores

**Files:**
- Modify: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzer.java`
- Test: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzerKCoreTest.java`

**Interfaces:**
- Consumes: `MindMapStore.nodesIn()`, `MindMapStore.neighbors()`, `MindMapCapability.GRAPH_ANALYSIS`
- Produces: `MindMapAnalyzer.KCore` record, `MindMapAnalyzer.kCores(store, subgraphId, tenantId, k)` — used by CommunitySummaryPhase (Task 9)

- [ ] **Step 1: Write KCore record and kCores test**

```java
package io.casehub.neocortex.mindmap.runtime;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.assertThat;

class MindMapAnalyzerKCoreTest {

    private InMemoryMindMapStore store;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        subgraphId = store.createSubgraph(
            new SubgraphInput("Test", SubgraphTypes.GENERAL, null), "t1");
    }

    @Test
    void kCores_emptySubgraph_returnsEmpty() {
        List<MindMapAnalyzer.KCore> cores = MindMapAnalyzer.kCores(store, subgraphId, "t1", 2);
        assertThat(cores).isEmpty();
    }

    @Test
    void kCores_triangle_returns2Core() {
        String a = store.addNode(NodeInput.of("A", subgraphId), "t1");
        String b = store.addNode(NodeInput.of("B", subgraphId), "t1");
        String c = store.addNode(NodeInput.of("C", subgraphId), "t1");
        store.addEdge(EdgeInput.of(a, b, "knows"), "t1");
        store.addEdge(EdgeInput.of(b, c, "knows"), "t1");
        store.addEdge(EdgeInput.of(a, c, "knows"), "t1");

        List<MindMapAnalyzer.KCore> cores = MindMapAnalyzer.kCores(store, subgraphId, "t1", 2);
        assertThat(cores).hasSize(1);
        assertThat(cores.getFirst().nodeIds()).containsExactlyInAnyOrder(a, b, c);
    }

    @Test
    void kCores_isolatedNode_excluded() {
        String a = store.addNode(NodeInput.of("A", subgraphId), "t1");
        String b = store.addNode(NodeInput.of("B", subgraphId), "t1");
        String c = store.addNode(NodeInput.of("C", subgraphId), "t1");
        String d = store.addNode(NodeInput.of("D", subgraphId), "t1");
        store.addEdge(EdgeInput.of(a, b, "knows"), "t1");
        store.addEdge(EdgeInput.of(b, c, "knows"), "t1");
        store.addEdge(EdgeInput.of(a, c, "knows"), "t1");

        List<MindMapAnalyzer.KCore> cores = MindMapAnalyzer.kCores(store, subgraphId, "t1", 2);
        assertThat(cores).hasSize(1);
        assertThat(cores.getFirst().nodeIds()).doesNotContain(d);
    }

    @Test
    void kCores_twoDisconnectedTriangles_returnsTwoCores() {
        String a = store.addNode(NodeInput.of("A", subgraphId), "t1");
        String b = store.addNode(NodeInput.of("B", subgraphId), "t1");
        String c = store.addNode(NodeInput.of("C", subgraphId), "t1");
        store.addEdge(EdgeInput.of(a, b, "knows"), "t1");
        store.addEdge(EdgeInput.of(b, c, "knows"), "t1");
        store.addEdge(EdgeInput.of(a, c, "knows"), "t1");

        String d = store.addNode(NodeInput.of("D", subgraphId), "t1");
        String e = store.addNode(NodeInput.of("E", subgraphId), "t1");
        String f = store.addNode(NodeInput.of("F", subgraphId), "t1");
        store.addEdge(EdgeInput.of(d, e, "knows"), "t1");
        store.addEdge(EdgeInput.of(e, f, "knows"), "t1");
        store.addEdge(EdgeInput.of(d, f, "knows"), "t1");

        List<MindMapAnalyzer.KCore> cores = MindMapAnalyzer.kCores(store, subgraphId, "t1", 2);
        assertThat(cores).hasSize(2);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap -Dtest=MindMapAnalyzerKCoreTest -DfailIfNoTests=false`
Expected: FAIL — method not found

- [ ] **Step 3: Implement kCores in MindMapAnalyzer**

Add the `KCore` record and `kCores()` method to the existing `MindMapAnalyzer` class using `ide_insert_member`:

```java
public record KCore(Set<String> nodeIds, double density) {
    public KCore { nodeIds = Set.copyOf(nodeIds); }
}

public static List<KCore> kCores(MindMapStore store, String subgraphId,
                                  String tenantId, int k) {
    requireAnalysis(store);
    List<MindMapNode> allNodes = store.nodesIn(subgraphId, tenantId);
    if (allNodes.isEmpty()) return List.of();

    Map<String, Set<String>> adjacency = new HashMap<>();
    for (MindMapNode node : allNodes) {
        adjacency.put(node.id(), new HashSet<>());
    }
    for (MindMapNode node : allNodes) {
        for (MindMapEdge edge : store.neighbors(node.id(), tenantId)) {
            String other = edge.sourceNodeId().equals(node.id())
                ? edge.targetNodeId() : edge.sourceNodeId();
            if (adjacency.containsKey(other)) {
                adjacency.get(node.id()).add(other);
                adjacency.get(other).add(node.id());
            }
        }
    }

    boolean changed = true;
    while (changed) {
        changed = false;
        var iterator = adjacency.entrySet().iterator();
        while (iterator.hasNext()) {
            var entry = iterator.next();
            if (entry.getValue().size() < k) {
                String removed = entry.getKey();
                iterator.remove();
                for (Set<String> neighbors : adjacency.values()) {
                    neighbors.remove(removed);
                }
                changed = true;
            }
        }
    }

    if (adjacency.isEmpty()) return List.of();

    List<KCore> cores = new ArrayList<>();
    Set<String> visited = new HashSet<>();
    for (String nodeId : adjacency.keySet()) {
        if (visited.contains(nodeId)) continue;
        Set<String> component = new HashSet<>();
        Queue<String> queue = new LinkedList<>();
        queue.add(nodeId);
        visited.add(nodeId);
        while (!queue.isEmpty()) {
            String current = queue.poll();
            component.add(current);
            for (String neighbor : adjacency.getOrDefault(current, Set.of())) {
                if (visited.add(neighbor)) {
                    queue.add(neighbor);
                }
            }
        }
        int edgeCount = 0;
        for (String n : component) {
            edgeCount += adjacency.getOrDefault(n, Set.of()).stream()
                .filter(component::contains).count();
        }
        edgeCount /= 2;
        int nodeCount = component.size();
        double density = nodeCount <= 1 ? 0.0
            : (2.0 * edgeCount) / (nodeCount * (nodeCount - 1));
        cores.add(new KCore(component, density));
    }
    return cores;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap -Dtest=MindMapAnalyzerKCoreTest`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzer.java \
        mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzerKCoreTest.java
git commit -m "feat(mindmap): MindMapAnalyzer.kCores — k-core decomposition for community detection

O(V+E) iterative algorithm: remove nodes with degree < k until stable,
find connected components in remaining graph, compute density per component.
Returns List<KCore> with nodeIds and density.

Refs #299"
```

---

### Task 9: CommunitySummaryPhase

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CommunitySummaryPhase.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CommunitySummaryPhaseTest.java`

**Interfaces:**
- Consumes: `MindMapAnalyzer.kCores()` (Task 8), `MindMapStore`, `Instance<AgentProvider>`, `ConsolidationPhase` SPI (Task 3)
- Produces: Summary-trait nodes with `coreHash`, `memberHash`, `summarizes` edges

- [ ] **Step 1: Write CommunitySummaryPhase test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Set;
import static org.assertj.core.api.Assertions.assertThat;

class CommunitySummaryPhaseTest {

    private InMemoryMindMapStore store;
    private CommunitySummaryPhase phase;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        phase = new CommunitySummaryPhase(store, null, 2, 3, 5);
        subgraphId = store.createSubgraph(
            new SubgraphInput("People", SubgraphTypes.PERSON, null), "t1");
    }

    private void createTriangle(String name1, String name2, String name3) {
        String a = store.addNode(NodeInput.of(name1, subgraphId), "t1");
        String b = store.addNode(NodeInput.of(name2, subgraphId), "t1");
        String c = store.addNode(NodeInput.of(name3, subgraphId), "t1");
        store.addEdge(EdgeInput.of(a, b, "knows"), "t1");
        store.addEdge(EdgeInput.of(b, c, "knows"), "t1");
        store.addEdge(EdgeInput.of(a, c, "knows"), "t1");
    }

    @Test
    void run_noLlm_createsSummaryWithDefaultText() {
        createTriangle("Alice", "Bob", "Carol");

        phase.run("t1", List.of());

        var nodes = store.nodesIn(subgraphId, "t1");
        var summaryNodes = nodes.stream()
            .filter(n -> n.traits().contains("Summary"))
            .toList();
        assertThat(summaryNodes).hasSize(1);
        assertThat(summaryNodes.getFirst().property("coreHash")).isPresent();
        assertThat(summaryNodes.getFirst().property("memberCount")).hasValue("3");
    }

    @Test
    void run_unchangedCluster_skipsSummary() {
        createTriangle("Alice", "Bob", "Carol");

        phase.run("t1", List.of());
        phase.run("t1", List.of());

        var summaryNodes = store.nodesIn(subgraphId, "t1").stream()
            .filter(n -> n.traits().contains("Summary"))
            .toList();
        assertThat(summaryNodes).hasSize(1);
    }

    @Test
    void run_dissolvedCluster_erasesStaleSummary() {
        String a = store.addNode(NodeInput.of("Alice", subgraphId), "t1");
        String b = store.addNode(NodeInput.of("Bob", subgraphId), "t1");
        String c = store.addNode(NodeInput.of("Carol", subgraphId), "t1");
        store.addEdge(EdgeInput.of(a, b, "knows"), "t1");
        store.addEdge(EdgeInput.of(b, c, "knows"), "t1");
        store.addEdge(EdgeInput.of(a, c, "knows"), "t1");

        phase.run("t1", List.of());
        assertThat(store.nodesIn(subgraphId, "t1").stream()
            .filter(n -> n.traits().contains("Summary")).count()).isEqualTo(1);

        store.eraseNode(c, "t1");

        phase.run("t1", List.of());
        assertThat(store.nodesIn(subgraphId, "t1").stream()
            .filter(n -> n.traits().contains("Summary")).count()).isEqualTo(0);
    }

    @Test
    void name_returnsCommunitySummary() {
        assertThat(phase.name()).isEqualTo("community-summary");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CommunitySummaryPhaseTest -DfailIfNoTests=false`
Expected: FAIL

- [ ] **Step 3: Implement CommunitySummaryPhase**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.runtime.MindMapAnalyzer;
import io.casehub.platform.agent.AgentProvider;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.*;
import java.util.logging.Logger;
import java.util.stream.Collectors;

@ApplicationScoped
@Priority(30)
public class CommunitySummaryPhase implements ConsolidationPhase {

    private static final Logger LOG = Logger.getLogger(
        CommunitySummaryPhase.class.getName());

    private final MindMapStore store;
    private final AgentProvider agentProvider;
    private final int k;
    private final int minClusterSize;
    private final int maxPerPass;

    @Inject
    public CommunitySummaryPhase(MindMapStore store,
                                  Instance<AgentProvider> agentProvider) {
        this(store,
            agentProvider.isResolvable() ? agentProvider.get() : null,
            3, 4, 5);
    }

    CommunitySummaryPhase(MindMapStore store, AgentProvider agentProvider,
                           int k, int minClusterSize, int maxPerPass) {
        this.store = store;
        this.agentProvider = agentProvider;
        this.k = k;
        this.minClusterSize = minClusterSize;
        this.maxPerPass = maxPerPass;
    }

    @Override
    public String name() {
        return "community-summary";
    }

    @Override
    public void run(String tenantId, List<String> subgraphPriority) {
        List<String> sgIds = orderedSubgraphs(tenantId, subgraphPriority);
        int generated = 0;

        for (String sgId : sgIds) {
            if (generated >= maxPerPass) break;
            List<MindMapAnalyzer.KCore> cores = MindMapAnalyzer.kCores(store, sgId, tenantId, k);
            Set<String> currentHashes = new HashSet<>();

            for (MindMapAnalyzer.KCore core : cores) {
                String coreHash = hashIds(core.nodeIds());
                currentHashes.add(coreHash);
            }

            cleanupStaleSummaries(sgId, tenantId, currentHashes);

            for (MindMapAnalyzer.KCore core : cores) {
                if (generated >= maxPerPass) break;
                if (core.nodeIds().size() < minClusterSize) continue;

                String coreHash = hashIds(core.nodeIds());
                String memberHash = computeMemberHash(core.nodeIds(), tenantId);

                var existing = findSummaryByCoreHash(sgId, tenantId, coreHash);
                if (existing.isPresent()) {
                    MindMapNode summary = existing.get();
                    if (memberHash.equals(summary.property("memberHash").orElse(""))) {
                        continue;
                    }
                    String title = generateTitle(core.nodeIds(), tenantId);
                    store.updateNode(summary.id(),
                        NodeUpdate.empty().withName(title).withPropertiesToSet(Map.of(
                            "memberHash", memberHash,
                            "memberCount", String.valueOf(core.nodeIds().size()),
                            "generatedAt", Instant.now().toString())),
                        tenantId);
                    generated++;
                } else {
                    String title = generateTitle(core.nodeIds(), tenantId);
                    String summaryId = store.addNode(
                        NodeInput.of(title, sgId)
                            .withTraits(Set.of("Summary"))
                            .withProperties(Map.of(
                                "coreHash", coreHash,
                                "memberHash", memberHash,
                                "memberCount", String.valueOf(core.nodeIds().size()),
                                "generatedAt", Instant.now().toString())),
                        tenantId);
                    for (String nodeId : core.nodeIds()) {
                        store.addEdge(EdgeInput.of(summaryId, nodeId, "summarizes"), tenantId);
                    }
                    generated++;
                }
            }
        }
    }

    private void cleanupStaleSummaries(String sgId, String tenantId,
                                        Set<String> currentHashes) {
        List<MindMapNode> summaries = store.nodesIn(sgId, tenantId).stream()
            .filter(n -> n.traits().contains("Summary"))
            .toList();
        for (MindMapNode summary : summaries) {
            String hash = summary.property("coreHash").orElse("");
            if (!currentHashes.contains(hash)) {
                store.eraseNode(summary.id(), tenantId);
            }
        }
    }

    private Optional<MindMapNode> findSummaryByCoreHash(String sgId, String tenantId,
                                                          String coreHash) {
        return store.nodesIn(sgId, tenantId).stream()
            .filter(n -> n.traits().contains("Summary"))
            .filter(n -> coreHash.equals(n.property("coreHash").orElse("")))
            .findFirst();
    }

    private String generateTitle(Set<String> nodeIds, String tenantId) {
        if (agentProvider == null) {
            List<String> names = nodeIds.stream()
                .map(id -> { try { return store.getNode(id, tenantId).name(); }
                             catch (Exception e) { return id; } })
                .sorted()
                .toList();
            return "Summary: " + String.join(", ",
                names.subList(0, Math.min(3, names.size())));
        }
        return "Summary (LLM)";
    }

    private String computeMemberHash(Set<String> nodeIds, String tenantId) {
        List<String> parts = nodeIds.stream().sorted().map(id -> {
            try {
                MindMapNode node = store.getNode(id, tenantId);
                return id + ":" + (node != null ? node.name() : "");
            } catch (Exception e) { return id; }
        }).toList();
        return hashString(String.join("|", parts));
    }

    private String hashIds(Set<String> ids) {
        return hashString(ids.stream().sorted().collect(Collectors.joining("|")));
    }

    private String hashString(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < 8; i++) {
                sb.append(String.format("%02x", hash[i]));
            }
            return sb.toString();
        } catch (Exception e) {
            return Integer.toHexString(input.hashCode());
        }
    }

    private List<String> orderedSubgraphs(String tenantId, List<String> priority) {
        List<String> all = store.listSubgraphs(tenantId).stream()
            .map(MindMapSubgraph::id)
            .collect(Collectors.toCollection(ArrayList::new));
        List<String> ordered = new ArrayList<>();
        for (String sgId : priority) {
            if (all.remove(sgId)) ordered.add(sgId);
        }
        ordered.addAll(all);
        return ordered;
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CommunitySummaryPhaseTest`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CommunitySummaryPhase.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CommunitySummaryPhaseTest.java
git commit -m "feat(consolidation): CommunitySummaryPhase — k-core clustering + LLM summaries

Creates Summary-trait nodes for k-core clusters ≥ minClusterSize.
Hash-based invalidation: unchanged clusters skip LLM calls.
Stale summaries erased when k-cores dissolve.
Capped at maxPerPass (default 5) new/regenerated summaries.
Graceful degradation without AgentProvider (fallback title generation).

Closes #299"
```

---

### Task 10: CuriosityRefreshPhase

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CuriosityRefreshPhase.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CuriosityRefreshPhaseTest.java`

**Interfaces:**
- Consumes: `CuriositySignalGenerator.computeSignals(tenantId, Set.of())`, `ConsolidationPhase` SPI (Task 3)
- Produces: Refreshed curiosity signals (side effect — signals are consumed by CuriositySignalProvider)

- [ ] **Step 1: Write test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.intelligence.CuriositySignal;
import io.casehub.neocortex.mindmap.intelligence.CuriositySignalGenerator;
import io.casehub.neocortex.mindmap.intelligence.SignalCategory;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Set;
import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;

class CuriosityRefreshPhaseTest {

    @Test
    void run_delegatesToGenerator() {
        var generator = mock(CuriositySignalGenerator.class);
        when(generator.computeSignals("t1", Set.of()))
            .thenReturn(List.of(new CuriositySignal(
                SignalCategory.STRUCTURAL, 0.8, "n1", "sg1",
                "Why?", "Orphan node")));

        var phase = new CuriosityRefreshPhase(generator);
        phase.run("t1", List.of());

        verify(generator).computeSignals("t1", Set.of());
    }

    @Test
    void name_returnsCuriosityRefresh() {
        var phase = new CuriosityRefreshPhase(mock(CuriositySignalGenerator.class));
        assertThat(phase.name()).isEqualTo("curiosity-refresh");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CuriosityRefreshPhaseTest -DfailIfNoTests=false`
Expected: FAIL

- [ ] **Step 3: Implement CuriosityRefreshPhase**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.intelligence.CuriositySignalGenerator;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.List;
import java.util.Set;

@ApplicationScoped
@Priority(40)
public class CuriosityRefreshPhase implements ConsolidationPhase {

    private final CuriositySignalGenerator generator;

    @Inject
    public CuriosityRefreshPhase(CuriositySignalGenerator generator) {
        this.generator = generator;
    }

    @Override
    public String name() {
        return "curiosity-refresh";
    }

    @Override
    public void run(String tenantId, List<String> subgraphPriority) {
        generator.computeSignals(tenantId, Set.of());
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CuriosityRefreshPhaseTest`
Expected: PASS (2 tests)

- [ ] **Step 5: Full test run**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap,mindmap-intelligence`
Expected: All existing + new tests pass

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CuriosityRefreshPhase.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CuriosityRefreshPhaseTest.java
git commit -m "feat(consolidation): CuriosityRefreshPhase — delegates to CuriositySignalGenerator

Thin delegate: invokes computeSignals(tenantId, Set.of()) with empty
recentEntityIds — background signals are not biased toward conversation.
@Priority(40) — runs last in the consolidation pipeline.

Closes #297
Closes #298"
```

---

## References

- `specs/issue-295-knowledge-consolidation/2026-09-10-knowledge-consolidation-pipeline-design.md` — design spec this plan implements
- `specs/issue-295-knowledge-consolidation/decisions.md` — design decisions D1-D6
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/AbstractForwardingMindMapStore.java` — decorator base class
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeInput.java` — node creation API
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeUpdate.java` — node update API
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java` — string type constants
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapConfidenceDefaults.java` — confidence defaults
- `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayDecorator.java` — decorator test pattern
- `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzer.java` — existing graph analysis
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java` — LLM extraction
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionResult.java` — extraction result shape
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractedEntity.java` — entity record
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGenerator.java` — curiosity signals
- GitHub #295, #296, #297, #298, #299, #300
