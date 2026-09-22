## Foundation: Architecture boundaries (agreed)

**Three-dimensional goal architecture:** LLM goals (prose, blocks/langchain4j), case goals (predicates, engine), cognitive goals (neocortex, NEW). Cognitive goals manage and enrich goals from both dimensions, and also operate standalone.

**Substrate vs orchestration split:** Neocortex = cognitive substrate (the WHAT — memory, knowledge graph, affect, curiosity, consolidation, goal cognition). Blocks = cognitive agent orchestration (the HOW — drives, goal proposal, narrative, social cognition, prompt rendering, behavioral wiring). Integration testing of the full cognitive agent lives at the blocks level.

**SPI inversion for LLM access:** Neocortex defines SPIs for cognitive operations requiring LLM (goal decomposition, goal recognition, consolidation phases). Blocks provides LLM-backed implementations via `@Alternative @Priority`. `@DefaultBean` NoOp in neocortex ensures standalone operation (e.g. Hortora). Pattern: `ReflectionSynthesizer`, `GraduationScorer`/`GraduationClassifier`.

**No split-brain:** Eidos `AgentRegistry` is the single authoritative store for "what goals does this agent have." Neocortex provides cognitive context that feeds INTO `GoalFormationContext` and `GoalRevisionContext`. No parallel goal registry.

Established by cross-repo audit, three brainstorming sessions, and live discussion. See `2026-09-22-goal-architecture-context.md`.

---

## D1: Where do shared goal primitives live?

**Choice:** No new shared module. Two existing layers, one natural dependency.

Eidos-api gets enriched identity-level goal types (expand `AgentGoal` with lifecycle state, horizon). These are typed enums following eidos conventions (`GoalPriority`, `GoalOutcome`).

Neocortex uses MindMap conventions for cognitive goal types — dependency types as edge vocabulary strings (`enables`, `blocks`, `requires`, `contributes-to`, `decomposes-into`), origin as a node property, resolution level as a property. Follows existing neocortex conventions (`SubgraphTypes`, edge vocabulary, property-based classification).

Neocortex gains eidos-api as a compile dependency on modules that need it (cognitive-index, mindmap-intelligence, goal module). The cognitive layer naturally needs to know the identity it's cognitive of — the `DescriptorView` indirection was principled but unnecessary. Direct access to `AgentGoal`, `GoalPriority`, `AgentDescriptor` simplifies the interface.

Lifecycle state transitions follow the existing AgentGoal mutation pattern: engine routing (GoalFormationService, GoalRevisionEvaluator, GoalAbandonmentEvaluator) writes lifecycle state via `AgentRegistry.register()`. Neocortex reads lifecycle state via eidos-api — it does not write lifecycle transitions. This is consistent with the "No split-brain" foundation.

DescriptorView remains for modules that don't need goal-specific context (agent name, disposition for cognitive derivation). Modules requiring AgentGoal access (cognitive-index, mindmap-intelligence, goal module) use eidos-api directly. DescriptorView.goals (`List<String>`) is not deprecated — it serves as a thin summary for non-goal contexts. AgentGoal is authoritative for cognitive goal processing.

**Alternatives:**
- New `neocortex-goal-api` module — adds a build artifact for types that naturally split between eidos (identity) and neocortex (cognitive). Over-abstraction.
- platform-api — goal lifecycle and horizon are domain concepts, not platform infrastructure. Stretches what "platform primitive" means.
- eidos-api for ALL types — forces eidos to carry cognitive vocabulary (dependency types, origin) it doesn't use internally.

**Rationale:** Each layer uses its own conventions. The shared vocabulary is the documented spec (property names, edge types, lifecycle values), not a Java module. Types go where they naturally belong — identity concepts in eidos, cognitive concepts in neocortex. One-way dependency: neocortex → eidos-api. No reverse.

**Trade-offs:** eidos-api grows by a few enums and fields on AgentGoal. neocortex gains a dependency on eidos-api (currently zero — but the cognitive layer should know the identity it's cognitive of).
**Sources:** AgentGoal.java, GoalPriority.java, DescriptorView.java, SubgraphTypes.java, MindMapVocabulary pattern, dependency graph analysis
**Exploration:** deep-analysis (three sessions)
**Status:** revised — added lifecycle write ownership (R1-02), DescriptorView transition plan (R1-03)

---

## D2: What happens to eidos GoalSignalStore?

**Choice:** Leave volatile. Neocortex tracks goal outcomes separately via ExperienceEvent flow.

Eidos's `GoalSignalStore` is a fast signal cache for engine routing evaluators — "how many successes/failures for this goal recently?" The `InMemoryGoalSignalStore` (volatile `ConcurrentHashMap`) serves this purpose. Engine routing is a hot path that needs low-latency reads.

Neocortex gets goal outcomes via the existing `ExperienceEvent` flow — durable, rich episodic storage in CaseMemoryStore. The cognitive system builds its understanding of goal effectiveness from episodic memory, not from a signal counter.

Two representations, different purposes: fast signal cache (eidos, volatile) for routing decisions vs persistent knowledge (neocortex, memory/MindMap) for cognitive reasoning. If eidos durability becomes genuinely needed later, it's an eidos concern — not #345 scope.

**Alternatives:**
- Eidos gets durable persistence — JPA/SQLite GoalSignalStore. Adds persistence weight to eidos for a cache. Broader eidos persistence review needed (drive state, trait pressure also volatile).
- Neocortex becomes the backend — GoalSignalStore backed by neocortex memory. Couples engine routing latency to neocortex availability.

**Rationale:** The existing ExperienceEvent flow already delivers goal outcomes to neocortex. No new integration needed. The volatile signal cache is fast enough for engine routing. Durability is a broader eidos concern that shouldn't block #345.
**Trade-offs:** Goal signal counts reset on JVM restart. Engine routing evaluators lose accumulated history. Acceptable for pre-release; eidos persistence review is a separate issue. **Trigger for revisiting:** Deferral becomes unacceptable when goal evolution must survive JVM restarts for production reliability — specifically, when multi-session agent behavior depends on accumulated goal history. Tracked as eidos issue for broader persistence review covering GoalSignalStore, drive state, and trait pressure.
**Depends on:** D1 (neocortex → eidos-api dependency)
**Sources:** InMemoryGoalSignalStore.java, GoalOutcomeRecorder.java, ExperienceEvent hierarchy
**Exploration:** quick
**Status:** revised — added concrete trigger condition for revisiting (R1-05)

---

## D3: What moves from blocks to neocortex?

**Choice:** Nothing moves now. Neocortex builds complementary substrate; blocks keeps orchestration.

Blocks' `GoalProposalOrchestrator` with drives, mappers, LLM formation, narrative escalation, and outcome pressure is behavioral orchestration — it wires cognitive signals into agent behavior. This belongs in blocks.

Neocortex builds cognitive goal substrate: recognition from experience, dependency graph in MindMap, affect valuation, progressive resolution via consolidation. Neocortex defines SPIs (GoalDecompositionService, GoalRecognitionService) with NoOp defaults. Blocks provides LLM-backed implementations.

Over time, blocks can consume neocortex's cognitive signals to enrich its orchestration: "is this proposed goal already tracked cognitively?" (dedup), "what's the cognitive priority of this goal?" (ranking), "is this goal blocked by dependencies?" (deferral). This is gradual adoption via CDI events and neocortex query APIs — not a migration.

**Alternatives:**
- Cognitive functions migrate to neocortex — drive→goal mapping, LLM formation, priority escalation. Cleanest long-term but biggest scope increase and unclear boundary (in this platform's convention, drives are behavioral rather than cognitive — this is an architectural boundary, not a cognitive science claim).
- Neocortex defines SPIs, blocks implements immediately — premature before the cognitive system exists. Define SPIs from real usage, not speculation.

**Rationale:** The substrate/orchestration split is the right boundary — defined as a platform convention, not a cognitive science universal. Cognitive science (SDT, BDI, Soar, ACT-R) treats motivation as cognitive; our distinction is architectural: neocortex handles knowledge-building operations (memory, inference, graph construction), blocks handles action-driving operations (drive evaluation, prompt rendering, goal proposal, behavioral wiring). Neocortex provides capability. Blocks provides integration. Moving orchestration to neocortex would force neocortex into behavioral decisions (when to propose, how to escalate, how to render prompts) that belong in blocks.
**Trade-offs:** Two systems process goal-related information. Mitigated by CDI events and the substrate/orchestration boundary — they don't overlap, they complement.
**Sources:** GoalProposalOrchestrator.java (500+ lines, deeply woven with drives/narrative), ReflectionSynthesizer pattern (SPI + NoOp)
**Exploration:** deep-analysis
**Status:** revised — reframed cognitive/behavioral boundary as platform convention (R1-08)

---

## D4: How does neocortex integrate with engine routing?

**Choice:** Separate cognitive evaluation via ConsolidationPhase. Engine routing picks up changes through existing query APIs.

Neocortex runs goal cognitive processing in its consolidation schedule (`GoalResolutionPhase`, `GoalRecognitionPhase`). These phases update MindMap goal state — dependencies, affect, lifecycle, resolution level.

Engine routing accesses cognitive goal context through:
1. `CognitiveProfile.resolve()` — returns `EntityKnowledge` with goal node, edges (dependencies), memories (experiences), trajectory (affect). Already designed for this (#253 D33-D43).
2. `GoalFormationContext.recentMemories` — neocortex's goal-related memories appear naturally in the formation context.
3. `GoalFormationService.propose()` — when cognitive processing identifies a goal ready for execution, neocortex (or blocks, acting on neocortex signals) proposes it.
4. `ExperienceEvent` — outcomes from engine flow back to neocortex's cognitive goal tracking.

No changes to engine APIs needed. Engine doesn't know or care that cognitive processing runs in a consolidation phase — it just sees enriched context through existing query interfaces.

**Alternatives:**
- Enrich GoalFormationContext with cognitive fields — adds neocortex-specific fields to platform-api. Couples platform types to cognitive concepts.
- Neocortex-backed GoalFormationStrategy — replaces LLM formation with cognitive formation. Too aggressive; LLM strategy works. Augment context, don't replace the strategy.

**Rationale:** The consolidation pattern is proven (ExperienceConsolidationPhase, MergeDetectionPhase, CuriosityRefreshPhase). Cognitive goal processing is periodic, not real-time — it runs during idle periods and updates persistent state. Engine routing reads the updated state on its next evaluation. No coupling, no latency impact on routing.
**Trade-offs:** Cognitive updates are not immediate — there's a lag between a goal event and cognitive processing. Acceptable because engine routing uses its own fast evaluators for real-time decisions. Cognitive depth adds perspective, not urgency.
**Depends on:** D1 (neocortex → eidos-api for AgentGoal access)
**Sources:** ConsolidationScheduler.java, CognitiveProfile.java, GoalFormationContext.java, GoalFormationService.java
**Exploration:** quick
**Status:** captured

---

## D5: Does desiredstate share goal dependency primitives with neocortex?

**Choice:** Independent types. Desiredstate's `Dependency(from, to)` is execution ordering. Neocortex's edges are semantic relationships. Different concepts.

Desiredstate's `Dependency` means "provision A before B" — topological execution order. Neocortex's goal edges mean "A enables B", "C blocks D" — semantic relationships that inform cognitive reasoning. An "enables" relationship doesn't necessarily mean "execute first" — it means "achieving A makes B possible."

The integration point (if needed later) is a `CognitiveGoalCompiler` that translates neocortex's goal dependency graph into a desiredstate execution graph. The translation IS the integration — mapping semantic relationships to execution ordering. No shared type captures both semantics cleanly.

**Alternatives:**
- Shared `GoalDependency(from, to, type)` — forces desiredstate to carry semantic types it doesn't interpret, or neocortex to carry execution concepts it doesn't need.
- Neocortex dependency informs desiredstate — a future concern. Design the integration point when a CognitiveGoalCompiler is actually needed.

**Rationale:** Execution ordering and semantic relationships are genuinely different. Sharing a type to avoid ~3 lines of duplication adds coupling without benefit. desiredstate doesn't need to know that "enables" is a relationship type; it just needs "A before B."
**Trade-offs:** If a CognitiveGoalCompiler is built, it must translate between representations. Acceptable — translation is the natural integration pattern for cross-subsystem concerns.
**Sources:** Dependency.java (desiredstate), MindMapVocabulary edge types, GoalCompiler<G> generic
**Exploration:** quick
**Status:** captured

---

## D6: Scope of epic #345

**Choice:** #345 covers neocortex cognitive goal substrate. Cross-repo consumption tracked as separate issues per repo.

Scope includes:
- Cognitive goal representation in MindMap (Goallike trait, GOAL subgraph type, structured properties)
- Goal dependency graph (typed edges via MindMapVocabulary)
- Goal recognition SPIs (with NoOp defaults, blocks provides LLM impl)
- Goal cognitive decomposition SPIs (same SPI pattern)
- GoalResolutionPhase (consolidation — progressive resolution, prune/expand/merge/revise/decay)
- Goal affect integration (anticipated affect, frustration modeling, satisfaction)
- Goal-conditioned retrieval (ModulationFactor for goal relevance)
- eidos-api dependency for identity access (AgentGoal on cognitive modules)
- Eidos AgentGoal enrichment (lifecycle state, horizon fields)

Out of scope (separate issues):
- Engine routing enrichment (engine repo issue)
- Blocks adoption of cognitive signals (blocks repo issue)
- Desiredstate CognitiveGoalCompiler (desiredstate repo issue)
- Eidos GoalSignalStore durability (eidos repo issue)
- Blocks DAG infrastructure refactor (blocks repo issue)
- Cross-agent goal awareness (future epic, depends on perspectival overlay infra)

**Alternatives:**
- Neocortex only (no eidos changes) — leaves AgentGoal without lifecycle/horizon. Other repos can't evolve toward the shared vocabulary.
- Full cross-repo (all 6 repos) — requires simultaneous changes to platform, eidos, engine, blocks, desiredstate, neocortex. Too large for one epic.

**Rationale:** Neocortex ships the cognitive substrate + eidos enrichment. Other repos adopt incrementally via separate issues. The spec designs for cross-repo coherence (shared vocabulary, documented edge types, CDI event contracts) without requiring simultaneous implementation.
**Trade-offs:** Cross-repo integration is designed but not implemented in #345. Each consuming repo ships its adoption independently. Acceptable — the substrate must exist before consumers can adopt it.
**Depends on:** D1 (no new module), D3 (nothing moves from blocks)
**Sources:** .plan deferred batches, context doc §Next Steps
**Exploration:** quick
**Status:** captured

---

## D7: Cognitive decomposition and progressive resolution

**Choice:** Progressive resolution model. Neocortex owns cognitive goal graph at variable resolution. LLM-based cognitive decomposition via SPI (blocks implements). Resolution managed by consolidation sleep cycle.

**Variable resolution:** Distant goals are single MindMap nodes with prose description. As time nears, overlaps are detected, or execution approaches, the GoalResolutionPhase increases resolution by decomposing into sub-goal nodes with `decomposes-into` edges. Approaching + overlapping goals get highest resolution. Distant + isolated goals stay as single nodes.

**Resolution triggers (GoalResolutionPhase, priority 35):**
- **Prune:** Distant goals with decomposed sub-goals that haven't been accessed → collapse back to single node
- **Expand:** Approaching goals (time proximity) or newly-overlapping goals → increase resolution via cognitive decomposition SPI
- **Merge:** Shared sub-goals across parent goals → merge sub-goal nodes, create `contributes-to` edges to both parents. Detection uses embedding similarity (SPLADE + dense vectors, leveraging existing neocortex infrastructure) for semantic matching — name-based Jaro-Winkler (MergeDetectionPhase) is insufficient for prose goals where "understand customer pain points" and "assess user frustration areas" are semantically equivalent but lexically distant
- **Revise:** Dependency state changed (sub-goal completed, blocker removed, new information) → update graph
- **Decay:** Goals with no activity and declining affect → reduce priority, suggest dormancy/abandonment

**Cognitive decomposition mechanism:** SPI defined in neocortex — `CognitiveGoalDecomposer` with `@FunctionalInterface` pattern:
```java
List<ParsedExtraction> decompose(String goalDescription, 
    List<MindMapNode> contextNodes, String tenantId);
```
Returns `ParsedExtraction` (existing type from MindMapExtractor) — entities (sub-goals) and relationships (decomposes-into edges). NoOp @DefaultBean returns empty list. Blocks provides LLM-backed implementation with cognitive prompt ("what does achieving this involve?" not "which agent does what?").

**GoalResolutionPhase priority 35:** After ExperienceConsolidationPhase (15), MergeDetectionPhase (20), SchemaDiscoveryPhase (25). Before CuriosityRefreshPhase (40) — goal resolution should inform curiosity signals.

**Two decompositions, separate concerns:**

| | Cognitive (neocortex) | Execution (blocks/engine) |
|---|---|---|
| Question | "What does this involve?" | "How do I execute this?" |
| When | Early — to understand structure | Late — when submitted for execution |
| Output | MindMap nodes (prose + affect + confidence) | DagPlan (agent tasks + contracts) |
| Persistence | Persistent graph, variable resolution | Per-case plan, discarded after execution |

**Alternatives:**
- Share DagPlan infrastructure — MindMap IS neocortex's graph. DagPlan is engine's. ~250 lines not worth extracting. Interface is GoalFormationService.propose() + ExperienceEvent.
- Fixed resolution (always decompose) — wastes cognitive effort on distant/irrelevant goals. LOD analogy: render nearby at high fidelity, distant at low.
- No cognitive decomposition (rely on engine decomposition) — engine decomposition is execution-coupled (agent assignment, capability matching). Can't inform cognitive deliberation (prioritization, overlap detection, opportunity cost).

**Rationale:** Progressive resolution matches human cognition — we don't plan distant goals in detail. The consolidation sleep cycle manages resolution bidirectionally (expand approaching, prune receding). SPI pattern keeps LLM infrastructure in blocks while neocortex owns the cognitive processing logic.
**Trade-offs:** Cognitive decomposition may produce different sub-goals than execution decomposition — they answer different questions. Not a defect; it's the point. Cognitive structure informs selection, execution structure informs dispatch.
**Depends on:** D3 (SPI pattern for LLM access), D6 (scope — GoalResolutionPhase is in-scope)
**Sources:** ConsolidationScheduler.java, MindMapExtractor.java (ParsedExtraction pattern), context doc §Progressive Resolution, context doc §Cognitive vs Execution Decomposition
**Exploration:** deep-analysis (two sessions)
**Status:** revised — specified embedding similarity for goal merge detection (R1-21)

---

## D8: Intentionlike → Goallike trait relationship

**Choice:** Goallike replaces Intentionlike. Intentionlike is deprecated.

Intentionlike (`goal()`, `status()`, `priority()`) is a minimal skeleton created before the goal cognition design existed. It's registered in TypeRegistry under the `"intention"` cognitive type but carries no lifecycle, horizon, dependency, or affect semantics.

Goallike replaces it with the full goal domain model: lifecycle state, horizon, origin (recognized/proposed/inherited), resolution level, affect valence. Goallike is registered in TypeRegistry under `"goal"` as a new cognitive type. Existing code referencing Intentionlike (TypeRegistry registration, CognitiveTraitInterfaceTest) is updated to use Goallike.

Intentionlike is not retained alongside Goallike — having both creates ambiguity about which interface represents goal semantics. The migration is mechanical: Intentionlike has 2 production references (TypeRegistry registration, CognitiveDerivationEngine) and test references.

**Alternatives:**
- Keep both — Intentionlike as a super-interface of Goallike. Adds unnecessary indirection for 3 methods. No consumer needs the minimal view.
- Rename Intentionlike to Goallike — preserves history but the semantics expand beyond renaming.

**Rationale:** Clean replacement. Intentionlike was a placeholder. Goallike is the designed interface.
**Sources:** Intentionlike.java (3 methods), TypeRegistry.java (cognitive type registration)
**Exploration:** surfaced by review (R1-25)
**Status:** captured

---

## D9: GOAL subgraph type for goal nodes

**Choice:** Goal nodes use a dedicated GOAL subgraph type, separate from COGNITIVE.

SubgraphTypes currently defines: PERSON, PROJECT, RESEARCH_AREA, ORGANISATION, CONCEPT, GENERAL, TYPE_SYSTEM, COGNITIVE. ExperienceConsolidationPhase graduates experiences into COGNITIVE. Goal nodes get their own GOAL subgraph type.

Separation enables:
- GoalResolutionPhase operates on GOAL subgraph independently
- CuriositySignalGenerator can prioritize GOAL subgraphs independently (high-affect approaching-deadline goals get priority)
- Goal-specific consolidation scheduling (GOAL subgraph may need different processing frequency than COGNITIVE)

GoalResolutionPhase processes GOAL subgraph nodes. When goal nodes reference cognitive experience nodes (via edges), the edges cross subgraph boundaries — this is already supported by MindMap's edge model (edges reference node IDs, not subgraph types).

**Alternatives:**
- Use COGNITIVE for goal nodes — simpler, but goal processing and experience processing intermix in the same subgraph priority queue. No independent scheduling.
- New GOAL_COGNITIVE compound — over-specified. Subgraph types are coarse categories, not fine-grained taxonomies.

**Rationale:** Subgraph types exist for independent scheduling and prioritization. Goals have different consolidation needs than experiences (resolution management, dependency tracking, affect-driven urgency). A dedicated type enables the right scheduling granularity.
**Sources:** SubgraphTypes.java, CuriositySignalGenerator, ConsolidationScheduler subgraph priority
**Exploration:** surfaced by review (R1-26)
**Status:** captured

---

## D10: Goal-conditioned retrieval mechanism

**Choice:** Graph proximity in MindMap, implemented as a ModulationFactor.

A `GoalRelevanceModulationFactor` implements `ModulationFactor<T>` and weights retrieved memories by their graph proximity to active goal nodes. Memories whose MindMap entity nodes are within N edges of a goal node receive higher modulation weight.

The mechanism leverages existing infrastructure:
- MindMap graph traversal (neighbors, edges) for proximity computation
- ModulationFactor SPI (`double apply(T item, ModulationProfile<T> profile)`) for retrieval weighting
- CognitiveProfile.resolve() already collects edges and memories for entity nodes

Graph proximity naturally captures goal relevance: memories directly associated with a goal (1 edge) are highly relevant; memories associated with a goal's dependency (2 edges) are moderately relevant; distant memories contribute less. The weighting decays with edge distance.

**Alternatives:**
- Embedding similarity between memory text and goal description — accurate but expensive (requires embedding computation during retrieval). May complement graph proximity for cold-start goals with few graph connections.
- Explicit tagging (memory recorded with goal reference) — requires upstream changes to memory recording. Only captures explicitly tagged memories, misses implicit relevance.
- Keyword matching — brittle, misses semantic relationships.

**Rationale:** Graph proximity is the natural mechanism for MindMap-based retrieval. It's computationally cheap (graph traversal, no LLM/embedding), leverages existing infrastructure, and improves as the goal graph densifies through consolidation.
**Trade-offs:** Cold-start goals (newly recognized, few graph connections) get minimal modulation benefit. Embedding similarity may supplement graph proximity for these cases. This is an implementation optimization, not a design change.
**Sources:** ModulationFactor.java (SPI), CognitiveProfile.resolve() (edge collection), MindMapStore.neighbors() (graph traversal)
**Exploration:** surfaced by review (R1-27)
**Status:** captured
