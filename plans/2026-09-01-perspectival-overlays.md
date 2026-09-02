# Perspectival Affect Overlays Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #240 — feat: perspectival affect overlays — per-agent PAD on shared MindMap nodes
**Issue group:** #253, #240

**Goal:** Per-agent PAD overlays on shared MindMap nodes — same node carries different emotional meaning for each viewer, resolved at query time via convention + merge + resolver.

**Architecture:** OverlayRef convention in mindmap-api (NodeRef scheme + trait). PerspectivalMerge pure utility and PerspectivalResolver CDI bean in cognitive-index. Resolver uses trait-based search to find overlay nodes in the agent's private tenant, merges with shared nodes. No store changes.

**Tech Stack:** Java 21, CDI (jakarta.enterprise), Instance<T> graceful degradation

## Global Constraints

- Java 21 source level (on Java 26 JVM): `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn`
- No changes to MindMapStore SPI or implementations
- cognitive-index needs new dependency on `memory-space-api` (for SpaceMembershipStore)
- Overlay nodes use trait `"overlay"` and `NodeRef(scheme="overlay", id=sharedNodeId)`
- Use `mvn` not `./mvnw`

---

## Batch 1: Convention + merge utility

### Task 1: OverlayRef convention in mindmap-api + PerspectivalMerge in cognitive-index

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/OverlayRef.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalMerge.java`
- Test: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/OverlayRefTest.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PerspectivalMergeTest.java`

**Interfaces:**
- Consumes: `NodeRef(scheme, id, qualifier)` from mindmap-api, `MindMapNode` interface from mindmap-api, `Confidence` from cognitive-api
- Produces: `OverlayRef.SCHEME`, `OverlayRef.of(String)`, `OverlayRef.sharedNodeId(MindMapNode)`, `PerspectivalMerge.merge(MindMapNode, MindMapNode)`

- [ ] **Step 1: Write OverlayRef tests**

Create `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/OverlayRefTest.java`:

```java
package io.casehub.neocortex.mindmap;

import org.junit.jupiter.api.Test;

import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class OverlayRefTest {

    @Test
    void ofCreatesCorrectNodeRef() {
        NodeRef ref = OverlayRef.of("shared-123");
        assertThat(ref.scheme()).isEqualTo("overlay");
        assertThat(ref.id()).isEqualTo("shared-123");
        assertThat(ref.qualifier()).isNull();
    }

    @Test
    void sharedNodeIdExtractsFromOverlayNode() {
        NodeRef overlayRef = OverlayRef.of("shared-456");
        NodeRef otherRef = new NodeRef("memory", "mem-1", null);
        // Use a stub that implements MindMapNode with the given refs
        MindMapNode node = stubWithRefs(Set.of(overlayRef, otherRef));
        Optional<String> id = OverlayRef.sharedNodeId(node);
        assertThat(id).contains("shared-456");
    }

    @Test
    void sharedNodeIdReturnsEmptyWhenNoOverlayRef() {
        NodeRef otherRef = new NodeRef("memory", "mem-1", null);
        MindMapNode node = stubWithRefs(Set.of(otherRef));
        assertThat(OverlayRef.sharedNodeId(node)).isEmpty();
    }

    private MindMapNode stubWithRefs(Set<NodeRef> refs) {
        return new MindMapNode() {
            public String id() { return "n1"; }
            public String name() { return "test"; }
            public String subgraphId() { return "sg1"; }
            public io.casehub.neocortex.cognitive.Confidence confidence() { return null; }
            public String provenance() { return null; }
            public java.time.Instant createdAt() { return java.time.Instant.now(); }
            public java.time.Instant updatedAt() { return java.time.Instant.now(); }
            public java.time.Instant validFrom() { return null; }
            public java.time.Instant validUntil() { return null; }
            public Set<String> traits() { return Set.of(); }
            public Set<NodeRef> refs() { return refs; }
            public Double pleasure() { return null; }
            public Double arousal() { return null; }
            public Double dominance() { return null; }
            public java.util.Optional<String> property(String key) { return java.util.Optional.empty(); }
            public java.util.Map<String, String> properties() { return java.util.Map.of(); }
        };
    }
}
```

- [ ] **Step 2: Write PerspectivalMerge tests**

Create `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PerspectivalMergeTest.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.NodeRef;
import io.casehub.neocortex.mindmap.OverlayRef;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class PerspectivalMergeTest {

    private static final Instant NOW = Instant.parse("2026-06-01T12:00:00Z");
    private static final Confidence SHARED_CONF =
        new Confidence(ConfidenceOrigin.STATED, 0.9, NOW);
    private static final Confidence OVERLAY_CONF =
        new Confidence(ConfidenceOrigin.INFERRED, 0.7, NOW);

    @Test
    void overlayPadReplacesSharedNullPad() {
        MindMapNode shared = sharedNode(null, null, null, SHARED_CONF, Map.of());
        MindMapNode overlay = overlayNode(0.8, 0.3, -0.2, null, Map.of());

        MindMapNode merged = PerspectivalMerge.merge(shared, overlay);

        assertThat(merged.pleasure()).isEqualTo(0.8);
        assertThat(merged.arousal()).isEqualTo(0.3);
        assertThat(merged.dominance()).isEqualTo(-0.2);
    }

    @Test
    void overlayConfidenceReplacesSharedConfidence() {
        MindMapNode shared = sharedNode(null, null, null, SHARED_CONF, Map.of());
        MindMapNode overlay = overlayNode(null, null, null, OVERLAY_CONF, Map.of());

        MindMapNode merged = PerspectivalMerge.merge(shared, overlay);

        assertThat(merged.confidence().value()).isEqualTo(0.7);
        assertThat(merged.confidence().origin()).isEqualTo(ConfidenceOrigin.INFERRED);
    }

    @Test
    void overlayPropertiesMergeOverlayWins() {
        MindMapNode shared = sharedNode(null, null, null, SHARED_CONF,
            Map.of("birthday", "1945-03-12", "surname", "Smith"));
        MindMapNode overlay = overlayNode(null, null, null, null,
            Map.of("notes", "love her", "surname", "Smithy"));

        MindMapNode merged = PerspectivalMerge.merge(shared, overlay);

        assertThat(merged.properties()).containsEntry("birthday", "1945-03-12");
        assertThat(merged.properties()).containsEntry("notes", "love her");
        assertThat(merged.properties()).containsEntry("surname", "Smithy");
    }

    @Test
    void nullOverlayPadKeepsSharedPad() {
        MindMapNode shared = sharedNode(0.5, 0.3, 0.1, SHARED_CONF, Map.of());
        MindMapNode overlay = overlayNode(null, null, null, null, Map.of());

        MindMapNode merged = PerspectivalMerge.merge(shared, overlay);

        assertThat(merged.pleasure()).isEqualTo(0.5);
        assertThat(merged.arousal()).isEqualTo(0.3);
        assertThat(merged.dominance()).isEqualTo(0.1);
    }

    @Test
    void sharedNameTraitsSubgraphPreserved() {
        MindMapNode shared = new StubNode(
            "shared-1", "Grandma", "sg-family",
            SHARED_CONF, null, NOW, NOW, null, null,
            Set.of("Personable"), Set.of(), null, null, null,
            Map.of("birthday", "1945-03-12"));
        MindMapNode overlay = overlayNode(0.9, 0.3, 0.5, null, Map.of("notes", "love her"));

        MindMapNode merged = PerspectivalMerge.merge(shared, overlay);

        assertThat(merged.id()).isEqualTo("shared-1");
        assertThat(merged.name()).isEqualTo("Grandma");
        assertThat(merged.subgraphId()).isEqualTo("sg-family");
        assertThat(merged.traits()).containsExactly("Personable");
        assertThat(merged.createdAt()).isEqualTo(NOW);
    }

    private MindMapNode sharedNode(Double p, Double a, Double d,
            Confidence conf, Map<String, String> props) {
        return new StubNode("shared-1", "Grandma", "sg-family",
            conf, null, NOW, NOW, null, null,
            Set.of("Personable"), Set.of(), p, a, d, props);
    }

    private MindMapNode overlayNode(Double p, Double a, Double d,
            Confidence conf, Map<String, String> props) {
        return new StubNode("overlay-1", "Grandma", "sg-overlays",
            conf, null, NOW, NOW, null, null,
            Set.of("overlay"), Set.of(OverlayRef.of("shared-1")),
            p, a, d, props);
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,cognitive-index -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: compilation failure — OverlayRef and PerspectivalMerge not yet created.

- [ ] **Step 4: Implement OverlayRef**

Create `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/OverlayRef.java`:

```java
package io.casehub.neocortex.mindmap;

import java.util.Optional;

public final class OverlayRef {

    public static final String SCHEME = "overlay";

    private OverlayRef() {}

    public static NodeRef of(String sharedNodeId) {
        return new NodeRef(SCHEME, sharedNodeId, null);
    }

    public static Optional<String> sharedNodeId(MindMapNode node) {
        return node.refs().stream()
            .filter(r -> SCHEME.equals(r.scheme()))
            .map(NodeRef::id)
            .findFirst();
    }
}
```

- [ ] **Step 5: Implement PerspectivalMerge**

Create `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalMerge.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.NodeRef;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

public final class PerspectivalMerge {

    private PerspectivalMerge() {}

    public static MindMapNode merge(MindMapNode shared, MindMapNode overlay) {
        Double pleasure = overlay.pleasure() != null ? overlay.pleasure() : shared.pleasure();
        Double arousal = overlay.arousal() != null ? overlay.arousal() : shared.arousal();
        Double dominance = overlay.dominance() != null ? overlay.dominance() : shared.dominance();
        Confidence confidence = overlay.confidence() != null ? overlay.confidence() : shared.confidence();

        Map<String, String> mergedProps = new HashMap<>(shared.properties());
        mergedProps.putAll(overlay.properties());

        return new MergedNode(
            shared.id(), shared.name(), shared.subgraphId(),
            confidence, shared.provenance(),
            shared.createdAt(), shared.updatedAt(),
            shared.validFrom(), shared.validUntil(),
            shared.traits(), shared.refs(),
            pleasure, arousal, dominance,
            Map.copyOf(mergedProps)
        );
    }

    private record MergedNode(
        String id, String name, String subgraphId,
        Confidence confidence, String provenance,
        Instant createdAt, Instant updatedAt,
        Instant validFrom, Instant validUntil,
        Set<String> traits, Set<NodeRef> refs,
        Double pleasure, Double arousal, Double dominance,
        Map<String, String> props
    ) implements MindMapNode {
        @Override
        public Optional<String> property(String key) {
            return Optional.ofNullable(props.get(key));
        }
        @Override
        public Map<String, String> properties() {
            return props;
        }
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl mindmap-api,cognitive-api,cognitive-index -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: 3 OverlayRef tests + 5 PerspectivalMerge tests PASS (plus existing tests).

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-api/ cognitive-index/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat: OverlayRef convention + PerspectivalMerge utility Refs #240"
```

---

## Batch 2: PerspectivalResolver + CLAUDE.md update

### Task 2: PerspectivalResolver CDI bean + resolver tests

**Files:**
- Modify: `cognitive-index/pom.xml` — add memory-space-api dependency
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalResolver.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PerspectivalResolverTest.java`
- Modify: `CLAUDE.md` — update mindmap-api, cognitive-index descriptions

**Interfaces:**
- Consumes: `OverlayRef` from Task 1, `PerspectivalMerge.merge()` from Task 1
- Consumes: `MindMapStore.search(MindMapQuery)` from mindmap-api
- Consumes: `SpaceMembershipStore.spacesFor()` from memory-space-api
- Produces: `PerspectivalResolver.resolve(List<MindMapNode>, String agentId, Instant asOf)`

- [ ] **Step 1: Add memory-space-api dependency to cognitive-index**

Add to `cognitive-index/pom.xml` dependencies (after memory-api):

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-space-api</artifactId>
</dependency>
```

- [ ] **Step 2: Write resolver tests**

Create `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PerspectivalResolverTest.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.memory.space.MemorySpace;
import io.casehub.neocortex.memory.space.SpaceMembership;
import io.casehub.neocortex.memory.space.SpaceMembershipStore;
import io.casehub.neocortex.memory.space.inmem.InMemorySpaceMembershipStore;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.MindMapVocabulary;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.NodeRef;
import io.casehub.neocortex.mindmap.OverlayRef;
import io.casehub.neocortex.mindmap.SubgraphInput;
import io.casehub.neocortex.mindmap.SubgraphType;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class PerspectivalResolverTest {

    private static final Instant NOW = Instant.parse("2026-06-01T12:00:00Z");
    private static final String SHARED_TENANT = "smiths-family";
    private static final String PRIVATE_TENANT = "alice-priv";
    private static final Confidence CONF =
        new Confidence(ConfidenceOrigin.STATED, 0.9, NOW);

    private MindMapStore mindMapStore;
    private SpaceMembershipStore spaceStore;
    private PerspectivalResolver resolver;
    private String sharedSubgraphId;
    private String privateSubgraphId;

    @BeforeEach
    void setUp() {
        mindMapStore = new InMemoryMindMapStore();
        mindMapStore.registerVocabulary(MindMapVocabulary.builder()
            .edgeType("related-to").build());

        spaceStore = new InMemorySpaceMembershipStore();
        spaceStore.createSpace(MemorySpace.sharedSpace(SHARED_TENANT, "Smiths Family"));
        spaceStore.createSpace(MemorySpace.privateSpace(PRIVATE_TENANT, "Alice Private", "alice"));
        spaceStore.addMember(new SpaceMembership("alice", SHARED_TENANT, Set.of(), NOW, null));
        spaceStore.addMember(new SpaceMembership("alice", PRIVATE_TENANT, Set.of(), NOW, null));

        resolver = new PerspectivalResolver(mindMapStore, spaceStore);

        sharedSubgraphId = mindMapStore.createSubgraph(
            new SubgraphInput("Family", SubgraphType.GENERAL, null), SHARED_TENANT);
        privateSubgraphId = mindMapStore.createSubgraph(
            new SubgraphInput("Overlays", SubgraphType.GENERAL, null), PRIVATE_TENANT);
    }

    @Test
    void findsOverlayAndMerges() {
        String sharedId = addSharedNode("Grandma");
        addOverlay(sharedId, 0.9, 0.3, 0.5);
        MindMapNode shared = mindMapStore.getNode(sharedId, SHARED_TENANT);

        var result = resolver.resolve(List.of(shared), "alice", NOW);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().name()).isEqualTo("Grandma");
        assertThat(result.getFirst().pleasure()).isEqualTo(0.9);
        assertThat(result.getFirst().arousal()).isEqualTo(0.3);
        assertThat(result.getFirst().dominance()).isEqualTo(0.5);
    }

    @Test
    void noOverlayReturnsSharedNodeAsIs() {
        String sharedId = addSharedNode("Uncle Bob");
        MindMapNode shared = mindMapStore.getNode(sharedId, SHARED_TENANT);

        var result = resolver.resolve(List.of(shared), "alice", NOW);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().name()).isEqualTo("Uncle Bob");
        assertThat(result.getFirst().pleasure()).isNull();
    }

    @Test
    void mixedSomeWithOverlaysSomeWithout() {
        String grandmaId = addSharedNode("Grandma");
        String uncleId = addSharedNode("Uncle Bob");
        addOverlay(grandmaId, 0.9, 0.3, 0.5);

        MindMapNode grandma = mindMapStore.getNode(grandmaId, SHARED_TENANT);
        MindMapNode uncle = mindMapStore.getNode(uncleId, SHARED_TENANT);

        var result = resolver.resolve(List.of(grandma, uncle), "alice", NOW);

        assertThat(result).hasSize(2);
        MindMapNode resolvedGrandma = result.stream()
            .filter(n -> n.name().equals("Grandma")).findFirst().orElseThrow();
        MindMapNode resolvedUncle = result.stream()
            .filter(n -> n.name().equals("Uncle Bob")).findFirst().orElseThrow();
        assertThat(resolvedGrandma.pleasure()).isEqualTo(0.9);
        assertThat(resolvedUncle.pleasure()).isNull();
    }

    @Test
    void gracefulDegradationNoMindMapStore() {
        PerspectivalResolver noStore = new PerspectivalResolver(null, spaceStore);
        MindMapNode shared = new StubNode("s1", "Test", "sg1",
            CONF, null, NOW, NOW, null, null,
            Set.of(), Set.of(), null, null, null, Map.of());

        var result = noStore.resolve(List.of(shared), "alice", NOW);
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().pleasure()).isNull();
    }

    @Test
    void gracefulDegradationNoSpaceMembershipStore() {
        PerspectivalResolver noStore = new PerspectivalResolver(mindMapStore, null);
        MindMapNode shared = new StubNode("s1", "Test", "sg1",
            CONF, null, NOW, NOW, null, null,
            Set.of(), Set.of(), null, null, null, Map.of());

        var result = noStore.resolve(List.of(shared), "alice", NOW);
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().pleasure()).isNull();
    }

    @Test
    void multipleSharedNodesBatchedInOneQuery() {
        String id1 = addSharedNode("Grandma");
        String id2 = addSharedNode("Grandpa");
        addOverlay(id1, 0.9, 0.3, 0.5);
        addOverlay(id2, 0.7, 0.2, 0.4);

        MindMapNode n1 = mindMapStore.getNode(id1, SHARED_TENANT);
        MindMapNode n2 = mindMapStore.getNode(id2, SHARED_TENANT);

        var result = resolver.resolve(List.of(n1, n2), "alice", NOW);

        assertThat(result).hasSize(2);
        assertThat(result).allSatisfy(n -> assertThat(n.pleasure()).isNotNull());
    }

    private String addSharedNode(String name) {
        return mindMapStore.addNode(new NodeInput(
            name, sharedSubgraphId, CONF, null,
            Set.of(), Set.of(), null, null,
            null, null, null, Map.of()), SHARED_TENANT);
    }

    private void addOverlay(String sharedNodeId, double p, double a, double d) {
        mindMapStore.addNode(new NodeInput(
            "overlay-" + sharedNodeId, privateSubgraphId, null, null,
            Set.of("overlay"), Set.of(OverlayRef.of(sharedNodeId)),
            null, null, p, a, d, Map.of()), PRIVATE_TENANT);
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: compilation failure — PerspectivalResolver not yet created.

- [ ] **Step 4: Implement PerspectivalResolver**

Create `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalResolver.java`:

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.space.MemorySpace;
import io.casehub.neocortex.memory.space.SpaceMembershipStore;
import io.casehub.neocortex.memory.space.SpaceType;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapQuery;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.OverlayRef;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.time.Instant;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

@ApplicationScoped
public class PerspectivalResolver {

    private final MindMapStore mindMapStore;
    private final SpaceMembershipStore spaceMembershipStore;

    @Inject
    public PerspectivalResolver(Instance<MindMapStore> mindMapStore,
                                 Instance<SpaceMembershipStore> spaceMembershipStore) {
        this.mindMapStore = mindMapStore.isUnsatisfied() ? null : mindMapStore.get();
        this.spaceMembershipStore = spaceMembershipStore.isUnsatisfied()
            ? null : spaceMembershipStore.get();
    }

    PerspectivalResolver(MindMapStore mindMapStore, SpaceMembershipStore spaceMembershipStore) {
        this.mindMapStore = mindMapStore;
        this.spaceMembershipStore = spaceMembershipStore;
    }

    public List<MindMapNode> resolve(List<MindMapNode> sharedNodes,
                                      String agentId, Instant asOf) {
        if (sharedNodes.isEmpty()) return sharedNodes;
        if (mindMapStore == null || spaceMembershipStore == null) return sharedNodes;

        String privateTenantId = findPrivateTenant(agentId, asOf);
        if (privateTenantId == null) return sharedNodes;

        Map<String, MindMapNode> overlayMap = loadOverlays(privateTenantId);

        return sharedNodes.stream()
            .map(shared -> {
                MindMapNode overlay = overlayMap.get(shared.id());
                return overlay != null ? PerspectivalMerge.merge(shared, overlay) : shared;
            })
            .toList();
    }

    private String findPrivateTenant(String agentId, Instant asOf) {
        return spaceMembershipStore.spacesFor(agentId, asOf).stream()
            .filter(s -> s.type() == SpaceType.PRIVATE)
            .map(MemorySpace::id)
            .findFirst()
            .orElse(null);
    }

    private Map<String, MindMapNode> loadOverlays(String privateTenantId) {
        MindMapQuery query = new MindMapQuery(
            privateTenantId, null, null, null,
            Set.of("overlay"), null, null, false,
            null, null, null, 1000);
        List<MindMapNode> overlayNodes = mindMapStore.search(query);

        Map<String, MindMapNode> map = new HashMap<>();
        for (MindMapNode node : overlayNodes) {
            OverlayRef.sharedNodeId(node).ifPresent(sharedId -> map.put(sharedId, node));
        }
        return map;
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl mindmap-api,cognitive-api,memory-space-api,memory-space-inmem,mindmap-inmem,cognitive-index -f /Users/mdproctor/claude/casehub/neocortex/pom.xml`
Expected: 6 resolver tests PASS (plus all existing tests).

- [ ] **Step 6: Update CLAUDE.md**

Add to mindmap-api description: `OverlayRef (convention for perspectival affect overlays — NodeRef scheme="overlay", trait "overlay"; of(sharedNodeId) factory, sharedNodeId(MindMapNode) extractor)`.

Add to cognitive-index description: `PerspectivalMerge (pure static utility: merge shared MindMapNode + private overlay → single perspectival node; overlay PAD/confidence/properties win when non-null), PerspectivalResolver (@ApplicationScoped — resolves perspectival overlays: finds agent's private overlay nodes via trait-based search, merges with shared nodes; Instance<MindMapStore> + Instance<SpaceMembershipStore> graceful degradation)`.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/ CLAUDE.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(cognitive-index): PerspectivalResolver + overlay merge Refs #240"
```

---

## References

- `specs/issue-253-cognitive-rearchitecture/2026-09-01-perspectival-overlays-design.md` — design spec
- `mindmap-api/.../NodeRef.java` — cross-store reference record
- `mindmap-api/.../MindMapNode.java` — node interface with PAD
- `mindmap-api/.../MindMapQuery.java` — query with trait filtering
- `mindmap-api/.../NodeInput.java` — node creation input
- `cognitive-index/.../CognitiveProfile.java` — Instance<T> graceful degradation pattern
- `cognitive-index/.../StubNode.java` — test stub
- `memory-space-api/.../SpaceMembershipStore.java` — space membership resolution
- `memory-space-inmem/.../InMemorySpaceMembershipStore.java` — test implementation
- `docs/guides/shared-memory-design.md` — authoritative overlay model
- GitHub #240 — focal issue
- GitHub #253 — parent branch issue
