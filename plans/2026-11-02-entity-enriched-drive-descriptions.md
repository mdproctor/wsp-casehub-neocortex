# Entity-Enriched Drive Descriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #733 — Entity-enriched drive descriptions via #721 annotation infrastructure
**Issue group:** #758, #759, #755, #733, #732, #753

**Goal:** Enrich P22 drive descriptions with relationship/reflection memories, MindMap edges, and Theory of Mind (BDI) data per entity, making drive descriptions grounded in specific interactions and beliefs rather than generic relational schemas.

**Architecture:** Expand `buildRelationalContext` to extract more memory domains and edges from EntityKnowledge. Add a `MentalModelLookup` SPI in cognition-api (implemented by MentalModelMemory in cognition) injected into P22 via `Instance<>` for graceful degradation. Add cognition-api as a dependency of mindmap-intelligence (verified: no cycle).

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI Instance<>, cognition-api (new dep)

## Global Constraints

- Java 21 source, Java 26 JVM
- New dependency: mindmap-intelligence → cognition-api (no cycle — verified)
- Barrett somatic register: all prompt text uses discovery verbs, no analytical language
- Token budget: max 5 memories per domain per entity, max 10 edges per entity, max 5 entities

---

## Batch 1: MentalModelLookup SPI and wiring

### Task 1: Create MentalModelLookup SPI in cognition-api and implement in cognition

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelLookup.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelMemory.java` — implement interface
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java` — add NoOp producer
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelLookupTest.java`

**Interfaces:**
- Produces: `MentalModelLookup` SPI — `Optional<MentalModelSnapshot> lookup(String agentId, String subjectId, String tenantId)`
- Produces: `MentalModelMemory implements MentalModelLookup`
- Produces: `@DefaultBean` NoOp producer returning `Optional.empty()`

- [ ] **Step 1: Create MentalModelLookup interface**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.mentalmodel;

import java.util.Optional;

@FunctionalInterface
public interface MentalModelLookup {
    Optional<MentalModelSnapshot> lookup(String agentId, String subjectId, String tenantId);
}
```

- [ ] **Step 2: Make MentalModelMemory implement MentalModelLookup**

Use `ide_edit_member` on the class declaration to add `implements MentalModelLookup`:

```java
public class MentalModelMemory implements MentalModelLookup {
```

The existing `lookup(String agentId, String subjectId, String tenantId)` method already matches the SPI signature. No method changes needed.

- [ ] **Step 3: Add NoOp @DefaultBean producer in CognitionDefaultBeans**

Use `ide_insert_member` to add a producer method:

```java
@Produces @DefaultBean @Singleton
public MentalModelLookup mentalModelLookup() {
    return (agentId, subjectId, tenantId) -> java.util.Optional.empty();
}
```

- [ ] **Step 4: Write test verifying SPI contract**

Create test file `cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelLookupTest.java`:

```java
package io.casehub.neocortex.cognition.mentalmodel;

import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class MentalModelLookupTest {

    @Test
    void noOpLookupReturnsEmpty() {
        MentalModelLookup noOp = (agentId, subjectId, tenantId) -> Optional.empty();
        assertThat(noOp.lookup("agent-1", "subject-1", "tenant-1")).isEmpty();
    }

    @Test
    void mentalModelMemoryImplementsLookup() {
        assertThat(MentalModelLookup.class.isAssignableFrom(MentalModelMemory.class)).isTrue();
    }
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=MentalModelLookupTest`
Expected: PASS

- [ ] **Step 6: Compile cognition-api to verify SPI is clean**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognition-api`
Expected: BUILD SUCCESS

- [ ] **Step 7: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelLookup.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelMemory.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java
git add cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelLookupTest.java
git commit -m "feat(#733): add MentalModelLookup SPI in cognition-api

@FunctionalInterface for per-entity ToM lookup. MentalModelMemory
implements it. @DefaultBean NoOp returns Optional.empty().

Refs #733"
```

## Batch 2: Expand buildRelationalContext with all entity data

### Task 2: Add cognition-api dependency and expand buildRelationalContext

**Files:**
- Modify: `mindmap-intelligence/pom.xml` — add cognition-api dependency
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhase.java` — expand buildRelationalContext, add MentalModelLookup injection
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhaseTest.java` — new tests for expanded context

**Interfaces:**
- Consumes: `MentalModelLookup` SPI from Task 1
- Consumes: `EntityKnowledge.edges()` → `List<MindMapEdge>` — typed relationships
- Consumes: `EntityKnowledge.memories()` — relationship and reflection domains
- Produces: Expanded "Relational context" section in P22 LLM prompt

- [ ] **Step 1: Add cognition-api dependency to mindmap-intelligence pom.xml**

Add to `mindmap-intelligence/pom.xml` dependencies section (non-Java file, use Edit tool):

```xml
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-cognition-api</artifactId>
        </dependency>
```

- [ ] **Step 2: Write failing test — relationship and reflection memories in prompt**

Add to `DriveDescriptionGenerationPhaseTest`:

```java
@Test
void promptIncludesRelationshipAndReflectionMemories() {
    String targetNodeId = store.addNode(
            NodeInput.of("penelope-pitstop", cognitiveSubgraphId)
                     .withProperties(Map.of("type", "person")),
            TENANT);
    var targetNode = store.getNode(targetNodeId, TENANT);

    var relMemory = new Memory("rel-mem-1", "A tense exchange over dinner",
            new MemoryDomain("relationship"), TENANT, AGENT, null,
            Map.of(), java.time.Instant.now(), null, null, null, null);
    var refMemory = new Memory("ref-mem-1", "They avoid conflict when challenged",
            new MemoryDomain("reflection"), TENANT, AGENT, null,
            Map.of(), java.time.Instant.now(), null, null, null, null);

    var entityKnowledge = new EntityKnowledge(
            targetNode, List.of(),
            Map.of(new MemoryDomain("experience"), List.of(),
                   new MemoryDomain("relationship"), List.of(relMemory),
                   new MemoryDomain("reflection"), List.of(refMemory)),
            null, Set.of(), TENANT, null);

    var stubProfile = new CognitiveProfile((MindMapStore) null, null) {
        @Override
        public Optional<EntityKnowledge> resolve(CognitiveProfileQuery query) {
            return Optional.of(entityKnowledge);
        }
    };

    var enrichedPhase = new DriveDescriptionGenerationPhase(
            store, satisfiedInstance(stubProfile), unsatisfiedInstance(), unsatisfiedInstance());
    enrichedPhase.setSessionPipeline(/* same pipeline as setUp */);

    seedDriveNode("gallantry", 0.9);
    seedFormationMemory("Your father knelt to help the stranger", "gallantry");
    seedRelationalSchema(AGENT, "penelope-pitstop", "beloved", "She means everything");

    enrichedPhase.run(TENANT, List.of());

    var descPrompts = capturedUserPrompts.stream()
                                         .filter(p -> p.contains("gallantry"))
                                         .toList();
    assertThat(descPrompts).isNotEmpty();
    assertThat(descPrompts.getFirst()).contains("tense exchange over dinner");
    assertThat(descPrompts.getFirst()).contains("avoid conflict");
}
```

Note: The constructor gains a 4th parameter `Instance<MentalModelLookup>`. Update the @Inject constructor and all existing test constructor calls accordingly.

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest#promptIncludesRelationshipAndReflectionMemories`
Expected: FAIL — constructor doesn't accept MentalModelLookup yet, or prompt doesn't include relationship/reflection memories

- [ ] **Step 4: Implement the expansion**

Update `DriveDescriptionGenerationPhase`:

**4a.** Add MentalModelLookup import and field:

```java
import io.casehub.neocortex.cognition.mentalmodel.MentalModelLookup;
import io.casehub.neocortex.cognition.mentalmodel.MentalModelSnapshot;
import io.casehub.neocortex.cognition.mentalmodel.AttributedState;

private final MentalModelLookup mentalModelLookup;
```

**4b.** Update @Inject constructor to accept 4th param:

```java
@Inject
public DriveDescriptionGenerationPhase(MindMapStore store,
                                        Instance<CognitiveProfile> cognitiveProfileInstance,
                                        Instance<DomainActivation> domainActivationInstance,
                                        Instance<MentalModelLookup> mentalModelLookupInstance) {
    this.store = store;
    this.cognitiveProfile = cognitiveProfileInstance.isUnsatisfied()
        ? null : cognitiveProfileInstance.get();
    this.domainActivation = domainActivationInstance.isUnsatisfied()
        ? null : domainActivationInstance.get();
    this.mentalModelLookup = mentalModelLookupInstance.isUnsatisfied()
        ? null : mentalModelLookupInstance.get();
}
```

**4c.** Update package-private constructor:

```java
DriveDescriptionGenerationPhase(MindMapStore store) {
    this.store = store;
    this.cognitiveProfile = null;
    this.domainActivation = null;
    this.mentalModelLookup = null;
}
```

**4d.** Add `MAX_EDGES = 10` constant.

**4e.** Expand `buildRelationalContext` to include relationship, reflection memories, edges, and ToM. Replace the method body:

After the experience memories section, add:

```java
// Relationship memories
var relationshipMemories = ek.memories().getOrDefault(
    new MemoryDomain("relationship"), List.of());
if (!relationshipMemories.isEmpty()) {
    sb.append("  How interactions have gone:\n");
    for (var mem : relationshipMemories.subList(0, Math.min(relationshipMemories.size(), MEMORY_LIMIT))) {
        sb.append("    - ").append(mem.text()).append("\n");
    }
}

// Reflection memories
var reflectionMemories = ek.memories().getOrDefault(
    new MemoryDomain("reflection"), List.of());
if (!reflectionMemories.isEmpty()) {
    sb.append("  Insights about them:\n");
    for (var mem : reflectionMemories.subList(0, Math.min(reflectionMemories.size(), MEMORY_LIMIT))) {
        sb.append("    - ").append(mem.text()).append("\n");
    }
}

// Edges
var edges = ek.edges();
if (!edges.isEmpty()) {
    sb.append("  Connections:\n");
    int edgeCount = 0;
    for (var edge : edges) {
        if (edgeCount >= MAX_EDGES) break;
        sb.append("    - ").append(edge.edgeType())
          .append(" → ").append(edge.targetNodeId()).append("\n");
        edgeCount++;
    }
}

// Theory of Mind
if (mentalModelLookup != null) {
    try {
        var snapshot = mentalModelLookup.lookup(agentId, targetId, tenantId);
        if (snapshot.isPresent()) {
            var tom = snapshot.get();
            if (!tom.beliefs().isEmpty() || !tom.desires().isEmpty() || !tom.intentions().isEmpty()) {
                sb.append("  What you think about them:\n");
                if (!tom.beliefs().isEmpty()) {
                    sb.append("    Beliefs: ");
                    sb.append(tom.beliefs().stream()
                        .map(b -> b.description() + " (confidence: " + String.format("%.1f", b.confidence()) + ")")
                        .collect(java.util.stream.Collectors.joining(", ")));
                    sb.append("\n");
                }
                if (!tom.desires().isEmpty()) {
                    sb.append("    Desires: ");
                    sb.append(tom.desires().stream()
                        .map(d -> d.description() + " (confidence: " + String.format("%.1f", d.confidence()) + ")")
                        .collect(java.util.stream.Collectors.joining(", ")));
                    sb.append("\n");
                }
                if (!tom.intentions().isEmpty()) {
                    sb.append("    Intentions: ");
                    sb.append(tom.intentions().stream()
                        .map(i -> i.description() + " (confidence: " + String.format("%.1f", i.confidence()) + ")")
                        .collect(java.util.stream.Collectors.joining(", ")));
                    sb.append("\n");
                }
            }
        }
    } catch (Exception e) {
        LOG.log(Level.FINE, "ToM lookup skipped for " + targetId + ": " + e.getMessage());
    }
}
```

Note: `agentId` is not currently a parameter of `buildRelationalContext`. Add it — change the method signature to `buildRelationalContext(String tenantId, String agentId, List<MindMapNode> agentSchemas)` and update the caller in `run()`.

**4f.** Also rename existing "Recent memories" to "Experiences with them" for consistency.

- [ ] **Step 5: Update all constructor calls in tests**

All existing `DriveDescriptionGenerationPhase(store, ..., unsatisfiedInstance())` calls need the 4th `unsatisfiedInstance()` parameter. Update setUp, skipsWhenNoSessionPipeline, and the enriched tests.

- [ ] **Step 6: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest#promptIncludesRelationshipAndReflectionMemories`
Expected: PASS

- [ ] **Step 7: Write test — ToM data appears in prompt when MentalModelLookup available**

```java
@Test
void promptIncludesTomWhenMentalModelLookupAvailable() {
    // Setup entity knowledge with stub CognitiveProfile (same as other tests)
    // Setup MentalModelLookup returning a MentalModelSnapshot with beliefs

    var snapshot = new MentalModelSnapshot(
            AGENT, "penelope-pitstop", TENANT,
            List.of(new AttributedState("trustworthy", "they are trustworthy", 0.9, 1,
                    java.time.Instant.now(), BdiDimension.BELIEF)),
            List.of(), List.of(),
            java.time.Instant.now(), null, java.time.Instant.now());

    MentalModelLookup stubLookup = (agentId, subjectId, tenantId) ->
            "penelope-pitstop".equals(subjectId) ? Optional.of(snapshot) : Optional.empty();

    var enrichedPhase = new DriveDescriptionGenerationPhase(
            store, satisfiedInstance(stubProfile), unsatisfiedInstance(), satisfiedInstance(stubLookup));
    // ... setup pipeline, seed data, run, assert prompt contains "trustworthy"
}
```

- [ ] **Step 8: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=DriveDescriptionGenerationPhaseTest`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add mindmap-intelligence/pom.xml
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhase.java
git add mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/DriveDescriptionGenerationPhaseTest.java
git commit -m "feat(#733): expand buildRelationalContext with relationship, reflection, edges, ToM

Adds relationship-domain memories, reflection-domain memories, MindMap
edges, and MentalModelLookup BDI data to P22 drive description prompts.
cognition-api dependency added (no cycle).

Closes #733"
```

## Batch 3: Cross-module verification

### Task 3: Verify build across affected modules

**Files:**
- No new files — verification only

- [ ] **Step 1: Full compile**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognition-api,cognition,mindmap-intelligence`
Expected: BUILD SUCCESS

- [ ] **Step 2: Run cognition tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: All tests PASS

- [ ] **Step 3: Run mindmap-intelligence tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: All tests PASS

## References

- [2026-11-02-entity-enriched-drive-descriptions-design.md] — design spec this plan implements
- [2026-11-02-drive-first-folding-design.md] — #732 design (plumbing this extends)
- [DriveDescriptionGenerationPhase.java] — P22 with buildRelationalContext
- [MentalModelSnapshot.java] — BDI value type
- [MentalModelMemory.java] — store class (implements new SPI)
- [AttributedState.java] — BDI state record
- [EntityKnowledge.java] — entity data with edges + multi-domain memories
- [CognitionDefaultBeans.java] — NoOp bean producers
- [GitHub #733] — focal issue
- [GitHub #732] — plumbing issue (done)
