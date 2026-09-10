# YAML Schema Conventions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #247 — feat: YAML schema design — conventions for cognitive type configuration
**Issue group:** #253, #247

**Goal:** Implement a victools jsonschema-generator module that generates JSON Schema with oneOf + discriminator for sealed hierarchies, shorthand support for polymorphic types, and enum inlining — validating the YAML conventions established in the design spec.

**Architecture:** New `schema-generator` Maven module in neocortex containing three victools `Module` implementations: `SealedHierarchyModule` (sealed interface → oneOf + const discriminator), `ShorthandModule` (scalar-or-object for Confidence/NodeRef/RecurrenceRule), and `EnumInliningModule` (inline enum values). A `CognitiveSchemaGenerator` wires them together and generates JSON Schema Draft 2020-12 for cognitive types. The conventions document is promoted to the project repo as the authoritative reference.

**Tech Stack:** Java 21, victools jsonschema-generator 4.38.0, Jackson YAML, JUnit 5

## Global Constraints

- Java 21 language level (on Java 26 JVM)
- victools jsonschema-generator 4.38.0 (same version as engine)
- JSON Schema Draft 2020-12
- camelCase for all YAML property keys
- `type` as the discriminator property name for all sealed hierarchies
- Module has zero Quarkus/CDI dependencies — pure Java + victools

---

## Batch 1: schema-generator module + SealedHierarchyModule

### Task 1: Create schema-generator module and implement SealedHierarchyModule

**Files:**
- Create: `schema-generator/pom.xml`
- Create: `schema-generator/src/main/java/io/casehub/neocortex/schema/SealedHierarchyModule.java`
- Create: `schema-generator/src/main/java/io/casehub/neocortex/schema/EnumInliningModule.java`
- Create: `schema-generator/src/test/java/io/casehub/neocortex/schema/SealedHierarchyModuleTest.java`
- Create: `schema-generator/src/test/java/io/casehub/neocortex/schema/EnumInliningModuleTest.java`
- Modify: `pom.xml` (parent — add module + dependencyManagement entry)

**Interfaces:**
- Produces: `SealedHierarchyModule implements com.github.victools.jsonschema.generator.Module` — constructor accepts `Map<Class<?>, Map<Class<?>, String>>` discriminator overrides
- Produces: `EnumInliningModule implements Module` — no-arg constructor

- [ ] **Step 1: Create schema-generator/pom.xml**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>0.2-SNAPSHOT</version>
    </parent>
    <artifactId>casehub-neocortex-schema-generator</artifactId>
    <name>CaseHub Neocortex Schema Generator</name>
    <description>JSON Schema generation for cognitive types — sealed hierarchy oneOf, enum inlining, shorthand polymorphism</description>

    <properties>
        <version.victools.jsonschema>4.38.0</version.victools.jsonschema>
    </properties>

    <dependencies>
        <dependency>
            <groupId>com.github.victools</groupId>
            <artifactId>jsonschema-generator</artifactId>
            <version>${version.victools.jsonschema}</version>
        </dependency>
        <dependency>
            <groupId>com.github.victools</groupId>
            <artifactId>jsonschema-module-jackson</artifactId>
            <version>${version.victools.jsonschema}</version>
        </dependency>
        <dependency>
            <groupId>com.fasterxml.jackson.dataformat</groupId>
            <artifactId>jackson-dataformat-yaml</artifactId>
        </dependency>

        <!-- Test — cognitive types for schema generation verification -->
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-cognitive-api</artifactId>
            <version>${project.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-api</artifactId>
            <version>${project.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-mindmap-api</artifactId>
            <version>${project.version}</version>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.assertj</groupId>
            <artifactId>assertj-core</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 2: Add module to parent pom.xml**

Add `<module>schema-generator</module>` to the `<modules>` section (after `mindmap-intelligence`), and add a `<dependency>` entry to `<dependencyManagement>`:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-schema-generator</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Write failing test for SealedHierarchyModule — basic sealed interface generates oneOf**

```java
package io.casehub.neocortex.schema;

import com.fasterxml.jackson.databind.JsonNode;
import com.github.victools.jsonschema.generator.Option;
import com.github.victools.jsonschema.generator.OptionPreset;
import com.github.victools.jsonschema.generator.SchemaGenerator;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfigBuilder;
import com.github.victools.jsonschema.generator.SchemaVersion;
import io.casehub.neocortex.cognitive.TemporalMark;
import java.util.Map;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class SealedHierarchyModuleTest {

    private SchemaGenerator generator(Map<Class<?>, Map<Class<?>, String>> overrides) {
        var builder = new SchemaGeneratorConfigBuilder(
            SchemaVersion.DRAFT_2020_12, OptionPreset.PLAIN_JSON);
        builder.with(Option.DEFINITIONS_FOR_ALL_OBJECTS);
        builder.with(new SealedHierarchyModule(overrides));
        return new SchemaGenerator(builder.build());
    }

    private SchemaGenerator generator() {
        return generator(Map.of());
    }

    @Test
    void sealedInterface_generatesOneOf_withTypeDiscriminator() {
        var schema = generator().generateSchema(TemporalMark.class);

        var oneOf = schema.get("oneOf");
        assertThat(oneOf).isNotNull();
        assertThat(oneOf.isArray()).isTrue();
        assertThat(oneOf.size()).isEqualTo(3);
    }

    @Test
    void discriminatorValues_areLowerCamelCase_byDefault() {
        var schema = generator().generateSchema(TemporalMark.class);

        var oneOf = schema.get("oneOf");
        var discriminatorValues = new java.util.ArrayList<String>();
        for (var entry : oneOf) {
            var allOf = entry.get("allOf");
            if (allOf != null) {
                for (var item : allOf) {
                    var props = item.get("properties");
                    if (props != null && props.has("type")) {
                        discriminatorValues.add(
                            props.get("type").get("const").asText());
                    }
                }
            }
        }

        assertThat(discriminatorValues).containsExactlyInAnyOrder(
            "wallClock", "relative", "ordinal");
    }

    @Test
    void discriminatorOverrides_replaceDefaultValues() {
        var overrides = Map.<Class<?>, Map<Class<?>, String>>of(
            TemporalMark.class, Map.of(
                TemporalMark.WallClock.class, "wall-clock"
            )
        );
        var schema = generator(overrides).generateSchema(TemporalMark.class);

        var oneOf = schema.get("oneOf");
        boolean foundOverride = false;
        for (var entry : oneOf) {
            var allOf = entry.get("allOf");
            if (allOf != null) {
                for (var item : allOf) {
                    var props = item.get("properties");
                    if (props != null && props.has("type")) {
                        if ("wall-clock".equals(
                                props.get("type").get("const").asText())) {
                            foundOverride = true;
                        }
                    }
                }
            }
        }
        assertThat(foundOverride).isTrue();
    }

    @Test
    void nonSealedType_isNotIntercepted() {
        var schema = generator().generateSchema(String.class);
        assertThat(schema.has("oneOf")).isFalse();
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -Dtest=SealedHierarchyModuleTest -f pom.xml`
Expected: Compilation failure — `SealedHierarchyModule` class does not exist.

- [ ] **Step 5: Implement SealedHierarchyModule**

```java
package io.casehub.neocortex.schema;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.github.victools.jsonschema.generator.CustomDefinition;
import com.github.victools.jsonschema.generator.Module;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfigBuilder;
import java.util.Map;

public class SealedHierarchyModule implements Module {

    private final Map<Class<?>, Map<Class<?>, String>> discriminatorOverrides;

    public SealedHierarchyModule() {
        this(Map.of());
    }

    public SealedHierarchyModule(Map<Class<?>, Map<Class<?>, String>> overrides) {
        this.discriminatorOverrides = Map.copyOf(overrides);
    }

    @Override
    public void applyToConfigBuilder(SchemaGeneratorConfigBuilder builder) {
        builder.forTypesInGeneral()
            .withCustomDefinitionProvider((type, context) -> {
                Class<?> erasedType = type.getErasedType();
                if (!erasedType.isSealed()) {
                    return null;
                }
                ObjectNode schema =
                    context.getGeneratorConfig().createObjectNode();
                ArrayNode oneOf = schema.putArray("oneOf");

                for (Class<?> subtype : erasedType.getPermittedSubclasses()) {
                    ObjectNode subtypeEntry = oneOf.addObject();
                    ArrayNode allOfArr = subtypeEntry.putArray("allOf");

                    ObjectNode discriminatorObj = allOfArr.addObject();
                    ObjectNode props = discriminatorObj.putObject("properties");
                    String value = resolveDiscriminator(erasedType, subtype);
                    props.putObject("type").put("const", value);
                    discriminatorObj.putArray("required").add("type");

                    ObjectNode refObj = allOfArr.addObject();
                    refObj.set("$ref",
                        context.createDefinitionReference(
                            context.resolve(subtype)));
                }

                return new CustomDefinition(schema);
            });
    }

    private String resolveDiscriminator(Class<?> parent, Class<?> subtype) {
        return discriminatorOverrides
            .getOrDefault(parent, Map.of())
            .getOrDefault(subtype, defaultDiscriminator(subtype));
    }

    static String defaultDiscriminator(Class<?> subtype) {
        String name = subtype.getSimpleName();
        return Character.toLowerCase(name.charAt(0)) + name.substring(1);
    }
}
```

- [ ] **Step 6: Implement EnumInliningModule**

```java
package io.casehub.neocortex.schema;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.github.victools.jsonschema.generator.CustomDefinition;
import com.github.victools.jsonschema.generator.Module;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfigBuilder;

public class EnumInliningModule implements Module {

    @Override
    public void applyToConfigBuilder(SchemaGeneratorConfigBuilder builder) {
        builder.forTypesInGeneral()
            .withCustomDefinitionProvider((type, context) -> {
                Class<?> erasedType = type.getErasedType();
                if (!erasedType.isEnum()) {
                    return null;
                }
                ObjectNode schema =
                    context.getGeneratorConfig().createObjectNode();
                schema.put("type", "string");
                ArrayNode enumValues = schema.putArray("enum");
                for (Object constant : erasedType.getEnumConstants()) {
                    enumValues.add(constant.toString());
                }
                return new CustomDefinition(schema, true);
            });
    }
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -Dtest=SealedHierarchyModuleTest -f pom.xml`
Expected: All 4 tests PASS.

- [ ] **Step 8: Write EnumInliningModule test**

```java
package io.casehub.neocortex.schema;

import com.fasterxml.jackson.databind.JsonNode;
import com.github.victools.jsonschema.generator.OptionPreset;
import com.github.victools.jsonschema.generator.SchemaGenerator;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfigBuilder;
import com.github.victools.jsonschema.generator.SchemaVersion;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class EnumInliningModuleTest {

    private SchemaGenerator generator() {
        var builder = new SchemaGeneratorConfigBuilder(
            SchemaVersion.DRAFT_2020_12, OptionPreset.PLAIN_JSON);
        builder.with(new EnumInliningModule());
        return new SchemaGenerator(builder.build());
    }

    @Test
    void enum_inlinedAsStringWithValues() {
        var schema = generator().generateSchema(ConfidenceOrigin.class);

        assertThat(schema.get("type").asText()).isEqualTo("string");
        var enumValues = schema.get("enum");
        assertThat(enumValues).isNotNull();
        assertThat(enumValues.size()).isEqualTo(4);
    }

    @Test
    void nonEnum_isNotIntercepted() {
        var schema = generator().generateSchema(String.class);
        assertThat(schema.has("enum")).isFalse();
    }
}
```

- [ ] **Step 9: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f pom.xml`
Expected: All 6 tests PASS.

- [ ] **Step 10: Add tests for complex sealed hierarchies — FeatureField, CbrFilter**

Add tests to `SealedHierarchyModuleTest`:

```java
@Test
void featureField_generates9Variants() {
    var schema = generator().generateSchema(
        io.casehub.neocortex.memory.cbr.FeatureField.class);

    var oneOf = schema.get("oneOf");
    assertThat(oneOf).isNotNull();
    assertThat(oneOf.size()).isEqualTo(9);
}

@Test
void cbrFilter_generates8Variants_includingRecursiveAllOf() {
    var schema = generator().generateSchema(
        io.casehub.neocortex.memory.cbr.CbrFilter.class);

    var oneOf = schema.get("oneOf");
    assertThat(oneOf).isNotNull();
    assertThat(oneOf.size()).isEqualTo(8);
}

@Test
void similaritySpec_generates6Variants_withNestedWarpingConstraint() {
    var schema = generator().generateSchema(
        io.casehub.neocortex.memory.cbr.SimilaritySpec.class);

    var oneOf = schema.get("oneOf");
    assertThat(oneOf).isNotNull();
    assertThat(oneOf.size()).isEqualTo(6);
}
```

- [ ] **Step 11: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f pom.xml`
Expected: All 9 tests PASS.

- [ ] **Step 12: Commit**

```bash
git add schema-generator/ pom.xml
git commit -m "feat(schema-generator): SealedHierarchyModule + EnumInliningModule for JSON Schema generation

Implements victools Module for sealed interface → oneOf + const discriminator.
Handles all 8 sealed hierarchies in cognitive types.

Refs #247"
```

---

## Batch 2: ShorthandModule + CognitiveSchemaGenerator + conventions doc

### Task 2: Implement ShorthandModule for scalar-or-object types

**Files:**
- Create: `schema-generator/src/main/java/io/casehub/neocortex/schema/ShorthandModule.java`
- Create: `schema-generator/src/test/java/io/casehub/neocortex/schema/ShorthandModuleTest.java`

**Interfaces:**
- Consumes: victools `Module` SPI
- Produces: `ShorthandModule implements Module` — handles Confidence, NodeRef, RecurrenceRule oneOf(scalar, object)

- [ ] **Step 1: Write failing tests for ShorthandModule**

```java
package io.casehub.neocortex.schema;

import com.fasterxml.jackson.databind.JsonNode;
import com.github.victools.jsonschema.generator.Option;
import com.github.victools.jsonschema.generator.OptionPreset;
import com.github.victools.jsonschema.generator.SchemaGenerator;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfigBuilder;
import com.github.victools.jsonschema.generator.SchemaVersion;
import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.mindmap.api.NodeRef;
import io.casehub.neocortex.mindmap.api.RecurrenceRule;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class ShorthandModuleTest {

    private SchemaGenerator generator() {
        var builder = new SchemaGeneratorConfigBuilder(
            SchemaVersion.DRAFT_2020_12, OptionPreset.PLAIN_JSON);
        builder.with(Option.DEFINITIONS_FOR_ALL_OBJECTS);
        builder.with(new ShorthandModule());
        return new SchemaGenerator(builder.build());
    }

    @Test
    void confidence_acceptsScalarNumber() {
        var schema = generator().generateSchema(Confidence.class);

        var oneOf = schema.get("oneOf");
        assertThat(oneOf).isNotNull();
        assertThat(oneOf.size()).isEqualTo(2);

        boolean hasNumber = false;
        boolean hasObject = false;
        for (var option : oneOf) {
            if ("number".equals(option.path("type").asText())) {
                hasNumber = true;
            }
            if ("object".equals(option.path("type").asText())) {
                hasObject = true;
            }
        }
        assertThat(hasNumber).isTrue();
        assertThat(hasObject).isTrue();
    }

    @Test
    void confidence_objectForm_hasOriginValueDecayReference() {
        var schema = generator().generateSchema(Confidence.class);

        var oneOf = schema.get("oneOf");
        for (var option : oneOf) {
            if ("object".equals(option.path("type").asText())) {
                var props = option.get("properties");
                assertThat(props.has("origin")).isTrue();
                assertThat(props.has("value")).isTrue();
                assertThat(props.has("decayReference")).isTrue();
                var required = option.get("required");
                assertThat(required).isNotNull();
                assertThat(required.toString()).contains("origin", "value");
                return;
            }
        }
        org.junit.jupiter.api.Assertions.fail("No object form found");
    }

    @Test
    void nodeRef_acceptsScalarString() {
        var schema = generator().generateSchema(NodeRef.class);

        var oneOf = schema.get("oneOf");
        assertThat(oneOf).isNotNull();

        boolean hasString = false;
        for (var option : oneOf) {
            if ("string".equals(option.path("type").asText())) {
                hasString = true;
            }
        }
        assertThat(hasString).isTrue();
    }

    @Test
    void recurrenceRule_acceptsScalarString() {
        var schema = generator().generateSchema(RecurrenceRule.class);

        var oneOf = schema.get("oneOf");
        assertThat(oneOf).isNotNull();

        boolean hasString = false;
        for (var option : oneOf) {
            if ("string".equals(option.path("type").asText())) {
                hasString = true;
            }
        }
        assertThat(hasString).isTrue();
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -Dtest=ShorthandModuleTest -f pom.xml`
Expected: Compilation failure — `ShorthandModule` class does not exist.

- [ ] **Step 3: Implement ShorthandModule**

```java
package io.casehub.neocortex.schema;

import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.github.victools.jsonschema.generator.CustomDefinition;
import com.github.victools.jsonschema.generator.Module;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfigBuilder;
import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.mindmap.api.NodeRef;
import io.casehub.neocortex.mindmap.api.RecurrenceRule;

public class ShorthandModule implements Module {

    @Override
    public void applyToConfigBuilder(SchemaGeneratorConfigBuilder builder) {
        builder.forTypesInGeneral()
            .withCustomDefinitionProvider((type, context) -> {
                Class<?> erasedType = type.getErasedType();
                if (erasedType == Confidence.class) {
                    return confidenceSchema(context.getGeneratorConfig());
                }
                if (erasedType == NodeRef.class) {
                    return nodeRefSchema(context.getGeneratorConfig());
                }
                if (erasedType == RecurrenceRule.class) {
                    return recurrenceRuleSchema(context.getGeneratorConfig());
                }
                return null;
            });
    }

    private CustomDefinition confidenceSchema(
            com.github.victools.jsonschema.generator.SchemaGeneratorConfig config) {
        ObjectNode schema = config.createObjectNode();
        ArrayNode oneOf = schema.putArray("oneOf");

        oneOf.addObject().put("type", "number")
            .put("minimum", 0).put("maximum", 1);

        ObjectNode full = oneOf.addObject();
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

        return new CustomDefinition(schema);
    }

    private CustomDefinition nodeRefSchema(
            com.github.victools.jsonschema.generator.SchemaGeneratorConfig config) {
        ObjectNode schema = config.createObjectNode();
        ArrayNode oneOf = schema.putArray("oneOf");

        oneOf.addObject().put("type", "string")
            .put("pattern", "^[^:]+:.+$");

        ObjectNode full = oneOf.addObject();
        full.put("type", "object");
        ObjectNode props = full.putObject("properties");
        props.putObject("scheme").put("type", "string");
        props.putObject("id").put("type", "string");
        props.putObject("qualifier").put("type", "string");
        full.putArray("required").add("scheme").add("id");

        return new CustomDefinition(schema);
    }

    private CustomDefinition recurrenceRuleSchema(
            com.github.victools.jsonschema.generator.SchemaGeneratorConfig config) {
        ObjectNode schema = config.createObjectNode();
        ArrayNode oneOf = schema.putArray("oneOf");

        oneOf.addObject().put("type", "string")
            .put("pattern", "^FREQ=");

        ObjectNode full = oneOf.addObject();
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

        return new CustomDefinition(schema);
    }
}
```

Note: ShorthandModule imports Confidence, NodeRef, RecurrenceRule at compile time. These must be moved from test to compile scope in pom.xml:

Move `casehub-neocortex-cognitive-api` and `casehub-neocortex-mindmap-api` from test to compile scope in `schema-generator/pom.xml`:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-cognitive-api</artifactId>
    <version>${project.version}</version>
</dependency>
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-mindmap-api</artifactId>
    <version>${project.version}</version>
</dependency>
```

Keep `casehub-neocortex-memory-api` at test scope (only SealedHierarchyModule tests use it).

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f pom.xml`
Expected: All 13 tests PASS (9 from Task 1 + 4 new).

- [ ] **Step 5: Commit**

```bash
git add schema-generator/
git commit -m "feat(schema-generator): ShorthandModule for Confidence/NodeRef/RecurrenceRule polymorphism

Scalar-or-object oneOf schema for types with natural shorthand forms.

Refs #247"
```

### Task 3: CognitiveSchemaGenerator + integration test + conventions doc promotion

**Files:**
- Create: `schema-generator/src/main/java/io/casehub/neocortex/schema/CognitiveSchemaGenerator.java`
- Create: `schema-generator/src/test/java/io/casehub/neocortex/schema/CognitiveSchemaGeneratorTest.java`
- Copy: `specs/.../2026-09-01-yaml-schema-conventions-design.md` → `docs/specs/2026-09-01-yaml-schema-conventions.md` (project repo)

**Interfaces:**
- Consumes: `SealedHierarchyModule`, `EnumInliningModule`, `ShorthandModule`
- Produces: `CognitiveSchemaGenerator` — `generate(Class<?>) → JsonNode`, `generateToYaml(Class<?>, Path)`

- [ ] **Step 1: Write failing integration test**

```java
package io.casehub.neocortex.schema;

import com.fasterxml.jackson.databind.JsonNode;
import io.casehub.neocortex.memory.cbr.CbrFeatureSchema;
import io.casehub.neocortex.memory.cbr.CbrQuery;
import io.casehub.neocortex.memory.cbr.FeatureField;
import io.casehub.neocortex.memory.cbr.FeatureValue;
import io.casehub.neocortex.memory.cbr.CbrFilter;
import io.casehub.neocortex.memory.cbr.SimilaritySpec;
import io.casehub.neocortex.memory.cbr.TemporalDecay;
import io.casehub.neocortex.memory.cbr.ScopeDecay;
import io.casehub.neocortex.cognitive.TemporalMark;
import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import static org.assertj.core.api.Assertions.assertThat;

class CognitiveSchemaGeneratorTest {

    private final CognitiveSchemaGenerator generator = new CognitiveSchemaGenerator();

    @Test
    void cbrFeatureSchema_generatesValidSchema() {
        var schema = generator.generate(CbrFeatureSchema.class);

        assertThat(schema).isNotNull();
        assertThat(schema.has("$defs") || schema.has("properties")).isTrue();
    }

    @Test
    void sealedHierarchies_allGenerateOneOf() {
        for (var sealedType : new Class<?>[] {
                FeatureField.class, CbrFilter.class, SimilaritySpec.class,
                TemporalDecay.class, ScopeDecay.class, TemporalMark.class }) {
            var schema = generator.generate(sealedType);
            assertThat(schema.has("oneOf"))
                .as("Expected oneOf for %s", sealedType.getSimpleName())
                .isTrue();
        }
    }

    @Test
    void confidence_generatesShorthandOneOf() {
        var schema = generator.generate(Confidence.class);

        var oneOf = schema.get("oneOf");
        assertThat(oneOf).isNotNull();
        assertThat(oneOf.size()).isEqualTo(2);
    }

    @Test
    void confidenceOrigin_generatesInlinedEnum() {
        var schema = generator.generate(ConfidenceOrigin.class);

        assertThat(schema.get("type").asText()).isEqualTo("string");
        assertThat(schema.has("enum")).isTrue();
    }

    @Test
    void generateToYaml_writesFile(@TempDir Path tempDir) throws IOException {
        Path output = tempDir.resolve("schema.yaml");
        generator.generateToYaml(TemporalMark.class, output);

        assertThat(output).exists();
        String content = Files.readString(output);
        assertThat(content).contains("oneOf");
        assertThat(content).contains("wallClock");
    }

    @Test
    void discriminatorOverrides_applied() {
        var schema = generator.generate(SimilaritySpec.class);

        var oneOf = schema.get("oneOf");
        boolean foundGaussian = false;
        for (var entry : oneOf) {
            var allOf = entry.get("allOf");
            if (allOf != null) {
                for (var item : allOf) {
                    var props = item.get("properties");
                    if (props != null && props.has("type")) {
                        String val = props.get("type").get("const").asText();
                        if ("gaussian".equals(val)) {
                            foundGaussian = true;
                        }
                    }
                }
            }
        }
        assertThat(foundGaussian)
            .as("Expected discriminator override: gaussian (not gaussianDecay)")
            .isTrue();
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -Dtest=CognitiveSchemaGeneratorTest -f pom.xml`
Expected: Compilation failure — `CognitiveSchemaGenerator` does not exist.

- [ ] **Step 3: Implement CognitiveSchemaGenerator**

```java
package io.casehub.neocortex.schema;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import com.fasterxml.jackson.dataformat.yaml.YAMLGenerator;
import com.github.victools.jsonschema.generator.Option;
import com.github.victools.jsonschema.generator.OptionPreset;
import com.github.victools.jsonschema.generator.SchemaGenerator;
import com.github.victools.jsonschema.generator.SchemaGeneratorConfigBuilder;
import com.github.victools.jsonschema.generator.SchemaVersion;
import com.github.victools.jsonschema.module.jackson.JacksonModule;
import com.github.victools.jsonschema.module.jackson.JacksonOption;
import io.casehub.neocortex.memory.cbr.SimilaritySpec;
import io.casehub.neocortex.memory.cbr.WarpingConstraint;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

public class CognitiveSchemaGenerator {

    private static final Map<Class<?>, Map<Class<?>, String>> DISCRIMINATOR_OVERRIDES =
        Map.of(
            SimilaritySpec.class, Map.of(
                SimilaritySpec.GaussianDecay.class, "gaussian",
                SimilaritySpec.StepDecay.class, "step",
                SimilaritySpec.ExponentialDecay.class, "exponential",
                SimilaritySpec.DtwSpec.class, "dtw",
                SimilaritySpec.EditDistanceSpec.class, "editDistance"
            ),
            WarpingConstraint.class, Map.of(
                WarpingConstraint.ItakuraParallelogram.class, "itakura"
            )
        );

    private final SchemaGenerator schemaGenerator;

    public CognitiveSchemaGenerator() {
        var builder = new SchemaGeneratorConfigBuilder(
            SchemaVersion.DRAFT_2020_12, OptionPreset.PLAIN_JSON);

        builder.with(Option.DEFINITIONS_FOR_ALL_OBJECTS);
        builder.with(Option.FLATTENED_ENUMS_FROM_TOSTRING);
        builder.with(new JacksonModule(JacksonOption.RESPECT_JSONPROPERTY_ORDER));
        builder.with(new EnumInliningModule());
        builder.with(new SealedHierarchyModule(DISCRIMINATOR_OVERRIDES));
        builder.with(new ShorthandModule());

        this.schemaGenerator = new SchemaGenerator(builder.build());
    }

    public JsonNode generate(Class<?> rootType) {
        return schemaGenerator.generateSchema(rootType);
    }

    public void generateToYaml(Class<?> rootType, Path output) throws IOException {
        JsonNode schema = generate(rootType);
        ObjectMapper yamlMapper = new ObjectMapper(
            new YAMLFactory()
                .disable(YAMLGenerator.Feature.WRITE_DOC_START_MARKER)
                .enable(YAMLGenerator.Feature.MINIMIZE_QUOTES));
        Files.createDirectories(output.getParent());
        yamlMapper.writerWithDefaultPrettyPrinter()
            .writeValue(output.toFile(), schema);
    }
}
```

Note: CognitiveSchemaGenerator imports SimilaritySpec and WarpingConstraint for the DISCRIMINATOR_OVERRIDES map. Add `casehub-neocortex-memory-api` to compile scope in `schema-generator/pom.xml`:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-api</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 4: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f pom.xml`
Expected: All 19 tests PASS.

- [ ] **Step 5: Verify full reactor build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests -f pom.xml`
Expected: BUILD SUCCESS — schema-generator module compiles with all dependencies.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -f pom.xml`
Expected: All tests PASS.

- [ ] **Step 6: Promote conventions doc to project repo**

Copy the spec as the authoritative conventions reference:

```bash
cp specs/issue-253-cognitive-rearchitecture/2026-09-01-yaml-schema-conventions-design.md \
   docs/specs/2026-09-01-yaml-schema-conventions.md
```

- [ ] **Step 7: Update CLAUDE.md module table**

Add the schema-generator module to CLAUDE.md's Module Structure and Maven Coordinates sections.

- [ ] **Step 8: Commit**

```bash
git add schema-generator/ pom.xml docs/specs/ CLAUDE.md
git commit -m "feat(schema-generator): CognitiveSchemaGenerator + conventions doc promotion

Wires SealedHierarchyModule, EnumInliningModule, ShorthandModule with
discriminator overrides for SimilaritySpec and WarpingConstraint.
Promotes YAML schema conventions spec to docs/specs/.

Closes #247"
```

---

## References

- `specs/issue-253-cognitive-rearchitecture/2026-09-01-yaml-schema-conventions-design.md` — design spec
- `engine/generator/src/main/java/io/casehub/generator/CaseHubSchemaGenerator.java` — victools wiring pattern
- `engine/generator/src/main/java/io/casehub/generator/module/EnumInliningModule.java` — enum inlining source
- `engine/generator/pom.xml` — victools version (4.38.0)
- `cognitive-api/pom.xml` — zero-dep module template
- GE-20260824-2eb1d7 — victools custom module patterns
- GE-20260825-ba18b3 — sealed hierarchy type discriminator pattern
- GitHub #247 — focal issue
- GitHub #253 — parent epic
