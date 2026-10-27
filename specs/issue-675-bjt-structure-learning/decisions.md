## D1: Overall architecture — StructureLearner facade + internal algorithm classes

**Choice:** Single StructureLearner facade with static pc() and hillClimbing() methods. Internal package-private PcAlgorithm and HillClimbingSearch classes. ConditionalIndependenceTest interface with GTest and FisherExactTest. Shared StructuralConstraints record. StructureResult output with toNetworkSpec() and toBayesNetwork(data).
**Alternatives:**
- Separate top-level classes per algorithm — no unified entry point, makes #677 fusion harder
- SPI interface with implementations — polymorphism overhead for a case where caller always knows which algorithm
**Rationale:** Matches existing static utility pattern (ModelValidator, ModelSelector). Minimal public API, clean internal decomposition. Single import point for #677.
**Trade-offs:** Two algorithms behind one class may grow the class; mitigated by delegation to internal classes
**Sources:** ModelValidator.java, ModelSelector.java — existing static utility patterns; NetworkElicitor.java — NetworkSpec output pattern
**Exploration:** quick
**Status:** captured

## D2: PC algorithm — standard PC with Meek's 4 orientation rules

**Choice:** Standard PC: skeleton discovery via CI tests, v-structure detection, Meek's R1-R4 iterative orientation. Output is a CPDAG — undirected edges get SpecStatus.PROPOSED with rationale "orientation undetermined — equivalence class."
**Alternatives:**
- Conservative PC (CPC) — verifies v-structures against all separating sets; more robust but stores all separating sets, significantly more memory
- PC-stable — order-independent variant; ~2x CI tests for robustness to variable ordering
**Rationale:** Standard PC is the textbook baseline. CPC and PC-stable are refinements that address robustness — add when benchmarks show they matter. CPDAG output gives #677 the right hooks for LLM-assisted orientation.
**Trade-offs:** Result depends on variable ordering (PC-stable fixes this). V-structure detection may have false positives from CI test errors (CPC fixes this). Both are acceptable for a first implementation.
**Sources:** Spirtes, Glymour, Scheines (2000) — Causation, Prediction, and Search; Meek (1995) — orientation rules
**Exploration:** quick
**Status:** captured
