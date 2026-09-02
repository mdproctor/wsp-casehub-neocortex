# Remove Memory-Space Modules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #255 — Remove memory-space modules
**Issue group:** #253, #255

**Goal:** Delete the 5 memory-space modules and decouple PerspectivalResolver
from the space model, replacing the SpaceMembershipStore lookup with
agentId-property-based overlay filtering within the same tenant.

**Architecture:** Overlay nodes carry an `agentId` property identifying
which agent they belong to. PerspectivalResolver searches for overlay
nodes by trait `"overlay"` within the caller's tenant, then filters by
agentId client-side. The 5 memory-space modules are deleted entirely —
they implement a wrong abstraction (space-as-tenant).

**Tech Stack:** Java 21, Quarkus CDI, Maven

## Global Constraints

- Use `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn` for all Maven commands
- Use `ide_*` tools for all structural code edits (never bash cp/mv/rm for source files)
- Commit with `Refs #255`

---

## Batch 1: Code refactor — OverlayRef + PerspectivalResolver

### Task 1: Add AGENT_ID constant to OverlayRef

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/OverlayRef.java`
- Modify: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/OverlayRefTest.java`

**Interfaces:**
- Produces: `OverlayRef.AGENT_ID` — `public static final String AGENT_ID = "agentId"` constant used by PerspectivalResolver (Task 2) to filter overlay nodes by agent

- [ ] **Step 1: Write the failing test**

Add a test to `OverlayRefTest` that verifies the constant exists and has the expected value:

```java
@Test
void agentIdConstantExists() {
    assertThat(OverlayRef.AGENT_ID).isEqualTo("agentId");
}
```

Use `ide_insert_member` to add after the `sharedNodeIdReturnsEmptyWhenNoOverlayRef` test.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=OverlayRefTest#agentIdConstantExists -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `AGENT_ID` does not exist.

- [ ] **Step 3: Add the constant**

Use `ide_insert_member` to add after the `SCHEME` field in `OverlayRef.java`:

```java
public static final String AGENT_ID = "agentId";
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=OverlayRefTest#agentIdConstantExists`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/OverlayRef.java mindmap-api/src/test/java/io/casehub/neocortex/mindmap/OverlayRefTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(mindmap-api): OverlayRef.AGENT_ID constant for overlay ownership

Refs #255

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: Refactor PerspectivalResolver — remove space dependency

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalResolver.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PerspectivalResolverTest.java`

**Interfaces:**
- Consumes: `OverlayRef.AGENT_ID` from Task 1
- Consumes: `OverlayRef.sharedNodeId(MindMapNode)` — existing
- Consumes: `MindMapQuery.of(tenantId, limit).withTraits(Set.of("overlay"))` — existing
- Produces: `PerspectivalResolver.resolve(List<MindMapNode> sharedNodes, String agentId, String tenantId) → List<MindMapNode>` — new signature. Returns shared nodes with per-agent overlay PAD/confidence/properties merged.
- Produces: constructor `PerspectivalResolver(Instance<MindMapStore>)` — CDI constructor, single dependency

- [ ] **Step 1: Rewrite PerspectivalResolver**

Use `ide_edit_member` to replace the class declaration and body. The full replacement:

```java
@ApplicationScoped
public class PerspectivalResolver {

    private final MindMapStore mindMapStore;

    @Inject
    public PerspectivalResolver(Instance<MindMapStore> mindMapStore) {
        this.mindMapStore = mindMapStore.isUnsatisfied() ? null : mindMapStore.get();
    }

    PerspectivalResolver(MindMapStore mindMapStore) {
        this.mindMapStore = mindMapStore;
    }

    public List<MindMapNode> resolve(List<MindMapNode> sharedNodes,
                                      String agentId, String tenantId) {
        if (sharedNodes.isEmpty()) return sharedNodes;
        if (mindMapStore == null) return sharedNodes;

        Map<String, MindMapNode> overlayMap = loadOverlays(tenantId, agentId);

        return sharedNodes.stream()
            .map(shared -> {
                MindMapNode overlay = overlayMap.get(shared.id());
                return overlay != null ? PerspectivalMerge.merge(shared, overlay) : shared;
            })
            .toList();
    }

    private Map<String, MindMapNode> loadOverlays(String tenantId, String agentId) {
        MindMapQuery query = MindMapQuery.of(tenantId, 1000)
            .withTraits(Set.of("overlay"));
        List<MindMapNode> overlayNodes = mindMapStore.search(query);

        Map<String, MindMapNode> map = new HashMap<>();
        for (MindMapNode node : overlayNodes) {
            if (agentId.equals(node.properties().get(OverlayRef.AGENT_ID))) {
                OverlayRef.sharedNodeId(node).ifPresent(sharedId -> map.put(sharedId, node));
            }
        }
        return map;
    }
}
```

Remove these imports from the file:
- `import io.casehub.neocortex.memory.space.MemorySpace;`
- `import io.casehub.neocortex.memory.space.SpaceMembershipStore;`
- `import io.casehub.neocortex.memory.space.SpaceType;`

Remove `import java.time.Instant;` (no longer needed — `asOf` parameter gone).

- [ ] **Step 2: Rewrite PerspectivalResolverTest**

Replace the full test class. Key changes:
- No more `spaceStore` / `InMemorySpaceMembershipStore` / space imports
- `PRIVATE_TENANT` constant removed — overlays go in `SHARED_TENANT`
- `addOverlay` helper adds `OverlayRef.AGENT_ID` property
- All `resolver.resolve(nodes, "alice", NOW)` calls become `resolver.resolve(nodes, "alice", SHARED_TENANT)`
- `gracefulDegradationNoSpaceMembershipStore` test deleted
- `gracefulDegradationNoMindMapStore` constructor call takes single null arg

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.MindMapVocabulary;
import io.casehub.neocortex.mindmap.NodeInput;
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
    private static final String TENANT = "smiths-family";
    private static final Confidence CONF =
        new Confidence(ConfidenceOrigin.STATED, 0.9, NOW);

    private MindMapStore mindMapStore;
    private PerspectivalResolver resolver;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        mindMapStore = new InMemoryMindMapStore();
        mindMapStore.registerVocabulary(MindMapVocabulary.builder()
            .edgeType("related-to").build());

        resolver = new PerspectivalResolver(mindMapStore);

        subgraphId = mindMapStore.createSubgraph(
            new SubgraphInput("Family", SubgraphType.GENERAL, null), TENANT);
    }

    @Test
    void findsOverlayAndMerges() {
        String sharedId = addSharedNode("Grandma");
        addOverlay(sharedId, "alice", 0.9, 0.3, 0.5);
        MindMapNode shared = mindMapStore.getNode(sharedId, TENANT);

        var result = resolver.resolve(List.of(shared), "alice", TENANT);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().name()).isEqualTo("Grandma");
        assertThat(result.getFirst().pleasure()).isEqualTo(0.9);
        assertThat(result.getFirst().arousal()).isEqualTo(0.3);
        assertThat(result.getFirst().dominance()).isEqualTo(0.5);
    }

    @Test
    void noOverlayReturnsSharedNodeAsIs() {
        String sharedId = addSharedNode("Uncle Bob");
        MindMapNode shared = mindMapStore.getNode(sharedId, TENANT);

        var result = resolver.resolve(List.of(shared), "alice", TENANT);

        assertThat(result).hasSize(1);
        assertThat(result.getFirst().name()).isEqualTo("Uncle Bob");
        assertThat(result.getFirst().pleasure()).isNull();
    }

    @Test
    void mixedSomeWithOverlaysSomeWithout() {
        String grandmaId = addSharedNode("Grandma");
        String uncleId = addSharedNode("Uncle Bob");
        addOverlay(grandmaId, "alice", 0.9, 0.3, 0.5);

        MindMapNode grandma = mindMapStore.getNode(grandmaId, TENANT);
        MindMapNode uncle = mindMapStore.getNode(uncleId, TENANT);

        var result = resolver.resolve(List.of(grandma, uncle), "alice", TENANT);

        assertThat(result).hasSize(2);
        MindMapNode resolvedGrandma = result.stream()
            .filter(n -> n.name().equals("Grandma")).findFirst().orElseThrow();
        MindMapNode resolvedUncle = result.stream()
            .filter(n -> n.name().equals("Uncle Bob")).findFirst().orElseThrow();
        assertThat(resolvedGrandma.pleasure()).isEqualTo(0.9);
        assertThat(resolvedUncle.pleasure()).isNull();
    }

    @Test
    void overlayFilteredByAgentId() {
        String sharedId = addSharedNode("Grandma");
        addOverlay(sharedId, "alice", 0.9, 0.3, 0.5);
        addOverlay(sharedId, "bob", 0.1, 0.8, 0.2);
        MindMapNode shared = mindMapStore.getNode(sharedId, TENANT);

        var aliceResult = resolver.resolve(List.of(shared), "alice", TENANT);
        var bobResult = resolver.resolve(List.of(shared), "bob", TENANT);

        assertThat(aliceResult.getFirst().pleasure()).isEqualTo(0.9);
        assertThat(bobResult.getFirst().pleasure()).isEqualTo(0.1);
    }

    @Test
    void gracefulDegradationNoMindMapStore() {
        PerspectivalResolver noStore = new PerspectivalResolver(
            (MindMapStore) null);
        MindMapNode shared = new StubNode("s1", "Test", "sg1",
            CONF, null, NOW, NOW, null, null,
            Set.of(), Set.of(), null, null, null, Map.of());

        var result = noStore.resolve(List.of(shared), "alice", TENANT);
        assertThat(result).hasSize(1);
        assertThat(result.getFirst().pleasure()).isNull();
    }

    @Test
    void multipleSharedNodesBatchedInOneQuery() {
        String id1 = addSharedNode("Grandma");
        String id2 = addSharedNode("Grandpa");
        addOverlay(id1, "alice", 0.9, 0.3, 0.5);
        addOverlay(id2, "alice", 0.7, 0.2, 0.4);

        MindMapNode n1 = mindMapStore.getNode(id1, TENANT);
        MindMapNode n2 = mindMapStore.getNode(id2, TENANT);

        var result = resolver.resolve(List.of(n1, n2), "alice", TENANT);

        assertThat(result).hasSize(2);
        assertThat(result).allSatisfy(n -> assertThat(n.pleasure()).isNotNull());
    }

    private String addSharedNode(String name) {
        return mindMapStore.addNode(new NodeInput(
            name, subgraphId, CONF, null,
            Set.of(), Set.of(), null, null,
            null, null, null, Map.of()), TENANT);
    }

    private void addOverlay(String sharedNodeId, String agentId,
                            double p, double a, double d) {
        mindMapStore.addNode(new NodeInput(
            "overlay-" + sharedNodeId + "-" + agentId, subgraphId, null, null,
            Set.of("overlay"), Set.of(OverlayRef.of(sharedNodeId)),
            null, null, p, a, d,
            Map.of(OverlayRef.AGENT_ID, agentId)), TENANT);
    }
}
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PerspectivalResolverTest`
Expected: 6 tests PASS (findsOverlayAndMerges, noOverlayReturnsSharedNodeAsIs, mixedSomeWithOverlaysSomeWithout, overlayFilteredByAgentId, gracefulDegradationNoMindMapStore, multipleSharedNodesBatchedInOneQuery)

- [ ] **Step 4: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PerspectivalResolver.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PerspectivalResolverTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor(cognitive-index): PerspectivalResolver uses agentId property, not SpaceMembershipStore

Overlay nodes carry agentId property within the same tenant.
Signature: resolve(sharedNodes, agentId, tenantId) replaces
resolve(sharedNodes, agentId, asOf). SpaceMembershipStore
dependency removed entirely.

Refs #255

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 2: Delete modules + clean build

### Task 3: Remove memory-space modules and dependencies

**Files:**
- Modify: `pom.xml` (parent) — remove 5 module declarations (lines 57-61) and 5 dependencyManagement entries (lines 322-346)
- Modify: `cognitive-index/pom.xml` — remove `casehub-neocortex-memory-space-api` compile dependency and `casehub-neocortex-memory-space-inmem` test dependency
- Delete: `memory-space-api/` directory (entire module)
- Delete: `memory-space/` directory (entire module)
- Delete: `memory-space-inmem/` directory (entire module)
- Delete: `memory-space-sqlite/` directory (entire module)
- Delete: `memory-space-testing/` directory (entire module)

**Interfaces:**
- Consumes: Task 2 must be complete — PerspectivalResolver no longer imports space types

- [ ] **Step 1: Remove memory-space dependencies from cognitive-index pom.xml**

Use the Edit tool to remove two dependency blocks from `cognitive-index/pom.xml`:

Remove the compile dependency (lines 28-30):
```xml
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-space-api</artifactId>
        </dependency>
```

Remove the test dependency (lines 61-65):
```xml
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-space-inmem</artifactId>
            <scope>test</scope>
        </dependency>
```

- [ ] **Step 2: Remove module declarations from parent pom.xml**

Use the Edit tool to remove 5 lines from the `<modules>` section (lines 57-61):
```xml
    <module>memory-space-api</module>
    <module>memory-space</module>
    <module>memory-space-testing</module>
    <module>memory-space-inmem</module>
    <module>memory-space-sqlite</module>
```

Remove 5 dependency blocks from `<dependencyManagement>` (lines 322-346):
```xml
      <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-memory-space-api</artifactId>
        <version>${project.version}</version>
      </dependency>
      <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-memory-space</artifactId>
        <version>${project.version}</version>
      </dependency>
      <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-memory-space-testing</artifactId>
        <version>${project.version}</version>
      </dependency>
      <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-memory-space-inmem</artifactId>
        <version>${project.version}</version>
      </dependency>
      <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-memory-space-sqlite</artifactId>
        <version>${project.version}</version>
      </dependency>
```

- [ ] **Step 3: Delete the 5 module directories**

Use bash `rm -rf` for directory deletion (these are entire modules being deleted, not refactoring):

```bash
rm -rf /Users/mdproctor/claude/casehub/neocortex/memory-space-api
rm -rf /Users/mdproctor/claude/casehub/neocortex/memory-space
rm -rf /Users/mdproctor/claude/casehub/neocortex/memory-space-inmem
rm -rf /Users/mdproctor/claude/casehub/neocortex/memory-space-sqlite
rm -rf /Users/mdproctor/claude/casehub/neocortex/memory-space-testing
```

- [ ] **Step 4: Reload project in IntelliJ**

Run `ide_reload_project` so IntelliJ picks up the pom.xml changes.

- [ ] **Step 5: Build to verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS — no compilation errors from removed modules.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: All cognitive-index tests pass.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add -A
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "refactor: delete memory-space modules — space-as-tenant was wrong abstraction

Remove memory-space-api, memory-space, memory-space-inmem,
memory-space-sqlite, memory-space-testing. Tenant is the hard
boundary; individual vs common memory is a property of the
memory itself, not a partitioning system.

Closes #255
Refs #253

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 3: Documentation updates

### Task 4: Update CLAUDE.md and cognitive-architecture-roadmap.md

**Files:**
- Modify: `CLAUDE.md` — remove all memory-space module references (~11 occurrences: module structure, Maven coordinates, root Java packages)
- Modify: `docs/guides/cognitive-architecture-roadmap.md` — update MemorySpace/Visibility references (lines 123, 125, 136, 527, 586)

- [ ] **Step 1: Update CLAUDE.md**

Remove from the module structure section:
```
memory-space-api/   — ...
memory-space/       — ...
memory-space-testing/ — ...
memory-space-inmem/ — ...
memory-space-sqlite/ — ...
```

Remove from the Maven Coordinates table:
```
| Memory Space API | `casehub-neocortex-memory-space-api` |
| Memory Space CDI | `casehub-neocortex-memory-space` |
| Memory Space testing | `casehub-neocortex-memory-space-testing` |
| Memory Space In-Memory | `casehub-neocortex-memory-space-inmem` |
| Memory Space SQLite | `casehub-neocortex-memory-space-sqlite` |
```

Remove from the Root Java packages:
```
| Root Java package (memory-space) | `io.casehub.neocortex.memory.space` |
```

Update the cognitive-index module description to remove the `SpaceMembershipStore` reference from `PerspectivalResolver` description. Change:
```
PerspectivalResolver (@ApplicationScoped — resolves perspectival overlays: finds agent's private overlay nodes via trait-based search, merges with shared nodes; Instance<MindMapStore> + Instance<SpaceMembershipStore> graceful degradation)
```
to:
```
PerspectivalResolver (@ApplicationScoped — resolves perspectival overlays: finds agent's overlay nodes via trait-based search + agentId property filter, merges with shared nodes; Instance<MindMapStore> graceful degradation)
```

- [ ] **Step 2: Update cognitive-architecture-roadmap.md**

At line 123, replace the `MemorySpace` and `Visibility` type descriptions with a note that these were removed. At line 136, update the scope description. At line 527, remove or mark the `memory-spaces:` YAML example as removed. At line 586, update the roadmap table entry for "1f: Memory Space Model" to indicate completed/removed.

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md docs/guides/cognitive-architecture-roadmap.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "docs: remove memory-space references from CLAUDE.md and roadmap

Refs #255

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## References

- [2026-09-01-remove-memory-space-modules-design.md] — design spec this plan implements
- [PerspectivalResolver.java:21-78] — sole external consumer, refactored in Task 2
- [PerspectivalResolverTest.java:27-163] — test file rewritten in Task 2
- [OverlayRef.java:5-21] — convention class, extended in Task 1
- [cognitive-index/pom.xml:28-65] — dependency removal in Task 3
- [pom.xml:57-61, 322-346] — module and dependency management removal in Task 3
- [D62-D64] — decisions from brainstorming
- [GitHub #255] — focal issue
- [GitHub #253] — parent epic
