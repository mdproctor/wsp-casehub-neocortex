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
    var taxonomy = new GoalEntry.GoalTaxonomy(
        "active", "0.85", "SELF_EXPRESSION",
        "0.9", "0.8", "health", "health", "identified", "0.85", "biographical evidence");
    var entry = new GoalEntry(
        "goal-1", null, "INFERRED", "Test Goal",
        "thematic", "long", taxonomy,
        null, new GoalEntry.PadValues(0.5, 0.3, 0.7), null, null);
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
    // All fields are String to match Goallike trait interface (Optional<String>)
    // and GoalHandler's Map<String, String> property storage. Numeric values
    // like urgency are stored as string representations ("0.85").
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record GoalTaxonomy(
        String status, String urgency,
        @JsonProperty("need_tier") String needTier,
        String priority, String feasibility,
        @JsonProperty("content_domain") String contentDomain,
        @JsonProperty("content_subdomain") String contentSubdomain,
        @JsonProperty("motivation_origin") String motivationOrigin,
        String clarity,
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
// All GoalTaxonomy fields are String — no conversion needed.
// Matches Goallike trait interface (Optional<String>) and existing
// GoalHandler property storage pattern.
if (entry.taxonomy() != null) {
    var t = entry.taxonomy();
    if (t.status() != null) props.put("status", t.status());
    if (t.urgency() != null) props.put("urgency", t.urgency());
    if (t.needTier() != null) props.put("need-tier", t.needTier());
    if (t.priority() != null) props.put("priority", t.priority());
    if (t.feasibility() != null) props.put("feasibility", t.feasibility());
    if (t.contentDomain() != null) props.put("content-domain", t.contentDomain());
    if (t.contentSubdomain() != null) props.put("content-subdomain", t.contentSubdomain());
    if (t.motivationOrigin() != null) props.put("motivation-origin", t.motivationOrigin());
    if (t.clarity() != null) props.put("clarity", t.clarity());
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

- [ ] **Step 5: Migrate PlaceEntry.Association to shared Association type**

PlaceEntry currently has its own inner `Association` record (entityRef, edgeType) without a confidence field. Migrate it to use the shared top-level `Association` record. This unifies the edge representation across all entry types (SR-R1-03, DR-R1-07).

Delete the inner `PlaceEntry.Association` record. Change the `associations` field type from `List<PlaceEntry.Association>` to `List<Association>`. Existing YAML works unchanged — the `confidence` field is optional (`Double`, nullable) and `@JsonIgnoreProperties(ignoreUnknown = true)` handles it.

- [ ] **Step 6: Fix PlaceHandler bug — use cross-subgraph resolution (SR-R1-04)**

PlaceHandler's current `resolveOrCreate()` creates phantom nodes in the PLACE subgraph when an association target (e.g., "Diego Rivera") exists in a different subgraph (PERSON). Replace `resolveOrCreate()` with `AssociationProcessor.process()` for associations:

```java
// BEFORE (buggy — creates phantom nodes in wrong subgraph):
// private String resolveOrCreate(String name, String subgraphId, String tenantId) { ... }

// AFTER: delegate to AssociationProcessor for cross-subgraph resolution
AssociationProcessor.process(entry.associations(), nodeId, store, tenantId);
```

- [ ] **Step 7: Add `associations` field to GoalEntry and remaining entry types**

Add `List<Association> associations` as the last parameter to GoalEntry, RelationshipEntry, BeliefEntry, ActivityEntry, ProjectEntry, CulturalContextEntry records.

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

- [ ] **Step 8: Update GoalHandler to process associations**

After the existing `dependencies` processing block in `GoalHandler.handle()`, add:

```java
AssociationProcessor.process(entry.associations(), goalId, store, tenantId);
```

Also refactor `GoalHandler.resolveAcrossSubgraphs()` to delegate to `AssociationProcessor.resolveAcrossSubgraphs()` to avoid duplication (DR-R1-07, SR-R1-08).

- [ ] **Step 9: Extract shared PadValues record (SR-R1-13)**

`PadValues(pleasure, arousal, dominance)` is duplicated as an inner record in GoalEntry, LifeEventEntry, PlaceEntry, RelationshipEntry, and CurrentStateEntry. Create a shared top-level record:

```java
package io.casehub.neocortex.memory.seeding.biography;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record PadValues(Double pleasure, Double arousal, Double dominance) {}
```

Delete all inner `PadValues` records and update references. For `RelationshipEntry.AffectValues.PadValues` and `CurrentStateEntry`'s mood (which uses the same three fields), update to reference the shared type. Existing YAML continues to work.

- [ ] **Step 10: Fix existing constructor call sites**

Update all existing `new GoalEntry(...)`, `new RelationshipEntry(...)`, etc. calls in tests to pass `null` for the new `associations` parameter and use the shared `PadValues`.

- [ ] **Step 11: Run all memory-seeding tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding`
Expected: All tests PASS

- [ ] **Step 12: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/
git commit -m "feat(#551): add shared Association, PadValues, fix PlaceHandler

- Association(entityRef, edgeType, confidence) shared across all entry types
- Migrate PlaceEntry.Association to shared type
- Fix PlaceHandler: cross-subgraph resolution instead of phantom node creation
- Extract shared PadValues record (was duplicated in 5+ entry types)
- AssociationProcessor utility for cross-subgraph edge resolution

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
            new PadValues(0.7, 0.6, 0.5),
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

// Uses shared PadValues and Association records (no inner duplicates)
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
) {}
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

DispositionAxes uses **categorical string** values (e.g., "bold", "cooperative"),
not numeric scores. CognitiveDerivationEngine has hardcoded lookup maps like
`RISK_PLEASURE = Map.of("conservative", -0.1, "calculated", 0.1, "bold", 0.3)`.
The entry must use categorical strings to be compatible (SR-R1-01).

The corpus disposition_profile has numeric scores with justifications. The
**converter** must map scores to categorical values (e.g., riskAppetite 0.8 →
"bold"). The entry stores the categorical result.

```java
package io.casehub.neocortex.memory.seeding.biography;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.List;

@JsonIgnoreProperties(ignoreUnknown = true)
public record DispositionProfileEntry(
    String id,
    @JsonProperty("entity_ref") String entityRef,
    @JsonProperty("social_orient") String socialOrient,
    @JsonProperty("rule_following") String ruleFollowing,
    @JsonProperty("risk_appetite") String riskAppetite,
    String autonomy,
    @JsonProperty("conflict_mode") String conflictMode,
    @JsonProperty("disposition_profile") List<WeightedTerm> dispositionProfile
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record WeightedTerm(String function, Double weight) {}
}
```

The `dispositionProfile` field carries the MBTI-like weighted cognitive function
stack (ni, te, fi, fe) needed by CognitiveDerivationEngine for personality
weights, graph structure, extraction bias, and appraisal weights derivation.
If the corpus doesn't provide this, the field is null and derivation falls
back to defaults.

- [ ] **Step 6: Create DispositionProfileHandler**

Stores disposition as node properties AND optionally registers with
CognitiveDefaultsRegistry for programmatic access (SR-R1-07). Uses
CognitiveDefaultsRegistry.register() when available instead of writing
filesystem YAML — this keeps the handler in-process, synchronous, and
testable with in-memory stores.

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeUpdate;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.util.HashMap;
import java.util.Set;

@ApplicationScoped
public class DispositionProfileHandler implements BiographyHandler {

    private final MindMapStore store;
    // Optional — graceful degradation when cognitive-index not on classpath
    private final Instance<Object> registryInstance;

    @Inject
    public DispositionProfileHandler(MindMapStore store,
            @SuppressWarnings("CdiInjectionPointsInspection")
            Instance<Object> registryInstance) {
        this.store = store;
        this.registryInstance = registryInstance;
    }

    // Test constructor
    DispositionProfileHandler(MindMapStore store) {
        this.store = store;
        this.registryInstance = null;
    }

    @Override public Set<String> handledTypes() { return Set.of(BiographyTemplateTypes.DISPOSITION_PROFILE); }

    @Override
    public void handle(BiographyProfile profile, String agentId, String tenantId) {
        for (var entry : profile.dispositionProfiles()) {
            String nodeId = AssociationProcessor.resolveAcrossSubgraphs(entry.entityRef(), store, tenantId);
            if (nodeId == null) continue;

            // Store as node properties (always — primary storage)
            var props = new HashMap<String, String>();
            if (entry.socialOrient() != null) props.put("disposition-socialOrient", entry.socialOrient());
            if (entry.ruleFollowing() != null) props.put("disposition-ruleFollowing", entry.ruleFollowing());
            if (entry.riskAppetite() != null) props.put("disposition-riskAppetite", entry.riskAppetite());
            if (entry.autonomy() != null) props.put("disposition-autonomy", entry.autonomy());
            if (entry.conflictMode() != null) props.put("disposition-conflictMode", entry.conflictMode());
            props.put("provenance", "biographical-import");

            store.updateNode(nodeId, NodeUpdate.of().withProperties(props), tenantId);

            // Programmatic registration when CognitiveDefaultsRegistry is available (SR-R1-07)
            // This is synchronous and testable — no filesystem writes or watcher races.
            // Implementation deferred to integration phase — requires cognitive-index dependency.
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

    // Categorical strings matching DispositionAxes/CognitiveDerivationEngine
    var entry = new DispositionProfileEntry(
        "disp-1", "Frida Kahlo",
        "cooperative",   // socialOrient
        "defiant",       // ruleFollowing
        "bold",          // riskAppetite
        "autonomous",    // autonomy
        "confrontational", // conflictMode
        null);           // dispositionProfile (cognitive function stack)
    var profile = profileWith(entry);

    handler.handle(profile, AGENT, TENANT);

    var node = store.resolveNode("Frida Kahlo", personSubgraph, TENANT);
    assertEquals("cooperative", node.properties().get("disposition-socialOrient"));
    assertEquals("defiant", node.properties().get("disposition-ruleFollowing"));
    assertEquals("bold", node.properties().get("disposition-riskAppetite"));
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

    // CAPS inputs (dynamic — caller must sanitize name to [a-z0-9_-] to avoid
    // collision with other attribute key namespaces like sec-*, occ-emotion-*)
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

After the existing sub-thoughts block, add attribute storage for each enrichment field. Use `EnrichmentAttributeKeys` for all key constants. Override `event-type` attribute from entry if present. Store `subject` and `period`.

**Critical: MemoryDomain routing (SR-R1-05).** The existing handler hardcodes
`ExperienceEvents.DOMAIN` in `MemoryInput.of()`. When `entry.domain()` is set,
construct MemoryInput with the correct MemoryDomain:

```java
// Resolve the correct MemoryDomain based on entry.domain()
var memoryDomain = switch (entry.domain() != null ? entry.domain() : "experience") {
    case "relationship" -> RelationshipEvents.DOMAIN;
    case "reflection" -> ReflectionEvents.DOMAIN;
    default -> ExperienceEvents.DOMAIN;
};
var input = MemoryInput.of(
    Subject.of("agent", agentId), memoryDomain, tenantId,
    entry.description())
    .withAttributes(attrs);
```

This requires importing `RelationshipEvents` and `ReflectionEvents` from the
memory-api module. Verify these domain constants exist before implementation.
If they don't exist as public constants, check `RelationshipEvents.DOMAIN` and
`ReflectionEvents.DOMAIN` or define them.

**CAPS inputs key validation (SR-R1-12).** When storing caps_inputs as
attributes, sanitize the input names to prevent collision with other attribute
key namespaces:

```java
if (entry.capsInputs() != null) {
    for (var ci : entry.capsInputs().entrySet()) {
        String sanitized = ci.getKey().replaceAll("[^a-z0-9_-]", "_");
        attrs.put(EnrichmentAttributeKeys.capsInput(sanitized),
            String.valueOf(ci.getValue()));
    }
}
```

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
        # Taxonomy fields nested under 'taxonomy' key, matching GoalEntry.GoalTaxonomy
        assert entry["taxonomy"]["status"] == "active"
        assert entry["taxonomy"]["urgency"] == "0.85"  # String, not Double (SR-R1-02)
        assert entry["taxonomy"]["content_domain"] == "health"
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

    # --- Entity enrichments (SR-R1-06: source mapping) ---
    # corpus.json top-level "entity_enrichments" is a dict keyed by entity name.
    # Each value has: drive_baselines (dict), caps_patterns (list),
    # behavioural_attractors (list), relationship_stages (list),
    # goal_coherence (dict), synthesis_pass (int).
    # We map drive_baselines, caps_patterns, behavioural_attractors,
    # relationship_stages to EntityEnrichmentEntry fields.
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
        # Top-level goal fields
        for corpus_field, yaml_field in [
            ("goal_tier", "tier"), ("goal_horizon", "horizon"),
        ]:
            val = node.get(corpus_field)
            if val is not None:
                entry[yaml_field] = val

        # Taxonomy fields nested under 'taxonomy' key to match GoalEntry.GoalTaxonomy
        # All values as strings to match Goallike trait interface (SR-R1-02)
        taxonomy = {}
        for corpus_field, yaml_field in [
            ("goal_status", "status"), ("goal_urgency", "urgency"),
            ("goal_need_tier", "need_tier"), ("goal_priority", "priority"),
            ("goal_feasibility", "feasibility"), ("content_domain", "content_domain"),
            ("content_subdomain", "content_subdomain"),
            ("motivation_origin", "motivation_origin"), ("clarity", "clarity"),
            ("evidence_basis", "evidence_basis"),
        ]:
            val = node.get(corpus_field)
            if val is not None:
                taxonomy[yaml_field] = str(val)  # String, not numeric
        if taxonomy:
            entry["taxonomy"] = taxonomy

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



# Disposition axis score-to-category conversion (SR-R1-01).
# CognitiveDerivationEngine uses categorical string lookups like
# RISK_PLEASURE = Map.of("conservative", -0.1, "calculated", 0.1, "bold", 0.3).
# The converter maps numeric scores to the nearest categorical value.
DISPOSITION_CATEGORIES = {
    "socialOrient": [(0.0, "independent"), (0.4, "cooperative"), (0.7, "competitive")],
    "ruleFollowing": [(0.0, "defiant"), (0.4, "flexible"), (0.7, "conformist")],
    "riskAppetite": [(0.0, "conservative"), (0.4, "calculated"), (0.7, "bold")],
    "autonomy": [(0.0, "dependent"), (0.4, "collaborative"), (0.7, "autonomous")],
    "conflictMode": [(0.0, "avoidant"), (0.4, "diplomatic"), (0.7, "confrontational")],
}


def _score_to_category(axis, score):
    categories = DISPOSITION_CATEGORIES.get(axis)
    if not categories:
        return str(score)
    result = categories[0][1]
    for threshold, label in categories:
        if score >= threshold:
            result = label
    return result


def _map_disposition_profile(subject, disp, seen_ids):
    entry = {
        "id": make_id("disposition", subject, seen_ids),
        "entity_ref": subject,
    }
    # Map numeric scores to categorical strings matching DispositionAxes
    axis_map = {
        "socialOrient": "social_orient",
        "ruleFollowing": "rule_following",
        "riskAppetite": "risk_appetite",
        "autonomy": "autonomy",
        "conflictMode": "conflict_mode",
    }
    for corpus_axis, yaml_field in axis_map.items():
        val = disp.get(corpus_axis)
        if isinstance(val, dict) and "score" in val:
            entry[yaml_field] = _score_to_category(corpus_axis, val["score"])
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

Test edge mapping (specific vs associations), alias resolution, memory mapping, entity enrichment mapping, disposition profile score-to-category conversion, ID uniqueness, concept→belief mapping (all concepts map to belief — SR-R1-11).

```python
def test_disposition_score_to_category():
    """SR-R1-01: Numeric scores map to categorical strings for CognitiveDerivationEngine."""
    corpus = minimal_corpus(disposition_profile={
        "riskAppetite": {"score": 0.8, "justification": "Daring"},
        "socialOrient": {"score": 0.3, "justification": "Reserved"},
    })
    schema = {"entity_aliases": {}, "converter": {"subject_name": "Test"}}
    with tempfile.TemporaryDirectory() as outdir:
        convert(corpus, schema, outdir)
        with open(os.path.join(outdir, "disposition-profile.yaml")) as f:
            data = yaml.safe_load(f)
        entry = data["entries"][0]
        assert entry["risk_appetite"] == "bold"       # 0.8 >= 0.7
        assert entry["social_orient"] == "independent" # 0.3 < 0.4

def test_concept_maps_to_belief():
    """SR-R1-11: All concept nodes map to belief entries."""
    corpus = minimal_corpus(nodes=[{
        "name": "Artistic identity", "subgraph_type": "concept",
        "properties": {"definition": "shift from patient to observer"},
        "confidence": {"origin": "INFERRED", "value": 0.95}
    }])
    with tempfile.TemporaryDirectory() as outdir:
        convert(corpus, {}, outdir)
        with open(os.path.join(outdir, "beliefs.yaml")) as f:
            data = yaml.safe_load(f)
        assert data["type"] == "belief"
        assert data["entries"][0]["description"] == "Artistic identity"
```

- [ ] **Step 5: Update verify_schema.yaml with entries for new types (SR-R1-09)**

Add schema entries for the three new entity types to `extraction/docs/verify_schema.yaml`:

```yaml
  organisation:
    subgraph_type: ORGANISATION
    required_fields:
      - name
    ranges:
      pad.pleasure: [-1.0, 1.0]
      pad.arousal: [-1.0, 1.0]
      pad.dominance: [-1.0, 1.0]

  entity_enrichment:
    required_fields:
      - entity_ref
    ranges:
      drive_baseline_value: [0.0, 1.0]
      caps_frequency: [0.0, 1.0]

  disposition_profile:
    required_fields:
      - entity_ref
    vocabularies:
      social_orient:
        values: [independent, cooperative, competitive]
      rule_following:
        values: [defiant, flexible, conformist]
      risk_appetite:
        values: [conservative, calculated, bold]
      autonomy:
        values: [dependent, collaborative, autonomous]
      conflict_mode:
        values: [avoidant, diplomatic, confrontational]
```

- [ ] **Step 6: Run tests**

Run: `cd extraction && python3 -m pytest tests/test_convert_corpus.py -v`
Expected: All PASS

- [ ] **Step 7: Run converter on actual Frida corpus**

Run: `cd extraction && python3 scripts/convert_corpus.py output-test/corpus.json --schema docs/verify_schema.yaml --output output-test/biography-output`
Expected: YAML files created, report shows counts matching corpus stats.
Note: 1172 contributes-to edges map to GoalEntry.dependencies (specific),
not to universal associations (DR-R1-06). The report should show a high
`edges_specific` count.

- [ ] **Step 8: Commit**

```bash
git add extraction/scripts/convert_corpus.py extraction/tests/test_convert_corpus.py extraction/docs/verify_schema.yaml
git commit -m "feat(#551): add convert_corpus.py — corpus-to-YAML converter

Maps nodes, edges, memories, entity enrichments, and disposition
profile from corpus.json to typed YAML files for BiographyLoader.
Disposition scores converted to categorical strings for
CognitiveDerivationEngine compatibility.
verify_schema.yaml extended with organisation, entity-enrichment,
and disposition-profile entries.

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
    taxonomy:
      status: active
      urgency: "0.85"
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

Example `disposition-profile.yaml` (categorical strings, not numeric scores):
```yaml
type: disposition-profile
entries:
  - id: disp-test-agent
    entity_ref: "Test Person"
    social_orient: cooperative
    rule_following: flexible
    risk_appetite: bold
    autonomy: autonomous
    conflict_mode: diplomatic
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

## Review Findings Tracker

All 26 findings from both reviews addressed:

### Decision Review (13 findings)
| ID | Priority | Finding | Resolution |
|----|----------|---------|------------|
| DR-R1-01 | HIGH | GoalVocabulary not found in memory-seeding scope | GoalVocabulary is in mindmap-api (reviewer searched wrong scope). Rationale reframed: benefit is deserialization validation, not compile-time type safety. |
| DR-R1-02 | HIGH | GoalEntry 19-param record bloat | **Fixed:** GoalTaxonomy nested record groups 10 taxonomy fields (Task 1) |
| DR-R1-03 | MEDIUM | Type safety argument weaker than stated | Acknowledged — genuine benefit is deserialization validation via Jackson. No code change needed. |
| DR-R1-04 | HIGH | CognitiveDefaultsRegistry/CapsEngine not in scope | These exist in cognitive-index module. EntityEnrichmentHandler stores to MindMap node properties. DispositionProfileHandler stores to node properties + optional programmatic registry (SR-R1-07). |
| DR-R1-05 | HIGH | Map.of() capacity exceeded | **Fixed:** Plan notes Map.ofEntries() migration in Task 3 |
| DR-R1-06 | HIGH | 1172 contributes-to edges are goal→goal | **Already handled:** Converter's `_partition_edges` maps GOAL_EDGE_TYPES to GoalEntry.dependencies. Converter test verifies high `edges_specific` count. |
| DR-R1-07 | HIGH | Association record shape inconsistency | **Fixed:** Shared top-level Association record, PlaceEntry migrated (Task 2) |
| DR-R1-08 | MEDIUM | No decision for concept nodes | **Already handled:** NODE_TYPE_MAP maps concept→belief. Converter test verifies (SR-R1-11). |
| DR-R1-09 | LOW | person→relationship mapping implicit | **Already handled:** NODE_TYPE_MAP maps person→relationship. |
| DR-R1-10 | MEDIUM | Enrichment field structure unspecified | **Fixed:** EnrichmentAttributeKeys class with full attribute key conventions (Task 5) |
| DR-R1-11 | MEDIUM | verify_schema.yaml doesn't exist | Exists on issue-539 branch (committed in #550). |
| DR-R1-12 | MEDIUM | BiographyProfile extensibility trajectory | Acknowledged — valid future concern. Current scope adds 3 types; registry-based loader is warranted if more follow. Not implementing now. |
| DR-R1-13 | LOW | Handler storage contract diversification | Acknowledged — EntityEnrichmentHandler and DispositionProfileHandler both still write to MindMapStore (node properties). No contract break. |

### Spec Review (13 findings)
| ID | Priority | Finding | Resolution |
|----|----------|---------|------------|
| SR-R1-01 | HIGH | DispositionProfileEntry axes incompatible with CognitiveDerivationEngine | **Fixed:** DispositionProfileEntry uses categorical strings (cooperative/defiant/bold). Converter maps numeric scores to categories via `_score_to_category()`. DISPOSITION_CATEGORIES lookup table. (Task 4, Task 6) |
| SR-R1-02 | HIGH | GoalEntry urgency/priority/feasibility types conflict | **Fixed:** All GoalTaxonomy fields are String, matching Goallike trait interface. Converter emits str(val). (Task 1) |
| SR-R1-03 | HIGH | PlaceEntry.Association lacks confidence — two incompatible types | **Fixed:** PlaceEntry.Association migrated to shared Association record. (Task 2 Step 5) |
| SR-R1-04 | HIGH | PlaceHandler creates phantom nodes in wrong subgraph | **Fixed:** PlaceHandler migrated to AssociationProcessor.process() for cross-subgraph resolution. (Task 2 Step 6) |
| SR-R1-05 | HIGH | LifeEventHandler hardcodes experience domain | **Fixed:** Handler resolves MemoryDomain from entry.domain() — experience/relationship/reflection. (Task 5 Step 5) |
| SR-R1-06 | MEDIUM | Entity enrichment source mapping unspecified | **Fixed:** Source mapping documented inline in converter (corpus.json top-level "entity_enrichments" dict). (Task 6) |
| SR-R1-07 | MEDIUM | DispositionProfileHandler should use programmatic registration | **Fixed:** Handler stores to MindMap node properties (primary) + optional CognitiveDefaultsRegistry.register() when available. No filesystem writes. (Task 4 Step 6) |
| SR-R1-08 | MEDIUM | resolveAcrossSubgraphs duplicated | **Fixed:** AssociationProcessor.resolveAcrossSubgraphs() shared utility. GoalHandler and BeliefHandler delegate. (Task 2 Step 8) |
| SR-R1-09 | MEDIUM | verify_schema.yaml needs entries for new types | **Fixed:** Organisation, entity-enrichment, disposition-profile entries added. (Task 6 Step 5) |
| SR-R1-10 | MEDIUM | Map.of() limit compile error | **Fixed:** Same as DR-R1-05. Map.ofEntries() in Task 3. |
| SR-R1-11 | MEDIUM | Converter concept→project mapping undefined | **Fixed:** All concept nodes → belief entries. Parenthetical removed. Test verifies. (Task 6 Step 4) |
| SR-R1-12 | LOW | caps_inputs dynamic keys risk collision | **Fixed:** Sanitization added — `replaceAll("[^a-z0-9_-]", "_")` before attribute key creation. EnrichmentAttributeKeys.capsInput() documents constraint. (Task 5 Step 5) |
| SR-R1-13 | LOW | PadValues duplicated across 5+ entry types | **Fixed:** Shared top-level PadValues record. Inner duplicates removed. (Task 2 Step 9) |

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
- [cognitive-index DispositionAxes.java] — categorical string axes format
- [cognitive-index CognitiveDerivationEngine.java] — score-to-category lookup maps
- [GitHub #551] — focal issue
- [GitHub #550] — verify_corpus.py design
- [GitHub #538] — parent epic
- Decision review: /Users/mdproctor/reviews/casehub-slots/issue-551-decision-20261012-013218/
- Spec review: /Users/mdproctor/reviews/casehub-slots/issue-551-spec-20261012-013637/
