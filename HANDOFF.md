# HANDOFF — casehub-neocortex

## Last Session

Continued cognitive rearchitecture on `issue-253-cognitive-rearchitecture`. Completed #247 (YAML schema conventions), #248 (Cognitive profile YAML), and #249 batches 1-2 of 3 (declarative rule DSL — condition + action models). Queue position 20→22 of 25.

### Completed

1. **#247 — YAML schema conventions** (M): New `schema-generator` module with SealedHierarchyModule (sealed → oneOf + const discriminator), EnumInliningModule, ShorthandModule (Confidence/NodeRef/RecurrenceRule), CognitiveSchemaGenerator. 28 tests. Conventions doc promoted to `docs/specs/2026-09-01-yaml-schema-conventions.md`. Decisions D65-D73.

2. **#248 — Cognitive profile YAML** (M): `CognitiveDefaults` aggregate record + `CognitiveDefaultsRegistry` (classpath scan `cognitive-profiles/*.yaml`, runtime lookup by agentId) + `PersonalityWeightsDeserializer` in cognitive-index. 10 tests. Moved `CuriosityConfig` from mindmap-intelligence to mindmap-api to break cyclic dependency. Decisions D74-D79.

3. **#249 — Declarative rule DSL** (L, in progress): Batches 1-2 of 3 complete.
   - Batch 1: `RuleCondition` sealed interface (11 structural predicates: hasProperty, propertyEquals, propertyIn, notHasProperty, hasEdgeType, hasEdgeTypes, hasAnyEdge, inSubgraphType, anyOf, allOf, not) + `DeclarativeTraitRule` in mindmap-api. 25 tests.
   - Batch 2: `EdgeDerivation` + `EdgeRef` + `TraversalSpec` + `DeclarativeDerivedEdgeRule` in mindmap-api. Two-level actions: Level 1 (direct inverse/flip), Level 2 (graph traversal with cycle prevention for transitive closure). 9 tests.
   - **Batch 3 remaining:** YAML deserializers (RuleConditionDeserializer), DeclarativeRuleRegistry CDI bean (global + per-agent merge), DerivedEdgeDecorator modification (`Instance<DeclarativeRuleRegistry>`), CognitiveDefaults extension (traitRules + derivedEdgeRules fields). Touches mindmap-intelligence, mindmap, cognitive-index, CLAUDE.md.

### Key Design Decisions

**D80 — Complete structural predicate set.** 11 predicates, not 5. A regular API prevents users from dropping to Java for trivial conditions like negation.

**D81 — Two-level derived edge actions.** Direct (inverse/flip) + traversal (transitive closure via TraversalSpec). The traverse block is declarative — says WHAT to follow, not HOW to query.

**D83 — Global rules + per-agent overrides.** Global rules in `rules/*.yaml`, per-agent in `cognitive-profiles/*.yaml`. Name collision = local wins.

**D84 — DeclarativeRuleRegistry.** CDI bean merges global + per-agent rules. DerivedEdgeDecorator gains `Instance<DeclarativeRuleRegistry>` alongside existing `Instance<DerivedEdgeRule>`.

### Architectural Changes

- **CuriosityConfig moved:** `mindmap-intelligence` → `mindmap-api` (pure record, broke cyclic dep)
- **New module:** `schema-generator/` (4 classes, 28 tests)
- **New in mindmap-api:** `RuleCondition`, `DeclarativeTraitRule`, `EdgeDerivation`, `EdgeRef`, `TraversalSpec`, `DeclarativeDerivedEdgeRule`, `TestNode`, `TestEdge`, `StubMindMapStore` (test stubs)
- **New in cognitive-index:** `CognitiveDefaults`, `CognitiveDefaultsRegistry`, `PersonalityWeightsDeserializer`

## What's Next

| # | Title | Scale | Complexity | Notes |
|---|-------|-------|------------|-------|
| 249 | Declarative rule DSL | L | High | **Batch 3 remaining** — YAML deserializers + DeclarativeRuleRegistry + DerivedEdgeDecorator mod + CognitiveDefaults extension. Plan: `plans/2026-09-02-declarative-rule-dsl.md`, Task 3. Spec review running at `/Users/mdproctor/reviews/casehub-neocortex/issue-249-rule-dsl-spec-20260902-091218/`. |
| 250 | YAML-to-Java compiler | L | High | Blocked by #249 |
| 251 | Identity-cognition derivation | M | High | Blocked by #248 (done) |

## Branch State

- Branch: `issue-253-cognitive-rearchitecture`
- All tests pass (full reactor build green)
- No uncommitted changes in project repo
- Specs: `2026-09-01-yaml-schema-conventions-design.md`, `2026-09-01-cognitive-defaults-design.md`, `2026-09-02-declarative-rule-dsl-design.md`
- Plans: `2026-09-01-yaml-schema-conventions.md`, `2026-09-01-cognitive-defaults.md`, `2026-09-02-declarative-rule-dsl.md`
