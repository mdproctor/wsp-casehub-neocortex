# Decisions — #324 MoodEvents + ExperienceEvents Cross-Domain Correlation

## D1: Correlation model — context signals, not domain-attributed

**Choice:** Mood and experience remain agent-global context signals correlated against per-subgraph affect trajectories. No capture pipeline changes.
**Alternatives:**
- Mood/experience attributed to subgraphs — requires tagging with active subgraph context at capture time; heavier pipeline changes, unclear provenance of "which subgraph was the agent thinking about"
- Both (layered) — start with context signals, extend with attribution later; adds design complexity for uncertain future need
**Rationale:** The question DomainActivation answers becomes "does agent mood/experience correlate with affect changes in specific subgraphs?" rather than "how does mood in domain A correlate with mood in domain B?" This is the more useful question — it links agent-global state to domain-specific dynamics without requiring changes to MoodState or ExperienceEvent capture.
**Trade-offs:** Cannot answer "does work mood differ from family mood" — mood stays agent-global. If domain-attributed mood is needed later, it's a separate issue with capture pipeline work.
**Sources:** DomainActivation.java (correlate method), MoodEvents.java (agent-scoped Subject), issue #324 description
**Exploration:** quick
**Status:** captured

## D2: Experience event projection — event density in time buckets

**Choice:** Count experience events per time bucket, normalize to [0,1] rate. Produces a 1D time series aligned with affect buckets.
**Alternatives:**
- Event-triggered windows — measure affect change before/after each event; answers "do experiences shift affect?" rather than "do they co-occur?"; more expensive, different question
- Sentiment/valence extraction — derive pseudo-PAD from Outcome.result via LLM/NLI; richer signal but heavy machinery dependency
**Rationale:** Simple, robust, directly DTW-compatible. Event density captures temporal co-occurrence: "do more experiences happen when affect is changing in subgraph X?" Avoids NLI/LLM dependencies.
**Trade-offs:** Loses semantic content of events (observation vs action vs outcome, positive vs negative). Purely temporal correlation — cannot distinguish "good experiences correlate with improving affect" from "any experiences correlate."
**Sources:** ExperienceEvents.java, ExperienceEvent sealed hierarchy, PadDtw.java
**Exploration:** quick
**Status:** captured

## D3: Mood correlation technique — DTW on PAD

**Choice:** Time-bucket mood PAD the same way as affect, run DTW via PadDtw.
**Alternatives:**
- Pearson/Spearman on aligned buckets — simpler linear correlation but misses temporal lag; DTW handles delay between mood change and affect response
**Rationale:** Mood is already a continuous 3D PAD signal — the only difference from affect is agent-global rather than entity-scoped. Reusing PadDtw avoids new correlation machinery. DTW's flexibility handles the case where mood reacts to affect (or vice versa) with a time lag.
**Trade-offs:** DTW is O(n*m), but bucket counts are small (days/weeks at 24h buckets = tens to low hundreds). Not a concern.
**Sources:** PadDtw.java, MoodState.java (PAD fields), MoodEvents.java (DOMAIN = "mood")
**Exploration:** quick
**Status:** captured

## D4: Result shape — extend DomainActivationResult

**Choice:** Add `Map<String, DomainCorrelation> moodCorrelations` and `Map<String, DomainCorrelation> experienceCorrelations` to DomainActivationResult, keyed by subgraph ID.
**Alternatives:**
- Separate ContextCorrelationResult — cleaner separation but two API calls for full picture; consumer must assemble
- Unified correlation map with typed keys — polymorphic keys replacing DomainPair; flexible but breaks existing consumers
**Rationale:** One query, one result, one call site. Consumers get everything. Existing `correlations` field (subgraph-to-subgraph) is unaffected. New fields are simply absent (empty maps) when not opted in.
**Trade-offs:** DomainActivationResult grows. If more signal types are added later, the record accumulates fields. Acceptable for a small number of known signal types.
**Sources:** DomainActivationResult.java, DomainCorrelation.java
**Exploration:** quick
**Status:** captured

## D5: Query opt-in — flags with default false

**Choice:** Add `withMoodCorrelation(boolean)` and `withExperienceCorrelation(boolean)` to DomainActivationQuery, default false.
**Alternatives:**
- Always compute when available — simpler API but every correlate() call queries 3 domains instead of 1, even when mood/experience data isn't needed
- Separate method (correlateWithContext) — clear separation but two methods doing similar work with near-identical setup
**Rationale:** Existing callers unchanged. New callers opt in explicitly. Avoids unnecessary CaseMemoryStore queries for mood/experience domains.
**Trade-offs:** More query builder methods. Minor API surface growth.
**Sources:** DomainActivationQuery.java (existing with* pattern)
**Exploration:** quick
**Status:** captured

## D6: Experience event aggregation — single density, not per-type

**Choice:** Aggregate all experience event types (observation/action/outcome) into a single density series.
**Alternatives:**
- Split by event type immediately — three separate density series per subgraph; richer but 3x correlations and sparse data risk
**Rationale:** With small event counts, splitting by type produces too-sparse series for meaningful DTW. Aggregated density still captures temporal co-occurrence. Per-type breakdown can be added when event volumes justify it.
**Trade-offs:** Loses event-type distinction. Cannot answer "do outcomes correlate differently than observations."
**Sources:** ExperienceEvent sealed hierarchy (Observation, Action, Outcome)
**Exploration:** quick
**Status:** captured

## D7: Experience-to-affect dimensionality — PAD magnitude reduction

**Choice:** Reduce subgraph affect to 1D via PAD magnitude (sqrt(p²+a²+d²)/sqrt(3), normalized to [0,1]). Normalize experience density to [0,1]. Run PadDtw on two 1D series.
**Alternatives:**
- Per-dimension correlation — correlate experience density against each PAD dimension separately (3 correlations per subgraph); richer but noisier, consumer must interpret three values
**Rationale:** Single correlation per subgraph, same DomainCorrelation type. PadDtw already handles 1D (euclidean degenerates to absolute difference). PAD magnitude captures overall emotional activation regardless of valence direction.
**Trade-offs:** Magnitude conflates positive and negative affect — high pleasure and high displeasure both produce high magnitude. If directional correlation matters (e.g., experiences correlate with improving but not worsening affect), this won't distinguish.
**Sources:** PadDtw.java (dimension-agnostic euclidean), CorrelationStrength.java (threshold-based)
**Exploration:** quick
**Status:** captured
