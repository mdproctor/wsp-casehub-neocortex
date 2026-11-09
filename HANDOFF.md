# HANDOFF — casehub-neocortex

## Last Session

Completed #879 (Search budget: separate amplification threshold). Added nullable `amplificationThreshold` field to `ExtremeInteractionConfig` so the onset of personality-scaling (drive modulation amplification) can diverge from the onset of performance-decline (per-parameter peaks / Yerkes-Dodson). Derived from conscientiousness in `CognitiveDerivationEngine` — higher conscientiousness lowers the threshold, meaning personality expression kicks in earlier under pressure.

Also landed #878 (per-parameter extreme peaks) which was done in a prior session but not yet pushed with implementation code. Both landed on main and pushed: #878 as `7f2010f9`, #879 as `d6812e91`. Blog `2026-11-09-mdp04-not-everything-breaks-at-once.md` revised with new section on amplification threshold divergence, pushed as `8f2776c4`.

## Queue Housekeeping

#878 and #879 are both closed on GitHub but still unchecked in `.queue`. The `plan_manager.py advance` command didn't check them off because there was no active branch when advance was called. The next session should check these off — either find the right plan_manager command or update the queue manually.

## Immediate Next Step

`work start 880` — #880 (Search budget: shared fatigue substrate with regulation fatigue). Continues the search budget extreme interaction series.

## Remaining Queue (Epic #841)

| # | Title | Scale | Complexity | Status |
|---|-------|-------|------------|--------|
| #878 | Search budget per-parameter extreme peaks | S | Med | Done, unchecked in queue |
| #879 | Search budget separate amplification threshold | S | Med | Done, unchecked in queue |
| #880 | Search budget shared fatigue substrate | S | Med | Open — NEXT |
| #890 | Intelligence capacity: learning rate modulation | S | Med | Open |
| #891 | Intelligence capacity: convergence ceiling | S | Med | Open |
| #892 | Intelligence capacity: appraisal frustration pathway | S | Med | Open |
| #894 | Eval pipeline coherence trace chain validation | M | High | Open |
| #905 | Run and calibrate exploration + capacity eval suite | L | High | Open |

## Key Files Modified This Session

- `cognitive-api/.../ExtremeInteractionConfig.java` — added `amplificationThreshold` field (13th parameter), `amplificationThresholdOrDefault()`, `withAmplificationThreshold()`
- `cognition/.../SearchBudgetTickParticipant.java` — each compute method resolves separate `ampThreshold` for `modulationScale()`
- `cognitive-index/.../CognitiveDerivationEngine.java` — derives `amplificationThreshold = clampPeak(extremePeak - conscientiousness * 0.1)`
- Tests added in all three modules (10 new tests total)
