# Cognitive Node Type Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #322 — Cognitive node type classification
**Issue group:** #322, #333

**Goal:** Register six cognitive node types (belief, intention, prediction, judgment, fear, desire) as compositional traits in the MindMap type system, with TypeRegistry hierarchy metadata, declarative YAML trait rules, and MindMapExtractor LLM classification.

**Architecture:** Cognitive types are compositional traits (additive), not exclusive subgraph types. All cognitive nodes live in a single COGNITIVE subgraph. A `cognitiveKind` property drives primary trait assignment via declarative YAML rules. Multiple cognitive traits can fire on a single node. TypeRegistry registers a COGNITIVE parent type with 6 children for hierarchy queries and schema derivation.

**Tech Stack:** Java 21, Quarkus CDI, InMemoryMindMapStore (tests), DeclarativeRuleRegistry (YAML trait rules), TypeRegistry, MindMapExtractor (LLM extraction)

## Global Constraints

- Java 21 source level, Java 26 JVM
- All `Optional<String>` returns on trait interfaces (property store is `Map<String, String>`)
- Trait interface naming: `-like` suffix for noun types (Belieflike, Fearlike), adjectival for verb types (Predictive, Evaluative)
- Declarative YAML rules in `cognitive-index/src/main/resources/rules/`
- No database migrations, no new modules, no SPI changes
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

---

## Batch 1: Foundation — SubgraphTypes + Trait Interfaces + Declarative Rules

### Task 1: COGNITIVE subgraph constant and 6 trait interfaces

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java:10`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Belieflike.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Intentionlike.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Predictive.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Evaluative.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Fearlike.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Desirelike.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CognitiveTraitInterfaceTest.java`

**Interfaces:**
- Produces: `SubgraphTypes.COGNITIVE` constant (used by Tasks 3, 4); `Belieflike`, `Intentionlike`, `Predictive`, `Evaluative`, `Fearlike`, `Desirelike` interfaces (used by Tasks 2, 3)

- [ ] **Step 1: Write tests for trait interface proxy access**

Create `CognitiveTraitInterfaceTest.java` with tests verifying `Thing.as(Belieflike.class)` returns correct property values, and that missing properties return empty Optionals:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.thing.Thing;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class CognitiveTraitInterfaceTest {

    private Thing thing(Map<String, String> properties) {
        return new Thing() {
            @Override public String id() { return "n1"; }
            @Override public String name() { return "Test"; }
            @Override public String type() { return "cognitive"; }
            @Override public Optional<String> property(String key) {
                return Optional.ofNullable(properties.get(key));
            }
            @Override public Map<String, String> properties() { return properties; }
            @Override public Set<String> traits() { return Set.of(); }
        };
    }

    @Test
    void belieflike_returnsProperties() {
        var t = thing(Map.of("subject", "project success", "status", "active", "basis", "test results"));
        var b = t.as(Belieflike.class);
        assertThat(b.subject()).contains("project success");
        assertThat(b.status()).contains("active");
        assertThat(b.basis()).contains("test results");
    }

    @Test
    void belieflike_emptyWhenMissing() {
        var b = thing(Map.of()).as(Belieflike.class);
        assertThat(b.subject()).isEmpty();
        assertThat(b.status()).isEmpty();
        assertThat(b.basis()).isEmpty();
    }

    @Test
    void intentionlike_returnsProperties() {
        var t = thing(Map.of("goal", "ship feature", "status", "active", "priority", "high"));
        var i = t.as(Intentionlike.class);
        assertThat(i.goal()).contains("ship feature");
        assertThat(i.status()).contains("active");
        assertThat(i.priority()).contains("high");
    }

    @Test
    void predictive_returnsProperties() {
        var t = thing(Map.of("timeframe", "Q4 2026", "status", "pending", "basis", "market trends"));
        var p = t.as(Predictive.class);
        assertThat(p.timeframe()).contains("Q4 2026");
        assertThat(p.status()).contains("pending");
        assertThat(p.basis()).contains("market trends");
    }

    @Test
    void evaluative_returnsProperties() {
        var t = thing(Map.of("target", "Alice", "stance", "positive", "basis", "track record"));
        var e = t.as(Evaluative.class);
        assertThat(e.target()).contains("Alice");
        assertThat(e.stance()).contains("positive");
        assertThat(e.basis()).contains("track record");
    }

    @Test
    void fearlike_returnsProperties() {
        var t = thing(Map.of("threat", "server crash", "severity", "high", "status", "active"));
        var f = t.as(Fearlike.class);
        assertThat(f.threat()).contains("server crash");
        assertThat(f.severity()).contains("high");
        assertThat(f.status()).contains("active");
    }

    @Test
    void desirelike_returnsProperties() {
        var t = thing(Map.of("aspiration", "promotion", "status", "active", "urgency", "medium"));
        var d = t.as(Desirelike.class);
        assertThat(d.aspiration()).contains("promotion");
        assertThat(d.status()).contains("active");
        assertThat(d.urgency()).contains("medium");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveTraitInterfaceTest -DfailIfNoTests=false`
Expected: compilation failure — Belieflike etc. don't exist yet

- [ ] **Step 3: Add COGNITIVE constant to SubgraphTypes**

In `SubgraphTypes.java`, add after the TYPE_SYSTEM line:

```java
public static final String COGNITIVE = "cognitive";
```

- [ ] **Step 4: Create the 6 trait interfaces**

Each follows the same pattern. All in `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/`:

**Belieflike.java:**
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Belieflike {
    Optional<String> subject();
    Optional<String> status();
    Optional<String> basis();
}
```

**Intentionlike.java:**
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Intentionlike {
    Optional<String> goal();
    Optional<String> status();
    Optional<String> priority();
}
```

**Predictive.java:**
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Predictive {
    Optional<String> timeframe();
    Optional<String> status();
    Optional<String> basis();
}
```

**Evaluative.java:**
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Evaluative {
    Optional<String> target();
    Optional<String> stance();
    Optional<String> basis();
}
```

**Fearlike.java:**
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Fearlike {
    Optional<String> threat();
    Optional<String> severity();
    Optional<String> status();
}
```

**Desirelike.java:**
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Desirelike {
    Optional<String> aspiration();
    Optional<String> status();
    Optional<String> urgency();
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveTraitInterfaceTest`
Expected: all 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Belieflike.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Intentionlike.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Predictive.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Evaluative.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Fearlike.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Desirelike.java \
  mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CognitiveTraitInterfaceTest.java
git commit -m "feat(mindmap): add COGNITIVE subgraph type + 6 cognitive trait interfaces

Belieflike, Intentionlike, Predictive, Evaluative, Fearlike, Desirelike —
compositional trait interfaces for cognitive node classification.

Refs #322"
```

### Task 2: Declarative YAML trait rules + compositionality tests

**Files:**
- Create: `cognitive-index/src/main/resources/rules/cognitive-traits.yaml`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveTraitRulesTest.java`

**Interfaces:**
- Consumes: `Belieflike`, `Intentionlike`, `Predictive`, `Evaluative`, `Fearlike`, `Desirelike` from Task 1; `DeclarativeRuleRegistry`, `RuleCondition`, `DeclarativeTraitRule` from mindmap-api
- Produces: `cognitive-traits.yaml` (loaded at runtime by DeclarativeRuleRegistry from classpath `rules/`)

- [ ] **Step 1: Write tests for declarative cognitive trait rules**

Create `CognitiveTraitRulesTest.java` that loads the YAML rules and verifies they match correctly. Use `DeclarativeRuleRegistry.loadFromClasspath()` (the test-visible package method) to load rules:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.SubgraphInput;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.TraitRule;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.IOException;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class CognitiveTraitRulesTest {

    private InMemoryMindMapStore store;
    private String subgraphId;
    private List<TraitRule> rules;

    @BeforeEach
    void setUp() throws IOException {
        store = new InMemoryMindMapStore();
        subgraphId = store.createSubgraph(
            new SubgraphInput("Cognitive", SubgraphTypes.COGNITIVE, null), "t1");
        var registry = DeclarativeRuleRegistry.loadFromClasspath(
            "rules/", null, Thread.currentThread().getContextClassLoader());
        rules = registry.allTraitRules();
    }

    private MindMapNode nodeWith(String name, Map<String, String> props) {
        String id = store.addNode(new NodeInput(name, subgraphId,
            null, "test", null, null,
            null, null, null, null, null, props), "t1");
        return store.getNode(id, "t1");
    }

    private boolean matches(String traitName, MindMapNode node) {
        return rules.stream()
            .filter(r -> r.traitName().equals(traitName))
            .anyMatch(r -> r.matches(node, List.of()));
    }

    @Test
    void belieflike_matchesCognitiveKindBelief() {
        var node = nodeWith("Project is on track", Map.of("cognitiveKind", "belief"));
        assertThat(matches("Belieflike", node)).isTrue();
    }

    @Test
    void intentionlike_matchesCognitiveKindIntention() {
        var node = nodeWith("Ship by Friday", Map.of("cognitiveKind", "intention"));
        assertThat(matches("Intentionlike", node)).isTrue();
    }

    @Test
    void predictive_matchesCognitiveKindPrediction() {
        var node = nodeWith("Market will crash", Map.of("cognitiveKind", "prediction"));
        assertThat(matches("Predictive", node)).isTrue();
    }

    @Test
    void evaluative_matchesCognitiveKindJudgment() {
        var node = nodeWith("Alice is trustworthy", Map.of("cognitiveKind", "judgment"));
        assertThat(matches("Evaluative", node)).isTrue();
    }

    @Test
    void fearlike_matchesCognitiveKindFear() {
        var node = nodeWith("Server will crash", Map.of("cognitiveKind", "fear"));
        assertThat(matches("Fearlike", node)).isTrue();
    }

    @Test
    void desirelike_matchesCognitiveKindDesire() {
        var node = nodeWith("Get promoted", Map.of("cognitiveKind", "desire"));
        assertThat(matches("Desirelike", node)).isTrue();
    }

    @Test
    void noMatch_withoutCognitiveKind() {
        var node = nodeWith("Abstract concept", Map.of());
        assertThat(matches("Belieflike", node)).isFalse();
        assertThat(matches("Intentionlike", node)).isFalse();
        assertThat(matches("Predictive", node)).isFalse();
        assertThat(matches("Evaluative", node)).isFalse();
        assertThat(matches("Fearlike", node)).isFalse();
        assertThat(matches("Desirelike", node)).isFalse();
    }

    @Test
    void compositionality_beliefWithTimeframeAlsoPredictive() {
        var node = nodeWith("Economy will recover",
            Map.of("cognitiveKind", "belief", "timeframe", "Q4 2026"));
        assertThat(matches("Belieflike", node)).isTrue();
        assertThat(matches("Predictive", node)).isTrue();
    }

    @Test
    void compositionality_beliefWithTargetAndStanceAlsoEvaluative() {
        var node = nodeWith("Alice is reliable",
            Map.of("cognitiveKind", "belief", "target", "Alice", "stance", "positive"));
        assertThat(matches("Belieflike", node)).isTrue();
        assertThat(matches("Evaluative", node)).isTrue();
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveTraitRulesTest -DfailIfNoTests=false`
Expected: failure — `rules/cognitive-traits.yaml` doesn't exist, no rules loaded

- [ ] **Step 3: Create cognitive-traits.yaml**

Create `cognitive-index/src/main/resources/rules/cognitive-traits.yaml`:

```yaml
traitRules:
  - trait: Belieflike
    when:
      propertyEquals:
        cognitiveKind: belief

  - trait: Intentionlike
    when:
      propertyEquals:
        cognitiveKind: intention

  - trait: Predictive
    when:
      propertyEquals:
        cognitiveKind: prediction

  - trait: Evaluative
    when:
      propertyEquals:
        cognitiveKind: judgment

  - trait: Fearlike
    when:
      propertyEquals:
        cognitiveKind: fear

  - trait: Desirelike
    when:
      propertyEquals:
        cognitiveKind: desire

  - trait: Predictive
    when:
      allOf:
        - hasProperty: timeframe
        - hasProperty: cognitiveKind

  - trait: Evaluative
    when:
      allOf:
        - hasProperty: target
        - hasProperty: stance
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveTraitRulesTest`
Expected: all 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cognitive-index/src/main/resources/rules/cognitive-traits.yaml \
  cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveTraitRulesTest.java
git commit -m "feat(cognitive-index): declarative YAML rules for cognitive trait classification

Primary rules: cognitiveKind property → trait assignment.
Secondary rules: property-pattern inference for compositionality
(timeframe → Predictive, target+stance → Evaluative).

Refs #322"
```

## Batch 2: Type Hierarchy — TypeRegistry + CognitiveLoader

### Task 3: Register COGNITIVE parent type and children in CognitiveLoader

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistry.java:33-37` (add COGNITIVE_TYPES map)
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoader.java:31-69` (add type registration)
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoaderTest.java` (add type registration tests)
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistryTest.java` (add cognitive hierarchy tests)

**Interfaces:**
- Consumes: `SubgraphTypes.COGNITIVE` from Task 1; `Belieflike`, `Intentionlike`, `Predictive`, `Evaluative`, `Fearlike`, `Desirelike` from Task 1; `TypeRegistry.registerType(String, String, String)`, `TypeRegistry.subtypesOf(String, String)`, `TypeRegistry.javaClass(String, String)`, `TypeRegistry.schemaFor(String, String)`
- Produces: COGNITIVE type hierarchy in TypeRegistry (used by downstream consumers for `subtypesOf("cognitive")` queries and schema derivation)

- [ ] **Step 1: Write tests for cognitive type hierarchy**

Add tests to `CognitiveLoaderTest.java`:

```java
@Test
void registersAllCognitiveTypes() {
    var store = new InMemoryMindMapStore();
    var registry = new TypeRegistry(store);
    var loader = new CognitiveLoader(store, List.of());
    loader.init();
    // CognitiveLoader should register types after init

    // Verify directly via TypeRegistry
    String tenantId = "t1";
    assertThat(registry.typeExists("cognitive", tenantId)).isTrue();
    assertThat(registry.typeExists("belief", tenantId)).isTrue();
    assertThat(registry.typeExists("intention", tenantId)).isTrue();
    assertThat(registry.typeExists("prediction", tenantId)).isTrue();
    assertThat(registry.typeExists("judgment", tenantId)).isTrue();
    assertThat(registry.typeExists("fear", tenantId)).isTrue();
    assertThat(registry.typeExists("desire", tenantId)).isTrue();
}

@Test
void cognitiveTypesAreSubtypesOfCognitive() {
    var store = new InMemoryMindMapStore();
    var registry = new TypeRegistry(store);
    var loader = new CognitiveLoader(store, List.of());
    loader.init();

    var subtypes = registry.subtypesOf("cognitive", "t1");
    assertThat(subtypes).containsExactlyInAnyOrder(
        "belief", "intention", "prediction", "judgment", "fear", "desire");
}

@Test
void cognitiveTypesHaveJavaClassAssociations() {
    var store = new InMemoryMindMapStore();
    var registry = new TypeRegistry(store);
    var loader = new CognitiveLoader(store, List.of());
    loader.init();

    assertThat(registry.javaClass("belief", "t1")).contains(Belieflike.class);
    assertThat(registry.javaClass("intention", "t1")).contains(Intentionlike.class);
    assertThat(registry.javaClass("prediction", "t1")).contains(Predictive.class);
    assertThat(registry.javaClass("judgment", "t1")).contains(Evaluative.class);
    assertThat(registry.javaClass("fear", "t1")).contains(Fearlike.class);
    assertThat(registry.javaClass("desire", "t1")).contains(Desirelike.class);
}

@Test
void schemaForBelief_derivesFromInterface() {
    var store = new InMemoryMindMapStore();
    var registry = new TypeRegistry(store);
    var loader = new CognitiveLoader(store, List.of());
    loader.init();

    var schema = registry.schemaFor("belief", "t1");
    assertThat(schema).containsKeys("subject", "status", "basis");
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveLoaderTest`
Expected: FAIL — CognitiveLoader.init() doesn't register types yet

- [ ] **Step 3: Add COGNITIVE_TYPES map to TypeRegistry**

Add a static map in `TypeRegistry.java` alongside the existing `CORE_TYPES` map:

```java
static final Map<String, Class<?>> COGNITIVE_TYPES = Map.of(
    "belief", Belieflike.class,
    "intention", Intentionlike.class,
    "prediction", Predictive.class,
    "judgment", Evaluative.class,
    "fear", Fearlike.class,
    "desire", Desirelike.class
);
```

Also extend `registerType()` to accept an optional java-class — or add a new overload `registerType(String typeName, String parentType, Class<?> javaClass, String tenantId)` that sets the `java-class` property and schema on the type node:

```java
public void registerType(String typeName, String parentType, Class<?> javaClass, String tenantId) {
    BootstrappedTenant bt = ensureBootstrapped(tenantId);
    String normalized = typeName.strip().toLowerCase();
    if (bt.resolveTypeNode(normalized) != null) return;

    Map<String, String> props = new HashMap<>();
    if (javaClass != null) {
        props.put(JAVA_CLASS, javaClass.getName());
        deriveSchemaFromInterface(javaClass).forEach((fieldName, sf) -> {
            props.put(SCHEMA_PREFIX + fieldName + ".type", sf.type());
        });
    }

    String nodeId = store.addNode(
        NodeInput.of(normalized, bt.typeSystemSubgraphId)
            .withProperties(props),
        tenantId);
    bt.typeNodeIds.put(normalized, nodeId);

    if (parentType != null) {
        MindMapNode parentNode = bt.resolveTypeNode(parentType.strip().toLowerCase());
        if (parentNode != null) {
            store.addEdge(EdgeInput.of(nodeId, parentNode.id(), SUBTYPE_OF)
                .withProvenance("type-registry"), tenantId);
        }
    }
}
```

- [ ] **Step 4: Add type registration to CognitiveLoader.init()**

Inject `TypeRegistry` into `CognitiveLoader`. In `init()`, after vocabulary registration, register cognitive types. CognitiveLoader registers types for a default tenant; types are idempotent so re-registration on subsequent tenant discovery is safe:

```java
private final TypeRegistry typeRegistry;

// Update constructor to accept Instance<TypeRegistry>
// In init():
if (typeRegistry != null) {
    String defaultTenant = "default";
    typeRegistry.registerType("cognitive", null, null, defaultTenant);
    for (var entry : TypeRegistry.COGNITIVE_TYPES.entrySet()) {
        typeRegistry.registerType(entry.getKey(), "cognitive", entry.getValue(), defaultTenant);
    }
    LOG.info("Registered " + TypeRegistry.COGNITIVE_TYPES.size() + " cognitive type(s)");
}
```

Note: The test creates CognitiveLoader with a direct TypeRegistry reference. The CDI constructor uses `Instance<TypeRegistry>` with graceful degradation.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveLoaderTest`
Expected: all tests PASS (existing + new)

- [ ] **Step 6: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: all tests PASS — no regressions

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TypeRegistry.java \
  mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoader.java \
  mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoaderTest.java
git commit -m "feat(mindmap-intelligence): register COGNITIVE type hierarchy in CognitiveLoader

COGNITIVE parent type under GENERAL with 6 children: belief, intention,
prediction, judgment, fear, desire. Java class associations enable
schema derivation via TypeRegistry.schemaFor().

Refs #322"
```

## Batch 3: MindMapExtractor — Prompt + Routing + cognitiveKind Property

### Task 4: Update MindMapExtractor for cognitive type extraction

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java:39-64` (SYSTEM_PROMPT), `:190-251` (applyExtraction), `:272-275` (normalizeType + new resolveSubgraphType)
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractorTest.java` (add cognitive routing tests)

**Interfaces:**
- Consumes: `SubgraphTypes.COGNITIVE` from Task 1; `ParsedEntity(String name, String type, Map<String, String> properties, ConfidenceOrigin origin)` — existing record; `ExtractedEntity(String nodeId, String name, boolean created, String subgraphType, Map<String, String> properties)` — existing record
- Produces: nodes in COGNITIVE subgraph with `cognitiveKind` property set

- [ ] **Step 1: Write tests for cognitive type routing**

Add tests to `MindMapExtractorTest.java` that verify:
1. `normalizeType("BELIEF")` returns `"belief"` (unchanged — still pure normalization)
2. `resolveSubgraphType("belief")` returns `SubgraphTypes.COGNITIVE`
3. `resolveSubgraphType("person")` returns `"person"` (non-cognitive types unchanged)
4. When extraction produces a BELIEF entity, the node gets `cognitiveKind=belief` property and lands in a COGNITIVE subgraph

```java
@Test
void normalizeType_lowercasesCognitiveType() {
    assertThat(extractor.normalizeType("BELIEF")).isEqualTo("belief");
    assertThat(extractor.normalizeType("PREDICTION")).isEqualTo("prediction");
}

@Test
void resolveSubgraphType_routesCognitiveTypesToCognitiveSubgraph() {
    assertThat(MindMapExtractor.resolveSubgraphType("belief"))
        .isEqualTo(SubgraphTypes.COGNITIVE);
    assertThat(MindMapExtractor.resolveSubgraphType("intention"))
        .isEqualTo(SubgraphTypes.COGNITIVE);
    assertThat(MindMapExtractor.resolveSubgraphType("prediction"))
        .isEqualTo(SubgraphTypes.COGNITIVE);
    assertThat(MindMapExtractor.resolveSubgraphType("judgment"))
        .isEqualTo(SubgraphTypes.COGNITIVE);
    assertThat(MindMapExtractor.resolveSubgraphType("fear"))
        .isEqualTo(SubgraphTypes.COGNITIVE);
    assertThat(MindMapExtractor.resolveSubgraphType("desire"))
        .isEqualTo(SubgraphTypes.COGNITIVE);
}

@Test
void resolveSubgraphType_preservesNonCognitiveTypes() {
    assertThat(MindMapExtractor.resolveSubgraphType("person")).isEqualTo("person");
    assertThat(MindMapExtractor.resolveSubgraphType("concept")).isEqualTo("concept");
}
```

For the integration test (cognitiveKind property), use the existing test infrastructure in MindMapExtractorTest to verify that when `applyExtraction` processes a `ParsedEntity` with type `"BELIEF"`, the resulting node has `cognitiveKind=belief` in its properties. This requires either making `applyExtraction` package-visible for testing or testing through the public `extract()` method with a mock AgentProvider.

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorTest -DfailIfNoTests=false`
Expected: FAIL — `resolveSubgraphType` doesn't exist yet

- [ ] **Step 3: Add COGNITIVE_TYPES set and resolveSubgraphType to MindMapExtractor**

Add a static set and method:

```java
private static final Set<String> COGNITIVE_TYPES = Set.of(
    "belief", "intention", "prediction", "judgment", "fear", "desire");

static String resolveSubgraphType(String normalizedType) {
    if (COGNITIVE_TYPES.contains(normalizedType)) return SubgraphTypes.COGNITIVE;
    return normalizedType;
}
```

- [ ] **Step 4: Update applyExtraction to set cognitiveKind property**

In `applyExtraction()`, before creating the node, check if the normalized type is cognitive and add the `cognitiveKind` property:

```java
String normalizedType = normalizeType(pe.type());
String sgType = resolveSubgraphType(normalizedType);

Map<String, String> nodeProps = pe.properties() != null
    ? new HashMap<>(pe.properties()) : new HashMap<>();
if (COGNITIVE_TYPES.contains(normalizedType)) {
    nodeProps.put("cognitiveKind", normalizedType);
}
```

Use `sgType` instead of `normalizedType` in the `findOrCreateSubgraph()` call. Use `nodeProps` instead of `pe.properties()` when creating/updating the node.

- [ ] **Step 5: Update SYSTEM_PROMPT with cognitive types**

Replace the type list in SYSTEM_PROMPT:

```java
"type": "PERSON|PROJECT|RESEARCH_AREA|ORGANISATION|CONCEPT|GENERAL|BELIEF|INTENTION|PREDICTION|JUDGMENT|FEAR|DESIRE"
```

Add classification guidance after the rules section:

```
For cognitive content (beliefs, intentions, predictions, judgments, fears, desires), \
classify by the PRIMARY cognitive aspect. Use STATED confidence for explicit markers \
("I think...", "I'm worried..."), INFERRED for implied attitudes, SPECULATED for \
ambiguous cases.
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorTest`
Expected: all tests PASS

- [ ] **Step 7: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests=false`
Expected: BUILD SUCCESS — all modules compile, all tests pass

- [ ] **Step 8: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java \
  mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractorTest.java
git commit -m "feat(mindmap-intelligence): cognitive type extraction in MindMapExtractor

Expand LLM extraction prompt with BELIEF|INTENTION|PREDICTION|JUDGMENT|
FEAR|DESIRE types. resolveSubgraphType() routes cognitive types to
COGNITIVE subgraph. cognitiveKind property set on extracted nodes.

Refs #322"
```

## References

- [2026-09-14-cognitive-node-types-design.md] — design spec this plan implements
- [decisions.md D1-D9] — decision rationale
- [SubgraphTypes.java] — subgraph type constants
- [TypeRegistry.java:105-125] — registerType API
- [CognitiveLoader.java:52-69] — cognitive bootstrap lifecycle
- [MindMapExtractor.java:39-64] — SYSTEM_PROMPT
- [MindMapExtractor.java:190-270] — applyExtraction + normalizeType
- [DeclarativeRuleRegistry.java:59-73] — YAML rule loading
- [StandardTraitRulesTest.java] — existing trait rule test pattern
- [CognitiveLoaderTest.java] — existing CognitiveLoader test pattern
- [ThingTest.java:58-64] — trait interface proxy test pattern
- [GitHub #322] — focal issue
- [GitHub #333] — cognitive observability epic (queued)
