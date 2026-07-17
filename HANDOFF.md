# Handoff — 2026-07-18

## What Changed

Branch `issue-161-planadapter-casetype-param` closed. Landed as `d63195e` on main. PR #163 → casehubio/neocortex. Closes #161.

**Delivered:** `PlanAdapter.adapt()` SPI gains `String caseType` as first parameter — explicit type context for type-specific adaptation rules, replacing fragile capability-name inference. `AdaptationTrace` record gains `caseType` field (non-null) for audit trail completeness. `NoOpPlanAdapter`, `TrackingPlanAdapter`, and all tests updated. 7 files, 109 insertions, 75 deletions.

## Immediate Next Step

Pick next from backlog. #148 (cross-plan structural analysis) is the next substantial CBR work. #109 (retrieval tracking analysis) is also unblocked.

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #148 | Cross-plan structural analysis / ensemble adaptation | M | High | Deferred from #85 |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready |
| #154 | Trust-weighted retention — precedent authority + trust trajectory | S | Med | Blocked by platform trust infra |
| #142 | Wire CbrOutcomeConsumer to CloudEvent routing | S | Med | Blocked by platform#174 |

## References

- PR: https://github.com/casehubio/neocortex/pull/163
