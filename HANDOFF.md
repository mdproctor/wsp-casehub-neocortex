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

**Three reusable agent prompts in `agents/` — read and dispatch, never regenerate:**

| Agent | File | Role | Invoke with |
|-------|------|------|-------------|
| Executor | `agents/executor.md` | Apply change + run pipeline | CHANGE + LABEL + LIMIT |
| Evaluator | `agents/evaluator.md` | Score results + check regressions | iteration label |
| Strategist | `agents/strategist.md` | Analyze history + propose next | (reads logs itself) |

**The orchestrator loop:**
1. Fork strategist → reads `changes-log.md` + `iteration-log.md` → writes `strategy.md` with next change
2. Read `strategy.md` (tiny — under 150 words)
3. Fork executor with the proposed change → applies it, runs pipeline, commits
4. Fork evaluator → scores results, writes `evaluation.md`
5. Read `evaluation.md` (tiny — under 100 words)
6. Append to `changes-log.md`: what was tried, what happened
7. If "DONE — ready for full run" → run full pipeline
8. Otherwise → goto 1

**State files (append-only, the orchestrator's memory):**
- `changes-log.md` — what was tried and what happened (prevents loops)
- `iteration-log.md` — quantitative scores per iteration (auto-updated by iterate.sh)

**Never re-read corpus JSON in the main context.** Agents produce human-readable summaries. The orchestrator reads only strategy.md and evaluation.md — both under 150 words.

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

Two modes for calibration:

**Mode 1 — Single session with forks (simpler):**
Use `iterate.sh` in background, forks for prompt changes, read `iteration-log.md` for results. Start fresh sessions via `work continue` when context fills up (~5 iterations).

**Mode 2 — Parallel tmux sessions (faster):**
```bash
python3 scripts/calibrate.py --experiments experiments.yaml
# Monitor:
tmux attach -t calibrate
python3 scripts/calibrate.py --check
python3 scripts/calibrate.py --summarize
```
Each experiment gets its own Claude Code session with full context. Define variants in `experiments.yaml`, launch all at once, compare results. Add new experiments to the YAML and re-launch — completed ones are skipped.

**When to use which:** Mode 1 for sequential refinement (each iteration builds on the last). Mode 2 for parallel A/B testing (independent variants tested simultaneously).

### Important paths

| Path | What |
|------|------|
| `/Users/mdproctor/claude/agents/pipeline-calibration/` | **Orchestrator + meta-agent briefs** (create new ones here as needed) |
| `blocks-ui/.../agents/` | Executor, evaluator, strategist briefs |
| `blocks-ui/.../scripts/extract_structure.py` | Extraction prompts (ENTITY_SYSTEM, GOAL_SYSTEM, EDGE_SYSTEM, MEMORY_SYSTEM) |
| `blocks-ui/.../scripts/chunk.py` | Chunking strategy |
| `blocks-ui/.../scripts/llm_client.py` | LLM client (model selection) |
| `blocks-ui/.../scripts/run_pipeline.sh` | Pipeline runner (--limit flag) |
| `blocks-ui/.../scripts/iterate.sh` | Clean run + compare + log |
| `blocks-ui/.../scripts/compare_corpus.py` | Baseline comparison |
| `blocks-ui/.../scripts/calibrate.py` | Tmux parallel launcher |
| `blocks-ui/.../output/` | Old baseline corpus |
| `blocks-ui/.../output-test/` | Subset test output |
| `blocks-ui/.../changes-log.md` | Experiment history (prevents loops) |
| `blocks-ui/.../iteration-log.md` | Quantitative scores |
| `blocks-ui/.../experiments.yaml` | Parallel experiment definitions |
| `blocks-ui/.../source/frida-kahlo-biography.md` | Source biography |

### Agent inventory

**Meta-level** (`/Users/mdproctor/claude/agents/pipeline-calibration/`):
- `orchestrator.md` — main loop, dispatches agents, tracks iterations
- `dead-end-detector.md` — identifies loops, stalls, regressions
- `results-analyst.md` — deep quality analysis (QUALITY/GAP/COMPARE modes)
- `approach-generator.md` — brainstorms 5 novel approaches when stuck

**Execution-level** (`blocks-ui/.../agents/`):
- `evaluator.md` — scores results, checks regressions (<100 words)
- `executor.md` — applies change, runs pipeline, commits (<50 words)
- `strategist.md` — proposes next experiment from history (<150 words)

**You can create new agent .md files as needed.** If you need a chunk-optimizer, a prompt-A/B-tester, or any other specialist, create it in the agents folder.

### Tmux + Claude verified

```bash
# Tested and working:
CLAUDE_CODE_USE_VERTEX=1 ANTHROPIC_VERTEX_PROJECT_ID=itpc-gcp-cp-pe-eng-claude CLOUD_ML_REGION=us-east5 claude --dangerously-skip-permissions -p '<prompt>'

# Read tmux output:
tmux capture-pane -t <session>:<window> -p | tail -20

# Kill session:
tmux kill-session -t <session>
```

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
