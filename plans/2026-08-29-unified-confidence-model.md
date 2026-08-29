# Unified Confidence Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #229 — Unified confidence model
**Issue group:** #253, #229, #232, #234, #235, #236, #237, #238, #239, #241, #242, #244, #243, #245, #230, #233, #240, #252, #231, #246, #247, #248, #249, #250, #251

**Goal:** Replace three incompatible confidence representations (MindMap ConfidenceOrigin+double, Memory Double importance, CBR Double confidence+CbrOutcome EMA) with a single shared `Confidence` record in a new `cognitive-api` module.

**Architecture:** New tier-0 `cognitive-api` module (zero deps, pure Java) provides `ConfidenceOrigin` (moved from mindmap-api, +UNKNOWN, -initialConfidence()) and `Confidence(origin, value, decayReference)`. Both `mindmap-api` and `memory-api` depend on it. Each store subsystem (MindMap, Memory, CBR) migrates its split fields to the unified record. Breaking changes throughout — pre-release platform.

**Tech Stack:** Java 21, Maven multi-module, Flyway (SQLite + PostgreSQL), Qdrant gRPC

## Global Constraints

- Java 21 language features (records, sealed, pattern matching)
- JVM 26 runtime
- All validation uses NaN-safe inverted range check: `!(value >= 0.0 && value <= 1.0)`
- `ConfidenceOrigin` is non-nullable on `Confidence` — use `UNKNOWN` for absent provenance
- MindMap factories (`stated`/`inferred`/`speculated`) enforce non-null `decayReference`
- `Confidence.unknown(value)` returns null `decayReference` (no decay for Memory/CBR)
- Use `ide_*` tools for all Java source operations. Bash only for non-code files.
- Build specific modules during migration: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <modules>`

---

## Batch 1: Foundation — cognitive-api module

### Task 1: Create cognitive-api module with Confidence and ConfidenceOrigin

**Files:**
- Create: `cognitive-api/pom.xml`
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/ConfidenceOrigin.java`
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/Confidence.java`
- Create: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/ConfidenceOriginTest.java`
- Create: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/ConfidenceTest.java`
- Modify: `pom.xml` (parent — add module + dependency management)

**Interfaces:**
- Produces: `io.casehub.neocortex.cognitive.ConfidenceOrigin` (enum: STATED, INFERRED, SPECULATED, UNKNOWN)
- Produces: `io.casehub.neocortex.cognitive.Confidence` (record: origin, value, decayReference; factories: stated, inferred, speculated, unknown; transformers: withValue, withDecayReference)

- [ ] **Step 1: Create pom.xml for cognitive-api module**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>1.0.0-SNAPSHOT</version>
    </parent>
    <artifactId>casehub-neocortex-cognitive-api</artifactId>
    <name>CaseHub Neocortex Cognitive API</name>
    <description>Cross-cutting cognitive types shared by MindMap, Memory, and CBR subsystems</description>
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
    </dependencies>
</project>
```

- [ ] **Step 2: Add cognitive-api to parent pom.xml**

In the parent `pom.xml`, add `<module>cognitive-api</module>` after `fusion-api` and before `rag-api`. Add dependency management entry:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-cognitive-api</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Write ConfidenceOrigin enum**

```java
package io.casehub.neocortex.cognitive;

public enum ConfidenceOrigin {
    STATED,
    INFERRED,
    SPECULATED,
    UNKNOWN
}
```

- [ ] **Step 4: Write ConfidenceOrigin test**

```java
package io.casehub.neocortex.cognitive;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class ConfidenceOriginTest {
    @Test void allValuesPresent() {
        assertThat(ConfidenceOrigin.values()).containsExactly(
            ConfidenceOrigin.STATED, ConfidenceOrigin.INFERRED,
            ConfidenceOrigin.SPECULATED, ConfidenceOrigin.UNKNOWN);
    }

    @Test void valueOfRoundTrips() {
        for (ConfidenceOrigin origin : ConfidenceOrigin.values()) {
            assertThat(ConfidenceOrigin.valueOf(origin.name())).isEqualTo(origin);
        }
    }
}
```

- [ ] **Step 5: Write Confidence record**

```java
package io.casehub.neocortex.cognitive;

import java.time.Instant;
import java.util.Objects;

public record Confidence(
    ConfidenceOrigin origin,
    double value,
    Instant decayReference
) {
    public Confidence {
        Objects.requireNonNull(origin, "origin required");
        if (!(value >= 0.0 && value <= 1.0)) {
            throw new IllegalArgumentException("value must be in [0,1], got: " + value);
        }
    }

    public static Confidence stated(double value, Instant decayReference) {
        Objects.requireNonNull(decayReference, "MindMap confidences require a decayReference");
        return new Confidence(ConfidenceOrigin.STATED, value, decayReference);
    }

    public static Confidence inferred(double value, Instant decayReference) {
        Objects.requireNonNull(decayReference, "MindMap confidences require a decayReference");
        return new Confidence(ConfidenceOrigin.INFERRED, value, decayReference);
    }

    public static Confidence speculated(double value, Instant decayReference) {
        Objects.requireNonNull(decayReference, "MindMap confidences require a decayReference");
        return new Confidence(ConfidenceOrigin.SPECULATED, value, decayReference);
    }

    public static Confidence unknown(double value) {
        return new Confidence(ConfidenceOrigin.UNKNOWN, value, null);
    }

    public Confidence withValue(double newValue) {
        return new Confidence(origin, newValue, decayReference);
    }

    public Confidence withDecayReference(Instant newRef) {
        return new Confidence(origin, value, newRef);
    }
}
```

- [ ] **Step 6: Write Confidence test**

```java
package io.casehub.neocortex.cognitive;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import java.time.Instant;
import static org.assertj.core.api.Assertions.*;

class ConfidenceTest {

    @Test void constructorStoresFields() {
        var now = Instant.now();
        var c = new Confidence(ConfidenceOrigin.STATED, 0.8, now);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.STATED);
        assertThat(c.value()).isEqualTo(0.8);
        assertThat(c.decayReference()).isEqualTo(now);
    }

    @Test void nullOriginThrows() {
        assertThatNullPointerException()
            .isThrownBy(() -> new Confidence(null, 0.5, null));
    }

    @ParameterizedTest
    @ValueSource(doubles = {-0.001, 1.001, -1.0, 2.0})
    void outOfRangeThrows(double v) {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new Confidence(ConfidenceOrigin.STATED, v, null));
    }

    @Test void nanThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new Confidence(ConfidenceOrigin.STATED, Double.NaN, null));
    }

    @Test void boundaryValuesAccepted() {
        assertThatNoException().isThrownBy(() -> new Confidence(ConfidenceOrigin.STATED, 0.0, null));
        assertThatNoException().isThrownBy(() -> new Confidence(ConfidenceOrigin.STATED, 1.0, null));
    }

    @Test void infinityThrows() {
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new Confidence(ConfidenceOrigin.STATED, Double.POSITIVE_INFINITY, null));
        assertThatIllegalArgumentException()
            .isThrownBy(() -> new Confidence(ConfidenceOrigin.STATED, Double.NEGATIVE_INFINITY, null));
    }

    @Test void statedFactoryEnforcesDecayReference() {
        var now = Instant.now();
        var c = Confidence.stated(1.0, now);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.STATED);
        assertThat(c.value()).isEqualTo(1.0);
        assertThat(c.decayReference()).isEqualTo(now);
    }

    @Test void statedFactoryNullDecayReferenceThrows() {
        assertThatNullPointerException()
            .isThrownBy(() -> Confidence.stated(1.0, null));
    }

    @Test void inferredFactoryEnforcesDecayReference() {
        var now = Instant.now();
        var c = Confidence.inferred(0.7, now);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.INFERRED);
        assertThatNullPointerException()
            .isThrownBy(() -> Confidence.inferred(0.7, null));
    }

    @Test void speculatedFactoryEnforcesDecayReference() {
        var now = Instant.now();
        var c = Confidence.speculated(0.3, now);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.SPECULATED);
        assertThatNullPointerException()
            .isThrownBy(() -> Confidence.speculated(0.3, null));
    }

    @Test void unknownFactoryNullDecayReference() {
        var c = Confidence.unknown(0.5);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.UNKNOWN);
        assertThat(c.value()).isEqualTo(0.5);
        assertThat(c.decayReference()).isNull();
    }

    @Test void withValuePreservesOtherFields() {
        var now = Instant.now();
        var c = Confidence.stated(1.0, now).withValue(0.5);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.STATED);
        assertThat(c.value()).isEqualTo(0.5);
        assertThat(c.decayReference()).isEqualTo(now);
    }

    @Test void withDecayReferencePreservesOtherFields() {
        var now = Instant.now();
        var later = now.plusSeconds(3600);
        var c = Confidence.stated(0.8, now).withDecayReference(later);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.STATED);
        assertThat(c.value()).isEqualTo(0.8);
        assertThat(c.decayReference()).isEqualTo(later);
    }

    @Test void nullDecayReferenceAllowedOnConstructor() {
        var c = new Confidence(ConfidenceOrigin.UNKNOWN, 0.5, null);
        assertThat(c.decayReference()).isNull();
    }

    @Test void recordEquality() {
        var now = Instant.now();
        var a = Confidence.stated(0.8, now);
        var b = Confidence.stated(0.8, now);
        assertThat(a).isEqualTo(b);
        assertThat(a.hashCode()).isEqualTo(b.hashCode());
    }
}
```

- [ ] **Step 7: Build and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognitive-api`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 8: Commit**

```
git add cognitive-api/ pom.xml
git commit -m "feat(cognitive-api): unified Confidence record + ConfidenceOrigin enum

New tier-0 module with zero dependencies. ConfidenceOrigin moved from
mindmap-api with UNKNOWN added, initialConfidence() removed. Confidence
record with NaN-safe validation and decay-aware factory methods.

Refs #229"
```

---

## Batch 2: MindMap SPI + core backend migration

### Task 2: Migrate mindmap-api interfaces and InMemoryMindMapStore

**Files:**
- Modify: `mindmap-api/pom.xml` (add cognitive-api dependency)
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapEdge.java`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeInput.java`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/EdgeInput.java`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeUpdate.java`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapQuery.java` (import only)
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapConfidenceDefaults.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/MindMapConfidenceDefaultsTest.java`
- Delete: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ConfidenceOrigin.java` (moved to cognitive-api)
- Modify: `mindmap-inmem/src/main/java/io/casehub/neocortex/mindmap/inmem/InMemoryMindMapStore.java`
- Modify: `mindmap-testing/src/main/java/io/casehub/neocortex/mindmap/testing/MindMapStoreContractTest.java`

**Interfaces:**
- Consumes: `io.casehub.neocortex.cognitive.Confidence`, `io.casehub.neocortex.cognitive.ConfidenceOrigin`
- Produces: Updated `MindMapNode.confidence()` → `Confidence`, removed `confidenceOrigin()` and `confirmedAt()`; `MindMapEdge.confidence()` → `Confidence`, removed `confidenceOrigin()`; `MindMapConfidenceDefaults.defaultValue(origin)`, `MindMapConfidenceDefaults.forOrigin(origin, decayRef)`

- [ ] **Step 1: Add cognitive-api dependency to mindmap-api pom.xml**

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-cognitive-api</artifactId>
</dependency>
```

- [ ] **Step 2: Delete old ConfidenceOrigin from mindmap-api**

Use `ide_refactor_safe_delete` on `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ConfidenceOrigin.java`. This will show compilation errors — expected, we're replacing it with the cognitive-api version.

- [ ] **Step 3: Create MindMapConfidenceDefaults**

Use `ide_create_file`:

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import java.time.Instant;

public final class MindMapConfidenceDefaults {

    private MindMapConfidenceDefaults() {}

    public static double defaultValue(ConfidenceOrigin origin) {
        return switch (origin) {
            case STATED -> 1.0;
            case INFERRED -> 0.7;
            case SPECULATED -> 0.3;
            case UNKNOWN -> 1.0;
        };
    }

    public static Confidence forOrigin(ConfidenceOrigin origin, Instant decayReference) {
        return switch (origin) {
            case STATED -> Confidence.stated(defaultValue(origin), decayReference);
            case INFERRED -> Confidence.inferred(defaultValue(origin), decayReference);
            case SPECULATED -> Confidence.speculated(defaultValue(origin), decayReference);
            case UNKNOWN -> Confidence.unknown(defaultValue(origin));
        };
    }
}
```

- [ ] **Step 4: Write MindMapConfidenceDefaults test**

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import static org.assertj.core.api.Assertions.*;

class MindMapConfidenceDefaultsTest {

    @Test void statedDefaultsTo1() {
        assertThat(MindMapConfidenceDefaults.defaultValue(ConfidenceOrigin.STATED)).isEqualTo(1.0);
    }
    @Test void inferredDefaultsTo07() {
        assertThat(MindMapConfidenceDefaults.defaultValue(ConfidenceOrigin.INFERRED)).isEqualTo(0.7);
    }
    @Test void speculatedDefaultsTo03() {
        assertThat(MindMapConfidenceDefaults.defaultValue(ConfidenceOrigin.SPECULATED)).isEqualTo(0.3);
    }
    @Test void unknownDefaultsTo1() {
        assertThat(MindMapConfidenceDefaults.defaultValue(ConfidenceOrigin.UNKNOWN)).isEqualTo(1.0);
    }

    @Test void forOriginStated_enforcesDecayReference() {
        var now = Instant.now();
        var c = MindMapConfidenceDefaults.forOrigin(ConfidenceOrigin.STATED, now);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.STATED);
        assertThat(c.value()).isEqualTo(1.0);
        assertThat(c.decayReference()).isEqualTo(now);
    }

    @Test void forOriginStated_nullDecayReferenceThrows() {
        assertThatNullPointerException()
            .isThrownBy(() -> MindMapConfidenceDefaults.forOrigin(ConfidenceOrigin.STATED, null));
    }

    @Test void forOriginUnknown_nullDecayReferenceAccepted() {
        var c = MindMapConfidenceDefaults.forOrigin(ConfidenceOrigin.UNKNOWN, null);
        assertThat(c.origin()).isEqualTo(ConfidenceOrigin.UNKNOWN);
        assertThat(c.decayReference()).isNull();
    }
}
```

- [ ] **Step 5: Migrate MindMapNode interface**

Replace the interface body with:

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

public interface MindMapNode {
    String id();
    String name();
    String subgraphId();
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
}
```

Removed: `confidenceOrigin()`, `confirmedAt()`. Changed: `confidence()` returns `Confidence`.

- [ ] **Step 6: Migrate MindMapEdge interface**

Replace the interface body — remove `confidenceOrigin()`, change `confidence()` to return `Confidence`:

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;

public interface MindMapEdge {
    String id();
    String sourceNodeId();
    String targetNodeId();
    String edgeType();
    ValidationTier tier();
    Confidence confidence();
    String provenance();
    Instant createdAt();
    Instant updatedAt();
    Instant validFrom();
    Instant validUntil();
    Double pleasure();
    Double arousal();
    Double dominance();
    Optional<String> property(String key);
    Map<String, String> properties();
}
```

- [ ] **Step 7: Migrate NodeInput record**

Replace `ConfidenceOrigin confidenceOrigin, Double confidence` with `Confidence confidence` (nullable):

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import java.time.Instant;
import java.util.Map;
import java.util.Set;

public record NodeInput(
    String name,
    String subgraphId,
    Confidence confidence,
    String provenance,
    Set<String> traits,
    Set<NodeRef> refs,
    Instant validFrom,
    Instant validUntil,
    Double pleasure,
    Double arousal,
    Double dominance,
    Map<String, String> properties
) {
    public NodeInput {
        if (name == null || name.isBlank())
            throw new IllegalArgumentException("name must not be blank");
        if (subgraphId == null || subgraphId.isBlank())
            throw new IllegalArgumentException("subgraphId must not be blank");
        traits = traits == null ? Set.of() : Set.copyOf(traits);
        refs = refs == null ? Set.of() : Set.copyOf(refs);
        properties = properties == null ? Map.of() : Map.copyOf(properties);
    }
}
```

- [ ] **Step 8: Migrate EdgeInput record**

Replace `ConfidenceOrigin confidenceOrigin, Double confidence` with `Confidence confidence` (nullable):

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import java.time.Instant;
import java.util.Map;
import java.util.Objects;

public record EdgeInput(
    String sourceNodeId,
    String targetNodeId,
    String edgeType,
    Confidence confidence,
    String provenance,
    Instant validFrom,
    Instant validUntil,
    Double pleasure,
    Double arousal,
    Double dominance,
    Map<String, String> properties
) {
    public EdgeInput {
        Objects.requireNonNull(sourceNodeId, "sourceNodeId");
        Objects.requireNonNull(targetNodeId, "targetNodeId");
        Objects.requireNonNull(edgeType, "edgeType");
        properties = properties == null ? Map.of() : Map.copyOf(properties);
    }
}
```

- [ ] **Step 9: Migrate NodeUpdate record**

Replace `ConfidenceOrigin confidenceOrigin, Double confidence, Instant confirmedAt` with `Confidence confidence` (nullable):

```java
package io.casehub.neocortex.mindmap;

import io.casehub.neocortex.cognitive.Confidence;
import java.time.Instant;
import java.util.Map;
import java.util.Set;

public record NodeUpdate(
    String name,
    Confidence confidence,
    Set<String> traitsToAdd,
    Set<String> traitsToRemove,
    Set<NodeRef> refsToAdd,
    Set<NodeRef> refsToRemove,
    Instant validFrom,
    Instant validUntil,
    Double pleasure,
    Double arousal,
    Double dominance,
    Map<String, String> propertiesToSet,
    Set<String> propertiesToRemove
) {
    public NodeUpdate {
        traitsToAdd = traitsToAdd == null ? Set.of() : Set.copyOf(traitsToAdd);
        traitsToRemove = traitsToRemove == null ? Set.of() : Set.copyOf(traitsToRemove);
        refsToAdd = refsToAdd == null ? Set.of() : Set.copyOf(refsToAdd);
        refsToRemove = refsToRemove == null ? Set.of() : Set.copyOf(refsToRemove);
        propertiesToSet = propertiesToSet == null ? Map.of() : Map.copyOf(propertiesToSet);
        propertiesToRemove = propertiesToRemove == null ? Set.of() : Set.copyOf(propertiesToRemove);
    }
}
```

- [ ] **Step 10: Update MindMapQuery import**

Change `import io.casehub.neocortex.mindmap.ConfidenceOrigin` to `import io.casehub.neocortex.cognitive.ConfidenceOrigin`. The `ConfidenceOrigin confidenceOrigin` field and `Double minConfidence` stay as separate query predicates — no structural change.

- [ ] **Step 11: Migrate InMemoryMindMapStore**

Update `StoredNode` and `StoredEdge` inner types to use `Confidence` instead of separate `confidenceOrigin`/`confidence`/`confirmedAt` fields. Update `addNode()` and `addEdge()` to apply `MindMapConfidenceDefaults` when input confidence is null. All `ConfidenceOrigin` imports change to `io.casehub.neocortex.cognitive.ConfidenceOrigin`.

Key changes:
- `StoredNode`: remove `confirmedAt`, replace `confidenceOrigin` + `confidence` with `Confidence confidence`
- `StoredEdge`: replace `confidenceOrigin` + `confidence` with `Confidence confidence`
- `addNode()`: when `input.confidence() == null`, use `MindMapConfidenceDefaults.forOrigin(ConfidenceOrigin.STATED, Instant.now())`
- `addEdge()`: same defaulting pattern
- `updateNode()`: when `update.confidence() != null`, replace the stored confidence entirely
- All accessor delegations update: `confidence()` returns `Confidence`, removed `confidenceOrigin()` and `confirmedAt()` accessors

- [ ] **Step 12: Migrate MindMapStoreContractTest**

Update all test helper methods and assertions:
- `nodeInput(name, subgraphId)` → pass `null` for confidence (store defaults)
- Tests that set explicit confidence: construct `Confidence.stated(value, Instant.now())`
- Tests that assert `confidenceOrigin()` → assert `confidence().origin()`
- Tests that assert `confidence()` (double) → assert `confidence().value()`
- Remove `updateNode_confirmedAtWithoutConfidence_resetsTo1` test (D6 — behavior eliminated)
- Add new test: confirmation (updating decayReference only) preserves value and origin
- All `ConfidenceOrigin` imports change to `io.casehub.neocortex.cognitive.ConfidenceOrigin`

- [ ] **Step 13: Build and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognitive-api,mindmap-api,mindmap-inmem,mindmap-testing`
Expected: BUILD SUCCESS, all contract tests pass

- [ ] **Step 14: Commit**

```
git add cognitive-api/ mindmap-api/ mindmap-inmem/ mindmap-testing/
git commit -m "refactor(mindmap): migrate to unified Confidence record

MindMapNode/Edge return Confidence instead of separate origin+double.
NodeInput/EdgeInput/NodeUpdate use single Confidence field. confirmedAt
removed from MindMapNode (subsumed by Confidence.decayReference).
MindMapConfidenceDefaults provides origin-based default values.

Refs #229"
```

### Task 3: Migrate mindmap decorators and analyzer

**Files:**
- Modify: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayDecorator.java`
- Modify: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzer.java`
- Modify: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayDecoratorTest.java`
- Modify: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzerTest.java`
- Modify: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/DerivedEdgeDecoratorTest.java`
- Modify: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/VocabularyNormalizationDecoratorTest.java`
- Modify: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/TraitApplicationDecoratorTest.java`
- Modify: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/NodeRefCleanupObserverTest.java`

**Interfaces:**
- Consumes: Updated `MindMapNode.confidence()` → `Confidence`
- Produces: `ConfidenceDecayDecorator` reads `confidence().decayReference()` instead of `confirmedAt()`/`updatedAt()`; `DecayedNode`/`DecayedEdge` simplified (no `confirmedAt` delegation)

- [ ] **Step 1: Migrate ConfidenceDecayDecorator**

Key changes:
- `withDecayedConfidence(MindMapNode)`: read `node.confidence()` as `Confidence`, apply decay to `c.value()` using `c.decayReference()`, return `DecayedNode(node, c.withValue(decayed))`
- `withDecayedConfidence(MindMapEdge)`: same pattern using `edge.confidence().decayReference()` instead of `edge.updatedAt()`
- `DecayedNode`: remove `confirmedAt()` method (field removed from interface), `confidence()` returns `Confidence` not `double`
- `DecayedEdge`: `confidence()` returns `Confidence` not `double`, remove `confidenceOrigin()` delegation
- `search()` post-filter: `n.confidence().value() < query.minConfidence()`

- [ ] **Step 2: Migrate MindMapAnalyzer**

- `staleNodes()`: read `node.confidence().decayReference()` instead of `node.confirmedAt()`
- `lowConfidenceCluster()`: read `node.confidence().value()` instead of `node.confidence()`

- [ ] **Step 3: Update all mindmap test classes**

All test files that construct `NodeInput` or `EdgeInput` must use the new constructor (with `Confidence` instead of separate `ConfidenceOrigin` + `Double`). All `ConfidenceOrigin` imports update. Test helper methods (`node()`, `edge()`) in each test class update.

- [ ] **Step 4: Build and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognitive-api,mindmap-api,mindmap,mindmap-inmem,mindmap-testing`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```
git commit -m "refactor(mindmap): migrate decorators and analyzer to Confidence

ConfidenceDecayDecorator reads decayReference from Confidence record.
MindMapAnalyzer.staleNodes uses confidence().decayReference().
All test classes updated to new NodeInput/EdgeInput constructors.

Refs #229"
```

### Task 4: Migrate mindmap-intelligence and mindmap-sqlite

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ParsedEntity.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ParsedRelationship.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractedRelationship.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionJsonParser.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java`
- Modify: All `mindmap-intelligence/src/test/java/` test files
- Modify: `mindmap-sqlite/src/main/java/io/casehub/neocortex/mindmap/sqlite/SqliteMindMapStore.java`
- Create: `mindmap-sqlite/src/main/resources/db/mindmap-sqlite/migration/V2__unified_confidence.sql`

**Interfaces:**
- Consumes: `MindMapConfidenceDefaults`, updated `NodeInput`/`EdgeInput`

- [ ] **Step 1: Migrate ParsedEntity and ParsedRelationship**

- `ParsedEntity`: rename `ConfidenceOrigin confidence` field to `ConfidenceOrigin origin`
- `ParsedRelationship`: rename `ConfidenceOrigin confidence` field to `ConfidenceOrigin origin`
- Both: change import from `io.casehub.neocortex.mindmap.ConfidenceOrigin` to `io.casehub.neocortex.cognitive.ConfidenceOrigin`

- [ ] **Step 2: Migrate ExtractedRelationship**

Change `ConfidenceOrigin` import. Field name `confidenceOrigin` stays (already clear).

- [ ] **Step 3: Migrate ExtractionJsonParser**

- `parseConfidence()`: return type stays `ConfidenceOrigin`, import changes
- Update import to `io.casehub.neocortex.cognitive.ConfidenceOrigin`

- [ ] **Step 4: Migrate MindMapExtractor**

Update `applyExtraction()` to construct `NodeInput` and `EdgeInput` with full `Confidence`:

```java
// Before:
store.addNode(new NodeInput(pe.name(), sgId, pe.confidence(), null, ...));
// After:
store.addNode(new NodeInput(pe.name(), sgId,
    MindMapConfidenceDefaults.forOrigin(pe.origin(), Instant.now()), ...));
```

Same pattern for `EdgeInput` construction from `ParsedRelationship.origin()`.

- [ ] **Step 5: Update intelligence test classes**

All test files: update `NodeInput`/`EdgeInput` constructors, `ConfidenceOrigin` imports.

- [ ] **Step 6: Write Flyway migration for mindmap-sqlite**

Create `V2__unified_confidence.sql`:

```sql
-- Nodes: rename confidence → confidence_value, confirmed_at → decay_reference
ALTER TABLE nodes RENAME COLUMN confidence TO confidence_value;
ALTER TABLE nodes RENAME COLUMN confirmed_at TO decay_reference;

-- Edges: rename confidence → confidence_value, add decay_reference from updated_at
ALTER TABLE edges RENAME COLUMN confidence TO confidence_value;
ALTER TABLE edges ADD COLUMN decay_reference TEXT;
UPDATE edges SET decay_reference = updated_at;
```

- [ ] **Step 7: Migrate SqliteMindMapStore**

- `addNode()` / `addEdge()`: write `confidence_origin`, `confidence_value`, `decay_reference` columns from `Confidence` record
- `toNode()` / `toEdge()`: construct `Confidence` from three columns
- `updateNode()`: when `update.confidence() != null`, update all three columns
- Remove `confirmedAt` handling in node operations
- Apply `MindMapConfidenceDefaults` when input confidence is null

- [ ] **Step 8: Build and verify full mindmap subsystem**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognitive-api,mindmap-api,mindmap,mindmap-inmem,mindmap-testing,mindmap-sqlite,mindmap-intelligence`
Expected: BUILD SUCCESS, all tests pass including SQLite integration tests

- [ ] **Step 9: Commit**

```
git commit -m "refactor(mindmap): migrate intelligence layer and SQLite backend

ParsedEntity/ParsedRelationship origin field renamed. MindMapExtractor
uses MindMapConfidenceDefaults.forOrigin(). SqliteMindMapStore Flyway
V2 migration: confidence→confidence_value, confirmed_at→decay_reference.

Refs #229"
```

---

## Batch 3: Memory SPI + backends migration

### Task 5: Migrate memory-api types, converters, and InMemoryMemoryStore

**Files:**
- Modify: `memory-api/pom.xml` (add cognitive-api dependency)
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/Memory.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryRetentionPolicy.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryOrder.java` (javadoc)
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryAttributeKeys.java` (NaN-safe validation)
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/personality/PersonalityWeightedRetrieval.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodModulatedRetrieval.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/ExperienceEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/relationship/RelationshipEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/reflection/ReflectionEvents.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/engagement/EngagementEvents.java`
- Modify: `memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/runtime/MemoryRetentionConfig.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/runtime/MemoryRetentionScheduler.java`
- Modify: `memory-testing/` contract tests

**Interfaces:**
- Consumes: `io.casehub.neocortex.cognitive.Confidence`
- Produces: `MemoryInput.confidence()` → `Confidence` (nullable), `Memory.confidence()` → `Confidence` (nullable), `MemoryRetentionPolicy.minConfidence()` replaces `minImportance()`

- [ ] **Step 1: Add cognitive-api dependency to memory-api pom.xml**

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-cognitive-api</artifactId>
</dependency>
```

- [ ] **Step 2: Migrate MemoryInput**

Replace `Double importance` with `Confidence confidence` (nullable). Update compact constructor validation — remove importance range check (Confidence constructor handles it). Update `withAttribute`, `withAttributes`, `withText` to carry `confidence`.

- [ ] **Step 3: Migrate Memory**

Replace `Double importance` with `Confidence confidence` (nullable).

- [ ] **Step 4: Migrate MemoryRetentionPolicy**

Rename `minImportance` to `minConfidence`. Update validation to NaN-safe pattern: `if (!(minConfidence >= 0.0 && minConfidence <= 1.0))`.

- [ ] **Step 5: Migrate converters**

All 5 converters (`ExperienceEvents`, `MoodEvents`, `RelationshipEvents`, `ReflectionEvents`, `EngagementEvents`) update their `toMemoryInput()` methods:

```java
// Before:
new MemoryInput(entityId, domain, tenantId, null, text, attrs, importance)
// After:
new MemoryInput(entityId, domain, tenantId, null, text, attrs,
    importance != null ? Confidence.unknown(importance) : null)
```

`ReflectionEvents` has level-derived importance: wrap with `Confidence.unknown(Math.min(0.3 + level * 0.2, 1.0))`.

- [ ] **Step 6: Migrate PersonalityWeightedRetrieval and MoodModulatedRetrieval**

Both: change `m.importance()` reads to null-safe `m.confidence()`:

```java
double confidence = m.confidence() != null ? m.confidence().value() : 1.0;
```

- [ ] **Step 7: Migrate InMemoryMemoryStore**

- `store()`: pass `input.confidence()` through to `Memory` construction
- `salience()`: read `confidence().value()` with null-coalescing
- `purge()`: read `policy.minConfidence()` and `memory.confidence().value()`

- [ ] **Step 8: Migrate MemoryRetentionConfig and MemoryRetentionScheduler**

- `MemoryRetentionConfig`: rename `minImportance()` to `minConfidence()`
- Config property: `casehub.memory.retention.min-importance` → `casehub.memory.retention.min-confidence`
- `MemoryRetentionScheduler`: read `config.minConfidence()`

- [ ] **Step 9: Update MemoryAttributeKeys NaN validation**

Change `formatConfidence` validation to NaN-safe pattern.

- [ ] **Step 10: Update memory-testing contract tests**

- `importance_roundTrip` → `confidence_roundTrip`
- `importance_nullDefault` → `confidence_nullDefault`
- `purge_importanceBased` → use `minConfidence`

- [ ] **Step 11: Build and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognitive-api,memory-api,memory,memory-inmem,memory-testing`
Expected: BUILD SUCCESS

- [ ] **Step 12: Commit**

```
git commit -m "refactor(memory): migrate importance to unified Confidence

MemoryInput/Memory: Double importance → Confidence confidence.
MemoryRetentionPolicy: minImportance → minConfidence with NaN-safe guard.
All converters wrap importance in Confidence.unknown(). Retrieval
utilities read confidence().value() with null-coalescing.

Refs #229"
```

### Task 6: Migrate memory SQL backends

**Files:**
- Modify: `memory-sqlite/src/main/java/io/casehub/neocortex/memory/sqlite/SqliteMemoryStore.java`
- Create: `memory-sqlite/src/main/resources/db/memory-sqlite/migration/V2__unified_confidence.sql`
- Modify: `memory-jpa/src/main/java/io/casehub/neocortex/memory/jpa/` (entity + store)
- Create: `memory-jpa/src/main/resources/db/memory/migration/V2__unified_confidence.sql`
- Modify: `memory-mem0/src/main/java/io/casehub/neocortex/memory/mem0/Mem0CaseMemoryStore.java`
- Modify: `memory-graphiti/src/main/java/io/casehub/neocortex/memory/graphiti/GraphitiCaseMemoryStore.java`

**Interfaces:**
- Consumes: Updated `MemoryInput.confidence()`, `Memory.confidence()`

- [ ] **Step 1: SQLite Flyway migration**

Create `V2__unified_confidence.sql`:

```sql
ALTER TABLE memories RENAME COLUMN importance TO confidence_value;
ALTER TABLE memories ADD COLUMN confidence_origin TEXT NOT NULL DEFAULT 'UNKNOWN';
```

- [ ] **Step 2: Migrate SqliteMemoryStore**

Update SQL queries to write/read `confidence_value` and `confidence_origin`. Construct `Confidence` from the two columns on read.

- [ ] **Step 3: JPA Flyway migration**

Create `V2__unified_confidence.sql`:

```sql
ALTER TABLE memories RENAME COLUMN importance TO confidence_value;
ALTER TABLE memories ADD COLUMN confidence_origin VARCHAR(20) NOT NULL DEFAULT 'UNKNOWN';
```

- [ ] **Step 4: Migrate JpaMemoryStore**

Update JPA entity fields and queries.

- [ ] **Step 5: Migrate Mem0 and Graphiti REST clients**

Update REST payload field mapping: `importance` → `confidence`/`confidence_value`.

- [ ] **Step 6: Build and verify all memory modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognitive-api,memory-api,memory,memory-inmem,memory-testing,memory-sqlite,memory-jpa,memory-mem0,memory-graphiti`
Expected: BUILD SUCCESS

- [ ] **Step 7: Commit**

```
git commit -m "refactor(memory): migrate SQL backends to unified Confidence

SQLite/JPA Flyway V2: importance→confidence_value, add confidence_origin.
Mem0/Graphiti REST payload updated.

Refs #229"
```

---

## Batch 4: CBR SPI + backends migration

### Task 7: Migrate CBR API types and InMemoryCbrCaseMemoryStore

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TextualCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureVectorCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrOutcome.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRetrievalTrace.java`
- Modify: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/InMemoryCbrCaseMemoryStore.java`
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrOutcomeTest.java`

**Interfaces:**
- Consumes: `io.casehub.neocortex.cognitive.Confidence`
- Produces: `CbrCase.confidence()` → `Confidence` (nullable), `CbrCase.withOutcome(String, Confidence)`, `CbrOutcome.adjustConfidence(Confidence, double, double)` → `Confidence`

- [ ] **Step 1: Migrate CbrCase interface**

```java
Confidence confidence();  // was Double
CbrCase withOutcome(String outcome, Confidence confidence);  // was Double
```

- [ ] **Step 2: Migrate TextualCbrCase, FeatureVectorCbrCase, PlanCbrCase**

All three: change `Double confidence` component to `Confidence confidence` (nullable). Remove manual `< 0.0 || > 1.0` validation (Confidence constructor handles it). Update `withOutcome` signature.

- [ ] **Step 3: Migrate CbrOutcome.adjustConfidence**

```java
public static Confidence adjustConfidence(Confidence old, double successRate,
                                          double learningRate) {
    double oldValue = old != null ? old.value() : 1.0;
    double newValue = (1.0 - learningRate) * oldValue + learningRate * successRate;
    ConfidenceOrigin origin = old != null ? old.origin() : ConfidenceOrigin.UNKNOWN;
    return new Confidence(origin, newValue, null);
}
```

- [ ] **Step 4: Migrate CbrRetrievalTrace.TracedCase**

Change `Double confidence` to `Confidence confidence` (nullable).

- [ ] **Step 5: Migrate InMemoryCbrCaseMemoryStore**

- `recordOutcome()`: construct `Confidence` from `adjustConfidence` result
- All reads of `cbrCase.confidence()` update for `Confidence` return type

- [ ] **Step 6: Update CbrOutcomeTest**

Test `adjustConfidence` with `Confidence` inputs and outputs. Verify origin preservation, value EMA, null decayReference.

- [ ] **Step 7: Update CbrCaseMemoryStoreContractTest**

All test helpers constructing CbrCase implementations: use `Confidence.unknown(value)` or `null`. All assertions reading confidence: use `.confidence().value()`.

- [ ] **Step 8: Build and verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognitive-api,memory-api,memory,memory-inmem,memory-testing,memory-cbr-inmem`
Expected: BUILD SUCCESS

- [ ] **Step 9: Commit**

```
git commit -m "refactor(cbr): migrate CbrCase/CbrOutcome to unified Confidence

CbrCase.confidence() returns Confidence. CbrOutcome.adjustConfidence
takes/returns Confidence with origin preservation. TracedCase carries
full Confidence snapshot.

Refs #229"
```

### Task 8: Migrate CBR decorators and backends

**Files:**
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/OutcomeWeightingCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ScopeDecayCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/TrendEnrichmentCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/TrustWeightedCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ErasureNotificationCbrCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/CbrOutcomeConsumer.java`
- Modify: `memory-cbr-crossencoder/src/main/java/io/casehub/neocortex/memory/cbr/crossencoder/RerankingCbrCaseMemoryStore.java`
- Modify: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/TrackingCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java`
- Modify: `memory-cbr-jpa/src/main/java/io/casehub/neocortex/memory/cbr/jpa/JpaCbrCaseMemoryStore.java`
- Modify: All associated test files

**Interfaces:**
- Consumes: Updated `CbrCase.confidence()` → `Confidence`

- [ ] **Step 1: Migrate CBR decorators**

Each decorator that reads `cbrCase.confidence()` or `cbrCase.confidence()` as `Double` updates to handle `Confidence`:
- `OutcomeWeightingCbrCaseMemoryStore`: `cbrCase.confidence() != null ? cbrCase.confidence().value() : 1.0`
- `CbrOutcomeConsumer`: update `adjustConfidence` call
- Other decorators (ScopeDecay, TrustWeighted, etc.): most don't touch confidence directly — just need recompilation with updated imports

- [ ] **Step 2: Migrate QdrantCbrCaseMemoryStore**

- `CbrPointBuilder`: serialize confidence as structured payload `{origin, value, decayReference}`
- Deserialization: reconstruct `Confidence` from payload fields
- `recordOutcome`: construct `Confidence` from EMA result
- Breaking storage format — Qdrant collections recreated (pre-release)

- [ ] **Step 3: Migrate JpaCbrCaseMemoryStore**

- Entity column changes: `confidence` (Double) → `confidence_value` (Double) + `confidence_origin` (String)
- Flyway migration (if CBR JPA has its own schema)
- Query/result mapping

- [ ] **Step 4: Migrate TrackingCbrCaseMemoryStore**

Update `TracedCase` construction to pass `Confidence` instead of `Double`.

- [ ] **Step 5: Update all CBR decorator tests**

Test helpers and assertions update for `Confidence` type.

- [ ] **Step 6: Build and verify full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS (full compilation check)

Then: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 7: Commit**

```
git commit -m "refactor(cbr): migrate decorators and backends to unified Confidence

OutcomeWeighting, Tracking, Qdrant, JPA backends read Confidence.
Qdrant payload serialization updated to structured confidence object.

Refs #229"
```

---

## Batch 5: Documentation + CLAUDE.md

### Task 9: Update documentation and CLAUDE.md

**Files:**
- Modify: `docs/guides/consumer-guide.md` (importance → confidence, 8 references)
- Modify: `docs/guides/contributor-guide.md` (importance → confidence, 6 references)
- Modify: `docs/guides/cognitive-types-guide.md` (confirmedAt reference)
- Modify: `docs/guides/cognitive-coherence-audit.md` (confirmedAt references, gap resolution)
- Modify: `docs/guides/cognitive-architecture-roadmap.md` (mark §1a as done)
- Modify: `CLAUDE.md` (add cognitive-api module, update module descriptions)

- [ ] **Step 1: Update consumer-guide.md**

Replace all `importance` references in Memory API descriptions with `confidence`. Update config property names (`min-importance` → `min-confidence`).

- [ ] **Step 2: Update contributor-guide.md**

Replace `importance` references. Update module descriptions to include `cognitive-api`.

- [ ] **Step 3: Update cognitive-types-guide.md**

Update line ~400: "gets reinforced by confirmation (`confirmedAt`)" → "gets reinforced by updating `decayReference` via a new `Confidence` with a fresh `Instant`"

- [ ] **Step 4: Update cognitive-coherence-audit.md**

Mark the three-model gap as resolved. Update `confirmedAt` references. Note the "Add confirmedAt to MindMapEdge" recommendation is now moot — edges use `confidence().decayReference()`.

- [ ] **Step 5: Update cognitive-architecture-roadmap.md**

Mark §1a (Unified Confidence Model) as complete.

- [ ] **Step 6: Update CLAUDE.md**

Add `cognitive-api` module to the module structure table and Maven coordinates. Update `mindmap-api` and `memory-api` descriptions to reference `Confidence` instead of `ConfidenceOrigin`/`importance`. Add `cognitive-api` dependency note.

- [ ] **Step 7: Commit**

```
git commit -m "docs: update guides and CLAUDE.md for unified Confidence model

consumer-guide, contributor-guide: importance→confidence.
cognitive-types-guide: confirmedAt→decayReference.
cognitive-coherence-audit: mark three-model gap resolved.
CLAUDE.md: add cognitive-api module.

Refs #229"
```

---

## References

- [2026-08-29-unified-confidence-model-design.md](../specs/issue-253-cognitive-rearchitecture/2026-08-29-unified-confidence-model-design.md) — design spec this plan implements
- [decisions.md](../specs/issue-253-cognitive-rearchitecture/decisions.md) — D1-D7 captured decisions
- [ConfidenceOrigin.java](../../mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ConfidenceOrigin.java) — current enum (moves to cognitive-api)
- [MindMapNode.java](../../mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java) — current interface
- [MemoryInput.java](../../memory-api/src/main/java/io/casehub/neocortex/memory/MemoryInput.java) — current importance field
- [CbrCase.java](../../memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCase.java) — current confidence interface
- [CbrOutcome.java](../../memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrOutcome.java) — current EMA
- [ConfidenceDecayDecorator.java](../../mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayDecorator.java) — current decay logic
- [GE-20260604-043617] — NaN range guard gotcha (inverted check pattern)
- [GitHub #229](https://github.com/casehubio/neocortex/issues/229) — focal issue
- [GitHub #253](https://github.com/casehubio/neocortex/issues/253) — epic
