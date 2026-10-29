# HANDOFF — casehub-neocortex

## Last Session

### #726 — CbrCaseEntry convenience record (2 files)

Added `CbrCaseEntry` to `memory-api` in `io.casehub.neocortex.memory.cbr`. Typed bridge for text-CBR Retain path via `CaseMemoryStore` — `toMemoryInput(Subject, tenantId)` maps problem→text with solution/outcome/confidence as attributes, `from(Memory)` extracts back. Domain: "solution". Not redundant with `CbrOutcomeData` (Revise path on `CbrRecordStore`). 13 tests, 751 memory-api tests pass. CLAUDE.md updated. Landed as `99a82d3b`.

## Suggested Next

Queue set up in `.plan` — 4 non-cognitive issues:

1. **#723** — ARC42STORIES naming update (CbrCaseMemoryStore → CbrRecordStore). Quick docs sync.
2. **#545** — Lifecycle event vocabulary enforcement (S/Low). Reduce 89 ad-hoc labels to standard set.
3. **#546** — Entity name normalisation (S/Med). Dedup 'Frida Kahlo' / 'Frida' and similar.
4. **#574** — Phase 2b memories lack passage-level provenance fields (S/Low).

## References

- `specs/issue-477-relational-schemas/2026-10-28-relational-schemas-design.md` — reviewed spec (authoritative)
- `specs/issue-477-relational-schemas/decisions.md` — 4 design decisions with rationale
