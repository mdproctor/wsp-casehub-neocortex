---
layout: post
title: "Closing the cognitive flywheel"
date: 2026-09-14
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [mindmap, schema, extraction, consolidation, type-system]
series: issue-335-cognitive-schema-flywheel
---

The MindMap extractor has been producing entities with properties for months — person nodes with roles, meeting nodes with dates, belief nodes with stances. But every extraction was open-ended. The LLM had no memory of what it had discovered before. Each conversation turn started from zero: guess the type, guess the properties, hope for consistency.

The schema flywheel closes that loop. Three layers, each feeding the next:

**Discovery.** A new consolidation phase — `SchemaDiscoveryPhase` at priority 25, slotting between merge detection and community summaries — scans entities of the same type and looks for property patterns. If 80% of "meeting" nodes have a "date" property, that becomes part of the meeting type's schema. The threshold, the minimum sample size, the required-flag cutoff — all configurable, because the right values depend on the deployment and the data. The interesting design constraint: Java-derived schema fields (from trait interfaces like `Personable`) are immutable to discovery. The provenance tag (`source=java` vs `source=discovered`) is the enforcement mechanism.

**Guided extraction.** When the extractor builds a prompt for the LLM, it now checks which types appear in the conversation's graph context. For each known type, it reads the schema from TypeRegistry and injects it as structured profile data — not directives, not instructions, just labeled fields: `meeting: {date: string (required), attendees: string (collection), agenda: string}`. The LLM integrates this naturally. An explicit "extract all observed properties" instruction keeps the door open for novel discovery.

**Promotion.** When a dynamic type stabilises — when its schema stops changing — a developer can run the `TraitInterfaceGenerator` CLI to produce a Java interface. `meeting` becomes `Meetinglike` with `Optional<String> date()`, `Optional<String> agenda()`. The developer reviews it, adjusts types, commits. From then on, application code gets compile-time safety and IDE autocomplete. But this is optional — the flywheel itself runs entirely on schema data stored as type node properties.

The design question that shaped the whole architecture: does the flywheel need Java interfaces at runtime? The answer is no. `ThingProxyHandler` already provides typed access via JDK Proxy — that IS runtime code generation. ByteBuddy or ASM would add classloader complexity for zero functional benefit. The flywheel is a data-flow system. Code generation is developer ergonomics for stable types, not flywheel mechanics.

The decision review surfaced a genuine concern: schema-guided extraction creates a positive feedback loop. The LLM preferentially extracts properties it's told about, which reinforces their frequency, which locks them in. Novel properties that were close to the threshold can get suppressed. The mitigation is provenance tracking (`first-seen-epoch` on discovered fields) and the explicit instruction to extract all properties regardless of schema. Future work: CBR auto-tuning of the thresholds based on extraction quality outcomes.

`SchemaField` gained three new fields — `collection`, `description`, `enumValues` — because the original `(name, type, required)` triple wasn't expressive enough for guided extraction. The LLM needs to know whether "attendees" is a list, what valid values for "status" are, and what a property means. The extension is backward-compatible: the 3-arg constructor delegates to the full 6-arg version with sensible defaults.

What this opens up: the type system is now self-documenting. Dynamic types accumulate schema through observation, not through developer effort. The schema guides future extraction, improving consistency. And when a type matters enough, it graduates to a Java interface — a conscious act, not an automated one. The cognitive graph knows what it knows about its own structure, and uses that knowledge to learn more precisely.
