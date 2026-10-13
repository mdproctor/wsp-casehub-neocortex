# Second Biography Trial Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #560 — Second biography trial run — generality proof
**Issue group:** #560

**Goal:** Prove the cognitive extraction pipeline generalises beyond Frida Kahlo by running it on Napoleon Bonaparte and comparing output quality.

**Architecture:** Three sequential work streams: (1) fix hardcoded Frida references in pipeline scripts, (2) write Napoleon biography and per-corpus config, (3) run pipeline, iterate, compare, and document findings.

**Tech Stack:** Python 3 scripts (extraction pipeline), bash (run_pipeline.sh), YAML (per-corpus config)

## Global Constraints

- Pipeline scripts live in `extraction/scripts/`
- Source biographies live in `extraction/sources/`
- Per-corpus output goes in `extraction/output-napoleon/`
- Per-corpus config (aliases.yaml, edge-corrections.yaml, verify_schema.yaml) lives alongside output in the output directory
- Python venv at `extraction/scripts/.venv/bin/python3`
- Napoleon biography: max 30 passages, ~400-500 words each
- Generality fixes committed BEFORE trial run (clean boundary)

---

## Batch 1: Pipeline Generality Fixes

### Task 1: Fix run_pipeline.sh orchestrator and functional defaults

Remove hardcoded Frida references from the pipeline orchestrator and the two scripts with functional defaults that will break Napoleon extraction.

**Files:**
- Modify: `extraction/scripts/run_pipeline.sh:267,276`
- Modify: `extraction/scripts/generate_overlay.py:80`
- Modify: `extraction/scripts/assemble_corpus.py:5,1231`

- [ ] **Step 1: Add `--schema` parameter to run_pipeline.sh**

At the top of `run_pipeline.sh`, after the existing `--limit` parameter parsing (around line 31), add `--schema` support. Add schema discovery logic after the venv check: look for `verify_schema.yaml` in the output directory first, fall back to `$SCRIPT_DIR/../docs/verify_schema.yaml`.

```bash
# Add to the while loop (after --limit case):
--schema) SCHEMA_PATH="$2"; shift 2;;

# After venv check (~line 45), add schema discovery:
# Schema discovery: explicit > output-dir > docs fallback
if [ -z "${SCHEMA_PATH:-}" ]; then
    if [ -f "$OUTDIR/verify_schema.yaml" ]; then
        SCHEMA_PATH="$OUTDIR/verify_schema.yaml"
    else
        SCHEMA_PATH="$SCRIPT_DIR/../docs/verify_schema.yaml"
    fi
fi

# Read subject name from schema
SUBJECT=$($VENV -c "
import yaml, sys
with open('$SCHEMA_PATH') as f:
    schema = yaml.safe_load(f)
print(schema.get('converter', {}).get('subject_name', ''))
")
if [ -z "$SUBJECT" ]; then
    echo "Error: converter.subject_name not found in $SCHEMA_PATH"
    exit 1
fi
echo "Schema: $SCHEMA_PATH"
echo "Subject: $SUBJECT"
```

- [ ] **Step 2: Propagate --subject and --schema to child scripts**

Update the `generate_overlay.py` invocation at line 267 to pass `--subject`:

```bash
# Line 267 — change from:
$VENV "$SCRIPT_DIR/generate_overlay.py" "$OUTDIR/structure.json" "$OUTDIR/passages.json" -o "$OUTDIR/reference-overlay.json"
# To:
$VENV "$SCRIPT_DIR/generate_overlay.py" "$OUTDIR/structure.json" "$OUTDIR/passages.json" -o "$OUTDIR/reference-overlay.json" --subject "$SUBJECT"
```

Update the `verify_corpus.py` invocation at line 276 to use the discovered schema:

```bash
# Line 276 — change from:
$VENV "$SCRIPT_DIR/verify_corpus.py" "$OUTDIR/corpus.json" \
    --schema "$SCRIPT_DIR/../docs/verify_schema.yaml" \
    --output "$OUTDIR"
# To:
$VENV "$SCRIPT_DIR/verify_corpus.py" "$OUTDIR/corpus.json" \
    --schema "$SCHEMA_PATH" \
    --output "$OUTDIR"
```

- [ ] **Step 3: Make --subject required in generate_overlay.py**

```python
# Line 80 — change from:
parser.add_argument('--subject', '-s', default='Frida Kahlo', help='Biography subject name')
# To:
parser.add_argument('--subject', '-s', required=True, help='Biography subject name')
```

- [ ] **Step 4: Remove hardcoded subject fallback in assemble_corpus.py**

```python
# Line 1231 — change from:
'subject': mem.get('subject', 'frida-kahlo'),
# To:
'subject': mem['subject'],
```

This will raise `KeyError` if a memory has no subject — that's intentional. A missing subject is an extraction bug.

Also fix the docstring at line 5:

```python
# Line 5 — change from:
ready for FridaSeeder or BiographyHandler import
# To:
ready for BiographyHandler import
```

- [ ] **Step 5: Commit generality fixes — functional defaults**

```bash
git add extraction/scripts/run_pipeline.sh extraction/scripts/generate_overlay.py extraction/scripts/assemble_corpus.py
git commit -m "fix(#560): remove hardcoded Frida defaults from pipeline orchestrator and scripts

- run_pipeline.sh: add --schema param, auto-discover verify_schema.yaml from output dir, read subject from schema
- generate_overlay.py: make --subject required (no default)
- assemble_corpus.py: remove 'frida-kahlo' subject fallback, fail on missing subject

Refs #560"
```

### Task 2: Fix LLM prompt examples

Remove Frida-specific examples from LLM system prompts that bias extraction toward Frida-world concepts.

**Files:**
- Modify: `extraction/scripts/extract_structure.py:134,139`
- Modify: `extraction/scripts/enrich_entity.py:48`

- [ ] **Step 1: Fix extract_structure.py canonical naming example**

```python
# Line 134 — change from:
use "Frida Kahlo" not "Frida", use "Mexico City" not "Mexico"
# To:
use the subject's full canonical name not a shortened form, use "Mexico City" not "Mexico"
```

- [ ] **Step 2: Fix extract_structure.py domain classification example**

```python
# Line 139 — change from:
"Frida was furious at the disorganisation in Paris"
# To:
"The subject was furious at the disorganisation they encountered"
```

- [ ] **Step 3: Fix enrich_entity.py prompt example**

```python
# Line 48 — change from:
"Diego Rivera"
# To:
"a close associate"
```

Also fix docstring at line 13:

```python
# Line 13 — change from:
--subject "Frida Kahlo"
# To:
--subject "Subject Name"
```

- [ ] **Step 4: Commit prompt fixes**

```bash
git add extraction/scripts/extract_structure.py extraction/scripts/enrich_entity.py
git commit -m "fix(#560): replace Frida-specific LLM prompt examples with generic ones

- extract_structure.py: generic canonical naming and domain classification examples
- enrich_entity.py: generic entity example in GOALS_RELATIONS_SYSTEM prompt

Refs #560"
```

### Task 3: Verify no Frida regression

Re-run deterministic post-LLM stages on existing Frida intermediates to confirm the generality fixes don't break the existing corpus.

**Files:**
- Read: `extraction/output/enriched.json` (existing intermediate)
- Read: `extraction/output/nlp-baseline.json` (existing intermediate)
- Read: `extraction/output/corpus.json` (existing baseline)

- [ ] **Step 1: Re-run assembly on Frida intermediates**

```bash
extraction/scripts/.venv/bin/python3 extraction/scripts/assemble_corpus.py \
    extraction/output/enriched.json \
    extraction/output/nlp-baseline.json \
    -o /tmp/frida-regression-test/corpus.json \
    -r /tmp/frida-regression-test/coverage-report.json \
    --llm-dedup
```

Note: if assembly fails because of the removed subject fallback (some Frida memories may lack the `subject` field), this reveals a pre-existing data quality issue. Fix by ensuring `extract_structure.py` always sets subject on memories, or add subject during assembly from `verify_schema.yaml`. Document the finding either way.

- [ ] **Step 2: Re-run verification on Frida intermediates**

```bash
extraction/scripts/.venv/bin/python3 extraction/scripts/verify_corpus.py \
    /tmp/frida-regression-test/corpus.json \
    --schema extraction/docs/verify_schema.yaml \
    --output /tmp/frida-regression-test/
```

Expected: 0 CRITICAL failures.

- [ ] **Step 3: Compare against baseline**

```bash
extraction/scripts/.venv/bin/python3 extraction/scripts/compare_corpus.py \
    extraction/output/corpus.json \
    /tmp/frida-regression-test/corpus.json
```

Expected: no regressions in structural counts or coverage.

- [ ] **Step 4: Clean up and commit**

Remove `/tmp/frida-regression-test/`. If any issues were found and fixed, commit the fixes.

```bash
rm -rf /tmp/frida-regression-test/
git commit -m "chore(#560): verify Frida regression after generality fixes — clean Refs #560" --allow-empty
```

---

## Batch 2: Napoleon Biography and Config

### Task 4: Write Napoleon biography

Write the complete Napoleon Bonaparte biography in chronological passage format, targeting the cognitive model gaps identified in #498.

**Files:**
- Create: `extraction/sources/napoleon-biography.md`

**Interfaces:**
- Produces: `extraction/sources/napoleon-biography.md` — chronological passages separated by `---` dividers, same format as `extraction/sources/frida-kahlo-biography.md`

- [ ] **Step 1: Study the Frida biography format**

Read `extraction/sources/frida-kahlo-biography.md` to understand the exact format: header, passage structure, `---` dividers, chronological section headers, passage density (~400-500 words each).

- [ ] **Step 2: Write Napoleon biography**

Write `extraction/sources/napoleon-biography.md` with these guidelines:

**Format:** `# Napoleon Bonaparte — Biographical Source Document` header, followed by chronological passages. Each passage has a `## N. Title (dates)` header, body text, and `---` divider.

**Coverage:** 17 life phases, ~20-22 passages, targeting these cognitive dimensions per #498:
- **Gloating:** Competitive rivalry, pleasure at rivals' failure (Austerlitz, response to defeated enemies)
- **Happy-for:** Vicarious joy at subordinates' success (if genuine — document honestly if Napoleon's response was more proprietary than disinterested)
- **Interruption:** Impulsive intervention, decisive action cutting through deliberation (Toulon, Brumaire, battlefield decisions)
- **Sorry-for:** Empathy for soldiers' suffering (battlefield scenes, retreat from Russia)
- **Disgust:** Moral revulsion (at cowardice, betrayal, incompetence)
- **Should-statements:** Duty, destiny, obligation (Corsican honor, imperial destiny)
- **Fortune-telling:** Strategic forecasting and its failures (Russian campaign prediction, Waterloo miscalculation)
- **Avoidance/withdrawal:** Elba exile, St Helena decline
- **Disqualifying positive:** Dismissing others' achievements

**Writing quality:** Psychological richness over military logistics. Specific episodes with emotional and cognitive content. ~400-500 words per passage. No summaries — scenes with internal states visible.

**Cap:** Maximum 30 passages. Target 20-22.

- [ ] **Step 3: Review passage count and word count**

```bash
# Count passages (sections separated by ---)
grep -c '^---$' extraction/sources/napoleon-biography.md

# Count words
wc -w extraction/sources/napoleon-biography.md
```

Verify: 20-30 passages, 8,000-14,000 words. If over 30 passages, merge the least cognitively rich ones.

- [ ] **Step 4: Commit biography**

```bash
git add extraction/sources/napoleon-biography.md
git commit -m "feat(#560): Napoleon Bonaparte biography source for generality trial

17 life phases, ~20-22 passages covering full life with focus on
cognitive dimensions missing from Frida corpus per #498.

Refs #560"
```

### Task 5: Create Napoleon per-corpus config

Create the per-corpus configuration files needed for Napoleon's pipeline run.

**Files:**
- Create: `extraction/output-napoleon/verify_schema.yaml`
- Create: `extraction/output-napoleon/aliases.yaml`
- Create: `extraction/output-napoleon/edge-corrections.yaml`

- [ ] **Step 1: Create output directory**

```bash
mkdir -p extraction/output-napoleon
```

- [ ] **Step 2: Create Napoleon verify_schema.yaml**

Copy from `extraction/docs/verify_schema.yaml` and modify:
- `entity_aliases`: Replace Frida aliases with Napoleon aliases:
  ```yaml
  entity_aliases:
    "Napoleon": "Napoleon Bonaparte"
    "Bonaparte": "Napoleon Bonaparte"
    "Josephine": "Joséphine de Beauharnais"
    "Joséphine": "Joséphine de Beauharnais"
    "Marie Louise": "Marie Louise of Austria"
  ```
- `converter.subject_name`: `"Napoleon Bonaparte"`
- Keep all entity type schemas, vocabularies, enrichment contracts, ranges, and edge/memory definitions identical

- [ ] **Step 3: Create initial Napoleon aliases.yaml**

```yaml
# Entity name aliases for Napoleon Bonaparte biography corpus.
# Maps dangling edge endpoint names to canonical node names.
# Used by assemble_corpus.py during edge resolution.
# Refined iteratively based on pipeline output.

# Proper name → full name
"Bonaparte": "Napoleon Bonaparte"
"the Emperor": "Napoleon Bonaparte"
"the Little Corporal": "Napoleon Bonaparte"
"the Corsican": "Napoleon Bonaparte"

# Family
"Letizia": "Letizia Bonaparte"
"Carlo": "Carlo Bonaparte"
"Joseph": "Joseph Bonaparte"
"Lucien": "Lucien Bonaparte"
"Louis": "Louis Bonaparte"

# Wives
"Joséphine": "Joséphine de Beauharnais"
"Josephine": "Joséphine de Beauharnais"
"Marie Louise": "Marie Louise of Austria"

# Key figures
"Talleyrand": "Charles Maurice de Talleyrand"
"Wellington": "Duke of Wellington"
```

This is an initial draft — will be refined after the first pipeline run based on dangling edge analysis.

- [ ] **Step 4: Create empty edge-corrections.yaml**

```yaml
# Factual edge corrections for Napoleon Bonaparte biography corpus.
# Applied by assemble_corpus.py during edge correction pass.
# Populated after inspecting first pipeline output.
```

- [ ] **Step 5: Commit per-corpus config**

```bash
git add extraction/output-napoleon/
git commit -m "feat(#560): Napoleon per-corpus config — schema, aliases, edge corrections

Initial per-corpus configuration for Napoleon pipeline run.
Aliases will be refined iteratively based on pipeline output.

Refs #560"
```

---

## Batch 3: Pipeline Run and Iteration

### Task 6: Run pipeline and iterate

Execute the full extraction pipeline on Napoleon's biography, inspect output, refine per-corpus config, and iterate until verification passes.

**Files:**
- Run: `extraction/scripts/run_pipeline.sh`
- Modify: `extraction/output-napoleon/aliases.yaml` (iterative refinement)
- Modify: `extraction/output-napoleon/edge-corrections.yaml` (iterative refinement)

- [ ] **Step 1: Run full pipeline**

```bash
bash extraction/scripts/run_pipeline.sh extraction/sources/napoleon-biography.md extraction/output-napoleon/ --schema extraction/output-napoleon/verify_schema.yaml
```

This runs: chunk → NLP baseline → LLM gap sweep → structural extraction → cognitive enrichment → entity synthesis → backfill → convergence loop → reference overlay → assembly → verification.

Monitor for errors. If the pipeline fails at any stage, diagnose and fix before proceeding.

- [ ] **Step 2: Inspect verification report**

```bash
cat extraction/output-napoleon/verification-report.json | python3 -m json.tool | head -50
```

Check for CRITICAL failures. Common issues on a new biography:
- Dangling edges (entities named differently in different passages)
- Invalid edge types (LLM inventing types not in the valid list)
- Missing enrichment fields

- [ ] **Step 3: Inspect dangling edges and refine aliases**

```bash
# Check dangling edge count from coverage report
python3 -c "
import json
r = json.load(open('extraction/output-napoleon/coverage-report.json'))
print('Dangling edges:', r.get('dangling_edges', {}))
"
```

For each dangling edge, add an alias mapping to `extraction/output-napoleon/aliases.yaml`. Common patterns:
- Short name → full name ("Napoleon" → "Napoleon Bonaparte")
- Title → person ("the Emperor" → "Napoleon Bonaparte")
- Variant spelling → canonical

- [ ] **Step 4: Inspect edge types and add corrections**

Review edges for factual errors:

```bash
python3 -c "
import json
c = json.load(open('extraction/output-napoleon/corpus.json'))
types = {}
for e in c.get('edges', []):
    t = e.get('type', 'unknown')
    types[t] = types.get(t, 0) + 1
for t, n in sorted(types.items(), key=lambda x: -x[1]):
    print(f'{t}: {n}')
"
```

Add corrections to `extraction/output-napoleon/edge-corrections.yaml` for:
- Incorrect relationship types (e.g. "married-to" when they were romantic partners)
- Fabricated relationships with no historical basis
- Incorrect directionality

- [ ] **Step 5: Re-run assembly and verification**

```bash
extraction/scripts/.venv/bin/python3 extraction/scripts/assemble_corpus.py \
    extraction/output-napoleon/enriched.json \
    extraction/output-napoleon/nlp-baseline.json \
    -o extraction/output-napoleon/corpus.json \
    -r extraction/output-napoleon/coverage-report.json \
    --llm-dedup

extraction/scripts/.venv/bin/python3 extraction/scripts/verify_corpus.py \
    extraction/output-napoleon/corpus.json \
    --schema extraction/output-napoleon/verify_schema.yaml \
    --output extraction/output-napoleon/
```

Repeat Steps 3-5 until verification passes with 0 CRITICAL.

- [ ] **Step 6: Commit pipeline output and refined config**

```bash
git add extraction/output-napoleon/
git commit -m "feat(#560): Napoleon pipeline output — initial run with iterative refinements

Pipeline converged. Aliases and edge corrections refined based on
output inspection.

Refs #560"
```

---

## Batch 4: Comparison and Findings

### Task 7: Write comparison report and findings document

Compare Napoleon corpus against Frida baseline across structural, coverage, and cognitive model dimensions. Document findings.

**Files:**
- Create: `extraction/docs/napoleon-trial-findings.md`

**Interfaces:**
- Consumes: `extraction/output-napoleon/corpus.json`, `extraction/output/corpus.json`, `extraction/docs/full-run-results.md`, casehubio/neocortex#498

- [ ] **Step 1: Gather Napoleon corpus stats**

```bash
python3 -c "
import json
c = json.load(open('extraction/output-napoleon/corpus.json'))
print(f'Nodes: {len(c.get(\"nodes\", []))}')
print(f'Edges: {len(c.get(\"edges\", []))}')
print(f'Memories: {len(c.get(\"memories\", []))}')
print(f'Entity enrichments: {len(c.get(\"entity_enrichments\", []))}')

# Node type distribution
types = {}
for n in c.get('nodes', []):
    t = n.get('type', 'unknown')
    types[t] = types.get(t, 0) + 1
print(f'Node types: {types}')

# Memory domain distribution
domains = {}
for m in c.get('memories', []):
    d = m.get('domain', 'unknown')
    domains[d] = domains.get(d, 0) + 1
print(f'Memory domains: {domains}')

# Edge type distribution (top 10)
etypes = {}
for e in c.get('edges', []):
    t = e.get('type', 'unknown')
    etypes[t] = etypes.get(t, 0) + 1
for t, n in sorted(etypes.items(), key=lambda x: -x[1])[:10]:
    print(f'  {t}: {n}')
"
```

- [ ] **Step 2: Gather coverage stats**

Run the coverage report or extract from the verification report:

```bash
python3 -c "
import json
r = json.load(open('extraction/output-napoleon/coverage-report.json'))
print(json.dumps(r, indent=2))
"
```

- [ ] **Step 3: Check cognitive model gap coverage**

Cross-reference Napoleon corpus against #498 dimension mapping:

```bash
python3 -c "
import json
c = json.load(open('extraction/output-napoleon/corpus.json'))

# Count OCC emotions across all memories
occ_counts = {}
for m in c.get('memories', []):
    enrichment = m.get('enrichment', {})
    for e in enrichment.get('occ_emotions', []):
        emotion = e if isinstance(e, str) else e.get('emotion', 'unknown')
        occ_counts[emotion] = occ_counts.get(emotion, 0) + 1

# Target gaps from #498
gaps = ['gloating', 'happy-for']
weak = ['sorry-for', 'hate', 'disgust']
print('=== OCC Emotion Gap Coverage ===')
for g in gaps:
    count = occ_counts.get(g, 0)
    status = 'FILLED' if count > 0 else 'STILL MISSING'
    print(f'  {g}: {count} ({status})')
for w in weak:
    count = occ_counts.get(w, 0)
    print(f'  {w}: {count} (target: strengthen)')

print()
print('=== All OCC emotions ===')
for e, n in sorted(occ_counts.items(), key=lambda x: -x[1]):
    print(f'  {e}: {n}')

# Count action tendencies
tend_counts = {}
for m in c.get('memories', []):
    enrichment = m.get('enrichment', {})
    for t in enrichment.get('action_tendencies', []):
        tendency = t if isinstance(t, str) else t.get('tendency', 'unknown')
        tend_counts[tendency] = tend_counts.get(tendency, 0) + 1

print()
print('=== Action Tendency Gap Coverage ===')
interruption = tend_counts.get('interruption', 0)
print(f'  interruption: {interruption} ({\"FILLED\" if interruption > 0 else \"STILL MISSING\"})')
print()
for t, n in sorted(tend_counts.items(), key=lambda x: -x[1]):
    print(f'  {t}: {n}')

# Count cognitive distortions
dist_counts = {}
for m in c.get('memories', []):
    enrichment = m.get('enrichment', {})
    for d in enrichment.get('cognitive_distortions', []):
        distortion = d if isinstance(d, str) else d.get('distortion', 'unknown')
        dist_counts[distortion] = dist_counts.get(distortion, 0) + 1

print()
print('=== Cognitive Distortion Representation ===')
targets = ['fortune_telling', 'should_statements', 'disqualifying_positive']
for t in targets:
    count = dist_counts.get(t, 0)
    print(f'  {t}: {count} (target: strengthen)')
"
```

- [ ] **Step 4: Write findings document**

Create `extraction/docs/napoleon-trial-findings.md` with this structure:

```markdown
# Napoleon Trial Run Findings — YYYY-MM-DD

## Summary
[One paragraph: did the pipeline generalise? Key metrics.]

## Structural Comparison

| Metric | Frida | Napoleon | Notes |
|--------|-------|----------|-------|
| Nodes | 132 | N | ... |
| Edges | 703 | N | ... |
| Memories | 261 | N | ... |
| Entity enrichments | 20 | N | ... |
| Edge resolution rate | X% | Y% | ... |

### Node Type Distribution
[Table comparing proportions]

### Memory Domain Distribution
[Table comparing proportions]

## Coverage Comparison

| Category | Frida | Napoleon |
|----------|-------|----------|
| Memory fields | 17/17 | N/17 |
| Enrichment fields | 22/24 | N/24 |
| OCC emotions | 20/22 | N/22 |
| Action tendencies | 8/9 | N/9 |
| SEC dimensions | 8/8 | N/8 |
| Sub-thought types | 7/7 | N/7 |

## Cognitive Model Gap Verification (vs #498)

### Zero-count gaps (must fill)
| Dimension | #498 prediction | Napoleon result | Filled? |
|-----------|----------------|-----------------|---------|
| gloating | competitive rivalry | N instances | Y/N |
| happy-for | vicarious joy | N instances | Y/N |
| interruption | impulsive intervention | N instances | Y/N |

### Weak dimensions (should strengthen)
| Dimension | Frida count | Napoleon count | Strengthened? |
|-----------|------------|----------------|---------------|
| sorry-for | 2 | N | Y/N |
| hate | 4 | N | Y/N |
| disgust | 5 | N | Y/N |

### Combined coverage
[22/22 OCC? 9/9 tendencies? 12/12 distortions?]

## What Worked Without Changes
[List]

## What Needed Per-Corpus Config
[List: aliases, corrections, schema changes]

## What Needed Code Changes
[List: the generality fixes from Batch 1]

## Recommendations
[Each becomes a GitHub issue]
```

- [ ] **Step 5: Create follow-up GitHub issues**

For each recommendation in the findings, create a GitHub issue:

```bash
gh issue create --repo casehubio/neocortex --title "<recommendation title>" --body "<details>" --label "scale: S"
```

- [ ] **Step 6: Commit findings**

```bash
git add extraction/docs/napoleon-trial-findings.md
git commit -m "docs(#560): Napoleon trial run findings — generality proof results

Closes #560"
```

## References

- [2026-10-13-second-biography-trial-design.md] — design spec this plan implements
- [extraction/scripts/run_pipeline.sh:267,276] — pipeline orchestrator hardcoded paths
- [extraction/scripts/generate_overlay.py:80] — hardcoded Frida subject default
- [extraction/scripts/assemble_corpus.py:1231] — hardcoded Frida subject fallback
- [extraction/scripts/extract_structure.py:134,139] — Frida-specific prompt examples
- [extraction/scripts/enrich_entity.py:48] — Frida-specific prompt example
- [extraction/docs/full-run-results.md] — Frida baseline metrics
- [extraction/docs/verify_schema.yaml] — per-corpus schema template
- [GitHub #498] — cognitive model gap analysis and Napoleon selection
- [GitHub #551] — parent epic, quality standard #2
- [GitHub #558] — regression baseline (completed)
