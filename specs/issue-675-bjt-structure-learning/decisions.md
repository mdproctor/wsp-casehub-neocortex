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
