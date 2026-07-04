# Handoff — 2026-07-04

## What Changed

Closed #94 — CBR adoption epic. Created `example-cbr` module with six domain demos (AML, Clinical, DevTown, Life, IoT, QuarkMind) showing Feature-Vector and Plan-Based CBR with realistic seed data and practical output. 20 smoke tests + 6 integration tests (Qdrant + EmbeddingModel). Documentation closes all adoption gaps: dense vector search, dual storage, config reference, dev mode guidance, two new domain guides (life, IoT), roadmap sections on all existing guides, cbr-types.md taxonomy, README CBR section. Design-reviewed (4 rounds, 16 issues, all resolved). Cross-references posted on all six app-side epics. Landed on fork main as `0a05ff9`.

Also created `docs/cbr/cbr-types.md` — full taxonomy of Textual, Feature-Vector, and Plan-Based CBR with inputs, outputs, routing signal, and roadmap extensions. Linked from README and CBR integration guide. Written for blocks#30 (CBR-enriched routing strategy context).

## Immediate Next Step

Push to upstream: `git -C /Users/mdproctor/claude/casehub/neocortex push upstream main`. Fork is current; blessed repo is not.

## What's Left

- #74 — Reconciliation job: reindex + orphan cleanup · M · Med
- #78 — Gate destructive dimension-mismatch recovery behind config flag · S · Low · blocked by #74
- #79 — Minor review findings batch · XS · Low
- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #74 | Reconciliation job | M | Med | Not blocking rollout but needed for dim migration |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #78 | Dimension migration config gate | S | Low | Blocked by #74 |
| #79 | Minor review findings batch | XS | Low | Non-blocking cleanup |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |

## Key References

- Design spec: `specs/2026-07-04-cbr-adoption-examples-design.md` (workspace)
- Plan: `plans/2026-07-04-cbr-adoption-examples.md` (workspace)
- CBR types doc: `docs/cbr/cbr-types.md` (project)
- Design review: `~/adr/casehub-neocortex/cbr-adoption-examples-20260704-161946/`
