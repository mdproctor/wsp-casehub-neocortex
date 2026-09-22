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
    ABANDONED,   // given up with reason
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
replaced by `Goallike` — the migration is mechanical (2 production references
each in TypeRegistry and CognitiveDerivationEngine).

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

### Goal edge vocabulary

Registered via `MindMapVocabulary` in `CognitiveLoader`:

| Edge type | Aliases | Purpose |
|-----------|---------|---------|
| `enables` | `makes-possible`, `unblocks` | Achieving A makes B possible |
| `blocks` | `prevents`, `gates` | A must be resolved before B |
| `requires` | `depends-on`, `needs` | A is a prerequisite for B |
| `contributes-to` | `supports`, `helps` | A partially advances B |
| `decomposes-into` | `breaks-down-to`, `involves` | A has sub-goal B |

### Cross-system linking

Goal MindMap nodes link to eidos identity and engine execution via `NodeRef`:

| Scheme | Purpose | Example |
|--------|---------|---------|
| `eidos-goal` | Links to AgentGoal by name | `NodeRef("eidos-goal", "explore-topic", null)` |
| `case` | Links to engine case | `NodeRef("case", caseId, null)` |

## SPIs

### CognitiveGoalDecomposer

Defined in neocortex. Blocks provides LLM-backed implementation.

```java
@FunctionalInterface
public interface CognitiveGoalDecomposer {
    List<ParsedExtraction> decompose(
        String goalDescription,
        List<MindMapNode> contextNodes,
        String tenantId);
}
```

`@DefaultBean` NoOp returns empty list. Blocks implementation uses a cognitive
prompt: "what does achieving this involve?" — produces sub-goal entities and
`decomposes-into` relationship edges.

### CognitiveGoalRecognizer

Defined in neocortex. Blocks provides LLM-backed implementation.

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

Manages progressive resolution of the cognitive goal graph:

**Prune:** Distant goals with decomposed sub-goals that haven't been accessed
→ collapse back to single node. The sub-goal nodes are removed and the parent
goal's `resolution` property drops to `low`. Detail can be re-derived when
needed.

**Expand:** Approaching goals (time proximity) or newly-overlapping goals →
invoke `CognitiveGoalDecomposer` SPI, store results as sub-goal MindMap nodes
with `decomposes-into` edges. Update parent's `resolution` to `medium` or
`high`.

**Merge:** Shared sub-goals across parent goals → merge sub-goal nodes, create
`contributes-to` edges to both parents. Detection uses embedding similarity
(SPLADE + dense vectors via existing neocortex infrastructure) for semantic
matching. Two goals like "understand customer pain points" and "assess user
frustration areas" are semantically equivalent despite lexical distance.

**Revise:** Dependency state changed (sub-goal completed elsewhere, blocker
removed, new information) → update graph. If a `blocks` edge target is
completed, the blocked goal transitions from `blocked` to `active`.

**Decay:** Goals with no activity and declining affect → reduce priority via
confidence decay. Suggest dormancy (update `status` to `dormant`) or
abandonment after extended inactivity. Uses existing `ConfidenceDecayDecorator`
mechanism.

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
- **Approaching deadline + high urgency** → increased arousal, potentially
  negative pleasure (stress)
- **Blocked goal + high urgency** → frustration (negative pleasure, high
  arousal)
- **Recently completed goal** → satisfaction (positive pleasure shift)
- **Dormant goal with declining affect** → reduced arousal

Updates PAD dimensions on goal MindMap nodes. `AffectTrajectoryDecorator`
captures these changes as domain="affect" memories, feeding the existing
`AffectTrajectoryAnalyzer` pipeline.

## Goal-Conditioned Retrieval (D10)

`GoalRelevanceModulationFactor` implements `ModulationFactor<T>`. Weights
retrieved items by graph proximity to active goal nodes in MindMap.

Proximity computation:
1. Identify active goal nodes (status=active in GOAL subgraph)
2. For each retrieved item, check if its entity node is within N edges of
   any active goal node
3. Apply distance-decaying weight: 1.0 for direct (1 edge), 0.7 for 2 edges,
   0.4 for 3 edges, 0 for 4+

Integrates with existing `RetrievalModulator` pipeline. No changes to
retrieval SPIs — pure composition.

Cold-start mitigation: newly recognized goals with few graph connections get
minimal modulation benefit. Embedding similarity may supplement graph proximity
as an optimization (not in initial implementation).

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

Blocks provides LLM implementations for neocortex SPIs:
- `CognitiveGoalDecomposer` — LLM-backed cognitive decomposition
- `CognitiveGoalRecognizer` — LLM-backed goal recognition

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
| `CognitiveGoalRecognizer` | mindmap-api | `io.casehub.neocortex.mindmap` |
| `RecognizedGoal` | mindmap-api | `io.casehub.neocortex.mindmap` |
| `GoalResolutionPhase` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence.consolidation` |
| `GoalRecognitionPhase` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence.consolidation` |
| `GoalAffectPhase` | mindmap-intelligence | `io.casehub.neocortex.mindmap.intelligence.consolidation` |
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
