---
layout: post
title: "Personality Shapes How Agents Cope"
date: 2026-11-16
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [coping, personality, big-five, pid-5, ema, cognitive-architecture, connor-smith]
series: issue-595-coping-strategies
---

# Personality Shapes How Agents Cope

Two characters face the same crisis. One plans an escape route. The other shuts down and waits for it to pass. Both responses are psychologically coherent — they follow directly from personality. The question is whether a cognitive agent architecture can produce that differentiation mechanically, without asking an LLM to improvise every time.

We built two pieces this session that answer that question: a personality-to-coping derivation engine, and a mechanical predictor that selects coping strategies from the EMA taxonomy. The LLM is still involved — it resolves ties and generates the reinterpretation narrative — but the structural selection is personality-driven and deterministic.

## Why Coping Needs Its Own Layer

Emotion regulation already exists in the pipeline. It takes an emotion and decides how to modulate it — reappraise, suppress, redirect, seek social support. The Gross process model gives us that. But regulation answers the wrong question for agents in narrative situations.

Regulation asks: *how do I feel less of this?*
Coping asks: *what do I do about the situation that caused it?*

Lazarus and Folkman drew this distinction in 1984. Marsella and Gratch formalised it for computational agents in 2009 with the EMA model. Coping operates on the situation appraisal — controllability, adjustability, relevance — not just the emotion. A highly controllable stressor calls for planning and confrontation. An uncontrollable one calls for acceptance or avoidance. The emotion type is a downstream signal, not the primary input.

The existing `RegulationStrategyPredictor` uses emotion categories as a proxy for controllability — ANGER means controllable, FEAR means uncontrollable. That proxy works, but it's indirect. The Scherer appraisal already computes SEC dimensions that include controllability directly. The coping predictor uses those dimensions instead.

## Deriving Coping Tendencies from Personality

Connor-Smith and Flachsbart published a meta-analysis in 2007 covering the relationship between Big Five personality traits and coping strategies. The correlations are modest but consistent:

- **Conscientiousness → problem-focused coping** (r = .21) — planful people plan
- **Neuroticism → avoidant coping** (r = .25) — anxious people disengage
- **Openness → positive reinterpretation** (r = .11) — open people reframe
- **Agreeableness + Extraversion → social support seeking** (r = .11, .14) — prosocial people reach out
- **Low Neuroticism → acceptance** (1 - N) — calm people accept what they can't control

The CDE (Cognitive Derivation Engine) already derives cognitive defaults from PID-5 personality facets — it does this for regulation, appraisal weights, search budgets, and a dozen other subsystems. Adding coping defaults follows the same pattern.

The challenge: the CDE operates on PID-5 facets (Anxiousness, Impulsivity, Callousness, Withdrawal, etc.), not Big Five dimensions directly. But Big Five composites from PID-5 facets are already established in the codebase — conscientiousness is derived from rule-following disposition plus inverse impulsivity, openness from inverse withdrawal plus inverse suspiciousness plus risk-taking. The same composites that drive recurring thought thresholds and search budget parameters now drive coping tendencies.

```java
public record CopingDefaults(
    double planfulTendency,
    double reinterpretationTendency,
    double avoidanceTendency,
    double supportSeekingTendency,
    double acceptanceTendency
) {}
```

Five numbers. Each derived from personality. Each consumed mechanically downstream. No LLM involved in the derivation.

## The Predictor: Six Stages, No Inference Calls

The `CopingStrategyPredictor` takes those five numbers plus the situation's controllability and the character's emotional state, and narrows 16 possible EMA coping strategies down to one — or to a family with a hint.

![CopingStrategyPredictor pipeline — six stages from inputs to prediction](svg/coping-predictor-pipeline.svg)

The six stages, in order:

**Cognitive load gate.** Under high cognitive load, complex strategies are unavailable — you can't plan an elaborate response when your working memory is saturated. The predictor filters to low-cost strategies: suppression, avoidance, disengagement, resignation. This migrates directly from the regulation predictor, where the same constraint applied to regulation strategy selection.

**Controllability filter.** High controllability (> 0.6) restricts to intention-category strategies — planning, confrontation, seeking support. Low controllability (< 0.3) restricts to belief and desire categories — reinterpretation, acceptance, denial, wishful thinking. Medium controllability leaves all strategies viable. This is the core EMA insight: coping is situation-adaptive, not personality-fixed.

**Mild distress override.** If the emotion intensity is below 0.40 and the emotion type is uncontrollable (fear, distress), the controllability filter is skipped. Mild uncontrollable distress doesn't warrant avoidance — a slight anxiety about an uncertain outcome shouldn't lock out problem-focused strategies.

**Self-conscious emotion refinement.** Shame and remorse trigger a specific pattern from Nathanson's 1992 compass of shame: avoidant personalities withdraw. If the dominant emotion is self-conscious and the character has high avoidance tendency (> 0.6) or an avoidant conflict mode, the predictor pins AVOIDANCE with high confidence and exits early. This preserves a behavioural signature that would otherwise be lost in the general personality resolution.

**Personality bias resolution.** Among the surviving strategies, which personality dimension dominates? If planful tendency is highest and PLANNING is viable, the predictor selects PLANNING. But multiple strategies can map to the same dimension — PLANNING and ACTIVE_CONFRONTATION both map to planful tendency. When that happens, confidence drops and the output includes a family label. The LLM resolves within-family ties using situational context.

**Output.** A `CopingPrediction` with a strategy, a confidence score, and an optional family label. High confidence (0.75) means the personality signal is clear and the predictor is pinning a specific strategy. Lower confidence (0.55) means the predictor is suggesting a direction but leaving the final choice to the LLM.

## What This Enables

The same crisis — a collapsing plan, a betrayal, an uncontrollable threat — now produces different coping responses from different characters, without any per-character prompt engineering. A high-conscientiousness character plans. A high-neuroticism character avoids. A high-openness character reframes. The differences emerge from the personality profile that was derived at character creation, flow through the CDE, and resolve mechanically in the predictor.

The LLM's role shifts from "decide what this character would do" to "generate the narrative for the decision that was already made." That's a significant reduction in the semantic load on each inference call, and it means the coping response is reproducible across runs with the same personality profile.

This is two of ten tasks in the coping strategies epic. What comes next: the LLM generation phase that produces reinterpretation narratives, the micro-loop that iterates until emotions converge, and the CAPS attractor integration that lets characters learn from their coping history.

The architecture is heading toward a place where personality drives behaviour at every level — from what you notice, to how you appraise it, to how you cope with it, to how you regulate what's left. Each layer is mechanical where signals are already resolved, and LLM-based where semantic context is genuinely needed. Coping slots into that boundary cleanly.
