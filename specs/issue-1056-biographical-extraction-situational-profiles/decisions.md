# Decisions — #1056 Biographical Extraction of Situational Profiles

## D1: Extraction parallelism

**Choice:** 3rd parallel LLM call alongside frameworks + archetypes
**Alternatives:**
- Sequential after frameworks — could use AMPD baselines as context, but adds latency
- Extend frameworks prompt — overloads an already large prompt, conflates baseline and shift assessment
**Rationale:** Situational shifts are reasoned from biographical episodes, not from baseline scores. The LLM can independently assess "how does this person change under stress" without knowing the numeric baseline. Parallel execution keeps total extraction time constant.
**Trade-offs:** Cannot cross-reference baseline AMPD scores to sanity-check delta magnitudes within the prompt; validation handles this post-hoc.
**Sources:** biographies/scripts/extract_personality.py (existing parallel ThreadPoolExecutor pattern), eidos AmpdFacetShift delta range [-50, 50]
**Exploration:** quick
**Status:** captured

## D2: Facet name convention in extraction output

**Choice:** Kebab-case in extraction JSON, title-case conversion at Java import boundary
**Alternatives:**
- Title-case throughout — matches eidos canonical form but inconsistent with existing extraction JSON which uses kebab-case for AMPD facets
- Numeric IDs — fragile, unreadable in JSON
**Rationale:** Existing extraction pipeline uses kebab-case for AMPD facets (line 32-36 of extract_personality.py). Consistency within the Python pipeline outweighs matching the Java eidos convention. The import layer already handles convention conversion.
**Trade-offs:** One extra conversion step in PersonalityProfileHandler.
**Sources:** extract_personality.py:32-36 (AMPD_FACETS list), eidos AmpdFacets.canonicalise()
**Exploration:** quick
**Status:** captured

## D3: Handling modes with insufficient evidence

**Choice:** Omit modes lacking biographical evidence; runtime falls back to archetype-family defaults
**Alternatives:**
- Emit all 5 modes with zero deltas — semantically wrong ("no shift" is different from "unknown")
- LLM-estimated deltas without evidence — contradicts the provenance model (would need provenance "estimated", not "biographical")
**Rationale:** The eidos runtime already handles fallback: when `situationalProfiles` is empty or partial for a character, `SituationalProfileDefaults.forFamily()` provides archetype-family defaults with provenance "estimated". Per-character extraction with provenance "biographical" only adds value when grounded in actual episodes.
**Trade-offs:** Some characters may have sparse coverage (e.g. only stress + flow, not social contexts). This is correct — partial evidence should produce partial profiles.
**Sources:** eidos SituationalProfileDefaults.forFamily(), issue #1056 comment "Characters without sufficient biographical evidence for a mode fall back to their archetype family default"
**Exploration:** quick
**Status:** captured
