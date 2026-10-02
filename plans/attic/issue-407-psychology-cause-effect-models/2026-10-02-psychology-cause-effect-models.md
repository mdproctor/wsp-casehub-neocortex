# Psychology Cause-Effect Models — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #407 — research: psychology cause-effect models for mechanical encoding
**Issue group:** #407

**Goal:** Produce the research foundation for a mechanical behavioral inference system — a reviewed spec document, structured CAPS network topology, and calibration roadmap that downstream issues (#401, #408, #397) consume.

**Architecture:** Two-layer hybrid — CAPS spreading activation network for computation (cyclic interactions, attractor formation, Rescorla-Wagner weight updates) + behavioral attractors stored as MindMap nodes. Six psychological models composed into one unified network through shared mediating nodes.

**Tech Stack:** YAML topology definition, Markdown spec document. No Java code in this issue — code implementation starts with #408 (graph engine).

## Global Constraints

- Research deliverable, not code — #407 produces the spec and topology that #408/#401 implement
- All weights classified by provenance: empirical (published effect sizes), consensus (clinical literature), estimated (theoretical derivation)
- Topology is species-level (shared structure), not per-agent — per-agent differences are in weights

---

## Batch 1: Finalize Research Deliverable

### Task 1: Validate topology YAML against spec

**Files:**
- Verify: `docs/specs/2026-10-02-caps-topology.yaml`
- Reference: workspace `specs/issue-407-psychology-cause-effect-models/2026-10-02-psychology-cause-effect-models-design.md`

**Interfaces:**
- Consumes: spec document sections §3.2 (nodes), §4.7 (connections), §3.3 (disposition), §5 (weights)
- Produces: validated topology YAML that #408 will load

- [ ] **Step 1: Count nodes match spec**

Verify input nodes (28), mediating nodes (20), output nodes (24) match spec §3.2.

- [ ] **Step 2: Verify all shared nodes from §4.7 have connections**

Check that self_worth, other_reliability, threat_sensitivity, FFFS_activation,
reinforcement_expectation, arousal_level, escape_assessment all appear in the
connections list as either source or target.

- [ ] **Step 3: Verify weight ranges**

All weights in [-1, +1]. All disposition modifiers in [0.1, 3.0].
Convergence parameters match §5 (epsilon=0.001, max_iterations=100).

- [ ] **Step 4: Commit validated topology**

```bash
git add docs/specs/2026-10-02-caps-topology.yaml
git commit -m "docs(#407): add CAPS network starter topology — 72 nodes, 40 connections, disposition modifiers

Structured YAML extracted from research spec. All weights classified by
provenance (empirical/consensus/estimated). Species-level topology for
#408 graph engine consumption.

Refs #407"
```

### Task 2: Final spec commit and issue closure

**Files:**
- Verify: workspace spec, decisions.md, pipeline.state

- [ ] **Step 1: Verify spec is committed**

Check workspace git status — ensure no uncommitted changes to the spec
after the design review implementors' modifications.

- [ ] **Step 2: Update pipeline state to PLANNING**

```
state: PLANNING
```

- [ ] **Step 3: Commit workspace**

```bash
git -C $WORKSPACE add .
git -C $WORKSPACE commit -m "wip(plan): implementation plan for #407 Refs #407"
```

- [ ] **Step 4: Close issue #407**

```bash
gh issue close 407 --repo casehubio/neocortex --comment "Research complete. Deliverables:
- Spec: 1456-line research document covering 6 psychological models
- Topology: YAML with 72 nodes, 40 key connections, disposition modifiers
- Calibration roadmap with provenance classification
- Standard adversarial review: 60 verified findings incorporated

Downstream: #401 (schema), #408 (graph engine)"
```

## References

- [2026-10-02-psychology-cause-effect-models-design.md] — design spec this plan implements
- [2026-10-02-caps-topology.yaml] — structured topology extracted from spec
- [decisions.md] — 6 design decisions captured during brainstorming
- [GitHub #406] — parent epic: emergent behavioral synthesis
- [GitHub #401] — downstream: standardised schema
- [GitHub #408] — downstream: cause-effect graph engine
- [GitHub #397] — downstream: behavioral attractor synthesis
