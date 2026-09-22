## D1: Three-dimensional goal architecture

**Choice:** Goals operate across three interacting dimensions, each owned by a different layer. Cognitive goals (neocortex) are the management and enrichment layer that tracks goals from both other dimensions, adds cognitive properties, and also operates standalone.

**Dimension 1 — LLM goals (blocks/langchain4j):** Prose goals proposed by drives or LLM decomposition. An agent's motivational system or an LLM generates natural language goals ("explore quantum computing", "help the customer resolve their billing issue"). These flow through `DriveGoalFormationStrategy` → `GoalProposalOrchestrator` → eventually become eidos `AgentGoal` for prompt rendering.

**Dimension 2 — Case goals (engine):** Structured predicates over case state. `Goal.builder().name("loan-approved").condition(".decision == \"approved\"").kind(GoalKind.SUCCESS).build()`. Machine-evaluated by the engine control loop. Cases ARE goal pursuit — a case runs, achieves its goal conditions, and completes. LLM goals can trigger cases (prose → structured execution). Expression evaluation is pluggable (JQ, MVEL, Java lambdas).

**Dimension 3 — Cognitive goals (neocortex, NEW):** Goals as MindMap knowledge graph nodes with affect, dependencies, confidence, temporal horizon, and lifecycle state. The cognitive layer MANAGES and ENRICHES goals from both other dimensions — when a drive proposes a goal, the cognitive layer tracks it; when a case completes, the cognitive layer updates goal status and models affective response. Cognitive goals also exist standalone — not every goal originates from a drive or triggers a case.

**Alternatives:**
- Two-tier only (LLM + case, no cognitive management) — leaves goal tracking, prioritization, and affect as ad-hoc responsibilities scattered across blocks and engine
- Unified single Goal type — forces a single type to serve prose interpretation, predicate evaluation, AND cognitive enrichment. The evaluation mechanisms are fundamentally different (LLM vs predicate vs graph reasoning)
- Goal as sealed interface hierarchy — sealed hierarchies across module boundaries are brittle and would live in different repos

**Rationale:** Each dimension has a genuinely different evaluation mechanism and lifecycle. LLM goals are interpreted by language models. Case goals are evaluated by predicate engines. Cognitive goals are managed by graph reasoning with affect modulation. Trying to unify the types conflates three distinct concerns. The cognitive layer's role is management and enrichment — it provides the persistent, structured view of an agent's goal landscape that neither blocks nor engine alone offers. "Standalone" is critical because cognitive goals can emerge from conversation, experience consolidation, or reflection without any drive signal or case execution.

**Key insight from engine research (ADR-0001):** "A goal is a predicate over state, not a checklist of tasks that ran." This applies to case goals. Cognitive goals extend this: a goal is ALSO a knowledge structure with affect, dependencies, and lifecycle — not just a predicate.

**Trade-offs:** Three systems must stay in sync. Cognitive goal state can diverge from engine case state if events are missed. Mitigated by CDI events at the seams (case completion → cognitive update, drive proposal → cognitive tracking).
**Sources:** engine blog 2026-04-09 (goals vs tasks research), LlmDriveGoalFormationStrategy.java, GoalProposalOrchestrator.java, Goal.java (api.model), GoalDecomposer.java, issue #345 comment (infrastructure audit)
**Exploration:** deep-analysis
**Status:** captured
