# Design Journal — issue-322-cognitive-node-types

## 2026-09-14 — Cognitive node type classification

### Key insight: compositionality over exclusive classification

The central design question was whether cognitive types (belief, intention, prediction, judgment, fear, desire) should be exclusive subgraph types or compositional traits. First-principles analysis revealed these are overlapping aspects of mental representations — "the servers will crash" is simultaneously a prediction, a belief, and a fear. Exclusive subgraph typing would force a choice, losing real information.

The architecture already handles this: subgraph types are exclusive (structural placement), traits are additive (behavioral classification). Cognitive types follow the Eventlike + Threatening/Aspirational pattern — shared subgraph with compositional traits — but with richer per-type schemas via trait interfaces.

### Decision review corrections

The standard decision review (3 rounds, $13.32) revised 4 of 6 original decisions:

- **D2 reversed**: CONCEPT → dedicated COGNITIVE subgraph. Consolidation phases operate per-subgraph — MergeDetectionPhase would incorrectly flag beliefs against concepts with similar names.
- **D3 enriched**: 2 properties → 3 per interface with `status` lifecycle pattern (matching Eventlike/Projectlike convention). Trait naming: `-like` suffix for nouns, adjectival for verbs.
- **D4 reversed**: Both programmatic + declarative → declarative baseline only. Baseline rules are trivially PropertyEquals — 6 Java classes for what YAML handles in 12 lines.
- **D5 restructured**: Subtypes of `concept` → subtypes of new COGNITIVE parent under GENERAL. Type hierarchy must match subgraph model.

### Implementation

4 tasks across 3 batches. One unexpected issue: DeclarativeRuleRegistry merges rules by trait name, so secondary compositional rules (e.g., `hasProperty: timeframe → Predictive`) overwrote primary rules (e.g., `cognitiveKind=prediction → Predictive`). Fixed by combining primary + secondary conditions under `anyOf`. 3 existing DeclarativeRuleRegistryTest assertions also needed updating for the new global rule count (2 → 8).
