---
layout: post
title: "The Data You Don't Have"
date: 2026-08-20
entry_type: note
subtype: diary
projects: [casehub-neocortex]
tags: [ml, strategy-classifier, onnx, class-imbalance, data-pipeline]
series: issue-202-retrain-strategy-classifier
---

The strategy classifier had three ONNX models trained on synthetic data. The synthetic training exposed the real problem: class imbalance so severe that the model couldn't learn tail archetypes at all. TECH_RUSH had 4 training samples. MUTA_HARASS had 33. ROACH_RUSH had 2,112. The 74% top-1 accuracy was an illusion inflated by one dominant class.

The obvious fix — retrain on real data — hit a harder question immediately: which real data? SC2EGSet was already extracted in the repo, but it inherits the same imbalance because ROACH_RUSH genuinely is the most common Zerg strategy in competitive play. More data from the same distribution doesn't fix a distribution problem.

Three sources emerged from a search: SC2EGSet (17,930 esports replays, already extracted), MSC (36,000 replays, never downloaded), and Spawning Tool (the largest collection of pro replays with labelled build orders). The key insight was targeted harvesting — searching Spawning Tool specifically for replay packs rich in underrepresented archetypes rather than bulk-downloading everything and hoping the tail classes show up.

All three sources use different formats. SC2EGSet provides pre-extracted JSON game states. MSC stores per-timestep sparse feature matrices. Spawning Tool has raw `.SC2Replay` files parsed by the `spawningtool` library. The design decision was unified labelling — thin adapters per source that normalize to a common build-order format (`[{type, name, minute}]`), then one rule-based labeller for everything. Consistent labels across sources matter more than leveraging each source's native classification.

The consolidation rule is 50 training samples minimum per archetype. Below that, focal loss and class weighting can't compensate — the CNN memorizes instead of generalizing. Archetypes that fall below the threshold merge into their nearest parent: TECH_RUSH into RUSH, HYDRA_PUSH into MACRO_ECONOMY. The consolidation is data-driven — applied after all sources are ingested, not predetermined.

The Spawning Tool adapter is done and tested. The merge-and-consolidation pipeline is done and tested. The MSC adapter is blocked — Google Drive rate-limited the download. The actual training run waits on data: a manual MSC download and some targeted Spawning Tool replay pack downloads for the tail archetypes. The pipeline code is ready; the data is not.
