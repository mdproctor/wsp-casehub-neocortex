# HANDOFF — casehub-neocortex

## Last Session

Continued blocks#303 — migrating social cognition layer from blocks to neocortex. Completed Batch 5 in full and most of Batch 6 (framework + goals). Total: 34 production classes + 12 test files migrated. 149 cognition tests pass.

### Batches completed

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
| 6c: SPIs for blocked | Done | MemoryHygieneOrchestrator, TemporalFocusOrchestrator, ReflectionRetrievalOrchestrator (thin interfaces in cognition-api) |
| 7: Bridge | Not started | |

### Deferred items

| Item | Reason |
|------|--------|
| ConsolidationMediator | Depends on ConsolidationArtifact (exists in slot 196, not merged to main) |
| CuriosityDrive | MemoryHygieneOrchestrator impl blocked on summarisation framework |
| InnerLifeOrchestrator | LevelEvent (blocks summarisation) |
| NarrativePipeline | blocks EventStreamBus, SummarisationRunner |
| NarrativeOutputProcessor | blocks OutputProcessor SPI |
| NarrativeContentSummariser | blocks ContentSummariser SPI |
| CognitionCore.promptSections() | Bridge layer — stays in blocks |

### Key design decisions this session

1. **CognitionCore without promptSections()** — removed all prompt bridge methods. CognitionCore owns tick scheduling and interaction recording. Blocks' SocialAvatarCognition will construct prompt sections using CognitionCore's accessors.

2. **Thin SPIs for blocked orchestrators** — created minimal interfaces (MemoryHygieneOrchestrator, TemporalFocusOrchestrator, ReflectionRetrievalOrchestrator) in cognition-api so CognitionCore compiles without the full implementations.

3. **ConsolidationMediator deferred** — depends on ConsolidationArtifact sealed interface that exists in slot 196's branch but hasn't merged to main. Will land when that branch merges.

4. **Unblock strategies:**
   - CommonGroundState: 3 pure records (42 LOC) duplicated to cognition-api
   - ContentSummariser: nullable in StrategyLearningOrchestrator, dropped entirely
   - NeedSatisfactionConfig: duplicated to cognition drive package
   - StructuredAgentInvoker: replaced with inline AgentProvider.invoke() calls throughout

### Key findings

- Batch 2 duplicated types to cognition-api but did NOT remove blocks originals. Both copies coexist.
- `ide_move_file` cannot cross project boundaries. All moves done by creating files in neocortex.
- eidos-api, memory-core, jackson-databind, platform-agent-api added as cognition dependencies.
- ConsolidationArtifact sealed interface exists in slot 196 but not on main — blocks references it.

## Immediate Next Step

Batch 7: blocks bridge update. Update SocialAvatarCognition to inject neocortex cognition beans, update prompt sections to use neocortex types, delete migrated blocks code. This is blocks-side work.

Before Batch 7, consider:
- Merging slot 196's ConsolidationArtifact so ConsolidationMediator can move
- Moving goal-specific phases from mindmap-intelligence to cognition (GoalResolutionPhase, GoalAffectPhase, GoalPrioritizationPhase, GoalRecognitionPhase) — neocortex-internal moves

## Cross-Module

- blocks#303 modifies both neocortex and blocks repos. blocks on main at 52e40944.
- Blocks code untouched — all changes so far are neocortex-side additions. Blocks cleanup deferred to Batch 7.

## References

- `wsp/specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `wsp/specs/issue-303-migrate-cognitive-state/decisions.md` — 6 design decisions
- `wsp/plans/2026-09-29-cognition-migration.md` — implementation plan (7 batches)
