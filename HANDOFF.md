# Session Handover — neocortex (slot 196)

**Date:** 2026-11-10
**Branch:** `main` (all work pushed)
**Queue:** drained — no active issues

## Current state

Pipeline coherence arc complete. Appraisal emotions now propagate through mood and drives within the same tick cycle. Pipeline coherence eval (#894) scores 4+/5 across all 4 scenarios (was 2/5 at session start).

The cognitive pipeline has three propagation pathways from appraisal:
1. **Appraisal→mood** via `bridgeAppraisalToMood` in CognitionCore (post-DERIVED re-tick)
2. **Appraisal→drives** via `AppraisalDriveModulator` (Frijda 1986 action tendencies)
3. **Appraisal→regulation** via `EmotionRegulationTickParticipant` (existing, now with distress trajectories)

Drive sources are no longer stubs — `MindMapDriveSource` reads from COGNITIVE subgraph with personality-derived fallbacks.

## What was done (2026-11-10)

8 issues closed:

| # | What | Key change |
|---|------|------------|
| 902 | Distress trajectory prompt enrichment | `RegulationTracker` trajectories in generation phase prompt for extrinsic strategies |
| 919 | Appraisal→mood→drive timing fix | Post-DERIVED re-tick + bridge relocation to CognitionCore |
| 922 | Appraisal→drive modulator | `AppraisalDriveModulator` — Frijda action tendencies → SDT drives |
| 923 | MindMapDriveSource | Personality+memory-driven drive baselines from COGNITIVE subgraph |
| 927 | Drive trigger descriptions | Personality-derived trigger text at cold start |
| 928 | Eval judge criteria | Full pipeline coherence rubric (mood+drives+regulation) |
| 931 | Generate override audit | Fixed 2 silent signature mismatches from #902 |
| 204 | Wacky-manor API alignment | CuriosityDrive constructor + CorpusStore.append→write (examples repo) |

## What to pick up next

### Priority 1: #932 — Smoke scenario (M/Med)

Real pipeline integration test: 20-30 ticks, 2-3 agents, real LLM calls, real eval judge. No mocks, no stubs. Fills the gap between unit tests and the 300-tick run. This is the test that validates the full cognitive model, not just the plumbing.

**Issue:** casehubio/neocortex#932
**Why:** Current tests use pre-set appraisal results and (until this session) stub drives. The smoke scenario exercises the actual system — real appraisal, real regulation, real drives, real mood. If something is silently broken, this catches it.

### Priority 2: #930 — 300-tick validation (M/Med)

The post-DERIVED re-tick doubles mood and drive ticks per cycle when appraisal is enabled. Validated via unit tests and eval, NOT validated at scale. Could cause mood overshoot or drive drift over 300 ticks × 17 characters.

**Issue:** casehubio/neocortex#930
**Baseline:** BASELINE0 (mean 3.93 in docs/eval/)

### Other open work

- **Traitors scenario** — mentioned as a direction for richer scenario testing
- #921 — Prediction calibration analysis (S/Med, regulation — check slot 211 overlap)
- #904 — Integration test: social context to goal (regulation-adjacent)
- #903 — Feature toggle for social regulation

### Slot 211 overlap — do not pick up

#905 (eval calibration) and #920 (RPI stale strategy) are queued in slot 211.

## Background reading

| Document | Location | What it covers |
|----------|----------|----------------|
| Post-era6 research doc | `neocortex/docs/research/2026-11-05-post-era6-regulation-and-identity.md` | Full arc — regulation, identity, search budget, pipeline coherence (Stream 10 added this session) |
| Pipeline coherence eval results | `neocortex/docs/eval/pipeline-coherence-eval-923.json` | Latest eval scores — all 4 scenarios at 4+/5 |
| Blog: When Emotions Go Nowhere | `wsp-casehub-neocortex/blog/2026-11-10-mdp01-when-emotions-go-nowhere.md` | Narrative of the pipeline coherence work — timing, Frijda, silent overrides |
| Design spec: MindMapDriveSource | `wsp-casehub-neocortex/specs/issue-923-personality-memory-drive-sources/2026-11-10-personality-memory-drive-sources-design.md` | 4 decisions, data flow, wiring |
| Implementation plan | `wsp-casehub-neocortex/plans/2026-11-10-personality-memory-drive-sources.md` | 4 tasks, 2 batches |

## Key files

| File | What it does |
|------|-------------|
| `cognition/.../core/CognitionCore.java` | Pipeline orchestrator — post-DERIVED propagation block (lines ~320-340) |
| `cognition/.../drive/AppraisalDriveModulator.java` | Frijda emotion→drive mapping (22 emotion types) |
| `cognition/.../drive/MindMapDriveSource.java` | Personality+memory-driven DriveSource — reads COGNITIVE subgraph |
| `cognition/.../drive/DriveOrchestrator.java` | `recordAppraisalModulation` + pending modulation queue |
| `cognition/.../regulation/EmotionRegulationGenerationPhase.java` | 13-param generate with distressTrajectories (#902) |
| `cognition/.../eval/CognitionTestHarness.java` | Test harness — now uses MindMapDriveSource, no stubs |
| `caps-llm-classifier/.../eval/PipelineCoherenceEvalTest.java` | Pipeline coherence eval — 4 scenarios, gate 4/5 |
| `cognitive-index/.../CognitiveDerivationEngine.java` | CDE — now preserves descriptor on derive() |
