# HANDOFF — casehub-neocortex

## Last Session

Continued blocks#303 — unblocked all 6 deferred classes by creating `summarisation` module and moving classes to cognition. Total: 46 production classes + 25 test files migrated. 191 cognition tests + 101 summarisation tests pass.

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
| 6d: Summarisation module | Done | LevelEvent, EventLevel, ContentSummariser, Summariser, StatefulSummariser, OutputProcessor, EmissionPolicy, LevelEventCompactor, StateStore, Tickable, WindowPolicy, LevelEventBus, LevelEventAccumulator, SummarisationRunner, WindowPolicyEmission, VerbatimContentSummariser, SummarisationPipeline, SummarisationPipelineFactory, DefaultSummarisationPipelineFactory |
| 6e: Prerequisite types | Done | KnowledgeGapSummary, ReflectionEntry, ReflectionQueryStore (memory-api), ConsolidationArtifact (mindmap-api), ConsolidationCompleted updated |
| 6f: Deferred classes | Done | CuriosityDrive, ConsolidationMediator, InnerLifeOrchestrator, NarrativePipeline, NarrativeContentSummariser, NarrativeOutputProcessor, NarrativeEmissionPolicy, ReflectionEventAdapter, NarrativeStateStore |
| 7: Bridge | Not started | |

### Deferred items

| Item | Reason |
|------|--------|
| CognitionCore.promptSections() | Bridge layer — stays in blocks |
| KeyedSummarisationRunner | YAGNI — bring when blocks migrates to neocortex summarisation |
| KeyedLevelEventAccumulator | YAGNI — same as above |

### Key design decisions this session

1. **Summarisation as single neocortex module** — full framework (SPIs + engine) in one module, no api/runtime split. Blocks keeps its copy temporarily; Batch 7 consolidates.

2. **Renames for clarity** — EventStreamBus → LevelEventBus, EventAccumulator → LevelEventAccumulator, Compactor → LevelEventCompactor. Names that sound generic but are tied to LevelEvent now say so explicitly.

3. **SummarisationPipelineFactory SPI** — NarrativePipeline receives a factory, passes its component SPIs (summariser, emission policy, output processor, state store), gets back a SummarisationPipeline. DefaultSummarisationPipelineFactory wraps SummarisationRunner.

4. **Memory-api for shared types** — KnowledgeGapSummary, ReflectionEntry, ReflectionQueryStore in memory-api (not cognition-api) so blocks can use them without pulling cognition's dependency chain.

5. **ConsolidationArtifact created on this branch** — same types as slot 196's branch. Accept merge conflict (types are identical, resolution is trivial).

6. **NarrativeStateStore replaces CbrStateStore chain** — wraps NarrativeMemory (already existed), implements summarisation StateStore. Eliminates NarrativeStore/CbrNarrativeStore/CbrStateStore adapter chain.

### Key findings

- Summarisation framework deeply embedded in blocks (~20 non-social consumers). Cannot be moved out of blocks — both copies coexist.
- Batch 2 dependency analysis missed transitive dependencies outside `agentic/social/` package tree (summarisation, memory types). Full import closure should have been computed.
- MemoryHygieneOrchestrator impl (233 LOC) still in blocks — depends on SummaryResult from qhorus-api.

## Immediate Next Step

Batch 7: blocks bridge update. Update SocialAvatarCognition to inject neocortex cognition beans, update prompt sections to use neocortex types, delete migrated blocks code, migrate blocks' summarisation imports to neocortex.

## Cross-Module

- blocks#303 modifies both neocortex and blocks repos. blocks on main at 52e40944.
- Blocks code untouched — all changes so far are neocortex-side additions. Blocks cleanup deferred to Batch 7.

## References

- `plans/2026-09-29-cognition-migration.md` — parent migration plan
- `plans/2026-09-30-summarisation-deferred-unblock.md` — summarisation + deferred classes plan
- `specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `specs/issue-303-migrate-cognitive-state/decisions.md` — design decisions
