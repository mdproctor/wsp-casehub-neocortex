# Decisions — Progressive Cognitive Attention Model (#381)

## D1: Spec scope

**Choice:** Neocortex + blocks contract
**Alternatives:**
- Neocortex only — simpler but leaves blocks integration undefined
- Full stack (+ agent runtime push receiver) — too many unknowns in the runtime layer; runtime is a separate spec
**Rationale:** The attention model needs to define what it produces AND how the consumer contract works. The blocks-side listener is the boundary where neocortex hands off to the agent layer. The runtime push receiver (WebSocket/queue/CLI) is a separate concern with its own unknowns.
**Trade-offs:** Runtime push receiver design deferred — blocks listener will fire a CDI event or call an SPI, but the actual "wake up the LLM" mechanism is out of scope.
**Sources:** casehubio/neocortex#381 issue body (three-layer architecture sketch)
**Exploration:** quick
**Status:** captured

## D2: Trigger model

**Choice:** Event-driven only (significance threshold crossing)
**Alternatives:**
- Event + scheduled briefings — adds complexity without clear benefit; schedule can be layered later by runtime-level cron
- Scheduled with event override — predictable cadence but wasteful when nothing changed
**Rationale:** The SignificanceAccumulator already implements event-driven threshold crossing. Extending this pattern is simpler than adding a parallel scheduling system. Scheduled briefings (morning wake) can be layered at the runtime level without neocortex changes.
**Trade-offs:** No built-in periodic check-in — if significance never crosses threshold, the agent never gets pushed. This is by design: no news is no push.
**Sources:** SignificanceAccumulator.java (existing threshold pattern), ConsolidationScheduler.java (daemon thread lifecycle)
**Exploration:** quick
**Status:** captured

## D3: Attention granularity

**Choice:** Per-principal (each agent gets independent attention accumulation and briefings)
**Alternatives:**
- Per-tenant — simpler, matches existing ConsolidationScheduler granularity, but all agents see the same attention events
- Per-tenant with principal filtering — accumulate per-tenant, filter at briefing time; middle ground but briefing construction still needs per-principal ranking
**Rationale:** Different agents within a tenant care about different goals. CognitiveDefaults are per-agentId, perspectival overlays are per-principal, goal surfacing in CognitiveGoalOrchestrator is per-agent. Attention should match this granularity.
**Trade-offs:** More state to manage — one accumulator instance per principal per tenant. Consolidation phases currently iterate tenants, not principals. The attention accumulator must enumerate principals within each tenant.
**Sources:** CognitiveDefaultsRegistry (per-agentId config), PerspectivalResolver (per-principal overlays), CognitiveGoalOrchestrator (per-agent goal surfacing)
**Exploration:** quick
**Status:** captured

## D4: Threshold model

**Choice:** Adaptive percentile — threshold drops as urgency distribution shifts upward
**Alternatives:**
- Static with decay — fixed threshold that decays over time since last push; doesn't respond to goal landscape
- Dual threshold — base + emergency; simpler but binary rather than continuous
**Rationale:** The attention threshold should reflect the cognitive pressure on the agent. When many goals are urgent, the agent should be more sensitive to changes. P75 of active goal urgencies per principal captures this naturally. When P75 urgency > 0.6, threshold halves — more goals approaching deadlines = more frequent attention.
**Trade-offs:** Requires computing the urgency distribution per principal each consolidation tick. Adds coupling between GoalPrioritizationPhase output and the attention accumulator.
**Sources:** GoalUrgency.java (time-aware urgency computation), GoalPrioritizationPhase.java (priority + urgency computation per goal)
**Exploration:** quick
**Status:** captured

## D5: Briefing granularity

**Choice:** Ranked signals only (AttentionItem-style: goal id, salience score, reason, category)
**Alternatives:**
- Signals + summary context — structured per-item summary; larger payload but more self-contained
- Narrative briefing — LLM-generated text; expensive (requires LLM call during consolidation) and breaks the principle of keeping consolidation LLM-free
**Rationale:** Mirrors the existing TemporalFocus output format (AttentionItem with salience + reason). The agent uses existing pull APIs (CognitiveProfile.resolve, MindMapStore.search) to get depth on items it decides to act on. Push gives awareness; pull gives depth.
**Trade-offs:** The blocks listener must know how to pull detail — it needs access to CognitiveProfile or MindMapStore. But CognitiveGoalOrchestrator already has this access.
**Sources:** TemporalFocus.java (AttentionItem pattern), cognitive-index (pull APIs)
**Exploration:** quick
**Status:** captured

## D6: Rate limiting

**Choice:** Minimum interval per principal (configurable, e.g. 5 minutes default)
**Alternatives:**
- Token budget per period — more nuanced cost control but harder to reason about; token consumption isn't known until the LLM processes the push
- Exponential backoff — self-regulating but could starve attention during sustained urgency
**Rationale:** Simple, predictable, prevents LLM cost runaway. Even if significance re-crosses threshold within the window, the push is suppressed until the interval expires. The interval is configurable per-principal via CognitiveDefaults.
**Trade-offs:** Fixed floor regardless of urgency — a truly critical signal (e.g. goal deadline in 5 minutes) still waits for the interval to expire. Could add an emergency override threshold, but deferred for simplicity.
**Sources:** CognitiveDefaults (per-agent configuration), SignificanceAccumulator.java (existing CAS-guarded triggering)
**Exploration:** quick
**Status:** captured

## D7: Signal sources

**Choice:** Consolidation + real-time hybrid — both paths converge at per-principal accumulator
**Alternatives:**
- Consolidation only — simpler but adds latency for urgent real-time signals
- Real-time only — fast but misses composite insights from consolidation (decay trends, merge opportunities, cross-goal priority shifts)
**Rationale:** Consolidation produces composite insights (goal priority recomputation, decay detection across the graph). Real-time events carry immediate significance (experience recorded mentioning a goal, external goal status change). Both are valid attention signals. They converge at the same per-principal accumulator, evaluated against the same adaptive threshold.
**Trade-offs:** Two signal paths to maintain. Need clear distinction between what consolidation phases produce vs what real-time events carry — avoid double-counting when an experience triggers both a real-time signal AND a consolidation tick.
**Sources:** SignificanceAccumulator.java (existing event-driven path), ConsolidationScheduler.java (existing consolidation path)
**Exploration:** quick
**Status:** captured

## D8: Blocks contract

**Choice:** New dedicated CognitiveAttentionListener (blocks-side)
**Alternatives:**
- Evolve CognitiveGoalOrchestrator — add @Observes method; reuses existing state tracking but couples tick-driven and push-driven logic
- SPI in neocortex (AttentionReceiver) — cleanest dependency direction but adds a new SPI when a CDI event suffices
**Rationale:** Separation of concerns: CognitiveGoalOrchestrator handles tick-driven goal surfacing (pull). CognitiveAttentionListener handles push-driven attention events. Different triggering mechanisms, different responsibilities. The listener can delegate to the orchestrator's existing goal rendering logic without inheriting its tick lifecycle.
**Trade-offs:** Some duplication of goal-fetching logic between orchestrator (tick) and listener (push). Mitigated by extracting shared rendering into a utility.
**Sources:** CognitiveGoalOrchestrator.java (existing tick-driven pattern), GoalPromptSection (existing goal rendering)
**Exploration:** quick
**Status:** superseded by D13

## D9: Phase signal mechanism

**Choice:** Phase return type evolution — extend ConsolidationPhase to surface attention signals
**Alternatives:**
- Observer-based signal emission — phases fire CDI events; no SPI change but signals become implicit and harder to trace
- Side-channel collector — inject SignalCollector into phases; no SPI change but adds dependency to every phase constructor
**Rationale:** Phases already compute the insights — this makes them explicit and type-safe. Each phase declares what it found. The scheduler collects signals from all phases per tick and feeds them to the per-principal accumulator. Backward-compatible: existing phases that don't produce signals return empty.
**Trade-offs:** ConsolidationPhase SPI changes (new method or return type). All existing phase implementations need updating, even if just to return empty. But there are only 10 phases, all in mindmap-intelligence.
**Sources:** ConsolidationPhase.java (current SPI), PhaseResult.java (current return type), GoalPrioritizationPhase.java (example phase with insights to surface)
**Exploration:** quick
**Status:** captured

## D10: ConsolidationPhase SPI evolution

**Choice:** Add `default List<AttentionSignal> signals() { return List.of(); }` to ConsolidationPhase
**Alternatives:**
- Change run() return type — breaks all 10 existing implementations
- Enrich PhaseResult — PhaseResult is constructed by the scheduler, not the phase; would need refactoring
**Rationale:** Default method is fully backward compatible. Phases accumulate signals during run(), caller reads via signals() after run() completes. No signature change to run(). Existing phases return empty until individually updated.
**Trade-offs:** Phase implementations must manage internal signal state (typically a List field cleared in beginTick()). Slightly less explicit than a return type, but the default method makes adoption incremental.
**Depends on:** D9 (phase signal mechanism)
**Sources:** ConsolidationPhase.java (current SPI with default beginTick())
**Exploration:** quick
**Status:** captured

## D11: Principal discovery

**Choice:** CognitiveDefaultsRegistry.allAgentIds() to enumerate known principals
**Alternatives:**
- MindMap overlay scan — expensive per tick, misses agents without overlays
- Explicit registration — adds lifecycle management burden
**Rationale:** CognitiveDefaultsRegistry already scans classpath for cognitive-profiles/*.yaml and provides forAgent/forAgentOrDefaults lookup. Adding allAgentIds() is trivial. Agents without cognitive profiles don't participate in attention — they haven't opted in to cognitive processing.
**Trade-offs:** Agents created at runtime (not via YAML profiles) won't be discovered. Acceptable for now — runtime agent creation can use explicit registration later.
**Depends on:** D3 (per-principal granularity)
**Sources:** CognitiveDefaultsRegistry.java (classpath scan, volatile Map.copyOf()), CognitiveProfileWatcher.java (filesystem hot-reload)
**Exploration:** quick
**Status:** captured

## D12: Real-time signal events

**Choice:** ExperienceRecorded + AffectRecorded + goal lifecycle changes feed attention accumulator directly
**Alternatives:**
- All cognitive CDI events — comprehensive but noisy
- ExperienceRecorded only — simplest but misses urgent affect signals
**Rationale:** These three event types carry immediate cognitive significance: experiences mention goals (subject matching), affect shifts signal emotional state changes relevant to goal appraisal, and external goal lifecycle changes (from GoalLifecycleProvider) indicate the goal landscape changed outside consolidation. Other events contribute via SignificanceAccumulator → consolidateNow() for batch processing.
**Trade-offs:** Need goal-relevance filtering on ExperienceRecorded (not all experiences are attention-worthy — only those whose subject matches an active goal). AffectRecorded needs a significance threshold (minor PAD fluctuations shouldn't trigger attention).
**Depends on:** D7 (hybrid signal sources)
**Sources:** ExperienceRecorded.java (CDI event), AffectRecorded (CDI event from AffectTrajectoryDecorator), GoalLifecycleProvider.java (SPI for external goal state)
**Exploration:** quick
**Status:** captured

## D13: CognitionCore as attention convergence point (revised D8)

**Choice:** CognitionCore gains a per-principal attention queue. CognitiveAttentionRequired CDI event writes to this queue. Tick-based agents drain it via promptSections(). Idle agents drain it when the push receiver wakes them. Replaces standalone CognitiveAttentionListener.
**Alternatives:**
- Standalone CognitiveAttentionListener bypassing CognitionCore — duplicates cognitive state management, doesn't work for tick-based agents
- Direct LLM invocation from listener — bypasses CognitionCore's prompt assembly and budget management
**Rationale:** Wacky-manor investigation revealed CognitionCore already owns cognitive state and prompt sections. The attention briefing is another cognitive section. CognitionCore must be the convergence point for both tick-based and push-based agents. This also enables CognitionCore to absorb CognitiveBudget — attention-aware budgeting becomes a platform concern.
**Trade-offs:** CognitionCore becomes more complex. It now manages attention queue state in addition to tick state. But this complexity belongs there — CognitionCore is the cognitive orchestrator.
**Depends on:** D8 (blocks contract, superseded)
**Sources:** wacky-manor ScenarioOrchestrator.java (tick loop with CognitionCore.tick()), CharacterCognition.renderCognitiveSections() (CognitionCore.promptSections() consumption), CognitiveBudget.java (situational attention budgeting)
**Exploration:** quick
**Status:** captured

## D14: Platform consolidation direction

**Choice:** Design the attention model so wacky-manor can delete custom cognitive code and use platform features directly. CognitiveBudget → CognitionCore. ManorConsolidationBeans manual wiring → CDI auto-registration. CharacterCognition section rendering → CognitionCore.promptSections(). App code should only provide domain-specific customization (game object types, action descriptors, scenario rules), not cognitive infrastructure.
**Alternatives:**
- Keep attention model independent of wacky-manor concerns — misses the consolidation opportunity
- Full wacky-manor refactor as part of #381 — too large, separate work
**Rationale:** User direction: make wacky-manor thinner by consolidating into eidos, blocks, and neocortex. #381 is the right vehicle for CognitionCore attention integration. The actual wacky-manor refactor is follow-up work, but the API design should enable it.
**Trade-offs:** The attention model's API surface must be general enough for wacky-manor's game loop AND idle agent push. This is actually good — it forces a better abstraction.
**Sources:** wacky-manor CognitiveBudget.java, ManorConsolidationBeans.java, CharacterCognition.java, ScenarioOrchestrator.java
**Exploration:** quick
**Status:** captured

## D15: Alignment with blocks#303 cognitive state migration

**Choice:** Design the attention model's layer placement to align with the blocks#303 reorganization. All cognitive state types and computation in neocortex. Orchestration and prompt assembly in blocks (CognitionCore). Post-#303, the migrated orchestrators (MoodOrchestrator, DriveOrchestrator, etc.) can emit attention signals directly to the accumulator — same neocortex module, no CDI boundary crossing.
**Alternatives:**
- Ignore #303 and design for current layer boundaries — would require rework when orchestrators migrate
- Wait for #303 to land before designing #381 — blocks the attention model unnecessarily; the layer placement is already clear
**Rationale:** #303 established the principle: neocortex = brain (state computation), blocks = coordination (tick, prompt, routing). The attention model follows this exactly. Designing for the post-#303 world means no rework when the migration lands.
**Trade-offs:** Pre-#303, the blocks-side consolidation phases (DriveAdaptation, RelationshipStage, BeliefRevision) produce signals via ConsolidationPhase.signals() which crosses into neocortex's accumulator. Post-#303, these phases move to neocortex and the crossing disappears. The design works either way — the ConsolidationPhase SPI is already in neocortex.
**Depends on:** D14 (platform consolidation direction)
**Sources:** blocks#303 issue body (migration scope), blocks#298 epic (sequencing: S/XS wiring first, then OCC extensions, then migration)
**Exploration:** quick
**Status:** captured
