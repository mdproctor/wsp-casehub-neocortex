# Cognitive Workbench — Batch 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #468 — feat: cognitive workbench — barebones showcase in blocks-ui
**Issue group:** #468

**Goal:** Build the foundation of the cognitive workbench — a working demo where you can load the Frida Kahlo dataset, explore the cognitive graph, click entities for details, and converse with the avatar via voice/text, with live cognitive ticks updating the graph in real-time.

**Architecture:** Cross-repo (neocortex + blocks-ui). Neocortex provides one small fix (wire `attention()` endpoint). blocks-ui provides: a dedicated Quarkus backend (`examples/cognitive-workbench-backend`) with DatasetSession lifecycle, WebSocket endpoints, and dataset management; a rendering layer (`packages/graph-stencil-cognitive`); two consumer components (`<cognitive-graph>`, `<entity-detail>`); a dock-workbench shell (`<cognitive-workbench>`); avatar integration; and the Frida Kahlo demo dataset.

**Tech Stack:** Java 21 / Quarkus 3.32 (backend), TypeScript / Lit 3.x / React Flow 12 (frontend), SQLite (stores), WebSocket (voice + cognitive state push), Kokoro TTS, pages-event (component communication)

## Global Constraints

- Neocortex modules: `groupId=io.casehub`, version `0.2-SNAPSHOT`
- blocks-ui packages: `@casehubio/*`, version `0.1.0` or `0.2.2`
- blocks deps: `casehub-blocks-speech-ws`, `casehub-blocks-speech-sherpa`, `casehub-platform-agent-api` at `${casehub-blocks.version}` = `0.2-SNAPSHOT`
- Quarkus: `3.32.2`
- Node stencil shapes/colors per mockups — see spec Section 2
- All MCP domain endpoints use `@McpDomain` annotation pattern
- Event topics use `pages-event` system (`onPagesEvent`/`dispatchPagesEvent`)
- All stores are SQLite with HikariCP WAL mode
- Java package root for backend: `io.casehub.blocks.cognitive.workbench`
- npm scope: `@casehubio/`

---

## Batch 1: Neocortex — Wire Attention Endpoint

### Task 1: Wire CognitionApi.attention() to CognitiveAttentionMediator

The `attention()` method in `CognitionService` currently returns `null`. It needs to delegate to `CognitiveAttentionMediator` to support the insight-feed component.

**Files:**
- Modify: `cognitive-observability-core/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionService.java`
- Test: `cognitive-observability-core/src/test/java/io/casehub/neocortex/cognitive/observability/CognitionServiceTest.java` (create if not exists)

**Interfaces:**
- Consumes: `CognitiveAttentionMediator` (from `mindmap-intelligence` — `getLatestBriefing(principalId, tenantId, topN)` or similar), `AttentionBriefing` (from `mindmap-api`)
- Produces: `CognitionApi.attention(tenantId, principalId, topN)` returns `AttentionBriefing`

- [ ] **Step 1: Find CognitiveAttentionMediator API**

Use `ide_find_class` to locate `CognitiveAttentionMediator` and `ide_find_class` for `CognitiveAttentionAccumulator`. Read the accumulator's public methods to understand how to retrieve the current briefing.

- [ ] **Step 2: Write the failing test**

```java
@QuarkusTest
class CognitionServiceAttentionTest {

    @Inject
    CognitionService service;

    @Inject
    CognitiveAttentionAccumulator accumulator;

    @Test
    void attention_returns_briefing_when_signals_accumulated() {
        // Feed a signal into the accumulator
        var signal = new AttentionSignal(
            PrincipalId.of("agent-1"), TenantId.of("tenant-1"),
            SignalCategory.GOAL_RECOGNIZED, "node-1", "Test Goal",
            0.8, "Goal recognized from experience"
        );
        accumulator.onSignal(signal);

        var result = service.attention("tenant-1", "agent-1", 5);

        assertNotNull(result);
        assertFalse(result.signals().isEmpty());
        assertEquals("agent-1", result.principalId().value());
    }

    @Test
    void attention_returns_empty_briefing_when_no_signals() {
        var result = service.attention("tenant-1", "unknown-agent", 5);

        assertNotNull(result);
        assertTrue(result.signals().isEmpty());
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability-core -Dtest=CognitionServiceAttentionTest -DfailIfNoTests=false`
Expected: FAIL — attention() returns null

- [ ] **Step 4: Wire attention() in CognitionService**

Use `ide_find_class` for `CognitionService`, then `ide_replace_member` to update the `attention()` method. Inject `Instance<CognitiveAttentionAccumulator>` (graceful degradation when not on classpath) and delegate:

```java
@Override
public AttentionBriefing attention(String tenantId, String principalId, Integer topN) {
    if (attentionAccumulator.isUnsatisfied()) {
        return new AttentionBriefing(PrincipalId.of(principalId), TenantId.of(tenantId),
            List.of(), 0.0, Instant.now());
    }
    var accumulator = attentionAccumulator.get();
    var briefing = accumulator.getBriefing(PrincipalId.of(principalId), TenantId.of(tenantId),
        topN != null ? topN : 10);
    return briefing != null ? briefing : new AttentionBriefing(
        PrincipalId.of(principalId), TenantId.of(tenantId),
        List.of(), 0.0, Instant.now());
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-observability-core -Dtest=CognitionServiceAttentionTest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognitive-observability-core/src/main/java/io/casehub/neocortex/cognitive/observability/CognitionService.java
git add cognitive-observability-core/src/test/java/io/casehub/neocortex/cognitive/observability/CognitionServiceAttentionTest.java
git commit -m "feat(#468): wire CognitionApi.attention() to CognitiveAttentionAccumulator

Refs #468"
```

---

## Batch 2: Backend — Workbench Quarkus Module

### Task 2: Scaffold workbench backend with DatasetSession lifecycle

Create the Quarkus backend module in blocks-ui. Establish DatasetSession — the session reconstruction architecture that encapsulates the full cognitive stack for a loaded dataset.

**Files:**
- Create: `examples/cognitive-workbench-backend/pom.xml`
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/DatasetSession.java`
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/DatasetSessionFactory.java`
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/WorkbenchState.java`
- Create: `examples/cognitive-workbench-backend/src/main/resources/application.properties`
- Test: `examples/cognitive-workbench-backend/src/test/java/io/casehub/blocks/cognitive/workbench/DatasetSessionFactoryTest.java`

**Interfaces:**
- Consumes: `SqliteMindMapStore`, `SqliteMemoryStore`, `SqliteCapsEngine`, `SqliteSnapshotStore`, `CognitionService`, `CognitionCore`, `CognitiveDefaultsRegistry` (all from neocortex)
- Produces: `DatasetSession` (record encapsulating stores + cognitive stack), `DatasetSessionFactory.create(Path datasetDir)` → `DatasetSession`, `WorkbenchState` (@ApplicationScoped — holds `AtomicReference<DatasetSession>`)

- [ ] **Step 1: Create pom.xml**

Model after `examples/avatar-demo/pom.xml`. Standalone (no parent reactor). Key dependencies:
- `io.casehub:casehub-neocortex-mindmap-sqlite`
- `io.casehub:casehub-neocortex-memory-sqlite`
- `io.casehub:casehub-neocortex-caps-engine`
- `io.casehub:casehub-neocortex-cognitive-observability-sqlite`
- `io.casehub:casehub-neocortex-cognition`
- `io.casehub:casehub-neocortex-memory-seeding`
- `io.casehub:casehub-neocortex-cognitive-index`
- `io.casehub:casehub-blocks-speech-ws`
- `io.casehub:casehub-blocks-speech-sherpa`
- `io.casehub:casehub-platform-agent-api`
- `io.quarkus:quarkus-websockets-next`
- `io.quarkus:quarkus-rest`
- `io.quarkus:quarkus-arc`

- [ ] **Step 2: Write the failing test for DatasetSessionFactory**

```java
@QuarkusTest
class DatasetSessionFactoryTest {

    @Inject
    DatasetSessionFactory factory;

    @Test
    void create_constructs_session_with_sqlite_stores(@TempDir Path tempDir) throws Exception {
        // Create minimal dataset directory with empty SQLite files
        Files.createFile(tempDir.resolve("mindmap.sqlite"));
        Files.createFile(tempDir.resolve("memory.sqlite"));
        Files.createFile(tempDir.resolve("caps.sqlite"));
        Files.createFile(tempDir.resolve("snapshots.sqlite"));
        Files.writeString(tempDir.resolve("cognitive-profile.yaml"), "agentId: frida\n");

        var session = factory.create(tempDir);

        assertNotNull(session);
        assertNotNull(session.mindMapStore());
        assertNotNull(session.memoryStore());
        assertNotNull(session.cognitionService());
        assertNotNull(session.agentId());
        assertEquals("frida", session.agentId());
    }

    @Test
    void create_throws_on_missing_directory() {
        assertThrows(IllegalArgumentException.class,
            () -> factory.create(Path.of("/nonexistent")));
    }

    @Test
    void close_releases_store_connections(@TempDir Path tempDir) throws Exception {
        Files.createFile(tempDir.resolve("mindmap.sqlite"));
        Files.createFile(tempDir.resolve("memory.sqlite"));
        Files.createFile(tempDir.resolve("caps.sqlite"));
        Files.createFile(tempDir.resolve("snapshots.sqlite"));
        Files.writeString(tempDir.resolve("cognitive-profile.yaml"), "agentId: test\n");

        var session = factory.create(tempDir);
        session.close();
        // Verify stores are closed by attempting an operation
        // (implementation detail — store operations should throw after close)
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/cognitive-workbench-backend -Dtest=DatasetSessionFactoryTest -DfailIfNoTests=false`
Expected: FAIL — classes don't exist

- [ ] **Step 4: Implement DatasetSession record**

```java
package io.casehub.blocks.cognitive.workbench;

import io.casehub.neocortex.cognitive.observability.CognitionService;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.caps.CapsEngine;
import io.casehub.neocortex.cognitive.observability.SnapshotStore;
import java.io.Closeable;

public record DatasetSession(
    String agentId,
    String tenantId,
    MindMapStore mindMapStore,
    CaseMemoryStore memoryStore,
    CapsEngine capsEngine,
    SnapshotStore snapshotStore,
    CognitionService cognitionService
) implements Closeable {

    @Override
    public void close() {
        // Close HikariCP connections for each SQLite store
        // Each store's DataSource implements Closeable
    }
}
```

- [ ] **Step 5: Implement DatasetSessionFactory**

```java
package io.casehub.blocks.cognitive.workbench;

import jakarta.enterprise.context.ApplicationScoped;
import java.nio.file.Path;

@ApplicationScoped
public class DatasetSessionFactory {

    public DatasetSession create(Path datasetDir) {
        if (!Files.isDirectory(datasetDir)) {
            throw new IllegalArgumentException("Dataset directory does not exist: " + datasetDir);
        }
        // Construct SQLite stores pointing at dataset directory files
        // Construct CognitionService with those stores
        // Parse cognitive-profile.yaml for agentId
        // Return new DatasetSession(...)
    }
}
```

- [ ] **Step 6: Implement WorkbenchState**

```java
package io.casehub.blocks.cognitive.workbench;

import jakarta.enterprise.context.ApplicationScoped;
import java.util.concurrent.atomic.AtomicReference;

@ApplicationScoped
public class WorkbenchState {

    private final AtomicReference<DatasetSession> activeSession = new AtomicReference<>();
    private volatile String mode = "static"; // "static" or "live"

    public DatasetSession currentSession() {
        return activeSession.get();
    }

    public DatasetSession requireSession() {
        var session = activeSession.get();
        if (session == null) throw new IllegalStateException("No dataset loaded");
        return session;
    }

    public void switchSession(DatasetSession newSession) {
        var old = activeSession.getAndSet(newSession);
        if (old != null) old.close();
    }

    public String mode() { return mode; }
    public void setMode(String mode) { this.mode = mode; }
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/cognitive-workbench-backend -Dtest=DatasetSessionFactoryTest`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench-backend/
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#468): scaffold workbench backend with DatasetSession lifecycle

Refs casehubio/neocortex#468"
```

### Task 3: WorkbenchApi + Frida Kahlo Seeder

Implement the `@McpDomain("neocortex/workbench")` API for dataset management and the Frida Kahlo biography seeder.

**Files:**
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/WorkbenchApi.java`
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/WorkbenchService.java`
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/DatasetInfo.java`
- Create: `examples/cognitive-workbench-backend/src/main/resources/biographies/frida-kahlo.yaml`
- Test: `examples/cognitive-workbench-backend/src/test/java/io/casehub/blocks/cognitive/workbench/WorkbenchServiceTest.java`
- Test: `examples/cognitive-workbench-backend/src/test/java/io/casehub/blocks/cognitive/workbench/FridaKahloSeederTest.java`

**Interfaces:**
- Consumes: `DatasetSessionFactory`, `WorkbenchState`, `BiographyImportRunner`, `BiographyLoader` (from memory-seeding)
- Produces: `WorkbenchApi` interface (`@McpDomain`), `WorkbenchService` implementation, `DatasetInfo` (record: id, name, path, subjectNodeId, createdAt)

- [ ] **Step 1: Write the WorkbenchApi interface**

```java
@McpDomain(value = "neocortex/workbench", app = "neocortex",
    summary = "Cognitive workbench — dataset management and research operations")
public interface WorkbenchApi {

    @PlatformQuery("List available datasets")
    List<DatasetInfo> listDatasets();

    @PlatformQuery("Activate a dataset by ID")
    DatasetInfo activateDataset(String datasetId);

    @PlatformQuery("Seed a built-in dataset")
    DatasetInfo seedDataset(String name);

    @PlatformQuery("Delete a dataset")
    boolean deleteDataset(String datasetId);

    @PlatformQuery("Get current workbench mode")
    String getMode();

    @PlatformQuery("Set workbench mode (static or live)")
    String setMode(String mode);
}
```

- [ ] **Step 2: Write the failing test for seeding**

```java
class FridaKahloSeederTest {

    @Test
    void seed_creates_frida_kahlo_dataset_with_expected_node_counts(@TempDir Path datasetsDir) {
        // Use in-memory stores for speed
        var mindMap = new InMemoryMindMapStore();
        var memory = new InMemoryMemoryStore();
        // Load and run biography
        var loader = new BiographyLoader();
        var profile = loader.load(
            getClass().getResourceAsStream("/biographies/frida-kahlo.yaml"));
        var runner = new BiographyImportRunner(/* handlers */);
        runner.run(profile, "frida", "frida-tenant");

        // Verify expected node counts by subgraph type
        var persons = mindMap.search(MindMapQuery.builder()
            .tenantId("frida-tenant").subgraphType("person").build());
        assertTrue(persons.size() >= 25, "Expected >= 25 PERSON nodes, got " + persons.size());

        var goals = mindMap.search(MindMapQuery.builder()
            .tenantId("frida-tenant").subgraphType("goal").build());
        assertTrue(goals.size() >= 10, "Expected >= 10 GOAL nodes, got " + goals.size());
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Expected: FAIL — frida-kahlo.yaml doesn't exist yet

- [ ] **Step 4: Write the Frida Kahlo biography YAML**

Create `src/main/resources/biographies/frida-kahlo.yaml` with ~105 entries across the 8-layer biographical model. Key entries:

```yaml
agentId: frida
subjectName: Frida Kahlo

culturalContexts:
  - id: cc-001
    description: "Mexican indigenous art traditions, Pre-Columbian visual motifs"
  - id: cc-002
    description: "Post-revolutionary Mexican nationalism (Mexicanidad)"
  # ... ~5 entries

places:
  - id: place-001
    name: Casa Azul
    description: "Family home in Coyoacán, Mexico City — birthplace and final home"
  - id: place-002
    name: Mexico City
    description: "Cultural capital, center of muralism movement"
  # ... ~10 entries

relationships:
  - id: rel-001
    name: Diego Rivera
    relationship: "Husband, fellow artist, tumultuous partnership"
  - id: rel-002
    name: Cristina Kahlo
    relationship: "Younger sister, complicated by Diego's affair"
  # ... ~30 entries

goals:
  - id: goal-001
    description: "Artistic recognition independent of Diego Rivera"
    tier: thematic
    horizon: aspirational
  - id: goal-002
    description: "Physical recovery and pain management"
    tier: thematic
    horizon: long
  # ... ~15 entries with decomposition

activities:
  - id: act-001
    description: "First solo exhibition at Julien Levy Gallery, New York, 1938"
    date: "1938-11-01"
  # ... ~40 entries

lifeEvents:
  - id: le-001
    description: "Bus accident at age 18 — spinal column, collarbone, ribs, pelvis fractured"
    date: "1925-09-17"
    emotionalImpact: severe
  # ... formative events

beliefs:
  - id: belief-001
    description: "Art must express personal truth, not aesthetic convention"
  # ... ~8 entries

currentStates:
  - id: cs-001
    description: "Chronic pain managed through painting, political activism, and relationships"
```

The full YAML will be ~400 lines covering all SubgraphTypes to exercise the rendering layer.

- [ ] **Step 5: Implement WorkbenchService**

Wire `BiographyImportRunner` for seeding, `DatasetSessionFactory` for session construction, file-based dataset directory management under a configurable `casehub.workbench.datasets-dir`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/cognitive-workbench-backend -Dtest="WorkbenchServiceTest,FridaKahloSeederTest"`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench-backend/
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#468): WorkbenchApi + Frida Kahlo seeder

Refs casehubio/neocortex#468"
```

### Task 4: WebSocket Endpoints — Voice + Cognitive State Push

Implement both WebSocket endpoints: `/ws/conversation` (voice) reusing blocks speech modules, and `/ws/cognitive` (cognitive state push with atomic tick-complete messages).

**Files:**
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/ConversationWebSocket.java`
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/CognitiveWebSocket.java`
- Create: `examples/cognitive-workbench-backend/src/main/java/io/casehub/blocks/cognitive/workbench/TickDelta.java`
- Test: `examples/cognitive-workbench-backend/src/test/java/io/casehub/blocks/cognitive/workbench/CognitiveWebSocketTest.java`

**Interfaces:**
- Consumes: `WorkbenchState`, `DatasetSession`, `CognitionCore` (from cognition module), blocks speech WS patterns from avatar-demo
- Produces: `CognitiveWebSocket` (publishes `tick-complete` composite messages), `ConversationWebSocket` (voice protocol), `TickDelta` (record containing all sub-deltas from a cognitive tick)

- [ ] **Step 1: Study avatar-demo WebSocket pattern**

Read the existing `SpeechWebSocket` or equivalent in `avatar-demo/` to understand the Quarkus websocket-next API usage, audio frame handling, and STT/TTS pipeline integration.

- [ ] **Step 2: Write the failing test for CognitiveWebSocket**

```java
@QuarkusTest
class CognitiveWebSocketTest {

    @Test
    void tick_complete_message_contains_all_sub_deltas() {
        var delta = new TickDelta(
            new MoodUpdate(0.3, -0.1, 0.5),
            List.of(new MemoryFormed("mem-1", "experience", "Had lunch at Dishoom", List.of("Dishoom"))),
            List.of(), // graph mutations
            List.of(), // attention signals
            null, // caps settled
            List.of(), // goal updates
            List.of()  // drive changes
        );

        var json = delta.toJson();

        assertTrue(json.contains("\"type\":\"tick-complete\""));
        assertTrue(json.contains("\"moodUpdate\""));
        assertTrue(json.contains("\"memoriesFormed\""));
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Expected: FAIL — TickDelta doesn't exist

- [ ] **Step 4: Implement TickDelta record**

```java
public record TickDelta(
    MoodUpdate moodUpdate,
    List<MemoryFormed> memoriesFormed,
    List<GraphMutationEvent> graphMutations,
    List<AttentionSignalEvent> attentionSignals,
    CapsSettledEvent capsSettled,
    List<GoalUpdateEvent> goalUpdates,
    List<DriveChangeEvent> driveChanges
) {
    public String toJson() {
        // Jackson serialization with type: "tick-complete" wrapper
    }
}
```

- [ ] **Step 5: Implement CognitiveWebSocket**

Quarkus `@WebSocket(path = "/ws/cognitive")` endpoint. On dataset switch, sends `dataset-switched`. On tick complete, sends composite `tick-complete` message.

- [ ] **Step 6: Implement ConversationWebSocket**

Reuse blocks speech infrastructure. `@WebSocket(path = "/ws/conversation")`. In live mode, after LLM response, trigger `CognitionCore.tick()` and publish delta via `CognitiveWebSocket`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/cognitive-workbench-backend`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench-backend/
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#468): voice + cognitive WebSocket endpoints

Refs casehubio/neocortex#468"
```

---

## Batch 3: Frontend — Rendering Layer + Event Bus

### Task 5: graph-stencil-cognitive Package

Create the rendering layer following the graph-stencil-case pattern. Node stencils per SubgraphType, PAD pill rendering, confidence borders, adapter from CognitionApi `graph()` response to GraphModel.

**Files:**
- Create: `packages/graph-stencil-cognitive/package.json`
- Create: `packages/graph-stencil-cognitive/tsconfig.json`
- Create: `packages/graph-stencil-cognitive/src/index.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/person.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/goal.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/activity.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/place.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/project.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/organisation.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/concept.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/register.ts`
- Create: `packages/graph-stencil-cognitive/src/stencils/pad-pill.ts`
- Create: `packages/graph-stencil-cognitive/src/adapter/cognitive-adapter.ts`
- Create: `packages/graph-stencil-cognitive/src/types.ts`
- Test: `packages/graph-stencil-cognitive/src/__tests__/cognitive-adapter.test.ts`
- Test: `packages/graph-stencil-cognitive/src/__tests__/pad-pill.test.ts`

**Interfaces:**
- Consumes: `@casehubio/graph-core` (GraphModel, GraphNode, GraphEdge, createGraph), `@casehubio/graph-renderer` (registerStencil, StencilTemplate), CognitionApi `graph()` response shape
- Produces: `registerCognitiveStencils()`, `cognitiveAdapter.toGraph(traversalResult): AdapterResult`, `CognitiveNode` type, `PadPill` template helper

- [ ] **Step 1: Create package.json and tsconfig.json**

Follow `graph-stencil-case/package.json` structure. Name: `@casehubio/graph-stencil-cognitive`. Same peer deps (`@xyflow/react`, `react`, `react-dom`). Same deps (`@casehubio/graph-core`, `@casehubio/graph-renderer`, `lit`).

- [ ] **Step 2: Write failing test for PAD pill rendering**

```typescript
import { describe, it, expect } from 'vitest';
import { padPillTemplate, padToColor } from '../stencils/pad-pill.js';

describe('PAD pill', () => {
  it('renders three segments with correct colors', () => {
    const result = padPillTemplate({ pleasure: 0.6, arousal: -0.3, dominance: 0.1 });
    expect(result).toBeDefined();
  });

  it('maps positive pleasure to green', () => {
    expect(padToColor(0.6, 'pleasure')).toBe('#34d399');
  });

  it('maps negative pleasure to red', () => {
    expect(padToColor(-0.6, 'pleasure')).toBe('#f87171');
  });

  it('maps zero to neutral', () => {
    expect(padToColor(0.0, 'pleasure')).toBe('#94a3b8');
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `yarn workspace @casehubio/graph-stencil-cognitive test`
Expected: FAIL — module not found

- [ ] **Step 4: Implement PAD pill**

```typescript
import { html, type TemplateResult } from 'lit';

export function padToColor(value: number, _dimension: string): string {
  if (value > 0.1) return '#34d399';  // green
  if (value < -0.1) return '#f87171'; // red
  return '#94a3b8';                    // slate neutral
}

export function padPillTemplate(pad: { pleasure: number; arousal: number; dominance: number }): TemplateResult {
  return html`
    <div class="pad-pill" title="P:${pad.pleasure.toFixed(1)} A:${pad.arousal.toFixed(1)} D:${pad.dominance.toFixed(1)}">
      <span class="pad-segment" style="background:${padToColor(pad.pleasure, 'pleasure')};width:${Math.abs(pad.pleasure) * 100}%"></span>
      <span class="pad-segment" style="background:${padToColor(pad.arousal, 'arousal')};width:${Math.abs(pad.arousal) * 100}%"></span>
      <span class="pad-segment" style="background:${padToColor(pad.dominance, 'dominance')};width:${Math.abs(pad.dominance) * 100}%"></span>
    </div>
  `;
}
```

- [ ] **Step 5: Implement stencils (one per SubgraphType) + register.ts**

Each stencil follows the `graph-stencil-case` pattern: `registerStencil({ type, label, icon, grammar, render })`. The `render` function returns a lit-html template with the node shape (SVG path), label, PAD pill, confidence border, and traits badges.

Implement all 7 stencils: person (hexagon, #4a9eff), goal (diamond, #34d399), activity (rounded rect, #a78bfa), place (octagon, #fbbf24), project (rectangle, #818cf8), organisation (pentagon, #22d3ee), concept (circle, #94a3b8).

`register.ts` calls `registerStencil()` for each type.

- [ ] **Step 6: Write failing test for cognitive adapter**

```typescript
import { describe, it, expect } from 'vitest';
import { toGraph } from '../adapter/cognitive-adapter.js';

describe('cognitive adapter', () => {
  it('converts graph traversal result to GraphModel', () => {
    const traversalResult = {
      nodes: [
        { id: 'n1', name: 'Frida', subgraphType: 'person', pleasure: 0.3, arousal: 0.1, dominance: 0.5, confidence: 0.9, traits: ['Personable'] },
        { id: 'n2', name: 'Diego', subgraphType: 'person', pleasure: -0.2, arousal: 0.4, dominance: 0.7, confidence: 0.85, traits: [] },
      ],
      edges: [
        { sourceId: 'n1', targetId: 'n2', type: 'married-to', validationTier: 'REGISTERED', confidence: 0.95 },
      ],
    };

    const result = toGraph(traversalResult);

    expect(result.nodes).toHaveLength(2);
    expect(result.edges).toHaveLength(1);
    expect(result.nodes[0].type).toBe('person');
    expect(result.nodes[0].properties.pad).toEqual({ pleasure: 0.3, arousal: 0.1, dominance: 0.5 });
  });
});
```

- [ ] **Step 7: Implement cognitive adapter**

```typescript
import { createGraph, type GraphNode, type GraphEdge, type AdapterResult } from '@casehubio/graph-core';

export interface CognitiveTraversalResult {
  nodes: CognitiveNodeData[];
  edges: CognitiveEdgeData[];
}

export function toGraph(result: CognitiveTraversalResult): AdapterResult {
  const nodes: GraphNode[] = result.nodes.map(n => ({
    id: n.id,
    type: n.subgraphType,
    label: n.name,
    properties: {
      pad: { pleasure: n.pleasure, arousal: n.arousal, dominance: n.dominance },
      confidence: n.confidence,
      traits: n.traits,
    },
  }));

  const edges: GraphEdge[] = result.edges.map(e => ({
    source: e.sourceId,
    target: e.targetId,
    label: e.type,
    properties: {
      validationTier: e.validationTier,
      confidence: e.confidence,
    },
  }));

  return createGraph(nodes, edges);
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `yarn workspace @casehubio/graph-stencil-cognitive test`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add packages/graph-stencil-cognitive/
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#468): graph-stencil-cognitive rendering layer

7 node stencils, PAD pill, confidence borders, cognitive adapter.
Refs casehubio/neocortex#468"
```

### Task 6: Cognitive Event Bus + WebSocket Controller

Define typed cognitive event topics and the WebSocket controller that translates backend `tick-complete` messages into pages-event dispatches.

**Files:**
- Create: `packages/graph-stencil-cognitive/src/events/topics.ts`
- Create: `packages/graph-stencil-cognitive/src/events/cognitive-ws-controller.ts`
- Create: `packages/graph-stencil-cognitive/src/events/types.ts`
- Test: `packages/graph-stencil-cognitive/src/__tests__/cognitive-ws-controller.test.ts`

**Interfaces:**
- Consumes: `@casehubio/pages-data` (`onPagesEvent`, `dispatchPagesEvent`), WebSocket API
- Produces: `CognitiveTopics` (topic string constants), `CognitiveWsController` (Lit reactive controller), typed payload interfaces for each topic

- [ ] **Step 1: Define event types and topic constants**

```typescript
// topics.ts
export const CognitiveTopics = {
  NODE_SELECTED: 'cognitive.node-selected',
  ENTITY_HIGHLIGHT: 'cognitive.entity-highlight',
  MOOD_CHANGED: 'cognitive.mood-changed',
  MEMORY_FORMED: 'cognitive.memory-formed',
  GRAPH_MUTATED: 'cognitive.graph-mutated',
  ATTENTION_SIGNAL: 'cognitive.attention-signal',
  CAPS_SETTLED: 'cognitive.caps-settled',
  GOAL_UPDATED: 'cognitive.goal-updated',
  DRIVE_CHANGED: 'cognitive.drive-changed',
  CONVERSATION_TURN: 'cognitive.conversation-turn',
  DATASET_CHANGED: 'cognitive.dataset-changed',
  MODE_CHANGED: 'cognitive.mode-changed',
} as const;

// types.ts — payload interfaces for each topic
export interface NodeSelectedPayload { nodeId: string; name: string; subgraphType: string; }
export interface MoodChangedPayload { pleasure: number; arousal: number; dominance: number; }
export interface MemoryFormedPayload { memoryId: string; domain: string; text: string; entityRefs: string[]; }
// ... all 12 topic payloads
```

- [ ] **Step 2: Write failing test for WS controller**

```typescript
describe('CognitiveWsController', () => {
  it('dispatches mood-changed event from tick-complete message', () => {
    const dispatched: Array<{ topic: string; payload: unknown }> = [];
    // Mock dispatchPagesEvent
    const controller = new CognitiveWsController(mockHost, {
      wsUrl: 'ws://localhost/ws/cognitive',
      dispatch: (topic, payload) => dispatched.push({ topic, payload }),
    });

    controller._handleMessage(JSON.stringify({
      type: 'tick-complete',
      moodUpdate: { pleasure: 0.5, arousal: -0.1, dominance: 0.3 },
      memoriesFormed: [],
      graphMutations: [],
      attentionSignals: [],
      capsSettled: null,
      goalUpdates: [],
      driveChanges: [],
    }));

    expect(dispatched).toContainEqual({
      topic: 'cognitive.mood-changed',
      payload: { pleasure: 0.5, arousal: -0.1, dominance: 0.3 },
    });
  });
});
```

- [ ] **Step 3: Implement CognitiveWsController**

Lit reactive controller modeled after `AvatarWsController`. Connects to `/ws/cognitive`, parses `tick-complete` messages, dispatches individual pages-events for each non-null sub-delta. Handles `dataset-switched` by dispatching `cognitive.dataset-changed`.

- [ ] **Step 4: Run tests, verify pass, commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add packages/graph-stencil-cognitive/
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#468): cognitive event bus + WS controller

12 typed topics, CognitiveWsController translates tick-complete to pages-events.
Refs casehubio/neocortex#468"
```

---

## Batch 4: Frontend — Components + Shell + Showcase

### Task 7: cognitive-graph Component

The primary visualization — a subgraph explorer using React Flow with cognitive stencils.

**Files:**
- Create: `components/cognitive-graph/package.json`
- Create: `components/cognitive-graph/src/cognitive-graph.ts`
- Create: `components/cognitive-graph/src/index.ts`
- Test: `components/cognitive-graph/src/cognitive-graph.test.ts`

**Interfaces:**
- Consumes: `@casehubio/graph-stencil-cognitive` (stencils, adapter), `@casehubio/pages-data` (onPagesEvent), CognitiveTopics
- Produces: `<cognitive-graph>` custom element. Properties: `endpoint` (CognitionApi base URL), `tenantId`, `subgraphFilter`, `confidenceThreshold`. Events: publishes `cognitive.node-selected` on click, subscribes to `cognitive.graph-mutated` for live updates, `cognitive.entity-highlight` for glow effect, `cognitive.dataset-changed` for reload.

- [ ] **Step 1: Create package.json**

Follow existing component pattern (e.g. `components/case-explorer/package.json`). Name: `@casehubio/blocks-ui-cognitive-graph`.

- [ ] **Step 2: Write failing test**

```typescript
describe('cognitive-graph', () => {
  it('renders graph nodes from endpoint data', async () => {
    const el = await fixture(html`
      <cognitive-graph .data=${mockTraversalResult}></cognitive-graph>
    `);
    const nodes = el.shadowRoot!.querySelectorAll('[data-node-id]');
    expect(nodes.length).toBe(mockTraversalResult.nodes.length);
  });

  it('dispatches node-selected on click', async () => {
    const el = await fixture(html`<cognitive-graph .data=${mockTraversalResult}></cognitive-graph>`);
    const events: CustomEvent[] = [];
    document.addEventListener('pages-event', (e) => events.push(e as CustomEvent));

    const node = el.shadowRoot!.querySelector('[data-node-id="n1"]');
    node?.dispatchEvent(new Event('click'));

    expect(events.some(e => e.detail.topic === 'cognitive.node-selected')).toBe(true);
  });
});
```

- [ ] **Step 3: Implement cognitive-graph component**

Lit component wrapping React Flow. Uses `cognitiveAdapter.toGraph()` for data mapping. Filter bar for subgraph type, confidence threshold. Node click handler dispatches `cognitive.node-selected`. Subscribes to `cognitive.graph-mutated` to animate new nodes/edges, `cognitive.entity-highlight` for glow.

- [ ] **Step 4: Run tests, verify pass, commit**

### Task 8: entity-detail Component

Deep-dive panel with 5 tabs responding to node selection.

**Files:**
- Create: `components/entity-detail/package.json`
- Create: `components/entity-detail/src/entity-detail.ts`
- Create: `components/entity-detail/src/index.ts`
- Test: `components/entity-detail/src/entity-detail.test.ts`

**Interfaces:**
- Consumes: `CognitionApi.entity()` response, `CognitiveTopics.NODE_SELECTED`, `@casehubio/pages-data`
- Produces: `<entity-detail>` custom element. Properties: `endpoint`, `tenantId`. Subscribes to `cognitive.node-selected`, fetches entity data, renders 5 tabs (Overview, Connections, Memories, Trajectory, History).

- [ ] **Step 1: Create package.json and component scaffold**
- [ ] **Step 2: Write failing test for entity loading on node selection**
- [ ] **Step 3: Implement entity-detail with 5 tabs**
- [ ] **Step 4: Run tests, verify pass, commit**

### Task 9: cognitive-workbench Shell + Avatar Integration + Showcase Page

The top-level workbench component using dock-workbench layout, plus the showcase page for the examples gallery.

**Files:**
- Create: `components/cognitive-workbench/package.json`
- Create: `components/cognitive-workbench/src/cognitive-workbench.ts`
- Create: `components/cognitive-workbench/src/index.ts`
- Create: `examples/src/pages/cognitive-workbench-page.ts`
- Create: `examples/mock-data/cognitive-workbench.ts`
- Modify: `examples/src/shell.ts` (add nav entry)
- Test: `components/cognitive-workbench/src/cognitive-workbench.test.ts`

**Interfaces:**
- Consumes: `dock-workbench` (from pages), `<cognitive-graph>`, `<entity-detail>`, `<casehub-avatar-panel>`, `CognitiveWsController`, `WorkbenchApi` endpoints
- Produces: `<cognitive-workbench>` custom element. Properties: `endpoint` (backend base URL). Renders dock-workbench with cognitive-graph in centre, avatar-panel docked right (fixed), entity-detail docked right, dataset selector, mode toggle.

- [ ] **Step 1: Create package.json**

Name: `@casehubio/blocks-ui-cognitive-workbench`. Dependencies include all cognitive components + avatar + pages-ui-components.

- [ ] **Step 2: Write the dock-workbench YAML structure**

```typescript
// The workbench renders a dock-workbench with this zone layout:
// Centre: cognitive-graph
// Right (fixed): casehub-avatar-panel
// Right (zone 2): entity-detail
// Bottom: transcript (from avatar), future affect-timeline slot
// Status bar: connection state, dataset name, mode
```

- [ ] **Step 3: Implement cognitive-workbench**

Wire `CognitiveWsController` for state push. Wire `AvatarWsController` for voice. Dataset selector fetches from `WorkbenchApi.listDatasets()`, activates via `WorkbenchApi.activateDataset()`. Mode toggle switches between static/live.

- [ ] **Step 4: Create showcase page**

```typescript
import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import '@casehubio/blocks-ui-cognitive-workbench';

@customElement('blocks-example-cognitive-workbench')
export class CognitiveWorkbenchPage extends LitElement {
  static override styles = css`
    :host { display: block; height: 100vh; }
  `;

  override render() {
    return html`
      <h2>Cognitive Workbench</h2>
      <p>Interactive cognitive model explorer with voice conversation.</p>
      <cognitive-workbench endpoint="/api"></cognitive-workbench>
    `;
  }
}
```

- [ ] **Step 5: Register in shell.ts**

Add to the `NAV` array in `examples/src/shell.ts`:
```typescript
{ id: 'cognitive-workbench', label: 'Cognitive Workbench', hash: '#cognitive-workbench' }
```

- [ ] **Step 6: Create mock data for offline gallery rendering**

```typescript
// examples/mock-data/cognitive-workbench.ts
export const mockCognitiveGraph = {
  nodes: [
    { id: 'frida', name: 'Frida Kahlo', subgraphType: 'person', pleasure: 0.2, arousal: 0.4, dominance: 0.6, confidence: 0.95, traits: ['Personable'] },
    { id: 'diego', name: 'Diego Rivera', subgraphType: 'person', pleasure: -0.1, arousal: 0.3, dominance: 0.8, confidence: 0.9, traits: ['Personable'] },
    { id: 'casa-azul', name: 'Casa Azul', subgraphType: 'place', pleasure: 0.7, arousal: 0.1, dominance: 0.5, confidence: 0.95, traits: ['Locatable'] },
    { id: 'artistic-recognition', name: 'Artistic Recognition', subgraphType: 'goal', pleasure: 0.4, arousal: 0.6, dominance: 0.3, confidence: 0.8, traits: ['Goallike'] },
    // ... enough nodes to demonstrate all 7 stencil types
  ],
  edges: [
    { sourceId: 'frida', targetId: 'diego', type: 'married-to', validationTier: 'REGISTERED', confidence: 0.95 },
    { sourceId: 'frida', targetId: 'casa-azul', type: 'lives-at', validationTier: 'REGISTERED', confidence: 0.9 },
    { sourceId: 'frida', targetId: 'artistic-recognition', type: 'pursues', validationTier: 'STATED', confidence: 0.85 },
  ],
};
```

- [ ] **Step 7: Run tests, verify pass, commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add components/cognitive-workbench/ components/cognitive-graph/ components/entity-detail/ examples/src/pages/cognitive-workbench-page.ts examples/mock-data/cognitive-workbench.ts examples/src/shell.ts
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#468): cognitive workbench shell, components, and showcase page

dock-workbench layout, avatar integration, cognitive-graph, entity-detail.
Refs casehubio/neocortex#468"
```

---

## References

- [2026-10-08-cognitive-workbench-design.md] — design spec this plan implements
- [cognitive-observability-core/.../CognitionService.java] — attention() stub to wire
- [cognitive-observability-core/.../CognitionApi.java] — 11 MCP endpoints
- [packages/graph-stencil-case/] — stencil package pattern reference
- [packages/avatar/src/avatar-ws-controller.ts] — WebSocket controller pattern
- [packages/avatar/src/casehub-avatar-panel.ts] — avatar panel integration reference
- [examples/avatar-demo/pom.xml] — Quarkus backend module pattern
- [memory-seeding/.../BiographyImportRunner.java] — seeder infrastructure
- [memory-seeding/.../BiographyLoader.java] — YAML biography loading
- [pages/examples/samples/Layout/Dock Workbench.page.yaml] — dock layout DSL
- [mockups/visualiser-mockups.html] — visual spec for node stencils and components
- [mockups/graph-visualisation-mockups.html] — graph and memory detail visual spec
- GitHub #468 — focal issue
- GitHub #471 — parent epic
- GitHub #463–467 — dependency issues (all closed)
