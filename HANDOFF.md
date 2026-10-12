# Session Handover — neocortex (slot 196)

**Date:** 2026-10-12
**Branch:** `main` (epic #513 landed)

## What was done

Epic #513 (cognitive pipeline completion) fully delivered and closed. 16 issues resolved across neocortex, examples, and blocks. 3 stale epics closed. Issue hygiene across 4 repos.

### Neocortex — pipeline work
- #506–#512: Epic #513 complete (inference wiring, pipeline tuning, trust interpretation)
- #515–#519: Config externalization — 44 constants moved to literature-grounded @ConfigMapping records
- #516: ConcernBasedSalienceStrategy — proper SPI for Klinger salience
- #517: ConflictInterpretation wired into trust computation
- Audit refactor: 3 bugs fixed, duplication eliminated, robustness improved
- CLAUDE.md updated with Pipeline Configuration section
- configureAppraisal() now passes mindMapStore (one-line fix for #444)

### Examples — wiring
- ManorConsolidationBeans updated: CognitiveDefaultsRegistry wired into RelationshipStagePhase (#118)
- 566 tests pass

### Blocks — cleanup
- Deleted stale social-jpa-common/ and social-jpa/ build artifacts (no source — migration already done)
- Closed #328 (migration done), #298 (8/9 children done), #274 (5/5 done), #333 (subsumed by neocortex#444)
- Transferred #309 → neocortex#552 (already implemented, closed)

### Soredium — issues filed
- #431: Slot-aware lifecycle (ctx.py doesn't support cross-repo)
- #437: Sweep steps iterate all slot repos instead of active only
- #438: archive_slot must check all repos before offering
- #439: Cross-session close verify fails
- #440: Forcing function scope too broad

### Garden — 3 entries captured
- GE-20261011-13dadc: EMA convergence ceiling gotcha
- GE-20261011-89d8b5: JSpecify @Nullable FQN gotcha
- GE-20261011-a0bf0a: Config-as-documentation technique

## What the next session must do

### 1. neocortex#444 — make CognitionCore self-wiring (HIGH PRIORITY)

**The problem:** CognitionCore uses imperative configure*() methods. Every application must call configureAppraisal(), configureGutFeeling(), configureSubThoughts() with the right params in the right order. If any is missed, that pipeline is silently dead.

**The fix:** Make CognitionCore a CDI bean (or use a builder with auto-discovery). @PostConstruct wires available participants automatically. Applications should never call configure*().

**Key file:** `cognition/src/main/java/.../core/CognitionCore.java`

**What exists:** configureAppraisal() already passes mindMapStore (fixed this session). The configure*() methods work — the issue is that they're imperative boilerplate that every consumer repeats.

**After this:** wacky-manor and any future app get full cognitive pipeline (appraisal, salience, gut feeling, sub-thoughts) by just injecting CognitionCore. No wiring code needed.

### 2. neocortex#520 — cognitive state dump endpoint

Diagnostic tooling for postmortems. Trace the full pipeline: seeded drives → adapted intensities → CAPS attractors → personality labels → rendered sections → LLM thinking.

Model after cognitive-observability module's existing CognitionInspectService.

### 3. examples#115 — run Layer 1+2+3 eval

After #444 lands, run the eval with GENERIC profile to measure the combined impact of all pipeline changes. The last eval was mean 3.57 — with reinforcement boost (#510), attractor differentiation (#511), concern salience (#508), and trust interpretation (#512), expect improvement.

### 4. examples#119 — Klinger concerns in wacky-manor

Depends on #444. Once CognitionCore self-wires, ConcernBasedSalienceStrategy activates automatically when salience is enabled. May need to enable salience in CognitionConfig for wacky-manor.

## Open issues by repo

### neocortex
| # | Title | Priority |
|---|-------|----------|
| 444 | Make CognitionCore self-wiring | High |
| 520 | Cognitive state dump endpoint | Medium |
| 385 | Scenario calibration questionnaire (standalone) | Low |

### examples
| # | Title | Priority |
|---|-------|----------|
| 115 | Close drive expression gap (eval) | High (after #444) |
| 118 | Wire drive adaptation (partial — ManorConsolidationBeans done) | Medium |
| 119 | Klinger concerns (depends on #444) | Medium |
| 117 | Unified disposition renderer design | Low |

## Test status (all green)
- neocortex cognition: 415 pass
- neocortex mindmap-intelligence: 524 pass
- neocortex caps-engine: 27 pass
- neocortex cognition-api: 73 pass
- examples wacky-manor: 566 pass
