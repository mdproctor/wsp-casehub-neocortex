---
layout: post
title: "Extract Locally, Verify Globally"
date: 2026-10-27
entry_type: article
subtype: diary
projects: [casehubio/neocortex]
tags: [extraction-pipeline, graph-quality, llm-verification, cognitive-engrams]
---

# Extract Locally, Verify Globally

The cognitive extraction pipeline processes biographies into knowledge graphs — entities, edges, memories — that feed the cognitive engine. Each passage goes through entity extraction, edge extraction, and enrichment independently. The LLM sees one passage at a time. The graph it produces is a global structure assembled from local operations.

That's the problem.

When I ran the Frida corpus through the post-vocabulary-fix pipeline (#704), the verification gate reported 71 critical dangling edges — references to entities that don't exist as nodes — and 2 orphan nodes with zero edges. The extraction prompt already says "every entity should have at least one edge." The LLM satisfices on this during generation. It produces relationships that feel right and moves on. Coverage is an instruction, not a constraint.

## The intersection that vanished

"Cuauhtemotzin and Cinco de Mayo" — the intersection where Frida's bus accident happened in 1925. The node carried extreme affect (pleasure -0.9, dominance -0.8) and lifecycle properties linking it to the accident. It had zero edges. The edge extraction call linked "the bus accident" to "Mexico City" instead. Locally reasonable, globally wrong. The intersection is unreachable by graph traversal.

The LLM had both entity names in context. It made a judgment call — link to the more prominent entity — that left the more specific one disconnected. No amount of prompt tuning fixes this. The LLM is doing two fundamentally different tasks in one call: generating relationships from text and verifying that every entity is covered. It satisfices on the second while doing the first.

## Three repair steps

I added a post-assembly verification pipeline between assembly (Step 7) and the existing verification gate (Step 8). Three steps, each following the same pattern: detect a global problem, send a targeted LLM call with focused context, validate the result against the registered vocabulary.

**Step 7.5 — Co-location gap closure.** For each passage, find entities that have no edge to any other entity in that same passage. One Haiku call per passage — the LLM reviews the assembled entities and edges and identifies what's missing. This subsumes zero-edge orphan detection: a global orphan is just a node with gaps in every passage it appears in.

The Frida corpus had 26 gap entities across 11 passages. After closure: zero gaps, 34 new edges added. The bus accident got its `at` edge to the intersection.

**Step 7.6 — Dangling edge resolution.** For each passage with edges referencing unknown entities, send the dangling names alongside the full node list and passage text. The LLM decides: match to an existing node (name variant), create a new entity (genuinely missing), or drop the edge (spurious).

63 dangling names across 9 passages. After resolution: 18 matched to existing nodes ("Trotsky" → "Leon Trotsky", "Cristina" → "Cristina Kahlo"), 39 new entities created (people, places, artworks the extraction missed entirely), 11 dropped as spurious (medical conditions, transient states). One remaining dangle.

**Step 8 — Verification gate.** The existing gate, now running on a repaired corpus. `dangling_edges` check: PASS. Was 71 criticals.

## The numbers

| Metric | Before | After |
|--------|--------|-------|
| Nodes | 152 | 191 |
| Edges | 634 | 654 |
| Critical dangles | 71 | 0 |
| Passage-level gaps | 26 | 0 |
| Global orphans | 2 | 0 |

Total cost: ~20 Haiku calls. One per passage with gaps, one per passage with dangles. Under two minutes.

## Why two calls beat one

The extraction prompt tries to generate relationships AND verify coverage in a single call. The repair steps separate these into different cognitive modes. Generation is open-ended — the LLM produces what feels right from the text. Verification is focused — the LLM reviews a specific entity's situation and decides whether something is missing.

This is the same insight as Corrective RAG: generation followed by verification catches errors that generation alone misses. The verification question is easier than the generation question because the hard work (identifying entities, producing most edges) is already done. The LLM just needs to review the assembled result and fill gaps.

I expected the gap closure to be the main win — catching the obvious orphans. The bigger surprise was the co-location gap detection. When I looked at the data, most entities connect to only 15% of their passage co-locators. That's not all gaps — many co-located entities legitimately have no relationship. But entities with zero in-passage connections are almost always extraction failures, and the LLM reliably produces valid edges when asked to focus on them.

The dangling resolution was equally productive. 39 entities that the extraction mentioned in relationships but never extracted as nodes — people, places, artworks that were contextually important but not focal enough for the entity extraction call to pick up. Creating them as back-filled nodes and connecting them to their edges completed relationships the extraction started but couldn't finish.

## What's left

The pipeline now has a repeatable post-assembly repair cycle: assemble → close gaps → resolve dangles → verify. Each step is a standalone script that operates on `corpus.json`. The verification gate is the final arbiter — if it passes, the corpus is import-ready.

The remaining verification findings are pre-existing extraction-level issues: a handful of unknown edge types (`enabled` instead of `enables`), invalid sub-thought type names, and subject alignment variants. Warnings, not blockers. They'll get fixed when the extraction prompts are next revised, not as post-assembly repair.

Napoleon is next.
