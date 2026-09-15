# MindMapExtractor parse/apply + ConversationBridge principalId/confidence — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #337 — MindMapExtractor.parseOnly() + ConversationBridge principalId/confidence params
**Issue group:** #337

**Goal:** Decompose MindMapExtractor.extract() into parse/apply phases and fix ConversationBridge's broken principalId + hardcoded confidence.

**Architecture:** Split the extract() method at its natural seam — LLM parsing vs store mutation. Make the parsed types public so callers can work with extraction results without persistence. Fix ConversationBridge to wire its principalId parameter through to NodeInput and propagate it via ExtractionRequested to the async extraction path. Add ConfidenceOrigin parameter for caller-controlled confidence.

**Tech Stack:** Java 21, Quarkus CDI, JUnit 5, AssertJ

## Global Constraints

- All changes within `mindmap-intelligence` module only
- No new modules, no new dependencies, no Flyway migrations
- Pre-release — clean API breaks are acceptable
- Use `ide_insert_member` / `ide_replace_member` for structural edits

---

## Batch 1: MindMapExtractor parse/apply decomposition

### Task 1: Make parsed types public and add parse() method

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ParsedExtraction.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ParsedEntity.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ParsedRelationship.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ParsedContradiction.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractor.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/MindMapExtractorTest.java`

**Interfaces:**
- Produces: `MindMapExtractor.parse(String, String, List<String>) → ParsedExtraction` (nullable return)
- Produces: `MindMapExtractor.apply(ParsedExtraction, String) → ExtractionResult`
- Produces: `MindMapExtractor.apply(ParsedExtraction, String, PrincipalId) → ExtractionResult`

- [ ] **Step 1: Write failing test — parse() returns ParsedExtraction without persisting**

```java
@Test
void parse_returnsExtractedEntitiesWithoutPersisting() {
    String response = """
        {"entities": [
            {"name": "Alice", "type": "PERSON", "properties": {"role": "engineer"}, "confidence": "STATED"}
        ], "relationships": [], "contradictions": []}
        """;
    var extractor = createExtractor(response);

    ParsedExtraction parsed = extractor.parse("Alice is an engineer", TENANT, List.of());

    assertThat(parsed).isNotNull();
    assertThat(parsed.entities()).hasSize(1);
    assertThat(parsed.entities().getFirst().name()).isEqualTo("Alice");
    assertThat(parsed.entities().getFirst().origin()).isEqualTo(ConfidenceOrigin.STATED);
    // Verify nothing persisted
    assertThat(store.search(MindMapQuery.of(TENANT, 100))).isEmpty();
}
```

Add import for `io.casehub.neocortex.cognitive.ConfidenceOrigin` and `io.casehub.neocortex.mindmap.MindMapQuery`.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorTest#parse_returnsExtractedEntitiesWithoutPersisting -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — `parse()` method does not exist

- [ ] **Step 3: Make parsed types public**

Change visibility on four files from `record` to `public record`:

`ParsedExtraction.java`:
```java
public record ParsedExtraction(
```

`ParsedEntity.java`:
```java
public record ParsedEntity(
```

`ParsedRelationship.java`:
```java
public record ParsedRelationship(
```

`ParsedContradiction.java`:
```java
public record ParsedContradiction(
```

- [ ] **Step 4: Add parse() method to MindMapExtractor**

Extract the parse logic from `extract()` into a new public method. Add this method before `extract()`:

```java
public ParsedExtraction parse(String conversationText, String tenantId,
                                List<String> recentEntityNames) {
    if (conversationText == null || conversationText.isBlank()) return null;
    if (agentProviderInstance.isUnsatisfied()) return null;

    Map<String, List<MindMapEdge>> context =
        retrieveContext(conversationText, tenantId, recentEntityNames);
    String userPrompt = buildUserPrompt(conversationText, context, recentEntityNames, tenantId);
    String llmResponse = invokeLlm(SYSTEM_PROMPT, userPrompt);
    if (llmResponse == null) return null;

    return ExtractionJsonParser.parse(llmResponse);
}
```

- [ ] **Step 5: Add apply() methods to MindMapExtractor**

Make `applyExtraction` public as `apply`, and add a principalId overload. Add these methods after `parse()`:

```java
public ExtractionResult apply(ParsedExtraction parsed, String tenantId) {
    return apply(parsed, tenantId, null);
}

public ExtractionResult apply(ParsedExtraction parsed, String tenantId,
                               PrincipalId principalId) {
    return applyExtraction(parsed, tenantId, principalId);
}
```

Add `import io.casehub.platform.api.identity.PrincipalId;` to MindMapExtractor.

- [ ] **Step 6: Update applyExtraction to accept PrincipalId**

Change the `applyExtraction` signature to accept `PrincipalId principalId` and wire it through to NodeInput and EdgeInput:

Change method signature:
```java
private ExtractionResult applyExtraction(ParsedExtraction parsed, String tenantId,
                                          PrincipalId principalId) {
```

In the node creation block (where `store.addNode` is called for new nodes), change:
```java
nodeId = store.addNode(new NodeInput(
    pe.name(), sgId,
    MindMapConfidenceDefaults.forOrigin(pe.origin(), Instant.now()),
    "llm-extraction", null, null, null, null,
    null, null, null,
    nodeProps, principalId, null), tenantId);
```

In the edge creation block, change:
```java
String edgeId = store.addEdge(new EdgeInput(
    sourceId, targetId, pr.type(),
    MindMapConfidenceDefaults.forOrigin(pr.origin(), Instant.now()),
    "llm-extraction", null, null, null, null, null, Map.of(),
    principalId), tenantId);
```

- [ ] **Step 7: Rewrite extract() as composition of parse + apply**

Replace the body of `extract(String, String, List<String>)`:
```java
public ExtractionResult extract(String conversationText, String tenantId,
                                 List<String> recentEntityNames) {
    ParsedExtraction parsed = parse(conversationText, tenantId, recentEntityNames);
    if (parsed == null) return ExtractionResult.EMPTY;
    return apply(parsed, tenantId);
}
```

- [ ] **Step 8: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorTest#parse_returnsExtractedEntitiesWithoutPersisting -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 9: Write test — parse returns null for blank input**

```java
@Test
void parse_blankInput_returnsNull() {
    var extractor = createExtractor("{}");
    assertThat(extractor.parse(null, TENANT, List.of())).isNull();
    assertThat(extractor.parse("  ", TENANT, List.of())).isNull();
}
```

- [ ] **Step 10: Write test — apply with principalId sets it on nodes**

```java
@Test
void apply_withPrincipalId_setsOnCreatedNodes() {
    String response = """
        {"entities": [
            {"name": "Alice", "type": "PERSON", "properties": {}, "confidence": "STATED"}
        ], "relationships": [], "contradictions": []}
        """;
    var extractor = createExtractor(response);
    ParsedExtraction parsed = extractor.parse("Alice is here", TENANT, List.of());
    PrincipalId pid = PrincipalId.of("agent-1");

    ExtractionResult result = extractor.apply(parsed, TENANT, pid);

    assertThat(result.entities()).hasSize(1);
    MindMapNode node = store.getNode(result.entities().getFirst().nodeId(), TENANT);
    assertThat(node.principalId()).isEqualTo(pid);
}
```

Add import for `io.casehub.platform.api.identity.PrincipalId`.

- [ ] **Step 11: Write test — existing extract() still works**

```java
@Test
void extract_compositionPreservesBehavior() {
    String response = """
        {"entities": [
            {"name": "Bob", "type": "PERSON", "properties": {}, "confidence": "INFERRED"}
        ], "relationships": [], "contradictions": []}
        """;
    var extractor = createExtractor(response);

    ExtractionResult result = extractor.extract("Bob is here", TENANT);

    assertThat(result.entities()).hasSize(1);
    assertThat(result.entities().getFirst().name()).isEqualTo("Bob");
    // Verify it did persist (unlike parse)
    assertThat(store.search(MindMapQuery.of(TENANT, 100))).isNotEmpty();
}
```

- [ ] **Step 12: Run all MindMapExtractor tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=MindMapExtractorTest`
Expected: all tests PASS (existing + new)

- [ ] **Step 13: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-intelligence/src/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat: decompose MindMapExtractor.extract() into parse() + apply()

Split extract() at the natural seam between LLM parsing and store
mutation. parse() returns ParsedExtraction without persistence.
apply() accepts optional PrincipalId for agent-scoped node creation.
ParsedExtraction, ParsedEntity, ParsedRelationship, ParsedContradiction
become public API.

Refs #337"
```

---

## Batch 2: ConversationBridge principalId/confidence + ExtractionRequested propagation

### Task 2: Fix ConversationBridge signature and wire principalId/confidence

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridge.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequested.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserver.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ConversationBridgeTest.java`
- Test: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/ExtractionRequestedObserverTest.java`

**Interfaces:**
- Consumes: `MindMapExtractor.apply(ParsedExtraction, String, PrincipalId)` from Task 1
- Produces: `ConversationBridge.process(String, String, List<String>, PrincipalId, ConfidenceOrigin) → SegmentationResult`

- [ ] **Step 1: Write failing test — process with PrincipalId creates scoped nodes**

```java
@Test
void process_withPrincipalId_setsOnCreatedNodes() {
    PrincipalId pid = PrincipalId.of("agent-1");
    var result = bridge.process("Some text.", "t1", List.of(), pid, null);
    assertThat(result.createdNodeIds()).isNotEmpty();
    MindMapNode node = store.getNode(result.createdNodeIds().getFirst(), "t1");
    assertThat(node.principalId()).isEqualTo(pid);
}
```

Add imports for `io.casehub.platform.api.identity.PrincipalId` and `io.casehub.neocortex.mindmap.MindMapNode`.

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ConversationBridgeTest#process_withPrincipalId_setsOnCreatedNodes -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation error — signature mismatch (5 args vs 4)

- [ ] **Step 3: Update ConversationBridge.process() signature and implementation**

Change the method signature from:
```java
public SegmentationResult process(String cleanedText, String tenantId,
                                   List<String> recentEntityNames,
                                   Object principalId) {
```
to:
```java
public SegmentationResult process(String cleanedText, String tenantId,
                                   List<String> recentEntityNames,
                                   PrincipalId principalId,
                                   ConfidenceOrigin confidenceOrigin) {
```

Add imports:
```java
import io.casehub.platform.api.identity.PrincipalId;
```

In the node creation block, change:
```java
String nodeId = store.addNode(
    NodeInput.of(seg.title(), subgraphId)
        .withConfidence(MindMapConfidenceDefaults.forOrigin(
            confidenceOrigin != null ? confidenceOrigin : ConfidenceOrigin.STATED,
            Instant.now()))
        .withProvenance("conversation-bridge")
        .withPrincipalId(principalId)
        .withProperties(Map.of(
            "body", seg.body(),
            "topic", seg.topic())),
    tenantId);
```

Update the ExtractionRequested event fire to pass principalId:
```java
eventSink.accept(new ExtractionRequested(
    cleanedText, tenantId, recentEntityNames, createdNodeIds, principalId));
```

- [ ] **Step 4: Update ExtractionRequested to carry principalId**

Change the record:
```java
import io.casehub.platform.api.identity.PrincipalId;

public record ExtractionRequested(
    String cleanedText,
    String tenantId,
    List<String> recentEntityNames,
    List<String> segmentNodeIds,
    PrincipalId principalId
) {
    public ExtractionRequested {
        recentEntityNames = recentEntityNames != null ? List.copyOf(recentEntityNames) : List.of();
        segmentNodeIds = List.copyOf(segmentNodeIds);
    }
}
```

- [ ] **Step 5: Update ExtractionRequestedObserver to forward principalId**

In `onExtractionRequested`, change the extract() call to use apply() with principalId:
```java
public void onExtractionRequested(@ObservesAsync ExtractionRequested event) {
    MutationContext.set("extraction");
    try {
        var parsed = extractor.parse(
            event.cleanedText(), event.tenantId(), event.recentEntityNames());

        if (parsed == null) return;

        var result = extractor.apply(parsed, event.tenantId(), event.principalId());
```

The rest of the method body remains unchanged.

- [ ] **Step 6: Update ExtractionRequestedObserverTest for parse/apply**

The existing `stubExtractor` overrides `extract()`, but the observer now calls `parse()` + `apply()`. Replace the stub and update ExtractionRequested constructor calls (now 5-arg with principalId):

Replace `stubExtractor` method:
```java
private MindMapExtractor stubExtractor(ExtractionResult result) {
    return new MindMapExtractor(store, null) {
        @Override
        public ParsedExtraction parse(String text, String tenantId,
                                       List<String> recentEntityNames) {
            if (result == ExtractionResult.EMPTY) return null;
            return new ParsedExtraction(List.of(), List.of(), List.of());
        }

        @Override
        public ExtractionResult apply(ParsedExtraction parsed, String tenantId,
                                       PrincipalId principalId) {
            return result;
        }
    };
}
```

Add import for `io.casehub.platform.api.identity.PrincipalId`.

Update all `new ExtractionRequested(...)` calls to include 5th arg (null principalId):
```java
// Every: new ExtractionRequested("text", "t1", List.of(), List.of(segmentId))
// becomes: new ExtractionRequested("text", "t1", List.of(), List.of(segmentId), null)
```

Update all 3 test methods.

- [ ] **Step 7: Update existing ConversationBridgeTest calls to new 5-arg signature**

All existing test calls pass `null` as the 4th arg. Add `null` as the 5th arg (confidenceOrigin):

```java
// Every existing call: bridge.process("...", "t1", List.of(), null)
// becomes:             bridge.process("...", "t1", List.of(), null, null)
```

Update all 6 existing test methods.

- [ ] **Step 8: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ConversationBridgeTest#process_withPrincipalId_setsOnCreatedNodes -Dsurefire.failIfNoSpecifiedTests=false`
Expected: PASS

- [ ] **Step 9: Write test — null confidenceOrigin defaults to STATED**

```java
@Test
void process_nullConfidence_defaultsToStated() {
    var result = bridge.process("Some text.", "t1", List.of(), null, null);
    MindMapNode node = store.getNode(result.createdNodeIds().getFirst(), "t1");
    assertThat(node.confidence().origin()).isEqualTo(ConfidenceOrigin.STATED);
    assertThat(node.confidence().value()).isEqualTo(1.0);
}
```

Add import for `io.casehub.neocortex.cognitive.ConfidenceOrigin`.

- [ ] **Step 10: Write test — INFERRED confidence creates nodes at 0.7**

```java
@Test
void process_inferredConfidence_createsNodesAt07() {
    var result = bridge.process("Some text.", "t1", List.of(), null,
        ConfidenceOrigin.INFERRED);
    MindMapNode node = store.getNode(result.createdNodeIds().getFirst(), "t1");
    assertThat(node.confidence().origin()).isEqualTo(ConfidenceOrigin.INFERRED);
    assertThat(node.confidence().value()).isEqualTo(0.7);
}
```

- [ ] **Step 11: Write test — ExtractionRequested carries principalId**

```java
@Test
void process_firesExtractionEventWithPrincipalId() {
    PrincipalId pid = PrincipalId.of("agent-1");
    bridge.process("Some text.", "t1", List.of(), pid, null);
    assertThat(firedEvents).hasSize(1);
    assertThat(firedEvents.getFirst().principalId()).isEqualTo(pid);
}
```

- [ ] **Step 12: Run all ConversationBridge tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=ConversationBridgeTest`
Expected: all tests PASS

- [ ] **Step 13: Run full mindmap-intelligence test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence`
Expected: all tests PASS (including ExtractionRequestedObserver tests — now using parse/apply stub)

- [ ] **Step 14: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add mindmap-intelligence/src/
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat: fix ConversationBridge principalId type + add confidence param

Change principalId from Object to PrincipalId and wire through to
NodeInput. Add nullable ConfidenceOrigin parameter (defaults to STATED).
Propagate principalId via ExtractionRequested to async extraction path.
ExtractionRequestedObserver now uses parse() + apply(principalId).

Closes #337"
```

## References

- [2026-09-15-parseonly-principalid-design.md] — design spec this plan implements
- [MindMapExtractor.java:109-128] — extract() decomposition target
- [ConversationBridge.java:40-77] — broken principalId, hardcoded confidence
- [ExtractionRequestedObserver.java:41-73] — async extraction path
- [NodeInput.java:101] — withPrincipalId() builder
- [EdgeInput.java:85] — withPrincipalId() builder
- [MindMapConfidenceDefaults.java] — confidence value defaults
- [GitHub #337] — focal issue
