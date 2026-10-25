# Session Handover — neocortex (slot 196)

**Date:** 2026-10-25
**Branch:** `issue-698-move-zero-dep-eval-tests`
**Epic:** casehubio/neocortex#697 — Migrate neocortex eval tests from wacky-manor

## What was done (this session)

### Move zero-dep eval tests to caps-llm-classifier (casehubio/neocortex#698)

Migrated 4 LLM eval tests from `casehubio/examples` wacky-manor `experiment/` to neocortex `caps-llm-classifier/src/test/java/.../eval/`:

| Test | Manor deps replaced |
|------|-------------------|
| ChannelWeightingEvalTest | None (direct move) |
| ClassifierModelComparisonTest | None (direct move) |
| SituationClassifierIntegrationTest | None (direct move) |
| BehavioralAttractorEvalTest | AgentResponse → ThinkingDialogueResponse; CharacterAgentLoop.RESPONSE_FORMAT_INSTRUCTION → inline; LlmTestSupport removed (unused) |

**Key design decision:** Tests are plain JUnit 5 (no `@QuarkusTest`) with manual infrastructure construction via `EvalTestSupport`. Library modules can't host full Quarkus applications, so CDI injection doesn't work. `EvalTestSupport` builds `ClaudeAgentClient` → `ClaudeAgentProvider` → `AgentProvider` adapter and `SessionPipeline` programmatically.

**Build integration:**
- Tests tagged `@Tag("llm-eval")`, excluded from default builds
- `llm-eval` Maven profile enables them: `mvn test -Pllm-eval -pl caps-llm-classifier`
- Test deps added: caps-engine, cognition, platform-agent-claude, platform-agent-gate (all test scope)
- Parent pom: added platform-agent-claude and platform-agent-gate to dependencyManagement

### Commits

```
bcf93fb0 feat(#698): move zero-dep eval tests from wacky-manor to caps-llm-classifier
```

## What the next session must do

### 1. Remove migrated tests from wacky-manor

The 4 tests still exist in `casehubio/examples` wacky-manor `experiment/` package. Once #698 is reviewed and merged, delete them from examples and update wacky-manor's test counts.

### 2. Continue epic #697 — parallel tracks

Three tracks can proceed independently:
- **#699** — Create neocortex eval test fixtures (unblocks #700 Phase 2)
- **#701** — Extract CognitionObservationBuilder from CharacterCognition (unblocks #702 Phase 3)
- **#700** — Move fixture-dep eval tests (blocked by #699)

## Test status

- caps-llm-classifier unit tests: 13 pass (existing), eval tests excluded
- caps-llm-classifier test-compile: BUILD SUCCESS (8 test files compile)
