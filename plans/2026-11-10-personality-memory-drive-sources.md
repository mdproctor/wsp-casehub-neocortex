# Personality+Memory-Driven DriveSource Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #923 — personality+memory-driven DriveSource implementations
**Issue group:** #923, #919, #922

**Goal:** Replace stub DriveSource implementations with a single `MindMapDriveSource` that reads personality+memory-derived intensities from the COGNITIVE subgraph, falling back to CDE-derived personality baselines.

**Architecture:** One generic `MindMapDriveSource` parameterised by `DriveAxis`, following the CuriosityDrive pattern. Reads `drive-intensity` nodes from MindMap's COGNITIVE subgraph (written by consolidation). Falls back to personality baselines derived by `CognitiveDerivationEngine` and stored on `CognitiveDefaults`. Wired into `CognitivePipelineBuilder` and `CognitionTestHarness`, replacing the three 0.1 stubs.

**Tech Stack:** Java 21, Quarkus, MindMapStore, CognitiveDerivationEngine

## Global Constraints

- Java 21 source level
- All code in `cognition` module (main + test)
- Follow CuriosityDrive pattern for MindMap reads
- DriveSource is `@FunctionalInterface`: `DriveIntensity evaluate(String agentId, String tenantId)`
- Trigger text must be descriptive (not "stub")
- IntelliJ MCP preferred for structural editing when available; Edit tool as fallback

---

## Batch 1: CDE Drive Baselines + MindMapDriveSource

### Task 1: Add drive baselines to CognitiveDefaults and CDE

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngineTest.java`

**Interfaces:**
- Produces: `CognitiveDefaults.driveBaseline(DriveAxis axis)` → `double` (0.3–0.6 range)

- [ ] **Step 1: Write failing test for CDE drive baseline derivation**

```java
@Test
void derivesCompetenceBaselineFromDisposition() {
    var view = DescriptorView.of("agent1",
        new DispositionAxes("cooperative", "strict", "aggressive", "moderate", "analytical"),
        List.of(), List.of());
    var defaults = CognitiveDerivationEngine.derive(view);
    assertThat(defaults.driveBaseline(DriveAxis.COMPETENCE)).isCloseTo(0.6, offset(0.05));
}

@Test
void derivesAffiliationBaselineFromDisposition() {
    var view = DescriptorView.of("agent1",
        new DispositionAxes("cooperative", "moderate", "moderate", "moderate", "accommodating"),
        List.of(), List.of());
    var defaults = CognitiveDerivationEngine.derive(view);
    assertThat(defaults.driveBaseline(DriveAxis.AFFILIATION)).isCloseTo(0.5, offset(0.05));
}

@Test
void derivesAutonomyBaselineFromDisposition() {
    var view = DescriptorView.of("agent1",
        new DispositionAxes("independent", "flexible", "conservative", "high", "confronting"),
        List.of(), List.of());
    var defaults = CognitiveDerivationEngine.derive(view);
    assertThat(defaults.driveBaseline(DriveAxis.AUTONOMY)).isCloseTo(0.6, offset(0.05));
}

@Test
void defaultBaselineWhenNoDisposition() {
    var defaults = CognitiveDefaults.empty("agent1");
    assertThat(defaults.driveBaseline(DriveAxis.COMPETENCE)).isCloseTo(0.4, offset(0.01));
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognitive-index/pom.xml test -Dtest="CognitiveDerivationEngineTest" -s .mvn/slot-settings.xml -pl .`
Expected: FAIL — `driveBaseline` method doesn't exist

- [ ] **Step 3: Add driveBaseline method to CognitiveDefaults**

Add a `Map<DriveAxis, Double> driveBaselines` field to CognitiveDefaults (or a method that reads from an internal map). Add a `driveBaseline(DriveAxis)` method returning the value or 0.4 default.

Note: CognitiveDefaults is a record with many fields — add `driveBaselines` as a `@Nullable Map` parameter to the canonical constructor, defaulting to null. The `driveBaseline()` method returns from the map or 0.4.

- [ ] **Step 4: Add derivation logic to CognitiveDerivationEngine**

In the `derive()` method, compute baselines using the disposition axes mapping from the spec:

```java
private static Map<DriveAxis, Double> deriveDriveBaselines(DispositionAxes axes) {
    if (axes == null) return Map.of();
    double competence = (axisValue(axes.ruleFollowing()) + axisValue(axes.riskAppetite())) / 2.0;
    double affiliation = (axisValue(axes.socialOrient()) + axisValue(axes.conflictMode())) / 2.0;
    double autonomy = axisValue(axes.autonomy());
    return Map.of(
        DriveAxis.COMPETENCE, competence,
        DriveAxis.AFFILIATION, affiliation,
        DriveAxis.AUTONOMY, autonomy);
}

private static double axisValue(String value) {
    if (value == null) return 0.4;
    return switch (value.toLowerCase()) {
        case "cooperative", "strict", "aggressive", "high", "autonomous", "confronting", "competitive" -> 0.6;
        case "moderate", "collaborative", "analytical", "accommodating" -> 0.4;
        case "independent", "flexible", "conservative", "low", "avoidant" -> 0.3;
        default -> 0.4;
    };
}
```

Pass the result to the CognitiveDefaults constructor.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognitive-index/pom.xml test -Dtest="CognitiveDerivationEngineTest" -s .mvn/slot-settings.xml -pl .`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngineTest.java
git commit -m "feat(#923): add CDE-derived drive baselines to CognitiveDefaults"
```

### Task 2: MindMapDriveSource implementation

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/MindMapDriveSource.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/drive/MindMapDriveSourceTest.java`

**Interfaces:**
- Consumes: `CognitiveDefaults.driveBaseline(DriveAxis)` from Task 1
- Produces: `MindMapDriveSource implements DriveSource` — constructor `(DriveAxis, MindMapStore, CognitiveDefaultsRegistry)`

- [ ] **Step 1: Write failing tests**

```java
@Test
void returnsIntensityFromMindMapNode() {
    var store = new InMemoryMindMapStore();
    // Seed a COGNITIVE subgraph with a drive-intensity node
    var sgId = store.createSubgraph("t1", "cognitive", SubgraphTypes.COGNITIVE);
    store.addNode(sgId, "t1", "competence-drive", Set.of(),
        Map.of("cognitiveKind", "drive-intensity", "drive-type", "COMPETENCE",
               "agent-id", "a1", "intensity", "0.55",
               "description", "strong mastery orientation"));

    var registry = CognitiveDefaultsRegistry.forTesting(CognitiveDefaults.empty("a1"));
    var source = new MindMapDriveSource(DriveAxis.COMPETENCE, store, registry);
    var result = source.evaluate("a1", "t1");

    assertThat(result.axis()).isEqualTo(DriveAxis.COMPETENCE);
    assertThat(result.intensity()).isCloseTo(0.55, offset(0.01));
    assertThat(result.trigger()).contains("mastery");
}

@Test
void fallsBackToCdeBaselineWhenNoNode() {
    var store = new InMemoryMindMapStore();
    store.createSubgraph("t1", "cognitive", SubgraphTypes.COGNITIVE);
    // No drive-intensity node seeded

    var defaults = /* derive from axes with COMPETENCE baseline ~0.5 */;
    var registry = CognitiveDefaultsRegistry.forTesting(defaults);
    var source = new MindMapDriveSource(DriveAxis.COMPETENCE, store, registry);
    var result = source.evaluate("a1", "t1");

    assertThat(result.axis()).isEqualTo(DriveAxis.COMPETENCE);
    assertThat(result.intensity()).isCloseTo(0.5, offset(0.1));
    assertThat(result.trigger()).contains("competence");
}

@Test
void returnsDefaultWhenNoCdeEntry() {
    var store = new InMemoryMindMapStore();
    var registry = CognitiveDefaultsRegistry.forTesting();
    var source = new MindMapDriveSource(DriveAxis.AFFILIATION, store, registry);
    var result = source.evaluate("unknown-agent", "t1");

    assertThat(result.axis()).isEqualTo(DriveAxis.AFFILIATION);
    assertThat(result.intensity()).isCloseTo(0.4, offset(0.01));
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test -Dtest="MindMapDriveSourceTest" -s .mvn/slot-settings.xml -pl .`
Expected: FAIL — class doesn't exist

- [ ] **Step 3: Implement MindMapDriveSource**

Follow the CuriosityDrive pattern. Use `MindMapQuery` to search the COGNITIVE subgraph for drive-intensity nodes matching the agent and drive-type.

```java
public class MindMapDriveSource implements DriveSource {
    private final DriveAxis axis;
    private final MindMapStore mindMapStore;
    private final CognitiveDefaultsRegistry registry;

    public MindMapDriveSource(DriveAxis axis, MindMapStore mindMapStore,
                               CognitiveDefaultsRegistry registry) {
        this.axis = axis;
        this.mindMapStore = mindMapStore;
        this.registry = registry;
    }

    @Override
    public DriveIntensity evaluate(String agentId, String tenantId) {
        var nodes = mindMapStore.search(MindMapQuery.of(tenantId, 200)
                .withType(SubgraphTypes.COGNITIVE));
        for (var node : nodes) {
            if (!"drive-intensity".equals(node.properties().get("cognitiveKind"))) continue;
            if (!agentId.equals(node.properties().get("agent-id"))) continue;
            if (!axis.name().equals(node.properties().get("drive-type"))) continue;
            double intensity = parseDouble(node.properties().get("intensity"), 0.4);
            String description = node.properties().getOrDefault("description",
                    axis.name().toLowerCase());
            return new DriveIntensity(axis, Math.clamp(intensity, 0.0, 1.0), description);
        }
        double baseline = registry.forAgent(agentId)
                .map(d -> d.driveBaseline(axis))
                .orElse(0.4);
        return new DriveIntensity(axis, baseline, axis.name().toLowerCase());
    }

    private static double parseDouble(String value, double fallback) {
        if (value == null) return fallback;
        try { return Double.parseDouble(value); }
        catch (NumberFormatException e) { return fallback; }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test -Dtest="MindMapDriveSourceTest" -s .mvn/slot-settings.xml -pl .`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/drive/MindMapDriveSource.java cognition/src/test/java/io/casehub/neocortex/cognition/drive/MindMapDriveSourceTest.java
git commit -m "feat(#923): add MindMapDriveSource — reads personality+memory drives from COGNITIVE subgraph"
```

## Batch 2: Wiring + Verification

### Task 3: Wire MindMapDriveSource into pipeline builder and test harness

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitivePipelineBuilder.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/eval/CognitionTestHarness.java`

**Interfaces:**
- Consumes: `MindMapDriveSource(DriveAxis, MindMapStore, CognitiveDefaultsRegistry)` from Task 2

- [ ] **Step 1: Replace stubs in CognitionTestHarness.Builder.build()**

Replace the three stub lines:
```java
// Before:
DriveSource competenceStub  = (a, t) -> new DriveIntensity(DriveAxis.COMPETENCE, 0.1, "stub");
DriveSource affiliationStub = (a, t) -> new DriveIntensity(DriveAxis.AFFILIATION, 0.1, "stub");
DriveSource autonomyStub    = (a, t) -> new DriveIntensity(DriveAxis.AUTONOMY, 0.1, "stub");

// After:
DriveSource competenceSource  = new MindMapDriveSource(DriveAxis.COMPETENCE, store, registry);
DriveSource affiliationSource = new MindMapDriveSource(DriveAxis.AFFILIATION, store, registry);
DriveSource autonomySource    = new MindMapDriveSource(DriveAxis.AUTONOMY, store, registry);
```

Update the `DriveOrchestrator` construction to use the new variable names.

- [ ] **Step 2: Wire in CognitivePipelineBuilder (if stubs exist there)**

Check if `CognitivePipelineBuilder.build()` creates drive sources. If it delegates to CDI injection (likely in production), no change needed. If it hardcodes stubs, replace similarly.

- [ ] **Step 3: Run full cognition test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test -s .mvn/slot-settings.xml -pl . -Dgroups='!llm-eval'`
Expected: all tests PASS (845+)

- [ ] **Step 4: Run existing harness integration test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml test -Dtest="AppraisalStatePropagationTest" -s .mvn/slot-settings.xml -pl .`
Expected: PASS — `harnessTickPropagatesAppraisalToDrives` should show competence well above 0.1

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitivePipelineBuilder.java cognition/src/test/java/io/casehub/neocortex/cognition/eval/CognitionTestHarness.java
git commit -m "feat(#923): wire MindMapDriveSource into pipeline builder and test harness"
```

### Task 4: Run pipeline coherence eval and verify improvement

**Files:**
- No new files — verification only

- [ ] **Step 1: Install cognition module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f cognition/pom.xml install -s .mvn/slot-settings.xml -pl .`

- [ ] **Step 2: Run pipeline coherence eval**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f caps-llm-classifier/pom.xml clean test -Pllm-eval -Dtest="PipelineCoherenceEvalTest" -s .mvn/slot-settings.xml -pl .`
Expected: all 4 tests PASS (score ≥ 4)

- [ ] **Step 3: Read eval results and verify drive sections changed**

```bash
cat caps-llm-classifier/target/experiment-results/pipeline-coherence-eval.json | python3 -m json.tool
```

Verify:
- MoodPromptSection no longer shows "emotionally even" after appraisal
- DrivePromptSection shows realistic values (0.3-0.6 range) with descriptive triggers (not "stub")
- Scores are 4+ across scenarios

- [ ] **Step 4: Save eval results and commit**

```bash
cp caps-llm-classifier/target/experiment-results/pipeline-coherence-eval.json docs/eval/pipeline-coherence-eval-923.json
git add docs/eval/pipeline-coherence-eval-923.json
git commit -m "docs(#923): save pipeline coherence eval results with real drive sources"
```

## References

- [2026-11-10-personality-memory-drive-sources-design.md] — design spec
- `cognition/src/main/java/.../drive/CuriosityDrive.java` — pattern template
- `cognition/src/main/java/.../prompt/observation/CognitionObservationBuilder.java:240-276` — existing drive-intensity node reader
- `cognitive-index/src/main/java/.../CognitiveDerivationEngine.java` — derivation engine
- `cognitive-index/src/main/java/.../CognitiveDefaults.java` — personality defaults record
- GitHub #923 — focal issue
- GitHub #919, #922 — parent issues (appraisal propagation)
- GitHub #894 — pipeline coherence eval
