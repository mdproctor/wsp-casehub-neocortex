# PID-5 Facet Extension for Situational Attractor Profiles

**Issue:** casehubio/neocortex#1076
**Date:** 2026-11-26
**Status:** Design

## Overview

Extend the PID-5 facet system from 13 to 25 facets across the full pipeline: classification (PersonalityPromptBuilder → CBR cache), situational modulation (archetype attractor profiles → EffectiveCognitiveDefaults), and cognitive derivation (CognitiveDerivationEngine rules). Backfill 2 existing facets that lack CDE rules.

## Scope

### In scope
- Add 12 PID-5 facets to `AmpdFacets.CANONICAL` (eidos) and `PersonalityFacet` (neocortex)
- Add CDE derivation rules for 10 facets (Tiers 1+2) based on literature review
- Add situational attractor profiles for all facets with STRONG/MODERATE evidence
- Extend PersonalityPromptBuilder to pass all 25 facets
- Backfill Deceitfulness (1-2 rules) and Attention Seeking (0-1 rules)
- End-to-end integration test

### Out of scope
- CDE structural decomposition (follow-up if engine exceeds ~1500 lines)
- Domain-cap multicollinearity handling (follow-up if integration tests show implausible stacking)
- Classifier eval (25 vs 13 facets) — validation step during implementation, not a design concern

## 1. Facet Inventory

### 12 New Facets (by PID-5 Domain)

| Facet | PID-5 Domain | CDE Tier | CDE Rules? | Situational Profiles? |
|---|---|---|---|---|
| Anhedonia | Negative Affect / Detachment | Tier 1 | Yes | Yes |
| Depressivity | Negative Affect | Tier 1 | Yes | Yes |
| Perseveration | Negative Affect | Tier 1 | Yes | Yes |
| Separation Insecurity | Negative Affect | Tier 1 | Yes | Yes |
| Rigid Perfectionism | Anankastia | Tier 1 | Yes | Yes |
| Distractibility | Disinhibition | Tier 1 | Yes | Yes |
| Restricted Affectivity | Detachment | Tier 2 | Yes | Yes |
| Irresponsibility | Disinhibition | Tier 2 | Yes | Yes |
| Cognitive/Perceptual Dysregulation | Psychoticism | Tier 2 | Yes | Yes |
| Eccentricity | Psychoticism | Tier 2 | Yes | Yes |
| Submissiveness | Negative Affect | No CDE | No | Yes (soft influence via classification prompt only) |
| Unusual Beliefs | Psychoticism | No CDE | No | Minimal |

### 2 Backfill Facets (existing, zero CDE rules)

| Facet | PID-5 Domain | CDE Rules to Add |
|---|---|---|
| Deceitfulness | Antagonism | laterality ↑, depth ↑ (Bereczkei 2014/2015 Machiavellianism) |
| Attention Seeking | Antagonism | arousal ↑ (weak, clinical literature only) |

## 2. CDE Derivation Rules

### Design Constraints

- **Coefficient sizing for Negative Affectivity:** 5 new NA facets join 4 existing ones (Anxiousness, Emotional Lability, Hostility, Suspiciousness). Keep coefficients at ±0.1 to avoid multicollinearity-driven overestimation on shared parameters like `deriveRecurringThoughtConfig`.
- **Provenance:** Every rule must carry a literature citation. Tier 1 rules are grounded in meta-analyses or multiple replicated studies. Tier 2 rules are grounded in indirect evidence (related constructs) with moderate confidence.

### Tier 1 Facet Rules

#### Anhedonia
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveMoodBaseline` | pleasure | ↓ | −(an−0.5)×0.4 | Meehl 1975; Germans & Kring 2000 |
| `deriveMoodBaseline` | arousal | ↓ | −(an−0.5)×0.3 | Treadway & Zald 2011 |
| `deriveCuriosity` | categoryWeights (all) | ↓ | −(an−0.5)×0.15 | Silvia 2006; Sherdell et al. 2012 |
| `deriveSearchBudget` | depthMidpoint | ↓ | −(an−0.5)×0.15 | Pillny et al. 2026 meta (g=−0.28) |
| `derivePoolConfig` | maxEffort | ↓ | −(an−0.5)×0.15 | Oxford/Cerebral Cortex 2024 |
| `deriveCbrStrategy` | temporalDecayDays | ↑ | +(an−0.5)×30 | Neural delay discounting 2025 |

#### Depressivity
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveMoodBaseline` | pleasure | ↓ | −(dp−0.5)×0.4 | Mehrabian 1996; Watson & Clark 1984 |
| `deriveMoodBaseline` | dominance | ↓ | −(dp−0.5)×0.4 | Seligman 1975; Maier & Seligman 2016 |
| `deriveAppraisalWeights` | conduciveness | ↓ | −(dp−0.5)×0.2 | Scherer 2022 (N=4859, path analysis) |
| `deriveAppraisalWeights` | controllability | ↓ | −(dp−0.5)×0.2 | Scherer 2022 |
| `deriveRecurringThought` | ruminationThreshold | ↓ | −(dp−0.5)×0.1 | Nolen-Hoeksema 1991 |
| `deriveCapacity` | workingMemorySpan | ↓ | −(dp−0.5)×0.1 | Nikolin 2021 meta (d=0.34−0.65) |
| `derivePoolConfig` | maxEffort | ↓ | −(dp−0.5)×0.1 | Pillny 2026 meta (g=−0.28) |
| `deriveRegulation` | reappraisalCapacity | ↓ | −(dp−0.5)×0.1 | Joormann & Gotlib 2010 |

#### Perseveration
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveRecurringThought` | fixationThreshold | ↓ | −(pv−0.5)×0.15 | Davis & Nolen-Hoeksema 2000 (WCST) |
| `deriveSearchBudget` | lateralityMidpoint | ↓ | −(pv−0.5)×0.15 | Chamberlain 2006; Robbins 2007 |
| `deriveSearchBudget` | convergenceMidpoint | ↑ | +(pv−0.5)×0.1 | "Depressive interlock" — Fredrickson 2001 inverse |
| `deriveHabituation` | habituationRate | ↓ | −(pv−0.5)×0.1 | PERCS framework 2026; GAD no-habituation findings |
| `deriveHabituation` | repetitionTolerance | ↑ | +(pv−0.5)×1.0 | PERCS 2026 (Repetitive Sequence Stability) |
| `deriveCapacity` | associativeReach | ↓ | −(pv−0.5)×0.1 | BMC Psychology 2026 (set-shifting → divergent thinking) |

#### Rigid Perfectionism
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveRecurringThought` | fixationThreshold | ↓ | −(rp−0.5)×0.1 | Xie 2019 meta (k=12, rumination) |
| `deriveSearchBudget` | convergenceMidpoint | ↑ | +(rp−0.5)×0.1 | Cognitive flexibility r=−.48 (2025) |
| `deriveSearchBudget` | lateralityMidpoint | ↓ | −(rp−0.5)×0.1 | Egan 2007 (dichotomous thinking) |
| `deriveHabituation` | habituationRate | ↓ | −(rp−0.5)×0.1 | Stahl 2015 (ERP, N=94) |
| `deriveHabituation` | repetitionTolerance | ↑ | +(rp−0.5)×1.0 | Bouchard 2009 (NJR + checking) |
| `derivePoolConfig` | maxEffort | ↑ | +(rp−0.5)×0.15 | Philp 2012 (overcommitment mediation) |
| `deriveRegulation` | reappraisalCapacity | ↓ | −(rp−0.5)×0.1 | Vois 2026 (3-wave, N=454; ECP → suppression) |

#### Distractibility
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveCapacity` | workingMemorySpan | ↓ | −(dt−0.5)×0.2 | Martinussen 2005 meta (d=0.85–1.06 spatial) |
| `deriveSearchBudget` | depthMidpoint | ↓ | −(dt−0.5)×0.15 | Esterman 2014 (sustained attention fluctuations) |
| `deriveSearchBudget` | breadthSteepness | ↑ | +(dt−0.5)×0.1 | Stolte 2022 (ADHD divergent thinking r=0.16–0.22) |
| `derivePoolConfig` | maxEffort | ↓ | −(dt−0.5)×0.1 | Esterman & Rothlein 2019 |

#### Separation Insecurity
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveRecurringThought` | fixationThreshold | ↓ | −(si−0.5)×0.1 | Stanton & Campbell 2015 |
| `deriveAppraisalWeights` | relevance | ↑ | +(si−0.5)×0.15 | Downey & Feldman 1996; Kawamoto 2015 |
| `deriveExtractionBias` | relationshipBias | ↑ | +(si−0.5)×0.15 | Mikulincer & Shaver 2003 |
| `deriveMoodBaseline` | arousal | ↑ | +(si−0.5)×0.15 | Attachment anxiety hyperactivation literature |
| `deriveRegulation` | reappraisalCapacity | ↓ | −(si−0.5)×0.1 | PLOS ONE 2018 (social anxiety mediation) |

### Tier 2 Facet Rules

#### Restricted Affectivity
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveExtractionBias` | affectSensitivity | ↓ | −(ra−0.5)×0.2 | Trevisan 2019 meta (66 samples, r=−.162) |
| `deriveRegulation` | reappraisalCapacity | ↓ | −(ra−0.5)×0.15 | Preece 2022 (N=501) |

#### Irresponsibility
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `derivePoolConfig` | maxEffort | ↓ | −(ir−0.5)×0.15 | Credé 2017 meta (N=66,807, ρ=.84 Grit-C) |
| `deriveCoping` | disengagement | ↑ | (via inverse conscientiousness) | Connor-Smith 2007 meta (N=33,094) |
| `deriveCbrStrategy` | temporalDecayDays | ↑ | +(ir−0.5)×20 | Manning 2014 (C→patience r=.47) |

#### Cognitive/Perceptual Dysregulation
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveCapacity` | workingMemorySpan | ↓ | −(cd−0.5)×0.1 | Siddi 2017 meta (67 studies) |
| `deriveSearchBudget` | depthMidpoint | ↓ | −(cd−0.5)×0.1 | Guralnik 2000 (DPD attention deficits) |
| `deriveExtractionBias` | affectSensitivity | ↓ | −(cd−0.5)×0.1 | Ozdemir 2025 meta (alexithymia-schizotypy) |

#### Eccentricity
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveSearchBudget` | lateralityMidpoint | ↑ | +(ec−0.5)×0.1 | Carson 2003 (reduced latent inhibition) |
| `deriveSearchBudget` | breadthSteepness | ↑ | +(ec−0.5)×0.1 | Wang 2018 (overinclusion mediation) |

### Backfill Rules

#### Deceitfulness
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveSearchBudget` | lateralityMidpoint | ↑ | +(dc−0.5)×0.1 | Bereczkei 2014/2015 (Machiavellian cognitive flexibility) |
| `deriveSearchBudget` | depthMidpoint | ↑ | +(dc−0.5)×0.1 | Bereczkei 2015/2017 (strategic planning) |

#### Attention Seeking
| CDE Method | Parameter | Direction | Coefficient | Citation |
|---|---|---|---|---|
| `deriveMoodBaseline` | arousal | ↑ | +(as−0.5)×0.1 | HPD clinical literature (emotional expressiveness) |

## 3. Situational Attractor Profiles

New facet shifts added to `archetype-situational-profiles.yaml` per archetype family × mode. Delta values on 0-100 AMPD scale (clamped [-50, 50]), converted to 0-1 by `SituationalDeltaConverter` (÷100).

### Stress Mode

| Facet | Delta | Confidence | Citation |
|---|---|---|---|
| Anhedonia | +12 | STRONG | Pizzagalli 2014 |
| Depressivity | +15 | STRONG | Beck 1967 diathesis-stress |
| Perseveration | +12 | STRONG | Nature Sci Reports 2021 |
| Distractibility | +12 | STRONG | PMC 2024 (PFC→amygdala shift) |
| Separation Insecurity | +12 | STRONG | Mikulincer & Shaver 2003 |
| Cog/Perceptual Dysregulation | +12 | STRONG | Bremner peritraumatic dissociation |
| Rigid Perfectionism | +8 | MODERATE | PMC 2022 self-critical amplification |
| Restricted Affectivity | +8 | MODERATE | Alexithymia intensification under burnout |
| Irresponsibility | +6 | MODERATE | Baumeister ego depletion (contested) |
| Eccentricity | +6 | MODERATE | Rónai 2026 ESM |
| Submissiveness | +8 | MODERATE | PNAS 2025 (stress + rank) |
| Unusual Beliefs | +6 | MODERATE | Keinan 1994/2002 (Gulf War) |

### Flow Mode

| Facet | Delta | Confidence | Citation |
|---|---|---|---|
| Depressivity | −12 | STRONG | Translational Psychiatry 2024 twin study |
| Distractibility | −15 | STRONG | Ashinoff & Abu-Akel 2021 |
| Anhedonia | −8 | MODERATE | Flow as sustained intrinsic reward via DA |
| Rigid Perfectionism | −8 | MODERATE | 2×2 model (ECP inhibits flow; flow suppresses evaluation) |
| Eccentricity | +8 | MODERATE | Nelson & Rawlings 2010 (positive schizotypy → creative flow) |
| Cog/Perceptual Dysregulation | +6 | MODERATE | JAEX 2022 (flow-dissociation overlap) |

### Social Collaborative Mode

| Facet | Delta | Confidence | Citation |
|---|---|---|---|
| Depressivity | +8 | STRONG | Flett 2024 co-rumination |
| Rigid Perfectionism | +8 | STRONG | Hewitt & Flett 1991 (socially prescribed) |
| Irresponsibility | −8 | MODERATE | Social accountability |
| Submissiveness | −6 | MODERATE | Gilbert safety system |
| Separation Insecurity | −6 | MODERATE | Supportive context → safety system |
| Restricted Affectivity | +6 | MODERATE | Emotional demands exposed |
| Perseveration | +6 | MODERATE | Nature 2025 co-rumination |

### Social Competitive Mode

| Facet | Delta | Confidence | Citation |
|---|---|---|---|
| Depressivity | +12 | STRONG | McCarthy & Morina 2020 meta |
| Rigid Perfectionism | +12 | STRONG | Curran & Hill 2019 meta |
| Separation Insecurity | +12 | STRONG | Gasiorowska 2026 (N=4,456) |
| Deceitfulness | +12 | STRONG | Bereczkei 2015 (Machiavellian strategy) |
| Submissiveness | +8 | MODERATE | Competition → deferral |
| Eccentricity | −8 | MODERATE | Asch 1951 conformity pressure |

### Social Hierarchical Mode

| Facet | Delta | Confidence | Citation |
|---|---|---|---|
| Submissiveness | +15 | STRONG | Tiedens & Fragale 2003 (complementarity) |
| Separation Insecurity | +12 | STRONG | Gilbert social rank theory |
| Irresponsibility | −8 | MODERATE | Authority enforcement → compliance |
| Eccentricity | −8 | MODERATE | Authority → conformity pressure |
| Deceitfulness | +8 | MODERATE | Stackelberg power differential |
| Depressivity | +8 | MODERATE | Social rank salience → depression |
| Cog/Perceptual Dysregulation | +6 | MODERATE | Social stress → dissociation |
| Rigid Perfectionism | +8 | MODERATE | Authority-imposed standards |

## 4. Classification Pipeline

### PersonalityPromptBuilder

Extend to pass all 25 facets in every classification call. Currently the PID-5 section of the prompt includes 7 facets; this grows to 25.

Changes:
- Remove the 7-facet allowlist — iterate over all facets from the metadata map
- `pid5Suffix()` and `personalitySystemPrompt()` include all 25 facet scores
- CBR cache key SHA-256 hash includes all 25 facet scores (sorted by facet name for deterministic ordering)

Token impact: ~100 additional tokens per classification call (negligible).

Validation: Run caps-llm-classifier eval suite with 25 facets to confirm accuracy is maintained vs 13-facet baseline.

## 5. Cross-Repo Changes

### Eidos (first)

1. `AmpdFacets.CANONICAL` — add 12 facet name strings to the `Set.of()` call
2. `archetype-situational-profiles.yaml` — add `AmpdFacetShift` entries for each archetype family × mode per Section 3

### Neocortex (after eidos version bump)

1. `PersonalityFacet` record — add 12 String constants (ANHEDONIA, DEPRESSIVITY, etc.)
2. `PersonalityProfileEntry.AmpdAssessment` record — add 12 `Integer` fields with `@JsonProperty` annotations for hyphenated JSON keys (e.g., `@JsonProperty("rigid-perfectionism") Integer rigidPerfectionism`). Note: `SituationalProfileEntry` already uses `Map<String, Integer> facetDeltas` — no changes needed there.
3. `PersonalityProfileHandler` — extend facet-to-node-property mapping to include the 12 new facets
4. `CognitiveDerivationEngine` — add derivation rules per Section 2 across existing derivation methods
5. `PersonalityPromptBuilder` — extend to 25 facets per Section 4
6. `PersonalityMetadataEnricher` — ensure new facets flow through metadata enrichment for BehavioralSynthesisPhase and DriveProfileDerivationPhase

### Existing Agent Migration

`PersonalityFacet.facetScore()` returns 0.5 for absent facets. Agents with 13-facet descriptors automatically get neutral defaults for the 12 new facets. No explicit migration needed — new facets only produce non-neutral CDE effects when an agent's descriptor includes them with non-0.5 scores.

## 6. Testing Strategy

### Integration Test

An end-to-end test that:
1. Creates an agent with the full 25-facet set (some facets at extreme values to produce visible effects)
2. Verifies all 25 facets flow through PersonalityPromptBuilder (classification pipeline)
3. Applies stress mode → verifies shifted facet scores via EffectiveCognitiveDefaults (modulation pipeline)
4. Derives cognitive defaults from both resting and effective views → verifies derived parameters differ (derivation pipeline)
5. Verifies resting vs effective distinction for extended facets
6. Spot-checks multicollinearity: an agent with high Anxiousness + high Depressivity + high Perseveration should not produce implausible `fixationThreshold` values

### Unit Tests per CDE Method

For each derivation method that gains new facet rules, add test cases verifying:
- Facet at 0.5 (neutral) produces no shift
- Facet at 0.0 and 1.0 produces expected shift direction and magnitude
- Multiple correlated NA facets at extreme values produce a combined shift within reasonable bounds

## References

- [casehubio/neocortex#977] — PID-5 facets in situation classification
- [casehubio/neocortex#712] — Shadow archetypes / situational personality modulation
- [casehubio/neocortex#1055] — EffectiveCognitiveDefaults with tenant-scoped derivation
- Meehl 1975 — Hedonic capacity model (Anhedonia)
- Treadway & Zald 2011 — Motivational anhedonia (Trends in Neurosciences)
- Pizzagalli 2014 — Stress-induced anhedonia (mesolimbic DA)
- Beck 1967 — Cognitive triad (Depressivity)
- Scherer 2022 — Appraisal Bias Model (N=4859, Frontiers)
- Nolen-Hoeksema 1991 — Response Styles Theory (rumination)
- Nikolin 2021 — WM deficits in depression meta-analysis
- Joormann & Gotlib 2010 — WM updating deficit in depression
- Maier & Seligman 2016 — Learned helplessness neuroscience update (Psych Review)
- Davis & Nolen-Hoeksema 2000 — Ruminators and perseverative errors (WCST)
- Chamberlain 2006 — OCD cognitive flexibility deficits
- Xie 2019 — Perfectionism → perseverative cognition meta-analysis
- Stahl 2015 — Error monitoring ERPs and perfectionism (N=94)
- Vois 2026 — Perfectionism → emotion regulation (3-wave, N=454)
- Philp 2012 — Perfectionism → overcommitment → burnout mediation
- Martinussen 2005 — WM deficits in ADHD meta-analysis (d=0.85–1.06)
- Smith & Samuel 2016 — PID-5 Distractibility → ADHD (β=.55)
- Esterman 2014 — Sustained attention fluctuations (fMRI)
- Stolte 2022 — ADHD divergent thinking (Frontiers in Psychiatry)
- Downey & Feldman 1996 — Rejection sensitivity
- Stanton & Campbell 2015 — Attachment anxiety and rumination (JSPR)
- Mikulincer & Shaver 2003 — Hyperactivating attachment strategies
- Gasiorowska 2026 — Attachment anxiety → status striving (N=4,456)
- Trevisan 2019 — Alexithymia and interoception meta-analysis (66 samples)
- Preece 2022 — Alexithymia and emotion regulation (N=501)
- Credé 2017 — Grit-Conscientiousness meta-analysis (N=66,807)
- Connor-Smith 2007 — Personality and coping meta-analysis (N=33,094)
- Siddi 2017 — Schizotypy WM meta-analysis (67 studies)
- Ozdemir 2025 — Alexithymia-schizotypy meta-analysis
- Carson 2003 — Reduced latent inhibition and creativity
- Wang 2018 — Overinclusive thinking mediation
- Nelson & Rawlings 2010 — Schizotypy as predictor of creative experience
- Bereczkei 2014/2015 — Machiavellianism and cognitive flexibility
- Curran & Hill 2019 — Perfectionism rising with societal competitiveness (APA meta)
- Tiedens & Fragale 2003 — Dominance-submission complementarity
- Ashinoff & Abu-Akel 2021 — Hyperfocus criteria (PMC)
- Keinan 1994/2002 — Stress and magical thinking (Gulf War)
- Rónai 2026 — Disorganized schizotypy and stress-reactivity (Journal of Personality)
