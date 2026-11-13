# Decisions — #941 Personality-Aware Situation Classification

## D1: Tension scoring mechanism

**Choice:** Static lookup table of conflicting axis value pairs, max tension > 0.5 triggers path C
**Alternatives:**
- Numeric distance on ordinal scale — axes are categorical, not ordinal; forces false gradients
- LLM-evaluated tension — expensive, non-deterministic, overkill for a routing heuristic
**Rationale:** Disposition axes have 3–4 categorical values each (conflictMode has 4: cooperative, competitive, analytical, avoidant; the other four axes have 3 each). Tension is a named psychological conflict between specific value combinations, not a continuous quantity. A lookup table is principled (each pair has a cited rationale), deterministic, and zero-cost at runtime. This adds classification-level personality influence (how situations are perceived), complementing the existing propagation-level influence in the CAPS topology's disposition_modifiers (how activations propagate through the network). The dual-level design is intentional: Lazarus's appraisal theory models personality as shaping both what we perceive (primary appraisal → classification) and how we respond (secondary appraisal → network propagation). CAPS convergence parameters (activation_clamp: [-1, 1]) bound the combined effect.
**Trade-offs:** New tension pairs require manual table entries. The value space is 5 axes × 3–4 values each (3 × 3 × 3 × 3 × 4 = 324 total axis-value combinations per agent, with C(5,2) = 10 cross-axis pairs). The genuinely conflicting pairs are ~6, empirically determined by which specific value combinations create interpretive tension.
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

**Choice:** Pass disposition axis values through the existing `Map<String, String> metadata` parameter on `SituationClassifier.classify()`. Caller serializes DispositionAxes values as metadata entries (keys: `disposition.socialOrient`, `disposition.ruleFollowing`, `disposition.riskAppetite`, `disposition.autonomy`, `disposition.conflictMode`). The classifier reads axis values from metadata and performs tension scoring, narrative lookup, and path routing internally. agentId in ClassificationContext continues to serve session identity.
**Alternatives:**
- Inject CognitiveDefaultsRegistry into LlmSituationClassifier — creates new compile-time dependency caps-llm-classifier → cognitive-index; couples classifier to a specific registry implementation; architecturally significant module boundary violation
- Pass full CognitiveDefaults through ClassificationContext — couples the SPI to cognitive-index types, heavy for what's needed
- Pass DispositionAxes through ClassificationContext — lighter but still couples SPI to cognitive-index types
**Rationale:** The metadata map is already designed for passing extensible context to classifiers and is stringly-typed by design (it already carries event-type, cognitiveKind, salience-multiplier as string key-value pairs). Axis values are categorical string labels by nature. The classifier owns all personality-to-prompt logic (tension scoring, narrative lookup, path routing) — the caller only provides raw axis data, not pre-processed tension info. No new module dependencies. No SPI signature changes. Works for any SituationClassifier implementation. The 4 production call sites using `ClassificationContext.of(tenantId)` are: BehavioralSynthesisPhase.java L145/L436 and DriveProfileDerivationPhase.java L196/L214. CognitionObservationBuilder.java L520 already passes agentId via `ClassificationContext.of(tenantId, agentId)`. See D6 for which call sites get personality-aware metadata.
**Trade-offs:** Stringly-typed axis data — mitigated by well-known key naming convention (`disposition.*`) and the classifier logging warnings for unrecognized axis values in the tension lookup. Requires each personality-aware call site to extract axes from CognitiveDefaults and put them in the metadata map.
**Sources:** ClassificationContext.java, SituationClassifier.java, BehavioralSynthesisPhase.java L145/L436, DriveProfileDerivationPhase.java L196/L214, CognitionObservationBuilder.java L520, caps-llm-classifier/pom.xml (no cognitive-index dependency)
**Exploration:** quick → revised after review
**Status:** revised (R1: metadata approach accepted over registry injection — eliminates caps-llm-classifier → cognitive-index dependency, keeps SPI implementation-agnostic)

## D4: Eval test design

**Choice:** Multi-profile comparison eval with observations from at least 4 distinct CAPS input categories, temperature=0, null hypothesis control, deterministic mechanism tests, and threshold sensitivity analysis
**Alternatives:**
- Binary A/B test (with/without personality) — doesn't distinguish path A from path C value
- Per-scenario battery (many observations, one profile) — measures consistency not differentiation
- Single observation prototype — insufficient to establish systematic divergence
**Rationale:** The three research questions from #941: (1) Does personality-aware classification improve drive differentiation beyond what overlap filtering provides? (2) Does it introduce unwanted bias? (3) Is the benefit worth the additional prompt complexity? Three metrics answer these: inter-profile activation variance (Q1), tension dual-activation and bias detection (Q2), baseline divergence vs personality-agnostic control (Q3). Four profiles cover: two simple (path A, no tension), one complex (path C, high tension), one moderate baseline. Multiple observations from distinct CAPS input categories (relationship, threat, achievement, social at minimum) prevent observation-selection bias. Null hypothesis test: same personality-agnostic prompt × 4 runs establishes the noise floor — personality-aware divergence must statistically exceed this. Temperature=0 reduces LLM stochasticity. Deterministic unit tests validate the mechanism independently: tension scoring function produces correct scores for known axis-value pairs, prompt builder produces expected system prompts per tension pair, routing logic sends simple profiles to path A and complex profiles to path C. Threshold sensitivity analysis (testing at 0.3, 0.5, 0.7) validates the routing boundary empirically.
**Trade-offs:** Larger eval matrix (4 profiles × 4+ observations × null control) increases LLM cost. Temperature=0 doesn't fully eliminate non-determinism but dramatically reduces it. Requires SessionPipeline.
**Depends on:** D2 (prompt design), D3 (data flow)
**Sources:** Issue #941 research questions and success criteria
**Exploration:** quick → revised after review
**Status:** revised (R1: multiple observations, temperature control, null hypothesis, deterministic mechanism tests, explicit metrics/questions, threshold sensitivity analysis)

## D5: Personality model for classification influence

**Choice:** DispositionAxes — 5 categorical axes (socialOrient, ruleFollowing, riskAppetite, autonomy, conflictMode) for classification-level personality influence
**Alternatives:**
- PID-5 facets (PersonalityFacet: Callousness, Risk Taking, Anxiousness, etc.) — continuous 0–1 scores modeling trait intensity along pathological dimensions; enables tension computation without a lookup table but models INTENSITY rather than interpretive DIRECTION
- PersonalityWeights (Big Five domain weights from memory-api) — too coarse (5 broad dimensions without specific behavioral orientation needed for situation framing)
- AttachmentProfile — too narrow (relationship-specific, doesn't cover risk/rule/conflict orientation)
**Rationale:** Classification-level personality influence shapes the DIRECTION of interpretation: a cooperative agent interprets social situations as connection opportunities while a competitive agent interprets them as status contests. DispositionAxes models this interpretive orientation directly — each axis value names a stance toward a class of situations. PID-5 facets model personality INTENSITY (how much of a trait someone has), which is already served by the CAPS topology's disposition_modifiers for propagation-level influence. Using PID-5 for both classification and propagation would conflate direction with magnitude. CognitiveDerivationEngine already uses both models at their appropriate levels: DispositionAxes for behavioral orientation, PID-5 facets for derivation functions requiring trait magnitude (e.g., deriveMoodBaseline, emotion regulation strategies). DescriptorView carries both disposition and personalityFacets, confirming these are distinct personality representations serving different architectural purposes.
**Sources:** DispositionAxes.java, PersonalityFacet.java, CognitiveDerivationEngine.java, CAPS topology disposition_modifiers, DescriptorView.java
**Exploration:** implicit → made explicit after review
**Status:** captured

## D6: Personality-aware classification scope

**Choice:** BehavioralSynthesisPhase classification is personality-aware (in scope for #941). DriveProfileDerivationPhase classification remains personality-agnostic (deferred to follow-up).
**Alternatives:**
- All consolidation phases personality-aware simultaneously — larger scope, conflates the eval (can't isolate the effect on behavioral synthesis if drive derivation also changes)
- Only BehavioralSynthesisPhase, never DriveProfileDerivationPhase — premature to rule out permanently; memory recall is personality-influenced in the psychological literature
**Rationale:** Issue #941 targets behavioral synthesis specifically. Introducing personality-aware classification in DriveProfileDerivationPhase simultaneously would confound the eval — activation divergence could come from either change. DriveProfileDerivationPhase classifies episodic memories and drive descriptions for drive profile construction; whether personality should influence how past memories are classified is a related but distinct question deserving its own eval after the mechanism is validated. Production call sites: BehavioralSynthesisPhase L145/L436 (in scope — add disposition metadata), DriveProfileDerivationPhase L196/L214 (deferred — no metadata change), CognitionObservationBuilder L520 (already passes agentId, separate concern).
**Sources:** BehavioralSynthesisPhase.java L145/L436, DriveProfileDerivationPhase.java L196/L214, CognitionObservationBuilder.java L520, Issue #941 scope
**Exploration:** implicit → made explicit after review
**Status:** captured
