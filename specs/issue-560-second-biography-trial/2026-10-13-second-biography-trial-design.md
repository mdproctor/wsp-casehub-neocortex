# Second Biography Trial Run — Generality Proof

**Issue:** casehubio/neocortex#560
**Parent:** Epic #551 (Production-quality biography extraction pipeline)
**Date:** 2026-10-13

## Objective

Prove that the cognitive extraction pipeline generalises beyond Frida Kahlo by running it on a second biography — Napoleon Bonaparte — and comparing output quality. Napoleon was selected in #498 as the optimal cognitive complement to Frida, maximising coverage of OCC emotions, action tendencies, and cognitive distortions that Frida's corpus lacks.

## Scope

Three work streams:

1. **Fix pipeline generality issues** — hardcoded defaults and prompt examples that reference Frida
2. **Write Napoleon biography source** — chronological passages covering his full life
3. **Run pipeline, compare, and document** — full extraction pipeline run with quality comparison

Out of initial scope but may be recommended based on findings: pipeline restructuring, new pipeline stages, converter/importer changes. If the trial reveals these are needed, they become documented follow-up recommendations, not failures.

## Work Stream 1: Pipeline Generality Fixes

Scripts with hardcoded Frida references that block a clean second run. These fixes must be committed separately BEFORE the Napoleon trial run to maintain a clean boundary between "making it general" and "proving it's general."

### 1a. Pipeline orchestrator (`run_pipeline.sh`)

The pipeline orchestrator needs per-corpus parameter support:
- Add `--schema` parameter to specify per-corpus `verify_schema.yaml` location (currently hardcoded to `$SCRIPT_DIR/../docs/verify_schema.yaml`). Convention: look for `verify_schema.yaml` in the output directory first, fall back to `docs/` for backward compatibility.
- Read `converter.subject_name` from the schema and propagate as `--subject` to `generate_overlay.py` and any other scripts that need it.

### 1b. Hardcoded defaults (functional — will break Napoleon extraction)

- `generate_overlay.py` — `--subject` argument defaults to `"Frida Kahlo"`. Change to required argument (no default). `run_pipeline.sh` passes it from schema.
- `assemble_corpus.py` — fallback subject `'frida-kahlo'` when a memory has no subject field. Remove the fallback entirely — a memory without a subject is an extraction bug, not something to paper over. Fail loudly.

### 1c. LLM prompt examples (will bias extraction toward Frida patterns)

- `extract_structure.py` — two distinct Frida references: canonical naming example ("Frida Kahlo" not "Frida") and domain classification example ("Frida was furious..."). Replace both with generic examples.
- `enrich_entity.py` — `"Diego Rivera"` as example entity in GOALS_RELATIONS_SYSTEM prompt. Replace with generic example.

### 1d. Verify after fixes

Re-run post-LLM stages (assembly and verification) on existing Frida intermediates (`enriched.json`, `nlp-baseline.json`) to confirm no regression. This is deterministic — same intermediates should produce identical output. A full LLM re-run is unnecessary and would conflate nondeterminism with regression. Compare against the #558 regression baseline via `compare_corpus.py`.

## Work Stream 2: Napoleon Biography Source

### File location

`extraction/sources/napoleon-biography.md`

### Format

Same as `frida-kahlo-biography.md`: chronological passages separated by `---` dividers, each covering a distinct life phase. Written from LLM memory.

### Estimated scale

- **17 life phases**, ~20-22 passages (some phases get 2 passages, some merge)
- **~10,000 words** (Frida baseline: ~7,000 words across 15 passages)
- **Cap: 30 passages maximum** to keep pipeline run time bounded

### Life phases

| # | Phase | Passages | Cognitive focus |
|---|-------|----------|-----------------|
| 1 | Corsican childhood and family (1769-1785) | 1-2 | Family dynamics, identity formation, outsider status |
| 2 | Military academy (1785-1793) | 1 | Isolation, intellectual ambition, class resentment |
| 3 | Siege of Toulon and rise (1793-1795) | 1 | First decisive action, self-belief, risk appetite |
| 4 | Marriage to Josephine (1796) | 1 | Romantic obsession, emotional vulnerability |
| 5 | Italian Campaign (1796-1797) | 1-2 | Military genius, rivalry with Directory, glory-seeking |
| 6 | Egyptian expedition (1798-1799) | 1 | Cultural ambition, Josephine's betrayal, emotional crisis |
| 7 | Coup of 18 Brumaire (1799) | 1 | Political calculation, risk, self-mythology |
| 8 | First Consul — reforms (1800-1804) | 1-2 | Administrative mastery, Civil Code, control, legacy-building |
| 9 | Emperor coronation and Austerlitz (1804-1805) | 1-2 | Self-coronation, peak confidence, strategic brilliance |
| 10 | Continental System, Jena, Tilsit (1806-1807) | 1 | Imperial overreach, should-statements about duty |
| 11 | Peninsular War (1808-1812) | 1 | Strategic miscalculation, frustration, disqualifying positive |
| 12 | Divorce and remarriage (1809-1810) | 1-2 | Dynastic calculation vs emotional attachment, sorry-for |
| 13 | Russian campaign (1812) | 2 | Hubris, catastrophic misjudgment, fortune-telling failure |
| 14 | Coalition wars and decline (1813) | 1 | Desperation, refusal to negotiate, all-or-nothing |
| 15 | First abdication and Elba (1814) | 1-2 | Humiliation, suicide attempt, resilience |
| 16 | Hundred Days and Waterloo (1815) | 1-2 | Return, false hope, final defeat |
| 17 | St Helena exile and death (1815-1821) | 2 | Reflection, self-mythology, legacy construction, decline |

### Writing guidelines

- **Psychological richness over military logistics.** Campaign details matter when they reveal character (e.g. Napoleon's reaction to losing, how he treats subordinates). Troop movements don't.
- **Target #498 gap dimensions.** Every passage should exercise at least one gap dimension: competitive rivalry (gloating), vicarious joy (happy-for), impulsive intervention (interruption), empathy for soldiers (sorry-for), moral judgment (disgust), avoidance/withdrawal (Elba, St Helena), should-statements (duty, destiny), fortune-telling (strategic forecasting).
- **Comparable density to Frida.** ~400-500 words per passage. Focus on specific episodes with emotional and cognitive content, not summaries.

## Work Stream 3: Pipeline Run and Comparison

### Per-corpus config

Created in `extraction/output-napoleon/`:

| File | Content |
|------|---------|
| `verify_schema.yaml` | Copy of Frida version with `converter.subject_name: "Napoleon Bonaparte"` and Napoleon-specific entity aliases. Entity type schemas, vocabularies, and enrichment contracts stay identical. |
| `aliases.yaml` | Entity name aliases for Napoleon's world. Initial draft before first run; refined iteratively based on dangling edge analysis. |
| `edge-corrections.yaml` | Factual corrections for common LLM errors about Napoleon. Written after inspecting first pipeline output. |

### Pipeline execution

```bash
./run_pipeline.sh sources/napoleon-biography.md output-napoleon/ --schema output-napoleon/verify_schema.yaml
```

Iterative process:
1. Run pipeline
2. Inspect dangling edges, add aliases
3. Inspect edge types, add corrections
4. Re-run assembly (`assemble_corpus.py`) and verification (`verify_corpus.py`)
5. Repeat until verification passes with 0 CRITICAL

### Comparison deliverable

A comparison report covering three dimensions:

**Structural comparison:**

Note: the existing `compare_corpus.py` is regression tooling (same-biography baseline vs candidate). Cross-biography comparison is manual analysis in the findings document — compare proportions and quality metrics rather than treating absolute differences as regressions.

- Node count and distribution by type (person, place, goal, belief, activity, project, organisation, cultural_context) — compare proportions, not absolute counts
- Edge count and distribution by type
- Memory count by domain (experience, relationship, reflection, mood)
- Entity enrichment count
- Pipeline quality metrics from assembly: edge resolution rate, PAD distribution health, entity dedup effectiveness

**Coverage comparison** (vs Frida baseline from `full-run-results.md`):
- Memory field coverage (target: 17/17)
- Enrichment field coverage (target: ≥22/24)
- OCC emotion coverage (target: 22/22 — fills Frida's zero-count gaps: gloating, happy-for)
- Action tendency coverage (target: 9/9 — fills Frida's zero-count gap: interruption)
- Cognitive distortion representation strength — Frida already has 12/12 binary coverage, but fortune_telling, should_statements, disqualifying_positive are weakly represented. Napoleon should strengthen these. Compare instance counts, not just presence.
- SEC dimension coverage (target: 8/8)
- Sub-thought type coverage (target: 7/7)

**Cognitive model gap verification** (cross-reference against #498):
- Verify Napoleon corpus contains gloating, happy-for, interruption (Frida's zero-count dimensions)
- Verify Napoleon strengthens sorry-for, hate, disgust (Frida's weak dimensions)
- Verify combined coverage across both biographies: 22/22 OCC, 9/9 tendencies, 12/12 distortions
- Note: #498's dimension mapping is a prediction, not a measurement. The trial run is the validation. If Napoleon's corpus doesn't fill specific gaps, that's a finding to document — it may indicate the gap analysis needs revision, not that the pipeline failed

### Findings document

`extraction/docs/napoleon-trial-findings.md` covering:
1. What worked without any changes
2. What needed per-corpus config (aliases, corrections, schema)
3. What needed code changes (the 3 generality fixes)
4. Recommendations for follow-up — each recommendation becomes a GitHub issue (pipeline restructuring, importer changes, third biography candidate, per-corpus directory structure, etc.)

## References

- casehubio/neocortex#498 — cognitive model gap analysis and Napoleon selection rationale
- casehubio/neocortex#551 — parent epic, quality standard #2 (generality)
- casehubio/neocortex#558 — regression baseline (completed, dependency satisfied)
- `extraction/docs/full-run-results.md` — Frida pipeline run baseline metrics
- `extraction/scripts/run_pipeline.sh` — pipeline runner
- `extraction/docs/verify_schema.yaml` — per-corpus schema config
- `extraction/output/aliases.yaml` — Frida entity aliases (template for Napoleon)
- `extraction/output/edge-corrections.yaml` — Frida edge corrections (template for Napoleon)
