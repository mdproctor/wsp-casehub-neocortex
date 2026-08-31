## D1: Module placement for unified Confidence type

**Choice:** New `cognitive-api` module — tier-0 pure Java, zero dependencies
**Alternatives:**
- In mindmap-api — lightweight but couples mindmap concepts into memory's dependency tree
- In memory-api — forces mindmap-api to gain heavier dependencies, breaking its zero-dep constraint
- `confidence-api` — too narrow; would need immediate renaming when TemporalMark (#234) or MemorySpace (#230) land
- `cognitive-primitives` — vague; doesn't follow the established `*-api` naming convention (memory-api, mindmap-api, fusion-api, rag-api)
**Rationale:** `cognitive-api` starts lean (2 types: `Confidence`, `ConfidenceOrigin`) but has a clear growth path — `TemporalMark` (#234), `MemorySpace`/`Visibility` (#230), `Affect` (#238) all need the same cross-cutting home. Justified investment, not speculative infrastructure. Module name describes architectural role (cross-cutting cognitive type layer), not a specific concept — naming audit (#232) pins concept terminology, not module structure.
**Trade-offs:** Adds a module to the build. Every future type placement decision must consider cognitive-api vs module-specific.
**Sources:** cognitive-architecture-roadmap.md §1a, cognitive-coherence-audit.md §Dimension 1, mindmap-api/pom.xml (zero deps), memory-api/pom.xml (fusion-api + platform-api deps)
**Exploration:** quick
**Status:** revised — removed NodeRef (#243) from growth path (R1-03: NodeRef is mindmap-only, 31 references all in mindmap-* modules; listing it as cross-cutting was incorrect)

## D2: Decay reference placement — internal to Confidence

**Choice:** `Confidence(ConfidenceOrigin origin, double value, Instant decayReference)` — decay reference is a field on the record
**Alternatives:**
- External only — Confidence carries just origin+value; each store picks its own timestamp for decay (confirmedAt, updatedAt, storedAt). Simpler record but perpetuates entity-specific dispatch in the decorator.
- Both with fallback — internal with external override. Migration-friendly but adds precedence rules.
- DecayAnchor interface on entities — entities implement `DecayAnchor { Instant decayReference(); }` and decorator reads the interface. Clean separation but breaks when Confidence is passed without its owning entity (cross-store queries, serialized records, API responses — decay cannot be computed from Confidence alone).
**Rationale:** "When was this confidence level last established?" is a property of the confidence itself, not the entity. Eliminates the awkward asymmetry where MindMapNode uses `confirmedAt` and MindMapEdge uses `updatedAt` for the same conceptual purpose. Makes `ConfidenceDecayDecorator` generic — it reads `confidence().decayReference()` regardless of entity type. Null decayReference explicitly means "this confidence does not decay" (e.g., Memory) — cleaner than entity-type checking. Critically, Confidence records are passed across subsystem boundaries (cross-store queries in Phase 4, serialized snapshots, API responses) — the decay anchor must travel WITH the value to remain computable.
**Factory method semantics:** `stated()`, `inferred()`, `speculated()` require non-null decayReference — if you know HOW something was established, you should know WHEN. This is an origin-semantics constraint, not a MindMap-specific one: an epistemically grounded confidence (known provenance) always has a temporal anchor. Error messages must be domain-neutral ("decayReference required"), not MindMap-specific. `unknown()` creates with null decayReference because UNKNOWN is provenance-less — there's no meaningful decay anchor. The raw constructor remains available for edge cases where a caller has a non-UNKNOWN origin but genuinely no temporal anchor.
**Trade-offs:** MindMapNode's `confirmedAt` becomes redundant — resolved by D6 (remove confirmedAt). Backends must persist decayReference alongside origin+value.
**Depends on:** D1 (module placement)
**Sources:** ConfidenceDecayDecorator.java (mindmap/runtime), MindMapNode.java:27 confirmedAt, MindMapEdge.java:22 updatedAt
**Exploration:** quick
**Status:** revised — factory method null check documented as origin-semantics (not MindMap-specific), error messages domain-neutralized (R1-09)

## D3: ConfidenceOrigin scope — keep 3 values + UNKNOWN, non-nullable

**Choice:** ConfidenceOrigin gains `UNKNOWN` enum value for "provenance not tracked." Non-nullable on the Confidence record. Moved to cognitive-api WITHOUT `initialConfidence()` — default confidence values are extraction policy, not type semantics.
**Alternatives:**
- Nullable origin (original decision) — null means "source unknown." Introduces null-handling obligations at every consumer; breaks exhaustive switch coverage; current codebase has zero null origins.
- Expand now — add OBSERVED, COMPUTED, REFLECTED for Memory/CBR contexts. Richer but couples #229 scope to #232 naming audit.
- Replace with String — maximum flexibility but loses type safety.
**Rationale:** `UNKNOWN` fills the provenance gap without expanding the origin taxonomy. Every consumer gets exhaustive switch coverage. UNKNOWN is the ABSENCE of provenance information, not a new provenance category — orthogonal to domain-specific origins (#232 may add). `initialConfidence()` removed from the enum: the values (STATED=1.0, INFERRED=0.7, SPECULATED=0.3) are MindMap extraction defaults, not cognitive axioms. A stated fact CAN have any confidence level. The defaults move to the MindMap store layer where they're actually used (InMemoryMindMapStore.addNode, SqliteMindMapStore.addNode — 4 call sites total).
**Trade-offs:** `UNKNOWN` adds a fourth enum value all switch expressions must handle. MindMap stores need a local defaulting utility for initialConfidence.
**Depends on:** D1 (module placement)
**Sources:** cognitive-architecture-roadmap.md §Terminology ("importance becomes value with origin=null"), ConfidenceOrigin.java, InMemoryMindMapStore.java:95, SqliteMindMapStore.java:238
**Exploration:** quick
**Status:** revised — UNKNOWN replaces nullable origin (R1-08); initialConfidence() stays in mindmap layer, not cognitive-api (R1-09)

## D4: API surface — single Confidence accessor replaces split fields

**Choice:** MindMapNode/MindMapEdge: `confidenceOrigin()` + `confidence()` → single `Confidence confidence()`. NodeInput/EdgeInput: separate fields → single `Confidence confidence`. MemoryInput/Memory: `Double importance` → `Confidence confidence` (nullable — null means "no confidence assessment"). CbrCase: `Double confidence()` → `Confidence confidence()`. CbrCase.withOutcome: `withOutcome(String outcome, Double confidence)` → `withOutcome(String outcome, Confidence confidence)` — cascades to TextualCbrCase, PlanCbrCase, FeatureVectorCbrCase. NodeUpdate: `ConfidenceOrigin confidenceOrigin, Double confidence, Instant confirmedAt` → single nullable `Confidence confidence` (null means "don't change"; non-null replaces entire confidence including decayReference). MindMapQuery: keeps separate `Double minConfidence` and `ConfidenceOrigin confidenceOrigin` as query predicates — these are independent filters, not a value composition. ParsedEntity: `ConfidenceOrigin confidence` renamed to `ConfidenceOrigin origin` for clarity (ParsedEntity carries origin only, not a full Confidence record — the confidence value is derived at store time).
**Alternatives:**
- Keep split fields + add Confidence — backwards compatible but duplicates the concept, confuses which to use.
- Adapter layer — old methods delegate to Confidence internally. Avoids breaking callers but adds indirection that never gets cleaned up.
**Rationale:** Pre-release platform — breaking changes cost nothing. One concept = one method. All callers update to `node.confidence().value()` which is more explicit about what they're reading. Eliminates the possibility of confidenceOrigin and confidence being inconsistent.
**Trade-offs:** Every caller of `node.confidence()` (expecting double) must update. CbrCase.withOutcome signature change cascades to all 3 implementations. 155 ConfidenceOrigin references + all confidence() call sites.
**Depends on:** D2 (record shape)
**Sources:** MindMapNode.java, MindMapEdge.java, NodeUpdate.java, MindMapQuery.java, MemoryInput.java, Memory.java, CbrCase.java, TextualCbrCase.java, PlanCbrCase.java, FeatureVectorCbrCase.java, ParsedEntity.java
**Exploration:** quick
**Status:** revised — NodeUpdate, MindMapQuery, ParsedEntity, CbrCase.withOutcome explicitly addressed (R1-11, R1-12)

## D5: EMA confidence smoothing — instance method on Confidence

**Choice:** `Confidence.adjust(double observedRate, double learningRate, Instant newDecayReference)` — instance method on the Confidence record. Returns a new Confidence with the same origin, EMA-smoothed value (`(1 - learningRate) * this.value + learningRate * observedRate`), and the given decayReference. CbrOutcome.adjustConfidence is removed — callers use `confidence.adjust(successRate, lr, outcome.observedAt())` directly. CbrOutcome itself stays in memory-api unchanged (it carries CBR-specific fields: result, successRate, detail).
**Alternatives:**
- Static method on CbrOutcome (original D5) — couples general-purpose EMA math to a CBR-specific type. Future consumers (engagement scoring, reflection consolidation, trajectory analysis) would need a CbrOutcome dependency to access a math function that takes and returns Confidence.
- Standalone utility class — adds a class for a single method with no clear home.
- Keep Double-based adjustConfidence — callers wrap/unwrap Confidence manually. Error-prone.
**Rationale:** The EMA formula is general-purpose numerical smoothing — it takes a Confidence and returns a Confidence, a pure transformation on the type itself. Placing the method on the type it transforms is not speculative; it follows the principle of methods-on-their-types (like `withValue()` and `withDecayReference()` already on Confidence). The roadmap shows engagement scoring, reflection levels, and trajectory analysis as future EMA consumers — all would naturally call `confidence.adjust()` without any CBR dependency. The "trigger context" (CBR outcome, engagement event, reflection) is irrelevant to the transformation itself; the trigger selects the observedRate and learningRate to pass.
**Trade-offs:** Confidence gains one method. CbrOutcome stores that called adjustConfidence update to `old.adjust(successRate, lr, outcome.observedAt())` — a mechanical migration.
**Depends on:** D1 (module placement), D4 (API surface)
**Sources:** CbrOutcome.java:30-34 adjustConfidence, InMemoryCbrCaseMemoryStore.java:198, JpaCbrCaseMemoryStore.java:228, QdrantCbrCaseMemoryStore.java:671, cognitive-architecture-roadmap.md §3c (engagement, reflection as future confidence consumers)
**Exploration:** quick
**Status:** revised — EMA adjustment moves from CbrOutcome static method to Confidence.adjust() instance method (R1-02, supersedes R1-14)

## D6: confirmedAt resolution — remove from MindMapNode

**Choice:** Remove `confirmedAt` from `MindMapNode`. Node confirmation = updating `Confidence` with `decayReference=Instant.now()`. Value and origin are preserved unless the caller explicitly provides new values. NodeUpdate's `confirmedAt` field is subsumed by the new `Confidence confidence` field — callers construct a Confidence with updated decayReference.
**Semantic change from current behavior:** The current store contract implicitly resets confidence to 1.0 when `confirmedAt` is set without an explicit confidence value (`InMemoryMindMapStore.java:124-131`, `SqliteMindMapStore.java:300-303`, enforced by contract test `updateNode_confirmedAtWithoutConfidence_resetsTo1`). Under D6, confirmation resets only the decay anchor — value is preserved. A SPECULATED node at 0.3 that is "confirmed" stays at 0.3 with a fresh decay clock, rather than silently jumping to 1.0. To reset value to 1.0, the caller must explicitly construct `new Confidence(origin, 1.0, Instant.now())`. This is a deliberate improvement: the current implicit reset erases the epistemic distinction between SPECULATED and STATED knowledge. Confirming means "I've re-verified this is still believed" — it does NOT mean "I've upgraded my certainty to maximum." The contract test `updateNode_confirmedAtWithoutConfidence_resetsTo1` will be removed; a new test will verify that confirmation preserves value while resetting decayReference.
**Alternatives:**
- Keep confirmedAt, derive decayReference from it — contradicts D2's design (decayReference is on the Confidence record, not derived from entity fields). Two sources of truth.
- Keep both, enforce equality — redundant fields with an invariant to maintain. Store implementations must keep them in sync.
- Keep confirmedAt as audit-only — adds a field that no consumer reads for audit purposes (verified: only ConfidenceDecayDecorator.java:78 and MindMapAnalyzer.java:163 read confirmedAt, both for decay/staleness).
- Preserve the implicit 1.0 reset on confirmation — caller passes `Confidence confidence` without value, store defaults to 1.0. Rejects because Confidence is a record with non-null fields (D2: `double value`, not `Double`); there is no "without value" state. The caller is always explicit.
**Rationale:** `confirmedAt` was always the decay anchor for nodes. After unification, `confidence().decayReference()` serves this role. The two runtime consumers (ConfidenceDecayDecorator, MindMapAnalyzer.staleNodes) read `confirmedAt` purely for decay computation — both migrate to `confidence().decayReference()`. No consumer reads confirmedAt for audit/human-readable purposes. `updatedAt` already captures "when was this entity last modified" for audit needs.
**Trade-offs:** Callers that set `NodeUpdate.confirmedAt` must construct a Confidence record instead. The implicit 1.0 reset is lost — callers that intend a value reset must be explicit. Breaking change — but pre-release platform, and the breakage forces callers to be explicit about what "confirmation" means in their context.
**Depends on:** D2 (decayReference on Confidence), D4 (NodeUpdate surface change)
**Sources:** MindMapNode.java:26, ConfidenceDecayDecorator.java:78, MindMapAnalyzer.java:163, MindMapStoreContractTest.java:222, InMemoryMindMapStore.java:124-131 (implicit 1.0 reset), SqliteMindMapStore.java:300-303 (same)
**Exploration:** surfaced by review (R1-06, R2-02)
**Status:** revised — confirmation semantics explicitly documented as deliberate change from implicit 1.0 reset (R2-02)

## D7: Memory importance → Confidence.value mapping

**Choice:** Memory's `Double importance` maps to `Confidence.value` with `origin=UNKNOWN`. This is a deliberate semantic collapse — importance (attentional salience) and confidence (epistemic certainty) are conceptually distinct but unified under a single [0,1] scalar.
**Alternatives:**
- Keep importance separate from confidence — Memory carries both `Confidence confidence` AND `Double importance`. Preserves the semantic distinction but means the "unified confidence" is not actually unified — Memory has two numeric dimensions where other subsystems have one.
- Multi-dimensional Confidence — `Confidence(origin, certainty, salience, decayReference)`. Captures both dimensions but designs a multi-axis model without evidence of what axes are actually needed. Premature decomposition.
- Rename importance to confidence with no acknowledgment — silent conflation without explicit design rationale.
**Rationale:** The current `confidence` field on Memory has no clear semantics — it's used as a retrieval weight in `PersonalityWeightedRetrieval` and `MoodModulatedRetrieval`, where it modulates ranking. It's not a well-defined measure of either salience or certainty. Unifying under a single scalar: (1) enables cross-store comparison and ranking, (2) eliminates an ambiguous field, (3) is the prerequisite for later decomposition if real usage reveals distinct dimensions. The roadmap's terminology table explicitly retires `confidence` in favor of `origin`. If Phase 3+ work reveals that salience and certainty must be separate (e.g., "high-importance but low-confidence" patterns emerge in real agent behavior), the Confidence record can be extended then — with evidence of what decomposition is actually needed.
**Depends on:** D1 (module placement), D4 (API surface)
**Sources:** cognitive-architecture-roadmap.md §Terminology ("importance becomes value with origin=null"), Memory.java:14 (importance field), MemoryInput.java:13 (importance field), PersonalityWeightedRetrieval usage, MoodModulatedRetrieval usage
**Exploration:** surfaced by review (R1-17)
**Status:** captured

## D8: TemporalMark placement — cognitive-api

**Choice:** `TemporalMark` sealed interface goes in `cognitive-api` alongside `Confidence` and `ConfidenceOrigin`.
**Alternatives:**
- New `temporal-api` module — clean separation but adds a build artifact for a single sealed interface. cognitive-api would need to depend on it or vice versa.
- `mindmap-api` — temporal bounds already live there, but couples a cross-cutting concept to the mindmap subsystem. Memory and CBR would gain a mindmap dependency.
**Rationale:** cognitive-api is the zero-deps cross-cutting cognitive types module. TemporalMark is a cognitive concept on par with Confidence — it represents how the system understands time across all subsystems. D1 explicitly anticipated this placement.
**Trade-offs:** cognitive-api grows from 2 to 4 types (TemporalMark + 3 inner records). Still lean.
**Depends on:** D1 (module placement established cognitive-api as the cross-cutting home)
**Sources:** cognitive-architecture-roadmap.md §2a, cognitive-api/src/main/java/io/casehub/neocortex/cognitive/
**Exploration:** quick
**Status:** captured

## D9: Ordinal resolution — carry pre-resolved Instant

**Choice:** `Ordinal(String turnId, Instant resolved)` — the wall-clock timestamp is resolved at construction time and carried within the record. `resolveToInstant()` returns the pre-resolved value. No separate `sequence` field — no event type currently provides one, and sub-turn ordering can be encoded in the turnId if needed.
**Alternatives:**
- External resolver function — `resolveToInstant(Function<String, Instant> turnResolver)`. More flexible but every call site needs a resolver, and cognitive-api can't reference store types.
- Fallback to now — `resolveToInstant(Instant now)` always returns `now` for ordinals. Simplest but loses temporal precision entirely.
**Rationale:** A zero-deps type can't perform lookups. Carrying the resolved timestamp makes the mark self-contained — once constructed, it can be sorted, compared, and persisted without external dependencies. The resolver is the caller's responsibility at construction time, not at usage time. The turnId is retained alongside the resolved Instant for audit/traceability: it links the temporal mark back to its conversational origin ("this timestamp came from turn X"). This enables debugging (why is this event at this time?), provenance tracking, and potential re-resolution if timestamps are corrected. The resolved Instant is sufficient for sorting and comparison; the turnId serves the orthogonal concern of provenance.
**Trade-offs:** Resolution must happen at construction. If the turn-timestamp mapping changes later, the mark becomes stale. Acceptable — timestamps of past turns don't change. Ordinal carries turnId even after resolution — this is intentional for audit, not dead weight.
**Sources:** cognitive-architecture-roadmap.md §2a (resolveToInstant design), ExperienceEvent.java (turnId field), memory-api event types
**Exploration:** quick
**Status:** revised — documented turnId audit/traceability purpose (R1-13)

## D10: Relative anchor nullability — nullable

**Choice:** `Relative(Duration offset, @Nullable Instant anchor)`. When anchor is null, `resolveToInstant(Instant now)` returns `now + offset`. When non-null, returns `anchor + offset`.
**Alternatives:**
- Required anchor — caller must pin to a concrete Instant at construction. Simpler but loses the distinction between "3 days from now" (floating, re-resolves each call) and "3 days after the meeting" (pinned).
**Rationale:** LLM-extracted temporal references naturally produce both kinds: "next week" (relative to now, floating) and "3 days after the project started" (relative to a known anchor). The nullable anchor preserves this distinction for downstream consumers.
**Trade-offs:** Floating relative marks produce different values on each `resolveToInstant()` call. Consumers that persist the resolved value should call once and store the result.
**Sources:** cognitive-architecture-roadmap.md §2a, MindMapExtractor temporal parsing use case
**Exploration:** quick
**Status:** captured

## D11: Scope — type definition only, no adoption

**Choice:** #234 defines `TemporalMark` in cognitive-api with factory methods and `resolveToInstant()`. Adoption on existing types is scoped to follow-up issues: #235 (event timestamps), #236 (temporal MindMapQuery).
**Alternatives:**
- Type + MindMapExtractor integration — also integrate into temporal parsing. Bigger scope, crosses into mindmap.
- Type + all event timestamps — combine with #235. Scope creep, M → L.
**Rationale:** The type is independently valuable and testable. Follow-up issues are already defined in the queue. Keeping this S-sized means it can land quickly.
**Trade-offs:** TemporalMark exists but nothing uses it until #235/#236. Brief period of unused code.
**Sources:** .plan queue (#235, #236 follow immediately), issue #234 scope
**Exploration:** quick
**Status:** captured

## D12: Multi-tenant parameters — no MemorySpace dependency

**Choice:** `TemporalIndex.query()` takes `Collection<String> tenantIds`. No dependency on MemorySpace types (#230). Follow-up issue #254 wires the visibility layer when #230 lands.
**Alternatives:**
- Design space-aware now with placeholder types — invents types #230 will define authoritatively. Speculative infrastructure.
- Single tenantId only — forces callers to query once per space and merge results themselves. Defeats the purpose of a cross-store aggregator.
**Rationale:** MemorySpace maps spaces to tenants ("each space IS a tenant"). The only thing TemporalIndex needs from MemorySpace is a list of tenantIds to query across. A `Collection<String>` captures that without a type dependency. #254 filed as the wiring follow-up.
**Trade-offs:** TemporalIndex is space-agnostic until #254 lands. Callers must resolve spaces to tenantIds themselves in the interim.
**Sources:** cognitive-architecture-roadmap.md §1f, §2d (memory space impact), issue #230 (scope), issue #254 (follow-up)
**Exploration:** quick
**Status:** captured

## D13: Pure chronological aggregator — no salience scoring in the index

**Choice:** TemporalIndex returns `List<TemporalEntry>` sorted by timestamp. No salience scoring, no ranking policy. Ranking is a separate composable concern (D14). TemporalQuery carries a `Collection<MemoryDomain> memoryDomains` field specifying which memory domains to include when querying the Memory store. Defaults to `{experience}` — the highest-signal domain for temporal content. Callers that need affect trajectories, mood snapshots, or engagement events pass the relevant domains explicitly.
**Alternatives:**
- Ranker inside the index — `index.query(timeRange, tenantIds, ranker)`. Two responsibilities: aggregation AND ranking. Couples scoring policy to data access.
- Salience as the primary sort — TemporalIndex produces a ranked "attention list." But salience depends on context (agent's current task, affect state) that the index shouldn't know about.
- Query all memory domains by default — returns every mood snapshot, PAD change, and engagement tick. High noise-to-signal for the primary "what happened?" use case.
- Hardcoded domain filter (original implementation) — silently excludes 5 domains with no caller override. Undocumented restriction.
**Rationale:** The index answers "what happened in this time window?" — a data aggregation question. "What's important right now?" is a policy question for TemporalFocus (#244). Keeping them separate means the index is testable without scoring policy and the ranker is testable without store dependencies. The `memoryDomains` filter follows the same pattern as `sources` (StoreKind filter) — configurable with a sensible default. TemporalFocus (#244) will pass `{experience, affect}` to include affect trajectories for anticipatory processing.
**Trade-offs:** Callers that want ranked results must compose index + ranker at the call site (two lines, not one). Callers that need non-experience domains must specify them explicitly.
**Depends on:** D14 (composable ranking)
**Sources:** cognitive-architecture-roadmap.md §2d, §4b (TemporalFocus), ExperienceEvents.DOMAIN, AffectEvents.DOMAIN, MoodEvents.DOMAIN, RelationshipEvents.DOMAIN, ReflectionEvents.DOMAIN, EngagementEvents.DOMAIN
**Exploration:** quick
**Status:** revised — added configurable memoryDomains filter to TemporalQuery, replacing hardcoded EXPERIENCE_DOMAIN (R1-04)

## D14: Composable ranking via standalone TemporalRanker

**Choice:** `TemporalRanker` is a standalone `@FunctionalInterface` in cognitive-index: `double score(TemporalEntry entry, Instant now)`. Composes with TemporalIndex output at the call site. Default implementation: recency-based (newer = higher). TemporalFocus (#244) becomes a TemporalRanker implementation, not a separate utility wrapping the index.
**Alternatives:**
- Ranker as index parameter — couples ranking to query execution (violates D13).
- No ranker abstraction — TemporalFocus as a wrapper class. Works but duplicates the aggregation call; new ranking strategies require new wrapper classes.
**Rationale:** Runtime composable without coupling. The index produces data, the ranker re-orders it. They're orthogonal types connected by `List<TemporalEntry>`. TemporalFocus (#244) shrinks from "aggregation + ranking utility" to "a TemporalRanker implementation" — S-sized instead of M.
**Trade-offs:** Ranker can't influence what the index fetches (e.g., can't skip CBR results if only MindMap events are salient). Acceptable — the index already supports selective store querying via configuration.
**Sources:** cognitive-architecture-roadmap.md §4b (TemporalFocus), FusionStrategy pattern in fusion-api, OutcomeWeightingFunction pattern in memory-api
**Exploration:** quick
**Status:** captured

## D15: Sealed TemporalSource on TemporalEntry — zero information loss

**Choice:** `TemporalEntry` carries a `TemporalSource` sealed interface with variants: `FromMindMap(MindMapNode node)`, `FromMemory(Memory memory)`, `FromCbr(ScoredCbrCase<?> cbrCase)`. Callers pattern-match to access the original object.
**Alternatives:**
- Normalized common shape — flatten to `(id, text, source, timestamp, confidence)`. Lossy — callers needing node-specific fields (validUntil, traits, PAD) require a second query.
- Opaque Object payload — maximum flexibility, zero type safety. Defeats sealed exhaustiveness.
**Rationale:** The index aggregates heterogeneous results. Pattern matching gives callers type-safe access to the full original object. Sealed interface ensures exhaustive switch coverage — adding a new store variant is a compile error at every consumer. Zero information loss means no second query needed.
**Trade-offs:** TemporalEntry carries the full store object (MindMapNode, Memory, ScoredCbrCase). Memory footprint is higher than a normalized shape. Acceptable — these are query results already in memory.
**Sources:** MindMapNode.java (validFrom, validUntil, traits, PAD), Memory.java (createdAt, confidence), ScoredCbrCase (caseId, score)
**Exploration:** quick
**Status:** captured

## D16: Module placement — new cognitive-index module

**Choice:** New `cognitive-index` module. Depends on cognitive-api + mindmap-api + memory-api. Houses TemporalIndex (CDI bean), TemporalEntry, TemporalSource, TemporalRanker. Clear growth path for CognitiveProfile (#243) and TemporalFocus (#244).
**Alternatives:**
- cognitive-api + separate module — types in cognitive-api (zero-dep), bean in new module. Splits the concept across two modules. cognitive-api's growth path (D1) anticipated cross-cutting types, not cross-store query utilities.
- Existing mindmap module — couples a cross-store concern to a single store's CDI wiring. MindMap is the primary temporal source but not the only one.
**Rationale:** `cognitive-index` names the architectural role: cross-store cognitive queries. It's the natural home for all Phase 4 utilities (CognitiveProfile, TemporalFocus) that span MindMap + Memory + CBR. cognitive-api stays zero-deps for value types; cognitive-index is the query/service tier above it.
**Trade-offs:** Adds a module to the build. But the alternative is scattering cross-store concerns across individual store modules.
**Depends on:** D1 (cognitive-api established as cross-cutting type home)
**Sources:** cognitive-architecture-roadmap.md §4a (CognitiveProfile), §4b (TemporalFocus), module structure in CLAUDE.md
**Exploration:** quick
**Status:** captured

## D17: CDI bean with Instance<T> for graceful degradation

**Choice:** `TemporalIndex` is `@ApplicationScoped`. Injects stores via `Instance<MindMapStore>`, `Instance<CaseMemoryStore>`, `Instance<CbrCaseMemoryStore>`. Checks `isResolvable()` at query time. Missing stores are silently skipped — the index returns entries from whatever stores are available.
**Alternatives:**
- Optional constructor params (nullable) — similar effect but requires explicit null-checking. Less idiomatic in Quarkus/CDI.
- Require all stores — hard dependency. Forces apps to include all store modules even when they only use one subsystem. Breaks the modular classpath design.
**Rationale:** An app using only MindMap should get temporal indexing for MindMap nodes without pulling in memory-sqlite or memory-qdrant. `Instance<T>.isResolvable()` is the standard Quarkus pattern for optional dependencies — used throughout the codebase (e.g., `MultiModalEmbedderProducer`, `SeparateModelEmbedder`).
**Trade-offs:** Runtime discovery means a missing store is a silent no-op, not a compile error. Acceptable — TemporalIndex is enrichment, not critical path.
**Sources:** MultiModalEmbedderProducer.java (Instance pattern), SeparateModelEmbedder.java (optional SparseEmbedder), CbrReconciliationService.java (optional EmbeddingModel)
**Exploration:** quick
**Status:** captured

## D18: Stateless query aggregator — not a materialized index

**Choice:** TemporalIndex is a stateless query aggregator. It re-queries the underlying stores on every call and merges results. No persistence, no materialized data structure, no update mechanism. Same architectural category as `MindMapAnalyzer` and `RetrievalAnalyzer`. All public classes carry javadoc explaining this intent.
**Alternatives:**
- Materialized SPI (interface + inmem + SQLite backends) — maintains a persistent sorted timeline, updated via CDI events or polling. Higher query efficiency (O(log n) lookup) but introduces dual-write consistency burden, requires store mutation events that don't exist today, and adds SPI + 2 backends for something that could be 50 lines of orchestration.
- Cached aggregator — stateless with a TTL cache. Middle ground but premature optimisation — the underlying stores already have temporal indexes.
**Rationale:** The underlying stores already persist the data and have temporal indexes (#236). Each store query is O(log n) on an indexed column. Worst case per call: 3 tenants × 3 stores = 9 indexed queries — negligible for a tick-loop consumer. A materialized index would create a second source of truth with consistency obligations (the `CbrReconciliationService` problem) for zero practical gain. If performance becomes a concern: (1) add TTL cache to CDI bean (minutes of work), (2) add CDI event listeners + in-memory sorted set (hours), (3) materialize only if query frequency reaches thousands/second (unlikely).
**Trade-offs:** Every call re-queries stores. No pre-computed result. Acceptable — 9 indexed queries take microseconds-to-milliseconds. The tick loop runs at most every few seconds.
**Sources:** MindMapAnalyzer.java (same pattern — pure computation over store data), RetrievalAnalyzer.java (same pattern), CbrReconciliationService.java (cautionary — dual-write complexity), cognitive-coherence-audit.md §Temporal (CuriositySignalGenerator tick loop)
**Exploration:** deep-analysis
**Status:** captured

## D19: Event trait classification — property-driven, two-axis

**Choice:** Event traits use two orthogonal properties: `eventKind` (scheduled / anticipated) and `eventValence` (positive / negative / aspirational). TraitRules match on these explicit properties, not on PAD inference.
- Appointable: `event-kind=scheduled` (valence irrelevant — a funeral is appointable)
- Aspirational: `event-kind=anticipated` + `event-valence=aspirational`
- Threatening: `event-kind=anticipated` + `event-valence=negative`
- Opportunistic: `event-kind=anticipated` + `event-valence=positive`
**Alternatives:**
- PAD-derived — infer valence from PAD values (Threatening = negative pleasure). Fragile: PAD boundaries are arbitrary and overlapping; a stressful job interview has complex PAD.
- Hybrid (explicit + PAD fallback) — two code paths, harder to test, unclear which classification the consumer is seeing.
- Single `event-type` property — forces mutual exclusivity (can't be both Appointable and Threatening).
- Boolean properties per trait — verbose for LLM extractors.
**Rationale:** Orthogonality. An event CAN carry both `event-kind=scheduled` (Appointable) AND `event-valence=negative` (Threatening). The axes are independent — kind is about temporal fixedness, valence is about emotional anticipation. PAD inference is fragile because emotional nuance doesn't map cleanly to thresholds. Explicit properties are set by the LLM extractor or the caller — the source that understands the semantic context.
**Trade-offs:** Requires the extractor to set the right properties. If `eventKind` is missing, no event traits fire — but this is the correct behavior (not every future-dated node is an "event").
**Sources:** TraitRule.java (matches on node + edges), PersonableTraitRule.java (property-checking pattern), ProjectlikeTraitRule.java (status property check), cognitive-architecture-roadmap.md §3c
**Exploration:** quick
**Status:** captured

## D20: Anticipatory affect — explicit caller via AffectType enum

**Choice:** New `AffectType` enum (`INHERENT`, `ANTICIPATORY`) in `cognitive-api` (see D25 for placement). `AffectEvents` gets a new overload: `toMemoryInput(nodeId, tenantId, p, a, d, AffectType type)` that sets `affect-type` attribute. The existing overload defaults to `INHERENT`. `AffectTrajectoryDecorator` always logs as `INHERENT` — it captures the node's PAD, which is inherent affect. Anticipatory affect is logged by a separate caller.
**Alternatives:**
- Auto-detect from `validFrom` — if node is future-dated, tag as ANTICIPATORY. Conflates "future node" with "anticipatory affect." You can set inherent affect on a future event (a funeral's inherent sadness ≠ the agent's anticipatory grief).
- Dual-PAD on NodeUpdate — 6 PAD fields (3 inherent + 3 anticipatory). Heavy record expansion for a distinction that belongs in the memory log, not on the node itself.
**Rationale:** Inherent affect is a property of the event ("funerals are sad"). Anticipatory affect is a property of the agent's emotional response to the event ("I dread the funeral"). These are set by different actors at different times — inherent by the extractor at creation, anticipatory by the agent as the event approaches. Separate entry points enforce this distinction.
**Trade-offs:** Anticipatory affect logging is not automatic — the consuming application must call the overloaded converter explicitly. This is intentional: neocortex provides the mechanism; the agent framework (blocks) provides the trigger.
**Depends on:** D19 (event trait classification — anticipatory affect only applies to nodes with event traits)
**Sources:** AffectEvents.java (converter pattern), AffectTrajectoryDecorator.java (intercepts updateNode), AffectRecorded.java (CDI event), cognitive-architecture-roadmap.md §3c
**Exploration:** quick
**Status:** captured

## D21: Event lifecycle — convention only, no transition validation

**Choice:** Lifecycle states (PLANNED, CONFIRMED, ACTIVE, COMPLETED, CANCELLED, REVIEWED) are property values on the `status` key. No transition enforcement — the system does not validate that status changes follow legal paths. TraitRules apply traits based on current status. Enforcement is the caller's responsibility.
**Alternatives:**
- Validated transitions via decorator — a new decorator validates state transitions against a legal transition table. Robust but couples MindMapStore to lifecycle semantics. The generic property system shouldn't know about event-specific state machines.
- Convention + affect audit log — no enforcement but every status change logs an affect entry. Appealing but the AffectTrajectoryDecorator already logs PAD changes — status changes without PAD changes don't need affect logging.
**Rationale:** The existing pattern. `ProjectlikeTraitRule` already checks `node.property("status").isPresent()` with no validation of values. Lifecycle enforcement belongs in the application layer (blocks/engine), not in the storage layer. MindMapStore is a graph database, not a business rule engine. The status values are documented in the consumer guide as a convention.
**Trade-offs:** Nothing prevents invalid transitions (COMPLETED → PLANNED). Acceptable for a pre-release platform where the caller is always the LLM extractor or agent framework.
**Sources:** ProjectlikeTraitRule.java:18 (status check), cognitive-architecture-roadmap.md §3c, GE-20260803-263c2c (state machine technique — relevant for consumers, not for the storage layer)
**Exploration:** quick
**Status:** captured

## D22: RRULE — RecurrenceRule record in mindmap-api, generator in mindmap-intelligence

**Choice:** `RecurrenceRule` record in `mindmap-api`: `RecurrenceRule(Frequency freq, int interval, Integer count, Instant until, Set<DayOfWeek> byDay)` with `parse(String rrule)` factory and `toString()` that produces an RRULE string. Minimal RFC 5545 subset: FREQ (DAILY/WEEKLY/MONTHLY/YEARLY), INTERVAL, COUNT, UNTIL, BYDAY. `RecurrenceGenerator` static utility in `mindmap-intelligence`: `List<NodeInput> generateInstances(MindMapNode template, RecurrenceRule rule, Instant horizon)`. Property key on template: `rrule`. Pure function, no CDI.
**Alternatives:**
- Full RRULE via library — RFC 5545 with EXDATE, RDATE, WKST, BYMONTH, BYHOUR. Heavy dependency for a string property on a graph node.
- Opaque string, no parsing — maximum simplicity but defers all value to the caller. The generator couldn't exist in neocortex.
- CDI bean generator — @ApplicationScoped for injection. Adds CDI weight for a stateless pure function.
**Rationale:** The minimal subset covers the core recurrence patterns needed for cognitive modelling (weekly team meeting, monthly review, annual check-up). The record in `mindmap-api` enables downstream consumers (e.g., calendar queries in blocks) to parse the property without depending on mindmap-intelligence. The generator in mindmap-intelligence follows the `CuriositySignalGenerator` pattern — a static utility that operates on graph data.
**Trade-offs:** No EXDATE/RDATE support — can't express "every Monday except holidays." For a cognitive model, exceptions are handled by cancelling individual instance nodes (`status=CANCELLED`), which captures the cancellation as a cognitively meaningful event with its own affect. EXDATE is a planned extension for v2 when declarative exception intent becomes necessary.
**Planned extensions:** EXDATE (exception dates), RDATE (additional dates), BYMONTH, BYHOUR — added when real usage demonstrates need beyond the core cognitive model.
**Sources:** RFC 5545 §3.3.10 (RRULE), CuriositySignalGenerator.java (static utility pattern), cognitive-architecture-roadmap.md §3c
**Exploration:** quick
**Status:** captured

## D23: Template-to-instance relationship — property link

**Choice:** Instance nodes carry `template-node-id=<templateId>` and `recurrence-index=<N>` as properties. The template node carries `rrule=<RRULE string>`. No edges between template and instances.
**Alternatives:**
- NodeRef — `NodeRef(scheme="template", id=templateId)`. Type-safe but NodeRefs are for cross-system references (memory, cbr), not intra-graph relationships.
- Edge — `edge-type="recurrence-instance"` from template to each instance. Graph-native but creates O(n) edges that clutter the graph and trigger DerivedEdgeRule evaluation for each.
**Rationale:** Properties are the simplest mechanism for metadata that doesn't need graph traversal. "Find all instances of this template" is a property-value search, not a graph walk. Edges are for semantic relationships between entities; template→instance is an implementation relationship.
**Trade-offs:** No graph-native traversal from template to instances. Property search works but isn't indexed in InMemoryMindMapStore's `search()` (it does text matching across values, not exact property-value lookup). Acceptable — the use case is rare and n is small.
**Depends on:** D22 (RRULE design)
**Sources:** MindMapNode.properties() (property system), NodeRef.java (cross-system ref), DerivedEdgeDecorator.java (edge-triggered rules)
**Exploration:** quick
**Status:** captured

## D24: Trait interface — single Eventlike interface

**Choice:** One `Eventlike` interface covering all event-related properties: `eventKind()`, `eventValence()`, `status()`, `rrule()`. Accessible via `TraitProxy.as(node, Eventlike.class)`. Separate from the 4 TraitRule implementations — the rules classify, the interface provides typed access.
**Alternatives:**
- Per-trait interfaces (Appointable, Aspirational, Threatening, Opportunistic) — follows existing pattern (Personable, Projectlike, Organisational). But event traits share a property namespace — splitting creates 4 interfaces with overlapping property access.
**Rationale:** Event traits share a property namespace (`eventKind`, `eventValence`, `status`, `rrule`). A node classified as both Appointable and Threatening has the same properties accessible through either trait. One interface avoids duplication and provides a single typed view of all event properties. The existing pattern (one interface per trait) works when traits have disjoint property namespaces; event traits don't.
**Trade-offs:** Consumer code uses `Eventlike` for all event types rather than a specific interface. The trait name (`Set<String> traits()`) still carries the specific classification.
**Depends on:** D19 (event trait properties)
**Sources:** Personable.java (trait interface pattern), TraitProxy.java (JDK Proxy accessor), cognitive-architecture-roadmap.md §3c
**Exploration:** quick
**Status:** captured

## D25: AffectType enum placement — cognitive-api

**Choice:** `AffectType` enum in `io.casehub.neocortex.cognitive` alongside `ConfidenceOrigin` and `TemporalMark`. Values: `INHERENT`, `ANTICIPATORY`.
**Alternatives:**
- memory-api alongside AffectEvents converter — colocates with the only current producer, but organizes by implementation proximity, not concept ownership. Future consumers (MindMap decorators distinguishing inherent from anticipatory PAD, CBR cases carrying affect type for retrieval scoring) would depend on memory-api for a cognitive concept.
- mindmap-api — it's about MindMap node affect. But the enum is consumed by the memory converter, not the MindMap store.
**Rationale:** AffectType classifies emotional relationship to events — a cognitive distinction independent of which subsystem produces or consumes it. Conceptually parallel to ConfidenceOrigin (classifies certainty provenance) and TemporalMark (classifies temporal reference). Meets the cognitive-api acceptance criteria (D26): it models a cognitive classification, is subsystem-independent, and its nature is inherently cross-cutting. AffectEvents in memory-api imports it, same as it already imports ConfidenceOrigin from cognitive-api. cognitive-api remains zero-deps — AffectType is a two-value enum.
**Trade-offs:** AffectEvents must import from cognitive-api instead of a local type. This is the same pattern it already uses for ConfidenceOrigin.
**Sources:** AffectEvents.java (converter), ConfidenceOrigin.java (parallel pattern), cognitive-api package structure, D26 (acceptance criteria)
**Exploration:** quick
**Status:** revised — moved from memory-api to cognitive-api per cognitive classification principle (R1-05)

## D26: cognitive-api acceptance criteria

**Choice:** cognitive-api houses types that classify or qualify cognitive state independent of which subsystem produced or consumes them. A type belongs in cognitive-api when it meets ALL of: (1) it models a cognitive classification or qualification (not domain-specific logic or converter utilities), (2) it is independent of any particular subsystem's implementation details, (3) it is zero-deps (no transitive dependencies beyond java.base). Types that are inherently cross-cutting by nature qualify even when currently consumed by a single subsystem — placement is by concept ownership, not consumer count.
**Alternatives:**
- Consumer-count heuristic — place in cognitive-api when 2+ subsystems use it. Fragile: a type can have one consumer today and three tomorrow. Leads to premature placement in module-specific packages followed by disruptive moves.
- Producer-count heuristic — place where the only producer lives. Conflates implementation proximity with concept ownership. The producer is an implementation detail; the concept's nature is architectural.
- No criteria — ad-hoc reasoning per decision. Leads to inconsistent placement over time as different decision-makers apply different heuristics.
**Rationale:** The criterion separates concept ownership (architectural) from implementation proximity (mechanical). ConfidenceOrigin classifies certainty provenance, TemporalMark classifies temporal reference, AffectType classifies emotional relationship — all are cognitive classifications independent of the subsystem that produced the data. The "by nature" clause prevents reactive placement: a cognitive concept placed in a module-specific package just because it has one consumer today will need to move when the second consumer arrives. cognitive-api's zero-deps constraint (D1) is an additional filter — types that carry dependencies belong in their module's API, not cognitive-api.
**Current members:** Confidence, ConfidenceOrigin, TemporalMark (WallClock, Relative, Ordinal), AffectType (D25).
**Trade-offs:** Requires judgment about whether a type is a "cognitive classification" — but that judgment is now explicit and documented rather than implicit and ad-hoc.
**Depends on:** D1 (module placement)
**Sources:** D1 (cognitive-api module), D8 (TemporalMark placement reasoning), D25 (AffectType placement reasoning), cognitive-architecture-roadmap.md §Principles (Orthogonality)
**Exploration:** surfaced by review (R1-10)
**Status:** captured

## D27: Trajectory data access — direct dependency on memory-api + cognitive-index

**Choice:** Add `memory-api` and `cognitive-index` as dependencies to `mindmap-intelligence`. `CuriositySignalGenerator` injects `Instance<CaseMemoryStore>` for graceful degradation. `AffectTrajectoryAnalyzer` is a static utility — no runtime coupling.
**Alternatives:**
- Trajectory provider SPI — define interface in mindmap-api, cognitive-index implements. Clean but adds an interface for a single consumer.
- Pass trajectory externally — caller pre-computes and passes. Pushes complexity to every caller.
**Rationale:** Follows the established `Instance<T>` pattern (AffectTrajectoryDecorator, MultiModalEmbedderProducer). No circular dependencies — cognitive-index depends on mindmap-api, not mindmap-intelligence.
**Trade-offs:** mindmap-intelligence gains two new dependencies. Acceptable — it already depends on mindmap, mindmap-api, and quarkus-arc.
**Sources:** CuriositySignalGenerator.java, AffectTrajectoryDecorator.java (Instance pattern), cognitive-architecture-roadmap.md §3e
**Exploration:** quick
**Status:** captured

## D28: PROXIMITY signals participate in trajectory modulation

**Choice:** Remove the `if (category == PROXIMITY) continue` skip. PROXIMITY signals get trajectory-based modulation: worsening boosts, improving dampens. Implements the roadmap's "approaching + worsening = highest priority" temporal-affective interplay.
**Alternatives:**
- Keep PROXIMITY exempt — simpler but misses the roadmap's core design (temporal-affective interplay is the point of this issue).
**Rationale:** The roadmap explicitly defines the interplay matrix (approaching + worsening = highest priority, approaching + improving = lower priority). Exempting PROXIMITY signals defeats the purpose.
**Trade-offs:** PROXIMITY scores now depend on memory data. If no CaseMemoryStore, fallback to snapshot preserves current behavior.
**Depends on:** D27 (dependency access)
**Sources:** CuriositySignalGenerator.java:185, cognitive-architecture-roadmap.md §3e (temporal-affective interplay table)
**Exploration:** quick
**Status:** captured

## D29: Trajectory thresholds via CuriosityConfig record

**Choice:** New `CuriosityConfig` record in `mindmap-intelligence` with trajectory dampening thresholds. Provides `defaults()` factory. Injected into `CuriositySignalGenerator` via `Instance<CuriosityConfig>` — falls back to `CuriosityConfig.defaults()` if not provided. Also absorbs existing hardcoded constants (PROXIMITY_SCALE, STALE_THRESHOLD, MAX_BFS_DEPTH, TOP_CENTRALITY).
**Alternatives:**
- Quarkus `@ConfigMapping` — config-file driven. More flexible but the thresholds are agent-specific (per cognitive profile), not deployment-specific. Config mapping is the wrong layer.
- Keep hardcoded — simplest but the thresholds are tunable parameters that belong in configuration.
**Rationale:** A record with defaults matches the Phase 5 roadmap design — `CuriosityConfig` will eventually be produced from cognitive profile YAML. For now, a CDI-injectable record with sensible defaults gives testability (pass config in tests) and future YAML wiring without adding config-file infrastructure.
**Trade-offs:** Adds a type for what was previously 4 constants. Worth it — the trajectory thresholds double the number of tunable parameters.
**Depends on:** D27 (trajectory access)
**Sources:** CuriositySignalGenerator.java:26-29 (existing constants), cognitive-architecture-roadmap.md §5c (cognitive profile YAML)
**Exploration:** quick
**Status:** captured

## D30: TemporalFocus — pure static utility with pre-computed trajectories

**Choice:** `TemporalFocus` is a pure static utility in `cognitive-index`. `focus(entries, now, trajectories, config)` returns `List<AttentionItem>`. `ranker(trajectories, config)` returns a composable `TemporalRanker`. No CDI, no store access. Caller pre-computes `Map<String, AffectTrajectory>` and passes it in.
**Alternatives:**
- CDI bean with Instance<CaseMemoryStore> — queries trajectories on demand. Convenient but impure, introduces N+1 query risk.
- Wrapper class around TemporalIndex — violates D13 (pure chronological aggregator) and D14 (composable ranking).
**Rationale:** Follows the established static utility pattern (AffectTrajectoryAnalyzer, MindMapAnalyzer, RetrievalAnalyzer). Pure function = testable without CDI, composable with any TemporalIndex query. Pre-computed trajectories avoid N+1 queries.
**Trade-offs:** Caller must pre-compute trajectories. Acceptable — the tick-loop caller queries trajectories once and passes them to both CuriositySignalGenerator and TemporalFocus.
**Depends on:** D13 (pure aggregator), D14 (composable ranker)
**Sources:** TemporalRanker.java (functional interface), AffectTrajectoryAnalyzer.java (static utility pattern), cognitive-architecture-roadmap.md §4b
**Exploration:** quick
**Status:** captured

## D31: TemporalFocusConfig — tunable scoring parameters

**Choice:** `TemporalFocusConfig` record in `cognitive-index` with scoring parameters: `proximityScale` (7.0), `worseningBoostCap` (1.0), `improvingDampenFactor` (0.5), `volatilityBoostCap` (0.5). `defaults()` factory. Passed to `focus()` and `ranker()`. Aligns with Phase 5 cognitive profile YAML.
**Alternatives:**
- Hardcoded constants — simple but inconsistent with D29 (CuriosityConfig established the configurable-thresholds pattern).
**Rationale:** Consistency with CuriosityConfig. Both are cognitive scoring utilities whose parameters will be derived from the cognitive profile YAML in Phase 5.
**Depends on:** D29 (CuriosityConfig pattern)
**Sources:** CuriosityConfig.java (pattern), cognitive-architecture-roadmap.md §5c
**Exploration:** quick
**Status:** captured

## D32: AttentionItem record — scored entry with reason

**Choice:** `AttentionItem(TemporalEntry entry, double salience, String reason)` record in `cognitive-index`. Implements `Comparable<AttentionItem>` (descending salience). Reason is a human-readable string: "approaching event", "recent experience", "worsening affect".
**Alternatives:**
- Extend TemporalEntry with score+reason — breaks the clean separation between data (entry) and scoring (ranker).
- Enum-based reason — structured but limits expressiveness; string is simpler and the reason is for display, not programmatic use.
**Rationale:** Clean composition: TemporalEntry is data, AttentionItem is scored data. The record is the return type of `focus()` — it carries everything a consumer needs to render an attention list.
**Depends on:** D30 (TemporalFocus design)
**Sources:** TemporalEntry.java (entry record), cognitive-architecture-roadmap.md §4b
**Exploration:** quick
**Status:** captured
