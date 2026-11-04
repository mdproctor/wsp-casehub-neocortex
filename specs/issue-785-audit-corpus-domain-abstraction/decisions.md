## D1: Audit scope — documented audit, not remediation

**Choice:** Produce a documented audit that catalogues all domain-abstraction leaks with severity classification, not a full remediation implementation.
**Alternatives:**
- Full remediation plan — designs and implements the refactoring. Too large for M/Med issue scope.
- Audit + quick wins — document everything and also land low-effort fixes. Mixes analysis and implementation in one branch.
**Rationale:** The audit is the right first step — it produces a reference that downstream issues can action without re-analysis. Keeps M/Med scope.
**Trade-offs:** Defers all code changes to future issues; leaks persist until remediation is picked up.
**Sources:** casehubio/neocortex#785 issue description
**Exploration:** quick
**Status:** captured

## D2: Use-case lenses — five diverse consumers

**Choice:** Stress-test abstractions against five use cases: clinical guidelines, legal precedents, game NPC knowledge, software documentation, and Hortora (existing consumer).
**Alternatives:**
- Three use cases (issue suggested 3-4) — less coverage, misses real-world edge cases.
- Four without Hortora — loses the baseline reference for what currently works.
**Rationale:** Five lenses provides comprehensive coverage. Including Hortora shows what works today and makes breakage risk concrete. Each use case has distinct document types, metadata models, and federation needs.
**Trade-offs:** More use cases means more analysis work per leak; worth it for an audit that will guide multiple future issues.
**Sources:** casehubio/neocortex#785 issue body ("walk through 3-4 diverse use cases")
**Exploration:** quick
**Status:** captured

## D3: Classification scheme — three-axis severity

**Choice:** Classify each leak on three dimensions: consumer impact (does this block a non-Hortora consumer?), remediation effort (XS/S/M/L), and Hortora breakage risk (will fixing this break existing usage?).
**Alternatives:**
- Consumer-blocking only — simpler but doesn't help prioritise remediation work.
- Consumer-blocking + effort — missing the risk dimension means remediation may break Hortora without warning.
**Rationale:** Three axes make the audit immediately actionable: "high impact, low effort, low risk" items are obvious quick wins; "high impact, high risk" items need careful design.
**Trade-offs:** Three dimensions per leak makes the spec more complex to read. Mitigated by the leak-first table format.
**Sources:** Audit findings showing the two-tier architecture where newer SPIs are clean and older impl is Hortora-shaped
**Exploration:** quick
**Status:** captured

## D4: Spec structure — leak-first with inline use-case tables

**Choice:** Organise spec by leak (each gets its own section with a use-case impact table), not by use case.
**Alternatives:**
- Use-case-first — one section per consumer walking through what works/breaks. More narrative but repeats the same leak across multiple sections.
- Matrix table — single large table, compact but loses the "why" behind each rating.
**Rationale:** Leak-first avoids repetition and makes each leak's severity immediately visible across all five consumers. Each section is self-contained with impact/effort/risk plus the per-consumer table.
**Trade-offs:** Harder to get a "would this work for my use case?" answer without reading the whole spec. Acceptable for a platform team audience.
**Sources:** Preview comparison during brainstorming
**Exploration:** quick
**Status:** captured

## D5: Roadmap inclusion — phased remediation direction

**Choice:** End the spec with a suggested 3-phase remediation sequence: quick renames → API fixes → structural extraction.
**Alternatives:**
- Purely descriptive — leak catalogue only, no remediation opinions. May lead to re-analysis when remediation starts.
- Descriptive + brief direction — enough to guide future work without committing to phases. Less actionable.
**Rationale:** A phased roadmap makes the audit immediately usable for sprint planning. Quick renames are safe to land fast; API fixes need more design; structural extraction is the big move.
**Trade-offs:** The roadmap is advisory — remediation issues may discover the phasing doesn't work. Acceptable since the spec frames it as "suggested" not "prescribed."
**Sources:** Audit findings showing distinct effort levels across leak categories
**Exploration:** quick
**Status:** captured
