# HANDOFF — casehub-neocortex

## Last Session

Continued implementing blocks#303 — migrating social cognition layer from blocks to neocortex. Completed Batch 4 (pure-computation orchestrators) and partial Batch 5 (LLM orchestrators). Total: 12 production classes + 4 test files + 2 supporting types migrated. 45 cognition tests pass.

### Batches completed

| Batch | Status | Classes moved |
|-------|--------|---------------|
| 1: Scaffolding | Done (prior session) | cognition-api + cognition modules |
| 2: Value Types | Done (prior session) | ~90 types duplicated to cognition-api |
| 3: Store Consolidation | Done (prior session) | NarrativeMemory, StrategyMemory, UserProfileMemory, MentalModelMemory |
| 4: Pure Orchestrators | Done | MoodOrchestrator, MoodCongruentGoalAppraisal, DriveOrchestrator, DriveComposer, NarrativeOrchestrator, GroupNarrativeOrchestrator, PersonalityEvolutionOrchestrator, RelationshipPressureSource |
| 5: LLM Orchestrators | Partial | UserModelOrchestrator, LlmReflectionSynthesizer, InteractionMapper, TokenJaccardDistance |
| 6: Framework | Not started | |
| 7: Bridge | Not started | |

### Deferred classes — blocking dependencies

| Class | Blocking dependency | Earliest batch |
|-------|-------------------|----------------|
| GoalEmotionMoodBridge | CognitiveGoalOrchestrator | Batch 6 |
| CuriosityDrive | MemoryHygieneOrchestrator | Batch 6 |
| CompetenceDrive | StrategyLearningOrchestrator | Batch 5 (blocked) |
| AffiliationDrive | UserModelOrchestrator | Now moveable (B5 done) |
| AutonomyDrive | MentalModelOrchestrator | Batch 5 (blocked) |
| DriveAdaptationPhase | NeedSatisfactionConfig, NeedTier | Batch 6 |
| NarrativePipeline | blocks summarisation framework | Batch 6+ |
| NarrativeOutputProcessor | blocks OutputProcessor SPI | Batch 6+ |
| NarrativeContentSummariser | StructuredAgentInvoker, ContentSummariser SPI | Batch 6+ |
| NarrativeEmissionPolicy | blocks EmissionPolicy SPI | Batch 6+ |
| MentalModelOrchestrator | CommonGroundState (blocks.conversation) | Batch 6+ |
| StrategyLearningOrchestrator | ContentSummariser + qhorus SPI | Batch 6+ |
| InnerLifeOrchestrator | LevelEvent (blocks summarisation) | Batch 6+ |

### Key findings

- Batch 2 duplicated types to cognition-api but did NOT remove blocks originals or add cognition-api dependency to blocks. Both copies coexist.
- `ide_move_file` cannot cross project boundaries in a workspace. All moves done by creating files in neocortex with adjusted packages.
- StructuredAgentInvoker is a stateless utility wrapping AgentProvider — replaced with inline AgentProvider calls (same pattern as rag-query-augmentation's AgentQueryAugmenter).
- eidos-api, memory-core, jackson-databind added as cognition dependencies.
- rag-spring has a pre-existing drift detection failure (unrelated to #303).

## Immediate Next Step

Batch 5 remaining: AffiliationDrive can now move (UserModelOrchestrator landed). Then Batch 6: CognitionCore framework, goal/emergence/consolidation phases — but this batch has the heaviest blocks coupling (summarisation framework, conversation types). May need design decision on whether to extract interfaces or defer those classes.

## Cross-Module

- blocks#303 modifies both neocortex and blocks repos. blocks is on main at 52e40944.
- Blocks code untouched — all changes so far are neocortex-side additions. Blocks cleanup deferred to Batch 7.

## References

- `wsp/specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `wsp/specs/issue-303-migrate-cognitive-state/decisions.md` — 6 design decisions
- `wsp/plans/2026-09-29-cognition-migration.md` — implementation plan (7 batches)
