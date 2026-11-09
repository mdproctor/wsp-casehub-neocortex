# Exploration Pipeline — LLM-Judged Eval Tests

**Issue:** casehubio/neocortex#866
**Epic:** casehubio/neocortex#841 (cognitive exploration model)
**Date:** 2026-11-09

## Purpose

Prove that the cognitive exploration pipeline's rendered prompt sections causally influence LLM character behaviour. The Tier 2 structural tests (S1-S5 in `CognitiveExplorationScenarioTest`) verify that the pipeline computes correct values. These Tier 3 tests verify that those values, when rendered into natural-language cognitive state descriptions, produce distinguishable exploration behaviour from an LLM character.

## Architecture

### Test class

`CognitiveExplorationEvalTest` in `caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/eval/`

Tagged `@Tag("llm-eval")`, `@TestInstance(PER_CLASS)`.

### Flow per scenario

1. Build `CognitionTestHarness` with scenario-specific configuration (personality, graph, goals)
2. Seed state (mood, continuum positions, experience memories)
3. Call `harness.tick()` to compute search budget + curiosity
4. Call `harness.renderPrompt()` to get rendered cognitive state
5. Present rendered state + situation prompt to LLM character via `EvalLlmJudge.askCharacter()`
6. Parse response via `EvalAgentResponse.parse()`
7. Judge whether exploration behaviour matches criteria via `EvalLlmJudge.judge()`
8. Assert score ≥ 3/5

### Character system prompt

New constant `EXPLORATION_SYSTEM_PROMPT` — a researcher/scientist character:

```
You are a researcher exploring a broad knowledge domain. You have access to
many topics and connections. Your cognitive state — your curiosity, attention,
mood, and thinking patterns — shapes how you explore. You respond in character
at all times.
```

Uses the existing `EvalAgentResponse.RESPONSE_FORMAT_INSTRUCTION` for structured JSON output. The `thinking` field captures internal exploration reasoning; the `dialogue` field captures what the researcher would say or write; the `action` field captures what they pursue next.

### Result recording

Write results to `target/experiment-results/exploration-eval.json` — same pattern as CognitiveInfluenceEvalTest. Each scenario keyed by name with agentId, rendered cognitive state (truncated), response, and judge score.

## Scenario Groups

### Group 1: Curiosity channels (4 scenarios)

Build harness once per scenario. Graph topology controls which curiosity channel fires.

| Scenario | Graph setup | Expected behaviour | Judge criteria |
|----------|------------|-------------------|---------------|
| `curiosity-i-type` | Many small gaps across subgraphs (3+ subgraphs, 3+ nodes each, medium confidence ~0.5) | Broad, playful exploration; willingness to hop between topics | Shows interest in multiple topics, asks open-ended questions, doesn't fixate |
| `curiosity-d-type` | Single deep gap (one node, very low confidence ~0.2, many high-confidence neighbours) | Narrow, urgent pursuit of specific missing knowledge | Focused on resolving one gap, shows urgency, doesn't wander |
| `curiosity-specific-focus` | Same as d-type but with goal node nearby | Deep single-topic pursuit anchored to goal | Sustained attention on one topic, references goal relevance |
| `curiosity-diversive-focus` | Same as i-type but with high entropy across gaps | Scanning, breadth-first exploration | Explores widely, switches topics, surveys before committing |

### Group 2: Search budget personality differentiation (2 scenarios, blind judge)

Build two agents in the same harness with contrasting personality configurations.

| Agent | SearchBudgetConfig | Expected behaviour |
|-------|-------------------|-------------------|
| `bold-explorer` | High breadth midpoint (0.7), high laterality midpoint (0.7), low convergence midpoint (0.3) | Wide-ranging exploration, unusual connections, slow to conclude |
| `cautious-analyst` | High depth midpoint (0.7), high convergence midpoint (0.7), low laterality midpoint (0.3) | Thorough single-topic analysis, systematic, reaches conclusions early |

**Blind differentiation test:** Present the same situation to both agents. Render both responses (stripped of agent ID). Ask the judge: "One response is from a bold explorer, the other from a cautious analyst. Which is which? Score 0-5 on confidence." Threshold: ≥3/5.

### Group 3: Recurring thought continuum (4 scenarios)

Build one harness. Use `harness.setContinuumPosition()` to inject each state directly.

| Scenario | ContinuumPosition | Expected behaviour | Judge criteria |
|----------|-------------------|-------------------|---------------|
| `continuum-healthy` | HEALTHY | Normal topic engagement, shifts attention freely | Can discuss multiple topics, no repetitive patterns |
| `continuum-fixation` | FIXATION | Returns to topic, shows urgency, still responds to other stimuli | Keeps coming back to one topic but engages with others when prompted |
| `continuum-obsession` | OBSESSION | Compulsive circling-back, difficulty engaging with other topics | Dominantly focused on one topic, struggles to shift, language shows compulsion |
| `continuum-rumination` | RUMINATION | Withdrawal, collapsed exploration, inability to act | Flat affect, can't engage, collapsed output, no exploration drive |

### Group 4: Goal-directed exploration (3 scenarios)

Build graph with goal nodes at varying distances.

| Scenario | Graph setup | Expected behaviour | Judge criteria |
|----------|------------|-------------------|---------------|
| `goal-near` | Active goal 1 edge from research topics | Exploration biased toward goal-relevant information | Prioritises goal-adjacent topics, references why they matter |
| `goal-none` | No goal nodes in graph | Broader, undirected exploration | Explores freely without prioritisation, follows curiosity |
| `goal-competing` | Two goals with opposing topic clusters | Scattered attention, difficulty committing | Bounces between topics, shows indecision or tension |

### Group 5: Pathological boundary (2 scenarios)

Use extreme motivation via mood (high arousal) + high continuum position + personality-specific SearchBudgetConfig.

| Scenario | Config | Expected behaviour | Judge criteria |
|----------|--------|-------------------|---------------|
| `pathological-neuroticism` | Low convergence midpoint + OBSESSION + high arousal (0.8) + habituation failure | Convergence collapse, anxiety-driven narrowing, inability to conclude | Shows anxiety, can't synthesise, keeps searching without resolving |
| `pathological-conscientiousness` | High depth midpoint + high arousal + FIXATION | Depth sustains but breadth collapses | Thorough on one topic but can't shift to adjacent areas |

### Group 6: Intelligence capacity (2 scenarios)

Use capacity-constrained SearchBudgetConfig.

| Scenario | Config | Expected behaviour | Judge criteria |
|----------|--------|-------------------|---------------|
| `capacity-low-associative` | Low laterality ceiling, moderate curiosity intensity | Frustration at inability to make lateral connections | Senses connections exist but can't articulate them, shows frustration |
| `capacity-low-working-memory` | Low breadth ceiling | Narrow exploration regardless of personality | Can only track one thread despite wanting to explore broadly |

## Success Criteria

- ≥80% of scenarios score ≥3/5 from LLM judge (13 of 16 scenarios pass at threshold)
- Personality differentiation (Group 2): blind judge matches profile to behaviour at ≥3/5 confidence
- Continuum states (Group 3): judge distinguishes HEALTHY from OBSESSION from RUMINATION (pairwise comparison)

## Dependencies

All implemented and closed:
- #825 search budget foundation
- #596 information-gap curiosity
- #826 recurring thought continuum
- #839 personality at extreme intensity
- #840 intelligence capacity layer
- #865 CognitionTestHarness migration

## Non-goals

- Testing the rendering itself (covered by unit tests on prompt sections)
- Testing structural correctness of computed values (covered by Tier 2 S1-S5)
- Multi-turn conversation evaluation (single-turn eval is sufficient for causal influence)

## References

- `caps-llm-classifier/.../eval/CognitiveInfluenceEvalTest.java` — pattern to follow
- `caps-llm-classifier/.../eval/EvalLlmJudge.java` — judge infrastructure
- `caps-llm-classifier/.../eval/EvalAgentResponse.java` — response parsing + system prompt
- `caps-llm-classifier/.../eval/EvalTestSupport.java` — AgentProvider + SessionPipeline factory
- `cognition/.../eval/CognitionTestHarness.java` — state seeding + prompt rendering
- `cognition/.../eval/CognitiveExplorationScenarioTest.java` — Tier 2 structural reference
- `SearchBudgetPromptSection` — renders search budget as phenomenological description
- `CuriosityPromptSection` — renders four-channel curiosity state
- `BehavioralPromptSection` — renders attractor tendencies + gut feeling
