# Code-Domain Embedding Model Evaluation

**Issue:** casehubio/neural-text#49
**Date:** 2026-07-02
**Status:** Draft

## Context

Hortora/engine#27 identified a vocabulary gap: general-purpose embedding models treat
Java class names (`ConcurrentHashMap`, `@DefaultBean`, `ExceptionMapper`) as generic
tokens. BERT WordPiece splits them into meaningless subwords (`con`, `##current`,
`##hash`, `##map`), degrading both dense and sparse retrieval for code-domain corpora
like the knowledge garden.

Since #49 was filed, two significant changes occurred:
1. **BGE-M3 adoption** — replaces nomic-embed-text + separate SPLADE with a single model
   producing dense (1024d) + sparse + ColBERT embeddings. Uses XLM-RoBERTa BPE tokenizer
   (SentencePiece), not BERT WordPiece.
2. **Three-leg retrieval** (engine#29) — dense + sparse + BM25 via RRF fusion pushed
   precision from 45% to 94%, with BM25 doing the heavy lifting on keyword-gap scenarios.

This evaluation answers: does BGE-M3's tokenizer handle Java identifiers better than
nomic's WordPiece? Can a code-domain model beat BGE-M3's dense embeddings? And does
any dense-only model approach what three-head retrieval already delivers?

## Goal

Research and evaluation only. Build understanding of how tokenization, training data,
and model architecture affect code-domain retrieval quality. Produce reusable evaluation
scripts and a findings report. No code changes to neocortex inference/rag modules.

## Model Roster

### Baseline
| Model | Params | Tokenizer | Training data | Dimensions |
|-------|--------|-----------|---------------|------------|
| BGE-M3 | ~568M | XLM-RoBERTa BPE | Web + multilingual | 1024 (dense+sparse+ColBERT) |

### Original #49 candidates (continuity)
| Model | Params | Tokenizer | Training data | Dimensions |
|-------|--------|-----------|---------------|------------|
| CodeBERT | 125M | RoBERTa BPE | CodeSearchNet (6 languages) | 768 |
| UniXcoder | 125M | RoBERTa BPE | Code + NL pairs | 768 |
| jina-embeddings-v2-base-code | 161M | JinaBERT ALiBi | 150M code pairs | 768 |
| nomic-embed-text-v1.5 | 137M | — | Web + code mix | 768 |

### Skyline (upper bound, not deployable)
| Model | Params | Tokenizer | Training data | Dimensions |
|-------|--------|-----------|---------------|------------|
| nomic-embed-code | 7B | Qwen BPE | Code-specific | 768 |

The skyline model sets an upper bound. If the 7B code model doesn't beat BGE-M3 on
Java identifiers, no code-domain model will. If it does, the gap quantifies what
deployable models leave on the table.

## Evaluation Layers

### Layer 1 — Tokenizer Analysis

Tokenize Java identifiers from the garden benchmark scenarios and compare how each
model's tokenizer splits them.

**Test vocabulary:**
- Class names: `ConcurrentHashMap`, `CopyOnWriteArrayList`, `ExceptionMapper`,
  `ChatModel`, `InMemoryWorkItemTemplateStore`
- CDI annotations: `@DefaultBean`, `@Alternative`, `@ApplicationScoped`, `@Priority`
- Framework identifiers: `AmbiguousResolutionException`, `websearch_to_tsquery`,
  `quarkus.datasource.active`
- Compound concepts: `shadowing`, `fireAsync`, `doChat`

**Measurements:**
- Token count per identifier (fewer = better preservation)
- Whether meaningful subwords survive (e.g. does `HashMap` stay intact?)
- Tokenizer type classification: WordPiece, BPE, SentencePiece, Unigram

**Output:** Table of model × identifier → token sequence. Diagnostic — explains the
mechanism of vocabulary gap. No models eliminated at this stage.

### Layer 2 — Embedding Discrimination

Quick proxy: can each model distinguish semantically different Java concepts that share
surface-level tokens?

**"Should be far" pairs:**
- `ConcurrentHashMap` vs `HashMap`
- `@DefaultBean` vs `default`
- `ChatModel` vs `chat`
- `shadowing` vs `Shadow DOM`
- `stream` (Java Streams) vs `stream` (SSE/HTTP streaming)

**"Should be close" pairs:**
- `@DefaultBean` vs `CDI ambiguous dependency resolution`
- `ConcurrentHashMap` vs `thread-safe map for lock-free concurrency`
- `ExceptionMapper` vs `JAX-RS error handling`

**Measurements:**
- Cosine similarity for each pair
- Delta between "far" and "close" groups — a model with good code-domain understanding
  produces a wide gap; a model treating Java identifiers as generic English produces a
  narrow gap or inverts the expected ordering

**Output:** Similarity scores per model. Models that can't separate `@DefaultBean` from
`default` have the same vocabulary gap as nomic-embed-text, regardless of tokenizer.

### Layer 3 — Full Benchmark

Reuse the engine's 14-scenario harness with existing scored judgments.

**Method:**
1. Embed all ~1,960 garden entries + 28 queries (14 scenarios × KW + NL) per model
2. Cosine similarity retrieval, top-20 per query
3. Score against human-judged baseline (0/1/2 scores from `baseline_scores.json`)
4. Calculate precision metrics matching engine#27/28/29 methodology

**Comparisons:**
- Each candidate dense-only vs BGE-M3 dense-only (isolates embedding quality)
- Each candidate dense-only vs BGE-M3 three-head (dense+sparse+ColBERT) — answers
  "can a better dense model match multi-modal retrieval?"
- Breakdown by failure mode: VOCABULARY_GAP / POLYSEMY / SEMANTIC_WIN / DOMAIN_ABSENCE

**Key question:** Does any code-domain model's dense embedding beat BGE-M3's dense
embedding on vocabulary gap scenarios? How close does the best dense-only result get
to three-head retrieval (94% precision from engine#29)?

**Output:** Precision table per model per scenario, with aggregate scores and
failure-mode breakdowns. Directly comparable to engine#27 baseline.

**Data sources:**
- Garden corpus: `~/.hortora/garden/` (sibling path)
- Queries: `~/claude/casehub/engine/scripts/benchmark/queries.py`
- Baseline scores: `~/claude/casehub/engine/scripts/benchmark/baseline_scores.json`

### Layer 4 — Deployment Feasibility

For models showing promise in Layers 2–3, assess practical deployment on JVM.

**Checks:**
- ONNX export: clean export? What opset? Custom ops that break ONNX Runtime JVM?
- Model size: ONNX file on disk, memory footprint at inference
- Inference latency: time per embedding on CPU (single text, batch of 20)
- Input constraints: max sequence length, required input tensor names
  (`input_mask` vs `attention_mask` — #51 showed this causes real breakage)
- Integration effort: config change / adapter on MultiModalEmbedder / new module

**Output:** Feasibility table per viable candidate with size, latency, ONNX compatibility,
integration complexity, and blockers.

## Deliverables

### Evaluation scripts
```
evaluation/code-domain-embeddings/
├── tokenizer_analysis.py         # Layer 1
├── embedding_discrimination.py   # Layer 2
├── benchmark_runner.py           # Layer 3
├── deployment_check.py           # Layer 4
└── requirements.txt
```

Self-contained. Read garden corpus and benchmark data from engine repo via sibling
paths (`~/claude/casehub/engine/`).

### Results data
```
evaluation/code-domain-embeddings/results/
├── tokenizer_splits.json
├── discrimination_scores.json
├── benchmark_precision.json
└── deployment_feasibility.json
```

Machine-readable for future model comparisons.

### Research report
```
evaluation/code-domain-embeddings/REPORT.md
```

Synthesizes all four layers. Written after evaluation runs. Answers: adopt a code-domain
model, supplement BGE-M3, or stay with three-head retrieval?

## Non-goals

- No changes to `inference-*`, `rag-*`, or `memory-*` modules
- No ONNX model files committed (too large — download instructions in scripts)
- No fine-tuning or training — evaluation of existing pre-trained models only
- No production deployment — that's a separate branch if a winner emerges

## References

- Garden entry: GE-20260627-4712de — vocabulary gap diagnosis
- engine#27: dense-only baseline benchmark (real-world-benchmark.md)
- engine#28: SPLADE hybrid benchmark (hybrid-benchmark.md)
- engine#29: three-leg retrieval findings (retrieval-research.md)
- Benchmark scripts: `~/claude/casehub/engine/scripts/benchmark/`
- BGE-M3 integration: `inference-bge-m3/` module in this repo
