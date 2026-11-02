# HANDOFF — casehub-neocortex

## Last Session (2026-11-02)

Designed #753 (cognitive-eidos bridge). Full brainstorming → spec → plan cycle completed. No implementation yet — plan is ready to execute.

**Design:** New `cognitive-eidos/` module in neocortex. `EidosCognitiveProfileBridge` (@ApplicationScoped) reads eidos `AgentDescriptor` instances at startup, converts to `DescriptorView`, calls `CognitiveDerivationEngine.derive()`, registers with `CognitiveDefaultsRegistry.register()`. All 10 derivation pathways fire automatically — personality weights, mood baseline, curiosity, CBR strategy, social cognition, graph structure, extraction bias, appraisal weights, habituation, temporal focus.

**Memory modulation:** Route `AgentExperienceService.recall()`, `recallRelationships()`, `recallReflections()` through `CognitiveMemoryRetriever` (cross-repo in casehub-mosaic slot 207). Personality weights modulate domain scoring.

**Key decisions (D6-D9):** Reusable module (not app-level wiring), runtime derivation (not YAML generation), all recall modulated, inject eidos provider directly via CDI.

## Immediate Next Step

Execute the implementation plan: `plans/2026-11-02-cognitive-eidos-bridge.md`. Three batches:
1. Create `cognitive-eidos/` module with `EidosCognitiveProfileBridge` + tests (neocortex)
2. Route recall through `CognitiveMemoryRetriever` (casehub-mosaic slot 207)
3. Verification — personality differentiation across derivation pathways

Use `executing-plans` (sequential, not SDD).

**Note:** `AgentQuery.all()` API needs confirmation at implementation time — eidos-api discovery method may differ. Check `AgentQuery` for the correct broad-query factory.

## References

- `specs/issue-758-pipeline-wiring-and-corpus/2026-11-02-cognitive-eidos-bridge-design.md` — design spec
- `specs/issue-758-pipeline-wiring-and-corpus/decisions.md` — D6-D9 decisions
- `plans/2026-11-02-cognitive-eidos-bridge.md` — implementation plan
- `blog/2026-11-02-mdp04-sixteen-characters-one-mind.md` — diary entry
