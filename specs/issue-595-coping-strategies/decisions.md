# Design Decisions — Issue #595 Coping Strategies

## D1: Full EMA over simplified 3-mode coping

**Choice:** Implement the full EMA (Marsella & Gratch 2009) coping model with multiple specific coping strategies, not a simplified 3-mode (approach/reframe/avoid) classification.
**Alternatives:**
- Simplified 3-mode — lower implementation cost but creates an artificial low-resolution bottleneck between high-resolution Scherer appraisal and high-resolution Gross regulation
**Rationale:** The architecture already implements detailed Scherer appraisal (4 SEC checks with multiple dimensions) and detailed Gross regulation (10 strategies). A 3-mode coping layer would lose within-mode differentiation (e.g., "wishful thinking" vs "positive reinterpretation" are both emotion-focused but produce different character behavior), sequential coping attempts (try → fail → switch), and personality-specific strategy mapping.
**Trade-offs:** Higher implementation complexity; EMA is a substantial system. But the cognitive pipeline demands matching resolution across all layers.
**Sources:** Marsella & Gratch (2009) EMA paper; existing SchererAppraisalStrategy.java, EmotionRegulationStrategy.java (10 strategies)
**Exploration:** quick
**Status:** captured

## D2: Coping subsumes intrapersonal regulation

**Choice:** EMA coping IS the strategy selection layer for intrapersonal regulation. The five Gross strategies plus the three intrinsic interpersonal strategies (SOCIAL_SUPPORT_SEEKING, SOCIAL_SHARING, SOCIAL_WITHDRAWAL) become downstream execution mechanisms that enact the selected coping strategy. The two extrinsic interpersonal strategies (CO_REGULATION, DELIBERATE_PROVOCATION) remain outside the coping model — they regulate another agent's emotions, not the coping agent's own, and continue to be selected through the existing social cognition pathway in EmotionRegulationTickParticipant.
**Alternatives:**
- Separate layers, coping constrains — keeps coping and regulation as distinct selections, coping narrows the regulation space. But creates two independent strategy selectors for overlapping territory.
- Merge into unified taxonomy — single expanded strategy enum combining EMA + Gross. Requires reworking existing regulation code for unclear benefit.
- Coping subsumes ALL regulation — extends EMA to include extrinsic strategies. But extrinsic regulation is qualitatively different: acting on another's emotions, not coping with one's own distress. Forcing it into a coping model would be a category error.
**Rationale:** EMA is explicitly intrapersonal — it models how an agent copes with its own distress. The overlap between EMA and Gross is in this intrapersonal space (COGNITIVE_CHANGE ≈ positive reinterpretation, SITUATION_SELECTION ≈ avoidance, SOCIAL_SUPPORT_SEEKING ≈ seek instrumental support). Two independent selectors would fight over the same territory. Coping selects "positive reinterpretation"; regulation enacts it via COGNITIVE_CHANGE. Clean layering: coping decides what to change, regulation executes the change. Extrinsic strategies (CO_REGULATION, DELIBERATE_PROVOCATION) are selected through social context signals (interacting agents, relational schemas, distress trajectories) — a fundamentally different selection mechanism than intrapersonal coping.
**Predictor fate:** RegulationStrategyPredictor is retired as a strategy SELECTOR — its role is absorbed by CopingStrategyPredictor (D6). RegulationDefaults is retained: its capacity scores (reappraisalCapacity, suppressionCapacity, redirectTendency) inform EXECUTION QUALITY in EmotionRegulationGenerationPhase, not strategy selection. CopingDefaults (D6) encodes personality PREFERENCES; RegulationDefaults encodes personality CAPACITIES. These are distinct: what you tend to do vs. how well you do it. The safety hard gate (fatigue/intensity → ATTENTIONAL_DEPLOYMENT) moves to a pre-coping gate, preserving its unconditional override behavior.
**Trade-offs:** EmotionRegulationGenerationPhase needs refactoring to receive coping strategy as input rather than independently selecting. RegulationStrategyPredictor selection logic is retired. Existing regulation tests need updating. The regulation execution infrastructure (prompts, effectiveness tracking, fatigue, CAPS integration) is preserved.
**Depends on:** D1 (full EMA provides the rich strategy taxonomy that makes subsumption natural)
**Sources:** Marsella & Gratch (2009) EMA coping taxonomy; Zaki & Williams (2013) intrinsic/extrinsic distinction; existing EmotionRegulationStrategy.java (10 strategies); EmotionRegulationTickParticipant.java social strategy validation
**Exploration:** quick
**Status:** revised
**Revised in:** R1 — scoped to intrapersonal regulation (R1-02), clarified predictor fate and defaults distinction (R1-08)

## D3: Intra-tick micro-loop for reappraisal

**Choice:** Within a single tick, run appraisal → coping selection → modify interpretation → re-evaluate, max N iterations, converging when no new coping opportunity exceeds threshold. Re-evaluation within the micro-loop uses keyword-based SEC checks (CopingCheck, RelevanceCheck, ImplicationCheck, NormativeCheck), not LLM-based implementations. Each iteration costs one LLM call for narrative reinterpretation; keyword SEC checks are zero-cost. The micro-loop is complementary to cross-tick regulation monitoring — RegulationMonitor continues to detect effectiveness decline across ticks and signal strategy switches.
**Alternatives:**
- Cross-tick accumulation — coping effects visible only next tick. Simpler but coping responses are always one tick delayed; a character can't reappraise and adjust within the same moment. The existing cross-tick RegulationMonitor handles REACTIVE strategy switching (detect failure over 3+ ticks, signal switch). The micro-loop handles PROACTIVE cognitive coping (explore reinterpretations within a single moment). These serve different psychological functions.
- Hybrid single reappraisal — exactly 2 passes max. Captures first-order effect but misses strategy chaining (try planning → fail → shift to acceptance).
**Rationale:** Faithful to EMA's continuous model where coping modifies the causal interpretation and appraisal feature detectors automatically re-evaluate. The iteration cap bounds cost. Strategy chaining (try → fail → try different strategy) is a key behavioral differentiator. Keyword-based SEC checks in the micro-loop follow the semantic resolution boundary: LLM resolves narrative meaning (reinterpretation), keyword checks detect signal words in the resolved text (mechanical evaluation of resolved values). This is the same principle as D4's "SEC checks evaluate the transformed text (mechanical on resolved interpretation)."
**Cost quantification:** Initial appraisal: 0–3 LLM calls (depends on SEC check implementations configured). Micro-loop: +1 LLM call per iteration (narrative reinterpretation only). With N=3 cap: +3 LLM calls worst case. Regulation execution: 1 LLM call. Total per tick: 4–7 LLM calls (vs current 4–5 without coping). Convergence typically occurs in 1–2 iterations; hitting the cap is the exception.
**Trade-offs:** More complex pipeline execution; needs convergence detection and iteration cap to prevent runaway. But bounded cost and richer behavioral dynamics.
**Depends on:** D1 (full EMA requires strategy chaining), D2 (coping drives regulation, so the loop controls the full coping→regulation flow)
**Sources:** Marsella & Gratch (2009) §Coping — continuous reappraisal model; existing keyword-based SecCheck implementations (CopingCheck.java, RelevanceCheck.java, ImplicationCheck.java, NormativeCheck.java)
**Exploration:** quick
**Status:** revised
**Revised in:** R1 — added explicit SEC check implementation specification, cost quantification, and cross-tick complementarity (R1-03, R1-07)

## D4: Narrative as causal interpretation in CopingState

**Choice:** The interpretation narrative is the mutable causal interpretation. CopingState carries: reinterpretable narrative (starts as raw situation, transformed each iteration by LLM), working SEC dimensions (re-derived mechanically each iteration), working emotions, and accumulated persistent effects (goal operations, drive modulations, attention directives) dispatched after convergence.
**Alternatives:**
- Extend AppraisalContext — AppraisalContext is immutable, doesn't naturally carry reinterpretation. Some coping effects must persist, so treating all as ephemeral is unfaithful.
- MindMap as causal interpretation — writing intermediate coping experiments to persistent storage is expensive and polluting. Wishful thinking shouldn't permanently change beliefs.
- New CopingInterpretation record — ends up being the same as CopingState but without the clear rationale for why narrative is the core.
**Rationale:** In an LLM-based architecture, "how the character sees the situation" is naturally text. LLM transforms the narrative (semantic work), SEC checks evaluate the transformed text (mechanical on resolved interpretation). This follows the semantic resolution boundary: LLM resolves semantics, mechanical computation evaluates resolved values. Persistent effects accumulate during the loop but only dispatch after convergence — no pollution of durable state with intermediate coping experiments.
**Trade-offs:** Reappraisal requires re-running SEC checks on each reinterpreted narrative (LLM cost per iteration). But this is bounded by the iteration cap from D3.
**Depends on:** D3 (intra-tick micro-loop defines the loop that CopingState serves)
**Sources:** Marsella & Gratch (2009) §Causal interpretation; D4-exploration.md (deep analysis)
**Exploration:** deep-analysis
**Status:** captured

## D5: Strategy-to-execution table for regulation mapping

**Choice:** A static mapping table routes each EMA coping strategy to either regulation execution OR direct effects. Not all coping strategies route through regulation — some produce goal operations, drive modulations, or narrative transformations directly. The table covers all EMA strategies with explicit routing for each.
**Mapping table:**

| EMA Coping Strategy | Route | Target |
|---|---|---|
| Positive reinterpretation | → Regulation | COGNITIVE_CHANGE |
| Planning | → Direct effect | Goal operation (create plan goal) |
| Seek instrumental support | → Regulation | SOCIAL_SUPPORT_SEEKING |
| Seek emotional support | → Regulation | SOCIAL_SHARING |
| Avoidance | → Regulation | SITUATION_SELECTION |
| Mental disengagement | → Regulation | ATTENTIONAL_DEPLOYMENT |
| Suppression | → Regulation | RESPONSE_MODULATION |
| Active confrontation | → Regulation | SITUATION_MODIFICATION |
| Acceptance | → Direct effect | Drive modulation (reduce drive intensity) + narrative |
| Denial | → Direct effect | Narrative transformation (refuse to acknowledge) |
| Wishful thinking | → Direct effect | Narrative transformation (alter perceived likelihood) |
| Shift responsibility | → Direct effect | Narrative transformation (reframe causal attribution) |
| Resignation | → Direct effect | Goal operation (drop goal) |
| Procrastination | → Direct effect | Goal operation (defer goal) |

**Alternatives:**
- LLM produces both — loses clean layering, existing regulation code becomes dead
- Coping replaces regulation entirely — discards working code and Gross-theoretical grounding
**Rationale:** Clean separation of concerns. Strategies with Gross equivalents route through the regulation execution infrastructure, preserving its prompts, effectiveness tracking, and fatigue mechanics. Strategies without Gross equivalents produce direct effects on CopingState — goal operations, drive modulations, and narrative transformations — which dispatch after convergence (D4). This is not incompleteness in the mapping; it reflects a genuine categorical difference between strategies that regulate emotion expression and strategies that modify the cognitive situation.
**Trade-offs:** Two routing paths (regulation vs direct effect) add complexity. But the alternative — forcing all strategies through regulation — would require inventing artificial regulation equivalents for "resignation" or "denial," polluting the Gross taxonomy.
**Depends on:** D2 (coping subsumes intrapersonal regulation — this decision defines the interface)
**Sources:** Marsella & Gratch (2009) EMA coping taxonomy; EmotionRegulationStrategy enum (10 values)
**Exploration:** quick
**Status:** revised
**Revised in:** R1 — expanded mapping table to cover all EMA strategies with explicit routing (R1-06)

## D6: Hybrid CopingDefaults + LLM for personality-coping mapping

**Choice:** CopingDefaults derived from Big Five via CDE (following RegulationDefaults pattern), feeding a CopingStrategyPredictor that filters by controllability then applies personality bias. LLM makes final selection with full situational context, optionally pinned by the predictor.
**Alternatives:**
- CopingDefaults only (no LLM) — personality signal alone can't assess situational viability. A conscientious character can't plan their way out of an uncontrollable situation. Violates semantic resolution boundary.
- LLM prompt only (no predictor) — personality→coping mapping becomes implicit and variable across calls. Loses observability and consistency. Ignores that personality tendency is already numerically resolved.
**Rationale:** Strategy selection involves two independently-resolvable signals: personality disposition (numeric, stable → mechanical) and situational viability (semantic, variable → LLM). The predictor handles the numeric signal, the LLM handles the semantic. This matches EMA's selection sequence (filter viable → personality resolves ties) and our architecture's established pattern (RegulationStrategyPredictor → EmotionRegulationGenerationPhase). Published Big Five→coping correlations are moderate-to-strong (same quality as Barańczuk 2019 for regulation).
**Trade-offs:** One more component to maintain (CopingStrategyPredictor + CopingDefaults). But follows established pattern and provides observability.
**Depends on:** D1 (full EMA strategy set), D2 (coping subsumes regulation), D4 (CopingState carries the context for selection)
**Sources:** Marsella & Gratch (2009) §Strategy selection; Connor-Smith & Flachsbart (2007) Big Five→coping meta-analysis; existing RegulationDefaults.java pattern; D6-exploration.md (deep analysis)
**Exploration:** deep-analysis
**Status:** captured

## D7: Coping SEC check feeds coping layer; keyword re-evaluation in micro-loop

**Choice:** The existing Scherer coping SEC check (evaluating CONTROLLABILITY and ADJUSTABILITY) provides input to the coping layer. In the micro-loop, the keyword-based CopingCheck re-evaluates controllability on the reinterpreted narrative. This is an intentional feedback loop: coping modifies the narrative → controllability re-evaluated → changed strategy viability → possibly different coping strategy → further narrative modification. The loop is bounded by D3's iteration cap and convergence detection.
**Alternatives:**
- Freeze controllability from initial appraisal — coping layer reads the initial controllability but never updates it. Simpler, but unfaithful to EMA: positive reinterpretation SHOULD change perceived controllability. A narrative that transforms "I'm trapped and helpless" to "I have options I haven't tried" should yield higher controllability scores.
- LLM-based controllability re-evaluation in micro-loop — higher fidelity but prohibitively expensive (adds an LLM call per iteration per check).
- Remove coping SEC check from appraisal entirely — eliminate overlap. But the coping SEC check legitimately shapes emotion mapping: controllability distinguishes ANGER (controllable negative) from FEAR (uncontrollable negative). Removing it changes emotion generation.
**Rationale:** The relationship between the coping SEC check and the coping layer is sequential and unidirectional in the initial pass: SEC check produces controllability → emotion mapping → emotions → coping layer filters by controllability. In the micro-loop, the keyword-based re-evaluation IS the reappraisal feedback mechanism. The keyword CopingCheck evaluates signal words ("can", "able", "trapped", "helpless") in the reinterpreted narrative, providing a lightweight but meaningful controllability signal. Stability is guaranteed: keyword checks are deterministic (same text → same score), the iteration cap bounds the loop, and convergence detection halts when no new coping opportunity exceeds threshold.
**Depends on:** D3 (micro-loop), D4 (narrative as mutable interpretation)
**Sources:** SchererAppraisalStrategy.java (coping SEC check injection), CopingCheck.java (keyword implementation), EmotionMapper.java (controllability → emotion type mapping)
**Exploration:** surfaced by review
**Status:** captured

## D8: CognitiveDefaults structural growth — defer to future refactoring

**Choice:** Adding copingDefaults to CognitiveDefaults (making 23 fields) follows the existing pattern. A structural refactoring into nested config groups is deferred to a separate issue.
**Alternatives:**
- Refactor CognitiveDefaults now — group into nested records (e.g., CognitionCapabilities containing regulationDefaults, copingDefaults, capacityConfig, cognitiveResourcePoolConfig). Architecturally cleaner but cross-cutting: every CognitiveDefaultsParser, every withX() method, every test that constructs CognitiveDefaults, and every YAML config that feeds it.
- Don't add copingDefaults — store coping config separately. Breaks the established CDE (CognitiveDefaultsExtractor) pattern where all personality-derived defaults flow through a single pipeline.
**Rationale:** CognitiveDefaults has grown incrementally as the cognitive architecture matured. The 22→23 field addition is not the tipping point — the record was already at this scale. The correct fix is a structural refactoring of CognitiveDefaults itself, not a scope change to the coping work. Filed for separate resolution.
**Depends on:** D6 (CopingDefaults existence)
**Sources:** CognitiveDefaults.java (22 record components, 15+ withX() methods)
**Exploration:** surfaced by review
**Status:** captured

## D9: Quarkmind compatibility — coping is config-gated

**Choice:** The coping system is scoped to conversational-speed agents. Quarkmind (millisecond game-loop) controls activation through CognitionConfig gating. The coping system is not activated unless explicitly configured.
**Alternatives:**
- Make coping millisecond-compatible — strip LLM calls, use only mechanical evaluation. Gutted: without LLM narrative reinterpretation, there is no reappraisal. The micro-loop would be purely mechanical keyword-matching, which is not coping.
- Exclude coping from cognition-api — put it in a separate module. Breaks the layering: coping sits between appraisal and regulation in the cognitive pipeline, not as an optional sidecar.
**Rationale:** The cognitive pipeline (L25) is already config-gated: `CognitionConfig.regulationEnabled()` gates regulation, `CognitionConfig.appraisalEnabled()` gates appraisal. A `CognitionConfig.copingEnabled()` flag follows the same pattern. Quarkmind uses the casehub harness pattern for case/work management at game-loop speed; it does not wire the full cognitive pipeline. The LLM-dependent cognitive stack (appraisal, regulation, coping) operates at conversational speed — this is inherent to any LLM-based cognitive architecture and is not specific to coping.
**Depends on:** D3 (micro-loop is LLM-dependent)
**Sources:** CognitionConfig.java (existing enable/disable gates), APPLICATIONS.md (quarkmind description), ARC42STORIES.MD §5 L25 ("casehub only")
**Exploration:** surfaced by review
**Status:** captured
