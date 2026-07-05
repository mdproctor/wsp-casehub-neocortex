# Batch S/XS Issues + #98 Tenant Discovery — Design Spec

Covers: #98, #102, #103, #95, #96, #97, #99, #100, #90

## 1. Tenant Discovery (#98)

### Problem

After a dimension change, `CbrCollectionManager.ensureCollection()` deletes and recreates the Qdrant collection — leaving it empty. The operator must reconcile all affected tenants, but has no way to discover which tenants have CBR data. `MemoryScanRequest` enforces non-null `tenantId` (type-level tenant isolation), so cross-tenant discovery via scan is architecturally impossible.

### Design

Add `discoverTenants()` to `CaseMemoryStore` as a capability-gated cross-tenant admin operation, following the precedent of `eraseEntityAcrossTenants()` which already calls `MemoryPermissions.assertCrossTenantAdmin()`.

```java
// CaseMemoryStore (memory-api)
default Set<String> discoverTenants(String attributeKey, String attributeValue) {
    throw new MemoryCapabilityException(MemoryCapability.DISCOVER_TENANTS, getClass());
}
```

- Both null → all distinct tenantIds. Both non-null → filtered by attribute match. Mixed null/non-null → `IllegalArgumentException`. Same validation pattern as `MemoryScanRequest`'s attributeKey/attributeValue pair.
- New `MemoryCapability.DISCOVER_TENANTS` in the admin tier (after `SCAN`).
- Implementations call `MemoryPermissions.assertCrossTenantAdmin(principal)` before executing.

**Backend implementations:**

| Adapter | Implementation |
|---------|---------------|
| JPA | `SELECT DISTINCT m.tenantId FROM CaseMemoryEntity m WHERE ...` |
| SQLite | `SELECT DISTINCT tenant_id FROM memories WHERE ...` |
| InMemory | stream → filter → map → collect to Set |
| NoOp | Default (throws MemoryCapabilityException) |
| Mem0/Graphiti | Default (throws) — REST backends don't support cross-tenant queries |

**Reconciliation service convenience:**

```java
// CbrReconciliationService
public Set<String> discoverTenants(String caseType) {
    if (delegate == null || !delegate.capabilities().contains(MemoryCapability.DISCOVER_TENANTS)) {
        LOG.info("Tenant discovery unavailable — delegate missing or lacks DISCOVER_TENANTS");
        return Set.of();
    }
    return delegate.discoverTenants(CbrAttributeKeys.CBR_CASE_TYPE, caseType);
}
```

### Why not Qdrant-specific discovery

After dimension migration, the Qdrant collection is empty — there are no tenants to discover. The delegate (`CaseMemoryStore`) is the only source of truth that survives a collection recreation.

## 2. CbrReconciliationService CDI Restructuring (#96 prerequisite)

### Problem

`CbrReconciliationService` is a POJO created by `@Produces` in `QdrantCbrBeanProducer`. CDI interceptors (`@Timed`) don't work on producer-created instances. The platform pattern (JpaMemoryStore, InMemoryMemoryStore, SqliteMemoryStore) uses `@Timed` annotations on CDI-managed beans.

### Design

1. `QdrantCbrBeanProducer` produces only `CbrCollectionManager` as `@Produces @ApplicationScoped`. Retains `QdrantClient` lifecycle management via `@PreDestroy`.
2. `CbrReconciliationService` becomes `@ApplicationScoped` with `@Inject` constructor taking `CbrCollectionManager`, `Instance<EmbeddingModel>`, `Instance<CaseMemoryStore>`, `QdrantCbrConfig`, `MeterRegistry`.
3. `QdrantCbrCaseMemoryStore` becomes `@ApplicationScoped` with `@Inject` constructor taking `CbrCollectionManager`, `Instance<EmbeddingModel>`, `QdrantCbrConfig`, `Instance<CaseMemoryStore>`. Overrides `NoOpCbrCaseMemoryStore @DefaultBean` by normal CDI bean discovery.
4. Remove the two `@Produces` methods for `CbrCaseMemoryStore` and `CbrReconciliationService` from the producer.

### Observability (#96)

Add `micrometer-core` compile dependency to `memory-qdrant/pom.xml`.

**Timing (method-level):**

```java
@Timed(value = "casehub.cbr.reconciliation", histogram = true,
       extraTags = {"operation", "reconcile"})
public ReconciliationResult reconcile(String caseType, String tenantId) { ... }

@Timed(value = "casehub.cbr.reconciliation", histogram = true,
       extraTags = {"operation", "reconcileAll"})
public List<ReconciliationResult> reconcileAll(String caseType, Set<String> tenantIds) { ... }
```

**Counters (programmatic, per-invocation):**

```java
meterRegistry.counter("casehub.cbr.reconciliation.orphans", "caseType", caseType).increment(orphansRemoved);
meterRegistry.counter("casehub.cbr.reconciliation.reindexed", "caseType", caseType).increment(reindexed);
meterRegistry.counter("casehub.cbr.reconciliation.errors", "caseType", caseType).increment(errors);
```

## 3. Cross-Tenant Batch Reconciliation (#97)

Builds on #96 (CDI restructuring) and #98 (tenant discovery).

```java
// CbrReconciliationService
public List<ReconciliationResult> reconcileAll(String caseType, Set<String> tenantIds) {
    List<ReconciliationResult> results = new ArrayList<>();
    for (String tenantId : tenantIds) {
        try {
            results.add(reconcile(caseType, tenantId));
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Reconciliation failed for tenant " + tenantId, e);
            results.add(new ReconciliationResult(caseType, tenantId, 0, 0, 1));
        }
    }
    return results;
}

public List<ReconciliationResult> reconcileAll(String caseType) {
    Set<String> tenants = discoverTenants(caseType);
    if (tenants.isEmpty()) {
        LOG.info("No tenants discovered for caseType=" + caseType);
        return List.of();
    }
    return reconcileAll(caseType, tenants);
}
```

Partial failures are captured per-tenant, not propagated. The result list carries the error count for each tenant.

## 4. ReactiveCaseMemoryStore Parity (#95)

### Gap

`ReactiveCaseMemoryStore` is missing four methods that exist on `CaseMemoryStore`:

| Method | Type | Status |
|--------|------|--------|
| `scan(MemoryScanRequest)` | I/O | Missing |
| `capabilities()` | Metadata | Missing |
| `requireCapability(MemoryCapability)` | Metadata | Missing |
| `discoverTenants(String, String)` | I/O (new) | Missing |

### Design

Add all four as default methods:

```java
// Reactive I/O — Uni-wrapped, default throws capability exception
default Uni<List<Memory>> scan(MemoryScanRequest request) {
    return Uni.createFrom().failure(
        new MemoryCapabilityException(MemoryCapability.SCAN, getClass()));
}

default Uni<Set<String>> discoverTenants(String attributeKey, String attributeValue) {
    return Uni.createFrom().failure(
        new MemoryCapabilityException(MemoryCapability.DISCOVER_TENANTS, getClass()));
}

// Metadata — synchronous, no Uni
default Set<MemoryCapability> capabilities() { return Set.of(); }

default void requireCapability(MemoryCapability capability) {
    if (!capabilities().contains(capability))
        throw new MemoryCapabilityException(capability, getClass());
}
```

**BlockingToReactiveBridge** — add delegation for all four methods. `scan` and `discoverTenants` use `runSubscriptionOn(Infrastructure.getDefaultWorkerPool())`. `capabilities` and `requireCapability` delegate directly (synchronous).

## 5. Case Enrichment Pipeline SPI (#90)

### Design constraints (from codebase evidence)

- `CbrAttributeKeys` lives in `memory-qdrant` (package `io.casehub.neocortex.memory.cbr.qdrant`), not `memory-api`. The SPI in memory-api cannot reference CBR-specific attribute keys for routing.
- Existing decorators (CorrectiveCaseRetriever, QueryExpandingCaseRetriever) are concrete classes with constructor-injected `@Delegate @Any` delegates.
- `CaseMemoryStore` has ~10 methods including defaults. A @Decorator must override ALL methods — default methods on the interface call `this` (the decorator), not the delegate.

### SPI (memory-api)

```java
public interface CaseEnrichmentStep {
    boolean appliesTo(MemoryInput input);
    MemoryInput enrich(MemoryInput input);
    default int priority() { return 0; }
}
```

- `appliesTo(MemoryInput)` instead of `caseType()` — application-tier steps define their own routing. A CBR enrichment step in QuarkMind's module can check `input.attributes().get("cbr.caseType")` using the `CbrAttributeKeys` constant it already depends on.
- `priority()` — lower runs first. Deterministic ordering regardless of CDI discovery order.

### Decorator (memory/)

Concrete class following the project's established decorator pattern:

```java
@Decorator
@Priority(Interceptor.Priority.APPLICATION)
public class CaseEnrichmentDecorator implements CaseMemoryStore {

    private final CaseMemoryStore delegate;
    private final List<CaseEnrichmentStep> sortedSteps;

    @Inject
    CaseEnrichmentDecorator(@Delegate @Any CaseMemoryStore delegate,
                            Instance<CaseEnrichmentStep> steps) {
        this.delegate = delegate;
        this.sortedSteps = steps.stream()
            .sorted(Comparator.comparingInt(CaseEnrichmentStep::priority))
            .toList();
    }

    @Override
    public String store(MemoryInput input) {
        return delegate.store(applyEnrichment(input));
    }

    @Override
    public StoreAllResult storeAll(List<MemoryInput> inputs) {
        return delegate.storeAll(inputs.stream().map(this::applyEnrichment).toList());
    }

    // All other methods: explicit delegation to delegate
    @Override public List<Memory> query(MemoryQuery q) { return delegate.query(q); }
    @Override public int erase(EraseRequest r) { return delegate.erase(r); }
    @Override public int eraseEntity(String e, String t) { return delegate.eraseEntity(e, t); }
    @Override public void eraseById(String m, String e, String t) { delegate.eraseById(m, e, t); }
    @Override public int eraseEntityAcrossTenants(String e, Set<String> t) { return delegate.eraseEntityAcrossTenants(e, t); }
    @Override public Set<MemoryCapability> capabilities() { return delegate.capabilities(); }
    @Override public void requireCapability(MemoryCapability c) { delegate.requireCapability(c); }
    @Override public List<Memory> scan(MemoryScanRequest r) { return delegate.scan(r); }
    @Override public Set<String> discoverTenants(String k, String v) { return delegate.discoverTenants(k, v); }

    private MemoryInput applyEnrichment(MemoryInput input) {
        if (sortedSteps.isEmpty()) return input;
        MemoryInput result = input;
        for (CaseEnrichmentStep step : sortedSteps) {
            if (step.appliesTo(result)) {
                try {
                    result = step.enrich(result);
                } catch (Exception e) {
                    LOG.log(Level.WARNING, "Enrichment step " + step.getClass().getName() + " failed", e);
                }
            }
        }
        return result;
    }
}
```

**Placement rationale:** In `memory/` (CDI wiring module), not a new module. The decorator has no dependencies beyond CDI + memory-api. With no `CaseEnrichmentStep` beans registered, the sorted list is empty and `applyEnrichment` is a no-op. Avoids adding a 31st module for a single decorator.

## 6. Batch Upserts (#102)

In `CbrReconciliationService.reconcile()`, replace the single-batch upsert with chunked batches:

```java
if (!batch.isEmpty()) {
    for (int i = 0; i < batch.size(); i += DEFAULT_PAGE_SIZE) {
        List<PointStruct> chunk = batch.subList(i, Math.min(i + DEFAULT_PAGE_SIZE, batch.size()));
        collectionManager.client().upsertAsync(collection, chunk).get();
    }
}
```

The `reindexed` counter moves from the per-point loop to after confirmed upsert, counted by batch contents — not incremented speculatively before the gRPC call.

## 7. Minor Review Findings (#103)

| # | Finding | Action |
|---|---------|--------|
| 1 | ScoredCbrCase NEGATIVE_INFINITY not tested | Add symmetric boundary test |
| 2 | JpaMemoryStore scan tests use JUnit assertions | Convert to AssertJ |
| 3 | SqliteMemoryStore @AfterEach cleanup | Skip — @BeforeEach is sufficient |
| 4 | QdrantClient not closed in test @AfterEach | Add tearDown closing QdrantClient |
| 5 | Error-counting path untested | Add test with Memory missing `solution` attribute |
| 6 | Counter before confirmed upsert | Addressed in #102 |
| 7 | Fully qualified Qdrant gRPC types | Import `Common.Filter`, `Common.PointId` consistently |
| 8 | CbrMemoryDeserializer RuntimeException control flow | `parseFeatures`/`parsePlanTrace` return null on `JsonProcessingException` with warning log; switch cases check null → yield null → `Optional.empty()` |

## 8. FlatCorpusStore Hidden Path Filtering (#99)

### FlatCorpusStore.list()

Replace `Files.walk()` + stream filter with `Files.walkFileTree()` + `SimpleFileVisitor`:

- `preVisitDirectory`: return `SKIP_SUBTREE` for `.`-prefixed directory names. This avoids descending into `.git/` (and stat'ing ~9K files) entirely.
- `visitFile`: skip `.`-prefixed file names. Then apply existing `_` path-prefix filter on the relative path.
- Existing `_` semantics preserved (root-level path prefix only — `validatePath` checks `path.startsWith("_")`).

### FlatChangeSource.onRawEvent()

Add hidden-segment filter:

```java
private static boolean containsHiddenSegment(String relativePath) {
    return relativePath.startsWith(".") || relativePath.contains("/.");
}
```

Applied alongside the existing `_` check: `if (relativePath.startsWith("_") || containsHiddenSegment(relativePath)) return;`

## 9. ColBERT Quantization Config (#100)

### RagConfig addition

```java
ColbertQuantizationConfig colbertQuantization();

interface ColbertQuantizationConfig {
    @WithDefault("NONE")
    DenseQuantization type();

    @WithDefault("true")
    boolean alwaysRam();
}
```

Reuses existing `DenseQuantization` enum (NONE, BINARY, SCALAR).

### QdrantEmbeddingIngestor.ensureCollection()

When building ColBERT VectorParams (lines 282-289), apply quantization if configured:

```java
VectorParams.Builder colbertBuilder = VectorParams.newBuilder()
    .setSize(embedder.colbertDimension().orElseThrow())
    .setDistance(Distance.Cosine)
    .setMultivectorConfig(MultiVectorConfig.newBuilder()
        .setComparator(MultiVectorComparator.MaxSim).build());

if (config.colbertQuantization().type() == DenseQuantization.SCALAR) {
    colbertBuilder.setQuantizationConfig(QuantizationConfig.newBuilder()
        .setScalar(ScalarQuantization.newBuilder()
            .setType(QuantizationType.Int8)
            .setAlwaysRam(config.colbertQuantization().alwaysRam())
            .build())
        .build());
} else if (config.colbertQuantization().type() == DenseQuantization.BINARY) {
    colbertBuilder.setQuantizationConfig(QuantizationConfig.newBuilder()
        .setBinary(BinaryQuantization.newBuilder()
            .setAlwaysRam(config.colbertQuantization().alwaysRam())
            .build())
        .build());
}
```

No oversampling — ColBERT MAX_SIM scoring doesn't benefit from it.
