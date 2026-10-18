# Cognitive Section Calibration — Arousal-Gated Tiered Rendering

**Issue:** casehubio/neocortex#400
**Date:** 2026-10-07
**Status:** Draft

## Problem

The cognitive system renders up to 16 sections per tick in the observation (user prompt). The disposition-derived personality lives in the system prompt as a weighted term list. When cognitive sections are prescriptive ("plan obsessively", "narrate in third person"), they override disposition completely — characters follow tendencies literally rather than expressing personality in nuanced ways.

Empirical findings from calibration experiments:
- Prescriptive cognitive sections override disposition → PP scored 2/5
- Disposition alone (no cognitive sections) produces good but generic results → PP scored 4/5 as "universal good leader"
- Coherent somatic personality + contextual cognitive state reinforces emergence → HC scored 5/5 with "Trust→Access→Control→Safety"
- Every reduction of cognitive sections strengthened the personality signal

The weighting between personality and cognitive data isn't static — it's driven by emotional intensity. High arousal → personality dominates (deep defaults under pressure). Low arousal → cognitive data has room to modulate expression. This matches real cognition: under stress, higher-order processing shuts off and instinct takes over.

## Architecture

### Three Fixed Tiers

Sections are assigned to tiers by their nature. The assignment is stable across all agents — what varies per agent is the arousal threshold at which lower tiers activate.

| Tier | Sections | Nature |
|------|----------|--------|
| **Core** | Mood, Drives, Appraisal, Behavioral, NeedsPyramid, CharacterDrives* | Somatic — body-level personality state, emotional reactions, gut feelings, crystallized behavioral attractors, psychological needs |
| **Contextual** | UserModel, MentalModel, Narrative, Attention, TemporalFocus | Relational — who's present, what you believe about them, shared history, what demands attention, temporal awareness |
| **Supplementary** | Strategy, EmergentGoals, Reflection, Consolidation, Constraints (soft) | Deliberative — learned strategies, planned goals, meta-cognitive insights, consolidation artifacts, behavioral guidelines |

*CharacterDrives is already mutually exclusive with Appraisal (existing conditional suppression in `promptSections()` line 502). In production with CARMA enabled, CharacterDrives does not render.

### Binary Tier Activation

Tiers are on or off. No condensed intermediate rendering state. No disposition-reinforcement text when suppressed.

Suppression IS reinforcement: fewer competing signals means the core tier's personality signal gets louder. This was proved empirically — removing sections improved emergence in every test.

No gradual condensation (adds complexity to every renderer for marginal benefit). No disposition labels when suppressed ("Your gallant nature guides you here" reintroduces the third-person briefing scripting that 9 experimental runs eliminated).

### Tier Activation Logic

Current PAD arousal compared against per-agent thresholds derived from the personality-dominance scalar:

```
supplementaryThreshold = 1.0 - personalityDominance
contextualThreshold    = supplementaryThreshold + 0.3   (clamped to 1.0)
```

| Arousal level | HC (scalar 0.9) | PP (scalar 0.5) |
|---|---|---|
| Low (< threshold) | All three tiers | All three tiers |
| Medium | Core + Contextual only | All three tiers |
| High | Core only | Core + Contextual only |
| Extreme | Core only | Core only |

HC (scalar 0.9): supplementary suppressed above arousal 0.1 (almost always), contextual above 0.4. Personality overwhelms almost everything — his cognitive norms are performance, not genuine values.

PP (scalar 0.5): supplementary suppressed above arousal 0.5 (moderate stress), contextual above 0.8 (extreme only). Personality and cognition are integrated — both instinct and learned behaviour produce reward.

### Tier Placement Rationale

**Attention stays Contextual:** Under extreme arousal, the body already knows what demands focus (the threat). The attention briefing is most useful during moderate arousal when multiple things compete. Under extreme stress, you don't need a list of things to pay attention to — you're already fixated.

**Soft constraints stay Supplementary:** Hard constraints live in the system prompt and are never affected. Soft constraints ("be diplomatic") are deliberately weaker guidelines. People relax social norms under extreme pressure. The safety net is that HARD constraints never disappear.

## Personality-Dominance Scalar

### Derivation

One `personalityDominance` value (double, 0.0-1.0) per agent, stored as the 18th field in `CognitiveDefaults`. Derived by `CognitiveDerivationEngine` as the 10th derivation pathway.

### Computation — PAD Geometry

The scalar is computed from formation memory PAD patterns without subjective classification of memories. The PAD geometry carries the signal: dominance co-occurring with pleasure = personality-driven reward. Pleasure without dominance = socially-mediated reward.

```
dominance_weighted_reward = Σ max(0, P_i) * D_i    for all formation memories
total_positive_pleasure   = Σ max(0, P_i)           for all formation memories

personalityDominance = clamp(
    (dominance_weighted_reward / total_positive_pleasure + 1) / 2,
    0.0, 1.0
)
```

**Fallback:** When `memoryCount == 0` (no formation memories), `personalityDominance` defaults to 0.5 (balanced — neither personality-dominant nor cognition-dominant).

### Empirical Validation

| Character | High-pleasure memories | Dominance pattern | Expected scalar |
|---|---|---|---|
| HC | Age 12 (manipulation), Age 18 (scheming) | D: 0.9, 0.9 — only personality-driven actions produce reward | ~0.85 |
| PP | Ages 5-17 (mixed instinct + learning) | D: varies (-0.2 to 0.8) — both personality and learned behaviour produce reward | ~0.55 |
| Mob | Highest intensity around Penelope | D: high when she's involved, mixed otherwise | ~0.65 |

## CDE Input Evolution

### DescriptorView Extension

`DescriptorView` currently carries: `agentId`, `DispositionAxes`, `dispositionProfile` (WeightedTerms), `goals`. The 10th pathway needs formation memory PAD statistics.

New field on `DescriptorView`:

```java
record FormationPadSummary(
    double dominanceWeightedReward,   // Σ max(0, P_i) * D_i
    double totalPositivePleasure,     // Σ max(0, P_i)
    int memoryCount                   // diagnostic + fallback guard
)
```

Pre-aggregated by the caller (blocks runtime) from the agent's formation memories at startup/profile-load time. The CDE receives statistics, never raw memories. Clean separation: memory storage owns the memories, the caller computes the summary, CDE derives the scalar.

The `memoryCount` field serves both diagnostics and the fallback check — `memoryCount == 0` is clearer intent than `totalPositivePleasure == 0` for "no memories exist."

### 10th Derivation Pathway

```java
// In CognitiveDerivationEngine
private static double derivePersonalityDominance(@Nullable FormationPadSummary summary) {
    if (summary == null || summary.memoryCount() == 0) {
        return 0.5;  // balanced default
    }
    if (summary.totalPositivePleasure() == 0.0) {
        return 0.5;  // no positive memories
    }
    double ratio = summary.dominanceWeightedReward() / summary.totalPositivePleasure();
    return Math.clamp((ratio + 1.0) / 2.0, 0.0, 1.0);
}
```

## Runtime Integration

### Tier-Aware Section Customizer

The tier filtering plugs into the existing `sectionCustomizer` mechanism on `CognitionCore`. No new rendering infrastructure needed. Individual sections remain simple renderers — they never see arousal or tiers.

```java
public class TierFilterCustomizer implements UnaryOperator<List<CognitionPromptRenderer>> {

    private final MoodOrchestrator mood;
    private final double personalityDominance;

    // Static tier mapping
    private static final Map<Class<?>, SectionTier> TIER_MAP = Map.ofEntries(
        // Core — somatic personality state
        Map.entry(MoodPromptSection.class, SectionTier.CORE),
        Map.entry(DrivePromptSection.class, SectionTier.CORE),
        Map.entry(AppraisalPromptSection.class, SectionTier.CORE),
        Map.entry(BehavioralPromptSection.class, SectionTier.CORE),
        Map.entry(CharacterDrivePromptSection.class, SectionTier.CORE),
        Map.entry(NeedsPyramidPromptSection.class, SectionTier.CORE),
        // Contextual — relational + situational
        Map.entry(UserModelPromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(MentalModelPromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(NarrativePromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(AttentionPromptSection.class, SectionTier.CONTEXTUAL),
        Map.entry(TemporalFocusPromptSection.class, SectionTier.CONTEXTUAL),
        // Supplementary — deliberative
        Map.entry(StrategyPromptSection.class, SectionTier.SUPPLEMENTARY),
        Map.entry(EmergentGoalPromptSection.class, SectionTier.SUPPLEMENTARY),
        Map.entry(ReflectionPromptSection.class, SectionTier.SUPPLEMENTARY),
        Map.entry(ConsolidationPromptSection.class, SectionTier.SUPPLEMENTARY),
        Map.entry(ConstraintPromptSection.class, SectionTier.SUPPLEMENTARY)
    );

    @Override
    public List<CognitionPromptRenderer> apply(List<CognitionPromptRenderer> sections) {
        double arousal = mood.currentArousal();
        double suppThreshold = 1.0 - personalityDominance;
        double ctxThreshold  = Math.min(suppThreshold + 0.3, 1.0);

        return sections.stream()
            .filter(s -> {
                var tier = TIER_MAP.getOrDefault(unwrapClass(s), SectionTier.CORE);
                return switch (tier) {
                    case CORE -> true;
                    case CONTEXTUAL -> arousal < ctxThreshold;
                    case SUPPLEMENTARY -> arousal < suppThreshold;
                };
            })
            .toList();
    }
}
```

The customizer is registered via `chainSectionCustomizer()` so it composes with any existing customizers. `unwrapClass()` handles `DirectiveSection` wrapping (extracts the delegate class).

### Arousal Source

The arousal value comes from `MoodOrchestrator` — the current PAD mood state's arousal component (range [-1, 1]). In the PAD model, arousal represents activation level: +1.0 is high activation (excitement, panic, rage), -1.0 is low activation (calm, relaxed, drowsy). The threshold comparison uses the raw arousal value directly — higher arousal means more activation, which suppresses lower tiers. Negative arousal (calm states) keeps all tiers active.

### Section Ordering Within Tiers

Sections within each active tier maintain their current ordering from `promptSections()`. The tier filter only removes sections — it does not reorder.

## Experiment Framework

### Experimental Setup

Experiments run in the examples repo (casehubio/examples), consuming neocortex. They validate that the tiered rendering produces better character behavior than the current flat rendering.

**Profile requirement:** All experiments use the GENERIC profile (not BASELINE) to avoid LLM training bias on character names. GENERIC results are the clean measurement of the architecture's effect, without character knowledge confounding the scores.

### Test Matrix

| Experiment | Config | Expected Result |
|---|---|---|
| **Baseline** | Current flat rendering (all sections, fixed order) | Reference scores |
| **Tier-only** | Tier filtering with personality-dominance scalar, neutral arousal | Better emergence for personality-dominant characters |
| **Arousal sweep** | Same characters at calm → stressed → crisis arousal levels | High arousal produces personality-dominant behavior; low arousal allows cognitive integration |

### Validation Criteria

Scoring rubric: character distinctiveness 1-5, emergence quality. Specific checks:
- HC under high arousal: predatory satisfaction overwhelms social norms (emerged, not scripted)
- PP under low arousal: personality and learned behavior integrate (father's teaching + instinct)
- PP under high arousal: falls back to protective instinct, learned strategies drop away
- Mob under high arousal (Penelope present): personality dominates completely
- Mob under low arousal (routine): more balanced cognitive expression

### Test Infrastructure

The `RelationalModelEvalTest` pattern: render observation → character response → judge emergence quality. The arousal sweep is the new dimension: same character, same event, vary arousal, verify the tier activation produces the right behavioral shift.

## Full Derivation Chain

```
Formation memories + PAD tags
    → sleep/consolidation
        → personality profile (personality-cognition weighting)
            → CognitiveDerivationEngine (10th pathway)
                → personalityDominance scalar in CognitiveDefaults
                    → TierFilterCustomizer at render time
                        → binary tier activation based on current arousal
```

Everything derived, nothing hand-configured except the authored memories.

## Dependencies

| Dependency | Status | Impact |
|---|---|---|
| casehubio/neocortex#398 (formation memory seeding) | Open | Formation memories with PAD tags needed for scalar computation |
| MoodOrchestrator.currentArousal() | Exists | Runtime arousal source |
| CognitiveDerivationEngine | Exists (9 pathways) | Extend with 10th pathway |
| CognitiveDefaults | Exists (17 fields) | Add 18th field |
| DescriptorView | Exists | Extend with FormationPadSummary |
| sectionCustomizer mechanism | Exists | Wiring point for tier filter |

## References

- casehubio/examples#97 — Phase 4: calibrating cognitive section prominence
- casehubio/examples#76 — directive-minimal YAML rewrite (established section ordering)
- `CognitionCore.promptSections()` — current section ordering and composition
- `CognitiveSystemPromptRenderer` — system prompt personality rendering
- `CognitivePreambleGenerator` — cognitive preamble in system prompt
- `DirectiveSection` — directive wrapping mechanism
- `CognitiveDerivationEngine` — 9 existing derivation pathways
- `CognitiveDefaults` — 17 existing fields from CDE
- `DescriptorView` — current CDE input record
- `TierFilterCustomizer` concept — uses existing `sectionCustomizer`/`chainSectionCustomizer`
- Wacky-manor calibration experiments — HC/PP/Mob empirical findings
