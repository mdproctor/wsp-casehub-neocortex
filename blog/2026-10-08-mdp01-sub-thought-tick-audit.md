---
title: "Where the classification logic actually belongs"
date: 2026-10-08
author: mdp
entry_type: note
subtype: diary
series: issue-478-sub-thought-tick-integration
tags: [architecture, module-boundaries, cdi, cognitive-pipeline, audit]
projects: [casehubio/neocortex]
---

Sub-thought decomposition — turning raw experience text into typed, entity-tagged cognitive reactions — has been the intermediate representation I wanted between experience ingestion and cognitive processing for a while. Issue #478 wired it into the tick lifecycle: a sync keyword pass gives immediate sub-thoughts during the tick, an async LLM path enriches them post-hoc, and downstream consumers (mental model, drives, CAPS, prompt rendering) all pull from the shared decomposition instead of independently re-interpreting raw text.

The implementation landed across eight tasks and compiled clean. All existing tests passed. I could have called it done there.

## What the audit found

Claude ran a four-dimensional review — API types, tick wiring, downstream consumers, and async observer chain — and surfaced sixteen findings. Four were runtime bugs. The most interesting was a CDI silent failure: `@Observes` on a bean created via `@Produces` never fires. The bean resolves fine, all its methods work, there's no error and no warning. The observer method is simply invisible to the CDI event dispatcher because producer-managed instances aren't scanned for observers.

The entire async enrichment cache — the path where LLM-enriched sub-thoughts feed back into the tick participant — was dead code. Every test passed because no test exercised the CDI event dispatch chain end-to-end.

The fix was straightforward: extract the observer into a dedicated `@ApplicationScoped` bean that injects the produced instance and delegates. But the bug itself was a reminder that CDI's observer mechanism has a qualification that doesn't announce itself.

## The duplication question

Finding #13 flagged code duplication between `RuleBasedSubThoughtExtractor` (in `cognition`) and `SubThoughtExtractor` (in `mindmap-intelligence`). Both did keyword-based sentence classification with nearly identical keyword sets. The initial response was to accept it — "architectural consequence of module boundaries, and the async path is designed to be replaced by LLM anyway."

I wasn't satisfied with that framing. The two modules are peers. Neither can depend on the other. But they both depend on `memory-api`, which is where `SubThoughtTypes` defines the seven type constants. The classification is a pure function over those constants — sentence in, type out. It belongs next to the types it classifies against.

`SubThoughtClassifier` now lives in `memory-api` alongside `SubThoughtTypes` and `SubThoughtAttributeKeys`. Three files that form a cohesive unit: what the types are, how to persist them, how to detect them in text. Both consumers delegate classification and add their own concerns — entity matching for the sync path, `ParsedSubThought` wrapping for the async path.

The duplication wasn't an architectural consequence. It was a signal that the classification logic was in the wrong module. The module boundary that prevented sharing wasn't a constraint to accept — it was evidence that the shared dependency was the right home.

## CDI decorator tiering

The CAPS integration had a similar module-boundary problem. `SubThoughtSituationDecorator` maps sub-thought types to CAPS input node activations — concern activates `social_threat` and `psychological_threat`, intention activates `agency_granted` and `choice_available`. The logic belongs in `caps-engine`, but `caps-engine` has no CDI dependencies by design.

The solution: keep the pure classification logic in `caps-engine` as a plain class with constructor-injected delegate, then extend it with a thin `@Decorator @Priority(70)` subclass in `mindmap-intelligence` (which has CDI). The CDI subclass is three lines — constructor delegates to `super()`. All the behaviour lives in the CDI-free parent.

This pattern — pure logic in a CDI-free module, thin CDI subclass in a CDI-enabled module — preserves the tier boundary while participating in the decorator chain. It's the kind of pattern that feels obvious in retrospect but isn't the first thing you reach for when you hit the "this module can't have CDI annotations" constraint.

## What this opens up

The sub-thought pipeline is plumbing — it routes typed reactions to consumers. The interesting work is in what those consumers can do with typed, entity-tagged data that they couldn't do with raw text: detect patterns across experiences ("I keep having concerns about Sarah"), track entity-specific affect trajectories, and feed pre-classified input to CAPS instead of relying on keyword matching against raw observations.

The `configureSubThoughts()` call still needs to be wired by the platform. Until then, the pipeline is complete but inert — exactly the same pattern as `configureGutFeeling()` and `setAppraisalParticipant()`. The platform integration is tracked as #488.
