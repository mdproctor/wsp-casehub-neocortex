---
layout: post
title: "Not Everything Breaks at Once"
date: 2026-11-09
entry_type: article
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive-architecture, personality, search-budget, literature-grounded, yerkes-dodson, task-complexity]
series: issue-839-search-budget-situational-strength
---

# Not Everything Breaks at Once

In [When Personality Disappears Under Pressure](/2026-11-09-mdp01-when-personality-disappears), I described how the search budget's extreme interaction layer makes personality *survive* at high arousal. A personality-specific peak controls when the inverted-U decline begins — anxious agents peak earlier, bold agents peak later. The decay rates and amplification rates are per-parameter. The peak itself is not.

That's one global threshold shared by depth, breadth, laterality, and convergence. The same arousal level triggers decline in creative association and focused search simultaneously.

The Yerkes-Dodson law says this is wrong.

## The Task-Complexity Effect

Yerkes and Dodson's original 1908 finding was not just "arousal hurts performance past a peak." It was that the peak position depends on task complexity. Simple tasks peak at higher arousal than complex ones. A mouse running a simple discrimination task performs best at high shock intensity. A mouse running a hard discrimination task degrades at moderate shock intensity. The inverted-U shifts left as complexity increases.

The search budget's four parameters represent four genuinely different cognitive operations:

**Laterality** — creative association, defocused attention, bridging distant concepts. This is the most complex operation. Martindale's (1999) work on creativity and cortical arousal showed that creative insight requires low cortical activation. High arousal narrows attention (Easterbrook 1959) and kills the lateral connections that make creative leaps possible. Laterality should peak earliest.

**Depth** — sustained multi-step reasoning, holding a chain of inferences. Complex, but with a structural scaffold — the chain has a direction. Conscientiousness protects it (Hockey's Compensatory Control Model: disciplined thinkers protect their primary task under stress). Depth should peak later than laterality.

**Breadth** — scanning multiple possibilities, cue utilisation. Moderate complexity. Easterbrook's narrowing hits breadth directly, but breadth is mechanically simpler than depth or laterality — you're surveying, not chaining. Open personalities sustain broader scanning longer.

**Convergence** — deciding to stop and commit. This is the simplest operation. It may even be *enhanced* by moderate stress — anxiety accelerates convergence (the "satisficing under pressure" effect). Convergence should peak latest.

A single threshold collapses this hierarchy. An agent under pressure loses creative association and focused commitment at the same arousal level. That doesn't match any empirical model of how cognition actually degrades.

## The Fix

![Uniform vs per-parameter peaks](images/uniform-vs-per-parameter-peaks.svg)

The left panel shows the old model: four curves sharing one peak. Past that threshold, everything declines together. The right panel shows the new model: laterality peaks and declines first, then breadth, then depth, then convergence. Each parameter has its own threshold.

The implementation adds four nullable `Double` fields to `ExtremeInteractionConfig`:

```java
public record ExtremeInteractionConfig(
        // ... existing decay and amplification rates ...
        Double depthPeak,
        Double breadthPeak,
        Double lateralityPeak,
        Double convergencePeak) {

    public double lateralityPeakOrDefault(double fallback) {
        return lateralityPeak != null ? lateralityPeak : fallback;
    }
    // ...
}
```

When null, each parameter falls back to the global `extremePeak` on `SearchBudgetConfig`. Backward compatible — existing agents with no per-parameter peaks behave identically.

Each `computeX()` method resolves its own peak:

```java
double peak = ext != null
    ? ext.breadthPeakOrDefault(config.extremePeak())
    : config.extremePeak();
double base = activationWithDecay(intensity, steepness, midpoint, decay, peak);
```

Fatigue accumulation and the `extremeActivation` flag still use the global peak. Those model composite motivational state, not per-parameter cognitive limits.

## Deriving Peaks from Personality

![Per-parameter peak derivation](images/per-parameter-peak-derivation.svg)

The global peak is already personality-derived:

```
globalPeak = 0.85 − (anxiousness − 0.5) × 0.3 − (emotionalLability − 0.5) × 0.2
```

The per-parameter peaks are offsets from this global peak, shaped by the personality traits most relevant to each cognitive operation:

| Parameter | Formula | Rationale |
|-----------|---------|-----------|
| lateralityPeak | globalPeak − 0.1 + openness × 0.08 | Creative association is most vulnerable; open personalities sustain it slightly longer |
| breadthPeak | globalPeak + openness × 0.05 | Scanning is simpler; open personalities are more resilient to cue narrowing |
| depthPeak | globalPeak − 0.05 + conscientiousness × 0.1 | Complex reasoning, but discipline protects the primary task |
| convergencePeak | globalPeak + conscientiousness × 0.08 | Focus is enhanced by discipline; converges later |

All clamped to [0.5, 0.95]. The range constraint ensures no per-parameter peak can fall below the global minimum or above the global maximum.

For a concrete example: an anxious worrier (anxiousness 0.8, emotional lability 0.7, conscientiousness 0.275) produces:
- Global peak: 0.72
- lateralityPeak: 0.64 — creative association starts declining well before anything else
- breadthPeak: 0.76 — scanning holds up slightly past the global peak
- depthPeak: 0.70 — close to global, the −0.05 offset nearly cancels the conscientiousness boost
- convergencePeak: 0.74 — can still commit decisions even as other faculties degrade

That ordering is the point. Under rising pressure, this agent loses creative leaps first, then depth of reasoning, and keeps the ability to commit and scan until later. A disciplined agent (conscientiousness 0.825) gets depthPeak 0.75 and convergencePeak 0.79 — discipline pushes both parameters higher, extending the window before they degrade.

## Why This Matters

The per-parameter peak distinction matters for anyone building cognitive agents, not just this codebase. The question is whether your agent's cognitive degradation under stress is *uniform* or *structured*.

Uniform degradation is easy to implement and easy to reason about, but it produces agents that lose every cognitive faculty simultaneously. An agent under pressure becomes generically worse — less creative, less deep, less focused, less decisive, all at the same rate. The result is a personality that fades to grey under load.

Structured degradation produces agents that compensate. Under rising arousal, creative association goes first — the agent stops making lateral leaps. But depth holds, convergence holds, scanning holds. As pressure increases further, depth starts to degrade while convergence remains. The agent narrows its cognitive repertoire rather than dimming uniformly. It becomes less creative but more decisive. Less exploratory but more focused.

That pattern — losing the complex faculties first while retaining the simple ones — is what the Yerkes-Dodson task-complexity effect predicts. It's what Hockey's Compensatory Control Model describes. And it's what makes cognitive agents feel like they're experiencing pressure rather than running a global discount on all their capabilities.

The practical cost was four nullable fields, four resolution methods, and four lines in the derivation engine. The structural cost was zero — the `activationWithDecay` function already takes `peak` as a parameter. Each compute method was already looking it up; we just changed *where* it looked.
