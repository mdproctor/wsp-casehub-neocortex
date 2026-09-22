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
