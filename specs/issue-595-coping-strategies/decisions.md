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
