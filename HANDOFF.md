# HANDOFF — casehub-neocortex

## Last Session

Cross-repo architecture audit for Epic #345 (goal cognition). Traced all goal primitives across eidos, engine, blocks, desiredstate, and neocortex — discovered four distinct goal concepts sharing one word. Blocks has the largest goal subsystem (500+ line GoalProposalOrchestrator with drive-based cognitive processing). GoalSignalStore in eidos is volatile with no durable implementation. Desiredstate already has a dependency graph and phased lifecycle that parallels what #345 proposes. Agreed on "complement, not replace" with shared vocabulary and independent engines. Created slot 203 with all 6 repos.

## Immediate Next Step

Open a CLI in slot 203 (`~/claude/casehub/slots/203/neocortex`), run `work`. Resolve decisions D1–D6 from the context doc, write the design spec, then create per-repo child issues.

## References

- `specs/issue-345-goal-cognition/2026-09-22-goal-architecture-context.md` — comprehensive audit with dependency graph, all goal types mapped, 6 open decisions (D1–D6)
- `blog/2026-09-22-mdp01-four-goals-one-word.md` — diary entry
- `JOURNAL.md` — session journal
- Slot 203: `~/claude/casehub/slots/203/` — platform, eidos, engine, blocks, desiredstate, neocortex
- Slot .plan: `~/claude/casehub/slots/203/.plan` — queue with Batch 0 active (architecture decisions), Batches 1–6 deferred
