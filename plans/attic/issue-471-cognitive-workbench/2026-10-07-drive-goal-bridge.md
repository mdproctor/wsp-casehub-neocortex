# Drive Goal Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #463 — feat: bridge drive-proposed goals to MindMap GOAL nodes
**Issue group:** #463

**Goal:** Bridge `GoalProposalOrchestrator`'s registered drive proposals into persistent MindMap GOAL nodes with deduplication and abandonment sync.

**Architecture:** New `DriveGoalBridgeParticipant` implements `CognitionTickParticipant` at TERMINAL phase. It reads registered proposals from `GoalProposalOrchestrator`, deduplicates via TermNormalizer + Jaro-Winkler against existing GOAL subgraph nodes, and creates/enriches/updates nodes via `MindMapStore`. `EmergentGoalPromptSection` is fixed to filter drive-originated nodes from the cognitive path to prevent double-counting.

**Tech Stack:** Java 21, Quarkus (CDI), MindMap SPI, knowledge-pipeline-api (TermNormalizer)

## Global Constraints

- Java 21 source level, Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Module: `cognition` (`io.casehub.neocortex.cognition.goal`)
- Test module: `cognition/src/test/`
- InMemoryMindMapStore for unit tests
- NoOpTermNormalizer (passthrough) — "general" domain not yet implemented
- All commits reference #463

---

## Batch 1: Core Bridge

### Task 1: Add `registeredGoals()` accessor to GoalProposalOrchestrator

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java:105`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestratorTest.java`

**Interfaces:**
- Produces: `GoalProposalOrchestrator.registeredGoals(String agentId, String tenantId) → List<DriveGoalProposal>` — returns only registered goals (not cached proposals). Empty list when no state exists.

- [ ] **Step 1: Write the failing test**

```java
@Test
void registeredGoals_returnsOnlyRegisteredNotCached() {
    var proposal = new DriveGoalProposal(
            DriveAxis.CURIOSITY, "Learn AI",
            "Study artificial intelligence fundamentals",
            "High curiosity drive", 0.8);
    orchestrator.registerGoals("agent1", "tenant1", List.of(proposal));

    List<DriveGoalProposal> registered = orchestrator.registeredGoals("agent1", "tenant1");

    assertThat(registered).hasSize(1);
    assertThat(registered.getFirst().goalName()).isEqualTo("Learn AI");
}

@Test
void registeredGoals_returnsEmptyListWhenNoState() {
    List<DriveGoalProposal> registered = orchestrator.registeredGoals("unknown", "tenant");

    assertThat(registered).isEmpty();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=GoalProposalOrchestratorTest#registeredGoals_returnsOnlyRegisteredNotCached -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — method `registeredGoals` does not exist

- [ ] **Step 3: Implement `registeredGoals()` method**

Add to `GoalProposalOrchestrator.java` after the `currentProposals()` method (line ~113):

```java
public List<DriveGoalProposal> registeredGoals(String agentId, String tenantId) {
    GoalProposalState state = states.get(agentId + "|" + tenantId);
    return state == null ? List.of() : List.copyOf(state.registeredGoals);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=GoalProposalOrchestratorTest#registeredGoals_returnsOnlyRegisteredNotCached+registeredGoals_returnsEmptyListWhenNoState -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestratorTest.java
git commit -m "feat(#463): add registeredGoals() accessor to GoalProposalOrchestrator

Exposes registered goals separately from cached proposals.
The drive goal bridge needs this as its single data source
for both creation and abandonment detection.

Refs #463"
```

### Task 2: Create DriveGoalBridgeParticipant with node creation

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/goal/DriveGoalBridgeParticipant.java`
- Modify: `cognition/pom.xml` (add knowledge-pipeline-api dependency)
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/goal/DriveGoalBridgeParticipantTest.java`

**Interfaces:**
- Consumes: `GoalProposalOrchestrator.registeredGoals(String, String) → List<DriveGoalProposal>` (Task 1)
- Consumes: `MindMapStore.addNode(NodeInput, String tenantId) → MindMapNode`
- Consumes: `MindMapStore.findSubgraph(String type, String tenantId) → Optional<MindMapSubgraph>`
- Consumes: `MindMapStore.createSubgraph(SubgraphInput, String tenantId) → MindMapSubgraph`
- Consumes: `MindMapStore.nodesInSubgraph(String subgraphId, String tenantId) → List<MindMapNode>`
- Consumes: `TermNormalizer.normalize(String term, String domain) → ExpandedTerm`
- Consumes: `JaroWinkler.similarity(String, String) → double`
- Produces: `DriveGoalBridgeParticipant` class implementing `CognitionTickParticipant`

- [ ] **Step 1: Add knowledge-pipeline-api dependency to cognition/pom.xml**

Add to `<dependencies>` section:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-knowledge-pipeline-api</artifactId>
</dependency>
```

- [ ] **Step 2: Write failing test — new node creation**

```java
@Test
void tick_createsGoalNodeForNewRegisteredProposal() {
    var store = new InMemoryMindMapStore();
    var normalizer = TermNormalizer.passthrough();
    var orchestrator = createOrchestrator();
    var bridge = new DriveGoalBridgeParticipant(orchestrator, store, normalizer, enabledConfig());

    var proposal = new DriveGoalProposal(
            DriveAxis.CURIOSITY, "Learn Spanish",
            "Study the Spanish language to conversational fluency",
            "Strong curiosity about languages", 0.85);
    orchestrator.registerGoals("agent1", "tenant1", List.of(proposal));

    bridge.tick(context("agent1", "tenant1"));

    var subgraph = store.findSubgraph("goal", "tenant1");
    assertThat(subgraph).isPresent();
    var nodes = store.nodesInSubgraph(subgraph.get().id(), "tenant1");
    assertThat(nodes).hasSize(1);

    var node = nodes.getFirst();
    assertThat(node.name()).isEqualTo("Learn Spanish");
    assertThat(node.properties().get("origin")).isEqualTo("drive-proposal");
    assertThat(node.properties().get("origin-drive")).isEqualTo("CURIOSITY");
    assertThat(node.properties().get("formation-reason")).isEqualTo("Strong curiosity about languages");
    assertThat(node.properties().get("status")).isEqualTo("active");
    assertThat(node.properties().get("description")).isEqualTo("Study the Spanish language to conversational fluency");
    assertThat(node.properties().get("horizon")).isEqualTo("long");
    assertThat(node.properties().get("drive-intensity")).isEqualTo("0.85");
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=DriveGoalBridgeParticipantTest#tick_createsGoalNodeForNewRegisteredProposal -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — class `DriveGoalBridgeParticipant` does not exist

- [ ] **Step 4: Implement DriveGoalBridgeParticipant**

```java
package io.casehub.neocortex.cognition.goal;

import io.casehub.neocortex.cognition.core.CognitionConfig;
import io.casehub.neocortex.cognition.core.CognitionTickContext;
import io.casehub.neocortex.cognition.core.CognitionTickParticipant;
import io.casehub.neocortex.cognition.drive.DriveAxis;
import io.casehub.neocortex.knowledge.TermNormalizer;
import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.intelligence.consolidation.JaroWinkler;
import io.casehub.eidos.api.GoalPriority;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;

public final class DriveGoalBridgeParticipant implements CognitionTickParticipant {

    private static final double JARO_WINKLER_THRESHOLD = 0.85;

    private final GoalProposalOrchestrator orchestrator;
    private final MindMapStore store;
    private final TermNormalizer normalizer;
    private final CognitionConfig config;
    private final ConcurrentHashMap<String, BridgeState> states = new ConcurrentHashMap<>();

    public DriveGoalBridgeParticipant(GoalProposalOrchestrator orchestrator,
                                       MindMapStore store,
                                       TermNormalizer normalizer,
                                       CognitionConfig config) {
        this.orchestrator = Objects.requireNonNull(orchestrator);
        this.store = Objects.requireNonNull(store);
        this.normalizer = Objects.requireNonNull(normalizer);
        this.config = Objects.requireNonNull(config);
    }

    @Override
    public void tick(CognitionTickContext context) {
        if (!config.goalsEnabled()) return;

        String agentId = context.agentId();
        String tenantId = context.tenantId();
        String key = agentId + "|" + tenantId;

        List<DriveGoalProposal> registered = orchestrator.registeredGoals(agentId, tenantId);
        BridgeState state = states.computeIfAbsent(key, k -> new BridgeState());

        String subgraphId = ensureGoalSubgraph(tenantId);

        Set<String> currentNames = new HashSet<>();
        for (DriveGoalProposal proposal : registered) {
            currentNames.add(proposal.goalName());
            if (state.persistedNames.contains(proposal.goalName())) continue;
            bridgeProposal(proposal, subgraphId, tenantId, agentId, state);
        }

        syncAbandonments(state, currentNames, tenantId);
    }

    private String ensureGoalSubgraph(String tenantId) {
        return store.findSubgraph(SubgraphTypes.GOAL, tenantId)
                .map(MindMapSubgraph::id)
                .orElseGet(() -> store.createSubgraph(
                        new SubgraphInput(SubgraphTypes.GOAL), tenantId).id());
    }

    private void bridgeProposal(DriveGoalProposal proposal, String subgraphId,
                                  String tenantId, String agentId, BridgeState state) {
        String canonical = normalizer.normalize(proposal.goalName(), "general").canonical();
        List<MindMapNode> existingGoals = store.nodesInSubgraph(subgraphId, tenantId);

        MindMapNode match = findMatch(canonical, existingGoals);
        if (match != null) {
            enrichExistingNode(match, proposal, tenantId);
            state.persistedNames.add(proposal.goalName());
            state.nameToNodeId.put(proposal.goalName(), match.id());
        } else {
            MindMapNode created = createGoalNode(proposal, subgraphId, tenantId, agentId);
            state.persistedNames.add(proposal.goalName());
            state.nameToNodeId.put(proposal.goalName(), created.id());
        }
    }

    private MindMapNode findMatch(String canonical, List<MindMapNode> existing) {
        for (MindMapNode node : existing) {
            if (canonical.equalsIgnoreCase(node.name())) return node;
            String desc = node.properties().get("description");
            if (desc != null && canonical.equalsIgnoreCase(desc)) return node;
        }
        for (MindMapNode node : existing) {
            if (JaroWinkler.similarity(canonical, node.name()) >= JARO_WINKLER_THRESHOLD) return node;
            String desc = node.properties().get("description");
            if (desc != null && JaroWinkler.similarity(canonical, desc) >= JARO_WINKLER_THRESHOLD) return node;
        }
        return null;
    }

    private MindMapNode createGoalNode(DriveGoalProposal proposal, String subgraphId,
                                        String tenantId, String agentId) {
        Map<String, String> props = new LinkedHashMap<>();
        props.put("description", proposal.goalDescription());
        props.put("status", "active");
        props.put("origin", "drive-proposal");
        props.put("origin-drive", proposal.axis().name());
        props.put("formation-reason", proposal.formationReason());
        props.put("horizon", mapHorizon(proposal.suggestedPriority()));
        props.put("drive-intensity", String.valueOf(proposal.driveIntensity()));
        props.put("agent-id", agentId);

        NodeInput input = NodeInput.of(proposal.goalName(), subgraphId)
                .withProperties(props)
                .withPrincipalId(new PrincipalId(agentId));
        return store.addNode(input, tenantId);
    }

    private void enrichExistingNode(MindMapNode node, DriveGoalProposal proposal, String tenantId) {
        Map<String, String> updates = new LinkedHashMap<>();
        updates.put("origin-drive", proposal.axis().name());
        updates.put("formation-reason", proposal.formationReason());
        store.updateNode(node.id(), NodeUpdate.empty().withPropertiesToSet(updates), tenantId);
    }

    private void syncAbandonments(BridgeState state, Set<String> currentNames, String tenantId) {
        var abandoned = new ArrayList<String>();
        for (String name : state.persistedNames) {
            if (!currentNames.contains(name)) {
                String nodeId = state.nameToNodeId.get(name);
                if (nodeId != null) {
                    Map<String, String> updates = new LinkedHashMap<>();
                    updates.put("status", "dormant");
                    updates.put("abandonment-reason", "drive-intensity-below-threshold");
                    store.updateNode(nodeId, NodeUpdate.empty().withPropertiesToSet(updates), tenantId);
                }
                abandoned.add(name);
            }
        }
        for (String name : abandoned) {
            state.persistedNames.remove(name);
            state.nameToNodeId.remove(name);
        }
    }

    private static String mapHorizon(GoalPriority priority) {
        if (priority == null) return "long";
        return switch (priority) {
            case PRIMARY -> "medium";
            case SECONDARY -> "long";
        };
    }

    private static final class BridgeState {
        final Set<String> persistedNames = new HashSet<>();
        final Map<String, String> nameToNodeId = new HashMap<>();
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=DriveGoalBridgeParticipantTest#tick_createsGoalNodeForNewRegisteredProposal -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 6: Write and run additional tests**

Add tests for:
- `tick_idempotent_sameProposalsDoNotCreateDuplicates` — call tick twice with same proposals, verify only one node
- `tick_enrichesExistingNodeOnJaroWinklerMatch` — create an existing GOAL node "Study Spanish", register "Learn Spanish" (Jaro-Winkler ≥ 0.85), verify enrichment not duplication
- `tick_crossPathDedup_matchesAgainstDescriptionProperty` — create node with name=long description (GoalRecognitionPhase style), register a short goalName matching the description
- `tick_syncsAbandonment_marksDormant` — register a goal, tick, unregister it, tick again, verify status="dormant"
- `tick_skipsWhenGoalsDisabled` — config with goalsEnabled=false, verify no nodes created
- `tick_createsSubgraphIfNotExists` — verify GOAL subgraph auto-creation
- `tick_setsAgentIdAndPrincipalId` — verify agent-id property and principalId set on node
- `tick_horizonMapping_primaryMapsMedium` — verify PRIMARY → "medium" and null → "long"

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=DriveGoalBridgeParticipantTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add cognition/pom.xml
git add cognition/src/main/java/io/casehub/neocortex/cognition/goal/DriveGoalBridgeParticipant.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/goal/DriveGoalBridgeParticipantTest.java
git commit -m "feat(#463): create DriveGoalBridgeParticipant with node creation and dedup

Bridges registered drive proposals to MindMap GOAL nodes.
Deduplicates via TermNormalizer + Jaro-Winkler >= 0.85
against existing node names and description properties.
Syncs abandonments to dormant status.

Refs #463"
```

### Task 3: Wire bridge into CognitionCore and fix EmergentGoalPromptSection

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java:565-571`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/EmergentGoalPromptSection.java:35-57`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/core/CognitionCoreTest.java` (existing)
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/prompt/EmergentGoalPromptSectionTest.java` (existing or new)

**Interfaces:**
- Consumes: `DriveGoalBridgeParticipant` (Task 2)
- Consumes: `CognitionCore.addParticipant(CognitionPhase, CognitionTickParticipant)`
- Produces: `CognitionCore.configureDriveGoalBridge(MindMapStore, TermNormalizer)` — new configure method

- [ ] **Step 1: Write failing test — CognitionCore wiring**

```java
@Test
void configureDriveGoalBridge_registersTerminalParticipant() {
    var core = createCoreWithGoalsEnabled();
    var store = new InMemoryMindMapStore();
    var normalizer = TermNormalizer.passthrough();

    core.configureDriveGoalBridge(store, normalizer);

    // Register a goal and tick — verify bridge creates a GOAL node
    core.goals().registerGoals("agent1", "tenant1", List.of(
            new DriveGoalProposal(DriveAxis.CURIOSITY, "Test Goal",
                    "A test goal description", "testing", 0.7)));

    core.tick("agent1", "tenant1", descriptor, resolver);

    var subgraph = store.findSubgraph("goal", "tenant1");
    assertThat(subgraph).isPresent();
    var nodes = store.nodesInSubgraph(subgraph.get().id(), "tenant1");
    assertThat(nodes).hasSize(1);
    assertThat(nodes.getFirst().name()).isEqualTo("Test Goal");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CognitionCoreTest#configureDriveGoalBridge_registersTerminalParticipant -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — method `configureDriveGoalBridge` does not exist

- [ ] **Step 3: Add `configureDriveGoalBridge()` to CognitionCore**

Add after the `configureGutFeeling()` method (around line 571):

```java
public void configureDriveGoalBridge(MindMapStore mindMapStore, TermNormalizer termNormalizer) {
    if (config.goalsEnabled() && goals != null) {
        addParticipant(CognitionPhase.TERMINAL,
                new DriveGoalBridgeParticipant(goals, mindMapStore, termNormalizer, config));
    }
}
```

Add import:
```java
import io.casehub.neocortex.knowledge.TermNormalizer;
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CognitionCoreTest#configureDriveGoalBridge_registersTerminalParticipant -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 5: Write failing test — EmergentGoalPromptSection no double-counting**

```java
@Test
void render_filtersOutDriveOriginatedNodesFromCognitivePath() {
    var orchestrator = createOrchestrator();
    var cognitiveGoals = createCognitiveGoalOrchestrator();
    var section = new EmergentGoalPromptSection(orchestrator, cognitiveGoals, config);

    // Register a drive proposal
    orchestrator.registerGoals("agent1", "tenant1", List.of(
            new DriveGoalProposal(DriveAxis.CURIOSITY, "Learn AI",
                    "Study AI", "curiosity", 0.8)));

    // Simulate the same goal appearing in cognitiveGoals with origin=drive-proposal
    // (as it would after bridge persists it)
    cognitiveGoals.addGoalForTest("agent1", "tenant1",
            new GoalEmotion("Learn AI", 0.7, null, DriveAxis.CURIOSITY, 1, "drive-proposal"));

    String output = section.render(renderContext("agent1", "tenant1"));

    // "Learn AI" should appear only once, not twice
    int count = countOccurrences(output, "Learn AI");
    assertThat(count).isEqualTo(1);
}
```

- [ ] **Step 6: Fix EmergentGoalPromptSection to prevent double-counting**

In `EmergentGoalPromptSection.render()`, filter the cognitive goals path to exclude nodes with `origin=drive-proposal` when drive goals are also present:

```java
if (cognitiveGoals != null) {
    cognitiveGoals.currentState(agentId, tenantId)
                  .ifPresent(state -> state.goals().stream()
                          .filter(ge -> !"drive-proposal".equals(ge.origin()))
                          .forEach(ge -> unified.add(UnifiedGoal.fromCognitive(ge, config.driveWeight()))));
}
```

This requires `GoalEmotion` to carry an `origin` field. If it doesn't, filter by checking if the goal name matches any registered drive proposal:

```java
if (cognitiveGoals != null && driveGoals != null) {
    Set<String> driveNames = driveGoals.registeredGoals(agentId, tenantId)
            .stream().map(DriveGoalProposal::goalName).collect(Collectors.toSet());
    cognitiveGoals.currentState(agentId, tenantId)
                  .ifPresent(state -> state.goals().stream()
                          .filter(ge -> !driveNames.contains(ge.name()))
                          .forEach(ge -> unified.add(UnifiedGoal.fromCognitive(ge, config.driveWeight()))));
} else if (cognitiveGoals != null) {
    cognitiveGoals.currentState(agentId, tenantId)
                  .ifPresent(state -> state.goals().forEach(ge ->
                          unified.add(UnifiedGoal.fromCognitive(ge, config.driveWeight()))));
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmergentGoalPromptSectionTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS (new and existing tests)

- [ ] **Step 8: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: ALL PASS — no regressions

- [ ] **Step 9: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/prompt/EmergentGoalPromptSection.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/core/CognitionCoreTest.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/prompt/EmergentGoalPromptSectionTest.java
git commit -m "feat(#463): wire DriveGoalBridgeParticipant into CognitionCore

Adds configureDriveGoalBridge() to CognitionCore.
Fixes EmergentGoalPromptSection to filter drive-originated
nodes from cognitive path, preventing double-counting.

Refs #463"
```

## Batch 2: Verification and Docs

### Task 4: Full build verification and CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md` (update cognition module description)

**Interfaces:**
- Consumes: All prior tasks

- [ ] **Step 1: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile and tests pass

- [ ] **Step 2: Update CLAUDE.md cognition section**

Add `DriveGoalBridgeParticipant` to the cognition module description in CLAUDE.md. Add it after the gut feeling description:

Add to the cognition section: `DriveGoalBridgeParticipant (TERMINAL-phase participant — bridges registered drive proposals to MindMap GOAL nodes: TermNormalizer + Jaro-Winkler dedup, enrichment on match, abandonment sync to dormant; per-agent ConcurrentHashMap state)`

Add `configureDriveGoalBridge()` to the CognitionCore description.

- [ ] **Step 3: File companion issues**

Create two GitHub issues:
1. `feat: add "general" domain to WordNetTermNormalizer with sub-dictionary loading` — references #463
2. `refactor: upgrade GoalRecognitionPhase dedup from equalsIgnoreCase to Jaro-Winkler` — references #463

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(#463): update CLAUDE.md with DriveGoalBridgeParticipant

Adds bridge participant to cognition module description.
Files companion issues for TermNormalizer general domain
and GoalRecognitionPhase dedup upgrade.

Closes #463"
```

## References

- `specs/issue-471-cognitive-workbench/2026-10-07-drive-goal-bridge-design.md` — design spec
- `cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java` — proposal orchestrator
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/goal/DriveGoalProposal.java` — proposal record
- `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java` — composition root
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionTickParticipant.java` — participant SPI
- `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/EmergentGoalPromptSection.java` — double-count fix target
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeInput.java` — node creation API
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/JaroWinkler.java` — string similarity
- `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/TermNormalizer.java` — normalization SPI
- GitHub #463 — focal issue
