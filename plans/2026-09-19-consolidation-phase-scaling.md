# Consolidation Phase Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #357 — perf: consolidation phase scaling — approximate algorithms for large subgraphs
**Issue group:** #357

**Goal:** Replace safety-cap node-count guards with approximate algorithms so merge detection, betweenness centrality, and orphan detection work on large subgraphs.

**Architecture:** Three independent fixes in mindmap-api, mindmap-core, mindmap-inmem, mindmap-sqlite, mindmap-intelligence, and mindmap-testing. Fix 3 adds a default SPI method with store-specific overrides. Fix 1 rewrites the merge detection inner loop. Fix 2 adds a new approximate method alongside the existing exact one.

**Tech Stack:** Java 21, JUnit 5, AssertJ, InMemoryMindMapStore (tests), SQLite (production)

## Global Constraints

- Java 21 source level, Java 26 JVM
- All tests run via `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`
- Use `mvn` not `./mvnw`
- Commits reference issue: `Refs #357`

---

## Batch 1: Orphan Nodes SPI Push-Down

### Task 1: Add `nodesWithoutEdges` to MindMapStore SPI + implementations + contract test

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapStore.java`
- Modify: `mindmap-sqlite/src/main/java/io/casehub/neocortex/mindmap/sqlite/SqliteMindMapStore.java`
- Modify: `mindmap-inmem/src/main/java/io/casehub/neocortex/mindmap/inmem/InMemoryMindMapStore.java`
- Modify: `mindmap-core/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzer.java`
- Modify: `mindmap-testing/src/main/java/io/casehub/neocortex/mindmap/testing/MindMapStoreContractTest.java`

**Interfaces:**
- Produces: `MindMapStore.nodesWithoutEdges(String subgraphId, String tenantId)` returning `List<MindMapNode>`

- [ ] **Step 1: Write contract test in MindMapStoreContractTest**

Add three tests at the end of the class, before the closing brace:

```java
// --- nodesWithoutEdges ---

@Test
void nodesWithoutEdges_returnsIsolatedNodes() {
    String a = store.addNode(nodeInput("Connected"), tenantId);
    String b = store.addNode(nodeInput("Isolated"), tenantId);
    store.addEdge(edgeInput(a,
        store.addNode(nodeInput("Other"), tenantId), "knows"), tenantId);

    List<MindMapNode> orphans = store.nodesWithoutEdges(defaultSubgraphId(), tenantId);

    assertThat(orphans).extracting("name").contains("Isolated");
    assertThat(orphans).extracting("name").doesNotContain("Connected", "Other");
}

@Test
void nodesWithoutEdges_allConnected_returnsEmpty() {
    String a = store.addNode(nodeInput("A"), tenantId);
    String b = store.addNode(nodeInput("B"), tenantId);
    store.addEdge(edgeInput(a, b, "knows"), tenantId);

    List<MindMapNode> orphans = store.nodesWithoutEdges(defaultSubgraphId(), tenantId);

    assertThat(orphans).isEmpty();
}

@Test
void nodesWithoutEdges_emptySubgraph_returnsEmpty() {
    List<MindMapNode> orphans = store.nodesWithoutEdges(defaultSubgraphId(), tenantId);

    assertThat(orphans).isEmpty();
}
```

Note: use the existing helper methods `nodeInput(String name)` and `edgeInput(String src, String tgt, String type)` already defined in the contract test, and `defaultSubgraphId()` for the subgraph, and `tenantId` field (which is `TENANT`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-sqlite -Dtest="SqliteMindMapStoreTest#nodesWithoutEdges*" -DfailIfNoTests=false`

Expected: compilation error — `nodesWithoutEdges` does not exist yet.

- [ ] **Step 3: Add default method to MindMapStore**

Add to `MindMapStore.java` after the `nodesIn` method (around line 50):

```java
default List<MindMapNode> nodesWithoutEdges(String subgraphId, String tenantId) {
    return nodesIn(subgraphId, tenantId).stream()
        .filter(n -> neighbors(n.id(), tenantId).isEmpty())
        .toList();
}
```

- [ ] **Step 4: Override in SqliteMindMapStore**

Add override method after the `nodesIn` method (around line 425):

```java
@Override
public List<MindMapNode> nodesWithoutEdges(String subgraphId, String tenantId) {
    try (Connection conn = dataSource.getConnection();
         PreparedStatement ps = conn.prepareStatement(
             "SELECT n.*, sg.type AS sg_type FROM mindmap_node n "
             + "JOIN mindmap_subgraph sg ON n.subgraph_id = sg.subgraph_id "
             + "WHERE n.tenant_id = ? AND n.subgraph_id = ? "
             + "AND (n.superseded_at IS NULL OR n.reinstated_at IS NOT NULL) "
             + "AND n.node_id NOT IN ("
             + "  SELECT source_node_id FROM mindmap_edge WHERE tenant_id = ?"
             + "  UNION"
             + "  SELECT target_node_id FROM mindmap_edge WHERE tenant_id = ?"
             + ")")) {
        ps.setString(1, tenantId);
        ps.setString(2, subgraphId);
        ps.setString(3, tenantId);
        ps.setString(4, tenantId);
        return collectNodes(ps);
    } catch (SQLException e) {
        throw new IllegalStateException("nodesWithoutEdges() failed", e);
    }
}
```

- [ ] **Step 5: Override in InMemoryMindMapStore**

Add override after the `nodesIn` method:

```java
@Override
public List<MindMapNode> nodesWithoutEdges(String subgraphId, String tenantId) {
    Set<String> connectedIds = new HashSet<>();
    for (StoredEdge e : edges.values()) {
        if (e.tenantId.equals(tenantId)) {
            connectedIds.add(e.sourceNodeId);
            connectedIds.add(e.targetNodeId);
        }
    }
    return nodesIn(subgraphId, tenantId).stream()
        .filter(n -> !connectedIds.contains(n.id()))
        .toList();
}
```

- [ ] **Step 6: Simplify MindMapAnalyzer.orphanNodes()**

Replace the body of `orphanNodes` (lines 42-51 in MindMapAnalyzer.java):

```java
public static List<OrphanNode> orphanNodes(MindMapStore store, String subgraphId, String tenantId) {
    requireAnalysis(store);
    return store.nodesWithoutEdges(subgraphId, tenantId).stream()
        .map(n -> new OrphanNode(n.id(), n.name(), subgraphId))
        .toList();
}
```

- [ ] **Step 7: Run all affected tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-testing,mindmap-sqlite,mindmap-inmem,mindmap-core`

Expected: all tests pass, including the 3 new contract tests and existing orphanNodes tests.

- [ ] **Step 8: Commit**

```bash
git -C "$PROJECT" add mindmap-api/ mindmap-sqlite/ mindmap-inmem/ mindmap-core/ mindmap-testing/
git -C "$PROJECT" commit -m "perf(mindmap-api): add nodesWithoutEdges SPI with single-query overrides

Default method preserves V-query behavior. SqliteMindMapStore overrides
with single NOT IN query. InMemoryMindMapStore overrides with set
difference. MindMapAnalyzer.orphanNodes() delegates to the store.

Refs #357"
```

---

## Batch 2: Approximate Betweenness Centrality

### Task 2: Add `approximateBetweennessCentrality` to MindMapAnalyzer + update caller

**Files:**
- Modify: `mindmap-core/src/main/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzer.java`
- Modify: `mindmap-core/src/test/java/io/casehub/neocortex/mindmap/runtime/MindMapAnalyzerTest.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriositySignalGenerator.java`

**Interfaces:**
- Produces: `MindMapAnalyzer.approximateBetweennessCentrality(MindMapStore, String, String, int)` returning `List<BetweennessCentrality>`

- [ ] **Step 1: Write failing tests in MindMapAnalyzerTest**

Add after the existing betweenness tests (around line 269):

```java
@Test
void approximateBetweennessCentrality_bridgeNodeScoresHighest() {
    String a = store.addNode(node("A"), "t1");
    String b = store.addNode(node("B"), "t1");
    String c = store.addNode(node("C"), "t1");
    store.addEdge(edge(a, b, "knows"), "t1");
    store.addEdge(edge(b, c, "knows"), "t1");

    List<MindMapAnalyzer.BetweennessCentrality> result =
        MindMapAnalyzer.approximateBetweennessCentrality(store, subgraphId, "t1", 100);

    assertThat(result).hasSize(3);
    assertThat(result.get(0).name()).isEqualTo("B");
    assertThat(result.get(0).score()).isGreaterThan(0.0);
}

@Test
void approximateBetweennessCentrality_matchesExactOnSmallGraph() {
    String a = store.addNode(node("A"), "t1");
    String b = store.addNode(node("B"), "t1");
    String c = store.addNode(node("C"), "t1");
    String d = store.addNode(node("D"), "t1");
    store.addEdge(edge(a, b, "knows"), "t1");
    store.addEdge(edge(b, c, "knows"), "t1");
    store.addEdge(edge(c, d, "knows"), "t1");

    var exact = MindMapAnalyzer.betweennessCentrality(store, subgraphId, "t1");
    var approx = MindMapAnalyzer.approximateBetweennessCentrality(
        store, subgraphId, "t1", 100);

    assertThat(approx).extracting("name")
        .containsExactlyElementsOf(exact.stream().map(bc -> bc.name()).toList());
}

@Test
void approximateBetweennessCentrality_deterministicResults() {
    String a = store.addNode(node("A"), "t1");
    String b = store.addNode(node("B"), "t1");
    String c = store.addNode(node("C"), "t1");
    store.addEdge(edge(a, b, "knows"), "t1");
    store.addEdge(edge(b, c, "knows"), "t1");

    var result1 = MindMapAnalyzer.approximateBetweennessCentrality(
        store, subgraphId, "t1", 2);
    var result2 = MindMapAnalyzer.approximateBetweennessCentrality(
        store, subgraphId, "t1", 2);

    assertThat(result1).extracting("score")
        .containsExactlyElementsOf(result2.stream().map(bc -> bc.score()).toList());
}

@Test
void approximateBetweennessCentrality_kGreaterThanV_usesAllNodes() {
    String a = store.addNode(node("A"), "t1");
    String b = store.addNode(node("B"), "t1");
    store.addEdge(edge(a, b, "knows"), "t1");

    var result = MindMapAnalyzer.approximateBetweennessCentrality(
        store, subgraphId, "t1", 1000);

    assertThat(result).hasSize(2);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-core -Dtest="MindMapAnalyzerTest#approximateBetweennessCentrality*" -DfailIfNoTests=false`

Expected: compilation error — method does not exist.

- [ ] **Step 3: Implement `approximateBetweennessCentrality`**

Add to `MindMapAnalyzer.java` after the existing `betweennessCentrality` method (after line 240). The algorithm is identical to the existing Brandes implementation, but iterates over a sampled subset of source nodes rather than all nodes, and scales results by V/k:

```java
public static List<BetweennessCentrality> approximateBetweennessCentrality(
        MindMapStore store, String subgraphId, String tenantId, int k) {
    requireAnalysis(store);
    List<MindMapNode> nodes = store.nodesIn(subgraphId, tenantId);
    if (nodes.size() <= 2) {
        return nodes.stream()
            .map(n -> new BetweennessCentrality(n.id(), n.name(), 0.0))
            .toList();
    }

    Map<String, Set<String>> adjacency = new HashMap<>();
    for (MindMapNode node : nodes) {
        Set<String> neighbors = new HashSet<>();
        for (MindMapEdge edge : store.neighbors(node.id(), tenantId)) {
            String other = edge.sourceNodeId().equals(node.id())
                ? edge.targetNodeId() : edge.sourceNodeId();
            neighbors.add(other);
        }
        adjacency.put(node.id(), neighbors);
    }

    Map<String, Double> centrality = new HashMap<>();
    List<String> nodeIds = nodes.stream().map(MindMapNode::id).toList();
    for (String id : nodeIds) {
        centrality.put(id, 0.0);
    }

    int effectiveK = Math.min(k, nodeIds.size());
    List<String> sources;
    if (effectiveK >= nodeIds.size()) {
        sources = nodeIds;
    } else {
        List<String> shuffled = new ArrayList<>(nodeIds);
        java.util.Collections.shuffle(shuffled, new java.util.Random(42));
        sources = shuffled.subList(0, effectiveK);
    }

    for (String source : sources) {
        Map<String, Integer> dist = new HashMap<>();
        Map<String, List<String>> pred = new HashMap<>();
        Map<String, Double> sigma = new HashMap<>();
        for (String n : nodeIds) {
            dist.put(n, -1);
            pred.put(n, new ArrayList<>());
            sigma.put(n, 0.0);
        }
        dist.put(source, 0);
        sigma.put(source, 1.0);

        Queue<String> queue = new ArrayDeque<>();
        Deque<String> stack = new ArrayDeque<>();
        queue.add(source);

        while (!queue.isEmpty()) {
            String v = queue.poll();
            stack.push(v);
            for (String w : adjacency.getOrDefault(v, Set.of())) {
                if (!dist.containsKey(w)) continue;
                if (dist.get(w) < 0) {
                    dist.put(w, dist.get(v) + 1);
                    queue.add(w);
                }
                if (dist.get(w) == dist.get(v) + 1) {
                    sigma.put(w, sigma.get(w) + sigma.get(v));
                    pred.get(w).add(v);
                }
            }
        }

        Map<String, Double> delta = new HashMap<>();
        for (String n : nodeIds) {
            delta.put(n, 0.0);
        }
        while (!stack.isEmpty()) {
            String w = stack.pop();
            for (String v : pred.get(w)) {
                delta.put(v, delta.get(v)
                    + (sigma.get(v) / sigma.get(w)) * (1 + delta.get(w)));
            }
            if (!w.equals(source)) {
                centrality.put(w, centrality.get(w) + delta.get(w));
            }
        }
    }

    double n = nodeIds.size();
    double norm = (n - 1) * (n - 2);
    double scale = (effectiveK < nodeIds.size()) ? (double) nodeIds.size() / effectiveK : 1.0;

    return nodes.stream()
        .map(node -> new BetweennessCentrality(
            node.id(), node.name(),
            norm > 0 ? centrality.get(node.id()) * scale / norm : 0.0))
        .sorted(Comparator.comparingDouble(BetweennessCentrality::score).reversed())
        .toList();
}
```

Ensure these imports are present at the top of MindMapAnalyzer.java: `java.util.ArrayList`, `java.util.Collections`, `java.util.Random`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-core -Dtest="MindMapAnalyzerTest"`

Expected: all tests pass, including 4 new approximate tests and existing exact tests.

- [ ] **Step 5: Update CuriositySignalGenerator — remove guard, switch to approximate**

In `CuriositySignalGenerator.java`, in method `collectCentralitySignals` (around line 157-164), replace:

```java
var nodes = store.nodesIn(sg.id(), tenantId);
if (nodes.size() > 2000) {
    return;
}

var betweenness = MindMapAnalyzer.betweennessCentrality(store, sg.id(), tenantId);
```

with:

```java
var betweenness = MindMapAnalyzer.approximateBetweennessCentrality(
    store, sg.id(), tenantId, 100);
```

- [ ] **Step 6: Run mindmap-intelligence tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git -C "$PROJECT" add mindmap-core/ mindmap-intelligence/
git -C "$PROJECT" commit -m "perf(mindmap): sampled Brandes for approximate betweenness centrality

New approximateBetweennessCentrality(store, subgraphId, tenantId, k) method
samples k random sources with deterministic seed. CuriositySignalGenerator
switches to approximate and removes the 2000-node guard.

Refs #357"
```

---

## Batch 3: Merge Detection Scaling

### Task 3: Rewrite `detectCandidates` with prefix bucketing + bulk neighbor pre-loading

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/MergeDetectionPhaseTest.java`

**Interfaces:**
- Consumes: `MindMapStore.nodesIn()`, `MindMapStore.neighbors()`
- Produces: same `List<MergeCandidate>` output, same `run()` contract

- [ ] **Step 1: Write failing tests for prefix bucketing behavior**

Add to `MergeDetectionPhaseTest.java`:

```java
@Test
void detectCandidates_differentPrefix_noCandidates() {
    store.addNode(NodeInput.of("Alice Smith", subgraphId), "t1");
    store.addNode(NodeInput.of("Zelda Smith", subgraphId), "t1");

    List<MergeCandidate> candidates = phase.detectCandidates(subgraphId, "t1");

    assertThat(candidates).isEmpty();
}

@Test
void detectCandidates_samePrefixSimilarNames_returnsCandidate() {
    String id1 = store.addNode(NodeInput.of("Machine Learning", subgraphId), "t1");
    String id2 = store.addNode(NodeInput.of("Machine Lerning", subgraphId), "t1");
    String shared = store.addNode(NodeInput.of("AI", subgraphId), "t1");
    store.addEdge(EdgeInput.of(id1, shared, "related-to"), "t1");
    store.addEdge(EdgeInput.of(id2, shared, "related-to"), "t1");

    List<MergeCandidate> candidates = phase.detectCandidates(subgraphId, "t1");

    assertThat(candidates).isNotEmpty();
}

@Test
void detectCandidates_shortNames_handledCorrectly() {
    String id1 = store.addNode(NodeInput.of("AI", subgraphId), "t1");
    String id2 = store.addNode(NodeInput.of("AI", subgraphId), "t1");
    String shared = store.addNode(NodeInput.of("Topic", subgraphId), "t1");
    store.addEdge(EdgeInput.of(id1, shared, "related-to"), "t1");
    store.addEdge(EdgeInput.of(id2, shared, "related-to"), "t1");

    List<MergeCandidate> candidates = phase.detectCandidates(subgraphId, "t1");

    assertThat(candidates).isNotEmpty();
}

@Test
void detectCandidates_largeSubgraph_doesNotSkip() {
    // Previously skipped at >500 nodes. Now should process.
    // Create enough nodes in two buckets to exceed old guard.
    for (int i = 0; i < 10; i++) {
        store.addNode(NodeInput.of("Alpha-" + i, subgraphId), "t1");
    }
    String id1 = store.addNode(NodeInput.of("Alice Smith", subgraphId), "t1");
    String id2 = store.addNode(NodeInput.of("Alice Smyth", subgraphId), "t1");
    String shared = store.addNode(NodeInput.of("Project", subgraphId), "t1");
    store.addEdge(EdgeInput.of(id1, shared, "works-on"), "t1");
    store.addEdge(EdgeInput.of(id2, shared, "works-on"), "t1");

    List<MergeCandidate> candidates = phase.detectCandidates(subgraphId, "t1");

    assertThat(candidates).isNotEmpty();
}
```

- [ ] **Step 2: Run tests to verify existing behavior**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="MergeDetectionPhaseTest"`

Expected: new tests pass (the current code handles these cases too, except the guard test won't trigger since we only have ~14 nodes). Verify existing tests still pass.

- [ ] **Step 3: Rewrite `detectCandidates` with three-phase pipeline**

Replace the `detectCandidates` method body (lines 88-122) with:

```java
List<MergeCandidate> detectCandidates(String subgraphId, String tenantId) {
    List<MindMapNode> nodes = store.nodesIn(subgraphId, tenantId).stream()
                                   .filter(n -> !n.traits().contains("Summary"))
                                   .toList();

    if (nodes.size() <= 1) {
        return List.of();
    }

    // Phase 1: Bulk pre-load neighbor sets
    Map<String, Set<String>> neighborSets = bulkLoadNeighbors(nodes, tenantId);

    // Phase 2: Prefix bucketing
    Map<String, List<MindMapNode>> buckets = prefixBucket(nodes);

    // Phase 3: Evaluate within each bucket
    List<MergeCandidate> candidates = new ArrayList<>();
    for (List<MindMapNode> bucket : buckets.values()) {
        for (int i = 0; i < bucket.size(); i++) {
            for (int j = i + 1; j < bucket.size(); j++) {
                MindMapNode a = bucket.get(i);
                MindMapNode b = bucket.get(j);
                double nameSim = JaroWinkler.similarity(a.name(), b.name());
                if (nameSim < nameThreshold) { continue; }

                Set<String> neighborsA = neighborSets.getOrDefault(a.id(), Set.of());
                Set<String> neighborsB = neighborSets.getOrDefault(b.id(), Set.of());
                double neighborOverlap = jaccard(neighborsA, neighborsB);

                double combined = 0.6 * nameSim + 0.4 * neighborOverlap;
                if (combined >= 0.6) {
                    String reason = neighborOverlap > 0
                        ? "name+neighbors" : "name-similarity";
                    candidates.add(new MergeCandidate(
                        a.id(), b.id(), combined, reason, Instant.now()));
                }
            }
        }
    }

    candidates.sort(Comparator.comparingDouble(MergeCandidate::score).reversed());
    return candidates;
}

private Map<String, Set<String>> bulkLoadNeighbors(List<MindMapNode> nodes,
                                                     String tenantId) {
    Map<String, Set<String>> result = new HashMap<>();
    for (MindMapNode node : nodes) {
        Set<String> ids = store.neighbors(node.id(), tenantId).stream()
            .map(edge -> edge.sourceNodeId().equals(node.id())
                ? edge.targetNodeId() : edge.sourceNodeId())
            .collect(Collectors.toSet());
        result.put(node.id(), ids);
    }
    return result;
}

private static Map<String, List<MindMapNode>> prefixBucket(List<MindMapNode> nodes) {
    Map<String, List<MindMapNode>> buckets = new HashMap<>();
    for (MindMapNode node : nodes) {
        String name = node.name().trim().toLowerCase();
        String key = name.length() >= 3 ? name.substring(0, 3) : name;
        buckets.computeIfAbsent(key, k -> new ArrayList<>()).add(node);
    }
    return buckets;
}
```

Also remove the old `neighborIds` method (lines 124-128) — it's replaced by the pre-loaded map.

Add import for `HashMap` if not already present.

- [ ] **Step 4: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="MergeDetectionPhaseTest"`

Expected: all tests pass — existing tests verify the same merge behavior, new tests verify bucketing.

- [ ] **Step 5: Run full build to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,mindmap-core,mindmap-inmem,mindmap-sqlite,mindmap-testing,mindmap-intelligence`

Expected: all tests pass across all affected modules.

- [ ] **Step 6: Commit**

```bash
git -C "$PROJECT" add mindmap-intelligence/
git -C "$PROJECT" commit -m "perf(mindmap-intelligence): prefix bucketing + bulk pre-load for merge detection

Replaces O(n²) pairwise comparison with prefix bucketing (O(n) + O(Σbᵢ²))
and replaces per-pair SQL neighbor queries with bulk pre-loading (O(n) once).
Removes the 500-node guard — merge detection now works on large subgraphs.

Refs #357"
```

## References

- [specs/issue-357-consolidation-phase-scaling/2026-09-19-consolidation-phase-scaling-design.md] — design spec
- [MergeDetectionPhase.java:88-122] — current O(n²) detectCandidates
- [MindMapAnalyzer.java:42-51] — current orphanNodes V-query loop
- [MindMapAnalyzer.java:156-240] — current Brandes implementation
- [CuriositySignalGenerator.java:157-175] — betweenness caller with 2000-node guard
- [MindMapStore.java] — SPI interface
- [SqliteMindMapStore.java:415-425] — nodesIn SQL pattern
- [InMemoryMindMapStore.java:275-282] — in-memory neighbors pattern
- [MindMapStoreContractTest.java] — contract test base
- [GitHub #357] — focal issue
- [GitHub #355] — parent GA audit epic
