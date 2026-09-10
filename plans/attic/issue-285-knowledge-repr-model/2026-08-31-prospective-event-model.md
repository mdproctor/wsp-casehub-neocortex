# Prospective Event Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #241 — Prospective event model
**Issue group:** #253, #241

**Goal:** Add event trait classification, lifecycle convention, anticipatory affect annotation, and recurring event generation to MindMap nodes.

**Architecture:** Four independent concerns, all additive. Event traits use the existing TraitRule + TraitApplicationDecorator infrastructure. Anticipatory affect extends the AffectEvents converter with an attribute tag. RecurrenceRule is a new parsing record in mindmap-api; RecurrenceGenerator is a static utility in mindmap-intelligence.

**Tech Stack:** Java 21, Quarkus CDI, JUnit 5, AssertJ

## Global Constraints

- Java 21 source level, Java 26 JVM
- Build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- TraitRule implementations must be `@ApplicationScoped` CDI beans
- Property keys use camelCase (`eventKind`, not `event-kind`) for TraitProxy compatibility
- All new types are zero-deps (cognitive-api) or depend only on mindmap-api
- cognitive-api must remain zero-deps (no transitive dependencies beyond java.base)

---

## Batch 1: Event Trait Classification

### Task 1: AffectType enum + AffectEvents overload

**Files:**
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/AffectType.java`
- Modify: `memory-api/src/main/java/io/casehub/neocortex/memory/mood/AffectEvents.java`
- Modify: `memory-api/src/test/java/io/casehub/neocortex/memory/mood/AffectEventsTest.java`

**Interfaces:**
- Produces: `AffectType.INHERENT`, `AffectType.ANTICIPATORY` — used by Task 2 integration tests and external callers
- Produces: `AffectEvents.toMemoryInput(String, String, double, double, double, AffectType)` — 6-arg overload

- [ ] **Step 1: Write tests for AffectType-aware converter**

Add to `AffectEventsTest.java`:

```java
import io.casehub.neocortex.cognitive.AffectType;

@Test
void toMemoryInput_withInherentType_setsAttribute() {
    MemoryInput input = AffectEvents.toMemoryInput("node-1", "t1", 0.5, -0.3, 0.7, AffectType.INHERENT);
    assertThat(input.attributes()).containsEntry("affect-type", "inherent");
}

@Test
void toMemoryInput_withAnticipatoryType_setsAttribute() {
    MemoryInput input = AffectEvents.toMemoryInput("node-1", "t1", 0.5, -0.3, 0.7, AffectType.ANTICIPATORY);
    assertThat(input.attributes()).containsEntry("affect-type", "anticipatory");
}

@Test
void toMemoryInput_defaultOverload_setsInherent() {
    MemoryInput input = AffectEvents.toMemoryInput("node-1", "t1", 0.5, -0.3, 0.7);
    assertThat(input.attributes()).containsEntry("affect-type", "inherent");
}
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-api -Dtest=AffectEventsTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — `AffectType` does not exist

- [ ] **Step 3: Create AffectType enum**

Create `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/AffectType.java`:

```java
package io.casehub.neocortex.cognitive;

public enum AffectType {
    INHERENT,
    ANTICIPATORY
}
```

- [ ] **Step 4: Add 6-arg overload to AffectEvents and update existing overload**

Modify `AffectEvents.java` — add the new overload and make the existing 5-arg method delegate:

```java
import io.casehub.neocortex.cognitive.AffectType;

public static MemoryInput toMemoryInput(String nodeId, String tenantId,
                                        double pleasure, double arousal, double dominance) {
    return toMemoryInput(nodeId, tenantId, pleasure, arousal, dominance, AffectType.INHERENT);
}

public static MemoryInput toMemoryInput(String nodeId, String tenantId,
                                        double pleasure, double arousal, double dominance,
                                        AffectType affectType) {
    return new MemoryInput(nodeId, DOMAIN, tenantId, null, "PAD update",
                           Map.of("affect-type", affectType.name().toLowerCase()),
                           null, pleasure, arousal, dominance);
}
```

- [ ] **Step 5: Run tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api,memory-api -Dtest=AffectEventsTest`
Expected: all tests pass (existing + 3 new)

- [ ] **Step 6: Commit**

```
feat(cognitive-api): AffectType enum + AffectEvents overload

Refs #241
```

### Task 2: Eventlike trait interface + 4 TraitRule implementations

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Eventlike.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/AppointableTraitRule.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/AspirationalTraitRule.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/ThreateningTraitRule.java`
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/OpportunisticTraitRule.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/StandardTraitRulesTest.java`
- Modify: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TraitProxyTest.java`

**Interfaces:**
- Consumes: `TraitRule` from mindmap-api, `MindMapNode` + `MindMapEdge` from mindmap-api
- Produces: `Eventlike` interface — `eventKind()`, `eventValence()`, `status()`, `rrule()` returning `Optional<String>`
- Produces: `AppointableTraitRule`, `AspirationalTraitRule`, `ThreateningTraitRule`, `OpportunisticTraitRule` — `@ApplicationScoped` beans

- [ ] **Step 1: Write failing tests for all four trait rules**

Add to `StandardTraitRulesTest.java`:

```java
@Test
void appointableRule_matchesScheduled() {
    String id = store.addNode(new NodeInput("Team Meeting", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("eventKind", "scheduled")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    var rule = new AppointableTraitRule();
    assertThat(rule.traitName()).isEqualTo("Appointable");
    assertThat(rule.matches(node, List.of())).isTrue();
}

@Test
void appointableRule_noMatchWithoutEventKind() {
    String id = store.addNode(node("Future Thing"), "t1");
    MindMapNode node = store.getNode(id, "t1");
    assertThat(new AppointableTraitRule().matches(node, List.of())).isFalse();
}

@Test
void appointableRule_noMatchAnticipated() {
    String id = store.addNode(new NodeInput("Maybe Promotion", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("eventKind", "anticipated")), "t1");
    MindMapNode node = store.getNode(id, "t1");
    assertThat(new AppointableTraitRule().matches(node, List.of())).isFalse();
}

@Test
void aspirationalRule_matchesAnticipatedAspirations() {
    String id = store.addNode(new NodeInput("New Job", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("eventKind", "anticipated", "eventValence", "aspirational")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    var rule = new AspirationalTraitRule();
    assertThat(rule.traitName()).isEqualTo("Aspirational");
    assertThat(rule.matches(node, List.of())).isTrue();
}

@Test
void aspirationalRule_noMatchScheduled() {
    String id = store.addNode(new NodeInput("Meeting", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("eventKind", "scheduled", "eventValence", "aspirational")), "t1");
    MindMapNode node = store.getNode(id, "t1");
    assertThat(new AspirationalTraitRule().matches(node, List.of())).isFalse();
}

@Test
void threateningRule_matchesAnticipatedNegative() {
    String id = store.addNode(new NodeInput("Exam", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("eventKind", "anticipated", "eventValence", "negative")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    var rule = new ThreateningTraitRule();
    assertThat(rule.traitName()).isEqualTo("Threatening");
    assertThat(rule.matches(node, List.of())).isTrue();
}

@Test
void opportunisticRule_matchesAnticipatedPositive() {
    String id = store.addNode(new NodeInput("Bonus", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("eventKind", "anticipated", "eventValence", "positive")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    var rule = new OpportunisticTraitRule();
    assertThat(rule.traitName()).isEqualTo("Opportunistic");
    assertThat(rule.matches(node, List.of())).isTrue();
}

@Test
void composability_scheduledAndNegative_isAppointableNotThreatening() {
    String id = store.addNode(new NodeInput("Funeral", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("eventKind", "scheduled", "eventValence", "negative")), "t1");
    MindMapNode node = store.getNode(id, "t1");
    assertThat(new AppointableTraitRule().matches(node, List.of())).isTrue();
    assertThat(new ThreateningTraitRule().matches(node, List.of())).isFalse();
}
```

- [ ] **Step 2: Run tests — verify compilation failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=StandardTraitRulesTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure — trait rule classes do not exist

- [ ] **Step 3: Create Eventlike interface**

Create `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/Eventlike.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import java.util.Optional;

public interface Eventlike {
    Optional<String> eventKind();
    Optional<String> eventValence();
    Optional<String> status();
    Optional<String> rrule();
}
```

- [ ] **Step 4: Create four TraitRule implementations**

Create `AppointableTraitRule.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class AppointableTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Appointable"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        return node.property("eventKind").map("scheduled"::equals).orElse(false);
    }
}
```

Create `AspirationalTraitRule.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class AspirationalTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Aspirational"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        return node.property("eventKind").map("anticipated"::equals).orElse(false)
            && node.property("eventValence").map("aspirational"::equals).orElse(false);
    }
}
```

Create `ThreateningTraitRule.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class ThreateningTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Threatening"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        return node.property("eventKind").map("anticipated"::equals).orElse(false)
            && node.property("eventValence").map("negative"::equals).orElse(false);
    }
}
```

Create `OpportunisticTraitRule.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapEdge;
import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.TraitRule;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@ApplicationScoped
public class OpportunisticTraitRule implements TraitRule {

    @Override
    public String traitName() { return "Opportunistic"; }

    @Override
    public boolean matches(MindMapNode node, List<MindMapEdge> edges) {
        return node.property("eventKind").map("anticipated"::equals).orElse(false)
            && node.property("eventValence").map("positive"::equals).orElse(false);
    }
}
```

- [ ] **Step 5: Run trait rule tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=StandardTraitRulesTest`
Expected: all tests pass (existing + 8 new)

- [ ] **Step 6: Write Eventlike TraitProxy test**

Add to `TraitProxyTest.java`:

```java
@Test
void as_eventlike_readsProperties() {
    String id = store.addNode(new NodeInput("Team Meeting", subgraphId,
        null, "test", null, null,
        null, null, null, null, null,
        Map.of("eventKind", "scheduled", "eventValence", "positive",
               "status", "confirmed", "rrule", "FREQ=WEEKLY;BYDAY=MO")), "t1");
    MindMapNode node = store.getNode(id, "t1");

    Eventlike e = TraitProxy.as(node, Eventlike.class);
    assertThat(e.eventKind()).isEqualTo(Optional.of("scheduled"));
    assertThat(e.eventValence()).isEqualTo(Optional.of("positive"));
    assertThat(e.status()).isEqualTo(Optional.of("confirmed"));
    assertThat(e.rrule()).isEqualTo(Optional.of("FREQ=WEEKLY;BYDAY=MO"));
}

@Test
void as_eventlike_missingProperties_returnsEmpty() {
    String id = store.addNode(new NodeInput("Plain Node", subgraphId,
        null, "test", null, null,
        null, null, null, null, null, null), "t1");
    MindMapNode node = store.getNode(id, "t1");

    Eventlike e = TraitProxy.as(node, Eventlike.class);
    assertThat(e.eventKind()).isEmpty();
    assertThat(e.status()).isEmpty();
    assertThat(e.rrule()).isEmpty();
}
```

- [ ] **Step 7: Run TraitProxy tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=TraitProxyTest`
Expected: all tests pass

- [ ] **Step 8: Commit**

```
feat(mindmap-intelligence): event trait rules + Eventlike interface

Appointable, Aspirational, Threatening, Opportunistic TraitRule
implementations using eventKind/eventValence property convention.

Refs #241
```

---

## Batch 2: Recurring Events

### Task 3: RecurrenceRule record + parse/toString

**Files:**
- Create: `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RecurrenceRule.java`
- Create: `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/RecurrenceRuleTest.java`

**Interfaces:**
- Produces: `RecurrenceRule(Frequency freq, int interval, Integer count, Instant until, Set<DayOfWeek> byDay)` — record with `parse(String)` factory and `toString()`
- Produces: `RecurrenceRule.Frequency` enum — `DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY`

- [ ] **Step 1: Write failing tests for parse and toString**

Create `mindmap-api/src/test/java/io/casehub/neocortex/mindmap/RecurrenceRuleTest.java`:

```java
package io.casehub.neocortex.mindmap;

import org.junit.jupiter.api.Test;

import java.time.DayOfWeek;
import java.time.Instant;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class RecurrenceRuleTest {

    @Test
    void parse_weeklyMonday() {
        RecurrenceRule rule = RecurrenceRule.parse("FREQ=WEEKLY;BYDAY=MO");
        assertThat(rule.freq()).isEqualTo(RecurrenceRule.Frequency.WEEKLY);
        assertThat(rule.interval()).isEqualTo(1);
        assertThat(rule.count()).isNull();
        assertThat(rule.until()).isNull();
        assertThat(rule.byDay()).containsExactly(DayOfWeek.MONDAY);
    }

    @Test
    void parse_dailyWithInterval() {
        RecurrenceRule rule = RecurrenceRule.parse("FREQ=DAILY;INTERVAL=3");
        assertThat(rule.freq()).isEqualTo(RecurrenceRule.Frequency.DAILY);
        assertThat(rule.interval()).isEqualTo(3);
    }

    @Test
    void parse_monthlyWithCount() {
        RecurrenceRule rule = RecurrenceRule.parse("FREQ=MONTHLY;COUNT=12");
        assertThat(rule.freq()).isEqualTo(RecurrenceRule.Frequency.MONTHLY);
        assertThat(rule.count()).isEqualTo(12);
    }

    @Test
    void parse_yearlyWithUntil() {
        Instant until = Instant.parse("2027-12-31T23:59:59Z");
        RecurrenceRule rule = RecurrenceRule.parse("FREQ=YEARLY;UNTIL=20271231T235959Z");
        assertThat(rule.freq()).isEqualTo(RecurrenceRule.Frequency.YEARLY);
        assertThat(rule.until()).isEqualTo(until);
    }

    @Test
    void parse_multipleDays() {
        RecurrenceRule rule = RecurrenceRule.parse("FREQ=WEEKLY;BYDAY=MO,WE,FR");
        assertThat(rule.byDay()).containsExactlyInAnyOrder(
            DayOfWeek.MONDAY, DayOfWeek.WEDNESDAY, DayOfWeek.FRIDAY);
    }

    @Test
    void parse_missingFreq_throws() {
        assertThatThrownBy(() -> RecurrenceRule.parse("INTERVAL=2"))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void toString_roundTrip() {
        String original = "FREQ=WEEKLY;INTERVAL=2;BYDAY=MO,WE,FR";
        RecurrenceRule rule = RecurrenceRule.parse(original);
        RecurrenceRule reparsed = RecurrenceRule.parse(rule.toString());
        assertThat(reparsed).isEqualTo(rule);
    }

    @Test
    void toString_minimalDaily() {
        RecurrenceRule rule = new RecurrenceRule(
            RecurrenceRule.Frequency.DAILY, 1, null, null, Set.of());
        assertThat(rule.toString()).isEqualTo("FREQ=DAILY");
    }

    @Test
    void defaultInterval_isOne() {
        RecurrenceRule rule = RecurrenceRule.parse("FREQ=DAILY");
        assertThat(rule.interval()).isEqualTo(1);
    }
}
```

- [ ] **Step 2: Run tests — verify compilation failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=RecurrenceRuleTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure

- [ ] **Step 3: Implement RecurrenceRule record**

Create `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/RecurrenceRule.java`:

```java
package io.casehub.neocortex.mindmap;

import java.time.DayOfWeek;
import java.time.Instant;
import java.time.format.DateTimeFormatter;
import java.time.ZoneOffset;
import java.util.EnumMap;
import java.util.LinkedHashSet;
import java.util.Map;
import java.util.Set;
import java.util.StringJoiner;

public record RecurrenceRule(
    Frequency freq,
    int interval,
    Integer count,
    Instant until,
    Set<DayOfWeek> byDay
) {
    public enum Frequency { DAILY, WEEKLY, MONTHLY, YEARLY }

    private static final DateTimeFormatter UNTIL_FORMAT =
        DateTimeFormatter.ofPattern("yyyyMMdd'T'HHmmss'Z'").withZone(ZoneOffset.UTC);

    private static final Map<String, DayOfWeek> DAY_MAP = Map.of(
        "MO", DayOfWeek.MONDAY, "TU", DayOfWeek.TUESDAY,
        "WE", DayOfWeek.WEDNESDAY, "TH", DayOfWeek.THURSDAY,
        "FR", DayOfWeek.FRIDAY, "SA", DayOfWeek.SATURDAY,
        "SU", DayOfWeek.SUNDAY);

    private static final Map<DayOfWeek, String> DAY_REVERSE;
    static {
        DAY_REVERSE = new EnumMap<>(DayOfWeek.class);
        DAY_MAP.forEach((k, v) -> DAY_REVERSE.put(v, k));
    }

    public RecurrenceRule {
        if (freq == null) throw new IllegalArgumentException("freq must not be null");
        if (interval < 1) throw new IllegalArgumentException("interval must be >= 1");
        byDay = byDay == null ? Set.of() : Set.copyOf(byDay);
    }

    public static RecurrenceRule parse(String rrule) {
        Frequency freq = null;
        int interval = 1;
        Integer count = null;
        Instant until = null;
        Set<DayOfWeek> byDay = new LinkedHashSet<>();

        for (String part : rrule.split(";")) {
            String[] kv = part.split("=", 2);
            if (kv.length != 2) continue;
            switch (kv[0]) {
                case "FREQ" -> freq = Frequency.valueOf(kv[1]);
                case "INTERVAL" -> interval = Integer.parseInt(kv[1]);
                case "COUNT" -> count = Integer.parseInt(kv[1]);
                case "UNTIL" -> until = UNTIL_FORMAT.parse(kv[1], Instant::from);
                case "BYDAY" -> {
                    for (String d : kv[1].split(",")) {
                        DayOfWeek day = DAY_MAP.get(d);
                        if (day == null) throw new IllegalArgumentException("Unknown day: " + d);
                        byDay.add(day);
                    }
                }
            }
        }
        if (freq == null) throw new IllegalArgumentException("FREQ is required");
        return new RecurrenceRule(freq, interval, count, until, byDay);
    }

    @Override
    public String toString() {
        StringJoiner sj = new StringJoiner(";");
        sj.add("FREQ=" + freq.name());
        if (interval > 1) sj.add("INTERVAL=" + interval);
        if (count != null) sj.add("COUNT=" + count);
        if (until != null) sj.add("UNTIL=" + UNTIL_FORMAT.format(until));
        if (!byDay.isEmpty()) {
            StringJoiner days = new StringJoiner(",");
            byDay.stream().sorted().forEach(d -> days.add(DAY_REVERSE.get(d)));
            sj.add("BYDAY=" + days);
        }
        return sj.toString();
    }
}
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api -Dtest=RecurrenceRuleTest`
Expected: all 9 tests pass

- [ ] **Step 5: Commit**

```
feat(mindmap-api): RecurrenceRule record with RFC 5545 RRULE subset

Supports FREQ, INTERVAL, COUNT, UNTIL, BYDAY. parse() + toString()
round-trip. Minimal subset for cognitive event recurrence.

Refs #241
```

### Task 4: RecurrenceGenerator static utility

**Files:**
- Create: `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/RecurrenceGenerator.java`
- Create: `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/RecurrenceGeneratorTest.java`

**Interfaces:**
- Consumes: `RecurrenceRule` from mindmap-api, `MindMapNode` from mindmap-api, `NodeInput` from mindmap-api
- Produces: `RecurrenceGenerator.generateInstances(MindMapNode template, RecurrenceRule rule, Instant horizon)` → `List<NodeInput>`

- [ ] **Step 1: Write failing tests**

Create `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/RecurrenceGeneratorTest.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.*;
import io.casehub.neocortex.mindmap.inmem.InMemoryMindMapStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.DayOfWeek;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

class RecurrenceGeneratorTest {

    private InMemoryMindMapStore store;
    private String subgraphId;

    @BeforeEach
    void setUp() {
        store = new InMemoryMindMapStore();
        subgraphId = store.createSubgraph(
            new SubgraphInput("Test", SubgraphType.GENERAL, null), "t1");
    }

    @Test
    void dailyRecurrence_generatesCorrectCount() {
        Instant start = Instant.parse("2026-09-01T09:00:00Z");
        String templateId = store.addNode(new NodeInput("Standup", subgraphId,
            null, "test", null, null,
            start, null, null, null, null,
            Map.of("rrule", "FREQ=DAILY;COUNT=3", "eventKind", "scheduled")), "t1");
        MindMapNode template = store.getNode(templateId, "t1");

        RecurrenceRule rule = RecurrenceRule.parse("FREQ=DAILY;COUNT=3");
        Instant horizon = start.plus(30, ChronoUnit.DAYS);

        List<NodeInput> instances = RecurrenceGenerator.generateInstances(template, rule, horizon);
        assertThat(instances).hasSize(3);
        assertThat(instances.get(0).validFrom()).isEqualTo(start.plus(1, ChronoUnit.DAYS));
        assertThat(instances.get(1).validFrom()).isEqualTo(start.plus(2, ChronoUnit.DAYS));
        assertThat(instances.get(2).validFrom()).isEqualTo(start.plus(3, ChronoUnit.DAYS));
    }

    @Test
    void instances_inheritTemplateProperties_exceptRrule() {
        Instant start = Instant.parse("2026-09-01T09:00:00Z");
        String templateId = store.addNode(new NodeInput("Meeting", subgraphId,
            null, "test", null, null,
            start, null, null, null, null,
            Map.of("rrule", "FREQ=DAILY;COUNT=1", "eventKind", "scheduled")), "t1");
        MindMapNode template = store.getNode(templateId, "t1");

        RecurrenceRule rule = RecurrenceRule.parse("FREQ=DAILY;COUNT=1");
        List<NodeInput> instances = RecurrenceGenerator.generateInstances(
            template, rule, start.plus(7, ChronoUnit.DAYS));

        NodeInput instance = instances.get(0);
        assertThat(instance.name()).isEqualTo("Meeting");
        assertThat(instance.subgraphId()).isEqualTo(subgraphId);
        assertThat(instance.properties()).containsEntry("eventKind", "scheduled");
        assertThat(instance.properties()).doesNotContainKey("rrule");
        assertThat(instance.properties()).containsEntry("template-node-id", templateId);
        assertThat(instance.properties()).containsEntry("recurrence-index", "0");
        assertThat(instance.properties()).containsEntry("status", "planned");
    }

    @Test
    void horizonLimitsGeneration() {
        Instant start = Instant.parse("2026-09-01T09:00:00Z");
        String templateId = store.addNode(new NodeInput("Daily", subgraphId,
            null, "test", null, null,
            start, null, null, null, null,
            Map.of("rrule", "FREQ=DAILY")), "t1");
        MindMapNode template = store.getNode(templateId, "t1");

        RecurrenceRule rule = RecurrenceRule.parse("FREQ=DAILY");
        List<NodeInput> instances = RecurrenceGenerator.generateInstances(
            template, rule, start.plus(3, ChronoUnit.DAYS));

        assertThat(instances).hasSize(3);
    }

    @Test
    void weeklyWithInterval() {
        Instant start = Instant.parse("2026-09-01T09:00:00Z");
        String templateId = store.addNode(new NodeInput("Biweekly", subgraphId,
            null, "test", null, null,
            start, null, null, null, null, Map.of()), "t1");
        MindMapNode template = store.getNode(templateId, "t1");

        RecurrenceRule rule = RecurrenceRule.parse("FREQ=WEEKLY;INTERVAL=2;COUNT=2");
        List<NodeInput> instances = RecurrenceGenerator.generateInstances(
            template, rule, start.plus(60, ChronoUnit.DAYS));

        assertThat(instances).hasSize(2);
        assertThat(instances.get(0).validFrom()).isEqualTo(start.plus(14, ChronoUnit.DAYS));
        assertThat(instances.get(1).validFrom()).isEqualTo(start.plus(28, ChronoUnit.DAYS));
    }

    @Test
    void emptyResult_whenTemplateHasNoValidFrom() {
        String templateId = store.addNode(new NodeInput("NoTime", subgraphId,
            null, "test", null, null,
            null, null, null, null, null, Map.of()), "t1");
        MindMapNode template = store.getNode(templateId, "t1");

        RecurrenceRule rule = RecurrenceRule.parse("FREQ=DAILY;COUNT=5");
        List<NodeInput> instances = RecurrenceGenerator.generateInstances(
            template, rule, Instant.now().plus(30, ChronoUnit.DAYS));

        assertThat(instances).isEmpty();
    }
}
```

- [ ] **Step 2: Run tests — verify compilation failure**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-intelligence -Dtest=RecurrenceGeneratorTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: compilation failure

- [ ] **Step 3: Implement RecurrenceGenerator**

Create `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/RecurrenceGenerator.java`:

```java
package io.casehub.neocortex.mindmap.intelligence;

import io.casehub.neocortex.mindmap.MindMapNode;
import io.casehub.neocortex.mindmap.NodeInput;
import io.casehub.neocortex.mindmap.RecurrenceRule;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.ZonedDateTime;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

public final class RecurrenceGenerator {

    private RecurrenceGenerator() {}

    public static List<NodeInput> generateInstances(MindMapNode template,
                                                     RecurrenceRule rule,
                                                     Instant horizon) {
        if (template.validFrom() == null) return List.of();

        List<NodeInput> instances = new ArrayList<>();
        ZonedDateTime cursor = template.validFrom().atZone(ZoneOffset.UTC);
        int generated = 0;

        while (true) {
            cursor = advance(cursor, rule);
            Instant candidateInstant = cursor.toInstant();

            if (candidateInstant.isAfter(horizon)) break;
            if (rule.until() != null && candidateInstant.isAfter(rule.until())) break;
            if (rule.count() != null && generated >= rule.count()) break;

            Map<String, String> props = new HashMap<>(template.properties());
            props.remove("rrule");
            props.put("template-node-id", template.id());
            props.put("recurrence-index", String.valueOf(generated));
            props.putIfAbsent("status", "planned");

            instances.add(new NodeInput(
                template.name(), template.subgraphId(),
                template.confidence(), template.provenance(),
                template.traits(), template.refs(),
                candidateInstant, template.validUntil(),
                template.pleasure(), template.arousal(), template.dominance(),
                props));

            generated++;
        }

        return List.copyOf(instances);
    }

    private static ZonedDateTime advance(ZonedDateTime from, RecurrenceRule rule) {
        return switch (rule.freq()) {
            case DAILY -> from.plusDays(rule.interval());
            case WEEKLY -> from.plusWeeks(rule.interval());
            case MONTHLY -> from.plusMonths(rule.interval());
            case YEARLY -> from.plusYears(rule.interval());
        };
    }
}
```

- [ ] **Step 4: Run tests — verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl mindmap-api,mindmap-intelligence -Dtest=RecurrenceGeneratorTest`
Expected: all 5 tests pass

- [ ] **Step 5: Full build verification**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests=false`
Expected: BUILD SUCCESS — all existing tests pass, all new tests pass

- [ ] **Step 6: Commit**

```
feat(mindmap-intelligence): RecurrenceGenerator — template → instance expansion

Static utility producing NodeInput instances from a template node +
RecurrenceRule + time horizon. Instances inherit template properties,
carry template-node-id and recurrence-index.

Refs #241
```

---

## Batch 3: Documentation

### Task 5: Update roadmap + consumer guide + CLAUDE.md

**Files:**
- Modify: `docs/guides/cognitive-architecture-roadmap.md` — mark §3c DONE
- Modify: `docs/guides/consumer-guide.md` — add event trait property convention and lifecycle status values
- Modify: `CLAUDE.md` — update mindmap-intelligence module description

**Interfaces:**
- None — documentation only

- [ ] **Step 1: Mark roadmap §3c DONE**

In `docs/guides/cognitive-architecture-roadmap.md`, update the `### 3c: Prospective Event Model` heading to include `— **DONE** (#241)` and add a summary paragraph describing the implementation.

- [ ] **Step 2: Update consumer guide with event property conventions**

In `docs/guides/consumer-guide.md`, add a section documenting:
- Event trait properties (`eventKind`, `eventValence`) and their values
- Lifecycle status values and the convention (not enforced)
- RecurrenceRule property key (`rrule`) and parse/toString usage
- AffectType distinction (inherent vs anticipatory)

- [ ] **Step 3: Update CLAUDE.md module descriptions**

Update `CLAUDE.md` to reflect:
- `cognitive-api` gains `AffectType` enum
- `mindmap-api` gains `RecurrenceRule` record
- `mindmap-intelligence` gains 4 TraitRule implementations, `Eventlike` interface, `RecurrenceGenerator`
- `memory-api` gains `AffectEvents` 6-arg overload

- [ ] **Step 4: Commit**

```
docs: mark roadmap §3c DONE, update guides for event model

Refs #241
```

## References

- `specs/issue-253-cognitive-rearchitecture/2026-08-31-prospective-event-model-design.md` — design spec
- `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/TraitRule.java` — SPI
- `mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/PersonableTraitRule.java` — pattern
- `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/StandardTraitRulesTest.java` — test pattern
- `mindmap-intelligence/src/test/java/io/casehub/neocortex/mindmap/intelligence/TraitProxyTest.java` — trait proxy test pattern
- `memory-api/src/main/java/io/casehub/neocortex/memory/mood/AffectEvents.java` — converter
- `memory-api/src/test/java/io/casehub/neocortex/memory/mood/AffectEventsTest.java` — converter test pattern
- `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/ConfidenceOrigin.java` — parallel enum pattern
- Decisions D19-D26
- GitHub #241
