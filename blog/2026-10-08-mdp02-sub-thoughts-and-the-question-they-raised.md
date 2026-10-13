---
layout: post
title: "Sub-Thoughts and the Question They Raised"
date: 2026-10-08
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive, sub-thought, biography, architecture, design]
series: issue-470-sub-thought-bio-import
---

# Sub-Thoughts and the Question They Raised

When an agent records "Lunch with Sarah at La Trattoria," the raw text is a surface description. The cognitive reactions underneath — she seemed distracted, the promotion must be weighing on her, I should bring David here next time — are where the real processing happens. Sub-thought decomposition captures these as typed, entity-tagged attributes on the parent memory record. Seven types: affect-observation, causal-inference, evaluative, intention, self-reflection, association, concern.

The data model decision was made in the prior session: sub-thoughts are Memory attributes, not MindMap nodes. Zero graph pollution, FTS-clean, with optional node attachment when a sub-thought earns it through consolidation graduation. This session built the pipeline that makes that model useful.

## The Extraction Pipeline

CheckInService — the "I was at X with Y" entry point — gained an overloaded `checkIn` that creates an experience memory and fires a `SubThoughtExtractionRequested` CDI event for async LLM decomposition. The key design constraint was backward compatibility: the existing constructor takes only `MindMapStore`, and the existing tests construct it directly. A package-private backward-compat constructor preserves this while the CDI constructor adds optional `Instance<ExperienceRecorder>` and `Event<SubThoughtExtractionRequested>`.

`SubThoughtExtractor.applySubThoughts()` writes the typed attributes via `CaseMemoryStore.enrichAttributes()` — a new SPI method that merges additional attributes into an existing memory without replacing it. The async observer is a stub for now. The LLM call that actually parses "Lunch with Sarah" into typed reactions doesn't exist yet.

## Graduation

`SubThoughtConsolidationPhase` scans experience memories, accumulates (entity, type) pairs across memories, and graduates when a pattern crosses a threshold. Three mentions of "Sarah" + "affect-observation" across different experiences → a COGNITIVE MindMap node with `graduated-sub-thought` trait and multi-NodeRef traceability back to each source memory. Biographical import memories are excluded — they're pre-authored, not earned through observation.

## The Biography Framework

Ten YAML template types across an eight-layer import model: cultural context at the bottom, current emotional state at the top. A `BiographyHandler` SPI per template type, dispatched in layer order by `BiographyImportRunner`. Each handler creates MindMap nodes or memory records with a three-tier provenance chain: source prose → template entry → imported node.

The handlers follow a mechanical pattern — resolve-or-create subgraph, check idempotency via `resolveNode`, set provenance properties, handle PAD and associations. `LifeEventHandler` is the exception: it stores sub-thought attributes atomically with the life event memory, meaning biographical events arrive pre-decomposed. The consolidation phase skips these (they haven't been "observed," they've been narrated), but the attribute structure is identical to what the live extraction pipeline produces.

## The Question This Raised

With the implementation done, I asked: how are sub-thoughts actually *used*? The honest answer was that they weren't. The data model exists, the storage works, graduation works, biography import works — but nothing in the cognitive pipeline consumes them. Each orchestrator (mood, drive, mental model, goal) still independently processes raw experience text.

The analysis that followed was more interesting than the implementation. Sub-thoughts decompose an experience into typed, entity-tagged reactions — exactly the intermediate representation each orchestrator is independently trying to derive from raw text. An affect-observation about Sarah is a belief about her current state. A concern about Sarah activates affiliation drive. An intention is a proto-goal.

The paradigm shift: sub-thoughts as the shared currency between experience and all downstream cognitive processing. One decomposition feeds many consumers instead of each orchestrator re-deriving what it needs.

The highest-value integration is mental model updates from entity-tagged sub-thoughts — direct BDI evidence with full traceability. The second is drive modulation from type distributions. Both are straightforward to wire through a `CognitionTickParticipant` that reads recent sub-thoughts and dispatches to existing orchestrators.

The extraction strategy matters too. A hybrid approach — lightweight rule-based sync during the tick for immediate decomposition, full LLM async for richer analysis later — means the current tick gets basic sub-thoughts without blocking, and subsequent ticks work with the richer version.

Whether sub-thoughts earn their place in the architecture depends entirely on this next step. The data model is infrastructure; the cognitive integration is the capability.
