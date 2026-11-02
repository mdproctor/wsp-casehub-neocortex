---
title: "Sixteen characters, one mind"
date: 2026-11-02
author: mdp
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
series: cognitive-pipeline-wiring
tags: [cognitive-architecture, eidos, personality-derivation, memory-modulation, agent-design]
---

# Sixteen characters, one mind

Continues from [Who your body remembers](2026-11-02-mdp03-who-your-body-remembers.md).

---

I noticed it while reviewing the cognitive pipeline wiring. Sixteen Manor characters. Each defined through eidos with unique disposition axes — social orientation, risk appetite, rule-following, autonomy, conflict mode. Jungian function profiles. Goals and constraints that shape every dialogue choice. Rich, distinct personalities.

Under the hood, every character thinks with the same brain.

CognitionCore runs. Prompt sections render — mood, drives, appraisal, salience. The pipeline is wired and functional. But `CognitiveDefaultsRegistry` is empty. No cognitive profiles exist. Every mood baseline is zero. Every curiosity weight is the default. When Muttley retrieves memories, the scoring is identical to Penelope Pitstop's. The personality data stops at eidos. It never reaches cognition.

## The derivation engine was waiting

`CognitiveDerivationEngine` exists for exactly this gap. It takes a `DescriptorView` — disposition axes, a Jungian function profile, goals — and derives cognitive parameters through ten pathways, each grounded in published research:

- **Disposition profile → personality weights** — which memory domains surface first
- **Disposition axes → mood baseline** — where the character's emotional resting state sits in pleasure-arousal-dominance space
- **Disposition + goals → curiosity configuration** — what counts as interesting
- **Goals → temporal focus** — how far the character's attention reaches
- **Rule-following + risk appetite → CBR strategy** — how similar is "similar enough" for case-based reasoning
- **Social orientation + conflict mode → social cognition** — trust formation speed, conflict interpretation
- **Disposition profile → graph structure** — whether the character connects knowledge or categorises it
- **Disposition profile → extraction bias** — what gets noticed in conversation
- **Disposition profile → appraisal weights** — emotional reactivity to events
- **Risk appetite + rule-following → habituation** — how quickly novelty fades

The eidos descriptors map one-to-one onto the inputs. `AgentDisposition` carries the same five axes as neocortex's `DispositionAxes`. The disposition profile is the same weighted term list. The goals are the same strings. The derivation engine was built for this data. Nobody had connected the pipe.

![Eidos to cognitive derivation pipeline](images/eidos-cognitive-derivation.svg)

## Why a bridge, not a config file

The obvious solution is YAML. Write sixteen `cognitive-profiles/*.yaml` files, one per character, with hand-authored personality weights and mood baselines. The cognitive engine already loads them. Ship it.

The problem is drift. The personality data already lives in eidos — disposition axes, function profiles, goals. A YAML cognitive profile is a second source of truth for the same character. Change a character's risk appetite in eidos and forget to update the YAML? The character's dialogue shifts but its cognitive parameters don't. It says bold things and then retrieves memories like a conservative. The inconsistency is silent — no test catches it, no compile error flags it, because the two files never reference each other.

The alternative is making eidos depend on neocortex directly. Then eidos could produce cognitive profiles itself. But that inverts the dependency — identity should not know about cognition. Eidos defines who a character is. Cognition defines how a character thinks. Those are different concerns with different change rates.

A bridge module sits between them. `cognitive-eidos` depends on both `casehub-eidos-api` and `casehub-neocortex-cognitive-index`, but neither depends on the bridge or on each other. It's a single CDI bean. At startup, it reads each character's eidos `AgentDescriptor`, converts it to a `DescriptorView`, and calls `CognitiveDerivationEngine.derive()`. The resulting `CognitiveDefaults` are registered with `CognitiveDefaultsRegistry.register()` — a method that already existed but had no callers outside test fixtures.

The bridge is pure mapping. No business logic, no state. It converts types from one system into types the other system expects. Any project that has eidos on its classpath can add `cognitive-eidos` and get derived cognitive profiles for free — no YAML authoring, no maintenance, no drift.

`deriveAndMerge()` overlays explicit values on the derived base. A character who needs a hand-tuned curiosity config that diverges from what derivation produces can still get one — a YAML override wins. The defaults are calculated, not imposed.

## What changes when characters remember differently

This is where it becomes practical.

`AgentExperienceService.recall()` currently queries `CaseMemoryStore` directly. Every character gets the same memory scores. Personality-weighted retrieval — `CognitiveMemoryRetriever` — exists on the classpath but nobody calls it. The routing change is straightforward: recall goes through the retriever, which applies `ModulationFactor` chains that include domain weighting from the character's personality weights.

A character with high experience weight surfaces experience memories. One with high relationship weight surfaces interaction histories. Same memory pool. Different ordering. The ordering determines what appears in the context window and what gets truncated.

![How personality weights shape memory retrieval](images/personality-modulated-retrieval.svg)

Consider two characters encountering the same person entering a room. Muttley — high experience weight, low relationship weight — recalls what happened last time: the prank, the chase, the consequence. Penelope — high relationship weight, high reflection weight — recalls how the relationship has developed: the warmth in the garden, her belief about trust between them.

Neither is filtering. The modulation changes scores, not availability. But the difference in what surfaces first shapes what the character thinks about, which shapes what it says, which shapes what it feels about the person in the room.

This is the practical difference between a reskinned agent — same prompt, different name — and one whose personality runs deep enough to change what it notices.

## Identity as cognition

Most multi-agent systems treat personality and cognition as separate configurations. A character sheet says "bold and impulsive." A retrieval config somewhere else says "similarity threshold: 0.85, temporal decay: moderate." Nobody checks whether those two descriptions of the same character agree. When they don't — and they will, because they're maintained by different people at different times — the character contradicts itself in ways that are hard to diagnose. The dialogue sounds bold. The memory retrieval acts cautious. The agent feels incoherent and nobody knows why, because the inconsistency lives across two files that never reference each other.

Derivation eliminates the category. There is no "cognitive config" to maintain. There is identity, and everything else follows. Change a character's risk appetite in eidos, and its CBR similarity threshold adjusts. Change its social orientation, and trust formation rate follows. The mapping is deterministic, auditable, and — importantly — reversible: given a character's cognitive parameters, you can trace every value back to the specific disposition axis or function weight that produced it.

That traceability matters when you're debugging behaviour. "Why did this character retrieve relationship memories first?" Because its disposition profile weights Fe at 0.9, which the derivation engine maps to high relationship domain weight. Not because someone typed `relationship: 1.6` into a YAML file six months ago and forgot why.
