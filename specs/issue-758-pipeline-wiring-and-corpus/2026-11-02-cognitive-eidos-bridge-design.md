# Cognitive-Eidos Bridge — Design Spec

**Issue:** casehubio/neocortex#753
**Branch:** issue-758-pipeline-wiring-and-corpus
**Date:** 2026-11-02

## Problem

Sixteen Manor characters have rich personality descriptors in eidos (disposition axes, Jungian profiles, goals) but `CognitiveDefaultsRegistry` is empty. All characters share identical fallback cognitive parameters — same mood baseline, same curiosity weights, same memory retrieval scoring. The personality data stops at eidos and never reaches the cognitive pipeline.

Additionally, `AgentExperienceService.recall()` queries `CaseMemoryStore` directly, bypassing `CognitiveMemoryRetriever` which is on the classpath but unused. Even with cognitive profiles, memory retrieval would remain unmodulated.

## Scope

**In scope:**
- New `cognitive-eidos/` module in neocortex — runtime bridge from eidos descriptors to CognitiveDefaults
- Route `AgentExperienceService.recall()`, `recallRelationships()`, `recallReflections()` through `CognitiveMemoryRetriever` (casehub-mosaic change)
- Verify personality differentiation is visible in cognitive pipeline output

**Not in scope:**
- CognitionCore → CharacterCognition wiring (already done)
- Salience pipeline wiring (done in #748)
- Retrieval modulation framework (done in #749, #750)
- Changes to CognitiveDerivationEngine derivation pathways

## Architecture

### Part 1: cognitive-eidos/ module (neocortex)

New module: `casehub-neocortex-cognitive-eidos`

**Dependencies:**
- `casehub-eidos-api` — provides `AgentDescriptor`, `AgentDisposition`, `AgentGoal`
- `casehub-neocortex-cognitive-index` — provides `CognitiveDefaultsRegistry`, `CognitiveDerivationEngine`, `DescriptorView`, `DispositionAxes`

**Key class:** `EidosCognitiveProfileBridge`
- `@ApplicationScoped`
- Injects eidos descriptor provider via `Instance<>` for graceful degradation when eidos is not on classpath
- `@PostConstruct` or `@Observes StartupEvent`: iterates all available `AgentDescriptor` instances
- For each descriptor:
  1. Extracts `AgentDisposition` → builds `DispositionAxes` from `primaryTerm()` per axis
  2. Extracts `dispositionProfile()` → converts `List<DispositionValue>` to `List<WeightedTerm>`
  3. Extracts `goals()` → `List<String>` from `AgentGoal.name()`
  4. Constructs `DescriptorView(agentId, axes, profile, goals)`
  5. Calls `CognitiveDerivationEngine.deriveAndMerge(descriptorView, existingOverrides)` — YAML overrides from classpath profiles take precedence over derived values
  6. Calls `CognitiveDefaultsRegistry.register(cognitiveDefaults)`

**Mapping detail:**

| Eidos type | Method | Neocortex type | Field |
|---|---|---|---|
| `AgentDisposition` | `primaryTerm("socialOrient")` | `DispositionAxes` | `socialOrient` |
| `AgentDisposition` | `primaryTerm("ruleFollowing")` | `DispositionAxes` | `ruleFollowing` |
| `AgentDisposition` | `primaryTerm("riskAppetite")` | `DispositionAxes` | `riskAppetite` |
| `AgentDisposition` | `primaryTerm("autonomy")` | `DispositionAxes` | `autonomy` |
| `AgentDisposition` | `primaryTerm("conflictMode")` | `DispositionAxes` | `conflictMode` |
| `AgentDisposition` | `dispositionProfile()` | `List<WeightedTerm>` | `dispositionProfile` |
| `AgentDescriptor` | `goals()` | `List<String>` | `goals` |

**Derivation pathways that fire automatically:**

1. Jungian disposition profile → `PersonalityWeights` (memory domain bias)
2. Disposition axes → `MoodBaseline` (PAD resting point)
3. Disposition + goals → `CuriosityConfig` (category weights)
4. Goals → `TemporalFocusConfig` (subgraph proximity weights)
5. Rule-following + risk appetite → `CbrStrategyDefaults` (minSimilarity, temporalDecayDays, RetrievalMode)
6. Social orientation + conflict mode → `SocialCognitionDefaults` (trustFormationRate, ConflictInterpretation)
7. Disposition profile → `GraphStructureDefaults` (InferenceStyle CONNECTIVE/CATEGORICAL/BALANCED)
8. Disposition profile → `ExtractionBiasDefaults` (relationshipBias, affectSensitivity)
9. Disposition profile → `AppraisalWeights` (empirically-grounded JPAF→Big Five→appraisal chain)
10. Risk appetite + rule-following + autonomy + goals → `HabituationConfig` (habituationRate, noveltyThreshold, repetitionTolerance, domainModulation)

**Override semantics:** `deriveAndMerge()` derives all ten pathways from the `DescriptorView`, then overlays any explicit values from YAML profiles (loaded by `CognitiveDefaultsRegistry` from classpath `cognitive-profiles/*.yaml`). Explicit values win. This allows per-character hand-tuning without losing derivation for everything else.

### Part 2: Modulated memory retrieval (casehub-mosaic)

**Target class:** `AgentExperienceService` in wacky-manor (slot 207)

**Change:** Inject `Instance<CognitiveMemoryRetriever>` alongside existing `CaseMemoryStore`. Route all three recall methods through the retriever when available:

- `recall()` (line 111) — currently `store.query()` with `MemoryQuery.forEntity()` ordering by SALIENCE
- `recallRelationships()` (line 127) — currently `store.query()` with relationship domain
- `recallReflections()` (line 140) — currently `store.query()` with reflection domain

**ModulationContext construction:** At recall time, build `ModulationContext` from:
- `personalityWeights` — from `CognitiveDefaultsRegistry.forAgent(agentId).personalityWeights()`
- `moodState` — from most recent mood memory via `CaseMemoryStore`, or null if unavailable
- `instant` — `Instant.now()`
- `tenantId` — from the existing query

`CognitiveMemoryRetriever.query(memoryQuery, modulationContext)` applies the modulation factor chain including domain weighting from personality weights. Characters with high `experience` weight score experience memories higher; characters with high `relationship` weight score interaction memories higher.

**Graceful degradation:** If `CognitiveMemoryRetriever` is not available (Instance unsatisfied), fall back to direct `CaseMemoryStore.query()` — identical to current behaviour.

### Part 3: Verification

Confirm that with cognitive profiles registered:
1. Different characters have different `CognitiveDefaults` — personality weights, mood baselines, and curiosity configs vary based on their eidos disposition
2. Memory retrieval ordering differs between characters — a character with high relationship weight surfaces relationship memories before experience memories, and vice versa
3. CognitionCore prompt sections render with differentiated parameters — drive descriptions, mood sections, and appraisal reflect the character's unique cognitive profile

## Module placement

```
neocortex/
  cognitive-eidos/
    pom.xml
    src/main/java/io/casehub/neocortex/cognitive/eidos/
      EidosCognitiveProfileBridge.java
```

Maven coordinates:
- artifactId: `casehub-neocortex-cognitive-eidos`
- Root Java package: `io.casehub.neocortex.cognitive.eidos`

## Trade-offs

- **Runtime eidos-api dependency** — cognitive-eidos/ has a compile dependency on `casehub-eidos-api`. Acceptable: eidos-api is a stable, published API module with no transitive weight.
- **Derivation runs at startup** — pure computation (no IO), negligible cost for 16 characters. Would need revisiting for hundreds of agents, but not a current concern.
- **One more neocortex module** — adds to the ~80 module count. Justified by clear single responsibility and reusability across eidos-consuming projects.
- **All recall modulated** — adds modulation overhead to every recall call. Lightweight (re-scoring existing results, no additional store queries).

## Decisions

- **D6:** Reusable `cognitive-eidos/` module in neocortex (not app-level wiring)
- **D7:** Runtime derivation at startup (not YAML generation)
- **D8:** All three recall methods modulated through `CognitiveMemoryRetriever`
- **D9:** Inject eidos descriptor provider directly via CDI (not SPI or event)

## References

- `cognitive-index/src/main/java/.../CognitiveDefaultsRegistry.java` — register() method at line 78
- `cognitive-index/src/main/java/.../CognitiveDerivationEngine.java` — deriveAndMerge() and 10 derivation pathways
- `cognitive-index/src/main/java/.../CognitiveMemoryRetriever.java` — ModulationContext-based query
- `cognitive-index/src/test/resources/cognitive-profiles/alice.yaml` — YAML profile format reference
- casehub-eidos-api: `AgentDescriptor`, `AgentDisposition`, `AgentGoal`
- casehub-mosaic slot 207: `AgentExperienceService.recall()` at line 111
- casehub-mosaic slot 207: `CharacterCognition.promptSections()` at lines 156-163
- casehub-mosaic slot 207: `descriptors-baseline.yaml` — eidos descriptor definitions
