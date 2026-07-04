# Handoff — 2026-07-04

## What Changed

Closed #80 — DJL `HuggingFaceTokenizer` silently clamps `maxLength` to `modelMaxLength` (default 512). One-line fix: set `modelMaxLength` alongside `maxLength` in the tokenizer options map. Landed on main as `e3fb82f`. Garden entry `GE-20260704-987f9c` captures the gotcha.

## Immediate Next Step

#74 (reconciliation job) remains the next M-sized issue. Dense vector search (#70) makes it more pressing — collection recreation drops existing points. Run `/work` to start.

## What's Left

- #74 — Reconciliation job: reindex + orphan cleanup · M · Med
- #78 — Gate destructive dimension-mismatch recovery behind config flag · S · Low · blocked by #74
- #79 — Minor review findings batch · XS · Low
- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #74 | Reconciliation job | M | Med | Not blocking rollout but needed for dim migration |
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #78 | Dimension migration config gate | S | Low | Blocked by #74 |
| #79 | Minor review findings batch | XS | Low | Non-blocking cleanup |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |

## Key References

- Garden entry: `GE-20260704-987f9c` — DJL modelMaxLength silent clamping
- Garden entry: `GE-20260703-39256d` — Qdrant score_threshold semantics
