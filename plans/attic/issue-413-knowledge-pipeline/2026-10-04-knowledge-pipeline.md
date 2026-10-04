# Knowledge Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #413 — feat: Phase 2 — Knowledge pipeline + LocationPlatform integration
**Issue group:** #413

**Goal:** Build a Tile38-backed knowledge pipeline that fetches from LocationPlatform providers, caches with spatial indexing, resolves entity identity across sources, orchestrates multi-session research projects, and promotes entities to MindMap.

**Architecture:** Two new modules (`knowledge-pipeline-api`, `knowledge-pipeline`). The API module defines SPIs and value types with zero CDI. The runtime module wires Tile38 (spatial cache), SQLite (dedup index, entity metadata, query cache, research sessions), and MindMap (promotion). Entity resolution uses spatial blocking via Tile38 NEARBY + domain-specific PlaceMatcher. Research lifecycle stores workflow state in SQLite, knowledge in MindMap RESEARCH_AREA subgraphs.

**Tech Stack:** Java 21, Quarkus 3.32.2, Tile38 1.30.0+ (Redis RESP via Jedis), SQLite (via sqlite-support), MindMap SPI, LocationPlatform SPI (connectors)

## Global Constraints

- Java 21 source level, Java 26 JVM
- Parent POM: `casehub-neocortex-parent` version `0.2-SNAPSHOT`
- Maven build: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
- Use `mvn` not `./mvnw`
- Package root: `io.casehub.neocortex.knowledge`
- Every commit references #413: `Refs #413` or `Closes #413`
- Tile38 minimum version 1.30.0 (expression WHERE + string FIELD support)
- Tests use JUnit 5 + AssertJ
- IntelliJ MCP for all code navigation and structural editing

---

## Batch 1: API Value Types and SPIs

### Task 1: Create knowledge-pipeline-api module with value types

**Files:**
- Create: `knowledge-pipeline-api/pom.xml`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/KnowledgeQuery.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/NormalizedQuery.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/CachedEntity.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/CacheFilter.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/MatchResult.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/MatchTier.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/PromotionRequest.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/PromotionResult.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/ResearchState.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/ResearchSession.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/SpatialBucket.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/BoundingBox.java`
- Modify: `pom.xml` (add `<module>knowledge-pipeline-api</module>`)
- Test: `knowledge-pipeline-api/src/test/java/io/casehub/neocortex/knowledge/KnowledgeQueryTest.java`
- Test: `knowledge-pipeline-api/src/test/java/io/casehub/neocortex/knowledge/SpatialBucketTest.java`

**Interfaces:**
- Consumes: `io.casehub.connectors.location.model.Coordinates` (from location-spi)
- Produces: `KnowledgeQuery` (sealed: TextSearch, NearbySearch, CategorySearch), `NormalizedQuery`, `CachedEntity`, `MatchResult`, `MatchTier`, `PromotionRequest`, `PromotionResult`, `ResearchState`, `ResearchSession`, `CacheFilter`, `SpatialBucket`, `BoundingBox`

- [ ] **Step 1: Create module directory and POM**

```xml
<!-- knowledge-pipeline-api/pom.xml -->
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
  <artifactId>casehub-neocortex-knowledge-pipeline-api</artifactId>
  <name>CaseHub Neocortex - Knowledge Pipeline API</name>
  <description>Knowledge pipeline SPIs and value types — cache, resolution, research lifecycle. Tier 1 pure Java.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-connectors-location-spi</artifactId>
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

Add `<module>knowledge-pipeline-api</module>` to the parent POM modules list, after `mindmap-intelligence`.

- [ ] **Step 2: Create KnowledgeQuery sealed hierarchy**

```java
package io.casehub.neocortex.knowledge;

import io.casehub.connectors.location.model.Coordinates;
import java.util.Objects;

public sealed interface KnowledgeQuery {

    record TextSearch(String query) implements KnowledgeQuery {
        public TextSearch { Objects.requireNonNull(query); }
    }

    record NearbySearch(Coordinates center, int radiusMeters,
                        CacheFilter filters) implements KnowledgeQuery {
        public NearbySearch {
            Objects.requireNonNull(center);
            if (radiusMeters <= 0) throw new IllegalArgumentException("radiusMeters must be positive");
        }
    }

    record CategorySearch(String category, Coordinates center,
                          int radiusMeters) implements KnowledgeQuery {
        public CategorySearch {
            Objects.requireNonNull(category);
            Objects.requireNonNull(center);
            if (radiusMeters <= 0) throw new IllegalArgumentException("radiusMeters must be positive");
        }
    }
}
```

- [ ] **Step 3: Create remaining value types**

`CacheFilter`:
```java
package io.casehub.neocortex.knowledge;

public record CacheFilter(String category, String priceLevel,
                           Double minRating, Integer maxRadius) {
    public static CacheFilter none() {
        return new CacheFilter(null, null, null, null);
    }
}
```

`MatchTier` enum:
```java
package io.casehub.neocortex.knowledge;

public enum MatchTier {
    DEFINITIVE, HIGH, MEDIUM, LOW;

    public static MatchTier fromConfidence(double confidence) {
        if (confidence >= 0.95) return DEFINITIVE;
        if (confidence >= 0.8) return HIGH;
        if (confidence >= 0.6) return MEDIUM;
        return LOW;
    }
}
```

`MatchResult`:
```java
package io.casehub.neocortex.knowledge;

import java.util.List;

public record MatchResult(double confidence, List<String> matchedSignals, MatchTier tier) {
    public MatchResult {
        if (confidence < 0.0 || confidence > 1.0)
            throw new IllegalArgumentException("confidence must be in [0,1]");
        matchedSignals = List.copyOf(matchedSignals);
    }
    public static MatchResult noMatch() {
        return new MatchResult(0.0, List.of(), MatchTier.LOW);
    }
}
```

`CachedEntity`:
```java
package io.casehub.neocortex.knowledge;

import io.casehub.connectors.location.model.Coordinates;
import java.time.Instant;
import java.util.Map;
import java.util.Objects;
import java.util.Set;

public record CachedEntity(
    String id,
    String name,
    Coordinates coordinates,
    String category,
    String source,
    String externalId,
    Map<String, String> properties,
    Instant fetchedAt,
    Instant expiresAt,
    Set<String> sessionIds,
    boolean hasDetail
) {
    public CachedEntity {
        Objects.requireNonNull(id);
        Objects.requireNonNull(name);
        Objects.requireNonNull(source);
        Objects.requireNonNull(externalId);
        properties = properties == null ? Map.of() : Map.copyOf(properties);
        sessionIds = sessionIds == null ? Set.of() : Set.copyOf(sessionIds);
    }
}
```

`PromotionRequest`, `PromotionResult`:
```java
package io.casehub.neocortex.knowledge;

public record PromotionRequest(String cacheEntityId, String tenantId,
                                String researchSessionId) {}

public record PromotionResult(String mindMapNodeId, boolean created) {}
```

`ResearchState` enum:
```java
package io.casehub.neocortex.knowledge;

public enum ResearchState { ACTIVE, PAUSED, COMPLETED }
```

`ResearchSession`:
```java
package io.casehub.neocortex.knowledge;

import java.time.Instant;

public record ResearchSession(
    String id, String name, String criteria, String mindMapSubgraphId,
    ResearchState state, String tenantId, Instant createdAt, Instant lastActive
) {}
```

`BoundingBox`:
```java
package io.casehub.neocortex.knowledge;

public record BoundingBox(double minLat, double minLng,
                           double maxLat, double maxLng) {
    public BoundingBox {
        if (minLat > maxLat) throw new IllegalArgumentException("minLat > maxLat");
        if (minLng > maxLng) throw new IllegalArgumentException("minLng > maxLng");
    }
}
```

`SpatialBucket`:
```java
package io.casehub.neocortex.knowledge;

public final class SpatialBucket {
    private SpatialBucket() {}

    private static final String BASE32 = "0123456789bcdefghjkmnpqrstuvwxyz";

    public static String encode(double lat, double lng, int precision) {
        double latMin = -90, latMax = 90;
        double lngMin = -180, lngMax = 180;
        boolean isLng = true;
        int bit = 0;
        int ch = 0;
        StringBuilder hash = new StringBuilder(precision);
        while (hash.length() < precision) {
            double mid;
            if (isLng) {
                mid = (lngMin + lngMax) / 2;
                if (lng >= mid) { ch |= (1 << (4 - bit)); lngMin = mid; }
                else { lngMax = mid; }
            } else {
                mid = (latMin + latMax) / 2;
                if (lat >= mid) { ch |= (1 << (4 - bit)); latMin = mid; }
                else { latMax = mid; }
            }
            isLng = !isLng;
            if (bit < 4) { bit++; }
            else { hash.append(BASE32.charAt(ch)); bit = 0; ch = 0; }
        }
        return hash.toString();
    }
}
```

`NormalizedQuery`:
```java
package io.casehub.neocortex.knowledge;

import java.util.Objects;

public record NormalizedQuery(KnowledgeQuery query, String cacheKey) {
    public NormalizedQuery {
        Objects.requireNonNull(query);
        Objects.requireNonNull(cacheKey);
    }
}
```

- [ ] **Step 4: Write tests for KnowledgeQuery and SpatialBucket**

```java
package io.casehub.neocortex.knowledge;

import io.casehub.connectors.location.model.Coordinates;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class KnowledgeQueryTest {
    @Test void textSearchRequiresQuery() {
        assertThatThrownBy(() -> new KnowledgeQuery.TextSearch(null))
            .isInstanceOf(NullPointerException.class);
    }
    @Test void nearbySearchRequiresPositiveRadius() {
        assertThatThrownBy(() -> new KnowledgeQuery.NearbySearch(
                new Coordinates(51.5, -0.1), 0, CacheFilter.none()))
            .isInstanceOf(IllegalArgumentException.class);
    }
    @Test void categorySearchCreatesValidQuery() {
        var q = new KnowledgeQuery.CategorySearch("italian", new Coordinates(51.5, -0.1), 1000);
        assertThat(q.category()).isEqualTo("italian");
        assertThat(q.radiusMeters()).isEqualTo(1000);
    }
    @Test void sealedHierarchyPermitsPatternMatch() {
        KnowledgeQuery q = new KnowledgeQuery.TextSearch("pizza");
        String result = switch (q) {
            case KnowledgeQuery.TextSearch t -> "text:" + t.query();
            case KnowledgeQuery.NearbySearch n -> "nearby";
            case KnowledgeQuery.CategorySearch c -> "cat:" + c.category();
        };
        assertThat(result).isEqualTo("text:pizza");
    }
}
```

```java
package io.casehub.neocortex.knowledge;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class SpatialBucketTest {
    @Test void encodesKingsCrossToExpectedGeohash() {
        String hash = SpatialBucket.encode(51.5317, -0.1240, 6);
        assertThat(hash).hasSize(6);
    }
    @Test void nearbyCoordinatesProduceSameHash() {
        String h1 = SpatialBucket.encode(51.5317, -0.1240, 6);
        String h2 = SpatialBucket.encode(51.5320, -0.1235, 6);
        assertThat(h1).isEqualTo(h2);
    }
    @Test void distantCoordinatesProduceDifferentHash() {
        String h1 = SpatialBucket.encode(51.5317, -0.1240, 6);
        String h2 = SpatialBucket.encode(55.9533, -3.1883, 6);
        assertThat(h1).isNotEqualTo(h2);
    }
}
```

- [ ] **Step 5: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl knowledge-pipeline-api`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add knowledge-pipeline-api/ pom.xml
git commit -m "feat(#413): add knowledge-pipeline-api module — value types and sealed KnowledgeQuery Refs #413"
```

### Task 2: Add SPIs to knowledge-pipeline-api

**Files:**
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/SpatialCacheStore.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/EntityMatcher.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/QueryNormalizer.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/KnowledgePipelineService.java`
- Create: `knowledge-pipeline-api/src/main/java/io/casehub/neocortex/knowledge/ResearchSessionService.java`

**Interfaces:**
- Consumes: `KnowledgeQuery`, `NormalizedQuery`, `CachedEntity`, `CacheFilter`, `BoundingBox`, `MatchResult`, `PromotionRequest`, `PromotionResult`, `ResearchSession`, `ResearchState`, `Coordinates` (from Task 1)
- Produces: `SpatialCacheStore`, `EntityMatcher<T>`, `QueryNormalizer`, `KnowledgePipelineService`, `ResearchSessionService`

- [ ] **Step 1: Write SpatialCacheStore SPI**

```java
package io.casehub.neocortex.knowledge;

import io.casehub.connectors.location.model.Coordinates;
import java.time.Instant;
import java.util.List;

public interface SpatialCacheStore {
    void set(CachedEntity entity, String tenantId);
    CachedEntity get(String entityId, String tenantId);
    List<CachedEntity> nearby(Coordinates center, int radiusMeters,
                               CacheFilter filters, String tenantId);
    List<CachedEntity> within(BoundingBox box, CacheFilter filters, String tenantId);
    void remove(String entityId, String tenantId);
    void expire(String entityId, Instant expiresAt, String tenantId);
}
```

- [ ] **Step 2: Write EntityMatcher SPI**

```java
package io.casehub.neocortex.knowledge;

@FunctionalInterface
public interface EntityMatcher<T> {
    MatchResult match(T candidate, T existing);
}
```

- [ ] **Step 3: Write QueryNormalizer SPI**

```java
package io.casehub.neocortex.knowledge;

@FunctionalInterface
public interface QueryNormalizer {
    NormalizedQuery normalize(String naturalLanguage);
}
```

- [ ] **Step 4: Write KnowledgePipelineService SPI**

```java
package io.casehub.neocortex.knowledge;

import java.util.List;

public interface KnowledgePipelineService {
    List<CachedEntity> search(KnowledgeQuery query, String tenantId);
    List<CachedEntity> search(KnowledgeQuery query, String tenantId,
                               String researchSessionId);
    PromotionResult promote(PromotionRequest request);
    void refreshStale(String tenantId);
}
```

- [ ] **Step 5: Write ResearchSessionService SPI**

```java
package io.casehub.neocortex.knowledge;

import java.util.List;

public interface ResearchSessionService {
    ResearchSession create(String name, String criteria, String tenantId);
    void pause(String sessionId);
    void resume(String sessionId);
    void complete(String sessionId);
    List<ResearchSession> listActive(String tenantId);
    ResearchSession get(String sessionId);
}
```

- [ ] **Step 6: Build to verify compilation**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -pl knowledge-pipeline-api -DskipTests`
Expected: BUILD SUCCESS

- [ ] **Step 7: Commit**

```bash
git add knowledge-pipeline-api/
git commit -m "feat(#413): add knowledge-pipeline SPIs — SpatialCacheStore, EntityMatcher, ResearchSessionService Refs #413"
```

---

## Batch 2: SQLite Stores (Dedup Index, Entity Metadata, Query Cache, Research Sessions)

### Task 3: Create knowledge-pipeline module with SQLite stores

**Files:**
- Create: `knowledge-pipeline/pom.xml`
- Create: `knowledge-pipeline/src/main/resources/db/knowledge-pipeline/V1__init.sql`
- Create: `knowledge-pipeline/src/main/resources/db/knowledge-research/V1__init.sql`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/dedup/DedupIndexStore.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/EntityMetadataStore.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/QueryCacheStore.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/research/ResearchSessionStore.java`
- Modify: `pom.xml` (add `<module>knowledge-pipeline</module>`)
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/dedup/DedupIndexStoreTest.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/EntityMetadataStoreTest.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/QueryCacheStoreTest.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/research/ResearchSessionStoreTest.java`

**Interfaces:**
- Consumes: `CachedEntity`, `ResearchSession`, `ResearchState` (from Task 1)
- Produces: `DedupIndexStore.lookup(source, externalId)`, `DedupIndexStore.upsert(source, externalId, cacheEntityId)`, `DedupIndexStore.setMindMapNodeId(source, externalId, nodeId)`, `EntityMetadataStore.save(entity)`, `EntityMetadataStore.get(entityId)`, `EntityMetadataStore.getBatch(entityIds)`, `EntityMetadataStore.delete(entityId)`, `EntityMetadataStore.addSession(entityId, sessionId)`, `EntityMetadataStore.sessionsFor(entityId)`, `QueryCacheStore.lookup(cacheKey, tenantId)`, `QueryCacheStore.record(cacheKey, tenantId, entityIds, expiresAt)`, `ResearchSessionStore.insert(session)`, `ResearchSessionStore.updateState(sessionId, state)`, `ResearchSessionStore.listByState(tenantId, state)`, `ResearchSessionStore.get(sessionId)`

- [ ] **Step 1: Create module POM**

```xml
<!-- knowledge-pipeline/pom.xml -->
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
  <artifactId>casehub-neocortex-knowledge-pipeline</artifactId>
  <name>CaseHub Neocortex - Knowledge Pipeline</name>
  <description>Knowledge pipeline runtime — Tile38 spatial cache, entity resolution, research lifecycle, promotion to MindMap.</description>
  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-knowledge-pipeline-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-mindmap-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-mindmap-intelligence</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-sqlite-support</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-connectors-location-spi</artifactId>
    </dependency>
    <dependency>
      <groupId>redis.clients</groupId>
      <artifactId>jedis</artifactId>
    </dependency>
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
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

Add `<module>knowledge-pipeline</module>` to parent POM after `knowledge-pipeline-api`.

- [ ] **Step 2: Create Flyway migrations**

`knowledge-pipeline/src/main/resources/db/knowledge-pipeline/V1__init.sql`:
```sql
CREATE TABLE dedup_index (
    source          TEXT NOT NULL,
    external_id     TEXT NOT NULL,
    cache_entity_id TEXT NOT NULL,
    mindmap_node_id TEXT,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    PRIMARY KEY (source, external_id)
);

CREATE TABLE entity_metadata (
    entity_id           TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    category            TEXT,
    source              TEXT NOT NULL,
    external_id         TEXT NOT NULL,
    properties          TEXT,
    fetched_at          TEXT NOT NULL,
    detail_fetched_at   TEXT,
    has_detail          INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE entity_sessions (
    entity_id  TEXT NOT NULL,
    session_id TEXT NOT NULL,
    PRIMARY KEY (entity_id, session_id)
);
CREATE INDEX idx_entity_session ON entity_sessions(session_id);

CREATE TABLE query_cache (
    cache_key   TEXT PRIMARY KEY,
    tenant_id   TEXT NOT NULL,
    entity_ids  TEXT NOT NULL,
    answered_at TEXT NOT NULL,
    expires_at  TEXT NOT NULL
);
CREATE INDEX idx_query_tenant ON query_cache(tenant_id);
```

`knowledge-pipeline/src/main/resources/db/knowledge-research/V1__init.sql`:
```sql
CREATE TABLE research_sessions (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    tenant_id    TEXT NOT NULL,
    criteria     TEXT,
    subgraph_id  TEXT NOT NULL,
    state        TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at   TEXT NOT NULL,
    last_active  TEXT NOT NULL
);
CREATE INDEX idx_sessions_tenant_state ON research_sessions(tenant_id, state);
```

- [ ] **Step 3: Write DedupIndexStore**

```java
package io.casehub.neocortex.knowledge.dedup;

import io.casehub.neocortex.sqlite.SqliteDataSourceFactory;
import com.zaxxer.hikari.HikariDataSource;
import java.sql.*;
import java.time.Instant;
import java.util.Optional;

public class DedupIndexStore {

    private final HikariDataSource ds;

    public DedupIndexStore(String dbPath) {
        this.ds = SqliteDataSourceFactory.create(dbPath, 3, 5000);
        SqliteDataSourceFactory.migrate(ds, "classpath:db/knowledge-pipeline");
    }

    public record DedupEntry(String cacheEntityId, String mindMapNodeId,
                              Instant firstSeen, Instant lastSeen) {}

    public Optional<DedupEntry> lookup(String source, String externalId) {
        try (Connection c = ds.getConnection();
             PreparedStatement ps = c.prepareStatement(
                 "SELECT cache_entity_id, mindmap_node_id, first_seen, last_seen "
                 + "FROM dedup_index WHERE source = ? AND external_id = ?")) {
            ps.setString(1, source);
            ps.setString(2, externalId);
            ResultSet rs = ps.executeQuery();
            if (!rs.next()) return Optional.empty();
            return Optional.of(new DedupEntry(
                rs.getString("cache_entity_id"),
                rs.getString("mindmap_node_id"),
                Instant.parse(rs.getString("first_seen")),
                Instant.parse(rs.getString("last_seen"))));
        } catch (SQLException e) { throw new RuntimeException(e); }
    }

    public void upsert(String source, String externalId, String cacheEntityId) {
        String now = Instant.now().toString();
        try (Connection c = ds.getConnection();
             PreparedStatement ps = c.prepareStatement(
                 "INSERT INTO dedup_index (source, external_id, cache_entity_id, first_seen, last_seen) "
                 + "VALUES (?, ?, ?, ?, ?) "
                 + "ON CONFLICT(source, external_id) DO UPDATE SET "
                 + "cache_entity_id = excluded.cache_entity_id, last_seen = excluded.last_seen")) {
            ps.setString(1, source);
            ps.setString(2, externalId);
            ps.setString(3, cacheEntityId);
            ps.setString(4, now);
            ps.setString(5, now);
            ps.executeUpdate();
        } catch (SQLException e) { throw new RuntimeException(e); }
    }

    public void setMindMapNodeId(String source, String externalId, String nodeId) {
        try (Connection c = ds.getConnection();
             PreparedStatement ps = c.prepareStatement(
                 "UPDATE dedup_index SET mindmap_node_id = ? "
                 + "WHERE source = ? AND external_id = ?")) {
            ps.setString(1, nodeId);
            ps.setString(2, source);
            ps.setString(3, externalId);
            ps.executeUpdate();
        } catch (SQLException e) { throw new RuntimeException(e); }
    }

    public void close() { ds.close(); }
}
```

- [ ] **Step 4: Write DedupIndexStoreTest**

```java
package io.casehub.neocortex.knowledge.dedup;

import org.junit.jupiter.api.*;
import static org.assertj.core.api.Assertions.*;

class DedupIndexStoreTest {
    private DedupIndexStore store;

    @BeforeEach void setUp() { store = new DedupIndexStore(":memory:"); }
    @AfterEach void tearDown() { store.close(); }

    @Test void lookupReturnsEmptyForUnknownEntity() {
        assertThat(store.lookup("google", "xyz")).isEmpty();
    }

    @Test void upsertAndLookupRoundTrips() {
        store.upsert("google", "ChIJ123", "cache-1");
        var entry = store.lookup("google", "ChIJ123");
        assertThat(entry).isPresent();
        assertThat(entry.get().cacheEntityId()).isEqualTo("cache-1");
        assertThat(entry.get().mindMapNodeId()).isNull();
    }

    @Test void upsertUpdatesLastSeen() throws InterruptedException {
        store.upsert("google", "ChIJ123", "cache-1");
        var first = store.lookup("google", "ChIJ123").get().lastSeen();
        Thread.sleep(10);
        store.upsert("google", "ChIJ123", "cache-1");
        var second = store.lookup("google", "ChIJ123").get().lastSeen();
        assertThat(second).isAfterOrEqualTo(first);
    }

    @Test void setMindMapNodeIdUpdatesEntry() {
        store.upsert("google", "ChIJ123", "cache-1");
        store.setMindMapNodeId("google", "ChIJ123", "node-42");
        var entry = store.lookup("google", "ChIJ123").get();
        assertThat(entry.mindMapNodeId()).isEqualTo("node-42");
    }
}
```

- [ ] **Step 5: Write EntityMetadataStore, QueryCacheStore, ResearchSessionStore** (follow same pattern — SQLite via SqliteDataSourceFactory, JDBC, unit tests with `:memory:`)

Each store follows the same pattern as DedupIndexStore. EntityMetadataStore adds `save(entity)`, `get(entityId)`, `getBatch(List<String> entityIds)`, `delete(entityId)`, `addSession(entityId, sessionId)`, `sessionsFor(entityId)`. QueryCacheStore adds `lookup(cacheKey, tenantId)`, `record(cacheKey, tenantId, List<String> entityIds, Instant expiresAt)`. ResearchSessionStore adds `insert(ResearchSession)`, `updateState(sessionId, ResearchState, Instant lastActive)`, `listByState(tenantId, ResearchState)`, `get(sessionId)`.

- [ ] **Step 6: Run all tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl knowledge-pipeline`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add knowledge-pipeline/ pom.xml
git commit -m "feat(#413): add SQLite stores — dedup index, entity metadata, query cache, research sessions Refs #413"
```

---

## Batch 3: Cache Key Generation and Entity Resolution

### Task 4: CacheKeyGenerator and PlaceMatcher

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/CacheKeyGenerator.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/resolution/PlaceMatcher.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/resolution/PhoneNormalizer.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/resolution/Haversine.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/CacheKeyGeneratorTest.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/resolution/PlaceMatcherTest.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/resolution/PhoneNormalizerTest.java`

**Interfaces:**
- Consumes: `KnowledgeQuery`, `NormalizedQuery`, `SpatialBucket`, `CachedEntity`, `MatchResult`, `MatchTier`, `EntityMatcher<CachedEntity>`, `Coordinates` (from Tasks 1-2)
- Produces: `CacheKeyGenerator.generate(KnowledgeQuery, int geohashPrecision) → NormalizedQuery`, `PlaceMatcher implements EntityMatcher<CachedEntity>`, `PhoneNormalizer.normalize(String) → String`, `Haversine.distanceMeters(Coordinates, Coordinates) → double`

- [ ] **Step 1: Write CacheKeyGenerator test**

```java
package io.casehub.neocortex.knowledge.cache;

import io.casehub.connectors.location.model.Coordinates;
import io.casehub.neocortex.knowledge.CacheFilter;
import io.casehub.neocortex.knowledge.KnowledgeQuery;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class CacheKeyGeneratorTest {
    @Test void textSearchNormalizesCase() {
        var q = new KnowledgeQuery.TextSearch("Find Italian  Restaurants");
        var nq = CacheKeyGenerator.generate(q, 6);
        assertThat(nq.cacheKey()).isEqualTo("TEXT:find italian restaurants");
    }
    @Test void nearbySearchRoundsToGeohash() {
        var q1 = new KnowledgeQuery.NearbySearch(new Coordinates(51.5317, -0.1240), 1000, CacheFilter.none());
        var q2 = new KnowledgeQuery.NearbySearch(new Coordinates(51.5320, -0.1235), 1000, CacheFilter.none());
        assertThat(CacheKeyGenerator.generate(q1, 6).cacheKey())
            .isEqualTo(CacheKeyGenerator.generate(q2, 6).cacheKey());
    }
    @Test void categorySearchIncludesCategoryInKey() {
        var q = new KnowledgeQuery.CategorySearch("italian", new Coordinates(51.5, -0.1), 1000);
        var nq = CacheKeyGenerator.generate(q, 6);
        assertThat(nq.cacheKey()).startsWith("CATEGORY:italian:");
    }
}
```

- [ ] **Step 2: Implement CacheKeyGenerator**

```java
package io.casehub.neocortex.knowledge.cache;

import io.casehub.neocortex.knowledge.*;
import java.text.Normalizer;

public final class CacheKeyGenerator {
    private CacheKeyGenerator() {}

    public static NormalizedQuery generate(KnowledgeQuery query, int geohashPrecision) {
        String key = switch (query) {
            case KnowledgeQuery.TextSearch t ->
                "TEXT:" + normalizeText(t.query());
            case KnowledgeQuery.NearbySearch n ->
                "NEARBY:" + SpatialBucket.encode(n.center().lat(), n.center().lng(), geohashPrecision)
                    + ":" + n.radiusMeters();
            case KnowledgeQuery.CategorySearch c ->
                "CATEGORY:" + c.category().toLowerCase().strip()
                    + ":" + SpatialBucket.encode(c.center().lat(), c.center().lng(), geohashPrecision)
                    + ":" + c.radiusMeters();
        };
        return new NormalizedQuery(query, key);
    }

    private static String normalizeText(String text) {
        return Normalizer.normalize(text, Normalizer.Form.NFKC)
            .toLowerCase().strip().replaceAll("\\s+", " ");
    }
}
```

- [ ] **Step 3: Write Haversine and PhoneNormalizer**

```java
package io.casehub.neocortex.knowledge.resolution;

import io.casehub.connectors.location.model.Coordinates;

public final class Haversine {
    private static final double R = 6_371_000;
    private Haversine() {}

    public static double distanceMeters(Coordinates a, Coordinates b) {
        double dLat = Math.toRadians(b.lat() - a.lat());
        double dLng = Math.toRadians(b.lng() - a.lng());
        double aLat = Math.toRadians(a.lat());
        double bLat = Math.toRadians(b.lat());
        double h = Math.sin(dLat / 2) * Math.sin(dLat / 2)
                 + Math.cos(aLat) * Math.cos(bLat)
                 * Math.sin(dLng / 2) * Math.sin(dLng / 2);
        return R * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
    }
}
```

```java
package io.casehub.neocortex.knowledge.resolution;

public final class PhoneNormalizer {
    private PhoneNormalizer() {}

    public static String normalize(String phone) {
        if (phone == null || phone.isBlank()) return "";
        String digits = phone.replaceAll("[^0-9+]", "");
        if (digits.startsWith("+44")) digits = "0" + digits.substring(3);
        if (digits.startsWith("0044")) digits = "0" + digits.substring(4);
        return digits;
    }
}
```

- [ ] **Step 4: Write PlaceMatcher test**

```java
package io.casehub.neocortex.knowledge.resolution;

import io.casehub.connectors.location.model.Coordinates;
import io.casehub.neocortex.knowledge.*;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.Map;
import java.util.Set;
import static org.assertj.core.api.Assertions.*;

class PlaceMatcherTest {
    private final PlaceMatcher matcher = new PlaceMatcher();

    private CachedEntity entity(String id, String name, double lat, double lng,
                                 String source, String extId, Map<String, String> props) {
        return new CachedEntity(id, name, new Coordinates(lat, lng), "restaurant",
            source, extId, props, Instant.now(), Instant.now().plusSeconds(86400), Set.of(), false);
    }

    @Test void sameExternalIdIsDefinitive() {
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "ChIJ123", Map.of());
        var b = entity("2", "Ondine Seafood", 51.5001, -0.1001, "google", "ChIJ123", Map.of());
        var result = matcher.match(a, b);
        assertThat(result.tier()).isEqualTo(MatchTier.DEFINITIVE);
    }

    @Test void closeProximityAndSimilarNameIsHigh() {
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "g1", Map.of());
        var b = entity("2", "Ondine Restaurant", 51.50003, -0.10003, "tripadvisor", "t1", Map.of());
        var result = matcher.match(a, b);
        assertThat(result.tier()).isIn(MatchTier.HIGH, MatchTier.MEDIUM);
        assertThat(result.confidence()).isGreaterThan(0.6);
    }

    @Test void distantEntitiesAreNoMatch() {
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "g1", Map.of());
        var b = entity("2", "Ondine", 55.9, -3.1, "tripadvisor", "t1", Map.of());
        var result = matcher.match(a, b);
        assertThat(result.tier()).isEqualTo(MatchTier.LOW);
    }

    @Test void phoneMatchIsHigh() {
        var a = entity("1", "Ondine", 51.5, -0.1, "google", "g1",
            Map.of("phone", "+44 131 226 1888"));
        var b = entity("2", "Ondine Seafood", 51.50003, -0.10003, "tripadvisor", "t1",
            Map.of("phone", "0131 226 1888"));
        var result = matcher.match(a, b);
        assertThat(result.tier()).isIn(MatchTier.DEFINITIVE, MatchTier.HIGH);
    }
}
```

- [ ] **Step 5: Implement PlaceMatcher**

```java
package io.casehub.neocortex.knowledge.resolution;

import io.casehub.neocortex.knowledge.*;
import io.casehub.neocortex.mindmap.intelligence.consolidation.JaroWinkler;
import java.util.ArrayList;
import java.util.List;

public class PlaceMatcher implements EntityMatcher<CachedEntity> {

    @Override
    public MatchResult match(CachedEntity candidate, CachedEntity existing) {
        if (candidate.source().equals(existing.source())
                && candidate.externalId().equals(existing.externalId())) {
            return new MatchResult(1.0, List.of("same external ID"), MatchTier.DEFINITIVE);
        }

        List<String> signals = new ArrayList<>();
        double best = 0.0;

        if (candidate.coordinates() != null && existing.coordinates() != null) {
            double dist = Haversine.distanceMeters(candidate.coordinates(), existing.coordinates());
            double nameSim = JaroWinkler.similarity(
                candidate.name().toLowerCase(), existing.name().toLowerCase());

            if (dist < 50 && nameSim > 0.85) {
                signals.add("proximity <50m + name similarity " + String.format("%.2f", nameSim));
                best = Math.max(best, 0.9);
            } else if (dist < 200 && nameSim > 0.9) {
                signals.add("proximity <200m + name similarity " + String.format("%.2f", nameSim));
                best = Math.max(best, 0.65);
            }
        }

        String phoneA = PhoneNormalizer.normalize(candidate.properties().get("phone"));
        String phoneB = PhoneNormalizer.normalize(existing.properties().get("phone"));
        if (!phoneA.isEmpty() && phoneA.equals(phoneB)) {
            signals.add("phone match");
            best = Math.max(best, 0.85);
        }

        if (signals.isEmpty()) {
            return MatchResult.noMatch();
        }
        return new MatchResult(best, signals, MatchTier.fromConfidence(best));
    }
}
```

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl knowledge-pipeline`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add knowledge-pipeline/
git commit -m "feat(#413): add CacheKeyGenerator, PlaceMatcher, Haversine, PhoneNormalizer Refs #413"
```

---

## Batch 4: InMemory SpatialCacheStore and Entity Resolution Engine

### Task 5: InMemorySpatialCacheStore and EntityResolutionEngine

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/InMemorySpatialCacheStore.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/CacheEntityIdGenerator.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/resolution/EntityResolutionEngine.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/InMemorySpatialCacheStoreTest.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/resolution/EntityResolutionEngineTest.java`

**Interfaces:**
- Consumes: `SpatialCacheStore`, `CachedEntity`, `EntityMatcher<CachedEntity>`, `PlaceMatcher`, `DedupIndexStore`, `AttentionSignal`, `SignalCategory`, `Coordinates`, `Haversine` (from Tasks 1-4)
- Produces: `InMemorySpatialCacheStore implements SpatialCacheStore`, `CacheEntityIdGenerator.generate(source, externalId) → String`, `EntityResolutionEngine.resolve(List<CachedEntity>, SpatialCacheStore, DedupIndexStore, tenantId) → List<CachedEntity>`

- [ ] **Step 1: Write CacheEntityIdGenerator**

```java
package io.casehub.neocortex.knowledge.cache;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;

public final class CacheEntityIdGenerator {
    private CacheEntityIdGenerator() {}

    public static String generate(String source, String externalId) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] hash = md.digest((source + ":" + externalId).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash).substring(0, 32);
        } catch (NoSuchAlgorithmException e) { throw new RuntimeException(e); }
    }
}
```

- [ ] **Step 2: Write InMemorySpatialCacheStore**

In-memory implementation using `ConcurrentHashMap` + `Haversine` for NEARBY filtering. Implements `SpatialCacheStore`. Suitable for tests without Tile38.

- [ ] **Step 3: Write InMemorySpatialCacheStoreTest** — set/get/nearby/within/remove/expire operations

- [ ] **Step 4: Write EntityResolutionEngine**

Resolution engine takes a list of freshly-fetched `CachedEntity` objects, runs them through blocking (SpatialCacheStore.nearby for existing cached entities) + matching (PlaceMatcher) + decision (three-tier). Medium confidence matches emit AttentionSignal. Returns the deduplicated list.

- [ ] **Step 5: Write EntityResolutionEngineTest** — definitive merge, high merge, medium signal emission, low separate

- [ ] **Step 6: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl knowledge-pipeline`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add knowledge-pipeline/
git commit -m "feat(#413): add InMemorySpatialCacheStore, CacheEntityIdGenerator, EntityResolutionEngine Refs #413"
```

---

## Batch 5: Entity Promotion and Research Orchestrator

### Task 6: EntityPromoter — three-stage promotion to MindMap

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/promotion/EntityPromoter.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/promotion/EntityPromoterTest.java`

**Interfaces:**
- Consumes: `SpatialCacheStore.get()`, `DedupIndexStore.lookup()`, `DedupIndexStore.setMindMapNodeId()`, `MindMapStore.resolveNode()`, `MindMapStore.addNode()`, `MindMapStore.updateNode()`, `MindMapStore.listSubgraphs()`, `MindMapStore.createSubgraph()`, `MindMapStore.getSubgraph()`, `MindMapStore.addEdge()`, `NodeInput`, `NodeUpdate`, `NodeRef`, `EdgeInput`, `SubgraphTypes`, `SubgraphInput`, `PromotionRequest`, `PromotionResult`, `CachedEntity` (from Tasks 1-5)
- Produces: `EntityPromoter.promote(PromotionRequest, MindMapStore, SpatialCacheStore, DedupIndexStore) → PromotionResult`

- [ ] **Step 1: Write EntityPromoterTest**

Test three paths: (1) dedup index already has mindmap_node_id → enrich existing node, (2) resolveNode finds PLACE match → enrich, (3) no match → create new PLACE node. Also test cross-subgraph edge creation when researchSessionId is present.

- [ ] **Step 2: Implement EntityPromoter** — three-stage resolution per spec §9.1

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl knowledge-pipeline`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add knowledge-pipeline/
git commit -m "feat(#413): add EntityPromoter — three-stage promotion to MindMap Refs #413"
```

### Task 7: ResearchOrchestrator — lifecycle management

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/research/ResearchOrchestrator.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/research/ResearchOrchestratorTest.java`

**Interfaces:**
- Consumes: `ResearchSessionService`, `ResearchSessionStore`, `MindMapStore.createSubgraph()`, `MindMapStore.addNode()`, `MindMapStore.updateSubgraph()`, `SubgraphTypes.RESEARCH_AREA`, `SpatialCacheStore.expire()`, `EntityMetadataStore.sessionsFor()`, `ResearchSession`, `ResearchState` (from Tasks 1-3, 5)
- Produces: `ResearchOrchestrator implements ResearchSessionService`

- [ ] **Step 1: Write ResearchOrchestratorTest**

Test: create (subgraph + root node + SQLite row), pause (state transition), resume (state + TTL extension), complete (state + grace period), listActive.

- [ ] **Step 2: Implement ResearchOrchestrator** — per spec §8

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl knowledge-pipeline`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add knowledge-pipeline/
git commit -m "feat(#413): add ResearchOrchestrator — lifecycle management with MindMap subgraphs Refs #413"
```

---

## Batch 6: Pipeline Orchestrator and Cache Eviction

### Task 8: KnowledgePipelineOrchestrator — end-to-end search + promote

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/KnowledgePipelineOrchestrator.java`
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/CacheDecayPolicy.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/KnowledgePipelineOrchestratorTest.java`

**Interfaces:**
- Consumes: All previous SPIs and stores. `Instance<LocationPlatform>` for multi-provider discovery.
- Produces: `KnowledgePipelineOrchestrator implements KnowledgePipelineService`

- [ ] **Step 1: Write CacheDecayPolicy** — field-type TTL computation per spec §10.1

- [ ] **Step 2: Write KnowledgePipelineOrchestratorTest** — end-to-end: search cache miss → fetch from location-ref → resolve → cache → return. Search cache hit. Promote flow.

- [ ] **Step 3: Implement KnowledgePipelineOrchestrator** — coordinates query normalization → cache check → fetch → resolution → cache store → return

- [ ] **Step 4: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -pl knowledge-pipeline`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge-pipeline/
git commit -m "feat(#413): add KnowledgePipelineOrchestrator — end-to-end search and promote Refs #413"
```

### Task 9: CacheEvictionScheduler

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/CacheEvictionScheduler.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/CacheEvictionSchedulerTest.java`

**Interfaces:**
- Consumes: `SpatialCacheStore`, `EntityMetadataStore`, `ResearchSessionStore`, `DedupIndexStore`
- Produces: `CacheEvictionScheduler` — scheduled eviction with research session protection

- [ ] **Step 1: Write CacheEvictionSchedulerTest** — expired entities removed, active-session entities protected, max-entity-age enforced, dedup index preserved

- [ ] **Step 2: Implement CacheEvictionScheduler** — per spec §10.2

- [ ] **Step 3: Run tests and commit**

```bash
git add knowledge-pipeline/
git commit -m "feat(#413): add CacheEvictionScheduler with research session protection Refs #413"
```

---

## Batch 7: Tile38 Client and Integration Tests

### Task 10: Tile38SpatialCacheStore

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/cache/Tile38SpatialCacheStore.java`
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/cache/Tile38SpatialCacheStoreIT.java`

**Interfaces:**
- Consumes: `SpatialCacheStore`, `CachedEntity`, `EntityMetadataStore`, `BoundingBox`, `CacheFilter`, `Coordinates`
- Produces: `Tile38SpatialCacheStore implements SpatialCacheStore` — Jedis-based Tile38 client

- [ ] **Step 1: Write Tile38SpatialCacheStore** — Maps SPI operations to Tile38 commands (SET, NEARBY, WITHIN, DEL, FSET) + SQLite EntityMetadataStore for non-spatial data. Per-tenant collections (`places_{tenantId}`).

- [ ] **Step 2: Write Tile38SpatialCacheStoreIT** — Testcontainers with `tile38/tile38` Docker image. Tests: set/get, nearby radius, within bounding box, remove, expire (FSET), tenant isolation.

- [ ] **Step 3: Run integration tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean verify -pl knowledge-pipeline -Dtest.groups=integration`
Expected: ALL PASS (requires Docker)

- [ ] **Step 4: Commit**

```bash
git add knowledge-pipeline/
git commit -m "feat(#413): add Tile38SpatialCacheStore — Jedis client with Testcontainers IT Refs #413"
```

### Task 11: End-to-end integration test

**Files:**
- Test: `knowledge-pipeline/src/test/java/io/casehub/neocortex/knowledge/KnowledgePipelineIntegrationTest.java`

- [ ] **Step 1: Write end-to-end test** — search → cache miss → fetch from location-ref → resolve → cache → promote to InMemoryMindMapStore → verify MindMap node with NodeRef

- [ ] **Step 2: Run and commit**

```bash
git add knowledge-pipeline/
git commit -m "feat(#413): add end-to-end integration test Refs #413"
```

---

## Batch 8: Observability and Documentation

### Task 12: Observability metrics and documentation

**Files:**
- Create: `knowledge-pipeline/src/main/java/io/casehub/neocortex/knowledge/KnowledgePipelineMetrics.java`
- Modify: `docs/guides/consumer-guide.md` (add knowledge pipeline section)
- Modify: `docs/guides/contributor-guide.md` (add knowledge pipeline internals)
- Modify: `CLAUDE.md` (add knowledge-pipeline modules to module structure)

**Interfaces:**
- Consumes: Micrometer `MeterRegistry`
- Produces: Counters/timers per spec §14

- [ ] **Step 1: Add KnowledgePipelineMetrics** — cache hits/misses, resolution decisions, provider fetch duration/errors, eviction stats, research session gauge, promotion counter

- [ ] **Step 2: Wire metrics into KnowledgePipelineOrchestrator and CacheEvictionScheduler**

- [ ] **Step 3: Update documentation** — consumer guide (usage), contributor guide (internals), CLAUDE.md (module list)

- [ ] **Step 4: Run full build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install`
Expected: BUILD SUCCESS, ALL TESTS PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge-pipeline/ docs/ CLAUDE.md
git commit -m "feat(#413): add observability metrics and update documentation Refs #413"
```

---

## References

- [2026-10-03-knowledge-pipeline-design.md](/Users/mdproctor/claude/public/casehub/neocortex/specs/issue-413-knowledge-pipeline/2026-10-03-knowledge-pipeline-design.md) — design spec this plan implements
- [decisions.md](/Users/mdproctor/claude/public/casehub/neocortex/specs/issue-413-knowledge-pipeline/decisions.md) — 11 validated decisions (D1-D11)
- [MindMapStore.java](/Users/mdproctor/claude/casehub/neocortex/mindmap-api/src/main/java/io/casehub/neocortex/mindmap/MindMapStore.java) — resolveNode, addNode, updateNode, merge
- [NodeInput.java](/Users/mdproctor/claude/casehub/neocortex/mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeInput.java) — node creation
- [NodeUpdate.java](/Users/mdproctor/claude/casehub/neocortex/mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeUpdate.java) — node enrichment (withRefsToAdd, withPropertiesToSet)
- [NodeRef.java](/Users/mdproctor/claude/casehub/neocortex/mindmap-api/src/main/java/io/casehub/neocortex/mindmap/NodeRef.java) — provenance (scheme, id, qualifier)
- [AttentionSignal.java](/Users/mdproctor/claude/casehub/neocortex/mindmap-api/src/main/java/io/casehub/neocortex/mindmap/AttentionSignal.java) — MERGE_CANDIDATE signal
- [CheckInService.java](/Users/mdproctor/claude/casehub/neocortex/mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/CheckInService.java) — ensureSubgraph pattern, resolveOrCreatePlace pattern
- [JaroWinkler.java](/Users/mdproctor/claude/casehub/neocortex/mindmap-intelligence/src/main/java/io/casehub/neocortex/mindmap/intelligence/consolidation/JaroWinkler.java) — name similarity
- [SqliteDataSourceFactory.java](/Users/mdproctor/claude/casehub/neocortex/sqlite-support/src/main/java/io/casehub/neocortex/sqlite/SqliteDataSourceFactory.java) — shared SQLite factory
- [LocationPlatform.java](/Users/mdproctor/claude/casehub/connectors/location-spi/src/main/java/io/casehub/connectors/location/spi/LocationPlatform.java) — PlaceSearch, PlaceDetails, Geocoding, Directions
- [Place.java](/Users/mdproctor/claude/casehub/connectors/location-spi/src/main/java/io/casehub/connectors/location/model/Place.java) — search result record
- [Tile38 commands](https://tile38.com/commands) — SET, NEARBY, WITHIN, DEL, FSET, SCAN
- GitHub #413 — focal issue
