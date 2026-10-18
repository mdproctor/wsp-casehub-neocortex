# Pipeline Convergence Loop Design

**Issue:** casehubio/neocortex#525
**Date:** 2026-10-09
**Branch:** issue-468-cognitive-workbench
**Repo:** blocks-ui (examples/cognitive-workbench/scripts/)

## Problem

The extraction pipeline runs as a fixed linear sequence: extract → enrich(2a) → synthesise(2b) → backfill(2a) → assemble. Phase 2b generates new text content (reflections, mood snapshots) that is only backfill-enriched — never run through structural extraction (no entity/edge discovery from their text) and never fed back into synthesis. Insights-from-insights are lost.

The pipeline must also survive interruption. Currently, any crash means a full restart — all LLM calls are re-executed, wasting time and cost.

## Invariant

Every text in the system — source or generated — has been:

1. **Structurally extracted** (entities, edges, memories identified)
2. **Cognitively enriched** (PAD, OCC, SEC, CAPS, drives, sub-thoughts, etc.)
3. **Fed into entity-level synthesis** (content informs the entity's cognitive profile)

The pipeline enforces this via a fixed-point convergence loop that terminates when no new content is produced.

## Convergence Loop

### Pass 1 (initial — unchanged from current pipeline)

```
chunk → nlp_extract → gap_sweep → extract_structure → enrich_cognitive → enrich_entity → backfill
```

After enrich_entity completes, record the count of new memories generated (reflections + mood snapshots).

### Pass 2+ (convergence)

```
1. Collect unextracted generated memories from prior pass
2. extract_structure --convergence    (batched per entity, graph-aware)
3. enrich_cognitive --backfill        (enrich all unenriched memories)
4. enrich_entity --incremental        (re-synthesize entities with new data)
5. enrich_cognitive --backfill        (enrich Phase 2b output)
6. new_memory_count = count from step 4
7. If new_memory_count == 0 → converged, break
8. If pass >= max_passes → safety stop, break
```

### Post-convergence

```
generate_overlay → assemble_corpus
```

### Termination guarantees

- **Natural convergence:** Each pass processes increasingly distilled content, producing diminishing returns. Practically terminates in 2-3 passes.
- **Confidence ceiling:** Pass-based confidence capping (see §Correctness) means later passes produce lower-confidence content, which is less likely to trigger synthesis.
- **Safety bound:** `max_passes` (default 5) provides a hard upper bound.

### Convergence mode configuration

The pipeline supports two modes via a `--mode` flag on `run_pipeline.sh`:

| Mode | Default | Behaviour |
|------|---------|-----------|
| `fixed-point` | Yes | All generated content (reflections, moods, drive profiles) triggers re-synthesis |
| `selective` | No | Only reflections trigger re-synthesis. Moods and drive profiles get extract+enrich but don't feed back into Phase 2b |

Selective mode is a cost dial — reflections carry the most semantic value for re-synthesis, while mood snapshots rarely surface new entities.

## Idempotency

### Item-level markers

Each data item carries processing flags that scripts check before processing:

**Memories:**
```json
{
  "text": "...",
  "structurally_extracted": true,
  "extraction_pass": "convergence-pass-2",
  "enriched": true,
  "enrichment_source": "phase-2a-backfill"
}
```

**Entities (in entity_enrichments):**
```json
{
  "Frida Kahlo": {
    "synthesis_pass": 2,
    "drive_baselines": {...},
    ...
  }
}
```

Scripts skip items where the relevant marker is already set. This provides item-level crash recovery — a step that processed 80/100 items before crashing resumes at item 81.

### Incremental writes

All LLM-based scripts write the output file after processing each item (or each batch for convergence extraction). The data file IS the checkpoint. On crash, the last successfully written item is preserved.

For `extract_structure.py` and `enrich_cognitive.py`, this means writing the full JSON after each processed passage/memory. For files of ~200KB, this is negligible overhead compared to the seconds-per-item LLM calls. Writes use write-to-temp + atomic rename (`os.replace`) to prevent corruption on crash mid-write.

For `enrich_entity.py`, write after each entity (3 LLM calls per entity, ~7 central entities).

### Pass-level manifest

`manifest.json` in the output directory tracks overall pipeline state:

```json
{
  "mode": "fixed-point",
  "max_passes": 5,
  "confidence_ceilings": [1.0, 0.8, 0.6, 0.4, 0.4],
  "passes": [
    {
      "pass": 1,
      "status": "complete",
      "steps_complete": ["chunk", "nlp_extract", "gap_sweep", "extract_structure", "enrich_cognitive", "enrich_entity", "backfill"],
      "new_memories": 23,
      "new_entities": 3,
      "new_edges": 5
    },
    {
      "pass": 2,
      "status": "in_progress",
      "step": "enrich_cognitive",
      "items_done": 15,
      "items_total": 30,
      "new_memories": 0,
      "new_entities": 0,
      "new_edges": 0
    }
  ],
  "converged": false
}
```

On restart:
1. Read manifest → find current pass and step
2. Skip completed passes entirely
3. Resume at current step within current pass
4. Within the step, item-level markers handle skipping processed items

### Resume flow

```
run_pipeline.sh starts
  ├── manifest.json exists?
  │   ├── No → fresh run, start at pass 1 step 1
  │   └── Yes → read manifest
  │       ├── Last pass complete + converged → skip to post-convergence
  │       ├── Last pass complete + not converged → start next pass
  │       └── Last pass in_progress → resume at recorded step
  │           └── Item markers within step handle skip logic
```

## Correctness

### Confidence decay

Each convergence pass caps maximum confidence:

| Pass | Ceiling | Typical content |
|------|---------|-----------------|
| 1 | 1.0 | Source passage extraction |
| 2 | 0.8 | Reflections/moods from pass 1 synthesis |
| 3 | 0.6 | Insights from pass 2 generated content |
| 4+ | 0.4 | Diminishing returns |

The LLM's assigned confidence value is clamped: `min(llm_confidence, ceiling)`. Content from convergence passes gets `confidence.origin = INFERRED` automatically.

### Synthesis threshold

In convergence passes, `enrich_entity.py --incremental` only re-synthesizes entities that have new data (edges, memories, or neighbours added) since their last synthesis AND where that new data has confidence above 0.4. Entities with only low-confidence additions are skipped — the marginal value of re-synthesis doesn't justify the cost.

### Deduplication

Before adding content from convergence extraction:

- **Entities:** Dedup by normalized name (lowercase). If an entity already exists, merge properties (new properties added, existing preserved).
- **Edges:** Dedup by `source|target|type` key. Existing edges preserved; duplicates dropped.
- **Memories:** The LLM prompt for convergence extraction includes the list of known entities and existing memories, instructing it to identify only NEW content. This is prompt-level dedup — cheaper than post-hoc text similarity.

### Provenance

Every item carries its derivation context:

- `extraction_pass`: `phase-1-structural` (pass 1), `convergence-pass-2`, `convergence-pass-3`, etc.
- `extraction_method`: `llm-extract` (pass 1), `llm-convergence-extract` (pass 2+)
- `enrichment_source`: `phase-2a-passage`, `phase-2a-backfill`, `phase-2b-entity`
- `convergence_pass`: integer pass number on all convergence-generated items

This enables full audit: any item can be traced to its origin pass and derivation chain.

## File Changes

### New file: `pipeline_state.py`

Manifest read/write and item marker utilities.

```python
class PipelineManifest:
    def __init__(self, path):           # reads existing or creates new
    def start_pass(self, pass_n):       # record pass start
    def update_step(self, step, items_done, items_total): # progress tracking
    def complete_step(self, step):      # mark step done in current pass
    def complete_pass(self, new_memories, new_entities, new_edges): # mark pass done
    def mark_converged(self):           # terminal state
    def current_pass(self) -> int:      # which pass we're on
    def current_step(self) -> str:      # which step within the pass
    def is_step_complete(self, step):   # check for resume
    def save(self):                     # write to disk

def confidence_ceiling(pass_n: int) -> float:
    ceilings = [1.0, 0.8, 0.6, 0.4]
    return ceilings[min(pass_n - 1, len(ceilings) - 1)]

def clamp_confidence(confidence: dict, pass_n: int) -> dict:
    ceiling = confidence_ceiling(pass_n)
    return {**confidence, 'value': min(confidence.get('value', 1.0), ceiling)}
```

### Modified: `extract_structure.py`

Add `--convergence` mode:

- Accepts `enriched.json` as input (reads generated memories)
- Accepts `--structure-base` to merge into existing structure
- Accepts `--pass N` for confidence ceilings and provenance tagging
- Groups generated memories by subject entity
- One batched LLM call per entity (with graph context + known entities list)
- Merges new entities/edges/memories into structure, deduplicating
- Stamps processed memories with `structurally_extracted: true`
- Writes incrementally after each entity batch
- New prompt: asks for NEW content only, given known graph context

### Modified: `enrich_entity.py`

Add `--incremental` mode:

- Accepts `--pass N` for confidence ceilings and provenance
- Tracks which entities were synthesized in which pass (via `synthesis_pass` marker)
- In incremental mode: only synthesizes entities with new data above confidence threshold since their `synthesis_pass`
- Reports count of new memories generated (the convergence metric)
- Writes incrementally after each entity
- Dedup: checks new reflections/moods against existing ones before adding

### Modified: `enrich_cognitive.py`

Add incremental writes:

- After enriching each memory, write the output file
- Backfill mode already skips enriched items (has `cognitive` key) — no logic change needed
- Add `--pass N` for provenance tagging on enrichment_source

### Modified: `run_pipeline.sh`

Convergence loop with manifest-based resume:

- Accept `--mode fixed-point|selective` (default: fixed-point)
- Accept `--max-passes N` (default: 5)
- Read manifest on start, resume if exists
- After pass 1, enter convergence loop
- Each pass updates manifest at step boundaries
- On convergence or max-passes: proceed to post-convergence steps
- Report convergence summary (passes, new content per pass)

### Documentation: methodology §5.1c

Add a new section documenting the convergence loop architecture, confidence decay model, idempotency mechanism, and configuration options.

## Acceptance Criteria

- [ ] Pipeline runs as a convergence loop (fixed-point default)
- [ ] Every generated memory goes through full extraction + enrichment chain
- [ ] Terminates when no new memories are generated (or max iterations reached)
- [ ] Confidence ceiling enforced per pass (1.0 / 0.8 / 0.6 / 0.4)
- [ ] Idempotent: restart after crash resumes at last incomplete item
- [ ] Manifest tracks pass/step/item state
- [ ] Selective mode configurable via `--mode selective`
- [ ] Documented in methodology §5.1c

## References

- casehubio/neocortex#525 — pipeline convergence loop issue
- `blocks-ui/examples/cognitive-workbench/scripts/run_pipeline.sh` — current pipeline
- `blocks-ui/examples/cognitive-workbench/scripts/extract_structure.py` — structural extraction
- `blocks-ui/examples/cognitive-workbench/scripts/enrich_entity.py` — Phase 2b synthesis
- `blocks-ui/examples/cognitive-workbench/scripts/enrich_cognitive.py` — Phase 2a enrichment
- `blocks-ui/examples/cognitive-workbench/docs/cognitive-extraction-methodology.md` §5.1 — architecture
- cognitive-api `Confidence` record, `ConfidenceOrigin` enum — confidence model
- D10-D13 in decisions.md — design decisions for this spec
