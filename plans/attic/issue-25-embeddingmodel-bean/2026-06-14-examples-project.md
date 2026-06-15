# Examples Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two example modules (`example-text-analysis` and `example-rag-pipeline`) demonstrating all casehub-neural-text capabilities with real ONNX models, multi-domain sample data, and comprehensive testing.

**Architecture:** Two modules split along the infrastructure boundary. `example-text-analysis` is standalone Java with no framework dependencies — load ONNX models, run inference, print results. `example-rag-pipeline` is Quarkus with Testcontainers Qdrant — ingest documents into a corpus, push to vector store, search with hybrid retrieval. Both use three Maven profiles (default/smoke/full) and JUnit `@Tag` annotations for test selection.

**Tech Stack:** Java 21, ONNX Runtime JVM 1.26.0, HuggingFace Tokenizers, LangChain4j 1.14.1, Quarkus 3.32.2 (RAG module only), Qdrant via Testcontainers (RAG module only), JUnit 5 + AssertJ.

**Spec:** `docs/specs/2026-06-14-examples-project-design.md`

---

### Task 1: Create GitHub Issue for Examples Project

**Files:**
- None (GitHub API only)

- [ ] **Step 1: Create the issue**

```bash
gh issue create --repo casehubio/neural-text --title "feat: examples project — Text Analysis + RAG Pipeline demos" --body "$(cat <<'EOF'
## Summary

Two example modules demonstrating all casehub-neural-text capabilities across three domains (tech, news, legal):

- `example-text-analysis` — standalone Java, no Quarkus. NLI, zero-shot classification, scoring (sentiment/toxicity/quality/readability), reranking, SPLADE embeddings.
- `example-rag-pipeline` — Quarkus + Testcontainers Qdrant. Corpus ingestion (Flat + Zip), hybrid dense+sparse search with RRF fusion, cross-encoder reranking.

Real ONNX models from HuggingFace. Three Maven profiles (default/smoke/full). Five test categories (unit, happy-path, correctness, cross-domain, edge-case).

## Spec
`docs/specs/2026-06-14-examples-project-design.md`

## Scale / Complexity
L / Med
EOF
)"
```

Record the issue number — all commits in this plan reference it as `#N`.

---

### Task 2: Model Research and Download Configuration

**Files:**
- None modified yet — research only

This task resolves the Open Items from the spec. The models chosen here determine the download URLs, SHA-256 checksums, and output dimensions used in all subsequent tasks.

- [ ] **Step 1: Verify NLI model availability**

Check that `cross-encoder/nli-deberta-v3-xsmall` has a quantized ONNX export on HuggingFace. The `inference-quarkus/pom.xml` already downloads from `https://huggingface.co/Xenova/nli-deberta-v3-xsmall/resolve/main/onnx/model_quantized.onnx` — confirm this URL is still live and note the file size.

```bash
curl -sI "https://huggingface.co/Xenova/nli-deberta-v3-xsmall/resolve/main/onnx/model_quantized.onnx" | head -5
```

Also verify the tokenizer: `https://huggingface.co/Xenova/nli-deberta-v3-xsmall/resolve/main/tokenizer.json`

Note: this model outputs 3 values (entailment, neutral, contradiction). DeBERTa convention: index 0 = entailment, index 1 = neutral, index 2 = contradiction. This is the OPPOSITE of the convention-constructor mapping in `NliClassifier` (which assumes index 0 = contradiction, index 2 = entailment). The demo must use the explicit-index constructor: `new NliClassifier(model, 0, 1, 2)`.

- [ ] **Step 2: Verify cross-encoder reranker model**

Check `cross-encoder/ms-marco-MiniLM-L-6-v2` for ONNX export availability:

```bash
curl -sI "https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2/resolve/main/onnx/model_quantized.onnx" | head -5
```

This model outputs 1 value (relevance score). Matches `CrossEncoderReranker` which expects `outputSize = 1`.

- [ ] **Step 3: Verify SPLADE model ONNX availability**

Check `naver/splade-cocondenser-ensembledistil` for ONNX export. This model is less commonly exported to ONNX — it may need a Xenova/Transformers.js export or a manual export.

```bash
curl -sI "https://huggingface.co/Xenova/splade-cocondenser-ensembledistil/resolve/main/onnx/model_quantized.onnx" | head -5
```

If unavailable, check `prithivida/Splade_PP_en_v1` which has ONNX exports.

- [ ] **Step 4: Research sentiment model for ScoringDemo (TextClassifier)**

Need a small ONNX model that outputs 3 classes (positive/negative/neutral). Candidates:
- `Xenova/distilbert-base-uncased-finetuned-sst-2-english` (2 classes: positive/negative, ~67MB)
- `Xenova/bert-base-multilingual-uncased-sentiment` (5 classes: 1-5 stars, ~170MB)

Check availability:
```bash
curl -sI "https://huggingface.co/Xenova/distilbert-base-uncased-finetuned-sst-2-english/resolve/main/onnx/model_quantized.onnx" | head -5
```

The 2-class SST-2 model is smaller and demonstrates `TextClassifier` just as well. Labels would be `List.of("negative", "positive")`.

- [ ] **Step 5: Verify ONNX Runtime version compatibility**

Check that `langchain4j-embeddings` 1.14.1 is compatible with `onnxruntime` 1.26.0. Read the `langchain4j-embeddings` POM to see which onnxruntime version it was compiled against:

Use IntelliJ MCP to read the dependency from the langchain4j-embeddings artifact in Maven.

If versions differ significantly, the parent POM's `dependencyManagement` pin will still force 1.26.0 — check for any removed/renamed classes.

- [ ] **Step 6: Document findings**

Record all verified URLs, SHA-256 checksums (from HuggingFace), model output sizes, and label mappings. These values are used directly in the POM download configurations and demo code in subsequent tasks.

---

### Task 3: Parent POM Profiles and Module Scaffolding

**Files:**
- Modify: `pom.xml` (parent POM)
- Create: `examples/example-text-analysis/pom.xml`
- Create: `examples/example-rag-pipeline/pom.xml`

- [ ] **Step 1: Add profiles to parent POM**

Add to `pom.xml` after the `</build>` closing tag (line ~264):

```xml
<profiles>
  <profile>
    <id>examples-smoke</id>
    <modules>
      <module>examples/example-text-analysis</module>
      <module>examples/example-rag-pipeline</module>
    </modules>
  </profile>
  <profile>
    <id>examples</id>
    <modules>
      <module>examples/example-text-analysis</module>
      <module>examples/example-rag-pipeline</module>
    </modules>
  </profile>
</profiles>
```

- [ ] **Step 2: Create example-text-analysis POM**

Create `examples/example-text-analysis/pom.xml`:

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
    <relativePath>../../pom.xml</relativePath>
  </parent>

  <artifactId>casehub-example-text-analysis</artifactId>
  <name>CaseHub Neural Text - Example: Text Analysis</name>
  <description>Standalone inference examples — NLI, classification, scoring, reranking, SPLADE — no Quarkus, no infrastructure</description>

  <dependencies>

    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-runtime</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-tasks</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-splade</artifactId>
    </dependency>

    <!-- Testing -->
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
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-inmem</artifactId>
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
            </configuration>
          </plugin>
        </plugins>
      </build>
    </profile>
    <profile>
      <id>examples</id>
      <build>
        <plugins>
          <plugin>
            <groupId>com.googlecode.maven-download-plugin</groupId>
            <artifactId>download-maven-plugin</artifactId>
            <executions>
              <!-- NLI model — used by NliDemo, ZeroShotClassificationDemo -->
              <execution>
                <id>download-nli-model</id>
                <phase>generate-test-resources</phase>
                <goals><goal>wget</goal></goals>
                <configuration>
                  <url>https://huggingface.co/Xenova/nli-deberta-v3-xsmall/resolve/main/onnx/model_quantized.onnx</url>
                  <outputDirectory>${project.build.directory}/models/nli-deberta-v3-xsmall</outputDirectory>
                  <outputFileName>model.onnx</outputFileName>
                  <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
                </configuration>
              </execution>
              <execution>
                <id>download-nli-tokenizer</id>
                <phase>generate-test-resources</phase>
                <goals><goal>wget</goal></goals>
                <configuration>
                  <url>https://huggingface.co/Xenova/nli-deberta-v3-xsmall/resolve/main/tokenizer.json</url>
                  <outputDirectory>${project.build.directory}/models/nli-deberta-v3-xsmall</outputDirectory>
                  <outputFileName>tokenizer.json</outputFileName>
                  <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
                </configuration>
              </execution>
              <!-- Reranker model -->
              <execution>
                <id>download-reranker-model</id>
                <phase>generate-test-resources</phase>
                <goals><goal>wget</goal></goals>
                <configuration>
                  <url>https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2/resolve/main/onnx/model_quantized.onnx</url>
                  <outputDirectory>${project.build.directory}/models/ms-marco-MiniLM-L-6-v2</outputDirectory>
                  <outputFileName>model.onnx</outputFileName>
                  <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
                </configuration>
              </execution>
              <execution>
                <id>download-reranker-tokenizer</id>
                <phase>generate-test-resources</phase>
                <goals><goal>wget</goal></goals>
                <configuration>
                  <url>https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2/resolve/main/tokenizer.json</url>
                  <outputDirectory>${project.build.directory}/models/ms-marco-MiniLM-L-6-v2</outputDirectory>
                  <outputFileName>tokenizer.json</outputFileName>
                  <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
                </configuration>
              </execution>
              <!-- Sentiment model — used by ScoringDemo (TextClassifier) -->
              <execution>
                <id>download-sentiment-model</id>
                <phase>generate-test-resources</phase>
                <goals><goal>wget</goal></goals>
                <configuration>
                  <url>https://huggingface.co/Xenova/distilbert-base-uncased-finetuned-sst-2-english/resolve/main/onnx/model_quantized.onnx</url>
                  <outputDirectory>${project.build.directory}/models/distilbert-sst2</outputDirectory>
                  <outputFileName>model.onnx</outputFileName>
                  <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
                </configuration>
              </execution>
              <execution>
                <id>download-sentiment-tokenizer</id>
                <phase>generate-test-resources</phase>
                <goals><goal>wget</goal></goals>
                <configuration>
                  <url>https://huggingface.co/Xenova/distilbert-base-uncased-finetuned-sst-2-english/resolve/main/tokenizer.json</url>
                  <outputDirectory>${project.build.directory}/models/distilbert-sst2</outputDirectory>
                  <outputFileName>tokenizer.json</outputFileName>
                  <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
                </configuration>
              </execution>
              <!-- SPLADE model — URLs filled in from Task 2 research -->
            </executions>
          </plugin>
        </plugins>
      </build>
    </profile>
  </profiles>

</project>
```

Note: SPLADE model download executions are added after Task 2 confirms the exact URLs.

- [ ] **Step 3: Create example-rag-pipeline POM**

Create `examples/example-rag-pipeline/pom.xml`:

```xml
<?xml version="1.0"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>io.casehub</groupId>
    <artifactId>casehub-neural-text-parent</artifactId>
    <version>0.2-SNAPSHOT</version>
    <relativePath>../../pom.xml</relativePath>
  </parent>

  <artifactId>casehub-example-rag-pipeline</artifactId>
  <name>CaseHub Neural Text - Example: RAG Pipeline</name>
  <description>End-to-end RAG example — corpus ingestion, hybrid dense+sparse search, cross-encoder reranking</description>

  <dependencies>

    <!-- Inference -->
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-runtime</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-tasks</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-splade</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-quarkus</artifactId>
    </dependency>

    <!-- RAG -->
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-rag-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-rag</artifactId>
    </dependency>

    <!-- Corpus -->
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-corpus-api</artifactId>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-corpus</artifactId>
    </dependency>

    <!-- LangChain4j — EmbeddingModel + OnnxEmbeddingModel for dense embeddings -->
    <dependency>
      <groupId>dev.langchain4j</groupId>
      <artifactId>langchain4j-embeddings</artifactId>
    </dependency>

    <!-- Quarkus -->
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-arc</artifactId>
    </dependency>

    <!-- Testing -->
    <dependency>
      <groupId>io.quarkus</groupId>
      <artifactId>quarkus-junit5</artifactId>
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
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-inference-inmem</artifactId>
      <scope>test</scope>
    </dependency>
    <dependency>
      <groupId>io.casehub</groupId>
      <artifactId>casehub-rag-testing</artifactId>
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
            </configuration>
          </plugin>
        </plugins>
      </build>
    </profile>
    <profile>
      <id>examples</id>
      <build>
        <plugins>
          <plugin>
            <groupId>com.googlecode.maven-download-plugin</groupId>
            <artifactId>download-maven-plugin</artifactId>
            <executions>
              <!-- Dense embedding model (all-MiniLM-L6-v2) -->
              <execution>
                <id>download-dense-model</id>
                <phase>generate-test-resources</phase>
                <goals><goal>wget</goal></goals>
                <configuration>
                  <url>https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/onnx/model_quantized.onnx</url>
                  <outputDirectory>${project.build.directory}/models/all-MiniLM-L6-v2</outputDirectory>
                  <outputFileName>model.onnx</outputFileName>
                  <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
                </configuration>
              </execution>
              <execution>
                <id>download-dense-tokenizer</id>
                <phase>generate-test-resources</phase>
                <goals><goal>wget</goal></goals>
                <configuration>
                  <url>https://huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/main/tokenizer.json</url>
                  <outputDirectory>${project.build.directory}/models/all-MiniLM-L6-v2</outputDirectory>
                  <outputFileName>tokenizer.json</outputFileName>
                  <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
                </configuration>
              </execution>
              <!-- SPLADE + Reranker model downloads — same as example-text-analysis -->
            </executions>
          </plugin>
        </plugins>
      </build>
    </profile>
  </profiles>

</project>
```

- [ ] **Step 4: Create directory structure**

```bash
mkdir -p examples/example-text-analysis/src/main/java/io/casehub/examples/analysis
mkdir -p examples/example-text-analysis/src/test/java/io/casehub/examples/analysis
mkdir -p examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag
mkdir -p examples/example-rag-pipeline/src/main/resources/corpus/tech
mkdir -p examples/example-rag-pipeline/src/main/resources/corpus/news
mkdir -p examples/example-rag-pipeline/src/main/resources/corpus/legal
mkdir -p examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag
```

- [ ] **Step 5: Verify scaffold builds**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -Pexamples-smoke -pl examples/example-text-analysis,examples/example-rag-pipeline -DskipTests
```

Expected: BUILD SUCCESS for both modules.

- [ ] **Step 6: Commit**

```bash
git add pom.xml examples/
git commit -m "chore(#N): scaffold examples modules — POMs, profiles, directory structure"
```

---

### Task 4: NliDemo — Smoke Tests (TDD)

**Files:**
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/NliDemoTest.java`
- Create: `examples/example-text-analysis/src/main/java/io/casehub/examples/analysis/NliDemo.java`

- [ ] **Step 1: Write the failing smoke test**

Create `NliDemoTest.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.tasks.NliClassifier;
import io.casehub.inference.tasks.NliLabel;
import io.casehub.inference.tasks.NliResult;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class NliDemoTest {

    @Test
    void allDomainsProduceResults() {
        var model = InMemoryInferenceModel.returning(0.1f, 0.2f, 0.7f);
        var nli = new NliClassifier(model);

        List<NliDemo.Result> results = NliDemo.run(nli);

        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(r -> {
            assertThat(r.domain()).isNotBlank();
            assertThat(r.premise()).isNotBlank();
            assertThat(r.hypothesis()).isNotBlank();
            assertThat(r.result().predicted()).isNotNull();
            assertThat(r.result().entailment() + r.result().neutral() + r.result().contradiction())
                .isCloseTo(1.0f, org.assertj.core.data.Offset.offset(1e-5f));
        });
    }

    @Test
    void coversAllThreeDomains() {
        var model = InMemoryInferenceModel.returning(0.1f, 0.2f, 0.7f);
        var nli = new NliClassifier(model);

        List<NliDemo.Result> results = NliDemo.run(nli);

        var domains = results.stream().map(NliDemo.Result::domain).distinct().toList();
        assertThat(domains).containsExactlyInAnyOrder("tech", "news", "legal");
    }

    @Test
    void includesEntailmentAndContradictionPairs() {
        var model = InMemoryInferenceModel.returning(0.1f, 0.2f, 0.7f);
        var nli = new NliClassifier(model);

        List<NliDemo.Result> results = NliDemo.run(nli);

        assertThat(results.size()).isGreaterThanOrEqualTo(6);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=NliDemoTest
```

Expected: FAIL — `NliDemo` class does not exist.

- [ ] **Step 3: Implement NliDemo**

Create `NliDemo.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.NliClassifier;
import io.casehub.inference.tasks.NliResult;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class NliDemo {

    public record Claim(String domain, String premise, String hypothesis) {}

    public record Result(String domain, String premise, String hypothesis, NliResult result) {}

    static final List<Claim> CLAIMS = List.of(
        new Claim("tech",  "CDI performs dependency injection at runtime using reflection.",
                           "CDI uses compile-time injection."),
        new Claim("tech",  "Quarkus supports both imperative and reactive programming models.",
                           "Quarkus is a framework for building Java applications."),
        new Claim("news",  "Interest rates were held steady at the latest policy meeting.",
                           "The central bank raised interest rates."),
        new Claim("news",  "Global temperatures rose by 1.2 degrees in 2025.",
                           "Climate change is accelerating."),
        new Claim("legal", "Early termination requires 90 days written notice.",
                           "The tenant may terminate the lease at will."),
        new Claim("legal", "The data processor shall implement appropriate technical measures.",
                           "Data protection requires security safeguards.")
    );

    public static List<Result> run(NliClassifier nli) {
        List<Result> results = new ArrayList<>();
        for (Claim claim : CLAIMS) {
            NliResult nliResult = nli.classify(claim.premise(), claim.hypothesis());
            results.add(new Result(claim.domain(), claim.premise(), claim.hypothesis(), nliResult));
        }
        return results;
    }

    public static void main(String[] args) {
        Path modelDir = Path.of("target/models/nli-deberta-v3-xsmall");
        try (InferenceModel model = new OnnxInferenceModel(
                new ModelConfig(modelDir.resolve("model.onnx"), modelDir.resolve("tokenizer.json")))) {
            var nli = new NliClassifier(model, 0, 1, 2);
            List<Result> results = run(nli);
            printResults(results);
        }
    }

    static void printResults(List<Result> results) {
        System.out.printf("%-6s %-55s %-55s %-14s %6s %6s %6s%n",
            "Domain", "Premise", "Hypothesis", "Predicted", "Ent", "Neu", "Con");
        System.out.println("-".repeat(200));
        for (Result r : results) {
            System.out.printf("%-6s %-55s %-55s %-14s %6.3f %6.3f %6.3f%n",
                r.domain(),
                truncate(r.premise(), 53),
                truncate(r.hypothesis(), 53),
                r.result().predicted(),
                r.result().entailment(),
                r.result().neutral(),
                r.result().contradiction());
        }
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max - 2) + "..";
    }
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=NliDemoTest
```

Expected: PASS — all 3 tests green.

- [ ] **Step 5: Commit**

```bash
git add examples/example-text-analysis/src/
git commit -m "feat(#N): NliDemo — premise/hypothesis analysis across tech, news, legal domains"
```

---

### Task 5: ZeroShotClassificationDemo — Smoke Tests (TDD)

**Files:**
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/ZeroShotClassificationDemoTest.java`
- Create: `examples/example-text-analysis/src/main/java/io/casehub/examples/analysis/ZeroShotClassificationDemo.java`

- [ ] **Step 1: Write the failing smoke test**

Create `ZeroShotClassificationDemoTest.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.tasks.NliClassifier;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class ZeroShotClassificationDemoTest {

    @Test
    void allTextsProduceRankedLabels() {
        var model = InMemoryInferenceModel.withFunction(3, input -> {
            String hypothesis = input.texts().get(1);
            if (hypothesis.contains("technology")) return new float[]{0.9f, 0.05f, 0.05f};
            if (hypothesis.contains("law")) return new float[]{0.7f, 0.1f, 0.2f};
            return new float[]{0.1f, 0.3f, 0.6f};
        });
        var nli = new NliClassifier(model, 0, 1, 2);

        List<ZeroShotClassificationDemo.Result> results = ZeroShotClassificationDemo.run(nli);

        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(r -> {
            assertThat(r.text()).isNotBlank();
            assertThat(r.topLabel()).isNotBlank();
            assertThat(r.scores()).isNotEmpty();
            assertThat(r.scores().values()).allSatisfy(score ->
                assertThat(score).isBetween(0.0f, 1.0f));
        });
    }

    @Test
    void coversAllThreeDomains() {
        var model = InMemoryInferenceModel.returning(0.3f, 0.3f, 0.4f);
        var nli = new NliClassifier(model);

        List<ZeroShotClassificationDemo.Result> results = ZeroShotClassificationDemo.run(nli);

        var domains = results.stream().map(ZeroShotClassificationDemo.Result::domain).distinct().toList();
        assertThat(domains).containsExactlyInAnyOrder("tech", "news", "legal");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=ZeroShotClassificationDemoTest
```

Expected: FAIL — `ZeroShotClassificationDemo` does not exist.

- [ ] **Step 3: Implement ZeroShotClassificationDemo**

Create `ZeroShotClassificationDemo.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.NliClassifier;
import io.casehub.inference.tasks.NliResult;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class ZeroShotClassificationDemo {

    record TextSample(String domain, String text) {}

    public record Result(String domain, String text, String topLabel, Map<String, Float> scores) {}

    static final List<String> CANDIDATE_LABELS = List.of(
        "technology", "finance", "law", "healthcare", "politics"
    );

    static final List<TextSample> SAMPLES = List.of(
        new TextSample("tech",  "Dependency injection decouples component creation from usage, allowing the container to manage lifecycle and scoping."),
        new TextSample("news",  "The Federal Reserve held interest rates steady, citing persistent inflation concerns and a resilient labor market."),
        new TextSample("legal", "Notwithstanding the provisions of subsection (b), the lessee shall not terminate prior to the expiration of the initial term.")
    );

    public static List<Result> run(NliClassifier nli) {
        List<Result> results = new ArrayList<>();
        for (TextSample sample : SAMPLES) {
            Map<String, Float> scores = new LinkedHashMap<>();
            for (String label : CANDIDATE_LABELS) {
                NliResult nliResult = nli.classify(sample.text(), "This text is about " + label + ".");
                scores.put(label, nliResult.entailment());
            }
            String topLabel = scores.entrySet().stream()
                .max(Map.Entry.comparingByValue())
                .map(Map.Entry::getKey)
                .orElseThrow();
            results.add(new Result(sample.domain(), sample.text(), topLabel, Map.copyOf(scores)));
        }
        return results;
    }

    public static void main(String[] args) {
        Path modelDir = Path.of("target/models/nli-deberta-v3-xsmall");
        try (InferenceModel model = new OnnxInferenceModel(
                new ModelConfig(modelDir.resolve("model.onnx"), modelDir.resolve("tokenizer.json")))) {
            var nli = new NliClassifier(model, 0, 1, 2);
            List<Result> results = run(nli);
            printResults(results);
        }
    }

    static void printResults(List<Result> results) {
        for (Result r : results) {
            System.out.printf("%n[%s] %s%n", r.domain(), truncate(r.text(), 100));
            System.out.printf("  Top label: %s%n", r.topLabel());
            r.scores().entrySet().stream()
                .sorted(Map.Entry.<String, Float>comparingByValue().reversed())
                .forEach(e -> System.out.printf("    %-15s %.3f%n", e.getKey(), e.getValue()));
        }
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max - 2) + "..";
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=ZeroShotClassificationDemoTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/example-text-analysis/src/
git commit -m "feat(#N): ZeroShotClassificationDemo — NLI-based zero-shot text classification"
```

---

### Task 6: ScoringDemo — Smoke Tests (TDD)

**Files:**
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/ScoringDemoTest.java`
- Create: `examples/example-text-analysis/src/main/java/io/casehub/examples/analysis/ScoringDemo.java`

- [ ] **Step 1: Write the failing smoke test**

Create `ScoringDemoTest.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.tasks.TextClassifier;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class ScoringDemoTest {

    @Test
    void sentimentDimensionProducesResults() {
        var model = InMemoryInferenceModel.returning(0.1f, 0.9f);
        var classifier = new TextClassifier(model, List.of("negative", "positive"));

        List<ScoringDemo.ScoredText> results = ScoringDemo.runSentiment(classifier);

        assertThat(results).hasSizeGreaterThanOrEqualTo(3);
        assertThat(results).allSatisfy(r -> {
            assertThat(r.text()).isNotBlank();
            assertThat(r.label()).isNotBlank();
            assertThat(r.score()).isBetween(0.0f, 1.0f);
        });
    }

    @Test
    void scoresSpanRange() {
        var model = InMemoryInferenceModel.withFunction(2, input -> {
            String text = input.texts().get(0);
            if (text.contains("terrible")) return new float[]{2.0f, -1.0f};
            if (text.contains("excellent")) return new float[]{-1.0f, 2.0f};
            return new float[]{0.1f, 0.1f};
        });
        var classifier = new TextClassifier(model, List.of("negative", "positive"));

        List<ScoringDemo.ScoredText> results = ScoringDemo.runSentiment(classifier);

        var scores = results.stream().map(ScoringDemo.ScoredText::score).toList();
        float min = scores.stream().min(Float::compare).orElseThrow();
        float max = scores.stream().max(Float::compare).orElseThrow();
        assertThat(max - min).isGreaterThan(0.1f);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=ScoringDemoTest
```

Expected: FAIL — `ScoringDemo` does not exist.

- [ ] **Step 3: Implement ScoringDemo**

Create `ScoringDemo.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.ClassificationResult;
import io.casehub.inference.tasks.TextClassifier;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public final class ScoringDemo {

    public record ScoredText(String text, String label, float score) {}

    static final List<String> SENTIMENT_TEXTS = List.of(
        "The service was absolutely terrible, I waited two hours and nobody came.",
        "The food was okay, nothing special but not bad either.",
        "The new version fixes every issue I had. Excellent work.",
        "Revenue declined 12% year over year in the third quarter."
    );

    static final List<String> TOXICITY_TEXTS = List.of(
        "I disagree with the proposed changes to the codebase.",
        "This is the worst code I have ever seen in my life.",
        "Can someone explain why this test is failing on CI?",
        "Anyone who writes code like this should be fired immediately."
    );

    public static List<ScoredText> runSentiment(TextClassifier classifier) {
        return classify(classifier, SENTIMENT_TEXTS);
    }

    public static List<ScoredText> runToxicity(TextClassifier classifier) {
        return classify(classifier, TOXICITY_TEXTS);
    }

    private static List<ScoredText> classify(TextClassifier classifier, List<String> texts) {
        List<ScoredText> results = new ArrayList<>();
        for (String text : texts) {
            ClassificationResult cr = classifier.classify(text);
            results.add(new ScoredText(text, cr.label(), cr.confidence()));
        }
        return results;
    }

    public static void main(String[] args) {
        Path sentimentDir = Path.of("target/models/distilbert-sst2");
        try (InferenceModel model = new OnnxInferenceModel(
                new ModelConfig(sentimentDir.resolve("model.onnx"), sentimentDir.resolve("tokenizer.json")))) {
            var classifier = new TextClassifier(model, List.of("negative", "positive"));

            System.out.println("=== Sentiment Scoring ===");
            printResults(runSentiment(classifier));
        }
    }

    static void printResults(List<ScoredText> results) {
        System.out.printf("%-70s %-12s %6s%n", "Text", "Label", "Score");
        System.out.println("-".repeat(92));
        for (ScoredText r : results) {
            System.out.printf("%-70s %-12s %6.3f%n",
                truncate(r.text(), 68), r.label(), r.score());
        }
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max - 2) + "..";
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=ScoringDemoTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/example-text-analysis/src/
git commit -m "feat(#N): ScoringDemo — sentiment and toxicity scoring with TextClassifier"
```

---

### Task 7: RerankingDemo — Smoke Tests (TDD)

**Files:**
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/RerankingDemoTest.java`
- Create: `examples/example-text-analysis/src/main/java/io/casehub/examples/analysis/RerankingDemo.java`

- [ ] **Step 1: Write the failing smoke test**

Create `RerankingDemoTest.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.tasks.CrossEncoderReranker;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class RerankingDemoTest {

    @Test
    void rerankProducesOrderedResults() {
        var model = InMemoryInferenceModel.withFunction(1, input -> {
            String candidate = input.texts().get(1);
            if (candidate.contains("ONNX")) return new float[]{0.95f};
            if (candidate.contains("inference")) return new float[]{0.7f};
            return new float[]{0.1f};
        });
        var reranker = new CrossEncoderReranker(model);

        RerankingDemo.RerankResult result = RerankingDemo.run(reranker);

        assertThat(result.query()).isNotBlank();
        assertThat(result.ranked()).isNotEmpty();
        assertThat(result.ranked().get(0).score())
            .isGreaterThanOrEqualTo(result.ranked().get(result.ranked().size() - 1).score());
    }

    @Test
    void candidatesSpanMultipleDomains() {
        var model = InMemoryInferenceModel.returning(0.5f);
        var reranker = new CrossEncoderReranker(model);

        RerankingDemo.RerankResult result = RerankingDemo.run(reranker);

        assertThat(result.candidates()).hasSizeGreaterThanOrEqualTo(6);
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=RerankingDemoTest
```

Expected: FAIL — `RerankingDemo` does not exist.

- [ ] **Step 3: Implement RerankingDemo**

Create `RerankingDemo.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.inference.tasks.RankedResult;

import java.nio.file.Path;
import java.util.List;

public final class RerankingDemo {

    public record RerankResult(String query, List<String> candidates, List<RankedResult> ranked) {}

    static final String QUERY = "How does ONNX inference work on the JVM?";

    static final List<String> CANDIDATES = List.of(
        "ONNX Runtime executes models directly inside the JVM via JNI, providing deterministic inference.",
        "CDI performs dependency injection at runtime using reflection and proxy generation.",
        "The Federal Reserve held interest rates steady at the latest policy meeting.",
        "Cross-encoder models process query-document pairs through every transformer layer for precise relevance scoring.",
        "Early termination of a lease requires 90 days written notice to the landlord.",
        "HuggingFace Tokenizers JNI provides fast tokenization for transformer models on the JVM.",
        "Global temperatures rose by 1.2 degrees Celsius in 2025 according to climate scientists.",
        "SPLADE uses masked language modeling to generate sparse learned vectors with implicit term expansion.",
        "The data processor shall implement appropriate technical and organisational security measures.",
        "Quarkus supports both imperative and reactive programming models for building cloud-native applications."
    );

    public static RerankResult run(CrossEncoderReranker reranker) {
        List<RankedResult> ranked = reranker.rerank(QUERY, CANDIDATES);
        return new RerankResult(QUERY, CANDIDATES, ranked);
    }

    public static void main(String[] args) {
        Path modelDir = Path.of("target/models/ms-marco-MiniLM-L-6-v2");
        try (InferenceModel model = new OnnxInferenceModel(
                new ModelConfig(modelDir.resolve("model.onnx"), modelDir.resolve("tokenizer.json")))) {
            var reranker = new CrossEncoderReranker(model);
            RerankResult result = run(reranker);
            printResults(result);
        }
    }

    static void printResults(RerankResult result) {
        System.out.printf("Query: %s%n%n", result.query());
        System.out.printf("%-4s %6s  %-4s  %s%n", "Rank", "Score", "Orig", "Candidate");
        System.out.println("-".repeat(120));
        for (int i = 0; i < result.ranked().size(); i++) {
            RankedResult r = result.ranked().get(i);
            System.out.printf("%-4d %6.3f  [%2d]  %s%n",
                i + 1, r.score(), r.originalIndex(), truncate(r.text(), 95));
        }
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max - 2) + "..";
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=RerankingDemoTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/example-text-analysis/src/
git commit -m "feat(#N): RerankingDemo — cross-encoder reranking across multi-domain candidates"
```

---

### Task 8: SparseEmbeddingDemo — Smoke Tests (TDD)

**Files:**
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/SparseEmbeddingDemoTest.java`
- Create: `examples/example-text-analysis/src/main/java/io/casehub/examples/analysis/SparseEmbeddingDemo.java`

- [ ] **Step 1: Write the failing smoke test**

Create `SparseEmbeddingDemoTest.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.splade.SparseEmbedder;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class SparseEmbeddingDemoTest {

    private static final int VOCAB_SIZE = 100;

    @Test
    void allTextsProduceSparseVectors() {
        float[] output = new float[VOCAB_SIZE];
        output[0] = 2.0f;
        output[5] = 1.5f;
        output[42] = 0.8f;
        var model = InMemoryInferenceModel.returning(output);
        var embedder = new SparseEmbedder(model);

        List<SparseEmbeddingDemo.EmbeddingResult> results = SparseEmbeddingDemo.run(embedder);

        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(r -> {
            assertThat(r.text()).isNotBlank();
            assertThat(r.sparseVector()).isNotEmpty();
            assertThat(r.sparseVector().values()).allSatisfy(v ->
                assertThat(v).isGreaterThan(0.0f));
        });
    }

    @Test
    void coversMultipleDomains() {
        float[] output = new float[VOCAB_SIZE];
        output[0] = 1.0f;
        var model = InMemoryInferenceModel.returning(output);
        var embedder = new SparseEmbedder(model);

        List<SparseEmbeddingDemo.EmbeddingResult> results = SparseEmbeddingDemo.run(embedder);

        var domains = results.stream().map(SparseEmbeddingDemo.EmbeddingResult::domain).distinct().toList();
        assertThat(domains).containsExactlyInAnyOrder("tech", "news", "legal");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=SparseEmbeddingDemoTest
```

Expected: FAIL — `SparseEmbeddingDemo` does not exist.

- [ ] **Step 3: Implement SparseEmbeddingDemo**

Create `SparseEmbeddingDemo.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.splade.SparseEmbedder;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Map;

public final class SparseEmbeddingDemo {

    record TextSample(String domain, String text) {}

    public record EmbeddingResult(String domain, String text, Map<Integer, Float> sparseVector) {}

    static final List<TextSample> SAMPLES = List.of(
        new TextSample("tech",  "How does dependency injection work in Quarkus applications?"),
        new TextSample("tech",  "ONNX Runtime provides cross-platform model execution via JNI."),
        new TextSample("news",  "The central bank announced a rate cut to stimulate economic growth."),
        new TextSample("news",  "AI regulation proposals are being debated across major economies."),
        new TextSample("legal", "The lessee may terminate the agreement with 30 days written notice."),
        new TextSample("legal", "Personal data must be processed in accordance with GDPR principles.")
    );

    public static List<EmbeddingResult> run(SparseEmbedder embedder) {
        List<EmbeddingResult> results = new ArrayList<>();
        for (TextSample sample : SAMPLES) {
            Map<Integer, Float> sparse = embedder.embed(sample.text());
            results.add(new EmbeddingResult(sample.domain(), sample.text(), sparse));
        }
        return results;
    }

    public static void main(String[] args) {
        Path modelDir = Path.of("target/models/splade");
        try (InferenceModel model = new OnnxInferenceModel(
                new ModelConfig(modelDir.resolve("model.onnx"), modelDir.resolve("tokenizer.json")))) {
            var embedder = new SparseEmbedder(model);
            List<EmbeddingResult> results = run(embedder);
            printResults(results);
        }
    }

    static void printResults(List<EmbeddingResult> results) {
        for (EmbeddingResult r : results) {
            System.out.printf("%n[%s] %s%n", r.domain(), r.text());
            System.out.printf("  Sparse vector: %d non-zero entries%n", r.sparseVector().size());
            System.out.printf("  Top-10 token indices by weight:%n");
            r.sparseVector().entrySet().stream()
                .sorted(Map.Entry.<Integer, Float>comparingByValue().reversed())
                .limit(10)
                .forEach(e -> System.out.printf("    token[%5d] = %.4f%n", e.getKey(), e.getValue()));
        }
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=SparseEmbeddingDemoTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/example-text-analysis/src/
git commit -m "feat(#N): SparseEmbeddingDemo — SPLADE sparse embeddings with top-weighted terms"
```

---

### Task 9: Edge Case Tests for example-text-analysis

**Files:**
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/EdgeCaseTest.java`

- [ ] **Step 1: Write edge case tests**

Create `EdgeCaseTest.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.inmem.InMemoryInferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.ModelLoadException;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.NliClassifier;
import io.casehub.inference.tasks.TextClassifier;
import io.casehub.inference.tasks.CrossEncoderReranker;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@Tag("smoke")
class EdgeCaseTest {

    @Test
    void nliHandlesEmptyStrings() {
        var model = InMemoryInferenceModel.returning(0.3f, 0.3f, 0.4f);
        var nli = new NliClassifier(model);
        var result = nli.classify("", "");
        assertThat(result.predicted()).isNotNull();
    }

    @Test
    void classifierHandlesEmptyString() {
        var model = InMemoryInferenceModel.returning(0.5f, 0.5f);
        var classifier = new TextClassifier(model, List.of("a", "b"));
        var result = classifier.classify("");
        assertThat(result.label()).isNotNull();
    }

    @Test
    void rerankerHandlesSingleCandidate() {
        var model = InMemoryInferenceModel.returning(0.5f);
        var reranker = new CrossEncoderReranker(model);
        var results = reranker.rerank("query", List.of("only one"));
        assertThat(results).hasSize(1);
    }

    @Test
    void missingModelFileThrowsModelLoadException() {
        assertThatThrownBy(() -> new OnnxInferenceModel(
                new ModelConfig(Path.of("nonexistent/model.onnx"), Path.of("nonexistent/tokenizer.json"))))
            .isInstanceOf(ModelLoadException.class);
    }
}
```

- [ ] **Step 2: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-text-analysis -Dtest=EdgeCaseTest
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add examples/example-text-analysis/src/test/
git commit -m "test(#N): edge case tests for example-text-analysis — empty strings, missing models"
```

---

### Task 10: Sample Corpus Documents for RAG Pipeline

**Files:**
- Create: 15 markdown files in `examples/example-rag-pipeline/src/main/resources/corpus/`

- [ ] **Step 1: Write tech domain documents**

Create 5 files in `examples/example-rag-pipeline/src/main/resources/corpus/tech/`:

**`cdi-injection.md`:**
```markdown
---
title: CDI Dependency Injection
domain: tech
tags: cdi, quarkus, injection
---

Contexts and Dependency Injection (CDI) is the standard dependency injection framework for Jakarta EE and Quarkus applications. CDI manages bean lifecycle and scoping through annotations like @ApplicationScoped, @RequestScoped, and @Inject. The container creates and destroys bean instances automatically based on their declared scope.

Unlike compile-time injection frameworks, CDI performs injection at runtime using reflection and proxy generation. This allows for dynamic bean resolution, producer methods, and interceptor chains. Quarkus optimizes this at build time through its ArC CDI implementation, which does compile-time bean discovery and generates bytecode instead of using reflection at runtime.

Key concepts include qualifiers for disambiguating beans, alternatives for environment-specific overrides, and events for decoupled communication between components.
```

**`quarkus-lifecycle.md`:**
```markdown
---
title: Quarkus Application Lifecycle
domain: tech
tags: quarkus, lifecycle, startup
---

Quarkus applications follow a distinct lifecycle with build-time and runtime phases. During the build phase, extensions perform class scanning, bytecode generation, and configuration processing. This moves work from runtime to build time, reducing startup latency and memory footprint.

The runtime phase begins with the StartupEvent, which signals that the CDI container is fully initialized and all beans are available. Shutdown is signaled via ShutdownEvent, giving beans an opportunity to release resources cleanly. The @PostConstruct and @PreDestroy lifecycle callbacks work as expected within CDI-managed beans.

For long-running processes, the @Scheduled annotation provides cron-like periodic task execution managed by the Quarkus scheduler subsystem.
```

**`onnx-runtime-basics.md`:**
```markdown
---
title: ONNX Runtime on the JVM
domain: tech
tags: onnx, inference, jvm
---

ONNX Runtime provides cross-platform inference for machine learning models exported in the Open Neural Network Exchange format. On the JVM, it operates through JNI bindings that load the native ONNX Runtime library. Models are loaded as OrtSession instances that accept tensor inputs and produce tensor outputs.

The inference pipeline consists of tokenization (converting text to token IDs via HuggingFace Tokenizers JNI), tensor construction (building input_ids and attention_mask tensors), session execution (running the ONNX graph), and output interpretation (reading float arrays from output tensors).

Thread safety is guaranteed by the OrtSession, which supports concurrent inference calls from multiple threads. Model loading is expensive but inference is fast — typically single-digit milliseconds for small transformer models on modern hardware.
```

**`rest-endpoint-design.md`:**
```markdown
---
title: REST Endpoint Design Patterns
domain: tech
tags: rest, api, design
---

RESTful API design in Quarkus uses JAX-RS annotations to map HTTP methods and paths to Java methods. The @Path annotation defines the base URI, while @GET, @POST, @PUT, and @DELETE map specific operations. Request and response bodies are serialized via Jackson or JSON-B.

Input validation combines Bean Validation annotations (@NotNull, @Size, @Valid) with Quarkus's built-in validation integration. Invalid requests receive a 400 response with structured error details. Path parameters use @PathParam, query parameters use @QueryParam, and headers use @HeaderParam.

Error handling follows the problem details RFC 7807 pattern, returning structured JSON with type, title, status, and detail fields. Global exception mappers convert domain exceptions to appropriate HTTP responses.
```

**`reactive-streams.md`:**
```markdown
---
title: Reactive Streams with Mutiny
domain: tech
tags: reactive, mutiny, vertx
---

Mutiny is the reactive programming library used by Quarkus for non-blocking, event-driven code. It provides two core types: Uni for single-value asynchronous operations and Multi for streams of values. Both support composition through operators like map, flatMap, and onFailure.

Reactive code runs on the Vert.x event loop, which means blocking operations must be offloaded to worker threads using @Blocking or Uni.emitOn(). Failing to do so blocks the event loop and degrades throughput for all requests sharing that loop.

The blocking-to-reactive bridge pattern wraps synchronous code in Uni.createFrom().item(() -> blockingCall()).emitOn(Infrastructure.getDefaultWorkerPool()), making it safe for event-loop consumers while keeping the implementation straightforward.
```

- [ ] **Step 2: Write news domain documents**

Create 5 files in `examples/example-rag-pipeline/src/main/resources/corpus/news/`:

**`central-bank-rates.md`:**
```markdown
---
title: Central Bank Holds Interest Rates Steady
domain: news
tags: economy, rates, monetary-policy
---

The Federal Reserve held its benchmark interest rate unchanged at the conclusion of its latest two-day policy meeting. The decision was widely expected by markets, with futures pricing reflecting a 95% probability of a hold before the announcement.

In the post-meeting statement, the committee cited persistent inflation above the 2% target and a resilient labor market as key factors. Chair Powell noted that while inflation has moderated from its peak, the pace of decline has slowed in recent months. The committee projects two rate cuts later in the year, contingent on continued progress toward the inflation target.

Bond yields fell modestly following the announcement, with the 10-year Treasury dropping 5 basis points.
```

**`tech-earnings-q1.md`:**
```markdown
---
title: Tech Sector Q1 Earnings Beat Expectations
domain: news
tags: technology, earnings, markets
---

Major technology companies reported first-quarter earnings that broadly exceeded analyst expectations, driven by strong cloud computing revenue and growing demand for AI infrastructure. Cloud spending across the three largest providers grew 28% year over year, with AI-related workloads accounting for a growing share of new deployments.

Hardware companies benefited from continued investment in GPU clusters and inference accelerators. Revenue from data center GPUs doubled compared to the prior year, though management cautioned that growth rates may moderate as enterprise customers complete initial infrastructure buildouts.

Advertising revenue showed mixed results, with search advertising growing while social media platforms reported softer spending from small and medium businesses.
```

**`climate-summit.md`:**
```markdown
---
title: Climate Summit Reaches Agreement on Emissions Framework
domain: news
tags: climate, environment, policy
---

Delegates from 195 countries reached consensus on a new emissions reduction framework at the annual climate summit. The agreement establishes binding targets for developed nations to reduce greenhouse gas emissions by 45% from 2005 levels by 2035, with differentiated timelines for developing economies.

The framework introduces a carbon border adjustment mechanism that applies tariffs to imports from countries without equivalent carbon pricing. Critics argue the mechanism could disrupt trade relationships, while supporters say it prevents carbon leakage — the shift of production to countries with weaker environmental standards.

Financing commitments for climate adaptation in vulnerable nations were increased to $150 billion annually, though several delegations noted this falls short of estimated needs.
```

**`ai-regulation.md`:**
```markdown
---
title: AI Regulation Proposals Advance in Legislature
domain: news
tags: ai, regulation, policy
---

A bipartisan legislative proposal for AI regulation advanced through committee, establishing transparency requirements for high-risk AI systems. The bill requires developers of AI systems used in employment, credit, and healthcare decisions to conduct and publish impact assessments before deployment.

Key provisions include mandatory disclosure of training data sources, algorithmic audit requirements by independent third parties, and a right of explanation for individuals affected by automated decisions. The bill exempts AI systems used purely for research purposes and low-risk applications like spam filtering and content recommendation.

Industry groups expressed mixed reactions, with some supporting the clarity of a federal framework while others argued the compliance burden could disadvantage smaller companies relative to large incumbents.
```

**`supply-chain.md`:**
```markdown
---
title: Global Supply Chains Adapt to Shifting Trade Patterns
domain: news
tags: trade, supply-chain, economics
---

Global supply chain patterns continued to shift as manufacturers diversified production away from concentrated single-country sourcing. Southeast Asian economies saw increased foreign direct investment in manufacturing capacity, particularly in electronics assembly and automotive components.

Shipping costs stabilized after two years of elevated rates, though port congestion in several major hubs remained a concern. Container volumes through the Suez Canal recovered to pre-disruption levels, reducing transit times for Europe-Asia trade routes.

Inventory strategies shifted from just-in-time toward just-in-case, with companies maintaining larger safety stocks of critical components. This increased working capital requirements but reduced the frequency of production stoppages due to supply disruptions.
```

- [ ] **Step 3: Write legal domain documents**

Create 5 files in `examples/example-rag-pipeline/src/main/resources/corpus/legal/`:

**`lease-termination.md`:**
```markdown
---
title: Lease Termination Provisions
domain: legal
tags: lease, termination, notice
---

Early termination of a commercial lease requires strict compliance with the notice provisions set forth in the agreement. The lessee must provide written notice to the lessor not fewer than 90 calendar days prior to the intended termination date. Notice must be delivered by registered mail or recognized courier service to the address specified in the lease.

The lessee remains liable for all rent and charges accruing through the termination date, plus an early termination fee equal to three months' base rent. The security deposit shall be applied against any outstanding obligations, with any remainder returned within 30 days of the termination date.

Notwithstanding the foregoing, the lessee may terminate without penalty if the premises become unfit for the permitted use due to circumstances beyond the lessee's control.
```

**`data-protection.md`:**
```markdown
---
title: Data Protection Obligations
domain: legal
tags: gdpr, data, privacy
---

The data processor shall implement appropriate technical and organizational measures to ensure a level of security appropriate to the risk. Such measures shall include, as appropriate, pseudonymization and encryption of personal data, the ability to ensure ongoing confidentiality and integrity, the ability to restore availability and access to personal data in a timely manner, and a process for regularly testing and evaluating the effectiveness of measures.

Processing shall be carried out only on documented instructions from the data controller, including with regard to transfers of personal data to a third country. The processor shall ensure that persons authorized to process personal data have committed themselves to confidentiality or are under an appropriate statutory obligation of confidentiality.

In the event of a personal data breach, the processor shall notify the controller without undue delay after becoming aware of the breach.
```

**`employment-notice.md`:**
```markdown
---
title: Employment Notice Period Requirements
domain: legal
tags: employment, notice, termination
---

Either party may terminate the employment relationship by providing written notice in accordance with the applicable notice period. For employees with less than two years of continuous service, the minimum notice period is one month. For employees with two to five years of service, the notice period is two months. For employees with more than five years of service, the notice period is three months.

During the notice period, the employee shall continue to perform their duties and the employer shall continue to provide compensation and benefits. The employer may, at its discretion, place the employee on garden leave during all or part of the notice period, during which the employee remains employed but is not required to attend the workplace.

Payment in lieu of notice may be made at the employer's election, calculated as the employee's base salary plus the average of variable compensation received during the preceding twelve months.
```

**`liability-limitation.md`:**
```markdown
---
title: Limitation of Liability Clauses
domain: legal
tags: liability, indemnification, damages
---

The total aggregate liability of the service provider under this agreement shall not exceed the total fees paid by the customer during the twelve-month period immediately preceding the event giving rise to the claim. This limitation applies regardless of the form of action, whether in contract, tort, strict liability, or otherwise.

In no event shall either party be liable for any indirect, incidental, special, consequential, or punitive damages, including but not limited to loss of profits, loss of data, business interruption, or loss of goodwill, even if such party has been advised of the possibility of such damages.

The limitations set forth in this section shall not apply to breaches of confidentiality obligations, indemnification obligations for third-party intellectual property claims, or liability arising from willful misconduct or gross negligence.
```

**`intellectual-property.md`:**
```markdown
---
title: Intellectual Property Assignment
domain: legal
tags: ip, assignment, copyright
---

All intellectual property created by the contractor in the performance of services under this agreement shall be the sole and exclusive property of the client. The contractor hereby assigns to the client all right, title, and interest in and to all work product, including all patent rights, copyrights, trade secret rights, and other intellectual property rights therein.

The contractor shall execute all documents and take all actions reasonably requested by the client to perfect the client's ownership rights in the work product. The contractor warrants that the work product is original, does not infringe the intellectual property rights of any third party, and is free from encumbrances.

The contractor retains the right to use general knowledge, skills, and experience acquired during the engagement, provided that such use does not involve disclosure of the client's confidential information or reproduction of the work product.
```

- [ ] **Step 4: Commit**

```bash
git add examples/example-rag-pipeline/src/main/resources/corpus/
git commit -m "feat(#N): sample corpus documents — 15 markdown files across tech, news, legal domains"
```

---

### Task 11: RAG Pipeline — CDI Wiring and Test Infrastructure

**Files:**
- Create: `examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag/ExampleModelProducer.java`
- Create: `examples/example-rag-pipeline/src/main/resources/application.properties`
- Create: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/TestCurrentPrincipal.java`
- Create: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/CorpusTestSupport.java`

- [ ] **Step 1: Create ExampleModelProducer**

Create `ExampleModelProducer.java`:

```java
package io.casehub.examples.rag;

import dev.langchain4j.model.embedding.EmbeddingModel;
import dev.langchain4j.model.embedding.onnx.OnnxEmbeddingModel;
import dev.langchain4j.model.embedding.onnx.PoolingMode;
import io.casehub.inference.InferenceModel;
import io.casehub.inference.quarkus.Inference;
import io.casehub.inference.splade.SparseEmbedder;
import io.casehub.inference.tasks.CrossEncoderReranker;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;

import java.nio.file.Path;

@ApplicationScoped
public class ExampleModelProducer {

    @Produces
    @ApplicationScoped
    EmbeddingModel denseModel() {
        return new OnnxEmbeddingModel(
            Path.of("target/models/all-MiniLM-L6-v2/model.onnx"),
            Path.of("target/models/all-MiniLM-L6-v2/tokenizer.json"),
            PoolingMode.MEAN);
    }

    @Produces
    @ApplicationScoped
    SparseEmbedder sparseEmbedder(@Inference("splade") InferenceModel model) {
        return new SparseEmbedder(model);
    }

    @Produces
    @ApplicationScoped
    CrossEncoderReranker reranker(@Inference("reranker") InferenceModel model) {
        return new CrossEncoderReranker(model);
    }
}
```

- [ ] **Step 2: Create application.properties**

Create `examples/example-rag-pipeline/src/main/resources/application.properties`:

```properties
# Inference model paths (used by InferenceModelProducer from inference-quarkus)
casehub.inference.models.splade.model-path=target/models/splade/model.onnx
casehub.inference.models.splade.tokenizer-path=target/models/splade/tokenizer.json
casehub.inference.models.reranker.model-path=target/models/ms-marco-MiniLM-L-6-v2/model.onnx
casehub.inference.models.reranker.tokenizer-path=target/models/ms-marco-MiniLM-L-6-v2/tokenizer.json

# RAG config
casehub.rag.tenancy-strategy=PREFIX
casehub.rag.dense-vector-name=dense
casehub.rag.sparse-vector-name=sparse
casehub.rag.retrieval.dense-top-k=20
casehub.rag.retrieval.sparse-top-k=20
casehub.rag.retrieval.rrf-k=60
casehub.rag.retrieval.rerank-enabled=true
casehub.rag.retrieval.rerank-top-n=50

# Qdrant
casehub.rag.qdrant.host=localhost
casehub.rag.qdrant.port=6334

# Ingestion
casehub.rag.ingestion.mode=manual
```

- [ ] **Step 3: Create TestCurrentPrincipal**

Create `TestCurrentPrincipal.java`:

```java
package io.casehub.examples.rag;

import io.casehub.platform.api.identity.CurrentPrincipal;

import jakarta.annotation.Priority;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Alternative;

import java.util.Set;

@Alternative
@Priority(1)
@ApplicationScoped
public class TestCurrentPrincipal implements CurrentPrincipal {

    @Override
    public String actorId() {
        return "test-actor";
    }

    @Override
    public Set<String> groups() {
        return Set.of();
    }

    @Override
    public String tenancyId() {
        return "demo-tenant";
    }

    @Override
    public boolean isCrossTenantAdmin() {
        return false;
    }
}
```

- [ ] **Step 4: Create CorpusTestSupport utility**

Create `CorpusTestSupport.java`:

```java
package io.casehub.examples.rag;

import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public final class CorpusTestSupport {

    private static final List<String> CORPUS_FILES = List.of(
        "corpus/tech/cdi-injection.md",
        "corpus/tech/quarkus-lifecycle.md",
        "corpus/tech/onnx-runtime-basics.md",
        "corpus/tech/rest-endpoint-design.md",
        "corpus/tech/reactive-streams.md",
        "corpus/news/central-bank-rates.md",
        "corpus/news/tech-earnings-q1.md",
        "corpus/news/climate-summit.md",
        "corpus/news/ai-regulation.md",
        "corpus/news/supply-chain.md",
        "corpus/legal/lease-termination.md",
        "corpus/legal/data-protection.md",
        "corpus/legal/employment-notice.md",
        "corpus/legal/liability-limitation.md",
        "corpus/legal/intellectual-property.md"
    );

    private CorpusTestSupport() {}

    public static Path copyCorpusToTempDir() throws IOException {
        Path tempDir = Files.createTempDirectory("example-corpus-");
        for (String file : CORPUS_FILES) {
            Path target = tempDir.resolve(file.substring("corpus/".length()));
            Files.createDirectories(target.getParent());
            try (InputStream is = CorpusTestSupport.class.getClassLoader().getResourceAsStream(file)) {
                if (is == null) throw new IllegalStateException("Missing classpath resource: " + file);
                Files.copy(is, target);
            }
        }
        return tempDir;
    }

    public static int documentCount() {
        return CORPUS_FILES.size();
    }
}
```

- [ ] **Step 5: Verify compilation**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile test-compile -Pexamples-smoke -pl examples/example-rag-pipeline
```

Expected: BUILD SUCCESS (compilation only — no tests yet).

Note: `ExampleModelProducer` may fail to compile if `langchain4j-embeddings` doesn't resolve. If so, the `EmbeddingModel` producer needs to be adjusted after Task 2 model research confirms the exact API. For smoke tests, `ExampleModelProducer` is not used — it's only active under `@QuarkusTest` integration tests.

- [ ] **Step 6: Commit**

```bash
git add examples/example-rag-pipeline/src/
git commit -m "feat(#N): RAG pipeline CDI wiring — ExampleModelProducer, TestCurrentPrincipal, CorpusTestSupport"
```

---

### Task 12: FlatCorpusIngestDemo — Smoke Tests (TDD)

**Files:**
- Create: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/FlatCorpusIngestSmokeTest.java`
- Create: `examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag/FlatCorpusIngestDemo.java`

- [ ] **Step 1: Write the failing smoke test**

Create `FlatCorpusIngestSmokeTest.java`:

```java
package io.casehub.examples.rag;

import dev.langchain4j.data.document.splitter.DocumentSplitters;
import io.casehub.corpus.zip.FlatChangeSource;
import io.casehub.corpus.zip.FlatCorpusStore;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.runtime.CorpusIngestionBinding;
import io.casehub.rag.runtime.CorpusIngestionService;
import io.casehub.rag.runtime.YamlFrontmatterExtractor;
import io.casehub.rag.testing.InMemoryCursorStore;
import io.casehub.rag.testing.InMemoryEmbeddingIngestor;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class FlatCorpusIngestSmokeTest {

    private static final CorpusRef CORPUS = new CorpusRef("demo-tenant", "examples");

    private InMemoryEmbeddingIngestor ingestor;
    private InMemoryCursorStore cursorStore;

    @BeforeEach
    void setUp() {
        ingestor = new InMemoryEmbeddingIngestor();
        cursorStore = new InMemoryCursorStore();
    }

    @Test
    void ingestsAllDocuments(@TempDir Path tempDir) throws IOException {
        Path corpusDir = CorpusTestSupport.copyCorpusToTempDir();
        var store = new FlatCorpusStore(corpusDir);
        var changeSource = new FlatChangeSource(corpusDir);
        var binding = new CorpusIngestionBinding(
            "examples", CORPUS, changeSource, store, new YamlFrontmatterExtractor());

        var service = new CorpusIngestionService(ingestor, cursorStore);
        service.processBinding(binding, DocumentSplitters.recursive(500, 50));

        assertThat(ingestor.getChunks(CORPUS)).isNotEmpty();
        assertThat(ingestor.listDocuments(CORPUS)).hasSize(CorpusTestSupport.documentCount());
    }

    @Test
    void incrementalIngestProducesNoNewChunks(@TempDir Path tempDir) throws IOException {
        Path corpusDir = CorpusTestSupport.copyCorpusToTempDir();
        var store = new FlatCorpusStore(corpusDir);
        var changeSource = new FlatChangeSource(corpusDir);
        var binding = new CorpusIngestionBinding(
            "examples", CORPUS, changeSource, store, new YamlFrontmatterExtractor());

        var service = new CorpusIngestionService(ingestor, cursorStore);
        var splitter = DocumentSplitters.recursive(500, 50);

        service.processBinding(binding, splitter);
        int firstRunChunks = ingestor.getChunks(CORPUS).size();

        service.processBinding(binding, splitter);
        int secondRunChunks = ingestor.getChunks(CORPUS).size();

        assertThat(secondRunChunks).isEqualTo(firstRunChunks);
    }

    @Test
    void metadataExtractedFromFrontmatter(@TempDir Path tempDir) throws IOException {
        Path corpusDir = CorpusTestSupport.copyCorpusToTempDir();
        var store = new FlatCorpusStore(corpusDir);
        var changeSource = new FlatChangeSource(corpusDir);
        var binding = new CorpusIngestionBinding(
            "examples", CORPUS, changeSource, store, new YamlFrontmatterExtractor());

        var service = new CorpusIngestionService(ingestor, cursorStore);
        service.processBinding(binding, DocumentSplitters.recursive(500, 50));

        var chunks = ingestor.getChunks(CORPUS);
        var chunkWithMetadata = chunks.stream()
            .filter(c -> c.metadata().containsKey("domain"))
            .findFirst();
        assertThat(chunkWithMetadata).isPresent();
        assertThat(chunkWithMetadata.get().metadata().get("domain"))
            .isIn("tech", "news", "legal");
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-rag-pipeline -Dtest=FlatCorpusIngestSmokeTest
```

Expected: FAIL — `FlatCorpusIngestDemo` does not exist. (Tests don't actually depend on the demo class yet — they use `CorpusIngestionService` directly. If they compile and run, that's fine. If `FlatChangeSource` import doesn't resolve, check that `casehub-corpus` is on the classpath.)

- [ ] **Step 3: Implement FlatCorpusIngestDemo**

Create `FlatCorpusIngestDemo.java`:

```java
package io.casehub.examples.rag;

import dev.langchain4j.data.document.DocumentSplitter;
import dev.langchain4j.data.document.splitter.DocumentSplitters;
import io.casehub.corpus.zip.FlatChangeSource;
import io.casehub.corpus.zip.FlatCorpusStore;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.CursorStore;
import io.casehub.rag.EmbeddingIngestor;
import io.casehub.rag.runtime.CorpusIngestionBinding;
import io.casehub.rag.runtime.CorpusIngestionService;
import io.casehub.rag.runtime.YamlFrontmatterExtractor;

import java.io.IOException;
import java.nio.file.Path;

public final class FlatCorpusIngestDemo {

    public static void run(EmbeddingIngestor ingestor, CursorStore cursorStore, Path corpusDir) {
        var store = new FlatCorpusStore(corpusDir);
        var changeSource = new FlatChangeSource(corpusDir);
        var binding = new CorpusIngestionBinding(
            "examples",
            new CorpusRef("demo-tenant", "examples"),
            changeSource,
            store,
            new YamlFrontmatterExtractor()
        );

        var service = new CorpusIngestionService(ingestor, cursorStore);
        DocumentSplitter splitter = DocumentSplitters.recursive(500, 50);

        System.out.println("=== Initial Ingestion ===");
        service.processBinding(binding, splitter);
        System.out.println("Ingestion complete.");

        System.out.println("\n=== Incremental Ingestion (no changes) ===");
        service.processBinding(binding, splitter);
        System.out.println("No new documents processed — cursor is current.");
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-rag-pipeline -Dtest=FlatCorpusIngestSmokeTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/example-rag-pipeline/src/
git commit -m "feat(#N): FlatCorpusIngestDemo — flat storage ingestion with incremental processing"
```

---

### Task 13: ZipCorpusIngestDemo — Smoke Tests (TDD)

**Files:**
- Create: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/ZipCorpusIngestSmokeTest.java`
- Create: `examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag/ZipCorpusIngestDemo.java`

- [ ] **Step 1: Write the failing smoke test**

Create `ZipCorpusIngestSmokeTest.java`:

```java
package io.casehub.examples.rag;

import io.casehub.corpus.zip.ChainManifest;
import io.casehub.corpus.zip.CompactionMode;
import io.casehub.corpus.zip.Compactor;
import io.casehub.corpus.zip.CorpusConfig;
import io.casehub.corpus.zip.ZipChangeSource;
import io.casehub.corpus.zip.ZipCorpusStore;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.runtime.CorpusIngestionBinding;
import io.casehub.rag.runtime.CorpusIngestionService;
import io.casehub.rag.runtime.YamlFrontmatterExtractor;
import io.casehub.rag.testing.InMemoryCursorStore;
import io.casehub.rag.testing.InMemoryEmbeddingIngestor;

import dev.langchain4j.data.document.splitter.DocumentSplitters;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class ZipCorpusIngestSmokeTest {

    private static final CorpusRef CORPUS = new CorpusRef("demo-tenant", "zip-examples");

    @Test
    void zipIngestAndCompaction(@TempDir Path tempDir) throws IOException {
        var config = new CorpusConfig("zip-examples", tempDir, 1024);
        var store = new ZipCorpusStore(config);

        store.append("docs/readme.md", "---\ntitle: Test\ndomain: tech\n---\nHello world.".getBytes());
        store.append("docs/guide.md", "---\ntitle: Guide\ndomain: tech\n---\nA guide.".getBytes());
        store.delete("docs/guide.md");
        store.append("docs/api.md", "---\ntitle: API\ndomain: tech\n---\nAPI reference.".getBytes());

        // Force rollover by exceeding maxZipSize
        byte[] payload = new byte[400];
        new java.util.Random(42).nextBytes(payload);
        store.append("rollover1.bin", payload);
        store.append("rollover2.bin", payload);
        store.append("rollover3.bin", payload);

        var manifest = ChainManifest.load(tempDir.resolve("chain.json"));
        var closedEntry = manifest.entries().stream()
            .filter(e -> "closed".equals(e.status()))
            .filter(e -> e.replacedBy() == null)
            .findFirst()
            .orElseThrow();

        Compactor.compact(tempDir.resolve(closedEntry.file()),
            CompactionMode.TOMBSTONES_ONLY, manifest, tempDir);

        var reloadedStore = new ZipCorpusStore(config);
        assertThat(reloadedStore.exists("docs/readme.md")).isTrue();
        assertThat(reloadedStore.exists("docs/api.md")).isTrue();
        assertThat(reloadedStore.exists("docs/guide.md")).isFalse();
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-rag-pipeline -Dtest=ZipCorpusIngestSmokeTest
```

- [ ] **Step 3: Implement ZipCorpusIngestDemo**

Create `ZipCorpusIngestDemo.java`:

```java
package io.casehub.examples.rag;

import dev.langchain4j.data.document.DocumentSplitter;
import dev.langchain4j.data.document.splitter.DocumentSplitters;
import io.casehub.corpus.zip.ChainManifest;
import io.casehub.corpus.zip.CompactionMode;
import io.casehub.corpus.zip.Compactor;
import io.casehub.corpus.zip.CorpusConfig;
import io.casehub.corpus.zip.ZipChangeSource;
import io.casehub.corpus.zip.ZipCorpusStore;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.CursorStore;
import io.casehub.rag.EmbeddingIngestor;
import io.casehub.rag.runtime.CorpusIngestionBinding;
import io.casehub.rag.runtime.CorpusIngestionService;
import io.casehub.rag.runtime.YamlFrontmatterExtractor;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;

public final class ZipCorpusIngestDemo {

    public static void run(EmbeddingIngestor ingestor, CursorStore cursorStore, Path corpusDir) throws IOException {
        var config = new CorpusConfig("zip-examples", corpusDir, 4096);
        var store = new ZipCorpusStore(config);

        System.out.println("=== Writing documents to ZIP corpus ===");
        Path sourceDir = CorpusTestSupport.copyCorpusToTempDir();
        Files.walk(sourceDir)
            .filter(Files::isRegularFile)
            .forEach(file -> {
                try {
                    String relativePath = sourceDir.relativize(file).toString();
                    store.append(relativePath, Files.readAllBytes(file));
                } catch (IOException e) {
                    throw new java.io.UncheckedIOException(e);
                }
            });

        var changeSource = new ZipChangeSource(store);
        var binding = new CorpusIngestionBinding(
            "zip-examples",
            new CorpusRef("demo-tenant", "zip-examples"),
            changeSource,
            store,
            new YamlFrontmatterExtractor()
        );

        var service = new CorpusIngestionService(ingestor, cursorStore);
        DocumentSplitter splitter = DocumentSplitters.recursive(500, 50);

        System.out.println("=== Ingesting from ZIP corpus ===");
        service.processBinding(binding, splitter);
        System.out.println("Ingestion complete.");
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-rag-pipeline -Dtest=ZipCorpusIngestSmokeTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/example-rag-pipeline/src/
git commit -m "feat(#N): ZipCorpusIngestDemo — ZIP storage with tombstone compaction"
```

---

### Task 14: HybridSearchDemo — Smoke Tests (TDD)

**Files:**
- Create: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/HybridSearchSmokeTest.java`
- Create: `examples/example-rag-pipeline/src/main/java/io/casehub/examples/rag/HybridSearchDemo.java`

- [ ] **Step 1: Write the failing smoke test**

Create `HybridSearchSmokeTest.java`:

```java
package io.casehub.examples.rag;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;
import io.casehub.rag.testing.InMemoryCaseRetriever;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class HybridSearchSmokeTest {

    @Test
    void allQueriesProduceFormattedOutput() {
        var retriever = new InMemoryCaseRetriever();
        var corpus = new CorpusRef("demo-tenant", "examples");
        retriever.addChunk(corpus, new RetrievedChunk(
            "CDI performs dependency injection at runtime.",
            "tech/cdi-injection.md", 0.85, Map.of("domain", "tech")));
        retriever.addChunk(corpus, new RetrievedChunk(
            "The Federal Reserve held rates steady.",
            "news/central-bank-rates.md", 0.72, Map.of("domain", "news")));
        retriever.addChunk(corpus, new RetrievedChunk(
            "Early termination requires 90 days notice.",
            "legal/lease-termination.md", 0.68, Map.of("domain", "legal")));

        List<HybridSearchDemo.SearchResult> results = HybridSearchDemo.run(retriever, corpus);

        assertThat(results).hasSize(3);
        assertThat(results).allSatisfy(r -> {
            assertThat(r.query()).isNotBlank();
            assertThat(r.chunks()).isNotEmpty();
        });
    }
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-rag-pipeline -Dtest=HybridSearchSmokeTest
```

Expected: FAIL — `HybridSearchDemo` does not exist.

- [ ] **Step 3: Implement HybridSearchDemo**

Create `HybridSearchDemo.java`:

```java
package io.casehub.examples.rag;

import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.RetrievedChunk;

import java.util.ArrayList;
import java.util.List;

public final class HybridSearchDemo {

    public record SearchResult(String query, List<RetrievedChunk> chunks) {}

    static final List<String> QUERIES = List.of(
        "How does dependency injection work?",
        "What happened with interest rates?",
        "Can I end my lease early?"
    );

    public static List<SearchResult> run(CaseRetriever retriever, CorpusRef corpus) {
        List<SearchResult> results = new ArrayList<>();
        for (String query : QUERIES) {
            List<RetrievedChunk> chunks = retriever.retrieve(query, corpus, 5);
            results.add(new SearchResult(query, chunks));
        }
        return results;
    }

    public static void printResults(List<SearchResult> results) {
        for (SearchResult sr : results) {
            System.out.printf("%n=== Query: %s ===%n", sr.query());
            System.out.println("Under the hood: dense top-20 + sparse top-20 → RRF fusion → cross-encoder rerank → top-5");
            System.out.printf("%-4s %6s  %-30s %-8s  %s%n", "Rank", "Score", "Source", "Domain", "Snippet");
            System.out.println("-".repeat(120));
            for (int i = 0; i < sr.chunks().size(); i++) {
                RetrievedChunk chunk = sr.chunks().get(i);
                String domain = chunk.metadata().getOrDefault("domain", "?");
                System.out.printf("%-4d %6.3f  %-30s %-8s  %s%n",
                    i + 1, chunk.relevanceScore(),
                    truncate(chunk.sourceDocumentId(), 28),
                    domain,
                    truncate(chunk.content(), 50));
            }
        }
    }

    private static String truncate(String s, int max) {
        return s.length() <= max ? s : s.substring(0, max - 2) + "..";
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-rag-pipeline -Dtest=HybridSearchSmokeTest
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add examples/example-rag-pipeline/src/
git commit -m "feat(#N): HybridSearchDemo — multi-domain hybrid search with result formatting"
```

---

### Task 15: RAG Pipeline Edge Case Tests

**Files:**
- Create: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/RagEdgeCaseTest.java`

- [ ] **Step 1: Write edge case tests**

Create `RagEdgeCaseTest.java`:

```java
package io.casehub.examples.rag;

import dev.langchain4j.data.document.splitter.DocumentSplitters;
import io.casehub.corpus.zip.FlatChangeSource;
import io.casehub.corpus.zip.FlatCorpusStore;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.runtime.CorpusIngestionBinding;
import io.casehub.rag.runtime.CorpusIngestionService;
import io.casehub.rag.runtime.YamlFrontmatterExtractor;
import io.casehub.rag.testing.InMemoryCaseRetriever;
import io.casehub.rag.testing.InMemoryCursorStore;
import io.casehub.rag.testing.InMemoryEmbeddingIngestor;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("smoke")
class RagEdgeCaseTest {

    private static final CorpusRef CORPUS = new CorpusRef("demo-tenant", "edge-case");

    @Test
    void emptyCorpusProducesNoChunks(@TempDir Path tempDir) {
        var store = new FlatCorpusStore(tempDir);
        var changeSource = new FlatChangeSource(tempDir);
        var ingestor = new InMemoryEmbeddingIngestor();
        var cursorStore = new InMemoryCursorStore();
        var binding = new CorpusIngestionBinding(
            "edge-case", CORPUS, changeSource, store, new YamlFrontmatterExtractor());

        var service = new CorpusIngestionService(ingestor, cursorStore);
        service.processBinding(binding, DocumentSplitters.recursive(500, 50));

        assertThat(ingestor.getChunks(CORPUS)).isEmpty();
    }

    @Test
    void corruptFrontmatterTreatedAsBody(@TempDir Path tempDir) throws IOException {
        var store = new FlatCorpusStore(tempDir);
        Files.writeString(tempDir.resolve("bad.md"), "---\nthis is not: valid: yaml: {{{\n---\nActual content here.");

        var changeSource = new FlatChangeSource(tempDir);
        var ingestor = new InMemoryEmbeddingIngestor();
        var cursorStore = new InMemoryCursorStore();
        var binding = new CorpusIngestionBinding(
            "edge-case", CORPUS, changeSource, store, new YamlFrontmatterExtractor());

        var service = new CorpusIngestionService(ingestor, cursorStore);
        service.processBinding(binding, DocumentSplitters.recursive(500, 50));

        assertThat(ingestor.getChunks(CORPUS)).isNotEmpty();
    }

    @Test
    void searchOnEmptyRetrieverReturnsEmptyList() {
        var retriever = new InMemoryCaseRetriever();
        var results = retriever.retrieve("anything", CORPUS, 5);
        assertThat(results).isEmpty();
    }
}
```

- [ ] **Step 2: Run tests**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-rag-pipeline -Dtest=RagEdgeCaseTest
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add examples/example-rag-pipeline/src/test/
git commit -m "test(#N): RAG pipeline edge case tests — empty corpus, corrupt frontmatter, empty retriever"
```

---

### Task 16: Run Full Smoke Suite and Verify

- [ ] **Step 1: Run all smoke tests across both modules**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -Pexamples-smoke
```

Expected: BUILD SUCCESS — all `@Tag("smoke")` tests pass across both modules.

- [ ] **Step 2: Verify default build still skips examples**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests
```

Expected: BUILD SUCCESS — example modules not built.

- [ ] **Step 3: Commit any fixes**

If any tests failed, fix them and commit:

```bash
git add -A
git commit -m "fix(#N): smoke test fixes"
```

---

### Task 17: Integration Tests (Full Profile — Real Models)

**Files:**
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/NliDemoIT.java`
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/RerankingDemoIT.java`
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/ScoringDemoIT.java`
- Create: `examples/example-text-analysis/src/test/java/io/casehub/examples/analysis/CrossDomainConsistencyIT.java`

This task creates the integration tests that run with real ONNX models. They only execute under the `examples` profile (nightly CI). Model URLs and label mappings come from Task 2 research.

- [ ] **Step 1: Write NLI integration test**

Create `NliDemoIT.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.NliClassifier;
import io.casehub.inference.tasks.NliLabel;
import io.casehub.inference.tasks.NliResult;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("integration")
class NliDemoIT {

    private static final Path MODEL_DIR = Path.of("target/models/nli-deberta-v3-xsmall");

    private static InferenceModel model;
    private static NliClassifier nli;

    @BeforeAll
    static void setUp() {
        model = new OnnxInferenceModel(new ModelConfig(
            MODEL_DIR.resolve("model.onnx"), MODEL_DIR.resolve("tokenizer.json")));
        nli = new NliClassifier(model, 0, 1, 2);
    }

    @AfterAll
    static void tearDown() {
        if (model != null) model.close();
    }

    @Test
    void entailmentScoredHighForSemanticImplication() {
        NliResult result = nli.classify("A dog runs in the park.", "An animal is moving.");
        assertThat(result.entailment()).isGreaterThan(0.7f);
        assertThat(result.predicted()).isEqualTo(NliLabel.ENTAILMENT);
    }

    @Test
    void contradictionScoredHighForOpposites() {
        NliResult result = nli.classify(
            "The central bank raised interest rates.",
            "Interest rates were held steady.");
        assertThat(result.contradiction()).isGreaterThan(0.5f);
    }

    @Test
    void allDomainsProducePlausibleScores() {
        List<NliDemo.Result> results = NliDemo.run(nli);

        assertThat(results).allSatisfy(r -> {
            float sum = r.result().entailment() + r.result().neutral() + r.result().contradiction();
            assertThat(sum).isCloseTo(1.0f, org.assertj.core.data.Offset.offset(1e-4f));
        });
    }

    @Test
    void zeroShotClassificationTopLabelIsPlausible() {
        List<ZeroShotClassificationDemo.Result> results = ZeroShotClassificationDemo.run(nli);

        for (var r : results) {
            assertThat(r.topLabel()).isNotBlank();
            assertThat(r.scores().get(r.topLabel())).isGreaterThan(0.0f);
        }
    }
}
```

- [ ] **Step 2: Write reranking integration test**

Create `RerankingDemoIT.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.CrossEncoderReranker;
import io.casehub.inference.tasks.RankedResult;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("integration")
class RerankingDemoIT {

    private static final Path MODEL_DIR = Path.of("target/models/ms-marco-MiniLM-L-6-v2");

    private static InferenceModel model;
    private static CrossEncoderReranker reranker;

    @BeforeAll
    static void setUp() {
        model = new OnnxInferenceModel(new ModelConfig(
            MODEL_DIR.resolve("model.onnx"), MODEL_DIR.resolve("tokenizer.json")));
        reranker = new CrossEncoderReranker(model);
    }

    @AfterAll
    static void tearDown() {
        if (model != null) model.close();
    }

    @Test
    void rerankingActuallyReorders() {
        RerankingDemo.RerankResult result = RerankingDemo.run(reranker);

        List<Integer> rankedIndices = result.ranked().stream()
            .map(RankedResult::originalIndex).toList();
        List<Integer> naturalOrder = List.of(0, 1, 2, 3, 4, 5, 6, 7, 8, 9);
        assertThat(rankedIndices).isNotEqualTo(naturalOrder);
    }

    @Test
    void topResultIsOnnxRelated() {
        RerankingDemo.RerankResult result = RerankingDemo.run(reranker);

        String topText = result.ranked().get(0).text().toLowerCase();
        assertThat(topText).containsAnyOf("onnx", "inference", "jvm", "model");
    }

    @Test
    void scoresAreDescending() {
        RerankingDemo.RerankResult result = RerankingDemo.run(reranker);

        for (int i = 1; i < result.ranked().size(); i++) {
            assertThat(result.ranked().get(i).score())
                .isLessThanOrEqualTo(result.ranked().get(i - 1).score());
        }
    }
}
```

- [ ] **Step 3: Write sentiment scoring integration test**

Create `ScoringDemoIT.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.TextClassifier;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("integration")
class ScoringDemoIT {

    private static final Path MODEL_DIR = Path.of("target/models/distilbert-sst2");

    private static InferenceModel model;
    private static TextClassifier classifier;

    @BeforeAll
    static void setUp() {
        model = new OnnxInferenceModel(new ModelConfig(
            MODEL_DIR.resolve("model.onnx"), MODEL_DIR.resolve("tokenizer.json")));
        classifier = new TextClassifier(model, List.of("negative", "positive"));
    }

    @AfterAll
    static void tearDown() {
        if (model != null) model.close();
    }

    @Test
    void positiveTextScoresHigherThanNegative() {
        var positiveResult = classifier.classify("The new version fixes every issue I had. Excellent work.");
        var negativeResult = classifier.classify("The service was absolutely terrible, I waited two hours.");

        assertThat(positiveResult.scores().get("positive"))
            .isGreaterThan(negativeResult.scores().get("positive"));
    }

    @Test
    void sentimentDemoProducesResults() {
        List<ScoringDemo.ScoredText> results = ScoringDemo.runSentiment(classifier);

        assertThat(results).isNotEmpty();
        assertThat(results).allSatisfy(r -> {
            assertThat(r.score()).isBetween(0.0f, 1.0f);
            assertThat(r.label()).isIn("negative", "positive");
        });
    }
}
```

- [ ] **Step 4: Write cross-domain consistency test**

Create `CrossDomainConsistencyIT.java`:

```java
package io.casehub.examples.analysis;

import io.casehub.inference.InferenceModel;
import io.casehub.inference.runtime.ModelConfig;
import io.casehub.inference.runtime.OnnxInferenceModel;
import io.casehub.inference.tasks.NliClassifier;
import io.casehub.inference.tasks.NliResult;

import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@Tag("integration")
class CrossDomainConsistencyIT {

    private static InferenceModel model;
    private static NliClassifier nli;

    @BeforeAll
    static void setUp() {
        Path dir = Path.of("target/models/nli-deberta-v3-xsmall");
        model = new OnnxInferenceModel(new ModelConfig(dir.resolve("model.onnx"), dir.resolve("tokenizer.json")));
        nli = new NliClassifier(model, 0, 1, 2);
    }

    @AfterAll
    static void tearDown() {
        if (model != null) model.close();
    }

    @Test
    void nliWorksAcrossAllDomains() {
        record Pair(String domain, String premise, String hypothesis) {}
        var pairs = List.of(
            new Pair("tech", "Quarkus supports reactive programming.", "Quarkus is a Java framework."),
            new Pair("news", "Global temperatures rose in 2025.", "Climate change is occurring."),
            new Pair("legal", "The processor shall implement security measures.", "Data protection requires safeguards.")
        );

        for (var pair : pairs) {
            NliResult result = nli.classify(pair.premise(), pair.hypothesis());
            assertThat(result.entailment())
                .as("Entailment for %s domain", pair.domain())
                .isGreaterThan(0.3f);
        }
    }

    @Test
    void zeroShotProducesDistinctLabelsPerDomain() {
        List<ZeroShotClassificationDemo.Result> results = ZeroShotClassificationDemo.run(nli);

        assertThat(results).hasSize(3);
        var labels = results.stream().map(ZeroShotClassificationDemo.Result::topLabel).distinct().toList();
        assertThat(labels.size()).isGreaterThanOrEqualTo(2);
    }
}
```

- [ ] **Step 5: Commit**

```bash
git add examples/example-text-analysis/src/test/
git commit -m "test(#N): integration tests for text analysis — real models, directional assertions"
```

---

### Task 18: RAG Pipeline Integration Tests (Full Profile — Real Models + Qdrant)

**Files:**
- Create: `examples/example-rag-pipeline/src/test/java/io/casehub/examples/rag/RagPipelineIT.java`

These tests require `@QuarkusTest`, Testcontainers Qdrant, and real ONNX models. They only run under the `examples` profile.

- [ ] **Step 1: Write RAG integration test**

Create `RagPipelineIT.java`:

```java
package io.casehub.examples.rag;

import dev.langchain4j.data.document.splitter.DocumentSplitters;
import io.casehub.corpus.zip.FlatChangeSource;
import io.casehub.corpus.zip.FlatCorpusStore;
import io.casehub.rag.CaseRetriever;
import io.casehub.rag.CorpusRef;
import io.casehub.rag.EmbeddingIngestor;
import io.casehub.rag.RetrievedChunk;
import io.casehub.rag.CursorStore;
import io.casehub.rag.runtime.CorpusIngestionBinding;
import io.casehub.rag.runtime.CorpusIngestionService;
import io.casehub.rag.runtime.YamlFrontmatterExtractor;

import io.quarkus.test.junit.QuarkusTest;
import jakarta.inject.Inject;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Order;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;

import java.io.IOException;
import java.nio.file.Path;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

@QuarkusTest
@Tag("integration")
@TestMethodOrder(MethodOrderer.OrderAnnotation.class)
class RagPipelineIT {

    private static final CorpusRef CORPUS = new CorpusRef("demo-tenant", "examples");
    private static Path corpusDir;

    @Inject EmbeddingIngestor ingestor;
    @Inject CursorStore cursorStore;
    @Inject CaseRetriever retriever;

    @BeforeAll
    static void copyCorpus() throws IOException {
        corpusDir = CorpusTestSupport.copyCorpusToTempDir();
    }

    @Test
    @Order(1)
    void ingestAllDocuments() {
        var store = new FlatCorpusStore(corpusDir);
        var changeSource = new FlatChangeSource(corpusDir);
        var binding = new CorpusIngestionBinding(
            "examples", CORPUS, changeSource, store, new YamlFrontmatterExtractor());

        var service = new CorpusIngestionService(ingestor, cursorStore);
        service.processBinding(binding, DocumentSplitters.recursive(500, 50));

        assertThat(ingestor.listDocuments(CORPUS))
            .hasSize(CorpusTestSupport.documentCount());
    }

    @Test
    @Order(2)
    void techQueryReturnsTechDocs() {
        List<RetrievedChunk> results = retriever.retrieve(
            "How does dependency injection work?", CORPUS, 5);

        assertThat(results).isNotEmpty();
        boolean hasTechDoc = results.stream()
            .anyMatch(c -> c.metadata().getOrDefault("domain", "").equals("tech"));
        assertThat(hasTechDoc).isTrue();
    }

    @Test
    @Order(2)
    void legalQueryReturnsLegalDocs() {
        List<RetrievedChunk> results = retriever.retrieve(
            "Can I end my lease early?", CORPUS, 5);

        assertThat(results).isNotEmpty();
        var topDomain = results.get(0).metadata().getOrDefault("domain", "");
        assertThat(topDomain).isEqualTo("legal");
    }

    @Test
    @Order(2)
    void metadataRoundTrips() {
        List<RetrievedChunk> results = retriever.retrieve(
            "data protection GDPR", CORPUS, 5);

        assertThat(results).isNotEmpty();
        var chunkWithMetadata = results.stream()
            .filter(c -> c.metadata().containsKey("domain"))
            .findFirst();
        assertThat(chunkWithMetadata).isPresent();
    }

    @Test
    @Order(2)
    void newsQueryReturnsNewsDocs() {
        List<RetrievedChunk> results = retriever.retrieve(
            "What happened with interest rates?", CORPUS, 5);

        assertThat(results).isNotEmpty();
        boolean hasNewsDoc = results.stream()
            .anyMatch(c -> c.metadata().getOrDefault("domain", "").equals("news"));
        assertThat(hasNewsDoc).isTrue();
    }
}
```

Note: this test class uses `@Order` because ingestion (Order 1) must complete before search (Order 2). All search tests share the same ingested corpus.

- [ ] **Step 2: This test is only run under the `examples` profile (nightly)**

Verify it's not picked up by smoke:

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn test -Pexamples-smoke -pl examples/example-rag-pipeline
```

Expected: `RagPipelineIT` is NOT executed (it's `@Tag("integration")`, not `@Tag("smoke")`).

- [ ] **Step 3: Commit**

```bash
git add examples/example-rag-pipeline/src/test/
git commit -m "test(#N): RAG pipeline integration tests — real models, Qdrant, cross-domain search"
```

---

### Task 19: README with Coverage Grid

**Files:**
- Create: `examples/README.md`

- [ ] **Step 1: Write README**

Create `examples/README.md`:

```markdown
# casehub-neural-text Examples

Two example modules demonstrating all casehub-neural-text capabilities across tech, news, and legal domains.

## Quick Start

```bash
# Smoke tests — no models, no Docker, seconds
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -Pexamples-smoke

# Full tests — downloads real ONNX models, runs Testcontainers Qdrant
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -Pexamples
```

## Modules

### example-text-analysis

Standalone Java — no Quarkus, no infrastructure. Load ONNX models and run inference.

| Demo | What it does | Run it |
|------|-------------|--------|
| `NliDemo` | Premise + hypothesis → entailment/contradiction/neutral | `java -cp ... NliDemo` |
| `ZeroShotClassificationDemo` | NLI-based zero-shot text classification | `java -cp ... ZeroShotClassificationDemo` |
| `ScoringDemo` | Sentiment scoring with TextClassifier | `java -cp ... ScoringDemo` |
| `RerankingDemo` | Cross-encoder reranking of search candidates | `java -cp ... RerankingDemo` |
| `SparseEmbeddingDemo` | SPLADE sparse embedding with top-weighted terms | `java -cp ... SparseEmbeddingDemo` |

### example-rag-pipeline

Quarkus + Testcontainers Qdrant — end-to-end corpus ingestion and hybrid search.

| Demo | What it does |
|------|-------------|
| `FlatCorpusIngestDemo` | Flat storage → CorpusIngestionBinding → processBinding() → incremental ingestion |
| `ZipCorpusIngestDemo` | ZIP storage → tombstones → rollover → compaction |
| `HybridSearchDemo` | Dense + SPLADE sparse → RRF fusion → cross-encoder rerank → top-5 |

## Capability Coverage

| Capability | Text Analysis | RAG Pipeline |
|---|:---:|:---:|
| OnnxInferenceModel | x | x |
| NliClassifier | x | |
| NLI zero-shot classification | x | |
| TextClassifier | x | |
| ScalarRegressor | x | |
| CrossEncoderReranker | x | x |
| SparseEmbedder | x | x |
| @Inference CDI qualifier | | x |
| Hybrid dense+sparse search | | x |
| RRF fusion | | x |
| Two-stage retrieval | | x |
| CorpusIngestionService | | x |
| FlatCorpusStore | | x |
| ZipCorpusStore + Compaction | | x |
| MetadataExtractor | | x |
| CursorStore | | x |

## Architecture Justification

See `docs/architecture-justification.md` for evidence-based rationale for each architectural layer.
```

- [ ] **Step 2: Commit**

```bash
git add examples/README.md
git commit -m "docs(#N): examples README with coverage grid and quick start"
```

---

### Task 20: Code Review and Final Verification

- [ ] **Step 1: Run full smoke suite one final time**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean test -Pexamples-smoke
```

Expected: BUILD SUCCESS.

- [ ] **Step 2: Invoke superpowers:requesting-code-review**

Review all changes on the branch. Any Minor or above finding that isn't fixed this session must be captured as a GitHub issue.

- [ ] **Step 3: Run implementation-doc-sync**

Sync documentation after committing.

- [ ] **Step 4: Verify default build is unaffected**

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install
```

Expected: BUILD SUCCESS — example modules not built, existing tests all pass.
