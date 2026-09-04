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
    }

    public static Subject of(String type, String id) {
        return new Subject(type, id);
    }
}
```

`type` is a free-form string — not an enum. The LLM discovers new types at runtime ("person", "project", "research-topic", "concern", "incident"). No recompile needed. The type vocabulary grows as the agent learns.

`Subject` is a reference to a Thing (#278). When the formal Thing model lands, Subject becomes `Thing.ref()` or similar. The `(type, id)` pair is already compatible.

### §1.2 entityId → subjectId Rename

Every occurrence of `entityId` in the memory and CBR subsystems becomes `subjectId`. The Subject record replaces the bare `String`:

| Current | New |
|---|---|
| `MemoryInput.entityId` (String) | `MemoryInput.subject` (Subject) |
| `MemoryQuery.entityIds` (List\<String>) | `MemoryQuery.subjects` (List\<Subject>) |
| `CaseMemoryStore.eraseEntity(entityId, tenantId)` | `CaseMemoryStore.eraseSubject(Subject, tenantId)` |
| `CaseMemoryStore.eraseEntityAcrossTenants(entityId, tenantIds)` | `CaseMemoryStore.eraseSubjectAcrossTenants(Subject, tenantIds)` |
| `CbrCaseMemoryStore.store(..., entityId, ...)` | `CbrCaseMemoryStore.store(..., Subject, ...)` |
| `EraseRequest.entityId` | `EraseRequest.subject` |
| Converter classes (ExperienceEvents, RelationshipEvents, etc.) | Update all `entityId` references |

Backward-compatible constructors or factory methods that accept `String entityId` and wrap it as `Subject.of("unknown", entityId)` — allows incremental migration of callers. These are deprecated-for-removal.

### §1.3 Storage Representation

In persistent stores (SQLite, JPA, Qdrant), Subject is stored as two fields:

| Store | subject_type column | subject_id column |
|---|---|---|
| SQLite | `TEXT NOT NULL DEFAULT 'unknown'` | existing `entity_id` column renamed |
| JPA/PostgreSQL | `VARCHAR NOT NULL DEFAULT 'unknown'` | existing `entity_id` column renamed |
| Qdrant payload | `subjectType` (keyword-indexed) | `subjectId` (keyword-indexed) |

Default `'unknown'` for the type ensures backward compatibility — existing data is valid without migration beyond a column rename.

---

## §2 Visibility Model

### §2.1 Fields

Two new fields on `MemoryInput`:

```java
String principalId       // owner — null means truly shared (no owner)
Set<String> sharedWith   // additional principals who can see — empty by default
```

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

When `callerPrincipalId` is set, the store filters results:
- Include memories where `principalId` is null (truly shared)
- Include memories where `principalId` equals `callerPrincipalId` (caller owns it)
- Include memories where `sharedWith` contains `callerPrincipalId` (shared with caller)
- Exclude all other memories

When `callerPrincipalId` is null (not set), no filtering — all memories visible. This preserves backward compatibility.

### §2.4 CBR Integration

`CbrQuery` already has `principalId` from #269 work on EdgeInput. The same visibility rules apply:
- `CbrCaseMemoryStore.store(...)` gains `principalId` and `sharedWith` parameters
- `CbrCaseMemoryStore.retrieveSimilar(...)` respects visibility based on `CbrQuery.callerPrincipalId`

### §2.5 Storage Representation

| Store | principalId | sharedWith |
|---|---|---|
| SQLite | `TEXT` column (nullable, keyword-indexed) | `TEXT` column (nullable, comma-separated, or JSON array) |
| JPA/PostgreSQL | `VARCHAR` column (nullable) | `VARCHAR[]` array column or JSON |
| Qdrant payload | `principalId` (keyword-indexed) | `sharedWith` (keyword array, matchKeywords) |
| In-memory | Direct field access + filter in `query()` |

---

## §3 MemoryInput Changes

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
) { ... }
```

Factory methods:
- `MemoryInput.of(Subject subject, MemoryDomain domain, String tenantId, String text)` — truly shared (backward compat)
- `MemoryInput.ownedBy(Subject subject, MemoryDomain domain, String tenantId, String text, String principalId)` — private by default
- `withPrincipalId(String)`, `withSharedWith(Set<String>)` builders

Backward-compatible constructor accepting the old parameter list (with String entityId, no principalId/sharedWith) wraps as `Subject.of("unknown", entityId)` with null visibility.

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
| `AffectEvents.toMemoryInput()` | passed through | passed through |

Agent-originated memories are private by default — the agent owns its own experiences, reflections, moods, and engagement records.

---

## §5 Store Implementation Changes

### §5.1 InMemoryMemoryStore

Filter in `query()`: iterate stored memories, apply the visibility predicate from §2.3. Straightforward — the in-memory store already iterates all memories.

### §5.2 SqliteMemoryStore

Add `principal_id` and `shared_with` columns. Extend the query SQL with a visibility WHERE clause:

```sql
WHERE (principal_id IS NULL
    OR principal_id = :callerPrincipalId
    OR shared_with LIKE '%' || :callerPrincipalId || '%')
```

For FTS5 queries, the visibility filter applies as a post-filter on the result set (FTS5 doesn't support arbitrary WHERE clauses in the MATCH expression).

### §5.3 JpaMemoryStore

Add `principalId` and `sharedWith` columns to the entity. Extend the JPQL/native query with the same visibility predicate.

### §5.4 Qdrant (CBR)

`principalId` stored as keyword-indexed payload field. `sharedWith` stored as keyword array. Filter in `CbrQueryTranslator.toIdentityFilter()` — add a `should` clause:
- `matchKeyword("principalId", callerPrincipalId)` OR
- `matchKeywords("sharedWith", List.of(callerPrincipalId))` OR
- NOT `hasId("principalId")` (no owner = truly shared)

---

## §6 Scope Boundaries

**In scope:**
- Subject record in memory-api
- entityId → subjectId rename across memory and CBR subsystems
- principalId + sharedWith on MemoryInput
- callerPrincipalId on MemoryQuery
- Visibility filtering in all store implementations
- Converter updates for agent-originated memories
- Contract tests for visibility rules

**Out of scope (separate issues):**
- TemporalIndex integration (#254 — unblocked by this)
- Formal Principal type integration (#276)
- Thing model and dynamic type system (#278)
- SubgraphType enum → dynamic string (#278)
- MindMap visibility (already has PerspectivalResolver)

---

## §7 Testing

### §7.1 Contract Tests (CaseMemoryStoreContractTest)

1. **Truly shared** — store with null principalId, query with any callerPrincipalId → visible
2. **Private** — store with principalId="alice", query as "alice" → visible, query as "bob" → not visible
3. **Owned + shared** — store with principalId="alice" sharedWith={"bob"}, query as "bob" → visible, query as "charlie" → not visible
4. **Null caller** — query with null callerPrincipalId → all memories visible (backward compat)
5. **Subject round-trip** — store with Subject("person", "alice"), query by subject → returned with type preserved
6. **Mixed visibility** — store private + shared memories, query returns only visible ones with correct count

### §7.2 CBR Contract Tests

Same visibility rules applied to CbrCaseMemoryStore.retrieveSimilar().

---

## References

- casehubio/platform#271 — Principal identity model
- casehubio/neocortex#269 — principalId on EdgeInput/NodeInput
- casehubio/neocortex#254 — TemporalIndex integration (unblocked)
- casehubio/neocortex#278 — Thing model, dynamic types, isA
- docs/specs/issue-253-cognitive-rearchitecture/2026-09-01-remove-memory-space-modules-design.md — why space-as-tenant was wrong
- docs/specs/issue-253-cognitive-rearchitecture/2026-08-31-memory-space-model-design.md — previous (removed) design
- MemoryInput.java — current SPI
- MemoryQuery.java — current query model
- CaseMemoryStore.java — current store interface
- Drools traits — prior art for dynamic type projection
