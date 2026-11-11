# HANDOFF — casehub-neocortex

## Last Session

Completed #933 (L/High) — applied process constraint technique from #905 to the wider eval suite. Closed as `376441c8`. Filed five follow-up issues (#937-#941) and reordered the queue by dependency chain. Revised the "Limitation That Wouldn't Limit" blog entry with #933's regulation applications. Added research doc.

### Issue completed

| # | Title | Scale | Outcome |
|---|-------|-------|---------|
| #933 | Apply process constraint technique to wider eval suite failures | L | Landed `376441c8` — cognitive load, fatigue, strategy differentiation constraints + drive description fallback |

### Key findings

**Process constraints generalize beyond capacity.** The technique from #905 (constraining reasoning procedure rather than describing limitations) works for emotion regulation, fatigue degradation, and personality-based strategy selection. Four interventions implemented in `EmotionRegulationGenerationPhase.buildUserMessage()`.

**DriveProfilePipelineTest root cause was simpler than expected.** The 12/12 failure was a missing description fallback in `CognitionObservationBuilder` (3-line fix), not a CAPS classification discrimination problem. The underlying overlap filtering architecture is sound — resting activation alone passes high-intensity drives, and the gaps for others are trivially small.

### Issues filed

| # | Title | Scale | Complexity | Queue position |
|---|-------|-------|------------|----------------|
| #937 | Verify process constraint effectiveness via LLM eval suite | S | Low | After #940 |
| #938 | PipelineCoherenceEvalTest — cross-stage narrative continuity | M | Med | After #939 |
| #939 | CAPS classifier empty-result fallback masks drive discrimination | S | Low | After #924 |
| #940 | DriveProfilePipelineTest fragile verbatim detection | XS | Low | After #920 |
| #941 | Drive profile personality-specific situation reasoning | M | High | End of queue |

### Artifacts

- Blog: `2026-11-11-mdp01-the-limitation-that-wouldnt-limit.md` — revised with #933 regulation applications
- Research: `docs/research/2026-11-11-process-constraint-regulation-findings.md` — technique generalization findings
- SVG: `blog/images/regulation-process-constraints.svg` — regulation pipeline constraint diagram

## Immediate Next Step

`work continue` — next in queue is #920 (Eval signal: RPI stale strategy persistence). S/Med.

## Remaining Queue (Epic #841)

| # | Title | Scale | Complexity | Status |
|---|-------|-------|------------|--------|
| #920 | Eval signal — RPI stale strategy persistence | S | Med | Active — next |
| #940 | DriveProfilePipelineTest fragile verbatim detection | XS | Low | Open |
| #937 | Verify process constraint effectiveness via LLM eval suite | S | Low | Open — needs `ANTHROPIC_API_KEY` |
| #924 | two-tier CoherenceJudge | ? | ? | Open |
| #939 | CAPS classifier empty-result fallback masks drive discrimination | S | Low | Open |
| #938 | PipelineCoherenceEvalTest — cross-stage narrative continuity | M | Med | Depends on #937 |
| #925 | CAPS consolidation coherence scenario | ? | ? | Open |
| #926 | unify test harnesses | ? | ? | Open |
| #941 | Drive profile personality-specific situation reasoning | M | High | Research — last |

## Key Files Modified This Session

- `cognition/.../EmotionRegulationGenerationPhase.java` — process constraints for load, fatigue, strategy
- `cognition/.../CognitionObservationBuilder.java` — 3-line drive description fallback
- `cognition/.../EmotionRegulationTickParticipant.java` — constructor reconciliation, WeightUpdateContext
- `cognition/.../CognitionCore.java` — constructor arity fix
- `caps-llm-classifier/.../CognitiveLoadStrategyEvalTest.java` — process constraint in inline prompt
- 3 new test files: load, fatigue, strategy constraint tests
