# HANDOFF — casehub-neocortex

## Current Epic

**#570 — Corpus quality fixes** (follows #551). Slot 211.

## Last Session

Resolved all 6 quality fix issues from #562 assessment. All work on branch `issue-564-per-memory-enrichments` (6 commits, ready for work-end).

**What shipped:**
- **#564 closed as invalid** — quality assessment incorrectly reported zero per-memory enrichments; corpus actually has 197/261 memories with full enrichment suite. Assessment corrected, grade upgraded PARTIAL→PASS.
- **#565 edge resolution** — added `resolve_edge_endpoints()` with 4 strategies (first-name matching, explicit aliases, paren-strip, dedup aliases). 312 of 534 dangling references resolved. `aliases.yaml` for per-biography overrides. 16 unit tests.
- **#566 subgraph assignments** — derived `subgraph` field from `subgraph_type` during assembly. All 132 nodes now have subgraph assignments.
- **#567 contributes-to saturation** — scoped cross-tier inference to subdomain + adjacent tiers only. 1172→317 contributes-to edges, total 1570→715, max fan-out 50→18.
- **#568 factual errors** — added `correct_edge_errors()` for structural fixes (inversions, duplicates, UNVALIDATED types) + per-biography corrections via `edge-corrections.yaml`. 16 corrections, 12 removals.
- **#569 arousal compression** — added calibration anchors to enrichment prompt (6-point arousal scale) + `audit_pad_distribution()` distribution check with stdev<0.2 warning. Re-enrichment needed for full effect.

**New files:**
- `extraction/output/aliases.yaml` — entity name aliases for edge resolution
- `extraction/output/edge-corrections.yaml` — factual edge corrections
- `extraction/tests/test_edge_resolution.py` — 22 tests for resolution + correction

**Corpus metrics after fixes:**
- 132 nodes (all with subgraph assignments)
- 703 edges (was 1570)
- 261 memories (197 enriched)
- 118 unresolved edge endpoints (genuinely missing entities — artworks, people, places)
- Arousal compression flagged (stdev=0.14, needs re-enrichment)

## Immediate Next Step

**#560 — Second biography trial run** (L scale, deferred from #551). Run the full extraction/enrichment pipeline on a new biography to validate generality. This is the remaining queue item.

## Queue

| # | Title | Scale | Priority | Status |
|---|-------|-------|----------|--------|
| 570 | Epic issue | — | — | Active |
| 564 | Per-memory enrichments missing | M | Critical | **Closed — invalid** |
| 565 | Entity naming inconsistency | M | High | **Closed** |
| 566 | Nodes missing subgraph/type | S | High | **Closed** |
| 567 | Contributes-to saturation | S | Medium | **Closed** |
| 568 | Factual errors in edges | S | Medium | **Closed** |
| 569 | PAD arousal compression | XS | Low | **Closed** |
| 560 | Second biography trial run | L | Deferred | Queued |

## State

- On `issue-564-per-memory-enrichments` branch, 6 commits ahead of main
- 22 Python tests passing (test_edge_resolution.py)
- All existing Java tests unaffected (Python-only changes)
- Branch ready for work-end squash and merge
