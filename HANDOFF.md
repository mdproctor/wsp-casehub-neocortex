# HANDOFF — casehub-neocortex

## Last Session

Completed #587 — Graduated SituationClassifier. Landed 3 squashed commits on main. Set up #721 branch for next session.

### #587 — Graduated SituationClassifier (L/High) — CLOSED

Widened `SituationClassifier` SPI with `ClassificationContext` (three-param abstract, two-param default with NONE). Created CDI producer for `LlmSituationClassifier` via `@Produces` in `caps-llm-classifier`. New `caps-situation-cbr` module with `CbrCachingSituationDecorator` (`@Decorator @Priority(60)`) — checks CBR for cached classifications via embedding similarity before delegating to LLM. Fixed session concurrency bug (per-invocation UUIDs). Wired `CognitionCoreFactory` to inject `SituationClassifier` into programmatic consumers.

Filed follow-up issues: #724 (progressive trust framework), #725 (classification outcome learning).

## Active Branch

`issue-721-unified-entity-linking` — scaffolded, no work done. Branch exists in both project and workspace repos.

## Suggested Next

**#721 — Unified entity linking** (XL/High). Bridge text corpus and knowledge graph via standoff annotation.

**User direction for brainstorm:**
- Start with scoping — this is XL, needs decomposition
- Compact indexes — light and fast, not heavyweight infrastructure
- Brainstorm is the first step — don't skip to implementation

## References

- `specs/issue-587-graduated-situation-classifier/2026-10-29-graduated-situation-classifier-design.md` — #587 spec (closed)
- `blog/2026-10-29-mdp02-when-keywords-lie.md` — diary entry for #587
- `docs/research/era5-relational-cognition-research.md` — context for #721
