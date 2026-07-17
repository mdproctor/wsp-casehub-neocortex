# Scope-Based Bulk Erasure + Aggregate Erasure Notification

**Issues:** #158, #159
**Date:** 2026-07-17
**Status:** Approved

## Context

#153 introduced hierarchical scoping to CBR — cases are stored at `Path` scopes and retrieved with scope visibility (`isAncestorOf`). Two follow-on needs emerged:

1. **#158 — eraseByScope:** Operational lifecycle cleanup. When a scope is decommissioned ("close this trial site"), all cases stored at that scope and below should be deleted. Not GDPR Art.17 (that is entity-anchored via `eraseEntity`).

2. **#159 — aggregate adjustment on entity erasure:** Higher-scope aggregates that track counts or statistics from lower-scope cases become stale after cases are erased. No mechanism exists for domains to know that source cases were removed so they can recompute.

## Design

### #158: eraseByScope(Path scope, String tenantId)

**SPI addition** — new method on `CbrCaseMemoryStore` and `ReactiveCbrCaseMemoryStore`:

```java
// CbrCaseMemoryStore
Integer eraseByScope(Path scope, String tenantId);

// ReactiveCbrCaseMemoryStore
Uni<Integer> eraseByScope(Path scope, String tenantId);
```

**Subtree semantics:** Erases all cases where `scope.equals(storedScope) || scope.isAncestorOf(storedScope)`. Root scope (`Path.root()`) erases all cases for the tenant.

**Return value:** Count of erased cases, consistent with `erase` and `eraseEntity`.

**Implementations:**

| Store | Approach |
|-------|----------|
| InMemory | `removeIf` with scope equality + `isAncestorOf` check |
| JPA | Root: `DELETE WHERE tenantId = :t`. Non-root: `DELETE WHERE tenantId = :t AND (scope = :s OR scope LIKE :prefix)` where prefix = `scope.value() + "/%"` |
| Qdrant | Scroll with tenantId filter, client-side scope prefix check, batch delete by point IDs. Acceptable for operational method. |
| NoOp | `return 0` |

**Forwarding:** All decorators (Tracking/50, OutcomeWeighting/65, Reranking/75, ScopeDecay/85, TrendEnrichment/90) and `BlockingToReactiveCbrBridge` gain pass-through forwarding. Same pattern as existing erasure methods.

### #159: CbrCasesErased CDI Event

**Event record** in memory-api:

```java
public record CbrCasesErased(
    String tenantId,
    int erasedCount,
    String entityId,      // non-null for eraseEntity
    Path scope,           // non-null for eraseByScope
    MemoryDomain domain,  // non-null for erase(EraseRequest)
    Instant erasedAt
) {}
```

**Mechanism:** CDI event, following the established pattern (`CbrRetrievalRecorded`, `CbrAdaptationRecorded`). Loosely coupled, fire-and-forget, supports multiple observers.

**Scope:** Fired for `erase`, `eraseEntity`, `eraseByScope` when `count > 0`. Not fired for `purge` — retention-based cleanup has different lifecycle expectations; aggregates built from purged data drift naturally with age-based policies.

**Decorator:** `ErasureNotificationCbrCaseMemoryStore` at `@Decorator @Priority(45)`. Outermost position ensures the event fires after the entire chain completes. Uses `Event.fireAsync()` for non-blocking notification. Reactive counterpart at same priority.

## Decisions

| Decision | Rationale |
|----------|-----------|
| Subtree semantics for eraseByScope | "Decommission this site" naturally means the entire subtree. Exact-scope deletion can use `erase(EraseRequest)` with future scope filter if needed. |
| CDI event over SPI callback or periodic recomputation | Established pattern in this module. Decoupled from store logic. Fire-and-forget. Multiple observers. |
| Not firing on purge | Purge is retention lifecycle, not explicit erasure. Aggregates drift naturally with age policies. |
| Qdrant scroll+delete | eraseByScope is operational, not query-path. Qdrant lacks keyword prefix matching. Scroll is correct and proportional. |
| Abstract method (not default) | All implementations are in this repo. SPI break is self-contained. Consistent with existing erase methods. |
| @Priority(45) for notification decorator | Below Tracking(50) = outermost. Event fires after complete erasure. |

## Contract Tests

6 new tests in `CbrCaseMemoryStoreContractTest`:
1. Erase at exact scope only erases that scope's cases
2. Erase at parent erases all descendant cases
3. Erase at root erases all cases for tenant
4. Tenant isolation preserved
5. Returns correct count
6. No cases at scope returns 0

Dedicated unit test for `ErasureNotificationCbrCaseMemoryStore`.

## Files Changed

| Module | Changes |
|--------|---------|
| memory-api | `CbrCaseMemoryStore` + `ReactiveCbrCaseMemoryStore` (add method), new `CbrCasesErased` record |
| memory | `NoOpCbrCaseMemoryStore`, `BlockingToReactiveCbrBridge`, all 6 blocking decorators + 5 reactive decorators (forwarding), new `ErasureNotificationCbrCaseMemoryStore` + reactive counterpart |
| memory-cbr-inmem | `InMemoryCbrCaseMemoryStore` (implement) |
| memory-cbr-jpa | `JpaCbrCaseMemoryStore` (implement) |
| memory-qdrant | `QdrantCbrCaseMemoryStore` (implement) |
| memory-cbr-crossencoder | 2 decorators (forwarding) |
| memory-cbr-tracking | 2 decorators (forwarding) |
| memory-testing | `CbrCaseMemoryStoreContractTest` (new tests) |

No Flyway migration — JPA delete query uses existing `scope` column from V4.
