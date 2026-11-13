# Personality-Aware Situation Classification — Design Spec

**Issue:** casehubio/neocortex#941
**Date:** 2026-11-13
**Status:** Draft

## Problem

The CAPS situation classifier produces identical activations regardless of which agent encounters a situation. A competitive agent and a cooperative agent receive the same CAPS input node activations for the same observation. Personality differentiation happens only through overlap filtering — which drive profiles match the activations — not through interpretive differences in how the situation is perceived.

This contradicts appraisal theory (Lazarus): personality shapes primary appraisal (what we perceive), not just secondary appraisal (how we respond). The CAPS topology already models secondary appraisal via disposition_modifiers on network connections. This spec adds primary appraisal — personality-shaped classification.

## Architecture

### Dual-level personality influence

| Level | Where | What it shapes | Mechanism |
|-------|-------|---------------|-----------|
| Classification (this spec) | `LlmSituationClassifier` prompt | Which CAPS input nodes activate | DispositionAxes → interpretive framing |
| Propagation (existing) | CAPS topology connections | How activations flow through network | disposition_modifiers → connection weight modulation |

DispositionAxes model interpretive *direction* (cooperative interprets social situations as connection opportunities). PID-5 facets model trait *magnitude* (how intensely someone expresses a trait). Both exist on `DescriptorView`; they serve different architectural purposes and should not be conflated.

### Hybrid A/C routing

Two personality injection paths, selected by a tension heuristic:

**Path A (default):** Personality description appended to the user prompt after the observation. Lightweight — the LLM applies personality as a filter.

**Path C (high tension):** Personality frame + tension narrative embedded in the system prompt. The LLM inhabits the interpretive frame rather than applying it externally. Triggered when disposition axes create internal psychological tension.

### Tension scoring

Static lookup table of conflicting axis value pairs. Each entry names a specific psychological conflict:

| riskAppetite | ruleFollowing | Score | Conflict |
|---|---|---|---|
| bold | strict | 1.0 | approach vs inhibition |

| autonomy | conflictMode | Score | Conflict |
|---|---|---|---|
| high | avoidant | 0.9 | independent but won't confront |

| socialOrient | autonomy | Score | Conflict |
|---|---|---|---|
| cooperative | high | 0.8 | group-oriented but self-directed |

| riskAppetite | conflictMode | Score | Conflict |
|---|---|---|---|
| bold | avoidant | 0.7 | acts but doesn't confront |

| socialOrient | autonomy | Score | Conflict |
|---|---|---|---|
| independent | low | 0.7 | independent identity but follows |

| socialOrient | ruleFollowing | Score | Conflict |
|---|---|---|---|
| competitive | strict | 0.6 | driven to win but bound by rules |

**Routing:** `maxTension > 0.5` → path C. Otherwise → path A.

The tension table lives in `LlmSituationClassifier` as a static data structure. It is evaluated at classify() time from the disposition metadata.

## Data Flow

### Personality through the SPI

Disposition axis values flow through the existing `Map<String, String> metadata` parameter on `SituationClassifier.classify()`. No SPI signature changes.

**Caller side (BehavioralSynthesisPhase):** Resolve `CognitiveDefaults` for the current agent from `defaultsRegistry`. Extract disposition axes. Serialize as metadata entries:
- `disposition.socialOrient` → axis value string
- `disposition.ruleFollowing` → axis value string
- `disposition.riskAppetite` → axis value string
- `disposition.autonomy` → axis value string
- `disposition.conflictMode` → axis value string

**Classifier side (LlmSituationClassifier):** Read `disposition.*` keys from metadata. Compute tension score. Route to path A or C. Build prompt accordingly.

### Scope

- **In scope:** BehavioralSynthesisPhase L145/L436 — add disposition metadata
- **Deferred:** DriveProfileDerivationPhase L196/L214 — separate eval needed
- **Separate concern:** CognitionObservationBuilder L520 — already passes agentId

### CBR caching fix (mandatory)

`CbrCachingSituationDecorator` (`@Decorator @Priority(60)`) caches classification results keyed by `SHA-256(description + eventType + cognitiveKind)`. Disposition metadata is NOT in the cache key. Without a fix, different personalities silently receive the same cached classification.

**Fix:** Include `disposition.*` metadata values in `computeCaseId()` hash. Add disposition values as categorical features in `lookupCbr()`/`storeCbr()` for CBR query filtering. Local to `CbrCachingSituationDecorator` — no new module dependencies.

## Prompt Design

### Path A — user prompt (low/no tension)

Appended after the observation description:

```
Character disposition: [socialOrient], [ruleFollowing] rule-following,
[riskAppetite] risk appetite, [autonomy] autonomy, [conflictMode] conflict style.
Classify the situation as this character would perceive it.
```

### Path C — system prompt (high tension)

System prompt rebuilt with personality frame before topology listing:

```
You are a psychological situation classifier perceiving the world
through a specific character's lens.

This character is [axis values]. [Tension narrative from lookup table].

Classify the following situation into CAPS input node activations.
[existing topology node listing]
```

Path C's user prompt ALSO includes axis values (same as path A), ensuring secondary tensions and full personality data remain visible.

### Tension narratives

| Pair | Narrative |
|---|---|
| bold + strict | "wants to act decisively but feels bound by rules — ambiguous situations feel like tests of whether the rules permit the action" |
| high autonomy + avoidant | "values independence but avoids confrontation — perceives social expectations as constraints but won't push against them directly" |
| cooperative + high autonomy | "drawn to group goals but resistant to group control — reads situations for both collaboration potential and threats to independence" |
| bold + avoidant | "impulsive toward action but shrinks from interpersonal friction — sees opportunities but worries about the social cost of seizing them" |
| independent + low autonomy | "identifies as self-reliant but defers to authority — notices when others lead but feels conflicted about following" |
| competitive + strict | "driven to win but constrained by propriety — seeks advantage within the rules, alert to where rules create or block competitive edges" |

## Eval Design

### Profiles

| Profile | Axes | Tension | Path | Expected bias |
|---|---|---|---|---|
| Competitive-assertive | competitive/flexible/bold/high/assertive | 0.0 | A | challenge, dominance |
| Cooperative-avoidant | cooperative/strict/conservative/low/avoidant | 0.0 | A | social harmony, caution |
| Bold-strict | competitive/strict/bold/moderate/collaborative | 1.0 | C | approach + inhibition dual-activation |
| Moderate baseline | cooperative/moderate/calculated/moderate/collaborative | 0.0 | A | neutral |

### Observations

At least 4 observations from distinct CAPS input categories (relationship, threat, achievement, social) to prevent observation-selection bias. Each observation should be ambiguous — legitimately mappable to multiple CAPS input nodes depending on interpretation.

### Metrics

1. **Inter-profile activation variance** — pairwise cosine distance between profiles' activation vectors. Personality-aware variance must exceed personality-agnostic null hypothesis variance.
2. **Tension dual-activation** — path C (bold-strict) should activate both approach AND inhibition nodes. Path A profiles should activate one or the other.
3. **Bias detection** — no profile should activate >80% of its observations to a single CAPS category. Personality should shape interpretation, not dominate it.

### Controls

- **Null hypothesis:** Same observation × 4 runs with personality-agnostic classifier. Establishes noise floor.
- **Temperature:** 0 for all LLM calls.
- **Deterministic mechanism tests:** Unit tests for tension scoring, prompt builder, routing logic. Independent of LLM.
- **Threshold sensitivity:** Test at 0.3, 0.5, 0.7 tension thresholds to validate the routing boundary.

## Implementation Scope

### New code
- `DispositionTension` — static utility: tension table + scoring from axis values
- `PersonalityPromptBuilder` — builds user-prompt or system-prompt personality framing based on tension score
- Metadata injection in `BehavioralSynthesisPhase` (2 call sites)
- Prompt integration in `LlmSituationClassifier.buildUserPrompt()` and system prompt rebuild
- CBR cache key fix in `CbrCachingSituationDecorator.computeCaseId()`

### Modified code
- `BehavioralSynthesisPhase` — extract disposition axes, pass as metadata
- `LlmSituationClassifier` — consume disposition metadata, route A/C, build personality-aware prompts
- `CbrCachingSituationDecorator` — include disposition in cache key hash

### Tests
- `DispositionTensionTest` — unit: tension scoring for all table entries + no-tension cases
- `PersonalityPromptBuilderTest` — unit: prompt output for path A and C
- `PersonalityClassificationEvalTest` — LLM eval: 4 profiles × 4+ observations with metrics

## References

- `LlmSituationClassifier.java` — current classifier implementation
- `SituationClassifier.java` — SPI signature
- `ClassificationContext.java` — context record
- `BehavioralSynthesisPhase.java` L145/L436 — classify() call sites
- `DriveProfileDerivationPhase.java` L196/L214 — deferred call sites
- `CbrCachingSituationDecorator.java` — CBR caching interaction
- `DispositionAxes.java` — axis definitions
- `CognitiveDerivationEngine.java` — axis-to-personality derivation
- Lazarus (1991) — appraisal theory: personality shapes primary appraisal
- Mischel & Shoda (1995) — CAPS: situation classification is personality-sensitive
