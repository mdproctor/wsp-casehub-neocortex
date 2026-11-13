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

## D2: Prompt design — dual path

**Choice:** Path A (user prompt) appends axis values + instruction after description. Path C (system prompt) rebuilds the opening with personality frame + tension narrative before topology listing.
**Alternatives:**
- User prompt only for all agents — misses interpretive framing for complex personalities
- System prompt only for all agents — unnecessary cost for simple personalities
- Post-processing weights instead of prompt framing — can't capture interpretive differences (multiplication doesn't equal perception)
**Rationale:** Path A is a lightweight filter: "Classify as this character would perceive it." Sufficient when axes don't conflict. Path C embeds a tension narrative that tells the LLM HOW the conflict shapes perception — the LLM inhabits the frame rather than applying it. Static narrative lookup table (6 entries) keyed by tension pair. System prompt is rebuilt per agent; per-agent sessions already exist so no additional cache cost.
**Trade-offs:** Path C requires per-agent system prompt construction (minor cost). Tension narratives are hand-written (bounded to ~6 entries, each 1-2 sentences).
**Depends on:** D1 (tension score determines which path)
**Sources:** LlmSituationClassifier.java prompt templates, appraisal theory (Lazarus — personality as lens, not filter)
**Exploration:** deep-analysis (first-principles: system prompt = identity, user prompt = instruction)
**Status:** captured

## D3: Personality data flow

**Choice:** Pass agentId in ClassificationContext (field already exists), resolve CognitiveDefaults inside LlmSituationClassifier via an injected CognitiveDefaultsRegistry
**Alternatives:**
- Pass full CognitiveDefaults through ClassificationContext — couples the SPI to cognitive-index types, heavy for what's needed
- Pass DispositionAxes through ClassificationContext — lighter but still couples SPI to cognitive-index
- Resolve personality in BehavioralSynthesisPhase and pass as metadata map — stringly-typed, loses type safety
**Rationale:** ClassificationContext already has agentId. The classifier is the consumer that needs personality — it should resolve what it needs from the registry, not receive pre-digested data. BehavioralSynthesisPhase already has defaultsRegistry; passing it to the classifier at construction (alongside topology) keeps the classify() SPI signature unchanged. The only call-site change is `ClassificationContext.of(tenantId)` → `ClassificationContext.of(tenantId, agentId)`.
**Trade-offs:** LlmSituationClassifier gains a dependency on CognitiveDefaultsRegistry (nullable, graceful degradation to personality-agnostic when null).
**Sources:** ClassificationContext.java, BehavioralSynthesisPhase.java L143/L435 call sites
**Exploration:** quick
**Status:** captured

## D4: Eval test design

**Choice:** 4-profile comparison eval with ambiguous observation, measuring inter-profile activation variance, tension dual-activation, and baseline divergence against personality-agnostic control
**Alternatives:**
- Binary A/B test (with/without personality) — doesn't distinguish path A from path C value
- Per-scenario battery (many observations, one profile) — measures consistency not differentiation
**Rationale:** The research question is whether personality produces divergent CAPS activations. That requires multiple personalities on the same observation with a control. Four profiles cover: two simple (path A, no tension), one complex (path C, high tension), one moderate baseline. The ambiguous observation ensures personality-shaped interpretation is possible — unambiguous observations should produce the same activations regardless of personality. Three metrics directly answer the three research questions from #941.
**Trade-offs:** LLM-dependent (results vary between runs). Single ambiguous observation may not generalise — could expand to 2-3 observations in follow-up. Requires SessionPipeline (can't run without LLM access).
**Depends on:** D2 (prompt design), D3 (data flow)
**Sources:** Issue #941 research questions and success criteria
**Exploration:** quick
**Status:** captured
