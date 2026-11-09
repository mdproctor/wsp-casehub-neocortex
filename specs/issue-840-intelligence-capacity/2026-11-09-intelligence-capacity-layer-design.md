# Intelligence Capacity Layer: Cognitive Capacity as Ceiling for Search Budget Parameters

**Issue:** casehubio/neocortex#840
**Branch:** issue-802-hortora-corpus-extraction
**Date:** 2026-11-09
**Depends on:** #825 (Cognitive search budget — foundational model, complete), #839 (Personality at extreme intensity — situational strength, complete)

## Problem

The search budget (#825) models how personality shapes the *distribution* of cognitive effort — where an agent allocates exploration across four parameters (depth, breadth, laterality, convergence). The extreme interaction layer (#839) models how personality expression changes under high motivation. Neither models *capacity* — how far that effort can productively reach.

DeYoung's Big Five Aspect Scales split Openness/Intellect into two empirically distinct aspects. Nusbaum & Silvia (2011) demonstrated the double dissociation: Openness predicts creativity but not fluid intelligence; Intellect predicts fluid intelligence but not creativity. DeYoung (2014) confirmed Intellect independently associates with general intelligence (g).

The current model captures Openness (motivation to explore) through PID-5 facets. It has no representation for Intellect (capacity to reason abstractly), because:

1. **PID-5 cannot source it.** PID-5 measures maladaptive personality pathology. DeYoung et al. (2016) showed PID-5's Psychoticism facets map to the Openness aspect specifically, while Intellect — a positive trait — has no PID-5 counterpart.
2. **Jungian functions cannot source it.** Ti/Te/Ni describe cognitive *style* (how you prefer to process), not cognitive *ability* (how much you can process). Conflating them is circular.
3. **Disposition axes cannot source it.** ruleFollowing, riskAppetite, autonomy are motivational constructs with no literature support as capacity proxies.

Consequence: a high-Openness, low-Intellect agent wants to explore laterally but can't chain distant associations productively. A high-Intellect, low-Openness agent can chain deep but doesn't pursue the connections. The current model cannot represent either.

## Solution Overview

Three capacity dimensions, each grounded in specific literature, bound three of the four search budget parameters as hard ceilings:

| Capacity dimension | What it bounds | Search parameter | Literature |
|---|---|---|---|
| **Relational complexity** | How many reasoning hops can be held simultaneously | Depth ceiling | Halford et al. (1998) — quaternary relation soft limit; Gf accounts for 80% of age-related variance |
| **Associative reach** | How far associations can bridge between distant concepts | Laterality ceiling | Mednick (1962) — flat vs steep associative hierarchies; RAT × Raven's r=0.38 |
| **Working memory span** | How many threads can be tracked simultaneously | Breadth ceiling | Engle & Kane (2004) — WMC as attention control; latent Gf correlation r≈0.72 |

Convergence receives no ceiling — it models *when to stop and synthesize*, which is personality-driven (Need for Cognitive Closure, conscientiousness), not capacity-limited.

**Processing order in `tick()`:**

Steps 1-6 are unchanged from #839. Step 7 is new:

1. Base logistic activation — `activationWithDecay()`
2. Scaled drive modulation — `modulation * scalingFactor`
3. Mood / gut adjustments
4. Pathological check (convergence floors to 0)
5. Channel modulation
6. Fatigue reallocation (per-parameter signed effects)
7. **Capacity ceiling** — `Math.min(ceiling, raw)` for depth, breadth, laterality (NEW)
8. `clamp01()` on all four values

Capacity and fatigue are independent (D5). Fatigue modifies raw values, capacity caps the result. The #839 spec explicitly anticipated this architecture.

## CognitiveCapacityConfig Record

```java
public record CognitiveCapacityConfig(
        double relationalComplexity,
        double associativeReach,
        double workingMemorySpan
) {
    public CognitiveCapacityConfig {
        validate("relationalComplexity", relationalComplexity);
        validate("associativeReach", associativeReach);
        validate("workingMemorySpan", workingMemorySpan);
    }

    public static CognitiveCapacityConfig defaults() {
        return new CognitiveCapacityConfig(0.75, 0.75, 0.75);
    }

    private static void validate(String name, double value) {
        if (value < 0.0 || value > 1.0)
            throw new IllegalArgumentException(name + " must be in [0,1], got " + value);
    }

    public CognitiveCapacityConfig withRelationalComplexity(double v) {
        return new CognitiveCapacityConfig(v, associativeReach, workingMemorySpan);
    }

    public CognitiveCapacityConfig withAssociativeReach(double v) {
        return new CognitiveCapacityConfig(relationalComplexity, v, workingMemorySpan);
    }

    public CognitiveCapacityConfig withWorkingMemorySpan(double v) {
        return new CognitiveCapacityConfig(relationalComplexity, associativeReach, v);
    }
}
```

All values in [0,1]: 1.0 = uncapped (maximally capable), 0.0 = fully constrained. Population-mean default 0.75.

### Scale Semantics

| Value | Meaning | Halford equivalent | Mednick equivalent | Engle equivalent |
|---|---|---|---|---|
| 1.0 | Uncapped — no capacity constraint | Beyond quaternary | Perfectly flat hierarchy | Unlimited attention control |
| 0.85-0.95 | High capacity | Quaternary relations fluid | Flat hierarchy, remote access easy | High WMC, interference-resistant |
| 0.65-0.85 | Moderate capacity | Ternary relations comfortable | Moderate hierarchy, some remote access | Average WMC |
| 0.45-0.65 | Below-average capacity | Binary relations primary | Steep hierarchy, dominant associations | Low WMC, interference-prone |
| < 0.45 | Low capacity | Unary primarily | Very steep, conventional only | Very limited parallel tracking |

### Placement on CognitiveDefaults

`CognitiveCapacityConfig` is a top-level nullable field on `CognitiveDefaults` (field 21), alongside `searchBudgetConfig`, `moodBaseline`, etc. Not nested inside `SearchBudgetConfig`.

```java
public record CognitiveDefaults(
        String agentId,
        String tenantId,
        PersonalityProfile personalityProfile,
        MoodBaseline moodBaseline,
        CuriosityConfig curiosity,
        TemporalFocusConfig temporalFocus,
        CbrStrategyDefaults cbrStrategy,
        SocialCognitionDefaults socialCognition,
        GraphStructureDefaults graphStructure,
        ExtractionBiasDefaults extractionBias,
        MindMapVocabulary vocabulary,
        Map<String, String> services,
        List<DeclarativeTraitRule> traitRules,
        List<DeclarativeDerivedEdgeRule> derivedEdgeRules,
        DescriptorView descriptor,
        AppraisalWeights appraisalWeights,
        HabituationConfig habituationConfig,
        RegulationDefaults regulationDefaults,
        SearchBudgetConfig searchBudgetConfig,
        RecurringThoughtConfig recurringThoughtConfig,
        CognitiveCapacityConfig capacityConfig          // NEW — field 21
) { ... }
```

Top-level placement enables future access from the memory subsystem for Cattell's Investment Theory learning rate modulation, without reaching through SearchBudgetConfig.

When null, capacity ceilings are disabled — existing behaviour preserved. The tick participant checks `capacityConfig != null` before applying ceilings.

## CDE Derivation

Extends `CognitiveDerivationEngine.deriveSearchBudgetDefaults()` with a capacity derivation block. When the cognitive profile YAML specifies explicit capacity values, the CDE's `deriveAndMerge()` overlays the explicit values on the derived base — explicit specification always wins.

### Jungian → Capacity Mapping

The derivation uses Jungian cognitive functions as weak proxies, with a compressed range of [0.55, 0.95] that acknowledges the low correlation (r ≈ 0.3-0.4):

```java
static CognitiveCapacityConfig deriveCapacity(DescriptorView view) {
    Map<String, Double> profile = toWeightMap(view.dispositionProfile());

    double ti = profile.getOrDefault("ti", 0.0);
    double te = profile.getOrDefault("te", 0.0);
    double ne = profile.getOrDefault("ne", 0.0);
    double ni = profile.getOrDefault("ni", 0.0);
    double si = profile.getOrDefault("si", 0.0);

    double relational = compress(0.5 * (ti + te));
    double associative = compress(0.5 * (ne + ni));
    double wmSpan = compress(0.5 * (te + si));

    return new CognitiveCapacityConfig(relational, associative, wmSpan);
}

private static double compress(double raw) {
    // Map [0, 1] → [0.55, 0.95]
    return 0.55 + raw * 0.4;
}
```

| Capacity dimension | Jungian proxy | Literature rationale |
|---|---|---|
| Relational complexity | Ti + Te | Analytical functions. Ti (internal logical chains) and Te (systematic external reasoning) weakly correlate with relational reasoning capacity. |
| Associative reach | Ne + Ni | Intuitive functions. Ne (divergent association) and Ni (convergent pattern bridging) weakly correlate with associative hierarchy flatness. |
| Working memory span | Te + Si | Structured processing. Te (organized parallel tracking) and Si (sequential detail maintenance) weakly correlate with working memory capacity. |

**Compressed range [0.55, 0.95]:** The derivation cannot produce extreme low values because "this personality profile makes you unintelligent" is an inference the Jungian-Gf correlation doesn't support. The compressed range limits the derivation's influence to moderate differentiation while allowing explicit YAML specification to produce the full [0, 1] range.

**Calibration note:** The Jungian → capacity mapping is the weakest link in this design. The direction (analytical functions correlate with reasoning capacity) is literature-supported but the specific formula (`0.5 * (ti + te)`) is a modelling choice, not an empirical finding. Quality tests validate that the derivation produces meaningful differentiation without pathological values.

### Concrete Examples

Using existing agent profiles:

**High-Ti/Te agent** (e.g., INTJ disposition — ni=0.9, te=0.85, fi=0.7, se=0.15):
- Relational complexity: compress(0.5 * (0.0 + 0.85)) = compress(0.425) = 0.72
- Associative reach: compress(0.5 * (0.0 + 0.9)) = compress(0.45) = 0.73
- WM span: compress(0.5 * (0.85 + 0.0)) = compress(0.425) = 0.72

Wait — ti is not in this profile. Let me use proper Jungian profiles:

**Analytical disposition** (ti=0.8, te=0.7, ni=0.6, ne=0.3, si=0.5):
- Relational: compress(0.5 * (0.8 + 0.7)) = compress(0.75) = 0.85
- Associative: compress(0.5 * (0.3 + 0.6)) = compress(0.45) = 0.73
- WM span: compress(0.5 * (0.7 + 0.5)) = compress(0.60) = 0.79

**Exploratory disposition** (ne=0.9, fi=0.7, ni=0.5, te=0.2, si=0.3, ti=0.2):
- Relational: compress(0.5 * (0.2 + 0.2)) = compress(0.20) = 0.63
- Associative: compress(0.5 * (0.9 + 0.5)) = compress(0.70) = 0.83
- WM span: compress(0.5 * (0.2 + 0.3)) = compress(0.25) = 0.65

The analytical agent has higher depth ceiling (0.85 vs 0.63) and higher WM span (0.79 vs 0.65). The exploratory agent has higher associative reach (0.83 vs 0.73). This differentiation is directionally correct and magnitude-moderate — exactly the intent.

## Pipeline Integration — SearchBudgetTickParticipant

### Ceiling Application

After fatigue reallocation (step 6, existing), before clamp (step 8):

```java
// Step 7: Capacity ceiling (NEW)
CognitiveCapacityConfig capacity = defaults.capacityConfig();
if (capacity != null) {
    depth = Math.min(capacity.relationalComplexity(), depth);
    breadth = Math.min(capacity.workingMemorySpan(), breadth);
    laterality = Math.min(capacity.associativeReach(), laterality);
    // convergence: no ceiling
}

// Step 8: Final clamp
depth = clamp01(depth);
breadth = clamp01(breadth);
laterality = clamp01(laterality);
convergence = clamp01(convergence);
```

### Capacity Gap Signal

The tick participant computes the gap between unconstrained and constrained values BEFORE applying the ceiling:

```java
boolean capacityConstrained = false;
if (capacity != null) {
    double unclampedDepth = depth;
    double unclampedBreadth = breadth;
    double unclampedLaterality = laterality;

    depth = Math.min(capacity.relationalComplexity(), depth);
    breadth = Math.min(capacity.workingMemorySpan(), breadth);
    laterality = Math.min(capacity.associativeReach(), laterality);

    double maxGap = Math.max(
        unclampedDepth - depth,
        Math.max(unclampedBreadth - breadth, unclampedLaterality - laterality));
    capacityConstrained = maxGap > 0.05;
}
```

The `capacityConstrained` flag is true when any parameter is materially capped (gap > 0.05 threshold to filter noise). The 0.05 threshold avoids triggering capacity-constrained prose for negligible ceiling effects — the LLM wouldn't render a 0.02 gap differently from zero.

### SearchBudget Record

Grows from 7 to 8 fields:

```java
public record SearchBudget(
        double breadth,
        double laterality,
        double depth,
        double convergence,
        SearchMotivation source,
        boolean extremeActivation,
        boolean capacityConstrained,    // NEW — field 8
        Instant evaluatedAt
) { ... }
```

## Prose Generation

### SearchBudgetDescriptionGenerationPhase

Extends the LLM prompt to generate three descriptions when capacity config is present. When capacity is null (or all ceilings ≥ 0.95), falls back to existing two-description format.

**New system prompt variant** (`SYSTEM_PROMPT_WITH_CAPACITY`):

```
Describe this agent's cognitive search disposition. Provide three descriptions:

1. **Normal range** — how they naturally explore under moderate motivation.
   Given parameters: breadth steepness={breadthSteepness}, midpoint={breadthMidpoint}, ...

2. **Extreme intensity** — how their exploration changes under extreme motivation
   pressure (past their tolerance peak of {extremePeak}).

3. **Capacity constrained** — what happens when their motivation pushes them
   past their cognitive capacity limits.
   - Depth capacity: {relationalComplexity} (relational reasoning ceiling)
   - Breadth capacity: {workingMemorySpan} (working memory span ceiling)
   - Laterality capacity: {associativeReach} (associative reach ceiling)
   - Where specifically does their reach exceed their grasp?
   - What does it feel like to want more cognitive reach than you have?

Write 2-3 sentences each, second person ("you"). Describe felt cognitive state,
not parameters.

Respond with JSON: {"normal": "...", "extreme": "...", "constrained": "..."}
```

Selection:
- `anyExtreme && capacity != null` → `SYSTEM_PROMPT_WITH_CAPACITY`
- `anyExtreme && capacity == null` → `SYSTEM_PROMPT_WITH_EXTREME` (existing)
- `!anyExtreme` → `SYSTEM_PROMPT` (existing)

All descriptions crystallise to the same MindMap COGNITIVE node: `description` (backward-compatible), `extreme-description` (#839), `constrained-description` (new).

### Tick-Time Prose Selection

`SearchBudgetPromptSection` selects prose based on the SearchBudget flags:

```java
String crystallised;
if (budget.capacityConstrained()) {
    crystallised = readProperty(agentId, tenantId, "constrained-description");
} else if (budget.extremeActivation()) {
    crystallised = readProperty(agentId, tenantId, "extreme-description");
} else {
    crystallised = readProperty(agentId, tenantId, "description");
}
```

Priority: `capacityConstrained` > `extremeActivation` > normal. An agent can be both capacity-constrained and at extreme intensity — capacity is the more specific condition.

### Example Prose

**Analytical disposition** (high relational, moderate WM span, moderate associative):
- Normal: *"You trace each thread methodically before moving to the next. Conclusions form from accumulated evidence, not flashes of insight."*
- Extreme: *"Pressure sharpens your focus. Under high motivation, you narrow to the strongest thread and follow it relentlessly."*
- Constrained: *"You can feel where your reasoning chain reaches its limit — three, four steps deep and the earlier links start to blur. You want to hold more of the argument in view at once, but the threads slip. Lateral leaps occasionally connect but more often land in noise."*

**Exploratory disposition** (low relational, high associative, low WM span):
- Constrained: *"Your mind reaches easily for distant connections — a metaphor here, an analogy there. But when you try to sustain multiple lines of inquiry, the earlier ones dissolve. Deep, systematic chains are effortful. You build understanding through flashes and bridges, not through sustained reasoning."*

## Cognitive Profile YAML

Explicit capacity specification in cognitive profiles:

```yaml
agentId: analyst-01
# ... existing personality, mood, etc. ...
capacityConfig:
  relationalComplexity: 0.90
  associativeReach: 0.70
  workingMemorySpan: 0.85
```

When `capacityConfig` is present in YAML, the CDE's `deriveAndMerge()` overlays explicit values on Jungian-derived defaults. Partially specified capacity (e.g., only `relationalComplexity`) fills missing fields from the derivation — standard `deriveAndMerge` semantics.

When `capacityConfig` is absent from YAML, the CDE derives all three values from the Jungian profile with compressed range.

## Quality Tests

### SearchBudgetCapacityTest (cognitive-index)

```java
@Test
void capacity_ceiling_bounds_parameter() {
    // capacity.relationalComplexity = 0.6
    // personality drives depth to 0.8
    // result: depth capped at 0.6
}

@Test
void capacity_below_activation_has_no_effect() {
    // capacity.relationalComplexity = 0.8
    // personality drives depth to 0.5
    // result: depth = 0.5 (ceiling not reached)
}

@Test
void capacity_gap_signal_fires_above_threshold() {
    // capacity = 0.6, personality drives to 0.8
    // gap = 0.2 > 0.05 threshold
    // capacityConstrained = true
}

@Test
void capacity_gap_below_threshold_does_not_fire() {
    // capacity = 0.78, personality drives to 0.8
    // gap = 0.02 < 0.05 threshold
    // capacityConstrained = false
}

@Test
void null_capacity_preserves_existing_behaviour() {
    // capacityConfig = null
    // all parameters pass through unchanged
    // capacityConstrained = false
}

@Test
void convergence_never_capped_by_capacity() {
    // explicit capacity config present
    // convergence passes through regardless of value
}

@Test
void capacity_applies_after_fatigue() {
    // fatigue pushes depth from 0.7 to 0.6
    // capacity ceiling = 0.5
    // result: depth = 0.5 (fatigue then ceiling)
}

@Test
void cde_derivation_produces_compressed_range() {
    // any Jungian profile
    // all derived capacity values in [0.55, 0.95]
}

@Test
void explicit_yaml_overrides_derived_capacity() {
    // YAML specifies relationalComplexity = 0.3
    // derived value would be 0.75
    // result: 0.3 wins
}

@Test
void capacity_differentiation_matches_jungian_direction() {
    // analytical profile (high Ti+Te): relational > exploratory profile's relational
    // exploratory profile (high Ne+Ni): associative > analytical profile's associative
}
```

### CognitionTestHarness Scenario (cognition)

Full-pipeline scenario with capacity-constrained agents:

1. Analytical agent with moderate capacity + high depth personality → verify depth capped, constrained prose selected
2. Exploratory agent with high associative reach + high Ne personality → verify laterality uncapped (capacity > activation), normal prose selected
3. Agent with null capacity config → verify full backward compatibility, no capacity-constrained prose

Following the #849 S1 personality differentiation pattern.

## Module Placement

| Component | Module | Rationale |
|---|---|---|
| `CognitiveCapacityConfig` | cognitive-api | Per-agent config record, alongside SearchBudgetConfig, HabituationConfig, etc. |
| `CognitiveDefaults` change (field 21) | cognitive-index | Existing location |
| `CognitiveDefaultsRegistry` YAML parsing | cognitive-index | Existing location |
| `CognitiveDerivationEngine` capacity derivation | cognitive-index | Alongside existing 15 pathways |
| `SearchBudget` change (`capacityConstrained`) | cognition-api | Existing location |
| Capacity ceiling application | cognition (`SearchBudgetTickParticipant`) | Tick-time computation |
| Prose generation updates | mindmap-intelligence (`SearchBudgetDescriptionGenerationPhase`) | Existing prose generation |
| Prose selection updates | cognition (`SearchBudgetPromptSection`) | Existing prose selection |
| Quality tests | cognitive-index (test) | Alongside existing `SearchBudgetQualityTest` |
| Scenario test | cognition (test) | `CognitionTestHarness` pattern |

## Deferred Items

- **Learning rate modulation** — Cattell's Investment Theory implies capacity should modulate learning effectiveness in the memory subsystem. `CognitiveCapacityConfig` placement on `CognitiveDefaults` enables this without architectural changes. Separate follow-up issue.
- **Fatigue-capacity coupling** — Sustained cognitive load degrades processing capacity in reality. #880 (shared fatigue substrate) covers the interaction design. For v1, fatigue and capacity are independent.
- **Convergence ceiling** — Inhibitory control (Miyake et al. 2000) is a capacity dimension, but convergence blurs the capacity/personality boundary (Need for Cognitive Closure). Not in scope unless empirical testing reveals the need.

## References

- `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/SearchBudgetConfig.java` — current search budget config
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java` — CDE output record (20 fields)
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java` — CDE derivation pathways
- `cognition-api/src/main/java/io/casehub/neocortex/cognition/search/SearchBudget.java` — tick-time search budget record
- `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java` — tick-time activation
- `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetPromptSection.java` — prose selection
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/CuriosityDescriptionGenerationPhase.java` — prose generation (also `SearchBudgetDescriptionGenerationPhase`)
- `specs/issue-839-search-budget-situational-strength/2026-11-08-search-budget-situational-strength-design.md` — #839 spec, §Forward Interaction with Intelligence Capacity Layer
- DeYoung, C.G., Quilty, L.C., Peterson, J.B., & Gray, J.R. (2014). Openness to Experience, Intellect, and Cognitive Ability. *Journal of Personality Assessment*, 96(1), 46-52.
- DeYoung, C.G., Carey, B.E., Krueger, R.F., & Ross, S.R. (2016). Ten Aspects of the Big Five in the Personality Inventory for DSM-5. *Personality Disorders: Theory, Research, and Treatment*, 7(2), 113-123.
- Nusbaum, E.C. & Silvia, P.J. (2011). Are Openness and Intellect distinct aspects of Openness to Experience? *Personality and Individual Differences*, 51, 571-574.
- Halford, G.S., Wilson, W.H., & Phillips, S. (1998). Processing capacity defined by relational complexity. *Behavioral and Brain Sciences*, 21(6), 803-831.
- Mednick, S.A. (1962). The associative basis of the creative process. *Psychological Review*, 69, 220-232.
- Engle, R.W. & Kane, M.J. (2004). Executive attention, working memory capacity, and a two-factor theory of cognitive control. In *The Psychology of Learning and Motivation*, Vol. 44, 145-199.
- Cattell, R.B. (1987). *Intelligence: Its Structure, Growth, and Action*. North-Holland.
- Newell, A. & Simon, H.A. (1972). *Human Problem Solving*. Prentice-Hall.
- Webster, D.M. & Kruglanski, A.W. (1994). Individual differences in need for cognitive closure. *Journal of Personality and Social Psychology*, 67(6), 1049-1062.
- Miyake, A. et al. (2000). The unity and diversity of executive functions. *Cognitive Psychology*, 41(1), 49-100.
