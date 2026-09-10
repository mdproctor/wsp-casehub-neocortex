# Temporal Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #234 — Temporal taxonomy — TemporalMark sealed hierarchy
**Issue group:** #253, #234

**Goal:** Define a `TemporalMark` sealed interface in `cognitive-api` that unifies wall-clock, relative, and ordinal time references with a common `resolveToInstant()` method.

**Architecture:** Single sealed interface with 3 inner records (`WallClock`, `Relative`, `Ordinal`) and static factory methods. Lives in `cognitive-api` alongside `Confidence`. Zero dependencies. Each variant implements `resolveToInstant(Instant now)` for sorting and proximity computation.

**Tech Stack:** Java 21 sealed interfaces, JUnit 5, AssertJ

## Global Constraints

- Java 21 language features (sealed interfaces, records, pattern matching)
- Zero external dependencies — `cognitive-api` is tier-0 pure Java
- Follow existing `cognitive-api` conventions (see `ConfidenceTest.java` for test style)
- Build with `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn` and `mvn` not `./mvnw`

---

## Batch 1: TemporalMark type + tests

### Task 1: TemporalMark sealed interface with 3 variants

**Files:**
- Create: `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/TemporalMark.java`
- Create: `cognitive-api/src/test/java/io/casehub/neocortex/cognitive/TemporalMarkTest.java`

**Interfaces:**
- Consumes: nothing — standalone type
- Produces: `TemporalMark` sealed interface with `resolveToInstant(Instant now)`, inner records `WallClock(Instant instant)`, `Relative(Duration offset, Instant anchor)`, `Ordinal(String turnId, Instant resolved)`, static factories `wallClock(Instant)`, `relativeToNow(Duration)`, `relativeToAnchor(Duration, Instant)`, `ordinal(String, Instant)`

- [ ] **Step 1: Write failing tests for WallClock**

```java
package io.casehub.neocortex.cognitive;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;

class TemporalMarkTest {

    private static final Instant NOW = Instant.parse("2026-08-30T12:00:00Z");
    private static final Instant MEETING = Instant.parse("2026-12-25T15:00:00Z");

    @Test
    void wallClock_resolvesToWrappedInstant() {
        var mark = TemporalMark.wallClock(MEETING);
        assertThat(mark.resolveToInstant(NOW)).isEqualTo(MEETING);
    }

    @Test
    void wallClock_ignoresNow() {
        var mark = TemporalMark.wallClock(MEETING);
        var differentNow = Instant.parse("2099-01-01T00:00:00Z");
        assertThat(mark.resolveToInstant(differentNow)).isEqualTo(MEETING);
    }

    @Test
    void wallClock_nullInstantThrows() {
        assertThatNullPointerException()
                .isThrownBy(() -> TemporalMark.wallClock(null));
    }

    @Test
    void wallClock_recordAccessor() {
        var mark = (TemporalMark.WallClock) TemporalMark.wallClock(MEETING);
        assertThat(mark.instant()).isEqualTo(MEETING);
    }
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -o 2>&1 | grep -E '(Tests run|BUILD|ERROR)' | tail -5`
Expected: Compilation failure — `TemporalMark` does not exist

- [ ] **Step 3: Implement TemporalMark with WallClock only**

Create `cognitive-api/src/main/java/io/casehub/neocortex/cognitive/TemporalMark.java`:

```java
package io.casehub.neocortex.cognitive;

import java.time.Duration;
import java.time.Instant;
import java.util.Objects;

public sealed interface TemporalMark {

    Instant resolveToInstant(Instant now);

    record WallClock(Instant instant) implements TemporalMark {
        public WallClock {
            Objects.requireNonNull(instant, "instant required");
        }

        @Override
        public Instant resolveToInstant(Instant now) {
            return instant;
        }
    }

    record Relative(Duration offset, Instant anchor) implements TemporalMark {
        public Relative {
            Objects.requireNonNull(offset, "offset required");
        }

        @Override
        public Instant resolveToInstant(Instant now) {
            Instant base = anchor != null ? anchor : now;
            return base.plus(offset);
        }
    }

    record Ordinal(String turnId, Instant resolved) implements TemporalMark {
        public Ordinal {
            Objects.requireNonNull(turnId, "turnId required");
            Objects.requireNonNull(resolved, "resolved required");
        }

        @Override
        public Instant resolveToInstant(Instant now) {
            return resolved;
        }
    }

    static TemporalMark wallClock(Instant instant) {
        return new WallClock(instant);
    }

    static TemporalMark relativeToNow(Duration offset) {
        return new Relative(offset, null);
    }

    static TemporalMark relativeToAnchor(Duration offset, Instant anchor) {
        return new Relative(offset, Objects.requireNonNull(anchor, "anchor required"));
    }

    static TemporalMark ordinal(String turnId, Instant resolved) {
        return new Ordinal(turnId, resolved);
    }
}
```

- [ ] **Step 4: Run WallClock tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -o 2>&1 | grep -E '(Tests run|BUILD|ERROR)' | tail -5`
Expected: PASS

- [ ] **Step 5: Add Relative tests**

Append to `TemporalMarkTest.java`:

```java
@Test
void relative_nullAnchor_resolvesFromNow() {
    var mark = TemporalMark.relativeToNow(Duration.ofDays(3));
    assertThat(mark.resolveToInstant(NOW)).isEqualTo(NOW.plus(Duration.ofDays(3)));
}

@Test
void relative_withAnchor_resolvesFromAnchor() {
    var mark = TemporalMark.relativeToAnchor(Duration.ofDays(3), MEETING);
    assertThat(mark.resolveToInstant(NOW)).isEqualTo(MEETING.plus(Duration.ofDays(3)));
}

@Test
void relative_negativeOffset_pastReference() {
    var mark = TemporalMark.relativeToNow(Duration.ofDays(-7));
    assertThat(mark.resolveToInstant(NOW)).isEqualTo(NOW.minus(Duration.ofDays(7)));
}

@Test
void relative_nullAnchor_differentNowProducesDifferentResult() {
    var mark = TemporalMark.relativeToNow(Duration.ofHours(1));
    var now1 = Instant.parse("2026-08-30T10:00:00Z");
    var now2 = Instant.parse("2026-08-30T14:00:00Z");
    assertThat(mark.resolveToInstant(now1)).isNotEqualTo(mark.resolveToInstant(now2));
}

@Test
void relative_nullOffsetThrows() {
    assertThatNullPointerException()
            .isThrownBy(() -> TemporalMark.relativeToNow(null));
}

@Test
void relative_relativeToAnchor_nullAnchorThrows() {
    assertThatNullPointerException()
            .isThrownBy(() -> TemporalMark.relativeToAnchor(Duration.ofDays(1), null));
}

@Test
void relative_recordAccessors() {
    var mark = (TemporalMark.Relative) TemporalMark.relativeToAnchor(Duration.ofDays(3), MEETING);
    assertThat(mark.offset()).isEqualTo(Duration.ofDays(3));
    assertThat(mark.anchor()).isEqualTo(MEETING);
}

@Test
void relative_nullAnchorAccessor() {
    var mark = (TemporalMark.Relative) TemporalMark.relativeToNow(Duration.ofDays(1));
    assertThat(mark.anchor()).isNull();
}
```

- [ ] **Step 6: Run all tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -o 2>&1 | grep -E '(Tests run|BUILD|ERROR)' | tail -5`
Expected: PASS

- [ ] **Step 7: Add Ordinal tests**

Append to `TemporalMarkTest.java`:

```java
@Test
void ordinal_resolvesToPreResolvedInstant() {
    var mark = TemporalMark.ordinal("turn-42", MEETING);
    assertThat(mark.resolveToInstant(NOW)).isEqualTo(MEETING);
}

@Test
void ordinal_ignoresNow() {
    var mark = TemporalMark.ordinal("turn-42", MEETING);
    var differentNow = Instant.parse("2099-01-01T00:00:00Z");
    assertThat(mark.resolveToInstant(differentNow)).isEqualTo(MEETING);
}

@Test
void ordinal_nullTurnIdThrows() {
    assertThatNullPointerException()
            .isThrownBy(() -> TemporalMark.ordinal(null, MEETING));
}

@Test
void ordinal_nullResolvedThrows() {
    assertThatNullPointerException()
            .isThrownBy(() -> TemporalMark.ordinal("turn-1", null));
}

@Test
void ordinal_recordAccessors() {
    var mark = (TemporalMark.Ordinal) TemporalMark.ordinal("turn-42", MEETING);
    assertThat(mark.turnId()).isEqualTo("turn-42");
    assertThat(mark.resolved()).isEqualTo(MEETING);
}
```

- [ ] **Step 8: Run all tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -o 2>&1 | grep -E '(Tests run|BUILD|ERROR)' | tail -5`
Expected: PASS

- [ ] **Step 9: Add pattern matching and equality tests**

Append to `TemporalMarkTest.java`:

```java
@Test
void patternMatching_exhaustive() {
    TemporalMark mark = TemporalMark.wallClock(NOW);
    String result = switch (mark) {
        case TemporalMark.WallClock wc -> "wall:" + wc.instant();
        case TemporalMark.Relative rel -> "rel:" + rel.offset();
        case TemporalMark.Ordinal ord -> "ord:" + ord.turnId();
    };
    assertThat(result).startsWith("wall:");
}

@Test
void equality_sameWallClockEqual() {
    assertThat(TemporalMark.wallClock(MEETING))
            .isEqualTo(TemporalMark.wallClock(MEETING));
}

@Test
void equality_sameRelativeEqual() {
    assertThat(TemporalMark.relativeToAnchor(Duration.ofDays(1), MEETING))
            .isEqualTo(TemporalMark.relativeToAnchor(Duration.ofDays(1), MEETING));
}

@Test
void equality_sameOrdinalEqual() {
    assertThat(TemporalMark.ordinal("t1", MEETING))
            .isEqualTo(TemporalMark.ordinal("t1", MEETING));
}

@Test
void equality_differentVariantsNotEqual() {
    assertThat(TemporalMark.wallClock(MEETING))
            .isNotEqualTo(TemporalMark.ordinal("t1", MEETING));
}
```

- [ ] **Step 10: Run full test suite to verify everything passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognitive-api -o 2>&1 | grep -E '(Tests run|BUILD|ERROR)' | tail -5`
Expected: All tests PASS

- [ ] **Step 11: Run full project build to verify no regressions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn install -o -DskipTests 2>&1 | grep -E '(BUILD|ERROR)' | tail -5`
Expected: BUILD SUCCESS

- [ ] **Step 12: Update CLAUDE.md cognitive-api description**

Add `TemporalMark` to the cognitive-api module description in `CLAUDE.md`:

Change: `cognitive-api/      — zero deps: Confidence record, ConfidenceOrigin enum.`
To: `cognitive-api/      — zero deps: Confidence record, ConfidenceOrigin enum, TemporalMark sealed hierarchy (WallClock, Relative, Ordinal).`

- [ ] **Step 13: Update roadmap §2a**

Mark `### 2a: Temporal Taxonomy` as `— **DONE** (#234)` in `docs/guides/cognitive-architecture-roadmap.md`.

- [ ] **Step 14: Commit**

```bash
git add cognitive-api/src/main/java/io/casehub/neocortex/cognitive/TemporalMark.java \
       cognitive-api/src/test/java/io/casehub/neocortex/cognitive/TemporalMarkTest.java \
       CLAUDE.md docs/guides/cognitive-architecture-roadmap.md
git commit -m "feat(cognitive-api): TemporalMark sealed hierarchy — wall-clock, relative, ordinal time

Refs #234

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"
```

## References

- [2026-08-30-temporal-taxonomy-design.md] — design spec
- [cognitive-api/src/main/java/io/casehub/neocortex/cognitive/Confidence.java] — module location + conventions
- [cognitive-api/src/test/java/io/casehub/neocortex/cognitive/ConfidenceTest.java] — test conventions
- [cognitive-architecture-roadmap.md §2a] — roadmap design sketch
- [D8, D9, D10, D11] — design decisions
- [GitHub #234] — focal issue
