# Goal Architecture Context — Platform-Wide Analysis

**Epic:** casehubio/neocortex#345
**Parent:** casehubio/neocortex#253
**Date:** 2026-09-22
**Status:** Context gathered, decisions pending
**Scope:** Cross-repo architecture — platform, eidos, engine, blocks, desiredstate, neocortex

## Problem

The word "goal" appears across six repos with four distinct meanings. Each layer
evolved independently — locally sound, but the total lacks a unifying architecture.
Epic #345 proposes adding cognitive goal processing to neocortex. Before building,
we need an architecture that works for the whole platform with the right
consolidation at the right layer.

## Current Goal Landscape

### Four goal concepts, one word

| Concept | Repo | Type | What it means | Dependencies | Lifecycle | Persistence |
|---------|------|------|---------------|-------------|-----------|-------------|
| Identity goal | eidos | `AgentGoal` | Standing objective on agent descriptor | None | Evolves (promote/demote) | JPA (`AgentGoalEntity`) |
| Case goal | engine | `Goal` | Terminal condition on case execution (`ExpressionEvaluator`) | None | Goal reached → case completes | Case state |
| Desired-state goal | desiredstate | `GoalCompiler<G>` | Domain outcome compiled to provisioning DAG | Explicit `Dependency(from, to)` | Phased (`CompletionCondition`) | `ReconciliationStateStore` (JPA) |
| Cognitive goal | neocortex (#345) | Proposed | Recognized intention with affect and dependencies | Typed edges (enables/blocks) | Full state machine | MindMap + Memory |

### Repo dependency graph (verified)

```
platform-api
  ↑
  ├── eidos-api
  │     ↑
  │     └── engine-api
  │           ↑
  │           ├── engine-runtime ←── neocortex-{memory-api, mindmap-api,
  │           │                       mindmap-intelligence, memory CDI, rag-api}
  │           │
  │           └── blocks-core ←──── neocortex-memory-api (provided)
  │                 ↑
  │                 └── blocks ←── neocortex-memory-api (provided)
  │
  ├── neocortex-*-api ←── platform-api only (ZERO eidos/engine deps)
  │
  └── desiredstate-api ←── neocortex-memory-api
```

Key structural facts:
- Neocortex is UPSTREAM of engine-runtime and blocks (they depend on neocortex APIs)
- Neocortex has ZERO dependencies on eidos or engine (uses `DescriptorView` pattern)
- A new lean `neocortex-goal-api` module would be consumable by engine, blocks, and desiredstate without circular deps
- Work repo is fully independent (no goal infrastructure)

### What each repo owns today

#### eidos (identity primitives + default evaluation)

**Data types:** `AgentGoal` (name, description, priority PRIMARY/SECONDARY, visibility, capabilities, attributes), `GoalPriority`, `GoalOutcome` (SUCCESS/FAILURE), `GoalOutcomeCounts` (success/failure counts + `successRate()`), `GoalContext` (description, subGoals, caseRef), `GoalEvolutionResult` (sealed: Unchanged/Evolved/Dampened)

**SPIs:** `GoalSignalStore` (record outcomes, query counts, decay, clear), `GoalEvolution` (evaluate descriptor + counts → result)

**Implementations:**
- `DefaultGoalEvolution` (runtime) — promotion/demotion: SECONDARY goals with >80% success rate promote to PRIMARY; PRIMARY with >70% failure demote. Configurable via `GoalPreferenceKeys`. Ensures at least one PRIMARY survives.
- `InMemoryGoalSignalStore` — volatile `ConcurrentHashMap`, lost on restart
- `NoOpGoalSignalStore`, `NoOpGoalEvolution` — fallback stubs

**Persistence gap:** `GoalSignalStore` has NO durable implementation. Goal outcome data is lost on JVM restart. This means engine's revision/abandonment evaluators can never accumulate enough history across restarts to trigger evolution.

**Design spec:** `engine/docs/specs/issue-100-goals-aims-constraints/2026-07-25-goals-constraints-design.md` — "BDI as orientation vocabulary, not execution architecture." Goals structure the system prompt; the LLM does reasoning. Goals are identity + rendering. Deferred: goal-based routing, termination, cross-agent awareness (eidos#101).

#### engine (execution + routing)

**Case-level goals:**
- `Goal` — name, `ExpressionEvaluator` condition (pluggable: JQ, Lambda), kind (success/failure/custom), description
- `GoalBasedCompletion` — case completion strategy from goal expressions (`allOf`, `anyOf`, `goal(name)`)
- `GoalReachedEvent` — fired when case goal condition becomes true
- `GoalDecomposer` SPI → `GoalStep` — decompose goals into plan steps (description + capabilityName)
- `GoalDecompositionContext` — state, depth, available capabilities, planning constraints, experiences

**Agent goal routing (SPIs in engine-api, implementations in runtime-core):**
- `GoalFormationService` — `propose(agentId, tenancyId, proposal) → GoalFormationResult`
- `GoalFormationStrategy` — LLM-backed: `propose(GoalFormationContext) → GoalFormationProposal`
- `GoalFormationContext` — agentId, tenancyId, reflectionInsights, existingGoals (`List<AgentGoal>`), recentMemories (`List<RetrievedMemory>`), remainingCapacity
- `GoalRevisionStrategy` — LLM-backed: `revise(GoalRevisionContext) → GoalRevisionProposal`
- `GoalRevisionContext` — agentId, tenancyId, goals (`List<AgentGoal>`), counts (`Map<String, GoalOutcomeCounts>`)
- `GoalRemovalService` — `removeGoals(agentId, tenancyId, goalNames, reason)`

**Routing evaluators (engine runtime-core):**
- `GoalOutcomeRecorder` — maps `WorkerOutcome` to `GoalOutcome`, records against matching `AgentGoal` capabilities via `GoalSignalStore`
- `GoalRevisionEvaluator` — reads outcome counts, calls `GoalEvolution` + `GoalRevisionStrategy` (LLM), writes evolved goals back via `AgentRegistry`
- `GoalAbandonmentEvaluator` — abandons goals exceeding failure threshold, filters `activeGoals()` from descriptor
- `GoalFormationEvaluator` — triggers goal formation from context changes
- `GoalSignalProvider` — provides goal signals to routing

**Key observation:** `DefaultGoalFormationService.propose()` validates proposals and calls `agentRegistry.register(updated)` — engine writes formed goals back to eidos `AgentRegistry`. The eidos registry IS the authoritative store for agent goals.

#### blocks (behavioral — largest goal subsystem)

**`io.casehub.blocks.agentic.social.goal` package (500+ lines orchestrator):**
- `GoalProposalOrchestrator` — full drive-based goal lifecycle:
  - Per-tick evaluation of drive states → goal proposals
  - Uses `DriveOrchestrator` for drive signals, `NarrativeOrchestrator` for narrative context
  - `GoalProposalState` — per-agent in-memory state (volatile)
  - Concurrency control via `KeyedLock`
- 4 drive→goal mappers: `AutonomyGoalMapper`, `CompetenceGoalMapper`, `AffiliationGoalMapper`, `CuriosityGoalMapper`
- `DriveGoalFormationStrategy` SPI + `LlmDriveGoalFormationStrategy` — LLM converts drive signals + context into goal descriptions
- `LlmCrossAxisGoalEnricher` — enriches proposals with cross-axis drive insights
- `GoalEscalationPolicy` SPI + `NarrativeGoalEscalationPolicy` — narrative-driven priority escalation
- `GoalProposalTick` — periodic evaluation interface
- `DriveGoalProposal` — proposal record (goalDescription, axis, driveIntensity, suggestedPriority)

**Prompt + termination:**
- `GoalPromptSection` — renders current goals into agent prompts ("Your current goals: [PRIMARY] X, [SECONDARY] Y")
- `GoalReached` — termination condition
- `GoalOutcomePressureSource` — maps `GoalOutcomeCounts` to `TraitActivation` (success rate > 0.7 → positive activation of dominant trait)

**YAML config:** `GoalProposalConfigSpec`, `GoalEscalationConfigSpec`

**Key observation:** Blocks' drive→goal mapping (drives → proposals → formation → escalation → outcomes → pressure feedback) is cognitively sophisticated. It was built before neocortex had cognitive infrastructure. Much of this is arguably cognitive processing that should complement neocortex's goal system.

#### desiredstate (convergence execution)

**Goal compilation:**
- `GoalCompiler<G>` — generic: compile domain-specific goal `G` into `DesiredStateGraph`
- `CompilationResult` — `SingleGraph` (one-shot) or `Lifecycle(List<Phase>)` (ordered phases)
- `Phase(id, graph, completionCondition)` — per-phase graph + completion predicate
- `CompletionCondition` — `allPresent()` (advance when all provisioned), `never()` (continuous reconciliation)

**Graph model:**
- `DesiredStateGraph` — DAG of `DesiredNode`s + `Dependency(from, to)` edges
- `dependenciesOf(node)`, `dependentsOf(node)`, `roots()`, `leaves()` — full graph navigation
- `withNode()`, `withoutNode()`, `withDependency()`, `overlay()`, `connect()` — immutable graph operations
- `DesiredNode(id, spec, humanGating, hooks)` — typed nodes with provisioning specs

**Reconciliation:**
- `ReconciliationLoop` — continuous convergence: desired vs actual state
- `NodeProvisioner` SPI — per-`NodeType` provisioning with resync intervals
- `ReconciliationResult` — resolved/drifted/faulted/mutations
- `ActualState` — observed `NodeStatus` per node (PRESENT/ABSENT/UNKNOWN)
- `ReconciliationStateStore` — durable (JPA implementation exists)

**Examples:**
- `ExpansionGoalCompiler` — two-phase lifecycle: build (sequential construction) → defend (continuous patrol/monitor)
- `OrgGoalCompiler` — organizational units + relationships as a single dependency graph

**Key observation:** Desiredstate already has a dependency graph and phased lifecycle. Its `GoalCompiler<G>` is designed for pluggable goal types — a `CognitiveGoalCompiler` could translate neocortex goal graphs into execution plans. Desiredstate keeps its own decomposition engine; it just uses shared primitives.

#### neocortex (the gap — current state)

- `Intentionlike` trait interface: `goal()`, `status()`, `priority()` — minimal skeleton
- `AspirationalTraitRule` — auto-assigns "Aspirational" trait on eventKind=anticipated + eventValence=aspirational
- `DescriptorView` — read-only eidos identity view with `goals` field (zero eidos compile dep)
- All cognitive infrastructure exists (MindMap, Memory, CBR, Affect, Curiosity, Consolidation) but no goal processing

## Agreed Architectural Direction

### Complement, not replace

Neocortex adds cognitive depth to the existing goal system. Each layer keeps its current role:
- eidos = identity declaration
- engine = case execution + routing orchestration
- blocks = behavioral wiring (drive→goal, prompt, pressure)
- desiredstate = infrastructure convergence
- neocortex = cognitive state (recognition, dependency graph, affect, prioritization)

### Shared vocabulary, independent engines

Goal primitives (types, dependency edges, lifecycle states) should be shared to avoid class duplication. Each repo keeps its own processing engine for its specific concern.

Desiredstate uses shared primitives but has its own `GoalCompiler` decomposition engine.
Neocortex uses shared primitives but has its own cognitive processing.
Engine uses shared lifecycle states but has its own routing evaluators.
Blocks uses shared types but has its own drive→goal behavioral wiring.

### No split-brain

Eidos `AgentRegistry` remains the single authoritative store for "what goals does this agent have." Neocortex provides cognitive context (dependencies, affect, recognition signals) that feeds INTO `GoalFormationContext` and `GoalRevisionContext`. No parallel goal registry.

## Open Decisions

### D1: Where do shared goal primitives live?

**Options:**
- **A. platform-api** — most upstream, available to everyone including eidos. No new dependency directions. But platform-api is the most stable layer; goal types would need to be genuinely universal.
- **B. neocortex-goal-api (lean, zero heavy deps)** — follows `cognitive-api`/`fusion-api` pattern. Engine, blocks, desiredstate already depend on neocortex modules. Would create one new direction: eidos → neocortex-goal-api (if eidos adopts shared types).
- **C. eidos-api (expand existing)** — eidos already has `AgentGoal`, `GoalPriority`. Expand with shared primitives. But neocortex would need to depend on eidos-api (currently zero deps).

**Constraint:** Whichever location, the module must be lean — no MindMap, no Memory, no CDI. Pure types + SPIs only.

**Factors to consider:**
- eidos currently has zero neocortex deps; neocortex has zero eidos deps. Either direction is a new coupling.
- platform-api avoids the question entirely but raises the bar for what "platform primitive" means.
- The shared primitives are: dependency edge types, lifecycle states, priority model, completion predicates. Are these platform-level or cognitive-level?

### D2: What happens to eidos GoalSignalStore?

**Current state:** Volatile in-memory store. Goal outcome data lost on restart. Engine's revision/abandonment evaluators need durable history.

**Options:**
- **A. Eidos gets durable persistence** — JPA/SQLite `GoalSignalStore` impl in eidos. Part of a broader eidos persistence review (what else needs durability? drive state? trait pressure?).
- **B. Neocortex becomes the backend** — `GoalSignalStore` backed by neocortex memory. Engine writes; neocortex persists. But adds latency to routing and couples engine routing to neocortex availability.
- **C. Leave volatile, neocortex tracks separately** — Neocortex gets goal outcomes via `ExperienceEvent` flow. Two representations serving different purposes (fast signal cache vs rich episodic store). Defer eidos durability.

**Recommendation direction:** Eidos gets its own persistence (option A). This is an eidos concern, not a neocortex scope item. Engine routing should work durably without neocortex. But scope it as a broader eidos persistence review — GoalSignalStore is not the only volatile state that matters.

### D3: What moves from blocks to neocortex?

Blocks' `GoalProposalOrchestrator` with drive→goal mappers, LLM formation, cross-axis enrichment, and narrative escalation is cognitive processing that was built before neocortex existed.

**Options:**
- **A. Nothing moves now** — blocks keeps its goal orchestration. Neocortex builds complementary cognitive processing (recognition from experience, dependency graph, affect). Blocks can optionally consume neocortex signals over time.
- **B. Cognitive functions migrate** — drive→goal mapping, LLM formation strategy, priority escalation move to neocortex. Blocks keeps mechanical wiring (prompt rendering, termination, trait pressure). Biggest scope increase but cleanest long-term architecture.
- **C. Neocortex provides SPIs, blocks implements** — neocortex defines goal cognition SPIs (GoalRecognizer, GoalPrioritizer, GoalAffectEvaluator). Blocks' orchestrator calls them. Processing moves gradually as implementations mature.

**Factors:** Option B is the cleanest but requires blocks changes. Option C is incremental. Option A risks building a parallel system.

### D4: How does neocortex goal cognition integrate with engine routing?

Engine's `GoalFormationContext` already takes `existingGoals` and `recentMemories`. Neocortex's cognitive signals need to flow through.

**Options:**
- **A. Enrich GoalFormationContext** — add cognitive fields (dependency graph, affect scores, blocked goals) to the formation/revision contexts. Engine routing consumes richer context.
- **B. Neocortex-backed GoalFormationStrategy** — neocortex provides a `GoalFormationStrategy` implementation that uses its cognitive infrastructure. Displaces the current LLM-only strategy.
- **C. Separate cognitive evaluation phase** — neocortex runs its own evaluation (via `ConsolidationPhase` or similar) and updates goal state independently. Engine routing picks up changes on next evaluation.

### D5: Does desiredstate share goal dependency primitives with neocortex?

Desiredstate has `Dependency(from, to)` and `DesiredStateGraph`. Neocortex proposes typed edges (enables/blocks/requires/contributes-to).

**Options:**
- **A. Shared dependency type** — a common `GoalDependency` record (from, to, type) in the shared primitives module. Desiredstate and neocortex both use it. Desiredstate maps type→execution order; neocortex maps type→semantic relationship.
- **B. Independent types** — each repo defines its own dependency concept. Desiredstate's `Dependency` is execution ordering; neocortex's edges are semantic. They're different enough to stay separate.
- **C. Neocortex dependency informs desiredstate** — neocortex's cognitive dependency graph feeds into `GoalCompiler` implementations. A `CognitiveGoalCompiler` translates neocortex goal+dependency graphs into desiredstate execution graphs. No shared type needed — the translation is the integration point.

### D6: Scope of Epic #345 vs cross-repo work

**Options:**
- **A. #345 scopes to neocortex only** — shared primitives module, cognitive goal processing, MindMap integration. Cross-repo integration (engine enrichment, blocks migration, desiredstate compilation, eidos persistence) tracked as separate epics per repo.
- **B. #345 covers the full architecture** — all 7 scope areas from the epic plus cross-repo integration. Requires a slot with platform, eidos, engine, blocks, desiredstate, neocortex.
- **C. #345 covers primitives + neocortex** — shared primitives module (wherever it lives) plus neocortex cognitive processing. Cross-repo consumption tracked separately but designed coherently.

### D7: How do blocks' goal decomposition and neocortex's cognitive goal graph relate?

**Context:** Blocks already decomposes prose goals into executable sub-goal DAGs via `DecompositionStrategy`. Multiple strategies exist:
- `LlmDecomposition` — LLM breaks prose into agent tasks or subtasks (recursive up to maxDepth). Produces `DagPlan<TaskNode.LeafTask>` with `DagNode(dependsOn, JoinType, contingency)`. Subtasks are recursively decomposed.
- `HeuristicDecomposition`, `CapabilityDependencyDecomposition`, `ForwardReasoningDecomposition` — rule-based strategies
- `GoapDecompositionStrategy` — Goal-Oriented Action Planning
- `ExplicitHtnDecompositionStrategy` — Hierarchical Task Network
- `PortfolioDecompositionStrategy` — multi-strategy selection

Engine's `DefaultGoalDecomposer` iterates `AgentGoal` records from the descriptor, calls the `DecompositionStrategy`, resolves each `GoalStep` to a binding + executor, and materialises the `DagPlan` into `PlanItemDefinition` records. CBR experiences are passed in the `GoalDecompositionContext` to inform decomposition.

**The overlap:** Both blocks/engine and neocortex produce dependency graphs with prose nodes and metadata. A `DagPlan` is a plan, not an execution — the engine/executor decides WHEN to dispatch based on dependencies. Each `DagNode` carries rich metadata: prose description, agent assignment (`AgentRef`), output validation gates (`OutputContract`), contingency plans (alternative `DagPlan` on failure), judgment targets (`JudgmentTarget` with prompt, evidence requirements, trust threshold, escalation strategy), and join semantics (ALL_OF or ANY_OF).

The differences are in node semantics, edge semantics, and lifecycle:

| | Blocks `DagPlan` | Neocortex cognitive graph |
|---|---|---|
| Node content | Prose task + agent assignment + output contract + judgment | Prose goal + affect + confidence + traits |
| Edge semantics | "must complete before" (execution ordering) | "enables/blocks/requires" (semantic relationship) |
| Lifecycle | Plan is created, executed, completed | Graph is persistent, evolves over time |
| Who consumes | Engine executor (dispatches when deps satisfied) | Cognitive processes (prioritisation, curiosity, retrieval) |
| Decomposition | LLM/GOAP/HTN produces the graph | Recognition + consolidation produces the graph |

Both are DAGs with prose nodes and typed edges. The question is whether they share graph primitives or bridge at integration points.

**How they could work together:**
- Neocortex's persistent goal graph provides **prior decomposition patterns** ("last time we decomposed goal X, the structure was Y") → informs LLM prompts or seeds HTN/GOAP strategies
- Neocortex's **known blockers** ("goal A is blocked by B") → decomposition can skip/defer blocked sub-goals
- Neocortex's **affective context** ("agent repeatedly failed at sub-goal C") → different strategy selection, different agent assignment
- Neocortex's **goal consolidation** ("goals X and Y share sub-goals") → merged decomposition avoids duplication
- Blocks' decomposition **outcomes** flow back to neocortex as experience → persistent graph learns which decompositions succeed

### Revised framing: progressive resolution

The original options (A–D) assumed decomposition and deliberation are separate concerns. Research and analysis show they are not — you cannot select, prioritise, or compare goals without understanding their structure. In BDI, deliberation requires understanding what a goal involves. In Soar, subgoaling IS cognition. In ACT-R, goal activation (which determines focus) requires knowing the goal's dependency context.

**The cognitive goal graph has variable resolution.** Not all goals need the same level of structural detail. Resolution depends on:

| Factor | Low resolution (single goal node) | High resolution (sub-goal graph) |
|--------|----------------------------------|----------------------------------|
| Time proximity | Far off | Imminent |
| Overlap with other goals | No overlap detected | Shared sub-goals or dependencies |
| Importance of detail | Decisions don't depend on structure | Prioritisation requires understanding size/cost |
| Execution readiness | Not being considered for execution | About to be submitted for execution |

A distant goal with no overlaps stays as a single node with prose description. As time nears, or an overlap with another goal is detected, neocortex progressively decomposes — generating rough sub-goals to understand scope, dependencies, and potential sharing. Only when a goal is about to be submitted for execution (or when comparing competing execution plans) does full resolution matter.

This is analogous to level-of-detail in graphics rendering — you don't render what you can't see, and you render nearby objects at higher fidelity than distant ones. The cognitive system spends decomposition effort where it has decision-making value.

**Implications for the architecture:**

1. **Neocortex owns the cognitive goal graph at all resolutions** — from single-node placeholders to fully decomposed sub-goal trees. The graph lives in MindMap. Resolution increases over time or on demand.

2. **Blocks' decomposition strategies are a capability neocortex uses for cognitive understanding** — not for execution planning. Neocortex asks "what would this goal involve?" to inform deliberation. The result is stored persistently as goal knowledge.

3. **Engine's execution decomposition is separate** — when neocortex submits a goal via `GoalFormationService.propose()`, engine decomposes again for execution (finer-grained, agent-assigned, with contingencies and output contracts). Engine's decomposition is execution-specific; neocortex's is cognition-specific.

4. **The "submit for execution" path exists** — `GoalFormationService.propose()` writes `AgentGoal` to `AgentRegistry`. Engine's `DefaultGoalDecomposer` picks it up. Neocortex doesn't need to track execution — outcomes flow back as `ExperienceEvent`.

5. **Dependency tracking triggers resolution increase** — when neocortex detects that goal A might share sub-goals with goal B (overlap detection), or that goal C is approaching its time horizon, it increases resolution by decomposing further. This is a cognitive consolidation activity (fits the `ConsolidationPhase` pattern).

6. **Goal selection operates on the graph at current resolution** — prioritisation uses whatever structural knowledge is available. A single-node goal is prioritised by its prose description, affect, and personality concordance. A decomposed goal is prioritised by sub-goal count, dependency depth, estimated effort, and overlap with other goals.

### Resolution management via consolidation ("sleep")

The existing `ConsolidationScheduler` runs periodic maintenance phases when the system is idle — this IS the cognitive "sleep" cycle. Goal resolution is managed as a consolidation phase (`GoalResolutionPhase`), not as a real-time process.

During consolidation, the phase:
- **Prunes** — distant goals with decomposed sub-goals that haven't been accessed → collapse back to single node. Too much detail too far out wastes graph complexity. The detail can be re-derived when needed.
- **Expands** — approaching goals (time proximity) or newly-overlapping goals → increase resolution by decomposing further. The system invests cognitive effort where decisions are imminent.
- **Merges** — detects shared sub-goals across different parent goals → merge sub-goal nodes, create "contributes-to" edges to both parents. This is how the system discovers that two apparently independent goals share infrastructure.
- **Revises** — goals whose dependency state changed (sub-goal completed elsewhere, blocker removed, new information) → update the graph.
- **Decays** — goals with no activity and declining affect → reduce priority, suggest dormancy or abandonment.

This mirrors human sleep consolidation — prune irrelevant detail, strengthen relevant connections, surface relationships not obvious during waking cognition. The `IdleTracker` + `ConsolidationScheduler` already handle timing. `CuriositySignalGenerator` already prioritises subgraphs for consolidation attention — goal subgraphs with high-affect or approaching-deadline goals would naturally receive priority.

Existing consolidation phases that goal resolution complements:
- `ExperienceConsolidationPhase` (priority 15) — graduates experiences to typed nodes. Goal outcomes from execution could graduate to goal-structure knowledge.
- `MergeDetectionPhase` (priority 20) — Jaro-Winkler name similarity + Jaccard neighbor overlap. Same mechanism detects shared sub-goals across parent goals.
- `CuriosityRefreshPhase` (priority 40) — recomputes curiosity signals. Goal-driven curiosity ("what do I need to know to pursue this goal?") is a natural category.

### Cognitive decomposition vs execution decomposition

Blocks' `DecompositionStrategy` is execution-oriented by design — `TaskNode.LeafTask` requires `executor()` (an `ExecutorRef`), `status()` (a `TaskStatus`). Every node must be an agent-assigned task. `LlmDecomposition`'s prompt says "decompose the goal into agent tasks assigned to the agent best suited for it." `PlannedTask` requires an `AgentRef`.

Cognitive sub-goals are not agent tasks. They are intentions — abstract prose representing what a goal involves. "Understand current pain points", "reduce response time", "build trust through consistency." No agent, no capability, no output contract.

**Neocortex needs its own cognitive decomposition** — LLM-based, producing prose sub-goal nodes in MindMap with `decomposes-into` edges. The prompt is different: "what does achieving this involve?" not "which agent does what?"

Two decompositions, different questions, different times:

| | Cognitive (neocortex) | Execution (blocks/engine) |
|---|---|---|
| Question | "What does this goal involve?" | "How do I execute this goal?" |
| When | Early — to understand structure for selection | Late — when submitted for execution |
| Output | MindMap nodes (prose + affect + confidence) | DagPlan (agent tasks + contracts + contingencies) |
| Node type | Intention/thought — no executor | PlannedTask — requires AgentRef |
| Persistence | Persistent graph, variable resolution | Per-case plan, discarded after execution |
| Who uses it | Deliberation (selection, prioritisation, overlap detection) | Engine dispatcher (routing, worker assignment) |

**Correction: blocks' types are more flexible than initially assessed.** `TaskDescriptor.executor()` is `@Nullable`. `GoalStep` (engine's own leaf type) already returns `null` for `executor()`. The `DagPlan` infrastructure (dependency edges, topological sort, cycle detection, join types, contingencies) works regardless of whether nodes have executors.

What blocks would need for cognitive decomposition:
1. **Different prompt** — `LlmDecomposition` already accepts a `SystemPromptCustomiser` SPI. A cognitive-mode customiser swaps "decompose into agent tasks" to "decompose into sub-goals."
2. **Different leaf type** — a `ThoughtNode` implementing `LeafTask` with `executor() → null`, prose description + rationale. Pattern already exists: `GoalStep` does exactly this.
3. **Same DAG infrastructure** — `DagPlan`, `DagNode`, topological sort, `sequentialMerge`, `JoinType` — all reusable unchanged.

The recursive subtask path in `LlmDecomposition` already produces compound nodes (`"subtask"` + `"description"`) that get recursively decomposed without agent assignment until the leaves. The infrastructure supports variable-depth decomposition with unassigned intermediate nodes.

However, the current model is at tension. The vocabulary is execution throughout — `TaskNode`, `LeafTask`, `PlannedTask`, `TaskDescriptor`, `executor()`, `TaskStatus`. Using "TaskNode" to represent a thought stretches terminology beyond intent. The types technically allow it, but the model wasn't designed for it.

**Blocks refactoring opportunity:** The clean parts are already separated — `DagPlan<T>` and `DagNode<T>` are generic, mention nothing about tasks or execution. The pollution is in the intermediate layer: `TaskNode<T>` (sealed, execution-flavored) and `DecompositionStrategy<T>` returning `DagPlan<TaskNode.LeafTask<T>>` instead of `DagPlan<T>`. A refactored blocks would make DAG composition a first-class concept independent of execution, with `DecompositionStrategy<T>` returning `DagPlan<T>` directly. The leaf type becomes truly domain-specific — execution leaves for agent tasks, cognitive leaves for MindMap goal nodes.

**Code verification (challenging the "generalised DAG engine" claim):**

The `DagPlan`/`DagNode`/`JoinType` infrastructure IS general — pure graph machinery with no execution concepts. But the decomposition strategies built on it are deeply coupled to execution:
- `CapabilityDependencyDecomposition` — reads `RoutingCandidate`, iterates `AgentCapability.inputTypes()/outputTypes()`, picks producers by `qualityHint()`, produces `PlannedTask` with agent refs. The planning algorithm IS about matching capabilities to agents.
- `GoapDecompositionStrategy` — coupled to `CaseDefinition.getGoapActions()`, engine's `GoapPlanner`, and `GoalStep`. Deeply engine-specific.
- `ForwardReasoningDecomposition` — SHOP-style forward chaining with `PrimitiveTask.effect()` mutating projected state. Algorithmically general but typed to execution concepts.
- `LlmDecomposition` — prompt hardwired to agent tasks, parser requires `RoutingCandidate` resolution.
- `HeuristicDecomposition` — delegates to sub-strategies, inherits their coupling.

**Honest assessment:** Blocks is an **execution planning engine built on top of general DAG infrastructure.** Not a generalised DAG composition engine. The decomposition strategies are deeply woven into `RoutingCandidate`, `AgentCapability`, `CaseDefinition`, `GoapAction`, `PlannedTask`.

**What IS shareable:** `DagPlan`, `DagNode`, `JoinType`, topological sort, cycle detection, `sequentialMerge`, `parallel` — the graph primitives. These could be extracted to a shared module.

**What is NOT shareable without refactoring:** The decomposition strategies themselves. They produce execution-oriented output and consume execution-oriented context.

**Revised direction:** A blocks refactor to separate the DAG infrastructure from execution-specific strategies would benefit blocks (cleaner model). But sharing graph types between blocks and neocortex is not worth the cost — `DagPlan`/`DagNode`/`JoinType` are ~250 lines total, neocortex and engine never exchange graphs at runtime, and neocortex already has MindMap as its graph infrastructure. The interface between neocortex and engine is `GoalFormationService.propose()` which exchanges goal descriptions (prose + priority), not graph structures.

Neocortex uses MindMap for cognitive goal graphs. Engine/blocks use `DagPlan` for execution plans. Communication is through goal submission, not graph sharing. No platform extraction needed.

Blocks refactoring (generics + factory patterns) still benefits blocks independently — cleaner separation of DAG infrastructure from execution types, less terminological tension. But it's a blocks concern, not a #345 dependency.

**Open sub-questions:**
- How does the cognitive sub-goal graph map to MindMap? Sub-goals as child nodes with typed edges (decomposes-into), resolution level as a node property.
- What priority should `GoalResolutionPhase` have in the consolidation schedule? Must run after `ExperienceConsolidationPhase` (needs graduated experience data) and after `MergeDetectionPhase` (needs merge candidates).
- Should cognitive decomposition use `MindMapExtractor` (existing LLM extraction pipeline with entity/relationship parsing), a new `GoalDecomposer` SPI in neocortex, or a standalone LLM call?

## Next Steps

1. **Move to a slot** — this work spans platform, eidos, engine, blocks, desiredstate, neocortex
2. **Resolve D1–D6** — make the architectural decisions with the full picture
3. **Write the design spec** — from resolved decisions
4. **Create child issues** — per-repo implementation work
5. **Implementation** — batched with checkpoints per the established workflow

## References

- `engine/docs/specs/issue-100-goals-aims-constraints/2026-07-25-goals-constraints-design.md` — eidos goal identity design
- `io.casehub.eidos.api.AgentGoal` — identity-layer goal record
- `io.casehub.eidos.api.GoalSignalStore` — volatile outcome signal SPI
- `io.casehub.eidos.api.GoalEvolution` — goal evolution SPI
- `io.casehub.eidos.runtime.health.DefaultGoalEvolution` — promotion/demotion logic
- `io.casehub.api.model.Goal` — case-level goal (ExpressionEvaluator conditions)
- `io.casehub.api.spi.routing.GoalFormationService` — agent goal formation SPI
- `io.casehub.api.spi.routing.GoalFormationContext` — formation context (existingGoals, recentMemories)
- `io.casehub.engine.internal.routing.DefaultGoalFormationService` — writes to AgentRegistry
- `io.casehub.engine.internal.routing.GoalRevisionEvaluator` — revision orchestration
- `io.casehub.engine.internal.routing.GoalAbandonmentEvaluator` — failure-threshold abandonment
- `io.casehub.engine.internal.routing.GoalOutcomeRecorder` — worker outcome → goal signal
- `io.casehub.blocks.agentic.social.goal.GoalProposalOrchestrator` — drive-based goal lifecycle
- `io.casehub.blocks.agentic.social.goal.LlmDriveGoalFormationStrategy` — LLM drive→goal formation
- `io.casehub.blocks.agentic.social.goal.*GoalMapper` — per-drive-axis mappers
- `io.casehub.blocks.agentic.social.GoalOutcomePressureSource` — outcome→trait pressure
- `io.casehub.blocks.agentic.social.prompt.GoalPromptSection` — goal prompt rendering
- `io.casehub.desiredstate.api.GoalCompiler` — generic goal→graph compilation
- `io.casehub.desiredstate.api.DesiredStateGraph` — dependency DAG with Dependency edges
- `io.casehub.desiredstate.api.Phase` — lifecycle phase with CompletionCondition
- `io.casehub.desiredstate.api.ReconciliationLoop` — continuous convergence
- `io.casehub.neocortex.mindmap.intelligence.Intentionlike` — minimal trait skeleton
- `io.casehub.neocortex.cognitive.index.DescriptorView` — zero-eidos-dep identity view
- `io.casehub.neocortex.mindmap.intelligence.CuriositySignalGenerator` — pattern for goal-driven attention
- `io.casehub.neocortex.memory.experience.GraduationClassifier` — pattern for goal recognition
- `io.casehub.blocks.agentic.decomposition.LlmDecomposition` — recursive LLM goal decomposition (prose → DagPlan)
- `io.casehub.blocks.agentic.decomposition.HeuristicDecomposition` — rule-based decomposition
- `io.casehub.blocks.agentic.decomposition.CapabilityDependencyDecomposition` — dependency-aware decomposition
- `io.casehub.engine.planning.decomposition.GoapDecompositionStrategy` — GOAP decomposition
- `io.casehub.engine.planning.decomposition.ExplicitHtnDecompositionStrategy` — HTN decomposition
- `io.casehub.engine.planning.decomposition.DefaultGoalDecomposer` — orchestrates decomposition per AgentGoal
- `io.casehub.engine.plan.DagPlan` — immutable DAG with topological sort, cycle detection, sequence/parallel/merge operations
- `io.casehub.engine.plan.DagNode` — node with dependsOn, JoinType, optional contingency plan
- Park et al. (2023) — Generative Agents, goal-directed daily planning from reflection
- Schulz & Jander (2025) — Planless BDI Agents, LLM plan generation from goal descriptions
- Addison (2025) — La VIDA, goal-self concordance from personality
