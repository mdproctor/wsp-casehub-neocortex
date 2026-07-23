# CBR Trust-Weighted Retrieval Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #154 — feat: CBR trust-weighted retention — precedent authority + trust trajectory signal
**Issue group:** #154

**Goal:** Add trust-weighted retrieval scoring to the CBR decorator chain — cases from trusted agents score higher, declining trust trajectories reduce precedent authority.

**Architecture:** Two new fields on CbrCase (trustScore, producerAgentId). New AgentTrustProvider SPI for trajectory computation. TrustWeightedCbrCaseMemoryStore @Decorator @Priority(60) with reactive parity. Graceful degradation without trust provider.

**Tech Stack:** Java 21, Quarkus 3.32, CDI decorators, Mutiny

## Global Constraints

- All CbrCase record changes are breaking (pre-release — acceptable)
- trustScore validated in [0,1] when non-null (same as confidence)
- No dependency on casehub-ledger-api — AgentTrustProvider is a neocortex-local SPI
- @IfBuildProperty keys must be declared in @ConfigMapping (SmallRye Config strict validation)
- Decorator @Priority(60) — between Tracking@50 and OutcomeWeighting@65

---

### Task 1: CbrCase model changes + contract tests (memory-api)

**Files:**
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/FeatureVectorCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TextualCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ScoredCbrCase.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRetrievalTrace.java` (TracedCase)
- Modify: `memory-testing/src/main/java/io/casehub/neocortex/memory/cbr/testing/CbrCaseMemoryStoreContractTest.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AgentTrustProvider.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/ReactiveAgentTrustProvider.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TrustWeightingFunction.java`

**Interfaces:**
- Produces: `CbrCase.trustScore()`, `CbrCase.producerAgentId()`, `ScoredCbrCase.trustTrajectory()`, `ScoredCbrCase.withTrustTrajectory(Double)`, `AgentTrustProvider`, `ReactiveAgentTrustProvider`, `TrustWeightingFunction`

This task is the foundation — every subsequent task depends on it. It changes the CbrCase sealed hierarchy which will break all callers (all three record types gain two new constructor params). Every test that constructs a CbrCase will need updating.

- [ ] **Step 1: Add trust fields to CbrCase interface**

Add default methods to `CbrCase`:
```java
default Double trustScore() { return null; }
default String producerAgentId() { return null; }
```

- [ ] **Step 2: Update FeatureVectorCbrCase**

Add `Double trustScore` and `String producerAgentId` as record components (after `features`). Add [0,1] validation for trustScore in compact constructor. Update `withOutcome()` and `withFeatures()` to preserve both fields.

- [ ] **Step 3: Update PlanCbrCase**

Same pattern — add after `planTrace`. Update `withOutcome()` and `withFeatures()`.

- [ ] **Step 4: Update TextualCbrCase**

Same pattern — add after `confidence`. Update `withOutcome()`.

- [ ] **Step 5: Fix all compilation errors across the project**

Every test and production class that constructs CbrCase records will break. Use `ide_diagnostics` with `includeBuildErrors=true` to find them. Add `, null, null` to each call site (trust is unknown for existing callers). This will touch files across memory-api, memory, memory-testing, memory-cbr-inmem, memory-cbr-crossencoder, memory-cbr-tracking, memory-qdrant, and examples.

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/neocortex/pom.xml install -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 6: Add trustTrajectory to ScoredCbrCase**

Add `Double trustTrajectory` field (nullable). Update all existing constructors to pass `null`. Add `withTrustTrajectory(Double delta)` method.

- [ ] **Step 7: Fix ScoredCbrCase compilation errors**

Same approach — `ide_diagnostics` to find broken call sites. Add `, null` for the new trustTrajectory parameter to all existing constructors.

- [ ] **Step 8: Add trust fields to TracedCase**

Add `Double trustScore`, `String producerAgentId`, `String trustTrajectory` to the `CbrRetrievalTrace.TracedCase` record. Fix all TracedCase construction sites.

- [ ] **Step 9: Create AgentTrustProvider SPI**

```java
package io.casehub.neocortex.memory.cbr;

import java.util.OptionalDouble;

@FunctionalInterface
public interface AgentTrustProvider {
    OptionalDouble currentTrustScore(String agentId);
}
```

- [ ] **Step 10: Create ReactiveAgentTrustProvider SPI**

```java
package io.casehub.neocortex.memory.cbr;

import io.smallrye.mutiny.Uni;
import java.util.OptionalDouble;

@FunctionalInterface
public interface ReactiveAgentTrustProvider {
    Uni<OptionalDouble> currentTrustScore(String agentId);
}
```

- [ ] **Step 11: Create TrustWeightingFunction SPI**

```java
package io.casehub.neocortex.memory.cbr;

import java.util.OptionalDouble;

@FunctionalInterface
public interface TrustWeightingFunction {
    double apply(double similarity, double trustScore, OptionalDouble trustTrajectory);
}
```

- [ ] **Step 12: Write contract tests for trust round-trip**

Add 9 tests to `CbrCaseMemoryStoreContractTest`:
- `trustScore_roundTrip` — store with trustScore=0.85, retrieve, verify
- `producerAgentId_roundTrip` — store with producerAgentId="agent-1", verify
- `trustScore_nullPreserved` — store with null, verify null
- `trustScore_withOutcome_preserved` — recordOutcome doesn't clobber trustScore
- `trustScore_withFeatures_preserved` — withFeatures preserves trustScore
- `trustScore_validation_rejectsOutOfRange` — trustScore=1.5 throws
- `producerAgentId_withOutcome_preserved` — recordOutcome preserves agentId
- `planCbrCase_trustFields_roundTrip` — PlanCbrCase with both fields
- `textualCbrCase_trustFields_roundTrip` — TextualCbrCase with both fields

- [ ] **Step 13: Run full test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/neocortex test`
Expected: All tests pass (including new contract tests on InMemory backend)

- [ ] **Step 14: Commit**

```
feat(#154): add trustScore, producerAgentId to CbrCase + trust SPIs

CbrCase gains trustScore() and producerAgentId() for trust-weighted
retrieval scoring. ScoredCbrCase gains trustTrajectory for observability.
AgentTrustProvider, ReactiveAgentTrustProvider, and TrustWeightingFunction
SPIs added to memory-api. 9 new contract tests.
```

---

### Task 2: DefaultTrustWeightingFunction + unit tests (memory module)

**Files:**
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/TrustWeightingConfig.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/DefaultTrustWeightingFunction.java`
- Create: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/DefaultTrustWeightingFunctionTest.java`

**Interfaces:**
- Consumes: `TrustWeightingFunction` (from Task 1)
- Produces: `DefaultTrustWeightingFunction` (@DefaultBean), `TrustWeightingConfig`

- [ ] **Step 1: Write failing tests**

7 tests for `DefaultTrustWeightingFunctionTest`:
- `authorityOnly_highTrust` — trustScore=0.9, no trajectory → score * 0.97
- `authorityOnly_lowTrust` — trustScore=0.1 → score * 0.73
- `authorityOnly_zeroTrust` — trustScore=0.0 → score * 0.7
- `trajectory_declining_appliesPenalty` — delta=-0.4 → additional * 0.8
- `trajectory_declining_floor` — delta=-2.0 → multiplier floors at 0.5
- `trajectory_improving_ignored` — positive delta → no effect
- `trajectory_absent_noEffect` — OptionalDouble.empty() → authority-only

- [ ] **Step 2: Create TrustWeightingConfig**

```java
@ConfigMapping(prefix = "casehub.cbr.trust-weighting")
public interface TrustWeightingConfig {
    @WithDefault("false")
    boolean enabled();

    @WithDefault("0.3")
    double influence();

    @WithDefault("0.5")
    double trajectorySensitivity();
}
```

- [ ] **Step 3: Implement DefaultTrustWeightingFunction**

`@DefaultBean @ApplicationScoped`. Constructor takes `TrustWeightingConfig`. Test constructor takes `(double influence, double trajectorySensitivity)`.

Authority: `score * (1 - α + α * trustScore)`
Trajectory (negative only): `* max(0.5, 1.0 + β * delta)`

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/neocortex/memory/pom.xml test -Dtest=DefaultTrustWeightingFunctionTest`
Expected: 7 tests pass

- [ ] **Step 5: Commit**

```
feat(#154): DefaultTrustWeightingFunction with authority + trajectory scoring
```

---

### Task 3: Trust weighting decorators + blocking-to-reactive bridge (memory module)

**Files:**
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/TrustWeightedCbrCaseMemoryStore.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/ReactiveTrustWeightedCbrCaseMemoryStore.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/BlockingAgentTrustProviderBridge.java`
- Create: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/TrustWeightedCbrCaseMemoryStoreTest.java`
- Create: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/ReactiveTrustWeightedCbrCaseMemoryStoreTest.java`

**Interfaces:**
- Consumes: `TrustWeightingFunction`, `AgentTrustProvider`, `ReactiveAgentTrustProvider`, `CbrCaseMemoryStore`, `ReactiveCbrCaseMemoryStore` (all from Tasks 1-2)
- Produces: `TrustWeightedCbrCaseMemoryStore` @Decorator @Priority(60), `ReactiveTrustWeightedCbrCaseMemoryStore` @Decorator @Priority(60), `BlockingAgentTrustProviderBridge` @DefaultBean

- [ ] **Step 1: Write blocking decorator unit tests**

7 tests for `TrustWeightedCbrCaseMemoryStoreTest`:
- `nullTrustScore_passesThrough`
- `mixedNullAndNonNull_onlyWeightsNonNull`
- `resortsAfterWeighting`
- `emptyResults_passesThrough`
- `trajectoryCache_singleCallPerAgent`
- `noAgentTrustProvider_authorityOnly`
- `trustTrajectory_storedOnScoredCbrCase`

- [ ] **Step 2: Implement blocking decorator**

`@Decorator @Priority(60) @IfBuildProperty(name = "casehub.cbr.trust-weighting.enabled", stringValue = "true")`. Inject `@Delegate @Any CbrCaseMemoryStore`, `TrustWeightingFunction`, `Instance<AgentTrustProvider>`. Local `trajectoryCache` per `retrieveSimilar()` call. All non-retrieveSimilar methods delegate unchanged.

- [ ] **Step 3: Run blocking tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/neocortex/memory/pom.xml test -Dtest=TrustWeightedCbrCaseMemoryStoreTest`
Expected: 7 tests pass

- [ ] **Step 4: Write reactive decorator unit tests**

3 tests for `ReactiveTrustWeightedCbrCaseMemoryStoreTest`:
- `batchedLookups_distinctAgentIds`
- `noReactiveProvider_authorityOnly`
- `mixedNullAndNonNull_reactiveWeighting`

- [ ] **Step 5: Create BlockingAgentTrustProviderBridge**

`@DefaultBean @ApplicationScoped implements ReactiveAgentTrustProvider`. Injects `Instance<AgentTrustProvider>`. If resolvable, wraps with `Uni.createFrom().item(...).runSubscriptionOn(Infrastructure.getDefaultWorkerPool())`. If not, returns `OptionalDouble.empty()`.

- [ ] **Step 6: Implement reactive decorator**

Same `@Decorator @Priority(60) @IfBuildProperty`. Injects `Instance<ReactiveAgentTrustProvider>`. Batched lookups via `Uni.join().all()`. Shared `applyWeighting()` logic.

- [ ] **Step 7: Run all memory module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/neocortex/memory/pom.xml test`
Expected: All tests pass

- [ ] **Step 8: Commit**

```
feat(#154): TrustWeighted decorators (blocking + reactive) + bridge
```

---

### Task 4: Qdrant backend trust payload + TracedCase observability (memory-qdrant, memory-cbr-tracking)

**Files:**
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/CbrPointBuilder.java`
- Modify: `memory-qdrant/src/main/java/io/casehub/neocortex/memory/cbr/qdrant/ReactiveQdrantCbrCaseMemoryStore.java`
- Modify: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/TrackingCbrCaseMemoryStore.java`
- Modify: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/ReactiveTrackingCbrCaseMemoryStore.java`

**Interfaces:**
- Consumes: `CbrCase.trustScore()`, `CbrCase.producerAgentId()`, `ScoredCbrCase.trustTrajectory()`, `TracedCase` (from Task 1)
- Produces: Trust-aware Qdrant payload serialization, trust-aware TracedCase construction

- [ ] **Step 1: Update CbrPointBuilder**

Add `trust_score` and `producer_agent_id` payload fields. Write at store time from `cbrCase.trustScore()` and `cbrCase.producerAgentId()`. Read at retrieval time into the reconstructed CbrCase.

- [ ] **Step 2: Update ReactiveQdrantCbrCaseMemoryStore**

Ensure the reconstructed CbrCase carries trustScore and producerAgentId from the Qdrant payload.

- [ ] **Step 3: Update TrackingCbrCaseMemoryStore TracedCase construction**

In `retrieveSimilar()`, construct `TracedCase` with the three new fields:
```java
new CbrRetrievalTrace.TracedCase(
    s.caseId(), s.score(), s.reranked(),
    s.featureSimilarities(), s.cbrCase().confidence(),
    s.cbrCase().trustScore(), s.cbrCase().producerAgentId(),
    trajectoryLabel(s.trustTrajectory()))
```

Add `trajectoryLabel(Double delta)` helper: null→null, <0→"declining", >0→"improving", ==0→"stable".

- [ ] **Step 4: Update ReactiveTrackingCbrCaseMemoryStore**

Same TracedCase construction changes.

- [ ] **Step 5: Run affected module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/neocortex test -pl memory-qdrant,memory-cbr-tracking`
Expected: All tests pass

- [ ] **Step 6: Commit**

```
feat(#154): Qdrant trust payload + TracedCase observability
```

---

### Task 5: CLAUDE.md update + full build verification

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: All prior tasks

- [ ] **Step 1: Update CLAUDE.md**

Update `memory-api/` description to include `AgentTrustProvider`, `ReactiveAgentTrustProvider`, `TrustWeightingFunction`, and the new CbrCase fields.

Update `memory/` description to include `TrustWeightedCbrCaseMemoryStore` @Decorator @Priority(60), `ReactiveTrustWeightedCbrCaseMemoryStore`, `DefaultTrustWeightingFunction`, `BlockingAgentTrustProviderBridge`.

Update decorator chain description if present.

- [ ] **Step 2: Full build with tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn -f /Users/mdproctor/claude/casehub/neocortex install`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 3: Commit**

```
docs(#154): update CLAUDE.md with trust-weighted retrieval scoring types
```
