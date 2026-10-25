---
layout: post
title: "The Import That Wasn't"
date: 2026-10-25
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [memory-seeding, corpus-import, relationship-stages, biography]
---

# The Import That Wasn't

The data model was ready. The Python converter was passing it through. The
YAML deserialized without complaint. And `EntityEnrichmentHandler` was
ignoring all of it.

`relationship_stages` is one of four enrichment types on
`EntityEnrichmentEntry`. The other three — drive baselines, CAPS patterns,
behavioural attractors — had their import code. This one had a record
definition, a working deserializer, and nothing else. The handler processed
entries 1–3 and stopped.

The fix itself was small: iterate the stages, store each transition as a
relationship-domain memory with `stage-from`, `stage-to`, `period`, and
`trigger` attributes. The `Transition` record also needed a `trigger`
field — the corpus data carries it but the Java type was silently dropping
it.

The interesting part is the semantic mismatch between what the corpus
provides and what the runtime consumes. The corpus carries narrative stages
— "admiration/mentorship" becoming "passionate/romantic" becoming
"turbulent/volatile". These are entity-specific, contextual, human-legible.
`RelationshipStagePhase` in consolidation works differently: it counts
positive/negative/neutral interactions, computes a familiarity score, and
maps that to generic tiers — stranger, acquaintance, familiar, friend,
confidant. The two systems describe the same phenomenon at different
altitudes.

Storing the biographical transitions as relationship-domain memories means
they're queryable by any component that looks at relationship history. They
won't directly drive the familiarity score — that's computed from
interaction counts — but they give the cognitive system access to
narrative context it didn't have before. A consolidation phase that wanted
to reason about *how* a relationship evolved, not just *how often*
interactions occurred, now has the data to work with.
