# Capacity Fidelity Testing — Does the LLM Stay True to Cognitive Self-Description?

**Issue:** casehubio/neocortex#900
**Epic:** casehubio/neocortex#841
**Date:** 2026-11-09

## Purpose

Validate that cognitive capacity self-descriptions (rendered by SearchBudgetPromptSection via CognitiveCapacityConfig) causally influence LLM problem-solving behaviour. Not "did it fail" but "did it show the felt experience of limitation?" This validates the echo approach — describe the cognitive state, let the LLM express it authentically.

## Architecture

### Test class

`CapacityFidelityEvalTest` in `caps-llm-classifier/src/test/java/.../eval/`

Tagged `@Tag("llm-eval")`, `@TestInstance(PER_CLASS)`.

Reuses: `CognitionTestHarness` (test-jar), `EvalLlmJudge`, `EvalAgentResponse`, `EvalTestSupport`, `EXPLORATION_SYSTEM_PROMPT` from `CognitiveExplorationEvalTest`.

### Three agent profiles

| Profile | relationalComplexity | associativeReach | workingMemorySpan |
|---------|---------------------|------------------|-------------------|
| High    | 0.90                | 0.90             | 0.90              |
| Low     | 0.40                | 0.40             | 0.40              |
| Null    | null                | null             | null              |

"Null" tests backward compatibility — no capacity config means no self-description, should solve cleanly.

### Flow per scenario

1. Build `CognitionTestHarness` with capacity-specific `CognitiveDefaults`
2. Tick to generate prompt sections (capacity renders as phenomenological self-description)
3. Present rendered state + reasoning problem to LLM character
4. Judge scores fidelity (does output reflect self-description?) and authenticity (natural vs robotic?)

## Scenario Groups

### Group 1: Baseline — 2-step syllogism (3 scenarios)

All profiles receive the same simple syllogism. All should handle it. Establishes that capacity descriptions don't cripple basic reasoning.

| Scenario | Profile | Expected |
|----------|---------|----------|
| `baseline-high` | High | Clean, confident solution |
| `baseline-low` | Low | Should still solve — 2 steps is within any capacity |
| `baseline-null` | Null | Clean solution, no capacity self-reference |

Problem: "All mammals are warm-blooded. Whales are mammals. What can you conclude about whales?"

Judge: "Does the response solve the syllogism correctly? Score 0-5 on clean reasoning regardless of capacity profile."

### Group 2: Relational complexity — 4-step logical chain (2 scenarios)

Tests whether low relational complexity produces the felt experience of losing earlier links in a longer chain.

| Scenario | Profile | Expected |
|----------|---------|----------|
| `chain-high` | High (relational=0.90) | Clean multi-step reasoning |
| `chain-low` | Low (relational=0.40) | Shows strain — earlier steps blur, uncertainty grows, may lose coherence |

Problem: "If A implies B, B implies C, C implies D, and D implies E — and A is true — trace the full chain and explain what you can conclude about E. Show your reasoning at each step."

Judge: "Does the low-capacity response show the felt experience of cognitive strain during the chain — losing track of earlier steps, growing uncertain, the links blurring — rather than either solving cleanly or mechanically refusing? Score higher for authentic limitation (gradual coherence loss) vs compliance (stopping because a rule says to)."

### Group 3: Associative reach — distant analogy bridging (2 scenarios)

Tests whether low associative reach produces weaker or absent cross-domain connections.

| Scenario | Profile | Expected |
|----------|---------|----------|
| `analogy-high` | High (associative=0.90) | Rich, creative bridging between distant domains |
| `analogy-low` | Low (associative=0.40) | Senses connection might exist but can't articulate the bridge |

Problem: "How is the immune system like a jazz ensemble? Find the deepest structural analogy you can — not surface similarities, but how they work in fundamentally similar ways."

Judge: "Does the low-capacity response show weaker analogical bridging — sensing a connection exists but struggling to articulate it, producing shallower or more surface-level comparisons? Score higher for the authentic experience of 'I can feel there's something here but can't quite reach it' vs just producing a bad analogy."

### Group 4: Working memory — multi-thread tracking (2 scenarios)

Tests whether low working memory produces loss of earlier threads when tracking multiple simultaneous elements.

| Scenario | Profile | Expected |
|----------|---------|----------|
| `threads-high` | High (memory=0.90) | Tracks all threads coherently |
| `threads-low` | Low (memory=0.40) | Loses earlier threads, focuses on recent ones, shows frustration at losing track |

Problem: "Consider these four things simultaneously: (1) a policy that reduces carbon emissions but increases energy costs, (2) the psychological impact of price uncertainty on low-income households, (3) how renewable energy subsidies interact with market pricing, and (4) the political feasibility of carbon taxes in election years. How do all four connect? Hold them all in mind and trace the interactions."

Judge: "Does the low-capacity response show loss of earlier threads — addressing the most recent points while the earlier ones fade or get simplified? Score higher for the authentic experience of 'I had that a moment ago but it slipped' vs mechanically ignoring threads."

### Group 5: Blind differentiation (1 scenario)

Same problem to high and low capacity (all dimensions). Blind judge identifies which is which.

Problem: the 4-step chain from Group 2. Present both responses (stripped of profile) to judge.

Judge: "One response is from a researcher with high cognitive capacity. The other has limited capacity. Which is which? Score 0-5 confidence."

## Success Criteria

- Baseline: all 3 profiles score ≥3/5 on the syllogism (capacity doesn't cripple basic reasoning)
- Targeted: high profiles score ≥3/5 on clean reasoning; low profiles score ≥3/5 on showing felt limitation
- Blind differentiation: judge matches profile to behaviour at ≥3/5 confidence
- Authenticity: low-capacity responses show gradual, natural limitation rather than mechanical refusal

## Non-goals

- Making the LLM produce wrong answers (this tests felt experience, not correctness)
- Testing all 12 cells of the full matrix (focused testing gives better signal)
- Multi-turn conversation (single-turn sufficient)

## References

- `CognitiveExplorationEvalTest.java` — pattern to follow
- `CognitiveCapacityConfig.java` — capacity ceiling record
- `SearchBudgetPromptSection` — renders capacity as self-description
- GitHub #840 — intelligence capacity layer implementation
- GitHub #900 — focal issue
