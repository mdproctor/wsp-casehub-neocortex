## D1: SubThoughtTickParticipant phase placement

**Choice:** FOUNDATION phase (custom participant, runs after mood + memory hygiene)
**Alternatives:**
- DERIVED phase (as issue originally proposed) — modeled on AppraisalTickParticipant, but sub-thought extraction has no dependency on cognitive state computed in earlier phases, so DERIVED causes a one-tick lag for all high-value consumers (mental model, drives)
- Pre-phase hook on CognitionCore — clean but over-engineered for one use case, adds a new concept to the tick lifecycle
- CognitionTickContext field expansion — couples the context record to sub-thought infrastructure, changes API for all participants
**Rationale:** Sub-thought extraction is input parsing (text → typed structure), not cognitive evaluation. It depends only on observation text + entity names, not on mood/drives/mental model. FOUNDATION placement makes sub-thoughts available to ALL downstream phases in the same tick: mental model (subject loop), drives (DERIVED), CAPS, prompt rendering. Uses existing extension mechanism (CognitionTickParticipant + per-agent ConcurrentHashMap + accessor).
**Accessor mechanism:** CognitionCore gains a `SubThoughtTickParticipant` field and `configureSubThoughts()` setter, following the AppraisalTickParticipant precedent (CognitionCore.java line 121, setAppraisalParticipant/configureAppraisal). The participant registers itself at FOUNDATION phase via `addParticipant(CognitionPhase.FOUNDATION, participant)`. Results stored in `ConcurrentHashMap<String, SubThoughtResult>`, accessible via `currentSubThoughts(String agentId, String tenantId)`. Downstream consumers access via CognitionCore reference (prompt sections) or direct constructor injection (DriveOrchestrator for D2, MentalModelOrchestrator receives push signals per D7).
**Trade-offs:** Slightly stretches the semantic meaning of "FOUNDATION" (baseline state establishment vs input decomposition). FOUNDATION custom participants run after mood/hygiene, so sub-thoughts can't inform mood baseline — acceptable since mood doesn't consume sub-thoughts.
**Sources:** CognitionCore.java tick lifecycle, AppraisalTickParticipant.java (DERIVED reference pattern), CognitionTickParticipant.java SPI, issue #478 architecture diagram
**Exploration:** deep-analysis
**Status:** revised — accessor mechanism specified (R1-02)

## D2: Drive modulation via DriveComposer

**Choice:** Sub-thought type distributions modulate drive intensities through DriveComposer, following the NarrativeModulation pattern
**Alternatives:**
- Four separate DriveSource classes (SubThoughtAffiliationDrive, etc.) — **does not work**: DriveOrchestrator takes four named constructor parameters, not CDI-discovered instances. DriveOrchestrator.tick() explicitly calls each by name. No plugin mechanism exists.
- Compose into existing drives (modify CuriosityDrive, CompetenceDrive, etc.) — conflates two independent signals. Existing drives derive intensity from their specific data sources (knowledge gaps, user relationships). Sub-thought data is a modulation signal, not a primary evaluator. Mixing them couples unrelated concerns.
- Add List<DriveSource> extension point to DriveOrchestrator — architectural change with no other motivation, and DriveSource.evaluate() returns DriveIntensity for ONE axis while sub-thought distributions affect ALL axes simultaneously
**Rationale:** NarrativeModulation provides the exact template. DriveOrchestrator.tick() already reads from NarrativeOrchestrator and passes `Map<DriveAxis, Double>` to DriveComposer.compose(). Sub-thought modulation follows the same pipeline:
1. DriveOrchestrator takes an optional `@Nullable SubThoughtTickParticipant` constructor parameter (like `@Nullable NarrativeOrchestrator` at line 55)
2. `SubThoughtModulation.compute()` maps sub-thought type distributions to `Map<DriveAxis, Double>` (concern→AFFILIATION, association→CURIOSITY, evaluative→COMPETENCE, self-reflection+intention→AUTONOMY)
3. DriveComposer.compose() gains a `@Nullable Map<DriveAxis, Double> subThoughtModulation` parameter, applied in the modulation pipeline after narrative modulation
**Trade-offs:** Adds a modulation step to DriveComposer (from 3 to 4 modulations: mood, personality, narrative, sub-thought). The modulation map computation runs every tick even when no sub-thoughts exist — the null check makes this O(1) for the empty case.
**Sources:** DriveOrchestrator.java (tick method line 67–114, NarrativeOrchestrator integration), NarrativeModulation.java (compute pattern), DriveComposer.java (compose signature + modulation pipeline), issue #478 drive mapping table
**Exploration:** quick → revised via review
**Depends on:** D1 (FOUNDATION phase placement — sub-thoughts available before drives tick at step 6), D7 (pull pattern for drives)
**Status:** revised — changed from four DriveSource classes to DriveComposer modulation (R1-04)

## D3: Mental model bridge mechanism

**Choice:** New MentalStateSignal variant — SubThoughtCue(type, text, entity, confidence) routed through existing signal pipeline, with heuristic extraction
**Alternatives:**
- Direct BDI upsert — bypasses signal pipeline, creates parallel update path that doesn't interact with heuristic/LLM gating, risk of overwrite conflicts
- Replace LLM inference entirely — premature; rule-based extraction won't match LLM quality until async LLM extraction path is proven
- Reuse VerbalCue with richer CueType mapping — CueType has three values (BELIEF_STATEMENT, DESIRE_EXPRESSION, INTENTION_DECLARATION) that map 1:1 to BDI dimensions. SubThoughtTypes have N:M mappings (affect-observation → Belief + potentially Desire; concern → Desire + Belief about threat). Forcing sub-thought semantics into CueType conflates two distinct classification domains.
**Rationale:** Routes through existing infrastructure (signal buffer, subject loop processing, heuristic extraction mapping). Naturally reduces redundant LLM calls — more sub-thought signals populate BDI before the LLM inference threshold is reached. Additive and safe — poor sub-thought extraction quality degrades gracefully.
**Heuristic extraction:** MentalModelOrchestrator.record() gains a second dispatch case: `if (signal instanceof SubThoughtCue stc) { extractSubThoughtHeuristic(state, stc); }`. The new method maps SubThoughtType → BDI dimension for same-tick BDI updates:
- affect-observation, evaluative → Belief (about entity state, confidence 0.6)
- concern, association → Desire (for entity wellbeing/engagement, confidence 0.6)
- intention → Intention (attributed intent, confidence 0.7)
- causal-inference, self-reflection → Belief (about causal structure / self-state, confidence 0.5)
Confidence values are lower than VerbalCue heuristics (0.8) because sub-thought extraction — especially sync (D5) — is less reliable than direct verbal cues.
**Trade-offs:** Adds a new signal variant to MentalStateSignal sealed hierarchy. The type → BDI mapping is a second heuristic path alongside VerbalCue, but the mapping tables are distinct (sub-thought types vs verbal cue types).
**Sources:** MentalModelOrchestrator.java (extractHeuristic line 189–200, record() line 64–78), MentalStateSignal sealed hierarchy, CueType enum (3 values: BELIEF_STATEMENT, DESIRE_EXPRESSION, INTENTION_DECLARATION), issue #478 BDI mapping table
**Exploration:** quick → revised via review
**Depends on:** D1 (sub-thoughts available in FOUNDATION, pushed to MentalModelOrchestrator buffer before subject loop), D7 (push pattern for mental model)
**Status:** revised — extractHeuristic extension specified, VerbalCue reuse alternative rejected (R1-06)

## D4: CAPS integration via metadata-enriched decorator

**Choice:** SituationClassifier @Decorator — reads sub-thought metadata from the classify() metadata map, produces additional CAPS activations, returns merged result
**Alternatives:**
- Ambient-state decorator reading from participant accessor — requires static/singleton accessor for tick-time state, thread-safety risk. Moot point: SituationClassifier.classify() is only called from BehavioralSynthesisPhase at consolidation time (verified via ide_find_references — exactly one call site). No tick-time classify() call exists.
- Embed sub-thought handling in each classifier implementation — duplicates mapping logic across RuleBasedSituationClassifier and LlmSituationClassifier. Sub-thought→CAPS mapping is a separate concern from base CAPS classification.
- Separate signal pathway (SubThoughtTickParticipant stores activations, BehavioralSynthesisPhase merges two sources) — breaks single-source abstraction, requires consolidation phase to know about dual activation sources.
**Rationale:** The dual-context problem from the original design does not exist: classify() is consolidation-only. The decorator reads sub-thought metadata from the `Map<String, String> metadata` parameter. BehavioralSynthesisPhase.nodeMetadata() is extended to include sub-thought attributes from MindMap node properties (populated by D6's async enrichment of source memories, which graduate to MindMap nodes). The decorator maps sub-thought type metadata to additional CAPS input node activations and merges with the delegate classifier's result. No ambient state, no static accessor, no thread-safety concern.
**Trade-offs:** Requires BehavioralSynthesisPhase.nodeMetadata() extension to read sub-thought properties from MindMap nodes. RuleBasedSituationClassifier currently ignores metadata entirely — the decorator adds the sub-thought concern without modifying the base classifier.
**Sources:** SituationClassifier.java SPI (classify signature: String description, Map<String, String> metadata), BehavioralSynthesisPhase.java (nodeMetadata() line 261–266, classify call line 101 — sole call site), RuleBasedSituationClassifier.java (does not use metadata parameter), issue #478 CAPS mapping table
**Exploration:** quick → revised via review
**Depends on:** D6 (async enrichment populates memory attributes that become MindMap node properties)
**Status:** revised — metadata-based data channel replaces ambient state, dual-context eliminated (R1-08)

## D5: Rule-based sync extraction strategy

**Choice:** Keyword matching + cached entity names — type detection via static keyword sets per sub-thought type, entity tagging via cached MindMap entity names refreshed on writes
**Alternatives:**
- Keyword matching only — no entity tags in sync pass, can't feed mental model BDI routing until async LLM enrichment; defeats purpose of same-tick mental model integration
- Full MindMap query per tick — correct but adds store I/O to every tick; unnecessary when a cached view suffices
- Fast LLM extraction in tick (Haiku) — adds 10–50ms latency to every tick for every observation. Sub-thought extraction is input decomposition, not a primary cognitive evaluation like appraisal. The async LLM path (D6) provides accurate classification within ~1s. Zero-latency provisional extraction is the design intent.
**Rationale:** Balances speed (O(n) over tokens, no store I/O) with utility (entity-tagged sub-thoughts enable same-tick mental model BDI updates). Entity name cache refreshed when MindMap writes occur — entity names change infrequently relative to tick frequency. Keyword sets in code initially (static Map), configurable later if needed.
**Precision acknowledgment:** Keyword matching has known low precision for cognitive categories. Sync-extracted sub-thoughts carry a confidence cap of 0.5 (provisional). This signals downstream consumers (mental model heuristic extraction at confidence 0.5–0.6 per D3, drive modulation with proportional dampening) to weight sync results appropriately.
**Reconciliation with D6:** Async LLM results are authoritative and overwrite sync results. When SubThoughtExtractionObserver (D6) enriches a memory's attributes via enrichAttributes(), sub-thought attribute keys (sub-thought-type, sub-thought-entity, sub-thought-confidence) use replace-on-enrichment semantics within the sub-thought namespace. The sync path provides provisional same-tick data; the async path provides the ground truth.
**Entity cache refresh timing:** Consolidation runs asynchronously via ConsolidationMediator, separate from the tick cycle. MindMap writes from consolidation happen between ticks. The entity name cache is refreshed via MindMapStore write events. At FOUNDATION time, the cache reflects the most recent consolidation writes.
**Trade-offs:** Keyword matching is lower quality than LLM extraction — misses nuanced types, may misclassify. Acceptable because: (1) results are marked provisional (confidence ≤ 0.5), (2) the async LLM pass enriches the same memory with authoritative classification, (3) a wrong provisional sub-thought degrades gracefully (slightly incorrect drive modulation for one tick).
**Sources:** RuleBasedSituationClassifier.java (keyword matching pattern reference), MindMapStoreIdleTracker.java (write tracking), SubThoughtTypes.java (7 type constants), issue #478 hybrid extraction strategy
**Exploration:** quick → revised via review
**Depends on:** D1 (extraction runs in FOUNDATION phase)
**Status:** revised — reconciliation strategy specified, precision acknowledged, entity cache timing clarified (R1-10)

## D6: SubThoughtExtractionObserver scope

**Choice:** All ExperienceRecorded events — every experience triggers async LLM sub-thought extraction
**Alternatives:**
- Selective by text length or event type — risks missing brief but high-value observations; filtering logic adds complexity for minimal savings
- Config-gated per ExperienceEvent subtype — over-engineering for a cheap extraction that self-filters (empty results cost nothing)
**Rationale:** Haiku calls are cheap (~$0.000025/1K tokens), empty extraction results are harmless downstream. Drive distributions and mental model accuracy improve with full coverage. Brief observations ("Sarah seemed off today") are exactly what sub-thoughts are designed to capture — length-based filtering would exclude them.
**Complementarity with D5:** D5 and D6 operate on different inputs at different times. D5 extracts from the current observation TEXT (the raw text passed to CognitionCore.tick() that may not yet be a recorded memory). D6 extracts from RECORDED EXPERIENCES (memories persisted via ExperienceRecorderCore). A tick may have an observation that hasn't been (and may never be) recorded as an experience. These are complementary, not redundant.
**Trade-offs:** More LLM calls than selective approaches. In high-frequency deployments (100+ experiences/minute across agents), this may require runtime throttling — but that's a deployment configuration concern, not a design constraint.
**Sources:** CheckInService.java (current single trigger point), ExperienceRecorded CDI event, SubThoughtExtractionRequested CDI event, SubThoughtExtractor.java (no-op stub to be implemented)
**Exploration:** quick
**Status:** captured

## D7: Push vs Pull — SubThoughtTickParticipant data flow pattern

**Choice:** Push to MentalModelOrchestrator; pull for drives, CAPS, and prompt rendering
**Alternatives:**
- Pure pull (all consumers read from participant accessor) — MentalModelOrchestrator.record() is a push API (it expects signals). Forcing pull would require MentalModelOrchestrator to poll SubThoughtTickParticipant, which is architecturally wrong — the mental model receives signals, it doesn't fetch them.
- Pure push (participant calls all consumers during its tick) — DriveOrchestrator.tick() is called by CognitionCore at step 6, not during FOUNDATION. The participant can't push to drives because drives haven't ticked yet. The participant stores data; DriveOrchestrator reads it when it ticks.
**Rationale:** Each consumer's API dictates the data flow direction:
- **MentalModelOrchestrator (push):** record() accepts MentalStateSignal instances. SubThoughtTickParticipant calls `mentalModel.record(new SubThoughtCue(...), agentId, subjectId, tenantId)` during its FOUNDATION tick, before the per-subject mental model loop (CognitionCore step 5). The participant takes MentalModelOrchestrator and SubjectResolver as constructor parameters. Entity names from sub-thoughts are mapped to subjectIds via SubjectResolver.
- **DriveOrchestrator (pull):** DriveOrchestrator.tick() runs at step 6. It reads from SubThoughtTickParticipant.currentSubThoughts() to compute modulation, like it reads from NarrativeOrchestrator.currentNarrative().
- **CAPS (pull via metadata):** Per D4, sub-thought data reaches SituationClassifier through the metadata map at consolidation time. No tick-time CAPS concern.
- **Prompt rendering (pull):** Prompt sections access via CognitionCore's SubThoughtTickParticipant field, like AppraisalPromptSection accesses AppraisalTickParticipant.
**Trade-offs:** The participant is both an active coordinator (push to mental model) and a passive data store (pull for drives, CAPS). This dual role is consistent with AppraisalTickParticipant, which actively pushes mood signals (bridgeToMood) while passively serving appraisal results.
**Sources:** MentalModelOrchestrator.record() (push API, line 64–78), DriveOrchestrator.tick() (pull pattern with NarrativeOrchestrator, line 80–84), AppraisalTickParticipant (dual push/pull precedent: bridgeToMood + currentResult)
**Exploration:** surfaced by review (R1-14, R1-19)
**Depends on:** D1 (participant placement and accessor)
**Status:** captured

## D8: SubThought value type vs attribute-based access

**Choice:** SubThought value type for in-process tick-time access; attribute-based storage for persistence
**Alternatives:**
- Attributes only — all consumers parse strings from memory attribute maps. Loses type safety, forces every consumer to know attribute key conventions and parse logic.
- Value type only — no persistence format. Forces memory enrichment to serialize/deserialize through a custom format rather than the established attribute pattern.
**Rationale:** The SubThought record (type: SubThoughtType, text: String, entity: String, confidence: double) provides type-safe structured access for all tick consumers (mental model, drives, prompt rendering). SubThoughtTickParticipant stores and serves SubThought instances. For persistence, SubThoughtExtractionObserver (D6) writes attribute keys (sub-thought-type, sub-thought-entity, sub-thought-confidence) via the established enrichAttributes() pattern. SubThoughtTickParticipant reads from both: current tick's sync-extracted SubThought instances AND SubThought instances reconstructed from recent memory attributes.
**Trade-offs:** Two representations for the same data. Conversion between them is mechanical (SubThought.fromAttributes() and SubThought.toAttributes()). The alternative (one representation) either sacrifices type safety (attributes-only) or breaks the memory enrichment pattern (value-type-only).
**Sources:** Issue #478 build order ("SubThought value type + query helpers"), SubThoughtAttributeKeys-style indexed string convention, Memory.enrichAttributes() API
**Exploration:** surfaced by review (R1-15)
**Status:** captured

## D9: Tick-scoped vs memory-scoped sub-thought unification

**Choice:** Sync results are ephemeral (tick-only), async results are persistent (memory attributes), participant merges both with async-wins precedence
**Alternatives:**
- Persist sync results — adds a write to every tick, creates potential conflicts with async enrichment, complicates the "async overwrites sync" reconciliation in D5.
- Only serve async results — loses same-tick availability for the current observation. The observation may not yet be a recorded memory (D6's trigger), so async results don't exist yet.
**Rationale:**
- **Sync results (D5):** Ephemeral SubThought instances in SubThoughtTickParticipant's ConcurrentHashMap. Produced from current observation text. Cleared when the next tick begins (or when the key is overwritten). Not stored in memory attributes.
- **Async results (D6):** Persistent memory attributes. Available in subsequent ticks when the participant queries recent memories.
- **Unification:** SubThoughtTickParticipant.tick() produces a merged view: current sync results + SubThoughts reconstructed from recent memory attributes (queried from memory store). If sync and async produce sub-thoughts for the same text span with different types, async wins (higher confidence, LLM-backed).
- **No double-storage:** Sync results exist only in-memory for the current tick. This avoids the overwrite/merge complexity the reviewer identifies — there's nothing to overwrite because sync results aren't persisted.
**Trade-offs:** Sync results are lost after the tick. If the same observation text triggers a tick but is never recorded as an experience (edge case), its sub-thoughts are never persisted. Acceptable because non-recorded observations are inherently ephemeral.
**Sources:** SubThoughtTickParticipant ConcurrentHashMap (D1), enrichAttributes() persistence (D6), reconciliation strategy (D5)
**Exploration:** surfaced by review (R1-16)
**Depends on:** D1 (participant storage), D5 (sync extraction), D6 (async enrichment)
**Status:** captured
