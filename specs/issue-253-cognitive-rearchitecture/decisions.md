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
**Trade-offs:** MindMapNode's `confirmedAt` becomes redundant — resolved by D6 (remove confirmedAt). Backends must persist decayReference alongside origin+value.
**Depends on:** D1 (module placement)
**Sources:** ConfidenceDecayDecorator.java (mindmap/runtime), MindMapNode.java:27 confirmedAt, MindMapEdge.java:22 updatedAt
**Exploration:** quick
**Status:** captured

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

## D5: CbrOutcome.adjustConfidence operates on Confidence

**Choice:** `adjustConfidence(Confidence old, double successRate, double learningRate, Instant observedAt)` → returns `Confidence` (preserves origin, updates value via EMA, sets decayReference to observedAt). CbrOutcome itself stays in memory-api — it's a CBR-specific operation record, not a cross-cutting type.
**Alternatives:**
- Keep Double-based adjustConfidence — callers wrap/unwrap Confidence manually. Works but error-prone.
- Move EMA into Confidence itself (`Confidence.adjust(...)`) — couples a CBR-specific operation trigger into the shared type. EMA is general-purpose math but only CBR uses it today; adding it to Confidence would be speculative.
- Pass entire CbrOutcome to the method — couples CbrOutcome to Confidence construction. The method is a math utility, not an event processor.
**Rationale:** The operation naturally preserves origin (how we originally learned this) while updating the numeric value and when it was last assessed. `Instant observedAt` as an explicit parameter makes the decayReference update clear in the method signature. CbrOutcome stays in memory-api because it carries CBR-specific fields (result, successRate, detail). adjustConfidence stays on CbrOutcome because it captures "how CBR outcomes adjust confidence" — the trigger context matters even though the math is general.
**Trade-offs:** CbrOutcome gains a dependency on cognitive-api (via memory-api's transitive dependency). Method signature gains a fourth parameter.
**Depends on:** D1 (module placement), D4 (API surface)
**Sources:** CbrOutcome.java:30-34 adjustConfidence, InMemoryCbrCaseMemoryStore.java:198 (call site with outcome.observedAt() available), JpaCbrCaseMemoryStore.java:228, QdrantCbrCaseMemoryStore.java:671
**Exploration:** quick
**Status:** revised — Instant observedAt added as explicit parameter (R1-14)

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
**Rationale:** A zero-deps type can't perform lookups. Carrying the resolved timestamp makes the mark self-contained — once constructed, it can be sorted, compared, and persisted without external dependencies. The resolver is the caller's responsibility at construction time, not at usage time.
**Trade-offs:** Resolution must happen at construction. If the turn-timestamp mapping changes later, the mark becomes stale. Acceptable — timestamps of past turns don't change.
**Sources:** cognitive-architecture-roadmap.md §2a (resolveToInstant design), ExperienceEvent.java (turnId field), memory-api event types
**Exploration:** quick
**Status:** captured

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
