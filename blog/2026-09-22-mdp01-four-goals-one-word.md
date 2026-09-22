---
title: "Four goals, one word"
date: 2026-09-22
author: mdp
tags: [architecture, goals, cross-repo, eidos, engine, blocks, desiredstate, neocortex]
entry_type: note
subtype: diary
series: issue-345-goal-cognition
projects: [casehubio/neocortex]
---

I wanted to add goal cognition to neocortex — recognition from experience, dependency tracking, affective valuation, prioritisation. Epic #345 lays out seven scope areas backed by BDI research and the existing cognitive infrastructure. Straightforward, I thought. Build on MindMap, wire into curiosity signals, use the consolidation phase pattern.

Then Claude started tracing `GoalSignalStore` consumers and I realised I didn't actually know where goals lived in this platform.

## The audit

We opened a workspace across six repos — platform, eidos, engine, blocks, desiredstate, neocortex — and used IntelliJ's semantic search to find every class with "Goal" in its name. The count was sobering. Engine alone returned 141 matches. Blocks had 65. Desiredstate 16. Eidos 32.

The word "goal" appears everywhere, meaning four different things.

**Eidos** defines `AgentGoal` — a standing objective on an agent's descriptor. Name, description, priority (PRIMARY or SECONDARY), visibility. Identity metadata. The original design spec (issue-100) says explicitly: "BDI as orientation vocabulary, not execution architecture." Goals structure the system prompt; the LLM does the reasoning.

**Engine** has `Goal` — a case-level completion condition with a pluggable `ExpressionEvaluator`. When the condition evaluates true, a `GoalReachedEvent` fires and the case transitions to COMPLETED or FAILED. Completely separate from eidos goals. Engine also owns the routing layer: `GoalFormationService` (propose goals), `GoalRevisionStrategy` (revise via LLM), `GoalAbandonmentEvaluator` (abandon on repeated failure). These operate on eidos `AgentGoal` instances and write back to eidos `AgentRegistry`.

**Blocks** is where it gets interesting. `GoalProposalOrchestrator` — 500+ lines — runs a full drive-based goal lifecycle. Four drive-to-goal mappers (autonomy, competence, affiliation, curiosity) feed into an LLM formation strategy with cross-axis enrichment and narrative-driven escalation. Goal outcomes flow back as trait pressure. This is cognitive processing. It was built before neocortex had the infrastructure to host it.

**Desiredstate** has `GoalCompiler<G>` — a generic interface that compiles domain-specific goals into a `DesiredStateGraph`. The graph has explicit `Dependency(from, to)` edges, topological ordering, phased lifecycle with `CompletionCondition`. A reconciliation loop continuously converges actual state toward desired. The expansion example compiles "expand to location X with structures Y" into a two-phase lifecycle: build (sequential construction) then defend (continuous patrol). This is a dependency graph and phased lifecycle — structurally parallel to what I was about to build in neocortex.

**Neocortex** has `Intentionlike` — an interface with three methods: `goal()`, `status()`, `priority()`. The gap.

## What this means for #345

If I'd built goal cognition in neocortex without this audit, I'd have created a parallel goal management system that doesn't know about engine's routing, blocks' drive-based proposals, or desiredstate's dependency graph. Split-brain architecture.

The right answer isn't to consolidate everything into one repo. Each layer owns a legitimate concern. Eidos owns identity. Engine owns execution. Blocks owns behavioural wiring. Desiredstate owns convergence. Neocortex owns cognition. But they need shared vocabulary.

We landed on "shared primitives, independent engines." A lean module — probably in neocortex, following the `cognitive-api` pattern — defines the common types: dependency edge types, lifecycle states, priority model. Each repo keeps its own processing engine but speaks the same language. Desiredstate keeps its `GoalCompiler` decomposition. Neocortex keeps its cognitive processing. Engine keeps its routing. No split brain.

## The durability gap

One finding I didn't expect: `GoalSignalStore` in eidos is volatile. Every implementation is a `ConcurrentHashMap` — goal outcome data is lost on JVM restart. Engine's revision and abandonment evaluators need outcome history across restarts to trigger evolution (minimum 10 outcomes at 80% success rate for promotion). That history resets to zero every time the process restarts.

This isn't a neocortex concern — it's an eidos durability concern that needs its own review. But it changes the shape of #345: neocortex shouldn't try to be the persistence backend for eidos. Engine routing needs to work durably without neocortex on the classpath.

## What's next

Six architectural decisions remain open. Where the shared primitives live (platform-api vs neocortex-goal-api). Whether blocks' cognitive goal processing migrates to neocortex. How neocortex's signals flow into engine's `GoalFormationContext`. Whether desiredstate shares dependency types or bridges through compilation. Slot 203 is set up with all six repos for the next session to resolve these and write the design spec.

The interesting question underneath all of it: blocks built sophisticated goal cognition before neocortex existed. Now neocortex exists. What moves, what stays, and what just needs a shared vocabulary?
