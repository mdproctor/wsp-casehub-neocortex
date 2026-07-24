# CBR Plan Adaptation SPI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #85 — feat: CBR Phase 5 — plan adaptation SPI
**Issue group:** #85

**Goal:** Add the Reuse phase to the CBR cycle — a `PlanAdapter` SPI that transforms retrieved `PlanCbrCase` plans into adapted plans for the current case context.

**Architecture:** Six new types in `memory-api` (`PlanAdapter`, `AdaptedPlan`, `AdaptedStep`, `AdaptationAction`, `AdaptationTrace`, `CbrAdaptationRecorded`), one `@DefaultBean` in `memory/` (`NoOpPlanAdapter`), one `@Decorator` in `memory-cbr-tracking/` (`TrackingPlanAdapter`), contract tests in `memory-testing/`, value type tests in `memory-api/`.

**Tech Stack:** Java 21, Quarkus CDI (quarkus-arc), JUnit 5, AssertJ

## Global Constraints

- Java 21 language level, Java 26 JVM
- All records: `Objects.requireNonNull` in compact constructor, `List.copyOf`/`Map.copyOf` for collections
- `@DefaultBean @ApplicationScoped` for no-op defaults
- `@Decorator @Priority(N) @IfBuildProperty` for opt-in decorators
- Package: `io.casehub.neocortex.memory.cbr` (API), `.runtime` (defaults), `.tracking` (decorators)
- Build with: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Test single module: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl <module>`

---

### Task 1: Value types in memory-api

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptationAction.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptedStep.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptedPlan.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptationTrace.java`
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrAdaptationRecorded.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptedStepTest.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptedPlanTest.java`
- Test: `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptationTraceTest.java`

**Interfaces:**
- Consumes: `PlanTrace` (existing), `ScoredCbrCase` (existing), `FeatureValue` (existing)
- Produces: `AdaptationAction`, `AdaptedStep`, `AdaptedPlan`, `AdaptationTrace`, `CbrAdaptationRecorded` — used by Tasks 2–4

- [ ] **Step 1: Write AdaptedStep tests**

Create `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptedStepTest.java`:

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class AdaptedStepTest {

    @Test void validStep() {
        var step = new AdaptedStep("b1", "cap1", "w1", "SUCCESS", 0,
                Map.of("k", "v"), AdaptationAction.RETAINED, null);
        assertThat(step.bindingName()).isEqualTo("b1");
        assertThat(step.capabilityName()).isEqualTo("cap1");
        assertThat(step.workerName()).isEqualTo("w1");
        assertThat(step.stepOutcome()).isEqualTo("SUCCESS");
        assertThat(step.priority()).isZero();
        assertThat(step.parameters()).containsEntry("k", "v");
        assertThat(step.action()).isEqualTo(AdaptationAction.RETAINED);
        assertThat(step.reason()).isNull();
    }

    @Test void nullBindingNameRejected() {
        assertThatNullPointerException().isThrownBy(() ->
                new AdaptedStep(null, "cap", "w", "SUCCESS", 0,
                        Map.of(), AdaptationAction.RETAINED, null));
    }

    @Test void nullCapabilityNameRejected() {
        assertThatNullPointerException().isThrownBy(() ->
                new AdaptedStep("b", null, "w", "SUCCESS", 0,
                        Map.of(), AdaptationAction.RETAINED, null));
    }

    @Test void negativePriorityRejected() {
        assertThatIllegalArgumentException().isThrownBy(() ->
                new AdaptedStep("b", "cap", "w", "SUCCESS", -1,
                        Map.of(), AdaptationAction.RETAINED, null));
    }

    @Test void nullActionRejected() {
        assertThatNullPointerException().isThrownBy(() ->
                new AdaptedStep("b", "cap", "w", "SUCCESS", 0,
                        Map.of(), null, null));
    }

    @Test void nullWorkerNameAllowed_removedStep() {
        var step = new AdaptedStep("b", "cap", null, "FAILURE", 0,
                Map.of(), AdaptationAction.REMOVED, "worker unavailable");
        assertThat(step.workerName()).isNull();
    }

    @Test void nullWorkerNameAllowed_addedStep() {
        var step = new AdaptedStep("b", "cap", null, null, 0,
                Map.of(), AdaptationAction.ADDED, "severity requires IRB");
        assertThat(step.workerName()).isNull();
        assertThat(step.stepOutcome()).isNull();
    }

    @Test void nullStepOutcomeAllowed_addedStep() {
        var step = new AdaptedStep("b", "cap", "w", null, 5,
                Map.of(), AdaptationAction.ADDED, "new step");
        assertThat(step.stepOutcome()).isNull();
    }

    @Test void nullParametersDefaultsToEmptyMap() {
        var step = new AdaptedStep("b", "cap", "w", "SUCCESS", 0,
                null, AdaptationAction.RETAINED, null);
        assertThat(step.parameters()).isEmpty();
    }

    @Test void parametersDefensivelyCopied() {
        var params = new java.util.HashMap<String, Object>();
        params.put("k", "v");
        var step = new AdaptedStep("b", "cap", "w", "SUCCESS", 0,
                params, AdaptationAction.RETAINED, null);
        params.put("k2", "v2");
        assertThat(step.parameters()).doesNotContainKey("k2");
    }

    @Test void allActionsAccessible() {
        assertThat(AdaptationAction.values()).containsExactly(
                AdaptationAction.RETAINED, AdaptationAction.SUBSTITUTED,
                AdaptationAction.BOOSTED, AdaptationAction.SUPPRESSED,
                AdaptationAction.ADDED, AdaptationAction.REMOVED);
    }
}
```

- [ ] **Step 2: Write AdaptedPlan tests**

Create `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptedPlanTest.java`:

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class AdaptedPlanTest {

    @Test void validPlan() {
        var step = new AdaptedStep("b", "cap", "w", "SUCCESS", 0,
                Map.of(), AdaptationAction.RETAINED, null);
        var plan = new AdaptedPlan(List.of(step));
        assertThat(plan.steps()).hasSize(1);
        assertThat(plan.steps().getFirst().bindingName()).isEqualTo("b");
    }

    @Test void nullStepsRejected() {
        assertThatNullPointerException().isThrownBy(() -> new AdaptedPlan(null));
    }

    @Test void stepsDefensivelyCopied() {
        var step = new AdaptedStep("b", "cap", "w", "SUCCESS", 0,
                Map.of(), AdaptationAction.RETAINED, null);
        var list = new ArrayList<>(List.of(step));
        var plan = new AdaptedPlan(list);
        list.add(new AdaptedStep("b2", "cap2", "w2", "SUCCESS", 1,
                Map.of(), AdaptationAction.ADDED, "test"));
        assertThat(plan.steps()).hasSize(1);
    }

    @Test void emptyStepsAllowed() {
        var plan = new AdaptedPlan(List.of());
        assertThat(plan.steps()).isEmpty();
    }
}
```

- [ ] **Step 3: Write AdaptationTrace tests**

Create `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptationTraceTest.java`:

```java
package io.casehub.neocortex.memory.cbr;

import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class AdaptationTraceTest {

    private final AdaptedStep step = new AdaptedStep("b", "cap", "w", "SUCCESS", 0,
            Map.of(), AdaptationAction.RETAINED, null);

    @Test void validTrace() {
        var trace = new AdaptationTrace("t1", "rt1", "c1", 0.85,
                List.of(step), Map.of("f", FeatureValue.string("v")), Instant.now());
        assertThat(trace.traceId()).isEqualTo("t1");
        assertThat(trace.retrievalTraceId()).isEqualTo("rt1");
        assertThat(trace.sourceCaseId()).isEqualTo("c1");
        assertThat(trace.sourceScore()).isEqualTo(0.85);
        assertThat(trace.steps()).hasSize(1);
        assertThat(trace.currentFeatures()).containsKey("f");
    }

    @Test void nullTraceIdRejected() {
        assertThatNullPointerException().isThrownBy(() ->
                new AdaptationTrace(null, null, "c1", 0.85,
                        List.of(step), Map.of(), Instant.now()));
    }

    @Test void nullStepsRejected() {
        assertThatNullPointerException().isThrownBy(() ->
                new AdaptationTrace("t1", null, "c1", 0.85,
                        null, Map.of(), Instant.now()));
    }

    @Test void nullFeaturesRejected() {
        assertThatNullPointerException().isThrownBy(() ->
                new AdaptationTrace("t1", null, "c1", 0.85,
                        List.of(step), null, Instant.now()));
    }

    @Test void nullTimestampRejected() {
        assertThatNullPointerException().isThrownBy(() ->
                new AdaptationTrace("t1", null, "c1", 0.85,
                        List.of(step), Map.of(), null));
    }

    @Test void nullSourceCaseIdAllowed() {
        var trace = new AdaptationTrace("t1", null, null, 0.85,
                List.of(step), Map.of(), Instant.now());
        assertThat(trace.sourceCaseId()).isNull();
    }

    @Test void nullRetrievalTraceIdAllowed() {
        var trace = new AdaptationTrace("t1", null, "c1", 0.85,
                List.of(step), Map.of(), Instant.now());
        assertThat(trace.retrievalTraceId()).isNull();
    }

    @Test void stepsDefensivelyCopied() {
        var list = new ArrayList<>(List.of(step));
        var trace = new AdaptationTrace("t1", null, "c1", 0.85,
                list, Map.of(), Instant.now());
        list.clear();
        assertThat(trace.steps()).hasSize(1);
    }

    @Test void featuresDefensivelyCopied() {
        var map = new HashMap<String, FeatureValue>();
        map.put("f", FeatureValue.string("v"));
        var trace = new AdaptationTrace("t1", null, "c1", 0.85,
                List.of(step), map, Instant.now());
        map.put("f2", FeatureValue.number(1.0));
        assertThat(trace.currentFeatures()).doesNotContainKey("f2");
    }

    @Test void cbrAdaptationRecordedRejectsNullTrace() {
        assertThatNullPointerException().isThrownBy(() ->
                new CbrAdaptationRecorded(null));
    }

    @Test void cbrAdaptationRecordedValid() {
        var trace = new AdaptationTrace("t1", null, "c1", 0.85,
                List.of(step), Map.of(), Instant.now());
        var event = new CbrAdaptationRecorded(trace);
        assertThat(event.trace()).isSameAs(trace);
    }
}
```

- [ ] **Step 4: Run tests — expect compilation failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-api`
Expected: FAIL — types do not exist yet

- [ ] **Step 5: Implement AdaptationAction**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptationAction.java`:

```java
package io.casehub.neocortex.memory.cbr;

public enum AdaptationAction {
    RETAINED,
    SUBSTITUTED,
    BOOSTED,
    SUPPRESSED,
    ADDED,
    REMOVED
}
```

- [ ] **Step 6: Implement AdaptedStep**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptedStep.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.Map;
import java.util.Objects;

public record AdaptedStep(
    String bindingName,
    String capabilityName,
    String workerName,
    String stepOutcome,
    int priority,
    Map<String, Object> parameters,
    AdaptationAction action,
    String reason
) {
    public AdaptedStep {
        Objects.requireNonNull(bindingName, "bindingName");
        Objects.requireNonNull(capabilityName, "capabilityName");
        if (priority < 0) throw new IllegalArgumentException("priority must be >= 0");
        parameters = parameters != null ? Map.copyOf(parameters) : Map.of();
        Objects.requireNonNull(action, "action");
    }
}
```

- [ ] **Step 7: Implement AdaptedPlan**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptedPlan.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.List;
import java.util.Objects;

public record AdaptedPlan(
    List<AdaptedStep> steps
) {
    public AdaptedPlan {
        Objects.requireNonNull(steps, "steps");
        steps = List.copyOf(steps);
    }
}
```

- [ ] **Step 8: Implement AdaptationTrace**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptationTrace.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Objects;

public record AdaptationTrace(
    String traceId,
    String retrievalTraceId,
    String sourceCaseId,
    double sourceScore,
    List<AdaptedStep> steps,
    Map<String, FeatureValue> currentFeatures,
    Instant timestamp
) {
    public AdaptationTrace {
        Objects.requireNonNull(traceId, "traceId");
        Objects.requireNonNull(steps, "steps");
        steps = List.copyOf(steps);
        Objects.requireNonNull(currentFeatures, "currentFeatures");
        currentFeatures = Map.copyOf(currentFeatures);
        Objects.requireNonNull(timestamp, "timestamp");
    }
}
```

- [ ] **Step 9: Implement CbrAdaptationRecorded**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrAdaptationRecorded.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.Objects;

public record CbrAdaptationRecorded(AdaptationTrace trace) {
    public CbrAdaptationRecorded {
        Objects.requireNonNull(trace, "trace");
    }
}
```

- [ ] **Step 10: Run tests — expect pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-api`
Expected: PASS — all new tests green

- [ ] **Step 11: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptationAction.java memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptedStep.java memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptedPlan.java memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AdaptationTrace.java memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrAdaptationRecorded.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptedStepTest.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptedPlanTest.java memory-api/src/test/java/io/casehub/neocortex/memory/cbr/AdaptationTraceTest.java
```
Message: `feat(#85): add plan adaptation value types — AdaptedStep, AdaptedPlan, AdaptationTrace, CbrAdaptationRecorded`

---

### Task 2: PlanAdapter SPI + NoOpPlanAdapter

**Files:**
- Create: `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanAdapter.java`
- Create: `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpPlanAdapter.java`
- Test: `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/NoOpPlanAdapterTest.java`

**Interfaces:**
- Consumes: `AdaptedPlan`, `AdaptedStep`, `AdaptationAction` (from Task 1), `ScoredCbrCase<PlanCbrCase>`, `FeatureValue` (existing)
- Produces: `PlanAdapter` SPI interface, `NoOpPlanAdapter` `@DefaultBean` — used by Tasks 3–4

- [ ] **Step 1: Write NoOpPlanAdapter tests**

Create `memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/NoOpPlanAdapterTest.java`:

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.cbr.AdaptationAction;
import io.casehub.neocortex.memory.cbr.FeatureValue;
import io.casehub.neocortex.memory.cbr.PlanCbrCase;
import io.casehub.neocortex.memory.cbr.PlanTrace;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class NoOpPlanAdapterTest {

    private final NoOpPlanAdapter adapter = new NoOpPlanAdapter();

    @Test void retainsAllSteps() {
        var trace1 = new PlanTrace("b1", "cap1", "w1", "SUCCESS", 0, Map.of());
        var trace2 = new PlanTrace("b2", "cap2", "w2", "FAILURE", 1, Map.of("p", "v"));
        var plan = new PlanCbrCase("problem", "solution", "WIN", 0.9,
                Map.of("f", FeatureValue.string("v")), List.of(trace1, trace2));
        var scored = new ScoredCbrCase<>(plan, "c1", 0.85);

        var result = adapter.adapt(scored, Map.of("f", FeatureValue.string("q")));

        assertThat(result.steps()).hasSize(2);
        assertThat(result.steps()).allSatisfy(s -> {
            assertThat(s.action()).isEqualTo(AdaptationAction.RETAINED);
            assertThat(s.reason()).isNull();
        });
    }

    @Test void preservesStepFields() {
        var trace = new PlanTrace("b1", "cap1", "w1", "SUCCESS", 3,
                Map.of("key", "val"));
        var plan = new PlanCbrCase("problem", "solution", null, null,
                Map.of(), List.of(trace));
        var scored = new ScoredCbrCase<>(plan, "c1", 0.5);

        var result = adapter.adapt(scored, Map.of());
        var step = result.steps().getFirst();

        assertThat(step.bindingName()).isEqualTo("b1");
        assertThat(step.capabilityName()).isEqualTo("cap1");
        assertThat(step.workerName()).isEqualTo("w1");
        assertThat(step.stepOutcome()).isEqualTo("SUCCESS");
        assertThat(step.priority()).isEqualTo(3);
        assertThat(step.parameters()).containsEntry("key", "val");
    }

    @Test void emptyTrace() {
        var plan = new PlanCbrCase("problem", "solution", null, null,
                Map.of(), List.of());
        var scored = new ScoredCbrCase<>(plan, "c1", 0.5);

        var result = adapter.adapt(scored, Map.of());

        assertThat(result.steps()).isEmpty();
    }
}
```

- [ ] **Step 2: Run tests — expect compilation failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory`
Expected: FAIL — `PlanAdapter` and `NoOpPlanAdapter` do not exist

- [ ] **Step 3: Implement PlanAdapter SPI**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanAdapter.java`:

```java
package io.casehub.neocortex.memory.cbr;

import java.util.Map;

public interface PlanAdapter {
    AdaptedPlan adapt(ScoredCbrCase<PlanCbrCase> retrieved,
                      Map<String, FeatureValue> currentFeatures);
}
```

- [ ] **Step 4: Implement NoOpPlanAdapter**

Create `memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpPlanAdapter.java`:

```java
package io.casehub.neocortex.memory.cbr.runtime;

import io.casehub.neocortex.memory.cbr.AdaptationAction;
import io.casehub.neocortex.memory.cbr.AdaptedPlan;
import io.casehub.neocortex.memory.cbr.AdaptedStep;
import io.casehub.neocortex.memory.cbr.FeatureValue;
import io.casehub.neocortex.memory.cbr.PlanAdapter;
import io.casehub.neocortex.memory.cbr.PlanCbrCase;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.Map;

@DefaultBean
@ApplicationScoped
public class NoOpPlanAdapter implements PlanAdapter {
    @Override
    public AdaptedPlan adapt(ScoredCbrCase<PlanCbrCase> retrieved,
                             Map<String, FeatureValue> currentFeatures) {
        return new AdaptedPlan(
                retrieved.cbrCase().planTrace().stream()
                        .map(t -> new AdaptedStep(
                                t.bindingName(), t.capabilityName(), t.workerName(),
                                t.stepOutcome(), t.priority(), t.parameters(),
                                AdaptationAction.RETAINED, null))
                        .toList()
        );
    }
}
```

- [ ] **Step 5: Run tests — expect pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-api/src/main/java/io/casehub/neocortex/memory/cbr/PlanAdapter.java memory/src/main/java/io/casehub/neocortex/memory/cbr/runtime/NoOpPlanAdapter.java memory/src/test/java/io/casehub/neocortex/memory/cbr/runtime/NoOpPlanAdapterTest.java
```
Message: `feat(#85): PlanAdapter SPI + NoOpPlanAdapter @DefaultBean`

---

### Task 3: TrackingPlanAdapter decorator in memory-cbr-tracking

**Files:**
- Create: `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/TrackingPlanAdapter.java`
- Test: `memory-cbr-tracking/src/test/java/io/casehub/neocortex/memory/cbr/tracking/TrackingPlanAdapterTest.java`

**Interfaces:**
- Consumes: `PlanAdapter` (from Task 2), `AdaptedPlan`, `AdaptedStep`, `AdaptationAction`, `AdaptationTrace`, `CbrAdaptationRecorded` (from Task 1), `ScoredCbrCase<PlanCbrCase>` (existing)
- Produces: `TrackingPlanAdapter` — CDI `@Decorator` that fires `CbrAdaptationRecorded` events

- [ ] **Step 1: Write TrackingPlanAdapter tests**

Create `memory-cbr-tracking/src/test/java/io/casehub/neocortex/memory/cbr/tracking/TrackingPlanAdapterTest.java`:

```java
package io.casehub.neocortex.memory.cbr.tracking;

import io.casehub.neocortex.memory.cbr.AdaptationAction;
import io.casehub.neocortex.memory.cbr.AdaptedPlan;
import io.casehub.neocortex.memory.cbr.AdaptedStep;
import io.casehub.neocortex.memory.cbr.CbrAdaptationRecorded;
import io.casehub.neocortex.memory.cbr.FeatureValue;
import io.casehub.neocortex.memory.cbr.PlanAdapter;
import io.casehub.neocortex.memory.cbr.PlanCbrCase;
import io.casehub.neocortex.memory.cbr.PlanTrace;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.*;

class TrackingPlanAdapterTest {

    private ScoredCbrCase<PlanCbrCase> scored() {
        var trace = new PlanTrace("b1", "cap1", "w1", "SUCCESS", 0, Map.of());
        var plan = new PlanCbrCase("problem", "solution", "WIN", 0.9,
                Map.of("f", FeatureValue.string("v")), List.of(trace));
        return new ScoredCbrCase<>(plan, "c1", 0.85);
    }

    private PlanAdapter noOpDelegate() {
        return (retrieved, features) -> new AdaptedPlan(
                retrieved.cbrCase().planTrace().stream()
                        .map(t -> new AdaptedStep(t.bindingName(), t.capabilityName(),
                                t.workerName(), t.stepOutcome(), t.priority(), t.parameters(),
                                AdaptationAction.RETAINED, null))
                        .toList());
    }

    @Test void firesEventAfterAdaptation() {
        var eventRef = new AtomicReference<CbrAdaptationRecorded>();
        var decorator = new TrackingPlanAdapter(noOpDelegate(), eventRef::set);

        var features = Map.of("f", FeatureValue.string("q"));
        decorator.adapt(scored(), features);

        assertThat(eventRef.get()).isNotNull();
        assertThat(eventRef.get().trace().traceId()).isNotBlank();
        assertThat(eventRef.get().trace().steps()).hasSize(1);
        assertThat(eventRef.get().trace().timestamp()).isNotNull();
    }

    @Test void traceContainsCorrectFields() {
        var eventRef = new AtomicReference<CbrAdaptationRecorded>();
        var decorator = new TrackingPlanAdapter(noOpDelegate(), eventRef::set);
        var features = Map.of("f", FeatureValue.string("q"));

        decorator.adapt(scored(), features);
        var trace = eventRef.get().trace();

        assertThat(trace.sourceCaseId()).isEqualTo("c1");
        assertThat(trace.sourceScore()).isEqualTo(0.85);
        assertThat(trace.currentFeatures()).containsKey("f");
        assertThat(trace.steps().getFirst().action()).isEqualTo(AdaptationAction.RETAINED);
    }

    @Test void trackingFailureDoesNotBreakAdaptation() {
        var decorator = new TrackingPlanAdapter(noOpDelegate(), e -> {
            throw new RuntimeException("event sink failure");
        });

        var result = decorator.adapt(scored(), Map.of());

        assertThat(result.steps()).hasSize(1);
        assertThat(result.steps().getFirst().bindingName()).isEqualTo("b1");
    }

    @Test void firesForNoOpAdapter() {
        var eventRef = new AtomicReference<CbrAdaptationRecorded>();
        var decorator = new TrackingPlanAdapter(noOpDelegate(), eventRef::set);

        var emptyPlan = new PlanCbrCase("problem", "solution", null, null,
                Map.of(), List.of());
        var scored = new ScoredCbrCase<>(emptyPlan, "c2", 0.3);
        decorator.adapt(scored, Map.of());

        assertThat(eventRef.get()).isNotNull();
        assertThat(eventRef.get().trace().steps()).isEmpty();
        assertThat(eventRef.get().trace().sourceCaseId()).isEqualTo("c2");
    }
}
```

- [ ] **Step 2: Run tests — expect compilation failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-cbr-tracking`
Expected: FAIL — `TrackingPlanAdapter` does not exist

- [ ] **Step 3: Implement TrackingPlanAdapter**

Create `memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/TrackingPlanAdapter.java`:

```java
package io.casehub.neocortex.memory.cbr.tracking;

import io.casehub.neocortex.memory.cbr.AdaptationTrace;
import io.casehub.neocortex.memory.cbr.AdaptedPlan;
import io.casehub.neocortex.memory.cbr.CbrAdaptationRecorded;
import io.casehub.neocortex.memory.cbr.FeatureValue;
import io.casehub.neocortex.memory.cbr.PlanAdapter;
import io.casehub.neocortex.memory.cbr.PlanCbrCase;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import io.quarkus.arc.properties.IfBuildProperty;
import jakarta.annotation.Priority;
import jakarta.decorator.Decorator;
import jakarta.decorator.Delegate;
import jakarta.enterprise.event.Event;
import jakarta.enterprise.inject.Any;
import jakarta.inject.Inject;
import org.jboss.logging.Logger;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.function.Consumer;

@Decorator
@Priority(50)
@IfBuildProperty(name = "casehub.cbr.adaptation-tracking.enabled", stringValue = "true")
public class TrackingPlanAdapter implements PlanAdapter {

    private static final Logger LOG = Logger.getLogger(TrackingPlanAdapter.class);

    private final PlanAdapter delegate;
    private final Consumer<CbrAdaptationRecorded> eventSink;

    @Inject
    TrackingPlanAdapter(@Delegate @Any PlanAdapter delegate,
                        Event<CbrAdaptationRecorded> recordedEvent) {
        this(delegate, recordedEvent::fire);
    }

    TrackingPlanAdapter(PlanAdapter delegate,
                        Consumer<CbrAdaptationRecorded> eventSink) {
        this.delegate = delegate;
        this.eventSink = eventSink;
    }

    @Override
    public AdaptedPlan adapt(ScoredCbrCase<PlanCbrCase> retrieved,
                             Map<String, FeatureValue> currentFeatures) {
        AdaptedPlan result = delegate.adapt(retrieved, currentFeatures);
        try {
            var trace = new AdaptationTrace(
                    UUID.randomUUID().toString(),
                    null,
                    retrieved.caseId(),
                    retrieved.score(),
                    result.steps(),
                    currentFeatures,
                    Instant.now()
            );
            eventSink.accept(new CbrAdaptationRecorded(trace));
        } catch (Exception e) {
            LOG.warn("CBR adaptation tracking failed — returning result unchanged", e);
        }
        return result;
    }
}
```

- [ ] **Step 4: Run tests — expect pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-cbr-tracking`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-cbr-tracking/src/main/java/io/casehub/neocortex/memory/cbr/tracking/TrackingPlanAdapter.java memory-cbr-tracking/src/test/java/io/casehub/neocortex/memory/cbr/tracking/TrackingPlanAdapterTest.java
```
Message: `feat(#85): TrackingPlanAdapter @Decorator — fires CbrAdaptationRecorded CDI events`

---

### Task 4: CLAUDE.md + full build verification

**Files:**
- Modify: `CLAUDE.md` — update module descriptions and memory-api type listings

- [ ] **Step 1: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: PASS — all modules compile and all tests green

- [ ] **Step 2: Update CLAUDE.md**

Add to the `memory-api` module description (after `CbrRetrievalTracker + ReactiveCbrRetrievalTracker` listings):
- `PlanAdapter` SPI
- `AdaptedPlan`, `AdaptedStep`, `AdaptationAction` value types
- `AdaptationTrace` audit record
- `CbrAdaptationRecorded` CDI event

Add to the `memory/` module description:
- `NoOpPlanAdapter @DefaultBean`

Add to the `memory-cbr-tracking/` module description:
- `TrackingPlanAdapter @Decorator @Priority(50)` with config property

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md
```
Message: `docs(#85): update CLAUDE.md — plan adaptation SPI types and modules`
