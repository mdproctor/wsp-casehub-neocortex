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
**Sources:** Memory.java, MindMapNode.java, NodeRef.java, first-principles analysis of query directions
**Exploration:** deep-analysis
**Status:** captured

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

**Choice:** Extend MindMapExtractor output to include span offsets
**Alternatives:**
- Separate annotation pass — double the LLM cost, cleaner separation
- Inline YAML anchors only — only works for named mentions, not pronouns
**Rationale:** MindMapExtractor already processes text and identifies entities. The LLM already knows where entities appear — asking it to report character offsets is a prompt extension, not a new capability. No additional LLM call.
**Trade-offs:** Couples annotation production to extraction. If extraction fails, annotations fail too. Acceptable — annotations without extracted entities are meaningless anyway.
**Sources:** MindMapExtractor.java (parse/apply split), ParsedExtraction.java, ParsedEntity.java
**Exploration:** quick
**Status:** captured

## D5: Memory lifecycle handling

**Choice:** CDI event observer on MemoryEntityErased
**Alternatives:**
- Decorator on CaseMemoryStore — tighter coupling, atomic but Memory shouldn't know about annotations
- Periodic reconciliation — eventually consistent, allows stale data to linger
**Rationale:** MemoryEntityErased CDI events already fire on erase. Decoupled — annotation index is optional, Memory doesn't know about it. Consistent with existing CDI event patterns across neocortex.
**Trade-offs:** Small window where annotations reference a deleted memory. Acceptable — no consumer will find the memory to render against.
**Sources:** MemoryEntityErased sealed interface, CaseMemoryStore SPI
**Exploration:** quick
**Status:** captured

## D6: Merge handling

**Choice:** CDI event observer on merge (repoint removeNodeId → keepNodeId)
**Alternatives:**
- MindMapStore decorator — atomic but tighter coupling
- Both decorator + event — belt-and-suspenders, over-engineered
**Rationale:** Rename is safe (node ID unchanged). Only merge retires a node ID. CDI event observer repoints annotations from removed node to surviving node. Decoupled and testable.
**Trade-offs:** Small window where annotations reference a retired node. Needs strong TDD — merge + annotation repointing is correctness-critical. Contract tests must cover: merge repoints, merge with duplicate spans (same entity mentioned via both merged nodes), merge cascade.
**Sources:** MindMapStore.mergeNodes(), MergeResult.java
**Exploration:** quick
**Status:** captured

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
**Rationale:** Annotations bridge text and graph — orthogonal to both. Follows existing Tier 1 module patterns (fusion-api, corpus-api, thing-api). SPI + value types in annotation-api. SQLite impl in annotation-sqlite. In-memory in annotation-inmem. Contract tests in annotation-testing.
**Trade-offs:** More modules. Acceptable — clean boundaries pay for themselves in test isolation.
**Sources:** fusion-api, corpus-api, thing-api module patterns
**Exploration:** quick
**Status:** captured

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
