# Knowledge Representation Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #285 — epic: Knowledge Representation Model — triples, cores, and dynamic type semantics
**Issue group:** #285, #278, #281, #282

**Goal:** Formalize MindMap's implicit Thing system with a `Thing` base interface, dynamic subgraph types, a type registry backed by MindMap nodes, and dynamic property schema.

**Architecture:** New `thing-api` module (zero deps) defines the `Thing` interface with `is()`/`as()` default methods. `MindMapNode` extends `Thing`, gaining `subgraphType()`. `SubgraphType` enum is replaced by dynamic strings. A `TypeRegistry` CDI bean in `mindmap-intelligence` mediates type operations over a TYPE_SYSTEM subgraph. Property schema for dynamic types is stored as properties on type nodes.

**Tech Stack:** Java 21, Quarkus 3.32, ArchUnit, Flyway, JDK Proxy (java.lang.reflect)

## Global Constraints

- Java source level 21, JVM 26
- thing-api must be zero deps (no mindmap, cognitive, platform, Quarkus, Jakarta)
- All type strings are lowercase-normalized (strip + toLowerCase)
- Trait names are PascalCase, case-sensitive
- ArchUnit enforced dependency constraints on thing-api
- Flyway migration V4 for mindmap-sqlite
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Test single module: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`

---

## Batch 1: thing-api Module — Foundation

### Task 1: Create thing-api module with Thing interface, ThingProxyHandler, and tests

**Files:**
- Create: `thing-api/pom.xml`
- Create: `thing-api/src/main/java/io/casehub/neocortex/thing/Thing.java`
- Create: `thing-api/src/main/java/io/casehub/neocortex/thing/ThingProxyHandler.java`
- Create: `thing-api/src/test/java/io/casehub/neocortex/thing/ThingTest.java`
- Create: `thing-api/src/test/java/io/casehub/neocortex/thing/DependencyConstraintTest.java`
- Modify: `pom.xml` (parent — add module + dependencyManagement)

**Interfaces:**
- Produces: `Thing` interface — `id()`, `name()`, `type()`, `property(String)`, `properties()`, `traits()`, `is(String)`, `as(Class<T>)`
- Produces: `ThingProxyHandler` — package-private, `createProxy(Thing, Class<T>)`

- [ ] **Step 1: Create pom.xml for thing-api**

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
    <artifactId>casehub-neocortex-thing-api</artifactId>
    <name>CaseHub Neocortex Thing API</name>
    <description>Semantic knowledge representation base — Thing interface with is()/as() trait support. Zero deps.</description>
    <!-- ArchUnit enforced: zero casehub, Quarkus, Jakarta, Spring dependencies -->
    <dependencies>
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
        <dependency>
            <groupId>com.tngtech.archunit</groupId>
            <artifactId>archunit-junit5</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

Write to `thing-api/pom.xml`.

- [ ] **Step 2: Add thing-api to parent pom.xml**

In the parent `pom.xml`, add `<module>thing-api</module>` before the `cognitive-api` module (line 25). In `<dependencyManagement>`, add:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-thing-api</artifactId>
    <version>${project.version}</version>
</dependency>
```

Use `ide_replace_text_in_file` or Edit tool.

- [ ] **Step 3: Write Thing interface**

```java
package io.casehub.neocortex.thing;

import java.util.Map;
import java.util.Optional;
import java.util.Set;

public interface Thing {

    String id();
    String name();
    String type();

    Optional<String> property(String key);
    Map<String, String> properties();

    Set<String> traits();

    default boolean is(String traitName) {
        return traits().contains(traitName);
    }

    default <T> T as(Class<T> traitInterface) {
        if (!traitInterface.isInterface()) {
            throw new IllegalArgumentException(
                "Trait must be an interface: " + traitInterface.getName());
        }
        return ThingProxyHandler.createProxy(this, traitInterface);
    }
}
```

Write to `thing-api/src/main/java/io/casehub/neocortex/thing/Thing.java`.

- [ ] **Step 4: Write ThingProxyHandler**

Port the coercion logic from `TraitInvocationHandler` in mindmap-intelligence with Boolean enhancement and primitive defaults:

```java
package io.casehub.neocortex.thing;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.Objects;
import java.util.Optional;

final class ThingProxyHandler implements InvocationHandler {

    private final Thing thing;
    private final Class<?> traitInterface;

    private ThingProxyHandler(Thing thing, Class<?> traitInterface) {
        this.thing = thing;
        this.traitInterface = traitInterface;
    }

    @SuppressWarnings("unchecked")
    static <T> T createProxy(Thing thing, Class<T> traitInterface) {
        return (T) Proxy.newProxyInstance(
            traitInterface.getClassLoader(),
            new Class<?>[] { traitInterface },
            new ThingProxyHandler(thing, traitInterface));
    }

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        return switch (method.getName()) {
            case "toString" -> traitInterface.getSimpleName() + "[" + thing.id() + "]";
            case "hashCode" -> Objects.hash(thing.id(), traitInterface);
            case "equals"   -> args[0] != null
                && Proxy.isProxyClass(args[0].getClass())
                && Proxy.getInvocationHandler(args[0]) instanceof ThingProxyHandler other
                && Objects.equals(thing.id(), other.thing.id())
                && Objects.equals(traitInterface, other.traitInterface);
            default -> {
                Class<?> returnType = method.getReturnType();
                Optional<String> value = thing.property(method.getName());
                if (returnType == Optional.class) {
                    yield value;
                } else if (value.isEmpty()) {
                    yield primitiveDefault(returnType);
                } else {
                    yield coerce(value.get(), returnType);
                }
            }
        };
    }

    private static Object coerce(String value, Class<?> returnType) {
        if (returnType == String.class) return value;
        if (returnType == Integer.class || returnType == int.class) return Integer.parseInt(value);
        if (returnType == Long.class || returnType == long.class) return Long.parseLong(value);
        if (returnType == Double.class || returnType == double.class) return Double.parseDouble(value);
        if (returnType == Boolean.class || returnType == boolean.class) return Boolean.parseBoolean(value);
        return value;
    }

    private static Object primitiveDefault(Class<?> returnType) {
        if (returnType == int.class) return 0;
        if (returnType == long.class) return 0L;
        if (returnType == double.class) return 0.0;
        if (returnType == boolean.class) return false;
        return null;
    }
}
```

Write to `thing-api/src/main/java/io/casehub/neocortex/thing/ThingProxyHandler.java`.

- [ ] **Step 5: Write ThingTest**

```java
package io.casehub.neocortex.thing;

import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ThingTest {

    interface Personable {
        Optional<String> birthday();
        Optional<String> role();
    }

    interface Measurable {
        int count();
        double score();
        boolean active();
        Long bigNumber();
    }

    private Thing thing(Map<String, String> properties, Set<String> traits) {
        return new Thing() {
            @Override public String id() { return "t1"; }
            @Override public String name() { return "Alice"; }
            @Override public String type() { return "person"; }
            @Override public Optional<String> property(String key) {
                return Optional.ofNullable(properties.get(key));
            }
            @Override public Map<String, String> properties() { return properties; }
            @Override public Set<String> traits() { return traits; }
        };
    }

    @Test
    void is_returnsTrueForPresentTrait() {
        Thing t = thing(Map.of(), Set.of("Personable"));
        assertThat(t.is("Personable")).isTrue();
    }

    @Test
    void is_returnsFalseForAbsentTrait() {
        Thing t = thing(Map.of(), Set.of("Personable"));
        assertThat(t.is("Projectlike")).isFalse();
    }

    @Test
    void is_isCaseSensitive() {
        Thing t = thing(Map.of(), Set.of("Personable"));
        assertThat(t.is("personable")).isFalse();
    }

    @Test
    void as_returnsProxyWithPropertyAccess() {
        Thing t = thing(Map.of("birthday", "1990-01-15", "role", "engineer"),
                        Set.of("Personable"));
        Personable p = t.as(Personable.class);
        assertThat(p.birthday()).contains("1990-01-15");
        assertThat(p.role()).contains("engineer");
    }

    @Test
    void as_returnsEmptyOptionalForMissingProperty() {
        Thing t = thing(Map.of(), Set.of());
        Personable p = t.as(Personable.class);
        assertThat(p.birthday()).isEmpty();
    }

    @Test
    void as_coercesPrimitiveTypes() {
        Thing t = thing(Map.of("count", "42", "score", "3.14", "active", "true"),
                        Set.of());
        Measurable m = t.as(Measurable.class);
        assertThat(m.count()).isEqualTo(42);
        assertThat(m.score()).isEqualTo(3.14);
        assertThat(m.active()).isTrue();
    }

    @Test
    void as_returnsDefaultsForMissingPrimitives() {
        Thing t = thing(Map.of(), Set.of());
        Measurable m = t.as(Measurable.class);
        assertThat(m.count()).isZero();
        assertThat(m.score()).isZero();
        assertThat(m.active()).isFalse();
    }

    @Test
    void as_returnsNullForMissingBoxedTypes() {
        Thing t = thing(Map.of(), Set.of());
        Measurable m = t.as(Measurable.class);
        assertThat(m.bigNumber()).isNull();
    }

    @Test
    void as_rejectsNonInterface() {
        Thing t = thing(Map.of(), Set.of());
        assertThatThrownBy(() -> t.as(String.class))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("Trait must be an interface");
    }

    @Test
    void as_toStringIncludesIdAndTraitName() {
        Thing t = thing(Map.of(), Set.of());
        Personable p = t.as(Personable.class);
        assertThat(p.toString()).isEqualTo("Personable[t1]");
    }

    @Test
    void as_equalsComparesIdAndTraitClass() {
        Thing t1 = thing(Map.of(), Set.of());
        Personable p1 = t1.as(Personable.class);
        Personable p2 = t1.as(Personable.class);
        assertThat(p1).isEqualTo(p2);
    }
}
```

Write to `thing-api/src/test/java/io/casehub/neocortex/thing/ThingTest.java`.

- [ ] **Step 6: Write DependencyConstraintTest**

```java
package io.casehub.neocortex.thing;

import com.tngtech.archunit.base.DescribedPredicate;
import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "io.casehub.neocortex.thing")
class DependencyConstraintTest {

    @ArchTest
    static final ArchRule noQuarkus = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.quarkus..", "jakarta..");

    @ArchTest
    static final ArchRule noSpring = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("org.springframework..");

    @ArchTest
    static final ArchRule noCasehubDomain = noClasses()
        .that().resideInAPackage("io.casehub.neocortex.thing..")
        .should().dependOnClassesThat(
            DescribedPredicate.describe("casehub classes outside thing-api",
                (JavaClass cls) -> cls.getPackageName().startsWith("io.casehub.")
                    && !cls.getPackageName().startsWith("io.casehub.neocortex.thing")));

    @ArchTest
    static final ArchRule noCognitive = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.casehub.neocortex.cognitive..");

    @ArchTest
    static final ArchRule noMindmap = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.casehub.neocortex.mindmap..");

    @ArchTest
    static final ArchRule noPlatform = noClasses().should()
        .dependOnClassesThat().resideInAnyPackage("io.casehub.platform..");
}
```

Write to `thing-api/src/test/java/io/casehub/neocortex/thing/DependencyConstraintTest.java`.

- [ ] **Step 7: Build and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl thing-api`
Expected: All tests pass. ArchUnit constraints hold.

- [ ] **Step 8: Commit**

```bash
git add thing-api/ pom.xml
git commit -m "feat(thing-api): Thing interface with is()/as() trait support Refs #278"
```

---

## Batch 2: SubgraphType → String + MindMapNode extends Thing

### Task 2: mindmap-api — SubgraphTypes, SubgraphInput normalization, MindMapNode extends Thing, subgraphType(), SchemaField

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SchemaField.java`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java` — extends Thing, add `subgraphType()`, default `type()`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapSubgraph.java` — `SubgraphType type` → `String type`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphInput.java` — `SubgraphType type` → `String type`, add normalization
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RuleCondition.java` — `InSubgraphType(SubgraphType)` → `InSubgraphType(String)`, real evaluate()
- Delete: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphType.java`
- Modify: `mindmap-api/pom.xml` — add thing-api dependency

**Interfaces:**
- Consumes: `Thing` from thing-api
- Produces: `SubgraphTypes` constants, `SchemaField` record, `MindMapNode.subgraphType()`, `MindMapNode.type()` default

- [ ] **Step 1: Add thing-api dependency to mindmap-api pom.xml**

In `mindmap-api/pom.xml`, add before the cognitive-api dependency:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-thing-api</artifactId>
</dependency>
```

- [ ] **Step 2: Create SubgraphTypes constants class**

```java
package io.casehub.neocortex.mindmap;

public final class SubgraphTypes {
    public static final String PERSON = "person";
    public static final String PROJECT = "project";
    public static final String RESEARCH_AREA = "research-area";
    public static final String ORGANISATION = "organisation";
    public static final String CONCEPT = "concept";
    public static final String GENERAL = "general";
    public static final String TYPE_SYSTEM = "type-system";

    private SubgraphTypes() {}
}
```

Write to `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java`.

- [ ] **Step 3: Create SchemaField record**

```java
package io.casehub.neocortex.mindmap;

public record SchemaField(String name, String type, boolean required) {}
```

Write to `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SchemaField.java`.

- [ ] **Step 4: Modify MindMapSubgraph — SubgraphType → String**

Change `MindMapSubgraph.java` record field from `SubgraphType type` to `String type`:

```java
public record MindMapSubgraph(
    String id,
    String name,
    String type,
    String rootNodeId,
    String tenantId,
    Instant createdAt
) {}
```

Use `ide_replace_member` to replace the record.

- [ ] **Step 5: Modify SubgraphInput — SubgraphType → String + normalization**

```java
package io.casehub.neocortex.mindmap;

import java.util.Objects;

public record SubgraphInput(String name, String type, String rootNodeId) {
    public SubgraphInput {
        Objects.requireNonNull(name, "name required");
        Objects.requireNonNull(type, "type required");
        type = type.strip().toLowerCase();
        if (type.isEmpty()) throw new IllegalArgumentException("type must not be blank");
    }
}
```

Use `ide_replace_member` on SubgraphInput.

- [ ] **Step 6: Modify RuleCondition.InSubgraphType — SubgraphType → String, real evaluate()**

Replace the InSubgraphType record inside RuleCondition.java:

```java
record InSubgraphType(String type) implements RuleCondition {
    @Override
    public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
        return type.equals(node.subgraphType());
    }
}
```

Use `ide_replace_member` on `InSubgraphType`.

- [ ] **Step 7: Modify MindMapNode — extends Thing, add subgraphType()**

Add `extends Thing` to MindMapNode and add `subgraphType()` method and `type()` default:

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.thing.Thing;
import io.casehub.platform.api.identity.PrincipalId;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

public interface MindMapNode extends Thing {

    // inherited from Thing: id(), name(), type(), property(), properties(), traits(), is(), as()

    String subgraphId();

    String subgraphType();

    @Override
    default String type() { return subgraphType(); }

    Confidence confidence();

    String provenance();

    Instant createdAt();

    Instant updatedAt();

    Instant validFrom();

    Instant validUntil();

    Set<String> traits();

    Set<NodeRef> refs();

    Double pleasure();

    Double arousal();

    Double dominance();

    Optional<String> property(String key);

    Map<String, String> properties();

    PrincipalId principalId();

    Set<String> sharedWith();
}
```

Use Edit tool to replace entire file content.

- [ ] **Step 8: Delete SubgraphType enum**

Use `ide_refactor_safe_delete` on `SubgraphType.java`. If it reports usages (expected — we haven't migrated callers yet), note them and delete the file manually. Remaining callers are fixed in Task 3 and Task 4.

Actually, safe delete will fail since callers still exist. Simply delete the file with bash (it's not a refactoring — the enum is being replaced, not renamed):

```bash
rm mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphType.java
```

- [ ] **Step 9: Verify mindmap-api compiles (expect failures in dependent modules)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl thing-api,mindmap-api`
Expected: mindmap-api compiles successfully. Downstream modules that reference SubgraphType will fail (fixed in Tasks 3-4).

- [ ] **Step 10: Commit**

```bash
git add mindmap-api/ thing-api/
git commit -m "refactor(mindmap-api): SubgraphType enum → String, MindMapNode extends Thing Refs #281"
```

### Task 3: Store implementations — InMemory + SQLite subgraphType resolution, Flyway V4

**Files:**
- Modify: `mindmap-inmem/src/main/java/io/casehub/neocortex/mindmap/inmem/InMemoryMindMapStore.java` — StoredNode gains subgraphType, createSubgraph uses String
- Modify: `mindmap-sqlite/src/main/java/io/casehub/neocortex/mindmap/sqlite/SqliteMindMapStore.java` — SqliteNode gains subgraphType, queries JOIN for type, use String
- Create: `mindmap-sqlite/src/main/resources/db/mindmap-sqlite/migration/V4__subgraph_type_lowercase.sql`
- Modify: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/NoOpMindMapStore.java` — remove SubgraphType import

**Interfaces:**
- Consumes: `SubgraphTypes` constants (from Task 2), `MindMapNode.subgraphType()` (from Task 2)
- Produces: Working store implementations that resolve `subgraphType()` on all returned nodes

- [ ] **Step 1: Modify InMemoryMindMapStore.StoredNode — add subgraphType field**

Add a `String subgraphType` field to StoredNode. The constructor takes it as a parameter. The `subgraphType()` method returns it. In `addNode()`, resolve the subgraph type from `subgraphs.get(input.subgraphId()).type()` when constructing StoredNode. In `createSubgraph()`, the `input.type()` is already a String (from Task 2).

Replace the StoredNode record:

```java
static class StoredNode implements MindMapNode {
    final String id;
    // ... existing fields ...
    final String subgraphType;
    // ... constructor adds subgraphType parameter ...
    @Override public String subgraphType() { return subgraphType; }
}
```

The key changes:
1. Add `final String subgraphType` field (after `tenantId`)
2. Constructor: add `String subgraphType` parameter, assign it
3. Add `@Override public String subgraphType() { return subgraphType; }` method
4. In `addNode()` (line 94): resolve `subgraphs.get(input.subgraphId()).type()` and pass to StoredNode constructor
5. In `createSubgraph()` (line 145): `input.type()` is already String — works as-is
6. Remove all `SubgraphType` imports

Use `ide_edit_member` or Edit tool for the StoredNode class and addNode method.

- [ ] **Step 2: Modify SqliteMindMapStore — JOIN for subgraphType**

Four groups of changes:

**a) SqliteNode record** — add `String subgraphType` field:
```java
private record SqliteNode(
    String id, String name, String subgraphId, String subgraphType,
    Confidence confidence, String provenance,
    // ... rest unchanged ...
) implements MindMapNode {
    @Override public String subgraphType() { return subgraphType; }
    // ... existing overrides ...
}
```

**b) toNode()** — read `subgraph_type` from joined result:
```java
private MindMapNode toNode(ResultSet rs) throws SQLException {
    // ... existing confidence parsing ...
    return new SqliteNode(
        rs.getString("node_id"),
        rs.getString("name"),
        rs.getString("subgraph_id"),
        rs.getString("subgraph_type"),  // from JOIN
        // ... rest unchanged ...
    );
}
```

**c) Node queries** — change `SELECT * FROM mindmap_node` to include JOIN:

For `getNode()` (line 278):
```sql
SELECT n.*, s.type AS subgraph_type FROM mindmap_node n JOIN mindmap_subgraph s ON n.subgraph_id = s.subgraph_id WHERE n.node_id = ? AND n.tenant_id = ?
```

Apply the same JOIN pattern to all node-returning queries:
- `getNode()` (line 278)
- `nodesIn()` equivalent
- `search()` equivalent
- `resolveNode()` equivalent
- Any query that calls `toNode(rs)`

**d) Subgraph methods** — replace `SubgraphType.valueOf(rs.getString("type"))` with `rs.getString("type")`:
- `getSubgraph()` (line 184)
- `listSubgraphs()` (line 221)
- `createSubgraph()` — the `input.type()` is already String

Remove the `SubgraphType` import.

- [ ] **Step 3: Create Flyway V4 migration**

```sql
-- Lowercase SubgraphType enum values and add unique constraint
UPDATE mindmap_subgraph SET type = LOWER(type);

CREATE UNIQUE INDEX IF NOT EXISTS mindmap_subgraph_tenant_type_idx
    ON mindmap_subgraph (tenant_id, type);
```

Write to `mindmap-sqlite/src/main/resources/db/mindmap-sqlite/migration/V4__subgraph_type_lowercase.sql`.

- [ ] **Step 4: Fix NoOpMindMapStore**

Remove the `SubgraphType` import from `NoOpMindMapStore.java`. The class returns null/empty for all methods, so no functional change needed. If `subgraphType()` needs implementing, it's inherited from MindMapNode with no default — add a stub:

The `NoOpMindMapStore` doesn't return nodes (getNode returns null), so `subgraphType()` on MindMapNode is an abstract method that the store's returned nodes must implement. Since NoOp returns null for getNode/search, no nodes are ever created — no change needed beyond removing the import.

- [ ] **Step 5: Build stores**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl mindmap-inmem,mindmap-sqlite,mindmap`
Expected: Compiles (may have test failures — those are fixed in Task 4).

- [ ] **Step 6: Commit**

```bash
git add mindmap-inmem/ mindmap-sqlite/ mindmap/
git commit -m "refactor: store implementations resolve subgraphType(), String types, Flyway V4 Refs #281"
```

### Task 4: Caller migration — tests, deserializers, MindMapExtractor

**Files:**
- Modify: `mindmap-testing/src/main/java/io/casehub/neocortex/mindmap/testing/MindMapStoreContractTest.java` — SubgraphType.X → SubgraphTypes.X
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/RuleConditionDeserializer.java` — SubgraphType.valueOf → string normalize
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java` — parseSubgraphType → normalizeType, subgraphCache type change
- Modify: All test files referencing SubgraphType (see list below)

Test files to migrate (mechanical SubgraphType.X → SubgraphTypes.X):
- `mindmap-intelligence/src/test/java/.../CuriositySignalGeneratorTest.java`
- `mindmap-intelligence/src/test/java/.../StandardTraitRulesTest.java`
- `mindmap-intelligence/src/test/java/.../TraitProxyTest.java`
- `mindmap-intelligence/src/test/java/.../RecurrenceGeneratorTest.java`
- `mindmap-intelligence/src/test/java/.../MindMapExtractorTest.java`
- `mindmap/src/test/java/.../DerivedEdgeDecoratorTest.java`
- `mindmap/src/test/java/.../ConfidenceDecayDecoratorTest.java`
- `mindmap/src/test/java/.../VocabularyNormalizationDecoratorTest.java`
- `mindmap/src/test/java/.../MindMapAnalyzerTest.java`
- `mindmap/src/test/java/.../NodeRefCleanupObserverTest.java`
- `mindmap/src/test/java/.../TraitApplicationDecoratorTest.java`
- `cognitive-index/src/test/java/.../PerspectivalResolverTest.java`

**Interfaces:**
- Consumes: `SubgraphTypes` constants (from Task 2)

- [ ] **Step 1: Migrate MindMapStoreContractTest**

Use `ide_refactor_rename` is not applicable here (it's an enum → class constant change). Use Edit tool to:
1. Replace `import io.casehub.neocortex.mindmap.SubgraphType;` with `import io.casehub.neocortex.mindmap.SubgraphTypes;`
2. Replace all `SubgraphType.GENERAL` → `SubgraphTypes.GENERAL`
3. Replace all `SubgraphType.PERSON` → `SubgraphTypes.PERSON`
4. Replace all `SubgraphType.PROJECT` → `SubgraphTypes.PROJECT`
5. Replace all `SubgraphType.ORGANISATION` → `SubgraphTypes.ORGANISATION`
6. Update assertion: `assertThat(sg.type()).isEqualTo(SubgraphType.PROJECT)` → `assertThat(sg.type()).isEqualTo(SubgraphTypes.PROJECT)`
7. Add contract test for `subgraphType()` resolution:

```java
@Test
void getNode_resolvesSubgraphType() {
    String sgId = store.createSubgraph(
        new SubgraphInput("People", SubgraphTypes.PERSON, null), TENANT);
    String nodeId = store.addNode(NodeInput.of("Alice", sgId), TENANT);
    MindMapNode node = store.getNode(nodeId, TENANT);
    assertThat(node.subgraphType()).isEqualTo(SubgraphTypes.PERSON);
    assertThat(node.type()).isEqualTo(SubgraphTypes.PERSON);
}

@Test
void getNode_supportsThingInterface() {
    String sgId = store.createSubgraph(
        new SubgraphInput("People", SubgraphTypes.PERSON, null), TENANT);
    String nodeId = store.addNode(
        NodeInput.of("Alice", sgId).withTraits(Set.of("Personable"))
            .withProperties(Map.of("role", "engineer")),
        TENANT);
    Thing thing = store.getNode(nodeId, TENANT);
    assertThat(thing.is("Personable")).isTrue();
    assertThat(thing.type()).isEqualTo("person");
}
```

- [ ] **Step 2: Migrate RuleConditionDeserializer**

Replace `SubgraphType.valueOf(node.get("inSubgraphType").asText())` at line 75 with:
```java
node.get("inSubgraphType").asText().strip().toLowerCase()
```

So the full line becomes:
```java
new RuleCondition.InSubgraphType(
    node.get("inSubgraphType").asText().strip().toLowerCase());
```

Remove `import io.casehub.neocortex.mindmap.SubgraphType;`.

- [ ] **Step 3: Migrate MindMapExtractor**

Three changes:

**a) subgraphCache type**: `Map<String, Map<SubgraphType, String>>` → `Map<String, Map<String, String>>`:
```java
private final Map<String, Map<String, String>> subgraphCache = new ConcurrentHashMap<>();
```

**b) Replace parseSubgraphType with normalizeType**:
```java
private String normalizeType(String type) {
    if (type == null || type.isBlank()) return SubgraphTypes.GENERAL;
    return type.strip().toLowerCase();
}
```

**c) Update findOrCreateSubgraph** — parameter type `SubgraphType` → `String`:
```java
private String findOrCreateSubgraph(String type, String tenantId) {
    Map<String, String> tenantCache = subgraphCache.computeIfAbsent(tenantId, t -> {
        Map<String, String> warm = new ConcurrentHashMap<>();
        for (MindMapSubgraph sg : store.listSubgraphs(t)) {
            warm.putIfAbsent(sg.type(), sg.id());
        }
        return warm;
    });
    return tenantCache.computeIfAbsent(type, t ->
        store.createSubgraph(new SubgraphInput(t, t, null), tenantId));
}
```

**d) Update applyExtraction caller** — line 197-198:
```java
String sgType = normalizeType(pe.type());
String sgId = findOrCreateSubgraph(sgType, tenantId);
```

**e) Update ExtractedEntity construction** — line 227:
```java
entities.add(new ExtractedEntity(nodeId, pe.name(), created,
    sgType,  // was sgType.name()
    pe.properties() != null ? pe.properties() : Map.of()));
```

Remove `import io.casehub.neocortex.mindmap.SubgraphType;`.

- [ ] **Step 4: Migrate all remaining test files**

Mechanical replacement across all test files listed above. For each file:
1. Replace `import io.casehub.neocortex.mindmap.SubgraphType;` → `import io.casehub.neocortex.mindmap.SubgraphTypes;`
2. Replace all `SubgraphType.GENERAL` → `SubgraphTypes.GENERAL`
3. Replace all `SubgraphType.PERSON` → `SubgraphTypes.PERSON`
4. Replace all `SubgraphType.PROJECT` → `SubgraphTypes.PROJECT`
5. Replace all `SubgraphType.ORGANISATION` → `SubgraphTypes.ORGANISATION`

Use Edit tool with `replace_all: true` for each constant per file.

- [ ] **Step 5: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: All modules compile and all tests pass.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "refactor: migrate all SubgraphType callers to SubgraphTypes string constants Refs #281 Closes #281"
```

---

## Batch 3: Type Registry + Schema + TraitProxy

### Task 5: TypeRegistry CDI bean with lazy bootstrap

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistry.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistryTest.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoader.java` — delegate type bootstrap to TypeRegistry

**Interfaces:**
- Consumes: `MindMapStore` (SPI), `SubgraphTypes.TYPE_SYSTEM` (from Task 2), `SchemaField` (from Task 2)
- Produces: `TypeRegistry` — `typeExists()`, `subtypesOf()`, `javaClass()`, `schemaFor()`, `registerType()`

- [ ] **Step 1: Write failing TypeRegistry tests**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.SchemaField;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class TypeRegistryTest {

    private InMemoryMindMapStore store;
    private TypeRegistry registry;
    private static final String TENANT = "t1";

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        registry = new TypeRegistry(store);
    }

    @Test
    void bootstrapsTypeSystemSubgraphOnFirstAccess() {
        assertThat(registry.typeExists(SubgraphTypes.PERSON, TENANT)).isTrue();
        assertThat(registry.typeExists(SubgraphTypes.PROJECT, TENANT)).isTrue();
        assertThat(registry.typeExists(SubgraphTypes.ORGANISATION, TENANT)).isTrue();
        assertThat(registry.typeExists(SubgraphTypes.GENERAL, TENANT)).isTrue();
    }

    @Test
    void bootstrapIsIdempotent() {
        registry.typeExists(SubgraphTypes.PERSON, TENANT);
        registry.typeExists(SubgraphTypes.PERSON, TENANT);
        long typeSystemCount = store.listSubgraphs(TENANT).stream()
            .filter(sg -> SubgraphTypes.TYPE_SYSTEM.equals(sg.type()))
            .count();
        assertThat(typeSystemCount).isEqualTo(1);
    }

    @Test
    void registerType_createsDynamicType() {
        registry.registerType("research-topic", TENANT);
        assertThat(registry.typeExists("research-topic", TENANT)).isTrue();
    }

    @Test
    void registerType_withParent() {
        registry.registerType("researcher", SubgraphTypes.PERSON, TENANT);
        assertThat(registry.typeExists("researcher", TENANT)).isTrue();
        assertThat(registry.subtypesOf(SubgraphTypes.PERSON, TENANT))
            .contains("researcher");
    }

    @Test
    void javaClass_returnsMappingForCoreTypes() {
        assertThat(registry.javaClass(SubgraphTypes.PERSON, TENANT))
            .contains(Personable.class);
    }

    @Test
    void javaClass_returnsEmptyForDynamicTypes() {
        registry.registerType("custom-type", TENANT);
        assertThat(registry.javaClass("custom-type", TENANT)).isEmpty();
    }

    @Test
    void schemaFor_derivesCoreTypeSchemaFromInterface() {
        Map<String, SchemaField> schema = registry.schemaFor(SubgraphTypes.PERSON, TENANT);
        assertThat(schema).containsKey("birthday");
        assertThat(schema.get("birthday").type()).isEqualTo("string");
        assertThat(schema.get("birthday").required()).isFalse();
    }

    @Test
    void schemaFor_returnsEmptyForUnregisteredType() {
        assertThat(registry.schemaFor("nonexistent", TENANT)).isEmpty();
    }
}
```

Write to `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistryTest.java`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=TypeRegistryTest`
Expected: Compilation error — TypeRegistry doesn't exist yet.

- [ ] **Step 3: Implement TypeRegistry**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.EdgeInput;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.MindMapSubgraph;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.SchemaField;
import io.casehub.neocortex.mindmap.SubgraphInput;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

@ApplicationScoped
public class TypeRegistry {

    private static final Logger LOG = Logger.getLogger(TypeRegistry.class.getName());
    private static final String SUBTYPE_OF = "subtype-of";
    private static final String JAVA_CLASS = "java-class";
    private static final String SCHEMA_PREFIX = "schema.";

    private static final Map<String, Class<?>> CORE_TYPES = Map.of(
        SubgraphTypes.PERSON, Personable.class,
        SubgraphTypes.PROJECT, Projectlike.class,
        SubgraphTypes.ORGANISATION, Organisational.class
    );

    private final MindMapStore store;
    private final Map<String, BootstrappedTenant> tenantCache = new ConcurrentHashMap<>();

    @Inject
    TypeRegistry(Instance<MindMapStore> store) {
        this.store = store.isResolvable() ? store.get() : null;
    }

    TypeRegistry(MindMapStore store) {
        this.store = store;
    }

    public boolean typeExists(String typeName, String tenantId) {
        return ensureBootstrapped(tenantId).resolveTypeNode(typeName) != null;
    }

    public List<String> subtypesOf(String typeName, String tenantId) {
        BootstrappedTenant bt = ensureBootstrapped(tenantId);
        MindMapNode typeNode = bt.resolveTypeNode(typeName);
        if (typeNode == null) return List.of();
        List<String> subtypes = new ArrayList<>();
        store.neighbors(typeNode.id(), SUBTYPE_OF, tenantId).stream()
            .filter(e -> e.targetNodeId().equals(typeNode.id()))
            .forEach(e -> {
                MindMapNode child = store.getNode(e.sourceNodeId(), tenantId);
                if (child != null) subtypes.add(child.name());
            });
        return subtypes;
    }

    public Optional<Class<?>> javaClass(String typeName, String tenantId) {
        MindMapNode typeNode = ensureBootstrapped(tenantId).resolveTypeNode(typeName);
        if (typeNode == null) return Optional.empty();
        return typeNode.property(JAVA_CLASS).map(className -> {
            try {
                return Class.forName(className);
            } catch (ClassNotFoundException e) {
                LOG.warning("java-class not found: " + className);
                return null;
            }
        });
    }

    public Map<String, SchemaField> schemaFor(String typeName, String tenantId) {
        MindMapNode typeNode = ensureBootstrapped(tenantId).resolveTypeNode(typeName);
        if (typeNode == null) return Map.of();

        Map<String, SchemaField> schema = new LinkedHashMap<>();
        typeNode.properties().forEach((key, value) -> {
            if (key.startsWith(SCHEMA_PREFIX) && key.endsWith(".type")) {
                String fieldName = key.substring(SCHEMA_PREFIX.length(),
                    key.length() - ".type".length());
                boolean required = Boolean.parseBoolean(
                    typeNode.property(SCHEMA_PREFIX + fieldName + ".required").orElse("false"));
                schema.put(fieldName, new SchemaField(fieldName, value, required));
            }
        });

        if (schema.isEmpty()) {
            return javaClass(typeName, tenantId)
                .map(TypeRegistry::deriveSchemaFromInterface)
                .orElse(Map.of());
        }
        return schema;
    }

    public void registerType(String typeName, String tenantId) {
        registerType(typeName, null, tenantId);
    }

    public void registerType(String typeName, String parentType, String tenantId) {
        BootstrappedTenant bt = ensureBootstrapped(tenantId);
        String normalized = typeName.strip().toLowerCase();
        if (bt.resolveTypeNode(normalized) != null) return;

        String nodeId = store.addNode(
            NodeInput.of(normalized, bt.typeSystemSubgraphId), tenantId);
        bt.typeNodeIds.put(normalized, nodeId);

        if (parentType != null) {
            MindMapNode parentNode = bt.resolveTypeNode(parentType.strip().toLowerCase());
            if (parentNode != null) {
                store.addEdge(new EdgeInput(nodeId, parentNode.id(), SUBTYPE_OF,
                    null, "type-registry", null, null, null, null, null, Map.of()), tenantId);
            }
        }
    }

    private BootstrappedTenant ensureBootstrapped(String tenantId) {
        if (store == null) return BootstrappedTenant.EMPTY;
        return tenantCache.computeIfAbsent(tenantId, this::bootstrap);
    }

    private BootstrappedTenant bootstrap(String tenantId) {
        String sgId = findTypeSystemSubgraph(tenantId);
        if (sgId == null) {
            sgId = createTypeSystemSubgraph(tenantId);
        }

        BootstrappedTenant bt = new BootstrappedTenant(sgId, store, tenantId);
        for (MindMapNode node : store.nodesIn(sgId, tenantId)) {
            bt.typeNodeIds.put(node.name(), node.id());
        }

        createCoreTypesIfAbsent(bt, tenantId);
        return bt;
    }

    private String findTypeSystemSubgraph(String tenantId) {
        for (MindMapSubgraph sg : store.listSubgraphs(tenantId)) {
            if (SubgraphTypes.TYPE_SYSTEM.equals(sg.type())) {
                return sg.id();
            }
        }
        return null;
    }

    private String createTypeSystemSubgraph(String tenantId) {
        try {
            return store.createSubgraph(
                new SubgraphInput("Type System", SubgraphTypes.TYPE_SYSTEM, null), tenantId);
        } catch (IllegalStateException e) {
            String existing = findTypeSystemSubgraph(tenantId);
            if (existing != null) return existing;
            throw e;
        }
    }

    private void createCoreTypesIfAbsent(BootstrappedTenant bt, String tenantId) {
        for (String coreType : List.of(
                SubgraphTypes.PERSON, SubgraphTypes.PROJECT,
                SubgraphTypes.ORGANISATION, SubgraphTypes.CONCEPT,
                SubgraphTypes.RESEARCH_AREA, SubgraphTypes.GENERAL)) {
            if (!bt.typeNodeIds.containsKey(coreType)) {
                Map<String, String> props = new HashMap<>();
                Class<?> javaClass = CORE_TYPES.get(coreType);
                if (javaClass != null) {
                    props.put(JAVA_CLASS, javaClass.getName());
                    deriveSchemaFromInterface(javaClass).forEach((fieldName, sf) -> {
                        props.put(SCHEMA_PREFIX + fieldName + ".type", sf.type());
                    });
                }
                String nodeId = store.addNode(
                    NodeInput.of(coreType, bt.typeSystemSubgraphId)
                        .withProperties(props),
                    tenantId);
                bt.typeNodeIds.put(coreType, nodeId);

                if (!coreType.equals(SubgraphTypes.GENERAL)) {
                    MindMapNode generalNode = bt.resolveTypeNode(SubgraphTypes.GENERAL);
                    if (generalNode != null) {
                        store.addEdge(new EdgeInput(nodeId, generalNode.id(), SUBTYPE_OF,
                            null, "type-registry", null, null, null, null, null, Map.of()), tenantId);
                    }
                }
            }
        }
    }

    static Map<String, SchemaField> deriveSchemaFromInterface(Class<?> traitInterface) {
        Map<String, SchemaField> schema = new LinkedHashMap<>();
        for (Method method : traitInterface.getDeclaredMethods()) {
            if (method.isDefault()) continue;
            if (method.getDeclaringClass() == Object.class) continue;
            String schemaType = mapReturnType(method.getReturnType(), method.getGenericReturnType());
            schema.put(method.getName(), new SchemaField(method.getName(), schemaType, false));
        }
        return schema;
    }

    private static String mapReturnType(Class<?> returnType, java.lang.reflect.Type genericType) {
        if (returnType == String.class) return "string";
        if (returnType == Optional.class) return "string";
        if (returnType == int.class || returnType == Integer.class) return "number";
        if (returnType == long.class || returnType == Long.class) return "number";
        if (returnType == double.class || returnType == Double.class) return "number";
        if (returnType == boolean.class || returnType == Boolean.class) return "boolean";
        return "string";
    }

    private static class BootstrappedTenant {
        static final BootstrappedTenant EMPTY = new BootstrappedTenant("", null, null);
        final String typeSystemSubgraphId;
        final MindMapStore store;
        final String tenantId;
        final Map<String, String> typeNodeIds = new ConcurrentHashMap<>();

        BootstrappedTenant(String sgId, MindMapStore store, String tenantId) {
            this.typeSystemSubgraphId = sgId;
            this.store = store;
            this.tenantId = tenantId;
        }

        MindMapNode resolveTypeNode(String typeName) {
            if (store == null) return null;
            String nodeId = typeNodeIds.get(typeName);
            if (nodeId == null) return null;
            return store.getNode(nodeId, tenantId);
        }
    }
}
```

Write to `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistry.java`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=TypeRegistryTest`
Expected: All TypeRegistry tests pass.

- [ ] **Step 5: Update CognitiveLoader to delegate type bootstrap**

Add `Instance<TypeRegistry>` injection. In `init()`, call `registry.typeExists(SubgraphTypes.GENERAL, tenantId)` for each discovered tenant to trigger lazy bootstrap. Use `Instance<CaseMemoryStore>` for `discoverTenants()` if available, otherwise skip.

This is a minor wiring change — TypeRegistry handles its own bootstrap lazily, so CognitiveLoader just needs to trigger it for known tenants at startup for warm caching.

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/
git commit -m "feat(mindmap-intelligence): TypeRegistry CDI bean with lazy bootstrap Refs #278"
```

### Task 6: TraitProxy deprecation + thing-api dependency in mindmap-intelligence

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitProxy.java` — @Deprecated, delegate to Thing.as()
- Modify: `mindmap-intelligence/pom.xml` — add thing-api dependency

**Interfaces:**
- Consumes: `Thing.as()` (inherited by MindMapNode from thing-api)

- [ ] **Step 1: Add thing-api dependency to mindmap-intelligence pom.xml**

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-thing-api</artifactId>
</dependency>
```

- [ ] **Step 2: Deprecate TraitProxy.as()**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapNode;

public final class TraitProxy {

    private TraitProxy() {}

    @Deprecated(forRemoval = true)
    @SuppressWarnings("unchecked")
    public static <T> T as(MindMapNode node, Class<T> traitInterface) {
        return node.as(traitInterface);
    }
}
```

Use Edit tool to replace the file content.

- [ ] **Step 3: Verify existing TraitProxy tests still pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=TraitProxyTest`
Expected: All pass — TraitProxy now delegates to Thing.as() which uses ThingProxyHandler (same logic, ported from TraitInvocationHandler).

- [ ] **Step 4: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: All modules compile, all tests pass.

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/
git commit -m "feat: TraitProxy deprecated, delegates to Thing.as() Refs #278 Closes #278 Closes #282"
```

---

## References

- [specs/issue-285-knowledge-repr-model/2026-09-09-knowledge-repr-model-design.md] — design spec this plan implements
- [specs/issue-285-knowledge-repr-model/decisions.md] — design decisions D1-D14
- [mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java] — interface extending Thing
- [mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphType.java] — enum being deleted
- [mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitInvocationHandler.java] — proxy logic ported to thing-api
- [mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java:260-280] — parseSubgraphType/findOrCreateSubgraph migration
- [mindmap-sqlite/src/main/java/io/casehub/neocortex/mindmap/sqlite/SqliteMindMapStore.java:1106-1120] — SqliteNode record gains subgraphType
- [mindmap-inmem/src/main/java/io/casehub/neocortex/mindmap/inmem/InMemoryMindMapStore.java:570-689] — StoredNode class gains subgraphType
- [cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/RuleConditionDeserializer.java:75] — SubgraphType.valueOf migration
- [corpus-api/src/test/java/io/casehub/neocortex/corpus/DependencyConstraintTest.java] — ArchUnit pattern reference
- [cognitive-api/pom.xml] — zero-dep module pom pattern
- GitHub #285, #278, #281, #282
