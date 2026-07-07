# Handoff — 2026-07-07

## What Changed

Closed #119 (original query in expansion result set) and #113 (per-leg embedding separation). Expansion decorators now always prepend the original query using record equality — safety net for HyDE drift. HybridCaseRetriever and reactive variant use `embedBatch()` when expansion is active: dense leg gets `searchText()` (expanded), sparse/ColBERT get `text()` (original). Unconditional — no config flag, it's a correctness fix. Adversarial design review (2 rounds, 9 issues, all resolved). CBR guide and README revised with full capability brief. Landed as `486b6e2` and `adaf00d` on both `origin/main` and `upstream/main`.

## Immediate Next Step

Pick next work item from What's Next — #109 and #110 are unblocked, #120 builds on this session's per-leg infrastructure.

## Cross-Module

**We're blocking:**
- `Hortora/engine` — can now adopt HyDE with confidence (original query always present, per-leg embedding correct). Their `0.2-SNAPSHOT` dependency picks up both changes.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked (#105 closed) |
| #110 | Retrieval tracking data retention policy | S | Low | Unblocked (#105 closed) |
| #120 | Expansion drift metrics with auto-fallback | M | Med | Builds on per-leg embedding |
| #121 | RerankingCaseRetriever with cross-encoder | M | Med | Hortora/engine#41 |

## Key References

- Spec: `docs/specs/2026-07-07-expansion-safety-and-per-leg-embedding-design.md`
