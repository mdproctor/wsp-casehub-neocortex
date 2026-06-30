# CBR Retrieval Architecture — Unified Knowledge Retrieval in neural-text

**Issue:** casehubio/neural-text#20
**Date:** 2026-06-30
**Status:** Draft
**Background:** [CBR Paradigms and Analysis](2026-06-30-cbr-paradigms-and-analysis.md)
**Refs:** casehubio/parent CBR-CAPABILITY.md, casehubio/engine#478, casehubio/platform#87

---

## 1. Problem

CaseHub has three independent "find similar things" systems — `CaseMemoryStore` (platform), `CaseRetriever` (neural-text), and CBR (gap) — that share no infrastructure despite doing the same underlying work: embed, index, search by similarity, return ranked results. CBR retrieval (the Retrieve step of the CBR cycle) does not exist; the platform runs degenerate CBR with Retain and Reuse only. Textual CBR already works via `CaseMemoryStore.query(question, RELEVANCE)`, but Feature-Vector and Plan-Based CBR have no SPI or implementation.

## 2. Decision

Build CBR retrieval as a natural extension of the existing `CaseMemoryStore` memory system. Add CBR-specific SPIs and types in `casehub-neural-text` that compose with `CaseMemoryStore` (which stays in `casehub-platform`) via delegation. The Qdrant-backed CBR implementation naturally belongs in neural-text alongside the existing Qdrant/embedding infrastructure.

**Why not CaseRetriever?** Issue #20 and engine#478 originally proposed `CaseRetriever` as the CBR retrieval SPI. Design analysis revealed these are fundamentally different contracts: `CaseRetriever` is a RAG SPI operating on text queries against document corpora (`RetrievalQuery` + `CorpusRef` → `RetrievedChunk`). CBR retrieval operates on structured feature vectors against case memories — different input types, output types, storage models, and similarity functions. `CbrCaseMemoryStore.retrieveSimilar()` is the right abstraction because CBR retrieval is a memory operation, not a corpus operation. Engine#478's integration point changes from `CaseRetriever` to `CbrCaseMemoryStore.retrieveSimilar()`.

### 2.1 What Goes in neural-text

| Module | Contents |
|--------|----------|
| `memory-api` | `CbrCaseMemoryStore`, `ReactiveCbrCaseMemoryStore`, `CbrCase` hierarchy, `CbrQuery`, `CbrFeatureSchema`, `FeatureField` (dep: `platform-api`) |
| `memory` | `NoOpCbrCaseMemoryStore @DefaultBean`, `BlockingToReactiveCbrBridge` |
| `memory-cbr-inmem` | In-memory `CbrCaseMemoryStore` implementation (`@Alternative @Priority(2)`, for testing + dev) |
| `memory-qdrant` | Qdrant-backed `CbrCaseMemoryStore` (Approach 3: payload filters + dense vector) |
| `memory-testing` | `CbrCaseMemoryStoreContractTest` |

### 2.2 What Stays in Platform

All existing memory infrastructure remains in `casehub-platform` unchanged:

- `platform-api`: `CaseMemoryStore`, `ReactiveCaseMemoryStore`, `GraphCaseMemoryStore`, `CbrCaseEntry`, `MemoryInput`, `Memory`, `MemoryQuery`, `MemoryPermissions`, all related types
- `platform` (mock module): `NoOpCaseMemoryStore @DefaultBean`, `BlockingToReactiveBridge`
- `memory-inmem/`: `InMemoryMemoryStore`
- `memory-jpa/`: `JpaMemoryStore`
- `memory-sqlite/`: `SqliteMemoryStore`
- `memory-mem0/`: `Mem0CaseMemoryStore`
- `memory-graphiti/`: `GraphitiCaseMemoryStore`
- `testing/`: `CaseMemoryStoreContractTest`

Also stays: `CurrentPrincipal`, `Preferences`, `Path`, `EndpointRegistry`, `GroupMembershipProvider`, agent providers, streams.

### 2.3 Dependencies

`memory-api` (neural-text) depends on `platform-api` for `MemoryInput`, `MemoryDomain`, `MemoryPermissions`, and `CurrentPrincipal`. Package: `io.casehub.memory.cbr`. No circular dependency — neural-text depends on platform, never the reverse.

`CbrCaseMemoryStore` does NOT extend `CaseMemoryStore`. It is a standalone SPI that internally delegates regular memory storage to an injected `CaseMemoryStore`. This avoids CDI bean displacement conflicts — a `CbrCaseMemoryStore` bean (e.g., Qdrant) coexists with any platform `CaseMemoryStore` bean (e.g., JPA) without ambiguity or priority displacement.

Consumers that need CBR retrieval add `casehub-memory-api` alongside `casehub-platform-api`. Existing `CaseMemoryStore` imports and usage are unchanged.

---

## 3. CbrCase Type Hierarchy

Open interface (not sealed — extensible for future paradigms without modifying the base):

```java
// memory-api
public interface CbrCase {
    String problem();       // NL text — embedded for text similarity (common denominator)
    String solution();      // NL summary — human-readable
    String outcome();       // result label (nullable)
    Double confidence();    // reliability [0.0, 1.0] (nullable)

    MemoryInput toMemoryInput(String entityId, MemoryDomain domain,
                              String tenantId, String caseId);
}
```

Base fields are universal across all CBR paradigms. `problem()` is always NL text — it serves as the fallback retrieval path that works with every backend. `toMemoryInput()` encapsulates the serialization contract (§3.4) — callers never manually construct `MemoryInput` attributes for CBR cases. Follows the existing `CbrCaseEntry.toMemoryInput()` pattern in `platform-api`.

### 3.1 TextualCbrCase

Replaces existing `CbrCaseEntry`. No additional fields.

```java
// memory-api
public record TextualCbrCase(String problem, String solution,
                              String outcome, Double confidence) implements CbrCase {}
```

### 3.2 FeatureVectorCbrCase

Adds structured features for precise matching.

```java
// memory-api
public record FeatureVectorCbrCase(String problem, String solution,
                                    String outcome, Double confidence,
                                    Map<String, Object> features) implements CbrCase {}
```

### 3.3 PlanCbrCase

Adds plan composition for CHEF-style adaptation.

```java
// engine-api
public record PlanCbrCase(String problem, String solution,
                          String outcome, Double confidence,
                          Map<String, Object> features,
                          List<PlanTrace> planTrace) implements CbrCase {}

public record PlanTrace(
    String bindingName,
    String capabilityName,
    String workerName,
    String stepOutcome,
    int priority,
    Map<String, Object> parameters
) {}
```

`PlanTrace` uses only `String` and `Map` — no dependency on engine runtime types.

### 3.4 Serialization

All subtypes serialize to `MemoryInput` for `CaseMemoryStore`:

| CbrCase field | MemoryInput mapping |
|--------------|---------------------|
| `problem()` | `text` |
| `solution()` | `attributes["solution"]` |
| `outcome()` | `attributes["outcome"]` |
| `confidence()` | `attributes["confidence"]` |
| `features` | `attributes["cbr.features"]` (JSON) |
| `planTrace` | `attributes["cbr.planTrace"]` (JSON) |
| discriminator | `attributes["cbr.type"]` — `"textual"`, `"feature-vector"`, `"plan"` |

Deserialization is backend-internal — each `CbrCaseMemoryStore` implementation reconstructs the correct subtype from its native storage format. The `Class<C>` parameter on `retrieveSimilar()` guides type selection. The `cbr.type` discriminator attribute enables JSON-based backends (Qdrant) to use Jackson polymorphic deserialization at runtime without compile-time coupling to specific subtypes. No centralized `from(Memory)` factory — avoids circular dependencies between `memory-api` and modules that define paradigm-specific subtypes (e.g., `PlanCbrCase` in `engine-api`).

---

## 4. Feature Schema

Describes the shape of a feature vector per case type. Drives index creation and query construction.

```java
// memory-api
public record CbrFeatureSchema(String caseType, List<FeatureField> fields) {}

public interface FeatureField {
    String name();
    record Categorical(String name) implements FeatureField {}
    record Numeric(String name, double min, double max) implements FeatureField {}
    record Text(String name) implements FeatureField {}
}
```

| Field Type | Index Type | Query Operation |
|-----------|-----------|-----------------|
| `Categorical` | Qdrant keyword payload index | Exact match filter |
| `Numeric` | Qdrant float payload index | Range filter |
| `Text` | Dense embedding | Cosine similarity |

Applications provide a schema per case type alongside `CbrFeatureVectorBuilder` (engine#478). Without a schema, backends fall back to text-only similarity on `problem()`.

### 4.1 Schema Registration Lifecycle

- **When:** `@Startup` CDI bean. Applications register schemas at startup alongside their `CbrFeatureVectorBuilder`.
- **Idempotency:** Last-write-wins for the same `caseType`. Re-registration replaces the schema.
- **Schema evolution:** Additive — new fields create new indexes. Existing cases without new fields simply don't match on them. Removed fields: indexes remain but no queries use them.
- **Store-before-register:** Falls back to text-only similarity on `problem()`. No schema = no payload filters.
- **Qdrant index creation:** Asynchronous. `registerSchema()` returns immediately. Queries before indexes are ready fall back to full scan (slower but correct).

### 4.2 Embedding Model

- `CbrCase.problem()` is always embedded as the **primary dense vector** (one per Qdrant point).
- `FeatureField.Text` features are stored as **payload text** with Qdrant full-text payload indexes for keyword filtering — they are NOT separately embedded.
- One dense vector per point (from `problem()`). Per-feature embeddings (multiple named vectors) deferred to future enhancement.
- Similarity ranking: payload filters (categorical exact-match, numeric range) reduce the candidate set → dense vector similarity on `problem()` ranks within it.

---

## 5. CbrQuery

```java
// memory-api (io.casehub.memory.cbr)
public record CbrQuery(
    String tenantId,                  // mandatory — tenant isolation (non-null)
    MemoryDomain domain,              // mandatory — domain scoping (non-null)
    String caseType,
    Map<String, Object> features,
    int topK,
    double minSimilarity,
    Instant notBefore                 // nullable
) {
    public CbrQuery {
        Objects.requireNonNull(tenantId, "tenantId required");
        Objects.requireNonNull(domain, "domain required");
        Objects.requireNonNull(caseType, "caseType required");
    }

    public static CbrQuery of(String tenantId, MemoryDomain domain,
                               String caseType, Map<String, Object> features, int topK) {
        return new CbrQuery(tenantId, domain, caseType, features, topK, 0.0, null);
    }
}
```

**No `entityIds` by design.** CBR retrieval is cross-entity within a tenant — the point is to find similar past cases across ALL entities (e.g., all past games in QuarkMind, all past investigations in AML), not just one entity's history. This differs from `MemoryQuery` which scopes to specific entities. `MemoryPermissions.assertTenant()` enforces the tenant boundary.

---

## 6. CbrCaseMemoryStore SPI

Standalone SPI — does NOT extend `CaseMemoryStore`. Implementations internally delegate regular memory storage to an injected `CaseMemoryStore` from platform.

**Why not extend?** The `GraphCaseMemoryStore extends CaseMemoryStore` pattern works within one repo where you pick one backend (Graphiti subsumes everything). With CBR in neural-text and base memory in platform, the `extends` relationship creates CDI bean displacement conflicts: a `CbrCaseMemoryStore` bean would also be a `CaseMemoryStore` bean, causing priority displacement with JPA/SQLite/inmem, dual `@DefaultBean` ambiguity between `NoOpCaseMemoryStore` and `NoOpCbrCaseMemoryStore`, and `@DefaultBean` removal cascades. Composition via delegation avoids all of these.

```java
// memory-api (io.casehub.memory.cbr)
public interface CbrCaseMemoryStore {

    void registerSchema(CbrFeatureSchema schema);

    String store(CbrCase cbrCase, String entityId, MemoryDomain domain,
                 String tenantId, String caseId);

    <C extends CbrCase> List<C> retrieveSimilar(CbrQuery query, Class<C> caseType);
}

// memory-api (io.casehub.memory.cbr)
public interface ReactiveCbrCaseMemoryStore {

    Uni<Void> registerSchema(CbrFeatureSchema schema);

    Uni<String> store(CbrCase cbrCase, String entityId, MemoryDomain domain,
                      String tenantId, String caseId);

    <C extends CbrCase> Uni<List<C>> retrieveSimilar(CbrQuery query, Class<C> caseType);
}
```

### 6.1 Typed Store Path

`store(CbrCase, ...)` is the single entry point for CBR case storage. Implementations:
1. Call `cbrCase.toMemoryInput(entityId, domain, tenantId, caseId)` to serialize
2. Delegate to the injected `CaseMemoryStore` for durable memory storage (JPA, SQLite, etc.)
3. Optionally index in their own backend for CBR-specific retrieval (Qdrant payload indexes, in-memory maps)

Applications call only `CbrCaseMemoryStore.store()` — never manually construct `MemoryInput` for CBR cases.

### 6.2 Schema Validation

`retrieveSimilar()` validates query features against the registered `CbrFeatureSchema` before dispatching to the backend:
- Categorical fields: value must be `String`
- Numeric fields: value must be `Number`, within `[min, max]`
- Text fields: value must be `String`
- Unknown fields (not in schema): ignored (forward compatible)

Throws `IllegalArgumentException` with a descriptive message on type mismatch. Enforced by `CbrCaseMemoryStoreContractTest`.

### 6.3 Bridge and No-Op

`BlockingToReactiveCbrBridge @DefaultBean` in `neural-text/memory` wraps blocking `CbrCaseMemoryStore` as `ReactiveCbrCaseMemoryStore`, following the same `runSubscriptionOn(workerPool)` pattern as `BlockingToReactiveBridge` in platform.

`NoOpCbrCaseMemoryStore @DefaultBean` in `neural-text/memory` — `store()` delegates to injected `CaseMemoryStore` only (no CBR indexing), `retrieveSimilar()` returns `List.of()`. No CDI conflict with `NoOpCaseMemoryStore` in platform — they are independent types.

### 6.4 Backend Matrix

| Backend | Repo | Implements | CBR Capability |
|---------|------|-----------|----------------|
| cbr-inmem (NEW) | neural-text | `CbrCaseMemoryStore` | In-memory field matching (testing + dev) |
| Qdrant (NEW) | neural-text | `CbrCaseMemoryStore` | Full: payload filters + dense + hybrid |
| inmem | platform | `CaseMemoryStore` | Text only |
| JPA | platform | `CaseMemoryStore` | Text only (extend later) |
| SQLite | platform | `CaseMemoryStore` | Text only (extend later) |
| mem0 | platform | `CaseMemoryStore` | Text similarity via vector embedding |
| graphiti | platform | `GraphCaseMemoryStore` | Graph proximity (extend later) |

CBR backends coexist with any platform `CaseMemoryStore` backend — no priority displacement.

---

## 7. Qdrant-Backed Memory (memory-qdrant)

New module. Implements `CbrCaseMemoryStore` using Qdrant with the recommended Approach 3 from the analysis document (payload filters + optional dense vector). Delegates regular memory storage to the platform's `CaseMemoryStore` (injected via CDI) — `memory-qdrant` handles only CBR-specific indexing and retrieval, not the full `CaseMemoryStore` contract.

**Storage:** `store()` calls `delegate.store(cbrCase.toMemoryInput(...))` for durable memory, then indexes the case as a Qdrant point. Categorical features → keyword payload indexes. Numeric features → float payload indexes. `problem()` text → dense vector. Full case record (including plan traces) in payload JSON.

**Retrieval:** `CbrFeatureSchema` drives query construction — categorical features become exact-match `PayloadFilter.Eq` filters, numeric features become `PayloadFilter.Range` filters (see §8.1 prerequisite), text features use Qdrant full-text payload indexes for keyword filtering. Dense vector search on `problem()` embedding ranks the filtered set by semantic similarity.

**Single dense vector model:** Each Qdrant point has one dense vector from `problem()` text. No per-feature embeddings — categorical/numeric features use payload filters, not vectors. This keeps the model simple and avoids multi-vector scoring complexity.

**Shared infrastructure with RAG:** Qdrant client, embedding models, `PayloadFilter` algebra, collection management, tenant isolation. Both `memory-qdrant` and `rag` modules are in the same repo and share these components.

---

## 8. Module Structure

```
neural-text/
  memory-api/              ← CBR SPI + types (Tier 1 pure Java; dep: platform-api)
  memory/                  ← NoOpCbrCaseMemoryStore @DefaultBean, BlockingToReactiveCbrBridge
  memory-cbr-inmem/        ← In-memory CbrCaseMemoryStore (@Alternative @Priority(2))
  memory-qdrant/           ← NEW: Qdrant hybrid search + CBR payload filters
  memory-testing/          ← CbrCaseMemoryStoreContractTest
  rag-api/                 ← CaseRetriever, EmbeddingIngestor, CorpusStore (unchanged)
  rag/                     ← Qdrant RAG wiring, hybrid RRF (unchanged)
  rag-crag/                ← Corrective RAG (unchanged)
  rag-expansion/           ← Query expansion (unchanged)
  rag-tika/                ← Tika parsing (unchanged)
  rag-testing/             ← RAG test stubs (unchanged)
  corpus-api/              ← CorpusStore SPIs (unchanged)
  corpus/                  ← Zip4j implementation (unchanged)
  inference-*/             ← ONNX models (unchanged)
```

Existing memory backends (JPA, SQLite, inmem, mem0, graphiti) remain in `casehub-platform` unchanged. See §2.2.

### 8.1 Shared Infrastructure

| Component | Used by |
|-----------|---------|
| Qdrant Java client | memory-qdrant, rag |
| Dense embedding model (LangChain4j) | memory-qdrant (for `problem()` embedding), rag |
| SPLADE sparse embedder | memory-qdrant (optional), rag |
| Cross-encoder reranker | memory-qdrant (optional), rag |
| `PayloadFilter` algebra | memory-qdrant (for CbrQuery), rag |
| `RrfFusion` | memory-qdrant (optional), rag |
| Collection management + tenant isolation | memory-qdrant, rag |

**Prerequisite — PayloadFilter extension:** The current `PayloadFilter` sealed hierarchy in `rag-api` supports only `Eq(String, String)` and `In(String, List<String>)` — no numeric operations. CBR requires range filters for numeric features. Before `memory-qdrant` can implement numeric feature matching, `PayloadFilter` must be extended with `Gte(String field, double value)`, `Lte(String field, double value)`, and `Range(String field, double min, double max)`. This is a change to the existing `rag-api` module, tracked as an issue in §11.

---

## 9. Implementation Tiers

### Tier 1 — Feature-Vector CBR (immediate)

- `memory-api`: `CbrCase` interface (with `toMemoryInput()`), `TextualCbrCase`, `FeatureVectorCbrCase`, `CbrQuery`, `CbrFeatureSchema`, `CbrCaseMemoryStore` (standalone — does not extend `CaseMemoryStore`), `ReactiveCbrCaseMemoryStore`
- `memory`: `NoOpCbrCaseMemoryStore @DefaultBean` (delegates to injected `CaseMemoryStore`), `BlockingToReactiveCbrBridge`
- `memory-cbr-inmem`: `CbrCaseMemoryStore` implementation (in-memory field matching)
- `memory-qdrant`: `CbrCaseMemoryStore` implementation (Approach 3)
- `memory-testing`: `CbrCaseMemoryStoreContractTest` — both `memory-cbr-inmem` and `memory-qdrant` must pass
- Prerequisite: `PayloadFilter` extension with numeric range support (§8.1)

Enables engine#478: `CbrFeatureVectorBuilder` → `CbrCaseMemoryStore.retrieveSimilar()` → `ImplementationRoutingStrategy`.

### Tier 2 — Plan-Based CBR

- `PlanCbrCase` + `PlanTrace` in engine-api
- `CaseOutcomeObserver` impl that serializes plan structure at case close
- Plan trace stored in Qdrant payload, retrievable alongside features

Enables CHEF-style plan adaptation: retrieve similar plans, identify substitutable components.

### Tier 3 — POCBR / Structural CBR (future)

- Graph-based case representation
- Workflow similarity via graph edit distance or GNN embeddings
- Potentially graphiti backend for structural similarity

---

## 10. Platform Document Updates

| Document | Change |
|----------|--------|
| **PLATFORM.md** Capability Ownership | Add "CBR retrieval" owner → `casehub-neural-text/memory-api` (`CbrCaseMemoryStore`). Base "Agent memory" stays in `casehub-platform-api`. |
| **PLATFORM.md** Boundary Rule | "CBR retrieval belongs in neural-text via `CbrCaseMemoryStore`" (not `CaseRetriever`). `CaseRetriever` remains the RAG retrieval SPI. |
| **PLATFORM.md** Cross-Repo Dependency Map | Add `casehub-memory-api` → engine (for `CbrCaseMemoryStore.retrieveSimilar()` at plan creation) |
| **CBR-CAPABILITY.md** Retrieve owner | `casehub-neural-text/memory-api` — `CbrCaseMemoryStore.retrieveSimilar()` (not `CaseRetriever`) |
| **CBR-CAPABILITY.md** Component Map | Retrieve via `CbrCaseMemoryStore`; base `CaseMemoryStore` still in platform |

---

## 11. Issues to File

| Repo | Title | Depends On |
|------|-------|-----------|
| neural-text | `memory-api` — CBR SPI types (`CbrCaseMemoryStore`, `CbrCase`, `CbrQuery`, `CbrFeatureSchema`) | — |
| neural-text | `PayloadFilter` extension — add `Gte`, `Lte`, `Range` numeric filter records to sealed hierarchy | — |
| neural-text | `memory-qdrant` — Qdrant-backed `CbrCaseMemoryStore` with payload filters + dense vector | `memory-api`, PayloadFilter |
| neural-text | `memory-cbr-inmem` — in-memory `CbrCaseMemoryStore` for testing + dev | `memory-api` |
| neural-text | `memory-testing` — `CbrCaseMemoryStoreContractTest` | `memory-api` |
| neural-text | `memory` — `NoOpCbrCaseMemoryStore @DefaultBean` + `BlockingToReactiveCbrBridge` | `memory-api` |
| engine | `PlanTrace` type in engine-api | — |
| engine | Retain plan traces at case close (`CaseOutcomeObserver` impl) | PlanTrace |
| engine | Update engine#478 — integration point is `CbrCaseMemoryStore.retrieveSimilar()`, not `CaseRetriever` | `memory-api` |
| platform | JPA memory backend — add CBR feature-field matching support (extend later) | `memory-api` |
| platform | SQLite memory backend — add CBR feature-field matching support (extend later) | `memory-api` |
| parent | Update PLATFORM.md — add CBR retrieval capability ownership | `memory-api` |
| parent | Update CBR-CAPABILITY.md — Retrieve owner is `CbrCaseMemoryStore`, not `CaseRetriever` | `memory-api` |
