# Temporal Archetype Salience — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1057 — Temporal archetype salience across life phases
**Issue group:** #1057

**Goal:** Extract per-phase archetype salience weights from biographical data, resolve an agent's current life phase from born date, and modulate situational profile intensity by phase-indexed archetype salience at tick time.

**Architecture:** `DevelopmentalPhaseResolver` (mindmap-api, pure utility) derives current phase from `lifecycle.born`. `PersonalityProfileHandler` (memory-seeding) writes `archetype-{rank}-salience-{phase}` properties from extraction data. `SituationalPersonalityParticipant` (cognition) reads phase salience at tick time and multiplies composite delta by the weight.

**Tech Stack:** Java 21, Quarkus CDI, JUnit 5 + AssertJ

## Global Constraints

- `SituationalPersonalityParticipant` is in `cognition` — has access to `EffectiveCognitiveDefaults` and `MindMapStore` (via injection)
- `DevelopmentalPhaseResolver` goes in `mindmap-api` — zero deps beyond `LifecycleDate`
- Phase values match `FormativeTimestampGenerator` conventions: `childhood` (0–12), `adolescence` (13–17), `early-adulthood` (18–25), `adulthood` (26+)
- Default phase salience = 1.0 when no data exists (backward compatible)
- Provenance strings: `"family-default:CREATOR"` for eidos defaults, `"biographical"` for per-character profiles

---

## Batch 1: Phase resolution + extraction data model

### Task 1: DevelopmentalPhaseResolver utility

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/DevelopmentalPhaseResolver.java`
- Test: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/DevelopmentalPhaseResolverTest.java`

**Interfaces:**
- Produces: `DevelopmentalPhaseResolver.resolvePhase(LifecycleDate born, Instant now) → String`
- Produces: `DevelopmentalPhaseResolver.resolvePhase(MindMapNode personNode, Instant now) → String`
- Produces: `DevelopmentalPhaseResolver.CHILDHOOD`, `ADOLESCENCE`, `EARLY_ADULTHOOD`, `ADULTHOOD` constants

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.mindmap;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;

import static org.assertj.core.api.Assertions.assertThat;

class DevelopmentalPhaseResolverTest {

    @Test
    void childReturnChildhood() {
        var born = LifecycleDate.parse("2020-01-15");
        var now = LocalDate.of(2028, 6, 1).atStartOfDay(ZoneOffset.UTC).toInstant();
        assertThat(DevelopmentalPhaseResolver.resolvePhase(born, now))
            .isEqualTo(DevelopmentalPhaseResolver.CHILDHOOD);
    }

    @Test
    void adolescentReturnsAdolescence() {
        var born = LifecycleDate.parse("2010-03-20");
        var now = LocalDate.of(2025, 6, 1).atStartOfDay(ZoneOffset.UTC).toInstant();
        assertThat(DevelopmentalPhaseResolver.resolvePhase(born, now))
            .isEqualTo(DevelopmentalPhaseResolver.ADOLESCENCE);
    }

    @Test
    void youngAdultReturnsEarlyAdulthood() {
        var born = LifecycleDate.parse("2004-07-10");
        var now = LocalDate.of(2025, 6, 1).atStartOfDay(ZoneOffset.UTC).toInstant();
        assertThat(DevelopmentalPhaseResolver.resolvePhase(born, now))
            .isEqualTo(DevelopmentalPhaseResolver.EARLY_ADULTHOOD);
    }

    @Test
    void adultReturnsAdulthood() {
        var born = LifecycleDate.parse("1990-01-01");
        var now = LocalDate.of(2025, 6, 1).atStartOfDay(ZoneOffset.UTC).toInstant();
        assertThat(DevelopmentalPhaseResolver.resolvePhase(born, now))
            .isEqualTo(DevelopmentalPhaseResolver.ADULTHOOD);
    }

    @Test
    void yearOnlyBornDate() {
        var born = LifecycleDate.parse("1907");
        var now = LocalDate.of(1920, 6, 1).atStartOfDay(ZoneOffset.UTC).toInstant();
        assertThat(DevelopmentalPhaseResolver.resolvePhase(born, now))
            .isEqualTo(DevelopmentalPhaseResolver.ADOLESCENCE);
    }

    @Test
    void nullBornDefaultsToAdulthood() {
        assertThat(DevelopmentalPhaseResolver.resolvePhase((LifecycleDate) null, Instant.now()))
            .isEqualTo(DevelopmentalPhaseResolver.ADULTHOOD);
    }

    @Test
    void boundaryAge12IsChildhood() {
        var born = LifecycleDate.parse("2013-01-01");
        var now = LocalDate.of(2025, 6, 1).atStartOfDay(ZoneOffset.UTC).toInstant();
        assertThat(DevelopmentalPhaseResolver.resolvePhase(born, now))
            .isEqualTo(DevelopmentalPhaseResolver.CHILDHOOD);
    }

    @Test
    void boundaryAge13IsAdolescence() {
        var born = LifecycleDate.parse("2012-01-01");
        var now = LocalDate.of(2025, 6, 1).atStartOfDay(ZoneOffset.UTC).toInstant();
        assertThat(DevelopmentalPhaseResolver.resolvePhase(born, now))
            .isEqualTo(DevelopmentalPhaseResolver.ADOLESCENCE);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest="DevelopmentalPhaseResolverTest"`

Expected: compilation error — `DevelopmentalPhaseResolver` does not exist.

- [ ] **Step 3: Implement DevelopmentalPhaseResolver**

Create `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/DevelopmentalPhaseResolver.java`:

```java
package io.casehub.neocortex.mindmap;

import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.time.temporal.ChronoUnit;

public final class DevelopmentalPhaseResolver {

    public static final String CHILDHOOD = "childhood";
    public static final String ADOLESCENCE = "adolescence";
    public static final String EARLY_ADULTHOOD = "early-adulthood";
    public static final String ADULTHOOD = "adulthood";

    private DevelopmentalPhaseResolver() {}

    public static String resolvePhase(LifecycleDate born, Instant now) {
        if (born == null) return ADULTHOOD;
        long days = ChronoUnit.DAYS.between(born.toStartInstant(), now);
        int years = (int) (days / 365.25);
        if (years <= 12) return CHILDHOOD;
        if (years <= 17) return ADOLESCENCE;
        if (years <= 25) return EARLY_ADULTHOOD;
        return ADULTHOOD;
    }

    public static String resolvePhase(MindMapNode personNode, Instant now) {
        if (personNode == null) return ADULTHOOD;
        String bornValue = personNode.properties().get(LifecycleEvents.key("born"));
        if (bornValue == null || bornValue.isBlank()) return ADULTHOOD;
        try {
            return resolvePhase(LifecycleDate.parse(bornValue), now);
        } catch (IllegalArgumentException e) {
            return ADULTHOOD;
        }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest="DevelopmentalPhaseResolverTest"`

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/DevelopmentalPhaseResolver.java mindmap-api/src/test/java/io/casehub/neocortex/mindmap/DevelopmentalPhaseResolverTest.java
git commit -m "feat(#1057): DevelopmentalPhaseResolver — derive life phase from born date

Pure static utility in mindmap-api. Phase boundaries match
FormativeTimestampGenerator conventions (0-12/13-17/18-25/26+).

Refs #1057

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: PhaseSalience extraction + PersonalityProfileHandler

**Files:**
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandler.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandlerTest.java` (existing, add test)

**Interfaces:**
- Produces: `PersonalityProfileEntry.PhaseSalience(String phase, Double salience, String evidence)` record
- Produces: `ArchetypeSelection.phaseSalience()` field (`List<PhaseSalience>`)
- Produces: PERSON node properties `archetype-{rank}-salience-{phase}` written by handler

- [ ] **Step 1: Write failing test**

Add to existing `PersonalityProfileHandlerTest.java` (or create if absent):

```java
@Test
void writesPhaseSalienceProperties() {
    var store = new InMemoryMindMapStore();
    var sgId = store.createSubgraph(
        new SubgraphInput("Person", SubgraphTypes.PERSON, null), "t1");
    var nodeId = store.addNode(NodeInput.of("test-agent", sgId), "t1");

    var phaseSalience = List.of(
        new PersonalityProfileEntry.PhaseSalience("childhood", 0.80, "childhood evidence"),
        new PersonalityProfileEntry.PhaseSalience("adulthood", 0.40, "adulthood evidence")
    );
    var archetype = new PersonalityProfileEntry.ArchetypeSelection(
        1, "creator", "engineer", List.of("innovative"), "evidence", 0.9, phaseSalience);
    var entry = new PersonalityProfileEntry(
        "p1", "test-agent",
        null, List.of(archetype), null, null, List.of(), List.of());

    var handler = new PersonalityProfileHandler(store);
    handler.handle(new BiographyProfile(/* ... minimal construction ... */), "test-agent", "t1");

    var node = store.search(MindMapQuery.of("t1", 10).withType(SubgraphTypes.PERSON)).getFirst();
    assertThat(node.properties()).containsEntry("archetype-1-salience-childhood", "0.8");
    assertThat(node.properties()).containsEntry("archetype-1-salience-adulthood", "0.4");
    assertThat(node.properties()).doesNotContainKey("archetype-1-salience-adolescence");
}
```

Note: the exact test construction depends on how `PersonalityProfileHandler.handle()` is invoked. Inspect the existing test file and adapt. The key assertion is that phase salience properties appear on the PERSON node.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest="PersonalityProfileHandlerTest#writesPhaseSalienceProperties"`

Expected: compilation error — `PhaseSalience` does not exist, `ArchetypeSelection` constructor doesn't accept it.

- [ ] **Step 3: Add PhaseSalience record to PersonalityProfileEntry**

Add inner record to `PersonalityProfileEntry`:

```java
@JsonIgnoreProperties(ignoreUnknown = true)
public record PhaseSalience(
    String phase,
    Double salience,
    String evidence
) {}
```

Add `@JsonProperty("phase_salience") List<PhaseSalience> phaseSalience` parameter to `ArchetypeSelection`. Update the compact constructor to default it:

```java
public ArchetypeSelection {
    adjectives = adjectives != null ? List.copyOf(adjectives) : List.of();
    phaseSalience = phaseSalience != null ? List.copyOf(phaseSalience) : List.of();
}
```

- [ ] **Step 4: Extend PersonalityProfileHandler.writeArchetypes()**

After the existing archetype property writes (line 123), add phase salience writes:

```java
if (arch.phaseSalience() != null) {
    for (var ps : arch.phaseSalience()) {
        if (ps.phase() != null && ps.salience() != null) {
            props.put(prefix + "-salience-" + ps.phase(), String.valueOf(ps.salience()));
        }
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest="PersonalityProfileHandlerTest#writesPhaseSalienceProperties"`

Expected: PASS.

- [ ] **Step 6: Run all PersonalityProfileHandler tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest="PersonalityProfileHandlerTest"`

Expected: all existing tests still PASS (new field defaults to empty list).

- [ ] **Step 7: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntry.java memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandler.java memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandlerTest.java
git commit -m "feat(#1057): PhaseSalience extraction + handler writes phase salience properties

ArchetypeSelection gains phaseSalience field. Handler writes
archetype-{rank}-salience-{phase} properties on PERSON nodes.

Refs #1057

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 2: Runtime modulation

### Task 3: Phase salience modulation in SituationalPersonalityParticipant

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/SituationalPersonalityParticipant.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/situational/SituationalPersonalityParticipantTest.java`

**Interfaces:**
- Consumes: `DevelopmentalPhaseResolver.resolvePhase(MindMapNode, Instant)` from Task 1
- Consumes: `archetype-{rank}-salience-{phase}` properties from Task 2
- Consumes: `SituationalProfile.provenance()` to resolve archetype family per mode

- [ ] **Step 1: Write failing test for phase salience modulation**

Add to `SituationalPersonalityParticipantTest.java`:

```java
@Test
void compositeDeltaScaledByPhaseSalience() {
    // Setup: agent with STRESS mode active, Creator family, childhood salience 0.5
    // Create a PERSON node with lifecycle.born (makes agent a child) and archetype-1-salience-childhood=0.5
    // Tick the participant
    // Assert: composite delta facet values are scaled by 0.5 compared to default (1.0)
}
```

The exact test setup depends on the existing test infrastructure. Inspect `SituationalPersonalityParticipantTest.java` for the pattern — it likely constructs a participant with mock/stub dependencies and calls `tick()`.

The key assertion: when `archetype-1-salience-childhood=0.5` exists and the agent's born date puts them in childhood, the composite delta's facet values should be 50% of what they'd be without phase salience (default 1.0).

- [ ] **Step 2: Run test to verify it fails**

Expected: fails because `computeCompositeDelta` doesn't account for phase salience yet.

- [ ] **Step 3: Add MindMapStore injection for phase/salience lookup**

Add a nullable `MindMapStore` field to `SituationalPersonalityParticipant`. Update the CDI-friendly constructor (via `CognitionCore.configureSituationalPersonality()`) to accept it. Update test constructors to pass null (graceful degradation).

```java
private final @org.jspecify.annotations.Nullable io.casehub.neocortex.mindmap.MindMapStore mindMapStore;
```

In `CognitionCore.configureSituationalPersonality()`, pass the existing `mindMapStore` field.

- [ ] **Step 4: Add phase salience resolution helper**

Add to `SituationalPersonalityParticipant`:

```java
private Map<SituationalMode, Double> buildPhaseSalienceMap(
        String agentId, String tenantId, java.time.Instant now,
        java.util.List<io.casehub.eidos.api.SituationalProfile> profiles) {
    if (mindMapStore == null) return Map.of();

    var personNodes = mindMapStore.search(
        io.casehub.neocortex.mindmap.MindMapQuery.of(tenantId, 10)
            .withType(io.casehub.neocortex.mindmap.SubgraphTypes.PERSON)
            .withText(agentId));
    if (personNodes.isEmpty()) return Map.of();
    var personNode = personNodes.getFirst();

    String phase = io.casehub.neocortex.mindmap.DevelopmentalPhaseResolver.resolvePhase(personNode, now);
    String primaryFamily = personNode.properties().get("archetype-1-family");

    var salienceMap = new java.util.EnumMap<SituationalMode, Double>(SituationalMode.class);
    for (var profile : profiles) {
        var mode = SituationalDeltaConverter.toMode(profile.mode());
        if (mode == null) continue;

        String family = resolveFamilyFromProvenance(profile.provenance(), primaryFamily);
        if (family == null) continue;

        int rank = resolveArchetypeRank(personNode, family);
        if (rank < 1) continue;

        String key = "archetype-" + rank + "-salience-" + phase;
        String val = personNode.properties().get(key);
        if (val != null) {
            try {
                salienceMap.put(mode, Double.parseDouble(val));
            } catch (NumberFormatException ignored) {}
        }
    }
    return Map.copyOf(salienceMap);
}

private static String resolveFamilyFromProvenance(String provenance, String primaryFamily) {
    if (provenance == null) return primaryFamily;
    if (provenance.startsWith("family-default:")) {
        return provenance.substring("family-default:".length()).toLowerCase(java.util.Locale.ROOT);
    }
    return primaryFamily;
}

private static int resolveArchetypeRank(io.casehub.neocortex.mindmap.MindMapNode personNode, String family) {
    for (int rank = 1; rank <= 3; rank++) {
        String nodeFamily = personNode.properties().get("archetype-" + rank + "-family");
        if (family.equalsIgnoreCase(nodeFamily)) return rank;
    }
    return 1;
}
```

- [ ] **Step 5: Modify computeCompositeDelta to accept and apply phase salience**

Update the method signature:

```java
private Map<String, Double> computeCompositeDelta(DetectionResult detection,
                                                   Map<SituationalMode, Map<String, Double>> profileDeltas,
                                                   Map<SituationalMode, Double> phaseSalience) {
    var composite = new LinkedHashMap<String, Double>();
    for (var group : SituationalMode.Group.values()) {
        var winner = detection.winner(group);
        if (winner == null) continue;
        double intensity = detection.intensity(winner);
        double salience = phaseSalience.getOrDefault(winner, 1.0);
        var deltas = profileDeltas.get(winner);
        if (deltas == null) continue;
        for (var entry : deltas.entrySet()) {
            composite.merge(entry.getKey(), entry.getValue() * intensity * salience, Double::sum);
        }
    }
    double sMax = config.dynamics().sMax();
    composite.replaceAll((k, v) -> Math.max(-sMax, Math.min(sMax, v)));
    return Map.copyOf(composite);
}
```

- [ ] **Step 6: Wire phase salience into tick()**

In `tick()`, build the phase salience map before the two `computeCompositeDelta` calls:

```java
var phaseSalience = buildPhaseSalienceMap(agentId, tenantId, now, profiles);
```

Pass `phaseSalience` to both calls to `computeCompositeDelta`.

- [ ] **Step 7: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="SituationalPersonalityParticipantTest#compositeDeltaScaledByPhaseSalience"`

Expected: PASS.

- [ ] **Step 8: Run all SituationalPersonalityParticipant tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="SituationalPersonalityParticipantTest"`

Expected: all existing tests still PASS (phaseSalience defaults to 1.0 when no MindMapStore or no properties).

- [ ] **Step 9: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/situational/SituationalPersonalityParticipant.java cognition/src/test/java/io/casehub/neocortex/cognition/situational/SituationalPersonalityParticipantTest.java cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java
git commit -m "feat(#1057): modulate situational profile intensity by phase-indexed archetype salience

computeCompositeDelta scales delta by phaseSalience from PERSON node.
Resolves current phase from lifecycle.born via DevelopmentalPhaseResolver.
Default 1.0 when no data — backward compatible.

Refs #1057

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 3: Verification

### Task 4: Full build verification

**Files:**
- None modified — verification only

- [ ] **Step 1: Build mindmap-api**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-api`

Expected: BUILD SUCCESS.

- [ ] **Step 2: Build memory-seeding**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-seeding`

Expected: BUILD SUCCESS.

- [ ] **Step 3: Build cognition**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition`

Expected: BUILD SUCCESS (1 pre-existing InnerLifeOrchestratorTest NPE is acceptable).

- [ ] **Step 4: Full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`

Expected: BUILD SUCCESS across all modules.

## References

- [2026-11-19-temporal-archetype-salience-design.md] — design spec
- [mindmap-api/.../LifecycleDate.java] — EDTF partial date value type
- [mindmap-api/.../LifecycleEvents.java] — lifecycle property conventions (born key)
- [memory-seeding/.../PersonalityProfileEntry.java:105-114] — ArchetypeSelection record
- [memory-seeding/.../PersonalityProfileHandler.java:111-123] — archetype property writing
- [memory-seeding/.../FormativeTimestampGenerator.java:29-49] — phase boundary conventions
- [cognition/.../SituationalPersonalityParticipant.java:187-203] — computeCompositeDelta formula
- [cognition/.../SituationalDeltaConverter.java] — profile-to-delta conversion
- [cognition/.../CognitionCore.java:1068-1072] — participant construction
- [eidos/.../SituationalProfileDeriver.java] — provenance format "family-default:FAMILY"
- [GitHub #1057] — focal issue
- [GitHub #712] — temporal drift concept origin
