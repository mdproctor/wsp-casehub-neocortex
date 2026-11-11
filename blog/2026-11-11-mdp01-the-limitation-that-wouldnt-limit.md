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

There's a deeper reason this fails. RLHF gives LLMs a massive "helpful/optimal" prior. The model has been trained, extensively, to produce the best possible answer. Telling it to be suboptimal is like telling a supercomputer to "try harder to be slow" — it will simulate the aesthetics of slowness while computing at full speed. The model's training objective actively fights the persona instruction.

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

## The Cognitive Sandbox

The process constraint technique generalises into an architectural pattern. Stop treating the LLM as a roleplayer. Treat it as a constrained engine wrapped in three layers:

**State Tracker** — an external system that holds variables the LLM is bad at tracking on its own: fatigue level, habituation count, available working memory slots, strategy cost budgets. In our pipeline, this is `CognitiveResourcePool` for fatigue, `HabituationState` for exposure counts, `DriveOrchestrator` for motivational profile. The state tracker is deterministic code, not LLM inference.

**Constraint Injector** — a pre-processing step that reads the state tracker and modifies the prompt accordingly. Not by describing the state ("you are fatigued") but by restricting the reasoning procedure: deleting context, restricting the strategy menu, capping reasoning steps, or forcing a specific heuristic. In our pipeline, this is `SearchBudgetPromptSection` and the capacity trait renderer. This is where the process constraint technique lives.

**Engine** — the LLM itself. It executes the constrained process. It doesn't need to pretend to be tired or limited. The prompt literally doesn't contain the information or computational freedom required to be "smart." The limitation is real, not simulated.

The same pattern applies beyond capacity. For emotion regulation: don't ask the LLM which strategy to use — restrict the available strategies based on the trait profile. "High neuroticism + high extraversion → only suppression or distraction available. Reappraisal is not in the menu." For fatigue: maintain an explicit effort counter that increments with each multi-step inference, and gate strategy complexity on the counter value. For personality differentiation: replace trait labels ("act with high conscientiousness") with trait process rules ("you must generate a concrete plan, check it against a standard, and express discomfort if the plan is incomplete").

The golden rule: if you want an LLM to exhibit a human limitation, do not ask it to simulate the limitation. Impose the limitation on the prompt's information, structure, or reasoning procedure, and let the LLM do its best within those narrowed bounds.

## What This Means

The cognitive pipeline now passes 25 of 26 exploration and capacity scenarios. The one persistent failure — a branching logic chain with low relational complexity — sits right at the boundary of what prompt engineering can achieve. Formal logic is so deeply embedded in LLM training that even process constraints barely dent the fluency.

Working memory limits (thread tracking) were the easiest to simulate via process constraints. Associative reach (analogy quality) was intermediate. Relational complexity (chain reasoning) was the hardest. Some dimensions are fundamentally harder because the model's actual capability in that domain is stronger.

For evaluation: score the thinking field for process compliance (double-checking, backtracking, acknowledged difficulty, slot tracking) rather than answer correctness. An LLM that follows the constrained procedure but arrives at the correct answer is closer to the target than one that simply fails.

The boundary is real, but it's narrower than I expected. Most of what matters for character-differentiated agents — how they explore, what grabs their attention, how they feel about what they find, which strategies they reach for — lives on the steerable side of the line. The Cognitive Sandbox pattern extends the steerable region further than description alone ever could.
