# HANDOFF — casehub-neocortex

## Last Session

Continued implementing blocks#303 — migrating social cognition layer from blocks to neocortex. Completed Batch 4 (pure-computation orchestrators) with scope adjustments based on dependency analysis. Moved 8 classes + 4 test classes from blocks to neocortex cognition module. 45 tests pass.

### Batch 4 — what moved

| Class | From (blocks) | To (neocortex cognition) | Changes |
|-------|--------------|-------------------------|---------|
| MoodOrchestrator | social/ | mood/ | KeyedLock → inline ConcurrentHashMap<String, ReentrantLock> |
| MoodCongruentGoalAppraisal | social/ | mood/ | Clean move |
| DriveOrchestrator | social/drive/ | drive/ | Removed CDI constructor (blocks deps); DriveSource-based only |
| DriveComposer | social/drive/ | drive/ | Clean move |
| NarrativeOrchestrator | social/narrative/ | narrative/ | NarrativeStore → NarrativeMemory, KeyedLock inlined |
| GroupNarrativeOrchestrator | social/narrative/ | narrative/ | Same rewire as above |
| PersonalityEvolutionOrchestrator | social/ | personality/ | KeyedLock inlined |
| RelationshipPressureSource | social/ | personality/ | Clean move |

### Batch 4 — what was deferred

These classes have blocking blocks dependencies and can't move until their dependencies migrate:

| Class | Blocking dependency | Move when |
|-------|-------------------|-----------|
| GoalEmotionMoodBridge | CognitiveGoalOrchestrator | Batch 6 |
| CuriosityDrive | MemoryHygieneOrchestrator | Batch 5/6 |
| CompetenceDrive | StrategyLearningOrchestrator | Batch 5 |
| AffiliationDrive | UserModelOrchestrator | Batch 5 |
| AutonomyDrive | MentalModelOrchestrator | Batch 5 |
| DriveAdaptationPhase | NeedSatisfactionConfig, NeedTier | Batch 6 |
| NarrativePipeline | blocks summarisation framework | Batch 5/6 |
| NarrativeOutputProcessor | blocks OutputProcessor SPI | Batch 5/6 |
| NarrativeContentSummariser | StructuredAgentInvoker | Batch 5 |
| NarrativeEmissionPolicy | blocks EmissionPolicy SPI | Batch 5/6 |

### Key findings

- Batch 2 duplicated types to cognition-api but did NOT remove blocks originals or add cognition-api dependency to blocks. Both copies coexist.
- `ide_move_file` cannot cross project boundaries in a workspace. All moves done by creating files in neocortex with adjusted packages.
- eidos-api added to neocortex parent POM dependency management.
- rag-spring has a pre-existing drift detection failure (unrelated to #303).

## Immediate Next Step

Batch 5: Move LLM-backed orchestrators (UserModelOrchestrator, MentalModelOrchestrator, StrategyLearningOrchestrator, InnerLifeOrchestrator, LlmReflectionSynthesizer). Replace StructuredAgentInvoker with AgentProvider.

## Cross-Module

- blocks#303 modifies both neocortex and blocks repos. blocks is on main at 52e40944.
- Blocks code untouched — all changes so far are neocortex-side additions. Blocks cleanup deferred to Batch 7.
- New types from #317/#318 (CognitiveProfileParticipant, DomainActivationParticipant, DomainActivationSnapshot) already partially handled (DomainActivationSnapshot is in cognition module).

## References

- `wsp/specs/issue-303-migrate-cognitive-state/2026-09-29-cognition-migration-design.md` — design spec
- `wsp/specs/issue-303-migrate-cognitive-state/decisions.md` — 6 design decisions
- `wsp/plans/2026-09-29-cognition-migration.md` — implementation plan (7 batches)
- `wsp/scripts/migrate_types.py` — cross-repo file migration script
- `wsp/scripts/fix_imports.py` — cross-subpackage import fixer
- `wsp/blog/2026-09-29-mdp01-the-brain-that-lived-in-the-wrong-body.md` — diary
