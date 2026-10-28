# Design Journal — issue-477-relational-schemas

## 2026-10-28 — Session 2: Children 1+2 implementation

Implemented #716 (types + storage) and #717 (appraisal wiring) — 10 commits total.

**Key decisions during implementation:**
- `org.jspecify.annotations.Nullable` not available at compile scope in `cognitive-index` — removed annotation, nullable semantics documented by convention
- `relies-on` chosen over `depends-on` for interpersonal dependency edge type — avoids alias conflict with GoalVocabulary's `requires → depends-on` alias
- `exploits` alias `uses` removed to avoid potential future conflicts with generic vocabulary
- `personality:` YAML key now nests under `personalityProfile:` in cognitive profiles — breaking change acceptable at pre-release maturity
- Personality facets filtered at `>= 0.5` score threshold in LLM prompt — avoids noise from low-scoring traits while keeping moderate ones visible
- Subgraph matching uses both `sg.type()` and `sg.name()` for PERSON subgraph resolution — defensive against configuration variations
