# Design Decisions — #840 Intelligence Capacity Layer

## D1: Capacity as first-class parameter, not personality-derived

**Choice:** Cognitive capacity is a first-class parameter orthogonal to personality, specified explicitly per agent in cognitive profile YAML, with CDE-derived defaults as fallback for unspecified agents.
**Alternatives:**
- Derive from Jungian profile (Ti+Te+Ni) — conflates cognitive style with cognitive ability. High-Ti means preference for logical analysis, not ability to do relational reasoning. Circular.
- Derive from PID-5 facets — PID-5 measures maladaptive pathology. DeYoung (2016) showed Intellect has no PID-5 counterpart. Structurally impossible.
- Derive from disposition axes — ruleFollowing/riskAppetite/autonomy are motivational constructs with no literature support as capacity proxies.
**Rationale:** Nusbaum & Silvia (2011) demonstrated the double dissociation: Openness predicts creativity not Gf; Intellect predicts Gf not creativity. DeYoung (2014) confirmed Intellect independently associates with g. Capacity is empirically orthogonal to personality — it requires its own representation, not a derivative of existing traits.
**Trade-offs:** Agents need explicit capacity specification for richest differentiation. Unspecified agents get compressed-range defaults.
**Sources:** DeYoung (2014) JPA 96(1); Nusbaum & Silvia (2011) PID 51; DeYoung et al. (2016) PMC4818976; Halford et al. (1998) BBS 21(6); Engle & Kane (2004) Psych L&M 44
**Exploration:** deep-analysis
**Status:** captured

## D2: Hard ceiling with capacity gap signal

**Choice:** Capacity applies as a hard ceiling (`Math.min(ceiling, raw)`) after fatigue and before clamp. The difference between unconstrained and constrained values produces a "capacity gap" signal that drives prose generation.
**Alternatives:**
- Soft ceiling (asymptotic) — `cap * (1 - exp(-raw/cap))`. More realistic for Mednick's gradient associative reach, but compresses the entire range including low values where capacity shouldn't matter. At LLM prompt rendering resolution (±0.1 qualitative levels), no visible benefit.
- Scaling factor (`raw * capacity`) — distorts low activations where capacity is irrelevant. At raw=0.3, capacity=0.7: scaling gives 0.21 (wrong), ceiling gives 0.30 (correct).
- Demand-dependent attenuation — capacity matters more at higher activation. More realistic but obscures the capacity gap signal and adds complexity for marginal prompt quality improvement.
**Rationale:** Hard ceiling produces the clearest signal for prose generation — the gap between what personality WANTS (unconstrained) and what capacity ALLOWS (constrained) IS the Openness/Intellect tension rendered as runtime data. Prose generator can detect the gap and render: "You want to bridge distant associations but lose the thread when the conceptual distance gets too far." At LLM prompt resolution, softer models produce equivalent qualitative output.
**Trade-offs:** Below-ceiling behavior is identical regardless of capacity (zero differentiation). Acceptable because below-ceiling means the agent isn't pushing limits — capacity isn't salient.
**Sources:** Halford et al. (1998) — quaternary limit is essentially hard; Engle & Kane (2004) — WMC as attention ceiling; #839 spec §Forward Interaction with Intelligence Capacity Layer
**Exploration:** deep-analysis
**Status:** captured

## D3: CognitiveCapacityConfig as top-level field on CognitiveDefaults

**Choice:** `CognitiveCapacityConfig` is a top-level nullable field on `CognitiveDefaults`, alongside `searchBudgetConfig`, `moodBaseline`, etc. Not nested inside `SearchBudgetConfig`.
**Alternatives:**
- Nested in SearchBudgetConfig — follows the pattern of ExtremeInteractionConfig and FatigueConfig. But capacity is conceptually broader than search budget per Cattell's Investment Theory (should eventually modulate learning rate in memory subsystem).
- Standalone config record loaded separately — unnecessary indirection when CognitiveDefaults already aggregates per-agent config.
**Rationale:** Capacity's first application is search budget ceilings, but Cattell's Investment Theory (higher Gf → more productive exploration → better knowledge integration) implies it should also modulate learning rate. Top-level placement means the memory subsystem can access it from CognitiveDefaults without reaching through SearchBudgetConfig.
**Trade-offs:** Slightly less cohesive than nesting in SearchBudgetConfig — the tick participant reads from two CognitiveDefaults fields instead of one SearchBudgetConfig. Marginal cost.
**Depends on:** D1 (capacity is first-class → needs its own config record)
**Sources:** Cattell (1987) Investment Theory; issue #840 §Relationship to Cattell's Investment Theory
**Exploration:** deep-analysis
**Status:** captured

## D4: Jungian-derived defaults with compressed range [0.55, 0.95]

**Choice:** When capacity isn't explicitly specified in cognitive profile YAML, derive from Jungian cognitive functions with compressed range [0.55, 0.95]. Relational complexity ← Ti+Te, associative reach ← Ne+Ni, working memory span ← Te+Si. Derivation extends existing `deriveSearchBudgetDefaults()` in CDE.
**Alternatives:**
- Flat defaults (all agents get 0.75) — simple and honest about the weak correlation, but zero differentiation between unspecified agents.
- Goals-derived — parse goals for cognitive demand indicators. Fragile, depends on text content.
- New CDE pathway — separate `deriveCapacityConfig()`. Unnecessary indirection when search budget derivation already processes the relevant Jungian inputs.
**Rationale:** Jungian functions → capacity is a weak proxy (r≈0.3-0.4 at best), but the compressed range [0.55, 0.95] is honest about this. The derivation can't produce extreme low values because "this personality profile makes you unintelligent" is an inference the data doesn't support. Provides personality-coherent differentiation without overclaiming. Explicit YAML specification overrides the derivation for richer agent profiles.
**Trade-offs:** Weak grounding for the specific Jungian→capacity mappings. Mitigated by compressed range — the derivation's influence is bounded.
**Depends on:** D1 (first-class with fallback derivation), D3 (on CognitiveDefaults)
**Sources:** DeYoung (2014) Intellect × Gf r≈0.3-0.4; Nusbaum & Silvia (2011) double dissociation
**Exploration:** deep-analysis
**Status:** captured

## D5: Independent fatigue-capacity interaction

**Choice:** Fatigue and capacity are independent for v1. Fatigue modifies raw parameter values, capacity caps the result. Pipeline order: base → extreme decay → drive modulations → channel modulation → fatigue → capacity ceiling → clamp.
**Alternatives:**
- Coupled: fatigue degrades capacity ceiling (`ceiling * (1 - fatigueLevel * degradationRate)`). More realistic — sustained cognitive load does degrade processing capacity. But couples two independent systems and risks double-counting since #839's fatigue already modifies the same parameters directly.
**Rationale:** The #839 spec explicitly anticipated this architecture: "capacity ceilings bound the maximum, fatigue effects modify within that bound. This is correct behavior." Keeping them independent for v1 is simpler, avoids double-counting, and was the designed integration point. #880 (shared fatigue substrate) already exists as a deferred issue for coupling them later.
**Trade-offs:** Misses the realistic phenomenon of capacity degradation under sustained load. Acceptable for v1 — the fatigue effects already model the degradation, capacity adds the ceiling.
**Depends on:** D2 (hard ceiling mechanism)
**Sources:** #839 spec §Forward Interaction with Intelligence Capacity Layer; #880 shared fatigue substrate deferred issue
**Exploration:** quick
**Status:** captured

## D6: No convergence ceiling

**Choice:** Convergence gets no capacity ceiling. Only three dimensions: relational complexity → depth, associative reach → laterality, working memory span → breadth.
**Alternatives:**
- Add inhibitory control ceiling for convergence — executive function inhibition (Miyake et al. 2000) is a capacity dimension. But Need for Cognitive Closure (Webster & Kruglanski 1994) blurs the capacity/personality boundary for convergence specifically.
**Rationale:** The issue defines exactly three capacity dimensions grounded in specific literature. Convergence (when to stop and synthesize) is personality-driven — conscientiousness, Need for Closure — not capacity-limited. Adding a fourth dimension would be ungrounded scope creep.
**Trade-offs:** Convergence is the only uncapped parameter. If empirical testing reveals convergence should be capacity-bounded, it can be added later without disrupting the architecture.
**Sources:** Issue #840 (three dimensions only); Webster & Kruglanski (1994) Need for Cognitive Closure
**Exploration:** quick
**Status:** captured

## D7: Learning rate modulation deferred

**Choice:** Cattell's Investment Theory implication (capacity modulates learning rate in memory subsystem) is noted in the spec but deferred to a follow-up issue.
**Alternatives:**
- Include in #840 scope — crosses module boundaries (cognitive-index → memory), separate concern from search budget ceilings. Would expand an already L-scale issue.
**Rationale:** CognitiveCapacityConfig placement on CognitiveDefaults (D3) enables future learning rate modulation without architectural changes. The search budget ceiling is the high-priority deliverable. Learning rate modulation is a natural follow-up once capacity infrastructure exists.
**Trade-offs:** Incomplete Cattell implementation. Acceptable — the foundation (capacity config) is in place for the extension.
**Depends on:** D3 (top-level placement enables future access from memory subsystem)
**Sources:** Cattell (1987) Investment Theory; issue #840 §Relationship to Cattell's Investment Theory
**Exploration:** quick
**Status:** captured

## D8: Prose generation — capacity-aware descriptions with gap signal

**Choice:** Extend `SearchBudgetDescriptionGenerationPhase` to include capacity parameters and gap signal. LLM prompt generates three descriptions: normal-range, extreme-intensity, and capacity-constrained. `SearchBudget` record gains `capacityConstrained` boolean flag (true when any gap > threshold) for tick-time prose selection. Prose section reads capacity config from CognitiveDefaults for detailed gap values.
**Alternatives:**
- Separate capacity prose section — fragments the cognitive self-description across two sections.
- Numeric-only (no prose) — capacity affects values but prose doesn't mention it. Misses the most interesting cognitive phenomenon: the Openness/Intellect tension.
**Rationale:** The capacity gap IS the cognitively interesting signal — "wants to explore but can't sustain it." The prose generator should render this tension explicitly. Following the #839 pattern (normal + extreme descriptions + boolean flag for selection), adding a third description variant is natural.
**Trade-offs:** Three-description LLM call is slightly more expensive than two. Marginal cost.
**Depends on:** D2 (gap signal), D3 (capacity config accessible from CognitiveDefaults)
**Sources:** #839 spec §Prose Generation; DeYoung (2014) Openness vs Intellect tension
**Exploration:** quick
**Status:** captured
