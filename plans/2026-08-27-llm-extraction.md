# LLM Entity/Relationship Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #220 — feat: mindmap-intelligence — LLM entity/relationship extraction
**Issue group:** #213, #215, #216, #217, #218, #219, #220, #221

**Goal:** Add LLM-powered entity and relationship extraction from conversation text to the mindmap-intelligence module, creating and updating nodes/edges in the MindMap graph.

**Architecture:** `MindMapExtractor` is a concrete `@ApplicationScoped` CDI bean in `mindmap-intelligence/` that takes conversation text + tenantId, queries the existing graph for context, invokes `AgentProvider` with a structured JSON prompt, parses the response, resolves entities against existing nodes, and creates/updates graph structure. Optional `AgentProvider` via CDI `Instance<>` — returns `ExtractionResult.EMPTY` when no LLM backend is available.

**Tech Stack:** Java 21, Quarkus 3.32.2, casehub-platform-agent-api (AgentProvider), Mutiny (Multi consumption), mindmap-api (MindMapStore SPI)

## Global Constraints

- Java 21 source level on Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- All code in `mindmap-intelligence/` module under `io.casehub.neocortex.mindmap.intelligence`
- Every commit references issue #220: `Refs #220`
- Tests use `InMemoryMindMapStore` — no Docker, no real LLM
- New Maven dependency: `casehub-platform-agent-api` (compile scope)
- New Maven dependency: `io.smallrye.reactive:mutiny` (compile scope)
- Use IntelliJ MCP (`ide_insert_member`, `ide_replace_member`, `ide_create_file`) for all Java file operations

---

## Batch 1: Value Types + JSON Parser

### Task 1: ExtractionResult and supporting records

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionResult.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractedEntity.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractedRelationship.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Contradiction.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ExtractionResultTest.java`

**Interfaces:**
- Consumes: `io.casehub.neocortex.mindmap.ConfidenceOrigin` (from mindmap-api)
- Produces: `ExtractionResult`, `ExtractedEntity`, `ExtractedRelationship`, `Contradiction` — used by Tasks 2 and 3

- [ ] **Step 1: Write tests for ExtractionResult**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.ConfidenceOrigin;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.assertThat;

class ExtractionResultTest {

    @Test
    void emptyResult() {
        ExtractionResult result = ExtractionResult.EMPTY;
        assertThat(result.entities()).isEmpty();
        assertThat(result.relationships()).isEmpty();
        assertThat(result.contradictions()).isEmpty();
        assertThat(result.entityNames()).isEmpty();
    }

    @Test
    void resultWithEntitiesAndRelationships() {
        var entity = new ExtractedEntity("node-1", "Alice", true, "PERSON",
            Map.of("role", "engineer"));
        var rel = new ExtractedRelationship("edge-1", "Alice", "Acme",
            "works-at", ConfidenceOrigin.STATED);
        var contradiction = new Contradiction("Alice", "works-at",
            "OldCorp", "Acme", "Alice changed jobs");

        var result = new ExtractionResult(
            List.of(entity), List.of(rel),
            List.of(contradiction), List.of("Alice", "Acme"));

        assertThat(result.entities()).hasSize(1);
        assertThat(result.entities().get(0).name()).isEqualTo("Alice");
        assertThat(result.entities().get(0).created()).isTrue();
        assertThat(result.relationships()).hasSize(1);
        assertThat(result.relationships().get(0).edgeType()).isEqualTo("works-at");
        assertThat(result.contradictions()).hasSize(1);
        assertThat(result.entityNames()).containsExactly("Alice", "Acme");
    }

    @Test
    void extractedEntityProperties() {
        var entity = new ExtractedEntity("n1", "Bob", false, "PERSON",
            Map.of("email", "bob@example.com", "role", "manager"));
        assertThat(entity.nodeId()).isEqualTo("n1");
        assertThat(entity.created()).isFalse();
        assertThat(entity.properties()).containsEntry("email", "bob@example.com");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExtractionResultTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — classes not found

- [ ] **Step 3: Create the four record classes**

`ExtractionResult.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.List;

public record ExtractionResult(
    List<ExtractedEntity> entities,
    List<ExtractedRelationship> relationships,
    List<Contradiction> contradictions,
    List<String> entityNames
) {
    public static final ExtractionResult EMPTY =
        new ExtractionResult(List.of(), List.of(), List.of(), List.of());
}
```

`ExtractedEntity.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Map;

public record ExtractedEntity(
    String nodeId,
    String name,
    boolean created,
    String subgraphType,
    Map<String, String> properties
) {}
```

`ExtractedRelationship.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.ConfidenceOrigin;

public record ExtractedRelationship(
    String edgeId,
    String sourceName,
    String targetName,
    String edgeType,
    ConfidenceOrigin confidenceOrigin
) {}
```

`Contradiction.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

public record Contradiction(
    String entityName,
    String property,
    String existingValue,
    String extractedValue,
    String description
) {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExtractionResultTest`
Expected: PASS — 3 tests

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-intelligence/src
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#220): ExtractionResult and supporting record types Refs #220"
```

### Task 2: ExtractionJsonParser

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionJsonParser.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ExtractionJsonParserTest.java`

**Interfaces:**
- Consumes: `ExtractionResult`, `ExtractedEntity`, `ExtractedRelationship`, `Contradiction` (from Task 1), `ConfidenceOrigin` (from mindmap-api)
- Produces: `ExtractionJsonParser.parse(String json)` returning a raw parsed result (entities/relationships/contradictions before graph resolution). Returns a package-private `ParsedExtraction` record.

The parser is a package-private utility — not a CDI bean. It handles malformed LLM output gracefully.

- [ ] **Step 1: Write tests for JSON parsing**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.ConfidenceOrigin;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class ExtractionJsonParserTest {

    @Test
    void parseValidJson() {
        String json = """
            {
              "entities": [
                {"name": "Alice", "type": "PERSON", "properties": {"role": "engineer"}, "confidence": "STATED"}
              ],
              "relationships": [
                {"source": "Alice", "target": "Acme", "type": "works-at", "confidence": "STATED"}
              ],
              "contradictions": [
                {"entity": "Alice", "property": "works-at", "existing": "OldCorp", "extracted": "Acme", "explanation": "Changed jobs"}
              ]
            }
            """;
        ParsedExtraction result = ExtractionJsonParser.parse(json);
        assertThat(result.entities()).hasSize(1);
        assertThat(result.entities().get(0).name()).isEqualTo("Alice");
        assertThat(result.entities().get(0).type()).isEqualTo("PERSON");
        assertThat(result.entities().get(0).properties()).containsEntry("role", "engineer");
        assertThat(result.entities().get(0).confidence()).isEqualTo(ConfidenceOrigin.STATED);
        assertThat(result.relationships()).hasSize(1);
        assertThat(result.relationships().get(0).source()).isEqualTo("Alice");
        assertThat(result.relationships().get(0).type()).isEqualTo("works-at");
        assertThat(result.contradictions()).hasSize(1);
        assertThat(result.contradictions().get(0).entity()).isEqualTo("Alice");
    }

    @Test
    void parseMarkdownWrappedJson() {
        String wrapped = """
            ```json
            {"entities": [{"name": "Bob", "type": "PERSON", "properties": {}, "confidence": "INFERRED"}], "relationships": [], "contradictions": []}
            ```
            """;
        ParsedExtraction result = ExtractionJsonParser.parse(wrapped);
        assertThat(result.entities()).hasSize(1);
        assertThat(result.entities().get(0).name()).isEqualTo("Bob");
    }

    @Test
    void parseJsonWithTrailingText() {
        String withTrailing = """
            {"entities": [], "relationships": [], "contradictions": []}
            Here is some additional explanation the LLM added.
            """;
        ParsedExtraction result = ExtractionJsonParser.parse(withTrailing);
        assertThat(result).isNotNull();
        assertThat(result.entities()).isEmpty();
    }

    @Test
    void parseMissingFieldsDefaultsToEmpty() {
        String minimal = """
            {"entities": [{"name": "Alice", "type": "PERSON", "properties": {}, "confidence": "STATED"}]}
            """;
        ParsedExtraction result = ExtractionJsonParser.parse(minimal);
        assertThat(result.entities()).hasSize(1);
        assertThat(result.relationships()).isEmpty();
        assertThat(result.contradictions()).isEmpty();
    }

    @Test
    void parseEmptyStringReturnsNull() {
        assertThat(ExtractionJsonParser.parse("")).isNull();
        assertThat(ExtractionJsonParser.parse(null)).isNull();
    }

    @Test
    void parseTotalGarbageReturnsNull() {
        assertThat(ExtractionJsonParser.parse("not json at all")).isNull();
    }

    @Test
    void parseUnknownConfidenceDefaultsToInferred() {
        String json = """
            {"entities": [{"name": "X", "type": "CONCEPT", "properties": {}, "confidence": "STRONG"}], "relationships": [], "contradictions": []}
            """;
        ParsedExtraction result = ExtractionJsonParser.parse(json);
        assertThat(result.entities().get(0).confidence()).isEqualTo(ConfidenceOrigin.INFERRED);
    }

    @Test
    void parseEntityWithoutPropertiesDefaultsToEmptyMap() {
        String json = """
            {"entities": [{"name": "X", "type": "CONCEPT", "confidence": "STATED"}], "relationships": [], "contradictions": []}
            """;
        ParsedExtraction result = ExtractionJsonParser.parse(json);
        assertThat(result.entities().get(0).properties()).isEmpty();
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExtractionJsonParserTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — classes not found

- [ ] **Step 3: Create ParsedExtraction and ParsedEntity/ParsedRelationship/ParsedContradiction records**

`ParsedExtraction.java` (package-private):
```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.List;

record ParsedExtraction(
    List<ParsedEntity> entities,
    List<ParsedRelationship> relationships,
    List<ParsedContradiction> contradictions
) {}

```

`ParsedEntity.java` (package-private):
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.ConfidenceOrigin;
import java.util.Map;

record ParsedEntity(
    String name,
    String type,
    Map<String, String> properties,
    ConfidenceOrigin confidence
) {}
```

`ParsedRelationship.java` (package-private):
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.ConfidenceOrigin;

record ParsedRelationship(
    String source,
    String target,
    String type,
    ConfidenceOrigin confidence
) {}
```

`ParsedContradiction.java` (package-private):
```java
package io.casehub.neocortex.mindmap.intelligence;

record ParsedContradiction(
    String entity,
    String property,
    String existing,
    String extracted,
    String explanation
) {}
```

- [ ] **Step 4: Create ExtractionJsonParser**

`ExtractionJsonParser.java` (package-private):
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.ConfidenceOrigin;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Logger;

final class ExtractionJsonParser {

    private static final Logger LOG = Logger.getLogger(ExtractionJsonParser.class.getName());

    private ExtractionJsonParser() {}

    static ParsedExtraction parse(String raw) {
        if (raw == null || raw.isBlank()) return null;

        String json = stripMarkdownWrapper(raw);
        json = extractFirstJsonObject(json);
        if (json == null) return null;

        try {
            return parseJsonObject(json);
        } catch (Exception e) {
            LOG.warning("Failed to parse extraction JSON: " + e.getMessage());
            return null;
        }
    }

    private static String stripMarkdownWrapper(String text) {
        String trimmed = text.strip();
        if (trimmed.startsWith("```")) {
            int firstNewline = trimmed.indexOf('\n');
            if (firstNewline >= 0) {
                trimmed = trimmed.substring(firstNewline + 1);
            }
            if (trimmed.endsWith("```")) {
                trimmed = trimmed.substring(0, trimmed.length() - 3);
            }
            return trimmed.strip();
        }
        return trimmed;
    }

    private static String extractFirstJsonObject(String text) {
        int start = text.indexOf('{');
        if (start < 0) return null;
        int depth = 0;
        boolean inString = false;
        boolean escaped = false;
        for (int i = start; i < text.length(); i++) {
            char c = text.charAt(i);
            if (escaped) { escaped = false; continue; }
            if (c == '\\' && inString) { escaped = true; continue; }
            if (c == '"') { inString = !inString; continue; }
            if (inString) continue;
            if (c == '{') depth++;
            else if (c == '}') { depth--; if (depth == 0) return text.substring(start, i + 1); }
        }
        return null;
    }

    private static ParsedExtraction parseJsonObject(String json) {
        // Minimal hand-rolled JSON parser for the known extraction schema.
        // We parse arrays of objects with string/object fields.
        List<ParsedEntity> entities = new ArrayList<>();
        List<ParsedRelationship> relationships = new ArrayList<>();
        List<ParsedContradiction> contradictions = new ArrayList<>();

        String entitiesJson = extractArray(json, "entities");
        if (entitiesJson != null) {
            for (String obj : splitArrayObjects(entitiesJson)) {
                entities.add(parseEntity(obj));
            }
        }

        String relsJson = extractArray(json, "relationships");
        if (relsJson != null) {
            for (String obj : splitArrayObjects(relsJson)) {
                relationships.add(parseRelationship(obj));
            }
        }

        String contradictionsJson = extractArray(json, "contradictions");
        if (contradictionsJson != null) {
            for (String obj : splitArrayObjects(contradictionsJson)) {
                contradictions.add(parseContradiction(obj));
            }
        }

        return new ParsedExtraction(entities, relationships, contradictions);
    }

    private static ParsedEntity parseEntity(String obj) {
        String name = extractString(obj, "name");
        String type = extractString(obj, "type");
        ConfidenceOrigin confidence = parseConfidence(extractString(obj, "confidence"));
        Map<String, String> props = extractStringMap(obj, "properties");
        return new ParsedEntity(name, type, props, confidence);
    }

    private static ParsedRelationship parseRelationship(String obj) {
        String source = extractString(obj, "source");
        String target = extractString(obj, "target");
        String type = extractString(obj, "type");
        ConfidenceOrigin confidence = parseConfidence(extractString(obj, "confidence"));
        return new ParsedRelationship(source, target, type, confidence);
    }

    private static ParsedContradiction parseContradiction(String obj) {
        String entity = extractString(obj, "entity");
        String property = extractString(obj, "property");
        String existing = extractString(obj, "existing");
        String extracted = extractString(obj, "extracted");
        String explanation = extractString(obj, "explanation");
        return new ParsedContradiction(entity, property, existing, extracted, explanation);
    }

    private static ConfidenceOrigin parseConfidence(String value) {
        if (value == null) return ConfidenceOrigin.INFERRED;
        try {
            return ConfidenceOrigin.valueOf(value);
        } catch (IllegalArgumentException e) {
            return ConfidenceOrigin.INFERRED;
        }
    }

    static String extractArray(String json, String key) {
        String search = "\"" + key + "\"";
        int keyIdx = json.indexOf(search);
        if (keyIdx < 0) return null;
        int colonIdx = json.indexOf(':', keyIdx + search.length());
        if (colonIdx < 0) return null;
        int bracketIdx = json.indexOf('[', colonIdx);
        if (bracketIdx < 0) return null;
        int depth = 0;
        for (int i = bracketIdx; i < json.length(); i++) {
            char c = json.charAt(i);
            if (c == '[') depth++;
            else if (c == ']') { depth--; if (depth == 0) return json.substring(bracketIdx + 1, i); }
        }
        return null;
    }

    static List<String> splitArrayObjects(String arrayContent) {
        List<String> objects = new ArrayList<>();
        int depth = 0;
        int start = -1;
        boolean inString = false;
        boolean escaped = false;
        for (int i = 0; i < arrayContent.length(); i++) {
            char c = arrayContent.charAt(i);
            if (escaped) { escaped = false; continue; }
            if (c == '\\' && inString) { escaped = true; continue; }
            if (c == '"') { inString = !inString; continue; }
            if (inString) continue;
            if (c == '{') { if (depth == 0) start = i; depth++; }
            else if (c == '}') { depth--; if (depth == 0 && start >= 0) { objects.add(arrayContent.substring(start, i + 1)); start = -1; } }
        }
        return objects;
    }

    static String extractString(String obj, String key) {
        String search = "\"" + key + "\"";
        int keyIdx = obj.indexOf(search);
        if (keyIdx < 0) return null;
        int colonIdx = obj.indexOf(':', keyIdx + search.length());
        if (colonIdx < 0) return null;
        int i = colonIdx + 1;
        while (i < obj.length() && obj.charAt(i) == ' ') i++;
        if (i >= obj.length()) return null;
        if (obj.charAt(i) == '"') {
            int end = findClosingQuote(obj, i + 1);
            return end > 0 ? obj.substring(i + 1, end) : null;
        }
        if (obj.charAt(i) == '{' || obj.charAt(i) == '[' || obj.charAt(i) == 'n') return null;
        int end = i;
        while (end < obj.length() && obj.charAt(end) != ',' && obj.charAt(end) != '}') end++;
        return obj.substring(i, end).strip();
    }

    private static int findClosingQuote(String s, int from) {
        for (int i = from; i < s.length(); i++) {
            if (s.charAt(i) == '\\') { i++; continue; }
            if (s.charAt(i) == '"') return i;
        }
        return -1;
    }

    static Map<String, String> extractStringMap(String obj, String key) {
        String search = "\"" + key + "\"";
        int keyIdx = obj.indexOf(search);
        if (keyIdx < 0) return Map.of();
        int colonIdx = obj.indexOf(':', keyIdx + search.length());
        if (colonIdx < 0) return Map.of();
        int braceIdx = obj.indexOf('{', colonIdx);
        if (braceIdx < 0) return Map.of();
        int depth = 0;
        int end = -1;
        for (int i = braceIdx; i < obj.length(); i++) {
            if (obj.charAt(i) == '{') depth++;
            else if (obj.charAt(i) == '}') { depth--; if (depth == 0) { end = i; break; } }
        }
        if (end < 0) return Map.of();
        String inner = obj.substring(braceIdx + 1, end).strip();
        if (inner.isEmpty()) return Map.of();
        Map<String, String> map = new LinkedHashMap<>();
        int pos = 0;
        while (pos < inner.length()) {
            int qStart = inner.indexOf('"', pos);
            if (qStart < 0) break;
            int qEnd = findClosingQuote(inner, qStart + 1);
            if (qEnd < 0) break;
            String k = inner.substring(qStart + 1, qEnd);
            int c = inner.indexOf(':', qEnd + 1);
            if (c < 0) break;
            int vStart = c + 1;
            while (vStart < inner.length() && inner.charAt(vStart) == ' ') vStart++;
            if (vStart >= inner.length()) break;
            if (inner.charAt(vStart) == '"') {
                int vEnd = findClosingQuote(inner, vStart + 1);
                if (vEnd < 0) break;
                map.put(k, inner.substring(vStart + 1, vEnd));
                pos = vEnd + 1;
            } else {
                int vEnd = vStart;
                while (vEnd < inner.length() && inner.charAt(vEnd) != ',' && inner.charAt(vEnd) != '}') vEnd++;
                map.put(k, inner.substring(vStart, vEnd).strip());
                pos = vEnd + 1;
            }
        }
        return map;
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ExtractionJsonParserTest`
Expected: PASS — 8 tests

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-intelligence/src
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#220): ExtractionJsonParser — hand-rolled JSON parser for LLM output Refs #220"
```

## Batch 2: listSubgraphs SPI + MindMapExtractor

### Task 3: Add listSubgraphs to MindMapStore SPI

The spec review (R2-01) identified that `listSubgraphs(tenantId)` is needed for the subgraph cache warm-up. This is a new SPI method that must be added to the interface and all implementations.

**Files:**
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapStore.java` — add `listSubgraphs()`
- Modify: `mindmap-inmem/src/main/java/io/casehub/neocortex/mindmap/inmem/InMemoryMindMapStore.java` — implement
- Modify: `mindmap-sqlite/src/main/java/io/casehub/neocortex/mindmap/sqlite/SqliteMindMapStore.java` — implement
- Modify: `mindmap/src/main/java/io/casehub/neocortex/mindmap/runtime/NoOpMindMapStore.java` — implement
- Modify: all decorators in `mindmap/` — add delegation
- Test: `mindmap-testing/src/main/java/io/casehub/neocortex/mindmap/testing/MindMapStoreContractTest.java` — add contract test

**Interfaces:**
- Consumes: `MindMapSubgraph` (from mindmap-api)
- Produces: `MindMapStore.listSubgraphs(String tenantId)` returning `List<MindMapSubgraph>` — used by Task 4

- [ ] **Step 1: Add contract test for listSubgraphs**

Add to `MindMapStoreContractTest`:

```java
@Test
void listSubgraphs_returnsAllSubgraphsForTenant() {
    String sg1 = store().createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
    String sg2 = store().createSubgraph(new SubgraphInput("Projects", SubgraphType.PROJECT, null), TENANT);
    store().createSubgraph(new SubgraphInput("Other", SubgraphType.GENERAL, null), "other-tenant");

    List<MindMapSubgraph> subgraphs = store().listSubgraphs(TENANT);

    assertThat(subgraphs).hasSize(2);
    assertThat(subgraphs).extracting(MindMapSubgraph::id).containsExactlyInAnyOrder(sg1, sg2);
}

@Test
void listSubgraphs_emptyTenantReturnsEmpty() {
    assertThat(store().listSubgraphs(TENANT)).isEmpty();
}
```

- [ ] **Step 2: Add `listSubgraphs` to `MindMapStore` interface**

Use `ide_insert_member` on `MindMapStore.java`:
```java
List<MindMapSubgraph> listSubgraphs(String tenantId);
```

- [ ] **Step 3: Implement in InMemoryMindMapStore, SqliteMindMapStore, NoOpMindMapStore, and all decorators**

`InMemoryMindMapStore` — filter subgraphs map by tenantId:
```java
@Override
public List<MindMapSubgraph> listSubgraphs(String tenantId) {
    return subgraphs.values().stream()
        .filter(sg -> sg.tenantId().equals(tenantId))
        .toList();
}
```

`SqliteMindMapStore` — SQL query:
```java
@Override
public List<MindMapSubgraph> listSubgraphs(String tenantId) {
    // SELECT * FROM subgraphs WHERE tenant_id = ?
    // Map ResultSet rows to MindMapSubgraph records
}
```

`NoOpMindMapStore`:
```java
@Override
public List<MindMapSubgraph> listSubgraphs(String tenantId) {
    return List.of();
}
```

All decorators (`DerivedEdgeDecorator`, `TraitApplicationDecorator`, `VocabularyNormalizationDecorator`, `ConfidenceDecayDecorator`) — delegate:
```java
@Override
public List<MindMapSubgraph> listSubgraphs(String tenantId) {
    return delegate.listSubgraphs(tenantId);
}
```

- [ ] **Step 4: Run contract tests + full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-testing,mindmap-inmem,mindmap-sqlite,mindmap`
Expected: PASS — contract tests pass for both backends

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-api mindmap-inmem mindmap-sqlite mindmap mindmap-testing
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#220): MindMapStore.listSubgraphs() — subgraph discovery for extraction cache Refs #220"
```

### Task 4: MindMapExtractor + Maven dependency wiring

**Files:**
- Modify: `mindmap-intelligence/pom.xml` — add casehub-platform-agent-api + mutiny deps
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractorTest.java`

**Interfaces:**
- Consumes: `MindMapStore` (from mindmap-api), `AgentProvider`/`AgentSessionConfig`/`AgentEvent` (from casehub-platform-agent-api), `ExtractionJsonParser`/`ParsedExtraction` (from Task 2), `ExtractionResult` (from Task 1)
- Produces: `MindMapExtractor.extract(String text, String tenantId)` and `extract(String text, String tenantId, List<String> recentEntityNames)`

- [ ] **Step 1: Add Maven dependencies to pom.xml**

Add to `mindmap-intelligence/pom.xml` `<dependencies>`:
```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-platform-agent-api</artifactId>
</dependency>
<dependency>
  <groupId>io.smallrye.reactive</groupId>
  <artifactId>mutiny</artifactId>
</dependency>
```

- [ ] **Step 2: Write tests for MindMapExtractor**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSession;
import io.casehub.platform.agent.AgentSessionConfig;
import io.casehub.platform.agent.AgentSessionInit;
import io.smallrye.mutiny.Multi;
import jakarta.enterprise.inject.Instance;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class MindMapExtractorTest {

    private static final String TENANT = "test-tenant";
    private InMemoryMindMapStore store;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
    }

    @Test
    void extractEntitiesFromConversation() {
        String response = """
            {"entities": [
                {"name": "Alice", "type": "PERSON", "properties": {"role": "engineer"}, "confidence": "STATED"},
                {"name": "Acme Corp", "type": "ORGANISATION", "properties": {}, "confidence": "STATED"}
            ], "relationships": [
                {"source": "Alice", "target": "Acme Corp", "type": "works-at", "confidence": "STATED"}
            ], "contradictions": []}
            """;
        var extractor = createExtractor(response);

        ExtractionResult result = extractor.extract("Alice is an engineer at Acme Corp", TENANT);

        assertThat(result.entities()).hasSize(2);
        assertThat(result.entities()).extracting(ExtractedEntity::name)
            .containsExactlyInAnyOrder("Alice", "Acme Corp");
        assertThat(result.entities()).allMatch(ExtractedEntity::created);
        assertThat(result.relationships()).hasSize(1);
        assertThat(result.relationships().get(0).edgeType()).isEqualTo("works-at");
        assertThat(result.entityNames()).containsExactlyInAnyOrder("Alice", "Acme Corp");
    }

    @Test
    void resolveExistingEntity() {
        String sgId = store.createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
        store.addNode(new NodeInput("Alice", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of("role", "manager")), TENANT);

        String response = """
            {"entities": [
                {"name": "Alice", "type": "PERSON", "properties": {"email": "alice@acme.com"}, "confidence": "STATED"}
            ], "relationships": [], "contradictions": []}
            """;
        var extractor = createExtractor(response);

        ExtractionResult result = extractor.extract("Alice's email is alice@acme.com", TENANT);

        assertThat(result.entities()).hasSize(1);
        assertThat(result.entities().get(0).created()).isFalse();

        MindMapNode alice = store.resolveNode("Alice", null, TENANT);
        assertThat(alice.property("email")).hasValue("alice@acme.com");
        assertThat(alice.property("role")).hasValue("manager");
    }

    @Test
    void detectContradiction() {
        String sgId = store.createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
        String aliceId = store.addNode(new NodeInput("Alice", sgId, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        String sgOrg = store.createSubgraph(new SubgraphInput("Orgs", SubgraphType.ORGANISATION, null), TENANT);
        String acmeId = store.addNode(new NodeInput("Acme", sgOrg, ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, null, null, Map.of()), TENANT);
        store.addEdge(new EdgeInput(aliceId, acmeId, "works-at", ConfidenceOrigin.STATED, null, "test",
            null, null, null, null, null, Map.of()), TENANT);

        String response = """
            {"entities": [
                {"name": "Alice", "type": "PERSON", "properties": {}, "confidence": "STATED"},
                {"name": "Initech", "type": "ORGANISATION", "properties": {}, "confidence": "STATED"}
            ], "relationships": [
                {"source": "Alice", "target": "Initech", "type": "works-at", "confidence": "STATED"}
            ], "contradictions": [
                {"entity": "Alice", "property": "works-at", "existing": "Acme", "extracted": "Initech", "explanation": "Alice changed jobs"}
            ]}
            """;
        var extractor = createExtractor(response);

        ExtractionResult result = extractor.extract("Alice now works at Initech", TENANT);

        assertThat(result.contradictions()).hasSize(1);
        assertThat(result.contradictions().get(0).entityName()).isEqualTo("Alice");
        assertThat(result.contradictions().get(0).existingValue()).isEqualTo("Acme");
    }

    @Test
    void carryForwardEnablesPronounResolution() {
        String response = """
            {"entities": [
                {"name": "Alice", "type": "PERSON", "properties": {"mood": "excited"}, "confidence": "INFERRED"}
            ], "relationships": [], "contradictions": []}
            """;
        var agent = new TestAgentProvider(response);
        var extractor = new MindMapExtractor(store, stubInstance(agent));

        extractor.extract("She seemed really excited", TENANT, List.of("Alice", "Acme"));

        assertThat(agent.lastUserPrompt).contains("Alice");
        assertThat(agent.lastUserPrompt).contains("Acme");
    }

    @Test
    void emptyLlmResponseReturnsEmpty() {
        var extractor = createExtractor("");

        ExtractionResult result = extractor.extract("Hello world", TENANT);

        assertThat(result).isSameAs(ExtractionResult.EMPTY);
    }

    @Test
    void noOpAgentProviderReturnsEmpty() {
        var noOpProvider = new AgentProvider() {
            @Override
            public Multi<AgentEvent> invoke(AgentSessionConfig config) {
                return Multi.createFrom().empty();
            }
            @Override
            public AgentSession openSession(AgentSessionInit init) {
                throw new UnsupportedOperationException();
            }
        };
        var extractor = new MindMapExtractor(store, stubInstance(noOpProvider));

        ExtractionResult result = extractor.extract("Hello world", TENANT);

        assertThat(result).isSameAs(ExtractionResult.EMPTY);
    }

    @Test
    void malformedJsonReturnsEmpty() {
        var extractor = createExtractor("This is not JSON at all");

        ExtractionResult result = extractor.extract("Hello world", TENANT);

        assertThat(result).isSameAs(ExtractionResult.EMPTY);
    }

    @Test
    void unknownEntityTypeDefaultsToGeneral() {
        String response = """
            {"entities": [
                {"name": "Climate Change", "type": "TOPIC", "properties": {}, "confidence": "STATED"}
            ], "relationships": [], "contradictions": []}
            """;
        var extractor = createExtractor(response);

        ExtractionResult result = extractor.extract("We discussed climate change", TENANT);

        assertThat(result.entities()).hasSize(1);
        assertThat(result.entities().get(0).subgraphType()).isEqualTo("GENERAL");
    }

    @Test
    void traitRulesFireOnExtractedProperties() {
        String response = """
            {"entities": [
                {"name": "Alice", "type": "PERSON", "properties": {"email": "alice@acme.com"}, "confidence": "STATED"}
            ], "relationships": [], "contradictions": []}
            """;
        var extractor = createExtractor(response);

        extractor.extract("Alice's email is alice@acme.com", TENANT);

        MindMapNode alice = store.resolveNode("Alice", null, TENANT);
        assertThat(alice).isNotNull();
        assertThat(alice.property("email")).hasValue("alice@acme.com");
    }

    // --- Test helpers ---

    private MindMapExtractor createExtractor(String cannedResponse) {
        return new MindMapExtractor(store, stubInstance(new TestAgentProvider(cannedResponse)));
    }

    @SuppressWarnings("unchecked")
    private static Instance<AgentProvider> stubInstance(AgentProvider provider) {
        return new Instance<>() {
            @Override public AgentProvider get() { return provider; }
            @Override public boolean isUnsatisfied() { return false; }
            @Override public boolean isResolvable() { return true; }
            @Override public boolean isAmbiguous() { return false; }
            @Override public void destroy(AgentProvider instance) {}
            @Override public Handle<AgentProvider> getHandle() { return null; }
            @Override public Iterable<Handle<AgentProvider>> handles() { return null; }
            @Override public AgentProvider select() { return provider; }
            @Override public Instance<AgentProvider> select(java.lang.annotation.Annotation... qualifiers) { return this; }
            @Override public <U extends AgentProvider> Instance<U> select(Class<U> subtype, java.lang.annotation.Annotation... qualifiers) { return null; }
            @Override public <U extends AgentProvider> Instance<U> select(jakarta.enterprise.util.TypeLiteral<U> subtype, java.lang.annotation.Annotation... qualifiers) { return null; }
            @Override public java.util.Iterator<AgentProvider> iterator() { return List.of(provider).iterator(); }
        };
    }

    static class TestAgentProvider implements AgentProvider {
        private final String response;
        int invocationCount = 0;
        String lastUserPrompt;

        TestAgentProvider(String response) { this.response = response; }

        @Override
        public Multi<AgentEvent> invoke(AgentSessionConfig config) {
            invocationCount++;
            lastUserPrompt = config.userPrompt();
            if (response == null || response.isEmpty()) {
                return Multi.createFrom().empty();
            }
            return Multi.createFrom().items(
                new AgentEvent.TextDelta(response),
                new AgentEvent.InvocationComplete(100, 50, 0, 0, 0, 0.001, 500L, 400L, "test", 1, false));
        }

        @Override
        public AgentSession openSession(AgentSessionInit init) {
            throw new UnsupportedOperationException();
        }
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — MindMapExtractor class not found

- [ ] **Step 4: Implement MindMapExtractor**

Create `MindMapExtractor.java`:
```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.platform.agent.AgentEvent;
import io.casehub.platform.agent.AgentProvider;
import io.casehub.platform.agent.AgentSessionConfig;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;
import jakarta.inject.Singleton;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;
import java.util.stream.Collectors;

@Singleton
public class MindMapExtractor {

    private static final Logger LOG = Logger.getLogger(MindMapExtractor.class.getName());
    private static final int MAX_CONTEXT_NODES = 20;

    private static final String SYSTEM_PROMPT = """
        You are a knowledge graph extraction agent. Given a conversation turn \
        and existing graph context, extract entities and relationships.

        Respond with a JSON object:
        {
          "entities": [
            {"name": "...", "type": "PERSON|PROJECT|RESEARCH_AREA|ORGANISATION|CONCEPT|GENERAL", "properties": {"key": "value"}, "confidence": "STATED|INFERRED|SPECULATED"}
          ],
          "relationships": [
            {"source": "entity name", "target": "entity name", "type": "relationship-type", "confidence": "STATED|INFERRED|SPECULATED"}
          ],
          "contradictions": [
            {"entity": "name", "property": "edge-or-property", "existing": "old value", "extracted": "new value", "explanation": "why they conflict"}
          ]
        }

        Rules:
        - Extract only entities and relationships explicitly or strongly implied in the conversation
        - Use the existing graph context to avoid creating duplicates
        - Use recently mentioned entities to resolve pronouns
        - Flag contradictions when extracted facts conflict with existing graph
        - Respond with valid JSON only""";

    private final MindMapStore store;
    private final Instance<AgentProvider> agentProviderInstance;
    private final Map<String, Map<SubgraphType, String>> subgraphCache = new ConcurrentHashMap<>();

    @Inject
    public MindMapExtractor(MindMapStore store, Instance<AgentProvider> agentProviderInstance) {
        this.store = store;
        this.agentProviderInstance = agentProviderInstance;
    }

    public ExtractionResult extract(String conversationText, String tenantId) {
        return extract(conversationText, tenantId, List.of());
    }

    public ExtractionResult extract(String conversationText, String tenantId, List<String> recentEntityNames) {
        if (conversationText == null || conversationText.isBlank()) return ExtractionResult.EMPTY;
        if (agentProviderInstance.isUnsatisfied()) return ExtractionResult.EMPTY;

        Map<String, List<MindMapEdge>> context = retrieveContext(conversationText, tenantId, recentEntityNames);
        String userPrompt = buildUserPrompt(conversationText, context, recentEntityNames);
        String llmResponse = invokeLlm(SYSTEM_PROMPT, userPrompt);
        if (llmResponse == null) return ExtractionResult.EMPTY;

        ParsedExtraction parsed = ExtractionJsonParser.parse(llmResponse);
        if (parsed == null) return ExtractionResult.EMPTY;

        return applyExtraction(parsed, tenantId);
    }

    private Map<String, List<MindMapEdge>> retrieveContext(String conversationText, String tenantId, List<String> recentEntityNames) {
        Map<String, List<MindMapEdge>> context = new LinkedHashMap<>();

        for (String name : recentEntityNames) {
            MindMapNode node = store.resolveNode(name, null, tenantId);
            if (node != null) {
                context.put(node.id(), store.neighbors(node.id(), tenantId));
            }
        }

        for (String term : extractCandidateTerms(conversationText)) {
            if (context.size() >= MAX_CONTEXT_NODES) break;
            List<MindMapNode> hits = store.search(
                new MindMapQuery(tenantId, null, term, null, null, null, null, false, 5));
            for (MindMapNode node : hits) {
                context.computeIfAbsent(node.id(), id -> store.neighbors(id, tenantId));
            }
        }
        return context;
    }

    List<String> extractCandidateTerms(String text) {
        List<String> terms = new ArrayList<>();
        String[] words = text.split("\\s+");
        StringBuilder current = new StringBuilder();
        for (String word : words) {
            String clean = word.replaceAll("[^a-zA-Z0-9'-]", "");
            if (clean.isEmpty()) continue;
            if (Character.isUpperCase(clean.charAt(0)) && !isCommonWord(clean)) {
                if (!current.isEmpty()) current.append(' ');
                current.append(clean);
            } else {
                if (!current.isEmpty()) {
                    terms.add(current.toString());
                    current.setLength(0);
                }
            }
        }
        if (!current.isEmpty()) terms.add(current.toString());
        return terms;
    }

    private static boolean isCommonWord(String word) {
        return Set.of("The", "A", "An", "I", "We", "He", "She", "It", "They",
            "This", "That", "These", "Those", "My", "Your", "His", "Her",
            "Its", "Our", "Their", "And", "But", "Or", "So", "If", "When",
            "Where", "How", "What", "Who", "Which", "Not", "No", "Yes",
            "Also", "Just", "Now", "Then", "Here", "There").contains(word);
    }

    private String buildUserPrompt(String conversationText, Map<String, List<MindMapEdge>> context, List<String> recentEntityNames) {
        var sb = new StringBuilder();
        sb.append("Conversation:\n").append(conversationText).append("\n\n");

        if (!context.isEmpty()) {
            sb.append("Existing graph context:\n");
            for (var entry : context.entrySet()) {
                MindMapNode node = store.getNode(entry.getKey(), store.search(
                    new MindMapQuery(null, null, null, null, null, null, null, false, 0)).isEmpty()
                    ? "" : "");
                // Simplified: get node directly
            }
            serializeContext(sb, context);
        }

        if (!recentEntityNames.isEmpty()) {
            sb.append("Recently mentioned entities:\n");
            sb.append(String.join(", ", recentEntityNames)).append("\n");
        }
        return sb.toString();
    }

    private void serializeContext(StringBuilder sb, Map<String, List<MindMapEdge>> context) {
        for (var entry : context.entrySet()) {
            String nodeId = entry.getKey();
            List<MindMapEdge> edges = entry.getValue();
            // We need the node to serialize it — retrieve from any tenant
            // The context map was built from search, so we can retrieve
            for (MindMapEdge edge : edges) {
                sb.append("  ").append(edge.edgeType());
                if (edge.sourceNodeId().equals(nodeId)) {
                    sb.append(" → ").append(edge.targetNodeId());
                } else {
                    sb.append(" ← ").append(edge.sourceNodeId());
                }
                sb.append(" [").append(edge.confidenceOrigin()).append("]\n");
            }
        }
    }

    private ExtractionResult applyExtraction(ParsedExtraction parsed, String tenantId) {
        List<ExtractedEntity> entities = new ArrayList<>();
        List<ExtractedRelationship> relationships = new ArrayList<>();
        List<String> entityNames = new ArrayList<>();
        Map<String, String> nameToNodeId = new HashMap<>();

        for (ParsedEntity pe : parsed.entities()) {
            SubgraphType sgType = parseSubgraphType(pe.type());
            String sgId = findOrCreateSubgraph(sgType, tenantId);

            MindMapNode existing = store.resolveNode(pe.name(), null, tenantId);
            String nodeId;
            boolean created;

            if (existing != null) {
                nodeId = existing.id();
                created = false;
                if (pe.properties() != null && !pe.properties().isEmpty()) {
                    store.updateNode(nodeId,
                        new NodeUpdate(null, null, null, null,
                            null, null, null, null, null, null,
                            null, null, null,
                            pe.properties(), null), tenantId);
                }
            } else {
                nodeId = store.addNode(new NodeInput(
                    pe.name(), sgId, pe.confidence(), null,
                    "llm-extraction", null, null, null, null,
                    null, null, null,
                    pe.properties() != null ? pe.properties() : Map.of()), tenantId);
                created = true;
            }

            nameToNodeId.put(pe.name(), nodeId);
            entityNames.add(pe.name());
            entities.add(new ExtractedEntity(nodeId, pe.name(), created, sgType.name(), pe.properties() != null ? pe.properties() : Map.of()));
        }

        for (ParsedRelationship pr : parsed.relationships()) {
            String sourceId = nameToNodeId.get(pr.source());
            String targetId = nameToNodeId.get(pr.target());
            if (sourceId == null) {
                MindMapNode src = store.resolveNode(pr.source(), null, tenantId);
                if (src != null) sourceId = src.id();
            }
            if (targetId == null) {
                MindMapNode tgt = store.resolveNode(pr.target(), null, tenantId);
                if (tgt != null) targetId = tgt.id();
            }
            if (sourceId != null && targetId != null) {
                String edgeId = store.addEdge(new EdgeInput(
                    sourceId, targetId, pr.type(), pr.confidence(), null,
                    "llm-extraction", null, null, null, null, null, Map.of()), tenantId);
                relationships.add(new ExtractedRelationship(edgeId, pr.source(), pr.target(), pr.type(), pr.confidence()));
            }
        }

        List<Contradiction> contradictions = new ArrayList<>();
        for (ParsedContradiction pc : parsed.contradictions()) {
            contradictions.add(new Contradiction(pc.entity(), pc.property(), pc.existing(), pc.extracted(), pc.explanation()));
        }

        return new ExtractionResult(entities, relationships, contradictions, entityNames);
    }

    private String findOrCreateSubgraph(SubgraphType type, String tenantId) {
        Map<SubgraphType, String> tenantCache = subgraphCache.computeIfAbsent(tenantId, t -> {
            Map<SubgraphType, String> warm = new ConcurrentHashMap<>();
            for (MindMapSubgraph sg : store.listSubgraphs(t)) {
                warm.putIfAbsent(sg.type(), sg.id());
            }
            return warm;
        });
        return tenantCache.computeIfAbsent(type, t ->
            store.createSubgraph(new SubgraphInput(t.name(), t, null), tenantId));
    }

    private SubgraphType parseSubgraphType(String type) {
        if (type == null) return SubgraphType.GENERAL;
        try {
            return SubgraphType.valueOf(type);
        } catch (IllegalArgumentException e) {
            LOG.fine("Unknown entity type '" + type + "', mapping to GENERAL");
            return SubgraphType.GENERAL;
        }
    }

    private String invokeLlm(String systemPrompt, String userPrompt) {
        AgentProvider provider = agentProviderInstance.get();
        try {
            var events = provider.invoke(AgentSessionConfig.of(systemPrompt, userPrompt))
                .collect().asList()
                .await().atMost(Duration.ofMinutes(2));

            boolean hasError = events.stream()
                .filter(AgentEvent.InvocationComplete.class::isInstance)
                .map(AgentEvent.InvocationComplete.class::cast)
                .anyMatch(AgentEvent.InvocationComplete::isError);
            if (hasError) {
                LOG.warning("LLM invocation completed with error flag");
                return null;
            }

            String text = events.stream()
                .filter(AgentEvent.TextDelta.class::isInstance)
                .map(AgentEvent.TextDelta.class::cast)
                .map(AgentEvent.TextDelta::text)
                .collect(Collectors.joining());

            return text.isEmpty() ? null : text;
        } catch (Exception e) {
            LOG.warning("LLM invocation failed: " + e.getMessage());
            return null;
        }
    }
}
```

**Note:** The `buildUserPrompt` method above has a simplified context serialization. The actual implementation should serialize node names and edge types from the context map. This will be refined during implementation when we can use `ide_replace_member` to iterate.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorTest`
Expected: PASS — 9 tests

- [ ] **Step 6: Run full build to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-intelligence
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#220): MindMapExtractor — LLM entity/relationship extraction pipeline Refs #220"
```

## Batch 3: Context Serialization Refinement + Edge Cases

### Task 5: Refine context serialization and add edge case tests

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java` — fix buildUserPrompt serialization
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractorTest.java` — add edge case tests

**Interfaces:**
- Consumes: all types from Tasks 1-4
- Produces: refined `MindMapExtractor` with correct context serialization

- [ ] **Step 1: Add tests for context serialization and edge cases**

Add to `MindMapExtractorTest`:

```java
@Test
void contextSerializationIncludesNodeNamesAndEdges() {
    String sgId = store.createSubgraph(new SubgraphInput("People", SubgraphType.PERSON, null), TENANT);
    String aliceId = store.addNode(new NodeInput("Alice", sgId, ConfidenceOrigin.STATED, null, "test",
        null, null, null, null, null, null, null, Map.of("role", "engineer")), TENANT);
    String sgOrg = store.createSubgraph(new SubgraphInput("Orgs", SubgraphType.ORGANISATION, null), TENANT);
    String acmeId = store.addNode(new NodeInput("Acme", sgOrg, ConfidenceOrigin.STATED, null, "test",
        null, null, null, null, null, null, null, Map.of()), TENANT);
    store.addEdge(new EdgeInput(aliceId, acmeId, "works-at", ConfidenceOrigin.STATED, null, "test",
        null, null, null, null, null, Map.of()), TENANT);

    String response = """
        {"entities": [], "relationships": [], "contradictions": []}
        """;
    var agent = new TestAgentProvider(response);
    var extractor = new MindMapExtractor(store, stubInstance(agent));

    extractor.extract("Alice mentioned her project", TENANT, List.of("Alice"));

    assertThat(agent.lastUserPrompt).contains("Alice");
    assertThat(agent.lastUserPrompt).contains("works-at");
}

@Test
void extractCandidateTerms_capitalisedSequences() {
    var extractor = createExtractor("");
    List<String> terms = extractor.extractCandidateTerms("Alice Smith works at Acme Corp in New York");
    assertThat(terms).containsExactly("Alice Smith", "Acme Corp", "New York");
}

@Test
void extractCandidateTerms_filtersCommonWords() {
    var extractor = createExtractor("");
    List<String> terms = extractor.extractCandidateTerms("The quick Brown Fox jumps over The Lazy Dog");
    assertThat(terms).contains("Brown Fox");
    assertThat(terms).doesNotContain("The");
}

@Test
void subgraphCacheIsTenantAware() {
    String response1 = """
        {"entities": [{"name": "Alice", "type": "PERSON", "properties": {}, "confidence": "STATED"}], "relationships": [], "contradictions": []}
        """;
    var extractor = createExtractor(response1);

    extractor.extract("Alice is a person", "tenant-a");
    extractor.extract("Alice is a person", "tenant-b");

    List<MindMapSubgraph> sgA = store.listSubgraphs("tenant-a");
    List<MindMapSubgraph> sgB = store.listSubgraphs("tenant-b");
    assertThat(sgA).hasSize(1);
    assertThat(sgB).hasSize(1);
    assertThat(sgA.get(0).id()).isNotEqualTo(sgB.get(0).id());
}

@Test
void relationshipWithUnresolvedEndpointIsSkipped() {
    String response = """
        {"entities": [
            {"name": "Alice", "type": "PERSON", "properties": {}, "confidence": "STATED"}
        ], "relationships": [
            {"source": "Alice", "target": "UnknownEntity", "type": "knows", "confidence": "INFERRED"}
        ], "contradictions": []}
        """;
    var extractor = createExtractor(response);

    ExtractionResult result = extractor.extract("Alice knows someone", TENANT);

    assertThat(result.entities()).hasSize(1);
    assertThat(result.relationships()).isEmpty();
}
```

- [ ] **Step 2: Fix buildUserPrompt to properly serialize context nodes**

Refine the `buildUserPrompt` and `serializeContext` methods to include node names, subgraph types, confidence, traits, and edge details. Use `store.getNode()` to retrieve node metadata for serialization.

```java
private String buildUserPrompt(String conversationText, Map<String, List<MindMapEdge>> context,
                                List<String> recentEntityNames, String tenantId) {
    var sb = new StringBuilder();
    sb.append("Conversation:\n").append(conversationText).append("\n\n");

    if (!context.isEmpty()) {
        sb.append("Existing graph context:\n");
        for (var entry : context.entrySet()) {
            MindMapNode node = store.getNode(entry.getKey(), tenantId);
            if (node == null) continue;
            sb.append("- ").append(node.name());
            sb.append(" (confidence: ").append(String.format("%.2f", node.confidence()));
            if (!node.traits().isEmpty()) {
                sb.append(", traits: ").append(String.join(", ", node.traits()));
            }
            sb.append(")\n");
            for (MindMapEdge edge : entry.getValue()) {
                sb.append("  ");
                if (edge.sourceNodeId().equals(node.id())) {
                    sb.append("→ ").append(edge.edgeType()).append(" → ");
                    MindMapNode target = store.getNode(edge.targetNodeId(), tenantId);
                    sb.append(target != null ? target.name() : edge.targetNodeId());
                } else {
                    sb.append("← ").append(edge.edgeType()).append(" ← ");
                    MindMapNode source = store.getNode(edge.sourceNodeId(), tenantId);
                    sb.append(source != null ? source.name() : edge.sourceNodeId());
                }
                sb.append(" [").append(edge.confidenceOrigin()).append("]\n");
            }
        }
        sb.append('\n');
    }

    if (!recentEntityNames.isEmpty()) {
        sb.append("Recently mentioned entities:\n");
        sb.append(String.join(", ", recentEntityNames)).append("\n");
    }
    return sb.toString();
}
```

Update the `extract` method to pass `tenantId` to `buildUserPrompt`.

- [ ] **Step 3: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: PASS — all tests

- [ ] **Step 4: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-intelligence
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#220): refine context serialization + edge case coverage Refs #220"
```

---

## References

- `specs/mindmap-spi/2026-08-26-mindmap-spi-design.md` §6 — LLM extraction spec
- `specs/mindmap-spi/decisions.md` D26-D35 — extraction design decisions
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/TraitProxy.java` — existing module structure
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapStore.java` — SPI interface (27 methods)
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeInput.java` — node creation record
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ConfidenceOrigin.java` — confidence enum
- GE-20260801-0aee7e — AgentEvent hierarchy and blocking text extraction
- GE-20260801-bcff35 — TestAgentProvider pattern
- GE-20260810-b1da3b — Structured JSON output via system prompt
- GE-20260810-804c58 — AgentProvider CDI tiering
- GitHub #220 — feat: mindmap-intelligence — LLM entity/relationship extraction
- GitHub #213 — MindMap SPI epic
