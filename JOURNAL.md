# Design Journal — issue-539-migrate-extraction-pipeline

## 2026-10-11 — Goal taxonomy extraction + pipeline quality pass

### What changed

Extended the extraction pipeline with Talevich/Emmons goal taxonomy (content domain, subdomain, motivation origin, clarity, evidence basis). Fixed edge extraction scaling by passing extracted entities as context to the edge LLM call — edge/node ratio went from 0.76 to 11.89. Added PAD on non-person entities. Wired LLM semantic dedup for near-miss goal pairs (union-find for transitivity). Quality audit surfaced and fixed 4 bugs: coverage checker key mismatch, entity merge missing taxonomy fields, memory/convergence name mismatches, confidence gaps.

### Key decisions

- **Entity context for edges and memories**: Entity+goal extraction runs first, then edges and memories receive the entity list as context. This trades parallelism for accuracy — the LLM uses canonical entity names and connects all entities it sees. The co-occurrence edge inference is a fallback for pairs the LLM missed.

- **LLM dedup gated by --llm-dedup**: Initially opt-in, then wired into run_pipeline.sh. The cost is minimal (1-2 Haiku calls per run) and it caught 5 real duplicates from 262 candidates. Conservative — only merges on DUPLICATE verdict, not RELATED.

- **derive_entity_pad from memory averages**: Goals can't get PAD this way because memories don't reference goals by name. GoalAffectPhase handles PAD at runtime for goals, so this is acceptable.

### Open questions

- 107 goals from one biography — is mechanical dedup threshold (JW≥0.90) too conservative?
- 348 dangling edges in full run — need to identify what they reference
- Import path field name alignment untested (corpus `goal_tier` vs GoalEntry `tier`)
- No Stage 4 post-import verification exists yet (#550 tracks this)
