# Activity/CRM Tracking — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #412 — feat: Phase 1 — Activity/CRM tracking with MindMap extensions
**Issue group:** #412

**Goal:** Extend MindMap with ACTIVITY and PLACE subgraph types, trait interfaces, a check-in API for recording "I was at X with Y", and CRM query services for relationship and place queries.

**Architecture:** All new code lives in existing modules — `mindmap-api` for subgraph type constants and vocabulary, `mindmap-intelligence` for trait interfaces, trait rules, check-in service, and query service. No new Maven modules. The check-in API composes existing MindMapStore operations (addNode, addEdge, resolveNode) into a higher-level domain operation. CRM queries compose MindMapStore search and neighbor traversal.

**Tech Stack:** Java 21, MindMap SPI (MindMapStore, NodeInput, EdgeInput, MindMapQuery), CDI (ApplicationScoped, Instance), JUnit 5, AssertJ, InMemoryMindMapStore for tests.

## Global Constraints

- Java 21 source level, Java 26 JVM
- Zero new Maven modules — extend existing `mindmap-api` and `mindmap-intelligence`
- All trait interfaces return `Optional<String>` (established pattern)
- SubgraphTypes uses lowercase string constants (established pattern)
- TraitRules are `@ApplicationScoped` CDI beans implementing `TraitRule` (established pattern)
- Vocabulary follows GoalVocabulary builder pattern (established pattern)
- Tests use `InMemoryMindMapStore` — no Docker, no CDI container
- `tenantId` is always the last parameter (SPI verb convention from #363)

---

## Batch 1: Foundation — Subgraph Types, Vocabulary, Traits, and Trait Rules

### Task 1: Add ACTIVITY and PLACE subgraph types + ActivityVocabulary

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActivityVocabulary.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/ActivityVocabularyTest.java`

**Interfaces:**
- Produces: `SubgraphTypes.ACTIVITY` ("activity"), `SubgraphTypes.PLACE` ("place") constants used by Tasks 2-4
- Produces: `ActivityVocabulary.ACTIVITY_VOCABULARY` — edge types "participated", "at", "occasion" used by Tasks 3-4

- [ ] **Step 1: Write the failing test for ActivityVocabulary**

```java
package io.casehub.neocortex.mindmap;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class ActivityVocabularyTest {

    @Test
    void vocabulary_containsThreeEdgeTypes() {
        var vocab = ActivityVocabulary.ACTIVITY_VOCABULARY;
        assertThat(vocab.edgeTypes()).hasSize(3);
    }

    @Test
    void participated_hasAliases() {
        var vocab = ActivityVocabulary.ACTIVITY_VOCABULARY;
        var participated = vocab.edgeTypes().stream()
            .filter(e -> "participated".equals(e.canonical()))
            .findFirst().orElseThrow();
        assertThat(participated.aliases()).containsExactlyInAnyOrder("took-part-in", "attended");
    }

    @Test
    void at_hasAliases() {
        var vocab = ActivityVocabulary.ACTIVITY_VOCABULARY;
        var at = vocab.edgeTypes().stream()
            .filter(e -> "at".equals(e.canonical()))
            .findFirst().orElseThrow();
        assertThat(at.aliases()).containsExactlyInAnyOrder("held-at", "located-at");
    }

    @Test
    void occasion_hasAliases() {
        var vocab = ActivityVocabulary.ACTIVITY_VOCABULARY;
        var occasion = vocab.edgeTypes().stream()
            .filter(e -> "occasion".equals(e.canonical()))
            .findFirst().orElseThrow();
        assertThat(occasion.aliases()).containsExactlyInAnyOrder("linked-event", "calendar-event");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=ActivityVocabularyTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `ActivityVocabulary` does not exist

- [ ] **Step 3: Add SubgraphTypes constants and create ActivityVocabulary**

Add to `SubgraphTypes.java` after the GOAL constant:

```java
public static final String ACTIVITY  = "activity";
public static final String PLACE     = "place";
```

Create `ActivityVocabulary.java`:

```java
package io.casehub.neocortex.mindmap;

public final class ActivityVocabulary {

    public static final MindMapVocabulary ACTIVITY_VOCABULARY = MindMapVocabulary.builder()
            .edgeType("participated", "took-part-in", "attended")
            .edgeType("at", "held-at", "located-at")
            .edgeType("occasion", "linked-event", "calendar-event")
            .build();

    private ActivityVocabulary() {}
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=ActivityVocabularyTest`
Expected: all 4 tests pass

- [ ] **Step 5: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ActivityVocabulary.java
git add mindmap-api/src/test/java/io/casehub/neocortex/mindmap/ActivityVocabularyTest.java
git commit -m "feat(#412): add ACTIVITY/PLACE subgraph types and ActivityVocabulary

Refs #412"
```

---

### Task 2: Add Locatable, Reviewable, Temporal trait interfaces + trait rules + tests

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Locatable.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Reviewable.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Temporal.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/LocatableTraitRule.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ReviewableTraitRule.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TemporalTraitRule.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/StandardTraitRulesTest.java`

**Interfaces:**
- Consumes: `SubgraphTypes.ACTIVITY`, `SubgraphTypes.PLACE` from Task 1
- Produces: `Locatable` (lat, lng, address, category, hours, phone, website), `Reviewable` (rating, reviewCount, priceRange), `Temporal` (date, duration, activityType, notes) — trait interfaces used by consumers via `Thing.as(Locatable.class)`
- Produces: `LocatableTraitRule`, `ReviewableTraitRule`, `TemporalTraitRule` — CDI beans for automatic trait detection

- [ ] **Step 1: Write failing tests for all three trait rules**

Add to `StandardTraitRulesTest.java`:

```java
@Test
void locatableRule_matchesLatLng() {
    String id = store.addNode(new NodeInput("Ondine", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("lat", "55.9533", "lng", "-3.1883")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    var rule = new LocatableTraitRule();
    assertThat(rule.traitName()).isEqualTo("Locatable");
    assertThat(rule.matches(node, List.of())).isTrue();
}

@Test
void locatableRule_matchesAddress() {
    String id = store.addNode(new NodeInput("Ondine", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("address", "2 George IV Bridge")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    assertThat(new LocatableTraitRule().matches(node, List.of())).isTrue();
}

@Test
void locatableRule_noMatch() {
    String id = store.addNode(node("Widget"), "t1");
    MindMapNode node = store.getNode(id, "t1");
    assertThat(new LocatableTraitRule().matches(node, List.of())).isFalse();
}

@Test
void reviewableRule_matchesRating() {
    String id = store.addNode(new NodeInput("Ondine", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("rating", "4.5")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    var rule = new ReviewableTraitRule();
    assertThat(rule.traitName()).isEqualTo("Reviewable");
    assertThat(rule.matches(node, List.of())).isTrue();
}

@Test
void reviewableRule_matchesPriceRange() {
    String id = store.addNode(new NodeInput("Ondine", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("priceRange", "£££")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    assertThat(new ReviewableTraitRule().matches(node, List.of())).isTrue();
}

@Test
void reviewableRule_noMatch() {
    String id = store.addNode(node("Widget"), "t1");
    MindMapNode node = store.getNode(id, "t1");
    assertThat(new ReviewableTraitRule().matches(node, List.of())).isFalse();
}

@Test
void temporalRule_matchesDate() {
    String id = store.addNode(new NodeInput("Dinner", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("date", "2026-10-01")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    var rule = new TemporalTraitRule();
    assertThat(rule.traitName()).isEqualTo("Temporal");
    assertThat(rule.matches(node, List.of())).isTrue();
}

@Test
void temporalRule_matchesDuration() {
    String id = store.addNode(new NodeInput("Run", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("duration", "PT1H30M")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    assertThat(new TemporalTraitRule().matches(node, List.of())).isTrue();
}

@Test
void temporalRule_noMatch() {
    String id = store.addNode(node("Widget"), "t1");
    MindMapNode node = store.getNode(id, "t1");
    assertThat(new TemporalTraitRule().matches(node, List.of())).isFalse();
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=StandardTraitRulesTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `LocatableTraitRule`, `ReviewableTraitRule`, `TemporalTraitRule` do not exist

- [ ] **Step 3: Create trait interfaces**

`Locatable.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Locatable {
    Optional<String> lat();
    Optional<String> lng();
    Optional<String> address();
    Optional<String> category();
    Optional<String> hours();
    Optional<String> phone();
    Optional<String> website();
}
```

`Reviewable.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Reviewable {
    Optional<String> rating();
    Optional<String> reviewCount();
    Optional<String> priceRange();
}
```

`Temporal.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Temporal {
    Optional<String> date();
    Optional<String> duration();
    Optional<String> activityType();
    Optional<String> notes();
}
```

- [ ] **Step 4: Create trait rules**

`LocatableTraitRule.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class LocatableTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Locatable"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        return (node.property("lat").isPresent() && node.property("lng").isPresent())
            || node.property("address").isPresent();
    }
}
```

`ReviewableTraitRule.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class ReviewableTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Reviewable"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        return node.property("rating").isPresent()
            || node.property("reviewCount").isPresent()
            || node.property("priceRange").isPresent();
    }
}
```

`TemporalTraitRule.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class TemporalTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Temporal"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        return node.property("date").isPresent()
            || node.property("duration").isPresent();
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=StandardTraitRulesTest`
Expected: all tests pass (including the 9 new ones)

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Locatable.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Reviewable.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Temporal.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/LocatableTraitRule.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ReviewableTraitRule.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TemporalTraitRule.java
git add mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/StandardTraitRulesTest.java
git commit -m "feat(#412): add Locatable, Reviewable, Temporal traits and trait rules

Refs #412"
```

---

## Batch 2: Check-In API

### Task 3: CheckInService — explicit "I was at X with Y"

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInRequest.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInResult.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInService.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CheckInServiceTest.java`

**Interfaces:**
- Consumes: `SubgraphTypes.ACTIVITY`, `SubgraphTypes.PLACE`, `SubgraphTypes.PERSON` from Task 1/existing
- Consumes: `ActivityVocabulary.ACTIVITY_VOCABULARY` edge types from Task 1
- Produces: `CheckInRequest` record (placeName, participants, date, notes, activityType, placeProperties)
- Produces: `CheckInResult` record (activityNodeId, placeNodeId, participantEdgeIds)
- Produces: `CheckInService.checkIn(CheckInRequest, String tenantId)` → `CheckInResult`

The service:
1. Resolves or creates a PLACE node (by name resolution in PLACE subgraphs)
2. Resolves or creates PERSON nodes for each participant
3. Creates an ACTIVITY node with date, notes, activityType properties
4. Links ACTIVITY → PLACE via "at" edge
5. Links each PERSON → ACTIVITY via "participated" edge (with per-person properties from the request)

- [ ] **Step 1: Write CheckInRequest and CheckInResult records**

`CheckInRequest.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public record CheckInRequest(
        String activityName,
        String placeName,
        List<Participant> participants,
        Instant date,
        String activityType,
        String notes,
        Map<String, String> placeProperties
) {
    public CheckInRequest {
        Objects.requireNonNull(activityName, "activityName");
        Objects.requireNonNull(placeName, "placeName");
        participants = participants == null ? List.of() : List.copyOf(participants);
        placeProperties = placeProperties == null ? Map.of() : Map.copyOf(placeProperties);
    }

    public record Participant(String name, Map<String, String> edgeProperties) {
        public Participant {
            Objects.requireNonNull(name, "name");
            edgeProperties = edgeProperties == null ? Map.of() : Map.copyOf(edgeProperties);
        }

        public Participant(String name) { this(name, Map.of()); }
    }

    public static CheckInRequest of(String activityName, String placeName) {
        return new CheckInRequest(activityName, placeName, List.of(),
                                  Instant.now(), null, null, Map.of());
    }

    public CheckInRequest withParticipants(List<Participant> participants) {
        return new CheckInRequest(activityName, placeName, participants,
                                  date, activityType, notes, placeProperties);
    }

    public CheckInRequest withDate(Instant date) {
        return new CheckInRequest(activityName, placeName, participants,
                                  date, activityType, notes, placeProperties);
    }

    public CheckInRequest withActivityType(String activityType) {
        return new CheckInRequest(activityName, placeName, participants,
                                  date, activityType, notes, placeProperties);
    }

    public CheckInRequest withNotes(String notes) {
        return new CheckInRequest(activityName, placeName, participants,
                                  date, activityType, notes, placeProperties);
    }

    public CheckInRequest withPlaceProperties(Map<String, String> placeProperties) {
        return new CheckInRequest(activityName, placeName, participants,
                                  date, activityType, notes, placeProperties);
    }
}
```

`CheckInResult.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.List;
import java.util.Objects;

public record CheckInResult(
        String activityNodeId,
        String placeNodeId,
        List<String> participantEdgeIds
) {
    public CheckInResult {
        Objects.requireNonNull(activityNodeId, "activityNodeId");
        Objects.requireNonNull(placeNodeId, "placeNodeId");
        participantEdgeIds = participantEdgeIds == null ? List.of() : List.copyOf(participantEdgeIds);
    }
}
```

- [ ] **Step 2: Write failing tests for CheckInService**

`CheckInServiceTest.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.SubgraphInput;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class CheckInServiceTest {

    private static final String TENANT = "t1";
    private InMemoryMindMapStore store;
    private CheckInService service;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        service = new CheckInService(store);
    }

    @Test
    void checkIn_createsActivityNode() {
        var request = CheckInRequest.of("Dinner at Ondine", "Ondine")
            .withDate(Instant.parse("2026-10-01T19:00:00Z"))
            .withActivityType("dining")
            .withNotes("great lobster");

        CheckInResult result = service.checkIn(request, TENANT);

        MindMapNode activity = store.getNode(result.activityNodeId(), TENANT);
        assertThat(activity.name()).isEqualTo("Dinner at Ondine");
        assertThat(activity.subgraphType()).isEqualTo(SubgraphTypes.ACTIVITY);
        assertThat(activity.property("activityType")).hasValue("dining");
        assertThat(activity.property("notes")).hasValue("great lobster");
        assertThat(activity.property("date")).hasValue("2026-10-01T19:00:00Z");
    }

    @Test
    void checkIn_createsPlaceNode() {
        var request = CheckInRequest.of("Dinner at Ondine", "Ondine")
            .withPlaceProperties(Map.of("address", "2 George IV Bridge", "category", "restaurant"));

        CheckInResult result = service.checkIn(request, TENANT);

        MindMapNode place = store.getNode(result.placeNodeId(), TENANT);
        assertThat(place.name()).isEqualTo("Ondine");
        assertThat(place.subgraphType()).isEqualTo(SubgraphTypes.PLACE);
        assertThat(place.property("address")).hasValue("2 George IV Bridge");
        assertThat(place.property("category")).hasValue("restaurant");
    }

    @Test
    void checkIn_linksActivityToPlace() {
        var request = CheckInRequest.of("Dinner at Ondine", "Ondine");

        CheckInResult result = service.checkIn(request, TENANT);

        List<MindMapEdge> edges = store.neighbors(result.activityNodeId(), "at", TENANT);
        assertThat(edges).hasSize(1);
        assertThat(edges.getFirst().targetNodeId()).isEqualTo(result.placeNodeId());
    }

    @Test
    void checkIn_linksParticipants() {
        var request = CheckInRequest.of("Dinner at Ondine", "Ondine")
            .withParticipants(List.of(
                new CheckInRequest.Participant("Sarah", Map.of("recommended", "true")),
                new CheckInRequest.Participant("Tom")));

        CheckInResult result = service.checkIn(request, TENANT);

        assertThat(result.participantEdgeIds()).hasSize(2);
        List<MindMapEdge> participantEdges = store.neighbors(result.activityNodeId(), "participated", TENANT);
        assertThat(participantEdges).hasSize(2);
    }

    @Test
    void checkIn_participantEdgeCarriesProperties() {
        var request = CheckInRequest.of("Dinner at Ondine", "Ondine")
            .withParticipants(List.of(
                new CheckInRequest.Participant("Sarah", Map.of("rating", "5", "recommended", "true"))));

        CheckInResult result = service.checkIn(request, TENANT);

        MindMapEdge edge = store.getEdge(result.participantEdgeIds().getFirst(), TENANT);
        assertThat(edge.edgeType()).isEqualTo("participated");
        assertThat(edge.property("rating")).hasValue("5");
        assertThat(edge.property("recommended")).hasValue("true");
    }

    @Test
    void checkIn_reusesExistingPlace() {
        var first = CheckInRequest.of("Lunch at Ondine", "Ondine");
        CheckInResult r1 = service.checkIn(first, TENANT);

        var second = CheckInRequest.of("Dinner at Ondine", "Ondine");
        CheckInResult r2 = service.checkIn(second, TENANT);

        assertThat(r2.placeNodeId()).isEqualTo(r1.placeNodeId());
    }

    @Test
    void checkIn_reusesExistingPerson() {
        var first = CheckInRequest.of("Lunch", "Ondine")
            .withParticipants(List.of(new CheckInRequest.Participant("Sarah")));
        service.checkIn(first, TENANT);

        var second = CheckInRequest.of("Dinner", "Costa")
            .withParticipants(List.of(new CheckInRequest.Participant("Sarah")));
        CheckInResult r2 = service.checkIn(second, TENANT);

        List<MindMapNode> persons = store.search(
            io.casehub.neocortex.mindmap.MindMapQuery.of(TENANT, 10)
                .withText("Sarah").withType(SubgraphTypes.PERSON));
        assertThat(persons).hasSize(1);
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CheckInServiceTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `CheckInService` does not exist

- [ ] **Step 4: Implement CheckInService**

`CheckInService.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.mindmap.EdgeInput;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.SubgraphInput;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@ApplicationScoped
public class CheckInService {

    private final MindMapStore store;

    @Inject
    public CheckInService(MindMapStore store) {
        this.store = store;
    }

    public CheckInResult checkIn(CheckInRequest request, String tenantId) {
        String placeNodeId = resolveOrCreatePlace(request, tenantId);
        String activityNodeId = createActivity(request, placeNodeId, tenantId);
        List<String> participantEdgeIds = linkParticipants(request, activityNodeId, tenantId);
        return new CheckInResult(activityNodeId, placeNodeId, participantEdgeIds);
    }

    private String resolveOrCreatePlace(CheckInRequest request, String tenantId) {
        String subgraphId = ensureSubgraph(SubgraphTypes.PLACE, tenantId);
        MindMapNode existing = store.resolveNode(request.placeName(), subgraphId, tenantId);
        if (existing != null) {
            return existing.id();
        }
        Map<String, String> props = new HashMap<>(request.placeProperties());
        return store.addNode(
            NodeInput.of(request.placeName(), subgraphId)
                .withProperties(props)
                .withProvenance("check-in"),
            tenantId);
    }

    private String createActivity(CheckInRequest request, String placeNodeId, String tenantId) {
        String subgraphId = ensureSubgraph(SubgraphTypes.ACTIVITY, tenantId);
        Map<String, String> props = new HashMap<>();
        if (request.date() != null) props.put("date", request.date().toString());
        if (request.activityType() != null) props.put("activityType", request.activityType());
        if (request.notes() != null) props.put("notes", request.notes());

        String activityId = store.addNode(
            NodeInput.of(request.activityName(), subgraphId)
                .withProperties(props)
                .withValidFrom(request.date())
                .withProvenance("check-in"),
            tenantId);

        store.addEdge(EdgeInput.of(activityId, placeNodeId, "at")
                .withProvenance("check-in"), tenantId);

        return activityId;
    }

    private List<String> linkParticipants(CheckInRequest request, String activityNodeId, String tenantId) {
        List<String> edgeIds = new ArrayList<>();
        String personSubgraphId = ensureSubgraph(SubgraphTypes.PERSON, tenantId);
        for (var participant : request.participants()) {
            String personId = resolveOrCreatePerson(participant.name(), personSubgraphId, tenantId);
            String edgeId = store.addEdge(
                EdgeInput.of(personId, activityNodeId, "participated")
                    .withProperties(participant.edgeProperties())
                    .withProvenance("check-in"),
                tenantId);
            edgeIds.add(edgeId);
        }
        return edgeIds;
    }

    private String resolveOrCreatePerson(String name, String subgraphId, String tenantId) {
        MindMapNode existing = store.resolveNode(name, subgraphId, tenantId);
        if (existing != null) {
            return existing.id();
        }
        return store.addNode(
            NodeInput.of(name, subgraphId).withProvenance("check-in"),
            tenantId);
    }

    private String ensureSubgraph(String type, String tenantId) {
        return store.listSubgraphs(tenantId).stream()
            .filter(s -> type.equals(s.type()))
            .map(s -> s.id())
            .findFirst()
            .orElseGet(() -> store.createSubgraph(
                new SubgraphInput(type, type, null), tenantId));
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CheckInServiceTest`
Expected: all 7 tests pass

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInRequest.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInResult.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInService.java
git add mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CheckInServiceTest.java
git commit -m "feat(#412): add CheckInService for explicit activity recording

Refs #412"
```

---

## Batch 3: CRM Queries

### Task 4: ActivityQueryService — relationship and place queries

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ActivityQueryService.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ActivitySummary.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ActivityQueryServiceTest.java`

**Interfaces:**
- Consumes: `MindMapStore` (search, neighbors), `SubgraphTypes.ACTIVITY`, `SubgraphTypes.PLACE`, `SubgraphTypes.PERSON`
- Produces: `ActivityQueryService.lastSeenWith(String personName, String tenantId)` → `Optional<ActivitySummary>` — finds the most recent activity with a named person
- Produces: `ActivityQueryService.activitiesWithPerson(String personName, int limit, String tenantId)` → `List<ActivitySummary>` — all shared activities
- Produces: `ActivityQueryService.placesVisited(int limit, String tenantId)` → `List<MindMapNode>` — distinct places from activity "at" edges
- Produces: `ActivityQueryService.activitiesAtPlace(String placeName, int limit, String tenantId)` → `List<ActivitySummary>` — all activities at a place
- Produces: `ActivitySummary` record (activityNode, placeNode, participantNames, date)

- [ ] **Step 1: Write ActivitySummary record**

`ActivitySummary.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapNode;

import java.time.Instant;
import java.util.List;
import java.util.Objects;

public record ActivitySummary(
        MindMapNode activityNode,
        MindMapNode placeNode,
        List<String> participantNames,
        Instant date
) {
    public ActivitySummary {
        Objects.requireNonNull(activityNode, "activityNode");
        participantNames = participantNames == null ? List.of() : List.copyOf(participantNames);
    }
}
```

- [ ] **Step 2: Write failing tests**

`ActivityQueryServiceTest.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class ActivityQueryServiceTest {

    private static final String TENANT = "t1";
    private InMemoryMindMapStore store;
    private CheckInService checkInService;
    private ActivityQueryService queryService;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        checkInService = new CheckInService(store);
        queryService = new ActivityQueryService(store);
    }

    @Test
    void lastSeenWith_returnsLatestActivity() {
        checkInService.checkIn(
            CheckInRequest.of("Lunch", "Ondine")
                .withDate(Instant.parse("2026-09-01T12:00:00Z"))
                .withParticipants(List.of(new CheckInRequest.Participant("Sarah"))),
            TENANT);
        checkInService.checkIn(
            CheckInRequest.of("Dinner", "Costa")
                .withDate(Instant.parse("2026-10-01T19:00:00Z"))
                .withParticipants(List.of(new CheckInRequest.Participant("Sarah"))),
            TENANT);

        Optional<ActivitySummary> result = queryService.lastSeenWith("Sarah", TENANT);

        assertThat(result).isPresent();
        assertThat(result.get().activityNode().name()).isEqualTo("Dinner");
        assertThat(result.get().date()).isEqualTo(Instant.parse("2026-10-01T19:00:00Z"));
    }

    @Test
    void lastSeenWith_emptyWhenNeverMet() {
        Optional<ActivitySummary> result = queryService.lastSeenWith("Unknown", TENANT);
        assertThat(result).isEmpty();
    }

    @Test
    void activitiesWithPerson_returnsAllShared() {
        checkInService.checkIn(
            CheckInRequest.of("Lunch", "Ondine")
                .withDate(Instant.parse("2026-09-01T12:00:00Z"))
                .withParticipants(List.of(new CheckInRequest.Participant("Sarah"))),
            TENANT);
        checkInService.checkIn(
            CheckInRequest.of("Dinner", "Costa")
                .withDate(Instant.parse("2026-10-01T19:00:00Z"))
                .withParticipants(List.of(new CheckInRequest.Participant("Sarah"))),
            TENANT);
        checkInService.checkIn(
            CheckInRequest.of("Coffee", "Starbucks")
                .withDate(Instant.parse("2026-10-02T10:00:00Z"))
                .withParticipants(List.of(new CheckInRequest.Participant("Tom"))),
            TENANT);

        List<ActivitySummary> result = queryService.activitiesWithPerson("Sarah", 10, TENANT);
        assertThat(result).hasSize(2);
    }

    @Test
    void placesVisited_returnsDistinctPlaces() {
        checkInService.checkIn(CheckInRequest.of("Lunch 1", "Ondine"), TENANT);
        checkInService.checkIn(CheckInRequest.of("Lunch 2", "Ondine"), TENANT);
        checkInService.checkIn(CheckInRequest.of("Coffee", "Costa"), TENANT);

        List<MindMapNode> places = queryService.placesVisited(10, TENANT);
        assertThat(places).hasSize(2);
        assertThat(places).extracting(MindMapNode::name)
            .containsExactlyInAnyOrder("Ondine", "Costa");
    }

    @Test
    void activitiesAtPlace_returnsAll() {
        checkInService.checkIn(
            CheckInRequest.of("Lunch", "Ondine")
                .withDate(Instant.parse("2026-09-01T12:00:00Z")),
            TENANT);
        checkInService.checkIn(
            CheckInRequest.of("Dinner", "Ondine")
                .withDate(Instant.parse("2026-10-01T19:00:00Z")),
            TENANT);
        checkInService.checkIn(
            CheckInRequest.of("Coffee", "Costa")
                .withDate(Instant.parse("2026-10-02T10:00:00Z")),
            TENANT);

        List<ActivitySummary> result = queryService.activitiesAtPlace("Ondine", 10, TENANT);
        assertThat(result).hasSize(2);
        assertThat(result).extracting(s -> s.activityNode().name())
            .containsExactlyInAnyOrder("Lunch", "Dinner");
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ActivityQueryServiceTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `ActivityQueryService` does not exist

- [ ] **Step 4: Implement ActivityQueryService**

`ActivityQueryService.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.MindMapQuery;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;

import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;

@ApplicationScoped
public class ActivityQueryService {

    private final MindMapStore store;

    @Inject
    public ActivityQueryService(MindMapStore store) {
        this.store = store;
    }

    public Optional<ActivitySummary> lastSeenWith(String personName, String tenantId) {
        return activitiesWithPerson(personName, 1, tenantId).stream().findFirst();
    }

    public List<ActivitySummary> activitiesWithPerson(String personName, int limit, String tenantId) {
        MindMapNode person = findPerson(personName, tenantId);
        if (person == null) return List.of();

        List<MindMapEdge> participatedEdges = store.neighbors(person.id(), "participated", tenantId);
        List<ActivitySummary> summaries = new ArrayList<>();
        for (var edge : participatedEdges) {
            MindMapNode activity = store.getNode(edge.targetNodeId(), tenantId);
            if (activity != null) {
                summaries.add(buildSummary(activity, tenantId));
            }
        }
        summaries.sort(Comparator.comparing(
            (ActivitySummary s) -> s.date() != null ? s.date() : Instant.EPOCH).reversed());
        return summaries.size() > limit ? summaries.subList(0, limit) : summaries;
    }

    public List<MindMapNode> placesVisited(int limit, String tenantId) {
        List<MindMapNode> activities = store.search(
            MindMapQuery.of(tenantId, 1000).withType(SubgraphTypes.ACTIVITY));
        Set<String> seenPlaceIds = new LinkedHashSet<>();
        List<MindMapNode> places = new ArrayList<>();
        for (var activity : activities) {
            List<MindMapEdge> atEdges = store.neighbors(activity.id(), "at", tenantId);
            for (var edge : atEdges) {
                if (seenPlaceIds.add(edge.targetNodeId())) {
                    MindMapNode place = store.getNode(edge.targetNodeId(), tenantId);
                    if (place != null) places.add(place);
                }
            }
        }
        return places.size() > limit ? places.subList(0, limit) : places;
    }

    public List<ActivitySummary> activitiesAtPlace(String placeName, int limit, String tenantId) {
        MindMapNode place = findPlace(placeName, tenantId);
        if (place == null) return List.of();

        List<MindMapNode> activities = store.search(
            MindMapQuery.of(tenantId, 1000).withType(SubgraphTypes.ACTIVITY));
        List<ActivitySummary> summaries = new ArrayList<>();
        for (var activity : activities) {
            List<MindMapEdge> atEdges = store.neighbors(activity.id(), "at", tenantId);
            boolean atThisPlace = atEdges.stream()
                .anyMatch(e -> e.targetNodeId().equals(place.id()));
            if (atThisPlace) {
                summaries.add(buildSummary(activity, tenantId));
            }
        }
        summaries.sort(Comparator.comparing(
            (ActivitySummary s) -> s.date() != null ? s.date() : Instant.EPOCH).reversed());
        return summaries.size() > limit ? summaries.subList(0, limit) : summaries;
    }

    private ActivitySummary buildSummary(MindMapNode activity, String tenantId) {
        MindMapNode placeNode = null;
        List<MindMapEdge> atEdges = store.neighbors(activity.id(), "at", tenantId);
        if (!atEdges.isEmpty()) {
            placeNode = store.getNode(atEdges.getFirst().targetNodeId(), tenantId);
        }
        List<MindMapEdge> participatedEdges = store.neighbors(activity.id(), "participated", tenantId);
        List<String> names = participatedEdges.stream()
            .map(e -> store.getNode(e.sourceNodeId(), tenantId))
            .filter(n -> n != null)
            .map(MindMapNode::name)
            .toList();
        Instant date = activity.property("date")
            .map(Instant::parse)
            .orElse(activity.validFrom());
        return new ActivitySummary(activity, placeNode, names, date);
    }

    private MindMapNode findPerson(String name, String tenantId) {
        return store.listSubgraphs(tenantId).stream()
            .filter(s -> SubgraphTypes.PERSON.equals(s.type()))
            .map(s -> store.resolveNode(name, s.id(), tenantId))
            .filter(n -> n != null)
            .findFirst().orElse(null);
    }

    private MindMapNode findPlace(String name, String tenantId) {
        return store.listSubgraphs(tenantId).stream()
            .filter(s -> SubgraphTypes.PLACE.equals(s.type()))
            .map(s -> store.resolveNode(name, s.id(), tenantId))
            .filter(n -> n != null)
            .findFirst().orElse(null);
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ActivityQueryServiceTest`
Expected: all 5 tests pass

- [ ] **Step 6: Run full module test suite to check for regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,mindmap-intelligence`
Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ActivitySummary.java
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ActivityQueryService.java
git add mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ActivityQueryServiceTest.java
git commit -m "feat(#412): add ActivityQueryService for CRM queries

Closes #412"
```

---

## References

- [2026-10-03-real-world-knowledge-platform-design.md] — design spec §4 (MindMap Extensions) and §9 (Phase 1 scope)
- [decisions.md] — 13 validated decisions (D1–D13) in connectors repo
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java` — existing subgraph type constants
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/GoalVocabulary.java` — vocabulary pattern
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Personable.java` — trait interface pattern
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/PersonableTraitRule.java` — trait rule pattern
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridge.java` — CDI service pattern
- `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/StandardTraitRulesTest.java` — test pattern
- GitHub #412 — focal issue
