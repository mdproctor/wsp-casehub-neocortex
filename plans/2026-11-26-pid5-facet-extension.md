# PID-5 Facet Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #1076 — PID5-facet-situational-attractor
**Issue group:** #1076

**Goal:** Extend the PID-5 facet system from 13 to 25 facets across classification, situational modulation, and cognitive derivation pipelines.

**Architecture:** Cross-repo change. Eidos owns the AMPD facet vocabulary (`AmpdFacets.CANONICAL`) and archetype situational profiles. Neocortex owns `PersonalityFacet` constants, `CognitiveDerivationEngine` rules, `PersonalityPromptBuilder`, and biography import handling. Eidos changes land first; neocortex consumes the updated eidos.

**Tech Stack:** Java 21, Quarkus 3.32.2, eidos (cross-repo), YAML archetype profiles

## Global Constraints

- All CDE coefficients for new Negative Affectivity facets must be ≤ ±0.1 to avoid multicollinearity stacking with existing NA facets (Anxiousness, Emotional Lability, Hostility, Suspiciousness)
- Tier 1 facets use coefficient magnitudes 0.1–0.4 (depending on domain concentration); Tier 2 use 0.1–0.2
- Situational deltas: STRONG evidence → ±10–15, MODERATE → ±5–10, WEAK → omit
- Every CDE rule must include a Javadoc citation (author, year, key finding)
- Facet name strings must match `AmpdFacets.CANONICAL` exactly (space-separated words, title case)

---

## Batch 1: Eidos foundation — AMPD vocabulary + archetype profiles

### Task 1: Extend AmpdFacets.CANONICAL and archetype situational profiles

**Files:**
- Modify: `eidos: api/src/main/java/io/casehub/eidos/api/AmpdFacets.java:10-14`
- Modify: `eidos: vocab/src/main/resources/META-INF/eidos/archetype-situational-profiles.yaml`
- Test: `eidos: api/src/test/java/io/casehub/eidos/api/AmpdFacetsTest.java`

**Interfaces:**
- Produces: 25-element `AmpdFacets.CANONICAL` set consumed by `AmpdFacetShift` validation and `SituationalDeltaConverter`

- [ ] **Step 1: Write failing test for 25 facets**

Add a test verifying CANONICAL contains all 25 facets:

```java
@Test
void canonical_contains25Facets() {
    assertEquals(25, AmpdFacets.CANONICAL.size());
    assertTrue(AmpdFacets.CANONICAL.contains("Anhedonia"));
    assertTrue(AmpdFacets.CANONICAL.contains("Depressivity"));
    assertTrue(AmpdFacets.CANONICAL.contains("Perseveration"));
    assertTrue(AmpdFacets.CANONICAL.contains("Rigid Perfectionism"));
    assertTrue(AmpdFacets.CANONICAL.contains("Distractibility"));
    assertTrue(AmpdFacets.CANONICAL.contains("Separation Insecurity"));
    assertTrue(AmpdFacets.CANONICAL.contains("Restricted Affectivity"));
    assertTrue(AmpdFacets.CANONICAL.contains("Irresponsibility"));
    assertTrue(AmpdFacets.CANONICAL.contains("Cognitive Perceptual Dysregulation"));
    assertTrue(AmpdFacets.CANONICAL.contains("Eccentricity"));
    assertTrue(AmpdFacets.CANONICAL.contains("Submissiveness"));
    assertTrue(AmpdFacets.CANONICAL.contains("Unusual Beliefs"));
}

@Test
void canonicalise_newFacets() {
    assertEquals("Anhedonia", AmpdFacets.canonicalise("anhedonia"));
    assertEquals("Rigid Perfectionism", AmpdFacets.canonicalise("rigid perfectionism"));
    assertEquals("Cognitive Perceptual Dysregulation",
            AmpdFacets.canonicalise("cognitive perceptual dysregulation"));
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl api -Dtest=AmpdFacetsTest -f /Users/mdproctor/claude/casehub/slots/229/eidos/pom.xml`
Expected: FAIL — CANONICAL has 13 elements, not 25

- [ ] **Step 3: Add 12 facets to AmpdFacets.CANONICAL**

Update `AmpdFacets.java` line 10-14:

```java
public static final Set<String> CANONICAL = Set.of(
        "Anxiousness", "Callousness", "Deceitfulness", "Emotional Lability",
        "Grandiosity", "Hostility", "Impulsivity", "Intimacy Avoidance",
        "Manipulativeness", "Risk Taking", "Suspiciousness", "Withdrawal",
        "Attention Seeking",
        "Anhedonia", "Depressivity", "Perseveration", "Rigid Perfectionism",
        "Distractibility", "Separation Insecurity", "Restricted Affectivity",
        "Irresponsibility", "Cognitive Perceptual Dysregulation", "Eccentricity",
        "Submissiveness", "Unusual Beliefs");
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl api -Dtest=AmpdFacetsTest -f /Users/mdproctor/claude/casehub/slots/229/eidos/pom.xml`
Expected: PASS

- [ ] **Step 5: Add situational shifts to archetype-situational-profiles.yaml**

For each of the 12 archetype families, add `AmpdFacetShift` entries for the new facets per the spec's Section 3 tables. Each family gets shifts appropriate to its archetype character. Example for `caregiver` family — add after the existing shifts:

```yaml
  caregiver:
    stress:
      provenance: estimated
      shifts:
        # ... existing shifts ...
        - {facet: Anhedonia, delta: 12}
        - {facet: Depressivity, delta: 15}
        - {facet: Perseveration, delta: 12}
        - {facet: Separation Insecurity, delta: 12}
        - {facet: Distractibility, delta: 12}
        - {facet: Restricted Affectivity, delta: 8}
        - {facet: Irresponsibility, delta: 6}
        - {facet: Eccentricity, delta: 6}
        - {facet: Submissiveness, delta: 8}
        - {facet: Cognitive Perceptual Dysregulation, delta: 12}
        - {facet: Unusual Beliefs, delta: 6}
    flow:
      provenance: estimated
      shifts:
        # ... existing shifts ...
        - {facet: Depressivity, delta: -12}
        - {facet: Distractibility, delta: -15}
        - {facet: Anhedonia, delta: -8}
        - {facet: Rigid Perfectionism, delta: -8}
        - {facet: Eccentricity, delta: 8}
        - {facet: Cognitive Perceptual Dysregulation, delta: 6}
    # ... similarly for social_collaborative, social_competitive, social_hierarchical
```

Repeat for all 12 families. Use the spec's Section 3 delta tables as the base values. Archetype-specific modulation: adjust deltas ±3 based on the family's character (e.g., `caregiver` gets higher Separation Insecurity stress shift; `rebel` gets lower Submissiveness hierarchical shift).

- [ ] **Step 6: Run full eidos test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -f /Users/mdproctor/claude/casehub/slots/229/eidos/pom.xml`
Expected: PASS

- [ ] **Step 7: Commit eidos changes**

```bash
git -C /Users/mdproctor/claude/casehub/slots/229/eidos add api/src/main/java/io/casehub/eidos/api/AmpdFacets.java vocab/src/main/resources/META-INF/eidos/archetype-situational-profiles.yaml api/src/test/java/io/casehub/eidos/api/AmpdFacetsTest.java
git -C /Users/mdproctor/claude/casehub/slots/229/eidos commit -m "feat(api): extend AmpdFacets.CANONICAL to 25 PID-5 facets + archetype profiles

Add 12 missing PID-5 facets: Anhedonia, Depressivity, Perseveration,
Rigid Perfectionism, Distractibility, Separation Insecurity, Restricted
Affectivity, Irresponsibility, Cognitive Perceptual Dysregulation,
Eccentricity, Submissiveness, Unusual Beliefs.

Add situational attractor profile shifts for all 12 families × 5 modes
based on literature review (stress/flow/social modulation evidence).

Refs casehubio/neocortex#1076"
```

- [ ] **Step 8: Install eidos locally**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -DskipTests -f /Users/mdproctor/claude/casehub/slots/229/eidos/pom.xml`
Expected: BUILD SUCCESS — updated eidos available in local Maven repo

---

## Batch 2: Neocortex PersonalityFacet constants + CDE derivation rules

### Task 2: Add PersonalityFacet constants and extend CDE derivation rules

**Files:**
- Modify: `neocortex: cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PersonalityFacet.java:8-20`
- Modify: `neocortex: cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java` (multiple derivation methods)
- Test: `neocortex: cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEnginePid5FacetTest.java`

**Interfaces:**
- Consumes: `AmpdFacets.CANONICAL` (25 elements, from Batch 1 eidos install)
- Produces: `PersonalityFacet` constants consumed by `PersonalityPromptBuilder`, `PersonalityMetadataEnricher`, `PersonalityProfileHandler`; CDE rules consumed by `CognitiveDerivationEngine.derive()`

- [ ] **Step 1: Add 12 PersonalityFacet constants**

Add after existing constants (line 20) in `PersonalityFacet.java`:

```java
public static final String ANHEDONIA = "Anhedonia";
public static final String DEPRESSIVITY = "Depressivity";
public static final String PERSEVERATION = "Perseveration";
public static final String RIGID_PERFECTIONISM = "Rigid Perfectionism";
public static final String DISTRACTIBILITY = "Distractibility";
public static final String SEPARATION_INSECURITY = "Separation Insecurity";
public static final String RESTRICTED_AFFECTIVITY = "Restricted Affectivity";
public static final String IRRESPONSIBILITY = "Irresponsibility";
public static final String COGNITIVE_PERCEPTUAL_DYSREGULATION = "Cognitive Perceptual Dysregulation";
public static final String ECCENTRICITY = "Eccentricity";
public static final String SUBMISSIVENESS = "Submissiveness";
public static final String UNUSUAL_BELIEFS = "Unusual Beliefs";
```

- [ ] **Step 2: Write failing tests for new CDE rules**

Add to `CognitiveDerivationEnginePid5FacetTest.java`. Follow the existing pattern — each test creates a `DescriptorView` with one facet at an extreme value (0.9) and asserts the derived parameter shifted in the expected direction vs a neutral (0.5) baseline.

**Tier 1 facet tests (6 facets × 3-6 parameters each = ~25 tests):**

```java
// Anhedonia
@Test
void moodBaseline_anhedoniaReducesPleasure() {
    var defaults = derive(facetsOf(PersonalityFacet.ANHEDONIA, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.ANHEDONIA, 0.5));
    assertTrue(defaults.moodBaseline().pleasure() < neutral.moodBaseline().pleasure());
}

@Test
void moodBaseline_anhedoniaReducesArousal() {
    var defaults = derive(facetsOf(PersonalityFacet.ANHEDONIA, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.ANHEDONIA, 0.5));
    assertTrue(defaults.moodBaseline().arousal() < neutral.moodBaseline().arousal());
}

@Test
void searchBudget_anhedoniaReducesDepth() {
    var defaults = derive(facetsOf(PersonalityFacet.ANHEDONIA, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.ANHEDONIA, 0.5));
    assertTrue(defaults.searchBudget().depthMidpoint() < neutral.searchBudget().depthMidpoint());
}

@Test
void pool_anhedoniaReducesMaxEffort() {
    var defaults = derive(facetsOf(PersonalityFacet.ANHEDONIA, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.ANHEDONIA, 0.5));
    assertTrue(defaults.poolConfig().maxEffort() < neutral.poolConfig().maxEffort());
}

// Depressivity
@Test
void moodBaseline_depressivityReducesPleasure() {
    var defaults = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.5));
    assertTrue(defaults.moodBaseline().pleasure() < neutral.moodBaseline().pleasure());
}

@Test
void moodBaseline_depressivityReducesDominance() {
    var defaults = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.5));
    assertTrue(defaults.moodBaseline().dominance() < neutral.moodBaseline().dominance());
}

@Test
void recurringThought_depressivityLowersRuminationThreshold() {
    var defaults = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.5));
    assertTrue(defaults.recurringThoughtConfig().ruminationThreshold()
            < neutral.recurringThoughtConfig().ruminationThreshold());
}

@Test
void capacity_depressivityReducesWorkingMemory() {
    var defaults = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.5));
    assertTrue(defaults.capacity().workingMemorySpan() < neutral.capacity().workingMemorySpan());
}

@Test
void appraisal_depressivityReducesConduciveness() {
    var defaults = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DEPRESSIVITY, 0.5));
    assertTrue(defaults.appraisalWeights().conduciveness()
            < neutral.appraisalWeights().conduciveness());
}

// Perseveration
@Test
void recurringThought_perseverationLowersFixation() {
    var defaults = derive(facetsOf(PersonalityFacet.PERSEVERATION, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.PERSEVERATION, 0.5));
    assertTrue(defaults.recurringThoughtConfig().fixationThreshold()
            < neutral.recurringThoughtConfig().fixationThreshold());
}

@Test
void searchBudget_perseverationReducesLaterality() {
    var defaults = derive(facetsOf(PersonalityFacet.PERSEVERATION, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.PERSEVERATION, 0.5));
    assertTrue(defaults.searchBudget().lateralityMidpoint()
            < neutral.searchBudget().lateralityMidpoint());
}

@Test
void searchBudget_perseverationIncreasesConvergence() {
    var defaults = derive(facetsOf(PersonalityFacet.PERSEVERATION, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.PERSEVERATION, 0.5));
    assertTrue(defaults.searchBudget().convergenceMidpoint()
            > neutral.searchBudget().convergenceMidpoint());
}

// Rigid Perfectionism
@Test
void recurringThought_rigidPerfectionismLowersFixation() {
    var defaults = derive(facetsOf(PersonalityFacet.RIGID_PERFECTIONISM, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.RIGID_PERFECTIONISM, 0.5));
    assertTrue(defaults.recurringThoughtConfig().fixationThreshold()
            < neutral.recurringThoughtConfig().fixationThreshold());
}

@Test
void pool_rigidPerfectionismIncreasesMaxEffort() {
    var defaults = derive(facetsOf(PersonalityFacet.RIGID_PERFECTIONISM, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.RIGID_PERFECTIONISM, 0.5));
    assertTrue(defaults.poolConfig().maxEffort() > neutral.poolConfig().maxEffort());
}

// Distractibility
@Test
void capacity_distractibilityReducesWorkingMemory() {
    var defaults = derive(facetsOf(PersonalityFacet.DISTRACTIBILITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DISTRACTIBILITY, 0.5));
    assertTrue(defaults.capacity().workingMemorySpan() < neutral.capacity().workingMemorySpan());
}

@Test
void searchBudget_distractibilityReducesDepth() {
    var defaults = derive(facetsOf(PersonalityFacet.DISTRACTIBILITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DISTRACTIBILITY, 0.5));
    assertTrue(defaults.searchBudget().depthMidpoint() < neutral.searchBudget().depthMidpoint());
}

@Test
void searchBudget_distractibilityIncreasesBreadth() {
    var defaults = derive(facetsOf(PersonalityFacet.DISTRACTIBILITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DISTRACTIBILITY, 0.5));
    assertTrue(defaults.searchBudget().breadthSteepness() > neutral.searchBudget().breadthSteepness());
}

// Separation Insecurity
@Test
void recurringThought_separationInsecurityLowersFixation() {
    var defaults = derive(facetsOf(PersonalityFacet.SEPARATION_INSECURITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.SEPARATION_INSECURITY, 0.5));
    assertTrue(defaults.recurringThoughtConfig().fixationThreshold()
            < neutral.recurringThoughtConfig().fixationThreshold());
}

@Test
void extractionBias_separationInsecurityIncreasesRelationship() {
    var defaults = derive(facetsOf(PersonalityFacet.SEPARATION_INSECURITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.SEPARATION_INSECURITY, 0.5));
    assertTrue(defaults.extractionBias().relationshipBias()
            > neutral.extractionBias().relationshipBias());
}
```

**Tier 2 facet tests (~8 tests) + backfill tests (~3 tests) + multicollinearity guard test (1 test):**

```java
// Restricted Affectivity
@Test
void extractionBias_restrictedAffectivityReducesAffectSensitivity() {
    var defaults = derive(facetsOf(PersonalityFacet.RESTRICTED_AFFECTIVITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.RESTRICTED_AFFECTIVITY, 0.5));
    assertTrue(defaults.extractionBias().affectSensitivity()
            < neutral.extractionBias().affectSensitivity());
}

// Irresponsibility
@Test
void pool_irresponsibilityReducesMaxEffort() {
    var defaults = derive(facetsOf(PersonalityFacet.IRRESPONSIBILITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.IRRESPONSIBILITY, 0.5));
    assertTrue(defaults.poolConfig().maxEffort() < neutral.poolConfig().maxEffort());
}

// Eccentricity
@Test
void searchBudget_eccentricityIncreasesLaterality() {
    var defaults = derive(facetsOf(PersonalityFacet.ECCENTRICITY, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.ECCENTRICITY, 0.5));
    assertTrue(defaults.searchBudget().lateralityMidpoint()
            > neutral.searchBudget().lateralityMidpoint());
}

// Cognitive Perceptual Dysregulation
@Test
void capacity_cogPerceptualDysregulationReducesWorkingMemory() {
    var defaults = derive(facetsOf(PersonalityFacet.COGNITIVE_PERCEPTUAL_DYSREGULATION, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.COGNITIVE_PERCEPTUAL_DYSREGULATION, 0.5));
    assertTrue(defaults.capacity().workingMemorySpan() < neutral.capacity().workingMemorySpan());
}

// Backfill: Deceitfulness
@Test
void searchBudget_deceitfulnessIncreasesLaterality() {
    var defaults = derive(facetsOf(PersonalityFacet.DECEITFULNESS, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.DECEITFULNESS, 0.5));
    assertTrue(defaults.searchBudget().lateralityMidpoint()
            > neutral.searchBudget().lateralityMidpoint());
}

// Backfill: Attention Seeking
@Test
void moodBaseline_attentionSeekingIncreasesArousal() {
    var defaults = derive(facetsOf(PersonalityFacet.ATTENTION_SEEKING, 0.9));
    var neutral = derive(facetsOf(PersonalityFacet.ATTENTION_SEEKING, 0.5));
    assertTrue(defaults.moodBaseline().arousal() > neutral.moodBaseline().arousal());
}

// Multicollinearity guard: stacking 3 NA facets should not produce implausible values
@Test
void multicollinearity_stackedNegativeAffectFacetsStayBounded() {
    var facets = List.of(
            new PersonalityFacet(PersonalityFacet.ANXIOUSNESS, 0.9, "test"),
            new PersonalityFacet(PersonalityFacet.DEPRESSIVITY, 0.9, "test"),
            new PersonalityFacet(PersonalityFacet.PERSEVERATION, 0.9, "test"));
    var defaults = derive(facets);
    // fixationThreshold should not go below 0 or become implausibly negative
    assertTrue(defaults.recurringThoughtConfig().fixationThreshold() > 0.0,
            "Stacked NA facets drove fixationThreshold below zero");
    // ruminationThreshold should stay positive
    assertTrue(defaults.recurringThoughtConfig().ruminationThreshold() > 0.0,
            "Stacked NA facets drove ruminationThreshold below zero");
}
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDerivationEnginePid5FacetTest`
Expected: FAIL — new facet constants exist but CDE methods don't reference them yet

- [ ] **Step 4: Implement CDE derivation rules**

Add facet score lookups and coefficient applications to each CDE derivation method following the spec's Section 2 tables. Use `ide_replace_member` to update each method body. Each rule gets a Javadoc comment with the literature citation.

The pattern for each rule (following existing code conventions in `deriveMoodBaseline`, `deriveCapacity`, etc.):

```java
// In deriveMoodBaseline():
// Anhedonia — Meehl 1975; Germans & Kring 2000
double an = facetScore(facets, PersonalityFacet.ANHEDONIA);
pleasure -= (an - 0.5) * 0.4;
arousal -= (an - 0.5) * 0.3;

// Depressivity — Mehrabian 1996; Seligman 1975
double dp = facetScore(facets, PersonalityFacet.DEPRESSIVITY);
pleasure -= (dp - 0.5) * 0.4;
dominance -= (dp - 0.5) * 0.4;

// Separation Insecurity — Mikulincer & Shaver 2003
double si = facetScore(facets, PersonalityFacet.SEPARATION_INSECURITY);
arousal += (si - 0.5) * 0.15;

// Attention Seeking backfill — HPD clinical literature
double as = facetScore(facets, PersonalityFacet.ATTENTION_SEEKING);
arousal += (as - 0.5) * 0.1;
```

Implement ALL rules from the spec's Section 2 across the following methods:
- `deriveMoodBaseline` — Anhedonia, Depressivity, Separation Insecurity, Attention Seeking
- `deriveAppraisalWeights` — Depressivity (conduciveness, controllability), Separation Insecurity (relevance)
- `deriveSearchBudget` — Anhedonia (depth), Perseveration (laterality, convergence), Rigid Perfectionism (convergence, laterality), Distractibility (depth, breadth), Eccentricity (laterality, breadth), Deceitfulness (laterality, depth)
- `deriveHabituation` — Perseveration (rate, repetitionTolerance), Rigid Perfectionism (rate, repetitionTolerance)
- `deriveExtractionBias` — Separation Insecurity (relationshipBias), Restricted Affectivity (affectSensitivity), Cog/Perceptual Dysregulation (affectSensitivity)
- `deriveRegulation` — Depressivity (reappraisal), Rigid Perfectionism (reappraisal), Separation Insecurity (reappraisal), Restricted Affectivity (reappraisal)
- `deriveRecurringThought` — Depressivity (rumination), Perseveration (fixation), Rigid Perfectionism (fixation), Separation Insecurity (fixation)
- `deriveCapacity` — Depressivity (WM), Distractibility (WM), Cog/Perceptual Dysregulation (WM), Perseveration (associativeReach)
- `derivePoolConfig` — Anhedonia (maxEffort), Depressivity (maxEffort), Rigid Perfectionism (maxEffort), Distractibility (maxEffort), Irresponsibility (maxEffort)
- `deriveCuriosity` — Anhedonia (categoryWeights)
- `deriveCbrStrategy` — Anhedonia (temporalDecay), Irresponsibility (temporalDecay)
- `deriveCoping` — Irresponsibility (via inverse conscientiousness)

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=CognitiveDerivationEnginePid5FacetTest`
Expected: PASS — all ~37 new tests green, multicollinearity guard passes

- [ ] **Step 6: Run full cognitive-index test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: PASS — existing tests unaffected (facetScore returns 0.5 for absent facets)

- [ ] **Step 7: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PersonalityFacet.java cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEnginePid5FacetTest.java
git commit -m "feat(cognitive-index): add 12 PID-5 facet constants + CDE derivation rules

Tier 1 (6 facets): Anhedonia, Depressivity, Perseveration, Rigid
Perfectionism, Distractibility, Separation Insecurity — 37 derivation
rules across mood, appraisal, search budget, habituation, capacity,
regulation, recurring thought, pool, curiosity, CBR strategy.

Tier 2 (4 facets): Restricted Affectivity, Irresponsibility, Cognitive
Perceptual Dysregulation, Eccentricity — 9 derivation rules.

Backfill: Deceitfulness (laterality, depth), Attention Seeking (arousal).

All rules literature-cited. NA facet coefficients capped at ±0.1 for
multicollinearity control.

Refs #1076"
```

---

## Batch 3: Classification pipeline + biography import + integration test

### Task 3: Extend PersonalityPromptBuilder to 25 facets

**Files:**
- Modify: `neocortex: caps-llm-classifier/src/main/java/io/casehub/neocortex/caps/llm/PersonalityPromptBuilder.java`
- Test: `neocortex: caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/PersonalityPromptBuilderTest.java`

**Interfaces:**
- Consumes: `PersonalityFacet` constants (from Task 2)
- Produces: Extended PID-5 prompt text and CBR cache key hash consumed by `LlmSituationClassifier` and `CbrCachingSituationDecorator`

- [ ] **Step 1: Write failing test for 25-facet prompt**

```java
@Test
void pid5Suffix_includes25Facets() {
    Map<String, String> metadata = new LinkedHashMap<>();
    // Add all 25 facets to metadata
    metadata.put("pid5.anxiousness", "0.72");
    metadata.put("pid5.anhedonia", "0.35");
    metadata.put("pid5.depressivity", "0.41");
    // ... all 25 ...
    String suffix = PersonalityPromptBuilder.pid5Suffix(metadata);
    assertNotNull(suffix);
    assertTrue(suffix.contains("Anhedonia"));
    assertTrue(suffix.contains("Depressivity"));
    assertTrue(suffix.contains("Rigid Perfectionism"));
    // Verify all 25 facets present
    assertEquals(25, suffix.lines()
            .filter(line -> line.contains(":"))
            .count());
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=PersonalityPromptBuilderTest`
Expected: FAIL — only 7 facets in allowlist

- [ ] **Step 3: Remove 7-facet allowlist, iterate all facets from metadata**

Update `PersonalityPromptBuilder.pid5Suffix()` to iterate over all `pid5.*` entries in the metadata map rather than checking against a hardcoded 7-element set. Sort by facet name for deterministic ordering.

Also update `personalitySystemPrompt()` (Path C) to include all 25 facets.

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl caps-llm-classifier -Dtest=PersonalityPromptBuilderTest`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add caps-llm-classifier/src/main/java/io/casehub/neocortex/caps/llm/PersonalityPromptBuilder.java caps-llm-classifier/src/test/java/io/casehub/neocortex/caps/llm/PersonalityPromptBuilderTest.java
git commit -m "feat(caps-llm-classifier): extend PersonalityPromptBuilder to 25 facets

Remove 7-facet allowlist. Iterate all pid5.* entries from metadata map,
sorted by facet name for deterministic CBR cache keys.

Refs #1076"
```

### Task 4: Extend AmpdAssessment record + PersonalityProfileHandler

**Files:**
- Modify: `neocortex: memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntry.java`
- Modify: `neocortex: memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandler.java`
- Test: `neocortex: memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntryTest.java`
- Test: `neocortex: memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandlerTest.java`

**Interfaces:**
- Consumes: `PersonalityFacet` constants (from Task 2), `AmpdFacets.CANONICAL` (from Task 1)
- Produces: Biography import support for 25-facet AMPD assessments

- [ ] **Step 1: Write failing test for 25-facet AmpdAssessment**

Add test verifying deserialization of a biography YAML with the new facet fields:

```java
@Test
void ampdAssessment_deserializes25Facets() {
    var yaml = """
            callousness: 30
            anhedonia: 45
            depressivity: 60
            rigid-perfectionism: 70
            """;
    var assessment = mapper.readValue(yaml, PersonalityProfileEntry.AmpdAssessment.class);
    assertEquals(30, assessment.callousness());
    assertEquals(45, assessment.anhedonia());
    assertEquals(60, assessment.depressivity());
    assertEquals(70, assessment.rigidPerfectionism());
}
```

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `anhedonia()`, `depressivity()`, `rigidPerfectionism()` methods don't exist

- [ ] **Step 3: Add 12 Integer fields to AmpdAssessment record**

Add fields with `@JsonProperty` annotations for hyphenated JSON keys:

```java
@JsonProperty("anhedonia") Integer anhedonia,
@JsonProperty("depressivity") Integer depressivity,
@JsonProperty("perseveration") Integer perseveration,
@JsonProperty("rigid-perfectionism") Integer rigidPerfectionism,
@JsonProperty("distractibility") Integer distractibility,
@JsonProperty("separation-insecurity") Integer separationInsecurity,
@JsonProperty("restricted-affectivity") Integer restrictedAffectivity,
@JsonProperty("irresponsibility") Integer irresponsibility,
@JsonProperty("cognitive-perceptual-dysregulation") Integer cognitivePerceptualDysregulation,
@JsonProperty("eccentricity") Integer eccentricity,
@JsonProperty("submissiveness") Integer submissiveness,
@JsonProperty("unusual-beliefs") Integer unusualBeliefs
```

- [ ] **Step 4: Extend PersonalityProfileHandler facet-to-node-property mapping**

Add the new facet mappings in `PersonalityProfileHandler` following the existing pattern for how the handler writes facet scores to MindMap node properties.

- [ ] **Step 5: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-seeding`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileEntry.java memory-seeding/src/main/java/io/casehub/neocortex/memory/seeding/biography/PersonalityProfileHandler.java memory-seeding/src/test/java/io/casehub/neocortex/memory/seeding/biography/
git commit -m "feat(memory-seeding): extend AmpdAssessment + handler for 25 facets

Add 12 Integer fields to AmpdAssessment record with @JsonProperty for
hyphenated YAML keys. Extend PersonalityProfileHandler facet-to-node
property mapping.

Refs #1076"
```

### Task 5: End-to-end integration test

**Files:**
- Create: `neocortex: cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/Pid5FacetPipelineIntegrationTest.java`

**Interfaces:**
- Consumes: `PersonalityFacet` (Task 2), `CognitiveDerivationEngine` (Task 2), `PersonalityMetadataEnricher` (existing)

- [ ] **Step 1: Write integration test**

```java
class Pid5FacetPipelineIntegrationTest {

    @Test
    void endToEnd_25FacetsFlowThroughAllPipelines() {
        // 1. Create descriptor with all 25 facets — some at extreme values
        var facets = List.of(
                new PersonalityFacet(PersonalityFacet.ANHEDONIA, 0.8, "test"),
                new PersonalityFacet(PersonalityFacet.DEPRESSIVITY, 0.75, "test"),
                new PersonalityFacet(PersonalityFacet.RIGID_PERFECTIONISM, 0.85, "test"),
                new PersonalityFacet(PersonalityFacet.DISTRACTIBILITY, 0.7, "test"),
                new PersonalityFacet(PersonalityFacet.ECCENTRICITY, 0.6, "test"),
                // ... remaining facets at neutral 0.5 ...
        );
        var view = new DescriptorView("test-agent", DEFAULT_AXES, BALANCED_PROFILE,
                List.of(), facets);

        // 2. Derive resting defaults
        var resting = CognitiveDerivationEngine.derive(view);

        // 3. Derive with shifted facets (simulating stress mode)
        var stressedFacets = facets.stream()
                .map(f -> switch (f.facet()) {
                    case PersonalityFacet.ANHEDONIA -> new PersonalityFacet(f.facet(),
                            Math.min(1.0, f.score() + 0.12), f.origin());
                    case PersonalityFacet.DEPRESSIVITY -> new PersonalityFacet(f.facet(),
                            Math.min(1.0, f.score() + 0.15), f.origin());
                    default -> f;
                })
                .toList();
        var stressedView = new DescriptorView("test-agent", DEFAULT_AXES, BALANCED_PROFILE,
                List.of(), stressedFacets);
        var effective = CognitiveDerivationEngine.derive(stressedView);

        // 4. Verify resting vs effective differ
        assertTrue(effective.moodBaseline().pleasure() < resting.moodBaseline().pleasure(),
                "Stress should reduce pleasure");
        assertTrue(effective.moodBaseline().dominance() < resting.moodBaseline().dominance(),
                "Stress should reduce dominance");

        // 5. Verify PersonalityMetadataEnricher includes new facets
        var metadata = new java.util.HashMap<String, String>();
        PersonalityMetadataEnricher.enrich(metadata, view);
        assertTrue(metadata.containsKey("pid5.anhedonia"),
                "Metadata should contain anhedonia");
        assertTrue(metadata.containsKey("pid5.depressivity"),
                "Metadata should contain depressivity");

        // 6. Multicollinearity sanity: all values in plausible range
        assertTrue(effective.recurringThoughtConfig().fixationThreshold() > 0.0);
        assertTrue(effective.recurringThoughtConfig().ruminationThreshold() > 0.0);
        assertTrue(effective.moodBaseline().pleasure() >= -1.0);
        assertTrue(effective.capacity().workingMemorySpan() > 0.0);
    }
}
```

- [ ] **Step 2: Run integration test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=Pid5FacetPipelineIntegrationTest`
Expected: PASS

- [ ] **Step 3: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests=false -pl cognitive-index,caps-llm-classifier,memory-seeding,cognition-api,cognition`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/Pid5FacetPipelineIntegrationTest.java
git commit -m "test(cognitive-index): end-to-end 25-facet pipeline integration test

Verifies facets flow through derivation (resting vs stressed), metadata
enrichment, and multicollinearity bounds.

Closes #1076"
```

---

## References

- [2026-11-26-pid5-facet-extension-design.md] — design spec this plan implements
- [cognitive-index/src/main/java/.../CognitiveDerivationEngine.java] — CDE rules target
- [cognitive-index/src/main/java/.../PersonalityFacet.java:3-29] — facet constants
- [cognitive-index/src/test/java/.../CognitiveDerivationEnginePid5FacetTest.java] — existing test pattern
- [caps-llm-classifier/src/main/java/.../PersonalityPromptBuilder.java] — classification pipeline
- [memory-seeding/src/main/java/.../PersonalityProfileEntry.java] — AmpdAssessment record
- [memory-seeding/src/main/java/.../PersonalityProfileHandler.java] — biography import
- [eidos: api/src/main/java/.../AmpdFacets.java:10-14] — CANONICAL set
- [eidos: vocab/src/main/resources/.../archetype-situational-profiles.yaml] — archetype profiles
- [GitHub #1076] — focal issue
- [GitHub #977] — PID-5 facets in situation classification
- [GitHub #712] — situational personality modulation
- [GitHub #1055] — EffectiveCognitiveDefaults
