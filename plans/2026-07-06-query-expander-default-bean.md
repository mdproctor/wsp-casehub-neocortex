# Query Expander Default Bean — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #112 — fix: LlmQueryExpander enableIfMissing=true causes unsatisfied ChatModel in consumer @QuarkusTest
**Issue group:** #112

**Goal:** Remove the implicit LLM default from query expansion so consumers can adopt `rag-expansion` without a `ChatModel` dependency, by adding a no-op `@DefaultBean` and requiring explicit mode selection.

**Architecture:** Four changes in `rag-expansion/`: (1) remove `enableIfMissing = true` from `LlmQueryExpander`, (2) change `ExpansionConfig.mode()` from `@WithDefault("llm") String` to `Optional<String>`, (3) add `NoOpQueryExpander` as `@DefaultBean`, (4) add `ExpansionConfigValidator` startup warning. All test `stubConfig` methods update to match the new `Optional<String> mode()` signature.

**Tech Stack:** Java 21, Quarkus Arc CDI, SmallRye Config `@ConfigMapping`

## Global Constraints

- Use `io.quarkus.arc.DefaultBean` (not jakarta)
- `NoOpQueryExpander` follows `NoOpCbrCaseMemoryStore` pattern in `memory/`
- All tests are plain JUnit 5 unit tests (no `@QuarkusTest` in this module)
- Build with: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl rag-expansion`

---

### Task 1: NoOpQueryExpander + ExpansionConfig.mode() change

This task creates the no-op default bean and updates the config interface. Both changes are tightly coupled — the no-op is meaningless without the config change, and the config change breaks stubConfig in tests without the no-op.

**Files:**
- Create: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/NoOpQueryExpander.java`
- Create: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/NoOpQueryExpanderTest.java`
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ExpansionConfig.java` (line 14-15)
- Modify: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/LlmQueryExpander.java` (line 17)
- Modify: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/LlmQueryExpanderTest.java` (stubConfig methods, lines 143-156)
- Modify: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/StepBackQueryExpanderTest.java` (stubConfig method, lines 80-89)
- Modify: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/TemplateQueryExpanderTest.java` (stubConfig method, lines 44-54)

**Interfaces:**
- Consumes: `QueryExpander` SPI from `rag-api` (interface with `List<RetrievalQuery> expand(RetrievalQuery query)`)
- Produces: `NoOpQueryExpander` — `@DefaultBean @ApplicationScoped`, displaced by any `@ApplicationScoped` or `@Alternative` implementation

- [ ] **Step 1: Write the failing test for NoOpQueryExpander**

Create `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/NoOpQueryExpanderTest.java`:

```java
package io.casehub.neocortex.rag.expansion;

import io.casehub.neocortex.rag.RetrievalQuery;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class NoOpQueryExpanderTest {

    @Test
    void expandReturnsSingleElementListWithOriginalQuery() {
        var expander = new NoOpQueryExpander();
        var query = RetrievalQuery.of("what is diabetes?");
        var result = expander.expand(query);

        assertThat(result).hasSize(1);
        assertThat(result.get(0)).isSameAs(query);
    }

    @Test
    void expandPreservesExistingExpansion() {
        var expander = new NoOpQueryExpander();
        var query = new RetrievalQuery("original", "prior expansion");
        var result = expander.expand(query);

        assertThat(result).hasSize(1);
        assertThat(result.get(0)).isSameAs(query);
        assertThat(result.get(0).expandedText()).isEqualTo("prior expansion");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=NoOpQueryExpanderTest -Dsurefire.failIfNoSpecifiedTests=false`

Expected: FAIL — `NoOpQueryExpander` class does not exist.

- [ ] **Step 3: Implement NoOpQueryExpander**

Create `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/NoOpQueryExpander.java`:

```java
package io.casehub.neocortex.rag.expansion;

import io.casehub.neocortex.rag.QueryExpander;
import io.casehub.neocortex.rag.RetrievalQuery;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;

import java.util.List;

@DefaultBean
@ApplicationScoped
public class NoOpQueryExpander implements QueryExpander {

    @Override
    public List<RetrievalQuery> expand(RetrievalQuery query) {
        return List.of(query);
    }
}
```

- [ ] **Step 4: Run NoOpQueryExpanderTest to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=NoOpQueryExpanderTest`

Expected: 2 tests PASS.

- [ ] **Step 5: Remove `enableIfMissing = true` from LlmQueryExpander**

In `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/LlmQueryExpander.java`, change:

```java
// Before (line 17)
@IfBuildProperty(name = "casehub.rag.expansion.mode", stringValue = "llm", enableIfMissing = true)

// After
@IfBuildProperty(name = "casehub.rag.expansion.mode", stringValue = "llm")
```

- [ ] **Step 6: Change `ExpansionConfig.mode()` to `Optional<String>`**

In `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ExpansionConfig.java`, change:

```java
// Before (lines 14-15)
@WithDefault("llm")
String mode();

// After
Optional<String> mode();
```

Also remove the `import io.smallrye.config.WithDefault;` if it becomes unused (check if `enabled()` or other methods use it — `enabled()` uses `@WithDefault("false")` and `hypotheticalCount()` uses `@WithDefault("1")`, so keep the import).

- [ ] **Step 7: Update `stubConfig` in LlmQueryExpanderTest**

In `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/LlmQueryExpanderTest.java`, change the `stubConfig` methods (lines 143-156):

```java
private static ExpansionConfig stubConfig(Optional<String> promptTemplate, int hypotheticalCount) {
    return new ExpansionConfig() {
        @Override public boolean enabled() { return true; }
        @Override public Optional<String> mode() { return Optional.of("llm"); }
        @Override public int hypotheticalCount() { return hypotheticalCount; }
        @Override public Optional<String> promptTemplate() { return promptTemplate; }
        @Override public Optional<String> template() { return Optional.empty(); }
        @Override public Optional<String> stepBackPromptTemplate() { return Optional.empty(); }
    };
}

private static ExpansionConfig stubConfig(Optional<String> promptTemplate) {
    return stubConfig(promptTemplate, 1);
}
```

- [ ] **Step 8: Update `stubConfig` in StepBackQueryExpanderTest**

In `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/StepBackQueryExpanderTest.java`, change the `stubConfig` method (lines 80-89):

```java
private static ExpansionConfig stubConfig(Optional<String> stepBackPromptTemplate) {
    return new ExpansionConfig() {
        @Override public boolean enabled() { return true; }
        @Override public Optional<String> mode() { return Optional.of("step-back"); }
        @Override public int hypotheticalCount() { return 1; }
        @Override public Optional<String> promptTemplate() { return Optional.empty(); }
        @Override public Optional<String> template() { return Optional.empty(); }
        @Override public Optional<String> stepBackPromptTemplate() { return stepBackPromptTemplate; }
    };
}
```

- [ ] **Step 9: Update `stubConfig` in TemplateQueryExpanderTest**

In `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/TemplateQueryExpanderTest.java`, change the `stubConfig` method (lines 44-54):

```java
private static ExpansionConfig stubConfig(Optional<String> template) {
    return new ExpansionConfig() {
        @Override public boolean enabled() { return true; }
        @Override public Optional<String> mode() { return Optional.of("template"); }
        @Override public int hypotheticalCount() { return 1; }
        @Override public Optional<String> promptTemplate() { return Optional.empty(); }
        @Override public Optional<String> template() { return template; }
        @Override public Optional<String> stepBackPromptTemplate() { return Optional.empty(); }
    };
}
```

- [ ] **Step 10: Run all rag-expansion tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion`

Expected: ALL tests pass (NoOpQueryExpanderTest + all existing tests with updated stubConfig).

- [ ] **Step 11: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add \
  rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/NoOpQueryExpander.java \
  rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/NoOpQueryExpanderTest.java \
  rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ExpansionConfig.java \
  rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/LlmQueryExpander.java \
  rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/LlmQueryExpanderTest.java \
  rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/StepBackQueryExpanderTest.java \
  rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/TemplateQueryExpanderTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#112): NoOpQueryExpander @DefaultBean, remove enableIfMissing + @WithDefault from expansion config"
```

---

### Task 2: ExpansionConfigValidator startup warning

**Files:**
- Create: `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ExpansionConfigValidator.java`
- Create: `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/ExpansionConfigValidatorTest.java`

**Interfaces:**
- Consumes: `ExpansionConfig.mode()` (returns `Optional<String>` from Task 1)
- Produces: Startup log warning when `expansion.enabled=true` but no mode is set

- [ ] **Step 1: Write the failing test for ExpansionConfigValidator**

Create `rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/ExpansionConfigValidatorTest.java`:

```java
package io.casehub.neocortex.rag.expansion;

import io.quarkus.runtime.StartupEvent;
import org.junit.jupiter.api.Test;

import java.util.Optional;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.LogRecord;
import java.util.logging.Logger;

import static org.assertj.core.api.Assertions.assertThat;

class ExpansionConfigValidatorTest {

    @Test
    void warnsWhenModeIsEmpty() {
        var validator = new ExpansionConfigValidator();
        validator.config = stubConfig(Optional.empty());

        var record = captureWarning(validator);

        assertThat(record).isNotNull();
        assertThat(record.getMessage()).contains("no mode is set");
        assertThat(record.getMessage()).contains("casehub.rag.expansion.mode");
    }

    @Test
    void noWarningWhenModeIsSet() {
        var validator = new ExpansionConfigValidator();
        validator.config = stubConfig(Optional.of("llm"));

        var record = captureWarning(validator);

        assertThat(record).isNull();
    }

    private LogRecord captureWarning(ExpansionConfigValidator validator) {
        var logger = Logger.getLogger(ExpansionConfigValidator.class.getName());
        var captured = new LogRecord[1];
        var handler = new Handler() {
            @Override public void publish(LogRecord r) {
                if (r.getLevel() == Level.WARNING) captured[0] = r;
            }
            @Override public void flush() {}
            @Override public void close() {}
        };
        logger.addHandler(handler);
        try {
            validator.onStartup(new StartupEvent());
        } finally {
            logger.removeHandler(handler);
        }
        return captured[0];
    }

    private static ExpansionConfig stubConfig(Optional<String> mode) {
        return new ExpansionConfig() {
            @Override public boolean enabled() { return true; }
            @Override public Optional<String> mode() { return mode; }
            @Override public int hypotheticalCount() { return 1; }
            @Override public Optional<String> promptTemplate() { return Optional.empty(); }
            @Override public Optional<String> template() { return Optional.empty(); }
            @Override public Optional<String> stepBackPromptTemplate() { return Optional.empty(); }
        };
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=ExpansionConfigValidatorTest -Dsurefire.failIfNoSpecifiedTests=false`

Expected: FAIL — `ExpansionConfigValidator` class does not exist.

- [ ] **Step 3: Implement ExpansionConfigValidator**

Create `rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ExpansionConfigValidator.java`:

```java
package io.casehub.neocortex.rag.expansion;

import io.quarkus.arc.properties.IfBuildProperty;
import io.quarkus.runtime.StartupEvent;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.event.Observes;
import jakarta.inject.Inject;

import java.util.logging.Logger;

@ApplicationScoped
@IfBuildProperty(name = "casehub.rag.expansion.enabled", stringValue = "true")
public class ExpansionConfigValidator {

    private static final Logger LOG = Logger.getLogger(ExpansionConfigValidator.class.getName());

    @Inject
    ExpansionConfig config;

    void onStartup(@Observes StartupEvent event) {
        if (config.mode().isEmpty()) {
            LOG.warning("Query expansion is enabled but no mode is set"
                + " — queries will pass through unchanged."
                + " Set casehub.rag.expansion.mode to llm, template, or step-back.");
        }
    }
}
```

Note: The `config` field uses package-private access (no `private` modifier) so the unit test can set it directly. The `@Inject` annotation drives CDI injection in production; in tests we assign directly.

- [ ] **Step 4: Run ExpansionConfigValidatorTest to verify it passes**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion -Dtest=ExpansionConfigValidatorTest`

Expected: 2 tests PASS.

- [ ] **Step 5: Run full rag-expansion test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl rag-expansion`

Expected: ALL tests pass.

- [ ] **Step 6: Run full project build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`

Expected: BUILD SUCCESS. No compile errors in any module that depends on `rag-expansion`.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add \
  rag-expansion/src/main/java/io/casehub/neocortex/rag/expansion/ExpansionConfigValidator.java \
  rag-expansion/src/test/java/io/casehub/neocortex/rag/expansion/ExpansionConfigValidatorTest.java
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(#112): ExpansionConfigValidator — startup warning when expansion enabled without mode"
```
