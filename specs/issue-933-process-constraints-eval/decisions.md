# Decisions — #933 Process Constraints for Eval Suite

## D1: Scope — treat all five test areas independently

**Choice:** Design independent interventions for each test class
**Alternatives:**
- Shared prompt-layer focus (A+B) — simpler but risks missing test-specific issues
- Regulation-only first — reduces blast radius but delays drive profile fix
**Rationale:** Each test class has a distinct failure mechanism; treating them independently lets us diagnose and fix precisely
**Trade-offs:** More implementation work, but each fix is focused and verifiable
**Sources:** Issue #933 body, all five test class source files
**Exploration:** quick
**Status:** captured

## D2: CognitiveLoadStrategyEvalTest — both production and test

**Choice:** Process constraints go in both EmotionRegulationGenerationPhase.buildUserMessage() (production) and the standalone test's SYSTEM prompt (mirror)
**Alternatives:**
- Production only (B) — standalone test becomes redundant
- Test only (A) — doesn't improve production behavior
**Rationale:** Production code gets the fix for real-world correctness; standalone test mirrors it for isolated validation without full pipeline
**Trade-offs:** Two places to maintain, but the test prompt is a deliberately simplified mirror
**Sources:** CognitiveLoadStrategyEvalTest.java, EmotionRegulationGenerationPhase.java
**Exploration:** quick
**Status:** captured

## D3: DriveProfilePipelineTest — code fix not process constraint

**Choice:** Fix the rendering fallback in renderInternalState() to use drive's own description when no DriveDescriptionGenerated node exists, within #933
**Alternatives:**
- Separate issue — keeps #933 focused on process constraints only
- Seed DriveDescriptionGenerated in test — fixes test but not production gap
**Rationale:** The 12/12 failure is a rendering gap, not an LLM behavior issue. Fixing in production resolves it fundamentally and any remaining failures after the fallback would indicate classifier issues
**Trade-offs:** #933 scope expands slightly beyond pure process constraints
**Sources:** CognitionObservationBuilder.java:164-211, EvalMindMapSeeder.java, DriveProfileDerivationPhase.java
**Exploration:** deep-analysis (code tracing to identify root cause)
**Status:** captured

## D4: Regulation strategy differentiation — procedural strategy descriptions

**Choice:** When the predictor falls through to LLM (pinnedStrategy == null), render the dominant regulation capacity as a process constraint telling the model HOW each strategy works as a reasoning process, not just numeric capacity labels
**Alternatives:**
- Keep numeric labels + stronger system prompt — less invasive but won't differentiate
- Pin strategies programmatically in more cases — removes LLM agency
**Rationale:** The proven #905 technique: LLMs respond to procedural instructions about HOW to reason, not descriptive labels about capabilities. The current prompt gives numbers ("suppression: 0.80") but not process ("you hold your face steady while the emotion continues internally")
**Trade-offs:** Longer user messages; strategies are described in both system prompt AND user message (but system prompt is generic, user message is personality-specific)
**Sources:** SearchBudgetPromptSection.java:213-229 (proven pattern), EmotionRegulationGenerationPhase.java:475-493
**Exploration:** quick
**Status:** captured

## D5: Fatigue degradation — process constraint for depleted capacity

**Choice:** When fatigue > 0.7, replace descriptive fatigue text with a process constraint that procedurally removes complex strategies from availability
**Alternatives:**
- Lower fatigue threshold for safety gate — mechanically forces AD but removes LLM generation quality
- Add fatigue as a system prompt modifier — less targeted
**Rationale:** Same technique as D4 — tell the model what cognitive tools it NO LONGER HAS, not that it's tired. The existing safety gate (EmotionRegulationTickParticipant line 182) handles fatigue > 0.7 by pinning ATTENTIONAL_DEPLOYMENT, but this fires independently of the LLM prompt. The process constraint makes the LLM's own reasoning align with the programmatic gate.
**Trade-offs:** Fatigue process constraint is effectively redundant with the safety gate for extreme values, but improves behavior in the 0.5-0.7 range where the LLM still has agency
**Sources:** EmotionRegulationTickParticipant.java:181-188, EmotionRegulationGenerationPhase.java:442-449
**Exploration:** quick
**Status:** captured

## D6: PipelineCoherenceEvalTest — emergent from upstream fixes

**Choice:** Fix upstream (D2, D4, D5) first, then re-evaluate coherence test failures. No dedicated process constraint for coherence tests.
**Alternatives:**
- Add coherence hints to prompt sections — addresses symptom not cause
- Modify the coherence judge thresholds — weakens the test
**Rationale:** 3/4 coherence failures trace back to the same regulation prompt quality issues that D4 and D5 address. The shame-regulation chain and curiosity-exploration chain produce incoherent regulation results because the regulation prompt doesn't constrain strategy selection. Fixing the source should fix the downstream coherence.
**Trade-offs:** If coherence tests still fail after upstream fixes, we'll need a second pass — but that's the correct diagnostic order
**Sources:** PipelineCoherenceEvalTest.java
**Exploration:** quick
**Status:** captured
