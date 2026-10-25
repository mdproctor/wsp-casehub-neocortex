# Hypothesis Tracking for Situational Awareness — Prior Art and Position

**Issue:** casehubio/neocortex#692
**Date:** 2026-10-25

## What we're building

A composable situational awareness harness with five layers:

1. **Observation** — raw signals arriving over time
2. **Inference** — BJT networks computing local probabilities from observations
3. **Composition** — multiple inference models wired into a DAG (#674, done)
4. **Hypothesis tracking** — competing explanations weighted and eliminated as evidence accumulates (#692)
5. **Decision** — influence diagrams choosing optimal actions given the current hypothesis state (#650, done)

Each layer is a domain-neutral primitive in the `inference-bayes` module. SC2 is the proving ground — fast feedback loop, measurable outcomes, well-catalogued strategy space — but the architecture is designed for any domain requiring observation → interpretation → decision under uncertainty. CaseHub case classification, fault diagnosis, and medical differential diagnosis are target applications of the same harness.

The hypothesis tracker (#692) is the missing layer. It maintains a weighted set of competing explanations (opponent strategies, fault modes, diagnoses), delegates inference to composed BJT networks per hypothesis, updates weights as observations arrive, and closes paths when evidence eliminates them.

---

## Prior art

### Synnaeve & Bessière — Bayesian Plan Recognition in StarCraft (2011)

The foundational work in this space. Synnaeve and Bessière built a Bayesian model that computes a probability distribution over opponent build trees from partial observations in StarCraft: Brood War. Parameters were learned from replay datasets using semi-supervised learning (expectation-maximisation over unlabelled replays).

**How it works:** The model represents each possible opponent strategy as a build tree — a sequence of technology and unit production choices. Observations (scouted buildings and units) update the posterior distribution over these trees. The model handles partial observability naturally — you don't need to see everything, just enough to shift the distribution.

**Results:** Strong prediction accuracy early in the game from limited scouting information. The model could identify the opponent's strategy well before it was fully executed, giving time to react.

**What they got right:** Using Bayesian inference for strategy prediction under partial observability. Learning parameters from replays rather than hand-coding. Treating uncertainty as a first-class concern.

**Limitation:** A single monolithic Bayesian network. The strategy prediction, observation model, and decision-making are all baked into one structure. Changing the strategy space or the observation model means rebuilding the network.

> Synnaeve, G., & Bessière, P. (2011). A Bayesian Model for Plan Recognition in RTS Games Applied to StarCraft. *AIIDE*.

### Synnaeve & Bessière — Multiscale Bayesian Modeling (2016)

The follow-up work extends the approach to three abstraction levels: micro-management (unit control), tactics (army positioning), and strategy (economy, technology, production). Each level uses its own Bayesian model, with probability distributions on shared variables connecting models across levels.

**How it works:** The key insight is "vertical continuity" — distributions from the strategy model feed into the tactics model, which feeds into the micro model. This is compositional in spirit. They also demonstrate "horizontal continuity" — sequential updates within each level as the game progresses.

**Similarity to our approach:** This is the closest existing work to our composition layer (#674). Their inter-level variable sharing is analogous to our posterior injection between composed networks. The three-level hierarchy maps naturally to a three-slot composition DAG.

**Difference:** Their composition is implicit — shared variables in a hand-wired hierarchy. Ours is explicit — named slots, directed links with configurable transfer modes (POSTERIOR/MAP), and runtime variant swapping. Their model is a single integrated system; ours is a set of composable primitives that can be wired differently for different domains.

> Synnaeve, G., & Bessière, P. (2016). Multiscale Bayesian Modeling for RTS Games: An Application to StarCraft AI. *IEEE Transactions on Computational Intelligence and AI in Games*, 8(4), 338–350.

### AlphaStar — Deep RL at Grandmaster Level (2019)

DeepMind's AlphaStar achieved Grandmaster-level play in StarCraft II using multi-agent reinforcement learning. The architecture uses a transformer over units, deep LSTM core, auto-regressive policy head, and a league-based training system where multiple agents train competitively to prevent strategy collapse.

**How it works:** Imitation learning from human replays produces an initial policy. Self-play reinforcement learning refines it. A "league" of diverse agents prevents overfitting to any single opponent style. A latent variable z conditions the policy and encodes the distribution of opening strategies from human games.

**What it achieves:** Superhuman play. AlphaStar beat professional players across all three races. The league training produces agents that can handle diverse strategies.

**Fundamental difference from our approach:** AlphaStar is pure System 1 — end-to-end pattern matching from game state to actions. It doesn't "know" the opponent is rushing; it doesn't maintain hypotheses; it can't explain its reasoning. The latent variable z captures strategy diversity statistically, not as an explicit hypothesis set.

**Limitations relevant to us:**
- **No interpretability** — you can't ask AlphaStar "what do you think the opponent is doing?" It doesn't have an answer. Our hypothesis tracker can report "73% rush, 20% expand, 7% tech" with the evidence chain for each.
- **Brittle to novelty** — trained on the existing strategy space. A genuinely novel strategy not in the training distribution can break it. Bayesian models degrade gracefully — an unexpected observation shifts the posterior toward uncertainty rather than producing confidently wrong answers.
- **Requires massive compute** — 16 TPUs training for 44 days. A mid-size studio would need $3-8M and 18-36 months to replicate. Our BJT approach runs on a laptop.
- **No transfer** — the trained model is specific to one game version. Balance patches require retraining. Our composable primitives transfer across domains by swapping the network definitions, not retraining from scratch.

> Vinyals, O., et al. (2019). Grandmaster level in StarCraft II using multi-agent reinforcement learning. *Nature*, 575, 350–354.

### Kleiman-Weiner et al. — Non-parametric Bayesian Inference of Strategies

Addresses the problem of strategy spaces that are too large to enumerate. Uses non-parametric Bayesian models (Dirichlet process mixtures) to infer strategies in repeated games without fixing the number of possible strategies in advance.

**Relevance:** If our hypothesis tracker needs to handle open-ended strategy spaces — where the opponent might do something not in the predefined set — non-parametric methods offer a path. For the initial implementation, a fixed hypothesis set is sufficient. This is a future extension if the fixed set proves too limiting.

> Kleiman-Weiner, M., et al. (2018). Non-parametric Bayesian Inference of Strategies in Repeated Games. *Computational Brain & Behavior*.

### Bayesian Inverse Games (2025)

Argues that maximum likelihood (point estimate) methods for opponent modeling are insufficient — you need full posterior uncertainty quantification to avoid overconfident decisions.

**Relevance:** Validates our design choice of POSTERIOR as the default transfer mode in the composition layer. MAP (point estimate) is available when appropriate, but full posterior distribution is the default because it preserves uncertainty through the inference chain.

> Inga, J., et al. (2025). Bayesian Inverse Games with High-Dimensional Multi-Modal Observations. *arXiv:2601.00696*.

### Survey: Opponent Modeling in Adversarial Domains (JAIR)

Comprehensive survey covering opponent modeling approaches across games, security, and autonomous systems. Identifies two main paradigms: direct behavior prediction (map observations to actions) and classification-then-prediction (classify opponent type, then predict based on type).

**Relevance:** Our hypothesis tracker is the classification-then-prediction paradigm — classify the opponent's strategy (hypothesis), then use that classification to drive decisions. The survey notes this approach is more interpretable and transferable than direct prediction, at the cost of requiring a predefined strategy taxonomy.

> Albrecht, S. V., & Stone, P. A Survey on Opponent Modeling in Adversarial Domains. *Journal of Artificial Intelligence Research*.

---

## How we compare

| Dimension | Synnaeve (2011/2016) | AlphaStar (2019) | Our approach |
|-----------|---------------------|------------------|-------------|
| **Inference method** | Single/hierarchical Bayesian network | End-to-end deep RL | Composable BJT networks + hypothesis tracker |
| **Strategy representation** | Build tree distribution | Latent variable z | Explicit hypothesis set with weighted paths |
| **Composability** | Hand-wired hierarchy | Monolithic neural network | Named slots, directed links, runtime variant swap |
| **Interpretability** | Posterior over build trees (readable) | Black box | Full hypothesis weights + evidence chain |
| **Adaptability** | Retrain parameters from replays | Retrain entire model ($M+) | Swap network definitions, add/remove hypotheses |
| **Novelty handling** | Degrades gracefully (shifts to uniform) | Can fail confidently | Degrades gracefully + extensible hypothesis set |
| **Compute requirement** | Laptop | 16 TPUs, 44 days | Laptop |
| **Domain transfer** | SC1-specific | SC2-specific | Domain-neutral primitives |
| **Multi-level reasoning** | Three-level hierarchy (2016) | Single level (flat state→action) | Composition DAG (arbitrary depth) |

---

## What's genuinely new in our approach

1. **Composable inference primitives.** Prior work uses monolithic models — one network per domain, rebuilt from scratch for each application. Our composition layer (#674) lets you wire domain-specific networks into arbitrary DAGs with posterior or MAP transfer between them. The same primitives compose differently for SC2, CaseHub, or fault diagnosis.

2. **Runtime context selection.** No prior work supports swapping sub-models at runtime without rebuilding the composition. Our slot variants let you swap the scouting model for a different matchup while preserving calibrated state in non-swapped networks. This is critical for domains where the interpretation model depends on context (different matchup, different patient history, different system configuration).

3. **Hypothesis tracking as a separate layer.** Synnaeve's work blends strategy prediction into the Bayesian network itself. AlphaStar has no explicit strategy prediction. Our design separates the hypothesis tracking from the inference — the tracker maintains the strategic picture, the BJT networks do the local inference, and the composition layer handles the wiring. Each is independently testable and replaceable.

4. **Domain-neutral reference architecture.** The five-layer harness (observation → inference → composition → hypothesis tracking → decision) is designed to transfer across domains. SC2 exercises all five layers with fast feedback. CaseHub uses the same architecture with different observation sources and hypothesis spaces.

---

## What we hope to achieve

**Short term:** A hypothesis tracker that runs on top of the composition layer, demonstrating strategy prediction in SC2 using replay data for validation. The tracker should report interpretable hypothesis weights ("73% rush") that a human player would recognise as reasonable reads.

**Medium term:** The same architecture applied to CaseHub — case type classification from evidence streams. A case arrives with initial observations; the hypothesis tracker maintains competing case type hypotheses (fraud, compliance, routine); as evidence accumulates through the case lifecycle, paths are eliminated and confidence in the remaining hypotheses rises.

**Long term:** A reusable situational awareness harness that any domain can plug into. Define your observation model, your hypothesis space, and your decision criteria. The harness handles inference, composition, tracking, and decision-making. The gap between "I have observations and I need decisions" and "I have a working probabilistic reasoning system" shrinks from months of custom engineering to wiring up existing primitives.

**Validation approach:** SC2 replays provide ground truth — the replay contains the full game state including the opponent's actual strategy. We can compare the tracker's hypothesis weights at each point in the game against what the opponent was actually doing. Prediction accuracy, time-to-correct-read, and calibration (does "73% rush" mean rush 73% of the time?) are measurable metrics.

---

## References

- [Synnaeve & Bessière (2011) — Bayesian Plan Recognition in StarCraft](https://cdn.aaai.org/ojs/12429/12429-52-15957-1-2-20201228.pdf)
- [Synnaeve & Bessière (2011) — Opening Prediction in RTS Games](https://ieeexplore.ieee.org/document/6032018/)
- [Synnaeve & Bessière (2016) — Multiscale Bayesian Modeling](https://ieeexplore.ieee.org/document/7293159/)
- [AlphaStar — Grandmaster Level in StarCraft II (Nature, 2019)](https://www.nature.com/articles/s41586-019-1724-z)
- [AlphaStar Blog Post — DeepMind](https://deepmind.google/blog/alphastar-grandmaster-level-in-starcraft-ii-using-multi-agent-reinforcement-learning/)
- [Kleiman-Weiner — Non-parametric Bayesian Inference of Strategies](https://compminds.uw.edu/pdfs/kleiman2018non.pdf)
- [Bayesian Inverse Games (2025)](https://arxiv.org/pdf/2601.00696)
- [Survey on Opponent Modeling in Adversarial Domains (JAIR)](https://www.jair.org/index.php/jair/article/download/12889/26762/29406)
- [Bayesian Programming for Multi-Player Video Games](https://www.researchgate.net/publication/278641976_Bayesian_Programming_and_Learning_for_Multi-Player_Video_Games_Application_to_RTS_AI)
