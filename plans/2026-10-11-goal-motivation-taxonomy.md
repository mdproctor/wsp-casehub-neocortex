# Goal & Motivation Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #538 — Epic: goal & motivation taxonomy model extension
**Issue group:** #539, #540, #541, #542, #543, #544, #545, #546, #547, #548

**Goal:** Extend the neocortex cognitive model with grounded goal/motivation taxonomy (Talevich/Emmons), migrate extraction pipeline, and improve corpus quality.

**Architecture:** Five-phase implementation: migrate Python pipeline to neocortex, extend Goallike trait + GoalVocabulary with taxonomy fields, update extraction prompts and assembler dedup, update importer, re-process Frida biography.

**Tech Stack:** Java 21 (Quarkus 3.32), Python 3.14 (extraction pipeline), Maven

## Global Constraints

- All Goallike trait methods return `Optional<String>` — the proxy is string-only
- Property keys for trait-backed properties must match the method name exactly (camelCase)
- Pre-existing kebab-case keys (`tier`, `horizon`, `need-tier`) retain current form
- `origin` → `recognitionSource` rename must be atomic across all four goal creation paths
- GoalVocabulary validates domain/origin values at import boundary

---

## Batch 1: Pipeline Migration (#539)

### Task 1: Move extraction pipeline to neocortex/extraction/

**Files:**
- Create: `extraction/scripts/` (move from blocks-ui)
- Create: `extraction/docs/field-registry.yaml` (move from blocks-ui)
- Create: `extraction/sources/frida-kahlo-biography.md` (move from blocks-ui)
- Create: `extraction/tests/` (move test files)
- Modify: `extraction/scripts/run_pipeline.sh` — update path references
- Modify: `extraction/scripts/iterate.sh` — update path references
- Modify: `.gitignore` — add extraction exclusions

**Interfaces:**
- Produces: working pipeline at `neocortex/extraction/` that produces identical output to the blocks-ui version

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p extraction/scripts extraction/docs extraction/sources extraction/tests
```

- [ ] **Step 2: Copy all pipeline files**

```bash
# Copy from blocks-ui (not move — verify first, remove later)
cp blocks-ui/examples/cognitive-workbench/scripts/*.py extraction/scripts/
cp blocks-ui/examples/cognitive-workbench/scripts/*.sh extraction/scripts/
cp blocks-ui/examples/cognitive-workbench/scripts/requirements.txt extraction/scripts/
cp blocks-ui/examples/cognitive-workbench/docs/field-registry.yaml extraction/docs/
cp blocks-ui/examples/cognitive-workbench/source/frida-kahlo-biography.md extraction/sources/
cp blocks-ui/examples/cognitive-workbench/scripts/test_*.py extraction/tests/
```

Note: `blocks-ui` is at `../blocks-ui` relative to neocortex. Use absolute paths from the slot root.

- [ ] **Step 3: Update path references in shell scripts**

In `extraction/scripts/run_pipeline.sh`: update `SCRIPT_DIR` computation and remove WORKBENCH references — scripts are now at the top level of extraction/.

In `extraction/scripts/iterate.sh`: update SOURCE, BASELINE, OUTDIR paths to use `extraction/` relative paths.

- [ ] **Step 4: Update .gitignore**

Add to neocortex `.gitignore`:
```
extraction/output/
extraction/output-test/
extraction/scripts/.venv/
extraction/scripts/__pycache__/
```

- [ ] **Step 5: Create venv and verify**

```bash
cd extraction/scripts && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

- [ ] **Step 6: Run pipeline on 3 passages and verify**

```bash
bash extraction/scripts/iterate.sh --limit 3 --label "migration-verify"
```

Compare output against pre-migration baseline — goal count, entity count, and coverage percentages should match within LLM non-determinism tolerance.

- [ ] **Step 7: Run tests**

```bash
extraction/scripts/.venv/bin/python3 -m pytest extraction/tests/ -v
```

- [ ] **Step 8: Commit**

```bash
git add extraction/ .gitignore
git commit -m "feat(#539): migrate extraction pipeline from blocks-ui to neocortex/extraction/

Refs #539"
```

## Batch 2: Goallike Trait + GoalVocabulary (#540)

### Task 2: Rename origin() to recognitionSource() on Goallike

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Goallike.java:9`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/GoallikeTest.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/GoallikeTraitRule.java` (if references origin)
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalHandler.java`

**Interfaces:**
- Consumes: existing `Goallike.origin()` method
- Produces: `Goallike.recognitionSource()` method + updated property keys in all goal creation paths

- [ ] **Step 1: Write failing test for recognitionSource()**

In `GoallikeTest.java`, add or update test to verify the renamed method:

```java
@Test
void recognitionSourceReturnsValue() {
    var node = createNodeWithProperty("recognitionSource", "conversation");
    var goal = node.as(Goallike.class);
    assertEquals(Optional.of("conversation"), goal.recognitionSource());
}
```

- [ ] **Step 2: Run test — verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=GoallikeTest#recognitionSourceReturnsValue -DfailIfNoTests=false
```

Expected: compilation error — `recognitionSource()` not defined.

- [ ] **Step 3: Rename origin() to recognitionSource() on Goallike interface**

Use `ide_replace_member` to change:
```java
Optional<String> origin();
```
to:
```java
Optional<String> recognitionSource();
```

- [ ] **Step 4: Update GoallikeTest — fix old test referencing origin()**

Update existing test that calls `origin()` to call `recognitionSource()`.

- [ ] **Step 5: Find and update all callers writing "origin" property key**

Use `ide_find_references` on the old `origin()` method. Update:

1. `GoalHandler.java` line ~40: if it writes `props.put("origin", ...)` — but looking at the current code, GoalHandler does NOT write an "origin" property. Skip.

2. Find `GoalRecognitionPhase` — search for `"origin"` property writes:
```bash
grep -rn '"origin"' mindmap-intelligence/src/main/java/
```
Update `props.put("origin", ...)` → `props.put("recognitionSource", ...)`

3. Find `DriveGoalBridgeParticipant`:
```bash
grep -rn '"origin"' cognition/src/main/java/
```
Update `props.put("origin", "drive-proposal")` → `props.put("recognitionSource", "drive-proposal")`

- [ ] **Step 6: Run full test suite for affected modules**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence,memory-seeding,cognition
```

- [ ] **Step 7: Commit**

```bash
git add mindmap-intelligence/ memory-seeding/ cognition/
git commit -m "refactor(#540): rename Goallike.origin() to recognitionSource()

Atomic rename across all four goal creation paths: GoalHandler,
GoalRecognitionPhase, DriveGoalBridgeParticipant. Property key
'origin' → 'recognitionSource' for ThingProxyHandler compatibility.

Refs #540"
```

### Task 3: Add taxonomy accessors to Goallike + vocabulary constants to GoalVocabulary

**Files:**
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Goallike.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/GoallikeTest.java`
- Modify: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/GoalVocabulary.java`
- Modify: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/GoalVocabularyTest.java`

**Interfaces:**
- Produces: `Goallike.contentDomain()`, `contentSubdomain()`, `motivationOrigin()`, `clarity()`, `evidenceBasis()`
- Produces: `GoalVocabulary.CONTENT_DOMAINS`, `MOTIVATION_ORIGINS`, `CONTENT_SUBDOMAINS` constant sets

- [ ] **Step 1: Write failing tests for new Goallike accessors**

```java
@Test
void contentDomainReturnsValue() {
    var node = createNodeWithProperty("contentDomain", "mastery-and-competence");
    var goal = node.as(Goallike.class);
    assertEquals(Optional.of("mastery-and-competence"), goal.contentDomain());
}

@Test
void clarityReturnsStringValue() {
    var node = createNodeWithProperty("clarity", "0.8");
    var goal = node.as(Goallike.class);
    assertEquals(Optional.of("0.8"), goal.clarity());
}

@Test
void motivationOriginReturnsValue() {
    var node = createNodeWithProperty("motivationOrigin", "intrinsic");
    var goal = node.as(Goallike.class);
    assertEquals(Optional.of("intrinsic"), goal.motivationOrigin());
}
```

- [ ] **Step 2: Run tests — verify compilation failure**

- [ ] **Step 3: Add accessors to Goallike interface**

```java
public interface Goallike {
    Optional<String> description();
    Optional<String> status();
    Optional<String> horizon();
    Optional<String> recognitionSource();
    Optional<String> resolution();
    Optional<String> urgency();
    Optional<String> feasibility();
    Optional<String> contentDomain();
    Optional<String> contentSubdomain();
    Optional<String> motivationOrigin();
    Optional<String> clarity();
    Optional<String> evidenceBasis();
}
```

- [ ] **Step 4: Run Goallike tests — verify PASS**

- [ ] **Step 5: Write failing test for GoalVocabulary constants**

```java
@Test
void contentDomainsHasNineValues() {
    assertEquals(9, GoalVocabulary.CONTENT_DOMAINS.size());
    assertTrue(GoalVocabulary.CONTENT_DOMAINS.contains("mastery-and-competence"));
    assertTrue(GoalVocabulary.CONTENT_DOMAINS.contains("self-actualisation"));
}

@Test
void motivationOriginsHasFourValues() {
    assertEquals(4, GoalVocabulary.MOTIVATION_ORIGINS.size());
    assertTrue(GoalVocabulary.MOTIVATION_ORIGINS.contains("intrinsic"));
}

@Test
void contentSubdomainsHas25Values() {
    assertEquals(25, GoalVocabulary.CONTENT_SUBDOMAINS.size());
    assertTrue(GoalVocabulary.CONTENT_SUBDOMAINS.contains("self-efficacy"));
}
```

- [ ] **Step 6: Add constants to GoalVocabulary**

```java
public static final Set<String> CONTENT_DOMAINS = Set.of(
    "morality-and-virtue", "religion-and-spirituality", "self-actualisation",
    "avoidance", "social-relating", "health", "family",
    "mastery-and-competence", "financial-and-occupational");

public static final Set<String> MOTIVATION_ORIGINS = Set.of(
    "intrinsic", "identified", "introjected", "external");

public static final Set<String> CONTENT_SUBDOMAINS = Set.of(
    "social-values", "personal-morals", "help-others", "highly-regarded",
    "religion-and-spirituality",
    "wisdom-and-serenity", "self-knowledge-and-happiness", "appreciating-beauty",
    "exploration-and-passions", "enjoy-life",
    "avoid-stress-harm-rejection-conflict", "avoid-hassles",
    "relate-and-belong", "intimacy", "stability", "power", "leadership",
    "health", "family",
    "achievement", "self-efficacy", "practical-competence", "intellectual-competence",
    "finances", "occupational-success");
```

- [ ] **Step 7: Run GoalVocabulary tests — verify PASS**

- [ ] **Step 8: Run full module tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,mindmap-intelligence
```

- [ ] **Step 9: Commit**

```bash
git add mindmap-api/ mindmap-intelligence/
git commit -m "feat(#540): add taxonomy accessors to Goallike + vocabulary constants

contentDomain (Talevich Y-level), contentSubdomain (W-level),
motivationOrigin (SDT), clarity (Emmons), evidenceBasis.
GoalVocabulary: CONTENT_DOMAINS (9), MOTIVATION_ORIGINS (4),
CONTENT_SUBDOMAINS (25).

Refs #540"
```

### Task 4: Extend GoalEntry + GoalHandler with taxonomy fields

**Files:**
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalEntry.java`
- Modify: `memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/GoalHandler.java`
- Modify: `memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/GoalHandlerTest.java`

**Interfaces:**
- Consumes: `GoalVocabulary.CONTENT_DOMAINS`, `MOTIVATION_ORIGINS`, `CONTENT_SUBDOMAINS`
- Produces: GoalHandler writes taxonomy fields as node properties with validation

- [ ] **Step 1: Write failing test for GoalHandler with taxonomy fields**

```java
@Test
void handleWritesTaxonomyProperties() {
    var entry = new GoalEntry("g1", null, "STATED", "Master painting",
        "thematic", "long",
        "active", "0.8", "0.7", "0.9", "SELF_EXPRESSION",
        "mastery-and-competence", "achievement", "intrinsic",
        0.85, "Pattern of daily practice across §4-§8",
        null, null, null);
    // ... set up profile with this entry, call handler
    // assert node has property "contentDomain" = "mastery-and-competence"
    // assert node has property "motivationOrigin" = "intrinsic"
    // assert node has property "clarity" = "0.85"
    // assert node has property "evidenceBasis" = "Pattern of daily practice across §4-§8"
}

@Test
void handleRejectsInvalidContentDomain() {
    var entry = new GoalEntry("g1", null, "STATED", "Master painting",
        "thematic", "long",
        null, null, null, null, null,
        "invalid-domain", null, "intrinsic",
        null, null, null, null, null);
    // ... call handler, expect rejection or warning log
}
```

- [ ] **Step 2: Run test — verify compilation failure**

- [ ] **Step 3: Extend GoalEntry record**

Add the new fields per spec §6.2:

```java
@JsonIgnoreProperties(ignoreUnknown = true)
public record GoalEntry(
    String id,
    @JsonProperty("source_ref") String sourceRef,
    @JsonProperty("confidence_origin") String confidenceOrigin,
    String name,
    String tier,
    String horizon,
    String status,
    String urgency,
    String priority,
    String feasibility,
    @JsonProperty("need_tier") String needTier,
    @JsonProperty("content_domain") String contentDomain,
    @JsonProperty("content_subdomain") String contentSubdomain,
    @JsonProperty("motivation_origin") String motivationOrigin,
    Double clarity,
    @JsonProperty("evidence_basis") String evidenceBasis,
    List<Dependency> dependencies,
    PadValues pad,
    @JsonProperty("sub_goals") List<SubGoal> subGoals
) {
    @JsonIgnoreProperties(ignoreUnknown = true)
    public record Dependency(String ref, @JsonProperty("edge_type") String edgeType) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record SubGoal(String id, String tier, String description) {}

    @JsonIgnoreProperties(ignoreUnknown = true)
    public record PadValues(Double pleasure, Double arousal, Double dominance) {}
}
```

- [ ] **Step 4: Update GoalHandler to write new properties with validation**

After existing property writes, add:

```java
// Previously-missing extraction fields
if (entry.status() != null) props.put("status", entry.status());
if (entry.urgency() != null) props.put("urgency", entry.urgency());
if (entry.priority() != null) props.put("priority", entry.priority());
if (entry.feasibility() != null) props.put("feasibility", entry.feasibility());
if (entry.needTier() != null) props.put("need-tier", entry.needTier());

// Taxonomy fields — validate against GoalVocabulary
if (entry.contentDomain() != null) {
    if (GoalVocabulary.CONTENT_DOMAINS.contains(entry.contentDomain())) {
        props.put("contentDomain", entry.contentDomain());
    } else {
        log.warn("Rejected invalid contentDomain '{}' for goal '{}'", entry.contentDomain(), entry.name());
    }
}
if (entry.contentSubdomain() != null) {
    if (GoalVocabulary.CONTENT_SUBDOMAINS.contains(entry.contentSubdomain())) {
        props.put("contentSubdomain", entry.contentSubdomain());
    } else {
        log.warn("Rejected invalid contentSubdomain '{}' for goal '{}'", entry.contentSubdomain(), entry.name());
    }
}
if (entry.motivationOrigin() != null) {
    if (GoalVocabulary.MOTIVATION_ORIGINS.contains(entry.motivationOrigin())) {
        props.put("motivationOrigin", entry.motivationOrigin());
    } else {
        log.warn("Rejected invalid motivationOrigin '{}' for goal '{}'", entry.motivationOrigin(), entry.name());
    }
}
if (entry.clarity() != null) props.put("clarity", String.valueOf(entry.clarity()));
if (entry.evidenceBasis() != null) props.put("evidenceBasis", entry.evidenceBasis());

// Rename origin property key
props.put("recognitionSource", "biographical-import");
```

Add `GoalVocabulary` import and logger to GoalHandler.

- [ ] **Step 5: Run tests — verify PASS**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding -Dtest=GoalHandlerTest
```

- [ ] **Step 6: Commit**

```bash
git add memory-seeding/
git commit -m "feat(#540): extend GoalEntry + GoalHandler with taxonomy fields

GoalEntry adds: status, urgency, priority, feasibility, needTier,
contentDomain, contentSubdomain, motivationOrigin, clarity, evidenceBasis.
GoalHandler validates domain/origin/subdomain against GoalVocabulary
constants, writes recognitionSource instead of origin.

Refs #540"
```

### Task 5: Update field registry with new goal fields

**Files:**
- Modify: `extraction/docs/field-registry.yaml` (after migration)

- [ ] **Step 1: Add new fields to field-registry.yaml**

Add under `node_fields`:

```yaml
- id: N24
  name: goal_content_domain
  ref: "Talevich Y-level"
  stages: [extraction, corpus, importer]
  type_filter: goal
- id: N25
  name: goal_content_subdomain
  ref: "Talevich W-level"
  stages: [extraction, corpus, importer]
  type_filter: goal
- id: N26
  name: goal_motivation_origin
  ref: "SDT"
  stages: [extraction, corpus, importer]
  type_filter: goal
- id: N27
  name: goal_clarity
  ref: "Emmons SAS"
  stages: [extraction, corpus, importer]
  type_filter: goal
- id: N28
  name: goal_evidence_basis
  ref: "§6.4"
  stages: [extraction, corpus, importer]
  type_filter: goal
```

- [ ] **Step 2: Update coverage checker for new fields**

Add to `_NODE_CHECKERS` in `extraction/scripts/coverage.py`:

```python
'goal_content_domain': lambda e: bool(e.get('goal_content_domain')),
'goal_motivation_origin': lambda e: bool(e.get('goal_motivation_origin')),
'goal_clarity': lambda e: e.get('goal_clarity') is not None,
'goal_evidence_basis': lambda e: bool(e.get('goal_evidence_basis')) or e.get('confidence', {}).get('origin') == 'SPECULATED',
```

- [ ] **Step 3: Run coverage tests**

```bash
extraction/scripts/.venv/bin/python3 -m pytest extraction/tests/test_coverage.py -v
```

- [ ] **Step 4: Commit**

```bash
git add extraction/
git commit -m "feat(#540): add taxonomy fields to field registry + coverage checkers

N24-N28: goal_content_domain, goal_content_subdomain, goal_motivation_origin,
goal_clarity, goal_evidence_basis. Coverage checker accounts for
SPECULATED goals having null evidence_basis.

Refs #540"
```

## Batch 3: Extraction Prompt + Vocabulary Enforcement (#541, #544, #545)

### Task 6: Update GOAL_SYSTEM extraction prompt with taxonomy fields

**Files:**
- Modify: `extraction/scripts/extract_structure.py` — GOAL_SYSTEM prompt

Update the GOAL_SYSTEM prompt per spec §4.1 — add `goal_content_domain` (9 values), `goal_content_subdomain` (25 values, optional), `goal_motivation_origin` (4 values), `goal_clarity`, `goal_evidence_basis`, and calibrated confidence guidance.

- [ ] **Step 1:** Update GOAL_SYSTEM prompt string in `extract_structure.py`
- [ ] **Step 2:** Run 3-passage subset to verify goals have new fields
- [ ] **Step 3:** Commit

### Task 7: Add goal vocabulary normalisation to assembler

**Files:**
- Modify: `extraction/scripts/assemble_corpus.py` — add `normalise_goal_vocabulary()`

Add normalisation maps per spec §5.3 for content domain, motivation origin. Add content domain guard to mechanical dedup (spec §5.1).

- [ ] **Step 1:** Add `normalise_goal_vocabulary()` function with normalisation maps
- [ ] **Step 2:** Wire into assembly pipeline after extraction, before dedup
- [ ] **Step 3:** Add content domain guard to `dedup_goals()` — same-domain requirement, null-domain skip
- [ ] **Step 4:** Run 3-passage subset to verify normalisation
- [ ] **Step 5:** Commit

### Task 8: Lifecycle vocabulary normalisation (#545)

**Files:**
- Modify: `extraction/scripts/assemble_corpus.py` — add lifecycle normalisation

Map ad-hoc lifecycle event labels to standard set. Flag subject-projected events.

- [ ] **Step 1:** Add normalisation map for lifecycle labels
- [ ] **Step 2:** Wire into assembly
- [ ] **Step 3:** Run subset to verify
- [ ] **Step 4:** Commit

### Task 9: Entity name normalisation (#546)

**Files:**
- Modify: `extraction/scripts/assemble_corpus.py` — add entity dedup

Same pattern as goal dedup — Jaro-Winkler + Jaccard for all entity types. Merge "Frida" into "Frida Kahlo".

- [ ] **Step 1:** Add `dedup_entities()` function
- [ ] **Step 2:** Wire into assembly after node construction
- [ ] **Step 3:** Run subset to verify "Frida"/"Frida Kahlo" merge
- [ ] **Step 4:** Commit

## Batch 4: Cross-Tier Linking + LLM Dedup (#542)

### Task 10: Cross-tier edge linking in assembler

**Files:**
- Modify: `extraction/scripts/assemble_corpus.py`

Group goals by content domain, create `contributes-to` edges from tactical to thematic/strategic within same domain.

- [ ] **Step 1:** Add `create_cross_tier_edges()` function
- [ ] **Step 2:** Wire after dedup, before final corpus assembly
- [ ] **Step 3:** Run subset, verify edges created
- [ ] **Step 4:** Commit

### Task 11: LLM semantic dedup (Phase 2 dedup)

**Files:**
- Modify: `extraction/scripts/assemble_corpus.py`

Batch near-miss candidates (≤20 per call) to LLM for DUPLICATE/RELATED/DISTINCT. Union-find for transitivity. Max 2 convergence rounds.

- [ ] **Step 1:** Add `llm_semantic_dedup()` function
- [ ] **Step 2:** Wire after mechanical pre-filter
- [ ] **Step 3:** Run subset, verify classifications
- [ ] **Step 4:** Commit

## Batch 5: Runtime Path Alignment + GoalResolutionPhase (#540)

### Task 12: Update GoalResolutionPhase.merge() with content domain guard

**Files:**
- Modify: `mindmap-intelligence/.../consolidation/GoalResolutionPhase.java`
- Modify: test file

Add content domain guard per spec §6.5 — require matching contentDomain, raise threshold to 0.90, null-domain skip.

- [ ] **Step 1:** Write failing test
- [ ] **Step 2:** Add content domain guard to merge()
- [ ] **Step 3:** Run tests, verify PASS
- [ ] **Step 4:** Commit

### Task 13: Taxonomy propagation in GoalResolutionPhase.expand()

**Files:**
- Modify: `mindmap-intelligence/.../consolidation/GoalResolutionPhase.java`

Per spec §6.4 — propagate contentDomain and motivationOrigin from parent to sub-goals.

- [ ] **Step 1:** Write failing test
- [ ] **Step 2:** Add propagation after sub-goal creation
- [ ] **Step 3:** Run tests, verify PASS
- [ ] **Step 4:** Commit

## Batch 6: Full Run + Re-Import (#529)

### Task 14: Full pipeline run with taxonomy

- [ ] **Step 1:** Run 3-passage subset: `bash extraction/scripts/iterate.sh --limit 3 --label "taxonomy-v1"`
- [ ] **Step 2:** Verify all new fields populated, coverage gates pass
- [ ] **Step 3:** Run full pipeline: `bash extraction/scripts/iterate.sh --limit 0 --label "taxonomy-full"`
- [ ] **Step 4:** Compare against previous baseline
- [ ] **Step 5:** Re-import via BiographyImportRunner
- [ ] **Step 6:** Verify taxonomy fields appear in MindMap goal nodes
- [ ] **Step 7:** Commit final corpus + close #529

## Batch 7: Affinity Profile (#543) — Deferred

### Task 15: AffinityDefaults record + YAML schema

Deferred to a separate session. Depends on all prior batches landing. See spec §3.6.

---

## References

- [specs/2026-10-11-goal-motivation-model-extension-design.md] — design spec (reviewed)
- [specs/2026-10-11-goal-motivation-taxonomy-rnd.md] — research doc
- [mindmap-intelligence/.../Goallike.java:5] — current trait interface
- [mindmap-api/.../GoalVocabulary.java:3] — current vocabulary
- [memory-seeding/.../GoalEntry.java:9] — current entry record
- [memory-seeding/.../GoalHandler.java:19] — current handler
- [GitHub #538] — epic
- [GitHub #539-#549] — child issues
