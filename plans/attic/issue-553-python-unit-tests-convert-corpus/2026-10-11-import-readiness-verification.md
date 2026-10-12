# Import Readiness Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #550 — Import readiness verification — repeatable QA gate for corpus output
**Issue group:** #538 (epic), #539, #550

**Goal:** Build `verify_corpus.py` — a standalone QA tool that diagnoses import-readiness issues in `corpus.json`, attributes each finding to its pipeline stage with pragmatic fix-level recommendations, and applies safe fixes when run with `--fix`.

**Architecture:** Schema-driven verification. A `verify_schema.yaml` declares the Java-side import contract (field mappings, vocabularies, ranges, aliases). `verify_corpus.py` loads this schema, validates `corpus.json` against it, produces a structured report (JSON + human-readable), and optionally applies safe fixes. Runs as the final pipeline step after `assemble_corpus.py`.

**Tech Stack:** Python 3, PyYAML (already a dependency), argparse, json, dataclasses

## Global Constraints

- Python script in `extraction/scripts/`, tests in `extraction/tests/`
- Follow existing CLI patterns from `assemble_corpus.py` (argparse, atomic_write from pipeline_state)
- Tests use `conftest.py` sys.path setup — import by module name, not path
- No new dependencies beyond what `assemble_corpus.py` already uses (json, yaml, argparse, os)
- Exit codes: 0 = pass, 1 = CRITICAL, 2 = WARNING only (INFO doesn't affect exit)

---

## Batch 1: Schema and Core Verification Engine

### Task 1: Create verify_schema.yaml — Java-side import contract

**Files:**
- Create: `extraction/docs/verify_schema.yaml`

**Interfaces:**
- Produces: YAML schema loaded by `verify_corpus.py` via `yaml.safe_load()`

- [ ] **Step 1: Write the schema file**

```yaml
format_version: 1

entity_aliases:
  "Frida": "Frida Kahlo"
  "Diego": "Diego Rivera"
  "Leon Trotsky": "León Trotsky"
  "The Two Fridas": "Las dos Fridas"
  "Self-Portrait with Cropped Hair": "Autorretrato con pelo cortado"

entity_types:
  goal:
    subgraph_type: GOAL
    field_mappings:
      goal_tier: tier
      goal_horizon: horizon
      goal_status: status
      goal_urgency: urgency
      goal_need_tier: need_tier
      goal_priority: priority
      goal_feasibility: feasibility
      goal_target_date: target_date
    required_fields:
      - name
      - tier
    vocabularies:
      content_domain:
        values:
          - morality-and-virtue
          - religion-and-spirituality
          - self-actualisation
          - avoidance
          - social-relating
          - health
          - family
          - mastery-and-competence
          - financial-and-occupational
        source: GoalVocabulary.CONTENT_DOMAINS
      content_subdomain:
        values:
          - social-values
          - personal-morals
          - help-others
          - highly-regarded
          - religion-and-spirituality
          - wisdom-and-serenity
          - self-knowledge-and-happiness
          - appreciating-beauty
          - exploration-and-passions
          - enjoy-life
          - avoid-stress-harm-rejection-conflict
          - avoid-hassles
          - relate-and-belong
          - intimacy
          - stability
          - power
          - leadership
          - health
          - family
          - achievement
          - self-efficacy
          - practical-competence
          - intellectual-competence
          - finances
          - occupational-success
        source: GoalVocabulary.CONTENT_SUBDOMAINS
      motivation_origin:
        values:
          - intrinsic
          - identified
          - introjected
          - external
        source: GoalVocabulary.MOTIVATION_ORIGINS
    ranges:
      pad.pleasure: [-1.0, 1.0]
      pad.arousal: [-1.0, 1.0]
      pad.dominance: [-1.0, 1.0]
      clarity: [0.0, 1.0]
    volume:
      warn_above: 60

  place:
    subgraph_type: PLACE
    required_fields:
      - name
    ranges:
      pad.pleasure: [-1.0, 1.0]
      pad.arousal: [-1.0, 1.0]
      pad.dominance: [-1.0, 1.0]

  relationship:
    subgraph_type: PERSON
    required_fields:
      - name
    ranges:
      affect.pad.pleasure: [-1.0, 1.0]
      affect.pad.arousal: [-1.0, 1.0]
      affect.pad.dominance: [-1.0, 1.0]
      dynamics.trust: [0.0, 1.0]

  belief:
    subgraph_type: COGNITIVE
    required_fields:
      - description
    ranges:
      confidence: [0.0, 1.0]

  life_event:
    required_fields:
      - description
    ranges:
      pad.pleasure: [-1.0, 1.0]
      pad.arousal: [-1.0, 1.0]
      pad.dominance: [-1.0, 1.0]
    sub_thought_types:
      - affect-observation
      - causal-inference
      - evaluative
      - intention
      - self-reflection
      - association
      - concern

  activity:
    subgraph_type: ACTIVITY
    required_fields:
      - name

  project:
    subgraph_type: PROJECT
    required_fields:
      - name

  cultural_context:
    subgraph_type: CULTURAL
    required_fields:
      - description

  current_state:
    ranges:
      mood.pleasure: [-1.0, 1.0]
      mood.arousal: [-1.0, 1.0]
      mood.dominance: [-1.0, 1.0]

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
    - inspires
    - opposes
    - influences
    - teaches
    - mentors
  dangling:
    critical_pct: 10
    warn_pct: 2

memories:
  valid_domains:
    - experience
    - relationship
    - reflection
    - mood
  enrichment_fields:
    - pad
    - occ_emotions
    - sec_appraisal
    - action_tendencies
    - sub_thoughts
    - cognitive_distortions
    - drive_impact
    - confidence
  enrichment_threshold: 80
```

- [ ] **Step 2: Commit**

```bash
git add extraction/docs/verify_schema.yaml
git commit -m "feat(#550): add verify_schema.yaml — Java-side import contract

Declares field mappings, vocabularies, ranges, entity aliases, and edge
types that the Java BiographyImportRunner expects. Used by verify_corpus.py
to validate corpus.json before import.

Refs #550"
```

### Task 2: Create verify_corpus.py — core verification engine with tests

**Files:**
- Create: `extraction/scripts/verify_corpus.py`
- Create: `extraction/tests/test_verify_corpus.py`

**Interfaces:**
- Consumes: `verify_schema.yaml` (YAML dict), `corpus.json` (JSON dict with `nodes`, `edges`, `memories` keys)
- Produces: verification report dict (JSON-serializable), corrected corpus dict (when `--fix`)

- [ ] **Step 1: Write the failing tests**

`extraction/tests/test_verify_corpus.py`:

```python
"""Tests for import readiness verification."""

import copy
import os
import pytest

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), '..', 'docs', 'verify_schema.yaml')


def _minimal_corpus(nodes=None, edges=None, memories=None):
    return {
        'format': 'cognitive-workbench-corpus/v2',
        'subject': 'Test Subject',
        'stats': {},
        'nodes': nodes or [],
        'edges': edges or [],
        'memories': memories or [],
    }


def _goal_node(name='Test Goal', **overrides):
    node = {
        'name': name,
        'subgraph_type': 'GOAL',
        'properties': {},
        'goal_tier': 'strategic',
        'goal_horizon': 'long',
        'content_domain': 'health',
        'motivation_origin': 'intrinsic',
    }
    node.update(overrides)
    return node


def _person_node(name='Frida Kahlo'):
    return {'name': name, 'subgraph_type': 'PERSON', 'properties': {}}


def _place_node(name='La Casa Azul'):
    return {'name': name, 'subgraph_type': 'PLACE', 'properties': {}}


def _edge(source, target, edge_type='associated-with'):
    return {'source': source, 'target': target, 'type': edge_type}


def _memory(text='A memory', domain='experience', subject='Frida Kahlo', **overrides):
    m = {'text': text, 'domain': domain, 'subject': subject}
    m.update(overrides)
    return m


# --- Schema loading ---

def test_load_schema():
    from verify_corpus import load_schema
    schema = load_schema(SCHEMA_PATH)
    assert schema['format_version'] == 1
    assert 'goal' in schema['entity_types']
    assert 'entity_aliases' in schema


def test_load_schema_missing_file():
    from verify_corpus import load_schema
    with pytest.raises(FileNotFoundError):
        load_schema('/nonexistent/schema.yaml')


# --- Dangling edges ---

def test_dangling_edge_detected():
    from verify_corpus import verify
    schema = load_test_schema()
    corpus = _minimal_corpus(
        nodes=[_person_node('Frida Kahlo')],
        edges=[_edge('Frida Kahlo', 'Nonexistent Place')],
    )
    report = verify(corpus, schema)
    dangling = [f for f in report['findings'] if f['category'] == 'dangling_edge']
    assert len(dangling) >= 1
    assert dangling[0]['severity'] == 'CRITICAL'


def test_dangling_edge_fixable_via_alias():
    from verify_corpus import verify
    schema = load_test_schema()
    corpus = _minimal_corpus(
        nodes=[_person_node('Frida Kahlo'), _place_node('La Casa Azul')],
        edges=[_edge('Frida', 'La Casa Azul', 'lives-at')],
    )
    report = verify(corpus, schema)
    dangling = [f for f in report['findings'] if f['category'] == 'dangling_edge']
    assert len(dangling) >= 1
    assert dangling[0]['severity'] == 'FIXABLE'


def test_alias_resolution_fix():
    from verify_corpus import verify, apply_fixes
    schema = load_test_schema()
    corpus = _minimal_corpus(
        nodes=[_person_node('Frida Kahlo'), _place_node('La Casa Azul')],
        edges=[_edge('Frida', 'La Casa Azul', 'lives-at')],
    )
    report = verify(corpus, schema)
    fixed_corpus, fixed_report = apply_fixes(corpus, report, schema)
    assert fixed_corpus['edges'][0]['source'] == 'Frida Kahlo'
    remaining = [f for f in fixed_report['findings'] if not f['fixed']]
    dangling = [f for f in remaining if f['category'] == 'dangling_edge']
    assert len(dangling) == 0


# --- Field alignment ---

def test_field_alignment_detected():
    from verify_corpus import verify
    schema = load_test_schema()
    corpus = _minimal_corpus(nodes=[_goal_node()])
    report = verify(corpus, schema)
    alignment = [f for f in report['findings'] if f['category'] == 'field_alignment']
    assert len(alignment) >= 1
    assert alignment[0]['severity'] == 'CRITICAL'


def test_field_alignment_fix():
    from verify_corpus import verify, apply_fixes
    schema = load_test_schema()
    goal = _goal_node()
    corpus = _minimal_corpus(nodes=[goal])
    report = verify(corpus, schema)
    fixed_corpus, _ = apply_fixes(corpus, report, schema)
    fixed_goal = fixed_corpus['nodes'][0]
    assert 'tier' in fixed_goal
    assert 'goal_tier' not in fixed_goal


# --- Vocabulary validation ---

def test_valid_vocabulary_passes():
    from verify_corpus import verify
    schema = load_test_schema()
    corpus = _minimal_corpus(nodes=[_goal_node(content_domain='health')])
    report = verify(corpus, schema)
    vocab = [f for f in report['findings'] if f['category'] == 'vocabulary_violation']
    assert len(vocab) == 0


def test_invalid_vocabulary_detected():
    from verify_corpus import verify
    schema = load_test_schema()
    corpus = _minimal_corpus(nodes=[_goal_node(content_domain='invalid-domain')])
    report = verify(corpus, schema)
    vocab = [f for f in report['findings'] if f['category'] == 'vocabulary_violation']
    assert len(vocab) >= 1
    assert vocab[0]['severity'] == 'WARNING'


# --- Range validation ---

def test_pad_in_range_passes():
    from verify_corpus import verify
    schema = load_test_schema()
    goal = _goal_node(pad={'pleasure': 0.5, 'arousal': -0.3, 'dominance': 0.7})
    corpus = _minimal_corpus(nodes=[goal])
    report = verify(corpus, schema)
    range_v = [f for f in report['findings'] if f['category'] == 'range_violation']
    assert len(range_v) == 0


def test_pad_out_of_range_detected():
    from verify_corpus import verify
    schema = load_test_schema()
    goal = _goal_node(pad={'pleasure': 1.5, 'arousal': -0.3, 'dominance': 0.7})
    corpus = _minimal_corpus(nodes=[goal])
    report = verify(corpus, schema)
    range_v = [f for f in report['findings'] if f['category'] == 'range_violation']
    assert len(range_v) >= 1
    assert range_v[0]['severity'] == 'WARNING'


def test_range_clamping_fix():
    from verify_corpus import verify, apply_fixes
    schema = load_test_schema()
    goal = _goal_node(pad={'pleasure': 1.5, 'arousal': -2.0, 'dominance': 0.7})
    corpus = _minimal_corpus(nodes=[goal])
    report = verify(corpus, schema)
    fixed_corpus, _ = apply_fixes(corpus, report, schema)
    pad = fixed_corpus['nodes'][0]['pad']
    assert pad['pleasure'] == 1.0
    assert pad['arousal'] == -1.0
    assert pad['dominance'] == 0.7


# --- Subject alignment ---

def test_subject_alignment_fixable():
    from verify_corpus import verify
    schema = load_test_schema()
    corpus = _minimal_corpus(
        nodes=[_person_node('Frida Kahlo')],
        memories=[_memory(subject='Frida')],
    )
    report = verify(corpus, schema)
    subj = [f for f in report['findings'] if f['category'] == 'subject_alignment']
    assert len(subj) >= 1
    assert subj[0]['severity'] == 'FIXABLE'


def test_subject_alignment_fix():
    from verify_corpus import verify, apply_fixes
    schema = load_test_schema()
    corpus = _minimal_corpus(
        nodes=[_person_node('Frida Kahlo')],
        memories=[_memory(subject='Frida')],
    )
    report = verify(corpus, schema)
    fixed_corpus, _ = apply_fixes(corpus, report, schema)
    assert fixed_corpus['memories'][0]['subject'] == 'Frida Kahlo'


# --- Volume anomaly ---

def test_volume_anomaly_detected():
    from verify_corpus import verify
    schema = load_test_schema()
    goals = [_goal_node(name=f'Goal {i}') for i in range(70)]
    corpus = _minimal_corpus(nodes=goals)
    report = verify(corpus, schema)
    vol = [f for f in report['findings'] if f['category'] == 'volume_anomaly']
    assert len(vol) >= 1
    assert vol[0]['severity'] == 'INFO'


# --- Enrichment gap ---

def test_enrichment_gap_detected():
    from verify_corpus import verify
    schema = load_test_schema()
    memories = [_memory(text=f'Memory {i}') for i in range(10)]
    corpus = _minimal_corpus(nodes=[_person_node()], memories=memories)
    report = verify(corpus, schema)
    gaps = [f for f in report['findings'] if f['category'] == 'enrichment_gap']
    assert len(gaps) >= 1


# --- Report format ---

def test_report_has_required_fields():
    from verify_corpus import verify
    schema = load_test_schema()
    corpus = _minimal_corpus()
    report = verify(corpus, schema)
    assert report['format'] == 'import-readiness-report/v1'
    assert 'summary' in report
    assert 'findings' in report
    assert 'checks_passed' in report
    summary = report['summary']
    for key in ('total_findings', 'critical', 'fixable', 'warning', 'info', 'gate'):
        assert key in summary


# --- Exit codes ---

def test_exit_code_pass():
    from verify_corpus import compute_exit_code
    report = {'summary': {'critical': 0, 'warning': 0, 'fixable': 0, 'info': 2}}
    assert compute_exit_code(report) == 0


def test_exit_code_critical():
    from verify_corpus import compute_exit_code
    report = {'summary': {'critical': 1, 'warning': 0, 'fixable': 0, 'info': 0}}
    assert compute_exit_code(report) == 1


def test_exit_code_warning():
    from verify_corpus import compute_exit_code
    report = {'summary': {'critical': 0, 'warning': 3, 'fixable': 0, 'info': 0}}
    assert compute_exit_code(report) == 2


# --- Fix idempotency ---

def test_fix_idempotent():
    from verify_corpus import verify, apply_fixes
    schema = load_test_schema()
    corpus = _minimal_corpus(
        nodes=[_person_node('Frida Kahlo'), _goal_node(pad={'pleasure': 1.5})],
        edges=[_edge('Frida', 'Frida Kahlo')],
        memories=[_memory(subject='Frida')],
    )
    report1 = verify(corpus, schema)
    fixed1, _ = apply_fixes(corpus, report1, schema)
    report2 = verify(fixed1, schema)
    fixed2, _ = apply_fixes(fixed1, report2, schema)
    assert fixed1 == fixed2


# --- Edge type validation ---

def test_unknown_edge_type_detected():
    from verify_corpus import verify
    schema = load_test_schema()
    corpus = _minimal_corpus(
        nodes=[_person_node(), _place_node()],
        edges=[_edge('Frida Kahlo', 'La Casa Azul', 'invented-edge-type')],
    )
    report = verify(corpus, schema)
    unknown = [f for f in report['findings'] if f['category'] == 'edge_type_unknown']
    assert len(unknown) >= 1


# --- Helper ---

def load_test_schema():
    from verify_corpus import load_schema
    return load_schema(SCHEMA_PATH)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/mdproctor/claude/casehub/slots/211/neocortex && python3 -m pytest extraction/tests/test_verify_corpus.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'verify_corpus'`

- [ ] **Step 3: Write verify_corpus.py implementation**

`extraction/scripts/verify_corpus.py`:

```python
"""Import readiness verification for cognitive corpus output.

Validates corpus.json against the Java-side import contract declared in
verify_schema.yaml. Diagnoses issues, attributes them to pipeline stages,
and optionally applies safe fixes.

Usage:
  verify_corpus.py <corpus.json> [--schema <path>] [--fix] [--output <dir>]
"""

import argparse
import copy
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone

import yaml

from pipeline_state import atomic_write


def load_schema(path):
    with open(path) as f:
        return yaml.safe_load(f)


def _resolve_nested(obj, dotted_key):
    """Resolve a dotted key path like 'pad.pleasure' against a dict."""
    parts = dotted_key.split('.')
    current = obj
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set_nested(obj, dotted_key, value):
    """Set a value at a dotted key path, creating intermediate dicts."""
    parts = dotted_key.split('.')
    current = obj
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def _classify_node(node, schema):
    """Determine which entity type config applies to a node."""
    sg = (node.get('subgraph_type') or '').upper()
    for type_name, type_cfg in schema.get('entity_types', {}).items():
        cfg_sg = (type_cfg.get('subgraph_type') or '').upper()
        if cfg_sg and cfg_sg == sg:
            return type_name, type_cfg
    # Fallback: nodes without subgraph_type may be life_events, current_state
    if node.get('goal_tier') or node.get('tier'):
        return 'goal', schema['entity_types'].get('goal', {})
    return None, {}


def verify(corpus, schema):
    """Run all verification checks. Returns a report dict."""
    findings = []
    checks_passed = []
    finding_counter = [0]

    def add_finding(category, severity, source_stage, fix_level, fix_description,
                    count=1, details=None):
        finding_counter[0] += 1
        findings.append({
            'id': f'F{finding_counter[0]:03d}',
            'category': category,
            'severity': severity,
            'source_stage': source_stage,
            'fix_level': fix_level,
            'fix_description': fix_description,
            'count': count,
            'details': details or {},
            'fixed': False,
        })

    nodes = corpus.get('nodes', [])
    edges = corpus.get('edges', [])
    memories = corpus.get('memories', [])
    node_names = {n['name'] for n in nodes if n.get('name')}
    aliases = schema.get('entity_aliases', {})

    # --- Dangling edges ---
    dangling_by_alias = Counter()
    dangling_unresolvable = Counter()
    for edge in edges:
        src, tgt = edge.get('source', ''), edge.get('target', '')
        for ref in (src, tgt):
            if ref and ref not in node_names:
                if ref in aliases and aliases[ref] in node_names:
                    dangling_by_alias[ref] += 1
                else:
                    dangling_unresolvable[ref] += 1

    for alias, count in dangling_by_alias.items():
        canonical = aliases[alias]
        affected_types = Counter()
        for e in edges:
            if e.get('source') == alias or e.get('target') == alias:
                affected_types[e.get('type', 'unknown')] += 1
        add_finding(
            'dangling_edge', 'FIXABLE', 'extraction', 'post_processing',
            f"Resolve alias: '{alias}' → '{canonical}'",
            count=count,
            details={'alias': alias, 'canonical': canonical,
                     'affected_edges': count,
                     'edge_types': list(affected_types.keys())},
        )

    for ref, count in dangling_unresolvable.items():
        add_finding(
            'dangling_edge', 'CRITICAL', 'extraction', 'extraction',
            f"Edge references unknown entity: '{ref}'",
            count=count,
            details={'reference': ref, 'affected_edges': count},
        )

    total_dangling = sum(dangling_by_alias.values()) + sum(dangling_unresolvable.values())
    dangling_cfg = schema.get('edges', {}).get('dangling', {})
    if edges:
        dangling_pct = total_dangling / len(edges) * 100
    else:
        dangling_pct = 0
    if dangling_pct <= dangling_cfg.get('warn_pct', 2) and total_dangling == 0:
        checks_passed.append('dangling_edges')

    # --- Field alignment ---
    for type_name, type_cfg in schema.get('entity_types', {}).items():
        mappings = type_cfg.get('field_mappings', {})
        if not mappings:
            continue
        cfg_sg = (type_cfg.get('subgraph_type') or '').upper()
        typed_nodes = [n for n in nodes
                       if (n.get('subgraph_type') or '').upper() == cfg_sg]
        for corpus_field, java_field in mappings.items():
            affected = [n for n in typed_nodes if corpus_field in n]
            if affected:
                add_finding(
                    'field_alignment', 'CRITICAL', 'assembly', 'assembler',
                    f"Rename '{corpus_field}' → '{java_field}' "
                    f"(Java @JsonProperty expects unprefixed)",
                    count=len(affected),
                    details={'corpus_field': corpus_field, 'java_field': java_field,
                             'entity_type': type_name, 'affected_nodes': len(affected)},
                )
        if not any(corpus_field in n for n in typed_nodes
                   for corpus_field in mappings):
            checks_passed.append(f'field_alignment_{type_name}')

    # --- Vocabulary validation ---
    for type_name, type_cfg in schema.get('entity_types', {}).items():
        vocabs = type_cfg.get('vocabularies', {})
        if not vocabs:
            continue
        cfg_sg = (type_cfg.get('subgraph_type') or '').upper()
        typed_nodes = [n for n in nodes
                       if (n.get('subgraph_type') or '').upper() == cfg_sg]
        for field_name, vocab_cfg in vocabs.items():
            valid_values = set(vocab_cfg.get('values', []))
            violations = []
            for n in typed_nodes:
                val = n.get(field_name)
                if val and val not in valid_values:
                    violations.append({'node': n.get('name'), 'value': val})
            if violations:
                add_finding(
                    'vocabulary_violation', 'WARNING', 'extraction', 'assembler',
                    f"Invalid {field_name} values not in "
                    f"{vocab_cfg.get('source', 'canonical set')}",
                    count=len(violations),
                    details={'field': field_name, 'violations': violations[:20],
                             'valid_values': sorted(valid_values)},
                )
            else:
                checks_passed.append(f'vocabulary_{field_name}')

    # --- Range validation ---
    for type_name, type_cfg in schema.get('entity_types', {}).items():
        ranges = type_cfg.get('ranges', {})
        if not ranges:
            continue
        cfg_sg = (type_cfg.get('subgraph_type') or '').upper()
        if cfg_sg:
            typed_nodes = [n for n in nodes
                           if (n.get('subgraph_type') or '').upper() == cfg_sg]
        else:
            typed_nodes = nodes
        for dotted_key, (lo, hi) in ranges.items():
            violations = []
            for n in typed_nodes:
                val = _resolve_nested(n, dotted_key)
                if val is not None and isinstance(val, (int, float)):
                    if val < lo or val > hi:
                        violations.append({
                            'node': n.get('name', n.get('description', '?')),
                            'field': dotted_key, 'value': val,
                            'range': [lo, hi],
                        })
            if violations:
                add_finding(
                    'range_violation', 'WARNING', 'enrichment', 'post_processing',
                    f"{dotted_key} values outside [{lo}, {hi}]",
                    count=len(violations),
                    details={'field': dotted_key, 'range': [lo, hi],
                             'violations': violations[:20]},
                )

    # --- Missing required fields ---
    for type_name, type_cfg in schema.get('entity_types', {}).items():
        required = type_cfg.get('required_fields', [])
        if not required:
            continue
        cfg_sg = (type_cfg.get('subgraph_type') or '').upper()
        if cfg_sg:
            typed_nodes = [n for n in nodes
                           if (n.get('subgraph_type') or '').upper() == cfg_sg]
        else:
            typed_nodes = nodes
        for field in required:
            missing = [n for n in typed_nodes if not n.get(field)]
            if missing:
                add_finding(
                    'missing_required', 'CRITICAL', 'extraction', 'extraction',
                    f"Required field '{field}' missing on {type_name} nodes",
                    count=len(missing),
                    details={'field': field, 'entity_type': type_name,
                             'missing_nodes': [n.get('name', '?') for n in missing[:20]]},
                )

    # --- Volume anomaly ---
    for type_name, type_cfg in schema.get('entity_types', {}).items():
        vol = type_cfg.get('volume', {})
        if not vol:
            continue
        cfg_sg = (type_cfg.get('subgraph_type') or '').upper()
        typed_nodes = [n for n in nodes
                       if (n.get('subgraph_type') or '').upper() == cfg_sg]
        warn_above = vol.get('warn_above', float('inf'))
        if len(typed_nodes) > warn_above:
            add_finding(
                'volume_anomaly', 'INFO', 'extraction', 'extraction',
                f"{len(typed_nodes)} {type_name} nodes (warn threshold: {warn_above})",
                count=len(typed_nodes),
                details={'entity_type': type_name, 'count': len(typed_nodes),
                         'threshold': warn_above},
            )

    # --- Subject alignment ---
    subject_aliases = Counter()
    subject_unknown = Counter()
    for m in memories:
        subj = m.get('subject', '')
        if subj and subj not in node_names:
            if subj in aliases and aliases[subj] in node_names:
                subject_aliases[subj] += 1
            else:
                subject_unknown[subj] += 1

    for alias, count in subject_aliases.items():
        canonical = aliases[alias]
        add_finding(
            'subject_alignment', 'FIXABLE', 'extraction', 'post_processing',
            f"Memory subject '{alias}' → '{canonical}'",
            count=count,
            details={'alias': alias, 'canonical': canonical,
                     'affected_memories': count},
        )

    for subj, count in subject_unknown.items():
        add_finding(
            'subject_alignment', 'WARNING', 'extraction', 'extraction',
            f"Memory subject '{subj}' not found in nodes",
            count=count,
            details={'subject': subj, 'affected_memories': count},
        )

    if not subject_aliases and not subject_unknown:
        checks_passed.append('subject_alignment')

    # --- Enrichment gap ---
    enrich_cfg = schema.get('memories', {})
    enrich_fields = enrich_cfg.get('enrichment_fields', [])
    enrich_threshold = enrich_cfg.get('enrichment_threshold', 80)
    experience_memories = [m for m in memories if m.get('domain') == 'experience']
    if experience_memories:
        enriched_count = sum(
            1 for m in experience_memories
            if any(m.get(f) for f in enrich_fields)
        )
        enrich_pct = enriched_count / len(experience_memories) * 100
        if enrich_pct < enrich_threshold:
            missing_count = len(experience_memories) - enriched_count
            add_finding(
                'enrichment_gap', 'INFO', 'enrichment', 'enrichment',
                f"{missing_count} experience memories missing cognitive enrichment "
                f"({enrich_pct:.0f}% < {enrich_threshold}% threshold)",
                count=missing_count,
                details={'enriched': enriched_count,
                         'total': len(experience_memories),
                         'pct': round(enrich_pct, 1),
                         'threshold': enrich_threshold},
            )
        else:
            checks_passed.append('enrichment_coverage')

    # --- Edge type validation ---
    valid_types = set(schema.get('edges', {}).get('valid_types', []))
    if valid_types:
        unknown_types = Counter()
        for e in edges:
            et = e.get('type', '')
            if et and et not in valid_types:
                unknown_types[et] += 1
        for et, count in unknown_types.items():
            add_finding(
                'edge_type_unknown', 'WARNING', 'extraction', 'extraction',
                f"Unknown edge type: '{et}'",
                count=count,
                details={'edge_type': et, 'occurrences': count},
            )
        if not unknown_types:
            checks_passed.append('edge_type_validity')

    # --- Sub-thought type validation ---
    for type_name, type_cfg in schema.get('entity_types', {}).items():
        valid_st = type_cfg.get('sub_thought_types')
        if not valid_st:
            continue
        valid_st_set = set(valid_st)
        for m in memories:
            for st in m.get('sub_thoughts', []) or []:
                st_type = st.get('type', '') if isinstance(st, dict) else ''
                if st_type and st_type not in valid_st_set:
                    add_finding(
                        'sub_thought_type', 'WARNING', 'enrichment', 'enrichment',
                        f"Invalid sub-thought type: '{st_type}'",
                        count=1,
                        details={'type': st_type, 'valid_types': sorted(valid_st_set)},
                    )

    # --- Memory domain validation ---
    valid_domains = set(schema.get('memories', {}).get('valid_domains', []))
    if valid_domains:
        invalid_domains = Counter()
        for m in memories:
            d = m.get('domain', '')
            if d and d not in valid_domains:
                invalid_domains[d] += 1
        if not invalid_domains:
            checks_passed.append('memory_domain_validity')

    # --- Build summary ---
    counts = Counter(f['severity'] for f in findings)
    summary = {
        'total_findings': len(findings),
        'critical': counts.get('CRITICAL', 0),
        'fixable': counts.get('FIXABLE', 0),
        'warning': counts.get('WARNING', 0),
        'info': counts.get('INFO', 0),
        'gate': 'FAIL' if counts.get('CRITICAL', 0) > 0 or counts.get('FIXABLE', 0) > 0
                else ('WARN' if counts.get('WARNING', 0) > 0 else 'PASS'),
    }

    return {
        'format': 'import-readiness-report/v1',
        'corpus': corpus.get('format', ''),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'summary': summary,
        'findings': findings,
        'checks_passed': sorted(set(checks_passed)),
    }


def apply_fixes(corpus, report, schema):
    """Apply safe fixes to a corpus based on a verification report.

    Returns (fixed_corpus, updated_report).
    """
    fixed = copy.deepcopy(corpus)
    updated_findings = copy.deepcopy(report['findings'])
    aliases = schema.get('entity_aliases', {})
    node_names = {n['name'] for n in fixed.get('nodes', []) if n.get('name')}

    for finding in updated_findings:
        if finding['fixed']:
            continue

        if finding['category'] == 'dangling_edge' and finding['severity'] == 'FIXABLE':
            alias = finding['details'].get('alias', '')
            canonical = finding['details'].get('canonical', '')
            if alias and canonical:
                for edge in fixed['edges']:
                    if edge.get('source') == alias:
                        edge['source'] = canonical
                    if edge.get('target') == alias:
                        edge['target'] = canonical
                finding['fixed'] = True

        elif finding['category'] == 'field_alignment':
            corpus_field = finding['details'].get('corpus_field', '')
            java_field = finding['details'].get('java_field', '')
            entity_type = finding['details'].get('entity_type', '')
            type_cfg = schema.get('entity_types', {}).get(entity_type, {})
            cfg_sg = (type_cfg.get('subgraph_type') or '').upper()
            for node in fixed['nodes']:
                if (node.get('subgraph_type') or '').upper() == cfg_sg:
                    if corpus_field in node:
                        node[java_field] = node.pop(corpus_field)
            finding['fixed'] = True

        elif finding['category'] == 'range_violation':
            lo, hi = finding['details'].get('range', [-1, 1])
            dotted_key = finding['details'].get('field', '')
            for node in fixed['nodes']:
                val = _resolve_nested(node, dotted_key)
                if val is not None and isinstance(val, (int, float)):
                    if val < lo or val > hi:
                        _set_nested(node, dotted_key, max(lo, min(hi, val)))
            finding['fixed'] = True

        elif finding['category'] == 'subject_alignment' and finding['severity'] == 'FIXABLE':
            alias = finding['details'].get('alias', '')
            canonical = finding['details'].get('canonical', '')
            if alias and canonical:
                for mem in fixed['memories']:
                    if mem.get('subject') == alias:
                        mem['subject'] = canonical
                finding['fixed'] = True

    # Rebuild summary with remaining unfixed
    unfixed = [f for f in updated_findings if not f['fixed']]
    counts = Counter(f['severity'] for f in unfixed)
    updated_report = copy.deepcopy(report)
    updated_report['findings'] = updated_findings
    updated_report['summary'] = {
        'total_findings': len(updated_findings),
        'critical': counts.get('CRITICAL', 0),
        'fixable': counts.get('FIXABLE', 0),
        'warning': counts.get('WARNING', 0),
        'info': counts.get('INFO', 0),
        'gate': 'FAIL' if counts.get('CRITICAL', 0) > 0 or counts.get('FIXABLE', 0) > 0
                else ('WARN' if counts.get('WARNING', 0) > 0 else 'PASS'),
    }

    return fixed, updated_report


def compute_exit_code(report):
    """Compute exit code from a report. 0=pass, 1=critical, 2=warning."""
    s = report['summary']
    if s.get('critical', 0) > 0 or s.get('fixable', 0) > 0:
        return 1
    if s.get('warning', 0) > 0:
        return 2
    return 0


def format_text_report(report):
    """Format a human-readable text report."""
    lines = []
    s = report['summary']
    gate_icon = {'PASS': '✅', 'WARN': '⚠️', 'FAIL': '❌'}.get(s['gate'], '?')
    lines.append(f"Import Readiness: {gate_icon} {s['gate']}")
    lines.append(f"  Findings: {s['total_findings']} "
                 f"(critical={s['critical']}, fixable={s['fixable']}, "
                 f"warning={s['warning']}, info={s['info']})")
    lines.append('')

    for f in report['findings']:
        fixed_tag = ' [FIXED]' if f.get('fixed') else ''
        lines.append(f"  [{f['severity']}] {f['category']}: "
                     f"{f['fix_description']} (×{f['count']}){fixed_tag}")
        lines.append(f"    Source: {f['source_stage']} → Fix: {f['fix_level']}")

    if report.get('checks_passed'):
        lines.append('')
        lines.append(f"  Checks passed: {', '.join(report['checks_passed'])}")

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Verify corpus.json import readiness against Java-side contract')
    parser.add_argument('corpus', help='Path to corpus.json')
    parser.add_argument('--schema', '-s', default=None,
                        help='Path to verify_schema.yaml (default: docs/verify_schema.yaml)')
    parser.add_argument('--fix', action='store_true',
                        help='Apply safe fixes and write corpus-verified.json')
    parser.add_argument('--output', '-o', default=None,
                        help='Output directory (default: same as corpus)')
    args = parser.parse_args()

    schema_path = args.schema or os.path.join(
        os.path.dirname(__file__), '..', 'docs', 'verify_schema.yaml')
    output_dir = args.output or os.path.dirname(args.corpus) or '.'

    schema = load_schema(schema_path)
    with open(args.corpus) as f:
        corpus = json.load(f)

    report = verify(corpus, schema)

    if args.fix:
        fixed_corpus, report = apply_fixes(corpus, report, schema)
        verified_path = os.path.join(output_dir, 'corpus-verified.json')
        atomic_write(verified_path, fixed_corpus)
        print(f"Fixed corpus: {verified_path}")

    report_path = os.path.join(output_dir, 'verification-report.json')
    atomic_write(report_path, report)

    text_report = format_text_report(report)
    text_path = os.path.join(output_dir, 'verification-report.txt')
    with open(text_path, 'w') as f:
        f.write(text_report)

    print(text_report)
    print(f"\nReport: {report_path}")

    sys.exit(compute_exit_code(report))


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/mdproctor/claude/casehub/slots/211/neocortex && python3 -m pytest extraction/tests/test_verify_corpus.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run against real corpus**

Run: `cd /Users/mdproctor/claude/casehub/slots/211/neocortex && python3 extraction/scripts/verify_corpus.py extraction/output/corpus.json --output /tmp/verify-test`

Expected: Report showing dangling edges, field alignment issues, etc. Exit code 1 (CRITICAL findings).

- [ ] **Step 6: Test fix mode against real corpus**

Run: `cd /Users/mdproctor/claude/casehub/slots/211/neocortex && python3 extraction/scripts/verify_corpus.py extraction/output/corpus.json --fix --output /tmp/verify-test`

Expected: `corpus-verified.json` written with aliases resolved and fields renamed. Re-verify to confirm fixes applied.

- [ ] **Step 7: Commit**

```bash
git add extraction/scripts/verify_corpus.py extraction/tests/test_verify_corpus.py
git commit -m "feat(#550): add verify_corpus.py — import readiness verification

Schema-driven verification of corpus.json against the Java-side import
contract. Diagnoses dangling edges, field alignment, vocabulary violations,
range violations, subject alignment, enrichment gaps, and volume anomalies.
--fix mode applies safe fixes (alias resolution, field rename, range clamp).

Refs #550"
```

## Batch 2: Pipeline Integration

### Task 3: Integrate verify step into run_pipeline.sh

**Files:**
- Modify: `extraction/scripts/run_pipeline.sh` (after line ~267, add Step 8)

**Interfaces:**
- Consumes: `corpus.json` (produced by Step 7 assemble_corpus.py)
- Produces: `verification-report.json`, `verification-report.txt` in output dir

- [ ] **Step 1: Add Step 8 to run_pipeline.sh**

After the existing Step 7 (assemble corpus) block at line ~267, add:

```bash
echo "--- Step 8: Verify Import Readiness ---"
$VENV "$SCRIPT_DIR/verify_corpus.py" "$OUTDIR/corpus.json" \
    --schema "$SCRIPT_DIR/../docs/verify_schema.yaml" \
    --output "$OUTDIR"
VERIFY_EXIT=$?
if [ $VERIFY_EXIT -eq 1 ]; then
    echo ""
    echo "CRITICAL: Import readiness gate failed."
    echo "Run with --fix to attempt auto-repair:"
    echo "  python3 scripts/verify_corpus.py $OUTDIR/corpus.json --fix --output $OUTDIR"
fi
```

Note: Do NOT `exit 1` — the pipeline should report but not block, since the
user may want to inspect the report first and then run `--fix` manually.

- [ ] **Step 2: Verify pipeline runs end-to-end**

Run the pipeline on a small test (if available) or verify `run_pipeline.sh`
parses correctly:

Run: `bash -n /Users/mdproctor/claude/casehub/slots/211/neocortex/extraction/scripts/run_pipeline.sh`
Expected: No syntax errors

- [ ] **Step 3: Commit**

```bash
git add extraction/scripts/run_pipeline.sh
git commit -m "feat(#550): integrate verify_corpus.py as Step 8 in pipeline

Runs import readiness verification after corpus assembly. Reports
findings but does not block — user reviews and runs --fix manually.

Closes #550"
```

## References

- [2026-10-11-import-readiness-verification-design.md] — design spec this plan implements
- `extraction/scripts/assemble_corpus.py` — CLI pattern reference, upstream step
- `extraction/scripts/pipeline_state.py` — atomic_write utility
- `extraction/scripts/coverage.py` — existing coverage gate library
- `extraction/tests/conftest.py` — sys.path setup for test imports
- `extraction/tests/test_coverage.py` — test pattern reference
- `extraction/scripts/run_pipeline.sh:262-267` — insertion point for Step 8
- `mindmap-api/.../GoalVocabulary.java` — canonical vocabulary sets
- `memory-seeding/.../GoalEntry.java` — field mapping reference
- GitHub #550 — focal issue
- GitHub #538 — extraction pipeline epic
