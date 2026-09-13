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
