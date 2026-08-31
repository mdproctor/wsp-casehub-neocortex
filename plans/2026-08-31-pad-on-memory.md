# PAD on Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #238 — PAD on MemoryInput/Memory
**Issue group:** #253, #229, #232, #234, #235, #236, #237, #238

**Goal:** Add nullable pleasure/arousal/dominance fields to MemoryInput
and Memory, aligning text memory with MindMap's PAD affective model.

**Architecture:** Add 3 nullable `Double` fields to `MemoryInput` (record)
and `Memory` (record). Update all construction sites to pass through the
new fields. Update persistent backends with Flyway migrations. Update
`MoodModulatedRetrieval` to read typed fields instead of parsing attributes.

**Tech Stack:** Java 21, Flyway (SQLite V2, JPA V1001), AssertJ

## Global Constraints

- Fields are nullable `Double` — null means "no affective annotation"
- Fields go after `confidence` in both records
- All existing converters pass `null, null, null` unless they carry PAD data
- MoodEvents is the one converter that should pass typed PAD values
- `Refs #238` on every commit

---

## Batch 1: API changes + all construction sites

### Task 1: Add PAD fields to MemoryInput, Memory, and fix all callers

This is a single large task because changing the record signatures breaks
every construction site. All must be fixed atomically.

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/Memory.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrieval.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/ExperienceEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/relationship/RelationshipEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/reflection/ReflectionEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementEvents.java`
- Modify: `memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java`
- Modify: all test files that construct MemoryInput or Memory directly
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/MemoryInputTest.java` (new or existing)

**Interfaces:**
- Consumes: existing MemoryInput 7-field constructor, Memory 9-field constructor
- Produces: MemoryInput 10-field constructor (+ `pleasure`, `arousal`, `dominance`),
  Memory 12-field constructor (+ same 3 fields), `MemoryInput.withPad(Double, Double, Double)`

- [ ] **Step 1: Write failing test for PAD on MemoryInput**

In `memory-api/src/test/java/io/casehub/neocortex/memory/`:

```java
@Test
void padFields_nullable() {
    var input = new MemoryInput("e1", new MemoryDomain("test"), "t1",
        null, "text", Map.of(), null, null, null, null);
    assertThat(input.pleasure()).isNull();
    assertThat(input.arousal()).isNull();
    assertThat(input.dominance()).isNull();
}

@Test
void padFields_carry_values() {
    var input = new MemoryInput("e1", new MemoryDomain("test"), "t1",
        null, "text", Map.of(), null, 0.5, -0.3, 0.7);
    assertThat(input.pleasure()).isEqualTo(0.5);
    assertThat(input.arousal()).isEqualTo(-0.3);
    assertThat(input.dominance()).isEqualTo(0.7);
}

@Test
void withPad_setsFields() {
    var input = new MemoryInput("e1", new MemoryDomain("test"), "t1",
        null, "text", Map.of(), null, null, null, null);
    var padded = input.withPad(0.5, -0.3, 0.7);
    assertThat(padded.pleasure()).isEqualTo(0.5);
    assertThat(padded.arousal()).isEqualTo(-0.3);
    assertThat(padded.dominance()).isEqualTo(0.7);
}
```

- [ ] **Step 2: Run to verify failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MemoryInputTest`
Expected: FAIL — constructor doesn't match

- [ ] **Step 3: Update MemoryInput record**

Add 3 fields after `confidence`:

```java
public record MemoryInput(
    String entityId,
    MemoryDomain domain,
    String tenantId,
    String caseId,
    String text,
    Map<String, String> attributes,
    Confidence confidence,
    Double pleasure,
    Double arousal,
    Double dominance
) {
```

Add `withPad` method:

```java
public MemoryInput withPad(Double pleasure, Double arousal, Double dominance) {
    return new MemoryInput(entityId, domain, tenantId, caseId, text, attributes,
        confidence, pleasure, arousal, dominance);
}
```

Update existing `withAttribute`, `withAttributes`, `withText` methods to
pass through `pleasure, arousal, dominance`.

- [ ] **Step 4: Update Memory record**

Add 3 fields after `confidence`:

```java
public record Memory(
    String memoryId,
    String entityId,
    MemoryDomain domain,
    String tenantId,
    String caseId,
    String text,
    Map<String, String> attributes,
    Instant createdAt,
    Confidence confidence,
    Double pleasure,
    Double arousal,
    Double dominance
) {
```

- [ ] **Step 5: Fix all MemoryInput construction sites**

Each converter that calls `new MemoryInput(...)` needs 3 extra `null` args:

| File | Line | Change |
|------|------|--------|
| `ExperienceEvents.java` | 62 | append `, null, null, null)` |
| `RelationshipEvents.java` | 48 | append `, null, null, null)` |
| `ReflectionEvents.java` | 43 | append `, null, null, null)` |
| `EngagementEvents.java` | 45 | append `, null, null, null)` |
| `MoodEvents.java` | 44 | pass typed PAD: `, state.pleasure(), state.arousal(), state.dominance()` instead of nulls |

For `MoodEvents`: also remove the PAD-as-attributes lines (the typed
fields replace `MoodAttributeKeys.PLEASURE/AROUSAL/DOMINANCE` in attrs).
Keep the attrs for `turn-id` — only remove the PAD attribute entries.

- [ ] **Step 6: Fix all Memory construction sites**

Each store that calls `new Memory(...)` needs 3 extra args from MemoryInput:

| File | Line | Change |
|------|------|--------|
| `InMemoryMemoryStore.java` | 73 | append `, input.pleasure(), input.arousal(), input.dominance()` |

- [ ] **Step 7: Fix all test files that construct MemoryInput or Memory**

Use `ide_search_text` with query `new MemoryInput(` and `new Memory(`
to find all test construction sites. Append `, null, null, null` to each.

This includes tests in: `memory-api`, `memory-testing`, `memory-inmem`,
`memory`, `memory-cbr-inmem`, `memory-cbr-embedding`, `memory-cbr-tracking`,
`cognitive-index`, and any other module with test-scope memory-api usage.

- [ ] **Step 8: Update MoodModulatedRetrieval**

Change `moodFactor()` to read PAD from typed fields instead of attributes:

Before:
```java
String pStr = memory.attributes().get(MoodAttributeKeys.PLEASURE);
// ... parseDouble for each
```

After:
```java
Double p = memory.pleasure();
Double a = memory.arousal();
Double d = memory.dominance();
if (p == null && a == null && d == null) return 1.0;
// use 0.0 for null individual dimensions
double pleasure = p != null ? p : 0.0;
double arousal = a != null ? a : 0.0;
double dominance = d != null ? d : 0.0;
```

- [ ] **Step 9: Run full memory-api + memory-inmem tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory,memory-inmem,memory-testing`
Expected: PASS

- [ ] **Step 10: Compile full project (no tests)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl '!memory-qdrant'`
Expected: COMPILE SUCCESS — all construction sites fixed

- [ ] **Step 11: Commit**

```
git add -A
git commit -m "feat(memory): add PAD fields to MemoryInput and Memory

Nullable pleasure/arousal/dominance on MemoryInput and Memory records.
MoodEvents passes typed PAD values. MoodModulatedRetrieval reads typed
fields instead of parsing attributes. All converters pass null.

Refs #238"
```

## Batch 2: Persistent backends + docs

### Task 2: SQLite and JPA Flyway migrations + backend updates

**Files:**
- Modify: `memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java`
- Create: `memory-sqlite/src/main/resources/db/migration/V2__add_pad_fields.sql`
- Modify: `memory-jpa/src/main/java/io/casehub/neocortex/memory/jpa/JpaMemoryStore.java`
- Create: `memory-jpa/src/main/resources/db/migration/V1001__add_pad_fields.sql`
- Modify: JPA entity class (if separate from JpaMemoryStore)
- Modify: `memory-mem0/src/main/java/io/casehub/neocortex/memory/mem0/Mem0CaseMemoryStore.java`
- Modify: `memory-graphiti/src/main/java/io/casehub/neocortex/memory/graphiti/GraphitiCaseMemoryStore.java`

**Interfaces:**
- Consumes: Memory 12-field constructor, MemoryInput PAD fields
- Produces: persisted PAD fields in SQLite and JPA backends

- [ ] **Step 1: Create SQLite migration**

```sql
-- V2__add_pad_fields.sql
ALTER TABLE memories ADD COLUMN pleasure REAL;
ALTER TABLE memories ADD COLUMN arousal REAL;
ALTER TABLE memories ADD COLUMN dominance REAL;
```

- [ ] **Step 2: Update SqliteMemoryStore**

Update INSERT to include the 3 new columns.
Update `toMemory()` to read the 3 columns from ResultSet and pass to Memory constructor.

- [ ] **Step 3: Create JPA migration**

```sql
-- V1001__add_pad_fields.sql
ALTER TABLE memories ADD COLUMN pleasure DOUBLE PRECISION;
ALTER TABLE memories ADD COLUMN arousal DOUBLE PRECISION;
ALTER TABLE memories ADD COLUMN dominance DOUBLE PRECISION;
```

- [ ] **Step 4: Update JPA entity and JpaMemoryStore**

Add `pleasure`, `arousal`, `dominance` fields to the JPA entity.
Update `toMemory()` to pass the fields.
Update `store()` to persist the fields from MemoryInput.

- [ ] **Step 5: Update Mem0 and Graphiti adapters**

Both are REST client adapters. Update their `toMemory()` or equivalent
to pass `null, null, null` for PAD fields when constructing Memory from
API responses. If the external API supports metadata, map PAD fields
to/from metadata.

- [ ] **Step 6: Run backend tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-sqlite,memory-jpa,memory-mem0,memory-graphiti`
Expected: PASS

- [ ] **Step 7: Commit**

```
git add -A
git commit -m "feat(memory): SQLite + JPA migrations for PAD fields

V2 SQLite, V1001 JPA — add pleasure/arousal/dominance columns.
Mem0 and Graphiti adapters pass null for PAD.

Refs #238"
```

### Task 3: Full build + documentation

**Files:**
- Modify: `CLAUDE.md` — update Memory record description
- Modify: `docs/guides/cognitive-architecture-roadmap.md` — mark §3a DONE

- [ ] **Step 1: Update CLAUDE.md**

In the memory-api module description, add PAD fields to the Memory/MemoryInput
descriptions.

- [ ] **Step 2: Mark roadmap §3a DONE**

Update `### 3a:` heading to `### 3a: PAD on MemoryInput/Memory — **DONE** (#238)`

- [ ] **Step 3: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl '!memory-qdrant'`
Expected: BUILD SUCCESS

- [ ] **Step 4: Commit**

```
git add CLAUDE.md docs/
git commit -m "docs: mark roadmap §3a DONE, update CLAUDE.md for PAD fields

Refs #238"
```

## References

- specs/issue-253-cognitive-rearchitecture/2026-08-31-chronological-index-design.md — prior spec context
- cognitive-architecture-roadmap.md §3a — roadmap section
- memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java — 7-field record
- memory-api/src/main/java/io/casehub/neocortex/memory/Memory.java — 9-field record
- memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrieval.java — PAD consumer
- memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodEvents.java — PAD producer
- mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java:34-38 — PAD pattern
- GitHub #238 — focal issue
