# CBR Reconciliation, Dimension Gate, and Minor Findings

**Issues:** #74, #78, #79
**Branch:** `issue-74-cbr-reconciliation-batch`
**Date:** 2026-07-04

## Problem

The CBR architecture has a dual-store design: `QdrantCbrCaseMemoryStore` delegates durable storage to `CaseMemoryStore` (JPA/SQLite) and maintains a Qdrant index for similarity search. When the index loses data — dimension change, Qdrant restart, failed upserts — there is no mechanism to recover from the durable store.

The root cause: `CaseMemoryStore` has no bulk enumeration capability. Its `query()` method requires `entityIds` (entity-scoped), making it impossible to answer "what CBR entries exist for caseType X?" The delegate is write-only for disaster recovery purposes — it can receive data but cannot be read back for reindexing.

Secondary issues: `CbrCollectionManager.ensureCollection()` silently deletes and recreates Qdrant collections on dimension mismatch (destructive, ungated), and several minor code review findings from #70.

## Design

### §1 CaseMemoryStore scan SPI (memory-api)

Three additions to `memory-api`:

**§1.1 MemoryCapability.SCAN**

New enum value in `MemoryCapability`:

```java
SCAN  // paginated attribute-filtered enumeration
```

**§1.2 MemoryScanRequest**

New request type in `io.casehub.neocortex.memory`:

```java
public record MemoryScanRequest(
    String tenantId,        // required — tenant isolation
    String domain,          // nullable — optional domain filter
    String attributeKey,    // nullable — attribute filter key
    String attributeValue,  // nullable — attribute filter value (requires key)
    int limit,              // page size, >= 1
    String afterMemoryId    // nullable — cursor for keyset pagination
) {
    public MemoryScanRequest {
        Objects.requireNonNull(tenantId, "tenantId required");
        if (limit < 1)
            throw new IllegalArgumentException("limit must be >= 1, got: " + limit);
        if (attributeValue != null && attributeKey == null)
            throw new IllegalArgumentException("attributeValue requires attributeKey");
        if (attributeKey != null && attributeValue == null)
            throw new IllegalArgumentException("attributeKey requires attributeValue for filtered scan");
    }
}
```

Pagination: `ORDER BY memoryId ASC, WHERE memoryId > :cursor`. Random UUIDs produce arbitrary but deterministic ordering — sufficient for exhaustive enumeration. Caller detects last page by `result.size() < limit`. Next cursor = `result.getLast().memoryId()`.

**§1.3 CaseMemoryStore.scan()**

Default method on `CaseMemoryStore`:

```java
default List<Memory> scan(MemoryScanRequest request) {
    throw new MemoryCapabilityException(MemoryCapability.SCAN, getClass());
}
```

No reactive variant (`ReactiveCaseMemoryStore`) in this iteration — reconciliation is blocking, reactive scan added when a consumer needs it.

### §2 Scan implementations

**§2.1 JpaMemoryStore** — native SQL against PostgreSQL:

Calls `MemoryPermissions.assertTenant(request.tenantId(), principal, requestContextActive())` before executing, matching the pattern of every other `CaseMemoryStore` method in `JpaMemoryStore`. The 3-arg form allows async/batch callers (no request context) to bypass principal comparison while preserving tenant-scoped data filtering.

The `attributes` column is stored as TEXT (per `MemoryEntry.columnDefinition = "TEXT"`). The `::jsonb` cast converts at query time. No GIN index is possible on a TEXT column; if scan performance becomes a concern, migrating the column to native JSONB would enable indexing.

SQL (filtered case — when `attributeKey` is non-null):

```sql
SELECT * FROM memory_entry
WHERE tenant_id = :tenantId
  AND (:domain IS NULL OR domain = :domain)
  AND attributes::jsonb->>:key = :value
  AND memory_id > :cursor
ORDER BY memory_id ASC
LIMIT :limit
```

When `attributeKey` is null (no attribute filter), the `AND attributes::jsonb->>...` clause is omitted entirely — the query scans all entries for the tenant (optionally filtered by domain). Implemented as conditional SQL builder logic: append the JSON clause only when `attributeKey != null`.

`->>` is a top-level key lookup, not a path expression — dotted keys like `cbr.caseType` work correctly.

Declares `MemoryCapability.SCAN` in `capabilities()`.

**§2.2 SqliteMemoryStore** — `json_extract` with quoted key syntax:

Calls `MemoryPermissions.assertTenant(request.tenantId(), principal, requestContextActive())` before executing, matching the pattern of every other `CaseMemoryStore` method in `SqliteMemoryStore`.

```sql
SELECT * FROM memory_entry
WHERE tenant_id = :tenantId
  AND (:domain IS NULL OR domain = :domain)
  AND json_extract(attributes, '$."' || :key || '"') = :value
  AND memory_id > :cursor
ORDER BY memory_id ASC
LIMIT :limit
```

Quoted key syntax (`$."cbr.caseType"`) prevents SQLite from interpreting `.` as a JSON path separator. Same conditional SQL builder pattern as §2.1 — JSON clause omitted when `attributeKey` is null.

Declares `MemoryCapability.SCAN` in `capabilities()`.

**§2.3 NoOpCaseMemoryStore** — does NOT override `scan()`. Inherits the throwing default. The no-op is a sentinel — `CbrReconciliationService` checks `capabilities().contains(SCAN)` (§3.2) and returns a no-op result before `scan()` is ever called.

**§2.4 Mem0CaseMemoryStore, GraphitiCaseMemoryStore** — inherit throwing default. REST-backed stores cannot do arbitrary attribute-filtered enumeration.

**§2.5 Contract test** — per `spi-default-method-contract-test` protocol: test using anonymous `CaseMemoryStore` implementation (abstract methods only) that verifies `scan()` throws `MemoryCapabilityException`.

### §3 CbrReconciliationService (memory-qdrant)

**§3.1 Class**

```java
public class CbrReconciliationService {
    private final CbrCollectionManager collectionManager;
    private final EmbeddingModel embeddingModel;          // nullable
    private final QdrantCbrConfig config;
    private final CaseMemoryStore delegate;               // nullable
    private final Map<String, CbrFeatureSchema> schemas;
}
```

Produced by `QdrantCbrBeanProducer` — shares `CbrCollectionManager`, `EmbeddingModel`, config, delegate, and schema registry with `QdrantCbrCaseMemoryStore`.

Apps inject via `Instance<CbrReconciliationService>` — only resolvable when `memory-qdrant` is on the classpath.

**§3.2 Preconditions**

Before reconciliation:
- `delegate == null` → return no-op `ReconciliationResult(caseType, tenantId, 0, 0, 0)` (Qdrant-only mode, nothing to reconcile)
- `!delegate.capabilities().contains(MemoryCapability.SCAN)` → return no-op `ReconciliationResult(caseType, tenantId, 0, 0, 0)` with `LOG.info("Reconciliation skipped — delegate does not support SCAN")`. This handles `NoOpCaseMemoryStore` (empty capabilities) gracefully — no exception for admin tooling.

**§3.3 Unified reconciliation pass**

Single-pass set-intersection algorithm. Two paginated scans, no N+1 queries.

**Step 1 — Build delegate index.** Scan delegate: `MemoryScanRequest(tenantId, null, "cbr.caseType", caseType, pageSize, cursor)`. For each `Memory`, compute deterministic point UUID via `CbrPointBuilder.pointId(tenantId, caseType, memory.caseId())` and accumulate into `Map<UUID, Memory>`.

**Step 2 — Qdrant intersection.** If the collection exists, scroll all Qdrant points filtered by `tenantId` payload. For each point:
- Point ID is in the delegate map → consistent. Remove from map.
- Point ID is NOT in the delegate map → orphan. Collect for batch deletion.

Delete orphans in bulk at end of each scroll page. If the collection does not exist, skip this step entirely — all delegate entries are missing by definition.

**Step 3 — Reindex missing.** Remaining entries in the delegate map are missing from Qdrant. For each:
1. Deserialize `Memory` → `CbrCase` (via `CbrMemoryDeserializer`)
2. Embed `problem()` if `embeddingModel != null`
3. Build point via `CbrPointBuilder`
4. Batch upsert (call `ensureCollection()` before first upsert if collection didn't exist)

**Error handling:** Each entry is processed independently. On any failure (deserialization, embedding, upsert): log WARNING with `memoryId` and failure reason, increment `errors` count, continue with remaining entries. No per-entry retry — reconciliation is idempotent, so the operator re-runs to pick up failures. This is simpler and more resilient than nested retries during a bulk recovery operation.

Memory bound: O(delegate entries) for the map. For typical CBR volumes per (tenantId, caseType) — hundreds to low thousands of cases — this is well within heap. If volumes grow beyond reasonable heap limits, degrade to batched existence-check: collect a page of IDs from Qdrant, query delegate with an IN clause.

**§3.4 Deserialization (Memory → CbrCase)**

Static utility `CbrMemoryDeserializer` in `memory-qdrant`. Inverse of `QdrantCbrCaseMemoryStore.serializeToMemoryInput()`:

| Memory field | CbrCase field |
|---|---|
| `text()` | `problem` |
| `attributes["solution"]` | `solution` |
| `attributes["outcome"]` | `outcome` |
| `attributes["confidence"]` | `confidence` (via `MemoryAttributeKeys.parseConfidence`) |
| `attributes["cbr.type"]` | discriminator → FeatureVectorCbrCase / PlanCbrCase / TextualCbrCase |
| `attributes["cbr.features"]` | `features` (JSON deserialization) |
| `attributes["cbr.planTrace"]` | `planTrace` (JSON deserialization, PlanCbrCase only) |

Extraction of `entityId`, `domain`, `caseId` comes from the `Memory` record fields directly (not attributes).

**Error handling:** `CbrMemoryDeserializer` returns `Optional<CbrCase>`. On failure — unknown `cbr.type` discriminator, malformed JSON in `cbr.features`/`cbr.planTrace`, missing required attributes — returns `Optional.empty()`. The caller (§3.3 Step 3) logs WARNING with `memoryId` and reason, increments `errors`. A single corrupt delegate entry must not abort reconciliation of the remaining entries.

CBR-specific attribute key constants (`"cbr.type"`, `"cbr.features"`, `"cbr.planTrace"`, `"cbr.caseType"`) must be shared constants in a `CbrAttributeKeys` class in `memory-qdrant`. Both `serializeToMemoryInput()` and `CbrMemoryDeserializer` reference these keys — string literals in both locations is a maintenance hazard.

Note: `reconstructCase()` (the query path, Qdrant → CbrCase) reads Qdrant payload fields (`_cbr_type`, `_features_json`, `_plan_trace_json`) — a separate key namespace from Memory attributes. These two deserialization paths are intentionally separate and must remain so.

**Round-trip test required:** `deserialize(serialize(case))` must produce the original `CbrCase` for all three CBR types (FeatureVectorCbrCase, PlanCbrCase, TextualCbrCase). This is the minimum correctness guarantee against format drift between `serializeToMemoryInput()` and `CbrMemoryDeserializer`.

**§3.5 Result type**

```java
public record ReconciliationResult(
    String caseType,
    String tenantId,
    int orphansRemoved,
    int entriesReindexed,
    int errors
) {}
```

**§3.6 Trigger model**

Admin-triggered only. No scheduled job — reconciliation is a recovery mechanism, not routine. Two paths:

1. **Admin API** — app injects `Instance<CbrReconciliationService>`, calls `reconcile(caseType, tenantId)`.
2. **Post-dimension-migration** — operator sees LOG.warning from `ensureCollection()`, triggers reconciliation per tenant.

Lazy cross-tenant recovery: after a dimension change destroys a collection, the triggering tenant's `store()` succeeds (collection recreated). Other tenants' data is missing until the operator runs reconciliation for each. The `LOG.warning` from `ensureCollection()` must include the collection name and an explicit note that ALL tenants sharing this case type are affected, not just the triggering tenant. Tenant discovery (enumerating affected tenants programmatically) is deferred — the scan SPI's required `tenantId` parameter intentionally prevents cross-tenant enumeration for tenant isolation. Operators discover affected tenants via their tenant management system or direct database query.

### §4 Dimension migration config gate (#78)

**§4.1 Config property**

```java
// In QdrantCbrConfig
@WithDefault("false")
boolean allowDimensionMigration();
```

Config key: `casehub.memory.cbr.qdrant.allow-dimension-migration`. Default `false` — dimension mismatch is a hard error in production.

**§4.2 Exception type**

```java
public class CbrDimensionMismatchException extends RuntimeException {
    private final String collection;
    private final int existingDimension;
    private final int requestedDimension;
}
```

In `memory-qdrant` (Qdrant-specific infrastructure error, not SPI).

**§4.3 ensureCollection() changes**

Hoist `effectiveDim` computation to method top (fixes #79 duplication). Gate dimension mismatch:

- `allowDimensionMigration = false` → throw `CbrDimensionMismatchException`
- `allowDimensionMigration = true` → LOG.warning with reconciliation instructions, delete and recreate collection

### §5 Minor findings (#79)

**§5.1 ScoredCbrCase score validation**

Add `[-1, 1]` range validation in compact constructor:

```java
if (score < -1.0 || score > 1.0)
    throw new IllegalArgumentException("score must be in [-1,1], got: " + score);
```

Add Javadoc: `@param score similarity score in [-1, 1] — 1.0 for filter-only matches, cosine similarity for dense vector search results`.

Cosine similarity is mathematically [-1, 1] for unit vectors. Current NLP embeddings produce [0, 1] in practice (positive-component vectors), but the validation must respect the mathematical range to avoid rejecting valid scores from future embedding models or domains. Validation catches NaN/infinity and out-of-range bugs without constraining valid cosine similarity values.

**§5.2 Duplicate effectiveDim**

Folded into §4.3 — the hoisted computation replaces both duplicated ternaries.

**§5.3 Missing Qdrant test for null embeddingModel + problem-present path**

New test in `QdrantCbrCaseMemoryStoreTest`:
- Store with no embedding model, query with problem text
- Assert INFO log "Dense search unavailable" is emitted (JUL handler capture)
- Assert filter-only results returned, problem text ignored for search

## Module impact

| Module | Changes |
|---|---|
| memory-api | `MemoryCapability.SCAN`, `MemoryScanRequest`, `CaseMemoryStore.scan()` default, `ScoredCbrCase` validation + Javadoc, contract test |
| memory-jpa | `JpaMemoryStore.scan()` implementation |
| memory-sqlite | `SqliteMemoryStore.scan()` implementation |
| memory-qdrant | `CbrReconciliationService`, `CbrMemoryDeserializer`, `CbrAttributeKeys`, `ReconciliationResult`, `CbrDimensionMismatchException`, `QdrantCbrConfig.allowDimensionMigration()`, `CbrCollectionManager` changes, `QdrantCbrBeanProducer` produces reconciliation service, round-trip serialization test, Qdrant-specific test |

No changes to: memory-mem0, memory-graphiti, memory-cbr-inmem, memory-testing, rag-*, inference-*, corpus-*, examples.

## Protocols consulted

- `spi-signature-change-all-impls-same-commit` — default method avoids compilation breakage; no signature change to existing methods
- `spi-default-method-contract-test` — contract test for scan() default
- `persistence-backend-cdi-priority` — applies to `CaseMemoryStore` delegate resolution in `QdrantCbrBeanProducer`: the CDI priority ladder determines which delegate (NoOp / JPA / SQLite) is injected into the reconciliation service
- `module-tier-structure` — scan SPI addition is Tier 1 (memory-api), implementations are Tier 3
- `qdrant-client-library` — direct `io.qdrant:client` usage, no LangChain4j abstraction
- `reactive-blocking-tier-separation` — reconciliation is blocking; no reactive variant in this iteration

## Out of scope

- Reactive `ReactiveCaseMemoryStore.scan()` — add when a reactive consumer needs it (TODO: file issue)
- Scheduled reconciliation — no routine need; admin-triggered covers all recovery scenarios (TODO: file issue)
- Cross-tenant batch reconciliation API — operator iterates tenants; the per-tenant API is the primitive (TODO: file issue)
- Reconciliation metrics/observability — future enhancement, not blocking initial implementation (TODO: file issue)
- Programmatic tenant discovery for post-dimension-change reconciliation — scan SPI's required `tenantId` intentionally prevents cross-tenant enumeration; operators use tenant management system or direct DB query (TODO: file issue)
