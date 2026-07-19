# Batch S/XS CBR Fixes — Design Spec

**Date:** 2026-07-19
**Branch:** issue-130-batch-sx-cbr-fixes
**Covers:** #130, #143, #128, #162, #141, #155

Six small issues batched on one branch. All feed back into CaseHub foundation and apps.

---

## #130 — Examples aggregator POM

**Problem:** `casehubio/examples` lists each neocortex example individually. Other repos (work, qhorus, eidos) already have aggregator POMs so the parent can reference a single `<module>`.

**Design:** Create `examples/pom.xml` — aggregator-only, no dependencies, no plugins. Parent = `casehub-neocortex-parent`, packaging = `pom`, three module entries: `example-text-analysis`, `example-rag-pipeline`, `example-cbr`.

**Follow-up:** File issue on `casehubio/examples` to collapse three neocortex entries into one.

---

## #162 — InMemoryCbrCaseMemoryStore.clearAll()

**Root cause:** `InMemoryCbrCaseMemoryStore` is `@ApplicationScoped` — persists across `@QuarkusTest` methods. No way to reset state between tests. `purge()` requires `maxAgeDays >= 1` / `maxCasesPerType >= 1` — can't clear fresh data. Documented in GE-20260716-986cd1.

**Design:** Add `clearAll()` to the concrete `InMemoryCbrCaseMemoryStore` and `ReactiveInMemoryCbrCaseMemoryStore` — not to the SPI. Test isolation is a test concern. Clears both `schemas` map and `cases` list.

**Contract test hook:** Add `protected void clearStore()` to `CbrCaseMemoryStoreContractTest` with a no-op default. In-memory test subclasses override it. Call in `@BeforeEach` to ensure test isolation.

---

## #141 — memory-cbr-jpa Map→FeatureValue migration

**Problem:** `JpaCbrCaseMemoryStore.deserializeMap()` returns `Map<String, Object>`, then `reconstruct()` round-trips through `FeatureValue.toFeatureMap()`. The intermediate raw map is unnecessary and fragile — type information is lost and re-inferred.

**Design:** Rename `deserializeMap` → `deserializeFeatures`. Return `Map<String, FeatureValue>` by applying `FeatureValue.toFeatureMap()` internally. Remove the `MAP_TYPE` field. Update `reconstruct()` to use the clean return type directly. Store path stays unchanged (`toRawMap` → JSON is correct for JSONB column compatibility).

---

## #143 — Configurable learning rate per case type

**Problem:** `CbrOutcome.DEFAULT_LEARNING_RATE = 0.2` is global. Different domains need different speeds: AML (conservative, low rate) vs game strategy (fast-moving, high rate).

**Design:** Add `Double learningRate()` to `CbrFeatureSchema`. Nullable — `null` means use `CbrOutcome.DEFAULT_LEARNING_RATE`. Schema is already per-caseType and already available in all store implementations at `recordOutcome` time.

Changes:
- `CbrFeatureSchema`: add `learningRate` field, validate in [0,1] when non-null
- `InMemoryCbrCaseMemoryStore.recordOutcome()`: look up schema, use `schema.learningRate()` if present
- `JpaCbrCaseMemoryStore.recordOutcome()`: same
- `QdrantCbrCaseMemoryStore.recordOutcome()` (reactive): same
- Contract test: add test with custom learning rate verifying EMA convergence speed differs

`CbrFeatureSchema` is a record. Adding a field is a source-breaking change (constructor call sites). Pre-release — breaking changes cost nothing. All existing callers add the new parameter. Provide a static factory that defaults learningRate to null for convenience.

---

## #128 — Graded similarity scoring for structured fields

**Problem:** `CbrSimilarityScorer.scoreDetailed()` hard-skips `CategoricalList`, `NumericList`, `NestedObject`, and `ObjectList` fields before checking caller-provided `LocalSimilarityFunction` overrides. This means overrides for structured fields are silently ignored.

**Design:** Move the structured-field skip to after the override lookup. If a caller provides a `LocalSimilarityFunction` override for a structured field, use it. If no override, skip the field (same as today — default is 0 contribution, not 0 similarity). This unblocks domain-specific scoring without building generalised list/object similarity.

The change is minimal: in `scoreDetailed()`, check for override before the `instanceof` skip. Same change in both overloads (with and without `dtwAbandonCostThreshold`).

---

## #155 — Supersession status + audit metadata SPI

**Problem:** `supersede()` and `reinstate()` write metadata but it's unreachable through the SPI. Audit consumers must bypass the SPI and query storage directly.

**Design:** Two new methods on `CbrCaseMemoryStore` + `ReactiveCbrCaseMemoryStore`:

```java
SupersessionStatus getSupersessionStatus(String caseId, String tenantId);
List<String> findSupersededCases(String tenantId, MemoryDomain domain);
```

New value type in `memory-api`:

```java
public record SupersessionStatus(
    boolean superseded,
    Instant supersededAt,
    String supersedingCaseId,
    String reason
) {
    public static final SupersessionStatus NOT_SUPERSEDED =
        new SupersessionStatus(false, null, null, null);
}
```

Backend implementations:
- **InMemory:** scan `StoredCase` fields
- **JPA:** JPQL query on `CbrCaseEntity`
- **Qdrant:** payload filter query (supersededAt IS NOT NULL)
- **NoOp:** return `NOT_SUPERSEDED` / empty list

Contract test: add tests for both methods — verify status after supersede, after reinstate, and that findSupersededCases filters correctly.

---

## Dependency Order

No inter-issue dependencies. All can be implemented in any order. Natural grouping:

1. **#130** (examples POM) — standalone, zero code impact
2. **#143** (learning rate) — changes `CbrFeatureSchema` record; do this early since #128 and #155 also touch the scorer/store
3. **#128** (structured field overrides) — changes `CbrSimilarityScorer`
4. **#162** (clearAll) — changes `InMemoryCbrCaseMemoryStore`
5. **#141** (JPA deserialize) — changes `JpaCbrCaseMemoryStore`
6. **#155** (supersession queries) — adds SPI methods; do last since it touches every backend

---

## Cross-repo ripple

- **casehubio/examples:** follow-up issue to collapse neocortex entries (#130)
- **All CBR consumers (engine, blocks, IoT, quarkmind, life, clinical):** `CbrFeatureSchema` constructor changes (#143) — source-breaking, compile-time caught. Pre-release, no backward compat required.
- **Parent docs:** `docs/repos/casehub-neocortex.md` update for new SPI methods (#155)
