---
layout: post
title: "Breaking circular repo entry — 9 to 2 cycles across 8 repos"
date: 2026-09-17
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [maven, architecture, dependency-management, multi-repo, ownership]
---

# Breaking circular repo entry — 9 to 2 cycles across 8 repos

The casehub platform has around 30 Maven repos. They share a groupId and build in a defined order. What I hadn't verified was whether that order was actually acyclic. It wasn't.

## The problem isn't Maven's

Maven catches circular dependencies within a single reactor. But cross-repo cycles — where repo A needs repo B's artifacts installed, and repo B needs repo A's — slip through silently. The `banCircularDependencies` enforcer rule from MojoHaus only checks if the building artifact's own `groupId:artifactId` appears in its transitive tree. A1 depending on B, which depends on A2, is invisible to it. Different artifacts, same repo, still can't bootstrap from a clean `~/.m2`.

I wrote a Python script that parses `pom.xml` files across all repos, builds the inter-repo dependency graph, and runs DFS cycle detection. Pure stdlib, no Maven execution, runs in seconds. It found nine cycles.

## Ownership, not graph theory

The first instinct was to move whichever file was smallest to break each cycle. That would have been wrong.

Take `TrustConsolidationPhase` — a single class in neocortex that imported two types from blocks, creating a `neocortex → blocks` edge. The quick fix: move it to blocks. But trust consolidation is entirely mechanical — query MindMap nodes, fetch ledger attestations, compute scores, write properties. No LLM anywhere. By the engine/blocks architectural split (mechanical processing lives in engine, LLM capabilities live in blocks), it belongs in engine, not blocks.

Following that thread revealed three independent trust pathways scattered across three repos — ingestion in blocks, consolidation in neocortex, routing in engine — all feeding from the same ledger pipeline. Consolidating them into engine gave trust a single home where the full lifecycle lives together: ingest, compute, apply. The cycle broke as a side effect of getting ownership right.

The same pattern repeated. Eidos had an `org-runtime` module implementing desiredstate's GoalCompiler SPI. But eidos declares identities and profiles — goal compilation is desiredstate's job. Moving it there broke a triangle cycle and placed the code where it can grow into the deployment story without eidos accumulating responsibilities it shouldn't have.

Eidos also had a routing bridge that delegated to engine's `AgentRoutingStrategy`. One class, one test. Integration glue sitting in the identity layer instead of the orchestration layer. Engine already had 257 references to eidos types — it speaks both vocabularies. The bridge moved to engine, eidos dropped its last engine dependency, and two more cycles disappeared.

The work adapter was the messiest — 20 bidirectional glue classes, production code that didn't compile because engine had refactored its SPI out from under it. The module was commented out of the reactor entirely. Moving it to engine (where the SPI references become intra-project) and deleting the dead `InboundWorkItemSchedulerImpl` was both a cycle fix and a cleanup of code that had been silently rotting.

## What survived

Two cycles remain. `platform ↔ neocortex` is structural — five memory store implementation modules in platform that should be in neocortex (the SPI migrated, the implementations didn't). That's a bigger move with downstream coordinate changes. `life ↔ openclaw` is an npm packaging question — wrapper modules in the wrong repo.

The remaining cycles are real work, but the approach is clear: ask who owns the capability, not which file is smallest.
