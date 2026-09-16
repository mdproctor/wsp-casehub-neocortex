---
layout: post
title: "Three ways to make a cognitive system less naive"
date: 2026-09-16
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive, consolidation, cbr, graduation, diversity, mmr]
series: issue-340-cognitive-s-batch
---

The cognitive subsystem's consolidation pipeline had a naivety problem. A single observation about someone — "Bob looks worried" — could graduate to a permanent belief. The CBR retrieval pipeline returned five cases that were essentially the same case with minor variations. And the consolidation scheduler ran on a dumb timer with no awareness of whether anything interesting had happened.

Three S-scale issues, each addressing a different flavour of the same underlying problem: the system wasn't discriminating enough.

**Corroboration (#340)** — The fix is a frequency gate on `GraduationScorer`. Before graduating an experience memory to a semantic node (belief, intention, judgment), the scorer now requires 3+ converging episodes about the same observed entity. The interesting design question was how to get store access into a `@FunctionalInterface` that takes a single `Memory`. We widened the SPI to `score(Memory, GraduationContext)` where the phase batch-queries per observed entity and pre-builds the context. Clean contract, no I/O inside the scorer, extensible for future importance scoring.

The implementation surfaced a naming confusion worth documenting: `Memory.subject()` returns the agent who recorded the memory, not the entity being observed. The observed entity lives in the attributes as `ExperienceAttributeKeys.SUBJECT`. We'd wired the corroboration query to `Memory.subject()`, which meant every memory from the same agent corroborated every other memory from that agent — the test for "different subjects don't corroborate" produced 3 graduated nodes instead of 0.

There's a subtlety in the cursor handling. If a memory has sufficient confidence but fails the corroboration check, the scan cursor doesn't advance past it. On the next consolidation pass — when a 3rd corroborating experience may have arrived — the memory gets re-evaluated. Without this, memories scanned before the corroboration threshold was met would be permanently skipped.

**Significance trigger (#342)** — A `SignificanceAccumulator` observes `ExperienceRecorded` CDI events, accumulates per-tenant significance via `DoubleAdder`, and triggers `consolidateNow()` when a configurable threshold is crossed. The metric is pluggable through a `SignificanceExtractor` SPI — the default returns 1.0 (pure event count), ready for real importance scores when #339 lands. The accumulator uses a CAS flag (`putIfAbsent`) to ensure once-per-window triggering, and the consolidation scheduler resets everything via `swapAndReset()` at tick start.

Code review caught a thread leak: the original implementation created a new `Executors.newSingleThreadExecutor()` per trigger invocation. Each executor spawned a daemon thread that was never shut down. Fixed by creating the executor once as a field.

**CBR diversity (#344)** — Maximal Marginal Relevance, the standard IR diversity technique. A `DiversityCbrCaseMemoryStore` decorator over-fetches by a configurable factor (default 1.5x), then greedily selects results that maximize `lambda * relevance - (1-lambda) * max_pairwise_similarity`. Pairwise similarity uses the existing `CbrSimilarityScorer` with uniform weights. The decorator caches schemas via `registerSchema()` interception for the pairwise computation. When no schema is cached, diversity is silently skipped — graceful degradation.

All three fit the established patterns: the scorer SPI follows the same `@DefaultBean` convention as every other pluggable component, the significance accumulator follows the `RetrievalAccessTracker` swap-and-reset model, and the diversity decorator is a plain class extending `DelegatingCbrCaseMemoryStore` like every other CBR retrieval modifier. The cursor-hold for retroactive corroboration is the only genuinely novel mechanism.
