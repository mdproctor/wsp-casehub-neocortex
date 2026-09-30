# HANDOFF — casehub-neocortex

## Last Session

Batch 7 implementation — completed Tasks 12 and 13 of the cognition migration.

### Task 12: Move prompt rendering to neocortex (Done)

Created the complete prompt rendering system in neocortex cognition:

- **cognition-api**: `CognitionPromptRenderer` (`@FunctionalInterface`, `@Nullable String render(CognitionRenderContext)`) and `CognitionRenderContext` record
- **cognition/prompt/**: 21 prompt sections migrated from blocks (MoodPromptSection, DrivePromptSection, NarrativePromptSection, AttentionPromptSection, EntityKnowledgePromptSection, StrategyPromptSection, UserModelPromptSection, MentalModelPromptSection, CharacterDrivePromptSection, NeedsPyramidPromptSection, ConsolidationPromptSection, TemporalFocusPromptSection, ReflectionPromptSection, SocialComparisonPromptSection, DomainActivationPromptSection, EmergentGoalPromptSection, ConstraintPromptSection, DirectiveSection, CognitivePreambleGenerator, CognitiveSystemPromptRenderer, ProactiveSpeechSupport)
- **cognition/prompt/observation/**: 8 rendering types (ObservationSection sealed hierarchy, AffordanceRenderer, CognitiveObservationSections with motivationalStateSection + narrativeSection)
- **CognitionCore**: wired `promptSections()` with section customizer, attention relevance overrides, consolidation artifact draining. Added `innerLife` and `consolidationMediator` fields
- **SPI additions**: `TemporalFocusOrchestrator.lastFocus()` and `ReflectionRetrievalOrchestrator.lastReflections()`. Added cognitive-index dependency to cognition-api POM

32 files changed, 1753 LOC added. 191 tests pass.

### Task 13: Move defaults (Done)

Created `CognitionDefaultBeans` with 16 `@DefaultBean @Singleton` producers: 13 config records (DriveConfig, MoodConfig, PersonalityEvolutionConfig, InnerLifeConfig, MentalModelConfig, UserModelConfig, StrategyLearningConfig, NarrativeConfig, GoalProposalConfig, GoalEscalationConfig, NormDetectionConfig, MoodCongruenceConfig, CognitiveGoalConfig) + SubjectResolver (empty set) + InteractionMapper (CognitiveImpact.fromText) + NormFilter (identity). Skipped blocks-only `EventStreamBus<DecisionSignal>`.

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
| 7: Complete Extraction | In progress | Tasks 12–13 done, Tasks 14–15 remain |

### Deferred items

| Item | Reason |
|------|--------|
| CognitionCore.promptSections() | Done — wired in Task 12 |
| KeyedSummarisationRunner | YAGNI — bring when blocks migrates to neocortex summarisation |
| KeyedLevelEventAccumulator | YAGNI — same as above |

## Immediate Next Step

**Batch 7 — Tasks 12–13 done, 2 remaining:**

1. **Task 14: Blocks cleanup** — Delete 169 migrated production files + 113 tests + SocialAvatarCognition + SocialPromptAssembler + SocialCognitionDefaultBeans + 23 prompt section originals. Create thin AvatarCognition adapter. Update CognitionCompiler imports. **This is the first task touching blocks code.** blocks on main at 52e40944.

2. **Task 15: Documentation** — Update neocortex and blocks CLAUDE.md. Update examples.

## Cross-Module

- blocks#303 modifies both neocortex and blocks repos. blocks on main at 52e40944.
- Blocks code untouched so far — all changes are neocortex-side additions. Batch 7 is the first batch touching blocks.

## References

- `plans/2026-09-29-cognition-migration.md` — migration plan (Batch 7 revised)
- `plans/2026-09-30-summarisation-deferred-unblock.md` — summarisation + deferred classes plan
- `specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `specs/issue-303-migrate-cognitive-state/decisions.md` — 10 design decisions (D1–D10)
- `specs/issue-303-migrate-cognitive-state/2026-09-30-cognitive-architecture-roadmap.md` — 5-phase roadmap
