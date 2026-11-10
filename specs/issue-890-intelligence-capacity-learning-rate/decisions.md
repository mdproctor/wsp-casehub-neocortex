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

## D4: Dimension-to-site mapping

**Choice:** Single capacity dimension per site, mapped by cognitive substrate relevance:
- CapsWeightUpdater → relationalComplexity (cause-effect pattern depth; Halford 1998)
- CbrOutcome.adjustConfidence → workingMemorySpan (multi-factor outcome evaluation; Engle & Kane 2004)
- DriveAdaptationPhase → associativeReach (drive-outcome connection breadth; Mednick 1962)
- StrategyLearningOrchestrator → workingMemorySpan (multi-dimensional strategy tracking; Engle & Kane 2004)
- DefaultGraduationScorer → relationalComplexity (abstracting from experience; Halford 1998)
- PersonalityEvolutionOrchestrator → relationalComplexity (self-model complexity; Halford 1998)
**Alternatives:**
- Composite (weighted combination of dimensions per site) — more nuanced but harder to explain and test; one dimension per site is already a strong signal
- All sites use same dimension — ignores that the three dimensions measure distinct cognitive substrates
**Rationale:** Each capacity dimension maps to a distinct cognitive operation (Halford = depth, Mednick = breadth, Engle & Kane = context retention). Each learning site has a primary cognitive demand that aligns with one dimension.
**Trade-offs:** Loses multi-dimensional interaction effects (e.g., relational complexity AND working memory jointly affecting CAPS learning). Acceptable as a first realization — composite can be added later without API changes.
**Sources:** Halford (1998), Mednick (1962), Engle & Kane (2004), Cattell (1971)
**Exploration:** quick
**Status:** captured

## D5: CBR wiring — learningRateMultiplier on CbrOutcome

**Choice:** Add nullable `Double learningRateMultiplier` field to `CbrOutcome` record. Existing single-arg constructor defaults to null. Store implementations multiply schema's learningRate by the multiplier when non-null. Cognitive-layer callers (BehavioralSynthesisPhase) set it from agent's capacity.
**Depends on:** D4 (CBR uses workingMemorySpan)
**Alternatives:**
- Decorator on CbrRecordStore — introduces cognitive-index dependency into memory layer; decorator can't easily intercept the internal adjustConfidence call
- Per-agent schemas — caseType × agent proliferation; schemas are meant to be structural, not per-agent tuning
**Rationale:** CbrOutcome is a value object in memory-api (tier 1). Adding a nullable field is backwards-compatible — null means no modulation (existing behavior). The cognitive layer sets the field; the store layer applies it. Clean separation.
**Trade-offs:** Every CbrRecordStore implementation needs updating to check the multiplier. Acceptable — there are 4 implementations, and the change is 3 lines per.
**Sources:** CbrOutcome.java, InMemoryCbrRecordStore, QdrantCbrRecordStore, SqliteMemoryStore recordOutcome sections
**Exploration:** quick
**Status:** captured

## D6: CAPS and graduation wiring

**Choice:** Two site-specific wiring changes:
1. **CapsWeightUpdater** — add `double capacityMultiplier` parameter to `update()`. BehavioralSynthesisPhase resolves relationalComplexity from CognitiveDefaultsRegistry and passes it. Multiplies `baseAlpha` (not `salienceMultiplier` — salience is attention, not learning capacity).
2. **DefaultGraduationScorer** — add `Double capacityMultiplier` field to `GraduationContext`. ExperienceConsolidationPhase resolves relationalComplexity and sets it. Scorer multiplies the `minCorroboration` threshold inversely (higher capacity = lower bar for graduation).
**Depends on:** D4 (CAPS uses relationalComplexity, graduation uses relationalComplexity)
**Alternatives:**
- Inject CognitiveDefaultsRegistry into CapsWeightUpdater/DefaultGraduationScorer directly — higher coupling, harder to test, violates the current pattern where these are pure computation classes
**Rationale:** Both sites are pure computation called by higher-level orchestrators. The orchestrators already have access to agent context. Passing capacity as a parameter keeps the computation classes dependency-free.
**Trade-offs:** Adds a parameter to `update()` — all callers need updating. Only one non-test caller (BehavioralSynthesisPhase), so impact is minimal.
**Sources:** CapsWeightUpdater:48-66, DefaultGraduationScorer:33-41, BehavioralSynthesisPhase, ExperienceConsolidationPhase
**Exploration:** quick
**Status:** captured
