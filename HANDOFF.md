# HANDOFF — casehub-neocortex

## Current Epic

**#570 — Corpus quality fixes** (follows #551). Slot 211 reactivated.

## Immediate Next Step

1. **Slot hygiene first** — 29 local branches, 1198 unrecovered artifacts, 119 stale branches, 83 unstamped. Clean up before starting implementation.
2. Then start the queue: #564 (critical — per-memory enrichments dropped during assembly).

## Queue

| # | Title | Scale | Priority |
|---|-------|-------|----------|
| 570 | Epic issue | — | — |
| 564 | Per-memory enrichments missing from assembled corpus | M | Critical |
| 565 | Entity naming inconsistency — 139 dangling edge references | M | High |
| 566 | Corpus nodes missing subgraph and type assignments | S | High |
| 567 | Contributes-to edge saturation | S | Medium |
| 568 | Factual errors in extracted edges | S | Medium |
| 569 | PAD arousal value compression | XS | Low |
| 560 | Second biography trial run (deferred from #551) | L | Deferred |

## Previous Epic (#551) Summary

11/12 issues closed across 2 sessions. Quality assessment graded corpus PARTIAL — disposition profile passes, 5/6 dimensions have systematic issues. Report at `docs/quality-reports/2026-10-12-frida-quality-assessment.md`.

## State

- On `main`, all #551 work landed
- 9 Java tests passing (5 LifeEventHandlerTest + 4 HandlerAssociationTest)
- 204 Python tests passing
- Golden baseline corpus: `extraction/output/corpus.json` (132 nodes, 1570 edges, 261 memories)
- GoalVocabulary stale-jar issue resolved (mindmap-api needed `mvn install` before memory-seeding compiles)
- IntelliJ MCP unavailable during last session (JVM heap critically low at 5%) — may need IDE restart

## Key Context

- The corpus exists in `extraction/output/corpus.json` but has NOT been imported into the cognitive stores yet
- `assemble_corpus.py` is where per-memory enrichments are dropped (#564) — trace the YAML→JSON path
- Entity naming: nodes use full/descriptive names, edges use short names — needs alias resolution in assembly (#565)
- All nodes have `type: unknown` / `subgraph: none` — assembly should derive from traits/categories (#566)
