# Handoff — 2026-07-06

## What Changed

Retrieval tracking SPI (#105). RetrievalTracker + ReactiveRetrievalTracker in rag-api with RetrievalOutcome enum (4-level graduated feedback), RetrievedDocumentRef, RetrievalRecord, RetrievalFeedback, RetrievalRecorded CDI event. TrackingCaseRetriever + ReactiveTrackingCaseRetriever @Decorator @Priority(50) with isAlreadyTracked guard and failure isolation. SqliteRetrievalTracker (HikariCP WAL + Flyway), InMemoryRetrievalTracker, BlockingToReactiveRetrievalTracker bridge, 17-test contract test. Adversarial design review (4 rounds, 11 issues, 10 verified). Filed #109 (analysis service) and #110 (retention policy). Garden entry GE-20260706-01fc22 (Instant.MAX SQLite gotcha). Landed on upstream main as `f34e94d`.

## Immediate Next Step

All work for #105 closed. Pick from What's Next — #63 (embedding evaluation) is the next substantive piece. #65 (Memori adapter) is blocked on external dependency.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |
| #106 | Semantic text field similarity in CbrSimilarityScorer | M | Med | Deferred from #82/#87 |
| #107 | Categorical similarity tables | M | Med | Deferred from #82/#87 |
| #108 | Per-field similarity function configuration | S | Low | Deferred from #82/#87 |
| #109 | Retrieval tracking analysis service | M | Med | New — blocked by #105 (now closed) |
| #110 | Retrieval tracking data retention policy | S | Low | New — blocked by #105 (now closed) |

## Key References

- Spec: `docs/specs/2026-07-05-retrieval-tracking-spi-design.md` (project)
- Design review: `~/adr/casehub-neocortex/retrieval-tracking-spi-20260705-230959/`
- Blog: `blog/2026-07-06-mdp01-retrieval-tracking-spi.md` (workspace)
- Garden: `GE-20260706-01fc22` — Instant.MAX breaks SQLite text-based timestamp comparisons
