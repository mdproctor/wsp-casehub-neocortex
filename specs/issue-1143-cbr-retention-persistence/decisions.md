## D1: CBR case scope

**Choice:** Per-tenant. Each tenant's retention config cases are stored and retrieved in tenant isolation. No cross-tenant retrieval or fallback.
**Alternatives:**
- Global — simpler, one case population across all tenants, but tenant workloads differ significantly
- Per-tenant with global fallback — query tenant first, fall back to global for cold start, but violates tenant data isolation which is a legal boundary (tenants are different organisations)
**Rationale:** Tenants represent different organisations with different memory workload characteristics. Legal data isolation requirements prohibit cross-tenant data sharing. The CBR store naturally enforces tenant isolation via tenantId on all operations. Cross-tenant metadata aggregation for platform-level analytics is a separate future concern outside the adaptation phase.
**Trade-offs:** Cold start — a new tenant gets DEFAULT until its own adaptation stabilises. Acceptable because the step-based adaptation converges within a few cycles regardless.
**Sources:** HygieneAdaptationPhase.run() (cognition), CbrRecordStore.store() tenantId parameter (memory-api), issue #1143 discussion
**Exploration:** quick
**Status:** captured

## D2: Store timing — stability-gated

**Choice:** Store a CBR case only when the threshold has been stable (HELD — pressure in target range) for N consecutive ticks (default 3). The stable config is proven to work under the current workload.
**Alternatives:**
- On every HygieneAdaptationEvent — more data points but includes intermediate steps that haven't proven themselves; pollutes the case base with configs that were immediately adjusted
- On direction reversal — captures inflection points but misses configs that stabilise without oscillation
**Rationale:** A config that has been held for multiple ticks has demonstrated it keeps eviction pressure in the target range under sustained load. This is the strongest evidence of a good config. Intermediate adjustments are search steps, not solutions.
**Trade-offs:** Slower case accumulation — requires 3+ stable ticks before the first case is stored. Acceptable because the config converges gradually and restart recovery is the rare case.
**Sources:** HygieneAdaptationPhase.run() hold logic (line 99), RetentionConfig (cognition-api)
**Exploration:** quick
**Status:** captured

## D3: Case features

**Choice:** Three numeric features: evictionPressure [0,1], totalScored [0,∞), consolidationGroups [0,∞). These characterise the memory workload context where the threshold worked well.
**Alternatives:**
- Pressure only — minimal but loses volume context; a threshold optimal for 100 memories may not suit 10,000
- Pressure + volume + agent count — agent count likely correlates with totalScored and adds marginal discriminative value
**Rationale:** evictionPressure captures the quality signal the adaptation responds to. totalScored and consolidationGroups capture workload scale — a threshold that works for a small memory store may not work for a large one. These three fields are already available from KnowledgeGapSummary with no additional computation.
**Trade-offs:** No personality or agent-level features. RetentionConfig weights are personality-driven (D3 in #1119 design), so the threshold is the only parameter that varies by workload. Acceptable for v1.
**Sources:** KnowledgeGapSummary (memory-api), HygieneAdaptationPhase.run() pressure computation
**Exploration:** quick
**Status:** captured

## D4: Startup retrieval location

**Choice:** In HygieneAdaptationPhase, on first tick per tenant (where it currently stores baseline and returns). Before returning, query CBR for the best prior config. If a match exists above minSimilarity, seed AdaptiveRetentionConfig with it.
**Alternatives:**
- In AdaptiveRetentionConfig @PostConstruct — doesn't know tenantId at construction time; tenants are discovered later during consolidation ticks
- New CbrRetentionInitializer bean — adds another bean for a simple query; the phase already has all required dependencies
**Rationale:** The first-tick baseline path in HygieneAdaptationPhase is the natural point where tenant context first becomes available. The phase already holds references to both CbrRecordStore (via Instance<>) and AdaptiveRetentionConfig. Adding the retrieval query to this path keeps the change localised.
**Trade-offs:** First tick does more work (CBR query + potential config update). Acceptable — this is a one-time operation per tenant per restart, not per-tick overhead.
**Depends on:** D1 (per-tenant scope determines query isolation)
**Sources:** HygieneAdaptationPhase.run() first-tick path (line 64-67), AdaptiveRetentionConfig (cognition)
**Exploration:** quick
**Status:** captured

## D5: Supersession strategy

**Choice:** When a new stable config is stored, supersede the previous active case for that tenant. One active case per tenant at any time.
**Alternatives:**
- Accumulate all stable configs — builds a richer case base over time, but most are intermediate states that have been superseded by later adaptation
- Keep top-N by confidence — more complex retention logic for marginal benefit when the system converges to one optimal threshold
**Rationale:** The adaptation is a convergent process — each stable config is meant to be better than the last. Keeping only the latest proven config avoids retrieving stale configurations that were optimal under different conditions. CbrRecordStore.supersede() already provides this capability with audit trail (SupersessionStatus).
**Trade-offs:** Loses historical configs. If the workload changes dramatically, the single surviving case may be a poor match. The adaptation will converge again from whatever config is retrieved. Acceptable.
**Sources:** CbrRecordLifecycle.supersede() (memory-api), SupersessionStatus (memory-api)
**Exploration:** quick
**Status:** captured

## D6: Module placement

**Choice:** All changes in the cognition module. HygieneAdaptationPhase gains CBR dependencies via Instance<CbrRecordStore> (graceful degradation when CBR not on classpath). No new types in cognition-api.
**Alternatives:**
- New module — over-engineering for this scope
- Changes in cognition-api — CBR dependency doesn't belong in the API module
**Rationale:** Follows existing pattern: BehavioralSynthesisPhase (mindmap-intelligence) already uses Instance<CbrRecordStore> for optional CBR integration. The phase is the only consumer; no SPI boundary needed.
**Trade-offs:** cognition module gains a soft dependency on memory-api's CBR types. Already present — CbrRecordStore is used by MemoryHygieneOrchestratorImpl in the same module.
**Sources:** BehavioralSynthesisPhase Instance<CbrRecordStore> pattern (mindmap-intelligence), MemoryHygieneOrchestratorImpl (cognition)
**Exploration:** quick
**Status:** captured
