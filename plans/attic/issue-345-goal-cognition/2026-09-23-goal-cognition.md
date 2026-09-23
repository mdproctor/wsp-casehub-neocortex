# Goal Cognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #345 — epic: goal cognition
**Issue group:** #345

**Goal:** Add cognitive goal substrate to neocortex — goal representation in MindMap, progressive resolution via consolidation, goal-conditioned retrieval, and SPIs for LLM-backed cognitive operations.

**Architecture:** Goals are MindMap nodes with a `Goallike` trait in a dedicated GOAL subgraph. Progressive resolution managed by GoalResolutionPhase in the consolidation sleep cycle. SPIs (CognitiveGoalDecomposer, CognitiveGoalRecognizer, GoalLifecycleProvider) defined in mindmap-api with NoOp defaults; blocks provides LLM implementations. Eidos AgentGoal enriched with GoalLifecycleState and GoalHorizon.

**Tech Stack:** Java 21 (on Java 26 JVM), Quarkus 3.32.2, neocortex MindMap infrastructure, eidos-api

## Global Constraints

- Java 21 source, Java 26 JVM. `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn`
- Use `mvn` not `./mvnw`
- All new types follow existing neocortex conventions (zero-deps API modules, CDI with `Instance<T>` graceful degradation)
- Edge vocabulary uses string constants, not enums (MindMap convention)
- SPIs use `@FunctionalInterface` with `@DefaultBean` NoOp pattern
- neocortex → eidos-api dependency added to cognitive-index and mindmap-intelligence POMs only
- All commits reference `Refs #345` or `Closes #345`
- IntelliJ MCP for all code navigation and editing. Use `ide_insert_member` for new methods, `ide_replace_member` for modifications, `ide_create_file` for new files.

---

## Batch 1: Foundation — Eidos Enrichment + SPIs + Vocabulary

After this batch: eidos has GoalLifecycleState/GoalHorizon enums on AgentGoal, mindmap-api has all SPI interfaces with NoOp defaults, GoalVocabulary defines edge types, SubgraphTypes has GOAL constant.

### Task 1: Eidos GoalLifecycleState and GoalHorizon

**Files:**
- Create: `eidos-api: io/casehub/eidos/api/GoalLifecycleState.java`
- Create: `eidos-api: io/casehub/eidos/api/GoalHorizon.java`
- Modify: `eidos-api: io/casehub/eidos/api/AgentGoal.java` — add two nullable fields
- Test: `eidos-api: io/casehub/eidos/api/AgentGoalTest.java` — verify backward compat

**Interfaces:**
- Produces: `GoalLifecycleState` enum (ACTIVE, BLOCKED, DEFERRED, COMPLETED, ABANDONED, DORMANT), `GoalHorizon` enum (IMMEDIATE, SHORT_TERM, MEDIUM_TERM, LONG_TERM, ASPIRATIONAL). `AgentGoal` record gains nullable `lifecycleState` and `horizon` fields.

- [ ] **Step 1: Write failing test for GoalLifecycleState enum**

```java
@Test void lifecycleStateValues() {
    assertThat(GoalLifecycleState.values()).hasSize(6);
    assertThat(GoalLifecycleState.valueOf("ACTIVE")).isNotNull();
    assertThat(GoalLifecycleState.valueOf("DORMANT")).isNotNull();
}
```

- [ ] **Step 2: Create GoalLifecycleState enum**

```java
public enum GoalLifecycleState {
    ACTIVE, BLOCKED, DEFERRED, COMPLETED, ABANDONED, DORMANT
}
```

- [ ] **Step 3: Write failing test for GoalHorizon enum**

```java
@Test void horizonValues() {
    assertThat(GoalHorizon.values()).hasSize(5);
    assertThat(GoalHorizon.valueOf("ASPIRATIONAL")).isNotNull();
}
```

- [ ] **Step 4: Create GoalHorizon enum**

```java
public enum GoalHorizon {
    IMMEDIATE, SHORT_TERM, MEDIUM_TERM, LONG_TERM, ASPIRATIONAL
}
```

- [ ] **Step 5: Write failing test for AgentGoal backward compatibility**

```java
@Test void existingGoalConstructionStillWorks() {
    var goal = new AgentGoal("test", "desc", GoalPriority.PRIMARY,
        Visibility.PUBLIC, List.of(), null);
    assertThat(goal.lifecycleState()).isNull();
    assertThat(goal.horizon()).isNull();
}

@Test void goalWithLifecycleAndHorizon() {
    var goal = new AgentGoal("test", "desc", GoalPriority.PRIMARY,
        Visibility.PUBLIC, List.of(), null,
        GoalLifecycleState.ACTIVE, GoalHorizon.MEDIUM_TERM);
    assertThat(goal.lifecycleState()).isEqualTo(GoalLifecycleState.ACTIVE);
    assertThat(goal.horizon()).isEqualTo(GoalHorizon.MEDIUM_TERM);
}
```

- [ ] **Step 6: Add nullable fields to AgentGoal record**

Add `@Nullable GoalLifecycleState lifecycleState` and `@Nullable GoalHorizon horizon` as the last two record components. Provide backward-compatible constructor that defaults both to null. Update Builder with `lifecycleState()` and `horizon()` methods.

- [ ] **Step 7: Run all eidos-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl eidos-api` (in eidos repo)
Expected: All existing tests pass, new tests pass.

- [ ] **Step 8: Commit**

```bash
git commit -m "feat(#345): add GoalLifecycleState and GoalHorizon to AgentGoal Refs #345"
```

### Task 2: GOAL Subgraph Type + GoalVocabulary + SPIs

**Files:**
- Modify: `mindmap-api: io/casehub/neocortex/mindmap/SubgraphTypes.java` — add GOAL constant
- Create: `mindmap-api: io/casehub/neocortex/mindmap/GoalVocabulary.java` — edge type definitions
- Create: `mindmap-api: io/casehub/neocortex/mindmap/CognitiveGoalDecomposer.java`
- Create: `mindmap-api: io/casehub/neocortex/mindmap/GoalDecompositionResult.java`
- Create: `mindmap-api: io/casehub/neocortex/mindmap/CognitiveGoalRecognizer.java`
- Create: `mindmap-api: io/casehub/neocortex/mindmap/RecognizedGoal.java`
- Create: `mindmap-api: io/casehub/neocortex/mindmap/GoalLifecycleProvider.java`
- Test: `mindmap-api: io/casehub/neocortex/mindmap/GoalVocabularyTest.java`
- Test: `mindmap-api: io/casehub/neocortex/mindmap/GoalDecompositionResultTest.java`
- Test: `mindmap-api: io/casehub/neocortex/mindmap/RecognizedGoalTest.java`

**Interfaces:**
- Produces: `SubgraphTypes.GOAL`, `GoalVocabulary.GOAL_VOCABULARY`, `CognitiveGoalDecomposer` SPI, `GoalDecompositionResult` value type, `CognitiveGoalRecognizer` SPI, `RecognizedGoal` value type, `GoalLifecycleProvider` SPI

- [ ] **Step 1: Write failing test for SubgraphTypes.GOAL**

```java
@Test void goalSubgraphTypeExists() {
    assertThat(SubgraphTypes.GOAL).isEqualTo("goal");
}
```

- [ ] **Step 2: Add GOAL constant to SubgraphTypes**

```java
public static final String GOAL = "goal";
```

- [ ] **Step 3: Write failing test for GoalVocabulary**

```java
@Test void vocabularyHasFiveEdgeTypes() {
    var vocab = GoalVocabulary.GOAL_VOCABULARY;
    assertThat(vocab.edgeTypes()).hasSize(5);
    assertThat(vocab.edgeTypes().stream().map(EdgeTypeDefinition::canonicalName))
        .containsExactlyInAnyOrder("enables", "blocks", "requires",
            "contributes-to", "decomposes-into");
}

@Test void enablesHasAliases() {
    var enables = GoalVocabulary.GOAL_VOCABULARY.edgeTypes().stream()
        .filter(e -> e.canonicalName().equals("enables")).findFirst().orElseThrow();
    assertThat(enables.aliases()).contains("makes-possible", "unblocks");
}
```

- [ ] **Step 4: Create GoalVocabulary class**

Static `GOAL_VOCABULARY` constant as a `MindMapVocabulary` with 5 `EdgeTypeDefinition` entries matching the spec's edge vocabulary table.

- [ ] **Step 5: Write tests for GoalDecompositionResult**

```java
@Test void emptyConstant() {
    assertThat(GoalDecompositionResult.EMPTY.subGoals()).isEmpty();
    assertThat(GoalDecompositionResult.EMPTY.relationships()).isEmpty();
}

@Test void constructionWithValues() {
    var result = new GoalDecompositionResult(
        List.of(new GoalDecompositionResult.SubGoal("sub", "short", Map.of())),
        List.of(new GoalDecompositionResult.GoalRelationship("parent", "sub", "decomposes-into")));
    assertThat(result.subGoals()).hasSize(1);
    assertThat(result.relationships()).hasSize(1);
}
```

- [ ] **Step 6: Create GoalDecompositionResult record**

Per spec — record with SubGoal and GoalRelationship inner records, EMPTY constant.

- [ ] **Step 7: Write test for RecognizedGoal**

```java
@Test void recognizedGoalConstruction() {
    var goal = new RecognizedGoal("explore topic", "conversation", "medium", 0.85);
    assertThat(goal.description()).isEqualTo("explore topic");
    assertThat(goal.confidence()).isEqualTo(0.85);
}
```

- [ ] **Step 8: Create RecognizedGoal record**

Per spec.

- [ ] **Step 9: Create CognitiveGoalDecomposer SPI**

```java
@FunctionalInterface
public interface CognitiveGoalDecomposer {
    GoalDecompositionResult decompose(String goalDescription,
        List<MindMapNode> contextNodes, String tenantId);
}
```

- [ ] **Step 10: Create CognitiveGoalRecognizer SPI**

Per spec.

- [ ] **Step 11: Create GoalLifecycleProvider SPI**

```java
@FunctionalInterface
public interface GoalLifecycleProvider {
    Map<String, String> getLifecycleStates(String agentId, String tenantId);
}
```

- [ ] **Step 12: Run all mindmap-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api`
Expected: All tests pass.

- [ ] **Step 13: Commit**

```bash
git commit -m "feat(#345): add GOAL subgraph type, GoalVocabulary, and cognitive goal SPIs Refs #345"
```

---

## Batch 2: Goallike Trait + TypeRegistry + NoOp Defaults

After this batch: MindMap nodes can be classified as goals via the Goallike trait. TypeRegistry registers "goal" as a cognitive type with "intention" and "desire" as subtypes. NoOp default beans registered for all SPIs. CognitiveLoader registers goal vocabulary.

### Task 3: Goallike Trait, TraitRule, and TypeRegistry

**Files:**
- Create: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/Goallike.java`
- Create: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/GoallikeTraitRule.java`
- Modify: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/TypeRegistry.java` — add "goal" type, "intention"/"desire" as subtypes
- Modify: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/Intentionlike.java` — add @Deprecated
- Modify: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/Desirelike.java` — add @Deprecated
- Modify: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/CognitiveLoader.java` — register goal vocabulary
- Create: `mindmap: io/casehub/neocortex/mindmap/runtime/NoOpCognitiveGoalDecomposer.java`
- Create: `mindmap: io/casehub/neocortex/mindmap/runtime/NoOpCognitiveGoalRecognizer.java`
- Create: `mindmap: io/casehub/neocortex/mindmap/runtime/NoOpGoalLifecycleProvider.java`
- Test: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/GoallikeTest.java`
- Test: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/GoallikeTraitRuleTest.java`

**Interfaces:**
- Consumes: `GoalVocabulary.GOAL_VOCABULARY` (Task 2), `SubgraphTypes.GOAL` (Task 2)
- Produces: `Goallike` interface, `GoallikeTraitRule`, NoOp beans for all 3 SPIs

- [ ] **Step 1: Write failing test for Goallike trait**

```java
@Test void goallikeTraitAccessesProperties() {
    var node = testNode(Map.of("description", "find diamond", "status", "active",
        "horizon", "medium", "urgency", "0.8"));
    var g = node.as(Goallike.class);
    assertThat(g.description()).contains("find diamond");
    assertThat(g.status()).contains("active");
    assertThat(g.horizon()).contains("medium");
    assertThat(g.urgency()).contains("0.8");
}
```

- [ ] **Step 2: Create Goallike interface**

Per spec — 7 Optional<String> accessor methods.

- [ ] **Step 3: Write failing test for GoallikeTraitRule**

```java
@Test void matchesNodeWithGoalProperties() {
    var node = testNode(Map.of("description", "find diamond", "status", "active"));
    assertThat(new GoallikeTraitRule().matches(node, List.of())).isTrue();
}

@Test void doesNotMatchNodeWithoutGoalProperties() {
    var node = testNode(Map.of("name", "Alice"));
    assertThat(new GoallikeTraitRule().matches(node, List.of())).isFalse();
}
```

- [ ] **Step 4: Create GoallikeTraitRule**

`@ApplicationScoped`, matches nodes with both `description` AND `status` properties present (minimum required goal properties).

- [ ] **Step 5: Update TypeRegistry — add "goal" cognitive type**

Replace the `COGNITIVE_TYPES` map entry for `"intention"` with `"goal"` → `Goallike.class`. Keep `"intention"` and `"desire"` as entries that point to `Goallike.class` (subtype mapping).

- [ ] **Step 6: Deprecate Intentionlike and Desirelike**

Add `@Deprecated(forRemoval = true)` to both interfaces.

- [ ] **Step 7: Update CognitiveLoader — register goal vocabulary**

In `CognitiveLoader.init()`, after the existing type registration block, add:
```java
store.registerVocabulary(GoalVocabulary.GOAL_VOCABULARY);
```

- [ ] **Step 8: Create NoOp default beans**

Three `@DefaultBean @ApplicationScoped` classes in mindmap module:
- `NoOpCognitiveGoalDecomposer` → returns `GoalDecompositionResult.EMPTY`
- `NoOpCognitiveGoalRecognizer` → returns `List.of()`
- `NoOpGoalLifecycleProvider` → returns `Map.of()`

- [ ] **Step 9: Run all mindmap-intelligence and mindmap tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence,mindmap`
Expected: All tests pass (including existing tests — backward compatible).

- [ ] **Step 10: Commit**

```bash
git commit -m "feat(#345): add Goallike trait, GoallikeTraitRule, TypeRegistry update, NoOp defaults Refs #345"
```

---

## Batch 3: GoalResolutionPhase

After this batch: the consolidation sleep cycle includes goal resolution — prune distant goals, expand approaching ones, merge shared sub-goals, revise dependency state, sync with eidos lifecycle.

### Task 4: GoalResolutionPhase — Core Structure + Prune/Revise/Sync

**Files:**
- Create: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/consolidation/GoalResolutionPhase.java`
- Modify: `mindmap-intelligence/pom.xml` — add eidos-api compile dependency
- Test: `mindmap-intelligence: io/casehub/neocortex/mindmap/intelligence/consolidation/GoalResolutionPhaseTest.java`

**Interfaces:**
- Consumes: `ConsolidationPhase` SPI, `MindMapStore`, `CognitiveGoalDecomposer` (NoOp), `GoalLifecycleProvider` (NoOp), `SubgraphTypes.GOAL`, `GoalVocabulary` edge types
- Produces: `GoalResolutionPhase` (priority 35) with Prune, Revise, Sync steps

- [ ] **Step 1: Add eidos-api dependency to mindmap-intelligence pom.xml**

Add `casehub-eidos-api` as compile dependency.

- [ ] **Step 2: Write failing test for phase registration**

```java
@Test void phaseNameAndPriority() {
    var phase = new GoalResolutionPhase(store, decomposer, lifecycleProvider);
    assertThat(phase.name()).isEqualTo("goal-resolution");
    assertThat(phase.priority()).isEqualTo(35);
}
```

- [ ] **Step 3: Write failing test for Prune step**

Test: create a goal node with resolution=high and sub-goal nodes linked by decomposes-into edges. Set the parent goal's horizon to "aspirational" (distant). Run the phase. Verify sub-goal nodes are removed and parent's resolution drops to "low".

- [ ] **Step 4: Write failing test for Revise step**

Test: create goal A (status=blocked) with a `blocks` edge from goal B. Set goal B status to "completed". Run the phase. Verify goal A transitions to status=active.

- [ ] **Step 5: Write failing test for Sync step**

Test: create a goal node with `eidos-goal-name=test-goal` property. Configure GoalLifecycleProvider to return `{"test-goal": "completed"}`. Run the phase. Verify node's status property updated to "completed".

- [ ] **Step 6: Write failing test for cycle detection in Revise**

Test: create goals A→B→C→A via `blocks` edges (introduced by simulated LLM decomposition). Run Revise. Verify the most recently added edge is removed and a warning is logged.

- [ ] **Step 7: Implement GoalResolutionPhase**

`@ApplicationScoped`, `@Priority(35)`, implements `ConsolidationPhase`. Constructor injects `Instance<MindMapStore>`, `Instance<CognitiveGoalDecomposer>`, `Instance<GoalLifecycleProvider>`. Graceful degradation — all `isResolvable()` guarded.

Run method executes 5 steps in order: Prune, Expand (no-op when decomposer is NoOp), Merge (deferred to Task 5), Revise, Sync.

- [ ] **Step 8: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: All tests pass.

- [ ] **Step 9: Commit**

```bash
git commit -m "feat(#345): add GoalResolutionPhase with Prune, Revise, Sync Refs #345"
```

### Task 5: GoalResolutionPhase — Expand + Merge

**Files:**
- Modify: `mindmap-intelligence: .../consolidation/GoalResolutionPhase.java` — implement Expand and Merge steps
- Modify: `mindmap-intelligence: .../consolidation/GoalResolutionPhaseTest.java` — add tests

**Interfaces:**
- Consumes: `CognitiveGoalDecomposer` (NoOp or real), `GoalDecompositionResult`, embedding model (optional via `Instance`)

- [ ] **Step 1: Write failing test for Expand step**

Test: create a goal node with urgency=0.9 (approaching) and resolution=low. Provide a non-NoOp CognitiveGoalDecomposer that returns sub-goals. Run the phase. Verify sub-goal nodes created with decomposes-into edges, parent resolution updated to "high".

- [ ] **Step 2: Write failing test for Expand with cycle rejection**

Test: provide a decomposer that returns a sub-goal that would create a cycle with an existing `requires` edge. Verify the cyclic edge is rejected and a warning logged.

- [ ] **Step 3: Write failing test for Merge step**

Test: create two parent goals, each with a sub-goal that has a similar name. Run Merge. Verify the duplicate sub-goal nodes are merged and `contributes-to` edges created to both parents.

- [ ] **Step 4: Implement Expand step**

Query GOAL subgraph for nodes with urgency > 0.7 (or near target-date) and resolution=low. For each, call `CognitiveGoalDecomposer.decompose()`. Convert `GoalDecompositionResult` to MindMap nodes and edges. Validate no cycles on `blocks`/`requires`/`decomposes-into` edges.

- [ ] **Step 5: Implement Merge step**

Find sub-goal nodes across different parents. Compare using Jaro-Winkler name similarity (≥0.85 threshold) as default. When embedding model available via `Instance`, use embedding similarity instead. Merge by calling `MindMapStore.mergeNodes()` and creating `contributes-to` edges to all parents.

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(#345): add GoalResolutionPhase Expand and Merge steps Refs #345"
```

---

## Batch 4: Supporting Phases + Retrieval Modulation

After this batch: full goal cognition pipeline operational — affect computation, priority ranking, goal recognition from experience, and goal-conditioned retrieval modulation.

### Task 6: GoalAffectPhase + GoalPrioritizationPhase

**Files:**
- Create: `mindmap-intelligence: .../consolidation/GoalAffectPhase.java`
- Create: `mindmap-intelligence: .../consolidation/GoalPrioritizationPhase.java`
- Test: `mindmap-intelligence: .../consolidation/GoalAffectPhaseTest.java`
- Test: `mindmap-intelligence: .../consolidation/GoalPrioritizationPhaseTest.java`

**Interfaces:**
- Consumes: `MindMapStore`, `SubgraphTypes.GOAL`, GoalVocabulary edge types
- Produces: `GoalAffectPhase` (priority 37), `GoalPrioritizationPhase` (priority 38)

- [ ] **Step 1: Write failing test for GoalAffectPhase — urgency increases arousal**

Test: goal with urgency=0.9 gets arousal PAD update.

- [ ] **Step 2: Write failing test for GoalAffectPhase — blocked goal frustration**

Test: blocked goal with high urgency gets negative pleasure + high arousal.

- [ ] **Step 3: Write failing test for GoalAffectPhase — completed goal satisfaction**

Test: completed goal gets positive pleasure shift.

- [ ] **Step 4: Implement GoalAffectPhase**

`@ApplicationScoped`, `@Priority(37)`. Queries GOAL subgraph, computes PAD updates based on status + urgency + feasibility. Updates PAD via `MindMapStore.updateNode()`.

- [ ] **Step 5: Write failing test for GoalPrioritizationPhase — composite priority**

Test: goal with urgency=0.8, feasibility=0.6, pleasure=0.5, dominance=0.7, 2 inbound enables edges. Verify computed priority matches the formula.

- [ ] **Step 6: Write failing test for GoalPrioritizationPhase — decay for standalone goal**

Test: standalone goal with no activity → status updated to dormant.

- [ ] **Step 7: Write failing test for GoalPrioritizationPhase — decay-signal for linked goal**

Test: linked goal with no activity → decay-signal property set, status NOT changed.

- [ ] **Step 8: Implement GoalPrioritizationPhase**

`@ApplicationScoped`, `@Priority(38)`. Two steps: Prioritize (compute composite priority per spec formula) and Decay (standalone direct, linked via decay-signal).

- [ ] **Step 9: Run tests, commit**

```bash
git commit -m "feat(#345): add GoalAffectPhase and GoalPrioritizationPhase Refs #345"
```

### Task 7: GoalRecognitionPhase

**Files:**
- Create: `mindmap-intelligence: .../consolidation/GoalRecognitionPhase.java`
- Test: `mindmap-intelligence: .../consolidation/GoalRecognitionPhaseTest.java`

**Interfaces:**
- Consumes: `CaseMemoryStore`, `CognitiveGoalRecognizer` (NoOp), `MindMapStore`
- Produces: `GoalRecognitionPhase` (priority 45)

- [ ] **Step 1: Write failing test — recognizes goal from experience memory**

Test: add experience memory "I really want to learn quantum computing". Provide recognizer that returns a RecognizedGoal. Run phase. Verify MindMap goal node created in GOAL subgraph.

- [ ] **Step 2: Write failing test — deduplicates against existing goals**

Test: existing goal "learn quantum computing" in GOAL subgraph. Recognition returns same goal. Verify no new node created, existing node confidence incremented.

- [ ] **Step 3: Write failing test — NoOp recognizer does nothing**

Test: run with NoOp recognizer. Verify no nodes created.

- [ ] **Step 4: Implement GoalRecognitionPhase**

`@ApplicationScoped`, `@Priority(45)`. Queries recent experience memories since last tick. Invokes recognizer. Creates/deduplicates goal nodes.

- [ ] **Step 5: Run tests, commit**

```bash
git commit -m "feat(#345): add GoalRecognitionPhase Refs #345"
```

### Task 8: GoalRelevanceModulationFactor

**Files:**
- Create: `cognitive-index: io/casehub/neocortex/cognitive/index/GoalRelevanceModulationFactor.java`
- Modify: `cognitive-index/pom.xml` — add eidos-api compile dependency (if not already present)
- Test: `cognitive-index: io/casehub/neocortex/cognitive/index/GoalRelevanceModulationFactorTest.java`

**Interfaces:**
- Consumes: `ModulationFactor<Memory>`, `MindMapStore`, `SubgraphTypes.GOAL`
- Produces: `GoalRelevanceModulationFactor`

- [ ] **Step 1: Write failing test — direct edge proximity**

Test: memory entity 1 edge from active goal. Verify weight = 1.0.

- [ ] **Step 2: Write failing test — 2-edge proximity**

Test: memory entity 2 edges from goal. Verify weight = 0.7.

- [ ] **Step 3: Write failing test — no entity node**

Test: memory with no MindMap entity. Verify weight = 1.0 (neutral).

- [ ] **Step 4: Write failing test — no active goals**

Test: no active goals in GOAL subgraph. Verify weight = 1.0 (neutral).

- [ ] **Step 5: Implement GoalRelevanceModulationFactor**

Implements `ModulationFactor<Memory>`. Constructor takes `MindMapStore` + `String tenantId`. Caches active goals, refreshed on `@Observes ConsolidationCompleted`. BFS proximity computation bounded to depth 4.

- [ ] **Step 6: Run tests, commit**

```bash
git commit -m "feat(#345): add GoalRelevanceModulationFactor Refs #345"
```

---

## Batch 5: Integration + Full Build Verification

After this batch: full build green, all modules compile with new eidos-api dependency, documentation updated.

### Task 9: Dependency Wiring + Full Build + CLAUDE.md Update

**Files:**
- Modify: `cognitive-index/pom.xml` — verify/add eidos-api dependency
- Modify: `CLAUDE.md` — update module descriptions for goal cognition types
- Modify: `docs/guides/contributor-guide.md` — add goal cognition section

- [ ] **Step 1: Verify eidos-api dependency in cognitive-index pom.xml**

Check if already present from Task 8. Add if missing.

- [ ] **Step 2: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: All modules compile, all tests pass.

- [ ] **Step 3: Update CLAUDE.md module descriptions**

Add goal cognition types to the relevant module descriptions (mindmap-api, mindmap-intelligence, cognitive-index).

- [ ] **Step 4: Update contributor guide**

Add section on goal cognition architecture, SPIs, and consolidation phases.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(#345): dependency wiring, full build green, docs updated Refs #345"
```

## References

- `specs/issue-345-goal-cognition/2026-09-23-goal-cognition-design.md` — design spec
- `specs/issue-345-goal-cognition/decisions.md` — D1-D10 architectural decisions
- `specs/issue-345-goal-cognition/2026-09-22-goal-architecture-context.md` — cross-repo audit
- `io.casehub.neocortex.mindmap.MindMapStore` — graph store SPI
- `io.casehub.neocortex.mindmap.intelligence.TypeRegistry` — cognitive type registration
- `io.casehub.neocortex.mindmap.intelligence.CognitiveLoader` — vocabulary registration
- `io.casehub.neocortex.mindmap.intelligence.consolidation.*Phase` — existing consolidation phases
- `io.casehub.neocortex.cognitive.index.ModulationFactor` — retrieval modulation SPI
- `io.casehub.eidos.api.AgentGoal` — identity goal record
- GitHub #345 — epic: goal cognition
- GitHub #378 — follow-up: blocks social memory migration
