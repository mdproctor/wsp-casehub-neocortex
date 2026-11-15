# D6 Exploration: Personality → Coping Strategy Mapping

## The Question

How should personality influence coping strategy selection?

## First-Principles Analysis

### Two independently-resolvable signals

Strategy selection involves two forces:
1. **Personality disposition** (stable, numeric, resolved) — Big Five scores
   encode coping tendencies. Mechanical computation works here.
2. **Situational viability** (variable, semantic, unresolved) — whether a
   strategy CAN work depends on narrative understanding of controllability,
   stakes, social context.

Strategy selection = personality tendency × situational viability.

### The semantic resolution boundary

- Personality tendency → numeric, resolved → mechanical predictor
- Situational viability → semantic, unresolved → LLM
- This is exactly the RegulationStrategyPredictor + GenerationPhase pattern

### EMA's selection sequence

1. Identify coping opportunity (intensity > threshold)
2. Propose viable strategies based on appraisal features (controllability, changeability)
3. Assess coping potential — rank by expected impact
4. Personality resolves ties among similarly-viable strategies

Personality doesn't blindly suggest — it resolves among viable options.
The predictor must also filter by controllability/adjustability (numeric, from SEC).

### Correlation strength (literature)

| Big Five trait | Coping tendency | Evidence |
|---|---|---|
| Conscientiousness | Planful, problem-focused | Meta-analytic, strong |
| Neuroticism | Emotion-focused, avoidant | Meta-analytic, strong |
| Openness | Positive reinterpretation | Moderate |
| Agreeableness | Seek social support | Moderate |
| Extraversion | Active coping, support seeking | Moderate |

Same strength as Barańczuk 2019 correlations used for RegulationDefaults.

### Why the predictor earns its keep

1. **Consistency** — same formula every time vs LLM variability
2. **Observability** — traceable decision chain for eval
3. **Cost** — in a micro-loop, skipping LLM when predictor has high confidence saves
4. **Pattern coherence** — matches regulation pipeline architecture

## Recommendation: Hybrid with CopingDefaults

CopingDefaults derived from Big Five via CDE (following RegulationDefaults pattern):
- planfulTendency (conscientiousness)
- reinterpretationTendency (openness)
- avoidanceTendency (neuroticism)
- supportSeekingTendency (agreeableness + extraversion)
- acceptanceTendency (inverse neuroticism)

CopingStrategyPredictor:
1. Reads CopingDefaults + SEC dimensions (controllability, adjustability)
2. Filters to viable strategies based on controllability
3. Applies personality bias among viable strategies
4. Produces Optional<CopingPrediction> — suggested strategy with confidence

LLM coping phase:
1. Receives prediction as bias/pin
2. Evaluates full situational context
3. Makes final selection
4. Produces reinterpreted narrative + effects
