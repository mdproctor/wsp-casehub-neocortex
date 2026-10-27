---
layout: post
title: "Two Kinds of Evidence"
date: 2026-10-27
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [inference-bayes, hypothesis-tracker, api-design]
---

# Two Kinds of Evidence

HypothesisTracker had a gap. It could handle one-shot scouting observations — you see a Gateway, you call `observe()`, the hypothesis weights shift toward Protoss strategies. Clean Bayesian update, exactly what you want for singular revelatory evidence.

But detectors and Drools markers aren't like that. They fire every tick, reporting the same state over and over. "I still see gateway units" shouldn't keep multiplying the probability — that evidence isn't new, it's a refresh. Call `observe()` sixty times with the same distribution and the weights converge to near-certainty, which is exactly wrong. The evidence hasn't gotten stronger. The detector is just confirming what it already said.

The fix is conceptually simple: separate evidence-setting from weight-updating. `setPerTickEvidence` pushes a distribution into every viable hypothesis's Bayes network and propagates beliefs internally, but never touches the inter-hypothesis weight distribution. The network knows about the evidence — marginals change, downstream variables update — but the hypothesis tracker doesn't treat it as new information for the purpose of discrimination.

`clearPerTickEvidence` handles the complement: when a Drools marker has no current output, the evidence retracts cleanly. And `marginalize` exposes per-hypothesis posteriors so the assessment layer can compute `P(archetype) ∝ weight × perTickLikelihood` — the hypothesis weight comes from scouting observations, the likelihood comes from the current detector state.

There's something satisfying about APIs where the hardest part is deciding what *not* to do. The Bayes infrastructure already handled everything — set evidence, propagate, query marginals. The gap was that HypothesisTracker coupled evidence injection with weight updating, and there was no way to inject without discriminating. Four thin methods, one conceptual separation.
