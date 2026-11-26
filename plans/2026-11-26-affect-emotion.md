# SE6: Affect & Emotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1226 — SE6: Affect & Emotion
**Issue group:** #1226

**Goal:** Fix 14 bugs in the affect and emotion pipeline that cause mood to pin at extremes, drives to ignore personality, regulation to suppress positive emotions, and appraisal to miss half the emotion vocabulary.

**Architecture:** Bottom-up fix order following the data flow: mood mechanics (foundation) → appraisal/mapping (signal production) → drive computation (signal consumption) → regulation (top of stack). One cross-repo change to eidos for pole sign semantics.

**Tech Stack:** Java 21 (on Java 26 JVM), Quarkus 3.32.2, eidos API

## Global Constraints

- Build all neocortex: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Build without tests: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
- Test specific module: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl <module>`
- Build eidos API: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl api -DskipTests` (from `/Users/mdproctor/claude/casehub/slots/230/eidos`)
- Use `mvn` not `./mvnw`
- Use IntelliJ MCP tools for code operations
- Pre-release stage — no backward compatibility needed
- Each task = one atomic commit referencing #1226

---

## Batch 1: Mood Mechanics

### Task 1: Thread safety on pendingSignals — C20

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mood/MoodOrchestrator.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/mood/MoodOrchestratorTest.java`

**Interfaces:**
- Produces: Thread-safe `record()` via `ConcurrentLinkedDeque`

- [ ] **Step 1: Write failing test — concurrent record and tick don't corrupt state**

Add to `MoodOrchestratorTest`:

```java
@Test
void concurrentRecordAndTickDoNotCorruptState() throws Exception {
    var orchestrator = createOrchestrator();
    var agentId = "agent-1";
    var tenantId = "t1";
    int iterations = 1000;
    var latch = new java.util.concurrent.CountDownLatch(1);
    var errors = new java.util.concurrent.atomic.AtomicInteger(0);

    var recorder = Thread.startVirtualThread(() -> {
        try { latch.await(); } catch (InterruptedException e) { return; }
        for (int i = 0; i < iterations; i++) {
            try {
                orchestrator.record(new MoodSignal.DirectShift(0.01, 0.0, 0.0, "test"), agentId, tenantId);
            } catch (Exception e) { errors.incrementAndGet(); }
        }
    });

    var ticker = Thread.startVirtualThread(() -> {
        try { latch.await(); } catch (InterruptedException e) { return; }
        for (int i = 0; i < iterations; i++) {
            try {
                orchestrator.doTick(agentId, tenantId, java.time.Instant.now());
            } catch (Exception e) { errors.incrementAndGet(); }
        }
    });

    latch.countDown();
    recorder.join(5000);
    ticker.join(5000);

    assertThat(errors.get()).as("no exceptions from concurrent access").isZero();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=MoodOrchestratorTest#concurrentRecordAndTickDoNotCorruptState`
Expected: FAIL — race condition on ArrayDeque.

- [ ] **Step 3: Replace ArrayDeque with ConcurrentLinkedDeque**

In `MoodOrchestrator.java`, change the `pendingSignals` field type from `ArrayDeque<MoodSignal>` to `ConcurrentLinkedDeque<MoodSignal>`. Update the import. Change the drain loop from `while (!isEmpty()) { removeFirst() }` to:

```java
MoodSignal signal;
while ((signal = state.pendingSignals.pollFirst()) != null) {
    drained.add(signal);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=MoodOrchestratorTest#concurrentRecordAndTickDoNotCorruptState`
Expected: PASS

- [ ] **Step 5: Run all MoodOrchestrator tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=MoodOrchestratorTest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/mood/MoodOrchestrator.java cognition/src/test/
git commit -m "fix(cognition): replace ArrayDeque with ConcurrentLinkedDeque in MoodOrchestrator (C20) Refs #1226"
```

---

### Task 2: Decay before signal — C3

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mood/MoodOrchestrator.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/mood/MoodOrchestratorTest.java`

**Interfaces:**
- Consumes: `MoodDecay.decay()` for pre-signal decay
- Produces: Signals applied to already-decayed mood state

- [ ] **Step 1: Write failing test — fresh signal after idle gap retains full strength**

```java
@Test
void freshSignalAfterIdleGapRetainsFullStrength() {
    var orchestrator = createOrchestrator();
    var agentId = "agent-1";
    var tenantId = "t1";
    var now = Instant.parse("2026-01-01T12:00:00Z");

    // First tick to establish state
    orchestrator.doTick(agentId, tenantId, now);

    // Record a signal then tick after a 2-hour idle gap
    orchestrator.record(new MoodSignal.DirectShift(0.5, 0.0, 0.0, "test"), agentId, tenantId);
    var afterGap = now.plus(Duration.ofHours(2));
    orchestrator.doTick(agentId, tenantId, afterGap);

    var mood = orchestrator.currentMood(agentId, tenantId);
    assertThat(mood.pleasure())
        .as("signal after idle gap should retain most of its strength")
        .isGreaterThan(0.4);
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=MoodOrchestratorTest#freshSignalAfterIdleGapRetainsFullStrength`
Expected: FAIL — signal decayed by 2 hours of elapsed time.

- [ ] **Step 3: Swap decay and signal accumulation order in doTick()**

Move the decay block (lines ~102-112) before the signal accumulation block (lines ~83-96). Decay the pre-signal mood first, then apply new signals to the decayed state.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS — signal applied after decay.

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/mood/MoodOrchestrator.java cognition/src/test/
git commit -m "fix(cognition): decay mood before applying signals in doTick (C3) Refs #1226"
```

---

### Task 3: Goal emotions as set-point bias — C4

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mood/MoodOrchestrator.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mood/GoalEmotionMoodBridge.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodDecay.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/mood/MoodOrchestratorTest.java`

**Interfaces:**
- Produces: `MoodOrchestrator.setGoalBias(String agentId, String tenantId, MoodState bias)`
- Produces: `MoodDecay.decay()` accepts effective baseline (baseline + goalBias)

- [ ] **Step 1: Write failing test — mood decays toward goal bias, not zero**

```java
@Test
void moodDecaysTowardGoalBiasNotZero() {
    var orchestrator = createOrchestrator();
    var agentId = "agent-1";
    var tenantId = "t1";
    var now = Instant.parse("2026-01-01T12:00:00Z");

    // Set a positive goal bias
    orchestrator.setGoalBias(agentId, tenantId, new MoodState(0.3, 0.0, 0.0));

    // Push mood positive
    orchestrator.record(new MoodSignal.DirectShift(0.8, 0.0, 0.0, "test"), agentId, tenantId);
    orchestrator.doTick(agentId, tenantId, now);

    // Let it decay for a long time
    var later = now.plus(Duration.ofHours(2));
    orchestrator.doTick(agentId, tenantId, later);

    var mood = orchestrator.currentMood(agentId, tenantId);
    assertThat(mood.pleasure())
        .as("mood should decay toward goal bias (0.3), not zero")
        .isCloseTo(0.3, within(0.05));
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — mood decays to 0.0 (baseline), not 0.3 (bias).

- [ ] **Step 3: Add setGoalBias to MoodOrchestrator**

Add `setGoalBias(String agentId, String tenantId, MoodState bias)` method. Store bias per agent in the state map.

- [ ] **Step 4: Modify MoodDecay.decay() to accept effective baseline**

Add an overload that takes `effectiveBaseline` (baseline + goalBias) instead of bare baseline.

- [ ] **Step 5: Update GoalEmotionMoodBridge to use setGoalBias instead of record(DirectShift)**

Replace the per-tick `record(DirectShift)` call with `setGoalBias()`. Compute the goal PAD bias from active goal emotions and call `setGoalBias()` only when the goal set changes.

- [ ] **Step 6: Run test to verify it passes**

- [ ] **Step 7: Run all mood tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=MoodOrchestratorTest`

- [ ] **Step 8: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/mood/ memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodDecay.java cognition/src/test/
git commit -m "fix(cognition): goal emotions as set-point bias, not per-tick delta (C4) Refs #1226"
```

---

### Task 4: Rate-limit mood deltas — C2

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/mood/MoodOrchestrator.java`
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/mood/MoodConfig.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/mood/MoodOrchestratorTest.java`

**Interfaces:**
- Consumes: `goalBias` from Task 3 for effective baseline
- Produces: Direction-aware asymptotic dampening on mood deltas
- Produces: MoodConfig default decay constant changed from 4h to 20min

- [ ] **Step 1: Write failing test — two strong signals don't pin mood at 1.0**

```java
@Test
void twoStrongSignalsDontPinMoodAtOne() {
    var orchestrator = createOrchestrator();
    var agentId = "agent-1";
    var tenantId = "t1";
    var now = Instant.parse("2026-01-01T12:00:00Z");

    orchestrator.record(new MoodSignal.DirectShift(0.8, 0.0, 0.0, "signal-1"), agentId, tenantId);
    orchestrator.record(new MoodSignal.DirectShift(0.8, 0.0, 0.0, "signal-2"), agentId, tenantId);
    orchestrator.doTick(agentId, tenantId, now);

    var mood = orchestrator.currentMood(agentId, tenantId);
    assertThat(mood.pleasure())
        .as("two +0.8 signals should not pin mood at 1.0")
        .isLessThan(1.0)
        .isGreaterThan(0.5);
}
```

- [ ] **Step 2: Write failing test — recovery signals are undampened**

```java
@Test
void recoverySignalsAreUndampened() {
    var orchestrator = createOrchestrator();
    var agentId = "agent-1";
    var tenantId = "t1";
    var now = Instant.parse("2026-01-01T12:00:00Z");

    // Push mood negative
    orchestrator.record(new MoodSignal.DirectShift(-0.8, 0.0, 0.0, "negative"), agentId, tenantId);
    orchestrator.doTick(agentId, tenantId, now);

    // Apply positive recovery signal
    orchestrator.record(new MoodSignal.DirectShift(0.5, 0.0, 0.0, "recovery"), agentId, tenantId);
    orchestrator.doTick(agentId, tenantId, now.plusSeconds(1));

    var mood = orchestrator.currentMood(agentId, tenantId);
    assertThat(mood.pleasure())
        .as("recovery signal toward baseline should apply at full strength")
        .isGreaterThan(-0.35);
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=MoodOrchestratorTest#twoStrongSignalsDontPinMoodAtOne+recoverySignalsAreUndampened`
Expected: FAIL — raw sum pins at 1.0; recovery is also dampened.

- [ ] **Step 4: Implement direction-aware asymptotic approach in doTick()**

Replace the raw accumulation loop with the direction-aware dampening from the spec:

```java
double effectiveBaseline = config.baseline().pleasure() + goalBiasPleasure;
double displacement = p - effectiveBaseline;
double remaining = config.maxDisplacement() - Math.abs(displacement);
double headroom = Math.max(0.0, remaining / config.maxDisplacement());

double delta = signal.pleasureDelta();
boolean pushingAway = (delta > 0 && displacement >= 0) || (delta < 0 && displacement <= 0);
p += pushingAway ? delta * headroom : delta;
```

Apply same pattern to arousal and dominance.

- [ ] **Step 5: Shorten default decay constant from 4h to 20min**

In `MoodConfig.java`, change the default decay constant from `Duration.ofHours(4)` to `Duration.ofMinutes(20)`.

- [ ] **Step 6: Run tests to verify they pass**

- [ ] **Step 7: Run all mood and regulation tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="MoodOrchestrator*,EmotionRegulation*"`

- [ ] **Step 8: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/mood/MoodOrchestrator.java cognition-api/src/main/java/io/casehub/neocortex/cognition/mood/MoodConfig.java cognition/src/test/
git commit -m "fix(cognition): direction-aware asymptotic mood dampening, 20min decay (C2) Refs #1226"
```

---

## Batch 2: Appraisal & Mapping

### Task 5: Concern salience normalisation — C16

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/salience/ConcernBasedSalienceStrategy.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/salience/ConcernBasedSalienceStrategyTest.java`

**Interfaces:**
- Produces: `keywordOverlap()` normalises by `Math.min(a.size(), b.size())`

- [ ] **Step 1: Write failing test — short concern fully matching long observation scores 1.0**

```java
@Test
void shortConcernFullyMatchingLongObservationScoresOne() {
    Set<String> concern = Set.of("improve", "user", "retention");
    Set<String> observation = Set.of("we", "need", "to", "improve", "user", "retention",
        "by", "analyzing", "behavioral", "patterns", "across", "different",
        "cohorts", "in", "the", "product", "analytics", "dashboard",
        "to", "find", "actionable", "insights", "for", "growth",
        "marketing", "team", "efforts", "next", "quarter", "planning");

    double score = ConcernBasedSalienceStrategy.keywordOverlap(concern, observation);
    assertThat(score).as("all concern words matching should score 1.0").isEqualTo(1.0);
}
```

(Note: `keywordOverlap` may be private — make it package-private for testing, or test via the public `computeSalience` method.)

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — returns 3/30 = 0.1.

- [ ] **Step 3: Change Math.max to Math.min**

In `keywordOverlap()`, change `Math.max(a.size(), b.size())` to `Math.min(a.size(), b.size())`.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/salience/ cognition/src/test/
git commit -m "fix(cognition): normalise concern salience by min set size (C16) Refs #1226"
```

---

### Task 6: Gut-feeling Layer 2 agent filter — C21

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/MemoryScanRequest.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/gut/GutFeelingParticipant.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/gut/GutFeelingParticipantTest.java`

**Interfaces:**
- Produces: `MemoryScanRequest` with `@Nullable PrincipalId callerPrincipalId` field
- Produces: Layer 2 affect scan scoped to requesting agent

- [ ] **Step 1: Write failing test — Layer 2 only returns agent-scoped affect memories**

```java
@Test
void layer2OnlyReturnsAgentScopedAffectMemories() {
    // Store affect memories for agent-1 and agent-2
    // Query gut feeling for agent-1
    // Assert results only contain agent-1's memories
    // (Exact setup depends on existing test infrastructure)
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Add callerPrincipalId to MemoryScanRequest**

Add a 7th field `@Nullable PrincipalId callerPrincipalId` to the record. Add a backward-compatible 6-arg constructor overload that defaults it to null.

- [ ] **Step 4: Update GutFeelingParticipant to pass agentId**

Change the scan call to include `PrincipalId.agent(agentId)`.

- [ ] **Step 5: Run test to verify it passes**

- [ ] **Step 6: Commit**

```bash
git add memory-api/ cognition/src/main/java/io/casehub/neocortex/cognition/gut/ cognition/src/test/
git commit -m "fix(cognition): scope gut-feeling Layer 2 affect scan to requesting agent (C21) Refs #1226"
```

---

### Task 7: Appraisal weights and habituation — C11

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategy.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategyTest.java`

**Interfaces:**
- Consumes: `context.appraisalWeights()` from AppraisalContext
- Produces: Appraisal weight bias instructions in LLM prompt
- Produces: Normalized token hash for habituation

- [ ] **Step 1: Write failing test — appraisal weights appear in prompt**

```java
@Test
void appraisalWeightsAppearInPrompt() {
    var weights = Map.of("relevance", 1.5, "novelty", 0.7, "controllability", 1.0);
    var context = createContextWithWeights(weights);
    String prompt = strategy.buildUserMessage(context);
    assertThat(prompt).contains("relevance");
    assertThat(prompt).doesNotContain("controllability");
}
```

- [ ] **Step 2: Write failing test — minor rephrasing triggers habituation**

```java
@Test
void minorRephrasingTriggersHabituation() {
    // "the dog barked loudly" and "a dog was barking" should produce same hash
    // (Exact test depends on the habituation API)
}
```

- [ ] **Step 3: Implement appraisal weight injection in buildUserMessage()**

For each SEC dimension where `Math.abs(weight - 1.0) > 0.15`, append a bias instruction.

- [ ] **Step 4: Replace hashCode with normalized token hash**

Lowercase, split on whitespace, sort tokens, remove stopwords (a, an, the, is, was, were, be, been, being), join with space, SHA-256.

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/ cognition/src/test/
git commit -m "fix(cognition): inject appraisal weights into LLM prompt, normalise habituation hash (C11) Refs #1226"
```

---

### Task 8: EmotionMapper missing 6 emotions + INTERRUPTION cap — C14

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/EmotionMapper.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/appraisal/EmotionMapperTest.java`

**Interfaces:**
- Produces: PRIDE, RELIEF, GRATITUDE, ADMIRATION, SATISFACTION, DISAPPOINTMENT mapping rules
- Produces: INTERRUPTION capped at 0.3

- [ ] **Step 1: Write failing tests — each missing emotion type maps correctly**

```java
@Test
void mapsGratitudeFromHighConducivenessLowControllability() {
    var sec = new SecResult(0.8, 0.3, 0.0, 0.8, 0.2, 0.0, 0.5, 0.5);
    var emotions = EmotionMapper.mapEmotions(sec);
    assertThat(emotions.stream().map(e -> e.type()).toList())
        .contains(EmotionType.GRATITUDE);
}

@Test
void interruptionCappedAtZeroPointThree() {
    var sec = new SecResult(0.8, 0.1, 0.0, 0.0, 0.5, 0.0, 0.5, 0.5);
    var emotions = EmotionMapper.mapEmotions(sec);
    var interruption = emotions.stream()
        .filter(e -> e.type() == EmotionType.INTERRUPTION).findFirst();
    assertThat(interruption).isPresent();
    assertThat(interruption.get().intensity()).isLessThanOrEqualTo(0.3);
}
```

Add similar tests for PRIDE, RELIEF, ADMIRATION, SATISFACTION, DISAPPOINTMENT.

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Add 6 mapping rules**

Add to `mapEmotions()`:
- PRIDE: `internalStandards > 0.6 && conduciveness > 0.6`
- RELIEF: `conduciveness > 0.6 && urgency > 0.3` (using urgency delta if available)
- GRATITUDE: `conduciveness > 0.6 && controllability < 0.4`
- ADMIRATION: `externalStandards > 0.7 && relevance > 0.3`
- SATISFACTION: `conduciveness > 0.6 && novelty < 0.3`
- DISAPPOINTMENT: `conduciveness < 0.3 && relevance > 0.5`

- [ ] **Step 4: Cap INTERRUPTION intensity**

Change INTERRUPTION intensity from `clampIntensity(1.0 - novelty)` to `clampIntensity((1.0 - novelty) * 0.3)`.

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Run all EmotionMapper tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionMapperTest`

- [ ] **Step 7: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/EmotionMapper.java cognition/src/test/
git commit -m "fix(cognition): add 6 missing OCC emotion mappings, cap INTERRUPTION at 0.3 (C14) Refs #1226"
```

---

## Batch 3: Drive Computation

### Task 9: Pole sign semantics — C7 (CROSS-REPO)

**Files:**
- Modify: `eidos/api/src/main/java/io/casehub/eidos/api/DispositionAxis.java` (eidos repo)
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveComposer.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/drive/DriveComposerTest.java`

**Interfaces:**
- Produces: `DispositionAxis.signedPosition(String term)` → +1.0 (high), -1.0 (low), 0.0 (mid)
- Produces: DriveComposer uses signed position for personality modulation

- [ ] **Step 1: Write failing test — cautious and bold produce opposite modulation**

Add to `DriveComposerTest`:

```java
@Test
void cautiousAndBoldProduceOppositeModulation() {
    var boldDisp = createDisposition("bold");
    var cautiousDisp = createDisposition("conservative");
    
    double boldMod = composer.personalityModulation(boldDisp, DriveAxis.CURIOSITY);
    double cautiousMod = composer.personalityModulation(cautiousDisp, DriveAxis.CURIOSITY);
    
    assertThat(boldMod).as("bold should produce positive modulation").isGreaterThan(0.0);
    assertThat(cautiousMod).as("cautious should produce negative modulation").isLessThan(0.0);
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — both return positive modulation.

- [ ] **Step 3: Add signedPosition() to DispositionAxis in eidos**

```java
public double signedPosition(String term) {
    if (term.equalsIgnoreCase(highPoleLabel())) return +1.0;
    if (term.equalsIgnoreCase(lowPoleLabel())) return -1.0;
    return 0.0;
}
```

Build and install eidos: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -pl api -DskipTests` from `/Users/mdproctor/claude/casehub/slots/230/eidos`

- [ ] **Step 4: Update DriveComposer to use signedPosition**

Change line 123:
```java
double sign = matchedAxis.signedPosition(values.getFirst().term());
return sign * weight * config.personalityModulationStrength();
```

- [ ] **Step 5: Run test to verify it passes**

- [ ] **Step 6: Commit eidos change**

```bash
git -C /Users/mdproctor/claude/casehub/slots/230/eidos add api/
git -C /Users/mdproctor/claude/casehub/slots/230/eidos commit -m "feat(api): add signedPosition() to DispositionAxis for pole semantics Refs casehubio/neocortex#1226"
```

- [ ] **Step 7: Commit neocortex change**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveComposer.java cognition/src/test/
git commit -m "fix(cognition): use DispositionAxis.signedPosition for drive personality modulation (C7) Refs #1226"
```

---

### Task 10: Coping drive modulations merge — C6

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/drive/DriveOrchestratorTest.java`

**Interfaces:**
- Produces: `recordAppraisalModulation()` uses `merge()` instead of `put()`

- [ ] **Step 1: Write failing test — two modulations accumulate**

```java
@Test
void twoModulationsAccumulate() {
    orchestrator.recordAppraisalModulation("a1", "t1",
        Map.of(DriveAxis.CURIOSITY, 0.1), Map.of(DriveAxis.CURIOSITY, "mild gap"));
    orchestrator.recordAppraisalModulation("a1", "t1",
        Map.of(DriveAxis.CURIOSITY, 0.3), Map.of(DriveAxis.CURIOSITY, "strong response"));

    // Tick to consume
    orchestrator.doTick("a1", "t1");

    // Verify combined modulation = 0.4, description = "strong response" (larger contributor)
    assertThat(lastAppliedModulation.get(DriveAxis.CURIOSITY))
        .as("modulations should sum").isCloseTo(0.4, within(0.001));
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — second `put()` overwrites first; result is 0.3 not 0.4.

- [ ] **Step 3: Replace put() with merge()**

Use the merge pattern from the spec for both `pendingAppraisalModulations` and `pendingAppraisalDescriptions`.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java cognition/src/test/
git commit -m "fix(cognition): accumulate coping drive modulations with merge (C6) Refs #1226"
```

---

### Task 11: DriveSource state agent-keyed — C9

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/CuriosityDrive.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/CompetenceDrive.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/AffiliationDrive.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/AutonomyDrive.java`
- Test: existing drive tests in `cognition/src/test/`

**Interfaces:**
- Produces: Per-agent state maps instead of single volatile fields

- [ ] **Step 1: Write failing test — two agents have independent drive state**

```java
@Test
void twoAgentsHaveIndependentDriveState() {
    drive.evaluate("agent-1", "t1", context1);
    drive.evaluate("agent-2", "t1", context2);
    
    var gaps1 = drive.lastGaps("agent-1");
    var gaps2 = drive.lastGaps("agent-2");
    
    assertThat(gaps1).as("agent-1 gaps should not be overwritten by agent-2")
        .isNotEqualTo(gaps2);
}
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Replace volatile fields with ConcurrentHashMap in all 4 DriveSource implementations**

For each drive (CuriosityDrive, CompetenceDrive, AffiliationDrive, AutonomyDrive):
- Replace `private volatile List<X> lastY = List.of()` with `private final ConcurrentHashMap<String, List<X>> lastYByAgent = new ConcurrentHashMap<>()`
- Update `evaluate()` to store per agentId
- Update accessors to take agentId parameter

- [ ] **Step 4: Run tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/drive/ cognition/src/test/
git commit -m "fix(cognition): agent-keyed state in all four DriveSource implementations (C9) Refs #1226"
```

---

### Task 12: DriveAdaptationPhase cursor + zero recovery — C10

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveAdaptationPhase.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/drive/DriveAdaptationPhaseTest.java`

**Interfaces:**
- Produces: Timestamp-based cursor instead of UUID comparison
- Produces: Additive intensity update (can recover from 0.0)

- [ ] **Step 1: Write failing test — intensity recovers from zero**

```java
@Test
void intensityRecoversFromZero() {
    // Set drive intensity to 0.0
    // Apply positive delta
    // Assert intensity > 0.0
    var result = adaptPhase.applyDelta(0.0, 0.5);
    assertThat(result).as("intensity at 0.0 should recover with positive delta").isGreaterThan(0.0);
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `0.0 * (1 + 0.5) = 0.0`.

- [ ] **Step 3: Fix multiplicative to additive update**

Change `currentIntensity * (1 + delta)` to `Math.min(1.0, Math.max(0.0, currentIntensity + delta * config.recoveryRate()))`.

- [ ] **Step 4: Fix UUID cursor to timestamp-based**

Replace `n.id().compareTo(lastProcessedId) > 0` with a timestamp comparison using a property on a sentinel node.

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveAdaptationPhase.java cognition/src/test/
git commit -m "fix(cognition): timestamp cursor and additive intensity recovery in DriveAdaptationPhase (C10) Refs #1226"
```

---

## Batch 4: Regulation

### Task 13: CognitiveResourcePool wiring — C5

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipantTest.java`

**Interfaces:**
- Consumes: `CognitiveResourcePool` from CDI (`DefaultCognitiveResourcePool`)
- Produces: Fatigue gate activated; alpha decreases with depletion

- [ ] **Step 1: Write failing test — depletion accumulates and reduces alpha**

```java
@Test
void depletionAccumulatesAndReducesAlpha() {
    // Provide a real CognitiveResourcePool
    // Trigger regulation multiple times
    // Assert depletion > 0 and alpha < DEFAULT_ALPHA
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `cognitiveResourcePool = null`, depletion always 0.

- [ ] **Step 3: Replace hardcoded null with CDI Instance injection**

Change `this.cognitiveResourcePool = null;` to accept `Instance<CognitiveResourcePool>` and resolve it.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/regulation/ cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java cognition/src/test/
git commit -m "fix(cognition): wire CognitiveResourcePool into EmotionRegulationTickParticipant (C5) Refs #1226"
```

---

### Task 14: CognitiveLoadEstimator LOW reachable — C17

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/CognitiveLoadEstimator.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/CognitiveLoadEstimatorTest.java`

**Interfaces:**
- Produces: `estimate()` counts drives with intensity > 0.3, not all axes

- [ ] **Step 1: Write failing test — LOW is reachable with low-intensity drives**

```java
@Test
void lowLoadReachableWithLowIntensityDrives() {
    var profile = createDriveProfile(0.1, 0.1, 0.2, 0.1);
    var load = estimator.estimate(profile, 0, 0);
    assertThat(load).isEqualTo(CognitiveLoad.LOW);
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `drives().size()` = 4 ≥ MODERATE_THRESHOLD.

- [ ] **Step 3: Count drives above intensity threshold**

Change `p.drives().size()` to `(int) p.drives().stream().filter(d -> d.intensity() > 0.3).count()`.

- [ ] **Step 4: Run test to verify it passes**

- [ ] **Step 5: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/regulation/CognitiveLoadEstimator.java cognition/src/test/
git commit -m "fix(cognition): count active drives for load estimation, not axis count (C17) Refs #1226"
```

---

### Task 15: Valence-aware regulation filter — C13

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipantTest.java`

**Interfaces:**
- Consumes: Appraisal emotions with PAD
- Produces: Safety gate fires on any emotion > 0.75 regardless of valence
- Produces: Normal regulation only triggers on negative-valence emotions

- [ ] **Step 1: Write failing test — high JOY does not trigger normal regulation**

```java
@Test
void highJoyDoesNotTriggerNormalRegulation() {
    // Set up appraisal with JOY at intensity 0.6 (above baseline but below safety)
    // Assert regulation does NOT fire
}
```

- [ ] **Step 2: Write failing test — extreme JOY triggers safety gate**

```java
@Test
void extremeJoyTriggersSafetyGate() {
    // Set up appraisal with JOY at intensity 0.9 (above safety threshold)
    // Assert ATTENTIONAL_DEPLOYMENT strategy is selected
}
```

- [ ] **Step 3: Run tests to verify they fail**

- [ ] **Step 4: Restructure tick() with two-tier approach**

Move safety gate before the effort computation early return. Filter `maxDiscrepancy` to negative-valence emotions only. See spec for the full flow restructure.

- [ ] **Step 5: Run tests to verify they pass**

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/regulation/ cognition/src/test/
git commit -m "fix(cognition): two-tier regulation — safety gate + valence filter (C13) Refs #1226"
```

---

### Task 16: Regulated intensity reaches mood — C12

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/mood/MoodSignal.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java`
- Test: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipantTest.java`

**Interfaces:**
- Produces: `MoodSignal.RegulatedShift` record type
- Produces: Regulation results recorded as mood corrections via MoodOrchestrator
- Consumes: `MoodOrchestrator.record()` from Task 1

- [ ] **Step 1: Write failing test — regulation result produces RegulatedShift mood signal**

```java
@Test
void regulationResultProducesRegulatedShiftMoodSignal() {
    // Trigger regulation with a strong negative emotion
    // Assert MoodOrchestrator received a RegulatedShift signal
    // Assert the delta is negative (regulation reduces intensity)
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — no MoodOrchestrator dependency, no RegulatedShift type.

- [ ] **Step 3: Add RegulatedShift to MoodSignal sealed interface**

```java
record RegulatedShift(
    double pleasureDelta,
    double arousalDelta,
    double dominanceDelta,
    String regulationStrategy,
    @Nullable EmotionType targetEmotion
) implements MoodSignal {
    public RegulatedShift {
        Objects.requireNonNull(regulationStrategy, "regulationStrategy required");
        validateDelta("pleasureDelta", pleasureDelta);
        validateDelta("arousalDelta", arousalDelta);
        validateDelta("dominanceDelta", dominanceDelta);
    }
}
```

- [ ] **Step 4: Wire MoodOrchestrator into EmotionRegulationTickParticipant**

Add `@Nullable MoodOrchestrator moodOrchestrator` as a constructor parameter. Wire via CognitionDefaultBeans.

- [ ] **Step 5: Record RegulatedShift in handleRegulationResult()**

After the existing result-storage block:
```java
if (moodOrchestrator != null && dominantType != null) {
    double intensityDelta = result.regulatedIntensity() - result.peakOriginalIntensity();
    var pad = AlmaPadTable.project(dominantType, intensityDelta);
    moodOrchestrator.record(new MoodSignal.RegulatedShift(
        pad.pleasure(), pad.arousal(), pad.dominance(),
        result.strategy().name(), dominantType), context.agentId(), context.tenantId());
}
```

- [ ] **Step 6: Run test to verify it passes**

- [ ] **Step 7: Run all regulation and mood tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="EmotionRegulation*,MoodOrchestrator*"`

- [ ] **Step 8: Commit**

```bash
git add cognition-api/ cognition/src/main/java/io/casehub/neocortex/cognition/regulation/ cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java cognition/src/test/
git commit -m "fix(cognition): bridge regulated intensity to mood via RegulatedShift signal (C12) Closes #1226"
```

---

## References

- [2026-11-26-affect-emotion-design.md] — design spec this plan implements
- `cognition/src/main/java/io/casehub/neocortex/cognition/mood/MoodOrchestrator.java` — C2, C3, C20
- `cognition/src/main/java/io/casehub/neocortex/cognition/mood/GoalEmotionMoodBridge.java` — C4
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/LlmAppraisalStrategy.java` — C11
- `cognition/src/main/java/io/casehub/neocortex/cognition/appraisal/EmotionMapper.java` — C14
- `cognition/src/main/java/io/casehub/neocortex/cognition/salience/ConcernBasedSalienceStrategy.java` — C16
- `cognition/src/main/java/io/casehub/neocortex/cognition/gut/GutFeelingParticipant.java` — C21
- `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveOrchestrator.java` — C6
- `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveComposer.java` — C7
- `cognition/src/main/java/io/casehub/neocortex/cognition/drive/CuriosityDrive.java` — C9
- `cognition/src/main/java/io/casehub/neocortex/cognition/drive/DriveAdaptationPhase.java` — C10
- `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java` — C5, C12, C13
- `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/CognitiveLoadEstimator.java` — C17
- `eidos/api/src/main/java/io/casehub/eidos/api/DispositionAxis.java` — C7 cross-repo
- `memory-api/src/main/java/io/casehub/neocortex/memory/mood/MoodDecay.java` — C3
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/mood/MoodSignal.java` — C12
- decisions.md D1, D2, D3, D4
- GitHub #1226
