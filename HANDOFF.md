# HANDOFF — casehub-neocortex

## Last Session

Landed 8 issues from epic #551 queue in a single session. All Python-side pipeline tooling and most XS/S child issues completed. One issue deferred (#560, needs LLM API access).

**What shipped (8 issues):**

| # | Title | Scale | SHA |
|---|-------|-------|-----|
| 553 | Python unit tests for convert_corpus.py | S | `45d7ec19` |
| 554 | Update verify_schema.yaml — org, entity-enrichment, disposition types | XS | `ac8e1121` |
| 555 | Update design spec — DispositionProfileEntry categorical axes | XS | `ca5b9b76` |
| 556 | Post-import validation script (validate_import.py) | S | `6832c74f` |
| 557 | Pipeline reproducibility demonstration | S | `5b91d4c0` |
| 558 | Regression baseline — compare_corpus.py rewrite with JSON reports | M | `3ca6286c` |
| 559 | CI gate for deterministic pipeline stages | S | `c03f899e` |
| 561 | Wire handler associations for Activity/Project/CulturalContext/Belief | XS | `1c8b7af1` |

**Deferred:**
- #560 — Second biography trial run (L) — needs LLM API access and source material

## Immediate Next Step

3 items remain in the epic #551 queue:

### Ready now
- #562 — Frida corpus quality assessment (M) — end-to-end cognitive model review of the corpus output
- #563 — LifeEventHandler domain routing tests (XS) — Java test coverage for MemoryDomain routing

### Deferred (needs separate session with API access)
- #560 — Second biography trial run (L) — select second subject, create per-corpus config, run full LLM pipeline

**Recommended start:** #563 (XS, quick Java test), then #562 (M, needs corpus reading).

```
Plan: .plan (position 9/12, 8 done, 1 deferred, 3 remaining)
Epic: #551, remaining: #560 (deferred), #562, #563
Branch: main (all work landed directly)
```

## State

- On `main`, all 8 issues landed as fast-forward merges with branch stamps
- 204 Python tests passing (47 convert, 27 validate_import, 19 compare_corpus, 8 reproducibility + 103 existing)
- 4 Java association tests passing (HandlerAssociationTest)
- 3 pre-existing Java test failures in GoalHandlerTest/BiographyImportIntegrationTest (GoalVocabulary.CONTENT_DOMAINS field missing — not from this session)
- CI workflow added: `.github/workflows/extraction-gate.yml` (coverage audit, verify informational, conversion smoke, pytest)
- Golden baseline: `extraction/output/corpus.json` (132 nodes, 1570 edges, 261 memories)
- verify_corpus.py verify gate is informational (145 pre-existing CRITICAL findings in corpus)

## Key Design Decisions

1. **validate_import.py** validates converter output against corpus (pre-import), not Java store state (post-import) — Python can't query Java stores. The Java integration test handles post-import verification.
2. **compare_corpus.py** rewrites the original (text-only, hardcoded targets) as a 3-category regression detector: structural (counts by type), field coverage (population rate drops >5%), content (removed nodes, PAD changes, missing enrichments). JSON report output.
3. **Reproducibility** proven: only non-determinism is verify_corpus.py timestamp field. All other stages produce byte-identical output from same inputs.
4. **CI verify gate** is informational — the current corpus has 145 CRITICAL findings from the extraction pipeline. Gate activates when corpus is cleaned.
5. **AssociationProcessor** now wired in all 4 remaining handlers (Activity, Project, CulturalContext, Belief) — same pattern as OrganisationHandler.

## Wrap orchestrator bug

The `wrap_orchestrator.py` crashed with `AttributeError: 'dict' object has no attribute 'is_done'` in `shared_steps.py:70` — `ctx.progress` is a plain dict instead of a ProgressTracker object. Reproducible — happens even after removing stale progress files. Handover written manually.
