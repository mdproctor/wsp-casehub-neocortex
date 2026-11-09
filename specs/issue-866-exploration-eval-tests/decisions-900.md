## D1: Separate test class

**Choice:** New `CapacityFidelityEvalTest` class in caps-llm-classifier eval package
**Alternatives:**
- Extend CognitiveExplorationEvalTest — conflates exploration behaviour with problem-solving fidelity
**Rationale:** Different evaluation focus, different problem structure, distinct validation of the echo approach. Separate results are easier to interpret.
**Trade-offs:** One more file; minimal since infrastructure is shared.
**Sources:** CognitiveExplorationEvalTest.java, issue #900
**Exploration:** quick
**Status:** captured

## D2: Test matrix structure

**Choice:** Focused — 3 targeted comparisons (one per capacity dimension) + baseline + blind differentiation
**Alternatives:**
- Full 3×4 matrix (12 scenarios) — mostly tests irrelevant combinations
**Rationale:** Each capacity dimension maps to one problem type. Testing low associativeReach on a syllogism adds no signal. Focused tests maximize signal-to-noise.
**Trade-offs:** Less coverage of cross-dimension effects; acceptable since #866 already covers capacity in exploration context.
**Sources:** CognitiveCapacityConfig.java, issue #900 problem types
**Exploration:** quick
**Status:** captured
