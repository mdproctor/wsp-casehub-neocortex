## D1: Overall approach — personality-modulated activation functions

**Choice:** Replace uniform logistic activation with per-parameter activation functions whose shape changes based on personality. Yerkes-Dodson peak position, Easterbrook narrowing rate, and fatigue resistance all derived from personality facets via CDE.

**Alternatives:**
- Situational strength multiplier — simpler math but can't represent Yerkes-Dodson inverted-U; patch on additive model rather than structural fix
- Separate extreme-intensity override layer — clean separation but introduces discontinuity at threshold boundary and doubles maintenance

**Rationale:** The literature (Yerkes-Dodson, Easterbrook, CAPS) describes continuous interaction effects. The inverted-U with personality-shifted peak is the core insight — only this approach can represent it structurally.

**Caveat (from review R1-10):** The Yerkes-Dodson inverted-U is a contested empirical generalisation (Corbett 2015, Teigen 1994). The design uses it as a modelling abstraction — "performance has a personality-specific peak and declines past it" — not as a literal neurophysiological claim. The quality test (personality×intensity interaction matrix) validates whether the abstraction produces meaningfully different LLM prompt outputs.

**Trade-offs:** Adds new fields to SearchBudgetConfig via sub-records. CDE derivation pathway gets more complex. All changes contained in SearchBudgetConfig + TickParticipant + CDE — no API surface change.

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

## D2: Activation function shape — exponential decay past peak

**Choice:** `activation = logistic(x, k, mid) * exp(-decay * max(0, x - peak))`. Two new parameters per budget dimension: `peak` (Yerkes-Dodson optimal arousal, personality-derived) and `decay` (sharpness of decline past peak). decay=0 means `exp(0)=1` — preserves current flat-ceiling behaviour for traits that sustain at extremes.

**Revision (from review R1-03):** Changed from quadratic penalty (`logistic - decay * (x-peak)²`) to exponential decay (`logistic * exp(-decay * max(0, x-peak))`). The exponential form:
- Is naturally non-negative (multiplicative, not subtractive) — no risk of composite going below 0
- Produces asymmetric decline (rapid initial drop, gradual plateau toward zero) — more faithful to empirical curves than symmetric quadratic
- Has no second-derivative discontinuity at the peak — smooth curvature transition
- Degrades gracefully: as intensity → 1.0 with high decay, activation approaches 0 smoothly

**Alternatives:**
- Quadratic penalty (`logistic - decay * max(0, x-peak)²`) — subtractive, can go negative before clamp01, symmetric decline not supported by empirical curves
- Gaussian-windowed logistic — also attenuates below the peak, which isn't literature-supported
- Asymmetric beta function — maximum flexibility but non-intuitive params, breaks CapsSettler logistic precedent

**Rationale:** The exponential multiplier only reduces activation past the peak (the `max(0,...)` clamp ensures `exp(0)=1` below peak), preserving current moderate-range behaviour. Multiplicative structure means the result inherits the logistic's (0,1) range without needing clamping. Two params with clear physical meaning.

**Trade-offs:** 8 new fields (4 peaks + 4 decays), later consolidated by D5 to 1 peak + 4 decays = 5 new fields.

**Depends on:** D1 (personality-modulated activation functions)

**Sources:**
- Yerkes & Dodson (1908) — inverted-U shape
- Eysenck & Eysenck (1985) — personality shifts peak position
- CapsSettler logistic precedent in caps-engine

**Exploration:** quick
**Status:** revised

## D3: Drive modulation scaling — intensity-scaled factor

**Choice:** Replace fixed additive modulations with `modulation * scalingFactor(intensity, personality)` where `scalingFactor = 1.0 + amplificationRate * max(0, intensity - extremePeak)`. At moderate intensity (below peak) the factor is 1.0 (preserves current behaviour). At extremes, personality-derived `amplificationRate` per parameter makes modulations grow (amplification), shrink (compression), or reverse.

**Negative scaling factors (from review R1-05):** Negative scaling factors are intentional for specific trait × parameter combinations. Convergence under neuroticism should reverse at extreme intensity — the curiosity convergence delay (+0.1) becomes a convergence *acceleration* as anxiety overrides exploratory drive. The scaling factor is clamped at `max(-1.0, scalingFactor)` to prevent unbounded reversal. The spec must document which combinations produce reversals and why.

**Threshold unification (from review R1-04):** D3's amplification threshold uses the same `extremePeak` from D2. The reviewer notes these are conceptually distinct — D2's peak is "performance starts declining" while D3's threshold is "personality expression starts scaling." This is an acknowledged simplification: both represent "where extreme behaviour begins" and diverge by less than the output resolution justifies. If empirical testing shows meaningful divergence, the threshold can be separated without breaking the config structure (add an optional `amplificationThreshold` field to `ExtremeInteractionConfig`).

**Alternatives:**
- Purely multiplicative `base * (1 + multiplier)` — naturally scales but weakens personality at low intensity, contradicting Situational Strength Theory (personality should be MOST expressed at low intensity)
- Non-linear per-drive profiles — too many degrees of freedom (4 drives × 4 parameters × curve shape)

**Rationale:** Preserves the well-tested additive behaviour at moderate intensity while allowing the three interaction types at extremes. One rate per parameter from CDE keeps config manageable.

**Trade-offs:** Shares the extremePeak threshold with D2 — a simplification (see above). Negative scaling can reverse modulations, which is a meaningful cognitive claim that must be validated.

**Depends on:** D1 (personality-modulated activation functions), D5 (extremePeak)

**Sources:**
- Meyer, Dalal & Hermida (2010) — personality-performance r=0.23 weak situations vs r=0.09 strong
- Dalal, Meyer et al. (2015) — trait-specific response to situational strength
- Current additive modulations in SearchBudgetTickParticipant.java:143-188

**Exploration:** quick
**Status:** revised

## D4: Fatigue dynamics — per-parameter strategic reallocation

**Choice:** Fatigue modelled as per-parameter strategic reallocation (Hockey 1997 Compensatory Control), not uniform depletion (Baumeister 1998 ego depletion — replication-contested, d=0.25). Each parameter has a personality-derived fatigue effect coefficient in [-1,1] determining direction and magnitude. Logarithmic temporal accumulation matching vigilance decrement literature. Gradual recovery (not reset) when intensity drops below peak.

**Mechanism:**
- Fatigue accumulates when intensity exceeds the `extremePeak` from D2/D5 (same threshold, different phenomenon: D2 is immediate peak-decline, D4 is temporal accumulation)
- `fatigueLevel = min(1.0, log(1 + ticksAbove) / log(1 + maxTicks))` — rapid initial onset, plateau (Warm, Parasuraman & Matthews 2008). Clamped at 1.0 to prevent unbounded effects when ticksAbove exceeds maxTicks (from review R1-07).
- Recovery: `ticksAbove = max(0, ticksAbove - recoveryRate)` — gradual, personality-derived (Hockey refractory period). Note: logarithmic accumulation produces hysteresis — recovery is fast when fatigue is low and slow when fatigue is high (from review R1-08). This matches Hockey's refractory period: deeply fatigued agents recover slowly.
- Per-parameter: `param += fatigueLevel * paramEffect`

**Per-parameter reallocation pattern:**

| Trait | Depth | Breadth | Laterality | Convergence | Mechanism |
|---|---|---|---|---|---|
| Conscientious | Protected (≈0) | Sacrificed (−) | Sacrificed (−) | Accelerated (+) | Hockey: primary task protection, satisficing |
| Neurotic | Vulnerable (−) | Rapidly sacrificed (−) | Noise (+) | Blocked (−) | Sarason: worry consumes resources |
| Open | Protected (≈0) | Slowly sacrificed (−) | Slowly sacrificed (−) | Neutral (≈0) | Ego-syntonic exploration costs less |
| Impulsive | Vulnerable (−) | Rapidly sacrificed (−) | Random jumps (+)† | Premature (+) | Executive control degrades first |

† Impulsivity→positive laterality is a second-order prediction (from review R1-11). Supported by inference (impulsivity = weak executive control + degraded control → random associations) but not directly validated experimentally. Easterbrook would predict narrowing for everyone. Flag as speculative in quality tests — if empirical testing shows narrowing instead, set to negative.

**Config:** Bundled as `FatigueConfig` sub-record on `SearchBudgetConfig` (nullable, like `channelModulation`):
```java
FatigueConfig(int maxTicks, double recoveryRate,
              double depthEffect, double breadthEffect,
              double lateralityEffect, double convergenceEffect)
```

**Fatigue state lifecycle (from review R1-13):**
- `FatigueState` record (`int ticksAbove`) stored in `ConcurrentHashMap<String, FatigueState>` on `SearchBudgetTickParticipant` alongside existing `results` map
- Created on first tick where intensity > extremePeak
- Survives across ticks within a session (temporal accumulator)
- Destroyed when agent is deregistered or process restarts — transient per-process state, not persisted
- Full recovery (ticksAbove returns to 0) removes the entry from the map

**Interaction with pathological threshold (from review R1-15):** Pathological threshold is evaluated first — if convergence collapses to 0 via the existing `pathologicalThreshold` check, fatigue effects on convergence are irrelevant (already floored). Fatigue effects apply to the other three parameters normally. Ordering: base activation (D2) → drive modulation (D3) → pathological check → fatigue reallocation (D4) → channel modulation → clamp01.

**Independence from RegulationFatigueTracker (from review R1-06):** Search fatigue and regulation fatigue are independent models for different phenomena. Search fatigue is arousal-driven cognitive narrowing (sustained high motivation degrades exploration capacity). Regulation fatigue is willpower depletion (suppressing emotions costs effort — Bosse et al. 2010). Different mechanisms, different resource pools. An agent can be regulation-fatigued (exhausted from suppressing anger) without being search-fatigued (motivation intensity is moderate). If future work reveals they share a resource pool, a shared substrate can be extracted — but the current evidence supports independence.

**Alternatives:**
- Uniform multiplier (Baumeister depletion) — replication-contested, masks per-parameter reallocation that Hockey's model predicts and that produces meaningfully different profiles
- Exponential decay from peak — conflates Yerkes-Dodson peak-decline (immediate) with fatigue (temporal); they're different phenomena
- Memory-backed tracking — cross-session persistence for within-session transient state; unnecessary dependency

**Rationale:** Hockey's compensatory control is better-grounded than Baumeister's ego depletion. Strategic reallocation produces the personality-differentiated fatigue profiles the issue requires: conscientious agents protect depth at the cost of breadth (discipline sustains focus), neurotic agents lose depth AND convergence (worry scatters AND blocks). The logarithmic accumulation matches vigilance decrement empirics. Sharing the Yerkes-Dodson peak as fatigue threshold is elegant — same personality-derived point triggers both the immediate activation decline and temporal fatigue accumulation.

**Trade-offs:** Per-parameter fatigue is more complex than a single multiplier. Relies on Hockey's model which, while well-supported, is harder to communicate than "resources deplete." Six new config fields on FatigueConfig. The impulsivity→positive laterality effect is speculative (see † above).

**Depends on:** D1 (personality-modulated activation), D2/D5 (extremePeak as fatigue threshold)

**Sources:**
- Hockey, G.R.J. (1997). Compensatory control in the regulation of human performance under stress and high workload. *Biological Psychology*, 45, 73-93.
- Warm, J.S., Parasuraman, R. & Matthews, G. (2008). Vigilance requires hard mental work and is stressful. *Human Factors*, 50(3), 433-441.
- Sarason, I.G. (1975). Anxiety and self-preoccupation — attentional resource competition
- Kahneman, D. (2011). *Thinking, Fast and Slow* — attention as finite resource
- Carter, E.C. & McCullough, M.E. (2014). Ego depletion meta-analysis, d=0.25 — contested replication

**Exploration:** deep-analysis
**Status:** revised

## D5: Config structure — single peak + two sub-records

**Choice:** One agent-level `extremePeak` on `SearchBudgetConfig` (Yerkes-Dodson arousal tolerance, CDE-derived from anxiousness/emotional lability). Two nullable sub-records:
- `ExtremeInteractionConfig(depthDecay, breadthDecay, lateralityDecay, convergenceDecay, depthAmplification, breadthAmplification, lateralityAmplification, convergenceAmplification)` — 8 fields
- `FatigueConfig(maxTicks, recoveryRate, depthEffect, breadthEffect, lateralityEffect, convergenceEffect)` — 6 fields

Total: 1 (peak) + 8 (interaction) + 6 (fatigue) = 15 new fields. SearchBudgetConfig grows from 11 to 14 top-level fields (peak + 2 nullable sub-records).

**Single peak simplification (from review R1-02):** The original Yerkes-Dodson finding was about task complexity — simple tasks peak at higher arousal, complex tasks peak lower. Within the search budget, depth (complex systematic analysis) and breadth (simpler parallel scanning) arguably have different optimal arousal points. A single `extremePeak` treats them identically. This is an acknowledged simplification: the LLM prompt rendering resolution (prose descriptions of cognitive state) doesn't benefit from a 0.1 difference in per-parameter peak position. The per-parameter `decay` values in `ExtremeInteractionConfig` capture the magnitude of the Yerkes-Dodson effect per parameter — a zero decay on depth for a conscientious agent means depth doesn't decline past peak even though the peak is agent-level. If future validation shows per-parameter peaks are needed, they can be added to `ExtremeInteractionConfig` without breaking the top-level structure.

**Alternatives:**
- Full per-parameter peaks (4 × peak) — more degrees of freedom than the output resolution justifies; can be added later to ExtremeInteractionConfig if needed
- Flat fields on SearchBudgetConfig — no sub-records, record grows from 11 to 26+ fields, unwieldy

**Rationale:** Nullable sub-records follow the channelModulation precedent — null disables the feature, keeping the defaults path simple. The per-parameter `decay` captures most of the Yerkes-Dodson task-complexity effect (zero decay = no decline = effectively infinite peak for that parameter).

**Trade-offs:** Single peak loses the task-complexity dimension of Yerkes-Dodson. Mitigated by per-parameter decay (zero decay = no decline, regardless of peak position).

**Depends on:** D2 (peak positions), D3 (amplification thresholds), D4 (fatigue config)

**Sources:**
- Eysenck & Eysenck (1985) — arousal tolerance as personality-level property
- Yerkes & Dodson (1908) — task complexity shifts peak (original mechanism, simplified here)
- SearchBudgetConfig.channelModulation pattern — nullable sub-record precedent

**Exploration:** quick
**Status:** revised

## D6: Config construction — withX() copy methods

**Choice:** Add `withX()` copy methods to `SearchBudgetConfig`, `ExtremeInteractionConfig`, and `FatigueConfig`. Construction: `SearchBudgetConfig.defaults().withExtremePeak(0.6).withExtremeInteraction(ExtremeInteractionConfig.defaults().withDepthDecay(0.0))`.

**Revision (from review R1-09):** Changed from builder pattern to `withX()` copy methods, following the established `CognitiveDefaults` convention. No config record in `cognitive-api` uses builders — `CognitiveDefaults` at 19 fields uses `withX()` methods. Introducing builders selectively for `SearchBudgetConfig` would create an inconsistency.

**Alternatives:**
- Builder classes — no precedent in the module; would be the only config record with builders while CognitiveDefaults (19 fields) uses withX()
- Positional constructors only — 14-arg calls are error-prone, but defaults() + withX() handles the override pattern

**Rationale:** `withX()` on records is idiomatic, consistent with the module, requires no new classes, and handles the "CDE only sets fields it needs to override" pattern equally well.

**Depends on:** D5 (config structure with sub-records)

**Sources:**
- CognitiveDefaults.withX() pattern — established convention in cognitive-index
- SearchBudgetConfig.defaults() — existing factory method

**Exploration:** quick
**Status:** revised
