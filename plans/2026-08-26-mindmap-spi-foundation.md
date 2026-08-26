# MindMap SPI Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** TBD — tracking epic must be created in `casehubio/neocortex` before implementation begins
**Issue group:** TBD

**Goal:** Deliver the MindMap SPI (mindmap-api), in-memory implementation
(mindmap-inmem), contract test suite (mindmap-testing), and CDI wiring
with decorators (mindmap) — the complete foundation for structural
knowledge graphs.

**Architecture:** New top-level module family following the established
`memory-*` pattern. `MindMapStore` is a standalone SPI (no inheritance
from `CaseMemoryStore` or `CbrCaseMemoryStore`). The in-memory
implementation passes all contract tests. CDI decorators provide
transparent vocabulary normalization and confidence decay. Graph analysis
and intelligence layers are separate future plans.

**Tech Stack:** Java 21, Quarkus 3.32.2 (CDI/Arc), JUnit 5, AssertJ

## Global Constraints

- Java 21 source, Java 26 JVM (`JAVA_HOME=$(/usr/libexec/java_home -v 26)`)
- `mindmap-api` has **zero** casehub module dependencies — pure Java only
- Build with `mvn` not `./mvnw`
- All modules use `io.casehub` groupId, `casehub-neocortex-mindmap-*` artifactId
- CDI modules need `jandex-maven-plugin` for bean discovery
- Every method that takes or returns tenant-scoped data requires `tenantId` parameter
- PAD affect fields use `pleasure()` not `valence()` — matches `MoodState.pleasure()`
- Confidence is two-part: `ConfidenceOrigin` (categorical provenance) + `double confidence` (numeric, decayable)
- Use IntelliJ MCP for all code navigation and editing on `.java` files

## Scope

**In scope (this plan):**
- `mindmap-api` — SPI interface + all value types
- `mindmap-inmem` — `InMemoryMindMapStore` implementation
- `mindmap-testing` — `MindMapStoreContractTest` abstract base
- `mindmap` — CDI wiring: `NoOpMindMapStore`, `VocabularyNormalizationDecorator`, `ConfidenceDecayDecorator`

**Out of scope (separate plans):**
- `mindmap-sqlite` — production SQLite backend
- `mindmap-intelligence` — LLM extraction, trait proxy, curiosity engine
- Blocks integration — CDI observers for domain events
- Graph analysis (`MindMapAnalyzer`) — pure computation module

---

## Batch 1: Maven Modules + SPI Types + Interface

### Task 1: Create Maven modules and define all SPI types

**Files:**
- Create: `mindmap-api/pom.xml`
- Create: `mindmap/pom.xml`
- Create: `mindmap-inmem/pom.xml`
- Create: `mindmap-testing/pom.xml`
- Modify: `pom.xml` (parent — add 4 module entries)
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapStore.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapNode.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapEdge.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeInput.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeUpdate.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/EdgeInput.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeRef.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapVocabulary.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/EdgeTypeDefinition.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphInput.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapSubgraph.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphType.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ValidationTier.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ConfidenceOrigin.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapQuery.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MergeResult.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MergeConflict.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SupersessionStatus.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapCapability.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapCapabilityException.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/VocabularyConflictException.java`
- Create: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/NoOpMindMapStore.java`

**Interfaces:**
- Produces: `MindMapStore` — the SPI interface consumed by all subsequent tasks
- Produces: All value types consumed by contract tests and implementations

- [ ] **Step 1: Create `mindmap-api/pom.xml`**

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
  <artifactId>casehub-neocortex-mindmap-api</artifactId>
  <name>CaseHub Neocortex - MindMap API</name>
  <description>MindMapStore SPI — typed knowledge graph with nodes, edges, vocabulary, aliases, subgraphs. Tier 1 pure Java.</description>
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

- [ ] **Step 2: Create `mindmap-testing/pom.xml`**

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
  <artifactId>casehub-neocortex-mindmap-testing</artifactId>
  <name>CaseHub Neocortex - MindMap Testing</name>
  <description>MindMapStoreContractTest abstract base class.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-mindmap-api</artifactId>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>compile</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>compile</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 3: Create `mindmap-inmem/pom.xml`**

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
  <artifactId>casehub-neocortex-mindmap-inmem</artifactId>
  <name>CaseHub Neocortex - MindMap In-Memory</name>
  <description>In-memory MindMapStore for testing and dev. @Alternative @Priority(1).</description>
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
      <artifactId>casehub-neocortex-mindmap-testing</artifactId>
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

- [ ] **Step 4: Create `mindmap/pom.xml`**

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
  <artifactId>casehub-neocortex-mindmap</artifactId>
  <name>CaseHub Neocortex - MindMap CDI</name>
  <description>NoOp @DefaultBean, vocabulary normalization decorator, confidence decay decorator.</description>
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

- [ ] **Step 5: Add modules to parent `pom.xml`**

Add after the `memory-graphiti` module entry:
```xml
    <module>mindmap-api</module>
    <module>mindmap</module>
    <module>mindmap-inmem</module>
    <module>mindmap-testing</module>
```

- [ ] **Step 6: Create all enums and simple value types in mindmap-api**

Create these files in `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/`:

`SubgraphType.java`:
```java
package io.casehub.neocortex.mindmap;

public enum SubgraphType {
    PERSON, PROJECT, RESEARCH_AREA, ORGANISATION, CONCEPT, GENERAL
}
```

`ValidationTier.java`:
```java
package io.casehub.neocortex.mindmap;

public enum ValidationTier {
    REGISTERED, UNVALIDATED
}
```

`ConfidenceOrigin.java`:
```java
package io.casehub.neocortex.mindmap;

public enum ConfidenceOrigin {
    STATED(1.0),
    INFERRED(0.7),
    SPECULATED(0.3);

    private final double initialConfidence;

    ConfidenceOrigin(double initialConfidence) {
        this.initialConfidence = initialConfidence;
    }

    public double initialConfidence() {
        return initialConfidence;
    }
}
```

`MindMapCapability.java`:
```java
package io.casehub.neocortex.mindmap;

public enum MindMapCapability {
    TRAVERSAL, MERGE, VOCABULARY, ALIAS, SUBGRAPH, SEARCH,
    SUPERSESSION, ERASE_NODE, ERASE_SUBGRAPH, ERASE_ENTITY,
    CROSS_TENANT_ERASE, GRAPH_ANALYSIS
}
```

`MindMapCapabilityException.java`:
```java
package io.casehub.neocortex.mindmap;

public class MindMapCapabilityException extends RuntimeException {
    private final MindMapCapability capability;

    public MindMapCapabilityException(MindMapCapability capability) {
        super("Capability not supported: " + capability);
        this.capability = capability;
    }

    public MindMapCapability capability() {
        return capability;
    }
}
```

`VocabularyConflictException.java`:
```java
package io.casehub.neocortex.mindmap;

public class VocabularyConflictException extends RuntimeException {
    public VocabularyConflictException(String message) {
        super(message);
    }
}
```

`NodeRef.java`:
```java
package io.casehub.neocortex.mindmap;

import java.util.Objects;

public record NodeRef(
    String scheme,
    String id,
    String qualifier
) {
    public NodeRef {
        Objects.requireNonNull(scheme, "scheme");
        Objects.requireNonNull(id, "id");
    }
}
```

`EdgeTypeDefinition.java`:
```java
package io.casehub.neocortex.mindmap;

import java.util.Objects;
import java.util.Set;

public record EdgeTypeDefinition(
    String canonical,
    Set<String> aliases,
    Double defaultDecayHalfLifeDays
) {
    public EdgeTypeDefinition {
        Objects.requireNonNull(canonical, "canonical");
        if (canonical.isBlank()) throw new IllegalArgumentException("canonical must not be blank");
        aliases = aliases == null ? Set.of() : Set.copyOf(aliases);
    }
}
```

`MindMapVocabulary.java`:
```java
package io.casehub.neocortex.mindmap;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;

public record MindMapVocabulary(List<EdgeTypeDefinition> edgeTypes) {
    public MindMapVocabulary {
        edgeTypes = List.copyOf(edgeTypes);
    }

    public static Builder builder() {
        return new Builder();
    }

    public static final class Builder {
        private final List<EdgeTypeDefinition> edgeTypes = new ArrayList<>();

        public Builder edgeType(String canonical, String... aliases) {
            edgeTypes.add(new EdgeTypeDefinition(canonical,
                Set.of(aliases), null));
            return this;
        }

        public Builder edgeType(String canonical, Double decayHalfLifeDays,
                                String... aliases) {
            edgeTypes.add(new EdgeTypeDefinition(canonical,
                Set.of(aliases), decayHalfLifeDays));
            return this;
        }

        public MindMapVocabulary build() {
            return new MindMapVocabulary(edgeTypes);
        }
    }
}
```

`MergeConflict.java`:
```java
package io.casehub.neocortex.mindmap;

public record MergeConflict(String key, String keptValue, String discardedValue) {}
```

`SupersessionStatus.java`:
```java
package io.casehub.neocortex.mindmap;

import java.time.Instant;

public record SupersessionStatus(
    String targetId,
    boolean superseded,
    Instant supersededAt,
    String supersedingId,
    String reason,
    Instant reinstatedAt
) {
    public static final SupersessionStatus NOT_SUPERSEDED =
        new SupersessionStatus(null, false, null, null, null, null);

    public boolean wasReinstated() {
        return reinstatedAt != null;
    }
}
```

- [ ] **Step 7: Create record types for inputs, outputs, and queries**

`SubgraphInput.java`:
```java
package io.casehub.neocortex.mindmap;

public record SubgraphInput(String name, SubgraphType type, String rootNodeId) {}
```

`MindMapSubgraph.java`:
```java
package io.casehub.neocortex.mindmap;

import java.time.Instant;

public record MindMapSubgraph(
    String id, String name, SubgraphType type,
    String rootNodeId, String tenantId, Instant createdAt
) {}
```

`NodeInput.java`:
```java
package io.casehub.neocortex.mindmap;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

public record NodeInput(
    String name,
    String subgraphId,
    ConfidenceOrigin confidenceOrigin,
    Double confidence,
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
        if (confidenceOrigin == null) confidenceOrigin = ConfidenceOrigin.STATED;
        traits = traits == null ? Set.of() : Set.copyOf(traits);
        refs = refs == null ? Set.of() : Set.copyOf(refs);
        properties = properties == null ? Map.of() : Map.copyOf(properties);
    }
}
```

`NodeUpdate.java`:
```java
package io.casehub.neocortex.mindmap;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

public record NodeUpdate(
    String name,
    ConfidenceOrigin confidenceOrigin,
    Double confidence,
    Instant confirmedAt,
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
) {}
```

`EdgeInput.java`:
```java
package io.casehub.neocortex.mindmap;

import java.time.Instant;
import java.util.Map;
import java.util.Objects;

public record EdgeInput(
    String sourceNodeId,
    String targetNodeId,
    String edgeType,
    ConfidenceOrigin confidenceOrigin,
    Double confidence,
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
        if (confidenceOrigin == null) confidenceOrigin = ConfidenceOrigin.STATED;
        properties = properties == null ? Map.of() : Map.copyOf(properties);
    }
}
```

`MindMapQuery.java`:
```java
package io.casehub.neocortex.mindmap;

import java.util.Objects;
import java.util.Set;

public record MindMapQuery(
    String tenantId,
    String subgraphId,
    String text,
    String edgeType,
    Set<String> traits,
    Double minConfidence,
    ConfidenceOrigin confidenceOrigin,
    boolean includeSuperseded,
    int limit
) {
    public MindMapQuery {
        Objects.requireNonNull(tenantId, "tenantId");
        if (limit <= 0) throw new IllegalArgumentException("limit must be positive");
    }
}
```

`MergeResult.java`:
```java
package io.casehub.neocortex.mindmap;

import java.util.List;
import java.util.Set;

public record MergeResult(
    String survivingNodeId,
    int edgesRepointed,
    int aliasesMerged,
    int duplicateEdgesRemoved,
    Set<String> traitsMerged,
    List<MergeConflict> propertyConflicts
) {}
```

- [ ] **Step 8: Create `MindMapNode` and `MindMapEdge` interfaces**

`MindMapNode.java`:
```java
package io.casehub.neocortex.mindmap;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

public interface MindMapNode {
    String id();
    String name();
    String subgraphId();
    ConfidenceOrigin confidenceOrigin();
    double confidence();
    String provenance();
    Instant createdAt();
    Instant updatedAt();
    Instant confirmedAt();
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

`MindMapEdge.java`:
```java
package io.casehub.neocortex.mindmap;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;

public interface MindMapEdge {
    String id();
    String sourceNodeId();
    String targetNodeId();
    String edgeType();
    ValidationTier tier();
    ConfidenceOrigin confidenceOrigin();
    double confidence();
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

- [ ] **Step 9: Create `MindMapStore` SPI interface**

`MindMapStore.java` — full interface as specified in §3.1 of the spec.
All methods with tenantId parameters, including vocabulary, node CRUD,
edge CRUD, aliases, merge, subgraphs, traversal, lifecycle, erasure,
and capabilities. See spec §3.1 for exact signatures.

- [ ] **Step 10: Create `NoOpMindMapStore` in the mindmap CDI module**

`mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/NoOpMindMapStore.java`:

`@DefaultBean @ApplicationScoped` implementing `MindMapStore`. Every
method either returns empty/null/0 or throws `MindMapCapabilityException`.
`capabilities()` returns `Set.of()`. This is the fallback when no real
backend is on the classpath.

- [ ] **Step 11: Build and verify all modules compile**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl mindmap-api,mindmap,mindmap-inmem,mindmap-testing -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 12: Commit**

```bash
git add mindmap-api/ mindmap/ mindmap-inmem/ mindmap-testing/ pom.xml
git commit -m "feat(mindmap): scaffold Maven modules + SPI types + interface + NoOp default"
```

---

## Batch 2: Node + Subgraph + Alias — core graph structure works

### Task 2: Contract tests and InMemoryMindMapStore for nodes, subgraphs, and aliases

**Files:**
- Create: `mindmap-inmem/src/main/java/io/casehub/neocortex/mindmap/inmem/InMemoryMindMapStore.java`
- Create: `mindmap-testing/src/main/java/io/casehub/neocortex/mindmap/testing/MindMapStoreContractTest.java`
- Create: `mindmap-inmem/src/test/java/io/casehub/neocortex/mindmap/inmem/InMemoryMindMapStoreTest.java`

**Interfaces:**
- Consumes: `MindMapStore`, all value types from Task 1
- Produces: `InMemoryMindMapStore` — in-memory implementation. `MindMapStoreContractTest` — abstract base class extended by each backend.

- [ ] **Step 1: Create `MindMapStoreContractTest` with subgraph + node CRUD tests**

In `mindmap-testing/`, create abstract test class with:
- `abstract MindMapStore createStore()` — implemented by each backend
- `@BeforeEach` calls `createStore()` and registers a test vocabulary
- Test: `addNode_returnsNonNullId`
- Test: `getNode_returnsStoredNode`
- Test: `updateNode_changesName`
- Test: `updateNode_addsTraits`
- Test: `updateNode_removesTraits`
- Test: `updateNode_setsProperties`
- Test: `updateNode_removesProperties`
- Test: `updateNode_setsConfirmedAt`
- Test: `updateNode_setsAffect`
- Test: `createSubgraph_returnsId`
- Test: `getSubgraph_returnsStoredSubgraph`
- Test: `nodesIn_returnsNodesInSubgraph`
- Test: `nodesIn_excludesOtherSubgraphs`
- Test: `addAlias_resolvesNode`
- Test: `removeAlias_noLongerResolves`
- Test: `resolveNode_byName`
- Test: `resolveNode_byAlias`
- Test: `resolveNode_nullSubgraphId_searchesAll`
- Test: `resolveNode_withSubgraphId_scopesSearch`
- Test: `resolveNode_unknownName_returnsNull`
- Test: `tenantIsolation_nodeInvisibleAcrossTenants`
- Test: `tenantIsolation_subgraphInvisibleAcrossTenants`
- Test: `tenantIsolation_aliasInvisibleAcrossTenants`

Each test follows the pattern: arrange (create subgraph, add node), act (call method), assert (check result).

- [ ] **Step 2: Create `InMemoryMindMapStore` with internal storage records**

Use `ConcurrentHashMap<String, StoredNode>` for nodes,
`ConcurrentHashMap<String, MindMapSubgraph>` for subgraphs,
`ConcurrentHashMap<String, String>` for aliases (alias → nodeId per tenant).
UUID.randomUUID() for ID generation.

Internal record `StoredNode` implements `MindMapNode` — holds all core fields
plus a `Map<String, String>` for dynamic properties. The `property(key)` method
checks core field names first, then falls back to the dynamic map.

Implement: `registerVocabulary`, `addNode`, `getNode`, `updateNode`,
`createSubgraph`, `getSubgraph`, `nodesIn`, `addAlias`, `removeAlias`,
`resolveNode`. All other methods throw `MindMapCapabilityException` for now.
`capabilities()` returns the set of implemented capabilities.
Add `clearAll()` for test isolation.

- [ ] **Step 3: Create `InMemoryMindMapStoreTest` extending contract test**

```java
class InMemoryMindMapStoreTest extends MindMapStoreContractTest {
    @Override
    protected MindMapStore createStore() {
        return new InMemoryMindMapStore();
    }
}
```

- [ ] **Step 4: Run tests and verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-testing,mindmap-inmem`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add mindmap-inmem/ mindmap-testing/
git commit -m "feat(mindmap): node + subgraph + alias CRUD with contract tests"
```

---

## Batch 3: Edge + Vocabulary + Traversal — full graph operations work

### Task 3: Contract tests and implementation for edges, vocabulary, traversal, search, and tenant isolation

**Files:**
- Modify: `mindmap-testing/.../MindMapStoreContractTest.java`
- Modify: `mindmap-inmem/.../InMemoryMindMapStore.java`

**Interfaces:**
- Consumes: Subgraph/node creation from Task 2
- Produces: Edge CRUD, vocabulary normalization, traversal, search, bridge detection

- [ ] **Step 1: Add edge + vocabulary contract tests**

- Test: `addEdge_returnsId`
- Test: `getEdge_returnsStoredEdge`
- Test: `removeEdge_deletesEdge`
- Test: `addEdge_registeredType_setsTierRegistered`
- Test: `addEdge_unregisteredType_setsTierUnvalidated`
- Test: `addEdge_aliasType_normalizesToCanonical`
- Test: `registerVocabulary_mergesDefinitions`
- Test: `registerVocabulary_conflictingAlias_throws`
- Test: `addEdge_withTemporalBounds`
- Test: `addEdge_withAffect`
- Test: `addEdge_withProperties`

- [ ] **Step 2: Add traversal + search contract tests**

- Test: `neighbors_returnsAllEdges`
- Test: `neighbors_filteredByType`
- Test: `neighbors_emptyForIsolatedNode`
- Test: `bridgeEdges_returnsCrossSubgraphEdges`
- Test: `bridgeEdges_excludesInternalEdges`
- Test: `search_byText_matchesNodeName`
- Test: `search_bySubgraph`
- Test: `search_byTraits`
- Test: `search_byEdgeType_returnsConnectedNodes`
- Test: `search_respectsLimit`
- Test: `tenantIsolation_edgeInvisibleAcrossTenants`

- [ ] **Step 3: Implement edge CRUD, vocabulary, traversal, and search in InMemoryMindMapStore**

Add `ConcurrentHashMap<String, StoredEdge>` for edges.
Add vocabulary registry: `Map<String, String>` for alias→canonical mapping,
`Map<String, EdgeTypeDefinition>` for canonical→definition.

Implement vocabulary registration with conflict detection
(`VocabularyConflictException` when an alias is already a canonical in
another definition).

Edge storage: on `addEdge()`, check if `edgeType` is in the alias map
→ normalise to canonical → set `ValidationTier.REGISTERED`. If not in
vocabulary at all → store as-is with `ValidationTier.UNVALIDATED`.

Traversal: `neighbors()` filters edges by sourceNodeId OR targetNodeId.
`bridgeEdges()` finds edges where source and target are in different
subgraphs. `search()` filters nodes by text (case-insensitive contains
on name + property values), subgraph, traits, and limit.

- [ ] **Step 4: Run tests and verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-testing,mindmap-inmem`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add mindmap-inmem/ mindmap-testing/
git commit -m "feat(mindmap): edge CRUD, vocabulary normalization, traversal, search"
```

---

## Batch 4: Merge + Lifecycle + Erasure — all SPI methods implemented

### Task 4: Contract tests and implementation for merge, supersession, and cascading erasure

**Files:**
- Modify: `mindmap-testing/.../MindMapStoreContractTest.java`
- Modify: `mindmap-inmem/.../InMemoryMindMapStore.java`

**Interfaces:**
- Consumes: Node/edge/alias/subgraph operations from Tasks 2-3
- Produces: Complete `MindMapStore` implementation — all methods work

- [ ] **Step 1: Add merge contract tests**

- Test: `mergeNodes_keepsTargetNode`
- Test: `mergeNodes_removesSourceNode`
- Test: `mergeNodes_unionsAliases`
- Test: `mergeNodes_repointsEdges`
- Test: `mergeNodes_deduplicatesEdges_higherConfidenceWins`
- Test: `mergeNodes_unionsTraits`
- Test: `mergeNodes_propertyConflict_newerWins`
- Test: `mergeNodes_reportsPropertyConflicts`

- [ ] **Step 2: Add supersession contract tests**

- Test: `supersede_marksTargetSuperseded`
- Test: `getSupersessionStatus_returnsStatus`
- Test: `reinstate_clearsSupersession`
- Test: `supersessionStatus_wasReinstated`
- Test: `supersede_notFoundThrows`

- [ ] **Step 3: Add erasure contract tests**

- Test: `eraseNode_removesNodeAndEdgesAndAliases`
- Test: `eraseNode_removesNodeRefs`
- Test: `eraseNode_returnsDeletedCount`
- Test: `eraseSubgraph_removesAllNodesAndEdges`
- Test: `eraseEntity_findsByNameOrAlias`
- Test: `eraseEntityAcrossTenants_erasesInAllTenants`
- Test: `eraseNode_nonExistent_returnsZero`

- [ ] **Step 4: Add capability contract tests**

- Test: `capabilities_returnsNonEmpty`
- Test: `requireCapability_supportedDoesNotThrow`
- Test: `requireCapability_unsupportedThrows`

- [ ] **Step 5: Implement merge, supersession, erasure, and capabilities**

**Merge:** find both nodes, union aliases (add source's aliases to target),
repoint edges (change sourceNodeId/targetNodeId from removeNode to keepNode),
deduplicate edges (same source+target+edgeType — keep the one with later
`updatedAt`), union traits, resolve property conflicts (later `updatedAt`
wins, record conflicts in `MergeConflict`), delete source node.

**Supersession:** store supersession metadata on the node (supersededAt,
supersedingId, reason). `reinstate()` clears supersession and records
reinstatedAt. `getSupersessionStatus()` returns the status record.

**Erasure:** `eraseNode()` — delete node, all edges where node is source
or target, all aliases for node, all NodeRefs on node. Return total
count. `eraseSubgraph()` — iterate nodesIn, eraseNode each, delete
subgraph record. `eraseEntity()` — find nodes by name or alias
(case-insensitive), eraseNode each. `eraseEntityAcrossTenants()` — same
across supplied tenant IDs.

**Capabilities:** `InMemoryMindMapStore.capabilities()` returns
`EnumSet.allOf(MindMapCapability.class)` — supports everything.

- [ ] **Step 6: Run tests and verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-testing,mindmap-inmem`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add mindmap-inmem/ mindmap-testing/
git commit -m "feat(mindmap): merge, supersession, cascading erasure, capabilities"
```

---

## Batch 5: CDI Decorators — production-ready wiring

### Task 5: VocabularyNormalizationDecorator and ConfidenceDecayDecorator

**Files:**
- Create: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/VocabularyNormalizationDecorator.java`
- Create: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayDecorator.java`
- Create: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayConfig.java`
- Create: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/VocabularyNormalizationDecoratorTest.java`
- Create: `mindmap/src/test/java/io/casehub/neocortex/mindmap/runtime/ConfidenceDecayDecoratorTest.java`

**Interfaces:**
- Consumes: `MindMapStore` SPI, `InMemoryMindMapStore` (as delegate in tests)
- Produces: CDI decorators that wrap any `MindMapStore` transparently

- [ ] **Step 1: Write VocabularyNormalizationDecorator tests**

- Test: `addEdge_normalizesAliasToCanonical` — register vocabulary with
  alias "employed-by" → canonical "works-at". Call `addEdge` with type
  "employed-by". Verify stored edge has type "works-at" and tier REGISTERED.
- Test: `addEdge_unregisteredType_passesThrough` — call `addEdge` with
  unregistered type. Verify stored edge has tier UNVALIDATED.
- Test: `addEdge_alreadyCanonical_noChange` — call `addEdge` with canonical
  type. Verify stored as-is with tier REGISTERED.

- [ ] **Step 2: Implement VocabularyNormalizationDecorator**

`@Decorator @Priority(APPLICATION)` on `MindMapStore`. Intercepts
`addEdge()` — looks up the edgeType in the vocabulary, normalises aliases,
and delegates to the real store with the normalised edge type. Thread-safe
vocabulary access via `ReadWriteLock`. All other methods delegate directly.

- [ ] **Step 3: Write ConfidenceDecayDecorator tests**

- Test: `getNode_appliesDecay` — store a node with confirmedAt = 1 half-life
  ago. Retrieve it. Verify effective confidence is ~0.5.
- Test: `getNode_freshNode_noDecay` — store a node with confirmedAt = now.
  Retrieve it. Verify confidence is unchanged.
- Test: `search_appliesMinConfidenceAfterDecay` — store two nodes, one
  recently confirmed (high effective confidence) and one stale (decayed
  below threshold). Search with `minConfidence`. Verify only the fresh
  node is returned.
- Test: `neighbors_edgesDecayed` — verify edge confidence is decayed based
  on edge updatedAt and vocabulary-defined half-life.

- [ ] **Step 4: Implement ConfidenceDecayDecorator**

`@Decorator @Priority(APPLICATION - 1)` on `MindMapStore` (lower priority
than vocabulary normalization — decay runs after normalization on writes,
before on reads). Intercepts `getNode()`, `search()`, `neighbors()`,
`nodesIn()`, `bridgeEdges()` — wraps returned nodes/edges with decayed
confidence values. Uses the formula:
`effectiveConfidence = confidence × 2^(-hoursSinceConfirmed / (halfLifeDays × 24))`

`ConfidenceDecayConfig` — `@ConfigMapping(prefix = "casehub.mindmap.decay")`
with per-SubgraphType node half-lives and a global default.

- [ ] **Step 5: Run all tests across all modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-api,mindmap,mindmap-inmem,mindmap-testing`
Expected: All tests PASS

- [ ] **Step 6: Run full project build to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 7: Commit**

```bash
git add mindmap/
git commit -m "feat(mindmap): vocabulary normalization + confidence decay decorators"
```

---

## References

- [2026-08-26-mindmap-spi-design.md] — design spec this plan implements
- [memory-api/pom.xml] — Maven module pattern (zero-dep API)
- [memory-cbr-inmem/pom.xml] — Maven module pattern (in-memory CDI)
- [memory-testing/pom.xml] — Maven module pattern (testing, compile-scope deps)
- [memory/pom.xml] — Maven module pattern (CDI wiring, jandex)
- [pom.xml] — parent pom module list
- [InMemoryCbrCaseMemoryStore] — in-memory implementation pattern
- [CbrCaseMemoryStore] — SPI pattern (standalone interface, capabilities, supersession)
- [GE-20260630-815259] — standalone SPI to avoid CDI displacement
- [D1–D18] — design decisions from brainstorming
