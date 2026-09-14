# Cognitive Node Type Classification — Design Spec

**Issue:** casehubio/neocortex#322
**Date:** 2026-09-14
**Branch:** issue-322-cognitive-node-types

## Summary

Register six cognitive node types (belief, intention, prediction, judgment, fear, desire) in the MindMap type system. These represent overlapping aspects of mental representations — a single proposition can simultaneously be a belief, a prediction, and a fear. The design uses compositional traits (additive) rather than exclusive subgraph types, following the established Eventlike + Threatening/Aspirational pattern at the correct abstraction level.

## Architecture

### Compositional Model (D1)

Cognitive types are **traits**, not exclusive types. A node classified as a belief can also carry the Predictive and Evaluative traits simultaneously. This follows from the observation that cognitive categories are overlapping aspects of mental content, not mutually exclusive taxonomies.

The existing dual-axis system handles this naturally:
- **Subgraph type** (exclusive) — structural placement. All cognitive nodes live in a single COGNITIVE subgraph.
- **Traits** (additive) — behavioral classification. Multiple cognitive traits fire on the same node via TraitRules.

### Subgraph: COGNITIVE (D2)

A new `COGNITIVE` subgraph type, separate from CONCEPT. Consolidation phases (MergeDetectionPhase, CommunitySummaryPhase, DomainActivation) operate per-subgraph — mixing cognitive nodes with abstract concepts produces incorrect merge detection and incoherent community clustering.

Add to `SubgraphTypes`:
```java
public static final String COGNITIVE = "cognitive";
```

### Type Hierarchy (D5)

COGNITIVE is a new parent type under GENERAL in TypeRegistry, with individual cognitive types as children:

```
GENERAL
├── PERSON
├── PROJECT
├── ORGANISATION
├── CONCEPT
├── RESEARCH_AREA
└── COGNITIVE
    ├── belief
    ├── intention
    ├── prediction
    ├── judgment
    ├── fear
    └── desire
```

Registration happens in `CognitiveLoader.init()` alongside existing vocabulary registration. TypeRegistry requires a tenant — CognitiveLoader iterates discovered tenants or registers lazily on first access.

## Trait Interfaces (D3)

Six interfaces in `mindmap-intelligence`, following the established pattern (`Optional<String>` returns, 3 properties each). Naming convention: `-like` suffix for noun-based types (consistent with Eventlike, Projectlike), adjectival form for verb-based types (Predictive, Evaluative).

### Belieflike

```java
public interface Belieflike {
    Optional<String> subject();
    Optional<String> status();    // active | revised | contradicted
    Optional<String> basis();
}
```

Consolidation lifecycle: revision on contradiction. `basis` enables contradiction detection by comparing the evidential foundation of conflicting beliefs.

### Intentionlike

```java
public interface Intentionlike {
    Optional<String> goal();
    Optional<String> status();    // active | achieved | abandoned | blocked
    Optional<String> priority();
}
```

Consolidation lifecycle: viability checking, achievement/abandonment tracking. `priority` enables lifecycle ordering during consolidation.

### Predictive

```java
public interface Predictive {
    Optional<String> timeframe();
    Optional<String> status();    // pending | confirmed | refuted
    Optional<String> basis();
}
```

Consolidation lifecycle: validation against outcomes within a timeframe. `basis` enables comparison of prediction foundations when evaluating conflicting predictions.

### Evaluative

```java
public interface Evaluative {
    Optional<String> target();
    Optional<String> stance();
    Optional<String> basis();
}
```

Consolidation lifecycle: challenge by evidence, comparison of evaluations. `basis` supports evidence-based reassessment. No `status` — evaluations are continuous, not lifecycle-gated.

### Fearlike

```java
public interface Fearlike {
    Optional<String> threat();
    Optional<String> severity();
    Optional<String> status();    // active | resolved | dismissed
}
```

Consolidation lifecycle: evaluation against current state. `severity` drives prioritisation of fear processing.

### Desirelike

```java
public interface Desirelike {
    Optional<String> aspiration();
    Optional<String> status();    // active | fulfilled | abandoned
    Optional<String> urgency();
}
```

Consolidation lifecycle: satisfaction tracking. `urgency` enables lifecycle ordering.

## Trait Rules (D4)

### Declarative Baseline

Primary trait assignment via `rules/cognitive-traits.yaml` in `cognitive-index` (loaded by DeclarativeRuleRegistry at `@PostConstruct`):

```yaml
traitRules:
  - trait: Belieflike
    when:
      propertyEquals:
        cognitiveKind: belief

  - trait: Intentionlike
    when:
      propertyEquals:
        cognitiveKind: intention

  - trait: Predictive
    when:
      propertyEquals:
        cognitiveKind: prediction

  - trait: Evaluative
    when:
      propertyEquals:
        cognitiveKind: judgment

  - trait: Fearlike
    when:
      propertyEquals:
        cognitiveKind: fear

  - trait: Desirelike
    when:
      propertyEquals:
        cognitiveKind: desire
```

### Secondary Compositional Rules

Additional rules for cross-type trait inference. A node with `cognitiveKind=belief` that also has a `timeframe` property gains the Predictive trait:

```yaml
  - trait: Predictive
    when:
      allOf:
        - hasProperty: timeframe
        - hasProperty: cognitiveKind

  - trait: Evaluative
    when:
      allOf:
        - hasProperty: target
        - hasProperty: stance
```

### Per-Agent Customisation

Agents can override or extend cognitive trait rules via their cognitive profile YAML (`cognitive-profiles/<agent>.yaml`), using the existing `traitRules:` section. DeclarativeRuleRegistry merges per-agent rules by name — a local rule with the same trait name suppresses the global rule.

## MindMapExtractor Changes (D6)

### Prompt Update

Expand the SYSTEM_PROMPT type list:

```
"type": "PERSON|PROJECT|RESEARCH_AREA|ORGANISATION|CONCEPT|GENERAL|BELIEF|INTENTION|PREDICTION|JUDGMENT|FEAR|DESIRE"
```

Add classification guidance to the prompt:

```
For cognitive content (beliefs, intentions, predictions, judgments, fears, desires):
- Classify by the PRIMARY cognitive aspect
- Set "cognitiveKind" as a property with the type value
- Use STATED confidence for explicit markers ("I think...", "I'm worried...")
- Use INFERRED for implied attitudes
- Use SPECULATED for ambiguous cases
```

### Subgraph Routing

Separate normalizeType() (pure strip+lowercase) from a new resolveSubgraphType() method:

```java
private static final Set<String> COGNITIVE_TYPES = Set.of(
    "belief", "intention", "prediction", "judgment", "fear", "desire");

private String resolveSubgraphType(String normalizedType) {
    if (COGNITIVE_TYPES.contains(normalizedType)) return SubgraphTypes.COGNITIVE;
    return normalizedType;
}
```

### Property Setting

In `applyExtraction()`, before subgraph routing, preserve the original cognitive type as a property:

```java
String normalizedType = normalizeType(pe.type());
if (COGNITIVE_TYPES.contains(normalizedType)) {
    // Add cognitiveKind to the node's properties
    properties.put("cognitiveKind", normalizedType);
}
String sgType = resolveSubgraphType(normalizedType);
```

## TypeRegistry Integration

### Schema Derivation

Each cognitive trait interface is associated with its type in TypeRegistry via the `java-class` property, enabling `typeRegistry.schemaFor("belief", tenantId)` to return the Belieflike interface's schema (subject, status, basis).

In `CognitiveLoader.init()`:

```java
private static final Map<String, Class<?>> COGNITIVE_JAVA_CLASSES = Map.of(
    "belief", Belieflike.class,
    "intention", Intentionlike.class,
    "prediction", Predictive.class,
    "judgment", Evaluative.class,
    "fear", Fearlike.class,
    "desire", Desirelike.class
);
```

Registration uses the existing `registerType(name, parent, tenantId)` API. The java-class property must be set on the type node — this requires either extending `registerType()` to accept properties, or a follow-up `updateNode()` call to set the java-class property.

### CognitiveLoader Tenant Discovery

CognitiveLoader needs a tenant ID for type registration. TypeRegistry already handles lazy per-tenant bootstrap via `ensureBootstrapped(tenantId)` — called on every TypeRegistry method. CognitiveLoader injects TypeRegistry and calls `registerType()` per tenant.

For @PostConstruct registration, CognitiveLoader uses `CaseMemoryStore.discoverTenants()` (already available via `Instance<CaseMemoryStore>` with graceful degradation). For tenants discovered after startup, `registerType()` is idempotent — calling it for an already-registered type is a no-op (`if (bt.resolveTypeNode(normalized) != null) return`).

```java
// In CognitiveLoader.init(), after vocabulary registration:
for (String tenantId : discoverTenants()) {
    registry.registerType("cognitive", null, tenantId);
    for (var entry : COGNITIVE_JAVA_CLASSES.entrySet()) {
        registry.registerType(entry.getKey(), "cognitive", tenantId);
    }
}
```

## Consolidation Strategy (D7)

Cognitive nodes participate in the existing consolidation pipeline within the COGNITIVE subgraph:

- **MergeDetectionPhase** — detects duplicate cognitive nodes (same proposition extracted twice)
- **CommunitySummaryPhase** — clusters related cognitive content (e.g., a cluster of beliefs about a person)
- **CuriosityRefreshPhase** — identifies gaps in cognitive content

Per-cognitive-type consolidation behaviors (beliefs revised on contradiction, predictions validated against outcomes) require trait-aware consolidation phases — this is follow-on work dependent on the type system existing first.

## Taxonomy Rationale (D9)

The six types are chosen for their distinct consolidation lifecycle behaviors:

| Type | Lifecycle | Why not collapsed |
|------|-----------|-------------------|
| belief | Revised on contradiction | Predictions have timeframes; beliefs don't |
| intention | Checked for viability, achievement tracking | Desires lack the commitment/planning aspect |
| prediction | Validated against outcomes within timeframe | Temporal epistemic — distinct from beliefs |
| judgment | Compared with other evaluations | Stance-based, no lifecycle state |
| fear | Evaluated against current state | Severity-driven — distinct from desires |
| desire | Checked for fulfillment | Urgency-driven — distinct from intentions |

BDI (3 types) is too coarse: it collapses types with distinct processing needs. KARO adds concepts (factive Knowledge vs Belief) that confidence scoring already handles.

## Module Impact

| Module | Change |
|--------|--------|
| `mindmap-api` | Add `COGNITIVE` constant to SubgraphTypes |
| `mindmap-intelligence` | 6 trait interfaces, TypeRegistry java-class associations |
| `cognitive-index` | `cognitive-traits.yaml` in `rules/`, CognitiveLoader type registration |
| `mindmap-intelligence` | MindMapExtractor prompt + resolveSubgraphType() + cognitiveKind property |

No database migrations. No new modules. No SPI changes.

## Testing Strategy

1. **Trait interface proxy tests** — `Thing.as(Belieflike.class).subject()` returns correct property values
2. **TraitRule matching tests** — declarative rules fire correctly on cognitiveKind property; compositional rules fire multiple traits
3. **TypeRegistry hierarchy tests** — `subtypesOf("cognitive")` returns all 6 types; `typeExists("belief")` is true
4. **MindMapExtractor integration** — LLM extraction classifies cognitive content; cognitiveKind property set correctly; nodes routed to COGNITIVE subgraph
5. **Compositionality test** — a node with `cognitiveKind=belief` and `timeframe` property gains both Belieflike and Predictive traits

## References

- TypeRegistry.java:105-125 — registerType API
- TraitRule.java:5-8 — trait rule interface
- MindMapExtractor.java:39-64 — SYSTEM_PROMPT and type list
- MindMapExtractor.java:272-275 — normalizeType
- DeclarativeRuleRegistry.java:59-73 — YAML rule loading
- RuleCondition.java — sealed condition hierarchy
- CognitiveLoader.java — cognitive bootstrap lifecycle
- SubgraphTypes.java — subgraph type constants
- PersonableTraitRule.java, ThreateningTraitRule.java — existing trait rule patterns
- Personable.java, Eventlike.java, Projectlike.java — existing trait interface patterns
- decisions.md D1-D9 — full decision rationale and alternatives
