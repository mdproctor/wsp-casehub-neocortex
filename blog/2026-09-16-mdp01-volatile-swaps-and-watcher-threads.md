---
title: "Volatile Swaps and Watcher Threads"
date: 2026-09-16
author: mdp
entry_type: note
subtype: diary
projects: [casehub-neocortex]
tags: [cognitive-profiles, hot-reload, concurrency, directory-watcher]
series: cognitive-rearchitecture
issue: 270
epic: 253
publish: false
---

# Volatile Swaps and Watcher Threads

Cognitive profiles define how each agent thinks — personality weights, curiosity thresholds, vocabulary, trait rules, derived edge rules. Until today, changing any of this meant restarting the application. For iterative agent development, that's a friction wall: tweak a curiosity dampen factor, restart, observe, repeat. The feedback loop should be seconds, not minutes.

The fix is `CognitiveProfileWatcher` — a single `@ApplicationScoped` bean that watches configurable filesystem directories for YAML changes and applies them live, without restart.

## The atomicity problem

The obvious approach — make the profiles field volatile and swap it — works for `CognitiveDefaultsRegistry` because it's a single `Map.copyOf()` behind one volatile reference. But `DeclarativeRuleRegistry` has two related fields: global trait rules and global derived edge rules. Two independent volatile writes create a window where a reader sees new trait rules paired with old derived edge rules — a state that never existed as a coherent configuration.

The design review caught this. The fix is a `GlobalRules` holder record: a single immutable object containing both lists, behind one volatile reference. One write, one publication point, no torn reads. Standard concurrency pattern, but easy to miss when the fields look independent.

## Merge semantics

We wanted classpath profiles to remain the baseline — bundled with the application, always present. Filesystem profiles layer on top: same `agentId` in the filesystem overrides the classpath version; new `agentId`s get added. On reload, the watcher re-reads the filesystem directory, merges with the cached classpath snapshot, and does the atomic swap. If the filesystem directory is empty, you get pure classpath behaviour — backwards-compatible by default.

The watcher snapshots the classpath baseline from the already-initialized registries at `@PostConstruct` time, rather than re-scanning the classpath. CDI constructor injection guarantees the registries are fully loaded before the watcher's own init runs — no ordering annotation needed, no `@DependsOn`.

## Event-only when it matters

A tempting mistake: fire `CognitiveProfilesReloaded` on every directory change. But when only global rules change, firing a profiles event is both semantically wrong and wasteful — `CognitiveLoader` would re-register identical vocabulary for no reason. `DeclarativeRuleRegistry` already reads per-agent rules from the profiles registry on every call, so profile changes automatically propagate to rule resolution via the volatile swap. The event fires only for profile changes; rule-only changes need no notification at all.

## What's next

The deferred item is `MindMapStore.unregisterVocabulary()` — when a profile with vocabulary is removed from the filesystem, its edge type definitions stay as orphans in the store. They're inert metadata that doesn't affect correctness, but a clean unregistration SPI would complete the lifecycle. That's a follow-up, not a blocker.

The real payoff comes when this connects to agent development tooling: edit a YAML profile in your IDE, watch the agent's behaviour change within the debounce window. No restart, no redeploy — just write and observe.
