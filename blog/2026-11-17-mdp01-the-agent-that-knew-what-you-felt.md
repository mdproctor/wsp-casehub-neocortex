---
layout: post
title: "The Agent That Knew What You Felt"
date: 2026-11-17
entry_type: article
subtype: diary
projects: [casehubio/neocortex]
tags: [cognition, theory-of-mind, bayesian-inference, trust-evolution, appraisal, scherer, bdi, mental-model, two-channel]
series: cognitive-pipeline
---

# The Agent That Knew What You Felt

The Theory of Mind engine has existed in `mindmap-intelligence/tom/` for months. Three-node Bayesian network — Threat → EmotionalState → Behavior — grounded in Scherer's appraisal theory, passing all its unit tests. Zero production callers. The observation builder had the API. The inference worked. Nobody called it.

Meanwhile, `CognitionCore.tick()` already loops over every subject the agent knows about, updates the BDI mental model (what the agent believes the other person thinks, wants, and intends to do), and moves on. The qualitative channel was live. The quantitative one was sitting in a drawer.

This session wired them together.

## Two channels, one read

An agent's understanding of another character now has two complementary channels:

**Qualitative:** LLM-inferred BDI — beliefs, desires, intentions extracted from conversation signals. "She believes the alliance is fragile." "He intends to claim the contested territory." These are rich, contextual, and expensive to compute. They update on each `mentalModel.tick()` and require LLM inference when enough signals accumulate.

**Quantitative:** Bayesian posterior — a probability distribution over emotional states (positive, neutral, distressed) inferred from the agent's own appraisal of the situation. This costs nothing — it's a small junction-tree inference on three variables, resetting per subject. It runs every tick, every subject.

The two channels answer different questions. The BDI channel answers *what do you think they want?* The Bayesian channel answers *how do you think they feel about what's happening?* An agent can infer "she wants to cooperate" (BDI) but also "she's 72% distressed about the current situation" (Bayesian). Both are useful. Neither subsumes the other.

## The bridge: appraisal → evidence → posterior

The existing `TheoryOfMindEngine` takes two pieces of evidence and produces a posterior. The question is where the evidence comes from.

The appraisal system already computes Scherer's SEC dimensions (stimulus evaluation checks) every tick — relevance, conduciveness, controllability, urgency, novelty. These are the agent's own evaluation of the situation. `TheoryOfMindBridge` maps two of them into the Bayesian network:

**Threat level** from conduciveness and controllability. Goal incongruence (inverse of conduciveness) combined with low coping power (low controllability) produces threat. The mapping is smooth — soft probability distributions, not hard thresholds — so a mildly incongruent situation with moderate controllability produces a spread across NONE/MILD/SEVERE rather than a crisp assignment. This matters because Bayesian inference on hard evidence throws away uncertainty.

**Behavior type** from action tendencies. The appraisal system also produces action readiness — APPROACH, AVOIDANCE, ATTENDING, DOMINANCE, SUBMISSION, and so on. The bridge groups these into approach-like, avoidant-like, and neutral-like, weighted by intensity. Again, soft evidence. An agent showing 60% approach and 30% avoidance produces a behavior distribution of roughly [0.67, 0.0, 0.33], not a hard APPROACH.

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 540 220" style="max-width:540px;font-family:system-ui,sans-serif">
  <rect width="540" height="220" fill="#fafafa" rx="6"/>
  <!-- SEC box -->
  <rect x="20" y="30" width="120" height="60" rx="4" fill="#dbeafe" stroke="#93c5fd" stroke-width="1.5"/>
  <text x="80" y="55" text-anchor="middle" font-size="11" font-weight="600" fill="#1e40af">SEC Dimensions</text>
  <text x="80" y="70" text-anchor="middle" font-size="9" fill="#3b82f6">conduciveness</text>
  <text x="80" y="80" text-anchor="middle" font-size="9" fill="#3b82f6">controllability</text>
  <!-- Action box -->
  <rect x="20" y="120" width="120" height="60" rx="4" fill="#dbeafe" stroke="#93c5fd" stroke-width="1.5"/>
  <text x="80" y="145" text-anchor="middle" font-size="11" font-weight="600" fill="#1e40af">Action Tendencies</text>
  <text x="80" y="160" text-anchor="middle" font-size="9" fill="#3b82f6">approach / avoidant</text>
  <text x="80" y="170" text-anchor="middle" font-size="9" fill="#3b82f6">intensity-weighted</text>
  <!-- Bridge box -->
  <rect x="190" y="60" width="100" height="80" rx="4" fill="#fef3c7" stroke="#fbbf24" stroke-width="1.5"/>
  <text x="240" y="92" text-anchor="middle" font-size="11" font-weight="600" fill="#92400e">ToM Bridge</text>
  <text x="240" y="108" text-anchor="middle" font-size="9" fill="#b45309">soft evidence</text>
  <text x="240" y="120" text-anchor="middle" font-size="9" fill="#b45309">mapping</text>
  <!-- Bayes box -->
  <rect x="340" y="60" width="100" height="80" rx="4" fill="#d1fae5" stroke="#6ee7b7" stroke-width="1.5"/>
  <text x="390" y="88" text-anchor="middle" font-size="11" font-weight="600" fill="#065f46">Bayesian</text>
  <text x="390" y="103" text-anchor="middle" font-size="11" font-weight="600" fill="#065f46">Network</text>
  <text x="390" y="118" text-anchor="middle" font-size="9" fill="#059669">3-node junction</text>
  <text x="390" y="130" text-anchor="middle" font-size="9" fill="#059669">tree inference</text>
  <!-- Posterior box -->
  <rect x="470" y="75" width="55" height="50" rx="4" fill="#fce7f3" stroke="#f9a8d4" stroke-width="1.5"/>
  <text x="497" y="97" text-anchor="middle" font-size="10" font-weight="600" fill="#9d174d">P(E)</text>
  <text x="497" y="112" text-anchor="middle" font-size="8" fill="#be185d">posterior</text>
  <!-- Arrows -->
  <line x1="140" y1="60" x2="186" y2="80" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="140" y1="150" x2="186" y2="120" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="290" y1="100" x2="336" y2="100" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <line x1="440" y1="100" x2="466" y2="100" stroke="#6b7280" stroke-width="1.5" marker-end="url(#arr)"/>
  <defs>
    <marker id="arr" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
      <path d="M0,0 L8,3 L0,6" fill="none" stroke="#6b7280" stroke-width="1"/>
    </marker>
  </defs>
</svg>

The engine creates a fresh network per inference call — three nodes, cheap — so there's no shared mutable state between concurrent agent ticks. I found this during code review: the original design reused a single engine instance with `reset()` between subjects. That's safe within a sequential subject loop but not across concurrent `tick()` calls for different agents. Fresh-per-call eliminates the race.

## Trust that listens to intent

The second piece: feeding BDI into trust evolution.

`RelationalSchemaEvolutionPhase` computes trust from observed interaction memories — positive interactions increase trust, negative ones decrease it. Personality conditions the rates: callousness dampens positive trust gain, avoidance caps the ceiling, conflict-interpretation style amplifies or absorbs negative valence.

The gap: an agent could infer "this person intends to deceive me" (BDI mental model, high confidence) and the trust score wouldn't move. Trust only evolved from direct observations. Inference was ignored.

The fix connects them. After computing the observation-driven trust delta, the phase looks up the mental model for the subject. If the BDI snapshot contains hostile intent (deception, manipulation, betrayal) with confidence ≥ 0.5, the trust delta is biased negative. If it contains cooperative intent (help, support, collaboration), the bias is positive.

The asymmetry is deliberate. Hostile bias is 3× the cooperative bias. Trust is lost quickly and earned slowly — a well-established pattern in social psychology (Slovic 1993; asymmetric dominance of negative events in trust formation). An agent that infers deception doesn't just withhold trust — it actively withdraws it.

Desires count at half the weight of intentions. Wanting to exploit is weaker evidence than planning to exploit. The classification operates on the already-extracted BDI keys and descriptions — structured output from the LLM inference, not raw text. This is the mechanical-over-keyword boundary: the LLM resolved the semantics, the keyword match operates on its output.

## The prompt surface

The posterior appears in the agent's prompt alongside the BDI text, but only when the dominant emotional state exceeds 60% confidence. Below that threshold the signal is too uncertain to be actionable — the agent has a vague read but nothing worth attending to.

When it fires, the prompt renders a one-line emotional read:

```
Theory of Mind (bob):
  What you believe about the user:
    - Values universal energy (confidence: 0.8)
  What you think they want:
    - Recognition for AC work (confidence: 0.7)
  Their likely intentions:
    - Build the Wardenclyffe tower (confidence: 0.5)
  Inferred emotional state (Bayesian):
    - positive: 15%, neutral: 25%, distressed: 60% → likely distressed
```

Two complementary reads. The BDI tells the agent *what* the other person is thinking. The Bayesian posterior tells it *how they feel about the situation*. The first is LLM-rich and context-dependent. The second is mechanically derived and always available.

## What remains

The CPTs (conditional probability tables) in the Bayesian network are fixed — the same tables for every agent. A callous agent and an empathic one run the same inference. Personality-modulated CPTs, where an agent's own disposition conditions the priors and likelihood tables, is the next step. The gap mapping moved Theory of Mind from "Absent" to "Foundational" but the personality-aware gap remains.

The keyword-based intent classifier (hostile vs. cooperative) has known false-positive risk — "helpless" matches the cooperative pattern "help", "distrust" matches "trust". I added negative exclusions for the obvious ones, but the approach is inherently fragile. A cleaner design would use the BDI dimension's own semantic extraction rather than post-hoc keyword matching. For now it works because the BDI keys are already LLM-structured, but it's a known seam.

Three issues closed, one engine activated, two channels feeding the prompt, trust evolution that listens to what the agent thinks you're planning. The machinery was already there. It just needed connecting.
