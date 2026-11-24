# Design Decisions — #1219 Briefed Cognitive Avatars

## D1: Profile format

**Choice:** Same CognitiveDefaults YAML format with a subset of fields
**Alternatives:**
- New simpler persona-specific format — cleaner author UX but adds translation layer
- Layered composition (thin persona layer referencing base profile) — extra indirection
**Rationale:** CognitiveDefaultsRegistry already handles partial profiles. No new parsing code. A persona can be progressively enriched as the consumer enables more capabilities.
**Trade-offs:** Persona authors see the full CognitiveDefaults schema even though they only use a subset. Documentation must make clear which fields matter for briefed mode.
**Sources:** cognitive-index/CognitiveDefaults.java, cognitive-index/CognitiveDefaultsRegistry.java, test profiles alice.yaml/minimal.yaml
**Exploration:** quick
**Status:** captured

## D2: Architecture — shared infrastructure + pluggable reasoning-shaping

**Choice:** Shared cognitive infrastructure (memory, goals, temporal focus, disposition config, MindMap) + pluggable reasoning-shaping layer (briefing OR emergence)
**Alternatives:**
- Monolithic "briefed mode" module separate from cognition — creates competing stacks
- Refactor CognitionCore to be the single composition root — too invasive
**Rationale:** Briefing and emergence are orthogonal approaches to reasoning-shaping, not layers of one stack. They share infrastructure but differ in how reasoning is shaped. Emergent branch has zero briefing (identity emerges). Briefed branch has full identity declaration (static, never drifts). The shared infrastructure is the CDI service layer (MindMapStore, CaseMemoryStore, GoalProposalOrchestrator, TemporalFocusOrchestrator, EffectiveCognitiveDefaults) — these are standalone CDI beans that both composition roots can inject independently. No extraction from CognitionCore is required. Aspirational: future unification toward one composable stack is supported by this architecture but is not a prerequisite for the design to be correct.
**Trade-offs:** Requires careful abstraction of the shared infrastructure boundary. CognitionCore doesn't get simpler — a new composition root sits alongside it.
**Sources:** cognition/CognitionCore.java, cognition-api/CognitionPromptRenderer.java, agency briefing mechanism
**Exploration:** deep-analysis
**Status:** revised — clarified shared infrastructure as CDI service layer, downgraded "future unification" from primary rationale to aspiration (R1-06, R1-12)

## D3: Briefing location

**Choice:** Briefing text as a field on CognitiveDefaults profile YAML
**Alternatives:**
- Consumer-owned (agency/MCP writes identity text) — neocortex never sees persona narrative
- Split: identity in profile, grounding in consumer — composed at render time
**Rationale:** Neocortex owns the full persona definition end-to-end: identity text + disposition config + capability flags. Consumers just render what neocortex provides. Consistent with neocortex owning CognitiveDefaults.
**Trade-offs:** Consumers can't customise briefing text without forking the profile. Consumer-specific grounding (situational details) must be handled separately.
**Sources:** agency/agentic-yaml briefing field, ConversationRunner.buildSystemPrompt()
**Exploration:** quick
**Status:** captured

## D4: Echo mechanism

**Choice:** Per-prompt identity anchor — static briefing text rendered as a prompt section every turn
**Alternatives:**
- Decision-point triggers (fire at specific phases) — over-engineered for the actual need
- Dynamic echo generation (LLM-generated reminders) — defeats the purpose of static identity
**Rationale:** Rigorously validated pattern: three-layer briefing (identity establishment, character grounding, behavioral echo). Era 1 research (880+ events, P25-P30) proved echo does not decay (0.04 drop across hundreds of events), produces substantive character reasoning (not surface style), and creates a compounding feedback loop with memory. The L1 emotional echo instruction ("What are you FEELING right now — not thinking, feeling? Name it. Remember your voice...") scored mean 4.06 vs 3.54 baseline. Critical finding: template/prescriptive echo SUPPRESSES character (scored below no-instruction control) — echo must be evocative. The echo instructs the model to draw on the avatar's memories and experiences, grounding responses in accumulated knowledge.
**Trade-offs:** Static text means the echo can't adapt to context. The same reminder fires whether the agent is planning goals or answering a simple question. Must avoid prescriptive templates — each persona's echo needs careful evocative crafting.
**Sources:** agency/agentic-yaml descriptors, era1-character-taxonomy-research.md, era3-cognitive-layering-research.md, eidos#129 minimal-briefing experiment, CognitivePreambleGenerator (emergent-tier equivalent)
**Exploration:** deep-analysis
**Status:** captured

## D5: Module structure

**Choice:** New `cognitive-runtime` module between cognitive-index and cognition
**Alternatives:**
- Extend cognitive-index — grows it beyond "index" into "runtime"
- New "avatar" module — distinct consumer-facing name, but naming mismatch with composable intent
**Rationale:** Clean separation: cognitive-index stays pure types/utilities, cognition stays emergent-specific (tick loop, CAPS, emotions), cognitive-runtime owns composition root, capability wiring, briefing renderer, shared prompt rendering chain. Module boundary prevents accidental coupling between briefed and emergent concerns — stronger than package boundaries. Aspirational: may enable future unification, but the module stands on separation-of-concerns merits alone.
**Trade-offs:** New module in an already large module tree. Must be careful not to duplicate functionality from cognitive-index or cognition.
**Sources:** Module dependency analysis, consumer-guide.md
**Exploration:** quick
**Status:** revised — removed "future unification" as primary rationale, stands on separation-of-concerns merits (R1-12)

## D6: Persona library scope

**Choice:** Ship 2 contrasting + custom (stoic mentor + bold strategist + custom)
**Alternatives:**
- All 5 pre-built personas — ships complete set but front-loads echo authoring for 5 personas
- 1 reference + custom — fastest to deliver but doesn't stress-test disposition spectrum
**Rationale:** The echo mechanism is proven — rigorously validated across 880+ events with quantitative scoring (era1-character-taxonomy-research, era3-cognitive-layering-research, eidos#129 minimal-briefing experiment). Echo does not decay (0.04 drop over hundreds of events), produces substantive character reasoning, and creates a compounding feedback loop. However, research shows template-based echo actively suppresses character expression (scored below no-instruction control). Each persona needs its own evocative (not prescriptive) echo sentences. Two personas at opposite ends of the disposition spectrum validate that the proven echo patterns transfer to this new briefed-avatar context. Custom lets early adopters build their own.
**Trade-offs:** Smaller initial library. Remaining personas are low-risk iteration-2 additions once the first two confirm the echo pattern.
**Sources:** Issue #1219, era1-character-taxonomy-research.md (P25-P30), era3-cognitive-layering-research.md, eidos#129 minimal-briefing experiment
**Exploration:** deep-analysis
**Status:** revised — reduced from 5 to 2+custom; rationale corrected to reflect proven echo mechanism (R1-04, user correction)

## D8: Composition root design

**Choice:** Three-layer composition model — capability SPIs + CognitiveAvatar root + pluggable reasoning strategy
**Alternatives:**
- Flat composition (no capability abstraction, wire renderers directly) — simpler but not extensible
- CognitionCore refactoring (make existing root support both modes) — too invasive, couples briefed to emergent internals
**Rationale:** Each cognitive capability (briefing, goals, temporal, memory, entity knowledge, disposition) is a self-contained unit with a consistent interface. CognitiveAvatar wires available capabilities based on the profile and provides renderPromptSections() + per-capability API access. The reasoning-shaping strategy is pluggable: briefed (static identity text, no tick) vs emergent (CognitionCore tick loop) vs hybrid (future). Enables progressive composition — consumers add capabilities incrementally.
**Trade-offs:** Abstraction cost — capability SPIs add an interface layer. Must avoid over-engineering the capability interface before we know what all capabilities need.
**Sources:** CognitionCore.java tick/render architecture, CognitionPromptRenderer SPI, agency briefing mechanism
**Exploration:** deep-analysis
**Depends on:** D2 (shared infrastructure + pluggable reasoning), D5 (cognitive-runtime module), D7 (progressive composition)
**Status:** captured

## D7: Progressive capability composition

**Choice:** Capabilities are independently togglable — consumers opt into layers incrementally
**Alternatives:**
- Fixed tiers (briefed = set A, emergent = set B) — simpler but rigid
- All-or-nothing (briefed mode is a single boolean) — loses composability
**Rationale:** The briefed tier isn't a fixed feature set — it's the bottom rung of a capability ladder. Start with static persona + briefing, add persistent memory, add goals, add temporal awareness. Each capability is a self-contained unit. Enables learning what works before committing to full composition. Future unification with emergent stack becomes natural — just add more capabilities.
**Trade-offs:** More complex wiring. Each capability must be independently testable and composable. Order-of-composition edge cases.
**Sources:** User design intent, CognitionConfig feature flags pattern
**Exploration:** deep-analysis
**Status:** captured

## D9: Consumer API — interface segregation for briefed vs emergent

**Choice:** Introduce `CognitivePromptSource` as a narrower interface; `CognitiveLifecycle` extends it
**Alternatives:**
- CognitiveAvatar implements CognitiveLifecycle with no-op tick/recordInteraction — simpler for consumers but violates LSP (3 of 6 methods are no-ops)
- Separate interfaces with no inheritance — consumers must handle two unrelated types
**Rationale:** `CognitiveLifecycle` has 6 methods. `tick()` and `recordInteraction()` are abstract with no defaults and are meaningless for briefed agents. Interface Segregation Principle: `CognitivePromptSource` owns `initialize()`, `promptSections()`, `contributeBlocks()`. `CognitiveLifecycle` extends it, adding `tick()`, `recordInteraction()`, `evaluateProactive()`. CognitionCore implements `CognitiveLifecycle` (unchanged). CognitiveAvatar implements `CognitivePromptSource` (clean contract). Consumers that only need prompt rendering depend on the narrower interface.
**Trade-offs:** Existing consumers of CognitiveLifecycle are unaffected (supertype added, no methods removed). New consumers must choose which interface to depend on.
**Sources:** cognition-api/CognitiveLifecycle.java, CognitionCore.java (implements CognitiveLifecycle)
**Depends on:** D8 (CognitiveAvatar composition root)
**Exploration:** surfaced by review
**Status:** captured

## D10: Eidos registration — briefed agents are neocortex-local

**Choice:** Briefed agents do NOT register with eidos
**Alternatives:**
- Require eidos registration for all agents — one identity source, coherence validation, routing/capability probing, but heavyweight dependency for lightweight agents
- Optional eidos registration — consumers choose, but adds a decision point and two code paths
**Rationale:** Briefed agents are lightweight neocortex-local constructs: no tick loop, no consolidation, no experience recording, no multi-agent routing. They don't need eidos routing (consumers explicitly create them), capability probing (consumers know capabilities from the profile), or eidos system prompt rendering (they use the neocortex cognitive prompt pipeline via CognitivePromptSource). Requiring eidos registration imposes JPA persistence, registry management, and the full eidos stack on what should be a simple YAML-defined persona. If a future use case requires eidos participation, D7's progressive composition supports upgrading to eidos registration without upgrade.
**Trade-offs:** Briefed agents can't participate in eidos-based orchestration without upgrade. BriefingCoherenceValidator (eidos) can't validate briefed profiles — neocortex must provide its own validation.
**Sources:** Issue #1219 requirements, EidosDescriptorViewSource.java, AgentDescriptor.java
**Exploration:** surfaced by review
**Status:** captured
