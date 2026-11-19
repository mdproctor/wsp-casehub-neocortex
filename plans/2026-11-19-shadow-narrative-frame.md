# Shadow Narrative Frame — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1058 — Shadow narrative frame: classify behavioural attractors as degraded archetype expression
**Issue group:** #1058

**Goal:** Annotate BEHAVIORAL attractor nodes with situational formation context (mode, facet displacements, archetype) and enhance `ShadowArchetypePromptSection` to render configurable, relevance-ranked displaced personality state with archetype context.

**Architecture:** A `SituationalSnapshotAccessor` SPI in cognition-api bridges the module boundary so `BehavioralSynthesisPhase` (mindmap-intelligence) can read the situational snapshot. Attractor nodes gain situational properties at formation time. `ShadowArchetypePromptSection` (cognition) is enhanced with a `ShadowFrameConfig` and `FacetRelevanceScorer` to render the top-N most relevant displaced facets.

**Tech Stack:** Java 21, Quarkus CDI, JUnit 5 + AssertJ

## Global Constraints

- `BehavioralSynthesisPhase` is in `mindmap-intelligence` — CANNOT import from `cognition` (circular dependency)
- `PipelineTrace.SituationalPersonalitySnapshot` is in `cognition-api` — shared by both modules
- `ShadowArchetypePromptSection` is NOT a CDI bean — constructed by `CognitionCore` with a `BiFunction`
- AMPD facet names in MindMap properties: kebab-case
- Use `Instance<T>` for graceful degradation on optional dependencies

---

## Batch 1: Snapshot accessor SPI

### Task 1: SituationalSnapshotAccessor SPI + CDI wiring

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/SituationalSnapshotAccessor.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/SituationalSnapshotAccessorTest.java`

**Interfaces:**
- Produces: `SituationalSnapshotAccessor` — `@FunctionalInterface`, single method `Optional<SituationalPersonalitySnapshot> currentSnapshot(String agentId, String tenantId)`
- Produces: `@DefaultBean @Singleton` producer in `CognitionDefaultBeans` returning no-op (empty optional)

- [ ] **Step 1: Write test for SPI contract**

```java
package io.casehub.neocortex.cognition;

import io.casehub.neocortex.cognition.trace.PipelineTrace.SituationalPersonalitySnapshot;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;

class SituationalSnapshotAccessorTest {

    @Test
    void noOpReturnsEmpty() {
        SituationalSnapshotAccessor accessor = (agentId, tenantId) -> Optional.empty();
        assertThat(accessor.currentSnapshot("agent-1", "tenant-1")).isEmpty();
    }

    @Test
    void returnsSnapshotWhenAvailable() {
        var snapshot = new SituationalPersonalitySnapshot(
            Map.of("STRESS", 0.72),
            "STRESS", null,
            Map.of("anxiousness", 0.15, "emotional-lability", 0.12),
            2
        );
        SituationalSnapshotAccessor accessor = (agentId, tenantId) -> Optional.of(snapshot);
        var result = accessor.currentSnapshot("agent-1", "tenant-1");
        assertThat(result).isPresent();
        assertThat(result.get().affectiveWinner()).isEqualTo("STRESS");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest="SituationalSnapshotAccessorTest" -f pom.xml`

Expected: compilation error — `SituationalSnapshotAccessor` does not exist.

- [ ] **Step 3: Create the SPI**

Create `cognition-api/src/main/java/io/casehub/neocortex/cognition/SituationalSnapshotAccessor.java`:

```java
package io.casehub.neocortex.cognition;

import io.casehub.neocortex.cognition.trace.PipelineTrace.SituationalPersonalitySnapshot;

import java.util.Optional;

@FunctionalInterface
public interface SituationalSnapshotAccessor {
    Optional<SituationalPersonalitySnapshot> currentSnapshot(String agentId, String tenantId);
}
```

- [ ] **Step 4: Add @DefaultBean producer in CognitionDefaultBeans**

In `CognitionDefaultBeans.java`, add a producer method:

```java
@Produces @DefaultBean @Singleton
SituationalSnapshotAccessor situationalSnapshotAccessor() {
    return (agentId, tenantId) -> Optional.empty();
}
```

Add import: `import io.casehub.neocortex.cognition.SituationalSnapshotAccessor;`

- [ ] **Step 5: Wire real implementation in CognitionCore**

In `CognitionCore`, after `situationalPersonalityParticipant` is created, add a method that exposes the participant's snapshot as a CDI-override producer. Since CognitionCore is `@ApplicationScoped`, it can produce:

```java
@Produces @ApplicationScoped
SituationalSnapshotAccessor realSituationalSnapshotAccessor() {
    if (situationalPersonalityParticipant != null) {
        return (agentId, tenantId) -> situationalPersonalityParticipant.currentSnapshot(agentId, tenantId);
    }
    return (agentId, tenantId) -> Optional.empty();
}
```

This overrides the `@DefaultBean` from `CognitionDefaultBeans` when `CognitionCore` is active.

- [ ] **Step 6: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest="SituationalSnapshotAccessorTest"`

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/SituationalSnapshotAccessor.java cognition-api/src/test/java/io/casehub/neocortex/cognition/SituationalSnapshotAccessorTest.java cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java cognition/src/main/java/io/casehub/neocortex/cognition/CognitionCore.java
git commit -m "feat(#1058): SituationalSnapshotAccessor SPI bridging cognition to consolidation

FunctionalInterface in cognition-api so mindmap-intelligence can
read situational personality state without circular dependency.

Refs #1058

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 2: Attractor context capture

### Task 2: BehavioralSynthesisPhase writes situational properties on attractor nodes

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhaseTest.java`

**Interfaces:**
- Consumes: `SituationalSnapshotAccessor` from Task 1 (via `Instance<>`)
- Consumes: `MindMapStore` (existing) for archetype-family lookup
- Produces: attractor nodes with additional properties: `situational-mode`, `situational-social-mode`, `situational-intensity`, `displaced-facets`, `archetype-family`

- [ ] **Step 1: Write failing test for situational properties on new attractor**

Add to `BehavioralSynthesisPhaseTest.java`:

```java
@Test
void newAttractorCarriesSituationalContext() {
    var store = new InMemoryMindMapStore();
    var sgId = store.createSubgraph("BEHAVIORAL", "behavioral", TENANT).id();
    var cognitiveSgId = store.createSubgraph("COGNITIVE", "cognitive", TENANT).id();
    var personSgId = store.createSubgraph("PERSON", "person", TENANT).id();

    // Create person node with archetype
    var personNode = store.addNode(
        NodeInput.of("test-agent", personSgId)
            .withProperties(Map.of("archetype-1-family", "creator"))
            .withProvenance("test"),
        TENANT
    );

    // Create graduated cognitive node
    store.addNode(
        NodeInput.of("graduated-experience", cognitiveSgId)
            .withProperties(Map.of(
                "agent-id", "test-agent",
                "source-memory-id", "mem-1",
                "cognitiveKind", "belief"
            ))
            .withTraits(Set.of("graduated-sub-thought"))
            .withProvenance("test"),
        TENANT
    );

    var snapshot = new SituationalPersonalitySnapshot(
        Map.of("STRESS", 0.72),
        "STRESS", null,
        Map.of("anxiousness", 0.15, "emotional-lability", 0.12),
        2
    );
    SituationalSnapshotAccessor accessor = (a, t) -> Optional.of(snapshot);

    var capsEngine = new StubCapsEngine();
    var classifier = new StubClassifier();
    var phase = new BehavioralSynthesisPhase(store, capsEngine, classifier, 20, null, null, accessor);
    phase.run(TENANT, List.of("COGNITIVE"));

    var attractors = store.search(
        MindMapQuery.forTenant(TENANT).withTraits(Set.of("CapsGenerated")).build()
    );
    assertThat(attractors).isNotEmpty();
    var attractor = attractors.getFirst();
    assertThat(attractor.properties()).containsEntry("situational-mode", "STRESS");
    assertThat(attractor.properties()).containsEntry("situational-intensity", "0.72");
    assertThat(attractor.properties()).containsEntry("archetype-family", "creator");
    assertThat(attractor.properties()).containsKey("displaced-facets");
    assertThat(attractor.properties().get("displaced-facets")).contains("anxiousness:0.15");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="BehavioralSynthesisPhaseTest#newAttractorCarriesSituationalContext"`

Expected: compilation error — constructor doesn't accept `SituationalSnapshotAccessor`.

- [ ] **Step 3: Add SituationalSnapshotAccessor injection to BehavioralSynthesisPhase**

Add field:

```java
private final Instance<SituationalSnapshotAccessor> snapshotAccessor;
```

Update CDI constructor to include `Instance<SituationalSnapshotAccessor> snapshotAccessor`. Update test constructor to accept `SituationalSnapshotAccessor accessor` (nullable, wrap in a simple holder).

- [ ] **Step 4: Add helper methods for situational context**

Add to BehavioralSynthesisPhase:

```java
private Map<String, String> buildSituationalProperties(String agentId, String tenantId) {
    var props = new HashMap<String, String>();
    if (snapshotAccessor != null && snapshotAccessor.isResolvable()) {
        snapshotAccessor.get().currentSnapshot(agentId, tenantId).ifPresent(snapshot -> {
            if (snapshot.affectiveWinner() != null) {
                props.put("situational-mode", snapshot.affectiveWinner());
                Double intensity = snapshot.modeIntensities().get(snapshot.affectiveWinner());
                if (intensity != null) props.put("situational-intensity", String.valueOf(intensity));
            }
            if (snapshot.socialWinner() != null) {
                props.put("situational-social-mode", snapshot.socialWinner());
            }
            if (!snapshot.facetDisplacements().isEmpty()) {
                String displaced = snapshot.facetDisplacements().entrySet().stream()
                    .filter(e -> Math.abs(e.getValue()) >= 0.01)
                    .sorted(Comparator.comparingDouble((Map.Entry<String, Double> e) -> Math.abs(e.getValue())).reversed())
                    .limit(8)
                    .map(e -> e.getKey() + ":" + String.format("%.2f", e.getValue()))
                    .collect(Collectors.joining(","));
                if (!displaced.isEmpty()) props.put("displaced-facets", displaced);
            }
        });
    }
    // Archetype family from PERSON node
    resolveArchetypeFamily(agentId, tenantId).ifPresent(family ->
        props.put("archetype-family", family));
    return props;
}

private Optional<String> resolveArchetypeFamily(String agentId, String tenantId) {
    var query = MindMapQuery.forTenant(tenantId)
        .inSubgraph("PERSON")
        .withText(agentId)
        .withLimit(1)
        .build();
    var nodes = store.search(query);
    if (nodes.isEmpty()) return Optional.empty();
    return Optional.ofNullable(nodes.getFirst().properties().get("archetype-1-family"));
}
```

- [ ] **Step 5: Wire situational properties into createOrStrengthenAttractor**

In `createOrStrengthenAttractor()`, after building the base properties map, merge the situational properties:

```java
var sitProps = buildSituationalProperties(agentId, tenantId);
props.putAll(sitProps);
```

Do this for both the new-node and existing-node paths.

- [ ] **Step 6: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="BehavioralSynthesisPhaseTest#newAttractorCarriesSituationalContext"`

Expected: PASS

- [ ] **Step 7: Run all BehavioralSynthesisPhase tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="BehavioralSynthesisPhaseTest"`

Expected: all existing tests still PASS (new accessor is null/empty in existing test constructors — graceful degradation).

- [ ] **Step 8: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhaseTest.java
git commit -m "feat(#1058): annotate attractor nodes with situational formation context

Writes situational-mode, displaced-facets, and archetype-family
properties on BEHAVIORAL nodes at synthesis time via snapshot accessor.

Refs #1058

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 3: Enhanced prompt rendering

### Task 3: ShadowFrameConfig + FacetRelevanceScorer

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/ShadowFrameConfig.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/FacetRelevanceScorer.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java` (add config producer)
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/situational/FacetRelevanceScorerTest.java`

**Interfaces:**
- Produces: `ShadowFrameConfig(int maxFacets, double minDisplacement, double modeRelevanceBoost, double attractorRelevanceBoost, Map<String, List<String>> attractorFacetCorrelations)`
- Produces: `FacetRelevanceScorer.score(Map<String, Double> displacements, String activeMode, Set<String> modeProfileFacets, String dominantAttractor, ShadowFrameConfig config) -> List<ScoredFacet>`
- Produces: `ScoredFacet(String facet, double displacement, double relevance, boolean modeCharacteristic, boolean attractorCorrelated)`

- [ ] **Step 1: Write failing test for relevance scoring**

```java
package io.casehub.neocortex.cognition.situational;

import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class FacetRelevanceScorerTest {

    private static final ShadowFrameConfig CONFIG = ShadowFrameConfig.defaults();

    @Test
    void modeCharacteristicFacetsRankHigher() {
        var displacements = Map.of(
            "anxiousness", 0.08,
            "grandiosity", 0.10
        );
        Set<String> modeProfileFacets = Set.of("anxiousness", "emotional-lability");
        var scored = FacetRelevanceScorer.score(displacements, "STRESS", modeProfileFacets, null, CONFIG);

        assertThat(scored).hasSize(2);
        assertThat(scored.getFirst().facet()).isEqualTo("anxiousness");
        assertThat(scored.getFirst().modeCharacteristic()).isTrue();
        assertThat(scored.get(1).facet()).isEqualTo("grandiosity");
        assertThat(scored.get(1).modeCharacteristic()).isFalse();
    }

    @Test
    void attractorCorrelatedFacetsGetBoosted() {
        var displacements = Map.of(
            "anxiousness", 0.08,
            "hostility", 0.09
        );
        var config = new ShadowFrameConfig(5, 0.05, 1.5, 1.3,
            Map.of("withdraw", List.of("anxiousness", "withdrawal", "intimacy-avoidance")));
        var scored = FacetRelevanceScorer.score(displacements, null, Set.of(), "withdraw", config);

        assertThat(scored.getFirst().facet()).isEqualTo("anxiousness");
        assertThat(scored.getFirst().attractorCorrelated()).isTrue();
    }

    @Test
    void belowMinDisplacementFiltered() {
        var displacements = Map.of(
            "anxiousness", 0.08,
            "grandiosity", 0.02
        );
        var scored = FacetRelevanceScorer.score(displacements, null, Set.of(), null, CONFIG);
        assertThat(scored).hasSize(1);
        assertThat(scored.getFirst().facet()).isEqualTo("anxiousness");
    }

    @Test
    void cappedAtMaxFacets() {
        var displacements = Map.of(
            "anxiousness", 0.5, "grandiosity", 0.4, "hostility", 0.3,
            "impulsivity", 0.2, "withdrawal", 0.15, "suspiciousness", 0.1,
            "risk-taking", 0.08
        );
        var config = new ShadowFrameConfig(3, 0.05, 1.5, 1.3, Map.of());
        var scored = FacetRelevanceScorer.score(displacements, null, Set.of(), null, config);
        assertThat(scored).hasSize(3);
    }

    @Test
    void combinedBoostsStack() {
        var displacements = Map.of(
            "anxiousness", 0.06,
            "hostility", 0.10
        );
        Set<String> modeProfileFacets = Set.of("anxiousness");
        var config = new ShadowFrameConfig(5, 0.05, 1.5, 1.3,
            Map.of("withdraw", List.of("anxiousness")));
        var scored = FacetRelevanceScorer.score(displacements, "STRESS", modeProfileFacets, "withdraw", config);

        // anxiousness: 0.06 * 1.5 * 1.3 = 0.117
        // hostility: 0.10 * 1.0 * 1.0 = 0.100
        assertThat(scored.getFirst().facet()).isEqualTo("anxiousness");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="FacetRelevanceScorerTest"`

Expected: compilation error.

- [ ] **Step 3: Create ShadowFrameConfig**

```java
package io.casehub.neocortex.cognition.situational;

import java.util.List;
import java.util.Map;

public record ShadowFrameConfig(
    int maxFacets,
    double minDisplacement,
    double modeRelevanceBoost,
    double attractorRelevanceBoost,
    Map<String, List<String>> attractorFacetCorrelations
) {
    public ShadowFrameConfig {
        attractorFacetCorrelations = attractorFacetCorrelations != null
            ? Map.copyOf(attractorFacetCorrelations) : Map.of();
    }

    public static ShadowFrameConfig defaults() {
        return new ShadowFrameConfig(5, 0.05, 1.5, 1.3, Map.ofEntries(
            Map.entry("withdraw", List.of("withdrawal", "anxiousness", "intimacy-avoidance")),
            Map.entry("fight", List.of("hostility", "impulsivity", "risk-taking")),
            Map.entry("flight", List.of("anxiousness", "withdrawal")),
            Map.entry("fawn", List.of("attention-seeking")),
            Map.entry("freeze", List.of("anxiousness", "emotional-lability")),
            Map.entry("trust", List.of("suspiciousness")),
            Map.entry("distrust", List.of("suspiciousness", "intimacy-avoidance")),
            Map.entry("approach", List.of("risk-taking", "grandiosity")),
            Map.entry("assert", List.of("hostility", "grandiosity")),
            Map.entry("submit", List.of("withdrawal", "anxiousness"))
        ));
    }
}
```

- [ ] **Step 4: Create FacetRelevanceScorer**

```java
package io.casehub.neocortex.cognition.situational;

import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class FacetRelevanceScorer {

    private FacetRelevanceScorer() {}

    public record ScoredFacet(
        String facet, double displacement, double relevance,
        boolean modeCharacteristic, boolean attractorCorrelated
    ) {}

    public static List<ScoredFacet> score(
            Map<String, Double> displacements,
            String activeMode,
            Set<String> modeProfileFacets,
            String dominantAttractor,
            ShadowFrameConfig config) {

        Set<String> attractorFacets = dominantAttractor != null
            ? Set.copyOf(config.attractorFacetCorrelations().getOrDefault(dominantAttractor, List.of()))
            : Set.of();

        return displacements.entrySet().stream()
            .filter(e -> Math.abs(e.getValue()) >= config.minDisplacement())
            .map(e -> {
                boolean modeBoosted = modeProfileFacets != null && modeProfileFacets.contains(e.getKey());
                boolean attractorBoosted = attractorFacets.contains(e.getKey());
                double modeBoost = modeBoosted ? config.modeRelevanceBoost() : 1.0;
                double attractorBoost = attractorBoosted ? config.attractorRelevanceBoost() : 1.0;
                double relevance = Math.abs(e.getValue()) * modeBoost * attractorBoost;
                return new ScoredFacet(e.getKey(), e.getValue(), relevance, modeBoosted, attractorBoosted);
            })
            .sorted(Comparator.comparingDouble(ScoredFacet::relevance).reversed())
            .limit(config.maxFacets())
            .toList();
    }
}
```

- [ ] **Step 5: Add @DefaultBean producer for ShadowFrameConfig**

In `CognitionDefaultBeans.java`:

```java
@Produces @DefaultBean @Singleton
ShadowFrameConfig shadowFrameConfig() {
    return ShadowFrameConfig.defaults();
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="FacetRelevanceScorerTest"`

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/situational/ShadowFrameConfig.java cognition/src/main/java/io/casehub/neocortex/cognition/situational/FacetRelevanceScorer.java cognition/src/test/java/io/casehub/neocortex/cognition/situational/FacetRelevanceScorerTest.java cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java
git commit -m "feat(#1058): ShadowFrameConfig + FacetRelevanceScorer for relevance-ranked facet rendering

Configurable scoring: |displacement| × modeBoost × attractorBoost.
Static attractor-facet correlation map on config, tunable defaults.

Refs #1058

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 4: Enhance ShadowArchetypePromptSection

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/ShadowArchetypePromptSection.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionCore.java` (updated wiring)
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/situational/ShadowArchetypePromptSectionTest.java`

**Interfaces:**
- Consumes: `SituationalPersonalitySnapshot` (via BiFunction accessor), `MindMapStore` (archetype + attractor lookup), `ShadowFrameConfig` (config), `FacetRelevanceScorer` (scoring)
- Produces: Rendered prompt section with mode, relevance-ranked facets, archetype family

- [ ] **Step 1: Write failing test for enhanced rendering**

Replace existing tests with enhanced versions in `ShadowArchetypePromptSectionTest.java`:

```java
@Test
void rendersRelevanceRankedFacetsWithArchetype() {
    var snapshot = new SituationalPersonalitySnapshot(
        Map.of("STRESS", 0.72),
        "STRESS", null,
        Map.of("anxiousness", 0.15, "emotional-lability", 0.12, "hostility", 0.08, "grandiosity", 0.03),
        3
    );
    var store = new InMemoryMindMapStore();
    var personSgId = store.createSubgraph("PERSON", "person", "t1").id();
    store.addNode(NodeInput.of("agent-1", personSgId)
        .withProperties(Map.of("archetype-1-family", "creator"))
        .withProvenance("test"), "t1");

    Set<String> modeProfileFacets = Set.of("anxiousness", "emotional-lability");
    var config = ShadowFrameConfig.defaults();

    var section = new ShadowArchetypePromptSection(
        (a, t) -> Optional.of(snapshot),
        store,
        config,
        (agentId, tenantId, mode) -> modeProfileFacets
    );
    var result = section.render("agent-1", "t1");

    assertThat(result).isNotNull();
    assertThat(result).contains("stress");
    assertThat(result).contains("72%");
    assertThat(result).contains("anxiousness");
    assertThat(result).contains("emotional-lability");
    assertThat(result).contains("Creator");
    assertThat(result).doesNotContain("grandiosity"); // below threshold after scoring
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: constructor mismatch — old constructor takes only BiFunction.

- [ ] **Step 3: Rewrite ShadowArchetypePromptSection**

The section needs four dependencies:
1. `BiFunction<String, String, Optional<SituationalPersonalitySnapshot>>` — snapshot accessor (existing)
2. `MindMapStore` — for archetype family + dominant attractor lookup
3. `ShadowFrameConfig` — config parameters
4. `TriFunction<String, String, String, Set<String>>` — mode profile facet resolver (agentId, tenantId, mode → facet set)

```java
package io.casehub.neocortex.cognition.situational;

import io.casehub.neocortex.cognition.CognitionPromptRenderer;
import io.casehub.neocortex.cognition.trace.PipelineTrace.SituationalPersonalitySnapshot;
import io.casehub.neocortex.mindmap.MindMapQuery;
import io.casehub.neocortex.mindmap.MindMapStore;

import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.function.BiFunction;

public class ShadowArchetypePromptSection implements CognitionPromptRenderer {

    @FunctionalInterface
    public interface ModeProfileResolver {
        Set<String> resolve(String agentId, String tenantId, String mode);
    }

    private final BiFunction<String, String, Optional<SituationalPersonalitySnapshot>> snapshotAccessor;
    private final MindMapStore store;
    private final ShadowFrameConfig config;
    private final ModeProfileResolver modeProfileResolver;

    public ShadowArchetypePromptSection(
            BiFunction<String, String, Optional<SituationalPersonalitySnapshot>> snapshotAccessor,
            MindMapStore store,
            ShadowFrameConfig config,
            ModeProfileResolver modeProfileResolver) {
        this.snapshotAccessor = snapshotAccessor;
        this.store = store;
        this.config = config;
        this.modeProfileResolver = modeProfileResolver;
    }

    @Override
    public String render(String agentId, String tenantId) {
        var optSnapshot = snapshotAccessor.apply(agentId, tenantId);
        if (optSnapshot.isEmpty()) return null;
        var snapshot = optSnapshot.get();

        if (snapshot.affectiveWinner() == null && snapshot.socialWinner() == null) return null;

        var sb = new StringBuilder();
        String activeMode = snapshot.affectiveWinner();

        // Mode header
        if (activeMode != null) {
            Double intensity = snapshot.modeIntensities().get(activeMode);
            sb.append("Your personality has shifted under ")
              .append(activeMode.toLowerCase().replace('_', ' '));
            if (intensity != null) sb.append(" (intensity ").append(Math.round(intensity * 100)).append("%)");
            sb.append(".\n");
        }
        if (snapshot.socialWinner() != null) {
            Double socialIntensity = snapshot.modeIntensities().get(snapshot.socialWinner());
            sb.append("Social orientation: ")
              .append(snapshot.socialWinner().toLowerCase().replace('_', ' '));
            if (socialIntensity != null) sb.append(" (intensity ").append(Math.round(socialIntensity * 100)).append("%)");
            sb.append(".\n");
        }

        // Relevance-ranked facets
        Set<String> modeProfileFacets = activeMode != null && modeProfileResolver != null
            ? modeProfileResolver.resolve(agentId, tenantId, activeMode)
            : Set.of();

        String dominantAttractor = resolveDominantAttractor(agentId, tenantId);

        var scored = FacetRelevanceScorer.score(
            snapshot.facetDisplacements(), activeMode, modeProfileFacets, dominantAttractor, config);

        if (!scored.isEmpty()) {
            for (var facet : scored) {
                String direction = facet.displacement() > 0 ? "elevated" : "reduced";
                String magnitude = Math.abs(facet.displacement()) > 0.15 ? "" :
                                   Math.abs(facet.displacement()) > 0.08 ? "" : "slightly ";
                sb.append("  ").append(formatFacetName(facet.facet())).append(": ")
                  .append(magnitude).append(direction)
                  .append(" (").append(String.format("%+d%%", Math.round(facet.displacement() * 100))).append(")");
                if (facet.modeCharacteristic()) sb.append(" — characteristic of this state");
                sb.append("\n");
            }
        }

        // Archetype context
        resolveArchetypeFamily(agentId, tenantId).ifPresent(family ->
            sb.append("\nYou are a ").append(capitalise(family)).append(". These shifts are your current felt reality.\n"));

        return sb.toString().trim();
    }

    @Override
    public int order() { return 215; }

    @Override
    public String blockTag() { return "SITUATIONAL"; }

    private String resolveDominantAttractor(String agentId, String tenantId) {
        var query = MindMapQuery.forTenant(tenantId)
            .inSubgraph("BEHAVIORAL")
            .withTraits(Set.of("CapsGenerated"))
            .withLimit(10)
            .build();
        var nodes = store.search(query);
        return nodes.stream()
            .filter(n -> agentId.equals(n.properties().get("agent-id")))
            .max(java.util.Comparator.comparingDouble(
                n -> parseDouble(n.properties().get("strength"))))
            .map(n -> n.properties().get("caps-node-id"))
            .orElse(null);
    }

    private Optional<String> resolveArchetypeFamily(String agentId, String tenantId) {
        var query = MindMapQuery.forTenant(tenantId)
            .inSubgraph("PERSON")
            .withText(agentId)
            .withLimit(1)
            .build();
        var nodes = store.search(query);
        if (nodes.isEmpty()) return Optional.empty();
        return Optional.ofNullable(nodes.getFirst().properties().get("archetype-1-family"));
    }

    private static String formatFacetName(String kebab) {
        return kebab.replace('-', ' ').substring(0, 1).toUpperCase() + kebab.replace('-', ' ').substring(1);
    }

    private static String capitalise(String s) {
        return s.isEmpty() ? s : s.substring(0, 1).toUpperCase() + s.substring(1);
    }

    private static double parseDouble(String s) {
        try { return s != null ? Double.parseDouble(s) : 0.0; }
        catch (NumberFormatException e) { return 0.0; }
    }
}
```

- [ ] **Step 4: Update CognitionCore wiring**

In CognitionCore where ShadowArchetypePromptSection is created (around line 826), update to pass additional dependencies:

```java
new ShadowArchetypePromptSection(
    situationalPersonalityParticipant::currentSnapshot,
    store,
    shadowFrameConfig,
    this::resolveModeProfileFacets
)
```

Add the `shadowFrameConfig` field (injected or from defaults) and a helper method:

```java
private Set<String> resolveModeProfileFacets(String agentId, String tenantId, String mode) {
    // Extract facet names from the agent's SituationalProfile for the given mode
    // via descriptor.disposition().situationalProfiles()
    // Return the set of facet names that have non-zero deltas for this mode
    // Graceful degradation: return Set.of() if unavailable
}
```

- [ ] **Step 5: Update existing tests**

Update `ShadowArchetypePromptSectionTest.java` to use the new 4-param constructor. Existing test logic should still validate mode/intensity rendering. Add new tests for facet rendering and archetype context.

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="ShadowArchetypePromptSectionTest"`

Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/situational/ShadowArchetypePromptSection.java cognition/src/main/java/io/casehub/neocortex/cognition/CognitionCore.java cognition/src/test/java/io/casehub/neocortex/cognition/situational/ShadowArchetypePromptSectionTest.java
git commit -m "feat(#1058): render relevance-ranked displaced facets + archetype context

ShadowArchetypePromptSection now renders top-N displaced facets
with mode and attractor relevance boosting, plus archetype family.

Refs #1058

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 4: Build verification

### Task 5: Full build verification

**Files:**
- None modified — verification only

- [ ] **Step 1: Build cognition-api + cognition**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition-api,cognition`

Expected: BUILD SUCCESS.

- [ ] **Step 2: Build mindmap-intelligence**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-intelligence`

Expected: BUILD SUCCESS.

- [ ] **Step 3: Full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`

Expected: BUILD SUCCESS across all modules.

## References

- [2026-11-19-shadow-narrative-frame-design.md] — design spec
- [mindmap-intelligence/.../BehavioralSynthesisPhase.java] — attractor creation (518 lines)
- [cognition/.../ShadowArchetypePromptSection.java] — current prompt renderer (61 lines)
- [cognition/.../SituationalPersonalityParticipant.java] — snapshot provider
- [cognition/.../PersonalityStateService.java] — CDI singleton holding personality state
- [cognition/CognitionCore.java] — wires ShadowArchetypePromptSection
- [cognition/CognitionDefaultBeans.java] — @DefaultBean producers
- [cognition-api/.../PipelineTrace.SituationalPersonalitySnapshot] — shared snapshot type
- [GitHub #1058] — focal issue
- [GitHub #712] — shadow narrative concept origin
