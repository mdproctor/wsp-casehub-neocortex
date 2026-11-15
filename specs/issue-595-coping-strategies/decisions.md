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
