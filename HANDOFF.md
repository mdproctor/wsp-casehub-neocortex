# HANDOFF — casehub-neocortex (slot 230)

## Active Work: SE2 CAPS Rework (#1222)

Branch `issue-1222-caps-rework` is ready for implementation. Design and planning are complete.

### What's ready

| Artifact | Location |
|----------|----------|
| **Spec** | `specs/issue-1222-caps-rework/2026-11-25-caps-rework-design.md` |
| **Decisions** (9) | `specs/issue-1222-caps-rework/decisions.md` |
| **Plan** (12 tasks, 4 batches) | `plans/2026-11-25-caps-rework.md` |

### How to start implementation

1. Run `work continue` — the pipeline will detect #1222 as active on `issue-1222-caps-rework`
2. Invoke `executing-plans` with the plan at `plans/2026-11-25-caps-rework.md`
3. Follow the 4-batch structure — each batch is a safe wrap point

### Plan summary (12 tasks, 4 batches)

**Batch 1: Settler Foundation** (Tasks 1-5)
- Task 1: BIPOLAR/rectified-tanh + activation clamp + NodeRange.restingLevel (D2, B1, N6)
- Task 2: Autonomy modifier key fix (N3)
- Task 3: Resting activation clamping (N4)
- Task 4: Distortion sign fix (B5)
- Task 5: Convergence threshold tightening (B6/D5)

**Batch 2: Weight Learning** (Tasks 6-7)
- Task 6: Multi-cue R-W + inhibitory removal + weight clamping + Flyway V2 (D4, B2, N1, N2)
- Task 7: Regulation weight update persistence (B3)

**Batch 3: Classification & CBR** (Tasks 8-10)
- Task 8: Drive injection filter + remap (D3, B12)
- Task 9: ClassificationOutcomeEvaluator OSCILLATION fix (B9)
- Task 10: CBR cache fixes + valence filter (B10, D6)

**Batch 4: Recalibration & Verification** (Tasks 11-12)
- Task 11: Downstream threshold recalibration (D9)
- Task 12: Epic criterion + integration tests (D7, B17)

### Key design decisions

- **D2**: Selective BIPOLAR — output nodes use tanh; UNIPOLAR mediating nodes use rectified tanh (`max(0, tanh(x))`). Respects topology's principled mixed-range design.
- **D3**: Drive injection filtered to INPUT nodes inside `mergeDriveIntensities()`. 16 remaps across 3 tiers (8 Tier 1, 5 Tier 2, 3 Tier 3), verified against runtime topology.
- **D4**: Textbook multi-cue Rescorla-Wagner with per-target-node prediction error. Inhibitory weights removed (dead code). Weight clamping [-2.0, 2.0].
- **D8**: Atomic commits per finding — git bisect-friendly.
- **D9**: Downstream threshold recalibration audit as part of the same PR.

### Verification criterion (from epic)

> Given `physical_threat=1.0`, the top attractor ranking must differ from the no-input ranking. Opposite personalities under the same input must produce attractor strength differences > 0.3.

### Modules in scope

caps-engine, caps-api, caps-testing, caps-llm-classifier, caps-situation-cbr, mindmap-intelligence (BehavioralSynthesisPhase, ClassificationOutcomeEvaluator), cognition (EmotionRegulationTickParticipant), cognition-api (RegulationCascadeConfig)

## Epic Status (#1220)

| Sub-epic | Issue | Status |
|----------|-------|--------|
| SE1: Pipeline Spine | #1221 | **Done** (closed) |
| SE2: CAPS Rework | #1222 | **In progress** — design complete, implementation next |
| SE3: Storage & Data Integrity | #1223 | **Done** (closed) |
| SE4: Consolidation Phases | #1224 | **Done** (closed) |
| SE5: cognitive-index | #1225 | **Done** (closed) |
| SE6: Affect & Emotion | #1226 | **Queued** |
| SE7: Orchestrators | #1227 | **Queued** |

**4 of 7 sub-epics done. SE2 in progress. SE6, SE7 queued.**
