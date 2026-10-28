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

Accessed via `CognitiveDefaults.personalityProfile().attachment()`. Derived by `CognitiveDerivationEngine` from formation memories or seeded explicitly in cognitive profile YAML.

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

`RelationalSchema.fromProperties()` reads these; `toProperties()` writes them. The `rel.` prefix namespace avoids collision with existing overlay properties (familiarity-score, familiarity-stage, etc.).

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

**Target threading (eliminates duplication):** `CognitionObservationBuilder` currently constructs `CognitionRenderContext` with `null` for `subjectId` (line 355, line 370). Once `CognitionTickContext.targetAgentId()` is available, thread it through to `CognitionObservationBuilder` and populate `CognitionRenderContext.subjectId` with the resolved target. This ensures all prompt renderers — `UserModelPromptSection`, `MentalModelPromptSection`, and the new `OtherModelPromptSection` — receive the target without any re-resolution. The target is resolved once (by the caller recording the interaction) and carried through the tick → render pipeline.

### Dynamic schema evolution

**Separation of concerns:** Familiarity computation (`RelationshipStagePhase`, priority 18) remains unchanged — it computes an objective interaction-frequency metric using simple arithmetic.

A new `RelationalSchemaEvolutionPhase implements ConsolidationPhase` at priority 18 (ordered after `RelationshipStagePhase` by CDI bean ordering within the same priority, or a fractional priority if needed) handles the richer, personality-modulated relational updates:

**Trust update:** After familiarity is computed, update `rel.trust` using:
- `SocialCognitionDefaults.trustFormationRate()` as learning rate
- Positive interactions → trust increases (scaled by personality: high Callousness dampens trust gain)
- Negative interactions → trust decreases (scaled by `ConflictInterpretation`: DISENGAGE amplifies, REPAIR dampens)
- `AttachmentProfile.avoidance` dampens trust ceiling (high avoidance → trust saturates below 1.0)

**Intimacy update:** Increases with interaction count and positive PAD. `AttachmentProfile.anxiety` amplifies intimacy gain (anxious attachment seeks closeness aggressively). `AttachmentProfile.avoidance` dampens it.

**Role evolution:** Thresholds on trust trigger role transitions:
- trust crosses 0.5 upward → role can evolve (e.g., stranger → ally)
- trust crosses -0.3 downward → role can degrade (e.g., ally → obstacle)
- Role transitions are logged as MindMap edge property changes for auditability

**Rationale for separation:** Trust, intimacy, and role evolution each have different inputs (PAD for intimacy, ConflictInterpretation for trust, threshold logic for role), different learning rates, and different ceiling behaviors. Keeping them in a separate phase from familiarity makes both independently testable and allows them to evolve without risk to the simpler familiarity pipeline.

### CAPS per-relationship biasing

The spec distinguishes two execution contexts with different purposes:

**Tick-time biasing (primary):** When `AppraisalTickParticipant.tick()` runs the `SituationClassifier`, adjust the input activation map based on the target's `RelationalSchema` before classification. This gives per-interaction relational context to the situation classifier:

```java
// In AppraisalTickParticipant.tick(), after resolving RelationalSchema
if (targetSchema != null && situationClassifier != null) {
    var biasedActivations = new HashMap<>(baseActivations);
    double trustBias = targetSchema.trust();  // [-1, 1]

    // High trust → boost secure_attachment, dampen rejection/betrayal
    biasedActivations.merge("secure_attachment", trustBias * 0.3, Double::sum);
    biasedActivations.merge("rejection", -trustBias * 0.2, Double::sum);
    biasedActivations.merge("betrayal", -trustBias * 0.25, Double::sum);

    // Low trust → boost suspicion inputs
    biasedActivations.merge("psychological_threat", -trustBias * 0.15, Double::sum);

    activations = situationClassifier.classify(observation, biasedActivations);
}
```

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
