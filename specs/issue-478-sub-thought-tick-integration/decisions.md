## D1: SubThoughtTickParticipant phase placement

**Choice:** FOUNDATION phase (custom participant, runs after mood + memory hygiene)
**Alternatives:**
- DERIVED phase (as issue originally proposed) — modeled on AppraisalTickParticipant, but sub-thought extraction has no dependency on cognitive state computed in earlier phases, so DERIVED causes a one-tick lag for all high-value consumers (mental model, drives)
- Pre-phase hook on CognitionCore — clean but over-engineered for one use case, adds a new concept to the tick lifecycle
- CognitionTickContext field expansion — couples the context record to sub-thought infrastructure, changes API for all participants
**Rationale:** Sub-thought extraction is input parsing (text → typed structure), not cognitive evaluation. It depends only on observation text + entity names, not on mood/drives/mental model. FOUNDATION placement makes sub-thoughts available to ALL downstream phases in the same tick: mental model (subject loop), drives (DERIVED), CAPS, prompt rendering. Uses existing extension mechanism (CognitionTickParticipant + per-agent ConcurrentHashMap + accessor).
**Trade-offs:** Slightly stretches the semantic meaning of "FOUNDATION" (baseline state establishment vs input decomposition). FOUNDATION custom participants run after mood/hygiene, so sub-thoughts can't inform mood baseline — acceptable since mood doesn't consume sub-thoughts.
**Sources:** CognitionCore.java tick lifecycle, AppraisalTickParticipant.java (DERIVED reference pattern), CognitionTickParticipant.java SPI, issue #478 architecture diagram
**Exploration:** deep-analysis
**Status:** captured

## D2: DriveSource design for sub-thought modulation

**Choice:** Four separate DriveSource classes — SubThoughtAffiliationDrive, SubThoughtCompetenceDrive, SubThoughtCuriosityDrive, SubThoughtAutonomyDrive
**Alternatives:**
- One parameterized class registered 4 times — less duplication but breaks CDI discovery pattern, requires manual registration in CognitionCore
- One class returning multiple intensities — requires changing DriveSource SPI to return List<DriveIntensity>, API change with no other motivation
**Rationale:** Follows established pattern (CuriosityDrive, CompetenceDrive, etc.). Each class is small (~20 lines of mapping logic), independently testable, CDI-discoverable. The shared element (participant accessor reference) is injected, not duplicated.
**Trade-offs:** Four classes where one could suffice. Acceptable because each has distinct mapping logic and the pattern is established.
**Sources:** DriveSource.java SPI, CuriosityDrive.java pattern, issue #478 drive mapping table
**Exploration:** quick
**Depends on:** D1 (FOUNDATION phase placement — drives read from participant accessor populated in FOUNDATION)
**Status:** captured

## D3: Mental model bridge mechanism

**Choice:** New MentalStateSignal variant — SubThoughtCue(type, text, entity, confidence) routed through existing signal pipeline
**Alternatives:**
- Direct BDI upsert — bypasses signal pipeline, creates parallel update path that doesn't interact with heuristic/LLM gating, risk of overwrite conflicts
- Replace LLM inference entirely — premature; rule-based extraction won't match LLM quality until async LLM extraction path is proven
**Rationale:** Routes through existing infrastructure (signal buffer, subject loop processing, heuristic extraction mapping). Naturally reduces redundant LLM calls — more sub-thought signals populate BDI before the LLM inference threshold is reached. Additive and safe — poor sub-thought extraction quality degrades gracefully.
**Trade-offs:** Adds a new signal variant to MentalStateSignal sealed hierarchy. The type → BDI mapping is a second heuristic path alongside VerbalCue, but the mapping tables are distinct (sub-thought types vs verbal cue types).
**Sources:** MentalModelOrchestrator.java (extractHeuristic, invokeLlmInference, record()), MentalStateSignal sealed hierarchy, issue #478 BDI mapping table
**Exploration:** quick
**Depends on:** D1 (sub-thoughts available in FOUNDATION, pushed to MentalModelOrchestrator buffer before subject loop)
**Status:** captured

## D4: CAPS integration approach

**Choice:** SituationClassifier @Decorator — intercepts classify(), runs keyword-based delegate, adds sub-thought-derived activations, returns merged result
**Alternatives:**
- Separate signal pathway — SubThoughtTickParticipant stores activations directly, BehavioralSynthesisPhase merges two sources; breaks single-source abstraction, requires consolidation phase to know about dual activation sources
**Rationale:** Transparent to consumers — BehavioralSynthesisPhase calls classify() and gets combined activations without knowing about the second signal source. Follows established CDI decorator pattern. During tick, reads from participant accessor; during consolidation, reads sub-thought attributes from the memory being classified. Classpath + config activated.
**Trade-offs:** Decorator must handle two contexts (tick-time via accessor, consolidation-time via memory attributes). Acceptable — the read source is a simple conditional on whether tick state is populated.
**Sources:** SituationClassifier.java SPI, RuleBasedSituationClassifier.java (keyword pattern), BehavioralSynthesisPhase.java (consumer), issue #478 CAPS mapping table
**Exploration:** quick
**Depends on:** D1 (sub-thoughts populated in FOUNDATION, available via accessor)
**Status:** captured

## D5: Rule-based sync extraction strategy

**Choice:** Keyword matching + cached entity names — type detection via static keyword sets per sub-thought type, entity tagging via cached MindMap entity names refreshed on writes
**Alternatives:**
- Keyword matching only — no entity tags in sync pass, can't feed mental model BDI routing until async LLM enrichment; defeats purpose of same-tick mental model integration
- Full MindMap query per tick — correct but adds store I/O to every tick; unnecessary when a cached view suffices
**Rationale:** Balances speed (O(n) over tokens, no store I/O) with utility (entity-tagged sub-thoughts enable same-tick mental model BDI updates). Entity name cache refreshed when MindMap writes occur — entity names change infrequently relative to tick frequency. Keyword sets in code initially (static Map), configurable later if needed.
**Trade-offs:** Keyword matching is lower quality than LLM extraction — misses nuanced types, may misclassify. Acceptable because the async LLM pass enriches the same memory with richer decomposition for subsequent ticks and consolidation.
**Sources:** RuleBasedSituationClassifier.java (keyword matching pattern reference), MindMapStoreIdleTracker.java (write tracking), SubThoughtTypes.java (7 type constants), issue #478 hybrid extraction strategy
**Exploration:** quick
**Depends on:** D1 (extraction runs in FOUNDATION phase)
**Status:** captured

## D6: SubThoughtExtractionObserver scope

**Choice:** All ExperienceRecorded events — every experience triggers async LLM sub-thought extraction
**Alternatives:**
- Selective by text length or event type — risks missing brief but high-value observations; filtering logic adds complexity for minimal savings
- Config-gated per ExperienceEvent subtype — over-engineering for a cheap extraction that self-filters (empty results cost nothing)
**Rationale:** Haiku calls are cheap, empty extraction results are harmless downstream. Drive distributions and mental model accuracy improve with full coverage. Brief observations ("Sarah seemed off today") are exactly what sub-thoughts are designed to capture — length-based filtering would exclude them.
**Trade-offs:** More LLM calls than selective approaches. Acceptable given Haiku cost and the value of comprehensive sub-thought coverage.
**Sources:** CheckInService.java (current single trigger point), ExperienceRecorded CDI event, SubThoughtExtractionRequested CDI event, SubThoughtExtractor.java (no-op stub to be implemented)
**Exploration:** quick
**Status:** captured
