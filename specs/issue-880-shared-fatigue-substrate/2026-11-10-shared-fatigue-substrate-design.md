# Shared Fatigue Substrate — Design Spec

**Issue:** casehubio/neocortex#880
**Epic:** casehubio/neocortex#841
**Date:** 2026-11-10

## Motivation

Search fatigue (Hockey 1997 compensatory control) and emotion regulation fatigue (Bosse et al. 2010 willpower depletion) are currently independent systems with separate resource pools. This contradicts Hockey's own theory — compensatory control models effortful cognitive activity competing for limited processing capacity, with strategic reallocation under load. An agent exhausted from emotion regulation should show degraded exploration capacity, and vice versa.

The original design (#839) deferred unification: "If future work reveals they share a resource pool, a shared substrate can be extracted." First-principles analysis confirms the theoretical case:

1. Hockey's compensatory control explicitly models a unified processing resource with strategic reallocation across all cognitive tasks.
2. Emotion regulation strategies (Gross 2015) compete for the same executive function and working memory resources that exploration uses.
3. Independent pools produce implausible behavior: a regulation-exhausted agent exploring at full capacity, or a search-exhausted agent regulating emotions perfectly.

## Architecture

### CognitiveResourcePool SPI (`cognition-api`)

A shared per-agent cognitive resource pool that any effortful subsystem can contribute to and read from.

```java
public interface CognitiveResourcePool {
    void recordEffort(String agentId, String tenantId, double amount);
    void recordRecovery(String agentId, String tenantId, double recoveryRate);
    double currentDepletion(String agentId, String tenantId);
}
```

- `recordEffort`: sources call during their tick when active. Amount is source-specific — search passes 1.0 per extreme-intensity tick, regulation passes `regulationEffort * contributionRate`.
- `recordRecovery`: sources call during their tick when idle. Decrements the accumulator by `recoveryRate`. Only reduces — never increases.
- `currentDepletion`: returns `log(1 + accumulator) / log(1 + maxEffort)`, range [0, 1]. Consumers read this and apply their own effects.

### CognitiveResourcePoolConfig (`cognitive-api`)

```java
public record CognitiveResourcePoolConfig(
    int maxEffort,
    double recoveryRate
) {
    public static CognitiveResourcePoolConfig defaults() {
        return new CognitiveResourcePoolConfig(10, 0.5);
    }
}
```

- `maxEffort`: effort units for full depletion (logarithmic scale). Personality-derived: `6 + conscientiousness * 8`.
- `recoveryRate`: accumulator decrement per idle-source recovery call. Personality-derived: `0.3 + conscientiousness * 0.4`.

Top-level field on `CognitiveDefaults` (field #22). Derived in `CognitiveDerivationEngine` from the same personality facets currently used for fatigue parameters.

### DefaultCognitiveResourcePool (`cognition`)

Implementation: `ConcurrentHashMap<String, Double>` keyed by `agentId:tenantId`. `@DefaultBean @ApplicationScoped`.

```
recordEffort(agentId, tenantId, amount):
  accumulator = map.merge(key, amount, (old, inc) -> old + inc)

recordRecovery(agentId, tenantId, recoveryRate):
  map.computeIfPresent(key, (k, v) ->
      v - recoveryRate <= 0 ? null : v - recoveryRate)

currentDepletion(agentId, tenantId):
  acc = map.getOrDefault(key, 0.0)
  return log(1 + acc) / log(1 + config.maxEffort())
```

The pool needs access to `CognitiveResourcePoolConfig` per agent. It reads from `CognitiveDefaultsRegistry` — same pattern as `SearchBudgetTickParticipant` reads `SearchBudgetConfig`.

### Net-Contribution Recovery Model

Each tick, each source independently calls either `recordEffort` (when active) or `recordRecovery` (when idle). The pool accumulator nets these:
- If search contributes 1.0 and regulation recovers 0.3, net change is +0.7.
- If both are idle, both call `recordRecovery`, net change is -0.6 (from two recovery calls).
- If both are active, both call `recordEffort`, accumulator grows from both sources.

This means a single high-intensity source CAN prevent net recovery. An agent under sustained extreme motivation won't recover regulation fatigue — which is the desired behavior (sustained cognitive load degrades all effortful processing).

## Source Integration

### Search Budget (`SearchBudgetTickParticipant`)

**Remove:**
- `FatigueState` class (deleted)
- `fatigueStates` ConcurrentHashMap field

**Add:**
- `CognitiveResourcePool` injection (nullable, graceful degradation)

**Tick logic change:**

Current:
```java
if (compositeIntensity > config.extremePeak()) {
    accumulator += 1.0;
} else {
    accumulator = max(0, accumulator - fatigueConfig.recoveryRate());
}
fatigueLevel = log(1 + accumulator) / log(1 + fatigueConfig.maxTicks());
```

New:
```java
if (pool != null) {
    var poolConfig = defaults.cognitiveResourcePoolConfig();
    if (compositeIntensity > config.extremePeak()) {
        pool.recordEffort(agentId, tenantId, 1.0);
    } else if (poolConfig != null) {
        pool.recordRecovery(agentId, tenantId, poolConfig.recoveryRate());
    }
    double depletion = pool.currentDepletion(agentId, tenantId);
    // apply per-parameter effects using depletion instead of fatigueLevel
}
```

The 4 per-parameter effects (depth, breadth, laterality, convergence) are applied identically — only the source of the depletion level changes.

### Emotion Regulation (`EmotionRegulationTickParticipant`)

**Remove:**
- `RegulationFatigueTracker` field and instantiation (class deleted)
- Direct fatigue tracking in `tick()`

**Add:**
- `CognitiveResourcePool` injection (nullable, graceful degradation)

**Tick logic change:**

Current:
```java
double alpha = fatigueTracker.effectiveAlpha(agentId, tenantId, DEFAULT_ALPHA);
// ... later ...
fatigueTracker.recordRegulation(agentId, tenantId, regulationEffort);
// or
fatigueTracker.recordRecovery(agentId, tenantId);
```

New:
```java
double depletion = pool != null ? pool.currentDepletion(agentId, tenantId) : 0.0;
double alpha = DEFAULT_ALPHA * (1.0 - depletion);
// ... later ...
if (pool != null) {
    pool.recordEffort(agentId, tenantId, regulationEffort * REGULATION_CONTRIBUTION_RATE);
} // else no-op — pool null means no fatigue tracking
// or when idle:
if (pool != null) {
    var poolConfig = defaults.cognitiveResourcePoolConfig();
    if (poolConfig != null) pool.recordRecovery(agentId, tenantId, poolConfig.recoveryRate());
}
```

`REGULATION_CONTRIBUTION_RATE` replaces `FATIGUE_RATE` (0.15). Same value, different constant name for clarity.

`isExhausted()` calls on the tracker become `pool.currentDepletion() >= 1.0` (practically unreachable under log scaling, but the semantics are preserved).

## Type Changes

### SearchFatigueEffects (renamed from FatigueConfig)

```java
public record SearchFatigueEffects(
    double depthEffect,
    double breadthEffect,
    double lateralityEffect,
    double convergenceEffect
) { ... }
```

- `maxTicks` and `recoveryRate` removed (moved to `CognitiveResourcePoolConfig`)
- `defaults()` factory updated
- `withMaxTicks()` and `withRecoveryRate()` wither methods removed
- `SearchBudgetConfig.fatigue()` renamed to `SearchBudgetConfig.fatigueEffects()`, returns `SearchFatigueEffects`

### RegulationFatigueTracker — Deleted

All responsibilities absorbed by `CognitiveResourcePool`:
- `recordRegulation()` → `pool.recordEffort()`
- `recordRecovery()` → `pool.recordRecovery()`
- `effectiveAlpha()` → inline: `DEFAULT_ALPHA * (1 - pool.currentDepletion())`
- `currentFatigue()` → `pool.currentDepletion()`
- `isExhausted()` → `pool.currentDepletion() >= 1.0`

### CognitiveDefaults — New Field

Add `CognitiveResourcePoolConfig cognitiveResourcePoolConfig` as field #22. Nullable (graceful degradation). `withCognitiveResourcePoolConfig()` wither method. `CognitiveDefaults.empty()` passes `null`.

### CognitiveDerivationEngine — Derivation Split

Current fatigue derivation block produces `FatigueConfig(maxTicks, recovery, depth, breadth, lat, conv)`.

Split into:
1. `CognitiveResourcePoolConfig(maxEffort, recoveryRate)` — using same formulas: `maxEffort = 6 + conscientiousness * 8`, `recoveryRate = 0.3 + conscientiousness * 0.4`
2. `SearchFatigueEffects(depthEffect, breadthEffect, lateralityEffect, convergenceEffect)` — using same effect derivation formulas

Both assigned to `CognitiveDefaults` — pool config as top-level field, fatigue effects nested in `SearchBudgetConfig`.

### CognitionDefaultBeans

Add `@DefaultBean @Singleton` producer for `CognitiveResourcePool` returning `DefaultCognitiveResourcePool`.

## Cross-Consumer Interaction Scenarios

The shared pool introduces cross-system effects that are theoretically desirable but require awareness:

1. **Search intensity degrades regulation.** Sustained extreme motivation (compositeIntensity > extremePeak for many ticks) accumulates pool depletion. Regulation effectiveness (alpha) decreases. An agent under sustained cognitive pressure becomes worse at emotion regulation — consistent with the observation that cognitive load impairs self-regulation.

2. **Regulation effort degrades exploration.** Active emotion suppression contributes to pool depletion. Search budget parameters degrade via per-parameter effects. An agent spending cognitive resources on emotion regulation has fewer resources for exploration — consistent with Gross's process model.

3. **Regulation self-limiting loop changes.** Previously: regulation → fatigue → reduced alpha → less regulation → recovery. Now: regulation → shared depletion → reduced alpha → less regulation, BUT search intensity can maintain depletion even when regulation stops. Recovery requires ALL sources to be idle or at least contributing less than the net recovery rate.

4. **Recurring thought interaction preserved.** Sustained fixation/rumination maintains compositeIntensity above extremePeak, accumulating pool depletion. This now also degrades regulation — a fixated agent becomes less able to regulate the emotions driving the fixation. This positive feedback loop is psychologically accurate.

## Tick Ordering

Both `SearchBudgetTickParticipant` and `EmotionRegulationTickParticipant` execute in `CognitionPhase.DERIVED`. Within a phase, execution order depends on registration order in `CognitionCore`. The first participant to run sees previous-tick pool state + its own contribution; the second sees previous-tick state + both contributions.

The ordering delta is one tick's worth of effort — negligible in practice. No ordering constraint is imposed. If ordering becomes significant in future, a two-phase approach (all contributions first, then all reads) can be added without SPI changes.

## Testing

- `DefaultCognitiveResourcePoolTest`: unit tests for accumulation, recovery, depletion calculation, concurrent access
- `SearchBudgetTickParticipantTest`: update existing fatigue tests to inject pool instead of asserting internal FatigueState
- `EmotionRegulationTickParticipantTest`: update to inject pool instead of asserting RegulationFatigueTracker state
- `RegulationFatigueTrackerTest`: delete (class deleted)
- New integration test: cross-consumer depletion — regulation effort degrades search budget, search intensity degrades regulation alpha
- `CognitiveDerivationEngineTest`: verify derivation split produces equivalent pool config + fatigue effects
- `SearchFatigueEffectsTest`: rename to `SearchFatigueEffectsTest`, update for 4-field record

## References

- Hockey, G.R.J. (1997). Compensatory control in the regulation of human performance under stress and high workload
- Bosse, T. et al. (2010). A computational model based on Gross' emotion regulation theory
- Gross, J.J. (2015). The extended process model of emotion regulation
- Kahneman, D. (1973). Attention and effort (capacity theory)
- `SearchBudgetTickParticipant.java` — current search fatigue implementation
- `RegulationFatigueTracker.java` — current regulation fatigue implementation
- `FatigueConfig.java` — current fatigue config record
- `EmotionRegulationTickParticipant.java` — current regulation participant
- `CognitiveDerivationEngine.java:790-840` — current fatigue derivation
- `CognitiveDefaults.java` — cognitive defaults record (21 current fields)
- `docs/specs/issue-839-search-budget-situational-strength/2026-11-08-search-budget-situational-strength-design.md:159-165` — original independence decision
- Decision review R1-01 through R1-10 — adversarial validation of decisions
