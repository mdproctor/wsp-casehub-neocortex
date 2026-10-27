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

## D3: Hill-climbing — three operations + random restarts

**Choice:** Add/remove/reverse edge operations scored by BIC (via ModelSelector.bic()). Accept greatest BIC improvement per step. Random restarts (configurable count, default 5) from empty graph with shuffled operation order. StructuralConstraints gate all operations.
**Alternatives:**
- No restarts — simpler but vulnerable to local optima for larger networks
- TABU search — more sophisticated escape from local optima but significantly more complex state management
**Rationale:** Random restarts are the standard approach in BN hill-climbing (Koller & Friedman, Heckerman et al.). Simple, effective, configurable tradeoff between quality and compute time.
**Trade-offs:** Restart count × operations per step = total BIC evaluations. Each BIC evaluation requires ParameterLearner.fit() + logLikelihood(). For large networks or many restarts, this is compute-intensive. Acceptable for the target scale (< 30 variables).
**Sources:** Heckerman, Geiger, Chickering (1995) — Learning Bayesian Networks; ModelSelector.bic() from #676
**Exploration:** quick
**Status:** captured

## D4: Independence test — @FunctionalInterface with adaptive default

**Choice:** IndependenceTest @FunctionalInterface with IndependenceResult record. Static factories gTest(alpha), fisherExact(alpha), adaptive(alpha). Adaptive selects Fisher's when expected count < 5, G-test otherwise.
**Alternatives:**
- Abstract class with shared contingency table logic — locks to tabular data, prevents future non-tabular tests
**Rationale:** Same pattern as FoldSplitter. Adaptive default means callers don't need to think about sample sizes. Contingency table building is a shared utility method, not a class hierarchy.
**Trade-offs:** FunctionalInterface can't enforce that implementations handle the conditioning set correctly — this is a usage discipline, not a type safety issue
**Sources:** FoldSplitter.java from #676 — same pattern; Agresti (2002) — chi-squared and Fisher's exact for contingency tables
**Exploration:** quick
**Status:** captured

## D5: Hill-climbing BIC scoring — decomposable local scores

**Choice:** Decomposable BIC with per-variable local scoring. Compute local scores once for all variables, recompute only affected variable(s) when evaluating a candidate edge operation. Cache contingency tables (parent-config counts) per variable. ModelSelector.bic() used for whole-network verification, not inner loop.
**Alternatives:**
- Full refit per candidate — O(V) slower per evaluation, impractical beyond toy networks (~1140 candidates per step for 20 variables)
**Rationale:** Decomposable local scoring is standard in all BN structure learning implementations. An add/remove/reverse touches at most 2 variables' parent sets. Each candidate evaluation is O(n × outcomes²) instead of O(n × V × outcomes²).
**Trade-offs:** More complex implementation (local score cache, contingency table management). Worth it — makes the difference between seconds and minutes for 20+ variable networks.
**Sources:** Koller & Friedman (2009) §18.4 — decomposable scores; Chickering (2002) — optimal search with BIC
**Depends on:** D3 (hill-climbing operations)
**Exploration:** quick
**Status:** captured
