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

## Design

### Data model

Promote the existing eval schema to production types. Three record types, stored as structured properties on perspectival overlay nodes in the PERSON subgraph.

#### RelationalSchema

Per-agent-per-target relational state. One per overlay node.

```java
// In mindmap-api or a new relational sub-package of cognitive-index
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

#### AttachmentProfile

Per-agent (not per-relationship). Derived from formation memories or seeded from biography.

```java
// In cognitive-index (alongside CognitiveDefaults)
public record AttachmentProfile(
    String style,           // secure, anxious-preoccupied, dismissive-avoidant, fearful-avoidant
    double anxiety,         // [0, 1] — attachment anxiety dimension
    double avoidance        // [0, 1] — attachment avoidance dimension
) {}
```

Added as a field on `CognitiveDefaults` (17th → 18th field). Derived by `CognitiveDerivationEngine` from formation memories or seeded explicitly in cognitive profile YAML.

#### PersonalityFacet (AMPD)

Already partially modelled via `personality_profile` in engram extraction (#711). The AMPD 25 facets provide trait-level filtering that disposition axes (5 coarse dimensions) cannot.

```java
// In cognitive-index
public record PersonalityFacet(
    String facet,    // e.g. "Callousness", "Manipulativeness", "Grandiosity"
    int score,       // 0-100
    @Nullable String origin  // felt description of the trait's origin
) {}
```

Added to `CognitiveDefaults` as `List<PersonalityFacet>`. Populated from personality profile extraction or biography seeding.

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
1. Read target agent ID from `CognitionTickContext.targetAgentId()` (new nullable field — the caller that records the interaction knows the target; the tick context should carry it rather than re-extracting from free text)
2. Look up the overlay node for (observer → target) using `PerspectivalResolver`
3. Read `RelationalSchema.fromProperties()` from the overlay
4. Pass to `AppraisalContext`

**Note:** `CognitionTickContext` is currently `(agentId, tenantId, descriptor, resolver, observation, briefing)` where `observation` is plain text. Adding `@Nullable String targetAgentId` to this record is the cleanest path — the caller (CognitionCore or the engine adapter) already knows who the agent is interacting with. Extracting the target from free-text observation would be fragile and add latency.

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
- Callousness (90): numbness where sympathy should be
- Manipulativeness (85): deception is your resting state
```

### Wiring: OtherModel prompt rendering

Create `OtherModelPromptSection implements CognitionPromptRenderer`:
- Resolves the interaction target (same logic as appraisal target resolution)
- Looks up `OtherModelDerived` nodes for (agent → target) in the COGNITIVE subgraph
- Renders empathic_sensing + relational_understanding into the prompt
- Gated by `CognitionConfig.otherModelEnabled()` (new boolean, default true)

### Dynamic schema evolution

`RelationshipStagePhase` extended to update relational schema dimensions:

**Trust update:** After computing familiarity, update `rel.trust` using:
- `SocialCognitionDefaults.trustFormationRate()` as learning rate
- Positive interactions → trust increases (scaled by personality: high Callousness dampens trust gain)
- Negative interactions → trust decreases (scaled by `ConflictInterpretation`: DISENGAGE amplifies, REPAIR dampens)
- `AttachmentProfile.avoidance` dampens trust ceiling (high avoidance → trust saturates below 1.0)

**Intimacy update:** Increases with interaction count and positive PAD. `AttachmentProfile.anxiety` amplifies intimacy gain (anxious attachment seeks closeness aggressively). `AttachmentProfile.avoidance` dampens it.

**Role evolution:** Thresholds on trust trigger role transitions:
- trust crosses 0.5 upward → role can evolve (e.g., stranger → ally)
- trust crosses -0.3 downward → role can degrade (e.g., ally → obstacle)
- Role transitions are logged as MindMap edge property changes for auditability

### CAPS per-relationship biasing

When CAPS settling processes a situation involving a known target, adjust input node activations based on relational schema:

```
// In BehavioralSynthesisPhase or a new CapsRelationalBiasDecorator
double trustBias = schema.trust();  // [-1, 1]

// High trust → boost secure_attachment, dampen rejection/betrayal
adjustActivation("secure_attachment", trustBias * 0.3);
adjustActivation("rejection", -trustBias * 0.2);
adjustActivation("betrayal", -trustBias * 0.25);

// Low trust → boost suspicion inputs
adjustActivation("psychological_threat", -trustBias * 0.15);
```

This is additive biasing on top of the situation classification — it doesn't replace the situation's own activation, it shifts the baseline per-relationship.

### RelationshipVocabulary

New vocabulary registered via `MindMapVocabulary`:

```java
public final class RelationshipVocabulary {
    public static final String TRUSTS = "trusts";
    public static final String DISTRUSTS = "distrusts";
    public static final String FEARS = "fears";
    public static final String ADMIRES = "admires";
    public static final String RESENTS = "resents";
    public static final String PROTECTS = "protects";
    public static final String EXPLOITS = "exploits";
    public static final String DEPENDS_ON = "depends-on";

    // Registered by CognitiveLoader alongside GoalVocabulary, ActivityVocabulary
}
```

Subsumes #575 (relationship edge types).

## Child issues

| # | Title | Scale | Complexity | Depends on | Blocks |
|---|-------|-------|------------|------------|--------|
| 1 | RelationalSchema + AttachmentProfile + PersonalityFacet types; overlay storage; RelationshipVocabulary | S | Med | — | 2, 4, 5 |
| 2 | Wire relational context into AppraisalContext + LlmAppraisalStrategy prompt | M | Med | 1 | — |
| 3 | OtherModelPromptSection — render mental models into agent prompt | M | Med | — | — |
| 4 | Dynamic schema evolution in RelationshipStagePhase | L | High | 1 | 5 |
| 5 | CAPS per-relationship input biasing | M | High | 1, 4 | — |

## Testing strategy

**Child 1:** Unit tests for RelationalSchema property serialization round-trip. Contract test extension for overlay property read/write.

**Child 2:** Unit test for `LlmAppraisalStrategy.buildUserMessage()` output format with relational context. Integration test: seed relational schema on overlay, run appraisal tick, verify user message includes relationship data.

**Child 3:** Unit test for `OtherModelPromptSection.render()` with seeded OtherModelDerived nodes. Verify output includes empathic_sensing and relational_understanding.

**Child 4:** Integration test: seed interactions, run consolidation, verify trust/intimacy/role evolution. Edge cases: trust ceiling with high avoidance, ConflictInterpretation.DISENGAGE amplification.

**Child 5:** Integration test: seed relational schema, run CAPS settling for same situation with different schemas, verify different output activations. The Hooded Claw test case: kindness from prey vs kindness from tool should produce different CAPS outputs.

## References

- `cognition-api/.../AppraisalContext.java` — current record, no target field
- `cognition/.../LlmAppraisalStrategy.java:21-49` — system prompt, :123-151 — user message builder
- `cognition/.../AppraisalTickParticipant.java:113-176` — tick method, disposition resolution
- `cognition/.../BehavioralPromptSection.java` — attractor rendering (global, not per-relationship)
- `mindmap-intelligence/.../OtherModelDerivationPhase.java` — per-pair mental model creation (disconnected from prompts)
- `cognition/.../RelationshipStagePhase.java` — familiarity computation on overlays
- `caps-engine/src/main/resources/caps-topology.yaml` — 6 Bowlby attachment input nodes
- `caps-llm-classifier/src/test/resources/eval-characters-generic.yaml:58-127` — eval schema format
- `caps-llm-classifier/src/test/java/.../EvalCharacterLoader.java:105-127` — schema loading
- casehubio/neocortex#575 — relationship edge type vocabulary (subsumed by RelationshipVocabulary)
- casehubio/neocortex#687 — relationship_stages import (addressed by Child 4)
- casehubio/neocortex#517 — ConflictInterpretation wiring (already landed, used by this design)
