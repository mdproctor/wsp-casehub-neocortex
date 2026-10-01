---
layout: post
title: "The Brain That Lived in the Wrong Body"
date: 2026-09-29
entry_type: note
subtype: diary
projects: [casehubio/neocortex, casehubio/blocks]
tags: [architecture, migration, cognitive, first-principles]
series: issue-303-migrate-cognitive-state
---

# The Brain That Lived in the Wrong Body

Neocortex is the cognitive engine. Blocks is the agent framework. And yet thirteen thousand lines of cognitive state computation — mood, drives, narrative, mental models, strategy learning, inner life, personality evolution — live in blocks, tightly coupled to neocortex types they can't function without.

I'd been aware of this for a while. The debt accumulated naturally: blocks was built first, the social cognition layer grew inside it, and neocortex grew underneath. By the time we had CaseMemoryStore, CbrRecordStore, MindMapStore, and the full cognitive-index layer, the orchestrators in blocks were already importing half of neocortex to do their work.

The original issue (blocks#303) scoped this as moving eight orchestrators. That turned out to be the wrong unit of analysis.

## The test that changed the scope

I applied one question to every component in blocks' social cognition package: *would this ever be used without neocortex?*

MoodOrchestrator? Its inputs and outputs are neocortex types — MoodState, MoodBaseline, MoodDecay. No.

DriveOrchestrator? Depends on MoodOrchestrator. No.

The four LLM-using orchestrators (UserModel, MentalModel, Strategy, InnerLife)? They use LLM calls to compute cognitive state transitions — BDI inference, strategy reflection, motivation assessment. The LLM is the reasoning engine, not the conversation layer. These are cognitive computation, not prompt assembly. No.

CognitionCore, the tick scheduler? It sequences cognitive orchestrators. If those orchestrators move, CognitionCore is just a cognitive tick scheduler — same pattern as ConsolidationScheduler in mindmap-intelligence. No.

The prompt sections that render cognitive state for conversations? They implement blocks' PromptSection interface. But would they be composed with anything else in blocks? No — they exist to serialize cognitive state, nothing more.

Every component failed the test. The entire social cognition layer — 213 production files, roughly 13,000 lines — belongs in neocortex.

## What blocks actually is

Once everything cognitive moves out, blocks becomes clear: it's a generic agent framework. Lifecycle, tools, sessions, plans, step execution. The conversation surface stays — SocialAvatarCognition and the prompt sections form a thin bridge that reads neocortex cognitive state and renders it for the LLM conversation. But the computation, the scheduling, the state management — all neocortex.

The dependency flows one way. Neocortex depends on platform (for AgentProvider) and eidos (for AgentDescriptor). Blocks depends on neocortex for cognitive state. No circular dependency. We audited every blocks dependency the orchestrators use — KeyedLock, StructuredAgentInvoker, ContentSummariser — and every one is either a platform type, a co-moving domain type, or a thin utility wrapper replaceable by a platform type.

## Two modules, not six

The initial instinct was to split: `cognition-api` for SPIs, `cognition` for base implementations, `cognition-llm` for LLM-backed orchestrators. But the split between base and LLM doesn't justify module overhead. If you're installing cognitive orchestration, you want all of it. AgentProvider is a platform type available via `Instance<AgentProvider>` with graceful degradation. One module, package separation for the internal organisation.

The naming went through a similar simplification. "cognitive-orchestration" is verbose and overly specific. "cognition" is the noun — the thing itself. The existing `cognitive-*` modules use the adjective form. This is the thing.

## Store consolidation

Each orchestrator had its own Store SPI — NarrativeStore, StrategyStore, UserProfileStore, MentalModelStore — with JPA implementations in blocks. These were built before neocortex had CaseMemoryStore and CbrRecordStore. They're ad-hoc solutions to problems that now have proper infrastructure.

Every one of them was already CBR-backed in practice. CbrNarrativeStore wraps CbrRecordStore. CbrStrategyStore wraps CbrRecordStore. We renamed them — NarrativeMemory, StrategyMemory, UserProfileMemory, MentalModelMemory — and dropped the SPI layer entirely. The typed wrappers provide domain-specific convenience methods over the generic stores. Three JPA modules get deleted.

## Where it stands

Three of seven batches complete: module scaffolding, 95 value types migrated to cognition-api, and the store consolidation. The foundation compiles. The remaining work is moving orchestrators (pure-computation first, then LLM-backed), the framework layer (CognitionCore, goal proposal, emergence), and updating the blocks bridge.

The cross-repo file moves surfaced an interesting tooling limitation — IntelliJ's `ide_move_file` doesn't handle cross-project transfers in workspaces, even when both repos are open. It deletes the source file, reports success, but the destination resolves incorrectly. We ended up writing a migration script that reads source files, transforms package declarations with ordered prefix matching, and writes to the target. A second pass fixes cross-subpackage imports using a type-to-package index built from the migrated files.

The optionality constraint shapes everything. If you install neocortex for RAG or inference, you shouldn't pay for cognitive tick scheduling. The existing modules already handle this well — `Instance<>` with `isResolvable()` throughout, `@DefaultBean` NoOps, config-gated features. The audit confirmed cognitive-index and mindmap-intelligence are already fully insulated. The new cognition module follows the same pattern.

The migration is mechanical from here. The design question — where does cognition live — is settled.
