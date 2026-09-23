# Goal Cognition Examples + Blog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #380 — Goal cognition: example module and educational blog article
**Issue group:** #380

**Goal:** Create a walkthrough example module demonstrating all goal cognition capabilities, and a substantial educational blog article with SVG illustrations across four real-world scenarios.

**Architecture:** Example module follows `example-mindmap-intelligence` pattern — `@TestInstance(PER_CLASS)`, ordered phases, in-memory stores, `@Tag("smoke")`. Blog article uses Article/explanation form with discursive mode, 7-8 SVG illustrations, Mark Proctor personal voice.

**Tech Stack:** Java 21 (on Java 26 JVM), JUnit 5, AssertJ, InMemoryMindMapStore, InMemoryMemoryStore

## Global Constraints

- Java 21 source, Java 26 JVM. `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn`
- Use `mvn` not `./mvnw`
- Example runs with `-Pexamples-smoke` (no Docker, no ONNX models)
- All commits reference `Refs #380` or `Closes #380`
- IntelliJ MCP for all code navigation and editing
- Blog article: personal voice (Mark Proctor), no process narration, no banned words (anti-slop.md)
- SVG illustrations: inline in markdown, `viewBox`-based responsive sizing, system-ui font family

---

## Batch 1: Example Module — Setup + Walkthrough

After this batch: `example-goal-cognition` module exists with a complete 10-phase walkthrough test demonstrating all goal cognition capabilities. Builds and passes with `-Pexamples-smoke`.

### Task 1: Example Module Setup + GoalCognitionWalkthroughTest

**Files:**
- Create: `examples/example-goal-cognition/pom.xml`
- Create: `examples/example-goal-cognition/src/test/java/io/casehub/neocortex/examples/goal/GoalCognitionWalkthroughTest.java`
- Modify: `pom.xml` — add module to `examples-smoke` and `examples` profiles

**Interfaces:**
- Consumes: InMemoryMindMapStore, InMemoryMemoryStore, GoalResolutionPhase, GoalAffectPhase, GoalPrioritizationPhase, GoalRecognitionPhase, GoalRelevanceModulationFactor, Goallike, GoalVocabulary, GoalDecompositionResult, RecognizedGoal
- Produces: Complete walkthrough demonstrating all goal cognition features

The walkthrough test class contains 10 ordered phases. Each phase builds on the shared graph state from prior phases. The full test file is a single deliverable — it tells a story through code.

**Phase 1 — Build the goal graph:** Create GOAL subgraph. Add goals: "Understand transformers" (aspirational, resolution=low), "Submit NeurIPS paper" (immediate, urgency=0.9, resolution=low), "Learn to cook" (medium-term, origin=experience), "Ship v2.0" (active, blocked), "Hire senior engineer" (active, status=active — blocker for Ship v2.0). Add dependency edges: paper requires understanding transformers, Ship v2.0 blocked by Hire senior engineer.

**Phase 2 — Goallike trait access:** `Thing.as(Goallike.class)` on the NeurIPS goal. Verify all 7 accessors (description, status, horizon, origin, resolution, urgency, feasibility).

**Phase 3 — Goal vocabulary and edges:** Verify GoalVocabulary edge types exist. Add edges using aliases ("unblocks", "depends-on"). Verify alias resolution.

**Phase 4 — Expand approaching goals:** Create a test CognitiveGoalDecomposer that decomposes "Submit NeurIPS paper" into 3 sub-goals (literature review, run experiments, write paper). Run GoalResolutionPhase. Verify sub-goal nodes created with decomposes-into edges, parent resolution updated to "high".

**Phase 5 — Prune distant goals:** Add sub-goals to "Understand transformers" (simulate prior expansion). Run GoalResolutionPhase. Verify aspirational goal's sub-goals removed, resolution dropped to "low".

**Phase 6 — Merge shared sub-goals:** Create two parent goals ("Rescue the princess", "Find the ancient artifact") each with a sub-goal containing "talk to blacksmith" / "visit the blacksmith". Run GoalResolutionPhase. Verify merge and contributes-to edges to both parents.

**Phase 7 — Revise dependencies:** Complete "Hire senior engineer" (set status=completed). Run GoalResolutionPhase. Verify "Ship v2.0" transitions from blocked→active.

**Phase 8 — Goal affect:** Run GoalAffectPhase. Verify: urgent goal (NeurIPS paper) gets high arousal, blocked goals get negative pleasure, completed goal (Hire) gets positive pleasure.

**Phase 9 — Goal prioritization:** Run GoalPrioritizationPhase on active goals. Verify composite priority computed. Verify goals with more inbound enables/contributes-to edges get higher importance score.

**Phase 10 — Goal-conditioned retrieval:** Create concept nodes connected to goal nodes at 1, 2, 3, and 4 edge distances. Create Memory objects referencing those concepts. Run GoalRelevanceModulationFactor. Verify distance-decayed weights: 1.0, 0.7, 0.4, 0.0.

- [ ] **Step 1: Create pom.xml for example-goal-cognition**

Model on `example-mindmap-intelligence/pom.xml`. Dependencies: thing-api, cognitive-api, cognitive-index, mindmap-api, mindmap-inmem, mindmap, mindmap-intelligence, memory-api, memory-inmem, memory-core. Test deps: junit-jupiter, assertj-core. Include `examples-smoke` profile with `<groups>smoke</groups>`.

- [ ] **Step 2: Add module to parent pom.xml**

Add `<module>examples/example-goal-cognition</module>` to both `examples-smoke` and `examples` profiles in the parent pom.xml.

- [ ] **Step 3: Write GoalCognitionWalkthroughTest with all 10 phases**

Create the complete walkthrough test class with `@TestInstance(PER_CLASS)`, `@TestMethodOrder(OrderAnnotation.class)`, `@Tag("smoke")`. Each phase is a `@Test @Order(N)` method. Include a `@BeforeAll` that creates the stores and GOAL subgraph.

Javadoc header describes the walkthrough scenario:
```
Walkthrough: cognitive goal management across four domains.

Scenario — four agents demonstrate different aspects of goal cognition:
a research agent managing paper deadlines (progressive resolution),
a product manager tracking feature dependencies (dependency revision),
a personal assistant discovering implicit goals (recognition + affect),
and a game NPC with overlapping quests (merge + retrieval modulation).

Each test method is a phase:
  1. Build the goal graph — goals with varied horizons and dependencies
  2. Goallike trait access — typed property access via Thing.as()
  3. Goal vocabulary — typed edges with alias resolution
  4. Expand — approaching goals decompose into sub-goals
  5. Prune — distant goals collapse back to low resolution
  6. Merge — shared sub-goals across parents
  7. Revise — blocker completion unblocks dependent goals
  8. Affect — PAD emotional computation from goal status
  9. Priority — composite formula ranks competing goals
 10. Retrieval modulation — memories biased by goal proximity
```

- [ ] **Step 4: Build and run**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-goal-cognition -Pexamples-smoke`
Expected: All 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(#380): add example-goal-cognition walkthrough module Refs #380"
```

---

## Batch 2: Blog Article

After this batch: complete educational blog article with 7-8 SVG illustrations, committed to workspace blog directory.

### Task 2: Write Blog Article

**Files:**
- Create: `$WORKSPACE/blog/2026-09-23-mdp02-when-your-agent-forgets-what-it-wants.md`

**Interfaces:**
- Consumes: Example module code for code snippets, design spec for architecture reference
- Produces: Complete blog article (~2500-3500 words, 7-8 SVGs)

Write the blog article following the spec structure (8 sections). Use write-content skill workflow: load personal voice, pre-draft gate, quality check, third-party review.

SVG illustrations (all inline, `viewBox`-based, `system-ui` font):

1. **"Goal as a string"** — prompt bubble floating in empty space
2. **Progressive resolution** — side-by-side low-res vs high-res goal graphs
3. **Dependencies** — typed edge graph with blocks(red)/enables(green)/requires(blue), before/after blocker resolution
4. **Affect trajectory** — PAD dimensions changing over time as goal status changes
5. **Shared sub-goals** — two parent goals with merged child, retrieval weight annotations
6. **Consolidation cycle** — circular 5-step phase diagram
7. **Narrow interface** — neocortex ↔ engine 2-arrow architecture
8. (Optional) **Priority formula** — visual breakdown of the 4 weighted components

Code snippets (short, 5-15 lines each):
- Goallike trait interface
- Priority formula
- GoalRelevanceModulationFactor distance weights

Voice: Mark Proctor personal style. Discursive mode. State findings directly, no process narration, end when finished.

- [ ] **Step 1: Load voice files and run pre-draft gate**

Load mark-proctor-voice.md, anti-slop.md, mandatory-rules.md, mandatory-gates.md. Classify I/we/Claude register per section. Verify content focus (no build runs, no test counts, no methodology).

- [ ] **Step 2: Draft all 8 sections with SVG illustrations**

Write the complete article with inline SVGs. Each section uses one of the four scenarios. Use code blocks sparingly — only where code IS the explanation.

- [ ] **Step 3: Quality check + third-party review**

Run anti-slop scan. Check factual accuracy. Scan for third-party references. Fix any issues.

- [ ] **Step 4: Write to disk and update blog index**

Write to `$WORKSPACE/blog/2026-09-23-mdp02-when-your-agent-forgets-what-it-wants.md`. Run `update_blog_index.py`. Commit.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(#380): educational blog article — when your agent forgets what it wants Refs #380"
```

---

## Batch 3: CLAUDE.md + Full Build Verification

After this batch: CLAUDE.md updated with example module, full build green.

### Task 3: CLAUDE.md Update + Build Verification

**Files:**
- Modify: `CLAUDE.md` — add example-goal-cognition to module structure and Maven coordinates

- [ ] **Step 1: Update CLAUDE.md module structure**

Add `example-goal-cognition/` entry under `examples/` in the module structure section.

- [ ] **Step 2: Update Maven coordinates table**

Add row for `casehub-neocortex-example-goal-cognition`.

- [ ] **Step 3: Build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl examples/example-goal-cognition -Pexamples-smoke`
Expected: Build success, all tests pass.

- [ ] **Step 4: Commit**

```bash
git commit -m "docs(#380): add example-goal-cognition to CLAUDE.md Refs #380"
```

## References

- `specs/issue-380-goal-cognition-examples-blog/2026-09-23-goal-cognition-examples-blog-design.md` — design spec
- `examples/example-mindmap-intelligence/` — walkthrough test pattern
- `blog/2026-09-23-mdp01-how-agents-think-about-what-they-want.md` — existing diary entry
- `specs/issue-345-goal-cognition/2026-09-23-goal-cognition-design.md` — goal cognition implementation design
- casehubio/neocortex#345 — implementation epic
- casehubio/neocortex#380 — this issue
