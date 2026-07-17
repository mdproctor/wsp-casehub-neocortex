# Handoff — 2026-07-17

## What Changed

Branch `issue-158-scope-erasure-aggregate-adj` closed. Landed as `b407543` on main. PR #160 → casehubio/neocortex. Closes #158, #159.

**Delivered:** CBR scope erasure + aggregate erasure notification. `eraseByScope(Path, tenantId)` with subtree semantics on all backends (InMemory, JPA prefix LIKE, Qdrant scroll+delete with per-case CaseMemoryStore delegation). `CbrCasesErased` sealed CDI event interface (`ByRequest`, `ByEntity`, `ByScope`) fired by `ErasureNotificationCbrCaseMemoryStore` @Decorator @Priority(45), blocking-only. 8 contract tests + 8 notification unit tests. Design review: 5 rounds, 14 issues, all resolved ($19.26).

**Key design decisions:** Subtree semantics (scope + all descendants). Sealed interface over union record (no nullable ambiguity, CDI subtype observation). Blocking-only notification decorator (no reactive counterpart — bridge routes all reactive calls through blocking chain, eliminating double-firing by design). `Event.fire()` synchronous (matches TrackingCbrCaseMemoryStore pattern). Not fired on purge (retention lifecycle ≠ explicit erasure).

## Immediate Next Step

Pick next from backlog. #148 (cross-plan structural analysis) is the next substantial CBR work. #154 blocked.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #154 | Trust-weighted retention — precedent authority + trust trajectory | S | Med | Blocked by platform trust infra |
| #148 | Cross-plan structural analysis / ensemble adaptation | M | High | Deferred from #85 |
| #142 | Wire CbrOutcomeConsumer to CloudEvent routing | S | Med | Blocked by platform#174 |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |

## References

- Spec: `docs/specs/2026-07-17-scope-erasure-aggregate-notification-design.md` (workspace)
- Plan: `plans/attic/issue-158-scope-erasure-aggregate-adj/2026-07-17-scope-erasure-aggregate-notification.md` (workspace)
- Design review: `~/adr/casehub-neocortex/scope-erasure-aggregate-notification-20260717-185328/`
- PR: https://github.com/casehubio/neocortex/pull/160
