# HANDOFF — casehub-neocortex

## Last Session (2026-10-25)

Landed #687 (import relationship_stages) on this branch alongside prior #580/#581/#582 work. EntityEnrichmentHandler now stores biographical relationship stage transitions as relationship-domain memories with stage-from/to, period, trigger, and provenance metadata. Added trigger field to Transition record. 5 tests (3 existing + 2 new), 63 total pass in memory-seeding.

Branch `issue-580-3d-ego-graph-view` closed. All 4 issues (#580, #581, #582, #687) landed on main and closed. Both repos pushed to origin and synced to local canonicals. 2 blog entries promoted and published (BJT article + "The Import That Wasn't" note).

Filed #691 — 3D brain-shaped graph layout with neuroanatomical region mapping and three-layer interaction model (pill filters, node-click highlight, explicit ego-focus).

## Immediate Next Step

`work start #691` — 3D brain-shaped graph layout. Builds on #580's THREE.js graph view. Key design decisions already captured in the issue: region mapping table, highlight/darken interaction model, pill filters with dual labels (functional + anatomical).

## Cross-Module

- **#618** — Migrate `ParallelLlmExecutor` to platform's `agent-session-core` — blocked by platform#654
- **#619** — `BeliefRevisionPhase`: replace direct `agentProvider.invoke()` with `SessionPipeline` — blocked by platform#654

## References

- #691 issue body — full region mapping table and interaction model
- `.plan` — queue state
