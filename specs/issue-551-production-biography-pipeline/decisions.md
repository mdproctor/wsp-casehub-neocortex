## D1: Goal taxonomy fields — extend GoalEntry

**Choice:** Add first-class fields to GoalEntry for all 10 taxonomy fields (status, urgency, need_tier, priority, feasibility, content_domain, content_subdomain, motivation_origin, clarity, evidence_basis). GoalHandler stores them as node properties.
**Alternatives:**
- Pack into properties map — no Java changes but loses type safety, relies on convention
- Tier-split (first-class for vocabulary-validated, properties for numeric) — unnecessary complexity when GoalHandler stores everything as properties anyway
**Rationale:** Type safety at compile time. GoalVocabulary already defines valid values for content_domain, content_subdomain, and motivation_origin. First-class fields enable validation in BiographyLoader or GoalHandler.
**Trade-offs:** More fields on GoalEntry record. But these are stable taxonomy fields from the goal motivation model (#528) — not speculative additions.
**Sources:** GoalEntry.java, GoalHandler.java, GoalVocabulary.java, verify_schema.yaml
**Exploration:** quick
**Status:** captured

## D2: Entity enrichments and disposition — new handler types

**Choice:** Add 'entity-enrichment' and 'disposition-profile' as new BiographyTemplateTypes at layer 7 (after goals/beliefs at 6, before current-state at 8). New handlers write to CognitiveDefaults YAML and CAPS state.
**Alternatives:**
- Extend existing handlers — merge drive baselines into RelationshipEntry, CAPS into CurrentStateEntry. Conflates distinct concerns.
- Separate import path — converter writes cognitive-profiles/*.yaml directly bypassing BiographyHandler. Breaks the single-import-runner pattern.
**Rationale:** Entity enrichments are conceptually distinct from any existing entry type. They represent synthesised meta-knowledge about entities (drive baselines, CAPS patterns, behavioural attractors). Layer 7 ensures all referenced entities exist before enrichment data is applied.
**Trade-offs:** Two new handlers and entry types. But the handler-per-concern pattern is already established and these are genuinely new concerns.
**Sources:** corpus.json entity_enrichments structure, CognitiveDefaultsRegistry, CapsEngine
**Exploration:** quick
**Status:** captured

## D3: Edge mapping — universal associations field

**Choice:** Add an optional `associations` list (entity_ref + edge_type + optional confidence) to every entry type that writes to MindMapStore. The converter maps edges through per-type specific fields first (GoalEntry.dependencies, ActivityEntry.participants, PlaceEntry.associations), then falls back to universal associations for remaining edges.
**Alternatives:**
- Dedicated edges.yaml file — clean separation but adds another handler and breaks the "edges belong to entities" mental model
- Entry-specific only — accepts edge loss for edges that don't fit built-in fields. The 1570 edges include many "contributes-to" (1172) that must be preserved.
**Rationale:** Most edges can be attributed to a source or target entity. Universal associations on entries keep edges co-located with the entity they belong to. The converter assigns each edge to the source entity's entry.
**Trade-offs:** Every node entry type gets an extra optional field. But `@JsonIgnoreProperties(ignoreUnknown = true)` means existing YAML without the field still works.
**Sources:** corpus.json edges structure, PlaceEntry.associations pattern, GoalEntry.dependencies pattern
**Exploration:** quick
**Status:** captured

## D4: Converter location — extraction/scripts/

**Choice:** Place `convert_corpus.py` in `neocortex/extraction/scripts/` alongside the rest of the pipeline (assemble_corpus.py, verify_corpus.py).
**Alternatives:**
- Java in memory-seeding module — stronger type coupling but mismatched language with the Python pipeline
- Standalone tool — unnecessary isolation for a single script
**Rationale:** The converter is the next pipeline step after verify. Same Python environment, same data format (reads corpus.json, writes YAML). Keeping it with the pipeline maintains the single `run_pipeline.sh` orchestration.
**Trade-offs:** Python script must track Java record changes. But verify_schema.yaml already bridges this — the converter reads the same schema.
**Sources:** extraction/scripts/ directory structure, run_pipeline.sh
**Exploration:** quick
**Status:** captured

## D5: Organisation nodes — new OrganisationHandler

**Choice:** Add 'organisation' as a new BiographyTemplateType at layer 4 (peer with place/activity/project). New OrganisationHandler writes to ORGANISATION subgraph.
**Alternatives:**
- Map to project entries — organisations are project-like but lose ORGANISATION subgraph semantics
- Map to cultural-context — some organisations provide cultural context, but this misrepresents their graph role
**Rationale:** Follows the handler-per-subgraph pattern. SubgraphTypes already defines ORGANISATION. The handler is straightforward — name, properties, traits, PAD, associations.
**Trade-offs:** One more handler and entry type. Minimal — the pattern is well-established.
**Sources:** SubgraphTypes.ORGANISATION, corpus node subgraph_types, OrganisationalTraitRule
**Exploration:** quick
**Status:** captured

## D6: Memory enrichment fields — extend LifeEventEntry

**Choice:** Add enrichment fields (occ_emotions, sec_appraisal, action_tendencies, cognitive_distortions, drive_impact, caps_inputs, goal_impacts, habituation, gut_feeling) to LifeEventEntry. LifeEventHandler stores them as memory attributes alongside existing sub_thoughts.
**Alternatives:**
- Post-import enrichment — import basic memories then enrich via CaseMemoryStore.enrichAttributes(). Adds a pipeline step and requires memory ID tracking.
- Enrichment overlay file — two files per type. Clean separation but unnecessary complexity.
**Rationale:** Sub-thoughts are already first-class on LifeEventEntry with attribute-based storage. The enrichment fields follow the same pattern — they're per-memory cognitive annotations stored as attributes. One entry, one handler call, one atomic store operation.
**Trade-offs:** LifeEventEntry becomes larger. But all fields are optional and `@JsonIgnoreProperties` handles existing YAML gracefully.
**Sources:** LifeEventEntry.java, LifeEventHandler.java, SubThoughtAttributeKeys pattern, corpus memory enrichment fields
**Exploration:** quick
**Status:** captured

## D7: Per-corpus config — reuse verify_schema.yaml

**Choice:** The converter reads verify_schema.yaml for entity aliases, vocabulary values, and field mappings. One source of truth for the verification-conversion-import chain.
**Alternatives:**
- Separate converter-config.yaml — duplicates alias/vocabulary data, two files to maintain
- Inline in corpus.json — couples config to data, changes corpus format
**Rationale:** verify_schema.yaml already encodes the Java-side contract (field mappings, valid vocabularies, entity aliases). The converter needs exactly the same information to produce valid YAML. Adding a 'converter' section to the schema keeps configuration co-located.
**Trade-offs:** verify_schema.yaml grows slightly. But it's already the contract bridge between Python and Java.
**Sources:** verify_schema.yaml, verify_corpus.py, D4 (converter location)
**Depends on:** D4 (converter reads schema from same directory)
**Exploration:** quick
**Status:** captured
