# Cognitive Review Triage — Verification at HEAD

**Date:** 2026-11-24
**Review commit:** c3230fd | **Verified at:** 107c043b (HEAD of cognitive-review-analysis)
**Review source:** `claude/magical-sagan-5e2uum/docs/research/2026-11-22-cognitive-review/REVIEW.md`

---

## Overview

The review contains 120+ findings across 9 sections. All were verified against current HEAD by reading the actual code paths. **Zero findings have been fully fixed since the review.** A handful are partially addressed. The vast majority remain valid.

| Section | Total | Still Valid | Partially Addressed | Fixed | Not Verifiable |
|---------|-------|------------|--------------------:|------:|---------------:|
| A — Wiring | 13 | 11 | 0 | 0 | 2 (agency-side) |
| B — CAPS | 17 | 12 | 2 | 0 | 0 |
| C — Affect | 21 | 14 | 4 | 0 | 0 |
| D — Personality | 19 | 18 | 1 | 0 | 0 |
| E — Higher cognition | 17 | 17 | 0 | 0 | 0 |
| F — Consolidation | 20 | 19 | 1 | 0 | 0 |
| **Total** | **107** | **91** | **8** | **0** | **2** |

Sections G (Evidence base), H (Direction), I (Recorded run data) are analysis/recommendations, not code findings.

---

## Categorisation

### By type

| Category | Count | Description |
|----------|------:|-------------|
| **genuine-bug** | 55 | Code does something wrong or harmful |
| **integration-gap** | 28 | Built but not wired into the production pipeline |
| **design-disagreement** | 14 | Reviewer questions a design choice; not necessarily wrong |
| **not-verifiable** | 2 | Agency-side code not in this repo |

### Corrections to the review

- **C16:** Threshold is `> 0` not `> 0.1` — normalization problem less severe than stated
- **C7:** Reclassified from genuine-bug to design-disagreement — polarity depends on eidos encoding
- **B8:** 7 of 9 output nodes are documented as intentionally predictor-only (coping outputs)
- **B12:** Disposition resolution now checks effectiveDefaults first, falls back to default only when unavailable
- **C21:** Layer 1 (experience search) is now agent-scoped; only Layer 2 (affect fallback) scans tenant-wide

---

## Priority groupings for issue creation

### P1: Unified pipeline composition

The meta-issue. Production (CognitionConfig.all()), tests (withAllSubsystems()), and wacky-manor (ManorCognitivePipelineBuilder) each assemble a different pipeline. Tests validate a configuration production never runs. Fixing this is prerequisite to everything else.

| Finding | Summary |
|---------|---------|
| A1 | CognitionConfig.all() leaves 11 subsystems off |
| A2 | Pipeline builder doesn't wire configureSearchBudget, configureCuriosity, etc. |
| A9 | RecurringThoughtPhase missing CDI scope — never discovered |
| A10 | Classpath profile loading fails inside jars |
| A11 | Missing orchestrator implementations in this repo |
| A13 | CognitionConfig is 27 positional booleans |

### P2: Per-agent state isolation

One CognitionCore shared by all agents with agent-specific state in instance fields. Must be resolved before any multi-agent testing is meaningful.

| Finding | Summary |
|---------|---------|
| A3 | Shared CognitionCore leaks lastAgentId, lastDescriptor, lastBriefing, etc. |
| C9 | CuriosityDrive and other drive sources share state across agents |
| D11 | Affect trajectories not agent-scoped |
| D19 | CognitiveMemoryRetriever has one shared mutable tick context |
| C19 | LLM session ids not tenant/subject scoped |
| E7 | Narrative partitions by tenant not agent |
| F3 | Cross-tenant leakage in attention path |

### P3: State corruption — bugs that would corrupt any run

These produce incorrect state that compounds over time. Must fix before any empirical measurement is valid.

| Finding | Summary |
|---------|---------|
| F1 | UUID cursor ordering skips memories on SQLite/JPA — **critical** |
| C1 | Stale appraisal re-bridged to mood/drives every tick |
| C2 | Mood additive deltas with no rate limit → pins at clamp |
| C3 | Decay timing: fresh signal immediately decayed after idle gap |
| C4 | Standing goal emotions added as delta every tick |
| C5 | CognitiveResourcePool hardcoded null — fatigue gate never fires |
| C6 | Coping drive modulations overwritten by put() |
| C8 | drives.tick runs twice per core tick — double smoothing |
| E4 | Mental-model confidence decay compounds (doesn't advance reference) |
| D7 | Recency decay captures Instant.now() once at startup — frozen |
| D13 | updateBase called every tick — invalidates cache, runs two full derivations |
| F2 | GoalAffect writes synthetic experience every pass, every goal |
| F12 | Uniform 30-day confidence decay, per-type half-life never read |
| D2 | Fear threshold inverted — anxious agents harder to frighten |

### P4: Affect pipeline correctness

Bugs in emotion mapping, regulation, and drive computation that produce wrong values but don't corrupt state cumulatively.

| Finding | Summary |
|---------|---------|
| C13 | Regulation triggers on JOY/PRIDE (no valence check) |
| C14 | EmotionMapper missing 6 emotions; INTERRUPTION intensity inverted |
| C15 | AlmaPadTable RELIEF dominance sign wrong (Gebhard 2005) |
| C17 | CognitiveLoadEstimator: drives().size() always 4, LOW unreachable |
| C11 | Appraisal weights and habituation config derived but never read |
| C12 | Regulation never changes what reaches mood or drives |
| C16 | Concern salience normalisation penalises short goals |

### P5: Higher cognition and consolidation wiring

Features built but not integrated or producing meaningful output.

| Finding | Summary |
|---------|---------|
| E1 | Mental-model/user-model/strategy LLM synthesis never fires (gate too strict) |
| E2 | Interaction quality uses agent's pre-interaction mood |
| E3 | configureTheoryOfMind never called in production |
| E8 | Memory hygiene: nothing evicted (composite always above threshold) |
| E10 | Goal tick results discarded; queryGoals returns all tenant goals |
| E11 | Regex JSON parsing breaks on ] in text, rejects +0.3 |
| F4 | SQLite LIMIT before trait filter; subgraph type/id confusion |
| F7 | Graduation cursor skip; actions/outcomes always pass |
| F9 | CuriosityRefreshPhase computes signals and discards them |
| F10 | Attention signals re-fire every pass (level-triggered) |
| F11 | Auto-merge at JW ≥ 0.9 merges similar but distinct entities |
| F15 | Active goals default to HOPE → never go dormant |
| F19 | Every paragraph becomes STATED 1.0 node; fuzzy name resolution errors |

### P6: CAPS effectiveness (pending measurement)

CAPS produces near-identical output across characters. The reviewer recommends "rebuild or retire" but this should wait until P1-P3 are resolved and the unified pipeline can be measured properly.

| Finding | Summary |
|---------|---------|
| B1 | Unipolar nodes at 0.5 background swamp situation input |
| B2 | Weight update is not multi-cue Rescorla-Wagner |
| B3 | Regulation discards updated weights — learning is a no-op |
| B5 | Distortions add positive constant regardless of sign |
| B6 | Convergence threshold too generous (variance 0.05) |
| B9 | ClassificationOutcomeEvaluator is roughly per-agent constant |
| B10 | CBR cache: case id from query not hit; fewer filter fields |
| B11 | RuleBasedSituationClassifier.classify() returns empty |
| B13 | Threshold multipliers × 0 = 0 |
| B14 | LlmSituationClassifier session reuse accumulates history |
| B17 | Tests don't constrain behaviour |

### Design disagreements (not issues — park for later)

| Finding | Summary |
|---------|---------|
| A12 | safeRun generic warning (observability preference) |
| B2 | Weight update variant (not textbook R-W) |
| B4 | Resting activations as post-hoc strength (design intent unclear) |
| B7 | "Attractor" terminology for feed-forward network |
| B15 | Precision tracking variant (not Pearce-Hall) |
| C7 | Drive polarity depends on eidos encoding |
| D3 | Fear from Sensing/Intuition (Jungian architecture constraint) |
| D5 | PersonalityWeights ineffective in single-domain queries |
| D8 | RetrievalModulator discards store relevance |
| D9 | DTW correlation normalisation |
| D12 | Null caller = admin access (intentional) |
| D17 | Effective personality dimensionality |
| E13 | Inner-life silence from last tick vs last user activity |
| F8 | Curiosity channels near-constant by construction |
| F13 | Information-gap score measures provenance/age |
| F18 | Per-pass consolidation cost |

---

## Recommended issue structure

Create **6 epics** matching P1-P6, with child issues for each finding or natural grouping of related findings. The epics should be ordered and labelled to reflect the dependency chain:

1. **P1 (Unified pipeline)** blocks everything — can't validate any fix without it
2. **P2 (Agent isolation)** blocks multi-agent testing
3. **P3 (State corruption)** blocks measurement
4. **P4 (Affect correctness)** can be done in parallel with P5
5. **P5 (Higher cognition wiring)** can be done in parallel with P4
6. **P6 (CAPS)** blocks on measurement results from P1-P3

Design disagreements don't need issues — they're documented here for reference and can be revisited after measurement.
