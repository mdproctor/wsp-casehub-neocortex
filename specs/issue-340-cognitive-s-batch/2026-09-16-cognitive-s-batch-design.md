# Cognitive S-Batch Design — #340, #342, #344

Three small, independent enhancements to the cognitive subsystem's consolidation and retrieval pipelines. Each is self-contained with no cross-dependencies between the three issues.

---

## 1. Corroboration-Gated Graduation (#340)

### Problem

`ExperienceConsolidationPhase` graduates individual experience memories to semantic nodes (beliefs, intentions, judgments) based on a single memory's confidence score. A single observation about a person can become a permanent belief — premature generalization that destroys the episodic signal.

### Design

**Widen the GraduationScorer SPI** to accept a `GraduationContext` record alongside the `Memory`:

```java
// memory-api
public record GraduationContext(int corroboratingCount, String tenantId) {}

// memory-api — change signature
@FunctionalInterface
public interface GraduationScorer {
    double score(Memory memory, GraduationContext context);
}
```

**`DefaultGraduationScorer`** returns 0.0 when `context.corroboratingCount() < minCorroboration` (configurable, default 3). Otherwise returns the existing confidence-based score. The threshold is an empirical starting point — 3 distinguishes coincidence from pattern while remaining achievable. Configurable via `ExperienceConsolidationConfig`.

**`ExperienceConsolidationPhase`** builds `GraduationContext` via batch queries:

1. Scan up to `maxPerPass` experience memories (existing cursor-based scan)
2. Extract unique `Subject` instances from the batch
3. For each unique Subject, query `CaseMemoryStore` for corroborating experience memories:
   - `MemoryQuery.forSubject(subject, ExperienceEvents.DOMAIN, tenantId)` — scoped to experience domain only (relationship/reflection memories are derived, not primary observations)
   - Use `withOrder(REVERSE_CHRONOLOGICAL).withLimit(minCorroboration)` — we only need to know whether the count meets the threshold, not all corroborating memories
4. Build `GraduationContext(count, tenantId)` per Subject, cache in a `Map<Subject, GraduationContext>`
5. Iterate memories, pass the pre-built context to `scorer.score(memory, context)`

**Architectural note:** Corroboration runs at consolidation time (batch, periodic), not at ingestion time. This enables retroactive corroboration — when a 3rd converging experience arrives, earlier experiences that didn't meet the threshold can graduate on the next consolidation pass. The trade-off is a latency window (up to `intervalMinutes`) between corroboration becoming sufficient and graduation occurring.

### Files Changed

| File | Change |
|------|--------|
| `memory-api/.../GraduationScorer.java` | Change signature to `score(Memory, GraduationContext)` |
| `memory-api/.../GraduationContext.java` | New record: `(int corroboratingCount, String tenantId)` |
| `mindmap-intelligence/.../DefaultGraduationScorer.java` | Add corroboration gate: return 0.0 when count < threshold |
| `mindmap-intelligence/.../ExperienceConsolidationPhase.java` | Batch-query per Subject, build context, pass to scorer |
| `mindmap-intelligence/.../ExperienceConsolidationConfig.java` | Add `minCorroboration` config (default 3) |

### Testing

- Unit test: `DefaultGraduationScorer` returns 0.0 when corroborating count < 3, returns confidence when >= 3
- Unit test: `ExperienceConsolidationPhase` does not graduate single-observation memories, does graduate when 3+ observations exist for the same Subject
- Unit test: Retroactive corroboration — memory that previously didn't graduate now graduates when corroborating count reaches threshold
- Unit test: Different Subjects are not corroborating (Subject("person", "alice") does not corroborate Subject("person", "bob"))

---

## 2. Importance-Threshold Reflection Trigger (#342)

### Problem

`ConsolidationScheduler` runs on a fixed 5-minute timer, gated only by `idleTracker.isIdle(1 min)`. After a burst of important observations, consolidation doesn't run until the next timer tick. The scheduler has no awareness of how much has happened since the last cycle.

### Dependency

Issue #339 (importance scoring at ingestion, scale M) is still open. This design uses event count as a proxy metric, with a pluggable extractor that #339 can replace with real importance scores.

### Design

**New `SignificanceAccumulator`** @ApplicationScoped bean in `mindmap-intelligence/consolidation/`:

```java
@ApplicationScoped
public class SignificanceAccumulator {
    private volatile ConcurrentHashMap<String, DoubleAdder> perTenant = new ConcurrentHashMap<>();
    private final ConsolidationScheduler scheduler;
    private final SignificanceExtractor extractor;
    private final double threshold;
    private final ExecutorService triggerExecutor;

    void onExperienceRecorded(@Observes ExperienceRecorded event) {
        double significance = extractor.extract(event);
        String tenantId = event.event().tenantId();
        DoubleAdder adder = perTenant.computeIfAbsent(tenantId, k -> new DoubleAdder());
        adder.add(significance);
        if (adder.sum() >= threshold) {
            triggerExecutor.submit(() -> scheduler.consolidateNow(tenantId));
        }
    }

    public SignificanceSnapshot swapAndReset() {
        var old = perTenant;
        perTenant = new ConcurrentHashMap<>();
        var snapshot = new HashMap<String, Double>();
        old.forEach((k, v) -> snapshot.put(k, v.sum()));
        return new SignificanceSnapshot(Map.copyOf(snapshot));
    }
}
```

Key design points:
- **Async trigger:** `consolidateNow()` is submitted to a single-thread daemon executor, not called in the CDI observer thread. This prevents the experience recording path from blocking on full consolidation.
- **Swap-and-reset:** `swapAndReset()` is called by the consolidation scheduler at tick start (same pattern as `RetrievalAccessTracker` / `AccessFrequencyPhase.beginTick()`). Events during consolidation count toward the next cycle.
- **Lock contention:** If `consolidateNow()` finds the lock held (timer-triggered consolidation already running), it drops silently. Consolidation is idempotent — the timer catches up. No queuing needed.

**`SignificanceExtractor`** @FunctionalInterface:

```java
@FunctionalInterface
public interface SignificanceExtractor {
    double extract(ExperienceRecorded event);
}
```

**`DefaultSignificanceExtractor`** @DefaultBean returns 1.0 (pure event count). When #339 lands, a new `@Alternative` extractor reads importance from `event.event().metadata().get("importance")`.

**Threshold** configurable via `casehub.consolidation.significance-threshold` (default 10.0 — equivalent to 10 events with the default extractor).

**Integration with `ConsolidationScheduler`:** Add `SignificanceAccumulator` as an optional dependency (via `Instance<SignificanceAccumulator>`). At the start of each `tick()`, call `accumulator.swapAndReset()` to reset the counter. The accumulator doesn't need to know about the timer — it resets when consolidation runs, regardless of trigger source.

### Files Changed

| File | Change |
|------|--------|
| `mindmap-intelligence/.../SignificanceAccumulator.java` | New: CDI observer, per-tenant accumulator, async trigger |
| `mindmap-intelligence/.../SignificanceExtractor.java` | New: @FunctionalInterface SPI |
| `mindmap-intelligence/.../DefaultSignificanceExtractor.java` | New: @DefaultBean returning 1.0 |
| `mindmap-intelligence/.../SignificanceSnapshot.java` | New: swap-and-reset result record |
| `mindmap-intelligence/.../ConsolidationScheduler.java` | Add optional `Instance<SignificanceAccumulator>`, call `swapAndReset()` at tick start |

### Testing

- Unit test: Accumulator increments per-tenant count on ExperienceRecorded
- Unit test: Threshold triggers consolidateNow() when reached
- Unit test: swapAndReset() clears counters and returns snapshot
- Unit test: Events during consolidation count toward next cycle (not lost)
- Unit test: Custom SignificanceExtractor producing importance > 1.0 triggers earlier
- Integration: Timer tick resets accumulator (no double-triggering)

---

## 3. CBR Retrieval Diversity Injection (#344)

### Problem

`CbrCaseMemoryStore.retrieveSimilar()` returns cases ranked purely by similarity score. When top-K cases cluster tightly — high individual similarity but low diversity — the retrieved set provides redundant information. Research (CBR-LLM survey, Hatalis et al. 2025) found that random sampling sometimes outperforms pure similarity ranking when top-K is too homogeneous.

### Design

**New `DiversityCbrCaseMemoryStore`** @Decorator @Priority(55) on CbrCaseMemoryStore:

```java
@Decorator
@Priority(55)
public class DiversityCbrCaseMemoryStore extends DelegatingCbrCaseMemoryStore {

    @Inject
    DiversityCbrCaseMemoryStore(@Delegate @Any CbrCaseMemoryStore delegate,
                                 DiversityConfig config) {
        super(delegate);
        this.lambda = config.lambda();        // default 0.7
        this.overFetchFactor = config.overFetchFactor(); // default 1.5
        this.enabled = config.enabled();      // default false
    }
}
```

**Priority 55** places it after all scoring decorators:

| Priority | Decorator |
|----------|-----------|
| 90 | TrendEnrichment |
| 85 | ScopeDecay |
| 75 | Reranking (cross-encoder) |
| 65 | OutcomeWeighting |
| 60 | TrustWeighted |
| **55** | **Diversity (new)** |
| 50 | Tracking |
| 45 | ErasureNotification / SupersessionNotification |

Running after all scoring means MMR operates on fully-modulated scores (relevance + trust + outcome confidence). This is correct — prefer diverse results that are also trusted and proven.

**Over-fetch factor** is 1.5× (not 2×) to limit cross-encoder cost propagation. With topK=10, the cross-encoder reranks 15 candidates instead of 10 — 50% more work, not 100%.

**MMR algorithm:**

1. Request `ceil(topK * overFetchFactor)` results from the delegate
2. If results <= topK, return as-is (no diversity needed)
3. Initialize selected set with the highest-scored result
4. Greedily select remaining K-1 results maximizing:
   `λ * score(case) - (1-λ) * max_pairwise_similarity(case, selected_set)`
5. `score(case)` is the `ScoredCbrCase.score()` from upstream decorators (normalized to [0,1])
6. Pairwise similarity uses `CbrSimilarityScorer` with uniform weights (1.0 for all fields) — not the query weights, since this measures inter-case similarity, not query relevance
7. Return the selected set, re-sorted by score descending

**Schema access:** The decorator intercepts `registerSchema()` to cache `CbrFeatureSchema` per case type. This cache is required for `CbrSimilarityScorer` to compute pairwise similarity. If no schema is cached for a case type, diversity is skipped (pass-through) with a warning log.

**Config:**

```properties
casehub.cbr.diversity.enabled=false          # opt-in
casehub.cbr.diversity.lambda=0.7             # relevance-diversity balance
casehub.cbr.diversity.over-fetch-factor=1.5  # candidates = topK * factor
```

### Files Changed

| File | Change |
|------|--------|
| `memory/.../DiversityCbrCaseMemoryStore.java` | New: @Decorator @Priority(55), MMR selection |
| `memory/.../DiversityConfig.java` | New: @ConfigMapping for diversity config |
| `memory/.../MmrSelector.java` | New: Pure-Java MMR algorithm (static utility, testable in isolation) |

### Testing

- Unit test: MmrSelector selects diverse results from a clustered set
- Unit test: MmrSelector with λ=1.0 produces identical ordering to pure score ranking (degenerate case)
- Unit test: MmrSelector with λ=0.0 maximizes diversity (selects most different cases)
- Unit test: Decorator passes through when disabled
- Unit test: Decorator passes through when results <= topK
- Unit test: Decorator passes through when no schema cached (with warning log)
- Unit test: Schema caching via registerSchema() interception
- Contract test: Decorator preserves ScoredCbrCase.caseId() and caseType() fields

---

## Architectural Notes

### Consolidation-Time vs Ingestion-Time Corroboration (R1-28)

Corroboration is checked at consolidation time (batch, periodic), not at memory ingestion. This enables retroactive corroboration — when a 3rd converging experience arrives, earlier experiences that didn't meet the threshold can graduate on the next pass. The trade-off is a latency window between corroboration becoming sufficient and graduation occurring. For the cognitive subsystem's typical use case (agent memory consolidation), this latency is acceptable — beliefs forming within minutes is fast enough.

### GraduationContext Scope (R1-30)

`GraduationContext` is a narrow, explicit record — not an extensible property bag. When #339 adds importance scoring, the field is added to the record directly. This keeps scorer dependencies visible in the type signature. A broad context hides what scorers actually depend on.

### Timer/Significance Double-Triggering (R1-29)

When `SignificanceAccumulator` triggers `consolidateNow()` and the timer subsequently fires `tick()`, the same tenant may be consolidated twice in rapid succession. This is wasteful but harmless — consolidation is idempotent (cursor-based scan prevents re-processing, dedup via `existingSourceIds`).

---

## References

- Issue #340 — corroboration-gated graduation
- Issue #342 — importance-threshold reflection trigger
- Issue #344 — CBR retrieval diversity injection
- Issue #339 — importance scoring at ingestion (dependency for #342 extractor upgrade)
- Issue #346 — text similarity corroboration (follow-up for #340)
- `memory-api/.../GraduationScorer.java` — current SPI
- `mindmap-intelligence/.../DefaultGraduationScorer.java` — current default (confidence passthrough)
- `mindmap-intelligence/.../ExperienceConsolidationPhase.java` — graduation pipeline
- `mindmap-intelligence/.../ConsolidationScheduler.java` — timer-based scheduler
- `mindmap-intelligence/.../RetrievalAccessTracker.java` — swap-and-reset pattern reference
- `memory/.../RerankingCbrCaseMemoryStore.java` — decorator pattern reference
- `memory-api/.../CbrSimilarityScorer.java` — pairwise similarity scoring
- CBR-LLM survey (arXiv:2504.06943) — diversity in case retrieval
- Generative Agents (Park et al.) — importance-triggered reflection
- Episodic Memory is the Missing Piece (arXiv:2502.06975) — Tulving's binding principle
