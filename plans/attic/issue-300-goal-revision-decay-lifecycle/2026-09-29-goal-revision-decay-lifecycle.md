# GoalRevision Decay-Signal Lifecycle Transitions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** blocks#300 — GoalRevision consumption — decay-signal lifecycle transitions
**Issue group:** blocks#300

**Goal:** Close the decay-signal data flow loop so that MindMap goal nodes with declining confidence trigger eidos goal lifecycle transitions, which then feed back to neocortex to clear the signal.

**Architecture:** Three changes across two repos (eidos, blocks). First, add a targeted `updateGoalLifecycleState` default method to `AgentRegistry` (eidos-api). Then wire the consumer in `SocialAvatarCognition` (blocks-core) to read pending revisions after each tick and call the new method. Finally, add an `EidosGoalLifecycleProvider` (blocks-core) that bridges eidos goal states back to neocortex's `GoalResolutionPhase.sync()`.

**Tech Stack:** Java 21, eidos-api (AgentRegistry, AgentGoal, GoalLifecycleState), neocortex mindmap-api (GoalLifecycleProvider), blocks-core (SocialAvatarCognition, CognitiveGoalOrchestrator), JUnit 5, AssertJ, Mockito

## Global Constraints

- All repos are pre-release — no backward compatibility concerns
- eidos-api is a pure Java module — no CDI, no Quarkus
- blocks-core depends on eidos-api and neocortex mindmap-api
- `GoalLifecycleState` enum values: ACTIVE, BLOCKED, DEFERRED, COMPLETED, ABANDONED, DORMANT
- `GoalRevision` record fields: goalNodeId, goalName, decaySignal, eidosGoalName
- Signal-to-state mapping: "dormant" → DORMANT, "abandon" → ABANDONED

---

## Batch 1: eidos-api — updateGoalLifecycleState default method

### Task 1: Add updateGoalLifecycleState to AgentRegistry

**Files:**
- Modify: `/Users/mdproctor/claude/casehub/slots/203/eidos/api/src/main/java/io/casehub/eidos/api/AgentRegistry.java`
- Modify: `/Users/mdproctor/claude/casehub/slots/203/eidos/api/src/test/java/io/casehub/eidos/api/AgentRegistrySpiTest.java`

**Interfaces:**
- Consumes: `AgentRegistry.findById(agentId, tenancyId)`, `AgentRegistry.register(descriptor)`, `AgentGoal.toBuilder().lifecycleState(state).build()`, `AgentDescriptor.toBuilder().goals(list).build()`
- Produces: `AgentRegistry.updateGoalLifecycleState(String agentId, String tenancyId, String goalName, GoalLifecycleState newState)` — default method, used by blocks Task 2

- [ ] **Step 1: Write failing tests**

Add three tests to `AgentRegistrySpiTest.java`:

```java
@Test
void updateGoalLifecycleState_transitionsMatchingGoal() {
    var store = new java.util.concurrent.ConcurrentHashMap<String, AgentDescriptor>();
    AgentRegistry registry = new AgentRegistry() {
        @Override public void register(AgentDescriptor d) { store.put(d.agentId(), d); }
        @Override public Optional<AgentDescriptor> findById(String id, String tid) {
            return Optional.ofNullable(store.get(id)).filter(d -> d.tenancyId().equals(tid));
        }
        @Override public List<AgentMatch> find(AgentQuery q) { return List.of(); }
    };

    var goal = new AgentGoal("research", "Do research", GoalPriority.HIGH,
            Visibility.PUBLIC, List.of(), null, GoalLifecycleState.ACTIVE, null);
    var descriptor = AgentDescriptor.builder()
            .agentId("a1").name("Agent").slot("default").tenancyId("t1")
            .goals(List.of(goal)).build();
    registry.register(descriptor);

    registry.updateGoalLifecycleState("a1", "t1", "research", GoalLifecycleState.DORMANT);

    var updated = registry.findById("a1", "t1").orElseThrow();
    assertThat(updated.goals()).hasSize(1);
    assertThat(updated.goals().get(0).lifecycleState()).isEqualTo(GoalLifecycleState.DORMANT);
}

@Test
void updateGoalLifecycleState_leavesOtherGoalsUnchanged() {
    var store = new java.util.concurrent.ConcurrentHashMap<String, AgentDescriptor>();
    AgentRegistry registry = new AgentRegistry() {
        @Override public void register(AgentDescriptor d) { store.put(d.agentId(), d); }
        @Override public Optional<AgentDescriptor> findById(String id, String tid) {
            return Optional.ofNullable(store.get(id)).filter(d -> d.tenancyId().equals(tid));
        }
        @Override public List<AgentMatch> find(AgentQuery q) { return List.of(); }
    };

    var goal1 = new AgentGoal("research", "Do research", GoalPriority.HIGH,
            Visibility.PUBLIC, List.of(), null, GoalLifecycleState.ACTIVE, null);
    var goal2 = new AgentGoal("learn", "Learn things", GoalPriority.MEDIUM,
            Visibility.PUBLIC, List.of(), null, GoalLifecycleState.ACTIVE, null);
    var descriptor = AgentDescriptor.builder()
            .agentId("a1").name("Agent").slot("default").tenancyId("t1")
            .goals(List.of(goal1, goal2)).build();
    registry.register(descriptor);

    registry.updateGoalLifecycleState("a1", "t1", "research", GoalLifecycleState.ABANDONED);

    var updated = registry.findById("a1", "t1").orElseThrow();
    assertThat(updated.goals()).hasSize(2);
    assertThat(updated.goals().stream().filter(g -> g.name().equals("research"))
            .findFirst().orElseThrow().lifecycleState()).isEqualTo(GoalLifecycleState.ABANDONED);
    assertThat(updated.goals().stream().filter(g -> g.name().equals("learn"))
            .findFirst().orElseThrow().lifecycleState()).isEqualTo(GoalLifecycleState.ACTIVE);
}

@Test
void updateGoalLifecycleState_noOpWhenAgentNotFound() {
    AgentRegistry registry = new AgentRegistry() {
        @Override public void register(AgentDescriptor d) {
            throw new AssertionError("register should not be called");
        }
        @Override public Optional<AgentDescriptor> findById(String id, String tid) {
            return Optional.empty();
        }
        @Override public List<AgentMatch> find(AgentQuery q) { return List.of(); }
    };

    registry.updateGoalLifecycleState("missing", "t1", "goal", GoalLifecycleState.DORMANT);
    // no exception = pass
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl api -f /Users/mdproctor/claude/casehub/slots/203/eidos/pom.xml -Dtest=AgentRegistrySpiTest`
Expected: FAIL — `updateGoalLifecycleState` method does not exist

- [ ] **Step 3: Implement the default method**

Add to `AgentRegistry.java` after the `find` method:

```java
default void updateGoalLifecycleState(String agentId, String tenancyId,
                                       String goalName, GoalLifecycleState newState) {
    findById(agentId, tenancyId).ifPresent(descriptor -> {
        var updatedGoals = descriptor.goals().stream()
                .map(g -> g.name().equals(goalName)
                        ? g.toBuilder().lifecycleState(newState).build()
                        : g)
                .toList();
        register(descriptor.toBuilder().goals(updatedGoals).build());
    });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl api -f /Users/mdproctor/claude/casehub/slots/203/eidos/pom.xml -Dtest=AgentRegistrySpiTest`
Expected: PASS — all 4 tests (1 existing + 3 new)

- [ ] **Step 5: Install eidos-api SNAPSHOT**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl api -f /Users/mdproctor/claude/casehub/slots/203/eidos/pom.xml -DskipTests`

This makes the updated `casehub-eidos-api` available to blocks.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/203/eidos add api/src/main/java/io/casehub/eidos/api/AgentRegistry.java api/src/test/java/io/casehub/eidos/api/AgentRegistrySpiTest.java
git -C /Users/mdproctor/claude/casehub/slots/203/eidos commit -m "feat(#300): add updateGoalLifecycleState default method to AgentRegistry

Targeted goal lifecycle transition that avoids full descriptor rebuild.
Default does read-modify-write via findById + register; implementations
can override with optimized paths.

Refs blocks#300"
```

---

## Batch 2: blocks — Revision consumption and GoalLifecycleProvider

### Task 2: Add consumeGoalRevisions to SocialAvatarCognition

**Files:**
- Modify: `/Users/mdproctor/claude/casehub/slots/203/blocks/blocks-core/src/main/java/io/casehub/blocks/agentic/social/prompt/SocialAvatarCognition.java`
- Modify: `/Users/mdproctor/claude/casehub/slots/203/blocks/blocks-core/src/test/java/io/casehub/blocks/agentic/social/prompt/SocialAvatarCognitionTest.java`

**Interfaces:**
- Consumes: `CognitiveGoalOrchestrator.pendingRevisions(agentId, tenantId)` → `List<GoalRevision>`, `GoalRevision.eidosGoalName()`, `GoalRevision.decaySignal()`, `AgentRegistry.updateGoalLifecycleState(agentId, tenancyId, goalName, state)` (from Task 1)
- Produces: After `SocialAvatarCognition.tick()`, pending decay-signal revisions are consumed and eidos goals transitioned

- [ ] **Step 1: Write failing tests**

Add to `SocialAvatarCognitionTest.java`. First, the test needs a builder-constructed instance with MindMapStore, GoalAppraisal, and CaseMemoryStore to enable the cognitiveGoals path. Add a helper and three new tests:

```java
import io.casehub.eidos.api.AgentGoal;
import io.casehub.eidos.api.GoalLifecycleState;
import io.casehub.eidos.api.GoalPriority;
import io.casehub.eidos.api.Visibility;
import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.mindmap.GoalAppraisal;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.MindMapSubgraph;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import org.mockito.ArgumentCaptor;

// New test class for revision consumption — add after existing tests

@Test
void tick_consumesDormantRevisionAndTransitionsGoal() {
    var mindMapStore = mock(MindMapStore.class);
    var goalAppraisal = mock(GoalAppraisal.class);
    var memoryStore = mock(CaseMemoryStore.class);

    // Return empty goal subgraph so CognitiveGoalOrchestrator.doTick doesn't NPE
    when(mindMapStore.listSubgraphs("t1")).thenReturn(List.of());

    var descriptor = AgentDescriptor.builder()
            .agentId("a1").name("Agent").slot("default").tenancyId("t1")
            .goals(List.of(new AgentGoal("research", "Research", GoalPriority.HIGH,
                    Visibility.PUBLIC, List.of(), null, GoalLifecycleState.ACTIVE, null)))
            .build();
    when(registry.findById("a1", "t1")).thenReturn(Optional.of(descriptor));

    // Build a node with decay-signal to be found by checkDecaySignal
    var goalNode = mock(io.casehub.neocortex.mindmap.MindMapNode.class);
    when(goalNode.id()).thenReturn("node-1");
    when(goalNode.name()).thenReturn("Research Goal");
    when(goalNode.property("decay-signal")).thenReturn(Optional.of("dormant"));
    when(goalNode.property("eidos-goal-name")).thenReturn(Optional.of("research"));
    when(goalNode.property("status")).thenReturn(Optional.of("active"));
    when(goalNode.property("priority")).thenReturn(Optional.empty());
    when(goalNode.property("surfacing-progress-gap")).thenReturn(Optional.empty());
    when(goalNode.property("surfaced-count")).thenReturn(Optional.empty());
    when(goalNode.property("last-progress-at")).thenReturn(Optional.empty());
    when(goalNode.property("last-surfaced-at")).thenReturn(Optional.empty());

    var goalSg = mock(MindMapSubgraph.class);
    when(goalSg.type()).thenReturn(SubgraphTypes.GOAL);
    when(goalSg.id()).thenReturn("sg-1");
    when(mindMapStore.listSubgraphs("t1")).thenReturn(List.of(goalSg));
    when(mindMapStore.nodesIn("sg-1", "t1")).thenReturn(List.of(goalNode));

    var cog = SocialAvatarCognition.builder()
            .mood(mood).drives(drives).mentalModel(mentalModel)
            .userModel(userModel).strategy(strategy)
            .agentRegistry(Optional.of(registry))
            .mindMapStore(Optional.of(mindMapStore))
            .goalAppraisal(Optional.of(goalAppraisal))
            .memoryStore(Optional.of(memoryStore))
            .build();

    cog.tick("a1", "t1", Set.of());

    verify(registry).updateGoalLifecycleState("a1", "t1", "research",
            GoalLifecycleState.DORMANT);
}

@Test
void tick_skipsRevisionWithoutEidosGoalName() {
    var mindMapStore = mock(MindMapStore.class);
    var goalAppraisal = mock(GoalAppraisal.class);
    var memoryStore = mock(CaseMemoryStore.class);

    var goalNode = mock(io.casehub.neocortex.mindmap.MindMapNode.class);
    when(goalNode.id()).thenReturn("node-1");
    when(goalNode.name()).thenReturn("Standalone Goal");
    when(goalNode.property("decay-signal")).thenReturn(Optional.of("dormant"));
    when(goalNode.property("eidos-goal-name")).thenReturn(Optional.empty());
    when(goalNode.property("status")).thenReturn(Optional.of("active"));
    when(goalNode.property("priority")).thenReturn(Optional.empty());
    when(goalNode.property("surfacing-progress-gap")).thenReturn(Optional.empty());
    when(goalNode.property("surfaced-count")).thenReturn(Optional.empty());
    when(goalNode.property("last-progress-at")).thenReturn(Optional.empty());
    when(goalNode.property("last-surfaced-at")).thenReturn(Optional.empty());

    var goalSg = mock(MindMapSubgraph.class);
    when(goalSg.type()).thenReturn(SubgraphTypes.GOAL);
    when(goalSg.id()).thenReturn("sg-1");
    when(mindMapStore.listSubgraphs("t1")).thenReturn(List.of(goalSg));
    when(mindMapStore.nodesIn("sg-1", "t1")).thenReturn(List.of(goalNode));

    var cog = SocialAvatarCognition.builder()
            .mood(mood).drives(drives).mentalModel(mentalModel)
            .userModel(userModel).strategy(strategy)
            .agentRegistry(Optional.of(registry))
            .mindMapStore(Optional.of(mindMapStore))
            .goalAppraisal(Optional.of(goalAppraisal))
            .memoryStore(Optional.of(memoryStore))
            .build();

    cog.tick("a1", "t1", Set.of());

    verify(registry, never()).updateGoalLifecycleState(any(), any(), any(), any());
}

@Test
void tick_isolatesErrorsPerRevision() {
    var mindMapStore = mock(MindMapStore.class);
    var goalAppraisal = mock(GoalAppraisal.class);
    var memoryStore = mock(CaseMemoryStore.class);

    var node1 = mock(io.casehub.neocortex.mindmap.MindMapNode.class);
    when(node1.id()).thenReturn("n1");
    when(node1.name()).thenReturn("G1");
    when(node1.property("decay-signal")).thenReturn(Optional.of("dormant"));
    when(node1.property("eidos-goal-name")).thenReturn(Optional.of("goal-a"));
    when(node1.property("status")).thenReturn(Optional.of("active"));
    when(node1.property("priority")).thenReturn(Optional.empty());
    when(node1.property("surfacing-progress-gap")).thenReturn(Optional.empty());
    when(node1.property("surfaced-count")).thenReturn(Optional.empty());
    when(node1.property("last-progress-at")).thenReturn(Optional.empty());
    when(node1.property("last-surfaced-at")).thenReturn(Optional.empty());

    var node2 = mock(io.casehub.neocortex.mindmap.MindMapNode.class);
    when(node2.id()).thenReturn("n2");
    when(node2.name()).thenReturn("G2");
    when(node2.property("decay-signal")).thenReturn(Optional.of("abandon"));
    when(node2.property("eidos-goal-name")).thenReturn(Optional.of("goal-b"));
    when(node2.property("status")).thenReturn(Optional.of("active"));
    when(node2.property("priority")).thenReturn(Optional.empty());
    when(node2.property("surfacing-progress-gap")).thenReturn(Optional.empty());
    when(node2.property("surfaced-count")).thenReturn(Optional.empty());
    when(node2.property("last-progress-at")).thenReturn(Optional.empty());
    when(node2.property("last-surfaced-at")).thenReturn(Optional.empty());

    var goalSg = mock(MindMapSubgraph.class);
    when(goalSg.type()).thenReturn(SubgraphTypes.GOAL);
    when(goalSg.id()).thenReturn("sg-1");
    when(mindMapStore.listSubgraphs("t1")).thenReturn(List.of(goalSg));
    when(mindMapStore.nodesIn("sg-1", "t1")).thenReturn(List.of(node1, node2));

    // First call throws, second should still succeed
    org.mockito.Mockito.doThrow(new RuntimeException("registry down"))
            .when(registry).updateGoalLifecycleState("a1", "t1", "goal-a",
                    GoalLifecycleState.DORMANT);

    var cog = SocialAvatarCognition.builder()
            .mood(mood).drives(drives).mentalModel(mentalModel)
            .userModel(userModel).strategy(strategy)
            .agentRegistry(Optional.of(registry))
            .mindMapStore(Optional.of(mindMapStore))
            .goalAppraisal(Optional.of(goalAppraisal))
            .memoryStore(Optional.of(memoryStore))
            .build();

    cog.tick("a1", "t1", Set.of());

    // Second revision still processed despite first failing
    verify(registry).updateGoalLifecycleState("a1", "t1", "goal-b",
            GoalLifecycleState.ABANDONED);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core -f /Users/mdproctor/claude/casehub/slots/203/blocks/pom.xml -Dtest=SocialAvatarCognitionTest`
Expected: FAIL — `consumeGoalRevisions` method does not exist / `updateGoalLifecycleState` not called

- [ ] **Step 3: Implement consumeGoalRevisions**

Add to `SocialAvatarCognition.java`:

1. Add import: `import io.casehub.eidos.api.GoalLifecycleState;`

2. Modify the `tick()` method to call `consumeGoalRevisions` after `core.tick()`:

```java
@Override
public void tick(String agentId, String tenantId, Set<String> activeSubjects) {
    var descriptor = resolveDescriptor(agentId, tenantId);
    core.tick(agentId, tenantId, descriptor, (aid, tid) -> activeSubjects);
    consumeGoalRevisions(agentId, tenantId);
}
```

3. Add the private method:

```java
private void consumeGoalRevisions(String agentId, String tenantId) {
    if (cognitiveGoals == null || agentRegistry.isEmpty()) return;

    for (var revision : cognitiveGoals.pendingRevisions(agentId, tenantId)) {
        if (revision.eidosGoalName() == null) continue;

        GoalLifecycleState newState = switch (revision.decaySignal()) {
            case "dormant" -> GoalLifecycleState.DORMANT;
            case "abandon" -> GoalLifecycleState.ABANDONED;
            default -> null;
        };
        if (newState == null) continue;

        try {
            agentRegistry.get().updateGoalLifecycleState(
                    agentId, tenantId, revision.eidosGoalName(), newState);
        } catch (Exception e) {
            LOG.log(System.Logger.Level.WARNING,
                    "Failed to transition goal '" + revision.eidosGoalName() + "'", e);
        }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core -f /Users/mdproctor/claude/casehub/slots/203/blocks/pom.xml -Dtest=SocialAvatarCognitionTest`
Expected: PASS — all tests including the 3 new ones

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/203/blocks add blocks-core/src/main/java/io/casehub/blocks/agentic/social/prompt/SocialAvatarCognition.java blocks-core/src/test/java/io/casehub/blocks/agentic/social/prompt/SocialAvatarCognitionTest.java
git -C /Users/mdproctor/claude/casehub/slots/203/blocks commit -m "feat(#300): consume GoalRevision decay signals in SocialAvatarCognition

After each tick, reads pendingRevisions from CognitiveGoalOrchestrator
and transitions eidos goals: dormant→DORMANT, abandon→ABANDONED.
Error isolation per revision. Skips standalone goals (no eidosGoalName).

Refs #300"
```

### Task 3: Add EidosGoalLifecycleProvider

**Files:**
- Create: `/Users/mdproctor/claude/casehub/slots/203/blocks/blocks-core/src/main/java/io/casehub/blocks/agentic/social/goal/EidosGoalLifecycleProvider.java`
- Create: `/Users/mdproctor/claude/casehub/slots/203/blocks/blocks-core/src/test/java/io/casehub/blocks/agentic/social/goal/EidosGoalLifecycleProviderTest.java`

**Interfaces:**
- Consumes: `AgentRegistry.findById(agentId, tenancyId)` → `Optional<AgentDescriptor>`, `AgentGoal.lifecycleState()` → `GoalLifecycleState`, `GoalLifecycleState.name().toLowerCase()` → status string
- Produces: `GoalLifecycleProvider.getLifecycleStates(agentId, tenantId)` → `Map<String, String>` of goalName → status. Used by neocortex `GoalResolutionPhase.sync()` to clear `decay-signal` properties.

- [ ] **Step 1: Write failing test**

Create `EidosGoalLifecycleProviderTest.java`:

```java
package io.casehub.blocks.agentic.social.goal;

import io.casehub.eidos.api.AgentDescriptor;
import io.casehub.eidos.api.AgentGoal;
import io.casehub.eidos.api.AgentRegistry;
import io.casehub.eidos.api.GoalLifecycleState;
import io.casehub.eidos.api.GoalPriority;
import io.casehub.eidos.api.Visibility;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class EidosGoalLifecycleProviderTest {

    @Test
    void returnsLifecycleStatesFromRegistry() {
        var registry = mock(AgentRegistry.class);
        var descriptor = AgentDescriptor.builder()
                .agentId("a1").name("Agent").slot("default").tenancyId("t1")
                .goals(List.of(
                        new AgentGoal("research", "Research", GoalPriority.HIGH,
                                Visibility.PUBLIC, List.of(), null,
                                GoalLifecycleState.DORMANT, null),
                        new AgentGoal("learn", "Learn", GoalPriority.MEDIUM,
                                Visibility.PUBLIC, List.of(), null,
                                GoalLifecycleState.ACTIVE, null)))
                .build();
        when(registry.findById("a1", "t1")).thenReturn(Optional.of(descriptor));

        var provider = new EidosGoalLifecycleProvider(registry);
        var states = provider.getLifecycleStates("a1", "t1");

        assertThat(states).containsEntry("research", "dormant");
        assertThat(states).containsEntry("learn", "active");
    }

    @Test
    void returnsEmptyMapWhenAgentNotFound() {
        var registry = mock(AgentRegistry.class);
        when(registry.findById("missing", "t1")).thenReturn(Optional.empty());

        var provider = new EidosGoalLifecycleProvider(registry);
        var states = provider.getLifecycleStates("missing", "t1");

        assertThat(states).isEmpty();
    }

    @Test
    void skipsGoalsWithNullLifecycleState() {
        var registry = mock(AgentRegistry.class);
        var descriptor = AgentDescriptor.builder()
                .agentId("a1").name("Agent").slot("default").tenancyId("t1")
                .goals(List.of(
                        new AgentGoal("old-goal", "Old", GoalPriority.LOW,
                                Visibility.PUBLIC, List.of(), null),
                        new AgentGoal("new-goal", "New", GoalPriority.HIGH,
                                Visibility.PUBLIC, List.of(), null,
                                GoalLifecycleState.ACTIVE, null)))
                .build();
        when(registry.findById("a1", "t1")).thenReturn(Optional.of(descriptor));

        var provider = new EidosGoalLifecycleProvider(registry);
        var states = provider.getLifecycleStates("a1", "t1");

        assertThat(states).hasSize(1);
        assertThat(states).containsEntry("new-goal", "active");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core -f /Users/mdproctor/claude/casehub/slots/203/blocks/pom.xml -Dtest=EidosGoalLifecycleProviderTest`
Expected: FAIL — `EidosGoalLifecycleProvider` class does not exist

- [ ] **Step 3: Implement EidosGoalLifecycleProvider**

Create `EidosGoalLifecycleProvider.java`:

```java
package io.casehub.blocks.agentic.social.goal;

import io.casehub.eidos.api.AgentGoal;
import io.casehub.eidos.api.AgentRegistry;
import io.casehub.neocortex.mindmap.GoalLifecycleProvider;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.util.Map;
import java.util.stream.Collectors;

@ApplicationScoped
public class EidosGoalLifecycleProvider implements GoalLifecycleProvider {

    private final AgentRegistry agentRegistry;

    @Inject
    public EidosGoalLifecycleProvider(Instance<AgentRegistry> agentRegistry) {
        this.agentRegistry = agentRegistry.isResolvable() ? agentRegistry.get() : null;
    }

    EidosGoalLifecycleProvider(AgentRegistry agentRegistry) {
        this.agentRegistry = agentRegistry;
    }

    @Override
    public Map<String, String> getLifecycleStates(String agentId, String tenantId) {
        if (agentRegistry == null) return Map.of();

        return agentRegistry.findById(agentId, tenantId)
                .map(descriptor -> descriptor.goals().stream()
                        .filter(g -> g.lifecycleState() != null)
                        .collect(Collectors.toMap(
                                AgentGoal::name,
                                g -> g.lifecycleState().name().toLowerCase())))
                .orElse(Map.of());
    }
}
```

The class has two constructors:
- CDI constructor (`@Inject`) taking `Instance<AgentRegistry>` for graceful degradation when no registry is available
- Package-private test constructor taking a direct `AgentRegistry` for unit testing

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core -f /Users/mdproctor/claude/casehub/slots/203/blocks/pom.xml -Dtest=EidosGoalLifecycleProviderTest`
Expected: PASS — all 3 tests

- [ ] **Step 5: Run full blocks-core test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl blocks-core -f /Users/mdproctor/claude/casehub/slots/203/blocks/pom.xml`
Expected: PASS — all existing tests plus the 6 new ones

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/203/blocks add blocks-core/src/main/java/io/casehub/blocks/agentic/social/goal/EidosGoalLifecycleProvider.java blocks-core/src/test/java/io/casehub/blocks/agentic/social/goal/EidosGoalLifecycleProviderTest.java
git -C /Users/mdproctor/claude/casehub/slots/203/blocks commit -m "feat(#300): EidosGoalLifecycleProvider bridges eidos goal states to neocortex

Reads AgentGoal.lifecycleState from AgentRegistry and returns as
Map<goalName, status> for GoalResolutionPhase.sync() to consume.
Displaces NoOpGoalLifecycleProvider via CDI priority.

Closes #300"
```

## References

- [2026-09-29-goal-revision-decay-lifecycle-design.md] — design spec this plan implements
- [eidos: api/src/main/java/io/casehub/eidos/api/AgentRegistry.java] — SPI to extend
- [eidos: api/src/main/java/io/casehub/eidos/api/AgentGoal.java] — lifecycleState field
- [eidos: api/src/main/java/io/casehub/eidos/api/GoalLifecycleState.java] — enum values
- [eidos: api/src/test/java/io/casehub/eidos/api/AgentRegistrySpiTest.java] — existing test
- [blocks: blocks-core/.../SocialAvatarCognition.java] — composition root
- [blocks: blocks-core/.../CognitiveGoalOrchestrator.java:76] — pendingRevisions()
- [blocks: blocks-core/.../SocialAvatarCognitionTest.java] — existing test
- [neocortex: mindmap-api/.../GoalLifecycleProvider.java] — SPI to implement
- [neocortex: mindmap-intelligence/.../GoalResolutionPhase.java:305] — sync() consumer
- [GitHub blocks#300] — focal issue
- [GitHub blocks#298] — parent epic
