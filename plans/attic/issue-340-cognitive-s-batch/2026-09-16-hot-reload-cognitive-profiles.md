# Hot-Reload Cognitive Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #270 — feat: hot-reload cognitive profiles — file-watch YAML config without restart
**Issue group:** #270

**Goal:** Enable live reload of cognitive profiles and global rules from filesystem directories without restart, using `io.methvin:directory-watcher` with atomic volatile swaps and CDI event notification.

**Architecture:** A new `CognitiveProfileWatcher` bean in `cognitive-index` uses DirectoryWatcher to monitor configurable filesystem directories. On change, it re-parses all YAML, merges with classpath baselines, performs atomic volatile swaps on `CognitiveDefaultsRegistry` and `DeclarativeRuleRegistry`, and fires a `CognitiveProfilesReloaded` CDI event. `CognitiveLoader` observes the event to re-register vocabulary.

**Tech Stack:** Java 21, Quarkus CDI, `io.methvin:directory-watcher` 0.19.1, Jackson YAML, JUnit 5, AssertJ, Awaitility

## Global Constraints

- Java 21 source, Java 26 JVM
- All new code in `cognitive-index` module (watcher, registries) and `mindmap-intelligence` (CognitiveLoader observer)
- `io.methvin:directory-watcher` 0.19.1 — version managed in parent POM
- Config-gated: `casehub.cognitive.profiles-dir` and `casehub.cognitive.rules-dir` — absent = no watching
- Immutable collections throughout: `Map.copyOf()`, `List.copyOf()`
- Thread safety: volatile reference swaps, no locks on read path

---

## Batch 1: Atomic reload infrastructure

After this batch, both registries support thread-safe atomic reload via package-private methods, and CognitiveLoader can observe reload events. Nothing triggers reloads yet — that comes in Batch 2.

### Task 1: Registry reload methods + CognitiveProfilesReloaded event

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfilesReloaded.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistry.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DeclarativeRuleRegistry.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/RegistryReloadTest.java`

**Interfaces:**
- Produces: `CognitiveDefaultsRegistry.reload(Map<String, CognitiveDefaults>)` — package-private
- Produces: `DeclarativeRuleRegistry.reloadGlobalRules(List<DeclarativeTraitRule>, List<DeclarativeDerivedEdgeRule>)` — package-private
- Produces: `CognitiveProfilesReloaded(Collection<CognitiveDefaults> profiles)` — public record

- [ ] **Step 1: Write failing test — CognitiveDefaultsRegistry.reload() swaps profiles**

```java
// cognitive-index/src/test/java/.../RegistryReloadTest.java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class RegistryReloadTest {

    @Test
    void reload_swapsProfilesAtomically() {
        var registry = CognitiveDefaultsRegistry.forTesting(
            CognitiveDefaults.empty("alice"));

        assertThat(registry.forAgent("alice")).isPresent();
        assertThat(registry.forAgent("bob")).isEmpty();

        registry.reload(java.util.Map.of(
            "bob", CognitiveDefaults.empty("bob")));

        assertThat(registry.forAgent("alice")).isEmpty();
        assertThat(registry.forAgent("bob")).isPresent();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=RegistryReloadTest#reload_swapsProfilesAtomically -DfailIfNoTests=false`
Expected: FAIL — `reload` method does not exist

- [ ] **Step 3: Implement CognitiveDefaultsRegistry.reload() + volatile field**

In `CognitiveDefaultsRegistry.java`:
- Change `private Map<String, CognitiveDefaults> profiles` to `private volatile Map<String, CognitiveDefaults> profiles`
- Add package-private method:

```java
void reload(Map<String, CognitiveDefaults> newProfiles) {
    this.profiles = Map.copyOf(newProfiles);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=RegistryReloadTest#reload_swapsProfilesAtomically -DfailIfNoTests=false`
Expected: PASS

- [ ] **Step 5: Write failing test — DeclarativeRuleRegistry.reloadGlobalRules() swaps atomically**

Add to `RegistryReloadTest.java`:

```java
@Test
void reloadGlobalRules_swapsAtomically() {
    var traitRule = new io.casehub.neocortex.mindmap.DeclarativeTraitRule(
        "TestTrait",
        new io.casehub.neocortex.mindmap.RuleCondition.HasEdgeTypes(java.util.List.of("knows")),
        null, null, null, null);
    var registry = DeclarativeRuleRegistry.of(java.util.List.of(), java.util.List.of());

    assertThat(registry.traitRules(null)).isEmpty();

    registry.reloadGlobalRules(
        java.util.List.of(traitRule),
        java.util.List.of());

    assertThat(registry.traitRules(null)).hasSize(1);
    assertThat(registry.traitRules(null).get(0).traitName()).isEqualTo("TestTrait");
}

@Test
void reloadGlobalRules_traitAndDerivedAreConsistent() {
    var registry = DeclarativeRuleRegistry.of(java.util.List.of(), java.util.List.of());

    var traitRule = new io.casehub.neocortex.mindmap.DeclarativeTraitRule(
        "NewTrait",
        new io.casehub.neocortex.mindmap.RuleCondition.HasEdgeTypes(java.util.List.of("knows")),
        null, null, null, null);
    var edgeRule = new io.casehub.neocortex.mindmap.DeclarativeDerivedEdgeRule(
        "new-edge", null, java.util.List.of());

    registry.reloadGlobalRules(
        java.util.List.of(traitRule),
        java.util.List.of(edgeRule));

    assertThat(registry.traitRules(null)).hasSize(1);
    assertThat(registry.derivedEdgeRules(null)).hasSize(1);
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=RegistryReloadTest -DfailIfNoTests=false`
Expected: FAIL — `reloadGlobalRules` method does not exist

- [ ] **Step 7: Introduce GlobalRules holder + refactor DeclarativeRuleRegistry**

In `DeclarativeRuleRegistry.java`:

1. Add private record:
```java
private record GlobalRules(List<DeclarativeTraitRule> traitRules,
                           List<DeclarativeDerivedEdgeRule> derivedEdgeRules) {}
```

2. Replace the two fields:
```java
// REMOVE:
// private List<DeclarativeTraitRule>       globalTraitRules   = List.of();
// private List<DeclarativeDerivedEdgeRule> globalDerivedRules = List.of();
// ADD:
private volatile GlobalRules globalRules = new GlobalRules(List.of(), List.of());
```

3. Update `init()`:
```java
this.globalRules = new GlobalRules(
    List.copyOf(result.traitRules()),
    List.copyOf(result.derivedEdgeRules()));
```

4. Update constructor:
```java
this.globalRules = new GlobalRules(List.copyOf(globalTraitRules), List.copyOf(globalDerivedRules));
```

5. Update all read methods to snapshot `globalRules` with a single volatile read:
```java
public List<TraitRule> traitRules(String agentId) {
    var merged = new LinkedHashMap<String, TraitRule>();
    GlobalRules snapshot = globalRules;
    snapshot.traitRules().forEach(r -> merged.put(r.traitName(), r));
    // ... per-agent merge unchanged
    return List.copyOf(merged.values());
}
```

Apply the same pattern to `allTraitRules()`, `derivedEdgeRules(agentId)`, `allDerivedEdgeRules()`.

6. Add package-private reload method:
```java
void reloadGlobalRules(List<DeclarativeTraitRule> traitRules,
                       List<DeclarativeDerivedEdgeRule> derivedRules) {
    this.globalRules = new GlobalRules(
        List.copyOf(traitRules), List.copyOf(derivedRules));
}
```

7. Update `loadFromClasspath`:
```java
static DeclarativeRuleRegistry loadFromClasspath(String rulesPath,
                                                  CognitiveDefaultsRegistry cognitiveDefaults,
                                                  ClassLoader classLoader) throws IOException {
    RuleFile loaded = loadGlobalRules(rulesPath, classLoader);
    return new DeclarativeRuleRegistry(loaded.traitRules(), loaded.derivedEdgeRules(), cognitiveDefaults);
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=RegistryReloadTest -DfailIfNoTests=false`
Expected: PASS (all 3 tests)

- [ ] **Step 9: Run existing DeclarativeRuleRegistryTest to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=DeclarativeRuleRegistryTest -DfailIfNoTests=false`
Expected: PASS

- [ ] **Step 10: Create CognitiveProfilesReloaded event record**

```java
// cognitive-index/src/main/java/.../CognitiveProfilesReloaded.java
package io.casehub.neocortex.cognitive.index;

import java.util.Collection;

public record CognitiveProfilesReloaded(Collection<CognitiveDefaults> profiles) {
    public CognitiveProfilesReloaded {
        profiles = java.util.List.copyOf(profiles);
    }
}
```

- [ ] **Step 11: Run full cognitive-index test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: PASS — all existing tests still green

- [ ] **Step 12: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfilesReloaded.java cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistry.java cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DeclarativeRuleRegistry.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/RegistryReloadTest.java
git commit -m "feat: atomic reload infrastructure for cognitive registries

Introduce GlobalRules holder for torn-read prevention in
DeclarativeRuleRegistry, volatile fields + reload() methods on both
registries, and CognitiveProfilesReloaded CDI event record.

Refs #270"
```

---

### Task 2: CognitiveLoader reload observer

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoader.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoaderReloadTest.java`

**Interfaces:**
- Consumes: `CognitiveProfilesReloaded(Collection<CognitiveDefaults> profiles)` from Task 1
- Consumes: `MindMapStore.registerVocabulary(MindMapVocabulary)` — existing SPI
- Consumes: `VocabularyConflictException` — existing exception from `mindmap-api`

- [ ] **Step 1: Write failing test — observer re-registers vocabulary**

```java
// mindmap-intelligence/src/test/.../CognitiveLoaderReloadTest.java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.cognitive.index.CognitiveDefaults;
import io.casehub.neocortex.cognitive.index.CognitiveProfilesReloaded;
import io.casehub.neocortex.mindmap.EdgeTypeDefinition;
import io.casehub.neocortex.mindmap.MindMapVocabulary;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

class CognitiveLoaderReloadTest {

    @Test
    void onProfilesReloaded_registersVocabularyForAllProfiles() {
        var store = new InMemoryMindMapStore();
        var loader = new CognitiveLoader(store, null, List.of());

        var vocab = new MindMapVocabulary(List.of(
            new EdgeTypeDefinition("likes", List.of(), null)));
        var profile = CognitiveDefaults.empty("agent-1").withVocabulary(vocab);

        loader.onProfilesReloaded(new CognitiveProfilesReloaded(List.of(profile)));

        assertThat(store.vocabulary().edgeTypes()).anyMatch(
            e -> e.canonical().equals("likes"));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveLoaderReloadTest#onProfilesReloaded_registersVocabularyForAllProfiles -DfailIfNoTests=false`
Expected: FAIL — `onProfilesReloaded` method does not exist

- [ ] **Step 3: Implement observer method in CognitiveLoader**

Add to `CognitiveLoader.java`:

```java
import io.casehub.neocortex.cognitive.index.CognitiveProfilesReloaded;
import io.casehub.neocortex.mindmap.VocabularyConflictException;
import jakarta.enterprise.event.Observes;

void onProfilesReloaded(@Observes CognitiveProfilesReloaded event) {
    if (store == null) return;
    int registered = 0;
    for (CognitiveDefaults defaults : event.profiles()) {
        if (defaults.vocabulary() != null) {
            try {
                store.registerVocabulary(defaults.vocabulary());
                registered++;
            } catch (VocabularyConflictException e) {
                LOG.warning("Vocabulary conflict during reload for agent '"
                    + defaults.agentId() + "': " + e.getMessage());
            }
        }
    }
    if (registered > 0) {
        LOG.info("Re-registered vocabulary from " + registered
            + " profile(s) after reload");
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveLoaderReloadTest#onProfilesReloaded_registersVocabularyForAllProfiles -DfailIfNoTests=false`
Expected: PASS

- [ ] **Step 5: Write failing test — profiles without vocabulary are skipped**

Add to `CognitiveLoaderReloadTest.java`:

```java
@Test
void onProfilesReloaded_skipsProfilesWithoutVocabulary() {
    var store = new InMemoryMindMapStore();
    var loader = new CognitiveLoader(store, null, List.of());

    var profile = CognitiveDefaults.empty("agent-no-vocab");

    loader.onProfilesReloaded(new CognitiveProfilesReloaded(List.of(profile)));

    assertThat(store.vocabulary().edgeTypes()).isEmpty();
}
```

- [ ] **Step 6: Run test to verify it passes (already handled)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=CognitiveLoaderReloadTest -DfailIfNoTests=false`
Expected: PASS (both tests)

- [ ] **Step 7: Write test — null store gracefully skips**

```java
@Test
void onProfilesReloaded_noStore_doesNotThrow() {
    var loader = new CognitiveLoader(null, null, List.of());

    var vocab = new MindMapVocabulary(List.of(
        new EdgeTypeDefinition("likes", List.of(), null)));
    var profile = CognitiveDefaults.empty("agent-1").withVocabulary(vocab);

    loader.onProfilesReloaded(new CognitiveProfilesReloaded(List.of(profile)));
    // no exception = pass
}
```

- [ ] **Step 8: Run all CognitiveLoader tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest="CognitiveLoader*" -DfailIfNoTests=false`
Expected: PASS (all tests including existing CognitiveLoaderTest)

- [ ] **Step 9: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoader.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoaderReloadTest.java
git commit -m "feat: CognitiveLoader observes CognitiveProfilesReloaded for vocabulary re-registration

Catches VocabularyConflictException per-profile to avoid breaking
the reload pipeline when vocabulary definitions conflict.

Refs #270"
```

---

## Batch 2: CognitiveProfileWatcher

After this batch, the full hot-reload pipeline is functional: file change → parse → merge → atomic swap → CDI event → vocabulary re-registration.

### Task 3: CognitiveProfileWatcher — filesystem loading + merge + DirectoryWatcher lifecycle

**Files:**
- Modify: `cognitive-index/pom.xml`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfileWatcher.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveProfileWatcherTest.java`

**Interfaces:**
- Consumes: `CognitiveDefaultsRegistry.reload(Map<String, CognitiveDefaults>)` from Task 1
- Consumes: `DeclarativeRuleRegistry.reloadGlobalRules(List, List)` from Task 1
- Consumes: `CognitiveProfilesReloaded` event from Task 1
- Consumes: `CognitiveDefaultsRegistry.createMapper()` — existing static method for YAML parsing
- Consumes: `DirectoryWatcher` from `io.methvin:directory-watcher`

- [ ] **Step 1: Add dependencies to cognitive-index/pom.xml**

Add to `<dependencies>`:

```xml
<dependency>
    <groupId>io.methvin</groupId>
    <artifactId>directory-watcher</artifactId>
</dependency>
<dependency>
    <groupId>org.eclipse.microprofile.config</groupId>
    <artifactId>microprofile-config-api</artifactId>
    <scope>provided</scope>
</dependency>
<dependency>
    <groupId>org.awaitility</groupId>
    <artifactId>awaitility</artifactId>
    <scope>test</scope>
</dependency>
```

- [ ] **Step 2: Write failing test — loadProfilesFromDirectory reads YAML files**

```java
// cognitive-index/src/test/.../CognitiveProfileWatcherTest.java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class CognitiveProfileWatcherTest {

    @TempDir Path tempDir;

    @Test
    void loadProfilesFromDirectory_readsYamlFiles() throws IOException {
        Files.writeString(tempDir.resolve("agent-x.yaml"),
            "agentId: agent-x\n");

        Map<String, CognitiveDefaults> profiles =
            CognitiveProfileWatcher.loadProfilesFromDirectory(tempDir);

        assertThat(profiles).hasSize(1);
        assertThat(profiles.get("agent-x").agentId()).isEqualTo("agent-x");
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest#loadProfilesFromDirectory_readsYamlFiles -DfailIfNoTests=false`
Expected: FAIL — class does not exist

- [ ] **Step 4: Create CognitiveProfileWatcher with loadProfilesFromDirectory**

```java
// cognitive-index/src/main/java/.../CognitiveProfileWatcher.java
package io.casehub.neocortex.cognitive.index;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.methvin.watcher.DirectoryChangeEvent;
import io.methvin.watcher.DirectoryWatcher;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Event;
import jakarta.inject.Inject;
import org.eclipse.microprofile.config.inject.ConfigProperty;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class CognitiveProfileWatcher {

    private static final Logger LOG = Logger.getLogger(
        CognitiveProfileWatcher.class.getName());
    private static final long DEBOUNCE_MS = 500;

    private final CognitiveDefaultsRegistry registry;
    private final DeclarativeRuleRegistry ruleRegistry;
    private final Event<CognitiveProfilesReloaded> reloadEvent;
    private final Optional<Path> profilesDir;
    private final Optional<Path> rulesDir;

    private Map<String, CognitiveDefaults> classpathProfiles;
    private RuleFile classpathRules;

    private volatile DirectoryWatcher profilesWatcher;
    private volatile DirectoryWatcher rulesWatcher;
    private ScheduledExecutorService debounceExecutor;
    private ScheduledFuture<?> pendingProfilesFlush;
    private ScheduledFuture<?> pendingRulesFlush;
    private final Object flushLock = new Object();

    @Inject
    CognitiveProfileWatcher(CognitiveDefaultsRegistry registry,
                            DeclarativeRuleRegistry ruleRegistry,
                            Event<CognitiveProfilesReloaded> reloadEvent,
                            @ConfigProperty(name = "casehub.cognitive.profiles-dir")
                                Optional<Path> profilesDir,
                            @ConfigProperty(name = "casehub.cognitive.rules-dir")
                                Optional<Path> rulesDir) {
        this.registry = registry;
        this.ruleRegistry = ruleRegistry;
        this.reloadEvent = reloadEvent;
        this.profilesDir = profilesDir;
        this.rulesDir = rulesDir;
    }

    CognitiveProfileWatcher(CognitiveDefaultsRegistry registry,
                            DeclarativeRuleRegistry ruleRegistry,
                            Event<CognitiveProfilesReloaded> reloadEvent,
                            Path profilesDir, Path rulesDir) {
        this.registry = registry;
        this.ruleRegistry = ruleRegistry;
        this.reloadEvent = reloadEvent;
        this.profilesDir = Optional.ofNullable(profilesDir);
        this.rulesDir = Optional.ofNullable(rulesDir);
    }

    static Map<String, CognitiveDefaults> loadProfilesFromDirectory(Path dir)
            throws IOException {
        ObjectMapper mapper = CognitiveDefaultsRegistry.createMapper();
        Map<String, CognitiveDefaults> loaded = new LinkedHashMap<>();
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(dir,
                p -> {
                    String name = p.getFileName().toString();
                    return (name.endsWith(".yaml") || name.endsWith(".yml"))
                        && !name.startsWith(".");
                })) {
            for (Path file : stream) {
                CognitiveDefaults defaults = mapper.readValue(
                    file.toFile(), CognitiveDefaults.class);
                CognitiveDefaultsRegistry.addProfile(loaded, defaults,
                    file.getFileName().toString());
            }
        }
        return loaded;
    }

    static RuleFile loadRulesFromDirectory(Path dir) throws IOException {
        ObjectMapper mapper = CognitiveDefaultsRegistry.createMapper();
        var traitRules = new java.util.ArrayList<
            io.casehub.neocortex.mindmap.DeclarativeTraitRule>();
        var derivedRules = new java.util.ArrayList<
            io.casehub.neocortex.mindmap.DeclarativeDerivedEdgeRule>();
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(dir,
                p -> {
                    String name = p.getFileName().toString();
                    return (name.endsWith(".yaml") || name.endsWith(".yml"))
                        && !name.startsWith(".");
                })) {
            for (Path file : stream) {
                RuleFile ruleFile = mapper.readValue(
                    file.toFile(), RuleFile.class);
                traitRules.addAll(ruleFile.traitRules());
                derivedRules.addAll(ruleFile.derivedEdgeRules());
            }
        }
        return new RuleFile(traitRules, derivedRules);
    }

    static Map<String, CognitiveDefaults> merge(
            Map<String, CognitiveDefaults> classpath,
            Map<String, CognitiveDefaults> filesystem) {
        var merged = new LinkedHashMap<>(classpath);
        merged.putAll(filesystem);
        return merged;
    }
    // ... lifecycle methods added in later steps
}
```

Note: `CognitiveDefaultsRegistry.addProfile()` needs to be changed from `private static` to `static` (package-private). Modify accordingly.

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest#loadProfilesFromDirectory_readsYamlFiles -DfailIfNoTests=false`
Expected: PASS

- [ ] **Step 6: Write failing test — merge: filesystem overrides classpath**

Add to `CognitiveProfileWatcherTest.java`:

```java
@Test
void merge_filesystemOverridesClasspath() {
    var classpath = Map.of(
        "alice", CognitiveDefaults.empty("alice"),
        "bob", CognitiveDefaults.empty("bob"));
    var filesystem = Map.of(
        "alice", CognitiveDefaults.empty("alice").withTenantId("overridden"));

    var merged = CognitiveProfileWatcher.merge(classpath, filesystem);

    assertThat(merged).hasSize(2);
    assertThat(merged.get("alice").tenantId()).isEqualTo("overridden");
    assertThat(merged.get("bob").agentId()).isEqualTo("bob");
}
```

- [ ] **Step 7: Run test to verify it passes (merge logic already implemented)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest -DfailIfNoTests=false`
Expected: PASS

- [ ] **Step 8: Write failing test — invalid YAML rejects reload, keeps previous state**

```java
@Test
void reloadProfiles_invalidYaml_keepsPreviousState() throws IOException {
    Files.writeString(tempDir.resolve("good.yaml"), "agentId: good\n");
    var registry = CognitiveDefaultsRegistry.forTesting(
        CognitiveDefaults.empty("original"));

    var watcher = new CognitiveProfileWatcher(
        registry, null, e -> {}, tempDir, null);
    watcher.snapshotBaselines();
    watcher.reloadProfiles();

    assertThat(registry.forAgent("good")).isPresent();

    Files.writeString(tempDir.resolve("bad.yaml"), "{{invalid yaml");

    watcher.reloadProfiles();

    assertThat(registry.forAgent("good")).isPresent();
}
```

- [ ] **Step 9: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest#reloadProfiles_invalidYaml_keepsPreviousState -DfailIfNoTests=false`
Expected: FAIL — `snapshotBaselines` and `reloadProfiles` methods do not exist

- [ ] **Step 10: Implement snapshotBaselines() and reloadProfiles()**

Add to `CognitiveProfileWatcher`:

```java
void snapshotBaselines() {
    var profileMap = new LinkedHashMap<String, CognitiveDefaults>();
    registry.allProfiles().forEach(p -> profileMap.put(p.agentId(), p));
    this.classpathProfiles = Map.copyOf(profileMap);
    this.classpathRules = ruleRegistry != null
        ? ruleRegistry.currentGlobalRules() : new RuleFile(java.util.List.of(), java.util.List.of());
}

void reloadProfiles() {
    if (profilesDir.isEmpty()) return;
    try {
        var filesystem = loadProfilesFromDirectory(profilesDir.get());
        var merged = merge(classpathProfiles, filesystem);
        registry.reload(merged);
        LOG.info("Reloaded " + merged.size() + " cognitive profile(s)");
        reloadEvent.fire(new CognitiveProfilesReloaded(merged.values()));
    } catch (Exception e) {
        LOG.log(Level.WARNING,
            "Failed to reload cognitive profiles — keeping previous state", e);
    }
}

void reloadRules() {
    if (rulesDir.isEmpty() || ruleRegistry == null) return;
    try {
        var filesystem = loadRulesFromDirectory(rulesDir.get());
        var mergedTrait = new java.util.ArrayList<>(classpathRules.traitRules());
        var namesSeen = new java.util.HashSet<String>();
        filesystem.traitRules().forEach(r -> namesSeen.add(r.traitName()));
        mergedTrait.removeIf(r -> namesSeen.contains(r.traitName()));
        mergedTrait.addAll(filesystem.traitRules());

        var mergedDerived = new java.util.ArrayList<>(classpathRules.derivedEdgeRules());
        var derivedNamesSeen = new java.util.HashSet<String>();
        filesystem.derivedEdgeRules().forEach(r -> derivedNamesSeen.add(r.name()));
        mergedDerived.removeIf(r -> derivedNamesSeen.contains(r.name()));
        mergedDerived.addAll(filesystem.derivedEdgeRules());

        ruleRegistry.reloadGlobalRules(mergedTrait, mergedDerived);
        LOG.info("Reloaded " + mergedTrait.size() + " global trait rule(s) and "
            + mergedDerived.size() + " global derived edge rule(s)");
    } catch (Exception e) {
        LOG.log(Level.WARNING,
            "Failed to reload global rules — keeping previous state", e);
    }
}
```

Also add to `DeclarativeRuleRegistry`:

```java
GlobalRules currentGlobalRules() {
    return globalRules;
}
```

Wait — `GlobalRules` is private. Either make it package-private, or expose `currentGlobalTraitRules()` and `currentGlobalDerivedRules()` separately. Since `CognitiveProfileWatcher` is in the same package, making `GlobalRules` package-private is cleanest. Change `private record GlobalRules` to `record GlobalRules` (package-private).

Actually, the watcher just needs the classpath rules as a baseline. It doesn't need the `GlobalRules` type — it can snapshot trait rules and derived rules separately via public methods. But `allTraitRules()` merges per-agent rules too. Better to expose a `currentGlobalRules()` returning a `RuleFile`:

```java
RuleFile currentGlobalRules() {
    GlobalRules snapshot = globalRules;
    return new RuleFile(snapshot.traitRules(), snapshot.derivedEdgeRules());
}
```

- [ ] **Step 11: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest#reloadProfiles_invalidYaml_keepsPreviousState -DfailIfNoTests=false`
Expected: PASS

- [ ] **Step 12: Write failing test — file change triggers reload + event**

```java
import static org.awaitility.Awaitility.await;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicReference;

@Test
void fileChange_triggersReloadAndFiresEvent() throws Exception {
    Files.writeString(tempDir.resolve("agent-1.yaml"), "agentId: agent-1\n");

    var registry = CognitiveDefaultsRegistry.forTesting(
        new CognitiveDefaults[0]);
    var firedEvent = new AtomicReference<CognitiveProfilesReloaded>();
    var watcher = new CognitiveProfileWatcher(
        registry, null, firedEvent::set, tempDir, null);
    watcher.snapshotBaselines();
    watcher.reloadProfiles();
    watcher.startWatching();

    try {
        assertThat(registry.forAgent("agent-1")).isPresent();

        Thread.sleep(1000); // warmup — macOS catch-up events

        Files.writeString(tempDir.resolve("agent-2.yaml"),
            "agentId: agent-2\n");

        await().atMost(15, TimeUnit.SECONDS).untilAsserted(() -> {
            assertThat(registry.forAgent("agent-2")).isPresent();
            assertThat(firedEvent.get()).isNotNull();
            assertThat(firedEvent.get().profiles()).hasSize(2);
        });
    } finally {
        watcher.stopWatching();
    }
}
```

- [ ] **Step 13: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest#fileChange_triggersReloadAndFiresEvent -DfailIfNoTests=false`
Expected: FAIL — `startWatching` and `stopWatching` methods do not exist

- [ ] **Step 14: Implement DirectoryWatcher lifecycle with debounce**

Add to `CognitiveProfileWatcher`:

```java
@PostConstruct
void init() {
    if (profilesDir.isEmpty() && rulesDir.isEmpty()) return;

    snapshotBaselines();

    profilesDir.ifPresent(dir -> {
        try {
            Files.createDirectories(dir);
            reloadProfiles();
        } catch (IOException e) {
            LOG.log(Level.WARNING,
                "Failed to create profiles directory: " + dir, e);
        }
    });

    rulesDir.ifPresent(dir -> {
        try {
            Files.createDirectories(dir);
            reloadRules();
        } catch (IOException e) {
            LOG.log(Level.WARNING,
                "Failed to create rules directory: " + dir, e);
        }
    });

    try {
        startWatching();
    } catch (Exception e) {
        LOG.log(Level.WARNING,
            "Failed to start file watchers — "
            + "running with classpath-only profiles", e);
    }
}

@PreDestroy
void destroy() {
    stopWatching();
}

void startWatching() {
    debounceExecutor = Executors.newSingleThreadScheduledExecutor(r -> {
        Thread t = new Thread(r, "cognitive-profile-watcher-debounce");
        t.setDaemon(true);
        return t;
    });

    profilesDir.ifPresent(dir -> {
        try {
            profilesWatcher = DirectoryWatcher.builder()
                .path(dir)
                .listener(event -> onProfilesEvent(event))
                .build();
            profilesWatcher.watchAsync();
            LOG.info("Watching cognitive profiles: " + dir);
        } catch (IOException e) {
            LOG.log(Level.WARNING,
                "Failed to create profiles watcher — "
                + "profiles will not auto-reload", e);
        }
    });

    rulesDir.ifPresent(dir -> {
        try {
            rulesWatcher = DirectoryWatcher.builder()
                .path(dir)
                .listener(event -> onRulesEvent(event))
                .build();
            rulesWatcher.watchAsync();
            LOG.info("Watching global rules: " + dir);
        } catch (IOException e) {
            LOG.log(Level.WARNING,
                "Failed to create rules watcher — "
                + "rules will not auto-reload", e);
        }
    });
}

void stopWatching() {
    synchronized (flushLock) {
        if (pendingProfilesFlush != null) {
            pendingProfilesFlush.cancel(false);
            pendingProfilesFlush = null;
        }
        if (pendingRulesFlush != null) {
            pendingRulesFlush.cancel(false);
            pendingRulesFlush = null;
        }
    }
    if (profilesWatcher != null) {
        try { profilesWatcher.close(); } catch (IOException e) {
            LOG.log(Level.WARNING, "Error closing profiles watcher", e);
        }
        profilesWatcher = null;
    }
    if (rulesWatcher != null) {
        try { rulesWatcher.close(); } catch (IOException e) {
            LOG.log(Level.WARNING, "Error closing rules watcher", e);
        }
        rulesWatcher = null;
    }
    if (debounceExecutor != null) {
        debounceExecutor.shutdownNow();
        debounceExecutor = null;
    }
}

private void onProfilesEvent(DirectoryChangeEvent event) {
    if (event.eventType() == DirectoryChangeEvent.EventType.OVERFLOW) {
        scheduleProfilesFlush();
        return;
    }
    if (event.path() == null || Files.isDirectory(event.path())) return;
    String name = event.path().getFileName().toString();
    if (!name.endsWith(".yaml") && !name.endsWith(".yml")) return;
    if (name.startsWith(".")) return;
    scheduleProfilesFlush();
}

private void onRulesEvent(DirectoryChangeEvent event) {
    if (event.eventType() == DirectoryChangeEvent.EventType.OVERFLOW) {
        scheduleRulesFlush();
        return;
    }
    if (event.path() == null || Files.isDirectory(event.path())) return;
    String name = event.path().getFileName().toString();
    if (!name.endsWith(".yaml") && !name.endsWith(".yml")) return;
    if (name.startsWith(".")) return;
    scheduleRulesFlush();
}

private void scheduleProfilesFlush() {
    synchronized (flushLock) {
        if (debounceExecutor == null || debounceExecutor.isShutdown()) return;
        if (pendingProfilesFlush != null) pendingProfilesFlush.cancel(false);
        pendingProfilesFlush = debounceExecutor.schedule(
            this::reloadProfiles, DEBOUNCE_MS, TimeUnit.MILLISECONDS);
    }
}

private void scheduleRulesFlush() {
    synchronized (flushLock) {
        if (debounceExecutor == null || debounceExecutor.isShutdown()) return;
        if (pendingRulesFlush != null) pendingRulesFlush.cancel(false);
        pendingRulesFlush = debounceExecutor.schedule(
            this::reloadRules, DEBOUNCE_MS, TimeUnit.MILLISECONDS);
    }
}
```

- [ ] **Step 15: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest#fileChange_triggersReloadAndFiresEvent -DfailIfNoTests=false`
Expected: PASS

- [ ] **Step 16: Write test — rules-only change does NOT fire CognitiveProfilesReloaded**

```java
@Test
void rulesChange_doesNotFireProfilesEvent(@TempDir Path rulesDir) throws Exception {
    Files.writeString(rulesDir.resolve("test-rules.yaml"),
        "traitRules:\n  - trait: TestTrait\n    when:\n      hasEdgeTypes: [knows]\n");

    var registry = CognitiveDefaultsRegistry.forTesting(
        new CognitiveDefaults[0]);
    var ruleRegistry = DeclarativeRuleRegistry.of(
        java.util.List.of(), java.util.List.of());
    var firedEvent = new AtomicReference<CognitiveProfilesReloaded>();
    var watcher = new CognitiveProfileWatcher(
        registry, ruleRegistry, firedEvent::set, null, rulesDir);
    watcher.snapshotBaselines();
    watcher.reloadRules();
    watcher.startWatching();

    try {
        Thread.sleep(1000);

        Files.writeString(rulesDir.resolve("new-rule.yaml"),
            "traitRules:\n  - trait: NewTrait\n    when:\n      hasEdgeTypes: [likes]\n");

        await().atMost(15, TimeUnit.SECONDS).untilAsserted(() ->
            assertThat(ruleRegistry.traitRules(null)).anyMatch(
                r -> r.traitName().equals("NewTrait")));

        assertThat(firedEvent.get()).isNull();
    } finally {
        watcher.stopWatching();
    }
}
```

- [ ] **Step 17: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest#rulesChange_doesNotFireProfilesEvent -DfailIfNoTests=false`
Expected: PASS

- [ ] **Step 18: Write test — watcher creation failure degrades gracefully**

```java
@Test
void watcherCreationFailure_degradesGracefully() throws IOException {
    var registry = CognitiveDefaultsRegistry.forTesting(
        CognitiveDefaults.empty("existing"));
    var watcher = new CognitiveProfileWatcher(
        registry, null, e -> {},
        Path.of("/nonexistent/\0invalid"), null);

    watcher.snapshotBaselines();
    // startWatching should log warning but not throw
    watcher.startWatching();

    assertThat(registry.forAgent("existing")).isPresent();
    watcher.stopWatching();
}
```

- [ ] **Step 19: Run all CognitiveProfileWatcher tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveProfileWatcherTest -DfailIfNoTests=false`
Expected: PASS (all tests)

- [ ] **Step 20: Run full cognitive-index test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: PASS — all existing tests still green

- [ ] **Step 21: Run full project build to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl cognitive-index,mindmap-intelligence,mindmap -DskipTests=false`
Expected: PASS — downstream modules that depend on cognitive-index compile and test correctly

- [ ] **Step 22: Commit**

```bash
git add cognitive-index/pom.xml cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveProfileWatcher.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveProfileWatcherTest.java
git commit -m "feat: CognitiveProfileWatcher — file-watch YAML config without restart

Watches configurable filesystem directories for cognitive profile and
global rule YAML files. On change, re-parses all files, merges with
classpath baselines, and performs atomic volatile swaps. Fires
CognitiveProfilesReloaded CDI event for profile changes only.

Uses io.methvin:directory-watcher with 500ms debounce, matching the
existing FlatChangeSource pattern. Config-gated via
casehub.cognitive.profiles-dir and casehub.cognitive.rules-dir.

Closes #270"
```

---

## References

- [2026-09-16-hot-reload-cognitive-profiles-design.md] — design spec this plan implements
- [CognitiveDefaultsRegistry.java:41-138] — current classpath loading, `loadFromClasspath()`, `Map.copyOf()` pattern
- [DeclarativeRuleRegistry.java:39-174] — global rules loading, per-agent merge-on-read
- [CognitiveLoader.java:31-83] — vocabulary registration loop
- [FlatChangeSource.java:25-378] — DirectoryWatcher usage pattern (debounce, overflow, daemon thread)
- [RuleFile.java:23-31] — rule file record structure
- [alice.yaml] — sample cognitive profile YAML structure
- GitHub #270 — focal issue
- GitHub #253 — parent epic (cognitive rearchitecture)
