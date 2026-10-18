# Decisions — Issue #400: Cognitive Section Calibration

## D1: Personality-cognition weighting model

**Choice:** Arousal-driven dynamic weighting — not a static dial, not a passive filter, not an override
**Alternatives:**
- Lens/filter — personality passively colours cognitive output. Too passive; empirical evidence shows personality actively drives behaviour, doesn't just tint it
- Override — personality suppresses cognitive data. Produces scripting (PP scored 2/5 with prescriptive tendencies)
- Static weighting — configurable dial between personality and cognition. Doesn't capture that the balance shifts with emotional intensity
**Rationale:** Empirical session findings: high arousal → personality dominates (you fall back to deep defaults under pressure); low arousal → cognitive data has room. PAD arousal is the natural control signal. HC's predatory satisfaction overwhelms social rules; PP's instinct and learned behaviour integrate when calm.
**Trade-offs:** Requires formation memory PAD data to compute the scalar — depends on memory seeding infrastructure (#398)
**Sources:** casehubio/examples#97 Phase 4 calibration experiments, wacky-manor HC/PP/Mob character testing session
**Exploration:** quick
**Status:** captured

## D2: Mechanism — tiered sections with derived boundaries

**Choice:** Three fixed tiers (Core / Contextual / Supplementary) with binary activation gated by arousal. Tier boundaries per-agent derived from personality-dominance scalar, not statically assigned.
**Alternatives:**
- Coordinator — centralised pre-render pass decides per-section. Fragile: coordinator must understand semantics of every section
- Self-aware sections — each renderer gets arousal context and adjusts. Too distributed: arousal logic changes require touching every renderer
- Static tier tags — sections statically tagged with tier. Doesn't capture per-agent variation (HC's tiers are almost all core; PP's are balanced)
**Rationale:** Tiers match real cognition: under high arousal, higher-order cognition shuts off and instinct takes over. The transition is a mode switch, not gradual. The tier abstraction is right; the assignment per-agent is what varies.
**Trade-offs:** Per-agent tier boundary variation requires the CDE derivation chain to be in place
**Sources:** Empirical: removing supplementary sections improved emergence in every test. Binary suppression IS reinforcement — fewer competing signals means core tier's personality signal gets louder.
**Exploration:** quick
**Status:** captured

## D3: Tier assignment — fixed by section nature

**Choice:** Section-to-tier mapping is fixed by section nature, identical across all agents:
- **Core** (always renders): Mood, Drives, Appraisal, Behavioral, CharacterDrives*, NeedsPyramid
- **Contextual** (situational): UserModel, MentalModel, Narrative, Attention, TemporalFocus
- **Supplementary** (low arousal only): Strategy, EmergentGoals, Reflection, Consolidation, Constraints (soft)

*CharacterDrives already conditionally suppressed when CARMA appraisal is active (existing mutual exclusion in promptSections()).

What varies per agent is the arousal threshold at which lower tiers activate, not which tier a section belongs to.
**Alternatives:**
- Per-agent section-to-tier mapping — sleep derives individual tier per section. Unnecessary: section nature (somatic vs cognitive) is stable; the content already varies per agent
- Per-category weights — weight per category rather than per section. Adds complexity without benefit since tier boundaries already handle the gradation
**Rationale:** Mood is always more somatic than goals, regardless of character. The personality-dominance scalar controls WHERE the cutoff is, not WHAT is above/below it.
**Trade-offs:** If a future section doesn't fit cleanly into one tier, the classification becomes a judgment call
**Sources:** CognitionCore.promptSections() ordering, CharacterDrivePromptSection conditional suppression (line 502)
**Exploration:** quick
**Status:** captured

## D4: Binary tier activation — no condensation, no reinforcement labels

**Choice:** Tiers are on or off. No condensed intermediate rendering state. No disposition-reinforcement text when suppressed.
**Alternatives:**
- Gradual condensation (full → condensed → suppressed) — adds complexity to every section renderer for marginal benefit. Tier boundaries already handle gradation via the scalar
- Disposition reinforcement lines when suppressed ("Your gallant nature guides you here") — reintroduces third-person briefing scripting that 9 runs eliminated. Somatic core tier IS the reinforcement
**Rationale:** Empirically proven: every time sections were reduced, personality signal strengthened. Suppression IS reinforcement. Real cognition is binary under high arousal — higher-order processing shuts off, instinct takes over.
**Trade-offs:** No graceful degradation — tiers snap on/off. Acceptable because the scalar's per-agent threshold IS the gradation mechanism.
**Sources:** Wacky-manor experiments: removing PP's tendencies improved emergence, removing formation memory static dump improved emergence
**Exploration:** quick
**Status:** captured

## D5: Personality-dominance scalar — single value in CognitiveDefaults

**Choice:** One `personalityDominance` double (0.0-1.0) per agent, stored as the 18th field in CognitiveDefaults. Derived by CDE from formation memory PAD patterns: `reward_from_personality_actions / total_reward`.
**Alternatives:**
- Per-section weights — each section gets its own weight. Requires sleep to reason about individual cognitive subsystems. Unnecessary: section nature is stable
- Per-category weights — weight per somatic/relational/cognitive category. Adds a layer of indirection for no benefit
- Separate TierConfig record — fragments the cognitive defaults model for no benefit. The scalar is a CDE derivation output, same pattern as the other 17 fields
**Rationale:** Directly computable from data we already have. HC: only personality-driven ages produce positive P+D → ~0.9. PP: mix of instinct and learned behaviour → ~0.5. One number, one derivation, one place to look.
**Trade-offs:** Requires formation memories with PAD tags to compute. Falls back to a default (0.5?) when no formation memories exist.
**Sources:** CognitiveDefaults record (17 existing fields), CognitiveDerivationEngine (9 existing pathways)
**Exploration:** quick
**Status:** captured

## D6: Derivation chain — CDE 10th pathway, not consolidation phase

**Choice:** CognitiveDerivationEngine adds a 10th derivation pathway: personality profile → personalityDominance. NOT a new consolidation phase.
**Alternatives:**
- New consolidation phase (TierDerivationPhase) — would be right if tier assignment required examining raw memories. But it doesn't — it examines the pattern that sleep already extracted from memories
- Extend BehavioralSynthesisPhase — behavioral synthesis is about BEHAVIOR (CAPS → attractors), not rendering priority. Different concern
**Rationale:** The CDE already derives operational parameters from personality input. This follows the same pattern. Keeps rendering logic out of the consolidation pipeline where it doesn't belong. The CDE needs to evolve from accepting only disposition input to accepting the richer sleep-derived personality profile.
**Trade-offs:** CDE currently takes DescriptorView (disposition axes + profile). Needs to accept formation memory PAD summary as additional input for the 10th pathway.
**Sources:** CognitiveDerivationEngine (9 existing pathways), BehavioralSynthesisPhase
**Exploration:** quick
**Depends on:** D5 (scalar lives in CognitiveDefaults)
**Status:** captured
