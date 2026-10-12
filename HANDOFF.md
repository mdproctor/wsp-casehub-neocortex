# HANDOFF — casehub-neocortex

## Last Session

Implemented epic #551 stages 9-11 (corpus-to-YAML converter, Java entry extensions, new handlers, integration test). Merged issue-539 extraction pipeline (25 commits) into the branch then added 7 commits for #551.

**What shipped:**
- `convert_corpus.py` — Python converter: corpus.json → 11 typed YAML files (132 nodes, 1470 edges, 261 memories on Frida corpus)
- Shared `Association` and `PadValues` records — unified across all entry types
- `PlaceHandler` bug fix — cross-subgraph resolution replacing phantom-node creation
- `OrganisationHandler` — new type at layer 4 (ORGANISATION subgraph)
- `EntityEnrichmentHandler` — layer 7 (drive baselines, CAPS patterns, behavioural attractors)
- `DispositionProfileHandler` — layer 7 (categorical disposition axes matching CognitiveDerivationEngine)
- `LifeEventEntry` extended with 9 enrichment types + `EnrichmentAttributeKeys` + MemoryDomain routing
- `BiographyTemplateTypes` migrated to `Map.ofEntries()` (13 entries)
- `BiographyImportIntegrationTest` — full round-trip verification

**What did NOT ship (filed as child issues):**

## Immediate Next Step

Epic #551 is reopened with 10 child issues. Recommended work order:

### Quick wins (XS, can batch in one session)
- #554 — Update verify_schema.yaml with new type entries
- #555 — Update design spec for DispositionProfileEntry
- #561 — Wire handler associations for Activity/Project/CulturalContext/Belief
- #563 — LifeEventHandler MemoryDomain routing test coverage

### Small (S, one per session)
- #553 — Python unit tests for convert_corpus.py
- #556 — Post-import validation script (validate_import.py)
- #557 — Pipeline reproducibility demonstration

### Medium (M, need brainstorming)
- #558 — Regression baseline — golden corpus.json for Frida
- #562 — Frida corpus quality assessment — end-to-end cognitive model review

### Large (L, depends on above)
- #559 — CI gate for deterministic stages (depends on #557)
- #560 — Second biography trial run — generality proof (depends on #558)

```
Plan: plans/2026-10-12-production-biography-pipeline.md
Spec: specs/issue-551-production-biography-pipeline/2026-10-12-production-biography-pipeline-design.md
Epic: #551, remaining: #553-#563 (10 child issues)
Branch: main (issue-551 landed and stamped)
```

## State

- On `main`, branch `issue-551-production-biography-pipeline` stamped as closed (landed as 037addd0)
- Design reviews: 26 findings from decision + spec reviews, all incorporated
- Code reviews: 0 CRITICAL, 2 WARNING (fixed), 7 NOTES (acknowledged)
- Conformance audit: 3 findings → filed as #553, #554, #555
- All Java tests pass (memory-seeding module)
- Converter verified on Frida corpus: 132 nodes, 1470 edges (1157 specific + 313 association), 261 memories
- Disposition score-to-category conversion: uses DISPOSITION_CATEGORIES lookup matching DispositionAxes/CognitiveDerivationEngine

## Key Design Decisions

1. **GoalEntry taxonomy fields already shipped** (from issue-539) — all String type matching Goallike trait interface
2. **DispositionProfileEntry uses categorical strings** (cooperative/defiant/bold) — NOT numeric scores — matching CognitiveDerivationEngine lookup maps (SR-R1-01)
3. **PlaceHandler fixed** — was creating phantom nodes in wrong subgraph; now uses AssociationProcessor for cross-subgraph resolution (SR-R1-04)
4. **MemoryDomain routing** — LifeEventHandler resolves experience/relationship/reflection domain from entry field, not hardcoded (SR-R1-05)
5. **Universal associations** — added to all MindMap-writing entry types, but only GoalHandler and PlaceHandler currently process them (#561 tracks the rest)
