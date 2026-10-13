# Design Decisions — #470 Sub-Thought Representation & Biographical Import

## D1: Sub-thought representation model

**Choice:** Structured sections within Memory records, with optional MindMap node attachment for richer data
**Alternatives:**
- Full MindMap nodes for every sub-thought — fully queryable but causes graph pollution (5-10 nodes per check-in, distorted centrality, consolidation noise)
- Separate Memory records with parent-memory-id — queryable with per-sub-thought PAD, but 5-10x storage explosion per check-in
- Lightweight MindMap node type — doesn't exist, would require deep cross-cutting changes to MindMapNode interface, all stores, all consolidation phases, all renderers
**Rationale:** "Memories are for what was experienced. MindMap nodes are for what was learned." Sub-thoughts are raw cognitive reactions — they belong in the memory layer as structured sections. When a section needs richer data (PAD, edges, traits), an optional MindMap node attaches to it via NodeRef(scheme="sub-thought", id=memoryId, qualifier=subThoughtIndex). A new `SubThoughtConsolidationPhase` (`@Priority(16)`) uses persistent accumulation to detect (entity, type) patterns across check-ins and graduates significant sub-thought groups to full MindMap nodes. The node only exists when earned.
**Trade-offs:** Per-sub-thought PAD is not available at the memory level — only when a node is attached. FTS finds text but sub-thought-type filtering requires attribute parsing. Cross-store linking via NodeRef is a convention, not enforced referential integrity.
**Sources:** MindMapNode interface (20 fields, no lightweight variant), NodeRef(scheme, id, qualifier), SubThoughtConsolidationPhase (@Priority(16)) graduation pathway, research spec §15.5 fragment-addressable headings
**Exploration:** deep-analysis
**Status:** captured

## D2: Sub-thought storage location within Memory record

**Choice:** Memory attributes — sub-thoughts stored as indexed key-value pairs in the existing `Map<String, String> attributes` field
**Alternatives:**
- Bracketed headings in text field (`[type] content`) — simpler to read but contaminates FTS (searching "intention" matches the label `[intention]`), false-positive risk from natural language brackets, multi-line delimiter unresolved
- Dedicated `List<MemorySection>` field — type-safe but requires schema change across all 6 store backends
- YAML-like key-value in text — machine-parseable but less natural for free text
**Rationale:** Memory attributes are the established pattern for structured metadata — ExperienceAttributeKeys, MoodAttributeKeys, EngagementAttributeKeys, RelationshipAttributeKeys all use this. Machine-parseable without regex, doesn't contaminate FTS, no false-positive risk. Memory text stays as pure parent description ("Lunch with Sarah at La Trattoria"). Attribute convention: `sub-thought-N-type`, `sub-thought-N-text`, optional `sub-thought-N-entity`. SubThoughtAttributeKeys constants class provides the key patterns.
**Trade-offs:** More verbose than text-embedded sections. Attribute map grows with sub-thought count. Rendering requires assembling from attributes rather than parsing text. Not human-readable in raw attribute dumps the way bracketed text is.
**Sources:** ExperienceAttributeKeys.java, MoodAttributeKeys, decision review R1-02 (FTS contamination, false-positive risk)
**Exploration:** quick
**Status:** revised (was: bracketed headings in text field)

## D3: Thought-type taxonomy

**Choice:** 7 types from issue proposal — affect-observation, causal-inference, evaluative, intention, self-reflection, association, concern
**Alternatives:**
- Expanded set (add memory, anticipation, regret, gratitude) — more granular but risks over-classification of early thoughts
- Minimal 4-type set (observation, inference, evaluation, intention) — too coarse, loses cognitive distinction between e.g. self-reflection and causal-inference
**Rationale:** Covers the cognitive reaction space without over-splitting. Extensible via new constants — follows the SubgraphTypes pattern (string constants, not enum, but with a known set for consumers to match against). SubThoughtTypes constants class provides the 7 values + a validation method for ingestion-time checking.
**Trade-offs:** Fixed taxonomy may not capture all cognitive reaction types. New types require adding a constant (intentional friction to prevent drift).
**Sources:** Issue #470 body, research spec §15.5 section heading types, SubgraphTypes pattern, decision review R1-04 (type drift risk)
**Exploration:** quick
**Depends on:** D2 (attribute key convention determines how types are stored)
**Status:** revised (was: extensible by convention with no validation)

## D4: Biographical template loading approach

**Choice:** New BiographyLoader with per-type Java records — purpose-built for biographical templates
**Alternatives:**
- Extend CatalogueLoader with TemplateType discriminator — CatalogueLoader only shares ~15 lines of directory listing + ObjectMapper.readValue(); CatalogueEntry's 11 fields are specific to formative psychological patterns and share nothing with biographical templates
- Unified biography document (one large YAML) — simpler to author but harder to validate per-section
**Rationale:** The backstory catalogue models psychological formative experiences (Bowlby, Bandura, CBT). Biographical import models factual life data (places, people, events, goals). These are fundamentally different domains — coupling via shared loader creates a forced dependency where neither benefits from the other's validation rules. BiographyLoader provides its own YAML loading, per-type Jackson deserialization, ID uniqueness, and cross-reference validation.
**Trade-offs:** Two loader classes in memory-seeding. The catalogue directory can still hold both YAML families — physical organization is independent of code architecture.
**Sources:** CatalogueLoader.java (shared code is ~15 lines), decision review R1-03
**Exploration:** quick
**Status:** revised (was: extend CatalogueLoader)

## D5: Layer model enforcement

**Choice:** Layer derived from template type with per-entry confidence override
**Alternatives:**
- Explicit layer field on every template YAML — redundant since the mapping is fixed (Places→4, Relationships→5, Goals→6, etc.)
- No layer enforcement — risks forward references and incorrect confidence origins
**Rationale:** The template type determines the layer (fixed mapping). A per-type default confidence origin is more accurate than per-layer — "She was born in Coyoacán" (STATED) and "She felt betrayal about her father's absence" (INFERRED) can occur in the same template type. Each entry can override confidence origin. Import orchestrator validates entity dependencies: layer N entries can reference entities from layer <N.
**Trade-offs:** If a new template type genuinely spans layers, the mapping needs updating. Override mechanism adds complexity to validation.
**Depends on:** D4 (template type definition)
**Sources:** Issue #470 layer table, research spec §15.1-15.4, decision review R1-06
**Exploration:** quick
**Status:** revised (was: explicit layer field)

## D6: Demo dataset scope

**Choice:** Design includes example schema snippets only — the Frida Kahlo dataset is a separate deliverable
**Alternatives:**
- Full biography as part of spec — proves schema end-to-end but substantial content effort in design phase
- Schema + one fully worked template type — partial validation
**Rationale:** The spec defines the YAML schema for all 9 template types with small illustrative snippets. A complete biography requires research into Frida Kahlo's life and careful emotional/relational modeling — that's implementation work, not design work.
**Trade-offs:** Schema may have gaps that only surface when writing a full biography. Mitigated by the illustrative snippets covering edge cases.
**Sources:** blocks-ui#231 (workbench spec, Frida Kahlo demo)
**Exploration:** quick
**Status:** captured

## D7: Import orchestration architecture

**Choice:** BiographyImportRunner with BiographyHandler registry — runner owns ordering and validation, handlers own per-type store interactions
**Alternatives:**
- Single BiographyOrchestrator dispatching to all stores — becomes a God class that grows with each template type; its own mitigation ("dispatch to strategy objects") is this approach
- Extend BackstorySeeder — keeps one class but grows large and mixes concerns
**Rationale:** Runner reads templates via BiographyLoader (D4), sorts by derived layer (D5), validates cross-layer entity references (load-time validated references only; handler-resolved references are resolved at execution time via `resolveOrCreate`), then iterates through `List<BiographyHandler>` (CDI-injected, sorted by priority). Each handler declares which template types it handles. `FormativeExperienceHandler` wraps `BackstorySeeder` for layer 2, converting template entries to `BackstoryProfile.CatalogueSelection` references. New template types require new handler classes, not modifications to the runner. Single point of control for ordering/validation without the runner knowing handler internals.
**Trade-offs:** More classes than a monolithic orchestrator. Handler registration pattern requires CDI wiring.
**Depends on:** D4 (template loading approach), D5 (layer model)
**Sources:** BackstorySeeder.java, decision review R1-05 (God class critique)
**Exploration:** quick
**Status:** revised (was: single BiographyOrchestrator)

## D8: Sub-thought creation ownership

**Choice:** LLM extraction at check-in time — async enrichment following the existing ExtractionRequested pattern
**Alternatives:**
- CheckInRequest accepts structured sub-thoughts — more deterministic but pushes cognitive decomposition onto the caller
- Both structured input + LLM fallback — most flexible but two code paths to maintain
**Rationale:** CheckInService captures the parent experience as a Memory record with text description. A new async observer (like ExtractionRequestedObserver) receives the check-in event, invokes an LLM to decompose the experience text into typed sub-thoughts (using the D3 taxonomy), and writes them as attributes (D2) back to the Memory record via CaseMemoryStore update. Follows the established ConversationBridge → ExtractionRequested → ExtractionRequestedObserver pattern.
**Trade-offs:** LLM latency — sub-thoughts aren't available immediately after check-in. The Memory record is updated asynchronously, which means consumers reading it immediately see only the parent text. NodeRef qualifiers (D1) can only be created after extraction completes.
**Depends on:** D1 (representation model), D2 (attribute storage), D3 (type taxonomy)
**Sources:** ConversationBridge.java, ExtractionRequestedObserver, decision review R1-10
**Exploration:** quick
**Status:** captured
