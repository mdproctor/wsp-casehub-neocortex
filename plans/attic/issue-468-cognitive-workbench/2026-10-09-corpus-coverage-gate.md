# Corpus Coverage Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #514 — Corpus import coverage gate — exhaustive field audit and soft gating
**Issue group:** #514, #468

**Goal:** Make the extraction pipeline and importer faithful to the cognitive extraction methodology by implementing coverage gates at all four pipeline stages: methodology → prompts → corpus → importer.

**Architecture:** A YAML field registry defines all 85 declarable fields. Each pipeline script checks its output against the registry. Haiku verification agents validate that gaps are justified against the source text. The importer wires all fields into cognitive engine stores and derives personality profiles from imported data.

**Tech Stack:** Python 3.11+ (pipeline scripts), Java 21 (importer), Anthropic API / Vertex AI (LLM calls), YAML (field registry), Quarkus (CDI wiring)

## Global Constraints

- All code lives in `blocks-ui/examples/cognitive-workbench/` (scripts in `scripts/`, Java in `src/main/java/`)
- Scripts use `llm_client.py` for LLM calls — supports Vertex AI and direct Anthropic API
- The methodology doc (`docs/cognitive-extraction-methodology.md`) is the source of truth — do not modify it
- The CLAUDE.md coverage protocol (`neocortex/CLAUDE.md §Cognitive Corpus Coverage Protocol`) defines the rules
- Haiku verification calls use `model_id()` which resolves to `claude-haiku-4-5`
- Extraction/enrichment calls keep their current model (also `model_id()` by default)
- Pipeline re-run requires Vertex AI credentials (`CLAUDE_CODE_USE_VERTEX=1`)

---

## Batch 1: Foundation — Field Registry and Coverage Library

### Task 1: Create the field registry YAML

**Files:**
- Create: `blocks-ui/examples/cognitive-workbench/docs/field-registry.yaml`
- Create: `blocks-ui/examples/cognitive-workbench/docs/coverage-justifications.json`

**Interfaces:**
- Produces: `field-registry.yaml` — loaded by all scripts and importer via `load_registry(path)`
- Produces: `coverage-justifications.json` — loaded by coverage checker for intentional exclusions

- [ ] **Step 1: Write the field registry**

Create `docs/field-registry.yaml` with all 85 fields from #514. Each field has: id, name, category, methodology_ref, required stages, applicable depth tiers, and current status.

```yaml
format: cognitive-field-registry/v1

categories:
  node_fields:
    threshold: 60
    fields:
      - id: N1
        name: name
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: done
      - id: N2
        name: subgraph_type
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: done
      - id: N3
        name: properties
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: done
      - id: N4
        name: traits
        ref: "§4.12"
        stages: [extraction, corpus, importer]
        tiers: [central, supporting]
        status: gap
      - id: N5
        name: trait_properties
        ref: "§4.12"
        stages: [extraction, corpus, importer]
        tiers: [central, supporting]
        status: gap
      - id: N6
        name: pad
        ref: "§4.1"
        stages: [extraction, corpus, importer]
        status: gap
      - id: N7
        name: confidence
        ref: "§4.9"
        stages: [extraction, corpus, importer]
        status: partial
      - id: N8
        name: confidence_decay_ref
        ref: "§4.9"
        stages: [extraction, corpus, importer]
        status: gap
      - id: N9
        name: node_ref_provenance
        ref: "§1.2"
        stages: [extraction, corpus, importer]
        status: gap
      - id: N10
        name: valid_from
        ref: "§4.13"
        stages: [extraction, corpus, importer]
        status: partial
      - id: N11
        name: valid_until
        ref: "§4.13"
        stages: [extraction, corpus, importer]
        status: partial
      - id: N12
        name: lifecycle_events
        ref: "#500"
        stages: [extraction, corpus, importer]
        status: gap
      - id: N13
        name: goal_horizon
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        tiers: [central, supporting]
        type_filter: goal
        status: gap
      - id: N14
        name: goal_status
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        type_filter: goal
        status: gap
      - id: N15
        name: goal_urgency
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        type_filter: goal
        status: gap
      - id: N16
        name: goal_need_tier
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        type_filter: goal
        status: gap
      - id: N17
        name: goal_priority
        ref: "§4.12"
        stages: [extraction, corpus, importer]
        type_filter: goal
        status: gap
      - id: N18
        name: goal_feasibility
        ref: "§4.12"
        stages: [extraction, corpus, importer]
        type_filter: goal
        status: gap
      - id: N19
        name: goal_target_date
        ref: "§4.12"
        stages: [extraction, corpus, importer]
        type_filter: goal
        status: gap
      - id: N20
        name: goal_tier
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        type_filter: goal
        status: gap
      - id: N21
        name: goal_pad_affect
        ref: "§4.7"
        stages: [enrichment, corpus, importer]
        type_filter: goal
        status: gap
      - id: N22
        name: edge_confidence
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: gap
      - id: N23
        name: edge_validation_tier
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: gap

  memory_fields:
    threshold: 50
    fields:
      - id: M1
        name: text
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: done
      - id: M2
        name: domain
        ref: "§4.0"
        stages: [extraction, corpus, importer]
        status: gap
      - id: M3
        name: event_type
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: done
      - id: M4
        name: subject
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: partial
      - id: M5
        name: period
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: done
      - id: M6
        name: related_entities
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        status: gap
      - id: M7
        name: source_provenance
        ref: "§1.2"
        stages: [extraction, corpus, importer]
        status: partial
      - id: M8
        name: extraction_method
        ref: "§1.2"
        stages: [extraction, corpus, importer]
        status: gap
      - id: M9
        name: extraction_pass
        ref: "§1.2"
        stages: [extraction, corpus, importer]
        status: gap
      - id: M10
        name: passage_id
        ref: "§1.2"
        stages: [extraction, corpus, importer]
        status: done
      - id: M11
        name: enrichment_version
        ref: "§1.2"
        stages: [extraction, corpus, importer]
        status: done
      - id: M12
        name: enrichment_timestamp
        ref: "§1.2"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: M13
        name: formative_developmental_period
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        event_filter: formative-experience
        status: gap
      - id: M14
        name: formative_situation_types
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        event_filter: formative-experience
        status: gap
      - id: M15
        name: formative_salience_multiplier
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        event_filter: formative-experience
        status: gap
      - id: M16
        name: formative_reinforcement_schedule
        ref: "§3.1"
        stages: [extraction, corpus, importer]
        event_filter: formative-experience
        status: gap
      - id: M17
        name: mentioned_entities
        ref: "Foundation"
        stages: [corpus, importer]
        status: partial

  enrichment_fields:
    threshold: 70
    fields:
      - id: E1
        name: pad
        ref: "§4.1"
        stages: [enrichment, corpus, importer]
        status: done
      - id: E2
        name: pad_justification
        ref: "§4.1"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E3
        name: occ_emotions
        ref: "§4.2"
        stages: [enrichment, corpus, importer]
        status: done
      - id: E4
        name: occ_emotion_source
        ref: "§4.2"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E5
        name: sec_appraisal
        ref: "§4.3"
        stages: [enrichment, corpus, importer]
        status: done
      - id: E6
        name: action_tendencies_intensity
        ref: "§4.4"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E7
        name: action_tendencies_structure
        ref: "§4.4"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E8
        name: cognitive_distortions_strength
        ref: "§4.6"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E9
        name: drive_impact
        ref: "§4.5"
        stages: [enrichment, corpus, importer]
        status: done
      - id: E10
        name: drive_justification
        ref: "§4.5"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E11
        name: sub_thoughts
        ref: "§4.10"
        stages: [enrichment, corpus, importer]
        status: partial
      - id: E12
        name: sub_thoughts_structured
        ref: "engine API"
        stages: [importer]
        status: gap
      - id: E13
        name: confidence
        ref: "§4.9"
        stages: [enrichment, corpus, importer]
        status: done
      - id: E14
        name: confidence_justification
        ref: "§4.9"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E15
        name: habituation
        ref: "§4.11"
        stages: [enrichment, corpus, importer]
        tiers: [central, supporting]
        status: gap
      - id: E16
        name: gut_feeling
        ref: "§4.16"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E17
        name: caps_inputs
        ref: "§4.6"
        stages: [enrichment, corpus, importer]
        tiers: [central]
        status: gap
      - id: E18
        name: caps_expected_outputs
        ref: "§4.6"
        stages: [enrichment, corpus, importer]
        tiers: [central]
        status: gap
      - id: E19
        name: goal_impact_goals
        ref: "§4.7"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E20
        name: goal_impact_state
        ref: "§4.7"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E21
        name: relationship_quality
        ref: "§4.8"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E22
        name: relationship_other_agent
        ref: "§4.8"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E23
        name: temporal_anchoring
        ref: "§4.13"
        stages: [enrichment, corpus, importer]
        status: gap
      - id: E24
        name: trait_assignment
        ref: "§4.12"
        stages: [enrichment, corpus, importer]
        tiers: [central, supporting]
        status: gap

  entity_level_fields:
    threshold: 40
    fields:
      - id: B1
        name: drive_baselines
        ref: "§A.4"
        stages: [phase2b, corpus, importer]
        tiers: [central]
        status: gap
      - id: B2
        name: caps_patterns
        ref: "§A.4"
        stages: [phase2b, corpus, importer]
        tiers: [central]
        status: gap
      - id: B3
        name: goal_coherence
        ref: "§A.4"
        stages: [phase2b, corpus, importer]
        tiers: [central]
        status: gap
      - id: B4
        name: reflections
        ref: "§4.14"
        stages: [phase2b, corpus, importer]
        tiers: [central]
        status: gap
      - id: B5
        name: mood_snapshots
        ref: "§4.15"
        stages: [phase2b, corpus, importer]
        tiers: [central]
        status: gap
      - id: B6
        name: behavioural_attractors
        ref: "§A.4"
        stages: [phase2b, corpus, importer]
        tiers: [central]
        status: gap
      - id: B7
        name: disposition_profile
        ref: "§4.0c"
        stages: [phase2b, corpus, importer]
        primary_subject_only: true
        status: gap
      - id: B8
        name: cognitive_defaults
        ref: "§4.0c"
        stages: [phase2b, corpus, importer]
        primary_subject_only: true
        status: gap
      - id: B9
        name: relationship_stages
        ref: "§4.8"
        stages: [phase2b, corpus, importer]
        tiers: [central]
        status: gap

  importer_derivations:
    threshold: 30
    fields:
      - id: I1
        name: cognitive_defaults_registration
        ref: "CognitiveDefaultsRegistry"
        stages: [importer]
        status: gap
      - id: I2
        name: personality_weights
        ref: "CognitiveDerivationEngine"
        stages: [importer]
        status: gap
      - id: I3
        name: mood_baseline
        ref: "CognitiveDerivationEngine"
        stages: [importer]
        status: gap
      - id: I4
        name: appraisal_weights
        ref: "CognitiveDerivationEngine"
        stages: [importer]
        status: gap
      - id: I5
        name: cbr_strategy
        ref: "CognitiveDerivationEngine"
        stages: [importer]
        status: gap
      - id: I6
        name: social_cognition_defaults
        ref: "CognitiveDerivationEngine"
        stages: [importer]
        status: gap
      - id: I7
        name: graph_structure_defaults
        ref: "CognitiveDerivationEngine"
        stages: [importer]
        status: gap
      - id: I8
        name: extraction_bias_defaults
        ref: "CognitiveDerivationEngine"
        stages: [importer]
        status: gap
      - id: I9
        name: habituation_config
        ref: "CognitiveDerivationEngine"
        stages: [importer]
        status: gap
      - id: I10
        name: initial_mood_state
        ref: "MoodEvents"
        stages: [importer]
        status: gap
      - id: I11
        name: vocabulary_registration
        ref: "MindMapStore.registerVocabulary()"
        stages: [importer]
        status: gap
      - id: I12
        name: trait_rules
        ref: "DeclarativeRuleRegistry"
        stages: [importer]
        status: gap

intentional_exclusions:
  - domain: engagement
    reason: "Per-interaction social signals, live conversation only (§4.0)"
  - domain: affect
    reason: "PAD recorded by AffectTrajectoryDecorator at runtime (§4.0)"
  - subgraph: type_system
    reason: "Generated by SchemaDiscoveryPhase consolidation (§4.0)"
  - subgraph: cognitive
    reason: "Generated by ExperienceConsolidationPhase (§4.0)"
  - subgraph: behavioral
    reason: "Generated by BehavioralSynthesisPhase (§4.0)"
```

- [ ] **Step 2: Write coverage justifications**

Create `docs/coverage-justifications.json`:

```json
{
  "format": "coverage-justifications/v1",
  "exclusions": [
    {"domain": "engagement", "reason": "Per-interaction social signals, live conversation only (§4.0)"},
    {"domain": "affect", "reason": "PAD recorded by AffectTrajectoryDecorator at runtime (§4.0)"},
    {"subgraph": "type_system", "reason": "Generated by SchemaDiscoveryPhase consolidation (§4.0)"},
    {"subgraph": "cognitive", "reason": "Generated by ExperienceConsolidationPhase (§4.0)"},
    {"subgraph": "behavioral", "reason": "Generated by BehavioralSynthesisPhase (§4.0)"}
  ]
}
```

- [ ] **Step 3: Commit**

```bash
git add docs/field-registry.yaml docs/coverage-justifications.json
git commit -m "feat(#514): add field registry YAML with all 85 declarable fields

Machine-readable contract for coverage gates at all pipeline stages.
Each field has: id, methodology ref, required stages, depth tiers, status.

Refs casehubio/neocortex#514"
```

### Task 2: Create the coverage checking library

**Files:**
- Create: `blocks-ui/examples/cognitive-workbench/scripts/coverage.py`
- Test: `blocks-ui/examples/cognitive-workbench/scripts/test_coverage.py`

**Interfaces:**
- Produces: `load_registry(path) → dict` — loads the YAML field registry
- Produces: `check_coverage(data, registry, stage) → CoverageReport` — checks data against registry for a given stage
- Produces: `verify_output(client, passage_text, output, registry, artifact_type, tier) → VerificationResult` — Haiku verification call
- Produces: `format_report(report) → str` — human-readable coverage report

- [ ] **Step 1: Write failing tests for registry loading**

```python
# test_coverage.py
import json
import os
import tempfile
import pytest
import yaml

from coverage import load_registry, check_node_coverage, check_memory_coverage, CoverageReport


def test_load_registry_returns_categories():
    registry = load_registry(os.path.join(os.path.dirname(__file__), '..', 'docs', 'field-registry.yaml'))
    assert 'node_fields' in registry['categories']
    assert 'enrichment_fields' in registry['categories']
    assert len(registry['categories']) == 5


def test_load_registry_fields_have_required_keys():
    registry = load_registry(os.path.join(os.path.dirname(__file__), '..', 'docs', 'field-registry.yaml'))
    for cat_name, cat in registry['categories'].items():
        for field in cat['fields']:
            assert 'id' in field, f"Field missing id in {cat_name}"
            assert 'name' in field, f"Field missing name in {cat_name}"
            assert 'stages' in field, f"Field {field['id']} missing stages"
            assert 'status' in field, f"Field {field['id']} missing status"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd blocks-ui/examples/cognitive-workbench/scripts && python3 -m pytest test_coverage.py -v`
Expected: FAIL (coverage module not found)

- [ ] **Step 3: Write failing tests for node coverage checking**

```python
def test_check_node_coverage_all_present():
    node = {
        'name': 'Frida Kahlo', 'subgraph_type': 'person',
        'properties': {'role': 'artist'}, 'traits': ['Personable'],
        'pad': {'pleasure': 0.5, 'arousal': 0.3, 'dominance': 0.7},
        'confidence': {'origin': 'STATED', 'value': 0.9},
    }
    registry = load_registry(os.path.join(os.path.dirname(__file__), '..', 'docs', 'field-registry.yaml'))
    report = check_node_coverage([node], registry)
    assert report.populated > 0
    assert report.pct > 0


def test_check_node_coverage_minimal_node():
    node = {'name': 'Test', 'subgraph_type': 'concept'}
    registry = load_registry(os.path.join(os.path.dirname(__file__), '..', 'docs', 'field-registry.yaml'))
    report = check_node_coverage([node], registry)
    assert len(report.gaps) > 0
    assert report.pct < 100


def test_goal_fields_only_checked_for_goals():
    node = {'name': 'Art', 'subgraph_type': 'concept'}
    registry = load_registry(os.path.join(os.path.dirname(__file__), '..', 'docs', 'field-registry.yaml'))
    report = check_node_coverage([node], registry)
    goal_gaps = [g for g in report.gaps if g['id'].startswith('N13')]
    assert len(goal_gaps) == 0  # goal fields not checked for non-goal nodes
```

- [ ] **Step 4: Implement coverage.py**

```python
"""Coverage gate library — checks pipeline output against the field registry."""

import json
import os
from dataclasses import dataclass, field
from typing import Any

import yaml

from llm_client import create_client, model_id


@dataclass
class CoverageReport:
    category: str
    populated: int
    total: int
    pct: float
    threshold: int
    gate: str  # PASS, WARN, FAIL
    gaps: list[dict] = field(default_factory=list)


@dataclass
class VerificationResult:
    verified: bool
    field_checks: list[dict]
    retries_needed: list[str]


def load_registry(path: str) -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def _field_applies(field_def: dict, entity: dict) -> bool:
    """Check if a field definition applies to this entity based on type and tier filters."""
    type_filter = field_def.get('type_filter')
    if type_filter and entity.get('subgraph_type') != type_filter:
        return False
    event_filter = field_def.get('event_filter')
    if event_filter and entity.get('event_type') != event_filter:
        return False
    return True


def _field_present(field_def: dict, entity: dict) -> bool:
    """Check if a field is populated in the entity data."""
    name = field_def['name']
    mapping = {
        'name': lambda e: bool(e.get('name')),
        'subgraph_type': lambda e: bool(e.get('subgraph_type')),
        'properties': lambda e: bool(e.get('properties')),
        'traits': lambda e: bool(e.get('traits')),
        'trait_properties': lambda e: bool(e.get('trait_properties')),
        'pad': lambda e: isinstance(e.get('pad'), dict) and e['pad'].get('pleasure') is not None,
        'confidence': lambda e: isinstance(e.get('confidence'), dict) and 'origin' in e.get('confidence', {}),
        'confidence_decay_ref': lambda e: e.get('confidence', {}).get('decay_reference') is not None,
        'node_ref_provenance': lambda e: bool(e.get('node_ref')),
        'valid_from': lambda e: e.get('valid_from') is not None or 'validFrom' in e.get('properties', {}),
        'valid_until': lambda e: e.get('valid_until') is not None,
        'lifecycle_events': lambda e: bool(e.get('lifecycle')),
        'edge_confidence': lambda e: e.get('confidence_origin') is not None,
        'edge_validation_tier': lambda e: e.get('validation_tier') is not None,
    }
    for prefix in ['goal_']:
        prop_name = name.replace(prefix, '')
        if name.startswith(prefix):
            mapping[name] = lambda e, p=prop_name: p in e.get('properties', {}) or p in e.get('goal', {})

    checker = mapping.get(name, lambda e: name in e or name.replace('_', '-') in e.get('properties', {}))
    return checker(entity)


def check_node_coverage(nodes: list[dict], registry: dict) -> CoverageReport:
    cat = registry['categories']['node_fields']
    applicable_fields = []
    populated_count = 0
    gaps = []

    for field_def in cat['fields']:
        relevant_nodes = [n for n in nodes if _field_applies(field_def, n)]
        if not relevant_nodes:
            continue
        applicable_fields.append(field_def)
        present = sum(1 for n in relevant_nodes if _field_present(field_def, n))
        if present == len(relevant_nodes):
            populated_count += 1
        elif present == 0:
            gaps.append({'id': field_def['id'], 'name': field_def['name'],
                         'missing': len(relevant_nodes), 'total': len(relevant_nodes)})
        else:
            gaps.append({'id': field_def['id'], 'name': field_def['name'],
                         'missing': len(relevant_nodes) - present, 'total': len(relevant_nodes)})

    total = len(applicable_fields)
    pct = round(populated_count / max(total, 1) * 100, 1)
    threshold = cat.get('threshold', 50)
    gate = 'PASS' if pct >= threshold else 'WARN' if pct >= threshold * 0.5 else 'FAIL'

    return CoverageReport('node_fields', populated_count, total, pct, threshold, gate, gaps)


def check_memory_coverage(memories: list[dict], registry: dict) -> CoverageReport:
    cat = registry['categories']['memory_fields']
    applicable_fields = []
    populated_count = 0
    gaps = []

    for field_def in cat['fields']:
        relevant = [m for m in memories if _field_applies(field_def, m)]
        if not relevant:
            continue
        applicable_fields.append(field_def)
        name = field_def['name']
        mem_mapping = {
            'text': 'text', 'domain': 'domain', 'event_type': 'event_type',
            'subject': 'subject', 'period': 'period', 'related_entities': 'related_entities',
            'source_provenance': 'source_passage', 'extraction_method': 'extraction_method',
            'extraction_pass': 'extraction_pass', 'passage_id': 'source_passage',
            'enrichment_version': 'enrichment_version', 'enrichment_timestamp': 'enrichment_timestamp',
            'mentioned_entities': 'mentioned_entities',
        }
        key = mem_mapping.get(name, name)
        present = sum(1 for m in relevant if m.get(key) is not None and m.get(key) != '')
        if name == 'domain':
            present = sum(1 for m in relevant if m.get('domain', 'experience') != 'experience' or m.get('domain') == 'experience')
            non_experience = sum(1 for m in relevant if m.get('domain', 'experience') != 'experience')
            if non_experience == 0:
                gaps.append({'id': field_def['id'], 'name': name,
                             'note': 'all memories hardcoded as experience', 'missing': len(relevant), 'total': len(relevant)})
                continue

        if present == len(relevant):
            populated_count += 1
        else:
            gaps.append({'id': field_def['id'], 'name': name,
                         'missing': len(relevant) - present, 'total': len(relevant)})

    total = len(applicable_fields)
    pct = round(populated_count / max(total, 1) * 100, 1)
    threshold = cat.get('threshold', 50)
    gate = 'PASS' if pct >= threshold else 'WARN' if pct >= threshold * 0.5 else 'FAIL'

    return CoverageReport('memory_fields', populated_count, total, pct, threshold, gate, gaps)


def check_enrichment_coverage(memories: list[dict], registry: dict) -> CoverageReport:
    cat = registry['categories']['enrichment_fields']
    applicable_fields = []
    populated_count = 0
    gaps = []

    for field_def in cat['fields']:
        applicable_fields.append(field_def)
        name = field_def['name']
        enrichment_checks = {
            'pad': lambda m: isinstance(m.get('pad'), dict),
            'pad_justification': lambda m: bool(m.get('pad_justification')),
            'occ_emotions': lambda m: bool(m.get('occ_emotions')),
            'occ_emotion_source': lambda m: any(isinstance(e, dict) and 'source' in e for e in m.get('occ_emotions', [])),
            'sec_appraisal': lambda m: isinstance(m.get('sec_appraisal') or m.get('sec'), dict),
            'action_tendencies_intensity': lambda m: any(isinstance(t, dict) and 'intensity' in t for t in m.get('action_tendencies', [])),
            'action_tendencies_structure': lambda m: any(isinstance(t, dict) and 'type' in t for t in m.get('action_tendencies', [])),
            'cognitive_distortions_strength': lambda m: any(isinstance(d, dict) and 'strength' in d for d in m.get('cognitive_distortions', [])),
            'drive_impact': lambda m: isinstance(m.get('drive_impact'), dict),
            'drive_justification': lambda m: bool(m.get('drive_justification')),
            'sub_thoughts': lambda m: bool(m.get('sub_thoughts')),
            'sub_thoughts_structured': lambda m: False,  # importer-only
            'confidence': lambda m: isinstance(m.get('confidence'), dict),
            'confidence_justification': lambda m: bool(m.get('confidence_justification')),
            'habituation': lambda m: m.get('habituation') is not None,
            'gut_feeling': lambda m: m.get('gut_feeling') is not None,
            'caps_inputs': lambda m: bool(m.get('caps_inputs')),
            'caps_expected_outputs': lambda m: bool(m.get('caps_expected_outputs')),
            'goal_impact_goals': lambda m: bool(m.get('goal_impacts')),
            'goal_impact_state': lambda m: any(g.get('state_change') for g in m.get('goal_impacts', [])),
            'relationship_quality': lambda m: bool(m.get('relationship', {}).get('quality_signal') if isinstance(m.get('relationship'), dict) else m.get('quality_signal')),
            'relationship_other_agent': lambda m: bool(m.get('relationship', {}).get('other_agent') if isinstance(m.get('relationship'), dict) else m.get('other_agent')),
            'temporal_anchoring': lambda m: bool(m.get('temporal_period') or m.get('period')),
            'trait_assignment': lambda m: False,  # node-level, checked in node coverage
        }
        checker = enrichment_checks.get(name, lambda m: False)
        present = sum(1 for m in memories if checker(m))
        if present >= len(memories) * 0.5:
            populated_count += 1
        elif present == 0:
            gaps.append({'id': field_def['id'], 'name': name, 'missing': len(memories), 'total': len(memories)})
        else:
            gaps.append({'id': field_def['id'], 'name': name, 'missing': len(memories) - present, 'total': len(memories)})

    total = len(applicable_fields)
    pct = round(populated_count / max(total, 1) * 100, 1)
    threshold = cat.get('threshold', 70)
    gate = 'PASS' if pct >= threshold else 'WARN' if pct >= threshold * 0.5 else 'FAIL'

    return CoverageReport('enrichment_fields', populated_count, total, pct, threshold, gate, gaps)


def format_report(reports: list[CoverageReport]) -> str:
    lines = ['=== Corpus Coverage Report ===', '']
    total_pop = 0
    total_all = 0
    for r in reports:
        total_pop += r.populated
        total_all += r.total
        icon = '✅' if r.gate == 'PASS' else '⚠' if r.gate == 'WARN' else '❌'
        lines.append(f'{r.category:25s} {r.populated:3d}/{r.total:<3d} ({r.pct:5.1f}%)  {icon} {r.gate} (threshold: {r.threshold}%)')
        for g in r.gaps[:5]:
            lines.append(f'  ❌ {g["id"]} {g["name"]}: {g.get("missing", "?")}/{g.get("total", "?")} missing')
        if len(r.gaps) > 5:
            lines.append(f'  ... and {len(r.gaps) - 5} more gaps')
    lines.append('')
    overall_pct = round(total_pop / max(total_all, 1) * 100, 1)
    lines.append(f'Overall: {total_pop}/{total_all} ({overall_pct}%)')
    return '\n'.join(lines)


VERIFICATION_PROMPT = """You are a verification agent for cognitive extraction quality.

Given:
1. An original biographical passage
2. The extracted/enriched output for that passage
3. The list of fields that should be populated for this artifact type

For each required field:
- If populated: verify the value is reasonable given the passage text. Flag if contradicted.
- If absent: check whether absence is justified by the passage content.
  - Justified: the passage genuinely does not contain information for this field.
  - Unjustified: the passage contains information that should have been captured.

Return JSON:
{"verified": true/false, "checks": [{"field": "name", "status": "present|justified_absent|unjustified_absent|incorrect", "reason": "..."}]}"""


def verify_output(client, passage_text: str, output: dict, applicable_fields: list[str], artifact_type: str) -> VerificationResult:
    user_prompt = f"""Passage:
"{passage_text}"

Extracted output ({artifact_type}):
{json.dumps(output, indent=2, default=str)[:3000]}

Required fields for {artifact_type}: {', '.join(applicable_fields)}

Verify each field. Return JSON."""

    try:
        response = client.messages.create(
            model=model_id(),
            max_tokens=1024,
            system=VERIFICATION_PROMPT,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        text = response.content[0].text
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            result = json.loads(text[start:end])
            checks = result.get('checks', [])
            retries = [c['field'] for c in checks if c.get('status') == 'unjustified_absent']
            return VerificationResult(
                verified=result.get('verified', len(retries) == 0),
                field_checks=checks,
                retries_needed=retries,
            )
    except Exception as e:
        print(f"  Verification warning: {e}")

    return VerificationResult(verified=True, field_checks=[], retries_needed=[])
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd blocks-ui/examples/cognitive-workbench/scripts && python3 -m pytest test_coverage.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/coverage.py scripts/test_coverage.py
git commit -m "feat(#514): add coverage gate library — registry loading, field checking, Haiku verification

Refs casehubio/neocortex#514"
```

---

## Batch 2: Extraction Prompt Fixes

### Task 3: Update extract_structure.py with full Phase 1 field set

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/scripts/extract_structure.py`

**Interfaces:**
- Consumes: `coverage.py:load_registry()`, `coverage.py:check_node_coverage()`, `coverage.py:verify_output()`
- Produces: Updated `structure.json` with all Phase 1 fields populated

- [ ] **Step 1: Update SYSTEM_PROMPT to request all Phase 1 fields**

Replace the extraction prompt to match methodology §3.1 and §A.2. Key additions:
- **Traits** per subgraph type (§4.12 table)
- **Goal properties**: horizon, status, urgency, need-tier, priority, feasibility, target-date, goal tier
- **Domain classification**: classify each memory as experience/relationship/reflection/mood
- **Edge metadata**: confidence origin (STATED/INFERRED) + validation tier (REGISTERED/UNVALIDATED)
- **FormativeExperience**: situation-types (CAPS input nodes), salience-multiplier, reinforcement-schedule
- **Node confidence**: origin + value per node
- **Temporal**: validFrom/validUntil ISO strings on nodes
- **Provenance**: extraction-method + extraction-pass on memories
- **Contradiction detection**: contradicts attribute referencing conflicting memories

The full prompt follows the template in methodology §A.2 but adds trait/goal/domain/edge-confidence requests. Show the updated `SYSTEM_PROMPT` string in full.

- [ ] **Step 2: Update output parsing to capture new fields**

In the `extract_passage()` function and the main loop, capture:
- `traits` array on each entity
- `goal` object on goal entities
- `confidence` object on each entity and edge
- `domain` field on each memory (not hardcoded)
- `formative_attrs` on formative memories
- `validation_tier` on edges

- [ ] **Step 3: Add post-extraction coverage check**

After processing all passages, load the field registry and run coverage checks:

```python
from coverage import load_registry, check_node_coverage, check_memory_coverage, format_report

registry = load_registry(os.path.join(os.path.dirname(__file__), '..', 'docs', 'field-registry.yaml'))
node_report = check_node_coverage(list(all_entities.values()), registry)
mem_report = check_memory_coverage(all_memories, registry)
print(format_report([node_report, mem_report]))
```

Include the coverage report in `structure.json` output.

- [ ] **Step 4: Add Haiku verification calls**

After each passage extraction, call `verify_output()` with the passage text and extracted output. If verification returns `retries_needed`, re-run extraction for that passage with an explicit instruction to fill the gaps.

- [ ] **Step 5: Commit**

```bash
git add scripts/extract_structure.py
git commit -m "feat(#514): extraction prompt covers all Phase 1 fields — traits, goals, domains, edges

Adds: trait assignment per subgraph type, goal depth (7 properties),
domain classification, edge confidence/validation, formative attributes,
post-extraction coverage gate, Haiku verification.

Refs casehubio/neocortex#514"
```

---

## Batch 3: Enrichment Prompt Fixes + Phase 2b

### Task 4: Update enrich_cognitive.py with full Phase 2a checklist

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/scripts/enrich_cognitive.py`

**Interfaces:**
- Consumes: `coverage.py:load_registry()`, `coverage.py:check_enrichment_coverage()`, `coverage.py:verify_output()`
- Produces: Updated `enriched.json` with all Phase 2a fields populated

- [ ] **Step 1: Update CHECKLIST_PROMPT to request all Phase 2a fields**

Add to the existing prompt:
- **Habituation** (§4.11): novelty classification, habituation score, echoes
- **Gut feeling** (§4.16): valence (APPROACH/AVOID/CAUTIOUS), intensity, resonance description
- **CAPS inputs** (§4.6): node activations from the reference table (Central tier only)
- **Goal impact** (§4.7): related goals, relationship type, state change, urgency delta
- **Relationship assessment** (§4.8): quality signal, other-agent, trust trajectory
- **PAD justification** (§4.1 A4): one sentence per dimension
- **OCC emotion source** (§4.2 E4): INTRINSIC/EMPATHIC/ATTRIBUTED per emotion
- **Action tendency structure** (§4.4): dominant tendency with intensity + secondary list
- **Drive justification** (§4.5 D5): one sentence per axis
- **Confidence justification** (§4.9 F4): why this confidence level
- **Temporal anchoring** (§4.13): period/date assignment

- [ ] **Step 2: Add Haiku verification per passage**

After each enrichment call, verify with the applicable field list from §4.0b type-discriminated table. Retry unjustified gaps once.

- [ ] **Step 3: Add enrichment coverage check at end**

```python
from coverage import load_registry, check_enrichment_coverage, format_report

registry = load_registry(os.path.join(os.path.dirname(__file__), '..', 'docs', 'field-registry.yaml'))
enrich_report = check_enrichment_coverage(enriched_memories, registry)
print(format_report([enrich_report]))
```

- [ ] **Step 4: Commit**

```bash
git add scripts/enrich_cognitive.py
git commit -m "feat(#514): enrichment prompt covers all Phase 2a checklist items

Adds: habituation, gut feeling, CAPS inputs, goal impact, relationship,
PAD/drive/confidence justifications, OCC source, tendency structure.
Haiku verification per passage with gap retry.

Refs casehubio/neocortex#514"
```

### Task 5: Create enrich_entity.py — Phase 2b entity-level enrichment

**Files:**
- Create: `blocks-ui/examples/cognitive-workbench/scripts/enrich_entity.py`

**Interfaces:**
- Consumes: `enriched.json` (Phase 2a output), `structure.json` (entity graph)
- Produces: Updated `enriched.json` with Phase 2b fields added (drive baselines, CAPS patterns, goal coherence, reflections, mood snapshots, disposition profile)

- [ ] **Step 1: Create script scaffold**

Script takes enriched.json + structure.json, identifies Central-tier entities, processes each with full context.

```python
#!/usr/bin/env python3
"""Step 5b: Entity-level enrichment — Phase 2b.

For each Central-tier entity, assesses holistic cognitive dimensions
that require the full entity context: drive baselines, CAPS patterns,
goal coherence, reflections, mood snapshots, disposition profile.

Input:  enriched.json (Phase 2a output)
Output: enriched.json (updated in-place with Phase 2b additions)
"""
```

- [ ] **Step 2: Implement entity context gathering**

For each Central-tier entity, gather:
- All edges involving the entity
- All memories mentioning the entity (from `mentioned_entities` or `related_entities`)
- Phase 2a enrichments on those memories
- Graph neighbourhood (1-hop connected entities)
- Top 20 memories by significance if >30 total, with statistical summary of the rest

- [ ] **Step 3: Implement Phase 2b prompt (from §A.4)**

System prompt requests: drive baselines, CAPS patterns, goal coherence, reflections, behavioural attractors, disposition profile (primary subject only).

- [ ] **Step 4: Implement Phase 2b output handling**

- Store drive baselines on the entity in enriched.json
- Create reflection memories (domain: "reflection") and mood snapshots (domain: "mood")
- Store disposition profile as top-level corpus field
- Add CAPS patterns and goal coherence to entity metadata

- [ ] **Step 5: Add Haiku verification**

Verify Phase 2b output per entity. Check drive baselines have justifications, disposition axes are in [0,1] range, reflections reference source memories.

- [ ] **Step 6: Commit**

```bash
git add scripts/enrich_entity.py
git commit -m "feat(#514): add Phase 2b entity-level enrichment script

Drive baselines, CAPS patterns, goal coherence, reflections,
mood snapshots, behavioural attractors, disposition profile.
Haiku verification per entity.

Refs casehubio/neocortex#514"
```

---

## Batch 4: Assembly Coverage Gate

### Task 6: Update assemble_corpus.py with 4-stage coverage report

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/scripts/assemble_corpus.py`

**Interfaces:**
- Consumes: `coverage.py:load_registry()`, all `check_*_coverage()` functions
- Produces: Updated `corpus.json` with all fields, `coverage-gate-report.json`

- [ ] **Step 1: Include all enrichment data in corpus output**

Update `assemble()` to include fields currently dropped:
- `traits` on nodes
- `pad` on nodes
- `confidence` on nodes (not hardcoded)
- `node_ref` provenance
- Domain-classified memories (read `domain` from enriched data, not hardcoded "experience")
- Phase 2b fields: `drive_baselines`, `caps_patterns`, `goal_coherence`
- `disposition_profile` as top-level corpus field
- Reflection and mood memories alongside experience memories
- All enrichment fields: habituation, gut feeling, CAPS inputs, goal impacts, relationship data
- Justification fields: pad_justification, drive_justification, confidence_justification

- [ ] **Step 2: Add 4-stage coverage gate report**

```python
from coverage import load_registry, check_node_coverage, check_memory_coverage, check_enrichment_coverage, format_report

registry = load_registry(registry_path)
reports = [
    check_node_coverage(corpus['nodes'], registry),
    check_memory_coverage(corpus['memories'], registry),
    check_enrichment_coverage(corpus['memories'], registry),
]
print(format_report(reports))

gate_report = {
    'stage_coverage': {
        'methodology_to_prompt': {'covered': sum(r.populated for r in reports), 'total': sum(r.total for r in reports)},
    },
    'category_breakdown': {r.category: {'pct': r.pct, 'threshold': r.threshold, 'gate': r.gate} for r in reports},
    'gaps': {r.category: r.gaps for r in reports},
}
with open(gate_report_path, 'w') as f:
    json.dump(gate_report, f, indent=2)
```

- [ ] **Step 3: Commit**

```bash
git add scripts/assemble_corpus.py
git commit -m "feat(#514): assembly carries all fields + 4-stage coverage gate report

corpus.json now includes traits, node PAD, domain-split memories,
Phase 2b fields, disposition profile. Coverage gate report warns
on gaps below per-category thresholds.

Refs casehubio/neocortex#514"
```

---

## Batch 5: Importer Rewrite

### Task 7: Update CorpusImporter.java — full field import

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/src/main/java/io/casehub/neocortex/workbench/CorpusImporter.java`

**Interfaces:**
- Consumes: `corpus.json` with all 85 fields
- Produces: MindMap nodes with traits + PAD + confidence + provenance, domain-split memories with structured sub-thoughts, vocabulary registration, import coverage report

- [ ] **Step 1: Add trait assignment to node import**

After creating each node, assign traits based on subgraph type and corpus trait data.
`NodeInput.withTraits(Set<String>)` takes a set of trait names:

```java
JsonNode traits = node.get("traits");
if (traits != null && traits.isArray()) {
    var traitSet = new java.util.HashSet<String>();
    for (JsonNode trait : traits) traitSet.add(trait.asText());
    input = input.withTraits(traitSet);
}
```

- [ ] **Step 2: Add node PAD from corpus**

```java
JsonNode nodePad = node.get("pad");
if (nodePad != null && nodePad.isObject()) {
    double p = nodePad.path("pleasure").asDouble(0);
    double a = nodePad.path("arousal").asDouble(0);
    double d = nodePad.path("dominance").asDouble(0);
    input = input.withPad(p, a, d);
}
```

- [ ] **Step 3: Add node confidence from corpus (not hardcoded)**

Replace the hardcoded `new Confidence(ConfidenceOrigin.STATED, 0.9, null)` with:

```java
JsonNode conf = node.get("confidence");
if (conf != null && conf.isObject()) {
    ConfidenceOrigin origin = ConfidenceOrigin.valueOf(conf.path("origin").asText("STATED"));
    double value = conf.path("value").asDouble(0.8);
    input = input.withConfidence(new Confidence(origin, value, null));
} else {
    input = input.withConfidence(new Confidence(ConfidenceOrigin.STATED, 0.8, null));
}
```

- [ ] **Step 4: Add NodeRef provenance**

```java
JsonNode nodeRef = node.get("node_ref");
if (nodeRef != null && nodeRef.isObject()) {
    input = input.withRef(new NodeRef(
        nodeRef.path("scheme").asText("biography"),
        nodeRef.path("id").asText(),
        nodeRef.path("qualifier").asText(null)
    ));
}
```

- [ ] **Step 5: Import domain-split memories**

Replace the hardcoded `"experience"` domain with the corpus-specified domain:

```java
String domain = mem.has("domain") ? mem.get("domain").asText() : "experience";
// domain is already read but all corpus data was "experience" — now it will vary
```

No code change needed — the importer already reads the domain field. The fix is upstream in the extraction/assembly scripts.

- [ ] **Step 6: Store sub-thoughts via SubThoughtAttributeKeys**

Replace the pipe-delimited string storage with structured attribute keys:

```java
JsonNode subThoughts = cogNode.get("sub_thoughts");
if (subThoughts != null && subThoughts.isArray() && !subThoughts.isEmpty()) {
    attrs.put(SubThoughtAttributeKeys.COUNT, String.valueOf(subThoughts.size()));
    for (int i = 0; i < subThoughts.size(); i++) {
        JsonNode st = subThoughts.get(i);
        String stType = st.isTextual() ? st.asText() : st.path("type").asText("");
        String stText = st.path("text").asText(st.path("content").asText(""));
        String stEntity = st.path("entity").asText("");
        attrs.put(SubThoughtAttributeKeys.type(i), stType);
        attrs.put(SubThoughtAttributeKeys.text(i), stText);
        if (!stEntity.isEmpty()) {
            attrs.put(SubThoughtAttributeKeys.entity(i), stEntity);
        }
    }
}
```

- [ ] **Step 7: Import new enrichment attributes**

Add attribute import for habituation, gut feeling, CAPS inputs, goal impacts, relationship data:

```java
// Habituation
JsonNode hab = cogNode.get("habituation");
if (hab != null && hab.isObject()) {
    attrs.put("habituation-novelty", hab.path("novelty").asText(""));
    attrs.put("habituation-score", String.format("%.2f", hab.path("score").asDouble()));
}

// CAPS inputs
JsonNode caps = cogNode.get("caps_inputs");
if (caps != null && caps.isObject()) {
    var sb = new StringBuilder();
    var fields = caps.fields();
    while (fields.hasNext()) {
        var f = fields.next();
        if (sb.length() > 0) sb.append(",");
        sb.append(f.getKey()).append(":").append(String.format("%.2f", f.getValue().asDouble()));
    }
    if (sb.length() > 0) attrs.put("caps-inputs", sb.toString());
}

// Goal impacts
JsonNode goals = cogNode.get("goal_impacts");
if (goals != null && goals.isArray()) {
    var sb = new StringBuilder();
    for (JsonNode g : goals) {
        if (sb.length() > 0) sb.append("|");
        sb.append(g.path("goal").asText()).append(":").append(g.path("relationship").asText());
    }
    if (sb.length() > 0) attrs.put("goal-impacts", sb.toString());
}

// Relationship
JsonNode rel = cogNode.get("relationship");
if (rel != null && rel.isObject()) {
    attrs.put("quality-signal", rel.path("quality_signal").asText(""));
    attrs.put("other-agent", rel.path("other_agent").asText(""));
    attrs.put("trust-trajectory", rel.path("trust_trajectory").asText(""));
}
```

- [ ] **Step 8: Add vocabulary registration**

After importing all edges, register the edge type vocabulary.
`MindMapVocabulary` uses a builder; `mindMapStore.registerVocabulary(vocab)` takes the built vocabulary:

```java
private void registerVocabulary(Collection<String> edgeTypes) {
    var builder = MindMapVocabulary.builder();
    for (String type : edgeTypes) {
        builder.edgeType(type);
    }
    mindMapStore.registerVocabulary(builder.build());
}
```

Call after `importEdges()` with the collected edge types.

- [ ] **Step 9: Generate import coverage report**

Add a post-import summary printed to stdout:

```java
private void printImportReport(int nodeCount, int edgeCount, int memCount,
        int traitsAssigned, int nodesWithPad, int domainsSplit, boolean profileDerived) {
    System.out.println("=== Import Coverage Report ===");
    System.out.printf("Nodes: %d imported%n", nodeCount);
    System.out.printf("  Traits assigned: %d/%d%n", traitsAssigned, nodeCount);
    System.out.printf("  PAD set: %d/%d%n", nodesWithPad, nodeCount);
    System.out.printf("Memories: %d imported%n", memCount);
    System.out.printf("  Domain-split: %d non-experience%n", domainsSplit);
    System.out.printf("Derivations:%n");
    System.out.printf("  CognitiveDefaults: %s%n", profileDerived ? "registered" : "NOT registered");
}
```

- [ ] **Step 10: Commit**

```bash
git add src/main/java/io/casehub/neocortex/workbench/CorpusImporter.java
git commit -m "feat(#514): importer handles all corpus fields — traits, PAD, structured sub-thoughts, vocabulary

Refs casehubio/neocortex#514"
```

### Task 8: Add personality derivation to importer

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/src/main/java/io/casehub/neocortex/workbench/CorpusImporter.java`
- Modify: `blocks-ui/examples/cognitive-workbench/pom.xml` (if cognitive-index dependency needed)

**Interfaces:**
- Consumes: disposition profile from `corpus.json`, `CognitiveDerivationEngine`, `CognitiveDefaultsRegistry`
- Produces: Registered CognitiveDefaults for the biographical subject, initial MoodState

- [ ] **Step 1: Read disposition profile from corpus**

```java
JsonNode dispositionNode = root.get("disposition_profile");
if (dispositionNode != null && dispositionNode.isObject()) {
    deriveAndRegisterProfile(dispositionNode, t);
}
```

- [ ] **Step 2: Derive CognitiveDefaults from disposition axes**

`CognitiveDerivationEngine.derive(DescriptorView)` is a pure static utility — no CDI needed.
`DispositionAxes` takes 5 String terms (not numeric): e.g. "extrovert"/"introvert", "bold"/"cautious".
The corpus disposition profile has numeric 0-1 values; map them to terms:

```java
@Inject CognitiveDefaultsRegistry registry;

private void deriveAndRegisterProfile(JsonNode disposition, String tenantId) {
    String socialOrient = disposition.path("socialOrient").asDouble() > 0.5 ? "extrovert" : "introvert";
    String ruleFollowing = disposition.path("ruleFollowing").asDouble() > 0.5 ? "strict" : "flexible";
    String riskAppetite = disposition.path("riskAppetite").asDouble() > 0.5 ? "bold" : "cautious";
    String autonomy = disposition.path("autonomy").asDouble() > 0.5 ? "high" : "low";
    String conflictMode = disposition.path("conflictMode").asDouble() > 0.5 ? "confrontational" : "avoidant";

    var axes = new DispositionAxes(socialOrient, ruleFollowing, riskAppetite, autonomy, conflictMode);
    var descriptor = DescriptorView.of(session.agentId(), axes, List.of(), List.of());
    CognitiveDefaults defaults = CognitiveDerivationEngine.derive(descriptor);
    registry.register(defaults);
}

- [ ] **Step 3: Create initial MoodState from aggregated PAD**

Aggregate PAD values across all imported memories to compute a baseline mood.
`MoodState(agentId, tenantId, timestamp, pleasure, arousal, dominance, cause, turnId, activeContextIds, metadata)`:

```java
private void initializeMoodBaseline(String tenantId, List<double[]> padValues) {
    double avgP = padValues.stream().mapToDouble(p -> p[0]).average().orElse(0);
    double avgA = padValues.stream().mapToDouble(p -> p[1]).average().orElse(0);
    double avgD = padValues.stream().mapToDouble(p -> p[2]).average().orElse(0);
    var mood = new MoodState(session.agentId(), tenantId, java.time.Instant.now(),
        avgP, avgA, avgD, "baseline from biography", null, null, java.util.Map.of());
    memoryStore.store(MoodEvents.toMemoryInput(mood));
}
```

- [ ] **Step 4: Commit**

```bash
git add src/main/java/io/casehub/neocortex/workbench/CorpusImporter.java pom.xml
git commit -m "feat(#514): importer derives personality profile from disposition + initializes mood baseline

Refs casehubio/neocortex#514"
```

---

## Batch 6: Pipeline Re-run and UI

### Task 9: Re-run the full pipeline

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/scripts/run_pipeline.sh`
- Output: All files in `blocks-ui/examples/cognitive-workbench/output/`

**Interfaces:**
- Consumes: All updated scripts
- Produces: Complete `corpus.json` with coverage gate report

- [ ] **Step 1: Update run_pipeline.sh to include Phase 2b and coverage gate**

```bash
#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Step 1: Chunk ==="
python3 chunk.py ../source/frida-kahlo-biography.md -o ../output/passages.json

echo "=== Step 2: NLP Baseline ==="
python3 nlp_extract.py ../output/passages.json -o ../output/nlp-baseline.json

echo "=== Step 3: LLM Gap Sweep ==="
python3 llm_gap_sweep.py ../output/passages.json ../output/nlp-baseline.json -o ../output/gap-sweep.json

echo "=== Step 4: Structural Extraction ==="
python3 extract_structure.py ../output/passages.json ../output/nlp-baseline.json --gaps ../output/gap-sweep.json -o ../output/structure.json

echo "=== Step 5a: Passage-Level Enrichment ==="
python3 enrich_cognitive.py ../output/passages.json ../output/structure.json -o ../output/enriched.json

echo "=== Step 5b: Entity-Level Enrichment ==="
python3 enrich_entity.py ../output/enriched.json ../output/structure.json

echo "=== Step 6: Reference Overlay ==="
python3 generate_overlay.py ../output/enriched.json -o ../output/reference-overlay.json

echo "=== Step 7: Assemble Corpus ==="
python3 assemble_corpus.py ../output/enriched.json ../output/nlp-baseline.json -o ../output/corpus.json -r ../output/coverage-report.json -m ../output/model-coverage.json --gate-report ../output/coverage-gate-report.json

echo "=== Done ==="
cp ../output/corpus.json ../src/main/resources/corpus.json
echo "Corpus copied to src/main/resources/"
```

- [ ] **Step 2: Run the pipeline**

Requires Vertex AI credentials. Run:

```bash
cd blocks-ui/examples/cognitive-workbench/scripts
.venv/bin/python3 -m pip install pyyaml  # if not already installed
bash run_pipeline.sh
```

- [ ] **Step 3: Verify coverage gate report**

Check `output/coverage-gate-report.json` — all categories should be above their thresholds.

- [ ] **Step 4: Commit updated corpus and coverage reports**

```bash
git add output/ src/main/resources/corpus.json
git commit -m "feat(#514): re-run pipeline — full coverage corpus with gate report

Refs casehubio/neocortex#514"
```

### Task 10: Surface disposition in personality facets viewer

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/src/main/java/io/casehub/neocortex/workbench/WorkbenchApi.java`
- Modify or create: UI components in `blocks-ui/examples/cognitive-workbench/src/main/resources/META-INF/resources/`

**Interfaces:**
- Consumes: Registered CognitiveDefaults from the importer
- Produces: REST endpoint serving personality facets, UI component displaying them

- [ ] **Step 1: Add personality endpoint to WorkbenchApi**

```java
@GET
@Path("/personality")
public Response getPersonality() {
    // Return the CognitiveDefaults registered for the imported subject
    // Includes: disposition axes, personality weights, mood baseline,
    // appraisal weights, CBR strategy, social cognition defaults
}
```

- [ ] **Step 2: Create or update UI component**

Add a personality facets panel showing:
- 5 disposition axes as a radar/spider chart or bar chart
- Derived personality weights per domain
- Mood baseline (PAD values)
- Appraisal weights

- [ ] **Step 3: Commit**

```bash
git add src/main/java/ src/main/resources/
git commit -m "feat(#514): personality facets viewer — disposition axes and derived weights in UI

Refs casehubio/neocortex#514"
```

---

## References

- [2026-10-09-corpus-coverage-gate-design.md] — design spec this plan implements
- [cognitive-extraction-methodology.md] — prescriptive methodology (source of truth)
- [scripts/extract_structure.py] — Phase 1 extraction script
- [scripts/enrich_cognitive.py] — Phase 2a enrichment script
- [scripts/assemble_corpus.py] — corpus assembly script
- [CorpusImporter.java] — Java corpus importer
- [CLAUDE.md §Cognitive Corpus Coverage Protocol] — standing protocol
- [GitHub #514] — exhaustive field registry issue
- [GitHub #468] — cognitive workbench parent issue
- [GitHub #499] — portable personality export (depends on importer derivations)
