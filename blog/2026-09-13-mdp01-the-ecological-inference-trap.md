---
layout: post
title: "The Ecological Inference Trap"
date: 2026-09-13
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive-index, cross-domain, dtw, mood, experience, significance-testing]
series: issue-324-cognitive-extensions
---

# The Ecological Inference Trap

DomainActivation had a clean design: find entities in a subgraph, collect their affect memories, bucket them into PAD time series, DTW the pairs. Cross-domain affect correlation. It worked because affect memories are per-entity, entities live in subgraphs, and the partitioning falls out naturally.

Extending this to mood broke that symmetry. Mood is agent-global — a single emotional state that isn't scoped to any particular domain. An agent feeling stressed doesn't tag their stress as "work stress" or "family stress." It's just stress. The initial design treated this as fine: correlate the global mood signal against each subgraph's affect trajectory using the same DTW machinery.

The decision review caught the problem. If one agent-global signal gets DTW'd against N subgraph trajectories simultaneously, any temporal structure in the mood (which all mood has — it changes gradually) will correlate with all concurrently active subgraphs. The statistical term is ecological inference — attributing group-level correlations to individual-level causation. An agent who's generally improving will show "strong" mood-affect correlation with every subgraph they're engaged with, not because mood tracks any specific domain, but because everything is trending together.

The fix is optional context attribution. `MoodState` gains `activeContextIds` — a set of opaque identifiers representing what the agent was engaged with when the mood was captured. When present, DomainActivation partitions the mood data points so each snapshot only contributes to subgraphs it was tagged with. When absent, it falls back to agent-global correlation with a quality flag (`contextAttributedCount` / `totalMoodCount`) so consumers know the data is unpartitioned.

Experience events hit a different wall. They're discrete — an Observation, an Action, an Outcome at a point in time. DTW operates on continuous time series. The issue description had already flagged this: "correlating discrete events requires different techniques." We built event-triggered affect windows instead. For each experience event at time T, compute the mean PAD before and after within a configurable window, take the delta. This directly measures "did affect shift when this happened?" rather than "do these signals move together?" Per-type breakdown (observation vs outcome) and bootstrap confidence intervals give the consumer directional, interpretable results.

The significance testing was the subtler trap. The natural approach for DTW significance is permutation testing — shuffle one series, recompute DTW 200 times, see how often the permuted similarity matches the observed. But shuffling a time series destroys its autocorrelation. Real mood and affect are gradual processes — adjacent values are similar by nature. A permuted series is random noise. The null distribution becomes trivially easy to beat, producing systematically low p-values. We use circular shift surrogates instead — rotate the series by a random offset, preserving temporal structure while destroying alignment. Same computational cost, correct null hypothesis.

What makes this extension interesting architecturally is the extensibility pattern. Rather than adding `moodCorrelations` and `experienceCorrelations` as named fields on `DomainActivationResult`, both sit behind a `Map<MemoryDomain, ...>` keyed by the memory domain constant. Adding relationship or reflection correlation later requires no signature changes — just a new domain handler in `correlate()`. The query uses `withContextDomains(Set<MemoryDomain>)` with an empty default, so existing callers see no change.

The per-entity affect model and the agent-global context model coexist cleanly. Affect correlation stays entity-scoped — it's the right model for per-domain emotional dynamics. Mood and experience stay agent-scoped — they're the right model for cross-domain context signals. The ecological inference guard ensures the agent-global signals don't produce spurious correlations, and the event-triggered windows avoid forcing discrete events into a continuous framework they don't fit.
