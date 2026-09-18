---
layout: post
title: "The ten-dimension audit that found a scheduler that could never recover"
date: 2026-09-18
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [audit, cdi, thread-safety, performance, mindmap, cbr]
---

Neocortex has been growing fast. Four capability areas, 40+ modules, CDI decorator chains ten deep, consolidation phases running on background threads, and cognitive subsystems wiring into each other through events nobody was observing. I wanted to know where the seams were before any of it went into production.

I set up a ten-dimension audit: decorator stack ordering, end-to-end pipeline tracing, code duplication, CDI wiring correctness, module layers, reliability, thread safety, SPI completeness, configuration consistency, and API surface polish. Claude ran all ten in parallel, each using IntelliJ's semantic code intelligence to trace actual call hierarchies and type relationships rather than grepping.

The critical find was in `ConsolidationScheduler`. The scheduled task had per-phase try-catch — careful, seemingly correct — but `discoverTenants()` sat *outside* the catch, in the setup code before the phase loop. One transient failure there and `ScheduledExecutorService.scheduleAtFixedRate` silently kills the task. Permanently. No log. No retry. The consolidation system would just stop, and nobody would know until they noticed that merge detection and experience graduation had gone quiet.

The second find was quieter but arguably worse. `ConfidenceDecayDecorator` — the exponential half-life decay that's supposed to reduce confidence scores on read operations — existed as a plain class in `mindmap-core` but was never wired into CDI. Every deployment since the decorator was written has been running without confidence decay. The MindMap documentation describes it as an active feature. It wasn't.

Same story with `VocabularyNormalizationDecorator` — except that one turned out to be an empty class with zero method overrides. Vocabulary normalization actually happens inside the store implementations. The decorator was a stub that never got implemented, and the docs described it as if it worked.

The thread-safety audit found a race condition in `RetrievalAccessTracker` that I hadn't considered. Two volatile fields — a counts map and a timestamps map — were swapped separately in `swapAndReset()`. Between the two writes, a concurrent `recordAccess()` could write to the new counts map but the old timestamps map. The timestamp data goes into the old snapshot and is lost. We fixed it by bundling both into a single volatile record reference — one atomic swap.

The CDI wiring check revealed something I should have caught earlier: all three notification decorators (`ErasureNotificationCbrCaseMemoryStore`, `SupersessionNotificationCbrCaseMemoryStore`, `ErasureNotificationCaseMemoryStore`) fire CDI events without try-catch. The tracking decorators — doing the same kind of observational side-channel work — correctly wrap their tracking calls. But the notification decorators don't. If any observer throws, the caller sees failure even though the delegate operation already succeeded. The fix was a shared `safeFire()` utility on each.

The performance audit found that MindMap's `search()` method was using `LIKE '%text%'` — a full table scan — despite having a perfectly good FTS5 virtual table with sync triggers already wired up. The FTS5 infrastructure existed since V1 of the migrations. It just wasn't being used by the query code. Switching to FTS5 MATCH is the difference between O(n) and O(log n) for every text search.

Two scaling cliffs surfaced in consolidation: `MergeDetectionPhase.detectCandidates()` does O(n^2) pairwise name comparison across all nodes in a subgraph, and `CuriositySignalGenerator` calls `betweennessCentrality` — O(V(V+E)) Brandes' algorithm — on every consolidation tick. For a subgraph with 5,000 nodes, that's minutes of computation per tick. We added node-count guards (skip at 500 and 2,000 respectively), but the real fix is approximate algorithms — MinHash for merge detection (already in `rag-api` for query clustering), and sampled Brandes for centrality.

The API surface audit found that `CbrCaseStore` erase methods return boxed `Integer` while `CaseMemoryStore` and `MindMapStore` use primitive `int`. No null semantics justify boxing. And `tenantId` appears in four different parameter positions across `CbrCaseLifecycle` methods — second, first, middle, and last. That kind of inconsistency accumulates into cognitive load for anyone implementing the SPIs.

What surprised me was what the audit *didn't* find. All 64 `Instance<T>` injection sites properly check `.isResolvable()` before calling `.get()`. Every `ConcurrentHashMap` uses `computeIfAbsent` for compound operations. The sealed hierarchies are all well-formed. The decorator chain ordering — when the priorities were unique — was correct across all four SPIs. The codebase is structurally sound; the issues were at the seams between subsystems, where observational side-channels met primary operations.

Eight commits landed directly on main. Twelve deferred items became GitHub issues under epic #355. Four universal protocols went into the garden — CDI observational decorator isolation, unique decorator priorities, scheduled task exception guards, and atomic volatile swap-and-reset.

The consolidation scheduler now catches everything and keeps ticking. Confidence decay is actually active. Text search uses the index that's been sitting there since day one. The notification decorators can't kill your store operation. The next session starts on #355 — batch graph operations first, then the scaling work.
