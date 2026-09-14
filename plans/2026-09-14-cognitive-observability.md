# Cognitive Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #333 — epic: cognitive observability
**Issue group:** #322, #333

**Goal:** Expose the cognitive subsystem's internal state via MCP tools
(cognition_inspect, cognition_entity, cognition_health, cognition_diff,
cognition_trace) backed by mutation tracking and snapshot persistence.

**Architecture:** Three layers — Layer 1 wraps existing MindMapAnalyzer
and CognitiveProfile as @McpDomain GraphQL resolvers. Layer 2 adds a
MutationTrackingDecorator on MindMapStore that persists every graph
mutation to a SnapshotStore SPI (SQLite impl), with keyframe/delta
model. Layer 3 adds temporal query tools that read from the mutation
log. MutationContext ThreadLocal in mindmap-api enables source tagging
without circular dependencies.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI decorators, SmallRye
GraphQL (@McpDomain auto-gen via platform), SQLite + HikariCP + Flyway,
Jackson for JSON serialization.

## Global Constraints

- Java 21 source level, Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All new modules: groupId `io.casehub`, parent `casehub-neocortex-parent`
- Root package: `io.casehub.neocortex.cognitive.observability`
- ConsolidationPhase.run() remains void — no SPI change
- Decorator pattern: runtime class extends AbstractForwardingMindMapStore + CDI wiring class extends runtime (see AffectTrajectoryCdiDecorator)
- @Decorator @Priority(20) — lowest = runs closest to bean, after TraitApplication(70) and AffectTrajectory(65)
- Filter synthetic Summary-trait nodes from k-core results in health tool
- All observability tools are read-only — never write to graph during observation
- MindMapStore.addNode returns String (nodeId), not MindMapNode
- MindMapStore.addEdge returns String (edgeId)
- MindMapStore.mergeNodes takes (keepNodeId, removeNodeId, tenantId) and returns MergeResult

---

## Batch 1: Layer 1 — Live View

### Task 1: cognitive-observability module scaffold + CognitionInspectResult type

**Files:**
- Create: `cognitive-observability/pom.xml`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionInspectResult.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/CognitionInspectResultTest.java`
- Modify: `pom.xml` (root — add `<module>cognitive-observability</module>`)

**Interfaces:**
- Consumes: `MindMapStore` (mindmap-api), `MindMapNode` (mindmap-api), `MindMapSubgraph` (mindmap-api)
- Produces: `CognitionInspectResult` record (subgraphStats: List<SubgraphStat>, confidenceHistogram: Map<String, Integer>)

- [ ] **Step 1: Create module pom.xml**

Model after `cognitive-index/pom.xml`. Dependencies: `casehub-neocortex-cognitive-index`, `casehub-neocortex-cognitive-api`, `casehub-neocortex-mindmap-api`, `casehub-neocortex-mindmap` (for MindMapAnalyzer), `casehub-neocortex-memory-api`. Add `<module>cognitive-observability</module>` to root pom.xml.

```xml
<artifactId>casehub-neocortex-cognitive-observability</artifactId>
<name>casehub-neocortex-cognitive-observability</name>
```

- [ ] **Step 2: Write test for CognitionInspectResult construction**

```java
@Test
void shouldBuildInspectResult() {
    var stats = List.of(new CognitionInspectResult.SubgraphStat(
        "sg1", "person", 10, 15, 0.72,
        Map.of("Personable", 3L, "Projectlike", 2L)));
    var histogram = Map.of(
        "0.0-0.2", 2, "0.2-0.4", 3, "0.4-0.6", 5,
        "0.6-0.8", 8, "0.8-1.0", 7);
    var result = new CognitionInspectResult(stats, histogram);
    assertEquals(1, result.subgraphStats().size());
    assertEquals(10, result.subgraphStats().getFirst().nodeCount());
    assertEquals(5, result.confidenceHistogram().get("0.4-0.6"));
}
```

- [ ] **Step 3: Run test — expect compilation failure (class doesn't exist)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability -Dtest=CognitionInspectResultTest`

- [ ] **Step 4: Implement CognitionInspectResult**

```java
public record CognitionInspectResult(
    List<SubgraphStat> subgraphStats,
    Map<String, Integer> confidenceHistogram
) {
    public record SubgraphStat(
        String subgraphId,
        String subgraphType,
        int nodeCount,
        int edgeCount,
        double avgConfidence,
        Map<String, Long> traitDistribution
    ) {}
}
```

- [ ] **Step 5: Run test — expect PASS**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability -Dtest=CognitionInspectResultTest`

- [ ] **Step 6: Commit**

```
feat(cognitive-observability): scaffold module + CognitionInspectResult type

Refs #333
```

### Task 2: CognitionInspectService + cognition_inspect logic

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionInspectService.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/CognitionInspectServiceTest.java`

**Interfaces:**
- Consumes: `MindMapStore.listSubgraphs(tenantId)`, `MindMapStore.nodesIn(subgraphId, tenantId)`, `MindMapNode.confidence()`, `MindMapNode.traits()`
- Produces: `CognitionInspectService.inspect(MindMapStore store, String tenantId, String subgraphId) → CognitionInspectResult`

- [ ] **Step 1: Write test — single subgraph inspection**

```java
@Test
void shouldInspectSingleSubgraph() {
    var store = new InMemoryMindMapStore();
    String sgId = store.createSubgraph(new SubgraphInput("people", "person"), "t1");
    store.addNode(NodeInput.builder("Alice").subgraphId(sgId)
        .confidence(Confidence.stated()).trait("Personable").build(), "t1");
    store.addNode(NodeInput.builder("Bob").subgraphId(sgId)
        .confidence(new Confidence(ConfidenceOrigin.INFERRED, 0.5, null)).trait("Personable").build(), "t1");

    var result = CognitionInspectService.inspect(store, "t1", sgId);

    assertEquals(1, result.subgraphStats().size());
    assertEquals(2, result.subgraphStats().getFirst().nodeCount());
    assertTrue(result.confidenceHistogram().get("0.8-1.0") > 0
        || result.confidenceHistogram().get("0.6-0.8") > 0);
}
```

- [ ] **Step 2: Write test — null subgraphId aggregates across all subgraphs**

```java
@Test
void shouldAggregateAcrossSubgraphs() {
    var store = new InMemoryMindMapStore();
    store.createSubgraph(new SubgraphInput("people", "person"), "t1");
    store.createSubgraph(new SubgraphInput("projects", "project"), "t1");
    store.addNode(NodeInput.builder("Alice").subgraphId("people")
        .confidence(Confidence.stated()).build(), "t1");
    store.addNode(NodeInput.builder("ProjectX").subgraphId("projects")
        .confidence(Confidence.stated()).build(), "t1");

    var result = CognitionInspectService.inspect(store, "t1", null);

    assertEquals(2, result.subgraphStats().size());
}
```

- [ ] **Step 3: Run tests — expect FAIL**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability -Dtest=CognitionInspectServiceTest`

- [ ] **Step 4: Implement CognitionInspectService**

Static utility class. When subgraphId is null, iterates `store.listSubgraphs(tenantId)`. Builds per-subgraph stats (nodeCount, edgeCount from `nodesIn` + neighbor count, avgConfidence, trait distribution). Builds confidence histogram with 5 buckets.

- [ ] **Step 5: Run tests — expect PASS**

- [ ] **Step 6: Commit**

```
feat(cognitive-observability): CognitionInspectService with per-subgraph stats

Refs #333
```

### Task 3: GraphHealthReport + CognitionHealthService

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/GraphHealthReport.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionHealthService.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/CognitionHealthServiceTest.java`

**Interfaces:**
- Consumes: `MindMapAnalyzer.orphanNodes()`, `MindMapAnalyzer.contradictions()`, `MindMapAnalyzer.lowConfidenceCluster()`, `MindMapAnalyzer.unvalidatedEdgeRatio()`, `MindMapAnalyzer.staleNodes()`, `MindMapAnalyzer.subgraphDensity()`, `MindMapAnalyzer.kCores()`
- Produces: `CognitionHealthService.health(MindMapStore, String tenantId, String subgraphId, int staleThresholdDays, double lowConfidenceThreshold) → GraphHealthReport`

- [ ] **Step 1: Write test — healthy graph returns clean report**

```java
@Test
void shouldReportHealthyGraph() {
    var store = new InMemoryMindMapStore();
    String sgId = store.createSubgraph(new SubgraphInput("people", "person"), "t1");
    String a = store.addNode(NodeInput.builder("Alice").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    String b = store.addNode(NodeInput.builder("Bob").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    store.addEdge(EdgeInput.builder(a, b, "knows").build(), "t1");

    var report = CognitionHealthService.health(store, "t1", sgId, 30, 0.3);

    assertEquals(0, report.orphanNodes().size());
    assertEquals(0, report.contradictions().size());
}
```

- [ ] **Step 2: Write test — graph with orphans detected**

```java
@Test
void shouldDetectOrphanNodes() {
    var store = new InMemoryMindMapStore();
    String sgId = store.createSubgraph(new SubgraphInput("people", "person"), "t1");
    store.addNode(NodeInput.builder("Lonely").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");

    var report = CognitionHealthService.health(store, "t1", sgId, 30, 0.3);

    assertEquals(1, report.orphanNodes().size());
}
```

- [ ] **Step 3: Write test — Summary-trait nodes filtered from kCores**

```java
@Test
void shouldFilterSyntheticNodesFromKCores() {
    var store = new InMemoryMindMapStore();
    String sgId = store.createSubgraph(new SubgraphInput("people", "person"), "t1");
    // Add a Summary-trait node (synthetic)
    store.addNode(NodeInput.builder("Summary Node").subgraphId(sgId)
        .confidence(Confidence.stated()).trait("Summary").build(), "t1");
    // Add real nodes with edges to form k-cores
    String a = store.addNode(NodeInput.builder("A").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    String b = store.addNode(NodeInput.builder("B").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    store.addEdge(EdgeInput.builder(a, b, "knows").build(), "t1");

    var report = CognitionHealthService.health(store, "t1", sgId, 30, 0.3);

    // Summary node should not appear in any k-core membership
    for (var kCore : report.kCores()) {
        for (String nodeId : kCore.nodeIds()) {
            var node = store.getNode(nodeId, "t1");
            assertFalse(node.traits().contains("Summary"),
                "Summary-trait nodes should be filtered from k-cores");
        }
    }
}
```

- [ ] **Step 4: Run tests — expect FAIL**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability -Dtest=CognitionHealthServiceTest`

- [ ] **Step 5: Implement GraphHealthReport record + CognitionHealthService**

GraphHealthReport wraps MindMapAnalyzer results. CognitionHealthService calls each analyzer method, filters Summary-trait nodes from k-core results. When subgraphId is null, iterates subgraphs and collects per-subgraph results without lossy aggregation.

- [ ] **Step 6: Run tests — expect PASS**

- [ ] **Step 7: Commit**

```
feat(cognitive-observability): GraphHealthReport + CognitionHealthService

Filters synthetic Summary-trait nodes from k-core analysis.

Refs #333
```

### Task 4: GraphSerializer utility (toJson + toMermaid)

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/GraphSerializer.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/GraphSerializerTest.java`

**Interfaces:**
- Consumes: `MindMapNode`, `MindMapEdge` (mindmap-api interfaces)
- Produces: `GraphSerializer.toJson(List<MindMapNode>, List<MindMapEdge>) → String`, `GraphSerializer.toMermaid(List<MindMapNode>, List<MindMapEdge>) → String`, `GraphSerializer.fromJson(String) → GraphSerializer.GraphData`

- [ ] **Step 1: Write test — toJson round-trip**

```java
@Test
void shouldRoundTripJson() {
    var store = new InMemoryMindMapStore();
    String sgId = store.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    String a = store.addNode(NodeInput.builder("Alpha").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    String b = store.addNode(NodeInput.builder("Beta").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    store.addEdge(EdgeInput.builder(a, b, "relates_to").build(), "t1");

    var nodes = store.nodesIn(sgId, "t1");
    var edges = store.neighbors(a, "t1");

    String json = GraphSerializer.toJson(nodes, edges);
    var data = GraphSerializer.fromJson(json);

    assertEquals(2, data.nodes().size());
    assertEquals(1, data.edges().size());
}
```

- [ ] **Step 2: Write test — toMermaid produces valid graph syntax**

```java
@Test
void shouldProduceMermaidSyntax() {
    var store = new InMemoryMindMapStore();
    String sgId = store.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    String a = store.addNode(NodeInput.builder("Alpha").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    String b = store.addNode(NodeInput.builder("Beta").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    store.addEdge(EdgeInput.builder(a, b, "relates_to").build(), "t1");

    var nodes = store.nodesIn(sgId, "t1");
    var edges = store.neighbors(a, "t1");

    String mermaid = GraphSerializer.toMermaid(nodes, edges);

    assertTrue(mermaid.startsWith("graph TD"));
    assertTrue(mermaid.contains("relates_to"));
}
```

- [ ] **Step 3: Run tests — expect FAIL**

- [ ] **Step 4: Implement GraphSerializer**

Jackson ObjectMapper for JSON (serialize node/edge interfaces to data records). Mermaid via StringBuilder: `graph TD\n` header, nodes as `id["name"]`, edges as `id1 -->|edgeType| id2`.

- [ ] **Step 5: Run tests — expect PASS**

- [ ] **Step 6: Commit**

```
feat(cognitive-observability): GraphSerializer with JSON and Mermaid export

Refs #333
```

### Task 5: @McpDomain GraphQL resolvers for Layer 1

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionResolver.java`

**Interfaces:**
- Consumes: `CognitionInspectService`, `CognitionHealthService`, `CognitiveProfile`, `MindMapStore`, `GraphSerializer`
- Produces: `CognitionResolver` (@McpDomain("cognition") @GraphQLApi) — inspect(), entity(), health() GraphQL queries

- [ ] **Step 1: Create CognitionResolver**

Single resolver class with all 3 Layer 1 queries. @McpDomain("cognition"), @GraphQLApi. Each @Query/@PlatformQuery delegates to the corresponding service. cognition_entity delegates to CognitiveProfile.resolve() directly.

```java
@McpDomain("cognition")
@GraphQLApi
@ApplicationScoped
public class CognitionResolver {

    @Inject MindMapStore store;
    @Inject Instance<CognitiveProfile> cognitiveProfile;

    @Query
    @PlatformQuery("Aggregate stats: node/edge counts per subgraph, confidence distribution, trait summary")
    public CognitionInspectResult inspect(@Name("tenantId") String tenantId,
                                           @Name("subgraphId") @Nullable String subgraphId) {
        return CognitionInspectService.inspect(store, tenantId, subgraphId);
    }

    @Query
    @PlatformQuery("Entity deep dive: node, edges, traits, PAD, confidence, affect trajectory, related memories")
    public EntityKnowledge entity(@Name("tenantId") String tenantId,
                                   @Name("entityName") @Nullable String entityName,
                                   @Name("nodeId") @Nullable String nodeId,
                                   @Name("subgraphId") @Nullable String subgraphId,
                                   @Name("includeMemories") @DefaultValue("true") boolean includeMemories,
                                   @Name("memoryLimit") @DefaultValue("10") int memoryLimit) {
        // Delegate to CognitiveProfile.resolve()
    }

    @Query
    @PlatformQuery("Graph health: orphans, contradictions, low-confidence clusters, unvalidated edges, stale nodes")
    public GraphHealthReport health(@Name("tenantId") String tenantId,
                                     @Name("subgraphId") @Nullable String subgraphId,
                                     @Name("staleThresholdDays") @DefaultValue("30") int staleThresholdDays,
                                     @Name("lowConfidenceThreshold") @DefaultValue("0.3") double lowConfidenceThreshold) {
        return CognitionHealthService.health(store, tenantId, subgraphId, staleThresholdDays, lowConfidenceThreshold);
    }
}
```

- [ ] **Step 2: Add platform-api dependency to cognitive-observability pom.xml**

SmallRye GraphQL annotations (@Query, @Name, @DefaultValue) + platform-api (@McpDomain, @PlatformQuery).

- [ ] **Step 3: Compile check**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognitive-observability`

- [ ] **Step 4: Commit**

```
feat(cognitive-observability): @McpDomain GraphQL resolver for Layer 1 tools

CognitionResolver exposes inspect, entity, health via platform MCP auto-gen.

Refs #333
```

### Task 6: Build verification — Layer 1 complete

**Files:**
- None new — verify everything compiles together

- [ ] **Step 1: Run full build of cognitive-observability**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl cognitive-observability`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 2: Run full project build to check no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit if any adjustments needed**

---

## Batch 2: Layer 2 — Snapshot + Delta Infrastructure

### Task 7: MutationContext in mindmap-api

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MutationContext.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/MutationContextTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `MutationContext.set(String source)`, `MutationContext.get() → String`, `MutationContext.clear()`

- [ ] **Step 1: Write test for ThreadLocal behavior**

```java
@Test
void shouldDefaultToManual() {
    MutationContext.clear();
    assertEquals("manual", MutationContext.get());
}

@Test
void shouldSetAndGet() {
    MutationContext.set("consolidation:MergeDetectionPhase");
    assertEquals("consolidation:MergeDetectionPhase", MutationContext.get());
    MutationContext.clear();
    assertEquals("manual", MutationContext.get());
}
```

- [ ] **Step 2: Run test — expect FAIL**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=MutationContextTest`

- [ ] **Step 3: Implement MutationContext**

```java
public final class MutationContext {
    private static final ThreadLocal<String> SOURCE = ThreadLocal.withInitial(() -> "manual");

    private MutationContext() {}

    public static void set(String source) { SOURCE.set(source); }
    public static String get() { return SOURCE.get(); }
    public static void clear() { SOURCE.remove(); }
}
```

- [ ] **Step 4: Run test — expect PASS**

- [ ] **Step 5: Commit**

```
feat(mindmap-api): add MutationContext ThreadLocal for mutation source tagging

Refs #333
```

### Task 8: GraphMutation sealed hierarchy + FieldChange

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/GraphMutation.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/FieldChange.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/GraphMutationTest.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/FieldChangeTest.java`

**Interfaces:**
- Consumes: `Confidence` (cognitive-api), `MergeConflict` (mindmap-api), `MindMapNode` (mindmap-api), `NodeUpdate` (mindmap-api)
- Produces: `GraphMutation` sealed interface (14 record variants: NodeAdded, NodeUpdated, NodeErased, EdgeAdded, EdgeRemoved, NodesMerged, NodeSuperseded, NodeReinstated, AliasAdded, AliasRemoved, SubgraphCreated, SubgraphErased, EntityErased), `FieldChange.diff(MindMapNode, NodeUpdate) → Map<String, FieldChange>`

- [ ] **Step 1: Write test for GraphMutation pattern matching**

```java
@Test
void shouldPatternMatchMutationTypes() {
    GraphMutation mutation = new GraphMutation.NodeAdded(
        "n1", "Alice", "sg1", Confidence.stated(), Instant.now(), "manual");

    String type = switch (mutation) {
        case GraphMutation.NodeAdded na -> "added:" + na.name();
        case GraphMutation.NodeUpdated nu -> "updated:" + nu.nodeId();
        case GraphMutation.NodeErased ne -> "erased:" + ne.nodeId();
        case GraphMutation.EdgeAdded ea -> "edge:" + ea.edgeType();
        case GraphMutation.EdgeRemoved er -> "edge-rm:" + er.edgeId();
        case GraphMutation.NodesMerged nm -> "merged:" + nm.survivorId();
        case GraphMutation.NodeSuperseded ns -> "super:" + ns.supersededId();
        case GraphMutation.NodeReinstated nr -> "reinstate:" + nr.nodeId();
        case GraphMutation.AliasAdded aa -> "alias:" + aa.alias();
        case GraphMutation.AliasRemoved ar -> "alias-rm:" + ar.alias();
        case GraphMutation.SubgraphCreated sc -> "sg:" + sc.name();
        case GraphMutation.SubgraphErased se -> "sg-rm:" + se.subgraphId();
        case GraphMutation.EntityErased ee -> "entity-rm:" + ee.entityName();
    };

    assertEquals("added:Alice", type);
    assertEquals("manual", mutation.source());
    assertNotNull(mutation.timestamp());
}
```

- [ ] **Step 2: Write test for FieldChange.diff**

```java
@Test
void shouldDiffNodeUpdate() {
    // Use InMemoryMindMapStore to create a real node, then diff against an update
    var store = new InMemoryMindMapStore();
    String sgId = store.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    String nodeId = store.addNode(NodeInput.builder("Alice").subgraphId(sgId)
        .confidence(Confidence.stated()).trait("Personable").build(), "t1");
    MindMapNode before = store.getNode(nodeId, "t1");

    NodeUpdate update = NodeUpdate.builder()
        .name("Alicia")
        .confidence(new Confidence(ConfidenceOrigin.INFERRED, 0.5, null))
        .build();

    Map<String, FieldChange> changes = FieldChange.diff(before, update);

    assertTrue(changes.containsKey("name"));
    assertEquals("Alice", changes.get("name").oldValue());
    assertEquals("Alicia", changes.get("name").newValue());
    assertTrue(changes.containsKey("confidence"));
}

@Test
void shouldIgnoreNullFields() {
    var store = new InMemoryMindMapStore();
    String sgId = store.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    String nodeId = store.addNode(NodeInput.builder("Alice").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    MindMapNode before = store.getNode(nodeId, "t1");

    NodeUpdate update = NodeUpdate.builder().build(); // all nulls

    Map<String, FieldChange> changes = FieldChange.diff(before, update);

    assertTrue(changes.isEmpty());
}
```

- [ ] **Step 3: Run tests — expect FAIL**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability -Dtest="GraphMutationTest,FieldChangeTest"`

- [ ] **Step 4: Implement GraphMutation sealed interface**

14 record variants as specified in the spec. Each implements `timestamp()` and `source()`. Add `@JsonTypeInfo(use = Id.NAME, property = "type")` + `@JsonSubTypes` for Jackson serialization.

- [ ] **Step 5: Implement FieldChange**

```java
public record FieldChange(String field, Object oldValue, Object newValue) {
    public static Map<String, FieldChange> diff(MindMapNode before, NodeUpdate update) {
        // Compare each non-null field in update against before
        // Only produce entries when the update field is non-null (scalars)
        // or non-empty (collection deltas: traitsToAdd, traitsToRemove, etc.)
    }
}
```

- [ ] **Step 6: Run tests — expect PASS**

- [ ] **Step 7: Commit**

```
feat(cognitive-observability): GraphMutation sealed hierarchy (14 types) + FieldChange

Jackson @JsonTypeInfo for polymorphic serialization.

Refs #333
```

### Task 9: GraphMutationRecorded CDI event + SnapshotStore SPI

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/GraphMutationRecorded.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/SnapshotStore.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/SnapshotRetentionPolicy.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/GraphSnapshot.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/NodeSnapshot.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/EdgeSnapshot.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/ConsolidationAuditEntry.java`

**Interfaces:**
- Consumes: `GraphMutation`, `Confidence`, `ValidationTier`, `NodeRef`
- Produces: `SnapshotStore` interface (storeMutation, findMutations, findMutationsForEntity, storeKeyframe, reconstruct, latestKeyframe, mutationCountSinceKeyframe, storeAuditEntry, findAuditEntries, lastConsolidationTime, purge, count), `GraphSnapshot`, `NodeSnapshot`, `EdgeSnapshot`, `ConsolidationAuditEntry`, `GraphMutationRecorded`

- [ ] **Step 1: Write SnapshotStore SPI and all type records**

These are pure data types and an SPI interface — no logic to test yet. Write all records as defined in the spec: GraphSnapshot, NodeSnapshot, EdgeSnapshot, ConsolidationAuditEntry (with PhaseAuditEntry), SnapshotRetentionPolicy, GraphMutationRecorded.

SnapshotStore interface with all methods from the spec.

- [ ] **Step 2: Compile check**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognitive-observability`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```
feat(cognitive-observability): SnapshotStore SPI + snapshot/audit types

SnapshotStore interface, GraphSnapshot/NodeSnapshot/EdgeSnapshot records,
ConsolidationAuditEntry, GraphMutationRecorded CDI event.

Refs #333
```

### Task 10: MutationTrackingDecorator (runtime class)

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/MutationTrackingDecorator.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/MutationTrackingDecoratorTest.java`

**Interfaces:**
- Consumes: `AbstractForwardingMindMapStore` (mindmap-api), `MutationContext` (mindmap-api), `SnapshotStore`, `GraphMutation`, `FieldChange`
- Produces: `MutationTrackingDecorator` extends `AbstractForwardingMindMapStore` — intercepts all MindMapStore mutation methods, persists GraphMutation records, fires event sink

- [ ] **Step 1: Write test — addNode produces NodeAdded mutation**

```java
@Test
void shouldCaptureNodeAdded() {
    var store = new InMemoryMindMapStore();
    var mutations = new ArrayList<GraphMutation>();
    var decorator = new MutationTrackingDecorator(store, null, evt -> mutations.add(evt.mutation()));

    String sgId = decorator.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    MutationContext.set("test-source");
    String nodeId = decorator.addNode(NodeInput.builder("Alice").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    MutationContext.clear();

    // SubgraphCreated + NodeAdded
    assertEquals(2, mutations.size());
    assertInstanceOf(GraphMutation.SubgraphCreated.class, mutations.get(0));
    var nodeAdded = (GraphMutation.NodeAdded) mutations.get(1);
    assertEquals(nodeId, nodeAdded.nodeId());
    assertEquals("Alice", nodeAdded.name());
    assertEquals("test-source", nodeAdded.source());
}
```

- [ ] **Step 2: Write test — updateNode produces NodeUpdated with FieldChanges**

```java
@Test
void shouldCaptureNodeUpdated() {
    var store = new InMemoryMindMapStore();
    var mutations = new ArrayList<GraphMutation>();
    var decorator = new MutationTrackingDecorator(store, null, evt -> mutations.add(evt.mutation()));

    String sgId = decorator.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    String nodeId = decorator.addNode(NodeInput.builder("Alice").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    mutations.clear();

    decorator.updateNode(nodeId, NodeUpdate.builder().name("Alicia").build(), "t1");

    assertEquals(1, mutations.size());
    var updated = (GraphMutation.NodeUpdated) mutations.getFirst();
    assertTrue(updated.changes().containsKey("name"));
    assertEquals("Alice", updated.changes().get("name").oldValue());
    assertEquals("Alicia", updated.changes().get("name").newValue());
}
```

- [ ] **Step 3: Write test — mergeNodes produces NodesMerged**

```java
@Test
void shouldCaptureMerge() {
    var store = new InMemoryMindMapStore();
    var mutations = new ArrayList<GraphMutation>();
    var decorator = new MutationTrackingDecorator(store, null, evt -> mutations.add(evt.mutation()));

    String sgId = decorator.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    String a = decorator.addNode(NodeInput.builder("Alice").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    String b = decorator.addNode(NodeInput.builder("Alicia").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");
    mutations.clear();

    decorator.mergeNodes(a, b, "t1");

    assertEquals(1, mutations.size());
    var merged = (GraphMutation.NodesMerged) mutations.getFirst();
    assertEquals(a, merged.survivorId());
    assertEquals(b, merged.absorbedId());
}
```

- [ ] **Step 4: Write test — eraseEntityAcrossTenants routes through decorator**

```java
@Test
void shouldRouteEraseEntityAcrossTenantsThroughDecorator() {
    var store = new InMemoryMindMapStore();
    var mutations = new ArrayList<GraphMutation>();
    var decorator = new MutationTrackingDecorator(store, null, evt -> mutations.add(evt.mutation()));

    String sg1 = decorator.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    decorator.addNode(NodeInput.builder("Alice").subgraphId(sg1)
        .confidence(Confidence.stated()).build(), "t1");
    String sg2 = decorator.createSubgraph(new SubgraphInput("test", "concept"), "t2");
    decorator.addNode(NodeInput.builder("Alice").subgraphId(sg2)
        .confidence(Confidence.stated()).build(), "t2");
    mutations.clear();

    decorator.eraseEntityAcrossTenants("Alice", Set.of("t1", "t2"));

    long entityErasedCount = mutations.stream()
        .filter(m -> m instanceof GraphMutation.EntityErased).count();
    assertEquals(2, entityErasedCount);
}
```

- [ ] **Step 5: Run tests — expect FAIL**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability -Dtest=MutationTrackingDecoratorTest`

- [ ] **Step 6: Implement MutationTrackingDecorator**

Extends `AbstractForwardingMindMapStore`. Constructor takes `(MindMapStore delegate, SnapshotStore snapshotStore, Consumer<GraphMutationRecorded> eventSink)`. Override: addNode, updateNode (pre-read + FieldChange.diff), eraseNode (pre-read for subgraphId), addEdge, removeEdge (pre-read for edge details), mergeNodes, supersede, reinstate, addAlias, removeAlias, createSubgraph, eraseSubgraph, eraseEntity, eraseEntityAcrossTenants (iterate and call this.eraseEntity per tenant). Each override delegates, then calls `persistMutation`.

- [ ] **Step 7: Run tests — expect PASS**

- [ ] **Step 8: Commit**

```
feat(cognitive-observability): MutationTrackingDecorator

Intercepts all MindMapStore mutations, creates GraphMutation records,
persists via SnapshotStore, fires events. Pre-reads nodes for
FieldChange diff on updateNode.

Refs #333
```

### Task 11: MutationTrackingCdiDecorator + ConsolidationCompleted event

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/MutationTrackingCdiDecorator.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationCompleted.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/PhaseResult.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/ConsolidationScheduler.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridge.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserver.java`

**Interfaces:**
- Consumes: `MutationTrackingDecorator`, `MindMapStore`, `SnapshotStore`, `Event<GraphMutationRecorded>`, `MutationContext`
- Produces: `MutationTrackingCdiDecorator` (@Decorator @Priority(20)), `ConsolidationCompleted(tenantId, phaseResults)`, `PhaseResult(phaseName, startedAt, completedAt, success, errorMessage)`

- [ ] **Step 1: Create ConsolidationCompleted + PhaseResult records**

```java
public record ConsolidationCompleted(String tenantId, List<PhaseResult> phaseResults) {}
public record PhaseResult(String phaseName, Instant startedAt, Instant completedAt,
                           boolean success, String errorMessage) {}
```

- [ ] **Step 2: Create MutationTrackingCdiDecorator**

Follow `AffectTrajectoryCdiDecorator` pattern exactly:

```java
@Decorator
@Priority(20)
public class MutationTrackingCdiDecorator extends MutationTrackingDecorator {
    @Inject
    public MutationTrackingCdiDecorator(@Delegate @Any MindMapStore delegate,
                                         Instance<SnapshotStore> snapshotStore,
                                         Event<GraphMutationRecorded> event) {
        super(delegate,
              snapshotStore.isResolvable() ? snapshotStore.get() : null,
              event::fire);
    }
}
```

- [ ] **Step 3: Modify ConsolidationScheduler.tick()**

Add `Event<ConsolidationCompleted>` injection. Wrap each phase.run() with MutationContext.set/clear and per-phase timing. Fire ConsolidationCompleted after all phases for each tenant. Same changes to consolidateNow().

- [ ] **Step 4: Modify ConversationBridge.process()**

Wrap body with `MutationContext.set("conversation-bridge")` / `MutationContext.clear()` in try/finally.

- [ ] **Step 5: Modify ExtractionRequestedObserver.onExtractionRequested()**

Wrap body with `MutationContext.set("extraction")` / `MutationContext.clear()` in try/finally.

- [ ] **Step 6: Run affected module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,mindmap-intelligence,cognitive-observability`
Expected: All tests pass

- [ ] **Step 7: Commit**

```
feat(cognitive-observability): CDI decorator + MutationContext integration

MutationTrackingCdiDecorator @Priority(20) classpath-activated.
ConsolidationScheduler fires ConsolidationCompleted with PhaseResult.
ConversationBridge + ExtractionRequestedObserver set MutationContext.

Refs #333
```

### Task 12: InMemorySnapshotStore + SnapshotStoreContractTest

**Files:**
- Create: `cognitive-observability-testing/pom.xml`
- Create: `cognitive-observability-testing/src/main/java/io/casehub/neocortex/cognitive/observability/testing/InMemorySnapshotStore.java`
- Create: `cognitive-observability-testing/src/main/java/io/casehub/neocortex/cognitive/observability/testing/SnapshotStoreContractTest.java`
- Create: `cognitive-observability-testing/src/test/java/io/casehub/neocortex/cognitive/observability/testing/InMemorySnapshotStoreTest.java`
- Modify: `pom.xml` (root — add module)

**Interfaces:**
- Consumes: `SnapshotStore`, `GraphMutation`, `GraphSnapshot`, `ConsolidationAuditEntry`, `SnapshotRetentionPolicy`
- Produces: `InMemorySnapshotStore @Alternative @Priority(2)`, `SnapshotStoreContractTest` abstract base

- [ ] **Step 1: Create module pom.xml**

Dependencies: `casehub-neocortex-cognitive-observability`, `junit-jupiter` (test scope).

- [ ] **Step 2: Write SnapshotStoreContractTest abstract base**

Tests covering:
- storeMutation + findMutations by time range
- findMutationsForEntity (including multi-node mutations like merges)
- storeKeyframe + latestKeyframe
- mutationCountSinceKeyframe
- reconstruct (keyframe + mutations applied)
- storeAuditEntry + findAuditEntries
- lastConsolidationTime
- purge with retention policy
- count
- GraphMutation JSON round-trip for all 14 mutation types

- [ ] **Step 3: Implement InMemorySnapshotStore**

ConcurrentHashMap-based. Store mutations as list, keyframes as list, audit entries as list. findMutationsForEntity extracts all affected node IDs from each mutation type (same logic as SQLite junction table). reconstruct finds nearest keyframe and replays mutations.

- [ ] **Step 4: Create InMemorySnapshotStoreTest extending the contract test**

```java
class InMemorySnapshotStoreTest extends SnapshotStoreContractTest {
    @Override
    protected SnapshotStore createStore() {
        return new InMemorySnapshotStore();
    }
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability-testing`
Expected: All contract tests pass

- [ ] **Step 6: Commit**

```
feat(cognitive-observability-testing): InMemorySnapshotStore + contract test

SnapshotStoreContractTest abstract base with mutation round-trip,
entity queries, keyframe reconstruction, audit entries, and purge tests.

Refs #333
```

### Task 13: SQLite SnapshotStore implementation

**Files:**
- Create: `cognitive-observability-sqlite/pom.xml`
- Create: `cognitive-observability-sqlite/src/main/java/io/casehub/neocortex/cognitive/observability/sqlite/SqliteSnapshotStore.java`
- Create: `cognitive-observability-sqlite/src/main/resources/db/observability/V1__create_snapshot_tables.sql`
- Create: `cognitive-observability-sqlite/src/test/java/io/casehub/neocortex/cognitive/observability/sqlite/SqliteSnapshotStoreTest.java`
- Modify: `pom.xml` (root — add module)

**Interfaces:**
- Consumes: `SnapshotStore`, `GraphMutation`, `GraphSnapshot`, HikariCP, Flyway
- Produces: `SqliteSnapshotStore @ApplicationScoped` — full SnapshotStore implementation backed by SQLite

- [ ] **Step 1: Create module pom.xml**

Dependencies: `casehub-neocortex-cognitive-observability`, `casehub-neocortex-cognitive-observability-testing` (test scope), `com.zaxxer:HikariCP`, `org.flywaydb:flyway-core`, `org.xerial:sqlite-jdbc`.

- [ ] **Step 2: Create Flyway migration V1__create_snapshot_tables.sql**

Tables: `mutations` (id, tenant_id, subgraph_id, source, mutation_type, timestamp, data), `mutation_nodes` (mutation_id, node_id, tenant_id — junction table), `keyframes` (id, tenant_id, subgraph_id, captured_at, data), `audit_entries` (id, tenant_id, started_at, completed_at, data). All indexes as specified in spec.

- [ ] **Step 3: Implement SqliteSnapshotStore**

Follow `SqliteMindMapStore` patterns: HikariCP WAL mode, Flyway migrations on construction. storeMutation: insert into mutations + extract node IDs into mutation_nodes junction table. Jackson ObjectMapper for JSON serialization. reconstruct: find nearest keyframe, find mutations between keyframe and pointInTime, apply mutations to keyframe state.

- [ ] **Step 4: Create SqliteSnapshotStoreTest extending the contract test**

```java
class SqliteSnapshotStoreTest extends SnapshotStoreContractTest {
    private Path tempDir;

    @Override
    protected SnapshotStore createStore() {
        tempDir = Files.createTempDirectory("snapshot-test");
        return new SqliteSnapshotStore(tempDir.resolve("test.db").toString());
    }

    @AfterEach
    void cleanup() throws Exception {
        // cleanup temp directory
    }
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability-sqlite`
Expected: All contract tests pass

- [ ] **Step 6: Commit**

```
feat(cognitive-observability-sqlite): SQLite SnapshotStore implementation

WAL mode, HikariCP, Flyway migrations. Junction table mutation_nodes
for entity-scoped queries. Jackson serialization for all 14 mutation types.

Refs #333
```

### Task 14: SnapshotCaptureService (keyframe triggering + retention)

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/SnapshotCaptureService.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/SnapshotCaptureServiceTest.java`

**Interfaces:**
- Consumes: `ConsolidationCompleted` CDI event, `SnapshotStore`, `MindMapStore`, `PhaseResult`, `GraphSnapshot`, `NodeSnapshot`, `EdgeSnapshot`, `ConsolidationAuditEntry`, `PhaseAuditEntry`, `SnapshotRetentionPolicy`
- Produces: `SnapshotCaptureService` (@ApplicationScoped) — observes ConsolidationCompleted, constructs audit entries, triggers keyframes, runs retention purge

- [ ] **Step 1: Write test — constructs ConsolidationAuditEntry from ConsolidationCompleted**

```java
@Test
void shouldConstructAuditEntry() {
    var snapshotStore = new InMemorySnapshotStore();
    var mindMapStore = new InMemoryMindMapStore();
    var service = new SnapshotCaptureService(snapshotStore, mindMapStore, 10, 90);

    var phaseResults = List.of(
        new PhaseResult("AccessFrequencyPhase", Instant.now().minusSeconds(5),
            Instant.now().minusSeconds(3), true, null),
        new PhaseResult("MergeDetectionPhase", Instant.now().minusSeconds(3),
            Instant.now(), true, null));

    service.onConsolidationCompleted(new ConsolidationCompleted("t1", phaseResults));

    var entries = snapshotStore.findAuditEntries("t1",
        Instant.now().minusMinutes(1), Instant.now().plusMinutes(1));
    assertEquals(1, entries.size());
    assertEquals(2, entries.getFirst().phases().size());
}
```

- [ ] **Step 2: Write test — captures keyframe when mutation threshold reached**

```java
@Test
void shouldCaptureKeyframeAtThreshold() {
    var snapshotStore = new InMemorySnapshotStore();
    var mindMapStore = new InMemoryMindMapStore();
    String sgId = mindMapStore.createSubgraph(new SubgraphInput("test", "concept"), "t1");
    mindMapStore.addNode(NodeInput.builder("Alice").subgraphId(sgId)
        .confidence(Confidence.stated()).build(), "t1");

    // Seed enough mutations to hit threshold (keyframeInterval = 3 for test)
    var service = new SnapshotCaptureService(snapshotStore, mindMapStore, 3, 90);
    for (int i = 0; i < 3; i++) {
        snapshotStore.storeMutation("t1", new GraphMutation.NodeAdded(
            "n" + i, "Node" + i, sgId, Confidence.stated(), Instant.now(), "test"));
    }

    service.onConsolidationCompleted(new ConsolidationCompleted("t1", List.of()));

    var keyframe = snapshotStore.latestKeyframe("t1", sgId);
    assertTrue(keyframe.isPresent());
}
```

- [ ] **Step 3: Run tests — expect FAIL**

- [ ] **Step 4: Implement SnapshotCaptureService**

@ApplicationScoped. Constructor injection: `Instance<SnapshotStore>`, `Instance<MindMapStore>`, config for keyframeInterval and retentionDays. `@Observes ConsolidationCompleted` handler: construct ConsolidationAuditEntry with per-phase mutationCount (query SnapshotStore by time range + source filter), store audit entry, check mutationCountSinceKeyframe per subgraph, capture keyframe if threshold met, run purge if 24h since last purge.

- [ ] **Step 5: Run tests — expect PASS**

- [ ] **Step 6: Run full build verification**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl cognitive-observability,cognitive-observability-testing,cognitive-observability-sqlite,mindmap-api,mindmap-intelligence`

- [ ] **Step 7: Commit**

```
feat(cognitive-observability): SnapshotCaptureService

Observes ConsolidationCompleted, constructs audit entries with per-phase
mutation counts, triggers keyframe capture at configurable threshold,
runs time-based retention purge.

Refs #333
```

---

## Batch 3: Layer 3 — Temporal Observation

### Task 15: GraphDiffResult + cognition_diff logic

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/GraphDiffResult.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionDiffService.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/CognitionDiffServiceTest.java`

**Interfaces:**
- Consumes: `SnapshotStore.findMutations()`, `SnapshotStore.lastConsolidationTime()`, `GraphMutation`
- Produces: `CognitionDiffService.diff(SnapshotStore, String tenantId, String subgraphId, Instant from, Instant to, String source) → GraphDiffResult`

- [ ] **Step 1: Write test — finds mutations in time range**

```java
@Test
void shouldFindMutationsInTimeRange() {
    var store = new InMemorySnapshotStore();
    Instant t0 = Instant.now().minusSeconds(60);
    Instant t1 = Instant.now().minusSeconds(30);
    Instant t2 = Instant.now();

    store.storeMutation("t1", new GraphMutation.NodeAdded(
        "n1", "Alice", "sg1", Confidence.stated(), t0, "manual"));
    store.storeMutation("t1", new GraphMutation.NodeAdded(
        "n2", "Bob", "sg1", Confidence.stated(), t1, "consolidation:MergeDetectionPhase"));

    var result = CognitionDiffService.diff(store, "t1", "sg1",
        t0.minusSeconds(1), t2, null);

    assertEquals(2, result.mutations().size());
    assertEquals(2, result.summary().nodesAdded());
}
```

- [ ] **Step 2: Write test — source filter**

```java
@Test
void shouldFilterBySource() {
    var store = new InMemorySnapshotStore();
    Instant now = Instant.now();

    store.storeMutation("t1", new GraphMutation.NodeAdded(
        "n1", "Alice", "sg1", Confidence.stated(), now.minusSeconds(10), "conversation-bridge"));
    store.storeMutation("t1", new GraphMutation.NodeAdded(
        "n2", "Bob", "sg1", Confidence.stated(), now.minusSeconds(5), "consolidation:MergeDetectionPhase"));

    var result = CognitionDiffService.diff(store, "t1", null,
        now.minusSeconds(60), now, "consolidation:*");

    assertEquals(1, result.mutations().size());
    assertEquals("Bob", ((GraphMutation.NodeAdded) result.mutations().getFirst()).name());
}
```

- [ ] **Step 3: Write test — null from defaults to last consolidation time**

```java
@Test
void shouldDefaultFromToLastConsolidation() {
    var store = new InMemorySnapshotStore();
    Instant consolidationTime = Instant.now().minusSeconds(300);
    store.storeAuditEntry(new ConsolidationAuditEntry(
        "t1", consolidationTime.minusSeconds(5), consolidationTime, List.of()));
    store.storeMutation("t1", new GraphMutation.NodeAdded(
        "n1", "Alice", "sg1", Confidence.stated(),
        consolidationTime.plusSeconds(10), "manual"));

    var result = CognitionDiffService.diff(store, "t1", null, null, null, null);

    assertEquals(1, result.mutations().size());
}
```

- [ ] **Step 4: Run tests — expect FAIL**

- [ ] **Step 5: Implement GraphDiffResult + CognitionDiffService**

GraphDiffResult record with mutations list, summary (counts by type), timeRange. CognitionDiffService static utility: resolves from/to defaults, queries SnapshotStore.findMutations, applies source filter (supports wildcard via startsWith), computes summary counts.

- [ ] **Step 6: Run tests — expect PASS**

- [ ] **Step 7: Commit**

```
feat(cognitive-observability): CognitionDiffService + GraphDiffResult

Structured diff with source filtering (wildcard support), aggregate
summary counts, default from=lastConsolidationTime.

Refs #333
```

### Task 16: EntityTrace + cognition_trace logic

**Files:**
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/EntityTrace.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/TraceEvent.java`
- Create: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionTraceService.java`
- Create: `cognitive-observability/src/test/java/io/casehub/neocortex/cognitive/observability/CognitionTraceServiceTest.java`

**Interfaces:**
- Consumes: `SnapshotStore.findMutationsForEntity()`, `CognitiveProfile.resolve()`, `MindMapStore.resolveNode()`
- Produces: `CognitionTraceService.trace(SnapshotStore, MindMapStore, CognitiveProfile, String tenantId, String entityName, String nodeId, String subgraphId, Instant from, Instant to) → EntityTrace`

- [ ] **Step 1: Write test — traces entity creation + update**

```java
@Test
void shouldTraceEntityLifecycle() {
    var snapshotStore = new InMemorySnapshotStore();
    Instant t0 = Instant.now().minusSeconds(60);
    Instant t1 = Instant.now().minusSeconds(30);

    snapshotStore.storeMutation("t1", new GraphMutation.NodeAdded(
        "n1", "Alice", "sg1", Confidence.stated(), t0, "conversation-bridge"));
    snapshotStore.storeMutation("t1", new GraphMutation.NodeUpdated(
        "n1", "sg1", Map.of("confidence", new FieldChange("confidence",
            Confidence.stated(), new Confidence(ConfidenceOrigin.INFERRED, 0.5, null))),
        t1, "consolidation:MergeDetectionPhase"));

    var trace = CognitionTraceService.trace(snapshotStore, null, null,
        "t1", null, "n1", null, null, null);

    assertEquals("n1", trace.entityId());
    assertEquals(2, trace.events().size());
    assertEquals(TraceEvent.Type.CREATED, trace.events().get(0).type());
    assertEquals(TraceEvent.Type.UPDATED, trace.events().get(1).type());
}
```

- [ ] **Step 2: Write test — merge shows MERGED_INTO for absorbed node**

```java
@Test
void shouldShowMergeFromBothPerspectives() {
    var snapshotStore = new InMemorySnapshotStore();
    Instant t0 = Instant.now();

    snapshotStore.storeMutation("t1", new GraphMutation.NodesMerged(
        "keep", "remove", List.of(), t0, "consolidation:MergeDetectionPhase"));

    // Trace absorbed node
    var absorbedTrace = CognitionTraceService.trace(snapshotStore, null, null,
        "t1", null, "remove", null, null, null);
    assertEquals(TraceEvent.Type.MERGED_INTO, absorbedTrace.events().getFirst().type());

    // Trace survivor node
    var survivorTrace = CognitionTraceService.trace(snapshotStore, null, null,
        "t1", null, "keep", null, null, null);
    assertEquals(TraceEvent.Type.MERGED_FROM, survivorTrace.events().getFirst().type());
}
```

- [ ] **Step 3: Run tests — expect FAIL**

- [ ] **Step 4: Implement TraceEvent, EntityTrace, CognitionTraceService**

TraceEvent: wraps GraphMutation + type enum (CREATED, UPDATED, MERGED_INTO, MERGED_FROM, SUPERSEDED, SUPERSEDED_BY, REINSTATED, ERASED, ALIAS_ADDED, ALIAS_REMOVED) + relatedEntities. EntityTrace: entityId, entityName, events list, currentState (nullable EntityKnowledge). CognitionTraceService: resolves entity by name if nodeId not provided, queries findMutationsForEntity, classifies each mutation into TraceEvent type based on the node's role in the mutation.

- [ ] **Step 5: Run tests — expect PASS**

- [ ] **Step 6: Commit**

```
feat(cognitive-observability): CognitionTraceService + EntityTrace

Entity-scoped audit trail with bidirectional merge/supersession tracing.
TraceEvent classifies mutations by the entity's role (survivor vs absorbed).

Refs #333
```

### Task 17: @McpDomain GraphQL resolvers for Layer 3 + full build verification

**Files:**
- Modify: `cognitive-observability/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionResolver.java` — add diff() and trace() queries
- Modify: `CLAUDE.md` — add cognitive-observability modules

**Interfaces:**
- Consumes: `CognitionDiffService`, `CognitionTraceService`, `SnapshotStore`
- Produces: diff() and trace() @Query methods on CognitionResolver

- [ ] **Step 1: Add diff() and trace() queries to CognitionResolver**

```java
@Query
@PlatformQuery("Structured delta: what changed between two points in time")
public GraphDiffResult diff(@Name("tenantId") String tenantId,
                             @Name("subgraphId") @Nullable String subgraphId,
                             @Name("from") @Nullable String from,
                             @Name("to") @Nullable String to,
                             @Name("source") @Nullable String source) {
    // Parse ISO-8601 timestamps, delegate to CognitionDiffService
}

@Query
@PlatformQuery("Entity audit trail: creation, updates, merges, supersessions over time")
public EntityTrace trace(@Name("tenantId") String tenantId,
                          @Name("entityName") @Nullable String entityName,
                          @Name("nodeId") @Nullable String nodeId,
                          @Name("subgraphId") @Nullable String subgraphId,
                          @Name("from") @Nullable String from,
                          @Name("to") @Nullable String to) {
    // Parse timestamps, delegate to CognitionTraceService
}
```

- [ ] **Step 2: Run full project build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 3: Update CLAUDE.md**

**Files:**
- Modify: `CLAUDE.md` — add cognitive-observability modules to module structure and maven coordinates

- [ ] **Step 1: Run full project build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS, all tests pass across all modules

- [ ] **Step 2: Update CLAUDE.md**

Add to module structure:
```
cognitive-observability/ — Domain logic, GraphQL resolvers (@McpDomain), mutation types, graph serialization
cognitive-observability-sqlite/ — SQLite SnapshotStore implementation (WAL + HikariCP + Flyway)
cognitive-observability-testing/ — InMemorySnapshotStore, SnapshotStoreContractTest abstract base
```

Add maven coordinates table entries and root Java package.

- [ ] **Step 3: Commit**

```
docs: update CLAUDE.md with cognitive-observability modules

Refs #333
```

## References

- [2026-09-14-cognitive-observability-design.md] — design spec this plan implements
- MindMapStore.java — mindmap-api SPI (method signatures for decorator)
- AbstractForwardingMindMapStore.java — mindmap-api forwarding base class
- AffectTrajectoryCdiDecorator.java — decorator pattern precedent (@Decorator @Priority, @Delegate @Any)
- MindMapAnalyzer.java — mindmap-runtime static analysis methods (health service)
- CognitiveProfile.java — cognitive-index entity resolution (entity/trace services)
- ConsolidationScheduler.java:96-150 — tick() and consolidateNow() loop structure
- ConversationBridge.java:40-72 — process() method to wrap with MutationContext
- ExtractionRequestedObserver.java:40-69 — onExtractionRequested() to wrap with MutationContext
- GE-20260910-2a660e — k-core includes synthetic nodes (filter in health service)
- GE-20260805-aa8a88 — synthetic container nodes cause false integrity mismatches
- GE-20260912-be7c74 — never write to graph during tick loop
- casehubio/neocortex#333 — epic issue
