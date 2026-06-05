# Native Image Gate — Design Spec

**Date:** 2026-06-05
**Issue:** casehubio/neural-text#2
**Chapter:** C2 ([ARC42STORIES §9.3](../../ARC42STORIES.MD))
**Status:** Draft (rev 2)

---

## Goal

Prove that ONNX Runtime JNI and HuggingFace Tokenizers JNI both load and execute correctly inside a Quarkus native image binary on macOS ARM (Apple Silicon). Binary pass/fail — either both JNI layers work or they don't.

This gates `inference-quarkus` (C5) native image support and Hortora's distributable native binary goal. If the gate fails, C5 proceeds in JVM-only mode.

## Non-Goals

- Full SPI design (`InferenceModel`, `InferenceInput`, `InferenceOutput`) — that's C3.
- Dense embeddings, SPLADE, or any model type beyond NLI.
- Quarkus extension annotations (`@InferenceModel` qualifier) — that's C5.
- Performance benchmarking.
- CI native builds — the gate runs locally on macOS ARM only (see CI section).

## Pass/Fail Criteria

**Pass:** A `@QuarkusMain` command-mode app, compiled to a native binary, successfully:
1. Loads a HuggingFace tokenizer via DJL JNI — independently verified
2. Runs ONNX inference via ONNX Runtime JNI — independently verified
3. Tokenizes a text pair + runs inference end-to-end → returns `float[3]` logits
4. Process exits 0

**Fail:** Any of the above steps throws a JNI error, native library load failure, or GraalVM build error that cannot be resolved with configuration. Document:
- Which JNI layer failed (ORT, DJL, or both)
- Whether it's a GraalVM limitation, library limitation, or configuration gap
- Whether upstream changes are needed
- Workaround options if any

---

## Module Structure — Build in Real Modules

No throwaway prototype module. The gate code goes into the production modules where it belongs. The JNI bridge logic in `inference-runtime` IS the code C3 will wrap with the SPI. The GraalVM config in `inference-quarkus` IS what C5 needs.

### inference-runtime

Minimal JNI bridge code — enough to validate both JNI layers:

```
inference-runtime/src/main/java/io/casehub/inference/runtime/
  OnnxSessionLoader.java     — load OrtEnvironment + OrtSession from model path
  TokenizerLoader.java       — load DJL HuggingFaceTokenizer from tokenizer.json path
  RawInference.java          — tokenize + run inference + return raw float[] output
```

No SPI interfaces, no `InferenceModel`, no `InferenceInput`/`InferenceOutput` types. C3 adds the SPI on top of this code. These classes are internal implementation details that the SPI will wrap — they stay as-is in C3.

### inference-quarkus

Native build profile + gate test:

```
inference-quarkus/src/main/resources/
  META-INF/native-image/io.casehub/casehub-inference-quarkus/
    reachability-metadata.json     — consolidated GraalVM 25 format
    native-image.properties        — --initialize-at-run-time entries

inference-quarkus/src/test/java/io/casehub/inference/prototype/
  NativeImageGateCommand.java      — @QuarkusMain command-mode app
  NativeImageGateIT.java           — integration test asserting exit code 0
```

### inference-api

Stays empty. The SPI interface comes in C3.

### Why not a throwaway module

- The JNI bridge code (`OnnxSessionLoader`, `TokenizerLoader`, `RawInference`) is exactly what `inference-runtime` will contain — writing it twice wastes effort.
- The GraalVM config files (`reachability-metadata.json`, `native-image.properties`) belong permanently in `inference-quarkus` — they'd need to move there anyway.
- The `@QuarkusMain` gate test in `src/test/java` stays as the permanent native regression test.
- If native fails, the JVM-mode code in `inference-runtime` is still correct and feeds C3.

---

## Build Configuration

### inference-runtime pom.xml (key dependencies)

```xml
<dependencies>
  <dependency>
    <groupId>com.microsoft.onnxruntime</groupId>
    <artifactId>onnxruntime</artifactId>
  </dependency>
  <dependency>
    <groupId>ai.djl.huggingface</groupId>
    <artifactId>tokenizers</artifactId>
  </dependency>
</dependencies>
```

### inference-quarkus pom.xml (key additions for gate)

```xml
<dependencies>
  <!-- existing deps plus: -->
  <dependency>
    <groupId>io.quarkus</groupId>
    <artifactId>quarkus-arc</artifactId>
  </dependency>
</dependencies>

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

<profiles>
  <profile>
    <id>native</id>
    <activation>
      <property><name>native</name></property>
    </activation>
    <properties>
      <quarkus.native.enabled>true</quarkus.native.enabled>
    </properties>
  </profile>
</profiles>
```

### Build commands

```bash
# JVM mode — iterative development (fast, seconds)
JAVA_HOME=$(/usr/libexec/java_home -v 26) mvn clean verify -pl inference-runtime,inference-quarkus

# Native gate — validation only (slow, minutes)
# Uses GraalVM 25 (not JDK 26) — intentional: GraalVM provides native-image
JAVA_HOME=$(/usr/libexec/java_home -v 25) mvn clean verify -pl inference-runtime,inference-quarkus -Dnative
```

---

## Model Provisioning

### Source: Xenova/nli-deberta-v3-xsmall

The original `cross-encoder/nli-deberta-v3-xsmall` ships PyTorch weights only — no ONNX file. The Xenova conversion (Transformers.js export) provides both `onnx/model.onnx` and `tokenizer.json` in the format DJL expects.

**Note:** The Xenova repo totals ~1.29GB across all formats. We download only the two files we need.

### Download mechanism: maven-download-plugin

Direct URL downloads from HuggingFace CDN. No Python dependency, deterministic, with built-in cache.

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
        <url>https://huggingface.co/Xenova/nli-deberta-v3-xsmall/resolve/main/onnx/model.onnx</url>
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

**URLs to verify at implementation time** — the HuggingFace CDN path format (`/resolve/main/`) and whether the Xenova repo hosts `onnx/model.onnx` at that path. If the path differs, adjust URLs before first build.

**CI caching:** `maven-download-plugin` caches to `~/.cache/maven-download/`. GitHub Actions caches this directory with a stable key. First run downloads (~90MB model + ~700KB tokenizer), subsequent runs are no-ops.

### Model path at runtime

Model path is passed as a system property at invocation — no Maven resource filtering, no `${...}` conflict with Quarkus property syntax.

The `@QuarkusMain` command-mode app reads the path from `quarkus.args` or a system property:
```bash
./target/*-runner -Dinference.model.dir=target/test-models/nli-deberta-v3-xsmall
```

The integration test sets this property via `maven-failsafe-plugin` `<systemPropertyVariables>`. The model directory is relative to the project build directory — the failsafe plugin runs from there.

---

## Gate Test Structure

### Independent JNI validation

ONNX Runtime JNI and DJL Tokenizers JNI are independent libraries with independent failure modes. The gate test validates each layer separately before testing them together, so the failure report identifies exactly which library is the problem.

### NativeImageGateCommand.java (`@QuarkusMain`)

A command-mode Quarkus app in `src/test/java/` — test infrastructure, not production code. Runs three validation phases:

```
Phase 1 — DJL Tokenizer JNI (independent)
  Load tokenizer from tokenizer.json
  Tokenize "hello world" → verify token IDs array is non-empty
  Print: "PASS: DJL Tokenizer JNI loaded and executed"

Phase 2 — ONNX Runtime JNI (independent)
  Create OrtEnvironment
  Create OrtSession from model.onnx
  Print model input/output names
  Print: "PASS: ONNX Runtime JNI loaded and session created"

Phase 3 — End-to-end inference
  Tokenize text pair: ("The weather is sunny", "It is raining")
  Create OnnxTensor inputs from token arrays
  Run session.run()
  Extract float[3] logits
  Assert contradiction score (index 0) is highest
  Print logits and result
  Print: "PASS: End-to-end inference completed"
```

Label order per model card: **contradiction=0, entailment=1, neutral=2**.

Exit 0 if all phases pass. Exit 1 on any failure, printing which phase and which JNI layer failed.

### NativeImageGateIT.java

```java
@QuarkusIntegrationTest
class NativeImageGateIT {
    @Test
    void nativeImageGatePasses() {
        // @QuarkusIntegrationTest launches the @QuarkusMain binary
        // and asserts it exits with code 0.
        // Stdout contains per-phase PASS/FAIL lines for diagnostics.
    }
}
```

---

## GraalVM Native Image Configuration

### Config format

GraalVM 25 supports a consolidated `reachability-metadata.json` format alongside the legacy separate files. The tracing agent on GraalVM 25 may output either format. **Standardise on `reachability-metadata.json`** (consolidated) — single file, easier to maintain.

Located at: `inference-quarkus/src/main/resources/META-INF/native-image/io.casehub/casehub-inference-quarkus/`

### Discovery process

1. Get the app running in JVM mode with both JNI layers working
2. Run with tracing agent to discover required config
3. Curate the agent output into a hand-written `reachability-metadata.json` with comments explaining each entry
4. Iterate: attempt native build → read error → add config → retry

### Known --initialize-at-run-time suspects

These classes load native libraries in static initializers. GraalVM runs class init at build time where the libs aren't available. List upfront to save build-fail-fix cycles:

**ONNX Runtime:**
- `ai.onnxruntime.OnnxRuntime` — calls `System.loadLibrary("onnxruntime")`

**DJL:**
- `ai.djl.util.Platform` — platform detection and native lib path resolution
- `ai.djl.huggingface.tokenizers.jni.LibUtils` — loads the tokenizers native library

These are starting points from known library internals. The tracing agent will find additional classes.

### Expected challenges (ordered by likelihood)

**1. `--initialize-at-run-time` for native lib loaders (high)**
Both libraries load `.dylib` files during class initialization. Fix: defer to runtime init.

**2. Missing JNI/reflection entries (medium)**
Tracing agent only captures exercised code paths. Fix: inspect ORT and DJL source for `native` method declarations.

**3. Native lib extraction (medium)**
Both JARs bundle native libs extracted to a temp dir at runtime. In native image, JAR resource handling differs. Fix: may need custom extraction or library path configuration.

**4. Oracle GraalVM svm-enterprise.jar class conflict (low–medium)**
Known issue where ONNX Runtime's `ai.onnxruntime.ValueInfo` class conflicts with classes in `svm-enterprise.jar` in Oracle GraalVM Enterprise builds. May or may not affect 25.0.3. If hit: try GraalVM CE as fallback.

### Iterative approach

Each fix is documented in `reachability-metadata.json` with comments explaining what it resolves. This documentation feeds directly into C5's Quarkus extension.

---

## Dependency Versions

| Dependency | Parent POM | Latest | Action |
|---|---|---|---|
| ONNX Runtime | 1.17.3 | ~1.21.x | Bump — GraalVM JNI metadata may have improved in newer versions. GitHub issue #5172 (ONNX+GraalVM) is closed. |
| DJL Tokenizers | 0.29.0 | ~0.36.0 | Bump — 7 minor versions may include native-image fixes and updated JNI surface. The DJL GraalVM demo uses recent versions. |
| Quarkus | 3.32.2 | (keep) | Current — no change needed. |
| GraalVM | 25.0.3 | (keep) | Installed, macOS ARM. Provides `native-image`. |

**Version bump is the first implementation step** — update parent POM, verify JVM-mode build still passes, then proceed to native. If native fails with bumped versions, the old versions are a fallback data point, but starting with the latest gives the best chance of existing metadata and fixes.

---

## CI Feasibility

**The native gate is local-only.** Native image compilation for macOS ARM requires a macOS ARM runner. GitHub Actions has M1 runners but they're more expensive and add CI complexity.

For the prototype: validate locally, document the result. CI can run the JVM-mode tests to verify the code is correct, but the native gate itself runs on the developer's machine.

If the gate passes and we want CI native builds in C5, options:
- GitHub Actions M1 runner (macos-14 or later)
- Cross-compile to Linux x86_64 for CI, macOS ARM locally
- Native gate as a manual CI workflow (triggered on demand, not per-push)

This decision belongs in C5, not the gate.

---

## Development Workflow

- **JVM mode** for iterative development (fast — seconds). All day-to-day work across C3–C6.
- **Native image** only for gate validation and CI regression (slow — minutes). Production deployment option.
- After the gate passes, the native config is parked in `inference-quarkus`. C5 expands it into a proper Quarkus extension with `@RegisterForReflection` and build-time annotation processing.

---

## Outcome Artifacts

**If PASS:**
- `inference-runtime` has working JNI bridge code — direct input to C3 (wrap with SPI)
- `inference-quarkus` has curated GraalVM config — direct input to C5 (Quarkus extension)
- `NativeImageGateCommand` + `NativeImageGateIT` stay as permanent native regression tests
- Parent POM has updated ORT + DJL versions validated for native

**If FAIL:**
- Failure report identifies which JNI layer failed (ORT, DJL, or both)
- Assessment: GraalVM limitation vs library limitation vs fixable upstream
- Workaround options documented
- C5 proceeds in JVM-only mode; Hortora native binary goal deferred
- JVM-mode code in `inference-runtime` still feeds C3

---

## Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| GraalVM (Oracle) | 25.0.3 | `native-image` compiler, macOS ARM |
| Quarkus | 3.32.2 | Application framework, native build integration |
| ONNX Runtime | bump to latest | Model execution via JNI |
| DJL HuggingFace Tokenizers | bump to latest | Tokenization via JNI |
| maven-download-plugin | latest | Model file download (build-time) |
| Xenova/nli-deberta-v3-xsmall | HuggingFace | Validation model (ONNX export) |
