## D1: Module placement for unified Confidence type

**Choice:** New `cognitive-api` module — tier-0 pure Java, zero dependencies
**Alternatives:**
- In mindmap-api — lightweight but couples mindmap concepts into memory's dependency tree
- In memory-api — forces mindmap-api to gain heavier dependencies, breaking its zero-dep constraint
**Rationale:** `cognitive-api` starts lean (2 types: `Confidence`, `ConfidenceOrigin`) but has a clear growth path — `TemporalMark` (#234), `MemorySpace`/`Visibility` (#230), `NodeRef` (#243), `Affect` (#238) all need the same cross-cutting home. Justified investment, not speculative infrastructure.
**Trade-offs:** Adds a module to the build. Every future type placement decision must consider cognitive-api vs module-specific.
**Sources:** cognitive-architecture-roadmap.md §1a, cognitive-coherence-audit.md §Dimension 1, mindmap-api/pom.xml (zero deps), memory-api/pom.xml (fusion-api + platform-api deps)
**Exploration:** quick
**Status:** captured

## D2: Decay reference placement — internal to Confidence

**Choice:** `Confidence(ConfidenceOrigin origin, double value, Instant decayReference)` — decay reference is a field on the record
**Alternatives:**
- External only — Confidence carries just origin+value; each store picks its own timestamp for decay (confirmedAt, updatedAt, storedAt). Simpler record but perpetuates entity-specific dispatch in the decorator.
- Both with fallback — internal with external override. Migration-friendly but adds precedence rules.
**Rationale:** "When was this confidence level last established?" is a property of the confidence itself, not the entity. Eliminates the awkward asymmetry where MindMapNode uses `confirmedAt` and MindMapEdge uses `updatedAt` for the same conceptual purpose. Makes `ConfidenceDecayDecorator` generic — it reads `confidence().decayReference()` regardless of entity type.
**Trade-offs:** MindMapNode's `confirmedAt` now becomes redundant for decay (may still serve as a human-readable audit timestamp). Backends must persist decayReference alongside origin+value.
**Depends on:** D1 (module placement)
**Sources:** ConfidenceDecayDecorator.java (mindmap/runtime), MindMapNode.java:27 confirmedAt, MindMapEdge.java:22 updatedAt
**Exploration:** quick
**Status:** captured

## D3: ConfidenceOrigin scope — keep 3 values, nullable

**Choice:** ConfidenceOrigin stays as STATED/INFERRED/SPECULATED (unchanged). Nullable on the Confidence record. Moved to cognitive-api as-is.
**Alternatives:**
- Expand now — add OBSERVED, COMPUTED, REFLECTED for Memory/CBR contexts. Richer but couples #229 scope to #232 naming audit.
- Replace with String — maximum flexibility but loses type safety and initialConfidence() defaults.
**Rationale:** Minimal change for #229. Memory uses `origin=null` (unknown provenance), CBR uses `null` or `INFERRED`. Extensions belong in #232 (naming audit) where the full terminology table is being pinned. The enum values have stable semantics within MindMap; broadening them prematurely risks naming choices that conflict with the audit.
**Trade-offs:** null origin means "source unknown" — consumers must handle the null case. No enum value for EMA-computed confidence until #232.
**Depends on:** D1 (module placement)
**Sources:** cognitive-architecture-roadmap.md §Terminology ("importance becomes value with origin=null"), ConfidenceOrigin.java
**Exploration:** quick
**Status:** captured

## D4: API surface — single Confidence accessor replaces split fields

**Choice:** MindMapNode/MindMapEdge: `confidenceOrigin()` + `confidence()` → single `Confidence confidence()`. NodeInput/EdgeInput: separate fields → single `Confidence confidence`. MemoryInput/Memory: `Double importance` → `Confidence confidence` (nullable). CbrCase: `Double confidence()` → `Confidence confidence()`.
**Alternatives:**
- Keep split fields + add Confidence — backwards compatible but duplicates the concept, confuses which to use.
- Adapter layer — old methods delegate to Confidence internally. Avoids breaking callers but adds indirection that never gets cleaned up.
**Rationale:** Pre-release platform — breaking changes cost nothing. One concept = one method. All callers update to `node.confidence().value()` which is more explicit about what they're reading. Eliminates the possibility of confidenceOrigin and confidence being inconsistent.
**Trade-offs:** Every caller of `node.confidence()` (expecting double) must update. 155 ConfidenceOrigin references + all confidence() call sites.
**Depends on:** D2 (record shape)
**Sources:** MindMapNode.java, MindMapEdge.java, MemoryInput.java, Memory.java, CbrCase.java
**Exploration:** quick
**Status:** captured

## D5: CbrOutcome.adjustConfidence operates on Confidence

**Choice:** `adjustConfidence(Confidence old, double successRate, double learningRate)` → returns `Confidence` (preserves origin, updates value + decayReference to observedAt). CbrOutcome itself stays in memory-api — it's a CBR-specific operation record, not a cross-cutting type.
**Alternatives:**
- Keep Double-based adjustConfidence — callers wrap/unwrap Confidence manually. Works but error-prone.
- Move EMA into Confidence itself — couples a CBR-specific operation into the shared type.
**Rationale:** The operation naturally preserves origin (how we originally learned this) while updating the numeric value and when it was last assessed. CbrOutcome stays in memory-api because it carries CBR-specific fields (result, successRate, detail).
**Trade-offs:** CbrOutcome gains a dependency on cognitive-api (via memory-api's transitive dependency).
**Depends on:** D1 (module placement), D4 (API surface)
**Sources:** CbrOutcome.java:30-34 adjustConfidence, CbrCaseMemoryStore.java:23 recordOutcome
**Exploration:** quick
**Status:** captured
