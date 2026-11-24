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
**Rationale:** Briefing and emergence are orthogonal approaches to reasoning-shaping, not layers of one stack. They share infrastructure but differ in how reasoning is shaped. Emergent branch has zero briefing (identity emerges). Briefed branch has full identity declaration (static, never drifts). Designing for future unification — one composable stack, not two competing ones.
**Trade-offs:** Requires careful abstraction of the shared infrastructure boundary. CognitionCore doesn't get simpler — a new composition root sits alongside it.
**Sources:** cognition/CognitionCore.java, cognition-api/CognitionPromptRenderer.java, agency briefing mechanism
**Exploration:** deep-analysis
**Status:** captured

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
**Rationale:** Existing validated pattern from agency: three-layer briefing (identity establishment, character grounding with specific references, behavioral echo). The echo is deeper than style — it shapes substance (what the agent values, how it reasons, what it draws on). Instructs model to draw on the avatar's memories and experiences. Carefully-worded sentences empirically validated to keep persona consistent across long sessions without resending full system prompt.
**Trade-offs:** Static text means the echo can't adapt to context. The same reminder fires whether the agent is planning goals or answering a simple question.
**Sources:** agency/agentic-yaml descriptors, CognitivePreambleGenerator (emergent-tier equivalent)
**Exploration:** deep-analysis
**Status:** captured

## D5: Module structure

**Choice:** New `cognitive-runtime` module between cognitive-index and cognition
**Alternatives:**
- Extend cognitive-index — grows it beyond "index" into "runtime"
- New "avatar" module — distinct consumer-facing name, but naming mismatch with composable intent
**Rationale:** Clean separation: cognitive-index stays pure types/utilities, cognition stays emergent-specific (tick loop, CAPS, emotions), cognitive-runtime owns composition root, capability wiring, briefing renderer, shared prompt rendering chain. Enables future unification where cognition becomes one configuration of cognitive-runtime.
**Trade-offs:** New module in an already large module tree. Must be careful not to duplicate functionality from cognitive-index or cognition.
**Sources:** Module dependency analysis, consumer-guide.md
**Exploration:** quick
**Status:** captured

## D6: Persona library scope

**Choice:** Ship all 5 pre-built personas (stoic mentor, thorough planner, bold strategist, pragmatic assistant, custom)
**Alternatives:**
- 2 contrasting + custom — validates mechanism with minimal scope
- 1 reference + custom — fastest to validate
**Rationale:** User preference for complete delivery. All 5 are YAML profiles with no additional code per persona — the mechanism is the work, not the profiles.
**Trade-offs:** More testing surface for validation. Each persona needs empirical tuning of the echo sentences.
**Sources:** Issue #1219 persona library section
**Exploration:** quick
**Status:** captured

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
