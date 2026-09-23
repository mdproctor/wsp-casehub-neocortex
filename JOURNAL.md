# Design Journal — issue-345-goal-cognition

## 2026-09-22 — Platform-wide goal architecture audit

Cross-repo analysis of goal primitives across eidos, engine, blocks, desiredstate, and neocortex. Traced all types, SPIs, implementations, and consumers using IntelliJ MCP across a 6-repo workspace.

Key findings:
- Four distinct "goal" concepts exist (identity, case, desired-state, cognitive) — each legitimate but sharing vocabulary
- Eidos provides primitives + default evaluation (GoalEvolution promotion/demotion). GoalSignalStore is volatile — no durable implementation exists anywhere
- Engine owns routing (formation, revision, abandonment evaluators) and writes goals back to eidos AgentRegistry
- Blocks has the largest goal subsystem — GoalProposalOrchestrator with 4 drive→goal mappers, LLM formation, narrative escalation. Arguably cognitive processing built before neocortex existed
- Desiredstate has its own dependency graph (Dependency DAG) and phased lifecycle — structural parallel with #345's proposed goal dependency graph

Agreed direction: complement (not replace), shared vocabulary with independent engines, eidos AgentRegistry remains authoritative. Slot 203 created for cross-repo design work. 6 open decisions (D1–D6) documented in context spec.

## 2026-09-23 — Decisions resolved, spec written, Batch 1 implemented

Resolved D1-D10 architectural decisions through three rounds of discussion + Standard decision review ($27). Key outcomes:

- **D1:** No new shared module. Eidos-api for identity types (lifecycle state, horizon). Neocortex MindMap conventions for cognitive types. neocortex → eidos-api dependency is natural — "the cognitive layer knows the identity it's cognitive of."
- **Three-dimensional goal model:** LLM goals (prose, blocks), case goals (predicates, engine), cognitive goals (MindMap, neocortex). Three complementary dimensions, not a hierarchy.
- **Substrate vs orchestration:** Neocortex = brain's memory (cerebral cortex). Blocks = motivational circuit (hypothalamus, basal ganglia — processes memories, doesn't store them). Future direction: all cognitive state migrates from blocks stores to neocortex (#378).
- **SPI inversion:** Neocortex defines cognitive SPIs with NoOp @DefaultBean. Blocks provides LLM implementations. Standalone neocortex works without blocks.
- **Progressive resolution:** Cognitive goal graph has variable detail — distant goals as single nodes, approaching goals decomposed. Resolution managed by consolidation sleep cycle (GoalResolutionPhase, priority 35).

Design spec written and validated through Standard post-spec review ($42, 3 rounds, 34 issues, 27 verified). Spec gained: lifecycle state synchronization model (linked vs standalone goals), cycle detection, goal priority computation formula, GoalLifecycleProvider SPI.

Implementation started — Batch 1 (Foundation) complete:
- Eidos: GoalLifecycleState + GoalHorizon enums on AgentGoal (backward compatible)
- Neocortex mindmap-api: SubgraphTypes.GOAL, GoalVocabulary (5 edge types), 3 SPIs (CognitiveGoalDecomposer, CognitiveGoalRecognizer, GoalLifecycleProvider) with value types

4 batches remaining: Goallike trait + TypeRegistry, GoalResolutionPhase, supporting phases + retrieval modulation, integration.

Follow-up issue created: neocortex#378 — migrate blocks social cognition stores to neocortex (XL/High).
