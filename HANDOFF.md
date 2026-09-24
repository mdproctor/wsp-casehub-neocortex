# HANDOFF — casehub-neocortex

## Last Session

**#296 — Goal-aware cognitive loop** (in progress, Batch 3 partial)

Cross-repo work: neocortex (branch `issue-296-occ-emotion-types`) + blocks (branch `issue-296-goal-aware-cognitive-loop`).

### Completed — neocortex (Batches 1-2)

**OCC Foundation (cognitive-api):**
- EmotionType enum (22 OCC types), CognitiveEmotion record, EmotionSource (INTRINSIC/EMPATHIC), PadProjection, AlmaPadTable (complete Gebhard 2005 OCC→PAD mapping)
- 92 cognitive-api tests pass

**GoalAppraisal SPI (mindmap-api):**
- GoalAppraisal @FunctionalInterface, AppraisalContext record
- HeuristicGoalAppraisal in mindmap-intelligence — maps goal state → OCC emotions (Hope/Fear/Satisfaction/Distress/Disappointment/Pity)
- Surfacing gap amplifies Fear via saturating logistic: gap/(gap+1)
- 12 HeuristicGoalAppraisal tests

**Surfacing + Affect (mindmap-intelligence):**
- SurfacingAggregationPhase (@Priority 12) — scans CaseMemoryStore for cognitive-event=goal-surfaced experiences, aggregates surfaced-count/first-surfaced-at/last-surfaced-at/last-progress-at/surfacing-progress-gap on goal nodes. 9 tests.
- GoalAffectPhase revised — delegates to GoalAppraisal SPI when available, falls back to legacy PAD switch. Uses surfacing-progress-gap (not total count). All 9 existing tests pass.
- **GoalEmotionalProgressionTest** — 7 ordered tests proving the Day 1→7 Hope→Fear→Satisfaction arc works end-to-end within neocortex alone. Full pipeline: surfacing events → aggregation → OCC appraisal.
- 304 mindmap-intelligence tests pass

### Completed — blocks (Batch 3, Task 5 only)

- CognitiveGoalOrchestrator implements CognitionTickParticipant — queries MindMap GOAL nodes, runs GoalAppraisal, records surfacing + agent emotions via CaseMemoryStore, detects decay-signal → GoalRevision, in-memory surfacing cooldown, cold-start fallthrough. 8 tests.
- CognitiveGoalConfig, CognitiveGoalState, GoalRevision records
- CognitionCore.setSectionCustomizer() — pre-wrapping section customization hook

### Remaining

**Task 6: GoalPromptSection extension + SocialAvatarCognition wiring**
- Extend GoalPromptSection to merge drive goals + cognitive goals
- Rank by composite priority (α × drive_intensity + (1-α) × mindmap_priority)
- Render with OCC emotional tone + surfacing context
- Wire in SocialAvatarCognition: construct CognitiveGoalOrchestrator, register as TERMINAL participant, set section customizer

**Task 7: CognitionDefinition DSL extension**
- CognitiveGoalConfigSpec record in agentic-yaml
- Add cognitiveGoal field to CognitionDefinition

**Task 8: E2E scenario test in blocks**
- Birthday gift reminder with full Day 1-7 progression
- Uses InMemoryMindMapStore + InMemoryMemoryStore + mock GoalFormationService

### Key decisions

Design spec: `wsp-casehub-blocks/specs/issue-296-goal-aware-cognitive-loop/2026-09-24-goal-aware-cognitive-loop-design.md`
Research doc: `wsp-casehub-blocks/specs/issue-296-goal-aware-cognitive-loop/2026-09-23-computational-emotion-research.md`
Decisions: `wsp-casehub-blocks/specs/issue-296-goal-aware-cognitive-loop/decisions.md`
Plan: `wsp-casehub-blocks/plans/2026-09-24-goal-aware-cognitive-loop.md`

### Build note

Slot's `.m2` Maven repo needed cross-repo deps installed from canonical repos (engine, work, platform, qhorus, ledger, worker, eidos). Use `-Dmaven.repo.local=/Users/mdproctor/claude/casehub/slots/203/.m2` when installing deps from outside the slot, or build within the slot where `.mvn/maven.config` sets this automatically.

## Immediate Next Step

Resume with `work continue`. Task 6 (GoalPromptSection + wiring) is next. IntelliJ MCP needed for .java edits. The plan doc has the full task specification.

## References

- `docs/specs/issue-345-goal-cognition/2026-09-23-goal-cognition-design.md` — neocortex goal cognition substrate spec
- `docs/guides/contributor-guide.md` — GoalUrgency, Decay step, dynamic urgency
- Blog: `wsp-casehub-blocks/blog/2026-09-24-mdp01-your-agent-doesnt-know-how-it-feels.md`
