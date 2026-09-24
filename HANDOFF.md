# HANDOFF — casehub-neocortex

## Last Session

**#296 — Goal-aware cognitive loop** (CLOSED, landed on main in both repos)

### What landed

**neocortex** (4 commits, 1,265 lines, 15 new files):
- EmotionType (22 OCC types), CognitiveEmotion, EmotionSource, PadProjection, AlmaPadTable in cognitive-api
- GoalAppraisal SPI + AppraisalContext in mindmap-api
- HeuristicGoalAppraisal — maps goal state → OCC emotions with surfacing-gap amplification
- SurfacingAggregationPhase (@Priority 12) — tracks surfacing history on goal nodes
- GoalAffectPhase revised — delegates to GoalAppraisal SPI, falls back to legacy
- GoalEmotionalProgressionTest — 7 ordered tests proving Day 1→7 Hope→Fear→Satisfaction arc
- 304 mindmap-intelligence tests pass

**blocks** (4 commits, 1,002 lines, 12 files):
- CognitiveGoalOrchestrator — CognitionTickParticipant, surfacing recording, agent-experience memories, decay-signal detection
- GoalPromptSection extended — unified drive + cognitive goal rendering with OCC emotion labels
- CognitionCore.setSectionCustomizer() — pre-wrapping section customization hook
- CognitionDefinition.cognitiveGoal DSL field
- GoalCognitionIntegrationTest — 9 ordered tests proving full blocks↔neocortex loop
- 2204 blocks tests pass

### Follow-up epic

**blocks#298** — Cognitive emotion architecture (11 issues):
- Immediate: #299 CDI wiring (S), #300 GoalRevision consumption (XS), #301 Emotion→Mood bridge (S)
- OCC extension: neocortex#382 personality calibration, #383 agent-based emotions, #384 compound emotions
- Architecture: #302 mood congruence, neocortex#385 scenario calibration, #381 push-based attention
- Repo reorganization: #303 migrate cognitive state blocks→neocortex (XL)
- Simulation: neocortex#386 cognitive simulation with calendar integration (L)

### Design artifacts

- Research: `wsp-casehub-blocks/specs/issue-296-goal-aware-cognitive-loop/2026-09-23-computational-emotion-research.md`
- Spec: `wsp-casehub-blocks/specs/issue-296-goal-aware-cognitive-loop/2026-09-24-goal-aware-cognitive-loop-design.md`
- Decisions: `wsp-casehub-blocks/specs/issue-296-goal-aware-cognitive-loop/decisions.md`
- Blog: `wsp-casehub-blocks/blog/2026-09-24-mdp01-your-agent-doesnt-know-how-it-feels.md`

## Immediate Next Step

.plan queue advanced to **neocortex#381** — Design: progressive cognitive attention model for long-running agents.

However, the user indicated preference to work the blocks#298 epic next — starting with the S/XS wiring issues (#299, #300, #301), then the repo reorganization (#303). Resume with `work continue` to discuss sequencing.
