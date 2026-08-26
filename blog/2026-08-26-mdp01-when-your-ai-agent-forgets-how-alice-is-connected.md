---
layout: post
title: "When Your AI Agent Forgets How Alice Is Connected"
date: 2026-08-26
entry_type: article
subtype: diary
projects: [casehubio/neocortex]
tags: [mindmap, knowledge-graph, forward-chaining, gdpr, graph-analysis]
series: issue-213-mindmap-epic
---

# When Your AI Agent Forgets How Alice Is Connected

An AI agent that remembers facts about a user but can't traverse relationships between them is doing recall, not understanding. "Alice works at Acme" and "Alice has a child named Bob" are two flat memories. Without structure connecting them, the agent can't answer "who is Alice's family?" without scanning every memory it has and hoping the text overlaps.

The mind map SPI we've been building in neocortex exists to fix this. It's a typed graph — nodes with properties, edges with governed vocabularies, subgraphs per topic or person — that gives cognitive subsystems a shared structural backbone. The flat memory stores (`CaseMemoryStore`, `CbrCaseMemoryStore`) keep doing what they're good at: text recall and feature-vector similarity. The graph adds the relationship layer they've never had.

This session pushed the graph from a storage substrate into something that reasons about its own content.

## Forward-Chaining Rules on a Knowledge Graph

The problem with a manually-maintained graph is that derived knowledge has to be maintained manually too. If you add a `has-child` edge from Alice to Bob, you expect a `parent-of` edge from Bob to Alice. If you later remove the `has-child` edge — because Alice corrects the record, or because the information decays below confidence threshold — the `parent-of` edge has to go with it. Miss that cleanup, and the graph contradicts itself.

`DerivedEdgeRule` is a pluggable SPI. Rules are CDI beans that the `DerivedEdgeDecorator` discovers automatically. When an edge is added, every rule evaluates it and produces zero or more derived edges. Those derived edges carry provenance metadata — which rule fired, which trigger edge caused them — so truth maintenance knows exactly what to retract when the evidence is removed.

```java
public interface DerivedEdgeRule {
    String name();
    List<EdgeInput> derive(MindMapNode sourceNode,
                           MindMapEdge trigger,
                           MindMapStore store);
}
```

The decorator chains derivations: a derived edge can trigger further rules, up to a configurable depth limit (default 3). This is forward chaining on a knowledge graph — the same principle Drools uses for production rules, scaled down to structural inference on a per-agent mind map.

The deeper point is economic, not just architectural. These rules are often **learned inference caches**. The LLM extraction layer (still ahead in the queue) discovers relationship patterns by analysing conversations — it pays the token cost once to figure out that `has-child` implies `parent-of`, or that `works-at` plus `manages` implies `colleague-of` between the managed employees. Once it codifies that pattern as a `DerivedEdgeRule`, every future instance of that relationship fires deterministically at zero token cost. The rule SPI is the boundary between expensive probabilistic inference and cheap deterministic inference.

This reframes what the rules are for. Hand-coded rules like "has-child implies parent-of" are obvious — you'd write those on day one. The interesting rules are the ones the agent discovers through experience. An agent that has had enough conversations to notice that people who share a `works-at` target and appear in the same `project` subgraph are usually collaborators can promote that observation to a rule. From that point forward, the graph maintains the `collaborates-with` edges automatically. The LLM never needs to re-derive that relationship.

Why does this matter to an end user? Two reasons. First, derived knowledge is where agents stop feeling stupid — an agent that knows Alice has a child named Bob but can't infer that Bob has a parent named Alice is doing dictionary lookup, not reasoning. Second, it gets cheaper over time. Every pattern the agent learns and promotes to a rule is an LLM call it never makes again. The graph accumulates not just knowledge but the *inference machinery* to maintain that knowledge. The cognitive subsystems (mental model, strategy, narrative) see a complete graph without paying for the inferences that produced it.

## Graph Analysis — What the Agent Doesn't Know

A graph that stores knowledge is useful. A graph that can tell you what's *missing* from its knowledge is more useful. `MindMapAnalyzer` computes structural, quality, temporal, and centrality signals — pure Java, no LLM dependency, following the same static-utility pattern as `RetrievalAnalyzer` in the RAG pipeline.

The structural signals find orphan nodes (knowledge with no connections), sparse subgraphs (topics the agent knows little about), and contradictions (two `works-at` edges pointing to different companies from the same person). The centrality signals — degree and betweenness — identify bridge nodes that connect otherwise separate clusters of knowledge, the entities worth keeping fresh because losing them disconnects entire areas of the graph.

These feed the curiosity engine (still ahead in the queue). An agent that knows Alice has few connections in its graph can ask targeted questions to fill the gaps. An agent that detects a stale cluster — nodes not confirmed in months — can prioritise re-verification. The analysis layer turns a passive knowledge store into an active knowledge seeker.

## GDPR Erasure That Actually Cascades

GDPR Art.17 says: delete everything about this person. For flat memory stores, that's a query-and-delete on a single entity ID. For a graph with cross-store references, it's harder.

A `MindMapNode` about Alice might carry a `NodeRef` pointing to her memory in `CaseMemoryStore` and another pointing to her CBR case profile. When the memory store erases Alice's data, those references become dangling pointers — and under GDPR, they're still personal data because they identify a data subject.

We built this in two layers. `MemoryEntityErased` is a sealed CDI event fired by a new `@Decorator` on `CaseMemoryStore`'s erase chain, matching the existing `CbrCasesErased` pattern. `NodeRefCleanupObserver` listens for both event types and scans the graph for matching `NodeRef`s, removing them via the existing `updateNode(refsToRemove)` API.

The error isolation matters: the observer catches exceptions and logs them rather than propagating. If the graph cleanup fails, the memory erasure itself still completes — GDPR compliance on the source store is not blocked by a downstream cleanup failure. The cleanup is proactive (CDI event-driven), not lazy (next-read check), because a lazy check that never fires is a data protection violation sitting in production.

## What This Opens Up

The trait system is next — forward-chaining rules that apply typed interfaces to nodes based on their properties and edges. A node with a "birthday" property and `parent-of` edges gets the `Personable` trait applied. That trait gives typed access to person-specific fields through a proxy, abstracting over core fields and dynamic properties. It's the same trait model from Drools, implemented independently here but designed so a future integration could delegate to Drools when available.

The curiosity engine sits behind that — the consumer of `MindMapAnalyzer`'s signals, turning structural gaps and stale regions into questions the agent actually asks. A mind map that maintains itself through forward chaining, analyses itself for gaps, and drives the agent's knowledge-seeking behaviour. That's the trajectory.
