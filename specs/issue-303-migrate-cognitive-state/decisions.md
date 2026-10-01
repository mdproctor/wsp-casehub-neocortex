# Decisions — blocks#303: Migrate Cognitive State

## D1: Migration scope — complete extraction, no bridge

**Choice:** Move ALL cognitive code to neocortex — orchestrators,
CognitionCore, prompt rendering, defaults, rendering utilities. No bridge
layer remains in blocks. Blocks retains only: a thin AvatarCognition
adapter (blocks' speech lifecycle → CognitionCore), and the YAML DSL
(CognitionCompiler + spec records with import updates).

**Supersedes:** Original D1 kept prompt sections and SocialAvatarCognition
in blocks as a "bridge layer." Revised after first-principles analysis:
neocortex is the complete single-agent cognitive stack. A cognitive LLM
agent doesn't need blocks at all — blocks adds multi-agent orchestration.
The "bridge" was a migration artifact, not an architectural boundary.

**Alternatives:**
- Bridge layer in blocks (original D1) — SocialAvatarCognition and prompt
  sections stay in blocks, forwarding to neocortex. Creates permanent
  technical debt: blocks code tightly coupled to cognitive internals,
  forwarding calls without adding value.
- Pure-computation only — leaves architecture half-migrated

**Rationale:** Applied the test: "for a single cognitive agent, does it
need blocks?" No. All drivers, ticks, prompt rendering, state management
are neocortex concerns. Blocks' role is multi-agent orchestration and
declarative configuration (YAML/annotation DSL). The prompt rendering
system is cognitive — it's how the brain presents itself to the LLM.

**Trade-offs:** Larger scope than original D1 (prompt sections move too).
Blocks' speech-api PromptSection interface stays in blocks — neocortex
defines its own rendering, blocks adapts if needed.

**Sources:** blocks#303, architectural discussion 2026-09-30

**Exploration:** deep-analysis

**Status:** captured (revised 2026-09-30)

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

## D7: Prompt rendering is cognitive — moves to neocortex

**Choice:** The composable prompt rendering system (23 prompt sections,
AffordanceRenderer, CognitiveObservationSections, CognitiveSystemPromptRenderer)
moves to neocortex cognition. CognitionCore.promptSections() composes them.
The rendering system is how the cognitive engine presents itself to the LLM.

**Alternatives:**
- Keep in blocks as bridge — creates permanent coupling, prompt sections
  are tightly bound to cognitive types they render, not to blocks
  infrastructure
- Replace with JSON serialization — tested and rejected; the composable
  prose rendering was built through multiple design iterations for
  behavioral conditioning effectiveness. JSON may work for some domains
  (neocortex#390 will evaluate) but the existing system shouldn't be
  discarded based on theory

**Rationale:** Cohesion principle — prompt sections are coupled to the
cognitive types they render. When a cognitive type changes, its prompt
section changes. They belong together. The rendering format (prose vs JSON
vs hybrid) should be pluggable per driver (neocortex#390).

**Sources:** architectural discussion 2026-09-30

**Exploration:** deep-analysis

**Status:** captured

## D8: Cognitive brief — eidos base + evolved layer

**Choice:** The cognitive brief (system-prompt-level instructions on how to
think and use cognitive capabilities) has two layers:
1. Base layer (eidos prompt cycle) — stable identity, capabilities,
   personality-driven reasoning style
2. Evolved layer (cognition) — learned adaptations from experience,
   evolved autonomously via consolidation phase (neocortex#391)

CognitionCore does not need a bootstrap step — eidos handles the base
brief. CognitionCore provides dynamic state. Both compose in the system
prompt.

**Alternatives:**
- CognitionCore generates the brief — wrong separation; the brief is
  identity (eidos), not runtime state (cognition)
- Static brief — misses the opportunity for metacognitive improvement

**Rationale:** CognitiveDerivationEngine already derives cognitive config
from eidos (DescriptorView → CognitiveDefaults). The brief is the prose
version of that derivation. Evolution is autonomous — no lifecycle hook
needed; consolidation infrastructure handles timing.

**Sources:** architectural discussion 2026-09-30, neocortex#391

**Exploration:** deep-analysis

**Status:** captured

## D9: Cognitive lifecycle follows orchestrator pattern

**Choice:** The cognitive lifecycle uses the established orchestrator
pattern: mechanical steps execute deterministically, the LLM receives
commands at defined points when judgment is needed.

Every lifecycle phase is mechanical + LLM commands:
- Tick: mechanical (compute state) → LLM command (appraise) → mechanical
- Prompt rendering: mechanical (collect state) → render per config
- Brief evolution: mechanical (collect observations) → LLM (evaluate)
- Consolidation: mechanical (detect candidates) → LLM (summarize)

**Rationale:** CognitionCore already uses this pattern (AgentProvider for
mood appraisal, BDI extraction). Making it explicit and consistent across
all lifecycle phases creates a uniform architecture.

**Sources:** architectural discussion 2026-09-30

**Exploration:** quick

**Status:** captured

**Depends on:** D7, D8

## D10: Internal cognitive LLM calls use separate context

**Choice:** Internal cognitive processing (mood appraisal, BDI extraction,
brief evolution, consolidation summaries) uses separate LLM calls via
AgentProvider — never the main conversation context window. Each cognitive
command is a focused, short-lived call with minimal context scoped to that
specific task.

Could use cheaper/smaller models for mechanical cognitive tasks (mood
classification, signal extraction) where full capability isn't needed.

**Alternatives:**
- Use the main conversation LLM — wastes the expensive conversation
  context window on internal processing; context is precious for the
  actual conversation

**Rationale:** The main LLM context holds the brief, cognitive state,
conversation history, and user message. Internal cognitive computation
should not compete for this space. AgentProvider already provides the
separation — this decision makes it an explicit architectural constraint.

**Sources:** architectural discussion 2026-09-30, existing CognitionCore
AgentProvider usage pattern

**Exploration:** quick

**Status:** captured

**Depends on:** D9
