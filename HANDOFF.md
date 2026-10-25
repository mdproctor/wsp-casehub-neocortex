# Session Handover — neocortex (slot 196)

**Date:** 2026-10-25
**Branches:** `issue-698-move-zero-dep-eval-tests`, `issue-699-neocortex-eval-fixtures`
**Epic:** casehubio/neocortex#697 — Migrate neocortex eval tests from wacky-manor

## What was done (this session)

### 1. Move zero-dep eval tests (casehubio/neocortex#698) — branch `issue-698-move-zero-dep-eval-tests`

Migrated 4 LLM eval tests from wacky-manor `experiment/` to neocortex `caps-llm-classifier/src/test/java/.../eval/`:

| Test | Manor deps replaced |
|------|-------------------|
| ChannelWeightingEvalTest | None (direct move) |
| ClassifierModelComparisonTest | None (direct move) |
| SituationClassifierIntegrationTest | None (direct move) |
| BehavioralAttractorEvalTest | AgentResponse → ThinkingDialogueResponse; CharacterAgentLoop.RESPONSE_FORMAT_INSTRUCTION → inline; LlmTestSupport removed (unused) |

### 2. Create eval test fixtures (casehubio/neocortex#699) — branch `issue-699-neocortex-eval-fixtures`

Created test fixtures for Phase 2 eval test migration:

| Fixture | Purpose |
|---------|---------|
| eval-characters.yaml | Baseline character data: drives + formation memories for 4 characters |
| eval-characters-generic.yaml | Generic profile (no pop-culture refs) for same characters |
| EvalCharacterData | Simplified SocialConfig record (drives + formation memories only) |
| EvalCharacterLoader | YAML loader for eval character data |
| CognitionCoreTestBuilder | Builds CognitionCore without agency deps (no-op MemoryHygiene) |
| CognitiveDeltaCapture | Tick-level section delta tracking utility |

**Key design decisions:**
- Tests are plain JUnit 5 (no `@QuarkusTest`). Library modules can't host full Quarkus apps.
- `EvalTestSupport` builds Claude backend + SessionPipeline programmatically (in #698).
- `CognitionCoreTestBuilder` replaces manor's `CognitiveActivationTest.buildCore()` with no-op stubs for agency-dependent MemoryHygieneOrchestrator (avoids circular neocortex→agency dep).
- Both branches modify parent pom (dependencyManagement) independently; merge will reconcile.

### Commits

```
# Branch issue-698-move-zero-dep-eval-tests
bcf93fb0 feat(#698): move zero-dep eval tests from wacky-manor to caps-llm-classifier

# Branch issue-699-neocortex-eval-fixtures
d94159a0 wip: extract character data fixtures for eval tests
8bf4af78 feat(#699): create neocortex eval test fixtures
```

## What the next session must do

### 1. Remove migrated tests from wacky-manor

Once #698 is reviewed and merged, delete the 4 original tests from examples.

### 2. Move Phase 2 eval tests (#700)

Blocked by #699. Once fixtures merged, migrate CognitiveEvalTest, EmergenceVerificationTest, SleepDerivationEvalTest, SomaticDescriptionEvalTest — replacing ManorSocialConfigLoader with EvalCharacterLoader and CognitiveActivationTest with CognitionCoreTestBuilder.

### 3. Extract CognitionObservationBuilder (#701)

Independent architectural work. Extract generic observation rendering from CharacterCognition into neocortex/cognition. Unblocks Phase 3 (#702).

## Test status

- caps-llm-classifier unit tests: 13 pass on both branches
- Both branches: BUILD SUCCESS (test-compile)
