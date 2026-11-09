## D1: Module placement

**Choice:** `caps-llm-classifier/src/test/java/.../eval/`
**Alternatives:**
- `cognition/src/test/java/.../eval/` — closer to code under test, but requires adding agent-platform test deps to cognition module
**Rationale:** Eval infrastructure (EvalLlmJudge, EvalTestSupport, EvalAgentResponse) already lives in caps-llm-classifier. No new dependencies needed.
**Trade-offs:** Test is one module away from the code it tests; acceptable since CognitionTestHarness is the public test API.
**Sources:** CognitiveInfluenceEvalTest.java, EvalLlmJudge.java
**Exploration:** quick
**Status:** captured

## D2: Character framing

**Choice:** Researcher/scientist exploring a knowledge domain
**Alternatives:**
- Country manor mystery (existing) — poor fit for exploration behaviour (breadth, depth, curiosity channels)
- Generic no-setting character — lacks the grounding needed for consistent exploration-style responses
**Rationale:** Exploration scenarios (broad vs narrow, topic pursuit, gap-closing) map naturally to a researcher. "I-TYPE curiosity → playful exploration" and "D-TYPE → urgent gap resolution" are native to research contexts.
**Trade-offs:** New system prompt diverges from existing eval character framing; acceptable since exploration is a distinct evaluation domain.
**Sources:** EvalAgentResponse.CHARACTER_SYSTEM_PROMPT, issue #866 scenario descriptions
**Exploration:** quick
**Status:** captured

## D3: Test structure

**Choice:** One test class with per-group `@Test` methods (not parameterized)
**Alternatives:**
- Single parameterized test — forces uniform scenario record across groups with fundamentally different setup (goal graphs, escalating memories, paired personalities)
- Multiple test classes per group — excessive for 6 groups, fragments the eval
**Rationale:** Each scenario group has unique harness setup. Per-group methods are readable, debuggable, and allow natural graph construction per group. Sub-scenarios within a method share their harness.
**Trade-offs:** Slightly more code than parameterized; worth the clarity.
**Sources:** CognitiveExplorationScenarioTest.java (S1-S5 structural tests), CognitiveInfluenceEvalTest.java
**Exploration:** quick
**Status:** captured
