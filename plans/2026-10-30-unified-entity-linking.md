# Unified Entity Linking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #721 — unified entity linking
**Issue group:** #721

**Goal:** Bridge the text corpus and knowledge graph via standoff annotations so every text mention — including pronouns — is grounded to a canonical MindMap entity.

**Architecture:** A dedicated annotation index (EntityAnnotationIndex SPI) stores `(text span → entity node ID)` mappings. Annotations are produced by extending MindMapExtractor's LLM output with surface form mentions, then computing offsets programmatically. CDI events handle lifecycle (memory erasure, node merge). Cognitive subsystems query the index for entity-aware salience, reflection, belief revision, and Theory of Mind.

**Tech Stack:** Java 21, Quarkus CDI, SQLite + HikariCP + Flyway, existing MindMapExtractor/AgentProvider LLM integration

## Global Constraints

- annotation-api is Tier 1 pure Java — zero CDI, no mindmap-api dependency
- Entity node IDs are opaque `String` identifiers throughout annotation-api
- All SPI methods require `tenantId` — tenant isolation is unconditional
- Character offsets are Java char indexes (UTF-16 code units) — `String.substring(start, end)` recovers mention text
- Annotations are immutable — correction is delete + re-create
- GroupId: `io.casehub`, parent: `casehub-neocortex-parent`, version: `0.4-SNAPSHOT`
- Root package: `io.casehub.neocortex.annotation`
- Use `ide_insert_member` for new methods, `ide_replace_member` for modifying existing ones
- Use `ide_refactor_rename` / `ide_move_file` for refactoring — never bash mv/cp on source files

---

## Batch 1: Core API + In-Memory Implementation

After this batch: annotation-api defines all value types + SPI, annotation-inmem provides the in-memory implementation, annotation-testing provides the contract test base, and AnnotationSpanResolver + AnchorAnnotationParser are tested standalone utilities.

### Task 1: annotation-api module — value types, SPI, and utilities

**Files:**
- Create: `annotation-api/pom.xml`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/EntityAnnotation.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/EntityAnnotationIndex.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/MentionInput.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/ResolvedSpan.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/ParsedAnchor.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/AnnotationMethod.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/EntityAnnotated.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/AnnotationSpanResolver.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/AnchorAnnotationParser.java`
- Create: `annotation-api/src/main/java/io/casehub/neocortex/annotation/AnchorParseResult.java`
- Test: `annotation-api/src/test/java/io/casehub/neocortex/annotation/AnnotationSpanResolverTest.java`
- Test: `annotation-api/src/test/java/io/casehub/neocortex/annotation/AnchorAnnotationParserTest.java`
- Modify: `pom.xml` (add `<module>annotation-api</module>`)

**Interfaces:**
- Produces: `EntityAnnotation` record, `EntityAnnotationIndex` SPI, `MentionInput` record, `ResolvedSpan` record, `ParsedAnchor` record, `AnnotationMethod` constants, `EntityAnnotated` CDI event record, `AnnotationSpanResolver.resolve(String, List<MentionInput>)`, `AnchorAnnotationParser.parse(String)`, `AnchorParseResult` record

- [ ] **Step 1: Create annotation-api/pom.xml**

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
  <artifactId>casehub-neocortex-annotation-api</artifactId>
  <name>CaseHub Neocortex - Annotation API</name>
  <description>Entity annotation SPI and value types. Tier 1 pure Java, zero deps.</description>
  <dependencies>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
</project>
```

Add `<module>annotation-api</module>` to the parent pom.xml after the `fusion-api` module entry.

- [ ] **Step 2: Write AnnotationSpanResolver failing tests**

```java
package io.casehub.neocortex.annotation;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.assertThat;

class AnnotationSpanResolverTest {

    private final AnnotationSpanResolver resolver = new AnnotationSpanResolver();

    @Test
    void resolveSingleNamedMention() {
        String text = "James examined the guest book.";
        var mentions = List.of(new MentionInput("James Pond", "James", 0));
        List<ResolvedSpan> spans = resolver.resolve(text, mentions);
        assertThat(spans).hasSize(1);
        assertThat(spans.get(0).startOffset()).isEqualTo(0);
        assertThat(spans.get(0).endOffset()).isEqualTo(5);
        assertThat(spans.get(0).surfaceForm()).isEqualTo("James");
        assertThat(text.substring(spans.get(0).startOffset(), spans.get(0).endOffset())).isEqualTo("James");
    }

    @Test
    void resolveMultipleMentionsWithPronouns() {
        String text = "James examined the book. He opened it carefully.";
        var mentions = List.of(
            new MentionInput("James Pond", "James", 0),
            new MentionInput("Guest Book", "book", 1),
            new MentionInput("James Pond", "He", 2),
            new MentionInput("Guest Book", "it", 3));
        List<ResolvedSpan> spans = resolver.resolve(text, mentions);
        assertThat(spans).hasSize(4);
        assertThat(spans.get(0).entityName()).isEqualTo("James Pond");
        assertThat(spans.get(2).entityName()).isEqualTo("James Pond");
        assertThat(spans.get(2).surfaceForm()).isEqualTo("He");
    }

    @Test
    void sortsByMentionIndexBeforeScanning() {
        String text = "James gave Clara the key.";
        // LLM grouped by entity, not text order
        var mentions = List.of(
            new MentionInput("James", "James", 0),
            new MentionInput("Key", "key", 2),
            new MentionInput("Clara", "Clara", 1));
        List<ResolvedSpan> spans = resolver.resolve(text, mentions);
        assertThat(spans).hasSize(3);
        assertThat(spans.get(0).surfaceForm()).isEqualTo("James");
        assertThat(spans.get(1).surfaceForm()).isEqualTo("Clara");
        assertThat(spans.get(2).surfaceForm()).isEqualTo("key");
    }

    @Test
    void skipsMissingSurfaceForm() {
        String text = "James walked away.";
        var mentions = List.of(
            new MentionInput("James", "James", 0),
            new MentionInput("Clara", "Clara", 1)); // not in text
        List<ResolvedSpan> spans = resolver.resolve(text, mentions);
        assertThat(spans).hasSize(1);
        assertThat(spans.get(0).entityName()).isEqualTo("James");
    }

    @Test
    void disambiguatesRepeatedSurfaceForms() {
        String text = "He saw it. He took it.";
        var mentions = List.of(
            new MentionInput("James", "He", 0),
            new MentionInput("Key", "it", 1),
            new MentionInput("James", "He", 2),
            new MentionInput("Key", "it", 3));
        List<ResolvedSpan> spans = resolver.resolve(text, mentions);
        assertThat(spans).hasSize(4);
        assertThat(spans.get(0).startOffset()).isEqualTo(0); // first "He"
        assertThat(spans.get(2).startOffset()).isEqualTo(11); // second "He"
    }

    @Test
    void emptyMentionsReturnsEmpty() {
        List<ResolvedSpan> spans = resolver.resolve("Some text.", List.of());
        assertThat(spans).isEmpty();
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl annotation-api -Dtest=AnnotationSpanResolverTest`
Expected: FAIL — classes not defined

- [ ] **Step 4: Implement value types and AnnotationSpanResolver**

Create all value types:

```java
// EntityAnnotation.java
package io.casehub.neocortex.annotation;

import java.time.Instant;
import java.util.Objects;

public record EntityAnnotation(
    String annotationId,
    String tenantId,
    String sourceType,
    String sourceId,
    String entityNodeId,
    int startOffset,
    int endOffset,
    String mentionText,
    Double confidence,
    String method,
    String ownerSubjectId,
    Instant createdAt
) {
    public EntityAnnotation {
        Objects.requireNonNull(annotationId, "annotationId");
        Objects.requireNonNull(tenantId, "tenantId");
        Objects.requireNonNull(sourceType, "sourceType");
        Objects.requireNonNull(sourceId, "sourceId");
        Objects.requireNonNull(entityNodeId, "entityNodeId");
        Objects.requireNonNull(mentionText, "mentionText");
        Objects.requireNonNull(method, "method");
        Objects.requireNonNull(createdAt, "createdAt");
        if (startOffset < 0) throw new IllegalArgumentException("startOffset must be >= 0");
        if (endOffset <= startOffset) throw new IllegalArgumentException("endOffset must be > startOffset");
    }
}

// MentionInput.java
package io.casehub.neocortex.annotation;

public record MentionInput(String entityName, String surfaceForm, int mentionIndex) {}

// ResolvedSpan.java
package io.casehub.neocortex.annotation;

public record ResolvedSpan(String entityName, String surfaceForm, int startOffset, int endOffset, int mentionIndex) {}

// ParsedAnchor.java
package io.casehub.neocortex.annotation;

public record ParsedAnchor(String alias, String surfaceForm, int startOffset, int endOffset) {}

// AnchorParseResult.java
package io.casehub.neocortex.annotation;

import java.util.List;

public record AnchorParseResult(String cleanText, List<ParsedAnchor> anchors) {}

// AnnotationMethod.java
package io.casehub.neocortex.annotation;

public final class AnnotationMethod {
    public static final String MANUAL = "manual";
    public static final String LLM_EXTRACTION = "llm-extraction";
    public static final String YAML_ANCHOR = "yaml-anchor";
    private AnnotationMethod() {}
}

// EntityAnnotated.java
package io.casehub.neocortex.annotation;

import java.util.List;

public record EntityAnnotated(List<EntityAnnotation> annotations, String tenantId) {}

// EntityAnnotationIndex.java
package io.casehub.neocortex.annotation;

import java.util.List;
import java.util.Map;
import java.util.Set;

public interface EntityAnnotationIndex {
    String addAnnotation(EntityAnnotation annotation);
    List<String> addAnnotations(List<EntityAnnotation> annotations);
    void removeAnnotation(String annotationId, String tenantId);
    void removeBySource(String sourceType, String sourceId, String tenantId);
    void removeByOwnerSubject(String sourceType, String ownerSubjectId, String tenantId);
    int repointEntity(String fromEntityNodeId, String toEntityNodeId, String tenantId);
    List<EntityAnnotation> findByEntity(String entityNodeId, String tenantId);
    List<EntityAnnotation> findByEntityPair(String entityNodeId1, String entityNodeId2, String tenantId);
    List<EntityAnnotation> findByEntities(Set<String> entityNodeIds, String tenantId);
    List<EntityAnnotation> findBySource(String sourceType, String sourceId, String tenantId);
    Set<String> distinctEntitiesInSource(String sourceType, String sourceId, String tenantId);
    Map<String, Long> entityMentionCounts(String tenantId);
}

// AnnotationSpanResolver.java
package io.casehub.neocortex.annotation;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public class AnnotationSpanResolver {

    public List<ResolvedSpan> resolve(String text, List<MentionInput> mentions) {
        if (mentions.isEmpty()) return List.of();
        List<MentionInput> sorted = new ArrayList<>(mentions);
        sorted.sort(Comparator.comparingInt(MentionInput::mentionIndex));
        List<ResolvedSpan> result = new ArrayList<>();
        int scanPos = 0;
        for (MentionInput m : sorted) {
            int idx = text.indexOf(m.surfaceForm(), scanPos);
            if (idx < 0) continue;
            result.add(new ResolvedSpan(m.entityName(), m.surfaceForm(), idx, idx + m.surfaceForm().length(), m.mentionIndex()));
            scanPos = idx + m.surfaceForm().length();
        }
        return List.copyOf(result);
    }
}
```

- [ ] **Step 5: Run AnnotationSpanResolver tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl annotation-api -Dtest=AnnotationSpanResolverTest`
Expected: PASS

- [ ] **Step 6: Write AnchorAnnotationParser failing tests**

```java
package io.casehub.neocortex.annotation;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class AnchorAnnotationParserTest {

    private final AnchorAnnotationParser parser = new AnchorAnnotationParser();

    @Test
    void parseSingleAnchor() {
        AnchorParseResult result = parser.parse("James[pp] is protective.");
        assertThat(result.cleanText()).isEqualTo("James is protective.");
        assertThat(result.anchors()).hasSize(1);
        assertThat(result.anchors().get(0).alias()).isEqualTo("pp");
        assertThat(result.anchors().get(0).surfaceForm()).isEqualTo("James");
        assertThat(result.anchors().get(0).startOffset()).isEqualTo(0);
        assertThat(result.anchors().get(0).endOffset()).isEqualTo(5);
        assertThat(result.cleanText().substring(0, 5)).isEqualTo("James");
    }

    @Test
    void parseMultipleAnchors() {
        AnchorParseResult result = parser.parse("He[pp] examined it[obj-7] carefully.");
        assertThat(result.cleanText()).isEqualTo("He examined it carefully.");
        assertThat(result.anchors()).hasSize(2);
        assertThat(result.anchors().get(0).alias()).isEqualTo("pp");
        assertThat(result.anchors().get(0).surfaceForm()).isEqualTo("He");
        assertThat(result.anchors().get(1).alias()).isEqualTo("obj-7");
        assertThat(result.anchors().get(1).surfaceForm()).isEqualTo("it");
    }

    @Test
    void multiWordAnchor() {
        AnchorParseResult result = parser.parse("the guest book[obj-7] was old.");
        assertThat(result.cleanText()).isEqualTo("the guest book was old.");
        assertThat(result.anchors()).hasSize(1);
        assertThat(result.anchors().get(0).surfaceForm()).isEqualTo("book");
        assertThat(result.anchors().get(0).alias()).isEqualTo("obj-7");
    }

    @Test
    void noAnchors() {
        AnchorParseResult result = parser.parse("Plain text with no anchors.");
        assertThat(result.cleanText()).isEqualTo("Plain text with no anchors.");
        assertThat(result.anchors()).isEmpty();
    }

    @Test
    void emptyText() {
        AnchorParseResult result = parser.parse("");
        assertThat(result.cleanText()).isEmpty();
        assertThat(result.anchors()).isEmpty();
    }

    @Test
    void offsetsAreCorrectInCleanText() {
        AnchorParseResult result = parser.parse("James[pp] gave Clara[clara] the key[key1].");
        assertThat(result.cleanText()).isEqualTo("James gave Clara the key.");
        for (ParsedAnchor a : result.anchors()) {
            assertThat(result.cleanText().substring(a.startOffset(), a.endOffset()))
                .isEqualTo(a.surfaceForm());
        }
    }
}
```

- [ ] **Step 7: Implement AnchorAnnotationParser**

```java
package io.casehub.neocortex.annotation;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class AnchorAnnotationParser {

    private static final Pattern ANCHOR_PATTERN = Pattern.compile("(\\S+)\\[([a-zA-Z0-9_-]+)]");

    public AnchorParseResult parse(String text) {
        if (text == null || text.isEmpty()) return new AnchorParseResult("", List.of());

        List<ParsedAnchor> anchors = new ArrayList<>();
        Matcher matcher = ANCHOR_PATTERN.matcher(text);
        StringBuilder clean = new StringBuilder();
        int lastEnd = 0;
        int offsetAdjustment = 0;

        while (matcher.find()) {
            clean.append(text, lastEnd, matcher.start());
            String surfaceForm = matcher.group(1);
            String alias = matcher.group(2);
            int cleanStart = clean.length();
            clean.append(surfaceForm);
            int cleanEnd = clean.length();
            anchors.add(new ParsedAnchor(alias, surfaceForm, cleanStart, cleanEnd));
            lastEnd = matcher.end();
        }
        clean.append(text, lastEnd, text.length());
        return new AnchorParseResult(clean.toString(), List.copyOf(anchors));
    }
}
```

- [ ] **Step 8: Run AnchorAnnotationParser tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl annotation-api -Dtest=AnchorAnnotationParserTest`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add annotation-api/ pom.xml
git commit -m "feat(#721): add annotation-api module — SPI, value types, span resolver, anchor parser

Refs #721"
```

### Task 2: annotation-testing + annotation-inmem — contract tests and in-memory implementation

**Files:**
- Create: `annotation-testing/pom.xml`
- Create: `annotation-testing/src/main/java/io/casehub/neocortex/annotation/testing/EntityAnnotationIndexContractTest.java`
- Create: `annotation-inmem/pom.xml`
- Create: `annotation-inmem/src/main/java/io/casehub/neocortex/annotation/inmem/InMemoryEntityAnnotationIndex.java`
- Create: `annotation-inmem/src/test/java/io/casehub/neocortex/annotation/inmem/InMemoryEntityAnnotationIndexTest.java`
- Modify: `pom.xml` (add `<module>annotation-testing</module>`, `<module>annotation-inmem</module>`)

**Interfaces:**
- Consumes: `EntityAnnotationIndex` SPI, `EntityAnnotation` record from Task 1
- Produces: `EntityAnnotationIndexContractTest` abstract base (for SQLite store in Batch 2), `InMemoryEntityAnnotationIndex` (for all test contexts)

- [ ] **Step 1: Write contract test base**

Create `annotation-testing/pom.xml` with compile-scope JUnit + assertj + annotation-api dependency (follows mindmap-testing pattern).

```java
package io.casehub.neocortex.annotation.testing;

import io.casehub.neocortex.annotation.AnnotationMethod;
import io.casehub.neocortex.annotation.EntityAnnotation;
import io.casehub.neocortex.annotation.EntityAnnotationIndex;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;

public abstract class EntityAnnotationIndexContractTest {

    protected abstract EntityAnnotationIndex createIndex();

    private EntityAnnotationIndex index;
    private static final String TENANT = "t1";
    private static final String OTHER_TENANT = "t2";

    @BeforeEach
    void setUp() { index = createIndex(); }

    private EntityAnnotation annotation(String entityNodeId, String sourceType, String sourceId,
                                         int start, int end, String mention) {
        return new EntityAnnotation(UUID.randomUUID().toString(), TENANT, sourceType, sourceId,
            entityNodeId, start, end, mention, 0.9, AnnotationMethod.LLM_EXTRACTION, null, Instant.now());
    }

    private EntityAnnotation annotationWithOwner(String entityNodeId, String sourceId,
                                                  String ownerSubjectId) {
        return new EntityAnnotation(UUID.randomUUID().toString(), TENANT, "memory", sourceId,
            entityNodeId, 0, 5, "James", 1.0, AnnotationMethod.LLM_EXTRACTION, ownerSubjectId, Instant.now());
    }

    @Test
    void addAndFindByEntity() {
        EntityAnnotation a = annotation("node-1", "memory", "mem-1", 0, 5, "James");
        index.addAnnotation(a);
        List<EntityAnnotation> found = index.findByEntity("node-1", TENANT);
        assertThat(found).hasSize(1);
        assertThat(found.get(0).mentionText()).isEqualTo("James");
    }

    @Test
    void addBatchAndFindByEntity() {
        var a1 = annotation("node-1", "memory", "mem-1", 0, 5, "James");
        var a2 = annotation("node-1", "memory", "mem-2", 0, 5, "He");
        index.addAnnotations(List.of(a1, a2));
        assertThat(index.findByEntity("node-1", TENANT)).hasSize(2);
    }

    @Test
    void removeAnnotation() {
        EntityAnnotation a = annotation("node-1", "memory", "mem-1", 0, 5, "James");
        String id = index.addAnnotation(a);
        index.removeAnnotation(id, TENANT);
        assertThat(index.findByEntity("node-1", TENANT)).isEmpty();
    }

    @Test
    void removeBySource() {
        index.addAnnotation(annotation("node-1", "memory", "mem-1", 0, 5, "James"));
        index.addAnnotation(annotation("node-2", "memory", "mem-1", 10, 15, "Clara"));
        index.addAnnotation(annotation("node-1", "memory", "mem-2", 0, 5, "James"));
        index.removeBySource("memory", "mem-1", TENANT);
        assertThat(index.findByEntity("node-1", TENANT)).hasSize(1);
        assertThat(index.findByEntity("node-2", TENANT)).isEmpty();
    }

    @Test
    void removeByOwnerSubject() {
        index.addAnnotation(annotationWithOwner("node-1", "mem-1", "alice"));
        index.addAnnotation(annotationWithOwner("node-2", "mem-2", "alice"));
        index.addAnnotation(annotationWithOwner("node-1", "mem-3", "bob"));
        index.removeByOwnerSubject("memory", "alice", TENANT);
        assertThat(index.findByEntity("node-1", TENANT)).hasSize(1); // bob's
        assertThat(index.findByEntity("node-2", TENANT)).isEmpty();
    }

    @Test
    void findByEntityPairSameDocument() {
        index.addAnnotation(annotation("node-1", "memory", "mem-1", 0, 5, "James"));
        index.addAnnotation(annotation("node-2", "memory", "mem-1", 10, 15, "Clara"));
        index.addAnnotation(annotation("node-1", "memory", "mem-2", 0, 5, "James"));
        List<EntityAnnotation> found = index.findByEntityPair("node-1", "node-2", TENANT);
        assertThat(found).hasSize(2); // both annotations from mem-1
        assertThat(found).allMatch(a -> a.sourceId().equals("mem-1"));
    }

    @Test
    void findByEntities() {
        index.addAnnotation(annotation("node-1", "memory", "mem-1", 0, 5, "James"));
        index.addAnnotation(annotation("node-2", "memory", "mem-2", 0, 5, "Clara"));
        index.addAnnotation(annotation("node-3", "memory", "mem-3", 0, 5, "Key"));
        List<EntityAnnotation> found = index.findByEntities(Set.of("node-1", "node-2"), TENANT);
        assertThat(found).hasSize(2);
    }

    @Test
    void findBySource() {
        index.addAnnotation(annotation("node-1", "memory", "mem-1", 0, 5, "James"));
        index.addAnnotation(annotation("node-2", "memory", "mem-1", 10, 15, "Clara"));
        List<EntityAnnotation> found = index.findBySource("memory", "mem-1", TENANT);
        assertThat(found).hasSize(2);
    }

    @Test
    void distinctEntitiesInSource() {
        index.addAnnotation(annotation("node-1", "memory", "mem-1", 0, 5, "James"));
        index.addAnnotation(annotation("node-1", "memory", "mem-1", 20, 22, "He"));
        index.addAnnotation(annotation("node-2", "memory", "mem-1", 10, 15, "Clara"));
        Set<String> entities = index.distinctEntitiesInSource("memory", "mem-1", TENANT);
        assertThat(entities).containsExactlyInAnyOrder("node-1", "node-2");
    }

    @Test
    void entityMentionCounts() {
        index.addAnnotation(annotation("node-1", "memory", "mem-1", 0, 5, "James"));
        index.addAnnotation(annotation("node-1", "memory", "mem-2", 0, 5, "He"));
        index.addAnnotation(annotation("node-2", "memory", "mem-1", 10, 15, "Clara"));
        Map<String, Long> counts = index.entityMentionCounts(TENANT);
        assertThat(counts).containsEntry("node-1", 2L);
        assertThat(counts).containsEntry("node-2", 1L);
    }

    @Test
    void repointEntity() {
        index.addAnnotation(annotation("old-node", "memory", "mem-1", 0, 5, "James"));
        index.addAnnotation(annotation("old-node", "memory", "mem-2", 0, 5, "He"));
        int repointed = index.repointEntity("old-node", "new-node", TENANT);
        assertThat(repointed).isEqualTo(2);
        assertThat(index.findByEntity("old-node", TENANT)).isEmpty();
        assertThat(index.findByEntity("new-node", TENANT)).hasSize(2);
    }

    @Test
    void repointEntityDeduplicates() {
        index.addAnnotation(annotation("node-a", "memory", "mem-1", 0, 5, "James"));
        index.addAnnotation(annotation("node-b", "memory", "mem-1", 0, 5, "James"));
        index.repointEntity("node-b", "node-a", TENANT);
        List<EntityAnnotation> found = index.findByEntity("node-a", TENANT);
        assertThat(found).hasSize(1);
    }

    @Test
    void repointNoMatchIsNoOp() {
        int repointed = index.repointEntity("nonexistent", "target", TENANT);
        assertThat(repointed).isEqualTo(0);
    }

    @Test
    void tenantIsolation() {
        index.addAnnotation(annotation("node-1", "memory", "mem-1", 0, 5, "James"));
        assertThat(index.findByEntity("node-1", OTHER_TENANT)).isEmpty();
    }

    @Test
    void nullableConfidence() {
        var a = new EntityAnnotation(UUID.randomUUID().toString(), TENANT, "memory", "mem-1",
            "node-1", 0, 5, "James", null, AnnotationMethod.MANUAL, null, Instant.now());
        index.addAnnotation(a);
        List<EntityAnnotation> found = index.findByEntity("node-1", TENANT);
        assertThat(found.get(0).confidence()).isNull();
    }

    @Test
    void nullableOwnerSubjectId() {
        var a = annotation("node-1", "memory", "mem-1", 0, 5, "James");
        index.addAnnotation(a);
        index.removeByOwnerSubject("memory", "nonexistent", TENANT);
        assertThat(index.findByEntity("node-1", TENANT)).hasSize(1);
    }
}
```

- [ ] **Step 2: Write InMemoryEntityAnnotationIndex**

```java
package io.casehub.neocortex.annotation.inmem;

import io.casehub.neocortex.annotation.EntityAnnotation;
import io.casehub.neocortex.annotation.EntityAnnotationIndex;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.stream.Collectors;

public class InMemoryEntityAnnotationIndex implements EntityAnnotationIndex {

    private final Map<String, EntityAnnotation> store = new ConcurrentHashMap<>();

    public void clearAll() { store.clear(); }

    @Override
    public String addAnnotation(EntityAnnotation annotation) {
        store.put(annotation.annotationId(), annotation);
        return annotation.annotationId();
    }

    @Override
    public List<String> addAnnotations(List<EntityAnnotation> annotations) {
        List<String> ids = new ArrayList<>();
        for (EntityAnnotation a : annotations) { ids.add(addAnnotation(a)); }
        return ids;
    }

    @Override
    public void removeAnnotation(String annotationId, String tenantId) {
        store.values().removeIf(a -> a.annotationId().equals(annotationId) && a.tenantId().equals(tenantId));
    }

    @Override
    public void removeBySource(String sourceType, String sourceId, String tenantId) {
        store.values().removeIf(a -> a.tenantId().equals(tenantId)
            && a.sourceType().equals(sourceType) && a.sourceId().equals(sourceId));
    }

    @Override
    public void removeByOwnerSubject(String sourceType, String ownerSubjectId, String tenantId) {
        store.values().removeIf(a -> a.tenantId().equals(tenantId)
            && a.sourceType().equals(sourceType)
            && ownerSubjectId.equals(a.ownerSubjectId()));
    }

    @Override
    public int repointEntity(String fromEntityNodeId, String toEntityNodeId, String tenantId) {
        List<EntityAnnotation> toRepoint = store.values().stream()
            .filter(a -> a.tenantId().equals(tenantId) && a.entityNodeId().equals(fromEntityNodeId))
            .toList();
        int count = toRepoint.size();
        for (EntityAnnotation a : toRepoint) {
            store.remove(a.annotationId());
            boolean duplicate = store.values().stream().anyMatch(existing ->
                existing.tenantId().equals(tenantId) && existing.entityNodeId().equals(toEntityNodeId)
                && existing.sourceType().equals(a.sourceType()) && existing.sourceId().equals(a.sourceId())
                && existing.startOffset() == a.startOffset() && existing.endOffset() == a.endOffset());
            if (!duplicate) {
                var repointed = new EntityAnnotation(a.annotationId(), a.tenantId(), a.sourceType(),
                    a.sourceId(), toEntityNodeId, a.startOffset(), a.endOffset(), a.mentionText(),
                    a.confidence(), a.method(), a.ownerSubjectId(), a.createdAt());
                store.put(repointed.annotationId(), repointed);
            }
        }
        return count;
    }

    @Override
    public List<EntityAnnotation> findByEntity(String entityNodeId, String tenantId) {
        return store.values().stream()
            .filter(a -> a.tenantId().equals(tenantId) && a.entityNodeId().equals(entityNodeId))
            .toList();
    }

    @Override
    public List<EntityAnnotation> findByEntityPair(String entityNodeId1, String entityNodeId2, String tenantId) {
        Map<String, Set<String>> sourceToEntities = new HashMap<>();
        for (EntityAnnotation a : store.values()) {
            if (!a.tenantId().equals(tenantId)) continue;
            if (a.entityNodeId().equals(entityNodeId1) || a.entityNodeId().equals(entityNodeId2)) {
                sourceToEntities.computeIfAbsent(a.sourceType() + ":" + a.sourceId(), k -> new HashSet<>())
                    .add(a.entityNodeId());
            }
        }
        Set<String> bothPresent = sourceToEntities.entrySet().stream()
            .filter(e -> e.getValue().contains(entityNodeId1) && e.getValue().contains(entityNodeId2))
            .map(Map.Entry::getKey)
            .collect(Collectors.toSet());
        return store.values().stream()
            .filter(a -> a.tenantId().equals(tenantId)
                && bothPresent.contains(a.sourceType() + ":" + a.sourceId())
                && (a.entityNodeId().equals(entityNodeId1) || a.entityNodeId().equals(entityNodeId2)))
            .toList();
    }

    @Override
    public List<EntityAnnotation> findByEntities(Set<String> entityNodeIds, String tenantId) {
        return store.values().stream()
            .filter(a -> a.tenantId().equals(tenantId) && entityNodeIds.contains(a.entityNodeId()))
            .toList();
    }

    @Override
    public List<EntityAnnotation> findBySource(String sourceType, String sourceId, String tenantId) {
        return store.values().stream()
            .filter(a -> a.tenantId().equals(tenantId)
                && a.sourceType().equals(sourceType) && a.sourceId().equals(sourceId))
            .toList();
    }

    @Override
    public Set<String> distinctEntitiesInSource(String sourceType, String sourceId, String tenantId) {
        return store.values().stream()
            .filter(a -> a.tenantId().equals(tenantId)
                && a.sourceType().equals(sourceType) && a.sourceId().equals(sourceId))
            .map(EntityAnnotation::entityNodeId)
            .collect(Collectors.toSet());
    }

    @Override
    public Map<String, Long> entityMentionCounts(String tenantId) {
        return store.values().stream()
            .filter(a -> a.tenantId().equals(tenantId))
            .collect(Collectors.groupingBy(EntityAnnotation::entityNodeId, Collectors.counting()));
    }
}
```

- [ ] **Step 3: Create InMemoryEntityAnnotationIndexTest extending contract test**

```java
package io.casehub.neocortex.annotation.inmem;

import io.casehub.neocortex.annotation.EntityAnnotationIndex;
import io.casehub.neocortex.annotation.testing.EntityAnnotationIndexContractTest;

class InMemoryEntityAnnotationIndexTest extends EntityAnnotationIndexContractTest {
    private final InMemoryEntityAnnotationIndex index = new InMemoryEntityAnnotationIndex();

    @Override
    protected EntityAnnotationIndex createIndex() {
        index.clearAll();
        return index;
    }
}
```

- [ ] **Step 4: Run all contract tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl annotation-inmem`
Expected: PASS — all 15 contract tests

- [ ] **Step 5: Commit**

```bash
git add annotation-testing/ annotation-inmem/ pom.xml
git commit -m "feat(#721): add annotation-testing contract tests + annotation-inmem in-memory implementation

Refs #721"
```

## Batch 2: SQLite Persistence

After this batch: SqliteEntityAnnotationIndex provides production-ready persistence with all contract tests passing.

### Task 3: annotation-sqlite — SQLite store with Flyway

**Files:**
- Create: `annotation-sqlite/pom.xml`
- Create: `annotation-sqlite/src/main/java/io/casehub/neocortex/annotation/sqlite/SqliteEntityAnnotationIndex.java`
- Create: `annotation-sqlite/src/main/resources/db/annotation/migration/V1__annotation_schema.sql`
- Test: `annotation-sqlite/src/test/java/io/casehub/neocortex/annotation/sqlite/SqliteEntityAnnotationIndexTest.java`
- Modify: `pom.xml` (add `<module>annotation-sqlite</module>`)

**Interfaces:**
- Consumes: `EntityAnnotationIndex` SPI, `EntityAnnotation` record, `EntityAnnotationIndexContractTest` from Tasks 1-2
- Produces: `SqliteEntityAnnotationIndex` (production store)

- [ ] **Step 1: Create Flyway migration**

```sql
-- V1__annotation_schema.sql
CREATE TABLE entity_annotations (
    annotation_id  TEXT NOT NULL,
    tenant_id      TEXT NOT NULL,
    source_type    TEXT NOT NULL,
    source_id      TEXT NOT NULL,
    entity_node_id TEXT NOT NULL,
    start_offset   INTEGER NOT NULL,
    end_offset     INTEGER NOT NULL,
    mention_text   TEXT NOT NULL,
    confidence     REAL,
    method         TEXT NOT NULL,
    owner_subject_id TEXT,
    created_at     TEXT NOT NULL,
    PRIMARY KEY (annotation_id)
);

CREATE INDEX idx_ann_entity ON entity_annotations(tenant_id, entity_node_id);
CREATE INDEX idx_ann_source ON entity_annotations(tenant_id, source_type, source_id);
CREATE INDEX idx_ann_owner  ON entity_annotations(tenant_id, source_type, owner_subject_id);
```

- [ ] **Step 2: Create pom.xml with sqlite-support, annotation-api, annotation-testing deps**

Dependencies: `casehub-neocortex-sqlite-support`, `casehub-neocortex-annotation-api`, `casehub-neocortex-annotation-testing` (test scope), JUnit, assertj (test scope).

- [ ] **Step 3: Implement SqliteEntityAnnotationIndex**

Follow `SqliteMindMapStore` pattern: constructor takes `DataSource` from `SqliteDataSourceFactory.create()`. JDBC operations with PreparedStatement. `repointEntity` uses UPDATE + DELETE for dedup (same source+offsets+entity after repoint).

- [ ] **Step 4: Create SqliteEntityAnnotationIndexTest extending contract test**

```java
package io.casehub.neocortex.annotation.sqlite;

import io.casehub.neocortex.annotation.EntityAnnotationIndex;
import io.casehub.neocortex.annotation.testing.EntityAnnotationIndexContractTest;
import io.casehub.neocortex.sqlite.SqliteDataSourceFactory;
import org.junit.jupiter.api.BeforeEach;
import javax.sql.DataSource;

class SqliteEntityAnnotationIndexTest extends EntityAnnotationIndexContractTest {
    private SqliteEntityAnnotationIndex index;

    @BeforeEach
    void init() {
        DataSource ds = SqliteDataSourceFactory.create(":memory:", "annotation");
        index = new SqliteEntityAnnotationIndex(ds);
    }

    @Override
    protected EntityAnnotationIndex createIndex() { return index; }
}
```

- [ ] **Step 5: Run contract tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl annotation-sqlite`
Expected: PASS — all 15 contract tests

- [ ] **Step 6: Commit**

```bash
git add annotation-sqlite/ pom.xml
git commit -m "feat(#721): add annotation-sqlite — SQLite persistence with Flyway

Refs #721"
```

## Batch 3: Extraction Pipeline Integration

After this batch: MindMapExtractor produces entity mentions with surface forms. ExtractionRequestedObserver writes annotations to the annotation index after extraction.

### Task 4: Extend MindMapExtractor — ParsedMention + prompt extension

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ParsedMention.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ParsedExtraction.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java:44-76` (SYSTEM_PROMPT)
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionJsonParser.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ExtractionJsonParserTest.java`

**Interfaces:**
- Consumes: Existing `ParsedExtraction`, `ParsedEntity`, `ExtractionJsonParser`
- Produces: `ParsedMention(entityName, surfaceForm, mentionIndex)`, extended `ParsedExtraction` with `mentions` field

- [ ] **Step 1: Write failing test for ParsedMention parsing**

Add test to ExtractionJsonParserTest for JSON with mentions array:

```java
@Test
void parsesWithMentions() {
    String json = """
        {"entities": [{"name": "James", "type": "PERSON", "properties": {}, "confidence": "STATED"}],
         "relationships": [], "contradictions": [],
         "mentions": [{"entity": "James", "surface": "James", "index": 0},
                      {"entity": "James", "surface": "He", "index": 1}]}
        """;
    ParsedExtraction result = ExtractionJsonParser.parse(json);
    assertThat(result.mentions()).hasSize(2);
    assertThat(result.mentions().get(0).entityName()).isEqualTo("James");
    assertThat(result.mentions().get(0).surfaceForm()).isEqualTo("James");
    assertThat(result.mentions().get(1).surfaceForm()).isEqualTo("He");
}

@Test
void parsesWithoutMentions() {
    String json = """
        {"entities": [{"name": "James", "type": "PERSON", "properties": {}, "confidence": "STATED"}],
         "relationships": [], "contradictions": []}
        """;
    ParsedExtraction result = ExtractionJsonParser.parse(json);
    assertThat(result.mentions()).isEmpty();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExtractionJsonParserTest#parsesWithMentions`
Expected: FAIL

- [ ] **Step 3: Implement ParsedMention + extend ParsedExtraction + update ExtractionJsonParser**

Create `ParsedMention.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

public record ParsedMention(String entityName, String surfaceForm, int mentionIndex) {}
```

Update `ParsedExtraction` to add `List<ParsedMention> mentions` field with backward-compatible constructor that defaults to `List.of()`.

Update `ExtractionJsonParser` to parse the `mentions` array from LLM JSON (graceful — missing `mentions` key returns empty list).

- [ ] **Step 4: Extend SYSTEM_PROMPT in MindMapExtractor**

Add to the JSON output format:
```
"mentions": [
  {"entity": "canonical entity name", "surface": "exact text as it appears", "index": 0}
]
```

Add to Rules:
```
- For each entity, list every mention in the text (including pronouns and descriptions). 
  Report the exact surface form and the canonical entity name. Number mentions in text order starting from 0.
```

- [ ] **Step 5: Run all mindmap-intelligence tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/
git commit -m "feat(#721): extend MindMapExtractor with entity mention spans

ParsedMention record, extended ParsedExtraction, updated LLM prompt
to report surface forms for all entity mentions including pronouns.

Refs #721"
```

### Task 5: Wire ExtractionRequestedObserver to produce annotations

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserver.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequested.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridge.java`
- Modify: `mindmap-intelligence/pom.xml` (add annotation-api dependency)
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserverAnnotationTest.java`

**Interfaces:**
- Consumes: `ParsedMention` from Task 4, `AnnotationSpanResolver`, `MentionInput`, `EntityAnnotation`, `EntityAnnotationIndex` from Task 1, `ExtractionResult.entities()` for name→nodeId mapping
- Produces: Annotations written to `EntityAnnotationIndex` after every extraction

- [ ] **Step 1: Write failing test for annotation production**

Test that when `ExtractionRequestedObserver` processes an extraction, annotations are written to an `InMemoryEntityAnnotationIndex`.

- [ ] **Step 2: Add `batchId` and `ownerSubjectId` to `ExtractionRequested`**

Extend the record with two new fields (nullable, backward-compatible defaults).

- [ ] **Step 3: Update `ConversationBridge.process()` to generate `batchId` and pass `ownerSubjectId`**

Generate `UUID.randomUUID().toString()` for batchId. Pass subject ID from caller context if available.

- [ ] **Step 4: Inject `Instance<EntityAnnotationIndex>` into `ExtractionRequestedObserver`**

After `apply()`, map `ParsedMention → MentionInput`, resolve spans, reconstruct name→nodeId from `result.entities()`, write annotations. Graceful degradation when annotation index not on classpath (`Instance.isResolvable()`).

- [ ] **Step 5: Run all mindmap-intelligence tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/
git commit -m "feat(#721): wire extraction pipeline to produce entity annotations

ExtractionRequestedObserver writes standoff annotations to
EntityAnnotationIndex after each extraction pass. batchId and
ownerSubjectId added to ExtractionRequested for source identification.

Refs #721"
```

## Batch 4: CDI Lifecycle Observers

After this batch: annotation CDI module handles memory erasure (cleanup) and node merge (repoint) automatically.

### Task 6: annotation module — CDI lifecycle observers

**Files:**
- Create: `annotation/pom.xml`
- Create: `annotation/src/main/java/io/casehub/neocortex/annotation/cdi/MemoryEntityErasedObserver.java`
- Create: `annotation/src/main/java/io/casehub/neocortex/annotation/cdi/MergeRepointObserver.java`
- Test: `annotation/src/test/java/io/casehub/neocortex/annotation/cdi/MemoryEntityErasedObserverTest.java`
- Test: `annotation/src/test/java/io/casehub/neocortex/annotation/cdi/MergeRepointObserverTest.java`
- Modify: `pom.xml` (add `<module>annotation</module>`)

**Interfaces:**
- Consumes: `EntityAnnotationIndex` SPI, `MemoryEntityErased` sealed interface from memory-api, `GraphMutationRecorded` + `GraphMutation.NodesMerged` from cognitive-observability
- Produces: CDI observers that maintain annotation index consistency on memory erasure and node merge

- [ ] **Step 1: Write MemoryEntityErasedObserver test**

Unit test (no CDI container): construct observer with InMemoryEntityAnnotationIndex, call the observer method directly with a MemoryEntityErased.ByEntity event, verify annotations deleted by ownerSubjectId.

- [ ] **Step 2: Implement MemoryEntityErasedObserver**

```java
package io.casehub.neocortex.annotation.cdi;

import io.casehub.neocortex.annotation.EntityAnnotationIndex;
import io.casehub.neocortex.memory.MemoryEntityErased;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

@ApplicationScoped
public class MemoryEntityErasedObserver {
    private final EntityAnnotationIndex index;

    @Inject
    public MemoryEntityErasedObserver(EntityAnnotationIndex index) { this.index = index; }

    void onErased(@Observes MemoryEntityErased event) {
        switch (event) {
            case MemoryEntityErased.ByEntity e ->
                index.removeByOwnerSubject("memory", e.subject().id(), e.tenantId());
            case MemoryEntityErased.ByRequest e ->
                index.removeByOwnerSubject("memory", e.subject().id(), e.tenantId());
            case MemoryEntityErased.CrossTenant e ->
                e.tenantIds().forEach(tid -> index.removeByOwnerSubject("memory", e.subject().id(), tid));
        }
    }
}
```

- [ ] **Step 3: Write MergeRepointObserver test**

Unit test: construct observer with InMemoryEntityAnnotationIndex, call with GraphMutationRecorded wrapping NodesMerged, verify annotations repointed and deduplicated.

- [ ] **Step 4: Implement MergeRepointObserver**

```java
package io.casehub.neocortex.annotation.cdi;

import io.casehub.neocortex.annotation.EntityAnnotationIndex;
import io.casehub.neocortex.cognitive.observability.GraphMutation;
import io.casehub.neocortex.cognitive.observability.GraphMutationRecorded;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

@ApplicationScoped
public class MergeRepointObserver {
    private final EntityAnnotationIndex index;

    @Inject
    public MergeRepointObserver(EntityAnnotationIndex index) { this.index = index; }

    void onMutation(@Observes GraphMutationRecorded event) {
        if (event.mutation() instanceof GraphMutation.NodesMerged merged) {
            index.repointEntity(merged.absorbedId(), merged.survivorId(), event.tenantId());
        }
    }
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl annotation`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add annotation/ pom.xml
git commit -m "feat(#721): add annotation CDI module — memory erasure + merge repoint observers

MemoryEntityErasedObserver deletes annotations by ownerSubjectId on
memory erasure. MergeRepointObserver repoints annotations on node merge
via GraphMutationRecorded CDI event.

Refs #721"
```

## Batch 5: Biography Anchor Integration

After this batch: biography YAML with bracket syntax is preprocessed — brackets stripped before handlers, annotations written to the index.

### Task 7: BiographyProfilePreprocessor — anchor syntax integration

**Files:**
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/BiographyProfilePreprocessor.java`
- Create: `annotation/src/main/java/io/casehub/neocortex/annotation/cdi/AnchorBiographyPreprocessor.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/BiographyImportRunner.java`
- Modify: `annotation/pom.xml` (add memory-seeding dependency)
- Test: `annotation/src/test/java/io/casehub/neocortex/annotation/cdi/AnchorBiographyPreprocessorTest.java`

**Interfaces:**
- Consumes: `AnchorAnnotationParser` from Task 1, `EntityAnnotationIndex` from Task 1, `BiographyProfile` from memory-seeding, `MindMapStore.resolveNode()` for alias→nodeId
- Produces: `BiographyProfilePreprocessor` SPI, `AnchorBiographyPreprocessor` implementation, sanitized profiles with clean text

- [ ] **Step 1: Write BiographyProfilePreprocessor SPI in memory-seeding**

```java
package io.casehub.neocortex.memory.seeding;

public interface BiographyProfilePreprocessor {
    BiographyProfile preprocess(BiographyProfile profile, String agentId, String tenantId);
}
```

- [ ] **Step 2: Modify BiographyImportRunner to use optional preprocessor**

Add `Instance<BiographyProfilePreprocessor>` injection. Before handler dispatch, if resolvable, call `preprocess()`.

- [ ] **Step 3: Write AnchorBiographyPreprocessor test**

Test that bracket syntax is stripped from profile text fields and annotations are written to InMemoryEntityAnnotationIndex.

- [ ] **Step 4: Implement AnchorBiographyPreprocessor**

Uses `AnchorAnnotationParser` to strip brackets and produce clean text. Resolves aliases via entity registry in YAML. Resolves canonical names to MindMap node IDs via `MindMapStore.resolveNode()`. Writes annotations to `EntityAnnotationIndex`.

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl annotation,memory-seeding`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add memory-seeding/ annotation/
git commit -m "feat(#721): biography anchor syntax preprocessing

BiographyProfilePreprocessor SPI strips bracket syntax from biography
YAML before handlers see it. AnchorBiographyPreprocessor writes
standoff annotations to EntityAnnotationIndex.

Refs #721"
```

## Batch 6: Cognitive Integration + Retrieval Modulation

After this batch: entity-aware salience, reflection, belief revision, Theory of Mind, and retrieval modulation are all operational.

### Task 8: EntityAwareSalienceStrategy + EntityOverlapModulationFactor

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/EntityAwareSalienceStrategy.java`
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/EntityOverlapModulationFactor.java`
- Modify: `cognition/pom.xml` (add annotation-api dependency)
- Modify: `cognitive-index/pom.xml` (add annotation-api dependency)
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/EntityAwareSalienceStrategyTest.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/EntityOverlapModulationFactorTest.java`

**Interfaces:**
- Consumes: `EntityAnnotationIndex` from Task 1, `SalienceStrategy` SPI, `ModulationFactor<Memory>`, `ModulationProfile<Memory>`
- Produces: `EntityAwareSalienceStrategy` (one-sided entity matching), `EntityOverlapModulationFactor` (retrieval boost)

- [ ] **Step 1: Write EntityAwareSalienceStrategy test**

Test one-sided matching: concern memory has annotations, observation is raw text. Verify entity name found in observation text boosts salience for that concern.

- [ ] **Step 2: Implement EntityAwareSalienceStrategy**

Decorator on `SalienceStrategy`. Collects entity node IDs from concern memory annotations, resolves entity names from annotation `mentionText`, searches observation text for those names, boosts salience for matching concerns. Falls back to delegate when no concern annotations exist.

- [ ] **Step 3: Write EntityOverlapModulationFactor test**

Test that memories sharing entity annotations with context get score boost.

- [ ] **Step 4: Implement EntityOverlapModulationFactor**

Constructor-injected `EntityAnnotationIndex` + `tenantId` + `Set<String> contextEntityNodeIds`. Calls `distinctEntitiesInSource("memory", memoryId, tenantId)`, computes overlap, returns `1.0 + overlap * 0.15`.

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EntityAwareSalienceStrategyTest && JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=EntityOverlapModulationFactorTest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognition/ cognitive-index/
git commit -m "feat(#721): entity-aware salience strategy + retrieval modulation

EntityAwareSalienceStrategy provides one-sided entity matching for
salience scoring. EntityOverlapModulationFactor boosts retrieval
scores for memories sharing entity annotations with query context.

Refs #721"
```

### Task 9: Entity-scoped reflection, belief revision, and Theory of Mind

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/LlmReflectionSynthesizer.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/BeliefRevisionPhase.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/MentalModelOrchestrator.java`
- Test: entity-scoped tests for each integration point

**Interfaces:**
- Consumes: `EntityAnnotationIndex.findByEntity()`, `findByEntityPair()` from Task 1
- Produces: Entity-scoped reflection, entity-grounded belief provenance, entity-scoped mental models

- [ ] **Step 1: Write test for entity-scoped reflection**

Test that `LlmReflectionSynthesizer` can retrieve all memories mentioning a specific entity via `findByEntity`, gathering complete interaction history including pronoun references.

- [ ] **Step 2: Integrate EntityAnnotationIndex into LlmReflectionSynthesizer**

Add optional `Instance<EntityAnnotationIndex>` injection. When available and a target entity is specified, use `findByEntity` to gather source memories rather than text search alone.

- [ ] **Step 3: Write test for entity-grounded belief revision**

Test that `BeliefRevisionPhase` uses entity annotations to detect conflicts between memories about the same entity.

- [ ] **Step 4: Integrate EntityAnnotationIndex into BeliefRevisionPhase**

Use entity annotations to ground belief provenance — when two memories conflict about the same entity, report precise span provenance.

- [ ] **Step 5: Write test for entity-scoped mental models**

Test that `MentalModelOrchestrator` builds complete models from all entity-linked mentions.

- [ ] **Step 6: Integrate EntityAnnotationIndex into MentalModelOrchestrator**

Use `findByEntity` to gather ALL mentions of the target entity (including pronouns, definite descriptions) for complete mental model construction. Use `findByEntityPair` for relationship-scoped queries.

- [ ] **Step 7: Run all cognition tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add cognition/
git commit -m "feat(#721): entity-scoped reflection, belief revision, and Theory of Mind

LlmReflectionSynthesizer, BeliefRevisionPhase, and
MentalModelOrchestrator now use EntityAnnotationIndex for
entity-grounded cognitive operations.

Refs #721"
```

## References

- [2026-10-30-unified-entity-linking-design.md] — design spec this plan implements
- [decisions.md] — 18 captured design decisions with review
- [MindMapExtractor.java:39] — existing LLM entity extraction
- [ConversationBridge.java:23] — existing text segmentation
- [ExtractionRequestedObserver] — async extraction pipeline
- [ParsedExtraction.java:1] — existing extraction output
- [ExtractionJsonParser] — LLM response JSON parsing
- [MergeResult.java:1] — merge semantics
- [MemoryEntityErased] — memory lifecycle events
- [GraphMutationRecorded] — graph mutation events
- [GoalRelevanceModulationFactor] — retrieval modulation pattern
- [ConcernBasedSalienceStrategy] — existing salience implementation
- [SqliteMindMapStore.java] — SQLite store pattern
- [fusion-api/pom.xml] — Tier 1 module pom pattern
- [mindmap-testing/pom.xml] — contract test module pattern
- GitHub #721 — unified entity linking issue
- GitHub #727 — extract GraphMutation types to Tier 1 (follow-up)
- GitHub #728 — ARC42STORIES entries (follow-up)
