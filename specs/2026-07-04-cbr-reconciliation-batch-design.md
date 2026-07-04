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

**§2.1 JpaMemoryStore** — native SQL against PostgreSQL jsonb:

```sql
SELECT * FROM memory_entry
WHERE tenant_id = :tenantId
  AND (:domain IS NULL OR domain = :domain)
  AND attributes::jsonb->>:key = :value
  AND memory_id > :cursor
ORDER BY memory_id ASC
LIMIT :limit
```

`->>` is a top-level key lookup, not a path expression — dotted keys like `cbr.caseType` work correctly. No GIN index needed; reconciliation is infrequent.

Declares `MemoryCapability.SCAN` in `capabilities()`.

When `attributeKey` is null (no attribute filter), omit the JSON clause — scan all entries for the tenant.

**§2.2 SqliteMemoryStore** — `json_extract` with quoted key syntax:

```sql
SELECT * FROM memory_entry
WHERE tenant_id = :tenantId
  AND (:domain IS NULL OR domain = :domain)
  AND json_extract(attributes, '$."' || :key || '"') = :value
  AND memory_id > :cursor
ORDER BY memory_id ASC
LIMIT :limit
```

Quoted key syntax (`$."cbr.caseType"`) prevents SQLite from interpreting `.` as a JSON path separator.

Declares `MemoryCapability.SCAN` in `capabilities()`.

**§2.3 NoOpCaseMemoryStore** — does NOT override `scan()`. Inherits the throwing default. The no-op is a sentinel — reconciliation calls `requireCapability(SCAN)` first and gets a clear `MemoryCapabilityException`, not a silent empty result.

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

Before either phase:
- `delegate == null` → return no-op result (Qdrant-only mode, nothing to reconcile)
- `delegate.requireCapability(MemoryCapability.SCAN)` → fail fast
- Collection doesn't exist → skip phase 1, proceed to phase 2 (reindex creates the collection)

**§3.3 Phase 1 — Orphan cleanup (Qdrant → delegate)**

Scroll all Qdrant points for the collection, filtered by `tenantId` payload. For each point:

1. Extract `entityId`, `domain`, `caseId` from payload
2. Query delegate: `MemoryQuery.forEntity(entityId, domain, tenantId).withCaseId(caseId).withLimit(1)`
3. If empty → orphan. Collect point UUID for batch deletion.

Delete orphans in bulk at end of each scroll page. Configurable scroll page size (default 100).

**§3.4 Phase 2 — Reindex missing (delegate → Qdrant)**

Scan delegate: `MemoryScanRequest(tenantId, null, "cbr.caseType", caseType, pageSize, cursor)`.

For each page of `Memory` records:

1. Compute deterministic point UUID: `CbrPointBuilder.pointId(tenantId, caseType, memory.caseId())`
2. Batch-check existence in Qdrant (scroll with ID filter, or `getAsync`)
3. For missing points: deserialize `Memory` → `CbrCase`, embed `problem()` if `embeddingModel != null`, build point, batch upsert

**§3.5 Deserialization (Memory → CbrCase)**

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

**§3.6 Result type**

```java
public record ReconciliationResult(
    String caseType,
    String tenantId,
    int orphansRemoved,
    int entriesReindexed,
    int errors
) {}
```

**§3.7 Trigger model**

Admin-triggered only. No scheduled job — reconciliation is a recovery mechanism, not routine. Two paths:

1. **Admin API** — app injects `Instance<CbrReconciliationService>`, calls `reconcile(caseType, tenantId)`.
2. **Post-dimension-migration** — operator sees LOG.warning from `ensureCollection()`, triggers reconciliation per tenant.

Lazy cross-tenant recovery: after a dimension change destroys a collection, the triggering tenant's `store()` succeeds (collection recreated). Other tenants' data is missing until the operator runs reconciliation for each.

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

Add `[0, 1]` range validation in compact constructor:

```java
if (score < 0.0 || score > 1.0)
    throw new IllegalArgumentException("score must be in [0,1], got: " + score);
```

Add Javadoc: `@param score similarity score in [0, 1] — 1.0 for filter-only matches, cosine similarity for dense vector search results`.

Current implementations all produce scores in [0, 1]: filter-only = 1.0, cosine on normalized embeddings = [0, 1]. Validation catches bugs without constraining valid usage.

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
| memory | `NoOpCaseMemoryStore.scan()` override |
| memory-jpa | `JpaMemoryStore.scan()` implementation |
| memory-sqlite | `SqliteMemoryStore.scan()` implementation |
| memory-qdrant | `CbrReconciliationService`, `CbrMemoryDeserializer`, `ReconciliationResult`, `CbrDimensionMismatchException`, `QdrantCbrConfig.allowDimensionMigration()`, `CbrCollectionManager` changes, `QdrantCbrBeanProducer` produces reconciliation service, Qdrant-specific test |

No changes to: memory-mem0, memory-graphiti, memory-cbr-inmem, memory-testing, rag-*, inference-*, corpus-*, examples.

## Protocols consulted

- `spi-signature-change-all-impls-same-commit` — default method avoids compilation breakage; no signature change to existing methods
- `spi-default-method-contract-test` — contract test for scan() default
- `persistence-backend-cdi-priority` — reconciliation service follows CDI priority ladder
- `module-tier-structure` — scan SPI addition is Tier 1 (memory-api), implementations are Tier 3
- `qdrant-client-library` — direct `io.qdrant:client` usage, no LangChain4j abstraction
- `reactive-blocking-tier-separation` — reconciliation is blocking; no reactive variant in this iteration

## Out of scope

- Reactive `ReactiveCaseMemoryStore.scan()` — add when a reactive consumer needs it
- Scheduled reconciliation — no routine need; admin-triggered covers all recovery scenarios
- Cross-tenant batch reconciliation API — operator iterates tenants; the per-tenant API is the primitive
- Reconciliation metrics/observability — future enhancement, not blocking initial implementation
