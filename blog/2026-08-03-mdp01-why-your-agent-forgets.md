---
layout: post
title: "Why Your Agent Forgets What It Just Did"
date: 2026-08-03
type: phase-update
entry_type: note
subtype: diary
projects: [casehub-neocortex]
tags: [memory, experience-stream, agent-memory, smallville, cdi, sealed-types]
series: issue-196-agent-memory-patterns
---

## Why Your Agent Forgets What It Just Did

Every AI agent system I've looked at hits the same wall. The agent completes a task — reviews a PR, investigates a suspicious transaction, triages a clinical event — and then forgets it happened. The next turn starts with a blank slate. Ask the agent what it did five minutes ago and it has nothing to say, because nothing was recorded.

This isn't a storage problem. CaseHub has had `CaseMemoryStore` for months — a tenant-isolated, GDPR-compliant, semantically searchable memory backend with five implementations. Devtown uses it to remember PR review context. AML uses it for prior investigation outcomes. The storage works. What's missing is the agent's own experience of doing the work.

## The Smallville Insight

The Generative Agents paper (Park et al., 2023) identified this as the foundational layer of agent cognition. Their memory stream is a timestamped log of everything an agent perceives or does: "John Lin is watering his plants at 10:30am", "Isabella Rodriguez greeted John", "The pharmacy opens at 9am." From this raw stream, the system derives everything else — relationship models, daily reflections, long-term plans.

CaseHub agents operate in a more structured environment than Smallville's small-town simulation, but the principle is identical. An agent that can query "what have I done today?" or "when did I last interact with Agent B?" has context that an amnesiac agent lacks. The raw experience stream is the input to relationship tracking, periodic reflection, and personality-weighted retrieval — all of which are downstream consumers that can't exist without it.

## Pattern, Not Store

The design question was whether the experience stream needs its own storage backend. It doesn't.

`CaseMemoryStore` already handles timestamped, tenant-isolated, importance-weighted, semantically searchable records with GDPR erasure. What it lacks is a schema — a structured way to say "this memory is an observation about PR #123" vs "this memory is the outcome of a code review." Without schema, every experience event is an unstructured blob of text with a `Map<String, String>` of arbitrary attributes. Callers construct `MemoryInput` by hand and hope they got the attribute keys right.

The experience stream is a typed API layer. A sealed interface — `ExperienceEvent` — with three concrete subtypes:

```java
public sealed interface ExperienceEvent
    permits Observation, Action, Outcome {
    String agentId();
    String tenantId();
    String turnId();     // groups events from the same agent turn
    String description(); // natural language for semantic search
    Double importance();  // [0,1] salience weight
    // ...
}
```

`Observation` is what the agent perceived — input context, another agent's result, environmental state. `Action` is what the agent did — which capability it exercised, who it acted on. `Outcome` is the result — success, failure, partial, with the capability tag for correlation.

Each type enforces its required fields at construction. An `Outcome` without a `result` won't compile. An `Observation` without a `subject` throws at construction, not when it hits the store three method calls later with an unhelpful `"text must not be blank"` error from a field the caller never touched.

## The Converter Does the Work

A utility class — `ExperienceEvents.toMemoryInput()` — converts any `ExperienceEvent` into a properly structured `MemoryInput` with standardized attribute keys. The domain is always `"experience"`. The event type is always set. Nullable fields are omitted, not set to empty strings. Caller-supplied metadata is merged in, but if it collides with a reserved key the converter throws — no silent overwrite.

This means the experience stream uses the same storage, same backends, same GDPR machinery, same semantic search, same importance-weighted salience ordering as every other memory in the system. No new modules. No new persistence implementations. No new Flyway migrations.

## What the Engine Calls

An `@ApplicationScoped` CDI service — `ExperienceStream` — is the ingestion entry point. After each agent turn, the engine calls `record(event)` and gets back a store-assigned memory ID. The service fires a synchronous `ExperienceRecorded` CDI event that downstream consumers observe. Relationship memory will watch for interactions involving other agents. The reflective diary will periodically query recent experiences and synthesise higher-order insights.

The `turnId` field groups events from the same agent turn. When the engine dispatches an agent, records its observations, and captures its outcome, all three events share a `turnId`. This matters because `Memory.createdAt()` is store-assigned — under load, three events from one turn can have identical or inverted timestamps. Without `turnId`, downstream consumers can't reconstruct the causal chain: "the agent observed X, did Y, which resulted in Z."

## Where This Goes

The experience stream is the first of four issues in the agent memory patterns epic. Relationship memory folds experience events into a per-agent-pair interaction graph via `GraphCaseMemoryStore`. The reflective diary periodically reads recent experiences and synthesises them into higher-level insights — the Smallville reflection mechanism adapted for CaseHub's structured environment. Personality-aware retrieval weights memory queries by disposition alignment, so an empathy-dominant agent retrieves relationship-relevant memories first.

All three consume the experience stream. None require changes to it. That's the test of whether a foundation layer is right — the consumers compose on top without reaching inside.
