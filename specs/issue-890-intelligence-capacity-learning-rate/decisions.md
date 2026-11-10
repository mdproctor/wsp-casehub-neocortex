# Decisions — #890 Intelligence Capacity Learning Rate Modulation

## D1: Scope — Full learning sweep

**Choice:** Modulate all 6 unmodulated learning/adaptation sites, not just memory subsystem
**Alternatives:**
- Memory-focused (CBR + graduation only) — tighter scope, matches issue description literally, but leaves Investment Theory half-realized
- Memory + CAPS only — covers pattern acquisition but misses drive/strategy/personality adaptation
**Rationale:** Cattell's Investment Theory implies cognitive capacity pervades all learning, not just memory. Partial application would create inconsistency — some subsystems capacity-aware, others not.
**Trade-offs:** Scale increases from M to L. Touches many modules across memory, cognition, CAPS, and mindmap-intelligence.
**Sources:** Issue #890, Cattell (1971) Investment Theory
**Exploration:** quick
**Status:** captured

## D2: Modulation formula — Linear multiplier with ceiling exception

**Choice:** `effectiveLR = baseLR * capacityDimension` for 5 of 6 sites. PersonalityEvolutionOrchestrator uses ceiling pattern (scale `l2Ceiling` by capacity).
**Alternatives:**
- Ceiling bound for all — matches SearchBudget pattern but awkward for already-small learning rates
- Logarithmic scaling — diminishing returns, but compressed [0.55, 0.95] range already provides that implicitly; adds complexity for negligible differentiation
- Asymmetric scaling (novel vs routine) — theoretically grounded in Investment Theory but differentiation smaller than system noise in the [0.55, 0.95] band; refinement for later
**Rationale:** Matches established codebase pattern (regulation uses `alpha * (1 - depletion)`, drive adaptation uses `lr * (1 - satisfaction)`). One mental model for how capacity flows through the system. PersonalityEvolution exception because `l2Ceiling` is already a ceiling — scaling a ceiling is more natural than multiplying a decay rate.
**Trade-offs:** Loses Investment Theory asymmetry (Gf helping novel patterns more than routine). Acceptable because compressed capacity range makes the practical difference negligible.
**Sources:** CapsWeightUpdater:48-66, DriveAdaptationPhase:220-248, EmotionRegulationTickParticipant:105-108, PersonalityEvolutionOrchestrator:103-110, Cattell (1971)
**Exploration:** deep-analysis
**Status:** captured

## D3: Documentation — Literature-linked Javadoc on all capacity modulation

**Choice:** Every modulation site gets Javadoc citing the literature or design decision that justifies the formula and dimension mapping.
**Alternatives:**
- Code-only (no Javadoc) — faster but loses the "why" for future readers
**Rationale:** User requirement. Capacity modulation is psychologically grounded — the mapping from capacity dimension to learning site is a design claim, not an implementation detail. Without Javadoc linking to Cattell, Halford, Mednick, Engle & Kane, the code reads as arbitrary multipliers.
**Trade-offs:** More verbose code. Acceptable because these are permanent architectural decisions.
**Sources:** User directive
**Exploration:** quick
**Status:** captured
