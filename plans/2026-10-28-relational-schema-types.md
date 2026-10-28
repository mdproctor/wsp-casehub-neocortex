# Relational Schema Types and Storage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #477 — Interpersonal relational schemas
**Issue group:** Child 1 of #477 epic

**Goal:** Create the production types (`RelationalSchema`, `AttachmentProfile`, `PersonalityFacet`, `PersonalityProfile`) and overlay storage, plus `RelationshipVocabulary`. This is the data foundation that Children 2-5 build on.

**Architecture:** Promote the eval-characters-generic.yaml schema to production Java records in `cognitive-index`. Store relational schema dimensions as `rel.`-prefixed properties on existing perspectival overlay nodes. Consolidate `AmpdFacets` (Map-based, integer-scored) into `PersonalityFacet` (record, double-scored). Group personality fields on `CognitiveDefaults` into a `PersonalityProfile` composite to reduce record arity.

**Tech Stack:** Java 21, cognitive-index module, mindmap-api module

## Global Constraints

- Java 21 source level, Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- All numeric scores use `double` in `[0,1]` or `[-1,1]` — no integer scales
- Use `ide_create_file` for new Java files, `ide_edit_member` / `ide_replace_member` for modifications
- Use `ide_refactor_rename` for renames, never bash `mv`
- Every commit references an issue: `Refs #477`

---

## Batch 1: New types — PersonalityFacet, AttachmentProfile, RelationalSchema

### Task 1: PersonalityFacet record

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PersonalityFacet.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PersonalityFacetTest.java`

**Interfaces:**
- Consumes: Nothing
- Produces: `PersonalityFacet(String facet, double score, @Nullable String origin)` — used by Tasks 3, 4, 5

- [ ] **Step 1: Write failing test**

```java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class PersonalityFacetTest {

    @Test
    void validFacet_createsSuccessfully() {
        var facet = new PersonalityFacet("Callousness", 0.9, "numbness where sympathy should be");
        assertThat(facet.facet()).isEqualTo("Callousness");
        assertThat(facet.score()).isEqualTo(0.9);
        assertThat(facet.origin()).isEqualTo("numbness where sympathy should be");
    }

    @Test
    void nullOrigin_isAllowed() {
        var facet = new PersonalityFacet("Grandiosity", 0.8, null);
        assertThat(facet.origin()).isNull();
    }

    @Test
    void scoreBelowZero_throws() {
        assertThatThrownBy(() -> new PersonalityFacet("X", -0.1, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void scoreAboveOne_throws() {
        assertThatThrownBy(() -> new PersonalityFacet("X", 1.1, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void boundaryValues_areAccepted() {
        assertThatCode(() -> new PersonalityFacet("X", 0.0, null)).doesNotThrowAnyException();
        assertThatCode(() -> new PersonalityFacet("X", 1.0, null)).doesNotThrowAnyException();
    }

    @Test
    void facetConstants_areAvailable() {
        assertThat(PersonalityFacet.CALLOUSNESS).isEqualTo("Callousness");
        assertThat(PersonalityFacet.MANIPULATIVENESS).isEqualTo("Manipulativeness");
        assertThat(PersonalityFacet.GRANDIOSITY).isEqualTo("Grandiosity");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PersonalityFacetTest -DfailIfNoTests=false`
Expected: Compilation error — PersonalityFacet doesn't exist

- [ ] **Step 3: Implement PersonalityFacet**

Use `ide_create_file` to create:

```java
package io.casehub.neocortex.cognitive.index;

import org.jspecify.annotations.Nullable;

public record PersonalityFacet(
        String facet,
        double score,
        @Nullable String origin
) {
    public static final String CALLOUSNESS = "Callousness";
    public static final String MANIPULATIVENESS = "Manipulativeness";
    public static final String GRANDIOSITY = "Grandiosity";
    public static final String DECEITFULNESS = "Deceitfulness";
    public static final String ATTENTION_SEEKING = "Attention Seeking";
    public static final String HOSTILITY = "Hostility";
    public static final String SUSPICIOUSNESS = "Suspiciousness";
    public static final String INTIMACY_AVOIDANCE = "Intimacy Avoidance";
    public static final String EMOTIONAL_LABILITY = "Emotional Lability";
    public static final String ANXIOUSNESS = "Anxiousness";
    public static final String RISK_TAKING = "Risk Taking";
    public static final String IMPULSIVITY = "Impulsivity";
    public static final String WITHDRAWAL = "Withdrawal";

    public PersonalityFacet {
        if (score < 0.0 || score > 1.0)
            throw new IllegalArgumentException("score must be in [0,1], got " + score);
    }

    public boolean isHigh() { return score >= 0.7; }
    public boolean isLow() { return score <= 0.3; }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PersonalityFacetTest`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PersonalityFacet.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PersonalityFacetTest.java
git commit -m "feat(#477): add PersonalityFacet record with [0,1] scale and AMPD constants

Refs #477

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 2: AttachmentProfile record

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/AttachmentProfile.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/AttachmentProfileTest.java`

**Interfaces:**
- Consumes: Nothing
- Produces: `AttachmentProfile(String style, double anxiety, double avoidance)` — used by Tasks 3, 4

- [ ] **Step 1: Write failing test**

```java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class AttachmentProfileTest {

    @Test
    void secure_hasLowAnxietyAndAvoidance() {
        var profile = new AttachmentProfile("secure", 0.1, 0.1);
        assertThat(profile.style()).isEqualTo("secure");
        assertThat(profile.anxiety()).isEqualTo(0.1);
        assertThat(profile.avoidance()).isEqualTo(0.1);
    }

    @Test
    void dismissiveAvoidant_hasHighAvoidance() {
        var profile = new AttachmentProfile("dismissive-avoidant", 0.1, 0.8);
        assertThat(profile.avoidance()).isEqualTo(0.8);
    }

    @Test
    void anxietyOutOfRange_throws() {
        assertThatThrownBy(() -> new AttachmentProfile("secure", -0.1, 0.0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new AttachmentProfile("secure", 1.1, 0.0))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void avoidanceOutOfRange_throws() {
        assertThatThrownBy(() -> new AttachmentProfile("secure", 0.0, -0.1))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new AttachmentProfile("secure", 0.0, 1.1))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=AttachmentProfileTest -DfailIfNoTests=false`
Expected: Compilation error

- [ ] **Step 3: Implement AttachmentProfile**

```java
package io.casehub.neocortex.cognitive.index;

public record AttachmentProfile(
        String style,
        double anxiety,
        double avoidance
) {
    public AttachmentProfile {
        if (anxiety < 0.0 || anxiety > 1.0)
            throw new IllegalArgumentException("anxiety must be in [0,1], got " + anxiety);
        if (avoidance < 0.0 || avoidance > 1.0)
            throw new IllegalArgumentException("avoidance must be in [0,1], got " + avoidance);
    }
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=AttachmentProfileTest`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/AttachmentProfile.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/AttachmentProfileTest.java
git commit -m "feat(#477): add AttachmentProfile record (style, anxiety, avoidance)

Refs #477

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

### Task 3: RelationalSchema record with overlay property serialization

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/RelationalSchema.java`
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/RelationalSchemaTest.java`

**Interfaces:**
- Consumes: Nothing
- Produces: `RelationalSchema(String targetId, String role, double trust, double intimacy, double utility, @Nullable String description)` with `toProperties()` → `Map<String, String>` and `fromProperties(Map<String, String>)` → `@Nullable RelationalSchema` — used by Children 2, 4, 5

- [ ] **Step 1: Write failing tests**

```java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import java.util.HashMap;
import java.util.Map;
import static org.assertj.core.api.Assertions.*;

class RelationalSchemaTest {

    @Test
    void roundTrip_preservesAllFields() {
        var schema = new RelationalSchema("peter-perfect", "obstacle", 0.1, 0.0, 0.2,
                "Predictably protective.");
        var props = schema.toProperties();
        var restored = RelationalSchema.fromProperties(props);
        assertThat(restored).isNotNull();
        assertThat(restored.targetId()).isEqualTo("peter-perfect");
        assertThat(restored.role()).isEqualTo("obstacle");
        assertThat(restored.trust()).isEqualTo(0.1);
        assertThat(restored.intimacy()).isEqualTo(0.0);
        assertThat(restored.utility()).isEqualTo(0.2);
        assertThat(restored.description()).isEqualTo("Predictably protective.");
    }

    @Test
    void fromProperties_noRelPrefix_returnsNull() {
        var props = Map.of("familiarity-score", "0.5");
        assertThat(RelationalSchema.fromProperties(props)).isNull();
    }

    @Test
    void fromProperties_partialProperties_usesDefaults() {
        var props = new HashMap<String, String>();
        props.put("rel.target-id", "stranger-1");
        props.put("rel.role", "ally");
        var schema = RelationalSchema.fromProperties(props);
        assertThat(schema).isNotNull();
        assertThat(schema.trust()).isEqualTo(0.0);
        assertThat(schema.intimacy()).isEqualTo(0.0);
        assertThat(schema.utility()).isEqualTo(0.0);
    }

    @Test
    void fromProperties_invalidNumeric_usesDefault() {
        var props = new HashMap<String, String>();
        props.put("rel.target-id", "target");
        props.put("rel.trust", "not-a-number");
        var schema = RelationalSchema.fromProperties(props);
        assertThat(schema).isNotNull();
        assertThat(schema.trust()).isEqualTo(0.0);
    }

    @Test
    void fromProperties_outOfRange_clamps() {
        var props = new HashMap<String, String>();
        props.put("rel.target-id", "target");
        props.put("rel.trust", "5.0");
        props.put("rel.intimacy", "-1.0");
        var schema = RelationalSchema.fromProperties(props);
        assertThat(schema).isNotNull();
        assertThat(schema.trust()).isEqualTo(1.0);
        assertThat(schema.intimacy()).isEqualTo(0.0);
    }

    @Test
    void trustRange_isNegativeOneToOne() {
        assertThatCode(() -> new RelationalSchema("t", "r", -1.0, 0.0, 0.0, null))
                .doesNotThrowAnyException();
        assertThatThrownBy(() -> new RelationalSchema("t", "r", -1.1, 0.0, 0.0, null))
                .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void propertiesUseRelPrefix() {
        var schema = new RelationalSchema("t", "ally", 0.5, 0.3, 0.7, null);
        var props = schema.toProperties();
        assertThat(props.keySet()).allMatch(k -> k.startsWith("rel."));
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=RelationalSchemaTest -DfailIfNoTests=false`
Expected: Compilation error

- [ ] **Step 3: Implement RelationalSchema**

```java
package io.casehub.neocortex.cognitive.index;

import org.jspecify.annotations.Nullable;
import java.util.HashMap;
import java.util.Map;

public record RelationalSchema(
        String targetId,
        String role,
        double trust,
        double intimacy,
        double utility,
        @Nullable String description
) {
    public static final String PREFIX = "rel.";

    public RelationalSchema {
        if (trust < -1.0 || trust > 1.0)
            throw new IllegalArgumentException("trust must be in [-1,1], got " + trust);
        if (intimacy < 0.0 || intimacy > 1.0)
            throw new IllegalArgumentException("intimacy must be in [0,1], got " + intimacy);
        if (utility < 0.0 || utility > 1.0)
            throw new IllegalArgumentException("utility must be in [0,1], got " + utility);
    }

    public Map<String, String> toProperties() {
        var props = new HashMap<String, String>();
        props.put(PREFIX + "target-id", targetId);
        props.put(PREFIX + "role", role);
        props.put(PREFIX + "trust", String.valueOf(trust));
        props.put(PREFIX + "intimacy", String.valueOf(intimacy));
        props.put(PREFIX + "utility", String.valueOf(utility));
        if (description != null) props.put(PREFIX + "description", description);
        return Map.copyOf(props);
    }

    public static @Nullable RelationalSchema fromProperties(Map<String, String> props) {
        var targetId = props.get(PREFIX + "target-id");
        if (targetId == null) return null;
        return new RelationalSchema(
                targetId,
                props.getOrDefault(PREFIX + "role", "stranger"),
                clamp(parseDouble(props.get(PREFIX + "trust"), 0.0), -1.0, 1.0),
                clamp(parseDouble(props.get(PREFIX + "intimacy"), 0.0), 0.0, 1.0),
                clamp(parseDouble(props.get(PREFIX + "utility"), 0.0), 0.0, 1.0),
                props.get(PREFIX + "description")
        );
    }

    private static double parseDouble(@Nullable String value, double fallback) {
        if (value == null || value.isBlank()) return fallback;
        try { return Double.parseDouble(value); }
        catch (NumberFormatException e) { return fallback; }
    }

    private static double clamp(double v, double min, double max) {
        return Math.max(min, Math.min(max, v));
    }
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=RelationalSchemaTest`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/RelationalSchema.java cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/RelationalSchemaTest.java
git commit -m "feat(#477): add RelationalSchema with overlay property serialization

rel.-prefixed properties on perspectival overlay nodes.
Defensive parsing: null for missing, defaults for partial, clamp for out-of-range.

Refs #477

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 2: PersonalityProfile composite and CognitiveDefaults refactoring

### Task 4: PersonalityProfile composite record and CognitiveDefaults migration

**Files:**
- Create: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/PersonalityProfile.java`
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDefaults.java` (replace `personality`, `personalityDominance`, `expressionStyles` fields with `personalityProfile`)
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/DescriptorView.java` (replace `ampdFacets` with `personalityFacets`)
- Modify: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/CognitiveDerivationEngine.java` (`deriveExpressionStyles` signature change)
- Modify: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/ExpressionStyleDerivationTest.java` (migrate to `PersonalityFacet`)
- Delete: `cognitive-index/src/main/java/io/casehub/neocortex/cognitive/index/AmpdFacets.java` (use `ide_refactor_safe_delete`)
- Test: `cognitive-index/src/test/java/io/casehub/neocortex/cognitive/index/PersonalityProfileTest.java`

**Interfaces:**
- Consumes: `PersonalityFacet` (Task 1), `AttachmentProfile` (Task 2)
- Produces: `PersonalityProfile(PersonalityWeights, Double, ExpressionStyleDefaults, AttachmentProfile, List<PersonalityFacet>)` — accessed via `CognitiveDefaults.personalityProfile()`

- [ ] **Step 1: Write failing test for PersonalityProfile**

```java
package io.casehub.neocortex.cognitive.index;

import org.junit.jupiter.api.Test;
import java.util.List;
import static org.assertj.core.api.Assertions.*;

class PersonalityProfileTest {

    @Test
    void compositeRecord_holdsAllFields() {
        var profile = new PersonalityProfile(
                null, null, null,
                new AttachmentProfile("dismissive-avoidant", 0.1, 0.8),
                List.of(new PersonalityFacet("Callousness", 0.9, null)));
        assertThat(profile.attachment()).isNotNull();
        assertThat(profile.attachment().avoidance()).isEqualTo(0.8);
        assertThat(profile.facets()).hasSize(1);
        assertThat(profile.facets().getFirst().facet()).isEqualTo("Callousness");
    }

    @Test
    void nullAttachmentAndFacets_areAllowed() {
        var profile = new PersonalityProfile(null, null, null, null, List.of());
        assertThat(profile.attachment()).isNull();
        assertThat(profile.facets()).isEmpty();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PersonalityProfileTest -DfailIfNoTests=false`
Expected: Compilation error

- [ ] **Step 3: Create PersonalityProfile record**

Use `ide_create_file`:

```java
package io.casehub.neocortex.cognitive.index;

import org.jspecify.annotations.Nullable;
import java.util.List;

public record PersonalityProfile(
        @Nullable PersonalityWeights personality,
        @Nullable Double personalityDominance,
        @Nullable ExpressionStyleDefaults expressionStyles,
        @Nullable AttachmentProfile attachment,
        List<PersonalityFacet> facets
) {
    public PersonalityProfile {
        facets = facets != null ? List.copyOf(facets) : List.of();
    }
}
```

- [ ] **Step 4: Run PersonalityProfile test, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index -Dtest=PersonalityProfileTest`
Expected: 2 tests PASS

- [ ] **Step 5: Refactor CognitiveDefaults**

Use `ide_edit_member` to replace the record declaration:
- Remove fields: `personality`, `personalityDominance`, `expressionStyles`
- Add field: `personalityProfile` (type `PersonalityProfile`)
- Update `empty()` factory: pass `new PersonalityProfile(null, null, null, null, List.of())`
- Replace `withPersonality`, `withPersonalityDominance`, `withExpressionStyles` → `withPersonalityProfile`
- Add convenience accessors: `personality()` delegating to `personalityProfile().personality()`, etc.

This is a mechanical refactoring — every caller of `defaults.personality()` continues to work via the delegating accessor. Every caller of `defaults.personalityDominance()` and `defaults.expressionStyles()` likewise.

- [ ] **Step 6: Migrate DescriptorView**

Use `ide_edit_member` on DescriptorView:
- Replace `AmpdFacets ampdFacets` → `List<PersonalityFacet> personalityFacets`
- Update compact constructor: `personalityFacets = personalityFacets != null ? List.copyOf(personalityFacets) : List.of();`
- Update backward-compat constructor: pass `null` for `personalityFacets` → `List.of()`
- Update `of()` factory: pass `List.of()` for `personalityFacets`

- [ ] **Step 7: Migrate CognitiveDerivationEngine.deriveExpressionStyles**

Use `ide_edit_member` to change signature from `deriveExpressionStyles(AmpdFacets facets)` to `deriveExpressionStyles(List<PersonalityFacet> facets)`.

Replace `facets.isHigh(AmpdFacets.GRANDIOSITY)` with helper:
```java
private static boolean isHigh(List<PersonalityFacet> facets, String name) {
    return facets.stream().filter(f -> name.equals(f.facet())).findFirst()
            .map(PersonalityFacet::isHigh).orElse(false);
}
private static boolean isLow(List<PersonalityFacet> facets, String name) {
    return facets.stream().filter(f -> name.equals(f.facet())).findFirst()
            .map(PersonalityFacet::isLow).orElse(true);
}
```

Then replace all `facets.isHigh(AmpdFacets.X)` → `isHigh(facets, PersonalityFacet.X)` and `facets.isLow(AmpdFacets.X)` → `isLow(facets, PersonalityFacet.X)`.

- [ ] **Step 8: Migrate ExpressionStyleDerivationTest**

Replace all `new AmpdFacets(Map.of(AmpdFacets.X, 85, ...))` with `List.of(new PersonalityFacet("X", 0.85, null), ...)`. Score conversion: `integer / 100.0`.

- [ ] **Step 9: Safe-delete AmpdFacets**

Use `ide_refactor_safe_delete` on `AmpdFacets.java`. If blocking usages remain, fix them first.

- [ ] **Step 10: Run full cognitive-index tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-index`
Expected: All tests PASS

- [ ] **Step 11: Run full build to verify no downstream breakage**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS (compilation check across all modules)

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "refactor(#477): introduce PersonalityProfile composite, retire AmpdFacets

CognitiveDefaults: personality + personalityDominance + expressionStyles
consolidated into PersonalityProfile (19 → 17 fields + attachment + facets).
AmpdFacets replaced by List<PersonalityFacet> with [0,1] scale.
DescriptorView updated: ampdFacets → personalityFacets.

Refs #477

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## Batch 3: RelationshipVocabulary

### Task 5: RelationshipVocabulary and CognitiveLoader registration

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RelationshipVocabulary.java`
- Modify: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoader.java` (register vocabulary)
- Test: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/RelationshipVocabularyTest.java` (if test dir exists, otherwise in mindmap-intelligence test)

**Interfaces:**
- Consumes: `MindMapVocabulary.builder()` pattern from `GoalVocabulary`
- Produces: `RelationshipVocabulary.RELATIONSHIP_VOCABULARY` — registered at startup via `CognitiveLoader`

- [ ] **Step 1: Write failing test**

```java
package io.casehub.neocortex.mindmap;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class RelationshipVocabularyTest {

    @Test
    void vocabularyHasExpectedEdgeTypes() {
        var vocab = RelationshipVocabulary.RELATIONSHIP_VOCABULARY;
        assertThat(vocab.edgeTypes()).extracting("canonicalName")
                .contains("trusts", "distrusts", "fears", "admires",
                           "resents", "protects", "exploits", "depends-on");
    }

    @Test
    void trustsHasExpectedAliases() {
        var trustType = RelationshipVocabulary.RELATIONSHIP_VOCABULARY.edgeTypes().stream()
                .filter(e -> "trusts".equals(e.canonicalName()))
                .findFirst().orElseThrow();
        assertThat(trustType.aliases()).contains("relies-on");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=RelationshipVocabularyTest -DfailIfNoTests=false`
Expected: Compilation error

- [ ] **Step 3: Implement RelationshipVocabulary**

Use `ide_create_file`:

```java
package io.casehub.neocortex.mindmap;

public final class RelationshipVocabulary {

    public static final MindMapVocabulary RELATIONSHIP_VOCABULARY = MindMapVocabulary.builder()
            .edgeType("trusts", 30.0, "relies-on")
            .edgeType("distrusts", 14.0, "suspects", "wary-of")
            .edgeType("fears", 14.0, "dreads", "avoids")
            .edgeType("admires", 60.0, "respects", "looks-up-to")
            .edgeType("resents", 21.0, "begrudges")
            .edgeType("protects", 60.0, "shields", "guards")
            .edgeType("exploits", 21.0, "uses", "manipulates")
            .edgeType("depends-on", 30.0, "needs", "leans-on")
            .build();

    private RelationshipVocabulary() {}
}
```

- [ ] **Step 4: Run test, verify pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=RelationshipVocabularyTest`
Expected: 2 tests PASS

- [ ] **Step 5: Register vocabulary in CognitiveLoader**

Find the `@PostConstruct` method in `CognitiveLoader` that registers `GoalVocabulary.GOAL_VOCABULARY`. Add `RelationshipVocabulary.RELATIONSHIP_VOCABULARY` registration using the same pattern.

- [ ] **Step 6: Full build verification**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS, all tests pass

- [ ] **Step 7: Commit**

```bash
git add mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RelationshipVocabulary.java mindmap-api/src/test/java/io/casehub/neocortex/mindmap/RelationshipVocabularyTest.java mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CognitiveLoader.java
git commit -m "feat(#477): add RelationshipVocabulary with 8 interpersonal edge types

trusts/distrusts/fears/admires/resents/protects/exploits/depends-on.
Registered via CognitiveLoader alongside GoalVocabulary.
Decay half-lives: trust/distrust 14-30d, admiration/protection 60d.

Refs #477

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## References

- [2026-10-28-relational-schemas-design.md] — design spec this plan implements
- [cognitive-index/CognitiveDefaults.java:31-136] — 19-field record being refactored
- [cognitive-index/AmpdFacets.java:5-40] — being retired, replaced by PersonalityFacet
- [cognitive-index/DescriptorView.java:21-46] — ampdFacets → personalityFacets migration
- [cognitive-index/CognitiveDerivationEngine.java:464-542] — deriveExpressionStyles caller
- [mindmap-api/GoalVocabulary.java:3-35] — vocabulary registration pattern
- [caps-llm-classifier/eval-characters-generic.yaml:36-127] — eval schema being promoted
- [GitHub #477] — parent epic
- [GitHub #575] — relationship edge types (orthogonal, not subsumed)
