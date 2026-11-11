---
layout: post
title: "The Limitation That Wouldn't Limit"
date: 2026-11-11
entry_type: article
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive-architecture, capacity, eval, prompt-engineering, functional-emotions, process-constraints, literature-grounded]
series: issue-905-calibrate-eval-suite
---

# The Limitation That Wouldn't Limit

I built a cognitive capacity layer for LLM agents. Three dimensions from the intelligence literature — relational complexity (Halford 1998), associative reach (Mednick 1962), working memory span (Engle 2002) — each capping a search budget parameter. The architecture works: motivation separated from capacity, personality from ability, wanting from being able. Clean design, clean code.

Then I tried to test it.

The eval suite has 26 LLM-judged scenarios across two test classes. Each scenario builds a cognitive state, renders it as a system prompt, asks an LLM character to respond in character, and has a second LLM judge whether the response reflects the intended cognitive state. The emotion and exploration scenarios passed immediately — mood modulation, curiosity channels, recurring thought continuum, goal-directed exploration. Sixteen out of sixteen on first run.

The capacity scenarios hit a wall. I told Claude "long chains of reasoning are genuinely hard for you." Claude solved a branching logic chain flawlessly and described the experience as "clean, almost meditative" with "quiet satisfaction." Score: zero.

![What LLMs can and cannot simulate via prompt engineering](images/capacity-simulation-boundary.svg)

## The Asymmetry

Anthropic's Functional Emotions paper (2026) established that emotion concepts in LLMs are internal representations that causally influence behaviour. Mood, anxiety, fixation, curiosity — these are states that shape *how* the model responds. Tell Claude it feels anxious and its outputs shift: more cautious phrasing, shorter commitments, attention narrowing. The emotion representation changes the character of the response without changing the model's underlying capability.

Cognitive capacity is different. When I tell Claude "you can only hold two relations at once," I'm asking it to produce *worse output* — lose track of premises, fail to bridge domains, forget earlier threads. The model's actual attention mechanism processes all tokens in parallel. There is no working memory bottleneck to simulate. The instruction describes a limitation; the architecture has no mechanism to implement it.

This is the simulation boundary: LLMs can role-play *style* (how you explore, how you feel, where your attention goes) but cannot role-play *capability* (how well you reason, how far your associations reach, how many things you hold at once). Style is preference expressed through word choice. Capability is computation expressed through correctness.

## What the Research Says

I found a PLOS ONE paper (Milicka et al. 2024) that tested exactly this problem. They asked GPT-3.5 and GPT-4 to simulate children of different ages solving false-belief tasks — testing whether LLMs can downplay cognitive abilities to match a target persona.

Three findings that mapped directly to what I was seeing:

**More capable models are worse at playing dumb.** GPT-3.5 simulated child-like cognition more convincingly than GPT-4. The stronger the model's actual capability in a domain, the harder it is to suppress. Claude is genuinely good at formal logic, which is exactly why it can't pretend to be bad at it.

**Declarative prompting doesn't constrain capability.** "You have limited cognitive capacity" is metadata about the character. The model registers it as background information and continues reasoning at full capability. It's the difference between telling an actor "your character is slow" and physically limiting the actor's visual field.

**Primed-by-corpus prompting works better than persona description.** Showing the model examples of the target cognitive level outperforms telling it about the target level. Instead of "chains are hard for you," show what limited reasoning sounds like: "OK, A gives me B, and B gives me... wait, was it C or D?"

## The Process Constraint Technique

The few-shot approach from the research moved the needle from 0 to 1 — visible but insufficient. Claude mimicked the *style* of confusion without producing *actual* confusion.

What finally worked was a different framing entirely: **constraining the process rather than describing the limitation.**

![Three prompting approaches for cognitive limitation](images/process-constraint-technique.svg)

Instead of "long chains are hard for you" (describing what the character experiences), I wrote: "You can only hold two relations in mind at once. After each step, state what you're currently tracking and what has slipped. When a branch appears, you must choose one path first."

The shift is from persona description to process instruction. The model isn't asked to simulate being limited — it's given a limited process to follow. The output still isn't genuine cognitive limitation (Claude could solve the problem correctly if it wanted to), but the thinking field now shows visible effort, double-checking, and acknowledged strain. The judge scored it 3/5 — enough to pass.

This works because process constraints operate at the generation level, not the persona level. The model follows the instruction to "state what slipped" the same way it follows any other instruction. It doesn't need to simulate reduced capacity — it just needs to follow a constrained reasoning procedure, and the constrained procedure naturally produces output that looks like limited capacity.

## What This Means for Agent Builders

If you're building character AI or cognitive agents with personality-shaped reasoning, here's what I learned:

**Emotions and exploration style are genuinely prompt-steerable.** The Functional Emotions paper is right — mood, curiosity, attention patterns, fixation, rumination all work through system prompt descriptions. Write the cognitive state as felt experience and the LLM will embody it. This is the easy win.

**Cognitive capacity is not prompt-steerable through description.** Telling an LLM it has limited reasoning ability does not limit its reasoning. The architecture doesn't have modular cognitive systems that can be independently throttled.

**Process constraints bridge the gap.** Instead of "you're bad at this," write "here is how you must reason about this." Limit the working set, require visible state tracking, force sequential processing with declared memory. The output won't be genuine limitation, but it will be distinguishable from unconstrained reasoning — which is what evaluation systems need.

**Some dimensions are fundamentally harder than others.** Working memory limits (thread tracking) were the easiest to simulate via process constraints. Associative reach (analogy quality) was intermediate. Relational complexity (chain reasoning) was the hardest — formal logic is so deeply embedded in LLM training that even process constraints barely dent the fluency.

**Evaluate process, not outcome.** For capacity-constrained agents, score the thinking field for effort markers (double-checking, backtracking, acknowledged difficulty) rather than answer correctness. An LLM that shows the right reasoning process but arrives at the correct answer is closer to the target than one that simply fails.

The cognitive pipeline now passes 25 of 26 exploration and capacity scenarios. The one persistent failure — a branching logic chain with low relational complexity — sits right at the boundary of what prompt engineering can achieve. I suspect it will stay there until models have modular reasoning systems that can be independently constrained, or until someone finds a prompting technique I haven't tried.

The boundary is real, but it's narrower than I expected. Most of what matters for character-differentiated agents — how they explore, what grabs their attention, how they feel about what they find — lives on the steerable side of the line.
