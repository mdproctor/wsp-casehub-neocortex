# CognitiveProfile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #243 — Cross-store entity resolution
**Issue group:** #253, #229, #232, #234, #235, #236, #237, #238, #239, #241, #242, #244, #243

**Goal:** Build a CognitiveProfile CDI bean in cognitive-index that
resolves everything the system knows about an entity across MindMap,
Memory, and CBR stores — the "tell me everything about Alice" query.

**Architecture:** Three new types in `cognitive-index`:
`CognitiveProfileQuery` (immutable query record with `byId`/`byName`
factories and `withX()` builders), `EntityKnowledge` (result record
aggregating node, edges, memories-by-domain, affect trajectory, and
unresolved refs), and `CognitiveProfile` (`@ApplicationScoped` CDI bean
with `Instance<T>` graceful degradation, single `resolve()` method
returning `Optional<EntityKnowledge>`). Follows TemporalIndex's proven
CDI + dual-constructor pattern. Composes with AffectTrajectoryAnalyzer
for trajectory computation.

**Tech Stack:** Java 21, JUnit 5, AssertJ, InMemoryMindMapStore,
StubMemoryStore (local test stub reused from TemporalIndexTest pattern)

## Global Constraints

- Module: `cognitive-index` (`io.casehub.neocortex.cognitive.index`)
- No new dependencies — cognitive-index already has mindmap-api,
  memory-api, cognitive-api, CDI, and test deps (mindmap-inmem,
  memory-inmem)
- All types are records (query, result) or `@ApplicationScoped` bean
- Immutable `withX()` pattern following CbrQuery convention
- `Instance<T>` graceful degradation following TemporalIndex convention
- Test constructor for unit tests without CDI
- Entity ID resolution uses both `node.id()` (UUID) and `node.name()`
  (human-readable) per D39

---

## Batch 1: Query and Result Types

### Task 1: CognitiveProfileQuery record

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfileQuery.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveProfileQueryTest.java`

**Interfaces:**
- Consumes: `MemoryDomain` from memory-api
- Produces: `CognitiveProfileQuery` — used by CognitiveProfile.resolve()
  and all tests. Key API surface:
  - `CognitiveProfileQuery.byId(String nodeId, String tenantId)`
  - `CognitiveProfileQuery.byName(String entityName, String tenantId)`
  - `CognitiveProfileQuery.byName(String entityName, String subgraphId, String tenantId)`
  - `withDomains(Set<MemoryDomain>)`, `withIncludeEdges(boolean)`, `withMemoryLimit(int)`
  - Fields: `nodeId()`, `entityName()`, `subgraphId()`, `tenantId()`,
    `domains()`, `includeEdges()`, `memoryLimit()`

- [ ] **Step 1: Write the failing tests**

Create test class with validation and factory method tests:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.MemoryDomain;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CognitiveProfileQueryTest {

    private static final String TENANT = "test-tenant";
    private static final String NODE_ID = "node-123";
    private static final String NAME = "Alice";
    private static final String SUBGRAPH = "family";

    @Test
    void byId_createsQueryWithDefaults() {
        var query = CognitiveProfileQuery.byId(NODE_ID, TENANT);

        assertThat(query.nodeId()).isEqualTo(NODE_ID);
        assertThat(query.entityName()).isNull();
        assertThat(query.subgraphId()).isNull();
        assertThat(query.tenantId()).isEqualTo(TENANT);
        assertThat(query.domains()).isEmpty();
        assertThat(query.includeEdges()).isTrue();
        assertThat(query.memoryLimit()).isEqualTo(50);
    }

    @Test
    void byName_createsQueryWithDefaults() {
        var query = CognitiveProfileQuery.byName(NAME, TENANT);

        assertThat(query.nodeId()).isNull();
        assertThat(query.entityName()).isEqualTo(NAME);
        assertThat(query.subgraphId()).isNull();
        assertThat(query.tenantId()).isEqualTo(TENANT);
    }

    @Test
    void byName_withSubgraph() {
        var query = CognitiveProfileQuery.byName(NAME, SUBGRAPH, TENANT);

        assertThat(query.entityName()).isEqualTo(NAME);
        assertThat(query.subgraphId()).isEqualTo(SUBGRAPH);
    }

    @Test
    void withDomains_returnsNewInstance() {
        var original = CognitiveProfileQuery.byId(NODE_ID, TENANT);
        var modified = original.withDomains(Set.of(new MemoryDomain("experience")));

        assertThat(modified.domains()).hasSize(1);
        assertThat(original.domains()).isEmpty();
    }

    @Test
    void withIncludeEdges_returnsNewInstance() {
        var query = CognitiveProfileQuery.byId(NODE_ID, TENANT).withIncludeEdges(false);
        assertThat(query.includeEdges()).isFalse();
    }

    @Test
    void withMemoryLimit_returnsNewInstance() {
        var query = CognitiveProfileQuery.byId(NODE_ID, TENANT).withMemoryLimit(10);
        assertThat(query.memoryLimit()).isEqualTo(10);
    }

    @Test
    void rejectsNullTenantId() {
        assertThatThrownBy(() -> CognitiveProfileQuery.byId(NODE_ID, null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void rejectsBothNodeIdAndEntityName() {
        assertThatThrownBy(() -> new CognitiveProfileQuery(
            NODE_ID, NAME, null, TENANT, Set.of(), true, 50))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsNeitherNodeIdNorEntityName() {
        assertThatThrownBy(() -> new CognitiveProfileQuery(
            null, null, null, TENANT, Set.of(), true, 50))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsInvalidMemoryLimit() {
        assertThatThrownBy(() -> CognitiveProfileQuery.byId(NODE_ID, TENANT).withMemoryLimit(0))
            .isInstanceOf(IllegalArgumentException.class);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileQueryTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: Compilation failure — `CognitiveProfileQuery` does not exist

- [ ] **Step 3: Implement CognitiveProfileQuery**

Create with `ide_create_file`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.MemoryDomain;

import java.util.Objects;
import java.util.Set;

public record CognitiveProfileQuery(
    String nodeId,
    String entityName,
    String subgraphId,
    String tenantId,
    Set<MemoryDomain> domains,
    boolean includeEdges,
    int memoryLimit
) {

    public CognitiveProfileQuery {
        Objects.requireNonNull(tenantId, "tenantId required");
        if (nodeId == null && entityName == null) {
            throw new IllegalArgumentException("nodeId or entityName required");
        }
        if (nodeId != null && entityName != null) {
            throw new IllegalArgumentException("nodeId and entityName are mutually exclusive");
        }
        if (memoryLimit < 1) {
            throw new IllegalArgumentException("memoryLimit must be >= 1, got: " + memoryLimit);
        }
        domains = domains == null ? Set.of() : Set.copyOf(domains);
    }

    public static CognitiveProfileQuery byId(String nodeId, String tenantId) {
        Objects.requireNonNull(nodeId, "nodeId required");
        return new CognitiveProfileQuery(nodeId, null, null, tenantId, Set.of(), true, 50);
    }

    public static CognitiveProfileQuery byName(String entityName, String tenantId) {
        Objects.requireNonNull(entityName, "entityName required");
        return new CognitiveProfileQuery(null, entityName, null, tenantId, Set.of(), true, 50);
    }

    public static CognitiveProfileQuery byName(String entityName, String subgraphId, String tenantId) {
        Objects.requireNonNull(entityName, "entityName required");
        return new CognitiveProfileQuery(null, entityName, subgraphId, tenantId, Set.of(), true, 50);
    }

    public CognitiveProfileQuery withDomains(Set<MemoryDomain> domains) {
        return new CognitiveProfileQuery(nodeId, entityName, subgraphId, tenantId, domains, includeEdges, memoryLimit);
    }

    public CognitiveProfileQuery withIncludeEdges(boolean includeEdges) {
        return new CognitiveProfileQuery(nodeId, entityName, subgraphId, tenantId, domains, includeEdges, memoryLimit);
    }

    public CognitiveProfileQuery withMemoryLimit(int memoryLimit) {
        return new CognitiveProfileQuery(nodeId, entityName, subgraphId, tenantId, domains, includeEdges, memoryLimit);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileQueryTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/src/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): CognitiveProfileQuery record with factories and withX() builders

Refs #243"
```

### Task 2: EntityKnowledge record

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/EntityKnowledge.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/EntityKnowledgeTest.java`

**Interfaces:**
- Consumes: `MindMapNode`, `MindMapEdge` from mindmap-api; `Memory`,
  `MemoryDomain` from memory-api; `AffectTrajectory` from cognitive-index;
  `NodeRef` from mindmap-api
- Produces: `EntityKnowledge` — returned by CognitiveProfile.resolve().
  Key API surface:
  - `EntityKnowledge(MindMapNode, List<MindMapEdge>, Map<MemoryDomain, List<Memory>>, AffectTrajectory, Set<NodeRef>, String)`
  - All fields accessible via record accessors

- [ ] **Step 1: Write the failing tests**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.NodeRef;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class EntityKnowledgeTest {

    private static final Instant NOW = Instant.parse("2026-01-01T12:00:00Z");
    private static final Confidence CONF = new Confidence(ConfidenceOrigin.STATED, 0.8, NOW);
    private static final MemoryDomain EXP = new MemoryDomain("experience");

    @Test
    void rejectsNullNode() {
        assertThatThrownBy(() -> new EntityKnowledge(
            null, List.of(), Map.of(), null, Set.of(), "tenant"))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void rejectsNullTenantId() {
        assertThatThrownBy(() -> new EntityKnowledge(
            StubNode.named("Alice"), List.of(), Map.of(), null, Set.of(), null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void defensiveCopiesOnCollections() {
        var memories = new java.util.HashMap<MemoryDomain, List<Memory>>();
        memories.put(EXP, List.of());
        var refs = new java.util.HashSet<NodeRef>();
        refs.add(new NodeRef("cbr", "case-1", null));

        var ek = new EntityKnowledge(
            StubNode.named("Alice"), List.of(), memories, null, refs, "tenant");

        memories.put(new MemoryDomain("mood"), List.of());
        refs.add(new NodeRef("cbr", "case-2", null));

        assertThat(ek.memories()).hasSize(1);
        assertThat(ek.unresolvedRefs()).hasSize(1);
    }

    @Test
    void trajectoryNullable() {
        var ek = new EntityKnowledge(
            StubNode.named("Alice"), List.of(), Map.of(), null, Set.of(), "tenant");
        assertThat(ek.trajectory()).isNull();
    }

    @Test
    void trajectoryPresent() {
        var trajectory = new AffectTrajectory(0.1, 0.2, 0.05, TrendDirection.IMPROVING, 0.1, 5);
        var ek = new EntityKnowledge(
            StubNode.named("Alice"), List.of(), Map.of(), trajectory, Set.of(), "tenant");
        assertThat(ek.trajectory()).isEqualTo(trajectory);
    }
}
```

This test references a `StubNode` helper. Create it as a package-private test utility
in the same directory:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.NodeRef;

import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

record StubNode(
    String id, String name, String subgraphId,
    Confidence confidence, String provenance,
    Instant createdAt, Instant updatedAt,
    Instant validFrom, Instant validUntil,
    Set<String> traits, Set<NodeRef> refs,
    Double pleasure, Double arousal, Double dominance,
    Map<String, String> properties
) implements MindMapNode {

    static StubNode named(String name) {
        return new StubNode(
            "id-" + name.toLowerCase(), name, "sg-1",
            new Confidence(ConfidenceOrigin.STATED, 0.9, Instant.now()),
            null, Instant.now(), Instant.now(), null, null,
            Set.of(), Set.of(), null, null, null, Map.of());
    }

    static StubNode withRefs(String name, Set<NodeRef> refs) {
        return new StubNode(
            "id-" + name.toLowerCase(), name, "sg-1",
            new Confidence(ConfidenceOrigin.STATED, 0.9, Instant.now()),
            null, Instant.now(), Instant.now(), null, null,
            Set.of(), refs, null, null, null, Map.of());
    }

    @Override
    public Optional<String> property(String key) {
        return Optional.ofNullable(properties.get(key));
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=EntityKnowledgeTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: Compilation failure — `EntityKnowledge` does not exist

- [ ] **Step 3: Implement EntityKnowledge**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.NodeRef;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public record EntityKnowledge(
    MindMapNode node,
    List<MindMapEdge> edges,
    Map<MemoryDomain, List<Memory>> memories,
    AffectTrajectory trajectory,
    Set<NodeRef> unresolvedRefs,
    String tenantId
) {

    public EntityKnowledge {
        Objects.requireNonNull(node, "node required");
        Objects.requireNonNull(tenantId, "tenantId required");
        edges = edges == null ? List.of() : List.copyOf(edges);
        memories = memories == null ? Map.of() : Map.copyOf(memories);
        unresolvedRefs = unresolvedRefs == null ? Set.of() : Set.copyOf(unresolvedRefs);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=EntityKnowledgeTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/src/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): EntityKnowledge record — cross-store entity resolution result

Refs #243"
```

---

## Batch 2: CognitiveProfile CDI Bean

### Task 3: CognitiveProfile resolve() — core resolution

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfile.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveProfileTest.java`

**Interfaces:**
- Consumes: `CognitiveProfileQuery` (Task 1), `EntityKnowledge` (Task 2),
  `AffectTrajectoryAnalyzer.analyze(List<Memory>)`,
  `MindMapStore.getNode/resolveNode/neighbors`,
  `CaseMemoryStore.query(MemoryQuery)`,
  `InMemoryMindMapStore` (test dep), `StubMemoryStore` (from
  TemporalIndexTest pattern, extended with PAD support)
- Produces: `CognitiveProfile.resolve(CognitiveProfileQuery) → Optional<EntityKnowledge>`

- [ ] **Step 1: Write the failing tests — node resolution + basic structure**

Create test class with the StubMemoryStore from TemporalIndexTest
extended to support PAD fields, plus tests for ID-based resolution,
name-based resolution, and not-found case:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.EraseRequest;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.MemoryInput;
import io.casehub.neocortex.memory.MemoryQuery;
import io.casehub.neocortex.mindmap.EdgeInput;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.NodeRef;
import io.casehub.neocortex.mindmap.SubgraphInput;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CopyOnWriteArrayList;

import static org.assertj.core.api.Assertions.assertThat;

class CognitiveProfileTest {

    private static final String TENANT = "test-tenant";
    private static final String SUBGRAPH = "test-subgraph";
    private static final Instant NOW = Instant.parse("2026-01-01T12:00:00Z");
    private static final Confidence CONF = new Confidence(ConfidenceOrigin.STATED, 0.8, NOW);
    private static final MemoryDomain EXPERIENCE = new MemoryDomain("experience");
    private static final MemoryDomain RELATIONSHIP = new MemoryDomain("relationship");
    private static final MemoryDomain AFFECT = new MemoryDomain("affect");

    private InMemoryMindMapStore mindMapStore;
    private TestMemoryStore memoryStore;
    private CognitiveProfile profile;

    @BeforeEach
    void setUp() {
        mindMapStore = new InMemoryMindMapStore();
        memoryStore = new TestMemoryStore();
        profile = new CognitiveProfile(mindMapStore, memoryStore, null);
        mindMapStore.createSubgraph(new SubgraphInput(SUBGRAPH, null), TENANT);
    }

    @Test
    void resolveById_returnsEntityKnowledge() {
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);

        var result = profile.resolve(CognitiveProfileQuery.byId(nodeId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().node().name()).isEqualTo("Alice");
        assertThat(result.get().tenantId()).isEqualTo(TENANT);
    }

    @Test
    void resolveByName_returnsEntityKnowledge() {
        mindMapStore.addNode(node("Alice"), TENANT);

        var result = profile.resolve(CognitiveProfileQuery.byName("Alice", SUBGRAPH, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().node().name()).isEqualTo("Alice");
    }

    @Test
    void resolveById_notFound_returnsEmpty() {
        var result = profile.resolve(CognitiveProfileQuery.byId("nonexistent", TENANT));
        assertThat(result).isEmpty();
    }

    @Test
    void resolveByName_notFound_returnsEmpty() {
        var result = profile.resolve(CognitiveProfileQuery.byName("Nobody", SUBGRAPH, TENANT));
        assertThat(result).isEmpty();
    }

    @Test
    void includesDirectEdges() {
        String aliceId = mindMapStore.addNode(node("Alice"), TENANT);
        String bobId = mindMapStore.addNode(node("Bob"), TENANT);
        mindMapStore.addEdge(new EdgeInput(aliceId, bobId, "knows", CONF, null, null, null, null, null, null, Map.of()), TENANT);

        var result = profile.resolve(CognitiveProfileQuery.byId(aliceId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().edges()).hasSize(1);
        assertThat(result.get().edges().getFirst().edgeType()).isEqualTo("knows");
    }

    @Test
    void excludesEdges_whenIncludeEdgesFalse() {
        String aliceId = mindMapStore.addNode(node("Alice"), TENANT);
        String bobId = mindMapStore.addNode(node("Bob"), TENANT);
        mindMapStore.addEdge(new EdgeInput(aliceId, bobId, "knows", CONF, null, null, null, null, null, null, Map.of()), TENANT);

        var query = CognitiveProfileQuery.byId(aliceId, TENANT).withIncludeEdges(false);
        var result = profile.resolve(query);

        assertThat(result).isPresent();
        assertThat(result.get().edges()).isEmpty();
    }

    @Test
    void queriesMemoriesByDomain() {
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);
        memoryStore.store(new MemoryInput(nodeId, EXPERIENCE, TENANT, null, "Alice had an experience", Map.of(), CONF, null, null, null));
        memoryStore.store(new MemoryInput("Alice", RELATIONSHIP, TENANT, null, "Alice relates to Bob", Map.of(), CONF, null, null, null));

        var result = profile.resolve(CognitiveProfileQuery.byId(nodeId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().memories()).containsKey(EXPERIENCE);
        assertThat(result.get().memories()).containsKey(RELATIONSHIP);
        assertThat(result.get().memories().get(EXPERIENCE)).hasSize(1);
        assertThat(result.get().memories().get(RELATIONSHIP)).hasSize(1);
    }

    @Test
    void domainSelection_onlyQueriesRequestedDomains() {
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);
        memoryStore.store(new MemoryInput(nodeId, EXPERIENCE, TENANT, null, "experience fact", Map.of(), CONF, null, null, null));
        memoryStore.store(new MemoryInput(nodeId, RELATIONSHIP, TENANT, null, "relationship fact", Map.of(), CONF, null, null, null));

        var query = CognitiveProfileQuery.byId(nodeId, TENANT)
            .withDomains(Set.of(EXPERIENCE));
        var result = profile.resolve(query);

        assertThat(result).isPresent();
        assertThat(result.get().memories()).containsKey(EXPERIENCE);
        assertThat(result.get().memories()).doesNotContainKey(RELATIONSHIP);
    }

    @Test
    void dualEntityId_findsMemoriesStoredUnderBothNodeIdAndName() {
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);
        memoryStore.store(new MemoryInput(nodeId, EXPERIENCE, TENANT, null, "stored by nodeId", Map.of(), CONF, null, null, null));
        memoryStore.store(new MemoryInput("Alice", EXPERIENCE, TENANT, null, "stored by name", Map.of(), CONF, null, null, null));

        var result = profile.resolve(CognitiveProfileQuery.byId(nodeId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().memories().get(EXPERIENCE)).hasSize(2);
    }

    @Test
    void computesAffectTrajectory() {
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);
        memoryStore.store(new MemoryInput(nodeId, AFFECT, TENANT, null, "PAD update", Map.of(), CONF, -0.5, 0.3, 0.1));
        memoryStore.store(new MemoryInput(nodeId, AFFECT, TENANT, null, "PAD update", Map.of(), CONF, -0.7, 0.5, -0.1));

        var result = profile.resolve(CognitiveProfileQuery.byId(nodeId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().trajectory()).isNotNull();
        assertThat(result.get().trajectory().trend()).isEqualTo(TrendDirection.WORSENING);
        assertThat(result.get().trajectory().sampleCount()).isEqualTo(2);
    }

    @Test
    void trajectoryComputed_evenWhenAffectDomainNotRequested() {
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);
        memoryStore.store(new MemoryInput(nodeId, AFFECT, TENANT, null, "PAD update", Map.of(), CONF, 0.5, 0.3, 0.1));
        memoryStore.store(new MemoryInput(nodeId, AFFECT, TENANT, null, "PAD update", Map.of(), CONF, 0.7, 0.2, 0.2));

        var query = CognitiveProfileQuery.byId(nodeId, TENANT)
            .withDomains(Set.of(EXPERIENCE));
        var result = profile.resolve(query);

        assertThat(result).isPresent();
        assertThat(result.get().trajectory()).isNotNull();
        assertThat(result.get().memories()).doesNotContainKey(AFFECT);
    }

    @Test
    void nodeRefMemory_followsSchemeMemory() {
        String linkedEntityId = "external-entity-123";
        var refs = Set.of(new NodeRef("memory", linkedEntityId, null));
        String nodeId = mindMapStore.addNode(nodeWithRefs("Alice", refs), TENANT);
        memoryStore.store(new MemoryInput(linkedEntityId, EXPERIENCE, TENANT, null, "linked memory", Map.of(), CONF, null, null, null));

        var result = profile.resolve(CognitiveProfileQuery.byId(nodeId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().memories().get(EXPERIENCE))
            .anyMatch(m -> m.text().equals("linked memory"));
    }

    @Test
    void nodeRefCbr_recordedAsUnresolved() {
        var refs = Set.of(new NodeRef("cbr", "case-42", null));
        String nodeId = mindMapStore.addNode(nodeWithRefs("Alice", refs), TENANT);

        var result = profile.resolve(CognitiveProfileQuery.byId(nodeId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().unresolvedRefs())
            .containsExactly(new NodeRef("cbr", "case-42", null));
    }

    @Test
    void gracefulDegradation_noMemoryStore() {
        var profileNoMemory = new CognitiveProfile(mindMapStore, null, null);
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);

        var result = profileNoMemory.resolve(CognitiveProfileQuery.byId(nodeId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().node().name()).isEqualTo("Alice");
        assertThat(result.get().memories()).isEmpty();
        assertThat(result.get().trajectory()).isNull();
    }

    @Test
    void gracefulDegradation_noMindMapStore() {
        var profileNoMindMap = new CognitiveProfile(null, memoryStore, null);

        var result = profileNoMindMap.resolve(CognitiveProfileQuery.byId("any-id", TENANT));

        assertThat(result).isEmpty();
    }

    @Test
    void memoryLimit_appliedPerDomain() {
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);
        for (int i = 0; i < 10; i++) {
            memoryStore.store(new MemoryInput(nodeId, EXPERIENCE, TENANT, null, "fact-" + i, Map.of(), CONF, null, null, null));
        }

        var query = CognitiveProfileQuery.byId(nodeId, TENANT).withMemoryLimit(3);
        var result = profile.resolve(query);

        assertThat(result).isPresent();
        assertThat(result.get().memories().get(EXPERIENCE)).hasSize(3);
    }

    @Test
    void emptyEntity_nodeExistsButNoMemoriesOrEdges() {
        String nodeId = mindMapStore.addNode(node("Alice"), TENANT);

        var result = profile.resolve(CognitiveProfileQuery.byId(nodeId, TENANT));

        assertThat(result).isPresent();
        assertThat(result.get().edges()).isEmpty();
        assertThat(result.get().memories()).isEmpty();
        assertThat(result.get().trajectory()).isNull();
        assertThat(result.get().unresolvedRefs()).isEmpty();
    }

    // --- helpers ---

    private static NodeInput node(String name) {
        return new NodeInput(name, SUBGRAPH, CONF, null, null, null, null, null, null, null, null, Map.of());
    }

    private static NodeInput nodeWithRefs(String name, Set<NodeRef> refs) {
        return new NodeInput(name, SUBGRAPH, CONF, null, null, refs, null, null, null, null, null, Map.of());
    }

    static class TestMemoryStore implements CaseMemoryStore {
        private final List<Memory> memories = new CopyOnWriteArrayList<>();

        @Override
        public String store(MemoryInput input) {
            String id = UUID.randomUUID().toString();
            memories.add(new Memory(id, input.entityId(), input.domain(), input.tenantId(),
                input.caseId(), input.text(), input.attributes(), Instant.now(),
                input.confidence(), input.pleasure(), input.arousal(), input.dominance()));
            return id;
        }

        @Override
        public List<Memory> query(MemoryQuery query) {
            return memories.stream()
                .filter(m -> query.entityIds().contains(m.entityId()))
                .filter(m -> m.domain().equals(query.domain()))
                .filter(m -> m.tenantId().equals(query.tenantId()))
                .filter(m -> query.since() == null || !m.createdAt().isBefore(query.since()))
                .limit(query.limit())
                .toList();
        }

        @Override
        public int erase(EraseRequest request) {
            return 0;
        }
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: Compilation failure — `CognitiveProfile` class does not exist

- [ ] **Step 3: Implement CognitiveProfile**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.MemoryOrder;
import io.casehub.neocortex.memory.MemoryQuery;
import io.casehub.neocortex.memory.cbr.CbrCaseMemoryStore;
import io.casehub.neocortex.memory.mood.AffectEvents;
import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeRef;
import io.casehub.neocortex.memory.experience.ExperienceEvents;
import io.casehub.neocortex.memory.relationship.RelationshipEvents;
import io.casehub.neocortex.memory.reflection.ReflectionEvents;
import io.casehub.neocortex.memory.mood.MoodEvents;
import io.casehub.neocortex.memory.engagement.EngagementEvents;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

@ApplicationScoped
public class CognitiveProfile {

    static final Set<MemoryDomain> DEFAULT_DOMAINS = Set.of(
        ExperienceEvents.DOMAIN,
        RelationshipEvents.DOMAIN,
        ReflectionEvents.DOMAIN,
        MoodEvents.DOMAIN,
        EngagementEvents.DOMAIN,
        AffectEvents.DOMAIN
    );

    private final MindMapStore mindMapStore;
    private final CaseMemoryStore memoryStore;
    private final CbrCaseMemoryStore cbrStore;

    @Inject
    public CognitiveProfile(Instance<MindMapStore> mindMapStore,
                            Instance<CaseMemoryStore> memoryStore,
                            Instance<CbrCaseMemoryStore> cbrStore) {
        this.mindMapStore = mindMapStore != null && mindMapStore.isResolvable() ? mindMapStore.get() : null;
        this.memoryStore = memoryStore != null && memoryStore.isResolvable() ? memoryStore.get() : null;
        this.cbrStore = cbrStore != null && cbrStore.isResolvable() ? cbrStore.get() : null;
    }

    CognitiveProfile(MindMapStore mindMapStore, CaseMemoryStore memoryStore, CbrCaseMemoryStore cbrStore) {
        this.mindMapStore = mindMapStore;
        this.memoryStore = memoryStore;
        this.cbrStore = cbrStore;
    }

    public Optional<EntityKnowledge> resolve(CognitiveProfileQuery query) {
        if (mindMapStore == null) {
            return Optional.empty();
        }

        MindMapNode node = resolveNode(query);
        if (node == null) {
            return Optional.empty();
        }

        List<String> entityIds = collectEntityIds(node);
        Set<NodeRef> unresolvedRefs = collectUnresolvedRefs(node);

        List<MindMapEdge> edges = query.includeEdges()
            ? mindMapStore.neighbors(node.id(), query.tenantId())
            : List.of();

        Set<MemoryDomain> domains = query.domains().isEmpty()
            ? DEFAULT_DOMAINS : query.domains();

        Map<MemoryDomain, List<Memory>> memories = queryMemories(entityIds, domains, query);

        AffectTrajectory trajectory = computeTrajectory(entityIds, memories, query);

        return Optional.of(new EntityKnowledge(node, edges, memories, trajectory, unresolvedRefs, query.tenantId()));
    }

    private MindMapNode resolveNode(CognitiveProfileQuery query) {
        try {
            if (query.nodeId() != null) {
                return mindMapStore.getNode(query.nodeId(), query.tenantId());
            } else {
                return mindMapStore.resolveNode(query.entityName(), query.subgraphId(), query.tenantId());
            }
        } catch (RuntimeException e) {
            return null;
        }
    }

    private List<String> collectEntityIds(MindMapNode node) {
        Set<String> ids = new LinkedHashSet<>();
        ids.add(node.id());
        ids.add(node.name());
        for (NodeRef ref : node.refs()) {
            if ("memory".equals(ref.scheme())) {
                ids.add(ref.id());
            }
        }
        return List.copyOf(ids);
    }

    private Set<NodeRef> collectUnresolvedRefs(MindMapNode node) {
        Set<NodeRef> unresolved = new LinkedHashSet<>();
        for (NodeRef ref : node.refs()) {
            if (!"memory".equals(ref.scheme())) {
                unresolved.add(ref);
            }
        }
        return unresolved;
    }

    private Map<MemoryDomain, List<Memory>> queryMemories(
            List<String> entityIds, Set<MemoryDomain> domains,
            CognitiveProfileQuery query) {
        if (memoryStore == null) {
            return Map.of();
        }
        Map<MemoryDomain, List<Memory>> result = new LinkedHashMap<>();
        for (MemoryDomain domain : domains) {
            List<Memory> memories = memoryStore.query(
                MemoryQuery.forEntities(entityIds, domain, query.tenantId())
                    .withLimit(query.memoryLimit())
                    .withOrder(MemoryOrder.CHRONOLOGICAL));
            if (!memories.isEmpty()) {
                result.put(domain, memories);
            }
        }
        return result;
    }

    private AffectTrajectory computeTrajectory(
            List<String> entityIds,
            Map<MemoryDomain, List<Memory>> memories,
            CognitiveProfileQuery query) {
        if (memoryStore == null) {
            return null;
        }

        List<Memory> affectMemories = memories.get(AffectEvents.DOMAIN);
        if (affectMemories == null) {
            affectMemories = memoryStore.query(
                MemoryQuery.forEntities(entityIds, AffectEvents.DOMAIN, query.tenantId())
                    .withLimit(query.memoryLimit())
                    .withOrder(MemoryOrder.CHRONOLOGICAL));
        }

        if (affectMemories.isEmpty()) {
            return null;
        }
        return AffectTrajectoryAnalyzer.analyze(affectMemories);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileTest -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: All 17 tests PASS

- [ ] **Step 5: Run full cognitive-index test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: All existing tests + new tests PASS (no regressions)

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/src/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): CognitiveProfile — cross-store entity resolution

CDI @ApplicationScoped bean with Instance<T> graceful degradation.
resolve() aggregates MindMap node, edges, memories across 6 domains,
affect trajectory, and NodeRef following into EntityKnowledge record.

Refs #243"
```

---

## Batch 3: Documentation and Roadmap Update

### Task 4: Update CLAUDE.md and mark roadmap DONE

**Files:**
- Modify: `CLAUDE.md` — add CognitiveProfile to cognitive-index module description
- Modify: `docs/guides/cognitive-architecture-roadmap.md` — mark §4a DONE

**Interfaces:**
- Consumes: completed CognitiveProfile implementation
- Produces: updated documentation

- [ ] **Step 1: Update CLAUDE.md cognitive-index description**

Add to the cognitive-index entry in the module structure section. The
current description reads:

```
cognitive-index/    — cross-store cognitive query tier: TemporalIndex (...), TemporalFocus (...). ...
```

Append CognitiveProfile, CognitiveProfileQuery, EntityKnowledge to
the description. Use the Edit tool (markdown, not Java).

- [ ] **Step 2: Mark roadmap §4a as DONE**

In `docs/guides/cognitive-architecture-roadmap.md`, update the §4a
heading to append `— **DONE** (#243)`. Add a summary paragraph below
describing what was implemented — same pattern as §1a, §2a, etc.

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md docs/guides/cognitive-architecture-roadmap.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "docs: mark roadmap §4a DONE, update CLAUDE.md for CognitiveProfile

Refs #243"
```

## References

- [2026-08-31-cognitive-profile-design.md] — design spec this plan implements
- [TemporalIndex.java] — CDI + Instance<T> pattern, test structure
- [AffectTrajectoryAnalyzer.java] — trajectory composition target
- [AffectEvents.java] — affect domain constant
- [TemporalIndexTest.java] — StubMemoryStore test pattern
- [NodeInput.java, EdgeInput.java] — constructors for test data
- [MindMapStore.java] — resolveNode, getNode, neighbors API
- [MemoryQuery.java] — forEntities multi-entityId query
- [GE-20260805-a28f5b] — three-tier CDI composition pattern
- [GE-20260630-815259] — cross-repo SPI displacement gotcha
- [GitHub #243] — focal issue
- [GitHub #253] — parent epic
