## Foundation: Three-dimensional goal architecture (agreed)

Goals operate across three interacting dimensions: LLM goals (prose, blocks/langchain4j), case goals (predicates, engine), and cognitive goals (neocortex, NEW). Cognitive goals manage and enrich goals from both other dimensions, and also operate standalone. Eidos `AgentRegistry` remains the single authoritative store for "what goals does this agent have." Neocortex provides cognitive context that feeds into formation/revision. No split-brain.

Established by cross-repo audit and two brainstorming sessions. See `2026-09-22-goal-architecture-context.md` for full analysis.

---

## D1: Where do shared goal primitives live?

*Pending — see proposal below*

## D2: What happens to eidos GoalSignalStore?

*Pending — see proposal below*

## D3: What moves from blocks to neocortex?

*Pending — see proposal below*

## D4: How does neocortex integrate with engine routing?

*Pending — see proposal below*

## D5: Does desiredstate share goal dependency primitives?

*Pending — see proposal below*

## D6: Scope of epic #345

*Pending — see proposal below*

## D7: Cognitive decomposition and progressive resolution

*Pending — see proposal below*
