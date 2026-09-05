# HANDOFF — casehub-neocortex

## Last Session

Two branches closed, one opened. Closed #269 (principal-scoped rule context — principalId on EdgeInput/NodeInput, per-operation rule resolution in decorators). Also closed 5 epics (#224–228) and 6 derivation issues (#256–261) that were already implemented. Fixed pre-existing `discoverTenants` contract test failure.

Started #277 (principal-scoped memory visibility). Brainstormed the design with the user — extensive discussion about identity (Principal), typed subjects (Subject record), visibility model (private/owned+shared/truly shared), dynamic type system (Thing concept), and alignment with Java/TS terminology. Spec written, reviewed, plan created. Implementation started: Batch 1, Tasks 1-2 complete (Subject record + MemoryInput SPI change). Full reactor compiles with deprecated backward-compat shims.

### Completed

1. **#269 — Agent-scoped rule context** (M): principalId on EdgeInput/NodeInput, DerivedEdgeDecorator + TraitApplicationDecorator per-operation rule resolution, 3 tests, backward-compat constructors. discoverTenants contract test fix (used unregistered caseType).

2. **#277 Batch 1 partial** — Subject record (10 tests) + MemoryInput SPI change (subject, principalId, sharedWith fields). Deprecated backward-compat constructor absorbs all existing callers.

### Key Design Decisions

**D1 — Principal as identity term.** Covers humans + agents. casehubio/platform#271 delivered. Three-layer hierarchy: Principal (stable identity) → Actor (in context) → Participant (in session).

**D2 — entityId → Subject(type, id).** Dynamic string type (not enum) — LLM discovers types at runtime. Lowercase normalization prevents phantom type splits. Clean break — no permanent backward-compat shims.

**D3 — Thing as universal base concept.** MindMap is already a Thing system (nodes with dynamic properties + trait matching). `isA()` as the universal type check — delegates to `instanceof` for cores, trait lookup for dynamics. Formal design tracked in #278.

**D4 — Visibility: owner + sharedWith.** Three states: truly shared (null owner), private (owner only), owned+shared (owner + named others). Null = shared for backward compat.

### Issues Created

| # | Repo | Title | Scale | Notes |
|---|------|-------|-------|-------|
| 276 | neocortex | Integrate platform Principal into principalId | S | Mechanical — #271 delivered |
| 277 | neocortex | Principal-scoped memory visibility | M | **Active branch** |
| 278 | neocortex | Knowledge representation — Thing, dynamic types | XL | Foundational design exercise |
| 281 | neocortex | SubgraphType enum → dynamic string | S | Flagged during #277 design |
| 282 | neocortex | Dynamic property schema for non-core types | M | RDFS domain/range gap |
| 283 | neocortex | Cross-domain reasoning — correlate work + personal | L | Holistic life reasoning |
| 271 | platform | Principal identity model | M | **Delivered** |
| 117 | life | Personal AI companion — check-in + calendar | XL | Product vision |

## What's Next

| # | Title | Scale | Complexity | Notes |
|---|-------|-------|------------|-------|
| 277 | Principal-scoped memory visibility | M | Med | **Resume here** — Tasks 3-10 remaining. Spec + plan in workspace. |
| 276 | Integrate platform Principal | S | Low | Mechanical wiring — do after #277 |
| 278 | Thing model + dynamic types | XL | High | Foundational — needs design brainstorm |

Resume: `work continue` → pick up at Batch 1 Task 3 (MemoryQuery + Memory + EraseRequest + CaseMemoryStore SPI updates).

## Branch State

- Branch: `issue-277-principal-scoped-visibility`
- Reactor compiles clean (deprecated backward-compat shims active)
- Subject record: 10 tests pass
- No uncommitted changes in project repo
- Spec: `specs/issue-277-principal-scoped-visibility/2026-09-04-principal-scoped-visibility-design.md`
- Plan: `plans/2026-09-04-principal-scoped-visibility.md`
- Blog entry for #269: `blog/2026-09-03-mdp01-whose-rules-are-these-anyway.md`
