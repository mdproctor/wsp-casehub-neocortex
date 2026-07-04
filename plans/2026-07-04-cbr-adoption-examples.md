# CBR Adoption & Examples — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use hortora:subagent-driven-development (recommended) or hortora:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all CBR adoption gaps with a unified example module (6 domain demos) and documentation updates.

**Architecture:** Single `examples/example-cbr/` module with six demo classes following the `example-text-analysis` pattern: static seed data, `run(CbrCaseMemoryStore)`, `printResults()`, `main()`. Smoke tests use `InMemoryCbrCaseMemoryStore` directly (no CDI). Integration tests use `@QuarkusTest` + Qdrant Testcontainers + `EmbeddingModel`.

**Tech Stack:** Java 21, JUnit 5, AssertJ, `memory-api` types, `memory-cbr-inmem` for smoke, `memory-qdrant` + `langchain4j-embeddings-all-minilm-l6-v2` for integration.

## Global Constraints

- Java source level 21, target JVM 26 (`JAVA_HOME=$(/usr/libexec/java_home -v 26)`)
- Build: `mvn` (not `./mvnw`)
- Parent version: `0.2-SNAPSHOT`
- groupId: `io.casehub`
- Package root: `io.casehub.neocortex.examples.cbr`
- All demo classes are `public final class`
- InMemory returns score 1.0 for all matches — expected output reflects this
- Every commit references an issue
- Existing `docs/cbr/cbr-types.md` and README CBR section already committed (8c7c1c3)

---

### Task 1: Module Scaffold + AML Demo

**Files:**
- Create: `examples/example-cbr/pom.xml`
- Modify: `pom.xml` (parent — add module + profile entries)
- Create: `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/AmlInvestigationDemo.java`
- Create: `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/AmlInvestigationDemoTest.java`

**Interfaces:**
- Consumes: `CbrCaseMemoryStore`, `CbrFeatureSchema`, `FeatureField`, `FeatureVectorCbrCase`, `CbrQuery`, `ScoredCbrCase`, `MemoryDomain` from `memory-api`
- Produces: `AmlInvestigationDemo.run(CbrCaseMemoryStore)` returning `List<AmlInvestigationDemo.Result>` — consumed by `CbrDemoRunner` (Task 5) and `CbrIntegrationIT` (Task 6)

- [ ] **Step 1: Create `examples/example-cbr/pom.xml`**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>0.2-SNAPSHOT</version>
        <relativePath>../../pom.xml</relativePath>
    </parent>

    <artifactId>casehub-neocortex-example-cbr</artifactId>
    <name>casehub-neocortex-example-cbr</name>
    <description>CBR demo — six domains showing Feature-Vector and Plan-Based retrieval</description>

    <dependencies>
        <!-- CBR API types (compile) -->
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-api</artifactId>
        </dependency>

        <!-- In-memory backend for main() and smoke tests -->
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-cbr-inmem</artifactId>
        </dependency>

        <!-- Test -->
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
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-surefire-plugin</artifactId>
                <configuration>
                    <reuseForks>false</reuseForks>
                </configuration>
            </plugin>
        </plugins>
    </build>

    <profiles>
        <profile>
            <id>examples-smoke</id>
            <build>
                <plugins>
                    <plugin>
                        <groupId>org.apache.maven.plugins</groupId>
                        <artifactId>maven-surefire-plugin</artifactId>
                        <configuration>
                            <groups>smoke</groups>
                            <reuseForks>false</reuseForks>
                        </configuration>
                    </plugin>
                </plugins>
            </build>
        </profile>
    </profiles>
</project>
```

- [ ] **Step 2: Add module to parent `pom.xml`**

Add `<module>examples/example-cbr</module>` after the existing example modules in the `<modules>` block, and in both `examples-smoke` and `examples` profiles.

In the `<modules>` block (after `examples/example-rag-pipeline`):
```xml
<module>examples/example-cbr</module>
```

In the `examples-smoke` profile `<modules>`:
```xml
<module>examples/example-cbr</module>
```

In the `examples` profile `<modules>`:
```xml
<module>examples/example-cbr</module>
```

- [ ] **Step 3: Verify the scaffold compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean compile -pl examples/example-cbr -am`
Expected: BUILD SUCCESS

- [ ] **Step 4: Write the AML smoke test**

Create `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/AmlInvestigationDemoTest.java`:

```java
package io.casehub.neocortex.examples.cbr;

import io.casehub.neocortex.memory.cbr.FeatureVectorCbrCase;
import io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrCaseMemoryStore;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class AmlInvestigationDemoTest {

    @Test
    void structuringQueryReturnsMatchingCases() {
        var store = new InMemoryCbrCaseMemoryStore();
        var results = AmlInvestigationDemo.run(store);

        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(r -> {
            assertThat(r.scored().score()).isEqualTo(1.0);
            assertThat(r.scored().cbrCase()).isInstanceOf(FeatureVectorCbrCase.class);
            var c = (FeatureVectorCbrCase) r.scored().cbrCase();
            assertThat(c.problem()).isNotBlank();
            assertThat(c.solution()).isNotBlank();
            assertThat(c.features().get("transaction_pattern")).isEqualTo("STRUCTURING");
        });
    }

    @Test
    void resultCountMatchesSeedData() {
        var store = new InMemoryCbrCaseMemoryStore();
        var results = AmlInvestigationDemo.run(store);
        // 4 of 10 seed cases have transaction_pattern=STRUCTURING
        assertThat(results).hasSize(4);
    }

    @Test
    void outcomesIncludeSarFiledAndCleared() {
        var store = new InMemoryCbrCaseMemoryStore();
        var results = AmlInvestigationDemo.run(store);
        var outcomes = results.stream()
            .map(r -> ((FeatureVectorCbrCase) r.scored().cbrCase()).outcome())
            .toList();
        assertThat(outcomes).contains("SAR_FILED", "CLEARED");
    }
}
```

- [ ] **Step 5: Run the test — verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples-smoke`
Expected: COMPILATION ERROR — `AmlInvestigationDemo` does not exist

- [ ] **Step 6: Write `AmlInvestigationDemo.java`**

Create `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/AmlInvestigationDemo.java`:

```java
package io.casehub.neocortex.examples.cbr;

import io.casehub.neocortex.memory.MemoryDomain;
import io.casehub.neocortex.memory.cbr.CbrCaseMemoryStore;
import io.casehub.neocortex.memory.cbr.CbrFeatureSchema;
import io.casehub.neocortex.memory.cbr.CbrQuery;
import io.casehub.neocortex.memory.cbr.FeatureField;
import io.casehub.neocortex.memory.cbr.FeatureVectorCbrCase;
import io.casehub.neocortex.memory.cbr.ScoredCbrCase;
import io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrCaseMemoryStore;

import java.util.List;
import java.util.Map;
import java.util.UUID;

public final class AmlInvestigationDemo {

    static final MemoryDomain DOMAIN = new MemoryDomain("aml");
    static final String TENANT = "demo";
    static final String CASE_TYPE = "aml-investigation";

    static final CbrFeatureSchema SCHEMA = CbrFeatureSchema.of(CASE_TYPE,
        FeatureField.categorical("transaction_pattern"),
        FeatureField.categorical("entity_risk_tier"),
        FeatureField.categorical("jurisdiction"),
        FeatureField.categorical("amount_range"),
        FeatureField.numeric("prior_sars_on_entity", 0, 100),
        FeatureField.text("investigation_narrative"));

    record SeedCase(String problem, String solution, String outcome,
                    double confidence, Map<String, Object> features) {}

    public record Result(ScoredCbrCase<FeatureVectorCbrCase> scored) {}

    static final List<SeedCase> SEED_CASES = List.of(
        new SeedCase(
            "Multiple cash deposits under $10,000 across 3 branches within 48 hours, beneficial owner linked to shell company in Cyprus",
            "Evidence path: bank statement analysis → beneficial ownership → SAR. Duration: 8 days.",
            "SAR_FILED", 0.92,
            Map.of("transaction_pattern", "STRUCTURING", "entity_risk_tier", "HIGH",
                   "jurisdiction", "CY", "amount_range", "50K-100K",
                   "prior_sars_on_entity", 2,
                   "investigation_narrative", "Multiple cash deposits under $10,000 across 3 branches within 48 hours")),
        new SeedCase(
            "Series of $9,000 cash deposits at different branches over two weeks, HIGH risk entity, Cyprus shell company",
            "Evidence path: transaction pattern → KYC gaps → SAR. Duration: 14 days.",
            "SAR_FILED", 0.88,
            Map.of("transaction_pattern", "STRUCTURING", "entity_risk_tier", "HIGH",
                   "jurisdiction", "CY", "amount_range", "50K-100K",
                   "prior_sars_on_entity", 0,
                   "investigation_narrative", "Series of $9,000 cash deposits at different branches")),
        new SeedCase(
            "Cash deposits just below reporting threshold from PEP-linked entity, funds moved to UK account",
            "Evidence path: transaction analysis → enhanced due diligence → SAR. Duration: 12 days.",
            "SAR_FILED", 0.85,
            Map.of("transaction_pattern", "STRUCTURING", "entity_risk_tier", "PEP",
                   "jurisdiction", "GB", "amount_range", "100K-500K",
                   "prior_sars_on_entity", 1,
                   "investigation_narrative", "Cash deposits from PEP-linked entity, funds transferred to UK")),
        new SeedCase(
            "Regular cash deposits under $10,000 from seasonal business — ice cream van operator with documented revenue",
            "Evidence path: bank statement → business verification → cleared. Duration: 6 days.",
            "CLEARED", 0.95,
            Map.of("transaction_pattern", "STRUCTURING", "entity_risk_tier", "LOW",
                   "jurisdiction", "US", "amount_range", "10K-50K",
                   "prior_sars_on_entity", 0,
                   "investigation_narrative", "Regular cash deposits from seasonal business")),
        new SeedCase(
            "Funds moved through 5 intermediary accounts across 3 jurisdictions before reaching final beneficiary",
            "Evidence path: network analysis → cross-border trace → SAR. Duration: 21 days.",
            "SAR_FILED", 0.91,
            Map.of("transaction_pattern", "LAYERING", "entity_risk_tier", "HIGH",
                   "jurisdiction", "MT", "amount_range", "500K+",
                   "prior_sars_on_entity", 3,
                   "investigation_narrative", "Funds layered through 5 intermediary accounts across 3 jurisdictions")),
        new SeedCase(
            "Multiple small wire transfers to same beneficiary from different source accounts, Malta corridor",
            "Evidence path: network mapping → KYC review → monitoring. Duration: 10 days.",
            "ESCALATED", 0.72,
            Map.of("transaction_pattern", "LAYERING", "entity_risk_tier", "MEDIUM",
                   "jurisdiction", "MT", "amount_range", "100K-500K",
                   "prior_sars_on_entity", 0,
                   "investigation_narrative", "Small wire transfers from multiple source accounts to single beneficiary")),
        new SeedCase(
            "10 individuals each depositing $9,500 at different branches on the same day for the same entity",
            "Evidence path: coordinated deposit analysis → smurfing pattern confirmed → SAR. Duration: 5 days.",
            "SAR_FILED", 0.96,
            Map.of("transaction_pattern", "SMURFING", "entity_risk_tier", "HIGH",
                   "jurisdiction", "US", "amount_range", "50K-100K",
                   "prior_sars_on_entity", 0,
                   "investigation_narrative", "Coordinated deposits by 10 individuals at different branches")),
        new SeedCase(
            "Wire transfer sent and returned between two related entities in different jurisdictions, no economic purpose",
            "Evidence path: transaction trace → related party analysis → SAR. Duration: 9 days.",
            "SAR_FILED", 0.89,
            Map.of("transaction_pattern", "ROUND_TRIP", "entity_risk_tier", "MEDIUM",
                   "jurisdiction", "LU", "amount_range", "100K-500K",
                   "prior_sars_on_entity", 1,
                   "investigation_narrative", "Wire transfer round-trip between related entities")),
        new SeedCase(
            "Large cash deposit from business with documented high cash turnover — cleared after enhanced due diligence",
            "Evidence path: business verification → site visit → cleared. Duration: 4 days.",
            "CLEARED", 0.97,
            Map.of("transaction_pattern", "LAYERING", "entity_risk_tier", "LOW",
                   "jurisdiction", "DE", "amount_range", "50K-100K",
                   "prior_sars_on_entity", 0,
                   "investigation_narrative", "Large cash deposit from legitimate high-turnover business")),
        new SeedCase(
            "Series of just-below-threshold international wires from PEP entity, rapid velocity over 72 hours",
            "Evidence path: velocity analysis → PEP screening → SAR. Duration: 7 days.",
            "SAR_FILED", 0.90,
            Map.of("transaction_pattern", "SMURFING", "entity_risk_tier", "PEP",
                   "jurisdiction", "CY", "amount_range", "100K-500K",
                   "prior_sars_on_entity", 4,
                   "investigation_narrative", "Below-threshold international wires from PEP entity"))
    );

    public static List<Result> run(CbrCaseMemoryStore store) {
        store.registerSchema(SCHEMA);

        for (var seed : SEED_CASES) {
            var cbrCase = new FeatureVectorCbrCase(
                seed.problem(), seed.solution(), seed.outcome(), seed.confidence(), seed.features());
            store.store(cbrCase, CASE_TYPE, UUID.randomUUID().toString(), DOMAIN, TENANT, UUID.randomUUID().toString());
        }

        var query = CbrQuery.of(TENANT, DOMAIN, CASE_TYPE,
            Map.of("transaction_pattern", "STRUCTURING"), 10);

        return store.retrieveSimilar(query, FeatureVectorCbrCase.class).stream()
            .map(Result::new)
            .toList();
    }

    static void printResults(List<Result> results) {
        System.out.println("AML Investigation — CBR Results");
        System.out.println("================================");
        System.out.printf("Query: transaction_pattern=STRUCTURING — new entity alert%n%n");
        System.out.printf("%d similar investigations found (of %d in case base)%n%n",
            results.size(), SEED_CASES.size());

        for (int i = 0; i < results.size(); i++) {
            var c = results.get(i).scored().cbrCase();
            System.out.printf("  #%d [%.2f] %s — %s%n", i + 1,
                results.get(i).scored().score(), c.outcome(), truncate(c.problem(), 70));
            System.out.printf("            %s%n%n", c.solution());
        }

        long sarCount = results.stream()
            .filter(r -> "SAR_FILED".equals(r.scored().cbrCase().outcome()))
            .count();
        System.out.printf("Summary: %d%% SAR filing rate for STRUCTURING cases.%n",
            results.isEmpty() ? 0 : sarCount * 100 / results.size());
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max - 3) + "...";
    }

    public static void main(String[] args) {
        var store = new InMemoryCbrCaseMemoryStore();
        printResults(run(store));
    }
}
```

- [ ] **Step 7: Run the smoke test — verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples-smoke`
Expected: 3 tests PASS

- [ ] **Step 8: Run `main()` to see output**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn exec:java -pl examples/example-cbr -Dexec.mainClass=io.casehub.neocortex.examples.cbr.AmlInvestigationDemo`
Expected: Formatted AML investigation output with 4 STRUCTURING cases, all scored 1.00

- [ ] **Step 9: Commit**

```bash
git add examples/example-cbr/ pom.xml
git commit -m "feat(#TBD): example-cbr scaffold + AmlInvestigationDemo

Module scaffold with surefire profiles (smoke/integration).
AML demo: 10 seed investigations, STRUCTURING query, SAR filing rate summary."
```

---

### Task 2: Feature-Vector Demos (Clinical, DevTown, Life, IoT)

**Files:**
- Create: `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/ClinicalAdverseEventDemo.java`
- Create: `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/DevtownPrReviewDemo.java`
- Create: `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/LifeContractorDemo.java`
- Create: `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/IotSituationDemo.java`
- Create: `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/ClinicalAdverseEventDemoTest.java`
- Create: `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/DevtownPrReviewDemoTest.java`
- Create: `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/LifeContractorDemoTest.java`
- Create: `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/IotSituationDemoTest.java`

**Interfaces:**
- Consumes: Same `memory-api` types as Task 1
- Produces: `ClinicalAdverseEventDemo.run(CbrCaseMemoryStore)` → `List<Result>`, `DevtownPrReviewDemo.run(...)` → `List<Result>`, `LifeContractorDemo.run(...)` → `List<Result>`, `IotSituationDemo.run(...)` → `List<Result>` — consumed by CbrDemoRunner (Task 5)

Each demo follows the exact same structural pattern as `AmlInvestigationDemo` (Task 1): `SCHEMA`, `SEED_CASES`, `run()`, `printResults()`, `main()`, `SeedCase` record, `Result` record. Only the domain-specific content differs.

- [ ] **Step 1: Write the four smoke tests**

Each test class follows the AML test pattern from Task 1. Key assertions per domain:

**ClinicalAdverseEventDemoTest** — query filters on `adverse_event_type=Hepatotoxicity` + `trial_arm=TREATMENT`. Assert 3 results, all scored 1.0, all `FeatureVectorCbrCase` with matching categorical features. Assert outcomes include `SAFETY_PROTOCOL`.

**DevtownPrReviewDemoTest** — query filters on `change_type=REFACTOR`. Assert 5 results (all refactors across languages), all scored 1.0. Assert outcomes include both `APPROVED` and `CHANGES_REQUESTED`.

**LifeContractorDemoTest** — query filters on `job_type=PLUMBING` + `property_area=HVAC`. Assert 4 results, all scored 1.0. Assert outcomes include `COMPLETED_ON_TIME` and `DELAYED`.

**IotSituationDemoTest** — query filters on `situation_type=TEMPERATURE_ANOMALY` + `room_type=KITCHEN`. Assert 5 results, all scored 1.0. Assert outcomes include `OPERATOR_DISMISSED` and `WORK_ITEM_CREATED`.

- [ ] **Step 2: Run tests — verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples-smoke`
Expected: COMPILATION ERROR — demo classes do not exist

- [ ] **Step 3: Write all four demo classes**

Each demo class uses the schema, seed data, query, and output format from the spec (§Demo Domains, sections 2-5). Follow the `AmlInvestigationDemo` pattern exactly:

**ClinicalAdverseEventDemo:**
- Schema: `adverse_event_type` (categorical), `trial_arm` (categorical), `severity_grade` (numeric 1-5), `time_to_onset_days` (numeric 0-365), `event_description` (text)
- 10 seed cases: hepatotoxicity/nephrotoxicity/neutropenia across treatment/control, grades 1-4, onset day 7-180
- Query: `Map.of("adverse_event_type", "Hepatotoxicity", "trial_arm", "TREATMENT")`
- Summary: safety protocol trigger rate, median onset, statin warning

**DevtownPrReviewDemo:**
- Schema: `language` (categorical), `change_type` (categorical), `files_changed` (numeric 1-1000), `lines_changed` (numeric 1-50000), `pr_description` (text)
- 10 seed cases: Java/Kotlin/TypeScript/Python, feature/bugfix/refactor/docs/test, various scales
- Query: `Map.of("change_type", "REFACTOR")`
- Summary: first-pass approval rate, recommended reviewers, top risk

**LifeContractorDemo:**
- Schema: `job_type` (categorical), `urgency` (categorical), `property_area` (categorical), `cost_band` (categorical), `season` (categorical), `job_description` (text)
- 10 seed cases: plumbing/electrical/roofing/appliance jobs with realistic contractor names, costs, SLA data
- Query: `Map.of("job_type", "PLUMBING", "property_area", "HVAC")`
- Summary: per-contractor performance, suggested SLA

**IotSituationDemo:**
- Schema: `situation_type` (categorical), `device_class` (categorical), `room_type` (categorical), `time_of_day` (categorical), `severity` (categorical), `situation_description` (text)
- 10 seed cases: temperature/motion/water/smoke situations, mix of genuine and false positives
- Query: `Map.of("situation_type", "TEMPERATURE_ANOMALY", "room_type", "KITCHEN")`
- Summary: false positive rate, genuine vs cooking-related, auto-downgrade suggestion

Seed data must be designed so the query result counts match the test assertions: 3 clinical hepatotoxicity/treatment cases, 5 devtown refactors, 4 life plumbing/HVAC cases, 5 IoT kitchen temperature cases.

- [ ] **Step 4: Run all smoke tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples-smoke`
Expected: 15 tests PASS (3 per domain × 5 domains including AML)

- [ ] **Step 5: Commit**

```bash
git add examples/example-cbr/src/
git commit -m "feat(#TBD): Feature-Vector demos — clinical, devtown, life, IoT

Four domain demos following AML pattern. Each: 10 seed cases,
categorical query, domain-specific summary output."
```

---

### Task 3: QuarkMind Plan-Based Demo

**Files:**
- Create: `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/QuarkmindBattleDemo.java`
- Create: `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/QuarkmindBattleDemoTest.java`

**Interfaces:**
- Consumes: `PlanCbrCase`, `PlanTrace` from `memory-api` (in addition to the types used by Task 1)
- Produces: `QuarkmindBattleDemo.run(CbrCaseMemoryStore)` → `List<QuarkmindBattleDemo.Result>` — consumed by CbrDemoRunner (Task 5)

- [ ] **Step 1: Write the smoke test**

Create `QuarkmindBattleDemoTest.java`:

```java
package io.casehub.neocortex.examples.cbr;

import io.casehub.neocortex.memory.cbr.PlanCbrCase;
import io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrCaseMemoryStore;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class QuarkmindBattleDemoTest {

    @Test
    void zergRoachRushQueryReturnsMatchingGames() {
        var store = new InMemoryCbrCaseMemoryStore();
        var results = QuarkmindBattleDemo.run(store);

        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(r -> {
            assertThat(r.scored().score()).isEqualTo(1.0);
            assertThat(r.scored().cbrCase()).isInstanceOf(PlanCbrCase.class);
            var c = r.scored().cbrCase();
            assertThat(c.features().get("opponent_race")).isEqualTo("ZERG");
            assertThat(c.features().get("detected_build")).isEqualTo("ROACH_RUSH");
        });
    }

    @Test
    void resultCountMatchesSeedData() {
        var store = new InMemoryCbrCaseMemoryStore();
        var results = QuarkmindBattleDemo.run(store);
        // 5 of 10 seed cases have opponent_race=ZERG + detected_build=ROACH_RUSH
        assertThat(results).hasSize(5);
    }

    @Test
    void planTracesArePreserved() {
        var store = new InMemoryCbrCaseMemoryStore();
        var results = QuarkmindBattleDemo.run(store);
        assertThat(results).allSatisfy(r -> {
            var c = r.scored().cbrCase();
            assertThat(c.planTrace()).isNotEmpty();
            assertThat(c.planTrace()).allSatisfy(t -> {
                assertThat(t.bindingName()).isNotBlank();
                assertThat(t.capabilityName()).isNotBlank();
                assertThat(t.priority()).isGreaterThanOrEqualTo(0);
            });
        });
    }

    @Test
    void planAnalysisShowsScoutCorrelation() {
        var store = new InMemoryCbrCaseMemoryStore();
        var results = QuarkmindBattleDemo.run(store);
        // Games with "scout" binding should correlate with wins
        long winsWithScout = results.stream()
            .filter(r -> "WIN".equals(r.scored().cbrCase().outcome()))
            .filter(r -> r.scored().cbrCase().planTrace().stream()
                .anyMatch(t -> "scout".equals(t.bindingName())))
            .count();
        assertThat(winsWithScout).isGreaterThanOrEqualTo(3);
    }
}
```

- [ ] **Step 2: Run test — verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples-smoke`
Expected: COMPILATION ERROR — `QuarkmindBattleDemo` does not exist

- [ ] **Step 3: Write `QuarkmindBattleDemo.java`**

Uses `PlanCbrCase` with `List<PlanTrace>` plan traces. Schema: `opponent_race`, `detected_build` (categorical), `army_size_ratio` (numeric 0-3), `resource_advantage` (numeric -5000 to 5000).

10 seed cases: 5 vs ZERG/ROACH_RUSH (4 wins, 1 loss), 5 vs other matchups. Each case has 3-5 plan trace steps with binding→capability→worker→outcome chains.

The `printResults()` method includes plan trace analysis: binding frequency across wins vs losses, scout correlation with wins, suggested opening sequence. Use the exact output format from the spec §6 (QuarkMind).

Query: `Map.of("opponent_race", "ZERG", "detected_build", "ROACH_RUSH")`

Plan analysis logic in `printResults()`:
```java
// Count binding appearances in winning vs losing games
Map<String, long[]> bindingStats = new LinkedHashMap<>();
for (var result : results) {
    var c = result.scored().cbrCase();
    boolean isWin = "WIN".equals(c.outcome());
    for (var trace : c.planTrace()) {
        bindingStats.computeIfAbsent(trace.bindingName(), k -> new long[2]);
        bindingStats.get(trace.bindingName())[isWin ? 0 : 1]++;
    }
}
```

- [ ] **Step 4: Run all smoke tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples-smoke`
Expected: 19 tests PASS (3+3+3+3+3+4 across all six domains)

- [ ] **Step 5: Commit**

```bash
git add examples/example-cbr/src/
git commit -m "feat(#TBD): QuarkmindBattleDemo — Plan-Based CBR with plan trace analysis

PlanCbrCase demo: 10 seed games, ZERG/ROACH_RUSH query, binding
frequency analysis, scout correlation, suggested opening sequence."
```

---

### Task 4: CbrDemoRunner

**Files:**
- Create: `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/CbrDemoRunner.java`
- Create: `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/CbrDemoRunnerTest.java`

**Interfaces:**
- Consumes: All six `Demo.run(CbrCaseMemoryStore)` methods from Tasks 1-3
- Produces: `CbrDemoRunner.run(CbrCaseMemoryStore)` → runs all six demos, prints unified output

- [ ] **Step 1: Write the smoke test**

```java
package io.casehub.neocortex.examples.cbr;

import io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrCaseMemoryStore;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class CbrDemoRunnerTest {

    @Test
    void allSixDemosRunWithoutError() {
        var store = new InMemoryCbrCaseMemoryStore();
        // Should not throw — all six demos register schemas, store, and query
        var allResults = CbrDemoRunner.run(store);
        assertThat(allResults).hasSize(6);
        assertThat(allResults.values()).allSatisfy(
            results -> assertThat(results).isNotEmpty());
    }
}
```

- [ ] **Step 2: Run test — verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples-smoke`
Expected: COMPILATION ERROR

- [ ] **Step 3: Write `CbrDemoRunner.java`**

```java
package io.casehub.neocortex.examples.cbr;

import io.casehub.neocortex.memory.cbr.CbrCaseMemoryStore;
import io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrCaseMemoryStore;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class CbrDemoRunner {

    public static Map<String, List<?>> run(CbrCaseMemoryStore store) {
        var results = new LinkedHashMap<String, List<?>>();
        results.put("AML Investigation", AmlInvestigationDemo.run(store));
        results.put("Clinical Adverse Event", ClinicalAdverseEventDemo.run(store));
        results.put("DevTown PR Review", DevtownPrReviewDemo.run(store));
        results.put("Life Contractor", LifeContractorDemo.run(store));
        results.put("IoT Situation", IotSituationDemo.run(store));
        results.put("QuarkMind Battle", QuarkmindBattleDemo.run(store));
        return results;
    }

    public static void main(String[] args) {
        var store = new InMemoryCbrCaseMemoryStore();

        System.out.println("╔══════════════════════════════════════════════════╗");
        System.out.println("║  CaseHub CBR — Six Domain Demos                 ║");
        System.out.println("║  Same SPI, different schemas, different domains  ║");
        System.out.println("╚══════════════════════════════════════════════════╝");
        System.out.println();

        AmlInvestigationDemo.printResults(AmlInvestigationDemo.run(store));
        System.out.println("\n" + "─".repeat(60) + "\n");
        ClinicalAdverseEventDemo.printResults(ClinicalAdverseEventDemo.run(store));
        System.out.println("\n" + "─".repeat(60) + "\n");
        DevtownPrReviewDemo.printResults(DevtownPrReviewDemo.run(store));
        System.out.println("\n" + "─".repeat(60) + "\n");
        LifeContractorDemo.printResults(LifeContractorDemo.run(store));
        System.out.println("\n" + "─".repeat(60) + "\n");
        IotSituationDemo.printResults(IotSituationDemo.run(store));
        System.out.println("\n" + "─".repeat(60) + "\n");
        QuarkmindBattleDemo.printResults(QuarkmindBattleDemo.run(store));
    }
}
```

- [ ] **Step 4: Run all smoke tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples-smoke`
Expected: 20 tests PASS

- [ ] **Step 5: Run `CbrDemoRunner.main()` to see unified output**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn exec:java -pl examples/example-cbr -Dexec.mainClass=io.casehub.neocortex.examples.cbr.CbrDemoRunner`
Expected: All six domain outputs printed with separators

- [ ] **Step 6: Commit**

```bash
git add examples/example-cbr/src/
git commit -m "feat(#TBD): CbrDemoRunner — runs all six demos, unified output"
```

---

### Task 5: Integration Tests (Qdrant + EmbeddingModel)

**Files:**
- Modify: `examples/example-cbr/pom.xml` (add Quarkus, Qdrant, embedding deps + jandex plugin)
- Create: `examples/example-cbr/src/main/java/io/casehub/neocortex/examples/cbr/CbrExampleProducer.java`
- Create: `examples/example-cbr/src/main/resources/application.properties`
- Create: `examples/example-cbr/src/test/java/io/casehub/neocortex/examples/cbr/CbrIntegrationIT.java`

**Interfaces:**
- Consumes: All six `Demo.run()` methods, Qdrant Testcontainers, `EmbeddingModel` CDI bean
- Produces: Integration test proving dense vector search ranks semantically similar problems higher

- [ ] **Step 1: Add integration dependencies to `pom.xml`**

Add to `<dependencies>`:

```xml
<!-- CDI wiring (runtime) -->
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory</artifactId>
    <scope>runtime</scope>
</dependency>

<!-- Qdrant backend (test — integration only) -->
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-qdrant</artifactId>
    <scope>test</scope>
</dependency>

<!-- Embedding model for dense vector search on problem() -->
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-embeddings-all-minilm-l6-v2</artifactId>
    <scope>test</scope>
</dependency>

<!-- Quarkus test -->
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-junit5</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>testcontainers</artifactId>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>junit-jupiter</artifactId>
    <scope>test</scope>
</dependency>

<!-- Quarkus ARC for CDI -->
<dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-arc</artifactId>
</dependency>
```

Add jandex plugin to `<build><plugins>`:
```xml
<plugin>
    <groupId>io.smallrye</groupId>
    <artifactId>jandex-maven-plugin</artifactId>
    <executions>
        <execution>
            <id>make-index</id>
            <goals>
                <goal>jandex</goal>
            </goals>
        </execution>
    </executions>
</plugin>
```

Check the parent pom `<dependencyManagement>` for `langchain4j-embeddings-all-minilm-l6-v2`. If not present, add it with the LangChain4j version property. If unsure, check: `grep -n "langchain4j-embeddings" pom.xml`.

- [ ] **Step 2: Create `CbrExampleProducer.java`**

CDI producer that provides the `EmbeddingModel` bean for Qdrant's dense vector search:

```java
package io.casehub.neocortex.examples.cbr;

import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.allminilml6v2.AllMiniLmL6V2EmbeddingModel;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;

@ApplicationScoped
public class CbrExampleProducer {

    @Produces
    @ApplicationScoped
    EmbeddingModel embeddingModel() {
        return new AllMiniLmL6V2EmbeddingModel();
    }
}
```

- [ ] **Step 3: Create `application.properties`**

```properties
# Qdrant CBR configuration (Testcontainers provides host/port via DevServices)
casehub.memory.cbr.qdrant.collection-prefix=cbr-example
casehub.memory.cbr.qdrant.dense-vector-name=dense
```

- [ ] **Step 4: Write `CbrIntegrationIT.java`**

```java
package io.casehub.neocortex.examples.cbr;

import io.casehub.neocortex.memory.cbr.CbrCaseMemoryStore;
import io.casehub.neocortex.memory.cbr.CbrQuery;
import io.casehub.neocortex.memory.cbr.FeatureVectorCbrCase;
import io.casehub.neocortex.memory.cbr.PlanCbrCase;
import io.casehub.neocortex.memory.MemoryDomain;
import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@QuarkusTest
@Tag("integration")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class CbrIntegrationIT {

    @Inject CbrCaseMemoryStore store;

    @Test
    @Order(1)
    void seedAllDomains() {
        // Register schemas and store all seed data
        AmlInvestigationDemo.run(store);
        ClinicalAdverseEventDemo.run(store);
        DevtownPrReviewDemo.run(store);
        LifeContractorDemo.run(store);
        IotSituationDemo.run(store);
        QuarkmindBattleDemo.run(store);
    }

    @Test
    @Order(2)
    void denseVectorSearchRanksByProblemSimilarity() {
        // Query with problem text — Qdrant should rank by embedding similarity
        var query = CbrQuery.of("demo", new MemoryDomain("aml"),
                "aml-investigation", Map.of("transaction_pattern", "STRUCTURING"), 10)
            .withProblem("cash deposits split across branches to avoid reporting threshold");

        var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(results).isNotEmpty();
        // With dense vector search, scores should be < 1.0 (real cosine similarity)
        assertThat(results.get(0).score()).isLessThan(1.0);
        assertThat(results.get(0).score()).isGreaterThan(0.0);
    }

    @Test
    @Order(2)
    void minSimilarityFiltersLowScores() {
        var query = CbrQuery.of("demo", new MemoryDomain("aml"),
                "aml-investigation", Map.of("transaction_pattern", "STRUCTURING"), 10)
            .withProblem("cash deposits split across branches")
            .withMinSimilarity(0.99);

        var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
        // Very high threshold should filter most results
        assertThat(results).hasSizeLessThan(4);
    }

    @Test
    @Order(2)
    void planTraceRoundTripsThroughQdrant() {
        var query = CbrQuery.of("demo", new MemoryDomain("quarkmind"),
                "quarkmind-battle",
                Map.of("opponent_race", "ZERG", "detected_build", "ROACH_RUSH"), 10);

        var results = store.retrieveSimilar(query, PlanCbrCase.class);
        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(r -> {
            assertThat(r.cbrCase().planTrace()).isNotEmpty();
            assertThat(r.cbrCase().planTrace().get(0).bindingName()).isNotBlank();
        });
    }

    @Test
    @Order(2)
    void crossDomainIsolation() {
        // AML query should not return clinical cases
        var query = CbrQuery.of("demo", new MemoryDomain("aml"),
                "aml-investigation", Map.of("transaction_pattern", "STRUCTURING"), 100);

        var results = store.retrieveSimilar(query, FeatureVectorCbrCase.class);
        assertThat(results).allSatisfy(r ->
            assertThat(r.cbrCase().features().get("transaction_pattern")).isEqualTo("STRUCTURING"));
    }
}
```

- [ ] **Step 5: Run integration tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl examples/example-cbr -Pexamples`
Expected: All smoke + integration tests PASS (requires Docker for Qdrant Testcontainers)

If Qdrant Testcontainers require Quarkus Dev Services configuration, add to `application.properties`:
```properties
quarkus.qdrant.devservices.enabled=true
```

- [ ] **Step 6: Commit**

```bash
git add examples/example-cbr/
git commit -m "feat(#TBD): CBR integration tests — Qdrant + EmbeddingModel

@QuarkusTest with Testcontainers Qdrant. Verifies dense vector search
on problem(), minSimilarity filtering, plan trace round-trip, and
cross-domain isolation."
```

---

### Task 6: Documentation Updates

**Files:**
- Modify: `docs/cbr/README.md` (dense vector search, dual storage, config reference, dev mode, guide table)
- Create: `docs/cbr/guide-life.md`
- Create: `docs/cbr/guide-iot.md`
- Modify: `docs/cbr/guide-aml.md` (dense vector note, config, roadmap)
- Modify: `docs/cbr/guide-clinical.md` (dense vector note, config, roadmap)
- Modify: `docs/cbr/guide-devtown.md` (dense vector note, config, roadmap)
- Modify: `docs/cbr/guide-engine.md` (dense vector note, config, roadmap)
- Modify: `README.md` (update introduction paragraph)

**Interfaces:**
- Consumes: Existing docs, spec §Infrastructure Gap Closures
- Produces: Complete documentation — no downstream dependencies

- [ ] **Step 1: Add sections to `docs/cbr/README.md`**

Add these sections after the existing "Backends" section:

**Dense Vector Search:**
```markdown
## Dense Vector Search

`CbrQuery.withProblem(text)` enables embedding-based similarity search within
the filtered candidate set. Requires an `EmbeddingModel` CDI bean:

\```java
@ApplicationScoped
public class CbrEmbeddingProducer {
    @Produces @ApplicationScoped
    EmbeddingModel embeddingModel() {
        return new AllMiniLmL6V2EmbeddingModel();
    }
}
\```

Without an `EmbeddingModel` bean, queries fall back to payload-filter-only
retrieval with synthetic 1.0 scores. Dense vector search adds semantic ranking
within the structurally filtered set.

Maven dependency:
\```xml
<dependency>
    <groupId>dev.langchain4j</groupId>
    <artifactId>langchain4j-embeddings-all-minilm-l6-v2</artifactId>
</dependency>
\```
```

**Dual Storage:**
```markdown
## Dual Storage

The Qdrant backend operates in two modes:

- **Qdrant-only** (default): CBR data lives in Qdrant only. No additional
  dependencies. Start here.
- **Qdrant + CaseMemoryStore**: When a platform `CaseMemoryStore` bean is on
  the classpath, `QdrantCbrBeanProducer` delegates durable storage to it.
  Adds platform memory query APIs alongside CBR similarity search.
```

**Configuration Reference:**
```markdown
## Configuration Reference

\```properties
casehub.memory.cbr.qdrant.host=localhost
casehub.memory.cbr.qdrant.port=6334
# casehub.memory.cbr.qdrant.api-key=           # optional, for authenticated Qdrant
# casehub.memory.cbr.qdrant.use-tls=false      # enable for production
casehub.memory.cbr.qdrant.collection-prefix=cbr
casehub.memory.cbr.qdrant.dense-vector-name=dense
casehub.memory.cbr.qdrant.max-retries=3
\```
```

**Dev Mode:**
```markdown
## Dev Mode

InMemory validates SPI wiring — schema registration, store/retrieve round-trip,
query validation. It does not provide similarity ranking (all scores 1.0), text
matching, or persistence. For retrieval quality, use Qdrant via Testcontainers.

\```properties
%dev.quarkus.arc.selected-alternatives=io.casehub.neocortex.memory.cbr.inmem.InMemoryCbrCaseMemoryStore
\```

Add `memory-cbr-inmem` at `runtime` scope (not just `test`) to use in dev mode.
```

Update the App-Specific Guides table to add Life and IoT rows.

- [ ] **Step 2: Create `docs/cbr/guide-life.md` and `docs/cbr/guide-iot.md`**

Follow the exact structure of existing guides (guide-aml.md, guide-clinical.md): Why CBR, CBR Paradigm, Feature Schema, Retain, Retrieve, Mock→Production, Maven Dependencies. Use the schemas, domain context, and code patterns from the spec §4 (Life) and §5 (IoT).

- [ ] **Step 3: Update existing guides (aml, clinical, devtown, engine)**

Add to each guide:

1. **Dense Vector Search note** (after Maven Dependencies):
```markdown
## Dense Vector Search

To enable semantic similarity on `problem()`, provide an `EmbeddingModel` CDI
bean. See [Dense Vector Search](README.md#dense-vector-search) in the
integration guide.
```

2. **Configuration snippet** (after Dense Vector Search):
```markdown
## Qdrant Configuration

\```properties
casehub.memory.cbr.qdrant.host=localhost
casehub.memory.cbr.qdrant.port=6334
casehub.memory.cbr.qdrant.collection-prefix=cbr
\```
```

3. **Roadmap section** (at the bottom):
Domain-specific future phase list from the spec's "Future phases" notes.

- [ ] **Step 4: Update `README.md` introduction paragraph**

Change the opening paragraph (line 7) to mention all three module sets:
```
Local ONNX text inference, LangChain4j RAG wiring, and case-based reasoning (CBR) for the casehubio platform. Three module sets: `inference-*` covers scoring and classification; `rag-*` wires the retrieval pipeline; `memory-*` provides structured similarity search over past cases.
```

- [ ] **Step 5: Verify no broken links**

Run: `grep -rn '\[.*\](.*\.md)' docs/cbr/ | head -20`
Check each link target exists.

- [ ] **Step 6: Commit**

```bash
git add docs/cbr/ README.md
git commit -m "docs(#TBD): CBR adoption gaps — dense vector, dual storage, config, dev mode, guides

- docs/cbr/README.md: dense vector search, dual storage, config
  reference, dev mode sections
- docs/cbr/guide-life.md + guide-iot.md: new domain guides
- Existing guides: dense vector note, config, roadmap sections
- README.md: introduction mentions all three module sets"
```

---

### Task 7: Epic + Cross-References

**Files:**
- No code files

**Interfaces:**
- Consumes: Completed example module and documentation
- Produces: GitHub epic with child issues, cross-reference comments on app-side epics

- [ ] **Step 1: Create the GitHub epic on casehubio/neocortex**

Use `gh issue create` with the epic structure from the spec §Issue Breakdown. Title: `epic: CBR adoption & examples — six-domain demo module + documentation`. Label: `epic`. Include child issue checklist (A-K from spec).

- [ ] **Step 2: Create child issues**

Create individual issues for each Wave item (A through K) referencing the epic. Use labels for wave grouping.

- [ ] **Step 3: Comment on app-side epics**

Comment on each of these issues with a pointer to the example module:
- `aml#92`
- `devtown#129`
- `clinical#115`
- `life#52`
- `iot#48`
- `parent#227`

Comment template:
```
The neocortex `example-cbr` module ([neocortex#TBD]) has a runnable demo for this domain — schema, seed data, query, and formatted output. See `AmlInvestigationDemo.java` (or the domain-specific class) for the integration pattern your app will follow.
```

- [ ] **Step 4: Commit cross-reference notes (if any workspace artifact updates)**

---

## Self-Review Checklist

- [x] **Spec coverage:** All spec sections mapped to tasks — module scaffold (T1), Feature-Vector demos (T1-T2), Plan-Based demo (T3), CbrDemoRunner (T4), integration tests (T5), documentation (T6), cross-references (T7). Issue K (TextualCbrCase) is a future spec per review decision.
- [x] **Placeholder scan:** No TBDs in code blocks. `#TBD` in commit messages is intentional — replaced with the actual issue number once filed in Task 7.
- [x] **Type consistency:** `Result` record, `SeedCase` record, `run(CbrCaseMemoryStore)` return type, `printResults()` signature consistent across all tasks. `MemoryDomain`, `CbrQuery.of()`, `store.retrieveSimilar()` used identically.
