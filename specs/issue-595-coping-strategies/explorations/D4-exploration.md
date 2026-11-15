# D4 Exploration: Causal Interpretation Representation

## The Question

EMA's coping strategies modify a "causal interpretation" — beliefs, desires,
intentions, probabilities, utilities. What's our equivalent?

## Options Considered

### A: Extend AppraisalContext with mutable fields

**Steelman:** Clean boundary. The micro-loop passes modified context back into
appraisal without polluting durable state. Familiar pattern.

**Devil's advocate:** AppraisalContext is immutable (a record). Making it mutable
changes its contract. Some coping effects ARE supposed to persist (resignation
drops a goal, planning creates one). Treating all effects as ephemeral is
unfaithful to the model. Also, AppraisalContext doesn't naturally carry the
concept of "reinterpreted narrative."

### B: MindMap as causal interpretation

**Steelman:** MindMap IS the causal interpretation — goals, beliefs,
relationships. Coping effects persist because they should. Faithful to EMA.

**Devil's advocate:** Micro-loop writes and re-reads MindMap multiple times per
tick. MindMap is backed by persistent storage — expensive. Intermediate coping
experiments (wishful thinking that later gets revised) written to durable state
are wasteful and confusing. Ephemeral cognitive exploration shouldn't pollute
long-term memory.

### C: New CopingInterpretation record

**Steelman:** Purpose-built for coping. Can carry exactly what's needed.

**Devil's advocate:** What IS needed? Ends up being a grab bag: narrative +
drives + goals + attention. Another data structure to maintain.

## First-Principles Analysis

### What is a "causal interpretation" in an LLM-based architecture?

EMA's original causal interpretation is a SYMBOLIC plan representation — goals,
beliefs, causal chains formalized as data structures. Appraisal derives from the
structure. Coping modifies the structure.

Our architecture is fundamentally different. We use LLM-based semantic processing
with numeric SEC evaluation. The natural representation of "how a character sees
the situation" is TEXT — the interpretation narrative.

### Tracing coping effects by type

**Semantic/narrative effects (require LLM):**
- Positive reinterpretation: transforms situation narrative
- Shift responsibility: reframes causal attribution in narrative
- Wishful thinking: adjusts perceived likelihood in narrative
- These are text transformations of meaning

**Numeric/motivational effects (post-resolution):**
- Mental disengagement: lower drive intensity
- Drive modulations from coping context

**Structural effects (goal lifecycle):**
- Planning: create a goal
- Resignation: drop a goal
- Procrastination: defer a goal
- Seek support: create social interaction goal
- Avoidance: create avoidance action

### The semantic resolution boundary

The interpretation narrative is the mutable core. LLM produces the
reinterpretation (semantic work). SEC checks evaluate the reinterpreted
narrative and produce numeric dimensions (mechanical on resolved text).
Downstream effects operate on those numbers.

This follows the established principle: LLM resolves semantics → mechanical
computation operates on resolved values.

## Recommendation: CopingState as micro-loop working state

Not any of A/B/C. A purpose-built micro-loop state where the NARRATIVE is
the mutable causal interpretation:

```
CopingState {
    interpretationNarrative: String  // starts as raw situation, reinterpreted each iteration
    secDimensions: Map<String, Double>  // re-derived from each reinterpretation
    emotions: List<CognitiveEmotion>  // re-derived from dimensions
    iteration: int  // current micro-loop pass
    
    // Accumulated for post-convergence dispatch
    goalOperations: List<GoalOperation>
    driveModulations: List<DriveModulation>
    attentionDirectives: List<AttentionDirective>
    strategiesAttempted: List<CopingStrategyAttempt>
}
```

**Why this works:**
1. The narrative IS the causal interpretation — natural for LLM architecture
2. SEC dimensions are re-derived each iteration — mechanical on resolved text
3. Persistent effects accumulate but don't dispatch until convergence
4. No mutation of AppraisalContext, no pollution of MindMap during the loop
5. After convergence, effects dispatch to their natural homes (goals, drives)
