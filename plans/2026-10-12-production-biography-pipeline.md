# Production Biography Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #551 — Epic: Production-quality biography extraction pipeline
**Issue group:** #551

**Goal:** Bridge the Python extraction pipeline to the Java cognitive engine by building a corpus-to-YAML converter, extending Java entry types, adding new handlers, and validating round-trip import integrity.

**Architecture:** A Python converter (`convert_corpus.py`) transforms `corpus.json` into typed YAML files. The Java `memory-seeding` module is extended with new entry fields, three new handler types, and a universal `associations` mechanism. A post-import validation step confirms round-trip integrity.

**Tech Stack:** Python 3 (converter, validation), Java 21 (entry types, handlers), Jackson YAML, Quarkus CDI, JUnit 5

## Global Constraints

- Java 21 source on Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build: `mvn` not `./mvnw`
- All entry records use `@JsonIgnoreProperties(ignoreUnknown = true)` for backward compatibility
- All handlers are `@ApplicationScoped` CDI beans
- All handlers store `provenance: "biographical-import"` and `template-ref` on created artifacts
- All new fields are optional — existing YAML without them continues to work
- Python scripts in `extraction/scripts/`, no external deps beyond PyYAML (already in requirements.txt)
- Every commit references `Refs #551`

---

## Batch 1: Java Entry Extensions — GoalEntry and Association

Extends GoalEntry with taxonomy fields and adds the universal `Association` record and `associations` field to all MindMap-writing entry types. After this batch, existing handler tests still pass and the YAML schema supports the new fields.

### Task 1: Extend GoalEntry with taxonomy fields

**Files:**
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalHandler.java`
- Modify: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/GoalHandlerTest.java`

**Interfaces:**
- Consumes: `GoalEntry` (existing record), `GoalHandler` (existing handler)
- Produces: Extended `GoalEntry` with `status`, `urgency`, `needTier`, `priority`, `feasibility`, `contentDomain`, `contentSubdomain`, `motivationOrigin`, `clarity`, `evidenceBasis` fields

- [ ] **Step 1: Write failing test for new GoalEntry fields**

Add a test that creates a GoalEntry with the new taxonomy fields and verifies GoalHandler stores them as node properties.

```java
@Test
void goalWithTaxonomyFields() {
    var entry = new GoalEntry(
        "goal-1", null, "INFERRED", "Test Goal",
        "thematic", "long", "active", 0.85, "SELF_EXPRESSION",
        0.9, 0.8, "health", "health", "identified", 0.85, "biographical evidence",
        null, new GoalEntry.PadValues(0.5, 0.3, 0.7), null);
    var profile = profileWith(entry);

    handler.handle(profile, AGENT, TENANT);

    var node = store.resolveNode("Test Goal", goalSubgraphId(), TENANT);
    assertNotNull(node);
    assertEquals("active", node.properties().get("status"));
    assertEquals("0.85", node.properties().get("urgency"));
    assertEquals("SELF_EXPRESSION", node.properties().get("need-tier"));
    assertEquals("0.9", node.properties().get("priority"));
    assertEquals("0.8", node.properties().get("feasibility"));
    assertEquals("health", node.properties().get("content-domain"));
    assertEquals("health", node.properties().get("content-subdomain"));
    assertEquals("identified", node.properties().get("motivation-origin"));
    assertEquals("0.85", node.properties().get("clarity"));
    assertEquals("biographical evidence", node.properties().get("evidence-basis"));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=GoalHandlerTest#goalWithTaxonomyFields`
Expected: Compilation error — GoalEntry constructor doesn't match

- [ ] **Step 3: Extend GoalEntry record**

```java
@JsonIgnoreProperties(ignoreUnknown = true)
public record GoalEntry(
    String id,
    @JsonProperty("source_ref") String sourceRef,
    @JsonProperty("confidence_origin") String confidenceOrigin,
    String name,
    String tier,
    String horizon,
    GoalTaxonomy taxonomy,
    List<Dependency> dependencies,
    PadValues pad,
    @JsonProperty("sub_goals") List<SubGoal> subGoals
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record GoalTaxonomy(
        String status, Double urgency,
        @JsonProperty("need_tier") String needTier,
        Double priority, Double feasibility,
        @JsonProperty("content_domain") String contentDomain,
        @JsonProperty("content_subdomain") String contentSubdomain,
        @JsonProperty("motivation_origin") String motivationOrigin,
        Double clarity,
        @JsonProperty("evidence_basis") String evidenceBasis
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Dependency(String ref, @JsonProperty("edge_type") String edgeType) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record SubGoal(String id, String tier, String description) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record PadValues(Double pleasure, Double arousal, Double dominance) {}
}
```

NOTE: The 10 taxonomy fields are grouped into a `GoalTaxonomy` nested record to avoid a 19-parameter constructor. In YAML this nests under a `taxonomy:` key.

- [ ] **Step 4: Update GoalHandler to store new fields**

In `GoalHandler.handle()`, after the existing `tier`/`horizon` property lines, add:

```java
if (entry.taxonomy() != null) {
    var t = entry.taxonomy();
    if (t.status() != null) props.put("status", t.status());
    if (t.urgency() != null) props.put("urgency", String.valueOf(t.urgency()));
    if (t.needTier() != null) props.put("need-tier", t.needTier());
    if (t.priority() != null) props.put("priority", String.valueOf(t.priority()));
    if (t.feasibility() != null) props.put("feasibility", String.valueOf(t.feasibility()));
    if (t.contentDomain() != null) props.put("content-domain", t.contentDomain());
    if (t.contentSubdomain() != null) props.put("content-subdomain", t.contentSubdomain());
    if (t.motivationOrigin() != null) props.put("motivation-origin", t.motivationOrigin());
    if (t.clarity() != null) props.put("clarity", String.valueOf(t.clarity()));
    if (t.evidenceBasis() != null) props.put("evidence-basis", t.evidenceBasis());
}
```

- [ ] **Step 5: Fix any existing GoalEntry constructor call sites**

Search for existing `new GoalEntry(` calls in tests and update them to include the new fields (pass `null` for each new parameter to preserve existing behavior).

- [ ] **Step 6: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=GoalHandlerTest`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalEntry.java memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalHandler.java memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/GoalHandlerTest.java
git commit -m "feat(#551): extend GoalEntry with taxonomy fields

Add status, urgency, need_tier, priority, feasibility, content_domain,
content_subdomain, motivation_origin, clarity, evidence_basis.
GoalHandler stores them as node properties.

Refs #551"
```

### Task 2: Add Association record and universal associations to entry types

**Files:**
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/Association.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/RelationshipEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BeliefEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ActivityEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ProjectEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/CulturalContextEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/AssociationProcessor.java`
- Modify: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/GoalHandlerTest.java`

**Interfaces:**
- Consumes: Entry types from Task 1
- Produces: `Association` record (`entityRef`, `edgeType`, `confidence`), `AssociationProcessor.process()` static method, `associations` field on all MindMap-writing entry types

- [ ] **Step 1: Write failing test for GoalEntry with associations**

```java
@Test
void goalWithAssociations() {
    var assoc = new Association("La Casa Azul", "associated-with", 0.8);
    var entry = new GoalEntry(
        "goal-assoc", null, null, "Goal With Place",
        null, null, null, null, null, null, null, null, null, null, null, null,
        null, null, null, List.of(assoc));
    var profile = profileWith(entry);

    // Create a place node for the association target
    var placeSubgraph = BiographyUtils.ensureSubgraph(store, SubgraphTypes.PLACE, TENANT);
    store.addNode(NodeInput.of("La Casa Azul", placeSubgraph), TENANT);

    handler.handle(profile, AGENT, TENANT);

    var goalNode = store.resolveNode("Goal With Place", goalSubgraphId(), TENANT);
    var edges = store.getEdges(goalNode.id(), TENANT);
    assertTrue(edges.stream().anyMatch(e ->
        e.type().equals("associated-with") && e.targetId() != null));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=GoalHandlerTest#goalWithAssociations`
Expected: Compilation error — Association class doesn't exist, GoalEntry constructor mismatch

- [ ] **Step 3: Create Association record**

```java
package io.casehub.neocortex.memory.seeding.biography;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

@JsonIgnoreProperties(ignoreUnknown = true)
public record Association(
    @JsonProperty("entity_ref") String entityRef,
    @JsonProperty("edge_type") String edgeType,
    Double confidence
) {}
```

- [ ] **Step 4: Create AssociationProcessor utility**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.mindmap.EdgeInput;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;

import java.time.Instant;
import java.util.List;

public final class AssociationProcessor {

    private AssociationProcessor() {}

    public static void process(List<Association> associations, String sourceNodeId,
                               MindMapStore store, String tenantId) {
        if (associations == null) return;
        for (var assoc : associations) {
            String targetId = resolveAcrossSubgraphs(assoc.entityRef(), store, tenantId);
            if (targetId == null) continue;
            var edge = EdgeInput.of(sourceNodeId, targetId, assoc.edgeType())
                .withProvenance("biographical-import");
            if (assoc.confidence() != null) {
                edge = edge.withConfidence(
                    new Confidence(ConfidenceOrigin.STATED, assoc.confidence(), Instant.now()));
            }
            store.addEdge(edge, tenantId);
        }
    }

    static String resolveAcrossSubgraphs(String name, MindMapStore store, String tenantId) {
        for (var sg : store.listSubgraphs(tenantId)) {
            MindMapNode node = store.resolveNode(name, sg.id(), tenantId);
            if (node != null) return node.id();
        }
        return null;
    }
}
```

- [ ] **Step 5: Add `associations` field to GoalEntry and remaining entry types**

Add `List<Association> associations` as the last parameter to GoalEntry, RelationshipEntry, BeliefEntry, ActivityEntry, ProjectEntry, CulturalContextEntry records. PlaceEntry already has its own `associations` field — leave it unchanged.

For GoalEntry:
```java
@JsonIgnoreProperties(ignoreUnknown = true)
public record GoalEntry(
    // ... existing fields ...
    @JsonProperty("sub_goals") List<SubGoal> subGoals,
    List<Association> associations   // NEW — last field
) { /* inner records unchanged */ }
```

Apply the same pattern to RelationshipEntry, BeliefEntry, ActivityEntry, ProjectEntry, CulturalContextEntry — add `List<Association> associations` as the last constructor parameter.

- [ ] **Step 6: Update GoalHandler to process associations**

After the existing `dependencies` processing block in `GoalHandler.handle()`, add:

```java
AssociationProcessor.process(entry.associations(), goalId, store, tenantId);
```

Also refactor `GoalHandler.resolveAcrossSubgraphs()` to delegate to `AssociationProcessor.resolveAcrossSubgraphs()` to avoid duplication.

- [ ] **Step 7: Fix existing constructor call sites**

Update all existing `new GoalEntry(...)`, `new RelationshipEntry(...)`, etc. calls in tests to pass `null` for the new `associations` parameter.

- [ ] **Step 8: Run all memory-seeding tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding`
Expected: All tests PASS

- [ ] **Step 9: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/Association.java memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/AssociationProcessor.java memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/
git commit -m "feat(#551): add Association record and universal associations

Association(entityRef, edgeType, confidence) added to GoalEntry,
RelationshipEntry, BeliefEntry, ActivityEntry, ProjectEntry, and
CulturalContextEntry. AssociationProcessor handles cross-subgraph
edge resolution for all handlers.

Refs #551"
```

---

## Batch 2: New Handlers — Organisation, EntityEnrichment, DispositionProfile

Adds three new entry types and handlers. After this batch, BiographyImportRunner can process all 13 entry types across the full layer ordering.

### Task 3: OrganisationEntry and OrganisationHandler

**Files:**
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/OrganisationEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/OrganisationHandler.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyTemplateTypes.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyProfile.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyLoader.java`
- Create: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/OrganisationHandlerTest.java`

**Interfaces:**
- Consumes: `BiographyTemplateTypes.layerFor()`, `BiographyUtils.ensureSubgraph()`, `AssociationProcessor.process()`, `PlaceHandler.resolveOrigin()`
- Produces: `OrganisationEntry` record, `OrganisationHandler` CDI bean at layer 4

- [ ] **Step 1: Write failing test for OrganisationHandler**

```java
@ExtendWith(MockitoExtension.class)
class OrganisationHandlerTest {

    private InMemoryMindMapStore store;
    private OrganisationHandler handler;
    private static final String AGENT = "test-agent";
    private static final String TENANT = "test-tenant";

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        handler = new OrganisationHandler(store);
    }

    @Test
    void createsOrganisationNode() {
        var entry = new OrganisationEntry(
            "org-1", null, "STATED", "Los Cachuchas",
            List.of("Organisational"),
            Map.of("type", "student group", "city", "Mexico City"),
            new OrganisationEntry.PadValues(0.7, 0.6, 0.5),
            null, "1920~", null);
        var profile = profileWith(entry);

        handler.handle(profile, AGENT, TENANT);

        var node = store.resolveNode("Los Cachuchas", orgSubgraphId(), TENANT);
        assertNotNull(node);
        assertEquals("student group", node.properties().get("type"));
        assertEquals("Mexico City", node.properties().get("city"));
        assertTrue(node.traits().contains("Organisational"));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=OrganisationHandlerTest`
Expected: Compilation error — classes don't exist

- [ ] **Step 3: Add ORGANISATION constant to BiographyTemplateTypes**

```java
public static final String ORGANISATION = "organisation";
```

In the `layerFor()` switch, add: `case ORGANISATION -> 4;`

NOTE: `BiographyTemplateTypes.LAYER_MAP` uses `Map.of()` which supports max 10 entries. When adding the 11th entry, switch to `Map.ofEntries(Map.entry(k, v), ...)` format. Do this now for ORGANISATION (11th entry), and the pattern will be ready for Task 4's additions.

- [ ] **Step 4: Create OrganisationEntry**

```java
package io.casehub.neocortex.memory.seeding.biography;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record OrganisationEntry(
    String id,
    @JsonProperty("source_ref") String sourceRef,
    @JsonProperty("confidence_origin") String confidenceOrigin,
    String name,
    List<String> traits,
    Map<String, String> properties,
    PadValues pad,
    List<Association> associations,
    @JsonProperty("valid_from") String validFrom,
    @JsonProperty("valid_until") String validUntil
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record PadValues(Double pleasure, Double arousal, Double dominance) {}
}
```

- [ ] **Step 5: Create OrganisationHandler**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.time.Instant;
import java.util.HashMap;
import java.util.Set;

@ApplicationScoped
public class OrganisationHandler implements BiographyHandler {

    private final MindMapStore store;

    @Inject
    public OrganisationHandler(MindMapStore store) { this.store = store; }

    @Override public Set<String> handledTypes() { return Set.of(BiographyTemplateTypes.ORGANISATION); }

    @Override
    public void handle(BiographyProfile profile, String agentId, String tenantId) {
        String subgraphId = BiographyUtils.ensureSubgraph(store, SubgraphTypes.ORGANISATION, tenantId);

        for (var entry : profile.organisations()) {
            MindMapNode existing = store.resolveNode(entry.name(), subgraphId, tenantId);
            if (existing != null) continue;

            var props = new HashMap<String, String>();
            props.put("provenance", "biographical-import");
            props.put("template-ref", "organisations.yaml#" + entry.id());
            if (entry.sourceRef() != null) props.put("source-ref", entry.sourceRef());
            if (entry.properties() != null) props.putAll(entry.properties());

            var origin = PlaceHandler.resolveOrigin(entry.confidenceOrigin());
            var input = NodeInput.of(entry.name(), subgraphId)
                .withConfidence(new Confidence(origin, 0.8, Instant.now()))
                .withProvenance("biographical-import")
                .withProperties(props);

            if (entry.traits() != null) {
                for (String trait : entry.traits()) {
                    input = input.withTrait(trait);
                }
            }
            if (entry.pad() != null) {
                input = input.withPad(entry.pad().pleasure(), entry.pad().arousal(), entry.pad().dominance());
            }
            if (entry.validFrom() != null) props.put("valid-from", entry.validFrom());
            if (entry.validUntil() != null) props.put("valid-until", entry.validUntil());

            String nodeId = store.addNode(input, tenantId);
            AssociationProcessor.process(entry.associations(), nodeId, store, tenantId);
        }
    }
}
```

- [ ] **Step 6: Update BiographyProfile to include organisations**

Add `List<OrganisationEntry> organisations` field to the BiographyProfile record. Add null-coalesce in the compact constructor.

- [ ] **Step 7: Update BiographyLoader to handle organisation type**

Add `OrganisationFile` record and `case BiographyTemplateTypes.ORGANISATION ->` in `loadFile()`. Add `List<OrganisationEntry> or` parameter threading.

- [ ] **Step 8: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=OrganisationHandlerTest`
Expected: PASS

- [ ] **Step 9: Run all memory-seeding tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding`
Expected: All tests PASS

- [ ] **Step 10: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/
git commit -m "feat(#551): add OrganisationEntry and OrganisationHandler

New type 'organisation' at layer 4 writes to ORGANISATION subgraph.
Supports name, traits, properties, PAD, associations, temporal validity.

Refs #551"
```

### Task 4: EntityEnrichmentEntry and DispositionProfileEntry with handlers

**Files:**
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/EntityEnrichmentEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/EntityEnrichmentHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/DispositionProfileEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/DispositionProfileHandler.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyTemplateTypes.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyProfile.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyLoader.java`
- Create: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/EntityEnrichmentHandlerTest.java`
- Create: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/DispositionProfileHandlerTest.java`

**Interfaces:**
- Consumes: `MindMapStore`, `AssociationProcessor.resolveAcrossSubgraphs()`, `BiographyTemplateTypes`
- Produces: `EntityEnrichmentEntry` (drive baselines, CAPS patterns, behavioural attractors), `EntityEnrichmentHandler` at layer 7, `DispositionProfileEntry` (disposition axes), `DispositionProfileHandler` at layer 7

- [ ] **Step 1: Write failing test for EntityEnrichmentHandler**

```java
@Test
void storesDriveBaselinesOnEntityNode() {
    // Pre-create the entity node
    var personSubgraph = BiographyUtils.ensureSubgraph(store, SubgraphTypes.PERSON, TENANT);
    store.addNode(NodeInput.of("Frida Kahlo", personSubgraph)
        .withProvenance("biographical-import"), TENANT);

    var baselines = Map.of(
        "curiosity", new EntityEnrichmentEntry.DriveBaseline(0.85, "Strong exploration"),
        "competence", new EntityEnrichmentEntry.DriveBaseline(0.88, "High skill drive"));
    var entry = new EntityEnrichmentEntry("enrich-1", "Frida Kahlo", baselines, null, null, null);
    var profile = profileWith(entry);

    handler.handle(profile, AGENT, TENANT);

    var node = store.resolveNode("Frida Kahlo", personSubgraph, TENANT);
    assertEquals("0.85", node.properties().get("drive-baseline-curiosity"));
    assertEquals("Strong exploration", node.properties().get("drive-baseline-curiosity-justification"));
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: Compilation error — EntityEnrichmentEntry doesn't exist

- [ ] **Step 3: Create EntityEnrichmentEntry**

```java
package io.casehub.neocortex.memory.seeding.biography;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record EntityEnrichmentEntry(
    String id,
    @JsonProperty("entity_ref") String entityRef,
    @JsonProperty("drive_baselines") Map<String, DriveBaseline> driveBaselines,
    @JsonProperty("caps_patterns") List<CapsPattern> capsPatterns,
    @JsonProperty("behavioural_attractors") List<BehaviouralAttractor> behaviouralAttractors,
    @JsonProperty("relationship_stages") List<RelationshipStage> relationshipStages
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record DriveBaseline(Double baseline, String justification) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record CapsPattern(String pattern, Double frequency) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record BehaviouralAttractor(String name, String description) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record RelationshipStage(
        @JsonProperty("other_agent") String otherAgent,
        List<Transition> transitions
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Transition(String from, String to, String period) {}
}
```

- [ ] **Step 4: Create EntityEnrichmentHandler**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeUpdate;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.util.HashMap;
import java.util.Set;

@ApplicationScoped
public class EntityEnrichmentHandler implements BiographyHandler {

    private final MindMapStore store;

    @Inject
    public EntityEnrichmentHandler(MindMapStore store) { this.store = store; }

    @Override public Set<String> handledTypes() { return Set.of(BiographyTemplateTypes.ENTITY_ENRICHMENT); }

    @Override
    public void handle(BiographyProfile profile, String agentId, String tenantId) {
        for (var entry : profile.entityEnrichments()) {
            String nodeId = AssociationProcessor.resolveAcrossSubgraphs(entry.entityRef(), store, tenantId);
            if (nodeId == null) continue;

            var props = new HashMap<String, String>();

            if (entry.driveBaselines() != null) {
                for (var e : entry.driveBaselines().entrySet()) {
                    props.put("drive-baseline-" + e.getKey(), String.valueOf(e.getValue().baseline()));
                    if (e.getValue().justification() != null) {
                        props.put("drive-baseline-" + e.getKey() + "-justification", e.getValue().justification());
                    }
                }
            }

            if (entry.capsPatterns() != null) {
                props.put("caps-pattern-count", String.valueOf(entry.capsPatterns().size()));
                for (int i = 0; i < entry.capsPatterns().size(); i++) {
                    var p = entry.capsPatterns().get(i);
                    props.put("caps-pattern-" + i + "-pattern", p.pattern());
                    if (p.frequency() != null) {
                        props.put("caps-pattern-" + i + "-frequency", String.valueOf(p.frequency()));
                    }
                }
            }

            if (entry.behaviouralAttractors() != null) {
                props.put("behavioural-attractor-count", String.valueOf(entry.behaviouralAttractors().size()));
                for (int i = 0; i < entry.behaviouralAttractors().size(); i++) {
                    var a = entry.behaviouralAttractors().get(i);
                    props.put("behavioural-attractor-" + i + "-name", a.name());
                    if (a.description() != null) {
                        props.put("behavioural-attractor-" + i + "-description", a.description());
                    }
                }
            }

            store.updateNode(nodeId, NodeUpdate.of().withProperties(props), tenantId);
        }
    }
}
```

- [ ] **Step 5: Create DispositionProfileEntry**

```java
package io.casehub.neocortex.memory.seeding.biography;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record DispositionProfileEntry(
    String id,
    @JsonProperty("entity_ref") String entityRef,
    Map<String, AxisValue> axes
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record AxisValue(Double score, String justification) {}
}
```

- [ ] **Step 6: Create DispositionProfileHandler**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeUpdate;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.util.HashMap;
import java.util.Set;

@ApplicationScoped
public class DispositionProfileHandler implements BiographyHandler {

    private final MindMapStore store;

    @Inject
    public DispositionProfileHandler(MindMapStore store) { this.store = store; }

    @Override public Set<String> handledTypes() { return Set.of(BiographyTemplateTypes.DISPOSITION_PROFILE); }

    @Override
    public void handle(BiographyProfile profile, String agentId, String tenantId) {
        for (var entry : profile.dispositionProfiles()) {
            String nodeId = AssociationProcessor.resolveAcrossSubgraphs(entry.entityRef(), store, tenantId);
            if (nodeId == null) continue;

            var props = new HashMap<String, String>();
            if (entry.axes() != null) {
                for (var e : entry.axes().entrySet()) {
                    props.put("disposition-" + e.getKey(), String.valueOf(e.getValue().score()));
                    if (e.getValue().justification() != null) {
                        props.put("disposition-" + e.getKey() + "-justification", e.getValue().justification());
                    }
                }
            }

            store.updateNode(nodeId, NodeUpdate.of().withProperties(props), tenantId);
        }
    }
}
```

- [ ] **Step 7: Update BiographyTemplateTypes with new constants**

```java
public static final String ENTITY_ENRICHMENT = "entity-enrichment";
public static final String DISPOSITION_PROFILE = "disposition-profile";
```

In `layerFor()`: `case ENTITY_ENRICHMENT, DISPOSITION_PROFILE -> 7;`

- [ ] **Step 8: Update BiographyProfile and BiographyLoader**

Add `List<EntityEnrichmentEntry> entityEnrichments` and `List<DispositionProfileEntry> dispositionProfiles` to BiographyProfile. Update BiographyLoader with new file records and switch cases.

- [ ] **Step 9: Write DispositionProfileHandler test**

```java
@Test
void storesDispositionAxesOnEntityNode() {
    var personSubgraph = BiographyUtils.ensureSubgraph(store, SubgraphTypes.PERSON, TENANT);
    store.addNode(NodeInput.of("Frida Kahlo", personSubgraph)
        .withProvenance("biographical-import"), TENANT);

    var axes = Map.of(
        "socialOrient", new DispositionProfileEntry.AxisValue(0.7, "Warm but selective"),
        "ruleFollowing", new DispositionProfileEntry.AxisValue(0.25, "Defiant"));
    var entry = new DispositionProfileEntry("disp-1", "Frida Kahlo", axes);
    var profile = profileWith(entry);

    handler.handle(profile, AGENT, TENANT);

    var node = store.resolveNode("Frida Kahlo", personSubgraph, TENANT);
    assertEquals("0.7", node.properties().get("disposition-socialOrient"));
    assertEquals("0.25", node.properties().get("disposition-ruleFollowing"));
}
```

- [ ] **Step 10: Run all memory-seeding tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding`
Expected: All tests PASS

- [ ] **Step 11: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/
git commit -m "feat(#551): add EntityEnrichment and DispositionProfile handlers

Layer 7 handlers store drive baselines, CAPS patterns, behavioural
attractors, and disposition axes as MindMap node properties.

Refs #551"
```

---

## Batch 3: LifeEventEntry Extensions

Extends LifeEventEntry with memory enrichment fields and updates LifeEventHandler to store them as attributes. After this batch, the full corpus memory data can be round-tripped through YAML.

### Task 5: Extend LifeEventEntry with enrichment fields

**Files:**
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/LifeEventEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/LifeEventHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/EnrichmentAttributeKeys.java`
- Modify: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/LifeEventHandlerTest.java`

**Interfaces:**
- Consumes: `LifeEventEntry` (existing), `LifeEventHandler` (existing), `SubThoughtAttributeKeys` pattern
- Produces: Extended `LifeEventEntry` with `domain`, `eventType`, `subject`, `period`, `relatedEntities`, `occEmotions`, `secAppraisal`, `actionTendencies`, `cognitiveDistortions`, `driveImpact`, `capsInputs`, `goalImpacts`, `habituation`, `gutFeeling`. `EnrichmentAttributeKeys` constants class.

- [ ] **Step 1: Write failing test for enriched life event**

```java
@Test
void storesEnrichmentAttributes() {
    var occ = List.of(new LifeEventEntry.OccEmotion("pride", 0.5, "ATTRIBUTED"));
    var sec = new LifeEventEntry.SecAppraisal(0.95, 0.2, 0.0, 0.7, 0.0, 0.0, 0.5, 0.8);
    var tendencies = List.of(new LifeEventEntry.ActionTendency("approach", 0.7));
    var drive = new LifeEventEntry.DriveImpact(0.3, 0.1, 0.4, -0.2);

    var entry = new LifeEventEntry(
        "le-enriched", null, "STATED", "1907", "Born in La Casa Azul",
        "experience", "observation", "Frida Kahlo", "1907",
        List.of("Guillermo Kahlo"),
        new LifeEventEntry.PadValues(0.6, 0.3, 0.4),
        occ, sec, tendencies, null, drive, null, null, null, null,
        null, null);
    var profile = profileWith(entry);

    handler.handle(profile, AGENT, TENANT);

    // Verify stored - retrieve via scan
    var memories = memoryStore.scan(
        MemoryScanRequest.of(Subject.of("agent", AGENT), "experience", TENANT));
    assertFalse(memories.isEmpty());
    var m = memories.get(0);
    assertEquals("observation", m.attributes().get("event-type"));
    assertEquals("Frida Kahlo", m.attributes().get("subject"));
    assertEquals("pride", m.attributes().get(EnrichmentAttributeKeys.occEmotionType(0)));
    assertEquals("0.5", m.attributes().get(EnrichmentAttributeKeys.occEmotionIntensity(0)));
    assertEquals("0.95", m.attributes().get(EnrichmentAttributeKeys.SEC_RELEVANCE));
    assertEquals("0.3", m.attributes().get(EnrichmentAttributeKeys.DRIVE_CURIOSITY));
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: Compilation error — new types don't exist

- [ ] **Step 3: Create EnrichmentAttributeKeys**

```java
package io.casehub.neocortex.memory.seeding.biography;

public final class EnrichmentAttributeKeys {

    private EnrichmentAttributeKeys() {}

    // OCC emotions (indexed)
    public static final String OCC_EMOTION_COUNT = "occ-emotion-count";
    public static String occEmotionType(int i) { return "occ-emotion-" + i + "-type"; }
    public static String occEmotionIntensity(int i) { return "occ-emotion-" + i + "-intensity"; }
    public static String occEmotionSource(int i) { return "occ-emotion-" + i + "-source"; }

    // SEC appraisal (flat)
    public static final String SEC_RELEVANCE = "sec-relevance";
    public static final String SEC_NOVELTY = "sec-novelty";
    public static final String SEC_URGENCY = "sec-urgency";
    public static final String SEC_CONDUCIVENESS = "sec-conduciveness";
    public static final String SEC_CONTROLLABILITY = "sec-controllability";
    public static final String SEC_ADJUSTABILITY = "sec-adjustability";
    public static final String SEC_INTERNAL_STANDARDS = "sec-internal-standards";
    public static final String SEC_EXTERNAL_STANDARDS = "sec-external-standards";

    // Action tendencies (indexed)
    public static final String ACTION_TENDENCY_COUNT = "action-tendency-count";
    public static String actionTendencyType(int i) { return "action-tendency-" + i + "-type"; }
    public static String actionTendencyIntensity(int i) { return "action-tendency-" + i + "-intensity"; }

    // Cognitive distortions (indexed)
    public static final String COGNITIVE_DISTORTION_COUNT = "cognitive-distortion-count";
    public static String cognitiveDistortionType(int i) { return "cognitive-distortion-" + i + "-type"; }
    public static String cognitiveDistortionStrength(int i) { return "cognitive-distortion-" + i + "-strength"; }

    // Drive impact (flat)
    public static final String DRIVE_CURIOSITY = "drive-curiosity";
    public static final String DRIVE_COMPETENCE = "drive-competence";
    public static final String DRIVE_AFFILIATION = "drive-affiliation";
    public static final String DRIVE_AUTONOMY = "drive-autonomy";

    // CAPS inputs (dynamic)
    public static String capsInput(String name) { return "caps-" + name; }

    // Goal impacts (indexed)
    public static final String GOAL_IMPACT_COUNT = "goal-impact-count";
    public static String goalImpactGoal(int i) { return "goal-impact-" + i + "-goal"; }
    public static String goalImpactRelationship(int i) { return "goal-impact-" + i + "-relationship"; }
    public static String goalImpactUrgencyDelta(int i) { return "goal-impact-" + i + "-urgency-delta"; }

    // Habituation (flat)
    public static final String HABITUATION_NOVELTY = "habituation-novelty";
    public static final String HABITUATION_SCORE = "habituation-score";
    public static final String HABITUATION_ECHOES = "habituation-echoes";

    // Gut feeling (flat)
    public static final String GUT_VALENCE = "gut-valence";
    public static final String GUT_INTENSITY = "gut-intensity";
    public static final String GUT_RESONANCE = "gut-resonance";

    // Related entities (indexed)
    public static final String RELATED_ENTITY_COUNT = "related-entity-count";
    public static String relatedEntity(int i) { return "related-entity-" + i; }
}
```

- [ ] **Step 4: Extend LifeEventEntry with inner records and new fields**

Add the new inner records (`OccEmotion`, `SecAppraisal`, `ActionTendency`, `CognitiveDistortion`, `DriveImpact`, `GoalImpact`, `Habituation`, `GutFeeling`) and the new fields (`domain`, `eventType`, `subject`, `period`, `relatedEntities`, `occEmotions`, `secAppraisal`, `actionTendencies`, `cognitiveDistortions`, `driveImpact`, `capsInputs`, `goalImpacts`, `habituation`, `gutFeeling`) to the LifeEventEntry record.

- [ ] **Step 5: Update LifeEventHandler to store enrichment attributes**

After the existing sub-thoughts block, add attribute storage for each enrichment field. Use `EnrichmentAttributeKeys` for all key constants. Override `event-type` attribute from entry if present. Store `domain` to allow non-experience domains. Store `subject` and `period`.

- [ ] **Step 6: Fix existing LifeEventEntry constructor calls in tests**

Add `null` for each new parameter.

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/
git commit -m "feat(#551): extend LifeEventEntry with cognitive enrichment fields

Add OCC emotions, SEC appraisal, action tendencies, cognitive distortions,
drive impact, CAPS inputs, goal impacts, habituation, gut feeling.
EnrichmentAttributeKeys provides indexed attribute key constants.

Refs #551"
```

---

## Batch 4: Python Converter

The converter script transforms corpus.json into typed YAML files. After this batch, the full pipeline can run: extract → assemble → verify → convert.

### Task 6: Create convert_corpus.py

**Files:**
- Create: `extraction/scripts/convert_corpus.py`
- Create: `extraction/tests/test_convert_corpus.py`

**Interfaces:**
- Consumes: `corpus.json` (format v2), `verify_schema.yaml` (entity_aliases, vocabularies)
- Produces: Directory of typed YAML files (`places.yaml`, `goals.yaml`, etc.) + `conversion-report.json`

- [ ] **Step 1: Write failing test for node-to-entry mapping**

```python
# test_convert_corpus.py
import json
import os
import tempfile
import yaml
from scripts.convert_corpus import convert

def test_goal_node_maps_to_goal_entry():
    corpus = {
        "format": "cognitive-workbench-corpus/v2",
        "subject": "Test Subject",
        "stats": {},
        "nodes": [{
            "name": "Test Goal",
            "subgraph_type": "goal",
            "properties": {},
            "confidence": {"origin": "STATED", "value": 0.9},
            "goal_tier": "thematic",
            "goal_horizon": "long",
            "goal_status": "active",
            "goal_urgency": 0.85,
            "content_domain": "health",
            "motivation_origin": "identified",
            "pad": {"pleasure": 0.5, "arousal": 0.3, "dominance": 0.7}
        }],
        "edges": [],
        "memories": [],
        "entity_enrichments": {},
        "disposition_profile": {}
    }
    schema = {"entity_aliases": {}, "entity_types": {}, "converter": {"subject_name": "Test Subject"}}

    with tempfile.TemporaryDirectory() as outdir:
        report = convert(corpus, schema, outdir)

        goals_path = os.path.join(outdir, "goals.yaml")
        assert os.path.exists(goals_path)
        with open(goals_path) as f:
            data = yaml.safe_load(f)
        assert data["type"] == "goal"
        assert len(data["entries"]) == 1
        entry = data["entries"][0]
        assert entry["name"] == "Test Goal"
        assert entry["tier"] == "thematic"
        assert entry["horizon"] == "long"
        assert entry["status"] == "active"
        assert entry["urgency"] == 0.85
        assert entry["content_domain"] == "health"
        assert entry["pad"]["pleasure"] == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd extraction && python3 -m pytest tests/test_convert_corpus.py::test_goal_node_maps_to_goal_entry -v`
Expected: ImportError — convert_corpus module doesn't exist

- [ ] **Step 3: Implement convert_corpus.py core**

```python
"""Corpus-to-YAML converter for BiographyLoader import.

Transforms corpus.json into typed YAML files ready for BiographyLoader.loadAll().

Usage:
  convert_corpus.py <corpus.json> [--schema <path>] [--output <dir>]
"""
import argparse
import json
import os
import re
import sys

import yaml


def slugify(name, max_len=60):
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug[:max_len]


def make_id(prefix, name, seen_ids):
    base = f"{prefix}-{slugify(name)}"
    if base not in seen_ids:
        seen_ids.add(base)
        return base
    for i in range(2, 1000):
        candidate = f"{base}-{i}"
        if candidate not in seen_ids:
            seen_ids.add(candidate)
            return candidate
    raise ValueError(f"Too many duplicate IDs for {base}")


NODE_TYPE_MAP = {
    "goal": "goal",
    "person": "relationship",
    "place": "place",
    "activity": "activity",
    "project": "project",
    "organisation": "organisation",
    "concept": "belief",
}

# Edge types that map to specific entry fields rather than associations
GOAL_EDGE_TYPES = {"contributes-to", "enables", "blocks", "requires", "decomposes-into"}
ACTIVITY_PLACE_EDGES = {"at"}
ACTIVITY_PARTICIPANT_EDGES = {"participated"}


def convert(corpus, schema, output_dir):
    aliases = schema.get("entity_aliases", {})
    seen_ids = set()
    report = {"nodes_mapped": 0, "edges_mapped": 0, "edges_specific": 0,
              "edges_association": 0, "edges_unattributable": 0,
              "memories_mapped": 0, "warnings": []}

    # Index nodes by name for edge resolution
    node_by_name = {n["name"]: n for n in corpus.get("nodes", [])}

    # Resolve alias in edge endpoints
    def resolve_alias(name):
        return aliases.get(name, name)

    # Build edge index: source_name -> list of edges
    edge_by_source = {}
    edge_by_target = {}
    for edge in corpus.get("edges", []):
        src = resolve_alias(edge.get("source", ""))
        tgt = resolve_alias(edge.get("target", ""))
        edge_by_source.setdefault(src, []).append({**edge, "source": src, "target": tgt})
        edge_by_target.setdefault(tgt, []).append({**edge, "source": src, "target": tgt})

    # --- Node mapping ---
    entries_by_type = {}
    node_to_entry_id = {}

    for node in corpus.get("nodes", []):
        sg_type = node.get("subgraph_type", "").lower()
        yaml_type = NODE_TYPE_MAP.get(sg_type)
        if not yaml_type:
            report["warnings"].append(f"Unknown subgraph_type: {sg_type} for node {node.get('name')}")
            continue

        entry = _map_node_to_entry(node, yaml_type, sg_type, seen_ids)
        node_to_entry_id[node["name"]] = entry["id"]

        # Map edges for this node
        node_edges = edge_by_source.get(node["name"], [])
        specific, assoc = _partition_edges(node_edges, yaml_type, node["name"])
        if specific:
            _apply_specific_edges(entry, yaml_type, specific)
        if assoc:
            entry["associations"] = [
                {"entity_ref": e["target"], "edge_type": e["type"],
                 "confidence": e.get("confidence_value")}
                for e in assoc
            ]
            report["edges_association"] += len(assoc)
        report["edges_specific"] += len(specific)

        entries_by_type.setdefault(yaml_type, []).append(entry)
        report["nodes_mapped"] += 1

    report["edges_mapped"] = report["edges_specific"] + report["edges_association"]

    # --- Memory mapping ---
    life_events = []
    current_states = []
    for i, mem in enumerate(corpus.get("memories", [])):
        domain = mem.get("domain", "experience")
        if domain == "mood" and mem.get("event_type") == "mood-snapshot":
            cs = _map_memory_to_current_state(mem, seen_ids, i)
            current_states.append(cs)
        else:
            le = _map_memory_to_life_event(mem, seen_ids, i)
            life_events.append(le)
        report["memories_mapped"] += 1

    if life_events:
        entries_by_type["life-event"] = life_events
    if current_states:
        entries_by_type["current-state"] = current_states

    # --- Entity enrichments ---
    enrichments = []
    for entity_name, data in corpus.get("entity_enrichments", {}).items():
        entry = _map_entity_enrichment(entity_name, data, seen_ids)
        enrichments.append(entry)
    if enrichments:
        entries_by_type["entity-enrichment"] = enrichments

    # --- Disposition profile ---
    disp = corpus.get("disposition_profile", {})
    if disp:
        subject = schema.get("converter", {}).get("subject_name", corpus.get("subject", "unknown"))
        dp_entry = _map_disposition_profile(subject, disp, seen_ids)
        entries_by_type["disposition-profile"] = [dp_entry]

    # --- Write YAML files ---
    type_to_filename = {
        "goal": "goals.yaml",
        "place": "places.yaml",
        "relationship": "relationships.yaml",
        "activity": "activities.yaml",
        "project": "projects.yaml",
        "organisation": "organisations.yaml",
        "belief": "beliefs.yaml",
        "life-event": "life-events.yaml",
        "current-state": "current-state.yaml",
        "entity-enrichment": "entity-enrichments.yaml",
        "disposition-profile": "disposition-profile.yaml",
    }

    for yaml_type, entries in entries_by_type.items():
        filename = type_to_filename.get(yaml_type, f"{yaml_type}.yaml")
        path = os.path.join(output_dir, filename)
        data = {"type": yaml_type, "entries": entries}
        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    # Write report
    report_path = os.path.join(output_dir, "conversion-report.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report


def _map_node_to_entry(node, yaml_type, sg_type, seen_ids):
    entry = {"id": make_id(sg_type, node["name"], seen_ids), "name": node["name"]}

    conf = node.get("confidence", {})
    if conf.get("origin"):
        entry["confidence_origin"] = conf["origin"]

    pad = node.get("pad")
    if pad:
        entry["pad"] = {k: v for k, v in pad.items() if k in ("pleasure", "arousal", "dominance") and v is not None}

    if node.get("valid_from"):
        entry["valid_from"] = str(node["valid_from"])
    if node.get("valid_until"):
        entry["valid_until"] = str(node["valid_until"])

    props = node.get("properties", {})
    traits = node.get("traits", [])

    if yaml_type == "goal":
        for corpus_field, yaml_field in [
            ("goal_tier", "tier"), ("goal_horizon", "horizon"), ("goal_status", "status"),
            ("goal_urgency", "urgency"), ("goal_need_tier", "need_tier"),
            ("goal_priority", "priority"), ("goal_feasibility", "feasibility"),
            ("content_domain", "content_domain"), ("content_subdomain", "content_subdomain"),
            ("motivation_origin", "motivation_origin"), ("clarity", "clarity"),
            ("evidence_basis", "evidence_basis"),
        ]:
            val = node.get(corpus_field)
            if val is not None:
                entry[yaml_field] = val

    elif yaml_type == "relationship":
        if traits:
            entry["traits"] = traits
        if props:
            entry["properties"] = {k: str(v) for k, v in props.items()}

    elif yaml_type == "place":
        if props:
            entry["properties"] = {k: str(v) for k, v in props.items()
                                   if not k.startswith("lifecycle.")}

    elif yaml_type == "activity":
        if props.get("type"):
            entry["activity_type"] = props["type"]
        trait_props = node.get("trait_properties", {})
        if trait_props.get("date"):
            entry["date"] = trait_props["date"]

    elif yaml_type == "belief":
        entry["description"] = node["name"]
        del entry["name"]

    elif yaml_type == "organisation":
        if traits:
            entry["traits"] = traits
        if props:
            entry["properties"] = {k: str(v) for k, v in props.items()}

    elif yaml_type == "project":
        desc = props.get("description")
        if desc:
            entry["description"] = desc
        remaining = {k: str(v) for k, v in props.items() if k != "description"}
        if remaining:
            entry["properties"] = remaining

    return entry


def _partition_edges(edges, yaml_type, source_name):
    specific = []
    associations = []
    for edge in edges:
        if yaml_type == "goal" and edge["type"] in GOAL_EDGE_TYPES:
            specific.append(edge)
        elif yaml_type == "activity" and edge["type"] in ACTIVITY_PLACE_EDGES:
            specific.append(edge)
        elif yaml_type == "activity" and edge["type"] in ACTIVITY_PARTICIPANT_EDGES:
            specific.append(edge)
        else:
            associations.append(edge)
    return specific, associations


def _apply_specific_edges(entry, yaml_type, edges):
    if yaml_type == "goal":
        deps = entry.get("dependencies", [])
        for e in edges:
            deps.append({"ref": e["target"], "edge_type": e["type"]})
        entry["dependencies"] = deps
    elif yaml_type == "activity":
        for e in edges:
            if e["type"] in ACTIVITY_PLACE_EDGES:
                entry["place_ref"] = e["target"]
            elif e["type"] in ACTIVITY_PARTICIPANT_EDGES:
                parts = entry.get("participants", [])
                parts.append({"entity_ref": e["target"]})
                entry["participants"] = parts


def _map_memory_to_life_event(mem, seen_ids, index):
    domain = mem.get("domain", "experience")
    entry = {
        "id": make_id(domain, f"{index:04d}", seen_ids),
        "description": mem["text"],
    }

    if mem.get("confidence", {}).get("origin"):
        entry["confidence_origin"] = mem["confidence"]["origin"]
    if mem.get("period"):
        entry["timestamp"] = str(mem["period"])

    entry["domain"] = domain
    if mem.get("event_type"):
        entry["event_type"] = mem["event_type"]
    if mem.get("subject"):
        entry["subject"] = mem["subject"]
    if mem.get("period"):
        entry["period"] = str(mem["period"])
    if mem.get("related_entities"):
        entry["related_entities"] = mem["related_entities"]

    pad = mem.get("pad")
    if pad and isinstance(pad, dict):
        entry["pad"] = {k: v for k, v in pad.items()
                        if k in ("pleasure", "arousal", "dominance") and v is not None}

    # Enrichment fields — pass through as-is (YAML serialization handles nested structures)
    for field in ["occ_emotions", "sec_appraisal", "action_tendencies",
                  "cognitive_distortions", "drive_impact", "caps_inputs",
                  "goal_impacts", "habituation", "gut_feeling"]:
        val = mem.get(field)
        if val is not None and val != [] and val != {}:
            entry[field] = val

    # Sub-thoughts
    if mem.get("sub_thoughts"):
        entry["sub_thoughts"] = [{"type": st["type"], "text": st["text"]}
                                 for st in mem["sub_thoughts"]
                                 if st.get("type") and st.get("text")]

    # Entity refs from related_entities
    if mem.get("related_entities"):
        entry["entity_refs"] = mem["related_entities"]

    return entry


def _map_memory_to_current_state(mem, seen_ids, index):
    entry = {"id": make_id("mood", f"{index:04d}", seen_ids)}
    pad = mem.get("pad", {})
    if pad:
        entry["mood"] = {k: v for k, v in pad.items()
                         if k in ("pleasure", "arousal", "dominance") and v is not None}
    if mem.get("text"):
        entry["recent_context"] = mem["text"]
    if mem.get("period"):
        entry["timestamp"] = str(mem["period"])
    return entry


def _map_entity_enrichment(entity_name, data, seen_ids):
    entry = {
        "id": make_id("enrichment", entity_name, seen_ids),
        "entity_ref": entity_name,
    }
    if data.get("drive_baselines"):
        entry["drive_baselines"] = {
            k: {"baseline": v.get("baseline"), "justification": v.get("justification")}
            for k, v in data["drive_baselines"].items()
        }
    if data.get("caps_patterns"):
        entry["caps_patterns"] = [
            {"pattern": p.get("pattern", ""), "frequency": p.get("frequency")}
            for p in data["caps_patterns"]
        ]
    if data.get("behavioural_attractors"):
        entry["behavioural_attractors"] = [
            {"name": a.get("name", ""), "description": a.get("description")}
            for a in data["behavioural_attractors"]
        ]
    if data.get("relationship_stages"):
        entry["relationship_stages"] = data["relationship_stages"]
    return entry


def _map_disposition_profile(subject, disp, seen_ids):
    entry = {
        "id": make_id("disposition", subject, seen_ids),
        "entity_ref": subject,
        "axes": {},
    }
    for axis, val in disp.items():
        if isinstance(val, dict) and "score" in val:
            entry["axes"][axis] = {
                "score": val["score"],
                "justification": val.get("justification"),
            }
    return entry


def main():
    parser = argparse.ArgumentParser(description="Convert corpus.json to biography YAML")
    parser.add_argument("corpus", help="Path to corpus.json")
    parser.add_argument("--schema", default=None, help="Path to verify_schema.yaml")
    parser.add_argument("--output", default="biography-output", help="Output directory")
    args = parser.parse_args()

    with open(args.corpus) as f:
        corpus = json.load(f)

    schema = {}
    if args.schema:
        with open(args.schema) as f:
            schema = yaml.safe_load(f)

    os.makedirs(args.output, exist_ok=True)
    report = convert(corpus, schema, args.output)

    print(f"Nodes mapped: {report['nodes_mapped']}")
    print(f"Edges mapped: {report['edges_mapped']} "
          f"(specific: {report['edges_specific']}, association: {report['edges_association']})")
    print(f"Memories mapped: {report['memories_mapped']}")
    if report["warnings"]:
        print(f"Warnings: {len(report['warnings'])}")
        for w in report["warnings"][:5]:
            print(f"  - {w}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Write additional converter tests**

Test edge mapping (specific vs associations), alias resolution, memory mapping, entity enrichment mapping, disposition profile mapping, ID uniqueness.

- [ ] **Step 5: Run tests**

Run: `cd extraction && python3 -m pytest tests/test_convert_corpus.py -v`
Expected: All PASS

- [ ] **Step 6: Run converter on actual Frida corpus**

Run: `cd extraction && python3 scripts/convert_corpus.py output-test/corpus.json --schema docs/verify_schema.yaml --output output-test/biography-output`
Expected: YAML files created, report shows counts matching corpus stats

- [ ] **Step 7: Commit**

```bash
git add extraction/scripts/convert_corpus.py extraction/tests/test_convert_corpus.py
git commit -m "feat(#551): add convert_corpus.py — corpus-to-YAML converter

Maps nodes, edges, memories, entity enrichments, and disposition
profile from corpus.json to typed YAML files for BiographyLoader.

Refs #551"
```

---

## Batch 5: Integration Test and Validation

End-to-end round-trip: converter YAML → BiographyImportRunner → store queries → validation assertions. After this batch, the pipeline is proven.

### Task 7: BiographyImportRunner integration test with converter output

**Files:**
- Create: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/BiographyImportIntegrationTest.java`
- Create: `memory-seeding/src/test/resources/biography-test/goals.yaml` (generated sample)
- Create: `memory-seeding/src/test/resources/biography-test/organisations.yaml` (generated sample)
- Create: `memory-seeding/src/test/resources/biography-test/life-events.yaml` (generated sample)
- Create: `memory-seeding/src/test/resources/biography-test/entity-enrichments.yaml` (generated sample)
- Create: `memory-seeding/src/test/resources/biography-test/disposition-profile.yaml` (generated sample)

**Interfaces:**
- Consumes: All handler types, `BiographyLoader.loadAll()`, `BiographyImportRunner.run()`
- Produces: Integration test proving round-trip from YAML to stores

- [ ] **Step 1: Create sample YAML test fixtures**

Create minimal YAML files exercising all 13 entry types (including the existing `places.yaml`). Use a small, self-contained data set — 2-3 entries per type.

Example `goals.yaml`:
```yaml
type: goal
entries:
  - id: goal-artistic-identity
    confidence_origin: INFERRED
    name: "Establish artistic identity"
    tier: thematic
    horizon: long
    status: active
    urgency: 0.85
    content_domain: self-actualisation
    motivation_origin: intrinsic
    pad:
      pleasure: 0.6
      arousal: 0.7
      dominance: 0.8
    dependencies:
      - ref: "La Casa Azul"
        edge_type: "associated-with"
```

- [ ] **Step 2: Write integration test**

```java
class BiographyImportIntegrationTest {

    @Test
    void fullRoundTrip() {
        var store = new InMemoryMindMapStore();
        var memoryStore = new InMemoryMemoryStore();

        var handlers = List.of(
            new CulturalContextHandler(store),
            new PlaceHandler(store),
            new ActivityHandler(store),
            new ProjectHandler(store),
            new OrganisationHandler(store),
            new RelationshipHandler(store, memoryStore),
            new GoalHandler(store),
            new BeliefHandler(store),
            new LifeEventHandler(memoryStore),
            new CurrentStateHandler(memoryStore),
            new EntityEnrichmentHandler(store),
            new DispositionProfileHandler(store)
        );
        var runner = new BiographyImportRunner(handlers);
        var loader = new BiographyLoader();

        Path biographyDir = Path.of("src/test/resources/biography-test");
        var profile = loader.loadAll(biographyDir, "test-agent", "test-tenant");
        runner.run(profile, "test-agent", "test-tenant");

        // Validate node counts
        var goalSubgraph = store.findSubgraph(SubgraphTypes.GOAL, "test-tenant");
        assertNotNull(goalSubgraph);
        var goalNodes = store.listNodes(goalSubgraph.id(), "test-tenant");
        assertFalse(goalNodes.isEmpty());

        // Validate goal taxonomy fields
        var goal = store.resolveNode("Establish artistic identity", goalSubgraph.id(), "test-tenant");
        assertNotNull(goal);
        assertEquals("thematic", goal.properties().get("tier"));
        assertEquals("active", goal.properties().get("status"));

        // Validate organisation
        var orgSubgraph = store.findSubgraph(SubgraphTypes.ORGANISATION, "test-tenant");
        assertNotNull(orgSubgraph);

        // Validate memories
        var memories = memoryStore.scan(
            MemoryScanRequest.of(Subject.of("agent", "test-agent"), "experience", "test-tenant"));
        assertFalse(memories.isEmpty());

        // Validate enrichment
        var personSubgraph = store.findSubgraph(SubgraphTypes.PERSON, "test-tenant");
        // If a person node exists with enrichment, check drive baselines
    }
}
```

- [ ] **Step 3: Run test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=BiographyImportIntegrationTest`
Expected: PASS

- [ ] **Step 4: Run full memory-seeding test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add memory-seeding/src/test/
git commit -m "feat(#551): add BiographyImportRunner integration test

Full round-trip: YAML fixtures → BiographyLoader → BiographyImportRunner
→ store queries → validation assertions. Covers all 13 entry types.

Refs #551"
```

### Task 8: Full module build verification

**Files:** None created — verification only

- [ ] **Step 1: Build all modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-seeding -am`
Expected: BUILD SUCCESS

- [ ] **Step 2: Run converter on Frida corpus and verify report**

Run: `cd extraction && python3 scripts/convert_corpus.py output-test/corpus.json --schema docs/verify_schema.yaml --output output-test/biography-output`
Expected: 132 nodes mapped, 1570 edges mapped (mix of specific and associations), 261 memories mapped

- [ ] **Step 3: Commit converter output as test fixture**

```bash
git add extraction/output-test/biography-output/
git commit -m "chore(#551): add Frida corpus converter output as test fixture

132 nodes, 1570 edges, 261 memories converted to typed YAML.

Refs #551"
```

---

## References

- [2026-10-12-production-biography-pipeline-design.md] — design spec this plan implements
- [memory-seeding/src/main/java/.../biography/GoalEntry.java] — existing goal entry record
- [memory-seeding/src/main/java/.../biography/GoalHandler.java] — existing goal handler
- [memory-seeding/src/main/java/.../biography/LifeEventEntry.java] — existing life event entry
- [memory-seeding/src/main/java/.../biography/LifeEventHandler.java] — existing life event handler
- [memory-seeding/src/main/java/.../biography/BiographyImportRunner.java] — import orchestrator
- [memory-seeding/src/main/java/.../biography/BiographyLoader.java] — YAML loader
- [memory-seeding/src/main/java/.../biography/BiographyTemplateTypes.java] — layer ordering
- [memory-seeding/src/main/java/.../biography/PlaceEntry.java] — Association pattern reference
- [extraction/docs/verify_schema.yaml] — Java-side import contract
- [extraction/output-test/corpus.json] — source data format
- [GitHub #551] — focal issue
- [GitHub #550] — verify_corpus.py design
- [GitHub #538] — parent epic
