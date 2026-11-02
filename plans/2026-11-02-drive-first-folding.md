# Drive-First Folding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #732 — Fold EntityKnowledge/SocialComparison/DomainActivation sections into drive-first rendering
**Issue group:** #758, #759, #755, #733, #732, #753

**Goal:** Enrich DriveDescriptionGenerationPhase (P22) with entity knowledge, social comparison, and domain activation data so drive descriptions are grounded in specific entities, perspective divergence, and cross-domain emotional patterns — eliminating the need for separate analytical prompt sections.

**Architecture:** Inject `CognitiveProfile` and `DomainActivation` into P22 via CDI `Instance<>` for graceful degradation. P22 calls these services at consolidation time to build a unified "Relational Context" section in its LLM prompt. The three analytical sections (`EntityKnowledgePromptSection`, `SocialComparisonPromptSection`, `DomainActivationPromptSection`) are disabled by default in `CognitionConfig.all()`.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI Instance<>, InMemoryMindMapStore (tests), StubPipelines (tests)

## Global Constraints

- Java 21 source, Java 26 JVM
- No new Maven dependencies — `cognitive-index` already on `mindmap-intelligence` classpath
- Barrett somatic register: all prompt text uses discovery verbs, no analytical language
- Token budget: max 5 memories per entity, max 5 entities in relational context

---

## Batch 1: P22 enrichment — entity knowledge and social comparison

### Task 1: Inject CognitiveProfile into P22 and build relational context prompt section

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhaseTest.java`

**Interfaces:**
- Consumes: `CognitiveProfile.resolve(CognitiveProfileQuery)` → `Optional<EntityKnowledge>` from `cognitive-index`
- Consumes: `SocialComparison.compare(Map<PrincipalId, EntityKnowledge>)` → `PerspectivalComparison` from `cognitive-index`
- Produces: Extended user prompt in `callLlm()` with "Relational context" section after "Relationships"

- [ ] **Step 1: Write the failing test — relational context appears in LLM prompt**

Add test to `DriveDescriptionGenerationPhaseTest`:

```java
@Test
void promptIncludesRelationalContextWhenCognitiveProfileAvailable() {
    seedDriveNode("gallantry", 0.9);
    seedFormationMemory("Your father knelt to help the stranger", "gallantry");
    seedRelationalSchema(AGENT, "penelope-pitstop", "beloved",
                         "She means everything");

    phase.run(TENANT, List.of());

    var descPrompts = capturedUserPrompts.stream()
                                         .filter(p -> p.contains("gallantry"))
                                         .toList();
    assertThat(descPrompts).isNotEmpty();
    assertThat(descPrompts.getFirst()).contains("Relational context");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest#promptIncludesRelationalContextWhenCognitiveProfileAvailable`
Expected: FAIL — prompt does not contain "Relational context"

- [ ] **Step 3: Add CognitiveProfile injection to P22**

Add to `DriveDescriptionGenerationPhase`:

```java
import io.casehub.neocortex.cognitive.index.CognitiveProfile;
import io.casehub.neocortex.cognitive.index.CognitiveProfileQuery;
import io.casehub.neocortex.cognitive.index.EntityKnowledge;
import io.casehub.neocortex.cognitive.index.SocialComparison;
import io.casehub.neocortex.cognitive.index.PerspectivalComparison;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryDomain;
import jakarta.enterprise.inject.Instance;
```

Change constructor:

```java
private final MindMapStore store;
private final CognitiveProfile cognitiveProfile;  // nullable
private volatile SessionPipeline sessionPipeline;

private static final int MAX_ENTITIES = 5;
private static final int MEMORY_LIMIT = 5;

@Inject
public DriveDescriptionGenerationPhase(MindMapStore store,
                                        Instance<CognitiveProfile> cognitiveProfileInstance) {
    this.store = store;
    this.cognitiveProfile = cognitiveProfileInstance.isUnsatisfied()
        ? null : cognitiveProfileInstance.get();
}
```

Add method to resolve relational context:

```java
private String buildRelationalContext(String tenantId, String agentId,
                                       List<MindMapNode> agentSchemas) {
    if (cognitiveProfile == null || agentSchemas.isEmpty()) {
        return "";
    }

    var sb = new StringBuilder();
    sb.append("Relational context for your pulls:\n\n");

    int entityCount = 0;
    for (var schema : agentSchemas) {
        if (entityCount >= MAX_ENTITIES) break;
        String targetId = schema.properties().get("target-id");
        String role = schema.properties().get("rel.role");
        if (targetId == null || role == null) continue;

        var query = CognitiveProfileQuery.byName(targetId, null)
            .withTenantId(tenantId)
            .withMemoryLimit(MEMORY_LIMIT);
        var knowledge = cognitiveProfile.resolve(query);
        if (knowledge.isEmpty()) continue;

        var ek = knowledge.get();
        sb.append("About ").append(ek.node().name());
        String type = ek.node().type();
        if (type != null) sb.append(" (").append(type).append(")");
        sb.append(":\n");

        var experienceMemories = ek.memories().getOrDefault(
            MemoryDomain.of("experience"), List.of());
        if (!experienceMemories.isEmpty()) {
            sb.append("  Recent memories:\n");
            for (var mem : experienceMemories) {
                sb.append("    - ").append(mem.text()).append("\n");
            }
        }

        var trajectory = ek.trajectory();
        if (trajectory != null && trajectory.sampleCount() > 0) {
            sb.append("  Emotional trajectory: ").append(trajectory.trend())
              .append(" (pleasure slope: ").append(
                  String.format("%.2f", trajectory.pleasureSlope()))
              .append(")\n");
        }
        sb.append("\n");
        entityCount++;
    }

    return sb.toString();
}
```

Modify `callLlm()` — add a `relationalContext` parameter and append it after the "Relationships" section:

```java
private String callLlm(AgentSession session, String driveType, String intensity,
                       List<MindMapNode> servingMemories,
                       List<MindMapNode> personalityNodes, MindMapNode attachmentNode,
                       List<MindMapNode> agentSchemas,
                       String bodyLocation, String channelEmphasis,
                       Map<String, String> otherDriveLocations,
                       String relationalContext) {
    // ... existing prompt building ...

    // After the relationships section and before the final instruction:
    if (relationalContext != null && !relationalContext.isEmpty()) {
        promptBuilder.append("\n").append(relationalContext);
    }

    // ... rest of method ...
}
```

Update `generateAndStore()` to call `buildRelationalContext()` and pass it through:

```java
String relationalContext = buildRelationalContext(tenantId, agentId, agentSchemas);
String rawResponse = callLlm(session, driveType, intensity, servingMemories,
                              personalityNodes, attachmentNode, agentSchemas,
                              bodyLocation, channelEmphasis, otherDriveLocations,
                              relationalContext);
```

Update test setUp to supply a `CognitiveProfile` mock via the constructor. Since `Instance<CognitiveProfile>` is CDI, the test constructor needs a wrapper. Create a helper `Instance` stub:

```java
// In test class, add helper
@SuppressWarnings("unchecked")
private static <T> Instance<T> satisfiedInstance(T value) {
    var instance = (Instance<T>) org.mockito.Mockito.mock(Instance.class);
    org.mockito.Mockito.when(instance.isUnsatisfied()).thenReturn(false);
    org.mockito.Mockito.when(instance.get()).thenReturn(value);
    return instance;
}

@SuppressWarnings("unchecked")
private static <T> Instance<T> unsatisfiedInstance() {
    var instance = (Instance<T>) org.mockito.Mockito.mock(Instance.class);
    org.mockito.Mockito.when(instance.isUnsatisfied()).thenReturn(true);
    return instance;
}
```

Update setUp to wire a `CognitiveProfile` that returns entity knowledge from the in-memory store. Since `CognitiveProfile` is `@ApplicationScoped` and depends on MindMapStore + CaseMemoryStore, use the unsatisfied instance for existing tests (no behavioral change) and a satisfied instance for the new test.

Actually, the simpler approach: create two phase instances in setUp — one without CognitiveProfile (existing tests) and one with. Or better: keep the existing phase as-is (unsatisfied instance) and create a separate test with a satisfied instance.

Add to setUp:

```java
phase = new DriveDescriptionGenerationPhase(store, unsatisfiedInstance());
```

For the new test, create a CognitiveProfile that delegates to the same store. Since CognitiveProfile depends on MindMapStore, CaseMemoryStore, and AffectTrajectoryAnalyzer, and the test doesn't need real memory resolution, mock it:

```java
@Test
void promptIncludesRelationalContextWhenCognitiveProfileAvailable() {
    var mockProfile = org.mockito.Mockito.mock(CognitiveProfile.class);
    // Seed a target entity node in the store
    String targetNodeId = store.addNode(
        NodeInput.of("penelope-pitstop", cognitiveSubgraphId)
            .withProperties(Map.of("type", "person")),
        TENANT);
    var targetNode = store.getNode(targetNodeId, TENANT).orElseThrow();

    var entityKnowledge = new EntityKnowledge(
        targetNode, List.of(),
        Map.of(MemoryDomain.of("experience"), List.of()),
        null, Set.of(), TENANT, null);

    org.mockito.Mockito.when(mockProfile.resolve(org.mockito.ArgumentMatchers.any()))
        .thenReturn(java.util.Optional.of(entityKnowledge));

    var enrichedPhase = new DriveDescriptionGenerationPhase(store, satisfiedInstance(mockProfile));
    enrichedPhase.setSessionPipeline(/* same pipeline as setUp */);

    seedDriveNode("gallantry", 0.9);
    seedFormationMemory("Your father knelt to help the stranger", "gallantry");
    seedRelationalSchema(AGENT, "penelope-pitstop", "beloved",
                         "She means everything");

    enrichedPhase.run(TENANT, List.of());

    var descPrompts = capturedUserPrompts.stream()
                                         .filter(p -> p.contains("gallantry"))
                                         .toList();
    assertThat(descPrompts).isNotEmpty();
    assertThat(descPrompts.getFirst()).contains("Relational context");
    assertThat(descPrompts.getFirst()).contains("penelope-pitstop");
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest#promptIncludesRelationalContextWhenCognitiveProfileAvailable`
Expected: PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest`
Expected: All existing tests PASS (they use unsatisfied instance — no behavioral change)

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhase.java
git add mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhaseTest.java
git commit -m "feat(#732): inject CognitiveProfile into P22 for entity-grounded drive descriptions

Adds relational context (entity memories, affect trajectory) to the
P22 LLM prompt alongside existing relational schemas. Instance<> for
graceful degradation when CognitiveProfile not on classpath.

Refs #732"
```

### Task 2: Add domain activation correlation to P22 relational context

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhaseTest.java`

**Interfaces:**
- Consumes: `DomainActivation.correlate(DomainActivationQuery)` → `Optional<DomainActivationResult>` from `cognitive-index`
- Produces: "Cross-domain emotional patterns" subsection in the relational context prompt

- [ ] **Step 1: Write the failing test — domain correlation appears in prompt**

```java
@Test
void promptIncludesDomainActivationWhenAvailable() {
    var mockProfile = org.mockito.Mockito.mock(CognitiveProfile.class);
    org.mockito.Mockito.when(mockProfile.resolve(org.mockito.ArgumentMatchers.any()))
        .thenReturn(java.util.Optional.empty());

    var mockDomainActivation = org.mockito.Mockito.mock(DomainActivation.class);
    var correlation = new DomainCorrelation(0.85, List.of(),
        CorrelationStrength.STRONG, 0.01, 10, 12);
    var result = new DomainActivationResult(
        Map.of("art", new DomainSignal("sg-art", null, 5, 10, 7),
               "relationships", new DomainSignal("sg-rel", null, 3, 8, 7)),
        Map.of(new DomainPair("art", "relationships"), correlation),
        Map.of(), Map.of());
    org.mockito.Mockito.when(mockDomainActivation.correlate(org.mockito.ArgumentMatchers.any()))
        .thenReturn(java.util.Optional.of(result));

    var enrichedPhase = new DriveDescriptionGenerationPhase(
        store, satisfiedInstance(mockProfile), satisfiedInstance(mockDomainActivation));
    enrichedPhase.setSessionPipeline(/* same pipeline */);

    seedDriveNode("curiosity", 0.8);
    seedFormationMemory("You first saw the painting and couldn't look away", "curiosity");

    enrichedPhase.run(TENANT, List.of());

    var descPrompts = capturedUserPrompts.stream()
                                         .filter(p -> p.contains("curiosity"))
                                         .toList();
    assertThat(descPrompts).isNotEmpty();
    assertThat(descPrompts.getFirst()).contains("Cross-domain emotional patterns");
    assertThat(descPrompts.getFirst()).contains("art");
    assertThat(descPrompts.getFirst()).contains("relationships");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest#promptIncludesDomainActivationWhenAvailable`
Expected: FAIL — constructor doesn't accept DomainActivation yet

- [ ] **Step 3: Add DomainActivation injection and prompt section**

Add `Instance<DomainActivation>` to constructor:

```java
private final DomainActivation domainActivation;  // nullable

@Inject
public DriveDescriptionGenerationPhase(MindMapStore store,
                                        Instance<CognitiveProfile> cognitiveProfileInstance,
                                        Instance<DomainActivation> domainActivationInstance) {
    this.store = store;
    this.cognitiveProfile = cognitiveProfileInstance.isUnsatisfied()
        ? null : cognitiveProfileInstance.get();
    this.domainActivation = domainActivationInstance.isUnsatisfied()
        ? null : domainActivationInstance.get();
}
```

Add method:

```java
private String buildDomainActivationContext(String tenantId, String agentId) {
    if (domainActivation == null) return "";

    var query = DomainActivationQuery.between(
        List.of(), tenantId,
        PrincipalId.of(agentId),
        java.time.Instant.now().minus(java.time.Duration.ofDays(7)),
        java.time.Instant.now());

    var result = domainActivation.correlate(query);
    if (result.isEmpty()) return "";

    var correlations = result.get().correlations();
    if (correlations.isEmpty()) return "";

    var sb = new StringBuilder();
    sb.append("Cross-domain emotional patterns:\n");
    for (var entry : correlations.entrySet()) {
        var pair = entry.getKey();
        var corr = entry.getValue();
        if (corr.strength() == CorrelationStrength.NONE) continue;
        sb.append("  Your emotional responses in \"")
          .append(pair.first()).append("\" and \"")
          .append(pair.second()).append("\" are ")
          .append(corr.strength().name().toLowerCase())
          .append(" correlated\n");
    }
    sb.append("\n");
    return sb.toString();
}
```

Call it from `run()` once per agent (not per drive), append to relational context:

```java
String domainContext = buildDomainActivationContext(tenantId, agentId);
String fullContext = relationalContext + domainContext;
```

Update existing tests' constructor calls to pass `unsatisfiedInstance()` for the new parameter.

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest#promptIncludesDomainActivationWhenAvailable`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhase.java
git add mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhaseTest.java
git commit -m "feat(#732): add domain activation correlation to P22 relational context

Cross-domain DTW correlations (e.g. art ↔ relationships) appear in
drive description prompts. Instance<DomainActivation> for graceful
degradation.

Refs #732"
```

## Batch 2: Config change and skip-logic hash

### Task 3: Disable entityKnowledgeEnabled in CognitionConfig.all() and add relational-context-hash

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java:66`
- Modify: `cognition-api/src/test/java/io/casehub/neocortex/cognition/core/CognitionConfigTest.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhaseTest.java`

**Interfaces:**
- Produces: `CognitionConfig.all()` returns `entityKnowledgeEnabled=false`
- Produces: `relational-context-hash` property on `DriveDescriptionGenerated` nodes for cache invalidation

- [ ] **Step 1: Write the failing test — CognitionConfig.all() entityKnowledgeEnabled is false**

```java
@Test
void allConfigDisablesEntityKnowledge() {
    var config = CognitionConfig.all();
    assertThat(config.entityKnowledgeEnabled()).isFalse();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=CognitionConfigTest#allConfigDisablesEntityKnowledge`
Expected: FAIL — currently returns true

- [ ] **Step 3: Change CognitionConfig.all()**

In `CognitionConfig.java` line 66, change the 17th parameter (entityKnowledgeEnabled) from `true` to `false`:

```java
public static CognitionConfig all() {
    return new CognitionConfig(true, true, true, true, true, true, true, true, true, false, true, true, true, true, true, true, false, false, false, false, false, false, true, true);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=CognitionConfigTest#allConfigDisablesEntityKnowledge`
Expected: PASS

- [ ] **Step 5: Write the failing test — relational-context-hash stored on description nodes**

Add to `DriveDescriptionGenerationPhaseTest`:

```java
@Test
void storesRelationalContextHashOnDescriptionNodes() {
    var mockProfile = org.mockito.Mockito.mock(CognitiveProfile.class);
    org.mockito.Mockito.when(mockProfile.resolve(org.mockito.ArgumentMatchers.any()))
        .thenReturn(java.util.Optional.empty());

    var enrichedPhase = new DriveDescriptionGenerationPhase(
        store, satisfiedInstance(mockProfile), unsatisfiedInstance());
    enrichedPhase.setSessionPipeline(/* same pipeline */);

    seedDriveNode("gallantry", 0.9);
    seedFormationMemory("Your father knelt to help the stranger", "gallantry");

    enrichedPhase.run(TENANT, List.of());

    var desc = findDescriptionNodes().getFirst();
    assertThat(desc.property("relational-context-hash")).isPresent();
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest#storesRelationalContextHashOnDescriptionNodes`
Expected: FAIL — no such property

- [ ] **Step 7: Add hash computation and storage**

In `DriveDescriptionGenerationPhase`, add hash utility:

```java
private static String hashContext(String relationalContext) {
    if (relationalContext == null || relationalContext.isEmpty()) return "";
    return Integer.toHexString(relationalContext.hashCode());
}
```

In `generateAndStore()`, add `relational-context-hash` to the properties map when creating the node:

```java
props.put("relational-context-hash", hashContext(relationalContext));
```

Update the skip logic in `run()` — the `requiredKeys` check now also compares the hash. Before the `describedKeys.containsAll(requiredKeys)` check, verify the hash hasn't changed:

```java
String currentHash = hashContext(relationalContext + domainContext);
boolean hashChanged = allCognitive.stream()
    .filter(n -> n.traits().contains(DESCRIPTION_TRAIT))
    .filter(n -> agentId.equals(n.properties().get("agent-id")))
    .findFirst()
    .map(n -> !currentHash.equals(n.properties().getOrDefault("relational-context-hash", "")))
    .orElse(false);

if (describedKeys.containsAll(requiredKeys) && !hashChanged) {
    LOG.info("Description generation [" + agentIndex + "/" + totalAgents + "]: "
             + agentId + " skipped — descriptions already exist");
    continue;
}
```

- [ ] **Step 8: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest`
Expected: All tests PASS

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=CognitionConfigTest`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java
git add cognition-api/src/test/java/io/casehub/neocortex/cognition/core/CognitionConfigTest.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhase.java
git add mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhaseTest.java
git commit -m "feat(#732): disable EntityKnowledge section, add relational-context-hash

CognitionConfig.all() now returns entityKnowledgeEnabled=false.
Drive description nodes store a relational-context-hash for cache
invalidation when entity knowledge changes.

Closes #732"
```

## Batch 3: Cross-module verification

### Task 4: Verify build and run affected module tests

**Files:**
- No new files — verification only

- [ ] **Step 1: Build the full project**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 2: Run mindmap-intelligence tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: All tests PASS

- [ ] **Step 3: Run cognition-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api`
Expected: All tests PASS

- [ ] **Step 4: Run cognition tests (verify CognitionConfig change doesn't break wiring)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All tests PASS

- [ ] **Step 5: Verify no compilation errors in downstream modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl mindmap-intelligence,cognition-api,cognition`
Expected: BUILD SUCCESS

## References

- [2026-11-02-drive-first-folding-design.md] — design spec this plan implements
- [DriveDescriptionGenerationPhase.java] — P22 consolidation phase (primary modification target)
- [DriveDescriptionGenerationPhaseTest.java] — existing test suite (15 tests)
- [CognitionConfig.java:66] — `all()` factory method
- [CognitiveProfile.java] — entity knowledge resolution service
- [DomainActivation.java] — cross-domain correlation service
- [SocialComparison.java] — static inter-agent perspective comparison
- [era5-relational-cognition-research.md] — architecture decision: fold into drives
- [GitHub #732] — focal issue
- [GitHub #733] — follow-up: richer entity data (depends on this)
