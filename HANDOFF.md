# HANDOFF — casehub-neocortex

## Last Session

**#379 — Goal cognition: Decay step + dynamic urgency** (closed, landed on main as `9a6ec4b3`)
- GoalPrioritizationPhase: added Decay step after Prioritize — standalone goals transition to dormant/abandoned, linked goals get decay-signal property
- GoalUrgency: new package-private utility — dynamic urgency from target-date using horizon-based budget mapping (immediate=4h, short=1d, medium=7d, long=30d, aspirational=365d)
- Both GoalPrioritizationPhase and GoalAffectPhase now use dynamic urgency when target-date present, static property fallback
- Graceful handling of malformed target-date values (falls back to static urgency)
- Clock injection for testability on both phases
- 33 tests (10 GoalUrgency, 14 GoalPrioritization, 9 GoalAffect), 274 module tests pass
- CLAUDE.md + contributor guide updated

**Follow-up issues filed:**
- blocks#296 — Goal-aware cognitive loop: surface priority/urgency/decay to LLM, trigger case creation (L/High)
- neocortex#381 — Design: progressive cognitive attention model for long-running agents (XL/High)

## Immediate Next Step

Resume with `work continue`. The .plan has two items queued:
1. blocks#296 — Wire GoalProposalOrchestrator to read priority/urgency/decay-signal, render to cognitive prompt, trigger case creation. Prerequisite for #381.
2. neocortex#381 — Design exploration: progressive push-based LLM invocation with urgency-driven attention thresholds. Needs brainstorming before code.

blocks#296 first — it's the pull-based integration that #381 builds on.

## References

- `docs/guides/contributor-guide.md` — GoalUrgency, Decay step, dynamic urgency documented
- `docs/specs/issue-345-goal-cognition/2026-09-23-goal-cognition-design.md` — authoritative design spec
- `examples/example-goal-cognition/` — walkthrough example (does not yet cover Decay/dynamic urgency paths)
- neocortex#378 — follow-up epic: blocks social memory migration
- Hortora/engine#90 — closed: engine capabilities extracted into neocortex
