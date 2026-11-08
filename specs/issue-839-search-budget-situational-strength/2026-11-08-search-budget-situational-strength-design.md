# Search Budget: Personality Expression Under Extreme Motivation — Situational Strength Interaction

**Issue:** casehubio/neocortex#839
**Branch:** issue-839-search-budget-situational-strength
**Date:** 2026-11-08
**Depends on:** #825 (Cognitive search budget — foundational model)

## Problem

The search budget model (#825) produces meaningful personality differentiation in the moderate-intensity range (0.3–0.7) but compresses against the ceiling at high intensity (>0.8). At intensity 0.8, `logistic(0.8, 6.0, 0.5) = 0.86` and the fixed additive drive modulations (±0.08 to ±0.15) are proportionally small. Personality character disappears — a bold explorer and a cautious analyst produce nearly identical budgets when motivation is maximal.

The literature predicts three personality-intensity interaction effects absent from the current model:

1. **Trait-specific amplification:** High conscientiousness sustains depth differentiation under pressure (Hockey 1997 primary task protection). High neuroticism amplifies convergence failure (Sarason 1975 worry consumes resources).
2. **Trait-specific compression:** High openness breadth narrows under extreme stress via Easterbrook (1959) cue-utilisation theory. Normal-range personality is genuinely overridden by extreme situational strength (Meyer, Dalal & Hermida 2010).
3. **Personality-dependent fatigue:** Sustained extreme motivation degrades search capacity, but the degradation pattern is personality-specific — conscientiousness protects depth at the cost of breadth (Hockey 1997 compensatory control), neuroticism loses both depth and convergence (Sarason 1975).

## Solution Overview

Three interaction effects applied in sequence after the existing base activation:

1. **Inverted-U decline (Yerkes-Dodson):** Past a personality-specific `extremePeak`, activation declines via exponential decay. The peak position is CDE-derived from anxiousness and emotional lability — neurotic agents peak earlier (0.6–0.7), conscientious agents later (0.9+).

2. **Modulation scaling (Situational Strength):** Drive modulations become intensity-dependent. Past the peak, personality-derived amplification rates make modulations grow (amplification), shrink (compression), or reverse (convergence failure under neuroticism).

3. **Fatigue reallocation (Compensatory Control):** Sustained extreme intensity triggers per-parameter reallocation. Each parameter has a signed fatigue effect: depth is protected for conscientious agents, sacrificed for neurotic; convergence accelerates for conscientious (satisficing), blocks for neurotic (can't commit).

**Processing order in `tick()`:**
1. Base activation with exponential decay — `activationWithDecay()`
2. Scaled drive modulation — `modulation * scalingFactor`
3. Mood / gut adjustments (existing, unchanged)
4. Pathological check (existing, unchanged — convergence floors to 0)
5. Fatigue reallocation — per-parameter signed effects
6. Channel modulation (existing, unchanged)
7. `clamp01()` on all four values

## Activation Function — Exponential Decay Past Peak

Replace the bare logistic with a decay-aware variant:

```java
static double activationWithDecay(double x, double k, double midpoint,
                                   double decay, double peak) {
    double base = logistic(x, k, midpoint);
    double penalty = Math.exp(-decay * Math.max(0.0, x - peak));
    return base * penalty;
}
```

- Below peak: `max(0, x - peak) = 0`, `exp(0) = 1.0` — pure logistic, current behaviour preserved
- At peak: activation equals logistic(peak) — the maximum
- Past peak: exponential decay reduces activation. Rate controlled by `decay` parameter.
- `decay = 0.0`: `exp(0) = 1.0` always — no decline, current flat-ceiling behaviour. Used for parameters that personality protects (e.g. depth for conscientious agents).

Properties of the exponential form:
- Naturally non-negative (multiplicative, not subtractive) — no risk of negative activation
- Asymmetric decline: rapid initial drop past peak, gradual plateau toward zero — more faithful to empirical Yerkes-Dodson curves than symmetric quadratic
- No second-derivative discontinuity at the peak — smooth curvature transition
- Inherits the logistic's (0,1) range without additional clamping

When `ExtremeInteractionConfig` is null, falls back to bare `logistic()` — existing behaviour.

**Caveat:** The Yerkes-Dodson inverted-U is a contested empirical generalisation (Corbett 2015, Teigen 1994). This design uses it as a modelling abstraction — "performance has a personality-specific peak and declines past it" — not as a literal neurophysiological claim. The quality test validates whether the abstraction produces meaningfully different outputs.

## Drive Modulation Scaling

Replace fixed additive modulations with intensity-scaled modulations:

Current: `if (dominant == DriveAxis.CURIOSITY) base += 0.15;`

New:
```java
double scale = 1.0 + amplificationRate * Math.max(0.0, intensity - extremePeak);
scale = Math.max(-1.0, scale);  // clamp reversal
if (dominant == DriveAxis.CURIOSITY) base += 0.15 * scale;
```

At moderate intensity (below peak): `max(0, intensity - peak) = 0`, so `scale = 1.0` — current additive behaviour preserved.

At extreme intensity (above peak): personality-derived `amplificationRate` scales the modulation:
- Positive rate → modulation grows (amplification). Depth for conscientious agents: the +0.15 competence boost becomes +0.20, +0.25.
- Negative rate → modulation shrinks (compression). Breadth for low-openness agents: the +0.15 curiosity boost becomes +0.10, +0.05.
- Rate sufficiently negative → modulation reverses (capped at scale = -1.0). Convergence delay for neurotic agents under extreme anxiety: the -0.10 curiosity delay becomes a +0.10 convergence *acceleration* as anxiety overrides exploratory drive.

Negative scaling factors are intentional for specific trait × parameter combinations. If empirical testing shows unintended reversals, the amplification rate is CDE-derived and can be constrained.

The amplification threshold shares the `extremePeak` from the inverted-U activation. This is an acknowledged simplification — the two phenomena (performance decline onset vs personality expression scaling onset) could theoretically diverge, but the output resolution of LLM prompt rendering doesn't benefit from the distinction. If future validation shows meaningful divergence, an optional `amplificationThreshold` field can be added to `ExtremeInteractionConfig`.

## Fatigue Dynamics — Per-Parameter Strategic Reallocation

Fatigue is modelled as per-parameter strategic reallocation (Hockey 1997 Compensatory Control), not uniform depletion (Baumeister 1998 ego depletion — replication-contested, Carter & McCullough 2014 meta-analysis d=0.25).

### Mechanism

**Accumulation:** Fatigue accumulates when composite intensity exceeds `extremePeak`. Logarithmic temporal accumulation matches the vigilance decrement literature (Warm, Parasuraman & Matthews 2008) — rapid initial onset, plateau:

```java
if (compositeIntensity > config.extremePeak()) {
    ticksAbove++;
} else {
    ticksAbove = Math.max(0, (int)(ticksAbove - config.fatigue().recoveryRate()));
}

double fatigueLevel = Math.min(1.0,
    Math.log(1 + ticksAbove) / Math.log(1 + config.fatigue().maxTicks()));
```

Clamped at 1.0 to prevent unbounded effects when `ticksAbove` exceeds `maxTicks`.

**Recovery:** Gradual, not instantaneous — `ticksAbove` decrements by `recoveryRate` per sub-peak tick. The logarithmic accumulation produces intentional hysteresis: recovery is fast when fatigue is low and extremely slow when fatigue is high. After sustained extreme intensity (`ticksAbove = 100`), reducing by 5 barely moves `fatigueLevel` from 1.0 to ~0.986. This matches Hockey's refractory period — deeply fatigued agents recover slowly.

**Application:** Per-parameter signed effects:

```java
depth      += fatigueLevel * config.fatigue().depthEffect();
breadth    += fatigueLevel * config.fatigue().breadthEffect();
laterality += fatigueLevel * config.fatigue().lateralityEffect();
convergence += fatigueLevel * config.fatigue().convergenceEffect();
```

### Per-Parameter Reallocation Pattern

| Personality trait | Depth | Breadth | Laterality | Convergence | Mechanism |
|---|---|---|---|---|---|
| Conscientious | Protected (≈0) | Sacrificed (−) | Sacrificed (−) | Accelerated (+) | Hockey: primary task protection, satisficing |
| Neurotic | Vulnerable (−) | Rapidly sacrificed (−) | Noise (+) | Blocked (−) | Sarason: worry consumes resources |
| Open | Protected (≈0) | Slowly sacrificed (−) | Slowly sacrificed (−) | Neutral (≈0) | Ego-syntonic exploration costs less |
| Impulsive | Vulnerable (−) | Rapidly sacrificed (−) | Random jumps (+)† | Premature (+) | Executive control degrades first |

† Impulsivity → positive laterality under fatigue is a second-order prediction. Supported by inference (impulsivity = weak executive control; degraded control → random associations) but not directly validated experimentally. Easterbrook would predict narrowing for everyone. Flagged as speculative in quality tests — if empirical testing shows narrowing instead, set to negative.

### Fatigue State Lifecycle

- `FatigueState` record (`int ticksAbove`) stored in `ConcurrentHashMap<String, FatigueState>` on `SearchBudgetTickParticipant` alongside existing `results` map
- Created on first tick where intensity > extremePeak
- Survives across ticks within a session (temporal accumulator)
- Destroyed when agent is deregistered or process restarts — transient per-process state, not persisted
- Full recovery (ticksAbove returns to 0) removes the entry from the map

### Interaction with Pathological Threshold

Pathological threshold is evaluated first — if convergence collapses to 0 via the existing `pathologicalThreshold` check, fatigue effects on convergence are irrelevant (already floored). Fatigue effects apply to the other three parameters normally.

### Independence from RegulationFatigueTracker

Search fatigue and regulation fatigue are independent models for different phenomena. Search fatigue is arousal-driven cognitive narrowing (sustained high motivation degrades exploration capacity). Regulation fatigue is willpower depletion (suppressing emotions costs effort — Bosse et al. 2010). Different mechanisms, different resource pools. An agent can be regulation-fatigued (exhausted from suppressing anger) without being search-fatigued (motivation intensity is moderate). If future work reveals they share a resource pool, a shared substrate can be extracted.

## Config Records

### SearchBudgetConfig

Grows from 11 to 14 top-level fields (1 primitive + 2 nullable sub-records):

```java
public record SearchBudgetConfig(
        double breadthSteepness,
        double breadthMidpoint,
        double lateralitySteepness,
        double lateralityMidpoint,
        double lateralityThreatFloor,
        double depthSteepness,
        double depthMidpoint,
        double convergenceSteepness,
        double convergenceMidpoint,
        double pathologicalThreshold,
        ChannelModulationConfig channelModulation,
        double extremePeak,
        ExtremeInteractionConfig extremeInteraction,
        FatigueConfig fatigue
) {
    public SearchBudgetConfig {
        // existing validation...
        if (extremePeak < 0.0 || extremePeak > 1.0)
            throw new IllegalArgumentException("extremePeak must be in [0,1], got " + extremePeak);
    }

    public static SearchBudgetConfig defaults() {
        return new SearchBudgetConfig(
            6.0, 0.5, 6.0, 0.5, 0.7, 3.0, 0.5, 6.0, 0.5, 1.4,
            null, 0.85, null, null);
    }

    public SearchBudgetConfig withExtremePeak(double peak) { ... }
    public SearchBudgetConfig withExtremeInteraction(ExtremeInteractionConfig config) { ... }
    public SearchBudgetConfig withFatigue(FatigueConfig config) { ... }
}
```

Default `extremePeak = 0.85` — high enough that moderate-range behaviour is unchanged. Null sub-records disable the features — backward compatible.

### ExtremeInteractionConfig

```java
public record ExtremeInteractionConfig(
        double depthDecay,
        double breadthDecay,
        double lateralityDecay,
        double convergenceDecay,
        double depthAmplification,
        double breadthAmplification,
        double lateralityAmplification,
        double convergenceAmplification
) {
    public ExtremeInteractionConfig {
        validateNonNegative("depthDecay", depthDecay);
        validateNonNegative("breadthDecay", breadthDecay);
        validateNonNegative("lateralityDecay", lateralityDecay);
        validateNonNegative("convergenceDecay", convergenceDecay);
    }

    public static ExtremeInteractionConfig defaults() {
        return new ExtremeInteractionConfig(
            0.0, 1.5, 2.0, 0.5,
            0.5, -1.0, -0.8, -1.5);
    }

    public ExtremeInteractionConfig withDepthDecay(double v) { ... }
    public ExtremeInteractionConfig withBreadthDecay(double v) { ... }
    // ... withX() for all 8 fields
}
```

Decay values are non-negative (0 = no decline). Amplification rates are unbounded (positive = amplify, negative = compress/reverse).

### FatigueConfig

```java
public record FatigueConfig(
        int maxTicks,
        double recoveryRate,
        double depthEffect,
        double breadthEffect,
        double lateralityEffect,
        double convergenceEffect
) {
    public FatigueConfig {
        if (maxTicks < 1) throw new IllegalArgumentException("maxTicks must be >= 1, got " + maxTicks);
        if (recoveryRate < 0) throw new IllegalArgumentException("recoveryRate must be >= 0, got " + recoveryRate);
        validateEffect("depthEffect", depthEffect);
        validateEffect("breadthEffect", breadthEffect);
        validateEffect("lateralityEffect", lateralityEffect);
        validateEffect("convergenceEffect", convergenceEffect);
    }

    public static FatigueConfig defaults() {
        return new FatigueConfig(10, 0.5, -0.1, -0.2, -0.15, 0.1);
    }

    private static void validateEffect(String name, double value) {
        if (value < -1.0 || value > 1.0)
            throw new IllegalArgumentException(name + " must be in [-1,1], got " + value);
    }

    public FatigueConfig withMaxTicks(int v) { ... }
    public FatigueConfig withRecoveryRate(double v) { ... }
    // ... withX() for all 6 fields
}
```

### Single Peak Simplification

The `extremePeak` is an agent-level value, not per-parameter. The original Yerkes-Dodson finding was about task complexity — simple tasks peak at higher arousal, complex tasks peak lower. Within the search budget, depth (complex systematic analysis) and breadth (simpler parallel scanning) arguably have different optimal arousal points. A single peak treats them identically.

This is an acknowledged simplification: the LLM prompt rendering resolution doesn't benefit from a 0.1 difference in per-parameter peak position. The per-parameter `decay` values capture most of the task-complexity effect — zero decay on depth for a conscientious agent means depth doesn't decline past peak, regardless of peak position. If future validation shows per-parameter peaks are needed, they can be added to `ExtremeInteractionConfig` without breaking the top-level structure.

## CDE Derivation Pathways

`CognitiveDerivationEngine.deriveSearchBudgetDefaults()` expands with three new derivation blocks. All use the same `conscientiousness` and `openness` composites already computed in the existing method.

### extremePeak

```java
double extremePeak = 0.85 - (anxiousness - 0.5) * 0.3 - (emotionalLability - 0.5) * 0.2;
extremePeak = Math.max(0.5, Math.min(0.95, extremePeak));
```

Range [0.5, 0.95]. Low anxiousness + low lability → 0.93 (tolerates extreme intensity). High anxiousness + high lability → 0.62 (peaks early).

### ExtremeInteractionConfig

| Field | Derivation | Personality logic |
|---|---|---|
| depthDecay | `max(0, (anxiousness - 0.3) * 2.0 - conscientiousness * 1.5)` | Anxiety degrades depth; conscientiousness protects (decay stays 0) |
| breadthDecay | `1.0 + (1.0 - openness) * 2.0` | Low openness → breadth narrows sharply past peak (Easterbrook) |
| lateralityDecay | `1.5 + (1.0 - openness) * 1.5 + impulsivity * 1.0` | Low openness + high impulsivity → laterality narrows fastest |
| convergenceDecay | `max(0, anxiousness * 1.5 - conscientiousness * 1.0)` | Anxiety degrades convergence; conscientiousness protects |
| depthAmplification | `conscientiousness * 1.0 - anxiousness * 0.5` | Conscientious → depth modulations amplify; anxious → compress |
| breadthAmplification | `-(1.0 - openness) * 1.5` | Low openness → breadth modulations compress at extremes |
| lateralityAmplification | `-(1.0 - openness) * 1.2` | Low openness → laterality modulations compress |
| convergenceAmplification | `-(anxiousness * 2.0 - conscientiousness * 0.8)` | Anxious → convergence modulations reverse (convergence failure) |

### FatigueConfig

| Field | Derivation | Personality logic |
|---|---|---|
| maxTicks | `(int)(6 + conscientiousness * 8)` | Range 6–14; conscientious sustains longer |
| recoveryRate | `0.3 + conscientiousness * 0.4` | Range 0.3–0.7; conscientious recovers faster |
| depthEffect | `-(anxiousness * 0.3) + conscientiousness * 0.05` | Neurotic loses depth; conscientious barely affected |
| breadthEffect | `-(0.15 + (1.0 - openness) * 0.15)` | Always negative; low openness sacrifices faster |
| lateralityEffect | `-(0.1 + (1.0 - openness) * 0.1) + impulsivity * 0.15` | Usually negative; impulsivity can flip positive |
| convergenceEffect | `conscientiousness * 0.2 - anxiousness * 0.15` | Positive for conscientious (satisficing); negative for anxious |

### Concrete Example

| | Bold (risk=0.9, anx=0.1, imp=0.7) | Cautious (risk=0.1, anx=0.8, lability=0.7) |
|---|---|---|
| extremePeak | 0.93 | 0.62 |
| depthDecay | 0.0 (protected) | 1.3 (sharp decline) |
| breadthDecay | 1.4 | 2.8 (narrows fast) |
| depthAmplification | 0.55 (amplifies) | -0.15 (compresses) |
| fatigue maxTicks | 12 | 7 |
| fatigue depthEffect | -0.03 (barely affected) | -0.22 (vulnerable) |
| fatigue convergenceEffect | +0.12 (satisficing) | -0.10 (blocked) |

At intensity 0.8: the bold explorer is below their peak (0.93) — full activation, no fatigue. The cautious analyst is past their peak (0.62) — activation declining, fatigue accumulating, breadth narrowing, convergence failing.

## Prose Generation

`SearchBudgetDescriptionGenerationPhase` gains a new section in its LLM prompt describing the agent's extreme-intensity personality:

```
Describe how this agent's search behaviour changes under extreme motivation:
- Extreme peak tolerance: {extremePeak} (how much pressure before performance declines)
- Under sustained extreme intensity, what degrades first and what holds?
- Does pressure sharpen their focus or scatter it?
```

The LLM generates personality-specific prose. Examples:
- Bold explorer: *"Pressure sharpens you. When motivation peaks, your focus narrows to the essential threads and holds there. Fatigue, when it comes, takes breadth first — you stop scanning for alternatives and commit to the line you're on."*
- Cautious analyst: *"High pressure overwhelms your capacity to sustain multiple threads. Anxiety pulls you back to re-examine what you've already covered rather than pushing forward. Your convergence stutters — you know you should synthesise, but the uncertainty prevents commitment."*

The `SearchBudgetPromptSection` at tick time selects the extreme-intensity prose when intensity > extremePeak.

## Quality Tests

### SearchBudgetExtremeInteractionTest (cognitive-index)

```java
@Test
void personality_differentiation_maintained_at_extreme_intensity() {
    // Grid: 4 personality profiles × 5 intensity levels (0.3, 0.5, 0.7, 0.85, 0.95)
    // For each pair of profiles at each intensity, compute budget difference
    // Assert: at intensity 0.85+, differentiation >= at intensity 0.5
}

@Test
void inverted_u_activates_past_personality_peak() {
    // neurotic profile (peak ~0.62): activation at 0.8 < activation at 0.6
    // conscientious profile (peak ~0.93): activation at 0.8 ≈ activation at 0.7
}

@Test
void fatigue_reallocation_matches_hockey_predictions() {
    // After N ticks above peak:
    // conscientious: depth stable, breadth decreased, convergence increased
    // neurotic: depth decreased, convergence decreased (blocked)
}

@Test
void fatigue_recovery_is_gradual_not_instantaneous() {
    // After sustained extreme intensity, drop below peak
    // fatigueLevel decreases but doesn't reset to 0
}

@Test
void impulsivity_laterality_under_fatigue_flagged_speculative() {
    // Validate direction of impulsive laterality effect
    // Document as speculative per R1-11
}
```

### CognitionTestHarness scenario (cognition)

Full-pipeline scenario with different personality profiles at extreme intensity. Assert prompt section renders meaningfully different prose — following the #849 S1 personality differentiation pattern.

## Module Placement

| Component | Module | Rationale |
|---|---|---|
| `ExtremeInteractionConfig` | cognitive-api | Per-agent config, alongside SearchBudgetConfig |
| `FatigueConfig` | cognitive-api | Per-agent config, alongside SearchBudgetConfig |
| `SearchBudgetConfig` changes | cognitive-api | Existing location |
| `activationWithDecay()` | cognition (TickParticipant) | Tick-time computation |
| `FatigueState` | cognition (TickParticipant) | Per-process transient state |
| CDE derivation pathways | cognitive-index (CDE) | Alongside existing 14 pathways |
| Prose generation updates | mindmap-intelligence | Existing SearchBudgetDescriptionGenerationPhase |
| Quality tests | cognitive-index (test) | Alongside existing SearchBudgetQualityTest |
| Scenario test | cognition (test) | CognitionTestHarness pattern |

## References

- `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java` — current activation functions and drive modulations
- `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/SearchBudgetConfig.java` — current config record
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java:646` — current CDE derivation
- `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/SearchBudgetQualityTest.java` — existing quality tests
- `cognition/src/test/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipantTest.java` — existing unit tests
- `docs/specs/issue-765-cognitive-richness/2026-11-05-cognitive-search-budget-design.md` — original search budget design
- Meyer, R.D., Dalal, R.S. & Hermida, R. (2010). A review and synthesis of situational strength in the organizational sciences. *Journal of Management*, 36(1), 121-140.
- Yerkes, R.M. & Dodson, J.D. (1908). The relation of strength of stimulus to rapidity of habit-formation. *Journal of Comparative Neurology and Psychology*, 18, 459-482.
- Eysenck, H.J. & Eysenck, M.W. (1985). *Personality and Individual Differences*. Plenum Press.
- Easterbrook, J.A. (1959). The effect of emotion on cue utilization and the organization of behavior. *Psychological Review*, 66(3), 183-201.
- Hockey, G.R.J. (1997). Compensatory control in the regulation of human performance under stress and high workload. *Biological Psychology*, 45, 73-93.
- Warm, J.S., Parasuraman, R. & Matthews, G. (2008). Vigilance requires hard mental work and is stressful. *Human Factors*, 50(3), 433-441.
- Sarason, I.G. (1975). Anxiety and self-preoccupation. In I.G. Sarason & C.D. Spielberger (Eds.), *Stress and Anxiety* (Vol. 2). Hemisphere.
- Mischel, W. & Shoda, Y. (1995). A cognitive-affective system theory of personality. *Psychological Review*, 102(4), 246-268.
- Carter, E.C. & McCullough, M.E. (2014). Publication bias and the limited strength model of self-control. *Frontiers in Psychology*, 5, 823.
- Corbett, M. (2015). From law to folklore: work stress and the Yerkes-Dodson Law. *Journal of Managerial Psychology*, 30(6), 741-752.
- Teigen, K.H. (1994). Yerkes-Dodson: A law for all seasons. *Theory & Psychology*, 4(4), 525-547.
- Bosse, T. et al. (2010). A BDI-based model of emotion regulation using exhaustion. *Cognitive Systems Research*, 11(3), 289-302.
- Dalal, R.S., Meyer, R.D. et al. (2015). Personality strength and situational influences on behavior. *Journal of Management*, 41(1), 261-287.
- Kahneman, D. (2011). *Thinking, Fast and Slow*. Farrar, Straus and Giroux.
