# Design Decisions — #692 Hypothesis Tracking

## D1: Ownership model

**Choice:** HypothesisTracker owns its CompositionInstance(s)
**Alternatives:**
- Stateless utility operating on externally-provided CompositionInstance — more flexible but caller must manage lifecycle and per-hypothesis state
- Owns but exposes read-only — middle ground, adds API surface for marginal benefit
**Rationale:** The tracker needs to manage per-hypothesis state (weights, elimination status, observation history). Owning the compositions keeps lifecycle clean and prevents external mutation from breaking invariants.
**Trade-offs:** Callers cannot share a composition between a tracker and other uses. They'd need a separate composition for non-hypothesis work.
**Sources:** CompositionInstance.java, MultiAgentInstance.java (same ownership pattern)
**Exploration:** quick
**Status:** captured

## D2: Hypothesis-to-composition mapping

**Choice:** One CompositionInstance per hypothesis
**Alternatives:**
- Shared composition with per-hypothesis slot variants — memory-efficient but conflates inference state; only works if hypotheses differ in one slot
- Single composition + mixture variable — compact but loses per-hypothesis conditional independence; can't do path elimination
**Rationale:** Each hypothesis needs independent inference state so that evidence updating one hypothesis doesn't contaminate others. Full isolation via separate CompositionInstances is the cleanest way to achieve this. Memory cost is N×(slots×JunctionTree), acceptable for typical hypothesis counts (5-15).
**Trade-offs:** Higher memory usage than shared-composition approaches. For very large compositions (>10 slots) with many hypotheses (>20), this could be expensive.
**Sources:** CompositionInstance.java (clone-per-hypothesis), MultiAgentInstance.java (one-slot-per-agent pattern)
**Exploration:** quick
**Status:** captured

## D3: Observation routing

**Choice:** Broadcast all observations to all viable hypotheses
**Alternatives:**
- Hypothesis-declared consumption — each hypothesis declares which variables it consumes; risks silent observation loss and breaks Bayesian premise
- Broadcast with relevance filtering — hypotheses mark observations as irrelevant; adds complexity for marginal benefit since irrelevant evidence produces uniform posteriors
**Rationale:** Standard Bayesian updating requires all hypotheses to evaluate the same evidence. The posterior naturally handles irrelevant observations (P(e|H) ≈ uniform → weight unchanged). Selective consumption would violate the mathematical foundation.
**Trade-offs:** All hypotheses pay the inference cost even for observations that don't change their weights. For expensive compositions, this could be noticeable.
**Sources:** Bayesian model averaging literature; BayesInstance.globalUpdate()
**Exploration:** quick
**Status:** captured

## D4: Weight update mechanism

**Choice:** Marginal likelihood scoring with Bayes' rule
**Alternatives:**
- Posterior divergence scoring — predictive but not standard Bayesian updating
- Log-odds accumulation — same math in log space; could be an implementation detail
**Rationale:** Textbook Bayesian model averaging: w_i ← w_i × P(evidence | H_i) / Z. The junction tree's normalization constant provides P(evidence | H_i) directly. Mathematically principled and well-understood.
**Trade-offs:** Numerical underflow for long observation sequences. Mitigate with periodic renormalization (already planned via normalize()). Log-odds accumulation (D4 alt) could be used internally if underflow becomes a problem.
**Sources:** BayesInstance.globalUpdate() (normalization constant available), Bayesian model selection literature
**Exploration:** quick
**Status:** captured

## D5: Elimination mechanism

**Choice:** Configurable posterior threshold with both soft and hard elimination
**Alternatives:**
- Relative ratio elimination — eliminate when N× less likely than leader; adapts but unstable when leader fluctuates
- No elimination, just weights — simpler but wastes computation on near-zero hypotheses
**Rationale:** Soft threshold (weight < configurable value, default 0.01) handles gradual evidence accumulation. Hard elimination handles impossible evidence (P(e|H) = 0). Both are standard. Eliminated hypotheses are retained in history for diagnostics but excluded from updates.
**Trade-offs:** Fixed threshold doesn't adapt to the number of hypotheses. A tracker with 100 hypotheses might eliminate too aggressively at 0.01. Mitigated by making the threshold configurable.
**Sources:** Bayesian model pruning literature
**Exploration:** quick
**Status:** captured

## D6: Module placement

**Choice:** In inference-bayes module
**Alternatives:**
- New inference-hypothesis module — cleaner separation but adds a module for 3-5 classes with no additional dependencies
- In caps-api or cognitive-index — wrong tier; hypothesis tracking is domain-generic, not cognitive-specific
**Rationale:** HypothesisTracker is the same architectural tier as MultiAgentInstance and InfluenceDiagramEngine: a consumer-level abstraction over the composition layer. Same module, same package, zero new dependencies.
**Trade-offs:** None significant. inference-bayes grows by ~5 classes but they're cohesive with the existing API.
**Sources:** inference-bayes module structure, MultiAgentInstance.java (same pattern)
**Exploration:** quick
**Status:** captured

## D7: Hypothesis definition API

**Choice:** HypothesisDefinition record + fluent builder
**Alternatives:**
- Callback-based configuration (Consumer<CompositionInstance>) — maximum flexibility but harder to serialize/inspect
- Implicit from variant keys — auto-generate from a discriminator slot's variants; convenient for simple cases but can't handle multi-slot hypotheses or prior overrides
**Rationale:** A record-based definition captures the hypothesis's identity (name, prior weight, variant activations, prior overrides) as inspectable data. The builder provides ergonomic construction. Follows the same pattern as CompositionBuilder.
**Trade-offs:** Less flexible than callbacks for exotic configurations. Mitigated by the prior-override mechanism which handles most cases.
**Sources:** CompositionBuilder.java (same builder pattern), NetworkSlot.variants (variant activation model)
**Exploration:** quick
**Status:** captured

## D8: Observation result type

**Choice:** ObservationResult record with weights, eliminated, leader, entropy, viable, isResolved
**Alternatives:**
- Just the weights map — minimal but pushes analysis onto every caller
- Event-based (listener) — useful for reactive systems but overkill for a pure-Java inference library
**Rationale:** The caller needs a snapshot of the hypothesis space after each observation. A record bundles all derived quantities (leader, entropy, eliminated set, resolution status) so callers don't recompute them.
**Trade-offs:** Record creation per observation. Negligible cost relative to inference.
**Sources:** CompositionStats.java (same snapshot-result pattern)
**Exploration:** quick
**Status:** captured
