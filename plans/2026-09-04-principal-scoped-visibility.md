# Principal-Scoped Memory Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #277 — principal-scoped memory visibility
**Issue group:** #277

**Goal:** Add principal ownership, typed subjects, and visibility filtering to the memory subsystem so queries return only what the querying principal is allowed to see.

**Architecture:** Create `Subject(type, id)` record in memory-api, rename `entityId` → `subject` across all memory/CBR types, add `principalId` + `sharedWith` visibility fields to `MemoryInput`, add `callerPrincipalId` to queries, implement filtering in all store backends.

**Tech Stack:** Java 21, Quarkus 3.32.2, SQLite (HikariCP WAL), JPA/PostgreSQL, Qdrant gRPC

## Global Constraints

- Pre-release — no backward-compatible shims. Clean break on entityId → Subject.
- Subject.type normalized to lowercase on construction.
- `principalId = null` means truly shared (backward compat for existing data).
- IntelliJ MCP for all renames and structural refactoring.
- All existing contract tests must continue to pass after each batch.

---

## Batch 1: Subject record + memory-api SPI foundation

### Task 1: Create Subject record and SubjectTest

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/Subject.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/SubjectTest.java`

**Interfaces:**
- Produces: `Subject(String type, String id)`, `Subject.of(String, String)` — used by all subsequent tasks

- [ ] **Step 1: Write failing tests for Subject**

```java
@Test void of_normalizesTypeToLowercase() {
    var s = Subject.of("Person", "alice");
    assertThat(s.type()).isEqualTo("person");
    assertThat(s.id()).isEqualTo("alice");
}

@Test void of_stripsWhitespace() {
    var s = Subject.of(" person ", " alice ");
    assertThat(s.type()).isEqualTo("person");
    assertThat(s.id()).isEqualTo("alice");
}

@Test void nullType_throws() {
    assertThatThrownBy(() -> Subject.of(null, "alice"))
        .isInstanceOf(NullPointerException.class);
}

@Test void blankType_throws() {
    assertThatThrownBy(() -> Subject.of("", "alice"))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test void nullId_throws() {
    assertThatThrownBy(() -> Subject.of("person", null))
        .isInstanceOf(NullPointerException.class);
}

@Test void equality_sameTypeAndId() {
    assertThat(Subject.of("person", "alice"))
        .isEqualTo(Subject.of("Person", "alice"));
}
```

- [ ] **Step 2: Run tests — expect FAIL (Subject not found)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SubjectTest`

- [ ] **Step 3: Implement Subject record**

Per spec §1.1 — record with compact constructor validation, lowercase normalization, whitespace stripping.

- [ ] **Step 4: Run tests — expect PASS**

- [ ] **Step 5: Commit**

```
feat(memory-api): Subject record — typed entity reference with lowercase normalization Refs #277
```

### Task 2: Add Subject to MemoryInput + visibility fields

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/MemoryInputTest.java` (if exists)

**Interfaces:**
- Consumes: `Subject` from Task 1
- Produces: `MemoryInput.subject()`, `MemoryInput.principalId()`, `MemoryInput.sharedWith()`, `MemoryInput.ownedBy()` factory

- [ ] **Step 1: Replace `entityId` with `subject` (Subject), add `principalId` (String, nullable), `sharedWith` (Set\<String>)**

Use `ide_edit_member` to replace the MemoryInput record declaration. Add backward-compatible constructor (old param list → wraps as Subject.of("unknown", entityId) with null visibility) — this is temporary to allow incremental compilation while other files are updated. Mark `@Deprecated(forRemoval = true)`.

- [ ] **Step 2: Update factory methods**

`MemoryInput.of(Subject, MemoryDomain, String tenantId, String text)` — truly shared.
`MemoryInput.ownedBy(Subject, MemoryDomain, String tenantId, String text, String principalId)` — private by default.
`withPrincipalId(String)`, `withSharedWith(Set<String>)` builders.

- [ ] **Step 3: Update all withX() methods to pass through new fields**

- [ ] **Step 4: Compile memory-api — fix any errors**

- [ ] **Step 5: Commit**

```
feat(memory-api): MemoryInput gains Subject, principalId, sharedWith Refs #277
```

### Task 3: Add callerPrincipalId to MemoryQuery + Subject to query types

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryQuery.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/Memory.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/EraseRequest.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/CaseMemoryStore.java`

**Interfaces:**
- Consumes: `Subject` from Task 1
- Produces: `MemoryQuery.callerPrincipalId()`, `MemoryQuery.subjects()` (was entityIds), `CaseMemoryStore.eraseSubject()`, `CaseMemoryStore.eraseSubjectAcrossTenants()`

- [ ] **Step 1: Update MemoryQuery** — `entityIds` → `subjects` (List\<Subject>), add `callerPrincipalId` (nullable). Add backward-compat factory accepting List\<String> entityIds (deprecated).

- [ ] **Step 2: Update Memory** — `entityId` → `subject` (Subject). Add backward-compat accessor (deprecated).

- [ ] **Step 3: Update EraseRequest** — `entityId` → `subject` (Subject).

- [ ] **Step 4: Update CaseMemoryStore interface** — rename `eraseEntity` → `eraseSubject`, `eraseEntityAcrossTenants` → `eraseSubjectAcrossTenants`. Update parameter types.

- [ ] **Step 5: Compile memory-api — fix remaining errors**

- [ ] **Step 6: Commit**

```
feat(memory-api): Subject on MemoryQuery/Memory/EraseRequest, callerPrincipalId for visibility Refs #277
```

---

## Batch 2: entityId → subject rename across modules

### Task 4: Rename across converters + memory CDI module

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/ExperienceEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/relationship/RelationshipEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/reflection/ReflectionEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementEvents.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/MemoryEmitter.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/ExperienceStream.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/RelationshipObserver.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/ReflectionService.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/EngagementStream.java`
- Modify: All corresponding test files

**Interfaces:**
- Consumes: `Subject`, `MemoryInput.subject()` from Tasks 1-2
- Produces: Converters produce `MemoryInput` with `Subject.of("agent", agentId)` and `principalId = agentId`

- [ ] **Step 1: Update each converter** — `entityId` → `Subject.of("agent", event.agentId())`, add `principalId = event.agentId()` (agent memories are private by default)

- [ ] **Step 2: Update memory CDI module classes** — follow compile errors from the converter changes

- [ ] **Step 3: Compile `mvn test-compile -pl memory-api,memory -am`**

- [ ] **Step 4: Run memory-api + memory tests**

- [ ] **Step 5: Commit**

```
refactor(memory): entityId → Subject across converters and CDI module Refs #277
```

### Task 5: Rename across store implementations

**Files:**
- Modify: `memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java`
- Modify: `memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java`
- Modify: `memory-jpa/src/main/java/io/casehub/neocortex/memory/jpa/JpaMemoryStore.java`
- Modify: `memory-mem0/src/main/java/io/casehub/neocortex/memory/mem0/Mem0CaseMemoryStore.java`
- Modify: `memory-graphiti/` store classes
- Modify: All corresponding test files

**Interfaces:**
- Consumes: Updated `CaseMemoryStore` SPI from Task 3

- [ ] **Step 1: Update InMemoryMemoryStore** — store/query use `Subject`, erase methods renamed

- [ ] **Step 2: Update SqliteMemoryStore** — SQL queries reference new column names, `Subject` serialization

- [ ] **Step 3: Update JpaMemoryStore** — entity mapping, JPQL updates

- [ ] **Step 4: Update Mem0CaseMemoryStore and GraphitiCaseMemoryStore**

- [ ] **Step 5: Compile and run tests for each module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-inmem,memory-sqlite,memory-jpa,memory-mem0,memory-graphiti -am`

- [ ] **Step 6: Commit**

```
refactor(memory-stores): entityId → Subject across all store implementations Refs #277
```

### Task 6: Rename across CBR subsystem

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java`
- Modify: CBR decorator classes in `memory/`
- Modify: `memory-cbr-inmem/`, `memory-qdrant/`, `memory-cbr-tracking/` stores
- Modify: `memory-testing/` contract tests
- Modify: All corresponding test files

**Interfaces:**
- Consumes: `Subject` from Task 1

- [ ] **Step 1: Update CbrCaseMemoryStore SPI** — `entityId` → `Subject`, add `principalId` + `sharedWith` to `store()`, add `callerPrincipalId` to `CbrQuery`

- [ ] **Step 2: Update CBR decorator classes** — follow compile errors

- [ ] **Step 3: Update InMemoryCbrCaseMemoryStore**

- [ ] **Step 4: Update QdrantCbrCaseMemoryStore** — payload field renames (entityId → subjectType + subjectId)

- [ ] **Step 5: Update contract tests** — all `entityId` references → `Subject`

- [ ] **Step 6: Compile and run full CBR test suite**

- [ ] **Step 7: Commit**

```
refactor(cbr): entityId → Subject across CBR subsystem + add visibility params Refs #277
```

---

## Batch 3: Visibility filtering in stores

### Task 7: Visibility filtering in InMemoryMemoryStore + contract tests

**Files:**
- Modify: `memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java`
- Modify: `memory-testing/` — add visibility contract tests

**Interfaces:**
- Consumes: `callerPrincipalId` from MemoryQuery (Task 3)
- Produces: Contract test base class methods that all store implementations must pass

- [ ] **Step 1: Write visibility contract tests** per spec §7.1:
  - Truly shared visible to any caller
  - Private visible only to owner
  - Owned+shared visible to owner and sharedWith
  - Null caller sees everything (backward compat)
  - Mixed visibility returns only visible memories with correct count

- [ ] **Step 2: Implement visibility filtering in InMemoryMemoryStore.query()**

- [ ] **Step 3: Run contract tests via InMemory**

- [ ] **Step 4: Commit**

```
feat(memory): visibility filtering in InMemoryMemoryStore + contract tests Refs #277
```

### Task 8: Visibility filtering in SqliteMemoryStore

**Files:**
- Modify: `memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java`
- Modify: Flyway migration (add `principal_id`, `shared_with`, `subject_type` columns)

- [ ] **Step 1: Add Flyway migration** — ALTER TABLE for new columns with defaults

- [ ] **Step 2: Implement visibility WHERE clause** per spec §5.2

- [ ] **Step 3: Store `principalId` and `sharedWith` in `store()`**

- [ ] **Step 4: Run SqliteMemoryStore contract tests**

- [ ] **Step 5: Commit**

```
feat(memory-sqlite): visibility columns + query filtering Refs #277
```

### Task 9: Visibility filtering in remaining stores

**Files:**
- Modify: `memory-jpa/` — entity + JPQL
- Modify: `memory-qdrant/` — payload fields + Qdrant filter
- Modify: `memory-mem0/`, `memory-graphiti/` — adapter updates

- [ ] **Step 1: JpaMemoryStore** — entity columns, JPQL visibility predicate

- [ ] **Step 2: QdrantCbrCaseMemoryStore** — payload fields, CbrQueryTranslator visibility filter

- [ ] **Step 3: Mem0 + Graphiti** — adapter mapping

- [ ] **Step 4: Run all store tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -q`

- [ ] **Step 5: Commit**

```
feat(memory-stores): visibility filtering across JPA, Qdrant, Mem0, Graphiti Refs #277
```

---

## Batch 4: Cognitive-index integration + cleanup

### Task 10: Update cognitive-index consumers + remove deprecated shims

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfile.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TemporalIndex.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalResolver.java`
- Modify: All cognitive-index tests
- Remove: Deprecated backward-compat constructors from MemoryInput, MemoryQuery

- [ ] **Step 1: Update CognitiveProfile** — queries use `Subject`, pass `callerPrincipalId` when resolving

- [ ] **Step 2: Update TemporalIndex** — queries use `Subject`

- [ ] **Step 3: Remove deprecated backward-compat constructors** — all callers now use Subject directly

- [ ] **Step 4: Full reactor build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test`
Expected: All tests pass (excluding pre-existing Qdrant flake if still present)

- [ ] **Step 5: Update CLAUDE.md** — reflect Subject, principalId, sharedWith, callerPrincipalId in module descriptions

- [ ] **Step 6: Commit**

```
feat(cognitive-index): Subject + visibility in CognitiveProfile and TemporalIndex, remove deprecated shims Refs #277
```

---

## References

- [2026-09-04-principal-scoped-visibility-design.md] — design spec this plan implements
- [MemoryInput.java] — current SPI (entityId field being replaced)
- [MemoryQuery.java] — current query model (entityIds being replaced)
- [CaseMemoryStore.java] — current store interface
- [CbrCaseMemoryStore.java] — CBR store interface
- [InMemoryMemoryStore.java] — in-memory implementation
- [SqliteMemoryStore.java] — SQLite implementation
- [QdrantCbrCaseMemoryStore.java] — Qdrant CBR implementation
- [casehubio/neocortex#269] — principalId on EdgeInput/NodeInput (prior art for the pattern)
- [casehubio/platform#271] — Principal identity model
- [casehubio/neocortex#278] — Thing model (Subject evolves into Thing.ref())
