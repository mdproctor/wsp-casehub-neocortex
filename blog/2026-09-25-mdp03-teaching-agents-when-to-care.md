---
title: "Teaching agents when to care"
date: 2026-09-25
author: mdp
entry_type: note
subtype: diary
projects: [casehub-neocortex]
tags: [cognitive-architecture, attention, consolidation, goal-cognition]
status: draft
---

# Teaching agents when to care

Neocortex's consolidation scheduler has been running background cognitive
maintenance for weeks now — goal priority computation, decay detection, OCC
emotional appraisal, experience graduation, merge detection. Ten phases,
all producing useful insights about the agent's goal landscape. The problem:
nobody's listening. `ConsolidationCompleted` fires with success/failure per
phase, but the actual cognitive payload — "this goal just became urgent",
"that goal decayed to dormant", "a new goal was recognised from experience"
— stays locked inside the phase code. The agent finds out only when a human
prompt triggers the next cognitive tick.

For long-running agents, that gap can be hours.

## The design question

The issue (#381) sketched a "morning-wake" model: consolidation runs
overnight, the agent wakes to a briefing of what changed. I liked the
metaphor but not the implementation — scheduled briefings mean the system
pushes whether or not anything changed. The existing `SignificanceAccumulator`
already solves the "when to act" problem for triggering consolidation: per-tenant
accumulation, configurable threshold, CAS-guarded firing. The attention model
extends that same pattern: accumulate cognitive significance per principal,
fire when the threshold crosses.

The threshold itself adapts. When the P75 of active goal urgencies rises —
more goals approaching deadlines — the threshold drops. More cognitive
pressure means more sensitivity to changes. Quiet periods naturally raise
it. This felt right: the agent's attention density should scale with its
cognitive load, not with a clock.

## The wacky-manor insight

The design started with a standalone `CognitiveAttentionListener` in blocks
that would observe the neocortex CDI event and invoke the LLM directly.
Clean separation. Then I looked at how wacky-manor actually uses CognitionCore.

`ScenarioOrchestrator` calls `CognitionCore.tick()` at the start of every
autonomous game tick. CognitionCore already manages all cognitive state —
mood, drives, narrative, goals, inner life — and produces prompt sections
that `CharacterCognition` renders into the observation. Five characters,
each getting a personalised cognitive context every tick.

The attention model can't bypass this. If a push event fires and the
listener directly invokes the LLM, it's constructing cognitive context
outside CognitionCore — duplicating logic, missing state. CognitionCore
has to be the convergence point. Tick-based agents (wacky-manor) drain
the attention briefing on the next tick via `promptSections()`. Idle agents
drain it when the push receiver wakes them.

This led to a `CognitiveAttentionMediator` — an `@ApplicationScoped` CDI
bean that holds per-principal queues, since CognitionCore itself is a
manually-constructed POJO (no CDI annotations, four constructor overloads,
instantiated per-agent). The mediator bridges CDI events to CognitionCore
instances. The spec review caught this — I'd originally put the queue
on CognitionCore itself, which would have required CDI annotations on a
class that explicitly avoids them.

## Drain semantics

The spec review also caught a subtlety in the `ConsolidationPhase.signals()`
design. I'd proposed a default method that returns accumulated signals:

```java
default List<AttentionSignal> signals() { return List.of(); }
```

The problem: `ConsolidationScheduler.tick()` calls `beginTickAllPhases()`
once, then iterates tenants. Without drain semantics — where `signals()`
returns and clears — tenant B's call would include tenant A's signals.
Cross-tenant leakage. The fix: `signals()` returns a copy and clears
internal state. Each tenant gets only its own signals.

## What landed

Batch 1 of four: the foundational types. `AttentionSignal` (per-principal
change event with category and significance), `SignalCategory` (11 values
covering both neocortex and blocks phases), `AttentionBriefing` (ranked
signal payload with urgencyP75), `CognitiveAttentionRequired` (CDI event
at the neocortex-to-blocks boundary). Plus `ConsolidationPhase.signals()`
as a backward-compatible default method, `CognitiveDefaultsRegistry.allAgentIds()`
for principal discovery, and a GoalUrgency clamp fix on two unclamped
fallback paths that could return values outside [0,1].

Three batches remain: the accumulator itself (per-principal state,
adaptive threshold, dedup, minimum interval guard), phase signal production
across six neocortex phases, and the integration test proving the full
pipeline.

## The blocks#303 alignment

This design is deliberately post-#303. That issue migrates all cognitive
state orchestrators (mood, drive, narrative, etc.) from blocks to neocortex.
Post-migration, those orchestrators can emit attention signals directly to
the accumulator — same module, no CDI boundary. The current design works
either way: blocks phases implement neocortex's `ConsolidationPhase` SPI
and produce signals through the same `signals()` method. But after #303,
the whole attention pipeline lives in one layer. Cleaner.

The direction is clear: wacky-manor should get thinner. `CognitiveBudget`,
the manual consolidation phase wiring in `ManorConsolidationBeans`, the
belief/trust/norm rendering in `CharacterCognition` — all of this belongs
in the platform. The attention model is designed so that CognitionCore's
attention-aware section gating replaces app-level budget management.
The game code provides game objects, action descriptors, and scenario
rules. The cognitive infrastructure is the platform's job.
