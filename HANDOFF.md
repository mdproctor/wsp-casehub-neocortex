# HANDOFF — casehub-neocortex

## Last Session

Continued cognitive rearchitecture on `issue-253-cognitive-rearchitecture`. Completed #249 (batch 3), #250, #251. Created 6 new issues (#256–#261) for remaining derivation connection points. Queue position 25→31 (25 done, 6 new).

### Completed

1. **#249 — Declarative rule DSL** (L, final batch): YAML deserializers (RuleConditionDeserializer, DeclarativeTraitRuleDeserializer, DeclarativeDerivedEdgeRuleDeserializer) in cognitive-index. DeclarativeRuleRegistry (@ApplicationScoped) loads global `rules/*.yaml` + per-agent overrides with name-based merge. DerivedEdgeDecorator CDI constructor gains `Instance<DeclarativeRuleRegistry>`. CognitiveDefaults extended with traitRules + derivedEdgeRules nullable fields. Architecture deviation: deserializers placed in cognitive-index (not mindmap-intelligence per spec) to avoid circular dependency — mindmap-intelligence → mindmap → cognitive-index works, but mindmap → mindmap-intelligence would be circular.

2. **#250 — YAML-to-Java compiler** (L→S actual): Most work already done by #249. CognitiveDefaultsRegistry and DeclarativeRuleRegistry gain @ApplicationScoped + @PostConstruct. TraitApplicationDecorator gains `Instance<DeclarativeRuleRegistry>` (mirrors DerivedEdgeDecorator). CognitiveLoader @ApplicationScoped in mindmap-intelligence — @PostConstruct vocabulary registration from cognitive profiles. `DeclarativeRuleRegistry.of()` public factory for programmatic construction.

3. **#251 — Identity-cognition derivation** (M): DescriptorView, DispositionAxes, WeightedTerm records in cognitive-index — zero eidos compile dependency. CognitiveDerivationEngine pure static utility: Jungian disposition profile → PersonalityWeights (8-function weighted average), disposition axes → MoodBaseline (PAD). `deriveAndMerge()` overlays explicit CognitiveDefaults overrides on derived base. CognitiveDefaults gains `descriptor` nullable field for embedded identity-cognition derivation.

### Key Design Decisions

**D85 — Deserializers in cognitive-index, not mindmap-intelligence.** The spec placed them in mindmap-intelligence, but CognitiveDefaultsRegistry (in cognitive-index) needs them to parse traitRules/derivedEdgeRules in cognitive profile YAML. mindmap-intelligence → mindmap → cognitive-index prevents reverse dependency.

**D86 — DeclarativeRuleRegistry.of() public factory.** Package-private test constructor wasn't accessible from mindmap module tests. Public static factory `of(traitRules, derivedEdgeRules)` provides programmatic construction without CDI.

**D87 — CognitiveDerivationEngine weighted average.** Disposition profile → PersonalityWeights uses weighted average across all functions in the profile, defaulting to 1.0 (neutral) for domains not mentioned by a function. This ensures blending: Ni at 0.35 + Te at 0.30 → reflection gets Ni's 1.5 weighted by 0.35 and Te's 1.0 weighted by 0.30.

### Architectural Changes

- **New in cognitive-index:** RuleConditionDeserializer, DeclarativeTraitRuleDeserializer, DeclarativeDerivedEdgeRuleDeserializer, RuleFile, DeclarativeRuleRegistry (@ApplicationScoped), DescriptorView, DispositionAxes, WeightedTerm, CognitiveDerivationEngine
- **New in mindmap-intelligence:** CognitiveLoader (@ApplicationScoped)
- **Modified:** CognitiveDefaults (+traitRules, +derivedEdgeRules, +descriptor), CognitiveDefaultsRegistry (@ApplicationScoped, +@PostConstruct, +rule deserializers), DerivedEdgeDecorator (+Instance<DeclarativeRuleRegistry>), TraitApplicationDecorator (+Instance<DeclarativeRuleRegistry>)
- **New dependency edge:** mindmap → cognitive-index (for DeclarativeRuleRegistry injection)

### Issues Created

| # | Title | Scale | Complexity | Notes |
|---|-------|-------|------------|-------|
| 256 | Derive curiosity direction | S | Low | disposition axes + goals → CuriosityConfig category weights |
| 257 | Derive prospective focus | S | Low | goals → TemporalFocusConfig subgraph proximity weights |
| 258 | Derive CBR strategy defaults | M | Med | ruleFollowing + riskAppetite → CbrQuery defaults |
| 259 | Derive social cognition config | M | Med | socialOrient + conflictMode → trust/conflict config. Needs design. |
| 260 | Derive graph structure preference | M | Med | disposition profile → disposition-gated derived edge rules |
| 261 | Derive extraction bias | L | High | disposition → MindMapExtractor prompt biasing. Needs design — LLM prompt engineering. |

## What's Next

| # | Title | Scale | Complexity | Notes |
|---|-------|-------|------------|-------|
| 256 | Derive curiosity direction | S | Low | Pure config derivation — extend CuriosityConfig + derivation engine |
| 257 | Derive prospective focus | S | Low | Pure config derivation — extend TemporalFocusConfig + derivation engine |
| 258 | Derive CBR strategy defaults | M | Med | New CbrStrategyDefaults config record needed |
| 259 | Derive social cognition config | M | Med | **Needs design** — conflict interpretation → runtime behaviour mapping |
| 260 | Derive graph structure preference | M | Med | Disposition-gated rule activation via DeclarativeRuleRegistry |
| 261 | Derive extraction bias | L | High | **Needs design** — LLM prompt engineering, not pure config |

Recommended order: 256, 257 (quick wins) → 258, 260 (mechanical M) → 259 (needs design) → 261 (needs design + LLM integration).

## Branch State

- Branch: `issue-253-cognitive-rearchitecture`
- Full reactor build green (compile). 156 cognitive-index tests pass.
- No uncommitted changes in project repo
- Blog entry: `blog/2026-09-02-mdp01-from-three-stores-to-one-mind.md` (workspace)
