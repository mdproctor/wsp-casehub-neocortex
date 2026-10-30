# Decisions — #721 Unified Entity Linking

## D1: Primary use case ordering

**Choice:** Authored corpus first, extend to runtime
**Alternatives:**
- Runtime LLM output first — higher latency sensitivity, less controlled input
- Both simultaneously — higher initial complexity without iterative learning
**Rationale:** Biography YAML corpus is controlled, batch-processed, and the extraction pipeline already exists. Design annotation format + indexes here where correctness can be verified, then extend to runtime.
**Trade-offs:** Runtime integration comes later, but the API is designed for both from the start.
**Sources:** Issue #721 (hybrid authoring section)
**Exploration:** quick
**Status:** captured

## D2: Annotation storage

**Choice:** Dedicated annotation index (new SPI + SQLite store)
**Alternatives:**
- Memory.attributes — only covers Memory text source, requires secondary index for entity→text queries (dual storage), opaque to store queries
- MindMap node properties — inverts the natural direction (text owns spans, not entities)
**Rationale:** First-principles analysis. Entity→text is the primary query direction. Annotations span multiple text sources (memories, MindMap node bodies, biography YAML, conversation turns). A dedicated index is the only option serving all sources without dual storage. Directly queryable both directions via indexed columns.
**Trade-offs:** Another store to manage — but it's a single SQLite table following existing patterns (SqliteRetrievalTracker, SqliteCbrRetrievalTracker).
**Tenancy:** The annotation index is tenant-scoped per the tenancy-repository-pattern protocol. Every annotation carries tenantId. All SPI query methods require tenantId. The SQLite store enforces tenant isolation unconditionally — no conditional filtering, no deployment-mode gates.
**Sources:** Memory.java, MindMapNode.java, NodeRef.java, first-principles analysis of query directions, tenancy-repository-pattern protocol
**Exploration:** deep-analysis
**Status:** revised — R1-12: made tenancy scoping explicit per platform protocol

## D3: Coreference model

**Choice:** Flat — every span points directly to entity_node_id
**Alternatives:**
- Explicit chain: spans grouped into numbered chains — preserves discourse structure but adds indirection
- Hierarchical: mention → chain → entity — three-level model, unnecessary complexity
**Rationale:** The chain IS the set of spans sharing the same entity_node_id. Chain reconstruction is GROUP BY. No additional data structure needed. All queries work via entity_node_id index.
**Trade-offs:** Loses discourse structure (which pronoun refers to which antecedent within a text). Acceptable — the use cases are entity-centric, not discourse-centric.
**Sources:** Issue #721 (coreference chains section)
**Exploration:** quick
**Status:** captured

## D4: Annotation production mechanism

**Choice:** Two-phase: LLM produces surface form mentions + coreference links during extraction, programmatic code computes character offsets via deterministic string matching
**Alternatives:**
- LLM produces character offsets directly — unreliable; LLMs hallucinate positions, miscounting whitespace, multi-byte characters, and token boundaries
- Separate annotation pass — additional LLM call adds latency and consistency risk for a task that is a natural extension of extraction output
- Inline YAML anchors only — only works for named mentions, not pronouns
**Rationale:** Entity identification and coreference resolution are semantic tasks the LLM excels at. Character offset computation is a positional task the LLM does poorly. MindMapExtractor already identifies entities and resolves coreferences. Extending its output to report surface form mentions ("He" → "James Pond") is a semantic extension. A programmatic post-pass locates those surface forms in the original text and computes exact character offsets — zero hallucination risk.
**Trade-offs:** Couples annotation production to extraction. If extraction fails, annotations fail too. Acceptable — annotations without extracted entities are meaningless anyway. Surface form matching may encounter ambiguity (multiple occurrences of the same surface form) — resolved by positional context from the LLM's mention ordering.
**Sources:** MindMapExtractor.java (parse/apply split), ParsedExtraction.java, ParsedEntity.java
**Exploration:** quick
**Status:** revised — R1-02: adopted two-phase approach separating semantic identification (LLM) from positional computation (code)

## D5: Memory lifecycle handling

**Choice:** CDI event observer on MemoryEntityErased, deleting annotations by (tenantId, sourceType, ownerSubjectId)
**Alternatives:**
- Decorator on CaseMemoryStore — tighter coupling, atomic but Memory shouldn't know about annotations
- Periodic reconciliation — eventually consistent, allows stale data to linger
- Modify erasure event to carry memory IDs — changes the event contract for a single consumer
- Delete by entity_node_id matching resolved subject — identity mismatch (Subject.id() is an entity name, entity_node_id is a MindMap node UUID), scope incompleteness (misses annotations from subject's memories about other entities), and MindMapStore race condition (node may already be erased)
**Rationale:** MemoryEntityErased CDI events already fire on erase. Decoupled — annotation index is optional, Memory doesn't know about it. The event carries Subject (with `id()` = entity name like "alice") and tenantId but not individual memory IDs. Each memory-sourced annotation carries an indexed `ownerSubjectId` field — the `Subject.id()` of the memory owner, set at creation time from `Memory.subject().id()`. On `MemoryEntityErased.ByEntity(tenantId, count, subject, erasedAt)`, the observer deletes all annotations where `ownerSubjectId = subject.id() AND sourceType = "memory" AND tenantId` matches. This avoids the identity mismatch (comparing entity names to entity names, not to MindMap node UUIDs), provides complete scope (deletes ALL annotations from the subject's memories regardless of which entities they reference), and requires no MindMapStore dependency at deletion time. For ByRequest: same mechanism scoped by domain. For CrossTenant: iterate affected tenants. The observer depends on annotation-api and memory-api only — no MindMapStore.
**Trade-offs:** Small window where annotations reference a deleted memory. Acceptable — no consumer will find the memory to render against. The `ownerSubjectId` field is nullable — non-memory source types may not have a meaningful owner subject.
**Sources:** MemoryEntityErased sealed interface (ByRequest, ByEntity, CrossTenant variants), Memory.subject(), MindMapBeans.onMemoryEntityErased() pattern (uses subject().id() directly as entity name)
**Exploration:** quick
**Status:** revised — R1-07 + R2-02 + R2-04: ownerSubjectId mechanism for identity-correct, scope-complete deletion

## D6: Merge handling

**Choice:** CDI event observer on GraphMutationRecorded, pattern-matching on NodesMerged variant (repoint absorbedId → survivorId)
**Alternatives:**
- MindMapStore decorator — atomic but tighter coupling; annotation index is a cross-cutting concern, not a MindMap concern
- Dedicated CDI event type for merges — new infrastructure; GraphMutationRecorded already wraps all mutation variants
- Both decorator + event — belt-and-suspenders, over-engineered
**Rationale:** Rename is safe (node ID unchanged). Only merge retires a node ID. MutationTrackingCdiDecorator fires GraphMutationRecorded wrapping GraphMutation.NodesMerged(survivorId, absorbedId, conflictsResolved, timestamp, source). The annotation observer lives in a CDI-capable module (e.g. annotation-cdi), not in annotation-api (Tier 1). This follows the established pattern: types in Tier 1, CDI integration in a separate module. Depends on cognitive-observability-core for the GraphMutation sealed type — this is a Tier 2 core module (contains MutationTrackingDecorator extending AbstractForwardingMindMapStore, with compile dependencies on mindmap-core, mindmap-intelligence, cognitive-index, jackson-databind). The transitive dependency weight is acceptable for the annotation-cdi module (CDI-capable, Tier 2+). Optional optimization: extract GraphMutation and GraphMutationRecorded types (which themselves depend only on Tier 1 modules: MergeConflict from mindmap-api, Confidence from cognitive-api) into a dedicated cognitive-observability-api Tier 1 module, following the standard three-tier split.
**Trade-offs:** Small window where annotations reference a retired node. Needs strong TDD — merge + annotation repointing is correctness-critical. Contract tests must cover: merge repoints, merge with duplicate spans (deduplication after repointing), merge cascade.
**Sources:** MutationTrackingDecorator.mergeNodes(), MutationTrackingCdiDecorator, GraphMutationRecorded, GraphMutation.NodesMerged
**Exploration:** quick
**Status:** revised — R1-03 + R2-03: specified exact mechanism (GraphMutationRecorded + pattern match), observer module placement, corrected cognitive-observability-core tier characterization from Tier 1 to Tier 2

## D7: Surface form storage

**Choice:** Store mention text alongside entity_node_id and offsets
**Alternatives:**
- Offsets only — recover surface form by slicing original text, but requires text to be available at query time
**Rationale:** Enables debugging, rendering annotation overlays without the original text, and understanding what surface form triggered the link. Archival — entity_node_id is authoritative. A few extra bytes per row.
**Trade-offs:** Slight storage overhead. Negligible for expected data volumes.
**Sources:** Issue #721 (profile independence section)
**Exploration:** quick
**Status:** captured

## D8: Scope

**Choice:** Full vision in one pass — all text sources, runtime coref, cognitive integration
**Alternatives:**
- API + SQLite + authored corpus only — lower risk, slower impact
- API + SQLite + corpus + retrieval — middle ground
**Rationale:** User direction. XL issue with the full architecture designed upfront. Implementation plan will decompose into ordered batches.
**Trade-offs:** Large implementation surface. Mitigated by strong API-first design and contract tests.
**Sources:** User direction, Issue #721 (full scope)
**Exploration:** quick
**Status:** captured

## D9: Runtime annotation path

**Choice:** Same extraction pass — MindMapExtractor produces spans during async extraction
**Alternatives:**
- Separate annotation step post-extraction — adds latency, cleaner separation
- Inline during ConversationBridge segmentation — fast but only catches named mentions
**Rationale:** MindMapExtractor already processes the text and identifies entities. Extended output produces annotations as a side-effect. No additional LLM call. ExtractionRequestedObserver writes spans to annotation index after applying entities to MindMap.
**Trade-offs:** Annotation quality depends on extraction quality. Acceptable — annotations are about the entities extraction found.
**Sources:** ConversationBridge.java, ExtractionRequestedObserver, MindMapExtractor.java
**Exploration:** quick
**Status:** captured

## D10: Retrieval integration

**Choice:** ModulationFactor<Memory> for entity overlap scoring
**Alternatives:**
- New retrieval method on annotation index — parallel retrieval path outside normal pipeline
- CaseRetriever decorator — couples annotation index to RAG
**Rationale:** Plugs into existing RetrievalModulator infrastructure (ModulationFactor, ModulationContext). Non-invasive — doesn't change retrieval SPIs. Boosts scores for memories sharing entity annotations with query context.
**Trade-offs:** Modulation is post-retrieval scoring, not retrieval-time filtering. Memories without entity overlap can still be retrieved via vector similarity. Acceptable — entity overlap is a signal, not a gate.
**Sources:** ModulationFactor, GoalRelevanceModulationFactor, RetrievalModulator
**Exploration:** quick
**Status:** captured

## D11: Cognitive integration scope

**Choice:** All four subsystems — salience, reflection, belief revision, Theory of Mind
**Alternatives:**
- Salience + reflection only — highest immediate impact
- Salience only — minimal viable
**Rationale:** User direction for full vision. Entity-awareness improves all four: salience (exact entity overlap vs fuzzy keyword), reflection (entity-scoped knowledge retrieval), belief revision (entity-grounded provenance), ToM (entity-scoped mental model building from ALL mentions including pronouns).
**Trade-offs:** Large integration surface across cognitive subsystems. Each integration point needs its own tests.
**Sources:** Issue #721 (cognitive operations section), ConcernBasedSalienceStrategy, MentalModelOrchestrator
**Exploration:** quick
**Status:** captured

## D12: Module placement

**Choice:** New annotation-api module (Tier 1 pure Java, zero CDI)
**Alternatives:**
- In mindmap-api — adds text-centric concern to graph-centric module
- In cognitive-api — annotations more fundamental than cognition
**Rationale:** Annotations bridge text and graph — orthogonal to both. Follows existing Tier 1 module patterns (fusion-api, corpus-api, thing-api). SPI + value types in annotation-api. SQLite impl in annotation-sqlite. In-memory in annotation-inmem. Contract tests in annotation-testing. CDI event observers (for merge handling D6, memory lifecycle D5) live in a separate CDI-capable module (annotation-cdi), not in annotation-api.
**Dependency boundary:** annotation-api does NOT depend on mindmap-api. Entity node IDs are opaque `String` identifiers per the platform's cross-module identifier convention. Resolution from entity name → node ID (via `MindMapStore.resolveNode()`) happens in the annotation-producing code, which lives in a higher-tier CDI-capable module. annotation-api defines its own text source identity type (D16) rather than importing `NodeRef` from mindmap-api.
**Trade-offs:** More modules. Acceptable — clean boundaries pay for themselves in test isolation.
**Sources:** fusion-api, corpus-api, thing-api module patterns, module-tier-structure protocol
**Exploration:** quick
**Status:** revised — R1-09: made dependency boundary and opaque identifier convention explicit

## D13: Architecture coupling

**Choice:** Dual — CDI events for lifecycle + direct SPI for queries
**Alternatives:**
- Event-driven only — forces consumers to cache and sync, strictly worse than querying index
- Direct API only — no lifecycle notifications, consumers must poll
**Rationale:** Events and direct API serve different purposes. Events notify state changed (annotation created, entity merged, memory erased). Direct API answers questions about current state (findByEntity, findByMemory). Every consumer needs the query API regardless. Events are orthogonal.
**Trade-offs:** None significant — this is the natural decomposition.
**Sources:** Existing CDI event patterns (ExperienceRecorded, CbrRetrievalRecorded, MemoryEntityErased)
**Exploration:** quick
**Status:** captured

## D14: YAML anchor syntax

**Choice:** `name[entity-id]` — uniform inline syntax for all mentions including pronouns
**Alternatives:**
- `name{entity-id}` — curly braces, avoids Markdown collision but less natural
- `{name|entity-id}` — single token, harder to read in prose
- Separate annotation block for pronouns — two places to maintain
**Rationale:** One parser, one syntax. `He[pp] examined it[obj-7]` is slightly awkward but uniform. Authors get used to it. LLM-assisted annotation can produce this format. Parser strips brackets, computes offsets, generates standoff annotations.
**Trade-offs:** Prose readability in source YAML is reduced by bracket annotations. Acceptable — source YAML is not user-facing, rendered text is clean.
**Sources:** Issue #721 (hybrid authoring section)
**Exploration:** quick
**Status:** captured

## D15: Entity alias resolution

**Choice:** YAML-local entity registry mapping short aliases to canonical entity names
**Alternatives:**
- Direct MindMap node IDs — precise but unreadable UUIDs in YAML
- MindMap node names directly — verbose, no shorthand
**Rationale:** Each YAML file declares `entities: {pp: 'James Pond', obj-7: 'Guest Book'}`. Parser resolves aliases to canonical names, which then resolve to MindMap node IDs via store.resolveNode(). Keeps YAML self-contained and readable.
**Trade-offs:** Registry must be maintained alongside YAML content. Acceptable — it's a manifest, consistent with existing corpus patterns.
**Sources:** Issue #721, existing biography YAML structure
**Exploration:** quick
**Status:** captured

## D16: Text source identity scheme

**Choice:** Tagged union — `(sourceType: String, sourceId: String)` pair owned by annotation-api
**Alternatives:**
- Reuse NodeRef(scheme, id, qualifier) from mindmap-api — creates forbidden cross-module dependency (D12)
- URI scheme (e.g., `memory:abc123`, `mindmap:node-456`) — overengineered string parsing for a simple identity problem
- Untyped string ID — loses source-type information needed for scoped deletion (D5) and cross-source queries
**Rationale:** Annotations span multiple text sources: memories, MindMap node bodies, biography YAML, conversation turns. Each annotation needs to identify its source for two operations: querying by source ("all annotations on this memory") and scoped deletion ("delete all memory-source annotations for this tenant"). A simple (sourceType, sourceId) pair provides both. Source types are well-known strings: "memory", "mindmap-node", "biography", "conversation-turn". Source IDs are opaque — the annotation index stores and indexes them without resolving them. This follows the same opaque identifier convention as NodeRef but without the mindmap-api dependency.
**Trade-offs:** Adding new source types requires updating consumers that switch on sourceType. Acceptable — new text sources are infrequent and each requires integration work regardless.
**Sources:** NodeRef pattern, D2 (multiple text sources), D5 (scoped deletion), D12 (dependency boundary)
**Exploration:** quick — surfaced by R1-10 reviewer challenge
**Status:** captured

## D17: Annotation confidence model

**Choice:** Optional confidence score (0.0–1.0) per annotation, producer-assigned
**Alternatives:**
- No confidence — all annotations equally authoritative regardless of source
- Post-hoc calibration step — adds pipeline complexity for uncertain accuracy improvement
- Hardcoded heuristic (named=1.0, pronoun=0.7, implicit=0.5) — ignores context-specific ambiguity
**Rationale:** LLM-produced annotations have varying accuracy: named entity mentions are high-confidence, pronoun coreferences depend on antecedent ambiguity, implicit references are lowest. The LLM is the best judge of its own uncertainty for a given resolution. Authored YAML annotations (D1) default to 1.0 — human-authored annotations are correct by definition. Downstream consumers (salience, reflection, belief revision, ToM per D11) can weight annotations by confidence.
**Trade-offs:** Confidence scores are LLM-dependent and may not be well-calibrated. Acceptable — even approximate confidence is better than treating all annotations as equal. Consumers can ignore confidence if they prefer uniform treatment.
**Sources:** R1-06, R1-11 reviewer challenges, D4 (LLM production), D11 (cognitive integration)
**Exploration:** quick — surfaced by R1-11 reviewer challenge
**Status:** captured

## D18: Annotation correctability

**Choice:** Immutable — correction is delete + re-create
**Alternatives:**
- Mutable update path — adds complexity (optimistic locking, partial update semantics) for marginal benefit
- Versioned annotations — tracks correction history, over-engineered for the use case
**Rationale:** Annotations are lightweight standoff records. Re-extraction naturally produces fresh annotations with corrected links. An update path would require conflict resolution semantics (what if the original annotation was modified by merge repointing D6 between creation and correction?) that add complexity without benefit. Delete + re-create is atomic and idempotent.
**Trade-offs:** No correction history. Acceptable — annotations are derived data, not primary records. The source (extraction or YAML) is the authoritative record.
**Sources:** R1-11 reviewer challenge, platform event-sourcing patterns
**Exploration:** quick — surfaced by R1-11 reviewer challenge
**Status:** captured
