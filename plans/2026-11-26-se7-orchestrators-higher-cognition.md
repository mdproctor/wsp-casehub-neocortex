# SE7: Orchestrators & Higher Cognition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1227 — SE7: Orchestrators & Higher Cognition
**Issue group:** #1227 (all findings under single issue)

**Goal:** Fix 16 bugs across signal gates, goal orchestration, memory hygiene, narrative/reflection, personality, and belief revision in the cognition module.

**Architecture:** All changes are in `cognition/` and `cognition-api/` modules. Each batch is independently testable. The spec's 6-batch structure maps directly to plan batches. E4 requires a record change in cognition-api (`AttributedState`); E8 requires formula change in cognition-api (`RetentionScore`, `RetentionConfig`).

**Tech Stack:** Java 21, Quarkus 3.32.2, JUnit 5

## Global Constraints

- Java 21 source (Java 26 JVM)
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Module test: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl cognition`
- All commits reference #1227: `Refs #1227`
- No new modules — all changes in existing files

---

## Batch 1: Signal Gates & Synthesis (E1, E4)

### Task 1: Fix confidence decay compounding (E4)

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/AttributedState.java:6`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java:283-299`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestratorTest.java`

**Interfaces:**
- Modifies: `AttributedState` record — adds `originalConfidence` field (8th field)
- Produces: Idempotent decay computation in `decayMap()`

- [ ] **Step 1: Write failing test for compounding decay**

Create a test that ticks twice and asserts confidence doesn't compound. The current code decays from already-decayed values, so after 2 ticks the confidence will be lower than it should be.

```java
@Test
void decayDoesNotCompoundAcrossTicks() {
    // Setup: add a mental model entry with known confidence
    var state = new AttributedState("key", "desc", 0.8, 1, Instant.now().minus(1, ChronoUnit.HOURS),
            BdiDimension.BELIEF, IntentValence.POSITIVE, 0.8);
    // After 1 hour with 24h half-life:
    // Correct: 0.8 * pow(0.5, 1/24) = 0.8 * 0.9715 = 0.7772
    // Tick 1 at +1h, Tick 2 at +1h (2h total):
    // Correct: 0.8 * pow(0.5, 2/24) = 0.8 * 0.9439 = 0.7551
    // Compounding bug would give: 0.7772 * pow(0.5, 2/24) = lower
    // Assert the 2-tick result matches the idempotent 2h computation
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="MentalModelOrchestratorTest#decayDoesNotCompoundAcrossTicks" -Dsurefire.failIfNoSpecifiedTests=false`

- [ ] **Step 3: Add `originalConfidence` to AttributedState record**

Use `ide_replace_member` to update the `AttributedState` record in cognition-api. Add `originalConfidence` as the 8th field. Update all construction sites — search with `ide_find_references` for `AttributedState` to find all callers.

```java
public record AttributedState(
    String key, String description, double confidence,
    int entrenchment, Instant lastReinforced,
    BdiDimension dimension, IntentValence valence,
    double originalConfidence
) {}
```

- [ ] **Step 4: Fix `decayMap()` to use idempotent recomputation**

In `MentalModelOrchestrator.java:283-299`, replace the current decay logic:

```java
// Before (compounding):
// s.confidence() * Math.pow(0.5, elapsedMs / halfLifeMs)

// After (idempotent):
double totalElapsedMs = Duration.between(s.lastReinforced(), now).toMillis();
double decayed = s.originalConfidence() * Math.pow(0.5, (double) totalElapsedMs / halfLifeMs);
// Update confidence to decayed value (don't touch originalConfidence or lastReinforced)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="MentalModelOrchestratorTest#decayDoesNotCompoundAcrossTicks" -Dsurefire.failIfNoSpecifiedTests=false`

- [ ] **Step 6: Run full module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api,cognition`

- [ ] **Step 7: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/AttributedState.java cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java cognition/src/test/
git commit -m "fix(cognition): idempotent confidence decay in MentalModelOrchestrator (E4)

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: Fix signal gates in all three orchestrators (E1)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java:181-186,311-320,584,609-616`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/usermodel/UserModelOrchestrator.java:184-195,277-286,466`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/strategy/StrategyLearningOrchestrator.java:180-261`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestratorTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/usermodel/UserModelOrchestratorTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/strategy/StrategyLearningOrchestratorTest.java`

**Interfaces:**
- Consumes: `SignificanceAccumulator` pattern from `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceAccumulator.java:21` (reference only — not a code dependency)
- Produces: Signal accumulation across ticks for all three orchestrators

- [ ] **Step 1: Write failing test — MentalModelOrchestrator synthesis fires after 3 ticks**

```java
@Test
void synthesisFiresAfterAccumulatingThreeSignals() {
    // Tick 1: add 1 signal → no synthesis
    // Tick 2: add 1 signal → no synthesis (2 accumulated)
    // Tick 3: add 1 signal → synthesis fires (3 >= threshold)
    // Assert: LLM synthesis was invoked after tick 3
}
```

- [ ] **Step 2: Run test to verify it fails** (currently signals are drained each tick)

- [ ] **Step 3: Fix MentalModelOrchestrator signal gate**

In `MentalModelOrchestrator.java`:
1. Remove the `drainBuffer()` call from `doTick()` before the threshold check (line ~185)
2. In `shouldInfer()` (line 311-320): check `signalBuffer.size() >= config.minSignalsForInference()` without draining
3. Only drain when threshold is met and synthesis fires
4. Add buffer cap (50): if `signalBuffer.size() >= MAX_BUFFER_SIZE`, force drain and synthesize

```java
private static final int MAX_BUFFER_SIZE = 50;

// In doTick / shouldInfer:
int accumulated = state.signalBuffer.size();
if (accumulated < config.minSignalsForInference() && accumulated < MAX_BUFFER_SIZE) {
    return; // keep accumulating
}
// Threshold met or buffer full — drain and synthesize
String text = drainBuffer(state);
// ... run LLM synthesis with text ...
```

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Write failing test — UserModelOrchestrator synthesis fires after accumulated lines**

Similar pattern to MentalModel but using the `StringBuilder textBuffer` (line 466). The gate check at `shouldSynthesise()` (line 277-286) counts newlines in the drained text.

- [ ] **Step 6: Fix UserModelOrchestrator signal gate**

In `UserModelOrchestrator.java`:
1. Keep appending to `textBuffer` across ticks without clearing
2. In `shouldSynthesise()` (line 277-286): check accumulated line count against threshold
3. Only clear buffer when synthesis fires
4. Add buffer size cap

- [ ] **Step 7: Run UserModelOrchestrator test**

- [ ] **Step 8: Write failing test — StrategyLearningOrchestrator fires on cumulative count**

The root cause is different: data IS preserved, but the gate uses `drainedTurns.size()` (current batch) instead of `state.totalSignals` (cumulative).

```java
@Test
void strategyFiresOnCumulativeSignalCount() {
    // Tick 1: 1 signal → totalSignals=1, drainedTurns=1 → gate: drainedTurns.size() < threshold → no synthesis
    // Tick 2: 1 signal → totalSignals=2, drainedTurns=1 → gate: drainedTurns.size() < threshold → no synthesis
    // Tick 3: 1 signal → totalSignals=3 → should fire
    // Assert: synthesis fires at tick 3
}
```

- [ ] **Step 9: Fix StrategyLearningOrchestrator gate check**

In `StrategyLearningOrchestrator.java` around line 210, change the gate:

```java
// Before: drainedTurns.size() < config.minSignalsForConversationCase()
// After: state.totalSignals < config.minSignalsForConversationCase()
```

- [ ] **Step 10: Run all signal gate tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="MentalModelOrchestratorTest,UserModelOrchestratorTest,StrategyLearningOrchestratorTest" -Dsurefire.failIfNoSpecifiedTests=false`

- [ ] **Step 11: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/ cognition/src/main/java/io/casehub/neocortex/cognition/usermodel/ cognition/src/main/java/io/casehub/neocortex/cognition/strategy/ cognition/src/test/
git commit -m "fix(cognition): accumulate signals across ticks before synthesis (E1)

MentalModel/UserModel: accumulate without draining, cap at 50.
Strategy: use cumulative state.totalSignals instead of drainedTurns.size().

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 2: Memory Hygiene (E8, E9)

### Task 3: Retention formula first-principles redesign (E8)

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/memory/RetentionScore.java:5-27`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/memory/RetentionConfig.java:3-16`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/memory/MemoryHygieneOrchestratorImpl.java:140-148`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/memory/RetentionScoreTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/memory/MemoryHygieneOrchestratorImplTest.java`

**Interfaces:**
- Modifies: `RetentionScore.compute()` — new signature with recency + frequency base, confidence × trust multiplier
- Modifies: `RetentionConfig` — new fields: `recencyWeight`, `frequencyWeight` (replaces confidence/scope/trust weights)
- Produces: Memories with low recency + low frequency now score near 0 and can be evicted

- [ ] **Step 1: Write failing test — old unaccessed memory scores below eviction threshold**

```java
@Test
void oldUnaccessedMemoryScoresBelowEvictionThreshold() {
    double score = RetentionScore.compute(
        "case1", "entity1",
        1.0,    // confidence (default)
        0.0,    // recencyFactor (very old)
        0.0,    // frequencyFactor (never accessed)
        1.0,    // trustFactor (default)
        RetentionConfig.DEFAULT
    );
    assertThat(score).isLessThan(RetentionConfig.DEFAULT.retentionThreshold());
}
```

- [ ] **Step 2: Run test — currently passes at 0.33 (above 0.1 threshold) → FAIL assertion**

- [ ] **Step 3: Redesign RetentionConfig**

```java
public record RetentionConfig(
    double retentionThreshold,
    double recencyWeight,
    double frequencyWeight
) {
    public static final RetentionConfig DEFAULT = new RetentionConfig(0.1, 1.0, 1.0);
}
```

- [ ] **Step 4: Redesign RetentionScore.compute()**

```java
public static double compute(String caseId, String entityId,
        double confidence, double recencyFactor, double frequencyFactor,
        double trustFactor, RetentionConfig config) {
    double base = (config.recencyWeight() * recencyFactor + config.frequencyWeight() * frequencyFactor)
                  / (config.recencyWeight() + config.frequencyWeight());
    double modulator = confidence * trustFactor;
    return base * modulator;
}
```

- [ ] **Step 5: Update MemoryHygieneOrchestratorImpl call site**

At line 140-148, update the `compute()` call to pass `frequencyFactor` instead of `scopeFactor`. Derive `frequencyFactor` from access count or retrieval strength.

- [ ] **Step 6: Fix all compilation errors from signature change**

Use `ide_find_references` on `RetentionScore.compute` and `RetentionConfig` to find all callers. Update each. Update test helpers like `WeightedScorer`, `CompositeConfidenceScorer`, etc.

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api,cognition`

- [ ] **Step 8: Commit**

```bash
git add cognition-api/ cognition/
git commit -m "fix(cognition): redesign retention formula — base score from recency + frequency (E8)

Confidence × trust as multiplicative modulators instead of additive terms.
Removes scopeFactor (always 1.0). Old unaccessed memories now evictable.

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 4: Fix hygiene grouping with pairwise similarity (E9)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/memory/MemoryHygieneOrchestratorImpl.java:42,231-249`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/memory/MemoryHygieneOrchestratorImplTest.java`

**Interfaces:**
- Consumes: `Instance<EmbeddingModel>` (CDI optional injection)
- Consumes: `crossLinkSimilarityThreshold` field (line 42)
- Produces: Correct pairwise grouping of semantically similar memories

- [ ] **Step 1: Write failing test — unrelated memories not grouped despite high query scores**

```java
@Test
void unrelatedMemoriesNotGroupedDespiteHighQueryScores() {
    // Two memories about different topics, both with high query relevance score
    // Current code groups them (both score > threshold vs query)
    // Correct: they should NOT be grouped (low pairwise similarity)
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Inject `Instance<EmbeddingModel>` into MemoryHygieneOrchestratorImpl**

Add constructor parameter: `@Any Instance<EmbeddingModel> embeddingModel`

- [ ] **Step 4: Rewrite `findSimilarGroups()` with pairwise cosine**

```java
private List<List<Memory>> findSimilarGroups(List<Memory> candidates) {
    if (!embeddingModel.isResolvable()) {
        return List.of(); // skip grouping when no embedding available
    }
    EmbeddingModel model = embeddingModel.get();
    // Batch embed all candidate texts
    List<String> texts = candidates.stream().map(Memory::text).toList();
    List<Embedding> embeddings = model.embedAll(texts.stream()
        .map(TextSegment::from).toList()).content();
    // Greedy single-pass grouping by pairwise cosine similarity
    // Use crossLinkSimilarityThreshold (existing config field)
    // ...
}
```

- [ ] **Step 5: Run tests**

- [ ] **Step 6: Commit**

```bash
git add cognition/
git commit -m "fix(cognition): pairwise cosine similarity for hygiene grouping (E9)

Replaces query-score-vs-threshold with embedding-based pairwise
comparison. Uses existing crossLinkSimilarityThreshold config.
Skips grouping gracefully when EmbeddingModel unavailable.

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 3: Goal Orchestration (E10)

### Task 5: Fix goal tick result capture + cleanup (E10e, E10b, E10c, E10d)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java:264-461,1537-1543`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/goal/CognitiveGoalOrchestrator.java:80-187`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java:255-262,597`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/core/CognitionCoreTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/goal/CognitiveGoalOrchestratorTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestratorTest.java`

**Interfaces:**
- Modifies: `CognitionCore` — add `safeCall(Supplier<T>)` or inline try-catch for goal tick
- Modifies: `CognitiveGoalOrchestrator.queryGoals()` — add agent filter
- Removes: `CognitiveGoalOrchestrator.recordSurfacing()` and `recordEmotions()` calls

- [ ] **Step 1: Write failing test — goal tick return value is consumed**

```java
@Test
void goalTickResultIsNotDiscarded() {
    // Setup: configure goal proposal to return a proposal
    // Tick CognitionCore
    // Assert: proposal was processed (not silently discarded by safeRun)
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add `safeCall()` to CognitionCore and fix goal tick**

At `CognitionCore.java`, add alongside `safeRun()` (line 1537-1543):

```java
private <T> T safeCall(Supplier<T> action) {
    try {
        return action.get();
    } catch (Exception e) {
        log.warn("Safe call failed", e);
        return null;
    }
}
```

Replace the goal tick call (within lines 264-461):
```java
// Before: safeRun(() -> goals.tick(agentId, tenantId, descriptor));
// After:
var goalResult = safeCall(() -> goals.tick(agentId, tenantId, descriptor));
if (goalResult != null) {
    // Process proposals, abandonments, priority adjustments
}
```

- [ ] **Step 4: Write test — queryGoals filters by agent**

```java
@Test
void queryGoalsFiltersToCurrentAgent() {
    // Setup: add goals for agent-A and agent-B in same tenant
    // Query as agent-A
    // Assert: only agent-A's goals returned
}
```

- [ ] **Step 5: Fix queryGoals agent filter**

In `CognitiveGoalOrchestrator.java:119-126`:
```java
// After querying, filter by agent-id property:
.filter(node -> agentId.equals(node.property("agent-id")))
```

- [ ] **Step 6: Write test — no experience memories from goal surfacing**

```java
@Test
void goalSurfacingDoesNotWriteExperienceMemories() {
    // Tick with active goals
    // Assert: no experience memories recorded (memoryStore not called)
}
```

- [ ] **Step 7: Remove recordSurfacing() and recordEmotions() calls**

In `CognitiveGoalOrchestrator.java:108-109`, remove the calls to `recordSurfacing()` and `recordEmotions()`. Optionally remove the methods themselves if no other callers exist (verify with `ide_find_references`).

- [ ] **Step 8: Fix cachedProposals not cleared on NoChange**

In `GoalProposalOrchestrator.java:255-262`, add `cachedProposals = null;` (or `.clear()`) in the `NoChange` return path.

- [ ] **Step 9: Run all goal tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="CognitionCoreTest,CognitiveGoalOrchestratorTest,GoalProposalOrchestratorTest" -Dsurefire.failIfNoSpecifiedTests=false`

- [ ] **Step 10: Commit**

```bash
git add cognition/
git commit -m "fix(cognition): capture goal tick results, filter by agent, remove memory pollution (E10)

E10e: safeCall() captures GoalProposalTick return value.
E10b: clear cachedProposals on NoChange path.
E10c: queryGoals filters by agent-id property.
E10d: remove recordSurfacing/recordEmotions — not experiences.

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 6: Wire deductive strategy context (E10a)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java:50-73,285-304`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestratorTest.java`

**Interfaces:**
- Consumes: `CognitiveDefaultsRegistry.forAgent()` → `CognitiveDefaults.dispositionAxes()`
- Consumes: `MoodOrchestrator.currentMood(agentId, tenantId)`
- Consumes: `CaseMemoryStore.search()` for beliefs and recent experiences
- Modifies: `GoalProposalOrchestrator` constructor — adds 3 new `Instance<>` dependencies

- [ ] **Step 1: Write failing test — deductive strategy receives populated context**

```java
@Test
void deductiveStrategyReceivesPopulatedContext() {
    // Setup: cognitive profile with known disposition, mood state, stored beliefs
    // Tick goal proposal
    // Assert: DeductiveFormationContext passed to strategy has non-null disposition, mood, non-empty beliefs
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add constructor dependencies**

Add to `GoalProposalOrchestrator` constructor (line 50-73):
```java
@Inject Instance<CognitiveDefaultsRegistry> cognitiveDefaultsRegistry,
@Inject Instance<MoodOrchestrator> moodOrchestrator,
@Inject Instance<CaseMemoryStore> memoryStore,
```

Use `Instance<>` for graceful degradation — when unavailable, `evaluateDeductive()` falls back to null/empty context (current behavior, but now explicit).

- [ ] **Step 4: Wire context into evaluateDeductive()**

In `GoalProposalOrchestrator.java:285-304`:
```java
DispositionAxes disposition = cognitiveDefaultsRegistry.isResolvable()
    ? cognitiveDefaultsRegistry.get().forAgentOrDefaults(agentId).dispositionAxes()
    : null;
MoodState mood = moodOrchestrator.isResolvable()
    ? moodOrchestrator.get().currentMood(agentId, tenantId)
    : null;
// Query beliefs and recent experiences from CaseMemoryStore...
var context = new DeductiveFormationContext(disposition, mood, beliefs, memories);
```

- [ ] **Step 5: Run tests**

- [ ] **Step 6: Commit**

```bash
git add cognition/
git commit -m "fix(cognition): wire cognitive context into deductive goal formation (E10a)

GoalProposalOrchestrator now passes disposition, mood, beliefs, and
recent experiences to DeductiveFormationContext. Graceful degradation
via Instance<> when subsystems unavailable.

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 4: Narrative, Reflection & Sub-thoughts (E7, E12, E17)

### Task 7: Fix narrative partition, sub-thought attribution, reflection heuristics

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/ReflectionEventAdapter.java:17-18,29-44`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtTickParticipant.java:71-85`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/reflection/LlmReflectionSynthesizer.java:258-296`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/narrative/ReflectionEventAdapterTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/subthought/SubThoughtTickParticipantTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/reflection/LlmReflectionSynthesizerTest.java`

**Interfaces:**
- Modifies: `ReflectionEventAdapter` watermark key — `agentId + ":" + tenantId`
- Modifies: `SubThoughtTickParticipant.pushToMentalModel()` — type filter (INTENTION only)
- Modifies: `LlmReflectionSynthesizer.parseHeuristic()` — fallback when sources unresolvable

- [ ] **Step 1: Write failing test — E7 narrative partitions by agent**

```java
@Test
void narrativePartitionsByAgentNotTenant() {
    // Publish reflections for agent-A and agent-B in same tenant
    // Assert: separate watermarks per agent (agent-A:tenant1, agent-B:tenant1)
}
```

- [ ] **Step 2: Fix ReflectionEventAdapter partition key**

In `ReflectionEventAdapter.java:29-44`, change the watermark key construction:
```java
// Before: watermarks.computeIfAbsent(tenantId, ...)
// After: watermarks.computeIfAbsent(agentId + ":" + tenantId, ...)
```

- [ ] **Step 3: Write failing test — E12 only INTENTION feeds mental model**

```java
@Test
void onlyIntentionSubThoughtsFeedMentalModel() {
    // Create sub-thoughts: INTENTION, CONCERN, AFFECT_OBSERVATION
    // Push to mental model
    // Assert: only INTENTION was forwarded, others filtered
}
```

- [ ] **Step 4: Fix SubThoughtTickParticipant type filter**

In `SubThoughtTickParticipant.java:71-85`:
```java
private void pushToMentalModel(List<ParsedSubThought> subThoughts, ...) {
    subThoughts.stream()
        .filter(st -> SubThoughtTypes.INTENTION.equals(st.type()))
        .forEach(st -> {
            // existing mental model push logic
        });
}
```

- [ ] **Step 5: Write failing test — E17 heuristic accepted without exact source**

```java
@Test
void heuristicAcceptedWithUnresolvableSources() {
    // LLM produces heuristic with hallucinated source_turns
    // Assert: heuristic is still returned (with lower confidence), not silently dropped
}
```

- [ ] **Step 6: Fix LlmReflectionSynthesizer heuristic acceptance**

In `LlmReflectionSynthesizer.java:258-296`:
```java
// After trying source_turns resolution:
if (sourceMemoryIds.isEmpty() && sourceCases != null && !sourceCases.isEmpty()) {
    sourceMemoryIds = resolveFromCases(sourceCases);
}
// Accept heuristic even with empty sources — lower confidence
double confidence = sourceMemoryIds.isEmpty() ? 0.3 : defaultConfidence;
if (sourceMemoryIds.isEmpty()) {
    log.warn("Heuristic accepted without source linkage: {}", heuristic.insight());
}
// Don't return null / don't skip
```

- [ ] **Step 7: Run all three tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="ReflectionEventAdapterTest,SubThoughtTickParticipantTest,LlmReflectionSynthesizerTest" -Dsurefire.failIfNoSpecifiedTests=false`

- [ ] **Step 8: Commit**

```bash
git add cognition/
git commit -m "fix(cognition): narrative partition, sub-thought filter, heuristic acceptance (E7, E12, E17)

E7: partition by agentId:tenantId, not tenantId alone.
E12: only INTENTION sub-thoughts feed mental model.
E17: accept heuristics with unresolvable sources at 0.3 confidence.

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 5: Personality & Constraints (E14, E15)

### Task 8: Fix personality baseline + dt scaling and constraint tiers

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/situational/PersonalityStateIntegrator.java:78-96,179-181`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/TierFilterCustomizer.java:25-42,83-88`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/situational/PersonalityStateIntegratorTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/prompt/TierFilterCustomizerTest.java`

**Interfaces:**
- Modifies: `PersonalityStateIntegrator.baselineFor()` — resolves from cognitive profile
- Modifies: `PersonalityStateIntegrator.pull()` — scales alpha by dt
- Modifies: `TierFilterCustomizer.TIER_MAP` — ConstraintPromptSection → CONTEXTUAL
- Modifies: `TierFilterCustomizer.tierOf()` — default → CONTEXTUAL

- [ ] **Step 1: Write failing test — E14 baseline from profile, not 0.5**

```java
@Test
void baselineReflectsAgentProfile() {
    // Setup: agent with known PID-5 facet values (e.g., anxiousness = 0.7)
    // Assert: baselineFor("anxiousness") returns 0.7, not 0.5
}
```

- [ ] **Step 2: Wire baselineFor() to CognitiveDefaultsRegistry**

In `PersonalityStateIntegrator.java:179-181`:
```java
// Before: return 0.5;
// After: resolve from cognitive profile
double baselineFor(String facetName) {
    if (cognitiveDefaults != null) {
        var pid5 = cognitiveDefaults.pid5Facets();
        if (pid5 != null && pid5.containsKey(facetName)) {
            return pid5.get(facetName);
        }
    }
    return 0.5; // fallback
}
```

- [ ] **Step 3: Write failing test — E14 pull rate independent of tick frequency**

```java
@Test
void pullRateIndependentOfTickFrequency() {
    // Pull with dt=1.0 (normal tick) → displacement X
    // Pull with dt=0.5 (double frequency) × 2 → displacement ~X
    // Assert: results approximately equal (within 5%)
}
```

- [ ] **Step 4: Scale alpha by dt in pull()**

In `PersonalityStateIntegrator.java:78-96`:
```java
// Before: facet * (1 - alpha) + baseline * alpha
// After:
double effectiveAlpha = 1.0 - Math.pow(1.0 - alpha, dt);
// facet * (1 - effectiveAlpha) + baseline * effectiveAlpha
```

- [ ] **Step 5: Write failing test — E15 constraints in CONTEXTUAL tier**

```java
@Test
void constraintSectionInContextualTier() {
    var tier = customizer.tierOf(ConstraintPromptSection.class);
    assertThat(tier).isEqualTo(SectionTier.CONTEXTUAL);
}

@Test
void unknownSectionDefaultsToContextual() {
    var tier = customizer.tierOf(SomeUnregisteredSection.class);
    assertThat(tier).isEqualTo(SectionTier.CONTEXTUAL);
}
```

- [ ] **Step 6: Fix TierFilterCustomizer**

In `TierFilterCustomizer.java`:
1. Line ~41 (TIER_MAP): move `ConstraintPromptSection.class` from SUPPLEMENTARY to CONTEXTUAL
2. Line 83-88 (`tierOf()`): change default from `SectionTier.CORE` to `SectionTier.CONTEXTUAL`

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="PersonalityStateIntegratorTest,TierFilterCustomizerTest" -Dsurefire.failIfNoSpecifiedTests=false`

- [ ] **Step 8: Commit**

```bash
git add cognition/
git commit -m "fix(cognition): personality baselines from profile, dt-scaled pull, tier fixes (E14, E15)

E14: baselineFor() resolves from CognitiveDefaultsRegistry, pull() scales
alpha by dt for tick-frequency independence.
E15: ConstraintPromptSection → CONTEXTUAL tier, default → CONTEXTUAL.

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 6: Remaining Orchestrators (E2, E5, E6, E16)

### Task 9: Fix quality signal timing + relational schema cursor (E2, E5)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java:160,636-650`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/relationship/RelationalSchemaEvolutionPhase.java:85-199`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/core/CognitionCoreTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/relationship/RelationalSchemaEvolutionPhaseTest.java`

**Interfaces:**
- Modifies: `CognitionCore.deriveQualitySignal()` — uses post-response mood delta
- Modifies: `RelationalSchemaEvolutionPhase.run()` — cursor-based incremental processing

- [ ] **Step 1: Write failing test — E2 quality derived from post-response delta**

```java
@Test
void qualitySignalReflectsPostResponseMood() {
    // Setup: pre-interaction mood pleasure = 0.3
    // Process interaction → agent response improves pleasure to 0.6
    // Assert: quality signal is POSITIVE (based on +0.3 delta during response)
}
```

- [ ] **Step 2: Fix deriveQualitySignal timing**

In `CognitionCore.java:636-650`, capture mood before response generation and compute delta after:
```java
InteractionSignal deriveQualitySignal(String agentId, String tenantId, String userMessage) {
    // Use postResponseMoodDelta instead of lastMoodDelta (pre-interaction)
    var delta = postResponseMoodDelta.get(agentId);
    // ... same threshold logic but on post-response delta ...
}
```

Add `postResponseMoodDelta` field alongside `lastMoodDelta` (line 160), populated after response generation.

- [ ] **Step 3: Write failing test — E5 relational schema uses cursor**

```java
@Test
void relationalSchemaOnlyProcessesNewMemories() {
    // Run once with 10 memories → processes all 10, saves cursor
    // Add 3 new memories
    // Run again → processes only 3 new memories, not 13
}
```

- [ ] **Step 4: Add cursor to RelationalSchemaEvolutionPhase**

In `RelationalSchemaEvolutionPhase.java:85-116`, add cursor pattern:
```java
// Load cursor from MindMap (cursor node with name "relational-schema-cursor")
Instant cursor = loadCursor(tenantId);
// Query only memories after cursor
var newMemories = memoryStore.search(..., cursor);
// Process only new memories
// Advance cursor after successful processing
saveCursor(tenantId, latestTimestamp);
```

- [ ] **Step 5: Run tests**

- [ ] **Step 6: Commit**

```bash
git add cognition/
git commit -m "fix(cognition): post-response quality signal, relational schema cursor (E2, E5)

E2: deriveQualitySignal uses post-response mood delta, not pre-interaction.
E5: RelationalSchemaEvolutionPhase processes only new memories via cursor.

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 10: Fix pressure mapping + belief revision (E6, E16)

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/RelationshipPressureSource.java:27-42`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/personality/InteractionPressureSource.java:26-40`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/belief/BeliefRevisionPhase.java:71-134,143-182,304-321`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/RelationshipPressureSourceTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/personality/InteractionPressureSourceTest.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/belief/BeliefRevisionPhaseTest.java`

**Interfaces:**
- Modifies: `RelationshipPressureSource.translate()` — CAPS-driven facet mapping
- Modifies: `InteractionPressureSource.translate()` — same fix
- Modifies: `BeliefRevisionPhase.processAgent()` — adds reinforcement path
- Modifies: `BeliefRevisionPhase.run()` — per-agent cursor, exception-safe advancement

- [ ] **Step 1: Write failing test — E6 pressure maps to engaged facets**

```java
@Test
void pressureMapsToEngagedFacetsNotDominantAuxiliary() {
    // Setup: CAPS settling with active social_threat node
    // Quality signal: POSITIVE
    // Assert: pressure applied to relevant facet (e.g., agreeableness), not hardcoded dominant
}
```

- [ ] **Step 2: Fix RelationshipPressureSource and InteractionPressureSource**

In both `translate()` methods (lines 27-42 / 26-40):
```java
// Before: POSITIVE → dominant trait, NEGATIVE → auxiliary
// After: use CAPS activations or appraisal dimensions to determine which facets
// Fallback: conduciveness → competence, external-standards → agreeableness
```

- [ ] **Step 3: Write failing test — E16 belief reinforcement**

```java
@Test
void supportingEvidenceReinforcesBeliefConfidence() {
    // Setup: belief with confidence 0.6
    // Add supporting evidence (high similarity, same valence)
    // Run belief revision
    // Assert: confidence increased (e.g., 0.7)
}
```

- [ ] **Step 4: Add reinforcement path to BeliefRevisionPhase.processAgent()**

In `BeliefRevisionPhase.java:143-182`:
```java
// After existing erosion logic for contradictions:
// Add: when evidence supports (high similarity + same valence) → reinforce
if (similarity > config.supportThreshold() && sameValence) {
    double reinforced = Math.min(currentConfidence + config.reinforcementStep(), 1.0);
    // Update belief confidence
}
```

- [ ] **Step 5: Write failing test — E16 per-agent cursor**

```java
@Test
void beliefRevisionUsesPerAgentCursor() {
    // Setup: two agents in same tenant
    // Process beliefs for agent-A, advance cursor
    // Add new evidence
    // Process for agent-B → should process ALL evidence (agent-B's cursor is independent)
}
```

- [ ] **Step 6: Fix per-agent cursor in BeliefRevisionPhase.run()**

In `BeliefRevisionPhase.java:71-134`:
```java
// Before: single cursor node "belief-revision-cursor" per tenant
// After: cursor node "belief-revision-cursor:" + agentId per agent
// Only advance cursor AFTER processAgent succeeds:
try {
    processAgent(agentId, tenantId, evidence);
    saveCursor(agentId, tenantId, latestTimestamp);
} catch (Exception e) {
    log.warn("Belief revision failed for agent {}, cursor not advanced", agentId, e);
    // Cursor stays at previous position — evidence will be reprocessed
}
```

- [ ] **Step 7: Run all Batch 6 tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="RelationshipPressureSourceTest,InteractionPressureSourceTest,BeliefRevisionPhaseTest" -Dsurefire.failIfNoSpecifiedTests=false`

- [ ] **Step 8: Commit**

```bash
git add cognition/
git commit -m "fix(cognition): CAPS-driven pressure mapping, belief reinforcement + per-agent cursor (E6, E16)

E6: pressure maps to CAPS-activated facets instead of hardcoded dominant/auxiliary.
E16: reinforcement path (symmetry with erosion), per-agent cursors,
exception-safe cursor advancement. Feature remains disabled by default.

Refs #1227

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## References

- `specs/issue-1227-orchestrators-higher-cognition/2026-11-26-orchestrators-higher-cognition-design.md` — design spec
- `specs/issue-1227-orchestrators-higher-cognition/decisions.md` — 6 design decisions
- `cognition/src/main/java/io/casehub/neocortex/cognition/mentalmodel/MentalModelOrchestrator.java` — E1, E4
- `cognition/src/main/java/io/casehub/neocortex/cognition/usermodel/UserModelOrchestrator.java` — E1
- `cognition/src/main/java/io/casehub/neocortex/cognition/strategy/StrategyLearningOrchestrator.java` — E1
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/mentalmodel/AttributedState.java` — E4
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/memory/RetentionScore.java` — E8
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/memory/RetentionConfig.java` — E8
- `cognition/src/main/java/io/casehub/neocortex/cognition/memory/MemoryHygieneOrchestratorImpl.java` — E8, E9
- `cognition/src/main/java/io/casehub/neocortex/cognition/core/CognitionCore.java` — E2, E10e
- `cognition/src/main/java/io/casehub/neocortex/cognition/goal/GoalProposalOrchestrator.java` — E10a, E10b
- `cognition/src/main/java/io/casehub/neocortex/cognition/goal/CognitiveGoalOrchestrator.java` — E10c, E10d
- `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/ReflectionEventAdapter.java` — E7
- `cognition/src/main/java/io/casehub/neocortex/cognition/subthought/SubThoughtTickParticipant.java` — E12
- `cognition/src/main/java/io/casehub/neocortex/cognition/reflection/LlmReflectionSynthesizer.java` — E17
- `cognition/src/main/java/io/casehub/neocortex/cognition/prompt/TierFilterCustomizer.java` — E15
- `cognition/src/main/java/io/casehub/neocortex/cognition/situational/PersonalityStateIntegrator.java` — E14
- `cognition/src/main/java/io/casehub/neocortex/cognition/personality/RelationshipPressureSource.java` — E6
- `cognition/src/main/java/io/casehub/neocortex/cognition/personality/InteractionPressureSource.java` — E6
- `cognition/src/main/java/io/casehub/neocortex/cognition/relationship/RelationalSchemaEvolutionPhase.java` — E5
- `cognition/src/main/java/io/casehub/neocortex/cognition/belief/BeliefRevisionPhase.java` — E16
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SignificanceAccumulator.java` — E1 reference pattern
- casehubio/neocortex#1227 — focal issue
- casehubio/neocortex#1220 — parent epic
