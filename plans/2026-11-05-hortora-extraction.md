# Hortora Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #802 — Extract Hortora-specific corpus code to dedicated module
**Issue group:** #789 (parent epic)

**Goal:** Extract Hortora-specific code from `corpus-management` into a new `corpus-management-hortora` module, introduce a `ScoreModifier` SPI, and split the `CorpusApi` MCP interface so non-Hortora consumers get clean generic operations.

**Architecture:** New `corpus-management-hortora` module depends on `corpus-management` which depends on `corpus-management-api`. `ScoreModifier` @FunctionalInterface SPI in the API module replaces hardcoded scoring strategies. `CorpusApi` MCP interface splits into generic (search, provenance, profiles) and garden-specific (`GardenCorpusApi` for entry detail, reindex, feedback).

**Tech Stack:** Java 21 (on Java 26 JVM), Maven, SQLite + Flyway, Jackson, SnakeYAML

## Global Constraints

- Java 21 source level, Java 26 JVM
- `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn` for all builds
- Use `mvn` not `./mvnw`
- IntelliJ MCP for all code navigation, refactoring, and structural editing
- All commits reference issue: `Refs #802`
- TDD: failing test → verify fail → implement → verify pass → commit

---

## Batch 1: ScoreModifier SPI and SearchResource Refactoring

### Task 1: Create ScoreModifier SPI and built-in implementations

**Files:**
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/ScoreModifier.java`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/TemporalDecayScoreModifier.java`
- Create: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/VersionDistanceScoreModifier.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/TemporalDecayScoreModifierTest.java`
- Create: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/VersionDistanceScoreModifierTest.java`

**Interfaces:**
- Produces: `ScoreModifier` — `double multiplier(Map<String,String> metadata, Map<String,String> context)` @FunctionalInterface
- Produces: `TemporalDecayScoreModifier(Map<Integer,Duration> tierHalfLives, Duration defaultHalfLife)` — reads `submitted` and `decay_tier` from metadata
- Produces: `VersionDistanceScoreModifier(double decayFactor, double floor)` — reads `verified_on` from metadata, BOM from context

- [ ] **Step 1: Write ScoreModifier SPI**

```java
package io.casehub.neocortex.corpus.management;

import java.util.Map;

@FunctionalInterface
public interface ScoreModifier {
    double multiplier(Map<String, String> metadata, Map<String, String> context);
}
```

- [ ] **Step 2: Write failing test for TemporalDecayScoreModifier**

```java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.corpus.management.ScoreModifier;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.LocalDate;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class TemporalDecayScoreModifierTest {

    private static final Map<Integer, Duration> TIER_HALF_LIVES = Map.of(
            0, Duration.ofDays(730),
            1, Duration.ofDays(365),
            2, Duration.ofDays(180),
            3, Duration.ofDays(90));

    private final ScoreModifier modifier = new TemporalDecayScoreModifier(
            TIER_HALF_LIVES, Duration.ofDays(365));

    @Test
    void no_submitted_date_returns_1() {
        assertThat(modifier.multiplier(Map.of(), Map.of())).isEqualTo(1.0);
    }

    @Test
    void blank_submitted_date_returns_1() {
        assertThat(modifier.multiplier(Map.of("submitted", ""), Map.of())).isEqualTo(1.0);
    }

    @Test
    void today_returns_1() {
        String today = LocalDate.now().toString();
        assertThat(modifier.multiplier(Map.of("submitted", today), Map.of())).isEqualTo(1.0);
    }

    @Test
    void one_half_life_ago_returns_approximately_half() {
        String date = LocalDate.now().minusDays(365).toString();
        double result = modifier.multiplier(Map.of("submitted", date, "decay_tier", "1"), Map.of());
        assertThat(result).isCloseTo(0.5, within(0.05));
    }

    @Test
    void uses_tier_specific_half_life() {
        String date = LocalDate.now().minusDays(90).toString();
        double tier3 = modifier.multiplier(Map.of("submitted", date, "decay_tier", "3"), Map.of());
        assertThat(tier3).isCloseTo(0.5, within(0.05));
    }

    @Test
    void unknown_tier_uses_default() {
        String date = LocalDate.now().minusDays(365).toString();
        double result = modifier.multiplier(Map.of("submitted", date, "decay_tier", "99"), Map.of());
        assertThat(result).isCloseTo(0.5, within(0.05));
    }

    @Test
    void invalid_date_returns_1() {
        assertThat(modifier.multiplier(Map.of("submitted", "not-a-date"), Map.of())).isEqualTo(1.0);
    }
}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dtest=TemporalDecayScoreModifierTest -DfailIfNoTests=false`
Expected: compilation failure — TemporalDecayScoreModifier does not exist

- [ ] **Step 4: Implement TemporalDecayScoreModifier**

```java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.corpus.management.ScoreModifier;

import java.time.Duration;
import java.time.LocalDate;
import java.time.format.DateTimeParseException;
import java.time.temporal.ChronoUnit;
import java.util.Map;

public class TemporalDecayScoreModifier implements ScoreModifier {

    private static final double LN2 = 0.693147;

    private final Map<Integer, Duration> tierHalfLives;
    private final Duration defaultHalfLife;

    public TemporalDecayScoreModifier(Map<Integer, Duration> tierHalfLives, Duration defaultHalfLife) {
        this.tierHalfLives = Map.copyOf(tierHalfLives);
        this.defaultHalfLife = defaultHalfLife;
    }

    @Override
    public double multiplier(Map<String, String> metadata, Map<String, String> context) {
        String submitted = metadata.get("submitted");
        if (submitted == null || submitted.isBlank()) return 1.0;
        try {
            var date = LocalDate.parse(submitted.length() > 10 ? submitted.substring(0, 10) : submitted);
            long daysSince = ChronoUnit.DAYS.between(date, LocalDate.now());
            if (daysSince <= 0) return 1.0;
            int tier = parseTier(metadata.get("decay_tier"));
            Duration halfLife = tierHalfLives.getOrDefault(tier, defaultHalfLife);
            return Math.exp(-LN2 * daysSince / halfLife.toDays());
        } catch (DateTimeParseException e) {
            return 1.0;
        }
    }

    private static int parseTier(String decayTier) {
        if (decayTier == null || decayTier.isBlank()) return 1;
        try {
            return Integer.parseInt(decayTier);
        } catch (NumberFormatException e) {
            return 1;
        }
    }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-api,corpus-management -Dtest=TemporalDecayScoreModifierTest`
Expected: all 7 tests PASS

- [ ] **Step 6: Write failing test for VersionDistanceScoreModifier**

```java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.corpus.management.ScoreModifier;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.within;

class VersionDistanceScoreModifierTest {

    private final ScoreModifier modifier = new VersionDistanceScoreModifier(0.03, 0.5);

    @Test
    void no_verified_on_returns_1() {
        assertThat(modifier.multiplier(Map.of(), Map.of())).isEqualTo(1.0);
    }

    @Test
    void blank_verified_on_returns_1() {
        assertThat(modifier.multiplier(Map.of("verified_on", ""), Map.of())).isEqualTo(1.0);
    }

    @Test
    void empty_bom_returns_1() {
        assertThat(modifier.multiplier(Map.of("verified_on", "quarkus:3.30"), Map.of())).isEqualTo(1.0);
    }

    @Test
    void same_version_returns_1() {
        assertThat(modifier.multiplier(
                Map.of("verified_on", "quarkus:3.36"),
                Map.of("quarkus", "3.36"))).isEqualTo(1.0);
    }

    @Test
    void one_minor_distance_decays() {
        double result = modifier.multiplier(
                Map.of("verified_on", "quarkus:3.35"),
                Map.of("quarkus", "3.36"));
        assertThat(result).isLessThan(1.0);
        assertThat(result).isGreaterThan(0.5);
    }

    @Test
    void large_distance_hits_floor() {
        double result = modifier.multiplier(
                Map.of("verified_on", "quarkus:2.0"),
                Map.of("quarkus", "3.36"));
        assertThat(result).isCloseTo(0.5, within(0.01));
    }

    @Test
    void unknown_stack_in_bom_returns_1() {
        assertThat(modifier.multiplier(
                Map.of("verified_on", "unknown:1.0"),
                Map.of("quarkus", "3.36"))).isEqualTo(1.0);
    }

    @Test
    void malformed_verified_on_returns_1() {
        assertThat(modifier.multiplier(
                Map.of("verified_on", "no-colon"),
                Map.of("quarkus", "3.36"))).isEqualTo(1.0);
    }
}
```

- [ ] **Step 7: Implement VersionDistanceScoreModifier**

```java
package io.casehub.neocortex.corpus.management.impl;

import io.casehub.neocortex.corpus.management.ScoreModifier;

import java.util.Map;

public class VersionDistanceScoreModifier implements ScoreModifier {

    private final double decayFactor;
    private final double floor;

    public VersionDistanceScoreModifier(double decayFactor, double floor) {
        this.decayFactor = decayFactor;
        this.floor = floor;
    }

    @Override
    public double multiplier(Map<String, String> metadata, Map<String, String> context) {
        String verifiedOn = metadata.get("verified_on");
        if (verifiedOn == null || verifiedOn.isBlank() || context.isEmpty()) return 1.0;
        String[] parts = verifiedOn.split(":", 2);
        if (parts.length < 2) return 1.0;
        String currentVersion = context.get(parts[0]);
        if (currentVersion == null) return 1.0;
        int distance = versionDistance(parts[1], currentVersion);
        if (distance <= 0) return 1.0;
        return Math.max(floor, Math.pow(decayFactor, distance));
    }

    private static int versionDistance(String a, String b) {
        int[] av = parseVersion(a), bv = parseVersion(b);
        return Math.abs(bv[0] - av[0]) * 10 + Math.abs(bv[1] - av[1]);
    }

    private static int[] parseVersion(String v) {
        String[] parts = v.split("[.]");
        try {
            return new int[]{
                    Integer.parseInt(parts[0]),
                    parts.length > 1 ? Integer.parseInt(parts[1]) : 0
            };
        } catch (NumberFormatException e) {
            return new int[]{0, 0};
        }
    }
}
```

- [ ] **Step 8: Run all modifier tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-api,corpus-management -Dtest="TemporalDecayScoreModifierTest,VersionDistanceScoreModifierTest"`
Expected: all tests PASS

- [ ] **Step 9: Commit**

```bash
git add corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/ScoreModifier.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/TemporalDecayScoreModifier.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/VersionDistanceScoreModifier.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/TemporalDecayScoreModifierTest.java corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/VersionDistanceScoreModifierTest.java
git commit -m "feat(#802): add ScoreModifier SPI with temporal-decay and version-distance implementations

Refs #802"
```

### Task 2: Refactor SearchResource to use ScoreModifier list

**Files:**
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SearchResource.java`
- Delete: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SearchScoringConfig.java`
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SearchResult.java`
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBean.java` (update SearchResource construction)

**Interfaces:**
- Consumes: `ScoreModifier` from Task 1
- Produces: Updated `SearchResource` constructor taking `List<ScoreModifier>` instead of `SearchScoringConfig`
- Produces: Cleaned `SearchResult` without garden-specific accessors

- [ ] **Step 1: Remove garden-specific accessors from SearchResult**

Use `ide_edit_member` or Edit tool to remove the 5 Jackson-annotated methods from `SearchResult.java`:
- `stalenessThreshold()` (lines 38-40)
- `tags()` (lines 42-49)
- `lastReviewed()` (lines 51-53)
- `author()` (lines 55-57)
- `verifiedOn()` (lines 59-61)

- [ ] **Step 2: Refactor SearchResource constructor and applyScoring**

Replace `SearchScoringConfig scoringConfig` parameter with `List<ScoreModifier> scoreModifiers` in the constructor.

Replace the `applyScoring` method body to iterate over modifiers:

```java
List<SearchResult> applyScoring(List<SearchResult> results, String queryText, Map<String, String> bom) {
    if (scoreModifiers.isEmpty()) return results;
    return results.stream().map(r -> {
        if (r.metadata() == null) return r;
        double multiplier = 1.0;
        for (var mod : scoreModifiers) {
            multiplier *= mod.multiplier(r.metadata(), bom);
        }
        if (multiplier >= 0.999) return r;
        Double adjustedCe = r.crossEncoderScore() != null ? r.crossEncoderScore() * multiplier : null;
        return r.withAdjustedScores(r.relevance() * multiplier, adjustedCe);
    }).toList();
}
```

Remove: `TIER_HALF_LIVES` constant, `temporalDecayScore()`, `versionScore()`, `versionDistance()`, `parseVersion()` methods, `LN2` constant, `DEFAULT_HALF_LIFE` constant.

Remove the `scoringConfig` field and all references to `scoringConfig.temporalDecayEnabled()`, `scoringConfig.versionScoringEnabled()`, etc.

- [ ] **Step 3: Delete SearchScoringConfig**

Use `ide_refactor_safe_delete` on `SearchScoringConfig.java`.

- [ ] **Step 4: Update CorpusApiBean and any other callers**

Update `CorpusApiBean` constructor to pass `List<ScoreModifier>` instead of `SearchScoringConfig` when constructing `SearchResource`. Find all callers via `ide_find_references` on `SearchResource` constructor and update them.

- [ ] **Step 5: Run existing tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-api,corpus-management`
Expected: all tests PASS (CorpusApiBeanTest constructs SearchResource as `null`, so no change needed there)

- [ ] **Step 6: Commit**

```bash
git add -u corpus-management/src/ corpus-management-api/src/
git commit -m "feat(#802): refactor SearchResource to use ScoreModifier list, remove SearchScoringConfig

Remove hardcoded temporal/version scoring from SearchResource.
Strip garden-specific accessors from SearchResult.

Refs #802"
```

### Task 3: Rename GardenReindexService → CorpusReindexService

**Files:**
- Rename: `GardenReindexService` → `CorpusReindexService` (use `ide_refactor_rename`)

**Interfaces:**
- Produces: `CorpusReindexService` — same API, new name

- [ ] **Step 1: Rename via IntelliJ**

Use `ide_refactor_rename` on `GardenReindexService` → `CorpusReindexService`. This updates all references including `CorpusApi.java` (the return type `GardenReindexService.ReindexResult` → `CorpusReindexService.ReindexResult`), `CorpusApiBean.java`, and `CorpusApiBeanTest.java`.

- [ ] **Step 2: Run tests to verify**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add -u
git commit -m "refactor(#802): rename GardenReindexService → CorpusReindexService

Refs #802"
```

---

## Batch 2: Module Scaffold and CorpusApi Split

### Task 4: Scaffold corpus-management-hortora module

**Files:**
- Create: `corpus-management-hortora/pom.xml`
- Modify: `pom.xml` (parent — add module + dependency management)
- Create: `corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/.gitkeep` (package placeholder)

**Interfaces:**
- Produces: Empty module that compiles

- [ ] **Step 1: Create pom.xml for the new module**

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.4-SNAPSHOT</version>
  </parent>

  <artifactId>casehub-neocortex-corpus-management-hortora</artifactId>
  <name>CaseHub Neocortex - Corpus Management Hortora</name>
  <description>Hortora-specific corpus management — garden metadata extraction, GE-ID patterns, staleness scoring, garden MCP domain.</description>

  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-corpus-management</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-sqlite-support</artifactId>
      <version>${project.version}</version>
    </dependency>
    <dependency>
      <groupId>org.yaml</groupId>
      <artifactId>snakeyaml</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-api</artifactId>
      <optional>true</optional>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-cognitive-api</artifactId>
      <optional>true</optional>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-platform-api</artifactId>
      <optional>true</optional>
    </dependency>

    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-cbr-inmem</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>io.smallrye</groupId>
        <artifactId>jandex-maven-plugin</artifactId>
        <executions>
          <execution>
            <id>make-index</id>
            <goals><goal>jandex</goal></goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 2: Add module to parent pom.xml**

Add `<module>corpus-management-hortora</module>` after `corpus-management-parsers` in the `<modules>` section (line ~105).

Add dependency management entry:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-corpus-management-hortora</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Create package directory**

```bash
mkdir -p corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora
mkdir -p corpus-management-hortora/src/test/java/io/casehub/neocortex/corpus/management/hortora
mkdir -p corpus-management-hortora/src/main/resources
```

- [ ] **Step 4: Verify empty module builds**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl corpus-management-hortora`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
git add corpus-management-hortora/ pom.xml
git commit -m "feat(#802): scaffold corpus-management-hortora module

Refs #802"
```

### Task 5: Split CorpusApi into generic and garden-specific

**Files:**
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApi.java` — remove garden-specific methods
- Create: `corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/GardenCorpusApi.java`
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBean.java` — remove garden dependencies
- Create: `corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/GardenCorpusApiBean.java`

**Interfaces:**
- Consumes: `CorpusReindexService` from Task 3
- Produces: Generic `CorpusApi` (search, provenance, profiles, status)
- Produces: `GardenCorpusApi` (entry, unretrieved, reindex, feedback, outcomes)

- [ ] **Step 1: Remove garden-specific methods from CorpusApi**

Remove these methods from `CorpusApi.java`:
- `entry(String corpusId, String entryId)` → EntryDetail
- `unretrieved(String corpusId, Integer minDays, Integer staleDays)` → UnretrievedReport
- `reindex(String corpusId)` → CorpusReindexService.ReindexResult
- `reindexEntry(String corpusId, String entryId)` → String
- `deleteEntry(String corpusId, String entryId)` → String
- `outcomeReport()` → String
- `recordOutcome(...)` → String
- `recordFeedback(...)` → String

Keep: `search`, `adaptiveSearch`, `status`, `profile`, `profiles`, `saveProfile`, `deleteProfile`, `forwardLineage`, `reverseLineage`, `provenanceStats`, `recordProvenance`.

Update the `@McpDomain` summary to: `"Corpus search, provenance, and profile management"`.

- [ ] **Step 2: Create GardenCorpusApi**

```java
package io.casehub.neocortex.corpus.management.hortora;

import io.casehub.neocortex.corpus.management.impl.CorpusReindexService;
import io.casehub.neocortex.corpus.management.impl.EntryDetail;
import io.casehub.neocortex.corpus.management.impl.UnretrievedReport;
import io.casehub.platform.api.mcp.McpDomain;
import io.casehub.platform.api.mcp.PlatformMutation;
import io.casehub.platform.api.mcp.PlatformQuery;

@McpDomain(value = "neocortex/garden-corpus", app = "neocortex",
        summary = "Garden-specific corpus operations — entry detail, reindex, feedback, outcomes")
public interface GardenCorpusApi {

    @PlatformQuery("Fetch a single corpus entry by ID — returns frontmatter metadata and markdown body")
    EntryDetail entry(String corpusId, String entryId);

    @PlatformQuery("List entries that have never been retrieved or are stale")
    UnretrievedReport unretrieved(String corpusId, Integer minDays, Integer staleDays);

    @PlatformMutation("Trigger full re-index: delete collection and rebuild from source")
    CorpusReindexService.ReindexResult reindex(String corpusId);

    @PlatformMutation("Re-index a single entry: delete vectors then re-extract and re-ingest")
    String reindexEntry(String corpusId, String entryId);

    @PlatformMutation("Delete a single entry's vectors from the index")
    String deleteEntry(String corpusId, String entryId);

    @PlatformQuery("Outcome report: summary of recorded outcomes across entries")
    String outcomeReport();

    @PlatformMutation("Record an outcome for a corpus entry (success/failure with context)")
    String recordOutcome(String entryId, String issueRepo, Integer issueNumber,
            String workContext, Double successRate, String detail);

    @PlatformMutation("Record retrieval feedback for entries — updates staleness tracking and provenance context")
    String recordFeedback(String entryIds, String outcome,
            String stack, String issueRepo, Integer issueNumber);
}
```

- [ ] **Step 3: Simplify CorpusApiBean**

Remove dependencies on: `CorpusIndexService`, `CorpusOutcomeService`.
Remove method implementations for: `entry`, `unretrieved`, `reindex`, `reindexEntry`, `deleteEntry`, `outcomeReport`, `recordOutcome`, `recordFeedback`.
Keep constructor params: `SearchResource`, `CorpusReindexService`, `SearchProfileStore`, `ProvenanceStore`, `CorpusRef`.

- [ ] **Step 4: Create GardenCorpusApiBean stub**

```java
package io.casehub.neocortex.corpus.management.hortora;

import io.casehub.neocortex.corpus.management.impl.CorpusIndexService;
import io.casehub.neocortex.corpus.management.impl.CorpusOutcomeService;
import io.casehub.neocortex.corpus.management.impl.CorpusReindexService;
import io.casehub.neocortex.corpus.management.impl.EntryDetail;
import io.casehub.neocortex.corpus.management.impl.UnretrievedReport;
import io.casehub.neocortex.rag.CorpusRef;

import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;

public class GardenCorpusApiBean implements GardenCorpusApi {

    private final CorpusIndexService indexService;
    private final CorpusReindexService reindexService;
    private final CorpusOutcomeService outcomeService;
    private final CorpusRef corpusRef;
    private final Path corpusRoot;

    public GardenCorpusApiBean(CorpusIndexService indexService,
                                CorpusReindexService reindexService,
                                CorpusOutcomeService outcomeService,
                                CorpusRef corpusRef,
                                Path corpusRoot) {
        this.indexService = indexService;
        this.reindexService = reindexService;
        this.outcomeService = outcomeService;
        this.corpusRef = corpusRef;
        this.corpusRoot = corpusRoot;
    }

    @Override
    public EntryDetail entry(String corpusId, String entryId) {
        if (corpusRoot == null) return null;
        return indexService.entry(corpusRoot, entryId);
    }

    @Override
    public UnretrievedReport unretrieved(String corpusId, Integer minDays, Integer staleDays) {
        return indexService.unretrieved(corpusRef,
                minDays != null ? minDays : 30,
                staleDays != null ? staleDays : 90);
    }

    @Override
    public CorpusReindexService.ReindexResult reindex(String corpusId) {
        return reindexService.reindex();
    }

    @Override
    public String reindexEntry(String corpusId, String entryId) {
        if (corpusRoot == null) return "No corpus root configured — cannot reindex.";
        return indexService.reindexEntry(corpusRef, entryId, corpusRoot);
    }

    @Override
    public String deleteEntry(String corpusId, String entryId) {
        return indexService.deleteEntry(corpusRef, entryId);
    }

    @Override
    public String outcomeReport() {
        return outcomeService.outcomeReport();
    }

    @Override
    public String recordOutcome(String entryId, String issueRepo, Integer issueNumber,
                                 String workContext, Double successRate, String detail) {
        return outcomeService.recordOutcome(entryId, issueRepo,
                issueNumber != null ? issueNumber : 0,
                workContext, successRate != null ? successRate : 0.0, detail);
    }

    @Override
    public String recordFeedback(String entryIds, String outcome,
                                  String stack, String issueRepo, Integer issueNumber) {
        if (entryIds == null || entryIds.isBlank()) return "Error: no entry IDs provided.";
        List<String> ids = Arrays.stream(entryIds.split("\\|"))
                .map(String::trim).filter(s -> !s.isEmpty()).toList();
        return indexService.recordFeedback(corpusRef, ids, outcome, stack, issueRepo, issueNumber);
    }
}
```

- [ ] **Step 5: Verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl corpus-management-api,corpus-management,corpus-management-hortora`
Expected: BUILD SUCCESS

- [ ] **Step 6: Commit**

```bash
git add corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApi.java corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBean.java corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/
git commit -m "feat(#802): split CorpusApi — generic stays, GardenCorpusApi in hortora module

Refs #802"
```

---

## Batch 3: Move Hortora-Specific Classes

### Task 6: Move classes to corpus-management-hortora

**Files:**
- Move: `GardenMetadataExtractor.java` → `corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/`
- Move: `CorpusIndexService.java` → same target
- Move: `BuiltInCorpusTypes.java` → same target
- Move: `CorpusOutcomeService.java` → same target
- Move: `EntryDetail.java` → same target
- Move: `UnretrievedReport.java` → same target
- Move: `StalenessReport.java` → same target
- Move: `FeedbackContext.java` → same target
- Move: `CorpusIndexServiceTest.java` → `corpus-management-hortora/src/test/java/io/casehub/neocortex/corpus/management/hortora/`
- Move: `CorpusOutcomeServiceTest.java` → same target

**Interfaces:**
- Consumes: Module scaffold from Task 4, GardenCorpusApiBean from Task 5

- [ ] **Step 1: Move main source files via ide_move_file**

Use `ide_move_file` for each class to move from `io.casehub.neocortex.corpus.management.impl` to `io.casehub.neocortex.corpus.management.hortora`. IntelliJ updates all imports and references.

Files to move (in this order to avoid broken references):
1. `StalenessReport.java`
2. `FeedbackContext.java`
3. `EntryDetail.java`
4. `UnretrievedReport.java`
5. `BuiltInCorpusTypes.java`
6. `GardenMetadataExtractor.java`
7. `CorpusOutcomeService.java`
8. `CorpusIndexService.java`

- [ ] **Step 2: Move test files**

Use `ide_move_file` for:
1. `CorpusIndexServiceTest.java` → `corpus-management-hortora/src/test/java/io/casehub/neocortex/corpus/management/hortora/`
2. `CorpusOutcomeServiceTest.java` → same target

- [ ] **Step 3: Fix any remaining compilation issues**

Use `ide_diagnostics` to find broken references. The main issues will be:
- `CorpusApiBean` no longer references moved classes (already handled in Task 5)
- `CorpusApiBeanTest` references to `CorpusIndexService` and stubs — update imports or refactor tests

- [ ] **Step 4: Remove snakeyaml dependency from corpus-management pom.xml if no longer needed**

Check if any remaining class in `corpus-management` uses `org.yaml.snakeyaml`. If only `GardenMetadataExtractor` used it (now moved), remove the dependency.

- [ ] **Step 5: Build and test both modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management,corpus-management-hortora`
Expected: all tests PASS in both modules

- [ ] **Step 6: Commit**

```bash
git add -u
git add corpus-management-hortora/
git commit -m "feat(#802): move Hortora-specific classes to corpus-management-hortora

Move: GardenMetadataExtractor, CorpusIndexService, BuiltInCorpusTypes,
CorpusOutcomeService, EntryDetail, UnretrievedReport, StalenessReport,
FeedbackContext and their tests.

Refs #802"
```

### Task 7: Extract GardenProvenanceExtension and move Flyway migrations

**Files:**
- Create: `corpus-management-hortora/src/main/java/io/casehub/neocortex/corpus/management/hortora/GardenProvenanceExtension.java`
- Create: `corpus-management-hortora/src/main/resources/db/garden-provenance/V1__staleness_reports.sql`
- Create: `corpus-management-hortora/src/main/resources/db/garden-provenance/V2__feedback_context.sql`
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/ProvenanceStore.java` — remove garden methods
- Delete: `corpus-management/src/main/resources/db/corpus-provenance/V2__staleness_reports.sql` — moves to hortora
- Delete: `corpus-management/src/main/resources/db/corpus-provenance/V3__feedback_context.sql` — moves to hortora
- Create: `corpus-management-hortora/src/test/java/io/casehub/neocortex/corpus/management/hortora/GardenProvenanceExtensionTest.java`

**Interfaces:**
- Consumes: `SqliteDataSourceFactory` from sqlite-support
- Produces: `GardenProvenanceExtension(DataSource)` — staleness/feedback methods

- [ ] **Step 1: Write failing test for GardenProvenanceExtension**

```java
package io.casehub.neocortex.corpus.management.hortora;

import io.casehub.neocortex.sqlite.SqliteDataSourceFactory;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class GardenProvenanceExtensionTest {

    private GardenProvenanceExtension extension;

    @BeforeEach
    void setUp() {
        var ds = SqliteDataSourceFactory.create(":memory:", 1, 3000);
        extension = new GardenProvenanceExtension(ds);
    }

    @Test
    void recordAndFindFeedbackContext() {
        extension.recordFeedbackContext("doc-1", "casehubio/repo", 42, "RELEVANT");
        var results = extension.findFeedbackContext("doc-1");
        assertThat(results).hasSize(1);
        assertThat(results.get(0).documentId()).isEqualTo("doc-1");
        assertThat(results.get(0).outcome()).isEqualTo("RELEVANT");
    }

    @Test
    void recordAndFindStalenessReports() {
        extension.recordStaleness("doc-1", "quarkus:3.36", "test");
        var results = extension.findStalenessReports("doc-1");
        assertThat(results).hasSize(1);
        assertThat(results.get(0).stack()).isEqualTo("quarkus:3.36");
    }

    @Test
    void findAllStalenessReports() {
        extension.recordStaleness("doc-1", "stack-a", "test");
        extension.recordStaleness("doc-2", "stack-b", "test");
        var all = extension.findAllStalenessReports();
        assertThat(all).hasSize(2);
    }
}
```

- [ ] **Step 2: Create Flyway migration scripts in hortora module**

`corpus-management-hortora/src/main/resources/db/garden-provenance/V1__staleness_reports.sql`:
```sql
CREATE TABLE staleness_reports (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     TEXT NOT NULL,
    stack           TEXT NOT NULL,
    reported_at     TEXT NOT NULL,
    reported_by     TEXT
);

CREATE INDEX idx_staleness_doc ON staleness_reports(document_id);
CREATE INDEX idx_staleness_stack ON staleness_reports(stack);
```

`corpus-management-hortora/src/main/resources/db/garden-provenance/V2__feedback_context.sql`:
```sql
CREATE TABLE feedback_context (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id     TEXT NOT NULL,
    issue_repo      TEXT NOT NULL,
    issue_number    INTEGER NOT NULL,
    outcome         TEXT NOT NULL,
    recorded_at     TEXT NOT NULL
);

CREATE INDEX idx_feedback_ctx_doc ON feedback_context(document_id);
CREATE INDEX idx_feedback_ctx_issue ON feedback_context(issue_repo, issue_number);
```

- [ ] **Step 3: Implement GardenProvenanceExtension**

```java
package io.casehub.neocortex.corpus.management.hortora;

import io.casehub.neocortex.sqlite.SqliteDataSourceFactory;

import javax.sql.DataSource;
import java.sql.*;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

public class GardenProvenanceExtension {

    private static final Logger LOG = Logger.getLogger(GardenProvenanceExtension.class.getName());
    private static final String FLYWAY_LOCATION = "classpath:db/garden-provenance";

    private final DataSource dataSource;

    public GardenProvenanceExtension(DataSource dataSource) {
        this.dataSource = dataSource;
        if (dataSource instanceof com.zaxxer.hikari.HikariDataSource hds) {
            SqliteDataSourceFactory.migrate(hds, FLYWAY_LOCATION);
        }
    }

    public void recordFeedbackContext(String documentId, String issueRepo, int issueNumber, String outcome) {
        String timestamp = Instant.now().toString();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO feedback_context (document_id, issue_repo, issue_number, outcome, recorded_at) VALUES (?, ?, ?, ?, ?)")) {
            ps.setString(1, documentId);
            ps.setString(2, issueRepo);
            ps.setInt(3, issueNumber);
            ps.setString(4, outcome);
            ps.setString(5, timestamp);
            ps.executeUpdate();
        } catch (SQLException e) {
            LOG.log(Level.SEVERE, "Failed to record feedback context", e);
        }
    }

    public List<FeedbackContext> findFeedbackContext(String documentId) {
        List<FeedbackContext> results = new ArrayList<>();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT document_id, issue_repo, issue_number, outcome, recorded_at FROM feedback_context WHERE document_id = ? ORDER BY recorded_at DESC")) {
            ps.setString(1, documentId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    results.add(new FeedbackContext(rs.getString("document_id"), rs.getString("issue_repo"),
                            rs.getInt("issue_number"), rs.getString("outcome"), rs.getString("recorded_at")));
                }
            }
        } catch (SQLException e) {
            LOG.log(Level.SEVERE, "Failed to query feedback context", e);
        }
        return results;
    }

    public void recordStaleness(String documentId, String stack, String reportedBy) {
        String timestamp = Instant.now().toString();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO staleness_reports (document_id, stack, reported_at, reported_by) VALUES (?, ?, ?, ?)")) {
            ps.setString(1, documentId);
            ps.setString(2, stack);
            ps.setString(3, timestamp);
            ps.setString(4, reportedBy);
            ps.executeUpdate();
        } catch (SQLException e) {
            LOG.log(Level.SEVERE, "Failed to record staleness report", e);
        }
    }

    public List<StalenessReport> findStalenessReports(String documentId) {
        List<StalenessReport> results = new ArrayList<>();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT document_id, stack, reported_at, reported_by FROM staleness_reports WHERE document_id = ? ORDER BY reported_at DESC")) {
            ps.setString(1, documentId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    results.add(new StalenessReport(rs.getString("document_id"), rs.getString("stack"),
                            rs.getString("reported_at"), rs.getString("reported_by")));
                }
            }
        } catch (SQLException e) {
            LOG.log(Level.SEVERE, "Failed to query staleness reports", e);
        }
        return results;
    }

    public List<StalenessReport> findAllStalenessReports() {
        List<StalenessReport> results = new ArrayList<>();
        try (Connection conn = dataSource.getConnection();
             Statement stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(
                     "SELECT document_id, stack, reported_at, reported_by FROM staleness_reports ORDER BY reported_at DESC")) {
            while (rs.next()) {
                results.add(new StalenessReport(rs.getString("document_id"), rs.getString("stack"),
                        rs.getString("reported_at"), rs.getString("reported_by")));
            }
        } catch (SQLException e) {
            LOG.log(Level.SEVERE, "Failed to query all staleness reports", e);
        }
        return results;
    }
}
```

- [ ] **Step 4: Remove garden methods from ProvenanceStore**

Remove: `recordFeedbackContext()`, `findFeedbackContext()`, `recordStaleness()`, `findStalenessReports()`, `findAllStalenessReports()`.

Note: Do NOT remove the V2/V3 Flyway migration files from `corpus-management/src/main/resources/db/corpus-provenance/` — existing databases already have these migrations applied and Flyway will fail if they disappear from the migration chain. Leave them in place for backward compatibility.

- [ ] **Step 5: Update CorpusIndexService.recordFeedback to use GardenProvenanceExtension**

In `CorpusIndexService` (now in the Hortora module), change the `ProvenanceStore provenanceStore` constructor parameter to `GardenProvenanceExtension gardenProvenance`. Update the `recordFeedback` method to call `gardenProvenance.recordFeedbackContext()` and `gardenProvenance.recordStaleness()` instead of `provenanceStore.recordFeedbackContext()` and `provenanceStore.recordStaleness()`.

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management,corpus-management-hortora`
Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add -u
git add corpus-management-hortora/
git commit -m "feat(#802): extract GardenProvenanceExtension, remove garden methods from ProvenanceStore

Refs #802"
```

---

## Batch 4: Test Migration and Verification

### Task 8: Fix tests and verify clean separation

**Files:**
- Modify: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/CorpusApiBeanTest.java` — remove tests for moved methods
- Create: `corpus-management-hortora/src/test/java/io/casehub/neocortex/corpus/management/hortora/GardenCorpusApiBeanTest.java`

**Interfaces:**
- Consumes: All changes from Tasks 1-7

- [ ] **Step 1: Clean up CorpusApiBeanTest**

Remove test methods that test garden-specific operations (now in GardenCorpusApiBean):
- `status_delegates_to_index_service` — uses CorpusIndexService (moved)
- `recordFeedback_splits_pipe_separated_ids` — uses CorpusIndexService
- `recordFeedback_invalid_outcome_returns_error` — uses CorpusIndexService
- `entry_returns_null_when_corpusRoot_is_null` — garden-specific
- `reindexEntry_returns_error_when_corpusRoot_is_null` — garden-specific
- `reindex_delegates_to_reindex_service` — tests GardenReindexService (renamed)
- `outcomeReport_delegates` — uses CorpusOutcomeService (moved)
- `deleteEntry_delegates_to_index_service` — uses CorpusIndexService
- `unretrieved_delegates_with_defaults` — uses CorpusIndexService

Keep: `implements_corpus_api`, `profiles_delegates_to_store`, `saveProfile_delegates`, `deleteProfile_delegates`, `recordProvenance_returns_zero_*`, `recordFeedback_returns_error_when_entryIds_null`, `corpus_api_has_mcp_domain_annotation`.

Update `CorpusApiBean` constructor calls to match the simplified constructor.

- [ ] **Step 2: Create GardenCorpusApiBeanTest**

```java
package io.casehub.neocortex.corpus.management.hortora;

import io.casehub.neocortex.corpus.management.impl.CorpusReindexService;
import io.casehub.neocortex.rag.CorpusRef;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class GardenCorpusApiBeanTest {

    @Test
    void implements_garden_corpus_api() {
        var bean = new GardenCorpusApiBean(null, null, null, null, null);
        assertThat(bean).isInstanceOf(GardenCorpusApi.class);
    }

    @Test
    void entry_returns_null_when_corpusRoot_is_null() {
        var bean = new GardenCorpusApiBean(null, null, null, null, null);
        assertThat(bean.entry("corpus", "GE-123")).isNull();
    }

    @Test
    void reindexEntry_returns_error_when_corpusRoot_is_null() {
        var bean = new GardenCorpusApiBean(null, null, null, null, null);
        assertThat(bean.reindexEntry("corpus", "GE-123")).contains("No corpus root");
    }

    @Test
    void recordFeedback_returns_error_when_entryIds_null() {
        var bean = new GardenCorpusApiBean(null, null, null, null, null);
        assertThat(bean.recordFeedback(null, "RELEVANT", null, null, null)).contains("no entry IDs");
    }

    @Test
    void reindex_delegates_to_reindex_service() {
        var ingestor = new CorpusIndexServiceTest.StubIngestor();
        var reindexService = new CorpusReindexService(
                ingestor, new CorpusRef("test", "test-corpus"), (ref, id) -> {});
        var bean = new GardenCorpusApiBean(null, reindexService, null, null, null);
        var result = bean.reindex("test-corpus");
        assertThat(result.status()).isEqualTo("ok");
    }

    @Test
    void garden_corpus_api_has_mcp_domain_annotation() {
        var annotation = GardenCorpusApi.class.getAnnotation(
                io.casehub.platform.api.mcp.McpDomain.class);
        assertThat(annotation).isNotNull();
        assertThat(annotation.value()).isEqualTo("neocortex/garden-corpus");
    }
}
```

- [ ] **Step 3: Run full test suite for both modules**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-api,corpus-management,corpus-management-hortora`
Expected: all tests PASS

- [ ] **Step 4: Verify corpus-management builds independently**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management -Dcorpus-management-hortora.skip=true`
Expected: BUILD SUCCESS — no Hortora classes needed

- [ ] **Step 5: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS for all modules

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test`
Expected: all tests PASS across entire project

- [ ] **Step 6: Commit**

```bash
git add -u
git add corpus-management-hortora/
git commit -m "feat(#802): complete test migration, verify clean module separation

corpus-management builds and tests pass without Hortora on classpath.
All garden-specific tests live in corpus-management-hortora.

Closes #802"
```

---

## References

- specs/issue-787-rich-document-ingestion/2026-11-05-hortora-extraction-design.md — design spec
- docs/specs/2026-11-04-corpus-domain-abstraction-audit.md — domain abstraction audit (L7, L9, L10)
- SearchResource.java:162-246 — temporal/version scoring (extracted to ScoreModifier)
- GardenMetadataExtractor.java — YAML frontmatter + GE-ID patterns (moves)
- CorpusIndexService.java — GE-ID patterns (moves)
- CorpusApi.java — MCP domain interface (splits)
- CorpusApiBean.java — facade (simplifies)
- ProvenanceStore.java — garden methods (extracted)
- GitHub #802, #789
