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
- Park et al. (2023) — Generative Agents, goal-directed daily planning from reflection
- Schulz & Jander (2025) — Planless BDI Agents, LLM plan generation from goal descriptions
- Addison (2025) — La VIDA, goal-self concordance from personality
