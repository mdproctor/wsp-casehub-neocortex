# Decisions — Cognitive S-Batch (#340, #342, #344)

## D1: Corroboration matching strategy for #340

**Choice:** Subject-based matching — corroborate by querying for experience memories with the same `Subject(type, id)` in the same tenant
**Alternatives:**
- Text similarity (embedding-based) — catches semantically related experiences about the same entity even with different Subject records, but adds embedding dependency and latency to consolidation
- Domain-only grouping — groups by MemoryDomain only, too coarse — would count unrelated observations about different entities as corroboration
**Rationale:** Subject is the typed entity reference that already exists on every Memory. Same Subject = same entity. Simple, exact, no new infrastructure. Text similarity deferred to follow-up #346.
**Trade-offs:** Misses corroboration across different Subject records that refer to the same real-world entity (e.g., Subject("person", "alice") vs Subject("colleague", "alice")). Acceptable because Subject normalization is a separate concern, and the 3+ threshold is conservative enough that false negatives (failing to graduate) are less harmful than false positives (premature promotion).
**Sources:** Issue #340, Memory.java, Subject.java, MemoryQuery.forSubject()
**Exploration:** quick
**Status:** captured

## D2: Scorer access pattern for corroboration (#340)

**Choice:** Widen GraduationScorer SPI to `score(Memory, GraduationContext)` — phase batch-queries per unique Subject, builds context, passes to scorer
**Alternatives:**
- CDI-injected scorer (no SPI change) — DefaultGraduationScorer gets CaseMemoryStore injected, queries inside score(). Hides dependency, per-memory queries (up to 20/tick), interface lies about what scorer needs.
- Gate in phase — ExperienceConsolidationPhase does corroboration check before calling scorer. Puts graduation logic in the wrong place; scorer is the decision point, not the phase.
**Rationale:** Pre-release, IntelliJ Change Signature makes refactor trivial. Context object is explicit (scorer contract says it needs context), batch-efficient (one query per unique Subject, not per memory), and extensible (#339 importance scores slot into GraduationContext without another refactor). Scorer stays pure computation — no I/O inside score().
**Trade-offs:** SPI change touches all GraduationScorer implementations (currently only DefaultGraduationScorer and its tests). Acceptable in pre-release.
**Sources:** GraduationScorer.java, DefaultGraduationScorer.java, ExperienceConsolidationPhase.java, MemoryQuery.forSubject()
**Exploration:** quick
**Status:** captured

## D3: Accumulator placement for significance trigger (#342)

**Choice:** New standalone `SignificanceAccumulator` @ApplicationScoped bean in mindmap-intelligence. Observes `ExperienceRecorded` CDI events, accumulates per-tenant significance, calls `consolidateNow()` when threshold crossed.
**Alternatives:**
- Extend ConsolidationScheduler directly — adds CDI observer + accumulation logic to an already 6-param constructor. Tangles timer and threshold concerns.
- Extend RetrievalAccessTracker — reuses swap-and-reset pattern but conflates node retrieval access tracking with experience significance tracking.
**Rationale:** Clean separation: scheduler owns the timer, accumulator owns the threshold trigger. Single responsibility. Extensible for #339 — swap event count for importance score without touching the scheduler.
**Trade-offs:** One more bean. Minimal — it's small and focused.
**Sources:** ConsolidationScheduler.java, RetrievalAccessTracker.java, ExperienceRecorded.java
**Exploration:** quick
**Status:** captured

## D4: Significance metric for accumulator (#342)

**Choice:** Event count with pluggable extractor — `@FunctionalInterface SignificanceExtractor` with `double extract(ExperienceRecorded)`. @DefaultBean returns 1.0 (pure count). Configurable threshold. When #339 lands, a new extractor returns the importance score.
**Alternatives:**
- Cumulative confidence — sum confidence values. More nuanced but still a proxy, and hardcodes the metric choice.
- Pure event count, no pluggability — YAGNI argument. But #339 is already filed and scoped; the pluggable interface costs one interface + one @DefaultBean.
**Rationale:** The extractor costs almost nothing (one @FunctionalInterface, one trivial @DefaultBean). It positions cleanly for #339 and avoids a refactor when importance scoring lands. The accumulator doesn't care what the number means — just whether the sum crossed a threshold.
**Trade-offs:** Marginal complexity of the pluggable interface. Justified by the known #339 dependency.
**Depends on:** D3 (accumulator placement)
**Sources:** Issue #342, Issue #339, ExperienceRecorded.java
**Exploration:** quick
**Status:** captured
