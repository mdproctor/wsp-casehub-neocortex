# CognitiveMemoryRetriever Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #750 — Integrate CognitiveMemoryRetriever into cognitive orchestrators
**Issue group:** #750

**Goal:** Wire CognitiveMemoryRetriever into 4 cognitive components so modulated
memory retrieval (recency, confidence, mood congruence, goal relevance) shapes
agent perception and reasoning.

**Architecture:** Add tick-scoped context to CognitiveMemoryRetriever so CognitionCore
can set mood/personality once per tick. Then integrate the retriever into
GutFeelingParticipant (direct substitution) and 3 orchestrators (supplementary
LLM context in their reflection/inference prompts).

**Tech Stack:** Java 21, Quarkus CDI, JUnit 5, AssertJ, Mockito

## Global Constraints

- CognitiveMemoryRetriever lives in `cognitive-index` (Tier 2). Orchestrators
  live in `cognition` (Tier 3). Dependency direction is correct.
- All new constructor parameters are `@Nullable` with graceful degradation.
- Consolidation phases must NOT use modulated retrieval.
- Existing tests must continue passing without modification.

---

## Batch 1: Tick-Scoped Context on CognitiveMemoryRetriever

### Task 1: Add tick-scoped context to CognitiveMemoryRetriever

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveMemoryRetriever.java`
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveMemoryRetrieverTest.java`

**Interfaces:**
- Produces: `setTickContext(ModulationContext)` — called by CognitionCore once per tick
- Produces: `query(MemoryQuery)` — now uses tick context when available instead of minimal fallback

- [ ] **Step 1: Write failing test — tick context used by convenience query**

```java
@Test
void convenienceQueryUsesTickContext() {
    var moodState = new MoodState(0.5, 0.3, 0.2);
    var moodFactor = ModulationFactors.moodCongruence(moodState, 1.0);

    var pleasant = memory("m1", NOW, Confidence.unknown(1.0), 0.6, 0.2, 0.1);
    var unpleasant = memory("m2", NOW, Confidence.unknown(1.0), -0.6, -0.2, -0.1);

    var retriever = new CognitiveMemoryRetriever(
            stubStore(List.of(unpleasant, pleasant)),
            List.of(),
            List.of(ctx -> {
                if (ctx.currentMood() == null) return null;
                return ModulationFactors.moodCongruence(ctx.currentMood(), 1.0);
            }));

    // Without tick context — mood factor won't fire (null mood)
    var withoutContext = retriever.query(query());
    assertThat(withoutContext).extracting(Memory::memoryId)
            .containsExactly("m2", "m1"); // original order

    // Set tick context with positive mood
    retriever.setTickContext(new ModulationContext(
            "a1", "t1", moodState, null, null));

    // With tick context — mood-congruent (pleasant) should rank higher
    var withContext = retriever.query(query());
    assertThat(withContext).extracting(Memory::memoryId)
            .containsExactly("m1", "m2");
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveMemoryRetrieverTest#convenienceQueryUsesTickContext -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `setTickContext` does not exist

- [ ] **Step 3: Implement tick-scoped context**

Add to `CognitiveMemoryRetriever`:
```java
private volatile ModulationContext tickContext;

public void setTickContext(ModulationContext context) {
    this.tickContext = context;
}
```

Update the convenience `query(MemoryQuery)` method:
```java
public List<Memory> query(MemoryQuery query) {
    var ctx = tickContext;
    if (ctx == null) {
        ctx = new ModulationContext(null, query.tenantId(), null, null, null);
    }
    return query(query, ctx);
}
```

- [ ] **Step 4: Add test helper for Memory with PAD**

The existing `memory()` helper may need a PAD variant. Add if not present:
```java
private static Memory memory(String id, Instant ts, Confidence conf,
                              double pleasure, double arousal, double dominance) {
    // Create memory with PAD values for mood congruence testing
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveMemoryRetrieverTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveMemoryRetriever.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveMemoryRetrieverTest.java
git commit -m "feat(#750): add tick-scoped context to CognitiveMemoryRetriever

Refs #750"
```

### Task 2: Wire tick context in CognitionCore.tick()

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java:224-290` (tick method)

**Interfaces:**
- Consumes: `CognitiveMemoryRetriever.setTickContext(ModulationContext)`
- Consumes: `MoodOrchestrator.currentMood(agentId, tenantId)` — already available on `mood` field
- Consumes: `CognitiveDefaultsRegistry.forAgentOrDefaults(agentId).personalityWeights()` — already available on `defaultsRegistry` field

- [ ] **Step 1: Write failing test — tick sets context on retriever**

Add to `CognitionCoreTest.java` (or create if missing). Use the existing
test patterns with mock orchestrators:

```java
@Test
void tick_setsTickContextOnRetriever() {
    var retriever = new CognitiveMemoryRetriever(
            stubStore(List.of()), List.of(), List.of());
    core.configureCognitiveMemoryRetriever(retriever);

    core.tick("a1", "t1", null, (a, t) -> Set.of(), "observation");

    // Verify retriever has tick context set (use reflection or add package-private accessor)
}
```

Note: Since `tickContext` is volatile and package-private access may be
needed, consider adding a package-private `tickContext()` accessor for
testing, or verify indirectly by checking that `query(MemoryQuery)` uses
mood context.

- [ ] **Step 2: Implement tick context wiring in CognitionCore.tick()**

In `CognitionCore.tick()`, after the mood tick block (line ~254) and before
`runCustomParticipants(CognitionPhase.FOUNDATION, context)` (line ~259),
add:

```java
if (cognitiveMemoryRetriever != null) {
    var moodState = mood.currentMood(agentId, tenantId).orElse(null);
    var personality = defaultsRegistry != null
            ? defaultsRegistry.forAgentOrDefaults(agentId).personalityWeights()
            : null;
    cognitiveMemoryRetriever.setTickContext(
            new ModulationContext(agentId, tenantId, moodState, personality, Set.of()));
}
```

Add import for `io.casehub.neocortex.cognitive.index.ModulationContext`.

- [ ] **Step 3: Run tests to verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dsurefire.failIfNoSpecifiedTests=false`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java
git commit -m "feat(#750): wire tick context into CognitiveMemoryRetriever from CognitionCore

CognitionCore.tick() now sets ModulationContext on the retriever after
FOUNDATION phase, making mood/personality available to all downstream
orchestrators without them needing to assemble context themselves.

Refs #750"
```

## Batch 2: GutFeelingParticipant Integration

### Task 3: Switch GutFeelingParticipant Layer 1 to CognitiveMemoryRetriever

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/gut/GutFeelingParticipant.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/gut/GutFeelingParticipantTest.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java` — `configureGutFeeling` method
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitivePipelineBuilder.java` — builder method

**Interfaces:**
- Consumes: `CognitiveMemoryRetriever.query(MemoryQuery)` — tick context already set
- Retains: `CaseMemoryStore.scan(MemoryScanRequest)` — Layer 2 affect scan stays unmodulated

- [ ] **Step 1: Write failing test — retriever used for Layer 1 experience search**

```java
@Test
void layer1UsesRetrieverWhenAvailable() {
    var store = createStore();
    store.store(MemoryInput.of(Subject.of("agent", "a1"), ExperienceEvents.DOMAIN, "t1",
            "Authority figure criticized harshly").withPad(-0.7, 0.6, -0.3));

    var retriever = new CognitiveMemoryRetriever(store, List.of(), List.of());

    var participant = new GutFeelingParticipant(retriever, store, null, null);
    var ctx = new CognitionTickContext("a1", "t1", null, (a, t) -> Set.of(), "authority");
    participant.tick(ctx);

    var result = participant.currentResult("a1", "t1");
    assertThat(result).isPresent();
    assertThat(result.get().valence()).isEqualTo(GutValence.AVOID);
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: compilation failure — no constructor `GutFeelingParticipant(CognitiveMemoryRetriever, CaseMemoryStore, MoodOrchestrator, CognitionConfig)`

- [ ] **Step 3: Update GutFeelingParticipant constructor and Layer 1**

Add `CognitiveMemoryRetriever` as the primary retrieval mechanism.
Retain `CaseMemoryStore` for Layer 2 (scan).

```java
private final @Nullable CognitiveMemoryRetriever memoryRetriever;
private final @Nullable CaseMemoryStore memoryStore;
private final @Nullable MoodOrchestrator moodOrchestrator;
private final @Nullable CognitionConfig config;

public GutFeelingParticipant(
        @Nullable CognitiveMemoryRetriever memoryRetriever,
        @Nullable CaseMemoryStore memoryStore,
        @Nullable MoodOrchestrator moodOrchestrator,
        CognitionConfig config) {
    this.memoryRetriever = memoryRetriever;
    this.memoryStore = memoryStore;
    this.moodOrchestrator = moodOrchestrator;
    this.config = config;
}
```

Keep backward-compatible constructors:
```java
public GutFeelingParticipant(
        @Nullable CaseMemoryStore memoryStore,
        @Nullable MoodOrchestrator moodOrchestrator,
        CognitionConfig config) {
    this(null, memoryStore, moodOrchestrator, config);
}

public GutFeelingParticipant(
        @Nullable CaseMemoryStore memoryStore,
        @Nullable MoodOrchestrator moodOrchestrator) {
    this(null, memoryStore, moodOrchestrator, null);
}
```

Update Layer 1 query in `tick()`:
```java
// Layer 1: experience search — use retriever when available, fall back to raw store
List<Memory> matches;
if (memoryRetriever != null) {
    matches = memoryRetriever.query(query);
} else if (memoryStore != null) {
    matches = memoryStore.query(query);
} else {
    return;
}
```

Layer 2 (affect scan) continues using `memoryStore.scan()` directly.

- [ ] **Step 4: Update CognitionCore.configureGutFeeling()**

Change the method to also accept the retriever:

```java
public void configureGutFeeling(
        @Nullable CaseMemoryStore memoryStore,
        @Nullable MoodOrchestrator moodOrchestrator) {
    if (memoryStore == null) { return; }
    this.gutFeelingParticipant = new GutFeelingParticipant(
            cognitiveMemoryRetriever, memoryStore, moodOrchestrator, config);
    addParticipant(CognitionPhase.DERIVED, this.gutFeelingParticipant);
}
```

- [ ] **Step 5: Run all GutFeelingParticipant tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=GutFeelingParticipantTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: ALL PASS

- [ ] **Step 6: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/gut/GutFeelingParticipant.java cognition/src/test/java/io/casehub/neocortex/cognition/gut/GutFeelingParticipantTest.java cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java
git commit -m "feat(#750): integrate CognitiveMemoryRetriever into GutFeelingParticipant

Layer 1 (experience search) uses modulated retrieval for mood-congruent
gut reactions. Layer 2 (affect scan) stays on raw CaseMemoryStore.

Refs #750"
```

## Batch 3: Orchestrator LLM Prompt Integration

### Task 4: Add modulated memories to StrategyLearningOrchestrator reflection

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/strategy/StrategyLearningOrchestrator.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/strategy/StrategyLearningOrchestratorTest.java`

**Interfaces:**
- Consumes: `CognitiveMemoryRetriever.query(MemoryQuery)` — via `ExperienceQuery.forAgent(agentId, tenantId).withLimit(5)`
- Produces: Enhanced reflection prompt with supplementary memories section

- [ ] **Step 1: Write failing test — reflection prompt includes modulated memories**

```java
@Test
void reflect_includesModulatedMemoriesInPrompt() {
    // Create store with experience memories
    var memoryStore = stubCaseMemoryStore(List.of(
            experienceMemory("Positive collaboration on creative project")));
    var retriever = new CognitiveMemoryRetriever(memoryStore, List.of(), List.of());

    var orchestratorWithRetriever = new StrategyLearningOrchestrator(
            strategyMemory, reflectionOrchestrator,
            StrategyLearningConfig.defaults(), clock, mockSessionPipeline(), retriever);

    // Record enough signals and conversations to trigger reflection
    // ... (use existing test patterns from setUp)
    // Capture the user prompt sent to the LLM
    // Verify it contains "Relevant experience memories"
}
```

The exact test structure depends on how the existing tests capture LLM
prompts. Use Mockito `ArgumentCaptor` on the `SessionPipeline` mock.

- [ ] **Step 2: Run test to verify it fails**

Expected: compilation failure — no constructor accepting `CognitiveMemoryRetriever`

- [ ] **Step 3: Add CognitiveMemoryRetriever to constructor**

```java
private final @Nullable CognitiveMemoryRetriever memoryRetriever;

public StrategyLearningOrchestrator(StrategyMemory strategyMemory,
                             ReflectionOrchestrator reflectionOrchestrator,
                             StrategyLearningConfig config,
                             Clock clock,
                             @Nullable SessionPipeline sessionPipeline,
                             @Nullable CognitiveMemoryRetriever memoryRetriever) {
    this.strategyMemory         = strategyMemory;
    this.reflectionOrchestrator = reflectionOrchestrator;
    this.config                 = config;
    this.clock                  = clock;
    this.sessionPipeline        = sessionPipeline;
    this.memoryRetriever        = memoryRetriever;
}
```

Add backward-compatible constructor:
```java
public StrategyLearningOrchestrator(StrategyMemory strategyMemory,
                             ReflectionOrchestrator reflectionOrchestrator,
                             StrategyLearningConfig config,
                             Clock clock,
                             @Nullable SessionPipeline sessionPipeline) {
    this(strategyMemory, reflectionOrchestrator, config, clock, sessionPipeline, null);
}
```

- [ ] **Step 4: Add modulated memories to buildReflectionPrompt()**

At the end of `buildReflectionPrompt()`, before the final guideline instruction:

```java
if (memoryRetriever != null) {
    var memories = memoryRetriever.query(
            ExperienceQuery.forAgent(agentId, tenantId).withLimit(5));
    if (!memories.isEmpty()) {
        sb.append("\nRelevant experience memories:\n");
        for (var m : memories) {
            var text = m.text();
            if (text != null && !text.isBlank()) {
                sb.append("  - ").append(text.length() > 120 ? text.substring(0, 120) : text).append("\n");
            }
        }
    }
}
```

Note: `buildReflectionPrompt` needs `agentId` and `tenantId` parameters added.
Currently it receives `StrategyProfile` and `TrendProfile`. Thread `agentId`
and `tenantId` from the callers (`doReflect`, `doReflectAsync`).

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=StrategyLearningOrchestratorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/strategy/StrategyLearningOrchestrator.java cognition/src/test/java/io/casehub/neocortex/cognition/strategy/StrategyLearningOrchestratorTest.java
git commit -m "feat(#750): add modulated memory context to strategy reflection

StrategyLearningOrchestrator.doReflect() includes mood-congruent
experience memories in the LLM reflection prompt.

Refs #750"
```

### Task 5: Add modulated memories to MentalModelOrchestrator BDI extraction

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestratorTest.java`

**Interfaces:**
- Consumes: `CognitiveMemoryRetriever.query(MemoryQuery)` — via `ExperienceQuery.forAgent(agentId, tenantId).withLimit(5)`

- [ ] **Step 1: Write failing test — BDI prompt includes modulated memories**

Follow the same pattern as Task 4: mock SessionPipeline, capture the user
prompt, verify it contains supplementary memory text when retriever is
available.

- [ ] **Step 2: Add CognitiveMemoryRetriever to constructor**

Same pattern: new parameter `@Nullable CognitiveMemoryRetriever memoryRetriever`,
backward-compatible constructor delegating with null.

- [ ] **Step 3: Include modulated memories in BDI extraction prompt**

In the method that builds the BDI extraction prompt (where `BDI_EXTRACTION_PROMPT`
is used as system prompt and user message is constructed), append modulated
memories:

```java
if (memoryRetriever != null) {
    var memories = memoryRetriever.query(
            ExperienceQuery.forAgent(agentId, tenantId).withLimit(5));
    if (!memories.isEmpty()) {
        promptBuilder.append("\n\nPrior relevant experiences:\n");
        for (var m : memories) {
            var text = m.text();
            if (text != null && !text.isBlank()) {
                promptBuilder.append("- ").append(
                        text.length() > 120 ? text.substring(0, 120) : text).append("\n");
            }
        }
    }
}
```

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=MentalModelOrchestratorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestratorTest.java
git commit -m "feat(#750): add modulated memory context to mental model BDI extraction

MentalModelOrchestrator includes mood-biased experience memories in the
BDI inference prompt, grounding theory-of-mind in the agent's subjective
experiential state.

Refs #750"
```

### Task 6: Add modulated memories to UserModelOrchestrator profile synthesis

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/usermodel/UserModelOrchestrator.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/usermodel/UserModelOrchestratorTest.java` (does not exist yet)

**Interfaces:**
- Consumes: `CognitiveMemoryRetriever.query(MemoryQuery)` — via `ExperienceQuery.forAgent(agentId, tenantId).withLimit(5)`

- [ ] **Step 1: Write test — profile synthesis includes modulated memories**

Follow the same pattern as Tasks 4-5.

- [ ] **Step 2: Add CognitiveMemoryRetriever to constructor**

Same pattern as other orchestrators.

- [ ] **Step 3: Include modulated memories in synthesis prompt**

In the method that builds the profile synthesis LLM prompt, append modulated
memories before the final instruction.

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=UserModelOrchestratorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/usermodel/UserModelOrchestrator.java cognition/src/test/java/io/casehub/neocortex/cognition/usermodel/UserModelOrchestratorTest.java
git commit -m "feat(#750): add modulated memory context to user model synthesis

UserModelOrchestrator includes recency-weighted experience memories in
the profile synthesis prompt.

Refs #750"
```

## Batch 4: Full Build Verification

### Task 7: Full module build + update issue description

**Files:**
- No new files — verification only

- [ ] **Step 1: Full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS

- [ ] **Step 2: Verify test counts haven't dropped**

Check that no tests were accidentally excluded.

- [ ] **Step 3: Update issue #750 description**

Add a comment noting the actual integration points differ from the original
description (CBR vs CaseMemoryStore), and list what was implemented.

- [ ] **Step 4: Final commit if any remaining changes**

## References

- [specs/issue-750-integrate-cognitive-memory-retriever/2026-11-01-cognitive-memory-retriever-integration-design.md] — design spec
- [CognitiveMemoryRetriever.java] — tick-scoped context target
- [CognitionCore.java:224-290] — tick method where context is set
- [GutFeelingParticipant.java:57] — existing CaseMemoryStore.query() call
- [StrategyLearningOrchestrator.java:484-526] — buildReflectionPrompt()
- [CognitionDefaultBeans.java:239-281] — CDI producer for retriever
- [CognitionCoreFactory.java:104-105] — gutFeeling wiring
- [GitHub #750] — focal issue
- [GitHub #736] — parent issue (CognitiveMemoryRetriever creation)
- [specs/issue-253-cognitive-rearchitecture/2026-08-31-retrieval-modulation-design.md] — original modulation design
