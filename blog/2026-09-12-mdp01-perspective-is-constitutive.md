---
layout: post
title: "Perspective Is Constitutive"
date: 2026-09-12
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [cognitive-index, social-cognition, perspectival, dtw, affect]
series: issue-287-social-cognition
---

# Perspective Is Constitutive

The cognitive-index module had a structural flaw hiding in plain sight. `CognitiveProfile.resolve()` would find an entity, compute its affect trajectory, and hand it back. `PerspectivalResolver` would separately merge an agent's overlay onto the same entity. These two operations ran independently — and the trajectory was computed on the *unmerged* node's PAD values.

If Alice sees Grandma with pleasure 0.9 and Bob sees her at -0.2, the trajectory should reflect that divergence. Instead, both agents got the same trajectory computed from the bare shared node. The overlay was cosmetic — applied after the derived computation that should have depended on it.

The fix inverts the pipeline order. Perspective is applied *before* trajectory computation, not after. PerspectivalResolver moves inside CognitiveProfile as a package-private collaborator instead of a standalone CDI bean. Memory queries get scoped by `withCallerPrincipalId()` so each agent sees only their own affect history. The entity knowledge record gains a `perceiver` field — null for the shared view, populated when looking through a specific agent's lens.

## Batched Comparison

The single-entity fix opened the door to the real question: how do N agents perceive the same entity differently? `CognitiveProfile.compare()` takes a set of agents and returns a map of perspectives, each fully resolved — overlaid, memory-scoped, trajectory-computed.

The implementation loads all overlay nodes in a single store query, partitions them by agent ID in memory, then runs the per-agent pipeline. One store hit regardless of agent count. Each agent gets their own EntityKnowledge with the correct perceiver.

`SocialComparison.compare()` is the analysis layer on top. Given the map of perspectives, it computes PAD-space Euclidean distances, signed per-dimension differences, and trajectory alignment via 3D cosine similarity across pleasure, arousal, and dominance slopes. Agents with incomplete PAD assessments (any null dimension) are excluded from distance metrics rather than coerced to zero — "no opinion" is not "neutral."

The canonical pair ordering in `AgentPair` tripped us up briefly. Signed differences need to follow the pair's internal ordering (`pair.a() - pair.b()`) regardless of which agent the caller passes first, or the sign flips depending on iteration order of an unordered map. A subtle one — the kind of bug that only appears with three or more agents and specific name orderings.

## Cross-Domain Correlation

The second piece addresses a different question: does stress at work correlate with tension at home? `DomainActivation` queries all entities within each subgraph, aggregates their affect memories into time-bucketed 3D PAD series, and runs Dynamic Time Warping to measure how similarly the emotional patterns evolve across domains.

I wrote a lightweight DTW operating on `double[][]` rather than reusing the CBR module's `DtwSimilarity`. Same algorithm, incompatible type interfaces — `DtwSimilarity` works with `FeatureValue` and `FeatureField`, while DomainActivation works with raw PAD doubles. The coupling cost wasn't worth the 60 lines of duplicated DP matrix code.

Privacy is structural. `DomainActivationQuery` requires a non-nullable `PrincipalId` — cross-agent affect comparison is literally not expressible through the API. Each agent can correlate their own domains; they can't peek at another agent's emotional patterns.

## The arousalSlope Gap

`AffectTrajectory` had slopes for pleasure and dominance but only *volatility* for arousal. That was fine when trajectory was a background metric, but 3D cosine similarity across slope vectors needs a slope in every dimension. The least-squares computation was already there for the other two — adding `arousalSlope` was mechanical. Seven construction sites to update across production and test code, all using named accessors, so the record field insertion was safe.
