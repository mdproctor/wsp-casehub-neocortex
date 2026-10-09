# Pipeline Convergence Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #525 — pipeline convergence loop
**Issue group:** #468, #522, #523, #524, #525

**Goal:** Refactor the cognitive extraction pipeline from a linear sequence into a fixed-point convergence loop where every generated text goes through the full inference chain, with idempotent restarts.

**Architecture:** The pipeline wraps its extract → enrich → synthesize steps in a convergence loop. A `PipelineManifest` tracks pass/step/item state for crash recovery. Each script writes incrementally and skips already-processed items via markers on the data. Confidence ceilings decay per pass to prevent circular amplification.

**Tech Stack:** Python 3, anthropic SDK (via existing `llm_client.py`), pytest

## Global Constraints

- All files in `blocks-ui/examples/cognitive-workbench/scripts/`
- Python scripts — no Java, no Maven, no Quarkus
- Tests run with: `python3 -m pytest <test_file> -v` (from the scripts directory)
- LLM calls use existing `llm_client.py` (create_client, model_id)
- Atomic writes via `os.replace()` (write to `.tmp`, rename)
- IntelliJ MCP unavailable — use bash for file operations (Python scripts, not Java source)

---

## Batch 1: Pipeline State Infrastructure

### Task 1: `pipeline_state.py` — manifest and confidence utilities

**Files:**
- Create: `blocks-ui/examples/cognitive-workbench/scripts/pipeline_state.py`
- Create: `blocks-ui/examples/cognitive-workbench/scripts/test_pipeline_state.py`

**Interfaces:**
- Produces: `PipelineManifest` class (init, start_pass, update_step, complete_step, complete_pass, mark_converged, current_pass, current_step, is_step_complete, save), `confidence_ceiling(pass_n)`, `clamp_confidence(confidence, pass_n)`, `atomic_write(path, data)`

- [ ] **Step 1: Write failing tests for confidence utilities**

```python
# test_pipeline_state.py
import json
import os
import tempfile
import pytest

from pipeline_state import confidence_ceiling, clamp_confidence, atomic_write, PipelineManifest


class TestConfidenceCeiling:
    def test_pass_1_is_1_0(self):
        assert confidence_ceiling(1) == 1.0

    def test_pass_2_is_0_8(self):
        assert confidence_ceiling(2) == 0.8

    def test_pass_3_is_0_6(self):
        assert confidence_ceiling(3) == 0.6

    def test_pass_4_is_0_4(self):
        assert confidence_ceiling(4) == 0.4

    def test_pass_5_is_0_4(self):
        assert confidence_ceiling(5) == 0.4

    def test_pass_100_is_0_4(self):
        assert confidence_ceiling(100) == 0.4


class TestClampConfidence:
    def test_pass_1_no_clamp(self):
        conf = {'origin': 'STATED', 'value': 0.9}
        result = clamp_confidence(conf, 1)
        assert result['value'] == 0.9
        assert result['origin'] == 'STATED'

    def test_pass_2_clamps_to_0_8(self):
        conf = {'origin': 'INFERRED', 'value': 0.95}
        result = clamp_confidence(conf, 2)
        assert result['value'] == 0.8

    def test_pass_2_no_clamp_when_below(self):
        conf = {'origin': 'INFERRED', 'value': 0.5}
        result = clamp_confidence(conf, 2)
        assert result['value'] == 0.5

    def test_missing_value_defaults_to_1(self):
        conf = {'origin': 'INFERRED'}
        result = clamp_confidence(conf, 3)
        assert result['value'] == 0.6

    def test_does_not_mutate_input(self):
        conf = {'origin': 'STATED', 'value': 0.95}
        clamp_confidence(conf, 2)
        assert conf['value'] == 0.95
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest test_pipeline_state.py::TestConfidenceCeiling -v && python3 -m pytest test_pipeline_state.py::TestClampConfidence -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement confidence utilities**

```python
# pipeline_state.py
"""Pipeline convergence state — manifest tracking, confidence ceilings, atomic I/O."""

import json
import os
import tempfile

_CEILINGS = [1.0, 0.8, 0.6, 0.4]


def confidence_ceiling(pass_n: int) -> float:
    return _CEILINGS[min(pass_n - 1, len(_CEILINGS) - 1)]


def clamp_confidence(confidence: dict, pass_n: int) -> dict:
    ceiling = confidence_ceiling(pass_n)
    return {**confidence, 'value': min(confidence.get('value', 1.0), ceiling)}


def atomic_write(path: str, data: dict):
    dir_name = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=dir_name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

- [ ] **Step 4: Run confidence tests to verify they pass**

Run: `python3 -m pytest test_pipeline_state.py::TestConfidenceCeiling test_pipeline_state.py::TestClampConfidence -v`
Expected: PASS (all 11 tests)

- [ ] **Step 5: Write failing tests for atomic_write**

```python
class TestAtomicWrite:
    def test_writes_json(self, tmp_path):
        path = str(tmp_path / 'test.json')
        atomic_write(path, {'key': 'value'})
        with open(path) as f:
            assert json.load(f) == {'key': 'value'}

    def test_no_tmp_file_left(self, tmp_path):
        path = str(tmp_path / 'test.json')
        atomic_write(path, {'key': 'value'})
        files = os.listdir(tmp_path)
        assert files == ['test.json']

    def test_overwrites_existing(self, tmp_path):
        path = str(tmp_path / 'test.json')
        atomic_write(path, {'v': 1})
        atomic_write(path, {'v': 2})
        with open(path) as f:
            assert json.load(f)['v'] == 2
```

- [ ] **Step 6: Run atomic_write tests — expect PASS**

Run: `python3 -m pytest test_pipeline_state.py::TestAtomicWrite -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Write failing tests for PipelineManifest**

```python
class TestPipelineManifest:
    def test_new_manifest_has_no_passes(self, tmp_path):
        m = PipelineManifest(str(tmp_path / 'manifest.json'))
        assert m.current_pass() == 0
        assert m.data['passes'] == []

    def test_start_pass_creates_entry(self, tmp_path):
        m = PipelineManifest(str(tmp_path / 'manifest.json'))
        m.start_pass(1)
        assert m.current_pass() == 1
        assert m.data['passes'][0]['status'] == 'in_progress'

    def test_complete_step_records(self, tmp_path):
        m = PipelineManifest(str(tmp_path / 'manifest.json'))
        m.start_pass(1)
        m.complete_step('chunk')
        assert m.is_step_complete('chunk')
        assert not m.is_step_complete('nlp_extract')

    def test_update_step_progress(self, tmp_path):
        m = PipelineManifest(str(tmp_path / 'manifest.json'))
        m.start_pass(1)
        m.update_step('extract_structure', 5, 30)
        assert m.current_step() == 'extract_structure'
        p = m.data['passes'][0]
        assert p['items_done'] == 5
        assert p['items_total'] == 30

    def test_complete_pass(self, tmp_path):
        m = PipelineManifest(str(tmp_path / 'manifest.json'))
        m.start_pass(1)
        m.complete_pass(new_memories=23, new_entities=3, new_edges=5)
        p = m.data['passes'][0]
        assert p['status'] == 'complete'
        assert p['new_memories'] == 23

    def test_mark_converged(self, tmp_path):
        m = PipelineManifest(str(tmp_path / 'manifest.json'))
        m.start_pass(1)
        m.complete_pass(0, 0, 0)
        m.mark_converged()
        assert m.data['converged'] is True

    def test_save_and_reload(self, tmp_path):
        path = str(tmp_path / 'manifest.json')
        m = PipelineManifest(path)
        m.start_pass(1)
        m.complete_step('chunk')
        m.save()
        m2 = PipelineManifest(path)
        assert m2.current_pass() == 1
        assert m2.is_step_complete('chunk')

    def test_mode_and_max_passes(self, tmp_path):
        m = PipelineManifest(str(tmp_path / 'manifest.json'),
                             mode='selective', max_passes=3)
        assert m.data['mode'] == 'selective'
        assert m.data['max_passes'] == 3
```

- [ ] **Step 8: Implement PipelineManifest**

```python
class PipelineManifest:
    def __init__(self, path: str, mode: str = 'fixed-point', max_passes: int = 5):
        self.path = path
        if os.path.exists(path):
            with open(path) as f:
                self.data = json.load(f)
        else:
            self.data = {
                'mode': mode,
                'max_passes': max_passes,
                'passes': [],
                'converged': False,
            }

    def start_pass(self, pass_n: int):
        self.data['passes'].append({
            'pass': pass_n,
            'status': 'in_progress',
            'steps_complete': [],
            'step': None,
            'items_done': 0,
            'items_total': 0,
            'new_memories': 0,
            'new_entities': 0,
            'new_edges': 0,
        })
        self.save()

    def update_step(self, step: str, items_done: int, items_total: int):
        p = self.data['passes'][-1]
        p['step'] = step
        p['items_done'] = items_done
        p['items_total'] = items_total
        self.save()

    def complete_step(self, step: str):
        p = self.data['passes'][-1]
        if step not in p['steps_complete']:
            p['steps_complete'].append(step)
        p['step'] = None
        self.save()

    def complete_pass(self, new_memories: int, new_entities: int, new_edges: int):
        p = self.data['passes'][-1]
        p['status'] = 'complete'
        p['new_memories'] = new_memories
        p['new_entities'] = new_entities
        p['new_edges'] = new_edges
        self.save()

    def mark_converged(self):
        self.data['converged'] = True
        self.save()

    def current_pass(self) -> int:
        if not self.data['passes']:
            return 0
        return self.data['passes'][-1]['pass']

    def current_step(self) -> str | None:
        if not self.data['passes']:
            return None
        return self.data['passes'][-1].get('step')

    def is_step_complete(self, step: str) -> bool:
        if not self.data['passes']:
            return False
        return step in self.data['passes'][-1].get('steps_complete', [])

    def save(self):
        atomic_write(self.path, self.data)
```

- [ ] **Step 9: Run all PipelineManifest tests — expect PASS**

Run: `python3 -m pytest test_pipeline_state.py::TestPipelineManifest -v`
Expected: PASS (8 tests)

- [ ] **Step 10: Run full test suite — expect PASS**

Run: `python3 -m pytest test_pipeline_state.py -v`
Expected: PASS (22 tests)

- [ ] **Step 11: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench/scripts/pipeline_state.py examples/cognitive-workbench/scripts/test_pipeline_state.py
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#525): add pipeline_state.py — manifest tracking + confidence ceilings

Refs #525"
```

## Batch 2: Incremental Writes + Idempotency in Existing Scripts

### Task 2: Add incremental writes and item markers to `enrich_cognitive.py`

This is the simplest script to retrofit because backfill mode already skips enriched items. We add: (a) atomic writes after each item, (b) `--pass` argument for provenance tagging.

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/scripts/enrich_cognitive.py`

**Interfaces:**
- Consumes: `atomic_write` from `pipeline_state.py` (Task 1)
- Produces: enriched.json with `enrichment_source` tagged by pass number when `--pass` is provided

- [ ] **Step 1: Add `--pass` argument to the argument parser**

In `main()`, after the existing `--backfill` argument:

```python
parser.add_argument('--pass-num', type=int, default=1, help='Convergence pass number (for provenance)')
```

- [ ] **Step 2: Import atomic_write and use it in run_normal**

At the top of the file, add:

```python
from pipeline_state import atomic_write
```

In `run_normal()`, after the `apply_enrichment(enriched_memories[global_idx], enrichment)` line and before `time.sleep(0.2)`, add the incremental write. Also tag enrichment_source with pass number. Replace the single final write with incremental writes:

After line `enrichment_count += 1` (inside the inner loop), add:

```python
                    output = {
                        'stats': {
                            'total_memories': len(enriched_memories),
                            'enriched': enrichment_count,
                            'coverage_pct': round(enrichment_count / max(len(enriched_memories), 1) * 100, 1),
                        },
                        'entities': structure.get('entities', []),
                        'edges': structure.get('edges', []),
                        'memories': enriched_memories,
                    }
                    atomic_write(args.output, output)
```

Remove the existing final write block (the `output = {...}` and `with open(args.output, 'w')` block after the loop).

- [ ] **Step 3: Use atomic_write in run_backfill**

In `run_backfill()`, after `enrichment_count += 1` inside the loop, add:

```python
                atomic_write(args.backfill, enriched)
```

If `--pass-num` > 1, tag the enrichment_source:

```python
                mem['enrichment_source'] = f'phase-2a-backfill-pass-{args.pass_num}'
```

Remove the existing final write block after the loop.

- [ ] **Step 4: Verify existing tests still pass**

Run: `python3 -m pytest test_coverage.py -v`
Expected: PASS (all existing tests)

- [ ] **Step 5: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench/scripts/enrich_cognitive.py
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#525): add incremental writes + pass provenance to enrich_cognitive.py

Refs #525"
```

### Task 3: Add incremental writes and `--incremental` mode to `enrich_entity.py`

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/scripts/enrich_entity.py`

**Interfaces:**
- Consumes: `atomic_write`, `clamp_confidence` from `pipeline_state.py` (Task 1)
- Produces: enriched.json with `synthesis_pass` markers on entity_enrichments, new memory count reported to stdout as `NEW_MEMORIES=N`

- [ ] **Step 1: Add `--incremental` and `--pass-num` arguments**

```python
parser.add_argument('--incremental', action='store_true', help='Only re-synthesize entities with new data')
parser.add_argument('--pass-num', type=int, default=1, help='Convergence pass number')
parser.add_argument('--mode', choices=['fixed-point', 'selective'], default='fixed-point', help='Convergence mode')
```

- [ ] **Step 2: Import pipeline_state utilities**

```python
from pipeline_state import atomic_write, clamp_confidence
```

- [ ] **Step 3: Add entity-has-new-data check**

After `identify_central_entities`, add a function:

```python
def has_new_data(entity_name: str, enriched: dict, last_synthesis_pass: int, memories: list) -> bool:
    """Check if entity has new edges or memories since its last synthesis pass."""
    name_lower = entity_name.lower()
    for mem in memories:
        pass_str = mem.get('extraction_pass', 'phase-1-structural')
        if pass_str.startswith('convergence-pass-'):
            mem_pass = int(pass_str.split('-')[-1])
            if mem_pass > last_synthesis_pass:
                conf = mem.get('confidence', {}).get('value', 1.0)
                if conf > 0.4:
                    related = [r.lower() for r in mem.get('related_entities', [])]
                    if name_lower in related or mem.get('subject', '').lower() == name_lower:
                        return True
    return False
```

- [ ] **Step 4: In `main()`, add incremental filtering**

After computing `central`, if `args.incremental`:

```python
    if args.incremental:
        existing = enriched.get('entity_enrichments', {})
        filtered = []
        for name in central:
            prev = existing.get(name, {})
            last_pass = prev.get('synthesis_pass', 0)
            if has_new_data(name, enriched, last_pass, memories):
                filtered.append(name)
        print(f"  Incremental: {len(filtered)}/{len(central)} entities have new data")
        central = filtered
```

- [ ] **Step 5: Add synthesis_pass marker and confidence clamping**

In the entity enrichment loop, after `entity_enrichments[entity_name] = {...}`:

```python
            entity_enrichments[entity_name]['synthesis_pass'] = args.pass_num
```

For reflections and mood snapshots, clamp confidence:

```python
            for ref in result.get('reflections', []):
                if not isinstance(ref, dict):
                    continue
                ref['domain'] = 'reflection'
                ref['subject'] = entity_name
                ref['enrichment_version'] = 'v1.0-phase2b'
                ref['extraction_pass'] = f'convergence-pass-{args.pass_num}' if args.pass_num > 1 else 'phase-2b-entity'
                ref['convergence_pass'] = args.pass_num
                if 'confidence' in ref:
                    ref['confidence'] = clamp_confidence(ref['confidence'], args.pass_num)
                reflections.append(ref)
```

Same pattern for mood_snapshots.

- [ ] **Step 6: Add incremental writes after each entity**

After the `time.sleep(0.3)` inside the entity loop, add:

```python
        enriched['entity_enrichments'] = entity_enrichments
        enriched['phase2b_reflections'] = enriched.get('phase2b_reflections', []) + reflections
        enriched['phase2b_mood_snapshots'] = enriched.get('phase2b_mood_snapshots', []) + mood_snapshots
        if disposition_profile:
            enriched['disposition_profile'] = disposition_profile
        atomic_write(args.enriched, enriched)
```

Adjust the loop to not re-append on each iteration — use local lists that accumulate, then merge once at write time. This requires restructuring the loop slightly: track `new_reflections` and `new_moods` per entity, append to the enriched lists at write time.

- [ ] **Step 7: Report new memory count for convergence metric**

At the end of `main()`:

```python
    new_count = len(reflections) + len(mood_snapshots)
    print(f"NEW_MEMORIES={new_count}")
```

- [ ] **Step 8: Handle selective mode**

When `args.mode == 'selective'`, only reflections count as "new memories" for convergence:

```python
    if args.mode == 'selective':
        new_count = len(reflections)
    else:
        new_count = len(reflections) + len(mood_snapshots)
    print(f"NEW_MEMORIES={new_count}")
```

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench/scripts/enrich_entity.py
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#525): add --incremental mode + confidence clamping to enrich_entity.py

Refs #525"
```

## Batch 3: Convergence Extraction

### Task 4: Add `--convergence` mode to `extract_structure.py`

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/scripts/extract_structure.py`
- Create: `blocks-ui/examples/cognitive-workbench/scripts/test_convergence_extract.py`

**Interfaces:**
- Consumes: `atomic_write`, `clamp_confidence` from `pipeline_state.py` (Task 1)
- Produces: updated structure.json with new entities/edges/memories merged, processed memories stamped with `structurally_extracted: true`

- [ ] **Step 1: Write the convergence extraction prompt**

Add after the existing `MEMORY_SYSTEM` prompt:

```python
CONVERGENCE_SYSTEM = """You are a biographical knowledge graph builder. Given synthesized insights about an entity and the existing graph context, identify NEW content not already captured.

For each piece of new content, produce ONE of:
1. NEW ENTITY (not in the known entities list):
   - name, type, properties, traits, confidence
2. NEW EDGE (not in the known edges list):
   - source, target, type, confidence_origin, validation_tier
3. NEW MEMORY (a distinct insight not captured by existing memories):
   - text, domain, event_type, subject, related_entities

IMPORTANT:
- Do NOT re-extract entities or edges that are already known
- Only produce genuinely new content implied by the synthesized insights
- If the insights contain no new extractable content, return empty arrays

Respond with JSON only: {"entities": [...], "edges": [...], "memories": [...]}"""
```

- [ ] **Step 2: Write failing tests for convergence extraction helpers**

```python
# test_convergence_extract.py
import json
import pytest


def test_group_memories_by_entity():
    from extract_structure import group_memories_by_entity
    memories = [
        {'text': 'Reflection 1', 'subject': 'Frida Kahlo', 'structurally_extracted': False},
        {'text': 'Mood 1', 'subject': 'Frida Kahlo', 'structurally_extracted': False},
        {'text': 'Reflection 2', 'subject': 'Diego Rivera', 'structurally_extracted': False},
        {'text': 'Already done', 'subject': 'Frida Kahlo', 'structurally_extracted': True},
    ]
    groups = group_memories_by_entity(memories)
    assert 'Frida Kahlo' in groups
    assert len(groups['Frida Kahlo']) == 2
    assert 'Diego Rivera' in groups
    assert len(groups['Diego Rivera']) == 1


def test_group_memories_skips_no_subject():
    from extract_structure import group_memories_by_entity
    memories = [{'text': 'No subject', 'structurally_extracted': False}]
    groups = group_memories_by_entity(memories)
    assert len(groups) == 0


def test_build_convergence_prompt():
    from extract_structure import build_convergence_prompt
    entity_name = 'Frida Kahlo'
    memories = [
        {'text': 'Frida transformed pain into art'},
        {'text': 'Sustained distress 1934-1935'},
    ]
    known_entities = ['Frida Kahlo', 'Diego Rivera', 'Mexico City']
    known_edges = ['Frida Kahlo|Diego Rivera|married-to']
    prompt = build_convergence_prompt(entity_name, memories, known_entities, known_edges)
    assert 'Frida Kahlo' in prompt
    assert 'transformed pain' in prompt
    assert 'Diego Rivera' in prompt
    assert 'married-to' in prompt


def test_merge_entities_dedup():
    from extract_structure import merge_extraction_results
    existing = {
        'entities': [{'name': 'Frida Kahlo', 'type': 'person', 'source_passages': ['p1']}],
        'edges': [],
        'memories': [],
    }
    new_results = {
        'entities': [
            {'name': 'Frida Kahlo', 'type': 'person', 'new_prop': 'val'},
            {'name': 'New Entity', 'type': 'concept'},
        ],
        'edges': [{'source': 'Frida Kahlo', 'target': 'New Entity', 'type': 'associated-with'}],
        'memories': [],
    }
    merged = merge_extraction_results(existing, new_results, pass_n=2)
    entity_names = [e['name'] for e in merged['entities']]
    assert entity_names.count('Frida Kahlo') == 1
    assert 'New Entity' in entity_names
    assert len(merged['edges']) == 1


def test_merge_edges_dedup():
    from extract_structure import merge_extraction_results
    existing = {
        'entities': [],
        'edges': [{'source': 'A', 'target': 'B', 'type': 'knows'}],
        'memories': [],
    }
    new_results = {
        'entities': [],
        'edges': [
            {'source': 'A', 'target': 'B', 'type': 'knows'},
            {'source': 'A', 'target': 'C', 'type': 'knows'},
        ],
        'memories': [],
    }
    merged = merge_extraction_results(existing, new_results, pass_n=2)
    assert len(merged['edges']) == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest test_convergence_extract.py -v`
Expected: FAIL — functions not defined

- [ ] **Step 4: Implement helper functions**

Add to `extract_structure.py`:

```python
from pipeline_state import atomic_write, clamp_confidence


def call_convergence_llm(client, system_prompt, user_prompt, entity_name):
    """Make a single convergence extraction LLM call — direct prompt, no template."""
    try:
        response = client.messages.create(
            model=model_id(),
            max_tokens=4096,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}],
        )
        text = response.content[0].text
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except Exception as e:
        print(f"    Warning: convergence extraction failed for {entity_name}: {e}", file=sys.stderr)
    return {}


def group_memories_by_entity(memories: list) -> dict[str, list]:
    groups = {}
    for mem in memories:
        if mem.get('structurally_extracted'):
            continue
        subject = mem.get('subject')
        if not subject:
            continue
        groups.setdefault(subject, []).append(mem)
    return groups


def build_convergence_prompt(entity_name: str, memories: list,
                              known_entities: list, known_edges: list) -> str:
    mem_text = '\n'.join(f'  [{i+1}] {m["text"]}' for i, m in enumerate(memories))
    ent_text = ', '.join(known_entities[:50])
    edge_text = '\n'.join(f'  {e}' for e in known_edges[:50])
    return f"""Entity: {entity_name}

Synthesized insights ({len(memories)} total):
{mem_text}

Known entities (do NOT re-extract these):
{ent_text}

Known edges (do NOT re-extract these):
{edge_text if edge_text else '  (none)'}

Identify any NEW entities, edges, or memories implied by these insights."""


def merge_extraction_results(existing: dict, new_results: dict, pass_n: int) -> dict:
    ent_by_key = {}
    for ent in existing.get('entities', []):
        ent_by_key[ent['name'].lower()] = ent

    for ent in new_results.get('entities', []):
        key = ent['name'].lower()
        if key in ent_by_key:
            for k, v in ent.items():
                if k not in ent_by_key[key]:
                    ent_by_key[key][k] = v
        else:
            ent['extraction_pass'] = f'convergence-pass-{pass_n}'
            ent['extraction_method'] = 'llm-convergence-extract'
            if 'confidence' in ent:
                ent['confidence'] = clamp_confidence(ent['confidence'], pass_n)
            ent_by_key[key] = ent

    edge_keys = set()
    merged_edges = []
    for edge in existing.get('edges', []):
        key = f"{edge['source'].lower()}|{edge['target'].lower()}|{edge['type']}"
        if key not in edge_keys:
            edge_keys.add(key)
            merged_edges.append(edge)

    new_edge_count = 0
    for edge in new_results.get('edges', []):
        key = f"{edge['source'].lower()}|{edge['target'].lower()}|{edge['type']}"
        if key not in edge_keys:
            edge_keys.add(key)
            edge['extraction_pass'] = f'convergence-pass-{pass_n}'
            merged_edges.append(edge)
            new_edge_count += 1

    merged_memories = list(existing.get('memories', []))
    for mem in new_results.get('memories', []):
        mem['extraction_pass'] = f'convergence-pass-{pass_n}'
        mem['extraction_method'] = 'llm-convergence-extract'
        mem['convergence_pass'] = pass_n
        if 'confidence' in mem:
            mem['confidence'] = clamp_confidence(mem['confidence'], pass_n)
        merged_memories.append(mem)

    return {
        'entities': list(ent_by_key.values()),
        'edges': merged_edges,
        'memories': merged_memories,
    }
```

- [ ] **Step 5: Run helper tests — expect PASS**

Run: `python3 -m pytest test_convergence_extract.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Implement `run_convergence` function**

Add to `extract_structure.py`:

```python
def run_convergence(args):
    """Convergence mode: extract from generated memories, merge into structure."""
    client = create_client()

    with open(args.convergence, 'r') as f:
        enriched = json.load(f)
    with open(args.structure_base, 'r') as f:
        structure = json.load(f)

    all_generated = []
    for mem in enriched.get('phase2b_reflections', []):
        if isinstance(mem, dict) and mem.get('text'):
            all_generated.append(mem)
    for mem in enriched.get('phase2b_mood_snapshots', []):
        if isinstance(mem, dict) and mem.get('text'):
            all_generated.append(mem)

    groups = group_memories_by_entity(all_generated)
    if not groups:
        print("  No unextracted generated memories — nothing to do")
        print("NEW_ENTITIES=0")
        print("NEW_EDGES=0")
        print("NEW_MEMORIES=0")
        return

    known_entities = [e['name'] for e in structure.get('entities', [])]
    known_edges = [f"{e['source']}|{e['target']}|{e['type']}" for e in structure.get('edges', [])]

    total_new_entities = 0
    total_new_edges = 0
    total_new_memories = 0

    for i, (entity_name, mems) in enumerate(groups.items()):
        print(f"  [{i+1}/{len(groups)}] {entity_name}: {len(mems)} generated memories")
        prompt = build_convergence_prompt(entity_name, mems, known_entities, known_edges)

        result = call_convergence_llm(client, CONVERGENCE_SYSTEM, prompt, entity_name)
        if not result:
            result = {'entities': [], 'edges': [], 'memories': []}

        new_ent = len(result.get('entities', []))
        new_edg = len(result.get('edges', []))
        new_mem = len(result.get('memories', []))
        print(f"    → {new_ent} entities, {new_edg} edges, {new_mem} memories")
        total_new_entities += new_ent
        total_new_edges += new_edg
        total_new_memories += new_mem

        structure = merge_extraction_results(structure, result, args.pass_num)

        for mem in mems:
            mem['structurally_extracted'] = True
            mem['extraction_pass'] = f'convergence-pass-{args.pass_num}'

        structure['stats'] = {
            'entities': len(structure['entities']),
            'edges': len(structure['edges']),
            'memories': len(structure['memories']),
        }
        atomic_write(args.output, structure)
        atomic_write(args.convergence, enriched)

        known_entities = [e['name'] for e in structure['entities']]
        known_edges = [f"{e['source']}|{e['target']}|{e['type']}" for e in structure['edges']]

        time.sleep(0.2)

    print(f"\nConvergence extraction complete:")
    print(f"NEW_ENTITIES={total_new_entities}")
    print(f"NEW_EDGES={total_new_edges}")
    print(f"NEW_MEMORIES={total_new_memories}")
```

- [ ] **Step 7: Add convergence arguments to argparser and route in main()**

```python
    parser.add_argument('--convergence', help='Path to enriched.json for convergence extraction')
    parser.add_argument('--structure-base', help='Path to existing structure.json to merge into')
    parser.add_argument('--pass-num', type=int, default=1, help='Convergence pass number')
```

In `main()`, before the existing logic:

```python
    if args.convergence:
        if not args.structure_base:
            parser.error('--convergence requires --structure-base')
        run_convergence(args)
        return
```

- [ ] **Step 8: Add incremental writes to existing `main()` path**

In the existing passage processing loop, after `time.sleep(0.2)`, add an incremental write of the structure built so far. This retrofits idempotency to pass 1:

```python
        # incremental write after each passage
        interim = {
            'stats': {'entities': len(all_entities), 'edges': len(edge_dedup),
                      'memories': len(all_memories), 'passages_processed': i + 1},
            'entities': list(all_entities.values()),
            'edges': list(edge_dedup.values()),
            'memories': all_memories,
        }
        atomic_write(args.output, interim)
```

Also add a check at the start to skip already-processed passages (for restart):

```python
    # Resume: load existing output if present
    existing_output = None
    if os.path.exists(args.output):
        try:
            with open(args.output) as f:
                existing_output = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing_output = None

    processed_passages = set()
    if existing_output:
        # Rebuild state from existing output
        for ent in existing_output.get('entities', []):
            key = ent['name'].lower()
            all_entities[key] = ent
            for pid in ent.get('source_passages', []):
                processed_passages.add(pid)
        all_edges = existing_output.get('edges', [])
        all_memories = existing_output.get('memories', [])
        for e in all_edges:
            key = f"{e['source'].lower()}|{e['target'].lower()}|{e['type']}"
            edge_dedup[key] = e
```

In the passage loop, add skip logic:

```python
        if passage['id'] in processed_passages:
            print(f"  [{i+1}/{len(passages)}] {passage['id']}: SKIPPED (already processed)")
            continue
```

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench/scripts/extract_structure.py examples/cognitive-workbench/scripts/test_convergence_extract.py
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#525): add --convergence mode + idempotent restarts to extract_structure.py

Refs #525"
```

## Batch 4: Convergence Loop Orchestrator + Documentation

### Task 5: Rewrite `run_pipeline.sh` with convergence loop

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/scripts/run_pipeline.sh`

**Interfaces:**
- Consumes: All modified scripts (Tasks 1-4), `manifest.json` for resume state

- [ ] **Step 1: Rewrite run_pipeline.sh**

```bash
#!/bin/bash
# Cognitive extraction pipeline — convergence loop.
#
# Usage:
#   ./run_pipeline.sh <source.md> [output-dir] [--mode fixed-point|selective] [--max-passes N]
#
# The pipeline converges: after entity synthesis (Phase 2b) produces new
# memories, those go through structural extraction and enrichment. The loop
# terminates when no new memories are generated or max passes is reached.

set -euo pipefail

SOURCE="${1:?Usage: $0 <source.md> [output-dir] [--mode MODE] [--max-passes N]}"
OUTDIR="${2:-./output}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="${SCRIPT_DIR}/.venv/bin/python3"

MODE="fixed-point"
MAX_PASSES=5

shift 2 2>/dev/null || shift $# 2>/dev/null
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode) MODE="$2"; shift 2;;
        --max-passes) MAX_PASSES="$2"; shift 2;;
        *) shift;;
    esac
done

if [ ! -f "$VENV" ]; then
    echo "Error: venv not found at $VENV"
    echo "Run: python3 -m venv ${SCRIPT_DIR}/.venv && ${SCRIPT_DIR}/.venv/bin/pip install -r ${SCRIPT_DIR}/requirements.txt"
    exit 1
fi

mkdir -p "$OUTDIR"
MANIFEST="$OUTDIR/manifest.json"

echo "=== Cognitive Extraction Pipeline ==="
echo "Source: $SOURCE"
echo "Output: $OUTDIR"
echo "Mode: $MODE"
echo "Max passes: $MAX_PASSES"
echo ""

# --- Helper: check if a step is complete in the manifest ---
step_done() {
    if [ ! -f "$MANIFEST" ]; then return 1; fi
    $VENV -c "
import json, sys
m = json.load(open('$MANIFEST'))
passes = m.get('passes', [])
if not passes: sys.exit(1)
p = passes[-1]
sys.exit(0 if '$1' in p.get('steps_complete', []) else 1)
"
}

is_converged() {
    if [ ! -f "$MANIFEST" ]; then return 1; fi
    $VENV -c "
import json, sys
m = json.load(open('$MANIFEST'))
sys.exit(0 if m.get('converged') else 1)
"
}

current_pass() {
    if [ ! -f "$MANIFEST" ]; then echo "0"; return; fi
    $VENV -c "
import json
m = json.load(open('$MANIFEST'))
passes = m.get('passes', [])
print(passes[-1]['pass'] if passes else 0)
"
}

# --- Initialize manifest for pass 1 if needed ---
PASS=$(current_pass)
if [ "$PASS" = "0" ]; then
    $VENV -c "
from pipeline_state import PipelineManifest
m = PipelineManifest('$MANIFEST', mode='$MODE', max_passes=$MAX_PASSES)
m.start_pass(1)
"
    PASS=1
fi

# --- Check for convergence from prior run ---
if is_converged; then
    echo "Pipeline already converged. Skipping to post-convergence."
    PASS=999
fi

# ===================== PASS 1 =====================
if [ "$PASS" = "1" ]; then
    echo "=== Pass 1: Initial Extraction ==="

    if ! step_done "chunk"; then
        echo "--- Step 1: Chunk ---"
        $VENV "$SCRIPT_DIR/chunk.py" "$SOURCE" -o "$OUTDIR/passages.json"
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('chunk')"
        echo ""
    fi

    if ! step_done "nlp_extract"; then
        echo "--- Step 2: NLP Baseline ---"
        $VENV "$SCRIPT_DIR/nlp_extract.py" "$OUTDIR/passages.json" -o "$OUTDIR/nlp-baseline.json"
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('nlp_extract')"
        echo ""
    fi

    if ! step_done "gap_sweep"; then
        echo "--- Step 3: LLM Gap Sweep ---"
        $VENV "$SCRIPT_DIR/llm_gap_sweep.py" "$OUTDIR/passages.json" "$OUTDIR/nlp-baseline.json" -o "$OUTDIR/gap-sweep.json"
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('gap_sweep')"
        echo ""
    fi

    if ! step_done "extract_structure"; then
        echo "--- Step 4: Structural Extraction ---"
        $VENV "$SCRIPT_DIR/extract_structure.py" "$OUTDIR/passages.json" "$OUTDIR/nlp-baseline.json" --gaps "$OUTDIR/gap-sweep.json" -o "$OUTDIR/structure.json"
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('extract_structure')"
        echo ""
    fi

    if ! step_done "enrich_cognitive"; then
        echo "--- Step 5a: Passage-Level Enrichment ---"
        $VENV "$SCRIPT_DIR/enrich_cognitive.py" "$OUTDIR/passages.json" "$OUTDIR/structure.json" -o "$OUTDIR/enriched.json" --pass-num 1
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('enrich_cognitive')"
        echo ""
    fi

    if ! step_done "enrich_entity"; then
        echo "--- Step 5b: Entity-Level Synthesis ---"
        $VENV "$SCRIPT_DIR/enrich_entity.py" "$OUTDIR/enriched.json" "$OUTDIR/structure.json" --pass-num 1 --mode "$MODE" 2>&1 | tee /tmp/enrich_entity_output.txt
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('enrich_entity')"
        echo ""
    fi

    if ! step_done "backfill"; then
        echo "--- Step 5c: Backfill Enrichment ---"
        $VENV "$SCRIPT_DIR/enrich_cognitive.py" --backfill "$OUTDIR/enriched.json" --pass-num 1
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('backfill')"
        echo ""
    fi

    # Complete pass 1, extract new memory count
    NEW_MEMS=$(grep -o 'NEW_MEMORIES=[0-9]*' /tmp/enrich_entity_output.txt 2>/dev/null | head -1 | cut -d= -f2 || echo "0")
    $VENV -c "
from pipeline_state import PipelineManifest
m = PipelineManifest('$MANIFEST')
m.complete_pass(new_memories=${NEW_MEMS:-0}, new_entities=0, new_edges=0)
"
    echo "Pass 1 complete. New memories: ${NEW_MEMS:-0}"
fi

# ===================== CONVERGENCE LOOP =====================
PASS=$(current_pass)
if [ "$PASS" = "1" ]; then
    PASS=2
fi

while [ "$PASS" -le "$MAX_PASSES" ]; do
    if is_converged; then break; fi

    echo ""
    echo "=== Convergence Pass $PASS ==="

    # Start new pass if needed
    CURRENT=$(current_pass)
    if [ "$CURRENT" -lt "$PASS" ]; then
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.start_pass($PASS)"
    fi

    if ! step_done "convergence_extract"; then
        echo "--- Convergence Extraction ---"
        $VENV "$SCRIPT_DIR/extract_structure.py" --convergence "$OUTDIR/enriched.json" --structure-base "$OUTDIR/structure.json" -o "$OUTDIR/structure.json" --pass-num "$PASS"
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('convergence_extract')"
        echo ""
    fi

    if ! step_done "backfill_enrich"; then
        echo "--- Backfill Enrichment ---"
        $VENV "$SCRIPT_DIR/enrich_cognitive.py" --backfill "$OUTDIR/enriched.json" --pass-num "$PASS"
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('backfill_enrich')"
        echo ""
    fi

    if ! step_done "incremental_entity"; then
        echo "--- Incremental Entity Synthesis ---"
        $VENV "$SCRIPT_DIR/enrich_entity.py" "$OUTDIR/enriched.json" "$OUTDIR/structure.json" --incremental --pass-num "$PASS" --mode "$MODE" 2>&1 | tee /tmp/enrich_entity_output.txt
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('incremental_entity')"
        echo ""
    fi

    if ! step_done "backfill_new"; then
        echo "--- Backfill New Memories ---"
        $VENV "$SCRIPT_DIR/enrich_cognitive.py" --backfill "$OUTDIR/enriched.json" --pass-num "$PASS"
        $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.complete_step('backfill_new')"
        echo ""
    fi

    # Complete pass, check convergence
    NEW_MEMS=$(grep -o 'NEW_MEMORIES=[0-9]*' /tmp/enrich_entity_output.txt 2>/dev/null | head -1 | cut -d= -f2 || echo "0")
    NEW_ENTS=$(grep -o 'NEW_ENTITIES=[0-9]*' /tmp/enrich_entity_output.txt 2>/dev/null | head -1 | cut -d= -f2 || echo "0")
    NEW_EDGS=$(grep -o 'NEW_EDGES=[0-9]*' /tmp/enrich_entity_output.txt 2>/dev/null | head -1 | cut -d= -f2 || echo "0")

    $VENV -c "
from pipeline_state import PipelineManifest
m = PipelineManifest('$MANIFEST')
m.complete_pass(new_memories=${NEW_MEMS:-0}, new_entities=${NEW_ENTS:-0}, new_edges=${NEW_EDGS:-0})
if ${NEW_MEMS:-0} == 0:
    m.mark_converged()
"

    echo "Pass $PASS complete. New memories: ${NEW_MEMS:-0}"

    if [ "${NEW_MEMS:-0}" = "0" ]; then
        echo "Converged — no new memories generated."
        break
    fi

    PASS=$((PASS + 1))
done

if [ "$PASS" -gt "$MAX_PASSES" ] && ! is_converged; then
    echo "Safety stop — max passes ($MAX_PASSES) reached."
    $VENV -c "from pipeline_state import PipelineManifest; m = PipelineManifest('$MANIFEST'); m.mark_converged()"
fi

# ===================== POST-CONVERGENCE =====================
echo ""
echo "--- Step 6: Reference Overlay ---"
$VENV "$SCRIPT_DIR/generate_overlay.py" "$OUTDIR/structure.json" "$OUTDIR/passages.json" -o "$OUTDIR/reference-overlay.json"
echo ""

echo "--- Step 7: Assemble Corpus ---"
$VENV "$SCRIPT_DIR/assemble_corpus.py" "$OUTDIR/enriched.json" "$OUTDIR/nlp-baseline.json" -o "$OUTDIR/corpus.json" -r "$OUTDIR/coverage-report.json"
echo ""

# Print convergence summary
echo "=== Pipeline Complete ==="
$VENV -c "
import json
m = json.load(open('$MANIFEST'))
for p in m['passes']:
    print(f\"  Pass {p['pass']}: {p['new_memories']} new memories, {p.get('new_entities', 0)} new entities, {p.get('new_edges', 0)} new edges\")
print(f\"  Total passes: {len(m['passes'])}\")
print(f\"  Converged: {m['converged']}\")
"
echo ""
echo "Outputs:"
echo "  $OUTDIR/passages.json        — chunked passages"
echo "  $OUTDIR/nlp-baseline.json    — NLP entity concordance"
echo "  $OUTDIR/gap-sweep.json       — LLM gap findings"
echo "  $OUTDIR/structure.json       — extracted graph structure"
echo "  $OUTDIR/enriched.json        — cognitively enriched data"
echo "  $OUTDIR/corpus.json          — importable corpus"
echo "  $OUTDIR/manifest.json        — convergence state"
echo "  $OUTDIR/coverage-report.json — coverage audit"
```

- [ ] **Step 2: Test the script parses arguments correctly**

Run: `bash -n /Users/mdproctor/claude/casehub/slots/211/blocks-ui/examples/cognitive-workbench/scripts/run_pipeline.sh`
Expected: No syntax errors

- [ ] **Step 3: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench/scripts/run_pipeline.sh
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "feat(#525): rewrite run_pipeline.sh with convergence loop + manifest resume

Refs #525"
```

### Task 6: Document convergence loop in methodology §5.1c

**Files:**
- Modify: `blocks-ui/examples/cognitive-workbench/docs/cognitive-extraction-methodology.md`

**Interfaces:**
- None (documentation only)

- [ ] **Step 1: Add §5.1c after §5.1b**

Insert after the "Anti-patterns" section at line ~973, before "### 5.2 Subagent Dispatch Pattern":

```markdown
### 5.1c Convergence Loop Architecture

The pipeline enforces a fixed-point invariant: every text — source or generated — must pass through structural extraction, cognitive enrichment, and entity-level synthesis. This is achieved via a convergence loop.

#### Loop structure

```
Pass 1 (initial):
  chunk → nlp_extract → gap_sweep → extract_structure → enrich_cognitive
  → enrich_entity → backfill

Pass 2+ (convergence):
  convergence_extract → backfill_enrich → incremental_entity → backfill_new
  → check: new_memories == 0 → converged

Post-convergence:
  generate_overlay → assemble_corpus
```

Typically converges in 2-3 passes. Safety bound: `--max-passes` (default 5).

#### Convergence extraction

Generated memories (reflections, mood snapshots) are grouped by subject entity. One batched LLM call per entity with the entity's generated memories + known graph context. The prompt asks only for NEW content not already in the graph. This is prompt-level dedup.

#### Confidence decay

Each pass caps maximum confidence: pass 1 = 1.0, pass 2 = 0.8, pass 3 = 0.6, pass 4+ = 0.4. LLM-assigned values are clamped. All convergence-generated content gets `confidence.origin = INFERRED`. Synthesis skips entities where all new data is below confidence 0.4.

#### Convergence modes

| Mode | Behaviour |
|------|-----------|
| `fixed-point` (default) | All generated content triggers re-synthesis |
| `selective` | Only reflections trigger re-synthesis |

#### Idempotency

Two-level tracking: (1) item markers on data (`structurally_extracted`, `enriched`, `synthesis_pass`), (2) pass-level `manifest.json`. Scripts write incrementally via atomic rename. On restart: manifest determines pass/step, markers determine item-level progress.

#### Provenance

Convergence-generated items carry `extraction_pass: convergence-pass-N`, `extraction_method: llm-convergence-extract`, and `convergence_pass: N` for full audit trail.
```

- [ ] **Step 2: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui add examples/cognitive-workbench/docs/cognitive-extraction-methodology.md
git -C /Users/mdproctor/claude/casehub/slots/211/blocks-ui commit -m "docs(#525): add §5.1c convergence loop architecture to methodology

Refs #525"
```

## References

- [2026-10-09-pipeline-convergence-loop-design.md] — design spec this plan implements
- `blocks-ui/examples/cognitive-workbench/scripts/run_pipeline.sh` — current pipeline orchestrator
- `blocks-ui/examples/cognitive-workbench/scripts/extract_structure.py` — structural extraction (3 calls/passage)
- `blocks-ui/examples/cognitive-workbench/scripts/enrich_entity.py` — Phase 2b entity synthesis
- `blocks-ui/examples/cognitive-workbench/scripts/enrich_cognitive.py` — Phase 2a cognitive enrichment
- `blocks-ui/examples/cognitive-workbench/scripts/pipeline_state.py` — new convergence state module
- `blocks-ui/examples/cognitive-workbench/scripts/llm_client.py` — shared LLM client
- `blocks-ui/examples/cognitive-workbench/scripts/coverage.py` — coverage gate library
- `blocks-ui/examples/cognitive-workbench/scripts/test_coverage.py` — existing test suite
- `blocks-ui/examples/cognitive-workbench/docs/cognitive-extraction-methodology.md` — methodology doc
- casehubio/neocortex#525 — focal issue
- D10-D13 in decisions.md — design decisions
