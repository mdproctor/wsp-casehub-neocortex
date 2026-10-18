# Decisions — #514 Corpus Coverage Gate

## D1: Field registry format

**Choice:** Single YAML file (`docs/field-registry.yaml`) in the workbench
**Alternatives:**
- Generated from methodology markdown — fragile parsing, prose mixed with structured data
- Hardcoded per-script — no sync mechanism, drifts immediately
**Rationale:** YAML is machine-readable by both Python scripts and Java importer, versionable, easy to extend. Methodology doc stays human-readable; YAML is the machine-readable contract.
**Trade-offs:** Two sources to keep in sync (methodology doc + YAML). Mitigated by maintenance rules in CLAUDE.md.
**Sources:** cognitive-extraction-methodology.md, CLAUDE.md §Cognitive Corpus Coverage Protocol
**Exploration:** quick
**Status:** captured

## D2: Implementation sequencing

**Choice:** Fix by pipeline stage, top-down (extraction → enrichment → Phase 2b → importer)
**Alternatives:**
- Fix by field group across stages — produces fully-wired subset sooner but multiple pipeline re-runs
- Fix importer first, then backfill — avoids wasting LLM credits but decouples from data flow
**Rationale:** Top-down matches the pipeline's data flow. Fixing extraction before enrichment means Phase 2a gets richer input. One pipeline run at the end saves LLM credits.
**Trade-offs:** No intermediate testable corpus until all stages are fixed. Acceptable because the coverage gate at each stage validates independently.
**Sources:** Pipeline architecture §5.1, scripts/{extract_structure,enrich_cognitive,assemble_corpus}.py
**Exploration:** quick
**Status:** captured

## D3: Verification agent architecture

**Choice:** Post-step verification pass — separate Haiku call per passage checking output against field registry and original text
**Alternatives:**
- Inline verification in extraction prompt — self-verification weaker than independent verification
- Batch verification after full pipeline — can't retry individual passages, must re-run whole pipeline
**Rationale:** Independent verification catches things self-verification misses. Per-passage retry is surgical. Haiku call is cheap relative to the extraction call.
**Trade-offs:** Doubles the number of LLM calls per passage. Haiku is ~10x cheaper than the extraction model, so total cost increase is ~10%.
**Sources:** §5.2 Subagent Dispatch Pattern, §5.3 Orchestrator Responsibilities item 6-7
**Exploration:** quick
**Status:** captured
