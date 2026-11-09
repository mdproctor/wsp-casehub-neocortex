---
layout: post
title: "The Gap Between Wanting to Think and Being Able To"
date: 2026-11-09
entry_type: article
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive-architecture, intelligence, personality, search-budget, literature-grounded, capacity, deyoung, halford]
series: issue-802-hortora-corpus-extraction
---

# The Gap Between Wanting to Think and Being Able To

The search budget model has been through three layers now. The base layer (#825) gives each agent a personality-shaped exploration envelope — four parameters derived from PID-5 personality facets. The extreme interaction layer (#839) makes personality expression change under pressure — inverted-U activation, fatigue reallocation, the whole Yerkes-Dodson dynamics. Both model *motivation*: how much you want to explore, and how that wanting changes under stress.

Neither models *capacity*: how far that wanting can productively reach.

I kept treating this as the same thing. An agent with high Openness explores broadly — that's what the PID-5 derivation does, that's what the search budget renders into the prompt. But Openness is about wanting to explore. It says nothing about whether the agent can sustain a four-step reasoning chain or bridge a distant analogy.

Colin DeYoung's Big Five Aspect Scales make the split explicit. What most personality models call "Openness to Experience" is actually two distinct traits: **Openness** (aesthetic sensitivity, imagination, perceptual exploration) and **Intellect** (intellectual engagement, abstract reasoning, perceived intelligence). Nusbaum and Silvia (2011) proved the double dissociation cleanly: Openness predicts creativity but not fluid intelligence. Intellect predicts fluid intelligence but not creativity. These are empirically separate constructs.

The practical consequence for agent design: a high-Openness, low-Intellect agent *wants* to explore laterally but can't chain distant associations productively. The motivation is there; the cognitive capacity isn't. A high-Intellect, low-Openness agent *can* chain deep but doesn't pursue the connections. The capacity exists; the motivation doesn't. The current model collapses both into one dimension.

## Why Personality Models Can't Fix This

I initially looked for ways to derive capacity from existing personality data. Three candidates, all dead ends.

**PID-5 facets** measure maladaptive personality pathology — anxiousness, impulsivity, emotional lability. DeYoung et al. (2016) mapped PID-5 facets to the Big Five Aspect Scales and found that PID-5's Psychoticism cluster maps to the Openness aspect specifically. Intellect — a positive trait associated with cognitive ability — has no PID-5 counterpart. The instrument is structurally unable to represent it.

**Jungian cognitive functions** describe cognitive *style*, not capacity. High Ti (introverted thinking) means you prefer internal logical analysis. It does not mean you're good at relational reasoning. Using Ti as a proxy for reasoning capacity conflates what you prefer with what you can do — circular reasoning dressed as a derivation.

**Disposition axes** (ruleFollowing, riskAppetite, autonomy) are motivational constructs. Mapping ruleFollowing to depth capacity has no literature support. It would be engineering convenience, not grounded design.

Capacity is orthogonal to personality. It needs its own representation.

## Three Dimensions from the Literature

Each capacity dimension bounds a specific search budget parameter, grounded in a distinct research tradition:

**Relational complexity** (Halford et al. 1998) bounds depth. Halford's key finding: processing capacity is defined by the number of dimensions that can be related simultaneously. Unary relations have one source of variation, binary have two, ternary three. The empirical soft limit is quaternary — four interrelated variables held simultaneously. Beyond that, the mind segments and chunks, degrading quality. Fluid intelligence accounts for 80% of the age-related variance in this capacity. An agent with low relational complexity can follow a two-step reasoning chain but loses the earlier links by step four.

**Associative reach** (Mednick 1962) bounds laterality. Mednick's associative hierarchy theory: creative people have flatter hierarchies — more remote associations are accessible. Given the word "table", most people reach "chair" instantly. People with flat hierarchies also reach "leg", "food", "periodic", "water". The Remote Associates Test correlates with Raven's Progressive Matrices at r=0.38. Not pure intelligence, not pure creativity — a capacity that straddles both. An agent with low associative reach wants to make lateral leaps but lands in noise more often than signal.

**Working memory span** (Engle & Kane 2004) bounds breadth. Their two-factor theory: working memory capacity is fundamentally about attention control — maintaining representations in the face of interference and distraction. At low demand, everyone performs similarly. At high demand, individual differences emerge. WMC correlates with fluid intelligence at the latent level at r=0.72. An agent with low WM span starts strong with multiple threads but loses the earlier ones as cognitive load increases.

Convergence gets no ceiling. It models *when to stop and synthesize* — a personality-driven decision (Need for Cognitive Closure, conscientiousness), not a capacity limit.

## The Architecture That Follows

![Capacity ceiling position in the search budget pipeline](images/capacity-ceiling-pipeline.svg)

Capacity applies as a hard ceiling after all existing pipeline steps. The ceiling is a `Math.min()` — it only matters when motivation pushes the agent beyond their cognitive limits. Below the ceiling, capacity has zero effect. The agent operates normally.

The interesting signal isn't the capped value. It's the **gap** between what personality drives and what capacity allows:

```java
double depthGap = Math.max(0.0, depth - capacity.relationalComplexityOrDefault());
depth = Math.min(capacity.relationalComplexityOrDefault(), depth);
```

A large gap means the agent is frustrated by cognitive limits — high motivation, low capacity. This is the Openness/Intellect tension rendered as a runtime signal. The prose generator detects the gap and produces descriptions that convey the felt experience of reaching beyond your grasp:

> *"You can feel where your reasoning chain reaches its limit — three, four steps deep and the earlier links start to blur. You want to hold more of the argument in view at once, but the threads slip."*

An agent with no gap gets a different description entirely. Same codebase, same pipeline, different cognitive experience — because the model now distinguishes wanting from being able.

## Deriving Defaults Without Overclaiming

Capacity is a first-class parameter in the cognitive profile YAML. But most agents won't have explicit capacity specification, so the CDE needs a default derivation.

The Jungian cognitive functions are the best available proxy — weakly correlated, but directionally correct. Ti+Te (analytical functions) weakly predict relational reasoning capacity. Ne+Ni (intuitive functions) weakly predict associative hierarchy flatness. Te+Si (structured processing) weakly predict working memory management.

The critical design choice: compress the derivation range to [0.55, 0.95]. The Jungian-to-capacity correlation is r=0.3-0.4 at best. A derivation that produced extreme low values would be claiming "this personality profile makes you unintelligent" — an inference the data doesn't support. The compressed range provides moderate differentiation while being honest about the weakness of the mapping. Explicit YAML specification can use the full [0.0, 1.0] range when richer characterisation is warranted.

## Why This Matters Beyond Cognitive Agents

The Openness/Intellect split has implications beyond personality-shaped search. Cattell's Investment Theory (1987) says fluid intelligence (capacity) gets invested in learning over time, producing crystallised intelligence (knowledge). Higher capacity means more productive exploration means a broader knowledge base. This suggests capacity should eventually modulate *learning rate* in the memory subsystem — not just the search envelope.

`CognitiveCapacityConfig` sits on `CognitiveDefaults` at the top level, not nested inside `SearchBudgetConfig`, specifically to enable this. The search budget ceiling is the first application. Learning rate modulation is the natural second.

For agent builders: every personality model I've seen conflates motivation and capacity into a single dimension. The agent "is curious" or "is analytical" as a monolithic trait. The double dissociation says these are separate. An agent can be curious without being capable, or capable without being curious. The tension between the two — the gap — is where the most interesting cognitive character emerges.
