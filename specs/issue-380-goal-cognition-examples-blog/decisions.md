## D1: Scenario strategy — all four domains

**Choice:** Use all four scenarios (research agent, product team, personal assistant, game NPC) as running illustrations, each demonstrating a different goal cognition capability.
**Alternatives:**
- Single scenario — simpler but fails to demonstrate domain-agnostic nature
- Two scenarios — less convincing than four
**Rationale:** Proves the system works across domains. Each reader finds at least one familiar context.
**Trade-offs:** More illustration work, longer article
**Sources:** User direction
**Exploration:** quick
**Status:** captured

## D2: Blog form — Article/explanation, discursive

**Choice:** Discursive explanation with personal voice and SVG illustrations throughout.
**Alternatives:**
- Tutorial — more hands-on but less conceptual
- Essay — strongest advocacy but less practical relevance
**Rationale:** Builds a mental model of why goal cognition matters. The existing diary entry covers architecture; this covers practical relevance.
**Trade-offs:** Less step-by-step guidance than a tutorial
**Sources:** Existing diary entry `2026-09-23-mdp01-how-agents-think-about-what-they-want.md`
**Exploration:** quick
**Status:** captured

## D3: Blog placement — workspace blog

**Choice:** Workspace blog/, promoted to project at close via work-end.
**Alternatives:**
- Direct to project docs/blog — breaks workspace artifact convention
**Rationale:** Consistent with existing writing workflow.
**Trade-offs:** None — standard path
**Sources:** Project conventions
**Exploration:** quick
**Status:** captured

## D4: Example module — walkthrough test with in-memory stores

**Choice:** Single `GoalCognitionWalkthroughTest` with 10 ordered phases, `@Tag("smoke")`, in-memory stores only.
**Alternatives:**
- Multiple test classes — fragments the narrative
- @QuarkusTest — adds container overhead for no benefit in examples
**Rationale:** Matches `MindMapIntelligenceWalkthroughTest` pattern. Each phase builds on previous state, tells a story.
**Trade-offs:** Single class may get long (~300-400 lines)
**Sources:** `examples/example-mindmap-intelligence/` pattern
**Exploration:** quick
**Status:** captured
