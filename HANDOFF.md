# HANDOFF — casehub-neocortex

## Last Session (extended — two rounds)

**Round 1:** Cross-repo architecture audit for Epic #345. Traced goal primitives across 6 repos, discovered 4 goal concepts, mapped dependency graph. Created slot 203.

**Round 2 (this session):** Deep analysis of blocks' decomposition, research grounding, and architectural refinement. Key findings:

- **Research grounding:** BDI separates desires (cognitive) from intentions (committed) from execution. ACT-R: goals bias retrieval. Scherer: goals are reference points for emotional appraisal. La VIDA: personality-concordant goal selection. Cognitive goals = deliberation, not planning.
- **Progressive resolution:** Cognitive goal graph has variable depth — single node for distant goals, decomposed for approaching/overlapping ones. LOD analogy. Resolution managed bidirectionally by consolidation sleep cycle (prune distant detail, expand approaching goals, merge shared sub-goals).
- **Cognitive vs execution decomposition:** Blocks' strategies (GOAP, HTN, LLM, heuristic) are execution-coupled (RoutingCandidate, AgentCapability, PlannedTask). Not reusable for cognitive decomposition. Neocortex needs its own LLM-based cognitive decomposition producing MindMap nodes.
- **No shared graph types needed:** MindMap IS neocortex's graph. DagPlan is engine's. Interface is GoalFormationService.propose() (prose + priority in) and ExperienceEvent (outcomes out). ~250 lines of graph code not worth extracting to platform.
- **Blocks refactor:** Worth doing for blocks' own cleanliness (generics + factory patterns), but not a #345 dependency.

## Immediate Next Step

In slot 203, pull this branch into the workspace clone and read the context doc. Resolve D1–D7, write the design spec.

## References

- `specs/issue-345-goal-cognition/2026-09-22-goal-architecture-context.md` — comprehensive audit with dependency graph, all goal types mapped, 6 open decisions (D1–D6)
- `blog/2026-09-22-mdp01-four-goals-one-word.md` — diary entry
- `JOURNAL.md` — session journal
- Slot 203: `~/claude/casehub/slots/203/` — platform, eidos, engine, blocks, desiredstate, neocortex
- Slot .plan: `~/claude/casehub/slots/203/.plan` — queue with Batch 0 active (architecture decisions), Batches 1–6 deferred
