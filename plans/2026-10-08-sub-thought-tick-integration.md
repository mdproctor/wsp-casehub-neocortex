# Sub-Thought Tick Lifecycle Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #478 — feat: integrate sub-thought decomposition into cognitive tick lifecycle
**Issue group:** #478

**Goal:** Wire sub-thought decomposition into the cognitive tick lifecycle so typed, entity-tagged reactions become the shared intermediate representation between raw experience and cognitive processing — feeding mental model BDI, drive modulation, CAPS classification, and prompt rendering.

**Architecture:** SubThoughtTickParticipant runs at FOUNDATION phase, extracting sub-thoughts via keyword matching + entity name cache (sync) and merging with LLM-enriched results (async cache). It pushes SubThoughtCue signals to MentalModelOrchestrator and exposes an accessor for DriveOrchestrator, CAPS decorator, and prompt section to pull from. SubThoughtExtractionObserver triggers async LLM extraction for all Observation/FormativeExperience events.

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI (ArC), ConcurrentHashMap for per-agent state

## Global Constraints

- Java 21 language features, run on Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`
- All new classes follow existing package conventions
- All CDI beans use constructor injection where possible
- Records are immutable — no setters
- SubThoughtTypes constants from memory-api (AFFECT_OBSERVATION, CAUSAL_INFERENCE, EVALUATIVE, INTENTION, SELF_REFLECTION, ASSOCIATION, CONCERN)
- Confidence: sync ≤ 0.5 (provisional), async = LLM-assigned, VerbalCue heuristic = 0.8

---

## Batch 1: API Foundation — value types and signal variant

### Task 1: SubThought value types + SubThoughtCue signal variant

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/subthought/SubThought.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtResult.java`
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughts.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalStateSignal.java:8` — add SubThoughtCue variant
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtAttributeKeys.java:3` — add confidence(int)
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java:3` — add subThoughtsEnabled
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/drive/DriveConfig.java:7` — add subThoughtModulationStrength
- Test: `cognition-api/src/test/java/io/casehub/neocortex/cognition/subthought/SubThoughtsTest.java`

**Interfaces:**
- Produces: `SubThought(String type, String text, @Nullable String entity, double confidence, Source source)` with `enum Source { SYNC, ASYNC }`
- Produces: `SubThoughtResult(List<SubThought> subThoughts, String observationHash)` with `EMPTY` constant
- Produces: `SubThoughts.extract(Memory)`, `SubThoughts.merge(List, List)`, `SubThoughts.ofType(List, String)`, `SubThoughts.forEntity(List, String)`
- Produces: `MentalStateSignal.SubThoughtCue(String subThoughtType, String content, String entity, double confidence)`
- Produces: `SubThoughtAttributeKeys.confidence(int index)` → `"sub-thought-N-confidence"`
- Produces: `CognitionConfig.subThoughtsEnabled()` (default true)
- Produces: `DriveConfig.subThoughtModulationStrength()` (default 0.6)

- [ ] **Step 1: Write tests for SubThought record**

```java
package io.casehub.neocortex.cognition.subthought;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class SubThoughtsTest {

    @Test
    void subThoughtRecordValidatesType() {
        var st = new SubThought("affect-observation", "she seemed sad", "Sarah", 0.5, SubThought.Source.SYNC);
        assertEquals("affect-observation", st.type());
        assertEquals("she seemed sad", st.text());
        assertEquals("Sarah", st.entity());
        assertEquals(0.5, st.confidence());
        assertEquals(SubThought.Source.SYNC, st.source());
    }

    @Test
    void subThoughtAllowsNullEntity() {
        var st = new SubThought("intention", "should go there", null, 0.5, SubThought.Source.SYNC);
        assertNull(st.entity());
    }

    @Test
    void subThoughtResultEmptyConstant() {
        assertNotNull(SubThoughtResult.EMPTY);
        assertTrue(SubThoughtResult.EMPTY.subThoughts().isEmpty());
        assertEquals("", SubThoughtResult.EMPTY.observationHash());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition-api -Dtest=SubThoughtsTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — SubThought class does not exist

- [ ] **Step 3: Create SubThought record**

Use `ide_create_file` to create `cognition-api/src/main/java/io/casehub/neocortex/cognition/subthought/SubThought.java`:

```java
package io.casehub.neocortex.cognition.subthought;

import jakarta.annotation.Nullable;

public record SubThought(
    String type,
    String text,
    @Nullable String entity,
    double confidence,
    Source source
) {
    public enum Source { SYNC, ASYNC }

    public SubThought {
        if (type == null || type.isBlank()) throw new IllegalArgumentException("type required");
        if (text == null || text.isBlank()) throw new IllegalArgumentException("text required");
        if (confidence < 0.0 || confidence > 1.0) throw new IllegalArgumentException("confidence must be [0, 1]");
    }
}
```

- [ ] **Step 4: Create SubThoughtResult record**

Use `ide_create_file` to create `cognition-api/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtResult.java`:

```java
package io.casehub.neocortex.cognition.subthought;

import java.util.List;

public record SubThoughtResult(
    List<SubThought> subThoughts,
    String observationHash
) {
    public static final SubThoughtResult EMPTY = new SubThoughtResult(List.of(), "");

    public SubThoughtResult {
        subThoughts = List.copyOf(subThoughts);
    }

    public boolean isEmpty() {
        return subThoughts.isEmpty();
    }
}
```

- [ ] **Step 5: Run the SubThought/SubThoughtResult tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition-api -Dtest=SubThoughtsTest`
Expected: PASS

- [ ] **Step 6: Write tests for SubThoughts utility**

Add to `SubThoughtsTest.java`:

```java
@Test
void mergePrefersSyncWhenNoOverlap() {
    var sync = List.of(new SubThought("intention", "should go", null, 0.5, SubThought.Source.SYNC));
    var async = List.of(new SubThought("concern", "worry about her", "Sarah", 0.8, SubThought.Source.ASYNC));
    var merged = SubThoughts.merge(sync, async);
    assertEquals(2, merged.size());
}

@Test
void mergeAsyncWinsOnOverlap() {
    var sync = List.of(new SubThought("evaluative", "the food was good", null, 0.5, SubThought.Source.SYNC));
    var async = List.of(new SubThought("affect-observation", "the food was good", "restaurant", 0.8, SubThought.Source.ASYNC));
    var merged = SubThoughts.merge(sync, async);
    assertEquals(1, merged.size());
    assertEquals(SubThought.Source.ASYNC, merged.getFirst().source());
    assertEquals("affect-observation", merged.getFirst().type());
}

@Test
void ofTypeFilters() {
    var list = List.of(
        new SubThought("concern", "worried", null, 0.5, SubThought.Source.SYNC),
        new SubThought("intention", "should go", null, 0.5, SubThought.Source.SYNC)
    );
    assertEquals(1, SubThoughts.ofType(list, "concern").size());
}

@Test
void forEntityFilters() {
    var list = List.of(
        new SubThought("concern", "worried about her", "Sarah", 0.5, SubThought.Source.SYNC),
        new SubThought("intention", "should go", null, 0.5, SubThought.Source.SYNC)
    );
    assertEquals(1, SubThoughts.forEntity(list, "Sarah").size());
    assertEquals(0, SubThoughts.forEntity(list, "Tom").size());
}
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition-api -Dtest=SubThoughtsTest`
Expected: FAIL — SubThoughts class does not exist

- [ ] **Step 8: Create SubThoughts utility**

Use `ide_create_file` to create `cognition-api/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughts.java`:

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.memory.Memory;
import io.casehub.neocortex.memory.experience.SubThoughtAttributeKeys;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class SubThoughts {

    private SubThoughts() {}

    public static List<SubThought> extract(Memory memory) {
        var attrs = memory.attributes();
        var countStr = attrs.get(SubThoughtAttributeKeys.COUNT);
        if (countStr == null) return List.of();
        int count;
        try { count = Integer.parseInt(countStr); } catch (NumberFormatException e) { return List.of(); }
        var result = new ArrayList<SubThought>(count);
        for (int i = 0; i < count; i++) {
            var type = attrs.get(SubThoughtAttributeKeys.type(i));
            var text = attrs.get(SubThoughtAttributeKeys.text(i));
            if (type == null || text == null) continue;
            var entity = attrs.get(SubThoughtAttributeKeys.entity(i));
            var confStr = attrs.get(SubThoughtAttributeKeys.confidence(i));
            double confidence = confStr != null ? Double.parseDouble(confStr) : 0.8;
            result.add(new SubThought(type, text, entity, confidence, SubThought.Source.ASYNC));
        }
        return List.copyOf(result);
    }

    public static List<SubThought> merge(List<SubThought> sync, List<SubThought> async) {
        Map<String, SubThought> byText = new LinkedHashMap<>();
        for (var st : sync) {
            byText.put(normalizeText(st.text()), st);
        }
        for (var st : async) {
            byText.put(normalizeText(st.text()), st);
        }
        return List.copyOf(byText.values());
    }

    public static List<SubThought> ofType(List<SubThought> subThoughts, String type) {
        return subThoughts.stream().filter(st -> type.equals(st.type())).toList();
    }

    public static List<SubThought> forEntity(List<SubThought> subThoughts, String entity) {
        return subThoughts.stream().filter(st -> entity.equals(st.entity())).toList();
    }

    private static String normalizeText(String text) {
        return text.strip().replaceAll("\\s+", " ").toLowerCase();
    }
}
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition-api -Dtest=SubThoughtsTest`
Expected: PASS

- [ ] **Step 10: Add SubThoughtCue to MentalStateSignal sealed hierarchy**

Modify `cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalStateSignal.java`. Add new record variant inside the sealed interface:

```java
record SubThoughtCue(String subThoughtType, String content, String entity, double confidence)
        implements MentalStateSignal {}
```

The `content` field name satisfies the `MentalStateSignal.content()` contract used by `MentalModelOrchestrator.record()` at line 76: `state.appendSignal(signal.content())`.

- [ ] **Step 11: Add confidence to SubThoughtAttributeKeys**

Modify `memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtAttributeKeys.java`. Add method:

```java
public static String confidence(int index) {
    return "sub-thought-" + index + "-confidence";
}
```

- [ ] **Step 12: Add subThoughtsEnabled to CognitionConfig**

Modify `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java`. Add boolean field `subThoughtsEnabled` (23rd field, before appraisalEnabled). Update `all()` and `none()` factories. Update `with()` switch.

- [ ] **Step 13: Add subThoughtModulationStrength to DriveConfig**

Modify `cognition-api/src/main/java/io/casehub/neocortex/cognition/drive/DriveConfig.java`. Add `double subThoughtModulationStrength` field (12th field). Update `defaults()` to include `0.6` for the new field.

- [ ] **Step 14: Run full cognition-api tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition-api`
Expected: PASS (may need to fix CognitionConfig constructor call sites in test code)

- [ ] **Step 15: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/subthought/ cognition-api/src/test/java/io/casehub/neocortex/cognition/subthought/ cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalStateSignal.java cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java cognition-api/src/main/java/io/casehub/neocortex/cognition/drive/DriveConfig.java memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtAttributeKeys.java
git commit -m "feat(#478): add SubThought value types, SubThoughtCue signal variant, config fields

Refs #478"
```

---

## Batch 2: Core Tick Integration — extraction + participant + wiring

### Task 2: RuleBasedSubThoughtExtractor

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/RuleBasedSubThoughtExtractor.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/subthought/RuleBasedSubThoughtExtractorTest.java`

**Interfaces:**
- Consumes: `SubThought(type, text, entity, confidence, source)` from Task 1
- Consumes: `SubThoughtTypes` constants from memory-api
- Produces: `RuleBasedSubThoughtExtractor.extract(String observation, String agentId, String tenantId)` → `List<SubThought>`
- Produces: `RuleBasedSubThoughtExtractor.refreshEntityCache(String tenantId, Set<String> names)`

- [ ] **Step 1: Write tests for keyword extraction**

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.memory.experience.SubThoughtTypes;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import java.util.Set;
import static org.junit.jupiter.api.Assertions.*;

class RuleBasedSubThoughtExtractorTest {

    private RuleBasedSubThoughtExtractor extractor;

    @BeforeEach
    void setUp() {
        extractor = new RuleBasedSubThoughtExtractor();
    }

    @Test
    void extractsAffectObservation() {
        var results = extractor.extract("Sarah seemed really upset today.", "agent1", "tenant1");
        assertEquals(1, results.size());
        assertEquals(SubThoughtTypes.AFFECT_OBSERVATION, results.getFirst().type());
        assertEquals(SubThought.Source.SYNC, results.getFirst().source());
        assertEquals(0.5, results.getFirst().confidence());
    }

    @Test
    void extractsCausalInference() {
        var results = extractor.extract("She is stressed because of the promotion.", "agent1", "tenant1");
        assertEquals(1, results.size());
        assertEquals(SubThoughtTypes.CAUSAL_INFERENCE, results.getFirst().type());
    }

    @Test
    void extractsIntention() {
        var results = extractor.extract("I should bring David here next time.", "agent1", "tenant1");
        assertEquals(1, results.size());
        assertEquals(SubThoughtTypes.INTENTION, results.getFirst().type());
    }

    @Test
    void extractsConcern() {
        var results = extractor.extract("I worry she is not coping well.", "agent1", "tenant1");
        assertEquals(1, results.size());
        assertEquals(SubThoughtTypes.CONCERN, results.getFirst().type());
    }

    @Test
    void extractsMultipleSentences() {
        var results = extractor.extract("Sarah seemed sad. I worry about her. The food was excellent.", "agent1", "tenant1");
        assertEquals(3, results.size());
    }

    @Test
    void skipsUnmatchedSentences() {
        var results = extractor.extract("We went to the park. The weather was nice.", "agent1", "tenant1");
        assertTrue(results.isEmpty());
    }

    @Test
    void entityNameMatching() {
        extractor.refreshEntityCache("tenant1", Set.of("Sarah", "David"));
        var results = extractor.extract("Sarah seemed upset.", "agent1", "tenant1");
        assertEquals(1, results.size());
        assertEquals("Sarah", results.getFirst().entity());
    }

    @Test
    void entityMatchingCaseInsensitive() {
        extractor.refreshEntityCache("tenant1", Set.of("Sarah"));
        var results = extractor.extract("I think sarah seemed upset.", "agent1", "tenant1");
        assertEquals("Sarah", results.getFirst().entity());
    }

    @Test
    void noEntityWhenCacheEmpty() {
        var results = extractor.extract("Sarah seemed upset.", "agent1", "tenant1");
        assertNull(results.getFirst().entity());
    }

    @Test
    void emptyObservationReturnsEmpty() {
        assertTrue(extractor.extract("", "agent1", "tenant1").isEmpty());
        assertTrue(extractor.extract(null, "agent1", "tenant1").isEmpty());
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition -Dtest=RuleBasedSubThoughtExtractorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure

- [ ] **Step 3: Implement RuleBasedSubThoughtExtractor**

Use `ide_create_file` to create `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/RuleBasedSubThoughtExtractor.java`:

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.memory.experience.SubThoughtTypes;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.regex.Pattern;

@ApplicationScoped
public class RuleBasedSubThoughtExtractor {

    private static final Map<String, List<String>> KEYWORD_SETS = Map.of(
        SubThoughtTypes.AFFECT_OBSERVATION, List.of("felt", "seemed", "appeared", "looked", "sounded", "happy", "sad", "anxious", "distressed", "upset", "worried", "cheerful", "tense", "relaxed", "frustrated"),
        SubThoughtTypes.CAUSAL_INFERENCE, List.of("because", "since", "caused", "due to", "reason", "therefore", "so that", "resulted in", "led to", "as a result", "explains why"),
        SubThoughtTypes.INTENTION, List.of("should", "plan to", "going to", "need to", "want to", "intend", "must", "ought to", "let's", "i'll"),
        SubThoughtTypes.SELF_REFLECTION, List.of("i feel", "i think", "i wonder", "i notice", "i realize", "it occurs to me", "looking back", "on reflection"),
        SubThoughtTypes.EVALUATIVE, List.of("good", "bad", "excellent", "terrible", "impressive", "disappointing", "wonderful", "awful", "great", "poor", "amazing", "mediocre"),
        SubThoughtTypes.ASSOCIATION, List.of("reminds me", "similar to", "like when", "just like", "connects to", "makes me think of", "brings to mind"),
        SubThoughtTypes.CONCERN, List.of("worry", "concerned", "afraid", "fear", "anxious about", "troubled by", "uneasy", "dread", "scared")
    );

    private static final Pattern SENTENCE_SPLIT = Pattern.compile("(?<=[.!?])\\s+");

    private final ConcurrentHashMap<String, Set<String>> entityCache = new ConcurrentHashMap<>();

    public List<SubThought> extract(String observation, String agentId, String tenantId) {
        if (observation == null || observation.isBlank()) return List.of();

        String[] sentences = SENTENCE_SPLIT.split(observation);
        var result = new ArrayList<SubThought>();
        Set<String> entities = entityCache.get(tenantId);

        for (String sentence : sentences) {
            String trimmed = sentence.strip();
            if (trimmed.isEmpty()) continue;
            String lower = trimmed.toLowerCase(Locale.ROOT);

            String bestType = null;
            int bestCount = 0;
            for (var entry : KEYWORD_SETS.entrySet()) {
                int count = countMatches(lower, entry.getValue());
                if (count > bestCount) {
                    bestCount = count;
                    bestType = entry.getKey();
                }
            }

            if (bestType != null) {
                String entity = findEntity(trimmed, entities);
                result.add(new SubThought(bestType, trimmed, entity, 0.5, SubThought.Source.SYNC));
            }
        }
        return List.copyOf(result);
    }

    public void refreshEntityCache(String tenantId, Set<String> names) {
        entityCache.put(tenantId, Set.copyOf(names));
    }

    private int countMatches(String lower, List<String> keywords) {
        int count = 0;
        for (String kw : keywords) {
            if (containsWord(lower, kw)) count++;
        }
        return count;
    }

    private boolean containsWord(String text, String keyword) {
        int idx = text.indexOf(keyword);
        if (idx < 0) return false;
        boolean startOk = idx == 0 || !Character.isLetterOrDigit(text.charAt(idx - 1));
        int end = idx + keyword.length();
        boolean endOk = end >= text.length() || !Character.isLetterOrDigit(text.charAt(end));
        return startOk && endOk;
    }

    private String findEntity(String sentence, Set<String> entities) {
        if (entities == null || entities.isEmpty()) return null;
        String lower = sentence.toLowerCase(Locale.ROOT);
        for (String entity : entities) {
            if (containsWord(lower, entity.toLowerCase(Locale.ROOT))) {
                return entity;
            }
        }
        return null;
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition -Dtest=RuleBasedSubThoughtExtractorTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/subthought/RuleBasedSubThoughtExtractor.java cognition/src/test/java/io/casehub/neocortex/cognition/subthought/RuleBasedSubThoughtExtractorTest.java
git commit -m "feat(#478): add RuleBasedSubThoughtExtractor — keyword + entity cache sync extraction

Refs #478"
```

### Task 3: SubThoughtTickParticipant + CognitionCore wiring

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtTickParticipant.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java:70` — add configureSubThoughts(), register FOUNDATION participant
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java:32` — add producer
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtsEnriched.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/subthought/SubThoughtTickParticipantTest.java`

**Interfaces:**
- Consumes: `RuleBasedSubThoughtExtractor.extract()` from Task 2
- Consumes: `SubThought`, `SubThoughtResult`, `SubThoughts.merge()` from Task 1
- Consumes: `MentalStateSignal.SubThoughtCue` from Task 1
- Consumes: `SubjectResolver.relevantSubjects(agentId, tenantId)` → `Set<String>`
- Consumes: `MentalModelOrchestrator.record(MentalStateSignal, agentId, subjectId, tenantId)`
- Produces: `SubThoughtTickParticipant.currentSubThoughts(String agentId, String tenantId)` → `SubThoughtResult`
- Produces: `CognitionCore.configureSubThoughts(SubThoughtTickParticipant)`
- Produces: `SubThoughtsEnriched(String memoryId, String agentId, String tenantId, List<ParsedSubThought> subThoughts)` CDI event

- [ ] **Step 1: Create SubThoughtsEnriched CDI event record**

Use `ide_create_file` to create `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtsEnriched.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.List;

public record SubThoughtsEnriched(
    String memoryId,
    String agentId,
    String tenantId,
    List<SubThoughtExtractor.ParsedSubThought> subThoughts
) {}
```

- [ ] **Step 2: Write tests for SubThoughtTickParticipant**

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.cognition.core.CognitionTickContext;
import io.casehub.neocortex.cognition.mentalmodel.MentalModelOrchestrator;
import io.casehub.neocortex.cognition.mentalmodel.MentalStateSignal;
import io.casehub.neocortex.cognition.core.SubjectResolver;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class SubThoughtTickParticipantTest {

    private RuleBasedSubThoughtExtractor extractor;
    private MentalModelOrchestrator mentalModel;
    private SubjectResolver resolver;
    private SubThoughtTickParticipant participant;

    @BeforeEach
    void setUp() {
        extractor = new RuleBasedSubThoughtExtractor();
        mentalModel = mock(MentalModelOrchestrator.class);
        resolver = (agentId, tenantId) -> Set.of("Sarah");
        participant = new SubThoughtTickParticipant(extractor, mentalModel, resolver);
        extractor.refreshEntityCache("t1", Set.of("Sarah"));
    }

    @Test
    void tickExtractsAndStores() {
        var context = new CognitionTickContext("agent1", "t1", null, resolver, "Sarah seemed upset.", null);
        participant.tick(context);

        var result = participant.currentSubThoughts("agent1", "t1");
        assertFalse(result.isEmpty());
        assertEquals(1, result.subThoughts().size());
        assertEquals("Sarah", result.subThoughts().getFirst().entity());
    }

    @Test
    void tickPushesSubThoughtCueToMentalModel() {
        var context = new CognitionTickContext("agent1", "t1", null, resolver, "Sarah seemed upset.", null);
        participant.tick(context);

        verify(mentalModel).record(
            argThat(signal -> signal instanceof MentalStateSignal.SubThoughtCue stc
                    && "Sarah".equals(stc.entity())),
            eq("agent1"), eq("Sarah"), eq("t1")
        );
    }

    @Test
    void tickSkipsNullObservation() {
        var context = new CognitionTickContext("agent1", "t1", null, resolver, null, null);
        participant.tick(context);

        var result = participant.currentSubThoughts("agent1", "t1");
        assertTrue(result == null || result.isEmpty());
        verifyNoInteractions(mentalModel);
    }

    @Test
    void tickSkipsMentalModelPushForNonSubjects() {
        resolver = (agentId, tenantId) -> Set.of("Tom");
        participant = new SubThoughtTickParticipant(extractor, mentalModel, resolver);

        var context = new CognitionTickContext("agent1", "t1", null, resolver, "Sarah seemed upset.", null);
        participant.tick(context);

        verifyNoInteractions(mentalModel);
        var result = participant.currentSubThoughts("agent1", "t1");
        assertFalse(result.isEmpty());
    }

    @Test
    void currentSubThoughtsReturnsEmptyForUnknownAgent() {
        var result = participant.currentSubThoughts("unknown", "t1");
        assertTrue(result == null || result.isEmpty());
    }
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition -Dtest=SubThoughtTickParticipantTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure

- [ ] **Step 4: Implement SubThoughtTickParticipant**

Use `ide_create_file` to create `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtTickParticipant.java`:

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.cognition.core.CognitionTickContext;
import io.casehub.neocortex.cognition.core.CognitionTickParticipant;
import io.casehub.neocortex.cognition.core.SubjectResolver;
import io.casehub.neocortex.cognition.mentalmodel.MentalModelOrchestrator;
import io.casehub.neocortex.cognition.mentalmodel.MentalStateSignal;
import io.casehub.neocortex.mindmap.intelligence.SubThoughtsEnriched;
import jakarta.annotation.Nullable;
import jakarta.enterprise.event.Observes;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

public class SubThoughtTickParticipant implements CognitionTickParticipant {

    private static final Duration ASYNC_CACHE_TTL = Duration.ofMinutes(5);

    private final RuleBasedSubThoughtExtractor extractor;
    private final @Nullable MentalModelOrchestrator mentalModel;
    private final @Nullable SubjectResolver resolver;

    private final ConcurrentHashMap<String, SubThoughtResult> state = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, AsyncCacheEntry> asyncCache = new ConcurrentHashMap<>();

    public SubThoughtTickParticipant(
            RuleBasedSubThoughtExtractor extractor,
            @Nullable MentalModelOrchestrator mentalModel,
            @Nullable SubjectResolver resolver) {
        this.extractor = extractor;
        this.mentalModel = mentalModel;
        this.resolver = resolver;
    }

    @Override
    public void tick(CognitionTickContext context) {
        var observation = context.observation();
        if (observation == null || observation.isBlank()) return;

        var agentId = context.agentId();
        var tenantId = context.tenantId();
        var key = agentId + ":" + tenantId;

        List<SubThought> sync = extractor.extract(observation, agentId, tenantId);

        var asyncEntry = asyncCache.get(key);
        List<SubThought> async = (asyncEntry != null && !asyncEntry.isExpired())
                ? asyncEntry.subThoughts : List.of();

        List<SubThought> merged = SubThoughts.merge(sync, async);
        String hash = sha256(observation);
        state.put(key, new SubThoughtResult(merged, hash));

        pushToMentalModel(merged, agentId, tenantId);
    }

    public @Nullable SubThoughtResult currentSubThoughts(String agentId, String tenantId) {
        return state.get(agentId + ":" + tenantId);
    }

    void onSubThoughtsEnriched(@Observes SubThoughtsEnriched event) {
        var enriched = event.subThoughts().stream()
                .map(p -> new SubThought(p.type(), p.text(), p.entity(),
                        0.8, SubThought.Source.ASYNC))
                .toList();
        asyncCache.put(event.agentId() + ":" + event.tenantId(),
                new AsyncCacheEntry(enriched, Instant.now()));
    }

    private void pushToMentalModel(List<SubThought> subThoughts, String agentId, String tenantId) {
        if (mentalModel == null || resolver == null) return;
        Set<String> subjects = resolver.relevantSubjects(agentId, tenantId);
        for (var st : subThoughts) {
            if (st.entity() != null && subjects.contains(st.entity())) {
                mentalModel.record(
                    new MentalStateSignal.SubThoughtCue(st.type(), st.text(), st.entity(), st.confidence()),
                    agentId, st.entity(), tenantId
                );
            }
        }
    }

    private static String sha256(String input) {
        try {
            var digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(input.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new AssertionError("SHA-256 not available", e);
        }
    }

    private record AsyncCacheEntry(List<SubThought> subThoughts, Instant cachedAt) {
        boolean isExpired() {
            return Duration.between(cachedAt, Instant.now()).compareTo(ASYNC_CACHE_TTL) > 0;
        }
    }
}
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition -Dtest=SubThoughtTickParticipantTest`
Expected: PASS

- [ ] **Step 6: Wire into CognitionCore**

Modify `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java`:

Add field near line 122 (after gutFeelingParticipant):
```java
private SubThoughtTickParticipant subThoughtParticipant;
```

Add method near line 590 (after configureGutFeeling):
```java
public void configureSubThoughts(SubThoughtTickParticipant participant) {
    this.subThoughtParticipant = participant;
    addParticipant(CognitionPhase.FOUNDATION, participant);
    if (drives != null) {
        drives.setSubThoughtParticipant(participant);
    }
}
```

Add to `promptSections()` near line 520 (after MentalModelPromptSection, before StrategyPromptSection):
```java
if (config.subThoughtsEnabled() && subThoughtParticipant != null) {
    sections.add(new SubThoughtPromptSection(subThoughtParticipant));
}
```

- [ ] **Step 7: Add SubThoughtTickParticipant producer to CognitionDefaultBeans**

Modify `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java`. Add producer method:

```java
@Produces @DefaultBean @Singleton
SubThoughtTickParticipant subThoughtTickParticipant(
        RuleBasedSubThoughtExtractor extractor,
        Instance<MentalModelOrchestrator> mentalModel,
        Instance<SubjectResolver> resolver) {
    return new SubThoughtTickParticipant(
        extractor,
        mentalModel.isResolvable() ? mentalModel.get() : null,
        resolver.isResolvable() ? resolver.get() : null
    );
}
```

- [ ] **Step 8: Run cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition`
Expected: PASS (SubThoughtPromptSection not yet created — will be a forward reference that compiles but isn't instantiated until Task 6 in Batch 3. Add the import but gate on the class existing. If it fails, comment out the promptSections line and add a TODO — Task 6 will uncomment.)

- [ ] **Step 9: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtTickParticipant.java cognition/src/test/java/io/casehub/neocortex/cognition/subthought/SubThoughtTickParticipantTest.java cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtsEnriched.java
git commit -m "feat(#478): add SubThoughtTickParticipant + CognitionCore FOUNDATION wiring

Refs #478"
```

---

## Batch 3: Downstream Consumers — drives, mental model, prompt

### Task 4: SubThoughtModulation + DriveComposer integration

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtModulation.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/ModulationLayer.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveComposer.java:12` — add ModulationLayer parameter
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java:20` — add setSubThoughtParticipant(), read sub-thoughts in tick()
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/subthought/SubThoughtModulationTest.java`

**Interfaces:**
- Consumes: `SubThoughtResult`, `SubThought`, `SubThoughts.ofType()` from Task 1
- Consumes: `SubThoughtTickParticipant.currentSubThoughts()` from Task 3
- Consumes: `DriveAxis` enum (CURIOSITY, COMPETENCE, AFFILIATION, AUTONOMY)
- Consumes: `DriveConfig.subThoughtModulationStrength()` from Task 1
- Produces: `SubThoughtModulation.compute(SubThoughtResult)` → `Map<DriveAxis, Double>`
- Produces: `ModulationLayer(Map<DriveAxis, Double> modulation, double strength, String source)`
- Produces: `DriveOrchestrator.setSubThoughtParticipant(SubThoughtTickParticipant)`

- [ ] **Step 1: Write tests for SubThoughtModulation**

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.cognition.drive.DriveAxis;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class SubThoughtModulationTest {

    @Test
    void concernBoostsAffiliation() {
        var result = new SubThoughtResult(List.of(
            new SubThought("concern", "worried", null, 0.5, SubThought.Source.SYNC)
        ), "hash");
        var mod = SubThoughtModulation.compute(result);
        assertTrue(mod.get(DriveAxis.AFFILIATION) > 0.0);
    }

    @Test
    void intentionBoostsCompetenceAndAutonomy() {
        var result = new SubThoughtResult(List.of(
            new SubThought("intention", "should do it", null, 0.5, SubThought.Source.SYNC)
        ), "hash");
        var mod = SubThoughtModulation.compute(result);
        assertTrue(mod.get(DriveAxis.COMPETENCE) > 0.0);
        assertTrue(mod.get(DriveAxis.AUTONOMY) > 0.0);
    }

    @Test
    void associationBoostsCuriosity() {
        var result = new SubThoughtResult(List.of(
            new SubThought("association", "reminds me", null, 0.5, SubThought.Source.SYNC)
        ), "hash");
        var mod = SubThoughtModulation.compute(result);
        assertTrue(mod.get(DriveAxis.CURIOSITY) > 0.0);
    }

    @Test
    void intensityCapsAtOne() {
        var many = new java.util.ArrayList<SubThought>();
        for (int i = 0; i < 20; i++) {
            many.add(new SubThought("concern", "worried " + i, null, 0.5, SubThought.Source.SYNC));
        }
        var mod = SubThoughtModulation.compute(new SubThoughtResult(many, "hash"));
        assertTrue(mod.get(DriveAxis.AFFILIATION) <= 1.0);
    }

    @Test
    void emptyResultReturnsZeros() {
        var mod = SubThoughtModulation.compute(SubThoughtResult.EMPTY);
        assertEquals(0.0, mod.get(DriveAxis.AFFILIATION));
        assertEquals(0.0, mod.get(DriveAxis.CURIOSITY));
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition -Dtest=SubThoughtModulationTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure

- [ ] **Step 3: Implement SubThoughtModulation**

Use `ide_create_file` to create `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtModulation.java`:

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.cognition.drive.DriveAxis;
import io.casehub.neocortex.memory.experience.SubThoughtTypes;

import java.util.EnumMap;
import java.util.Map;

public final class SubThoughtModulation {

    private static final double STEP = 0.15;

    private SubThoughtModulation() {}

    public static Map<DriveAxis, Double> compute(SubThoughtResult subThoughts) {
        if (subThoughts.isEmpty()) {
            return Map.of(
                DriveAxis.AFFILIATION, 0.0, DriveAxis.COMPETENCE, 0.0,
                DriveAxis.CURIOSITY, 0.0, DriveAxis.AUTONOMY, 0.0
            );
        }

        int concern = 0, affect = 0, intention = 0, evaluative = 0;
        int association = 0, causal = 0, selfReflection = 0;

        for (var st : subThoughts.subThoughts()) {
            switch (st.type()) {
                case SubThoughtTypes.CONCERN -> concern++;
                case SubThoughtTypes.AFFECT_OBSERVATION -> affect++;
                case SubThoughtTypes.INTENTION -> intention++;
                case SubThoughtTypes.EVALUATIVE -> evaluative++;
                case SubThoughtTypes.ASSOCIATION -> association++;
                case SubThoughtTypes.CAUSAL_INFERENCE -> causal++;
                case SubThoughtTypes.SELF_REFLECTION -> selfReflection++;
                default -> {}
            }
        }

        var result = new EnumMap<DriveAxis, Double>(DriveAxis.class);
        result.put(DriveAxis.AFFILIATION, Math.min(1.0, (concern + affect) * STEP));
        result.put(DriveAxis.COMPETENCE, Math.min(1.0, (intention + evaluative) * STEP));
        result.put(DriveAxis.CURIOSITY, Math.min(1.0, (association + causal) * STEP));
        result.put(DriveAxis.AUTONOMY, Math.min(1.0, (intention + selfReflection) * STEP));
        return Map.copyOf(result);
    }
}
```

- [ ] **Step 4: Create ModulationLayer record**

Use `ide_create_file` to create `cognition/src/main/java/io/casehub/neocortex/cognition/drive/ModulationLayer.java`:

```java
package io.casehub.neocortex.cognition.drive;

import java.util.Map;

public record ModulationLayer(Map<DriveAxis, Double> modulation, double strength, String source) {
    public ModulationLayer {
        modulation = Map.copyOf(modulation);
    }
}
```

- [ ] **Step 5: Modify DriveComposer to accept ModulationLayer list**

Modify `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveComposer.java`. Change the `compose()` signature to replace `@Nullable Map<DriveAxis, Double> narrativeModulation` with `List<ModulationLayer> modulations`. Replace the narrative modulation application block (lines 38-41) with iteration over layers:

```java
for (var layer : modulations) {
    intensity += layer.modulation().getOrDefault(axis, 0.0) * layer.strength();
}
```

- [ ] **Step 6: Add setSubThoughtParticipant to DriveOrchestrator**

Modify `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java`:

Add field: `private SubThoughtTickParticipant subThoughtParticipant;`

Add setter:
```java
public void setSubThoughtParticipant(SubThoughtTickParticipant participant) {
    this.subThoughtParticipant = participant;
}
```

In `tick()` method, where narrativeModulation is computed and passed to compose(), build the modulation layers list:

```java
var modulations = new ArrayList<ModulationLayer>();
if (narrativeOrchestrator != null) {
    var narrativeMod = NarrativeModulation.compute(narrativeOrchestrator.currentNarrative(agentId, tenantId));
    if (narrativeMod != null) {
        modulations.add(new ModulationLayer(narrativeMod, config.narrativeModulationStrength(), "narrative"));
    }
}
if (subThoughtParticipant != null) {
    var stResult = subThoughtParticipant.currentSubThoughts(agentId, tenantId);
    if (stResult != null && !stResult.isEmpty()) {
        modulations.add(new ModulationLayer(SubThoughtModulation.compute(stResult), config.subThoughtModulationStrength(), "sub-thought"));
    }
}
```

Pass `modulations` to `composer.compose()`.

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition`
Expected: PASS (existing DriveComposer tests may need signature updates)

- [ ] **Step 8: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtModulation.java cognition/src/test/java/io/casehub/neocortex/cognition/subthought/SubThoughtModulationTest.java cognition/src/main/java/io/casehub/neocortex/cognition/drive/ModulationLayer.java cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveComposer.java cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java
git commit -m "feat(#478): add SubThoughtModulation + DriveComposer ModulationLayer integration

Refs #478"
```

### Task 5: MentalModelOrchestrator SubThoughtCue dispatch

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java:23` — add extractSubThoughtHeuristic, dispatch in record()
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestratorSubThoughtTest.java`

**Interfaces:**
- Consumes: `MentalStateSignal.SubThoughtCue(subThoughtType, content, entity, confidence)` from Task 1
- Consumes: `SubThoughtTypes` constants
- Produces: BDI updates via existing `upsertBelief()` and `upsertState()` methods

- [ ] **Step 1: Write test for SubThoughtCue heuristic extraction**

```java
package io.casehub.neocortex.cognition.mentalmodel;

import io.casehub.neocortex.memory.experience.SubThoughtTypes;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class MentalModelOrchestratorSubThoughtTest {

    // Use the existing test infrastructure from MentalModelOrchestratorTest
    // to create an orchestrator instance with in-memory backing

    @Test
    void subThoughtCueAffectCreatesBeliefAboutEntityState() {
        // record(SubThoughtCue("affect-observation", "Sarah seemed upset", "Sarah", 0.6), agentId, "Sarah", tenantId)
        // → upsertBelief with confidence 0.6
        // Verify: getBelief returns entry with "Sarah seemed upset"
    }

    @Test
    void subThoughtCueConcernCreatesDesire() {
        // record(SubThoughtCue("concern", "worry about her coping", "Sarah", 0.6), ...)
        // → upsertState for DESIRE with confidence 0.6
    }

    @Test
    void subThoughtCueIntentionCreatesIntention() {
        // record(SubThoughtCue("intention", "should bring David", "David", 0.7), ...)
        // → upsertState for INTENTION with confidence 0.7
    }

    @Test
    void subThoughtCueCausalCreatesExplanatoryBelief() {
        // record(SubThoughtCue("causal-inference", "promotion weighing on her", "Sarah", 0.5), ...)
        // → upsertBelief with confidence 0.5
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition -Dtest=MentalModelOrchestratorSubThoughtTest`
Expected: FAIL — no dispatch for SubThoughtCue

- [ ] **Step 3: Add extractSubThoughtHeuristic to MentalModelOrchestrator**

Modify `cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java`.

In `record()` method (line 64-78), add instanceof branch after VerbalCue:

```java
} else if (signal instanceof MentalStateSignal.SubThoughtCue stc) {
    extractSubThoughtHeuristic(state, stc);
}
```

Add new private method after `extractHeuristic()` (line 200):

```java
private void extractSubThoughtHeuristic(SubjectMentalState state, MentalStateSignal.SubThoughtCue cue) {
    var now = clock.instant();
    var key = normalizeKey(cue.content());
    switch (cue.subThoughtType()) {
        case SubThoughtTypes.AFFECT_OBSERVATION, SubThoughtTypes.EVALUATIVE ->
            upsertBelief(state, key, cue.content(), 0.6);
        case SubThoughtTypes.CONCERN, SubThoughtTypes.ASSOCIATION ->
            upsertState(state.desires, key, cue.content(), 0.6, BdiDimension.DESIRE, now);
        case SubThoughtTypes.INTENTION ->
            upsertState(state.intentions, key, cue.content(), 0.7, BdiDimension.INTENTION, now);
        case SubThoughtTypes.CAUSAL_INFERENCE, SubThoughtTypes.SELF_REFLECTION ->
            upsertBelief(state, key, cue.content(), 0.5);
        default -> {}
    }
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition -Dtest=MentalModelOrchestratorSubThoughtTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestratorSubThoughtTest.java
git commit -m "feat(#478): add SubThoughtCue dispatch in MentalModelOrchestrator

Refs #478"
```

### Task 6: SubThoughtPromptSection

**Files:**
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtPromptSection.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/subthought/SubThoughtPromptSectionTest.java`

**Interfaces:**
- Consumes: `SubThoughtTickParticipant.currentSubThoughts(agentId, tenantId)` → `SubThoughtResult`
- Consumes: `CognitionPromptRenderer` SPI
- Produces: Prompt section text grouped by entity

- [ ] **Step 1: Write test**

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.cognition.core.CognitionRenderContext;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class SubThoughtPromptSectionTest {

    @Test
    void rendersGroupedByEntity() {
        var participant = mockParticipantWith(List.of(
            new SubThought("affect-observation", "she seemed distracted", "Sarah", 0.8, SubThought.Source.ASYNC),
            new SubThought("evaluative", "the pasta was excellent", "restaurant", 0.7, SubThought.Source.ASYNC),
            new SubThought("intention", "should bring David next time", null, 0.5, SubThought.Source.SYNC)
        ));
        var section = new SubThoughtPromptSection(participant);
        var context = new CognitionRenderContext("agent1", "t1", null);
        var rendered = section.render(context);

        assertTrue(rendered.contains("About Sarah:"));
        assertTrue(rendered.contains("she seemed distracted"));
        assertTrue(rendered.contains("General:"));
        assertTrue(rendered.contains("should bring David"));
    }

    @Test
    void rendersEmptyWhenNoSubThoughts() {
        var participant = mockParticipantWith(List.of());
        var section = new SubThoughtPromptSection(participant);
        var context = new CognitionRenderContext("agent1", "t1", null);
        var rendered = section.render(context);
        assertTrue(rendered == null || rendered.isBlank());
    }
    
    // Helper: create a participant and pre-populate its state
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition -Dtest=SubThoughtPromptSectionTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure

- [ ] **Step 3: Implement SubThoughtPromptSection**

Use `ide_create_file` to create `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtPromptSection.java`:

```java
package io.casehub.neocortex.cognition.subthought;

import io.casehub.neocortex.cognition.core.CognitionPromptRenderer;
import io.casehub.neocortex.cognition.core.CognitionRenderContext;

import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.stream.Collectors;

public class SubThoughtPromptSection implements CognitionPromptRenderer {

    private static final int MAX_SUB_THOUGHTS = 10;
    private final SubThoughtTickParticipant participant;

    public SubThoughtPromptSection(SubThoughtTickParticipant participant) {
        this.participant = participant;
    }

    @Override
    public String render(CognitionRenderContext context) {
        var result = participant.currentSubThoughts(context.agentId(), context.tenantId());
        if (result == null || result.isEmpty()) return "";

        var sorted = result.subThoughts().stream()
                .sorted(Comparator.comparingDouble(SubThought::confidence).reversed())
                .limit(MAX_SUB_THOUGHTS)
                .toList();

        var grouped = sorted.stream()
                .collect(Collectors.groupingBy(
                        st -> st.entity() != null ? st.entity() : "General",
                        LinkedHashMap::new,
                        Collectors.toList()));

        var sb = new StringBuilder("## Recent Cognitive Reactions\n\n");
        for (var entry : grouped.entrySet()) {
            String label = "General".equals(entry.getKey()) ? "General:" : "About " + entry.getKey() + ":";
            sb.append(label).append('\n');
            for (var st : entry.getValue()) {
                sb.append("- ").append(st.text()).append(" (").append(st.type()).append(")\n");
            }
            sb.append('\n');
        }
        return sb.toString().strip();
    }
}
```

- [ ] **Step 4: Uncomment promptSections() wiring in CognitionCore** (if gated in Task 3 Step 6)

Ensure the `SubThoughtPromptSection` import and instantiation in `CognitionCore.promptSections()` compiles.

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtPromptSection.java cognition/src/test/java/io/casehub/neocortex/cognition/subthought/SubThoughtPromptSectionTest.java cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java
git commit -m "feat(#478): add SubThoughtPromptSection — entity-grouped cognitive reactions in prompt

Refs #478"
```

---

## Batch 4: Async Enrichment — observer, LLM extraction, event wiring

### Task 7: SubThoughtExtractionObserver + SubThoughtExtractor LLM implementation

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractionObserver.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractor.java:17` — implement onExtractionRequested(), fire SubThoughtsEnriched, add confidence to ParsedSubThought
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractionObserverTest.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractorTest.java`

**Interfaces:**
- Consumes: `ExperienceRecorded` CDI event (memoryId, event)
- Consumes: `SubThoughtExtractionRequested(memoryId, tenantId, experienceText, principalId)`
- Consumes: `SubThoughtExtractor.applySubThoughts(memoryId, List<ParsedSubThought>, tenantId)`
- Produces: `SubThoughtsEnriched` CDI event (fired after enrichment)
- Produces: `SubThoughtExtractionObserver` — `@Observes ExperienceRecorded`, filters Observation/FormativeExperience, rate-limited per agent

- [ ] **Step 1: Write test for SubThoughtExtractionObserver**

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.memory.experience.ExperienceEvent;
import io.casehub.neocortex.memory.experience.ExperienceRecorded;
import jakarta.enterprise.event.Event;
import org.junit.jupiter.api.Test;
import static org.mockito.Mockito.*;

class SubThoughtExtractionObserverTest {

    @Test
    void firesExtractionForObservation() {
        @SuppressWarnings("unchecked")
        Event<SubThoughtExtractionRequested> event = mock(Event.class);
        var observer = new SubThoughtExtractionObserver();
        // inject event field via reflection or constructor
        var observation = new ExperienceEvent.Observation("agent1", "t1", "She seemed happy");
        var recorded = new ExperienceRecorded(observation, "mem-1");
        observer.onExperienceRecorded(recorded);
        verify(event).fireAsync(any(SubThoughtExtractionRequested.class));
    }

    @Test
    void skipsActionEvents() {
        // Action events should not trigger extraction
    }

    @Test
    void rateLimitsPerAgent() {
        // Two events within 5s for same agent → only first fires
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-intelligence -Dtest=SubThoughtExtractionObserverTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure

- [ ] **Step 3: Implement SubThoughtExtractionObserver**

Use `ide_create_file` to create `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractionObserver.java` with the code from spec §7 (rate-limited, event-type-filtered observer).

- [ ] **Step 4: Add confidence to ParsedSubThought, implement LLM extraction in SubThoughtExtractor**

Modify `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractor.java`:

1. Add `double confidence` field to `ParsedSubThought` record (line 52)
2. Extend `applySubThoughts()` to persist confidence via `SubThoughtAttributeKeys.confidence(i)`
3. Implement `onExtractionRequested()`:
   - Check AgentProvider availability (Instance<AgentProvider>)
   - Build system prompt describing 7 sub-thought types + JSON response format
   - Call AgentProvider with Haiku
   - Parse JSON into `List<ParsedSubThought>`
   - Call `applySubThoughts()`
   - Fire `SubThoughtsEnriched` CDI event
4. Add `@Inject Event<SubThoughtsEnriched> enrichedEvent` field

- [ ] **Step 5: Run mindmap-intelligence tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl mindmap-intelligence`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractionObserver.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractor.java mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/
git commit -m "feat(#478): add SubThoughtExtractionObserver + LLM extraction in SubThoughtExtractor

Refs #478"
```

---

## Batch 5: CAPS Integration — situation decorator

### Task 8: SubThoughtSituationDecorator + BehavioralSynthesisPhase metadata

**Files:**
- Create: `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/SubThoughtSituationDecorator.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java:36` — extend nodeMetadata()
- Test: `caps-engine/src/test/java/io/casehub/neocortex/caps/engine/SubThoughtSituationDecoratorTest.java`

**Interfaces:**
- Consumes: `SituationClassifier.classify(String description, Map<String, String> metadata)` → `List<SituationActivation>`
- Consumes: `SituationActivation(String nodeId, double confidence)`
- Consumes: Metadata key `cognitiveKind` from graduated MindMap nodes
- Produces: `SubThoughtSituationDecorator` — `@Decorator @Priority(70)` on SituationClassifier

- [ ] **Step 1: Write test for SubThoughtSituationDecorator**

```java
package io.casehub.neocortex.caps.engine;

import io.casehub.neocortex.caps.SituationActivation;
import io.casehub.neocortex.caps.SituationClassifier;
import org.junit.jupiter.api.Test;
import java.util.List;
import java.util.Map;
import static org.junit.jupiter.api.Assertions.*;

class SubThoughtSituationDecoratorTest {

    @Test
    void addsConcernActivationsToBaseResult() {
        SituationClassifier base = (desc, meta) -> List.of(
            new SituationActivation("social_threat", 0.3)
        );
        var decorator = new SubThoughtSituationDecorator();
        // inject delegate
        var metadata = Map.of("cognitiveKind", "concern");
        var result = decorator.classify("worried about her", metadata);
        assertTrue(result.size() > 1);
        assertTrue(result.stream().anyMatch(a -> a.confidence() >= 0.5));
    }

    @Test
    void mergesTakesMaxConfidenceOnDuplicate() {
        SituationClassifier base = (desc, meta) -> List.of(
            new SituationActivation("social_threat", 0.8)
        );
        var decorator = new SubThoughtSituationDecorator();
        var metadata = Map.of("cognitiveKind", "concern");
        var result = decorator.classify("worried", metadata);
        var socialThreat = result.stream()
            .filter(a -> "social_threat".equals(a.nodeId()))
            .findFirst().orElseThrow();
        assertEquals(0.8, socialThreat.confidence());
    }

    @Test
    void passesThoughWithoutCognitiveKind() {
        SituationClassifier base = (desc, meta) -> List.of(
            new SituationActivation("mastery", 0.5)
        );
        var decorator = new SubThoughtSituationDecorator();
        var result = decorator.classify("did well", Map.of());
        assertEquals(1, result.size());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl caps-engine -Dtest=SubThoughtSituationDecoratorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure

- [ ] **Step 3: Implement SubThoughtSituationDecorator**

Use `ide_create_file` to create `caps-engine/src/main/java/io/casehub/neocortex/caps/engine/SubThoughtSituationDecorator.java`:

```java
package io.casehub.neocortex.caps.engine;

import io.casehub.neocortex.caps.SituationActivation;
import io.casehub.neocortex.caps.SituationClassifier;
import io.casehub.neocortex.memory.experience.SubThoughtTypes;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.inject.Inject;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

@Decorator
@Priority(70)
public class SubThoughtSituationDecorator implements SituationClassifier {

    @Inject @Delegate SituationClassifier delegate;

    private static final Map<String, List<SituationActivation>> TYPE_ACTIVATIONS = Map.of(
        SubThoughtTypes.AFFECT_OBSERVATION, List.of(
            new SituationActivation("acceptance", 0.3),
            new SituationActivation("exclusion", 0.3)),
        SubThoughtTypes.CAUSAL_INFERENCE, List.of(
            new SituationActivation("mastery", 0.4)),
        SubThoughtTypes.CONCERN, List.of(
            new SituationActivation("social_threat", 0.6),
            new SituationActivation("psychological_threat", 0.5)),
        SubThoughtTypes.INTENTION, List.of(
            new SituationActivation("agency_granted", 0.5),
            new SituationActivation("choice_available", 0.4)),
        SubThoughtTypes.SELF_REFLECTION, List.of(
            new SituationActivation("agency_granted", 0.4))
    );

    @Override
    public List<SituationActivation> classify(String description, Map<String, String> metadata) {
        List<SituationActivation> base = delegate.classify(description, metadata);
        String cognitiveKind = metadata != null ? metadata.get("cognitiveKind") : null;
        if (cognitiveKind == null) return base;

        List<SituationActivation> extra = TYPE_ACTIVATIONS.getOrDefault(cognitiveKind, List.of());
        if (extra.isEmpty()) return base;

        var merged = new LinkedHashMap<String, Double>();
        for (var a : base) merged.merge(a.nodeId(), a.confidence(), Math::max);
        for (var a : extra) merged.merge(a.nodeId(), a.confidence(), Math::max);

        return merged.entrySet().stream()
                .map(e -> new SituationActivation(e.getKey(), e.getValue()))
                .toList();
    }
}
```

- [ ] **Step 4: Extend BehavioralSynthesisPhase.nodeMetadata()**

Modify `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java`. In `nodeMetadata()` (line 261-266), add sub-thought properties from the MindMap node:

```java
var cognitiveKind = node.properties().get("cognitiveKind");
if (cognitiveKind != null) {
    metadata.put("cognitiveKind", cognitiveKind.toString());
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl caps-engine,mindmap-intelligence`
Expected: PASS

- [ ] **Step 6: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test`
Expected: PASS — all modules compile and tests pass

- [ ] **Step 7: Commit**

```bash
git add caps-engine/src/main/java/io/casehub/neocortex/caps/engine/SubThoughtSituationDecorator.java caps-engine/src/test/java/io/casehub/neocortex/caps/engine/SubThoughtSituationDecoratorTest.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java
git commit -m "feat(#478): add SubThoughtSituationDecorator + BehavioralSynthesisPhase metadata

Closes #478"
```

---

## References

- [2026-10-08-sub-thought-tick-integration-design.md] — design spec this plan implements
- [decisions.md] — 9 validated design decisions
- cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java — tick lifecycle, promptSections, addParticipant
- cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitionConfig.java — feature enable flags
- cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalStateSignal.java — sealed hierarchy
- cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java — tick, NarrativeOrchestrator integration
- cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveComposer.java — compose signature
- cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java — record, extractHeuristic
- cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java — CDI producers
- memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtTypes.java — 7 type constants
- memory-api/src/main/java/io/casehub/neocortex/memory/experience/SubThoughtAttributeKeys.java — attribute keys
- mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/SubThoughtExtractor.java — stub + applySubThoughts
- caps-api/src/main/java/io/casehub/neocortex/caps/SituationClassifier.java — classify SPI
- caps-engine/src/main/resources/caps-topology.yaml — input node IDs
- mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/BehavioralSynthesisPhase.java — nodeMetadata
- GitHub casehubio/neocortex#478 — focal issue
- GitHub casehubio/neocortex#470 — prerequisite (sub-thought data model)
