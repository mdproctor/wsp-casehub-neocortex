# HANDOFF — casehub-neocortex

## Last Session

Closed 4 issues: #920 (eval signal review — no RPI evidence), #940 (fragile drive detection fix), #937 (process constraint eval — 10/11 passed), #889 (literature Javadoc citations cherry-picked). Also reconciled local/upstream main divergence from mega-squash issue — canonical main rewritten by fixer slot, local main synced.

### Issues completed

| # | Title | Scale | Outcome |
|---|-------|-------|---------|
| #920 | Eval signal — RPI stale strategy persistence | S | Closed — zero instances in eval traces, existing anti-RPI mechanisms catalogued |
| #940 | DriveProfilePipelineTest fragile verbatim detection | XS | Landed `de8cb4a2` — replaced verbatim description matching with drive type label detection |
| #937 | Verify process constraint effectiveness via LLM eval suite | S | Closed — 10/11 passed (91%), gate 80%. Results in `docs/eval/process-constraint-eval-937.json` |
| #924 | Two-tier CoherenceJudge | — | Closed by another slot |
| #939 | CAPS classifier empty-result fallback | — | Closed by another slot |

### Pending branch

`issue-889-literature-javadoc-cherry` — 6 commits on top of main:
- 4 cherry-picked Javadoc `@see` literature citation commits (#889)
- Stream 11 research doc additions (#920, #937 findings)
- Process constraint findings verification section

**Needs landing** via work-end when git history is stable.

### Key findings

**RPI eval signal (#920):** Current eval suite lacks temporal dimension for RPI detection. All evals test single-turn congruence, not multi-turn strategy persistence under context change. #938 (cross-stage narrative continuity) is the natural surface point for RPI signals.

**Process constraints verified (#937):** All three #933 targets passed — cognitive load biases strategy selection, fatigue transitions to AD, per-strategy personality congruence holds. One pre-existing failure (proactive avoidance goals) unrelated to process constraints.

### Research docs updated

- `docs/research/2026-11-05-post-era6-regulation-and-identity.md` — added Stream 11 (process constraint verification + RPI eval signal)
- `docs/research/2026-11-11-process-constraint-regulation-findings.md` — added verification section with eval pass rates

## Immediate Next Step

`work continue` — next in queue is #938 (PipelineCoherenceEvalTest cross-stage narrative continuity). M/Med.

## Remaining Queue (Epic #841)

| # | Title | Scale | Complexity | Status |
|---|-------|-------|------------|--------|
| #938 | PipelineCoherenceEvalTest — cross-stage narrative continuity | M | Med | Active — next |
| #925 | CAPS consolidation coherence scenario | M | Med | Open |
| #926 | Unify test harnesses | M | Med | Open |
| #941 | Drive profile personality-specific situation reasoning | M | High | Open — last |

## Git State

- **neocortex:** on branch `issue-889-literature-javadoc-cherry` (6 commits ahead of main)
- **Local main:** synced with upstream/main (`325237ab`)
- 63 old feature branches are stamped (safe to clean up)
- `issue-937-process-constraint-eval` and `issue-937-clean` can be deleted (work on main)
