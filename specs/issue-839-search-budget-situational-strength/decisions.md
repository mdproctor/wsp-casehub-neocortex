## D1: Overall approach — personality-modulated activation functions

**Choice:** Replace uniform logistic activation with per-parameter activation functions whose shape changes based on personality. Yerkes-Dodson peak position, Easterbrook narrowing rate, and fatigue resistance all derived from personality facets via CDE.

**Alternatives:**
- Situational strength multiplier — simpler math but can't represent Yerkes-Dodson inverted-U; patch on additive model rather than structural fix
- Separate extreme-intensity override layer — clean separation but introduces discontinuity at threshold boundary and doubles maintenance

**Rationale:** The literature (Yerkes-Dodson, Easterbrook, CAPS) describes continuous interaction effects. The inverted-U with personality-shifted peak is the core insight — only this approach can represent it structurally.

**Trade-offs:** Adds 5-8 fields to SearchBudgetConfig. CDE derivation pathway gets more complex. All changes contained in SearchBudgetConfig + TickParticipant + CDE — no API surface change.

**Sources:**
- `cognition/src/main/java/io/casehub/neocortex/cognition/search/SearchBudgetTickParticipant.java` — current logistic activation
- `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/SearchBudgetConfig.java` — current config record
- `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java:646` — current CDE derivation
- `docs/specs/issue-765-cognitive-richness/2026-11-05-cognitive-search-budget-design.md` — original design
- Meyer, Dalal & Hermida (2010) — situational strength theory
- Yerkes & Dodson (1908) — inverted-U with personality-shifted peak
- Easterbrook (1959) — cue-utilisation narrowing under arousal
- Mischel & Shoda (1995) — CAPS rigid narrowing at extremes

**Exploration:** quick
**Status:** captured

## D2: Activation function shape — logistic minus quadratic penalty

**Choice:** `activation = logistic(x, k, mid) - decay * max(0, x - peak)²`. Two new parameters per budget dimension: `peak` (Yerkes-Dodson optimal arousal, personality-derived) and `decay` (sharpness of decline past peak). decay=0 preserves current flat-ceiling behaviour for traits that sustain at extremes.

**Alternatives:**
- Gaussian-windowed logistic — also attenuates below the peak, which isn't literature-supported
- Asymmetric beta function — maximum flexibility but non-intuitive params, breaks CapsSettler logistic precedent

**Rationale:** The quadratic penalty only activates past the peak (max(0,...) clamp), preserving current moderate-range behaviour. Two params with clear physical meaning. Monotonically increasing below peak, inverted-U above — exactly Yerkes-Dodson.

**Trade-offs:** More parameters on SearchBudgetConfig (8 new: 4 peaks + 4 decays). The quadratic penalty is an approximation — real Yerkes-Dodson curves may be asymmetric — but it's sufficient for the prompt-rendering resolution.

**Depends on:** D1 (personality-modulated activation functions)

**Sources:**
- Yerkes & Dodson (1908) — inverted-U shape
- Eysenck & Eysenck (1985) — personality shifts peak position
- CapsSettler logistic precedent in caps-engine

**Exploration:** quick
**Status:** captured

## D3: Drive modulation scaling — intensity-scaled factor

**Choice:** Replace fixed additive modulations with `modulation * scalingFactor(intensity, personality)` where `scalingFactor = 1.0 + amplificationRate * max(0, intensity - amplificationThreshold)`. At moderate intensity the factor is 1.0 (preserves current behaviour). At extremes, personality-derived `amplificationRate` per parameter makes modulations grow (amplification), shrink (compression), or reverse.

**Alternatives:**
- Purely multiplicative `base * (1 + multiplier)` — naturally scales but weakens personality at low intensity, contradicting Situational Strength Theory (personality should be MOST expressed at low intensity)
- Non-linear per-drive profiles — too many degrees of freedom (4 drives × 4 parameters × curve shape)

**Rationale:** Preserves the well-tested additive behaviour at moderate intensity while allowing the three interaction types at extremes. One rate + threshold per parameter from CDE keeps config manageable.

**Trade-offs:** The amplification threshold is a second "inflection point" alongside the Yerkes-Dodson peak — could be confusing if they diverge. In practice they should be close: both represent "where extreme behaviour begins."

**Depends on:** D1 (personality-modulated activation functions)

**Sources:**
- Meyer, Dalal & Hermida (2010) — personality-performance r=0.23 weak situations vs r=0.09 strong
- Dalal, Meyer et al. (2015) — trait-specific response to situational strength
- Current additive modulations in SearchBudgetTickParticipant.java:143-188

**Exploration:** quick
**Status:** captured

## D4: Fatigue dynamics — per-parameter strategic reallocation

**Choice:** Fatigue modelled as per-parameter strategic reallocation (Hockey 1997 Compensatory Control), not uniform depletion (Baumeister 1998 ego depletion — replication-contested, d=0.25). Each parameter has a personality-derived fatigue effect coefficient in [-1,1] determining direction and magnitude. Logarithmic temporal accumulation matching vigilance decrement literature. Gradual recovery (not reset) when intensity drops below peak.

**Mechanism:**
- Fatigue accumulates when intensity exceeds the Yerkes-Dodson peak from D2 (same threshold, different phenomenon: D2 is immediate peak-decline, D4 is temporal accumulation)
- `fatigueLevel = log(1 + ticksAbove) / log(1 + maxTicks)` — rapid initial onset, plateau (Warm, Parasuraman & Matthews 2008)
- Recovery: `ticksAbove = max(0, ticksAbove - recoveryRate)` — gradual, personality-derived (Hockey refractory period)
- Per-parameter: `param += fatigueLevel * paramEffect`

**Per-parameter reallocation pattern:**

| Trait | Depth | Breadth | Laterality | Convergence | Mechanism |
|---|---|---|---|---|---|
| Conscientious | Protected (≈0) | Sacrificed (−) | Sacrificed (−) | Accelerated (+) | Hockey: primary task protection, satisficing |
| Neurotic | Vulnerable (−) | Rapidly sacrificed (−) | Noise (+) | Blocked (−) | Sarason: worry consumes resources |
| Open | Protected (≈0) | Slowly sacrificed (−) | Slowly sacrificed (−) | Neutral (≈0) | Ego-syntonic exploration costs less |
| Impulsive | Vulnerable (−) | Rapidly sacrificed (−) | Random jumps (+) | Premature (+) | Executive control degrades first |

**Config:** Bundled as `FatigueConfig` sub-record on `SearchBudgetConfig` (nullable, like `channelModulation`):
```java
FatigueConfig(int maxTicks, double recoveryRate,
              double depthEffect, double breadthEffect,
              double lateralityEffect, double convergenceEffect)
```

**Alternatives:**
- Uniform multiplier (Baumeister depletion) — replication-contested, masks per-parameter reallocation that Hockey's model predicts and that produces meaningfully different profiles
- Exponential decay from peak — conflates Yerkes-Dodson peak-decline (immediate) with fatigue (temporal); they're different phenomena
- Memory-backed tracking — cross-session persistence for within-session transient state; unnecessary dependency

**Rationale:** Hockey's compensatory control is better-grounded than Baumeister's ego depletion. Strategic reallocation produces the personality-differentiated fatigue profiles the issue requires: conscientious agents protect depth at the cost of breadth (discipline sustains focus), neurotic agents lose depth AND convergence (worry scatters AND blocks). The logarithmic accumulation matches vigilance decrement empirics. Sharing the Yerkes-Dodson peak as fatigue threshold is elegant — same personality-derived point triggers both the immediate activation decline and temporal fatigue accumulation.

**Trade-offs:** Per-parameter fatigue is more complex than a single multiplier. Relies on Hockey's model which, while well-supported, is harder to communicate than "resources deplete." Six new config fields on FatigueConfig. The impulsivity→positive laterality effect (random jumps under degraded executive control) is a second-order prediction — harder to validate.

**Depends on:** D1 (personality-modulated activation), D2 (Yerkes-Dodson peak as fatigue threshold)

**Sources:**
- Hockey, G.R.J. (1997). Compensatory control in the regulation of human performance under stress and high workload. *Biological Psychology*, 45, 73-93.
- Warm, J.S., Parasuraman, R. & Matthews, G. (2008). Vigilance requires hard mental work and is stressful. *Human Factors*, 50(3), 433-441.
- Sarason, I.G. (1975). Anxiety and self-preoccupation — attentional resource competition
- Kahneman, D. (2011). *Thinking, Fast and Slow* — attention as finite resource
- Carter, E.C. & McCullough, M.E. (2014). Ego depletion meta-analysis, d=0.25 — contested replication

**Exploration:** deep-analysis
**Status:** captured

## D5: Config structure — single peak + two sub-records

**Choice:** One agent-level `extremePeak` on `SearchBudgetConfig` (Yerkes-Dodson arousal tolerance, CDE-derived from anxiousness/emotional lability). Two nullable sub-records:
- `ExtremeInteractionConfig(depthDecay, breadthDecay, lateralityDecay, convergenceDecay, depthAmplification, breadthAmplification, lateralityAmplification, convergenceAmplification)` — 8 fields
- `FatigueConfig(maxTicks, recoveryRate, depthEffect, breadthEffect, lateralityEffect, convergenceEffect)` — 6 fields

Total: 1 (peak) + 8 (interaction) + 6 (fatigue) = 15 new fields. SearchBudgetConfig grows from 11 to 14 top-level fields (peak + 2 nullable sub-records).

**Alternatives:**
- Full per-parameter peaks (4 × peak) — more degrees of freedom than literature supports; Yerkes-Dodson peak is an agent-level property (arousal tolerance), not parameter-specific
- Flat fields on SearchBudgetConfig — no sub-records, record grows from 11 to 26+ fields, unwieldy

**Rationale:** D3's amplification threshold and D2's peak serve the same purpose — "where extreme behaviour begins." Unifying them as a single agent-level `extremePeak` saves 4 fields and is more accurate: the literature describes arousal tolerance as a personality trait, not as a per-cognitive-parameter property. Nullable sub-records follow the channelModulation precedent — null disables the feature, keeping the defaults path simple.

**Trade-offs:** Single peak means we can't model a personality that peaks early for convergence but late for depth. The literature doesn't predict this level of specificity, so this is acceptable.

**Depends on:** D2 (peak positions), D3 (amplification thresholds), D4 (fatigue config)

**Sources:**
- Eysenck & Eysenck (1985) — arousal tolerance as personality-level property
- SearchBudgetConfig.channelModulation pattern — nullable sub-record precedent

**Exploration:** quick
**Status:** captured

## D6: Builder classes for config records

**Choice:** Add static `builder()` factory methods returning fluent builders for `SearchBudgetConfig`, `ExtremeInteractionConfig`, and `FatigueConfig`. Builders pre-populated with defaults. Records remain immutable — builder is the construction API.

**Rationale:** SearchBudgetConfig grows to 14 constructor args. ExtremeInteractionConfig has 8. Positional constructor calls are unreadable and error-prone at this scale. Builders with defaults mean CDE and YAML parsing only set the fields they need to override.

**Trade-offs:** Three new builder inner classes. Boilerplate, but the alternative (14-arg constructor calls in tests and CDE) is worse.

**Depends on:** D5 (config structure with sub-records)

**Sources:**
- Existing pattern: no current builder precedent in neocortex config records, but standard Java practice for records with >5 fields

**Exploration:** quick
**Status:** captured
