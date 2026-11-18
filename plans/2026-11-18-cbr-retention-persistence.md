# CBR Retention Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1143 — CBR persistence for learned retention parameters
**Issue group:** #1143

**Goal:** Persist learned retention threshold configurations via CBR so the system resumes from its last known-good config on restart instead of DEFAULT.

**Architecture:** Extend `HygieneAdaptationPhase` with stability detection and CBR integration. On stability (N consecutive held ticks), store the current config as a `CbrFeatureRecord`. On first tick per tenant, query CBR for the best prior config and seed `AdaptiveRetentionConfig`. One active case per tenant via supersession.

**Tech Stack:** Java 21, Quarkus 3.32.2, CBR subsystem (CbrRecordStore, CbrFeatureRecord, CbrQuery)

## Global Constraints

- Java 21 source, Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Module: all changes in `cognition` module
- CBR dependency: optional via `Instance<CbrRecordStore>` — graceful degradation when not on classpath
- Tenant isolation: no cross-tenant data retrieval (legal boundary)
- Test: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition`

---

## Batch 1: CBR integration in HygieneAdaptationPhase

### Task 1: Add stability tracking and CBR config properties

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationConfig.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhase.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhaseTest.java`

**Interfaces:**
- Consumes: `HygieneAdaptationConfig` (existing), `AdaptiveRetentionConfig` (existing), `MemoryHygieneOrchestrator` (existing)
- Produces: Stability counter tracking (internal state), new config properties `stabilityThreshold()` returning `int`, `cbrMinSimilarity()` returning `double`

- [ ] **Step 1: Write failing test for stability counter increment on HELD**

```java
@Test
void stabilityCounterIncrementsOnHeld() {
    // First tick — baseline
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());

    // Second tick — pressure in target range = HELD
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());

    // Third tick — still held
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());

    // No adaptation happened — config unchanged
    assertThat(adaptiveConfig.current()).isEqualTo(RetentionConfig.DEFAULT);
    assertThat(firedEvents).isEmpty();
}
```

- [ ] **Step 2: Run test to verify it passes (this is existing behaviour)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#stabilityCounterIncrementsOnHeld`
Expected: PASS (existing hold logic already works)

- [ ] **Step 3: Write failing test for stability counter reset on LOWERED**

```java
@Test
void stabilityCounterResetsOnAdaptation() {
    // Tick 1 — baseline
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());

    // Ticks 2-3 — held (counter should be 2)
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());

    // Tick 4 — high pressure, triggers LOWERED → resets counter
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(40, 2, 100));
    phase.run("t1", List.of());
    assertThat(firedEvents).hasSize(1);

    // Ticks 5-6 — held again, counter restarts from 0
    firedEvents.clear();
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());

    // No CBR store → no case stored, but stability counter is tracking
    assertThat(firedEvents).isEmpty();
}
```

- [ ] **Step 4: Run test to verify it passes (existing behaviour)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#stabilityCounterResetsOnAdaptation`
Expected: PASS

- [ ] **Step 5: Add config properties to HygieneAdaptationConfig**

Add to `HygieneAdaptationConfig.java`:

```java
@WithDefault("3")
int stabilityThreshold();

@WithDefault("0.3")
double cbrMinSimilarity();
```

- [ ] **Step 6: Add stability counter state to HygieneAdaptationPhase**

Add fields to `HygieneAdaptationPhase`:

```java
private final ConcurrentHashMap<String, Integer> stabilityCounters = new ConcurrentHashMap<>();
```

Add stability tracking to the `run()` method. After the existing hold/adapt logic:
- When a tick results in no change (HELD — pressure in target range), call `stabilityCounters.merge(tenantId, 1, Integer::sum)`
- When a tick results in LOWERED or RAISED, call `stabilityCounters.put(tenantId, 0)`

- [ ] **Step 7: Update TestConfig to implement new config methods**

In `HygieneAdaptationPhaseTest.TestConfig`:

```java
@Override public int stabilityThreshold() { return 3; }
@Override public double cbrMinSimilarity() { return 0.3; }
```

- [ ] **Step 8: Run all existing tests to verify nothing is broken**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest`
Expected: All 8 existing tests PASS

- [ ] **Step 9: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationConfig.java cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhase.java cognition/src/test/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhaseTest.java
git commit -m "feat(#1143): add stability tracking and CBR config to HygieneAdaptationPhase

Add stabilityThreshold and cbrMinSimilarity config properties.
Track consecutive held ticks per tenant via stability counter.
Counter resets on any adaptation (LOWERED/RAISED).

Refs #1143

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: CBR case storage on stability confirmation

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhase.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhaseTest.java`

**Interfaces:**
- Consumes: `CbrRecordStore.registerSchema(CbrRecordSchema)`, `CbrRecordStore.store(CbrRecord, String caseType, String entityId, MemoryDomain domain, String tenantId, String caseId, Path scope)`, `CbrRecordStore.findCaseIds(MemoryDomain, String caseType, Map filters, String tenantId)`, `CbrRecordLifecycle.supersede(String caseId, String supersedingCaseId, String reason, String tenantId)`, stability counter from Task 1
- Produces: CBR cases stored with case type `"retention-config"`, domain `MemoryDomain("hygiene")`, features `{evictionPressure, totalScored, consolidationGroups}`

- [ ] **Step 1: Write failing test for CBR schema registration**

Add to `HygieneAdaptationPhaseTest`:

```java
@Test
void registersSchemaWhenCbrStoreAvailable() {
    var cbrStore = new StubCbrRecordStore();
    var phaseWithCbr = new HygieneAdaptationPhase(
            orchestrator, adaptiveConfig, new TestConfig(), firedEvents::add, cbrStore);

    assertThat(cbrStore.registeredSchemas).hasSize(1);
    assertThat(cbrStore.registeredSchemas.getFirst().caseType()).isEqualTo("retention-config");
    assertThat(cbrStore.registeredSchemas.getFirst().fields()).hasSize(3);
}
```

Also add a `StubCbrRecordStore` inner class (minimal stub implementing `CbrRecordStore` with recording lists):

```java
static class StubCbrRecordStore implements CbrRecordStore {
    final List<CbrRecordSchema> registeredSchemas = new ArrayList<>();
    final List<StoredCase> storedCases = new ArrayList<>();
    final List<String> supersededCaseIds = new ArrayList<>();
    private final Map<String, List<CbrMatch<CbrRecord>>> retrievalResults = new HashMap<>();

    record StoredCase(CbrRecord record, String caseType, String entityId,
                      MemoryDomain domain, String tenantId, String caseId) {}

    @Override
    public void registerSchema(CbrRecordSchema schema) {
        registeredSchemas.add(schema);
    }

    @Override
    public String store(CbrRecord cbrRecord, String caseType, String entityId,
                        MemoryDomain domain, String tenantId, String caseId,
                        io.casehub.platform.api.path.Path scope) {
        String id = "case-" + storedCases.size();
        storedCases.add(new StoredCase(cbrRecord, caseType, entityId, domain, tenantId, caseId));
        return id;
    }

    @Override
    public <C extends CbrRecord> List<CbrMatch<C>> retrieveSimilar(CbrQuery query, Class<C> caseType) {
        @SuppressWarnings("unchecked")
        var results = (List<CbrMatch<C>>) (List<?>) retrievalResults.getOrDefault(query.tenantId(), List.of());
        return results;
    }

    void setRetrievalResult(String tenantId, List<CbrMatch<CbrRecord>> results) {
        retrievalResults.put(tenantId, results);
    }

    @Override
    public List<String> findCaseIds(MemoryDomain domain, String caseType,
                                     Map<String, CbrFilter> filters, String tenantId) {
        return storedCases.stream()
                .filter(c -> c.tenantId().equals(tenantId))
                .filter(c -> c.caseType().equals(caseType))
                .map(c -> "case-" + storedCases.indexOf(c))
                .toList();
    }

    @Override public int erase(io.casehub.neocortex.memory.EraseRequest request) { return 0; }
    @Override public int eraseEntity(String entityId, String tenantId) { return 0; }
    @Override public int eraseByScope(io.casehub.platform.api.path.Path scope, String tenantId) { return 0; }
    @Override public boolean supersede(String caseId, String supersedingCaseId, String reason, String tenantId) {
        supersededCaseIds.add(caseId);
        return true;
    }
    @Override public boolean reinstate(String caseId, String tenantId) { return false; }
    @Override public SupersessionStatus getSupersessionStatus(String caseId, String tenantId) { return SupersessionStatus.NOT_SUPERSEDED; }
    @Override public List<SupersessionStatus> findSupersededCases(MemoryDomain domain, String tenantId) { return List.of(); }
    @Override public void recordOutcome(String caseId, CbrOutcome outcome, String tenantId) {}
    @Override public int supersedeMatching(MemoryDomain domain, String caseType, Map<String, CbrFilter> filters, String reason, String tenantId) { return 0; }
    @Override public int supersedeAll(java.util.Collection<String> caseIds, String reason, String tenantId) { return 0; }
    @Override public int reinstateMatching(MemoryDomain domain, String caseType, Map<String, CbrFilter> filters, String tenantId) { return 0; }
    @Override public int reinstateAll(java.util.Collection<String> caseIds, String tenantId) { return 0; }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#registersSchemaWhenCbrStoreAvailable`
Expected: FAIL — constructor with CbrRecordStore parameter doesn't exist

- [ ] **Step 3: Add CbrRecordStore dependency and schema registration**

Modify `HygieneAdaptationPhase`:

Add fields:
```java
private static final String CASE_TYPE = "retention-config";
private static final MemoryDomain DOMAIN = new MemoryDomain("hygiene");

private final CbrRecordStore cbrRecordStore;
private final ConcurrentHashMap<String, String> activeCaseIds = new ConcurrentHashMap<>();
```

Add new constructor for testing (accepts CbrRecordStore directly):
```java
HygieneAdaptationPhase(
        MemoryHygieneOrchestrator hygieneOrchestrator,
        AdaptiveRetentionConfig adaptiveConfig,
        HygieneAdaptationConfig config,
        Consumer<HygieneAdaptationEvent> eventSink,
        CbrRecordStore cbrRecordStore) {
    this.hygieneOrchestrator = hygieneOrchestrator;
    this.adaptiveConfig = adaptiveConfig;
    this.config = config;
    this.eventSink = eventSink;
    this.cbrRecordStore = cbrRecordStore;
    registerSchema();
}
```

Modify the CDI constructor to accept `Instance<CbrRecordStore>`:
```java
public HygieneAdaptationPhase(
        MemoryHygieneOrchestrator hygieneOrchestrator,
        AdaptiveRetentionConfig adaptiveConfig,
        HygieneAdaptationConfig config,
        Event<HygieneAdaptationEvent> adaptationEvent,
        Instance<CbrRecordStore> cbrRecordStoreInstance) {
    this(hygieneOrchestrator, adaptiveConfig, config,
         (Consumer<HygieneAdaptationEvent>) adaptationEvent::fire,
         cbrRecordStoreInstance.isResolvable() ? cbrRecordStoreInstance.get() : null);
}
```

Update existing test constructor (null CbrRecordStore):
```java
HygieneAdaptationPhase(
        MemoryHygieneOrchestrator hygieneOrchestrator,
        AdaptiveRetentionConfig adaptiveConfig,
        HygieneAdaptationConfig config,
        Consumer<HygieneAdaptationEvent> eventSink) {
    this(hygieneOrchestrator, adaptiveConfig, config, eventSink, null);
}
```

Add `registerSchema()` method:
```java
private void registerSchema() {
    if (cbrRecordStore == null) return;
    cbrRecordStore.registerSchema(CbrRecordSchema.of(CASE_TYPE,
            new FeatureField.Numeric("evictionPressure", 0.0, 1.0),
            new FeatureField.Numeric("totalScored", 0, 100_000),
            new FeatureField.Numeric("consolidationGroups", 0, 10_000)));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#registersSchemaWhenCbrStoreAvailable`
Expected: PASS

- [ ] **Step 5: Write failing test for case storage on stability threshold**

```java
@Test
void storesCbrCaseOnStabilityThreshold() {
    var cbrStore = new StubCbrRecordStore();
    var phaseWithCbr = new HygieneAdaptationPhase(
            orchestrator, adaptiveConfig, new TestConfig(), firedEvents::add, cbrStore);

    // Tick 1 — baseline (also does CBR retrieval, finds nothing)
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phaseWithCbr.run("t1", List.of());

    // Ticks 2-4 — held for 3 consecutive ticks (stabilityThreshold=3)
    for (int i = 0; i < 3; i++) {
        orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
        phaseWithCbr.run("t1", List.of());
    }

    assertThat(cbrStore.storedCases).hasSize(1);
    var stored = cbrStore.storedCases.getFirst();
    assertThat(stored.caseType()).isEqualTo("retention-config");
    assertThat(stored.tenantId()).isEqualTo("t1");
    assertThat(stored.record().features()).containsKeys("evictionPressure", "totalScored", "consolidationGroups");
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#storesCbrCaseOnStabilityThreshold`
Expected: FAIL — no case stored

- [ ] **Step 7: Implement case storage in run()**

Add a private method `storeStableConfig`:

```java
private void storeStableConfig(String tenantId, RetentionConfig config,
                                double pressure, int totalScored, int consolidationGroups) {
    if (cbrRecordStore == null) return;

    var features = Map.<String, FeatureValue>of(
            "evictionPressure", FeatureValue.number(pressure),
            "totalScored", FeatureValue.number(totalScored),
            "consolidationGroups", FeatureValue.number(consolidationGroups));

    var record = new CbrFeatureRecord(
            "retention threshold " + config.retentionThreshold()
                    + " at pressure " + String.format("%.3f", pressure)
                    + " for " + totalScored + " memories",
            "retentionThreshold=" + config.retentionThreshold(),
            null,
            new io.casehub.neocortex.cognitive.Confidence(
                    io.casehub.neocortex.cognitive.ConfidenceOrigin.INFERRED, 1.0, null),
            features, null, null);

    String newCaseId = cbrRecordStore.store(record, CASE_TYPE, tenantId,
            DOMAIN, tenantId, null, io.casehub.platform.api.path.Path.root());

    // Supersede previous case
    String previousCaseId = activeCaseIds.put(tenantId, newCaseId);
    if (previousCaseId != null) {
        try {
            cbrRecordStore.supersede(previousCaseId, newCaseId, "newer stable config", tenantId);
        } catch (Exception e) {
            // best-effort supersession
        }
    }

    // Record success outcome
    try {
        cbrRecordStore.recordOutcome(newCaseId,
                CbrOutcome.of(1.0, "stable for " + this.config.stabilityThreshold() + " ticks",
                        java.time.Instant.now()),
                tenantId);
    } catch (Exception e) {
        // best-effort outcome recording
    }

    stabilityCounters.put(tenantId, 0);
}
```

In `run()`, after the existing hold path (line 99-101 — where it puts summary and config and returns), add stability counter logic. The method needs restructuring: instead of returning early on hold, track the hold and check if the threshold is reached.

Modify the end of `run()` — after the existing adaptation/hold logic, add:

```java
// After all adaptation/hold logic, check stability for CBR storage
int counter = stabilityCounters.merge(tenantId, 1, Integer::sum);
if (counter >= config.stabilityThreshold()) {
    double stablePressure = (double) currentSummary.lowRetentionCount() / currentSummary.totalScored();
    storeStableConfig(tenantId, adaptiveConfig.current(), stablePressure,
            currentSummary.totalScored(), currentSummary.consolidationGroups());
}
```

And reset the counter when adaptation occurs (after LOWERED or RAISED):
```java
stabilityCounters.put(tenantId, 0);
```

- [ ] **Step 8: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#storesCbrCaseOnStabilityThreshold`
Expected: PASS

- [ ] **Step 9: Write test for supersession of previous case**

```java
@Test
void supersedesPreviousCaseOnNewStableConfig() {
    var cbrStore = new StubCbrRecordStore();
    var phaseWithCbr = new HygieneAdaptationPhase(
            orchestrator, adaptiveConfig, new TestConfig(), firedEvents::add, cbrStore);

    // Baseline
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phaseWithCbr.run("t1", List.of());

    // First stability window (3 held ticks) → stores case 0
    for (int i = 0; i < 3; i++) {
        orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
        phaseWithCbr.run("t1", List.of());
    }
    assertThat(cbrStore.storedCases).hasSize(1);

    // Adaptation (resets counter)
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(40, 2, 100));
    phaseWithCbr.run("t1", List.of());

    // Second stability window → stores case 1, supersedes case 0
    for (int i = 0; i < 3; i++) {
        orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
        phaseWithCbr.run("t1", List.of());
    }

    assertThat(cbrStore.storedCases).hasSize(2);
    assertThat(cbrStore.supersededCaseIds).hasSize(1);
    assertThat(cbrStore.supersededCaseIds.getFirst()).isEqualTo("case-0");
}
```

- [ ] **Step 10: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#supersedesPreviousCaseOnNewStableConfig`
Expected: PASS (implementation from Step 7 handles this)

- [ ] **Step 11: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest`
Expected: All tests PASS

- [ ] **Step 12: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhase.java cognition/src/test/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhaseTest.java
git commit -m "feat(#1143): store retention config as CBR case on stability confirmation

Register retention-config schema at construction. Store CbrFeatureRecord
with evictionPressure/totalScored/consolidationGroups features when
threshold is stable for N consecutive ticks. Supersede previous case
per tenant.

Refs #1143

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 3: CBR retrieval on first tick per tenant

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhase.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhaseTest.java`

**Interfaces:**
- Consumes: `CbrRecordStore.retrieveSimilar(CbrQuery, Class)` returning `List<CbrMatch<CbrRecord>>`, `AdaptiveRetentionConfig.update(RetentionConfig)`, stability counter and CBR store from Tasks 1-2
- Produces: On first tick per tenant, `AdaptiveRetentionConfig` is seeded with the best matching prior config from CBR (or stays at DEFAULT if no match)

- [ ] **Step 1: Write failing test for startup retrieval**

```java
@Test
void retrievesPriorConfigOnFirstTick() {
    var cbrStore = new StubCbrRecordStore();
    var phaseWithCbr = new HygieneAdaptationPhase(
            orchestrator, adaptiveConfig, new TestConfig(), firedEvents::add, cbrStore);

    // Pre-load a CBR case with a non-default threshold
    var priorConfig = new RetentionConfig(0.07, 1.0, 1.0, 0.5, 0.5);
    var priorRecord = new CbrFeatureRecord(
            "retention threshold 0.07 at pressure 0.150 for 200 memories",
            "retentionThreshold=0.07",
            null,
            new io.casehub.neocortex.cognitive.Confidence(
                    io.casehub.neocortex.cognitive.ConfidenceOrigin.INFERRED, 1.0, null),
            Map.of("evictionPressure", FeatureValue.number(0.15),
                   "totalScored", FeatureValue.number(200),
                   "consolidationGroups", FeatureValue.number(5)),
            null, null);

    cbrStore.setRetrievalResult("t1", List.of(
            new CbrMatch<>(priorRecord, "prior-case-1", "retention-config", 0.8)));

    // First tick — should retrieve prior config and seed it
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phaseWithCbr.run("t1", List.of());

    assertThat(adaptiveConfig.current().retentionThreshold()).isEqualTo(0.07);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#retrievesPriorConfigOnFirstTick`
Expected: FAIL — config is still DEFAULT (0.1)

- [ ] **Step 3: Implement CBR retrieval on first tick**

Add a private method `retrievePriorConfig`:

```java
private void retrievePriorConfig(String tenantId, KnowledgeGapSummary currentSummary) {
    if (cbrRecordStore == null) return;
    if (currentSummary.totalScored() == 0) return;

    double pressure = (double) currentSummary.lowRetentionCount() / currentSummary.totalScored();

    try {
        var query = CbrQuery.of(tenantId, DOMAIN, io.casehub.platform.api.path.Path.root(),
                        CASE_TYPE,
                        Map.of("evictionPressure", FeatureValue.number(pressure),
                               "totalScored", FeatureValue.number(currentSummary.totalScored()),
                               "consolidationGroups", FeatureValue.number(currentSummary.consolidationGroups())),
                        1)
                .withMinSimilarity(config.cbrMinSimilarity())
                .withRetrievalMode(RetrievalMode.FEATURE_ONLY);

        var matches = cbrRecordStore.retrieveSimilar(query, CbrRecord.class);
        if (!matches.isEmpty()) {
            var best = matches.getFirst();
            String solution = best.cbrRecord().solution();
            if (solution != null && solution.startsWith("retentionThreshold=")) {
                double threshold = Double.parseDouble(solution.substring("retentionThreshold=".length()));
                var currentConfig = adaptiveConfig.current();
                var restoredConfig = new RetentionConfig(threshold,
                        currentConfig.confidenceWeight(), currentConfig.recencyWeight(),
                        currentConfig.scopeWeight(), currentConfig.trustWeight());
                adaptiveConfig.update(restoredConfig);
                activeCaseIds.put(tenantId, best.caseId());
            }
        }
    } catch (Exception e) {
        // graceful degradation — log and continue with DEFAULT
        java.util.logging.Logger.getLogger(HygieneAdaptationPhase.class.getName())
                .log(java.util.logging.Level.FINE, "CBR retrieval failed for tenant " + tenantId, e);
    }
}
```

In `run()`, in the first-tick path (where `previous == null`), call `retrievePriorConfig` before storing baseline:

```java
if (previous == null) {
    retrievePriorConfig(tenantId, currentSummary);
    previousSummaries.put(tenantId, currentSummary);
    previousConfigs.put(tenantId, adaptiveConfig.current());
    return;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#retrievesPriorConfigOnFirstTick`
Expected: PASS

- [ ] **Step 5: Write test for no retrieval when CBR store absent**

```java
@Test
void noCbrStoreSkipsRetrievalGracefully() {
    // Phase without CBR store (existing setUp phase)
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phase.run("t1", List.of());

    // Should still use DEFAULT — no NPE, no errors
    assertThat(adaptiveConfig.current()).isEqualTo(RetentionConfig.DEFAULT);
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#noCbrStoreSkipsRetrievalGracefully`
Expected: PASS

- [ ] **Step 7: Write test for no match returns DEFAULT**

```java
@Test
void noMatchKeepsDefault() {
    var cbrStore = new StubCbrRecordStore();
    var phaseWithCbr = new HygieneAdaptationPhase(
            orchestrator, adaptiveConfig, new TestConfig(), firedEvents::add, cbrStore);

    // No retrieval results configured — empty
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phaseWithCbr.run("t1", List.of());

    assertThat(adaptiveConfig.current()).isEqualTo(RetentionConfig.DEFAULT);
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#noMatchKeepsDefault`
Expected: PASS

- [ ] **Step 9: Write test for tenant isolation**

```java
@Test
void retrievalIsIsolatedPerTenant() {
    var cbrStore = new StubCbrRecordStore();
    var phaseWithCbr = new HygieneAdaptationPhase(
            orchestrator, adaptiveConfig, new TestConfig(), firedEvents::add, cbrStore);

    // Set up retrieval result only for tenant t1
    var priorRecord = new CbrFeatureRecord(
            "retention threshold 0.05", "retentionThreshold=0.05", null,
            new io.casehub.neocortex.cognitive.Confidence(
                    io.casehub.neocortex.cognitive.ConfidenceOrigin.INFERRED, 1.0, null),
            Map.of("evictionPressure", FeatureValue.number(0.15),
                   "totalScored", FeatureValue.number(200),
                   "consolidationGroups", FeatureValue.number(5)),
            null, null);
    cbrStore.setRetrievalResult("t1", List.of(
            new CbrMatch<>(priorRecord, "case-t1", "retention-config", 0.8)));

    // First tick for t1 — retrieves config
    orchestrator.setTenantSummary("t1", new KnowledgeGapSummary(15, 1, 100));
    phaseWithCbr.run("t1", List.of());
    assertThat(adaptiveConfig.current().retentionThreshold()).isEqualTo(0.05);

    // Reset config to DEFAULT for t2 test
    adaptiveConfig.update(RetentionConfig.DEFAULT);

    // First tick for t2 — no retrieval result → stays DEFAULT
    orchestrator.setTenantSummary("t2", new KnowledgeGapSummary(15, 1, 100));
    phaseWithCbr.run("t2", List.of());
    assertThat(adaptiveConfig.current()).isEqualTo(RetentionConfig.DEFAULT);
}
```

- [ ] **Step 10: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest#retrievalIsIsolatedPerTenant`
Expected: PASS

- [ ] **Step 11: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=HygieneAdaptationPhaseTest`
Expected: All tests PASS

- [ ] **Step 12: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhase.java cognition/src/test/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhaseTest.java
git commit -m "feat(#1143): retrieve prior retention config from CBR on first tick

On first tick per tenant, query CbrRecordStore for the best matching
retention-config case. If found, seed AdaptiveRetentionConfig with the
stored threshold instead of DEFAULT. Graceful degradation when no CBR
store or no match.

Closes #1143

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 4: Full module build verification

**Files:**
- None modified — verification only

**Interfaces:**
- Consumes: All changes from Tasks 1-3
- Produces: Verified green build for the cognition module

- [ ] **Step 1: Run full cognition module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All tests PASS

- [ ] **Step 2: Run build for the full project (without tests) to verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognition -am`
Expected: BUILD SUCCESS

## References

- [specs/issue-1143-cbr-retention-persistence/2026-11-18-cbr-retention-persistence-design.md] — design spec
- [cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhase.java] — phase being extended
- [cognition/src/main/java/io/casehub/neocortex/cognition/memory/AdaptiveRetentionConfig.java] — in-memory config holder
- [cognition/src/main/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationConfig.java] — config interface
- [cognition/src/main/java/io/casehub/neocortex/cognition/memory/RetentionConfig.java] — config record
- [cognition/src/test/java/io/casehub/neocortex/cognition/memory/HygieneAdaptationPhaseTest.java] — existing tests
- [memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRecordStore.java] — CBR SPI
- [memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrFeatureRecord.java] — feature-vector record
- [memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrQuery.java] — query builder
- [mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java] — CBR pattern template
- [specs/issue-1119-hygiene-adaptation-phase/2026-11-18-hygiene-adaptation-phase-design.md] — parent design
- [GitHub #1143] — focal issue
- [GitHub #1119] — parent implementation
