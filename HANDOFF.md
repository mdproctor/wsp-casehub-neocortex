# Handoff — 2026-07-07

## What Changed

Closed #107 (categorical similarity tables) and #108 (per-field similarity function configuration). New `SimilaritySpec` sealed interface — pure data records (`CategoricalTable`, `GaussianDecay`, `StepDecay`, `ExponentialDecay`) that attach optional similarity configuration to `FeatureField.Categorical` and `FeatureField.Numeric`. `FeatureField` itself sealed with `permits`. `CbrSimilarityScorer` refactored to three-level precedence: caller override → field spec → type default. All dispatch sites (`CbrQueryTranslator`, `CbrCollectionManager`, `QdrantCbrCaseMemoryStore`) migrated to exhaustive `switch`. 964 tests pass, full build green. Landed as `a30110f` on both `origin/main` and `upstream/main`.

## Immediate Next Step

Pick next work item from What's Next — `#109` (retrieval tracking analysis) and `#110` (retention policy) are unblocked now that #105 landed.

## Cross-Module

**We're blocking:**
- `Hortora/engine` — needs the new neocortex SNAPSHOT (`0.2-SNAPSHOT`) to pick up the SimilaritySpec + sealed FeatureField changes. Their CBR schemas will need updating if they use `FeatureField` in switch expressions.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |
| #109 | Retrieval tracking analysis service | M | Med | Unblocked (#105 closed) |
| #110 | Retrieval tracking data retention policy | S | Low | Unblocked (#105 closed) |

## Key References

- Spec: `docs/specs/2026-07-07-cbr-similarity-functions-design.md`
- Blog: `blog/2026-07-07-mdp01-why-records-cant-carry-behaviour.md`
