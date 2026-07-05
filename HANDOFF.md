# Handoff — 2026-07-05

## What Changed

Closed 9 issues in a single branch (#90, #95, #96, #97, #98, #99, #100, #102, #103). Added `CaseMemoryStore.discoverTenants()` SPI with JPA/SQLite/InMemory backends for post-dimension-change tenant discovery. `CaseEnrichmentStep` SPI + `CaseEnrichmentDecorator` for pre-store transformation pipelines. Full `ReactiveCaseMemoryStore` parity (scan, capabilities, requireCapability, discoverTenants). CDI-restructured `CbrReconciliationService` with `@Timed` + Micrometer counters, `reconcileAll()` overloads, chunked batch upserts. `FlatCorpusStore` hidden path filtering via `FileVisitor SKIP_SUBTREE`. `ColbertQuantizationConfig` in `RagConfig`. Landed on upstream main as `e2fd9dc`.

## Immediate Next Step

All 9 issues closed. Pick from What's Next — #63 (embedding evaluation) is the next substantive piece. #65 (Memori adapter) is blocked on external dependency.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |

## Key References

- Design spec: `specs/2026-07-05-batch-s-xs-plus-98-design.md` (workspace)
- Plan: `plans/attic/issue-98-batch-s-xs-tenant-discovery/2026-07-05-batch-s-xs-plus-98.md` (workspace)
- Design review: `~/adr/casehub-neocortex/batch-s-xs-plus-98-20260705-023014/`
- Blog: `blog/2026-07-05-mdp02-nine-issues-one-branch.md` (workspace)
