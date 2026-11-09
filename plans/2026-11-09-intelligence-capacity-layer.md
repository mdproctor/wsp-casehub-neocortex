# Intelligence Capacity Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #840 — Intelligence capacity layer
**Issue group:** #841 (Cognitive exploration epic)

**Goal:** Add cognitive capacity ceilings (relational complexity, associative reach, working memory span) that bound the search budget parameters (depth, laterality, breadth) based on intelligence rather than personality.

**Architecture:** New `CognitiveCapacityConfig` record on `CognitiveDefaults` (field 21). CDE derives from Jungian functions with compressed range [0.55, 0.95]. Tick participant applies hard ceilings after fatigue (step 7), before clamp (step 8). Capacity gap signal drives prose selection.

**Tech Stack:** Java 21, Quarkus 3.32.2, JUnit 5

## Global Constraints

- All capacity values in [0,1]. Boxed `Double` fields — null means "not specified."
- Compressed derivation range [0.55, 0.95] — Jungian correlation too weak for extreme values.
- Convergence gets no ceiling — personality-driven, not capacity-limited.
- Fatigue and capacity are independent — fatigue modifies raw, capacity caps result.
- Backward compatible — null `capacityConfig` disables ceilings, existing behaviour preserved.

---

## Batch 1: Type Foundation

### Task 1: CognitiveCapacityConfig record + CognitiveDefaults field 21

**Files:**
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/CognitiveCapacityConfig.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java`
- Test: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/CognitiveCapacityConfigTest.java`

**Interfaces:**
- Produces: `CognitiveCapacityConfig` record with `relationalComplexity()`, `associativeReach()`, `workingMemorySpan()` (all `Double`), `mergeWith()`, `*OrDefault()` accessors, `defaults()` factory, `withX()` builders. `CognitiveDefaults.capacityConfig()` field and `withCapacityConfig()` method.

- [ ] **Step 1: Write failing tests for CognitiveCapacityConfig**

```java
package io.casehub.neocortex.cognitive;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CognitiveCapacityConfigTest {

    @Test
    void defaults_returns_population_midpoint() {
        var config = CognitiveCapacityConfig.defaults();
        assertEquals(0.75, config.relationalComplexity());
        assertEquals(0.75, config.associativeReach());
        assertEquals(0.75, config.workingMemorySpan());
    }

    @Test
    void validation_rejects_out_of_range() {
        assertThrows(IllegalArgumentException.class,
            () -> new CognitiveCapacityConfig(1.5, 0.5, 0.5));
        assertThrows(IllegalArgumentException.class,
            () -> new CognitiveCapacityConfig(0.5, -0.1, 0.5));
    }

    @Test
    void null_fields_are_allowed() {
        var config = new CognitiveCapacityConfig(0.9, null, null);
        assertEquals(0.9, config.relationalComplexity());
        assertNull(config.associativeReach());
        assertNull(config.workingMemorySpan());
    }

    @Test
    void orDefault_returns_1_for_null() {
        var config = new CognitiveCapacityConfig(0.9, null, null);
        assertEquals(0.9, config.relationalComplexityOrDefault());
        assertEquals(1.0, config.associativeReachOrDefault());
        assertEquals(1.0, config.workingMemorySpanOrDefault());
    }

    @Test
    void mergeWith_fills_nulls_from_derived() {
        var explicit = new CognitiveCapacityConfig(0.9, null, null);
        var derived = new CognitiveCapacityConfig(0.7, 0.73, 0.79);
        var merged = explicit.mergeWith(derived);
        assertEquals(0.9, merged.relationalComplexity());
        assertEquals(0.73, merged.associativeReach());
        assertEquals(0.79, merged.workingMemorySpan());
    }

    @Test
    void mergeWith_explicit_wins_over_derived() {
        var explicit = new CognitiveCapacityConfig(0.9, 0.6, 0.8);
        var derived = new CognitiveCapacityConfig(0.7, 0.73, 0.79);
        var merged = explicit.mergeWith(derived);
        assertEquals(0.9, merged.relationalComplexity());
        assertEquals(0.6, merged.associativeReach());
        assertEquals(0.8, merged.workingMemorySpan());
    }

    @Test
    void withX_builders_produce_correct_copies() {
        var config = CognitiveCapacityConfig.defaults();
        var modified = config.withRelationalComplexity(0.9);
        assertEquals(0.9, modified.relationalComplexity());
        assertEquals(0.75, modified.associativeReach());
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -Dtest=CognitiveCapacityConfigTest -DfailIfNoTests=false`
Expected: Compilation failure — `CognitiveCapacityConfig` doesn't exist yet.

- [ ] **Step 3: Implement CognitiveCapacityConfig**

Create `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/CognitiveCapacityConfig.java` with the record from the spec — boxed `Double` fields, null-conditional validation, `mergeWith()`, `*OrDefault()` accessors, `defaults()`, `withX()` builders.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -Dtest=CognitiveCapacityConfigTest`
Expected: All 7 tests PASS.

- [ ] **Step 5: Add capacityConfig field to CognitiveDefaults**

Modify `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java`:
- Add `CognitiveCapacityConfig capacityConfig` as field 21 in the record declaration
- Update `empty()` factory — add null as the 21st argument
- Add `withCapacityConfig(CognitiveCapacityConfig capacityConfig)` method
- Update all 20 existing `withX()` methods to include `capacityConfig` in their constructor calls

This is the mechanical blast radius change. Each existing `withX()` method positionally reconstructs the record — add `capacityConfig` (or `this.capacityConfig`) as the last argument to each.

- [ ] **Step 6: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognitive-api,cognitive-index`
Expected: BUILD SUCCESS. No behavioral changes — just structural.

- [ ] **Step 7: Commit**

```bash
git add cognitive-api/src/main/java/io/casehub/neocortex/cognitive/CognitiveCapacityConfig.java
git add cognitive-api/src/test/java/io/casehub/neocortex/cognitive/CognitiveCapacityConfigTest.java
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java
git commit -m "feat(#840): add CognitiveCapacityConfig record and CognitiveDefaults field 21

Three-dimension cognitive capacity model: relationalComplexity (depth ceiling),
associativeReach (laterality ceiling), workingMemorySpan (breadth ceiling).
Boxed Double fields for per-field partial YAML merge.

Refs #840"
```

### Task 2: SearchBudget fields 8-11

**Files:**
- Modify: `cognition-api/src/main/java/io/casehub/neocortex/cognition/search/SearchBudget.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java` (constructor calls only — add 0.0 defaults)

**Interfaces:**
- Consumes: None (standalone record change)
- Produces: `SearchBudget.capacityConstrained()`, `SearchBudget.depthGap()`, `SearchBudget.breadthGap()`, `SearchBudget.lateralityGap()` — fields 8-11

- [ ] **Step 1: Add fields to SearchBudget record**

Add 4 new fields between `extremeActivation` and `evaluatedAt`:
```java
boolean capacityConstrained,    // field 8
double depthGap,                // field 9
double breadthGap,              // field 10
double lateralityGap,           // field 11
```

- [ ] **Step 2: Fix all callers that construct SearchBudget**

Find all callers using `ide_find_references` on the SearchBudget constructor. Add `false, 0.0, 0.0, 0.0` as arguments to preserve existing behavior. The primary caller is `SearchBudgetTickParticipant.tick()` — update it to pass the new defaults.

- [ ] **Step 3: Verify compilation across all modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognition-api,cognition`
Expected: BUILD SUCCESS.

- [ ] **Step 4: Commit**

```bash
git add cognition-api/src/main/java/io/casehub/neocortex/cognition/search/SearchBudget.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java
git commit -m "feat(#840): add capacity gap fields to SearchBudget record

Fields 8-11: capacityConstrained boolean + per-parameter gap values
(depthGap, breadthGap, lateralityGap). Defaults to false/0.0 — no
behavioral change until capacity ceiling logic is wired.

Refs #840"
```

## Batch 2: CDE Derivation

### Task 3: Jungian → capacity derivation + quality tests

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaultsRegistry.java` (if YAML parsing needs adjustment)
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveCapacityDerivationTest.java`

**Interfaces:**
- Consumes: `CognitiveCapacityConfig` from Task 1, `CognitiveDefaults.withCapacityConfig()` from Task 1
- Produces: `CognitiveDerivationEngine.deriveCapacity(List<WeightedTerm>)`, `mergeCapacity()` — CDE derives capacity values for any agent with a Jungian profile

- [ ] **Step 1: Write failing tests for derivation**

```java
package io.casehub.neocortex.cognitive.index;

import io.casehub.neocortex.cognitive.CognitiveCapacityConfig;
import org.junit.jupiter.api.Test;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;

class CognitiveCapacityDerivationTest {

    @Test
    void compressed_range_bounds() {
        // Analytical: ti=0.8, te=0.7, ni=0.6, ne=0.3, si=0.5
        var analytical = buildProfile(0.8, 0.7, 0.6, 0.3, 0.5);
        var config = CognitiveDerivationEngine.deriveCapacity(analytical);
        assertNotNull(config);
        assertTrue(config.relationalComplexity() >= 0.55 && config.relationalComplexity() <= 0.95);
        assertTrue(config.associativeReach() >= 0.55 && config.associativeReach() <= 0.95);
        assertTrue(config.workingMemorySpan() >= 0.55 && config.workingMemorySpan() <= 0.95);
    }

    @Test
    void analytical_has_higher_relational_than_exploratory() {
        var analytical = buildProfile(0.8, 0.7, 0.6, 0.3, 0.5);
        var exploratory = buildProfile(0.2, 0.2, 0.5, 0.9, 0.3);
        var a = CognitiveDerivationEngine.deriveCapacity(analytical);
        var e = CognitiveDerivationEngine.deriveCapacity(exploratory);
        assertTrue(a.relationalComplexity() > e.relationalComplexity(),
            "Analytical (high Ti+Te) should have higher relational complexity");
    }

    @Test
    void exploratory_has_higher_associative_than_analytical() {
        var analytical = buildProfile(0.8, 0.7, 0.6, 0.3, 0.5);
        var exploratory = buildProfile(0.2, 0.2, 0.5, 0.9, 0.3);
        var a = CognitiveDerivationEngine.deriveCapacity(analytical);
        var e = CognitiveDerivationEngine.deriveCapacity(exploratory);
        assertTrue(e.associativeReach() > a.associativeReach(),
            "Exploratory (high Ne+Ni) should have higher associative reach");
    }

    @Test
    void null_profile_returns_null() {
        assertNull(CognitiveDerivationEngine.deriveCapacity(null));
        assertNull(CognitiveDerivationEngine.deriveCapacity(List.of()));
    }

    @Test
    void concrete_analytical_values() {
        // ti=0.8, te=0.7 → relational = compress(0.5*(0.8+0.7)) = compress(0.75) = 0.85
        var profile = buildProfile(0.8, 0.7, 0.6, 0.3, 0.5);
        var config = CognitiveDerivationEngine.deriveCapacity(profile);
        assertEquals(0.85, config.relationalComplexity(), 0.001);
        assertEquals(0.73, config.associativeReach(), 0.001);
        assertEquals(0.79, config.workingMemorySpan(), 0.001);
    }

    @Test
    void merge_explicit_wins_over_derived() {
        var explicit = new CognitiveCapacityConfig(0.9, null, null);
        var derived = new CognitiveCapacityConfig(0.7, 0.73, 0.79);
        var merged = CognitiveDerivationEngine.mergeCapacity(explicit, derived);
        assertEquals(0.9, merged.relationalComplexity());
        assertEquals(0.73, merged.associativeReach());
        assertEquals(0.79, merged.workingMemorySpan());
    }

    @Test
    void merge_null_explicit_returns_derived() {
        var derived = new CognitiveCapacityConfig(0.7, 0.73, 0.79);
        var merged = CognitiveDerivationEngine.mergeCapacity(null, derived);
        assertSame(derived, merged);
    }

    @Test
    void merge_null_derived_returns_explicit() {
        var explicit = new CognitiveCapacityConfig(0.9, null, null);
        var merged = CognitiveDerivationEngine.mergeCapacity(explicit, null);
        assertSame(explicit, merged);
    }

    // Helper: builds WeightedTerm list for ti, te, ni, ne, si
    private static List<WeightedTerm> buildProfile(
            double ti, double te, double ni, double ne, double si) {
        return List.of(
            new WeightedTerm("ti", ti), new WeightedTerm("te", te),
            new WeightedTerm("ni", ni), new WeightedTerm("ne", ne),
            new WeightedTerm("si", si));
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveCapacityDerivationTest -DfailIfNoTests=false`
Expected: Compilation failure — `deriveCapacity` method doesn't exist yet.

- [ ] **Step 3: Implement deriveCapacity() and mergeCapacity()**

Add to `CognitiveDerivationEngine.java`:
- `static CognitiveCapacityConfig deriveCapacity(List<WeightedTerm> profile)` — Jungian→capacity with `compress()` function
- `static CognitiveCapacityConfig mergeCapacity(CognitiveCapacityConfig explicit, CognitiveCapacityConfig derived)` — null-coalescing merge
- `private static double compress(double raw)` — maps [0,1] → [0.55, 0.95]

Wire into `derive()`: call `deriveCapacity(descriptor.dispositionProfile())` and chain `.withCapacityConfig(capacity)`.

Wire into `deriveAndMerge()`: add `.withCapacityConfig(mergeCapacity(explicit.capacityConfig(), derived.capacityConfig()))`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveCapacityDerivationTest`
Expected: All 8 tests PASS.

- [ ] **Step 5: Verify full module build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: BUILD SUCCESS — existing tests still pass with the new derivation wired in.

- [ ] **Step 6: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java
git add cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveCapacityDerivationTest.java
git commit -m "feat(#840): add Jungian → capacity CDE derivation pathway

deriveCapacity() maps Ti+Te → relational, Ne+Ni → associative, Te+Si → WM span
with compressed range [0.55, 0.95]. mergeCapacity() enables per-field YAML override.

Refs #840"
```

## Batch 3: Pipeline Ceiling

### Task 4: Capacity ceiling + gap signal in tick participant

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java`
- Create: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/SearchBudgetCapacityTest.java`

**Interfaces:**
- Consumes: `CognitiveCapacityConfig` from Task 1, `CognitiveDefaults.capacityConfig()` from Task 1, `SearchBudget` fields 8-11 from Task 2
- Produces: Tick-time capacity ceiling application — `SearchBudget` instances with correct `capacityConstrained`, `depthGap`, `breadthGap`, `lateralityGap` values

- [ ] **Step 1: Write failing quality tests**

Create `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/SearchBudgetCapacityTest.java` with 12 test methods from the spec: `capacity_ceiling_bounds_parameter`, `capacity_below_activation_has_no_effect`, `capacity_gap_signal_fires_above_threshold`, `capacity_gap_below_threshold_does_not_fire`, `null_capacity_preserves_existing_behaviour`, `convergence_never_capped_by_capacity`, `capacity_applies_after_fatigue`, `cde_derivation_produces_compressed_range`, `explicit_yaml_overrides_derived_capacity`, `partial_yaml_fills_unspecified_from_derivation`, `partial_yaml_without_derivation_leaves_unspecified_uncapped`, `capacity_differentiation_matches_jungian_direction`.

These tests exercise the tick participant's ceiling logic by constructing `CognitiveDefaults` with `capacityConfig`, running `tick()` (or the equivalent compute methods), and asserting on the resulting `SearchBudget` values.

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=SearchBudgetCapacityTest -DfailIfNoTests=false`
Expected: Tests fail — ceiling logic not implemented yet.

- [ ] **Step 3: Implement capacity ceiling in tick participant**

Modify `SearchBudgetTickParticipant.tick()` — add step 7 between fatigue (step 6) and clamp (step 8):

```java
// Step 7: Capacity ceiling
double depthGap = 0.0, breadthGap = 0.0, lateralityGap = 0.0;
boolean capacityConstrained = false;
CognitiveCapacityConfig capacity = defaults.capacityConfig();
if (capacity != null) {
    double rc = capacity.relationalComplexityOrDefault();
    double wm = capacity.workingMemorySpanOrDefault();
    double ar = capacity.associativeReachOrDefault();

    depthGap = Math.max(0.0, depth - rc);
    breadthGap = Math.max(0.0, breadth - wm);
    lateralityGap = Math.max(0.0, laterality - ar);

    depth = Math.min(rc, depth);
    breadth = Math.min(wm, breadth);
    laterality = Math.min(ar, laterality);

    double maxGap = Math.max(depthGap, Math.max(breadthGap, lateralityGap));
    capacityConstrained = maxGap > 0.05;
}
```

Update the `SearchBudget` construction to pass the new fields: `capacityConstrained, depthGap, breadthGap, lateralityGap`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=SearchBudgetCapacityTest`
Expected: All 12 tests PASS.

- [ ] **Step 5: Run full cognition module tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition`
Expected: BUILD SUCCESS — existing tests pass with null capacityConfig (backward compatible).

- [ ] **Step 6: Commit**

```bash
git add cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java
git add cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/SearchBudgetCapacityTest.java
git commit -m "feat(#840): apply capacity ceilings in search budget tick participant

Step 7 in pipeline: Math.min(ceiling, raw) for depth, breadth, laterality
after fatigue. Per-parameter gap values + capacityConstrained boolean flag
with 0.05 noise threshold.

Refs #840"
```

## Batch 4: Prose & Scenario

### Task 5: Unified prose generation + prose composition

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SearchBudgetDescriptionGenerationPhase.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetPromptSection.java`

**Interfaces:**
- Consumes: `CognitiveDefaults.capacityConfig()` from Task 1, `SearchBudget.capacityConstrained()` from Task 2
- Produces: MindMap `constrained-description` property on COGNITIVE nodes. Prose composition in prompt section.

- [ ] **Step 1: Update SearchBudgetDescriptionGenerationPhase**

Replace `SYSTEM_PROMPT` / `SYSTEM_PROMPT_WITH_EXTREME` dual-variant approach with `SYSTEM_PROMPT_UNIFIED` as specified. Update `buildUserPrompt()` to conditionally include capacity parameters when `capacityConfig != null`. Update response parsing to use `extractField(response, "normal")` with `"description"` fallback. Update `crystallise()` to store `"constrained-description"` property.

- [ ] **Step 2: Update SearchBudgetPromptSection for composition**

Replace exclusive priority selection with composition: capacity-constrained prose prepends to base (normal or extreme). Follow the `modulateByContinuum()` pattern from the spec:

```java
String base = budget.extremeActivation()
    ? readCrystallisedProse(agentId, tenantId, "extreme-description")
    : readCrystallisedProse(agentId, tenantId, "description");
if (budget.capacityConstrained()) {
    String constrained = readCrystallisedProse(agentId, tenantId, "constrained-description");
    if (constrained != null && base != null) {
        return modulateByContinuum(constrained + " " + base);
    }
    if (constrained != null) {
        return modulateByContinuum(constrained);
    }
}
if (base != null) {
    return modulateByContinuum(base);
}
```

- [ ] **Step 3: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl mindmap-intelligence,cognition`
Expected: BUILD SUCCESS.

- [ ] **Step 4: Commit**

```bash
git add mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SearchBudgetDescriptionGenerationPhase.java
git add cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetPromptSection.java
git commit -m "feat(#840): unified prose generation + capacity-constrained prose composition

Single SYSTEM_PROMPT_UNIFIED replaces dual-variant approach. Capacity
prose prepends to base (normal or extreme) via composition, not exclusive
priority. Fixes per-batch format mismatch bug.

Refs #840"
```

### Task 6: CognitionTestHarness capacity scenario

**Files:**
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/search/SearchBudgetCapacityScenarioTest.java`

**Interfaces:**
- Consumes: All prior tasks — full pipeline exercised end-to-end

- [ ] **Step 1: Write scenario test**

Following the #849 S1 personality differentiation pattern, create a CognitionTestHarness scenario with 3 agents:

1. **Analytical agent** — high depth personality (midpoint 0.3, high depth drive), moderate relational capacity (0.65). Verify: depth capped at 0.65, `capacityConstrained = true`, constrained prose prepended.
2. **Exploratory agent** — high laterality personality, high associative reach (0.90). Verify: laterality NOT capped (capacity > activation), `capacityConstrained = false`, normal prose selected.
3. **Default agent** — null `capacityConfig`. Verify: full backward compatibility, `capacityConstrained = false`, no constrained prose.

- [ ] **Step 2: Run scenario test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SearchBudgetCapacityScenarioTest`
Expected: All 3 scenarios PASS.

- [ ] **Step 3: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests && JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api,cognitive-index,cognition-api,cognition,mindmap-intelligence`
Expected: BUILD SUCCESS across all affected modules.

- [ ] **Step 4: Commit**

```bash
git add cognition/src/test/java/io/casehub/neocortex/cognition/search/SearchBudgetCapacityScenarioTest.java
git commit -m "test(#840): CognitionTestHarness capacity scenario — 3 agent profiles

Analytical (capped depth), exploratory (uncapped laterality), default
(null capacity — backward compatible). Full pipeline exercise.

Refs #840"
```

## References

- `specs/issue-840-intelligence-capacity/2026-11-09-intelligence-capacity-layer-design.md` — design spec
- `specs/issue-840-intelligence-capacity/decisions.md` — 8 design decisions
- `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/SearchBudgetConfig.java` — existing search budget config pattern
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java:33` — 20-field record to extend
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java` — 15 existing derivation pathways
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/search/SearchBudget.java:31` — 7-field record to extend
- `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java:42` — tick-time pipeline
- `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetPromptSection.java:26` — prose selection
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/SearchBudgetDescriptionGenerationPhase.java:41` — prose generation
- `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/SearchBudgetQualityTest.java` — existing quality test pattern
- `specs/issue-839-search-budget-situational-strength/2026-11-08-search-budget-situational-strength-design.md` — #839 spec (forward interaction section)
- GitHub #840, #841, #890, #891, #892
