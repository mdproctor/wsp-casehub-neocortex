# Cognitive Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #248 — feat: cognitive profile YAML — agent cognitive configuration file
**Issue group:** #253, #248

**Goal:** Implement a YAML-driven cognitive configuration system that produces per-agent `CognitiveDefaults` records from classpath YAML files, with runtime lookup via `CognitiveDefaultsRegistry`.

**Architecture:** `CognitiveDefaults` record in cognitive-index aggregates PersonalityWeights, MoodBaseline, CuriosityConfig, TemporalFocusConfig, MindMapVocabulary, and a services map. Jackson YAML parser with a custom `PersonalityWeightsDeserializer` (MemoryDomain key wrapping). `CognitiveDefaultsRegistry` CDI bean scans classpath at startup and exposes runtime lookup by agentId.

**Tech Stack:** Java 21, Jackson YAML, Quarkus CDI, JUnit 5

## Global Constraints

- Java 21 language level (on Java 26 JVM)
- camelCase for all YAML keys (D65)
- All CognitiveDefaults fields except agentId are nullable (null = use subsystem defaults)
- Jackson ObjectMapper must call `findAndRegisterModules()` (GE-20260602-a4d290)
- cognitive-index module — no new modules created

---

## Batch 1: CognitiveDefaults record + YAML parser

### Task 1: CognitiveDefaults record, PersonalityWeightsDeserializer, and parser tests

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PersonalityWeightsDeserializer.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsParserTest.java`
- Create: `cognitive-index/src/test/resources/cognitive-profiles/alice.yaml`
- Create: `cognitive-index/src/test/resources/cognitive-profiles/minimal.yaml`
- Modify: `cognitive-index/pom.xml` — add mindmap-intelligence + jackson-dataformat-yaml deps

**Interfaces:**
- Consumes: `PersonalityWeights` (memory-api), `MoodBaseline` (memory-api), `CuriosityConfig` (mindmap-intelligence), `TemporalFocusConfig` (cognitive-index), `MindMapVocabulary` (mindmap-api), `EdgeTypeDefinition` (mindmap-api), `MemoryDomain` (memory-api)
- Produces: `CognitiveDefaults(String agentId, String tenantId, PersonalityWeights, MoodBaseline, CuriosityConfig, TemporalFocusConfig, MindMapVocabulary, Map<String, String> services)`, `PersonalityWeightsDeserializer`

- [ ] **Step 1: Add dependencies to cognitive-index/pom.xml**

Add before the `<dependency>` for `jakarta.enterprise`:

```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-mindmap-intelligence</artifactId>
</dependency>
<dependency>
    <groupId>com.fasterxml.jackson.dataformat</groupId>
    <artifactId>jackson-dataformat-yaml</artifactId>
</dependency>
```

- [ ] **Step 2: Write test YAML files**

`cognitive-index/src/test/resources/cognitive-profiles/alice.yaml`:
```yaml
agentId: alice
tenantId: family-1

personality:
  experience: 1.5
  relationship: 0.8
  mood: 1.2

moodBaseline:
  pleasure: 0.0
  arousal: -0.2
  dominance: 0.3

curiosity:
  proximityScale: 7.0
  staleDaysThreshold: 90
  maxBfsDepth: 4
  topCentrality: 3
  volatilityThreshold: 0.3
  maxBoostFactor: 1.0
  minDampenFactor: 0.1
  improvingDampenCap: 0.7
  volatilityBoostCap: 0.5
  trajectoryLimit: 20

temporalFocus:
  proximityScale: 7.0
  worseningBoostCap: 1.0
  improvingDampenFactor: 0.5
  volatilityBoostCap: 0.5

vocabulary:
  edgeTypes:
    - canonical: knows
      aliases: [knows-about, familiar-with]
      defaultDecayHalfLifeDays: 365
    - canonical: child-of

services:
  reflectionSynthesizer: llm
  explanationRenderer: detailed
```

`cognitive-index/src/test/resources/cognitive-profiles/minimal.yaml`:
```yaml
agentId: bob
```

- [ ] **Step 3: Write failing parser tests**

```java
package io.casehub.neocortex.cognitive.index;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.personality.PersonalityWeights;
import java.io.IOException;
import java.io.InputStream;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CognitiveDefaultsParserTest {

    private ObjectMapper mapper;

    @BeforeEach
    void setUp() {
        mapper = new ObjectMapper(new YAMLFactory()).findAndRegisterModules();
        var module = new SimpleModule();
        module.addDeserializer(PersonalityWeights.class, new PersonalityWeightsDeserializer());
        mapper.registerModule(module);
    }

    private CognitiveDefaults parse(String resource) throws IOException {
        try (InputStream is = getClass().getClassLoader()
                .getResourceAsStream(resource)) {
            return mapper.readValue(is, CognitiveDefaults.class);
        }
    }

    @Test
    void fullProfile_parsesAllSections() throws IOException {
        var defaults = parse("cognitive-profiles/alice.yaml");

        assertThat(defaults.agentId()).isEqualTo("alice");
        assertThat(defaults.tenantId()).isEqualTo("family-1");
        assertThat(defaults.personality()).isNotNull();
        assertThat(defaults.personality().getWeight(new MemoryDomain("experience"))).isEqualTo(1.5);
        assertThat(defaults.personality().getWeight(new MemoryDomain("relationship"))).isEqualTo(0.8);
        assertThat(defaults.moodBaseline()).isNotNull();
        assertThat(defaults.moodBaseline().pleasure()).isEqualTo(0.0);
        assertThat(defaults.moodBaseline().arousal()).isEqualTo(-0.2);
        assertThat(defaults.curiosity()).isNotNull();
        assertThat(defaults.curiosity().proximityScale()).isEqualTo(7.0);
        assertThat(defaults.temporalFocus()).isNotNull();
        assertThat(defaults.temporalFocus().worseningBoostCap()).isEqualTo(1.0);
        assertThat(defaults.vocabulary()).isNotNull();
        assertThat(defaults.vocabulary().edgeTypes()).hasSize(2);
        assertThat(defaults.vocabulary().edgeTypes().get(0).canonical()).isEqualTo("knows");
        assertThat(defaults.services()).containsEntry("reflectionSynthesizer", "llm");
    }

    @Test
    void minimalProfile_onlyAgentId() throws IOException {
        var defaults = parse("cognitive-profiles/minimal.yaml");

        assertThat(defaults.agentId()).isEqualTo("bob");
        assertThat(defaults.tenantId()).isNull();
        assertThat(defaults.personality()).isNull();
        assertThat(defaults.moodBaseline()).isNull();
        assertThat(defaults.curiosity()).isNull();
        assertThat(defaults.temporalFocus()).isNull();
        assertThat(defaults.vocabulary()).isNull();
        assertThat(defaults.services()).isEmpty();
    }

    @Test
    void missingAgentId_throwsNullPointer() {
        assertThatThrownBy(() -> new CognitiveDefaults(
            null, null, null, null, null, null, null, null))
            .isInstanceOf(NullPointerException.class)
            .hasMessageContaining("agentId");
    }

    @Test
    void servicesMap_isDefensivelyCopied() throws IOException {
        var defaults = parse("cognitive-profiles/alice.yaml");
        assertThatThrownBy(() -> defaults.services().put("new", "value"))
            .isInstanceOf(UnsupportedOperationException.class);
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDefaultsParserTest -f pom.xml`
Expected: Compilation failure — `CognitiveDefaults` and `PersonalityWeightsDeserializer` do not exist.

- [ ] **Step 5: Implement CognitiveDefaults record**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.memory.mood.MoodBaseline;
import io.casehub.neocortex.memory.personality.PersonalityWeights;
import io.casehub.neocortex.mindmap.MindMapVocabulary;
import io.casehub.neocortex.mindmap.intelligence.CuriosityConfig;
import java.util.Map;
import java.util.Objects;

public record CognitiveDefaults(
    String agentId,
    String tenantId,
    PersonalityWeights personality,
    MoodBaseline moodBaseline,
    CuriosityConfig curiosity,
    TemporalFocusConfig temporalFocus,
    MindMapVocabulary vocabulary,
    Map<String, String> services
) {
    public CognitiveDefaults {
        Objects.requireNonNull(agentId, "agentId required");
        services = services != null ? Map.copyOf(services) : Map.of();
    }
}
```

- [ ] **Step 6: Implement PersonalityWeightsDeserializer**

```java
package io.casehub.neocortex.cognitive.index;

import com.fasterxml.jackson.core.JsonParser;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.DeserializationContext;
import com.fasterxml.jackson.databind.deser.std.StdDeserializer;
import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.personality.PersonalityWeights;
import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.Map;

public class PersonalityWeightsDeserializer extends StdDeserializer<PersonalityWeights> {

    public PersonalityWeightsDeserializer() {
        super(PersonalityWeights.class);
    }

    @Override
    public PersonalityWeights deserialize(JsonParser p, DeserializationContext ctx)
            throws IOException {
        Map<String, Double> raw = p.readValueAs(new TypeReference<Map<String, Double>>() {});
        Map<MemoryDomain, Double> weights = new LinkedHashMap<>();
        raw.forEach((k, v) -> weights.put(new MemoryDomain(k), v));
        return new PersonalityWeights(weights);
    }
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDefaultsParserTest -f pom.xml`
Expected: All 4 tests PASS.

- [ ] **Step 8: Run full cognitive-index test suite to check for regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -f pom.xml`
Expected: All tests PASS (existing 100 + new 4).

- [ ] **Step 9: Commit**

```bash
git add cognitive-index/
git commit -m "feat(cognitive-index): CognitiveDefaults record + YAML parser

Aggregate record for per-agent cognitive configuration. Custom
PersonalityWeightsDeserializer for MemoryDomain key wrapping.
All sections optional — null means use subsystem defaults.

Refs #248"
```

---

## Batch 2: CognitiveDefaultsRegistry + CLAUDE.md

### Task 2: CognitiveDefaultsRegistry CDI bean with classpath loading

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistry.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistryTest.java`
- Create: `cognitive-index/src/test/resources/cognitive-profiles/duplicate.yaml` (test fixture for duplicate agentId)
- Modify: `CLAUDE.md` — update cognitive-index module description

**Interfaces:**
- Consumes: `CognitiveDefaults` (from Task 1), `PersonalityWeightsDeserializer` (from Task 1)
- Produces: `CognitiveDefaultsRegistry` — `Optional<CognitiveDefaults> forAgent(String agentId)`, `CognitiveDefaults forAgentOrDefaults(String agentId)`, `Collection<CognitiveDefaults> allProfiles()`

- [ ] **Step 1: Write failing tests for CognitiveDefaultsRegistry**

```java
package io.casehub.neocortex.cognitive.index;

import java.io.IOException;
import java.util.List;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class CognitiveDefaultsRegistryTest {

    private CognitiveDefaultsRegistry registry(String path) throws IOException {
        return CognitiveDefaultsRegistry.loadFromClasspath(path,
            Thread.currentThread().getContextClassLoader());
    }

    @Test
    void loadFromClasspath_findsAllProfiles() throws IOException {
        var reg = registry("cognitive-profiles/");

        assertThat(reg.allProfiles()).hasSizeGreaterThanOrEqualTo(2);
    }

    @Test
    void forAgent_returnsMatchingProfile() throws IOException {
        var reg = registry("cognitive-profiles/");

        var alice = reg.forAgent("alice");
        assertThat(alice).isPresent();
        assertThat(alice.get().agentId()).isEqualTo("alice");
        assertThat(alice.get().personality()).isNotNull();
    }

    @Test
    void forAgent_returnsEmptyForUnknown() throws IOException {
        var reg = registry("cognitive-profiles/");

        assertThat(reg.forAgent("unknown")).isEmpty();
    }

    @Test
    void forAgentOrDefaults_returnsDefaultsForUnknown() throws IOException {
        var reg = registry("cognitive-profiles/");

        var defaults = reg.forAgentOrDefaults("unknown");
        assertThat(defaults.agentId()).isEqualTo("unknown");
        assertThat(defaults.personality()).isNull();
        assertThat(defaults.moodBaseline()).isNull();
        assertThat(defaults.curiosity()).isNull();
        assertThat(defaults.services()).isEmpty();
    }

    @Test
    void minimalProfile_loadsWithNullSections() throws IOException {
        var reg = registry("cognitive-profiles/");

        var bob = reg.forAgent("bob");
        assertThat(bob).isPresent();
        assertThat(bob.get().tenantId()).isNull();
        assertThat(bob.get().personality()).isNull();
        assertThat(bob.get().vocabulary()).isNull();
    }

    @Test
    void emptyPath_producesEmptyRegistry() throws IOException {
        var reg = registry("cognitive-profiles-nonexistent/");

        assertThat(reg.allProfiles()).isEmpty();
        assertThat(reg.forAgent("alice")).isEmpty();
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDefaultsRegistryTest -f pom.xml`
Expected: Compilation failure — `CognitiveDefaultsRegistry` does not exist.

- [ ] **Step 3: Implement CognitiveDefaultsRegistry**

```java
package io.casehub.neocortex.cognitive.index;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.module.SimpleModule;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import io.casehub.neocortex.memory.personality.PersonalityWeights;
import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.util.Collection;
import java.util.Enumeration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.logging.Level;
import java.util.logging.Logger;
import org.eclipse.microprofile.config.inject.ConfigProperty;

@ApplicationScoped
public class CognitiveDefaultsRegistry {

    private static final Logger LOG = Logger.getLogger(CognitiveDefaultsRegistry.class.getName());

    @Inject
    @ConfigProperty(name = "casehub.cognitive.profiles.path", defaultValue = "cognitive-profiles/")
    String profilesPath;

    private Map<String, CognitiveDefaults> profiles = Map.of();

    CognitiveDefaultsRegistry() {}

    @PostConstruct
    void init() {
        try {
            var loaded = loadFromClasspath(profilesPath,
                Thread.currentThread().getContextClassLoader());
            this.profiles = loaded.profiles;
            if (!profiles.isEmpty()) {
                LOG.info("Loaded " + profiles.size() + " cognitive profile(s): "
                    + String.join(", ", profiles.keySet()));
            }
        } catch (IOException e) {
            throw new RuntimeException("Failed to load cognitive profiles from " + profilesPath, e);
        }
    }

    public Optional<CognitiveDefaults> forAgent(String agentId) {
        return Optional.ofNullable(profiles.get(agentId));
    }

    public CognitiveDefaults forAgentOrDefaults(String agentId) {
        return profiles.getOrDefault(agentId,
            new CognitiveDefaults(agentId, null, null, null, null, null, null, null));
    }

    public Collection<CognitiveDefaults> allProfiles() {
        return profiles.values();
    }

    static CognitiveDefaultsRegistry loadFromClasspath(String path, ClassLoader classLoader)
            throws IOException {
        ObjectMapper mapper = new ObjectMapper(new YAMLFactory()).findAndRegisterModules();
        var module = new SimpleModule();
        module.addDeserializer(PersonalityWeights.class, new PersonalityWeightsDeserializer());
        mapper.registerModule(module);

        Map<String, CognitiveDefaults> loaded = new LinkedHashMap<>();
        String normalizedPath = path.endsWith("/") ? path : path + "/";

        Enumeration<URL> resources = classLoader.getResources(normalizedPath);
        while (resources.hasMoreElements()) {
            URL dirUrl = resources.nextElement();
            if ("file".equals(dirUrl.getProtocol())) {
                var dir = new java.io.File(dirUrl.getFile());
                if (dir.isDirectory()) {
                    var files = dir.listFiles((d, name) ->
                        name.endsWith(".yaml") || name.endsWith(".yml"));
                    if (files != null) {
                        for (var file : files) {
                            try (InputStream is = new java.io.FileInputStream(file)) {
                                var defaults = mapper.readValue(is, CognitiveDefaults.class);
                                addProfile(loaded, defaults, file.getName());
                            }
                        }
                    }
                }
            }
        }

        var registry = new CognitiveDefaultsRegistry();
        registry.profiles = Map.copyOf(loaded);
        return registry;
    }

    private static void addProfile(Map<String, CognitiveDefaults> map,
            CognitiveDefaults defaults, String source) {
        if (map.containsKey(defaults.agentId())) {
            throw new IllegalStateException(
                "Duplicate agentId '" + defaults.agentId()
                    + "' in cognitive profile: " + source);
        }
        map.put(defaults.agentId(), defaults);
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDefaultsRegistryTest -f pom.xml`
Expected: All 6 tests PASS.

- [ ] **Step 5: Run full cognitive-index test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -f pom.xml`
Expected: All tests PASS.

- [ ] **Step 6: Verify full reactor build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests -f pom.xml`
Expected: BUILD SUCCESS.

- [ ] **Step 7: Update CLAUDE.md**

Add to cognitive-index module description: `CognitiveDefaults (per-agent cognitive config record from YAML — personality, mood baseline, curiosity, temporal focus, vocabulary, services), CognitiveDefaultsRegistry (@ApplicationScoped — classpath scan for cognitive-profiles/*.yaml, runtime lookup by agentId), PersonalityWeightsDeserializer (MemoryDomain key wrapping for YAML parsing)`.

Add to Maven coordinates: `| Root Java package (cognitive-defaults) | io.casehub.neocortex.cognitive.index |` — already covered by existing cognitive-index entry.

- [ ] **Step 8: Commit**

```bash
git add cognitive-index/ CLAUDE.md
git commit -m "feat(cognitive-index): CognitiveDefaultsRegistry — YAML-driven agent cognitive configuration

Classpath scan for cognitive-profiles/*.yaml at startup. Per-agent
lookup via forAgent(agentId) and forAgentOrDefaults(agentId).
Configurable path via casehub.cognitive.profiles.path.

Closes #248"
```

---

## References

- `specs/issue-253-cognitive-rearchitecture/2026-09-01-cognitive-defaults-design.md` — design spec
- `cognitive-index/pom.xml` — existing dependencies
- `memory-api/src/main/java/io/casehub/neocortex/memory/personality/PersonalityWeights.java` — MemoryDomain map
- `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodBaseline.java` — PAD record
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CuriosityConfig.java` — 10-field config
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/TemporalFocusConfig.java` — 4-field config
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapVocabulary.java` — edge type list
- GE-20260602-a4d290 — ObjectMapper requires findAndRegisterModules()
- GitHub #248 — focal issue
- GitHub #253 — parent epic
