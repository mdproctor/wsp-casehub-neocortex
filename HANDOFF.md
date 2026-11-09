# HANDOFF — casehub-neocortex

## Last Session

Closed #839 branch and performed a semantic merge of slot 211 (cognitive exploration) into the canonical neocortex repo (`~/claude/casehub/neocortex`). Slot 196 had landed corpus-management-parsers, annotations, regulation predictor quality (#830), rich document ingestion (#787), and MCP annotations — all of which diverged from slot 211's cognitive exploration work (#825, #826, #596, #847, #848, #849, #839). Merge resolved 16 conflicts across 15 files with BUILD SUCCESS verified. Key merge points: CognitiveDefaults 20-field record (regulationDefaults + searchBudgetConfig + recurringThoughtConfig), CognitiveDerivationEngine (all derivation pathways), EmotionRegulation (canonical superset from Phase 4 calibration), corpus-management (canonical superset with annotations/relationships), research doc (all streams combined).

Also: fixed blog entry — removed "backwards compatibility" framing per user feedback (pre-release project, no compat concerns, refactor for clean API design).

## Immediate Next Step

`work continue 802` — Phase 3 structural extraction: extract Hortora-specific corpus code to dedicated `corpus-management-hortora` module. Scale L, Complexity High. Involves `Content` sealed hierarchy in `CorpusEntry`, moving `GardenMetadataExtractor`/`CorpusIndexService`, and extracting `ScoringStrategy` SPI. Fresh session recommended — different domain from merge work.

## State

- All repos synced: canonical, slot 211, workspace all at `4b1e132d`
- Issue #839 closed on GitHub
- Branch `issue-839-search-budget-situational-strength` stamped (both repos)
- Queue: #802 is active, followed by #788, #804, #810, #811, #812

## References

- `specs/issue-839-search-budget-situational-strength/2026-11-08-search-budget-situational-strength-design.md` — reviewed spec
- `specs/issue-839-search-budget-situational-strength/decisions.md` — 6 design decisions
- `plans/2026-11-08-search-budget-situational-strength.md` — implementation plan (3 batches, 6 tasks — all complete)
- `blog/2026-11-09-mdp01-when-personality-disappears.md` — revised diary entry (backwards compat framing removed)
- Deferred issues: #878 (per-parameter peaks), #879 (separate amplification threshold), #880 (shared fatigue substrate)

## Warnings

- `schema-generator` module has a pre-existing build failure (Jackson 3 `tools.jackson.databind.node.ObjectNode` not found) — unrelated to merge
- `cognitive-observability-spring` needs Jandex index from `cognitive-observability-core` — build ordering dependency, works with `mvn install` but fails with `mvn compile`
