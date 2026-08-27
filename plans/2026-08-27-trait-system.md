# Trait System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #219 — feat: mindmap-intelligence — trait system with proxy generation
**Issue group:** #213, #215, #216, #217, #218, #219, #220, #221

**Goal:** Add forward-chaining trait rules to the mindmap graph — nodes automatically
receive traits based on their properties and edges, with truth maintenance and typed
proxy access.

**Architecture:** Three-layer split following D19-D22. `TraitRule` SPI in mindmap-api
(extension point contract). `TraitApplicationDecorator` at `@Priority(70)` in mindmap/
(engine — fires rules, applies/retracts traits). `mindmap-intelligence/` module (knowledge —
standard trait interfaces, proxy generation, and rule implementations).

**Tech Stack:** Java 21, CDI (Quarkus ArC), JDK `java.lang.reflect.Proxy`, JUnit 5, AssertJ

## Global Constraints

- Java 21 source level, Java 26 JVM
- Zero external deps in mindmap-api/ (pure Java, Tier 1)
- mindmap/ depends on mindmap-api + quarkus-arc
- mindmap-intelligence/ depends on mindmap-api + quarkus-arc (NO LLM deps for trait system)
- Jandex plugin required in all CDI modules
- All trait interface methods MUST use boxed types or Optional, never primitives (D21)
- Convention: method name = property key for proxy mapping

---

## Batch 1: Decorator Engine — TraitRule SPI + TraitApplicationDecorator

### Task 1: TraitRule SPI + TraitApplicationDecorator + unit tests

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraitRule.java`
- Create: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/TraitApplicationDecorator.java`
- Create: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/TraitApplicationDecoratorTest.java`

**Interfaces:**
- Consumes: `MindMapStore` SPI, `NodeInput`, `NodeUpdate`, `EdgeInput`, `MindMapNode`, `MindMapEdge`
- Produces: `TraitRule` interface (consumed by Task 3), `TraitApplicationDecorator` (CDI decorator)

- [ ] **Step 1: Write TraitRule SPI interface**

Use `ide_create_file` to create `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraitRule.java`:

```java
package io.casehub.neocortex.mindmap;

import java.util.List;

public interface TraitRule {
    String traitName();
    boolean matches(MindMapNode node, List<MindMapEdge> edges);
}
```

- [ ] **Step 2: Verify TraitRule compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl mindmap-api -q`
Expected: BUILD SUCCESS

- [ ] **Step 3: Write failing tests for TraitApplicationDecorator**

Use `ide_create_file` to create the test class. Tests cover: basic rule firing on addNode,
addEdge, removeEdge, updateNode; truth maintenance (retraction when no rules match);
conflict resolution (application wins); reentrancy guard; empty rule list passthrough.

```java
package io.casehub.neocortex.mindmap.runtime;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class TraitApplicationDecoratorTest {

    private InMemoryMindMapStore store;
    private TraitApplicationDecorator decorator;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        decorator = new TraitApplicationDecorator(store, List.of(new PersonableRule()));
        subgraphId = store.createSubgraph(
            new SubgraphInput("Test", SubgraphType.GENERAL, null), "t1");
    }

    @Test
    void addNode_withMatchingProperties_appliesTrait() {
        String id = decorator.addNode(
            new NodeInput("Alice", subgraphId, ConfidenceOrigin.STATED, null,
                "test", null, null, null, null, null, null, null,
                Map.of("birthday", "1990-01-15")), "t1");

        MindMapNode node = decorator.getNode(id, "t1");
        assertThat(node.traits()).contains("Personable");
    }

    @Test
    void addNode_withoutMatchingProperties_noTrait() {
        String id = decorator.addNode(node("Project-X"), "t1");

        MindMapNode node = decorator.getNode(id, "t1");
        assertThat(node.traits()).doesNotContain("Personable");
    }

    @Test
    void addEdge_matchingEdgeType_appliesTraitToSource() {
        String alice = decorator.addNode(node("Alice"), "t1");
        String bob = decorator.addNode(node("Bob"), "t1");

        decorator.addEdge(edge(alice, bob, "parent-of"), "t1");

        MindMapNode aliceNode = decorator.getNode(alice, "t1");
        assertThat(aliceNode.traits()).contains("Personable");
    }

    @Test
    void removeEdge_lastEvidence_retractsTrait() {
        String alice = decorator.addNode(node("Alice"), "t1");
        String bob = decorator.addNode(node("Bob"), "t1");

        String edgeId = decorator.addEdge(edge(alice, bob, "parent-of"), "t1");
        assertThat(decorator.getNode(alice, "t1").traits()).contains("Personable");

        decorator.removeEdge(edgeId, "t1");

        assertThat(decorator.getNode(alice, "t1").traits()).doesNotContain("Personable");
    }

    @Test
    void updateNode_addProperty_appliesTrait() {
        String alice = decorator.addNode(node("Alice"), "t1");
        assertThat(decorator.getNode(alice, "t1").traits()).doesNotContain("Personable");

        decorator.updateNode(alice,
            new NodeUpdate(null, null, null, null, null, null, null, null,
                null, null, null, null, null,
                Map.of("birthday", "1990-01-15"), null), "t1");

        assertThat(decorator.getNode(alice, "t1").traits()).contains("Personable");
    }

    @Test
    void updateNode_removeProperty_retractsTrait() {
        String alice = decorator.addNode(
            new NodeInput("Alice", subgraphId, ConfidenceOrigin.STATED, null,
                "test", null, null, null, null, null, null, null,
                Map.of("birthday", "1990-01-15")), "t1");
        assertThat(decorator.getNode(alice, "t1").traits()).contains("Personable");

        decorator.updateNode(alice,
            new NodeUpdate(null, null, null, null, null, null, null, null,
                null, null, null, null, null,
                null, Set.of("birthday")), "t1");

        assertThat(decorator.getNode(alice, "t1").traits()).doesNotContain("Personable");
    }

    @Test
    void conflictResolution_applicationWinsOverRetraction() {
        // Two rules: one matches (birthday), one doesn't (email)
        // Application wins — trait should be present
        decorator = new TraitApplicationDecorator(store,
            List.of(new PersonableRule(), new EmailPersonableRule()));

        String alice = decorator.addNode(
            new NodeInput("Alice", subgraphId, ConfidenceOrigin.STATED, null,
                "test", null, null, null, null, null, null, null,
                Map.of("birthday", "1990-01-15")), "t1");

        assertThat(decorator.getNode(alice, "t1").traits()).contains("Personable");
    }

    @Test
    void reentrancyGuard_traitMutationDoesNotRetriggerEvaluation() {
        var countingRule = new CountingRule();
        decorator = new TraitApplicationDecorator(store, List.of(countingRule));

        String alice = decorator.addNode(node("Alice"), "t1");
        String bob = decorator.addNode(node("Bob"), "t1");
        // Reset after addNode calls (each addNode triggers 1 evaluation)
        countingRule.callCount = 0;

        decorator.addEdge(edge(alice, bob, "parent-of"), "t1");

        // matches() called for source (alice) and target (bob) — 2 calls
        // The updateNode that applies the trait should NOT trigger re-evaluation
        assertThat(countingRule.callCount).isEqualTo(2);
    }

    @Test
    void decoratorChain_derivedEdgeTriggersTrait() {
        // Chain: TraitApp(70) → DerivedEdge(80) → Store
        // has-child → DerivedEdge creates parent-of → TraitApp sees parent-of → applies Personable
        var derivedDecorator = new DerivedEdgeDecorator(store,
            List.of(new DerivedEdgeDecoratorTest.InverseEdgeRule()));
        decorator = new TraitApplicationDecorator(derivedDecorator, List.of(new PersonableRule()));

        String alice = decorator.addNode(node("Alice"), "t1");
        String bob = decorator.addNode(node("Bob"), "t1");

        decorator.addEdge(edge(alice, bob, "has-child"), "t1");

        // DerivedEdge creates "parent-of" on bob → TraitApp sees it → Personable on bob
        assertThat(decorator.getNode(bob, "t1").traits()).contains("Personable");
        // alice has "has-child" but not "parent-of" — PersonableRule checks for parent-of
        // However alice IS the source of has-child, and has-child triggers the rule
        // if PersonableRule checked for has-child too, alice would get it.
        // As written, PersonableRule checks parent-of/child-of/works-at, so only bob gets it.
    }

    @Test
    void emptyRuleList_purePassthrough() {
        TraitApplicationDecorator noRules = new TraitApplicationDecorator(store, List.of());

        String alice = noRules.addNode(
            new NodeInput("Alice", subgraphId, ConfidenceOrigin.STATED, null,
                "test", null, null, null, null, null, null, null,
                Map.of("birthday", "1990-01-15")), "t1");

        assertThat(noRules.getNode(alice, "t1").traits()).isEmpty();
    }

    @Test
    void multipleRules_differentTraits_bothApplied() {
        decorator = new TraitApplicationDecorator(store,
            List.of(new PersonableRule(), new ProjectlikeRule()));

        String node = decorator.addNode(
            new NodeInput("Neocortex", subgraphId, ConfidenceOrigin.STATED, null,
                "test", null, null, null, null, null, null, null,
                Map.of("birthday", "n/a", "status", "active")), "t1");

        MindMapNode result = decorator.getNode(node, "t1");
        assertThat(result.traits()).contains("Personable", "Projectlike");
    }


    // --- Test rules ---

    static class PersonableRule implements TraitRule {
        @Override public String traitName() { return "Personable"; }

        @Override
        public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
            boolean hasProperties = node.property("birthday").isPresent()
                || node.property("role").isPresent()
                || node.property("email").isPresent();
            boolean hasEdges = edges.stream()
                .anyMatch(e -> "parent-of".equals(e.edgeType())
                    || "child-of".equals(e.edgeType())
                    || "works-at".equals(e.edgeType()));
            return hasProperties || hasEdges;
        }
    }

    static class EmailPersonableRule implements TraitRule {
        @Override public String traitName() { return "Personable"; }

        @Override
        public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
            return node.property("email").isPresent();
        }
    }

    static class ProjectlikeRule implements TraitRule {
        @Override public String traitName() { return "Projectlike"; }

        @Override
        public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
            return node.property("status").isPresent();
        }
    }

    static class CountingRule implements TraitRule {
        int callCount = 0;
        @Override public String traitName() { return "Personable"; }

        @Override
        public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
            callCount++;
            return edges.stream().anyMatch(e -> "parent-of".equals(e.edgeType()));
        }
    }

    private NodeInput node(String name) {
        return new NodeInput(name, subgraphId, ConfidenceOrigin.STATED, null,
            "test", null, null, null, null, null, null, null, null);
    }

    private EdgeInput edge(String source, String target, String type) {
        return new EdgeInput(source, target, type, ConfidenceOrigin.STATED, null,
            "test", null, null, null, null, null, null);
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap -Dtest=TraitApplicationDecoratorTest -q`
Expected: COMPILATION FAILURE (TraitApplicationDecorator doesn't exist)

- [ ] **Step 5: Implement TraitApplicationDecorator**

Use `ide_create_file` to create the decorator:

```java
package io.casehub.neocortex.mindmap.runtime;

import io.casehub.neocortex.mindmap.*;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.inject.Any;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.util.*;

@Decorator
@Priority(70)
public class TraitApplicationDecorator implements MindMapStore {

    private static final ThreadLocal<Boolean> evaluating =
        ThreadLocal.withInitial(() -> false);

    private final MindMapStore          delegate;
    private final List<TraitRule>        rules;

    @Inject
    public TraitApplicationDecorator(@Delegate @Any MindMapStore delegate,
                                     Instance<TraitRule> rules) {
        this(delegate, rules.stream().toList());
    }

    TraitApplicationDecorator(MindMapStore delegate, List<TraitRule> rules) {
        this.delegate = delegate;
        this.rules    = List.copyOf(rules);
    }

    @Override
    public String addNode(NodeInput input, String tenantId) {
        String nodeId = delegate.addNode(input, tenantId);
        if (!evaluating.get()) {
            evaluateTraitsForNode(nodeId, tenantId);
        }
        return nodeId;
    }

    @Override
    public void updateNode(String nodeId, NodeUpdate update, String tenantId) {
        delegate.updateNode(nodeId, update, tenantId);
        if (!evaluating.get()) {
            evaluateTraitsForNode(nodeId, tenantId);
        }
    }

    @Override
    public String addEdge(EdgeInput input, String tenantId) {
        String edgeId = delegate.addEdge(input, tenantId);
        if (!evaluating.get()) {
            evaluating.set(true);
            try {
                evaluateTraitsForNode(input.sourceNodeId(), tenantId);
                evaluateTraitsForNode(input.targetNodeId(), tenantId);
            } finally {
                evaluating.set(false);
            }
        }
        return edgeId;
    }

    @Override
    public void removeEdge(String edgeId, String tenantId) {
        MindMapEdge edge = delegate.getEdge(edgeId, tenantId);
        String sourceId = edge != null ? edge.sourceNodeId() : null;
        String targetId = edge != null ? edge.targetNodeId() : null;

        delegate.removeEdge(edgeId, tenantId);

        if (!evaluating.get() && edge != null) {
            evaluating.set(true);
            try {
                evaluateTraitsForNode(sourceId, tenantId);
                evaluateTraitsForNode(targetId, tenantId);
            } finally {
                evaluating.set(false);
            }
        }
    }

    private void evaluateTraitsForNode(String nodeId, String tenantId) {
        if (rules.isEmpty()) return;

        MindMapNode node = delegate.getNode(nodeId, tenantId);
        if (node == null) return;

        List<MindMapEdge> edges = delegate.neighbors(nodeId, tenantId);

        Set<String> traitsToAdd    = new LinkedHashSet<>();
        Set<String> traitsToRemove = new LinkedHashSet<>();

        Map<String, Boolean> traitMatches = new HashMap<>();
        for (TraitRule rule : rules) {
            boolean matches = rule.matches(node, edges);
            traitMatches.merge(rule.traitName(), matches, (a, b) -> a || b);
        }

        for (var entry : traitMatches.entrySet()) {
            String traitName = entry.getKey();
            boolean anyMatch = entry.getValue();
            boolean present  = node.traits().contains(traitName);

            if (anyMatch && !present) {
                traitsToAdd.add(traitName);
            } else if (!anyMatch && present) {
                traitsToRemove.add(traitName);
            }
        }

        if (!traitsToAdd.isEmpty() || !traitsToRemove.isEmpty()) {
            delegate.updateNode(nodeId,
                new NodeUpdate(null, null, null, null,
                    traitsToAdd.isEmpty() ? null : traitsToAdd,
                    traitsToRemove.isEmpty() ? null : traitsToRemove,
                    null, null, null, null, null, null, null, null, null),
                tenantId);
        }
    }


    // --- Delegate all other methods ---

    @Override
    public void registerVocabulary(MindMapVocabulary vocabulary)                                 {delegate.registerVocabulary(vocabulary);}

    @Override
    public MindMapNode getNode(String nodeId, String tenantId)                                   {return delegate.getNode(nodeId, tenantId);}

    @Override
    public MindMapEdge getEdge(String edgeId, String tenantId)                                   {return delegate.getEdge(edgeId, tenantId);}

    @Override
    public void addAlias(String nodeId, String alias, String tenantId)                           {delegate.addAlias(nodeId, alias, tenantId);}

    @Override
    public void removeAlias(String nodeId, String alias, String tenantId)                        {delegate.removeAlias(nodeId, alias, tenantId);}

    @Override
    public MindMapNode resolveNode(String nameOrAlias, String subgraphId, String tenantId)       {return delegate.resolveNode(nameOrAlias, subgraphId, tenantId);}

    @Override
    public MergeResult mergeNodes(String keepNodeId, String removeNodeId, String tenantId)       {return delegate.mergeNodes(keepNodeId, removeNodeId, tenantId);}

    @Override
    public String createSubgraph(SubgraphInput input, String tenantId)                           {return delegate.createSubgraph(input, tenantId);}

    @Override
    public MindMapSubgraph getSubgraph(String subgraphId, String tenantId)                       {return delegate.getSubgraph(subgraphId, tenantId);}

    @Override
    public void updateSubgraph(String subgraphId, String rootNodeId, String tenantId)            {delegate.updateSubgraph(subgraphId, rootNodeId, tenantId);}

    @Override
    public List<MindMapNode> nodesIn(String subgraphId, String tenantId)                         {return delegate.nodesIn(subgraphId, tenantId);}

    @Override
    public List<MindMapEdge> bridgeEdges(String subgraphId, String tenantId)                     {return delegate.bridgeEdges(subgraphId, tenantId);}

    @Override
    public List<MindMapEdge> neighbors(String nodeId, String tenantId)                           {return delegate.neighbors(nodeId, tenantId);}

    @Override
    public List<MindMapEdge> neighbors(String nodeId, String edgeType, String tenantId)          {return delegate.neighbors(nodeId, edgeType, tenantId);}

    @Override
    public List<MindMapNode> search(MindMapQuery query)                                          {return delegate.search(query);}

    @Override
    public void supersede(String targetId, String supersedingId, String reason, String tenantId) {delegate.supersede(targetId, supersedingId, reason, tenantId);}

    @Override
    public void reinstate(String targetId, String tenantId)                                      {delegate.reinstate(targetId, tenantId);}

    @Override
    public SupersessionStatus getSupersessionStatus(String targetId, String tenantId)            {return delegate.getSupersessionStatus(targetId, tenantId);}

    @Override
    public int eraseNode(String nodeId, String tenantId)                                         {return delegate.eraseNode(nodeId, tenantId);}

    @Override
    public int eraseSubgraph(String subgraphId, String tenantId)                                 {return delegate.eraseSubgraph(subgraphId, tenantId);}

    @Override
    public int eraseEntity(String entityName, String tenantId)                                   {return delegate.eraseEntity(entityName, tenantId);}

    @Override
    public int eraseEntityAcrossTenants(String entityName, Set<String> tenantIds)                {return delegate.eraseEntityAcrossTenants(entityName, tenantIds);}

    @Override
    public Set<MindMapCapability> capabilities()                                                 {return delegate.capabilities();}
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap -Dtest=TraitApplicationDecoratorTest -q`
Expected: All 11 tests PASS

- [ ] **Step 7: Run full mindmap module tests for regression**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap -q`
Expected: All existing tests PASS (no regression)

- [ ] **Step 8: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraitRule.java \
        mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/TraitApplicationDecorator.java \
        mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/TraitApplicationDecoratorTest.java
git commit -m "feat(#219): TraitRule SPI + TraitApplicationDecorator — forward-chaining trait evaluation

Refs #219"
```

---

## Batch 2: Intelligence Module — trait interfaces, standard rules, proxy

### Task 2: mindmap-intelligence/ module + trait interfaces + standard rules

**Files:**
- Create: `mindmap-intelligence/pom.xml`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Personable.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Projectlike.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Organisational.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/PersonableTraitRule.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ProjectlikeTraitRule.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/OrganisationalTraitRule.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/StandardTraitRulesTest.java`
- Modify: `pom.xml` (parent — add module + dependency management)

**Interfaces:**
- Consumes: `TraitRule` SPI (from Task 1), `MindMapNode`, `MindMapEdge`
- Produces: `Personable`, `Projectlike`, `Organisational` interfaces (consumed by Task 3),
  `PersonableTraitRule`, `ProjectlikeTraitRule`, `OrganisationalTraitRule` CDI beans

- [ ] **Step 1: Create mindmap-intelligence/pom.xml**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-neocortex-mindmap-intelligence</artifactId>
  <name>CaseHub Neocortex - MindMap Intelligence</name>
  <description>Trait interfaces, proxy generation, and standard trait rules for MindMap graph.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-mindmap-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-mindmap-inmem</artifactId>
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
  <build>
    <plugins>
      <plugin>
        <groupId>io.smallrye</groupId>
        <artifactId>jandex-maven-plugin</artifactId>
        <executions>
          <execution>
            <id>make-index</id>
            <goals><goal>jandex</goal></goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 2: Register module in parent pom.xml**

Add `<module>mindmap-intelligence</module>` after `mindmap-sqlite` in the `<modules>` section.

Add to `<dependencyManagement>`:
```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-mindmap-intelligence</artifactId>
  <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Create source directories**

```bash
mkdir -p mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence
mkdir -p mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence
```

- [ ] **Step 4: Write trait interfaces**

Use `ide_create_file` for each:

`Personable.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Personable {
    Optional<String> birthday();
    Optional<String> role();
    Optional<String> email();
    Optional<String> phone();
}
```

`Projectlike.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Projectlike {
    Optional<String> status();
    Optional<String> startDate();
    Optional<String> endDate();
    Optional<String> description();
}
```

`Organisational.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Organisational {
    Optional<String> industry();
    Optional<String> size();
    Optional<String> location();
}
```

- [ ] **Step 5: Write failing tests for standard trait rules**

Use `ide_create_file`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class StandardTraitRulesTest {

    private InMemoryMindMapStore store;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        subgraphId = store.createSubgraph(
            new SubgraphInput("Test", SubgraphType.GENERAL, null), "t1");
    }

    @Test
    void personableRule_matchesBirthday() {
        String id = store.addNode(new NodeInput("Alice", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null,
            Map.of("birthday", "1990-01-15")), "t1");
        MindMapNode node = store.getNode(id, "t1");

        var rule = new PersonableTraitRule();
        assertThat(rule.traitName()).isEqualTo("Personable");
        assertThat(rule.matches(node, List.of())).isTrue();
    }

    @Test
    void personableRule_matchesParentOfEdge() {
        String alice = store.addNode(node("Alice"), "t1");
        String bob = store.addNode(node("Bob"), "t1");
        String edgeId = store.addEdge(edge(alice, bob, "parent-of"), "t1");

        MindMapNode aliceNode = store.getNode(alice, "t1");
        MindMapEdge e = store.getEdge(edgeId, "t1");
        assertThat(new PersonableTraitRule().matches(aliceNode, List.of(e))).isTrue();
    }

    @Test
    void personableRule_noMatch() {
        String id = store.addNode(node("Widget"), "t1");
        MindMapNode node = store.getNode(id, "t1");
        assertThat(new PersonableTraitRule().matches(node, List.of())).isFalse();
    }

    @Test
    void projectlikeRule_matchesStatus() {
        String id = store.addNode(new NodeInput("Neocortex", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null,
            Map.of("status", "active")), "t1");
        MindMapNode node = store.getNode(id, "t1");

        var rule = new ProjectlikeTraitRule();
        assertThat(rule.traitName()).isEqualTo("Projectlike");
        assertThat(rule.matches(node, List.of())).isTrue();
    }

    @Test
    void organisationalRule_matchesIndustry() {
        String id = store.addNode(new NodeInput("Acme", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null,
            Map.of("industry", "tech")), "t1");
        MindMapNode node = store.getNode(id, "t1");

        var rule = new OrganisationalTraitRule();
        assertThat(rule.traitName()).isEqualTo("Organisational");
        assertThat(rule.matches(node, List.of())).isTrue();
    }

    private NodeInput node(String name) {
        return new NodeInput(name, subgraphId, ConfidenceOrigin.STATED, null,
            "test", null, null, null, null, null, null, null, null);
    }

    private EdgeInput edge(String source, String target, String type) {
        return new EdgeInput(source, target, type, ConfidenceOrigin.STATED, null,
            "test", null, null, null, null, null, null);
    }
}
```

- [ ] **Step 6: Implement standard trait rules**

Use `ide_create_file` for each:

`PersonableTraitRule.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class PersonableTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Personable"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        boolean hasProperties = node.property("birthday").isPresent()
            || node.property("role").isPresent()
            || node.property("email").isPresent()
            || node.property("phone").isPresent();
        boolean hasEdges = edges.stream()
            .anyMatch(e -> "parent-of".equals(e.edgeType())
                || "child-of".equals(e.edgeType())
                || "works-at".equals(e.edgeType()));
        return hasProperties || hasEdges;
    }
}
```

`ProjectlikeTraitRule.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class ProjectlikeTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Projectlike"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        boolean hasProperties = node.property("status").isPresent()
            || node.property("startDate").isPresent()
            || node.property("endDate").isPresent();
        boolean hasEdges = edges.stream()
            .anyMatch(e -> "contributes-to".equals(e.edgeType())
                || "depends-on".equals(e.edgeType()));
        return hasProperties || hasEdges;
    }
}
```

`OrganisationalTraitRule.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class OrganisationalTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Organisational"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        boolean hasProperties = node.property("industry").isPresent()
            || node.property("size").isPresent()
            || node.property("location").isPresent();
        boolean hasEdges = edges.stream()
            .anyMatch(e -> "employs".equals(e.edgeType())
                || "subsidiary-of".equals(e.edgeType()));
        return hasProperties || hasEdges;
    }
}
```

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -q`
Expected: All 5 tests PASS

- [ ] **Step 8: Commit**

```bash
git add mindmap-intelligence/ pom.xml
git commit -m "feat(#219): mindmap-intelligence module — trait interfaces + standard rules

Refs #219"
```

### Task 3: TraitProxy — JDK Proxy generation + tests

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitProxy.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitInvocationHandler.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TraitProxyTest.java`

**Interfaces:**
- Consumes: `MindMapNode` interface, `Personable`/`Projectlike`/`Organisational` from Task 2
- Produces: `TraitProxy.as(MindMapNode, Class<T>)` — public API for typed node access

- [ ] **Step 1: Write failing tests for TraitProxy**

Use `ide_create_file`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class TraitProxyTest {

    private InMemoryMindMapStore store;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        subgraphId = store.createSubgraph(
            new SubgraphInput("Test", SubgraphType.GENERAL, null), "t1");
    }

    @Test
    void as_returnsProxyImplementingInterface() {
        String id = store.addNode(new NodeInput("Alice", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null,
            Map.of("birthday", "1990-01-15", "role", "engineer")), "t1");
        MindMapNode node = store.getNode(id, "t1");

        Personable p = TraitProxy.as(node, Personable.class);
        assertThat(p).isInstanceOf(Personable.class);
        assertThat(p.birthday()).isEqualTo(Optional.of("1990-01-15"));
        assertThat(p.role()).isEqualTo(Optional.of("engineer"));
    }

    @Test
    void as_missingProperty_returnsEmpty() {
        String id = store.addNode(new NodeInput("Alice", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null, null), "t1");
        MindMapNode node = store.getNode(id, "t1");

        Personable p = TraitProxy.as(node, Personable.class);
        assertThat(p.birthday()).isEmpty();
        assertThat(p.email()).isEmpty();
    }

    @Test
    void as_nonInterface_throwsIllegalArgument() {
        String id = store.addNode(new NodeInput("Alice", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null, null), "t1");
        MindMapNode node = store.getNode(id, "t1");

        assertThatThrownBy(() -> TraitProxy.as(node, String.class))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("interface");
    }

    @Test
    void as_projectlike_readsProperties() {
        String id = store.addNode(new NodeInput("Neocortex", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null,
            Map.of("status", "active", "startDate", "2026-01-01")), "t1");
        MindMapNode node = store.getNode(id, "t1");

        Projectlike p = TraitProxy.as(node, Projectlike.class);
        assertThat(p.status()).isEqualTo(Optional.of("active"));
        assertThat(p.startDate()).isEqualTo(Optional.of("2026-01-01"));
        assertThat(p.endDate()).isEmpty();
    }

    @Test
    void as_toString_includesNodeName() {
        String id = store.addNode(new NodeInput("Alice", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null, null), "t1");
        MindMapNode node = store.getNode(id, "t1");

        Personable p = TraitProxy.as(node, Personable.class);
        assertThat(p.toString()).contains("Alice").contains("Personable");
    }

    @Test
    void as_equals_sameNodeSameInterface_areEqual() {
        String id = store.addNode(new NodeInput("Alice", subgraphId,
            ConfidenceOrigin.STATED, null, "test", null, null,
            null, null, null, null, null, null), "t1");
        MindMapNode node = store.getNode(id, "t1");

        Personable p1 = TraitProxy.as(node, Personable.class);
        Personable p2 = TraitProxy.as(node, Personable.class);
        assertThat(p1).isEqualTo(p2);
        assertThat(p1.hashCode()).isEqualTo(p2.hashCode());
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=TraitProxyTest -q`
Expected: COMPILATION FAILURE (TraitProxy doesn't exist)

- [ ] **Step 3: Implement TraitInvocationHandler**

Use `ide_create_file`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapNode;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Method;
import java.util.Objects;
import java.util.Optional;

final class TraitInvocationHandler implements InvocationHandler {

    private final MindMapNode node;
    private final Class<?>    traitInterface;

    TraitInvocationHandler(MindMapNode node, Class<?> traitInterface) {
        this.node           = node;
        this.traitInterface = traitInterface;
    }

    @Override
    public Object invoke(Object proxy, Method method, Object[] args) throws Throwable {
        return switch (method.getName()) {
            case "toString" -> traitInterface.getSimpleName() + "[" + node.name() + "]";
            case "hashCode" -> Objects.hash(node.id(), traitInterface);
            case "equals"   -> args[0] != null
                && java.lang.reflect.Proxy.isProxyClass(args[0].getClass())
                && java.lang.reflect.Proxy.getInvocationHandler(args[0]) instanceof TraitInvocationHandler other
                && Objects.equals(node.id(), other.node.id())
                && Objects.equals(traitInterface, other.traitInterface);
            default -> {
                Class<?> returnType = method.getReturnType();
                Optional<String> value = node.property(method.getName());
                if (returnType == Optional.class) {
                    yield value;
                } else if (returnType == String.class) {
                    yield value.orElse(null);
                } else if (returnType == Integer.class) {
                    yield value.map(Integer::valueOf).orElse(null);
                } else if (returnType == Long.class) {
                    yield value.map(Long::valueOf).orElse(null);
                } else if (returnType == Double.class) {
                    yield value.map(Double::valueOf).orElse(null);
                } else {
                    yield value.orElse(null);
                }
            }
        };
    }
}
```

- [ ] **Step 4: Implement TraitProxy**

Use `ide_create_file`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapNode;

import java.lang.reflect.Proxy;

public final class TraitProxy {

    private TraitProxy() {}

    @SuppressWarnings("unchecked")
    public static <T> T as(MindMapNode node, Class<T> traitInterface) {
        if (!traitInterface.isInterface()) {
            throw new IllegalArgumentException(
                "Trait must be an interface: " + traitInterface.getName());
        }
        return (T) Proxy.newProxyInstance(
            traitInterface.getClassLoader(),
            new Class<?>[] { traitInterface },
            new TraitInvocationHandler(node, traitInterface));
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -q`
Expected: All 11 tests PASS (5 rule tests + 6 proxy tests)

- [ ] **Step 6: Run full build for regression**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,mindmap,mindmap-intelligence -q`
Expected: All tests PASS across all three modules

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitProxy.java \
        mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitInvocationHandler.java \
        mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TraitProxyTest.java
git commit -m "feat(#219): TraitProxy — JDK Proxy generation for typed trait access

Refs #219"
```

---

## References

- `specs/mindmap-spi/2026-08-26-mindmap-spi-design.md` §5 — trait system design
- `specs/mindmap-spi/decisions.md` D19-D25 — trait system decisions
- `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/DerivedEdgeDecorator.java` — decorator pattern reference
- `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/DerivedEdgeDecoratorTest.java` — test pattern reference
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeUpdate.java` — traitsToAdd/traitsToRemove API
- GE-20260716-f292d3 — CDI decorator ordering
- GE-20260803-0c691f — JDK Proxy pattern for CDI Instance stubbing
- GitHub #219 — focal issue
- GitHub #213 — epic
