# HANDOFF — casehub-neocortex

## Current Session (2026-11-18)

**Shadow archetype chain scaffolded — 8 issues queued, #1068 active.**

This session completed 4 issues from the prior queue (bug fixes + CDI wiring), then scaffolded the shadow archetype / CARMA continuation work.

### What was completed

| # | Issue | Type | What |
|---|-------|------|------|
| #1132 | LivedDispositionSource | feat | Implemented `EidosLivedDispositionSource` — surfaces evolved personality to eidos `findEffective()`. Extracted `livedDisposition()` from `livedDescriptor()` to work at `AgentDisposition` level. Fixed latent bug where `livedDescriptor` dropped `ampdFacets` and `situationalProfiles`. |
| #1082 | Wire SituationalPersonalityParticipant | feat | Added `situationalPersonalityEnabled` to `CognitionConfig` (27th field). CDI producers for `SituationalPersonalityConfig` (YAML) and `SituationalDetector`. `configureSituationalPersonality()` in `CognitionCore` with AppraisalAccessor/MoodAccessor adapters. Wired through builder and factory. Gated, default false. |
| #1135 | AMPD facet composition | feat | `composeFacets()` on `EidosCognitiveProfileBridge` — projects resting facet evolution (homeOffset + promoted, no transient displacement) into `AgentDisposition.ampdFacets` for `findEffective()`. |
| #1138 | Cap narrative field length | fix | One-line `cap(narrative, MAX_DESCRIPTION_LENGTH)` in `CopingGenerationPhase.parseResponse()`. |

All 4 committed to main. 4 done items in queue pending `work end` close ceremony from prior batch (#1132, #1082, #1135, #1138).

### Queue — shadow archetype chain (8 items, position 1/8)

| Pos | # | Title | Scale | Complexity | Notes |
|-----|---|-------|-------|------------|-------|
| 1 | #1068 | LlmAppraisalStrategy situational facet prompt clause | XS | Low | **Active.** Unblocked (#1055 closed). Quick win. |
| 2 | #1084 | PipelineTrace SituationalPersonalitySnapshot | S | Low | Observability: surface detection results in trace |
| 3 | #1083 | RelationalSchemaResolver trust signal | S | Med | Replaces hardcoded trust=0.0 in participant |
| 4 | #1059 | CARMA SEC situational-mode context + ShadowArchetypePromptSection | S | Med | AppraisalContext mode field + explicit rendering |
| 5 | #1056 | Biographical extraction of situational profiles | M | Med | Extraction pass → engram AMPD delta scale |
| 6 | #1058 | Shadow narrative frame: attractor classification | M | High | BehavioralSynthesisPhase attractor annotation |
| 7 | #1057 | Temporal archetype salience across life phases | M | High | Open design questions |
| 8 | #1076 | PID-5 facet extension for situational attractors | M | High | 12 missing facets; literature review |

Items 1-4 are small independent pieces. Items 5-6 form the core shadow narrative frame. Items 7-8 are research-heavy and may warrant brainstorming.

### Key context for the implementing session

**All blockers resolved.** eidos#234 (SituationalProfile on AgentDisposition), #1055 (EffectiveCognitiveDefaults), #712 runtime, and #1082 (CDI wiring, done this session) are all closed.

**Pre-existing test failure.** `DispositionSignalWriterTest` in the cognition module has a compile error — `InMemorySignalStore` doesn't implement `activationWeights()` from a changed `DispositionSignalStore` SPI in eidos. Not caused by this session's work. Fix before running full cognition test suite.

**CognitionConfig is now 27 fields.** The `with()` switch has 27 cases. Adding more fields follows the same pattern — append to record, update `all()`/`withAllSubsystems()`/`none()`, add case.

### Branch and workspace state

- **Project repo** (`neocortex`): on `main`, 6 commits ahead of `local/main` (2 from #1132/#1135 cognitive-eidos, 2 from #1082 CognitionConfig + wiring, 1 from #1135 facets, 1 from #1138 cap fix)
- **Workspace repo** (`wsp-casehub-neocortex`): on `issue-1130/cdi-wiring-personality-state-integrator`, queue has 8 new items + 4 done pending close

## Prior Sessions

**2026-11-17/18:** #1060 design — unified personality evolution. Brainstorming, adversarial review (4 dimensions), 14-task plan. No code written. Plan at `wsp/plans/2026-11-18-unified-personality-evolution.md`.

**Earlier:** Epic #1090 bug fix sweep — 7 issues resolved. Prior queue of 24 items fully drained across multiple sessions.
