# HANDOFF — casehub-neocortex

## Last Session

Completed #322 (cognitive node type classification) — full brainstorm-through-implementation cycle. Design explored compositionality vs exclusive classification from first principles; decision review (3 rounds, $13.32) revised 4 of 6 original decisions. Implementation: 4 tasks, 3 batches, all tests green (144 in affected modules).

### What was built

- **COGNITIVE subgraph type** — `SubgraphTypes.COGNITIVE` constant in mindmap-api
- **6 trait interfaces** — Belieflike, Intentionlike, Predictive, Evaluative, Fearlike, Desirelike (3 properties each, `Optional<String>`, `-like` suffix for nouns, adjectival for verbs)
- **Declarative YAML trait rules** — `cognitive-index/src/main/resources/rules/cognitive-traits.yaml` with primary (`cognitiveKind` property) + secondary compositional rules (`anyOf` for cross-type inference)
- **TypeRegistry hierarchy** — COGNITIVE parent under GENERAL with 6 children, java-class associations for schema derivation via `schemaFor()`
- **MindMapExtractor** — prompt expanded with cognitive types, `resolveSubgraphType()` routes to COGNITIVE subgraph, `cognitiveKind` property set on extracted nodes

### Key design decisions

- D1: Compositional traits (additive) over exclusive subtypes — cognitive categories overlap
- D2: Dedicated COGNITIVE subgraph (consolidation phases operate per-subgraph)
- D3: 3-property interfaces with `status` lifecycle pattern
- D4: Declarative YAML baseline (programmatic reserved for complex matching)
- D5: COGNITIVE parent type under GENERAL (not under CONCEPT)
- D6: Separated normalizeType (pure) from resolveSubgraphType (routing)

### Implementation notes

- DeclarativeRuleRegistry merges rules by trait name — secondary compositional rules must use `anyOf` with primary condition to avoid overwriting
- DeclarativeRuleRegistryTest assertions updated: 2 → 8 global trait rules

## Immediate Next Step

#333 — epic: cognitive observability (MCP tools for graph inspection, delta, health, trace). XL/Med. Needs brainstorming to decompose into child issues. Three layers: Layer 1 (live view — cognition_inspect, cognition_entity, cognition_health), Layer 2 (snapshot + delta infrastructure), Layer 3 (temporal observation — cognition_diff, cognition_trace).

## References

- Spec: `wksp/specs/issue-322-cognitive-node-types/2026-09-14-cognitive-node-types-design.md`
- Decisions: `wksp/specs/issue-322-cognitive-node-types/decisions.md` (D1-D9)
- Plan: `wksp/plans/2026-09-14-cognitive-node-types.md`
- Journal: `wksp/JOURNAL.md`
- Open issues: #333 (cognitive observability epic)
