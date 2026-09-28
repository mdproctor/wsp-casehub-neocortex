---
layout: post
title: "When Your Agent Judges Itself"
date: 2026-09-28
entry_type: note
subtype: diary
projects: [casehubio/neocortex]
tags: [occ, emotions, appraisal, cognitive, pride, shame, admiration, reproach]
---

I've been thinking about what makes an agent feel Pride versus Shame — and it turns out the answer depends on whose standards you're measuring against.

The OCC emotion model splits appraisal into three branches: events against goals (Hope, Fear, Satisfaction), actions against standards (Pride, Shame, Admiration, Reproach), and objects against attitudes (Love, Hate). We had the first branch — prospect-based emotions via `HeuristicGoalAppraisal`. An agent could feel Hope about an active goal or Distress about a blocked one. But it couldn't evaluate its own actions, or judge another agent's.

The interesting design question was: what are "standards" in a system where agents have goals and personality profiles but no explicit moral code? In OCC theory, praiseworthiness is about conformity to norms. We needed something concrete.

The answer we landed on: goal-derived standards with personality modulation. An action that advances a goal is praiseworthy; one that harms a goal is blameworthy. But how *easily* an agent feels Pride or Shame depends on its disposition — specifically the `ruleFollowing` and `socialOrient` axes from the cognitive profile.

This produces an asymmetry that matches the theory. A strict agent (high `selfStandardsStrictness`) has a shame threshold of `0.2 / 2.0 = 0.1` — small failures trigger Shame easily. But its pride threshold is `0.2 * 2.0 = 0.4` — only significant achievements register. A flexible agent is the mirror: hard to shame, easy to please. The personality modulates the emotional landscape without requiring a separate "standards" infrastructure.

The trigger design went through an iteration during the decision review. The original plan used `RelationshipRecorded` events for other-appraisal (Admiration/Reproach of another agent's actions). Claude caught a structural problem: `RelationshipProcessor` constructs events with `Map.of()` as metadata, stripping the `capability` and `result` fields needed for goal-relevance matching. Without those, you're left with free-text description parsing — which the mindmap-intelligence tier can't do (no LLM access). We switched to a single-trigger design where both self and other-appraisal paths fire from the same `ExperienceRecorded` event, giving both paths the full `Outcome` record.

Compound emotions fell out naturally. Once you know an action was praiseworthy (Pride) *and* the outcome was positive for a relevant goal (`goalRelevance > 0.3`), you can infer the prospect emotion (Joy/Satisfaction) from the same inputs. Gratification = Pride + inferred Joy. No cross-phase coordination, no emotion buffering, no event pipeline. The compound detection is four `switch` cases inside `HeuristicActionAppraisal`.

The `EmotionSource` enum gained `ATTRIBUTED` — distinguishing judgment of another's actions (Admiration, Reproach) from empathy for another's situation (Pity). The original design reused `EMPATHIC` for both, but they're fundamentally different OCC processes. A consumer asking "show me empathic responses" should not get Reproach in the results.

What this opens up: the compounds (Gratification, Remorse, Gratitude, Anger) are the bridge to social dynamics. Gratitude = Admiration + Joy = "your action helped me achieve my goal." Anger = Reproach + Distress = "your action harmed my goal." These are the emotional substrates of trust and conflict — and they're now derivable from the same goal-relevance signal that drives prospect-based emotions.
