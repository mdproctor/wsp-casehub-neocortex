# Memory Backend Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate all CaseMemoryStore SPI types and backend implementations from casehub-platform into casehub-neural-text, fix the CBR discriminator fragility (#59), and update the CBR spec (#58).

**Architecture:** Three phases — (1) fix CBR discriminator with TDD in neural-text, (2) rename packages via IntelliJ workspace refactoring across all 26 repos, (3) move files from platform to neural-text and update Maven dependencies. IntelliJ semantic refactoring handles import propagation; Maven dependency updates are manual.

**Tech Stack:** Java 21, Quarkus 3.32.2, Maven, IntelliJ MCP (ide_move_file, ide_refactor_rename), Qdrant, LangChain4j

## Global Constraints

- Java 21 source (Java 26 JVM): `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Use `mvn` not `./mvnw`
- All modules: `groupId=io.casehub`, `version=0.2-SNAPSHOT`
- IntelliJ MCP: use `mcp__intellij-index__*` for all semantic operations, pass `project_path` when needed
- Never use bash grep/find for class search — use IntelliJ MCP
- TDD: write failing test first, verify failure, implement, verify pass
- Every commit references an issue
- Platform protocols at `casehub/garden/docs/protocols/universal/` are binding

---

### Task 1: #58 — Update CBR Spec

**Files:**
- Modify: `specs/issue-20-cbr-retrieval-architecture/2026-06-30-cbr-retrieval-architecture.md` (workspace: `/Users/mdproctor/claude/public/casehub/neural-text/`)

- [ ] **Step 1: Read the spec sections that need correction**

Read the spec file, locate §6 (CbrCaseMemoryStore SPI section) where `store()`, `erase()`, `eraseEntity()` signatures and NoOp delegation are described.

- [ ] **Step 2: Fix store() signature**

Add `String caseType` as the 2nd parameter in the `store()` signature (both blocking and reactive). The correct signature is:
```java
String store(CbrCase cbrCase, String caseType, String entityId,
             MemoryDomain domain, String tenantId, String caseId);
```

- [ ] **Step 3: Fix erase()/eraseEntity() return types**

Change `int` → `Integer` (boxed) for both methods. Required for `Uni<Integer>` reactive parity.

- [ ] **Step 4: Fix NoOp delegation description**

Update spec to state NoOpCbrCaseMemoryStore is a pure no-op — does NOT delegate to CaseMemoryStore. No hard dependency on platform having an active CaseMemoryStore bean.

- [ ] **Step 5: Commit**

```
git -C /Users/mdproctor/claude/public/casehub/neural-text commit -m "docs(#58): update CBR spec — store() caseType param, Integer returns, NoOp delegation"
```

---

### Task 2: #59 — CbrCase Discriminator Fix (TDD)

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/memory/cbr/CbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/memory/cbr/TextualCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/memory/cbr/FeatureVectorCbrCase.java`
- Modify: `memory-api/src/test/java/io/casehub/memory/cbr/CbrCaseTest.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/memory/cbr/qdrant/CbrPointBuilder.java`
- Modify: `memory-qdrant/src/test/java/io/casehub/memory/cbr/qdrant/CbrPointBuilderTest.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`

**Interfaces:**
- Produces: `CbrCase.cbrType()` method, `TextualCbrCase.CBR_TYPE` constant, `FeatureVectorCbrCase.CBR_TYPE` constant

**Prerequisite:** Invoke `superpowers:test-driven-development` and `java-dev` skills before implementing.

- [ ] **Step 1: Write failing test for cbrType() on TextualCbrCase**

In `memory-api/src/test/java/io/casehub/memory/cbr/CbrCaseTest.java`, add:
```java
@Test
void textualCbrCase_cbrType_returns_textual() {
    var c = new TextualCbrCase("problem", "solution", null, null);
    assertThat(c.cbrType()).isEqualTo("textual");
}
```

- [ ] **Step 2: Run test — verify compile failure**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrCaseTest#textualCbrCase_cbrType_returns_textual
```
Expected: compile error — `cbrType()` not defined on CbrCase.

- [ ] **Step 3: Add cbrType() to CbrCase interface**

```java
public interface CbrCase {
    String cbrType();
    String problem();
    String solution();
    String outcome();
    Double confidence();
}
```

- [ ] **Step 4: Implement cbrType() in TextualCbrCase**

```java
public record TextualCbrCase(String problem, String solution,
                              String outcome, Double confidence) implements CbrCase {
    public static final String CBR_TYPE = "textual";
    @Override public String cbrType() { return CBR_TYPE; }
    // ... existing canonical constructor unchanged
}
```

- [ ] **Step 5: Implement cbrType() in FeatureVectorCbrCase**

```java
public record FeatureVectorCbrCase(String problem, String solution,
                                    String outcome, Double confidence,
                                    Map<String, Object> features) implements CbrCase {
    public static final String CBR_TYPE = "feature-vector";
    @Override public String cbrType() { return CBR_TYPE; }
    // ... existing canonical constructor unchanged
}
```

- [ ] **Step 6: Run test — verify pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=CbrCaseTest
```

- [ ] **Step 7: Write failing test for CbrPointBuilder _cbr_type field**

In `CbrPointBuilderTest.java`, add:
```java
@Test
void buildPoint_stores_cbr_type_discriminator() {
    var textual = new TextualCbrCase("problem", "solution", null, null);
    PointStruct point = CbrPointBuilder.buildPoint(textual, "game",
        "e1", "cbr", "t1", "c1", null, "dense");
    assertThat(point.getPayloadMap().get("_cbr_type").getStringValue()).isEqualTo("textual");
    assertThat(point.getPayloadMap()).doesNotContainKey("_case_class");

    var fv = new FeatureVectorCbrCase("p", "s", null, null, Map.of("race", "Zerg"));
    PointStruct fvPoint = CbrPointBuilder.buildPoint(fv, "game",
        "e1", "cbr", "t1", "c2", null, "dense");
    assertThat(fvPoint.getPayloadMap().get("_cbr_type").getStringValue()).isEqualTo("feature-vector");
}

@Test
void buildPoint_featureVectorCase_emptyFeatures_still_writes_features_json() {
    var fv = new FeatureVectorCbrCase("p", "s", null, null, Map.of());
    PointStruct point = CbrPointBuilder.buildPoint(fv, "game",
        "e1", "cbr", "t1", "c1", null, "dense");
    assertThat(point.getPayloadMap().get("_features_json").getStringValue()).isEqualTo("{}");
    assertThat(point.getPayloadMap().get("_cbr_type").getStringValue()).isEqualTo("feature-vector");
}
```

- [ ] **Step 8: Run tests — verify failure**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -Dtest=CbrPointBuilderTest
```

- [ ] **Step 9: Update CbrPointBuilder**

Replace `_case_class` with `_cbr_type`. Always write `_features_json` for FeatureVectorCbrCase (remove `!fv.features().isEmpty()` guard for JSON blob, keep for `f_<name>` fields):

```java
// Replace line 93:
payload.put("_cbr_type", ValueFactory.value(cbrCase.cbrType()));

// Update feature block (line 74): separate JSON blob from individual fields
if (cbrCase instanceof FeatureVectorCbrCase fv) {
    // Always store features JSON for reconstruction (even empty)
    try {
        payload.put("_features_json", ValueFactory.value(MAPPER.writeValueAsString(fv.features())));
    } catch (JsonProcessingException e) {
        throw new RuntimeException("Failed to serialize features", e);
    }
    // Individual fields for Qdrant filtering — only when non-empty
    if (!fv.features().isEmpty()) {
        for (Map.Entry<String, Object> entry : fv.features().entrySet()) {
            String key = "f_" + entry.getKey();
            Object val = entry.getValue();
            if (val instanceof String s) {
                payload.put(key, ValueFactory.value(s));
            } else if (val instanceof Number n) {
                payload.put(key, ValueFactory.value(n.doubleValue()));
            }
        }
    }
}
```

- [ ] **Step 10: Run CbrPointBuilder tests — verify pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant -Dtest=CbrPointBuilderTest
```

- [ ] **Step 11: Update reconstructCase in QdrantCbrCaseMemoryStore**

Replace the existing `reconstructCase` method (lines 300-326) with discriminator-first dispatch:

```java
@SuppressWarnings("unchecked")
private <C extends CbrCase> C reconstructCase(Map<String, Value> payload, Class<C> caseClass) {
    String problem = extractString(payload, "problem");
    String solution = extractString(payload, "solution");
    if (problem == null || solution == null) return null;

    String outcome = extractString(payload, "outcome");
    Double confidence = extractDouble(payload, "confidence");
    String cbrType = extractString(payload, "_cbr_type");

    CbrCase reconstructed = switch (cbrType) {
        case FeatureVectorCbrCase.CBR_TYPE -> reconstructFeatureVector(payload, problem, solution, outcome, confidence);
        case TextualCbrCase.CBR_TYPE -> new TextualCbrCase(problem, solution, outcome, confidence);
        case null -> throw new IllegalStateException("Missing _cbr_type in CBR point");
        default -> throw new IllegalArgumentException("Unknown CBR type: " + cbrType);
    };

    if (!caseClass.isInstance(reconstructed)) return null;
    return caseClass.cast(reconstructed);
}

private CbrCase reconstructFeatureVector(Map<String, Value> payload,
                                          String problem, String solution,
                                          String outcome, Double confidence) {
    String featuresJson = extractString(payload, "_features_json");
    if (featuresJson == null) {
        return new FeatureVectorCbrCase(problem, solution, outcome, confidence, Map.of());
    }
    try {
        Map<String, Object> features = MAPPER.readValue(featuresJson, MAP_TYPE);
        return new FeatureVectorCbrCase(problem, solution, outcome, confidence, features);
    } catch (JsonProcessingException e) {
        throw new RuntimeException("Corrupted _features_json in CBR point", e);
    }
}
```

- [ ] **Step 12: Update serializeToMemoryInput**

Replace the instanceof discriminator chain (lines 137-149) with:
```java
attributes.put("cbr.type", cbrCase.cbrType());
if (cbrCase instanceof FeatureVectorCbrCase fv) {
    try {
        attributes.put("cbr.features", MAPPER.writeValueAsString(fv.features()));
    } catch (JsonProcessingException e) {
        throw new RuntimeException("Failed to serialize features to JSON", e);
    }
}
```

- [ ] **Step 13: Run all memory module tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory,memory-testing,memory-cbr-inmem,memory-qdrant
```

- [ ] **Step 14: Commit**

```
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#59): discriminator-based reconstructCase — cbrType() on CbrCase, _cbr_type payload field"
```

---

### Task 3: Delete CbrCaseEntry + Package Rename (IntelliJ Refactoring)

**Files:**
- Delete: `platform-api/src/main/java/io/casehub/platform/api/memory/CbrCaseEntry.java` (platform)
- Delete: `platform-api/src/test/java/io/casehub/platform/api/memory/CbrCaseEntryTest.java` (platform)
- Modify: ALL files importing `io.casehub.platform.api.memory.*` across 26 repos (IntelliJ handles)
- Modify: ALL files importing `io.casehub.platform.memory.*` across 26 repos (IntelliJ handles)

**Prerequisite:** casehub-wide IntelliJ workspace must be open with all repos. Verify with `ide_index_status`.

- [ ] **Step 1: Verify zero external consumers of CbrCaseEntry**

Use `ide_find_references` for `io.casehub.platform.api.memory.CbrCaseEntry`. Confirm all references are self-referential (within CbrCaseEntry.java, CbrCaseEntryTest.java, and javadoc links).

- [ ] **Step 2: Delete CbrCaseEntry**

Use `ide_refactor_safe_delete` on CbrCaseEntry.java, then delete CbrCaseEntryTest.java.

- [ ] **Step 3: Package rename — SPI types**

Use IntelliJ to rename package `io.casehub.platform.api.memory` → `io.casehub.memory` in platform-api. This propagates import changes across all 26 repos in the workspace.

After rename, sync files: `ide_sync_files` on affected repos.

- [ ] **Step 4: Package rename — backend implementations**

Rename package `io.casehub.platform.memory` → `io.casehub.memory` for:
- `platform/` module (NoOpCaseMemoryStore, BlockingToReactiveBridge)
- Each `memory-*` backend module (inmem, jpa, sqlite, mem0, graphiti)

This is a separate refactoring operation from Step 3 — different source package.

- [ ] **Step 5: Verify compilation across repos**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl platform-api -f /Users/mdproctor/claude/casehub/platform/pom.xml
```

Also spot-check consumer repos for import correctness via `ide_diagnostics`.

- [ ] **Step 6: Commit all affected repos**

Commit each repo that had import changes:
- platform: `"refactor(#56): rename io.casehub.platform.api.memory → io.casehub.memory, delete CbrCaseEntry"`
- neural-text: `"refactor(#56): update imports — io.casehub.memory"`
- engine, devtown, aml, clinical, soc, fsitrading: same message pattern

---

### Task 4: Create Neural-Text Modules + Move SPI Types

**Files:**
- Create: `memory-inmem/pom.xml`, `memory-jpa/pom.xml`, `memory-sqlite/pom.xml`, `memory-mem0/pom.xml`, `memory-graphiti/pom.xml` (neural-text)
- Modify: `pom.xml` (neural-text parent — add new modules)
- Move: 17 types from `platform-api/…/memory/` → `memory-api/…/memory/` via `ide_move_file`
- Move: NoOpCaseMemoryStore, BlockingToReactiveBridge from `platform/` → `memory/` via `ide_move_file`
- Move: CaseMemoryStoreContractTest from `testing/` → `memory-testing/` via `ide_move_file`

- [ ] **Step 1: Add new modules to neural-text parent POM**

Add to the `<modules>` section of `/Users/mdproctor/claude/casehub/neural-text/pom.xml`:
```xml
<module>memory-inmem</module>
<module>memory-jpa</module>
<module>memory-sqlite</module>
<module>memory-mem0</module>
<module>memory-graphiti</module>
```

- [ ] **Step 2: Create module POMs**

For each backend module, create a POM based on the platform equivalent but with:
- Parent: `casehub-neural-text-parent`
- ArtifactId: `casehub-memory-*` (drop `platform-` prefix)
- Dependencies: `casehub-memory-api` instead of `casehub-platform-api`
- Test deps: `casehub-memory` (NoOp) and `casehub-memory-testing` (contract test) instead of `casehub-platform` and `casehub-platform-testing`

Read each platform POM, adapt, and write to neural-text.

- [ ] **Step 3: Create source directories**

Create `src/main/java` and `src/test/java` directory structures for each new module with the correct package paths under `io/casehub/memory/`.

- [ ] **Step 4: Move SPI types from platform-api to neural-text/memory-api**

Use `ide_move_file` for each of the 17 types in `io.casehub.memory` package:
- CaseMemoryStore.java
- ReactiveCaseMemoryStore.java
- GraphCaseMemoryStore.java
- MemoryInput.java
- Memory.java
- MemoryQuery.java
- MemoryDomain.java
- MemoryOrder.java
- MemoryCapability.java
- MemoryPermissions.java
- MemoryAttributeKeys.java
- EraseRequest.java
- GraphMemoryQuery.java
- StoreAllResult.java
- StoreFailure.java
- MemoryCapabilityException.java
- MemoryResultType.java

Destination: `memory-api/src/main/java/io/casehub/memory/`

Also move any associated test files from `platform-api/src/test/`.

- [ ] **Step 5: Move NoOpCaseMemoryStore + BlockingToReactiveBridge**

Use `ide_move_file` to move from `platform/src/main/java/io/casehub/memory/` to `memory/src/main/java/io/casehub/memory/runtime/`.

Update package declarations to `io.casehub.memory.runtime`.

- [ ] **Step 6: Move CaseMemoryStoreContractTest**

Use `ide_move_file` from `platform/testing/src/main/java/io/casehub/memory/` to `memory-testing/src/main/java/io/casehub/memory/testing/`.

- [ ] **Step 7: Move backend source files**

For each backend (inmem, jpa, sqlite, mem0, graphiti):
- Use `ide_move_file` to move all source files from platform module to neural-text module
- Move test files similarly
- Move resources (Flyway migrations for JPA: `db/memory/migration/`, SQLite migrations)
- Move REST client interfaces and DTOs (Mem0, Graphiti)

- [ ] **Step 8: Sync IntelliJ and verify**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -f /Users/mdproctor/claude/casehub/neural-text/pom.xml -DskipTests
```

- [ ] **Step 9: Commit neural-text**

```
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "feat(#56): move CaseMemoryStore SPI + all backends from platform to neural-text"
```

---

### Task 5: Consumer Updates + Platform Cleanup

**Files:**
- Modify: POMs in devtown, aml, clinical, soc, fsitrading, casehub-all, parent
- Remove: memory-* modules from platform parent POM
- Remove: memory source dirs from platform

- [ ] **Step 1: Update Maven dependencies in consumer POMs**

For each consumer repo, swap artifact coordinates:
- `casehub-platform-memory-inmem` → `casehub-memory-inmem`
- `casehub-platform-memory-jpa` → `casehub-memory-jpa`
- `casehub-platform-memory-sqlite` → `casehub-memory-sqlite`
- `casehub-platform-memory-mem0` → `casehub-memory-mem0`
- `casehub-platform-memory-graphiti` → `casehub-memory-graphiti`

Add `casehub-memory-api` where consumers import memory types but don't depend on a specific backend.

Consumer-specific changes per the spec's consumer table.

- [ ] **Step 2: Update casehub-parent BOM**

In `/Users/mdproctor/claude/casehub/parent/pom.xml`, update `<dependencyManagement>` to declare `casehub-memory-*` artifacts instead of `casehub-platform-memory-*`.

- [ ] **Step 3: Remove memory modules from platform**

Remove from platform parent POM `<modules>`:
```xml
<!-- DELETE these lines -->
<module>memory-inmem</module>
<module>memory-jpa</module>
<module>memory-sqlite</module>
<module>memory-mem0</module>
<module>memory-graphiti</module>
```

Remove the now-empty memory source directories from platform:
- Delete `memory-inmem/`, `memory-jpa/`, `memory-sqlite/`, `memory-mem0/`, `memory-graphiti/`
- Delete moved source files from `platform-api/src/main/java/io/casehub/memory/` (now empty after Step 4 of Task 4)
- Delete moved source files from `platform/src/main/java/io/casehub/memory/`
- Delete moved source files from `testing/src/main/java/io/casehub/memory/`

- [ ] **Step 4: Build neural-text (install to local Maven)**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/neural-text/pom.xml -DskipTests
```

- [ ] **Step 5: Build platform**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/platform/pom.xml -DskipTests
```

- [ ] **Step 6: Build all consumer repos**

Build each in dependency order:
```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/engine/pom.xml -DskipTests
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/devtown/pom.xml -DskipTests
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/aml/pom.xml -DskipTests
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/clinical/pom.xml -DskipTests
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -f /Users/mdproctor/claude/casehub/life/pom.xml -DskipTests
```

- [ ] **Step 7: Run neural-text tests (full)**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -f /Users/mdproctor/claude/casehub/neural-text/pom.xml
```

- [ ] **Step 8: Commit all repos**

Commit each affected repo with issue reference:
- platform: `"refactor(#56): remove memory-* modules — migrated to neural-text"`
- parent: `"refactor(#56): BOM — casehub-memory-* replaces casehub-platform-memory-*"`
- devtown: `"refactor(#56): swap casehub-platform-memory-inmem → casehub-memory-inmem"`
- aml, clinical, soc, fsitrading: similar messages

---

### Task 6: Documentation Updates

**Files:**
- Modify: `/Users/mdproctor/claude/casehub/parent/docs/PLATFORM.md`
- Modify: `/Users/mdproctor/claude/casehub/neural-text/ARC42STORIES.MD`
- Modify: CBR spec §2.2 (workspace)
- Modify: `/Users/mdproctor/claude/casehub/neural-text/CLAUDE.md`

- [ ] **Step 1: Update PLATFORM.md**

- Capability Ownership table: memory owner → `casehub-neural-text/memory-api`
- Cross-Repo Dependency Map: replace `casehub-platform-api`/`casehub-platform-memory-*` rows with `casehub-memory-api`/`casehub-memory-*`
- Build Order: neural-text publishes before engine, aml, devtown, clinical, life, soc, fsitrading
- Repository Map: update platform one-liner (remove memory modules), update neural-text one-liner (add memory modules)

- [ ] **Step 2: Update ARC42STORIES.MD**

Add memory-* module entries as a new layer group covering the migrated modules.

- [ ] **Step 3: Update prior CBR spec §2.2**

In the issue-20 CBR spec, update §2.2 to reference this spec as superseding the "memory stays in platform" decision.

- [ ] **Step 4: Update neural-text CLAUDE.md**

Update module structure, Maven coordinates, and package sections to include the new memory modules.

- [ ] **Step 5: Commit documentation**

```
git -C /Users/mdproctor/claude/casehub/neural-text commit -m "docs(#56): update ARC42STORIES.MD + CLAUDE.md for memory migration"
git -C /Users/mdproctor/claude/casehub/parent commit -m "docs(#56): update PLATFORM.md — memory ownership moves to neural-text"
```

---

### Task 7: Final Coherence Review

- [ ] **Step 1: Protocol coherence check**

Re-read `module-tier-structure.md`, `persistence-backend-cdi-priority.md`, `spi-signature-change-all-impls-same-commit.md`. Verify the migrated code complies.

- [ ] **Step 2: Invoke superpowers:requesting-code-review**

Review all changes before creating the final commit.

- [ ] **Step 3: File GitHub issues for any deferred concerns**

Any Minor+ findings from the code review that aren't fixed in this session get filed as GitHub issues.

- [ ] **Step 4: Invoke implementation-doc-sync**

Sync documentation after all commits are final.
