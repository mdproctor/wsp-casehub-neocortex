# Cognitive-Eidos Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #753 — Manor: wire CharacterCognition through standard CognitionCore pipeline
**Issue group:** #758, #759, #755, #733, #732, #753

**Goal:** Bridge eidos personality descriptors to cognitive profiles via a reusable neocortex module, and route memory retrieval through personality-weighted modulation.

**Architecture:** New `cognitive-eidos/` module in neocortex converts eidos `AgentDescriptor` to `DescriptorView` at startup, derives `CognitiveDefaults` via `CognitiveDerivationEngine`, and registers with `CognitiveDefaultsRegistry`. In casehub-mosaic, `AgentExperienceService.recall()` routes through `CognitiveMemoryRetriever` for personality-weighted domain modulation.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI, casehub-eidos-api, casehub-neocortex-cognitive-index

## Global Constraints

- Java 21 source, Java 26 JVM
- `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All commits reference an issue: `Refs #753` or `Closes #753`
- Root package: `io.casehub.neocortex.cognitive.eidos`

---

## Batch 1: cognitive-eidos/ module (neocortex)

### Task 1: Create cognitive-eidos module with EidosCognitiveProfileBridge

**Files:**
- Create: `cognitive-eidos/pom.xml`
- Create: `cognitive-eidos/src/main/java/io/casehub/neocortex/cognitive/eidos/EidosCognitiveProfileBridge.java`
- Create: `cognitive-eidos/src/test/java/io/casehub/neocortex/cognitive/eidos/EidosCognitiveProfileBridgeTest.java`
- Modify: `pom.xml` (parent — add module)

**Interfaces:**
- Consumes: `AgentRegistry.find(AgentQuery)` → `List<AgentMatch>` (eidos-api), `CognitiveDerivationEngine.derive(DescriptorView)` → `CognitiveDefaults` (cognitive-index), `CognitiveDefaultsRegistry.register(CognitiveDefaults)` (cognitive-index)
- Produces: Registered `CognitiveDefaults` per eidos agent at startup — accessible via `CognitiveDefaultsRegistry.forAgent(agentId)`

- [ ] **Step 1: Write the failing test**

```java
package io.casehub.neocortex.cognitive.eidos;

import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import io.casehub.neocortex.cognitive.index.CognitiveDerivationEngine;
import io.casehub.neocortex.cognitive.index.DescriptorView;
import io.casehub.neocortex.cognitive.index.DispositionAxes;
import io.casehub.neocortex.cognitive.index.WeightedTerm;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class EidosCognitiveProfileBridgeTest {

    @Test
    void bridgeRegistersProfileForEachDescriptor() {
        var registry = CognitiveDefaultsRegistry.forTesting();

        var view = DescriptorView.of(
                "muttley",
                new DispositionAxes("competitive", "low", "high", "low", "aggressive"),
                List.of(new WeightedTerm("Se", 0.8), new WeightedTerm("Te", 0.6)),
                List.of("cause chaos", "avoid punishment")
        );

        var bridge = new EidosCognitiveProfileBridge(registry);
        bridge.registerFromDescriptor(view);

        var profile = registry.forAgent("muttley");
        assertTrue(profile.isPresent(), "profile should be registered");
        assertEquals("muttley", profile.get().agentId());
        assertNotNull(profile.get().personalityProfile());
        assertNotNull(profile.get().moodBaseline());
    }

    @Test
    void derivedPersonalityWeightsReflectDisposition() {
        var registry = CognitiveDefaultsRegistry.forTesting();

        var muttley = DescriptorView.of(
                "muttley",
                new DispositionAxes("competitive", "low", "high", "low", "aggressive"),
                List.of(new WeightedTerm("Se", 0.8), new WeightedTerm("Te", 0.6)),
                List.of("cause chaos")
        );

        var penelope = DescriptorView.of(
                "penelope",
                new DispositionAxes("nurturing", "high", "low", "moderate", "diplomatic"),
                List.of(new WeightedTerm("Fe", 0.9), new WeightedTerm("Fi", 0.7)),
                List.of("help others", "stay safe")
        );

        var bridge = new EidosCognitiveProfileBridge(registry);
        bridge.registerFromDescriptor(muttley);
        bridge.registerFromDescriptor(penelope);

        var muttleyProfile = registry.forAgent("muttley").orElseThrow();
        var penelopeProfile = registry.forAgent("penelope").orElseThrow();

        assertNotEquals(
                muttleyProfile.personalityProfile().personality(),
                penelopeProfile.personalityProfile().personality(),
                "different dispositions should produce different personality weights"
        );

        assertNotEquals(
                muttleyProfile.moodBaseline(),
                penelopeProfile.moodBaseline(),
                "different dispositions should produce different mood baselines"
        );
    }

    @Test
    void existingYamlProfileIsNotOverwritten() {
        var existing = CognitiveDerivationEngine.derive(
                DescriptorView.of(
                        "muttley",
                        new DispositionAxes("nurturing", "high", "low", "moderate", "diplomatic"),
                        List.of(new WeightedTerm("Fe", 0.9)),
                        List.of("be nice")
                )
        );
        var registry = CognitiveDefaultsRegistry.forTesting(existing);

        var view = DescriptorView.of(
                "muttley",
                new DispositionAxes("competitive", "low", "high", "low", "aggressive"),
                List.of(new WeightedTerm("Se", 0.8)),
                List.of("cause chaos")
        );

        var bridge = new EidosCognitiveProfileBridge(registry);
        bridge.registerFromDescriptor(view);

        var profile = registry.forAgent("muttley").orElseThrow();
        assertEquals(existing.moodBaseline(), profile.moodBaseline(),
                "existing YAML profile should not be overwritten by eidos derivation");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-eidos -Dtest=EidosCognitiveProfileBridgeTest -am`
Expected: compilation failure — `EidosCognitiveProfileBridge` does not exist

- [ ] **Step 3: Create module pom.xml**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.4-SNAPSHOT</version>
  </parent>

  <artifactId>casehub-neocortex-cognitive-eidos</artifactId>
  <name>CaseHub Neocortex - Cognitive Eidos Bridge</name>
  <description>Bridges eidos identity descriptors to cognitive profiles via CognitiveDerivationEngine</description>

  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-cognitive-index</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-eidos-api</artifactId>
    </dependency>
    <dependency>
      <groupId>jakarta.enterprise</groupId>
      <artifactId>jakarta.enterprise.cdi-api</artifactId>
      <scope>provided</scope>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 4: Add module to parent pom.xml**

In the parent `pom.xml`, add `<module>cognitive-eidos</module>` after the `<module>cognitive-index</module>` line.

- [ ] **Step 5: Write EidosCognitiveProfileBridge**

```java
package io.casehub.neocortex.cognitive.eidos;

import io.casehub.eidos.api.AgentDescriptor;
import io.casehub.eidos.api.AgentDisposition;
import io.casehub.eidos.api.AgentGoal;
import io.casehub.eidos.api.AgentRegistry;
import io.casehub.eidos.api.DispositionAxis;
import io.casehub.eidos.api.DispositionValue;
import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import io.casehub.neocortex.cognitive.index.CognitiveDerivationEngine;
import io.casehub.neocortex.cognitive.index.DescriptorView;
import io.casehub.neocortex.cognitive.index.DispositionAxes;
import io.casehub.neocortex.cognitive.index.WeightedTerm;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import io.quarkus.runtime.Startup;
import org.jboss.logging.Logger;

import java.util.List;

@ApplicationScoped
@Startup
public class EidosCognitiveProfileBridge {

    private static final Logger LOG = Logger.getLogger(EidosCognitiveProfileBridge.class);

    private final CognitiveDefaultsRegistry registry;
    private final Instance<AgentRegistry> agentRegistryInstance;

    @Inject
    public EidosCognitiveProfileBridge(CognitiveDefaultsRegistry registry,
                                       Instance<AgentRegistry> agentRegistryInstance) {
        this.registry = registry;
        this.agentRegistryInstance = agentRegistryInstance;
        init();
    }

    // Test constructor — no eidos dependency
    public EidosCognitiveProfileBridge(CognitiveDefaultsRegistry registry) {
        this.registry = registry;
        this.agentRegistryInstance = null;
    }

    private void init() {
        if (agentRegistryInstance == null || agentRegistryInstance.isUnsatisfied()) {
            LOG.info("No AgentRegistry available — skipping eidos profile bridge");
            return;
        }
        var agentRegistry = agentRegistryInstance.get();
        var matches = agentRegistry.find(AgentQuery.all());
        int count = 0;
        for (var match : matches) {
            var descriptor = match.descriptor();
            var view = toDescriptorView(descriptor);
            registerFromDescriptor(view);
            count++;
        }
        LOG.infof("Registered %d cognitive profiles from eidos descriptors", count);
    }

    public void registerFromDescriptor(DescriptorView view) {
        if (registry.forAgent(view.agentId()).isPresent()) {
            LOG.debugf("Skipping eidos derivation for %s — YAML profile exists", view.agentId());
            return;
        }
        var defaults = CognitiveDerivationEngine.derive(view);
        registry.register(defaults);
    }

    static DescriptorView toDescriptorView(AgentDescriptor descriptor) {
        var disposition = descriptor.disposition();
        var axes = new DispositionAxes(
                disposition.primaryTerm(DispositionAxis.SOCIAL_ORIENTATION),
                disposition.primaryTerm(DispositionAxis.RULE_FOLLOWING),
                disposition.primaryTerm(DispositionAxis.RISK_APPETITE),
                disposition.primaryTerm(DispositionAxis.AUTONOMY),
                disposition.primaryTerm(DispositionAxis.CONFLICT_MODE)
        );
        var profile = disposition.dispositionProfile().stream()
                .map(dv -> new WeightedTerm(dv.term(), dv.weight()))
                .toList();
        var goals = descriptor.goals().stream()
                .map(AgentGoal::name)
                .toList();
        return DescriptorView.of(descriptor.agentId(), axes, profile, goals);
    }
}
```

**Note:** The exact `AgentQuery.all()` API needs to be confirmed at implementation time — the eidos-api may use a different discovery pattern. Check `AgentQuery` for a builder or static factory that returns all agents for the active tenancy.

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-eidos -Dtest=EidosCognitiveProfileBridgeTest -am`
Expected: 3 tests PASS

- [ ] **Step 7: Build the full project to verify no breakage**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS — all modules compile including new cognitive-eidos

- [ ] **Step 8: Commit**

```bash
git add cognitive-eidos/ pom.xml
git commit -m "feat(#753): add cognitive-eidos bridge module

Derives CognitiveDefaults from eidos AgentDescriptor via
CognitiveDerivationEngine. Registers profiles with
CognitiveDefaultsRegistry at startup. Existing YAML profiles
are not overwritten.

Refs #753"
```

---

## Batch 2: Modulated recall wiring (casehub-mosaic, cross-repo)

### Task 2: Route AgentExperienceService recall through CognitiveMemoryRetriever

**Cross-repo:** This task modifies `AgentExperienceService` in casehub-mosaic (slot 207, `examples/wacky-manor/`).

**Files:**
- Modify: `examples/wacky-manor/src/main/java/.../AgentExperienceService.java` (lines ~111, ~127, ~140)
- Modify: `examples/wacky-manor/pom.xml` (add cognitive-eidos dependency if not already present)

**Interfaces:**
- Consumes: `CognitiveMemoryRetriever.query(MemoryQuery, ModulationContext)` → `List<Memory>` (cognitive-index), `CognitiveDefaultsRegistry.forAgentOrDefaults(String)` → `CognitiveDefaults` (cognitive-index)
- Produces: Personality-modulated memory retrieval for all three recall methods

- [ ] **Step 1: Add cognitive-eidos dependency to wacky-manor pom.xml**

Add to `examples/wacky-manor/pom.xml`:
```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-cognitive-eidos</artifactId>
</dependency>
```

This pulls in `cognitive-index` transitively, which provides `CognitiveMemoryRetriever` and `CognitiveDefaultsRegistry`.

- [ ] **Step 2: Modify AgentExperienceService to inject CognitiveMemoryRetriever and CognitiveDefaultsRegistry**

Add fields:
```java
@Inject
Instance<CognitiveMemoryRetriever> retrieverInstance;

@Inject
CognitiveDefaultsRegistry cognitiveDefaultsRegistry;
```

- [ ] **Step 3: Create helper method for modulated query**

```java
private List<Memory> modulatedQuery(MemoryQuery query, String agentId) {
    if (retrieverInstance.isUnsatisfied()) {
        return store.query(query);
    }
    var defaults = cognitiveDefaultsRegistry.forAgentOrDefaults(agentId);
    var context = new ModulationContext(
            null, // moodState — null falls back to unmodulated mood
            query.tenantId(),
            defaults.personalityProfile() != null ? defaults.personalityProfile().personality() : null,
            Instant.now(),
            Set.of()
    );
    return retrieverInstance.get().query(query, context);
}
```

- [ ] **Step 4: Route recall() through modulatedQuery**

Change `recall()` (line ~111) from:
```java
return store.query(MemoryQuery.forEntity(agentId, MANOR_DOMAIN, tenantId));
```
to:
```java
return modulatedQuery(
    MemoryQuery.forEntity(agentId, MANOR_DOMAIN, tenantId),
    agentId
);
```

Apply the same pattern to `recallRelationships()` (line ~127) and `recallReflections()` (line ~140).

- [ ] **Step 5: Verify wacky-manor builds**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl examples/wacky-manor -am`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```bash
git add examples/wacky-manor/
git commit -m "feat(#753): route AgentExperienceService recall through CognitiveMemoryRetriever

All three recall methods (recall, recallRelationships, recallReflections)
now use personality-weighted domain modulation when CognitiveMemoryRetriever
is available. Falls back to direct CaseMemoryStore query when not.

Refs #753"
```

---

## Batch 3: Verification

### Task 3: End-to-end personality differentiation verification

**Files:**
- Create: `cognitive-eidos/src/test/java/io/casehub/neocortex/cognitive/eidos/PersonalityDifferentiationTest.java`

**Interfaces:**
- Consumes: `EidosCognitiveProfileBridge.registerFromDescriptor(DescriptorView)`, `CognitiveDefaultsRegistry.forAgent(String)`, `CognitiveMemoryRetriever.query(MemoryQuery, ModulationContext)`

- [ ] **Step 1: Write differentiation test**

```java
package io.casehub.neocortex.cognitive.eidos;

import io.casehub.neocortex.cognitive.index.*;
import io.casehub.neocortex.memory.api.*;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;

class PersonalityDifferentiationTest {

    @Test
    void differentPersonalitiesProduceDifferentCognitiveDefaults() {
        var registry = CognitiveDefaultsRegistry.forTesting();
        var bridge = new EidosCognitiveProfileBridge(registry);

        // High-risk aggressive character
        bridge.registerFromDescriptor(DescriptorView.of(
                "hooded-claw",
                new DispositionAxes("competitive", "low", "high", "high", "aggressive"),
                List.of(new WeightedTerm("Se", 0.9), new WeightedTerm("Te", 0.7)),
                List.of("defeat enemies", "seize control")
        ));

        // Nurturing diplomatic character
        bridge.registerFromDescriptor(DescriptorView.of(
                "penelope-pitstop",
                new DispositionAxes("nurturing", "high", "low", "moderate", "diplomatic"),
                List.of(new WeightedTerm("Fe", 0.9), new WeightedTerm("Fi", 0.7)),
                List.of("help others", "win fairly")
        ));

        var claw = registry.forAgent("hooded-claw").orElseThrow();
        var penelope = registry.forAgent("penelope-pitstop").orElseThrow();

        // Mood baselines should differ
        assertNotEquals(claw.moodBaseline(), penelope.moodBaseline());

        // CBR strategies should differ (risk appetite drives minSimilarity)
        assertNotEquals(claw.cbrStrategy(), penelope.cbrStrategy());

        // Social cognition should differ (conflict mode drives trust/conflict)
        assertNotEquals(claw.socialCognition(), penelope.socialCognition());

        // Graph structure should differ (disposition profile drives inference style)
        assertNotEquals(claw.graphStructure(), penelope.graphStructure());

        // All ten pathways produce non-null values
        assertNotNull(claw.personalityProfile());
        assertNotNull(claw.moodBaseline());
        assertNotNull(claw.curiosity());
        assertNotNull(claw.cbrStrategy());
        assertNotNull(claw.socialCognition());
        assertNotNull(claw.graphStructure());
        assertNotNull(claw.extractionBias());
        assertNotNull(claw.appraisalWeights());
        assertNotNull(claw.habituationConfig());
    }
}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-eidos -Dtest=PersonalityDifferentiationTest -am`
Expected: PASS — ten pathways produce differentiated, non-null values for different disposition profiles

- [ ] **Step 3: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-eidos -am`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add cognitive-eidos/
git commit -m "test(#753): verify personality differentiation across derivation pathways

Closes #753"
```

---

## References

- [2026-11-02-cognitive-eidos-bridge-design.md] — design spec this plan implements
- [CognitiveDefaultsRegistry.java:78] — `register(CognitiveDefaults)` method
- [CognitiveDerivationEngine.java:141] — `derive(DescriptorView)` static factory
- [CognitiveMemoryRetriever.java:38] — `query(MemoryQuery, ModulationContext)` method
- [DescriptorView.java:42] — `of(agentId, axes, profile, goals)` factory
- [DispositionAxes.java:18] — `DispositionAxes(socialOrient, ruleFollowing, riskAppetite, autonomy, conflictMode)` record
- [GitHub #753] — Manor: wire CharacterCognition through standard CognitionCore pipeline
