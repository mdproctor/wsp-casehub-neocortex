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

**Choice:** Remove `confirmedAt` from `MindMapNode`. Node confirmation = updating `Confidence` with `decayReference=Instant.now()` (value and origin unchanged). NodeUpdate's `confirmedAt` field is subsumed by the new `Confidence confidence` field — callers construct a Confidence with updated decayReference.
**Alternatives:**
- Keep confirmedAt, derive decayReference from it — contradicts D2's design (decayReference is on the Confidence record, not derived from entity fields). Two sources of truth.
- Keep both, enforce equality — redundant fields with an invariant to maintain. Store implementations must keep them in sync.
- Keep confirmedAt as audit-only — adds a field that no consumer reads for audit purposes (verified: only ConfidenceDecayDecorator.java:78 and MindMapAnalyzer.java:163 read confirmedAt, both for decay/staleness).
**Rationale:** `confirmedAt` was always the decay anchor for nodes. After unification, `confidence().decayReference()` serves this role. The two runtime consumers (ConfidenceDecayDecorator, MindMapAnalyzer.staleNodes) read `confirmedAt` purely for decay computation — both migrate to `confidence().decayReference()`. No consumer reads confirmedAt for audit/human-readable purposes. `updatedAt` already captures "when was this entity last modified" for audit needs.
**Trade-offs:** Callers that set `NodeUpdate.confirmedAt` must construct a Confidence record instead. Breaking change — but pre-release platform.
**Depends on:** D2 (decayReference on Confidence), D4 (NodeUpdate surface change)
**Sources:** MindMapNode.java:26, ConfidenceDecayDecorator.java:78, MindMapAnalyzer.java:163, MindMapStoreContractTest.java:222
**Exploration:** surfaced by review (R1-06)
**Status:** captured

## D7: Memory importance → Confidence.value mapping

**Choice:** Memory's `Double importance` maps to `Confidence.value` with `origin=UNKNOWN`. This is a deliberate semantic collapse — importance (attentional salience) and confidence (epistemic certainty) are conceptually distinct but unified under a single [0,1] scalar.
**Alternatives:**
- Keep importance separate from confidence — Memory carries both `Confidence confidence` AND `Double importance`. Preserves the semantic distinction but means the "unified confidence" is not actually unified — Memory has two numeric dimensions where other subsystems have one.
- Multi-dimensional Confidence — `Confidence(origin, certainty, salience, decayReference)`. Captures both dimensions but designs a multi-axis model without evidence of what axes are actually needed. Premature decomposition.
- Rename importance to confidence with no acknowledgment — silent conflation without explicit design rationale.
**Rationale:** The current `importance` field on Memory has no clear semantics — it's used as a retrieval weight in `PersonalityWeightedRetrieval` and `MoodModulatedRetrieval`, where it modulates ranking. It's not a well-defined measure of either salience or certainty. Unifying under a single scalar: (1) enables cross-store comparison and ranking, (2) eliminates an ambiguous field, (3) is the prerequisite for later decomposition if real usage reveals distinct dimensions. The roadmap's terminology table explicitly retires `importance` in favor of `confidence`. If Phase 3+ work reveals that salience and certainty must be separate (e.g., "high-importance but low-confidence" patterns emerge in real agent behavior), the Confidence record can be extended then — with evidence of what decomposition is actually needed.
**Depends on:** D1 (module placement), D4 (API surface)
**Sources:** cognitive-architecture-roadmap.md §Terminology ("importance becomes value with origin=null"), Memory.java:14 (importance field), MemoryInput.java:13 (importance field), PersonalityWeightedRetrieval usage, MoodModulatedRetrieval usage
**Exploration:** surfaced by review (R1-17)
**Status:** captured
