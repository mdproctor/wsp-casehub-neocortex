# HANDOFF — casehub-neocortex

## Last Session

Completed #550 (import readiness verification) and #549 (formative experience domain mapping). Built `verify_corpus.py` — a schema-driven QA tool that validates `corpus.json` against the Java-side import contract. Diagnoses 11 categories of issues (dangling edges, field alignment, vocabulary violations, range violations, subject alignment, enrichment gaps, volume anomalies, edge types, sub-thought types, memory domains). `--fix` mode applies safe fixes (alias resolution, field renames, range clamping). Integrated as Step 8 in `run_pipeline.sh`. Also fixed formative experience domain scattering (19 memories in wrong domains) and updated `.gitignore` to preserve `enriched.json` and other key intermediates.

## Immediate Next Step

Two issues remain on epic #538: #543 (affinity profile YAML) and #549 (closed). Close #550 on GitHub. Then either start #543 or run work-end if the epic is ready to close.

```
Plan: plans/2026-10-11-import-readiness-verification.md
Spec: specs/issue-539-migrate-extraction-pipeline/2026-10-11-import-readiness-verification-design.md
Epic: #538, remaining: #543
Branch: issue-539-migrate-extraction-pipeline
```

## State

- On `issue-539-migrate-extraction-pipeline`
- Issues completed this session: #550, #549
- Issues remaining on epic: #543 (affinity profile YAML — not started, different topic)
- All Python tests pass: 26 new tests in `test_verify_corpus.py`
- Real corpus validation: 173 findings detected, fix mode resolves aliases + field renames
- Key intermediate preservation: `.gitignore` updated so `enriched.json`, `nlp-baseline.json`, `corpus.json`, `manifest.json` are now tracked in git
- Production `enriched.json` not currently in `output/` — was not preserved from the last full pipeline run. Next full run will preserve it.

## Files Changed This Session

### extraction/docs/verify_schema.yaml (new)
Java-side import contract: field mappings, vocabularies, ranges, entity aliases, edge types.

### extraction/scripts/verify_corpus.py (new)
Import readiness verification tool. 11 check categories, 4 severity levels (CRITICAL/FIXABLE/WARNING/INFO). Default mode diagnoses. `--fix` applies safe fixes.

### extraction/tests/test_verify_corpus.py (new)
26 unit tests covering all check categories, fix mode, idempotency, exit codes.

### extraction/scripts/assemble_corpus.py (modified)
Added formative-experience domain normalisation: if `event_type` is `formative-experience`, force `domain` to `experience`.

### extraction/scripts/run_pipeline.sh (modified)
Added Step 8 (verify import readiness) after Step 7 (assemble corpus). Added header comment about intermediate preservation.

### .gitignore (modified)
Changed `extraction/output/` to `extraction/output/*` with exceptions for `enriched.json`, `nlp-baseline.json`, `corpus.json`, `manifest.json`.

## Known Issues

- 137 CRITICAL dangling edges in corpus remain after fix mode — these are entities referenced in edges but not present as nodes (e.g. "Mexico", "Guillermo Kahlo", "Tina Modotti"). These are extraction-stage issues: the LLM mentions entities in edges that were never extracted as nodes.
- 22 unknown edge types (e.g. `child-of`, `married-to`, `affair-with`, `depicted-in`) — extraction produces edge types not in the schema's valid set. Either extend the schema or constrain extraction.
- Production `enriched.json` needs regeneration — next full pipeline run will produce and preserve it.
