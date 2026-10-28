# Interpersonal Relational Schemas — Per-Relationship Awareness for the Cognitive Pipeline

**Issue:** casehubio/neocortex#477
**Date:** 2026-10-28
**Status:** Draft

## Problem

The cognitive pipeline processes every interaction as if the other party is anonymous. `AppraisalContext` carries drives, mood, disposition, and habituation — but no information about WHO the agent is interacting with. A psychopath appraising "someone was kind to me" cannot distinguish whether the kind person is prey (exploit the trust), an obstacle (dismiss it), or a genuine ally (accept it cautiously).

### Verified gaps

| Component | What exists | What's missing |
|-----------|-------------|----------------|
| `AppraisalContext` | Drives, mood, disposition, habituation | No interaction target, no relational schema, no AMPD facets |
| `LlmAppraisalStrategy` | System prompt mentions disposition | No per-relationship context in user message |
| `OtherModelDerivationPhase` | Creates per-pair mental model nodes (empathic_sensing, inferred_values, appraisal_sensitivities, relational_understanding) | Output is disconnected from prompt rendering |
| `RelationshipStagePhase` | Computes familiarity scalar on overlays | Doesn't feed back into appraisal or CAPS |
| `BehavioralSynthesisPhase` | Creates CAPS-generated attractors | Attractors are global, not per-relationship |
| Eval YAML | RelationalSchema (target/role/trust/intimacy/utility) + AttachmentProfile (style/anxiety/avoidance) + AMPD facets | Eval-only — no production types |
| CAPS topology | 6 Bowlby attachment inputs, self/other mediating models, social outputs | Situational, not relational — no per-person biasing |

### What already works

Villain drift is partially mitigated by:
- **Disposition-weighted CAPS connections** — psychopathic dispositions have different connection strengths (e.g., bold riskAppetite boosts BAS, reduces threat sensitivity)
- **Behavioral attractors** — crystallized tendencies resist the LLM's prosocial bias ("You have a deeply ingrained predatory satisfaction")
- **CARMA appraisal** — LLM sub-call receives disposition axes and generates personality-filtered SEC dimensions
- **ConflictInterpretation** — DISENGAGE amplifies negative interaction weight in trust computation

These mechanisms work at the agent-global level. The gap is per-relationship differentiation.

### Two AppraisalContexts — distinct concerns

The codebase has two `AppraisalContext` records:

1. **`io.casehub.neocortex.mindmap.AppraisalContext`** (mindmap-api) — carries `Map<String, Double> relationshipScores` for node surfacing and attention priority decisions. These are scalar attention weights that influence which mind map nodes get surfaced during consolidation.

2. **`io.casehub.neocortex.cognition.appraisal.AppraisalContext`** (cognition-api) — the one this spec modifies. Carries structured psychological context for the cognitive appraisal process (situation assessment, emotional response generation).

These serve different layers: the mindmap-api `relationshipScores` are attention/surfacing weights (how much cognitive attention to allocate to nodes related to this person), while the cognition-api `RelationalSchema` provides emotional/behavioral context (how the agent feels about and should behave toward this person). They are complementary, not redundant.

## Scope

This spec addresses a subset of #477's four-layer architecture:

| Layer | #477 scope | This spec | Status |
|-------|-----------|-----------|--------|
| 1 — Formation | Childhood → personality schemas | — | Deferred (requires #398 memory seeding) |
| 2 — Traits | AMPD 25 facets, PCL-R, Dark Triad | Extends existing `AmpdFacets` with origin metadata | Partial — facet scores exist; origins are new |
| 3 — Relational | Attraction/repulsion, connection/disconnection, longing/indifference | Trust, intimacy, utility (cognitive assessment dimensions) | Partial — emotional dimensions deferred |
| 4 — Dynamic | Personality-filtered appraisal, PAD updates | Trust update, role evolution, CAPS biasing | Covered |

**Intentionally deferred:**
- **Layer 1 formation schemas** — depends on #398 memory seeding infrastructure. Formative experience data already flows through `FormationPadSummary` for personality dominance derivation; schema-level modelling (Schema Therapy 18 EMS, TA life scripts) requires richer formation memory structure.
- **Layer 3 emotional dimensions** — attraction/repulsion, connection/disconnection, longing/indifference map to PAD per-relationship overlays and are architecturally distinct from the cognitive assessment dimensions (trust, intimacy, utility) addressed here. The cognitive dimensions serve the appraisal pipeline; the emotional dimensions serve PAD mood overlays.
- **PCL-R four-facet mapping and Dark Triad/Tetrad integration** — the AMPD 25 facets subsume these for the appraisal use case; explicit cross-mapping is research scope.

Each deferred item should be captured as a GitHub issue linked to #477.

## Design

### Data model

Promote the existing eval schema to production types. Three record types, stored as structured properties on perspectival overlay nodes in the PERSON subgraph.

#### RelationalSchema

Per-agent-per-target relational state. One per overlay node.

```java
// In cognitive-index — structurally analogous to DispositionAxes
// (psychological model of how an agent views a relationship)
public record RelationalSchema(
    String targetId,         // agent ID of the other party
    String role,             // prey, obstacle, threat, tool, ally, mentor, protectee, stranger
    double trust,            // [-1, 1] — how much the agent trusts this person
    double intimacy,         // [0, 1] — emotional closeness
    double utility,          // [0, 1] — instrumental usefulness
    @Nullable String description  // free-text felt description
) {
    // Property key prefix for overlay storage
    public static final String PREFIX = "rel.";

    public Map<String, String> toProperties() { ... }
    public static @Nullable RelationalSchema fromProperties(Map<String, String> props) { ... }
}
```

**Module placement:** `cognitive-index`. `RelationalSchema` is a cognitive construct — a psychological model of how an agent views a relationship — not a storage primitive. It is structurally analogous to `DispositionAxes` (psychological model of personality traits) which also lives in `cognitive-index`. The storage mechanism (overlay properties) is an implementation detail; the type itself is a cognitive concept. `cognition-api` already depends on `cognitive-index`, so no new dependency is required.

#### PersonalityProfile (composite record)

`CognitiveDefaults` currently has 19 fields, each `withX` method threading all 19 positionally. Adding `AttachmentProfile` and `List<PersonalityFacet>` would push this to 21 fields. Instead, group the personality-related fields into a composite record:

```java
// In cognitive-index
public record PersonalityProfile(
    PersonalityWeights personality,
    Double personalityDominance,
    ExpressionStyleDefaults expressionStyles,
    AttachmentProfile attachment,
    List<PersonalityFacet> facets
) {}
```

This replaces five individual fields on `CognitiveDefaults` with one composite:
- `personality` (PersonalityWeights) — existing, moves into composite
- `personalityDominance` (Double) — existing, moves into composite
- `expressionStyles` (ExpressionStyleDefaults) — existing, moves into composite
- `attachment` (AttachmentProfile) — new
- `facets` (List\<PersonalityFacet\>) — new

`CognitiveDefaults` drops from 19 → 17 fields (net decrease despite adding two new concepts). Every `withX` method benefits from the reduced arity.

#### AttachmentProfile

Per-agent (not per-relationship). Derived from formation memories or seeded from biography.

```java
// In cognitive-index (inside PersonalityProfile)
public record AttachmentProfile(
    String style,           // secure, anxious-preoccupied, dismissive-avoidant, fearful-avoidant
    double anxiety,         // [0, 1] — attachment anxiety dimension
    double avoidance        // [0, 1] — attachment avoidance dimension
) {}
```

Accessed via `CognitiveDefaults.personalityProfile().attachment()`.

**Derivation path:** Two sources, in priority order:

1. **YAML-seeded (primary for initial implementation):** Cognitive profile YAML includes `attachment: { style: "dismissive-avoidant", anxiety: 0.2, avoidance: 0.8 }`. The existing `CognitiveDefaultsParser` (which already handles `PersonalityWeights`, `MoodBaseline`, etc.) is extended to parse this section. This is the path used by the Hooded Claw test case and all initial character definitions. Child 1 owns this.

2. **Derived from `FormationPadSummary` (future):** `CognitiveDerivationEngine.derive(DescriptorView)` currently uses `FormationPadSummary` to derive `personalityDominance` from `dominanceWeightedReward / totalPositivePleasure`. `FormationPadSummary` currently carries only dominance/pleasure aggregates — it does not carry the caregiver-responsiveness or attachment-relevant dimensions needed to derive attachment style. Extending `FormationPadSummary` with attachment-relevant fields (e.g., caregiver consistency score, early rejection frequency) is deferred to the Layer 1 formation schemas work. Until then, YAML seeding is the production path.

#### PersonalityFacet (AMPD)

Already partially modelled via `personality_profile` in engram extraction (#711). The AMPD 25 facets provide trait-level filtering that disposition axes (5 coarse dimensions) cannot.

```java
// In cognitive-index
public record PersonalityFacet(
    String facet,    // e.g. "Callousness", "Manipulativeness", "Grandiosity"
    double score,    // [0, 1] — consistent with all other scales (trust, intimacy, PAD, CAPS activations)
    @Nullable String origin  // felt description of the trait's origin
) {
    public PersonalityFacet {
        if (score < 0.0 || score > 1.0)
            throw new IllegalArgumentException("score must be in [0,1], got " + score);
    }
}
```

**Scale rationale:** Every numeric dimension in the cognitive pipeline uses `double` in `[0,1]` or `[-1,1]`: trust, intimacy, PAD, CAPS activations, attachment anxiety/avoidance, trustFormationRate. Using `int 0-100` would create a normalization hazard at every usage site. The eval YAML format (if it uses integer scores) normalizes during parsing — `score / 100.0`.

Accessed via `CognitiveDefaults.personalityProfile().facets()`. Populated from personality profile extraction or biography seeding.

**Relationship to `AmpdFacets`:** `AmpdFacets` in `cognitive-index` currently stores AMPD scores as `Map<String, Integer>` with 13 facet constants (CALLOUSNESS, MANIPULATIVENESS, GRANDIOSITY, etc.). It is loaded via `DescriptorView.ampdFacets()` and consumed by `CognitiveDerivationEngine.deriveExpressionStyles()`. `PersonalityFacet` supersedes `AmpdFacets` — it carries the same data in a normalized `[0,1]` scale with optional origin metadata. Migration:

- `DescriptorView.ampdFacets()` → `DescriptorView.personalityFacets()` returning `List<PersonalityFacet>`
- Facet constants (CALLOUSNESS, MANIPULATIVENESS, etc.) move to `PersonalityFacet`
- `CognitiveDerivationEngine.deriveExpressionStyles(AmpdFacets)` changes signature to accept `List<PersonalityFacet>`
- `AmpdFacets` is retired — single representation eliminates model fragmentation
- All callers updated mechanically; `isHigh(facet)` becomes `score >= 0.7`, `isLow(facet)` becomes `score <= 0.3`

#### Boundary: DispositionAxes vs PersonalityFacets

These two personality representations serve different subsystems:

- **DispositionAxes** (5 coarse dimensions: socialOrient, ruleFollowing, riskAppetite, autonomy, conflictMode): the **quantitative driver** for CAPS weight modulation. Connection weights in `caps-topology.yaml` are multiplied by disposition-derived factors via `disposition_modifiers`. This is the mechanism that makes a psychopathic agent's CAPS network respond differently at the topological level.

- **PersonalityFacets** (AMPD 25 facets, `double` in `[0,1]`): **qualitative personality context** for two consumers:
  1. LLM appraisal prompting — rendered as text in `LlmAppraisalStrategy.buildUserMessage()` so the LLM can reason about personality nuance that 5 disposition axes cannot express
  2. Trust/intimacy dynamics — specific facets (Callousness, Manipulativeness) modulate the trust/intimacy update formulas in relational schema evolution

DispositionAxes modulates CAPS topology. PersonalityFacets modulates LLM reasoning and relational dynamics. They do not overlap or compound — they operate on different subsystems.

### Storage: overlay properties

Relational schema dimensions are stored as properties on existing perspectival overlay nodes:

```
rel.target-id = "peter-perfect"
rel.role = "obstacle"
rel.trust = "0.1"
rel.intimacy = "0.0"
rel.utility = "0.2"
rel.description = "Predictably protective. Too simple to be a real threat."
```

`RelationalSchema.fromProperties()` reads these; `toProperties()` writes them. The `rel.` prefix namespace avoids collision with existing overlay properties (`familiarity-score`, `familiarity-stage`, `familiarity-interaction-count` — see `OverlayFamiliarityPropertyModel`).

**Naming convention:** Existing overlay properties use dash-separated flat names (`familiarity-score`). The `rel.` prefix introduces dot-separated namespacing for related property groups — a deliberate convention choice to scope relational schema properties as a unit. The dot prefix enables `fromProperties()` to filter relevant properties by prefix match rather than checking each key individually. Both conventions coexist; `OverlayFamiliarityPropertyModel` constants remain unchanged.

**Defensive parsing in `fromProperties()`:**
- If no `rel.*` properties exist at all → return `null` (no schema — first encounter, not yet consolidated)
- Missing `rel.trust` → default `0.0` (neutral)
- Missing `rel.intimacy` → default `0.0` (none)
- Missing `rel.utility` → default `0.0` (none)
- Missing `rel.role` → default `"stranger"`
- Non-numeric values (empty string, `"NaN"`, corrupted) → use the field default, following the same `parseDoubleSafe()` pattern used in `AppraisalTickParticipant`
- Out-of-range values → clamp to valid range (`trust` to `[-1,1]`, `intimacy`/`utility` to `[0,1]`)

This ensures a partially-written overlay (e.g., `rel.role = "ally"` but no `rel.trust`) returns a semantically coherent schema rather than throwing or returning semantically inconsistent data.

**Write-ordering constraint:** All overlay property writes for a given node MUST happen within a single `updateNode()` call or within a single consolidation phase. `SqliteMindMapStore.updateNode()` performs a non-transactional read-modify-write on the properties JSON column. Two concurrent `updateNode()` calls on the same node can clobber each other's property changes. Currently `RelationshipStagePhase` is the only consolidation phase writing to overlay properties; `RelationalSchemaEvolutionPhase` (introduced by this spec) runs at the same priority and writes in the same pass. If future phases also write overlay properties, they must coordinate to avoid clobbering.

No new SPI or store — this uses the existing `MindMapStore.updateNode()` with `NodeUpdate.withPropertiesToSet()`.

### Wiring: AppraisalContext extension

```java
public record AppraisalContext(
    PerceivedSituation situation,
    List<Drive> drives,
    AppraisalWeights weights,
    HabituationConfig habituationConfig,
    HabituationState habituation,
    MoodState currentMood,
    @Nullable DispositionAxes dispositionAxes,
    @Nullable RelationalSchema targetSchema,         // NEW
    @Nullable List<PersonalityFacet> personalityFacets  // NEW
) { ... }
```

`AppraisalTickParticipant.tick()` resolves the target:
1. Read target agent ID from `CognitionTickContext.targetAgentId()` (new nullable field)
2. Look up the overlay node for (observer → target) using the existing overlay resolution in `RelationshipStagePhase.run()` — iterate PERSON subgraph overlays, match on `OverlayRef.AGENT_ID`
3. Read `RelationalSchema.fromProperties()` from the overlay
4. Pass to `AppraisalContext`

**Full target resolution data flow:**

```
Caller (engine adapter, quarkmind-core)
  │  knows targetAgentId from conversation/interaction context
  ▼
CognitionCore.tick(agentId, tenantId, descriptor, resolver, observation, targetAgentId)
  │  new overload — adds @Nullable String targetAgentId
  │  existing overloads pass null for backward compatibility
  ▼
CognitionTickContext(agentId, tenantId, descriptor, resolver, observation, briefing, targetAgentId)
  │  new nullable field — 7th → 8th record component
  │  new convenience constructors mirror existing pattern
  ├──▶ AppraisalTickParticipant.tick(context)
  │      reads context.targetAgentId() → resolves RelationalSchema from overlay
  │      passes RelationalSchema into AppraisalContext
  │
  ├──▶ [future participants] — target available via context record
  │
  ▼
CognitionCore.promptSections()
  │  threads lastTargetAgentId → CognitionRenderContext
  ▼
CognitionRenderContext(agentId, tenantId, subjectId, activatedDriveCategories)
  │  subjectId is populated from targetAgentId (currently null at construction sites)
  ├──▶ OtherModelPromptSection.render(context) — uses context.subjectId()
  ├──▶ UserModelPromptSection.render(context) — already uses subjectId
  └──▶ MentalModelPromptSection.render(context) — already uses subjectId
```

**Graduated cognitive node tagging:** When `AppraisalTickParticipant.tick()` processes an observation with a non-null `targetAgentId`, the resulting cognitive node (if graduated to the COGNITIVE subgraph) carries a `target-agent-id` property. This propagates the per-interaction target identity into the consolidation pipeline, where `BehavioralSynthesisPhase` and `RelationalSchemaEvolutionPhase` can read it. This mirrors the existing `ExperienceAttributeKeys.TARGET_AGENT` pattern in the memory layer.

**Why `targetAgentId` belongs on `CognitionTickContext`:** The interaction target is not appraisal-specific — it is a first-class property of any cognitive tick that involves another agent. Multiple tick participants benefit from knowing who the agent is interacting with: `AppraisalTickParticipant` (relational context for emotional appraisal), future mood-modulation participants (mood response may differ by relationship), and prompt rendering (via threading to `CognitionRenderContext.subjectId`). The caller (CognitionCore or the engine adapter) always knows the target; extracting it from free-text observation would be fragile and add latency. This follows the same pattern as `@Nullable AttentionBriefing briefing` and `@Nullable AgentDescriptor descriptor` — optional context carried on the tick record that not every participant uses.

`LlmAppraisalStrategy.buildUserMessage()` appends:

```
Relationship with [targetId]:
- Role: prey
- Trust: 0.1 (very low)
- Intimacy: 0.0 (none)
- Utility: 0.9 (very high)
- Description: She inherited everything you built. Her trust in you is
  the most useful thing about her.

Personality traits:
- Callousness (0.90): numbness where sympathy should be
- Manipulativeness (0.85): deception is your resting state
```

### Wiring: OtherModel prompt rendering

Create `OtherModelPromptSection implements CognitionPromptRenderer`:
- Uses `context.subjectId()` from `CognitionRenderContext` (populated by the tick pipeline from `CognitionTickContext.targetAgentId()` — see below)
- Looks up OtherModel-derived nodes for (agent → target) in the COGNITIVE subgraph
- Renders empathic_sensing + relational_understanding into the prompt
- Gated by `CognitionConfig.otherModelEnabled()` (new boolean, default true)

**`otherModelEnabled` vs `mentalModelEnabled` — semantic boundary:** `mentalModelEnabled` gates the `MentalModelOrchestrator` subsystem which extracts beliefs/desires/intentions (BDI) from conversations via `MentalModelPromptSection` — the observer's real-time model of what subjects think and want. `otherModelEnabled` gates `OtherModelPromptSection` which renders empathic sensing, inferred values, appraisal sensitivities, and relational understanding — the observer's pre-computed emotional/relational model of targets, derived during consolidation by `OtherModelDerivationPhase`. These are architecturally distinct: BDI extraction runs per-conversation (tick-time), while empathic models are derived from formation memories and relational schemas (consolidation-time). A deployment could enable conversation-time BDI modelling (`mentalModelEnabled=true`) while disabling the richer empathic model (`otherModelEnabled=false`) — or vice versa.

**Target threading (eliminates duplication):** `CognitionObservationBuilder` currently constructs `CognitionRenderContext` with `null` for `subjectId` (line 355, line 370). Once `CognitionTickContext.targetAgentId()` is available, thread it through to `CognitionObservationBuilder` and populate `CognitionRenderContext.subjectId` with the resolved target. This ensures all prompt renderers — `UserModelPromptSection`, `MentalModelPromptSection`, and the new `OtherModelPromptSection` — receive the target without any re-resolution. The target is resolved once (by the caller recording the interaction) and carried through the tick → render pipeline.

### Dynamic schema evolution

**Separation of concerns:** Familiarity computation (`RelationshipStagePhase`, `@Priority(18)`) remains unchanged — it computes an objective interaction-frequency metric using simple arithmetic.

A new `RelationalSchemaEvolutionPhase implements ConsolidationPhase` at `@Priority(19)` handles the richer, personality-modulated relational updates.

**Priority ordering:**

| Priority | Phase | Reads | Writes |
|----------|-------|-------|--------|
| 18 | `RelationshipStagePhase` | CaseMemoryStore (relationship memories) | overlay properties (familiarity-score, familiarity-stage) |
| 19 | `RelationalSchemaEvolutionPhase` | overlay properties (familiarity), CaseMemoryStore, CognitiveDefaultsRegistry | overlay properties (rel.trust, rel.intimacy, rel.role) |
| 19 | `BehavioralSynthesisPhase` | COGNITIVE subgraph nodes (graduated) | BEHAVIORAL subgraph nodes (attractors), CapsEngine state |

`RelationalSchemaEvolutionPhase` runs after `RelationshipStagePhase` (19 > 18), guaranteeing familiarity is computed before trust/intimacy/role evolution. It shares `@Priority(19)` with `BehavioralSynthesisPhase` — their relative ordering is non-deterministic, which is correct because they are fully independent: different input sources, different output targets, no shared mutable state. This follows the existing codebase pattern where `MergeDetectionPhase` and `DriveProfileDerivationPhase` share `@Priority(20)` for the same reason.

If consolidation-time CAPS biasing is added in the future (requiring `BehavioralSynthesisPhase` to read overlay `rel.*` properties), the phases would need renumbering to enforce ordering. That is future scope.

#### Initial seeding

When `RelationalSchemaEvolutionPhase` encounters an overlay node with no `rel.*` properties (first consolidation for a new relationship), it seeds the initial schema:

```
rel.role = "stranger"
rel.trust = 0.0
rel.intimacy = 0.0
rel.utility = 0.0
rel.description = null
```

**First-interaction gap:** Between the first cognitive tick involving a target and the first consolidation run, the overlay has no `rel.*` properties. `RelationalSchema.fromProperties()` returns `null`, and `AppraisalTickParticipant` processes the interaction without relational context. This is correct — the agent has no relational history with this target yet. The schema is created at the next consolidation cycle.

#### Trust update formula

After familiarity is computed, update `rel.trust`:

```
// Inputs
trustFormationRate = SocialCognitionDefaults.trustFormationRate()  // [0, 1], default 0.5
callousness = personalityFacet("Callousness").score()             // [0, 1], or 0.0 if absent
avoidance = attachmentProfile.avoidance()                         // [0, 1], or 0.0 if absent

// Interaction valence — from PAD pleasure of relationship memories
// Uses the same positive/negative/neutral classification as computeFamiliarity()
interactionValence = (positive * positiveWeight - negative * negativeWeight) / total
// Normalized to [-1, 1]
valence = clamp(interactionValence, -1.0, 1.0)

// ConflictInterpretation modulation (same multipliers as computeFamiliarity())
conflictMultiplier = switch (conflictInterpretation) {
    REPAIR -> 0.6       // repairs dampen negative impact
    INFORMATION -> 0.9  // treats conflict as data
    NEUTRAL -> 1.0      // no modulation
    DISENGAGE -> 1.4    // withdrawal amplifies negative impact
}

// Trust delta
if (valence >= 0) {
    // Positive interaction: Callousness dampens trust GAIN
    trustDelta = trustFormationRate * valence * (1.0 - callousness)
} else {
    // Negative interaction: ConflictInterpretation modulates negative impact
    trustDelta = trustFormationRate * valence * conflictMultiplier
}

// Trust ceiling — avoidant attachment limits how much trust can grow
trustCeiling = 1.0 - avoidance
trustFloor = -1.0

newTrust = clamp(currentTrust + trustDelta, trustFloor, trustCeiling)
```

**Design rationale:** The formula mirrors `UserModelOrchestrator.computeFamiliarity()` (same `conflictMultiplier` switch, same positive/negative classification from PAD pleasure) but produces a signed `[-1, 1]` value instead of a `[0, 1]` scalar. Callousness dampens positive trust formation (the agent cannot gain trust easily from kind interactions) but does NOT dampen negative trust loss (even callous agents respond to betrayal). The avoidance ceiling means a dismissive-avoidant agent (avoidance=0.8) can only reach trust=0.2 regardless of positive interactions.

#### Intimacy update formula

```
// Intimacy increases with positive interactions, dampened by avoidance
intimacyDelta = trustFormationRate * max(0, valence) * (1.0 - avoidance)

// Anxiety amplifies intimacy gain (anxious attachment seeks closeness)
intimacyDelta *= (1.0 + 0.5 * anxiety)

newIntimacy = clamp(currentIntimacy + intimacyDelta, 0.0, 1.0)
```

#### Role evolution — transition table

Trust thresholds trigger role RE-EVALUATION, not deterministic transitions. The current role, trust value, and personality determine the new role:

| Current role | Trust ≥ 0.5 (upward crossing) | Trust ≤ -0.3 (downward crossing) |
|---|---|---|
| `stranger` | → `ally` (default) or `tool` (if Manipulativeness > 0.7) | → `threat` |
| `ally` | → `mentor` (if utility > 0.5) or stays `ally` | → `obstacle` |
| `mentor` | stays `mentor` | → `obstacle` |
| `tool` | → `ally` (if Callousness < 0.3) or stays `tool` | → `obstacle` |
| `prey` | → `tool` (if Manipulativeness > 0.5) or stays `prey` | → `threat` |
| `obstacle` | → `stranger` (trust recovery, needs ≥ 0.5) | stays `obstacle` |
| `threat` | → `stranger` (trust recovery, needs ≥ 0.5) | stays `threat` |
| `protectee` | stays `protectee` | → `stranger` |

**Personality conditioning:** A psychopathic agent (high Callousness + high Manipulativeness) experiencing positive interactions with `prey` does NOT evolve to `ally`. The pleasure signal from exploitation increases trust, but the Manipulativeness > 0.5 gate routes `prey` → `tool` instead. This prevents the semantically wrong `prey → ally` transition.

**Multi-hop prevention:** Only one transition per consolidation cycle. If trust jumps from 0.0 to 0.8 in a single cycle, only the first applicable transition fires.

**Mid-range behavior (trust between -0.3 and 0.5):** No role transition is triggered. The role remains whatever it was last set to. This is intentional — roles are sticky. A `stranger` at trust 0.3 is still a stranger until trust crosses the 0.5 threshold.

**Role transitions are logged** as MindMap edge property changes for auditability.

**Rationale for separation:** Trust, intimacy, and role evolution each have different inputs (PAD for intimacy, ConflictInterpretation for trust, threshold logic for role), different learning rates, and different ceiling behaviors. Keeping them in a separate phase from familiarity makes both independently testable and allows them to evolve without risk to the simpler familiarity pipeline.

### CAPS per-relationship biasing

The spec distinguishes two execution contexts with different purposes:

**Tick-time biasing (primary):** When `AppraisalTickParticipant.tick()` runs the `SituationClassifier`, adjust the classified activation outputs based on the target's `RelationalSchema`. The biasing applies AFTER classification, using multiplicative scaling to preserve relative differences and avoid saturation against the `[-1, 1]` clamp:

```java
// In AppraisalTickParticipant.tick(), after classification and schema resolution
if (targetSchema != null) {
    var biased = new HashMap<>(classifiedActivations);
    double trust = targetSchema.trust();  // [-1, 1]

    // Multiplicative biasing — preserves relative differences at high activations
    // Trust > 0: boost secure, dampen threat
    // Trust < 0: boost threat, dampen secure
    //
    // Provenance for scaling factors (all ≤1× topology weight to avoid
    // overwhelming situation signal):
    //   0.30 — secure_attachment → self_worth weight is 0.30 in caps-topology.yaml
    //          (van IJzendoorn 1995, r=.24-.32). Matched directly.
    //   0.20 — rejection → other_reliability weight is -0.35; scaled down to avoid
    //          double-counting (situation classifier already carries rejection signal)
    //   0.25 — betrayal: no direct topology connection; estimated between rejection
    //          (0.35) and abandonment (0.20). Consensus, subject to calibration.
    //   0.15 — psychological_threat: conservative below all attachment weights.
    //          Estimated, subject to calibration via Hooded Claw test suite (Child 5).
    biased.computeIfPresent("secure_attachment", (k, v) -> v * (1.0 + trust * 0.3));
    biased.computeIfPresent("rejection",         (k, v) -> v * (1.0 - trust * 0.2));
    biased.computeIfPresent("betrayal",          (k, v) -> v * (1.0 - trust * 0.25));
    biased.computeIfPresent("psychological_threat", (k, v) -> v * (1.0 - trust * 0.15));
}
```

**Why multiplicative, not additive:** Additive biasing (e.g., `activation + trust * 0.3`) creates saturation against the CAPS activation clamp `[-1, 1]`. Two agents with trust 0.7 and 1.0 both produce `secure_attachment` = 1.0 when the base activation is ≥ 0.7 — the trust difference vanishes. Multiplicative biasing (e.g., `activation * (1 + trust * 0.3)`) preserves relative differences: base 0.8 × 1.21 = 0.97 vs 0.8 × 1.30 = 1.04 (clamped to 1.0, but the gap is narrower). For inputs near zero, multiplicative biasing has minimal effect, which is correct — there's nothing to bias.

**Consolidation-time biasing (secondary):** `BehavioralSynthesisPhase` (priority 19) processes graduated cognitive nodes and runs `CapsEngine.settle()`. It does NOT receive per-interaction target context — it processes batches of graduated nodes. Per-relationship biasing at consolidation time would require extending `BehavioralSynthesisPhase` to group graduated nodes by target and apply relational context per group. This is a future enhancement — tick-time biasing addresses the immediate need.

### RelationshipVocabulary

New vocabulary registered via `MindMapVocabulary`, following the `GoalVocabulary` pattern:

```java
public final class RelationshipVocabulary {
    public static final MindMapVocabulary RELATIONSHIP_VOCABULARY = MindMapVocabulary.builder()
        .edgeType("trusts", 30.0, "relies-on")
        .edgeType("distrusts", 14.0, "suspects", "wary-of")
        .edgeType("fears", 14.0, "dreads", "avoids")
        .edgeType("admires", 60.0, "respects", "looks-up-to")
        .edgeType("resents", 21.0, "begrudges")
        .edgeType("protects", 60.0, "shields", "guards")
        .edgeType("exploits", 21.0, "uses", "manipulates")
        .edgeType("depends-on", 30.0, "needs", "leans-on")
        .build();

    private RelationshipVocabulary() {}
}
```

Edge types are registered through `MindMapVocabulary.Builder.edgeType()` with canonical names, aliases, and decay half-lives (days). Trust/distrust edges decay faster (14-30 days) than structural relationship edges (admiration, protection — 60 days), reflecting the psychological reality that trust is more volatile than regard.

These are **interpersonal emotional stances** — how an agent feels about another person. They are distinct from factual relationship types (married-to, affair-with, divorced-from) tracked in #575 (corpus edge type vocabulary). #575 addresses structural/biographical categories extracted during corpus processing; this vocabulary addresses emotional/evaluative edges in the PERSON subgraph.

## Child issues

| # | Title | Scale | Complexity | Depends on | Blocks |
|---|-------|-------|------------|------------|--------|
| 1 | RelationalSchema + PersonalityProfile (with AttachmentProfile + PersonalityFacet) types; CognitiveDefaults refactoring; overlay storage; RelationshipVocabulary | M | Med | — | 2, 4, 5 |
| 2 | Wire relational context into AppraisalContext + LlmAppraisalStrategy prompt | M | Med | 1 | — |
| 3 | OtherModelPromptSection — render mental models into agent prompt; thread targetAgentId through CognitionRenderContext | M | Med | — | — |
| 4 | RelationalSchemaEvolutionPhase — trust, intimacy, role dynamics | L | High | 1 | — |
| 5 | CAPS per-relationship tick-time input biasing | M | High | 1 | — |

**Dependency note:** Child 5 reads static `RelationalSchema` values (trust, intimacy, role) from overlay properties. It does not depend on Child 4 (the dynamic evolution logic) — it works with whatever values are stored, whether seeded initially or evolved dynamically. Children 4 and 5 are both independent consumers of Child 1's types.

## Testing strategy

**Child 1:** Unit tests for RelationalSchema property serialization round-trip. Unit tests for PersonalityProfile composition. Verify CognitiveDefaults with/without PersonalityProfile. Contract test extension for overlay property read/write.

**Child 2:** Unit test for `LlmAppraisalStrategy.buildUserMessage()` output format with relational context. Integration test: seed relational schema on overlay, run appraisal tick, verify user message includes relationship data.

**Child 3:** Unit test for `OtherModelPromptSection.render()` with seeded OtherModel-derived nodes. Verify output includes empathic_sensing and relational_understanding. Verify `CognitionRenderContext.subjectId` is correctly threaded from `CognitionTickContext.targetAgentId`.

**Child 4:** Integration test: seed interactions, run consolidation, verify trust/intimacy/role evolution. Edge cases: trust ceiling with high avoidance, ConflictInterpretation.DISENGAGE amplification. Separate from familiarity tests — verify RelationalSchemaEvolutionPhase independently of RelationshipStagePhase.

**Child 5:** Integration test: seed relational schema, classify situation with and without relational biasing, verify different activation outputs. The Hooded Claw test case: kindness from prey vs kindness from tool should produce different situation classifications.

## References

- `cognition-api/.../AppraisalContext.java` — current record, no target field
- `cognition/.../LlmAppraisalStrategy.java:21-49` — system prompt, :123-151 — user message builder
- `cognition/.../AppraisalTickParticipant.java:113-176` — tick method, disposition resolution
- `cognition/.../BehavioralPromptSection.java` — attractor rendering (global, not per-relationship)
- `mindmap-intelligence/.../OtherModelDerivationPhase.java` — per-pair mental model creation (disconnected from prompts)
- `cognition/.../RelationshipStagePhase.java` — familiarity computation on overlays
- `caps-engine/src/main/resources/caps-topology.yaml` — 6 Bowlby attachment input nodes, disposition_modifiers
- `caps-llm-classifier/src/test/resources/eval-characters-generic.yaml:58-127` — eval schema format
- `caps-llm-classifier/src/test/java/.../EvalCharacterLoader.java:105-127` — schema loading
- `cognitive-index/.../CognitiveDefaults.java` — 19-field record, refactored to 17 with PersonalityProfile composite
- `cognitive-index/.../DispositionAxes.java` — 5-axis quantitative personality (CAPS modulation)
- `mindmap-api/.../GoalVocabulary.java` — vocabulary registration pattern
- `cognition/.../CognitionObservationBuilder.java:355,370` — CognitionRenderContext construction (currently null subjectId)
- `mindmap-api/.../AppraisalContext.java` — mindmap-api variant with relationshipScores (attention weights, distinct from cognition-api AppraisalContext)
- casehubio/neocortex#575 — relationship edge type vocabulary (corpus factual types — distinct from this spec's emotional stances)
- casehubio/neocortex#687 — relationship_stages import (addressed by Child 4)
- casehubio/neocortex#517 — ConflictInterpretation wiring (already landed, used by this design)
