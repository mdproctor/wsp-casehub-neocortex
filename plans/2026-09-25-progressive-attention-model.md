# Progressive Cognitive Attention Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #381 — Design: progressive cognitive attention model for long-running agents
**Issue group:** #381

**Goal:** Add event-driven cognitive attention that bridges consolidation
insights to LLM invocation — per-principal accumulation with adaptive
threshold, signal production from consolidation phases, and a CDI event
boundary for blocks integration.

**Architecture:** New types in mindmap-api (AttentionSignal, SignalCategory,
AttentionBriefing, CognitiveAttentionRequired). ConsolidationPhase gains
`signals()` default method with drain semantics. CognitiveAttentionAccumulator
in mindmap-intelligence collects signals from phases + real-time events,
evaluates per-principal adaptive threshold, fires CDI event when crossed.

**Tech Stack:** Java 21, Quarkus CDI, ConcurrentHashMap/ConcurrentLinkedQueue

## Global Constraints

- Java 21 source on Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All new types in `io.casehub.neocortex.mindmap` or `io.casehub.neocortex.mindmap.intelligence.consolidation` packages
- ConsolidationPhase SPI is in mindmap-intelligence (not mindmap-api)
- signals() uses drain semantics (return + clear)
- Per-principal state keyed by `principalId + "|" + tenantId`
- Phases that cannot resolve principal ownership set `principalId = null`
- GoalUrgency unclamped fallback paths must be fixed (clamp to [0,1])

---

## Batch 1: Signal types and SPI evolution

### Task 1: AttentionSignal, SignalCategory, AttentionBriefing, CognitiveAttentionRequired

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/AttentionSignal.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SignalCategory.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/AttentionBriefing.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/CognitiveAttentionRequired.java`
- Test: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/AttentionSignalTest.java`

**Interfaces:**
- Consumes: nothing (leaf types)
- Produces: `AttentionSignal(String principalId, String tenantId, SignalCategory category, String sourceNodeId, String sourceName, double significance, String reason)`, `SignalCategory` enum (11 values), `AttentionBriefing(String principalId, String tenantId, List<AttentionSignal> signals, double urgencyP75, Instant generatedAt)` with `topN(int)`, `CognitiveAttentionRequired(AttentionBriefing briefing, Instant firedAt)`

- [ ] **Step 1: Write AttentionSignal test**

```java
package io.casehub.neocortex.mindmap;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class AttentionSignalTest {

    @Test
    void construction_preserves_all_fields() {
        var signal = new AttentionSignal(
            "agent-1", "tenant-1", SignalCategory.URGENCY_SPIKE,
            "node-42", "Project deadline", 0.85, "urgency rose to 0.85");
        assertEquals("agent-1", signal.principalId());
        assertEquals("tenant-1", signal.tenantId());
        assertEquals(SignalCategory.URGENCY_SPIKE, signal.category());
        assertEquals("node-42", signal.sourceNodeId());
        assertEquals("Project deadline", signal.sourceName());
        assertEquals(0.85, signal.significance());
        assertEquals("urgency rose to 0.85", signal.reason());
    }

    @Test
    void null_principalId_for_unresolvable_ownership() {
        var signal = new AttentionSignal(
            null, "tenant-1", SignalCategory.MERGE_CANDIDATE,
            "node-99", "Duplicate entity", 0.6, "Jaro-Winkler 0.91");
        assertNull(signal.principalId());
    }

    @Test
    void signal_category_covers_all_sources() {
        assertEquals(11, SignalCategory.values().length);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=AttentionSignalTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — types not defined

- [ ] **Step 3: Write AttentionSignal, SignalCategory, AttentionBriefing, CognitiveAttentionRequired**

```java
// AttentionSignal.java
package io.casehub.neocortex.mindmap;

public record AttentionSignal(
    String principalId,
    String tenantId,
    SignalCategory category,
    String sourceNodeId,
    String sourceName,
    double significance,
    String reason
) {}
```

```java
// SignalCategory.java
package io.casehub.neocortex.mindmap;

public enum SignalCategory {
    URGENCY_SPIKE,
    DECAY_DETECTED,
    GOAL_RECOGNIZED,
    BLOCKER_RESOLVED,
    PRIORITY_SHIFT,
    AFFECT_CHANGE,
    MERGE_CANDIDATE,
    EXPERIENCE_GRADUATED,
    DRIVE_SHIFT,
    RELATIONSHIP_STAGE,
    BELIEF_REVISED
}
```

```java
// AttentionBriefing.java
package io.casehub.neocortex.mindmap;

import java.time.Instant;
import java.util.List;

public record AttentionBriefing(
    String principalId,
    String tenantId,
    List<AttentionSignal> signals,
    double urgencyP75,
    Instant generatedAt
) {
    public AttentionBriefing {
        signals = List.copyOf(signals);
    }

    public List<AttentionSignal> topN(int n) {
        return signals.subList(0, Math.min(n, signals.size()));
    }
}
```

```java
// CognitiveAttentionRequired.java
package io.casehub.neocortex.mindmap;

import java.time.Instant;

public record CognitiveAttentionRequired(
    AttentionBriefing briefing,
    Instant firedAt
) {}
```

- [ ] **Step 4: Write AttentionBriefing test**

Add to `AttentionSignalTest.java`:

```java
@Test
void briefing_topN_returns_first_n_signals() {
    var signals = List.of(
        new AttentionSignal("a", "t", SignalCategory.URGENCY_SPIKE, "n1", "G1", 0.9, "r1"),
        new AttentionSignal("a", "t", SignalCategory.DECAY_DETECTED, "n2", "G2", 0.5, "r2"),
        new AttentionSignal("a", "t", SignalCategory.GOAL_RECOGNIZED, "n3", "G3", 0.3, "r3"));
    var briefing = new AttentionBriefing("a", "t", signals, 0.7, Instant.now());
    assertEquals(2, briefing.topN(2).size());
    assertEquals(SignalCategory.URGENCY_SPIKE, briefing.topN(2).get(0).category());
}

@Test
void briefing_topN_clamps_to_list_size() {
    var signals = List.of(
        new AttentionSignal("a", "t", SignalCategory.URGENCY_SPIKE, "n1", "G1", 0.9, "r1"));
    var briefing = new AttentionBriefing("a", "t", signals, 0.5, Instant.now());
    assertEquals(1, briefing.topN(10).size());
}

@Test
void briefing_signals_are_immutable() {
    var signals = new java.util.ArrayList<>(List.of(
        new AttentionSignal("a", "t", SignalCategory.URGENCY_SPIKE, "n1", "G1", 0.9, "r1")));
    var briefing = new AttentionBriefing("a", "t", signals, 0.5, Instant.now());
    signals.clear();
    assertEquals(1, briefing.signals().size());
}
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=AttentionSignalTest`
Expected: PASS (6 tests)

- [ ] **Step 6: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/AttentionSignal.java mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SignalCategory.java mindmap-api/src/main/java/io/casehub/neocortex/mindmap/AttentionBriefing.java mindmap-api/src/main/java/io/casehub/neocortex/mindmap/CognitiveAttentionRequired.java mindmap-api/src/test/java/io/casehub/neocortex/mindmap/AttentionSignalTest.java
git commit -m "feat(#381): add AttentionSignal, SignalCategory, AttentionBriefing, CognitiveAttentionRequired types

Refs #381"
```

### Task 2: ConsolidationPhase.signals() default method + GoalUrgency clamp fix

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationPhase.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalUrgency.java:25,32`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalUrgencyTest.java` (new or extended)

**Interfaces:**
- Consumes: `AttentionSignal` from Task 1
- Produces: `ConsolidationPhase.signals()` returning `List<AttentionSignal>` (default empty). `GoalUrgency.computeUrgency()` always clamped to [0,1].

- [ ] **Step 1: Write GoalUrgency clamp test**

```java
@Test
void fallback_urgency_clamped_to_unit_interval() {
    var node = createNodeWithProperty("urgency", "2.0");
    double urgency = GoalUrgency.computeUrgency(node, Instant.now());
    assertTrue(urgency <= 1.0, "urgency must be clamped to 1.0 max");
    assertEquals(1.0, urgency);
}

@Test
void fallback_negative_urgency_clamped_to_zero() {
    var node = createNodeWithProperty("urgency", "-0.5");
    double urgency = GoalUrgency.computeUrgency(node, Instant.now());
    assertTrue(urgency >= 0.0, "urgency must be clamped to 0.0 min");
    assertEquals(0.0, urgency);
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: `urgency` returns 2.0 unclamped — test fails

- [ ] **Step 3: Fix GoalUrgency fallback paths**

In `GoalUrgency.java`, change both fallback lines (25 and 32):

From:
```java
return node.property("urgency").map(Double::parseDouble).orElse(0.0);
```

To:
```java
return node.property("urgency")
    .map(v -> Math.max(0.0, Math.min(1.0, Double.parseDouble(v))))
    .orElse(0.0);
```

- [ ] **Step 4: Add signals() default method to ConsolidationPhase**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.AttentionSignal;

import java.util.List;

public interface ConsolidationPhase {
    String name();
    void run(String tenantId, List<String> subgraphPriority);
    default void beginTick() {}
    default List<AttentionSignal> signals() { return List.of(); }
}
```

- [ ] **Step 5: Run full mindmap-intelligence test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: all 304 tests pass (no existing phase breaks — default method returns empty)

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationPhase.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalUrgency.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalUrgencyTest.java
git commit -m "feat(#381): add ConsolidationPhase.signals() default method + clamp GoalUrgency fallbacks

Refs #381"
```

### Task 3: CognitiveDefaultsRegistry.allAgentIds()

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistry.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistryTest.java` (extended)

**Interfaces:**
- Consumes: existing `profiles` map
- Produces: `Set<String> allAgentIds()` — all registered agent IDs

- [ ] **Step 1: Write test**

```java
@Test
void allAgentIds_returns_registered_agents() {
    var defaults1 = CognitiveDefaults.empty("agent-a");
    var defaults2 = CognitiveDefaults.empty("agent-b");
    var registry = CognitiveDefaultsRegistry.forTesting(defaults1, defaults2);
    var ids = registry.allAgentIds();
    assertEquals(Set.of("agent-a", "agent-b"), ids);
}

@Test
void allAgentIds_returns_empty_when_no_profiles() {
    var registry = CognitiveDefaultsRegistry.forTesting();
    assertTrue(registry.allAgentIds().isEmpty());
}
```

- [ ] **Step 2: Run to verify failure**

Expected: `allAgentIds()` not defined — compilation error

- [ ] **Step 3: Implement**

Add to `CognitiveDefaultsRegistry.java`:

```java
public java.util.Set<String> allAgentIds() {
    return profiles.keySet();
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDefaultsRegistryTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistry.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistryTest.java
git commit -m "feat(#381): add CognitiveDefaultsRegistry.allAgentIds()

Refs #381"
```

## Batch 2: CognitiveAttentionAccumulator

### Task 4: CognitiveAttentionAccumulator — core accumulation and threshold

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CognitiveAttentionAccumulator.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CognitiveAttentionAccumulatorTest.java`

**Interfaces:**
- Consumes: `AttentionSignal`, `AttentionBriefing`, `CognitiveAttentionRequired` from Task 1. `CognitiveDefaultsRegistry.allAgentIds()` from Task 3.
- Produces: `addSignals(List<AttentionSignal>)` — adds signals, evaluates threshold. `updateUrgencyP75(String principalId, String tenantId, double urgencyP75)`. Fires `CognitiveAttentionRequired` CDI event when threshold crossed.

- [ ] **Step 1: Write test — per-principal isolation**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.cognitive.index.CognitiveDefaults;
import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import io.casehub.neocortex.mindmap.*;
import org.junit.jupiter.api.Test;

import java.time.Clock;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;

class CognitiveAttentionAccumulatorTest {

    @Test
    void signals_accumulate_per_principal() {
        var fired = new ArrayList<CognitiveAttentionRequired>();
        var registry = CognitiveDefaultsRegistry.forTesting(
            CognitiveDefaults.empty("agent-a"),
            CognitiveDefaults.empty("agent-b"));
        var acc = new CognitiveAttentionAccumulator(
            registry, null, fired::add, Clock.systemUTC(), 5.0, 300);

        acc.addSignals(List.of(
            new AttentionSignal("agent-a", "t1", SignalCategory.URGENCY_SPIKE,
                "n1", "G1", 3.0, "r1"),
            new AttentionSignal("agent-b", "t1", SignalCategory.DECAY_DETECTED,
                "n2", "G2", 2.0, "r2")));

        // Neither crosses threshold of 5.0
        assertTrue(fired.isEmpty());

        acc.addSignals(List.of(
            new AttentionSignal("agent-a", "t1", SignalCategory.PRIORITY_SHIFT,
                "n3", "G3", 3.0, "r3")));

        // agent-a: 3.0 + 3.0 = 6.0 > 5.0 — fires
        // agent-b: 2.0 < 5.0 — does not fire
        assertEquals(1, fired.size());
        assertEquals("agent-a", fired.get(0).briefing().principalId());
    }
}
```

- [ ] **Step 2: Run to verify failure**

Expected: `CognitiveAttentionAccumulator` not defined

- [ ] **Step 3: Implement CognitiveAttentionAccumulator**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.MindMapStore;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.function.Consumer;

public class CognitiveAttentionAccumulator {

    private final ConcurrentHashMap<String, PrincipalAttention> perPrincipal = new ConcurrentHashMap<>();
    private final CognitiveDefaultsRegistry registry;
    private final MindMapStore mindMapStore;
    private final Consumer<CognitiveAttentionRequired> eventSink;
    private final Clock clock;
    private final double baseThreshold;
    private final long minIntervalSeconds;

    static class PrincipalAttention {
        final ConcurrentLinkedQueue<AttentionSignal> pending = new ConcurrentLinkedQueue<>();
        volatile Instant lastPushAt = Instant.EPOCH;
        volatile double urgencyP75 = 0.0;
    }

    public CognitiveAttentionAccumulator(
            CognitiveDefaultsRegistry registry,
            MindMapStore mindMapStore,
            Consumer<CognitiveAttentionRequired> eventSink,
            Clock clock,
            double baseThreshold,
            long minIntervalSeconds) {
        this.registry = registry;
        this.mindMapStore = mindMapStore;
        this.eventSink = eventSink;
        this.clock = clock;
        this.baseThreshold = baseThreshold;
        this.minIntervalSeconds = minIntervalSeconds;
    }

    public void addSignals(List<AttentionSignal> signals) {
        var byPrincipal = new HashMap<String, List<AttentionSignal>>();
        for (var signal : signals) {
            String key = signal.principalId() != null ? signal.principalId() : "__broadcast__";
            byPrincipal.computeIfAbsent(key, k -> new ArrayList<>()).add(signal);
        }

        var broadcastSignals = byPrincipal.remove("__broadcast__");

        for (var entry : byPrincipal.entrySet()) {
            var pa = perPrincipal.computeIfAbsent(entry.getKey(), k -> new PrincipalAttention());
            deduplicateAndAdd(pa, entry.getValue());
            evaluateThreshold(entry.getKey(), pa);
        }

        if (broadcastSignals != null && registry != null) {
            for (String agentId : registry.allAgentIds()) {
                var pa = perPrincipal.computeIfAbsent(agentId, k -> new PrincipalAttention());
                deduplicateAndAdd(pa, broadcastSignals);
                evaluateThreshold(agentId, pa);
            }
        }
    }

    public void updateUrgencyP75(String principalId, double urgencyP75) {
        var pa = perPrincipal.computeIfAbsent(principalId, k -> new PrincipalAttention());
        pa.urgencyP75 = Math.min(1.0, urgencyP75);
    }

    private void deduplicateAndAdd(PrincipalAttention pa, List<AttentionSignal> signals) {
        for (var signal : signals) {
            var existing = pa.pending.stream()
                .filter(s -> Objects.equals(s.sourceNodeId(), signal.sourceNodeId())
                             && s.category() == signal.category())
                .findFirst();
            if (existing.isPresent()) {
                if (signal.significance() > existing.get().significance()) {
                    pa.pending.remove(existing.get());
                    pa.pending.add(signal);
                }
            } else {
                pa.pending.add(signal);
            }
        }
    }

    private void evaluateThreshold(String principalId, PrincipalAttention pa) {
        double urgencyP75 = Math.min(1.0, pa.urgencyP75);
        double adjusted = urgencyP75 > 0.6
            ? baseThreshold * (1.0 - (urgencyP75 - 0.6))
            : baseThreshold;
        adjusted = Math.max(adjusted, baseThreshold * 0.6);

        double total = 0;
        for (var s : pa.pending) { total += s.significance(); }
        if (total < adjusted) return;

        Instant now = clock.instant();
        if (Duration.between(pa.lastPushAt, now).getSeconds() < minIntervalSeconds) return;

        var signalList = new ArrayList<>(pa.pending);
        signalList.sort(Comparator.comparingDouble(AttentionSignal::significance).reversed());
        pa.pending.clear();
        pa.lastPushAt = now;

        String tenantId = signalList.isEmpty() ? "" : signalList.get(0).tenantId();
        var briefing = new AttentionBriefing(principalId, tenantId, signalList, urgencyP75, now);
        eventSink.accept(new CognitiveAttentionRequired(briefing, now));
    }
}
```

- [ ] **Step 4: Write additional tests — adaptive threshold, min interval, dedup, broadcast**

```java
@Test
void adaptive_threshold_lowers_with_high_urgency_p75() {
    var fired = new ArrayList<CognitiveAttentionRequired>();
    var registry = CognitiveDefaultsRegistry.forTesting(CognitiveDefaults.empty("a"));
    var acc = new CognitiveAttentionAccumulator(registry, null, fired::add, Clock.systemUTC(), 5.0, 0);

    acc.updateUrgencyP75("a", 0.8);
    // adjusted = 5.0 * (1.0 - 0.2) = 4.0
    acc.addSignals(List.of(
        new AttentionSignal("a", "t", SignalCategory.URGENCY_SPIKE, "n1", "G1", 4.5, "r")));
    assertEquals(1, fired.size());
}

@Test
void minimum_interval_suppresses_rapid_pushes() {
    var fired = new ArrayList<CognitiveAttentionRequired>();
    var fixedClock = Clock.fixed(Instant.parse("2026-01-01T00:00:00Z"), java.time.ZoneOffset.UTC);
    var registry = CognitiveDefaultsRegistry.forTesting(CognitiveDefaults.empty("a"));
    var acc = new CognitiveAttentionAccumulator(registry, null, fired::add, fixedClock, 5.0, 300);

    acc.addSignals(List.of(
        new AttentionSignal("a", "t", SignalCategory.URGENCY_SPIKE, "n1", "G1", 6.0, "r")));
    assertEquals(1, fired.size());

    // Same clock instant — within 300s interval
    acc.addSignals(List.of(
        new AttentionSignal("a", "t", SignalCategory.DECAY_DETECTED, "n2", "G2", 6.0, "r")));
    assertEquals(1, fired.size(), "second push suppressed by interval guard");
}

@Test
void deduplication_keeps_higher_significance() {
    var fired = new ArrayList<CognitiveAttentionRequired>();
    var registry = CognitiveDefaultsRegistry.forTesting(CognitiveDefaults.empty("a"));
    var acc = new CognitiveAttentionAccumulator(registry, null, fired::add, Clock.systemUTC(), 5.0, 0);

    acc.addSignals(List.of(
        new AttentionSignal("a", "t", SignalCategory.URGENCY_SPIKE, "n1", "G1", 2.0, "low")));
    acc.addSignals(List.of(
        new AttentionSignal("a", "t", SignalCategory.URGENCY_SPIKE, "n1", "G1", 4.0, "high"),
        new AttentionSignal("a", "t", SignalCategory.DECAY_DETECTED, "n2", "G2", 2.0, "other")));

    assertEquals(1, fired.size());
    var briefing = fired.get(0).briefing();
    assertEquals(2, briefing.signals().size());
    assertEquals(4.0, briefing.signals().get(0).significance());
}

@Test
void null_principal_broadcasts_to_all_registered_agents() {
    var fired = new ArrayList<CognitiveAttentionRequired>();
    var registry = CognitiveDefaultsRegistry.forTesting(
        CognitiveDefaults.empty("a"), CognitiveDefaults.empty("b"));
    var acc = new CognitiveAttentionAccumulator(registry, null, fired::add, Clock.systemUTC(), 5.0, 0);

    acc.addSignals(List.of(
        new AttentionSignal(null, "t", SignalCategory.MERGE_CANDIDATE,
            "n1", "Dup entity", 6.0, "r")));
    assertEquals(2, fired.size());
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveAttentionAccumulatorTest`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CognitiveAttentionAccumulator.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CognitiveAttentionAccumulatorTest.java
git commit -m "feat(#381): CognitiveAttentionAccumulator — per-principal threshold + dedup + interval guard

Refs #381"
```

## Batch 3: Phase signal production + scheduler integration

### Task 5: GoalPrioritizationPhase signal production

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalPrioritizationPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalPrioritizationPhaseTest.java`

**Interfaces:**
- Consumes: `AttentionSignal`, `SignalCategory` from Task 1
- Produces: `signals()` returning URGENCY_SPIKE (urgency > 0.7), PRIORITY_SHIFT (priority changed by > 0.2), DECAY_DETECTED (goal transitioned to dormant/abandoned)

- [ ] **Step 1: Write test for urgency spike signal**

```java
@Test
void emits_urgency_spike_signal_when_urgency_exceeds_threshold() {
    // Setup: create a goal node with target-date approaching (urgency > 0.7)
    var store = new InMemoryMindMapStore();
    var phase = new GoalPrioritizationPhase(store, Clock.fixed(
        Instant.parse("2026-09-24T00:00:00Z"), java.time.ZoneOffset.UTC));
    String tenantId = "t1";

    // Create goal subgraph and goal node with approaching deadline
    var sg = store.createSubgraph(new SubgraphInput("goal", "goal"), tenantId);
    store.addNode(new NodeInput("Urgent task", sg.id(), tenantId)
        .withProperty("status", "active")
        .withProperty("target-date", "2026-09-25")
        .withProperty("horizon", "short")
        .withProperty("agent-id", "agent-1")
        .withTrait("Goallike"));

    phase.beginTick();
    phase.run(tenantId, List.of());

    var signals = phase.signals();
    assertTrue(signals.stream().anyMatch(
        s -> s.category() == SignalCategory.URGENCY_SPIKE
             && "agent-1".equals(s.principalId())));
}
```

- [ ] **Step 2: Run to verify it fails**

Expected: `signals()` returns empty (default method)

- [ ] **Step 3: Add signal production to GoalPrioritizationPhase**

Add a `pendingSignals` field, clear in `beginTick()`, populate during
`prioritize()` and `decay()`, return+clear in `signals()`. Emit
URGENCY_SPIKE when urgency > 0.7, DECAY_DETECTED when transitioning to
dormant/abandoned, PRIORITY_SHIFT when composite priority delta > 0.2.
Read `agent-id` property for principalId (null if absent).

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=GoalPrioritizationPhaseTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalPrioritizationPhase.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalPrioritizationPhaseTest.java
git commit -m "feat(#381): GoalPrioritizationPhase emits URGENCY_SPIKE, PRIORITY_SHIFT, DECAY_DETECTED signals

Refs #381"
```

### Task 6: GoalAffectPhase + remaining phase signal production

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalAffectPhase.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalRecognitionPhase.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/GoalResolutionPhase.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhase.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ExperienceConsolidationPhase.java`
- Modify: corresponding test files (extended)

**Interfaces:**
- Consumes: `AttentionSignal`, `SignalCategory` from Task 1
- Produces: Each phase's `signals()` returning its category-specific signals per §5.3

- [ ] **Step 1: Write tests for each phase's signal production**

One test per phase verifying the expected signal category is emitted
when the phase's core logic detects a change. Follow the same pattern
as Task 5 — setup phase with InMemoryMindMapStore, run, check signals().

- [ ] **Step 2: Run to verify failures**

- [ ] **Step 3: Implement signal production in each phase**

Same pattern: add `pendingSignals` field, clear in `beginTick()`, emit
during `run()`, drain in `signals()`. Each phase emits its own category:
- GoalAffectPhase → AFFECT_CHANGE
- GoalRecognitionPhase → GOAL_RECOGNIZED
- GoalResolutionPhase → BLOCKER_RESOLVED
- MergeDetectionPhase → MERGE_CANDIDATE
- ExperienceConsolidationPhase → EXPERIENCE_GRADUATED

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: all 304+ tests pass

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/
git commit -m "feat(#381): all 6 neocortex phases emit attention signals

GoalAffectPhase, GoalRecognitionPhase, GoalResolutionPhase,
MergeDetectionPhase, ExperienceConsolidationPhase now produce
category-specific AttentionSignals via signals() drain semantics.

Refs #381"
```

### Task 7: ConsolidationScheduler signal collection + accumulator integration

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationScheduler.java:35-48,156-174`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationSchedulerTest.java` (extended)

**Interfaces:**
- Consumes: `ConsolidationPhase.signals()` from Task 2, `CognitiveAttentionAccumulator.addSignals()` from Task 4
- Produces: modified `runPhases()` that collects signals from phases and feeds the accumulator

- [ ] **Step 1: Write test — scheduler feeds accumulator**

```java
@Test
void runPhases_collects_signals_and_feeds_accumulator() {
    var firedEvents = new ArrayList<CognitiveAttentionRequired>();
    var registry = CognitiveDefaultsRegistry.forTesting(CognitiveDefaults.empty("agent-a"));
    var accumulator = new CognitiveAttentionAccumulator(
        registry, null, firedEvents::add, Clock.systemUTC(), 5.0, 0);

    var phase = new StubSignalPhase("test-phase", List.of(
        new AttentionSignal("agent-a", "t1", SignalCategory.URGENCY_SPIKE,
            "n1", "G1", 6.0, "r")));

    var scheduler = new ConsolidationScheduler(
        List.of(phase), new IdleTracker(), memoryStore,
        curiosityGenerator, accumulator);

    // Simulate a consolidation tick for tenant "t1"
    // ... (invoke runPhases via consolidateNow or similar)

    assertEquals(1, firedEvents.size());
}
```

- [ ] **Step 2: Run to verify failure**

Expected: ConsolidationScheduler constructor doesn't accept accumulator yet

- [ ] **Step 3: Modify ConsolidationScheduler**

Add `CognitiveAttentionAccumulator` as an optional constructor parameter
(nullable, using `Instance<CognitiveAttentionAccumulator>` for CDI).
Modify `runPhases()`:

```java
private void runPhases(String tenantId) {
    List<String>      priority     = subgraphPriority(tenantId);
    List<PhaseResult> phaseResults = new ArrayList<>();
    List<AttentionSignal> allSignals = new ArrayList<>();
    for (ConsolidationPhase phase : phases) {
        Instant phaseStart = Instant.now();
        MutationContext.set("consolidation:" + phase.name());
        try {
            phase.run(tenantId, priority);
            allSignals.addAll(phase.signals());
            phaseResults.add(new PhaseResult(phase.name(), phaseStart, Instant.now(), true, null));
        } catch (Exception e) {
            phaseResults.add(new PhaseResult(phase.name(), phaseStart, Instant.now(), false, e.getMessage()));
            LOG.log(Level.WARNING, "Phase " + phase.name()
                                   + " failed for tenant " + tenantId, e);
        } finally {
            MutationContext.clear();
        }
    }
    if (attentionAccumulator != null && !allSignals.isEmpty()) {
        attentionAccumulator.addSignals(allSignals);
    }
    completionSink.accept(new ConsolidationCompleted(tenantId, phaseResults));
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationScheduler.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationSchedulerTest.java
git commit -m "feat(#381): ConsolidationScheduler collects phase signals and feeds accumulator

Refs #381"
```

## Batch 4: Integration test + real-time event observers

### Task 8: Real-time event observers on accumulator

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CognitiveAttentionAccumulator.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CognitiveAttentionAccumulatorTest.java` (extended)

**Interfaces:**
- Consumes: `ExperienceRecorded` (memory-api), `AffectRecorded` (memory-api)
- Produces: attention signals from real-time events fed to the same threshold mechanism

- [ ] **Step 1: Write test — AffectRecorded with significant PAD delta**

```java
@Test
void affect_recorded_with_large_pad_delta_creates_signal() {
    var fired = new ArrayList<CognitiveAttentionRequired>();
    var store = new InMemoryMindMapStore();
    var registry = CognitiveDefaultsRegistry.forTesting(CognitiveDefaults.empty("a"));
    var acc = new CognitiveAttentionAccumulator(registry, store, fired::add,
        Clock.systemUTC(), 1.0, 0);

    // Create node with PAD values
    var sg = store.createSubgraph(new SubgraphInput("people", "person"), "t1");
    var node = store.addNode(new NodeInput("Test entity", sg.id(), "t1")
        .withProperty("agent-id", "a"));
    store.updateNode(node.id(), "t1", new NodeUpdate()
        .withPleasure(0.8).withArousal(0.2).withDominance(0.5));

    // Prime the PAD cache with initial values
    acc.onAffectRecorded(new AffectRecorded(node.id(), "t1", "mem-1"));
    assertTrue(fired.isEmpty(), "first observation primes cache, no signal");

    // Update PAD to significantly different values
    store.updateNode(node.id(), "t1", new NodeUpdate()
        .withPleasure(-0.5).withArousal(0.9).withDominance(0.1));

    acc.onAffectRecorded(new AffectRecorded(node.id(), "t1", "mem-2"));
    assertEquals(1, fired.size());
    assertEquals(SignalCategory.AFFECT_CHANGE, fired.get(0).briefing().signals().get(0).category());
}
```

- [ ] **Step 2: Run to verify failure**

- [ ] **Step 3: Implement onAffectRecorded and onExperienceRecorded**

Add PAD cache (`ConcurrentHashMap<String, double[]> padCache`), AffectRecorded
observer with delta threshold (default 0.3), ExperienceRecorded observer
with goal-metadata matching.

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveAttentionAccumulatorTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CognitiveAttentionAccumulator.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CognitiveAttentionAccumulatorTest.java
git commit -m "feat(#381): real-time event observers on accumulator — AffectRecorded + ExperienceRecorded

Refs #381"
```

### Task 9: End-to-end AttentionIntegrationTest

**Files:**
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/AttentionIntegrationTest.java`

**Interfaces:**
- Consumes: all previous tasks
- Produces: integration test proving full pipeline: seed goals → run consolidation → accumulator fires → verify briefing

- [ ] **Step 1: Write end-to-end test**

```java
@Test
void full_pipeline_seed_goals_consolidate_fire_attention() {
    var store = new InMemoryMindMapStore();
    var memoryStore = new InMemoryMemoryStore();
    var fired = new ArrayList<CognitiveAttentionRequired>();
    var registry = CognitiveDefaultsRegistry.forTesting(CognitiveDefaults.empty("agent-1"));
    var accumulator = new CognitiveAttentionAccumulator(
        registry, store, fired::add, Clock.fixed(
            Instant.parse("2026-09-24T12:00:00Z"), java.time.ZoneOffset.UTC), 3.0, 0);

    // Seed goal subgraph with approaching deadline
    var sg = store.createSubgraph(new SubgraphInput("goal", "goal"), "t1");
    store.addNode(new NodeInput("Ship release", sg.id(), "t1")
        .withProperty("status", "active")
        .withProperty("target-date", "2026-09-25")
        .withProperty("horizon", "short")
        .withProperty("agent-id", "agent-1")
        .withTrait("Goallike"));

    // Build scheduler with real phases and accumulator
    var priorityPhase = new GoalPrioritizationPhase(store,
        Clock.fixed(Instant.parse("2026-09-24T12:00:00Z"), java.time.ZoneOffset.UTC));
    var scheduler = new ConsolidationScheduler(
        List.of(priorityPhase), new IdleTracker(), memoryStore, null, accumulator);

    priorityPhase.beginTick();
    priorityPhase.run("t1", List.of());
    var signals = priorityPhase.signals();
    accumulator.addSignals(signals);

    assertFalse(fired.isEmpty(), "should fire attention for approaching deadline");
    var briefing = fired.get(0).briefing();
    assertEquals("agent-1", briefing.principalId());
    assertTrue(briefing.signals().stream()
        .anyMatch(s -> s.category() == SignalCategory.URGENCY_SPIKE));
}
```

- [ ] **Step 2: Run test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=AttentionIntegrationTest`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: all tests pass (304+ existing + new)

- [ ] **Step 4: Commit**

```bash
git add mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/AttentionIntegrationTest.java
git commit -m "feat(#381): end-to-end attention integration test

Seed goals → consolidation → signals → accumulator → fire CognitiveAttentionRequired

Closes #381"
```

## References

- specs/issue-381-progressive-attention-model/2026-09-25-progressive-attention-model-design.md — design spec
- specs/issue-381-progressive-attention-model/decisions.md — 15 decisions
- ConsolidationPhase.java:5 — current SPI (mindmap-intelligence)
- ConsolidationScheduler.java:156-174 — current runPhases()
- GoalPrioritizationPhase.java — urgency + priority computation
- GoalAffectPhase.java — OCC appraisal
- GoalUrgency.java:25,32 — unclamped fallback paths
- CognitiveDefaultsRegistry.java:62-72 — forAgent/allProfiles
- SignificanceAccumulator.java — existing threshold pattern
- AffectRecorded.java — CDI event for affect changes
- casehubio/neocortex#381 — focal issue
- casehubio/blocks#303 — layer placement alignment
