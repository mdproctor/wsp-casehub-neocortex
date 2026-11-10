# Shared Fatigue Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #880 — Search budget: shared fatigue substrate with regulation fatigue
**Issue group:** #841

**Goal:** Unify search fatigue and regulation fatigue into a shared cognitive resource pool, implementing Hockey's (1997) compensatory control theory where all effortful cognitive activity draws from a limited processing resource.

**Architecture:** A `CognitiveResourcePool` SPI in `cognition-api` tracks shared per-agent cognitive depletion. Two initial sources contribute effort: search intensity (when above extremePeak) and emotion regulation (proportional to regulation effort). Consumers read depletion level and apply their own effects. `SearchFatigueEffects` is renamed to `SearchFatigueEffects` (retaining only the 4 per-parameter effects), `RegulationFatigueTracker` is deleted. Pool config is personality-derived via `CognitiveDerivationEngine`.

**Tech Stack:** Java 21, Quarkus CDI, JUnit 5

## Global Constraints

- Java 21 source, Java 26 JVM
- `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install` for builds
- Use `mvn` not `./mvnw`
- Pre-release: clean API, no backwards compatibility shims
- All commits reference issue: `Refs #880` or `Closes #880`
- Use `ide_refactor_rename` for renames, `ide_create_file` for new .java files

---

## Batch 1: Foundation — Config + SPI + Rename

### Task 1: Create CognitiveResourcePoolConfig and SearchFatigueEffects rename

**Files:**
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/CognitiveResourcePoolConfig.java`
- Create: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/CognitiveResourcePoolConfigTest.java`
- Rename: `SearchFatigueEffects` → `SearchFatigueEffects` (use `ide_refactor_rename`)
- Modify: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/SearchBudgetConfig.java` — rename `fatigue()` → `fatigueEffects()`, type `SearchFatigueEffects`
- Modify: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/SearchFatigueEffectsTest.java` (auto-renamed from FatigueConfigTest) — remove pool param tests, update remaining tests
- Modify: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/SearchBudgetConfigTest.java` — update `withFatigueEffects` → `withFatigueEffects`

**Interfaces:**
- Produces: `CognitiveResourcePoolConfig(int maxEffort, double recoveryRate)` with `defaults()`, `withMaxEffort(int)`, `withRecoveryRate(double)`, validation
- Produces: `SearchFatigueEffects(double depthEffect, double breadthEffect, double lateralityEffect, double convergenceEffect)` — renamed from FatigueConfig with maxTicks/recoveryRate removed
- Produces: `SearchBudgetConfig.fatigueEffects()` returning `SearchFatigueEffects`

- [ ] **Step 1: Write CognitiveResourcePoolConfig test**

```java
package io.casehub.neocortex.cognitive;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class CognitiveResourcePoolConfigTest {

    @Test
    void defaults_produces_valid_config() {
        var config = CognitiveResourcePoolConfig.defaults();
        assertEquals(10, config.maxEffort());
        assertEquals(0.5, config.recoveryRate());
    }

    @Test
    void maxEffort_must_be_positive() {
        assertThrows(IllegalArgumentException.class,
                () -> CognitiveResourcePoolConfig.defaults().withMaxEffort(0));
    }

    @Test
    void negative_recoveryRate_rejected() {
        assertThrows(IllegalArgumentException.class,
                () -> CognitiveResourcePoolConfig.defaults().withRecoveryRate(-0.1));
    }

    @Test
    void zero_recoveryRate_allowed() {
        var config = CognitiveResourcePoolConfig.defaults().withRecoveryRate(0.0);
        assertEquals(0.0, config.recoveryRate());
    }

    @Test
    void withMaxEffort_returns_copy() {
        var config = CognitiveResourcePoolConfig.defaults().withMaxEffort(20);
        assertEquals(20, config.maxEffort());
        assertEquals(0.5, config.recoveryRate());
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -Dtest=CognitiveResourcePoolConfigTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — class not found

- [ ] **Step 3: Implement CognitiveResourcePoolConfig**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognitive;

public record CognitiveResourcePoolConfig(
        int maxEffort,
        double recoveryRate) {

    public CognitiveResourcePoolConfig {
        if (maxEffort < 1) {
            throw new IllegalArgumentException("maxEffort must be >= 1, got " + maxEffort);
        }
        if (recoveryRate < 0) {
            throw new IllegalArgumentException("recoveryRate must be >= 0, got " + recoveryRate);
        }
    }

    public static CognitiveResourcePoolConfig defaults() {
        return new CognitiveResourcePoolConfig(10, 0.5);
    }

    public CognitiveResourcePoolConfig withMaxEffort(int v) {
        return new CognitiveResourcePoolConfig(v, recoveryRate);
    }

    public CognitiveResourcePoolConfig withRecoveryRate(double v) {
        return new CognitiveResourcePoolConfig(maxEffort, v);
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -Dtest=CognitiveResourcePoolConfigTest`
Expected: PASS

- [ ] **Step 5: Rename FatigueConfig → SearchFatigueEffects**

Use `ide_refactor_rename` on `SearchFatigueEffects` class → `SearchFatigueEffects`. This updates all references project-wide.

- [ ] **Step 6: Remove pool parameters from SearchFatigueEffects**

Use `ide_edit_member` to replace the record declaration. Remove `maxTicks` and `recoveryRate` fields. Remove `withMaxTicks()` and `withRecoveryRate()` methods. Update compact constructor to remove pool param validation. Update `defaults()` to `new SearchFatigueEffects(-0.1, -0.2, -0.15, 0.1)`. Update all `withXxx()` methods to use 4-param constructor.

New record:

```java
public record SearchFatigueEffects(
        double depthEffect,
        double breadthEffect,
        double lateralityEffect,
        double convergenceEffect) {

    public SearchFatigueEffects {
        validateEffect("depthEffect", depthEffect);
        validateEffect("breadthEffect", breadthEffect);
        validateEffect("lateralityEffect", lateralityEffect);
        validateEffect("convergenceEffect", convergenceEffect);
    }

    public static SearchFatigueEffects defaults() {
        return new SearchFatigueEffects(-0.1, -0.2, -0.15, 0.1);
    }

    public SearchFatigueEffects withDepthEffect(double v) {
        return new SearchFatigueEffects(v, breadthEffect, lateralityEffect, convergenceEffect);
    }

    public SearchFatigueEffects withBreadthEffect(double v) {
        return new SearchFatigueEffects(depthEffect, v, lateralityEffect, convergenceEffect);
    }

    public SearchFatigueEffects withLateralityEffect(double v) {
        return new SearchFatigueEffects(depthEffect, breadthEffect, v, convergenceEffect);
    }

    public SearchFatigueEffects withConvergenceEffect(double v) {
        return new SearchFatigueEffects(depthEffect, breadthEffect, lateralityEffect, v);
    }

    private static void validateEffect(String name, double value) {
        if (value < -1.0 || value > 1.0) {
            throw new IllegalArgumentException(name + " must be in [-1,1], got " + value);
        }
    }
}
```

- [ ] **Step 7: Rename SearchBudgetConfig.fatigue() → fatigueEffects()**

Use `ide_refactor_rename` on the `fatigue` field/accessor in `SearchBudgetConfig` → `SearchFatigueEffects`. Update `withFatigue()` → `withFatigueEffects()`. Fix any compilation errors from the 6→4 param constructor change in `SearchBudgetConfig.defaults()` and `withFatigueEffects()`.

- [ ] **Step 8: Update SearchFatigueEffectsTest (formerly FatigueConfigTest)**

Remove tests for removed fields: `maxTicks_must_be_positive`, `negative_maxTicks_rejected`, `negative_recoveryRate_rejected`, `zero_recoveryRate_allowed`, `withMaxTicks_returns_copy_preserving_other_fields`. Update remaining tests for 4-param constructor.

- [ ] **Step 9: Fix compilation errors in downstream consumers**

After the rename and field removal, fix compilation errors in:
- `SearchBudgetTickParticipant.java` — `config.fatigue()` → `config.fatigueEffects()`, `fatigueConfig.maxTicks()` and `fatigueConfig.recoveryRate()` references need temporary stubs or removal (will be replaced by pool in Task 4)
- `CognitiveDerivationEngine.java` — `new FatigueConfig(6 params)` → `new SearchFatigueEffects(4 params)` (pool params extracted to separate construction)
- `SearchBudgetConfigTest.java` — `withFatigueEffects` → `withFatigueEffects`
- Test files referencing `FatigueConfig.defaults()` → `SearchFatigueEffects.defaults()`

- [ ] **Step 10: Build cognitive-api module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api`
Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(#880): add CognitiveResourcePoolConfig, rename FatigueConfig → SearchFatigueEffects

Extract pool parameters (maxEffort, recoveryRate) to new
CognitiveResourcePoolConfig. SearchFatigueEffects retains only
the 4 per-parameter search budget effects.

Refs #880

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Create CognitiveResourcePool SPI and DefaultCognitiveResourcePool

**Files:**
- Create: `cognition-api/src/main/java/io/casehub/neocortex/cognition/core/CognitiveResourcePool.java`
- Create: `cognition/src/main/java/io/casehub/neocortex/cognition/core/DefaultCognitiveResourcePool.java`
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/core/DefaultCognitiveResourcePoolTest.java`
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/CognitionDefaultBeans.java` — add pool producer

**Interfaces:**
- Consumes: `CognitiveResourcePoolConfig` from Task 1
- Produces: `CognitiveResourcePool` SPI — `recordEffort(String agentId, String tenantId, double amount)`, `recordRecovery(String agentId, String tenantId, double recoveryRate)`, `currentDepletion(String agentId, String tenantId)` → double [0,1]
- Produces: `DefaultCognitiveResourcePool` — `@DefaultBean @ApplicationScoped` implementation using `ConcurrentHashMap<String, Double>`

- [ ] **Step 1: Write DefaultCognitiveResourcePool tests**

```java
package io.casehub.neocortex.cognition.core;

import io.casehub.neocortex.cognitive.CognitiveResourcePoolConfig;
import io.casehub.neocortex.cognitive.index.CognitiveDefaults;
import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class DefaultCognitiveResourcePoolTest {

    private DefaultCognitiveResourcePool pool;

    @BeforeEach
    void setUp() {
        var config = CognitiveResourcePoolConfig.defaults();
        var registry = new CognitiveDefaultsRegistry() {
            @Override
            public Optional<CognitiveDefaults> forAgent(String agentId) {
                return Optional.of(CognitiveDefaults.empty(agentId)
                        .withCognitiveResourcePoolConfig(config));
            }
            @Override
            public CognitiveDefaults forAgentOrDefaults(String agentId) {
                return forAgent(agentId).orElseThrow();
            }
        };
        pool = new DefaultCognitiveResourcePool(registry);
    }

    @Test
    void initially_zero_depletion() {
        assertEquals(0.0, pool.currentDepletion("a1", "t1"));
    }

    @Test
    void recordEffort_increases_depletion() {
        pool.recordEffort("a1", "t1", 1.0);
        assertTrue(pool.currentDepletion("a1", "t1") > 0.0);
    }

    @Test
    void depletion_uses_logarithmic_scaling() {
        pool.recordEffort("a1", "t1", 5.0);
        double depletion = pool.currentDepletion("a1", "t1");
        double expected = Math.log(1 + 5.0) / Math.log(1 + 10);
        assertEquals(expected, depletion, 1e-9);
    }

    @Test
    void recordRecovery_decreases_depletion() {
        pool.recordEffort("a1", "t1", 3.0);
        double before = pool.currentDepletion("a1", "t1");
        pool.recordRecovery("a1", "t1", 0.5);
        assertTrue(pool.currentDepletion("a1", "t1") < before);
    }

    @Test
    void recovery_floors_at_zero() {
        pool.recordEffort("a1", "t1", 0.1);
        pool.recordRecovery("a1", "t1", 10.0);
        assertEquals(0.0, pool.currentDepletion("a1", "t1"));
    }

    @Test
    void agents_are_isolated() {
        pool.recordEffort("a1", "t1", 5.0);
        assertEquals(0.0, pool.currentDepletion("a2", "t1"));
    }

    @Test
    void multi_source_effort_accumulates() {
        pool.recordEffort("a1", "t1", 1.0);
        pool.recordEffort("a1", "t1", 1.0);
        double expected = Math.log(1 + 2.0) / Math.log(1 + 10);
        assertEquals(expected, pool.currentDepletion("a1", "t1"), 1e-9);
    }

    @Test
    void net_contribution_effort_exceeds_recovery() {
        pool.recordEffort("a1", "t1", 3.0);
        double afterEffort = pool.currentDepletion("a1", "t1");
        pool.recordEffort("a1", "t1", 1.0);
        pool.recordRecovery("a1", "t1", 0.3);
        assertTrue(pool.currentDepletion("a1", "t1") > afterEffort);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=DefaultCognitiveResourcePoolTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — class not found

- [ ] **Step 3: Create CognitiveResourcePool SPI**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.core;

public interface CognitiveResourcePool {

    void recordEffort(String agentId, String tenantId, double amount);

    void recordRecovery(String agentId, String tenantId, double recoveryRate);

    double currentDepletion(String agentId, String tenantId);
}
```

- [ ] **Step 4: Implement DefaultCognitiveResourcePool**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognition.core;

import io.casehub.neocortex.cognitive.CognitiveResourcePoolConfig;
import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;

import java.util.concurrent.ConcurrentHashMap;

public class DefaultCognitiveResourcePool implements CognitiveResourcePool {

    private final CognitiveDefaultsRegistry defaultsRegistry;
    private final ConcurrentHashMap<String, Double> accumulators = new ConcurrentHashMap<>();

    public DefaultCognitiveResourcePool(CognitiveDefaultsRegistry defaultsRegistry) {
        this.defaultsRegistry = defaultsRegistry;
    }

    @Override
    public void recordEffort(String agentId, String tenantId, double amount) {
        if (amount <= 0) return;
        String key = agentId + ":" + tenantId;
        accumulators.merge(key, amount, Double::sum);
    }

    @Override
    public void recordRecovery(String agentId, String tenantId, double recoveryRate) {
        if (recoveryRate <= 0) return;
        String key = agentId + ":" + tenantId;
        accumulators.computeIfPresent(key, (k, v) -> {
            double recovered = v - recoveryRate;
            return recovered <= 0.0 ? null : recovered;
        });
    }

    @Override
    public double currentDepletion(String agentId, String tenantId) {
        String key = agentId + ":" + tenantId;
        double accumulator = accumulators.getOrDefault(key, 0.0);
        if (accumulator <= 0.0) return 0.0;
        var defaults = defaultsRegistry.forAgentOrDefaults(agentId);
        var poolConfig = defaults.cognitiveResourcePoolConfig();
        int maxEffort = poolConfig != null ? poolConfig.maxEffort()
                : CognitiveResourcePoolConfig.defaults().maxEffort();
        return Math.min(1.0, Math.log(1 + accumulator) / Math.log(1 + maxEffort));
    }
}
```

- [ ] **Step 5: Add CognitiveDefaults.cognitiveResourcePoolConfig field**

Use `ide_edit_member` on the `CognitiveDefaults` record declaration to add `CognitiveResourcePoolConfig cognitiveResourcePoolConfig` as the 22nd field (nullable). Add `withCognitiveResourcePoolConfig()` wither method. Update `empty()` factory to pass `null`. Update compact constructor (all 22 fields). Update all existing `withXxx()` methods to include the new field in their constructor call.

- [ ] **Step 6: Add @DefaultBean producer to CognitionDefaultBeans**

Use `ide_insert_member` to add a producer method:

```java
@Produces
@DefaultBean
@Singleton
CognitiveResourcePool cognitiveResourcePool(CognitiveDefaultsRegistry registry) {
    return new DefaultCognitiveResourcePool(registry);
}
```

- [ ] **Step 7: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=DefaultCognitiveResourcePoolTest`
Expected: PASS

- [ ] **Step 8: Build full project to verify no compilation errors**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl cognitive-api,cognition-api,cognitive-index,cognition`
Expected: BUILD SUCCESS

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(#880): add CognitiveResourcePool SPI and DefaultCognitiveResourcePool

Shared per-agent cognitive resource pool with logarithmic depletion.
Sources contribute effort, consumers read depletion level.
CognitiveDefaults gains cognitiveResourcePoolConfig field (#22).

Refs #880

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Batch 2: Source Integration

### Task 3: Integrate pool into SearchBudgetTickParticipant

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java` — inject pool, replace FatigueState
- Delete: `cognition/src/main/java/io/casehub/neocortex/cognition/search/FatigueState.java` (use `ide_refactor_safe_delete`)
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipantTest.java` — update fatigue tests to use pool

**Interfaces:**
- Consumes: `CognitiveResourcePool` from Task 2, `SearchFatigueEffects` from Task 1, `CognitiveResourcePoolConfig` from Task 1
- Produces: same `SearchBudget` output — behavior is equivalent for search-only scenarios

- [ ] **Step 1: Update SearchBudgetTickParticipant to accept CognitiveResourcePool**

Add `@Nullable CognitiveResourcePool` as a constructor parameter. Remove `fatigueStates` field and `FatigueState` import.

Use `ide_edit_member` on the constructor to add the pool parameter:

```java
public SearchBudgetTickParticipant(
        DriveOrchestrator driveOrchestrator,
        @Nullable AppraisalTickParticipant appraisalParticipant,
        @Nullable GutFeelingParticipant gutFeelingParticipant,
        @Nullable MoodOrchestrator moodOrchestrator,
        CognitiveDefaultsRegistry defaultsRegistry,
        @Nullable CognitionConfig cognitionConfig,
        @Nullable CuriosityDrive curiosityDrive,
        @Nullable CognitiveResourcePool cognitiveResourcePool) {
    this.driveOrchestrator = driveOrchestrator;
    this.appraisalParticipant = appraisalParticipant;
    this.gutFeelingParticipant = gutFeelingParticipant;
    this.moodOrchestrator = moodOrchestrator;
    this.defaultsRegistry = defaultsRegistry;
    this.cognitionConfig = cognitionConfig;
    this.curiosityDrive = curiosityDrive;
    this.cognitiveResourcePool = cognitiveResourcePool;
}
```

Add field: `private final @Nullable CognitiveResourcePool cognitiveResourcePool;`

Remove field: `private final ConcurrentHashMap<String, FatigueState> fatigueStates = new ConcurrentHashMap<>();`

- [ ] **Step 2: Replace fatigue logic in tick() method**

Use `ide_replace_member` on the `tick` method. Replace the fatigue block (lines ~130-155) with:

```java
SearchFatigueEffects fatigueEffects = config.fatigueEffects();
if (fatigueEffects != null && cognitiveResourcePool != null) {
    var poolConfig = defaults.cognitiveResourcePoolConfig();
    if (compositeIntensity > config.extremePeak()) {
        cognitiveResourcePool.recordEffort(agentId, tenantId, 1.0);
    } else if (poolConfig != null) {
        cognitiveResourcePool.recordRecovery(agentId, tenantId, poolConfig.recoveryRate());
    }
    double depletion = cognitiveResourcePool.currentDepletion(agentId, tenantId);
    if (depletion > 0.0) {
        depth += depletion * fatigueEffects.depthEffect();
        breadth += depletion * fatigueEffects.breadthEffect();
        laterality += depletion * fatigueEffects.lateralityEffect();
        convergence += depletion * fatigueEffects.convergenceEffect();
    }
}
```

- [ ] **Step 3: Delete FatigueState**

Use `ide_refactor_safe_delete` on `FatigueState.java`.

- [ ] **Step 4: Update fatigue tests in SearchBudgetTickParticipantTest**

Update the existing fatigue tests (`fatigue_accumulates_and_degrades_breadth`, `fatigue_does_not_accumulate_below_peak`) to:
- Create a `DefaultCognitiveResourcePool` and pass it to the participant constructor
- Set up `CognitiveDefaults` with `CognitiveResourcePoolConfig.defaults()` via the registry
- Assert on the same behavioral outcomes (depletion affects breadth, no accumulation below peak)

- [ ] **Step 5: Fix compilation in any other tests constructing SearchBudgetTickParticipant**

Search for other test files that construct `SearchBudgetTickParticipant` and add the pool parameter (pass `null` for tests that don't test fatigue).

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SearchBudgetTickParticipantTest`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(#880): wire CognitiveResourcePool into SearchBudgetTickParticipant

Replace FatigueState with shared pool reads. Delete FatigueState class.
Search fatigue behavior is equivalent for single-source scenarios.

Refs #880

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Integrate pool into EmotionRegulationTickParticipant and delete RegulationFatigueTracker

**Files:**
- Modify: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipant.java` — inject pool, remove tracker
- Delete: `cognition/src/main/java/io/casehub/neocortex/cognition/regulation/RegulationFatigueTracker.java` (use `ide_refactor_safe_delete`)
- Delete: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/RegulationFatigueTrackerTest.java`
- Modify: `cognition/src/test/java/io/casehub/neocortex/cognition/regulation/EmotionRegulationTickParticipantTest.java` — update fatigue assertions

**Interfaces:**
- Consumes: `CognitiveResourcePool` from Task 2, `CognitiveResourcePoolConfig` from Task 1
- Produces: same `EmotionRegulationResult` output — regulation effort now contributes to shared pool

- [ ] **Step 1: Update EmotionRegulationTickParticipant to accept CognitiveResourcePool**

Add `@Nullable CognitiveResourcePool` parameter to all constructors (there are 4 overloaded constructors — the most complete one gets the field, others pass `null` or chain). Remove `RegulationFatigueTracker` field.

Add field: `private final @Nullable CognitiveResourcePool cognitiveResourcePool;`
Remove field: `private final RegulationFatigueTracker fatigueTracker;`
Remove: `this.fatigueTracker = new RegulationFatigueTracker();` from constructors.

- [ ] **Step 2: Replace tracker calls in tick() method**

Replace:
```java
double alpha = fatigueTracker.effectiveAlpha(context.agentId(), context.tenantId(), DEFAULT_ALPHA);
```
With:
```java
double depletion = cognitiveResourcePool != null
        ? cognitiveResourcePool.currentDepletion(context.agentId(), context.tenantId()) : 0.0;
double alpha = DEFAULT_ALPHA * (1.0 - depletion);
```

Replace:
```java
double currentFatigue = fatigueTracker.currentFatigue(context.agentId(), context.tenantId());
```
With:
```java
double currentFatigue = cognitiveResourcePool != null
        ? cognitiveResourcePool.currentDepletion(context.agentId(), context.tenantId()) : 0.0;
```

Replace:
```java
fatigueTracker.recordRegulation(context.agentId(), context.tenantId(), regulationEffort);
```
With:
```java
if (cognitiveResourcePool != null) {
    cognitiveResourcePool.recordEffort(context.agentId(), context.tenantId(),
            regulationEffort * REGULATION_CONTRIBUTION_RATE);
}
```

Add constant: `static final double REGULATION_CONTRIBUTION_RATE = 0.15;`

Replace:
```java
fatigueTracker.recordRecovery(context.agentId(), context.tenantId());
```
With:
```java
if (cognitiveResourcePool != null) {
    var defaults = defaultsRegistry != null
            ? defaultsRegistry.forAgentOrDefaults(context.agentId()) : null;
    var poolConfig = defaults != null ? defaults.cognitiveResourcePoolConfig() : null;
    if (poolConfig != null) {
        cognitiveResourcePool.recordRecovery(context.agentId(), context.tenantId(),
                poolConfig.recoveryRate());
    }
}
```

- [ ] **Step 3: Delete RegulationFatigueTracker and its test**

Use `ide_refactor_safe_delete` on `RegulationFatigueTracker.java`. Delete `RegulationFatigueTrackerTest.java` manually (test file, no references to check).

- [ ] **Step 4: Update EmotionRegulationTickParticipantTest**

Update tests that asserted on tracker state to instead inject a `DefaultCognitiveResourcePool` and assert on pool depletion or regulation behavior changes. Pass `CognitiveResourcePoolConfig.defaults()` via the registry.

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=EmotionRegulationTickParticipantTest`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(#880): wire CognitiveResourcePool into EmotionRegulationTickParticipant

Replace RegulationFatigueTracker with shared pool reads/writes.
Delete RegulationFatigueTracker class. Regulation effort now
contributes to the shared cognitive depletion pool.

Refs #880

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: CognitiveDerivationEngine split + cross-consumer integration test

**Files:**
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java` — split fatigue derivation into pool config + effects
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngineTest.java` — verify split
- Create: `cognition/src/test/java/io/casehub/neocortex/cognition/core/SharedFatigueIntegrationTest.java` — cross-consumer depletion test

**Interfaces:**
- Consumes: `CognitiveResourcePoolConfig` from Task 1, `SearchFatigueEffects` from Task 1
- Produces: `CognitiveDefaults` with both `cognitiveResourcePoolConfig` and `searchBudgetConfig.fatigueEffects()` derived from personality

- [ ] **Step 1: Split derivation in CognitiveDerivationEngine**

In `deriveSearchBudgetDefaults()` method, split the current fatigue block:

Current (approx lines 818-826):
```java
int    fatigueMaxTicks = (int) (6 + conscientiousness * 8);
double fatigueRecovery = 0.3 + conscientiousness * 0.4;
double fatigueDepth    = Math.min(0.0, -0.08 * (1.0 - conscientiousness));
double fatigueBreadth  = -(0.15 + (1.0 - openness) * 0.15);
double fatigueLat      = -(0.1 + (1.0 - openness) * 0.1) + impulsivity * 0.15;
double fatigueConv     = conscientiousness * 0.2 - anxiousness * 0.15;
var fatigue = new FatigueConfig(fatigueMaxTicks, fatigueRecovery,
                                fatigueDepth, fatigueBreadth, fatigueLat, fatigueConv);
```

Split into:
```java
var poolConfig = new CognitiveResourcePoolConfig(
        (int) (6 + conscientiousness * 8),
        0.3 + conscientiousness * 0.4);
var fatigueEffects = new SearchFatigueEffects(
        Math.min(0.0, -0.08 * (1.0 - conscientiousness)),
        -(0.15 + (1.0 - openness) * 0.15),
        -(0.1 + (1.0 - openness) * 0.1) + impulsivity * 0.15,
        conscientiousness * 0.2 - anxiousness * 0.15);
```

The `poolConfig` is set on the returned `CognitiveDefaults` via `.withCognitiveResourcePoolConfig(poolConfig)`. The `SearchFatigueEffects` goes into `SearchBudgetConfig` via `.withFatigueEffects(fatigueEffects)`.

- [ ] **Step 2: Update CognitiveDerivationEngineTest**

Add test verifying the derivation split produces equivalent values:

```java
@Test
void derivation_produces_pool_config_and_fatigue_effects() {
    var defaults = CognitiveDerivationEngine.derive(testDescriptor);
    assertNotNull(defaults.cognitiveResourcePoolConfig());
    assertTrue(defaults.cognitiveResourcePoolConfig().maxEffort() >= 6);
    assertTrue(defaults.cognitiveResourcePoolConfig().recoveryRate() >= 0.3);
    assertNotNull(defaults.searchBudgetConfig().fatigueEffects());
}
```

- [ ] **Step 3: Run CDE tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDerivationEngineTest`
Expected: PASS

- [ ] **Step 4: Write cross-consumer integration test**

```java
package io.casehub.neocortex.cognition.core;

import io.casehub.neocortex.cognitive.CognitiveResourcePoolConfig;
import io.casehub.neocortex.cognitive.index.CognitiveDefaults;
import io.casehub.neocortex.cognitive.index.CognitiveDefaultsRegistry;
import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.*;

class SharedFatigueIntegrationTest {

    private DefaultCognitiveResourcePool createPool() {
        var config = CognitiveResourcePoolConfig.defaults();
        var registry = new CognitiveDefaultsRegistry() {
            @Override
            public Optional<CognitiveDefaults> forAgent(String agentId) {
                return Optional.of(CognitiveDefaults.empty(agentId)
                        .withCognitiveResourcePoolConfig(config));
            }
            @Override
            public CognitiveDefaults forAgentOrDefaults(String agentId) {
                return forAgent(agentId).orElseThrow();
            }
        };
        return new DefaultCognitiveResourcePool(registry);
    }

    @Test
    void regulation_effort_degrades_search_depletion() {
        var pool = createPool();
        pool.recordEffort("a1", "t1", 0.5 * 0.15);
        pool.recordEffort("a1", "t1", 0.5 * 0.15);
        pool.recordEffort("a1", "t1", 0.5 * 0.15);
        assertTrue(pool.currentDepletion("a1", "t1") > 0.0,
                "Regulation effort should increase shared depletion");
    }

    @Test
    void search_intensity_degrades_regulation_effectiveness() {
        var pool = createPool();
        for (int i = 0; i < 5; i++) {
            pool.recordEffort("a1", "t1", 1.0);
        }
        double depletion = pool.currentDepletion("a1", "t1");
        double effectiveAlpha = 0.8 * (1.0 - depletion);
        assertTrue(effectiveAlpha < 0.8,
                "Search-driven depletion should reduce regulation alpha");
    }

    @Test
    void dual_source_depletes_faster_than_single() {
        var poolSingle = createPool();
        var poolDual = createPool();

        for (int i = 0; i < 3; i++) {
            poolSingle.recordEffort("a1", "t1", 1.0);
            poolDual.recordEffort("a1", "t1", 1.0);
            poolDual.recordEffort("a1", "t1", 0.5 * 0.15);
        }
        assertTrue(poolDual.currentDepletion("a1", "t1")
                > poolSingle.currentDepletion("a1", "t1"));
    }

    @Test
    void recovery_when_both_sources_idle() {
        var pool = createPool();
        pool.recordEffort("a1", "t1", 3.0);
        double peak = pool.currentDepletion("a1", "t1");
        pool.recordRecovery("a1", "t1", 0.5);
        pool.recordRecovery("a1", "t1", 0.5);
        assertTrue(pool.currentDepletion("a1", "t1") < peak);
    }
}
```

- [ ] **Step 5: Run integration test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=SharedFatigueIntegrationTest`
Expected: PASS

- [ ] **Step 6: Full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests=false`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 7: Update CLAUDE.md**

Update the `SearchFatigueEffects` reference in the Key config records line to `SearchFatigueEffects`. Add `CognitiveResourcePoolConfig` to the list. Update the cognition module description to mention `CognitiveResourcePool` SPI and `DefaultCognitiveResourcePool`. Update `CognitiveDefaults` field count from 21 to 22.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "$(cat <<'EOF'
feat(#880): split CDE derivation, add cross-consumer integration tests

CognitiveDerivationEngine now derives CognitiveResourcePoolConfig
separately from SearchFatigueEffects. Integration tests verify
cross-consumer depletion: regulation effort degrades search,
search intensity degrades regulation effectiveness.

Closes #880

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## References

- [2026-11-10-shared-fatigue-substrate-design.md] — design spec this plan implements
- [SearchBudgetTickParticipant.java] — current search fatigue implementation
- [RegulationFatigueTracker.java] — current regulation fatigue (to be deleted)
- [FatigueConfig.java] — current fatigue config (to be renamed)
- [EmotionRegulationTickParticipant.java] — current regulation participant
- [CognitiveDerivationEngine.java:790-840] — current fatigue derivation
- [CognitiveDefaults.java] — cognitive defaults record (21→22 fields)
- [CognitionDefaultBeans.java] — CDI producers
- [SearchBudgetConfig.java] — config record containing fatigue sub-record
- [GitHub #880] — focal issue
- [GitHub #841] — parent epic
