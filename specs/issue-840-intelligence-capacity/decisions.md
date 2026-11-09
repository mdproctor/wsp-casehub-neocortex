# Design Decisions — #840 Intelligence Capacity Layer

## D1: Capacity as first-class parameter, not personality-derived

**Choice:** Cognitive capacity is a first-class parameter orthogonal to personality, specified explicitly per agent in cognitive profile YAML, with CDE-derived defaults as fallback for unspecified agents.
**Alternatives:**
- Derive from Jungian profile (Ti+Te+Ni) — conflates cognitive style with cognitive ability. High-Ti means preference for logical analysis, not ability to do relational reasoning. Circular.
- Derive from PID-5 facets — PID-5 measures maladaptive pathology. DeYoung (2016) showed Intellect has no PID-5 counterpart. Structurally impossible.
- Derive from disposition axes — ruleFollowing/riskAppetite/autonomy are motivational constructs with no literature support as capacity proxies.
**Rationale:** Nusbaum & Silvia (2011) demonstrated the double dissociation: Openness predicts creativity not Gf; Intellect predicts Gf not creativity. DeYoung (2014) confirmed Intellect independently associates with g. Capacity is empirically orthogonal to personality — it requires its own representation, not a derivative of existing traits.
**Trade-offs:** Agents need explicit capacity specification for richest differentiation. Unspecified agents get compressed-range defaults.
**Sources:** DeYoung (2014) JPA 96(1); Nusbaum & Silvia (2011) PID 51; DeYoung et al. (2016) PMC4818976; Halford et al. (1998) BBS 21(6); Engle & Kane (2004) Psych L&M 44
**Exploration:** deep-analysis
**Status:** captured
