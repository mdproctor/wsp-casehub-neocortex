# Biographical Extraction of Situational Profiles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1056 — Biographical extraction of per-character situational personality profiles
**Issue group:** #1056

**Goal:** Add a parallel LLM extraction pass to the biographical pipeline that produces per-character situational personality profiles (how AMPD facets shift under stress, flow, and social contexts), with provenance "biographical", flowing through the engram into the Java import chain.

**Architecture:** Third parallel LLM call in `extract_personality.py` extracts situational facet deltas. Output flows through `assemble_corpus.py` (automatic), `convert_corpus.py` (one-line pass-through), into `PersonalityProfileEntry` (new nested record) and `PersonalityProfileHandler` (writes MindMap node properties).

**Tech Stack:** Python 3 (LLM extraction), Java 21 (import chain), Jackson (deserialization), JUnit 5 + AssertJ (tests)

## Global Constraints

- AMPD facet names in Python: kebab-case (`emotional-lability`)
- AMPD facet names in eidos: title-case with spaces (`Emotional Lability`)
- Conversion happens at the Java import boundary
- Delta range: [-50, 50] integer
- Valid modes: `stress`, `flow`, `social_collaborative`, `social_competitive`, `social_hierarchical`
- Provenance for extracted profiles: `"biographical"`

---

## Batch 1: Python extraction pipeline

### Task 1: Add situational profile extraction to extract_personality.py

**Files:**
- Modify: `biographies/scripts/extract_personality.py`

**Interfaces:**
- Consumes: `AMPD_FACETS` list (line 32), `build_context_for_subject()` (line 210), `call_llm()` (line 386), `ThreadPoolExecutor` pattern (line 461)
- Produces: `VALID_MODES` set, `build_situational_prompt(context: str) -> str`, `validate_situational_profiles(profiles: list, warnings: list) -> list`, `situational_profiles` key inside `personality_profile` dict

- [ ] **Step 1: Add VALID_MODES constant**

After `ATTACHMENT_STYLES` (line 40), add:

```python
VALID_MODES = {
    'stress', 'flow', 'social_collaborative', 'social_competitive', 'social_hierarchical'
}
```

- [ ] **Step 2: Add build_situational_prompt function**

After `build_archetypes_prompt()` (after line 207), add:

```python
def build_situational_prompt(context: str) -> str:
    ampd_list = ', '.join(AMPD_FACETS)
    modes_desc = """1. **stress** — threat, loss, resource scarcity, illness, physical/emotional pain
2. **flow** — peak functioning, creative engagement, mastery states, absorption
3. **social_collaborative** — teamwork, partnerships, mentorship, group projects
4. **social_competitive** — rivalry, adversarial interactions, contests, comparisons
5. **social_hierarchical** — authority/subordination, institutional power, deference/command"""

    system = f"""You are a personality psychologist assessing how a biographical subject's personality traits shift under different situational contexts.

You will assess shifts on the AMPD (Alternative Model for Personality Disorders) facet scale.
AMPD facets: {ampd_list}

For each situational mode below, identify which facets shift from the subject's baseline and by how much, based on SPECIFIC biographical episodes. Only include facets that demonstrably shift — omit facets with no evidence of change.

### Situational Modes
{modes_desc}

### Instructions
- Express shifts as integer deltas in the range [-50, +50] on the 0-100 AMPD scale
- Positive delta = facet increases in this mode; negative = facet decreases
- Ground EVERY delta in a specific biographical episode — no speculative shifts
- Only include modes where the biography provides clear evidence of personality shift
- Omit modes entirely if biographical evidence is insufficient

Respond with JSON only:
{{
  "situational_profiles": [
    {{
      "mode": "stress",
      "facet_deltas": {{"anxiousness": 15, "emotional-lability": 12}},
      "evidence": "During her spinal surgery recovery (1946), Frida showed increased anxiety and emotional volatility..."
    }}
  ]
}}"""

    return system
```

- [ ] **Step 3: Add validate_situational_profiles function**

After `build_situational_prompt()`, add:

```python
def validate_situational_profiles(profiles: list, warnings: list) -> list:
    validated = []
    seen_modes = set()
    for profile in profiles:
        mode = profile.get('mode')
        if mode not in VALID_MODES:
            warnings.append(f"Invalid situational mode: {mode} — not in {VALID_MODES}")
            continue
        if mode in seen_modes:
            warnings.append(f"Duplicate situational mode: {mode}")
            continue
        seen_modes.add(mode)

        deltas = profile.get('facet_deltas', {})
        clean_deltas = {}
        for facet, delta in deltas.items():
            if facet not in AMPD_FACETS:
                warnings.append(f"Invalid AMPD facet in {mode}: {facet}")
                continue
            if not isinstance(delta, (int, float)):
                warnings.append(f"Non-numeric delta for {facet} in {mode}: {delta}")
                continue
            clamped = max(-50, min(50, int(delta)))
            if abs(clamped) != abs(int(delta)):
                warnings.append(f"Delta clamped for {facet} in {mode}: {delta} -> {clamped}")
            if abs(clamped) > 30:
                warnings.append(f"Large delta for {facet} in {mode}: {clamped}")
            if clamped != 0:
                clean_deltas[facet] = clamped

        if clean_deltas:
            validated.append({
                'mode': mode,
                'facet_deltas': clean_deltas,
                'evidence': profile.get('evidence', '')
            })

    return validated
```

- [ ] **Step 4: Wire 3rd parallel call into extract_personality**

Replace the `ThreadPoolExecutor` block in `extract_personality()` (lines 461-465):

```python
    sit_prompt = build_situational_prompt(context)

    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        fw_future = pool.submit(call_llm, client, fw_prompt, context, 'frameworks')
        arch_future = pool.submit(call_llm, client, arch_prompt, context, 'archetypes')
        sit_future = pool.submit(call_llm, client, sit_prompt, context, 'situational')
        results['frameworks'] = fw_future.result()
        results['archetypes'] = arch_future.result()
        results['situational'] = sit_future.result()
```

- [ ] **Step 5: Add situational profile to combined output and validation**

After the existing `validated, warnings = validate_output(combined, schema)` block (line 483), before the consistency check, add handling for situational profiles. Update the section that builds `validated` (after line 482):

```python
    sit_result = results.get('situational', {})
    raw_profiles = sit_result.get('situational_profiles', [])
    if raw_profiles:
        sit_validated = validate_situational_profiles(raw_profiles, warnings)
        if sit_validated:
            validated['situational_profiles'] = sit_validated
```

- [ ] **Step 6: Add summary output for situational profiles**

In `main()`, after the archetypes summary print (line 542), add:

```python
    sit_profiles = profile.get('situational_profiles', [])
    if sit_profiles:
        print(f"  Situational profiles: {len(sit_profiles)} modes extracted")
        for sp in sit_profiles:
            print(f"    {sp['mode']}: {len(sp.get('facet_deltas', {}))} facet shifts")
    else:
        print(f"  Situational profiles: none (insufficient evidence)")
```

- [ ] **Step 7: Commit**

```bash
git add biographies/scripts/extract_personality.py
git commit -m "feat(#1056): add situational profile extraction to personality pipeline

Adds 3rd parallel LLM call extracting per-mode AMPD facet deltas
with biographical evidence grounding and [-50,50] delta validation.

Refs #1056

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: Add pass-through in convert_corpus.py

**Files:**
- Modify: `biographies/scripts/convert_corpus.py`

**Interfaces:**
- Consumes: `personality_profile.situational_profiles` from engram.json
- Produces: `situational_profiles` key in personality-profile YAML entry

- [ ] **Step 1: Add situational_profiles pass-through**

In `_map_personality_profile()` (line 407), after the `inconsistencies` block (line 437), add:

```python
    situational = pp.get("situational_profiles")
    if situational:
        entry["situational_profiles"] = situational
```

- [ ] **Step 2: Commit**

```bash
git add biographies/scripts/convert_corpus.py
git commit -m "feat(#1056): pass through situational_profiles in convert_corpus

Refs #1056

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 2: Java import chain

### Task 3: Add SituationalProfileEntry to PersonalityProfileEntry and test deserialization

**Files:**
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntry.java`
- Modify: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntryTest.java`

**Interfaces:**
- Consumes: Jackson deserialization from YAML with `situational_profiles` key
- Produces: `PersonalityProfileEntry.SituationalProfileEntry(String mode, Map<String, Integer> facetDeltas, String evidence)` record, `List<SituationalProfileEntry> situationalProfiles()` accessor

- [ ] **Step 1: Write failing deserialization test**

Add to `PersonalityProfileEntryTest.java`:

```java
@Test
void deserializesSituationalProfiles() throws Exception {
    String json = """
        {
            "id": "pp-6",
            "entity_ref": "Frida Kahlo",
            "situational_profiles": [
                {
                    "mode": "stress",
                    "facet_deltas": {"anxiousness": 15, "emotional-lability": 12, "hostility": 8},
                    "evidence": "During spinal surgery recovery..."
                },
                {
                    "mode": "flow",
                    "facet_deltas": {"emotional-lability": -10, "withdrawal": -15},
                    "evidence": "While painting in bed..."
                }
            ]
        }
        """;
    var entry = MAPPER.readValue(json, PersonalityProfileEntry.class);
    assertThat(entry.situationalProfiles()).hasSize(2);
    assertThat(entry.situationalProfiles().getFirst().mode()).isEqualTo("stress");
    assertThat(entry.situationalProfiles().getFirst().facetDeltas())
        .containsEntry("anxiousness", 15)
        .containsEntry("emotional-lability", 12)
        .containsEntry("hostility", 8);
    assertThat(entry.situationalProfiles().getFirst().evidence()).startsWith("During");
    assertThat(entry.situationalProfiles().get(1).mode()).isEqualTo("flow");
    assertThat(entry.situationalProfiles().get(1).facetDeltas())
        .containsEntry("emotional-lability", -10)
        .containsEntry("withdrawal", -15);
}

@Test
void situationalProfilesDefaultsToEmptyList() throws Exception {
    String json = """
        {
            "id": "pp-7",
            "entity_ref": "Test Subject"
        }
        """;
    var entry = MAPPER.readValue(json, PersonalityProfileEntry.class);
    assertThat(entry.situationalProfiles()).isEmpty();
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest="PersonalityProfileEntryTest#deserializesSituationalProfiles" -Dsurefire.failIfNoSpecifiedTests=false`

Expected: compilation error — `situationalProfiles()` does not exist.

- [ ] **Step 3: Add SituationalProfileEntry record and field**

In `PersonalityProfileEntry.java`, add nested record before the closing `}`:

```java
@JsonIgnoreProperties(ignoreUnknown = true)
public record SituationalProfileEntry(
    String mode,
    @JsonProperty("facet_deltas") Map<String, Integer> facetDeltas,
    String evidence
) {
    public SituationalProfileEntry {
        facetDeltas = facetDeltas != null ? Map.copyOf(facetDeltas) : Map.of();
    }
}
```

Add field to the top-level record parameters (after `List<String> inconsistencies`):

```java
@JsonProperty("situational_profiles") List<SituationalProfileEntry> situationalProfiles
```

Update the compact constructor to handle the new field:

```java
public PersonalityProfileEntry {
    archetypes = archetypes != null ? List.copyOf(archetypes) : List.of();
    inconsistencies = inconsistencies != null ? List.copyOf(inconsistencies) : List.of();
    situationalProfiles = situationalProfiles != null ? List.copyOf(situationalProfiles) : List.of();
}
```

- [ ] **Step 4: Fix test helper constructor call**

The existing `PersonalityProfileEntryTest.handlesNullsGracefully` test and `PersonalityProfileHandlerTest.buildProfile()` construct `PersonalityProfileEntry` directly. The new field is added at the end, so pass `List.of()` as the last argument.

In `PersonalityProfileHandlerTest.buildProfile()` (line 154), update:

```java
var entry = new PersonalityProfileEntry("pp-1", "Frida Kahlo", frameworks, archetypes, disposition, null, List.of(), List.of());
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest="PersonalityProfileEntryTest,PersonalityProfileHandlerTest"`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntry.java memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntryTest.java memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandlerTest.java
git commit -m "feat(#1056): add SituationalProfileEntry to PersonalityProfileEntry

Jackson-deserializable record for per-mode AMPD facet deltas with
kebab-case field names matching the extraction pipeline output.

Refs #1056

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 4: Write situational profiles in PersonalityProfileHandler

**Files:**
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandler.java`
- Modify: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandlerTest.java`

**Interfaces:**
- Consumes: `PersonalityProfileEntry.situationalProfiles()` from Task 3, `MindMapStore.updateNode()` (existing)
- Produces: MindMap node properties with pattern `situational-<mode>-<facet-kebab>: <delta>`

- [ ] **Step 1: Write failing test for situational profile properties**

Add to `PersonalityProfileHandlerTest.java`:

```java
@Test
void writesSituationalProfileProperties() {
    var store = new InMemoryMindMapStore();
    var sgId = BiographyUtils.ensureSubgraph(store, SubgraphTypes.PERSON, TENANT);
    store.addNode(NodeInput.of("Frida Kahlo", sgId).withProvenance("test"), TENANT);

    var handler = new PersonalityProfileHandler(store, true);
    handler.handle(buildProfileWithSituational(), AGENT, TENANT);

    var node = store.resolveNode("Frida Kahlo", sgId, TENANT);
    assertThat(node.properties()).containsEntry("situational-stress-anxiousness", "15");
    assertThat(node.properties()).containsEntry("situational-stress-emotional-lability", "12");
    assertThat(node.properties()).containsEntry("situational-stress-hostility", "8");
    assertThat(node.properties()).containsEntry("situational-flow-emotional-lability", "-10");
    assertThat(node.properties()).containsEntry("situational-flow-withdrawal", "-15");
    assertThat(node.properties()).containsEntry("situational-stress-provenance", "biographical");
    assertThat(node.properties()).containsEntry("situational-flow-provenance", "biographical");
}

@Test
void skipsEmptySituationalProfiles() {
    var store = new InMemoryMindMapStore();
    var sgId = BiographyUtils.ensureSubgraph(store, SubgraphTypes.PERSON, TENANT);
    store.addNode(NodeInput.of("Frida Kahlo", sgId).withProvenance("test"), TENANT);

    var handler = new PersonalityProfileHandler(store, true);
    handler.handle(buildProfile(), AGENT, TENANT);

    var node = store.resolveNode("Frida Kahlo", sgId, TENANT);
    assertThat(node.properties().keySet().stream().filter(k -> k.startsWith("situational-"))).isEmpty();
}
```

Add the helper method:

```java
private BiographyProfile buildProfileWithSituational() {
    var frameworks = buildProfile().personalityProfiles().getFirst().frameworks();
    var archetypes = buildProfile().personalityProfiles().getFirst().archetypes();
    var disposition = buildProfile().personalityProfiles().getFirst().disposition();

    var situational = List.of(
        new PersonalityProfileEntry.SituationalProfileEntry(
            "stress", Map.of("anxiousness", 15, "emotional-lability", 12, "hostility", 8),
            "During spinal surgery recovery..."
        ),
        new PersonalityProfileEntry.SituationalProfileEntry(
            "flow", Map.of("emotional-lability", -10, "withdrawal", -15),
            "While painting in bed..."
        )
    );

    var entry = new PersonalityProfileEntry("pp-1", "Frida Kahlo", frameworks, archetypes, disposition, null, List.of(), situational);

    return new BiographyProfile(AGENT, TENANT,
        List.of(), List.of(), List.of(), List.of(),
        List.of(), List.of(), List.of(), List.of(),
        List.of(), List.of(), List.of(), List.of(),
        List.of(entry), List.of());
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest="PersonalityProfileHandlerTest#writesSituationalProfileProperties" -Dsurefire.failIfNoSpecifiedTests=false`

Expected: FAIL — no `situational-stress-anxiousness` property written.

- [ ] **Step 3: Add writeSituationalProfiles method**

In `PersonalityProfileHandler.java`, add after `writeDispositionAxis()`:

```java
private void writeSituationalProfiles(java.util.List<PersonalityProfileEntry.SituationalProfileEntry> profiles,
                                       HashMap<String, String> props) {
    if (profiles == null || profiles.isEmpty()) return;

    for (var profile : profiles) {
        if (profile.mode() == null) continue;
        String prefix = "situational-" + profile.mode();
        for (var delta : profile.facetDeltas().entrySet()) {
            props.put(prefix + "-" + delta.getKey(), String.valueOf(delta.getValue()));
        }
        props.put(prefix + "-provenance", "biographical");
    }
}
```

- [ ] **Step 4: Wire writeSituationalProfiles into handle()**

In `handle()`, after `writeDisposition(entry.disposition(), props);` (line 36), add:

```java
            writeSituationalProfiles(entry.situationalProfiles(), props);
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest="PersonalityProfileHandlerTest,PersonalityProfileEntryTest"`

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandler.java memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandlerTest.java
git commit -m "feat(#1056): write situational profile properties in PersonalityProfileHandler

Writes per-mode AMPD facet deltas as MindMap node properties
(situational-<mode>-<facet>: <delta>) with biographical provenance.

Refs #1056

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 3: Build verification

### Task 5: Full module build verification

**Files:**
- None modified — verification only

- [ ] **Step 1: Build memory-seeding module**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl memory-seeding`

Expected: BUILD SUCCESS, all tests pass.

- [ ] **Step 2: Build full project (skip tests for speed)**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`

Expected: BUILD SUCCESS across all modules.

- [ ] **Step 3: Final commit if any adjustments were needed**

Only if compilation fixes were required. Otherwise skip.

## References

- [2026-11-18-biographical-extraction-situational-profiles-design.md] — design spec
- [biographies/scripts/extract_personality.py] — extraction pipeline
- [biographies/scripts/convert_corpus.py:407-439] — personality profile YAML conversion
- [memory-seeding/.../PersonalityProfileEntry.java] — Jackson import record
- [memory-seeding/.../PersonalityProfileHandler.java] — MindMap property writer
- [memory-seeding/.../PersonalityProfileEntryTest.java] — deserialization tests
- [memory-seeding/.../PersonalityProfileHandlerTest.java] — handler tests
- [eidos SituationalProfile.java] — target type (mode, shifts, provenance)
- [eidos AmpdFacetShift.java] — delta record (facet, delta [-50, 50])
- [GitHub #1056] — focal issue
- [GitHub #941] — personality-aware situation classification (runtime consumer)
