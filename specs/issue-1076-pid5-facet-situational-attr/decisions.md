# Decisions — #1076 PID-5 Facet Extension

## D1: Which facets get CDE derivation rules

**Choice:** Tiers 1+2 — 10 new facets get CDE rules, 2 enter enum without rules, 2 existing facets backfilled.

**Tier 1 (6 facets, strong empirical support):**
- Depressivity, Anhedonia, Perseveration, Rigid Perfectionism, Distractibility, Separation Insecurity

**Tier 2 (4 facets, moderate empirical support):**
- Restricted Affectivity, Irresponsibility, Cognitive/Perceptual Dysregulation, Eccentricity

**No rules (2 facets, weak/no empirical support):**
- Submissiveness (psychometrically poor, λ=−.35 max loading), Unusual Beliefs (effects are belief content, not cognitive processing)

**Backfill existing facets:**
- Deceitfulness: 1–2 modest rules (laterality ↑, depth ↑ via Machiavellianism literature)
- Attention Seeking: 0–1 rules (arousal ↑ weak, more behavioral strategy than cognitive processing)

**Alternatives:**
- All 12 get rules — forces speculative rules (Submissiveness dominance-only, Unusual Beliefs contested associativeReach) that produce noise
- Tier 1 only — misses 4 facets with genuine moderate evidence (Restricted Affectivity has strong alexithymia support, Irresponsibility backed by N=66,807 Grit meta-analysis)

**Rationale:** The boundary between "has CDE rules" and "doesn't" should be the boundary between "empirically demonstrated cognitive processing effects" and "behavioral strategy or belief content without cognitive processing evidence." Submissiveness and Unusual Beliefs fall on the wrong side. Deceitfulness/Attention Seeking are behavioral strategies that were correctly left without rules initially — backfill with minimal rules only where evidence exists.

**Trade-offs:** 2 of 25 facets will have no CDE derivation rules. This means they flow through classification and situational modulation but don't affect derived cognitive parameters. Agents with high Submissiveness or Unusual Beliefs won't get differentiated cognitive profiles from those facets alone.

**Sources:**
- Literature review forks: Negative Affect cluster (Meehl 1975, Beck 1967, Scherer 2022, Nolen-Hoeksema 1991, Davis & Nolen-Hoeksema 2000)
- Executive function cluster (Martinussen 2005 meta, Smith & Samuel 2016, Xie 2019 meta, Credé 2017 meta)
- Interpersonal cluster (Trevisan 2019 meta, Downey & Feldman 1996, Stanton & Campbell 2015)
- Psychoticism cluster (Carson 2003, Siddi 2017 meta, Ozdemir 2025 meta, Mohr 2001 vs Kiang & Kutas 2010)
- Backfill (Bereczkei 2014/2015, Connor-Smith 2007 meta)

**Exploration:** deep-analysis
**Status:** captured

## D2: Situational attractor profile strategy

**Depends on:** D1 (facet selection)

**Choice:** Confidence-scaled deltas — only STRONG and MODERATE evidence enters profiles; WEAK evidence omitted.

**Scaling:**
- STRONG evidence → delta ±10–15, provenance: empirical
- MODERATE evidence → delta ±5–10, provenance: empirical
- WEAK evidence → omit (no shift in profile)
- Unchanged/no evidence → omit

**Key findings from literature review:**

*Stress mode:* 11 of 14 facets amplify under stress. Strongest: Depressivity, Anhedonia, Distractibility, Separation Insecurity, Cog/Perceptual Dysregulation (all STRONG). Deceitfulness unchanged (strategic, not reactive). Attention Seeking WEAK (omit).

*Flow mode:* Two opposing effects — DMN suppression dampens self-referential facets (Depressivity ↓ STRONG, Distractibility ↓ STRONG, Anhedonia ↓ MODERATE, Rigid Perfectionism ↓ MODERATE); absorption amplifies positive schizotypy features (Eccentricity ↑ MODERATE, Cog/Perceptual Dysregulation ↑ MODERATE). Most facets have WEAK/NONE flow evidence → omit.

*Social collaborative:* Mixed — some dampened by safety/accountability (Irresponsibility ↓, Submissiveness ↓, Separation Insecurity ↓), some amplified by social demands (Depressivity ↑ via co-rumination, Rigid Perfectionism ↑ via socially prescribed pressure, Restricted Affectivity ↑ via emotional demands).

*Social competitive:* Strongest modulator — 7 facets amplify. Depressivity, Rigid Perfectionism, Separation Insecurity, Deceitfulness all STRONG. Eccentricity dampened by conformity pressure (MODERATE).

*Social hierarchical:* Submissiveness ↑ STRONG (THE primary trigger). Separation Insecurity ↑ STRONG. Eccentricity ↓, Irresponsibility ↓ dampened by conformity/authority.

**Alternatives:**
- Uniform moderate (±10 for all) — loses the empirical gradation that the literature supports
- Full range with estimated — includes WEAK evidence as provenance:estimated, more complete but adds speculative entries

**Rationale:** The confidence-scaled approach preserves the empirical signal in the magnitude. A STRONG finding (Pizzagalli 2014 meta-analytic support for stress-induced anhedonia) should produce a larger shift than a MODERATE finding (Rónai 2026 single ESM study for eccentricity under stress). Omitting WEAK evidence keeps profiles clean — agents with WEAK-only modulations don't get noisy shifts.

**Trade-offs:** Some facets will have empty profiles for certain modes (e.g., Restricted Affectivity under flow has no shift because evidence is NONE). This means those facets contribute to resting CDE derivation but don't shift situationally in those modes. We accept this as honest rather than speculative.

**Sources:** explorations/D2-situational-modulation-literature.md (full literature tables)

**Exploration:** deep-analysis
**Status:** captured

## D3: Cross-repo sequencing

**Choice:** Eidos first, neocortex depends.

1. eidos: Add 12 facets to `AmpdFacets.CANONICAL` + `PersonalityFacet` enum
2. neocortex: Bump eidos dependency version
3. neocortex: CDE rules, situational profiles, PersonalityPromptBuilder extension, tests

**Alternatives:**
- Parallel with interface contract — risk of name mismatches
- Neocortex first with string literals — faster iteration but weaker type safety

**Rationale:** Clean dependency chain. Eidos owns the AMPD facet vocabulary; neocortex consumes it. Changing both simultaneously creates coordination risk in a multi-slot environment.

**Trade-offs:** Requires an eidos commit+publish before neocortex work can begin. This is ~30 min of work, not a bottleneck.

**Exploration:** quick
**Status:** captured

## D4: PersonalityPromptBuilder extension strategy

**Choice:** Pass all 25 facets in every classification call. No relevance filter.

**Alternatives:**
- Relevance-filtered (|score - 0.5| > threshold) — reduces noise but makes CBR cache keys unstable

**Rationale:** Simpler, deterministic. 25 facet-value pairs add ~100 tokens to the prompt — negligible cost. CBR cache key stability matters: same agent always hashes the same facet set regardless of which facets happen to be "interesting."

**Trade-offs:** Agents with average scores on most facets include uninformative facet values in the prompt. The classifier must handle the full set, though Haiku-class models handle this easily.

**Exploration:** quick
**Status:** captured
