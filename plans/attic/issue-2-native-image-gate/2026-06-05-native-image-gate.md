# Native Image Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate that ONNX Runtime JNI and HuggingFace Tokenizers JNI both work in a Quarkus native image binary on macOS ARM — binary pass/fail gate for C5 and Hortora native deployment.

**Architecture:** Minimal JNI bridge code in `inference-runtime` (3 classes), `@QuarkusMain` command-mode gate test in `inference-quarkus` with independent JNI layer validation. GraalVM 25 native image config discovered via tracing agent, curated by hand.

**Tech Stack:** Java 21 (source) on GraalVM 25.0.3, Quarkus 3.32.2, ONNX Runtime 1.26.0, DJL Tokenizers 0.36.0, maven-download-plugin 1.9.0

**Spec:** `specs/issue-2-native-image-gate/2026-06-05-native-image-gate-design.md` (rev 6, approved)

**Build commands:**
```bash
# JVM mode (fast, iterative)
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean verify -pl inference-runtime,inference-quarkus -am

# Native gate (slow, validation)
JAVA_HOME=$(/usr/libexec/java_home -v 25) mvn clean verify -pl inference-runtime,inference-quarkus -am -Dnative
```

---

### Task 1: Bump dependency versions and check for AWT blockers

**Files:**
- Modify: `pom.xml` (parent POM — properties and pluginManagement)

- [ ] **Step 1: Update parent POM dependency versions**

In `pom.xml`, update these properties:

```xml
<onnxruntime.version>1.26.0</onnxruntime.version>
<djl.tokenizers.version>0.36.0</djl.tokenizers.version>
```

Add a new property:

```xml
<download-maven-plugin.version>1.9.0</download-maven-plugin.version>
```

Add to `<pluginManagement><plugins>`:

```xml
<plugin>
  <groupId>com.googlecode.maven-download-plugin</groupId>
  <artifactId>download-maven-plugin</artifactId>
  <version>${download-maven-plugin.version}</version>
</plugin>
```

- [ ] **Step 2: Verify JVM build passes with bumped versions**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean install -DskipTests`
Expected: BUILD SUCCESS (no source code yet, just POM resolution)

- [ ] **Step 3: Check for AWT transitive dependencies**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn dependency:tree -pl inference-runtime -am | grep -i awt`
Expected: No output (no AWT deps). If AWT deps appear, stop and assess — this may be a hard blocker for macOS native image (see spec §Expected Challenges #5).

- [ ] **Step 4: Commit**

```bash
git add pom.xml
git commit -m "chore(#2): bump ONNX Runtime 1.26.0, DJL 0.36.0, add download-maven-plugin 1.9.0"
```

---

### Task 2: Check langchain4j for existing native-image metadata

**Files:** None — research task

- [ ] **Step 1: Inspect langchain4j-embeddings-onnx for GraalVM config**

Search the `langchain4j` source or quarkiverse `quarkus-langchain4j` extension for existing `reachability-metadata.json`, `jni-config.json`, `reflect-config.json`, or `native-image.properties` files that register `com.microsoft.onnxruntime` or `ai.djl` classes.

Check:
- `langchain4j-embeddings-onnx` module in the langchain4j repo
- `quarkus-langchain4j` extension in the quarkiverse GitHub org

Look for any `META-INF/native-image/` resources related to ONNX Runtime or DJL tokenizers.

- [ ] **Step 2: Document findings**

If metadata found: save the relevant entries as a reference file at `inference-quarkus/src/main/resources/META-INF/native-image/io.casehub/casehub-inference-quarkus/BORROWED-METADATA.md` listing what was found and where. These entries will be incorporated into `reachability-metadata.json` in Task 7.

If nothing found: proceed — we'll discover everything via the tracing agent.

No commit for this task — findings inform Task 7.

---

### Task 3: Write TokenizerLoader in inference-runtime

**Files:**
- Create: `inference-runtime/src/main/java/io/casehub/inference/runtime/TokenizerLoader.java`

- [ ] **Step 1: Create TokenizerLoader**

```java
package io.casehub.inference.runtime;

import ai.djl.huggingface.tokenizers.HuggingFaceTokenizer;
import java.io.IOException;
import java.nio.file.Path;

public final class TokenizerLoader {

    private TokenizerLoader() {}

    public static HuggingFaceTokenizer load(Path tokenizerJsonPath) throws IOException {
        return HuggingFaceTokenizer.newInstance(tokenizerJsonPath);
    }
}
```

- [ ] **Step 2: Verify it compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl inference-runtime -am`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add inference-runtime/src/main/java/io/casehub/inference/runtime/TokenizerLoader.java
git commit -m "feat(#2): TokenizerLoader — load DJL HuggingFaceTokenizer from path"
```

---

### Task 4: Write OnnxSessionLoader in inference-runtime

**Files:**
- Create: `inference-runtime/src/main/java/io/casehub/inference/runtime/OnnxSessionLoader.java`

- [ ] **Step 1: Create OnnxSessionLoader**

```java
package io.casehub.inference.runtime;

import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtException;
import ai.onnxruntime.OrtSession;
import java.nio.file.Path;

public final class OnnxSessionLoader {

    private OnnxSessionLoader() {}

    public static OrtEnvironment createEnvironment() {
        return OrtEnvironment.getEnvironment();
    }

    public static OrtSession createSession(OrtEnvironment env, Path modelPath) throws OrtException {
        return env.createSession(modelPath.toString());
    }
}
```

- [ ] **Step 2: Verify it compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl inference-runtime -am`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add inference-runtime/src/main/java/io/casehub/inference/runtime/OnnxSessionLoader.java
git commit -m "feat(#2): OnnxSessionLoader — load OrtEnvironment + OrtSession from path"
```

---

### Task 5: Write RawInference in inference-runtime

**Files:**
- Create: `inference-runtime/src/main/java/io/casehub/inference/runtime/RawInference.java`

- [ ] **Step 1: Create RawInference**

This class tokenizes a text pair and runs ONNX inference, returning raw logits. It connects TokenizerLoader and OnnxSessionLoader.

```java
package io.casehub.inference.runtime;

import ai.djl.huggingface.tokenizers.Encoding;
import ai.djl.huggingface.tokenizers.HuggingFaceTokenizer;
import ai.onnxruntime.OnnxTensor;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtException;
import ai.onnxruntime.OrtSession;
import java.util.Map;

public final class RawInference {

    private RawInference() {}

    public static float[] classifyPair(OrtEnvironment env, OrtSession session,
                                        HuggingFaceTokenizer tokenizer,
                                        String premise, String hypothesis) throws OrtException {
        Encoding encoding = tokenizer.encode(premise, hypothesis);
        long[] inputIds = encoding.getIds();
        long[] attentionMask = encoding.getAttentionMask();

        long[][] inputIds2d = {inputIds};
        long[][] attentionMask2d = {attentionMask};

        try (OnnxTensor idsTensor = OnnxTensor.createTensor(env, inputIds2d);
             OnnxTensor maskTensor = OnnxTensor.createTensor(env, attentionMask2d)) {

            Map<String, OnnxTensor> inputs = Map.of(
                "input_ids", idsTensor,
                "attention_mask", maskTensor
            );

            try (OrtSession.Result result = session.run(inputs)) {
                float[][] logits = (float[][]) result.get(0).getValue();
                return logits[0];
            }
        }
    }
}
```

**Note:** The exact input tensor names (`input_ids`, `attention_mask`) and output shape (`float[][]`) are model-specific. DeBERTa-v3-xsmall NLI uses these names. If the model has different input names, adjust in Task 6 when we first run the JVM test and see the actual model metadata.

- [ ] **Step 2: Verify it compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl inference-runtime -am`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add inference-runtime/src/main/java/io/casehub/inference/runtime/RawInference.java
git commit -m "feat(#2): RawInference — tokenize text pair + run ONNX inference → float[] logits"
```

---

### Task 6: Configure inference-quarkus build for gate test

**Files:**
- Modify: `inference-quarkus/pom.xml`

- [ ] **Step 1: Add model download plugin to default build**

Add to `inference-quarkus/pom.xml` inside `<build><plugins>`, after the existing jandex plugin:

```xml
<plugin>
  <groupId>com.googlecode.maven-download-plugin</groupId>
  <artifactId>download-maven-plugin</artifactId>
  <executions>
    <execution>
      <id>download-onnx-model</id>
      <phase>generate-test-resources</phase>
      <goals><goal>wget</goal></goals>
      <configuration>
        <url>https://huggingface.co/Xenova/nli-deberta-v3-xsmall/resolve/main/onnx/model_quantized.onnx</url>
        <outputDirectory>${project.build.directory}/test-models/nli-deberta-v3-xsmall</outputDirectory>
        <outputFileName>model.onnx</outputFileName>
        <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
      </configuration>
    </execution>
    <execution>
      <id>download-tokenizer</id>
      <phase>generate-test-resources</phase>
      <goals><goal>wget</goal></goals>
      <configuration>
        <url>https://huggingface.co/Xenova/nli-deberta-v3-xsmall/resolve/main/tokenizer.json</url>
        <outputDirectory>${project.build.directory}/test-models/nli-deberta-v3-xsmall</outputDirectory>
        <outputFileName>tokenizer.json</outputFileName>
        <cacheDirectory>${user.home}/.cache/maven-download</cacheDirectory>
      </configuration>
    </execution>
  </executions>
</plugin>
```

- [ ] **Step 2: Add surefire config**

Add surefire plugin configuration inside `<build><plugins>`:

```xml
<plugin>
  <groupId>org.apache.maven.plugins</groupId>
  <artifactId>maven-surefire-plugin</artifactId>
  <configuration>
    <systemPropertyVariables>
      <java.util.logging.manager>org.jboss.logmanager.LogManager</java.util.logging.manager>
    </systemPropertyVariables>
  </configuration>
</plugin>
```

- [ ] **Step 3: Add native profile**

Add a `<profiles>` section to `inference-quarkus/pom.xml`:

```xml
<profiles>
  <profile>
    <id>native</id>
    <activation>
      <property><name>native</name></property>
    </activation>
    <properties>
      <quarkus.native.enabled>true</quarkus.native.enabled>
    </properties>
    <build>
      <plugins>
        <plugin>
          <groupId>io.quarkus</groupId>
          <artifactId>quarkus-maven-plugin</artifactId>
          <version>${quarkus.version}</version>
          <extensions>true</extensions>
          <executions>
            <execution>
              <goals>
                <goal>build</goal>
                <goal>generate-code</goal>
                <goal>generate-code-tests</goal>
                <goal>native-image-agent</goal>
              </goals>
            </execution>
          </executions>
        </plugin>
        <plugin>
          <groupId>org.apache.maven.plugins</groupId>
          <artifactId>maven-failsafe-plugin</artifactId>
          <version>${surefire-plugin.version}</version>
          <executions>
            <execution>
              <goals>
                <goal>integration-test</goal>
                <goal>verify</goal>
              </goals>
            </execution>
          </executions>
        </plugin>
      </plugins>
    </build>
  </profile>
</profiles>
```

- [ ] **Step 4: Verify POM is valid**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn validate -pl inference-quarkus -am`
Expected: BUILD SUCCESS

- [ ] **Step 5: Commit**

```bash
git add inference-quarkus/pom.xml
git commit -m "build(#2): configure inference-quarkus — model download, surefire, native profile"
```

---

### Task 7: Write NativeImageGateCommand

**Files:**
- Create: `inference-quarkus/src/main/java/io/casehub/inference/quarkus/gate/NativeImageGateCommand.java`

- [ ] **Step 1: Create the @QuarkusMain command-mode app**

```java
package io.casehub.inference.quarkus.gate;

import ai.djl.huggingface.tokenizers.Encoding;
import ai.djl.huggingface.tokenizers.HuggingFaceTokenizer;
import ai.onnxruntime.OrtEnvironment;
import ai.onnxruntime.OrtSession;
import io.casehub.inference.runtime.OnnxSessionLoader;
import io.casehub.inference.runtime.RawInference;
import io.casehub.inference.runtime.TokenizerLoader;
import io.quarkus.runtime.QuarkusApplication;
import io.quarkus.runtime.annotations.QuarkusMain;
import java.nio.file.Path;

@QuarkusMain(name = "native-gate")
public class NativeImageGateCommand implements QuarkusApplication {

    @Override
    public int run(String... args) throws Exception {
        if (args.length < 1) {
            System.err.println("FAIL: model directory argument required");
            return 1;
        }
        Path modelDir = Path.of(args[0]);
        Path tokenizerPath = modelDir.resolve("tokenizer.json");
        Path modelPath = modelDir.resolve("model.onnx");

        // Phase 1 — DJL Tokenizer JNI (independent)
        HuggingFaceTokenizer tokenizer;
        try {
            tokenizer = TokenizerLoader.load(tokenizerPath);
            Encoding encoding = tokenizer.encode("hello world");
            if (encoding.getIds().length == 0) {
                System.err.println("FAIL: DJL Tokenizer JNI — tokenization returned empty IDs");
                return 1;
            }
            System.out.println("PASS: DJL Tokenizer JNI loaded and executed");
        } catch (Exception e) {
            System.err.println("FAIL: DJL Tokenizer JNI — " + e.getMessage());
            e.printStackTrace(System.err);
            return 1;
        }

        // Phase 2 — ONNX Runtime JNI (independent)
        OrtEnvironment env;
        OrtSession session;
        try {
            env = OnnxSessionLoader.createEnvironment();
            session = OnnxSessionLoader.createSession(env, modelPath);
            System.out.println("Model inputs: " + session.getInputNames());
            System.out.println("Model outputs: " + session.getOutputNames());
            System.out.println("PASS: ONNX Runtime JNI loaded and session created");
        } catch (Exception e) {
            System.err.println("FAIL: ONNX Runtime JNI — " + e.getMessage());
            e.printStackTrace(System.err);
            return 1;
        }

        // Phase 3 — End-to-end inference
        try {
            float[] logits = RawInference.classifyPair(
                env, session, tokenizer,
                "The weather is sunny", "It is raining"
            );
            System.out.printf("Logits: contradiction=%.4f, entailment=%.4f, neutral=%.4f%n",
                logits[0], logits[1], logits[2]);
            if (logits[0] <= logits[1] || logits[0] <= logits[2]) {
                System.err.println("FAIL: End-to-end inference — contradiction score not highest");
                return 1;
            }
            System.out.println("PASS: End-to-end inference completed");
        } catch (Exception e) {
            System.err.println("FAIL: End-to-end inference — " + e.getMessage());
            e.printStackTrace(System.err);
            return 1;
        } finally {
            session.close();
            env.close();
            tokenizer.close();
        }

        return 0;
    }
}
```

- [ ] **Step 2: Verify it compiles**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn compile -pl inference-quarkus -am`
Expected: BUILD SUCCESS

- [ ] **Step 3: Commit**

```bash
git add inference-quarkus/src/main/java/io/casehub/inference/quarkus/gate/NativeImageGateCommand.java
git commit -m "feat(#2): NativeImageGateCommand — @QuarkusMain gate with 3-phase JNI validation"
```

---

### Task 8: Write gate tests and verify JVM mode

**Files:**
- Create: `inference-quarkus/src/test/java/io/casehub/inference/quarkus/gate/NativeImageGateTest.java`
- Create: `inference-quarkus/src/test/java/io/casehub/inference/quarkus/gate/NativeImageGateIT.java`

- [ ] **Step 1: Create NativeImageGateTest (JVM mode)**

```java
package io.casehub.inference.quarkus.gate;

import io.quarkus.test.junit.main.Launch;
import io.quarkus.test.junit.main.LaunchResult;
import io.quarkus.test.junit.main.QuarkusMainTest;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

@QuarkusMainTest
public class NativeImageGateTest {

    @Test
    @Launch(value = {"target/test-models/nli-deberta-v3-xsmall"}, exitCode = 0)
    void nativeImageGatePasses(LaunchResult result) {
        assertThat(result.getOutput())
            .contains("PASS: DJL Tokenizer JNI loaded and executed")
            .contains("PASS: ONNX Runtime JNI loaded and session created")
            .contains("PASS: End-to-end inference completed");
    }
}
```

- [ ] **Step 2: Create NativeImageGateIT (native mode)**

```java
package io.casehub.inference.quarkus.gate;

import io.quarkus.test.junit.main.QuarkusMainIntegrationTest;

@QuarkusMainIntegrationTest
public class NativeImageGateIT extends NativeImageGateTest {
}
```

- [ ] **Step 3: Run JVM-mode test**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean verify -pl inference-runtime,inference-quarkus -am`

Expected: Model downloads (~83MB, cached after first run), `NativeImageGateTest` passes with all three PASS lines in output. `NativeImageGateIT` is not executed (failsafe only runs with `-Dnative`).

**If test fails:** Debug based on output. Common issues:
- Model download URL incorrect → adjust URLs in pom.xml
- Tensor input names don't match model → print `session.getInputNames()` output, adjust `RawInference.classifyPair` input map keys
- Tokenizer can't load → verify `tokenizer.json` was downloaded correctly
- Logit order different → check model card, adjust assertion index

- [ ] **Step 4: Commit**

```bash
git add inference-quarkus/src/test/java/io/casehub/inference/quarkus/gate/NativeImageGateTest.java
git add inference-quarkus/src/test/java/io/casehub/inference/quarkus/gate/NativeImageGateIT.java
git commit -m "test(#2): gate tests — @QuarkusMainTest (JVM) + @QuarkusMainIntegrationTest (native)"
```

---

### Task 9: Native image config — tracing agent discovery

**Files:**
- Create: `inference-quarkus/src/main/resources/META-INF/native-image/io.casehub/casehub-inference-quarkus/reachability-metadata.json`
- Create: `inference-quarkus/src/main/resources/META-INF/native-image/io.casehub/casehub-inference-quarkus/native-image.properties`
- Create: `inference-quarkus/src/main/resources/NATIVE-IMAGE-NOTES.md`

This task is iterative — the exact config entries depend on what the tracing agent discovers and what the native build fails on. The steps below provide the framework; the specific entries are filled during iteration.

- [ ] **Step 1: Create initial native-image.properties with known suspects**

Create `inference-quarkus/src/main/resources/META-INF/native-image/io.casehub/casehub-inference-quarkus/native-image.properties`:

```properties
Args = --initialize-at-run-time=ai.onnxruntime.OnnxRuntime \
       --initialize-at-run-time=ai.djl.util.Platform \
       --initialize-at-run-time=ai.djl.huggingface.tokenizers.jni.LibUtils
```

These are the known classes that load native libraries in static initializers (spec §Known suspects). Additional classes will be added as discovered.

- [ ] **Step 2: Create empty reachability-metadata.json**

Create `inference-quarkus/src/main/resources/META-INF/native-image/io.casehub/casehub-inference-quarkus/reachability-metadata.json`:

```json
{
}
```

Entries will be added based on tracing agent output and native build errors.

- [ ] **Step 3: Create NATIVE-IMAGE-NOTES.md**

Create `inference-quarkus/src/main/resources/NATIVE-IMAGE-NOTES.md`:

```markdown
# Native Image Configuration Notes

Companion documentation for reachability-metadata.json and native-image.properties.
Each entry explains what it fixes and what error appears without it.

## --initialize-at-run-time entries (native-image.properties)

### ai.onnxruntime.OnnxRuntime
Calls System.loadLibrary("onnxruntime") in static initializer.
Without: build-time init fails — native lib not available at build time.

### ai.djl.util.Platform
Platform detection and native lib path resolution in static initializer.
Without: build-time init fails — platform detection reads files not available at build time.

### ai.djl.huggingface.tokenizers.jni.LibUtils
Loads the tokenizers native library in static initializer.
Without: build-time init fails — native lib not available at build time.

## reachability-metadata.json entries

(Populated during tracing agent discovery — Task 9 iteration)
```

- [ ] **Step 4: Attempt native build**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 25) mvn clean verify -pl inference-runtime,inference-quarkus -am -Dnative`

This will likely fail. Read the error output carefully:
- `ClassNotFoundException` or `NoClassDefFoundError` → add to reflection/JNI config
- `UnsatisfiedLinkError` → native lib not found; check resource registration
- Class initialization error → add to `--initialize-at-run-time`
- AWT-related `UnsatisfiedLinkError` → see spec §Expected Challenge #5; try `-Dquarkus.native.container-build=true` as fallback

- [ ] **Step 5: Iterate — add config entries and retry**

For each build failure:
1. Identify the failing class or resource
2. Add the appropriate entry to `reachability-metadata.json` or `native-image.properties`
3. Document the entry in `NATIVE-IMAGE-NOTES.md` — what error it fixes
4. Retry the native build

Repeat until the native build succeeds and `NativeImageGateIT` passes.

**Optional: use tracing agent to discover entries in bulk:**
```bash
JAVA_HOME=$(/usr/libexec/java_home -v 25) java \
  -agentlib:native-image-agent=config-output-dir=target/agent-config \
  -jar inference-quarkus/target/quarkus-app/quarkus-run.jar \
  target/test-models/nli-deberta-v3-xsmall
```
Exercise the classify path, then inspect `target/agent-config/` for generated config. Curate the output into `reachability-metadata.json` — don't copy verbatim; understand each entry.

- [ ] **Step 6: Commit when native gate passes**

```bash
git add inference-quarkus/src/main/resources/META-INF/native-image/
git add inference-quarkus/src/main/resources/NATIVE-IMAGE-NOTES.md
git commit -m "feat(#2): native image config — reachability metadata + init-at-run-time entries

ONNX Runtime JNI + DJL Tokenizers JNI validated in Quarkus native image
on macOS ARM (GraalVM 25.0.3). Gate: PASS."
```

If the gate **fails** after exhausting config options:

```bash
git add inference-quarkus/src/main/resources/
git commit -m "docs(#2): native image gate — FAIL, partial config documented

[document which layer failed and why in commit body]"
```

---

### Task 10: Final verification and cleanup

- [ ] **Step 1: Run full JVM build to confirm nothing broke**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean verify -pl inference-runtime,inference-quarkus -am`
Expected: BUILD SUCCESS, NativeImageGateTest passes

- [ ] **Step 2: Run native gate one final time from clean**

Run: `JAVA_HOME=$(/usr/libexec/java_home -v 25) mvn clean verify -pl inference-runtime,inference-quarkus -am -Dnative`
Expected: BUILD SUCCESS, NativeImageGateIT passes, output contains all three PASS lines

- [ ] **Step 3: Commit any remaining changes**

Verify `git status --short` shows clean or only expected changes. Commit if needed.
