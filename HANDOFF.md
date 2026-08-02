# Handoff — 2026-08-02 (cbr-quality-retention)

## What Changed

Implemented three features across memory-api, memory/, rag-api, and rag modules:

- **#176 — Trust-based retention:** `minTrustScore` on `CbrRetentionPolicy` (OR semantics with age/count). Trust-based purge in InMemory and JPA. New `scan()`/`discoverTenants()` SPI on `CbrCaseMemoryStore` with InMemory and JPA implementations. `TrustRetentionService` for trajectory-based purging via `AgentTrustProvider`. `CbrRetentionScheduler` as production consumer.

- **#189 — Memory importance:** `importance` field on `MemoryInput`/`Memory` (31 files updated via IntelliJ change-signature). `MemoryRetentionPolicy` with AND semantics (old AND unimportant = purge). `purge()` SPI on `CaseMemoryStore` + InMemory/JPA/SQLite implementations. `MemoryRetentionScheduler`. `CaseEnrichmentDecorator` updated to delegate `purge()`.

- **#190 — Dynamic RRF weight boosting:** `weightMultipliers` on `RetrievalQuery`. `effectiveWeight()` in `HybridCaseRetriever` across all 3 fusion paths. Per-query multipliers trigger client-side RRF fallback when weights become non-equal. Fixed recursive `effectiveWeight` bug from bulk replacement.

- **#166 — Closed as stale:** Reactive tier was removed in #384. Virtual threads made reactive JPA unnecessary.

- **#191 filed:** CLAUDE.md describes removed reactive tier — needs cleanup (large change, separate session).
- **#194 filed:** Qdrant backend needs trust-purge, scan, discoverTenants implementations.

## Carrying forward from prior session

- **SC2 strategy classifier blog draft** — written but not saved to disk. Draft was presented in session. Needs review and save.
- **vs_protoss ONNX model** — not retrained (Podman OOM). vs_terran and vs_zerg retrained with cumulative fog-of-war, stashed in `git stash` on main.
- **SC2EGSet ZIPs** — stored in `quarkmind/data/sc2egset-replays/` (5 packs, ~2.5 GB, gitignored).

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #194 | Qdrant backend — trust-purge, scan, discoverTenants | S | Low | Contract tests already exist |
| #191 | CLAUDE.md cleanup of removed reactive tier | S | Low | 61 files removed in #384 |
| #22 | Extract corpus CDI to corpus-quarkus/ module | M | Low | Trigger: second consumer |
| — | quarkmind#212: three-tier cascade integration | L | Med | Consumes trained .onnx models |
| — | Retrain vs_protoss with cumulative fog-of-war | S | Low | Blocked on Podman memory |
