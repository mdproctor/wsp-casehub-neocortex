# HANDOFF — casehub-neocortex

## Last Session

Continued blocks#303 — migrating social cognition layer from blocks to neocortex. Completed remaining Batch 5 items (MentalModelOrchestrator, StrategyLearningOrchestrator) and all unblocked drive sources (AffiliationDrive, AutonomyDrive, CompetenceDrive, DriveAdaptationPhase). Total: 22 production classes + 8 test files migrated. 110 cognition tests pass.

### Batches completed

| Batch | Status | Classes moved |
|-------|--------|---------------|
| 1: Scaffolding | Done (prior session) | cognition-api + cognition modules |
| 2: Value Types | Done (prior session) | ~90 types duplicated to cognition-api |
| 3: Store Consolidation | Done (prior session) | NarrativeMemory, StrategyMemory, UserProfileMemory, MentalModelMemory |
| 4: Pure Orchestrators | Done (prior session) | MoodOrchestrator, MoodCongruentGoalAppraisal, DriveOrchestrator, DriveComposer, NarrativeOrchestrator, GroupNarrativeOrchestrator, PersonalityEvolutionOrchestrator, RelationshipPressureSource |
| 5: LLM Orchestrators | Done | UserModelOrchestrator, LlmReflectionSynthesizer, InteractionMapper, TokenJaccardDistance, MentalModelOrchestrator, StrategyLearningOrchestrator |
| 5b: Drive Sources | Done | AffiliationDrive, AutonomyDrive, CompetenceDrive, DriveAdaptationPhase |
| 6: Framework | Not started | |
| 7: Bridge | Not started | |

### This session's commits

| SHA | Description |
|-----|-------------|
| b7f4b591 | AffiliationDrive (6 tests) |
| 9eeecce5 | MentalModelOrchestrator + CommonGroundState records (17 tests) |
| f70c1675 | StrategyLearningOrchestrator — dropped nullable ContentSummariser (24 tests) |
| f7b6fdfd | DriveAdaptationPhase + NeedSatisfactionConfig + NeedTierMappingProvider (5 tests) |
| 988c4c62 | AutonomyDrive + CompetenceDrive (13 tests) |

### Unblock strategies used

| Class | Strategy |
|-------|----------|
| MentalModelOrchestrator | Duplicated CommonGroundState + GroundedFact + EpistemicStatus (42 LOC) to cognition-api |
| StrategyLearningOrchestrator | Dropped nullable ContentSummariser integration (blocks summarisation dep) |
| DriveAdaptationPhase | Duplicated NeedSatisfactionConfig + NeedTierMappingProvider to cognition drive package |
| AutonomyDrive | Cascading unblock from MentalModelOrchestrator |
| CompetenceDrive | Cascading unblock from StrategyLearningOrchestrator |

### Deferred classes — blocking dependencies

| Class | Blocking dependency | Notes |
|-------|-------------------|-------|
| GoalEmotionMoodBridge | CognitiveGoalOrchestrator | Batch 6 |
| CuriosityDrive | MemoryHygieneOrchestrator → summarisation framework | Batch 6+ |
| NarrativePipeline | blocks EventStreamBus, SummarisationRunner | Deep summarisation coupling |
| NarrativeOutputProcessor | blocks OutputProcessor SPI | Deep summarisation coupling |
| NarrativeContentSummariser | blocks ContentSummariser SPI | Deep summarisation coupling |
| InnerLifeOrchestrator | LevelEvent (blocks summarisation) | Could extract interface |

### Key findings

- Batch 2 duplicated types to cognition-api but did NOT remove blocks originals or add cognition-api dependency to blocks. Both copies coexist.
- `ide_move_file` cannot cross project boundaries in a workspace. All moves done by creating files in neocortex with adjusted packages.
- StructuredAgentInvoker replaced with inline AgentProvider calls (same pattern as rag-query-augmentation's AgentQueryAugmenter).
- KeyedLock replaced with ConcurrentHashMap<String, ReentrantLock> withLock() pattern.
- eidos-api, memory-core, jackson-databind added as cognition dependencies.
- rag-spring has a pre-existing drift detection failure (unrelated to #303).
- CommonGroundState is trivially duplicatable (3 pure records, 42 LOC, zero deps).
- ContentSummariser in StrategyLearningOrchestrator was nullable — safe to drop without behavioral change.

## Immediate Next Step

Batch 6: CognitionCore framework + goal/emergence/consolidation phases. This batch has the heaviest blocks coupling — 5 classes blocked on blocks' summarisation framework (EventStreamBus, SummarisationRunner, LevelEvent, OutputProcessor, ContentSummariser). Design decision needed: extract minimal interfaces for these into cognition-api, or defer the 5 summarisation-coupled classes until blocks itself is refactored.

Moveable items in Batch 6 (no summarisation dep): CognitionCore, CognitionSnapshot, CognitionDelta, CognitionMetrics, CognitiveAttentionMediator, ConsolidationMediator, GoalProposalOrchestrator, CognitiveGoalOrchestrator (unblocks GoalEmotionMoodBridge), BeliefRevisionPhase, RelationshipStagePhase.

## Cross-Module

- blocks#303 modifies both neocortex and blocks repos. blocks is on main at 52e40944.
- Blocks code untouched — all changes so far are neocortex-side additions. Blocks cleanup deferred to Batch 7.

## References

- `wsp/specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `wsp/specs/issue-303-migrate-cognitive-state/decisions.md` — 6 design decisions
- `wsp/plans/2026-09-29-cognition-migration.md` — implementation plan (7 batches)
