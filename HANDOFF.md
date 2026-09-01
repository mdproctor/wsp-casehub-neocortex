# HANDOFF — casehub-neocortex

## Last Session

Continued cognitive rearchitecture on `issue-253-cognitive-rearchitecture`. Completed #247 (YAML schema conventions) and #248 (Cognitive profile YAML). Queue position 20→22 of 25.

### Completed

1. **#247 — YAML schema conventions** (M): Established comprehensive YAML schema conventions for all cognitive types (D65-D73). Created new `schema-generator` Maven module with 4 classes: `SealedHierarchyModule` (sealed interface → oneOf + const discriminator via victools 4.38.0), `EnumInliningModule` (inline enum values), `ShorthandModule` (scalar-or-object for Confidence/NodeRef/RecurrenceRule), `CognitiveSchemaGenerator` (wires all modules, Draft 2020-12, YAML output). 28 tests. Conventions doc promoted to `docs/specs/2026-09-01-yaml-schema-conventions.md`. Key conventions: camelCase keys (D65), `type` discriminator (D66), FeatureValue inference-first (D67), `@Named` SPI refs (D68), scalar-or-object shorthand (D69).

2. **#248 — Cognitive profile YAML** (M): `CognitiveDefaults` aggregate record in cognitive-index — per-agent YAML config for personality weights, mood baseline, curiosity, temporal focus, vocabulary, and named SPI references. `CognitiveDefaultsRegistry` CDI bean with classpath scan (`cognitive-profiles/*.yaml`) and runtime lookup by agentId. `PersonalityWeightsDeserializer` for MemoryDomain key wrapping. 10 tests. **Moved `CuriosityConfig` from mindmap-intelligence to mindmap-api** to break cyclic dependency — it's a pure record that belongs in the API tier. Decisions D74-D79.

### Key Design Decisions

**D65 — camelCase for YAML keys.** Platform-consistent with engine (`topK`, `caseType`) and eidos (`agentId`, `tenancyId`).

**D66 — `type` as sealed hierarchy discriminator.** Standard JSON Schema / Jackson convention. None of the 8 sealed hierarchies have a semantic `type` property that would collide.

**D74 — Separate cognitive profile YAML, agentId join key.** Zero coupling between neocortex and eidos. Composes via shared `agentId`.

**D76 — CognitiveDefaults naming.** Avoids collision with existing `CognitiveProfile` (runtime entity resolver). "Defaults" = baseline parameters that runtime deviates from.

### Architectural Change

**CuriosityConfig moved from mindmap-intelligence to mindmap-api.** mindmap-intelligence already depended on cognitive-index, so cognitive-index couldn't depend on mindmap-intelligence (cycle). CuriosityConfig is a zero-dep pure record with `defaults()` factory — belongs in the API tier. All 174 tests (cognitive-index 110 + mindmap-intelligence 70) pass with no regressions. `import io.casehub.neocortex.mindmap.CuriosityConfig` replaces `import io.casehub.neocortex.mindmap.intelligence.CuriosityConfig`.

## What's Next

| # | Title | Scale | Complexity | Notes |
|---|-------|-------|------------|-------|
| 249 | Declarative rule DSL | M | High | Next up — YAML trait rules + derived edge rules. The highest-complexity remaining issue. #247 §11 establishes @Named convention; #249 extends to inline rule expressions. |
| 250 | YAML-to-Java compiler | L | High | Build-time/startup YAML→CDI loader. Blocked by #248, #249 |
| 251 | Identity-cognition derivation | M | High | AgentDescriptor→CognitiveDefaults. Blocked by #248 (done) |

## Branch State

- Branch: `issue-253-cognitive-rearchitecture`
- All tests pass (cognitive-index 110, mindmap-intelligence 70, schema-generator 28, full build green)
- No uncommitted changes in project repo
- New module: `schema-generator/` (4 classes, 28 tests)
- New classes in cognitive-index: `CognitiveDefaults`, `CognitiveDefaultsRegistry`, `PersonalityWeightsDeserializer`
- Specs: `2026-09-01-yaml-schema-conventions-design.md`, `2026-09-01-cognitive-defaults-design.md`
