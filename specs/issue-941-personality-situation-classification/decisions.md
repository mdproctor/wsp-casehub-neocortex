# Decisions — #941 Personality-Aware Situation Classification

## D1: Tension scoring mechanism

**Choice:** Static lookup table of conflicting axis value pairs, max tension > 0.5 triggers path C
**Alternatives:**
- Numeric distance on ordinal scale — axes are categorical, not ordinal; forces false gradients
- LLM-evaluated tension — expensive, non-deterministic, overkill for a routing heuristic
**Rationale:** Disposition axes have 3 categorical values each. Tension is a named psychological conflict between specific value combinations, not a continuous quantity. A lookup table is principled (each pair has a cited rationale), deterministic, and zero-cost at runtime.
**Trade-offs:** New tension pairs require manual table entries. Bounded to 5-axis × 3-value space (15 possible pairs, ~6 are genuinely conflicting).
**Sources:** DispositionAxes.java, CognitiveDerivationEngine.java axis mappings, appraisal theory (Lazarus — concerns shape perception)
**Exploration:** deep-analysis (first-principles discussion in conversation)
**Status:** captured
