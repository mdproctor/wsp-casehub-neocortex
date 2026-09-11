# Multi-Agent Social Cognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #287 — epic: Multi-Agent Social Cognition
**Issue group:** #287, #271, #283

**Goal:** Enable multi-agent perspectival comparison and cross-domain temporal reasoning in cognitive-index.

**Architecture:** Perceiver-primary re-architecture of CognitiveProfile — perspective applied before trajectory computation, PerspectivalResolver internalized. Two new focused types: SocialComparison (static utility for multi-agent PAD comparison) and DomainActivation (CDI bean for cross-domain DTW correlation).

**Tech Stack:** Java 21, Quarkus CDI, cognitive-index module, InMemoryMindMapStore + InMemoryMemoryStore for tests

## Global Constraints

- All code in `cognitive-index` module, package `io.casehub.neocortex.cognitive.index`
- Follow existing Instance<T> graceful degradation pattern for CDI beans
- Static utilities follow AffectTrajectoryAnalyzer pattern (final class, private constructor, static methods)
- Records for all value types — no mutable state
- AssertJ for assertions, JUnit 5 for tests
- No new module dependencies — cognitive-index already depends on mindmap-api, memory-api, mindmap-inmem (test)
- Use `ide_insert_member` for new methods, `ide_replace_member` for body rewrites, `ide_refactor_rename` for renames

---

## Batch 1: Perspective Integration — CognitiveProfile becomes perceiver-primary

After this batch: `CognitiveProfile.resolve()` with `asSeenBy()` returns perspectival EntityKnowledge with correctly scoped trajectory. PerspectivalResolver is package-private.

### Task 1: Query and result record changes

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfileQuery.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/EntityKnowledge.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveProfileQueryTest.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/EntityKnowledgeTest.java`

**Interfaces:**
- Produces: `CognitiveProfileQuery.withAsSeenBy(PrincipalId)` wither, `EntityKnowledge.perceiver()` accessor

- [ ] **Step 1: Write failing test for CognitiveProfileQuery.withAsSeenBy**

```java
@Test
void withAsSeenBySetsField() {
    var principal = new PrincipalId("alice");
    var query = CognitiveProfileQuery.byName("Grandma", "t1")
        .withAsSeenBy(principal);
    assertThat(query.asSeenBy()).isEqualTo(principal);
}

@Test
void byIdDefaultsAsSeenByToNull() {
    var query = CognitiveProfileQuery.byId("node-1", "t1");
    assertThat(query.asSeenBy()).isNull();
}

@Test
void byNameDefaultsAsSeenByToNull() {
    var query = CognitiveProfileQuery.byName("X", "t1");
    assertThat(query.asSeenBy()).isNull();
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileQueryTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `asSeenBy` field does not exist

- [ ] **Step 3: Add asSeenBy field to CognitiveProfileQuery**

Use `ide_edit_member` to add the `asSeenBy` field to CognitiveProfileQuery record. Add it as the last field with default null in all existing factories:

```java
// Record field addition
PrincipalId asSeenBy    // nullable; null = shared/unperspectived view

// New wither
public CognitiveProfileQuery withAsSeenBy(PrincipalId principal) {
    return new CognitiveProfileQuery(nodeId, entityName, subgraphId, tenantId,
        domains, includeEdges, memoryLimit, principal);
}
```

Update all existing factory methods (`byId`, `byName`) and withers to pass `null` for asSeenBy. Add `import io.casehub.platform.api.identity.PrincipalId;`.

- [ ] **Step 4: Write failing test for EntityKnowledge.perceiver**

```java
@Test
void perceiverNullForSharedView() {
    var ek = new EntityKnowledge(
        StubNode.named("X"), List.of(), Map.of(), null, Set.of(), "t1", null);
    assertThat(ek.perceiver()).isNull();
}

@Test
void perceiverSetForPerspectivalView() {
    var principal = new PrincipalId("alice");
    var ek = new EntityKnowledge(
        StubNode.named("X"), List.of(), Map.of(), null, Set.of(), "t1", principal);
    assertThat(ek.perceiver()).isEqualTo(principal);
}
```

- [ ] **Step 5: Add perceiver field to EntityKnowledge**

Use `ide_edit_member` to add `PrincipalId perceiver` as the last field. Update the compact constructor — perceiver is nullable, no validation needed. Add PrincipalId import.

- [ ] **Step 6: Fix compilation — update all EntityKnowledge construction sites**

Search for all EntityKnowledge constructors with `ide_find_references` on the EntityKnowledge record. Add `null` as the last argument to every existing construction site (CognitiveProfile.resolve(), tests).

- [ ] **Step 7: Run all tests to verify backward compatibility**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: all existing tests pass — no behavioral change

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): add asSeenBy to CognitiveProfileQuery, perceiver to EntityKnowledge

Refs #271"
```

### Task 2: Internalize PerspectivalResolver

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalResolver.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PerspectivalResolverTest.java`

**Interfaces:**
- Produces: `PerspectivalResolver.loadAllOverlays(String tenantId)` package-private method
- Produces: PerspectivalResolver class visibility → package-private

- [ ] **Step 1: Write failing test for loadAllOverlays**

Add to PerspectivalResolverTest:

```java
@Test
void loadAllOverlaysReturnsAllOverlayNodesForTenant() {
    // Create two overlay nodes for different agents
    PrincipalId alice = new PrincipalId("alice");
    PrincipalId bob = new PrincipalId("bob");

    String sharedNodeId = mindMapStore.addNode(
        NodeInput.of("Grandma", subgraphId, TENANT).withConfidence(CONF));

    mindMapStore.addNode(NodeInput.of("alice-overlay", subgraphId, TENANT)
        .withTraits(Set.of("overlay"))
        .withRefs(Set.of(OverlayRef.of(sharedNodeId)))
        .withProperties(Map.of(OverlayRef.AGENT_ID, "alice"))
        .withConfidence(CONF));

    mindMapStore.addNode(NodeInput.of("bob-overlay", subgraphId, TENANT)
        .withTraits(Set.of("overlay"))
        .withRefs(Set.of(OverlayRef.of(sharedNodeId)))
        .withProperties(Map.of(OverlayRef.AGENT_ID, "bob"))
        .withConfidence(CONF));

    List<MindMapNode> allOverlays = resolver.loadAllOverlays(TENANT);
    assertThat(allOverlays).hasSize(2);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PerspectivalResolverTest#loadAllOverlaysReturnsAllOverlayNodesForTenant`
Expected: compilation failure — `loadAllOverlays` does not exist

- [ ] **Step 3: Extract loadAllOverlays from existing loadOverlays**

Use `ide_replace_member` on PerspectivalResolver to refactor the existing private `loadOverlays(tenantId, principal)` method:

```java
List<MindMapNode> loadAllOverlays(String tenantId) {
    MindMapQuery query = MindMapQuery.of(tenantId, 1000)
                                     .withTraits(Set.of("overlay"));
    return mindMapStore.search(query);
}

private Map<String, MindMapNode> loadOverlays(String tenantId, PrincipalId principal) {
    List<MindMapNode> allOverlays = loadAllOverlays(tenantId);
    Map<String, MindMapNode> map = new HashMap<>();
    for (MindMapNode node : allOverlays) {
        if (principal.value().equals(node.properties().get(OverlayRef.AGENT_ID))) {
            OverlayRef.sharedNodeId(node).ifPresent(sharedId -> map.put(sharedId, node));
        }
    }
    return map;
}
```

- [ ] **Step 4: Change PerspectivalResolver visibility to package-private**

Remove `@ApplicationScoped` annotation and `public` modifier from the class declaration. Change `public PerspectivalResolver(Instance<MindMapStore>...)` constructor to package-private. Change `public List<MindMapNode> resolve(...)` to package-private.

Remove the `@Inject` annotation from the CDI constructor since it's no longer a CDI bean.

- [ ] **Step 5: Fix compilation — update PerspectivalResolverTest**

PerspectivalResolverTest is in the same package — it can still access package-private members. Verify it compiles. Remove any CDI-specific test infrastructure if present.

- [ ] **Step 6: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: all tests pass. PerspectivalResolverTest still works (same package).

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor(cognitive-index): internalize PerspectivalResolver as package-private

Reverses #253 D55 — zero external production callers confirmed.
Adds loadAllOverlays() for batched overlay loading.

Refs #271"
```

### Task 3: CognitiveProfile perspective-aware resolve()

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfile.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveProfileTest.java`

**Interfaces:**
- Consumes: `CognitiveProfileQuery.asSeenBy()`, `EntityKnowledge(... perceiver)`, `PerspectivalResolver` (package-private)
- Produces: `CognitiveProfile.resolve(query)` — now perspective-aware when `asSeenBy` is set

- [ ] **Step 1: Write failing test — resolve with asSeenBy applies overlay before trajectory**

Add to CognitiveProfileTest:

```java
@Test
void resolveWithAsSeenByAppliesOverlayBeforeTrajectory() {
    // Create shared node with no PAD
    String subgraphId = mindMapStore.addSubgraph(
        SubgraphInput.of("test-sg", "general", TENANT));
    String nodeId = mindMapStore.addNode(
        NodeInput.of("Grandma", subgraphId, TENANT).withConfidence(CONF));

    // Create overlay with pleasure=0.9 for alice
    PrincipalId alice = new PrincipalId("alice");
    mindMapStore.addNode(NodeInput.of("alice-overlay", subgraphId, TENANT)
        .withTraits(Set.of("overlay"))
        .withRefs(Set.of(OverlayRef.of(nodeId)))
        .withProperties(Map.of(OverlayRef.AGENT_ID, "alice"))
        .withPleasure(0.9).withArousal(0.3).withDominance(0.5)
        .withConfidence(CONF));

    var query = CognitiveProfileQuery.byId(nodeId, TENANT)
        .withAsSeenBy(alice);
    var ek = profile.resolve(query);

    assertThat(ek).isPresent();
    assertThat(ek.get().node().pleasure()).isEqualTo(0.9);
    assertThat(ek.get().perceiver()).isEqualTo(alice);
}

@Test
void resolveWithoutAsSeenByReturnsSharedView() {
    String subgraphId = mindMapStore.addSubgraph(
        SubgraphInput.of("test-sg", "general", TENANT));
    String nodeId = mindMapStore.addNode(
        NodeInput.of("Grandma", subgraphId, TENANT).withConfidence(CONF));

    var query = CognitiveProfileQuery.byId(nodeId, TENANT);
    var ek = profile.resolve(query);

    assertThat(ek).isPresent();
    assertThat(ek.get().node().pleasure()).isNull();
    assertThat(ek.get().perceiver()).isNull();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileTest#resolveWithAsSeenByAppliesOverlayBeforeTrajectory`
Expected: FAIL — pleasure is null (overlay not applied)

- [ ] **Step 3: Integrate PerspectivalResolver into CognitiveProfile**

Use `ide_replace_member` on CognitiveProfile to:

1. Add `PerspectivalResolver` field (constructed internally, not injected):
```java
private final PerspectivalResolver perspectivalResolver;
```

2. Initialize in both constructors:
```java
// CDI constructor
this.perspectivalResolver = this.mindMapStore != null
    ? new PerspectivalResolver(this.mindMapStore) : null;

// Test constructor
this.perspectivalResolver = mindMapStore != null
    ? new PerspectivalResolver(mindMapStore) : null;
```

3. Remove the unused `cbrStore` field and its constructor parameter (cleanup from spec review).

4. Modify `resolve()` to apply perspective before trajectory:
```java
public Optional<EntityKnowledge> resolve(CognitiveProfileQuery query) {
    if (mindMapStore == null) { return Optional.empty(); }

    MindMapNode node = resolveNode(query);
    if (node == null) { return Optional.empty(); }

    // Apply perspectival overlay BEFORE trajectory computation
    PrincipalId asSeenBy = query.asSeenBy();
    if (asSeenBy != null && perspectivalResolver != null) {
        List<MindMapNode> resolved = perspectivalResolver.resolve(
            List.of(node), asSeenBy, query.tenantId());
        node = resolved.getFirst();
    }

    List<String> entityIds = collectEntityIds(node);
    Set<NodeRef> unresolvedRefs = collectUnresolvedRefs(node);

    List<MindMapEdge> edges = query.includeEdges()
        ? mindMapStore.neighbors(node.id(), query.tenantId())
        : List.of();

    Set<MemoryDomain> domains = query.domains().isEmpty()
        ? DEFAULT_DOMAINS : query.domains();

    Map<MemoryDomain, List<Memory>> memories =
        queryMemories(entityIds, domains, query);

    AffectTrajectory trajectory =
        computeTrajectory(entityIds, memories, query);

    return Optional.of(new EntityKnowledge(
        node, edges, memories, trajectory, unresolvedRefs,
        query.tenantId(), asSeenBy));
}
```

- [ ] **Step 4: Write failing test — principal-scoped memory queries**

```java
@Test
void resolveWithAsSeenByScopesMemoriesByPrincipal() {
    String subgraphId = mindMapStore.addSubgraph(
        SubgraphInput.of("test-sg", "general", TENANT));
    String nodeId = mindMapStore.addNode(
        NodeInput.of("Entity", subgraphId, TENANT).withConfidence(CONF));

    PrincipalId alice = new PrincipalId("alice");

    // Store memories: one owned by alice, one by bob
    memoryStore.store(MemoryInput.of("alice memory", AFFECT, TENANT)
        .withSubject("unknown", nodeId)
        .withPrincipalId(alice)
        .withPleasure(0.8));
    memoryStore.store(MemoryInput.of("bob memory", AFFECT, TENANT)
        .withSubject("unknown", nodeId)
        .withPrincipalId(new PrincipalId("bob"))
        .withPleasure(-0.5));

    var query = CognitiveProfileQuery.byId(nodeId, TENANT)
        .withAsSeenBy(alice)
        .withDomains(Set.of(AFFECT));
    var ek = profile.resolve(query);

    assertThat(ek).isPresent();
    // Only alice's memory should be returned
    var affectMemories = ek.get().memories().get(AFFECT);
    assertThat(affectMemories).hasSize(1);
}
```

- [ ] **Step 5: Add principal scoping to queryMemories**

Use `ide_replace_member` on `queryMemories`:

```java
private Map<MemoryDomain, List<Memory>> queryMemories(
        List<String> entityIds, Set<MemoryDomain> domains,
        CognitiveProfileQuery query) {
    if (memoryStore == null) { return Map.of(); }
    Map<MemoryDomain, List<Memory>> result = new LinkedHashMap<>();
    for (MemoryDomain domain : domains) {
        var memQuery = MemoryQuery.forSubjects(
            entityIds.stream()
                .map(id -> io.casehub.neocortex.memory.Subject.of("unknown", id))
                .toList(),
            domain, query.tenantId())
            .withLimit(query.memoryLimit())
            .withOrder(MemoryOrder.CHRONOLOGICAL);

        // Principal scoping when perspective is set
        if (query.asSeenBy() != null) {
            memQuery = memQuery.withCallerPrincipalId(query.asSeenBy());
        }

        List<Memory> memories = memoryStore.query(memQuery);
        if (!memories.isEmpty()) {
            result.put(domain, memories);
        }
    }
    return result;
}
```

- [ ] **Step 6: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: all tests pass including new perspective tests

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): perspective-aware resolve() with principal-scoped memories

Perspective applied before trajectory computation — fixes structural
bug where trajectory was computed on unmerged shared node PAD.
Memory queries scoped by withCallerPrincipalId when asSeenBy is set.
Removes unused CbrCaseMemoryStore injection.

Refs #271"
```

---

## Batch 2: Multi-Agent Comparison (#271)

After this batch: `CognitiveProfile.compare()` returns N perspectival EntityKnowledge records. `SocialComparison.compare()` computes divergence metrics. #271 complete.

### Task 4: CognitiveProfile.compare() batched method

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfile.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveProfileTest.java`

**Interfaces:**
- Consumes: `PerspectivalResolver.loadAllOverlays(String)`, `PerspectivalMerge.merge(MindMapNode, MindMapNode)`, `AffectTrajectoryAnalyzer.analyze(List<Memory>)`
- Produces: `CognitiveProfile.compare(CognitiveProfileQuery, Set<PrincipalId>)` → `Map<PrincipalId, EntityKnowledge>`

- [ ] **Step 1: Write failing test — compare returns per-agent EntityKnowledge**

```java
@Test
void compareReturnsPerspectivePerAgent() {
    String subgraphId = mindMapStore.addSubgraph(
        SubgraphInput.of("test-sg", "general", TENANT));
    String nodeId = mindMapStore.addNode(
        NodeInput.of("Grandma", subgraphId, TENANT).withConfidence(CONF));

    PrincipalId alice = new PrincipalId("alice");
    PrincipalId bob = new PrincipalId("bob");

    // Alice overlay: pleasure=0.9
    mindMapStore.addNode(NodeInput.of("alice-o", subgraphId, TENANT)
        .withTraits(Set.of("overlay"))
        .withRefs(Set.of(OverlayRef.of(nodeId)))
        .withProperties(Map.of(OverlayRef.AGENT_ID, "alice"))
        .withPleasure(0.9).withConfidence(CONF));

    // Bob overlay: pleasure=-0.2
    mindMapStore.addNode(NodeInput.of("bob-o", subgraphId, TENANT)
        .withTraits(Set.of("overlay"))
        .withRefs(Set.of(OverlayRef.of(nodeId)))
        .withProperties(Map.of(OverlayRef.AGENT_ID, "bob"))
        .withPleasure(-0.2).withConfidence(CONF));

    var query = CognitiveProfileQuery.byId(nodeId, TENANT);
    Map<PrincipalId, EntityKnowledge> result =
        profile.compare(query, Set.of(alice, bob));

    assertThat(result).hasSize(2);
    assertThat(result.get(alice).node().pleasure()).isEqualTo(0.9);
    assertThat(result.get(bob).node().pleasure()).isEqualTo(-0.2);
    assertThat(result.get(alice).perceiver()).isEqualTo(alice);
    assertThat(result.get(bob).perceiver()).isEqualTo(bob);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileTest#compareReturnsPerspectivePerAgent`
Expected: compilation failure — `compare` method does not exist

- [ ] **Step 3: Implement compare()**

Use `ide_insert_member` on CognitiveProfile:

```java
public Map<PrincipalId, EntityKnowledge> compare(
        CognitiveProfileQuery query, Set<PrincipalId> agents) {
    if (mindMapStore == null || agents.isEmpty()) { return Map.of(); }

    MindMapNode sharedNode = resolveNode(query);
    if (sharedNode == null) { return Map.of(); }

    // Load ALL overlays once — single store hit
    List<MindMapNode> allOverlays = perspectivalResolver != null
        ? perspectivalResolver.loadAllOverlays(query.tenantId())
        : List.of();

    // Partition by agentId
    Map<String, MindMapNode> overlaysByAgent = new HashMap<>();
    for (MindMapNode overlay : allOverlays) {
        String agentId = overlay.properties().get(OverlayRef.AGENT_ID);
        if (agentId != null) {
            OverlayRef.sharedNodeId(overlay).ifPresent(sid -> {
                if (sid.equals(sharedNode.id())) {
                    overlaysByAgent.put(agentId, overlay);
                }
            });
        }
    }

    Set<MemoryDomain> domains = query.domains().isEmpty()
        ? DEFAULT_DOMAINS : query.domains();

    Map<PrincipalId, EntityKnowledge> result = new LinkedHashMap<>();
    for (PrincipalId agent : agents) {
        MindMapNode agentNode = overlaysByAgent.containsKey(agent.value())
            ? PerspectivalMerge.merge(sharedNode, overlaysByAgent.get(agent.value()))
            : sharedNode;

        List<String> entityIds = collectEntityIds(agentNode);
        Set<NodeRef> unresolvedRefs = collectUnresolvedRefs(agentNode);

        List<MindMapEdge> edges = query.includeEdges()
            ? mindMapStore.neighbors(agentNode.id(), query.tenantId())
            : List.of();

        // Principal-scoped query for this agent
        CognitiveProfileQuery agentQuery = query.withAsSeenBy(agent);
        Map<MemoryDomain, List<Memory>> memories =
            queryMemories(entityIds, domains, agentQuery);
        AffectTrajectory trajectory =
            computeTrajectory(entityIds, memories, agentQuery);

        result.put(agent, new EntityKnowledge(
            agentNode, edges, memories, trajectory, unresolvedRefs,
            query.tenantId(), agent));
    }
    return result;
}
```

- [ ] **Step 4: Write test — compare loads overlays once (efficiency)**

```java
@Test
void compareLoadsOverlaysOnce() {
    // This test verifies batched behavior — we test it by confirming
    // compare() works with 3 agents and returns correct results for each.
    // The single-scan guarantee is structural (one loadAllOverlays call).
    String subgraphId = mindMapStore.addSubgraph(
        SubgraphInput.of("test-sg", "general", TENANT));
    String nodeId = mindMapStore.addNode(
        NodeInput.of("Entity", subgraphId, TENANT).withConfidence(CONF));

    PrincipalId a = new PrincipalId("a");
    PrincipalId b = new PrincipalId("b");
    PrincipalId c = new PrincipalId("c");

    for (var agent : List.of(a, b, c)) {
        mindMapStore.addNode(NodeInput.of(agent.value() + "-o", subgraphId, TENANT)
            .withTraits(Set.of("overlay"))
            .withRefs(Set.of(OverlayRef.of(nodeId)))
            .withProperties(Map.of(OverlayRef.AGENT_ID, agent.value()))
            .withPleasure(agent.value().charAt(0) * 0.1)
            .withConfidence(CONF));
    }

    var result = profile.compare(
        CognitiveProfileQuery.byId(nodeId, TENANT), Set.of(a, b, c));
    assertThat(result).hasSize(3);
    assertThat(result.keySet()).containsExactlyInAnyOrder(a, b, c);
}
```

- [ ] **Step 5: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): batched compare() for multi-agent perspective resolution

Single overlay scan for all agents. Each agent gets principal-scoped
memories and perspectival trajectory.

Refs #271"
```

### Task 5: SocialComparison static utility and result records

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/SocialComparison.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalComparison.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/AffectSnapshot.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PadDistanceMatrix.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/AgentPair.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PairwiseDifferences.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PadDimension.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TrajectoryAlignment.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TrendAgreement.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/SocialComparisonTest.java`

**Interfaces:**
- Consumes: `EntityKnowledge`, `AffectTrajectory`, `TrendDirection`, `PrincipalId`
- Produces: `SocialComparison.compare(Map<PrincipalId, EntityKnowledge>)` → `PerspectivalComparison`

- [ ] **Step 1: Create result record types**

Create all record types first (they have no behavior to test independently):

**PadDimension.java:**
```java
package io.casehub.neocortex.cognitive.index;
public enum PadDimension { PLEASURE, AROUSAL, DOMINANCE }
```

**TrendAgreement.java:**
```java
package io.casehub.neocortex.cognitive.index;
public enum TrendAgreement { ALIGNED, DIVERGENT, MIXED, INSUFFICIENT }
```

**AgentPair.java:**
```java
package io.casehub.neocortex.cognitive.index;
import io.casehub.platform.api.identity.PrincipalId;
import java.util.Objects;

public record AgentPair(PrincipalId a, PrincipalId b) {
    public AgentPair {
        Objects.requireNonNull(a);
        Objects.requireNonNull(b);
        if (a.value().compareTo(b.value()) > 0) {
            PrincipalId temp = a; a = b; b = temp;
        }
    }
    public static AgentPair of(PrincipalId a, PrincipalId b) {
        return new AgentPair(a, b);
    }
}
```

**AffectSnapshot.java:**
```java
package io.casehub.neocortex.cognitive.index;
import io.casehub.platform.api.identity.PrincipalId;
import java.util.Objects;

public record AffectSnapshot(
    PrincipalId agent,
    Double pleasure, Double arousal, Double dominance,
    AffectTrajectory trajectory
) {
    public AffectSnapshot { Objects.requireNonNull(agent); }
}
```

**PadDistanceMatrix.java:**
```java
package io.casehub.neocortex.cognitive.index;
import java.util.Map;

public record PadDistanceMatrix(Map<AgentPair, Double> distances) {
    public PadDistanceMatrix { distances = Map.copyOf(distances); }
    public double distance(io.casehub.platform.api.identity.PrincipalId a,
                          io.casehub.platform.api.identity.PrincipalId b) {
        return distances.getOrDefault(AgentPair.of(a, b), 0.0);
    }
    public double maxDistance() {
        return distances.values().stream().mapToDouble(d -> d).max().orElse(0.0);
    }
    public double meanDistance() {
        return distances.values().stream().mapToDouble(d -> d).average().orElse(0.0);
    }
}
```

**PairwiseDifferences.java:**
```java
package io.casehub.neocortex.cognitive.index;
import io.casehub.platform.api.identity.PrincipalId;
import java.util.Map;

public record PairwiseDifferences(Map<AgentPair, Double> differences) {
    public PairwiseDifferences { differences = Map.copyOf(differences); }
    public double difference(PrincipalId a, PrincipalId b) {
        AgentPair pair = AgentPair.of(a, b);
        double raw = differences.getOrDefault(pair, 0.0);
        return a.value().compareTo(b.value()) <= 0 ? raw : -raw;
    }
}
```

**TrajectoryAlignment.java:**
```java
package io.casehub.neocortex.cognitive.index;
import java.util.Map;

public record TrajectoryAlignment(
    Map<AgentPair, Double> cosineSimilarities,
    Map<AgentPair, TrendAgreement> agreements
) {
    public TrajectoryAlignment {
        cosineSimilarities = Map.copyOf(cosineSimilarities);
        agreements = Map.copyOf(agreements);
    }
}
```

**PerspectivalComparison.java:**
```java
package io.casehub.neocortex.cognitive.index;
import io.casehub.platform.api.identity.PrincipalId;
import java.util.Map;
import java.util.Set;

public record PerspectivalComparison(
    String entityId, String entityName,
    Map<PrincipalId, AffectSnapshot> perspectives,
    Set<PrincipalId> unassessedAgents,
    PadDistanceMatrix distances,
    Map<PadDimension, PairwiseDifferences> dimensionDifferences,
    TrajectoryAlignment trajectoryAlignment,
    int agentCount
) {}
```

- [ ] **Step 2: Write failing tests for SocialComparison**

```java
@Test
void compareTwoAgentsComputesPadDistance() {
    PrincipalId alice = new PrincipalId("alice");
    PrincipalId bob = new PrincipalId("bob");

    var perspectives = Map.of(
        alice, ekWithPad(alice, 0.9, 0.3, 0.5),
        bob, ekWithPad(bob, -0.2, 0.7, 0.1));

    PerspectivalComparison result = SocialComparison.compare(perspectives);

    assertThat(result.agentCount()).isEqualTo(2);
    double dist = result.distances().distance(alice, bob);
    // sqrt((0.9-(-0.2))^2 + (0.3-0.7)^2 + (0.5-0.1)^2) = sqrt(1.21+0.16+0.16) ≈ 1.237
    assertThat(dist).isCloseTo(1.237, within(0.01));
}

@Test
void compareTwoAgentsComputesSignedDifferences() {
    PrincipalId alice = new PrincipalId("alice");
    PrincipalId bob = new PrincipalId("bob");

    var perspectives = Map.of(
        alice, ekWithPad(alice, 0.9, 0.3, 0.5),
        bob, ekWithPad(bob, -0.2, 0.7, 0.1));

    PerspectivalComparison result = SocialComparison.compare(perspectives);

    double pleasureDiff = result.dimensionDifferences()
        .get(PadDimension.PLEASURE).difference(alice, bob);
    assertThat(pleasureDiff).isCloseTo(1.1, within(0.001));
}

@Test
void compareAlignedTrajectories() {
    PrincipalId alice = new PrincipalId("alice");
    PrincipalId bob = new PrincipalId("bob");

    var perspectives = Map.of(
        alice, ekWithTrajectory(alice, 0.5, 0.3),   // improving
        bob, ekWithTrajectory(bob, 0.3, 0.2));       // also improving

    PerspectivalComparison result = SocialComparison.compare(perspectives);

    AgentPair pair = AgentPair.of(alice, bob);
    assertThat(result.trajectoryAlignment().agreements().get(pair))
        .isEqualTo(TrendAgreement.ALIGNED);
    assertThat(result.trajectoryAlignment().cosineSimilarities().get(pair))
        .isGreaterThan(0.9);
}

@Test
void compareDivergentTrajectories() {
    PrincipalId alice = new PrincipalId("alice");
    PrincipalId bob = new PrincipalId("bob");

    var perspectives = Map.of(
        alice, ekWithTrajectory(alice, 0.5, 0.3),    // improving
        bob, ekWithTrajectory(bob, -0.5, -0.3));      // worsening

    PerspectivalComparison result = SocialComparison.compare(perspectives);

    AgentPair pair = AgentPair.of(alice, bob);
    assertThat(result.trajectoryAlignment().agreements().get(pair))
        .isEqualTo(TrendAgreement.DIVERGENT);
    assertThat(result.trajectoryAlignment().cosineSimilarities().get(pair))
        .isLessThan(-0.9);
}

@Test
void nullPadTreatedAsZero() {
    PrincipalId alice = new PrincipalId("alice");
    PrincipalId bob = new PrincipalId("bob");

    var perspectives = Map.of(
        alice, ekWithPad(alice, null, null, null),
        bob, ekWithPad(bob, 0.5, 0.5, 0.5));

    PerspectivalComparison result = SocialComparison.compare(perspectives);
    double dist = result.distances().distance(alice, bob);
    // sqrt(0.25+0.25+0.25) ≈ 0.866
    assertThat(dist).isCloseTo(0.866, within(0.01));
}
```

Add helper methods to the test class:
```java
private EntityKnowledge ekWithPad(PrincipalId agent, Double p, Double a, Double d) {
    var node = new StubNode("id-" + agent.value(), "entity", "sg", "general",
        null, null, Instant.now(), Instant.now(), null, null,
        Set.of(), Set.of(), p, a, d, Map.of(), null, Set.of());
    return new EntityKnowledge(node, List.of(), Map.of(), null, Set.of(), "t1", agent);
}

private EntityKnowledge ekWithTrajectory(PrincipalId agent,
        double pleasureSlope, double dominanceSlope) {
    var node = StubNode.named("entity");
    var trajectory = new AffectTrajectory(
        pleasureSlope, 0.1, dominanceSlope,
        pleasureSlope > 0 ? TrendDirection.IMPROVING : TrendDirection.WORSENING,
        Math.abs(pleasureSlope), 10);
    return new EntityKnowledge(node, List.of(), Map.of(), trajectory, Set.of(), "t1", agent);
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=SocialComparisonTest`
Expected: compilation failure — SocialComparison class does not exist

- [ ] **Step 4: Implement SocialComparison**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.platform.api.identity.PrincipalId;
import java.util.*;

public final class SocialComparison {
    private SocialComparison() {}

    public static PerspectivalComparison compare(
            Map<PrincipalId, EntityKnowledge> perspectives) {
        if (perspectives.isEmpty()) {
            throw new IllegalArgumentException("at least one perspective required");
        }

        EntityKnowledge first = perspectives.values().iterator().next();
        String entityId = first.node().id();
        String entityName = first.node().name();

        Map<PrincipalId, AffectSnapshot> snapshots = new LinkedHashMap<>();
        Set<PrincipalId> unassessed = new LinkedHashSet<>();

        for (var entry : perspectives.entrySet()) {
            PrincipalId agent = entry.getKey();
            EntityKnowledge ek = entry.getValue();
            Double p = ek.node().pleasure();
            Double a = ek.node().arousal();
            Double d = ek.node().dominance();
            if (p == null && a == null && d == null) {
                unassessed.add(agent);
            }
            snapshots.put(agent, new AffectSnapshot(agent, p, a, d, ek.trajectory()));
        }

        List<PrincipalId> assessed = perspectives.keySet().stream()
            .filter(a -> !unassessed.contains(a)).toList();

        PadDistanceMatrix distances = computeDistances(snapshots, assessed);
        Map<PadDimension, PairwiseDifferences> diffs = computeDifferences(snapshots, assessed);
        TrajectoryAlignment alignment = computeAlignment(perspectives, assessed);

        return new PerspectivalComparison(entityId, entityName, snapshots,
            unassessed, distances, diffs, alignment, perspectives.size());
    }

    private static PadDistanceMatrix computeDistances(
            Map<PrincipalId, AffectSnapshot> snapshots, List<PrincipalId> assessed) {
        Map<AgentPair, Double> distances = new LinkedHashMap<>();
        for (int i = 0; i < assessed.size(); i++) {
            for (int j = i + 1; j < assessed.size(); j++) {
                AffectSnapshot a = snapshots.get(assessed.get(i));
                AffectSnapshot b = snapshots.get(assessed.get(j));
                double dp = pad(a.pleasure()) - pad(b.pleasure());
                double da = pad(a.arousal()) - pad(b.arousal());
                double dd = pad(a.dominance()) - pad(b.dominance());
                distances.put(AgentPair.of(assessed.get(i), assessed.get(j)),
                    Math.sqrt(dp * dp + da * da + dd * dd));
            }
        }
        return new PadDistanceMatrix(distances);
    }

    private static Map<PadDimension, PairwiseDifferences> computeDifferences(
            Map<PrincipalId, AffectSnapshot> snapshots, List<PrincipalId> assessed) {
        Map<PadDimension, PairwiseDifferences> result = new LinkedHashMap<>();
        for (PadDimension dim : PadDimension.values()) {
            Map<AgentPair, Double> diffs = new LinkedHashMap<>();
            for (int i = 0; i < assessed.size(); i++) {
                for (int j = i + 1; j < assessed.size(); j++) {
                    AffectSnapshot a = snapshots.get(assessed.get(i));
                    AffectSnapshot b = snapshots.get(assessed.get(j));
                    double va = padDim(a, dim);
                    double vb = padDim(b, dim);
                    diffs.put(AgentPair.of(assessed.get(i), assessed.get(j)), va - vb);
                }
            }
            result.put(dim, new PairwiseDifferences(diffs));
        }
        return result;
    }

    private static TrajectoryAlignment computeAlignment(
            Map<PrincipalId, EntityKnowledge> perspectives, List<PrincipalId> assessed) {
        Map<AgentPair, Double> cosines = new LinkedHashMap<>();
        Map<AgentPair, TrendAgreement> agreements = new LinkedHashMap<>();

        for (int i = 0; i < assessed.size(); i++) {
            for (int j = i + 1; j < assessed.size(); j++) {
                PrincipalId ai = assessed.get(i);
                PrincipalId aj = assessed.get(j);
                AgentPair pair = AgentPair.of(ai, aj);
                AffectTrajectory ta = perspectives.get(ai).trajectory();
                AffectTrajectory tb = perspectives.get(aj).trajectory();

                if (ta == null || tb == null || ta.sampleCount() < 2 || tb.sampleCount() < 2) {
                    cosines.put(pair, 0.0);
                    agreements.put(pair, TrendAgreement.INSUFFICIENT);
                    continue;
                }

                double[] va = {ta.pleasureSlope(), ta.dominanceSlope()};
                double[] vb = {tb.pleasureSlope(), tb.dominanceSlope()};
                double dot = va[0] * vb[0] + va[1] * vb[1];
                double magA = Math.sqrt(va[0] * va[0] + va[1] * va[1]);
                double magB = Math.sqrt(vb[0] * vb[0] + vb[1] * vb[1]);

                double cosine = (magA < 1e-9 || magB < 1e-9) ? 0.0 : dot / (magA * magB);
                cosines.put(pair, cosine);

                TrendAgreement agreement;
                if (ta.trend() == tb.trend()) {
                    agreement = ta.trend() == TrendDirection.STABLE
                        ? TrendAgreement.ALIGNED : TrendAgreement.ALIGNED;
                } else if (ta.trend() == TrendDirection.STABLE
                        || tb.trend() == TrendDirection.STABLE) {
                    agreement = TrendAgreement.MIXED;
                } else {
                    agreement = TrendAgreement.DIVERGENT;
                }
                agreements.put(pair, agreement);
            }
        }
        return new TrajectoryAlignment(cosines, agreements);
    }

    private static double pad(Double v) { return v != null ? v : 0.0; }

    private static double padDim(AffectSnapshot s, PadDimension dim) {
        return switch (dim) {
            case PLEASURE -> pad(s.pleasure());
            case AROUSAL -> pad(s.arousal());
            case DOMINANCE -> pad(s.dominance());
        };
    }
}
```

- [ ] **Step 5: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): SocialComparison utility — PAD distance, pairwise differences, trajectory alignment

Static utility following AffectTrajectoryAnalyzer pattern. Computes
multi-agent divergence from Map<PrincipalId, EntityKnowledge>.

Closes #271"
```

---

## Batch 3: Cross-Domain Reasoning (#283)

After this batch: `DomainActivation.correlate()` returns cross-subgraph DTW similarity with alignment paths. #283 complete.

### Task 6: DomainActivation CDI bean with DTW correlation

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainActivation.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainActivationQuery.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainActivationResult.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainSignal.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainPair.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DomainCorrelation.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CorrelationStrength.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PadDtw.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PadDtwTest.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/DomainActivationTest.java`

**Interfaces:**
- Consumes: `MindMapStore.search(MindMapQuery)`, `CaseMemoryStore.query(MemoryQuery)`, `AffectTrajectoryAnalyzer.analyze(List<Memory>)`, `PrincipalId`
- Produces: `DomainActivation.correlate(DomainActivationQuery)` → `Optional<DomainActivationResult>`

- [ ] **Step 1: Create result record types**

**CorrelationStrength.java:**
```java
package io.casehub.neocortex.cognitive.index;
public enum CorrelationStrength {
    STRONG, MODERATE, WEAK, NONE;
    public static CorrelationStrength fromSimilarity(double s) {
        if (s >= 0.7) return STRONG;
        if (s >= 0.4) return MODERATE;
        if (s >= 0.2) return WEAK;
        return NONE;
    }
}
```

**DomainPair.java, DomainSignal.java, DomainCorrelation.java, DomainActivationResult.java, DomainActivationQuery.java** — per spec. Create all record types.

- [ ] **Step 2: Write failing test for PadDtw — general-purpose DTW over double arrays**

Create PadDtwTest:

```java
@Test
void identicalSeriesHasZeroCost() {
    double[] a = {0.1, 0.2, 0.3, 0.4, 0.5};
    double[] b = {0.1, 0.2, 0.3, 0.4, 0.5};
    PadDtw.DtwResult result = PadDtw.compute(a, b);
    assertThat(result.normalizedCost()).isCloseTo(0.0, within(0.001));
    assertThat(result.alignment()).hasSize(5);
}

@Test
void oppositeSeriesHasHighCost() {
    double[] a = {-1.0, -0.5, 0.0, 0.5, 1.0};
    double[] b = {1.0, 0.5, 0.0, -0.5, -1.0};
    PadDtw.DtwResult result = PadDtw.compute(a, b);
    assertThat(result.normalizedCost()).isGreaterThan(0.5);
}

@Test
void similarityIsInverseCost() {
    double[] a = {0.1, 0.2, 0.3};
    double[] b = {0.1, 0.2, 0.3};
    PadDtw.DtwResult result = PadDtw.compute(a, b);
    assertThat(result.similarity()).isCloseTo(1.0, within(0.001));
}
```

- [ ] **Step 3: Implement PadDtw — lightweight DTW for 1D double arrays**

```java
package io.casehub.neocortex.cognitive.index;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public final class PadDtw {
    private PadDtw() {}

    public record DtwResult(double normalizedCost, double similarity,
                            List<int[]> alignment) {}

    public static DtwResult compute(double[] query, double[] candidate) {
        int n = query.length, m = candidate.length;
        if (n == 0 || m == 0) {
            return new DtwResult(Double.MAX_VALUE, 0.0, List.of());
        }

        double[][] cost = new double[n + 1][m + 1];
        for (int i = 0; i <= n; i++) cost[i][0] = Double.MAX_VALUE;
        for (int j = 0; j <= m; j++) cost[0][j] = Double.MAX_VALUE;
        cost[0][0] = 0;

        for (int i = 1; i <= n; i++) {
            for (int j = 1; j <= m; j++) {
                double d = Math.abs(query[i - 1] - candidate[j - 1]);
                cost[i][j] = d + Math.min(cost[i - 1][j],
                    Math.min(cost[i][j - 1], cost[i - 1][j - 1]));
            }
        }

        double normalizedCost = cost[n][m] / Math.max(n, m);

        // Backtrace
        List<int[]> alignment = new ArrayList<>();
        int i = n, j = m;
        while (i > 0 && j > 0) {
            alignment.add(new int[]{i - 1, j - 1});
            double diag = cost[i - 1][j - 1];
            double left = cost[i][j - 1];
            double up = cost[i - 1][j];
            if (diag <= left && diag <= up) { i--; j--; }
            else if (up <= left) { i--; }
            else { j--; }
        }
        Collections.reverse(alignment);

        double similarity = 1.0 / (1.0 + normalizedCost);
        return new DtwResult(normalizedCost, similarity, alignment);
    }
}
```

- [ ] **Step 4: Run PadDtw tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PadDtwTest`
Expected: PASS

- [ ] **Step 5: Write failing tests for DomainActivation**

```java
@Test
void correlateTwoSubgraphsWithCorrelatedSignals() {
    // Create two subgraphs with entities that have correlated affect
    String workSg = mindMapStore.addSubgraph(
        SubgraphInput.of("work", "organisation", TENANT));
    String familySg = mindMapStore.addSubgraph(
        SubgraphInput.of("family", "person", TENANT));

    String workEntity = mindMapStore.addNode(
        NodeInput.of("Project", workSg, TENANT).withConfidence(CONF));
    String familyEntity = mindMapStore.addNode(
        NodeInput.of("Spouse", familySg, TENANT).withConfidence(CONF));

    PrincipalId alice = new PrincipalId("alice");
    Instant base = Instant.parse("2026-01-01T00:00:00Z");

    // Store affect memories with correlated pleasure values
    for (int day = 0; day < 10; day++) {
        double pleasure = 0.1 * day;  // increasing
        Instant t = base.plus(java.time.Duration.ofDays(day));
        memoryStore.store(MemoryInput.of("work-" + day, AFFECT, TENANT)
            .withSubject("unknown", workEntity)
            .withPrincipalId(alice).withPleasure(pleasure).withCreatedAt(t));
        memoryStore.store(MemoryInput.of("family-" + day, AFFECT, TENANT)
            .withSubject("unknown", familyEntity)
            .withPrincipalId(alice).withPleasure(pleasure * 0.8).withCreatedAt(t));
    }

    var query = DomainActivationQuery.between(alice, TENANT, workSg, familySg)
        .withFrom(base).withTo(base.plus(java.time.Duration.ofDays(10)));
    var result = domainActivation.correlate(query);

    assertThat(result).isPresent();
    var corr = result.get().correlations()
        .get(new DomainPair(familySg, workSg));
    assertThat(corr.strength()).isIn(CorrelationStrength.STRONG, CorrelationStrength.MODERATE);
}

@Test
void correlateRequiresPrincipal() {
    assertThatThrownBy(() -> new DomainActivationQuery(
        null, Set.of("a", "b"), TENANT, null, null, null))
        .isInstanceOf(NullPointerException.class);
}

@Test
void correlateEmptySubgraphReturnsEmpty() {
    String emptySg = mindMapStore.addSubgraph(
        SubgraphInput.of("empty", "general", TENANT));
    String otherSg = mindMapStore.addSubgraph(
        SubgraphInput.of("other", "general", TENANT));

    PrincipalId alice = new PrincipalId("alice");
    var query = DomainActivationQuery.between(alice, TENANT, emptySg, otherSg);
    assertThat(domainActivation.correlate(query)).isEmpty();
}

@Test
void correlateGracefulDegradationNoMindMapStore() {
    var degraded = new DomainActivation(null, memoryStore);
    PrincipalId alice = new PrincipalId("alice");
    var query = DomainActivationQuery.between(alice, TENANT, "a", "b");
    assertThat(degraded.correlate(query)).isEmpty();
}
```

- [ ] **Step 6: Implement DomainActivation**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryOrder;
import io.casehub.neocortex.memory.MemoryQuery;
import io.casehub.neocortex.memory.Subject;
import io.casehub.neocortex.memory.mood.AffectEvents;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapQuery;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.platform.api.identity.PrincipalId;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.time.Duration;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;

@ApplicationScoped
public class DomainActivation {

    private final MindMapStore mindMapStore;
    private final CaseMemoryStore memoryStore;

    @Inject
    public DomainActivation(Instance<MindMapStore> mindMapStore,
                            Instance<CaseMemoryStore> memoryStore) {
        this.mindMapStore = mindMapStore != null && mindMapStore.isResolvable()
            ? mindMapStore.get() : null;
        this.memoryStore = memoryStore != null && memoryStore.isResolvable()
            ? memoryStore.get() : null;
    }

    DomainActivation(MindMapStore mindMapStore, CaseMemoryStore memoryStore) {
        this.mindMapStore = mindMapStore;
        this.memoryStore = memoryStore;
    }

    public Optional<DomainActivationResult> correlate(DomainActivationQuery query) {
        if (mindMapStore == null || memoryStore == null) { return Optional.empty(); }

        Map<String, DomainSignal> signals = new LinkedHashMap<>();
        Map<String, double[]> pleasureSeries = new LinkedHashMap<>();

        for (String sgId : query.subgraphIds()) {
            List<MindMapNode> entities = mindMapStore.search(
                MindMapQuery.of(query.tenantId(), 1000).withSubgraphId(sgId));
            if (entities.isEmpty()) { return Optional.empty(); }

            List<Memory> allMemories = new ArrayList<>();
            for (MindMapNode entity : entities) {
                var memQuery = MemoryQuery.forSubjects(
                    List.of(Subject.of("unknown", entity.id())),
                    AffectEvents.DOMAIN, query.tenantId())
                    .withCallerPrincipalId(query.principal())
                    .withLimit(1000)
                    .withOrder(MemoryOrder.CHRONOLOGICAL);
                allMemories.addAll(memoryStore.query(memQuery));
            }

            if (allMemories.isEmpty()) { return Optional.empty(); }

            // Filter by time window
            if (query.from() != null) {
                allMemories.removeIf(m -> m.createdAt() != null && m.createdAt().isBefore(query.from()));
            }
            if (query.to() != null) {
                allMemories.removeIf(m -> m.createdAt() != null && m.createdAt().isAfter(query.to()));
            }

            allMemories.sort(Comparator.comparing(m -> m.createdAt() != null ? m.createdAt() : Instant.EPOCH));

            AffectTrajectory trajectory = AffectTrajectoryAnalyzer.analyze(allMemories);

            // Time-bucketed pleasure values
            double[] buckets = timeBucket(allMemories, query.bucketDuration(),
                query.from(), query.to());

            signals.put(sgId, new DomainSignal(sgId, trajectory,
                entities.size(), allMemories.size(), buckets.length));
            pleasureSeries.put(sgId, buckets);
        }

        // Pairwise DTW
        List<String> sgIds = new ArrayList<>(query.subgraphIds());
        Map<DomainPair, DomainCorrelation> correlations = new LinkedHashMap<>();
        for (int i = 0; i < sgIds.size(); i++) {
            for (int j = i + 1; j < sgIds.size(); j++) {
                DomainPair pair = new DomainPair(sgIds.get(i), sgIds.get(j));
                double[] a = pleasureSeries.get(sgIds.get(i));
                double[] b = pleasureSeries.get(sgIds.get(j));

                if (a.length < 2 || b.length < 2) {
                    correlations.put(pair, new DomainCorrelation(
                        0.0, List.of(), Math.min(a.length, b.length),
                        CorrelationStrength.NONE));
                    continue;
                }

                PadDtw.DtwResult dtw = PadDtw.compute(a, b);
                correlations.put(pair, new DomainCorrelation(
                    dtw.similarity(), dtw.alignment().stream()
                        .map(p -> new io.casehub.neocortex.memory.cbr.AlignmentPair(p[0], p[1]))
                        .toList(),
                    Math.min(a.length, b.length),
                    CorrelationStrength.fromSimilarity(dtw.similarity())));
            }
        }

        return Optional.of(new DomainActivationResult(
            signals, correlations, query.principal(), query.tenantId(),
            query.from(), query.to()));
    }

    private double[] timeBucket(List<Memory> memories, Duration bucket,
            Instant from, Instant to) {
        if (memories.isEmpty()) { return new double[0]; }
        Instant start = from != null ? from : memories.getFirst().createdAt();
        Instant end = to != null ? to : memories.getLast().createdAt();
        long bucketMs = bucket.toMillis();
        int bucketCount = (int) ((end.toEpochMilli() - start.toEpochMilli()) / bucketMs) + 1;
        bucketCount = Math.max(1, Math.min(bucketCount, 10000));

        double[] sums = new double[bucketCount];
        int[] counts = new int[bucketCount];
        for (Memory m : memories) {
            if (m.createdAt() == null) continue;
            int idx = (int) ((m.createdAt().toEpochMilli() - start.toEpochMilli()) / bucketMs);
            idx = Math.max(0, Math.min(idx, bucketCount - 1));
            sums[idx] += m.pleasure() != null ? m.pleasure() : 0.0;
            counts[idx]++;
        }
        // Only return buckets with data
        List<Double> result = new ArrayList<>();
        for (int i = 0; i < bucketCount; i++) {
            if (counts[i] > 0) { result.add(sums[i] / counts[i]); }
        }
        return result.stream().mapToDouble(d -> d).toArray();
    }
}
```

Note: The `AlignmentPair` import from memory-api may need adaptation — check if cognitive-index already depends on memory-api. If not, use a local pair type instead.

- [ ] **Step 7: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: all tests pass

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): DomainActivation — cross-domain DTW correlation

CDI bean for cross-subgraph affect correlation. Time-bucketed PAD
aggregation per subgraph, pairwise DTW similarity with alignment.
Privacy by method signature — single PrincipalId required.
Includes PadDtw — lightweight 1D DTW for PAD time series.

Closes #283"
```

---

## References

- [2026-09-11-social-cognition-design.md] — design spec
- [decisions.md] — D1-D6 decisions
- [PerspectivalResolver.java] — overlay loading logic (internalized)
- [CognitiveProfile.java:160] — trajectory bug
- [AffectTrajectoryAnalyzer.java] — static utility pattern
- [PerspectivalMerge.java] — node merge utility
- [DtwSimilarity.java] — existing DTW precedent in memory-api
- [StubNode.java] — existing test stub for MindMapNode
- [CognitiveProfileTest.java] — existing test infrastructure
- [PerspectivalResolverTest.java] — existing test infrastructure
- GitHub #287 — epic
- GitHub #271 — multi-agent perspectival queries
- GitHub #283 — cross-domain reasoning
