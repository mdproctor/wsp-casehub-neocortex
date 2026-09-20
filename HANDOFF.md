# HANDOFF — casehub-neocortex

## Last Session

Three issues closed (#359, #372, #374), plus a cross-repo CDI fix (#373). Two new issues filed (#375, #376) from vocabulary audit discussion. Full build green (54 modules, all tests).

### What Happened

**#359 — Event recorder dedup + DelegatingCaseMemoryStore (S/Low)**
- Extracted `EventRecorderCore<E, R, F, S>` abstract base in `memory-core`
- Created `DelegatingCaseMemoryStore` in `memory-api`
- `memory-core` module documented in CLAUDE.md (was missing)

**#372 — CaseContextRetriever (S/Low)**
- New `CaseContextRetriever` in `rag-api` — multi-corpus retrieval with per-corpus error isolation, dedup, typed return
- 11 unit tests

**#374 — Spring module reactor ordering fix**
- `rag-spring`, `memory-spring`, `mindmap-spring` were listed before their Quarkus source modules — Jandex index not found on clean build. Reordered in parent POM.

**#375 — Filed: rename Case-prefixed SPIs + plan-type engine vocabulary (M/High)**
- Blocked by #376. Slot 199 created (neocortex + engine) but parked.

**#376 — Filed: platform vocabulary audit (design)**
- Systematic audit needed before any more renames. Current state: piecemeal naming decisions causing thrash and downstream breakage (PlanCbrCase → ResolvedCase broke life).
- Scope: audit public types across platform-api, neocortex, engine. Map downstream app usage. Produce a vocabulary spec with ownership rules.
- Output: vocabulary spec document, not code.

### Documentation Updated
- CLAUDE.md, ARC42STORIES §5, consumer guide, contributor guide — all synced

### Issues Closed
- #359, #372, #374

## Next

**#376 — Platform vocabulary audit (design, brainstorm)**
Must complete before #375 implementation. Produces a vocabulary spec covering:
- Every public type/SPI/string identifier across platform, neocortex, engine
- Downstream app impact matrix (SOC, AML, clinical, life, connectors)
- Unified ownership rules (what lives where and why)
- String → typed identity migration plan
- CBR terminology alignment (undo "Resolution" vocabulary, restore CBR literature terms)
- @Deprecated bridge policy for all future renames

**Then #375 — implementation in slot 199** (gated on #376 spec approval)

**Then #355 GA audit remainder:**
- #360 — extract cbr-algorithms from memory-api (M/Med)
- #361 — resolve mindmap→cognitive-index upward dependency (S/High)
- #362 — audit orphaned SPIs (S/Low)
- #363 — API consistency (M/Med) — #375/#376 covers highest-priority subset
- #364 — consumer-facing SPI Javadoc (M/Low)
- #365 — config consistency (M/Med)
- #366 — config reference documentation (S/Low)
- #367 — SPI completeness (L/Med)

## Cross-Module

- Engine AML tests should pass after rebuilding against latest neocortex
- casehubio/soc#57 can now refactor to use `CaseContextRetriever` (#372 landed)
- Slot 199 (neocortex + engine) parked — gated on #376 vocabulary spec
