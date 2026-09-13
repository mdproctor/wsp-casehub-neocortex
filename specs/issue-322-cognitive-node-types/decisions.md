## D1: Cognitive types as compositional traits, not exclusive subgraph types

**Choice:** Option C — compositional traits + type hierarchy metadata + unified subgraph
**Alternatives:**
- Option A (subtypes + separate subgraphs) — forces exclusive classification, loses compositionality. A "prediction that is also a fear" can only live in one subgraph. 6 micro-subgraphs produce noisy DomainActivation signals with few nodes each.
- Option B (property-based traits only, no TypeRegistry) — no type hierarchy metadata, no schema derivation via java-class, no `subtypesOf()` queries. Ad-hoc compositionality without structural support.
**Rationale:** Cognitive types (belief, intention, prediction, judgment, fear, desire) are overlapping aspects of mental representations, not exclusive categories. "The servers will crash" is simultaneously a prediction, a belief, and a fear. The architecture's type/trait duality already handles this — types for structural placement (exclusive), traits for behavioral classification (compositional). Follows the Eventlike + Threatening/Aspirational pattern at the correct abstraction level: shared subgraph + compositional traits with richer per-type schemas via trait interfaces.
**Overlap with Eventlike-derived traits:** Cognitive traits and Eventlike-derived traits (Threatening, Aspirational, Opportunistic) operate on different property discriminators. Cognitive traits match on `cognitiveKind`; Eventlike traits match on `eventKind` + `eventValence`. A node that carries BOTH property sets (e.g. a fear that is also modeled as an anticipated event) correctly receives both trait sets — this is compositionality working as designed. The two classification systems are complementary, not redundant: cognitive traits classify propositional attitude type, Eventlike traits classify event characteristics.
**Trade-offs:** Loses per-type subgraph isolation — consolidation must filter by trait/property rather than targeting a subgraph. DomainActivation cannot compute separate "belief trajectory" vs "intention trajectory" at the subgraph level (would need trait-based filtering, which is a future enhancement).
**Sources:** TypeRegistry.java, TraitRule.java, MindMapExtractor.java, ThreateningTraitRule.java, RuleCondition.java, DeclarativeRuleRegistry.java
**Exploration:** deep-analysis
**Status:** captured

## D2: Subgraph placement — dedicated COGNITIVE subgraph

**Choice:** Cognitive nodes live in a new COGNITIVE subgraph, separate from CONCEPT
**Alternatives:**
- Stay in CONCEPT subgraph — simpler (no new constant), but consolidation phases operate per-subgraph and would incorrectly compare cognitive nodes with abstract concepts. MergeDetectionPhase's Jaro-Winkler comparison would flag belief nodes against concept nodes with similar names. CommunitySummaryPhase's k-core clustering would produce incoherent communities mixing concepts with propositional attitudes. DomainActivation's per-subgraph affect trajectories would conflate concept-related and belief-related signals.
- Per-cognitive-type subgraphs (BELIEF, INTENTION, FEAR, etc.) — too granular. Rejected by D1 as Option A: loses compositionality, produces noisy DomainActivation signals with few nodes each.
**Rationale:** The existing architecture uses subgraph as the first level of structural separation (PERSON vs PROJECT vs CONCEPT), with traits providing the second level of behavioral classification within subgraphs. A single COGNITIVE subgraph follows this pattern: subgraph separates cognitive content from non-cognitive content, traits distinguish beliefs from fears from intentions within the cognitive subgraph. MergeDetectionPhase, CommunitySummaryPhase, and DomainActivation all operate per-subgraph — a dedicated subgraph immediately protects cognitive nodes from incorrect cross-type processing without requiring any changes to those phases. The cost is one string constant in SubgraphTypes and one registerType() call.
**Trade-offs:** COGNITIVE subgraph must reach sufficient density for CommunitySummaryPhase k-core clustering and DomainActivation trajectory analysis to produce meaningful results. In early adoption, low node counts per subgraph may produce sparse signals.
**Sources:** SubgraphTypes.java, ConsolidationScheduler.java, MergeDetectionPhase.java, CommunitySummaryPhase.java, DomainActivation.java
**Exploration:** quick → revised after review
**Depends on:** D1 (compositional traits — subgraph is structural, traits handle classification)
**Status:** revised (R1-02: reviewer demonstrated that consolidation phases operate per-subgraph and CONCEPT placement produces incorrect merge detection and incoherent community summaries)

## D3: Trait interface properties — status-consistent schemas with platform naming

**Choice:** Six trait interfaces with 3 properties each, using `status` for lifecycle state (consistent with Eventlike/Projectlike pattern), `Optional<String>` throughout:
- Belieflike: subject, status (active|revised|contradicted), basis
- Intentionlike: goal, status (active|achieved|abandoned|blocked), priority
- Predictive: timeframe, status (pending|confirmed|refuted), basis
- Evaluative: target, stance, basis
- Fearlike: threat, severity, status (active|resolved|dismissed)
- Desirelike: aspiration, status (active|fulfilled|abandoned), urgency

Trait naming follows established conventions:
- `-like` suffix for noun-based types: Belieflike, Intentionlike, Fearlike, Desirelike (consistent with Eventlike, Projectlike)
- Adjectival form for verb-based types: Predictive, Evaluative (consistent with established pattern — these describe what the content does)
**Alternatives:**
- 2-property interfaces with boolean-like lifecycle fields (revised, viable, validated, fulfilled) — rejected: boolean markers don't match the established `status` pattern on Eventlike/Projectlike, and 2 properties is below the established minimum (Organisational has 3).
- Richer schemas with 4-6 properties per type — crosses into application-level concerns. Consumers can add custom properties without schema changes.
- Single shared CognitiveLike interface with all fields — god interface anti-pattern, loses per-type schema derivation.
- Original naming (Fearful, Desirous, Intentional) — Fearful means "full of fear" (describes the node as afraid, not as representing a fear). Desirous means "wanting something." These break the convention where trait names describe the entity category. Intentional is ambiguous (common English: "done on purpose" vs philosophy: "aboutness").
**Rationale:** 3 properties per interface matches the established floor (Organisational: 3). Using `status` with enum-like values (strings in the property store) follows the Eventlike/Projectlike pattern — lifecycle state expressed as a classifier, not a boolean marker. The `-like` suffix for noun-based cognitive types is consistent with Eventlike and Projectlike; adjectival forms for Predictive and Evaluative follow the established pattern of describing what the content does (predicts, evaluates). Third properties (`basis`, `priority`, `urgency`) serve infrastructure-level consolidation: `basis` enables contradiction detection, `priority`/`urgency` enable lifecycle ordering.
**Trade-offs:** Intentionally lean — applications needing richer schemas add custom properties to nodes directly, outside the trait interface. The `status` values per type must be documented as conventions, not enforced by the property store.
**Sources:** Personable.java, Eventlike.java, Projectlike.java, Organisational.java
**Exploration:** quick → revised after review
**Depends on:** D1 (trait interfaces are the compositional axis)
**Status:** revised (R1-03: reviewer identified lifecycle property naming as inconsistent with established pattern; R1-04: reviewer identified Fearful/Desirous/Intentional as breaking naming convention)

## D4: Trait rule delivery — declarative baseline + programmatic for complex matching

**Choice:** Declarative YAML rules for baseline cognitive trait assignment, programmatic Java rules reserved for complex matching logic
**Alternatives:**
- Programmatic only (6 @ApplicationScoped classes) — each would be a trivial single-PropertyEquals check (~130 lines total for no logic beyond what YAML handles in ~12 lines). Inconsistent with the declarative rule infrastructure built specifically for this purpose.
- Both programmatic AND declarative (original D4) — redundant. TraitApplicationDecorator.resolveRules() merges both sources; having a programmatic PropertyEquals("cognitiveKind", "belief") alongside a declarative PropertyEquals("cognitiveKind", "belief") is pure duplication.
**Rationale:** The DeclarativeRuleRegistry already loads YAML from the classpath `rules/` directory at @PostConstruct, merging global rules with per-agent cognitive profile rules. TraitApplicationDecorator.resolveRules() combines programmatic CDI beans with DeclarativeRuleRegistry rules — both participate identically in trait evaluation. The baseline cognitive rules are trivially simple (single PropertyEquals checks), matching the exact pattern DeclarativeTraitRule + RuleCondition.PropertyEquals was built for. A single `cognitive-traits.yaml` with 6 PropertyEquals rules provides the baseline. The claim that programmatic rules provide "compile-time guarantees" is misleading — CDI discovers beans at runtime, and a missing @ApplicationScoped annotation removes a rule as silently as a missing YAML file. Test coverage is the real guarantee, which works equally for both mechanisms. Complex matching logic (multi-property AND, edge-type checks) would justify programmatic rules — PersonableTraitRule's 4-property OR + 3-edge-type check legitimately earns its Java code. The baseline cognitive rules do not.
**Trade-offs:** Declarative rules lack IDE navigation from rule definition to trait usage. Developers must look at YAML to understand what triggers cognitive traits. Acceptable because the rules are trivially simple and self-documenting.
**Sources:** DeclarativeTraitRule.java, RuleCondition.java, DeclarativeRuleRegistry.java, TraitApplicationDecorator.java, PersonableTraitRule.java, ThreateningTraitRule.java
**Exploration:** quick → revised after review
**Depends on:** D1 (trait rules are the classification mechanism), D3 (properties determine what rules match on)
**Status:** revised (R1-05: reviewer demonstrated that baseline rules are trivially simple PropertyEquals checks and that the declarative infrastructure already handles this pattern)

## D5: TypeRegistry registration — COGNITIVE parent type in CognitiveLoader

**Choice:** Register a COGNITIVE parent type as a subtype of GENERAL, then register individual cognitive types (belief, intention, prediction, judgment, fear, desire) as subtypes of COGNITIVE. All registration in CognitiveLoader's @PostConstruct:
```
registerType("cognitive", "general", tenantId)   // COGNITIVE as sibling of CONCEPT
registerType("belief", "cognitive", tenantId)     // cognitive types under COGNITIVE
registerType("intention", "cognitive", tenantId)
...
```
Resulting type hierarchy:
```
GENERAL
├── PERSON
├── PROJECT
├── ORGANISATION
├── CONCEPT
├── RESEARCH_AREA
└── COGNITIVE
    ├── belief
    ├── intention
    ├── prediction
    ├── judgment
    ├── fear
    └── desire
```
**Alternatives:**
- Register cognitive types as subtypes of `concept` (original D5) — semantically contradicts D2. D2 establishes that cognitive content is fundamentally different from conceptual content (separate subgraph). But `subtypesOf("concept")` would return cognitive types, answering "what kinds of concepts exist?" with beliefs and fears. The RESEARCH_AREA precedent (sibling of CONCEPT, not subtype, despite research areas being arguable concept specializations) confirms: structural categories that warrant their own subgraph should be siblings in the type hierarchy, not children.
- Add COGNITIVE to `createCoreTypesIfAbsent()` in TypeRegistry — makes the COGNITIVE category foundational. Appropriate IF cognitive types are considered as structurally fundamental as PERSON or CONCEPT. Currently: cognitive types are domain intelligence bootstrapped by CognitiveLoader, not core infrastructure — keep registration in CognitiveLoader.
- New CognitiveTypeBootstrap bean — single responsibility but a new class for 10 lines of registerType() calls.
**Rationale:** The type hierarchy should encode classification semantics consistent with the subgraph model. `subtypesOf("concept")` should return concept specializations; `subtypesOf("cognitive")` should return cognitive types. D2's subgraph separation (COGNITIVE ≠ CONCEPT) must be reflected in the type hierarchy — otherwise downstream consumers that query `subtypesOf()` to understand type relationships will get semantically incorrect answers. CognitiveLoader already owns cognitive bootstrap lifecycle (vocabulary registration, graceful degradation via Instance<MindMapStore>). Adding the COGNITIVE parent type registration alongside individual type registrations keeps all cognitive bootstrap in one place.
**Trade-offs:** CognitiveLoader gains a second responsibility (type registration + vocabulary registration). Acceptable — both are cognitive bootstrap concerns. COGNITIVE as a type has no java-class association at v1 (a shared CognitiveLike super-interface was rejected in D3 as a god interface).
**Sources:** CognitiveLoader.java, TypeRegistry.java (registerType, createCoreTypesIfAbsent, subtypesOf)
**Exploration:** quick → revised twice after review
**Depends on:** D1 (types registered as metadata), D2 (COGNITIVE subgraph — type hierarchy must be consistent)
**Status:** revised (R1-08: removed overstated D2 dependency; R2-01: cognitive types registered under COGNITIVE parent instead of concept, aligning type hierarchy with subgraph model)

## D6: MindMapExtractor prompt — expand type list with separated routing

**Choice:** Add BELIEF|INTENTION|PREDICTION|JUDGMENT|FEAR|DESIRE to the extraction type list. Separate concerns: normalizeType() remains pure normalization (strip + lowercase). A new resolveSubgraphType(String normalizedType) method maps types to subgraphs. applyExtraction() sets `cognitiveKind` from the original extracted type independently of subgraph routing.
**Alternatives:**
- Original D6 (routing logic in normalizeType) — mixes normalization and classification concerns. normalizeType() must know which types are cognitive. Adding new cognitive types requires modifying normalizeType(). ExtractedEntity.subgraphType() loses the distinction between cognitive types.
- Separate `cognitiveKind` field in extraction schema — doubles classification burden on the LLM, risks inconsistency between type and cognitiveKind fields. More invasive change to ExtractionJsonParser.
**Rationale:** normalizeType() should remain pure: type.strip().toLowerCase(). resolveSubgraphType() handles the mapping from normalized type to target subgraph (cognitive types → COGNITIVE, person → PERSON, etc.). This keeps normalizeType() stable when new types are added and preserves the original extracted type information for downstream consumers. applyExtraction() can read the original type from the extraction result and set cognitiveKind as a property, independently of subgraph routing. ExtractedEntity retains the original classified type.
**Trade-offs:** Two methods instead of one for the type → subgraph path. Acceptable — each has a single responsibility.
**Sources:** MindMapExtractor.java (SYSTEM_PROMPT, normalizeType, applyExtraction), ExtractionJsonParser.java
**Exploration:** quick → revised after review
**Depends on:** D1 (cognitiveKind property is the discriminator), D2 (route to COGNITIVE subgraph)
**Status:** revised (R1-06: reviewer identified mixed normalization/routing concerns and loss of type information in ExtractedEntity)

## D7: Cognitive consolidation strategy

**Choice:** Cognitive nodes participate in the existing consolidation pipeline (MergeDetectionPhase, CommunitySummaryPhase, CuriosityRefreshPhase) within the COGNITIVE subgraph. Per-cognitive-type consolidation behaviors (beliefs revised on contradiction, predictions validated against outcomes, intentions checked for viability) are a follow-on concern that requires trait-aware consolidation phases — not addressed in this spec.
**Alternatives:**
- Skip consolidation entirely for cognitive nodes (exclude COGNITIVE subgraph from phases) — loses merge detection, community summaries, and curiosity signals for cognitive content.
- Implement trait-aware consolidation phases immediately — correct long-term design but scope creep for issue #322, which establishes the type system. Consolidation customization requires the types to exist first.
**Rationale:** Issue #322 establishes the cognitive type infrastructure (traits, interfaces, type hierarchy, extraction). The consolidation pipeline (#295) is already operational and will process the COGNITIVE subgraph using its existing phases. This provides useful baseline behavior: within-cognitive merge detection catches actual duplicates ("the servers will crash" extracted twice), community summaries provide clustering of related cognitive content, curiosity refresh identifies gaps. Per-type consolidation behaviors (the issue's stated goal of "beliefs get revised on contradiction, fears get evaluated against current state") require trait-filtered phases, which is a distinct engineering effort dependent on the type system existing first.
**Trade-offs:** v1 consolidation within COGNITIVE subgraph is type-unaware — it cannot distinguish beliefs from fears. MergeDetectionPhase may flag semantically similar but distinct cognitive nodes (e.g., two beliefs with similar subjects but different stances). This is acceptable at v1 because: (1) the merge threshold is conservative (autoMerge ≥ 0.9, flag ≥ 0.7), (2) cognitive nodes typically have more distinctive names than concepts, and (3) per-type phases are the next engineering step.
**Sources:** ConsolidationScheduler.java, MergeDetectionPhase.java, CommunitySummaryPhase.java, CuriosityRefreshPhase.java
**Exploration:** surfaced during review (R1-09)
**Status:** captured

## D8: LLM extraction can classify cognitive content types

**Choice:** Single-pass LLM classification — the extraction prompt includes cognitive types (BELIEF, INTENTION, PREDICTION, JUDGMENT, FEAR, DESIRE) alongside entity types (PERSON, PROJECT, etc.). The LLM classifies each extracted element in one step. Confidence scoring (STATED/INFERRED/SPECULATED) provides quality signals.
**Alternatives:**
- Two-pass classification (extract entities first, then classify cognitive type separately) — doubles LLM cost, introduces inconsistency risk between passes.
- Rule-based classification (heuristic patterns to identify beliefs, fears, etc.) — brittle, language-dependent, misses context-dependent classifications.
- Classification with validation (LLM classifies, then a second LLM call validates) — expensive, diminishing returns on accuracy.
**Rationale:** The existing MindMapExtractor already asks the LLM to classify entities by type — adding cognitive types extends the classification vocabulary rather than changing the mechanism. LLM classification of propositional attitudes IS harder than entity classification (the reviewer is correct on this point), but modern LLMs handle this well for conversational text where the speaker's attitude is typically explicit or strongly implied ("I think...", "I'm worried that...", "We should..."). The confidence scoring (STATED for explicit markers, INFERRED for implied attitudes, SPECULATED for ambiguous cases) provides downstream consumers with classification quality signals. TraitApplicationDecorator re-evaluates traits on every node mutation, so misclassifications that are later corrected (via property updates) will trigger automatic trait re-evaluation. The empirical risk is systematic misclassification (e.g., predictions consistently classified as beliefs), which should be measured during implementation and addressed with prompt engineering or few-shot examples if the error rate exceeds ~15%.
**Trade-offs:** Classification accuracy is an empirical assumption, not an architectural guarantee. If accuracy is poor, the trait system built on top produces unreliable behavior. Mitigation: confidence scoring + trait re-evaluation + prompt iteration.
**Sources:** MindMapExtractor.java (SYSTEM_PROMPT, ExtractionJsonParser), MindMapConfidenceDefaults.java
**Exploration:** surfaced during review (R1-10)
**Status:** captured

## D9: Cognitive type taxonomy — six types from domain requirements

**Choice:** Six cognitive types: belief, intention, prediction, judgment, fear, desire
**Alternatives:**
- BDI (Belief-Desire-Intention) — 3 types, standard in multi-agent systems (Rao & Georgeff, 1991). Fears are modeled as negative desires, predictions as probabilistic beliefs, judgments as evaluative beliefs. Too coarse for the platform's consolidation needs: beliefs and predictions require different lifecycle handling (predictions have a timeframe and falsification date; beliefs don't). Fears and desires require different consolidation strategies (fears are evaluated against current state; desires are checked for fulfillment).
- KARO framework (Knowledge, Abilities, Results, Obligations) — adds Knowledge (factive) vs Belief (potentially wrong), plus Commitments, Goals, and Obligations. Richer than BDI but introduces concepts (Knowledge as factive vs Belief as potentially wrong) that the platform doesn't need at v1 — confidence scoring already captures epistemic uncertainty without a separate type.
- Full propositional attitude taxonomy (doxastic, conative, evaluative, affective) — categories, not types. Maps to 4 super-categories, not to the 6 distinct processing behaviors the platform needs.
**Rationale:** The six types are chosen for their distinct consolidation lifecycle behaviors, not for theoretical purity:
1. Beliefs → revised on contradiction (epistemic lifecycle)
2. Intentions → checked for viability, tracked to achievement/abandonment (conative lifecycle)
3. Predictions → validated against outcomes within a timeframe (temporal epistemic lifecycle)
4. Judgments → compared with other evaluations, stance-based (evaluative lifecycle)
5. Fears → evaluated against current state, severity-driven (affective-epistemic lifecycle)
6. Desires → checked for fulfillment, urgency-driven (conative lifecycle)

Each type maps to a distinct set of consolidation operations that cannot be collapsed without losing processing fidelity. The taxonomy is pragmatic (driven by what the platform needs to DO with each type) rather than theoretically motivated (derived from a philosophical framework). The BDI objection that "fears are negative desires" and "predictions are probabilistic beliefs" is reductive — it collapses types with distinct processing needs into categories that would require sub-type dispatch within the consolidated category, re-introducing the complexity at a different level.
**Sources:** Issue #322, wacky-manor social cognition design, cognitive-types-guide.md, cognitive-architecture-roadmap.md
**Exploration:** surfaced during review (R1-07) — made explicit as a decision
**Status:** captured
