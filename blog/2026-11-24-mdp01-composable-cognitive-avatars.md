---
layout: post
title: "Composable Cognitive Avatars"
date: 2026-11-24
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive-runtime, briefing, persona, composition, echo]
series: issue-1219-briefed-cognitive-avatars
---

# Composable Cognitive Avatars

The cognitive stack has had one altitude: full emergence. CognitionCore runs a tick loop, settles CAPS attractors, computes emotions, evolves personality over time. It works — agents genuinely develop character through experience. But it's heavyweight. A coaching avatar that helps you plan your week doesn't need emergent emotions. It needs to think, remember, have goals, and stay in character.

The question was whether we could get there without building a parallel system. The answer turned out to be architectural, not algorithmic.

## Briefing and emergence are orthogonal

I'd been thinking of "briefed mode" as a simpler version of "emergent mode" — the same stack with fewer features enabled. That framing was wrong. Briefing and emergence are orthogonal strategies for the same problem: shaping how an agent reasons.

The emergent branch has zero briefing. Identity emerges from CAPS attractors, personality evolution, accumulated experience. Session 100 is different from session 1 because the agent has changed.

The briefed branch has full briefing. "You are a stoic mentor. Think and respond through duty, through the long view, through what is within control." Identity is declared, not discovered. Session 100 sounds the same as session 1 — but the avatar remembers everything and its goals have progressed.

Both branches share the same infrastructure: MindMap for knowledge and goals, CaseMemoryStore for persistent memory, TemporalFocus for temporal awareness, CognitiveDefaultsRegistry for profile config. The infrastructure doesn't care which reasoning-shaping strategy sits on top.

## The echo mechanism

The three-layer briefing — identity, grounding, echo — comes from research we did in era 1 and era 3. The key finding: a good evocative echo ("Think and respond as a stoic mentor would — through duty, through the long view") keeps the persona consistent across hundreds of turns with no measurable decay. Mean expression scored 4.06 versus 3.54 baseline across 880+ evaluated events.

The critical constraint: prescriptive echo kills character. "Review your personality traits and respond accordingly" scored *below* the no-instruction control. The model performs worse when told to follow a checklist than when given no instruction at all. Each persona's echo needs careful evocative crafting — specific sentences that capture substance, not surface.

This isn't about speaking style. The stoic mentor doesn't just *sound* stoic — it prioritises duty over personal gain in its goal decomposition, focuses on what's within control when scoping tasks, and draws on the avatar's accumulated memories to ground advice in the specific person it's helping.

## Composable capabilities

The new `cognitive-runtime` module sits between `cognitive-index` and `cognition`. It provides a `CognitiveCapability` SPI — each cognitive function is a self-contained unit that produces prompt sections:

- **BriefingCapability** — renders the three-layer echo every prompt
- **GoalCapability** — queries the GOAL subgraph, filters and sorts by priority
- **TemporalCapability** — feeds MindMap nodes to TemporalFocus for now/yesterday/future awareness
- **MemoryCapability** — scans recent experience memories for context
- **EntityKnowledgeCapability** — resolves entities via CognitiveProfile
- **DispositionCapability** — renders disposition axes from the profile

`CognitiveAvatar` wires whatever capabilities are available. If MindMapStore isn't on the classpath, goal and temporal capabilities simply aren't wired — the avatar still works with just briefing. Each capability degrades independently.

The important thing: this list isn't a ceiling. Consolidation, practical appraisal (relevancy and urgency scoring), tick scheduling, inner thoughts, hierarchy of needs — all of these can be added as capabilities without touching the composition root. The architecture doesn't draw boundaries between "briefed" and "emergent" capabilities. Configuration defines what's composed, not the module structure.

## Interface segregation

`CognitiveLifecycle` had six methods. Three of them — `tick()`, `recordInteraction()`, `evaluateProactive()` — are meaningless for avatars without a tick loop. We extracted `CognitivePromptSource` as the narrower interface: `initialize()`, `promptSections()`, `contributeBlocks()`. CognitionCore still implements `CognitiveLifecycle`; CognitiveAvatar implements `CognitivePromptSource`. Consumers that work with both depend on the narrower type.

## What's next

Two follow-up items from the wrap review: unit tests for MemoryCapability and EntityKnowledgeCapability (#1233), and adding disposition axes to the persona profiles (#1234). Both are XS. The documentation batch (consumer guide, CLAUDE.md) is also pending.

The bigger question is what capabilities get composed in next. Consolidation — memory hygiene, goal resolution, experience graduation — is universal infrastructure, not emergent-specific. Any avatar with persistent memory benefits from it. And practical appraisal — the urgency and relevancy system that predates the emotion pipeline — belongs in the composable menu. An avatar that can tell you "your deadline for X is in 3 days and you haven't started the prerequisite" is more useful than one that just remembers your goals.
