---
layout: post
title: "The Bugs That Didn't Crash"
date: 2026-11-17
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [multi-tenancy, search-limits, cognitive-pipeline, data-loss, debugging]
series: issue-977-pid5-facet-personality-classification
---

# The Bugs That Didn't Crash

Eight issues in the queue. Three already fixed by other sessions. One referencing a class that no longer exists. One deferred because it needs a design decision. Three that needed actual code changes. The pattern across all three: silent data loss. No exceptions. No warnings in the log. Just wrong answers, delivered with confidence.

## Shared Cache, Shared Results

`BehavioralSynthesisPhase` caches the last CAPS settling result per agent — the behavioral attractors that shape what the agent says next. The cache key was `agentId`. Not `tenantId:agentId`. Just `agentId`.

In a single-tenant deployment, this is invisible. In multi-tenant, the same agent seeded in two tenants shares one cached settling result. Tenant A's betrayal scenario writes the cache. Tenant B's routine conversation reads it. Tenant B's agent suddenly exhibits distrust attractors that belong to someone else's story.

The fix is one line of key construction. The discovery is the reminder: multi-tenant bugs don't crash. They produce plausible wrong answers in contexts you're not looking at.

## The Limit That Erased History

Nine call sites across the cognition and mindmap-intelligence modules followed the same pattern:

```java
store.search(MindMapQuery.of(tenantId, 200)
             .withType(SubgraphTypes.COGNITIVE))
     .stream()
     .filter(n -> "drive-intensity".equals(
         n.properties().get("cognitiveKind")))
     .filter(n -> agentId.equals(
         n.properties().get("agent-id")))
     .toList();
```

The database returns up to 200 COGNITIVE nodes. The in-memory filter keeps only the ones matching a specific kind and agent. The problem: COGNITIVE is the busiest subgraph type. Every regulation event, every graduated experience, every drive-intensity snapshot — all COGNITIVE. An active agent generates hundreds of these nodes per session.

![Search-then-filter data loss](images/search-then-filter-data-loss.svg)

Past 200 nodes, the limit truncates before the filter runs. Drive-intensity lookups miss recent intensity snapshots. Emotion regulation history loses its oldest entries — the ones that establish baselines. The `InformationGapDetector` can't find information gaps in nodes it never sees. Everything continues to function. The answers are just increasingly wrong, proportional to how active the tenant is.

I raised the limit from 200 to 2000, matching the precedent already set by other search sites in the same codebase. It's the right fix for now. The structural fix — pushing property filters into `MindMapQuery` so the database does the filtering instead of Java — is filed as #1091.

## What Makes These Hard

None of these had a stack trace. None produced an error message. The enum test (`SignalCategory` grew from 12 to 14 values, test still asserted 12) at least failed visibly — that's the easy kind. The hard kind is a cache that returns someone else's behavioral attractors, or a search that silently drops your most recent data points. Both produce output that looks correct unless you know exactly what should be there.

The search-then-filter pattern is worth calling out because it's genuinely tempting. `MindMapQuery` doesn't support property-based filters, so the in-memory filter feels like the natural workaround. It works until the data grows past the limit. And the limit is invisible in test environments, where nobody has 200 COGNITIVE nodes.

## What's Still Open

`PersonalityEvolutionOrchestrator` has zero production callers — its `tick()` method is never invoked outside tests. The orchestrator exists, it's wired by CDI, it just never runs. Fixing it requires deciding whether personality evolution should be a consolidation phase or a tick participant, and how disposition profile changes propagate to the cognitive defaults derivation engine. That's a design decision, not a bug fix, and it's staying in the queue (#1060) for a session that can give it proper attention.

The two pre-existing test failures in the cognition module — `AppraisalStatePropagationTest` and `EmotionRegulationTickParticipantTest` — are now tracked as #1092 and #1093. They were failing before this session and they're failing after it. The fixes on this branch don't touch their code paths.
