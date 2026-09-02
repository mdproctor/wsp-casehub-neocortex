# Declarative Rule DSL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #249 — feat: declarative rule DSL — YAML trait rules and derived edge rules
**Issue group:** #253, #249

**Goal:** Implement a declarative condition/action DSL that YAML can express for TraitRule and DerivedEdgeRule, with global rules + per-agent overrides via DeclarativeRuleRegistry.

**Architecture:** `RuleCondition` sealed interface (11 predicates) and `DeclarativeTraitRule` in mindmap-api provide the condition model. `EdgeDerivation`, `TraversalSpec`, and `DeclarativeDerivedEdgeRule` in mindmap-api provide the action model. Jackson YAML deserializers in mindmap-intelligence parse rule files. `DeclarativeRuleRegistry` CDI bean loads global rules and merges with per-agent rules from CognitiveDefaultsRegistry. `DerivedEdgeDecorator` gains `Instance<DeclarativeRuleRegistry>` for combined discovery.

**Tech Stack:** Java 21, Jackson YAML, Quarkus CDI, JUnit 5

## Global Constraints

- Java 21 language level (on Java 26 JVM)
- camelCase for all YAML keys (D65)
- RuleCondition and action types in mindmap-api (zero deps, tier-0)
- Compiler and registry in mindmap-intelligence
- Global rules in `rules/*.yaml`, per-agent rules in `cognitive-profiles/*.yaml`
- Name-based override: agent-local rule with same name suppresses global rule

---

## Batch 1: Condition model — RuleCondition sealed interface + DeclarativeTraitRule

### Task 1: RuleCondition sealed interface with 11 predicates + DeclarativeTraitRule

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RuleCondition.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/DeclarativeTraitRule.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/RuleConditionTest.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/DeclarativeTraitRuleTest.java`

**Interfaces:**
- Consumes: `MindMapNode` (mindmap-api), `MindMapEdge` (mindmap-api), `TraitRule` (mindmap-api), `SubgraphType` (mindmap-api)
- Produces: `RuleCondition` sealed interface with `evaluate(MindMapNode, List<MindMapEdge>) → boolean`, `DeclarativeTraitRule` implementing `TraitRule`

- [ ] **Step 1: Write failing tests for RuleCondition predicates**

```java
package io.casehub.neocortex.mindmap;

import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class RuleConditionTest {

    private static MindMapNode nodeWith(Map<String, String> properties) {
        return new TestNode(properties);
    }

    private static MindMapEdge edgeOf(String type) {
        return new TestEdge(type);
    }

    @Test
    void hasProperty_trueWhenPresent() {
        var cond = new RuleCondition.HasProperty("birthday");
        assertThat(cond.evaluate(nodeWith(Map.of("birthday", "1940-01-01")), List.of())).isTrue();
    }

    @Test
    void hasProperty_falseWhenAbsent() {
        var cond = new RuleCondition.HasProperty("birthday");
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of())).isFalse();
    }

    @Test
    void propertyEquals_trueWhenMatches() {
        var cond = new RuleCondition.PropertyEquals("eventKind", "scheduled");
        assertThat(cond.evaluate(nodeWith(Map.of("eventKind", "scheduled")), List.of())).isTrue();
    }

    @Test
    void propertyEquals_falseWhenDiffers() {
        var cond = new RuleCondition.PropertyEquals("eventKind", "scheduled");
        assertThat(cond.evaluate(nodeWith(Map.of("eventKind", "anticipated")), List.of())).isFalse();
    }

    @Test
    void propertyIn_trueWhenValueInSet() {
        var cond = new RuleCondition.PropertyIn("status", Set.of("ACTIVE", "CONFIRMED"));
        assertThat(cond.evaluate(nodeWith(Map.of("status", "ACTIVE")), List.of())).isTrue();
    }

    @Test
    void propertyIn_falseWhenValueNotInSet() {
        var cond = new RuleCondition.PropertyIn("status", Set.of("ACTIVE", "CONFIRMED"));
        assertThat(cond.evaluate(nodeWith(Map.of("status", "CANCELLED")), List.of())).isFalse();
    }

    @Test
    void notHasProperty_trueWhenAbsent() {
        var cond = new RuleCondition.NotHasProperty("deletedAt");
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of())).isTrue();
    }

    @Test
    void notHasProperty_falseWhenPresent() {
        var cond = new RuleCondition.NotHasProperty("deletedAt");
        assertThat(cond.evaluate(nodeWith(Map.of("deletedAt", "2026-01-01")), List.of())).isFalse();
    }

    @Test
    void hasEdgeType_trueWhenEdgeExists() {
        var cond = new RuleCondition.HasEdgeType("parent-of");
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of(edgeOf("parent-of")))).isTrue();
    }

    @Test
    void hasEdgeType_falseWhenNoMatch() {
        var cond = new RuleCondition.HasEdgeType("parent-of");
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of(edgeOf("works-at")))).isFalse();
    }

    @Test
    void hasEdgeTypes_trueWhenAnyMatch() {
        var cond = new RuleCondition.HasEdgeTypes(Set.of("parent-of", "child-of"));
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of(edgeOf("child-of")))).isTrue();
    }

    @Test
    void hasAnyEdge_trueWhenEdgesExist() {
        var cond = new RuleCondition.HasAnyEdge();
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of(edgeOf("x")))).isTrue();
    }

    @Test
    void hasAnyEdge_falseWhenEmpty() {
        var cond = new RuleCondition.HasAnyEdge();
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of())).isFalse();
    }

    @Test
    void anyOf_trueWhenOneMatches() {
        var cond = new RuleCondition.AnyOf(List.of(
            new RuleCondition.HasProperty("birthday"),
            new RuleCondition.HasEdgeType("parent-of")
        ));
        assertThat(cond.evaluate(nodeWith(Map.of("birthday", "x")), List.of())).isTrue();
    }

    @Test
    void anyOf_falseWhenNoneMatch() {
        var cond = new RuleCondition.AnyOf(List.of(
            new RuleCondition.HasProperty("birthday"),
            new RuleCondition.HasEdgeType("parent-of")
        ));
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of())).isFalse();
    }

    @Test
    void allOf_trueWhenAllMatch() {
        var cond = new RuleCondition.AllOf(List.of(
            new RuleCondition.HasProperty("status"),
            new RuleCondition.HasEdgeType("contributes-to")
        ));
        assertThat(cond.evaluate(
            nodeWith(Map.of("status", "ACTIVE")),
            List.of(edgeOf("contributes-to")))).isTrue();
    }

    @Test
    void allOf_falseWhenOneFails() {
        var cond = new RuleCondition.AllOf(List.of(
            new RuleCondition.HasProperty("status"),
            new RuleCondition.HasEdgeType("contributes-to")
        ));
        assertThat(cond.evaluate(nodeWith(Map.of("status", "ACTIVE")), List.of())).isFalse();
    }

    @Test
    void not_invertsInnerCondition() {
        var cond = new RuleCondition.Not(new RuleCondition.HasProperty("deletedAt"));
        assertThat(cond.evaluate(nodeWith(Map.of()), List.of())).isTrue();
        assertThat(cond.evaluate(nodeWith(Map.of("deletedAt", "x")), List.of())).isFalse();
    }

    @Test
    void nestedCombinators_workCorrectly() {
        var cond = new RuleCondition.AllOf(List.of(
            new RuleCondition.PropertyIn("status", Set.of("ACTIVE", "IN_PROGRESS")),
            new RuleCondition.Not(new RuleCondition.HasProperty("completedAt")),
            new RuleCondition.HasEdgeType("contributes-to")
        ));
        assertThat(cond.evaluate(
            nodeWith(Map.of("status", "ACTIVE")),
            List.of(edgeOf("contributes-to")))).isTrue();
        assertThat(cond.evaluate(
            nodeWith(Map.of("status", "ACTIVE", "completedAt", "2026-01-01")),
            List.of(edgeOf("contributes-to")))).isFalse();
    }
}
```

The test uses `TestNode` and `TestEdge` stubs — simple implementations of MindMapNode/MindMapEdge that are already available in mindmap-api test scope (or create minimal stubs).

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=RuleConditionTest -f pom.xml`
Expected: Compilation failure — `RuleCondition` does not exist.

- [ ] **Step 3: Implement RuleCondition sealed interface**

```java
package io.casehub.neocortex.mindmap;

import java.util.List;
import java.util.Set;

public sealed interface RuleCondition {

    boolean evaluate(MindMapNode node, List<MindMapEdge> edges);

    record HasProperty(String name) implements RuleCondition {
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return node.property(name).isPresent();
        }
    }

    record PropertyEquals(String name, String value) implements RuleCondition {
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return node.property(name).map(value::equals).orElse(false);
        }
    }

    record PropertyIn(String name, Set<String> values) implements RuleCondition {
        public PropertyIn { values = Set.copyOf(values); }
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return node.property(name).map(values::contains).orElse(false);
        }
    }

    record NotHasProperty(String name) implements RuleCondition {
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return node.property(name).isEmpty();
        }
    }

    record HasEdgeType(String edgeType) implements RuleCondition {
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return edges.stream().anyMatch(e -> edgeType.equals(e.edgeType()));
        }
    }

    record HasEdgeTypes(Set<String> edgeTypes) implements RuleCondition {
        public HasEdgeTypes { edgeTypes = Set.copyOf(edgeTypes); }
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return edges.stream().anyMatch(e -> edgeTypes.contains(e.edgeType()));
        }
    }

    record HasAnyEdge() implements RuleCondition {
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return !edges.isEmpty();
        }
    }

    record InSubgraphType(SubgraphType type) implements RuleCondition {
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            // requires subgraph context — evaluated by the trait matching layer
            // which has access to the subgraph type via MindMapStore
            return false;
        }
    }

    record AnyOf(List<RuleCondition> conditions) implements RuleCondition {
        public AnyOf { conditions = List.copyOf(conditions); }
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return conditions.stream().anyMatch(c -> c.evaluate(node, edges));
        }
    }

    record AllOf(List<RuleCondition> conditions) implements RuleCondition {
        public AllOf { conditions = List.copyOf(conditions); }
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return conditions.stream().allMatch(c -> c.evaluate(node, edges));
        }
    }

    record Not(RuleCondition condition) implements RuleCondition {
        public boolean evaluate(MindMapNode node, List<MindMapEdge> edges) {
            return !condition.evaluate(node, edges);
        }
    }
}
```

Note: `InSubgraphType` needs store access — it returns false at the condition level. The trait matching layer (which has store access) can check subgraph type before invoking the condition. Mark as a known limitation in the test.

- [ ] **Step 4: Implement DeclarativeTraitRule**

```java
package io.casehub.neocortex.mindmap;

import java.util.List;
import java.util.Objects;

public record DeclarativeTraitRule(String traitName, RuleCondition when) implements TraitRule {

    public DeclarativeTraitRule {
        Objects.requireNonNull(traitName, "traitName required");
        Objects.requireNonNull(when, "when condition required");
    }

    @Override
    public String traitName() { return traitName; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        return when.evaluate(node, edges);
    }
}
```

- [ ] **Step 5: Write DeclarativeTraitRule test**

```java
package io.casehub.neocortex.mindmap;

import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class DeclarativeTraitRuleTest {

    @Test
    void declarativeRule_matchesLikeProgrammaticPersonable() {
        var rule = new DeclarativeTraitRule("Personable",
            new RuleCondition.AnyOf(List.of(
                new RuleCondition.HasProperty("birthday"),
                new RuleCondition.HasProperty("role"),
                new RuleCondition.HasProperty("email"),
                new RuleCondition.HasProperty("phone"),
                new RuleCondition.HasEdgeTypes(Set.of("parent-of", "child-of", "works-at"))
            )));

        assertThat(rule.traitName()).isEqualTo("Personable");
        assertThat(rule.matches(
            new TestNode(Map.of("birthday", "1940-01-01")), List.of())).isTrue();
        assertThat(rule.matches(
            new TestNode(Map.of()), List.of(new TestEdge("works-at")))).isTrue();
        assertThat(rule.matches(
            new TestNode(Map.of()), List.of())).isFalse();
    }

    @Test
    void declarativeRule_matchesLikeProgrammaticAppointable() {
        var rule = new DeclarativeTraitRule("Appointable",
            new RuleCondition.PropertyEquals("eventKind", "scheduled"));

        assertThat(rule.matches(
            new TestNode(Map.of("eventKind", "scheduled")), List.of())).isTrue();
        assertThat(rule.matches(
            new TestNode(Map.of("eventKind", "anticipated")), List.of())).isFalse();
    }
}
```

- [ ] **Step 6: Create test stubs (TestNode, TestEdge) if they don't exist**

Check if mindmap-api test scope already has stubs. If not, create minimal implementations:

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

record TestNode(Map<String, String> props) implements MindMapNode {
    TestNode(Map<String, String> properties) { this.props = Map.copyOf(properties); }
    public String id() { return "test-id"; }
    public String name() { return "test"; }
    public String subgraphId() { return "sg-1"; }
    public Confidence confidence() { return null; }
    public Set<String> traits() { return Set.of(); }
    public Set<NodeRef> refs() { return Set.of(); }
    public Instant validFrom() { return null; }
    public Instant validUntil() { return null; }
    public Double pleasure() { return null; }
    public Double arousal() { return null; }
    public Double dominance() { return null; }
    public Optional<String> property(String key) { return Optional.ofNullable(props.get(key)); }
    public Map<String, String> properties() { return props; }
    public Instant updatedAt() { return Instant.now(); }
}

record TestEdge(String edgeType) implements MindMapEdge {
    public String id() { return "edge-id"; }
    public String sourceNodeId() { return "src"; }
    public String targetNodeId() { return "tgt"; }
    public Confidence confidence() { return null; }
    public String provenance() { return null; }
    public Instant validFrom() { return null; }
    public Instant validUntil() { return null; }
    public Double pleasure() { return null; }
    public Double arousal() { return null; }
    public Double dominance() { return null; }
    public Map<String, String> properties() { return Map.of(); }
    public Instant updatedAt() { return Instant.now(); }
}
```

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -f pom.xml`
Expected: All tests PASS (existing + ~20 new condition tests + 2 trait rule tests).

- [ ] **Step 8: Commit**

```bash
git add mindmap-api/
git commit -m "feat(mindmap-api): RuleCondition sealed interface + DeclarativeTraitRule

11-predicate condition DSL: hasProperty, propertyEquals, propertyIn,
notHasProperty, hasEdgeType, hasEdgeTypes, hasAnyEdge, inSubgraphType,
anyOf, allOf, not. DeclarativeTraitRule implements TraitRule using
condition evaluation.

Refs #249"
```

---

## Batch 2: Action model — EdgeDerivation + DeclarativeDerivedEdgeRule

### Task 2: Edge derivation types + DeclarativeDerivedEdgeRule with direct and traversal actions

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/EdgeDerivation.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/EdgeRef.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraversalSpec.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/DeclarativeDerivedEdgeRule.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/DeclarativeDerivedEdgeRuleTest.java`

**Interfaces:**
- Consumes: `DerivedEdgeRule` (mindmap-api), `EdgeInput` (mindmap-api), `MindMapStore` (mindmap-api), `MindMapNode`, `MindMapEdge`, `Confidence` (cognitive-api)
- Produces: `EdgeDerivation(edgeType, source, target, confidence, properties)`, `EdgeRef` enum (`TRIGGER_SOURCE, TRIGGER_TARGET, TRAVERSAL_NODE`), `TraversalSpec(follow, from, direction, maxDepth)`, `DeclarativeDerivedEdgeRule` implementing `DerivedEdgeRule`

- [ ] **Step 1: Write failing tests for direct derivation (Level 1)**

```java
package io.casehub.neocortex.mindmap;

import java.util.List;
import java.util.Map;
import java.util.Set;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class DeclarativeDerivedEdgeRuleTest {

    @Test
    void directDerivation_inverseEdge() {
        var rule = new DeclarativeDerivedEdgeRule(
            "inverse-knows",
            Set.of("knows"),
            null,
            List.of(new EdgeDerivation("known-by",
                EdgeRef.TRIGGER_TARGET, EdgeRef.TRIGGER_SOURCE,
                null, Map.of())));

        var trigger = new TestEdge("knows") {
            @Override public String sourceNodeId() { return "alice"; }
            @Override public String targetNodeId() { return "bob"; }
        };
        var sourceNode = new TestNode(Map.of());

        var derived = rule.derive(sourceNode, trigger, null);

        assertThat(derived).hasSize(1);
        assertThat(derived.get(0).edgeType()).isEqualTo("known-by");
        assertThat(derived.get(0).sourceNodeId()).isEqualTo("bob");
        assertThat(derived.get(0).targetNodeId()).isEqualTo("alice");
    }

    @Test
    void directDerivation_nonMatchingTrigger_returnsEmpty() {
        var rule = new DeclarativeDerivedEdgeRule(
            "inverse-knows",
            Set.of("knows"),
            null,
            List.of(new EdgeDerivation("known-by",
                EdgeRef.TRIGGER_TARGET, EdgeRef.TRIGGER_SOURCE,
                null, Map.of())));

        var trigger = new TestEdge("works-with") {
            @Override public String sourceNodeId() { return "alice"; }
            @Override public String targetNodeId() { return "bob"; }
        };

        var derived = rule.derive(new TestNode(Map.of()), trigger, null);
        assertThat(derived).isEmpty();
    }

    @Test
    void directDerivation_withProperties() {
        var rule = new DeclarativeDerivedEdgeRule(
            "bidi-colleague",
            Set.of("works-with"),
            null,
            List.of(new EdgeDerivation("works-with",
                EdgeRef.TRIGGER_TARGET, EdgeRef.TRIGGER_SOURCE,
                null, Map.of("derived-reason", "bidirectional"))));

        var trigger = new TestEdge("works-with") {
            @Override public String sourceNodeId() { return "alice"; }
            @Override public String targetNodeId() { return "bob"; }
        };

        var derived = rule.derive(new TestNode(Map.of()), trigger, null);
        assertThat(derived).hasSize(1);
        assertThat(derived.get(0).properties()).containsEntry("derived-reason", "bidirectional");
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=DeclarativeDerivedEdgeRuleTest -f pom.xml`
Expected: Compilation failure.

- [ ] **Step 3: Implement EdgeRef, EdgeDerivation, TraversalSpec**

```java
// EdgeRef.java
package io.casehub.neocortex.mindmap;

public enum EdgeRef {
    TRIGGER_SOURCE, TRIGGER_TARGET, TRAVERSAL_NODE
}

// EdgeDerivation.java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import java.util.Map;
import java.util.Objects;

public record EdgeDerivation(
    String edgeType,
    EdgeRef source,
    EdgeRef target,
    Confidence confidence,
    Map<String, String> properties
) {
    public EdgeDerivation {
        Objects.requireNonNull(edgeType, "edgeType required");
        Objects.requireNonNull(source, "source required");
        Objects.requireNonNull(target, "target required");
        properties = properties != null ? Map.copyOf(properties) : Map.of();
    }
}

// TraversalSpec.java
package io.casehub.neocortex.mindmap;

import java.util.Objects;

public record TraversalSpec(
    String follow,
    EdgeRef from,
    TraversalDirection direction,
    int maxDepth
) {
    public enum TraversalDirection { OUTBOUND, INBOUND }

    public TraversalSpec {
        Objects.requireNonNull(follow, "follow edge type required");
        Objects.requireNonNull(from, "from reference required");
        Objects.requireNonNull(direction, "direction required");
        if (maxDepth < 1) throw new IllegalArgumentException("maxDepth must be >= 1");
    }
}
```

- [ ] **Step 4: Implement DeclarativeDerivedEdgeRule**

```java
package io.casehub.neocortex.mindmap;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public record DeclarativeDerivedEdgeRule(
    String name,
    Set<String> triggerEdgeTypes,
    TraversalSpec traverse,
    List<EdgeDerivation> derivations
) implements DerivedEdgeRule {

    public DeclarativeDerivedEdgeRule {
        Objects.requireNonNull(name, "name required");
        triggerEdgeTypes = Set.copyOf(triggerEdgeTypes);
        derivations = List.copyOf(derivations);
    }

    @Override
    public String name() { return name; }

    @Override
    public List<EdgeInput> derive(MindMapNode sourceNode, MindMapEdge trigger,
                                   MindMapStore store) {
        if (!triggerEdgeTypes.contains(trigger.edgeType())) {
            return List.of();
        }
        if (traverse == null) {
            return deriveDirect(trigger);
        }
        return deriveWithTraversal(trigger, store);
    }

    private List<EdgeInput> deriveDirect(MindMapEdge trigger) {
        List<EdgeInput> result = new ArrayList<>();
        for (EdgeDerivation d : derivations) {
            String src = resolveRef(d.source(), trigger, null);
            String tgt = resolveRef(d.target(), trigger, null);
            result.add(new EdgeInput(src, tgt, d.edgeType(),
                d.confidence(), null, null, null, null, null, null, d.properties()));
        }
        return result;
    }

    private List<EdgeInput> deriveWithTraversal(MindMapEdge trigger, MindMapStore store) {
        if (store == null) return List.of();
        String startNodeId = resolveRef(traverse.from(), trigger, null);
        List<EdgeInput> result = new ArrayList<>();
        walkGraph(store, startNodeId, trigger, traverse.maxDepth(), result,
            new java.util.HashSet<>());
        return result;
    }

    private void walkGraph(MindMapStore store, String currentNodeId,
            MindMapEdge trigger, int remainingDepth, List<EdgeInput> result,
            Set<String> visited) {
        if (remainingDepth <= 0 || !visited.add(currentNodeId)) return;

        String tenantId = inferTenantId(store, trigger);
        List<MindMapEdge> neighbors = store.neighbors(currentNodeId, tenantId);
        for (MindMapEdge edge : neighbors) {
            boolean matchesType = traverse.follow().equals(edge.edgeType());
            if (!matchesType) continue;

            String nextNodeId;
            if (traverse.direction() == TraversalSpec.TraversalDirection.OUTBOUND) {
                if (!edge.sourceNodeId().equals(currentNodeId)) continue;
                nextNodeId = edge.targetNodeId();
            } else {
                if (!edge.targetNodeId().equals(currentNodeId)) continue;
                nextNodeId = edge.sourceNodeId();
            }

            for (EdgeDerivation d : derivations) {
                String src = resolveRef(d.source(), trigger, nextNodeId);
                String tgt = resolveRef(d.target(), trigger, nextNodeId);
                result.add(new EdgeInput(src, tgt, d.edgeType(),
                    d.confidence(), null, null, null, null, null, null, d.properties()));
            }

            walkGraph(store, nextNodeId, trigger, remainingDepth - 1, result, visited);
        }
    }

    private static String resolveRef(EdgeRef ref, MindMapEdge trigger, String traversalNode) {
        return switch (ref) {
            case TRIGGER_SOURCE -> trigger.sourceNodeId();
            case TRIGGER_TARGET -> trigger.targetNodeId();
            case TRAVERSAL_NODE -> {
                if (traversalNode == null)
                    throw new IllegalStateException("TRAVERSAL_NODE used without traverse block");
                yield traversalNode;
            }
        };
    }

    private static String inferTenantId(MindMapStore store, MindMapEdge trigger) {
        // DerivedEdgeDecorator passes tenantId via addEdge — the store
        // context is already tenant-scoped. Return empty string as fallback.
        return "";
    }
}
```

Note: `inferTenantId` is a limitation — the DerivedEdgeRule interface doesn't receive tenantId. The store is already tenant-scoped by the DerivedEdgeDecorator's addEdge context. File a follow-up if this becomes an issue.

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -f pom.xml`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add mindmap-api/
git commit -m "feat(mindmap-api): EdgeDerivation + DeclarativeDerivedEdgeRule with traversal

Two-level derived edge actions: Level 1 (direct flip/inverse),
Level 2 (graph traversal via TraversalSpec for transitive closure).
Implements DerivedEdgeRule — programmatic and declarative rules coexist.

Refs #249"
```

---

## Batch 3: YAML deserializers + DeclarativeRuleRegistry + integration

### Task 3: YAML parsing, DeclarativeRuleRegistry, DerivedEdgeDecorator modification, CognitiveDefaults extension

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/RuleConditionDeserializer.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/DeclarativeRuleRegistry.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/RuleConditionDeserializerTest.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/DeclarativeRuleRegistryTest.java`
- Create: `mindmap-intelligence/src/test/resources/rules/test-rules.yaml`
- Modify: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/DerivedEdgeDecorator.java` — add `Instance<DeclarativeRuleRegistry>`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java` — add traitRules + derivedEdgeRules fields
- Modify: `cognitive-index/src/test/resources/cognitive-profiles/alice.yaml` — add rules sections
- Modify: `CLAUDE.md` — update module descriptions

**Interfaces:**
- Consumes: `RuleCondition` (mindmap-api), `DeclarativeTraitRule` (mindmap-api), `DeclarativeDerivedEdgeRule` (mindmap-api), `CognitiveDefaultsRegistry` (cognitive-index), `DerivedEdgeDecorator` (mindmap)
- Produces: `RuleConditionDeserializer`, `DeclarativeRuleRegistry`, modified `DerivedEdgeDecorator`

- [ ] **Step 1: Create test rules YAML file**

`mindmap-intelligence/src/test/resources/rules/test-rules.yaml`:
```yaml
traitRules:
  - trait: Personable
    when:
      anyOf:
        - hasProperty: birthday
        - hasProperty: role
        - hasEdgeTypes: [parent-of, child-of]

  - trait: Appointable
    when:
      propertyEquals:
        eventKind: scheduled

derivedEdgeRules:
  - name: inverse-knows
    on:
      edgeType: knows
    derive:
      - edgeType: known-by
        source: trigger.target
        target: trigger.source

  - name: descendant-chain
    on:
      edgeType: child-of
    traverse:
      follow: child-of
      from: trigger.target
      direction: outbound
      maxDepth: 3
    derive:
      - edgeType: descendant-of
        source: trigger.source
        target: traversal.node
```

- [ ] **Step 2: Write RuleConditionDeserializer + tests**

The deserializer reads a YAML mapping and dispatches based on the key name. Single-key mappings (`hasProperty: name`) produce leaf predicates. Combinator keys (`anyOf`, `allOf`) produce nested conditions.

```java
package io.casehub.neocortex.mindmap.intelligence;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.deser.std.StdDeserializer;
import io.casehub.neocortex.mindmap.RuleCondition;
import java.io.IOException;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class RuleConditionDeserializer extends StdDeserializer<RuleCondition> {

    public RuleConditionDeserializer() { super(RuleCondition.class); }

    @Override
    public RuleCondition deserialize(JsonParser p, DeserializationContext ctx)
            throws IOException {
        JsonNode node = p.getCodec().readTree(p);
        return parseCondition(node);
    }

    RuleCondition parseCondition(JsonNode node) {
        if (node.has("hasProperty"))
            return new RuleCondition.HasProperty(node.get("hasProperty").asText());
        if (node.has("notHasProperty"))
            return new RuleCondition.NotHasProperty(node.get("notHasProperty").asText());
        if (node.has("propertyEquals")) {
            var obj = node.get("propertyEquals");
            var entry = obj.fields().next();
            return new RuleCondition.PropertyEquals(entry.getKey(), entry.getValue().asText());
        }
        if (node.has("propertyIn")) {
            var obj = node.get("propertyIn");
            var entry = obj.fields().next();
            Set<String> values = new HashSet<>();
            entry.getValue().forEach(v -> values.add(v.asText()));
            return new RuleCondition.PropertyIn(entry.getKey(), values);
        }
        if (node.has("hasEdgeType"))
            return new RuleCondition.HasEdgeType(node.get("hasEdgeType").asText());
        if (node.has("hasEdgeTypes")) {
            Set<String> types = new HashSet<>();
            node.get("hasEdgeTypes").forEach(v -> types.add(v.asText()));
            return new RuleCondition.HasEdgeTypes(types);
        }
        if (node.has("hasAnyEdge"))
            return new RuleCondition.HasAnyEdge();
        if (node.has("anyOf")) {
            List<RuleCondition> conditions = new ArrayList<>();
            node.get("anyOf").forEach(c -> conditions.add(parseCondition(c)));
            return new RuleCondition.AnyOf(conditions);
        }
        if (node.has("allOf")) {
            List<RuleCondition> conditions = new ArrayList<>();
            node.get("allOf").forEach(c -> conditions.add(parseCondition(c)));
            return new RuleCondition.AllOf(conditions);
        }
        if (node.has("not"))
            return new RuleCondition.Not(parseCondition(node.get("not")));
        throw new IllegalArgumentException("Unknown condition: " + node);
    }
}
```

- [ ] **Step 3: Write full YAML rules file deserializer and DeclarativeRuleRegistry**

The registry loads rules from YAML files using a combined deserializer module. It merges global rules with per-agent rules from CognitiveDefaultsRegistry.

See spec §5 for the full implementation. The registry uses `Instance<CognitiveDefaultsRegistry>` for graceful degradation.

- [ ] **Step 4: Modify DerivedEdgeDecorator to accept registry**

Use `ide_replace_member` to update the CDI constructor:

```java
@Inject
public DerivedEdgeDecorator(@Delegate @Any MindMapStore delegate,
                            Instance<DerivedEdgeRule> rules,
                            Instance<DeclarativeRuleRegistry> registry) {
    List<DerivedEdgeRule> allRules = new ArrayList<>(rules.stream().toList());
    if (registry.isResolvable()) {
        allRules.addAll(registry.get().derivedEdgeRules(null));
    }
    this.rules = List.copyOf(allRules);
    this.maxDepth = DEFAULT_MAX_DEPTH;
}
```

The existing test constructor (no CDI) remains unchanged.

- [ ] **Step 5: Extend CognitiveDefaults with rule fields**

Add two nullable fields to CognitiveDefaults record:

```java
public record CognitiveDefaults(
    String agentId,
    String tenantId,
    PersonalityWeights personality,
    MoodBaseline moodBaseline,
    CuriosityConfig curiosity,
    TemporalFocusConfig temporalFocus,
    MindMapVocabulary vocabulary,
    Map<String, String> services,
    List<DeclarativeTraitRule> traitRules,
    List<DeclarativeDerivedEdgeRule> derivedEdgeRules
) { ... }
```

Update CognitiveDefaultsRegistry's ObjectMapper to register RuleCondition deserializer.

- [ ] **Step 6: Write integration tests**

Test the full path: YAML rules file → parse → DeclarativeRuleRegistry → trait matching + derived edge creation.

- [ ] **Step 7: Run all affected test suites**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,mindmap-intelligence,mindmap,cognitive-index -f pom.xml`
Expected: All tests PASS.

- [ ] **Step 8: Verify full reactor build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests -f pom.xml`
Expected: BUILD SUCCESS.

- [ ] **Step 9: Update CLAUDE.md**

Add to mindmap-api: `RuleCondition (sealed interface — 11 structural predicates for declarative trait rules), DeclarativeTraitRule (TraitRule implementation backed by RuleCondition evaluation), EdgeDerivation + EdgeRef + TraversalSpec (derived edge action model), DeclarativeDerivedEdgeRule (DerivedEdgeRule implementation — direct flip + graph traversal)`.

Add to mindmap-intelligence: `DeclarativeRuleRegistry (@ApplicationScoped — loads global rules from rules/*.yaml + per-agent overrides from cognitive profiles, name-based override merge), RuleConditionDeserializer (Jackson YAML → RuleCondition tree)`.

- [ ] **Step 10: Commit**

```bash
git add mindmap-api/ mindmap-intelligence/ mindmap/ cognitive-index/ CLAUDE.md
git commit -m "feat(mindmap): declarative rule DSL — YAML trait rules + derived edge rules

RuleConditionDeserializer parses YAML conditions into RuleCondition trees.
DeclarativeRuleRegistry loads global rules + per-agent overrides with
name-based merge. DerivedEdgeDecorator gains Instance<DeclarativeRuleRegistry>
for combined programmatic + declarative rule discovery.

Closes #249"
```

---

## References

- `specs/issue-253-cognitive-rearchitecture/2026-09-02-declarative-rule-dsl-design.md` — design spec
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraitRule.java` — trait rule interface
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/DerivedEdgeRule.java` — derived edge rule interface
- `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/DerivedEdgeDecorator.java` — rule execution decorator
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/PersonableTraitRule.java` — programmatic trait rule pattern
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java` — cognitive config record
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistry.java` — YAML loading registry
- GitHub #249 — focal issue
- GitHub #253 — parent epic
