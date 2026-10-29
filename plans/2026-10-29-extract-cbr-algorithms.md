# Extract cbr-algorithms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #360 — refactor: extract cbr-algorithms from memory-api
**Issue group:** #360

**Goal:** Extract pure-Java algorithm implementations from memory-api into a new cbr-algorithms module, leaving memory-api with only SPI interfaces and value types.

**Architecture:** New `cbr-algorithms` module depends on `memory-api` (not reverse). Same Java package (`io.casehub.neocortex.memory.cbr`) — no import changes in any consumer. Consumers add `cbr-algorithms` as a dependency alongside existing `memory-api`.

**Tech Stack:** Java 21, Maven

## Global Constraints

- Java package stays `io.casehub.neocortex.memory.cbr` — split-package, no import changes
- groupId: `io.casehub`, version: `${project.version}` (0.4-SNAPSHOT)
- Tier 1 pure Java — zero CDI, zero framework dependencies
- Same test deps as memory-api: junit-jupiter, assertj-core

---

## Batch 1: Create cbr-algorithms module and move files

### Task 1: Create cbr-algorithms module with POM and move source files

**Files:**
- Create: `cbr-algorithms/pom.xml`
- Move (git mv): 7 algorithm source files from `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/` to `cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/`
- Move (git mv): 7 output value type source files (same directories)
- Move (git mv): 8 test files from `memory-api/src/test/java/io/casehub/neocortex/memory/cbr/` to `cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/`
- Modify: `pom.xml` (parent — add module + dependencyManagement entry)

**Interfaces:**
- Consumes: memory-api types (FeatureValue, FeatureField, SimilaritySpec, CbrRecordSchema, CbrRecord, CbrQuery, CbrFilter, CbrMatch, WarpingConstraint, TrendSpec, TrendType, NumericRange, LocalSimilarityFunction, TemporalDecay, ScopeDecay)
- Produces: `casehub-neocortex-cbr-algorithms` Maven artifact

- [ ] **Step 1: Create cbr-algorithms/pom.xml**

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
  <artifactId>casehub-neocortex-cbr-algorithms</artifactId>
  <name>CaseHub Neocortex - CBR Algorithms</name>
  <description>Pure-Java CBR scoring, DTW, edit distance, trend analysis, and validation. Tier 1 — zero CDI.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-api</artifactId>
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
</project>
```

- [ ] **Step 2: Create directory structure**

```bash
mkdir -p cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr
mkdir -p cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr
```

- [ ] **Step 3: Move algorithm source files**

Move these 7 files from `memory-api/src/main/java/io/casehub/neocortex/memory/cbr/` to `cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/`:

```bash
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorer.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DtwSimilarity.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/LbKeogh.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditDistanceSimilarity.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TrendAnalyzer.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRecordValidator.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/CbrRecordFilterMatcher.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
```

- [ ] **Step 4: Move output-only value type files**

Move these 7 files (same source → dest pattern):

```bash
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/DtwResult.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/AlignmentPair.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditDistanceResult.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditOp.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/EditStep.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TrendProfile.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/main/java/io/casehub/neocortex/memory/cbr/TrendFieldNaming.java cbr-algorithms/src/main/java/io/casehub/neocortex/memory/cbr/
```

- [ ] **Step 5: Move test files**

```bash
git mv memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrSimilarityScorerTest.java cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/test/java/io/casehub/neocortex/memory/cbr/DtwSimilarityTest.java cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/test/java/io/casehub/neocortex/memory/cbr/LbKeoghTest.java cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/test/java/io/casehub/neocortex/memory/cbr/EditDistanceSimilarityTest.java cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/test/java/io/casehub/neocortex/memory/cbr/TrendAnalyzerTest.java cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/test/java/io/casehub/neocortex/memory/cbr/TrendFieldNamingTest.java cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrFeatureValidatorTest.java cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/
git mv memory-api/src/test/java/io/casehub/neocortex/memory/cbr/CbrRecordFilterMatcherTest.java cbr-algorithms/src/test/java/io/casehub/neocortex/memory/cbr/
```

- [ ] **Step 6: Add module to parent pom.xml**

In the `<modules>` section, add `cbr-algorithms` immediately after `memory-api`:

```xml
    <module>memory-api</module>
    <module>cbr-algorithms</module>
    <module>memory-core</module>
```

- [ ] **Step 7: Add dependencyManagement entry in parent pom.xml**

After the `casehub-neocortex-memory-api` entry (line ~424), add:

```xml
      <dependency>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-cbr-algorithms</artifactId>
        <version>${project.version}</version>
      </dependency>
```

- [ ] **Step 8: Build cbr-algorithms to verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl memory-api,cbr-algorithms`
Expected: BUILD SUCCESS — all 8 moved tests pass, cbr-algorithms compiles against memory-api types

- [ ] **Step 9: Commit**

```bash
git add cbr-algorithms/ pom.xml memory-api/
git commit -m "refactor(#360): create cbr-algorithms module, move algorithm files from memory-api

Move CbrSimilarityScorer, DtwSimilarity, LbKeogh, EditDistanceSimilarity,
TrendAnalyzer, CbrRecordValidator, CbrRecordFilterMatcher and their
output value types to new cbr-algorithms module. Same package — no
import changes needed.

Refs #360"
```

---

## Batch 2: Wire consumer dependencies

### Task 2: Add cbr-algorithms dependency to all consumer modules

**Files:**
- Modify: `memory-cbr-inmem/pom.xml`
- Modify: `memory-cbr-jpa/pom.xml` (if exists) or `memory-cbr-jpa-common/pom.xml`
- Modify: `memory-cbr-spring-jpa/pom.xml`
- Modify: `memory-qdrant/pom.xml`
- Modify: `memory-core/pom.xml`
- Modify: `memory-testing/pom.xml`
- Modify: `cognition/pom.xml`

**Interfaces:**
- Consumes: `casehub-neocortex-cbr-algorithms` artifact from Task 1
- Produces: All consumers compile and test successfully

- [ ] **Step 1: Add cbr-algorithms to memory-cbr-inmem/pom.xml**

Add after the `memory-api` dependency:

```xml
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-cbr-algorithms</artifactId>
    </dependency>
```

- [ ] **Step 2: Add cbr-algorithms to memory-cbr-jpa pom.xml**

Check which POM file exists (`memory-cbr-jpa/pom.xml` or `memory-cbr-jpa-common/pom.xml`). Add the same dependency block after memory-api.

- [ ] **Step 3: Add cbr-algorithms to memory-cbr-spring-jpa/pom.xml**

Same dependency block after memory-api.

- [ ] **Step 4: Add cbr-algorithms to memory-qdrant/pom.xml**

Same dependency block after memory-api.

- [ ] **Step 5: Add cbr-algorithms to memory-core/pom.xml**

Same dependency block after memory-api.

- [ ] **Step 6: Add cbr-algorithms to memory-testing/pom.xml**

Same dependency block after memory-api. (Contract tests reference CbrSimilarityScorer.)

- [ ] **Step 7: Add cbr-algorithms to cognition/pom.xml**

Same dependency block after memory-api. (StrategyLearningOrchestrator uses TrendAnalyzer.)

- [ ] **Step 8: Full build to verify all consumers compile**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS — all modules compile, all tests pass

- [ ] **Step 9: Commit**

```bash
git add memory-cbr-inmem/pom.xml memory-cbr-jpa*/pom.xml memory-cbr-spring-jpa/pom.xml memory-qdrant/pom.xml memory-core/pom.xml memory-testing/pom.xml cognition/pom.xml
git commit -m "refactor(#360): add cbr-algorithms dependency to all consumers

Modules that import algorithm classes (CbrSimilarityScorer, CbrRecordValidator,
CbrRecordFilterMatcher, TrendAnalyzer, LbKeogh) now depend on
cbr-algorithms alongside memory-api.

Refs #360"
```

---

## Batch 3: Update documentation

### Task 3: Update CLAUDE.md and close issue

**Files:**
- Modify: `CLAUDE.md` (module structure, Maven coordinates)

- [ ] **Step 1: Add cbr-algorithms to module structure in CLAUDE.md**

In the module structure block, add after `memory-api/`:

```
cbr-algorithms/     — pure-Java CBR scoring (CbrSimilarityScorer), DTW (DtwSimilarity, LbKeogh), edit distance (EditDistanceSimilarity), trend analysis (TrendAnalyzer), validation (CbrRecordValidator, CbrRecordFilterMatcher). Tier 1 — zero CDI.
```

- [ ] **Step 2: Add Maven coordinates to CLAUDE.md**

In the Maven Coordinates table, add after the Memory API row:

```
| CBR Algorithms | `casehub-neocortex-cbr-algorithms` |
```

And in the root Java package table:

```
| Root Java package (cbr-algorithms) | `io.casehub.neocortex.memory.cbr` |
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(#360): add cbr-algorithms to module structure and Maven coordinates

Closes #360"
```

## References

- [2026-10-29-extract-cbr-algorithms-design.md] — design spec
- [memory-api/pom.xml] — source module POM
- [pom.xml:16-95] — parent module list
- [pom.xml:420-424] — memory-api dependencyManagement entry
- [memory-cbr-inmem/pom.xml] — consumer POM pattern
- casehubio/neocortex#360 — focal issue
- casehubio/neocortex#355 — parent issue
