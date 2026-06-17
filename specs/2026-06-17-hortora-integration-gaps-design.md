# Hortora Integration Gaps — Design Spec

**Issue:** casehubio/neural-text#36
**Date:** 2026-06-17
**Status:** Draft (rev 2 — revised after review)

## Architectural boundary shift

neural-text#35 made `rag-api` and `rag` consumable by Hortora. This was a deliberate boundary change — the #35 issue showed that Hortora/engine duplicates significant code from `rag/` (Qdrant integration, ingestion orchestration, cursor management, change detection). The duplication is worth eliminating.

However, #35 did not update the architectural documents. The following now-stale constraints must be corrected as part of this work:

- **ARC42STORIES §1 stakeholders:** Hortora row says "takes inference-\* only" — now also takes `rag-api`, `rag`, `rag-testing`
- **ARC42STORIES §2 constraints:** "Hortora shares inference-\* only — rag-\* modules are casehub-specific" — no longer true
- **ARC42STORIES §4 layer table:** L6 (`rag-api`, `rag-testing`) and L7 (`rag`) marked "casehub only" — should be "✅ yes" (shared)
- **ARC42STORIES §12 risks:** "Hortora's usage pattern conflicts with SPI design" — update to reflect that rag-\* adoption is now the primary integration surface
- **PLATFORM.MD deep-dive** (`casehubio/parent: docs/repos/casehub-neural-text.md`): "The rag-\* modules are casehub-specific — Hortora does not take them" — cross-repo change, file issue on casehubio/parent

## Problem

Five integration gaps remain after #35. One requires code changes (tenancy optionality); one requires a design position (ingestion orchestration); three are documentation.

The blocking gap: `RagBeanProducer` and `ReactiveRagBeanProducer` hard-inject `CurrentPrincipal` from `casehub-platform-api`. Hortora doesn't provide this bean — CDI fails at startup with an unsatisfied dependency.

## Change 1: TenantGuard — deployment-time tenancy policy

### Why not null-guards

The obvious approach — `Instance<CurrentPrincipal>`, resolve to null, null-guard every `assertTenant()` call — has a structural problem. `SparseEmbedder` being absent means "use dense-only mode" (a feature degradation). `CurrentPrincipal` being absent means "skip tenant authorization" (a security degradation). Same CDI mechanism, fundamentally different semantic. Treating a security control the same as a feature toggle is a category error.

Additionally, 10 scattered `if (currentPrincipal != null)` guards are fragile by construction. Every future method must remember to guard. One missed guard is a `NullPointerException` for Hortora or a silent security bypass for casehub.

### Design: TenantGuard

Capture the deployment-time decision (multi-tenant vs single-tenant) as a strategy object, constructed once at producer time:

```java
@FunctionalInterface
interface TenantGuard {
    void assertTenant(String tenantId);

    static TenantGuard of(CurrentPrincipal principal) {
        return principal == null
            ? tenantId -> {}
            : tenantId -> MemoryPermissions.assertTenant(
                tenantId, principal, RequestContextCheck.isActive());
    }
}
```

Package-private in `io.casehub.rag.runtime`. Not part of the public API.

**Why not push null-safety into `MemoryPermissions`:** `MemoryPermissions` lives in `casehub-platform-api`. The platform should maintain its strong contract — `CurrentPrincipal` is never null in a request context. The optionality belongs at the neural-text boundary where the deployment-time decision is made.

### Bean producer changes

Both `RagBeanProducer` and `ReactiveRagBeanProducer`:

```java
// Before
@Inject CurrentPrincipal currentPrincipal;

// After
@Inject Instance<CurrentPrincipal> currentPrincipalInstance;
```

In each producer method, construct the guard once:

```java
CurrentPrincipal principal = currentPrincipalInstance.isResolvable()
    ? currentPrincipalInstance.get() : null;
TenantGuard tenantGuard = TenantGuard.of(principal);
```

Pass `TenantGuard` (never null) to implementation constructors instead of `CurrentPrincipal`.

### Implementation class changes

Four classes: `QdrantEmbeddingIngestor`, `HybridCaseRetriever`, `ReactiveQdrantEmbeddingIngestor`, `ReactiveHybridCaseRetriever`.

Replace the `CurrentPrincipal` field with `TenantGuard`. Replace every `assertTenant()` call site (10 total: 4 + 1 + 4 + 1) with:

```java
tenantGuard.assertTenant(corpus.tenantId());
```

No null checks. No conditionals. The guard either checks or no-ops based on construction-time decision.

**CDI proxy correctness:** The `CurrentPrincipal` captured in the lambda is a CDI client proxy (injected into an `@ApplicationScoped` producer). The proxy resolves to the correct `@RequestScoped` instance on each call. `RequestContextCheck.isActive()` evaluates at call time inside the lambda, not construction time. Both behaviours are preserved.

### Security risk assessment

In casehub deployments: `casehub-platform` ships `MockCurrentPrincipal @DefaultBean` — `CurrentPrincipal` always resolves. Production has OIDC or Qhorus inbound — always resolves. The no-op guard can only fire for consumers who deliberately chose not to provide a principal.

### Test plan

All four test classes get null-principal coverage:

- `QdrantEmbeddingIngestorTest` — verify `ingest()`, `deleteDocument()`, `deleteCorpus()`, `listDocuments()` work with `TenantGuard.of(null)`
- `HybridCaseRetrieverTest` — verify `retrieve()` works with `TenantGuard.of(null)`
- `ReactiveQdrantEmbeddingIngestorTest` — verify `ingest()`, `deleteDocument()`, `deleteCorpus()`, `listDocuments()` work with `TenantGuard.of(null)`
- `ReactiveHybridCaseRetrieverTest` — verify `retrieve()` works with `TenantGuard.of(null)`

Existing tests pass unchanged — they provide a principal via `RagTestFixtures.stubPrincipal()`, which produces a non-null `TenantGuard`.

Full build verification: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install` passes.

## Gap 2: Ingestion orchestration — position taken

Hortora/engine has `GardenIndexer` + `GardenIngestionService` that duplicate neural-text's `CorpusIngestionService` orchestrator. Two integration paths exist.

**Recommendation: Path A — use CorpusIngestionService.**

Hortora/engine is Quarkus 3.32.2 (same platform version as neural-text). All framework dependencies CorpusIngestionService requires (`@ApplicationScoped`, `@Scheduled`, `@Observes StartupEvent`, `WatchableChangeSource`) are available. The #35 issue body listed CorpusIngestionService under "Already Works" with the note "Hortora provides `CorpusIngestionBinding` via CDI."

Hortora provides a `CorpusIngestionBinding` CDI bean wired to its garden filesystem. CorpusIngestionService handles startup scanning, filesystem watching, cursor persistence, change detection. This drops the most duplicated code from Hortora/engine.

Path B (call `EmbeddingIngestor` directly) remains available for non-Quarkus consumers, but Hortora is on Quarkus and should use Path A.

No code changes needed in neural-text for this gap. Document the recommendation in #36.

## Gap 3: engine#521 scope clarification

casehubio/engine#521 ("update CaseRetriever call sites for PayloadFilter parameter") targets existing casehub consumers updating from 3-param to 4-param `retrieve()`. Hortora adopts the new 4-param API directly — this issue is not relevant to them. Comment on the issue clarifying scope.

## Gap 4: Collection schema upgrade path

Qdrant collection schemas are immutable after creation. If Hortora starts dense-only (no `SparseEmbedder` bean) and later adds SPLADE, the upgrade path is: drop collection + full re-index. Document in #36 so Hortora makes an informed initial mode choice.

## Gap 5: casehub-platform-api transitive dependency

`casehub-rag` depends on `casehub-platform-api` (0.2-SNAPSHOT) for `CurrentPrincipal`, `MemoryPermissions`, and `RequestContextCheck`. This is pulled in transitively.

**Version coordination risk:** `casehub-platform-api` is currently 0.2-SNAPSHOT — Hortora would track casehub's unreleased platform. If `CurrentPrincipal`'s interface changes, Hortora's build breaks even though they don't use tenancy. This creates a coupling that should be documented explicitly.

`casehub-platform-api` is zero-dep pure-Java — no framework coupling, safe on any classpath. The risk is version coordination, not classpath pollution. Mitigation: `casehub-platform-api` should eventually publish stable releases to decouple consumer timelines. Document this coupling and mitigation in #36.

## ARC42STORIES updates (in scope)

| Section | Current | Updated |
|---------|---------|---------|
| §1 stakeholders, Hortora row | "SPLADE sparse embeddings + CrossEncoderReranker — takes inference-\* only" | "SPLADE, CrossEncoderReranker (inference-\*) + EmbeddingIngestor, CaseRetriever, CorpusIngestionService (rag-\*)" |
| §2 constraints | "Hortora shares inference-\* only — rag-\* modules are casehub-specific" | "Hortora shares inference-\* and rag-\* — rag modules support optional tenancy for non-casehub consumers" |
| §4 layer table, L6 | "casehub only" | "✅ yes" |
| §4 layer table, L7 | "casehub only" | "✅ yes" |
| §12 risk table, Hortora row | "C3 complete — SPI design validated; Hortora integration pending" | "rag-\* consumption enabled (#35); tenancy optionality shipped (#36); Hortora adoption pending" |

**Cross-repo:** File issue on casehubio/parent to update `docs/repos/casehub-neural-text.md` — "The rag-\* modules are casehub-specific — Hortora does not take them" is stale.

## Scope

**In scope:**
- `TenantGuard` strategy in `rag/runtime` (new class, package-private)
- `Instance<CurrentPrincipal>` in `RagBeanProducer` and `ReactiveRagBeanProducer`
- `TenantGuard` replaces `CurrentPrincipal` field in 4 implementation classes
- 10 `assertTenant()` call sites → `tenantGuard.assertTenant()` (no null-checks)
- Null-principal tests in all 4 test classes
- ARC42STORIES updates (§1, §2, §4, §12)
- Documentation on gaps 2–5 in #36
- File issue on casehubio/parent to update PLATFORM.MD deep-dive

**Out of scope:**
- No new modules
- No changes to `rag-api/` (SPI signatures don't mention `CurrentPrincipal`)
- No changes to `rag-testing/` (`InMemoryCaseRetriever` doesn't use `CurrentPrincipal`)
- No changes to `casehub-platform-api` (`MemoryPermissions` keeps its strong contract)
- No removal of `casehub-platform-api` dependency from `rag/pom.xml` — still used by `TenantGuard`
