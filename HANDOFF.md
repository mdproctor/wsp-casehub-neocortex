# HANDOFF — casehub-neocortex

## Last Session

Batch of 4 XS/S maintenance fixes on branch `issue-491-batch-fixes`, all landed on main. Blog entry written with 2 SVG diagrams.

### #491 — Priority collision renumber (8 files)

Two `@Priority` collisions in the consolidation pipeline: `BehavioralSynthesisPhase` and `RelationalSchemaEvolutionPhase` both at 19, `MergeDetectionPhase` and `DriveProfileDerivationPhase` both at 20. Renumbered the 19–27 range so all 22 phases have unique priorities. Drive chain ordering preserved. CLAUDE.md updated to match.

### #494 — Stale vocabulary in tests (2 files)

Replaced `"collaborative"` with `"cooperative"` in 4 memory-seeding test sites. Tests were passing via the `default -> {}` no-op branch — the drive modulation paths they claimed to test never executed.

### #713 — CognitionConfig toggle mapping (1 file)

Added 24-row Javadoc table to `CognitionConfig` mapping each boolean toggle to its `CognitionDefinition` YAML section and the orchestrator/prompt section it gates.

### #715 — executionChainId on CbrPlanRecord (4 files)

Nullable `executionChainId` field for linking triage attempts into chains. Backward-compatible 8-arg constructor (27 existing call sites unchanged). Qdrant store serialises/deserialises via `_execution_chain_id` payload key. `withExecutionChainId()` convenience method. 3 new tests.

## Suggested Next

#587 — Graduated SituationClassifier (L/High). The priority renumbering fixed phase ordering, but `BehavioralSynthesisPhase` still depends on `RuleBasedSituationClassifier` which uses academic vocabulary that doesn't match runtime language. #587 wires the existing `LlmSituationClassifier` as a fallback and adds CBR confidence accumulation.

## References

- `blog/2026-10-29-mdp02-four-bugs-that-passed-ci.md` — diary entry with 2 SVG diagrams
