# HANDOFF — casehub-neocortex

## Last Session

Closed blocks#299 (SocialAvatarCognition CDI wiring for CognitiveGoalOrchestrator, S/Low). Refactored SocialAvatarCognition from a 10-param constructor to a builder pattern. Builder constructs CognitiveGoalOrchestrator when MindMapStore + GoalAppraisal + CaseMemoryStore are all available (graceful degradation via CDI Instance/Optional). Extended CognitionCompiler with compileCognitiveGoal(). Updated both Quarkus (BlocksBeans) and Spring (BlocksAutoConfiguration) producers.

## Immediate Next Step

Pick up blocks#300 (GoalRevision decay-signal, XS/Low) — the last prerequisite before the XL migration (blocks#303).

## Cross-Module

- blocks#303 (XL/High) — migrate cognitive state to neocortex. Blocked by blocks#300.
- blocks-core has a pre-existing build failure: CognitiveSystemPromptRenderer references AgentVoiceProfile/voice() from eidos-api, but that type doesn't exist in eidos yet.
- blocks#302 (mood congruence) — still open, batch 4 of the cognitive emotion epic.
- blocks#308 (L/High) — context-budget prompt rendering, still open.
