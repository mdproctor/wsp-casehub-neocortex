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
        Double relationalComplexity,
        Double associativeReach,
        Double workingMemorySpan
) {
    public CognitiveCapacityConfig {
        if (relationalComplexity != null) validate("relationalComplexity", relationalComplexity);
        if (associativeReach != null) validate("associativeReach", associativeReach);
        if (workingMemorySpan != null) validate("workingMemorySpan", workingMemorySpan);
    }

    public static CognitiveCapacityConfig defaults() {
        return new CognitiveCapacityConfig(0.75, 0.75, 0.75);
    }

    private static void validate(String name, double value) {
        if (value < 0.0 || value > 1.0)
            throw new IllegalArgumentException(name + " must be in [0,1], got " + value);
    }

    public CognitiveCapacityConfig mergeWith(CognitiveCapacityConfig derived) {
        return new CognitiveCapacityConfig(
            relationalComplexity != null ? relationalComplexity : derived.relationalComplexity(),
            associativeReach != null ? associativeReach : derived.associativeReach(),
            workingMemorySpan != null ? workingMemorySpan : derived.workingMemorySpan());
    }

    public double relationalComplexityOrDefault() {
        return relationalComplexity != null ? relationalComplexity : 0.75;
    }

    public double associativeReachOrDefault() {
        return associativeReach != null ? associativeReach : 0.75;
    }

    public double workingMemorySpanOrDefault() {
        return workingMemorySpan != null ? workingMemorySpan : 0.75;
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

Fields use `Double` (boxed) to distinguish "not specified" (null) from "explicitly set to 0.0". Jackson deserialises missing YAML fields as null, enabling per-field merge in `deriveAndMerge()`. The `mergeWith()` method implements per-field null-coalescing: explicit values win, missing fields fall through to derived.

All values in [0,1]: 1.0 = uncapped (maximally capable), 0.0 = fully constrained. Derivation midpoint default 0.75 — equals `compress(0.5)`, the midpoint of the compressed Jungian derivation range [0.55, 0.95]. Not an empirical population mean.

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

Top-level placement enables future access from the memory subsystem for Cattell's Investment Theory learning rate modulation (#890), without reaching through SearchBudgetConfig.

When null, capacity ceilings are disabled — existing behaviour preserved. The tick participant checks `capacityConfig != null` before applying ceilings.

**Integration blast radius:** Adding field 21 changes the `CognitiveDefaults` record constructor, `empty()` factory (adds null argument), and all 20 existing `withX()` methods (each positionally reconstructs the record). A new `withCapacityConfig()` method is needed. This is the same mechanical pattern followed for every prior field addition (fields 16–20 in recent issues).

## CDE Derivation

New `deriveCapacity()` method called from `derive()`, parallel to the existing 15 derivation pathways (`derivePersonality`, `deriveMoodBaseline`, `deriveSearchBudgetDefaults`, etc.). Not an extension of `deriveSearchBudgetDefaults()` — that method returns `SearchBudgetConfig`, while capacity lives on `CognitiveDefaults` at the top level.

### Integration Points

**`derive()` addition** (CognitiveDerivationEngine.java:179):
```java
CognitiveCapacityConfig capacity = deriveCapacity(descriptor.dispositionProfile());
// ... existing derivation calls ...
return CognitiveDefaults.empty(descriptor.agentId())
    // ... existing .withX() chain ...
    .withCapacityConfig(capacity);
```

**`deriveAndMerge()` addition** (CognitiveDerivationEngine.java:213):
```java
.withCapacityConfig(mergeCapacity(explicit.capacityConfig(), derived.capacityConfig()))
```

**Per-field capacity merge** — unlike other CDE fields that use whole-record null-coalescing, capacity uses per-field merge via `CognitiveCapacityConfig.mergeWith()`:
```java
private static CognitiveCapacityConfig mergeCapacity(
        CognitiveCapacityConfig explicit, CognitiveCapacityConfig derived) {
    if (explicit == null) return derived;
    if (derived == null) return explicit;
    return explicit.mergeWith(derived);
}
```

This handles partial YAML specification correctly: a YAML specifying only `relationalComplexity: 0.90` produces a `CognitiveCapacityConfig(0.90, null, null)` — Jackson maps missing fields to null (boxed `Double`). The `mergeWith()` fills the nulls from the derived values, producing `CognitiveCapacityConfig(0.90, derivedAssociative, derivedWmSpan)`.

### Jungian → Capacity Mapping

The derivation uses Jungian cognitive functions as weak proxies, with a compressed range of [0.55, 0.95] that acknowledges the low correlation (r ≈ 0.3-0.4). Follows the existing CDE iteration pattern over `List<WeightedTerm>` (see `deriveGraphStructure`, `deriveExtractionBias`, `deriveAppraisalWeights`):

```java
static CognitiveCapacityConfig deriveCapacity(List<WeightedTerm> profile) {
    if (profile == null || profile.isEmpty()) return null;

    double tiWeight = 0.0, teWeight = 0.0, neWeight = 0.0, niWeight = 0.0, siWeight = 0.0;
    for (WeightedTerm term : profile) {
        String fn = term.term().toLowerCase();
        switch (fn) {
            case "ti" -> tiWeight = term.weight();
            case "te" -> teWeight = term.weight();
            case "ne" -> neWeight = term.weight();
            case "ni" -> niWeight = term.weight();
            case "si" -> siWeight = term.weight();
        }
    }

    double relational = compress(0.5 * (tiWeight + teWeight));
    double associative = compress(0.5 * (neWeight + niWeight));
    double wmSpan = compress(0.5 * (teWeight + siWeight));

    return new CognitiveCapacityConfig(relational, associative, wmSpan);
}

private static double compress(double raw) {
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
    double rc = capacity.relationalComplexityOrDefault();
    double wm = capacity.workingMemorySpanOrDefault();
    double ar = capacity.associativeReachOrDefault();

    depth = Math.min(rc, depth);
    breadth = Math.min(wm, breadth);
    laterality = Math.min(ar, laterality);
    // convergence: no ceiling
}

// Step 8: Final clamp
depth = clamp01(depth);
breadth = clamp01(breadth);
laterality = clamp01(laterality);
convergence = clamp01(convergence);
```

### Capacity Gap Signal

The tick participant computes the per-parameter gap between unconstrained and constrained values. Gap values are exposed on `SearchBudget` for two consumers: prose selection (boolean threshold) and the appraisal system (#892 — frustration pathway):

```java
double depthGap = 0.0, breadthGap = 0.0, lateralityGap = 0.0;
boolean capacityConstrained = false;
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

The `capacityConstrained` boolean uses a 0.05 threshold to filter noise for prose selection — the LLM wouldn't render a 0.02 gap differently from zero. The per-parameter gap values (depthGap, breadthGap, lateralityGap) are preserved at full precision for the appraisal system to generate proportional frustration (#892).

### SearchBudget Record

Grows from 7 to 11 fields:

```java
public record SearchBudget(
        double breadth,
        double laterality,
        double depth,
        double convergence,
        SearchMotivation source,
        boolean extremeActivation,
        boolean capacityConstrained,    // NEW — field 8
        double depthGap,                // NEW — field 9
        double breadthGap,              // NEW — field 10
        double lateralityGap,           // NEW — field 11
        Instant evaluatedAt
) { ... }
```

Per-parameter gap values (fields 9-11) are 0.0 when no capacity ceiling binds. Non-zero values indicate the magnitude by which motivation exceeds capacity on each dimension. Epic #841 requires these for the capacity→appraisal frustration pathway (#892): a gap of 0.3 (high motivation, low capacity) should produce stronger frustration than a gap of 0.05.

## Prose Generation

### SearchBudgetDescriptionGenerationPhase

Extends the LLM prompt to generate a third description (capacity-constrained) when capacity config is present.

**Unified system prompt** — replaces the current two-variant approach (`SYSTEM_PROMPT` / `SYSTEM_PROMPT_WITH_EXTREME`). The existing per-batch system prompt selection (`anyExtreme ? SYSTEM_PROMPT_WITH_EXTREME : SYSTEM_PROMPT`) has a known limitation: when any agent in the batch has extreme features, ALL agents receive the extreme-format system prompt, causing format mismatch for non-extreme agents. Adding a third variant would compound this problem.

The fix: a single unified system prompt that describes all possible fields. Each agent's per-agent **user prompt** specifies which descriptions are needed by including or excluding the relevant parameters:

```
SYSTEM_PROMPT_UNIFIED:

You describe an agent's cognitive search disposition — how they
naturally approach exploration and problem-solving, shaped by their personality.

Generate descriptions based on what information is provided:

1. **Normal range** (always) — how they naturally explore under moderate
   motivation. Write 2-3 sentences in second person ("you").

2. **Extreme intensity** (only when extreme parameters are provided) — how
   their exploration changes under extreme motivation pressure. 2-3 sentences.

3. **Capacity constrained** (only when capacity parameters are provided) —
   what happens when motivation pushes past cognitive capacity limits.
   Where does their reach exceed their grasp? 2-3 sentences.

Describe felt cognitive state, not parameters. Do not name parameters.

Respond with JSON containing only the requested fields:
- Base only: {"description": "..."}
- With extreme: {"normal": "...", "extreme": "..."}
- With capacity: {"normal": "...", "constrained": "..."}
- With both: {"normal": "...", "extreme": "...", "constrained": "..."}
```

The per-agent user prompt (`buildUserPrompt`) conditionally includes extreme parameters (when `extremeInteraction != null || fatigue != null`) and capacity parameters (when `capacityConfig != null`). Each task's response parsing (`extractField`/`extractDescription`) handles whichever fields are present — existing null-safe extraction with fallback works unchanged.

All descriptions crystallise to the same MindMap COGNITIVE node: `description` (backward-compatible), `extreme-description` (#839), `constrained-description` (new).

### Tick-Time Prose Selection

`SearchBudgetPromptSection` selects prose using **composition**, not exclusive priority. Capacity constraint and extreme activation describe orthogonal phenomena — capacity is structural (ceiling), extreme is dynamic (pressure). An agent can experience both simultaneously, and should.

This follows the existing `modulateByContinuum()` pattern: fixation context is prepended to the base prose, composing two independent signals.

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

Composition semantics: capacity-constrained prose **prepends** to the selected base (normal or extreme). An INTP at 0.9 intensity with a relational complexity ceiling of 0.7 hears both: their reasoning is truncated by capacity AND pressure is narrowing their focus. `modulateByContinuum()` then modulates the combined prose by recurring thought state, composing all three independent signals.

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

When `capacityConfig` is present in YAML, the CDE's `deriveAndMerge()` uses per-field merge via `CognitiveCapacityConfig.mergeWith()`. Partially specified capacity (e.g., only `relationalComplexity: 0.90`) fills missing fields from the Jungian derivation:

```yaml
# Partial specification — only relationalComplexity is explicit
capacityConfig:
  relationalComplexity: 0.90
```

Jackson deserialises this as `CognitiveCapacityConfig(0.90, null, null)` — `Double` (boxed) fields map missing YAML keys to null, not 0.0. The `mergeWith()` call in `deriveAndMerge()` produces `CognitiveCapacityConfig(0.90, derivedAssociative, derivedWmSpan)`. This is distinct from the existing `deriveAndMerge()` pattern for other fields (whole-record null-coalescing) — capacity requires per-field merge because partial specification is a common use case (configuring one dimension while deriving the rest).

When `capacityConfig` is absent from YAML (null at record level), whole-record null-coalescing applies as with all other fields — the derived capacity config wins entirely.

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

## Forward Interaction with #839

The #839 spec (§Forward Interaction with Intelligence Capacity Layer) explicitly requests: "#840's spec should evaluate whether to absorb this spec's direct-parameter approach into a ceiling-mediated model."

**Evaluation:** The independent model is correct. Fatigue and capacity model different phenomena:

1. **Different mechanisms:** Fatigue is motivational resource depletion (dynamic, transient) — Hockey's compensatory control allocates resources strategically under load. Capacity is structural cognitive limit (static, derived from intelligence) — Halford's relational complexity defines the ceiling regardless of motivational state.

2. **Different directionality:** Fatigue effects are signed — they push parameters up (laterality under impulsivity) or down (depth under neuroticism). Ceiling mediation only makes sense for upper bounds. Absorbing fatigue into capacity ceilings would lose the signed reallocation that is Hockey's key insight.

3. **Correct processing order:** Fatigue modifies raw values (step 6), capacity caps the result (step 7). This means fatigue cannot push a parameter above its capacity ceiling — the ceiling always wins. The reverse ordering would be wrong: applying ceiling first would cap the raw value before fatigue's reallocation, preventing the meaningful differentiation of "what you sacrifice when fatigued."

4. **No double-counting:** #839's fatigue effects modify the search budget parameters directly (additive). Capacity ceilings apply `Math.min()` after. These compose correctly — fatigue cannot push above the ceiling, and ceiling cannot undo fatigue-driven reduction below it. The #839 concern about "two fatigue sources could double-count" applies only to the deferred #880 scenario where capacity ceilings themselves degrade under fatigue. For v1, capacity ceilings are static.

**Reference to #880:** If future work (per epic #841: "Cognitive capacity degrades under fatigue") introduces fatigue-dependent ceiling degradation, the two fatigue sources would interact. #880 (shared fatigue substrate) is the appropriate venue for that design. This spec's static capacity model is correct for v1 and forward-compatible with dynamic ceilings.

## Deferred Items

- **Learning rate modulation** (#890) — Cattell's Investment Theory implies capacity should modulate learning effectiveness in the memory subsystem. `CognitiveCapacityConfig` placement on `CognitiveDefaults` enables this without architectural changes.
- **Fatigue-capacity coupling** — Sustained cognitive load degrades processing capacity in reality. #880 (shared fatigue substrate) covers the interaction design. For v1, fatigue and capacity are independent.
- **Convergence ceiling** (#891) — Inhibitory control (Miyake et al. 2000) is a capacity dimension, but convergence blurs the capacity/personality boundary (Need for Cognitive Closure). Filed for evaluation after empirical testing (#866) reveals whether convergence benefits from a ceiling.
- **Capacity→appraisal frustration pathway** (#892) — Epic #841 requires that capacity gaps produce frustration via the appraisal system. This spec exposes per-parameter gap values on `SearchBudget` (fields 9-11) to enable this. The appraisal integration itself is separate work.

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
