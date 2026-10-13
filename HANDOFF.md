# HANDOFF — casehub-neocortex

## Current Epic

**#570 — Corpus quality fixes** (follows #551). Slot 211 reactivated.

## Last Session

Slot hygiene sweep — no implementation work. Cleaned up 28 non-main branches accumulated across multiple epics.

**What shipped:**
- Promoted 17 spec files from 4 workspace branches to main
- Promoted 2 blog entries to workspace main (mdp01: personality calibration, mdp02: sub-thoughts)
- Stamped 3 previously unstamped branches (issue-470, issue-501, issue-539)
- Verified all 23 issue branches are stamped and merged
- Acknowledged 6 superseded Java files (FormativeGraduationClassifier/Scorer, ExpansionStrategy)
- Filed soredium#445 for work-end orchestrator bugs (mechanical step dependencies on main, state persistence, plan advance corruption)

**Branch status after cleanup:**
- 23 issue branches: all stamped, all work verified on main
- 5 backup branches: pre-squash snapshots, unstamped by design
- 0 unstamped issue branches remaining

## Immediate Next Step

Start #564 — per-memory enrichments missing from assembled corpus (Critical, M).

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

## State

- On `main`, all work landed
- 9 Java tests passing (5 LifeEventHandlerTest + 4 HandlerAssociationTest)
- 204 Python tests passing
- Golden baseline corpus: `extraction/output/corpus.json` (132 nodes, 1570 edges, 261 memories)
- Quality report: `docs/quality-reports/2026-10-12-frida-quality-assessment.md`
- wrap_orchestrator.py still broken (`shared_steps.py:70` AttributeError) — handovers written manually

## Key Context for #564

- The corpus exists at `extraction/output/corpus.json` but has NOT been imported into the cognitive stores yet
- `assemble_corpus.py` is where per-memory enrichments are dropped — trace the YAML→JSON path
- The YAML biography files in `extraction/output/biography-output/` contain enrichment data (OCC, SEC, drives, sub-thoughts, CAPS, gut feeling, habituation) but none of it appears in the assembled corpus
- Only PAD values survive assembly — everything else is lost
- Fix the assembly, re-run, verify enrichments appear in corpus.json
