# Brief Review — cognitive-proving-ground-brief.md

Reviewed for: contradictions, ambiguity, missing context, scope confusion, priority drift, red herrings, and missing guardrails. Each finding includes the problematic text and a proposed fix.

---

## 1. Scope Confusion — The Biggest Risk

**Problem:** The brief mixes two distinct deliverables without clearly separating them:
- A **test harness** (snapshot/inject/assert infrastructure)
- A **scenario format** (Traitors game structure, phases, characters)

A fresh session could easily read "Design the scenario engine — phase structure, event generation, character interaction mechanics" and start building a game engine. The brief says "not a game" at the top but then devotes large sections to game design (day/night/roundtable phases, duration in ticks, elimination mechanics).

**Problematic text:**
> "## Game Format Ideas"
> "Design the scenario engine — phase structure, event generation, character interaction mechanics"

**Fix:** Rename "Game Format Ideas" to something like "Situation Generation — Game Format as Vehicle" and add an explicit note: "This section describes game mechanics ONLY as context for what situations the harness needs to generate. The next session should not design or implement game mechanics — it should design the harness that can run scenario scripts, of which a Traitors-format script is one example."

Also reorder "What the Next Session Should Do" to put harness first and scenario engine second, with explicit scope gates.

---

## 2. Missing Context — "The Current Scenario"

**Problem:** The brief references "the current format," "the current scenario," "current eval scores individual sentences," and "5 core characters exist" without explaining what these are. The supporting files (`existing-scenario-audit.md`, `cognitive-capability-matrix.md`) have this context, but the brief doesn't tell the next session to read them first.

**Problematic text:**
> "5 core characters exist with full biography profiles. 13 supporting without profiles."
> "What the current scenario DOESN'T exercise (gaps)"

**Fix:** Add a "Read First" section at the top, before "What This Is":

```
## Read First
Before acting on this brief, read these two files in order:
1. `existing-scenario-audit.md` — what the current wacky-manor scenario does, its characters, and its cognitive coverage gaps
2. `cognitive-capability-matrix.md` — 68 cognitive capabilities mapped to trigger conditions and environmental requirements

This brief synthesizes both. If something below is unclear, the answer is in one of those files.
```

---

## 3. Missing Guardrails

**Problem:** No explicit "do NOT" section. LLMs are prone to:
- Starting implementation immediately without brainstorming
- Building the most interesting-sounding part (game engine) instead of the most important (harness)
- Designing all 23 macro tests in detail before validating the harness concept
- Treating the macro test catalogue as a spec to implement rather than a framework to brainstorm from

**Fix:** Add a "Guardrails" section right after the priority hierarchy:

```
## Guardrails — What NOT To Do

1. **Do not implement.** This session is brainstorming and design only. No code, no PRs, no new modules.
2. **Do not design a game.** The Traitors format is a situation generator, not the deliverable. The deliverable is a test harness.
3. **Do not detail all 23+ macro tests.** The catalogue is illustrative — pick 3-5 that span different capability clusters and design those deeply. The rest validate the framework.
4. **Do not add cognitive capabilities.** The existing 68 capabilities may have gaps. Document the gaps — do not fill them yet. Gap-driven development means the failing test comes first.
5. **Brainstorm before proposing.** Use the brainstorming skill. Explore alternatives for the harness architecture before committing to one.
```

---

## 4. Priority Drift in "Game Format Ideas"

**Problem:** The "Game Format Ideas" section reads as game design. It discusses day/night phases, roundtable mechanics, banishment votes, and duration in ticks. A fresh session will likely latch onto this as the main deliverable because it's the most concrete and interesting section.

**Problematic text:**
> "### Core structure (from #176/#203):"
> "### Duration design:"
> "Phase structure: ~10 ticks day, ~5 ticks night, ~10 ticks roundtable = ~25 ticks per round × 6-12 rounds"

**Fix:** Add a framing line at the top of the section:

```
> **Context, not spec.** This section describes one possible situation-generation format.
> The next session should evaluate whether this format covers the capability gaps above,
> propose alternatives or modifications, and design the harness to be format-agnostic —
> the Traitors format is one scenario script, not the only one.
```

---

## 5. Ambiguity — "Snapshot" Has Two Meanings

**Problem:** "Snapshot" is used for both:
- Capturing a character's full cognitive state at runtime (for replay/debugging)
- Pre-seeding a character to a specific state for testing (state injection)

These are related but different infrastructure. A fresh session might conflate them.

**Problematic text:**
> "Snapshot capture — freeze full cognitive state at a point in time"
> "Snapshot restore — resume from a frozen state with optional tweaks"

vs.

> "Pre-seed the character states to the starting conditions"

**Fix:** Use distinct terminology:
- **Checkpoint** = capture full state at runtime for later restoration
- **Fixture** = pre-composed state for test setup (may come from a checkpoint, or be hand-built)
- **State injection** = the API that loads a fixture into the cognitive pipeline

---

## 6. Contradiction — "Enemy → Reconciliation" Duration

**Problem:** The long-arc section says "Enemy → reconciliation arc (~50-80 ticks minimum)" but the tick budget table in `cognitive-capability-matrix.md` says the same thing. However, the "long-arc" header says "100+ ticks, personality-level" — placing the 50-80 tick reconciliation arc under a 100+ tick header is confusing.

**Problematic text (line 54):**
> **Long-arc (100+ ticks, personality-level):**
> - Enemy → reconciliation arc (~50-80 ticks minimum)

**Fix:** Move "Enemy → reconciliation" to the medium-arc section (30-80 ticks), which is where its tick estimate actually falls. The long-arc section should only contain arcs that genuinely need 100+ ticks.

---

## 7. Missing — What "Brainstorm the Harness Architecture" Means

**Problem:** The first action item says "Brainstorm the harness architecture — snapshot capture/restore, state injection API, macro test runner" but doesn't give the next session enough to work with. What are the design questions? What are the constraints? What alternatives exist?

**Problematic text:**
> "1. **Brainstorm the harness architecture** — snapshot capture/restore, state injection API, macro test runner"

**Fix:** Expand into sub-questions the brainstorm should address:

```
1. **Brainstorm the harness architecture.** Key design questions:
   - How do we checkpoint full cognitive state? (Serialize all stores? Graph + memory + CAPS + mood + drives?)
   - What's the fixture format? (YAML like biographies? Programmatic builder like CognitiveEmergenceTest?)
   - How do we assert trajectories? (Time-series assertions on state sequences? Trajectory shape matching?)
   - How do we classify intent separately from tone? (LLM judge? Rule-based from cognitive state? Both?)
   - How does this compose with the existing eval infrastructure (~100 test classes, Python classification pipeline)?
   - What's the minimum viable harness that can run the interruption-escalation test end to end?
```

---

## 8. Missing — Relationship to Existing Code

**Problem:** The brief mentions existing infrastructure (`BackstorySeeder`, `CognitiveEmergenceTest`, `ManorCognitiveSeeder`, InMemory stores, eval pipeline) but doesn't explain how the new harness should relate to them. Build on top? Replace? Wrap?

**Fix:** Add a line under "What partially exists":

```
The new harness should build on these, not replace them. The question is what 
abstraction layer sits above them to compose checkpoints, fixtures, state injection, 
and trajectory assertions into a single test API.
```

---

## 9. Structural Reordering

**Problem:** The document's flow is:
1. What this is + priorities
2. Capability landscape + gaps
3. State injection architecture
4. Character design
5. Game format ideas
6. Turing test markers + macro tests
7. Verification depth
8. More macro tests
9. Development flow
10. Next steps

The Turing test section and macro test catalogue are split across the document, with verification depth wedged between them. The game format appears before the verification framework, making it seem more important.

**Fix:** Reorder to:
1. Read first (new)
2. What this is + priorities
3. Guardrails (new)
4. Capability landscape + gaps
5. Verification depth (State → Intent → Trajectory)
6. Macro test suite (all patterns together — Turing markers, interruption, reality TV, behavioral science, emotional escalation)
7. Development flow (gap-driven)
8. State injection & snapshot architecture
9. Character design
10. Game format (explicitly marked as context, not spec)
11. Next steps + supporting materials

This puts the "what are we proving and how" before the "what tools do we need" before the "what scenarios generate the situations."

---

## 10. Minor — Undefined Acronyms and Terms

A fresh session may not know:
- **SEC** — Scherer's stimulus evaluation checks (used without definition in the Turing test table)
- **OCC** — Ortony, Clore & Collins emotion model
- **PAD** — Pleasure-Arousal-Dominance (defined implicitly but never explicitly)
- **CAPS** — Cognitive-Affective Processing System
- **PID-5** — Personality Inventory for DSM-5
- **Ticks** — unclear whether these are wall-clock time or simulation steps (they're simulation steps)
- **Consolidation** — the periodic background processing cycle (not obvious from name alone)

**Fix:** Add a 10-line glossary at the end, or define each on first use. The brief is for a fresh session that hasn't read the CLAUDE.md.

---

## Summary of Severity

| # | Finding | Risk if unfixed |
|---|---------|----------------|
| 1 | Scope confusion (harness vs game) | **High** — session builds wrong thing |
| 2 | Missing "read first" | **Medium** — session lacks context, asks questions or guesses |
| 3 | Missing guardrails | **High** — session starts implementing or game-designing |
| 4 | Priority drift in game section | **Medium** — game design absorbs the session |
| 5 | Snapshot ambiguity | **Low** — clarifiable during brainstorm |
| 6 | Duration contradiction | **Low** — cosmetic |
| 7 | Vague harness brainstorm | **Medium** — session doesn't know what to explore |
| 8 | Missing relationship to existing code | **Medium** — session might rebuild from scratch |
| 9 | Structural reordering | **Medium** — game format overshadows verification |
| 10 | Undefined terms | **Low** — session can look them up, but wastes time |
