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

**Choice:** New standalone `SignificanceAccumulator` @ApplicationScoped bean in mindmap-intelligence. Observes `ExperienceRecorded` CDI events, accumulates per-tenant significance, triggers consolidation asynchronously when threshold crossed.
**Alternatives:**
- Extend ConsolidationScheduler directly — adds CDI observer + accumulation logic to an already 6-param constructor. Tangles timer and threshold concerns.
- Extend RetrievalAccessTracker — reuses swap-and-reset pattern but conflates node retrieval access tracking with experience significance tracking.
**Rationale:** Clean separation: scheduler owns the timer, accumulator owns the threshold trigger. Single responsibility. Extensible for #339 — swap event count for importance score without touching the scheduler.
**Trade-offs:** One more bean. Minimal — it's small and focused.
**Review refinements (R1-11, R1-12, R1-13):**
- `consolidateNow()` must be called asynchronously (submit to internal executor), not in the CDI observer thread — synchronous invocation blocks the experience recording path on full consolidation.
- Reset via swap-and-reset pattern (following RetrievalAccessTracker): reset counter at consolidation start, not at trigger time. Events during consolidation count toward the next cycle.
- If consolidation lock is held when significance triggers, the request is dropped (tryLock). This is acceptable — consolidation is idempotent and the timer will catch up.
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

## D5: Diversity integration point for CBR retrieval (#344)

**Choice:** New `DiversityCbrCaseMemoryStore` @Decorator @Priority(55) on CbrCaseMemoryStore following the `RerankingCbrCaseMemoryStore` pattern (CDI @Decorator + DelegatingCbrCaseMemoryStore base + @Inject @Delegate @Any). Config-gated (`casehub.cbr.diversity.enabled`).
**Alternatives:**
- Post-processing inside QdrantCbrCaseMemoryStore — couples diversity to Qdrant, doesn't apply to InMemoryCbrCaseMemoryStore.
- Standalone utility called by consumer — no automatic application, every consumer must remember to call it.
**Rationale:** Consistent with all other retrieval modifiers. Priority 55 places it after all scoring/reranking (Reranking @75, OutcomeWeighting @65, TrustWeighted @60) so MMR sees fully-scored results. Config-gated means zero overhead when disabled.
**Trade-offs:** Over-fetches by a configurable factor (default 1.5×, not 2×) to limit cross-encoder cost. At 1.5× with topK=10, cross-encoder reranks 15 instead of 10 candidates — 50% more work, not 100%.
**Review refinements (R1-18, R1-19, R1-20, R1-22):**
- Follows the RerankingCbrCaseMemoryStore wiring pattern specifically (CDI @Decorator, not manual delegation).
- Priority 55 chosen to run after TrustWeighted @60 — MMR uses fully-modulated scores, which is architecturally correct (prefer diverse results that are also trusted/proven).
- Over-fetch factor reduced from 2× to 1.5× to limit cross-encoder cost propagation.
- Intercepts `registerSchema()` to cache CbrFeatureSchema for pairwise similarity computation via CbrSimilarityScorer.
**Sources:** RerankingCbrCaseMemoryStore.java, DelegatingCbrCaseMemoryStore.java, QdrantCbrCaseMemoryStore.retrieveSimilar()
**Exploration:** quick
**Status:** captured

## D6: Pairwise similarity metric for diversity detection (#344)

**Choice:** Feature-based pairwise similarity via existing `CbrSimilarityScorer`. Reuses the established scoring infrastructure — handles categorical, numeric, temporal, and structured fields. No new infrastructure.
**Alternatives:**
- Embedding cosine similarity — captures semantic redundancy but requires EmbeddingModel at retrieval time (optional dependency). Adds latency for batch embedding.
- Jaccard on feature keys — very fast but extremely coarse. Two cases with identical keys but different values look identical.
**Rationale:** CbrSimilarityScorer already handles the full type system. Using it for pairwise comparison is consistent and semantically correct. No additional dependencies.
**Trade-offs:** O(K²) pairwise comparisons on the over-fetched set. For typical K (5-20), this is negligible.
**Depends on:** D5 (decorator placement)
**Sources:** CbrSimilarityScorer.java, ScoredCbrCase.featureSimilarities()
**Exploration:** quick
**Status:** captured

## D7: Diversity replacement strategy (#344)

**Choice:** MMR-style greedy selection (Maximal Marginal Relevance). Over-fetch topK*2, then greedily select K results maximizing λ*similarity_to_query - (1-λ)*max_similarity_to_selected. λ configurable (default 0.7 favors relevance).
**Alternatives:**
- Swap most redundant — find highest mutual similarity pair in top-K, replace lower-scored one with best diverse candidate from outside top-K. Simpler but ad-hoc.
- Cluster-then-pick — cluster over-fetched results, pick best per cluster. More principled but adds clustering complexity and cluster count tuning.
**Rationale:** MMR is the standard IR diversity technique. Well-understood, single-pass, O(K²) on the over-fetched set. λ parameter gives direct control over relevance-diversity trade-off. No tuning of cluster counts or similarity thresholds needed.
**Trade-offs:** λ requires calibration per use case. Default 0.7 is conservative (relevance-heavy). Users can tune lower for more diversity.
**Depends on:** D5 (decorator placement), D6 (similarity metric)
**Sources:** Issue #344, CBR-LLM survey (arXiv:2504.06943)
**Exploration:** quick
**Status:** captured
