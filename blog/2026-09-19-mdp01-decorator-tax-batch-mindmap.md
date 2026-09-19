---
title: "The Decorator Tax — Batch Operations for MindMap"
date: 2026-09-19
author: mdp
entry_type: note
subtype: diary
tags: [mindmap, performance, spi, decorators, cdi, sqlite]
projects: [casehubio/neocortex]
---

Every `addNode()` call in the MindMap subsystem traverses a chain of five CDI decorators before reaching the database. Each decorator reads back from the store to do its work — DerivedEdgeDecorator fetches the edge and source node to evaluate forward-chaining rules, TraitApplicationDecorator reads nodes to evaluate trait rules, MutationTrackingDecorator persists an audit record. For a single node, this is fine. For MindMapExtractor processing a typical conversation extraction — ten entities, fifteen relationships — it means over a hundred separate database operations, each in its own autocommit transaction.

The fix was structurally straightforward but architecturally interesting. I added `addNodes` and `addEdges` as default methods on the `MindMapStore` SPI, with loop-over-single implementations that any existing store inherits without changes. Then each layer got its own batch override: SQLite wraps everything in a single transaction (one WAL sync instead of N), and each decorator delegates the batch to its inner layer first, then runs its side-effects on the results. DerivedEdgeDecorator evaluates rules after all edges are inserted, not interleaved with each insertion. TraitApplicationDecorator evaluates traits for all new nodes at once, seeing the complete batch state rather than a partially-built graph.

The critical design constraint was in `AbstractForwardingMindMapStore`. The default SPI method calls `this.addNode()`, which on a forwarding decorator re-enters the outermost decorator for each item — producing O(N × chain_length) work. The forwarding base must delegate to `delegate.addNodes()` instead, so the batch propagates inward through the chain. Anyone adding a new default method to a decorated SPI will hit this — it's not a Java gotcha exactly, but it's the kind of thing you only think about once you've drawn out the call graph.

The callers — MindMapExtractor, CommunitySummaryPhase, ExperienceConsolidationPhase, TypeRegistry — all followed the same refactoring pattern: collect inputs in the loop instead of calling the store, batch-insert after the loop, then map returned IDs back to build the result objects. ConversationBridge was deliberately excluded — it fires CDI events between addNode calls, and batching would change the event ordering semantics.

What this opens up: the batch infrastructure is now in place for the consolidation pipeline to scale beyond single-tenant small graphs. When a tenant has thousands of nodes and the consolidation scheduler runs CommunitySummaryPhase across dozens of subgraphs, the difference between N transactions and one transaction becomes measurable. The same pattern could extend to `updateNodes` if the need arises, though the update case is more complex because each update depends on reading current state.
