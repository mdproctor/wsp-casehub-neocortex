# HANDOFF — casehub-neocortex

## Last Session

Epic #526 (corpus extraction richness) — 16/17 items complete. Remaining: #529 (pipeline re-run).

**Session work:**
- Extraction prompts: #501 (lifecycle), #527 (formative), #528 (goals)
- Importer round 1: #530 (formative attrs), #531 (LifecycleResolver), #532 (gut/temporal/caps/contradicts)
- Importer round 2 (audit-driven): #533 (goal+trait nodes), #534 (edge metadata), #535 (memory provenance), #536 (entity enrichments), #537 (subject parameterization)
- Fixed: clamp_confidence float handling, EDTF postfix qualifiers
- Split goal extraction into dedicated 4th LLM call (entity regression fix)
- Added `--limit N` to both `extract_structure.py` and `run_pipeline.sh` for fast subset iteration

All blocks-ui commits on `issue-471-cognitive-workbench`.

## Immediate Next Step

**#529 — Pipeline re-run with coverage verification.** Use subset iteration to calibrate.

### What to do

1. Check if the 3-passage test in `output-test/` completed (was still running at session end)
2. If complete, examine results — goals, entities, lifecycle, formative experiences
3. If quality is good, run full 16-passage pipeline: `./run_pipeline.sh <source> output-v2 --max-passes 3`
4. If quality needs work, iterate on prompts using `--limit 3` for fast turnaround
5. Compare before/after against old corpus in `output/`
6. Run coverage gate and verify 85-field registry (#514)

### Baseline for comparison (old corpus in output/)

| Metric | Old value |
|--------|-----------|
| Nodes | 168 |
| Goals | 56 |
| Formative experiences | 12 |
| Lifecycle events | 0 |
| Memories | 285 (197 enriched) |
| Domains | experience:78, relationship:23, reflection:106, mood:76 |

### 2-passage spot check (verified — output-test/structure.json from earlier run)

| Metric | 2 passages | Projected 16 |
|--------|-----------|--------------|
| Entities | 45 | ~170+ |
| Goals | 15 | ~120+ |
| Formative | 12 | ~96 |
| Lifecycle entities | 4 | ~30+ |

### Key findings from this session

1. **Combined entity+goal prompt caused 85% entity regression** (168→25). Fixed by splitting goals into a dedicated 4th LLM call.
2. **17 corpus fields were silently dropped by the importer.** All fixed with 22 unit tests.
3. **LifecycleDate uses EDTF postfix qualifiers** (`1939~` not `~1939`). Extraction prompt corrected.
4. **LLM sometimes returns bare float confidence** instead of {origin, value} dict. Fixed in clamp_confidence.
5. **Subject was hardcoded to frida-kahlo.** Now parameterized from corpus.json.

## Key Context

- Pipeline makes 4 LLM calls per passage: entities, goals, edges, memories (was 3)
- `--limit N` flag enables fast subset iteration without full runs
- CorpusImporter has 5 testable static methods: buildMemoryAttributes, resolveTemporalBounds, buildNodeProperties, buildEdgeProperties, resolveSubject
- 22 unit tests cover all importer paths — zero dropped fields
- Neocortex 0.2-SNAPSHOT installed to local Maven repo with LifecycleResolver

## Open Issues

| Issue | Summary | Status |
|-------|---------|--------|
| #526 | **Epic: corpus extraction richness** | 16/17 done |
| #529 | Pipeline re-run + coverage verification | **Next** — iterate with --limit |
| #498 | Napoleon biography | After #526 |
| #499 | Behavioural template extraction | Design done |
| #502 | Importer UI | After #526 |
| #503 | Avatar narrator | Design done |
| #514 | Coverage gate / field registry | During #529 |

## References

- Epic: casehubio/neocortex#526
- Pipeline scripts: `blocks-ui/examples/cognitive-workbench/scripts/`
- Source biography: `blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md`
- Test output (3-passage subset): `blocks-ui/examples/cognitive-workbench/output-test/`
- Old corpus (baseline): `blocks-ui/examples/cognitive-workbench/output/`
