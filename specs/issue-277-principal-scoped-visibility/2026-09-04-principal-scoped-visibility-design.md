# Principal-Scoped Memory Visibility

**Issue:** casehubio/neocortex#277
**Depends on:** casehubio/platform#271 (Principal identity model), casehubio/neocortex#269 (principalId on EdgeInput/NodeInput)
**Unblocks:** casehubio/neocortex#254 (wire visibility into TemporalIndex)
**Related:** casehubio/neocortex#278 (knowledge representation model — Thing, dynamic types)

## Purpose

Within a tenant, different principals (humans and agents) have different cognitive perspectives. Alice's private observation about Bob is not Bob's to see. Shared family knowledge is everyone's. The memory stores currently have no concept of ownership or visibility — every memory in a tenant is visible to every query.

This spec adds principal ownership and visibility to the memory subsystem so that queries return only what the querying principal is allowed to see.

---

## §1 Subject — Typed Entity Reference

**Rename `entityId` → `subjectId` across the codebase.** The current name is vague. "Subject" says what it means: who or what the memory is about.

### §1.1 Subject Record

**Location:** `io.casehub.neocortex.memory` in `memory-api`

```java
public record Subject(String type, String id) {
    public Subject {
        Objects.requireNonNull(type, "type required");
        Objects.requireNonNull(id, "id required");
        type = type.strip().toLowerCase();
        id = id.strip();
        if (type.isEmpty()) throw new IllegalArgumentException("type must not be blank");
        if (id.isEmpty()) throw new IllegalArgumentException("id must not be blank");
    }

    public static Subject of(String type, String id) {
        return new Subject(type, id);
    }
}
```

`type` is a free-form string — not an enum. The LLM discovers new types at runtime ("person", "project", "research-topic", "concern", "incident"). No recompile needed. The type vocabulary grows as the agent learns.

Type is normalized to lowercase on construction — `Subject.of("Person", "alice")` and `Subject.of("person", "alice")` produce identical subjects. This prevents LLM casing inconsistencies from creating phantom type splits.

`Subject` is a reference to a Thing (#278). When the formal Thing model lands, Subject becomes `Thing.ref()` or similar. The `(type, id)` pair is already compatible.

### §1.2 entityId → subjectId Rename

Every occurrence of `entityId` in the memory and CBR subsystems becomes `subjectId`. The Subject record replaces the bare `String`. No backward-compatible constructors or shims — this is a clean break. Every call site must construct `Subject` explicitly with a meaningful type. The compiler errors are the feature: they force each caller to answer "what is this entity?"

| Current | New |
|---|---|
| `MemoryInput.entityId` (String) | `MemoryInput.subject` (Subject) |
| `MemoryQuery.entityIds` (List\<String>) | `MemoryQuery.subjects` (List\<Subject>) |
| `Memory.entityId` (String) | `Memory.subject` (Subject) |
| `GraphMemoryQuery.entityIds` (List\<String>) | `GraphMemoryQuery.subjects` (List\<Subject>) |
| `GraphMemoryQuery.entityTypes` (Set\<String>) | `GraphMemoryQuery.subjectTypes` (Set\<String>) |
| `CaseMemoryStore.eraseEntity(String entityId, String tenantId)` | `CaseMemoryStore.eraseSubject(Subject subject, String tenantId)` |
| `CaseMemoryStore.eraseEntityAcrossTenants(String entityId, Set\<String> tenantIds)` | `CaseMemoryStore.eraseSubjectAcrossTenants(Subject subject, Set\<String> tenantIds)` |
| `CaseMemoryStore.eraseById(String memoryId, String entityId, String tenantId)` | `CaseMemoryStore.eraseById(String memoryId, Subject subject, String tenantId)` |
| `CbrCaseMemoryStore.store(CbrCase, String caseType, String entityId, MemoryDomain, String tenantId, String caseId, Path scope)` | `CbrCaseMemoryStore.store(CbrCase, String caseType, Subject subject, MemoryDomain, String tenantId, String caseId, Path scope, String principalId, Set\<String> sharedWith)` |
| `CbrCaseMemoryStore.eraseEntity(String entityId, String tenantId)` | `CbrCaseMemoryStore.eraseSubject(Subject subject, String tenantId)` |
| `EraseRequest.entityId` (String) | `EraseRequest.subject` (Subject) |
| Converter classes (ExperienceEvents, RelationshipEvents, AffectEvents, etc.) | Update all `entityId` references |

### §1.3 Storage Representation

In persistent stores (SQLite, JPA, Qdrant), Subject is stored as two fields:

| Store | subject_type column | subject_id column |
|---|---|---|
| SQLite | `TEXT NOT NULL` | existing `entity_id` column renamed |
| JPA/PostgreSQL | `VARCHAR NOT NULL` | existing `entity_id` column renamed |
| Qdrant payload | `subjectType` (keyword-indexed) | `subjectId` (keyword-indexed) |

Migration: existing rows have no `subject_type`. The ALTER TABLE migration adds the column with `DEFAULT 'unknown'` to satisfy NOT NULL for existing data. A data migration script backfills meaningful types from domain metadata (e.g., domain=`experience`/`relationship`/`mood`/`engagement` → type=`agent`; domain=`affect` → type=`node`). The `DEFAULT 'unknown'` is a migration artifact for existing rows only — no Java code constructs `Subject.of("unknown", ...)`.

**Reachability:** records with `subject_type = 'unknown'` (or any type) remain fully queryable because queries match on `subject_id` only — `subject_type` is not a query filter (see §2.3). Direct callers that store memories outside the converter paths (e.g., `GardenOutcomeService` with domain=`knowledge`, strategy-learning domain callers) will have their call sites updated to construct explicit Subject types as part of the clean break, and the migration script backfills their existing data accordingly. The exact type mapping for each non-converter domain is determined during implementation when each caller is migrated.

---

## §2 Visibility Model

### §2.1 Fields

Two new fields on `MemoryInput`:

```java
String principalId       // owner — null means truly shared (no owner)
Set<String> sharedWith   // additional principals who can see — empty by default
```

The `principalId` value is sourced from `CurrentPrincipal.actorId()` at runtime. It is a bare `String` — consistent with how the platform already represents principal identity. The formal `Principal` type (#276) can refine this later without breaking the memory SPI.

### §2.2 Three Visibility States

| State | principalId | sharedWith | Who sees it |
|---|---|---|---|
| **Truly shared** | null | empty | Everyone in the tenant |
| **Private** | "alice" | empty | Only Alice |
| **Owned + shared** | "alice" | {"bob"} | Alice and Bob |

Backward compatibility: existing memories have `principalId = null, sharedWith = empty` → truly shared. No behaviour change for existing code.

### §2.3 Query-Time Filtering

`MemoryQuery` gains an optional `callerPrincipalId` field:

```java
public record MemoryQuery(
    List<Subject> subjects,     // was entityIds
    MemoryDomain domain,
    String tenantId,
    String caseId,
    String question,
    int limit,
    Instant since,
    MemoryOrder order,
    String callerPrincipalId    // NEW — nullable, who is querying
) { ... }
```

`GraphMemoryQuery` gains the same field, and `entityTypes` is renamed to `subjectTypes` for consistency with the Subject model:

```java
public record GraphMemoryQuery(
    String tenantId,
    List<Subject> subjects,     // was entityIds
    MemoryDomain domain,
    String question,
    int limit,
    Instant since,
    Instant validAt,
    Set<String> subjectTypes,   // was entityTypes — graph-engine result type filter
    MemoryResultType resultType,
    String callerPrincipalId    // NEW — nullable, who is querying
) { ... }
```

**Subject query matching:** queries match on `Subject.id` only — `Subject.type` is **not** a query filter. The `subjects` list in `MemoryQuery` and `GraphMemoryQuery` is matched against `subject_id` in the store. This means:
- A query for `Subject.of("agent", "alice")` matches all memories with `subject_id = "alice"`, regardless of their stored `subject_type`
- Pre-existing data with `subject_type = 'unknown'` remains reachable by querying with the original entity ID
- Domain already scopes the result set — `Subject.type` would add redundant filtering on top of domain
- `Subject.type` is valuable as write-side enrichment (forces callers to name the entity kind) and read-side metadata (query results carry the type)
- `GraphMemoryQuery.subjectTypes` is a separate, opt-in filter that operates on the graph engine's entity categorization, gated by the `ENTITY_TYPE_FILTER` capability

When `callerPrincipalId` is set, the store filters results:
- Include memories where `principalId` is null (truly shared)
- Include memories where `principalId` equals `callerPrincipalId` (caller owns it)
- Include memories where `sharedWith` contains `callerPrincipalId` (shared with caller)
- Exclude all other memories

When `callerPrincipalId` is null (not set), no filtering — all memories visible. This preserves backward compatibility.

Both `CaseMemoryStore.query(MemoryQuery)` and `GraphCaseMemoryStore.graphQuery(GraphMemoryQuery)` apply this filtering. The filtering logic is identical — the difference is only in how the query reaches the store.

### §2.4 CBR Integration

`CbrQuery` does **not** currently have a `principalId` field — unlike `EdgeInput` and `NodeInput` which gained `principalId` in #269, `CbrQuery` was not part of that change. This spec adds it:

```java
public record CbrQuery(
    // ... existing 16 fields ...
    String callerPrincipalId    // NEW — nullable, who is querying
) { ... }
```

`CbrCaseMemoryStore` changes:
- `store(...)` gains `principalId` (String) and `sharedWith` (Set\<String>) parameters
- `retrieveSimilar(...)` respects visibility based on `CbrQuery.callerPrincipalId`

`CbrQueryTranslator.toIdentityFilter()` gains a visibility clause when `callerPrincipalId` is non-null:

```java
if (query.callerPrincipalId() != null) {
    Filter.Builder visibility = Filter.newBuilder();
    // truly shared — no principalId set (or absent on pre-existing data)
    visibility.addShould(Filter.newBuilder()
        .addMust(ConditionFactory.isEmpty("principalId")).build());
    // caller owns it
    visibility.addShould(Filter.newBuilder()
        .addMust(ConditionFactory.matchKeyword("principalId",
            query.callerPrincipalId())).build());
    // shared with caller
    visibility.addShould(Filter.newBuilder()
        .addMust(ConditionFactory.matchKeywords("sharedWith",
            List.of(query.callerPrincipalId()))).build());
    builder.addMust(visibility.build());
}
```

**Why `isEmpty` not `isNull`:** Pre-existing CBR cases have no `principalId` field in their Qdrant payload — the field is entirely absent, not null. Qdrant's `isNull` only matches fields that exist with a null value; `isEmpty` matches both absent fields and null values. Using `isNull` would silently exclude all pre-existing CBR data from principal-scoped queries.

### §2.5 Storage Representation

| Store | principalId | sharedWith |
|---|---|---|
| SQLite | `TEXT` column (nullable) | `TEXT` column (nullable, **JSON array**) |
| JPA/PostgreSQL | `VARCHAR` column (nullable) | `JSON` column |
| Qdrant payload | `principalId` (keyword-indexed) | `sharedWith` (keyword array, matchKeywords) |
| In-memory | Direct field access + filter in `query()` |

`sharedWith` is always stored as a JSON array (e.g. `["bob","charlie"]`). Comma-separated storage has no safe way to do exact-match set membership in SQL — substring matching produces false positives (e.g. LIKE '%bob%' matches "bobby").

### §2.6 Erase Semantics

Erase operations (`erase`, `eraseEntity`, `eraseEntityAcrossTenants`, `eraseById`) are **visibility-unaware by design**. A tenant admin can erase any memory regardless of `principalId`/`sharedWith`. This is intentional: GDPR Art.17 right to erasure requires the data controller to delete data regardless of who created it within the tenant.

The asymmetry (can't read private memories, but can erase them) is correct — read visibility is a cognitive concern; erasure is a compliance/admin concern.

### §2.7 Visibility Immutability

Visibility (`principalId` and `sharedWith`) is set at creation time and cannot be changed after storage. `CaseMemoryStore` is append-only at the SPI level — there is no update operation.

If a principal needs to change a memory's visibility, the workflow is: query the memory, erase the original (requires `ERASE_BY_ID` capability), re-store with updated visibility. This is not atomic and the `createdAt` timestamp will reflect the re-store time.

This limitation is acceptable because:
- Visibility decisions are typically known at creation time (the agent decides private vs shared as part of the cognitive process that generates the memory)
- Re-sharing is a low-frequency operation — agents rarely need to declassify memories
- Adding `updateVisibility()` would require partial-update support across all adapters, including REST-backed ones (Mem0, Graphiti) where metadata updates may not be straightforward
- Future work can add an `UPDATE_VISIBILITY` capability if the need materializes

---

## §3 MemoryInput and Memory Changes

### §3.1 MemoryInput (Write Path)

```java
public record MemoryInput(
    Subject subject,            // was: String entityId
    MemoryDomain domain,
    String tenantId,
    String caseId,
    String text,
    Map<String, String> attributes,
    Confidence confidence,
    Double pleasure,
    Double arousal,
    Double dominance,
    String principalId,         // NEW — owner, nullable
    Set<String> sharedWith      // NEW — additional viewers, empty by default
) {
    public MemoryInput {
        // ... existing validations ...
        // Normalize blank principalId to null (truly shared).
        // Prevents cross-store inconsistency: Qdrant isEmpty matches "",
        // but SQLite IS NULL and InMemory == null do not.
        principalId = (principalId != null && principalId.isBlank()) ? null : principalId;
        // Strip and filter sharedWith: remove nulls and blanks, strip whitespace.
        sharedWith = sharedWith == null ? Set.of() : sharedWith.stream()
            .filter(s -> s != null && !s.isBlank())
            .map(String::strip)
            .collect(Collectors.toUnmodifiableSet());
    }
}
```

Factory methods:
- `MemoryInput.of(Subject subject, MemoryDomain domain, String tenantId, String text)` — truly shared (null principalId, empty sharedWith)
- `MemoryInput.ownedBy(Subject subject, MemoryDomain domain, String tenantId, String text, String principalId)` — private by default
- `withPrincipalId(String)`, `withSharedWith(Set<String>)` builders

No backward-compatible constructors — every call site migrates to `Subject`.

### §3.2 Memory (Read Path)

```java
public record Memory(
    String memoryId,
    Subject subject,            // was: String entityId
    MemoryDomain domain,
    String tenantId,
    String caseId,
    String text,
    Map<String, String> attributes,
    Instant createdAt,
    Confidence confidence,
    Double pleasure,
    Double arousal,
    Double dominance,
    String principalId,         // NEW — owner, nullable
    Set<String> sharedWith      // NEW — additional viewers
) { ... }
```

Round-trip integrity: a memory stored with `Subject.of("person", "alice")` returns with `subject().type() == "person"` and `subject().id() == "alice"`. The current `String entityId` loses the type — `Subject` fixes this.

### §3.3 storeAll

`CaseMemoryStore.storeAll(List<MemoryInput>)` is mechanically affected by the MemoryInput change. The default implementation delegates to `store()` — no additional changes needed in the interface. Contract tests that construct MemoryInput directly must be updated.

---

## §4 Converter Updates

All event converters that produce `MemoryInput` must pass through the `principalId`:

| Converter | Subject | principalId source |
|---|---|---|
| `ExperienceEvents.toMemoryInput()` | `Subject.of("agent", event.agentId())` | `event.agentId()` |
| `RelationshipEvents.toMemoryInput()` | `Subject.of("agent", event.agentId())` | `event.agentId()` |
| `ReflectionEvents.toMemoryInput()` | `Subject.of("agent", event.agentId())` | `event.agentId()` |
| `MoodEvents.toMemoryInput()` | `Subject.of("agent", event.agentId())` | `event.agentId()` |
| `EngagementEvents.toMemoryInput()` | `Subject.of("agent", event.agentId())` | `event.agentId()` |
| `AffectEvents.toMemoryInput()` | `Subject.of("node", nodeId)` | `null` (no owner — PAD changes are node-intrinsic, not agent-scoped) |

Agent-originated memories are private by default — the agent owns its own experiences, reflections, moods, and engagement records.

`AffectEvents` uses a MindMap node UUID as entityId. The subject type is `"node"` — these are emotional state snapshots on a MindMap node, triggered by PAD changes. The `principalId` is null because PAD changes are node-intrinsic: the node's emotional state belongs to the node itself, not to any particular agent. MindMap node visibility is handled separately by `PerspectivalResolver` — the memory just records the state.

---

## §5 Store Implementation Changes

### §5.1 InMemoryMemoryStore

Filter in `query()`: iterate stored memories, apply the visibility predicate from §2.3. Straightforward — the in-memory store already iterates all memories.

### §5.2 SqliteMemoryStore

Add `principal_id` and `shared_with` columns. `shared_with` stored as JSON array. Extend the query SQL with a visibility WHERE clause:

```sql
WHERE (principal_id IS NULL
    OR principal_id = :callerPrincipalId
    OR EXISTS (SELECT 1 FROM json_each(shared_with) WHERE value = :callerPrincipalId))
```

For FTS5 queries, the visibility filter applies as a post-filter on the result set (FTS5 doesn't support arbitrary WHERE clauses in the MATCH expression). **Post-filter truncation applies:** FTS5 returns ranked results up to `limit`, then visibility filtering may reduce the count below `limit`. This is consistent with the REST-backed adapters (§5.5, §5.6) — non-FTS SQLite queries apply visibility in the WHERE clause before LIMIT, so they return the full requested count.

### §5.3 JpaMemoryStore

Add `principalId` and `sharedWith` columns to the entity. `sharedWith` stored as JSON. Extend the JPQL/native query with the visibility predicate. JSON containment check uses database-specific functions (PostgreSQL `@>` operator or `jsonb_exists`).

### §5.4 Qdrant (CBR)

`principalId` stored as keyword-indexed payload field. `sharedWith` stored as keyword array. Filter in `CbrQueryTranslator.toIdentityFilter()` — add a `should` clause (see §2.4 for the filter structure).

### §5.5 Mem0CaseMemoryStore

Mem0 is a REST-backed adapter. Visibility fields are passed as metadata to the Mem0 API:
- `principalId` stored in Mem0 metadata (key: `_principalId`)
- `sharedWith` stored in Mem0 metadata (key: `_sharedWith`, JSON array string)
- Query-time: fetch results from Mem0, apply visibility predicate as a post-filter in `query()` (Mem0's search API does not support arbitrary metadata filtering)

The `toMemory()` mapping extracts `principalId` and `sharedWith` from the metadata map to populate the `Memory` record's visibility fields.

**Post-filter truncation:** because Mem0's API does not support arbitrary metadata filtering, visibility is applied as a post-filter. If the backend returns `limit` results and some are filtered out by visibility, the caller receives fewer than `limit` results. This is an inherent limitation of post-filtered visibility on REST-backed adapters. It is acceptable because: (a) semantic search relevance degrades beyond the first few results — returning fewer highly-relevant visible results is better than over-fetching for quantity; (b) the alternative (over-fetch with a multiplier) adds latency and REST API cost with no guaranteed improvement; (c) callers already handle partial results from all query paths.

### §5.6 GraphitiCaseMemoryStore

Graphiti is a REST-backed adapter implementing `GraphCaseMemoryStore`. Visibility changes apply to both `query()` and `graphQuery()`:
- `principalId` and `sharedWith` passed as episode/message metadata to Graphiti
- Query-time: apply visibility predicate as a post-filter on results from both `query()` and `graphQuery()`
- `factToMemory()` and `episodeToMemory()` extract visibility fields from episode metadata into the `Memory` record

**Post-filter truncation:** same behavior as §5.5 Mem0 — results may be fewer than `limit` after visibility filtering. Same rationale applies.

### §5.7 Decorator Chain Impact

The following decorators pass through `CbrCaseMemoryStore.store()` parameters and need updating for the `entityId→Subject` rename and new `principalId`/`sharedWith` parameters:

**CbrCaseMemoryStore decorators:**
- ScopeDecayCbrCaseMemoryStore
- TemporalDecayCbrCaseMemoryStore
- TrendEnrichmentCbrCaseMemoryStore
- TrustWeightedCbrCaseMemoryStore
- ErasureNotificationCbrCaseMemoryStore
- OutcomeWeightingCbrCaseMemoryStore
- TrackingCbrCaseMemoryStore
- RerankingCbrCaseMemoryStore

**CaseMemoryStore decorators:**
- ErasureNotificationCaseMemoryStore
- CaseEnrichmentDecorator

All changes are mechanical pass-through — decorators do not interpret visibility fields. The `eraseEntity` → `eraseSubject` rename also propagates through `ErasureNotificationCbrCaseMemoryStore` and `ErasureNotificationCaseMemoryStore`.

---

## §6 Scope Boundaries

**In scope:**
- Subject record in memory-api
- entityId → subjectId rename across memory and CBR subsystems
- principalId + sharedWith on MemoryInput and Memory
- callerPrincipalId on MemoryQuery, GraphMemoryQuery, and CbrQuery
- Visibility filtering in all store implementations (InMemory, SQLite, JPA, Qdrant, Mem0, Graphiti)
- Converter updates for agent-originated memories
- Contract tests for visibility rules
- Decorator chain pass-through updates

**Out of scope (separate issues):**
- TemporalIndex integration (#254 — unblocked by this)
- Formal Principal type integration (#276)
- Thing model and dynamic type system (#278)
- SubgraphType enum → dynamic string (#278)
- MindMap visibility (already has PerspectivalResolver)
- PerspectivalResolver principalId alignment (#280 — filed from this review)

**PerspectivalResolver (#280):** Issue #277 lists "PerspectivalResolver alignment" as scope item 4. `PerspectivalResolver.resolve()` operates on MindMap overlay nodes using `agentId` — it has no connection to the memory SPI. The alignment (rename `agentId` to `principalId`, evaluate extending overlay resolution to memory visibility) is a MindMap-layer concern. Filed as #280. Issue #277 can be closed without it — the memory visibility model is complete and PerspectivalResolver works independently.

---

## §7 Testing

### §7.1 Contract Tests (CaseMemoryStoreContractTest)

1. **Truly shared** — store with null principalId, query with any callerPrincipalId → visible
2. **Private** — store with principalId="alice", query as "alice" → visible, query as "bob" → not visible
3. **Owned + shared** — store with principalId="alice" sharedWith={"bob"}, query as "bob" → visible, query as "charlie" → not visible
4. **Null caller** — query with null callerPrincipalId → all memories visible (backward compat)
5. **Subject round-trip** — store with Subject("person", "alice"), query by subject → returned with type preserved
6. **Mixed visibility** — store private + shared memories, query returns only visible ones with correct count
7. **Subject type normalization** — Subject("Person", "alice") matches Subject("person", "alice")

### §7.2 CBR Contract Tests

Same visibility rules applied to CbrCaseMemoryStore.retrieveSimilar().

### §7.3 GraphQuery Contract Tests

Visibility filtering applied to GraphCaseMemoryStore.graphQuery() — same rules as §7.1 but via GraphMemoryQuery.

### §7.4 Memory Output Record

Query results carry Subject (not bare entityId), principalId, and sharedWith. Verify round-trip from MemoryInput → store → query → Memory preserves all fields.

---

## References

- casehubio/platform#271 — Principal identity model (CurrentPrincipal.actorId())
- casehubio/neocortex#269 — principalId on EdgeInput/NodeInput
- casehubio/neocortex#254 — TemporalIndex integration (unblocked)
- casehubio/neocortex#278 — Thing model, dynamic types, isA
- casehubio/neocortex#280 — PerspectivalResolver principalId alignment
- docs/specs/issue-253-cognitive-rearchitecture/2026-09-01-remove-memory-space-modules-design.md — why space-as-tenant was wrong
- docs/specs/issue-253-cognitive-rearchitecture/2026-08-31-memory-space-model-design.md — previous (removed) design
- MemoryInput.java — current SPI
- MemoryQuery.java — current query model
- CaseMemoryStore.java — current store interface
- Drools traits — prior art for dynamic type projection
