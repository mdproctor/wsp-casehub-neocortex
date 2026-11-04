# Rich Document Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> subagent-driven-development (recommended) or executing-plans to
> implement this plan task-by-task. Each task follows TDD
> (test-driven-development) and uses ide-tooling for structural
> editing. Steps use checkbox (`- [ ]`) syntax for tracking.

**Focal issue:** #787 — Rich document ingestion — PDFs, Word, images with positional markdown format
**Issue group:** #787, #789 (parent epic)

**Goal:** Build a document parsing pipeline that converts binary documents (PDF, DOCX, images) into positional markdown — a text format preserving spatial structure via panel layouts and `#@` block annotations — and integrates with the existing corpus-management ingestion pipeline.

**Architecture:** New `corpus-management-parsers` module provides `DocumentParser` SPI with format-specific implementations. SPI types (`StructuralChunker`, `ImageDescriber`, `LayoutClassifier`, `PanelDefinition`) live in `corpus-management-api` (Tier 1). `BlockAnnotationParser` (for `#@` syntax) also lives in `corpus-management-api` since annotation-api source is not in this repo. `SqliteCorpusEntryStore.ingestEmbedding()` is enhanced to detect `content_format: positional-markdown` metadata and route to `StructuralChunker`.

**Tech Stack:** Java 21, Apache PDFBox (PDF structural extraction), Apache POI (DOCX), Apache Tika 2.9.2 (OCR via TesseractOCRParser), Maven, JUnit 5, AssertJ

## Global Constraints

- Java 21 source, Java 26 JVM: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn ...`
- Build: `mvn` not `./mvnw`
- All new types in `corpus-management-api` are pure Java, zero CDI
- All new types in `corpus-management-parsers` may use CDI (quarkus-arc)
- Commits reference issue: `Refs #787`
- IntelliJ MCP for all code navigation and structural editing
- TDD: write failing test → verify fail → implement → verify pass → commit
- Coordinate normalization: panel coordinates are 0.0–1.0 relative to page dimensions

---

## Batch 1: Foundation — SPI types and annotation parser

After this batch: all SPI types and the `#@` annotation parser exist, compile, and are fully tested. No module wiring yet.

### Task 1: BlockAnnotationParser

Parse `#@` block annotations from positional markdown. Strips `#@` lines, produces clean text + offset-mapped annotations.

**Files:**
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/BlockAnnotation.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/BlockParseResult.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/BlockAnnotationParser.java`
- Test: `corpus-management-api/src/test/java/io/casehub/neocortex/corpus/management/BlockAnnotationParserTest.java`

**Interfaces:**
- Consumes: nothing
- Produces: `BlockAnnotationParser.parse(String text) → BlockParseResult`; `BlockParseResult(String cleanText, List<BlockAnnotation> annotations)`; `BlockAnnotation(String type, String value, Map<String, String> params, int startOffset, int endOffset)`

- [ ] **Step 1: Write BlockAnnotation record**

```java
package io.casehub.neocortex.corpus.management;

import java.util.Map;

public record BlockAnnotation(
    String type,
    String value,
    Map<String, String> params,
    int startOffset,
    int endOffset
) {
    public BlockAnnotation {
        if (type == null || type.isBlank()) throw new IllegalArgumentException("type must not be blank");
        if (value == null) value = "";
        params = params == null ? Map.of() : Map.copyOf(params);
        if (startOffset < 0) throw new IllegalArgumentException("startOffset must be >= 0");
        if (endOffset < startOffset) throw new IllegalArgumentException("endOffset must be >= startOffset");
    }
}
```

- [ ] **Step 2: Write BlockParseResult record**

```java
package io.casehub.neocortex.corpus.management;

import java.util.List;

public record BlockParseResult(
    String cleanText,
    List<BlockAnnotation> annotations
) {
    public BlockParseResult {
        if (cleanText == null) cleanText = "";
        annotations = annotations == null ? List.of() : List.copyOf(annotations);
    }
}
```

- [ ] **Step 3: Write failing tests for BlockAnnotationParser**

```java
package io.casehub.neocortex.corpus.management;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class BlockAnnotationParserTest {

    private final BlockAnnotationParser parser = new BlockAnnotationParser();

    @Test
    void parseEmptyText() {
        BlockParseResult result = parser.parse("");
        assertThat(result.cleanText()).isEmpty();
        assertThat(result.annotations()).isEmpty();
    }

    @Test
    void parseNoAnnotations() {
        BlockParseResult result = parser.parse("Plain text with no annotations.");
        assertThat(result.cleanText()).isEqualTo("Plain text with no annotations.");
        assertThat(result.annotations()).isEmpty();
    }

    @Test
    void parseSinglePanelAnnotation() {
        String input = "#@ panel: header\n# Title\n\nSome text.";
        BlockParseResult result = parser.parse(input);
        assertThat(result.cleanText()).isEqualTo("# Title\n\nSome text.");
        assertThat(result.annotations()).hasSize(1);
        BlockAnnotation ann = result.annotations().get(0);
        assertThat(ann.type()).isEqualTo("panel");
        assertThat(ann.value()).isEqualTo("header");
        assertThat(ann.startOffset()).isEqualTo(0);
        assertThat(ann.endOffset()).isEqualTo(result.cleanText().length());
    }

    @Test
    void parseMultipleAnnotations() {
        String input = "#@ panel: left\nLeft text.\n#@ panel: right\nRight text.";
        BlockParseResult result = parser.parse(input);
        assertThat(result.cleanText()).isEqualTo("Left text.\nRight text.");
        assertThat(result.annotations()).hasSize(2);
        assertThat(result.annotations().get(0).type()).isEqualTo("panel");
        assertThat(result.annotations().get(0).value()).isEqualTo("left");
        assertThat(result.annotations().get(1).type()).isEqualTo("panel");
        assertThat(result.annotations().get(1).value()).isEqualTo("right");
        String leftText = result.cleanText().substring(
            result.annotations().get(0).startOffset(),
            result.annotations().get(0).endOffset());
        assertThat(leftText).isEqualTo("Left text.\n");
    }

    @Test
    void parsePageAnnotation() {
        String input = "#@ page: 1\nPage one.\n#@ page: 2\nPage two.";
        BlockParseResult result = parser.parse(input);
        assertThat(result.annotations()).hasSize(2);
        assertThat(result.annotations().get(0).type()).isEqualTo("page");
        assertThat(result.annotations().get(0).value()).isEqualTo("1");
        assertThat(result.annotations().get(1).value()).isEqualTo("2");
    }

    @Test
    void parseAnnotationWithKeyValueParams() {
        String input = "#@ figure: caption=\"Fig 1\" alt=\"diagram\"\nFigure content.";
        BlockParseResult result = parser.parse(input);
        assertThat(result.annotations()).hasSize(1);
        BlockAnnotation ann = result.annotations().get(0);
        assertThat(ann.type()).isEqualTo("figure");
        assertThat(ann.params()).containsEntry("caption", "Fig 1");
        assertThat(ann.params()).containsEntry("alt", "diagram");
    }

    @Test
    void parseAnnotationWithQuotedValue() {
        String input = "#@ ocr: \"Extracted text from image\"\nSurrounding text.";
        BlockParseResult result = parser.parse(input);
        assertThat(result.annotations()).hasSize(1);
        assertThat(result.annotations().get(0).type()).isEqualTo("ocr");
        assertThat(result.annotations().get(0).value()).isEqualTo("Extracted text from image");
    }

    @Test
    void offsetsAreCorrectInCleanText() {
        String input = "#@ panel: a\nAlpha.\n#@ panel: b\nBeta.\n#@ panel: c\nGamma.";
        BlockParseResult result = parser.parse(input);
        for (BlockAnnotation ann : result.annotations()) {
            String segment = result.cleanText().substring(ann.startOffset(), ann.endOffset());
            assertThat(segment).isNotBlank();
        }
    }

    @Test
    void annotationLineWithExtraSpaces() {
        String input = "#@   panel:   header  \nContent.";
        BlockParseResult result = parser.parse(input);
        assertThat(result.annotations()).hasSize(1);
        assertThat(result.annotations().get(0).type()).isEqualTo("panel");
        assertThat(result.annotations().get(0).value()).isEqualTo("header");
    }

    @Test
    void nonAnnotationHashLines() {
        String input = "# Heading\n## Subheading\n#not an annotation\nText.";
        BlockParseResult result = parser.parse(input);
        assertThat(result.cleanText()).isEqualTo(input);
        assertThat(result.annotations()).isEmpty();
    }

    @Test
    void layoutAnnotation() {
        String input = "#@ layout: 2-column\n#@ panel: left\nLeft.";
        BlockParseResult result = parser.parse(input);
        assertThat(result.annotations()).hasSize(2);
        assertThat(result.annotations().get(0).type()).isEqualTo("layout");
        assertThat(result.annotations().get(0).value()).isEqualTo("2-column");
    }
}
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-api -Dtest=BlockAnnotationParserTest -Dsurefire.failIfNoSpecifiedTests=false`
Expected: FAIL — BlockAnnotationParser class not found

- [ ] **Step 5: Implement BlockAnnotationParser**

```java
package io.casehub.neocortex.corpus.management;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class BlockAnnotationParser {

    private static final Pattern ANNOTATION_LINE = Pattern.compile("^#@\\s*(\\w+):\\s*(.*)$");
    private static final Pattern KV_PAIR = Pattern.compile("(\\w+)=\"([^\"]*)\"");

    public BlockParseResult parse(String text) {
        if (text == null || text.isEmpty()) return new BlockParseResult("", List.of());

        String[] lines = text.split("\n", -1);
        StringBuilder clean = new StringBuilder();
        List<AnnotationEntry> entries = new ArrayList<>();

        for (String line : lines) {
            Matcher m = ANNOTATION_LINE.matcher(line);
            if (m.matches()) {
                String type = m.group(1);
                String rawValue = m.group(2).strip();
                String value = unquote(rawValue);
                Map<String, String> params = parseParams(rawValue);
                if (!params.isEmpty()) {
                    String firstToken = rawValue.split("\\s+")[0];
                    if (!firstToken.contains("=")) {
                        value = unquote(firstToken);
                    } else {
                        value = "";
                    }
                }
                entries.add(new AnnotationEntry(type, value, params, clean.length()));
            } else {
                if (!clean.isEmpty() || !line.isEmpty()) {
                    if (!clean.isEmpty()) clean.append("\n");
                    clean.append(line);
                } else if (clean.isEmpty() && line.isEmpty()) {
                    // skip leading empty lines after annotation
                }
            }
        }

        // Fix: handle the case where clean text starts building correctly
        String cleanText = rebuildCleanText(text, lines);

        List<BlockAnnotation> annotations = new ArrayList<>();
        // Rebuild with proper offset tracking
        StringBuilder cleanBuilder = new StringBuilder();
        List<AnnotationEntry> pendingAnnotations = new ArrayList<>();

        for (String line : lines) {
            Matcher m = ANNOTATION_LINE.matcher(line);
            if (m.matches()) {
                String type = m.group(1);
                String rawValue = m.group(2).strip();
                String value = unquote(rawValue);
                Map<String, String> params = parseParams(rawValue);
                if (!params.isEmpty()) {
                    String firstToken = rawValue.split("\\s+")[0];
                    if (!firstToken.contains("=")) {
                        value = unquote(firstToken);
                    } else {
                        value = "";
                    }
                }
                pendingAnnotations.add(new AnnotationEntry(type, value, params, cleanBuilder.length()));
            } else {
                if (cleanBuilder.length() > 0) cleanBuilder.append("\n");
                cleanBuilder.append(line);
            }
        }

        cleanText = cleanBuilder.toString();

        for (int i = 0; i < pendingAnnotations.size(); i++) {
            AnnotationEntry entry = pendingAnnotations.get(i);
            int endOffset = (i + 1 < pendingAnnotations.size())
                ? pendingAnnotations.get(i + 1).offset
                : cleanText.length();
            annotations.add(new BlockAnnotation(entry.type, entry.value, entry.params, entry.offset, endOffset));
        }

        return new BlockParseResult(cleanText, annotations);
    }

    private static String unquote(String s) {
        if (s.length() >= 2 && s.startsWith("\"") && s.endsWith("\"")) {
            return s.substring(1, s.length() - 1);
        }
        return s;
    }

    private static Map<String, String> parseParams(String raw) {
        Map<String, String> params = new LinkedHashMap<>();
        Matcher m = KV_PAIR.matcher(raw);
        while (m.find()) {
            params.put(m.group(1), m.group(2));
        }
        return params.isEmpty() ? Map.of() : Map.copyOf(params);
    }

    private static String rebuildCleanText(String text, String[] lines) {
        StringBuilder sb = new StringBuilder();
        for (String line : lines) {
            if (!ANNOTATION_LINE.matcher(line).matches()) {
                if (sb.length() > 0) sb.append("\n");
                sb.append(line);
            }
        }
        return sb.toString();
    }

    private record AnnotationEntry(String type, String value, Map<String, String> params, int offset) {}
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-api -Dtest=BlockAnnotationParserTest`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/BlockAnnotation.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/BlockParseResult.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/BlockAnnotationParser.java corpus-management-api/src/test/java/io/casehub/neocortex/corpus/management/BlockAnnotationParserTest.java
git commit -m "feat(#787): add BlockAnnotationParser for #@ block annotations Refs #787"
```

### Task 2: SPI types in corpus-management-api

Define the Tier 1 SPI types that corpus-management and corpus-management-parsers depend on.

**Files:**
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/PanelDefinition.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/StructuredChunk.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/StructuralChunker.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/ImageDescriber.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/LayoutClassification.java`
- Create: `corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/LayoutClassifier.java`
- Test: `corpus-management-api/src/test/java/io/casehub/neocortex/corpus/management/PanelDefinitionTest.java`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `PanelDefinition(String id, double x, double y, double w, double h)`
  - `StructuredChunk(String text, Map<String, String> metadata)`
  - `StructuralChunker.chunk(String positionalMarkdown, int maxChunkSize) → List<StructuredChunk>`
  - `ImageDescriber.describe(byte[] imageBytes, String mimeType) → String`
  - `LayoutClassification(String layoutName, List<PanelDefinition> panels)`
  - `LayoutClassifier.classify(byte[] pageImage, String mimeType) → LayoutClassification`

- [ ] **Step 1: Write PanelDefinition record with validation test**

```java
package io.casehub.neocortex.corpus.management;

public record PanelDefinition(String id, double x, double y, double w, double h) {
    public PanelDefinition {
        if (id == null || id.isBlank()) throw new IllegalArgumentException("id must not be blank");
        if (x < 0.0 || x > 1.0) throw new IllegalArgumentException("x must be in [0.0, 1.0]");
        if (y < 0.0 || y > 1.0) throw new IllegalArgumentException("y must be in [0.0, 1.0]");
        if (w <= 0.0 || w > 1.0) throw new IllegalArgumentException("w must be in (0.0, 1.0]");
        if (h <= 0.0 || h > 1.0) throw new IllegalArgumentException("h must be in (0.0, 1.0]");
    }
}
```

Test:
```java
package io.casehub.neocortex.corpus.management;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.*;

class PanelDefinitionTest {

    @Test
    void validPanel() {
        var panel = new PanelDefinition("main", 0.0, 0.0, 1.0, 1.0);
        assertThat(panel.id()).isEqualTo("main");
        assertThat(panel.w()).isEqualTo(1.0);
    }

    @Test
    void rejectsBlankId() {
        assertThatThrownBy(() -> new PanelDefinition("", 0.0, 0.0, 1.0, 1.0))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void rejectsOutOfRangeCoordinates() {
        assertThatThrownBy(() -> new PanelDefinition("p", -0.1, 0.0, 1.0, 1.0))
            .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> new PanelDefinition("p", 0.0, 0.0, 0.0, 1.0))
            .isInstanceOf(IllegalArgumentException.class);
    }
}
```

- [ ] **Step 2: Write remaining SPI types**

```java
// StructuredChunk.java
package io.casehub.neocortex.corpus.management;

import java.util.Map;

public record StructuredChunk(String text, Map<String, String> metadata) {
    public StructuredChunk {
        if (text == null) throw new IllegalArgumentException("text must not be null");
        metadata = metadata == null ? Map.of() : Map.copyOf(metadata);
    }
}
```

```java
// StructuralChunker.java
package io.casehub.neocortex.corpus.management;

import java.util.List;

public interface StructuralChunker {
    List<StructuredChunk> chunk(String positionalMarkdown, int maxChunkSize);
}
```

```java
// ImageDescriber.java
package io.casehub.neocortex.corpus.management;

@FunctionalInterface
public interface ImageDescriber {
    String describe(byte[] imageBytes, String mimeType);
}
```

```java
// LayoutClassification.java
package io.casehub.neocortex.corpus.management;

import java.util.List;

public record LayoutClassification(String layoutName, List<PanelDefinition> panels) {
    public LayoutClassification {
        if (layoutName == null || layoutName.isBlank()) throw new IllegalArgumentException("layoutName must not be blank");
        panels = panels == null ? List.of() : List.copyOf(panels);
    }
}
```

```java
// LayoutClassifier.java
package io.casehub.neocortex.corpus.management;

@FunctionalInterface
public interface LayoutClassifier {
    LayoutClassification classify(byte[] pageImage, String mimeType);
}
```

- [ ] **Step 3: Run tests**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-api`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/PanelDefinition.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/StructuredChunk.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/StructuralChunker.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/ImageDescriber.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/LayoutClassification.java corpus-management-api/src/main/java/io/casehub/neocortex/corpus/management/LayoutClassifier.java corpus-management-api/src/test/java/io/casehub/neocortex/corpus/management/PanelDefinitionTest.java
git commit -m "feat(#787): add SPI types — PanelDefinition, StructuralChunker, ImageDescriber, LayoutClassifier Refs #787"
```

---

## Batch 2: Module scaffold + positional markdown builder

After this batch: corpus-management-parsers module exists with DocumentParser SPI, layout presets, PositionalMarkdownBuilder, and CorpusType.DOCUMENT. Positional markdown can be generated and parsed.

### Task 3: corpus-management-parsers Maven module + DocumentParser SPI

Scaffold the new module with pom.xml, DocumentParser SPI, supporting records (ParseResult, Layout, ImageRegion, DocumentParserConfig), and layout presets.

**Files:**
- Create: `corpus-management-parsers/pom.xml`
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/DocumentParser.java`
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/ParseResult.java`
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/Layout.java`
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/ImageRegion.java`
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/DocumentParserConfig.java`
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/LayoutPresets.java`
- Modify: `pom.xml` (parent) — add `<module>corpus-management-parsers</module>` and `<dependency>` in `<dependencyManagement>`
- Test: `corpus-management-parsers/src/test/java/io/casehub/neocortex/corpus/management/parsers/LayoutPresetsTest.java`

**Interfaces:**
- Consumes: `PanelDefinition` (from Task 2)
- Produces:
  - `DocumentParser.parse(InputStream, String, DocumentParserConfig) → ParseResult`
  - `DocumentParser.supportedMediaTypes() → Set<String>`
  - `ParseResult(String positionalMarkdown, Layout layout, Map<String, String> extractedMetadata, List<ImageRegion> imageRegions)`
  - `Layout(String name, List<PanelDefinition> panels, int pageCount, int[] pageSize)`
  - `ImageRegion(String panelId, int pageNumber, String captionText, String ocrText, String llmDescription, byte[] imageBytes)`
  - `DocumentParserConfig(boolean ocrEnabled, boolean llmImageDescriptionEnabled, boolean llmLayoutDetectionEnabled, int maxPages)`
  - `LayoutPresets.resolve(String name) → List<PanelDefinition>`
  - `LayoutPresets.PRESETS` — Map of preset name → panel definitions

- [ ] **Step 1: Create pom.xml for corpus-management-parsers**

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

  <artifactId>casehub-neocortex-corpus-management-parsers</artifactId>
  <name>CaseHub Neocortex - Corpus Management Parsers</name>
  <description>Document parsing pipeline — PDF, DOCX, image to positional markdown with structural annotations.</description>

  <dependencies>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-neocortex-corpus-management-api</artifactId>
    </dependency>

    <!-- PDF structural extraction -->
    <dependency>
      <groupId>org.apache.pdfbox</groupId>
      <artifactId>pdfbox</artifactId>
      <version>3.0.3</version>
    </dependency>

    <!-- DOCX parsing -->
    <dependency>
      <groupId>org.apache.poi</groupId>
      <artifactId>poi-ooxml</artifactId>
      <version>5.3.0</version>
    </dependency>

    <!-- OCR via Tika TesseractOCRParser -->
    <dependency>
      <groupId>org.apache.tika</groupId>
      <artifactId>tika-core</artifactId>
      <version>2.9.2</version>
    </dependency>
    <dependency>
      <groupId>org.apache.tika</groupId>
      <artifactId>tika-parsers-standard-package</artifactId>
      <version>2.9.2</version>
      <exclusions>
        <exclusion>
          <groupId>org.apache.logging.log4j</groupId>
          <artifactId>*</artifactId>
        </exclusion>
      </exclusions>
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

- [ ] **Step 2: Add module to parent pom.xml**

Add `<module>corpus-management-parsers</module>` after the `corpus-management` module entry (line ~104 in parent pom.xml).

Add to `<dependencyManagement>`:
```xml
<dependency>
  <groupId>io.casehub</groupId>
  <artifactId>casehub-neocortex-corpus-management-parsers</artifactId>
  <version>${project.version}</version>
</dependency>
```

- [ ] **Step 3: Write DocumentParser SPI + supporting records**

Create `DocumentParser.java`, `ParseResult.java`, `Layout.java`, `ImageRegion.java`, `DocumentParserConfig.java` per the spec's §DocumentParser SPI section. All records with validation.

- [ ] **Step 4: Write LayoutPresets with tests**

```java
package io.casehub.neocortex.corpus.management.parsers;

import io.casehub.neocortex.corpus.management.PanelDefinition;
import java.util.List;
import java.util.Map;

public final class LayoutPresets {

    public static final Map<String, List<PanelDefinition>> PRESETS = Map.ofEntries(
        Map.entry("single", List.of(new PanelDefinition("main", 0.0, 0.0, 1.0, 1.0))),
        Map.entry("2-column", List.of(
            new PanelDefinition("left", 0.0, 0.0, 0.48, 1.0),
            new PanelDefinition("right", 0.52, 0.0, 0.48, 1.0))),
        Map.entry("3-column", List.of(
            new PanelDefinition("left", 0.0, 0.0, 0.31, 1.0),
            new PanelDefinition("center", 0.345, 0.0, 0.31, 1.0),
            new PanelDefinition("right", 0.69, 0.0, 0.31, 1.0))),
        Map.entry("header-body-footer", List.of(
            new PanelDefinition("header", 0.0, 0.9, 1.0, 0.1),
            new PanelDefinition("body", 0.0, 0.1, 1.0, 0.78),
            new PanelDefinition("footer", 0.0, 0.0, 1.0, 0.08))),
        Map.entry("grid-2x2", List.of(
            new PanelDefinition("top-left", 0.0, 0.5, 0.48, 0.5),
            new PanelDefinition("top-right", 0.52, 0.5, 0.48, 0.5),
            new PanelDefinition("bottom-left", 0.0, 0.0, 0.48, 0.48),
            new PanelDefinition("bottom-right", 0.52, 0.0, 0.48, 0.48)))
    );

    public static List<PanelDefinition> resolve(String name) {
        List<PanelDefinition> panels = PRESETS.get(name);
        if (panels == null) throw new IllegalArgumentException("Unknown layout preset: " + name);
        return panels;
    }

    private LayoutPresets() {}
}
```

Test verifies all presets exist and have valid coordinates.

- [ ] **Step 5: Run tests and commit**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-parsers`
Expected: ALL PASS

```bash
git add corpus-management-parsers/ pom.xml
git commit -m "feat(#787): scaffold corpus-management-parsers module with DocumentParser SPI and layout presets Refs #787"
```

### Task 4: PositionalMarkdownBuilder + CorpusType.DOCUMENT

Build positional markdown cover documents from `ParseResult`. Define the `DOCUMENT` corpus type.

**Files:**
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/PositionalMarkdownBuilder.java`
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/DocumentCorpusTypes.java`
- Test: `corpus-management-parsers/src/test/java/io/casehub/neocortex/corpus/management/parsers/PositionalMarkdownBuilderTest.java`

**Interfaces:**
- Consumes: `ParseResult`, `Layout`, `PanelDefinition` (from Task 3), `CorpusType`, `FieldSchema` (from corpus-management-api)
- Produces: `PositionalMarkdownBuilder.build(ParseResult, String artifactRef) → String` (YAML-frontmatter cover document)

- [ ] **Step 1: Write failing tests for PositionalMarkdownBuilder**

Test that `build()` produces a valid YAML frontmatter document with layout, panels, content_format, artifact_ref, and the positional markdown body.

- [ ] **Step 2: Implement PositionalMarkdownBuilder**

Serializes `ParseResult.layout()` into YAML frontmatter, merges `extractedMetadata`, hardcodes `content_format: positional-markdown`, appends positional markdown body.

- [ ] **Step 3: Write DocumentCorpusTypes**

```java
package io.casehub.neocortex.corpus.management.parsers;

import io.casehub.neocortex.corpus.management.CorpusType;
import io.casehub.neocortex.corpus.management.FieldSchema;
import java.util.Map;

public final class DocumentCorpusTypes {

    public static final CorpusType DOCUMENT = new CorpusType(
        "document",
        Map.of("content_format", FieldSchema.STRING,
               "source_format", FieldSchema.STRING,
               "layout", FieldSchema.STRING),
        Map.of("artifact_ref", FieldSchema.STRING,
               "source_pages", FieldSchema.INTEGER),
        null
    );

    private DocumentCorpusTypes() {}
}
```

- [ ] **Step 4: Run tests and commit**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-parsers`
Expected: ALL PASS

```bash
git add corpus-management-parsers/src/
git commit -m "feat(#787): add PositionalMarkdownBuilder and DocumentCorpusTypes Refs #787"
```

---

## Batch 3: Chunking + integration

After this batch: the full pipeline works end-to-end — positional markdown is chunked structurally and embedded with per-chunk metadata.

### Task 5: DefaultStructuralChunker implementation

Implement structure-aware chunking that splits at `#@` boundaries and produces per-chunk metadata.

**Files:**
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/DefaultStructuralChunker.java`
- Test: `corpus-management-parsers/src/test/java/io/casehub/neocortex/corpus/management/parsers/DefaultStructuralChunkerTest.java`

**Interfaces:**
- Consumes: `StructuralChunker` SPI (Task 2), `BlockAnnotationParser` (Task 1), `StructuredChunk` (Task 2)
- Produces: `DefaultStructuralChunker implements StructuralChunker` — `chunk(String positionalMarkdown, int maxChunkSize) → List<StructuredChunk>`

- [ ] **Step 1: Write failing tests**

Test cases:
- Single panel, small text → one chunk with panel metadata
- Two panels → two chunks, each with correct panel ID
- Page annotations → page number in chunk metadata
- Large panel text → falls back to character-based splitting
- Very short chunks (< 20% threshold) → merged with next
- Heading-level splitting within a panel
- Mixed annotations (panel + figure + ocr)

- [ ] **Step 2: Implement DefaultStructuralChunker**

Algorithm per spec §Chunking Algorithm:
1. Parse `#@` via `BlockAnnotationParser`
2. Split at `#@ page:`, `#@ panel:`, `#@ layout:` boundaries
3. Within panel: split at headings if oversized
4. Within section: fall back to character-based splitting
5. Merge very short chunks (< 20% of maxChunkSize)
6. Attach metadata per chunk

- [ ] **Step 3: Run tests and commit**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-parsers`
Expected: ALL PASS

```bash
git add corpus-management-parsers/src/
git commit -m "feat(#787): implement DefaultStructuralChunker with structure-aware splitting Refs #787"
```

### Task 6: SqliteCorpusEntryStore integration

Enhance `ingestEmbedding()` to detect positional markdown via `content_format` metadata and route to `StructuralChunker`.

**Files:**
- Modify: `corpus-management/src/main/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStore.java` — add `StructuralChunker` optional dependency, modify `ingestEmbedding()`
- Modify: `corpus-management/pom.xml` — add optional dependency on corpus-management-api (already present via transitive)
- Test: `corpus-management/src/test/java/io/casehub/neocortex/corpus/management/impl/SqliteCorpusEntryStoreTest.java` — add test for positional markdown chunking

**Interfaces:**
- Consumes: `StructuralChunker` (Task 2 SPI, Task 5 impl), `StructuredChunk` (Task 2), `CorpusEntry`, `ChunkInput`, `EmbeddingIngestor`
- Produces: enhanced `ingestEmbedding()` — detects `content_format: positional-markdown` and routes to `StructuralChunker`

- [ ] **Step 1: Write failing test**

Create a `CorpusEntry` with `content_format: positional-markdown` metadata and a body containing `#@` annotations. Verify that `ingestEmbedding()` produces multiple `ChunkInput` objects with per-chunk metadata (page, panel, section) instead of one.

Use a stub `StructuralChunker` implementation for the test.

- [ ] **Step 2: Modify SqliteCorpusEntryStore**

Add `StructuralChunker` as an optional constructor parameter (or CDI `Instance<StructuralChunker>`). Modify `ingestEmbedding()` per spec §Integration with SqliteCorpusEntryStore — detect via `entry.metadata().get("content_format")`, route to `StructuralChunker` or existing single-chunk behavior.

- [ ] **Step 3: Run full corpus-management test suite**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management`
Expected: ALL PASS (existing tests unaffected — they don't set `content_format` metadata)

- [ ] **Step 4: Commit**

```bash
git add corpus-management/src/
git commit -m "feat(#787): integrate StructuralChunker into SqliteCorpusEntryStore.ingestEmbedding() Refs #787"
```

---

## Batch 4: Document parsers

After this batch: PDF, DOCX, and images can be parsed into positional markdown with structural annotations. Full end-to-end pipeline operational.

### Task 7: PdfDocumentParser

Parse PDFs using Apache PDFBox. Extract text blocks with spatial positions, classify page layout, assign text to panels, generate positional markdown.

**Files:**
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/PdfDocumentParser.java`
- Test: `corpus-management-parsers/src/test/java/io/casehub/neocortex/corpus/management/parsers/PdfDocumentParserTest.java`
- Test resource: `corpus-management-parsers/src/test/resources/sample-single-column.pdf`

**Interfaces:**
- Consumes: `DocumentParser` SPI (Task 3), `DocumentParserConfig` (Task 3), `Layout` (Task 3), `PanelDefinition` (Task 2), `LayoutPresets` (Task 3), `LayoutClassifier` (Task 2, optional), `ImageDescriber` (Task 2, optional)
- Produces: `PdfDocumentParser implements DocumentParser` — `parse(InputStream, String, DocumentParserConfig) → ParseResult`

- [ ] **Step 1: Create a minimal test PDF**

Use PDFBox programmatically in the test to create a simple single-column PDF with known text content. Avoids committing binary test fixtures.

- [ ] **Step 2: Write failing tests**

Test cases:
- Single-page, single-column PDF → layout=single, one panel
- Extract text preserves content
- Page size extracted correctly
- `supportedMediaTypes()` returns `application/pdf`

- [ ] **Step 3: Implement PdfDocumentParser**

Use PDFBox `PDFTextStripperByArea` or `PDFTextStripper` with custom `TextPosition` processing to extract text blocks with (x, y, w, h) positions. Classify layout using heuristic column detection (gap analysis between text block x-coordinates). Assign text blocks to panels. Generate positional markdown with `#@` annotations.

- [ ] **Step 4: Run tests and commit**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -pl corpus-management-parsers -Dtest=PdfDocumentParserTest`
Expected: ALL PASS

```bash
git add corpus-management-parsers/src/
git commit -m "feat(#787): implement PdfDocumentParser with PDFBox structural extraction Refs #787"
```

### Task 8: DocxDocumentParser

Parse DOCX files using Apache POI. Extract paragraphs, tables, and images with structural information.

**Files:**
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/DocxDocumentParser.java`
- Test: `corpus-management-parsers/src/test/java/io/casehub/neocortex/corpus/management/parsers/DocxDocumentParserTest.java`

**Interfaces:**
- Consumes: `DocumentParser` SPI (Task 3), `DocumentParserConfig` (Task 3), `Layout` (Task 3), `PanelDefinition` (Task 2), `LayoutPresets` (Task 3)
- Produces: `DocxDocumentParser implements DocumentParser` — `parse(InputStream, String, DocumentParserConfig) → ParseResult`

- [ ] **Step 1: Create minimal test DOCX**

Use Apache POI `XWPFDocument` in the test to create a DOCX with a heading, paragraph, and table.

- [ ] **Step 2: Write failing tests**

Test: extract heading, paragraph, table from DOCX. Verify positional markdown has correct structure.

- [ ] **Step 3: Implement DocxDocumentParser**

DOCX is inherently single-column (Word doesn't expose column positions programmatically like PDF). Layout is always `single` unless section columns are detected. Extract paragraphs, tables, images via POI. Generate positional markdown.

- [ ] **Step 4: Run tests and commit**

```bash
git add corpus-management-parsers/src/
git commit -m "feat(#787): implement DocxDocumentParser with Apache POI Refs #787"
```

### Task 9: ImageDocumentParser

Parse images using Tika's TesseractOCRParser. Extract text via OCR, optionally describe via LLM.

**Files:**
- Create: `corpus-management-parsers/src/main/java/io/casehub/neocortex/corpus/management/parsers/ImageDocumentParser.java`
- Test: `corpus-management-parsers/src/test/java/io/casehub/neocortex/corpus/management/parsers/ImageDocumentParserTest.java`

**Interfaces:**
- Consumes: `DocumentParser` SPI (Task 3), `DocumentParserConfig` (Task 3), `Layout` (Task 3), `ImageDescriber` (Task 2, optional)
- Produces: `ImageDocumentParser implements DocumentParser` — layout is always `single` with one `main` panel. Body contains OCR text + optional `#@ describe:` annotation.

- [ ] **Step 1: Write failing tests**

Test with a programmatically created image containing known text (if Tesseract is available). Fallback test: verify correct ParseResult structure with empty OCR when Tesseract is not on PATH.

- [ ] **Step 2: Implement ImageDocumentParser**

Use Tika's `AutoDetectParser` with `TesseractOCRParser` config. Layout is always `single`. If `ImageDescriber` is provided and config enables it, add `#@ describe:` annotation.

- [ ] **Step 3: Run tests and commit**

```bash
git add corpus-management-parsers/src/
git commit -m "feat(#787): implement ImageDocumentParser with Tika OCR Refs #787"
```

---

## References

- [2026-11-04-rich-document-ingestion-design.md] — design spec this plan implements
- [corpus-management-api/.../CorpusEntry.java] — String body record
- [corpus-management-api/.../CorpusType.java] — record with required/optional FieldSchema
- [corpus-management-api/.../FieldSchema.java] — enum (STRING, INTEGER, etc.)
- [corpus-management/.../SqliteCorpusEntryStore.java:121-130] — ingestEmbedding() method
- [corpus-management/.../BuiltInCorpusTypes.java] — existing corpus type pattern
- [corpus-management/.../CoverDocumentParser.java] — existing cover document parsing
- [rag-tika/.../TikaDocumentParser.java] — existing Tika integration
- [rag-tika/pom.xml] — Tika 2.9.2 dependency pattern
- [GitHub #787] — focal issue
- [GitHub #789] — parent epic
- [decisions.md] — design decisions
