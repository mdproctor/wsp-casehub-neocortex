# Import Readiness Verification — Design Spec

**Issue:** casehubio/neocortex#550
**Branch:** issue-539-migrate-extraction-pipeline
**Date:** 2026-10-11

## Problem

The extraction pipeline (epic #538) produces `corpus.json` for import via
`BiographyImportRunner`. The pipeline has extraction-side coverage gates
(field registry, `coverage.py`), but no verification that the corpus will
import cleanly into the Java stores. Problems discovered so far in the
Frida Kahlo corpus:

- **348/1,570 dangling edges** — edges referencing entities by short name
  ("Frida") when the node is stored as "Frida Kahlo"
- **Field name misalignment** — corpus uses `goal_tier`, Java expects `tier`
  via `@JsonProperty`; `@JsonIgnoreProperties(ignoreUnknown=true)` silently
  produces nulls
- **107 goals** from one biography after dedup — expected 20-40
- **6% goal PAD coverage** — goals lack affective seed values
- **Subject inconsistency** — 10 memories with subject "Frida" instead of
  "Frida Kahlo"
- **75% enrichment coverage** — 64 memories missing cognitive fields

These problems span multiple pipeline stages. Some have clean upstream fixes
(field prefix is an assembler bug). Others — like LLM naming inconsistency —
are best fixed by post-processing because LLM inference is inherently noisy.

## Solution

A standalone Python script `verify_corpus.py` that:

1. **Diagnoses** all import-readiness issues in `corpus.json`
2. **Attributes** each finding to the pipeline stage that caused it and
   recommends **where the fix is most reliable** (upstream prompt, assembler
   post-processing, or corpus patch)
3. **Fixes** safe issues when run with `--fix`, producing a corrected
   `corpus-verified.json`
4. **Reports** remaining issues for manual review

The verifier validates `corpus.json` against a declarative `verify_schema.yaml`
that encodes the Java-side import contract: field mappings, vocabularies,
value ranges, required fields, and reference resolution rules.

## Architecture

### File Layout

```
extraction/
  scripts/
    verify_corpus.py       — the verification tool
  docs/
    verify_schema.yaml     — Java-side import contract
  tests/
    test_verify_corpus.py  — unit tests
```

### verify_schema.yaml — Import Contract

Declares the Java-side expectations per entity type:

```yaml
format_version: 1

# Entity name aliases — used for dangling edge and subject resolution
entity_aliases:
  "Frida": "Frida Kahlo"
  "Diego": "Diego Rivera"
  # Extended by the verifier when it detects new short-name patterns

# Per-type field contracts
entity_types:
  goal:
    subgraph_type: GOAL
    # Field mappings: corpus field → Java field
    field_mappings:
      goal_tier: tier
      goal_horizon: horizon
      goal_status: status
      goal_urgency: urgency
      goal_need_tier: need_tier
      goal_priority: priority
      goal_feasibility: feasibility
    # Required fields (null/absent → CRITICAL)
    required_fields:
      - name
      - tier
    # Vocabulary constraints (value must be in set)
    vocabularies:
      content_domain:
        values: [morality-and-virtue, religion-and-spirituality, self-actualisation,
                 avoidance, social-relating, health, family, mastery-and-competence,
                 financial-and-occupational]
        source: GoalVocabulary.CONTENT_DOMAINS
      content_subdomain:
        values: [social-values, personal-morals, help-others, ...]
        source: GoalVocabulary.CONTENT_SUBDOMAINS
      motivation_origin:
        values: [intrinsic, identified, introjected, external]
        source: GoalVocabulary.MOTIVATION_ORIGINS
    # Value range constraints
    ranges:
      pad.pleasure: [-1.0, 1.0]
      pad.arousal: [-1.0, 1.0]
      pad.dominance: [-1.0, 1.0]
      clarity: [0.0, 1.0]
    # Volume thresholds
    volume:
      warn_above: 60
      info: "107 goals from one biography; expected 20-40 distinct"

  place:
    subgraph_type: PLACE
    required_fields: [name]
    ranges:
      pad.pleasure: [-1.0, 1.0]
      pad.arousal: [-1.0, 1.0]
      pad.dominance: [-1.0, 1.0]

  relationship:
    subgraph_type: PERSON
    required_fields: [name]
    ranges:
      affect.pad.pleasure: [-1.0, 1.0]
      affect.pad.arousal: [-1.0, 1.0]
      affect.pad.dominance: [-1.0, 1.0]
      dynamics.trust: [0.0, 1.0]

  belief:
    subgraph_type: COGNITIVE
    required_fields: [description]
    ranges:
      confidence: [0.0, 1.0]

  life_event:
    required_fields: [description]
    ranges:
      pad.pleasure: [-1.0, 1.0]
      pad.arousal: [-1.0, 1.0]
      pad.dominance: [-1.0, 1.0]
    sub_thought_types: [affect-observation, causal-inference, evaluative,
                        intention, self-reflection, association, concern]

  activity:
    subgraph_type: ACTIVITY
    required_fields: [name]

  project:
    subgraph_type: PROJECT
    required_fields: [name]

  cultural_context:
    subgraph_type: CULTURAL
    required_fields: [description]

  current_state:
    ranges:
      mood.pleasure: [-1.0, 1.0]
      mood.arousal: [-1.0, 1.0]
      mood.dominance: [-1.0, 1.0]

# Edge validation
edges:
  valid_types:
    - pursues
    - associated-with
    - at
    - contributes-to
    - created-by
    - located-in
    - enables
    - blocks
    - requires
    - decomposes-into
    - collaborated-with
    - participated
    - lives-at
    - evidence-for
  # Dangling edge threshold
  dangling:
    critical_pct: 10    # >10% dangling → CRITICAL
    warn_pct: 2         # >2% dangling → WARNING

# Memory validation
memories:
  valid_domains: [experience, relationship, reflection, mood]
  enrichment_fields:
    - pad
    - occ_emotions
    - sec_appraisal
    - action_tendencies
    - sub_thoughts
    - cognitive_distortions
    - drive_impact
    - confidence
  enrichment_threshold: 80  # % of experience memories that should have enrichment
```

### verify_corpus.py — Verification Tool

```
Usage:
  verify_corpus.py <corpus.json> [--schema <verify_schema.yaml>] [--fix] [--output <dir>]

Default mode (no --fix):
  Reads corpus.json, validates against schema, writes:
    - verification-report.json  (structured, machine-readable)
    - verification-report.txt   (human-readable summary)
  Exit code: 0 = pass, 1 = has CRITICAL findings, 2 = has WARNING findings

Fix mode (--fix):
  Applies safe fixes, writes:
    - corpus-verified.json      (corrected corpus)
    - verification-report.json  (report with fix actions applied)
    - verification-report.txt   (human-readable summary)
  Exit code: 0 = no CRITICAL or WARNING remaining, 1 = unresolved CRITICAL, 2 = unresolved WARNING only
  (INFO findings do not affect the exit code)
```

### Report Structure

```json
{
  "format": "import-readiness-report/v1",
  "corpus": "corpus.json",
  "timestamp": "2026-10-11T12:00:00Z",
  "summary": {
    "total_findings": 42,
    "critical": 3,
    "fixable": 28,
    "warning": 8,
    "info": 3,
    "gate": "FAIL"
  },
  "findings": [
    {
      "id": "F001",
      "category": "dangling_edge",
      "severity": "FIXABLE",
      "source_stage": "extraction",
      "fix_level": "post_processing",
      "fix_description": "Resolve alias: 'Frida' → 'Frida Kahlo'",
      "count": 202,
      "details": {
        "alias": "Frida",
        "canonical": "Frida Kahlo",
        "affected_edges": 202,
        "edge_types": ["pursues", "created-by", "lives-at", "..."]
      },
      "fixed": false
    },
    {
      "id": "F002",
      "category": "field_alignment",
      "severity": "CRITICAL",
      "source_stage": "assembly",
      "fix_level": "assembler",
      "fix_description": "Rename 'goal_tier' → 'tier' (Java @JsonProperty expects unprefixed)",
      "count": 107,
      "details": {
        "corpus_field": "goal_tier",
        "java_field": "tier",
        "affected_nodes": 107
      },
      "fixed": false
    }
  ],
  "checks_passed": [
    "vocabulary_content_domain",
    "vocabulary_motivation_origin",
    "memory_domain_validity",
    "enrichment_coverage"
  ]
}
```

### Check Categories

| Category | What it checks | Severity | Fix level |
|----------|---------------|----------|-----------|
| `dangling_edge` | Edge source/target not in node list | FIXABLE (if alias exists) or CRITICAL | Post-processing: alias resolution |
| `field_alignment` | Corpus field name ≠ Java @JsonProperty | CRITICAL | Assembler: fix the prefix logic |
| `vocabulary_violation` | Value not in canonical vocabulary set | WARNING | Assembler: extend normalisation tables |
| `range_violation` | Numeric value outside declared range | WARNING | Enrichment: clamp in post-processing |
| `missing_required` | Required field is null/absent | CRITICAL | Extraction: prompt adjustment |
| `volume_anomaly` | Entity count exceeds threshold | INFO | Extraction: prompt tuning + dedup thresholds |
| `subject_alignment` | Memory subject doesn't match any node name | FIXABLE (if alias exists) or WARNING | Post-processing: same alias resolution |
| `enrichment_gap` | Memory missing expected cognitive fields | INFO | Enrichment: backfill pass |
| `sub_thought_type` | Sub-thought type not in valid set | WARNING | Enrichment: type validation |
| `edge_type_unknown` | Edge type not in valid types list | WARNING | Extraction: vocabulary constraint |
| `duplicate_candidate` | Near-miss entities that may be duplicates | INFO | Assembly: dedup threshold tuning |

### Fix Mode Behaviour

When run with `--fix`, the verifier applies these **safe** transformations:

1. **Alias resolution** — Resolve entity short names using `entity_aliases`
   from the schema. Applied to: edge source/target, memory subjects.
2. **Field rename** — Apply `field_mappings` to rename corpus fields to
   Java-expected names. Applied to: node fields per entity type.
3. **Range clamping** — Clamp numeric values to declared ranges. Applied to:
   PAD values, confidence, clarity.
4. **Sub-thought type normalisation** — Map invalid types to closest valid
   type if unambiguous.

Fixes NOT applied automatically (stay in report):
- Vocabulary violations with no clear mapping
- Volume anomalies (requires human judgment)
- Missing required fields (can't be synthesised)
- Duplicate candidates (requires semantic judgment)
- Unknown edge types (may be legitimate new types)

### Integration with run_pipeline.sh

Added as the final pipeline step, after `assemble_corpus.py`:

```bash
# Step 8: Verify corpus import readiness
python3 scripts/verify_corpus.py "$OUTPUT_DIR/corpus.json" \
    --schema docs/verify_schema.yaml \
    --output "$OUTPUT_DIR"

if [ $? -eq 1 ]; then
    echo "CRITICAL: Import readiness gate failed"
    echo "Run with --fix to attempt auto-repair:"
    echo "  python3 scripts/verify_corpus.py $OUTPUT_DIR/corpus.json --fix"
    exit 1
fi
```

### Pipeline Manifest Integration

Register as a pipeline step in `manifest.json` via `PipelineManifest`:

```python
manifest.record_step("verify_corpus", {
    "findings": summary.total_findings,
    "critical": summary.critical,
    "fixable": summary.fixable,
    "gate": summary.gate
})
```

## Relationship to Existing Coverage Gates

`verify_corpus.py` complements but does not replace `coverage.py`:

| Concern | coverage.py | verify_corpus.py |
|---------|-------------|------------------|
| Field population rates | Yes (field registry) | No (cross-checks coverage.py's report) |
| Structural integrity | No | Yes (dangling edges, ref resolution) |
| Java import contract | No | Yes (field names, vocabularies, ranges) |
| Volume sanity | No | Yes (per-type thresholds) |
| Fix application | No | Yes (--fix mode) |
| Subject alignment | No | Yes (alias resolution) |

`coverage.py` answers "are fields populated?" `verify_corpus.py` answers
"will this import cleanly?"

## Test Strategy

Unit tests in `test_verify_corpus.py`:

1. **Dangling edge detection** — corpus with edges to non-existent nodes
2. **Alias resolution** — verify fix mode resolves known aliases
3. **Field alignment** — detect `goal_` prefix, verify rename fix
4. **Vocabulary validation** — valid and invalid values
5. **Range validation** — PAD values inside, outside, and on boundary
6. **Subject alignment** — short names in memory subjects
7. **Report format** — JSON structure matches spec
8. **Exit codes** — 0/1/2 for pass/critical/warning
9. **Fix idempotency** — running fix twice produces same output
10. **Schema loading** — missing schema, malformed schema

## References

- `extraction/scripts/assemble_corpus.py` — corpus assembler (upstream)
- `extraction/scripts/coverage.py` — existing field coverage gates
- `extraction/docs/field-registry.yaml` — field registry (90 fields)
- `memory-seeding/src/.../biography/BiographyImportRunner.java` — Java importer
- `memory-seeding/src/.../biography/BiographyLoader.java` — YAML parser + validation
- `memory-seeding/src/.../biography/GoalEntry.java` — goal field mappings
- `memory-seeding/src/.../biography/GoalHandler.java` — vocabulary validation
- `mindmap-api/src/.../mindmap/GoalVocabulary.java` — canonical vocabulary sets
- Issue #550 — import readiness verification
- Issue #538 — extraction pipeline epic (parent)
