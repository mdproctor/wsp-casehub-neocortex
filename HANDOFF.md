# Handoff — 2026-07-06

## What Changed

Closed #111 (already done — InMemoryQueryExpander existed on main since `3329c47`). Filed and delivered #112: `LlmQueryExpander`'s `enableIfMissing=true` caused unsatisfied `ChatModel` dependency in consumer `@QuarkusTest` even with `InMemoryQueryExpander` `@Alternative`. Root cause: Quarkus Arc validates injection points of ALL registered beans, not just the selected one. Fix: removed `enableIfMissing`, added `NoOpQueryExpander` `@DefaultBean` (pass-through), changed `ExpansionConfig.mode()` to `Optional<String>` (removed `@WithDefault("llm")`), added `ExpansionConfigValidator` startup warning. Design review (4 issues, all verified, $7.69). Garden entry GE-20260706-8488d8 (Arc `@Alternative` injection point validation gotcha). Landed on upstream main as `e13bd33`.

## Immediate Next Step

Pick from What's Next — engine adoption of `rag-expansion` is now unblocked (#112 closed). #63 (embedding evaluation) is next substantive neocortex work. #65 (Memori adapter) remains blocked on external dependency.

## What's Left

- #65 — Memori adapter (default backend) · XL · Med · blocked on external dependency

## What's Next

| # | Description | Scale | Complexity | Notes |
|---|-------------|-------|------------|-------|
| #63 | Run embedding evaluation + REPORT.md | M | Med | Scripts ready, models cached |
| #65 | Memori adapter | XL | Med | Blocked on external dependency |
| #106 | Semantic text field similarity in CbrSimilarityScorer | M | Med | Deferred from #82/#87 |
| #107 | Categorical similarity tables | M | Med | Deferred from #82/#87 |
| #108 | Per-field similarity function configuration | S | Low | Deferred from #82/#87 |
| #109 | Retrieval tracking analysis service | M | Med | New — depends on #105 (closed) |
| #110 | Retrieval tracking data retention policy | S | Low | New — depends on #105 (closed) |

## Key References

- Spec: `docs/specs/2026-07-06-query-expander-default-bean-design.md` (project)
- Design review: `~/adr/casehub-neocortex/query-expander-default-bean-20260706-083243/`
- Blog: `blog/2026-07-06-mdp02-the-alternative-that-didnt-replace-anything.md` (workspace)
- Garden: `GE-20260706-8488d8` — Quarkus Arc @Alternative does not suppress injection point validation of displaced beans
