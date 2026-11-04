# HANDOFF — casehub-neocortex

## Last Session

Completed **#801** — remediated 3 API-layer leaks in corpus-management-api: moved CorpusType constants to `BuiltInCorpusTypes` in impl (L2), moved `InteractionContext/InteractionType/ActivityType` from API to impl (L3), added `embeddingVector` field to `CorpusQuery` with withers and factories (L5). All IntelliJ-driven refactoring. 133 tests + 11 example tests pass. Branch landed, issue closed. Scaffolded feature branches for all 7 remaining epic issues.

## Immediate Next Step

Pick up **#787** (Rich document ingestion — PDFs, Word, images). Requires brainstorming the `Content` sealed hierarchy from audit L1 — `CorpusEntry.body` is currently `String`, blocking non-text corpora. Branch `issue-787-rich-document-ingestion` exists.

## References

- `specs/issue-801-remediate-corpus-api-leaks/` — design spec + decisions for #801
- `plans/2026-11-04-corpus-api-remediation.md` — implementation plan for #801
- `docs/specs/2026-11-04-corpus-domain-abstraction-audit.md` — audit (L1-L13)
- `.plan` — queue: #787, #802, #788, #804, #810, #811, #812
