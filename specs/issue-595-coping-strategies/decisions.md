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

## D2: Coping subsumes regulation

**Choice:** EMA coping IS the strategy selection layer. The existing EmotionRegulationStrategy becomes a downstream execution mechanism that enacts the selected coping strategy.
**Alternatives:**
- Separate layers, coping constrains — keeps coping and regulation as distinct selections, coping narrows the regulation space. But creates two independent strategy selectors for overlapping territory.
- Merge into unified taxonomy — single expanded strategy enum combining EMA + Gross. Requires reworking existing regulation code for unclear benefit.
**Rationale:** EMA's 12 strategies and Gross's 10 strategies overlap significantly (COGNITIVE_CHANGE ≈ positive reinterpretation, SITUATION_SELECTION ≈ avoidance, SOCIAL_SUPPORT_SEEKING ≈ seek instrumental support). Two independent selectors would fight over the same territory. Coping selects "positive reinterpretation"; regulation enacts it via COGNITIVE_CHANGE. Clean layering: coping decides what to change, regulation executes the change.
**Trade-offs:** RegulationStrategyPredictor and EmotionRegulationGenerationPhase need refactoring to receive coping strategy as input rather than independently selecting. Existing regulation tests may need updating.
**Depends on:** D1 (full EMA provides the rich strategy taxonomy that makes subsumption natural)
**Sources:** Marsella & Gratch (2009) EMA coping taxonomy; existing EmotionRegulationStrategy.java (10 strategies)
**Exploration:** quick
**Status:** captured

## D3: Intra-tick micro-loop for reappraisal

**Choice:** Within a single tick, run appraisal → coping selection → modify interpretation → re-evaluate, max N iterations, converging when no new coping opportunity exceeds threshold.
**Alternatives:**
- Cross-tick accumulation — coping effects visible only next tick. Simpler but coping responses are always one tick delayed; a character can't reappraise and adjust within the same moment.
- Hybrid single reappraisal — exactly 2 passes max. Captures first-order effect but misses strategy chaining (try planning → fail → shift to acceptance).
**Rationale:** Faithful to EMA's continuous model where coping modifies the causal interpretation and appraisal feature detectors automatically re-evaluate. The iteration cap bounds cost. Strategy chaining (try → fail → try different strategy) is a key behavioral differentiator.
**Trade-offs:** More complex pipeline execution; needs convergence detection and iteration cap to prevent runaway. But bounded cost and richer behavioral dynamics.
**Depends on:** D1 (full EMA requires strategy chaining), D2 (coping drives regulation, so the loop controls the full coping→regulation flow)
**Sources:** Marsella & Gratch (2009) §Coping — continuous reappraisal model
**Exploration:** quick
**Status:** captured

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

**Choice:** A static mapping table: each EMA coping strategy maps to one or more EmotionRegulationStrategy values as its execution mechanism. Coping decides WHAT to change, regulation executes HOW.
**Alternatives:**
- LLM produces both — loses clean layering, existing regulation code becomes dead
- Coping replaces regulation entirely — discards working code and Gross-theoretical grounding
**Rationale:** Clean separation of concerns. The mapping is well-defined by the overlap between the two taxonomies (positive reinterpretation → COGNITIVE_CHANGE, avoidance → SITUATION_SELECTION, seek support → SOCIAL_SUPPORT_SEEKING). The regulation execution infrastructure (prompts, effectiveness tracking, fatigue) remains valuable.
**Trade-offs:** The mapping may not be 1:1 for all strategies. Some EMA strategies (wishful thinking, shift responsibility) don't have clean Gross equivalents — these produce direct narrative effects rather than routing through regulation.
**Depends on:** D2 (coping subsumes regulation — this decision defines the interface)
**Sources:** EMA coping taxonomy (12 strategies); EmotionRegulationStrategy enum (10 values)
**Exploration:** quick
**Status:** captured

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
