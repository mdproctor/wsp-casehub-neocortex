# HANDOFF — casehub-neocortex

## Last Session

Completed #407 (research: psychology cause-effect models). Produced a 1456-line
spec covering 6 psychological models (attachment, BIS/BAS, CBT, trauma, operant
conditioning, Bandura) composed into a CAPS spreading activation network. Key
decision: two-layer hybrid (CAPS + behavioral attractors) with Rescorla-Wagner
weight updates — three-layer Bayesian design simplified during standard
adversarial review (60 findings incorporated, 4 dimensions, $136). Extracted
starter topology YAML (77 nodes, 38 connections, disposition modifiers). Landed
on main as 97cdd961.

## Immediate Next Step

Start #401 — standardised experience-to-behaviour schema. The catalogue of
reusable entries (trigger → tendency → seeding recipe) that #408 and #398
consume. Read the #407 spec first.

## References

- Spec: `specs/issue-407-psychology-cause-effect-models/2026-10-02-psychology-cause-effect-models-design.md`
- Topology: `neocortex/docs/specs/2026-10-02-caps-topology.yaml`
- Decisions: `specs/issue-407-psychology-cause-effect-models/decisions.md`
- Epic: casehubio/neocortex#406
