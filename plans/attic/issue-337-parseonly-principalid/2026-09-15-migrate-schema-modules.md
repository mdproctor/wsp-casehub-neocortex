# Migrate Schema Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #291 — refactor: migrate SealedHierarchyModule and ShorthandModule to shared casehub-platform-schema-generator
**Issue group:** #291, #290

**Goal:** Replace local `EnumInliningModule` and `ShorthandModule` with shared versions from `casehub-platform-schema-generator`, deleting local copies while preserving identical schema output.

**Architecture:** `CognitiveSchemaGenerator` already uses the platform `SealedHierarchyModule`. The remaining two modules are replaced: `EnumInliningModule` is a drop-in import swap; `ShorthandModule` requires building a `Map<Class<?>, ShorthandDefinition>` with explicit scalar/object schema builders for `Confidence`, `NodeRef`, and `RecurrenceRule`.

**Tech Stack:** victools jsonschema-generator 4.38.0, casehub-platform-schema-generator 0.2-SNAPSHOT, Java 21

## Global Constraints

- Schema output must be identical before and after migration — existing tests are the equivalence gate
- `casehub-platform-schema-generator` dependency already in `schema-generator/pom.xml` — no POM changes needed
- `cognitive-api` and `mindmap-api` dependencies stay — needed for `Confidence`, `NodeRef`, `RecurrenceRule` class references

---

## Batch 1: Migrate both modules and verify schema equivalence

### Task 1: Migrate EnumInliningModule to platform version

**Files:**
- Delete: `schema-generator/src/main/java/io/casehub/neocortex/schema/EnumInliningModule.java` (use `ide_refactor_safe_delete`)
- Delete: `schema-generator/src/test/java/io/casehub/neocortex/schema/EnumInliningModuleTest.java` (use `ide_refactor_safe_delete`)
- Modify: `schema-generator/src/main/java/io/casehub/neocortex/schema/CognitiveSchemaGenerator.java` — update import

**Interfaces:**
- Consumes: platform `io.casehub.schema.generator.module.EnumInliningModule` (no-arg constructor, same `Module` interface)
- Produces: unchanged `CognitiveSchemaGenerator` — identical schema output

- [ ] **Step 1: Run existing tests to establish baseline**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all tests PASS

- [ ] **Step 2: Update CognitiveSchemaGenerator import**

In `CognitiveSchemaGenerator.java`, replace the local import with the platform import. The constructor already uses `new EnumInliningModule()` — no other code changes needed.

Replace:
```java
import io.casehub.neocortex.schema.EnumInliningModule;
```
With:
```java
import io.casehub.schema.generator.module.EnumInliningModule;
```

Note: this import doesn't exist as a standalone line — `EnumInliningModule` is in the same package, so it has no import. The class reference `new EnumInliningModule()` on line 63 will resolve to the platform version once the local class is deleted. No import change needed — just delete the local file.

- [ ] **Step 3: Delete local EnumInliningModule**

Use `ide_refactor_safe_delete` on `schema-generator/src/main/java/io/casehub/neocortex/schema/EnumInliningModule.java`.

If safe delete reports usages: the only expected usage is `CognitiveSchemaGenerator` line 63 — after deletion, that reference resolves to the platform class on the classpath. Force the delete.

- [ ] **Step 4: Delete EnumInliningModuleTest**

Use `ide_refactor_safe_delete` on `schema-generator/src/test/java/io/casehub/neocortex/schema/EnumInliningModuleTest.java`.

No usages expected — it's a standalone test class.

- [ ] **Step 5: Add explicit import for platform EnumInliningModule**

After deleting the local class, `CognitiveSchemaGenerator` needs an explicit import since the platform class is in a different package. Add:

```java
import io.casehub.schema.generator.module.EnumInliningModule;
```

- [ ] **Step 6: Verify schema equivalence**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all remaining tests PASS (EnumInliningModuleTest is gone; CognitiveSchemaGeneratorTest.confidenceOrigin_generatesInlinedEnum covers enum inlining)

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add schema-generator/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor: migrate EnumInliningModule to shared platform version

Replace local EnumInliningModule with io.casehub.schema.generator.module.EnumInliningModule
from casehub-platform-schema-generator. Delete local copy and its unit test —
CognitiveSchemaGeneratorTest covers enum inlining through the composed generator.

Refs #291"
```

### Task 2: Migrate ShorthandModule to platform version with ShorthandDefinition registrations

**Files:**
- Delete: `schema-generator/src/main/java/io/casehub/neocortex/schema/ShorthandModule.java` (use `ide_refactor_safe_delete`)
- Modify: `schema-generator/src/main/java/io/casehub/neocortex/schema/CognitiveSchemaGenerator.java` — add `SHORTHAND_DEFINITIONS` map, update import and constructor
- Modify: `schema-generator/src/test/java/io/casehub/neocortex/schema/ShorthandModuleTest.java` — repoint to platform module with neocortex definitions

**Interfaces:**
- Consumes: platform `io.casehub.schema.generator.module.ShorthandModule(Map<Class<?>, ShorthandDefinition>)`, `ShorthandDefinition.of(Function<Config, ObjectNode>, Function<Config, ObjectNode>)`
- Produces: unchanged schema output; `CognitiveSchemaGenerator.SHORTHAND_DEFINITIONS` (package-private) for test reuse

- [ ] **Step 1: Add SHORTHAND_DEFINITIONS map to CognitiveSchemaGenerator**

Add a package-private static field with the three `ShorthandDefinition` registrations, splitting each type's current `oneOf` into separate scalar and object builders. Add the field after `DISCRIMINATOR_OVERRIDES`:

```java
static final Map<Class<?>, ShorthandDefinition> SHORTHAND_DEFINITIONS = Map.of(
    Confidence.class, ShorthandDefinition.of(
        config -> {
            ObjectNode n = config.createObjectNode();
            n.put("type", "number").put("minimum", 0).put("maximum", 1);
            return n;
        },
        config -> {
            ObjectNode full = config.createObjectNode();
            full.put("type", "object");
            ObjectNode props = full.putObject("properties");
            ObjectNode origin = props.putObject("origin");
            origin.put("type", "string");
            origin.putArray("enum")
                .add("STATED").add("INFERRED").add("SPECULATED").add("UNKNOWN");
            props.putObject("value").put("type", "number")
                .put("minimum", 0).put("maximum", 1);
            props.putObject("decayReference").put("type", "string")
                .put("format", "date-time");
            full.putArray("required").add("origin").add("value");
            return full;
        }
    ),
    NodeRef.class, ShorthandDefinition.of(
        config -> {
            ObjectNode n = config.createObjectNode();
            n.put("type", "string").put("pattern", "^[^:]+:.+$");
            return n;
        },
        config -> {
            ObjectNode full = config.createObjectNode();
            full.put("type", "object");
            ObjectNode props = full.putObject("properties");
            props.putObject("scheme").put("type", "string");
            props.putObject("id").put("type", "string");
            props.putObject("qualifier").put("type", "string");
            full.putArray("required").add("scheme").add("id");
            return full;
        }
    ),
    RecurrenceRule.class, ShorthandDefinition.of(
        config -> {
            ObjectNode n = config.createObjectNode();
            n.put("type", "string").put("pattern", "^FREQ=");
            return n;
        },
        config -> {
            ObjectNode full = config.createObjectNode();
            full.put("type", "object");
            ObjectNode props = full.putObject("properties");
            ObjectNode freq = props.putObject("freq");
            freq.put("type", "string");
            freq.putArray("enum")
                .add("DAILY").add("WEEKLY").add("MONTHLY").add("YEARLY");
            props.putObject("interval").put("type", "integer").put("minimum", 1);
            props.putObject("count").put("type", "integer").put("minimum", 1);
            props.putObject("until").put("type", "string").put("format", "date-time");
            ObjectNode byDay = props.putObject("byDay");
            byDay.put("type", "array");
            ObjectNode byDayItems = byDay.putObject("items");
            byDayItems.put("type", "string");
            byDayItems.putArray("enum")
                .add("MO").add("TU").add("WE").add("TH").add("FR").add("SA").add("SU");
            full.putArray("required").add("freq");
            return full;
        }
    )
);
```

Add required imports:
```java
import io.casehub.schema.generator.module.ShorthandDefinition;
import io.casehub.schema.generator.module.ShorthandModule;
```

- [ ] **Step 2: Update constructor to use platform ShorthandModule**

Replace the constructor line:
```java
builder.with(new ShorthandModule());
```
With:
```java
builder.with(new ShorthandModule(SHORTHAND_DEFINITIONS));
```

- [ ] **Step 3: Run tests with both modules present**

Before deleting the local ShorthandModule, verify the platform version produces identical output. The import change in Step 1 means the constructor now uses the platform class; the local file is unused.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all tests PASS (CognitiveSchemaGeneratorTest verifies schema equivalence)

Note: `ShorthandModuleTest` will still pass because it references the local `ShorthandModule` — it hasn't been updated yet.

- [ ] **Step 4: Delete local ShorthandModule**

Use `ide_refactor_safe_delete` on `schema-generator/src/main/java/io/casehub/neocortex/schema/ShorthandModule.java`.

Expected usage warning: `ShorthandModuleTest` still references the local class. Force the delete — we update the test next.

- [ ] **Step 5: Update ShorthandModuleTest to use platform module**

Replace the import and `generator()` method to use the platform `ShorthandModule` with `CognitiveSchemaGenerator.SHORTHAND_DEFINITIONS`:

Replace imports:
```java
// Remove (no longer exists):
// import io.casehub.neocortex.schema.ShorthandModule;
// (was same-package, no explicit import)

// Add:
import io.casehub.schema.generator.module.ShorthandModule;
```

Replace the `generator()` method:
```java
private SchemaGenerator generator() {
    var builder = new SchemaGeneratorConfigBuilder(
        SchemaVersion.DRAFT_2020_12, OptionPreset.PLAIN_JSON);
    builder.with(Option.DEFINITIONS_FOR_ALL_OBJECTS);
    builder.with(new ShorthandModule(CognitiveSchemaGenerator.SHORTHAND_DEFINITIONS));
    return new SchemaGenerator(builder.build());
}
```

All 9 test methods remain unchanged — they verify schema structure, which is identical.

- [ ] **Step 6: Verify all tests pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add schema-generator/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor: migrate ShorthandModule to shared platform version

Replace local ShorthandModule with io.casehub.schema.generator.module.ShorthandModule
from casehub-platform-schema-generator. Build ShorthandDefinition registrations for
Confidence, NodeRef, and RecurrenceRule inline in CognitiveSchemaGenerator. Update
ShorthandModuleTest to use platform module with neocortex definitions.

Closes #290
Refs #291"
```

## References

- [specs/issue-291-migrate-schema-modules/2026-09-15-migrate-schema-modules-design.md] — design spec
- [CognitiveSchemaGenerator.java:56-68] — current module wiring
- [ShorthandModule.java (local)] — current hardcoded implementation (117 lines)
- [EnumInliningModule.java (local)] — current implementation (43 lines)
- [ShorthandDefinition (platform)] — new API interface
- [ShorthandModule (platform)] — new generic implementation
- [GitHub #291] — parent migration issue
- [GitHub #290] — ShorthandModule-specific migration issue
- [casehubio/platform#279] — SealedHierarchyModule extraction
- [casehubio/platform#280] — ShorthandModule extraction
