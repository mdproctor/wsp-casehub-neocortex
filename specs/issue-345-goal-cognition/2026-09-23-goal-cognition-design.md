# Goal Cognition — Design Spec

**Issue:** casehubio/neocortex#345
**Epic:** casehubio/neocortex#253
**Date:** 2026-09-23
**Status:** Draft

## Problem

The casehub platform has goal infrastructure across four repos (eidos identity,
engine execution, blocks behavioral orchestration, desiredstate convergence) but
no cognitive goal processing. Agents can have goals (eidos), execute them
(engine), propose them from drives (blocks), and compile them into state graphs
(desiredstate) — but they cannot reason about goals: track dependencies, assess
affective impact, progressively decompose as execution approaches, or condition
memory retrieval on active goal context.

Neocortex adds the cognitive goal substrate that enriches the existing goal
architecture with structured goal knowledge.

## Architecture

### Three-dimensional goal model

Goals operate across three interacting dimensions:

1. **LLM goals** (prose, blocks/langchain4j) — natural language goals proposed
   by drives or LLM decomposition. An agent's motivational system generates
   goals like "explore quantum computing" or "help the customer resolve their
   billing issue." These flow through `DriveGoalFormationStrategy` →
   `GoalProposalOrchestrator` → become eidos `AgentGoal` for prompt rendering.
   LLM decomposition strategies recursively break prose into sub-steps, each
   binding to a capability, until steps map to concrete workers.

2. **Case goals** (predicates, engine) — formal conditions over case state.
   `Goal.builder().name("loan-approved").condition(".decision == \"approved\"")
   .kind(GoalKind.SUCCESS).build()`. Machine-evaluated by the engine control
   loop. Cases ARE goal pursuit — a case runs, achieves its goal conditions,
   and completes. Expression evaluation is pluggable (JQ, MVEL, Java lambdas).
   A goal is a predicate over state, not a checklist of tasks that ran (ADR-0001).

3. **Cognitive goals** (neocortex, NEW) — goals as MindMap knowledge graph
   nodes with affect, dependencies, confidence, temporal horizon, and lifecycle
   state. The cognitive layer manages and enriches goals from both other
   dimensions — when a drive proposes a goal, the cognitive layer tracks it;
   when a case completes, the cognitive layer updates goal status and models
   affective response. Cognitive goals also exist standalone — not every goal
   originates from a drive or triggers a case.

### Substrate vs orchestration split

**Neocortex = cognitive substrate** (the WHAT) — memory, knowledge graph,
affect, curiosity, consolidation, goal cognition. Provides hooks, lifecycle
SPIs, and events. Testable in isolation.

**Blocks = cognitive agent orchestration** (the HOW) — drives, goal proposal,
narrative, social cognition, prompt rendering, termination. Wires the cognitive
substrate into agent behavior via the avatar DSL (`CognitionDefinition` with
drive, mood, personality, narrative, goalProposal, goalEscalation, etc.).
Integration testing of the full cognitive agent lives at the blocks level.

### SPI inversion for LLM access

Neocortex defines SPIs for cognitive operations requiring LLM. Blocks provides
implementations via `@Alternative @Priority`. `@DefaultBean` NoOp in neocortex
ensures standalone operation (e.g. Hortora). Existing pattern:
`ReflectionSynthesizer`, `GraduationScorer`/`GraduationClassifier`.

### No split-brain

Eidos `AgentRegistry` is the single authoritative store for "what goals does
this agent have." Engine routing (GoalFormationService, GoalRevisionEvaluator,
GoalAbandonmentEvaluator) writes lifecycle state via `AgentRegistry.register()`.
Neocortex reads lifecycle state via eidos-api — it does not write lifecycle
transitions. Neocortex provides cognitive context (dependencies, affect,
recognition signals) that feeds INTO `GoalFormationContext` and
`GoalRevisionContext`.

## Dependency Changes

Neocortex gains eidos-api as a compile dependency on modules that need it:
`cognitive-index`, `mindmap-intelligence`, and the new goal module. The cognitive
layer naturally needs to know the identity it's cognitive of.

`DescriptorView` remains for modules that don't need goal-specific context
(agent name, disposition for cognitive derivation). Modules requiring
`AgentGoal` access use eidos-api directly.

No new shared modules. Eidos-api gets identity-level goal enrichment (lifecycle
state, horizon). Neocortex uses MindMap conventions (edge vocabulary, properties)
for cognitive goal types.

## Eidos AgentGoal Enrichment

Two new fields on `AgentGoal`:

### GoalLifecycleState

```java
public enum GoalLifecycleState {
    ACTIVE,      // being pursued
    BLOCKED,     // prerequisites not met
    DEFERRED,    // consciously postponed
    COMPLETED,   // achieved
    ABANDONED,   // given up — reason stored as abandonment-reason property on MindMap node
    DORMANT      // not being pursued, can reactivate
}
```

Nullable on `AgentGoal` — null means lifecycle is not tracked (backward
compatible). Engine routing evaluators set lifecycle state via
`AgentRegistry.register()`.

### GoalHorizon

```java
public enum GoalHorizon {
    IMMEDIATE,    // this conversation
    SHORT_TERM,   // this session/day
    MEDIUM_TERM,  // this week/project
    LONG_TERM,    // ongoing commitment
    ASPIRATIONAL  // may never be achieved, shapes direction
}
```

Nullable on `AgentGoal`. Set at goal formation time. Blocks' social-config YAML
gains optional `horizon` field per goal entry.

## Lifecycle State Synchronization

Two categories of cognitive goals with different authority models:

**Linked goals** (have `eidos-goal-name` property): Eidos `AgentRegistry` is
authoritative. GoalResolutionPhase's Sync step queries `GoalLifecycleProvider`
SPI (see §SPIs) for current lifecycle state and updates the MindMap node's
`status` property to match. One-way flow: eidos → MindMap. Neocortex never
writes lifecycle transitions for linked goals — it provides cognitive context
(dependencies, affect, priority) that feeds into `GoalFormationContext` and
`GoalRevisionContext`.

**Standalone cognitive goals** (no eidos counterpart): MindMap is the sole
store. GoalResolutionPhase manages lifecycle transitions directly:
- `active` → `blocked`: when a `blocks` or `requires` dependency becomes
  active or unresolved
- `blocked` → `active`: when all blocking dependencies are resolved
- `active` → `dormant`: via GoalPrioritizationPhase Decay (extended inactivity)
- `active` → `abandoned`: via GoalPrioritizationPhase Decay (with
  `abandonment-reason` property)
- `active` → `completed`: when engine case outcome confirms goal achievement

**Linked goals and Decay:** GoalPrioritizationPhase's Decay step applies
lifecycle transitions (`status` property writes) only to standalone goals.
For linked goals, Decay records a `decay-signal` property (`dormant` or
`abandon`) on the MindMap node instead of writing `status` directly. Blocks
reads `decay-signal` during the next `GoalRevisionStrategy` evaluation and
proposes the transition through eidos — which writes the authoritative state
change via `AgentRegistry.register()`. The `decay-signal` property is cleared
by the Sync step when eidos state is imported.

This does not violate no-split-brain: linked goals have one authority (eidos);
standalone goals have one authority (MindMap). No goal has two authorities.
Decay respects the authority boundary — it signals, not writes, for linked
goals.

### Goal Supersession

Goals can be superseded — replaced by a better goal with rationale. Uses
existing `MindMapStore.supersede(targetId, supersedingId, reason, tenantId)`.

Supersession differs from abandonment: a superseded goal was replaced by a
better formulation, not given up. The supersession record (via
`SupersessionStatus`) preserves the replacement chain — useful for cognitive
reflection ("why did I reformulate this goal?").

GoalResolutionPhase triggers supersession during Merge when two goals are
semantically equivalent but one is better formulated. The weaker goal is
superseded by the stronger one. Blocks can also trigger supersession
explicitly via `MindMapStore.supersede()` when drive re-evaluation produces
a refined goal.

## MindMap Goal Representation

### Goallike trait interface

Replaces `Intentionlike` (D8). Registered as cognitive type `"goal"` in
`TypeRegistry`.

```java
public interface Goallike {
    Optional<String> description();
    Optional<String> status();       // lifecycle state as string
    Optional<String> horizon();      // temporal horizon
    Optional<String> origin();       // drive/conversation/reflection/experience/explicit
    Optional<String> resolution();   // low/medium/high — current decomposition depth
    Optional<String> urgency();
    Optional<String> feasibility();
}
```

Registered types: `"intention"` and `"desire"` become subtypes of `"goal"` in
TypeRegistry, so LLM extraction producing these types maps to the unified goal
type. Both `Intentionlike` and `Desirelike` Java interfaces are deprecated and
replaced by `Goallike` — the migration is mechanical (1 production reference
each in `TypeRegistry.COGNITIVE_TYPES`).

### Intentionlike/Desirelike → Goallike mapping

| Old interface | Old method | Goallike equivalent |
|---------------|-----------|---------------------|
| `Intentionlike.goal()` | Goal description | `Goallike.description()` |
| `Intentionlike.status()` | Status string | `Goallike.status()` |
| `Intentionlike.priority()` | Priority string | Dropped — replaced by computed `priority` property |
| `Desirelike.aspiration()` | Aspiration text | `Goallike.description()` |
| `Desirelike.status()` | Status string | `Goallike.status()` |
| `Desirelike.urgency()` | Urgency string | `Goallike.urgency()` |

### GOAL subgraph type (D9)

New `SubgraphTypes.GOAL = "goal"` constant. Goal nodes stored in dedicated
GOAL subgraphs per tenant. Enables independent scheduling in
`CuriositySignalGenerator` and `ConsolidationScheduler`.

### Goal properties (MindMap conventions)

| Property | Values | Purpose |
|----------|--------|---------|
| `status` | active/blocked/deferred/completed/abandoned/dormant | Lifecycle state |
| `horizon` | immediate/short/medium/long/aspirational | Temporal horizon |
| `origin` | drive/conversation/reflection/experience/explicit | Where the goal came from |
| `resolution` | low/medium/high | Current decomposition depth |
| `urgency` | 0.0-1.0 | Deadline pressure |
| `feasibility` | 0.0-1.0 | How close to actionable |
| `eidos-goal-name` | string | Links to eidos AgentGoal name |
| `target-date` | ISO-8601 date | Optional deadline — when present, urgency is dynamically computed |
| `priority` | 0.0-1.0 | Computed composite priority (see §Goal Priority Computation) |
| `abandonment-reason` | string | Why the goal was abandoned — required when status=abandoned |
| `decay-signal` | dormant/abandon | Decay recommendation for linked goals — cleared by Sync step |

### Goal edge vocabulary

Registered globally in `CognitiveLoader.init()` alongside cognitive type
registration — not through per-agent `CognitiveDefaults` profiles. Goal edge
vocabulary is domain infrastructure shared across all agents. A static
`GOAL_VOCABULARY` constant in `GoalVocabulary` (mindmap-api,
`io.casehub.neocortex.mindmap`) provides the `MindMapVocabulary` instance;
`CognitiveLoader.init()` calls
`store.registerVocabulary(GoalVocabulary.GOAL_VOCABULARY)` after the existing
type registration block:

| Edge type | Aliases | Purpose |
|-----------|---------|---------|
| `enables` | `makes-possible`, `unblocks` | Achieving A makes B possible |
| `blocks` | `prevents`, `gates` | A must be resolved before B |
| `requires` | `depends-on`, `needs` | A is a prerequisite for B |
| `contributes-to` | `supports`, `helps` | A partially advances B |
| `decomposes-into` | `breaks-down-to`, `involves` | A has sub-goal B |

### Cycle detection

`blocks` and `requires` edges form a DAG constraint — circular dependencies
are incoherent ("A blocks B and B blocks A" means neither can activate).
Validation on edge creation: when adding a `blocks`, `requires`, or
`decomposes-into` edge, check for cycles via BFS/DFS from target to source
along edges of the same type. Reject with `CyclicDependencyException` if a
path exists.

`enables` and `contributes-to` edges are NOT subject to cycle validation —
mutual enablement ("A enables B and B enables A") is semantically valid
(synergistic goals).

GoalResolutionPhase also runs periodic cycle detection during the Revise step
as a safety net — edges created by LLM decomposition may introduce cycles
that were valid individually but form transitive chains. Detected cycles are
resolved by removing the most recently added edge and logging a warning.

### Cross-system linking

Goal MindMap nodes link to eidos identity and engine execution via `NodeRef`:

| Scheme | Purpose | Example |
|--------|---------|---------|
| `eidos-goal` | Links to AgentGoal by name | `NodeRef("eidos-goal", "explore-topic", null)` |
| `case` | Links to engine case | `NodeRef("case", caseId, null)` |

## SPIs

### CognitiveGoalDecomposer

Defined in mindmap-api (alongside its return types). Blocks provides
LLM-backed implementation.

```java
@FunctionalInterface
public interface CognitiveGoalDecomposer {
    GoalDecompositionResult decompose(
        String goalDescription,
        List<MindMapNode> contextNodes,
        String tenantId);
}

public record GoalDecompositionResult(
    List<SubGoal> subGoals,
    List<GoalRelationship> relationships
) {
    public static final GoalDecompositionResult EMPTY =
        new GoalDecompositionResult(List.of(), List.of());

    public record SubGoal(
        String description,
        String suggestedHorizon,
        Map<String, String> properties) {}

    public record GoalRelationship(
        String sourceDescription,
        String targetDescription,
        String edgeType) {}
}
```

`@DefaultBean` NoOp returns `GoalDecompositionResult.EMPTY`. Blocks
implementation uses a cognitive prompt: "what does achieving this involve?" —
produces sub-goal entities and `decomposes-into` relationship edges.
GoalResolutionPhase converts `GoalDecompositionResult` into MindMap nodes and
edges.

**Standalone limitation:** NoOp means GoalResolutionPhase.expand() is a no-op
in standalone mode (no blocks, no LLM). Standalone deployments (e.g., Hortora)
get goal storage, recognition, and affect — but not progressive resolution.
The cognitive goal graph is still valuable without decomposition: manually
created goals, recognized goals, and their dependency edges still function.
Progressive resolution is a cognitive enhancement, not a prerequisite.

### GoalLifecycleProvider

Defined in mindmap-api. Blocks provides implementation backed by
`AgentRegistry`.

```java
@FunctionalInterface
public interface GoalLifecycleProvider {
    Map<String, String> getLifecycleStates(
        String agentId, String tenantId);
}
```

Returns goal name → status string (`"active"`, `"blocked"`, `"deferred"`,
`"completed"`, `"abandoned"`, `"dormant"`). Status strings match the MindMap
`status` property vocabulary — no eidos types cross this boundary.

`@DefaultBean` NoOp returns empty map — standalone deployments have no
linked goals, so the Sync step becomes a no-op. Blocks implementation
queries `AgentRegistry.resolve(agentId, tenantId).goals()` and maps each
`AgentGoal.lifecycleState().name().toLowerCase()` to the status string.

GoalResolutionPhase's Sync step injects this SPI and calls it to read
eidos lifecycle state for linked goals. The Sync step data flow in
multi-agent tenants:
1. Find linked goal nodes in the GOAL subgraph (those with `eidos-goal-name`
   property)
2. Group by `node.principalId()` — the `PrincipalId.id()` is the agent
   identity bridge
3. Call `GoalLifecycleProvider.getLifecycleStates(principalId.id(), tenantId)`
   per agent
4. Match returned states to goal nodes by `eidos-goal-name` property value
5. Update MindMap `status` property to match

This follows the same inversion pattern as `CognitiveGoalDecomposer` and
`CognitiveGoalRecognizer` — neocortex defines what it needs; blocks provides
the runtime implementation. The `Map<String, String>` return type preserves
mindmap-api's eidos-free boundary (mindmap-api is Tier 1 pure Java with zero
eidos dependencies).

### CognitiveGoalRecognizer

Defined in mindmap-api. Blocks provides LLM-backed implementation.

```java
@FunctionalInterface
public interface CognitiveGoalRecognizer {
    List<RecognizedGoal> recognize(
        String conversationText,
        List<MindMapNode> existingGoals,
        String tenantId);
}

public record RecognizedGoal(
    String description,
    String origin,
    String suggestedHorizon,
    double confidence) {}
```

`@DefaultBean` NoOp returns empty list. Blocks implementation uses LLM to
detect goal-like content ("I want to...", "we should...", "it would be great
if...") and classify on the intention spectrum.

## Consolidation Phases

### GoalResolutionPhase (priority 35)

Runs after ExperienceConsolidationPhase (15), MergeDetectionPhase (20),
SchemaDiscoveryPhase (25). Before CuriosityRefreshPhase (40).

**SubgraphPriority interaction:** Goal phases always process the GOAL subgraph
regardless of whether it appears in the `subgraphPriority` list. The priority
list (computed from curiosity signals) determines processing order and resource
allocation for general consolidation phases — goal-specific phases are scoped
to the GOAL subgraph by design. If no curiosity signal targets the GOAL
subgraph, goal phases still run — goal processing is not optional.

Manages progressive resolution of the cognitive goal graph. Steps execute
in the order listed — this order is load-bearing:

**Prune:** Distant goals with decomposed sub-goals that haven't been accessed
→ collapse back to single node. The sub-goal nodes are removed and the parent
goal's `resolution` property drops to `low`. Detail can be re-derived when
needed.

**Expand:** Approaching goals (high urgency or near `target-date`) or
newly-overlapping goals → invoke `CognitiveGoalDecomposer` SPI, store results
as sub-goal MindMap nodes with `decomposes-into` edges (subject to cycle
validation — see §Cycle detection). Update parent's `resolution` to `medium`
or `high`.

**Merge:** Shared sub-goals across parent goals → merge sub-goal nodes, create
`contributes-to` edges to both parents. Detection uses the same embedding
infrastructure as `MergeDetectionPhase` — `Instance<Object> embeddingModel`
injected at construction. When an embedding model is available (blocks
deployment), semantic similarity enables matching goals like "understand
customer pain points" and "assess user frustration areas." When no embedding
model is available (standalone), falls back to Jaro-Winkler name similarity +
Jaccard neighbor overlap (same as MergeDetectionPhase).

**Revise:** Dependency state changed (sub-goal completed elsewhere, blocker
removed, new information) → update graph. If a `blocks` edge target is
completed, the blocked goal transitions from `blocked` to `active`. Periodic
cycle detection runs as a safety net — edges created by LLM decomposition may
form transitive cycles.

**Sync:** For goals linked via `eidos-goal-name`, query `GoalLifecycleProvider`
SPI for current lifecycle state and update MindMap node `status` property to
match. Groups linked goals by `principalId` for multi-agent tenants — see
§SPIs GoalLifecycleProvider for the full data flow. Clears `decay-signal`
properties after importing eidos state. One-way flow: eidos → MindMap.
See §Lifecycle State Synchronization.

Step ordering rationale: Expand before Merge (new sub-goals from expansion are
candidates for cross-parent merging). Revise before Sync (update internal
dependency state before importing external lifecycle). Sync last (imports
authoritative state that subsequent phases — GoalAffectPhase,
GoalPrioritizationPhase — use for their computations).

### GoalPrioritizationPhase (priority 38)

Runs after GoalAffectPhase (37), ensuring priority computation uses
current-tick affect values. Steps execute in the order listed.

**Prioritize:** Compute composite `priority` property on each active goal
node. See §Goal Priority Computation.

**Decay:** Goals with no activity and declining affect → reduce priority via
confidence decay. Uses existing `ConfidenceDecayDecorator` mechanism.

For **standalone goals**: directly update `status` to `dormant` or `abandoned`
(with `abandonment-reason` property). See §Lifecycle State Synchronization.

For **linked goals**: record `decay-signal` property (`dormant` or `abandon`)
on the MindMap node. Do NOT write `status` directly — eidos is authoritative.
Blocks reads the signal during `GoalRevisionStrategy` evaluation.

### Goal Priority Computation

Computed during GoalPrioritizationPhase's Prioritize step. Stored as the
`priority` property (0.0–1.0) on each active goal node.

**Composite formula:**

```
priority = w_u * urgency
         + w_f * feasibility
         + w_a * affective_valence
         + w_i * importance
```

Where:
- `urgency` (0.0–1.0): from goal property. When `target-date` is present,
  dynamically computed as `1.0 - (remaining_time / horizon_budget)` clamped
  to [0, 1]. When absent, uses the static `urgency` property value.
- `feasibility` (0.0–1.0): from goal property. Updated by Revise step when
  blockers are resolved.
- `affective_valence` (0.0–1.0): derived from PAD dimensions on the goal
  node. Formula: `(pleasure + dominance + 2) / 4`. Arousal is excluded —
  it drives affect trajectory (energy, stress) but not goal desirability.
  Pleasure captures "how positively does the agent feel about this goal."
  Dominance captures "how much agency does the agent have over it." When
  PAD dimensions are unset (defaulting to 0.0 — neutral), the formula
  yields 0.5 (neutral valence). Computed by GoalAffectPhase.
- `importance` (0.0–1.0): number of `contributes-to` and `enables` inbound
  edges normalized by max across active goals. Goals that enable or
  contribute to many other goals are structurally important.

Default weights: `w_u=0.3, w_f=0.2, w_a=0.2, w_i=0.3`. Configurable per
deployment. The priority score is a substrate signal — blocks decides what
to do with it (goal selection, prompt ordering, capacity allocation).

### GoalRecognitionPhase (priority 45)

Runs after CuriosityRefreshPhase (40). Scans recent experience memories for
goal-like content that hasn't already been tracked.

1. Query `CaseMemoryStore` for recent experience memories (since last
   consolidation tick)
2. Filter to memories not already linked to goal nodes (no `NodeRef` to
   existing goal)
3. Invoke `CognitiveGoalRecognizer` SPI with the text
4. For each recognized goal above confidence threshold:
   - Check if a similar goal already exists (embedding similarity to existing
     GOAL subgraph nodes)
   - If new: create MindMap node in GOAL subgraph with properties
   - If duplicate: increment confidence on existing node

### GoalAffectPhase (priority 37)

Runs between GoalResolutionPhase (35) and CuriosityRefreshPhase (40).

Computes anticipated affect for active goals:
- **High urgency** → increased arousal. When `target-date` is present,
  urgency is dynamically recomputed from temporal distance (see §Goal
  Priority Computation). When absent, the static `urgency` property
  drives the affect computation directly.
- **Blocked goal + high urgency** → frustration (negative pleasure, high
  arousal)
- **Recently completed goal** → satisfaction (positive pleasure shift)
- **Dormant goal with declining affect** → reduced arousal

Updates PAD dimensions on goal MindMap nodes. `AffectTrajectoryDecorator`
captures these changes as domain="affect" memories, feeding the existing
`AffectTrajectoryAnalyzer` pipeline.

**Deferred: avoidance pattern.** Issue #345 §4 requires modeling dread —
goals with high importance but high difficulty developing avoidance patterns
that affect retrieval and curiosity. This requires the basic affect
infrastructure to be in place first. Tracked as a follow-up issue on
neocortex (see §Explicitly Deferred Items).

## Goal-Conditioned Retrieval (D10)

`GoalRelevanceModulationFactor` implements `ModulationFactor<Memory>` (typed
to `Memory`, matching the existing `ModulationFactors.domainWeight()` pattern).
Weights retrieved memories by graph proximity to active goal nodes in MindMap.

**MindMapStore access:** Injected at construction time, not through the
`ModulationFactor.apply(item, profile)` contract. The factor is constructed
with a `MindMapStore` reference and a `String tenantId`. Active goal nodes
are cached and refreshed via `@Observes ConsolidationCompleted` — the CDI
event fired by `ConsolidationScheduler` after each consolidation tick.
This ties cache refresh to the actual consolidation cycle rather than an
independent TTL.

**Entity mapping:** Each `Memory` has a `Subject` with `type()` and `id()`.
The factor maps `memory.subject().id()` to a MindMap entity node via
`MindMapStore.search(MindMapQuery)`, scoped by `memory.subject().type()`
to match the appropriate subgraph. If the memory's subject has a MindMap
node, graph proximity to active goals is computed.

Proximity computation:
1. Identify active goal nodes (status=active in GOAL subgraph) — cached at
   construction, refreshed per consolidation cycle
2. For each retrieved memory, resolve its entity node in MindMap
3. If entity node exists, compute shortest path to any active goal node via
   BFS on MindMap edges (bounded to depth 4)
4. Apply distance-decaying weight: 1.0 for direct (1 edge), 0.7 for 2 edges,
   0.4 for 3 edges, 0 for 4+
5. If no entity node exists, return 1.0 (neutral — no modulation)

Integrates with existing `RetrievalModulator` pipeline. No changes to
retrieval SPIs — pure composition.

Cold-start mitigation: newly recognized goals with few graph connections get
minimal modulation benefit. Embedding similarity may supplement graph proximity
as an optimization (not in initial implementation).

## Explicitly Deferred Items

The following requirements from epic #345 are explicitly out of scope for the
initial implementation. Each will be tracked as a follow-up issue on neocortex.

| Item | Epic reference | Rationale for deferral |
|------|---------------|----------------------|
| Opportunity cost awareness | §3 | Blocks-level orchestration concern — "pursuing A means NOT pursuing B" requires selection logic that belongs in blocks' `GoalProposalOrchestrator`. The substrate provides the signals (competing goals, their priorities, resource estimates via decomposition depth). Blocks surfaces the trade-off. |
| Dread/avoidance pattern | §4 | Requires basic goal affect infrastructure to be in place first. Avoidance is a second-order affect pattern — an agent that dreads a high-importance goal avoids engaging with related topics, which should affect retrieval modulation and curiosity signals. Build on GoalAffectPhase + GoalRelevanceModulationFactor. |
| Emergent goal discovery | §2 | "Achieving A reveals that B is now possible." GoalResolutionPhase's Revise step handles structural changes (dependency resolution, blocker removal) but not emergent recognition of newly possible goals. This requires integration with GoalRecognitionPhase — when Revise resolves a dependency, recognition should scan for newly possible goals in the updated context. Build on both phases. |

## Integration Points

### Neocortex → Engine (goal submission)

When cognitive processing identifies a goal ready for execution, the path is:

```
GoalResolutionPhase detects execution-ready goal
  → blocks' orchestrator reads cognitive goal state (via MindMap query)
  → blocks calls GoalFormationService.propose(agentId, tenancyId, proposal)
  → engine writes AgentGoal to AgentRegistry
  → engine's DefaultGoalDecomposer picks it up for execution
```

Neocortex does not call GoalFormationService directly — blocks orchestrates
the submission, enriching with behavioral context (drive alignment, narrative
fit, capacity check).

### Engine → Neocortex (outcome feedback)

Case outcomes flow via the existing ExperienceEvent pipeline:

```
Case completes (goal reached/failed)
  → ExperienceRecorderCore records ExperienceEvent
  → ExperienceConsolidationPhase graduates to goal-related knowledge
  → GoalResolutionPhase updates dependency graph
  → GoalAffectPhase updates anticipated affect
```

### Blocks ↔ Neocortex (cognitive enrichment)

Blocks reads neocortex goal state via existing query APIs:
- `MindMapStore.search(MindMapQuery)` — find goal nodes by properties
- `CognitiveProfile.resolve(query)` — get goal node with edges, memories,
  trajectory
- `MindMapStore.neighbors(nodeId, edgeType, tenantId)` — traverse dependency
  graph

Blocks provides implementations for neocortex SPIs:
- `CognitiveGoalDecomposer` — LLM-backed cognitive decomposition
- `CognitiveGoalRecognizer` — LLM-backed goal recognition
- `GoalLifecycleProvider` — AgentRegistry-backed lifecycle state query

## What This Does NOT Change

- `AgentRegistry` remains the authoritative goal store
- Engine routing evaluators (formation, revision, abandonment) unchanged
- Blocks' `GoalProposalOrchestrator` and drive→goal pipeline unchanged
- Blocks' avatar DSL (`CognitionDefinition`) unchanged (optionally gains
  neocortex cognitive signal consumption over time)
- Desiredstate's `GoalCompiler<G>` and `DesiredStateGraph` unchanged
- Case model `Goal` (ExpressionEvaluator conditions) unchanged
- `GoalSignalStore` remains volatile (D2) — goal signal counts reset on JVM
  restart. Acceptable for pre-release; eidos persistence review tracked
  separately

## Module Structure

New types go in existing modules — no new modules created:

| Type | Module | Package |
|------|--------|---------|
| `Goallike` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence` |
| `GoallikeTraitRule` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence` |
| `CognitiveGoalDecomposer` | mindmap-api | `io.casehub.neocortex.mindmap` |
| `GoalDecompositionResult` | mindmap-api | `io.casehub.neocortex.mindmap` |
| `GoalVocabulary` | mindmap-api | `io.casehub.neocortex.mindmap` |
| `GoalLifecycleProvider` | mindmap-api | `io.casehub.neocortex.mindmap` |
| `CognitiveGoalRecognizer` | mindmap-api | `io.casehub.neocortex.mindmap` |
| `RecognizedGoal` | mindmap-api | `io.casehub.neocortex.mindmap` |
| `GoalResolutionPhase` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence.consolidation` |
| `GoalRecognitionPhase` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence.consolidation` |
| `GoalAffectPhase` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence.consolidation` |
| `GoalPrioritizationPhase` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence.consolidation` |
| `GoalRelevanceModulationFactor` | cognitive-index | `io.casehub.neocortex.cognitive.index` |
| `GoalLifecycleState` | eidos-api | `io.casehub.eidos.api` |
| `GoalHorizon` | eidos-api | `io.casehub.eidos.api` |

## Test Coverage

- Goallike trait interface: property access via `Thing.as(Goallike.class)`
- GoallikeTraitRule: auto-classification from properties
- TypeRegistry: `"goal"` type registration, `"intention"`/`"desire"` as subtypes
- GoalResolutionPhase: prune (collapse distant), expand (decompose approaching),
  merge (shared sub-goals), revise (dependency updates), decay (inactivity)
- GoalRecognitionPhase: recognition from experience text, dedup against existing
  goals
- GoalAffectPhase: PAD updates for approaching/blocked/completed/dormant goals
- GoalRelevanceModulationFactor: graph proximity weighting, distance decay,
  cold-start behavior
- MindMapVocabulary: goal edge type registration with aliases
- GOAL subgraph: independent from COGNITIVE subgraph
- NodeRef linking: eidos-goal scheme, case scheme
- Integration with existing consolidation schedule (priority ordering)
- CognitiveGoalDecomposer NoOp: returns empty list (standalone mode)
- CognitiveGoalRecognizer NoOp: returns empty list (standalone mode)
- Eidos AgentGoal: lifecycle state and horizon fields (backward compatible —
  nullable, existing tests pass without values)
- Cycle detection: reject cycles in blocks/requires/decomposes-into edges,
  allow cycles in enables/contributes-to edges
- Cycle detection periodic: GoalResolutionPhase Revise detects and resolves
  transitive cycles introduced by LLM decomposition
- Goal priority computation: composite formula with four signals, default
  weights, edge cases (missing affect → neutral 0.5, no inbound edges →
  importance 0.0)
- GoalPrioritizationPhase: runs after GoalAffectPhase, uses current-tick
  affect values
- Dynamic urgency: target-date present → urgency computed from temporal
  distance; target-date absent → static urgency property used
- Lifecycle state synchronization: linked goals sync from GoalLifecycleProvider,
  standalone goals managed by GoalResolutionPhase
- Goal supersession: MindMapStore.supersede() called during Merge, supersession
  chain preserved
- abandonment-reason: required property when status=abandoned, validated on
  transition
- GoalDecompositionResult: construction, SubGoal/GoalRelationship inner records,
  EMPTY constant, conversion to MindMap nodes and edges
- SubgraphPriority independence: goal phases run regardless of whether GOAL
  appears in the curiosity-generated priority list
- GoalLifecycleProvider: NoOp returns empty map, blocks implementation returns
  lifecycle states from AgentRegistry
- Desirelike/Intentionlike → Goallike mapping: all methods mapped correctly
  including Desirelike.status()
- Decay linked vs standalone: standalone goals get direct status writes,
  linked goals get decay-signal property (not status). Verify decay-signal
  cleared by Sync.
- affective_valence formula: (pleasure + dominance + 2) / 4, arousal excluded,
  neutral PAD → 0.5
- GoalLifecycleProvider returns Map<String, String> (no eidos types cross
  mindmap-api boundary)
- Sync step agentId sourcing: linked goals grouped by principalId, provider
  called per agent, results matched by eidos-goal-name
- GoalRelevanceModulationFactor cache: refreshed on @Observes
  ConsolidationCompleted, not TTL

## References

- `decisions.md` — D1-D10 validated architectural decisions
- `2026-09-22-goal-architecture-context.md` — cross-repo audit, dependency
  graph, agreed direction
- `engine/docs/blog/2026-04-09-mdp03-pojo-graph-and-goals.md` — goals vs
  tasks research, BDI framing, ADR-0001
- `engine/docs/specs/issue-100-goals-aims-constraints/2026-07-25-goals-constraints-design.md`
  — eidos goal identity design
- `wacky-manor/src/main/resources/META-INF/eidos/social-config.yaml` — avatar
  DSL with goals, drives, norms, relationships
- `blocks/agentic-yaml/src/main/java/.../CognitionDefinition.java` — cognitive
  agent DSL specification
- `GoalProposalOrchestrator.java` — blocks drive→goal lifecycle
- `LlmDriveGoalFormationStrategy.java` — LLM drive→goal formation
- `DefaultGoalDecomposer.java` — engine execution decomposition
- `LlmDecompositionStrategy.java` — LLM execution decomposition
- `ConsolidationScheduler.java` — consolidation sleep cycle pattern
- `MindMapExtractor.java` — ParsedExtraction pattern for LLM extraction
- `CognitiveProfile.java` — cross-store entity resolution
- `ModulationFactor.java` — retrieval modulation SPI
- Park et al. (2023) — Generative Agents
- Schulz & Jander (2025) — Planless BDI Agents
- Addison (2025) — La VIDA goal-self concordance
- Scherer (2001) — Appraisal theory (goals as emotional reference points)
- Nagashima et al. (2024) — Intrinsic motivation via pattern discovery
