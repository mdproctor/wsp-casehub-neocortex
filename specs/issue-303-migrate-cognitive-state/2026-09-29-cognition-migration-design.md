# Cognition Migration Design — blocks#303

**Date:** 2026-09-29
**Issue:** casehubio/blocks#303
**Scope:** Migrate entire social cognition layer from blocks to neocortex

## Problem

Blocks owns ~213 production files (~13,355 LOC) of cognitive state
computation that cannot function without neocortex. Every orchestrator,
every store, every consolidation phase depends on neocortex types, stores,
or SPIs. The current split is historical — blocks was built first, neocortex
grew underneath it. The architecture should reflect reality: neocortex owns
all cognitive computation, blocks owns the conversation surface.

## Boundary

**Moves to neocortex (new `cognition-api` + `cognition` modules):**
- CognitionCore (tick scheduler) + framework types
- All 8 orchestrators + supporting types
- Goal proposal + cognitive goal lifecycle
- Emergence (norms + collective goals)
- Belief revision phase
- Drive adaptation phase
- Relationship stage phase
- LlmReflectionSynthesizer
- Store SPIs (consolidated onto existing neocortex abstractions)
- MemoryHygieneOrchestrator
- TemporalFocusOrchestrator
- Shared utilities (KeyedLock or equivalent)
- All associated tests (~114 files, ~14,673 LOC)

**Stays in blocks (bridge layer):**
- `SocialAvatarCognition` — CDI composition root, injects neocortex beans
- 16 prompt sections — read neocortex cognitive state, render as PromptSection
- `CognitiveSystemPromptRenderer` + `SocialPromptAssembler`
- `SocialCognitionDefaultBeans` — CDI producer for defaults
- `PromptSection` and `AvatarCognition` interfaces remain in speech-api

Blocks becomes a thin adapter: neocortex exports cognitive state, blocks
renders it for the LLM conversation.

## Module Structure

### cognition-api (zero deps, Tier 1)

Package: `io.casehub.neocortex.cognition`

Contains:
- Tick types: `MoodTick`, `DriveTick`, `NarrativeTick`, `UserModelTick`,
  `MentalModelTick`, `StrategyLearningTick`, `StrategyReflection`,
  `InnerLifeTick`, `EvolutionTick`
- State types: `DriveProfile`, `DriveAxis`, `DriveIntensity`,
  `NarrativeState`, `NarrativeFragment`, `NarrativeEpisode`,
  `UserProfile`, `MentalModelSnapshot`, `StrategyProfile`,
  `MentalProjection`, `AttributedState`, `TraitActivation`
- Signal hierarchies: `MoodSignal` (sealed), `InteractionSignal` (sealed),
  `MentalStateSignal` (sealed), `EngagementSignal` (sealed)
- Enums: `CognitionPhase`, `DriveAxis`, `BdiDimension`, `CueType`,
  `RewardAxis`, `ReinforcementDirection`
- SPIs: `CognitionTickParticipant`, `DriveSource`, `TraitPressureSource`
- Records: `CognitionTickContext`, `CognitiveImpact`,
  `MotivationAssessment`, `ContentQualityGate`
- Config types: `MoodConfig`, `MoodCongruenceConfig`, `DriveConfig`,
  `DriveAdaptationConfig`, `NarrativeConfig`, `UserModelConfig`,
  `MentalModelConfig`, `StrategyLearningConfig`, `InnerLifeConfig`,
  `PersonalityEvolutionConfig`
- Goal proposal types: goal policies, mappers, records
- Emergence types: norm/collective-goal records, configs

Dependencies: cognitive-api only (for Confidence, ConfidenceOrigin, etc.).
Most types are pure records/enums with zero deps.

### cognition (CDI implementation)

Package: `io.casehub.neocortex.cognition`

Sub-packages:
```
io.casehub.neocortex.cognition
  .core         — CognitionCore, CognitionSnapshot, CognitionDelta,
                   CognitionMetrics, CognitiveAttentionMediator,
                   ConsolidationMediator, AttentionRelevance
  .mood         — MoodOrchestrator, MoodCongruentGoalAppraisal,
                   GoalEmotionMoodBridge
  .drive        — DriveOrchestrator, DriveComposer, drive source impls
                   (Affiliation, Autonomy, Competence, Curiosity),
                   DriveAdaptationPhase, RelationshipPressureSource
  .narrative    — NarrativeOrchestrator, NarrativePipeline,
                   NarrativeOutputProcessor, NarrativeContentSummariser
  .usermodel    — UserModelOrchestrator
  .mentalmodel  — MentalModelOrchestrator
  .strategy     — StrategyLearningOrchestrator
  .innerlife    — InnerLifeOrchestrator
  .personality  — PersonalityEvolutionOrchestrator
  .goal         — GoalProposalOrchestrator, CognitiveGoalOrchestrator,
                   LlmDriveGoalFormationStrategy, LlmCrossAxisGoalEnricher
  .emergence    — SocialNormDetector, CollectiveGoalFormation
  .belief       — BeliefRevisionPhase
  .relationship — RelationshipStagePhase, RelationshipStageConfig/Provider
  .reflection   — LlmReflectionSynthesizer
  .memory       — MemoryHygieneOrchestrator
  .temporal     — TemporalFocusOrchestrator, ReflectionRetrievalOrchestrator
```

Dependencies:
- cognition-api
- cognitive-api, cognitive-index
- memory-api (CaseMemoryStore, CbrRecordStore, ExperienceEvent, MoodState, etc.)
- mindmap-api (MindMapStore, GoalAppraisal, AttentionSignal)
- mindmap-intelligence (ConsolidationPhase SPI, TypeRegistry)
- platform (AgentProvider — via `Instance<AgentProvider>` for graceful degradation)
- eidos (AgentDescriptor, DispositionEvolution — via `Instance<>`)
- fusion-api (for strategy scoring)

All external deps via `Instance<>` for optionality. If cognition module
is not on classpath, nothing activates in other neocortex modules — they
already use `Instance<>` throughout (confirmed by optionality audit).

### cognition-inmem

In-memory store stubs for `@QuarkusTest`. Follows existing pattern
(mindmap-inmem, memory-inmem).

### cognition-testing

Contract test base classes. Follows existing pattern (mindmap-testing,
memory-testing, rag-testing).

## Store Consolidation

No new Store SPIs. Existing ad-hoc stores map onto neocortex abstractions:

| Blocks store | Neocortex target | Rationale |
|---|---|---|
| NarrativeStore | CbrRecordStore | CbrNarrativeStore already uses CBR. NarrativeStateSchema already defines the CBR schema. Direct mapping. |
| StrategyStore | CbrRecordStore | Strategy profiles are feature-vector records with similarity search. This IS CBR. |
| UserProfileStore | CaseMemoryStore | User observations + synthesized profiles are domain-scoped memories (domain="user-profile"). |
| MentalModelStore | CaseMemoryStore | BDI snapshots are domain-scoped memories (domain="mental-model"). Alternatively, MindMap nodes with Believable/Intentional traits on per-agent subgraphs. |

Each consolidation replaces a custom SPI + JPA implementation with
domain-specific query helpers on top of the generic store. Typed
convenience methods (e.g., `findProfileForUser(agentId, userId)`) wrap
the generic `CaseMemoryStore.query()` call.

JPA backend implementations in blocks (`social-jpa`, `social-jpa-common`,
`social-spring-jpa`) are deleted — their data maps onto the generic store
backends (SQLite, Qdrant, in-memory) that already exist.

## Migration Ordering

IntelliJ `ide_move_file` and `ide_refactor_rename` handle the mechanical
moves. The ordering ensures no circular cross-repo dependencies at any
intermediate step.

### Phase 0: Prerequisites

- blocks#317 must land first (active work in another slot)
- Create `cognition-api` and `cognition` Maven modules in neocortex
- Wire into parent POM, set up package structure

### Phase 1: Value types and SPIs → cognition-api

Move bottom-up — types with zero dependencies first:
1. Enums: CognitionPhase, DriveAxis, BdiDimension, CueType, RewardAxis,
   ReinforcementDirection
2. Records: tick types (MoodTick, DriveTick, etc.), state types
   (DriveProfile, NarrativeState, UserProfile, MentalModelSnapshot, etc.)
3. Sealed hierarchies: MoodSignal, InteractionSignal, MentalStateSignal,
   EngagementSignal
4. Config types: all *Config records
5. SPIs: CognitionTickParticipant, DriveSource, TraitPressureSource

No blocks code changes needed yet — blocks can depend on
cognition-api temporarily during migration.

### Phase 2: Pure-computation orchestrators → cognition

Move orchestrators that don't use LLM:
1. MoodOrchestrator + MoodCongruentGoalAppraisal + GoalEmotionMoodBridge
2. DriveOrchestrator + DriveComposer + drive source impls
3. NarrativeOrchestrator + NarrativePipeline + NarrativeOutputProcessor
4. PersonalityEvolutionOrchestrator

Each move: update imports in blocks to point at neocortex, run tests.

### Phase 3: Store consolidation

For each store, in parallel:
1. Write the domain-specific query helper on the neocortex store
2. Migrate data access in the orchestrator to use the neocortex store
3. Delete the blocks Store SPI + JPA implementation
4. Update/move tests

### Phase 4: LLM-backed orchestrators → cognition

1. UserModelOrchestrator (replace StructuredAgentInvoker with AgentProvider)
2. MentalModelOrchestrator
3. StrategyLearningOrchestrator
4. InnerLifeOrchestrator
5. NarrativeContentSummariser
6. LlmReflectionSynthesizer

### Phase 5: Framework + higher-order components → cognition

1. CognitionCore + CognitionSnapshot + CognitionDelta + CognitionMetrics
2. CognitiveAttentionMediator + ConsolidationMediator + AttentionRelevance
3. GoalProposalOrchestrator + CognitiveGoalOrchestrator + LLM strategies
4. SocialNormDetector + CollectiveGoalFormation (emergence)
5. BeliefRevisionPhase
6. DriveAdaptationPhase
7. RelationshipStagePhase
8. MemoryHygieneOrchestrator + TemporalFocusOrchestrator

### Phase 6: Blocks bridge update

1. Update SocialAvatarCognition to inject neocortex cognition beans
2. Update 16 prompt sections to read from neocortex types
3. Update SocialCognitionDefaultBeans
4. Delete all blocks social/ packages (except bridge layer)
5. Delete blocks social-jpa modules

### Phase 7: Cleanup

1. Delete KeyedLock from blocks (replaced by neocortex equivalent or
   standard concurrency)
2. Delete StructuredAgentInvoker if no longer used
3. Run full test suite across both repos
4. Update blocks CLAUDE.md — remove social cognition module descriptions
5. Update neocortex CLAUDE.md — add cognition module descriptions

## Optionality Guarantee

**Existing neocortex modules are already safe** (confirmed by audit):
- cognitive-index: all beans use `Instance<>` with `isResolvable()` checks
- mindmap-intelligence: ConsolidationScheduler discovers phases via CDI,
  runs harmlessly with zero phases
- cognitive-observability: classpath-activated decorator

**New cognition module requirements:**
- All store access via `Instance<CaseMemoryStore>`, `Instance<CbrRecordStore>`,
  `Instance<MindMapStore>` with graceful degradation
- `Instance<AgentProvider>` for LLM access — LLM orchestrators no-op when
  unavailable
- CognitionCore only activates when cognition module is on classpath
- `@DefaultBean` NoOps for any SPIs the module exports
- Config-gated features via `@IfBuildProperty` where appropriate

**The 4 goal-specific consolidation phases** currently in
mindmap-intelligence (GoalResolutionPhase, GoalAffectPhase,
GoalPrioritizationPhase, GoalRecognitionPhase) are candidates to move
into the cognition module since they're cognition-domain. They already
work via CDI discovery — moving them just changes which jar they ship in.

## Consumer Impact

**Pre-release platform — breaking changes cost nothing.**

- casehub/examples (wackymanor): update imports from blocks social types
  to neocortex cognition types
- Any app importing blocks social cognition directly: update deps to
  include neocortex cognition module
- blocks dependency: add `cognition` as a dependency, remove internal
  social cognition packages

## Scale

| Metric | Value |
|---|---|
| Production files to move | ~213 |
| Production LOC | ~13,355 |
| Test files to move | ~114 |
| Test LOC | ~14,673 |
| New neocortex modules | 4 (cognition-api, cognition, cognition-inmem, cognition-testing) |
| Blocks modules affected | blocks-core, social-jpa, social-jpa-common, social-spring-jpa |
| Blocks modules deleted | social-jpa, social-jpa-common, social-spring-jpa |
| Migration phases | 7 |

## References

- casehubio/blocks#303 — original issue
- casehubio/blocks#296 — established the pattern (OCC emotions moved to neocortex)
- casehubio/blocks#298 — parent epic
- neocortex CLAUDE.md — module structure and conventions
- rag-query-augmentation — precedent for AgentProvider usage in neocortex
- cognitive-index — Instance<> graceful degradation patterns
- mindmap-intelligence ConsolidationScheduler — tick scheduler precedent
