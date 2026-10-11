# Goals, Motivations, and Affinity: A Taxonomy for Cognitive Agents

**Type:** Research & Design Direction
**Date:** 2026-10-11
**Status:** Research complete, model extension proposed
**Tracks:** casehubio/neocortex#529 (findings), future issue (implementation)

---

## 1. Problem Statement

The neocortex cognitive model extracts and represents goals from biographical text, but lacks a grounded taxonomy for classifying them. The current model uses an ad-hoc 3-tier system (thematic/strategic/tactical) and a Maslow-derived `goal_need_tier` (SAFETY/TASKS/SOCIAL/SELF_EXPRESSION/UNDERSTANDING). Empirical analysis of a 138-goal corpus extracted from a Frida Kahlo biography revealed:

- **58 thematic goals** — too many. Many are the same life theme re-extracted per passage in different words.
- **No content classification** — "build emotional resilience" and "carry pregnancy to term" are structurally identical (both thematic) despite being fundamentally different kinds of goals.
- **No motivation typing** — goals exist in isolation from what drives them.
- **Over-inference without accountability** — the LLM projects plausible goals not directly stated in the text, which is valuable but needs classification, not rejection.

Beyond biographical agents, synthetic cognitive agents face a deeper problem: disposition profiles define *how* an agent processes but not *what* it cares about. A high-mastery agent with no content seeds is hollow — mastery of what?

## 2. Literature Review

### 2.1 Talevich, Read, Walsh, Iyer & Chopra (2017) — Comprehensive Taxonomy of Human Motives

**Publication:** "Toward a comprehensive taxonomy of human motives", *PLOS ONE* 12(2): e0172279. Open access. 217 citations.

**Methodology:** 161 motive statements gleaned from motivation literature (McDougall 1908 to present). 489 participants performed card-sort tasks, grouping motives by perceived similarity. Hierarchical cluster analysis (Ward's method) on the co-occurrence matrix produced a 5-level hierarchy with 44 concrete clusters. Data available at OSF: https://osf.io/4m3w4/

**Key structural finding:** Three superordinate clusters — **Meaning, Communion, Agency** — rather than the expected two-factor Agency/Communion split (Bakan 1966). Meaning (morality, religion, self-actualisation) emerged as a distinct third factor.

**Applied AI relevance:** A 2010 companion paper (Read, Walsh & Talevich, IVA Conference) explicitly framed this taxonomy as "a principled basis for the motives of intelligent agents."

#### Full Hierarchy

**Level Z — 3 superordinate clusters (life orientation)**

| Code | Label |
|------|-------|
| Z1 | Meaning |
| Z2 | Communion |
| Z3 | Agency |

**Level Y — 9 domain clusters (content classification)**

| Code | Label | Parent |
|------|-------|--------|
| Y1 | Morality & Virtue | Meaning |
| Y2 | Religion & Spirituality | Meaning |
| Y3 | Self-Actualisation | Meaning |
| Y4 | Avoidance Motives | Communion |
| Y5 | Social Relating | Communion |
| Y6 | Health | Communion |
| Y7 | Family | Communion |
| Y8 | Mastery & Competence | Agency |
| Y9 | Financial & Occupational Success | Agency |

**Level X — 14 subdomain clusters**

| Code | Label | Parent |
|------|-------|--------|
| X1 | Social Values & Morals | Y1 |
| X2 | Help Others & Highly Regarded | Y1 |
| X3 | Religion & Spirituality | Y2 |
| X4 | Self-Fulfilment | Y3 |
| X5 | Openness to Experience | Y3 |
| X6 | Avoid Harm/Stress/Rejection/Conflict | Y4 |
| X7 | Avoid Hassles | Y4 |
| X8 | Security & Belonging | Y5 |
| X9 | Power | Y5 |
| X10 | Health | Y6 |
| X11 | Family | Y7 |
| X12 | Ambition & Ability | Y8 |
| X13 | Intellectual Competence | Y8 |
| X14 | Financial & Occupational Success | Y9 |

**Level W — 25 named goal types**

| Code | Label | Parent |
|------|-------|--------|
| W1 | Social Values | X1 |
| W2 | Personal Morals | X1 |
| W3 | Help Others | X2 |
| W4 | Highly Regarded | X2 |
| W5 | Religion & Spirituality | X3 |
| W6 | Wisdom & Serenity | X4 |
| W7 | Self-knowledge & Happiness | X4 |
| W8 | Appreciating Beauty | X5 |
| W9 | Exploration & Passions | X5 |
| W10 | Enjoy Life | X5 |
| W11 | Avoid Stress/Harm/Rejection/Conflict | X6 |
| W12 | Avoid Hassles | X7 |
| W13 | Relate & Belong | X8 |
| W14 | Intimacy | X8 |
| W15 | Stability | X8 |
| W16 | Better than/Control Others | X9 |
| W17 | Leadership | X9 |
| W18 | Health | X10 |
| W19 | Family | X11 |
| W20 | Achievement | X12 |
| W21 | Self-Efficacy | X12 |
| W22 | Practical Competence | X12 |
| W23 | Intellectual Competence | X13 |
| W24 | Finances | X14 |
| W25 | Occupational Success | X14 |

**Level V — 44 concrete motive clusters (161 individual motives)**

Selected examples by superordinate:

- **Meaning:** V8 Wisdom & Serenity (harmony, higher meaning, wisdom), V11 Appreciating Beauty (fine design, arts, creativity, natural beauty), V12 Exploration (risk-taking, curiosity, uniqueness, flexibility), V13 Pursue Ideals & Passions
- **Communion:** V22 Social Life & Friendship (social groups, close friends, people to rely on), V25 Emotional Intimacy (emotional closeness, being in love), V27 Stability & Safety (feeling safe, stability, having a mentor), V32 Good Family Life (good parent, emotionally close to children, stable family)
- **Agency:** V34 Mastery & Perseverance (difficult things, overcoming failure, mastering tasks, ambition), V36 Confidence & Autonomy (confident, independent, own guidelines), V37 Self-Regulated (disciplined, self-controlled), V41 Intellectual Growth (smart, intellectual experiences, education)

### 2.2 Emmons (1986, 1999) — Personal Strivings Framework

**Key contribution:** Goal abstraction as a continuum, not discrete levels. Strivings are "what individuals are characteristically aiming to accomplish through their behavior" — explicitly supports observer inference, not just self-report.

**Abstraction levels:**
- Abstract/thematic → general values, dispositional patterns ("be a good listener")
- Mid-level/strategic → personal strivings proper ("maintain close friendships")
- Concrete/tactical → specific tasks/actions ("call Mom on Sunday")

**Finding (Emmons 1992):** Excessively abstract goals predict worse well-being and more physical illness — too abstract means unactionable. Relevant for our thematic tier: some extracted thematic goals may be pathologically abstract.

**Origin dimension (from Self-Determination Theory):**

| Origin | Definition | Biographical Signal |
|--------|-----------|-------------------|
| Intrinsic | Pursued for inherent interest/satisfaction | Subject expresses joy, passion, absorption |
| Identified | Personally valued, accepted as one's own | Subject articulates why this matters |
| Introjected | Driven by internal pressure, guilt, shame | "I should...", obligation language |
| External | Driven by reward/punishment from others | Compliance, social expectation |

**Mapping to confidence model:**
- STATED + Intrinsic/Identified → high confidence
- INFERRED + Intrinsic → medium confidence (pattern of joyful engagement implies the goal)
- INFERRED + Introjected → medium confidence (pattern of guilt/obligation implies the goal)
- SPECULATED + any origin → low confidence

**Striving Assessment Scales (SAS) — 17 appraisal dimensions:**
Key additions we lack: **clarity** (how well-defined), **effort** (how much invested), **instrumentality** (how goals support/conflict with each other).

**Content categories (Emmons 2003):** Achievement (32%), Personal growth/Health (26%), Affiliation, Intimacy, Self-presentation, Self-sufficiency, Identity, Generativity, Spirituality, Power, Maladaptive. Non-exclusive.

### 2.3 Ford & Nichols (1987) — Taxonomy of Human Goals (MST)

24 goals in 2 domains:

- **Within-person:** Affective (happiness, tranquillity, bodily sensations), Cognitive (exploration, understanding, intellectual creativity), Subjective Organisation (unity, transcendence)
- **Person-environment:** Self-assertive (self-determination, individuality, superiority, resource acquisition), Integrative (belongingness, social responsibility, equity, resource provision), Task (mastery, management, creativity, safety)

Less applicable than Talevich (fixed vocabulary, no hierarchy, designed for self-report). Useful as a cross-reference for validating the Talevich taxonomy's coverage.

## 3. Current Model Gaps

### 3.1 Goal Classification

The `Goallike` trait interface currently provides:
- `goal_tier` — thematic/strategic/tactical (ad-hoc, conflates content with abstraction)
- `goal_horizon` — immediate/short/medium/long/aspirational
- `goal_status` — active/blocked/completed/dormant/abandoned
- `goal_need_tier` — SAFETY/TASKS/SOCIAL/SELF_EXPRESSION/UNDERSTANDING (Maslow-derived)
- `goal_urgency`, `goal_priority`, `goal_feasibility` — numeric 0.0-1.0

**What's missing:**
- Content domain (Talevich Y-level) — *what kind* of goal
- Motivation origin (SDT) — *why* they pursue it
- Clarity — how well-defined the goal is
- Evidence basis — what in the text supports the goal's existence

### 3.2 Motivation Layer

The drive system provides four axes (curiosity/competence/affiliation/autonomy) from Deci & Ryan's Self-Determination Theory. These are structural — they predict *that* mastery matters but not *mastery of what*. The content that fills the drive axes is currently:

- For biographical agents: implicit in extracted goals and memories
- For synthetic agents: absent entirely

There is no explicit motivation model connecting drives to specific domains of interest.

### 3.3 Affinity/Taste

No representation exists for irreducible personal preferences — the "born this way" attractions that precede experience and can't be derived from personality dimensions. For biographical agents this is captured implicitly in the biography. For synthetic agents, this is a gap that leaves agents hollow until sufficient experience accumulates.

## 4. Three Sources of Affinity

Analysis of how real humans develop specific domain attachments reveals three distinct pathways:

### 4.1 Seeded (Pre-experiential)

Irreducible attractions that precede any experience. The child who picks up every insect before anyone taught them to care about insects. These are initial conditions, not caused by anything in the agent's history.

- **For biographical agents:** Captured by extraction — the biography records what the subject was drawn to before identifiable causes.
- **For synthetic agents:** Must be declared in the profile. The disposition axes predict a *probability distribution* over domain categories but cannot resolve to specific content.
- **Modelling principle:** Derive the shape (personality → likely category), declare the content (author → specific domain).

### 4.2 Acquired (Competence-driven)

Affinities that develop through a feedback loop: exposure → competence → reward → reinforcement.

Example: Becoming good at programming → success feels good → mastery drive reinforces → increased engagement → more competence → lock-in.

**Feedback dynamics matter.** Domains with faster feedback cycles (milliseconds for code, seconds for games) select more aggressively for certain personality profiles. High novelty-seeking + fast habituation + systematic thinking → computers are almost uniquely reinforcing because they provide immediate, varied, systematic feedback at the speed the personality demands.

- **Existing machinery:** CBR outcome feedback (success → higher confidence → retrieval weight → recommendation → more success). The loop exists but isn't explicitly modelled as an affinity formation mechanism.
- **Modelable extension:** `HabituationConfig` (habituation rate, novelty threshold) + drive axes could predict reward-profile-matched domains. Domains with matching feedback dynamics score higher in the latent distribution.

### 4.3 Borrowed (Association/Social-driven)

Affinities transferred from relationships or social context.

- **Association pathway:** Chess bonded to Dad through "played-with" edge. Dad carries strong positive PAD. DomainActivation cross-subgraph correlation detects the co-activation. The game's value is borrowed from the relationship.
- **Social pathway:** Friends play the game → affiliation drive pulls you in → you start because they play → may develop genuine competence attachment, or may dissolve when the group dissolves.

**Existing machinery:** MindMap edges + affect trajectory (association), EngagementEvents + affiliation drive (social). Both pathways are emergent from current systems.

## 5. The Modelling Boundary

**"You can parameterise the engine but you can't parameterise taste."**

The cognitive engine can:
- Derive which *categories* of motivation are likely strong (disposition → Talevich Y-level distribution)
- Amplify seeded content through drive dynamics
- Form new affinities through competence and social feedback loops
- Evolve preferences as experiences accumulate

The cognitive engine cannot:
- Predict specific content preferences from personality alone (why painting, not music?)
- Generate taste from first principles
- Resolve the latent affinity distribution without environmental input or authorial declaration

This is the same constraint novelists face: a character generation system can create personality profiles, but someone still decides that *this* character loves *this* thing.

**Design principle: derive the shape, observe the content.** The derived layer should produce a probability distribution over domains. The seed layer (or early experience) resolves the distribution to specific outcomes.

## 6. Proposed Model Extensions

### 6.1 Goal Content Domain (Talevich Y-level)

Add `goalContentDomain()` to the `Goallike` trait interface:

```
MORALITY_AND_VIRTUE      // Y1 — Meaning
RELIGION_AND_SPIRITUALITY // Y2 — Meaning
SELF_ACTUALISATION       // Y3 — Meaning
AVOIDANCE                // Y4 — Communion
SOCIAL_RELATING          // Y5 — Communion
HEALTH                   // Y6 — Communion
FAMILY                   // Y7 — Communion
MASTERY_AND_COMPETENCE   // Y8 — Agency
FINANCIAL_AND_OCCUPATIONAL // Y9 — Agency
```

Each goal gets classified into one of these 9 domains. The 3 superordinate clusters (Meaning/Communion/Agency) are derivable from the domain and don't need a separate field.

Optional: `goalContentSubdomain()` at Talevich X-level (14 values) for finer classification when needed.

### 6.2 Motivation Origin (SDT)

Add `goalOrigin()` to `Goallike`:

```
INTRINSIC    // pursued for inherent interest/satisfaction
IDENTIFIED   // personally valued, accepted as own
INTROJECTED  // driven by internal pressure, guilt, shame
EXTERNAL     // driven by reward/punishment from others
```

This is orthogonal to `ConfidenceOrigin` (STATED/INFERRED/SPECULATED) which captures *how we know* the goal exists. `goalOrigin` captures *why the subject pursues it*.

### 6.3 Goal Clarity

Add `goalClarity()` as a 0.0-1.0 dimension (from Emmons' SAS):

- 1.0 = precisely defined, actionable ("complete medical degree by 1928")
- 0.5 = directional but open-ended ("achieve artistic independence")
- 0.0 = vague, aspirational ("be happy")

This replaces the implicit assumption that thematic goals are always clear.

### 6.4 Evidence Basis

Add `goalEvidenceBasis()` as a string field — a one-line citation of what in the source text supports the goal's existence:

- Explicit: "She resolved to be financially self-sufficient" (§4)
- Behavioural: "Pattern of choosing art over domestic life across §4-§8"
- Absent: null (for SPECULATED goals)

Makes the inference chain auditable. Feeds into the confidence model.

### 6.5 Affinity Profile (Cognitive Profile YAML)

New section in the cognitive profile YAML for synthetic agents:

```yaml
affinities:
  seeded:
    - domain: "systematic-technical"
      strength: 0.8
      specificity: null  # unresolved — environment determines content
    - domain: "aesthetic-visual"
      strength: 0.4
      content: "minimalist design"  # resolved — author-declared
  reward_profile:
    feedback_speed: fast        # fast/moderate/slow
    novelty_demand: high        # how quickly stimulus must vary
    mastery_satisfaction: high  # reward from competence growth
```

The `seeded` entries declare latent affinities at the category level. `content` resolves the category to specific domain when the author wants to declare taste. `null` content means the environment resolves it through exposure + competence feedback.

The `reward_profile` enables prediction of which domains will produce competence lock-in based on their feedback dynamics.

### 6.6 Extraction Prompt Updates

The GOAL_SYSTEM extraction prompt should be updated to:

1. Request `content_domain` from the 9-value Talevich taxonomy
2. Request `origin` from the 4-value SDT classification
3. Request `clarity` as a 0.0-1.0 score
4. Request `evidence_basis` as a one-line source citation
5. Provide examples calibrated to each content domain so the LLM classifies accurately

### 6.7 Goal Dedup Strategy

Two-phase dedup:

1. **Mechanical pre-filter** — Jaro-Winkler ≥ 0.90 AND Jaccard word overlap ≥ 0.50, same tier. Conservative — reduces the LLM search space by ~96% (9,453 pairs → ~341 candidates). Precision-first: never merge non-duplicates.

2. **LLM semantic judgment** — batch the ~341 near-miss candidates to an LLM for semantic equivalence assessment. The LLM can distinguish "Maintain artistic independence and voice" from "Maintain artistic independence from curatorial control" — string similarity cannot.

## 7. Relationship to Existing Drive System

The 4-axis drive model (curiosity/competence/affiliation/autonomy) provides the structural dynamics. The Talevich taxonomy provides the content vocabulary. They compose:

| Drive Axis | Talevich Domains (likely high activation) |
|-----------|------------------------------------------|
| Curiosity | Self-Actualisation, Mastery & Competence |
| Competence | Mastery & Competence, Financial & Occupational |
| Affiliation | Social Relating, Family |
| Autonomy | Self-Actualisation (Openness to Experience) |

The `CognitiveDerivationEngine` already derives drive configuration from disposition axes. This mapping extends it to predict content domain weights from the same disposition profile — which Talevich domains are likely strong for this personality configuration.

## 8. Open Questions

1. **Granularity for extraction.** Should the extraction prompt use Y-level (9 domains) or W-level (25 types)? Y-level is simpler for the LLM; W-level is more precise. Could start with Y and refine.

2. **Cross-tier dedup.** The same life theme appears as thematic ("artistic independence") and tactical ("refuse to let curator change exhibition layout"). These are semantically related but at different abstraction levels. Should they be linked (edge: "contributes-to") or merged?

3. **Affinity formation detection.** Can we detect competence lock-in as it happens — the moment an acquired affinity transitions from "doing because good at it" to "genuinely caring about it"? What's the signal?

4. **Talevich taxonomy validation.** The taxonomy was derived from US participants. Cross-cultural validity for biographical subjects from different cultures needs consideration.

5. **Motive vs goal distinction.** Talevich calls these "motives" — enduring dispositional tendencies. Our goals include both motives (enduring) and objectives (completable). Should we distinguish them, or let the abstraction level + status capture the difference?

## References

- Talevich, Read, Walsh, Iyer & Chopra (2017). "Toward a comprehensive taxonomy of human motives." *PLOS ONE* 12(2): e0172279. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0172279
- Read, Walsh & Talevich (2010). "A principled basis for the motives of intelligent agents." *IVA Conference*. https://link.springer.com/chapter/10.1007/978-3-642-15892-6_4
- Chulef, Read & Walsh (2001). "A Hierarchical Taxonomy of Human Goals." *Motivation and Emotion* 25:191-232
- Emmons (1986). "Personal strivings: An approach to personality and subjective well-being." *Journal of Personality and Social Psychology* 51(5): 1058-1068
- Emmons (1992). "Abstract versus concrete goals: personal striving level, physical illness, and psychological well-being." *JPSP* 62(2): 292-300
- Emmons (1999). *The Psychology of Ultimate Concerns.* Guilford Press
- Ford & Nichols (1987). "A taxonomy of human goals and some possible applications." In Ford & Ford (Eds.), *Humans as Self-Constructing Living Systems*
- Deci & Ryan (1985). *Intrinsic Motivation and Self-Determination in Human Behavior.* Springer
- OSF data repository: https://osf.io/4m3w4/
- Read Lab taxonomy page: https://dornsife.usc.edu/stephenjread/taxonomy-of-human-motivation/
- neocortex `Goallike` trait: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/Goallike.java`
- neocortex `CognitiveDerivationEngine`: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java`
- neocortex `HabituationConfig`: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/HabituationConfig.java`
- Goal audit data: `blocks-ui/examples/cognitive-workbench/output-test/corpus.json` (138 goals, Frida Kahlo biography)
