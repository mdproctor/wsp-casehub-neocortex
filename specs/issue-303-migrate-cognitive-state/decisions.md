# Decisions — blocks#303: Migrate Cognitive State

## D1: Migration scope — all cognitive code moves

**Choice:** Move all 8 orchestrators, CognitionCore, all supporting types,
Store SPIs, and the social cognition surface (prompt sections, civility
constraints) from blocks to neocortex.

**Alternatives:**
- Pure-computation only (4 orchestrators) — leaves the architecture
  half-migrated with cognitive state split across repos
- Move orchestrators but keep CognitionCore in blocks — CognitionCore
  would never be composed with anything else in blocks; it's a cognitive
  tick scheduler, same pattern as ConsolidationScheduler

**Rationale:** Applied the test "would this be useful or ever be used
without neocortex?" to every component. Every orchestrator, the tick
scheduler, and the social cognition surface failed — they all depend on
neocortex types, stores, or SPIs. The current split is a historical
accident, not a design choice.

**Trade-offs:** Larger migration scope. Blocks loses its social cognition
package entirely, becoming a generic agent framework. This is the correct
architecture — blocks provides lifecycle, tools, sessions, plans; neocortex
provides all cognitive computation.

**Sources:** blocks#303 issue body, blocks#296 (established the pattern),
blocks social/ package structure, neocortex CLAUDE.md module descriptions

**Exploration:** deep-analysis (first-principles dependency test on all 8
orchestrators + CognitionCore + social surface)

**Status:** captured

## D2: No circular dependency — clean one-way flow

**Choice:** Neocortex depends on platform (AgentProvider) and eidos
(AgentDescriptor). Blocks depends on neocortex cognitive module. No blocks
dependencies flow into neocortex.

**Alternatives:**
- Keep LLM orchestrators in blocks to avoid platform dependency — but
  neocortex already has this dependency via rag-query-augmentation

**Rationale:** Audited every blocks dependency used by the orchestrators.
All are either: platform types (already available to neocortex), eidos
types (independent), domain types that co-move, or thin utility wrappers
replaceable by platform types (StructuredAgentInvoker → AgentProvider).

**Trade-offs:** None — this is strictly cleaner than the current state.

**Sources:** blocks KeyedLock, StructuredAgentInvoker, ContentSummariser
usage analysis; rag-query-augmentation AgentProvider precedent

**Exploration:** deep-analysis

**Status:** captured

**Depends on:** D1

## D3: One module, package separation

**Choice:** Two Maven modules: `cognition-api` (SPIs, zero deps) and
`cognition` (all implementations). Internal package separation for
pure-computation vs LLM-backed orchestrators. No separate module for
LLM orchestrators.

**Alternatives:**
- Two impl modules (cognitive-orchestration + cognitive-orchestration-llm) —
  the split doesn't justify module overhead; if you install cognitive
  orchestration you want all of it
- Three+ modules with finer granularity — maintenance overhead without
  proportional benefit

**Rationale:** AgentProvider is a platform type available via
`Instance<AgentProvider>` with graceful degradation. One module is simpler
to maintain, test, and version. Package separation provides the logical
boundary without the build complexity.

**Trade-offs:** Cannot install pure-computation orchestrators without the
LLM ones on the classpath. Acceptable because the LLM orchestrators only
activate when AgentProvider is available.

**Sources:** Neocortex module naming conventions, existing module structure

**Exploration:** quick

**Status:** captured

## D4: Store consolidation onto existing neocortex abstractions

**Choice:** Consolidate blocks' ad-hoc Store SPIs onto existing neocortex
stores rather than transplanting them:
- NarrativeStore → CbrRecordStore (already uses CBR via CbrNarrativeStore)
- StrategyStore → CbrRecordStore (learned patterns with feature vectors)
- UserProfileStore → CaseMemoryStore (domain="user-profile")
- MentalModelStore → CaseMemoryStore (domain="mental-model") or MindMap
  nodes with traits

**Alternatives:**
- Transplant stores as-is with new SPIs — preserves proliferation of
  ad-hoc stores, each needing its own contract tests, backends, CDI wiring

**Rationale:** The separate stores were built before neocortex had these
abstractions. They solve problems that CaseMemoryStore (domain-scoped
temporal state), CbrRecordStore (structured similarity search), and
MindMapStore (graph relationships) now solve generically. Consolidation
inherits existing infrastructure: contract tests, multiple backends,
decorators, the CDI priority ladder.

**Trade-offs:** Requires mapping existing store schemas onto generic store
APIs. Domain-specific type safety achieved via thin typed query helpers
rather than full SPI hierarchies.

**Sources:** blocks NarrativeStore/CbrNarrativeStore, UserProfileStore,
MentalModelStore, StrategyStore; neocortex CaseMemoryStore, CbrRecordStore,
MindMapStore APIs

**Exploration:** quick

**Status:** captured

**Depends on:** D1

## D5: Fully optional — classpath + config activated

**Choice:** The cognition module is fully optional. If not on the classpath,
nothing activates. NoOp @DefaultBean fallbacks for all SPIs. Existing
neocortex cognitive code (cognitive-index, mindmap-intelligence) audited
for the same optionality guarantee.

**Alternatives:**
- None considered — this is a hard constraint from the user

**Rationale:** Neocortex serves multiple use cases (inference, RAG, CBR,
MindMap). Cognitive orchestration is one use case. Installing neocortex
for RAG shouldn't pull in cognitive tick scheduling. "Your install only
pays for it if the modules are present and turned on."

**Trade-offs:** Must ensure all cross-module references use Instance<>
or @DefaultBean for graceful degradation. Audit scope extends beyond
the migration itself.

**Sources:** Existing neocortex patterns: @DefaultBean (NoOpMindMapStore),
@IfBuildProperty (rag-crossencoder), Instance<> (mindmap-intelligence
consolidation phases)

**Exploration:** quick

**Status:** captured

## D6: Naming — "cognition" not "cognitive-orchestration"

**Choice:** Module names: `cognition-api`, `cognition`. Package root:
`io.casehub.neocortex.cognition`.

**Alternatives:**
- cognitive-orchestration — verbose, overly specific; this IS cognition,
  not just orchestration of cognitive processes
- social-cognition — too narrow; the module may grow beyond social contexts

**Rationale:** Existing `cognitive-*` modules use the adjective form
(cognitive-api, cognitive-index). "cognition" is the noun — the thing
itself. Clean, simple, accurate.

**Trade-offs:** None.

**Exploration:** quick

**Status:** captured
