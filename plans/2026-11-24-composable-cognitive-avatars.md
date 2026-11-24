# Composable Cognitive Avatars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1219 — Briefed personality profiles — practical coach/mentor/assistant personas
**Issue group:** #1219

**Goal:** Deliver composable cognitive avatars — agents assembled from independent cognitive capabilities with per-prompt briefing, goals, temporal awareness, memory, and disposition config.

**Architecture:** New `cognitive-runtime` module between `cognitive-index` and `cognition`. `CognitiveCapability` SPI for composable cognitive functions. `CognitiveAvatar` composition root implements `CognitivePromptSource` (new narrower interface extracted from `CognitiveLifecycle`). Existing CDI infrastructure (MindMapStore, CaseMemoryStore, CognitiveDefaultsRegistry) consumed directly — no extraction from CognitionCore.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI (Jakarta), Jackson YAML, Maven

## Global Constraints

- Java 21 source (runs on Java 26 JVM)
- `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn` for all builds
- Use `mvn` not `./mvnw`
- All new code under `io.casehub.neocortex.cognitive.runtime` package
- Use `ide_insert_member` / `ide_replace_member` for code edits, not bash
- Every commit references `Refs #1219`
- CognitiveDefaults record changes must preserve backward compatibility (compact constructor defaults, `empty()` factory, `withX()` methods)

---

## Batch 1: Foundation — CognitivePromptSource + BriefingConfig

After this batch: `CognitivePromptSource` interface extracted from `CognitiveLifecycle`, `BriefingConfig` added to `CognitiveDefaults`, existing tests pass.

### Task 1: Extract CognitivePromptSource from CognitiveLifecycle

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/prompt/CognitivePromptSource.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/prompt/CognitiveLifecycle.java`
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/prompt/CognitivePromptSourceTest.java`

**Interfaces:**
- Produces: `CognitivePromptSource` interface with `initialize()`, `promptSections()`, `contributeBlocks()`, `salienceOf()`
- Consumed by: Task 4 (`CognitiveAvatar implements CognitivePromptSource`)

- [ ] **Step 1: Write failing test for CognitivePromptSource**

```java
package io.casehub.neocortex.cognition.prompt;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class CognitivePromptSourceTest {

    @Test
    void contributeBlocks_renders_active_sections() {
        var renderer = new CognitionPromptRenderer() {
            @Override public String render(CognitionRenderContext ctx) { return "test content"; }
            @Override public BlockTag blockTag() { return BlockTag.PERSONALITY; }
            @Override public SectionTier sectionTier() { return SectionTier.CORE; }
        };

        CognitivePromptSource source = new CognitivePromptSource() {
            @Override public List<CognitionPromptRenderer> promptSections() {
                return List.of(renderer);
            }
        };

        var ctx = new CognitionRenderContext("agent-1", "tenant-1", null);
        var blocks = source.contributeBlocks(ctx);
        assertEquals(1, blocks.size());
        assertEquals("test content", blocks.getFirst().content());
        assertEquals(1.0f, blocks.getFirst().salience());
    }

    @Test
    void contributeBlocks_skips_null_content() {
        var renderer = new CognitionPromptRenderer() {
            @Override public String render(CognitionRenderContext ctx) { return null; }
            @Override public BlockTag blockTag() { return BlockTag.PERSONALITY; }
        };

        CognitivePromptSource source = new CognitivePromptSource() {
            @Override public List<CognitionPromptRenderer> promptSections() {
                return List.of(renderer);
            }
        };

        var blocks = source.contributeBlocks(new CognitionRenderContext("a", "t", null));
        assertTrue(blocks.isEmpty());
    }

    @Test
    void cognitiveLifecycle_is_subtype() {
        assertTrue(CognitivePromptSource.class.isAssignableFrom(CognitiveLifecycle.class));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api -Dtest=CognitivePromptSourceTest -DfailIfNoTests=false`
Expected: Compilation failure — `CognitivePromptSource` does not exist

- [ ] **Step 3: Create CognitivePromptSource interface**

Create `cognition-api/src/main/java/io/casehub/neocortex/cognition/prompt/CognitivePromptSource.java`:

```java
package io.casehub.neocortex.cognition.prompt;

import io.casehub.eidos.api.PromptBlock;
import io.casehub.eidos.api.PromptTier;
import org.jspecify.annotations.Nullable;

import java.util.ArrayList;
import java.util.List;

public interface CognitivePromptSource {

    default void initialize(String agentId, String tenantId) {}

    List<CognitionPromptRenderer> promptSections();

    default List<PromptBlock> contributeBlocks(CognitionRenderContext context) {
        var blocks = new ArrayList<PromptBlock>();
        for (var renderer : promptSections()) {
            try {
                var content = renderer.render(context);
                if (content != null && !content.isBlank()) {
                    var tag = renderer.blockTag();
                    var simpleName = renderer.getClass().getSimpleName();
                    var tagName = tag != null ? tag.name()
                            : simpleName.isEmpty() ? renderer.getClass().getName() : simpleName;
                    var salience = salienceOf(renderer.sectionTier());
                    blocks.add(new PromptBlock(PromptTier.COGNITIVE, tagName, salience, content));
                }
            } catch (Exception e) {
                // skip — matches CognitiveLifecycle behaviour
            }
        }
        return List.copyOf(blocks);
    }

    private static float salienceOf(@Nullable SectionTier tier) {
        if (tier == null) return 0.5f;
        return switch (tier) {
            case CORE -> 1.0f;
            case CONTEXTUAL -> 0.6f;
            case SUPPLEMENTARY -> 0.3f;
        };
    }
}
```

- [ ] **Step 4: Make CognitiveLifecycle extend CognitivePromptSource**

Modify `CognitiveLifecycle.java`:
- Add `extends CognitivePromptSource`
- Remove `initialize()`, `promptSections()`, `contributeBlocks()`, `salienceOf()` — they now live in the supertype
- Keep `tick()`, `recordInteraction()`, `evaluateProactive()` — these are lifecycle-only

```java
public interface CognitiveLifecycle extends CognitivePromptSource {

    void tick(String agentId, String tenantId, Set<String> activeSubjects);

    default @Nullable String evaluateProactive(String agentId, String tenantId,
                                                String channelContext) {
        return null;
    }

    void recordInteraction(String agentId, String tenantId,
                           @Nullable String subjectId,
                           String userMessage, String response);
}
```

- [ ] **Step 5: Run tests to verify everything passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api`
Expected: All tests pass including existing `CognitiveLifecycleContributeBlocksTest`

- [ ] **Step 6: Verify CognitionCore still compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognition`
Expected: Compiles — CognitionCore implements CognitiveLifecycle which still has all the same methods via inheritance

- [ ] **Step 7: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/prompt/CognitivePromptSource.java cognition-api/src/main/java/io/casehub/neocortex/cognition/prompt/CognitiveLifecycle.java cognition-api/src/test/java/io/casehub/neocortex/cognition/prompt/CognitivePromptSourceTest.java
git commit -m "feat(cognition-api): extract CognitivePromptSource from CognitiveLifecycle

Interface segregation: CognitivePromptSource owns initialize(),
promptSections(), contributeBlocks(). CognitiveLifecycle extends it,
adding tick(), recordInteraction(), evaluateProactive().

Refs #1219

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: Add BriefingConfig to CognitiveDefaults

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/BriefingConfig.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/BriefingConfigTest.java`

**Interfaces:**
- Produces: `BriefingConfig` record (identity, grounding, echo), `CognitiveDefaults.briefing()` accessor
- Consumed by: Task 5 (`BriefingCapability`)

- [ ] **Step 1: Write failing test for BriefingConfig parsing**

```java
package io.casehub.neocortex.cognitive.index;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class BriefingConfigTest {

    @Test
    void parsesFromYaml() throws Exception {
        var yaml = """
                identity: You are a stoic mentor.
                grounding: Draw on your memories.
                echo: Think as a stoic would.
                """;
        var mapper = new ObjectMapper(new YAMLFactory());
        var config = mapper.readValue(yaml, BriefingConfig.class);
        assertEquals("You are a stoic mentor.", config.identity());
        assertEquals("Draw on your memories.", config.grounding());
        assertEquals("Think as a stoic would.", config.echo());
    }

    @Test
    void allFieldsNullable() throws Exception {
        var yaml = "{}";
        var mapper = new ObjectMapper(new YAMLFactory());
        var config = mapper.readValue(yaml, BriefingConfig.class);
        assertNull(config.identity());
        assertNull(config.grounding());
        assertNull(config.echo());
    }

    @Test
    void cognitiveDefaultsCarriesBriefing() throws Exception {
        var yaml = """
                agentId: test-agent
                briefing:
                  identity: You are a test persona.
                  echo: Think as a test would.
                """;
        var mapper = new ObjectMapper(new YAMLFactory());
        var defaults = mapper.readValue(yaml, CognitiveDefaults.class);
        assertNotNull(defaults.briefing());
        assertEquals("You are a test persona.", defaults.briefing().identity());
    }

    @Test
    void cognitiveDefaultsBriefingNullWhenAbsent() {
        var defaults = CognitiveDefaults.empty("test");
        assertNull(defaults.briefing());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=BriefingConfigTest -DfailIfNoTests=false`
Expected: Compilation failure — `BriefingConfig` does not exist

- [ ] **Step 3: Create BriefingConfig record**

Create `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/BriefingConfig.java`:

```java
package io.casehub.neocortex.cognitive.index;

import org.jspecify.annotations.Nullable;

public record BriefingConfig(
        @Nullable String identity,
        @Nullable String grounding,
        @Nullable String echo
) {}
```

- [ ] **Step 4: Add briefing field to CognitiveDefaults**

Add `@Nullable BriefingConfig briefing` as the 9th component of the `CognitiveDefaults` record. Update:
- Compact constructor: add `// briefing stays null when absent` (no defaulting needed)
- `empty()` factory: pass `null` for the new field
- All existing `withX()` methods: pass `this.briefing` to preserve it
- Add `withBriefing(BriefingConfig briefing)` method

Use `ide_replace_member` for the record header and compact constructor. Use `ide_insert_member` for `withBriefing()`.

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: All tests pass — existing profiles without `briefing` field parse correctly (Jackson ignores unknown-absent fields)

- [ ] **Step 6: Verify downstream modules compile**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognition,cognitive-eidos`
Expected: Compiles — record gains a component but all existing construction sites use named-parameter patterns or builders

- [ ] **Step 7: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/BriefingConfig.java cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/BriefingConfigTest.java
git commit -m "feat(cognitive-index): add BriefingConfig to CognitiveDefaults

Three-layer briefing (identity, grounding, echo) as optional 9th
component. Null when absent — backward compatible with existing profiles.

Refs #1219

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 2: cognitive-runtime module + capability SPI

After this batch: New Maven module exists with `CognitiveCapability` SPI, `CognitiveAvatarContext`, `CognitiveAvatar` composition root, `BriefingCapability`, and `CognitiveAvatarProducer`. Module compiles and tests pass.

### Task 3: Create cognitive-runtime Maven module

**Files:**
- Create: `cognitive-runtime/pom.xml`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/CognitiveCapability.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/CognitiveAvatarContext.java`
- Modify: `pom.xml` (parent — add module)
- Test: compilation only (SPI has no behavior to test alone)

**Interfaces:**
- Produces: `CognitiveCapability` SPI, `CognitiveAvatarContext` record
- Consumed by: Task 4 (`CognitiveAvatar`), Task 5-8 (capability implementations)

- [ ] **Step 1: Create module directory structure**

```bash
mkdir -p cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime
mkdir -p cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime
```

- [ ] **Step 2: Create pom.xml**

Create `cognitive-runtime/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>0.4-SNAPSHOT</version>
    </parent>
    <artifactId>casehub-neocortex-cognitive-runtime</artifactId>
    <name>CaseHub Neocortex Cognitive Runtime</name>
    <description>Composable cognitive avatar runtime — capability SPI, composition root, briefing</description>
    <dependencies>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-cognitive-index</artifactId>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-cognition-api</artifactId>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-mindmap-api</artifactId>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-api</artifactId>
        </dependency>
        <dependency>
            <groupId>jakarta.enterprise</groupId>
            <artifactId>jakarta.enterprise.cdi-api</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>jakarta.inject</groupId>
            <artifactId>jakarta.inject-api</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>org.jspecify</groupId>
            <artifactId>jspecify</artifactId>
        </dependency>
        <dependency>
            <groupId>org.junit.jupiter</groupId>
            <artifactId>junit-jupiter</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
```

- [ ] **Step 3: Add module to parent pom.xml**

Add `<module>cognitive-runtime</module>` to the parent `pom.xml` modules list, after `cognitive-index`.

- [ ] **Step 4: Create CognitiveCapability SPI**

Create `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/CognitiveCapability.java`:

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognition.prompt.CognitionPromptRenderer;
import java.util.List;

public interface CognitiveCapability {

    String name();

    default void initialize(CognitiveAvatarContext context) {}

    List<CognitionPromptRenderer> promptSections();

    default boolean isActive() { return true; }
}
```

- [ ] **Step 5: Create CognitiveAvatarContext**

Create `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/CognitiveAvatarContext.java`:

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognitive.index.CognitiveDefaults;

public record CognitiveAvatarContext(
        String agentId,
        String tenantId,
        CognitiveDefaults profile
) {}
```

- [ ] **Step 6: Verify module compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognitive-runtime`
Expected: Compiles successfully

- [ ] **Step 7: Commit**

```bash
git add cognitive-runtime/ pom.xml
git commit -m "feat(cognitive-runtime): create module with CognitiveCapability SPI

New module between cognitive-index and cognition. Owns the composable
avatar runtime: CognitiveCapability SPI and CognitiveAvatarContext.

Refs #1219

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 4: CognitiveAvatar composition root + BriefingCapability + CognitiveAvatarProducer

**Files:**
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/CognitiveAvatar.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/BriefingCapability.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/BriefingPromptSection.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/CognitiveAvatarProducer.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/ProfileDescriptorViewSource.java`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/CognitiveAvatarTest.java`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/BriefingCapabilityTest.java`

**Interfaces:**
- Consumes: `CognitiveCapability` (Task 3), `CognitivePromptSource` (Task 1), `BriefingConfig` (Task 2)
- Produces: `CognitiveAvatar`, `BriefingCapability`, `CognitiveAvatarProducer`, `ProfileDescriptorViewSource`

- [ ] **Step 1: Write failing test for BriefingCapability**

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognitive.index.BriefingConfig;
import io.casehub.neocortex.cognition.prompt.BlockTag;
import io.casehub.neocortex.cognition.prompt.CognitionRenderContext;
import io.casehub.neocortex.cognition.prompt.SectionTier;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class BriefingCapabilityTest {

    @Test
    void rendersThreeLayerBriefing() {
        var config = new BriefingConfig("You are stoic.", "Draw on memories.", "Think stoically.");
        var capability = new BriefingCapability(config);
        var sections = capability.promptSections();
        assertEquals(1, sections.size());

        var ctx = new CognitionRenderContext("agent", "tenant", null);
        var content = sections.getFirst().render(ctx);
        assertTrue(content.contains("You are stoic."));
        assertTrue(content.contains("Draw on memories."));
        assertTrue(content.contains("Think stoically."));
    }

    @Test
    void blockTagIsPersonality() {
        var config = new BriefingConfig("identity", null, null);
        var capability = new BriefingCapability(config);
        assertEquals(BlockTag.PERSONALITY, capability.promptSections().getFirst().blockTag());
    }

    @Test
    void sectionTierIsCore() {
        var config = new BriefingConfig("identity", null, null);
        var capability = new BriefingCapability(config);
        assertEquals(SectionTier.CORE, capability.promptSections().getFirst().sectionTier());
    }

    @Test
    void skipsNullLayers() {
        var config = new BriefingConfig("You are stoic.", null, "Think stoically.");
        var capability = new BriefingCapability(config);
        var ctx = new CognitionRenderContext("agent", "tenant", null);
        var content = capability.promptSections().getFirst().render(ctx);
        assertTrue(content.contains("You are stoic."));
        assertFalse(content.contains("null"));
        assertTrue(content.contains("Think stoically."));
    }

    @Test
    void nameIsBriefing() {
        var config = new BriefingConfig("id", null, null);
        assertEquals("briefing", new BriefingCapability(config).name());
    }
}
```

- [ ] **Step 2: Write failing test for CognitiveAvatar**

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognitive.index.BriefingConfig;
import io.casehub.neocortex.cognitive.index.CognitiveDefaults;
import io.casehub.neocortex.cognition.prompt.CognitionRenderContext;
import io.casehub.neocortex.cognition.prompt.CognitivePromptSource;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class CognitiveAvatarTest {

    @Test
    void implementsCognitivePromptSource() {
        var profile = CognitiveDefaults.empty("test");
        var avatar = new CognitiveAvatar(profile, List.of());
        assertInstanceOf(CognitivePromptSource.class, avatar);
    }

    @Test
    void composesCapabilityRenderers() {
        var config = new BriefingConfig("You are a test.", null, "Think as a test.");
        var profile = CognitiveDefaults.empty("test").withBriefing(config);
        var capability = new BriefingCapability(config);
        var avatar = new CognitiveAvatar(profile, List.of(capability));

        var sections = avatar.promptSections();
        assertFalse(sections.isEmpty());

        var ctx = new CognitionRenderContext("test", "tenant", null);
        var content = sections.getFirst().render(ctx);
        assertTrue(content.contains("You are a test."));
    }

    @Test
    void skipsInactiveCapabilities() {
        var inactive = new CognitiveCapability() {
            @Override public String name() { return "inactive"; }
            @Override public List<io.casehub.neocortex.cognition.prompt.CognitionPromptRenderer> promptSections() {
                return List.of();
            }
            @Override public boolean isActive() { return false; }
        };
        var profile = CognitiveDefaults.empty("test");
        var avatar = new CognitiveAvatar(profile, List.of(inactive));
        assertTrue(avatar.promptSections().isEmpty());
    }

    @Test
    void capabilityLookupByType() {
        var config = new BriefingConfig("id", null, null);
        var briefing = new BriefingCapability(config);
        var profile = CognitiveDefaults.empty("test");
        var avatar = new CognitiveAvatar(profile, List.of(briefing));

        assertTrue(avatar.capability(BriefingCapability.class).isPresent());
        assertFalse(avatar.capability(GoalCapability.class).isPresent());
    }

    @Test
    void contributeBlocksProducesPromptBlocks() {
        var config = new BriefingConfig("You are a test.", null, null);
        var profile = CognitiveDefaults.empty("test").withBriefing(config);
        var avatar = new CognitiveAvatar(profile, List.of(new BriefingCapability(config)));

        var ctx = new CognitionRenderContext("test", "tenant", null);
        var blocks = avatar.contributeBlocks(ctx);
        assertEquals(1, blocks.size());
        assertEquals("PERSONALITY", blocks.getFirst().name());
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-runtime -DfailIfNoTests=false`
Expected: Compilation failure — classes don't exist yet

- [ ] **Step 4: Implement BriefingPromptSection**

Create `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/BriefingPromptSection.java`:

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognitive.index.BriefingConfig;
import io.casehub.neocortex.cognition.prompt.BlockTag;
import io.casehub.neocortex.cognition.prompt.CognitionPromptRenderer;
import io.casehub.neocortex.cognition.prompt.CognitionRenderContext;
import io.casehub.neocortex.cognition.prompt.SectionTier;
import org.jspecify.annotations.Nullable;

public class BriefingPromptSection implements CognitionPromptRenderer {

    private final BriefingConfig briefing;

    public BriefingPromptSection(BriefingConfig briefing) {
        this.briefing = briefing;
    }

    @Override
    public @Nullable String render(CognitionRenderContext ctx) {
        if (briefing == null) return null;
        var sb = new StringBuilder();
        if (briefing.identity() != null) sb.append(briefing.identity()).append("\n\n");
        if (briefing.grounding() != null) sb.append(briefing.grounding()).append("\n\n");
        if (briefing.echo() != null) sb.append(briefing.echo());
        var result = sb.toString().strip();
        return result.isEmpty() ? null : result;
    }

    @Override
    public BlockTag blockTag() { return BlockTag.PERSONALITY; }

    @Override
    public @Nullable SectionTier sectionTier() { return SectionTier.CORE; }
}
```

- [ ] **Step 5: Implement BriefingCapability**

Create `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/BriefingCapability.java`:

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognitive.index.BriefingConfig;
import io.casehub.neocortex.cognition.prompt.CognitionPromptRenderer;
import java.util.List;

public class BriefingCapability implements CognitiveCapability {

    private final BriefingConfig config;

    public BriefingCapability(BriefingConfig config) {
        this.config = config;
    }

    @Override
    public String name() { return "briefing"; }

    @Override
    public List<CognitionPromptRenderer> promptSections() {
        return List.of(new BriefingPromptSection(config));
    }
}
```

- [ ] **Step 6: Implement CognitiveAvatar**

Create `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/CognitiveAvatar.java`:

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognitive.index.CognitiveDefaults;
import io.casehub.neocortex.cognition.prompt.CognitionPromptRenderer;
import io.casehub.neocortex.cognition.prompt.CognitivePromptSource;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;

public class CognitiveAvatar implements CognitivePromptSource {

    private final CognitiveDefaults profile;
    private final List<CognitiveCapability> capabilities;

    public CognitiveAvatar(CognitiveDefaults profile,
                           List<CognitiveCapability> capabilities) {
        this.profile = profile;
        this.capabilities = List.copyOf(capabilities);
    }

    @Override
    public void initialize(String agentId, String tenantId) {
        var context = new CognitiveAvatarContext(agentId, tenantId, profile);
        capabilities.forEach(c -> c.initialize(context));
    }

    @Override
    public List<CognitionPromptRenderer> promptSections() {
        return capabilities.stream()
            .filter(CognitiveCapability::isActive)
            .flatMap(c -> c.promptSections().stream())
            .sorted(Comparator.comparingInt(r ->
                r.blockTag() != null ? r.blockTag().sortOrdinal() : 999))
            .toList();
    }

    public <T extends CognitiveCapability> Optional<T> capability(Class<T> type) {
        return capabilities.stream()
            .filter(type::isInstance)
            .map(type::cast)
            .findFirst();
    }

    public CognitiveDefaults profile() { return profile; }
}
```

- [ ] **Step 7: Implement CognitiveAvatarProducer**

Create `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/CognitiveAvatarProducer.java`:

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import io.casehub.neocortex.cognitive.index.CognitiveProfilesReloaded;
import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.cognitive.index.CognitiveProfile;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import java.util.ArrayList;
import java.util.concurrent.ConcurrentHashMap;

@ApplicationScoped
public class CognitiveAvatarProducer {

    @Inject CognitiveDefaultsRegistry registry;
    @Inject Instance<MindMapStore> mindMapStore;
    @Inject Instance<CaseMemoryStore> memoryStore;
    @Inject Instance<CognitiveProfile> cognitiveProfile;

    private final ConcurrentHashMap<String, CognitiveAvatar> cache =
        new ConcurrentHashMap<>();

    public CognitiveAvatar create(String agentId, String tenantId) {
        var key = tenantId + ":" + agentId;
        return cache.computeIfAbsent(key,
            k -> buildAndInitAvatar(agentId, tenantId));
    }

    void onProfileReload(@Observes CognitiveProfilesReloaded event) {
        cache.clear();
    }

    private CognitiveAvatar buildAndInitAvatar(
            String agentId, String tenantId) {
        var profile = registry.forAgentOrDefaults(agentId);
        var capabilities = new ArrayList<CognitiveCapability>();

        if (profile.briefing() != null) {
            capabilities.add(new BriefingCapability(profile.briefing()));
        }
        if (mindMapStore.isResolvable()) {
            capabilities.add(new GoalCapability(mindMapStore.get()));
            capabilities.add(new TemporalCapability(mindMapStore.get()));
        }
        if (memoryStore.isResolvable()) {
            capabilities.add(new MemoryCapability(memoryStore.get()));
        }
        if (cognitiveProfile.isResolvable()) {
            capabilities.add(
                new EntityKnowledgeCapability(cognitiveProfile.get()));
        }

        capabilities.add(new DispositionCapability(profile));

        var avatar = new CognitiveAvatar(profile, capabilities);
        avatar.initialize(agentId, tenantId);
        return avatar;
    }
}
```

Note: `GoalCapability`, `TemporalCapability`, `MemoryCapability`, `EntityKnowledgeCapability`, `DispositionCapability` are created in Batch 3. For now this compiles only if those classes exist — create stubs if needed, or defer `CognitiveAvatarProducer` to after Batch 3.

- [ ] **Step 8: Implement ProfileDescriptorViewSource**

Create `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/ProfileDescriptorViewSource.java`:

```java
package io.casehub.neocortex.cognitive.runtime;

import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import io.casehub.neocortex.cognitive.index.DescriptorView;
import io.casehub.neocortex.cognitive.index.DescriptorViewSource;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.DefaultBean;
import jakarta.inject.Inject;
import java.util.List;
import java.util.Optional;

@DefaultBean
@ApplicationScoped
public class ProfileDescriptorViewSource implements DescriptorViewSource {

    private final CognitiveDefaultsRegistry registry;

    @Inject
    public ProfileDescriptorViewSource(CognitiveDefaultsRegistry registry) {
        this.registry = registry;
    }

    @Override
    public Optional<DescriptorView> find(String tenantId, String agentId) {
        return registry.forAgent(agentId)
            .filter(p -> p.tenantId() == null
                      || p.tenantId().equals(tenantId))
            .map(d -> d.descriptor());
    }

    @Override
    public List<String> agentIds(String tenantId) {
        return registry.allProfiles().stream()
            .filter(p -> p.tenantId() == null
                      || p.tenantId().equals(tenantId))
            .map(d -> d.agentId())
            .toList();
    }
}
```

- [ ] **Step 9: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-runtime`
Expected: All tests pass

- [ ] **Step 10: Commit**

```bash
git add cognitive-runtime/src/
git commit -m "feat(cognitive-runtime): CognitiveAvatar, BriefingCapability, producer

Composition root implementing CognitivePromptSource. BriefingCapability
renders three-layer echo. CognitiveAvatarProducer with tenant-keyed
caching and profile hot-reload. ProfileDescriptorViewSource @DefaultBean.

Refs #1219

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 3: Remaining capabilities + persona profiles

After this batch: All 6 capabilities implemented and tested. Two pre-built persona YAML profiles. Full build passes.

### Task 5: GoalCapability + TemporalCapability

**Files:**
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/GoalCapability.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/GoalPromptSection.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/TemporalCapability.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/TemporalPromptSection.java`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/GoalCapabilityTest.java`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/TemporalCapabilityTest.java`

**Interfaces:**
- Consumes: `CognitiveCapability` SPI (Task 3), `MindMapStore` (mindmap-api), `TemporalFocus` (cognitive-index)
- Produces: `GoalCapability`, `TemporalCapability`

- [ ] **Step 1: Write failing tests for GoalCapability**

Test that GoalCapability queries GOAL subgraph from MindMapStore, renders active goals sorted by priority property, degrades gracefully when MindMapStore has no GOAL nodes.

- [ ] **Step 2: Write failing tests for TemporalCapability**

Test that TemporalCapability feeds MindMap temporal entries to `TemporalFocus.focus()` and renders the resulting `AttentionItem` list. Test graceful degradation when no temporal entries exist.

- [ ] **Step 3: Implement GoalCapability**

Query `MindMapStore.nodesIn(tenantId, SubgraphTypes.GOAL)`, filter for active goals (not superseded, not abandoned), sort by `priority` property, render as prompt section with `BlockTag.GOALS` and `SectionTier.CONTEXTUAL`.

- [ ] **Step 4: Implement TemporalCapability**

Build `TemporalEntry` list from MindMap nodes with temporal validity, call `TemporalFocus.focus()` with `TemporalFocusConfig` from profile, render top 5 `AttentionItem` entries. `BlockTag.TEMPORAL`, `SectionTier.CONTEXTUAL`.

- [ ] **Step 5: Run tests, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-runtime`

- [ ] **Step 6: Commit**

### Task 6: MemoryCapability + EntityKnowledgeCapability + DispositionCapability

**Files:**
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/MemoryCapability.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/MemoryPromptSection.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/EntityKnowledgeCapability.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/DispositionCapability.java`
- Create: `cognitive-runtime/src/main/java/io/casehub/neocortex/cognitive/runtime/DispositionPromptSection.java`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/MemoryCapabilityTest.java`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/EntityKnowledgeCapabilityTest.java`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/DispositionCapabilityTest.java`

**Interfaces:**
- Consumes: `CognitiveCapability` SPI (Task 3), `CaseMemoryStore` (memory-api), `CognitiveProfile` (cognitive-index), `CognitiveDerivationEngine` (cognitive-index)
- Produces: `MemoryCapability`, `EntityKnowledgeCapability`, `DispositionCapability`

- [ ] **Step 1: Write failing tests for all three capabilities**

MemoryCapability: queries recent memories for the agent/tenant, renders as context. EntityKnowledgeCapability: delegates to CognitiveProfile.resolve(), renders EntityKnowledge. DispositionCapability: renders disposition-derived config summary.

- [ ] **Step 2: Implement all three**

MemoryCapability: `BlockTag.MEMORY`, `SectionTier.SUPPLEMENTARY`. EntityKnowledgeCapability: `BlockTag.BELIEFS`, `SectionTier.CONTEXTUAL`. DispositionCapability: `BlockTag.BEHAVIORAL`, `SectionTier.CORE`.

- [ ] **Step 3: Run tests, verify pass**

- [ ] **Step 4: Commit**

### Task 7: Persona YAML profiles + full integration test

**Files:**
- Create: `cognitive-runtime/src/main/resources/cognitive-profiles/stoic-mentor.yaml`
- Create: `cognitive-runtime/src/main/resources/cognitive-profiles/bold-strategist.yaml`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/PersonaProfileTest.java`
- Test: `cognitive-runtime/src/test/java/io/casehub/neocortex/cognitive/runtime/CognitiveAvatarIntegrationTest.java`

**Interfaces:**
- Consumes: All capabilities (Tasks 4-6), `CognitiveDefaultsRegistry` (cognitive-index)
- Produces: Pre-built persona profiles, integration test proving end-to-end composition

- [ ] **Step 1: Create stoic-mentor.yaml**

Disposition: high ruleFollowing, low riskAppetite, high autonomy, moderate socialOrient, collaborative conflictMode. Three-layer briefing with evocative echo (not prescriptive). Behavioral defaults for curiosity and temporal focus.

- [ ] **Step 2: Create bold-strategist.yaml**

Disposition: low ruleFollowing, high riskAppetite, high autonomy, high socialOrient, competitive conflictMode. Contrasting three-layer briefing. Different behavioral defaults.

- [ ] **Step 3: Write PersonaProfileTest**

Verify both profiles load via `CognitiveDefaultsRegistry`, have correct agentIds, disposition axes, and briefing config present.

- [ ] **Step 4: Write CognitiveAvatarIntegrationTest**

End-to-end: load stoic-mentor profile → create `CognitiveAvatar` with `BriefingCapability` → call `contributeBlocks()` → verify `PromptBlock` list contains briefing content with correct tier and salience.

- [ ] **Step 5: Run full module test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-runtime`

- [ ] **Step 6: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: All modules compile and all tests pass

- [ ] **Step 7: Commit**

```bash
git add cognitive-runtime/src/
git commit -m "feat(cognitive-runtime): persona profiles and integration tests

Stoic mentor + bold strategist YAML profiles with three-layer evocative
briefing. Full integration test: profile → avatar → prompt blocks.

Refs #1219

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## Batch 4: Documentation + CLAUDE.md

After this batch: Consumer guide updated, CLAUDE.md updated, ARC42STORIES updated. Issue closable.

### Task 8: Documentation updates

**Files:**
- Modify: `docs/guides/consumer-guide.md` — add cognitive-runtime module table
- Modify: `CLAUDE.md` — add cognitive-runtime to module structure and maven coordinates
- Modify: ARC42STORIES.MD (workspace) — add cognitive-runtime building block

- [ ] **Step 1: Update consumer-guide.md**

Add `cognitive-runtime` module to the Knowledge Model table with artifactId `casehub-neocortex-cognitive-runtime` and description of what consumers get (CognitiveAvatar, CognitiveCapability SPI, BriefingCapability, pre-built personas).

- [ ] **Step 2: Update CLAUDE.md**

Add `cognitive-runtime` to the module structure diagram and maven coordinates table. Add root Java package `io.casehub.neocortex.cognitive.runtime`.

- [ ] **Step 3: Update ARC42STORIES.MD**

Add cognitive-runtime building block entry, layer entry, CognitiveCapability SPI concept, briefed avatar lifecycle journey.

- [ ] **Step 4: Commit**

```bash
git add docs/ CLAUDE.md
git commit -m "docs: add cognitive-runtime to consumer guide and CLAUDE.md

Refs #1219

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

---

## References

- [2026-11-24-composable-cognitive-avatars-design.md] — design spec this plan implements
- [decisions.md] — 10 design decisions with rationale
- `cognition-api/src/main/java/.../CognitiveLifecycle.java:11` — interface to extract from
- `cognitive-index/src/main/java/.../CognitiveDefaults.java:35` — record to extend with BriefingConfig
- `cognitive-index/src/main/java/.../CognitiveDefaultsRegistry.java` — profile loading infrastructure
- `cognitive-index/src/main/java/.../DescriptorViewSource.java` — SPI for ProfileDescriptorViewSource
- `cognitive-index/src/main/java/.../TemporalFocus.java` — temporal awareness utility
- `cognitive-index/src/test/resources/cognitive-profiles/alice.yaml` — existing profile format reference
- `neocortex/docs/research/era1-character-taxonomy-research.md` — echo validation research
- casehubio/neocortex#1219 — focal issue
