# HANDOFF — casehub-neocortex

## Last Session

Design session for blocks#303 Batch 7. No implementation — pure architectural analysis and planning. Revised Batch 7 from "bridge update" to "complete extraction, no bridge." Created 3 new issues, transferred 4 issues from blocks to neocortex, closed blocks#311 epic.

### Key architectural decisions (D7–D10)

1. **D7: Prompt rendering is cognitive** — the 23 prompt sections, AffordanceRenderer, CognitiveObservationSections move to neocortex cognition. CognitionCore.promptSections() composes them. No bridge layer in blocks.

2. **D8: Cognitive brief = eidos base + evolved layer** — eidos prompt cycle generates the base brief (identity, capabilities, reasoning style). Cognition evolves it through experience (metacognitive feedback loop, neocortex#391).

3. **D9: Lifecycle follows orchestrator pattern** — mechanical steps + LLM commands at defined points. Every lifecycle phase (tick, rendering, brief evolution, consolidation) follows this pattern.

4. **D10: Internal cognitive LLM calls use separate context** — mood appraisal, BDI extraction, brief evolution use separate LLM calls via AgentProvider. Never the main conversation context window. Uses existing platform request routing.

### Issues created

| Issue | What |
|-------|------|
| neocortex#390 | Evaluate prompt rendering formats: prose vs JSON vs hybrid |
| neocortex#391 | Adaptive cognitive brief — metacognitive feedback loop |
| neocortex#392 | Multi-agent cognitive architecture — Inside Out model with adversarial subsystems |

### Issues transferred (blocks → neocortex)

| From | To | What |
|------|----|------|
| blocks#308 | neocortex#393 | Context-budget-aware prompt rendering |
| blocks#283 | neocortex#394 | Directive-minimal architecture |
| blocks#286 | neocortex#395 | Neocortex seeding user guide |
| blocks#313 | neocortex#396 | CBR plan adaptation |

### Issues closed

- blocks#311 — Epic: Neocortex cognitive integration (all children resolved)

### Batches completed (prior sessions)

| Batch | Status | Classes moved |
|-------|--------|---------------|
| 1: Scaffolding | Done | cognition-api + cognition modules |
| 2: Value Types | Done | ~90 types duplicated to cognition-api |
| 3: Store Consolidation | Done | NarrativeMemory, StrategyMemory, UserProfileMemory, MentalModelMemory |
| 4: Pure Orchestrators | Done | MoodOrchestrator, MoodCongruentGoalAppraisal, DriveOrchestrator, DriveComposer, NarrativeOrchestrator, GroupNarrativeOrchestrator, PersonalityEvolutionOrchestrator, RelationshipPressureSource |
| 5: LLM Orchestrators | Done | UserModelOrchestrator, LlmReflectionSynthesizer, InteractionMapper, TokenJaccardDistance, MentalModelOrchestrator, StrategyLearningOrchestrator |
| 5b: Drive Sources | Done | AffiliationDrive, AutonomyDrive, CompetenceDrive, DriveAdaptationPhase |
| 6a: Consolidation Phases | Done | BeliefRevisionPhase, RelationshipStagePhase |
| 6b: Framework + Goals | Done | CognitionCore, CognitionSnapshot, CognitionDelta, CognitionMetrics, AttentionRelevance, CognitiveAttentionMediator, CognitiveGoalOrchestrator, GoalProposalOrchestrator, GoalEmotionMoodBridge |
| 6c: SPIs for blocked | Done | MemoryHygieneOrchestrator, TemporalFocusOrchestrator, ReflectionRetrievalOrchestrator |
| 6d: Summarisation module | Done | Full summarisation framework |
| 6e: Prerequisite types | Done | KnowledgeGapSummary, ReflectionEntry, ReflectionQueryStore, ConsolidationArtifact |
| 6f: Deferred classes | Done | CuriosityDrive, ConsolidationMediator, InnerLifeOrchestrator, NarrativePipeline + related |
| 7: Complete Extraction | In progress | Task 12 done |

### Deferred items

| Item | Reason |
|------|--------|
| CognitionCore.promptSections() | Done — wired in Task 12 |
| KeyedSummarisationRunner | YAGNI — bring when blocks migrates to neocortex summarisation |
| KeyedLevelEventAccumulator | YAGNI — same as above |

## Immediate Next Step

**Batch 7 execution — Task 12 done, 3 remaining:**

1. ~~**Task 12: Move prompt rendering to neocortex**~~ — Done. CognitionPromptRenderer interface in cognition-api. 21 prompt sections + 8 observation rendering types + CognitiveSystemPromptRenderer + ProactiveSpeechSupport + DirectiveSection in cognition module. CognitionCore.promptSections() wired with section customizer and attention relevance overrides. Also added lastFocus()/lastReflections() to TemporalFocusOrchestrator/ReflectionRetrievalOrchestrator SPIs, added cognitive-index dependency to cognition-api.

2. **Task 13: Move defaults** — Recreate SocialCognitionDefaultBeans' 13 @DefaultBean configs in neocortex cognition module.

3. **Task 14: Blocks cleanup** — Delete 169 migrated production files + 113 tests + SocialAvatarCognition + SocialPromptAssembler + SocialCognitionDefaultBeans + 23 prompt section originals. Create thin AvatarCognition adapter. Update CognitionCompiler imports.

4. **Task 15: Documentation** — Update neocortex and blocks CLAUDE.md. Update examples.

## Cross-Module

- blocks#303 modifies both neocortex and blocks repos. blocks on main at 52e40944.
- Blocks code untouched so far — all changes are neocortex-side additions. Batch 7 is the first batch touching blocks.

## References

- `plans/2026-09-29-cognition-migration.md` — migration plan (Batch 7 revised)
- `plans/2026-09-30-summarisation-deferred-unblock.md` — summarisation + deferred classes plan
- `specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `specs/issue-303-migrate-cognitive-state/decisions.md` — 10 design decisions (D1–D10)
- `specs/issue-303-migrate-cognitive-state/2026-09-30-cognitive-architecture-roadmap.md` — 5-phase roadmap
