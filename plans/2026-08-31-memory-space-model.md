# Memory Space Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #230 — feat: memory space model — private, shared, and selective visibility
**Issue group:** #253, #230

**Goal:** Implement the memory space model — MemorySpace, Visibility, SpaceMembership types and SpaceMembershipStore SPI with three-tier CDI backends (NoOp, InMemory, SQLite).

**Architecture:** Space-as-tenant model. Each memory space IS a tenantId. The visibility layer maintains membership (which agents see which spaces) and resolves the set of tenant IDs to query. Existing stores remain unchanged — they still receive `tenantId`. Five new modules following the established mindmap three-tier CDI pattern: API (zero deps) → CDI wiring (NoOp @DefaultBean) → testing (contract test base) → in-memory (@Alternative @Priority(2)) → SQLite (@Alternative @Priority(1)).

**Tech Stack:** Java 21, Quarkus CDI (quarkus-arc), SQLite + HikariCP + Flyway, JUnit 5, AssertJ

## Global Constraints

- Java 21 source level (on Java 26 JVM): `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn`
- `memory-space-api` is tier-0, zero runtime deps (only JUnit + AssertJ for tests)
- CDI modules require `jandex-maven-plugin` in build plugins
- All modules use `groupId=io.casehub`, `version=0.2-SNAPSHOT`, parent `casehub-neocortex-parent`
- Package root: `io.casehub.neocortex.memory.space`
- Each new module must be registered in parent pom.xml `<modules>` and `<dependencyManagement>`
- Use `mvn` not `./mvnw`

**Spec deviation:** The spec places NoOpSpaceMembershipStore in `memory-space-api`, but that would require a quarkus-arc dependency, breaking the zero-dep guarantee. Following the established `mindmap/` pattern, the NoOp goes in a separate `memory-space/` CDI wiring module. The spec itself references "same pattern as NoOpMindMapStore in `mindmap`" — and NoOpMindMapStore is in the `mindmap` module, not `mindmap-api`.

---

## Batch 1: API types and SPI (memory-space-api)

### Task 1: Create memory-space-api module with types, SPI, and validation tests

**Files:**
- Create: `memory-space-api/pom.xml`
- Create: `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/SpaceType.java`
- Create: `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/MemorySpace.java`
- Create: `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/Visibility.java`
- Create: `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/SpaceMembership.java`
- Create: `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/SpaceMembershipStore.java`
- Create: `memory-space-api/src/test/java/io/casehub/neocortex/memory/space/MemorySpaceTest.java`
- Create: `memory-space-api/src/test/java/io/casehub/neocortex/memory/space/SpaceMembershipTest.java`
- Create: `memory-space-api/src/test/java/io/casehub/neocortex/memory/space/VisibilityTest.java`
- Modify: `pom.xml` (parent — add module + dependencyManagement)

**Interfaces:**
- Produces: `SpaceType` enum (PRIVATE, SHARED)
- Produces: `MemorySpace` record (id, type, name, ownerId) with `privateSpace()`, `sharedSpace()` factories
- Produces: `Visibility` sealed interface (Private, Shared, Selective)
- Produces: `SpaceMembership` record (agentId, spaceId, roles, validFrom, validUntil)
- Produces: `SpaceMembershipStore` SPI interface (createSpace, getSpace, addMember, revokeMember, spacesFor, membersOf)

- [ ] **Step 1: Create module pom.xml**

Use `ide_create_file` to create `memory-space-api/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>io.casehub</groupId>
        <artifactId>casehub-neocortex-parent</artifactId>
        <version>0.2-SNAPSHOT</version>
    </parent>
    <artifactId>casehub-neocortex-memory-space-api</artifactId>
    <name>CaseHub Neocortex Memory Space API</name>
    <description>Memory space model — MemorySpace, Visibility, SpaceMembership types and SpaceMembershipStore SPI</description>
    <dependencies>
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

- [ ] **Step 2: Register module in parent pom.xml**

Add `<module>memory-space-api</module>` to the `<modules>` section (after `mindmap-intelligence`).

Add to `<dependencyManagement>`:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-space-api</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Write validation tests**

Create `memory-space-api/src/test/java/io/casehub/neocortex/memory/space/MemorySpaceTest.java`:

```java
package io.casehub.neocortex.memory.space;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class MemorySpaceTest {

    @Test
    void privateSpaceRequiresOwnerId() {
        assertThatThrownBy(() -> MemorySpace.privateSpace("id", "name", null))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void sharedSpaceRejectsOwnerId() {
        assertThatThrownBy(() -> new MemorySpace("id", SpaceType.SHARED, "name", "owner"))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void privateSpaceFactoryCreatesCorrectly() {
        MemorySpace space = MemorySpace.privateSpace("alice-priv", "Alice Private", "alice");
        assertThat(space.id()).isEqualTo("alice-priv");
        assertThat(space.type()).isEqualTo(SpaceType.PRIVATE);
        assertThat(space.name()).isEqualTo("Alice Private");
        assertThat(space.ownerId()).isEqualTo("alice");
    }

    @Test
    void sharedSpaceFactoryCreatesCorrectly() {
        MemorySpace space = MemorySpace.sharedSpace("family", "Smith Family");
        assertThat(space.id()).isEqualTo("family");
        assertThat(space.type()).isEqualTo(SpaceType.SHARED);
        assertThat(space.name()).isEqualTo("Smith Family");
        assertThat(space.ownerId()).isNull();
    }

    @Test
    void rejectsNullIdAndName() {
        assertThatThrownBy(() -> MemorySpace.privateSpace(null, "name", "owner"))
            .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> MemorySpace.privateSpace("id", null, "owner"))
            .isInstanceOf(NullPointerException.class);
    }
}
```

Create `memory-space-api/src/test/java/io/casehub/neocortex/memory/space/SpaceMembershipTest.java`:

```java
package io.casehub.neocortex.memory.space;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.HashSet;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class SpaceMembershipTest {

    @Test
    void defensiveCopiesRoles() {
        Set<String> roles = new HashSet<>();
        roles.add("admin");
        SpaceMembership m = new SpaceMembership("agent", "space", roles, Instant.now(), null);
        roles.add("sneaky");
        assertThat(m.roles()).containsExactly("admin");
    }

    @Test
    void rejectsNullRequiredFields() {
        Instant now = Instant.now();
        assertThatThrownBy(() -> new SpaceMembership(null, "space", Set.of(), now, null))
            .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> new SpaceMembership("agent", null, Set.of(), now, null))
            .isInstanceOf(NullPointerException.class);
        assertThatThrownBy(() -> new SpaceMembership("agent", "space", Set.of(), null, null))
            .isInstanceOf(NullPointerException.class);
    }

    @Test
    void nullRolesDefaultsToEmptySet() {
        SpaceMembership m = new SpaceMembership("agent", "space", null, Instant.now(), null);
        assertThat(m.roles()).isEmpty();
    }
}
```

Create `memory-space-api/src/test/java/io/casehub/neocortex/memory/space/VisibilityTest.java`:

```java
package io.casehub.neocortex.memory.space;

import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class VisibilityTest {

    @Test
    void privateVariant() {
        Visibility v = new Visibility.Private("alice");
        assertThat(v).isInstanceOf(Visibility.Private.class);
        assertThat(((Visibility.Private) v).ownerId()).isEqualTo("alice");
    }

    @Test
    void sharedVariant() {
        Visibility v = new Visibility.Shared("family");
        assertThat(v).isInstanceOf(Visibility.Shared.class);
        assertThat(((Visibility.Shared) v).spaceId()).isEqualTo("family");
    }

    @Test
    void selectiveVariantDefensiveCopiesRecipients() {
        Set<String> ids = new java.util.HashSet<>();
        ids.add("bob");
        Visibility.Selective v = new Visibility.Selective("space", ids);
        ids.add("sneaky");
        assertThat(v.recipientIds()).containsExactly("bob");
    }

    @Test
    void selectiveRejectsNullSpaceId() {
        assertThatThrownBy(() -> new Visibility.Selective(null, Set.of("a")))
            .isInstanceOf(NullPointerException.class);
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-space-api`
Expected: compilation failure — types not yet created.

- [ ] **Step 5: Implement SpaceType enum**

Create `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/SpaceType.java`:

```java
package io.casehub.neocortex.memory.space;

public enum SpaceType {
    PRIVATE,
    SHARED
}
```

- [ ] **Step 6: Implement MemorySpace record**

Create `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/MemorySpace.java`:

```java
package io.casehub.neocortex.memory.space;

import java.util.Objects;

public record MemorySpace(
    String id,
    SpaceType type,
    String name,
    String ownerId
) {
    public MemorySpace {
        Objects.requireNonNull(id, "id");
        Objects.requireNonNull(type, "type");
        Objects.requireNonNull(name, "name");
        if (type == SpaceType.PRIVATE && ownerId == null) {
            throw new IllegalArgumentException("ownerId required for PRIVATE spaces");
        }
        if (type == SpaceType.SHARED && ownerId != null) {
            throw new IllegalArgumentException("ownerId must be null for SHARED spaces");
        }
    }

    public static MemorySpace privateSpace(String id, String name, String ownerId) {
        return new MemorySpace(id, SpaceType.PRIVATE, name, ownerId);
    }

    public static MemorySpace sharedSpace(String id, String name) {
        return new MemorySpace(id, SpaceType.SHARED, name, null);
    }
}
```

- [ ] **Step 7: Implement Visibility sealed interface**

Create `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/Visibility.java`:

```java
package io.casehub.neocortex.memory.space;

import java.util.Objects;
import java.util.Set;

public sealed interface Visibility {

    record Private(String ownerId) implements Visibility {
        public Private {
            Objects.requireNonNull(ownerId, "ownerId");
        }
    }

    record Shared(String spaceId) implements Visibility {
        public Shared {
            Objects.requireNonNull(spaceId, "spaceId");
        }
    }

    record Selective(String spaceId, Set<String> recipientIds) implements Visibility {
        public Selective {
            Objects.requireNonNull(spaceId, "spaceId");
            Objects.requireNonNull(recipientIds, "recipientIds");
            recipientIds = Set.copyOf(recipientIds);
        }
    }
}
```

- [ ] **Step 8: Implement SpaceMembership record**

Create `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/SpaceMembership.java`:

```java
package io.casehub.neocortex.memory.space;

import java.time.Instant;
import java.util.Objects;
import java.util.Set;

public record SpaceMembership(
    String agentId,
    String spaceId,
    Set<String> roles,
    Instant validFrom,
    Instant validUntil
) {
    public SpaceMembership {
        Objects.requireNonNull(agentId, "agentId");
        Objects.requireNonNull(spaceId, "spaceId");
        Objects.requireNonNull(validFrom, "validFrom");
        roles = roles == null ? Set.of() : Set.copyOf(roles);
    }
}
```

- [ ] **Step 9: Implement SpaceMembershipStore SPI**

Create `memory-space-api/src/main/java/io/casehub/neocortex/memory/space/SpaceMembershipStore.java`:

```java
package io.casehub.neocortex.memory.space;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

public interface SpaceMembershipStore {

    void createSpace(MemorySpace space);

    Optional<MemorySpace> getSpace(String spaceId);

    void addMember(SpaceMembership membership);

    void revokeMember(String agentId, String spaceId, Instant revokedAt);

    List<MemorySpace> spacesFor(String agentId, Instant asOf);

    List<SpaceMembership> membersOf(String spaceId, Instant asOf);
}
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-space-api`
Expected: all 8 tests PASS (5 MemorySpace, 3 SpaceMembership, 4 Visibility — wait, let me recount).

Recount: MemorySpaceTest (5 tests), SpaceMembershipTest (3 tests), VisibilityTest (4 tests) = 12 tests.

- [ ] **Step 11: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-space-api/ pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory-space-api): types, SPI, and validation tests Refs #230"
```

---

## Batch 2: Contract tests + InMemory backend (memory-space-testing + memory-space-inmem)

### Task 2: Create contract test base and InMemory implementation

**Files:**
- Create: `memory-space-testing/pom.xml`
- Create: `memory-space-testing/src/main/java/io/casehub/neocortex/memory/space/testing/SpaceMembershipStoreContractTest.java`
- Create: `memory-space-inmem/pom.xml`
- Create: `memory-space-inmem/src/main/java/io/casehub/neocortex/memory/space/inmem/InMemorySpaceMembershipStore.java`
- Create: `memory-space-inmem/src/test/java/io/casehub/neocortex/memory/space/inmem/InMemorySpaceMembershipStoreTest.java`
- Modify: `pom.xml` (parent — add modules + dependencyManagement)

**Interfaces:**
- Consumes: `SpaceMembershipStore` SPI from Task 1
- Consumes: `MemorySpace`, `SpaceMembership`, `SpaceType` from Task 1
- Produces: `SpaceMembershipStoreContractTest` abstract base class (10 contract tests)
- Produces: `InMemorySpaceMembershipStore` @Alternative @Priority(2)

- [ ] **Step 1: Create memory-space-testing pom.xml**

Use `ide_create_file` to create `memory-space-testing/pom.xml`:

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
  <artifactId>casehub-neocortex-memory-space-testing</artifactId>
  <name>CaseHub Neocortex - Memory Space Testing</name>
  <description>SpaceMembershipStoreContractTest abstract base class.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-space-api</artifactId>
    </dependency>
    <dependency>
      <groupId>org.junit.jupiter</groupId>
      <artifactId>junit-jupiter</artifactId>
      <scope>compile</scope>
    </dependency>
    <dependency>
      <groupId>org.assertj</groupId>
      <artifactId>assertj-core</artifactId>
      <scope>compile</scope>
    </dependency>
  </dependencies>
</project>
```

- [ ] **Step 2: Create memory-space-inmem pom.xml**

Use `ide_create_file` to create `memory-space-inmem/pom.xml`:

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
  <artifactId>casehub-neocortex-memory-space-inmem</artifactId>
  <name>CaseHub Neocortex - Memory Space In-Memory</name>
  <description>In-memory SpaceMembershipStore for testing and dev. @Alternative @Priority(2).</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-space-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-space-testing</artifactId>
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

- [ ] **Step 3: Register both modules in parent pom.xml**

Add to `<modules>` (after `mindmap-intelligence`):
```xml
<module>memory-space-testing</module>
<module>memory-space-inmem</module>
```

Add to `<dependencyManagement>`:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-space-testing</artifactId>
    <version>${project.version}</version>
</dependency>
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-space-inmem</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 4: Write contract test base**

Create `memory-space-testing/src/main/java/io/casehub/neocortex/memory/space/testing/SpaceMembershipStoreContractTest.java`:

```java
package io.casehub.neocortex.memory.space.testing;

import io.casehub.neocortex.memory.space.MemorySpace;
import io.casehub.neocortex.memory.space.SpaceMembership;
import io.casehub.neocortex.memory.space.SpaceMembershipStore;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;

public abstract class SpaceMembershipStoreContractTest {

    protected SpaceMembershipStore store;

    protected abstract SpaceMembershipStore createStore();

    private static final Instant T0 = Instant.parse("2026-01-01T00:00:00Z");
    private static final Instant T1 = T0.plus(1, ChronoUnit.HOURS);
    private static final Instant T2 = T0.plus(2, ChronoUnit.HOURS);
    private static final Instant T3 = T0.plus(3, ChronoUnit.HOURS);
    private static final Instant T4 = T0.plus(4, ChronoUnit.HOURS);

    @BeforeEach
    void setUp() {
        store = createStore();
    }

    @Test
    void createSpaceAndGetRoundTrip() {
        MemorySpace space = MemorySpace.sharedSpace("family", "Smith Family");
        store.createSpace(space);
        var retrieved = store.getSpace("family");
        assertThat(retrieved).isPresent();
        assertThat(retrieved.get().id()).isEqualTo("family");
        assertThat(retrieved.get().name()).isEqualTo("Smith Family");
        assertThat(retrieved.get().type()).isEqualTo(io.casehub.neocortex.memory.space.SpaceType.SHARED);
        assertThat(retrieved.get().ownerId()).isNull();
    }

    @Test
    void getSpaceReturnsEmptyForUnknown() {
        assertThat(store.getSpace("nonexistent")).isEmpty();
    }

    @Test
    void addMemberAndSpacesFor() {
        MemorySpace space = MemorySpace.sharedSpace("team", "Dev Team");
        store.createSpace(space);
        store.addMember(new SpaceMembership("alice", "team", Set.of("member"), T0, null));
        var spaces = store.spacesFor("alice", T1);
        assertThat(spaces).hasSize(1);
        assertThat(spaces.getFirst().id()).isEqualTo("team");
    }

    @Test
    void spacesForRespectsValidFrom() {
        MemorySpace space = MemorySpace.sharedSpace("team", "Dev Team");
        store.createSpace(space);
        store.addMember(new SpaceMembership("alice", "team", Set.of(), T2, null));
        assertThat(store.spacesFor("alice", T1)).isEmpty();
        assertThat(store.spacesFor("alice", T2)).hasSize(1);
        assertThat(store.spacesFor("alice", T3)).hasSize(1);
    }

    @Test
    void spacesForRespectsValidUntil() {
        MemorySpace space = MemorySpace.sharedSpace("team", "Dev Team");
        store.createSpace(space);
        store.addMember(new SpaceMembership("alice", "team", Set.of(), T0, T2));
        assertThat(store.spacesFor("alice", T1)).hasSize(1);
        assertThat(store.spacesFor("alice", T2)).isEmpty();
        assertThat(store.spacesFor("alice", T3)).isEmpty();
    }

    @Test
    void revokeMemberSetsValidUntil() {
        MemorySpace space = MemorySpace.sharedSpace("team", "Dev Team");
        store.createSpace(space);
        store.addMember(new SpaceMembership("alice", "team", Set.of(), T0, null));
        assertThat(store.spacesFor("alice", T1)).hasSize(1);
        store.revokeMember("alice", "team", T2);
        assertThat(store.spacesFor("alice", T3)).isEmpty();
        assertThat(store.spacesFor("alice", T1)).hasSize(1);
    }

    @Test
    void membersOfReturnsActiveMembers() {
        MemorySpace space = MemorySpace.sharedSpace("team", "Dev Team");
        store.createSpace(space);
        store.addMember(new SpaceMembership("alice", "team", Set.of("admin"), T0, null));
        store.addMember(new SpaceMembership("bob", "team", Set.of("member"), T0, null));
        var members = store.membersOf("team", T1);
        assertThat(members).hasSize(2);
        assertThat(members).extracting(SpaceMembership::agentId)
            .containsExactlyInAnyOrder("alice", "bob");
    }

    @Test
    void membersOfRespectsTemporalValidity() {
        MemorySpace space = MemorySpace.sharedSpace("team", "Dev Team");
        store.createSpace(space);
        store.addMember(new SpaceMembership("alice", "team", Set.of(), T0, null));
        store.addMember(new SpaceMembership("bob", "team", Set.of(), T2, null));
        var membersAtT1 = store.membersOf("team", T1);
        assertThat(membersAtT1).hasSize(1);
        assertThat(membersAtT1.getFirst().agentId()).isEqualTo("alice");
        var membersAtT3 = store.membersOf("team", T3);
        assertThat(membersAtT3).hasSize(2);
    }

    @Test
    void multipleSpacesAgentSeesAll() {
        store.createSpace(MemorySpace.privateSpace("alice-priv", "Alice Private", "alice"));
        store.createSpace(MemorySpace.sharedSpace("family", "Family"));
        store.createSpace(MemorySpace.sharedSpace("work", "Work Team"));
        store.addMember(new SpaceMembership("alice", "alice-priv", Set.of(), T0, null));
        store.addMember(new SpaceMembership("alice", "family", Set.of(), T0, null));
        store.addMember(new SpaceMembership("alice", "work", Set.of(), T0, null));
        var spaces = store.spacesFor("alice", T1);
        assertThat(spaces).hasSize(3);
        assertThat(spaces).extracting(MemorySpace::id)
            .containsExactlyInAnyOrder("alice-priv", "family", "work");
    }

    @Test
    void revokedMemberHistoricalQuery() {
        MemorySpace space = MemorySpace.sharedSpace("team", "Dev Team");
        store.createSpace(space);
        store.addMember(new SpaceMembership("alice", "team", Set.of("member"), T0, null));
        store.revokeMember("alice", "team", T2);
        assertThat(store.spacesFor("alice", T3)).isEmpty();
        assertThat(store.spacesFor("alice", T1)).hasSize(1);
        assertThat(store.membersOf("team", T1)).hasSize(1);
        assertThat(store.membersOf("team", T3)).isEmpty();
    }
}
```

- [ ] **Step 5: Write InMemorySpaceMembershipStore test runner**

Create `memory-space-inmem/src/test/java/io/casehub/neocortex/memory/space/inmem/InMemorySpaceMembershipStoreTest.java`:

```java
package io.casehub.neocortex.memory.space.inmem;

import io.casehub.neocortex.memory.space.SpaceMembershipStore;
import io.casehub.neocortex.memory.space.testing.SpaceMembershipStoreContractTest;

class InMemorySpaceMembershipStoreTest extends SpaceMembershipStoreContractTest {

    @Override
    protected SpaceMembershipStore createStore() {
        return new InMemorySpaceMembershipStore();
    }
}
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-space-inmem`
Expected: compilation failure — InMemorySpaceMembershipStore not yet created.

- [ ] **Step 7: Implement InMemorySpaceMembershipStore**

Create `memory-space-inmem/src/main/java/io/casehub/neocortex/memory/space/inmem/InMemorySpaceMembershipStore.java`:

```java
package io.casehub.neocortex.memory.space.inmem;

import io.casehub.neocortex.memory.space.MemorySpace;
import io.casehub.neocortex.memory.space.SpaceMembership;
import io.casehub.neocortex.memory.space.SpaceMembershipStore;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;

@Alternative
@Priority(2)
@ApplicationScoped
public class InMemorySpaceMembershipStore implements SpaceMembershipStore {

    private final ConcurrentHashMap<String, MemorySpace> spaces = new ConcurrentHashMap<>();
    private final CopyOnWriteArrayList<MutableMembership> memberships = new CopyOnWriteArrayList<>();

    @Override
    public void createSpace(MemorySpace space) {
        spaces.put(space.id(), space);
    }

    @Override
    public Optional<MemorySpace> getSpace(String spaceId) {
        return Optional.ofNullable(spaces.get(spaceId));
    }

    @Override
    public void addMember(SpaceMembership membership) {
        memberships.add(new MutableMembership(membership));
    }

    @Override
    public void revokeMember(String agentId, String spaceId, Instant revokedAt) {
        for (MutableMembership m : memberships) {
            if (m.agentId.equals(agentId) && m.spaceId.equals(spaceId) && m.validUntil == null) {
                m.validUntil = revokedAt;
            }
        }
    }

    @Override
    public List<MemorySpace> spacesFor(String agentId, Instant asOf) {
        return memberships.stream()
            .filter(m -> m.agentId.equals(agentId))
            .filter(m -> isActiveAt(m, asOf))
            .map(m -> spaces.get(m.spaceId))
            .filter(s -> s != null)
            .toList();
    }

    @Override
    public List<SpaceMembership> membersOf(String spaceId, Instant asOf) {
        return memberships.stream()
            .filter(m -> m.spaceId.equals(spaceId))
            .filter(m -> isActiveAt(m, asOf))
            .map(MutableMembership::toRecord)
            .toList();
    }

    private boolean isActiveAt(MutableMembership m, Instant asOf) {
        if (asOf.isBefore(m.validFrom)) return false;
        return m.validUntil == null || asOf.isBefore(m.validUntil);
    }

    private static class MutableMembership {
        final String agentId;
        final String spaceId;
        final java.util.Set<String> roles;
        final Instant validFrom;
        volatile Instant validUntil;

        MutableMembership(SpaceMembership source) {
            this.agentId = source.agentId();
            this.spaceId = source.spaceId();
            this.roles = source.roles();
            this.validFrom = source.validFrom();
            this.validUntil = source.validUntil();
        }

        SpaceMembership toRecord() {
            return new SpaceMembership(agentId, spaceId, roles, validFrom, validUntil);
        }
    }
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-space-testing,memory-space-inmem`
Expected: 10 contract tests PASS.

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-space-testing/ memory-space-inmem/ pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory-space): contract tests + InMemorySpaceMembershipStore Refs #230"
```

---

## Batch 3: CDI wiring + SQLite backend (memory-space + memory-space-sqlite)

### Task 3: Create memory-space CDI module with NoOpSpaceMembershipStore

**Files:**
- Create: `memory-space/pom.xml`
- Create: `memory-space/src/main/java/io/casehub/neocortex/memory/space/runtime/NoOpSpaceMembershipStore.java`
- Create: `memory-space/src/test/java/io/casehub/neocortex/memory/space/runtime/NoOpSpaceMembershipStoreTest.java`
- Modify: `pom.xml` (parent — add module + dependencyManagement)

**Interfaces:**
- Consumes: `SpaceMembershipStore`, `MemorySpace` from Task 1
- Produces: `NoOpSpaceMembershipStore` @DefaultBean — singleton private space per agentId

- [ ] **Step 1: Create memory-space pom.xml**

Use `ide_create_file` to create `memory-space/pom.xml`:

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
  <artifactId>casehub-neocortex-memory-space</artifactId>
  <name>CaseHub Neocortex - Memory Space CDI</name>
  <description>NoOp @DefaultBean for SpaceMembershipStore — graceful degradation for single-agent apps.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-memory-space-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
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

- [ ] **Step 2: Register module in parent pom.xml**

Add `<module>memory-space</module>` to `<modules>` (after `memory-space-api`).

Add to `<dependencyManagement>`:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-space</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Write NoOp test**

Create `memory-space/src/test/java/io/casehub/neocortex/memory/space/runtime/NoOpSpaceMembershipStoreTest.java`:

```java
package io.casehub.neocortex.memory.space.runtime;

import io.casehub.neocortex.memory.space.SpaceType;
import org.junit.jupiter.api.Test;

import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;

class NoOpSpaceMembershipStoreTest {

    private final NoOpSpaceMembershipStore store = new NoOpSpaceMembershipStore();

    @Test
    void spacesForReturnsSingletonPrivateSpace() {
        var spaces = store.spacesFor("alice", Instant.now());
        assertThat(spaces).hasSize(1);
        assertThat(spaces.getFirst().id()).isEqualTo("alice");
        assertThat(spaces.getFirst().type()).isEqualTo(SpaceType.PRIVATE);
        assertThat(spaces.getFirst().name()).isEqualTo("alice");
        assertThat(spaces.getFirst().ownerId()).isEqualTo("alice");
    }

    @Test
    void getSpaceReturnsEmpty() {
        assertThat(store.getSpace("any")).isEmpty();
    }

    @Test
    void membersOfReturnsEmpty() {
        assertThat(store.membersOf("any", Instant.now())).isEmpty();
    }
}
```

- [ ] **Step 4: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-space`
Expected: compilation failure — NoOpSpaceMembershipStore not yet created.

- [ ] **Step 5: Implement NoOpSpaceMembershipStore**

Create `memory-space/src/main/java/io/casehub/neocortex/memory/space/runtime/NoOpSpaceMembershipStore.java`:

```java
package io.casehub.neocortex.memory.space.runtime;

import io.casehub.neocortex.memory.space.MemorySpace;
import io.casehub.neocortex.memory.space.SpaceMembership;
import io.casehub.neocortex.memory.space.SpaceMembershipStore;
import io.quarkus.arc.DefaultBean;
import jakarta.enterprise.context.ApplicationScoped;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

@DefaultBean
@ApplicationScoped
public class NoOpSpaceMembershipStore implements SpaceMembershipStore {

    @Override
    public void createSpace(MemorySpace space) {}

    @Override
    public Optional<MemorySpace> getSpace(String spaceId) {
        return Optional.empty();
    }

    @Override
    public void addMember(SpaceMembership membership) {}

    @Override
    public void revokeMember(String agentId, String spaceId, Instant revokedAt) {}

    @Override
    public List<MemorySpace> spacesFor(String agentId, Instant asOf) {
        return List.of(MemorySpace.privateSpace(agentId, agentId, agentId));
    }

    @Override
    public List<SpaceMembership> membersOf(String spaceId, Instant asOf) {
        return List.of();
    }
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-space`
Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-space/ pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory-space): NoOpSpaceMembershipStore @DefaultBean Refs #230"
```

### Task 4: Create memory-space-sqlite with SqliteSpaceMembershipStore

**Files:**
- Create: `memory-space-sqlite/pom.xml`
- Create: `memory-space-sqlite/src/main/resources/db/memory-space-sqlite/migration/V1__space_membership_schema.sql`
- Create: `memory-space-sqlite/src/main/java/io/casehub/neocortex/memory/space/sqlite/SqliteSpaceMembershipStore.java`
- Create: `memory-space-sqlite/src/test/java/io/casehub/neocortex/memory/space/sqlite/SqliteSpaceMembershipStoreTest.java`
- Modify: `pom.xml` (parent — add module + dependencyManagement)

**Interfaces:**
- Consumes: `SpaceMembershipStore`, `MemorySpace`, `SpaceMembership` from Task 1
- Consumes: `SpaceMembershipStoreContractTest` from Task 2
- Produces: `SqliteSpaceMembershipStore` @Alternative @Priority(1)

- [ ] **Step 1: Create memory-space-sqlite pom.xml**

Use `ide_create_file` to create `memory-space-sqlite/pom.xml`:

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
    </parent>
    <artifactId>casehub-neocortex-memory-space-sqlite</artifactId>
    <packaging>jar</packaging>
    <name>CaseHub Neocortex - Memory Space SQLite</name>
    <description>SQLite-backed SpaceMembershipStore. @Alternative @Priority(1) — displaces InMemory and
        NoOp when on classpath. HikariCP DataSource, Flyway migrations. Configure casehub.memory-space.sqlite.path.</description>
    <dependencies>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-space-api</artifactId>
            <version>${project.version}</version>
        </dependency>
        <dependency>
            <groupId>org.xerial</groupId>
            <artifactId>sqlite-jdbc</artifactId>
        </dependency>
        <dependency>
            <groupId>com.zaxxer</groupId>
            <artifactId>HikariCP</artifactId>
        </dependency>
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-core</artifactId>
        </dependency>
        <dependency>
            <groupId>io.quarkus</groupId>
            <artifactId>quarkus-arc</artifactId>
        </dependency>
        <dependency>
            <groupId>org.eclipse.microprofile.config</groupId>
            <artifactId>microprofile-config-api</artifactId>
            <scope>provided</scope>
        </dependency>
        <dependency>
            <groupId>io.casehub</groupId>
            <artifactId>casehub-neocortex-memory-space-testing</artifactId>
            <version>${project.version}</version>
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

- [ ] **Step 2: Register module in parent pom.xml**

Add `<module>memory-space-sqlite</module>` to `<modules>` (after `memory-space-inmem`).

Add to `<dependencyManagement>`:
```xml
<dependency>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neocortex-memory-space-sqlite</artifactId>
    <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Create Flyway migration**

Create `memory-space-sqlite/src/main/resources/db/memory-space-sqlite/migration/V1__space_membership_schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS memory_space (
    space_id  TEXT NOT NULL,
    type      TEXT NOT NULL,
    name      TEXT NOT NULL,
    owner_id  TEXT,
    PRIMARY KEY (space_id)
);

CREATE TABLE IF NOT EXISTS space_membership (
    agent_id    TEXT NOT NULL,
    space_id    TEXT NOT NULL,
    roles       TEXT NOT NULL DEFAULT '[]',
    valid_from  TEXT NOT NULL,
    valid_until TEXT,
    PRIMARY KEY (agent_id, space_id, valid_from)
);

CREATE INDEX IF NOT EXISTS space_membership_agent_idx
    ON space_membership (agent_id);

CREATE INDEX IF NOT EXISTS space_membership_space_idx
    ON space_membership (space_id);
```

- [ ] **Step 4: Write SqliteSpaceMembershipStore test runner**

Create `memory-space-sqlite/src/test/java/io/casehub/neocortex/memory/space/sqlite/SqliteSpaceMembershipStoreTest.java`:

```java
package io.casehub.neocortex.memory.space.sqlite;

import io.casehub.neocortex.memory.space.SpaceMembershipStore;
import io.casehub.neocortex.memory.space.testing.SpaceMembershipStoreContractTest;

class SqliteSpaceMembershipStoreTest extends SpaceMembershipStoreContractTest {

    @Override
    protected SpaceMembershipStore createStore() {
        SqliteSpaceMembershipStore store = new SqliteSpaceMembershipStore();
        store.path = ":memory:";
        store.maxPoolSize = 1;
        store.busyTimeoutMs = 5000;
        store.init();
        return store;
    }
}
```

- [ ] **Step 5: Run test to verify it fails**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-space-sqlite`
Expected: compilation failure — SqliteSpaceMembershipStore not yet created.

- [ ] **Step 6: Implement SqliteSpaceMembershipStore**

Create `memory-space-sqlite/src/main/java/io/casehub/neocortex/memory/space/sqlite/SqliteSpaceMembershipStore.java`:

```java
package io.casehub.neocortex.memory.space.sqlite;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import io.casehub.neocortex.memory.space.MemorySpace;
import io.casehub.neocortex.memory.space.SpaceMembership;
import io.casehub.neocortex.memory.space.SpaceMembershipStore;
import io.casehub.neocortex.memory.space.SpaceType;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;
import org.eclipse.microprofile.config.inject.ConfigProperty;
import org.flywaydb.core.Flyway;
import org.sqlite.SQLiteConfig;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;

@Alternative
@Priority(1)
@ApplicationScoped
public class SqliteSpaceMembershipStore implements SpaceMembershipStore {

    @ConfigProperty(name = "casehub.memory-space.sqlite.path")
    String path;

    @ConfigProperty(name = "casehub.memory-space.sqlite.pool.max-size", defaultValue = "5")
    int maxPoolSize;

    @ConfigProperty(name = "casehub.memory-space.sqlite.busy-timeout-ms", defaultValue = "5000")
    int busyTimeoutMs;

    private HikariDataSource dataSource;

    @PostConstruct
    void init() {
        boolean isMemory = ":memory:".equals(path) || path.isBlank();
        int effectivePoolSize = isMemory ? 1 : maxPoolSize;

        SQLiteConfig sqLiteConfig = new SQLiteConfig();
        if (!isMemory) {
            sqLiteConfig.setJournalMode(SQLiteConfig.JournalMode.WAL);
        }
        sqLiteConfig.setSynchronous(SQLiteConfig.SynchronousMode.NORMAL);
        sqLiteConfig.setBusyTimeout(busyTimeoutMs);

        org.sqlite.SQLiteDataSource sqLiteDataSource = new org.sqlite.SQLiteDataSource(sqLiteConfig);
        sqLiteDataSource.setUrl("jdbc:sqlite:" + path);

        HikariConfig hikari = new HikariConfig();
        hikari.setDataSource(sqLiteDataSource);
        hikari.setMaximumPoolSize(effectivePoolSize);
        hikari.setMinimumIdle(1);

        dataSource = new HikariDataSource(hikari);

        Flyway.configure()
            .dataSource(dataSource)
            .locations("classpath:db/memory-space-sqlite/migration")
            .load()
            .migrate();
    }

    @PreDestroy
    void shutdown() {
        if (dataSource != null) dataSource.close();
    }

    @Override
    public void createSpace(MemorySpace space) {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                 "INSERT INTO memory_space (space_id, type, name, owner_id) VALUES (?, ?, ?, ?)")) {
            ps.setString(1, space.id());
            ps.setString(2, space.type().name());
            ps.setString(3, space.name());
            ps.setString(4, space.ownerId());
            ps.executeUpdate();
        } catch (SQLException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public Optional<MemorySpace> getSpace(String spaceId) {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                 "SELECT space_id, type, name, owner_id FROM memory_space WHERE space_id = ?")) {
            ps.setString(1, spaceId);
            try (ResultSet rs = ps.executeQuery()) {
                if (!rs.next()) return Optional.empty();
                return Optional.of(new MemorySpace(
                    rs.getString("space_id"),
                    SpaceType.valueOf(rs.getString("type")),
                    rs.getString("name"),
                    rs.getString("owner_id")
                ));
            }
        } catch (SQLException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public void addMember(SpaceMembership membership) {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                 "INSERT INTO space_membership (agent_id, space_id, roles, valid_from, valid_until) VALUES (?, ?, ?, ?, ?)")) {
            ps.setString(1, membership.agentId());
            ps.setString(2, membership.spaceId());
            ps.setString(3, rolesToJson(membership.roles()));
            ps.setString(4, membership.validFrom().toString());
            ps.setString(5, membership.validUntil() == null ? null : membership.validUntil().toString());
            ps.executeUpdate();
        } catch (SQLException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public void revokeMember(String agentId, String spaceId, Instant revokedAt) {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                 "UPDATE space_membership SET valid_until = ? WHERE agent_id = ? AND space_id = ? AND valid_until IS NULL")) {
            ps.setString(1, revokedAt.toString());
            ps.setString(2, agentId);
            ps.setString(3, spaceId);
            ps.executeUpdate();
        } catch (SQLException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public List<MemorySpace> spacesFor(String agentId, Instant asOf) {
        String sql = "SELECT s.space_id, s.type, s.name, s.owner_id FROM space_membership m "
            + "JOIN memory_space s ON m.space_id = s.space_id "
            + "WHERE m.agent_id = ? AND m.valid_from <= ? AND (m.valid_until IS NULL OR m.valid_until > ?)";
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            String ts = asOf.toString();
            ps.setString(1, agentId);
            ps.setString(2, ts);
            ps.setString(3, ts);
            List<MemorySpace> result = new ArrayList<>();
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    result.add(new MemorySpace(
                        rs.getString("space_id"),
                        SpaceType.valueOf(rs.getString("type")),
                        rs.getString("name"),
                        rs.getString("owner_id")
                    ));
                }
            }
            return result;
        } catch (SQLException e) {
            throw new RuntimeException(e);
        }
    }

    @Override
    public List<SpaceMembership> membersOf(String spaceId, Instant asOf) {
        String sql = "SELECT agent_id, space_id, roles, valid_from, valid_until FROM space_membership "
            + "WHERE space_id = ? AND valid_from <= ? AND (valid_until IS NULL OR valid_until > ?)";
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            String ts = asOf.toString();
            ps.setString(1, spaceId);
            ps.setString(2, ts);
            ps.setString(3, ts);
            List<SpaceMembership> result = new ArrayList<>();
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    result.add(new SpaceMembership(
                        rs.getString("agent_id"),
                        rs.getString("space_id"),
                        rolesFromJson(rs.getString("roles")),
                        Instant.parse(rs.getString("valid_from")),
                        rs.getString("valid_until") == null ? null : Instant.parse(rs.getString("valid_until"))
                    ));
                }
            }
            return result;
        } catch (SQLException e) {
            throw new RuntimeException(e);
        }
    }

    private String rolesToJson(Set<String> roles) {
        if (roles.isEmpty()) return "[]";
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (String role : roles) {
            if (!first) sb.append(",");
            sb.append("\"").append(role.replace("\"", "\\\"")).append("\"");
            first = false;
        }
        sb.append("]");
        return sb.toString();
    }

    private Set<String> rolesFromJson(String json) {
        if (json == null || json.equals("[]")) return Set.of();
        String inner = json.substring(1, json.length() - 1);
        Set<String> result = new LinkedHashSet<>();
        for (String part : inner.split(",")) {
            String trimmed = part.trim();
            if (trimmed.startsWith("\"") && trimmed.endsWith("\"")) {
                result.add(trimmed.substring(1, trimmed.length() - 1));
            }
        }
        return Set.copyOf(result);
    }
}
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl memory-space-sqlite`
Expected: 10 contract tests PASS.

- [ ] **Step 8: Run full build to verify everything compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS. All modules compile, all tests pass.

- [ ] **Step 9: Commit**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add memory-space-sqlite/ pom.xml
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "feat(memory-space-sqlite): SqliteSpaceMembershipStore + Flyway migration Refs #230"
```

- [ ] **Step 10: Update CLAUDE.md module structure and coordinates**

Add memory-space modules to the Module Structure section and Maven Coordinates table in `CLAUDE.md`.

Module structure additions (after `mindmap-intelligence/`):
```
memory-space-api/       — MemorySpace, SpaceType, Visibility, SpaceMembership, SpaceMembershipStore SPI
                          (zero deps, tier-0)
memory-space/           — NoOpSpaceMembershipStore @DefaultBean (graceful degradation)
memory-space-testing/   — SpaceMembershipStoreContractTest abstract base (10 tests)
memory-space-inmem/     — InMemorySpaceMembershipStore @Alternative @Priority(2) — tests
memory-space-sqlite/    — SqliteSpaceMembershipStore @Alternative @Priority(1) — production
                          (HikariCP WAL + Flyway)
```

Maven Coordinates additions:
```
| Memory Space API | `casehub-neocortex-memory-space-api` |
| Memory Space CDI | `casehub-neocortex-memory-space` |
| Memory Space testing | `casehub-neocortex-memory-space-testing` |
| Memory Space In-Memory | `casehub-neocortex-memory-space-inmem` |
| Memory Space SQLite | `casehub-neocortex-memory-space-sqlite` |
| Root Java package (memory-space) | `io.casehub.neocortex.memory.space` |
```

- [ ] **Step 11: Commit CLAUDE.md update**

```bash
git -C /Users/mdproctor/claude/casehub/neocortex add CLAUDE.md
git -C /Users/mdproctor/claude/casehub/neocortex commit -m "docs: add memory-space modules to CLAUDE.md Refs #230"
```

---

## References

- `specs/issue-253-cognitive-rearchitecture/2026-08-31-memory-space-model-design.md` — design spec
- `cognitive-api/pom.xml` — zero-dep tier-0 module pattern
- `mindmap/src/main/java/.../NoOpMindMapStore.java` — @DefaultBean graceful degradation pattern
- `mindmap-inmem/src/main/java/.../InMemoryMindMapStore.java` — @Alternative @Priority(2) pattern
- `mindmap-sqlite/src/main/java/.../SqliteMindMapStore.java` — SQLite + HikariCP + Flyway pattern
- `mindmap-testing/src/main/java/.../MindMapStoreContractTest.java` — contract test base pattern
- `mindmap-inmem/src/test/java/.../InMemoryMindMapStoreTest.java` — contract test runner pattern
- `mindmap-sqlite/src/test/java/.../SqliteMindMapStoreTest.java` — SQLite test with :memory: pattern
- GitHub #230 — focal issue
- GitHub #253 — parent branch issue
