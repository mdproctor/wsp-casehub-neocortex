# Sub-Thought Representation & Biographical Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #470 — feat: sub-thought representation and biographical import template schema
**Issue group:** #470

**Goal:** Add sub-thought decomposition as Memory attributes with optional MindMap node attachment, and a biographical import framework with 10 template types across an 8-layer import model.

**Architecture:** Sub-thoughts are indexed attributes on parent Memory records (`sub-thought-N-type`, `sub-thought-N-text`, `sub-thought-N-entity`). A new `CaseMemoryStore.enrichAttributes()` SPI method enables async post-store enrichment. `SubThoughtConsolidationPhase` graduates cross-memory patterns to COGNITIVE MindMap nodes via `SubThoughtRef` NodeRef linking. Biographical import uses a `BiographyHandler` registry dispatched in layer order by `BiographyImportRunner`.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI, Jackson YAML, JUnit 5, AssertJ, Mockito

## Global Constraints

- Java 21 source on Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26)`
- Build with `mvn` not `./mvnw`
- All commits reference #470: `Refs #470` or `Closes #470`
- New constants follow `SubgraphTypes` pattern: `public static final String`, private constructor, no enum
- New NodeRef conventions follow `OverlayRef` pattern: scheme constant, static factories, static extractors
- CaseMemoryStore default methods throw `MemoryCapabilityException`
- Handler provenance: `provenance=biographical-import`, `template-ref=<file>#<id>`, `source-ref=<source_ref>`
- Tests use AssertJ assertions, JUnit 5, contract test pattern where applicable

---

## Batch 1: Sub-thought type system

### Task 1: SubThoughtTypes + SubThoughtAttributeKeys

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtTypes.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtAttributeKeys.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/experience/SubThoughtTypesTest.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/experience/SubThoughtAttributeKeysTest.java`

**Interfaces:**
- Consumes: nothing (leaf types)
- Produces: `SubThoughtTypes.AFFECT_OBSERVATION` etc. (7 constants), `SubThoughtTypes.isKnown(String)`, `SubThoughtTypes.validate(String)`, `SubThoughtAttributeKeys.COUNT`, `SubThoughtAttributeKeys.type(int)`, `SubThoughtAttributeKeys.text(int)`, `SubThoughtAttributeKeys.entity(int)`, `SubThoughtAttributeKeys.graduated(int)`

- [ ] **Step 1: Write SubThoughtTypes tests**

```java
package io.casehub.neocortex.memory.experience;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class SubThoughtTypesTest {

    @Test
    void knownTypesAreRecognised() {
        assertThat(SubThoughtTypes.isKnown("affect-observation")).isTrue();
        assertThat(SubThoughtTypes.isKnown("causal-inference")).isTrue();
        assertThat(SubThoughtTypes.isKnown("evaluative")).isTrue();
        assertThat(SubThoughtTypes.isKnown("intention")).isTrue();
        assertThat(SubThoughtTypes.isKnown("self-reflection")).isTrue();
        assertThat(SubThoughtTypes.isKnown("association")).isTrue();
        assertThat(SubThoughtTypes.isKnown("concern")).isTrue();
    }

    @Test
    void unknownTypeIsNotRecognised() {
        assertThat(SubThoughtTypes.isKnown("unknown-type")).isFalse();
        assertThat(SubThoughtTypes.isKnown("")).isFalse();
    }

    @Test
    void validateThrowsForUnknownType() {
        assertThatThrownBy(() -> SubThoughtTypes.validate("bogus"))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("Unknown sub-thought type: bogus");
    }

    @Test
    void validateAcceptsKnownType() {
        assertThatCode(() -> SubThoughtTypes.validate("intention"))
            .doesNotThrowAnyException();
    }

    @Test
    void constantsMatchExpectedValues() {
        assertThat(SubThoughtTypes.AFFECT_OBSERVATION).isEqualTo("affect-observation");
        assertThat(SubThoughtTypes.CAUSAL_INFERENCE).isEqualTo("causal-inference");
        assertThat(SubThoughtTypes.EVALUATIVE).isEqualTo("evaluative");
        assertThat(SubThoughtTypes.INTENTION).isEqualTo("intention");
        assertThat(SubThoughtTypes.SELF_REFLECTION).isEqualTo("self-reflection");
        assertThat(SubThoughtTypes.ASSOCIATION).isEqualTo("association");
        assertThat(SubThoughtTypes.CONCERN).isEqualTo("concern");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SubThoughtTypesTest -am`
Expected: FAIL — `SubThoughtTypes` does not exist

- [ ] **Step 3: Write SubThoughtTypes implementation**

Use `ide_create_file` or Write tool.

```java
package io.casehub.neocortex.memory.experience;

import java.util.Set;

public final class SubThoughtTypes {
    public static final String AFFECT_OBSERVATION = "affect-observation";
    public static final String CAUSAL_INFERENCE   = "causal-inference";
    public static final String EVALUATIVE         = "evaluative";
    public static final String INTENTION          = "intention";
    public static final String SELF_REFLECTION    = "self-reflection";
    public static final String ASSOCIATION        = "association";
    public static final String CONCERN            = "concern";

    private static final Set<String> KNOWN = Set.of(
        AFFECT_OBSERVATION, CAUSAL_INFERENCE, EVALUATIVE,
        INTENTION, SELF_REFLECTION, ASSOCIATION, CONCERN);

    public static boolean isKnown(String type) {
        return KNOWN.contains(type);
    }

    public static void validate(String type) {
        if (!isKnown(type)) {
            throw new IllegalArgumentException(
                "Unknown sub-thought type: " + type + ". Known: " + KNOWN);
        }
    }

    private SubThoughtTypes() {}
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SubThoughtTypesTest -am`
Expected: PASS — all 5 tests green

- [ ] **Step 5: Write SubThoughtAttributeKeys tests**

```java
package io.casehub.neocortex.memory.experience;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class SubThoughtAttributeKeysTest {

    @Test
    void countConstant() {
        assertThat(SubThoughtAttributeKeys.COUNT).isEqualTo("sub-thought-count");
    }

    @Test
    void indexedKeyGeneration() {
        assertThat(SubThoughtAttributeKeys.type(0)).isEqualTo("sub-thought-0-type");
        assertThat(SubThoughtAttributeKeys.text(0)).isEqualTo("sub-thought-0-text");
        assertThat(SubThoughtAttributeKeys.entity(0)).isEqualTo("sub-thought-0-entity");
        assertThat(SubThoughtAttributeKeys.graduated(0)).isEqualTo("sub-thought-0-graduated");
    }

    @Test
    void indexedKeyGenerationHigherIndex() {
        assertThat(SubThoughtAttributeKeys.type(3)).isEqualTo("sub-thought-3-type");
        assertThat(SubThoughtAttributeKeys.text(12)).isEqualTo("sub-thought-12-text");
    }
}
```

- [ ] **Step 6: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SubThoughtAttributeKeysTest -am`
Expected: FAIL — `SubThoughtAttributeKeys` does not exist

- [ ] **Step 7: Write SubThoughtAttributeKeys implementation**

```java
package io.casehub.neocortex.memory.experience;

public final class SubThoughtAttributeKeys {
    public static final String COUNT = "sub-thought-count";

    public static String type(int index)      { return "sub-thought-" + index + "-type"; }
    public static String text(int index)      { return "sub-thought-" + index + "-text"; }
    public static String entity(int index)    { return "sub-thought-" + index + "-entity"; }
    public static String graduated(int index) { return "sub-thought-" + index + "-graduated"; }

    private SubThoughtAttributeKeys() {}
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=SubThoughtAttributeKeysTest -am`
Expected: PASS — all 3 tests green

- [ ] **Step 9: Commit**

```bash
git add memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtTypes.java memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtAttributeKeys.java memory-api/src/test/java/io/casehub/neocortex/memory/experience/SubThoughtTypesTest.java memory-api/src/test/java/io/casehub/neocortex/memory/experience/SubThoughtAttributeKeysTest.java
git commit -m "feat(#470): add SubThoughtTypes constants and SubThoughtAttributeKeys

Refs #470"
```

---

### Task 2: enrichAttributes SPI + SubThoughtRef + SubgraphTypes.CULTURAL

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryCapability.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/CaseMemoryStore.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/DelegatingCaseMemoryStore.java`
- Modify: `memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java`
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubThoughtRef.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/EnrichAttributesContractTest.java`
- Test: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/SubThoughtRefTest.java`

**Interfaces:**
- Consumes: `MemoryCapability` enum, `CaseMemoryStore` SPI, `NodeRef(scheme, id, qualifier)`, `OverlayRef` pattern
- Produces: `MemoryCapability.ENRICH_ATTRIBUTES`, `CaseMemoryStore.enrichAttributes(String memoryId, Map<String, String> additionalAttributes, String tenantId)`, `SubThoughtRef.of(String memoryId, int subThoughtIndex)` → `NodeRef`, `SubThoughtRef.memoryId(MindMapNode)` → `Optional<String>`, `SubThoughtRef.subThoughtIndex(MindMapNode)` → `Optional<Integer>`, `SubgraphTypes.CULTURAL`

- [ ] **Step 1: Write enrichAttributes contract test**

```java
package io.casehub.neocortex.memory;

import io.casehub.neocortex.memory.experience.ExperienceEvents;
import io.casehub.neocortex.memory.experience.SubThoughtAttributeKeys;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

import java.util.Map;

public abstract class EnrichAttributesContractTest {

    protected abstract CaseMemoryStore store();
    protected abstract String tenantId();

    @Test
    void enrichAttributesMergesIntoExistingMemory() {
        String memoryId = store().store(
            MemoryInput.of(Subject.of("agent", "a1"),
                ExperienceEvents.DOMAIN, tenantId(), "Lunch with Sarah"));

        store().enrichAttributes(memoryId,
            Map.of(SubThoughtAttributeKeys.COUNT, "1",
                   SubThoughtAttributeKeys.type(0), "affect-observation",
                   SubThoughtAttributeKeys.text(0), "She seemed distracted"),
            tenantId());

        var results = store().query(MemoryQuery.of(
            Subject.of("agent", "a1"), ExperienceEvents.DOMAIN, tenantId()));
        assertThat(results).hasSize(1);
        var memory = results.getFirst();
        assertThat(memory.attributes()).containsEntry(
            SubThoughtAttributeKeys.COUNT, "1");
        assertThat(memory.attributes()).containsEntry(
            SubThoughtAttributeKeys.type(0), "affect-observation");
        assertThat(memory.attributes()).containsEntry(
            SubThoughtAttributeKeys.text(0), "She seemed distracted");
    }

    @Test
    void enrichAttributesPreservesExistingAttributes() {
        String memoryId = store().store(
            MemoryInput.of(Subject.of("agent", "a1"),
                ExperienceEvents.DOMAIN, tenantId(), "Test memory")
                .withAttribute("event-type", "observation"));

        store().enrichAttributes(memoryId,
            Map.of(SubThoughtAttributeKeys.COUNT, "1"),
            tenantId());

        var results = store().query(MemoryQuery.of(
            Subject.of("agent", "a1"), ExperienceEvents.DOMAIN, tenantId()));
        var memory = results.getFirst();
        assertThat(memory.attributes()).containsEntry("event-type", "observation");
        assertThat(memory.attributes()).containsEntry(
            SubThoughtAttributeKeys.COUNT, "1");
    }

    @Test
    void enrichAttributesThrowsForNonexistentMemory() {
        assertThatThrownBy(() ->
            store().enrichAttributes("nonexistent-id",
                Map.of("key", "value"), tenantId()))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void enrichAttributesCapabilityDeclared() {
        assertThat(store().capabilities())
            .contains(MemoryCapability.ENRICH_ATTRIBUTES);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -am`
Expected: FAIL — `ENRICH_ATTRIBUTES` does not exist

- [ ] **Step 3: Add ENRICH_ATTRIBUTES to MemoryCapability**

Use `ide_insert_member` on `MemoryCapability.java` to add after `PURGE`:

```java
    ENRICH_ATTRIBUTES
```

- [ ] **Step 4: Add enrichAttributes default method to CaseMemoryStore**

Use `ide_insert_member` on `CaseMemoryStore.java` to add before the closing brace:

```java
    default void enrichAttributes(String memoryId, Map<String, String> additionalAttributes,
                                  String tenantId) {
        throw new MemoryCapabilityException(MemoryCapability.ENRICH_ATTRIBUTES, getClass());
    }
```

Add `import java.util.Map;` if not already present.

- [ ] **Step 5: Add enrichAttributes delegation to DelegatingCaseMemoryStore**

Use `ide_insert_member` on `DelegatingCaseMemoryStore.java`:

```java
    @Override public void enrichAttributes(String memoryId, Map<String, String> additionalAttributes, String tenantId) { delegate.enrichAttributes(memoryId, additionalAttributes, tenantId); }
```

Add `import java.util.Map;` if not already present.

- [ ] **Step 6: Implement enrichAttributes in InMemoryMemoryStore**

Use `ide_insert_member` on `InMemoryMemoryStore.java`. Add ENRICH_ATTRIBUTES to the capabilities set. Then add:

```java
    @Override
    public void enrichAttributes(String memoryId, Map<String, String> additionalAttributes,
                                 String tenantId) {
        boolean found = false;
        for (var entry : store.entrySet()) {
            if (!entry.getKey().tenantId().equals(tenantId)) continue;
            var memories = entry.getValue();
            for (int i = 0; i < memories.size(); i++) {
                var m = memories.get(i);
                if (m.memoryId().equals(memoryId)) {
                    var merged = new java.util.HashMap<>(m.attributes());
                    merged.putAll(additionalAttributes);
                    memories.set(i, new Memory(m.memoryId(), m.subject(), m.domain(),
                        m.tenantId(), m.caseId(), m.text(), merged, m.createdAt(),
                        m.confidence(), m.pleasure(), m.arousal(), m.dominance(),
                        m.principalId(), m.sharedWith()));
                    found = true;
                    break;
                }
            }
            if (found) break;
        }
        if (!found) {
            throw new IllegalArgumentException("Memory not found: " + memoryId);
        }
    }
```

- [ ] **Step 7: Run enrichAttributes contract test via InMemoryMemoryStore**

Create a concrete test in memory-inmem that extends the contract test:

```java
package io.casehub.neocortex.memory.inmem;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.EnrichAttributesContractTest;
import org.junit.jupiter.api.BeforeEach;

class InMemoryEnrichAttributesTest extends EnrichAttributesContractTest {
    private InMemoryMemoryStore store;

    @BeforeEach
    void setUp() { store = new InMemoryMemoryStore(null); }

    @Override protected CaseMemoryStore store() { return store; }
    @Override protected String tenantId() { return "test-tenant"; }
}
```

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-inmem -Dtest=InMemoryEnrichAttributesTest -am`
Expected: PASS — all 4 tests green

- [ ] **Step 8: Write SubThoughtRef test**

```java
package io.casehub.neocortex.mindmap;

import org.junit.jupiter.api.Test;
import java.util.Optional;
import java.util.Set;
import static org.assertj.core.api.Assertions.*;

class SubThoughtRefTest {

    @Test
    void ofCreatesNodeRefWithCorrectScheme() {
        NodeRef ref = SubThoughtRef.of("mem-123", 2);
        assertThat(ref.scheme()).isEqualTo("sub-thought");
        assertThat(ref.id()).isEqualTo("mem-123");
        assertThat(ref.qualifier()).isEqualTo("2");
    }

    @Test
    void memoryIdExtractsFromNode() {
        var node = stubNode(Set.of(SubThoughtRef.of("mem-456", 0)));
        assertThat(SubThoughtRef.memoryId(node)).isEqualTo(Optional.of("mem-456"));
    }

    @Test
    void subThoughtIndexExtractsFromNode() {
        var node = stubNode(Set.of(SubThoughtRef.of("mem-456", 3)));
        assertThat(SubThoughtRef.subThoughtIndex(node)).isEqualTo(Optional.of(3));
    }

    @Test
    void emptyWhenNoSubThoughtRef() {
        var node = stubNode(Set.of(new NodeRef("other", "id", null)));
        assertThat(SubThoughtRef.memoryId(node)).isEmpty();
        assertThat(SubThoughtRef.subThoughtIndex(node)).isEmpty();
    }

    private MindMapNode stubNode(Set<NodeRef> refs) {
        return new MindMapNode() {
            @Override public String subgraphType() { return "cognitive"; }
            @Override public String id() { return "n1"; }
            @Override public String name() { return "test"; }
            @Override public String subgraphId() { return "sg1"; }
            @Override public io.casehub.neocortex.cognitive.Confidence confidence() { return null; }
            @Override public String provenance() { return null; }
            @Override public java.time.Instant createdAt() { return null; }
            @Override public java.time.Instant updatedAt() { return null; }
            @Override public java.time.Instant validFrom() { return null; }
            @Override public java.time.Instant validUntil() { return null; }
            @Override public Set<String> traits() { return Set.of(); }
            @Override public Set<NodeRef> refs() { return refs; }
            @Override public Double pleasure() { return null; }
            @Override public Double arousal() { return null; }
            @Override public Double dominance() { return null; }
            @Override public Optional<String> property(String key) { return Optional.empty(); }
            @Override public java.util.Map<String, String> properties() { return java.util.Map.of(); }
            @Override public io.casehub.platform.api.identity.PrincipalId principalId() { return null; }
            @Override public Set<String> sharedWith() { return Set.of(); }
        };
    }
}
```

- [ ] **Step 9: Write SubThoughtRef implementation**

```java
package io.casehub.neocortex.mindmap;

import java.util.Optional;

public final class SubThoughtRef {
    public static final String SCHEME = "sub-thought";

    public static NodeRef of(String memoryId, int subThoughtIndex) {
        return new NodeRef(SCHEME, memoryId, String.valueOf(subThoughtIndex));
    }

    public static Optional<String> memoryId(MindMapNode node) {
        return node.refs().stream()
            .filter(r -> SCHEME.equals(r.scheme()))
            .map(NodeRef::id)
            .findFirst();
    }

    public static Optional<Integer> subThoughtIndex(MindMapNode node) {
        return node.refs().stream()
            .filter(r -> SCHEME.equals(r.scheme()))
            .map(r -> Integer.parseInt(r.qualifier()))
            .findFirst();
    }

    private SubThoughtRef() {}
}
```

- [ ] **Step 10: Add CULTURAL to SubgraphTypes**

Use `ide_insert_member` on `SubgraphTypes.java` to add after `BEHAVIORAL`:

```java
    public static final String CULTURAL   = "cultural";
```

- [ ] **Step 11: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api,memory-inmem,mindmap-api -am`
Expected: PASS

- [ ] **Step 12: Commit**

```bash
git add memory-api/src/main/java/io/casehub/neocortex/memory/MemoryCapability.java memory-api/src/main/java/io/casehub/neocortex/memory/CaseMemoryStore.java memory-api/src/main/java/io/casehub/neocortex/memory/DelegatingCaseMemoryStore.java memory-api/src/test/java/io/casehub/neocortex/memory/EnrichAttributesContractTest.java memory-inmem/src/main/java/io/casehub/neocortex/memory/inmem/InMemoryMemoryStore.java memory-inmem/src/test/java/io/casehub/neocortex/memory/inmem/InMemoryEnrichAttributesTest.java mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubThoughtRef.java mindmap-api/src/main/java/io/casehub/neocortex/mindmap/SubgraphTypes.java mindmap-api/src/test/java/io/casehub/neocortex/mindmap/SubThoughtRefTest.java
git commit -m "feat(#470): add enrichAttributes SPI, SubThoughtRef, and CULTURAL subgraph type

Refs #470"
```

---

## Batch 2: Sub-thought extraction pipeline

### Task 3: SubThoughtExtractor + CheckInService integration

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractionRequested.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractor.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInService.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInResult.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractorTest.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CheckInServiceSubThoughtTest.java`

**Interfaces:**
- Consumes: `SubThoughtTypes.validate(String)`, `SubThoughtAttributeKeys.*`, `CaseMemoryStore.enrichAttributes(String, Map, String)`, `ExperienceRecorder.record(ExperienceEvent)`, `CheckInService.checkIn(CheckInRequest, String)`
- Produces: `SubThoughtExtractionRequested(memoryId, tenantId, experienceText, principalId)`, `SubThoughtExtractor.onExtractionRequested(@ObservesAsync SubThoughtExtractionRequested)`

- [ ] **Step 1: Write SubThoughtExtractionRequested event record**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.platform.api.identity.PrincipalId;

public record SubThoughtExtractionRequested(
        String memoryId,
        String tenantId,
        String experienceText,
        PrincipalId principalId
) {
    public SubThoughtExtractionRequested {
        java.util.Objects.requireNonNull(memoryId, "memoryId required");
        java.util.Objects.requireNonNull(tenantId, "tenantId required");
        java.util.Objects.requireNonNull(experienceText, "experienceText required");
    }
}
```

- [ ] **Step 2: Write SubThoughtExtractor test**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.experience.SubThoughtAttributeKeys;
import io.casehub.neocortex.memory.experience.SubThoughtTypes;
import io.casehub.platform.api.identity.PrincipalId;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class SubThoughtExtractorTest {

    @Test
    void enrichesMemoryWithParsedSubThoughts() {
        var store = mock(CaseMemoryStore.class);
        var extractor = new SubThoughtExtractor(store);

        var parsed = List.of(
            new SubThoughtExtractor.ParsedSubThought(
                SubThoughtTypes.AFFECT_OBSERVATION, "She seemed distracted", "Sarah"),
            new SubThoughtExtractor.ParsedSubThought(
                SubThoughtTypes.INTENTION, "Should bring David here", "La Trattoria")
        );

        extractor.applySubThoughts("mem-1", parsed, "tenant-1");

        @SuppressWarnings("unchecked")
        ArgumentCaptor<Map<String, String>> attrsCaptor = ArgumentCaptor.forClass(Map.class);
        verify(store).enrichAttributes(eq("mem-1"), attrsCaptor.capture(), eq("tenant-1"));

        Map<String, String> attrs = attrsCaptor.getValue();
        assertThat(attrs).containsEntry(SubThoughtAttributeKeys.COUNT, "2");
        assertThat(attrs).containsEntry(SubThoughtAttributeKeys.type(0), "affect-observation");
        assertThat(attrs).containsEntry(SubThoughtAttributeKeys.text(0), "She seemed distracted");
        assertThat(attrs).containsEntry(SubThoughtAttributeKeys.entity(0), "Sarah");
        assertThat(attrs).containsEntry(SubThoughtAttributeKeys.type(1), "intention");
        assertThat(attrs).containsEntry(SubThoughtAttributeKeys.text(1), "Should bring David here");
        assertThat(attrs).containsEntry(SubThoughtAttributeKeys.entity(1), "La Trattoria");
    }

    @Test
    void rejectsUnknownSubThoughtType() {
        var store = mock(CaseMemoryStore.class);
        var extractor = new SubThoughtExtractor(store);

        var parsed = List.of(
            new SubThoughtExtractor.ParsedSubThought("bogus", "text", null));

        assertThatThrownBy(() -> extractor.applySubThoughts("mem-1", parsed, "t1"))
            .isInstanceOf(IllegalArgumentException.class)
            .hasMessageContaining("Unknown sub-thought type");
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SubThoughtExtractorTest -am`
Expected: FAIL — `SubThoughtExtractor` does not exist

- [ ] **Step 4: Write SubThoughtExtractor implementation**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.experience.SubThoughtAttributeKeys;
import io.casehub.neocortex.memory.experience.SubThoughtTypes;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.ObservesAsync;
import jakarta.inject.Inject;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.logging.Level;
import java.util.logging.Logger;

@ApplicationScoped
public class SubThoughtExtractor {

    private static final Logger LOG = Logger.getLogger(SubThoughtExtractor.class.getName());

    private final CaseMemoryStore memoryStore;

    @Inject
    public SubThoughtExtractor(CaseMemoryStore memoryStore) {
        this.memoryStore = memoryStore;
    }

    public void onExtractionRequested(@ObservesAsync SubThoughtExtractionRequested event) {
        try {
            // LLM call would go here — parse experienceText into sub-thoughts
            // For now, this is a hook point. The LLM integration is a separate concern.
            LOG.fine(() -> "Sub-thought extraction requested for memory " + event.memoryId());
        } catch (Exception e) {
            LOG.log(Level.WARNING, "Sub-thought extraction failed for memory " + event.memoryId(), e);
        }
    }

    public void applySubThoughts(String memoryId, List<ParsedSubThought> subThoughts,
                                  String tenantId) {
        Map<String, String> attrs = new HashMap<>();
        attrs.put(SubThoughtAttributeKeys.COUNT, String.valueOf(subThoughts.size()));
        for (int i = 0; i < subThoughts.size(); i++) {
            var st = subThoughts.get(i);
            SubThoughtTypes.validate(st.type());
            attrs.put(SubThoughtAttributeKeys.type(i), st.type());
            attrs.put(SubThoughtAttributeKeys.text(i), st.text());
            if (st.entity() != null) {
                attrs.put(SubThoughtAttributeKeys.entity(i), st.entity());
            }
        }
        memoryStore.enrichAttributes(memoryId, attrs, tenantId);
    }

    public record ParsedSubThought(String type, String text, String entity) {}
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SubThoughtExtractorTest -am`
Expected: PASS

- [ ] **Step 6: Modify CheckInService to create experience memory and fire extraction event**

Read `CheckInService.java` and `CheckInResult.java` first. Then modify `CheckInService`:

1. Add constructor parameters: `ExperienceRecorder recorder`, `Event<SubThoughtExtractionRequested> extractionEvent`
2. In `checkIn()`, after creating the activity node: create an `Observation` experience via recorder, fire `SubThoughtExtractionRequested` async
3. Return a new `CheckInResult` that includes `memoryId`

Use `ide_replace_member` to modify the constructor and `checkIn` method. Update `CheckInResult` to include `String memoryId`.

- [ ] **Step 7: Write CheckInService integration test**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.memory.experience.ExperienceRecorder;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class CheckInServiceSubThoughtTest {

    @Test
    void checkInFiresSubThoughtExtractionEvent() {
        var store = new InMemoryMindMapStore();
        var recorder = mock(ExperienceRecorder.class);
        when(recorder.record(any())).thenReturn("mem-1");

        var eventCaptor = ArgumentCaptor.forClass(SubThoughtExtractionRequested.class);
        @SuppressWarnings("unchecked")
        jakarta.enterprise.event.Event<SubThoughtExtractionRequested> event = mock(jakarta.enterprise.event.Event.class);

        var service = new CheckInService(store, recorder, event);
        var request = CheckInRequest.of("Lunch with Sarah", "La Trattoria")
            .withDate(Instant.parse("2026-10-07T12:00:00Z"))
            .withNotes("Great pasta, Sarah seemed distracted");

        var result = service.checkIn(request, "tenant-1");

        assertThat(result.memoryId()).isNotNull();
        verify(event).fireAsync(eventCaptor.capture());
        var extracted = eventCaptor.getValue();
        assertThat(extracted.memoryId()).isEqualTo("mem-1");
        assertThat(extracted.tenantId()).isEqualTo("tenant-1");
    }
}
```

- [ ] **Step 8: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -am`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractionRequested.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractor.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInService.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInResult.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractorTest.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/CheckInServiceSubThoughtTest.java
git commit -m "feat(#470): add SubThoughtExtractor and CheckInService integration

CheckInService now creates an experience Observation memory and fires
SubThoughtExtractionRequested for async LLM decomposition.

Refs #470"
```

---

## Batch 3: Sub-thought graduation

### Task 4: SubThoughtConsolidationPhase

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SubThoughtConsolidationPhase.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SubThoughtConsolidationPhaseTest.java`

**Interfaces:**
- Consumes: `ConsolidationPhase` SPI, `CaseMemoryStore.scan(MemoryScanRequest)`, `CaseMemoryStore.enrichAttributes(String, Map, String)`, `MindMapStore.addNode(NodeInput, String)`, `SubThoughtAttributeKeys.*`, `SubThoughtRef.of(String, int)`, `SubgraphTypes.COGNITIVE`
- Produces: `SubThoughtConsolidationPhase` — `@Priority(16)` `ConsolidationPhase` impl; graduated `MindMapNode` entries in COGNITIVE subgraph with `graduated-sub-thought` trait and multi-NodeRef traceability

- [ ] **Step 1: Write SubThoughtConsolidationPhase test**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryInput;
import io.casehub.neocortex.memory.MemoryScanRequest;
import io.casehub.neocortex.memory.Subject;
import io.casehub.neocortex.memory.experience.ExperienceEvents;
import io.casehub.neocortex.memory.experience.SubThoughtAttributeKeys;
import io.casehub.neocortex.memory.experience.SubThoughtTypes;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.SubThoughtRef;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import io.casehub.neocortex.memory.inmem.InMemoryMemoryStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class SubThoughtConsolidationPhaseTest {

    private InMemoryMemoryStore memoryStore;
    private InMemoryMindMapStore mindMapStore;
    private SubThoughtConsolidationPhase phase;
    private static final String TENANT = "test-tenant";

    @BeforeEach
    void setUp() {
        memoryStore = new InMemoryMemoryStore(null);
        mindMapStore = new InMemoryMindMapStore();
        phase = new SubThoughtConsolidationPhase(memoryStore, mindMapStore, 3);
    }

    @Test
    void graduatesWhenThresholdCrossed() {
        for (int i = 0; i < 3; i++) {
            storeMemoryWithSubThought("mem-" + i, SubThoughtTypes.CAUSAL_INFERENCE,
                "Inference " + i, "Sarah");
        }

        phase.run(TENANT, List.of(SubgraphTypes.COGNITIVE));

        var nodes = mindMapStore.search(
            io.casehub.neocortex.mindmap.MindMapQuery.builder()
                .tenantId(TENANT).traits(java.util.Set.of("graduated-sub-thought")).build());
        assertThat(nodes).hasSize(1);
        var node = nodes.getFirst();
        assertThat(node.properties()).containsEntry("cognitiveKind", "causal-inference");
        assertThat(node.properties()).containsEntry("source-count", "3");
        assertThat(node.refs()).hasSize(3);
        assertThat(node.refs()).allMatch(r -> SubThoughtRef.SCHEME.equals(r.scheme()));
    }

    @Test
    void doesNotGraduateBelowThreshold() {
        for (int i = 0; i < 2; i++) {
            storeMemoryWithSubThought("mem-" + i, SubThoughtTypes.CAUSAL_INFERENCE,
                "Inference " + i, "Sarah");
        }

        phase.run(TENANT, List.of(SubgraphTypes.COGNITIVE));

        var nodes = mindMapStore.search(
            io.casehub.neocortex.mindmap.MindMapQuery.builder()
                .tenantId(TENANT).traits(java.util.Set.of("graduated-sub-thought")).build());
        assertThat(nodes).isEmpty();
    }

    @Test
    void skipsBiographicalImportMemories() {
        for (int i = 0; i < 3; i++) {
            var attrs = subThoughtAttrs(SubThoughtTypes.EVALUATIVE, "Eval " + i, "Place");
            attrs.put("provenance", "biographical-import");
            storeMemoryWithAttrs("mem-bio-" + i, attrs);
        }

        phase.run(TENANT, List.of(SubgraphTypes.COGNITIVE));

        var nodes = mindMapStore.search(
            io.casehub.neocortex.mindmap.MindMapQuery.builder()
                .tenantId(TENANT).traits(java.util.Set.of("graduated-sub-thought")).build());
        assertThat(nodes).isEmpty();
    }

    @Test
    void marksGraduatedSubThoughts() {
        for (int i = 0; i < 3; i++) {
            storeMemoryWithSubThought("mem-" + i, SubThoughtTypes.CONCERN,
                "Concern " + i, "Sarah");
        }

        phase.run(TENANT, List.of(SubgraphTypes.COGNITIVE));

        for (int i = 0; i < 3; i++) {
            var memories = memoryStore.query(
                io.casehub.neocortex.memory.MemoryQuery.of(
                    Subject.of("agent", "a1"), ExperienceEvents.DOMAIN, TENANT));
            var mem = memories.stream()
                .filter(m -> m.attributes().containsKey(SubThoughtAttributeKeys.graduated(0)))
                .toList();
            assertThat(mem).isNotEmpty();
        }
    }

    private void storeMemoryWithSubThought(String desc, String type, String text, String entity) {
        var attrs = subThoughtAttrs(type, text, entity);
        storeMemoryWithAttrs(desc, attrs);
    }

    private java.util.Map<String, String> subThoughtAttrs(String type, String text, String entity) {
        var attrs = new java.util.HashMap<String, String>();
        attrs.put("event-type", "observation");
        attrs.put(SubThoughtAttributeKeys.COUNT, "1");
        attrs.put(SubThoughtAttributeKeys.type(0), type);
        attrs.put(SubThoughtAttributeKeys.text(0), text);
        if (entity != null) attrs.put(SubThoughtAttributeKeys.entity(0), entity);
        return attrs;
    }

    private void storeMemoryWithAttrs(String desc, Map<String, String> attrs) {
        memoryStore.store(new MemoryInput(
            Subject.of("agent", "a1"), ExperienceEvents.DOMAIN, TENANT,
            null, desc, attrs, null, null, null, null, null, null));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SubThoughtConsolidationPhaseTest -am`
Expected: FAIL — `SubThoughtConsolidationPhase` does not exist

- [ ] **Step 3: Write SubThoughtConsolidationPhase implementation**

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.MemoryScanRequest;
import io.casehub.neocortex.memory.experience.ExperienceEvents;
import io.casehub.neocortex.memory.experience.SubThoughtAttributeKeys;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.NodeRef;
import io.casehub.neocortex.mindmap.SubThoughtRef;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.logging.Logger;

@ApplicationScoped
@Priority(16)
public class SubThoughtConsolidationPhase implements ConsolidationPhase {

    private static final Logger LOG = Logger.getLogger(SubThoughtConsolidationPhase.class.getName());
    private static final int DEFAULT_THRESHOLD = 3;
    private static final int MAX_PER_PASS = 50;

    private final CaseMemoryStore memoryStore;
    private final MindMapStore mindMapStore;
    private final int graduationThreshold;

    private final Map<EntityTypePair, List<SubThoughtSource>> accumulation = new HashMap<>();

    @Inject
    public SubThoughtConsolidationPhase(Instance<CaseMemoryStore> memoryStore,
                                         Instance<MindMapStore> mindMapStore) {
        this.memoryStore = memoryStore.isResolvable() ? memoryStore.get() : null;
        this.mindMapStore = mindMapStore.isResolvable() ? mindMapStore.get() : null;
        this.graduationThreshold = DEFAULT_THRESHOLD;
    }

    SubThoughtConsolidationPhase(CaseMemoryStore memoryStore,
                                  MindMapStore mindMapStore,
                                  int graduationThreshold) {
        this.memoryStore = memoryStore;
        this.mindMapStore = mindMapStore;
        this.graduationThreshold = graduationThreshold;
    }

    @Override
    public String name() { return "sub-thought-graduation"; }

    @Override
    public void beginTick() { /* accumulation persists across ticks */ }

    @Override
    public void run(String tenantId, List<String> subgraphPriority) {
        if (memoryStore == null || mindMapStore == null) return;

        var request = MemoryScanRequest.of(tenantId, ExperienceEvents.DOMAIN)
            .withAttributeFilter(SubThoughtAttributeKeys.COUNT, null)
            .withLimit(MAX_PER_PASS);

        List<Memory> memories = memoryStore.scan(request);

        for (Memory memory : memories) {
            String countStr = memory.attributes().get(SubThoughtAttributeKeys.COUNT);
            if (countStr == null) continue;
            if ("biographical-import".equals(memory.attributes().get("provenance"))) continue;

            int count = Integer.parseInt(countStr);
            for (int i = 0; i < count; i++) {
                if ("true".equals(memory.attributes().get(SubThoughtAttributeKeys.graduated(i)))) continue;

                String entity = memory.attributes().get(SubThoughtAttributeKeys.entity(i));
                String type = memory.attributes().get(SubThoughtAttributeKeys.type(i));
                if (entity == null || type == null) continue;

                var key = new EntityTypePair(entity, type);
                accumulation.computeIfAbsent(key, k -> new ArrayList<>())
                    .add(new SubThoughtSource(memory.memoryId(), i));
            }
        }

        var graduated = new ArrayList<EntityTypePair>();
        for (var entry : accumulation.entrySet()) {
            if (entry.getValue().size() >= graduationThreshold) {
                graduateSubThought(entry.getKey(), entry.getValue(), tenantId);
                graduated.add(entry.getKey());
            }
        }
        graduated.forEach(accumulation::remove);
    }

    private void graduateSubThought(EntityTypePair pair, List<SubThoughtSource> sources,
                                     String tenantId) {
        String subgraphId = SubgraphUtils.ensureSubgraph(
            mindMapStore, SubgraphTypes.COGNITIVE, tenantId);

        Set<NodeRef> refs = new HashSet<>();
        for (var source : sources) {
            refs.add(SubThoughtRef.of(source.memoryId(), source.subThoughtIndex()));
        }

        mindMapStore.addNode(
            NodeInput.of(pair.entity() + " — " + pair.type(), subgraphId)
                .withConfidence(Confidence.inferred(0.7, Instant.now()))
                .withProvenance("sub-thought-graduation")
                .withTraits(Set.of("graduated-sub-thought"))
                .withRefs(refs)
                .withProperties(Map.of(
                    "cognitiveKind", pair.type(),
                    "source-count", String.valueOf(sources.size()))),
            tenantId);

        for (var source : sources) {
            try {
                memoryStore.enrichAttributes(source.memoryId(),
                    Map.of(SubThoughtAttributeKeys.graduated(source.subThoughtIndex()), "true"),
                    tenantId);
            } catch (Exception e) {
                LOG.warning("Could not mark sub-thought graduated: " + source.memoryId()
                    + "#" + source.subThoughtIndex());
            }
        }
    }

    record EntityTypePair(String entity, String type) {}
    record SubThoughtSource(String memoryId, int subThoughtIndex) {}
}
```

Note: `SubgraphUtils` is an existing package-private utility in `mindmap-intelligence`. If it is not accessible from the consolidation package, inline the subgraph lookup.

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=SubThoughtConsolidationPhaseTest -am`
Expected: PASS — all 4 tests green

- [ ] **Step 5: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SubThoughtConsolidationPhase.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SubThoughtConsolidationPhaseTest.java
git commit -m "feat(#470): add SubThoughtConsolidationPhase for cross-memory graduation

Separate @Priority(16) ConsolidationPhase that accumulates (entity, type)
patterns across memories and graduates to COGNITIVE nodes with multi-NodeRef
traceability. Skips biographical-import provenance memories.

Refs #470"
```

---

## Batch 4: Biography import framework

### Task 5: Entry records + BiographyLoader + BiographyImportRunner

**Files:**
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyProfile.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyLoader.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyImportRunner.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BiographyTemplateTypes.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/CulturalContextEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/LifeEventEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PlaceEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ActivityEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ProjectEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/RelationshipEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BeliefEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/CurrentStateEntry.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/FormativeExperienceEntry.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/BiographyLoaderTest.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/BiographyImportRunnerTest.java`
- Test resources: `memory-seeding/src/test/resources/biography-test/`

**Interfaces:**
- Consumes: Jackson YAML, `CatalogueLoader` (for FormativeExperienceHandler reference only)
- Produces: `BiographyHandler` SPI (`Set<String> handledTypes()`, `void handle(BiographyProfile, String, String)`), `BiographyProfile` record, `BiographyLoader.loadAll(Path)`, `BiographyImportRunner.run(BiographyProfile, String, String)`, `BiographyTemplateTypes` constants (10 type strings + layer mapping), all entry records

- [ ] **Step 1: Write BiographyTemplateTypes constants**

```java
package io.casehub.neocortex.memory.seeding.biography;

import java.util.Map;

public final class BiographyTemplateTypes {
    public static final String CULTURAL_CONTEXT     = "cultural-context";
    public static final String FORMATIVE_EXPERIENCE = "formative-experience";
    public static final String LIFE_EVENT           = "life-event";
    public static final String PLACE                = "place";
    public static final String ACTIVITY             = "activity";
    public static final String PROJECT              = "project";
    public static final String RELATIONSHIP         = "relationship";
    public static final String GOAL                 = "goal";
    public static final String BELIEF               = "belief";
    public static final String CURRENT_STATE        = "current-state";

    private static final Map<String, Integer> LAYER_MAP = Map.of(
        CULTURAL_CONTEXT, 1,
        FORMATIVE_EXPERIENCE, 2,
        LIFE_EVENT, 4,
        PLACE, 4,
        ACTIVITY, 4,
        PROJECT, 4,
        RELATIONSHIP, 5,
        GOAL, 6,
        BELIEF, 6,
        CURRENT_STATE, 8
    );

    public static int layerFor(String type) {
        Integer layer = LAYER_MAP.get(type);
        if (layer == null) throw new IllegalArgumentException("Unknown template type: " + type);
        return layer;
    }

    private BiographyTemplateTypes() {}
}
```

- [ ] **Step 2: Write entry records**

Create each entry record with `@JsonIgnoreProperties(ignoreUnknown = true)` and `@JsonProperty` for snake_case. Example for `PlaceEntry`:

```java
package io.casehub.neocortex.memory.seeding.biography;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.util.List;
import java.util.Map;

@JsonIgnoreProperties(ignoreUnknown = true)
public record PlaceEntry(
    String id,
    @JsonProperty("source_ref") String sourceRef,
    @JsonProperty("confidence_origin") String confidenceOrigin,
    String name,
    Map<String, String> properties,
    PadValues pad,
    List<Association> associations
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Association(
        @JsonProperty("entity_ref") String entityRef,
        @JsonProperty("edge_type") String edgeType
    ) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record PadValues(Double pleasure, Double arousal, Double dominance) {}
}
```

Create analogous records for all 10 entry types following the YAML schemas from spec §3.2.1–3.2.10. Each record follows the same pattern: `@JsonIgnoreProperties`, `@JsonProperty` for snake_case fields, nested records for sub-structures.

- [ ] **Step 3: Write BiographyProfile record**

```java
package io.casehub.neocortex.memory.seeding.biography;

import java.util.List;

public record BiographyProfile(
    String agentId,
    String tenantId,
    List<CulturalContextEntry> culturalContexts,
    List<FormativeExperienceEntry> formativeExperiences,
    List<LifeEventEntry> lifeEvents,
    List<PlaceEntry> places,
    List<ActivityEntry> activities,
    List<ProjectEntry> projects,
    List<RelationshipEntry> relationships,
    List<GoalEntry> goals,
    List<BeliefEntry> beliefs,
    List<CurrentStateEntry> currentStates
) {
    public BiographyProfile {
        culturalContexts = culturalContexts != null ? List.copyOf(culturalContexts) : List.of();
        formativeExperiences = formativeExperiences != null ? List.copyOf(formativeExperiences) : List.of();
        lifeEvents = lifeEvents != null ? List.copyOf(lifeEvents) : List.of();
        places = places != null ? List.copyOf(places) : List.of();
        activities = activities != null ? List.copyOf(activities) : List.of();
        projects = projects != null ? List.copyOf(projects) : List.of();
        relationships = relationships != null ? List.copyOf(relationships) : List.of();
        goals = goals != null ? List.copyOf(goals) : List.of();
        beliefs = beliefs != null ? List.copyOf(beliefs) : List.of();
        currentStates = currentStates != null ? List.copyOf(currentStates) : List.of();
    }
}
```

- [ ] **Step 4: Write BiographyHandler SPI**

```java
package io.casehub.neocortex.memory.seeding.biography;

import java.util.Set;

public interface BiographyHandler {
    Set<String> handledTypes();
    void handle(BiographyProfile profile, String agentId, String tenantId);
}
```

- [ ] **Step 5: Write BiographyLoader**

```java
package io.casehub.neocortex.memory.seeding.biography;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.casehub.yaml.jackson.YamlMappers;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.stream.Stream;

public class BiographyLoader {

    private final ObjectMapper mapper = YamlMappers.create();

    public BiographyProfile loadAll(Path biographyDir, String agentId, String tenantId) {
        var culturalContexts = new ArrayList<CulturalContextEntry>();
        var formativeExperiences = new ArrayList<FormativeExperienceEntry>();
        var lifeEvents = new ArrayList<LifeEventEntry>();
        var places = new ArrayList<PlaceEntry>();
        var activities = new ArrayList<ActivityEntry>();
        var projects = new ArrayList<ProjectEntry>();
        var relationships = new ArrayList<RelationshipEntry>();
        var goals = new ArrayList<GoalEntry>();
        var beliefs = new ArrayList<BeliefEntry>();
        var currentStates = new ArrayList<CurrentStateEntry>();

        try (Stream<Path> files = Files.list(biographyDir)) {
            files.filter(p -> p.toString().endsWith(".yaml"))
                 .sorted()
                 .forEach(p -> loadFile(p, culturalContexts, formativeExperiences,
                     lifeEvents, places, activities, projects,
                     relationships, goals, beliefs, currentStates));
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to list biography directory " + biographyDir, e);
        }

        var profile = new BiographyProfile(agentId, tenantId,
            culturalContexts, formativeExperiences, lifeEvents, places,
            activities, projects, relationships, goals, beliefs, currentStates);

        validate(profile);
        return profile;
    }

    private void loadFile(Path file,
                          List<CulturalContextEntry> cc, List<FormativeExperienceEntry> fe,
                          List<LifeEventEntry> le, List<PlaceEntry> pl,
                          List<ActivityEntry> ac, List<ProjectEntry> pr,
                          List<RelationshipEntry> re, List<GoalEntry> go,
                          List<BeliefEntry> be, List<CurrentStateEntry> cs) {
        try {
            var header = mapper.readValue(file.toFile(), TypeHeader.class);
            if (header.type() == null) {
                throw new IllegalStateException("Missing 'type' field in " + file);
            }
            switch (header.type()) {
                case BiographyTemplateTypes.CULTURAL_CONTEXT ->
                    cc.addAll(mapper.readValue(file.toFile(), CulturalContextFile.class).entries());
                case BiographyTemplateTypes.FORMATIVE_EXPERIENCE ->
                    fe.addAll(mapper.readValue(file.toFile(), FormativeExperienceFile.class).entries());
                case BiographyTemplateTypes.LIFE_EVENT ->
                    le.addAll(mapper.readValue(file.toFile(), LifeEventFile.class).entries());
                case BiographyTemplateTypes.PLACE ->
                    pl.addAll(mapper.readValue(file.toFile(), PlaceFile.class).entries());
                case BiographyTemplateTypes.ACTIVITY ->
                    ac.addAll(mapper.readValue(file.toFile(), ActivityFile.class).entries());
                case BiographyTemplateTypes.PROJECT ->
                    pr.addAll(mapper.readValue(file.toFile(), ProjectFile.class).entries());
                case BiographyTemplateTypes.RELATIONSHIP ->
                    re.addAll(mapper.readValue(file.toFile(), RelationshipFile.class).entries());
                case BiographyTemplateTypes.GOAL ->
                    go.addAll(mapper.readValue(file.toFile(), GoalFile.class).entries());
                case BiographyTemplateTypes.BELIEF ->
                    be.addAll(mapper.readValue(file.toFile(), BeliefFile.class).entries());
                case BiographyTemplateTypes.CURRENT_STATE ->
                    cs.addAll(mapper.readValue(file.toFile(), CurrentStateFile.class).entries());
                default -> throw new IllegalStateException("Unknown type: " + header.type() + " in " + file);
            }
        } catch (IOException e) {
            throw new UncheckedIOException("Failed to load " + file, e);
        }
    }

    public void validate(BiographyProfile profile) {
        var ids = new HashSet<String>();
        // Validate ID uniqueness across all entry types
        validateIds(ids, profile.culturalContexts().stream().map(CulturalContextEntry::id).toList());
        validateIds(ids, profile.formativeExperiences().stream().map(FormativeExperienceEntry::id).toList());
        validateIds(ids, profile.lifeEvents().stream().map(LifeEventEntry::id).toList());
        validateIds(ids, profile.places().stream().map(PlaceEntry::id).toList());
        validateIds(ids, profile.activities().stream().map(ActivityEntry::id).toList());
        validateIds(ids, profile.projects().stream().map(ProjectEntry::id).toList());
        validateIds(ids, profile.relationships().stream().map(RelationshipEntry::id).toList());
        validateIds(ids, profile.goals().stream().map(GoalEntry::id).toList());
        validateIds(ids, profile.beliefs().stream().map(BeliefEntry::id).toList());
        validateIds(ids, profile.currentStates().stream().map(CurrentStateEntry::id).toList());
    }

    private void validateIds(HashSet<String> seen, List<String> newIds) {
        for (String id : newIds) {
            if (!seen.add(id)) {
                throw new IllegalStateException("Duplicate biography entry ID: " + id);
            }
        }
    }

    @JsonIgnoreProperties(ignoreUnknown = true)
    record TypeHeader(String type) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record CulturalContextFile(List<CulturalContextEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record FormativeExperienceFile(List<FormativeExperienceEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record LifeEventFile(List<LifeEventEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record PlaceFile(List<PlaceEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record ActivityFile(List<ActivityEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record ProjectFile(List<ProjectEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record RelationshipFile(List<RelationshipEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record GoalFile(List<GoalEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record BeliefFile(List<BeliefEntry> entries) {}
    @JsonIgnoreProperties(ignoreUnknown = true) record CurrentStateFile(List<CurrentStateEntry> entries) {}
}
```

- [ ] **Step 6: Write BiographyImportRunner**

```java
package io.casehub.neocortex.memory.seeding.biography;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@ApplicationScoped
public class BiographyImportRunner {

    private final List<BiographyHandler> handlers;
    private final Set<String> seededAgents = Collections.synchronizedSet(new HashSet<>());

    @Inject
    public BiographyImportRunner(Instance<BiographyHandler> handlers) {
        this.handlers = new ArrayList<>();
        handlers.forEach(this.handlers::add);
        this.handlers.sort(Comparator.comparingInt(h ->
            h.handledTypes().stream()
                .mapToInt(BiographyTemplateTypes::layerFor)
                .min().orElse(Integer.MAX_VALUE)));
    }

    BiographyImportRunner(List<BiographyHandler> handlers) {
        this.handlers = new ArrayList<>(handlers);
        this.handlers.sort(Comparator.comparingInt(h ->
            h.handledTypes().stream()
                .mapToInt(BiographyTemplateTypes::layerFor)
                .min().orElse(Integer.MAX_VALUE)));
    }

    public void run(BiographyProfile profile, String agentId, String tenantId) {
        if (!seededAgents.add(agentId)) {
            throw new IllegalStateException("Agent " + agentId + " already has biographical data");
        }

        for (BiographyHandler handler : handlers) {
            handler.handle(profile, agentId, tenantId);
        }
    }
}
```

- [ ] **Step 7: Write BiographyLoader test with YAML fixtures**

Create test YAML at `memory-seeding/src/test/resources/biography-test/places.yaml`:

```yaml
type: place
entries:
  - id: casa-azul
    name: "La Casa Azul"
    properties:
      address: "Londres 247, Coyoacán"
    pad:
      pleasure: 0.6
      arousal: 0.2
      dominance: 0.5
```

Test:

```java
package io.casehub.neocortex.memory.seeding.biography;

import org.junit.jupiter.api.Test;
import java.nio.file.Path;
import static org.assertj.core.api.Assertions.*;

class BiographyLoaderTest {

    @Test
    void loadsPlaceEntries() {
        var loader = new BiographyLoader();
        var profile = loader.loadAll(
            Path.of("src/test/resources/biography-test"), "agent-1", "tenant-1");
        assertThat(profile.places()).hasSize(1);
        assertThat(profile.places().getFirst().name()).isEqualTo("La Casa Azul");
        assertThat(profile.places().getFirst().pad().pleasure()).isEqualTo(0.6);
    }

    @Test
    void rejectsDuplicateIds() {
        // Create a temporary directory with duplicate IDs for this test
        assertThatThrownBy(() -> {
            var loader = new BiographyLoader();
            var dir = java.nio.file.Files.createTempDirectory("bio-dup");
            java.nio.file.Files.writeString(dir.resolve("a.yaml"),
                "type: place\nentries:\n  - id: dup\n    name: A\n");
            java.nio.file.Files.writeString(dir.resolve("b.yaml"),
                "type: place\nentries:\n  - id: dup\n    name: B\n");
            loader.loadAll(dir, "a1", "t1");
        }).isInstanceOf(IllegalStateException.class)
          .hasMessageContaining("Duplicate biography entry ID: dup");
    }
}
```

- [ ] **Step 8: Write BiographyImportRunner test**

```java
package io.casehub.neocortex.memory.seeding.biography;

import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import static org.assertj.core.api.Assertions.*;

class BiographyImportRunnerTest {

    @Test
    void handlersInvokedInLayerOrder() {
        var order = new AtomicInteger(0);
        var layer1Handler = new TestHandler(Set.of("cultural-context"), order, 0);
        var layer5Handler = new TestHandler(Set.of("relationship"), order, 0);
        var layer4Handler = new TestHandler(Set.of("place"), order, 0);

        var runner = new BiographyImportRunner(List.of(layer5Handler, layer1Handler, layer4Handler));
        runner.run(emptyProfile(), "agent-1", "tenant-1");

        assertThat(layer1Handler.invokedAt).isEqualTo(0);
        assertThat(layer4Handler.invokedAt).isEqualTo(1);
        assertThat(layer5Handler.invokedAt).isEqualTo(2);
    }

    @Test
    void rejectsDoubleSeedingSameAgent() {
        var runner = new BiographyImportRunner(List.of());
        runner.run(emptyProfile(), "agent-1", "tenant-1");
        assertThatThrownBy(() -> runner.run(emptyProfile(), "agent-1", "tenant-1"))
            .isInstanceOf(IllegalStateException.class)
            .hasMessageContaining("already has biographical data");
    }

    private BiographyProfile emptyProfile() {
        return new BiographyProfile("a1", "t1",
            List.of(), List.of(), List.of(), List.of(), List.of(),
            List.of(), List.of(), List.of(), List.of(), List.of());
    }

    static class TestHandler implements BiographyHandler {
        final Set<String> types;
        final AtomicInteger counter;
        int invokedAt;

        TestHandler(Set<String> types, AtomicInteger counter, int ignored) {
            this.types = types; this.counter = counter;
        }

        @Override public Set<String> handledTypes() { return types; }
        @Override public void handle(BiographyProfile p, String a, String t) {
            invokedAt = counter.getAndIncrement();
        }
    }
}
```

- [ ] **Step 9: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -am`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/resources/biography-test/
git commit -m "feat(#470): add biography import framework — entry records, loader, runner, handler SPI

BiographyLoader reads per-type YAML files, BiographyImportRunner dispatches
to BiographyHandler implementations in layer order with idempotency guard.
10 entry records for each template type.

Refs #470"
```

---

## Batch 5: Biography handlers

### Task 6: Layer 1-4 handlers

**Files:**
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/CulturalContextHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/FormativeExperienceHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/LifeEventHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PlaceHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ActivityHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ProjectHandler.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PlaceHandlerTest.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/LifeEventHandlerTest.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/ActivityHandlerTest.java`

**Interfaces:**
- Consumes: `BiographyHandler`, `BiographyProfile`, `MindMapStore.addNode(NodeInput, String)`, `MindMapStore.addEdge(EdgeInput, String)`, `MindMapStore.resolveNode(String, String, String)`, `CaseMemoryStore.store(MemoryInput)`, `SubThoughtAttributeKeys.*`, `BackstorySeeder.seed(BackstoryProfile)`
- Produces: 6 handler implementations. Each creates MindMap nodes and/or memory records with provenance properties.

- [ ] **Step 1: Write PlaceHandler test**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class PlaceHandlerTest {

    @Test
    void createsPlaceNodeWithProvenanceAndPad() {
        var store = new InMemoryMindMapStore();
        var handler = new PlaceHandler(store);

        var entry = new PlaceEntry("casa-azul", "source.md#casa", null,
            "La Casa Azul",
            Map.of("address", "Londres 247"),
            new PlaceEntry.PadValues(0.6, 0.2, 0.5),
            List.of());

        var profile = profileWith(List.of(entry));
        handler.handle(profile, "agent-1", "tenant-1");

        var nodes = store.search(io.casehub.neocortex.mindmap.MindMapQuery.builder()
            .tenantId("tenant-1").subgraph(SubgraphTypes.PLACE).build());
        assertThat(nodes).hasSize(1);
        var node = nodes.getFirst();
        assertThat(node.name()).isEqualTo("La Casa Azul");
        assertThat(node.pleasure()).isEqualTo(0.6);
        assertThat(node.properties()).containsEntry("provenance", "biographical-import");
        assertThat(node.properties()).containsEntry("template-ref", "places.yaml#casa-azul");
        assertThat(node.properties()).containsEntry("source-ref", "source.md#casa");
    }

    private BiographyProfile profileWith(List<PlaceEntry> places) {
        return new BiographyProfile("a1", "t1",
            List.of(), List.of(), List.of(), places, List.of(),
            List.of(), List.of(), List.of(), List.of(), List.of());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=PlaceHandlerTest -am`
Expected: FAIL

- [ ] **Step 3: Write PlaceHandler**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.cognitive.Confidence;
import io.casehub.neocortex.cognitive.ConfidenceOrigin;
import io.casehub.neocortex.mindmap.EdgeInput;
import io.casehub.neocortex.mindmap.MindMapStore;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.intelligence.SubgraphUtils;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;
import java.util.Set;

public class PlaceHandler implements BiographyHandler {

    private final MindMapStore store;

    public PlaceHandler(MindMapStore store) { this.store = store; }

    @Override public Set<String> handledTypes() { return Set.of(BiographyTemplateTypes.PLACE); }

    @Override
    public void handle(BiographyProfile profile, String agentId, String tenantId) {
        for (var entry : profile.places()) {
            String subgraphId = SubgraphUtils.ensureSubgraph(store, SubgraphTypes.PLACE, tenantId);

            var existing = store.resolveNode(entry.name(), subgraphId, tenantId);
            if (existing != null) continue;

            var props = new HashMap<String, String>();
            props.put("provenance", "biographical-import");
            props.put("template-ref", "places.yaml#" + entry.id());
            if (entry.sourceRef() != null) props.put("source-ref", entry.sourceRef());
            if (entry.properties() != null) props.putAll(entry.properties());

            var origin = entry.confidenceOrigin() != null
                ? ConfidenceOrigin.valueOf(entry.confidenceOrigin())
                : ConfidenceOrigin.STATED;

            var input = NodeInput.of(entry.name(), subgraphId)
                .withConfidence(Confidence.of(origin, 0.8, Instant.now()))
                .withProvenance("biographical-import")
                .withProperties(props);

            if (entry.pad() != null) {
                input = input.withPad(entry.pad().pleasure(), entry.pad().arousal(), entry.pad().dominance());
            }

            String nodeId = store.addNode(input, tenantId);

            if (entry.associations() != null) {
                for (var assoc : entry.associations()) {
                    String targetId = resolveOrCreate(assoc.entityRef(), subgraphId, tenantId);
                    store.addEdge(EdgeInput.of(nodeId, targetId, assoc.edgeType())
                        .withProvenance("biographical-import"), tenantId);
                }
            }
        }
    }

    private String resolveOrCreate(String name, String subgraphId, String tenantId) {
        var existing = store.resolveNode(name, subgraphId, tenantId);
        if (existing != null) return existing.id();
        return store.addNode(NodeInput.of(name, subgraphId).withProvenance("biographical-import"), tenantId);
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=PlaceHandlerTest -am`
Expected: PASS

- [ ] **Step 5: Write remaining layer 1-4 handlers**

Follow the same pattern for:
- `CulturalContextHandler` — creates nodes in CULTURAL subgraph with norms as properties
- `FormativeExperienceHandler` — wraps BackstorySeeder, converts entries to CatalogueSelection
- `LifeEventHandler` — stores via CaseMemoryStore.store() with sub-thought attributes (bypasses ExperienceRecorder)
- `ActivityHandler` — creates ACTIVITY nodes, links to place and participants via resolveOrCreate
- `ProjectHandler` — creates PROJECT nodes, links to activities via activity_refs

Each handler follows the PlaceHandler pattern: resolve or create subgraph, check idempotency via resolveNode, set provenance properties, handle PAD and associations.

- [ ] **Step 6: Write LifeEventHandler test**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.memory.MemoryInput;
import io.casehub.neocortex.memory.experience.SubThoughtAttributeKeys;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class LifeEventHandlerTest {

    @Test
    void storesWithSubThoughtAttributesAtomically() {
        var store = mock(CaseMemoryStore.class);
        when(store.store(any())).thenReturn("mem-1");
        var handler = new LifeEventHandler(store);

        var subThoughts = List.of(
            new LifeEventEntry.SubThought("affect-observation", "The isolation was profound."),
            new LifeEventEntry.SubThought("self-reflection", "First fracture between body and will.")
        );
        var entry = new LifeEventEntry("polio", "source.md#polio", null,
            "1913-01-01", "Contracted polio at age six.",
            new LifeEventEntry.PadValues(-0.6, 0.5, -0.7),
            subThoughts, List.of());

        var profile = profileWith(List.of(entry));
        handler.handle(profile, "agent-1", "tenant-1");

        var captor = ArgumentCaptor.forClass(MemoryInput.class);
        verify(store).store(captor.capture());

        var input = captor.getValue();
        assertThat(input.text()).isEqualTo("Contracted polio at age six.");
        assertThat(input.attributes()).containsEntry(SubThoughtAttributeKeys.COUNT, "2");
        assertThat(input.attributes()).containsEntry(SubThoughtAttributeKeys.type(0), "affect-observation");
        assertThat(input.attributes()).containsEntry(SubThoughtAttributeKeys.text(0), "The isolation was profound.");
        assertThat(input.attributes()).containsEntry("provenance", "biographical-import");
        assertThat(input.pleasure()).isEqualTo(-0.6);
    }

    private BiographyProfile profileWith(List<LifeEventEntry> events) {
        return new BiographyProfile("a1", "t1",
            List.of(), List.of(), events, List.of(), List.of(),
            List.of(), List.of(), List.of(), List.of(), List.of());
    }
}
```

- [ ] **Step 7: Run all handler tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -am`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/
git commit -m "feat(#470): add layer 1-4 biography handlers

CulturalContextHandler, FormativeExperienceHandler, LifeEventHandler,
PlaceHandler, ActivityHandler, ProjectHandler — all with provenance chain
and idempotency via resolveNode.

Refs #470"
```

---

### Task 7: Layer 5-8 handlers

**Files:**
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/RelationshipHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/BeliefHandler.java`
- Create: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/CurrentStateHandler.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/RelationshipHandlerTest.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/GoalHandlerTest.java`
- Test: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/CurrentStateHandlerTest.java`

**Interfaces:**
- Consumes: `BiographyHandler`, `MindMapStore`, `CaseMemoryStore`, `MoodEvents`, `SubgraphTypes.PERSON`, `SubgraphTypes.GOAL`, `SubgraphTypes.COGNITIVE`, `GoalVocabulary` edge types
- Produces: 4 handler implementations completing the biography import pipeline

- [ ] **Step 1: Write RelationshipHandler test**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.memory.CaseMemoryStore;
import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import java.util.Set;
import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;

class RelationshipHandlerTest {

    @Test
    void createsPersonNodeWithBdiAndAffect() {
        var store = new InMemoryMindMapStore();
        var memStore = mock(CaseMemoryStore.class);
        when(memStore.store(any())).thenReturn("mem-1");
        var handler = new RelationshipHandler(store, memStore);

        var entry = new RelationshipEntry("diego-rivera", null, null,
            "Diego Rivera", List.of("Personable"),
            new RelationshipEntry.BdiValues("Brilliant artist", "Mutual respect", "Maintain partnership"),
            new RelationshipEntry.AffectValues(new RelationshipEntry.PadValues(0.2, 0.7, -0.3)),
            new RelationshipEntry.DynamicsValues(0.4, "confrontational"),
            Map.of("relationship_type", "spouse"));

        handler.handle(profileWith(List.of(entry)), "agent-1", "tenant-1");

        var nodes = store.search(io.casehub.neocortex.mindmap.MindMapQuery.builder()
            .tenantId("tenant-1").subgraph(SubgraphTypes.PERSON).build());
        assertThat(nodes).hasSize(1);
        assertThat(nodes.getFirst().name()).isEqualTo("Diego Rivera");
        assertThat(nodes.getFirst().traits()).contains("Personable");
        assertThat(nodes.getFirst().pleasure()).isEqualTo(0.2);
    }

    private BiographyProfile profileWith(List<RelationshipEntry> rels) {
        return new BiographyProfile("a1", "t1",
            List.of(), List.of(), List.of(), List.of(), List.of(),
            List.of(), rels, List.of(), List.of(), List.of());
    }
}
```

- [ ] **Step 2: Write RelationshipHandler, GoalHandler, BeliefHandler, CurrentStateHandler**

Each follows the established pattern:
- `RelationshipHandler` — creates/enriches PERSON nodes with traits, BDI as properties, PAD, and dynamics. Stores BDI as a relationship memory.
- `GoalHandler` — creates GOAL nodes with tier and horizon properties, links sub-goals as child edges, links dependencies via GoalVocabulary edge types
- `BeliefHandler` — creates COGNITIVE subgraph nodes with cognitive_kind, links entity_refs
- `CurrentStateHandler` — stores MoodState via MoodEvents, stores recent context as memory

- [ ] **Step 3: Write GoalHandler test**

```java
package io.casehub.neocortex.memory.seeding.biography;

import io.casehub.neocortex.mindmap.SubgraphTypes;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.*;

class GoalHandlerTest {

    @Test
    void createsGoalNodeWithSubGoals() {
        var store = new InMemoryMindMapStore();
        var handler = new GoalHandler(store);

        var subGoal = new GoalEntry.SubGoal("intl-recognition", "STRATEGIC",
            "Gain recognition beyond Mexico");
        var dep = new GoalEntry.Dependency("self-portraits-series", "contributes-to");
        var entry = new GoalEntry("artistic-legacy", null, null,
            "Establish artistic legacy", "THEMATIC", "aspirational",
            List.of(dep),
            new GoalEntry.PadValues(0.5, 0.6, 0.7),
            List.of(subGoal));

        handler.handle(profileWith(List.of(entry)), "agent-1", "tenant-1");

        var nodes = store.search(io.casehub.neocortex.mindmap.MindMapQuery.builder()
            .tenantId("tenant-1").subgraph(SubgraphTypes.GOAL).build());
        assertThat(nodes).hasSizeGreaterThanOrEqualTo(1);
        var parent = nodes.stream().filter(n -> n.name().equals("Establish artistic legacy")).findFirst();
        assertThat(parent).isPresent();
        assertThat(parent.get().properties()).containsEntry("tier", "THEMATIC");
    }

    private BiographyProfile profileWith(List<GoalEntry> goals) {
        return new BiographyProfile("a1", "t1",
            List.of(), List.of(), List.of(), List.of(), List.of(),
            List.of(), List.of(), goals, List.of(), List.of());
    }
}
```

- [ ] **Step 4: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -am`
Expected: PASS

- [ ] **Step 5: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-api,memory-inmem,mindmap-api,mindmap-intelligence,memory-seeding -am`
Expected: PASS — all modules compile and pass tests

- [ ] **Step 6: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/ memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/
git commit -m "feat(#470): add layer 5-8 biography handlers

RelationshipHandler, GoalHandler, BeliefHandler, CurrentStateHandler —
completes the biographical import pipeline with full provenance chain.

Closes #470"
```

---

## References

- `specs/issue-470-sub-thought-bio-import/2026-10-07-sub-thought-bio-import-design.md` — design spec this plan implements
- `memory-api/.../ExperienceAttributeKeys.java` — attribute key pattern
- `memory-api/.../CaseMemoryStore.java` — SPI interface (enrichAttributes addition)
- `memory-api/.../DelegatingCaseMemoryStore.java` — delegation pattern
- `memory-api/.../MemoryCapability.java` — capability enum
- `mindmap-api/.../SubgraphTypes.java` — string constants pattern
- `mindmap-api/.../OverlayRef.java` — NodeRef convention pattern
- `mindmap-api/.../NodeRef.java` — cross-store reference record
- `mindmap-intelligence/.../CheckInService.java` — check-in entry point
- `mindmap-intelligence/.../ExtractionRequestedObserver.java` — async extraction pattern
- `mindmap-intelligence/.../ExtractionRequested.java` — CDI event record pattern
- `mindmap-intelligence/.../consolidation/ConsolidationPhase.java` — consolidation SPI
- `memory-seeding/.../BackstorySeeder.java` — existing seeding infrastructure
- `memory-seeding/.../CatalogueLoader.java` — existing loader (not reused)
- `memory-inmem/.../InMemoryMemoryStore.java` — in-memory backend
- GitHub #470 — feature specification
