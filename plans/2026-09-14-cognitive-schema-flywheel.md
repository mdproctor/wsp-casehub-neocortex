# Cognitive Schema Flywheel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #335 — epic: cognitive schema flywheel
**Issue group:** #335, #292, #293, #334

**Goal:** Close the cognitive flywheel: schema discovery → guided extraction → better discovery, with optional dev-time promotion to Java trait interfaces.

**Architecture:** Three layers: (1) SchemaDiscoveryPhase consolidation phase analyzes property patterns and writes schema to type nodes, (2) MindMapExtractor reads schemas and injects them into extraction prompts as profile data, (3) TraitInterfaceGenerator CLI produces Java source files from stabilized schemas. The runtime flywheel runs on schema DATA in type node properties — no Java interfaces involved.

**Tech Stack:** Java 21, Quarkus 3.32.2, InMemoryMindMapStore (tests)

## Global Constraints

- Java 21 source, Java 26 JVM
- Build with `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All commits reference an issue: `Refs #292`, `Refs #293`, or `Refs #334`
- SchemaField backward compatibility — existing 3-arg constructor must continue to work
- `schema.{field}.source` provenance: `java` for interface-derived, `discovered` for LLM-observed
- Java-derived schema fields are immutable by discovery (source=java fields never overwritten)

---

## Batch 1: SchemaField Extension + TypeRegistry Provenance

### Task 1: Extend SchemaField record with new fields

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SchemaField.java`
- Test: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/SchemaFieldTest.java`

**Interfaces:**
- Produces: `SchemaField(String name, String type, boolean required, boolean collection, String description, List<String> enumValues)` — record with backward-compatible 3-arg constructor

- [ ] **Step 1: Write the failing test**

```java
package io.casehub.neocortex.mindmap;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.assertThat;

class SchemaFieldTest {

    @Test
    void threeArgConstructor_setsDefaults() {
        var sf = new SchemaField("name", "string", true);
        assertThat(sf.collection()).isFalse();
        assertThat(sf.description()).isNull();
        assertThat(sf.enumValues()).isNull();
    }

    @Test
    void fullConstructor_setsAllFields() {
        var sf = new SchemaField("status", "string", false, false,
            "current status", List.of("active", "completed", "cancelled"));
        assertThat(sf.name()).isEqualTo("status");
        assertThat(sf.type()).isEqualTo("string");
        assertThat(sf.required()).isFalse();
        assertThat(sf.collection()).isFalse();
        assertThat(sf.description()).isEqualTo("current status");
        assertThat(sf.enumValues()).containsExactly("active", "completed", "cancelled");
    }

    @Test
    void collectionField_flagsCorrectly() {
        var sf = new SchemaField("attendees", "string", false, true, null, null);
        assertThat(sf.collection()).isTrue();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=SchemaFieldTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — SchemaField only has 3 fields

- [ ] **Step 3: Implement SchemaField extension**

Replace the SchemaField record:

```java
package io.casehub.neocortex.mindmap;

import java.util.List;

public record SchemaField(
    String name,
    String type,
    boolean required,
    boolean collection,
    String description,
    List<String> enumValues
) {
    public SchemaField(String name, String type, boolean required) {
        this(name, type, required, false, null, null);
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=SchemaFieldTest`
Expected: PASS

- [ ] **Step 5: Verify no compilation breakage across modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl mindmap-api,mindmap-intelligence,mindmap,mindmap-inmem,mindmap-sqlite,mindmap-testing,cognitive-index,schema-generator`
Expected: BUILD SUCCESS — existing 3-arg callers still compile

- [ ] **Step 6: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SchemaField.java mindmap-api/src/test/java/io/casehub/neocortex/mindmap/SchemaFieldTest.java
git commit -m "feat(mindmap-api): extend SchemaField with collection, description, enumValues

Backward-compatible — existing 3-arg constructor delegates to full
constructor with defaults (collection=false, description=null,
enumValues=null).

Refs #292"
```

### Task 2: Add provenance tracking to TypeRegistry

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistry.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistryTest.java`

**Interfaces:**
- Consumes: `SchemaField(name, type, required, collection, description, enumValues)` from Task 1
- Produces: `TypeRegistry.schemaFor(String, String)` returns extended SchemaField; `registerType(String, String, Class<?>, String)` writes `schema.{field}.source=java`

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class TypeRegistryProvenanceTest {

    private InMemoryMindMapStore store;
    private TypeRegistry registry;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        registry = new TypeRegistry(store);
    }

    @Test
    void registerType_withJavaClass_writesSourceJava() {
        registry.registerType("person", null, Personable.class, "t1");
        MindMapNode typeNode = findTypeNode("person", "t1");
        assertThat(typeNode.property("schema.role.source")).hasValue("java");
    }

    @Test
    void schemaFor_readsCollectionAndDescriptionFields() {
        registry.registerType("meeting", null, null, "t1");
        MindMapNode typeNode = findTypeNode("meeting", "t1");
        store.updateNode(typeNode.id(), new NodeUpdate(
            null, null, null, null, null, null, null, null,
            null, null, null,
            Map.of(
                "schema.attendees.type", "string",
                "schema.attendees.required", "false",
                "schema.attendees.collection", "true",
                "schema.attendees.description", "people attending",
                "schema.attendees.source", "discovered"
            ), null), "t1");

        Map<String, SchemaField> schema = registry.schemaFor("meeting", "t1");
        SchemaField attendees = schema.get("attendees");
        assertThat(attendees).isNotNull();
        assertThat(attendees.collection()).isTrue();
        assertThat(attendees.description()).isEqualTo("people attending");
        assertThat(attendees.type()).isEqualTo("string");
    }

    @Test
    void schemaFor_javaAndDiscovered_mergeWithJavaPrecedence() {
        registry.registerType("person", null, Personable.class, "t1");
        MindMapNode typeNode = findTypeNode("person", "t1");
        store.updateNode(typeNode.id(), new NodeUpdate(
            null, null, null, null, null, null, null, null,
            null, null, null,
            Map.of(
                "schema.department.type", "string",
                "schema.department.source", "discovered",
                "schema.department.description", "org department"
            ), null), "t1");

        Map<String, SchemaField> schema = registry.schemaFor("person", "t1");
        assertThat(schema).containsKey("role");
        assertThat(schema).containsKey("department");
        assertThat(schema.get("department").description()).isEqualTo("org department");
    }

    private MindMapNode findTypeNode(String typeName, String tenantId) {
        return store.search(MindMapQuery.of(tenantId, 100)
            .withType(SubgraphTypes.TYPE_SYSTEM)).stream()
            .filter(n -> n.name().equals(typeName))
            .findFirst().orElseThrow();
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=TypeRegistryProvenanceTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — source property not written, new SchemaField fields not read

- [ ] **Step 3: Update TypeRegistry.registerType to write source=java**

In `registerType(String, String, Class<?>, String)`, after writing schema properties from `deriveSchemaFromInterface`, add a `schema.{field}.source=java` property for each field:

```java
deriveSchemaFromInterface(javaClass).forEach((fieldName, sf) -> {
    props.put(SCHEMA_PREFIX + fieldName + ".type", sf.type());
    props.put(SCHEMA_PREFIX + fieldName + ".source", "java");
});
```

- [ ] **Step 4: Update TypeRegistry.schemaFor to read extended fields**

Update `schemaFor()` to read collection, description, enumValues, and source from type node properties. After the existing `schema.{field}.type` parsing:

```java
boolean collection = Boolean.parseBoolean(
    typeNode.property(SCHEMA_PREFIX + fieldName + ".collection").orElse("false"));
String description = typeNode.property(SCHEMA_PREFIX + fieldName + ".description").orElse(null);
String enumStr = typeNode.property(SCHEMA_PREFIX + fieldName + ".enum").orElse(null);
List<String> enumValues = enumStr != null
    ? List.of(enumStr.split(",")) : null;
schema.put(fieldName, new SchemaField(fieldName, value, required, collection, description, enumValues));
```

Also update the Java fallback path to use the extended constructor:

```java
if (schema.isEmpty()) {
    return javaClass(typeName, tenantId)
        .map(TypeRegistry::deriveSchemaFromInterface)
        .orElse(Map.of());
}
```

Merge Java-derived schema with property-based schema (Java takes precedence):

```java
Map<String, SchemaField> javaSchema = javaClass(typeName, tenantId)
    .map(TypeRegistry::deriveSchemaFromInterface)
    .orElse(Map.of());
Map<String, SchemaField> merged = new LinkedHashMap<>(schema);
javaSchema.forEach(merged::putIfAbsent);
return merged;
```

Wait — actually the logic should be: read properties first, then merge Java-derived fields. Java fields should NOT overwrite discovered fields that have richer metadata (description, enumValues). But if both exist for the same field name, Java's type wins. The simplest approach: properties-based schema is the primary result; Java-derived schema fills gaps only. This is already what the existing code does (Java fallback only when `schema.isEmpty()`). With provenance tracking (source=java written at registration), the property-based path handles Java-derived fields too. So the merge is: read all `schema.*` properties (both java and discovered fields are there), fall back to `deriveSchemaFromInterface` ONLY when no `schema.*` properties exist at all.

Keep the existing fallback logic unchanged — it already works correctly because `registerType` now writes `schema.*.source=java` alongside `schema.*.type`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=TypeRegistryProvenanceTest`
Expected: PASS

- [ ] **Step 6: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: PASS — no regressions in existing TypeRegistry tests

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistry.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistryProvenanceTest.java
git commit -m "feat(type-registry): provenance tracking and extended SchemaField support

registerType with Java class writes schema.{field}.source=java.
schemaFor reads collection, description, enumValues from type node
properties. Java-derived fields are protected from discovery overwrite.

Refs #292"
```

## Batch 2: Schema Discovery Phase

### Task 3: Implement SchemaDiscoveryPhase

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SchemaDiscoveryPhase.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SchemaDiscoveryConfig.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SchemaDiscoveryPhaseTest.java`

**Interfaces:**
- Consumes: `ConsolidationPhase` SPI, `MindMapStore.search(MindMapQuery)`, `TypeRegistry.schemaFor(String, String)`, `SchemaField` from Task 1
- Produces: `SchemaDiscoveryPhase.run(String tenantId, List<String> subgraphPriority)` — writes `schema.*` properties to type nodes

- [ ] **Step 1: Write the config record**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.smallrye.config.ConfigMapping;
import io.smallrye.config.WithDefault;

@ConfigMapping(prefix = "casehub.mindmap.schema-discovery")
public interface SchemaDiscoveryConfig {
    @WithDefault("0.8")
    double threshold();

    @WithDefault("5")
    int minSamples();

    @WithDefault("0.95")
    double requiredThreshold();
}
```

- [ ] **Step 2: Write the failing tests**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import io.casehub.neocortex.mindmap.intelligence.TypeRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class SchemaDiscoveryPhaseTest {

    private InMemoryMindMapStore store;
    private TypeRegistry registry;
    private SchemaDiscoveryPhase phase;
    private String sgId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        registry = new TypeRegistry(store);
        phase = new SchemaDiscoveryPhase(store, registry, 0.8, 5, 0.95);
        sgId = store.createSubgraph(
            new SubgraphInput("Meetings", "meeting", null), "t1");
        registry.registerType("meeting", null, "t1");
    }

    @Test
    void discoversSchema_whenPropertyFrequencyAboveThreshold() {
        for (int i = 0; i < 5; i++) {
            store.addNode(NodeInput.of("meeting-" + i, sgId)
                .withProperties(Map.of("date", "2026-01-0" + (i + 1),
                                       "agenda", "topic-" + i)), "t1");
        }
        phase.run("t1", List.of("meeting"));

        Map<String, SchemaField> schema = registry.schemaFor("meeting", "t1");
        assertThat(schema).containsKey("date");
        assertThat(schema).containsKey("agenda");
        assertThat(schema.get("date").type()).isEqualTo("string");
    }

    @Test
    void skipsProperty_belowThreshold() {
        for (int i = 0; i < 5; i++) {
            Map<String, String> props = new java.util.HashMap<>(Map.of("date", "2026-01-01"));
            if (i < 3) props.put("location", "room-" + i);
            store.addNode(NodeInput.of("meeting-" + i, sgId)
                .withProperties(props), "t1");
        }
        phase.run("t1", List.of("meeting"));

        Map<String, SchemaField> schema = registry.schemaFor("meeting", "t1");
        assertThat(schema).containsKey("date");
        assertThat(schema).doesNotContainKey("location");
    }

    @Test
    void skipsType_belowMinSamples() {
        for (int i = 0; i < 4; i++) {
            store.addNode(NodeInput.of("meeting-" + i, sgId)
                .withProperties(Map.of("date", "2026-01-01")), "t1");
        }
        phase.run("t1", List.of("meeting"));

        Map<String, SchemaField> schema = registry.schemaFor("meeting", "t1");
        assertThat(schema).isEmpty();
    }

    @Test
    void setsRequired_whenFrequencyAboveRequiredThreshold() {
        for (int i = 0; i < 5; i++) {
            store.addNode(NodeInput.of("meeting-" + i, sgId)
                .withProperties(Map.of("date", "2026-01-0" + (i + 1))), "t1");
        }
        phase.run("t1", List.of("meeting"));

        SchemaField date = registry.schemaFor("meeting", "t1").get("date");
        assertThat(date).isNotNull();
        assertThat(date.required()).isTrue();
    }

    @Test
    void doesNotOverwrite_javaSourcedFields() {
        registry.registerType("person", null, Personable.class, "t1");
        String personSgId = store.createSubgraph(
            new SubgraphInput("People", SubgraphTypes.PERSON, null), "t1");
        for (int i = 0; i < 5; i++) {
            store.addNode(NodeInput.of("person-" + i, personSgId)
                .withProperties(Map.of("role", "engineer", "department", "eng")), "t1");
        }
        phase.run("t1", List.of(SubgraphTypes.PERSON));

        Map<String, SchemaField> schema = registry.schemaFor("person", "t1");
        assertThat(schema).containsKey("department");
        MindMapNode typeNode = store.search(MindMapQuery.of("t1", 100)
            .withType(SubgraphTypes.TYPE_SYSTEM)).stream()
            .filter(n -> n.name().equals("person")).findFirst().orElseThrow();
        assertThat(typeNode.property("schema.role.source")).hasValue("java");
        assertThat(typeNode.property("schema.department.source")).hasValue("discovered");
    }

    @Test
    void infersNumericType_whenAllValuesParseAsNumbers() {
        for (int i = 0; i < 5; i++) {
            store.addNode(NodeInput.of("meeting-" + i, sgId)
                .withProperties(Map.of("duration", String.valueOf(30 + i * 5))), "t1");
        }
        phase.run("t1", List.of("meeting"));

        SchemaField duration = registry.schemaFor("meeting", "t1").get("duration");
        assertThat(duration).isNotNull();
        assertThat(duration.type()).isEqualTo("number");
    }

    @Test
    void infersEnumValues_whenFewDistinctValues() {
        String[] statuses = {"active", "completed", "cancelled", "active", "active"};
        for (int i = 0; i < 5; i++) {
            store.addNode(NodeInput.of("meeting-" + i, sgId)
                .withProperties(Map.of("status", statuses[i])), "t1");
        }
        phase.run("t1", List.of("meeting"));

        SchemaField status = registry.schemaFor("meeting", "t1").get("status");
        assertThat(status).isNotNull();
        assertThat(status.enumValues()).containsExactlyInAnyOrder("active", "completed", "cancelled");
    }

    @Test
    void writesProvenanceFields() {
        for (int i = 0; i < 5; i++) {
            store.addNode(NodeInput.of("meeting-" + i, sgId)
                .withProperties(Map.of("date", "2026-01-01")), "t1");
        }
        phase.run("t1", List.of("meeting"));

        MindMapNode typeNode = store.search(MindMapQuery.of("t1", 100)
            .withType(SubgraphTypes.TYPE_SYSTEM)).stream()
            .filter(n -> n.name().equals("meeting")).findFirst().orElseThrow();
        assertThat(typeNode.property("schema.date.source")).hasValue("discovered");
        assertThat(typeNode.property("schema.date.first-seen-epoch")).isPresent();
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SchemaDiscoveryPhaseTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — SchemaDiscoveryPhase class does not exist

- [ ] **Step 4: Implement SchemaDiscoveryPhase**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.intelligence.TypeRegistry;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.time.Instant;
import java.util.*;
import java.util.logging.Logger;

@ApplicationScoped
@Priority(25)
public class SchemaDiscoveryPhase implements ConsolidationPhase {

    private static final Logger LOG = Logger.getLogger(SchemaDiscoveryPhase.class.getName());
    private static final String SCHEMA_PREFIX = "schema.";
    private static final Set<String> SKIP_PROPERTIES = Set.of("cognitiveKind");
    private static final int MAX_ENUM_VALUES = 10;

    private final MindMapStore store;
    private final TypeRegistry registry;
    private final double threshold;
    private final int minSamples;
    private final double requiredThreshold;

    @Inject
    public SchemaDiscoveryPhase(MindMapStore store,
                                 Instance<TypeRegistry> registry,
                                 Instance<SchemaDiscoveryConfig> config) {
        this.store = store;
        this.registry = registry.isResolvable() ? registry.get() : null;
        SchemaDiscoveryConfig c = config.isResolvable() ? config.get() : null;
        this.threshold = c != null ? c.threshold() : 0.8;
        this.minSamples = c != null ? c.minSamples() : 5;
        this.requiredThreshold = c != null ? c.requiredThreshold() : 0.95;
    }

    SchemaDiscoveryPhase(MindMapStore store, TypeRegistry registry,
                          double threshold, int minSamples, double requiredThreshold) {
        this.store = store;
        this.registry = registry;
        this.threshold = threshold;
        this.minSamples = minSamples;
        this.requiredThreshold = requiredThreshold;
    }

    @Override
    public String name() {
        return "schema-discovery";
    }

    @Override
    public void run(String tenantId, List<String> subgraphPriority) {
        if (registry == null) return;
        for (String sgType : subgraphPriority) {
            discoverForSubgraphType(sgType, tenantId);
        }
    }

    private void discoverForSubgraphType(String sgType, String tenantId) {
        List<MindMapNode> nodes = store.search(
            MindMapQuery.of(tenantId, 10000).withType(sgType));
        if (nodes.size() < minSamples) return;

        Map<String, String> nodeTypes = new HashMap<>();
        for (MindMapNode node : nodes) {
            String type = node.property("cognitiveKind").orElse(sgType);
            nodeTypes.put(node.id(), type);
        }

        Map<String, List<MindMapNode>> byType = new HashMap<>();
        for (MindMapNode node : nodes) {
            byType.computeIfAbsent(nodeTypes.get(node.id()), k -> new ArrayList<>()).add(node);
        }

        for (var entry : byType.entrySet()) {
            String typeName = entry.getKey();
            List<MindMapNode> typeNodes = entry.getValue();
            if (typeNodes.size() < minSamples) continue;
            analyzeType(typeName, typeNodes, tenantId);
        }
    }

    private void analyzeType(String typeName, List<MindMapNode> nodes, String tenantId) {
        Map<String, SchemaField> existingSchema = registry.schemaFor(typeName, tenantId);
        int totalNodes = nodes.size();

        Map<String, List<String>> propertyValues = new HashMap<>();
        for (MindMapNode node : nodes) {
            for (var prop : node.properties().entrySet()) {
                if (prop.getKey().startsWith(SCHEMA_PREFIX)) continue;
                if (SKIP_PROPERTIES.contains(prop.getKey())) continue;
                propertyValues.computeIfAbsent(prop.getKey(), k -> new ArrayList<>())
                    .add(prop.getValue());
            }
        }

        MindMapNode typeNode = findTypeNode(typeName, tenantId);
        if (typeNode == null) return;

        Map<String, String> updates = new LinkedHashMap<>();
        String epochStr = String.valueOf(Instant.now().getEpochSecond());

        for (var prop : propertyValues.entrySet()) {
            String fieldName = prop.getKey();
            List<String> values = prop.getValue();
            double frequency = (double) values.size() / totalNodes;
            if (frequency < threshold) continue;

            if (isJavaSourced(typeNode, fieldName)) continue;

            if (existingSchema.containsKey(fieldName)) {
                String existingSource = typeNode.property(
                    SCHEMA_PREFIX + fieldName + ".source").orElse(null);
                if ("java".equals(existingSource)) continue;
            }

            String inferredType = inferType(values);
            boolean isCollection = inferCollection(values);
            List<String> enumVals = inferEnumValues(values);
            boolean required = frequency >= requiredThreshold;

            updates.put(SCHEMA_PREFIX + fieldName + ".type", inferredType);
            updates.put(SCHEMA_PREFIX + fieldName + ".required", String.valueOf(required));
            updates.put(SCHEMA_PREFIX + fieldName + ".source", "discovered");
            if (isCollection) {
                updates.put(SCHEMA_PREFIX + fieldName + ".collection", "true");
            }
            if (enumVals != null) {
                updates.put(SCHEMA_PREFIX + fieldName + ".enum", String.join(",", enumVals));
            }
            if (typeNode.property(SCHEMA_PREFIX + fieldName + ".first-seen-epoch").isEmpty()) {
                updates.put(SCHEMA_PREFIX + fieldName + ".first-seen-epoch", epochStr);
            }
        }

        if (!updates.isEmpty()) {
            store.updateNode(typeNode.id(), new NodeUpdate(
                null, null, null, null, null, null, null, null,
                null, null, null, updates, null), tenantId);
            LOG.info("Discovered " + updates.size() / 3 + " schema field(s) for type '"
                + typeName + "' in tenant '" + tenantId + "'");
        }
    }

    private boolean isJavaSourced(MindMapNode typeNode, String fieldName) {
        return typeNode.property(SCHEMA_PREFIX + fieldName + ".source")
            .map("java"::equals).orElse(false);
    }

    private MindMapNode findTypeNode(String typeName, String tenantId) {
        return store.search(MindMapQuery.of(tenantId, 100)
            .withType(SubgraphTypes.TYPE_SYSTEM)).stream()
            .filter(n -> n.name().equals(typeName))
            .findFirst().orElse(null);
    }

    static String inferType(List<String> values) {
        boolean allNumeric = values.stream().allMatch(v -> {
            try { Double.parseDouble(v); return true; }
            catch (NumberFormatException e) { return false; }
        });
        if (allNumeric) return "number";

        boolean allBoolean = values.stream().allMatch(v ->
            "true".equalsIgnoreCase(v) || "false".equalsIgnoreCase(v));
        if (allBoolean) return "boolean";

        return "string";
    }

    static boolean inferCollection(List<String> values) {
        long commaCount = values.stream()
            .filter(v -> v.contains(",") && v.split(",").length >= 2)
            .count();
        return (double) commaCount / values.size() >= 0.6;
    }

    static List<String> inferEnumValues(List<String> values) {
        Set<String> distinct = new LinkedHashSet<>(values);
        if (distinct.size() <= MAX_ENUM_VALUES && distinct.size() < values.size()) {
            return List.copyOf(distinct);
        }
        return null;
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SchemaDiscoveryPhaseTest`
Expected: PASS

- [ ] **Step 6: Run full consolidation test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: PASS — no regressions

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SchemaDiscoveryPhase.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SchemaDiscoveryConfig.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SchemaDiscoveryPhaseTest.java
git commit -m "feat(consolidation): SchemaDiscoveryPhase — property pattern analysis

@Priority(25) consolidation phase discovers type schemas from entity
property patterns. Configurable threshold (80%), min-samples (5),
required-threshold (95%). Provenance tracking: source=discovered,
first-seen-epoch. Java-sourced schema fields are immutable.

Refs #292"
```

## Batch 3: Adaptive Extraction

### Task 4: Schema-guided prompt injection in MindMapExtractor

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractorSchemaTest.java`

**Interfaces:**
- Consumes: `TypeRegistry.schemaFor(String, String)` from Task 2, `SchemaField` from Task 1
- Produces: Modified `buildUserPrompt()` that injects schema hints for context-relevant types

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class MindMapExtractorSchemaTest {

    private InMemoryMindMapStore store;
    private TypeRegistry registry;
    private MindMapExtractor extractor;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        registry = new TypeRegistry(store);
        extractor = new MindMapExtractor(store, null, registry);
    }

    @Test
    void buildSchemaHint_formatsSchemaAsProfileData() {
        Map<String, SchemaField> schema = Map.of(
            "date", new SchemaField("date", "string", true),
            "attendees", new SchemaField("attendees", "string", false, true, null, null)
        );
        String hint = MindMapExtractor.buildSchemaHint(
            Map.of("meeting", schema));
        assertThat(hint).contains("Known type schemas:");
        assertThat(hint).contains("meeting:");
        assertThat(hint).contains("date: string (required)");
        assertThat(hint).contains("attendees: string (collection)");
        assertThat(hint).contains("Extract all observed properties");
    }

    @Test
    void buildSchemaHint_emptySchemas_returnsEmpty() {
        String hint = MindMapExtractor.buildSchemaHint(Map.of());
        assertThat(hint).isEmpty();
    }

    @Test
    void buildSchemaHint_includesEnumValues() {
        Map<String, SchemaField> schema = Map.of(
            "status", new SchemaField("status", "string", false, false,
                null, List.of("active", "completed", "cancelled"))
        );
        String hint = MindMapExtractor.buildSchemaHint(
            Map.of("task", schema));
        assertThat(hint).contains("status: string [active, completed, cancelled]");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorSchemaTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — no 3-arg constructor, no buildSchemaHint method

- [ ] **Step 3: Add TypeRegistry dependency to MindMapExtractor**

Add a third constructor parameter `Instance<TypeRegistry>` to the `@Inject` constructor and a test constructor that accepts `TypeRegistry` directly:

```java
private final TypeRegistry typeRegistry;

@Inject
public MindMapExtractor(MindMapStore store,
                          Instance<AgentProvider> agentProviderInstance,
                          Instance<TypeRegistry> typeRegistryInstance) {
    this.store = store;
    this.agentProviderInstance = agentProviderInstance;
    this.typeRegistry = typeRegistryInstance.isResolvable() ? typeRegistryInstance.get() : null;
}

MindMapExtractor(MindMapStore store, Instance<AgentProvider> agentProviderInstance,
                  TypeRegistry typeRegistry) {
    this.store = store;
    this.agentProviderInstance = agentProviderInstance;
    this.typeRegistry = typeRegistry;
}
```

- [ ] **Step 4: Implement buildSchemaHint**

```java
static String buildSchemaHint(Map<String, Map<String, SchemaField>> schemas) {
    if (schemas.isEmpty()) return "";
    var sb = new StringBuilder();
    sb.append("Known type schemas:\n");
    for (var entry : schemas.entrySet()) {
        sb.append("  ").append(entry.getKey()).append(": {");
        var fields = new ArrayList<String>();
        for (var field : entry.getValue().values()) {
            var desc = new StringBuilder(field.name()).append(": ").append(field.type());
            var qualifiers = new ArrayList<String>();
            if (field.required()) qualifiers.add("required");
            if (field.collection()) qualifiers.add("collection");
            if (!qualifiers.isEmpty()) {
                desc.append(" (").append(String.join(", ", qualifiers)).append(")");
            }
            if (field.enumValues() != null && !field.enumValues().isEmpty()) {
                desc.append(" [").append(String.join(", ", field.enumValues())).append("]");
            }
            fields.add(desc.toString());
        }
        sb.append(String.join(", ", fields));
        sb.append("}\n");
    }
    sb.append("\nExtract all observed properties, including those not listed in known schemas.\n");
    return sb.toString();
}
```

- [ ] **Step 5: Inject schema hints into buildUserPrompt**

At the end of `buildUserPrompt()`, before `return sb.toString()`, add schema injection:

```java
if (typeRegistry != null) {
    Map<String, Map<String, SchemaField>> schemas = new LinkedHashMap<>();
    Set<String> contextTypes = new HashSet<>();
    for (var entry : context.entrySet()) {
        MindMapNode node = store.getNode(entry.getKey(), tenantId);
        if (node != null && node.subgraphType() != null) {
            String type = node.property("cognitiveKind").orElse(node.subgraphType());
            contextTypes.add(type);
        }
    }
    for (String type : contextTypes) {
        Map<String, SchemaField> schema = typeRegistry.schemaFor(type, tenantId);
        if (!schema.isEmpty()) {
            schemas.put(type, schema);
        }
    }
    String schemaHint = buildSchemaHint(schemas);
    if (!schemaHint.isEmpty()) {
        sb.append(schemaHint);
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorSchemaTest`
Expected: PASS

- [ ] **Step 7: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: PASS — no regressions in existing MindMapExtractor tests

- [ ] **Step 8: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractorSchemaTest.java
git commit -m "feat(extractor): schema-guided prompt injection for adaptive extraction

MindMapExtractor reads type schemas from TypeRegistry and injects
them as structured profile data into the extraction prompt. Selective
injection — only types found in the conversation's graph context.
Explicit 'extract all observed properties' instruction preserves
novel property discovery.

Refs #334"
```

## Batch 4: Dev-Time Trait Interface Generator

### Task 5: Implement TraitInterfaceGenerator CLI

**Files:**
- Create: `schema-generator/src/main/java/io/casehub/neocortex/schema/TraitInterfaceGenerator.java`
- Test: `schema-generator/src/test/java/io/casehub/neocortex/schema/TraitInterfaceGeneratorTest.java`

**Interfaces:**
- Consumes: `SchemaField` from Task 1
- Produces: `TraitInterfaceGenerator.generate(String typeName, Map<String, SchemaField> schema, String packageName)` → Java source string

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.neocortex.schema;

import io.casehub.neocortex.mindmap.SchemaField;
import org.junit.jupiter.api.Test;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class TraitInterfaceGeneratorTest {

    @Test
    void generate_simpleType_producesCorrectInterface() {
        Map<String, SchemaField> schema = new LinkedHashMap<>();
        schema.put("date", new SchemaField("date", "string", true));
        schema.put("agenda", new SchemaField("agenda", "string", false));

        String source = TraitInterfaceGenerator.generate(
            "meeting", schema, "io.casehub.neocortex.mindmap.intelligence");

        assertThat(source).contains("package io.casehub.neocortex.mindmap.intelligence;");
        assertThat(source).contains("import java.util.Optional;");
        assertThat(source).contains("public interface Meetinglike {");
        assertThat(source).contains("Optional<String> date();");
        assertThat(source).contains("Optional<String> agenda();");
    }

    @Test
    void generate_hyphenatedTypeName_convertsToPascalCase() {
        Map<String, SchemaField> schema = new LinkedHashMap<>();
        schema.put("title", new SchemaField("title", "string", false));

        String source = TraitInterfaceGenerator.generate(
            "research-report", schema, "io.casehub.example");

        assertThat(source).contains("public interface ResearchReportlike {");
    }

    @Test
    void generate_emptySchema_producesEmptyInterface() {
        String source = TraitInterfaceGenerator.generate(
            "empty", Map.of(), "io.casehub.example");

        assertThat(source).contains("public interface Emptylike {");
        assertThat(source).doesNotContain("Optional<String>");
    }

    @Test
    void toInterfaceName_convertsCorrectly() {
        assertThat(TraitInterfaceGenerator.toInterfaceName("meeting")).isEqualTo("Meetinglike");
        assertThat(TraitInterfaceGenerator.toInterfaceName("research-report")).isEqualTo("ResearchReportlike");
        assertThat(TraitInterfaceGenerator.toInterfaceName("org-unit")).isEqualTo("OrgUnitlike");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -Dtest=TraitInterfaceGeneratorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — class does not exist

- [ ] **Step 3: Implement TraitInterfaceGenerator**

```java
package io.casehub.neocortex.schema;

import io.casehub.neocortex.mindmap.SchemaField;
import java.util.Map;

public final class TraitInterfaceGenerator {

    private TraitInterfaceGenerator() {}

    public static String generate(String typeName, Map<String, SchemaField> schema,
                                   String packageName) {
        String interfaceName = toInterfaceName(typeName);
        var sb = new StringBuilder();
        sb.append("package ").append(packageName).append(";\n\n");
        if (!schema.isEmpty()) {
            sb.append("import java.util.Optional;\n\n");
        }
        sb.append("public interface ").append(interfaceName).append(" {\n");
        for (var field : schema.values()) {
            sb.append("    Optional<String> ").append(field.name()).append("();\n");
        }
        sb.append("}\n");
        return sb.toString();
    }

    static String toInterfaceName(String typeName) {
        String[] parts = typeName.split("-");
        var sb = new StringBuilder();
        for (String part : parts) {
            if (!part.isEmpty()) {
                sb.append(Character.toUpperCase(part.charAt(0)));
                if (part.length() > 1) sb.append(part.substring(1));
            }
        }
        sb.append("like");
        return sb.toString();
    }

    public static void main(String[] args) {
        if (args.length < 3) {
            System.err.println("Usage: TraitInterfaceGenerator --type <name> --tenant <id> --package <pkg>");
            System.exit(1);
        }
        String type = null, tenant = "default", pkg = null;
        for (int i = 0; i < args.length; i++) {
            switch (args[i]) {
                case "--type" -> type = args[++i];
                case "--tenant" -> tenant = args[++i];
                case "--package" -> pkg = args[++i];
            }
        }
        if (type == null || pkg == null) {
            System.err.println("--type and --package are required");
            System.exit(1);
        }
        System.err.println("Note: standalone mode generates from inline schema only.");
        System.err.println("For live store access, use within a Quarkus application.");
        System.out.println(generate(type, Map.of(), pkg));
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl schema-generator -Dtest=TraitInterfaceGeneratorTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add schema-generator/src/main/java/io/casehub/neocortex/schema/TraitInterfaceGenerator.java schema-generator/src/test/java/io/casehub/neocortex/schema/TraitInterfaceGeneratorTest.java
git commit -m "feat(schema-generator): TraitInterfaceGenerator CLI for type promotion

Generates Java trait interface source files from type schemas.
Naming convention: type-name → TypeNamelike (PascalCase + 'like').
All properties → Optional<String> — developer promotes types on review.

Refs #293"
```

## Batch 5: Full Build Verification + CLAUDE.md

### Task 6: Full build verification and CLAUDE.md update

**Files:**
- Modify: `CLAUDE.md` — update module descriptions

- [ ] **Step 1: Run full build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile and all tests pass

- [ ] **Step 2: Update CLAUDE.md**

Add to the `mindmap-intelligence` module description:
- `SchemaDiscoveryPhase (@Priority(25) — property pattern analysis → type node schema properties; configurable threshold/minSamples/requiredThreshold; provenance tracking source=discovered/java; Java-sourced fields immutable)`
- Update `MindMapExtractor` description to mention schema-guided prompt injection
- Update `TypeRegistry` description to mention provenance tracking (source=java/discovered) and extended SchemaField reading

Add to `schema-generator` module description:
- `TraitInterfaceGenerator (CLI: type schema → Java trait interface source file; naming convention TypeNamelike)`

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md with schema flywheel components

SchemaDiscoveryPhase, schema-guided extraction in MindMapExtractor,
TraitInterfaceGenerator in schema-generator. TypeRegistry provenance
tracking.

Refs #335"
```

## References

- [2026-09-14-cognitive-schema-flywheel-design.md] — design spec this plan implements
- [decisions.md D1-D8] — design decisions
- [TypeRegistry.java:91-162] — schemaFor, registerType methods
- [MindMapExtractor.java:39-198] — SYSTEM_PROMPT, buildUserPrompt
- [ConsolidationPhase.java] — phase SPI
- [MergeDetectionPhase.java] — @Priority(20) pattern reference
- [SchemaField.java] — current record
- [CognitiveSchemaGenerator.java] — schema-generator module pattern
- [GE-20260912-c4c279] — Thing trait projections
- [GE-20260914-e3cb03] — profile data over prose directives
- [GitHub #335] — epic issue
- [GitHub #292] — schema discovery
- [GitHub #293] — code generation
- [GitHub #334] — adaptive extraction
