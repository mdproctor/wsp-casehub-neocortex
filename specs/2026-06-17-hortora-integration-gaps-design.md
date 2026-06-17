# Hortora Integration Gaps — Design Spec

**Issue:** casehubio/neural-text#36
**Date:** 2026-06-17
**Status:** Draft

## Problem

neural-text#35 made `rag-api` and `rag` consumable by Hortora, but five integration gaps remain. One requires code changes; four are documentation.

The blocking gap: `RagBeanProducer` and `ReactiveRagBeanProducer` hard-inject `CurrentPrincipal` from `casehub-platform-api`. Hortora doesn't provide this bean — CDI fails at startup with an unsatisfied dependency.

## Change 1: Make CurrentPrincipal optional via Instance<>

### Rationale

`CurrentPrincipal` is used for tenant authorization — `MemoryPermissions.assertTenant()` verifies the caller's tenant matches the corpus on every operation. The 3-arg form already no-ops when CDI request context is inactive (background threads, startup). The problem is purely CDI wiring — the bean must be injectable even if the runtime check is already safe.

The `Instance<T>` pattern is already used in the same producer classes for `SparseEmbedder` and `CrossEncoderReranker`. Extending it to `CurrentPrincipal` is consistent and unsurprising.

Security risk assessment: the "silently disabled" scenario requires a casehub deployment that lost its `casehub-platform` dependency (which ships `MockCurrentPrincipal @DefaultBean`). That would break dozens of other things first. For non-casehub consumers like Hortora, absence is deliberate — single-tenant, no tenant authorization needed.

### Bean producer changes

Both `RagBeanProducer` and `ReactiveRagBeanProducer`:

```java
// Before
@Inject CurrentPrincipal currentPrincipal;

// After
@Inject Instance<CurrentPrincipal> currentPrincipalInstance;
```

In each producer method, resolve:

```java
CurrentPrincipal principal = currentPrincipalInstance.isResolvable()
    ? currentPrincipalInstance.get() : null;
```

Pass nullable `CurrentPrincipal` to implementation constructors.

### Implementation class changes

Four classes: `QdrantEmbeddingIngestor`, `HybridCaseRetriever`, `ReactiveQdrantEmbeddingIngestor`, `ReactiveHybridCaseRetriever`.

The `currentPrincipal` field stays typed as `CurrentPrincipal` but becomes nullable. Every `assertTenant()` call site (10 total across all four classes) wraps with a null-guard:

```java
if (currentPrincipal != null) {
    MemoryPermissions.assertTenant(corpus.tenantId(), currentPrincipal, RequestContextCheck.isActive());
}
```

### Test plan

- Add null-principal tests to `QdrantEmbeddingIngestorTest` — verify `ingest()`, `deleteDocument()`, `listDocuments()` work when `currentPrincipal` is null.
- Add null-principal test to `HybridCaseRetrieverTest` — verify `retrieve()` works when `currentPrincipal` is null.
- Existing tests pass unchanged — they provide a principal via `RagTestFixtures.stubPrincipal()`.
- Full build verification: `mvn clean install` passes.

## Documentation gaps (no code changes)

### Gap 2: Ingestion orchestration choice

Hortora's engine has `GardenIndexer` + `GardenIngestionService` that duplicate neural-text's `CorpusIngestionService` orchestrator. Two integration paths:

**Path A — Use CorpusIngestionService:** Provide `CorpusIngestionBinding` CDI beans. neural-text handles startup scanning, filesystem watching (`WatchableChangeSource`), cursor persistence (`CursorStore`), `@Scheduled` polling fallback, and change detection. Drops the most duplicated code from engine.

**Path B — Call EmbeddingIngestor directly:** Keep Hortora's own orchestration. Simpler initial integration, less code dropped.

This is the biggest architectural choice for the engine side. Document both paths with tradeoffs in #36 — the choice is Hortora's.

### Gap 3: engine#521 not relevant to Hortora

casehubio/engine#521 targets existing casehub consumers updating from 3-param to 4-param `retrieve()`. Hortora adopts the new 4-param API directly. Comment on the issue clarifying scope.

### Gap 4: Collection schema upgrade path

Qdrant collection schemas are immutable after creation. If Hortora starts dense-only (no `SparseEmbedder` bean) and later adds SPLADE, the upgrade path is: drop collection + full re-index. Document in #36 so Hortora makes an informed initial mode choice.

### Gap 5: casehub-platform-api transitive dependency

`casehub-rag` depends on `casehub-platform-api` (0.2-SNAPSHOT) for `CurrentPrincipal`, `MemoryPermissions`, and `RequestContextCheck`. This is pulled in transitively. `casehub-platform-api` is zero-dep pure-Java — no framework coupling, safe on any classpath. Document in #36 so Hortora isn't surprised.

## Scope

**In scope:**
- `Instance<CurrentPrincipal>` in `RagBeanProducer` and `ReactiveRagBeanProducer`
- Null-guard on 10 `assertTenant()` call sites across 4 implementation classes
- Tests for null-principal path
- Documentation on gaps 2–5 as comments/updates on #36

**Out of scope:**
- No new modules
- No changes to `rag-api/` (SPI signatures don't mention `CurrentPrincipal`)
- No changes to `rag-testing/` (`InMemoryCaseRetriever` doesn't use `CurrentPrincipal`)
- No changes to `casehub-platform-api`
- No removal of `casehub-platform-api` dependency from `rag/pom.xml`
- No code changes for gaps 2–5
