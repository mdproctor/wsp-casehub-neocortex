# HANDOFF — casehub-neocortex

## Last Session

Epic #526 (corpus extraction richness) — 16/17 items complete. Remaining: #529 (pipeline re-run).

Session closed 13 issues, created the epic, added 22 unit tests for importer coverage, split goal extraction into a dedicated 4th LLM call, added `--limit N` for fast iteration. All blocks-ui commits on `issue-471-cognitive-workbench`.

## Immediate Next Step — AUTONOMOUS CALIBRATION (#529)

**The user is away for the afternoon. Work autonomously. Do not ask questions — use initiative, fork sub-agents for ideas, and self-evaluate.**

### Mission

Calibrate the extraction pipeline to maximize data richness with zero regressions against the baseline. Iterate fast on small subsets (`--limit 3`), evaluate, pivot if not progressing, then do a full run when confident.

### Baseline (old corpus in `output/`)

| Metric | Old value | Target |
|--------|-----------|--------|
| Nodes | 168 | ≥150 |
| Goals | 56 | ≥50 |
| Formative experiences | 12 | ≥40 (was 65 in 3-call run) |
| Lifecycle events | 0 | ≥15 |
| Memories | 285 (197 enriched) | ≥250 |
| Domains | exp:78, rel:23, ref:106, mood:76 | All 4 represented |
| Coverage gate | Not run | ≥80% on node/memory/enrichment |

### 2-passage spot check (from the 4-call split)

45 entities, 15 goals, 12 formative, 4 lifecycle entities from 2 passages. Projected ~170+ entities at full scale. The 4-call split works — validated.

### What to calibrate

1. **Extraction prompt tuning** — the prompts are in `extract_structure.py` (ENTITY_SYSTEM, GOAL_SYSTEM, EDGE_SYSTEM, MEMORY_SYSTEM). Adjust wording, specificity, examples to maximize yield without regression.

2. **Chunk strategy** — `chunk.py` splits on markdown headers. Current passages are ~2,500 chars each. Try:
   - Sub-chunking long passages (>3000 chars) into smaller pieces
   - Overlapping chunks for entity continuity
   - Different granularity and measure impact on entity yield

3. **Call structure** — currently 4 calls per passage (entities, goals, edges, memories). Try:
   - Merging edges back into entities (edges may need entity context)
   - Splitting memory extraction (formative vs regular)
   - Second-pass extraction for implicit entities missed on first pass

4. **Model choice** — currently claude-haiku-4-5. Try:
   - Sonnet for extraction (more expensive but potentially better yield)
   - Haiku for enrichment (cheaper, enrichment is more mechanical)
   - Compare cost vs quality tradeoff

5. **Convergence tuning** — how many passes, what threshold for "converged"

### Architecture — token-efficient orchestration

**Keep the main context lean.** Reusable scripts handle all heavy lifting — forks are tiny dispatches, not repeated prompts.

**Pre-built tools (do NOT regenerate — just invoke):**

| Script | Purpose | Usage |
|--------|---------|-------|
| `iterate.sh` | Clean run + compare + log | `bash iterate.sh --limit 3 --label "try-X"` |
| `compare_corpus.py` | Baseline comparison with scores | `python3 compare_corpus.py baseline.json candidate.json` |
| `iteration-log.md` | Append-only log of all iterations | Auto-updated by iterate.sh |

**Iteration loop — the main session does only this:**
1. Decide what to change (prompt, chunking, call structure)
2. Fork to make the change and commit
3. Run `iterate.sh --limit 3 --label "description"` in background
4. When done, read just the last entry in `iteration-log.md` (the score line)
5. Decide next action based on score

**Fork prompts should be SHORT.** Example:
- "In extract_structure.py, add 'Extract at least 5 entities per passage' to ENTITY_SYSTEM before the Respond line. Commit as wip."
- "Read the last 30 lines of iteration-log.md and report: score, regressions, recommendation in under 50 words."

**Never re-read corpus JSON in the main context.** The scripts produce human-readable summaries. If you need deeper analysis, fork it.

### Evaluation protocol

After each iteration:
1. Count: entities, goals, formative experiences, lifecycle events, memories, enriched memories
2. Compare against baseline — flag regressions
3. Check coverage gate report (in `coverage-gate-report.json`)
4. Score: improvement = gains - (2 × regressions). Regressions cost double.
5. If 3 consecutive iterations show no improvement, **pivot strategy** — fork a sub-agent to brainstorm alternatives

### Decision framework

| Situation | Action |
|-----------|--------|
| Regression on entities/goals | Revert prompt change, try different angle |
| Improvement on some metrics, regression on others | Keep change, add targeted fix for regression |
| 3 iterations no progress | Fork brainstorm agent for 5 alternative approaches |
| All metrics meet targets | Run full pipeline (`--limit 0`), verify at scale |
| Full run matches subset projections | Close #529, update HANDOFF |
| Full run regresses vs subset | Fork agent to investigate per-passage quality |
| Context getting heavy | Start a fresh session with `work continue` — HANDOFF has everything |

### Session management

If the main context fills up (completed 5+ iterations, lots of back-and-forth), **start a fresh session** via `work continue`. The HANDOFF will carry forward what worked and what didn't. Don't try to do everything in one session — fresh context reasons better than compressed context on iteration 15.

### Important paths

| Path | What |
|------|------|
| `blocks-ui/examples/cognitive-workbench/scripts/` | Pipeline scripts |
| `blocks-ui/examples/cognitive-workbench/scripts/extract_structure.py` | Extraction prompts (ENTITY_SYSTEM, GOAL_SYSTEM, EDGE_SYSTEM, MEMORY_SYSTEM) |
| `blocks-ui/examples/cognitive-workbench/scripts/chunk.py` | Chunking strategy |
| `blocks-ui/examples/cognitive-workbench/scripts/llm_client.py` | LLM client (model selection) |
| `blocks-ui/examples/cognitive-workbench/scripts/run_pipeline.sh` | Pipeline runner (--limit flag) |
| `blocks-ui/examples/cognitive-workbench/output/` | Old baseline corpus |
| `blocks-ui/examples/cognitive-workbench/output-test/` | 3-passage test (may have completed) |
| `blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md` | Source biography |

### Key findings from prior session

1. **Combined entity+goal prompt caused 85% entity regression.** Fixed by splitting into 4 calls. Don't combine them again.
2. **Frida-specific examples in prompts caused the LLM to only extract those examples.** Use generic guidance, not subject-specific examples.
3. **LLM sometimes returns bare float confidence** instead of {origin, value} dict. Already fixed in clamp_confidence.
4. **LifecycleDate uses EDTF postfix qualifiers** (`1939~` not `~1939`).

### Commit discipline

Commit after every substantial change. Use `wip: <description>` for checkpoint commits. The blocks-ui repo is on branch `issue-471-cognitive-workbench`.

## Open Issues

| Issue | Summary | Status |
|-------|---------|--------|
| #526 | **Epic: corpus extraction richness** | 16/17 done |
| #529 | Pipeline re-run + coverage verification | **Active — autonomous calibration** |
| #498 | Napoleon biography | After #526 |
| #502 | Importer UI | After #526 |
| #514 | Coverage gate / field registry | During #529 |

## References

- Epic: casehubio/neocortex#526
- Pipeline scripts: `blocks-ui/examples/cognitive-workbench/scripts/`
- Source biography: `blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md`
