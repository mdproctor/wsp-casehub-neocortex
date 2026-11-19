# Biographical Extraction of Situational Personality Profiles — Design Spec

**Issue:** casehubio/neocortex#1056
**Date:** 2026-11-18
**Status:** Draft

## Problem

The runtime consumes `AgentDisposition.situationalProfiles` (eidos#234), which defines how a character's AMPD personality facets shift under stress, flow, and social contexts. Currently these profiles come only from archetype-family defaults (provenance "estimated"). Characters with rich biographical evidence should have per-character situational profiles grounded in documented episodes (provenance "biographical"), replacing the generic defaults.

The extraction pipeline (`biographies/scripts/extract_personality.py`) already scores baseline AMPD facets. This spec adds a parallel extraction pass for situational modulation.

## Architecture

### Extraction layer (Python)

Add `build_situational_prompt()` to `extract_personality.py`. The prompt asks the LLM to assess how the subject's personality facets shift under each of 5 modes:

| Mode | Biographical grounding |
|------|----------------------|
| `stress` | Documented stress responses: threat, loss, resource scarcity, illness |
| `flow` | Documented peak performance: creative engagement, mastery states |
| `social_collaborative` | Documented teamwork, partnerships, mentorship |
| `social_competitive` | Documented rivalry, adversarial interactions |
| `social_hierarchical` | Documented authority/subordination episodes |

Output format per mode:
```json
{
  "mode": "stress",
  "facet_deltas": {
    "anxiousness": 15,
    "emotional-lability": 12,
    "hostility": 8
  },
  "evidence": "During her spinal surgery recovery (1946), Frida showed..."
}
```

**Deltas** are integers in [-50, 50] on the AMPD scale. Only shifted facets are included — zero-delta facets are omitted. Facet names use kebab-case (consistent with existing extraction JSON).

**Parallelism:** Runs as a 3rd parallel LLM call in the existing `ThreadPoolExecutor(max_workers=3)`. Does not depend on baseline AMPD scores — the LLM reasons about shifts from biographical evidence alone.

**Evidence requirement:** Each mode requires specific biographical episode citations. Modes lacking sufficient evidence are omitted entirely. The prompt instructs: "Only include modes where you have clear biographical evidence of personality shift. Omit modes where the biography provides insufficient evidence."

### Validation

Add `validate_situational_profiles()`:
- Mode must be in `VALID_MODES` set
- Facet names must be in `AMPD_FACETS` list
- Deltas must be integers in [-50, 50]
- Duplicate modes rejected
- Warn on delta magnitude > 30 (unusual but not invalid)

### Pipeline pass-through

**assemble_corpus.py:** No change needed — `personality_profile` dict is copied wholesale, so a new `situational_profiles` key inside it propagates automatically.

**convert_corpus.py:** Add pass-through in `_map_personality_profile()`:
```python
situational = pp.get("situational_profiles")
if situational:
    entry["situational_profiles"] = situational
```

### Java import chain

**PersonalityProfileEntry.java** — Add nested record and field:
```java
public record SituationalProfileEntry(
    String mode,
    @JsonProperty("facet_deltas") Map<String, Integer> facetDeltas,
    String evidence
) {}

@JsonProperty("situational_profiles")
List<SituationalProfileEntry> situationalProfiles
```

**PersonalityProfileHandler.java** — Add `writeSituationalProfiles()`:
1. Convert kebab-case facet names to title-case via `AmpdFacets.canonicalise()`
2. Build `AmpdFacetShift` list per mode
3. Create `SituationalProfile(mode, shifts, "biographical")` records
4. Write as MindMap node properties: `situational-<mode>-<facet>: <delta>` for downstream eidos bridge consumption

### Runtime integration

The `EidosCognitiveProfileBridge` already passes through `situationalProfiles` from `AgentDisposition`. The import path's job is to get situational profiles INTO the character's disposition data. The bridge in `livedDisposition()` and `composeFacets()` already handles the rest.

## Data Flow

```
Biography text
    ↓ (LLM extraction — parallel call 3)
personality_profile.situational_profiles  [enriched.json]
    ↓ (assemble_corpus.py — automatic pass-through)
personality_profile.situational_profiles  [engram.json]
    ↓ (convert_corpus.py — explicit pass-through)
situational_profiles                      [personality-profile.yaml]
    ↓ (BiographyLoader → PersonalityProfileEntry)
SituationalProfileEntry list              [Java records]
    ↓ (PersonalityProfileHandler)
MindMap node properties                   [situational-stress-anxiousness: 15]
    ↓ (EidosCognitiveProfileBridge)
AgentDisposition.situationalProfiles      [SituationalProfile records]
```

## Testing

1. **Python:** Test `build_situational_prompt()` produces valid prompt structure. Test `validate_situational_profiles()` enforces constraints (valid modes, valid facets, delta range, duplicate rejection).
2. **Java:** Test `PersonalityProfileEntry` Jackson deserialization with `situational_profiles` field. Test `PersonalityProfileHandler.writeSituationalProfiles()` converts facet names and writes correct properties.

## Scope exclusions

- **Re-running existing biographies:** This adds the extraction capability. Re-extracting existing characters is a separate run, not a code change.
- **Archetype blending for multi-archetype characters:** Issue #1056 mentions this but it's already handled by the runtime — per-character extraction subsumes blending by providing direct profiles.

## References

- eidos#234 — `AgentDisposition.situationalProfiles` type definition
- eidos `SituationalProfileDefaults.forFamily()` — archetype-family defaults
- eidos `AmpdFacetShift(String facet, int delta)` — delta record, facet range [-50, 50]
- eidos `AmpdFacets.canonicalise()` — kebab→title-case conversion
- `biographies/scripts/extract_personality.py` — existing extraction pipeline
- `biographies/scripts/convert_corpus.py` — engram→YAML conversion
- `memory-seeding/PersonalityProfileEntry.java` — Jackson import record
- `memory-seeding/PersonalityProfileHandler.java` — MindMap property writer
- #941 spec — personality-aware situation classification (runtime consumer)
