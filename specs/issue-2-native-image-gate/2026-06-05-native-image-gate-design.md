# Native Image Gate — Design Spec

**Date:** 2026-06-05
**Issue:** casehubio/neural-text#2
**Chapter:** C2 (ARC42STORIES §9.3)
**Status:** Draft

---

## Goal

Prove that ONNX Runtime JNI and HuggingFace Tokenizers JNI both load and execute correctly inside a Quarkus native image binary on macOS ARM (Apple Silicon). Binary pass/fail — either both JNI layers work or they don't.

This gates `inference-quarkus` (C5) native image support and Hortora's distributable native binary goal. If the gate fails, C5 proceeds in JVM-only mode.

## Non-Goals

- Production code. This is a throwaway validation module.
- REST endpoints or HTTP-level testing.
- Dense embeddings, SPLADE, or any model type beyond NLI.
- Quarkus extension development (that's C5).
- Performance benchmarking.

## Pass/Fail Criteria

**Pass:** A `@QuarkusIntegrationTest` running against the native binary successfully:
1. Loads a HuggingFace tokenizer via DJL JNI
2. Tokenizes a text pair (premise + hypothesis)
3. Runs ONNX inference via ONNX Runtime JNI
4. Returns a `float[3]` logits tensor (entailment/neutral/contradiction)

**Fail:** Any of the above steps throws a JNI error, native library load failure, or GraalVM build error that cannot be resolved with configuration. Document what broke, whether it's a GraalVM or library limitation, and whether upstream changes are needed.

---

## Module Structure

A new Maven module `native-image-prototype/` at the project root, gated behind a Maven profile so normal builds skip it.

```
native-image-prototype/
  pom.xml
  src/main/java/io/casehub/inference/prototype/
    NativeImageGateApp.java
  src/main/resources/
    application.properties
    META-INF/native-image/io.casehub/native-image-prototype/
      reflect-config.json
      jni-config.json
      resource-config.json
      native-image.properties
  src/test/java/io/casehub/inference/prototype/
    NativeImageGateIT.java
```

### Parent POM Integration

The module is activated via a `native-prototype` profile:

```xml
<profile>
  <id>native-prototype</id>
  <modules>
    <module>native-image-prototype</module>
  </modules>
</profile>
```

Not listed in the default `<modules>` block — regular `mvn clean install` skips it entirely.

### Build Command

```bash
JAVA_HOME=$(/usr/libexec/java_home -v 25) mvn clean verify -pl native-image-prototype -Pnative-prototype -Dnative
```

GraalVM 25.0.3 (Oracle, macOS ARM) provides `native-image`. The project compiles to Java 21 bytecode.

---

## Model Provisioning

**Model:** `cross-encoder/nli-deberta-v3-xsmall` — a small NLI model (~90MB ONNX, ~700KB tokenizer.json). Chosen because it exercises the exact production use case (tokenize text pair → infer → 3-class logits) with the smallest footprint.

**Download mechanism:** `exec-maven-plugin` calling `huggingface-cli download` during `generate-resources` phase. Downloads to `target/models/nli-deberta-v3-xsmall/`.

```xml
<plugin>
  <groupId>org.codehaus.mojo</groupId>
  <artifactId>exec-maven-plugin</artifactId>
  <executions>
    <execution>
      <id>download-model</id>
      <phase>generate-resources</phase>
      <goals><goal>exec</goal></goals>
      <configuration>
        <executable>huggingface-cli</executable>
        <arguments>
          <argument>download</argument>
          <argument>cross-encoder/nli-deberta-v3-xsmall</argument>
          <argument>--local-dir</argument>
          <argument>${project.build.directory}/models/nli-deberta-v3-xsmall</argument>
        </arguments>
      </configuration>
    </execution>
  </executions>
</plugin>
```

**CI caching:** `huggingface-cli` uses `~/.cache/huggingface/hub/` as its download cache. GitHub Actions caches this directory between runs with a stable key based on the model name. First run downloads, subsequent runs are a no-op.

**Pre-requisite:** `huggingface-cli` must be installed (`pip install huggingface_hub`). Document in the module README.

### Model Path Configuration

```properties
# application.properties
inference.prototype.model-dir=${project.build.directory}/models/nli-deberta-v3-xsmall
```

---

## Prototype Code

### NativeImageGateApp.java

A `@ApplicationScoped` CDI bean with no domain types or SPI. Raw JNI calls only.

Responsibilities:
- Load HuggingFace tokenizer from `tokenizer.json` via DJL's `HuggingFaceTokenizer` JNI binding
- Create `OrtEnvironment` and `OrtSession` from `model.onnx` via ONNX Runtime JNI
- Expose `float[] classify(String premise, String hypothesis)` that:
  1. Tokenizes the text pair → token IDs + attention mask
  2. Creates `OnnxTensor` inputs from the token arrays
  3. Runs `session.run()` → raw output tensors
  4. Extracts and returns the `float[3]` logits

No error recovery, no pooling, no lifecycle management beyond `@PreDestroy` cleanup. This is throwaway code.

### NativeImageGateIT.java

A `@QuarkusIntegrationTest` (not `@QuarkusTest`). Quarkus runs this against the native binary when built with `-Dnative`.

Test case:
```java
classify("The weather is sunny", "It is raining")
→ float[3] where contradiction score is highest
```

Assertions:
- Result is non-null
- Result has exactly 3 elements
- Contradiction index (typically [2]) has the highest value
- No JNI exceptions thrown

The assertion on contradiction being highest is a sanity check, not an accuracy test. If the model loads and runs but produces garbage logits, that's a different problem from JNI failure.

---

## GraalVM Native Image Configuration

### Discovery Process

1. Get the app running in JVM mode with both JNI layers working — validate the code is correct before attempting native
2. Run with tracing agent: `java -agentlib:native-image-agent=config-output-dir=target/agent-config -jar target/quarkus-app/quarkus-run.jar`
3. Exercise the classify path to capture JNI crossings
4. Curate the agent output into hand-written config files with comments explaining each entry

### Config Files

All in `src/main/resources/META-INF/native-image/io.casehub/native-image-prototype/`:

- **`jni-config.json`** — ONNX Runtime JNI bridge classes (`OrtEnvironment`, `OrtSession`, `OnnxTensor`, etc.) and DJL tokenizer JNI bridge classes. These cross the JNI boundary.
- **`reflect-config.json`** — classes discovered via reflection (platform detection, native lib loading).
- **`resource-config.json`** — native `.dylib` files bundled inside JARs (`ai/onnxruntime/native/osx-aarch64/libonnxruntime.dylib` and DJL's equivalent). Must be registered as resources so GraalVM includes them in the native image.
- **`native-image.properties`** — `--initialize-at-run-time` entries for classes that load native libraries in static initializers. Most likely failure point.

### Expected Challenges

**1. `--initialize-at-run-time` for native lib loaders (high likelihood)**
Both libraries load `.dylib` files during class initialization. GraalVM runs class initializers at build time where the libs aren't available. Fix: defer those classes to runtime init.

**2. Missing JNI entries (medium likelihood)**
Tracing agent only captures exercised code paths. Fix: inspect ONNX Runtime and DJL source for `native` method declarations and register them manually.

**3. Native lib extraction (medium likelihood)**
Both JARs bundle native libs extracted to a temp dir at runtime. In native image, JAR resource handling differs. Fix: may need custom extraction or library path configuration.

### Iterative Approach

The native build will likely fail on the first attempt. The process is:
1. Attempt build
2. Read the error (missing class, missing resource, build-time init failure)
3. Add the appropriate config entry
4. Retry

Each fix is documented in the config file with a comment explaining what it resolves. This documentation feeds directly into C5's Quarkus extension.

---

## Development Workflow

- **JVM mode** for iterative development (fast — seconds). Get the code working first, then tackle native.
- **Native image** only for the final gate validation (slow — minutes).
- After the gate passes, all subsequent development (C3–C6) runs on JVM. Native image config is parked until C5.

---

## Outcome Artifacts

**If PASS:**
- The curated GraalVM config files — direct input to C5's Quarkus extension
- Documentation of which classes need runtime init, JNI registration, and resource bundling
- Confidence that `inference-quarkus` can target native image

**If FAIL:**
- Documentation of what broke and why
- Assessment: GraalVM limitation vs library limitation vs fixable with upstream contribution
- Recommendation: JVM-only deployment, or wait for specific upstream fix
- C5 proceeds in JVM-only mode; Hortora native binary goal deferred

---

## Dependencies

| Dependency | Version | Purpose |
|---|---|---|
| GraalVM (Oracle) | 25.0.3 | `native-image` compiler, macOS ARM |
| Quarkus | 3.32.2 | Application framework, native build integration |
| ONNX Runtime | 1.17.3 | Model execution via JNI |
| DJL HuggingFace Tokenizers | 0.29.0 | Tokenization via JNI |
| `huggingface-cli` | latest | Model download (build-time, not runtime) |
| `cross-encoder/nli-deberta-v3-xsmall` | HuggingFace | Validation model (~90MB) |

## Cleanup

After the gate passes (or fails), the `native-image-prototype/` module is removed from the repo. The `native-prototype` profile is removed from the parent POM. The config files and documentation are preserved — they move to C5's `inference-quarkus` module (on pass) or to the issue's closing comment (on fail).
