# Decisions — #324 MoodEvents + ExperienceEvents Cross-Domain Correlation

## D1: Correlation model — context-attributed mood with agent-global fallback

**Choice:** Add optional `activeContextIds: Set<String>` to `MoodState`, populated at capture time with the IDs of subgraphs/domains the agent is actively engaged with. When present, DomainActivation partitions mood data points — only mood snapshots whose `activeContextIds` intersect the target subgraph contribute to that subgraph's mood correlation. When absent (legacy data), fall back to agent-global correlation.
**Alternatives:**
- Agent-global only (no context attribution) — avoids capture pipeline changes but produces spurious correlations via ecological inference: one agent-global signal correlated against N subgraph trajectories will show correlation with all concurrently active subgraphs
- Full domain-attributed mood — mood becomes entity-scoped like affect; heaviest pipeline change, unclear provenance of "which subgraph was the agent thinking about"
- Metadata-based attribution — store context IDs in MoodState's existing `metadata` map; avoids type change but loses type safety and makes the field invisible to callers
**Rationale:** The ecological inference problem (R1-02) is real: an agent-global mood signal correlated against multiple subgraph affect trajectories without controlling for domain engagement context produces confounded results. An optional typed field is the minimal change that addresses the core problem while maintaining backward compatibility for legacy data. `activeContextIds` is domain-agnostic (not coupled to cognitive-index's subgraph concept) — it's a set of opaque context identifiers that the correlation layer interprets. The engine knows which case/step is active; cases have subgraph associations; the capture site populates the field.
**Trade-offs:** Requires MoodState constructor change and call-site migration (mechanical). Legacy mood data without context IDs falls back to agent-global correlation (degraded but not broken).
**Sources:** DomainActivation.java (correlate method), MoodEvents.java (agent-scoped Subject), MoodState.java, issue #324 description ("cannot be attributed to a specific subgraph without capture pipeline changes")
**Exploration:** quick
**Status:** revised — R1-02 identified ecological inference problem with agent-global-only approach; added context attribution with fallback

## D2: Experience event projection — event-triggered affect windows

**Choice:** For each `ExperienceEvent` at time T in a subgraph, compute Δ(affect) = mean(affect[T, T+window]) − mean(affect[T−window, T]) per PAD dimension. This directly measures whether experiences shift subgraph affect, preserving event-type information (compute Δ separately for Outcome-success, Outcome-failure, Observation, Action).
**Alternatives:**
- Event density in time buckets with DTW — count events per bucket, normalize to [0,1], run DTW against affect time series. Issue #324 explicitly warns against this: "DTW operates on continuous time series; correlating discrete events requires different techniques." Also discards event valence/type and produces circularity (events often cause affect changes, so density-affect correlation rediscovers the causal pathway)
- Granger causality — test whether past event counts improve prediction of future affect values. Standard statistical framework for temporal precedence but heavier machinery, harder to interpret per-event
- Sentiment/valence extraction via LLM — derive pseudo-PAD from Outcome.result; richer signal but heavy dependency
**Rationale:** Issue #324 names "event co-occurrence analysis, Granger causality on event-triggered windows" as the appropriate techniques. Event-triggered windows directly answer the useful question: "do experiences shift subgraph affect?" They handle sparsity naturally (work with individual events, no minimum count needed), preserve event type/valence (Outcome.result, Observation.subject, Action.capability), and provide directional information (did affect improve or worsen after this event?). The density-based DTW approach converts discrete events to pseudo-continuous signals — exactly what the issue says not to do.
**Trade-offs:** Requires sufficient affect data around each event for meaningful Δ computation. Window size is a parameter that needs tuning. Cannot detect long-lag effects where experience-to-affect delay exceeds the window.
**Sources:** ExperienceEvent sealed hierarchy (Observation, Action, Outcome), Outcome.result, issue #324 description
**Exploration:** quick
**Status:** revised — R1-03 identified that density-based DTW contradicts issue #324's own analysis and discards event valence

## D3: Mood correlation technique — DTW on 3D PAD with warping constraints

**Choice:** Time-bucket mood PAD the same way as affect, run DTW via PadDtw with Sakoe-Chiba banding. PadDtw to be enhanced with configurable `WarpingConstraint` (reusing the sealed interface from memory-api) and early abandonment support.
**Alternatives:**
- Use `DtwSimilarity` from memory-api directly — already has warping constraints and early abandonment, but operates on `Map<String, FeatureValue>` with `FeatureField.TimeSeries` schema. The type interfaces are incompatible: `DtwSimilarity` requires CBR types (`FeatureValue`, `FeatureField`), while DomainActivation works with raw `double[][]` PAD arrays. Using `DtwSimilarity` would require wrapping PAD doubles in `FeatureValue.NumberVal` and creating a synthetic `FeatureField.TimeSeries` schema — coupling cognitive-index to CBR abstractions for no architectural benefit. This was explicitly evaluated in the social cognition spec (issue-287) and the contributor guide.
- Pearson/Spearman on aligned buckets — simpler linear correlation but misses temporal lag; DTW handles delay between mood change and affect response
**Rationale:** PadDtw as a lightweight `double[][]` DTW utility was an intentional design choice documented in the social cognition spec: "The core DTW algorithm (distance matrix computation + backtrace, ~40 lines) is independent of CBR types. `DtwSimilarity` in memory-api remains unchanged — the algorithms are identical but the type interfaces are incompatible (`FeatureValue`/`FeatureField` vs raw doubles), and coupling them would require either a dependency from memory-api to cognitive-api (wrong direction) or a new shared module (overkill for 40 lines of algorithm)." However, PadDtw needs enhancement: Sakoe-Chiba banding is standard practice for mood↔affect correlation with temporal lag. The `WarpingConstraint` sealed interface from memory-api is already in cognitive-index's dependency graph — PadDtw can accept it as a parameter without creating new types.
**Trade-offs:** Two DTW implementations remain (PadDtw and DtwSimilarity). This is intentional — same algorithm, incompatible type interfaces. ~60 lines of algorithm duplication is acceptable to avoid coupling cognitive-index to CBR-specific types.
**Sources:** PadDtw.java, DtwSimilarity.java, WarpingConstraint.java, social cognition spec §Change 7, contributor guide §PadDtw
**Exploration:** quick
**Status:** revised — R1-04 correctly identified need for warping constraints; PadDtw enhanced rather than replaced, per prior architectural decision

## D4: Result shape — extensible context correlation map

**Choice:** Add `Map<MemoryDomain, Map<String, DomainCorrelation>> contextCorrelations` to `DomainActivationResult`, keyed by context domain (e.g., `MoodEvents.DOMAIN`) then by subgraph ID. Existing `correlations` field (subgraph-to-subgraph) is unaffected.
**Alternatives:**
- Per-domain fields (`moodCorrelations`, `experienceCorrelations`) — one method per domain type; N-field growth pattern as new domains are added
- Separate ContextCorrelationResult — cleaner separation but two API calls for full picture
- Unified polymorphic keys — flexible but breaks existing consumers
**Rationale:** R1-05 correctly identified that per-domain fields produce N-field growth. The extensible map scales without touching the record signature when new domains (relationship, reflection, engagement) are added. The `MemoryDomain` key controls which queries execute — the set of requested domains in the query drives computation.
**Trade-offs:** Consumers index by `MemoryDomain` rather than named fields. Slightly less discoverable but more forward-compatible.
**Sources:** DomainActivationResult.java, MemoryDomain.java, DomainCorrelation.java
**Exploration:** quick
**Status:** revised — R1-05 identified N-field growth pattern; adopted extensible map keyed by MemoryDomain

## D5: Query opt-in — domain set with default empty

**Choice:** Add `withContextDomains(Set<MemoryDomain>)` to `DomainActivationQuery`, default empty set. `Set.of(MoodEvents.DOMAIN)` = mood correlation only. `Set.of(MoodEvents.DOMAIN, ExperienceEvents.DOMAIN)` = both. Empty set = no context correlation (existing behavior).
**Alternatives:**
- Per-domain boolean flags (`withMoodCorrelation(boolean)`, `withExperienceCorrelation(boolean)`) — one method per domain type; same N-field growth pattern as D4
- Always compute when available — simpler API but queries all domains even when not needed
**Rationale:** Follows from D4 revision. One method for any combination of domains. Avoids unnecessary CaseMemoryStore queries for domains not requested. The set of requested domains controls which queries execute.
**Trade-offs:** Callers must know `MemoryDomain` constants. Minor discoverability cost, offset by extensibility.
**Sources:** DomainActivationQuery.java, MoodEvents.DOMAIN, ExperienceEvents.DOMAIN
**Exploration:** quick
**Status:** revised — R1-05 combined with D4; adopted single extensible method

## D6: Experience event analysis — per-type event-triggered windows

**Choice:** Compute event-triggered affect windows per event type (Observation, Action, Outcome) and per outcome valence (Outcome.result). No aggregation into a single density series.
**Alternatives:**
- Single aggregated density — lose event-type distinction; cannot answer "do outcomes correlate differently than observations"
- Split density per type for DTW — too-sparse series for meaningful DTW (original D6 concern)
**Rationale:** With D2 revised to event-triggered affect windows, the original sparsity concern (R1-06) dissolves. Event-triggered windows work with individual events — no minimum density threshold for statistical reliability. Per-type analysis is natural: compute Δ(affect) for Outcome-success events separately from Outcome-failure events. This directly answers "do positive outcomes correlate with improving affect in subgraph X?" — the most useful question that was unanswerable with pure density.
**Trade-offs:** More granular output (per-type Δ statistics). Consumers choose their aggregation level.
**Sources:** ExperienceEvent sealed hierarchy (Observation, Action, Outcome), Outcome.result
**Exploration:** quick
**Status:** revised — R1-06 sparsity concern dissolves with D2 event-triggered window approach

## D7: Experience-to-affect dimensionality — per-PAD-dimension Δ(affect)

**Choice:** Compute Δ(affect) per PAD dimension (pleasure, arousal, dominance) around each experience event. Report per-dimension statistics in `DomainCorrelation` via `Map<PadDimension, Double> dimensionDeltas` or equivalent. No magnitude reduction.
**Alternatives:**
- PAD magnitude reduction `sqrt(p²+a²+d²)/sqrt(3)` — conflates positive and negative affect; high pleasure and high displeasure both produce high magnitude; "stuff is happening" correlates with "stuff is happening"
- Pleasure-only reduction — more informative than magnitude but discards arousal and dominance dimensions
**Rationale:** R1-07 correctly identified that magnitude conflation destroys the most informative signal. The example of alternating positive/negative affect producing high magnitude throughout is compelling — it would show "strong correlation" with any concurrent activity. Per-dimension Δ(affect) is strictly more informative: pleasure captures valence direction, arousal captures activation, dominance captures agency. The `PadDimension` enum already exists in the codebase (`io.casehub.neocortex.cognitive.index.PadDimension`). Consumers pick the dimension relevant to their question.
**Trade-offs:** Three values per event instead of one. Consumers must choose or combine dimensions. More informative, marginally more complex to consume.
**Sources:** PadDimension.java, DomainCorrelation.java
**Exploration:** quick
**Status:** revised — R1-07 identified magnitude conflation destroys directional signal; adopted per-dimension approach

## D8: Causal model — context-attributed correlation with directional affect measurement

**Choice:** The correlation design explicitly addresses causal inference through two mechanisms: (1) D1's context attribution partitions mood by active engagement context, controlling for the confound that agent-global mood co-varies with all concurrent subgraphs; (2) D2's event-triggered affect windows measure directional affect change (Δ pre/post event), establishing temporal precedence rather than bare co-occurrence.
**Alternatives:**
- Bare temporal co-occurrence via DTW — the original implicit approach. DTW similarity between agent-global signals and entity-scoped affect is nearly meaningless without controlling for domain engagement context (R1-09).
- Full Granger causality framework — standard for temporal precedence questions but requires minimum time series length and stationarity assumptions that may not hold for sparse affect data
**Rationale:** R1-09 surfaced this as an implicit decision. Temporal co-occurrence alone (DTW similarity between two time series) cannot distinguish meaningful correlation from coincidental co-activity. The revised design addresses this at two levels: D1's context attribution eliminates the confound (mood only correlates with subgraphs the agent was actively engaged with), and D2's event-triggered windows provide directional measurement (not just "do they co-occur" but "does affect change after this event").
**Trade-offs:** Context attribution requires capture pipeline changes (D1). Event-triggered windows require sufficient affect data around events.
**Sources:** DomainActivation.java, issue #324 description, R1-09
**Exploration:** new — surfaced by reviewer
**Status:** captured

## D9: Statistical significance — permutation testing for DTW, bootstrap CI for event-triggered windows

**Choice:** Add statistical significance assessment to all correlation outputs. For mood-affect DTW: permutation test — shuffle one series N times (N=200), recompute DTW each time, compare observed similarity to the null distribution. Report p-value in `DomainCorrelation`. For event-triggered affect windows: bootstrap confidence interval on Δ(affect) values — resample with replacement, compute mean Δ at each resample, report 95% CI bounds. `CorrelationStrength.fromSimilarity()` gains a significance guard: `STRONG`/`MODERATE` require p < 0.05, else downgrade to `WEAK`.
**Alternatives:**
- No significance testing — consumers have no way to distinguish meaningful from spurious correlations. With small bucket counts (tens to low hundreds), DTW correlations can appear strong by chance.
- Parametric tests — assume normality of affect distributions; may not hold for PAD data with high autocorrelation
**Rationale:** R1-11 correctly identified that DTW similarity scores without significance assessment produce false confidence. `CorrelationStrength.STRONG` (>= 0.7) could be assigned to random co-occurrence with small samples. Permutation tests are distribution-free and computationally trivial at these scales (200 permutations × ~100×100 DTW matrix = ~2M operations, sub-millisecond). Bootstrap CI for event-triggered windows is equally cheap and provides interpretable confidence bounds on the measured effect.
**Trade-offs:** Adds computational cost (permutation test runs DTW ~200 times). Negligible at the expected bucket counts (tens to low hundreds). Adds `pValue` field to `DomainCorrelation`.
**Sources:** CorrelationStrength.java, DomainCorrelation.java
**Exploration:** new — surfaced by reviewer
**Status:** captured
