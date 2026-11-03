# Decisions — Cognitive Knowledge Management (#763 + #764)

## D1: Unified design for #763 and #764

**Choice:** Design both issues together as a single unified abstraction
**Alternatives:**
- Multi-session research first (#763) — validates garden factory + agent-authored entries, but risks designing retrieval that doesn't accommodate transcripts
- Autobiographical recall first (#764) — validates transcript indexing, but risks a transcript-specific design that doesn't generalise
**Rationale:** Both issues want the same thing: a searchable body of knowledge with a lifecycle. The difference is source (external vs internal), not the store/retrieve model. Designing together avoids two incompatible systems.
**Trade-offs:** Larger initial design scope; more decisions to make upfront before validating any single use case
**Sources:** casehubio/neocortex#763, casehubio/neocortex#764
**Exploration:** quick
**Status:** captured

## D2: Corpus as the core abstraction

**Choice:** A "corpus" is the first-class concept — a typed, searchable collection of knowledge with a lifecycle that an agent can create, populate, query, and evolve
**Alternatives:**
- Unified query surface over existing stores — keeps specialised stores, builds a single query API over them. Less disruptive but doesn't address creation/lifecycle
- Single canonical store — replaces the store zoo with one store. Radical simplification but high risk and doesn't respect that graph, vector, and event-stream access patterns are fundamentally different
**Rationale:** The agent shouldn't think about stores — it thinks about knowledge collections. "My research corpus," "my interaction history," "the team's knowledge garden." The corpus handles different document types through a uniform API. Underlying stores are implementation details.
**Trade-offs:** New abstraction layer; existing stores (MindMap, CaseMemoryStore, CbrRecordStore) remain separate — the corpus doesn't replace them, it's a new peer
**Sources:** casehubio/neocortex#763 (architecture section), Hortora garden engine
**Exploration:** quick
**Status:** captured

## D3: Typed corpora

**Choice:** Each corpus declares its document schema at creation — a research corpus holds papers and summaries, a transcript corpus holds interaction records, a knowledge-garden corpus holds curated entries
**Alternatives:**
- Mixed corpora — any document type in any corpus. Simpler creation but harder indexing and metadata extraction
- Typed with mixed allowed — primary type with secondary types. Flexible but blurs the schema boundary
**Rationale:** Different document types need different metadata extraction, different indexing strategies, and different cover document templates. Typing at the corpus level keeps the indexing pipeline clean. Cross-corpus search unifies at query time.
**Trade-offs:** Agent must choose a type at creation; cross-type documents require cross-corpus search rather than single-corpus containment
**Sources:** casehubio/neocortex#763 (use cases: research, transcript, domain-expert, investigation)
**Exploration:** quick
**Status:** captured

## D4: Corpus owns its Qdrant collection

**Choice:** Each corpus gets its own Qdrant collection. MindMap and CaseMemoryStore remain separate stores — the corpus is a new peer, not a replacement. Promotion from corpus to MindMap is explicit (like EntityPromoter today).
**Alternatives:**
- Corpus wraps existing stores — a view over MindMap/CaseMemoryStore/etc. Unifies query surface but adds indirection over everything
- Corpus is always Qdrant, other stores stay separate — similar to chosen approach but frames it as "always Qdrant" rather than "owns its collection"
**Rationale:** MindMap (graph), CaseMemoryStore (event stream), and CbrRecordStore (feature vectors) have fundamentally different data models. The corpus is vector-indexed document search — a distinct access pattern. Clean separation, explicit promotion.
**Trade-offs:** Knowledge exists in two places after promotion (corpus entry + MindMap node). Cross-store consistency is the agent's responsibility.
**Sources:** Hortora engine (garden = Qdrant collection), rag-api (CaseRetriever SPI)
**Exploration:** quick
**Status:** captured

## D5: Three-layer document model

**Choice:** Original artifact (native format: PDF, HTML, scan) + Cover document (garden entry format: markdown+YAML) + Index record (Qdrant vectors derived from cover)
**Alternatives:**
- Two-layer (original + index) — loses the working artifact that accumulates understanding
- Markdown-only (Hortora model) — doesn't handle external source material like PDFs
**Rationale:** Real corpora contain heterogeneous material. PDFs can't be cleanly converted to markdown (images, citations, math degrade). The cover document captures the agent's understanding of the material — summary, annotations, cross-references. The index is derived from the cover, so search is over the agent's understanding, not raw text. For curated knowledge (Hortora-style), the cover IS the knowledge — no separate original.
**Trade-offs:** More storage; extraction quality varies by document type; cover must be kept in sync as understanding evolves
**Sources:** Discussion of PDF/OCR handling, Hortora garden entry format
**Exploration:** quick
**Status:** captured

## D6: Uniform markdown+YAML cover format

**Choice:** Every cover document uses the Hortora garden entry format — markdown body with YAML frontmatter. Different corpus types have different required/optional frontmatter fields, but the base format is always the same.
**Alternatives:**
- Per-type structured Java records — more type-safe but loses human-readable trail and requires per-type serialization
- Markdown body + typed metadata — structured Java API with YAML persistence. Best of both but more complexity
**Rationale:** Hortora already has a proven, production-tested format. Single indexing pipeline, single rendering strategy, human-readable, git-friendly. Garden entries are already cover documents — no new format to invent.
**Trade-offs:** YAML frontmatter is loosely typed; validation must be explicit per corpus type
**Sources:** Hortora garden entry format, existing GardenMetadataExtractor
**Exploration:** quick
**Status:** captured

## D7: Single per-agent transcript corpus

**Choice:** One corpus per agent holds all interaction history. Labels and metadata make it queryable by project, time, interaction type, activity type. The corpus grows as a continuous autobiographical stream.
**Alternatives:**
- Scoped corpora (one per project/session) — clear boundaries but cross-project recall requires cross-corpus search
- Both continuous + scoped — a universal corpus plus project-scoped ones. More flexibility but more corpora to manage
**Rationale:** Mirrors autobiographical memory — one continuous stream, not segmented archives. Labels (interaction type, activity type, domain) provide the scoping. Staleness/retention handles cleanup within the single corpus.
**Trade-offs:** Single corpus grows indefinitely; needs retention policy and efficient filtering. No natural "close the project" boundary.
**Sources:** casehubio/neocortex#764 (lifetime scale, cross-project recall)
**Exploration:** quick
**Status:** captured

## D8: Both implicit and explicit corpus creation

**Choice:** Infrastructure corpora (interaction history) auto-created on agent lifecycle events. Intentional corpora (research, domain gardens) created via LLM tool calls. Same underlying API, different trigger. Agents may also proactively create corpora based on curiosity/interest patterns (anticipatory creation).
**Alternatives:**
- Only explicit creation — simpler but requires the agent to remember to create infrastructure corpora
- Only implicit — system decides what corpora exist. Removes agency from knowledge management.
**Rationale:** Some corpora are infrastructure (transcripts should just exist). Others are intentional acts of knowledge management. Anticipatory creation connects to the curiosity drive — an agent noticing an emerging interest and proactively setting up structure to capture it.
**Trade-offs:** Implicit creation requires well-defined lifecycle events; anticipatory creation needs heuristics to avoid corpus proliferation
**Sources:** casehubio/neocortex#764 (auto-created transcript), CuriositySignalGenerator (anticipatory)
**Exploration:** quick
**Status:** captured

## D9: Soft archive lifecycle

**Choice:** Archived corpora stop accepting new entries and drop out of default cross-corpus search, but remain queryable on explicit request. Qdrant collection stays, excluded from federated search unless the query specifically targets it.
**Alternatives:**
- Hard archive with compaction — compact to summary, delete Qdrant collection, keep only summary + originals. Saves resources but loses granular search
- No archival — corpora live forever with retention policy cleanup. Simplest but Qdrant collections accumulate
**Rationale:** Cheap to keep, easy to revive. Research from a closed project might become relevant again years later. Soft archive preserves the option without polluting default search.
**Trade-offs:** Qdrant resource usage grows over time (collection count + storage). May need periodic compaction for truly dead corpora.
**Sources:** Hortora federation (searchOrder: always/default), CbrRetentionPolicy pattern
**Exploration:** quick
**Status:** captured

## D10: RRF fusion for cross-corpus search

**Choice:** Cross-corpus search uses Reciprocal Rank Fusion to merge results from multiple corpora into a single ranked list. Per-corpus weight configuration. Cognitive modulation (mood, goals, recency) applies as a post-fusion scoring pass via CognitiveMemoryRetriever.
**Alternatives:**
- Sequential with priority — search corpora in order, stop when enough found. Faster but may miss relevant results in lower-priority corpora
- Per-corpus presentation — no fusion, results grouped by corpus. Consumer decides weighting. Transparent but pushes ranking burden to the consumer.
**Rationale:** RRF is proven (already in fusion-api), handles heterogeneous score distributions across corpora well. Per-corpus weights allow tuning (e.g., active research corpus weighted higher than archived ones). Cognitive modulation post-fusion applies the agent's current cognitive state to the unified result set.
**Trade-offs:** RRF position-based ranking may under-weight highly relevant results in a low-priority corpus
**Sources:** fusion-api (ScoreFusion), CognitiveMemoryRetriever (#750)
**Exploration:** quick
**Status:** captured

## D11: Extend CognitiveMemoryRetriever for corpus modulation

**Choice:** Extend the existing CognitiveMemoryRetriever (#750) to accept corpus search results alongside memory results. One modulation pipeline for all knowledge retrieval.
**Alternatives:**
- Corpus-specific modulation — independent wiring using same ModulationFactor interface. Decoupled from tick lifecycle but two parallel modulation paths
- Standalone + tick-integrated — corpus search works standalone, CognitiveMemoryRetriever wraps it during ticks. More flexible but more integration surface.
**Rationale:** CognitiveMemoryRetriever already has composable ModulationFactors (recency, confidence, mood congruence, goal relevance). Corpus search results benefit from the same modulation. Single pipeline is simpler to reason about and test.
**Trade-offs:** Corpus module gains a dependency on cognitive-index (where CognitiveMemoryRetriever lives). Corpus queries outside of ticks still need a modulation context.
**Sources:** CognitiveMemoryRetriever (#750), ModulationFactor (cognitive-api)
**Exploration:** quick
**Status:** captured

## D12: Corpus catalogue

**Choice:** A registry of all corpora per agent/tenant. Tracks what corpora exist, their type, status, scope, federation config (upstream/peer references), and how to reach them (Qdrant collection name). Cross-corpus search queries the catalogue to discover which corpora to include.
**Alternatives:** None considered — the need for a catalogue emerged naturally from the design. Without it, there's no way to discover what corpora exist or which to include in federated search.
**Rationale:** Agents need to browse, manage, and search across their knowledge collections. Cross-corpus search needs to discover which corpora to include. The catalogue is the integration point.
**Trade-offs:** Another piece of persistent state to manage (catalogue must be durable and consistent with actual Qdrant collections)
**Sources:** DomainRegistry (knowledge-pipeline), Hortora FederationConfig
**Exploration:** quick
**Status:** captured

## D13: Hortora engine fully absorbed into neocortex

**Choice:** Hortora's engine capabilities migrate entirely into corpus-management as universal behaviors for all corpus types: adaptive search, federation, provenance, staleness, feedback, reindexing. corpus-management IS the garden engine. Hortora the product becomes neocortex deployed and configured for its Java/tech domains — 100% neocortex, zero engine-specific code.
**Alternatives:**
- Hortora stays separate, corpus delegates to it — two parallel systems, more maintenance
- Partial migration — extract some capabilities, leave others in engine. Extended period of overlap
**Rationale:** We control both repos. Hortora's engine is already a thin layer over neocortex RAG SPIs. Every capability it provides (adaptive search, provenance, staleness, feedback, federation) is generic — not domain-specific. Moving everything into neocortex means one codebase, one test suite, one evolution path. Hortora becomes a deployment configuration, not a codebase.
**Trade-offs:** Larger neocortex; Hortora development becomes neocortex development; MCP tool surface needs to be configurable per deployment
**Sources:** Hortora engine architecture, neocortex #304 (garden platform extraction)
**Exploration:** quick
**Status:** captured

## D14: Full four-level hierarchy from day one

**Choice:** The corpus abstraction supports Hortora's four-level knowledge hierarchy (canonical → community → platform → product) from the start, with upstream/peer federation built into the SPI.
**Alternatives:**
- Design for hierarchy, implement flat first — SPI accommodates it but V1 is flat. Avoids complexity but risks design gaps
- Flat only — hierarchy stays in Hortora. Simplest but blocks the Hortora migration
**Rationale:** Hortora already provides the working template. The hierarchy model is proven. Building it from the start avoids a migration from flat to hierarchical later.
**Trade-offs:** More complex SPI; hierarchy semantics (augment vs override) must be defined precisely upfront
**Depends on:** D13 (Hortora becomes a corpus type)
**Sources:** Hortora four-level methodology, ChainWalker federation
**Exploration:** quick
**Status:** captured

## D15: Corpus federation with upstream and peer edges

**Choice:** Every corpus is a node in a federation graph. Each corpus can have 0..n upstream sources (parent chain — inherited knowledge, sequential walk) and 0..n peer sources (sibling corpora — federated parallel fan-out). A searching client composes its search scope from 1..n sources.
**Alternatives:** None considered separately — this is the Hortora ChainWalker model generalised to all corpus types.
**Rationale:** Distributed knowledge collaboration requires that corpora can reference and search each other. The upstream/peer distinction captures the semantic difference between inherited knowledge (parent knows best unless overridden) and collaborative knowledge (peers contribute equally).
**Trade-offs:** Federation graph can become complex; cycle prevention required; latency grows with chain depth
**Depends on:** D14 (full hierarchy)
**Sources:** Hortora ChainWalker, FederationConfig (upstream refs, peer refs, visited set)
**Exploration:** quick
**Status:** captured

## D16: New corpus-management module pair

**Choice:** New module pair: corpus-management-api (SPIs: CorpusManager, CorpusCatalogue, CorpusEntry, CorpusQuery, CorpusType, federation types) + corpus-management (impl: Qdrant wiring, cover document handling, cross-corpus search, catalogue persistence, artifact storage bridge)
**Alternatives:**
- Extend existing corpus-api — muddies the boundary (corpus-api is currently a zero-deps binary archive module)
- Inside knowledge-pipeline — reuses domain dispatch but knowledge-pipeline is connector-focused, not document-focused
**Rationale:** Clean SPI boundary. Agents depend on corpus-management-api, not on Qdrant or RAG internals. The existing corpus-api (ZIP archives) continues to serve as the artifact storage layer — corpus-management-api depends on it for original artifact persistence.
**Trade-offs:** Two new Maven modules; another API surface to maintain and document
**Sources:** Module structure patterns in neocortex (rag-api/rag, memory-api/memory, mindmap-api/mindmap)
**Exploration:** quick
**Status:** captured

## D17: Recovery — move Hortora's mature code instead of keeping reimplementations

**Choice:** Delete the reimplementations in corpus-management and IntelliJ-move Hortora's actual 9-month-mature engine code into corpus-management. Generify during the move. Hortora engine becomes a thin deployment layer (MCP tools, REST, config, CDI producers). Hortora's 22 test files remain in Hortora and validate the migration by proving functionality is preserved.
**Alternatives:**
- Keep reimplementations and wire Hortora on top — less disruption but the mature code stays locked in Hortora instead of being universally reusable, and the reimplementations lack 9 months of edge-case hardening
- Scrap and redo from scratch — cleanest git history but loses genuinely new code (transcript covers, cognitive integration) and wastes already-committed work
**Rationale:** The original plan explicitly specified IntelliJ migration to preserve code maturity. The previous session deviated by rewriting from scratch. Moving the actual code preserves all edge cases, error handling, and production-learned refinements. Hortora's test suite is the proof the migration works.
**Trade-offs:** More complex migration (type adaptation needed); git history shows delete+move rather than clean moves
**Sources:** Hortora engine (34 source files, 22 test files), gap audit showing 5 partial/5 missing reimplementations
**Exploration:** quick
**Status:** captured

## D18: CorpusApi lives in corpus-management module

**Choice:** Add `CorpusApi` interface directly to the `corpus-management` module
**Alternatives:**
- New `corpus-management-core` module (parallel to cognitive-observability-core) — cleaner separation but adds a Maven module for one interface + implementation bean
- `corpus-management-api` — clean contract but adds platform-api dependency to the zero-dep SPI module
**Rationale:** corpus-management already depends on `casehub-platform-api` and contains all services that CorpusApi delegates to. No new module overhead. The interface and its implementation bean live with their dependencies.
**Trade-offs:** The impl module gains a framework annotation; less separation than the cognitive-observability model
**Depends on:** D16 (corpus-management module pair)
**Sources:** CognitionApi in cognitive-observability-core (pattern reference), corpus-management/pom.xml
**Exploration:** quick
**Status:** captured

## D19: New CorpusIndexService for RAG-layer operations

**Choice:** Create a `CorpusIndexService` for index-level operations (status, delete, reindex-single, unretrieved). Feedback recording expands ProvenanceStore.
**Alternatives:**
- Expand existing services — add status() to GardenReindexService, delete/reindex to CorpusEntryStore, etc. No new class but responsibilities blur.
- Keep orchestration in CorpusApi implementation bean — simpler but the API bean becomes a fat controller with RAG SPI dependencies
**Rationale:** Clean separation: SearchResource handles queries, CorpusIndexService handles index management, ProvenanceStore handles lineage + feedback. Each service has a single concern. The CorpusApi implementation bean is a thin delegator.
**Trade-offs:** One new service class; CorpusIndexService depends on RAG SPIs (EmbeddingIngestor, RetrievalTracker, RetrievalAnalyzer, MetadataExtractor)
**Depends on:** D18 (CorpusApi in corpus-management)
**Sources:** GardenMcpTools (operations that directly call RAG SPIs), rag-api SPIs
**Exploration:** quick
**Status:** captured

## D20: CorpusApi operation surface — 19 operations (11 query, 8 mutation)

**Choice:** 19 operations mapping all Hortora endpoints: search, adaptiveSearch, entry, profile, profiles, status, unretrieved, forwardLineage, reverseLineage, provenanceStats, outcomeReport (queries); reindex, reindexEntry, deleteEntry, saveProfile, deleteProfile, recordOutcome, recordProvenance, recordFeedback (mutations). Generic parameter names (corpusId replaces gardenId, entryId replaces geId).
**Alternatives:**
- Minimal surface (search + CRUD only) — fewer operations but loses provenance, outcomes, feedback, and index management that are essential for knowledge lifecycle
- Hortora-specific naming — preserves "garden" terminology but breaks the generic corpus abstraction from D2/D13
**Rationale:** One-to-one mapping ensures zero capability loss during migration. Generic naming (corpus/entry vs garden/GE) follows D13's decision that Hortora becomes a corpus deployment. Delegation targets are clear: SearchResource, CorpusIndexService (new), SearchProfileStore, ProvenanceStore, CorpusOutcomeService, GardenReindexService.
**Trade-offs:** 19 operations is a larger API surface than CognitionApi's 11, but corpus management genuinely has more operations (CRUD + search + lifecycle + lineage + feedback)
**Depends on:** D18 (module placement), D19 (CorpusIndexService for RAG-layer ops)
**Sources:** Hortora GardenMcpTools (10 MCP tools), SearchEndpoint, EntryResource, ProfileResource, ReindexResource, OutcomeResource, ProvenanceResource
**Exploration:** quick
**Status:** captured
