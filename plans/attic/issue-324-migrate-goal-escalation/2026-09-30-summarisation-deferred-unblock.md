# Summarisation & Deferred Classes Unblock Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** casehubio/blocks#303 — Migrate cognitive state from
blocks to neocortex

**Issue group:** casehubio/blocks#303, casehubio/blocks#298 (parent
epic)

**Goal:** Unblock the 6 deferred classes from the cognition migration by
creating `summarisation` as a single neocortex module (SPIs + engine +
CDI wiring), adding prerequisite types to `memory-api` and `mindmap-api`,
and moving all 6 classes to the `cognition` module.

**Architecture:** New `summarisation` module owns the entire event
summarisation framework — SPIs, records, engine, and CDI wiring — in one
module. No api/runtime split. This makes neocortex fully self-contained:
a cognitive LLM runs with only neocortex, no blocks on classpath. Blocks'
copy coexists temporarily; Batch 7 consolidates blocks onto neocortex's
module. `cognition` depends on `summarisation`. `NarrativePipeline`
receives `SummarisationPipelineFactory` via CDI — resolved by
`DefaultSummarisationPipelineFactory` in the same module.

**Renames from blocks originals:**
- `EventStreamBus` → `LevelEventBus`
- `EventAccumulator` → `LevelEventAccumulator`
- `Compactor` → `LevelEventCompactor`
- `KeyedAccumulator` → `KeyedLevelEventAccumulator` (when brought over)

**Tech Stack:** Java 21, Quarkus 3.32.2, CDI, Maven multi-module

## Global Constraints

- Pre-release platform — breaking changes are free
- Build with: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- All commits reference `casehubio/blocks#303`
- groupId: `io.casehub`, artifactId prefix: `casehub-neocortex-`
- Root package for summarisation: `io.casehub.neocortex.summarisation`
- `ide_move_file` cannot cross repo boundaries — create files in
  neocortex, read source from blocks
- IntelliJ workspace already open with both repos (use
  `project_path=/Users/mdproctor/claude/casehub/slots/203/neocortex`)
- Blocks source dir:
  `/Users/mdproctor/claude/casehub/slots/203/blocks/blocks-core/src/main/java/io/casehub/blocks/agentic/social/`
- Blocks summarisation dir:
  `/Users/mdproctor/claude/casehub/slots/203/blocks/summarisation-api/src/main/java/io/casehub/blocks/summarisation/`

---

## Batch 1: Summarisation Module + Prerequisite Types

### Task 1: Create summarisation module

Single module containing the full framework: SPIs, records, engine, and
`DefaultSummarisationPipelineFactory`. Everything stays together — no
api/runtime split. Blocks and cognition both depend on this module.

**Files:**
- Create: `summarisation/pom.xml`
- Create: 17 Java files in
  `summarisation/src/main/java/io/casehub/neocortex/summarisation/`
- Create: `DefaultSummarisationPipelineFactory.java`
- Modify: `pom.xml` (parent — add module)

**Interfaces:**
- Produces: Full summarisation framework — SPIs (`ContentSummariser`,
  `Summariser`, `StatefulSummariser`, `OutputProcessor`, `EmissionPolicy`,
  `LevelEventCompactor`, `StateStore`, `Tickable`, `SummarisationPipeline`,
  `SummarisationPipelineFactory`), records (`LevelEvent`, `EventLevel`,
  `WindowPolicy`), engine (`SummarisationRunner`, `LevelEventAccumulator`,
  `WindowPolicyEmission`), utility (`LevelEventBus`), and CDI wiring
  (`DefaultSummarisationPipelineFactory`). Neocortex is fully
  self-contained for cognitive summarisation.

**Rename:** `LevelEventBus` → `LevelEventBus` (makes the LevelEvent
coupling explicit — this is not a generic event bus).

- [ ] **Step 1: Create summarisation POM**

Create `summarisation/pom.xml`:

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
  </parent>
  <artifactId>casehub-neocortex-summarisation</artifactId>
  <name>CaseHub Neocortex - Summarisation</name>
  <description>Event summarisation framework — LevelEvent model, ContentSummariser/EmissionPolicy/OutputProcessor SPIs, SummarisationRunner engine, LevelEventBus, DefaultSummarisationPipelineFactory.</description>
  <dependencies>
    <dependency>
      <groupId>org.jspecify</groupId>
      <artifactId>jspecify</artifactId>
      <version>1.0.0</version>
    </dependency>
    <dependency>
      <groupId>jakarta.enterprise</groupId>
      <artifactId>jakarta.enterprise.cdi-api</artifactId>
      <scope>provided</scope>
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

- [ ] **Step 2: Add module to parent POM**

In `pom.xml` (neocortex root), add before `cognition-api` (line 76):

```xml
    <module>summarisation</module>
    <module>cognition-api</module>
```

- [ ] **Step 3: Create all files**

Create all files in
`summarisation/src/main/java/io/casehub/neocortex/summarisation/`.
Source from blocks' `summarisation-api` — change package to
`io.casehub.neocortex.summarisation`.

**SPIs and records** (copy with package change):

**LevelEvent.java:**
```java
package io.casehub.neocortex.summarisation;

import org.jspecify.annotations.Nullable;

public record LevelEvent<E>(E payload, long timestamp, EventLevel level, @Nullable String tenancyId) {}
```

**EventLevel.java:**
```java
package io.casehub.neocortex.summarisation;

public record EventLevel(String name, int ordinal) {}
```

**ContentSummariser.java:**
```java
package io.casehub.neocortex.summarisation;

import org.jspecify.annotations.Nullable;

import java.util.List;
import java.util.concurrent.CompletionStage;

@FunctionalInterface
public interface ContentSummariser<T, R> {

    CompletionStage<R> summarise(List<T> items, @Nullable R previous);

    default StatefulSummariser<T, R, R> asSummariser() {
        return (batch, prev) -> {
            var items = batch.stream().map(LevelEvent::payload).toList();
            return summarise(items, prev)
                .thenApply(out -> new StatefulSummariser.SummariseResult<>(List.of(out), out));
        };
    }
}
```

**Summariser.java:**
```java
package io.casehub.neocortex.summarisation;

import java.util.List;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;

@FunctionalInterface
public interface Summariser<IN, OUT> {
    CompletionStage<List<OUT>> summarise(List<LevelEvent<IN>> batch);

    static <IN, OUT> Summariser<IN, OUT> ofSync(SyncSummariser<IN, OUT> sync) {
        return batch -> CompletableFuture.completedFuture(sync.summarise(batch));
    }

    @FunctionalInterface
    interface SyncSummariser<IN, OUT> {
        List<OUT> summarise(List<LevelEvent<IN>> batch);
    }
}
```

**StatefulSummariser.java:**
```java
package io.casehub.neocortex.summarisation;

import org.jspecify.annotations.Nullable;

import java.util.List;
import java.util.concurrent.CompletionStage;

public interface StatefulSummariser<IN, OUT, S> extends Summariser<IN, OUT> {

    CompletionStage<SummariseResult<OUT, S>> summarise(
            List<LevelEvent<IN>> batch, @Nullable S previousState);

    @Override
    default CompletionStage<List<OUT>> summarise(List<LevelEvent<IN>> batch) {
        return summarise(batch, null).thenApply(SummariseResult::outputs);
    }

    record SummariseResult<OUT, S>(List<OUT> outputs, @Nullable S newState) {}
}
```

**OutputProcessor.java:**
```java
package io.casehub.neocortex.summarisation;

import org.jspecify.annotations.Nullable;

import java.util.List;

@FunctionalInterface
public interface OutputProcessor<OUT, S> {
    List<OUT> process(List<OUT> outputs, @Nullable S currentState);
}
```

**EmissionPolicy.java:**
```java
package io.casehub.neocortex.summarisation;

import org.jspecify.annotations.Nullable;

import java.util.List;

@FunctionalInterface
public interface EmissionPolicy<IN, S> {
    boolean shouldEmit(List<LevelEvent<IN>> buffered,
                       @Nullable S currentState,
                       long now);

    static <IN, S> EmissionPolicy<IN, S> anyOf(
            List<EmissionPolicy<IN, S>> policies) {
        return (buffered, state, now) ->
                policies.stream().anyMatch(p -> p.shouldEmit(buffered, state, now));
    }

    static <IN, S> EmissionPolicy<IN, S> allOf(
            List<EmissionPolicy<IN, S>> policies) {
        return (buffered, state, now) ->
                policies.stream().allMatch(p -> p.shouldEmit(buffered, state, now));
    }
}
```

**LevelEventCompactor.java:**
```java
package io.casehub.neocortex.summarisation;

import java.util.List;

@FunctionalInterface
public interface LevelEventCompactor<E> {
    List<LevelEvent<E>> compact(List<LevelEvent<E>> events);
}
```

**StateStore.java:**
```java
package io.casehub.neocortex.summarisation;

import org.jspecify.annotations.Nullable;

public interface StateStore<S> {
    @Nullable S load(String partitionKey);

    void store(String partitionKey, S state);
}
```

**Tickable.java:**
```java
package io.casehub.neocortex.summarisation;

import java.util.concurrent.CompletableFuture;
import java.util.concurrent.CompletionStage;

public interface Tickable {
    CompletionStage<Void> tick(long now);

    default CompletionStage<Void> flush() {
        return CompletableFuture.completedFuture(null);
    }
}
```

**WindowPolicy.java:**
```java
package io.casehub.neocortex.summarisation;

public record WindowPolicy(long maxAge, int maxCount) {
    public WindowPolicy {
        if (maxAge < 0) throw new IllegalArgumentException("maxAge must be >= 0, was: " + maxAge);
        if (maxCount < 0) throw new IllegalArgumentException("maxCount must be >= 0, was: " + maxCount);
        if (maxAge == 0 && maxCount == 0) throw new IllegalArgumentException("At least one of maxAge or maxCount must be positive");
    }

    public static WindowPolicy ofCount(int maxCount) {
        return new WindowPolicy(0, maxCount);
    }

    public static WindowPolicy ofAge(long maxAgeMs) {
        return new WindowPolicy(maxAgeMs, 0);
    }

    public static WindowPolicy of(long maxAgeMs, int maxCount) {
        return new WindowPolicy(maxAgeMs, maxCount);
    }
}
```

- [ ] **Step 4: Create new SPIs**

**SummarisationPipeline.java:**

```java
package io.casehub.neocortex.summarisation;

public interface SummarisationPipeline<IN> extends Tickable {
    void accept(LevelEvent<IN> event);
}
```

**SummarisationPipelineFactory.java:**

```java
package io.casehub.neocortex.summarisation;

import org.jspecify.annotations.Nullable;

public interface SummarisationPipelineFactory {

    <IN, OUT, S> SummarisationPipeline<IN> create(
            StatefulSummariser<IN, OUT, S> summariser,
            @Nullable OutputProcessor<OUT, S> outputProcessor,
            EmissionPolicy<IN, S> emissionPolicy,
            @Nullable StateStore<S> stateStore,
            String partitionKey,
            WindowPolicy windowPolicy);
}
```

- [ ] **Step 5: Create LevelEventBus**

Read blocks'
`summarisation-api/src/main/java/io/casehub/blocks/summarisation/LevelEventBus.java`
(47 LOC). Create as `LevelEventBus.java` in neocortex — rename class
from `LevelEventBus` to `LevelEventBus`, change package. The class is
a CopyOnWriteArrayList-based pub/sub typed to `LevelEvent<E>`.

- [ ] **Step 6: Copy engine classes from blocks**

Read each file from
`blocks/summarisation-api/src/main/java/io/casehub/blocks/summarisation/`.
Create in `summarisation/src/main/java/io/casehub/neocortex/summarisation/`
with package change:

- `SummarisationRunner.java` (300 LOC — builder + tick engine)
- `LevelEventAccumulator.java` (59 LOC — synchronized buffer with drain)
- `WindowPolicyEmission.java` (27 LOC — package-private EmissionPolicy impl)

`SummarisationRunner` must implement `SummarisationPipeline<IN>`. Verify
the builder API when reading blocks' source. If it doesn't already
implement these interfaces, add `implements SummarisationPipeline<IN>`
and wire the existing `tick()` and event acceptance methods.

- [ ] **Step 7: Create DefaultSummarisationPipelineFactory**

Create `summarisation/src/main/java/io/casehub/neocortex/summarisation/DefaultSummarisationPipelineFactory.java`:

```java
package io.casehub.neocortex.summarisation;

import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;
import org.jspecify.annotations.Nullable;

@ApplicationScoped
@DefaultBean
public class DefaultSummarisationPipelineFactory implements SummarisationPipelineFactory {

    @Override
    public <IN, OUT, S> SummarisationPipeline<IN> create(
            StatefulSummariser<IN, OUT, S> summariser,
            @Nullable OutputProcessor<OUT, S> outputProcessor,
            EmissionPolicy<IN, S> emissionPolicy,
            @Nullable StateStore<S> stateStore,
            String partitionKey,
            WindowPolicy windowPolicy) {

        var runner = SummarisationRunner.<IN, OUT, S>builder()
                .summariser(summariser)
                .emissionPolicy(emissionPolicy)
                .windowPolicy(windowPolicy)
                .partitionKey(partitionKey);

        if (outputProcessor != null) {
            runner.outputProcessor(outputProcessor);
        }
        if (stateStore != null) {
            runner.stateStore(stateStore);
        }

        return runner.build();
    }
}
```

- [ ] **Step 8: Build**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl summarisation -DskipTests
```

Expected: BUILD SUCCESS.

- [ ] **Step 9: Copy all tests from blocks**

Read all test files from
`blocks/summarisation-api/src/test/java/io/casehub/blocks/summarisation/`.
Copy to `summarisation/src/test/java/io/casehub/neocortex/summarisation/`,
changing package declarations and renaming `LevelEventBusTest` →
`LevelEventBusTest`. All 18 test files, 132 tests.

Add a test for `DefaultSummarisationPipelineFactory`:

```java
package io.casehub.neocortex.summarisation;

import org.junit.jupiter.api.Test;
import java.util.concurrent.CompletableFuture;
import static org.assertj.core.api.Assertions.assertThat;

class DefaultSummarisationPipelineFactoryTest {

    @Test
    void createReturnsFunctionalPipeline() {
        var factory = new DefaultSummarisationPipelineFactory();
        StatefulSummariser<String, String, Void> summariser =
                (batch, prev) -> CompletableFuture.completedFuture(
                        new StatefulSummariser.SummariseResult<>(
                                batch.stream().map(LevelEvent::payload).toList(), null));

        var pipeline = factory.create(
                summariser, null,
                (buffered, state, now) -> buffered.size() >= 2,
                null, "test", WindowPolicy.ofCount(10));

        pipeline.accept(new LevelEvent<>("a", 1L, new EventLevel("test", 0), null));
        pipeline.accept(new LevelEvent<>("b", 2L, new EventLevel("test", 0), null));
        var result = pipeline.tick(3L);
        assertThat(result).isNotNull();
    }
}
```

- [ ] **Step 10: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl summarisation
```

Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add summarisation/ pom.xml
git commit -m "feat(#303): create summarisation runtime module

SummarisationRunner engine, LevelEventAccumulator,
DefaultSummarisationPipelineFactory. Neocortex is fully self-contained
for cognitive summarisation — no blocks dependency at runtime.

Refs casehubio/blocks#303"
```

### Task 2: Add prerequisite types to memory-api, cognition-api, and mindmap-api

**Files:**
- Create: `memory-api/.../memory/KnowledgeGapSummary.java`
- Create: `memory-api/.../memory/ReflectionEntry.java`
- Create: `memory-api/.../memory/ReflectionQueryStore.java`
- Modify: `cognition-api/.../cognition/memory/MemoryHygieneOrchestrator.java`
- Create: `mindmap-api/.../mindmap/ConsolidationArtifact.java`
- Modify: `mindmap-intelligence/.../consolidation/ConsolidationCompleted.java`
- Modify: `cognition/pom.xml` (add summarisation dependency)

**Interfaces:**
- Consumes: summarisation (Task 1)
- Produces: Types needed by the 6 deferred classes

Note: ReflectionEntry, ReflectionQueryStore, and KnowledgeGapSummary go
in `memory-api` (not cognition-api) so blocks can use them without
pulling in cognition-api's heavy dependency chain. memory-api is a leaf
module blocks already depends on, and it already owns the reflection
domain (ReflectionSynthesizer, ReflectionEvent, ReflectionQuery).

- [ ] **Step 1: Create KnowledgeGapSummary**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/KnowledgeGapSummary.java`:

```java
package io.casehub.neocortex.memory;

public record KnowledgeGapSummary(
        int lowRetentionCount,
        int consolidationGroupCount,
        double averageRetentionScore) {}
```

Read blocks'
`blocks-core/.../blocks/memory/KnowledgeGapSummary.java` to verify
fields match exactly.

- [ ] **Step 2: Extend MemoryHygieneOrchestrator**

Modify `cognition-api/src/main/java/io/casehub/neocortex/cognition/memory/MemoryHygieneOrchestrator.java`:

```java
package io.casehub.neocortex.cognition.memory;

import io.casehub.neocortex.memory.KnowledgeGapSummary;
import org.jspecify.annotations.Nullable;

public interface MemoryHygieneOrchestrator {
    void tick(String agentId, String tenantId);

    @Nullable KnowledgeGapSummary knowledgeGaps(String agentId, String tenantId);
}
```

Read blocks' `MemoryHygieneOrchestrator` to verify the `knowledgeGaps`
signature matches what `CuriosityDrive` calls.

- [ ] **Step 3: Create ReflectionEntry**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/ReflectionEntry.java`:

Read blocks'
`blocks-core/.../blocks/memory/ReflectionEntry.java` (16 LOC record).
Recreate with package `io.casehub.neocortex.memory`.

- [ ] **Step 4: Create ReflectionQueryStore**

Create `memory-api/src/main/java/io/casehub/neocortex/memory/ReflectionQueryStore.java`:

Read blocks'
`blocks-core/.../blocks/memory/ReflectionQueryStore.java` (14 LOC
interface). Recreate with package
`io.casehub.neocortex.memory`. Update `ReflectionEntry`
import to `io.casehub.neocortex.memory.ReflectionEntry`.

- [ ] **Step 5: Create ConsolidationArtifact**

Create `mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ConsolidationArtifact.java`:

Read from slot 196 branch:
```bash
git -C /Users/mdproctor/claude/casehub/slots/196/neocortex show issue-312-consolidation-artifacts:mindmap-api/src/main/java/io/casehub/neocortex/mindmap/ConsolidationArtifact.java
```

Recreate identically (28 LOC sealed interface with 5 record variants:
`GraduatedExperience`, `MergePerformed`, `MergeFlagged`,
`CuriosityQuestion`, `CommunitySummaryCreated`).

- [ ] **Step 6: Update ConsolidationCompleted**

Modify `mindmap-intelligence/.../consolidation/ConsolidationCompleted.java`:

```java
package io.casehub.neocortex.mindmap.intelligence.consolidation;

import io.casehub.neocortex.mindmap.ConsolidationArtifact;

import java.util.List;

public record ConsolidationCompleted(
        String tenantId,
        List<PhaseResult> phaseResults,
        List<ConsolidationArtifact> artifacts) {}
```

- [ ] **Step 7: Add summarisation dependency to cognition POM**

Add to `cognition/pom.xml`, after `cognition-api`:

```xml
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-summarisation</artifactId>
    </dependency>
```

This gives cognition the full engine (transitive access to
summarisation). `DefaultSummarisationPipelineFactory` is discovered
by CDI — NarrativePipeline gets a real pipeline, not a no-op.

- [ ] **Step 8: Build to verify**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests
```

Expected: BUILD SUCCESS. ConsolidationCompleted's new field may break
callers — find and fix with `ide_find_references`:

```
ide_find_references(file="mindmap-intelligence/.../ConsolidationCompleted.java",
                    line=<record line>,
                    project_path="/Users/mdproctor/claude/casehub/slots/203/neocortex")
```

Update all callers to pass `List.of()` for the new `artifacts` field.

- [ ] **Step 9: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition-api,cognition,mindmap-api,mindmap-intelligence,mindmap,mindmap-inmem,mindmap-sqlite,mindmap-testing
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add cognition-api/ mindmap-api/ mindmap-intelligence/ cognition/pom.xml
git commit -m "feat(#303): add prerequisite types for deferred class migration

KnowledgeGapSummary, ReflectionEntry, ReflectionQueryStore in memory-api.
ConsolidationArtifact in mindmap-api. MemoryHygieneOrchestrator extended
with knowledgeGaps(). ConsolidationCompleted carries artifacts.

Refs casehubio/blocks#303"
```

---

## Batch 2: Move CuriosityDrive, ConsolidationMediator, InnerLifeOrchestrator

### Task 3: Move CuriosityDrive and ConsolidationMediator

**Files:**
- Create: `cognition/.../cognition/drive/CuriosityDrive.java`
- Create: `cognition/.../cognition/drive/CuriosityDriveTest.java`
- Create: `cognition/.../cognition/core/ConsolidationMediator.java`
- Create: `cognition/.../cognition/core/ConsolidationMediatorTest.java`

**Interfaces:**
- Consumes: `MemoryHygieneOrchestrator.knowledgeGaps()`,
  `KnowledgeGapSummary` (memory-api, Task 2),
  `ConsolidationArtifact` (mindmap-api, Task 2),
  `ConsolidationCompleted` (mindmap-intelligence, Task 2)
- Produces: `CuriosityDrive` (`DriveSource` impl),
  `ConsolidationMediator` (CDI observer)

- [ ] **Step 1: Write CuriosityDrive test**

Read blocks' test:
`blocks-core/src/test/java/io/casehub/blocks/agentic/social/drive/CuriosityDriveTest.java`

Create `cognition/src/test/java/io/casehub/neocortex/cognition/drive/CuriosityDriveTest.java`.
Adapt: change package, update imports to neocortex types
(`KnowledgeGapSummary` from memory-api, `MemoryHygieneOrchestrator` from cognition-api,
`DriveSource`/`DriveIntensity` from cognition-api drive package).

- [ ] **Step 2: Run test — verify failure**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CuriosityDriveTest
```

Expected: compilation failure (class not found).

- [ ] **Step 3: Create CuriosityDrive**

Read blocks'
`blocks-core/.../agentic/social/drive/CuriosityDrive.java` (38 LOC).
Create `cognition/src/main/java/io/casehub/neocortex/cognition/drive/CuriosityDrive.java`.

Changes from blocks:
- Package: `io.casehub.neocortex.cognition.drive`
- `KnowledgeGapSummary` import →
  `io.casehub.neocortex.cognition.memory.KnowledgeGapSummary`
- `MemoryHygieneOrchestrator` import →
  `io.casehub.neocortex.cognition.memory.MemoryHygieneOrchestrator`
- All other `DriveSource`/`DriveIntensity`/`DriveAxis` imports →
  cognition-api drive package (already there from Batch 2)

- [ ] **Step 4: Run test — verify pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=CuriosityDriveTest
```

Expected: PASS.

- [ ] **Step 5: Write ConsolidationMediator test**

Read blocks' test:
`blocks-core/src/test/java/io/casehub/blocks/agentic/social/ConsolidationMediatorTest.java`
(8 tests, 110 LOC).

Create `cognition/src/test/java/io/casehub/neocortex/cognition/core/ConsolidationMediatorTest.java`.
Adapt: change package, update `ConsolidationArtifact` import to
`io.casehub.neocortex.mindmap.ConsolidationArtifact`,
`ConsolidationCompleted` to
`io.casehub.neocortex.mindmap.intelligence.consolidation.ConsolidationCompleted`.

- [ ] **Step 6: Create ConsolidationMediator**

Read blocks'
`blocks-core/.../agentic/social/ConsolidationMediator.java` (52 LOC).
Create `cognition/src/main/java/io/casehub/neocortex/cognition/core/ConsolidationMediator.java`.

Changes from blocks:
- Package: `io.casehub.neocortex.cognition.core`
- `ConsolidationArtifact` import →
  `io.casehub.neocortex.mindmap.ConsolidationArtifact`
- `ConsolidationCompleted` import →
  `io.casehub.neocortex.mindmap.intelligence.consolidation.ConsolidationCompleted`
- CDI observer `@Observes ConsolidationCompleted` — verify CDI event
  wiring compiles

- [ ] **Step 7: Run test — verify pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=ConsolidationMediatorTest
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add cognition/
git commit -m "feat(#303): move CuriosityDrive and ConsolidationMediator to cognition

CuriosityDrive computes curiosity intensity from knowledge gap stats.
ConsolidationMediator buffers ConsolidationArtifact events per agent.

Refs casehubio/blocks#303"
```

### Task 4: Move InnerLifeOrchestrator

**Files:**
- Create: `cognition/.../cognition/innerlife/InnerLifeOrchestrator.java`
- Create: `cognition/.../cognition/innerlife/InnerLifeOrchestratorTest.java`

**Interfaces:**
- Consumes: `LevelEvent` (summarisation),
  `AgentProvider` (platform-agent-api), `InnerLifeConfig`,
  `MotivationAssessment`, `ContentQualityGate`, `CivilityConstraint`
  (all cognition-api), `CaseMemoryStore` (memory-api),
  `MoodState` (memory-api), `ReflectionRetrievalOrchestrator`
  (cognition-api)
- Produces: `InnerLifeOrchestrator` CDI bean

- [ ] **Step 1: Write InnerLifeOrchestrator test**

Read blocks' test:
`blocks-core/src/test/java/io/casehub/blocks/agentic/social/InnerLifeOrchestratorTest.java`
(8 tests, 189 LOC).

Create `cognition/src/test/java/io/casehub/neocortex/cognition/innerlife/InnerLifeOrchestratorTest.java`.
Adapt:
- Package: `io.casehub.neocortex.cognition.innerlife`
- `LevelEvent` → `io.casehub.neocortex.summarisation.LevelEvent`
- `StructuredAgentInvoker` → replace with `AgentProvider` mock
- `KeyedLock` → removed (inline logic)
- `InnerLifeConfig` etc → cognition-api imports

- [ ] **Step 2: Run test — verify failure**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=InnerLifeOrchestratorTest
```

Expected: compilation failure.

- [ ] **Step 3: Create InnerLifeOrchestrator**

Read blocks'
`blocks-core/.../agentic/social/InnerLifeOrchestrator.java` (293 LOC).
Create `cognition/src/main/java/io/casehub/neocortex/cognition/innerlife/InnerLifeOrchestrator.java`.

Changes from blocks:
- Package: `io.casehub.neocortex.cognition.innerlife`
- `LevelEvent` import →
  `io.casehub.neocortex.summarisation.LevelEvent`
- `StructuredAgentInvoker` + `InvocationResult` → replace with
  `Instance<AgentProvider>` injection. Convert `invoker.invoke(...)`
  calls to `agentProvider.get().invoke(...)`. Follow the pattern
  established in `UserModelOrchestrator` and
  `MentalModelOrchestrator` (already migrated in Batch 5).
- `KeyedLock` → replace with
  `ConcurrentHashMap<String, ReentrantLock>` pattern:
  ```java
  private final ConcurrentHashMap<String, ReentrantLock> locks = new ConcurrentHashMap<>();
  private ReentrantLock lockFor(String key) {
      return locks.computeIfAbsent(key, k -> new ReentrantLock());
  }
  ```
- `ReflectionOrchestrator` → verify this is the same as
  `ReflectionRetrievalOrchestrator` in cognition-api. If different,
  check type hierarchy and update.
- All InnerLife config/value types → cognition-api imports

- [ ] **Step 4: Run test — verify pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=InnerLifeOrchestratorTest
```

Expected: PASS.

- [ ] **Step 5: Full build check**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

Expected: BUILD SUCCESS.

- [ ] **Step 6: Commit**

```bash
git add cognition/
git commit -m "feat(#303): move InnerLifeOrchestrator to cognition

LLM-driven agent inner life — observation buffering, civility
constraints, motivation assessment. Replaced StructuredAgentInvoker
with AgentProvider, inlined KeyedLock.

Refs casehubio/blocks#303"
```

---

## Batch 3: Move Narrative Classes

### Task 5: Move NarrativePipeline, NarrativeContentSummariser, NarrativeOutputProcessor, and helpers

**Files:**
- Create: `cognition/.../cognition/narrative/NarrativeContentSummariser.java`
- Create: `cognition/.../cognition/narrative/NarrativeOutputProcessor.java`
- Create: `cognition/.../cognition/narrative/NarrativeEmissionPolicy.java`
- Create: `cognition/.../cognition/narrative/ReflectionEventAdapter.java`
- Create: `cognition/.../cognition/narrative/NarrativeStateStore.java`
- Create: `cognition/.../cognition/narrative/NarrativePipeline.java`
- Create: Tests for all above

**Interfaces:**
- Consumes: `ContentSummariser`, `OutputProcessor`, `EmissionPolicy`,
  `StateStore`, `LevelEventBus`, `SummarisationPipelineFactory`,
  `LevelEvent`, `EventLevel` (all from summarisation);
  `ReflectionEntry`, `ReflectionQueryStore` (memory-api);
  `NarrativeMemory`, `NarrativeState`, `NarrativeConfig`,
  `NarrativeStateSchema`, `TokenJaccardDistance` (cognition);
  `AgentProvider` (platform-agent-api)
- Produces: Full narrative summarisation pipeline in cognition module

- [ ] **Step 1: Write NarrativeOutputProcessor test**

Read blocks' test:
`blocks-core/src/test/java/.../narrative/NarrativeOutputProcessorTest.java`
(5 tests, 97 LOC).

Create `cognition/src/test/java/io/casehub/neocortex/cognition/narrative/NarrativeOutputProcessorTest.java`.
Adapt: package change, `OutputProcessor` import from summarisation.

- [ ] **Step 2: Create NarrativeOutputProcessor**

Read blocks'
`blocks-core/.../narrative/NarrativeOutputProcessor.java` (64 LOC).
Create `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/NarrativeOutputProcessor.java`.

Changes:
- Package: `io.casehub.neocortex.cognition.narrative`
- `OutputProcessor` import →
  `io.casehub.neocortex.summarisation.OutputProcessor`
- `NarrativeState` import → already in this package

- [ ] **Step 3: Run test — verify pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=NarrativeOutputProcessorTest
```

- [ ] **Step 4: Write NarrativeContentSummariser test**

Read blocks' test:
`blocks-core/src/test/java/.../narrative/NarrativeContentSummariserTest.java`
(10 tests, 254 LOC).

Create `cognition/src/test/java/io/casehub/neocortex/cognition/narrative/NarrativeContentSummariserTest.java`.
Adapt:
- Package change
- `ContentSummariser` import from summarisation
- `StructuredAgentInvoker` → `AgentProvider` mock/stub
- `ReflectionEntry` import from memory-api

- [ ] **Step 5: Create NarrativeContentSummariser**

Read blocks'
`blocks-core/.../narrative/NarrativeContentSummariser.java` (367 LOC).
Create `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/NarrativeContentSummariser.java`.

Changes:
- Package: `io.casehub.neocortex.cognition.narrative`
- `ContentSummariser` import →
  `io.casehub.neocortex.summarisation.ContentSummariser`
- `StructuredAgentInvoker` → `Instance<AgentProvider>` (same pattern
  as InnerLifeOrchestrator)
- `ReflectionEntry` import →
  `io.casehub.neocortex.cognition.narrative.ReflectionEntry`
- All `NarrativeState`, `NarrativeConfig`, `NarrativeEpisode` etc →
  already in this package

- [ ] **Step 6: Run test — verify pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest=NarrativeContentSummariserTest
```

- [ ] **Step 7: Create NarrativeEmissionPolicy**

Read blocks'
`blocks-core/.../narrative/NarrativeEmissionPolicy.java` (51 LOC).
Create `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/NarrativeEmissionPolicy.java`.

Changes:
- Package: `io.casehub.neocortex.cognition.narrative`
- `EmissionPolicy`, `LevelEvent` imports from summarisation
- `TokenJaccardDistance` → already in cognition (migrated Batch 5)
- `NarrativeSynthesisGate`, `IndividualEpisode`, `NarrativeState` →
  already in cognition-api/cognition

- [ ] **Step 8: Create ReflectionEventAdapter**

Read blocks'
`blocks-core/.../narrative/ReflectionEventAdapter.java` (45 LOC).
Create `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/ReflectionEventAdapter.java`.

Changes:
- Package: `io.casehub.neocortex.cognition.narrative`
- `LevelEventBus`, `LevelEvent`, `EventLevel` imports from
  summarisation module
- `ReflectionEntry`, `ReflectionQueryStore` imports from memory-api

- [ ] **Step 9: Create NarrativeStateStore**

This replaces the old `CbrStateStore` → `CbrNarrativeStore` →
`NarrativeStore` chain. It wraps `NarrativeMemory` (already exists)
and implements `StateStore<NarrativeState>` from summarisation.

Create `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/NarrativeStateStore.java`:

```java
package io.casehub.neocortex.cognition.narrative;

import io.casehub.neocortex.summarisation.StateStore;
import org.jspecify.annotations.Nullable;

public class NarrativeStateStore implements StateStore<NarrativeState> {

    private final NarrativeMemory memory;
    private final String tenantId;

    public NarrativeStateStore(NarrativeMemory memory, String tenantId) {
        this.memory = memory;
        this.tenantId = tenantId;
    }

    @Override
    public @Nullable NarrativeState load(String partitionKey) {
        return memory.load(partitionKey, tenantId);
    }

    @Override
    public void store(String partitionKey, NarrativeState state) {
        memory.store(state);
    }
}
```

Read blocks' `CbrStateStore` (24 LOC) to verify the load/store
delegation matches.

- [ ] **Step 10: Write NarrativePipeline test**

Read blocks' test:
`blocks-core/src/test/java/.../narrative/NarrativePipelineTest.java`
(4 tests, 201 LOC).

Create `cognition/src/test/java/io/casehub/neocortex/cognition/narrative/NarrativePipelineTest.java`.
Adapt:
- Package change
- Summarisation imports from summarisation
- Mock `SummarisationPipelineFactory` — return a test pipeline
  that captures accepted events and produces canned output on tick
- `ReflectionEntry` from memory-api
- `NarrativeMemory`, `NarrativeState` etc from cognition

- [ ] **Step 11: Create NarrativePipeline**

Read blocks'
`blocks-core/.../narrative/NarrativePipeline.java` (69 LOC).
Create `cognition/src/main/java/io/casehub/neocortex/cognition/narrative/NarrativePipeline.java`.

This is a rewrite, not a straight copy. The original wires
`LevelEventBus` + `SummarisationRunner`. The new version uses
`SummarisationPipelineFactory` SPI:

```java
package io.casehub.neocortex.cognition.narrative;

import io.casehub.neocortex.summarisation.*;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Instance;

@ApplicationScoped
public class NarrativePipeline implements Tickable {

    private final LevelEventBus<ReflectionEntry> reflectionBus;
    private final SummarisationPipeline<ReflectionEntry> pipeline;

    NarrativePipeline(
            Instance<SummarisationPipelineFactory> factoryInstance,
            NarrativeContentSummariser summariser,
            NarrativeOutputProcessor outputProcessor,
            NarrativeEmissionPolicy emissionPolicy,
            NarrativeMemory narrativeMemory,
            NarrativeConfig config) {

        this.reflectionBus = new LevelEventBus<>();

        if (factoryInstance.isResolvable()) {
            var stateStore = new NarrativeStateStore(narrativeMemory, config.tenantId());
            this.pipeline = factoryInstance.get().create(
                    summariser.asSummariser(),
                    outputProcessor,
                    emissionPolicy,
                    stateStore,
                    config.partitionKey(),
                    config.windowPolicy());
            reflectionBus.subscribe(e -> true, pipeline::accept);
        } else {
            this.pipeline = null;
        }
    }

    public void observe(ReflectionEntry entry) {
        reflectionBus.publish(new LevelEvent<>(
                entry, System.currentTimeMillis(),
                new EventLevel("reflection", 0), null));
    }

    @Override
    public java.util.concurrent.CompletionStage<Void> tick(long now) {
        return pipeline != null ? pipeline.tick(now)
                : java.util.concurrent.CompletableFuture.completedFuture(null);
    }

    @Override
    public java.util.concurrent.CompletionStage<Void> flush() {
        return pipeline != null ? pipeline.flush()
                : java.util.concurrent.CompletableFuture.completedFuture(null);
    }
}
```

Read the original blocks source to verify the wiring logic, event level
naming, and config fields match. The exact constructor parameters depend
on what `NarrativeConfig` provides — read `NarrativeConfig` in
cognition-api to verify `partitionKey()`, `tenantId()`,
`windowPolicy()` accessors exist (add them if missing).

- [ ] **Step 12: Run tests — verify pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl cognition -Dtest="NarrativeOutputProcessorTest,NarrativeContentSummariserTest,NarrativePipelineTest"
```

Expected: all pass.

- [ ] **Step 13: Full build**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

Expected: BUILD SUCCESS, all tests pass.

- [ ] **Step 14: Commit**

```bash
git add cognition/
git commit -m "feat(#303): move narrative pipeline and summarisation classes to cognition

NarrativePipeline, NarrativeContentSummariser, NarrativeOutputProcessor,
NarrativeEmissionPolicy, ReflectionEventAdapter, NarrativeStateStore.
NarrativePipeline rewired to use SummarisationPipelineFactory SPI.

Refs casehubio/blocks#303"
```

---

## Post-Plan: HANDOFF and CLAUDE.md Updates

After all batches complete:

1. Update `HANDOFF.md` — move all 6 deferred items from "Deferred" to
   completed batches
2. Update neocortex `CLAUDE.md` — add `summarisation` module
   description and Maven coordinates
3. Note in HANDOFF: blocks needs to migrate imports from
   `io.casehub.blocks.summarisation` to
   `io.casehub.neocortex.summarisation` (Batch 7 bridge work)

---

## References

- [2026-09-29-cognition-migration.md] — parent migration plan
- [2026-09-29-cognition-migration-design.md] — design spec
- blocks `summarisation-api/` — source for summarisation framework types
- blocks `blocks-core/.../agentic/social/` — source for deferred classes
- slot 196 branch `issue-312-consolidation-artifacts` — ConsolidationArtifact source
- casehubio/blocks#303 — focal issue
- casehubio/blocks#298 — parent epic
