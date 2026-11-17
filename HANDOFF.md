# HANDOFF — casehub-neocortex

## Last Session

CAPS settling convergence fix (#1027). The CAPS eval suite's worst scenario (3.60/5) produced zero behavioral attractors when social-threat inputs caused multi-cycle oscillation. The network was doing something — oscillating between withdrawal and cautious approach — but averaging the oscillation erased the signal. Fixed by detecting oscillation at MAX_ITERATIONS and extracting attractors from peak activations. Added convergence metadata flow through BehavioralSynthesisPhase and tension-aware rendering in BehavioralPromptSection.

### Branch: `issue-1027-caps-settling-convergence`

5 commits:

1. **#1027 test** — SocialThreatOscillationTest: 4 tests covering oscillation detection, peak extraction, defensive attractors, damped regression guard
2. **#1027 fix** — CapsSettler: multi-cycle oscillation detection at MAX_ITERATIONS with peak-based attractor extraction
3. **#1027 metadata** — BehavioralSynthesisPhase: store/clear convergence-type on attractor nodes
4. **#1027 rendering** — BehavioralPromptSection: "competing pull" tension framing for oscillation attractors
5. **Review fix** — clear stale convergence-type on reconvergence, deduplicate sourceContext extraction

### Issues filed this session

| # | Title | Priority |
|---|-------|----------|
| #1043 | Oscillation attractor strategic differentiation in BehavioralPromptSection | S/Med |
| #1044 | CognitiveEmergenceSampleTest.classifierDrivenSettling — distrust not produced | XS/Low |

### Key design decisions

- **Peak not average**: oscillation attractor extraction uses peak output activations rather than averaged state. The average dilutes oscillating outputs below threshold.
- **Oscillation is not failure**: reclassify MAX_ITERATIONS to OSCILLATION when output amplitude > epsilon×10. CBR outcome weight triples (0.1→0.3).
- **Stale metadata cleared**: convergence-type property removed when subsequent settling converges normally.
- **SettlingResult.activations() stays averaged**: only attractor extraction uses peaks.

### Pre-existing failures (not from this session)

- `CognitiveEmergenceSampleTest.classifierDrivenSettling` — `distrust` not produced (#1044)
- `SchererAppraisalStrategyTest.disabledSecs_reducedOutput` (#1039)

## Next Session Plan

### Remaining queue items

| Order | # | Title | Scale/Complexity | Notes |
|-------|---|-------|-----------------|-------|
| 1 | #1033 | BehavioralPromptSection drops mid-tier attractors | — | Related to #1034; attractor rendering filtering |
| 2 | #1034 | Attractor filter threshold is activation-function-dependent | — | The 0.55 filter only works for unipolar outputs; bipolar outputs need different threshold |

Also filed: #1039 (pre-existing test), #1040 (schema cleanup), #1043 (oscillation strategy), #1044 (classifierDrivenSettling).

### Context to carry forward

- Blog entries: `wsp-casehub-neocortex/blog/2026-11-17-mdp01-the-black-box-that-shrugged.md`, `2026-11-17-mdp02-the-network-that-couldnt-decide.md`
- Pre-existing test failures: #1039, #1044
- Design docs updated: `docs/specs/issue-406.../2026-10-04-caps-graph-engine-design.md`, `docs/specs/issue-434.../2026-10-06-behavioral-prompt-section-design.md`

### Files changed this session

| File | What changed |
|------|-------------|
| `cognition-api/.../DriveEvaluation.java` | **New** — per-axis composition trace record |
| `cognition-api/.../DriveConfig.java` | +smoothingAlpha field (0.3 default) |
| `cognition-api/.../PipelineTrace.java` | +driveEvaluations field |
| `cognition/.../DriveComposer.java` | composeWithEvaluations() — per-axis delta tracking, emotion provenance in triggers |
| `cognition/.../DriveOrchestrator.java` | Asymmetric EMA smoothing, lastDriveEvaluations(), appraisal descriptions |
| `cognition/.../ModulationLayer.java` | +descriptions field for per-axis provenance |
| `cognition/.../AppraisalDriveModulator.java` | +INTEREST, DISTRESS→AFFILIATION, REMORSE→AFFILIATION; dominantContributions() |
| `cognition/.../LlmAppraisalStrategy.java` | action_targets schema + parsing + application |
| `cognition/.../TopologyChannelWeighter.java` | APPROACH/SUBMISSION/DOMINANCE profiles and switch cases |
| `cognition/.../SearchBudgetPromptSection.java` | Appraisal-coupled prose (crisis/urgency qualifiers) |
| `cognition/.../CognitionCore.java` | driveEvaluations(), appraisal supplier wiring, descriptions passing |
| `caps-llm-classifier/.../EvalTestSupport.java` | JVM shutdown hook for ClaudeAgentClient |
| `knowledge-pipeline/.../DocumentSearchableProvider.java` | search(null) → search() |
| `cognitive-observability-testing/.../PipelineSnapshotStoreContractTest.java` | +driveEvaluations param |
