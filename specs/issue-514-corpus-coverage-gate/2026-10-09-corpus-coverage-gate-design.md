# Corpus Coverage Gate — Design Spec

**Issue:** casehubio/neocortex#514
**Branch:** issue-468-cognitive-workbench
**Date:** 2026-10-09

## Problem

The cognitive extraction methodology (`cognitive-extraction-methodology.md`) prescribes 85 declarable fields across 5 categories. The pipeline scripts and importer implement 25% of them. The gap is invisible — there is no mechanism to detect, report, or enforce coverage. New capabilities added to the methodology silently fail to reach the corpus or cognitive engine.

## Solution

A four-stage coverage chain with a machine-readable field registry, computed coverage reports at each stage, and Haiku verification agents that enforce justified coverage at every gap.

## Architecture

### 1. Field Registry (`docs/field-registry.yaml`)

Single source of truth for all declarable fields. Read by Python scripts and Java importer.

```yaml
format: cognitive-field-registry/v1
categories:
  node_fields:
    threshold: 60  # soft gate percentage
    fields:
      - id: N1
        name: name
        methodology_ref: "§3.1"
        stages: {extraction: required, corpus: required, importer: required}
        status: done
      - id: N4
        name: traits
        methodology_ref: "§4.12"
        stages: {extraction: required, corpus: required, importer: required}
        status: gap
        depth_tier: [central, supporting]  # only required for these tiers
      - id: N6
        name: pad
        methodology_ref: "§4.1"
        stages: {extraction: required, corpus: required, importer: required}
        status: gap
  enrichment_fields:
    threshold: 70
    fields:
      - id: E15
        name: habituation
        methodology_ref: "§4.11"
        stages: {enrichment: required, corpus: required, importer: required}
        status: gap
        depth_tier: [central, supporting]
      - id: E17
        name: caps_inputs
        methodology_ref: "§4.6"
        stages: {enrichment: phase2b, corpus: required, importer: required}
        status: gap
        depth_tier: [central]
  # ... all 85 fields
  intentional_exclusions:
    - domain: engagement
      reason: "Per-interaction social signals, live conversation only (§4.0)"
    - domain: affect
      reason: "PAD recorded by AffectTrajectoryDecorator at runtime (§4.0)"
```

Each field declares:
- **id**: stable reference (N1-N23, M1-M17, E1-E24, B1-B9, I1-I12)
- **stages**: which pipeline stages must handle it, with `required` or `phase2b`
- **depth_tier**: which entity tiers this field applies to (null = all)
- **status**: `done`, `partial`, `gap`

### 2. Coverage Reports

#### 2a. Post-extraction report (`extract_structure.py`)

After extracting each passage, count:
- Entities with traits assigned vs entities without
- Goal nodes with horizon/status/urgency vs goals without
- Memories with domain classification vs hardcoded "experience"
- Edges with confidence vs edges without
- FormativeExperience memories with situation-types vs without

Output appended to `structure.json`:
```json
{
  "coverage": {
    "node_fields": {"populated": 5, "total": 23, "pct": 22, "threshold": 60},
    "memory_fields": {"populated": 7, "total": 17, "pct": 41, "threshold": 50},
    "gaps": [
      {"id": "N4", "name": "traits", "count_missing": 166, "count_total": 166},
      {"id": "N13", "name": "goal_horizon", "count_missing": 3, "count_total": 3}
    ]
  }
}
```

#### 2b. Post-enrichment report (`enrich_cognitive.py`)

After enriching each passage, the Haiku verification agent checks every applicable field for the artifact type (from §4.0b type-discriminated table). Reports:

```json
{
  "coverage": {
    "enrichment_fields": {"populated": 10, "total": 24, "pct": 42, "threshold": 70},
    "verification": {
      "passages_verified": 16,
      "gaps_justified": 45,
      "gaps_unjustified": 3,
      "retries_triggered": 3,
      "retries_succeeded": 2
    }
  }
}
```

#### 2c. Post-assembly report (`assemble_corpus.py`)

Already produces `model-coverage.json`. Extend to check all 85 fields against the registry:

```json
{
  "stage_coverage": {
    "methodology_to_prompt": {"covered": 24, "total": 85, "pct": 28},
    "prompt_to_corpus": {"covered": 21, "total": 24, "pct": 88},
    "overall": {"covered": 21, "total": 85, "pct": 25}
  },
  "category_breakdown": {
    "node_fields": {"pct": 22, "threshold": 60, "gate": "WARN"},
    "memory_fields": {"pct": 41, "threshold": 50, "gate": "WARN"},
    "enrichment_fields": {"pct": 42, "threshold": 70, "gate": "WARN"},
    "entity_level": {"pct": 0, "threshold": 40, "gate": "FAIL"},
    "importer_derivations": {"pct": 0, "threshold": 30, "gate": "FAIL"}
  }
}
```

#### 2d. Post-import report (`CorpusImporter.java`)

After importing, verify store contents:

```
=== Import Coverage Report ===
Nodes: 166 imported
  Traits assigned:     0/166  (0%)   ⚠ gap
  PAD set:             0/166  (0%)   ⚠ gap
  NodeRef provenance:  0/166  (0%)   ⚠ gap
  Goal properties:     0/3    (0%)   ⚠ gap

Memories: 99 imported
  Domain-split:        0/99   (0%)   ⚠ all "experience"
  SubThought keys:     0/99   (0%)   ⚠ pipe-delimited, not structured

Derivations:
  CognitiveDefaults:   not registered  ❌
  MoodBaseline:        not set         ❌
  Vocabulary:          not registered  ❌

Overall: 15/68 applicable fields (22%)
```

### 3. Verification Agents

Each pipeline stage that involves LLM extraction/enrichment uses a Haiku verification pass.

#### Verification flow per passage:

```
Extract/Enrich (Sonnet/Opus)
    ↓ output
Verify (Haiku)
    ├─ All applicable fields populated? → ✅ pass
    ├─ Field absent + justification present → verify justification against passage text
    │   ├─ Justification true → ✅ justified absence
    │   └─ Justification false → 🔄 retry (max 1)
    └─ Field absent + no justification → 🔄 retry (max 1)
         └─ Still absent after retry → ⚠ log as unjustified gap
```

#### Haiku verification prompt:

```
You are a verification agent. Given:
1. An original biographical passage
2. The extracted/enriched output for that passage
3. The list of fields that should be populated for this artifact type and depth tier

Check each required field:
- If populated: verify the value is reasonable given the passage text
- If absent: the extraction must have provided a justification. Verify the justification is true by reading the passage.
- If absent without justification: flag as unjustified gap

Return: {"verified": true/false, "field_checks": [{"id": "E15", "status": "present|justified_absent|unjustified_absent|incorrect", "reason": "..."}]}
```

#### Cost model:

- Extraction call: ~2000 tokens in, ~1000 out (Sonnet) = ~$0.012/passage
- Verification call: ~1500 tokens in, ~500 out (Haiku) = ~$0.0004/passage
- Verification adds ~3% cost per passage
- Retry adds another extraction call (~$0.012) for ~5-10% of passages

### 4. Script Changes

#### `extract_structure.py` — Phase 1

Update the extraction prompt to request all prescribed Phase 1 fields:
- **Traits**: per-subgraph-type trait assignment (§4.12 table)
- **Goal depth**: horizon, status, urgency, need-tier, priority, feasibility, target-date, goal tier
- **Domain classification**: LLM classifies each memory as experience/relationship/reflection/mood
- **Edge metadata**: confidence origin + validation tier
- **FormativeExperience**: situation-types, salience-multiplier, reinforcement-schedule
- **Temporal**: validFrom/validUntil on nodes
- **Provenance**: extraction-method, extraction-pass on memories
- **Contradiction detection**: contradicts attribute when passages conflict

Add post-extraction coverage check against field registry.

#### `enrich_cognitive.py` — Phase 2a

Update the enrichment prompt to request all prescribed Phase 2a fields:
- **Habituation**: novelty, score, echoes (§4.11)
- **Gut feeling**: valence, intensity, resonance (§4.16)
- **CAPS inputs**: node activations (§4.6) — for Central tier
- **Goal impact**: related goals, relationship type, state change, urgency delta (§4.7)
- **Relationship assessment**: quality signal, other-agent, trust trajectory (§4.8)
- **PAD justification** (§4.1 A4)
- **OCC emotion source**: INTRINSIC/EMPATHIC/ATTRIBUTED (§4.2 E4)
- **Action tendency structure**: dominant + intensity + secondary (§4.4)
- **Drive justification** (§4.5 D5)
- **Confidence justification** (§4.9 F4)
- **Temporal anchoring** (§4.13)
- **Trait assignment** on nodes (§4.12)

Add Haiku verification pass after each enrichment call.

#### New: `enrich_entity.py` — Phase 2b

New script for entity-level enrichment. One call per Central-tier entity with full context:
- **Drive baselines**: per-axis baseline + justification
- **CAPS patterns**: recurring activation patterns
- **Goal coherence**: summary, conflicts, synergies
- **Reflections**: synthesised insights (level 1-2) → stored as reflection domain memories
- **Mood snapshots**: periodic PAD → stored as mood domain memories
- **Behavioural attractors**: recurring approach/avoidance patterns
- **Disposition profile**: 5 axes + justification (primary subject only)
- **Relationship stage transitions**: stage changes across time

Add Haiku verification pass after each entity enrichment.

#### `assemble_corpus.py`

- Read field registry, compute four-stage coverage report
- Include all enrichment fields in corpus output (currently drops many)
- Include traits, goal properties, node PAD, node confidence in corpus nodes
- Include domain-classified memories (not hardcoded "experience")
- Include Phase 2b outputs (reflections, mood snapshots, disposition)
- Produce `coverage-gate-report.json` alongside existing reports

#### `CorpusImporter.java`

- Read all corpus fields and wire into stores
- Assign traits via `NodeInput.withTrait()`
- Set node PAD values
- Set node confidence from corpus (not hardcoded)
- Register vocabulary for edge types
- Set NodeRef provenance
- Import domain-split memories (relationship, reflection, mood)
- Store sub-thoughts via `SubThoughtAttributeKeys`
- Import CAPS inputs, habituation, goal impact as memory attributes
- Derive CognitiveDefaults from disposition profile → register with `CognitiveDefaultsRegistry`
- Derive mood baseline → store initial MoodState
- Produce post-import coverage report

### 5. Implementation Sequence

Top-down by pipeline stage. One pipeline re-run at the end.

| Step | What | Deliverable |
|------|------|-------------|
| 1 | Create `field-registry.yaml` with all 85 fields | Machine-readable registry |
| 2 | Update `extract_structure.py` prompt + coverage check | Extraction covers all Phase 1 fields |
| 3 | Update `enrich_cognitive.py` prompt + Haiku verification | Enrichment covers all Phase 2a fields |
| 4 | Write `enrich_entity.py` + Haiku verification | Phase 2b exists |
| 5 | Update `assemble_corpus.py` + coverage gate report | Corpus carries all fields + 4-stage report |
| 6 | Update `CorpusImporter.java` + import report + derivations | Full cognitive agent after import |
| 7 | Re-run full pipeline on Frida biography | Complete corpus with coverage reports |
| 8 | Surface disposition in personality facets viewer (UI) | Visual payoff |

### 6. Non-goals

- Not changing the methodology doc — it's already prescriptive enough
- Not adding new cognitive capabilities — this is about making scripts faithful to existing methodology
- Not processing Napoleon (#498) — that's a separate corpus, not a pipeline fix
- Not building the avatar narrator (#503) — separate issue

## References

- `cognitive-extraction-methodology.md` — the prescriptive spec (1639 lines)
- `cognitive-model-reference.md` — model type definitions
- `scripts/{extract_structure,enrich_cognitive,assemble_corpus}.py` — current scripts
- `CorpusImporter.java` — current importer
- casehubio/neocortex#514 — exhaustive field registry issue
- casehubio/neocortex#499 — portable personality export (depends on importer derivations)
- casehubio/neocortex#500-502 — lifecycle event model (feeds into temporal fields)
- CLAUDE.md §Cognitive Corpus Coverage Protocol — standing protocol for all sessions
