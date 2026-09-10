# Builder APIs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #231 — Builder APIs
**Issue group:** #253, #231

**Goal:** Add `of()` / `empty()` factories and `withX()` methods to 5
record types, eliminating positional-null constructor calls.

**Architecture:** CbrQuery-style immutable record builders — static
factory for required fields, individual `withX()` methods returning new
instances via the canonical constructor. No mutable builders, no new
modules, no new dependencies.

**Tech Stack:** Java 21 records, JUnit 5, AssertJ

## Global Constraints

- Java 21 source on Java 26 JVM
- `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn` for all builds
- Use `ide_insert_member` for adding methods, `ide_replace_member` for modifying
- Each `withX()` calls the canonical constructor — validation fires every time
- Collections default to `null` in `of()` — let compact constructors normalize
- No space parameters (D58)
- Build command: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`

---

## Batch 1: mindmap-api builders (MindMapQuery, NodeInput, EdgeInput, NodeUpdate)

### Task 1: MindMapQuery of() + withX()

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapQuery.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/MindMapQueryTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `MindMapQuery.of(String tenantId, int limit)` factory,
  10 `withX()` methods (withSubgraphId, withText, withEdgeType,
  withTraits, withMinConfidence, withConfidenceOrigin,
  withIncludeSuperseded, withValidAfter, withValidBefore, withUpdatedAfter)

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.HashSet;
import java.util.Set;

import static org.assertj.core.api.Assertions.*;

class MindMapQueryTest {

    @Test
    void of_createsQueryWithDefaults() {
        var q = MindMapQuery.of("t1", 50);
        assertThat(q.tenantId()).isEqualTo("t1");
        assertThat(q.limit()).isEqualTo(50);
        assertThat(q.subgraphId()).isNull();
        assertThat(q.text()).isNull();
        assertThat(q.edgeType()).isNull();
        assertThat(q.traits()).isNull();
        assertThat(q.minConfidence()).isNull();
        assertThat(q.confidenceOrigin()).isNull();
        assertThat(q.includeSuperseded()).isFalse();
        assertThat(q.validAfter()).isNull();
        assertThat(q.validBefore()).isNull();
        assertThat(q.updatedAfter()).isNull();
    }

    @Test
    void of_nullTenantId_throws() {
        assertThatThrownBy(() -> MindMapQuery.of(null, 50))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void of_zeroLimit_throws() {
        assertThatThrownBy(() -> MindMapQuery.of("t1", 0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void withText_returnsNewInstance() {
        var q = MindMapQuery.of("t1", 10);
        var q2 = q.withText("Alice");
        assertThat(q2.text()).isEqualTo("Alice");
        assertThat(q2.tenantId()).isEqualTo("t1");
        assertThat(q.text()).isNull(); // original unchanged
    }

    @Test
    void chaining_setsMultipleFields() {
        var now = Instant.now();
        var q = MindMapQuery.of("t1", 20)
            .withText("search")
            .withSubgraphId("sg1")
            .withMinConfidence(0.5)
            .withValidAfter(now)
            .withIncludeSuperseded(true);
        assertThat(q.text()).isEqualTo("search");
        assertThat(q.subgraphId()).isEqualTo("sg1");
        assertThat(q.minConfidence()).isEqualTo(0.5);
        assertThat(q.validAfter()).isEqualTo(now);
        assertThat(q.includeSuperseded()).isTrue();
    }

    @Test
    void withTraits_defensivelyCopies() {
        var mutable = new HashSet<>(Set.of("person"));
        var q = MindMapQuery.of("t1", 10).withTraits(mutable);
        mutable.add("org");
        assertThat(q.traits()).containsExactly("person");
    }

    @Test
    void withConfidenceOrigin_setsField() {
        var q = MindMapQuery.of("t1", 10)
            .withConfidenceOrigin(ConfidenceOrigin.STATED);
        assertThat(q.confidenceOrigin()).isEqualTo(ConfidenceOrigin.STATED);
    }

    @Test
    void withEdgeType_setsField() {
        var q = MindMapQuery.of("t1", 10).withEdgeType("KNOWS");
        assertThat(q.edgeType()).isEqualTo("KNOWS");
    }

    @Test
    void withValidBefore_setsField() {
        var now = Instant.now();
        var q = MindMapQuery.of("t1", 10).withValidBefore(now);
        assertThat(q.validBefore()).isEqualTo(now);
    }

    @Test
    void withUpdatedAfter_setsField() {
        var now = Instant.now();
        var q = MindMapQuery.of("t1", 10).withUpdatedAfter(now);
        assertThat(q.updatedAfter()).isEqualTo(now);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=MindMapQueryTest`
Expected: compilation failure — `of()` and `withX()` methods don't exist

- [ ] **Step 3: Add of() factory and withX() methods to MindMapQuery**

Use `ide_insert_member` to add to `MindMapQuery.java` after the compact
constructor (line 25):

```java
public static MindMapQuery of(String tenantId, int limit) {
    return new MindMapQuery(tenantId, null, null, null, null,
                            null, null, false, null, null, null, limit);
}

public MindMapQuery withSubgraphId(String subgraphId) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withText(String text) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withEdgeType(String edgeType) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withTraits(Set<String> traits) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withMinConfidence(Double minConfidence) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withConfidenceOrigin(ConfidenceOrigin confidenceOrigin) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withIncludeSuperseded(boolean includeSuperseded) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withValidAfter(Instant validAfter) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withValidBefore(Instant validBefore) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}

public MindMapQuery withUpdatedAfter(Instant updatedAfter) {
    return new MindMapQuery(tenantId, subgraphId, text, edgeType, traits,
                            minConfidence, confidenceOrigin, includeSuperseded,
                            validAfter, validBefore, updatedAfter, limit);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=MindMapQueryTest`
Expected: all 10 tests PASS

- [ ] **Step 5: Run full mindmap-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api`
Expected: all existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapQuery.java \
        mindmap-api/src/test/java/io/casehub/neocortex/mindmap/MindMapQueryTest.java
git commit -m "feat(mindmap-api): MindMapQuery.of() + withX() builders Refs #231"
```

---

### Task 2: NodeInput of() + withX()

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeInput.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/NodeInputTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `NodeInput.of(String name, String subgraphId)` factory,
  12 `withX()` methods (withConfidence, withProvenance, withTraits,
  withRefs, withValidFrom, withValidUntil, withPleasure, withArousal,
  withDominance, withPad, withProperties, withProperty)

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.*;

class NodeInputTest {

    @Test
    void of_createsWithDefaults() {
        var n = NodeInput.of("Alice", "sg1");
        assertThat(n.name()).isEqualTo("Alice");
        assertThat(n.subgraphId()).isEqualTo("sg1");
        assertThat(n.confidence()).isNull();
        assertThat(n.provenance()).isNull();
        assertThat(n.traits()).isEmpty();
        assertThat(n.refs()).isEmpty();
        assertThat(n.validFrom()).isNull();
        assertThat(n.validUntil()).isNull();
        assertThat(n.pleasure()).isNull();
        assertThat(n.arousal()).isNull();
        assertThat(n.dominance()).isNull();
        assertThat(n.properties()).isEmpty();
    }

    @Test
    void of_blankName_throws() {
        assertThatThrownBy(() -> NodeInput.of("", "sg1"))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void of_blankSubgraphId_throws() {
        assertThatThrownBy(() -> NodeInput.of("Alice", ""))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void withConfidence_returnsNewInstance() {
        var n = NodeInput.of("Alice", "sg1");
        var conf = new Confidence(ConfidenceOrigin.STATED, 0.9, null);
        var n2 = n.withConfidence(conf);
        assertThat(n2.confidence()).isEqualTo(conf);
        assertThat(n.confidence()).isNull();
    }

    @Test
    void chaining_setsMultipleFields() {
        var now = Instant.now();
        var n = NodeInput.of("Alice", "sg1")
            .withTraits(Set.of("person"))
            .withProvenance("test")
            .withPad(0.8, 0.3, 0.5)
            .withValidFrom(now);
        assertThat(n.traits()).containsExactly("person");
        assertThat(n.provenance()).isEqualTo("test");
        assertThat(n.pleasure()).isEqualTo(0.8);
        assertThat(n.arousal()).isEqualTo(0.3);
        assertThat(n.dominance()).isEqualTo(0.5);
        assertThat(n.validFrom()).isEqualTo(now);
    }

    @Test
    void withProperty_mergesIntoExisting() {
        var n = NodeInput.of("Alice", "sg1")
            .withProperties(Map.of("k1", "v1"))
            .withProperty("k2", "v2");
        assertThat(n.properties()).containsEntry("k1", "v1")
                                  .containsEntry("k2", "v2");
    }

    @Test
    void withProperties_defensivelyCopies() {
        var mutable = new HashMap<String, String>();
        mutable.put("k", "v");
        var n = NodeInput.of("Alice", "sg1").withProperties(mutable);
        mutable.put("k2", "v2");
        assertThat(n.properties()).hasSize(1);
    }

    @Test
    void withRefs_setsField() {
        var ref = NodeRef.of("github", "123", null);
        var n = NodeInput.of("Alice", "sg1").withRefs(Set.of(ref));
        assertThat(n.refs()).containsExactly(ref);
    }

    @Test
    void withValidUntil_setsField() {
        var future = Instant.now().plusSeconds(3600);
        var n = NodeInput.of("Alice", "sg1").withValidUntil(future);
        assertThat(n.validUntil()).isEqualTo(future);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=NodeInputTest`
Expected: compilation failure

- [ ] **Step 3: Add of() factory and withX() methods to NodeInput**

Use `ide_insert_member` to add after the compact constructor:

```java
public static NodeInput of(String name, String subgraphId) {
    return new NodeInput(name, subgraphId, null, null, null, null,
                         null, null, null, null, null, null);
}

public NodeInput withConfidence(Confidence confidence) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withProvenance(String provenance) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withTraits(Set<String> traits) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withRefs(Set<NodeRef> refs) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withValidFrom(Instant validFrom) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withValidUntil(Instant validUntil) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withPleasure(Double pleasure) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withArousal(Double arousal) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withDominance(Double dominance) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withPad(Double pleasure, Double arousal, Double dominance) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withProperties(Map<String, String> properties) {
    return new NodeInput(name, subgraphId, confidence, provenance, traits, refs,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public NodeInput withProperty(String key, String value) {
    var merged = new java.util.HashMap<>(properties);
    merged.put(key, value);
    return withProperties(merged);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=NodeInputTest`
Expected: all 9 tests PASS

- [ ] **Step 5: Run full mindmap-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeInput.java \
        mindmap-api/src/test/java/io/casehub/neocortex/mindmap/NodeInputTest.java
git commit -m "feat(mindmap-api): NodeInput.of() + withX() builders Refs #231"
```

---

### Task 3: EdgeInput of() + withX()

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/EdgeInput.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/EdgeInputTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `EdgeInput.of(String sourceNodeId, String targetNodeId, String edgeType)` factory,
  10 `withX()` methods (withConfidence, withProvenance, withValidFrom,
  withValidUntil, withPleasure, withArousal, withDominance, withPad,
  withProperties, withProperty)

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class EdgeInputTest {

    @Test
    void of_createsWithDefaults() {
        var e = EdgeInput.of("src", "tgt", "KNOWS");
        assertThat(e.sourceNodeId()).isEqualTo("src");
        assertThat(e.targetNodeId()).isEqualTo("tgt");
        assertThat(e.edgeType()).isEqualTo("KNOWS");
        assertThat(e.confidence()).isNull();
        assertThat(e.provenance()).isNull();
        assertThat(e.validFrom()).isNull();
        assertThat(e.validUntil()).isNull();
        assertThat(e.pleasure()).isNull();
        assertThat(e.arousal()).isNull();
        assertThat(e.dominance()).isNull();
        assertThat(e.properties()).isEmpty();
    }

    @Test
    void of_nullSourceNodeId_throws() {
        assertThatThrownBy(() -> EdgeInput.of(null, "tgt", "KNOWS"))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void withConfidence_returnsNewInstance() {
        var e = EdgeInput.of("src", "tgt", "KNOWS");
        var conf = new Confidence(ConfidenceOrigin.STATED, 0.8, null);
        var e2 = e.withConfidence(conf);
        assertThat(e2.confidence()).isEqualTo(conf);
        assertThat(e.confidence()).isNull();
    }

    @Test
    void chaining_setsMultipleFields() {
        var now = Instant.now();
        var e = EdgeInput.of("src", "tgt", "KNOWS")
            .withProvenance("test")
            .withPad(0.5, 0.3, 0.7)
            .withValidFrom(now);
        assertThat(e.provenance()).isEqualTo("test");
        assertThat(e.pleasure()).isEqualTo(0.5);
        assertThat(e.validFrom()).isEqualTo(now);
    }

    @Test
    void withProperty_mergesIntoExisting() {
        var e = EdgeInput.of("src", "tgt", "KNOWS")
            .withProperties(Map.of("k1", "v1"))
            .withProperty("k2", "v2");
        assertThat(e.properties()).containsEntry("k1", "v1")
                                  .containsEntry("k2", "v2");
    }

    @Test
    void withProperties_defensivelyCopies() {
        var mutable = new HashMap<String, String>();
        mutable.put("k", "v");
        var e = EdgeInput.of("src", "tgt", "KNOWS").withProperties(mutable);
        mutable.put("k2", "v2");
        assertThat(e.properties()).hasSize(1);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=EdgeInputTest`
Expected: compilation failure

- [ ] **Step 3: Add of() factory and withX() methods to EdgeInput**

Use `ide_insert_member` to add after the compact constructor:

```java
public static EdgeInput of(String sourceNodeId, String targetNodeId, String edgeType) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, null, null,
                         null, null, null, null, null, null);
}

public EdgeInput withConfidence(Confidence confidence) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withProvenance(String provenance) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withValidFrom(Instant validFrom) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withValidUntil(Instant validUntil) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withPleasure(Double pleasure) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withArousal(Double arousal) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withDominance(Double dominance) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withPad(Double pleasure, Double arousal, Double dominance) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withProperties(Map<String, String> properties) {
    return new EdgeInput(sourceNodeId, targetNodeId, edgeType, confidence, provenance,
                         validFrom, validUntil, pleasure, arousal, dominance, properties);
}

public EdgeInput withProperty(String key, String value) {
    var merged = new java.util.HashMap<>(properties);
    merged.put(key, value);
    return withProperties(merged);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=EdgeInputTest`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/EdgeInput.java \
        mindmap-api/src/test/java/io/casehub/neocortex/mindmap/EdgeInputTest.java
git commit -m "feat(mindmap-api): EdgeInput.of() + withX() builders Refs #231"
```

---

### Task 4: NodeUpdate empty() + withX()

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeUpdate.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/NodeUpdateTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `NodeUpdate.empty()` factory, 14 `withX()` methods
  (withName, withConfidence, withTraitsToAdd, withTraitsToRemove,
  withRefsToAdd, withRefsToRemove, withValidFrom, withValidUntil,
  withPleasure, withArousal, withDominance, withPad,
  withPropertiesToSet, withPropertiesToRemove)

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.*;

class NodeUpdateTest {

    @Test
    void empty_createsWithDefaults() {
        var u = NodeUpdate.empty();
        assertThat(u.name()).isNull();
        assertThat(u.confidence()).isNull();
        assertThat(u.traitsToAdd()).isEmpty();
        assertThat(u.traitsToRemove()).isEmpty();
        assertThat(u.refsToAdd()).isEmpty();
        assertThat(u.refsToRemove()).isEmpty();
        assertThat(u.validFrom()).isNull();
        assertThat(u.validUntil()).isNull();
        assertThat(u.pleasure()).isNull();
        assertThat(u.arousal()).isNull();
        assertThat(u.dominance()).isNull();
        assertThat(u.propertiesToSet()).isEmpty();
        assertThat(u.propertiesToRemove()).isEmpty();
    }

    @Test
    void withName_returnsNewInstance() {
        var u = NodeUpdate.empty();
        var u2 = u.withName("New Name");
        assertThat(u2.name()).isEqualTo("New Name");
        assertThat(u.name()).isNull();
    }

    @Test
    void chaining_setsMultipleFields() {
        var conf = new Confidence(ConfidenceOrigin.STATED, 0.9, null);
        var u = NodeUpdate.empty()
            .withName("Alice")
            .withConfidence(conf)
            .withTraitsToAdd(Set.of("person"))
            .withPad(0.8, 0.3, 0.5)
            .withPropertiesToSet(Map.of("role", "lead"));
        assertThat(u.name()).isEqualTo("Alice");
        assertThat(u.confidence()).isEqualTo(conf);
        assertThat(u.traitsToAdd()).containsExactly("person");
        assertThat(u.pleasure()).isEqualTo(0.8);
        assertThat(u.propertiesToSet()).containsEntry("role", "lead");
    }

    @Test
    void withTraitsToRemove_setsField() {
        var u = NodeUpdate.empty().withTraitsToRemove(Set.of("old"));
        assertThat(u.traitsToRemove()).containsExactly("old");
    }

    @Test
    void withRefsToAdd_setsField() {
        var ref = NodeRef.of("github", "123", null);
        var u = NodeUpdate.empty().withRefsToAdd(Set.of(ref));
        assertThat(u.refsToAdd()).containsExactly(ref);
    }

    @Test
    void withPropertiesToRemove_setsField() {
        var u = NodeUpdate.empty().withPropertiesToRemove(Set.of("obsolete"));
        assertThat(u.propertiesToRemove()).containsExactly("obsolete");
    }

    @Test
    void withValidFrom_setsField() {
        var now = Instant.now();
        var u = NodeUpdate.empty().withValidFrom(now);
        assertThat(u.validFrom()).isEqualTo(now);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=NodeUpdateTest`
Expected: compilation failure

- [ ] **Step 3: Add empty() factory and withX() methods to NodeUpdate**

Use `ide_insert_member` to add after the compact constructor:

```java
public static NodeUpdate empty() {
    return new NodeUpdate(null, null, Set.of(), Set.of(), Set.of(), Set.of(),
                          null, null, null, null, null, Map.of(), Set.of());
}

public NodeUpdate withName(String name) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withConfidence(Confidence confidence) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withTraitsToAdd(Set<String> traitsToAdd) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withTraitsToRemove(Set<String> traitsToRemove) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withRefsToAdd(Set<NodeRef> refsToAdd) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withRefsToRemove(Set<NodeRef> refsToRemove) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withValidFrom(Instant validFrom) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withValidUntil(Instant validUntil) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withPleasure(Double pleasure) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withArousal(Double arousal) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withDominance(Double dominance) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withPad(Double pleasure, Double arousal, Double dominance) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withPropertiesToSet(Map<String, String> propertiesToSet) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}

public NodeUpdate withPropertiesToRemove(Set<String> propertiesToRemove) {
    return new NodeUpdate(name, confidence, traitsToAdd, traitsToRemove,
                          refsToAdd, refsToRemove, validFrom, validUntil,
                          pleasure, arousal, dominance, propertiesToSet, propertiesToRemove);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=NodeUpdateTest`
Expected: all 7 tests PASS

- [ ] **Step 5: Run full mindmap-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api`
Expected: all tests pass (including existing contract tests)

- [ ] **Step 6: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeUpdate.java \
        mindmap-api/src/test/java/io/casehub/neocortex/mindmap/NodeUpdateTest.java
git commit -m "feat(mindmap-api): NodeUpdate.empty() + withX() builders Refs #231"
```

---

## Batch 2: memory-api builders (MemoryInput completion)

### Task 5: MemoryInput of() + missing withX()

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/MemoryInputTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `MemoryInput.of(String entityId, MemoryDomain domain, String tenantId, String text)` factory,
  `withCaseId(String)`, `withConfidence(Confidence)` (complements existing
  withAttribute, withAttributes, withText, withPad)

- [ ] **Step 1: Write failing tests**

Add to existing `MemoryInputTest.java`:

```java
@Test
void of_createsWithDefaults() {
    var input = MemoryInput.of("e1", DOMAIN, "t1", "hello");
    assertThat(input.entityId()).isEqualTo("e1");
    assertThat(input.domain()).isEqualTo(DOMAIN);
    assertThat(input.tenantId()).isEqualTo("t1");
    assertThat(input.text()).isEqualTo("hello");
    assertThat(input.caseId()).isNull();
    assertThat(input.attributes()).isEmpty();
    assertThat(input.confidence()).isNull();
    assertThat(input.pleasure()).isNull();
    assertThat(input.arousal()).isNull();
    assertThat(input.dominance()).isNull();
}

@Test
void of_nullEntityId_throws() {
    assertThatThrownBy(() -> MemoryInput.of(null, DOMAIN, "t1", "text"))
        .isInstanceOf(NullPointerException.class);
}

@Test
void of_blankText_throws() {
    assertThatThrownBy(() -> MemoryInput.of("e1", DOMAIN, "t1", ""))
        .isInstanceOf(IllegalArgumentException.class);
}

@Test
void withCaseId_returnsNewInstance() {
    var input = MemoryInput.of("e1", DOMAIN, "t1", "text");
    var enriched = input.withCaseId("case-1");
    assertThat(enriched.caseId()).isEqualTo("case-1");
    assertThat(enriched.entityId()).isEqualTo("e1");
    assertThat(input.caseId()).isNull();
}

@Test
void withConfidence_returnsNewInstance() {
    var conf = new io.casehub.neocortex.cognitive.Confidence(
        io.casehub.neocortex.cognitive.ConfidenceOrigin.STATED, 0.9, null);
    var input = MemoryInput.of("e1", DOMAIN, "t1", "text");
    var enriched = input.withConfidence(conf);
    assertThat(enriched.confidence()).isEqualTo(conf);
    assertThat(input.confidence()).isNull();
}

@Test
void of_chainingWithExistingWithers() {
    var input = MemoryInput.of("e1", DOMAIN, "t1", "text")
        .withCaseId("case-1")
        .withAttribute("k", "v")
        .withPad(0.5, 0.3, 0.7);
    assertThat(input.caseId()).isEqualTo("case-1");
    assertThat(input.attributes()).containsEntry("k", "v");
    assertThat(input.pleasure()).isEqualTo(0.5);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MemoryInputTest`
Expected: compilation failure — `of()`, `withCaseId()`, `withConfidence()` don't exist

- [ ] **Step 3: Add of() factory and missing withX() methods to MemoryInput**

Use `ide_insert_member` to add after the existing `withPad` method:

```java
public static MemoryInput of(String entityId, MemoryDomain domain,
                              String tenantId, String text) {
    return new MemoryInput(entityId, domain, tenantId, null, text,
                           Map.of(), null, null, null, null);
}

public MemoryInput withCaseId(String caseId) {
    return new MemoryInput(entityId, domain, tenantId, caseId, text,
                           attributes, confidence, pleasure, arousal, dominance);
}

public MemoryInput withConfidence(Confidence confidence) {
    return new MemoryInput(entityId, domain, tenantId, caseId, text,
                           attributes, confidence, pleasure, arousal, dominance);
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=MemoryInputTest`
Expected: all tests PASS (existing + 6 new)

- [ ] **Step 5: Run full memory-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java \
        memory-api/src/test/java/io/casehub/neocortex/memory/MemoryInputTest.java
git commit -m "feat(memory-api): MemoryInput.of() + withCaseId/withConfidence builders Refs #231"
```

---

## References

- [2026-09-01-builder-apis-design.md] — design spec this plan implements
- CbrQuery.java — proven of() + withX() pattern
- MindMapQuery.java:9-26 — 12-field record, primary pain point
- NodeInput.java:9-33 — 12-field record
- EdgeInput.java:9-29 — 11-field record
- NodeUpdate.java:9-33 — 13-field mutation record
- MemoryInput.java:8-45 — 10-field record, partially done
- MemoryInputTest.java — existing test file to extend
- D58-D61 in decisions.md — design decisions
- GitHub #231 — focal issue
- GitHub #255 — space model rearchitecture (why no space params)
