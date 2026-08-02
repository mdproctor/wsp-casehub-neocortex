# Handoff — 2026-08-02 (batch-s-xs-quality)

## What Changed

Two branches landed this session covering 9 closed issues:

### Branch 1: issue-166-cbr-quality-retention (10 commits)
- **#176** — Trust-based CBR retention (minTrustScore, scan/discoverTenants SPI, TrustRetentionService, CbrRetentionScheduler)
- **#189** — Memory importance + decay (importance field on MemoryInput/Memory, MemoryRetentionPolicy, purge SPI, MemoryRetentionScheduler)
- **#190** — Dynamic RRF weight boosting (per-query weightMultipliers on RetrievalQuery, effectiveWeight in HybridCaseRetriever)
- **#166** — Closed as stale (reactive tier removed in #384)

### Branch 2: issue-195-batch-s-xs-quality (6 commits)
- **#195** — Pre-ingestion dedup gate (DedupEmbeddingIngestor decorator, cosine similarity check)
- **#194** — Qdrant trust-purge, scan, discoverTenants (178/180 tests pass, 2 pagination edge cases)
- **#193** — variantId on PlanTrace (nullable field for prompt variant correlation)
- **#192** — MemoryOrder.SALIENCE (recency x importance scoring in InMemoryMemoryStore)
- **#191** — CLAUDE.md reactive tier cleanup (zero remaining reactive references)
- **#188** — PersonalityTransitionSchema (CBR schema for Jungian personality evolution)

### Also filed
- **#191** — CLAUDE.md reactive tier cleanup (closed)
- **#194** — Qdrant scan/discoverTenants (closed)
- **Hortora/engine#75** — gardenUnretrieved refactor to use RetrievalAnalyzer (moved from neocortex#168)
- **casehubio/engine#854** — closed (wrong repo, moved to Hortora/engine#75)

### Blog entries
- "When Your Agent Remembers Too Much" — CBR quality & retention
- "The First Five Minutes" — SC2 strategy classifier

## Carrying forward
- **vs_protoss ONNX model** — not retrained (Podman OOM). vs_terran and vs_zerg retrained, stashed in `git stash`.
- **SC2EGSet ZIPs** — stored in `quarkmind/data/sc2egset-replays/` (5 packs, ~2.5 GB, gitignored).
- **Qdrant scan_pagination** — 2 contract test failures due to scroll offset semantics. Needs investigation.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Trigger: second consumer |
| — | quarkmind#212: three-tier cascade integration | L | Med | Consumes trained .onnx models |
| — | Retrain vs_protoss with cumulative fog-of-war | S | Low | Blocked on Podman memory |
| — | Qdrant scan pagination fix | XS | Low | scroll offset vs cursor semantics |
