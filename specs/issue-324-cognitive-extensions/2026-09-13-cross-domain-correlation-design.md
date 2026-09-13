# Cross-Domain Correlation for Mood and Experience Events

**Issue:** casehubio/neocortex#324
**Branch:** issue-324-cognitive-extensions
**Date:** 2026-09-13

## Summary

Extend `DomainActivation` to correlate agent mood and experience events against per-subgraph affect trajectories. Two new correlation types:

1. **Mood ↔ affect** — DTW on 3D PAD time series (mood is continuous, same as affect, just agent-scoped rather than entity-scoped). Context-attributed mood partitions data points by subgraph; legacy agent-global mood falls back to unpartitioned correlation.

2. **Experience → affect** — event-triggered affect windows measuring Δ(affect) before/after each experience event per PAD dimension. Per-type breakdown (Observation/Action/Outcome).

Statistical significance via permutation testing (DTW) and bootstrap CI (event windows).

## Scope

**In scope:**
- `MoodState` gains optional `activeContextIds` for domain partitioning
- `DomainActivationQuery` gains `withContextDomains(Set<MemoryDomain>)` and `withEventWindow(Duration)`
- `DomainActivationResult` gains `contextCorrelations` and `eventImpacts` maps
- `DomainCorrelation` gains `pValue` field
- `PadDtw` gains `WarpingConstraint` parameter (Sakoe-Chiba banding)
- New `EventTriggeredAnalyzer` static utility
- New `EventImpact` and `EventTypeImpact` value types
- Permutation significance testing for DTW correlations

**Out of scope:**
- Full domain-attributed mood (mood becoming entity-scoped like affect)
- ExperienceEvent schema changes
- Granger causality or other heavyweight statistical frameworks
- LLM-based sentiment extraction from experience descriptions

## Design

### 1. MoodState Capture Pipeline

`MoodState` record gains one optional field:

```java
public record MoodState(
    String agentId, String tenantId, Instant timestamp,
    double pleasure, double arousal, double dominance,
    String cause, String turnId,
    Set<String> activeContextIds,  // nullable — null/empty = agent-global
    Map<String, String> metadata
)
```

- `activeContextIds` is a set of opaque context identifiers (subgraph IDs, case IDs, etc.) representing the domains the agent was actively engaged with when the mood snapshot was taken.
- `null` or empty = agent-global (backward compatible). All existing callers pass `null`.
- The correlation layer interprets these as subgraph IDs. Mood data points only contribute to subgraphs whose ID is in the set.
- `MoodEvents.toMemoryInput()` stores context IDs as a comma-separated attribute via new `MoodAttributeKeys.ACTIVE_CONTEXT_IDS` when present, omits the attribute when absent.

**Rationale (D1):** Without context attribution, correlating one agent-global mood signal against N subgraph affect trajectories produces ecological inference — the mood correlates with all concurrently active subgraphs, giving spurious N-way correlation. Optional context attribution eliminates this confound while maintaining backward compatibility.

**MoodDecay behavior (R1-09):** `MoodDecay.decay()` preserves `activeContextIds` from the input `MoodState`. Decayed mood originated from context-specific mood — it remains context-specific, just temporally relaxed toward baseline.

**Mixed attribution during transition (R1-11):** During adoption, some mood entries will have `activeContextIds` (correctly partitioned) while legacy entries won't (agent-global fallback). `DomainCorrelation` for mood reports `contextAttributedCount` and `totalMoodCount` so consumers can assess data quality. When both types are present, the ecological inference risk affects only the fallback portion.

### 2. Query Extensions

`DomainActivationQuery` gains:

```java
public DomainActivationQuery withContextDomains(Set<MemoryDomain> domains)
public DomainActivationQuery withEventWindow(Duration window)
```

- `contextDomains` controls which context signals to correlate. Empty set = no context correlation (existing behavior, default). `Set.of(MoodEvents.DOMAIN)` = mood only. `Set.of(MoodEvents.DOMAIN, ExperienceEvents.DOMAIN)` = both.
- `eventWindow` sets the pre/post window for event-triggered affect analysis. Default: same as `bucketDuration` (24 hours). Controls how much affect data before and after each experience event is used to compute Δ(affect).

`contextDomains` replaces per-domain boolean flags. `MemoryDomain`-based extensibility means adding new correlation domains (relationship, reflection, engagement) requires no query signature changes.

**Subgraph constraint relaxation (R1-08):** The existing ≥2 subgraph requirement is relaxed when `contextDomains` is non-empty. Context correlation (mood↔affect, experience→affect) is meaningful for a single subgraph — "how does my mood correlate with affect in my work domain?" Validation: require ≥2 subgraphs only when `contextDomains` is empty (pairwise correlation is the only output). When `contextDomains` is non-empty, ≥1 subgraph suffices.

### 3. Result Extensions

`DomainActivationResult` gains two new fields:

```java
public record DomainActivationResult(
    Map<String, DomainSignal> domains,
    Map<DomainPair, DomainCorrelation> correlations,
    Map<MemoryDomain, Map<String, DomainCorrelation>> contextCorrelations,
    Map<MemoryDomain, Map<String, EventImpact>> eventImpacts,
    PrincipalId principal, String tenantId,
    Instant from, Instant to
)
```

- `contextCorrelations` — DTW-based correlations for continuous context signals. Keyed by `MemoryDomain` (e.g., `MoodEvents.DOMAIN`) → subgraph ID → `DomainCorrelation`. Used for mood ↔ affect.
- `eventImpacts` — event-triggered affect window results for discrete signals. Keyed by `MemoryDomain` (e.g., `ExperienceEvents.DOMAIN`) → subgraph ID → `EventImpact`. Used for experience → affect.
- When `contextDomains` is empty, both maps are empty (backward compatible).

`DomainCorrelation` gains a `pValue` field:

```java
public record DomainCorrelation(
    double dtwSimilarity,
    List<DtwAlignment> alignment,
    int samplePairs,
    CorrelationStrength strength,
    double pValue,
    int contextAttributedCount,   // mood entries with activeContextIds (0 for non-mood)
    int totalMoodCount            // total mood entries used (0 for non-mood)
)
```

- `pValue` from circular shift significance test. `Double.NaN` when not computed (existing subgraph-to-subgraph correlations, or when insufficient data).
- `contextAttributedCount`/`totalMoodCount` — attribution quality signal for mood correlations (R1-11). Both 0 for non-mood correlations.
- `CorrelationStrength.fromSimilarity(double s, double pValue)` new overload with significance guard: `STRONG`/`MODERATE` require p < 0.05, else downgraded to `WEAK`. Existing single-arg `fromSimilarity(double s)` is unchanged (backward compatible).

### 4. New Value Types

```java
public record ConfidenceInterval(double lower, double upper) {}

public record EventImpact(
    Map<PadDimension, Double> meanDelta,
    Map<PadDimension, ConfidenceInterval> confidenceInterval,  // 95% CI
    int eventCount,
    int totalEvents,
    Map<String, EventTypeImpact> byType
)

public record EventTypeImpact(
    Map<PadDimension, Double> meanDelta,
    Map<PadDimension, ConfidenceInterval> confidenceInterval,  // 95% CI
    int eventCount
)
```

- `ConfidenceInterval` — typed record replacing raw `double[]` for CI bounds (R1-10).
- `meanDelta` — mean Δ(affect) per PAD dimension across all events with sufficient surrounding data.
- `confidenceInterval` — bootstrap 95% CI per dimension (1000 resamples). Present on both aggregate and per-type (R1-07).
- `eventCount` — events with ≥1 affect data point in both pre and post windows.
- `totalEvents` — total experience events in the time range (including those without sufficient affect).
- `byType` — per event-type breakdown keyed by event type name ("observation", "action", "outcome").

### 5. Correlation Algorithms

#### 5a. Mood ↔ Affect (DTW with warping)

1. Query `CaseMemoryStore` for `domain="mood"` memories matching the agent (`Subject.of("agent", principal.id())`), filtered by `from`/`to` time window.
2. **Context partitioning:** For each subgraph, filter mood entries:
   - If mood entry has non-empty `activeContextIds` → include only if IDs intersect the subgraph ID.
   - If mood entry has null/empty `activeContextIds` → include (agent-global fallback).
3. Time-bucket the partitioned mood PAD into `double[][]` using `bucketDuration` and `from`/`to` (same logic as existing affect bucketing).
4. Run `PadDtw.compute(moodBuckets, affectBuckets, constraint)` — 3D PAD DTW with Sakoe-Chiba banding (default window: 10% of series length).
5. **Circular shift significance test (R1-02):** Generate 200 circular shift surrogates of the mood series — shift by a random offset in [1, bucketCount-1], wrapping around. This preserves the series' autocorrelation structure while destroying temporal alignment with affect. Recompute DTW for each surrogate, p-value = fraction of surrogate similarities ≥ observed. Random permutation (the naive approach) destroys autocorrelation, making the null distribution artificially easy to beat and inflating type I error. Use deterministic seed derived from query parameters for reproducibility.

#### 5b. Experience → Affect (event-triggered windows)

1. Query `CaseMemoryStore` for `domain="experience"` memories matching the agent, filtered by `from`/`to`.
2. **All experience events apply to every subgraph (R1-04).** Experience events are agent-global — they have no subgraph attribution. For each event, we measure affect change in every subgraph. This is intentional: the cross-domain effect is exactly what makes this analysis useful ("when this agent had an experience, how did affect change in each domain?"). A work experience affecting family affect is a meaningful finding, not a bug.
3. For each experience event at time T, and for each subgraph:
   - Collect affect memories for entities in that subgraph within `[T - eventWindow, T)` → compute mean PAD per dimension (pre).
   - Collect affect memories within `[T, T + eventWindow]` → compute mean PAD per dimension (post).
   - Δ = post - pre, per PAD dimension.
   - Skip events with < 1 affect data point in either window.
4. **Overlapping windows (R1-05):** When events occur more frequently than `eventWindow`, pre/post windows overlap — event A's post-window includes event B's effect. The measured Δ reflects the aggregate affect change within the window, not the isolated effect of a single event. This is acceptable and documented: with sufficiently sparse events the problem vanishes, and with dense events the aggregate signal is itself informative. Consumers can reduce `eventWindow` for higher temporal precision at the cost of requiring denser affect data.
5. Aggregate Δ values across events: compute mean and bootstrap 95% CI (1000 resamples with replacement).
6. Group by event type name for per-type `EventTypeImpact` with per-type CI (R1-07).

#### 5c. PadDtw Enhancement

New overload accepting `WarpingConstraint`:

```java
static DtwResult compute(double[][] query, double[][] candidate,
                         WarpingConstraint constraint)
```

All three `WarpingConstraint` variants are supported (R1-03 — sealed interface requires exhaustive handling):
- `Unconstrained`: no banding (equivalent to existing behavior).
- `SakoeChibaBand(windowSize)`: cells where `|i*m/n - j| > windowSize` are set to `Double.MAX_VALUE`.
- `ItakuraParallelogram(maxSlope)`: slope-bounded warping, ported from `DtwSimilarity.computeJStart/computeJEnd` (~15 lines).
- `null` constraint = unconstrained (existing behavior, backward compatible).

#### 5d. New Utility — EventTriggeredAnalyzer

```java
public final class EventTriggeredAnalyzer {
    public static EventImpact analyze(
        List<Memory> experienceMemories,
        List<Memory> affectMemories,
        Duration window)
}
```

Pure static utility, same pattern as `AffectTrajectoryAnalyzer` and `MindMapAnalyzer`. Stateless computation over store data.

- Experience memories provide event timestamps and types (extracted from `ExperienceAttributeKeys.EVENT_TYPE` attribute).
- Affect memories provide PAD values and timestamps.
- Both lists should be sorted chronologically.
- Window parameter controls pre/post affect collection.

### 6. DomainActivation.correlate() Changes

The `correlate()` method is extended, not replaced. After computing existing subgraph-to-subgraph affect correlations:

1. Check `query.contextDomains()`. If empty, set `contextCorrelations` and `eventImpacts` to empty maps and return.
2. For each domain in `contextDomains`:
   - If domain is a continuous PAD signal (mood): query memories, partition by context, time-bucket, DTW per subgraph, permutation test → add to `contextCorrelations`.
   - If domain is a discrete event signal (experience): query memories, run `EventTriggeredAnalyzer.analyze()` per subgraph → add to `eventImpacts`.
3. Domain classification (continuous vs discrete) is determined by the correlation layer, not by the domain type itself. Initially hardcoded: `MoodEvents.DOMAIN` → continuous, `ExperienceEvents.DOMAIN` → discrete. Extensible via a registry if more domains are added.

### 7. Testing Strategy

**EventTriggeredAnalyzer tests:**
- Correlated events at affect inflection points → non-zero Δ
- Events during flat affect → Δ near zero
- Sparse affect data → `eventCount` < `totalEvents`
- Empty inputs → empty `EventImpact`
- Per-type breakdown → correct `byType` partitioning
- Bootstrap CI bounds bracket mean Δ

**PadDtw warping constraint tests:**
- Sakoe-Chiba produces same result as unconstrained for well-aligned series
- Banding reduces similarity for large temporal offset
- Null constraint = unconstrained (backward compatible)

**Circular shift significance tests:**
- Correlated series → p < 0.05
- Random series → p ≥ 0.05, strength downgraded
- Deterministic seed → reproducible results
- Circular shift preserves autocorrelation (verify surrogate series has similar variance/mean as original)

**DomainActivation integration tests:**
- Context-attributed mood → correlation only with matching subgraph
- Agent-global mood → correlation with all subgraphs
- Mixed attribution → `contextAttributedCount` < `totalMoodCount` (R1-11)
- Experience events → `EventImpact` populated with per-type breakdown
- Single subgraph with contextDomains → valid result (R1-08)
- Empty `contextDomains` → empty maps (backward compatible)
- Graceful degradation — no mood/experience memories → empty maps

**MoodState tests:**
- `activeContextIds` null accepted
- Defensive copy
- `MoodEvents.toMemoryInput()` stores/omits context IDs attribute correctly
- `MoodDecay.decay()` preserves `activeContextIds` from input (R1-09)

## Modules Touched

| Module | Changes |
|--------|---------|
| `memory-api` | `MoodState` gains `activeContextIds`. `MoodAttributeKeys` gains `ACTIVE_CONTEXT_IDS`. `MoodEvents.toMemoryInput()` updated. |
| `cognitive-index` | `DomainActivation` extended. `DomainActivationQuery` gains `contextDomains`/`eventWindow`, ≥1 subgraph when contextDomains non-empty. `DomainActivationResult` gains `contextCorrelations`/`eventImpacts`. `DomainCorrelation` gains `pValue`/`contextAttributedCount`/`totalMoodCount`. `PadDtw` gains warping constraint overload (all 3 variants). New `EventTriggeredAnalyzer`, `EventImpact`, `EventTypeImpact`, `ConfidenceInterval`. `CorrelationStrength.fromSimilarity()` gains significance guard. |
| `mindmap` | No changes. |

## Trade-offs

- **D1:** `activeContextIds` on `MoodState` is a capture pipeline change. Adding the field to the record constructor breaks 39 existing call sites across neocortex (tests, examples) and blocks (MoodOrchestrator, DriveComposer) — all mechanical migration, passing `null`. New callers at the engine level need to populate it for domain-partitioned correlation to work. Without it, mood correlates agent-globally with all subgraphs.
- **DomainCorrelation:** Adding `pValue`, `contextAttributedCount`, and `totalMoodCount` fields breaks 2 existing constructor call sites in `DomainActivation.correlate()` — pass `Double.NaN` and `0, 0` for existing subgraph-to-subgraph correlations.
- **DomainActivationQuery (R1-06):** Adding `contextDomains` and `eventWindow` fields to the record breaks 2 direct constructor calls in tests and requires updating the `between()` factory (defaults: `contextDomains = Set.of()`, `eventWindow = null`). All existing `with*()` copy methods must forward the new fields.
- **D2:** Event-triggered windows require sufficient affect data around each event. If affect observations are sparse (e.g., > 24h gaps), many events will be skipped. Window size is configurable.
- **D3:** Two DTW implementations remain (`PadDtw` and `DtwSimilarity`). Intentional — same algorithm, incompatible type interfaces. ~60 lines of duplication avoids coupling cognitive-index to CBR types.
- **D7:** Per-dimension Δ(affect) produces three values per event instead of one. Consumers choose or combine dimensions.
- **D9:** Permutation testing runs DTW ~200 times per subgraph pair. Low-single-digit milliseconds at expected bucket counts (tens to low hundreds).

## References

- `DomainActivation.correlate()` — existing cross-subgraph correlation algorithm
- `PadDtw.compute()` — existing DTW implementation (~60 lines)
- `MoodState` record — current structure (memory-api)
- `MoodEvents.toMemoryInput()` — mood → MemoryInput converter
- `MoodDecay.decay()` — exponential mood decay toward baseline
- `ExperienceEvent` sealed hierarchy — Observation, Action, Outcome
- `ExperienceEvents.toMemoryInput()` — event converter
- `AffectTrajectoryAnalyzer.analyze()` — static utility pattern model
- `WarpingConstraint` sealed interface — Unconstrained, SakoeChibaBand, ItakuraParallelogram (memory-api)
- `PadDimension` enum — PLEASURE, AROUSAL, DOMINANCE (cognitive-index)
- `CorrelationStrength.fromSimilarity()` — threshold-based strength classification
- `DtwSimilarity.computeJStart/computeJEnd` — ItakuraParallelogram reference impl (memory-api)
- GE-20260824-829f7a — DTW alignment paths not exposed through retrieval API
- GE-20260824-9f3788 — standard DTW forces full endpoint alignment
- casehubio/neocortex#324 — parent issue
- casehubio/neocortex#283 — cross-domain reasoning parent
- decisions.md — D1-D9 with rationale
