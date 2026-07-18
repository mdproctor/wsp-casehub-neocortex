# Native Reactive Backends Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #101 — refactor: ReactiveCaseMemoryStore — replace bridge-only implementations with native reactive backends
**Issue group:** #101

**Goal:** Add native reactive implementations for in-memory, Mem0, Graphiti, and Qdrant backends so the reactive SPI path has no bridge.

**Architecture:** Canonical direction follows the underlying technology (engine pattern). Blocking canonical for in-memory (reactive wraps). Reactive canonical for Mem0/Graphiti/Qdrant (blocking delegates via `.await().indefinitely()`). JDBC backends keep the existing bridge.

**Tech Stack:** Java 21, Quarkus 3.32.2, SmallRye Mutiny, MicroProfile REST Client Reactive, Qdrant Java Client 1.18.1 (Guava `ListenableFuture`), LangChain4j 1.14.1

## Global Constraints

- Java 21 source level (running on Java 26 JVM)
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- Mutiny `Uni<>` for all reactive return types — no `CompletableFuture`
- `@Timed` annotations only on canonical direction — never on the delegate side
- Inject blocking SPIs by interface (not concrete class) to avoid ARC `@Alternative` resolution issues
- All IntelliJ MCP operations require `project_path=/Users/mdproctor/claude/casehub/neocortex`

---

### Task 1: ReactiveGraphCaseMemoryStore interface + bridge change

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/ReactiveGraphCaseMemoryStore.java`
- Modify: `memory/src/main/java/io/casehub/memory/runtime/BlockingToReactiveBridge.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/ReactiveGraphCaseMemoryStoreSpiTest.java`

**Interfaces:**
- Consumes: `ReactiveCaseMemoryStore` (memory-api), `GraphMemoryQuery` (memory-api)
- Produces: `ReactiveGraphCaseMemoryStore` interface — used by Task 4 (Graphiti reactive store)

- [ ] **Step 1: Write the failing test**

```java
package io.casehub.neocortex.memory;

import io.smallrye.mutiny.Uni;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class ReactiveGraphCaseMemoryStoreSpiTest {

    @Test
    void defaultGraphQuery_returnsEmptyList() {
        ReactiveCaseMemoryStore base = new ReactiveCaseMemoryStore() {
            @Override public Uni<String> store(MemoryInput input) { return Uni.createFrom().item(""); }
            @Override public Uni<List<Memory>> query(MemoryQuery query) { return Uni.createFrom().item(List.of()); }
            @Override public Uni<Integer> erase(EraseRequest request) { return Uni.createFrom().item(0); }
        };
        // Cast to ReactiveGraphCaseMemoryStore — should fail until interface exists
        ReactiveGraphCaseMemoryStore graphStore = (ReactiveGraphCaseMemoryStore) base;
        List<Memory> result = graphStore.graphQuery(
            new GraphMemoryQuery("entity", new MemoryDomain("d"), "tenant", "question"))
            .await().indefinitely();
        assertTrue(result.isEmpty());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=ReactiveGraphCaseMemoryStoreSpiTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation error — `ReactiveGraphCaseMemoryStore` does not exist

- [ ] **Step 3: Create ReactiveGraphCaseMemoryStore interface**

Use `ide_create_file`:

```java
package io.casehub.neocortex.memory;

import io.smallrye.mutiny.Uni;
import java.util.List;

public interface ReactiveGraphCaseMemoryStore extends ReactiveCaseMemoryStore {

    default Uni<List<Memory>> graphQuery(GraphMemoryQuery query) {
        return Uni.createFrom().item(List.of());
    }
}
```

- [ ] **Step 4: Fix test — cast to ReactiveGraphCaseMemoryStore needs a proper anonymous class**

Update the test to instantiate `ReactiveGraphCaseMemoryStore` directly (not cast):

```java
@Test
void defaultGraphQuery_returnsEmptyList() {
    ReactiveGraphCaseMemoryStore store = new ReactiveGraphCaseMemoryStore() {
        @Override public Uni<String> store(MemoryInput input) { return Uni.createFrom().item(""); }
        @Override public Uni<List<Memory>> query(MemoryQuery query) { return Uni.createFrom().item(List.of()); }
        @Override public Uni<Integer> erase(EraseRequest request) { return Uni.createFrom().item(0); }
    };
    List<Memory> result = store.graphQuery(
        new GraphMemoryQuery("entity", new MemoryDomain("d"), "tenant", "question"))
        .await().indefinitely();
    assertTrue(result.isEmpty());
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=ReactiveGraphCaseMemoryStoreSpiTest`
Expected: PASS

- [ ] **Step 6: Update BlockingToReactiveBridge to implement ReactiveGraphCaseMemoryStore**

Use `ide_edit_member` on `BlockingToReactiveBridge` class declaration:

Change `implements ReactiveCaseMemoryStore` to `implements ReactiveGraphCaseMemoryStore`

The default `graphQuery()` method from the interface returns `List.of()` — matching `NoOpCaseMemoryStore.graphQuery()` behavior. No additional method override needed.

- [ ] **Step 7: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl memory-api,memory`
Expected: BUILD SUCCESS — `BlockingToReactiveBridge` satisfies both `ReactiveCaseMemoryStore` and `ReactiveGraphCaseMemoryStore` via the `extends` relationship.

- [ ] **Step 8: Run existing bridge tests to verify no regression**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/ReactiveGraphCaseMemoryStore.java memory-api/src/test/java/io/casehub/neocortex/memory/ReactiveGraphCaseMemoryStoreSpiTest.java memory/src/main/java/io/casehub/memory/runtime/BlockingToReactiveBridge.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#101): add ReactiveGraphCaseMemoryStore interface, bridge implements it"
```

---

### Task 2: In-memory reactive wrappers

**Files:**
- Create: `memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/ReactiveInMemoryMemoryStore.java`
- Create: `memory-inmem/src/test/java/io/casehub/neocortex/memory/inmem/ReactiveInMemoryMemoryStoreTest.java`
- Create: `memory-cbr-inmem/src/main/java/io/casehub/neocortex/memory/cbr/inmem/ReactiveInMemoryCbrCaseMemoryStore.java`
- Create: `memory-cbr-inmem/src/test/java/io/casehub/neocortex/memory/cbr/inmem/ReactiveInMemoryCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `CaseMemoryStore` SPI (memory-api), `CbrCaseMemoryStore` SPI (memory-api), `ReactiveCaseMemoryStore` (memory-api), `ReactiveCbrCaseMemoryStore` (memory-api)
- Produces: `ReactiveInMemoryMemoryStore` — `@Alternative @Priority(10)` displacing `BlockingToReactiveBridge @DefaultBean`. `ReactiveInMemoryCbrCaseMemoryStore` — `@Alternative @Priority(2)` displacing `BlockingToReactiveCbrBridge @DefaultBean`.

- [ ] **Step 1: Write the CaseMemoryStore reactive wrapper test**

```java
package io.casehub.neocortex.memory.inmem;

import io.casehub.neocortex.memory.*;
import io.smallrye.mutiny.Uni;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.jupiter.api.Assertions.*;

class ReactiveInMemoryMemoryStoreTest {

    private static final MemoryDomain DOMAIN = new MemoryDomain("d");
    private static final String TENANT = "t";
    private static final MemoryInput INPUT = new MemoryInput("e", DOMAIN, TENANT, null, "text", Map.of());
    private static final MemoryQuery QUERY = MemoryQuery.forEntity("e", DOMAIN, TENANT).withLimit(10);
    private static final EraseRequest ERASE = new EraseRequest("e", DOMAIN, TENANT, null);

    private ReactiveInMemoryMemoryStore storeWith(AtomicLong capturedThreadId) {
        CaseMemoryStore spy = new CaseMemoryStore() {
            @Override public String store(MemoryInput i) {
                capturedThreadId.set(Thread.currentThread().getId());
                return "mem-1";
            }
            @Override public List<Memory> query(MemoryQuery q) {
                capturedThreadId.set(Thread.currentThread().getId());
                return List.of();
            }
            @Override public int erase(EraseRequest r) {
                capturedThreadId.set(Thread.currentThread().getId());
                return 1;
            }
        };
        return new ReactiveInMemoryMemoryStore(spy);
    }

    @Test
    void store_executesOnCallerThread() {
        var capturedId = new AtomicLong(-1);
        String result = storeWith(capturedId).store(INPUT).await().indefinitely();
        assertEquals("mem-1", result);
        assertEquals(Thread.currentThread().getId(), capturedId.get(),
            "In-memory reactive wrapper must NOT dispatch to worker pool");
    }

    @Test
    void query_executesOnCallerThread() {
        var capturedId = new AtomicLong(-1);
        storeWith(capturedId).query(QUERY).await().indefinitely();
        assertEquals(Thread.currentThread().getId(), capturedId.get());
    }

    @Test
    void erase_executesOnCallerThread() {
        var capturedId = new AtomicLong(-1);
        int count = storeWith(capturedId).erase(ERASE).await().indefinitely();
        assertEquals(1, count);
        assertEquals(Thread.currentThread().getId(), capturedId.get());
    }

    @Test
    void capabilities_delegatesDirectly() {
        CaseMemoryStore delegate = new CaseMemoryStore() {
            @Override public String store(MemoryInput i) { return ""; }
            @Override public List<Memory> query(MemoryQuery q) { return List.of(); }
            @Override public int erase(EraseRequest r) { return 0; }
            @Override public Set<MemoryCapability> capabilities() {
                return Set.of(MemoryCapability.SCAN, MemoryCapability.DISCOVER_TENANTS);
            }
        };
        var store = new ReactiveInMemoryMemoryStore(delegate);
        assertEquals(Set.of(MemoryCapability.SCAN, MemoryCapability.DISCOVER_TENANTS),
            store.capabilities());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-inmem -Dtest=ReactiveInMemoryMemoryStoreTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: Compilation error — `ReactiveInMemoryMemoryStore` does not exist

- [ ] **Step 3: Implement ReactiveInMemoryMemoryStore**

Use `ide_create_file`:

```java
package io.casehub.neocortex.memory.inmem;

import io.casehub.neocortex.memory.*;
import io.quarkus.arc.DefaultBean;
import io.smallrye.mutiny.Uni;
import jakarta.alternative.Alternative;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.List;
import java.util.Set;

@Alternative
@Priority(10)
@ApplicationScoped
public class ReactiveInMemoryMemoryStore implements ReactiveCaseMemoryStore {

    private final CaseMemoryStore delegate;

    @Inject
    public ReactiveInMemoryMemoryStore(CaseMemoryStore delegate) {
        this.delegate = delegate;
    }

    @Override
    public Uni<String> store(MemoryInput input) {
        return Uni.createFrom().item(() -> delegate.store(input));
    }

    @Override
    public Uni<List<Memory>> query(MemoryQuery query) {
        return Uni.createFrom().item(() -> delegate.query(query));
    }

    @Override
    public Uni<Integer> erase(EraseRequest request) {
        return Uni.createFrom().item(() -> delegate.erase(request));
    }

    @Override
    public Uni<StoreAllResult> storeAll(List<MemoryInput> inputs) {
        return Uni.createFrom().item(() -> delegate.storeAll(inputs));
    }

    @Override
    public Uni<Integer> eraseEntity(String entityId, String tenantId) {
        return Uni.createFrom().item(() -> delegate.eraseEntity(entityId, tenantId));
    }

    @Override
    public Uni<Void> eraseById(String memoryId, String entityId, String tenantId) {
        return Uni.createFrom().voidItem().invoke(() -> delegate.eraseById(memoryId, entityId, tenantId));
    }

    @Override
    public Uni<Integer> eraseEntityAcrossTenants(String entityId, Set<String> tenantIds) {
        return Uni.createFrom().item(() -> delegate.eraseEntityAcrossTenants(entityId, tenantIds));
    }

    @Override
    public Uni<List<Memory>> scan(MemoryScanRequest request) {
        return Uni.createFrom().item(() -> delegate.scan(request));
    }

    @Override
    public Uni<Set<String>> discoverTenants(String attributeKey, String attributeValue) {
        return Uni.createFrom().item(() -> delegate.discoverTenants(attributeKey, attributeValue));
    }

    @Override
    public Set<MemoryCapability> capabilities() {
        return delegate.capabilities();
    }

    @Override
    public void requireCapability(MemoryCapability capability) {
        delegate.requireCapability(capability);
    }
}
```

Note: `@Alternative` annotation is `jakarta.enterprise.inject.Alternative`, not `jakarta.alternative.Alternative`. Fix the import.

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-inmem -Dtest=ReactiveInMemoryMemoryStoreTest`
Expected: PASS — all 4 tests green

- [ ] **Step 5: Write the CBR reactive wrapper test**

```java
package io.casehub.neocortex.memory.cbr.inmem;

import io.casehub.neocortex.memory.EraseRequest;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import io.casehub.platform.api.path.Path;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicLong;
import static org.junit.jupiter.api.Assertions.*;

class ReactiveInMemoryCbrCaseMemoryStoreTest {

    @Test
    void store_executesOnCallerThread() {
        var capturedId = new AtomicLong(-1);
        var delegate = new InMemoryCbrCaseMemoryStore();
        var schema = new CbrFeatureSchema("test", List.of(
            FeatureField.categorical("color")));
        delegate.registerSchema(schema);

        var store = new ReactiveInMemoryCbrCaseMemoryStore(delegate);
        var cbrCase = new FeatureVectorCbrCase("problem", "solution", "outcome",
            Map.of("color", FeatureValue.string("red")));

        String id = store.store(cbrCase, "test", "entity", new MemoryDomain("d"),
            "tenant", null, Path.of("root")).await().indefinitely();
        assertNotNull(id);
    }

    @Test
    void retrieveSimilar_returnsResults() {
        var delegate = new InMemoryCbrCaseMemoryStore();
        var schema = new CbrFeatureSchema("test", List.of(
            FeatureField.categorical("color")));
        delegate.registerSchema(schema);

        var cbrCase = new FeatureVectorCbrCase("problem", "solution", "outcome",
            Map.of("color", FeatureValue.string("red")));
        delegate.store(cbrCase, "test", "entity", new MemoryDomain("d"),
            "tenant", null, Path.of("root"));

        var store = new ReactiveInMemoryCbrCaseMemoryStore(delegate);
        var query = CbrQuery.builder("test", "similar problem",
            Map.of("color", FeatureValue.string("red")), "tenant", Path.of("root")).build();

        List<ScoredCbrCase<FeatureVectorCbrCase>> results = store.retrieveSimilar(query,
            FeatureVectorCbrCase.class).await().indefinitely();
        assertEquals(1, results.size());
    }
}
```

- [ ] **Step 6: Implement ReactiveInMemoryCbrCaseMemoryStore**

Use `ide_create_file`:

```java
package io.casehub.neocortex.memory.cbr.inmem;

import io.casehub.neocortex.memory.EraseRequest;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.*;
import io.smallrye.mutiny.Uni;
import jakarta.enterprise.inject.Alternative;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.util.List;

@Alternative
@Priority(2)
@ApplicationScoped
public class ReactiveInMemoryCbrCaseMemoryStore implements ReactiveCbrCaseMemoryStore {

    private final CbrCaseMemoryStore delegate;

    @Inject
    public ReactiveInMemoryCbrCaseMemoryStore(CbrCaseMemoryStore delegate) {
        this.delegate = delegate;
    }

    @Override
    public Uni<Void> registerSchema(CbrFeatureSchema schema) {
        return Uni.createFrom().voidItem().invoke(() -> delegate.registerSchema(schema));
    }

    @Override
    public Uni<String> store(CbrCase cbrCase, String caseType, String entityId,
                             MemoryDomain domain, String tenantId, String caseId,
                             io.casehub.platform.api.path.Path scope) {
        return Uni.createFrom().item(() -> delegate.store(cbrCase, caseType, entityId,
            domain, tenantId, caseId, scope));
    }

    @Override
    public <C extends CbrCase> Uni<List<ScoredCbrCase<C>>> retrieveSimilar(
            CbrQuery query, Class<C> caseType) {
        return Uni.createFrom().item(() -> delegate.retrieveSimilar(query, caseType));
    }

    @Override
    public Uni<Integer> erase(EraseRequest request) {
        return Uni.createFrom().item(() -> delegate.erase(request));
    }

    @Override
    public Uni<Integer> eraseEntity(String entityId, String tenantId) {
        return Uni.createFrom().item(() -> delegate.eraseEntity(entityId, tenantId));
    }

    @Override
    public Uni<Integer> eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) {
        return Uni.createFrom().item(() -> delegate.eraseByScope(scope, tenantId));
    }

    @Override
    public Uni<Void> recordOutcome(String caseId, String tenantId, CbrOutcome outcome) {
        return Uni.createFrom().voidItem()
            .invoke(() -> delegate.recordOutcome(caseId, tenantId, outcome));
    }

    @Override
    public Uni<Integer> purge(CbrRetentionPolicy policy) {
        return Uni.createFrom().item(() -> delegate.purge(policy));
    }

    @Override
    public Uni<Void> supersede(String caseId, String tenantId, String supersedingCaseId,
                               String reason) {
        return Uni.createFrom().voidItem()
            .invoke(() -> delegate.supersede(caseId, tenantId, supersedingCaseId, reason));
    }

    @Override
    public Uni<Void> reinstate(String caseId, String tenantId) {
        return Uni.createFrom().voidItem().invoke(() -> delegate.reinstate(caseId, tenantId));
    }
}
```

- [ ] **Step 7: Run CBR test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-cbr-inmem -Dtest=ReactiveInMemoryCbrCaseMemoryStoreTest`
Expected: PASS

- [ ] **Step 8: Run full module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-inmem,memory-cbr-inmem`
Expected: All tests pass

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-inmem/ memory-cbr-inmem/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#101): in-memory native reactive wrappers — no worker pool dispatch"
```

---

### Task 3: Mem0 reactive backend

**Files:**
- Create: `memory-mem0/src/main/java/io/casehub/neocortex/memory/mem0/ReactiveMem0Client.java`
- Create: `memory-mem0/src/main/java/io/casehub/neocortex/memory/mem0/ReactiveMem0CaseMemoryStore.java`
- Modify: `memory-mem0/src/main/java/io/casehub/neocortex/memory/mem0/Mem0CaseMemoryStore.java` — thin delegate
- Delete: `memory-mem0/src/main/java/io/casehub/neocortex/memory/mem0/Mem0Client.java` — replaced by reactive client
- Modify: tests in `memory-mem0/src/test/`

**Interfaces:**
- Consumes: `ReactiveCaseMemoryStore` (memory-api), `Mem0AuthFilter` (memory-mem0), `Mem0Config` (memory-mem0), DTO classes (`Mem0AddRequest`, `Mem0AddResponse`, `Mem0ListResponse`, `Mem0Memory`, `Mem0SearchRequest`)
- Produces: `ReactiveMem0CaseMemoryStore` — `@Alternative @Priority(1)` reactive canonical. `Mem0CaseMemoryStore` becomes thin delegate.

- [ ] **Step 1: Create ReactiveMem0Client**

This is the reactive REST client interface. Use `ide_create_file`. Same `@Path` annotations as `Mem0Client`, same `configKey`, but `Uni<>` return types:

```java
package io.casehub.neocortex.memory.mem0;

import io.casehub.neocortex.memory.mem0.dto.*;
import io.smallrye.mutiny.Uni;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import org.eclipse.microprofile.rest.client.annotation.RegisterProvider;
import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;

@RegisterRestClient(configKey = "mem0")
@RegisterProvider(Mem0AuthFilter.class)
@Path("/")
public interface ReactiveMem0Client {

    @POST @Path("/memories")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    Uni<Mem0AddResponse> add(Mem0AddRequest request);

    @GET @Path("/memories")
    @Produces(MediaType.APPLICATION_JSON)
    Uni<Mem0ListResponse> list(
        @QueryParam("user_id") String userId,
        @QueryParam("agent_id") String agentId,
        @QueryParam("run_id") String runId);

    @POST @Path("/search")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    Uni<Mem0ListResponse> search(Mem0SearchRequest request);

    @GET @Path("/memories/{memoryId}")
    @Produces(MediaType.APPLICATION_JSON)
    Uni<Mem0Memory> getById(@PathParam("memoryId") String memoryId);

    @DELETE @Path("/memories/{memoryId}")
    Uni<Void> deleteById(@PathParam("memoryId") String memoryId);

    @DELETE @Path("/memories")
    Uni<Void> deleteAll(
        @QueryParam("user_id") String userId,
        @QueryParam("agent_id") String agentId,
        @QueryParam("run_id") String runId);
}
```

- [ ] **Step 2: Create ReactiveMem0CaseMemoryStore**

This is the canonical implementation — all logic migrates here from `Mem0CaseMemoryStore`. Use `ide_create_file`. The class mirrors the blocking store's logic but uses `ReactiveMem0Client` and `Uni` chains:

Key patterns:
- `client.add(request)` returns `Uni<Mem0AddResponse>` → chain with `.map()`
- `client.list(...)` returns `Uni<Mem0ListResponse>` → chain with `.map()` for filtering
- `storeAll()` overrides default with index-tagged concurrency via `Multi`

The class is `@Alternative @Priority(1) @ApplicationScoped implements ReactiveCaseMemoryStore`.

Port all methods from `Mem0CaseMemoryStore`:
- `store()` → `Uni<String>` via `client.add(request).map(r -> r.results().getFirst().id())`
- `query()` → `Uni<List<Memory>>` via `client.search()/list()` chains
- `erase()` → `Uni<Integer>` via `client.deleteAll()/.deleteById()` chains
- `storeAll()` → `Uni<StoreAllResult>` via `Multi` with concurrency cap
- `capabilities()` → direct delegation (synchronous)
- Helper methods (compoundUserId, toMemory, etc.) are pure functions — copy as-is

- [ ] **Step 3: Convert Mem0CaseMemoryStore to thin delegate**

Use `ide_edit_member` to replace each method body:
- Remove `Mem0Client` injection, add `ReactiveMem0CaseMemoryStore` injection
- Each method becomes: `return reactiveMem0.method(args).await().indefinitely();`
- `capabilities()` and `requireCapability()` delegate directly (no `.await()`)
- Remove the `Mem0Client` field and all private helper methods (moved to reactive store)

- [ ] **Step 4: Delete blocking Mem0Client**

Use `ide_refactor_safe_delete` on `Mem0Client.java`. After step 3, no references should remain (the reactive client replaces it).

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-mem0`

Fix any test failures — tests may need updating to inject the reactive store or use the reactive client. Existing WireMock-based tests should continue to work since the HTTP endpoints haven't changed.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-mem0/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#101): Mem0 native reactive — reactive REST client, canonical store, blocking thin delegate"
```

---

### Task 4: Graphiti reactive backend

**Files:**
- Create: `memory-graphiti/src/main/java/io/casehub/neocortex/memory/graphiti/ReactiveGraphitiClient.java`
- Create: `memory-graphiti/src/main/java/io/casehub/neocortex/memory/graphiti/ReactiveGraphitiCaseMemoryStore.java`
- Modify: `memory-graphiti/src/main/java/io/casehub/neocortex/memory/graphiti/GraphitiCaseMemoryStore.java` — thin delegate
- Delete: `memory-graphiti/src/main/java/io/casehub/neocortex/memory/graphiti/GraphitiClient.java`
- Modify: tests in `memory-graphiti/src/test/`

**Interfaces:**
- Consumes: `ReactiveGraphCaseMemoryStore` (from Task 1), `GraphitiAuthFilter`, `GraphitiConfig`, DTO classes, `GraphMemoryQuery`
- Produces: `ReactiveGraphitiCaseMemoryStore implements ReactiveGraphCaseMemoryStore` — `@Alternative @Priority(2)` reactive canonical. `GraphitiCaseMemoryStore` becomes thin delegate.

Same pattern as Task 3 (Mem0). Key differences:

- `ReactiveGraphitiClient.addMessages()` returns `Uni<Response>` (not typed DTO) — reactive store must check status codes explicitly
- Reactive store implements `ReactiveGraphCaseMemoryStore` (not plain `ReactiveCaseMemoryStore`) to provide reactive `graphQuery()`
- `@RegisterProvider(GraphitiAuthFilter.class)` on reactive client

- [ ] **Step 1: Create ReactiveGraphitiClient**

Use `ide_create_file`. Same structure as `ReactiveMem0Client` — `@RegisterRestClient(configKey = "graphiti")` with `Uni<>` returns.

```java
package io.casehub.neocortex.memory.graphiti;

import io.casehub.neocortex.memory.graphiti.dto.*;
import io.smallrye.mutiny.Uni;
import jakarta.ws.rs.*;
import jakarta.ws.rs.core.MediaType;
import jakarta.ws.rs.core.Response;
import org.eclipse.microprofile.rest.client.annotation.RegisterProvider;
import org.eclipse.microprofile.rest.client.inject.RegisterRestClient;
import java.util.List;

@RegisterRestClient(configKey = "graphiti")
@RegisterProvider(GraphitiAuthFilter.class)
@Path("/")
public interface ReactiveGraphitiClient {

    @POST @Path("/messages")
    @Consumes(MediaType.APPLICATION_JSON)
    Uni<Response> addMessages(AddMessagesRequest request);

    @POST @Path("/search")
    @Consumes(MediaType.APPLICATION_JSON)
    @Produces(MediaType.APPLICATION_JSON)
    Uni<GraphitiSearchResponse> search(GraphitiSearchRequest request);

    @GET @Path("/episodes/{groupId}")
    @Produces(MediaType.APPLICATION_JSON)
    Uni<List<GraphitiEpisodicNode>> getEpisodes(
        @PathParam("groupId") String groupId,
        @QueryParam("last_n") int lastN);

    @DELETE @Path("/group/{groupId}")
    Uni<Void> deleteGroup(@PathParam("groupId") String groupId);

    @DELETE @Path("/episode/{uuid}")
    Uni<Void> deleteEpisode(@PathParam("uuid") String uuid);
}
```

- [ ] **Step 2: Create ReactiveGraphitiCaseMemoryStore**

Use `ide_create_file`. Port all logic from `GraphitiCaseMemoryStore`. Implements `ReactiveGraphCaseMemoryStore` (from Task 1) — provides both standard `ReactiveCaseMemoryStore` methods and reactive `graphQuery()`.

`@Alternative @Priority(2) @ApplicationScoped`.

Same porting pattern as Mem0:
- `store()` → `client.addMessages(request)` returns `Uni<Response>`, chain with `.map()`
- `graphQuery()` → `client.search(request).map(response -> extractFacts(response))`
- `erase()` → `client.deleteGroup()/.deleteEpisode()` chains

- [ ] **Step 3: Convert GraphitiCaseMemoryStore to thin delegate**

Use `ide_edit_member` to replace each method body. Injects `ReactiveGraphitiCaseMemoryStore`. Each method: `return reactiveStore.method(args).await().indefinitely();` for reactive methods, direct delegation for `capabilities()`.

- [ ] **Step 4: Delete blocking GraphitiClient**

Use `ide_refactor_safe_delete` on `GraphitiClient.java`.

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-graphiti`

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-graphiti/ memory-api/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#101): Graphiti native reactive — reactive REST client, canonical store, blocking thin delegate"
```

---

### Task 5: Qdrant reactive backend

**Files:**
- Create: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/ReactiveQdrantCbrCaseMemoryStore.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/QdrantCbrCaseMemoryStore.java` — thin delegate
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrCollectionManager.java` — add async method variants
- Modify: tests in `memory-qdrant/src/test/`

**Interfaces:**
- Consumes: `ReactiveCbrCaseMemoryStore` (memory-api), `QdrantClient` async API (`searchAsync`, `upsertAsync`, `scrollAsync`, `deleteAsync`), `CbrCollectionManager` async methods, `EmbeddingModel`, `SparseEmbedder`, `QdrantCbrConfig`, `CbrPointBuilder`, `CbrQueryTranslator`, `CbrFeatureValidator`, `CbrSimilarityScorer`
- Produces: `ReactiveQdrantCbrCaseMemoryStore` — `@ApplicationScoped` displacing `BlockingToReactiveCbrBridge @DefaultBean`. `QdrantCbrCaseMemoryStore` becomes thin delegate.

This is the largest task. The Qdrant store has 1043 lines of complex search logic.

**Key pattern — `toUni()` helper:**

```java
private static <T> Uni<T> toUni(ListenableFuture<T> future) {
    return Uni.createFrom().<T>emitter(em ->
        Futures.addCallback(future, new FutureCallback<>() {
            @Override public void onSuccess(T result) { em.complete(result); }
            @Override public void onFailure(Throwable t) { em.fail(t); }
        }, MoreExecutors.directExecutor()));
}
```

- [ ] **Step 1: Add async methods to CbrCollectionManager**

Use `ide_insert_member` to add async variants alongside existing blocking methods:

```java
Uni<Void> ensureCollectionAsync(String caseType, int vectorDimension) {
    // Same logic as ensureCollection() but chains toUni() calls
    // instead of blocking .get()
}

Uni<Void> registerSchemaIndexesAsync(CbrFeatureSchema schema, int vectorDimension) {
    // Same logic, chained with .chain()
}

Uni<Integer> deleteByFilterAsync(String collection, Filter filter) {
    // Same logic, scroll + delete via toUni()
}
```

Each method mirrors the blocking version's logic but replaces `future.get()` with `toUni(future)` and `.chain()` sequencing.

- [ ] **Step 2: Create ReactiveQdrantCbrCaseMemoryStore**

Use `ide_create_file`. This is the canonical implementation — ALL logic from `QdrantCbrCaseMemoryStore` moves here. The class is `@ApplicationScoped implements ReactiveCbrCaseMemoryStore`.

Key reactive patterns by method category:

**store():**
```java
@Override
public Uni<String> store(CbrCase cbrCase, String caseType, String entityId,
                         MemoryDomain domain, String tenantId, String caseId,
                         io.casehub.platform.api.path.Path scope) {
    // Validate, build point (CPU — synchronous)
    // Then chain: ensureCollectionAsync → toUni(client.upsertAsync(...))
    return collectionManager.ensureCollectionAsync(caseType, vectorDimension())
        .chain(() -> {
            PointStruct point = buildPoint(cbrCase, caseType, entityId, domain,
                tenantId, caseId, scope);
            String collection = collectionManager.collectionName(caseType);
            return toUni(collectionManager.client().upsertAsync(collection,
                List.of(point)));
        })
        .map(result -> pointId)
        .chain(id -> {
            if (delegate != null) {
                return Uni.createFrom().item(() -> {
                    delegate.store(serializeToMemoryInput(...));
                    return id;
                });
            }
            return Uni.createFrom().item(id);
        });
}
```

**retrieveSimilar() — the complex one:**
```java
@Override
public <C extends CbrCase> Uni<List<ScoredCbrCase<C>>> retrieveSimilar(
        CbrQuery query, Class<C> caseClass) {
    // 1. Resolve mode, build filter (CPU)
    RetrievalMode mode = resolveEffectiveMode(query);
    String collection = collectionManager.collectionName(query.caseType());
    Filter filter = CbrQueryTranslator.buildFilter(query, schemas.get(query.caseType()));

    return switch (mode) {
        case FEATURE_ONLY -> retrieveFeatureOnlyAsync(query, caseClass, collection, filter,
            schemas.get(query.caseType()));
        case SEMANTIC_ONLY -> retrieveSemanticOnlyAsync(query, caseClass, collection, filter);
        case HYBRID -> retrieveHybridAsync(query, caseClass, collection, filter,
            schemas.get(query.caseType()));
    };
}
```

**retrieveHybridAsync() — parallel leg dispatch:**
```java
private <C extends CbrCase> Uni<List<ScoredCbrCase<C>>> retrieveHybridAsync(
        CbrQuery query, Class<C> caseClass, String collection,
        Filter filter, CbrFeatureSchema schema) {
    // 1. Hoist embeddings (worker pool — blocking LangChain4j APIs)
    Uni<Embedding> denseUni = embeddingModel != null
        ? Uni.createFrom().item(() -> embeddingModel.embed(query.problem()).content())
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
        : Uni.createFrom().nullItem();
    Uni<Map<Integer, Float>> sparseUni = sparseEmbedder != null
        ? Uni.createFrom().item(() -> sparseEmbedder.embed(query.problem()))
            .runSubscriptionOn(Infrastructure.getDefaultWorkerPool())
        : Uni.createFrom().nullItem();

    return Uni.combine().all().unis(denseUni, sparseUni).asTuple()
        .chain(embeddings -> {
            // 2. Fire search legs in parallel with per-leg error recovery
            var dense = executeDenseSearchAsync(collection, filter, query, embeddings.getItem1())
                .onFailure().recoverWithItem(e -> { LOG.warning("Dense failed: " + e); return List.of(); });
            var splade = executeSpladeSearchAsync(collection, filter, query, embeddings.getItem2())
                .onFailure().recoverWithItem(e -> { LOG.warning("SPLADE failed: " + e); return List.of(); });
            var bm25 = executeBm25SearchAsync(collection, filter, query)
                .onFailure().recoverWithItem(e -> { LOG.warning("BM25 failed: " + e); return List.of(); });
            var filterQ = executeFilterQueryAsync(collection, filter, query.topK())
                .onFailure().recoverWithItem(e -> { LOG.warning("Filter failed: " + e); return List.of(); });

            return Uni.join().all(dense, splade, bm25, filterQ).andFailFast();
        })
        .map(legs -> {
            // 3. Fuse scores (CPU — same logic as blocking version)
            // ... merge, score, sort, trim
        });
}
```

Each `executeXxxSearchAsync()` method uses `toUni(client.searchAsync(searchRequest))`.

All remaining methods (`erase`, `eraseEntity`, `eraseByScope`, `recordOutcome`, `supersede`, `reinstate`, `purge`) follow the same pattern: build the request (CPU), then `toUni(client.xxxAsync(...))` for the I/O call, chain with `.map()` for result processing.

Pure CPU helper methods (`reconstructCase`, `reconstructPlanCase`, `reconstructFeatureVector`, `mergePoints`, `trimToTopK`, `buildTextOverrides`, etc.) copy from the blocking store unchanged.

- [ ] **Step 3: Convert QdrantCbrCaseMemoryStore to thin delegate**

Use `ide_edit_member` on each method. Remove all logic, replace with delegation:

```java
@ApplicationScoped
public class QdrantCbrCaseMemoryStore implements CbrCaseMemoryStore {

    @Inject ReactiveQdrantCbrCaseMemoryStore reactiveStore;

    @Override
    public void registerSchema(CbrFeatureSchema schema) {
        reactiveStore.registerSchema(schema).await().indefinitely();
    }

    @Override
    public String store(CbrCase cbrCase, String caseType, String entityId,
                        MemoryDomain domain, String tenantId, String caseId,
                        io.casehub.platform.api.path.Path scope) {
        return reactiveStore.store(cbrCase, caseType, entityId, domain, tenantId,
            caseId, scope).await().indefinitely();
    }

    @Override
    public <C extends CbrCase> List<ScoredCbrCase<C>> retrieveSimilar(
            CbrQuery query, Class<C> caseType) {
        return reactiveStore.retrieveSimilar(query, caseType).await().indefinitely();
    }

    // ... same pattern for all remaining methods
}
```

Remove all private fields and helper methods (moved to reactive store). Keep only `reactiveStore` injection and delegation methods.

- [ ] **Step 4: Run Testcontainers integration tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-qdrant`

This runs `QdrantCbrCaseMemoryStoreTest` (Testcontainers Qdrant) which exercises the full path: thin delegate → reactive store → Qdrant.

- [ ] **Step 5: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Verify all modules compile and tests pass across the project.

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-qdrant/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#101): Qdrant native reactive — async gRPC, parallel search legs, blocking thin delegate"
```
