## D1: Cognitive types as compositional traits, not exclusive subgraph types

**Choice:** Option C — compositional traits + type hierarchy metadata + unified subgraph
**Alternatives:**
- Option A (subtypes + separate subgraphs) — forces exclusive classification, loses compositionality. A "prediction that is also a fear" can only live in one subgraph. 6 micro-subgraphs produce noisy DomainActivation signals with few nodes each.
- Option B (property-based traits only, no TypeRegistry) — no type hierarchy metadata, no schema derivation via java-class, no `subtypesOf()` queries. Ad-hoc compositionality without structural support.
**Rationale:** Cognitive types (belief, intention, prediction, judgment, fear, desire) are overlapping aspects of mental representations, not exclusive categories. "The servers will crash" is simultaneously a prediction, a belief, and a fear. The architecture's type/trait duality already handles this — types for structural placement (exclusive), traits for behavioral classification (compositional). Follows the Eventlike + Threatening/Aspirational pattern at the correct abstraction level: shared subgraph + compositional traits with richer per-type schemas via trait interfaces.
**Trade-offs:** Loses per-type subgraph isolation — consolidation must filter by trait/property rather than targeting a subgraph. DomainActivation cannot compute separate "belief trajectory" vs "intention trajectory" at the subgraph level (would need trait-based filtering, which is a future enhancement).
**Sources:** TypeRegistry.java, TraitRule.java, MindMapExtractor.java, ThreateningTraitRule.java, RuleCondition.java, DeclarativeRuleRegistry.java
**Exploration:** deep-analysis
**Status:** captured

## D2: Subgraph placement — stay in CONCEPT

**Choice:** Cognitive nodes live in the existing CONCEPT subgraph
**Alternatives:**
- New COGNITIVE subgraph type — separates propositional attitudes from abstract concepts. Adds a constant to SubgraphTypes + TypeRegistry bootstrap for a philosophy-of-mind distinction with no practical benefit at v1.
**Rationale:** Concepts and cognitive representations are closely related. Consolidation targets by trait, not subgraph. Trait-filtered analysis is the right path for cognitive-specific trajectories if needed later.
**Trade-offs:** CONCEPT subgraph becomes a mix of abstract ideas and mental representations. If the distinction matters for downstream consumers, they filter by trait.
**Sources:** SubgraphTypes.java, TypeRegistry.java (createCoreTypesIfAbsent)
**Exploration:** quick
**Depends on:** D1 (compositional traits — subgraph is structural, traits handle classification)
**Status:** captured

## D3: Trait interface properties — minimal infrastructure-level schemas

**Choice:** Six trait interfaces with 2 properties each, all `Optional<String>`:
- Belieflike: subject, revised
- Intentional: goal, viable
- Predictive: timeframe, validated
- Evaluative: target, stance
- Fearful: threat, severity
- Desirous: aspiration, fulfilled
**Alternatives:**
- Richer schemas with 4-6 properties per type — more expressive but crosses into application-level concerns. Consumers can always add custom properties without schema changes.
- Single shared CognitiveLike interface with all fields — god interface anti-pattern, loses per-type schema derivation.
**Rationale:** Follows the established pattern (Personable: 4 fields, Eventlike: 4 fields, Organisational: 3 fields). Properties must be meaningful at the infrastructure level (consolidation lifecycle), extractable by LLM, and not application-specific. Boolean-like fields are strings because the property store is Map<String, String>.
**Trade-offs:** Intentionally thin — applications needing richer schemas add custom properties to nodes directly, outside the trait interface.
**Sources:** Personable.java, Eventlike.java, Projectlike.java, Organisational.java
**Exploration:** quick
**Depends on:** D1 (trait interfaces are the compositional axis)
**Status:** captured

## D4: Trait rule delivery — programmatic + declarative (layered)

**Choice:** Both programmatic Java rules AND declarative YAML rules
**Alternatives:**
- Programmatic only — no per-agent customization, no secondary compositional inference without Java code changes
- Declarative YAML only — no compile-time guarantee that baseline rules exist, inconsistent with every existing trait rule in the codebase (all are programmatic @ApplicationScoped)
**Rationale:** The two mechanisms serve different purposes in the existing layered architecture. Programmatic rules (6 @ApplicationScoped classes) provide the non-negotiable baseline: `cognitiveKind=X → X-like trait`. Declarative YAML rules (in `rules/cognitive-traits.yaml`) provide secondary compositional inference (e.g., has `timeframe` → also Predictive) and per-agent customization via cognitive profiles. No conflict risk — trait assignment is idempotent (traits are a Set).
**Trade-offs:** More artifacts (6 Java classes + YAML file) than either approach alone. Acceptable because each layer has a distinct purpose.
**Sources:** PersonableTraitRule.java, ThreateningTraitRule.java, DeclarativeRuleRegistry.java, DeclarativeTraitRule.java, RuleCondition.java, alice.yaml (cognitive profile with per-agent traitRules)
**Exploration:** quick
**Depends on:** D1 (trait rules are the classification mechanism), D3 (properties determine what rules match on)
**Status:** captured

## D5: TypeRegistry registration in CognitiveLoader

**Choice:** Register cognitive types as subtypes of `concept` in CognitiveLoader's @PostConstruct, alongside existing vocabulary registration
**Alternatives:**
- TypeRegistry.createCoreTypesIfAbsent() — makes cognitive types look foundational when they're domain intelligence. Tighter coupling.
- New CognitiveTypeBootstrap bean — single responsibility but a new class for 10 lines of registerType() calls.
**Rationale:** CognitiveLoader already owns cognitive bootstrap lifecycle. Instance<MindMapStore> graceful degradation already wired. Adding registerType() calls next to registerVocabulary() is natural and keeps all cognitive bootstrap in one place.
**Trade-offs:** CognitiveLoader gains a second responsibility (type registration + vocabulary registration). Acceptable — both are cognitive bootstrap concerns.
**Sources:** CognitiveLoader.java, TypeRegistry.java (registerType method)
**Exploration:** quick
**Depends on:** D1 (types registered as metadata), D2 (subtypes of concept)
**Status:** captured
